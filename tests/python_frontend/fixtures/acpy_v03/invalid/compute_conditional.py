"""Boundary: runtime Python conditional expressions are not pure Var syntax."""

from __future__ import annotations

import agentic_circuit as ac


def choose(value: ac.u16) -> ac.u16:
    return value if value else 0


@ac.system
def compute_conditional() -> None:
    source = ac.source(ac.u16)
    result = ac.compute(source, choose)
    ac.observe(result)

