"""Boundary: a compute helper cannot capture a module-level Python value."""

from __future__ import annotations

import agentic_circuit as ac


BIAS = 4


def biased(value: ac.u16) -> ac.u16:
    return value + BIAS


@ac.system
def compute_open_capture() -> None:
    source = ac.source(ac.u16)
    result = ac.compute(source, biased)
    ac.observe(result)

