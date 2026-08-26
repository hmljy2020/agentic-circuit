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
    FieldDescriptor,
    NamedType,
    PayloadDeclaration,
    PayloadType,
    Policy,
    QueueValue,
    ScalarType,
    SemanticProgram,
    Scope,
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
        f"!ac.queue_v03<{_payload_type(queue.constraint.payload)}, "
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
            f"{result} = ac.var.get {operands[0]} field {_string(field)} : "
            f"{_var_type(operand_types[0])} -> {_var_type(result_type)}"
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


def _field_attribute(field: FieldDescriptor) -> str:
    path = ", ".join(_string(component) for component in field.path)
    return (
        f"#ac.field<root = {_payload_type(field.root)}, path = [{path}], "
        f"leaf = {_payload_type(field.leaf)}>"
    )


def _policy_attribute(policy: Policy) -> str:
    if policy != Policy("round_robin"):
        raise _error("P4 emitter supports only parameter-free round_robin policy")
    return "#ac.policy<kind = round_robin>"


def _block_parameter(block: BlockInstance, name: str) -> object:
    parameters = {parameter.name: parameter.value for parameter in block.parameters}
    if set(parameters) != {name}:
        raise _error(f"{block.opcode} requires exactly parameter {name!r}")
    return parameters[name]


def _block_parameters(block: BlockInstance, expected: set[str]) -> dict[str, object]:
    parameters = {parameter.name: parameter.value for parameter in block.parameters}
    if set(parameters) != expected:
        raise _error(
            f"{block.opcode} parameters must be {tuple(sorted(expected))}"
        )
    return parameters


def _queue_operands(queues: tuple[str, ...]) -> str:
    return ", ".join(f"%{queue}" for queue in queues)


def _queue_types(queues: tuple[str, ...], queue_map: dict[str, QueueValue]) -> str:
    return ", ".join(_queue_type(queue_map[queue]) for queue in queues)


