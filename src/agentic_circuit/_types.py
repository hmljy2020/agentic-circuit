"""Public annotation categories and frontend-only symbolic values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Never, TypeVar, get_args, get_origin


T = TypeVar("T")
P = TypeVar("P")
I = TypeVar("I")
R = TypeVar("R")


class i8:
    """Signless 8-bit ACPy value type marker."""


class i16:
    """Signless 16-bit ACPy value type marker."""


class i32:
    """Signless 32-bit ACPy value type marker."""


class i64:
    """Signless 64-bit ACPy value type marker."""


class f32:
    """32-bit floating-point ACPy value type marker."""


class f64:
    """64-bit floating-point ACPy value type marker."""


class Vector:
    """Fixed ACPy value vector, spelled ``Vector[element, length]``."""

    @classmethod
    def __class_getitem__(cls, _parameters: object) -> type["Vector"]:
        return cls


class Static(Generic[T]):
    """Mark an elaboration-time specialization parameter."""


class Flow(Generic[T, P]):
    """Describe a typed logical dataflow edge using protocol ``P``."""


@dataclass(frozen=True, slots=True, eq=False)
class FlowBundle(Generic[T, P]):
    """An immutable, statically-shaped collection of linear Flow leaves.

    Bundles exist only in the Python frontend.  They are flattened in row-major
    order before ACIR is emitted; no tuple or bundle value reaches the runtime.
    """

    payload: object
    protocol: object
    shape: tuple[int, ...]
    leaves: tuple["SymbolicValue", ...]

    def __post_init__(self) -> None:
        if not self.shape or any(type(size) is not int or size <= 0 for size in self.shape):
            raise TypeError("ACPY-FLOW-007: FlowBundle shape must be non-empty and positive")
        leaf_count = 1
        for size in self.shape:
            leaf_count *= size
        if leaf_count != len(self.leaves):
            raise TypeError("ACPY-FLOW-007: FlowBundle shape does not match its leaves")
        expected = Flow[self.payload, self.protocol]
        if any(
            not isinstance(leaf, SymbolicValue) or leaf.annotation != expected
            for leaf in self.leaves
        ):
            raise TypeError("ACPY-FLOW-007: FlowBundle leaves must have one Flow type")

    def __repr__(self) -> str:
        return f"FlowBundle(shape={self.shape!r}, payload={self.payload!r})"


class Endpoint(Generic[I, R]):
    """Describe interface ``I`` bound in role ``R``."""


@dataclass(frozen=True, slots=True, eq=False)
class SymbolicValue:
    """Frontend identity for an architecture value without a Python value."""

    stable_name: str
    annotation: object
    _flow_consumed: bool = field(
        default=False, init=False, compare=False, repr=False
    )

    def __repr__(self) -> str:
        return f"SymbolicValue({self.stable_name!r})"

    def _reject(self, operation: str) -> Never:
        raise TypeError(
            f"ACPY-STATIC-002: {self.stable_name!r} cannot be used for {operation}"
        )

    def __bool__(self) -> Never:
        return self._reject("truth testing")

    def __int__(self) -> Never:
        return self._reject("integer conversion")

    def __hash__(self) -> Never:
        return self._reject("hashing")

    def __iter__(self) -> Never:
        return self._reject("iteration")

    def __eq__(self, other: object) -> Never:
        return self._reject("equality")

    def __ne__(self, other: object) -> Never:
        return self._reject("equality")


@dataclass(frozen=True, slots=True, eq=False, repr=False)
class ResourceRef(SymbolicValue, Generic[T, R]):
    """A typed resource capability bound in a declared role."""

    role: object

    @property
    def resource_type(self) -> object:
        return self.annotation

    def __repr__(self) -> str:
        return f"ResourceRef({self.stable_name!r})"


def _protocol_name(protocol: object) -> str:
    protocol_name = getattr(protocol, "__name__", None)
    if not isinstance(protocol_name, str) or not protocol_name:
        raise TypeError("ACPY-FLOW-002: protocol must be a named protocol type")
    return "".join(
        ("_" + char.lower()) if char.isupper() and index else char.lower()
        for index, char in enumerate(protocol_name)
    )


def export_flow(queue: object, *, protocol: object) -> SymbolicValue | FlowBundle:
    """Create a structural Flow value from a declared queue specification."""

    from ._resources import QueueSpec

    if isinstance(queue, (tuple, list)):
        if not queue:
            raise TypeError("ACPY-FLOW-007: export_flow queue tuple must be non-empty")
        if any(not isinstance(item, QueueSpec) for item in queue):
            raise TypeError("ACPY-FLOW-001: export_flow requires queue declarations")
        if len({id(item) for item in queue}) != len(queue):
            raise TypeError("ACPY-FLOW-006: a queue cannot be exported more than once")
        payload = queue[0].payload_type
        if any(item.payload_type != payload for item in queue):
            raise TypeError("ACPY-FLOW-005: FlowBundle queues must share one payload")
        normalized = _protocol_name(protocol)
        if any(item.protocol != normalized for item in queue):
            raise TypeError(
                "ACPY-FLOW-003: queue protocol does not match exported Flow protocol"
            )
        if any(item._flow_exported for item in queue):
            raise TypeError("ACPY-FLOW-006: a queue cannot be exported more than once")
        leaves = tuple(export_flow(item, protocol=protocol) for item in queue)
        assert all(isinstance(item, SymbolicValue) for item in leaves)
        return FlowBundle(payload, protocol, (len(queue),), leaves)
    if not isinstance(queue, QueueSpec):
        raise TypeError("ACPY-FLOW-001: export_flow requires a queue declaration")
    normalized = _protocol_name(protocol)
    if queue.protocol != normalized:
        raise TypeError(
            "ACPY-FLOW-003: queue protocol does not match exported Flow protocol"
        )
    if queue._flow_exported:
        raise TypeError("ACPY-FLOW-006: a queue cannot be exported more than once")
    object.__setattr__(queue, "_flow_exported", True)
    annotation = Flow[queue.payload_type, protocol]
    return SymbolicValue(stable_name=f"{queue.name}.flow", annotation=annotation)


def import_flow(flow: object, queue: object) -> None:
    """Attach one symbolic Flow to a declared destination queue."""

    from ._resources import QueueSpec

    if isinstance(flow, FlowBundle):
        if not isinstance(queue, (tuple, list)) or len(queue) != len(flow.leaves):
            raise TypeError("ACPY-FLOW-007: Queue tuple and FlowBundle shape must match")
        if flow.shape != (len(queue),):
            raise TypeError("ACPY-FLOW-007: Queue tuple and FlowBundle shape must match")
        if len({id(item) for item in queue}) != len(queue):
            raise TypeError("ACPY-FLOW-006: destination queues must be unique")
        # Validate every edge before consuming any leaf, so failure is atomic.
        for leaf, destination in zip(flow.leaves, queue, strict=True):
            _validate_import(leaf, destination)
        for leaf, destination in zip(flow.leaves, queue, strict=True):
            object.__setattr__(leaf, "_flow_consumed", True)
            object.__setattr__(destination, "_flow_imported", True)
        return
    _validate_import(flow, queue)
    assert isinstance(flow, SymbolicValue)
    object.__setattr__(flow, "_flow_consumed", True)
    object.__setattr__(queue, "_flow_imported", True)


def _validate_import(flow: object, queue: object) -> None:
    from ._resources import QueueSpec

    if not isinstance(flow, SymbolicValue) or get_origin(flow.annotation) is not Flow:
        raise TypeError("ACPY-FLOW-004: import_flow requires a Flow symbolic value")
    if not isinstance(queue, QueueSpec):
        raise TypeError("ACPY-FLOW-001: import_flow requires a queue declaration")
    payload, protocol = get_args(flow.annotation)
    payload = getattr(payload, "__forward_arg__", payload)
    normalized = _protocol_name(protocol)
    if payload != queue.payload_type:
        raise TypeError("ACPY-FLOW-005: Flow payload does not match destination queue")
    if normalized != queue.protocol:
        raise TypeError("ACPY-FLOW-003: Flow protocol does not match destination queue")
    if flow._flow_consumed:
        raise TypeError("ACPY-FLOW-006: Flow value cannot be imported more than once")
    if queue._flow_imported:
        raise TypeError("ACPY-FLOW-006: a queue cannot import more than one Flow")


def _test_symbolic(stable_name: str, annotation: object) -> SymbolicValue:
    """Create a symbolic value for contract tests without elaboration state."""

    return SymbolicValue(stable_name=stable_name, annotation=annotation)
