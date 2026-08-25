"""Closed ACPy v0.3 semantic graph records.

This module deliberately does not import the ACIR text emitter.  It is the
typed boundary between Python elaboration and dialect-specific lowering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from ._canonical_json import JsonValue, canonical_json_bytes, sha256_bytes
from ._diagnostics import SourceSpan


class SemanticError(ValueError):
    """A deterministic ACPy v0.3 semantic graph failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ScalarType:
    name: str
    width: int

    def __post_init__(self) -> None:
        if not self.name or self.width <= 0:
            raise SemanticError(
                "ACPY03-TYPE-001", "scalar type requires a name and positive width"
            )

    def to_json(self) -> dict[str, JsonValue]:
        return {"kind": "scalar", "name": self.name, "width": self.width}


NamedTypeKind: TypeAlias = Literal["struct", "enum", "union"]


@dataclass(frozen=True, slots=True)
class NamedType:
    kind: NamedTypeKind
    name: str

    def __post_init__(self) -> None:
        if self.kind not in {"struct", "enum", "union"} or not self.name:
            raise SemanticError("ACPY03-TYPE-001", "invalid named payload type")

    def to_json(self) -> dict[str, JsonValue]:
        return {"kind": self.kind, "name": self.name}


@dataclass(frozen=True, slots=True)
class ArrayType:
    extent: int
    element: PayloadType

    def __post_init__(self) -> None:
        if self.extent <= 0:
            raise SemanticError("ACPY03-TYPE-001", "array extent must be positive")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "kind": "array",
            "extent": self.extent,
            "element": payload_type_json(self.element),
        }


PayloadType: TypeAlias = ScalarType | NamedType | ArrayType


def payload_type_json(payload: PayloadType) -> dict[str, JsonValue]:
    return payload.to_json()


@dataclass(frozen=True, slots=True)
class PayloadField:
    name: str
    type: PayloadType

    def __post_init__(self) -> None:
        if not self.name:
            raise SemanticError("ACPY03-TYPE-002", "payload field name is empty")

    def to_json(self) -> dict[str, JsonValue]:
        return {"name": self.name, "type": payload_type_json(self.type)}


@dataclass(frozen=True, slots=True)
class PayloadDeclaration:
    kind: NamedTypeKind
    name: str
    fields: tuple[PayloadField, ...] = ()
    enumerants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise SemanticError("ACPY03-TYPE-002", "payload declaration name is empty")
        if self.kind == "enum":
            if self.fields or not self.enumerants:
                raise SemanticError(
                    "ACPY03-TYPE-002", "enum requires enumerants and no fields"
                )
            if len(self.enumerants) != len(set(self.enumerants)):
                raise SemanticError(
                    "ACPY03-TYPE-002", "enum enumerants must be unique"
                )
        elif self.enumerants:
            raise SemanticError(
                "ACPY03-TYPE-002", "non-enum declaration cannot have enumerants"
            )
        field_names = tuple(field.name for field in self.fields)
        if len(field_names) != len(set(field_names)):
            raise SemanticError("ACPY03-TYPE-002", "payload fields must be unique")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "kind": self.kind,
            "name": self.name,
            "fields": [field.to_json() for field in self.fields],
            "enumerants": list(self.enumerants),
        }


@dataclass(frozen=True, slots=True)
class FieldDescriptor:
    root: NamedType
    path: tuple[str, ...]
    leaf: PayloadType

    def __post_init__(self) -> None:
        if not self.path or any(not component for component in self.path):
            raise SemanticError(
                "ACPY03-TYPE-003", "field descriptor path must be non-empty"
            )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "root": self.root.to_json(),
            "path": list(self.path),
            "leaf": payload_type_json(self.leaf),
        }


@dataclass(frozen=True, slots=True)
class Policy:
    kind: str
    fields: tuple[tuple[str, FieldDescriptor], ...] = ()
    integers: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if not self.kind:
            raise SemanticError("ACPY03-POLICY-001", "policy kind is empty")
        field_names = tuple(name for name, _ in self.fields)
        integer_names = tuple(name for name, _ in self.integers)
        names = (*field_names, *integer_names)
        if len(names) != len(set(names)):
            raise SemanticError(
                "ACPY03-POLICY-001", "policy parameter names must be unique"
            )
        if field_names != tuple(sorted(field_names)) or integer_names != tuple(
            sorted(integer_names)
        ):
            raise SemanticError(
                "ACPY03-POLICY-001", "policy parameters must be canonicalized"
            )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "kind": self.kind,
            "fields": [
                {"name": name, "value": value.to_json()}
                for name, value in self.fields
            ],
            "integers": [
                {"name": name, "value": value}
                for name, value in self.integers
            ],
        }