def _emit_block(
    block: BlockInstance,
    queue_map: dict[str, QueueValue],
    region_map: dict[str, VarRegion],
) -> list[str]:
    if block.opcode == "source":
        if block.inputs or block.regions or block.parameters:
            raise _error("source cannot have inputs, regions, or parameters")
        output = _require_one(
            _group_queues(block, "result", "output", "produce"), "source output"
        )
        return [
            f"    %{output} = ac.v03.source {_string(block.id)} : "
            f"{_queue_type(queue_map[output])}"
        ]

    if block.opcode == "compute":
        if block.parameters or len(block.regions) != 1:
            raise _error("compute requires one Var region and no parameters")
        input_queue = _require_one(
            _group_queues(block, "input", "input", "consume"), "compute input"
        )
        output_queue = _require_one(
            _group_queues(block, "result", "output", "produce"), "compute output"
        )
        region = region_map[block.regions[0]]
        lines = [f"    %{output_queue} = ac.compute %{input_queue} {{"]
        lines.extend(_emit_region(region))
        lines.append(
            f"    }} : ({_queue_type(queue_map[input_queue])}) -> "
            f"{_queue_type(queue_map[output_queue])}"
        )
        return lines

    if block.opcode == "observe":
        if block.results or block.regions or block.parameters:
            raise _error("observe requires one Queue and no results/regions/parameters")
        input_queue = _require_one(
            _group_queues(block, "input", "input", "observe"), "observe input"
        )
        return [
            f"    ac.v03.observe %{input_queue} as {_string(block.id)} fields [] : "
            f"{_queue_type(queue_map[input_queue])}"
        ]

    if block.opcode == "queue":
        if block.regions or block.parameters:
            raise _error("queue cannot have Var regions or static parameters")
        input_queue = _require_one(
            _group_queues(block, "input", "input", "consume"), "queue input"
        )
        output_queue = _require_one(
            _group_queues(block, "result", "output", "produce"), "queue output"
        )
        return [
            f"    %{output_queue} = ac.queue %{input_queue} : "
            f"{_queue_type(queue_map[input_queue])} -> "
            f"{_queue_type(queue_map[output_queue])}"
        ]

    if block.opcode == "route":
        if block.regions:
            raise _error("route cannot have Var regions")
        input_queue = _require_one(
            _group_queues(block, "input", "input", "consume"), "route input"
        )
        outputs = _group_queues(block, "result", "outputs", "produce")
        selector = _block_parameter(block, "by")
        if not isinstance(selector, FieldDescriptor):
            raise _error("route 'by' parameter must be a typed field")
        result_names = ", ".join(f"%{queue}" for queue in outputs)
        result_types = ", ".join(_queue_type(queue_map[queue]) for queue in outputs)
        return [
            f"    {result_names} = ac.v03.route %{input_queue} by "
            f"({_field_attribute(selector)}) : "
            f"({_queue_type(queue_map[input_queue])}) -> ({result_types})"
        ]

    if block.opcode == "fork":
        if block.regions or block.parameters:
            raise _error("fork cannot have Var regions or static parameters")
        input_queue = _require_one(
            _group_queues(block, "input", "input", "consume"), "fork input"
        )
        outputs = _group_queues(block, "result", "outputs", "produce")
        result_names = ", ".join(f"%{queue}" for queue in outputs)
        result_types = ", ".join(_queue_type(queue_map[queue]) for queue in outputs)
        return [
            f"    {result_names} = ac.v03.fork %{input_queue} : "
            f"({_queue_type(queue_map[input_queue])}) -> ({result_types})"
        ]

    if block.opcode == "merge":
        if block.regions:
            raise _error("merge cannot have Var regions")
        inputs = _group_queues(block, "input", "inputs", "consume")
        output = _require_one(
            _group_queues(block, "result", "output", "produce"), "merge output"
        )
        policy = _block_parameter(block, "policy")
        if not isinstance(policy, Policy):
            raise _error("merge policy parameter must be typed")
        operands = ", ".join(f"%{queue}" for queue in inputs)
        input_types = ", ".join(_queue_type(queue_map[queue]) for queue in inputs)
        return [
            f"    %{output} = ac.v03.merge ({operands}) policy "
            f"({_policy_attribute(policy)}) : ({input_types}) -> "
            f"{_queue_type(queue_map[output])}"
        ]

    if block.opcode == "issue":
        if block.regions:
            raise _error("issue cannot have Var regions")
        enqueue = _group_queues(block, "input", "enqueue", "consume")
        wakeup = _group_queues(block, "input", "wakeup", "consume")
        recheck_response = _group_queues(
            block, "input", "recheck_response", "consume"
        )
        issued = _group_queues(block, "result", "issued", "produce")
        recheck_request = _group_queues(
            block, "result", "recheck_request", "produce"
        )
        parameters = {
            parameter.name: parameter.value for parameter in block.parameters
        }
        required_parameters = {"entries", "policy", "width"}
        descriptor_parameters = {
            "dependency_key",
            "dependency_ready",
            "wakeup_key",
        }
        if not required_parameters.issubset(parameters) or not set(
            parameters
        ).issubset(required_parameters | descriptor_parameters):
            raise _error("issue parameters do not match its frozen contract")
        present_descriptors = descriptor_parameters.intersection(parameters)
        if present_descriptors and present_descriptors != descriptor_parameters:
            raise _error("issue dependency descriptors must be present together")
        entries = parameters["entries"]
        width = parameters["width"]
        policy = parameters["policy"]
        if type(entries) is not int or type(width) is not int or not isinstance(
            policy, str
        ):
            raise _error("issue entries/width/policy have invalid static types")
        result_names = _queue_operands((*issued, *recheck_request))
        wakeup_syntax = ""
        if wakeup:
            wakeup_syntax = (
                f" wakeup ({_queue_operands(wakeup)} : "
                f"{_queue_types(wakeup, queue_map)})"
            )
        recheck_response_syntax = ""
        if recheck_response:
            recheck_response_syntax = (
                f" recheck_response ({_queue_operands(recheck_response)} : "
                f"{_queue_types(recheck_response, queue_map)})"
            )
        recheck_request_syntax = ""
        if recheck_request:
            recheck_request_syntax = (
                f" recheck_request ({_queue_types(recheck_request, queue_map)})"
            )
        descriptor_syntax = ""
        if present_descriptors:
            descriptors = []
            for name in sorted(descriptor_parameters):
                descriptor = parameters[name]
                if not isinstance(descriptor, FieldDescriptor):
                    raise _error(f"issue {name} must be a typed field")
                descriptors.append(f"{name} = {_field_attribute(descriptor)}")
            descriptor_syntax = " {" + ", ".join(descriptors) + "}"
        return [
            f"    {result_names} = ac.v03.issue "
            f"enqueue ({_queue_operands(enqueue)} : "
            f"{_queue_types(enqueue, queue_map)})"
            f"{wakeup_syntax}{recheck_response_syntax} "
            f"entries {entries} width {width} policy {_string(policy)} -> "
            f"issued ({_queue_types(issued, queue_map)})"
            f"{recheck_request_syntax}{descriptor_syntax}"
        ]

    if block.opcode == "engine":
        if block.regions:
            raise _error("engine cannot have Var regions")
        issued = _group_queues(block, "input", "issued", "consume")
        completed = _group_queues(block, "result", "completed", "produce")
        parameters = _block_parameters(
            block, {"inflight", "initiation_interval", "kind", "latency_by"}
        )
        inflight = parameters["inflight"]
        initiation_interval = parameters["initiation_interval"]
        kind = parameters["kind"]
        latency_by = parameters["latency_by"]
        if (
            type(inflight) is not int
            or type(initiation_interval) is not int
            or not isinstance(kind, str)
            or not isinstance(latency_by, FieldDescriptor)
        ):
            raise _error("engine static parameters have invalid types")
        return [
            f"    {_queue_operands(completed)} = ac.v03.engine "
            f"({_queue_operands(issued)}) latency_by "
            f"({_field_attribute(latency_by)}) inflight {inflight} "
            f"initiation_interval {initiation_interval} kind {_string(kind)} : "
            f"({_queue_types(issued, queue_map)}) -> "
            f"({_queue_types(completed, queue_map)})"
        ]

    if block.opcode == "reorder":
        if block.regions:
            raise _error("reorder cannot have Var regions")
        completed = _group_queues(block, "input", "completed", "consume")
        retired = _require_one(
            _group_queues(block, "result", "retired", "produce"),
            "reorder retired",
        )
        parameters = _block_parameters(
            block, {"by", "entries", "policy", "width"}
        )
        identity = parameters["by"]
        entries = parameters["entries"]
        policy = parameters["policy"]
        width = parameters["width"]
        if (
            not isinstance(identity, FieldDescriptor)
            or type(entries) is not int
            or type(width) is not int
            or not isinstance(policy, str)
        ):
            raise _error("reorder static parameters have invalid types")
        return [
            f"    %{retired} = ac.v03.reorder completed ({_queue_operands(completed)}) "
            f"by ({_field_attribute(identity)}) entries {entries} "
            f"width {width} policy {_string(policy)} : "
            f"({_queue_types(completed, queue_map)}) -> "
            f"{_queue_type(queue_map[retired])}"
        ]

    if block.opcode == "sink":
        if block.results or block.regions or block.parameters:
            raise _error("sink requires one Queue and no results/regions/parameters")
        input_queue = _require_one(
            _group_queues(block, "input", "input", "consume"), "sink input"
        )
        return [
            f"    ac.v03.sink %{input_queue} : {_queue_type(queue_map[input_queue])}"
        ]

    raise _error(f"P4 emitter does not support primitive {block.opcode!r}")


