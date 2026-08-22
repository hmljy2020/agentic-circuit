"""Source-ordered assignment, call, and SSA normalization."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from ._canonical_json import canonical_json_bytes, sha256_bytes
from ._diagnostics import Diagnostic, DiagnosticBag, RelatedLocation, SourceSpan
from ._frontend import CapturedProgram
from ._naming import StableNameAllocator, StableNameError
from ._resolve import (
    ResolvedCall,
    PortBinding,
    ResultBinding,
    ResolutionError,
    UnresolvedCall,
    ValueCategory,
    ValueVersion,
    resolve_call,
)
from ._schemas import ComponentSchema, signature_for
from ._static_eval import StaticEnvironment, StaticValue, evaluate_static
from ._records import collect_record_definitions, record_by_name


@dataclass(frozen=True, slots=True)
class NormalizedScopeRegion:
    key: str
    name: str
    parent: str | None
    call_keys: tuple[str, ...]
    value_names: tuple[str, ...]
    source: SourceSpan


@dataclass(frozen=True, slots=True)
class FlowBoundary:
    value: ValueVersion
    direction: str
    queues: tuple[tuple[str, str, str, int], ...]


@dataclass(frozen=True, slots=True)
class NormalizedProgram:
    definition: str
    arguments: tuple[ValueVersion, ...]
    values: tuple[ValueVersion, ...]
    calls: tuple[ResolvedCall, ...]
    returns: tuple[ValueVersion, ...]
    diagnostics: tuple[Diagnostic, ...]
    scopes: tuple[NormalizedScopeRegion, ...] = ()
    captures: tuple[ValueVersion, ...] = ()
    flow_boundaries: tuple[FlowBoundary, ...] = ()
    host_inputs: tuple[tuple[str, str], ...] = ()
    host_outputs: tuple[tuple[str, str], ...] = ()

    def value_names(self) -> tuple[str, ...]:
        return tuple(value.name for value in self.values)

    def return_names(self) -> tuple[str, ...]:
        return tuple(value.name for value in self.returns)


def _span(path: str, node: ast.AST) -> SourceSpan:
    return SourceSpan(
        path,
        node.lineno,
        node.col_offset + 1,
        node.end_lineno or node.lineno,
        (node.end_col_offset or node.col_offset) + 1,
    )


def _annotation_category(annotation: ast.expr | None) -> ValueCategory:
    value = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    if isinstance(value, ast.Name):
        return {
            "Static": "static",
            "Flow": "flow",
            "FlowBundle": "flow_bundle",
            "Endpoint": "endpoint",
            "ResourceRef": "resource",
        }.get(value.id, "static")
    return "static"


def _result_category(type_key: str) -> ValueCategory:
    lowered = type_key.lower()
    if "flowbundle" in lowered:
        return "flow_bundle"
    if "flow" in lowered:
        return "flow"
    if "endpoint" in lowered:
        return "endpoint"
    if "resource" in lowered:
        return "resource"
    return "result"


def _bundle_spec_from_key(type_key: str) -> tuple[str, str, int] | None:
    try:
        expression = ast.parse(type_key, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expression, ast.Subscript) or not isinstance(expression.value, ast.Name):
        return None
    elements = expression.slice.elts if isinstance(expression.slice, ast.Tuple) else []
    if (
        expression.value.id != "FlowBundle"
        or len(elements) != 3
        or not isinstance(elements[0], ast.Name)
        or not isinstance(elements[1], ast.Name)
        or not isinstance(elements[2], ast.Constant)
        or type(elements[2].value) is not int
    ):
        return None
    return elements[0].id, elements[1].id, elements[2].value


class _Normalizer:
    def __init__(
        self,
        captured: CapturedProgram,
        definition: str,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self._captured = captured
        self._definition = definition
        self._node = node
        self._diagnostics = DiagnosticBag()
        self._versions: dict[str, int] = {}
        self._current: dict[str, ValueVersion] = {}
        self._values: list[ValueVersion] = []
        self._calls: list[ResolvedCall] = []
        self._returns: tuple[ValueVersion, ...] = ()
        self._scopes: list[NormalizedScopeRegion | None] = []
        self._scope_stack: list[str] = []
        self._names = StableNameAllocator()
        self._static_values = dict(captured.static_arguments)
        self._consumed_bundles: dict[str, SourceSpan] = {}
        self._bundle_outputs: dict[str, tuple[str, int, SourceSpan]] = {}
        self._captures: list[ValueVersion] = []
        self._flow_boundaries: list[FlowBoundary] = []
        self._host_inputs: list[tuple[str, str]] = []
        self._host_outputs: list[tuple[str, str]] = []
        symbols = dict(captured.symbols)
        from ._resources import QueueSpec
        from ._types import FlowBundle
        queues_by_name: dict[str, QueueSpec] = {}
        host_inputs_by_queue: dict[str, str] = {}
        host_outputs_by_queue: dict[str, str] = {}
        for symbolic in symbols.values():
            candidates = symbolic if isinstance(symbolic, (tuple, list)) else (symbolic,)
            for candidate in candidates:
                if isinstance(candidate, QueueSpec):
                    queues_by_name[candidate.name] = candidate
                    if candidate.host_input is not None:
                        host_inputs_by_queue[candidate.name] = candidate.host_input
                    if candidate.host_output is not None:
                        host_outputs_by_queue[candidate.name] = candidate.host_output
        self._host_inputs = sorted(host_inputs_by_queue.items())
        if len({host_name for _queue, host_name in self._host_inputs}) != len(
            self._host_inputs
        ):
            raise ResolutionError("ACPY-HOST-001: host input names must be unique")
        self._host_outputs = sorted(host_outputs_by_queue.items())
        if len({host_name for _queue, host_name in self._host_outputs}) != len(
            self._host_outputs
        ):
            raise ResolutionError("ACPY-HOST-001: host output names must be unique")
        for symbol_name, symbolic in captured.symbols:
            if not isinstance(symbolic, FlowBundle) or len(symbolic.shape) != 1:
                continue
            protocol_name = getattr(symbolic.protocol, "__name__", "ReadyValid")
            queue_specs = []
            for leaf in symbolic.leaves:
                queue_name = leaf.stable_name.removesuffix(".flow")
                queue = queues_by_name.get(queue_name)
                if queue is None:
                    raise ResolutionError(f"exported Flow queue {queue_name!r} is not captured")
                queue_specs.append((queue.name, queue.payload_type, queue.protocol, queue.depth))
            payloads = {item[1] for item in queue_specs}
            if len(payloads) != 1:
                raise ResolutionError("exported Flow queues must share one payload")
            payload = next(iter(payloads))
            payload_key = "int" if payload == "i32" else payload
            value = ValueVersion(
                symbol_name,
                0,
                "flow_bundle",
                f"FlowBundle[{payload_key}, {protocol_name}, {symbolic.shape[0]}]",
                "boundary:export",
                "borrowed",
            )
            self._current[symbol_name] = value
            self._captures.append(value)
            self._flow_boundaries.append(FlowBoundary(value, "export", tuple(queue_specs)))
        arguments: list[ValueVersion] = []
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            value = ValueVersion(
                source_name=argument.arg,
                version=0,
                category=_annotation_category(argument.annotation),
                type_key=ast.unparse(argument.annotation) if argument.annotation else "unknown",
                producer=None,
            )
            arguments.append(value)
            self._current[argument.arg] = value
        self._arguments = tuple(arguments)

    def _error(
        self,
        code: str,
        message: str,
        node: ast.AST,
        related: tuple[RelatedLocation, ...] = (),
    ) -> None:
        self._diagnostics.add(
            Diagnostic(
                stage="ssa-normalization",
                code=code,
                severity="error",
                message=message,
                source=_span(self._captured.source.path, node),
                related=related,
            )
        )

    def _new_value(
        self,
        source_name: str,
        category: ValueCategory,
        type_key: str,
        producer: str,
        ownership: str = "borrowed",
    ) -> ValueVersion:
        version = self._versions.get(source_name, 0)
        self._versions[source_name] = version + 1
        value = ValueVersion(
            source_name, version, category, type_key, producer, ownership
        )
        self._current[source_name] = value
        self._values.append(value)
        return value

    def _value(self, expression: ast.expr) -> ValueVersion:
        if not isinstance(expression, ast.Name) or expression.id not in self._current:
            raise ResolutionError("ACPY-SYMBOL-001: expression is not a bound value")
        return self._current[expression.id]

    def _static(self, expression: ast.expr | object) -> StaticValue:
        if isinstance(expression, ast.expr):
            return evaluate_static(
                expression, StaticEnvironment(self._static_values)
            )
        return expression

    def _bound_candidate(
        self, node: ast.Call, schema: ComponentSchema
    ) -> tuple[
        tuple[tuple[str, ValueVersion], ...],
        tuple[tuple[str, StaticValue], ...],
        str | None,
    ]:
        if any(keyword.arg is None for keyword in node.keywords):
            raise ResolutionError("keyword unpacking is not supported")
        signature = signature_for(schema)
        keyword_values = {
            keyword.arg: keyword.value
            for keyword in node.keywords
            if keyword.arg is not None
        }
        try:
            bound = signature.bind(*node.args, **keyword_values)
        except TypeError as error:
            raise ResolutionError(str(error)) from error
        bound.apply_defaults()
        ports = tuple(
            (port.name, self._value(bound.arguments[port.name]))
            for port in schema.ports
        )
        static_arguments = tuple(
            (parameter.name, self._static(bound.arguments[parameter.name]))
            for parameter in schema.parameters
        )
        instance_name = self._static(bound.arguments["name"])
        if instance_name is not None and type(instance_name) is not str:
            raise ResolutionError("instance name must be a static string")
        return ports, static_arguments, instance_name

    def _target_names(self, target: ast.expr) -> tuple[str, ...]:
        if isinstance(target, ast.Name):
            return (target.id,)
        if isinstance(target, (ast.Tuple, ast.List)) and all(
            isinstance(item, ast.Name) for item in target.elts
        ):
            return tuple(item.id for item in target.elts)
        raise ResolutionError("assignment target must be a name or name tuple")

    def _context_target_names(self, target: ast.expr | None, instance: str) -> tuple[str, ...]:
        if target is None or not isinstance(target, (ast.Tuple, ast.List)):
            raise ResolutionError(
                f"{instance} requires direct assignment to a non-empty flat tuple/list"
            )
        if not target.elts:
            raise ResolutionError(f"{instance} requires at least one output target")
        names: list[str] = []
        for item in target.elts:
            if isinstance(item, ast.Starred):
                raise ResolutionError(f"{instance} does not allow a starred output target")
            if not isinstance(item, ast.Name):
                kind = "nested target" if isinstance(item, (ast.Tuple, ast.List)) else type(item).__name__
                raise ResolutionError(f"{instance} output target must be a simple name, not {kind}")
            names.append(item.id)
        if len(names) != len(set(names)):
            raise ResolutionError(f"{instance} output target names must be distinct")
        return tuple(names)

    def _consume_bundle(self, value: ValueVersion, node: ast.AST) -> None:
        if value.category != "flow_bundle":
            raise ResolutionError(
                f"input {value.source_name!r} must be a FlowBundle[int, ReadyValid]"
            )
        previous = self._consumed_bundles.get(value.name)
        if previous is not None:
            raise ResolutionError(
                f"ACPY-FLOW-006: FlowBundle {value.source_name!r} is consumed more than once"
            )
        self._consumed_bundles[value.name] = _span(self._captured.source.path, node)

    def _context_call(
        self, target: ast.expr | None, node: ast.Call, schema: ComponentSchema
    ) -> None:
        source = _span(self._captured.source.path, node)
        display_name = schema.identity.rsplit(".", 1)[-1]
        diagnostic_name = display_name
        for keyword in node.keywords:
            if (
                keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and type(keyword.value.value) is str
            ):
                diagnostic_name = f"{display_name} instance {keyword.value.value!r}"
                break
        inferred_outputs = (
            len(target.elts) if isinstance(target, (ast.Tuple, ast.List)) else None
        )
        try:
            target_names = self._context_target_names(target, display_name)
            if any(keyword.arg is None for keyword in node.keywords):
                raise ResolutionError("keyword unpacking is not supported")
            signature = signature_for(schema)
            keyword_values = {
                keyword.arg: keyword.value for keyword in node.keywords if keyword.arg is not None
            }
            bound = signature.bind(*node.args, **keyword_values)
            bound.apply_defaults()
            inputs_expression = bound.arguments["inputs"]
            if not isinstance(inputs_expression, (ast.Tuple, ast.List)) or not inputs_expression.elts:
                raise ResolutionError(f"{display_name} inputs must be a non-empty fixed tuple/list")
            if any(not isinstance(item, ast.Name) for item in inputs_expression.elts):
                raise ResolutionError(f"{display_name} inputs must name individual node FlowBundles")
            input_values = tuple(self._value(item) for item in inputs_expression.elts)
            if len({value.name for value in input_values}) != len(input_values):
                raise ResolutionError(f"ACPY-FLOW-006: {display_name} inputs repeat one FlowBundle")
            static_values = {
                parameter.name: self._static(bound.arguments[parameter.name])
                for parameter in schema.parameters
            }
            explicit_name = self._static(bound.arguments["name"])
            if explicit_name is not None and (type(explicit_name) is not str or not explicit_name):
                raise ResolutionError("instance name must be a non-empty static string")
            input_ports = len(input_values)
            output_ports = len(target_names)
            bundle_specs = tuple(_bundle_spec_from_key(value.type_key) for value in input_values)
            if any(spec is None for spec in bundle_specs):
                raise ResolutionError(f"{display_name} inputs must be typed FlowBundles")
            exact_bundle_specs = tuple(spec for spec in bundle_specs if spec is not None)
            payload_fields: dict[str, StaticValue] = {}
            payload_keys = {spec[0] for spec in exact_bundle_specs}
            protocols = {spec[1] for spec in exact_bundle_specs}
            shapes = {spec[2] for spec in exact_bundle_specs}
            if len(payload_keys) != 1 or protocols != {"ReadyValid"}:
                raise ResolutionError(f"{display_name} inputs must share one ready-valid payload")
            payload_key = next(iter(payload_keys))
            if schema.identity == "ac.std.Crossbar":
                integers = (
                    "virtual_channels", "ingress_depth", "egress_depth", "route_offset", "route_width"
                )
                if any(type(static_values[name]) is not int for name in integers):
                    raise ResolutionError("Crossbar numeric parameters must be static integers")
                vc = static_values["virtual_channels"]
                ingress = static_values["ingress_depth"]
                egress = static_values["egress_depth"]
                offset = static_values["route_offset"]
                route_width = static_values["route_width"]
                assert isinstance(vc, int) and isinstance(ingress, int) and isinstance(egress, int)
                assert isinstance(offset, int) and isinstance(route_width, int)
                if vc < 1:
                    raise ResolutionError("Crossbar virtual_channels must be >= 1")
                if ingress < 1 or egress < 1:
                    raise ResolutionError("Crossbar ingress_depth and egress_depth must be >= 1")
                if offset < 0 or route_width < 1 or offset + route_width > 32:
                    raise ResolutionError("Crossbar route slice must satisfy 0 <= offset and offset + width <= 32")
                if static_values["policy"] != "greedy_fixed_priority":
                    raise ResolutionError("Crossbar policy must be 'greedy_fixed_priority'")
                if output_ports > 2**route_width:
                    raise ResolutionError("Crossbar output count exceeds route_width encoding")
                if input_ports * output_ports * vc > 4096:
                    raise ResolutionError("Crossbar input_ports * output_ports * virtual_channels exceeds 4096")
                topology_fields: dict[str, StaticValue] = {}
                if payload_key != "int" or shapes != {vc}:
                    raise ResolutionError(
                        "Crossbar inputs must have FlowBundle[int, ReadyValid] leaves"
                    )
            elif schema.identity in {"ac.std.RingNoC", "ac.std.MeshNoC"}:
                vc = 1
                numeric = ("queue_depth", "route_offset")
                if schema.identity == "ac.std.MeshNoC":
                    numeric += (
                        "width",
                        "height",
                        "virtual_channels",
                        "link_latency",
                        "credit_delay",
                        "vc_alloc_delay",
                        "sw_alloc_delay",
                        "input_speedup",
                        "output_speedup",
                    )
                if any(type(static_values[name]) is not int for name in numeric):
                    raise ResolutionError(f"{display_name} numeric parameters must be static integers")
                queue_depth = static_values["queue_depth"]
                offset = static_values["route_offset"]
                assert isinstance(queue_depth, int) and isinstance(offset, int)
                if input_ports != output_ports:
                    raise ResolutionError(f"{display_name} input and output node counts must match")
                if not 1 <= queue_depth <= 64:
                    raise ResolutionError(f"{display_name} queue_depth must be in [1, 64]")
                if offset < 0:
                    raise ResolutionError(f"{display_name} route_offset must be >= 0")
                if shapes != {1}:
                    raise ResolutionError(f"{display_name} inputs must have shape (1,)")
                route_field = static_values["route_field"]
                if type(route_field) is not str:
                    raise ResolutionError(f"{display_name} route_field must be a static string")
                if schema.identity == "ac.std.RingNoC":
                    if static_values["arbitration"] != "greedy_fixed_priority":
                        raise ResolutionError(
                            "RingNoC arbitration must be 'greedy_fixed_priority'"
                        )
                    if not 2 <= input_ports <= 16:
                        raise ResolutionError("RingNoC node count must be in [2, 16]")
                    if static_values["routing"] != "clockwise":
                        raise ResolutionError("RingNoC routing must be 'clockwise'")
                    route_width = max(1, (input_ports - 1).bit_length())
                    topology_fields = {
                        "topology": "ring",
                        "nodes": input_ports,
                        "route_width": route_width,
                    }
                else:
                    mesh_width = static_values["width"]
                    mesh_height = static_values["height"]
                    mesh_vcs = static_values["virtual_channels"]
                    link_latency = static_values["link_latency"]
                    input_speedup = static_values["input_speedup"]
                    output_speedup = static_values["output_speedup"]
                    credit_delay = static_values["credit_delay"]
                    vc_alloc_delay = static_values["vc_alloc_delay"]
                    sw_alloc_delay = static_values["sw_alloc_delay"]
                    wait_for_tail_credit = static_values["wait_for_tail_credit"]
                    assert isinstance(mesh_width, int) and isinstance(mesh_height, int)
                    assert isinstance(mesh_vcs, int) and isinstance(link_latency, int)
                    assert isinstance(input_speedup, int) and isinstance(output_speedup, int)
                    assert isinstance(credit_delay, int) and isinstance(vc_alloc_delay, int)
                    assert isinstance(sw_alloc_delay, int)
                    if not 1 <= mesh_width <= 4 or not 1 <= mesh_height <= 4:
                        raise ResolutionError("MeshNoC width and height must be in [1, 4]")
                    if mesh_width * mesh_height != input_ports:
                        raise ResolutionError("MeshNoC width * height must equal node count")
                    if mesh_vcs != 1:
                        raise ResolutionError("MeshNoC virtual_channels must be exactly 1")
                    flow_control = static_values["flow_control"]
                    router_pipeline = static_values["router_pipeline"]
                    if flow_control not in {"ready_valid", "credit"}:
                        raise ResolutionError(
                            "MeshNoC flow_control must be 'ready_valid' or 'credit'"
                        )
                    if link_latency != 1:
                        raise ResolutionError("MeshNoC link_latency must be exactly 1")
                    if router_pipeline not in {"single_stage_elastic", "input_queued"}:
                        raise ResolutionError(
                            "MeshNoC router_pipeline must be 'single_stage_elastic' or 'input_queued'"
                        )
                    if not 0 <= credit_delay <= 64:
                        raise ResolutionError("MeshNoC credit_delay must be in [0, 64]")
                    if not 0 <= vc_alloc_delay <= 64 or not 0 <= sw_alloc_delay <= 64:
                        raise ResolutionError(
                            "MeshNoC allocation delays must be in [0, 64]"
                        )
                    if type(wait_for_tail_credit) is not bool:
                        raise ResolutionError(
                            "MeshNoC wait_for_tail_credit must be a static boolean"
                        )
                    if flow_control == "ready_valid":
                        if router_pipeline != "single_stage_elastic":
                            raise ResolutionError(
                                "MeshNoC ready_valid requires router_pipeline='single_stage_elastic'"
                            )
                        if credit_delay or vc_alloc_delay or sw_alloc_delay or wait_for_tail_credit:
                            raise ResolutionError(
                                "MeshNoC ready_valid does not accept credit or allocation timing"
                            )
                    elif router_pipeline == "single_stage_elastic":
                        if vc_alloc_delay or sw_alloc_delay:
                            raise ResolutionError(
                                "MeshNoC single_stage_elastic requires zero allocation delays"
                            )
                    else:
                        if vc_alloc_delay < 1 or sw_alloc_delay < 1:
                            raise ResolutionError(
                                "MeshNoC input_queued requires positive VC and switch allocation delays"
                            )
                    if not wait_for_tail_credit and credit_delay:
                        raise ResolutionError(
                            "MeshNoC credit_delay requires wait_for_tail_credit=True"
                        )
                    if input_speedup != 1 or output_speedup != 1:
                        raise ResolutionError(
                            "MeshNoC input_speedup and output_speedup must be exactly 1"
                        )
                    if static_values["routing"] != "xy":
                        raise ResolutionError("MeshNoC routing must be 'xy'")
                    if static_values["arbitration"] not in {
                        "greedy_fixed_priority",
                        "round_robin",
                    }:
                        raise ResolutionError(
                            "MeshNoC arbitration must be 'greedy_fixed_priority' or 'round_robin'"
                        )
                    route_x_width = max(1, (mesh_width - 1).bit_length())
                    route_y_width = max(1, (mesh_height - 1).bit_length())
                    route_width = route_x_width + route_y_width
                    topology_fields = {
                        "topology": "mesh",
                        "nodes": input_ports,
                        "route_x_width": route_x_width,
                        "route_y_width": route_y_width,
                        "route_width": route_width,
                    }
                if offset + route_width > 32:
                    raise ResolutionError(f"{display_name} destination bits exceed i32 payload")
                if payload_key == "int":
                    if route_field:
                        raise ResolutionError(f"{display_name} i32 payload must omit route_field")
                else:
                    packet = record_by_name(
                        payload_key, collect_record_definitions(self._captured)
                    )
                    field = (
                        next((field for field in packet.fields if field.name == route_field), None)
                        if packet is not None and packet.kind == "packet"
                        else None
                    )
                    if field is None or field.acir_type != "i32":
                        raise ResolutionError(
                            f"{display_name} route_field must name a top-level i32 Packet field"
                        )
                    assert packet is not None
                    payload_fields["payload_size"] = packet.size
            else:
                raise ResolutionError(
                    f"unsupported compiler-native generator {schema.identity!r}; "
                    "supported generators: ac.std.Crossbar, ac.std.MeshNoC, ac.std.RingNoC"
                )
            for expression, value in zip(inputs_expression.elts, input_values, strict=True):
                self._consume_bundle(value, expression)
        except (ResolutionError, ValueError, TypeError) as error:
            count = (
                f" (inferred output_ports={inferred_outputs})"
                if inferred_outputs is not None
                else ""
            )
            self._error(
                "ACPY-CROSSBAR-001" if schema.identity == "ac.std.Crossbar" else "ACPY-NOC-001",
                f"{diagnostic_name}{count}: {error}",
                target or node,
            )
            return

        entity_key = f"call:{node.lineno}:{node.col_offset + 1}"
        try:
            instance_name = self._names.allocate(
                schema.identity, None, explicit_name, (node.lineno, node.col_offset + 1)
            )
        except StableNameError as error:
            self._error("ACPY-NAME-002", str(error), node)
            return
        result_values = tuple(
            self._new_value(
                name,
                "flow_bundle",
                f"FlowBundle[{payload_key}, ReadyValid, {vc}]",
                entity_key,
                "owned",
            )
            for name in target_names
        )
        for index, value in enumerate(result_values):
            self._bundle_outputs[value.name] = (instance_name, index, source)
        derived = {
            **static_values,
            "input_ports": input_ports,
            "output_ports": output_ports,
            "virtual_channels": vc,
            "payload": "i32" if payload_key == "int" else payload_key,
            "protocol": "ready_valid",
            **payload_fields,
            **topology_fields,
        }
        fingerprint = sha256_bytes(
            canonical_json_bytes({"schema": schema.fingerprint, **derived})
        )
        static_arguments = tuple(sorted(derived.items()))
        self._calls.append(
            ResolvedCall(
                entity_key=entity_key,
                schema=schema,
                instance_name=instance_name,
                static_arguments=static_arguments,
                inputs=tuple(
                    PortBinding(f"input{index}", value, "flow", "consumer")
                    for index, value in enumerate(input_values)
                ),
                results=tuple(
                    ResultBinding("output", value, index, (vc,))
                    for index, value in enumerate(result_values)
                ),
                source=source,
                specialization=fingerprint,
            )
        )

    def _call(self, target: ast.expr | None, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            self._error("ACPY-CALL-001", "call target must be a registered name", node)
            return
        candidates = self._captured.registry.candidates(node.func.id)
        generators = tuple(schema for schema in candidates if schema.generator is not None)
        if len(generators) == 1 and len(candidates) == 1:
            self._context_call(target, node, generators[0])
            return
        viable: list[
            tuple[
                ComponentSchema,
                tuple[tuple[str, ValueVersion], ...],
                tuple[tuple[str, StaticValue], ...],
                str | None,
            ]
        ] = []
        attempts: list[RelatedLocation] = []
        source = _span(self._captured.source.path, node)
        for schema in candidates:
            try:
                ports, static_arguments, explicit_name = self._bound_candidate(
                    node, schema
                )
            except (ResolutionError, ValueError) as error:
                attempts.append(
                    RelatedLocation(
                        f"attempted {schema.identity}: {error}", source, None
                    )
                )
            else:
                viable.append((schema, ports, static_arguments, explicit_name))
                attempts.append(
                    RelatedLocation(f"attempted {schema.identity}: viable", source, None)
                )
        if len(viable) != 1:
            code = "ACPY-CALL-006" if len(viable) > 1 else "ACPY-CALL-003"
            message = (
                f"call {node.func.id!r} is ambiguous"
                if len(viable) > 1
                else f"call {node.func.id!r} has no exact binding"
            )
            self._error(code, message, node, tuple(attempts))
            return

        schema, ports, static_arguments, explicit_name = viable[0]
        if target is None:
            target_names = ()
        else:
            try:
                target_names = self._target_names(target)
            except ResolutionError as error:
                self._error("ACPY-CALL-005", str(error), target)
                return
        if len(target_names) != len(schema.results):
            self._error(
                "ACPY-CALL-005",
                f"{schema.identity} returns {len(schema.results)} values, not {len(target_names)}",
                target,
            )
            return
        entity_key = f"call:{node.lineno}:{node.col_offset + 1}"
        assignment_name = target_names[0] if len(target_names) == 1 else None
        try:
            instance_name = self._names.allocate(
                schema.identity,
                assignment_name if schema.effect_kind == "stateful" else None,
                explicit_name,
                (node.lineno, node.col_offset + 1),
            )
        except StableNameError as error:
            self._error("ACPY-NAME-002", str(error), node)
            return
        result_values = tuple(
            self._new_value(
                target_name,
                _result_category(result.acir_type),
                result.acir_type,
                entity_key,
                result.ownership,
            )
            for target_name, result in zip(target_names, schema.results, strict=True)
        )
        unresolved = UnresolvedCall(
            entity_key=entity_key,
            instance_name=instance_name,
            static_arguments=static_arguments,
            port_values=ports,
            result_values=result_values,
            source=source,
        )
        try:
            self._calls.append(resolve_call(unresolved, schema))
        except ResolutionError as error:
            self._error("ACPY-CALL-004", str(error), node)

    def _assignment(self, statement: ast.Assign) -> None:
        if len(statement.targets) != 1:
            self._error(
                "ACPY-SYNTAX-001", "chained assignment is not supported", statement
            )
            return
        if isinstance(statement.value, ast.Call):
            self._call(statement.targets[0], statement.value)
            return
        try:
            source = self._value(statement.value)
            targets = self._target_names(statement.targets[0])
        except ResolutionError as error:
            self._error("ACPY-SYMBOL-001", str(error), statement)
            return
        if len(targets) != 1:
            self._error("ACPY-SYNTAX-001", "value shape does not match target", statement)
            return
        self._new_value(targets[0], source.category, source.type_key, source.producer or "bind")

    def _return(self, statement: ast.Return) -> None:
        if statement.value is None:
            self._returns = ()
            return
        expressions = (
            tuple(statement.value.elts)
            if isinstance(statement.value, (ast.Tuple, ast.List))
            else (statement.value,)
        )
        try:
            self._returns = tuple(self._value(expression) for expression in expressions)
        except ResolutionError as error:
            self._error("ACPY-SYMBOL-001", str(error), statement)

    def _import_flow(self, node: ast.Call) -> None:
        if len(node.args) != 2 or node.keywords or not isinstance(node.args[0], ast.Name):
            self._error(
                "ACPY-FLOW-007",
                "import_flow requires one FlowBundle name and one fixed Queue tuple",
                node,
            )
            return
        queue_expression = node.args[1]
        if not isinstance(queue_expression, (ast.Tuple, ast.List)) or not queue_expression.elts:
            self._error("ACPY-FLOW-007", "import_flow queues must be a non-empty fixed tuple", node)
            return
        symbols = dict(self._captured.symbols)
        from ._resources import QueueSpec
        queues = []
        for expression in queue_expression.elts:
            queue = symbols.get(expression.id) if isinstance(expression, ast.Name) else None
            if (
                isinstance(expression, ast.Subscript)
                and isinstance(expression.value, ast.Name)
                and isinstance(expression.slice, ast.Constant)
                and type(expression.slice.value) is int
            ):
                collection = symbols.get(expression.value.id)
                index = expression.slice.value
                if isinstance(collection, (tuple, list)) and 0 <= index < len(collection):
                    queue = collection[index]
            if not isinstance(queue, QueueSpec):
                self._error("ACPY-FLOW-001", "import_flow requires captured Queue declarations", expression)
                return
            queues.append((queue.name, queue.payload_type, queue.protocol, queue.depth))
        try:
            value = self._value(node.args[0])
            self._consume_bundle(value, node.args[0])
        except ResolutionError as error:
            self._error("ACPY-FLOW-007", str(error), node)
            return
        bundle = _bundle_spec_from_key(value.type_key)
        if bundle is None or bundle[2] != len(queues):
            self._error("ACPY-FLOW-007", "Queue tuple and FlowBundle shape must match", node)
            return
        expected_payload = "i32" if bundle[0] == "int" else bundle[0]
        if any(payload != expected_payload or protocol != "ready_valid" for _, payload, protocol, _ in queues):
            self._error("ACPY-FLOW-005", "Flow payload or protocol does not match destination Queue", node)
            return
        self._flow_boundaries.append(FlowBoundary(value, "import", tuple(queues)))

    def _with_scope(self, statement: ast.With) -> None:
        valid = (
            len(statement.items) == 1
            and statement.items[0].optional_vars is None
            and isinstance(statement.items[0].context_expr, ast.Call)
            and isinstance(statement.items[0].context_expr.func, ast.Name)
            and statement.items[0].context_expr.func.id == "scope"
            and len(statement.items[0].context_expr.args) == 1
            and not statement.items[0].context_expr.keywords
        )
        if not valid:
            self._error(
                "ACPY-SCOPE-001", "only with scope(static_name) is supported", statement
            )
            return
        context = statement.items[0].context_expr
        assert isinstance(context, ast.Call)
        try:
            name = self._static(context.args[0])
        except ValueError as error:
            self._error("ACPY-SCOPE-001", str(error), context.args[0])
            return
        if type(name) is not str or not name:
            self._error(
                "ACPY-SCOPE-001", "scope name must be a non-empty static string", context
            )
            return
        key = f"scope:{statement.lineno}:{statement.col_offset + 1}"
        parent = self._scope_stack[-1] if self._scope_stack else None
        index = len(self._scopes)
        self._scopes.append(None)
        call_start = len(self._calls)
        value_start = len(self._values)
        self._scope_stack.append(key)
        for nested in statement.body:
            self._statement(nested)
        self._scope_stack.pop()
        self._scopes[index] = NormalizedScopeRegion(
            key=key,
            name=name,
            parent=parent,
            call_keys=tuple(call.entity_key for call in self._calls[call_start:]),
            value_names=tuple(value.name for value in self._values[value_start:]),
            source=_span(self._captured.source.path, statement),
        )

    def _statement(self, statement: ast.stmt) -> None:
        if isinstance(statement, ast.Assign):
            self._assignment(statement)
        elif isinstance(statement, ast.Return):
            self._return(statement)
        elif isinstance(statement, ast.With):
            self._with_scope(statement)
        elif isinstance(statement, ast.Expr) and isinstance(
            statement.value, ast.Call
        ):
            function = statement.value.func
            if isinstance(function, ast.Name) and function.id == "import_flow":
                self._import_flow(statement.value)
            else:
                self._call(None, statement.value)
        elif isinstance(statement, ast.Pass):
            return
        else:
            self._error(
                "ACPY-SYNTAX-001",
                f"{type(statement).__name__} normalization is not supported yet",
                statement,
            )

    def run(self) -> NormalizedProgram:
        for statement in self._node.body:
            self._statement(statement)
        returned = {value.name for value in self._returns}
        for value_name, (instance, port_index, source) in self._bundle_outputs.items():
            if value_name not in self._consumed_bundles and value_name not in returned:
                self._diagnostics.add(
                    Diagnostic(
                        stage="ssa-normalization",
                        code="ACPY-FLOW-008",
                        severity="error",
                        message=f"unconnected linear output {instance}.output[{port_index}]",
                        source=source,
                    )
                )
        return NormalizedProgram(
            definition=self._definition,
            arguments=self._arguments,
            values=tuple(self._values),
            calls=tuple(self._calls),
            returns=self._returns,
            diagnostics=self._diagnostics.freeze(),
            scopes=tuple(scope for scope in self._scopes if scope is not None),
            captures=tuple(self._captures),
            flow_boundaries=tuple(self._flow_boundaries),
            host_inputs=tuple(self._host_inputs),
            host_outputs=tuple(self._host_outputs),
        )


def normalize_program(
    captured: CapturedProgram, *, definition: str | None = None
) -> NormalizedProgram:
    qualified_name = definition or (
        captured.selected_system.qualified_name
        if captured.selected_system is not None
        else ""
    )
    sites = {
        site.qualified_name: site
        for site in captured.source.definitions
        if isinstance(site.node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    site = sites.get(qualified_name)
    if site is None or not isinstance(site.node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        diagnostic = Diagnostic(
            stage="ssa-normalization",
            code="ACPY-SYMBOL-DEFINITION",
            severity="error",
            message=f"definition {qualified_name!r} is not captured",
        )
        return NormalizedProgram(qualified_name, (), (), (), (), (diagnostic,))
    return _Normalizer(captured, qualified_name, site.node).run()