@dataclass(frozen=True, slots=True)
class QueueContract:
    depth: int
    latency: int
    rate: int
    domain: str
    ordering: str = "fifo"

    def __post_init__(self) -> None:
        if self.depth <= 0:
            raise SemanticError("ACPY03-QUEUE-001", "Queue depth must be positive")
        if self.latency <= 0:
            raise SemanticError(
                "ACPY03-QUEUE-001", "Queue latency must be at least one"
            )
        if self.rate <= 0:
            raise SemanticError("ACPY03-QUEUE-001", "Queue rate must be positive")
        if not self.domain or self.ordering != "fifo":
            raise SemanticError(
                "ACPY03-QUEUE-001", "Queue requires a domain and FIFO ordering"
            )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "depth": self.depth,
            "latency": self.latency,
            "rate": self.rate,
            "domain": self.domain,
            "ordering": self.ordering,
        }


@dataclass(frozen=True, slots=True)
class QueueConstraint:
    payload: PayloadType
    depth: int | None = None
    latency: int | None = None
    rate: int | None = None
    domain: str | None = None
    ordering: str = "fifo"

    def merge(self, other: QueueConstraint) -> QueueConstraint:
        if self.payload != other.payload:
            raise SemanticError(
                "ACPY03-QUEUE-002", "Queue constraints disagree on payload type"
            )

        def unify(name: str, left: object | None, right: object | None):
            if left is not None and right is not None and left != right:
                raise SemanticError(
                    "ACPY03-QUEUE-002", f"Queue constraints disagree on {name}"
                )
            return left if left is not None else right

        ordering = unify("ordering", self.ordering, other.ordering)
        assert isinstance(ordering, str)
        return QueueConstraint(
            payload=self.payload,
            depth=unify("depth", self.depth, other.depth),
            latency=unify("latency", self.latency, other.latency),
            rate=unify("rate", self.rate, other.rate),
            domain=unify("domain", self.domain, other.domain),
            ordering=ordering,
        )

    def freeze(self) -> QueueContract:
        missing = tuple(
            name
            for name, value in (
                ("depth", self.depth),
                ("latency", self.latency),
                ("rate", self.rate),
                ("domain", self.domain),
            )
            if value is None
        )
        if missing:
            raise SemanticError(
                "ACPY03-QUEUE-003",
                "Queue contract is unresolved: " + ", ".join(missing),
            )
        assert self.depth is not None
        assert self.latency is not None
        assert self.rate is not None
        assert self.domain is not None
        return QueueContract(
            self.depth, self.latency, self.rate, self.domain, self.ordering
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "payload": payload_type_json(self.payload),
            "depth": self.depth,
            "latency": self.latency,
            "rate": self.rate,
            "domain": self.domain,
            "ordering": self.ordering,
        }


@dataclass(frozen=True, slots=True)
class QueueValue:
    id: str
    constraint: QueueConstraint
    source: SourceSpan | None = None

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "constraint": self.constraint.to_json(),
            "source": _source_json(self.source),
        }


PortEffect: TypeAlias = Literal["consume", "observe", "produce"]


@dataclass(frozen=True, slots=True)
class PortGroup:
    name: str
    effect: PortEffect
    queues: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name or self.effect not in {"consume", "observe", "produce"}:
            raise SemanticError("ACPY03-PORT-001", "invalid port group")
        if len(self.queues) != len(set(self.queues)):
            raise SemanticError(
                "ACPY03-PORT-001", "a port group cannot repeat a Queue value"
            )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "effect": self.effect,
            "queues": list(self.queues),
        }


SemanticParameterValue: TypeAlias = (
    None | bool | int | str | PayloadType | FieldDescriptor | Policy
)


