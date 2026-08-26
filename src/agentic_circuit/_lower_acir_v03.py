"""Deterministic lowering from the ACPy v0.3 semantic graph to ACIR.

The emitter intentionally consumes only :class:`SemanticProgram`.  Python AST
capture and ACIR spelling therefore remain separate compiler stages.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ._canonical_json import sha256_bytes
from ._diagnostics import SourceSpan
from ._semantic_v03 import (
    ArrayType,
    BlockInstance,
    NamedType,
    PayloadDeclaration,
    PayloadType,
    QueueValue,
    ScalarType,
    SemanticProgram,
    VarOperation,
    VarRegion,
)


_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_P3_SCALARS = {
    "i1": 1,
    "u2": 2,
    "u8": 8,
    "u16": 16,
    "u32": 32,
    "u64": 64,
}


class AcirV03LoweringError(ValueError):
    """A deterministic semantic-to-ACIR contract failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class AcirV03Artifact:
    text: str
    sha256: str
    source_map: tuple[tuple[str, SourceSpan], ...]


def _error(message: str) -> AcirV03LoweringError:
    return AcirV03LoweringError("ACPY-V03-ACIR-001", message)


def _symbol(value: str) -> str:
    if not _SYMBOL.fullmatch(value):
        raise _error(f"invalid ACIR symbol {value!r}")
    return value


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _payload_type(payload: PayloadType) -> str:
    if isinstance(payload, ScalarType):
        expected = _P3_SCALARS.get(payload.name)
        if expected != payload.width:
            raise _error(
                f"unsupported or inconsistent P3 scalar {payload.name!r}/{payload.width}"
            )
        return f"i{payload.width}"
    if isinstance(payload, NamedType):
        if payload.kind != "struct":
            raise _error(f"P3 cannot emit named {payload.kind} payloads")
        return f"!ac.struct<@types::@{_symbol(payload.name)}>"
    if isinstance(payload, ArrayType):
        return f"!ac.vector<{payload.extent} x {_payload_type(payload.element)}>"
    raise _error(f"unsupported payload type {type(payload).__name__}")


def _var_type(payload: PayloadType) -> str:
    return f"!ac.var<{_payload_type(payload)}>"


def _queue_type(queue: QueueValue) -> str:
    contract = queue.constraint.freeze()
    domain = _symbol(contract.domain)
    return (
        f"!ac.queue<{_payload_type(queue.constraint.payload)}, "
        f"#ac.queue_contract<depth = {contract.depth}, "
        f"latency = {contract.latency}, rate = {contract.rate}, "
        f"domain = @{domain}, ordering = {contract.ordering}>>"
    )


def _scalar_layout(payload: PayloadType) -> tuple[int, int]:
    if not isinstance(payload, ScalarType):
        raise _error("P3 struct layout currently requires scalar fields")
    _payload_type(payload)
    size = (payload.width + 7) // 8
    return size, size


