"""Agentic Circuit's portable Python construction surface."""

from __future__ import annotations

from pkgutil import extend_path
from typing import Never


__path__ = extend_path(__path__, __name__)

from ._definitions import (
    extern_module,
    generated_module,
    interface,
    module,
    packet,
    process,
    protocol,
    struct,
    system,
    transaction,
)
from ._resources import address_map, address_space, host_input_queue, queue
from ._types import Endpoint, Flow, FlowBundle, ResourceRef, Static, export_flow, import_flow


__all__ = (
    "system",
    "module",
    "extern_module",
    "generated_module",
    "struct",
    "packet",
    "transaction",
    "protocol",
    "interface",
    "process",
    "scope",
    "array",
    "instances",
    "view",
    "queue",
    "host_input_queue",
    "ResourceRef",
    "address_space",
    "address_map",
    "Static",
    "Flow",
    "FlowBundle",
    "export_flow",
    "import_flow",
    "Endpoint",
    "try_send",
    "try_recv",
    "yield_sim",
)


def _not_implemented(primitive: str) -> Never:
    raise NotImplementedError(
        f"{primitive} is part of the v0.2 public surface but is not implemented yet"
    )


def scope(name: str) -> Never:
    return _not_implemented("scope")


def array(*values: object) -> Never:
    return _not_implemented("array")


def instances(*values: object) -> Never:
    return _not_implemented("instances")


def view(value: object, *selectors: object) -> Never:
    return _not_implemented("view")


def try_send(queue: object, value: int) -> Never:
    return _not_implemented("try_send")


def try_recv(queue: object) -> Never:
    return _not_implemented("try_recv")


def yield_sim() -> Never:
    return _not_implemented("yield_sim")
