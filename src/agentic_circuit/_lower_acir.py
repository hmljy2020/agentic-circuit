"""Deterministic ACPy construction and canonical ACIR text emission."""

from __future__ import annotations

import json
import re
import ast
from dataclasses import dataclass

from ._acpy import (
    AcpyDocument,
    EntityAllocator,
    Property,
    SchemaRef,
    SourceFile,
)
from ._canonical_json import sha256_bytes, utf16_sort_key
from ._diagnostics import SourceSpan
from ._frontend import CapturedProgram
from ._normalize import NormalizedProgram
from ._process import ProcessProgram
from ._resolve import ValueVersion
from ._static_eval import StaticValue


_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _value_annotation_type(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return {
            "bool": "i1",
            "int": "i32",
            "float": "f64",
        }.get(node.id, f"!ac.packet<@types::@{node.id}>")
    raise ValueError("ACPY-TYPE-FLOW: unsupported Flow payload annotation")


def _flow_spec(type_key: str) -> tuple[str, str] | None:
    try:
        expression = ast.parse(type_key, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expression, ast.Subscript) or not isinstance(
        expression.value, ast.Name
    ) or expression.value.id != "Flow":
        return None
    elements = (
        expression.slice.elts
        if isinstance(expression.slice, ast.Tuple)
        else [expression.slice]
    )
    if len(elements) != 2 or not isinstance(elements[1], ast.Name):
        raise ValueError("ACPY-TYPE-FLOW: Flow requires payload and protocol types")
    return _value_annotation_type(elements[0]), _snake_case(elements[1].id)


def _bundle_spec(type_key: str) -> tuple[str, str, int | None] | None:
    try:
        expression = ast.parse(type_key, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expression, ast.Subscript) or not isinstance(expression.value, ast.Name):
        return None
    if expression.value.id != "FlowBundle":
        return None
    elements = expression.slice.elts if isinstance(expression.slice, ast.Tuple) else [expression.slice]
    if len(elements) not in (2, 3) or not isinstance(elements[1], ast.Name):
        raise ValueError("ACPY-TYPE-FLOW: FlowBundle requires payload and protocol types")
    width: int | None = None
    if len(elements) == 3:
        if not isinstance(elements[2], ast.Constant) or type(elements[2].value) is not int:
            raise ValueError("ACPY-TYPE-FLOW: FlowBundle shape must be static")
        width = elements[2].value
    return _value_annotation_type(elements[0]), _snake_case(elements[1].id), width


def annotation_type_to_acir(type_key: str) -> str:
    """Lower one captured public annotation to its canonical ACIR spelling."""

    flow = _flow_spec(type_key)
    if flow is not None:
        payload, protocol = flow
        return f"!ac.flow<{payload}, @{protocol}>"
    bundle = _bundle_spec(type_key)
    if bundle is not None:
        payload, protocol, _ = bundle
        return f"!ac.flow<{payload}, @{protocol}>"
    return {"bool": "i1", "RuntimeBool": "i1", "int": "i32"}.get(
        type_key, type_key
    )


@dataclass(frozen=True, slots=True)
class AcirArtifact:
    text: str
    sha256: str
    source_map: tuple[tuple[str, SourceSpan], ...]


def _properties(**values: StaticValue) -> tuple[Property, ...]:
    return tuple(
        Property(name, value)
        for name, value in sorted(values.items(), key=lambda item: utf16_sort_key(item[0]))
    )


def build_verified_acpy(
    captured: CapturedProgram,
    program: NormalizedProgram,
    processes: tuple[ProcessProgram, ...] = (),
) -> AcpyDocument:
    """Build the closed semantic document in dense semantic order."""

    selected = captured.selected_system
    if selected is None:
        raise ValueError("ACPY-VERIFY-001: a selected system is required")
    sites = {site.qualified_name: site for site in captured.source.definitions}
    system_site = sites[selected.qualified_name]
    module_site = sites.get(program.definition)
    if module_site is None:
        raise ValueError("ACPY-VERIFY-001: root module source is missing")

    allocator = EntityAllocator()
    system = allocator.allocate(
        kind="system",
        scope=selected.qualified_name,
        source=system_site.span,
        properties=_properties(root=program.definition),
    )
    module = allocator.allocate(
        kind="module",
        scope=program.definition,
        source=module_site.span,
        parent=system.id,
        properties=_properties(name=program.definition),
    )
    values: dict[str, str] = {}
    for argument in program.arguments:
        entity = allocator.allocate(
            kind="arg",
            scope=program.definition,
            source=module_site.span,
            parent=module.id,
            type=argument.type_key,
            properties=_properties(name=argument.source_name),
        )
        values[argument.name] = entity.id
    for capture in program.captures:
        entity = allocator.allocate(
            kind="capture",
            scope=program.definition,
            source=module_site.span,
            parent=module.id,
            type=capture.type_key,
            properties=_properties(name=capture.source_name),
        )
        values[capture.name] = entity.id

    for call in program.calls:
        uses = tuple(values[binding.value.name] for binding in call.inputs)
        call_properties: dict[str, StaticValue] = {
            "instance_name": call.instance_name,
        }
        if call.specialization is not None:
            call_properties["specialization"] = call.specialization
            call_properties.update(dict(call.static_arguments))
        call_entity = allocator.allocate(
            kind="call",
            scope=program.definition,
            source=call.source,
            parent=module.id,
            uses=uses,
            schema_ref=SchemaRef(call.schema.identity, call.schema.fingerprint),
            properties=_properties(**call_properties),
        )
        for binding in call.results:
            result_properties: dict[str, StaticValue] = {
                "name": (
                    binding.value.source_name
                    if call.schema.generator is not None
                    else binding.value.name
                ),
            }
            if binding.port_index is not None:
                result_properties["port_index"] = binding.port_index
                result_properties["shape"] = binding.shape
                if call.schema.identity in {"ac.std.RingNoC", "ac.std.MeshNoC"}:
                    result_properties["node_id"] = binding.port_index
            result = allocator.allocate(
                kind="result",
                scope=program.definition,
                source=call.source,
                parent=call_entity.id,
                type=binding.value.type_key,
                uses=(call_entity.id,),
                properties=_properties(**result_properties),
            )
            values[binding.value.name] = result.id

    process_definitions = {
        definition.qualified_name: definition
        for definition in captured.definitions
        if definition.kind == "process"
    }
    for process in processes:
        definition = next(
            (
                item
                for item in process_definitions.values()
                if item.__name__ == process.name
            ),
            None,
        )
        source = sites[definition.qualified_name].span if definition is not None else None
        allocator.allocate(
            kind="process",
            scope=program.definition,
            source=source,
            parent=module.id,
            properties=_properties(name=process.name),
        )

    allocator.allocate(
        kind="return",
        scope=program.definition,
        source=module_site.span,
        parent=module.id,
        uses=tuple(values[value.name] for value in program.returns),
    )
    document = AcpyDocument(
        entry=system.id,
        sources=(SourceFile(captured.source.path, captured.source.sha256),),
        entities=allocator.freeze(),
    )
    errors = document.verify()
    if errors:
        raise ValueError(
            "ACPY-VERIFY-001: " + "; ".join(error.message for error in errors)
        )
    return document


def _symbol(value: str) -> str:
    candidate = value.rsplit(".", 1)[-1]
    if not _SYMBOL.fullmatch(candidate):
        raise ValueError(f"ACPY-VERIFY-001: invalid ACIR symbol {value!r}")
    return candidate


def _ssa(value: ValueVersion) -> str:
    candidate = f"{value.source_name}_{value.version}"
    return re.sub(r"[^A-Za-z0-9_]", "_", candidate)


def _static_attribute(value: StaticValue) -> str:
    if value is None:
        return "unit"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    raise ValueError(
        f"ACPY-VERIFY-001: unsupported ACIR static value {type(value).__name__}"
    )


def _static_arguments(values: tuple[tuple[str, StaticValue], ...]) -> str:
    return ", ".join(
        f"{name} = {_static_attribute(value)}" for name, value in values
    )


def _argument_types(program: NormalizedProgram) -> dict[str, str]:
    inferred: dict[str, str] = {
        argument.name: annotation_type_to_acir(argument.type_key)
        for argument in program.arguments
    }
    for call in program.calls:
        if call.schema.generator is not None:
            continue
        for port, binding in zip(call.schema.ports, call.inputs, strict=True):
            inferred.setdefault(binding.value.name, annotation_type_to_acir(port.acir_type))
    return inferred


def _crossbar_parameters(call: object) -> dict[str, StaticValue]:
    return dict(call.static_arguments)  # type: ignore[attr-defined]


def _crossbar_symbol(call: object) -> str:
    parameters = _crossbar_parameters(call)
    digest = str(call.specialization).removeprefix("sha256:")[:12]  # type: ignore[attr-defined]
    return (
        f"Crossbar__{parameters['input_ports']}x{parameters['output_ports']}"
        f"_v{parameters['virtual_channels']}__{digest}"
    )


def _crossbar_declaration(call: object) -> list[str]:
    parameters = _crossbar_parameters(call)
    inputs = int(parameters["input_ports"])
    outputs = int(parameters["output_ports"])
    vcs = int(parameters["virtual_channels"])
    ingress_depth = int(parameters["ingress_depth"])
    egress_depth = int(parameters["egress_depth"])
    route_offset = int(parameters["route_offset"])
    route_width = int(parameters["route_width"])
    symbol = _crossbar_symbol(call)
    flow_type = "!ac.flow<i32, @ready_valid>"
    arguments = ", ".join(
        f"%input{i}_vc{vc} : {flow_type}" for i in range(inputs) for vc in range(vcs)
    )
    result_types = ", ".join(flow_type for _ in range(outputs * vcs))
    signature = flow_type if outputs * vcs == 1 else f"({result_types})"
    static_text = _static_arguments(call.static_arguments)  # type: ignore[attr-defined]
    lines = [
        f"  ac.module @{symbol}({arguments}) -> {signature} parameters {{{static_text}}} graph {{"
    ]
    for i in range(inputs):
        for vc in range(vcs):
            queue = f"in{i}_vc{vc}"
            lines.append(
                f"    ac.queue @{queue} payload i32 entries {ingress_depth} ordering \"fifo\" "
                f"protocol @ready_valid ownership \"exclusive\" id \"{queue}\" path \"{queue}\""
            )
    returned: list[str] = []
    for output in range(outputs):
        for vc in range(vcs):
            queue = f"out{output}_vc{vc}"
            value = f"%output{output}_vc{vc}"
            lines.append(
                f"    ac.queue @{queue} payload i32 entries {egress_depth} ordering \"fifo\" "
                f"protocol @ready_valid ownership \"exclusive\" id \"{queue}\" path \"{queue}\""
            )
    for i in range(inputs):
        for vc in range(vcs):
            queue = f"in{i}_vc{vc}"
            lines.append(
                f"    ac.flow.import %input{i}_vc{vc} to @{queue} : {flow_type}"
            )
    for output in range(outputs):
        for vc in range(vcs):
            queue = f"out{output}_vc{vc}"
            value = f"%output{output}_vc{vc}"
            lines.append(f"    {value} = ac.flow.export @{queue} : {flow_type}")
            returned.append(value)
    for i in range(inputs):
        lines.append(
            f"    ac.resource @pin{i} capacity 1 issue_width 1 ii 1 "
            "latency {kind = \"fixed\", ticks = 1 : i64} "
            "lifecycle {reservation = \"propose_commit\", release = \"balanced\", cancellation = \"explicit\"} "
            f"ownership \"exclusive\" classes [] id \"pin{i}\" path \"pin{i}\""
        )
    for output in range(outputs):
        lines.append(
            f"    ac.resource @pout{output} capacity 1 issue_width 1 ii 1 "
            "latency {kind = \"fixed\", ticks = 1 : i64} "
            "lifecycle {reservation = \"propose_commit\", release = \"balanced\", cancellation = \"explicit\"} "
            f"ownership \"exclusive\" classes [] id \"pout{output}\" path \"pout{output}\""
        )
    lines.append("    ac.process @scheduler kind \"control\" {")
    for i in range(inputs):
        for vc in range(vcs):
            lines.append(f"      %head_i{i}_v{vc}, %valid_i{i}_v{vc} = ac.peek @in{i}_vc{vc} : i32")
    for output in range(outputs):
        for vc in range(vcs):
            lines.append(f"      %space_o{output}_v{vc} = ac.space @out{output}_vc{vc}")
    lines.append("      %zero = arith.constant 0 : i32")
    lines.append(f"      %output_count = arith.constant {outputs} : i32")
    lines.append(f"      %route_mask = arith.constant {(1 << route_width) - 1} : i32")
    if route_offset:
        lines.append(f"      %route_shift = arith.constant {route_offset} : i32")
    for i in range(inputs):
        for vc in range(vcs):
            source = f"%head_i{i}_v{vc}"
            if route_offset:
                shifted = f"%shifted_i{i}_v{vc}"
                lines.append(f"      {shifted} = arith.shrui {source}, %route_shift : i32")
                source = shifted
            lines.append(f"      %dst_i{i}_v{vc} = arith.andi {source}, %route_mask : i32")
            lines.append(
                f"      %invalid_route_i{i}_v{vc} = arith.cmpi uge, %dst_i{i}_v{vc}, %output_count : i32"
            )
            lines.append(
                f"      %invalid_stall_i{i}_v{vc} = arith.andi %valid_i{i}_v{vc}, %invalid_route_i{i}_v{vc} : i1"
            )
    for output in range(outputs):
        lines.append(f"      %route_o{output} = arith.constant {output} : i32")
        for vc in range(vcs):
            lines.append(
                f"      %writable_o{output}_v{vc} = arith.cmpi sgt, %space_o{output}_v{vc}, %zero : i32"
            )
    candidates: list[tuple[str, int, int, int]] = []
    for vc in range(vcs):
        for output in range(outputs):
            for i in range(inputs):
                match = f"%match_v{vc}_o{output}_i{i}"
                valid_route = f"%valid_route_v{vc}_o{output}_i{i}"
                request = f"%request_v{vc}_o{output}_i{i}"
                lines.append(f"      {match} = arith.cmpi eq, %dst_i{i}_v{vc}, %route_o{output} : i32")
                lines.append(f"      {valid_route} = arith.andi %valid_i{i}_v{vc}, {match} : i1")
                lines.append(f"      {request} = arith.andi {valid_route}, %writable_o{output}_v{vc} : i1")
                candidates.append((request, vc, output, i))
    grants = [f"%grant_{index}" for index in range(len(candidates))]
    lines.append(f"      {', '.join(grants)} = ac.arbitrate greedy_fixed_priority candidates [")
    for index, (request, _vc, output, i) in enumerate(candidates):
        comma = "," if index + 1 != len(candidates) else ""
        lines.append(f"        {request} uses [@pin{i}, @pout{output}]{comma}")
    lines.append("      ] : (" + ", ".join("i1" for _ in candidates) + ")")
    for index, (_request, vc, output, i) in enumerate(candidates):
        lines.append(
            f"      %fire_{index} = ac.try_transfer @in{i}_vc{vc} to @out{output}_vc{vc} when %grant_{index} : i32"
        )
    lines.extend(("      ac.yield_sim", "    }"))
    lines.append(f"    ac.return {', '.join(returned)} : {result_types}")
    lines.append("  }")
    return lines


def _generator_parameters(call: object) -> dict[str, StaticValue]:
    return dict(call.static_arguments)  # type: ignore[attr-defined]


def _generator_symbol(call: object) -> str:
    identity = call.schema.identity  # type: ignore[attr-defined]
    if identity == "ac.std.Crossbar":
        return _crossbar_symbol(call)
    parameters = _generator_parameters(call)
    digest = str(call.specialization).removeprefix("sha256:")[:12]  # type: ignore[attr-defined]
    if identity == "ac.std.RingNoC":
        return f"RingNoC__n{parameters['nodes']}__{digest}"
    if identity == "ac.std.MeshNoC":
        return f"MeshNoC__{parameters['width']}x{parameters['height']}__{digest}"
    raise ValueError(
        f"ACPY-GENERATOR-001: unsupported compiler-native generator {identity!r}; "
        "supported generators: ac.std.Crossbar, ac.std.MeshNoC, ac.std.RingNoC"
    )


def _queue_line(name: str, depth: int) -> str:
    return (
        f"    ac.queue @{name} payload i32 entries {depth} ordering \"fifo\" "
        f"protocol @ready_valid ownership \"exclusive\" id \"{name}\" path \"{name}\""
    )


def _resource_line(name: str) -> str:
    return (
        f"    ac.resource @{name} capacity 1 issue_width 1 ii 1 "
        "latency {kind = \"fixed\", ticks = 1 : i64} "
        "lifecycle {reservation = \"propose_commit\", release = \"balanced\", cancellation = \"explicit\"} "
        f"ownership \"exclusive\" classes [] id \"{name}\" path \"{name}\""
    )


def _noc_header(call: object) -> tuple[list[str], int, int, str]:
    parameters = _generator_parameters(call)
    nodes = int(parameters["nodes"])
    depth = int(parameters["queue_depth"])
    symbol = _generator_symbol(call)
    flow_type = "!ac.flow<i32, @ready_valid>"
    arguments = ", ".join(f"%input{node} : {flow_type}" for node in range(nodes))
    results = ", ".join(flow_type for _ in range(nodes))
    signature = flow_type if nodes == 1 else f"({results})"
    static_text = _static_arguments(call.static_arguments)  # type: ignore[attr-defined]
    return ([f"  ac.module @{symbol}({arguments}) -> {signature} parameters {{{static_text}}} graph {{"], nodes, depth, flow_type)


def _noc_scheduler(
    node: int,
    ingresses: list[tuple[str, str]],
    egresses: list[tuple[str, str]],
    route_requests: dict[tuple[str, str], str],
    decode: list[str],
    arbitration: str = "greedy_fixed_priority",
) -> list[str]:
    """Emit one deterministic output-major, ingress-minor NoC scheduler."""

    lines = [f"    ac.process @node{node}_scheduler kind \"control\" {{"]
    for ingress_name, queue in ingresses:
        lines.append(
            f"      %head_{ingress_name}, %valid_{ingress_name} = ac.peek @{queue} : i32"
        )
    lines.extend(decode)
    for egress_name, queue in egresses:
        lines.append(f"      %space_{egress_name} = ac.space @{queue}")
        lines.append(f"      %writable_{egress_name} = arith.cmpi sgt, %space_{egress_name}, %zero : i32")
    candidates: list[tuple[str, str, str, str, str]] = []
    candidates_by_egress: dict[str, list[int]] = {}
    for egress_name, egress_queue in egresses:
        for ingress_name, ingress_queue in ingresses:
            route = route_requests[(egress_name, ingress_name)]
            request = f"%request_{egress_name}_{ingress_name}"
            lines.append(
                f"      {request} = arith.andi {route}, %writable_{egress_name} : i1"
            )
            candidates.append(
                (request, ingress_name, ingress_queue, egress_name, egress_queue)
            )
            candidates_by_egress.setdefault(egress_name, []).append(len(candidates) - 1)
    arbiter_requests = [candidate[0] for candidate in candidates]
    rr_pointers: dict[str, tuple[str, list[int]]] = {}
    if arbitration == "round_robin":
        lines.append("      %rr_true = arith.constant true")
        for egress_name, indices in candidates_by_egress.items():
            state_queue = f"node{node}_rr_{egress_name}"
            pointer = f"%rr_pointer_{egress_name}"
            valid = f"%rr_pointer_valid_{egress_name}"
            lines.append(
                f"      {pointer}, {valid} = ac.try_recv @{state_queue} : i32"
            )
            positions: list[str] = []
            at_positions: list[str] = []
            for position in range(len(indices)):
                position_value = f"%rr_position_{egress_name}_{position}"
                at_position = f"%rr_at_{egress_name}_{position}"
                lines.append(
                    f"      {position_value} = arith.constant {position} : i32"
                )
                lines.append(
                    f"      {at_position} = arith.cmpi eq, {pointer}, {position_value} : i32"
                )
                positions.append(position_value)
                at_positions.append(at_position)
            selected: list[str] = []
            for target_position, candidate_index in enumerate(indices):
                request = candidates[candidate_index][0]
                terms: list[str] = []
                for start_position in range(len(indices)):
                    earlier_positions: list[int] = []
                    cursor = start_position
                    while cursor != target_position:
                        earlier_positions.append(cursor)
                        cursor = (cursor + 1) % len(indices)
                    eligible = at_positions[start_position]
                    if earlier_positions:
                        blocked = candidates[indices[earlier_positions[0]]][0]
                        for ordinal, earlier in enumerate(earlier_positions[1:], start=1):
                            combined = (
                                f"%rr_blocked_{egress_name}_{target_position}_"
                                f"{start_position}_{ordinal}"
                            )
                            lines.append(
                                f"      {combined} = arith.ori {blocked}, "
                                f"{candidates[indices[earlier]][0]} : i1"
                            )
                            blocked = combined
                        available = (
                            f"%rr_available_{egress_name}_{target_position}_{start_position}"
                        )
                        lines.append(
                            f"      {available} = arith.xori {blocked}, %rr_true : i1"
                        )
                        start_eligible = (
                            f"%rr_start_{egress_name}_{target_position}_{start_position}"
                        )
                        lines.append(
                            f"      {start_eligible} = arith.andi {eligible}, {available} : i1"
                        )
                        eligible = start_eligible
                    term = f"%rr_term_{egress_name}_{target_position}_{start_position}"
                    lines.append(f"      {term} = arith.andi {eligible}, {request} : i1")
                    terms.append(term)
                chosen = terms[0]
                for ordinal, term in enumerate(terms[1:], start=1):
                    combined = f"%rr_selected_{egress_name}_{target_position}_{ordinal}"
                    lines.append(f"      {combined} = arith.ori {chosen}, {term} : i1")
                    chosen = combined
                selected.append(chosen)
                arbiter_requests[candidate_index] = chosen
            rr_pointers[egress_name] = (pointer, indices)
    grants = [f"%grant_{index}" for index in range(len(candidates))]
    lines.append(f"      {', '.join(grants)} = ac.arbitrate greedy_fixed_priority candidates [")
    for index, (_request, ingress_name, _iq, egress_name, _eq) in enumerate(candidates):
        comma = "," if index + 1 != len(candidates) else ""
        lines.append(
            f"        {arbiter_requests[index]} uses [@node{node}_pin_{ingress_name}, @node{node}_pout_{egress_name}]{comma}"
        )
    lines.append("      ] : (" + ", ".join("i1" for _ in candidates) + ")")
    for index, (_request, _ingress_name, ingress_queue, _egress_name, egress_queue) in enumerate(candidates):
        lines.append(
            f"      %fire_{index} = ac.try_transfer @{ingress_queue} to @{egress_queue} when %grant_{index} : i32"
        )
    for egress_name, (pointer, indices) in rr_pointers.items():
        next_pointer = pointer
        for position, candidate_index in enumerate(indices):
            next_value = f"%rr_next_value_{egress_name}_{position}"
            updated = f"%rr_next_pointer_{egress_name}_{position}"
            lines.append(
                f"      {next_value} = arith.constant {(position + 1) % len(indices)} : i32"
            )
            lines.append(
                f"      {updated} = arith.select {grants[candidate_index]}, "
                f"{next_value}, {next_pointer} : i32"
            )
            next_pointer = updated
        lines.append(
            f"      %rr_state_written_{egress_name} = ac.try_send "
            f"@node{node}_rr_{egress_name} {next_pointer} : i32"
        )
    lines.extend(("      ac.yield_sim", "    }"))
    return lines


def _ring_declaration(call: object) -> list[str]:
    lines, nodes, depth, flow_type = _noc_header(call)
    parameters = _generator_parameters(call)
    offset = int(parameters["route_offset"])
    route_width = int(parameters["route_width"])
    for node in range(nodes):
        lines.append(_queue_line(f"node{node}_local_in", depth))
        lines.append(_queue_line(f"node{node}_local_out", depth))
        lines.append(_queue_line(f"link_n{node}_to_n{(node + 1) % nodes}_cw", depth))
    for node in range(nodes):
        lines.append(f"    ac.flow.import %input{node} to @node{node}_local_in : {flow_type}")
        lines.append(f"    %output{node} = ac.flow.export @node{node}_local_out : {flow_type}")
    for node in range(nodes):
        previous = (node - 1) % nodes
        ingresses = [
            ("cw", f"link_n{previous}_to_n{node}_cw"),
            ("local", f"node{node}_local_in"),
        ]
        egresses = [
            ("local", f"node{node}_local_out"),
            ("cw", f"link_n{node}_to_n{(node + 1) % nodes}_cw"),
        ]
        lines.extend(_resource_line(f"node{node}_pin_{name}") for name, _ in ingresses)
        lines.extend(_resource_line(f"node{node}_pout_{name}") for name, _ in egresses)
        decode: list[str] = ["      %zero = arith.constant 0 : i32"]
        decode.append(f"      %node_count = arith.constant {nodes} : i32")
        decode.append(f"      %route_mask = arith.constant {(1 << route_width) - 1} : i32")
        if offset:
            decode.append(f"      %route_shift = arith.constant {offset} : i32")
        requests: dict[tuple[str, str], str] = {}
        for ingress_name, _queue in ingresses:
            source = f"%head_{ingress_name}"
            if offset:
                decode.append(f"      %shifted_{ingress_name} = arith.shrui {source}, %route_shift : i32")
                source = f"%shifted_{ingress_name}"
            decode.append(f"      %dst_{ingress_name} = arith.andi {source}, %route_mask : i32")
            decode.append(f"      %dst_valid_{ingress_name} = arith.cmpi ult, %dst_{ingress_name}, %node_count : i32")
            decode.append(f"      %node_match_{ingress_name} = arith.cmpi eq, %dst_{ingress_name}, %this_node : i32")
            decode.append(f"      %not_node_{ingress_name} = arith.cmpi ne, %dst_{ingress_name}, %this_node : i32")
            decode.append(f"      %valid_dst_{ingress_name} = arith.andi %valid_{ingress_name}, %dst_valid_{ingress_name} : i1")
            decode.append(f"      %route_local_{ingress_name} = arith.andi %valid_dst_{ingress_name}, %node_match_{ingress_name} : i1")
            decode.append(f"      %route_cw_{ingress_name} = arith.andi %valid_dst_{ingress_name}, %not_node_{ingress_name} : i1")
            requests[("local", ingress_name)] = f"%route_local_{ingress_name}"
            requests[("cw", ingress_name)] = f"%route_cw_{ingress_name}"
        decode.insert(1, f"      %this_node = arith.constant {node} : i32")
        lines.extend(_noc_scheduler(node, ingresses, egresses, requests, decode))
    result_types = ", ".join(flow_type for _ in range(nodes))
    lines.append(f"    ac.return {', '.join(f'%output{node}' for node in range(nodes))} : {result_types}")
    lines.append("  }")
    return lines


_MESH_DIRECTIONS = {
    "north": (0, 1),
    "east": (1, 0),
    "south": (0, -1),
    "west": (-1, 0),
}


def _mesh_declaration(call: object) -> list[str]:
    lines, nodes, depth, flow_type = _noc_header(call)
    parameters = _generator_parameters(call)
    width = int(parameters["width"])
    height = int(parameters["height"])
    offset = int(parameters["route_offset"])
    x_width = int(parameters["route_x_width"])
    y_width = int(parameters["route_y_width"])
    arbitration = str(parameters["arbitration"])
    for node in range(nodes):
        lines.append(_queue_line(f"node{node}_local_in", depth))
        lines.append(_queue_line(f"node{node}_local_out", depth))
    for node in range(nodes):
        x, y = node % width, node // width
        for direction in ("north", "east", "south", "west"):
            dx, dy = _MESH_DIRECTIONS[direction]
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                neighbor = ny * width + nx
                lines.append(_queue_line(f"link_n{node}_to_n{neighbor}_{direction}", depth))
    if arbitration == "round_robin":
        for node in range(nodes):
            x, y = node % width, node // width
            lines.append(_queue_line(f"node{node}_rr_local", 2))
            for direction in ("north", "east", "south", "west"):
                dx, dy = _MESH_DIRECTIONS[direction]
                if 0 <= x + dx < width and 0 <= y + dy < height:
                    lines.append(_queue_line(f"node{node}_rr_{direction}", 2))
    for node in range(nodes):
        lines.append(f"    ac.flow.import %input{node} to @node{node}_local_in : {flow_type}")
        lines.append(f"    %output{node} = ac.flow.export @node{node}_local_out : {flow_type}")
    opposite = {"north": "south", "east": "west", "south": "north", "west": "east"}
    for node in range(nodes):
        x, y = node % width, node // width
        inbound: dict[str, str] = {}
        outbound: dict[str, str] = {}
        for direction in ("north", "east", "south", "west"):
            dx, dy = _MESH_DIRECTIONS[direction]
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                neighbor = ny * width + nx
                inbound[direction] = f"link_n{neighbor}_to_n{node}_{opposite[direction]}"
                outbound[direction] = f"link_n{node}_to_n{neighbor}_{direction}"
        ingresses = [(name, inbound[name]) for name in ("north", "east", "south", "west") if name in inbound]
        ingresses.append(("local", f"node{node}_local_in"))
        egresses = [("local", f"node{node}_local_out")]
        egresses.extend((name, outbound[name]) for name in ("north", "east", "south", "west") if name in outbound)
        lines.extend(_resource_line(f"node{node}_pin_{name}") for name, _ in ingresses)
        lines.extend(_resource_line(f"node{node}_pout_{name}") for name, _ in egresses)
        decode = [
            "      %zero = arith.constant 0 : i32",
            f"      %this_x = arith.constant {x} : i32",
            f"      %this_y = arith.constant {y} : i32",
            f"      %width = arith.constant {width} : i32",
            f"      %height = arith.constant {height} : i32",
            f"      %x_mask = arith.constant {(1 << x_width) - 1} : i32",
            f"      %y_mask = arith.constant {(1 << y_width) - 1} : i32",
        ]
        if offset:
            decode.append(f"      %route_shift = arith.constant {offset} : i32")
        decode.append(f"      %y_shift = arith.constant {x_width} : i32")
        requests: dict[tuple[str, str], str] = {}
        for ingress_name, _queue in ingresses:
            source = f"%head_{ingress_name}"
            if offset:
                decode.append(f"      %shifted_{ingress_name} = arith.shrui {source}, %route_shift : i32")
                source = f"%shifted_{ingress_name}"
            decode.extend(
                (
                    f"      %dst_x_{ingress_name} = arith.andi {source}, %x_mask : i32",
                    f"      %dst_y_bits_{ingress_name} = arith.shrui {source}, %y_shift : i32",
                    f"      %dst_y_{ingress_name} = arith.andi %dst_y_bits_{ingress_name}, %y_mask : i32",
                    f"      %x_valid_{ingress_name} = arith.cmpi ult, %dst_x_{ingress_name}, %width : i32",
                    f"      %y_valid_{ingress_name} = arith.cmpi ult, %dst_y_{ingress_name}, %height : i32",
                    f"      %coord_valid_{ingress_name} = arith.andi %x_valid_{ingress_name}, %y_valid_{ingress_name} : i1",
                    f"      %flit_valid_{ingress_name} = arith.andi %valid_{ingress_name}, %coord_valid_{ingress_name} : i1",
                    f"      %x_eq_{ingress_name} = arith.cmpi eq, %dst_x_{ingress_name}, %this_x : i32",
                    f"      %x_gt_{ingress_name} = arith.cmpi ugt, %dst_x_{ingress_name}, %this_x : i32",
                    f"      %x_lt_{ingress_name} = arith.cmpi ult, %dst_x_{ingress_name}, %this_x : i32",
                    f"      %y_eq_{ingress_name} = arith.cmpi eq, %dst_y_{ingress_name}, %this_y : i32",
                    f"      %y_gt_{ingress_name} = arith.cmpi ugt, %dst_y_{ingress_name}, %this_y : i32",
                    f"      %y_lt_{ingress_name} = arith.cmpi ult, %dst_y_{ingress_name}, %this_y : i32",
                    f"      %route_east_{ingress_name} = arith.andi %flit_valid_{ingress_name}, %x_gt_{ingress_name} : i1",
                    f"      %route_west_{ingress_name} = arith.andi %flit_valid_{ingress_name}, %x_lt_{ingress_name} : i1",
                    f"      %x_eq_y_gt_{ingress_name} = arith.andi %x_eq_{ingress_name}, %y_gt_{ingress_name} : i1",
                    f"      %x_eq_y_lt_{ingress_name} = arith.andi %x_eq_{ingress_name}, %y_lt_{ingress_name} : i1",
                    f"      %x_eq_y_eq_{ingress_name} = arith.andi %x_eq_{ingress_name}, %y_eq_{ingress_name} : i1",
                    f"      %route_north_{ingress_name} = arith.andi %flit_valid_{ingress_name}, %x_eq_y_gt_{ingress_name} : i1",
                    f"      %route_south_{ingress_name} = arith.andi %flit_valid_{ingress_name}, %x_eq_y_lt_{ingress_name} : i1",
                    f"      %route_local_{ingress_name} = arith.andi %flit_valid_{ingress_name}, %x_eq_y_eq_{ingress_name} : i1",
                )
            )
            for egress_name, _ in egresses:
                requests[(egress_name, ingress_name)] = f"%route_{egress_name}_{ingress_name}"
        lines.extend(
            _noc_scheduler(
                node,
                ingresses,
                egresses,
                requests,
                decode,
                arbitration=arbitration,
            )
        )
    result_types = ", ".join(flow_type for _ in range(nodes))
    lines.append(f"    ac.return {', '.join(f'%output{node}' for node in range(nodes))} : {result_types}")
    lines.append("  }")
    return lines


_GENERATOR_EMITTERS = {
    "ac.std.Crossbar": _crossbar_declaration,
    "ac.std.MeshNoC": _mesh_declaration,
    "ac.std.RingNoC": _ring_declaration,
}


def _generator_declaration(call: object) -> list[str]:
    identity = call.schema.identity  # type: ignore[attr-defined]
    emitter = _GENERATOR_EMITTERS.get(identity)
    if emitter is None:
        raise ValueError(
            f"ACPY-GENERATOR-001: unsupported compiler-native generator {identity!r}; "
            f"supported generators: {', '.join(sorted(_GENERATOR_EMITTERS))}"
        )
    return emitter(call)


def _boundary_symbol(direction: str, value: ValueVersion) -> str:
    prefix = "FlowSource" if direction == "export" else "FlowSink"
    return f"{prefix}__{_ssa(value)}"


def _flow_boundary_declarations(program: NormalizedProgram) -> list[str]:
    lines: list[str] = []
    for boundary in program.flow_boundaries:
        symbol = _boundary_symbol(boundary.direction, boundary.value)
        flow_types = tuple(
            f"!ac.flow<{payload}, @{protocol}>"
            for _name, payload, protocol, _depth in boundary.queues
        )
        if boundary.direction == "export":
            result_signature = (
                flow_types[0]
                if len(flow_types) == 1
                else "(" + ", ".join(flow_types) + ")"
            )
            lines.append(f"  ac.module @{symbol}() -> {result_signature} parameters {{}} graph {{")
        else:
            arguments = ", ".join(
                f"%vc{vc} : {flow_type}" for vc, flow_type in enumerate(flow_types)
            )
            lines.append(f"  ac.module @{symbol}({arguments}) parameters {{}} graph {{")
        returned: list[str] = []
        for vc, (queue_name, payload, protocol, depth) in enumerate(boundary.queues):
            lines.append(
                f"    ac.queue @{queue_name} payload {payload} entries {depth} ordering \"fifo\" "
                f"protocol @{protocol} ownership \"exclusive\" id \"{queue_name}\" path \"{queue_name}\""
            )
        for vc, (queue_name, payload, protocol, _depth) in enumerate(boundary.queues):
            flow_type = f"!ac.flow<{payload}, @{protocol}>"
            if boundary.direction == "export":
                value = f"%vc{vc}"
                lines.append(f"    {value} = ac.flow.export @{queue_name} : {flow_type}")
                returned.append(value)
            else:
                lines.append(f"    ac.flow.import %vc{vc} to @{queue_name} : {flow_type}")
        if returned:
            lines.append(f"    ac.return {', '.join(returned)} : {', '.join(flow_types)}")
        else:
            lines.append("    ac.return")
        lines.append("  }")
    return lines


def _component_declarations(program: NormalizedProgram) -> list[str]:
    schemas = {
        call.schema.identity: call.schema
        for call in program.calls
        if call.schema.generator is None
    }
    symbols: set[str] = set()
    lines: list[str] = []
    for identity in sorted(schemas, key=utf16_sort_key):
        schema = schemas[identity]
        symbol = _symbol(identity)
        if symbol in symbols:
            raise ValueError("ACPY-CALL-006: component symbol collision")
        symbols.add(symbol)
        arguments = ", ".join(
            f"%{port.name} : {annotation_type_to_acir(port.acir_type)}" for port in schema.ports
        )
        result_types = tuple(annotation_type_to_acir(result.acir_type) for result in schema.results)
        result_signature = (
            ""
            if not result_types
            else " -> " + (
                result_types[0]
                if len(result_types) == 1
                else "(" + ", ".join(result_types) + ")"
            )
        )
        calls = [call for call in program.calls if call.schema.identity == identity]
        schema_parameters = calls[0].static_arguments if calls else ()
        parameter_text = _static_arguments(schema_parameters)
        if schema.external_binding is not None:
            lines.append(
                f"  ac.module.extern @{symbol} : ({', '.join(annotation_type_to_acir(port.acir_type) for port in schema.ports)})"
                f" -> {('()' if not result_types else result_signature.removeprefix(' -> '))} "
                f"parameters {{{parameter_text}}} implementation "
                f"{{registry = \"cpp\", name = {json.dumps(schema.external_binding)}}}"
            )
            continue
        lines.append(
            f"  ac.module @{symbol}({arguments}){result_signature} parameters {{}} graph {{"
        )
        returned: list[str] = []
        for result in schema.results:
            if result.source_binding is None:
                raise ValueError(
                    f"ACPY-VERIFY-001: {identity} result {result.name!r} has no structural source"
                )
            returned.append(f"%{result.source_binding}")
        if returned:
            lines.append(
                "    ac.return "
                + ", ".join(returned)
                + " : "
                + ", ".join(result_types)
            )
        else:
            lines.append("    ac.return")
        lines.append("  }")
    specializations: dict[str, object] = {}
    for call in program.calls:
        if call.schema.generator is not None and call.specialization is not None:
            specializations.setdefault(call.specialization, call)
    for fingerprint in sorted(specializations, key=utf16_sort_key):
        lines.extend(_generator_declaration(specializations[fingerprint]))
    lines.extend(_flow_boundary_declarations(program))
    return lines


def _emit_process(process: ProcessProgram, kind: str) -> list[str]:
    queue_names: dict[str, tuple[str, str]] = {}
    for capture in process.captures:
        match = re.fullmatch(r"QueueSpec\[([^,]+),([^,]+),(\d+),([^]]+)\]", capture.type_key)
        if match is None:
            raise ValueError("ACPY-VERIFY-001: only root-owned QueueSpec process captures are supported")
        queue_names[capture.source_name] = (match.group(4), match.group(1))
    if len(process.blocks) != 1:
        raise ValueError("ACPY-VERIFY-001: multi-block process requires CFG lowering")
    block = process.blocks[0]
    if block.edge.kind != "suspend" or block.edge.operation != "yield_sim":
        raise ValueError("ACPY-VERIFY-001: unsupported process operation shape")
    lines = [f"    ac.process @{_symbol(process.name)} kind {json.dumps(kind)} {{"]
    for index, action in enumerate(block.actions):
        if action.operation not in {"try_send", "try_recv"} or not action.arguments:
            raise ValueError("ACPY-VERIFY-001: only single-block Queue actions are supported")
        queue = queue_names.get(action.arguments[0])
        if queue is None:
            raise ValueError("ACPY-VERIFY-001: Queue action target is not root-owned")
        queue_name, payload_type = queue
        if action.operation == "try_send":
            if len(action.arguments) != 2:
                raise ValueError("ACPY-PROCESS-003: try_send requires queue and i32 payload")
            payload = action.arguments[1]
            if re.fullmatch(r"-?[0-9]+", payload):
                value = f"%send_value_{index}"
                lines.append(f"      {value} = arith.constant {payload} : i32")
            elif _SYMBOL.fullmatch(payload):
                value = f"%{payload}"
            else:
                raise ValueError("ACPY-PROCESS-003: try_send payload must be one i32 value")
            result = (
                f"%{action.result}"
                if isinstance(action.result, str)
                else f"%send_accepted_{index}"
            )
            lines.append(f"      {result} = ac.try_send @{queue_name} {value} : {payload_type}")
        else:
            if len(action.arguments) != 1:
                raise ValueError("ACPY-PROCESS-003: try_recv requires one queue")
            if isinstance(action.result, tuple):
                value, received = (f"%{name}" for name in action.result)
            elif isinstance(action.result, str):
                value, received = f"%recv_value_{index}", f"%{action.result}"
            else:
                value, received = f"%recv_value_{index}", f"%recv_received_{index}"
            lines.append(f"      {value}, {received} = ac.try_recv @{queue_name} : {payload_type}")
    lines.extend(("      ac.yield_sim", "    }"))
    return lines


def lower_to_acir(
    program: NormalizedProgram,
    document: AcpyDocument,
    *,
    system_name: str,
    processes: tuple[tuple[ProcessProgram, str], ...] = (),
) -> AcirArtifact:
    errors = document.verify()
    if errors:
        raise ValueError("ACPY-VERIFY-001: lowering requires verified ACPy")
    types = _argument_types(program)
    root = _symbol(program.definition)
    lines = ['module attributes {ac.contract_epoch = "0.2"} {']
    workload = next(
        (process.name for process, kind in processes if kind == "workload"), None
    )
    system = f"  ac.system @{_symbol(system_name)} root @{root} as \"root\" tick 0 \"cycle\""
    if workload is not None:
        system += f" workload @{root}::@{_symbol(workload)}"
    system += (
        " seed {kind = \"fixed\", value = 0 : i64} instrumentation [] "
        "results {id = \"default\", format = \"json\"} selected true"
    )
    lines.append(system)
    flow_specs: set[tuple[str, str]] = set()
    for argument in program.arguments:
        if (spec := _flow_spec(argument.type_key)) is not None:
            flow_specs.add(spec)
        elif (bundle := _bundle_spec(argument.type_key)) is not None:
            flow_specs.add(bundle[:2])
    for call in program.calls:
        if call.schema.generator is not None:
            flow_specs.add(("i32", "ready_valid"))
            continue
        for port in call.schema.ports:
            if (spec := _flow_spec(port.acir_type)) is not None:
                flow_specs.add(spec)
        for result in call.schema.results:
            if (spec := _flow_spec(result.acir_type)) is not None:
                flow_specs.add(spec)
    for process, _kind in processes:
        for capture in process.captures:
            match = re.fullmatch(
                r"QueueSpec\[([^,]+),([^,]+),(\d+),([^]]+)\]", capture.type_key
            )
            if match is not None:
                flow_specs.add((match.group(1), match.group(2)))
    protocols: dict[str, set[str]] = {}
    for payload, protocol in flow_specs:
        protocols.setdefault(protocol, set()).add(payload)
    for protocol in sorted(protocols, key=utf16_sort_key):
        lines.extend(
            (
                f"  ac.protocol @{protocol} {{",
                '    ac.role @sender dual @receiver cardinality "exclusive"',
                '    ac.role @receiver dual @sender cardinality "exclusive"',
                "    ac.state @idle initial true terminal false",
            )
        )
        for index, payload in enumerate(sorted(protocols[protocol], key=utf16_sort_key)):
            lines.append(
                f"    ac.event @transfer_{index} from @sender to @receiver payload {payload} action \"offer\""
            )
        lines.extend(
            (
                '    ac.guarantee "ordering" = "fifo"',
                '    ac.guarantee "backpressure" = "capacity"',
                "  }",
            )
        )
    declarations = _component_declarations(program)
    if declarations:
        lines.extend(declarations)

    bundle_widths: dict[str, int] = {}
    for call in program.calls:
        if call.schema.generator is None:
            continue
        vc = int(dict(call.static_arguments)["virtual_channels"])
        for binding in call.inputs:
            previous = bundle_widths.setdefault(binding.value.name, vc)
            if previous != vc:
                raise ValueError("ACPY-CROSSBAR-001: FlowBundle VC shape mismatch")
        for binding in call.results:
            bundle_widths[binding.value.name] = vc
    for boundary in program.flow_boundaries:
        bundle_widths[boundary.value.name] = len(boundary.queues)
    argument_parts: list[str] = []
    for argument in program.arguments:
        if argument.category != "flow_bundle":
            argument_parts.append(f"%{argument.source_name} : {types[argument.name]}")
            continue
        bundle = _bundle_spec(argument.type_key)
        assert bundle is not None
        payload, protocol, declared_width = bundle
        width = bundle_widths.get(argument.name, declared_width)
        if width is None:
            raise ValueError(
                f"ACPY-TYPE-FLOW: cannot infer FlowBundle shape for {argument.source_name!r}"
            )
        if declared_width is not None and declared_width != width:
            raise ValueError("ACPY-CROSSBAR-001: FlowBundle VC shape mismatch")
        flow_type = f"!ac.flow<{payload}, @{protocol}>"
        argument_parts.extend(
            f"%{argument.source_name}_vc{vc} : {flow_type}" for vc in range(width)
        )
    arguments = ", ".join(argument_parts)
    return_types_list: list[str] = []
    for value in program.returns:
        if value.category != "flow_bundle":
            return_types_list.append(annotation_type_to_acir(value.type_key))
            continue
        bundle = _bundle_spec(value.type_key)
        assert bundle is not None
        payload, protocol, declared_width = bundle
        width = bundle_widths.get(value.name, declared_width)
        if width is None:
            raise ValueError("ACPY-TYPE-FLOW: cannot infer returned FlowBundle shape")
        return_types_list.extend(f"!ac.flow<{payload}, @{protocol}>" for _ in range(width))
    return_types = tuple(return_types_list)
    result_signature = (
        ""
        if not return_types
        else " -> "
        + (return_types[0] if len(return_types) == 1 else "(" + ", ".join(return_types) + ")")
    )
    lines.append(
        f"  ac.module @{root}({arguments}){result_signature} parameters {{}} graph {{"
    )
    source_map: list[tuple[str, SourceSpan]] = []
    names: dict[str, str | tuple[str, ...]] = {}
    for argument in program.arguments:
        if argument.category == "flow_bundle":
            width = bundle_widths[argument.name]
            names[argument.name] = tuple(
                f"%{argument.source_name}_vc{vc}" for vc in range(width)
            )
        else:
            names[argument.name] = f"%{argument.source_name}"
    declared_queues: set[str] = set()
    queue_specs = {
        queue_name: (payload, protocol, depth)
        for boundary in program.flow_boundaries
        for queue_name, payload, protocol, depth in boundary.queues
    }
    for queue_name, host_name in program.host_inputs:
        if queue_name not in queue_specs:
            raise ValueError(
                f"ACPY-HOST-001: host input queue {queue_name!r} must be exported as a Flow"
            )
        payload, protocol, depth = queue_specs[queue_name]
        declared_queues.add(queue_name)
        lines.append(
            f"    ac.queue @{queue_name} payload {payload} entries {depth} ordering \"fifo\" "
            f"protocol @{protocol} ownership \"exclusive\" id \"{queue_name}\" path \"{queue_name}\" "
            f"{{ac.host_input = {json.dumps(host_name)}}}"
        )
    for process, _kind in processes:
        for capture in process.captures:
            match = re.fullmatch(
                r"QueueSpec\[([^,]+),([^,]+),(\d+),([^]]+)\]", capture.type_key
            )
            if match is None:
                continue
            payload, protocol, depth, queue_name = match.groups()
            if queue_name in declared_queues:
                continue
            declared_queues.add(queue_name)
            lines.append(
                f"    ac.queue @{queue_name} payload {payload} entries {depth} ordering \"fifo\" "
                f"protocol @{protocol} ownership \"exclusive\" id \"{queue_name}\" path \"{queue_name}\""
            )
    for boundary in program.flow_boundaries:
        if boundary.direction != "export":
            continue
        leaves = tuple(
            f"%{boundary.value.source_name}_vc{vc}"
            for vc in range(len(boundary.queues))
        )
        flow_types = tuple(
            f"!ac.flow<{payload}, @{protocol}>"
            for _name, payload, protocol, _depth in boundary.queues
        )
        if all(queue_name in declared_queues for queue_name, *_ in boundary.queues):
            for leaf, flow_type, (queue_name, *_rest) in zip(
                leaves, flow_types, boundary.queues, strict=True
            ):
                lines.append(f"    {leaf} = ac.flow.export @{queue_name} : {flow_type}")
        else:
            arrow = flow_types[0] if len(flow_types) == 1 else f"({', '.join(flow_types)})"
            instance = f"boundary_source_{boundary.value.source_name}"
            lines.append(
                f"    {', '.join(leaves)} = ac.instance @{instance} of "
                f"@{_boundary_symbol(boundary.direction, boundary.value)}() static {{}} "
                f"id {json.dumps(instance)} path {json.dumps(instance)} : () -> {arrow}"
            )
        names[boundary.value.name] = tuple(leaves)
    for call in program.calls:
        if call.schema.generator is not None:
            flattened_operands = [
                leaf
                for binding in call.inputs
                for leaf in (
                    names[binding.value.name]
                    if isinstance(names[binding.value.name], tuple)
                    else (names[binding.value.name],)
                )
            ]
            operands = ", ".join(flattened_operands)
            flow_type = "!ac.flow<i32, @ready_valid>"
            operand_types = ", ".join(flow_type for _ in flattened_operands)
            flat_results = [
                (binding, vc)
                for binding in call.results
                for vc in range(binding.shape[0])
            ]
            result_names = tuple(
                f"%{_ssa(binding.value)}_vc{vc}" for binding, vc in flat_results
            )
            for binding in call.results:
                names[binding.value.name] = tuple(
                    f"%{_ssa(binding.value)}_vc{vc}" for vc in range(binding.shape[0])
                )
            prefix = ", ".join(result_names) + " = "
            result_types = ", ".join(flow_type for _ in result_names)
            arrow = flow_type if len(result_names) == 1 else f"({result_types})"
            lines.append(
                f"    {prefix}ac.instance @{_symbol(call.instance_name)} of @{_generator_symbol(call)}({operands}) "
                f"static {{{_static_arguments(call.static_arguments)}}} id {json.dumps(call.instance_name)} "
                f"path {json.dumps(call.instance_name)} : ({operand_types}) -> {arrow}"
            )
            source_map.append((f"@{root}::@{call.instance_name}", call.source))
            continue
        operands = ", ".join(str(names[binding.value.name]) for binding in call.inputs)
        operand_types = ", ".join(
            annotation_type_to_acir(port.acir_type) for port in call.schema.ports
        )
        results = tuple(binding.value for binding in call.results)
        if len(results) > 1:
            raise ValueError("ACPY-VERIFY-001: multi-result instance emission is not closed")
        prefix = ""
        if results:
            name = f"%{_ssa(results[0])}"
            names[results[0].name] = name
            prefix = name + " = "
        result_types = ", ".join(annotation_type_to_acir(result.acir_type) for result in call.schema.results)
        arrow = result_types if len(call.schema.results) == 1 else f"({result_types})"
        lines.append(
            f"    {prefix}ac.instance @{_symbol(call.instance_name)} of @{_symbol(call.schema.identity)}({operands}) "
            f"static {{{_static_arguments(call.static_arguments)}}} id {json.dumps(call.instance_name)} "
            f"path {json.dumps(call.instance_name)} : ({operand_types}) -> {arrow}"
        )
        source_map.append((f"@{root}::@{call.instance_name}", call.source))

    for process, kind in processes:
        lines.extend(_emit_process(process, kind))
    for boundary in program.flow_boundaries:
        if boundary.direction != "import":
            continue
        source = names[boundary.value.name]
        if not isinstance(source, tuple) or len(source) != len(boundary.queues):
            raise ValueError("ACPY-FLOW-007: Queue tuple and FlowBundle shape must match")
        flow_types = tuple(
            f"!ac.flow<{payload}, @{protocol}>"
            for _name, payload, protocol, _depth in boundary.queues
        )
        if all(queue_name in declared_queues for queue_name, *_ in boundary.queues):
            for leaf, flow_type, (queue_name, *_rest) in zip(
                source, flow_types, boundary.queues, strict=True
            ):
                lines.append(f"    ac.flow.import {leaf} to @{queue_name} : {flow_type}")
        else:
            instance = f"boundary_sink_{boundary.value.source_name}"
            lines.append(
                f"    ac.instance @{instance} of @{_boundary_symbol(boundary.direction, boundary.value)}"
                f"({', '.join(source)}) static {{}} id {json.dumps(instance)} path {json.dumps(instance)} "
                f": ({', '.join(flow_types)}) -> ()"
            )
    if program.returns:
        flattened_returns = [
            leaf
            for value in program.returns
            for leaf in (
                names[value.name]
                if isinstance(names[value.name], tuple)
                else (names[value.name],)
            )
        ]
        operands = ", ".join(flattened_returns)
        lines.append(f"    ac.return {operands} : {', '.join(return_types)}")
    else:
        lines.append("    ac.return")
    lines.extend(("  }", "}"))
    text = "\n".join(lines) + "\n"
    return AcirArtifact(
        text=text,
        sha256=sha256_bytes(text.encode("utf-8")),
        source_map=tuple(source_map),
    )