def _scope_paths(scopes: dict[str, Scope], root: Scope) -> dict[str, tuple[str, ...]]:
    paths = {root.id: (root.name,)}
    pending = [root]
    while pending:
        parent = pending.pop()
        for child_id in parent.children:
            child = scopes[child_id]
            paths[child_id] = (*paths[parent.id], child.name)
            pending.append(child)
    if len(paths) != len(scopes):
        raise _error("scope tree is disconnected")
    return paths


def _scope_symbol(path: tuple[str, ...]) -> str:
    return _symbol("__".join(path))


def _function_results(types: tuple[str, ...]) -> str:
    if not types:
        return ""
    if len(types) == 1:
        return f" -> {types[0]}"
    return " -> (" + ", ".join(types) + ")"


def _emit_instance(
    child: Scope,
    symbol: str,
    queue_map: dict[str, QueueValue],
) -> str:
    inputs = tuple(_queue_type(queue_map[queue]) for queue in child.inputs)
    outputs = tuple(_queue_type(queue_map[queue]) for queue in child.outputs)
    result = ""
    if child.outputs:
        result = ", ".join(f"%{queue}" for queue in child.outputs) + " = "
    operands = ", ".join(f"%{queue}" for queue in child.inputs)
    return (
        f"    {result}ac.instance @{_symbol(child.name + '_' + child.id)} "
        f"of @{symbol}({operands}) static {{}} id {_string(child.id)} "
        f"path {_string(child.name)} : ({', '.join(inputs)}) -> "
        f"({', '.join(outputs)})"
    )


