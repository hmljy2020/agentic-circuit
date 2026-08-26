"""Boundary: a compute helper is exactly one return expression in v0.3."""

from __future__ import annotations

import agentic_circuit as ac


def staged(value: ac.u16) -> ac.u16:
    intermediate = value + 1
    return intermediate


@ac.system
def compute_multiple_statements() -> None:
    source = ac.source(ac.u16)
    result = ac.compute(source, staged)
    ac.observe(result)

