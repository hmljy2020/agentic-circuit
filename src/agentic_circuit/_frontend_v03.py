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
    FieldDescriptor,
    NamedType,
    PayloadDeclaration,
    PayloadField,
    PayloadType,
    PortGroup,
    Policy,
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
from ._static_eval import (
    FrozenMap,
    StaticEnvironment,
    StaticEvalError,
    StaticValue,
    evaluate_static,
    validate_ijson_value,
)


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

    def descriptor(self, node: ast.expr) -> FieldDescriptor:
        path: list[str] = []
        cursor = node
        while isinstance(cursor, ast.Attribute):
            path.append(cursor.attr)
            cursor = cursor.value
        if not isinstance(cursor, ast.Name) or cursor.id not in self.declarations:
            raise _ElaborationFailure(
                "ACPY-V03-TYPE-004",
                "field descriptor must start at a frozen payload declaration",
                _span(self.unit, node),
            )
        root = NamedType("struct", cursor.id)
        leaf: PayloadType = root
        for component in reversed(path):
            leaf = self.field(leaf, component, node)
        return FieldDescriptor(root, tuple(reversed(path)), leaf)


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
        self.collections: dict[str, tuple[str, ...]] = {}
        self.queue_types: dict[str, PayloadType] = {}
        self.queue_order: list[str] = []
        self.catalog = davincioo_core_catalog()
        self.static_values: dict[str, StaticValue] = {}
        self.static_locals: dict[str, StaticValue] = {}
        self.scope_stack = [self.builder.root_scope]
        self.scope_parents: dict[str, str | None] = {
            self.builder.root_scope: None
        }
        self.producer_scope: dict[str, str] = {}
        self.use_scopes: dict[str, list[str]] = {}

    def run(self) -> SemanticProgram:
        self._validate_consts()
        assert isinstance(self.system.node, ast.FunctionDef)
        self._statements(self.system.node.body)
        self._infer_scope_io()
        return self.builder.freeze()

    @property
    def current_scope(self) -> str:
        return self.scope_stack[-1]

    def _statements(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            self._statement(statement)

    def _statement(self, statement: ast.stmt) -> None:
        if isinstance(statement, ast.Assign):
            self._assignment(statement)
            return
        if isinstance(statement, ast.Expr):
            if isinstance(statement.value, ast.Constant) and isinstance(
                statement.value.value, str
            ):
                return
            if isinstance(statement.value, ast.Call):
                self._observe(statement.value)
                return
        if isinstance(statement, ast.If):
            condition = self._static(statement.test)
            if type(condition) is not bool:
                raise _ElaborationFailure(
                    "ACPY-V03-STATIC-001",
                    "static if condition must be boolean",
                    _span(self.unit, statement.test),
                )
            self._statements(statement.body if condition else statement.orelse)
            return
        if isinstance(statement, ast.For):
            self._for(statement)
            return
        if isinstance(statement, ast.With):
            self._with_scope(statement)
            return
        if isinstance(statement, ast.Return) and statement.value is None:
            return
        if isinstance(statement, ast.Pass):
            return
        raise _ElaborationFailure(
            "ACPY-V03-SYNTAX-001",
            f"unsupported system statement {type(statement).__name__}",
            _span(self.unit, statement),
        )

    def _static(self, node: ast.AST) -> StaticValue:
        try:
            return evaluate_static(
                node,
                StaticEnvironment({**self.static_values, **self.static_locals}),
            )
        except StaticEvalError as error:
            raise _ElaborationFailure(
                "ACPY-V03-STATIC-001", str(error), _span(self.unit, node)
            ) from error

    def _for(self, statement: ast.For) -> None:
        if statement.orelse or not isinstance(statement.target, ast.Name):
            raise _ElaborationFailure(
                "ACPY-V03-STATIC-002",
                "static for requires one name target and no else",
                _span(self.unit, statement),
            )
        values = self._static(statement.iter)
        if not isinstance(values, tuple):
            raise _ElaborationFailure(
                "ACPY-V03-STATIC-002",
                "static for iterable must be a bounded tuple/range",
                _span(self.unit, statement.iter),
            )
        name = statement.target.id
        missing = object()
        previous = self.static_locals.get(name, missing)
        try:
            for value in values:
                self.static_locals[name] = value
                self._statements(statement.body)
        finally:
            if previous is missing:
                self.static_locals.pop(name, None)
            else:
                self.static_locals[name] = previous  # type: ignore[assignment]

    def _with_scope(self, statement: ast.With) -> None:
        if (
            len(statement.items) != 1
            or statement.items[0].optional_vars is not None
            or not isinstance(statement.items[0].context_expr, ast.Call)
        ):
            raise _ElaborationFailure(
                "ACPY-V03-SCOPE-001",
                "with requires one ac.scope context without an as target",
                _span(self.unit, statement),
            )
        call = statement.items[0].context_expr
        if _call_name(call) != "scope" or len(call.args) != 1 or call.keywords:
            raise _ElaborationFailure(
                "ACPY-V03-SCOPE-001",
                "ac.scope requires one static name",
                _span(self.unit, call),
            )
        name = self._static(call.args[0])
        if not isinstance(name, str) or not name:
            raise _ElaborationFailure(
                "ACPY-V03-SCOPE-001",
                "scope name must be a non-empty static string",
                _span(self.unit, call.args[0]),
            )
        parent = self.current_scope
        scope = self.builder.add_scope(name, parent, _span(self.unit, statement))
        self.scope_parents[scope] = parent
        self.scope_stack.append(scope)
        try:
            self._statements(statement.body)
        finally:
            self.scope_stack.pop()

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
        self.static_values = values
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

    def _target_names(self, target: ast.expr) -> tuple[str, ...]:
        if isinstance(target, ast.Name):
            return (target.id,)
        if isinstance(target, (ast.Tuple, ast.List)):
            return tuple(
                name for child in target.elts for name in self._target_names(child)
            )
        raise _ElaborationFailure(
            "ACPY-V03-SYNTAX-001",
            "primitive results require name or tuple/list targets",
            _span(self.unit, target),
        )

    def _bind(self, target: ast.expr, queues: tuple[str, ...]) -> None:
        names = self._target_names(target)
        if any(name in self.queues or name in self.collections for name in names):
            raise _ElaborationFailure(
                "ACPY-V03-SYNTAX-001",
                "Queue or collection name is rebound",
                _span(self.unit, target),
            )
        if isinstance(target, ast.Name):
            if len(queues) == 1:
                self.queues[target.id] = queues[0]
            else:
                self.collections[target.id] = queues
            return
        assert isinstance(target, (ast.Tuple, ast.List))
        if len(target.elts) != len(queues):
            raise _ElaborationFailure(
                "ACPY-V03-SYNTAX-001",
                "primitive result arity does not match assignment target",
                _span(self.unit, target),
            )
        for child, queue in zip(target.elts, queues, strict=True):
            if not isinstance(child, ast.Name):
                raise _ElaborationFailure(
                    "ACPY-V03-SYNTAX-001",
                    "nested primitive result destructuring is not supported",
                    _span(self.unit, child),
                )
            self.queues[child.id] = queue

    def _assignment(self, statement: ast.Assign) -> None:
        if len(statement.targets) != 1 or not isinstance(statement.value, ast.Call):
            raise _ElaborationFailure(
                "ACPY-V03-SYNTAX-001",
                "system assignments require one target and one primitive call",
                _span(self.unit, statement),
            )
        target = statement.targets[0]
        call = statement.value
        name = _call_name(call)
        if name == "source":
            outputs = self._source(call)
        elif name == "compute":
            outputs = self._compute(call)
        elif name == "queue":
            outputs = self._transport(call)
        elif name == "route":
            outputs = self._route(call)
        elif name == "fork":
            outputs = self._fork(call)
        elif name == "merge":
            outputs = self._merge(call)
        else:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-001",
                f"unsupported P4 primitive {name!r}",
                _span(self.unit, call),
            )
        self._bind(target, outputs)

    def _queue(
        self,
        payload: PayloadType,
        node: ast.AST,
        *,
        depth: int = 1,
        latency: int = 1,
        rate: int = 1,
        domain: str = "core",
    ) -> str:
        queue = self.builder.add_queue(
            QueueConstraint(payload, depth, latency, rate, domain),
            _span(self.unit, node),
        )
        self.queue_types[queue] = payload
        self.queue_order.append(queue)
        return queue

    def _queue_like(self, queue: str, node: ast.AST) -> str:
        return self._queue(self.queue_types[queue], node)

    def _queue_ref(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name) and node.id in self.queues:
            return self.queues[node.id]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in self.collections
        ):
            index = self._static(node.slice)
            if type(index) is not int:
                raise _ElaborationFailure(
                    "ACPY-V03-CALL-003",
                    "Queue collection index must be a static integer",
                    _span(self.unit, node.slice),
                )
            try:
                return self.collections[node.value.id][index]
            except IndexError as error:
                raise _ElaborationFailure(
                    "ACPY-V03-CALL-003",
                    "Queue collection index is out of range",
                    _span(self.unit, node),
                ) from error
        raise _ElaborationFailure(
            "ACPY-V03-CALL-003", "Queue reference does not resolve", _span(self.unit, node)
        )

    def _queue_collection(self, node: ast.expr) -> tuple[str, ...]:
        if isinstance(node, ast.Name) and node.id in self.collections:
            return self.collections[node.id]
        if isinstance(node, (ast.Tuple, ast.List)):
            return tuple(self._queue_ref(item) for item in node.elts)
        raise _ElaborationFailure(
            "ACPY-V03-CALL-003",
            "expected a static Queue tuple/list",
            _span(self.unit, node),
        )

    def _keywords(self, call: ast.Call, allowed: set[str]) -> dict[str, ast.expr]:
        result: dict[str, ast.expr] = {}
        for keyword in call.keywords:
            if keyword.arg is None or keyword.arg not in allowed or keyword.arg in result:
                raise _ElaborationFailure(
                    "ACPY-V03-CALL-002",
                    f"invalid keyword for ac.{_call_name(call)}",
                    _span(self.unit, keyword),
                )
            result[keyword.arg] = keyword.value
        return result

    def _contract_values(
        self, call: ast.Call, *, allowed: set[str] | None = None
    ) -> dict[str, object]:
        keywords = self._keywords(
            call, allowed or {"depth", "latency", "rate", "domain"}
        )
        values = {name: self._static(node) for name, node in keywords.items()}
        for name in ("depth", "latency", "rate"):
            if name in values and type(values[name]) is not int:
                raise _ElaborationFailure(
                    "ACPY-V03-QUEUE-001",
                    f"Queue {name} must be a static integer",
                    _span(self.unit, keywords[name]),
                )
        if "domain" in values and not isinstance(values["domain"], str):
            raise _ElaborationFailure(
                "ACPY-V03-QUEUE-001",
                "Queue domain must be a static string",
                _span(self.unit, keywords["domain"]),
            )
        return values

    def _add_block(
        self,
        opcode: str,
        inputs: tuple[PortGroup, ...],
        results: tuple[PortGroup, ...],
        *,
        regions: tuple[str, ...] = (),
        parameters: tuple[SemanticParameter, ...] = (),
        source: SourceSpan | None = None,
    ) -> str:
        block = self.builder.add_block(
            opcode,
            self.current_scope,
            inputs,
            results,
            regions=regions,
            parameters=tuple(sorted(parameters, key=lambda item: item.name)),
            source=source,
            catalog=self.catalog,
        )
        for group in inputs:
            for queue in group.queues:
                self.use_scopes.setdefault(queue, []).append(self.current_scope)
        for group in results:
            for queue in group.queues:
                self.producer_scope[queue] = self.current_scope
        return block

    def _source(self, call: ast.Call) -> tuple[str, ...]:
        if len(call.args) != 1:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.source requires one payload type", _span(self.unit, call)
            )
        payload = self.types.resolve(call.args[0])
        values = self._contract_values(call)
        queue = self._queue(payload, call, **values)  # type: ignore[arg-type]
        self._add_block(
            "source",
            (),
            (PortGroup("output", "produce", (queue,)),),
            source=_span(self.unit, call),
        )
        return (queue,)

    def _compute(self, call: ast.Call) -> tuple[str, ...]:
        if (
            len(call.args) != 2
            or call.keywords
            or not isinstance(call.args[1], ast.Name)
        ):
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002",
                "ac.compute requires a Queue name and pure helper name",
                _span(self.unit, call),
            )
        input_queue = self._queue_ref(call.args[0])
        input_type = self.queue_types[input_queue]
        helper = self.helpers.get(call.args[1].id)
        if helper is None:
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
        self._add_block(
            "compute",
            (PortGroup("input", "consume", (input_queue,)),),
            (PortGroup("output", "produce", (output_queue,)),),
            regions=(region_id,),
            source=_span(self.unit, call),
        )
        return (output_queue,)

    def _transport(self, call: ast.Call) -> tuple[str, ...]:
        if len(call.args) != 1:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.queue requires one input Queue", _span(self.unit, call)
            )
        input_queue = self._queue_ref(call.args[0])
        values = self._contract_values(call)
        output = self._queue(self.queue_types[input_queue], call, **values)  # type: ignore[arg-type]
        self._add_block(
            "queue",
            (PortGroup("input", "consume", (input_queue,)),),
            (PortGroup("output", "produce", (output,)),),
            source=_span(self.unit, call),
        )
        return (output,)

    def _route(self, call: ast.Call) -> tuple[str, ...]:
        if len(call.args) != 1:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.route requires one input Queue", _span(self.unit, call)
            )
        keywords = self._keywords(call, {"by", "outputs"})
        if set(keywords) != {"by", "outputs"}:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.route requires by and outputs", _span(self.unit, call)
            )
        count = self._static(keywords["outputs"])
        if type(count) is not int or count <= 0:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "route outputs must be positive", _span(self.unit, keywords["outputs"])
            )
        input_queue = self._queue_ref(call.args[0])
        descriptor = self.types.descriptor(keywords["by"])
        if descriptor.root != self.queue_types[input_queue]:
            raise _ElaborationFailure(
                "ACPY-V03-TYPE-003",
                "route selector root must match its input payload",
                _span(self.unit, keywords["by"]),
            )
        outputs = tuple(self._queue_like(input_queue, call) for _ in range(count))
        self._add_block(
            "route",
            (PortGroup("input", "consume", (input_queue,)),),
            (PortGroup("outputs", "produce", outputs),),
            parameters=(SemanticParameter("by", descriptor),),
            source=_span(self.unit, call),
        )
        return outputs

    def _fork(self, call: ast.Call) -> tuple[str, ...]:
        if len(call.args) != 1:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.fork requires one input Queue", _span(self.unit, call)
            )
        keywords = self._keywords(call, {"outputs"})
        if set(keywords) != {"outputs"}:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.fork requires outputs", _span(self.unit, call)
            )
        count = self._static(keywords["outputs"])
        if type(count) is not int or count <= 0:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "fork outputs must be positive", _span(self.unit, keywords["outputs"])
            )
        input_queue = self._queue_ref(call.args[0])
        outputs = tuple(self._queue_like(input_queue, call) for _ in range(count))
        self._add_block(
            "fork",
            (PortGroup("input", "consume", (input_queue,)),),
            (PortGroup("outputs", "produce", outputs),),
            source=_span(self.unit, call),
        )
        return outputs

    def _merge(self, call: ast.Call) -> tuple[str, ...]:
        if len(call.args) != 1:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.merge requires one Queue collection", _span(self.unit, call)
            )
        keywords = self._keywords(call, {"policy"})
        if set(keywords) != {"policy"}:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "ac.merge requires policy", _span(self.unit, call)
            )
        policy = self._static(keywords["policy"])
        if policy not in {"round_robin", "priority", "oldest"}:
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "unsupported merge policy", _span(self.unit, keywords["policy"])
            )
        inputs = self._queue_collection(call.args[0])
        payloads = {self.queue_types[queue] for queue in inputs}
        if not inputs or len(payloads) != 1:
            raise _ElaborationFailure(
                "ACPY-V03-TYPE-003", "merge inputs require one payload type", _span(self.unit, call.args[0])
            )
        output = self._queue(next(iter(payloads)), call)
        self._add_block(
            "merge",
            (PortGroup("inputs", "consume", inputs),),
            (PortGroup("output", "produce", (output,)),),
            parameters=(SemanticParameter("policy", Policy(str(policy))),),
            source=_span(self.unit, call),
        )
        return (output,)

    def _observe(self, call: ast.Call) -> None:
        if (
            _call_name(call) != "observe"
            or len(call.args) != 1
            or call.keywords
        ):
            raise _ElaborationFailure(
                "ACPY-V03-CALL-002", "expression statement must be ac.observe(Queue)", _span(self.unit, call)
            )
        queue = self._queue_ref(call.args[0])
        self._add_block(
            "observe",
            (PortGroup("input", "observe", (queue,)),),
            (),
            source=_span(self.unit, call),
        )

    def _inside(self, candidate: str, scope: str) -> bool:
        cursor: str | None = candidate
        while cursor is not None:
            if cursor == scope:
                return True
            cursor = self.scope_parents[cursor]
        return False

    def _infer_scope_io(self) -> None:
        for scope in self.scope_parents:
            if scope == self.builder.root_scope:
                continue
            inputs: list[str] = []
            outputs: list[str] = []
            for queue in self.queue_order:
                producer = self.producer_scope.get(queue)
                uses = self.use_scopes.get(queue, [])
                if any(self._inside(use, scope) for use in uses) and (
                    producer is None or not self._inside(producer, scope)
                ):
                    inputs.append(queue)
                if producer is not None and self._inside(producer, scope) and any(
                    not self._inside(use, scope) for use in uses
                ):
                    outputs.append(queue)
            self.builder.set_scope_io(scope, tuple(inputs), tuple(outputs))


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