def _source_order(source: SourceSpan | None, identity: str) -> tuple[object, ...]:
    numeric_identity = int(identity[1:]) if identity[1:].isdigit() else identity
    if source is None:
        return (1, 0, 0, numeric_identity)
    return (0, source.start_line, source.start_column, numeric_identity)


def lower_semantic_v03(program: SemanticProgram) -> AcirV03Artifact:
    """Emit the frozen P3-P5 ACIR profile from a verified semantic program."""

    program.verify(require_frozen_queues=True)
    queue_map = {queue.id: queue for queue in program.queues}
    block_map = {block.id: block for block in program.blocks}
    region_map = {region.id: region for region in program.var_regions}
    scope_map = {scope.id: scope for scope in program.scopes}
    root_scope = scope_map[program.root_scope]
    if root_scope.parent is not None:
        raise _error("root scope cannot have a parent")
    if root_scope.inputs or root_scope.outputs:
        raise _error("root scope cannot have module Queue ports")
    paths = _scope_paths(scope_map, root_scope)
    symbols = {scope.id: _scope_symbol(paths[scope.id]) for scope in program.scopes}

    system = _symbol(f"{program.system}_system")
    root = symbols[root_scope.id]
    lines = ['builtin.module attributes {ac.contract_epoch = "0.3"} {']
    lines.extend(_emit_declarations(program.declarations))
    lines.append(
        f"  ac.system @{system} root @{root} as {_string(root)} tick 0 \"cycle\" "
        "seed {kind = \"fixed\", value = 0 : i64} instrumentation [] "
        "results {id = \"default\", format = \"json\"} selected true"
    )

    for scope in program.scopes:
        input_types = tuple(_queue_type(queue_map[queue]) for queue in scope.inputs)
        output_types = tuple(_queue_type(queue_map[queue]) for queue in scope.outputs)
        lines.append(
            f"  ac.module @{symbols[scope.id]}({', '.join(input_types)})"
            f"{_function_results(output_types)} parameters {{}} graph {{"
        )
        if scope.inputs:
            arguments = ", ".join(
                f"%{queue} : {_queue_type(queue_map[queue])}"
                for queue in scope.inputs
            )
            lines.append(f"  ^bb0({arguments}):")

        items: list[tuple[tuple[object, ...], str, str]] = []
        for block_id in scope.blocks:
            block = block_map[block_id]
            items.append((_source_order(block.source, block.id), "block", block_id))
        for child_id in scope.children:
            child = scope_map[child_id]
            items.append((_source_order(child.source, child.id), "scope", child_id))
        for _, kind, identity in sorted(items):
            if kind == "block":
                lines.extend(_emit_block(block_map[identity], queue_map, region_map))
            else:
                child = scope_map[identity]
                lines.append(_emit_instance(child, symbols[child.id], queue_map))

        if scope.outputs:
            operands = ", ".join(f"%{queue}" for queue in scope.outputs)
            types = ", ".join(_queue_type(queue_map[queue]) for queue in scope.outputs)
            lines.append(f"    ac.return {operands} : {types}")
        else:
            lines.append("    ac.return")
        lines.append("  }")

    lines.append("}")
    text = "\n".join(lines) + "\n"
    return AcirV03Artifact(
        text,
        sha256_bytes(text.encode("utf-8")),
        _collect_source_map(program),
    )
