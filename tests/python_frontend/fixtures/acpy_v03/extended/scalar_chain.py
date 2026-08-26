"""Exercise scalar Queue payloads, chained consumers, and read-only observers.

Two observations of ``second`` are legal because observation does not consume
Queue ownership and therefore does not require broadcast normalization.
"""

from __future__ import annotations

import agentic_circuit as ac


def increment(value: ac.u16) -> ac.u16:
    return value + 1


@ac.system
def scalar_chain() -> None:
    source = ac.source(ac.u16)
    first = ac.compute(source, increment)
    second = ac.compute(first, increment)
    ac.observe(second)
    ac.observe(second)