@dataclass(frozen=True, slots=True)
class SemanticParameter:
    name: str
    value: SemanticParameterValue

    def __post_init__(self) -> None:
        if not self.name:
            raise SemanticError("ACPY03-BLOCK-001", "parameter name is empty")

    def to_json(self) -> dict[str, JsonValue]:
        return {"name": self.name, "value": _parameter_json(self.value)}


@dataclass(frozen=True, slots=True)
class VarValue:
    id: str
    type: PayloadType
    source: SourceSpan | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise SemanticError("ACPY03-VAR-001", "Var value id is empty")

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "type": payload_type_json(self.type),
            "source": _source_json(self.source),
        }


_VAR_OPCODES = frozenset(
    {
        "constant",
        "struct",
        "get",
        "update",
        "array",
        "extract",
        "unary",
        "binary",
        "compare",
        "select",
        "cast",
        "yield",
    }
)


@dataclass(frozen=True, slots=True)
class VarOperation:
    id: str
    opcode: str
    operands: tuple[str, ...]
    results: tuple[VarValue, ...]
    parameters: tuple[SemanticParameter, ...] = ()
    source: SourceSpan | None = None

    def __post_init__(self) -> None:
        if not self.id or self.opcode not in _VAR_OPCODES:
            raise SemanticError("ACPY03-VAR-001", "invalid canonical Var operation")
        if self.opcode == "yield" and self.results:
            raise SemanticError("ACPY03-VAR-001", "Var yield cannot have results")
        if self.opcode != "yield" and not self.results:
            raise SemanticError(
                "ACPY03-VAR-001", "non-terminator Var operation requires a result"
            )
        parameter_names = tuple(parameter.name for parameter in self.parameters)
        if parameter_names != tuple(sorted(parameter_names)) or len(
            parameter_names
        ) != len(set(parameter_names)):
            raise SemanticError(
                "ACPY03-VAR-001", "Var parameters must be unique and canonicalized"
            )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "opcode": self.opcode,
            "operands": list(self.operands),
            "results": [result.to_json() for result in self.results],
            "parameters": [parameter.to_json() for parameter in self.parameters],
            "source": _source_json(self.source),
        }


@dataclass(frozen=True, slots=True)
class VarRegion:
    id: str
    inputs: tuple[VarValue, ...]
    operations: tuple[VarOperation, ...]
    outputs: tuple[str, ...]

    def verify(self) -> None:
        if not self.id:
            raise SemanticError("ACPY03-VAR-001", "Var region id is empty")
        _require_dense_ids("v", tuple(value.id for value in self.inputs))
        available = {value.id for value in self.inputs}
        next_value = len(self.inputs)
        yielded = False
        for index, operation in enumerate(self.operations):
            if operation.id != f"vo{index}":
                raise SemanticError(
                    "ACPY03-VAR-001", "Var operation ids must be dense and ordered"
                )
            if any(operand not in available for operand in operation.operands):
                raise SemanticError(
                    "ACPY03-VAR-002", "Var operand does not dominate its use"
                )
            if yielded:
                raise SemanticError(
                    "ACPY03-VAR-002", "Var yield must be the final operation"
                )
            if operation.opcode == "yield":
                yielded = True
                if operation.operands != self.outputs:
                    raise SemanticError(
                        "ACPY03-VAR-002", "Var yield operands must match outputs"
                    )
                continue
            for result in operation.results:
                if result.id != f"v{next_value}":
                    raise SemanticError(
                        "ACPY03-VAR-001", "Var value ids must be dense and ordered"
                    )
                available.add(result.id)
                next_value += 1
        if not yielded:
            raise SemanticError("ACPY03-VAR-002", "Var region requires a final yield")

    def to_json(self) -> dict[str, JsonValue]:
        self.verify()
        return {
            "id": self.id,
            "inputs": [value.to_json() for value in self.inputs],
            "operations": [operation.to_json() for operation in self.operations],
            "outputs": list(self.outputs),
        }


