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
from ._records import RecordDefinition, collect_record_definitions, named_acir_type
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


def _payload_acir(type_key: str, records: tuple[RecordDefinition, ...]) -> str:
    primitive = {
        "bool": "i1",
        "int": "i32",
        "i1": "i1",
        "i8": "i8",
        "i16": "i16",
        "i32": "i32",
        "i64": "i64",
        "f32": "f32",
        "f64": "f64",
    }.get(type_key)
    if primitive is not None:
        return primitive
    named = named_acir_type(type_key, records)
    if named is not None:
        return named
    if type_key.startswith("!ac."):
        return type_key
    raise ValueError(f"ACPY-TYPE-PACKET: unresolved payload type {type_key!r}")


def _packet_size(type_key: str, records: tuple[RecordDefinition, ...]) -> int | None:
    return next(
        (record.size for record in records if record.kind == "packet" and record.name == type_key),
        None,
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
    records = collect_record_definitions(captured)
    for record in records:
        allocator.allocate(
            kind=record.kind,  # type: ignore[arg-type]
            scope="types",
            source=record.site.span,
            parent=system.id,
            type=record.acir_type,
            properties=_properties(
                alignment=record.alignment,
                endianness=record.endianness,
                fields=tuple(
                    (
                        field.name,
                        field.type_key,
                        field.offset,
                    )
                    for field in record.fields
                ),
                name=record.name,
                size=record.size,
            ),
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


def _emit_type_scope(records: tuple[RecordDefinition, ...]) -> list[str]:
    if not records:
        return []
    lines = ["  ac.type_scope @types {"]
    for record in records:
        fields = ", ".join(
            f'{{name = {json.dumps(field.name)}, type = {field.acir_type}}}'
            for field in record.fields
        )
        lines.append(f"    ac.{record.kind} @{record.name} fields [{fields}]")
    layouts = []
    for record in records:
        members = (
            f'abi_alignment = {record.alignment} : i64, '
            f'endianness = {json.dumps(record.endianness)}, '
            f'preferred_alignment = {record.alignment} : i64, '
        )
        if record.kind == "packet":
            members += f'serialization_width = {record.size} : i64, '
        members += f'size = {record.size} : i64'
        layouts.append(f"{record.acir_type} = {{{members}}}")
    lines.append("  } {dlti.dl_spec = #dlti.dl_spec<")
    lines.append("    " + ",\n    ".join(layouts))
    lines.append("  >}")
    return lines


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


def _generator_payload_type(call: object) -> str:
    payload = str(_generator_parameters(call)["payload"])
    return "i32" if payload == "i32" else f"!ac.packet<@types::@{payload}>"


def _queue_line(name: str, depth: int, payload_type: str = "i32", payload_size: int | None = None) -> str:
    bytes_text = f" bytes {depth * payload_size}" if payload_size is not None else ""
    return (
        f"    ac.queue @{name} payload {payload_type} entries {depth}{bytes_text} ordering \"fifo\" "
        f"protocol @ready_valid ownership \"exclusive\" id \"{name}\" path \"{name}\""
    )


def _resource_line(name: str) -> str:
    return (
        f"    ac.resource @{name} capacity 1 issue_width 1 ii 1 "
        "latency {kind = \"fixed\", ticks = 1 : i64} "
        "lifecycle {reservation = \"propose_commit\", release = \"balanced\", cancellation = \"explicit\"} "
        f"ownership \"exclusive\" classes [] id \"{name}\" path \"{name}\""
    )


@dataclass(frozen=True, slots=True)
class _NoCIngress:
    name: str
    queue: str
    return_credit_queue: str | None = None


@dataclass(frozen=True, slots=True)
class _NoCEgress:
    name: str
    queue: str
    vc_state_queue: str | None = None
    receive_credit_queue: str | None = None


@dataclass(frozen=True, slots=True)
class _NoCTiming:
    flow_control: str = "ready_valid"
    router_pipeline: str = "single_stage_elastic"
    credit_delay: int = 0
    vc_alloc_delay: int = 0
    sw_alloc_delay: int = 0
    wait_for_tail_credit: bool = False


def _noc_header(call: object) -> tuple[list[str], int, int, str, str, int | None]:
    parameters = _generator_parameters(call)
    nodes = int(parameters["nodes"])
    depth = int(parameters["queue_depth"])
    symbol = _generator_symbol(call)
    payload_type = _generator_payload_type(call)
    payload_size = int(parameters["payload_size"]) if "payload_size" in parameters else None
    flow_type = f"!ac.flow<{payload_type}, @ready_valid>"
    arguments = ", ".join(f"%input{node} : {flow_type}" for node in range(nodes))
    results = ", ".join(flow_type for _ in range(nodes))
    signature = flow_type if nodes == 1 else f"({results})"
    static_text = _static_arguments(call.static_arguments)  # type: ignore[attr-defined]
    return ([f"  ac.module @{symbol}({arguments}) -> {signature} parameters {{{static_text}}} graph {{"], nodes, depth, flow_type, payload_type, payload_size)


def _noc_scheduler(
    node: int,
    ingresses: list[_NoCIngress],
    egresses: list[_NoCEgress],
    route_requests: dict[tuple[str, str], str],
    decode: list[str],
    payload_type: str,
    arbitration: str = "greedy_fixed_priority",
    timing: _NoCTiming = _NoCTiming(),
) -> list[str]:
    """Emit one deterministic output-major, ingress-minor NoC scheduler."""

    lines = [f"    ac.process @node{node}_scheduler kind \"control\" {{"]
    for ingress in ingresses:
        lines.append(
            f"      %head_{ingress.name}, %valid_{ingress.name} = ac.peek @{ingress.queue} : {payload_type}"
        )
    lines.extend(decode)
    credit_egresses = [
        egress
        for egress in egresses
        if timing.wait_for_tail_credit and egress.receive_credit_queue is not None
    ]
    if credit_egresses:
        lines.append("      %vc_true = arith.constant true")
        lines.append("      %vc_false = arith.constant false")
        lines.append("      %vc_one = arith.constant 1 : i32")
        lines.append("      %vc_wait = arith.constant -1 : i32")
        for egress in credit_egresses:
            assert egress.vc_state_queue is not None
            lines.append(
                f"      %vc_state_{egress.name}, %vc_state_valid_{egress.name} = "
                f"ac.try_recv @{egress.vc_state_queue} : i32"
            )
            lines.append(
                f"      %credit_token_{egress.name}, %credit_ready_{egress.name} = "
                f"ac.try_recv @{egress.receive_credit_queue} : i32"
            )
            lines.append(
                f"      %vc_counting_{egress.name} = arith.cmpi sgt, "
                f"%vc_state_{egress.name}, %zero : i32"
            )
            lines.append(
                f"      %vc_decremented_{egress.name} = arith.subi "
                f"%vc_state_{egress.name}, %vc_one : i32"
            )
            lines.append(
                f"      %vc_aged_{egress.name} = arith.select %vc_counting_{egress.name}, "
                f"%vc_decremented_{egress.name}, %vc_state_{egress.name} : i32"
            )
            lines.append(
                f"      %vc_effective_{egress.name} = arith.select %credit_ready_{egress.name}, "
                f"%credit_token_{egress.name}, %vc_aged_{egress.name} : i32"
            )
            lines.append(
                f"      %vc_busy_{egress.name} = arith.cmpi ne, "
                f"%vc_effective_{egress.name}, %zero : i32"
            )
            lines.append(
                f"      %vc_free_{egress.name} = arith.xori %vc_busy_{egress.name}, %vc_true : i1"
            )
    for egress in egresses:
        lines.append(f"      %space_{egress.name} = ac.space @{egress.queue}")
        lines.append(f"      %writable_{egress.name} = arith.cmpi sgt, %space_{egress.name}, %zero : i32")
    candidates: list[tuple[str, str, str, str, str]] = []
    candidates_by_egress: dict[str, list[int]] = {}
    for egress in egresses:
        for ingress in ingresses:
            route = route_requests[(egress.name, ingress.name)]
            request = f"%request_{egress.name}_{ingress.name}"
            lines.append(
                f"      {request} = arith.andi {route}, %writable_{egress.name} : i1"
            )
            if egress in credit_egresses:
                gated = f"%request_vc_{egress.name}_{ingress.name}"
                lines.append(
                    f"      {gated} = arith.andi {request}, %vc_free_{egress.name} : i1"
                )
                request = gated
            candidates.append(
                (request, ingress.name, ingress.queue, egress.name, egress.queue)
            )
            candidates_by_egress.setdefault(egress.name, []).append(len(candidates) - 1)
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
            f"      %fire_{index} = ac.try_transfer @{ingress_queue} to @{egress_queue} when %grant_{index} : {payload_type}"
        )
    fires_by_egress: dict[str, list[str]] = {}
    fires_by_ingress: dict[str, list[str]] = {}
    for index, (_request, ingress_name, _iq, egress_name, _eq) in enumerate(candidates):
        fires_by_egress.setdefault(egress_name, []).append(f"%fire_{index}")
        fires_by_ingress.setdefault(ingress_name, []).append(f"%fire_{index}")

    def emit_any(prefix: str, terms: list[str]) -> str:
        value = terms[0]
        for ordinal, term in enumerate(terms[1:], start=1):
            combined = f"%{prefix}_{ordinal}"
            lines.append(f"      {combined} = arith.ori {value}, {term} : i1")
            value = combined
        return value

    for egress in credit_egresses:
        assert egress.vc_state_queue is not None
        fired = emit_any(f"vc_fired_{egress.name}", fires_by_egress[egress.name])
        next_state = f"%vc_state_next_{egress.name}"
        lines.append(
            f"      {next_state} = arith.select {fired}, %vc_wait, "
            f"%vc_effective_{egress.name} : i32"
        )
        lines.append(
            f"      %vc_state_written_{egress.name} = ac.try_send "
            f"@{egress.vc_state_queue} {next_state} : i32"
        )
    if timing.wait_for_tail_credit:
        lines.append(f"      %credit_value = arith.constant {timing.credit_delay} : i32")
        for ingress in ingresses:
            if ingress.return_credit_queue is None:
                continue
            departed = emit_any(
                f"departed_{ingress.name}", fires_by_ingress[ingress.name]
            )
            lines.append(f"      scf.if {departed} {{")
            lines.append(
                f"        %credit_accepted_{ingress.name} = ac.try_send "
                f"@{ingress.return_credit_queue} %credit_value : i32"
            )
            lines.append(
                f"        ac.assert %credit_accepted_{ingress.name}, "
                f'"NoC credit queue overflow on {ingress.return_credit_queue}"'
            )
            lines.append("      }")
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


def _noc_iq_scheduler(
    node: int,
    ingresses: list[_NoCIngress],
    egresses: list[_NoCEgress],
    route_requests: dict[tuple[str, str], str],
    decode: list[str],
    payload_type: str,
    arbitration: str,
    timing: _NoCTiming,
) -> list[str]:
    """Emit a topology-neutral one-VC input-queued router scheduler."""

    lines = [f"    ac.process @node{node}_scheduler kind \"control\" {{"]
    for ingress in ingresses:
        lines.append(
            f"      %head_{ingress.name}, %valid_{ingress.name} = "
            f"ac.peek @{ingress.queue} : {payload_type}"
        )
    lines.extend(decode)
    lines.extend(
        (
            "      %iq_true = arith.constant true",
            "      %iq_false = arith.constant false",
            "      %iq_one = arith.constant 1 : i32",
            "      %iq_wait_credit = arith.constant -128 : i32",
            "      %iq_va_base = arith.constant 100 : i32",
            "      %iq_sa_base = arith.constant 200 : i32",
        )
    )
    for egress in egresses:
        lines.append(f"      %space_{egress.name} = ac.space @{egress.queue}")
        lines.append(
            f"      %writable_{egress.name} = arith.cmpi sgt, "
            f"%space_{egress.name}, %zero : i32"
        )

    pipe_effective: dict[str, str] = {}
    pipe_idle: dict[str, str] = {}
    pipe_va_ready: dict[str, str] = {}
    pipe_sa_ready: dict[str, str] = {}
    ingress_valid_route: dict[str, str] = {}

    def emit_any(prefix: str, terms: list[str]) -> str:
        value = terms[0]
        for ordinal, term in enumerate(terms[1:], start=1):
            combined = f"%{prefix}_{ordinal}"
            lines.append(f"      {combined} = arith.ori {value}, {term} : i1")
            value = combined
        return value

    for ingress in ingresses:
        state_queue = f"node{node}_pipe_{ingress.name}"
        lines.append(
            f"      %pipe_state_{ingress.name}, %pipe_state_valid_{ingress.name} = "
            f"ac.try_recv @{state_queue} : i32"
        )
        lines.append(
            f"      %pipe_gt_va_{ingress.name} = arith.cmpi sgt, "
            f"%pipe_state_{ingress.name}, %iq_va_base : i32"
        )
        lines.append(
            f"      %pipe_lt_sa_{ingress.name} = arith.cmpi slt, "
            f"%pipe_state_{ingress.name}, %iq_sa_base : i32"
        )
        lines.append(
            f"      %pipe_va_counting_{ingress.name} = arith.andi "
            f"%pipe_gt_va_{ingress.name}, %pipe_lt_sa_{ingress.name} : i1"
        )
        lines.append(
            f"      %pipe_sa_counting_{ingress.name} = arith.cmpi sgt, "
            f"%pipe_state_{ingress.name}, %iq_sa_base : i32"
        )
        lines.append(
            f"      %pipe_counting_{ingress.name} = arith.ori "
            f"%pipe_va_counting_{ingress.name}, %pipe_sa_counting_{ingress.name} : i1"
        )
        lines.append(
            f"      %pipe_decremented_{ingress.name} = arith.subi "
            f"%pipe_state_{ingress.name}, %iq_one : i32"
        )
        effective = f"%pipe_effective_{ingress.name}"
        lines.append(
            f"      {effective} = arith.select %pipe_counting_{ingress.name}, "
            f"%pipe_decremented_{ingress.name}, %pipe_state_{ingress.name} : i32"
        )
        pipe_effective[ingress.name] = effective
        pipe_idle[ingress.name] = f"%pipe_idle_{ingress.name}"
        pipe_va_ready[ingress.name] = f"%pipe_va_ready_{ingress.name}"
        pipe_sa_ready[ingress.name] = f"%pipe_sa_ready_{ingress.name}"
        lines.append(
            f"      {pipe_idle[ingress.name]} = arith.cmpi eq, {effective}, %zero : i32"
        )
        lines.append(
            f"      {pipe_va_ready[ingress.name]} = arith.cmpi eq, "
            f"{effective}, %iq_va_base : i32"
        )
        lines.append(
            f"      {pipe_sa_ready[ingress.name]} = arith.cmpi eq, "
            f"{effective}, %iq_sa_base : i32"
        )
        routes = [route_requests[(egress.name, ingress.name)] for egress in egresses]
        ingress_valid_route[ingress.name] = emit_any(
            f"valid_route_{ingress.name}", routes
        )

    egress_effective: dict[str, str] = {}
    egress_free: dict[str, str] = {}
    for egress in egresses:
        assert egress.vc_state_queue is not None
        lines.append(
            f"      %owner_state_{egress.name}, %owner_state_valid_{egress.name} = "
            f"ac.try_recv @{egress.vc_state_queue} : i32"
        )
        current = f"%owner_state_{egress.name}"
        if timing.wait_for_tail_credit and egress.receive_credit_queue is not None:
            lines.append(
                f"      %owner_credit_{egress.name}, %owner_credit_ready_{egress.name} = "
                f"ac.try_recv @{egress.receive_credit_queue} : i32"
            )
            lines.append(
                f"      %owner_after_wait_{egress.name} = arith.cmpi sgt, "
                f"{current}, %iq_wait_credit : i32"
            )
            lines.append(
                f"      %owner_before_free_{egress.name} = arith.cmpi slt, "
                f"{current}, %zero : i32"
            )
            lines.append(
                f"      %owner_counting_{egress.name} = arith.andi "
                f"%owner_after_wait_{egress.name}, %owner_before_free_{egress.name} : i1"
            )
            lines.append(
                f"      %owner_incremented_{egress.name} = arith.addi "
                f"{current}, %iq_one : i32"
            )
            lines.append(
                f"      %owner_aged_{egress.name} = arith.select "
                f"%owner_counting_{egress.name}, %owner_incremented_{egress.name}, "
                f"{current} : i32"
            )
            lines.append(
                f"      %owner_credit_negative_{egress.name} = arith.subi "
                f"%zero, %owner_credit_{egress.name} : i32"
            )
            current = f"%owner_effective_{egress.name}"
            lines.append(
                f"      {current} = arith.select %owner_credit_ready_{egress.name}, "
                f"%owner_credit_negative_{egress.name}, %owner_aged_{egress.name} : i32"
            )
        egress_effective[egress.name] = current
        egress_free[egress.name] = f"%owner_free_{egress.name}"
        lines.append(
            f"      {egress_free[egress.name]} = arith.cmpi eq, {current}, %zero : i32"
        )

    va_candidates: list[tuple[str, _NoCIngress, _NoCEgress]] = []
    va_by_egress: dict[str, list[int]] = {}
    for egress in egresses:
        for ingress in ingresses:
            route_ready = f"%va_route_{egress.name}_{ingress.name}"
            request = f"%va_request_{egress.name}_{ingress.name}"
            lines.append(
                f"      {route_ready} = arith.andi "
                f"{route_requests[(egress.name, ingress.name)]}, "
                f"{pipe_va_ready[ingress.name]} : i1"
            )
            lines.append(
                f"      {request} = arith.andi {route_ready}, "
                f"{egress_free[egress.name]} : i1"
            )
            va_candidates.append((request, ingress, egress))
            va_by_egress.setdefault(egress.name, []).append(len(va_candidates) - 1)

    va_grants = [f"%va_grant_{index}" for index in range(len(va_candidates))]
    va_rr_next: dict[str, str] = {}
    # Deterministic routing makes every ingress request at most one egress.
    # The input half of a separable input-first allocator therefore has one
    # request; emit the contested output halves independently.  Keeping each
    # ACIR arbiter bounded by the router radix avoids a topology-size-dependent
    # conversion blow-up without changing the grant relation.
    for egress in egresses:
        indices = va_by_egress[egress.name]
        results = [va_grants[index] for index in indices]
        if arbitration == "round_robin":
            pointer = f"%va_rr_pointer_{egress.name}"
            next_pointer = f"%va_rr_next_{egress.name}"
            lines.append(
                f"      {pointer}, %va_rr_valid_{egress.name} = ac.try_recv "
                f"@node{node}_va_rr_{egress.name} : i32"
            )
            lines.append(
                f"      {', '.join(results + [next_pointer])} = "
                f"ac.arbitrate round_robin state {pointer} candidates ["
            )
            va_rr_next[egress.name] = next_pointer
        else:
            lines.append(
                f"      {', '.join(results)} = "
                "ac.arbitrate greedy_fixed_priority candidates ["
            )
        for ordinal, index in enumerate(indices):
            comma = "," if ordinal + 1 != len(indices) else ""
            lines.append(
                f"        {va_candidates[index][0]} uses "
                f"[@node{node}_va_pout_{egress.name}]{comma}"
            )
        request_types = ", ".join("i1" for _ in indices)
        if arbitration == "round_robin":
            lines.append(
                f"      ] : (i32, {request_types}) -> ({request_types}, i32)"
            )
        else:
            lines.append(f"      ] : ({request_types})")

    va_grants_by_ingress: dict[str, list[str]] = {item.name: [] for item in ingresses}
    va_grants_by_egress: dict[str, list[tuple[str, int]]] = {
        item.name: [] for item in egresses
    }
    for index, (_request, ingress, egress) in enumerate(va_candidates):
        va_grants_by_ingress[ingress.name].append(va_grants[index])
        va_grants_by_egress[egress.name].append(
            (va_grants[index], ingresses.index(ingress) + 1)
        )

    sa_candidates: list[tuple[str, _NoCIngress, _NoCEgress]] = []
    for egress in egresses:
        for ingress_index, ingress in enumerate(ingresses, start=1):
            owner_value = f"%owner_value_{egress.name}_{ingress.name}"
            owner_match = f"%owner_match_{egress.name}_{ingress.name}"
            stage_route = f"%sa_stage_route_{egress.name}_{ingress.name}"
            owned_route = f"%sa_owned_route_{egress.name}_{ingress.name}"
            request = f"%sa_request_{egress.name}_{ingress.name}"
            lines.append(f"      {owner_value} = arith.constant {ingress_index} : i32")
            lines.append(
                f"      {owner_match} = arith.cmpi eq, {egress_effective[egress.name]}, "
                f"{owner_value} : i32"
            )
            lines.append(
                f"      {stage_route} = arith.andi "
                f"{route_requests[(egress.name, ingress.name)]}, "
                f"{pipe_sa_ready[ingress.name]} : i1"
            )
            lines.append(f"      {owned_route} = arith.andi {stage_route}, {owner_match} : i1")
            lines.append(
                f"      {request} = arith.andi {owned_route}, "
                f"%writable_{egress.name} : i1"
            )
            sa_candidates.append((request, ingress, egress))

    sa_grants = [f"%sa_grant_{index}" for index in range(len(sa_candidates))]
    # Transfers remain in one resource arbiter so ACIR can prove that the
    # syntactically repeated pop operations for each ingress are exclusive.
    lines.append(
        f"      {', '.join(sa_grants)} = ac.arbitrate greedy_fixed_priority candidates ["
    )
    for index, (request, ingress, egress) in enumerate(sa_candidates):
        comma = "," if index + 1 != len(sa_candidates) else ""
        lines.append(
            f"        {request} uses "
            f"[@node{node}_pin_{ingress.name}, @node{node}_pout_{egress.name}]{comma}"
        )
    lines.append("      ] : (" + ", ".join("i1" for _ in sa_candidates) + ")")
    fires_by_ingress: dict[str, list[str]] = {item.name: [] for item in ingresses}
    fires_by_egress: dict[str, list[str]] = {item.name: [] for item in egresses}
    for index, (_request, ingress, egress) in enumerate(sa_candidates):
        fire = f"%fire_{index}"
        lines.append(
            f"      {fire} = ac.try_transfer @{ingress.queue} to @{egress.queue} "
            f"when {sa_grants[index]} : {payload_type}"
        )
        fires_by_ingress[ingress.name].append(fire)
        fires_by_egress[egress.name].append(fire)

    if timing.wait_for_tail_credit:
        lines.append(f"      %credit_value = arith.constant {timing.credit_delay} : i32")
        for ingress in ingresses:
            if ingress.return_credit_queue is None:
                continue
            departed = emit_any(f"departed_{ingress.name}", fires_by_ingress[ingress.name])
            lines.append(f"      scf.if {departed} {{")
            lines.append(
                f"        %credit_accepted_{ingress.name} = ac.try_send "
                f"@{ingress.return_credit_queue} %credit_value : i32"
            )
            lines.append(
                f"        ac.assert %credit_accepted_{ingress.name}, "
                f'"NoC credit queue overflow on {ingress.return_credit_queue}"'
            )
            lines.append("      }")

    for egress in egresses:
        current = egress_effective[egress.name]
        for ordinal, (grant, owner) in enumerate(va_grants_by_egress[egress.name]):
            owner_constant = f"%owner_grant_value_{egress.name}_{ordinal}"
            updated = f"%owner_after_va_{egress.name}_{ordinal}"
            lines.append(f"      {owner_constant} = arith.constant {owner} : i32")
            lines.append(
                f"      {updated} = arith.select {grant}, {owner_constant}, {current} : i32"
            )
            current = updated
        fired = emit_any(f"owner_fired_{egress.name}", fires_by_egress[egress.name])
        release = (
            "%iq_wait_credit"
            if timing.wait_for_tail_credit and egress.receive_credit_queue is not None
            else "%zero"
        )
        next_state = f"%owner_next_{egress.name}"
        lines.append(
            f"      {next_state} = arith.select {fired}, {release}, {current} : i32"
        )
        lines.append(
            f"      %owner_written_{egress.name} = ac.try_send "
            f"@{egress.vc_state_queue} {next_state} : i32"
        )

    va_ready_value = 100 + timing.vc_alloc_delay
    sa_ready_value = 200 + timing.sw_alloc_delay
    for ingress in ingresses:
        start = f"%pipe_start_{ingress.name}"
        lines.append(
            f"      {start} = arith.andi {pipe_idle[ingress.name]}, "
            f"{ingress_valid_route[ingress.name]} : i1"
        )
        lines.append(
            f"      %pipe_va_value_{ingress.name} = arith.constant {va_ready_value} : i32"
        )
        lines.append(
            f"      %pipe_sa_value_{ingress.name} = arith.constant {sa_ready_value} : i32"
        )
        current = f"%pipe_after_start_{ingress.name}"
        lines.append(
            f"      {current} = arith.select {start}, %pipe_va_value_{ingress.name}, "
            f"{pipe_effective[ingress.name]} : i32"
        )
        va_granted = emit_any(
            f"pipe_va_granted_{ingress.name}", va_grants_by_ingress[ingress.name]
        )
        after_va = f"%pipe_after_va_{ingress.name}"
        lines.append(
            f"      {after_va} = arith.select {va_granted}, "
            f"%pipe_sa_value_{ingress.name}, {current} : i32"
        )
        fired = emit_any(f"pipe_fired_{ingress.name}", fires_by_ingress[ingress.name])
        next_state = f"%pipe_next_{ingress.name}"
        lines.append(
            f"      {next_state} = arith.select {fired}, %zero, {after_va} : i32"
        )
        lines.append(
            f"      %pipe_written_{ingress.name} = ac.try_send "
            f"@node{node}_pipe_{ingress.name} {next_state} : i32"
        )

    for egress_name, next_pointer in va_rr_next.items():
        lines.append(
            f"      %va_rr_written_{egress_name} = ac.try_send "
            f"@node{node}_va_rr_{egress_name} {next_pointer} : i32"
        )
    lines.extend(("      ac.yield_sim", "    }"))
    return lines


def _ring_declaration(call: object) -> list[str]:
    lines, nodes, depth, flow_type, payload_type, payload_size = _noc_header(call)
    parameters = _generator_parameters(call)
    offset = int(parameters["route_offset"])
    route_width = int(parameters["route_width"])
    route_field = str(parameters["route_field"])
    for node in range(nodes):
        lines.append(_queue_line(f"node{node}_local_in", depth, payload_type, payload_size))
        lines.append(_queue_line(f"node{node}_local_out", depth, payload_type, payload_size))
        lines.append(_queue_line(f"link_n{node}_to_n{(node + 1) % nodes}_cw", depth, payload_type, payload_size))
    for node in range(nodes):
        lines.append(f"    ac.flow.import %input{node} to @node{node}_local_in : {flow_type}")
        lines.append(f"    %output{node} = ac.flow.export @node{node}_local_out : {flow_type}")
    for node in range(nodes):
        previous = (node - 1) % nodes
        ingresses = [
            _NoCIngress("cw", f"link_n{previous}_to_n{node}_cw"),
            _NoCIngress("local", f"node{node}_local_in"),
        ]
        egresses = [
            _NoCEgress("local", f"node{node}_local_out"),
            _NoCEgress("cw", f"link_n{node}_to_n{(node + 1) % nodes}_cw"),
        ]
        lines.extend(_resource_line(f"node{node}_pin_{item.name}") for item in ingresses)
        lines.extend(_resource_line(f"node{node}_pout_{item.name}") for item in egresses)
        decode: list[str] = ["      %zero = arith.constant 0 : i32"]
        decode.append(f"      %node_count = arith.constant {nodes} : i32")
        decode.append(f"      %route_mask = arith.constant {(1 << route_width) - 1} : i32")
        if offset:
            decode.append(f"      %route_shift = arith.constant {offset} : i32")
        requests: dict[tuple[str, str], str] = {}
        for ingress in ingresses:
            ingress_name = ingress.name
            source = f"%head_{ingress_name}"
            if route_field:
                source = f"%route_value_{ingress_name}"
                decode.append(
                    f"      {source} = ac.record.get %head_{ingress_name} "
                    f"{{field = {json.dumps(route_field)}}} : ({payload_type}) -> i32"
                )
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
        lines.extend(_noc_scheduler(node, ingresses, egresses, requests, decode, payload_type))
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
    lines, nodes, depth, flow_type, payload_type, payload_size = _noc_header(call)
    parameters = _generator_parameters(call)
    width = int(parameters["width"])
    height = int(parameters["height"])
    offset = int(parameters["route_offset"])
    x_width = int(parameters["route_x_width"])
    y_width = int(parameters["route_y_width"])
    arbitration = str(parameters["arbitration"])
    route_field = str(parameters["route_field"])
    timing = _NoCTiming(
        flow_control=str(parameters["flow_control"]),
        router_pipeline=str(parameters["router_pipeline"]),
        credit_delay=int(parameters["credit_delay"]),
        vc_alloc_delay=int(parameters["vc_alloc_delay"]),
        sw_alloc_delay=int(parameters["sw_alloc_delay"]),
        wait_for_tail_credit=bool(parameters["wait_for_tail_credit"]),
    )
    for node in range(nodes):
        lines.append(_queue_line(f"node{node}_local_in", depth, payload_type, payload_size))
        lines.append(_queue_line(f"node{node}_local_out", depth, payload_type, payload_size))
    for node in range(nodes):
        x, y = node % width, node // width
        for direction in ("north", "east", "south", "west"):
            dx, dy = _MESH_DIRECTIONS[direction]
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                neighbor = ny * width + nx
                lines.append(_queue_line(f"link_n{node}_to_n{neighbor}_{direction}", depth, payload_type, payload_size))
    input_queued = timing.router_pipeline == "input_queued"
    if timing.wait_for_tail_credit:
        for node in range(nodes):
            x, y = node % width, node // width
            for direction in ("north", "east", "south", "west"):
                dx, dy = _MESH_DIRECTIONS[direction]
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor = ny * width + nx
                    credit = f"credit_n{neighbor}_to_n{node}_for_{direction}"
                    lines.append(_queue_line(credit, 2))
    if input_queued:
        for node in range(nodes):
            x, y = node % width, node // width
            lines.append(_queue_line(f"node{node}_vc_local", 2))
            lines.append(_queue_line(f"node{node}_pipe_local", 2))
            for direction in ("north", "east", "south", "west"):
                dx, dy = _MESH_DIRECTIONS[direction]
                if 0 <= x + dx < width and 0 <= y + dy < height:
                    lines.append(_queue_line(f"node{node}_vc_{direction}", 2))
                    lines.append(_queue_line(f"node{node}_pipe_{direction}", 2))
    elif timing.wait_for_tail_credit:
        for node in range(nodes):
            x, y = node % width, node // width
            for direction in ("north", "east", "south", "west"):
                dx, dy = _MESH_DIRECTIONS[direction]
                if 0 <= x + dx < width and 0 <= y + dy < height:
                    lines.append(_queue_line(f"node{node}_vc_{direction}", 2))
    if arbitration == "round_robin" and not input_queued:
        for node in range(nodes):
            x, y = node % width, node // width
            lines.append(_queue_line(f"node{node}_rr_local", 2))
            for direction in ("north", "east", "south", "west"):
                dx, dy = _MESH_DIRECTIONS[direction]
                if 0 <= x + dx < width and 0 <= y + dy < height:
                    lines.append(_queue_line(f"node{node}_rr_{direction}", 2))
    if arbitration == "round_robin" and input_queued:
        for node in range(nodes):
            x, y = node % width, node // width
            lines.append(_queue_line(f"node{node}_va_rr_local", 2))
            for direction in ("north", "east", "south", "west"):
                dx, dy = _MESH_DIRECTIONS[direction]
                if 0 <= x + dx < width and 0 <= y + dy < height:
                    lines.append(_queue_line(f"node{node}_va_rr_{direction}", 2))
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
        ingresses: list[_NoCIngress] = []
        for name in ("north", "east", "south", "west"):
            if name not in inbound:
                continue
            source_node = int(inbound[name].split("_n", 1)[1].split("_to", 1)[0])
            source_direction = opposite[name]
            credit = (
                f"credit_n{node}_to_n{source_node}_for_{source_direction}"
                if timing.wait_for_tail_credit
                else None
            )
            ingresses.append(_NoCIngress(name, inbound[name], credit))
        ingresses.append(_NoCIngress("local", f"node{node}_local_in"))
        egresses: list[_NoCEgress] = [
            _NoCEgress(
                "local",
                f"node{node}_local_out",
                f"node{node}_vc_local" if input_queued else None,
            )
        ]
        for name in ("north", "east", "south", "west"):
            if name not in outbound:
                continue
            neighbor = node + _MESH_DIRECTIONS[name][1] * width + _MESH_DIRECTIONS[name][0]
            credit = (
                f"credit_n{neighbor}_to_n{node}_for_{name}"
                if timing.wait_for_tail_credit
                else None
            )
            state = (
                f"node{node}_vc_{name}"
                if input_queued or timing.wait_for_tail_credit
                else None
            )
            egresses.append(_NoCEgress(name, outbound[name], state, credit))
        lines.extend(_resource_line(f"node{node}_pin_{item.name}") for item in ingresses)
        lines.extend(_resource_line(f"node{node}_pout_{item.name}") for item in egresses)
        if input_queued:
            lines.extend(
                _resource_line(f"node{node}_va_pout_{item.name}") for item in egresses
            )
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
        for ingress in ingresses:
            ingress_name = ingress.name
            source = f"%head_{ingress_name}"
            if route_field:
                source = f"%route_value_{ingress_name}"
                decode.append(
                    f"      {source} = ac.record.get %head_{ingress_name} "
                    f"{{field = {json.dumps(route_field)}}} : ({payload_type}) -> i32"
                )
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
            for egress in egresses:
                requests[(egress.name, ingress_name)] = f"%route_{egress.name}_{ingress_name}"
        scheduler = _noc_iq_scheduler if input_queued else _noc_scheduler
        lines.extend(
            scheduler(
                node,
                ingresses,
                egresses,
                requests,
                decode,
                payload_type,
                arbitration=arbitration,
                timing=timing,
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


def _flow_boundary_declarations(program: NormalizedProgram, records: tuple[RecordDefinition, ...]) -> list[str]:
    lines: list[str] = []
    for boundary in program.flow_boundaries:
        symbol = _boundary_symbol(boundary.direction, boundary.value)
        flow_types = tuple(
            f"!ac.flow<{_payload_acir(payload, records)}, @{protocol}>"
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
                f"    ac.queue @{queue_name} payload {_payload_acir(payload, records)} entries {depth} ordering \"fifo\" "
                f"protocol @{protocol} ownership \"exclusive\" id \"{queue_name}\" path \"{queue_name}\""
            )
        for vc, (queue_name, payload, protocol, _depth) in enumerate(boundary.queues):
            flow_type = f"!ac.flow<{_payload_acir(payload, records)}, @{protocol}>"
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


def _component_declarations(program: NormalizedProgram, records: tuple[RecordDefinition, ...]) -> list[str]:
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
    lines.extend(_flow_boundary_declarations(program, records))
    return lines


def _process_arguments(arguments: tuple[str, ...]) -> tuple[list[str], dict[str, str]]:
    positional: list[str] = []
    keywords: dict[str, str] = {}
    for argument in arguments:
        if "=" in argument:
            name, value = argument.split("=", 1)
            keywords[name] = value
        else:
            positional.append(argument)
    return positional, keywords


def _static_string(value: str, context: str) -> str:
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError) as error:
        raise ValueError(f"ACPY-PROCESS-003: {context} must be a static string") from error
    if type(parsed) is not str or not parsed:
        raise ValueError(f"ACPY-PROCESS-003: {context} must be a non-empty static string")
    return parsed


def _emit_process(
    process: ProcessProgram, kind: str, records: tuple[RecordDefinition, ...]
) -> list[str]:
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
    value_types: dict[str, str] = {}

    def emit_value(expression: str, expected: str, index: int, label: str) -> str:
        if _SYMBOL.fullmatch(expression):
            actual = value_types.get(expression)
            if actual is not None and actual != expected:
                raise ValueError(
                    f"ACPY-PROCESS-003: {expression!r} has type {actual}, expected {expected}"
                )
            return f"%{expression}"
        try:
            literal = ast.literal_eval(expression)
        except (ValueError, SyntaxError) as error:
            raise ValueError("ACPY-PROCESS-003: Packet fields require SSA names or scalar literals") from error
        name = f"%{label}_{index}_{len(lines)}"
        if expected.startswith("i") and expected[1:].isdigit() and type(literal) is int:
            lines.append(f"      {name} = arith.constant {literal} : {expected}")
            return name
        if expected in {"f32", "f64"} and type(literal) in {int, float}:
            lines.append(f"      {name} = arith.constant {float(literal)} : {expected}")
            return name
        raise ValueError(f"ACPY-PROCESS-003: literal is incompatible with {expected}")

    for index, action in enumerate(block.actions):
        if action.operation.startswith("record_create:"):
            if not isinstance(action.result, str):
                raise ValueError("ACPY-PROCESS-003: record construction requires one result")
            name = action.operation.partition(":")[2]
            record = next((item for item in records if item.name == name), None)
            if record is None:
                raise ValueError(f"ACPY-TYPE-PACKET: unknown record {name!r}")
            positional, keywords = _process_arguments(action.arguments)
            if positional or set(keywords) != {field.name for field in record.fields}:
                raise ValueError(
                    f"ACPY-PROCESS-003: {name} constructor requires every field by name"
                )
            operands = [
                emit_value(keywords[field.name], field.acir_type, index, field.name)
                for field in record.fields
            ]
            fields = ", ".join(json.dumps(field.name) for field in record.fields)
            types = ", ".join(field.acir_type for field in record.fields)
            lines.append(
                f"      %{action.result} = ac.record.create {', '.join(operands)} "
                f"{{field_names = [{fields}]}} : ({types}) -> {record.acir_type}"
            )
            value_types[action.result] = record.acir_type
            continue
        if action.operation == "record_get":
            positional, keywords = _process_arguments(action.arguments)
            if len(positional) != 1 or set(keywords) != {"field"} or not isinstance(action.result, str):
                raise ValueError("ACPY-PROCESS-003: record_get requires record and field")
            record_type = value_types.get(positional[0])
            record = next((item for item in records if item.acir_type == record_type), None)
            field_name = _static_string(keywords["field"], "record field")
            field = next((item for item in record.fields if item.name == field_name), None) if record else None
            if field is None:
                raise ValueError(f"ACPY-PROCESS-003: unknown record field {field_name!r}")
            lines.append(
                f"      %{action.result} = ac.record.get %{positional[0]} "
                f"{{field = {json.dumps(field_name)}}} : ({record.acir_type}) -> {field.acir_type}"
            )
            value_types[action.result] = field.acir_type
            continue
        if action.operation == "record_with":
            positional, keywords = _process_arguments(action.arguments)
            if len(positional) != 1 or set(keywords) != {"field", "value"} or not isinstance(action.result, str):
                raise ValueError("ACPY-PROCESS-003: record_with requires record, field, and value")
            record_type = value_types.get(positional[0])
            record = next((item for item in records if item.acir_type == record_type), None)
            field_name = _static_string(keywords["field"], "record field")
            field = next((item for item in record.fields if item.name == field_name), None) if record else None
            if field is None or record is None:
                raise ValueError(f"ACPY-PROCESS-003: unknown record field {field_name!r}")
            replacement = emit_value(keywords["value"], field.acir_type, index, "with")
            lines.append(
                f"      %{action.result} = ac.record.with %{positional[0]}, {replacement} "
                f"{{field = {json.dumps(field_name)}}} : ({record.acir_type}, {field.acir_type}) -> {record.acir_type}"
            )
            value_types[action.result] = record.acir_type
            continue
        if action.operation == "packet_serialize":
            positional, keywords = _process_arguments(action.arguments)
            if len(positional) != 1 or keywords or not isinstance(action.result, str):
                raise ValueError("ACPY-PROCESS-003: packet_serialize requires one Packet")
            record_type = value_types.get(positional[0])
            record = next(
                (item for item in records if item.kind == "packet" and item.acir_type == record_type),
                None,
            )
            if record is None:
                raise ValueError("ACPY-PROCESS-003: packet_serialize operand is not a Packet")
            result_type = f"!ac.vector<{record.size} x i8>"
            lines.append(
                f"      %{action.result} = ac.packet.serialize %{positional[0]} "
                f"{{packet = @types::@{record.name}}} : ({record.acir_type}) -> {result_type}"
            )
            value_types[action.result] = result_type
            continue
        if action.operation == "packet_deserialize":
            positional, keywords = _process_arguments(action.arguments)
            if len(positional) != 2 or keywords or not isinstance(action.result, str):
                raise ValueError("ACPY-PROCESS-003: packet_deserialize requires Packet type and bytes")
            record = next(
                (item for item in records if item.kind == "packet" and item.name == positional[0]),
                None,
            )
            bytes_type = value_types.get(positional[1])
            if record is None or bytes_type != f"!ac.vector<{record.size} x i8>":
                raise ValueError("ACPY-PROCESS-003: packet_deserialize type or byte width mismatch")
            lines.append(
                f"      %{action.result} = ac.packet.deserialize %{positional[1]} "
                f"{{packet = @types::@{record.name}}} : ({bytes_type}) -> {record.acir_type}"
            )
            value_types[action.result] = record.acir_type
            continue
        if action.operation not in {"try_send", "try_recv"} or not action.arguments:
            raise ValueError("ACPY-VERIFY-001: only typed single-block Queue actions are supported")
        queue = queue_names.get(action.arguments[0])
        if queue is None:
            raise ValueError("ACPY-VERIFY-001: Queue action target is not root-owned")
        queue_name, payload_type = queue
        if action.operation == "try_send":
            if len(action.arguments) != 2:
                raise ValueError("ACPY-PROCESS-003: try_send requires queue and payload")
            payload = action.arguments[1]
            if re.fullmatch(r"-?[0-9]+", payload):
                if payload_type != "i32":
                    raise ValueError("ACPY-PROCESS-003: only i32 Queue accepts an integer literal")
                value = f"%send_value_{index}"
                lines.append(f"      {value} = arith.constant {payload} : i32")
            elif _SYMBOL.fullmatch(payload):
                value = f"%{payload}"
                expected = _payload_acir(payload_type, records)
                if value_types.get(payload) not in {None, expected}:
                    raise ValueError("ACPY-PROCESS-003: try_send payload type mismatch")
            else:
                raise ValueError("ACPY-PROCESS-003: try_send payload must be one SSA value")
            result = (
                f"%{action.result}"
                if isinstance(action.result, str)
                else f"%send_accepted_{index}"
            )
            queue_type = _payload_acir(payload_type, records)
            lines.append(f"      {result} = ac.try_send @{queue_name} {value} : {queue_type}")
            if isinstance(action.result, str):
                value_types[action.result] = "i1"
        else:
            if len(action.arguments) != 1:
                raise ValueError("ACPY-PROCESS-003: try_recv requires one queue")
            if isinstance(action.result, tuple):
                value, received = (f"%{name}" for name in action.result)
            elif isinstance(action.result, str):
                value, received = f"%recv_value_{index}", f"%{action.result}"
            else:
                value, received = f"%recv_value_{index}", f"%recv_received_{index}"
            queue_type = _payload_acir(payload_type, records)
            lines.append(f"      {value}, {received} = ac.try_recv @{queue_name} : {queue_type}")
            value_types[value.removeprefix("%")] = queue_type
            value_types[received.removeprefix("%")] = "i1"
    lines.extend(("      ac.yield_sim", "    }"))
    return lines


def lower_to_acir(
    program: NormalizedProgram,
    document: AcpyDocument,
    *,
    system_name: str,
    processes: tuple[tuple[ProcessProgram, str], ...] = (),
    records: tuple[RecordDefinition, ...] = (),
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
    lines.extend(_emit_type_scope(records))
    flow_specs: set[tuple[str, str]] = set()
    for argument in program.arguments:
        if (spec := _flow_spec(argument.type_key)) is not None:
            flow_specs.add(spec)
        elif (bundle := _bundle_spec(argument.type_key)) is not None:
            flow_specs.add(bundle[:2])
    for call in program.calls:
        if call.schema.generator is not None:
            parameters = dict(call.static_arguments)
            flow_specs.add((str(parameters["payload"]), "ready_valid"))
            if call.schema.identity == "ac.std.MeshNoC" and (
                parameters.get("arbitration") == "round_robin"
                or parameters.get("wait_for_tail_credit") is True
                or parameters.get("router_pipeline") == "input_queued"
            ):
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
            payload_type = _payload_acir(payload, records)
            lines.append(
                f"    ac.event @transfer_{index} from @sender to @receiver payload {payload_type} action \"offer\""
            )
        lines.extend(
            (
                '    ac.guarantee "ordering" = "fifo"',
                '    ac.guarantee "backpressure" = "capacity"',
                "  }",
            )
        )
    declarations = _component_declarations(program, records)
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
        flow_type = f"!ac.flow<{_payload_acir(payload, records)}, @{protocol}>"
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
        return_types_list.extend(
            f"!ac.flow<{_payload_acir(payload, records)}, @{protocol}>" for _ in range(width)
        )
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
    host_inputs = dict(program.host_inputs)
    host_outputs = dict(program.host_outputs)
    for queue_name in sorted(set(host_inputs) | set(host_outputs), key=utf16_sort_key):
        if queue_name not in queue_specs:
            raise ValueError(
                f"ACPY-HOST-001: host queue {queue_name!r} must participate in a Flow boundary"
            )
        payload, protocol, depth = queue_specs[queue_name]
        declared_queues.add(queue_name)
        payload_type = _payload_acir(payload, records)
        byte_capacity = _packet_size(payload, records)
        bytes_text = f" bytes {depth * byte_capacity}" if byte_capacity is not None else ""
        attributes = []
        if queue_name in host_inputs:
            attributes.append(f"ac.host_input = {json.dumps(host_inputs[queue_name])}")
        if queue_name in host_outputs:
            attributes.append(f"ac.host_output = {json.dumps(host_outputs[queue_name])}")
        lines.append(
            f"    ac.queue @{queue_name} payload {payload_type} entries {depth}{bytes_text} ordering \"fifo\" "
            f"protocol @{protocol} ownership \"exclusive\" id \"{queue_name}\" path \"{queue_name}\" "
            f"{{{', '.join(attributes)}}}"
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
                f"    ac.queue @{queue_name} payload {_payload_acir(payload, records)} entries {depth} ordering \"fifo\" "
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
            f"!ac.flow<{_payload_acir(payload, records)}, @{protocol}>"
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
            flow_type = f"!ac.flow<{_generator_payload_type(call)}, @ready_valid>"
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
        lines.extend(_emit_process(process, kind, records))
    for boundary in program.flow_boundaries:
        if boundary.direction != "import":
            continue
        source = names[boundary.value.name]
        if not isinstance(source, tuple) or len(source) != len(boundary.queues):
            raise ValueError("ACPY-FLOW-007: Queue tuple and FlowBundle shape must match")
        flow_types = tuple(
            f"!ac.flow<{_payload_acir(payload, records)}, @{protocol}>"
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
