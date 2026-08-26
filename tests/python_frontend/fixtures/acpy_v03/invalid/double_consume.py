from __future__ import annotations

import agentic_circuit as ac


def increment(value: ac.u16) -> ac.u16:
    return value + 1


@ac.system
def double_consume() -> None:
    source = ac.source(ac.u16)
    left = ac.compute(source, increment)
    right = ac.compute(source, increment)
    ac.observe(left)
    ac.observe(right)