@dataclass(frozen=True, slots=True)
class BlockInstance:
    id: str
    opcode: str
    scope: str
    inputs: tuple[PortGroup, ...]
    results: tuple[PortGroup, ...]
    regions: tuple[str, ...] = ()
    parameters: tuple[SemanticParameter, ...] = ()
    source: SourceSpan | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.opcode or not self.scope:
            raise SemanticError(
                "ACPY03-BLOCK-001", "block requires id, opcode and scope"
            )
        if any(group.effect == "produce" for group in self.inputs):
            raise SemanticError(
                "ACPY03-BLOCK-001", "input groups cannot produce Queue values"
            )
        if any(group.effect != "produce" for group in self.results):
            raise SemanticError(
                "ACPY03-BLOCK-001", "result groups must produce Queue values"
            )
        input_names = tuple(group.name for group in self.inputs)
        result_names = tuple(group.name for group in self.results)
        parameter_names = tuple(parameter.name for parameter in self.parameters)
        for kind, names in (
            ("input group", input_names),
            ("result group", result_names),
            ("parameter", parameter_names),
        ):
            if len(names) != len(set(names)):
                raise SemanticError(
                    "ACPY03-BLOCK-001", f"duplicate {kind} name"
                )
        if parameter_names != tuple(sorted(parameter_names)):
            raise SemanticError(
                "ACPY03-BLOCK-001", "parameters must be canonicalized by name"
            )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "opcode": self.opcode,
            "scope": self.scope,
            "inputs": [group.to_json() for group in self.inputs],
            "results": [group.to_json() for group in self.results],
            "regions": list(self.regions),
            "parameters": [parameter.to_json() for parameter in self.parameters],
            "source": _source_json(self.source),
        }


@dataclass(frozen=True, slots=True)
class Scope:
    id: str
    name: str
    parent: str | None
    blocks: tuple[str, ...]
    children: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    source: SourceSpan | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise SemanticError("ACPY03-SCOPE-001", "scope id/name is empty")
        for values in (self.blocks, self.children, self.inputs, self.outputs):
            if len(values) != len(set(values)):
                raise SemanticError(
                    "ACPY03-SCOPE-001", "scope references must be unique"
                )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "name": self.name,
            "parent": self.parent,
            "blocks": list(self.blocks),
            "children": list(self.children),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "source": _source_json(self.source),
        }


@dataclass(frozen=True, slots=True)
class DeferredEdge:
    id: str
    output_queue: str
    payload: PayloadType
    bound_queue: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.output_queue:
            raise SemanticError(
                "ACPY03-DEFERRED-001", "deferred edge id/output is empty"
            )

    def bind(self, queue: str) -> DeferredEdge:
        if self.bound_queue is not None:
            raise SemanticError(
                "ACPY03-DEFERRED-002", "deferred edge may be bound exactly once"
            )
        if not queue:
            raise SemanticError(
                "ACPY03-DEFERRED-002", "deferred binding target is empty"
            )
        return DeferredEdge(self.id, self.output_queue, self.payload, queue)

    def require_bound(self) -> str:
        if self.bound_queue is None:
            raise SemanticError("ACPY03-DEFERRED-003", "deferred edge is unbound")
        return self.bound_queue


PortArityKind: TypeAlias = Literal["fixed", "variadic"]


@dataclass(frozen=True, slots=True)
class PortSpec:
    name: str
    effect: PortEffect
    arity: PortArityKind
    minimum: int

    def __post_init__(self) -> None:
        if (
            not self.name
            or self.effect not in {"consume", "observe", "produce"}
            or self.arity not in {"fixed", "variadic"}
            or self.minimum < 0
        ):
            raise SemanticError("ACPY03-SPEC-001", "invalid BlockSpec port")
        if self.arity == "fixed" and self.minimum == 0:
            raise SemanticError(
                "ACPY03-SPEC-001", "fixed BlockSpec port requires positive arity"
            )


ParameterKind: TypeAlias = Literal[
    "bool", "integer", "string", "type", "field", "policy"
]


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: str
    kind: ParameterKind
    required: bool = True

    def __post_init__(self) -> None:
        if not self.name or self.kind not in {
            "bool",
            "integer",
            "string",
            "type",
            "field",
            "policy",
        }:
            raise SemanticError("ACPY03-SPEC-001", "invalid BlockSpec parameter")


@dataclass(frozen=True, slots=True)
class PayloadRelation:
    groups: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.groups) < 2 or len(self.groups) != len(set(self.groups)):
            raise SemanticError(
                "ACPY03-SPEC-001", "payload relation requires unique port groups"
            )


BlockRole: TypeAlias = Literal["design", "verification", "observation"]