def _struct_layout(declaration: PayloadDeclaration) -> tuple[int, int]:
    if declaration.kind != "struct":
        raise _error(f"P3 cannot emit {declaration.kind} declarations")
    offset = 0
    alignment = 1
    for field in declaration.fields:
        size, field_alignment = _scalar_layout(field.type)
        alignment = max(alignment, field_alignment)
        offset = ((offset + field_alignment - 1) // field_alignment) * field_alignment
        offset += size
    size = ((offset + alignment - 1) // alignment) * alignment
    return max(size, 1), alignment


def _emit_declarations(declarations: tuple[PayloadDeclaration, ...]) -> list[str]:
    if not declarations:
        return []
    lines = ["  ac.type_scope @types {"]
    for declaration in declarations:
        if declaration.kind != "struct":
            raise _error(f"P3 cannot emit {declaration.kind} declarations")
        fields = ", ".join(
            "{name = " + _string(field.name) + ", type = " + _payload_type(field.type) + "}"
            for field in declaration.fields
        )
        lines.append(
            f"    ac.struct @{_symbol(declaration.name)} fields [{fields}]"
        )
    lines.append("  } {dlti.dl_spec = #dlti.dl_spec<")
    for index, declaration in enumerate(declarations):
        size, alignment = _struct_layout(declaration)
        comma = "," if index + 1 != len(declarations) else ""
        lines.append(
            f"    !ac.struct<@types::@{_symbol(declaration.name)}> = "
            f"{{abi_alignment = {alignment} : i64, endianness = \"little\", "
            f"preferred_alignment = {alignment} : i64, size = {size} : i64}}{comma}"
        )
    lines.append("  >}")
    return lines


def _parameters(operation: VarOperation) -> dict[str, object]:
    return {parameter.name: parameter.value for parameter in operation.parameters}


def _require_parameters(
    operation: VarOperation, expected: set[str]
) -> dict[str, object]:
    parameters = _parameters(operation)
    if set(parameters) != expected:
        raise _error(
            f"{operation.opcode} parameters must be {tuple(sorted(expected))}"
        )
    return parameters


def _single_result(operation: VarOperation) -> tuple[str, PayloadType]:
    if len(operation.results) != 1:
        raise _error(f"{operation.opcode} requires one result")
    result = operation.results[0]
    return result.id, result.type


def _operand_types(
    operation: VarOperation, values: dict[str, PayloadType]
) -> tuple[PayloadType, ...]:
    try:
        return tuple(values[operand] for operand in operation.operands)
    except KeyError as error:
        raise _error(f"unresolved Var operand {error.args[0]!r}") from error


def _emit_var_operation(
    operation: VarOperation, values: dict[str, PayloadType]
) -> str:
    operand_types = _operand_types(operation, values)
    operands = tuple(f"%{operand}" for operand in operation.operands)

    if operation.opcode == "yield":
        _require_parameters(operation, set())
        if len(operands) != 1 or operation.results:
            raise _error("yield requires one operand and no results")
        return f"ac.var.yield {operands[0]} : {_var_type(operand_types[0])}"

    result_id, result_type = _single_result(operation)
    result = f"%{result_id}"
    if operation.opcode == "constant":
        parameters = _require_parameters(operation, {"value"})
        if operands or not isinstance(result_type, ScalarType):
            raise _error("constant requires no operands and one scalar result")
        value = parameters["value"]
        if type(value) is bool:
            attribute = "true" if value else "false"
        elif type(value) is int:
            attribute = f"{value} : {_payload_type(result_type)}"
        else:
            raise _error("constant value must be bool or integer")
        return f"{result} = ac.var.constant {attribute} as {_var_type(result_type)}"

    if operation.opcode == "get":
        parameters = _require_parameters(operation, {"field"})
        field = parameters["field"]
        if len(operands) != 1 or not isinstance(field, str):
            raise _error("get requires one operand and a string field")
        return (
            f"{result} = ac.var.get {operands[0]} [{_string(field)}] : "
            f"({_var_type(operand_types[0])}) -> {_var_type(result_type)}"
        )

    if operation.opcode == "binary":
        parameters = _require_parameters(operation, {"operator"})
        operator = parameters["operator"]
        if len(operands) != 2 or not isinstance(operator, str):
            raise _error("binary requires two operands and a string operator")
        return (
            f"{result} = ac.var.binary {_string(operator)} "
            f"{operands[0]}, {operands[1]} : "
            f"({_var_type(operand_types[0])}) -> {_var_type(result_type)} "
            f"rhs {_var_type(operand_types[1])}"
        )

    if operation.opcode == "struct":
        parameters = _require_parameters(operation, {"fields", "type"})
        fields = parameters["fields"]
        declared_type = parameters["type"]
        if not isinstance(fields, str) or declared_type != result_type:
            raise _error("struct fields/type parameters do not match its result")
        field_names = () if not fields else tuple(fields.split(","))
        if len(field_names) != len(operands):
            raise _error("struct field and operand arity differ")
        field_text = ", ".join(_string(field) for field in field_names)
        operand_text = ", ".join(operands)
        type_text = ", ".join(_var_type(item) for item in operand_types)
        return (
            f"{result} = ac.var.struct [{field_text}]({operand_text}) : "
            f"({type_text}) -> {_var_type(result_type)}"
        )

    raise _error(f"P3 emitter does not support ac.var.{operation.opcode}")


def _emit_region(region: VarRegion) -> list[str]:
    region.verify()
    if len(region.inputs) != 1:
        raise _error("P3 compute region requires one input")
    values = {value.id: value.type for value in region.inputs}
    argument = region.inputs[0]
    lines = [f"    ^bb0(%{argument.id}: {_var_type(argument.type)}):"]
    for operation in region.operations:
        lines.append("      " + _emit_var_operation(operation, values))
        for result in operation.results:
            values[result.id] = result.type
    return lines


def _group_queues(
    block: BlockInstance, kind: str, name: str, effect: str
) -> tuple[str, ...]:
    groups = block.inputs if kind == "input" else block.results
    matching = tuple(group for group in groups if group.name == name)
    if len(matching) != 1 or matching[0].effect != effect:
        raise _error(f"{block.opcode} requires {effect} {kind} group {name!r}")
    return matching[0].queues


def _require_one(values: tuple[str, ...], context: str) -> str:
    if len(values) != 1:
        raise _error(f"{context} requires exactly one Queue")
    return values[0]


def _collect_source_map(program: SemanticProgram) -> tuple[tuple[str, SourceSpan], ...]:
    entries: list[tuple[str, SourceSpan]] = []
    for block in program.blocks:
        if block.source is not None:
            entries.append((block.id, block.source))
    for region in program.var_regions:
        for operation in region.operations:
            if operation.source is not None:
                entries.append((f"{region.id}/{operation.id}", operation.source))
    return tuple(entries)


def lower_semantic_v03(program: SemanticProgram) -> AcirV03Artifact:
    """Emit the frozen P3 ACIR profile from a verified semantic program."""

    program.verify(require_frozen_queues=True)
    queue_map = {queue.id: queue for queue in program.queues}
    block_map = {block.id: block for block in program.blocks}
    region_map = {region.id: region for region in program.var_regions}
    scope_map = {scope.id: scope for scope in program.scopes}
    root_scope = scope_map[program.root_scope]
    if root_scope.parent is not None or root_scope.children:
        raise _error("P3 emitter requires one root scope without children")
    if root_scope.blocks != tuple(block.id for block in program.blocks):
        raise _error("P3 root scope must own every block in semantic order")
    if root_scope.inputs or root_scope.outputs:
        raise _error("P3 root scope cannot have module Queue ports")

    system = _symbol(f"{program.system}_system")
    root = _symbol(root_scope.name)
    lines = ['builtin.module attributes {ac.contract_epoch = "0.3"} {']
    lines.extend(_emit_declarations(program.declarations))
    lines.append(
        f"  ac.system @{system} root @{root} as {_string(root)} tick 0 \"cycle\" "
        "seed {kind = \"fixed\", value = 0 : i64} instrumentation [] "
        "results {id = \"default\", format = \"json\"} selected true"
    )
    lines.append(f"  ac.module @{root}() parameters {{}} graph {{")

    produced: set[str] = set()
    for block_id in root_scope.blocks:
        block = block_map[block_id]
        if block.parameters:
            raise _error(f"P3 {block.opcode} cannot carry static parameters")
        if block.opcode == "source":
            if block.inputs or block.regions:
                raise _error("source cannot have inputs or Var regions")
            output = _require_one(
                _group_queues(block, "result", "output", "produce"), "source output"
            )
            lines.append(
                f"    %{output} = ac.source {_string(block.id)} : "
                f"{_queue_type(queue_map[output])}"
            )
            produced.add(output)
            continue
        if block.opcode == "compute":
            input_queue = _require_one(
                _group_queues(block, "input", "input", "consume"), "compute input"
            )
            output_queue = _require_one(
                _group_queues(block, "result", "output", "produce"), "compute output"
            )
            if input_queue not in produced:
                raise _error("P3 compute input must be produced earlier")
            if len(block.regions) != 1:
                raise _error("compute requires one Var region")
            region = region_map[block.regions[0]]
            lines.append(f"    %{output_queue} = ac.compute %{input_queue} {{")
            lines.extend(_emit_region(region))
            lines.append(
                f"    }} : ({_queue_type(queue_map[input_queue])}) -> "
                f"{_queue_type(queue_map[output_queue])}"
            )
            produced.add(output_queue)
            continue
        if block.opcode == "observe":
            input_queue = _require_one(
                _group_queues(block, "input", "input", "observe"), "observe input"
            )
            if block.results or block.regions or input_queue not in produced:
                raise _error("observe requires one previously produced Queue")
            lines.append(
                f"    ac.observe %{input_queue} as {_string(block.id)} fields [] : "
                f"{_queue_type(queue_map[input_queue])}"
            )
            continue
        raise _error(f"P3 emitter does not support primitive {block.opcode!r}")

    lines.append("    ac.return")
    lines.append("  }")
    lines.append("}")
    text = "\n".join(lines) + "\n"
    return AcirV03Artifact(
        text,
        sha256_bytes(text.encode("utf-8")),
        _collect_source_map(program),
    )
