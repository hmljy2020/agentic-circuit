"""AST-only elaboration for the frozen ACPy v0.3 semantic graph.

This module intentionally stops before ACIR text emission.  It provides the
source-to-semantic half of the P3 vertical slice without depending on a private
or unregistered dialect.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from ._diagnostics import Diagnostic, SourceSpan
from ._semantic_v03 import (
    NamedType,
    PayloadDeclaration,
    PayloadField,
    PayloadType,
    PortGroup,
    QueueConstraint,
    ScalarType,
    SemanticBuilder,
    SemanticError,
    SemanticParameter,
    SemanticProgram,
    VarOperation,
    VarRegion,
    VarValue,
    davincioo_core_catalog,
)
from ._source import DefinitionSite, SourceCaptureError, SourceUnit, load_source_unit
from ._static_eval import FrozenMap, StaticValue, validate_ijson_value


_SCALARS = {
    "i1": ScalarType("i1", 1),
    "u2": ScalarType("u2", 2),
    "u8": ScalarType("u8", 8),
    "u16": ScalarType("u16", 16),
    "u32": ScalarType("u32", 32),
    "u64": ScalarType("u64", 64),
}


@dataclass(frozen=True, slots=True)
class SemanticCaptureRequest:
    entry: Path
    workspace: Path
    system: str
    const_arguments: tuple[tuple[str, StaticValue], ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticFrontendResult:
    program: SemanticProgram | None
    diagnostics: tuple[Diagnostic, ...]


class _ElaborationFailure(ValueError):
    def __init__(self, code: str, message: str, source: SourceSpan | None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.source = source


def _span(unit: SourceUnit, node: ast.AST) -> SourceSpan:
    end_line = getattr(node, "end_lineno", None) or node.lineno
    end_column = getattr(node, "end_col_offset", None)
    if end_column is None:
        end_column = node.col_offset
    return SourceSpan(
        unit.path,
        node.lineno,
        node.col_offset + 1,
        end_line,
        end_column + 1,
    )


def _qualified_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _decorated(site: DefinitionSite, name: str) -> bool:
    return any(candidate.rsplit(".", 1)[-1] == name for candidate in site.decorator_names)


def _call_name(node: ast.Call) -> str:
    return _qualified_name(node.func).rsplit(".", 1)[-1]


class _TypeEnvironment:
    def __init__(self, unit: SourceUnit) -> None:
        self.unit = unit
        self.declarations: dict[str, PayloadDeclaration] = {}
        self.configs: dict[str, tuple[PayloadField, ...]] = {}
        for site in unit.definitions:
            if not isinstance(site.node, ast.ClassDef):
                continue
            if _decorated(site, "struct"):
                declaration = PayloadDeclaration(
                    "struct", site.name, self._fields(site.node)
                )
                self._insert(self.declarations, site.name, declaration, site.span)
            elif _decorated(site, "config"):
                self._insert(self.configs, site.name, self._fields(site.node), site.span)

    @staticmethod
    def _insert(target: dict, name: str, value: object, span: SourceSpan) -> None:
        if name in target:
            raise _ElaborationFailure(
                "ACPY-V03-TYPE-001", f"duplicate type {name!r}", span
            )
        target[name] = value

    def _fields(self, node: ast.ClassDef) -> tuple[PayloadField, ...]:
        fields: list[PayloadField] = []
        for statement in node.body:
            if isinstance(statement, ast.Expr) and isinstance(
                statement.value, ast.Constant
            ) and isinstance(statement.value.value, str):
                continue
            if not isinstance(statement, ast.AnnAssign) or not isinstance(
                statement.target, ast.Name
            ) or statement.value is not None:
                raise _ElaborationFailure(
                    "ACPY-V03-TYPE-002",
                    "config/struct bodies may contain annotated fields only",
                    _span(self.unit, statement),
                )
            fields.append(
                PayloadField(statement.target.id, self.resolve(statement.annotation))
            )
        return tuple(fields)

    def resolve(self, node: ast.expr) -> PayloadType:
        name = _qualified_name(node).rsplit(".", 1)[-1]
        name = {"bool": "i1", "int": "u64"}.get(name, name)
        if name in _SCALARS:
            return _SCALARS[name]
        if name in self.declarations:
            return NamedType("struct", name)
        raise _ElaborationFailure(
            "ACPY-V03-TYPE-003",
            f"unsupported or unresolved payload type {ast.unparse(node)!r}",
            _span(self.unit, node),
        )

    def field(self, root: PayloadType, name: str, node: ast.AST) -> PayloadType:
        if not isinstance(root, NamedType) or root.kind != "struct":
            raise _ElaborationFailure(
                "ACPY-V03-VAR-002", "field access requires a struct value", _span(self.unit, node)
            )
        declaration = self.declarations[root.name]
        for field in declaration.fields:
            if field.name == name:
                return field.type
        raise _ElaborationFailure(
            "ACPY-V03-VAR-002",
            f"struct {root.name!r} has no field {name!r}",
            _span(self.unit, node),
        )


class _VarLowerer:
    def __init__(
        self,
        unit: SourceUnit,
        types: _TypeEnvironment,
        helper: ast.FunctionDef,
        input_type: PayloadType,
        output_type: PayloadType,
        region_id: str,
    ) -> None:
        self.unit = unit
        self.types = types
        self.helper = helper
        self.input_type = input_type
        self.output_type = output_type
        self.region_id = region_id
        self.operations: list[VarOperation] = []
        self.values: dict[str, VarValue] = {}
        arguments = [*helper.args.posonlyargs, *helper.args.args]
        if (
            len(arguments) != 1
            or helper.args.kwonlyargs
            or helper.args.vararg is not None
            or helper.args.kwarg is not None
        ):
            raise _ElaborationFailure(
                "ACPY-V03-VAR-001",
                "compute helper requires exactly one positional parameter",
                _span(unit, helper),
            )
        self.parameter = arguments[0].arg
        self.values[self.parameter] = VarValue(
            "v0", input_type, _span(unit, arguments[0])
        )

    def lower(self) -> VarRegion:
        statements = tuple(
            statement
            for statement in self.helper.body
            if not (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            )
        )
        if len(statements) != 1 or not isinstance(statements[0], ast.Return):
            raise _ElaborationFailure(
                "ACPY-V03-VAR-001",
                "compute helper must contain one pure return expression",
                _span(self.unit, self.helper),
            )
        statement = statements[0]
        if statement.value is None:
            raise _ElaborationFailure(
                "ACPY-V03-VAR-001", "compute helper must return a value", _span(self.unit, statement)
            )
        result = self._expression(statement.value, self.output_type)
        if result.type != self.output_type:
            raise _ElaborationFailure(
                "ACPY-V03-VAR-003",
                "compute helper result does not match its return annotation",
                _span(self.unit, statement.value),
            )
        self.operations.append(
            VarOperation(
                f"vo{len(self.operations)}",
                "yield",
                (result.id,),
                (),
                source=_span(self.unit, statement),
            )
        )
        region = VarRegion(
            self.region_id,
            (self.values[self.parameter],),
            tuple(self.operations),
            (result.id,),
        )
        region.verify()
        return region

    def _result(
        self,
        opcode: str,
        operands: tuple[VarValue, ...],
        result_type: PayloadType,
        node: ast.AST,
        parameters: tuple[SemanticParameter, ...] = (),
    ) -> VarValue:
        value = VarValue(
            f"v{len(self.values)}", result_type, _span(self.unit, node)
        )
        operation = VarOperation(
            f"vo{len(self.operations)}",
            opcode,
            tuple(operand.id for operand in operands),
            (value,),
            tuple(sorted(parameters, key=lambda item: item.name)),
            _span(self.unit, node),
        )
        self.operations.append(operation)
        self.values[value.id] = value
        return value

    def _expression(
        self, node: ast.expr, expected: PayloadType | None = None
    ) -> VarValue:
        if isinstance(node, ast.Name):
            if node.id != self.parameter:
                raise _ElaborationFailure(
                    "ACPY-V03-VAR-004",
                    f"compute helper captures open name {node.id!r}",
                    _span(self.unit, node),
                )
            return self.values[node.id]
        if isinstance(node, ast.Attribute):
            root = self._expression(node.value)
            result_type = self.types.field(root.type, node.attr, node)
            return self._result(
                "get",
                (root,),
                result_type,
                node,
                (SemanticParameter("field", node.attr),),
            )
        if isinstance(node, ast.Constant) and type(node.value) in {bool, int}:
            result_type = expected
            if result_type is None:
                result_type = _SCALARS["i1"] if type(node.value) is bool else _SCALARS["u64"]
            if not isinstance(result_type, ScalarType):
                raise _ElaborationFailure(
                    "ACPY-V03-VAR-003", "literal requires a scalar context", _span(self.unit, node)
                )
            return self._result(
                "constant",
                (),
                result_type,
                node,
                (SemanticParameter("value", node.value),),
            )
        if isinstance(node, ast.BinOp):
            left = self._expression(node.left, expected)
            right = self._expression(node.right, left.type)
            if left.type != right.type or not isinstance(left.type, ScalarType):
                raise _ElaborationFailure(
                    "ACPY-V03-VAR-003",
                    "binary operands must have one scalar type",
                    _span(self.unit, node),
                )
            operators = {
                ast.Add: "add",
                ast.Sub: "sub",
                ast.Mult: "mul",
                ast.BitAnd: "and",
                ast.BitOr: "or",
                ast.BitXor: "xor",
            }
            operator = operators.get(type(node.op))
            if operator is None:
                raise _ElaborationFailure(
                    "ACPY-V03-VAR-003", "unsupported binary operator", _span(self.unit, node)
                )
            return self._result(
                "binary",
                (left, right),
                left.type,
                node,
                (SemanticParameter("operator", operator),),
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            declaration = self.types.declarations.get(node.func.id)
            if declaration is None:
                raise _ElaborationFailure(
                    "ACPY-V03-VAR-004",
                    "compute helper may only call frozen struct constructors",
                    _span(self.unit, node),
                )
            if node.args or any(keyword.arg is None for keyword in node.keywords):
                raise _ElaborationFailure(
                    "ACPY-V03-VAR-003",
                    "struct construction requires explicit keyword fields",
                    _span(self.unit, node),
                )
            keyword_map = {keyword.arg: keyword.value for keyword in node.keywords}
            field_names = tuple(field.name for field in declaration.fields)
            if tuple(keyword_map) != field_names:
                raise _ElaborationFailure(
                    "ACPY-V03-VAR-003",
                    "struct construction must provide fields in declaration order",
                    _span(self.unit, node),
                )
            operands = tuple(
                self._expression(keyword_map[field.name], field.type)
                for field in declaration.fields
            )
            result_type = NamedType("struct", declaration.name)
            return self._result(
                "struct",
                operands,
                result_type,
                node,
                (
                    SemanticParameter("fields", ",".join(field_names)),
                    SemanticParameter("type", result_type),
                ),
            )
        raise _ElaborationFailure(
            "ACPY-V03-VAR-004",
            f"impure or unsupported compute syntax: {type(node).__name__}",
            _span(self.unit, node),
        )


class _SystemElaborator:
    def __init__(
        self,
        unit: SourceUnit,
        types: _TypeEnvironment,
        system: DefinitionSite,
        const_arguments: tuple[tuple[str, StaticValue], ...],
    ) -> None:
        self.unit = unit
        self.types = types
        self.system = system
        self.const_arguments = const_arguments
        self.helpers = {
            site.name: site.node
            for site in unit.definitions
            if isinstance(site.node, ast.FunctionDef)
            and not site.decorator_names
        }
        assert isinstance(system.node, ast.FunctionDef)
        self.builder = SemanticBuilder(system.name, system.name, system.span)
        for declaration in types.declarations.values():
            self.builder.add_declaration(declaration)
        self.queues: dict[str, str] = {}
        self.queue_types: dict[str, PayloadType] = {}
        self.catalog = davincioo_core_catalog()

    def run(self) -> SemanticProgram:
        self._validate_consts()
        assert isinstance(self.system.node, ast.FunctionDef)
        for statement in self.system.node.body:
            if isinstance(statement, ast.Assign):
                self._assignment(statement)
            elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                self._observe(statement.value)
            elif isinstance(statement, ast.Return) and statement.value is None:
                continue
            elif isinstance(statement, ast.Pass):
                continue
            else:
                raise _ElaborationFailure(
                    "ACPY-V03-SYNTAX-001",
                    f"unsupported system statement {type(statement).__name__}",
                    _span(self.unit, statement),
                )
        return self.builder.freeze()

    def _validate_consts(self) -> None:
        assert isinstance(self.system.node, ast.FunctionDef)
        arguments = [
            *self.system.node.args.posonlyargs,
            *self.system.node.args.args,
            *self.system.node.args.kwonlyargs,
        ]
        expected_names = tuple(argument.arg for argument in arguments)
        actual_names = tuple(name for name, _ in self.const_arguments)
        if actual_names != tuple(sorted(actual_names)) or len(actual_names) != len(
            set(actual_names)
        ):
            raise _ElaborationFailure(
                "ACPY-V03-CONST-001",
                "const arguments must be unique and canonicalized",
                self.system.span,
            )
        if set(actual_names) != set(expected_names):
            raise _ElaborationFailure(
                "ACPY-V03-CONST-001",
                "system const argument binding is incomplete or contains extras",
                self.system.span,
            )
        values = dict(self.const_arguments)
        for argument in arguments:
            annotation = argument.annotation
            valid = (
                isinstance(annotation, ast.Subscript)
                and _qualified_name(annotation.value).rsplit(".", 1)[-1] == "const"
                and isinstance(annotation.slice, ast.Name)
                and annotation.slice.id in self.types.configs
            )
            if not valid:
                raise _ElaborationFailure(
                    "ACPY-V03-CONST-002",
                    "system parameters must use ac.const[Config]",
                    _span(self.unit, argument),
                )
            value = values[argument.arg]
            validate_ijson_value(value)
            if not isinstance(value, FrozenMap):
                raise _ElaborationFailure(
                    "ACPY-V03-CONST-002",
                    "config specialization must be a frozen record",
                    _span(self.unit, argument),
                )
            fields = self.types.configs[annotation.slice.id]
            if set(value) != {field.name for field in fields}:
                raise _ElaborationFailure(
                    "ACPY-V03-CONST-002",
                    "config specialization fields do not match declaration order",
                    _span(self.unit, argument),
                )

    def _assignment(self, statement: ast.Assign) -> None:
        if (
            len(statement.targets) != 1
            or not isinstance(statement.targets[0], ast.Name)
            or not isinstance(statement.value, ast.Call)
        ):
            raise _ElaborationFailure(
                "ACPY-V03-SYNTAX-001",
                "system assignments require one name and one primitive call",
                _span(self.unit, statement),
            )
        target = statement.targets[0].id
        if target in self.queues:
            raise _ElaborationFailure(
                "ACPY-V03-SYNTAX-001", f"Queue name {target!r} is rebound", _span(self.unit, statement.targets[0])
            )
        call = statement.value
        name = _call_name(call)
        if name == "source":
            self._source(target, call)
        elif name == "compute":
            self._compute(target, call)
        else:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-001",
                f"unsupported P3 primitive {name!r}",
                _span(self.unit, call),
            )

    def _queue(self, payload: PayloadType, node: ast.AST) -> str:
        return self.builder.add_queue(
            QueueConstraint(payload, depth=1, latency=1, rate=1, domain="core"),
            _span(self.unit, node),
        )

    def _source(self, target: str, call: ast.Call) -> None:
        if len(call.args) != 1 or call.keywords:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.source requires one payload type", _span(self.unit, call)
            )
        payload = self.types.resolve(call.args[0])
        queue = self._queue(payload, call)
        self.builder.add_block(
            "source",
            self.builder.root_scope,
            (),
            (PortGroup("output", "produce", (queue,)),),
            source=_span(self.unit, call),
            catalog=self.catalog,
        )
        self.queues[target] = queue
        self.queue_types[target] = payload

    def _compute(self, target: str, call: ast.Call) -> None:
        if (
            len(call.args) != 2
            or call.keywords
            or not isinstance(call.args[0], ast.Name)
            or not isinstance(call.args[1], ast.Name)
        ):
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002",
                "ac.compute requires a Queue name and pure helper name",
                _span(self.unit, call),
            )
        input_name = call.args[0].id
        input_queue = self.queues.get(input_name)
        input_type = self.queue_types.get(input_name)
        helper = self.helpers.get(call.args[1].id)
        if input_queue is None or input_type is None or helper is None:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-003",
                "compute input or helper does not resolve",
                _span(self.unit, call),
            )
        if helper.returns is None:
            raise _ElaborationFailure(
                "ACPY-V03-TYPE-003", "compute helper requires a return annotation", _span(self.unit, helper)
            )
        output_type = self.types.resolve(helper.returns)
        region_id = self.builder.next_region_id
        region = _VarLowerer(
            self.unit, self.types, helper, input_type, output_type, region_id
        ).lower()
        self.builder.add_region(region)
        output_queue = self._queue(output_type, call)
        self.builder.add_block(
            "compute",
            self.builder.root_scope,
            (PortGroup("input", "consume", (input_queue,)),),
            (PortGroup("output", "produce", (output_queue,)),),
            regions=(region_id,),
            source=_span(self.unit, call),
            catalog=self.catalog,
        )
        self.queues[target] = output_queue
        self.queue_types[target] = output_type

    def _observe(self, call: ast.Call) -> None:
        if (
            _call_name(call) != "observe"
            or len(call.args) != 1
            or call.keywords
            or not isinstance(call.args[0], ast.Name)
        ):
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "expression statement must be ac.observe(Queue)", _span(self.unit, call)
            )
        queue = self.queues.get(call.args[0].id)
        if queue is None:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-003", "observe Queue does not resolve", _span(self.unit, call)
            )
        self.builder.add_block(
            "observe",
            self.builder.root_scope,
            (PortGroup("input", "observe", (queue,)),),
            (),
            source=_span(self.unit, call),
            catalog=self.catalog,
        )


def elaborate_semantic_v03(request: SemanticCaptureRequest) -> SemanticFrontendResult:
    """Capture one system into a deterministic v0.3 semantic graph."""

    try:
        unit = load_source_unit(request.entry, request.workspace)
        types = _TypeEnvironment(unit)
        systems = tuple(
            site
            for site in unit.definitions
            if isinstance(site.node, ast.FunctionDef)
            and _decorated(site, "system")
            and (site.name == request.system or site.qualified_name == request.system)
        )
        if len(systems) != 1:
            raise _ElaborationFailure(
                "ACPY-V03-SYMBOL-001",
                f"system {request.system!r} is missing or ambiguous",
                systems[0].span if systems else None,
            )
        program = _SystemElaborator(
            unit, types, systems[0], request.const_arguments
        ).run()
        program.verify(require_frozen_queues=True)
        return SemanticFrontendResult(program, ())
    except _ElaborationFailure as error:
        diagnostic = Diagnostic(
            stage="semantic-elaboration",
            code=error.code,
            severity="error",
            message=error.message,
            source=error.source,
        )
        return SemanticFrontendResult(None, (diagnostic,))
    except (SemanticError, SourceCaptureError, ValueError) as error:
        diagnostic = Diagnostic(
            stage="semantic-elaboration",
            code="ACPY-V03-VERIFY-001",
            severity="error",
            message=str(error),
        )
        return SemanticFrontendResult(None, (diagnostic,))