@dataclass(frozen=True, slots=True)
class BlockSpec:
    opcode: str
    inputs: tuple[PortSpec, ...]
    results: tuple[PortSpec, ...]
    parameters: tuple[ParameterSpec, ...]
    payload_relations: tuple[PayloadRelation, ...]
    stateful: bool
    role: BlockRole = "design"

    def __post_init__(self) -> None:
        if not self.opcode or self.role not in {
            "design",
            "verification",
            "observation",
        }:
            raise SemanticError("ACPY03-SPEC-001", "invalid BlockSpec identity")
        input_names = tuple(port.name for port in self.inputs)
        result_names = tuple(port.name for port in self.results)
        if len(input_names) != len(set(input_names)) or len(result_names) != len(
            set(result_names)
        ):
            raise SemanticError("ACPY03-SPEC-001", "BlockSpec ports must be unique")
        parameter_names = tuple(parameter.name for parameter in self.parameters)
        if parameter_names != tuple(sorted(parameter_names)) or len(
            parameter_names
        ) != len(set(parameter_names)):
            raise SemanticError(
                "ACPY03-SPEC-001", "BlockSpec parameters must be canonicalized"
            )
        known_groups = {*input_names, *result_names}
        for relation in self.payload_relations:
            if any(group not in known_groups for group in relation.groups):
                raise SemanticError(
                    "ACPY03-SPEC-001", "payload relation references unknown group"
                )

    def verify_instance(
        self, instance: BlockInstance, queues: tuple[QueueValue, ...]
    ) -> None:
        if instance.opcode != self.opcode:
            raise SemanticError(
                "ACPY03-SPEC-002", "BlockSpec opcode does not match instance"
            )
        self._verify_groups("input", self.inputs, instance.inputs)
        self._verify_groups("result", self.results, instance.results)
        expected_parameters = {parameter.name: parameter for parameter in self.parameters}
        actual_parameters = {parameter.name: parameter for parameter in instance.parameters}
        missing = tuple(
            name
            for name, parameter in expected_parameters.items()
            if parameter.required and name not in actual_parameters
        )
        extra = tuple(name for name in actual_parameters if name not in expected_parameters)
        if missing or extra:
            raise SemanticError(
                "ACPY03-SPEC-002",
                f"BlockSpec parameter mismatch; missing={missing}, extra={extra}",
            )
        queue_map = {queue.id: queue for queue in queues}
        group_map = {
            group.name: group
            for group in (*instance.inputs, *instance.results)
        }
        for relation in self.payload_relations:
            payloads = {
                queue_map[queue_id].constraint.payload
                for group_name in relation.groups
                for queue_id in group_map[group_name].queues
                if queue_id in queue_map
            }
            if len(payloads) > 1:
                raise SemanticError(
                    "ACPY03-SPEC-003", "BlockSpec payload relation is not satisfied"
                )

    @staticmethod
    def _verify_groups(
        kind: str, expected: tuple[PortSpec, ...], actual: tuple[PortGroup, ...]
    ) -> None:
        if tuple(group.name for group in actual) != tuple(
            group.name for group in expected
        ):
            raise SemanticError(
                "ACPY03-SPEC-002", f"{kind} port groups do not match BlockSpec"
            )
        for port, group in zip(expected, actual, strict=True):
            if port.effect != group.effect:
                raise SemanticError(
                    "ACPY03-SPEC-002", f"{kind} port effect does not match BlockSpec"
                )
            count = len(group.queues)
            if (port.arity == "fixed" and count != port.minimum) or (
                port.arity == "variadic" and count < port.minimum
            ):
                raise SemanticError(
                    "ACPY03-SPEC-002", f"{kind} port arity does not match BlockSpec"
                )


@dataclass(frozen=True, slots=True)
class BlockCatalog:
    specs: tuple[BlockSpec, ...]

    def __post_init__(self) -> None:
        opcodes = tuple(spec.opcode for spec in self.specs)
        if opcodes != tuple(sorted(opcodes)) or len(opcodes) != len(set(opcodes)):
            raise SemanticError(
                "ACPY03-SPEC-001", "BlockCatalog must be unique and canonicalized"
            )

    def lookup(self, opcode: str) -> BlockSpec:
        for spec in self.specs:
            if spec.opcode == opcode:
                return spec
        raise SemanticError(
            "ACPY03-SPEC-004", f"opcode {opcode!r} is outside the official catalog"
        )


