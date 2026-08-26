"""Boundary: division is not in the closed v0.3 compute binary-operator set."""

from __future__ import annotations

import agentic_circuit as ac


def divide(value: ac.u16) -> ac.u16:
    return value // 2


@ac.system
def compute_division() -> None:
    source = ac.source(ac.u16)
    result = ac.compute(source, divide)
    ac.observe(result)

