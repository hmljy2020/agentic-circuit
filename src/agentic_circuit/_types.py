"""Public annotation categories and frontend-only symbolic values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Never, TypeVar, get_args, get_origin


T = TypeVar("T")
P = TypeVar("P")
I = TypeVar("I")
R = TypeVar("R")


class Static(Generic[T]):
    """Mark an elaboration-time specialization parameter."""


class Flow(Generic[T, P]):
    """Describe a typed logical dataflow edge using protocol ``P``."""


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


def export_flow(queue: object, *, protocol: object) -> SymbolicValue:
    """Create a structural Flow value from a declared queue specification."""

    from ._resources import QueueSpec

    if not isinstance(queue, QueueSpec):
        raise TypeError("ACPY-FLOW-001: export_flow requires a queue declaration")
    protocol_name = getattr(protocol, "__name__", None)
    if not isinstance(protocol_name, str) or not protocol_name:
        raise TypeError("ACPY-FLOW-002: protocol must be a named protocol type")
    normalized = "".join(
        ("_" + char.lower()) if char.isupper() and index else char.lower()
        for index, char in enumerate(protocol_name)
    )
    if queue.protocol != normalized:
        raise TypeError(
            "ACPY-FLOW-003: queue protocol does not match exported Flow protocol"
        )
    annotation = Flow[queue.payload_type, protocol]
    return SymbolicValue(stable_name=f"{queue.name}.flow", annotation=annotation)


def import_flow(flow: object, queue: object) -> None:
    """Attach one symbolic Flow to a declared destination queue."""

    from ._resources import QueueSpec

    if not isinstance(flow, SymbolicValue) or get_origin(flow.annotation) is not Flow:
        raise TypeError("ACPY-FLOW-004: import_flow requires a Flow symbolic value")
    if not isinstance(queue, QueueSpec):
        raise TypeError("ACPY-FLOW-001: import_flow requires a queue declaration")
    payload, protocol = get_args(flow.annotation)
    payload = getattr(payload, "__forward_arg__", payload)
    protocol_name = getattr(protocol, "__name__", "")
    normalized = "".join(
        ("_" + char.lower()) if char.isupper() and index else char.lower()
        for index, char in enumerate(protocol_name)
    )
    if payload != queue.payload_type:
        raise TypeError("ACPY-FLOW-005: Flow payload does not match destination queue")
    if normalized != queue.protocol:
        raise TypeError("ACPY-FLOW-003: Flow protocol does not match destination queue")
    if flow._flow_consumed:
        raise TypeError("ACPY-FLOW-006: Flow value cannot be imported more than once")
    object.__setattr__(flow, "_flow_consumed", True)


def _test_symbolic(stable_name: str, annotation: object) -> SymbolicValue:
    """Create a symbolic value for contract tests without elaboration state."""

    return SymbolicValue(stable_name=stable_name, annotation=annotation)