def davincioo_core_catalog() -> BlockCatalog:
    """Return the frozen 13-op v0.3 semantic catalog.

    Static parameter details are refined by the versioned BlockSpec source once
    the shared B6 contract lands.  Port group names, effects and minimum arity
    are already part of the frozen frontend contract.
    """

    consume_one = lambda name: PortSpec(name, "consume", "fixed", 1)
    observe_one = lambda name: PortSpec(name, "observe", "fixed", 1)
    produce_one = lambda name: PortSpec(name, "produce", "fixed", 1)
    consume_many = lambda name, minimum=1: PortSpec(
        name, "consume", "variadic", minimum
    )
    produce_many = lambda name, minimum=1: PortSpec(
        name, "produce", "variadic", minimum
    )
    same = lambda *groups: (PayloadRelation(tuple(groups)),)

    specs = (
        BlockSpec(
            "compute",
            (consume_one("input"),),
            (produce_one("output"),),
            (),
            (),
            False,
        ),
        BlockSpec(
            "engine",
            (consume_one("input"),),
            (produce_one("completed"),),
            (),
            same("input", "completed"),
            True,
        ),
        BlockSpec(
            "fork",
            (consume_one("input"),),
            (produce_many("outputs"),),
            (),
            same("input", "outputs"),
            False,
        ),
        BlockSpec(
            "issue",
            (
                consume_many("enqueue"),
                consume_many("wakeup"),
                consume_many("recheck_response"),
            ),
            (produce_many("issued"), produce_many("recheck_request")),
            (),
            same("enqueue", "issued"),
            True,
        ),
        BlockSpec(
            "merge",
            (consume_many("inputs"),),
            (produce_one("output"),),
            (),
            same("inputs", "output"),
            False,
        ),
        BlockSpec(
            "observe",
            (observe_one("input"),),
            (),
            (),
            (),
            False,
            "observation",
        ),
        BlockSpec(
            "pool",
            (consume_many("acquire"), consume_many("release")),
            (produce_many("acquired"),),
            (),
            same("acquire", "acquired"),
            True,
        ),
        BlockSpec(
            "queue",
            (consume_one("input"),),
            (produce_one("output"),),
            (),
            same("input", "output"),
            True,
        ),
        BlockSpec(
            "reorder",
            (consume_one("enqueue"), consume_one("completed")),
            (produce_one("admitted"), produce_one("retired")),
            (),
            same("enqueue", "completed", "admitted", "retired"),
            True,
        ),
        BlockSpec(
            "route",
            (consume_one("input"),),
            (produce_many("outputs"),),
            (),
            same("input", "outputs"),
            False,
        ),
        BlockSpec(
            "sink",
            (consume_one("input"),),
            (),
            (),
            (),
            True,
        ),
        BlockSpec(
            "source",
            (),
            (produce_one("output"),),
            (),
            (),
            True,
        ),
        BlockSpec(
            "table",
            (
                consume_many("access", 0),
                consume_many("update", 0),
                consume_many("query", 0),
            ),
            (
                produce_many("accessed", 0),
                produce_many("updated", 0),
                produce_many("response", 0),
            ),
            (),
            (),
            True,
        ),
    )
    return BlockCatalog(specs)


