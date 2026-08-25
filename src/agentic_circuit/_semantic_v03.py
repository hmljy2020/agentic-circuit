"""Closed ACPy v0.3 semantic graph records.

This module deliberately does not import the ACIR text emitter.  It is the
typed boundary between Python elaboration and dialect-specific lowering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from ._canonical_json import JsonValue, canonical_json_bytes
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
class BlockInstance:
    id: str
    opcode: str
    scope: str
    inputs: tuple[PortGroup, ...]
    results: tuple[PortGroup, ...]
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
class SemanticProgram:
    system: str
    root_scope: str
    declarations: tuple[PayloadDeclaration, ...]
    queues: tuple[QueueValue, ...]
    blocks: tuple[BlockInstance, ...]
    scopes: tuple[Scope, ...]
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
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_json())


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