@dataclass(frozen=True, slots=True)
class SemanticProgram:
    system: str
    root_scope: str
    declarations: tuple[PayloadDeclaration, ...]
    queues: tuple[QueueValue, ...]
    blocks: tuple[BlockInstance, ...]
    scopes: tuple[Scope, ...]
    var_regions: tuple[VarRegion, ...] = ()
    contract_epoch: str = "0.3"

    def verify(self, *, require_frozen_queues: bool = False) -> None:
        if self.contract_epoch != "0.3" or not self.system:
            raise SemanticError(
                "ACPY03-PROGRAM-001", "semantic program must use contract epoch 0.3"
            )
        _require_dense_ids("q", tuple(queue.id for queue in self.queues))
        _require_dense_ids("b", tuple(block.id for block in self.blocks))
        _require_dense_ids("s", tuple(scope.id for scope in self.scopes))
        queue_ids = {queue.id for queue in self.queues}
        block_ids = {block.id for block in self.blocks}
        scope_ids = {scope.id for scope in self.scopes}
        region_ids = {region.id for region in self.var_regions}
        if len(region_ids) != len(self.var_regions):
            raise SemanticError("ACPY03-VAR-001", "Var region ids must be unique")
        for region in self.var_regions:
            region.verify()
        if self.root_scope not in scope_ids:
            raise SemanticError(
                "ACPY03-SCOPE-002", "root scope does not resolve"
            )

        declaration_names = tuple(item.name for item in self.declarations)
        if len(declaration_names) != len(set(declaration_names)):
            raise SemanticError(
                "ACPY03-TYPE-002", "payload declaration names must be unique"
            )

        producers = {queue_id: 0 for queue_id in queue_ids}
        consumers = {queue_id: 0 for queue_id in queue_ids}
        for block in self.blocks:
            if block.scope not in scope_ids:
                raise SemanticError(
                    "ACPY03-SCOPE-002", f"block {block.id} has unresolved scope"
                )
            if any(region not in region_ids for region in block.regions):
                raise SemanticError(
                    "ACPY03-VAR-001", f"block {block.id} Var region does not resolve"
                )
            for group in block.inputs:
                for queue_id in group.queues:
                    if queue_id not in queue_ids:
                        raise SemanticError(
                            "ACPY03-QUEUE-004", "input Queue does not resolve"
                        )
                    if group.effect == "consume":
                        consumers[queue_id] += 1
            for group in block.results:
                for queue_id in group.queues:
                    if queue_id not in queue_ids:
                        raise SemanticError(
                            "ACPY03-QUEUE-004", "result Queue does not resolve"
                        )
                    producers[queue_id] += 1

        for queue_id in sorted(queue_ids):
            if producers[queue_id] != 1:
                raise SemanticError(
                    "ACPY03-QUEUE-004",
                    f"Queue {queue_id} requires exactly one producer",
                )
            if consumers[queue_id] > 1:
                raise SemanticError(
                    "ACPY03-QUEUE-005",
                    f"Queue {queue_id} has multiple consuming uses",
                )
        for scope in self.scopes:
            if scope.parent is not None and scope.parent not in scope_ids:
                raise SemanticError(
                    "ACPY03-SCOPE-002", f"scope {scope.id} parent does not resolve"
                )
            if any(block not in block_ids for block in scope.blocks):
                raise SemanticError(
                    "ACPY03-SCOPE-002", f"scope {scope.id} block does not resolve"
                )
            if any(child not in scope_ids for child in scope.children):
                raise SemanticError(
                    "ACPY03-SCOPE-002", f"scope {scope.id} child does not resolve"
                )
            if any(queue not in queue_ids for queue in (*scope.inputs, *scope.outputs)):
                raise SemanticError(
                    "ACPY03-SCOPE-002", f"scope {scope.id} Queue does not resolve"
                )
        if require_frozen_queues:
            for queue in self.queues:
                queue.constraint.freeze()

    def to_json(self) -> dict[str, JsonValue]:
        self.verify()
        return {
            "schema": "agentic-circuit-acpy-semantic",
            "version": "0.3",
            "contract_epoch": self.contract_epoch,
            "system": self.system,
            "root_scope": self.root_scope,
            "declarations": [item.to_json() for item in self.declarations],
            "queues": [queue.to_json() for queue in self.queues],
            "blocks": [block.to_json() for block in self.blocks],
            "scopes": [scope.to_json() for scope in self.scopes],
            "var_regions": [region.to_json() for region in self.var_regions],
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())


@dataclass(frozen=True, slots=True)
class SemanticArtifact:
    data: bytes
    sha256: str

    @staticmethod
    def from_program(program: SemanticProgram) -> SemanticArtifact:
        program.verify(require_frozen_queues=True)
        data = program.canonical_bytes()
        return SemanticArtifact(data, sha256_bytes(data))


@dataclass(slots=True)
class _ScopeDraft:
    id: str
    name: str
    parent: str | None
    blocks: list[str]
    children: list[str]
    inputs: list[str]
    outputs: list[str]
    source: SourceSpan | None


class SemanticBuilder:
    """Source-ordered allocator for deterministic ACPy v0.3 graphs."""

    def __init__(self, system: str, root_name: str, source: SourceSpan | None = None):
        if not system or not root_name:
            raise SemanticError(
                "ACPY03-PROGRAM-001", "builder requires system and root name"
            )
        self._system = system
        self._declarations: list[PayloadDeclaration] = []
        self._queues: list[QueueValue] = []
        self._blocks: list[BlockInstance] = []
        self._regions: list[VarRegion] = []
        self._scopes: list[_ScopeDraft] = [
            _ScopeDraft("s0", root_name, None, [], [], [], [], source)
        ]

    @property
    def root_scope(self) -> str:
        return "s0"

    def add_declaration(self, declaration: PayloadDeclaration) -> None:
        self._declarations.append(declaration)

    def add_queue(
        self, constraint: QueueConstraint, source: SourceSpan | None = None
    ) -> str:
        identity = f"q{len(self._queues)}"
        self._queues.append(QueueValue(identity, constraint, source))
        return identity

    def add_scope(
        self,
        name: str,
        parent: str,
        source: SourceSpan | None = None,
    ) -> str:
        parent_scope = self._scope(parent)
        identity = f"s{len(self._scopes)}"
        self._scopes.append(
            _ScopeDraft(identity, name, parent, [], [], [], [], source)
        )
        parent_scope.children.append(identity)
        return identity

    def set_scope_io(
        self, scope: str, inputs: tuple[str, ...], outputs: tuple[str, ...]
    ) -> None:
        draft = self._scope(scope)
        draft.inputs[:] = inputs
        draft.outputs[:] = outputs

    def add_region(self, region: VarRegion) -> str:
        identity = f"vr{len(self._regions)}"
        if region.id != identity:
            raise SemanticError(
                "ACPY03-VAR-001", "Var region ids must be dense and ordered"
            )
        region.verify()
        self._regions.append(region)
        return identity

    def add_block(
        self,
        opcode: str,
        scope: str,
        inputs: tuple[PortGroup, ...],
        results: tuple[PortGroup, ...],
        *,
        regions: tuple[str, ...] = (),
        parameters: tuple[SemanticParameter, ...] = (),
        source: SourceSpan | None = None,
        catalog: BlockCatalog | None = None,
    ) -> str:
        draft = self._scope(scope)
        identity = f"b{len(self._blocks)}"
        block = BlockInstance(
            identity,
            opcode,
            scope,
            inputs,
            results,
            regions,
            parameters,
            source,
        )
        if catalog is not None:
            catalog.lookup(opcode).verify_instance(block, tuple(self._queues))
        self._blocks.append(block)
        draft.blocks.append(identity)
        return identity

    def freeze(self) -> SemanticProgram:
        scopes = tuple(
            Scope(
                draft.id,
                draft.name,
                draft.parent,
                tuple(draft.blocks),
                tuple(draft.children),
                tuple(draft.inputs),
                tuple(draft.outputs),
                draft.source,
            )
            for draft in self._scopes
        )
        program = SemanticProgram(
            self._system,
            self.root_scope,
            tuple(self._declarations),
            tuple(self._queues),
            tuple(self._blocks),
            scopes,
            tuple(self._regions),
        )
        program.verify()
        return program

    def _scope(self, identity: str) -> _ScopeDraft:
        for scope in self._scopes:
            if scope.id == identity:
                return scope
        raise SemanticError("ACPY03-SCOPE-002", "scope does not resolve")


def _require_dense_ids(prefix: str, values: tuple[str, ...]) -> None:
    expected = tuple(f"{prefix}{index}" for index in range(len(values)))
    if values != expected:
        raise SemanticError(
            "ACPY03-PROGRAM-001", f"{prefix} identities must be dense and ordered"
        )


def _source_json(source: SourceSpan | None) -> JsonValue:
    if source is None:
        return None
    return {
        "file": source.file,
        "start_line": source.start_line,
        "start_column": source.start_column,
        "end_line": source.end_line,
        "end_column": source.end_column,
    }


def _parameter_json(value: SemanticParameterValue) -> JsonValue:
    if value is None or type(value) in (bool, int, str):
        return value
    if isinstance(value, (ScalarType, NamedType, ArrayType)):
        return {"type": payload_type_json(value)}
    if isinstance(value, FieldDescriptor):
        return {"field": value.to_json()}
    if isinstance(value, Policy):
        return {"policy": value.to_json()}
    raise SemanticError(
        "ACPY03-BLOCK-001", f"unsupported semantic parameter {type(value).__name__}"
    )
