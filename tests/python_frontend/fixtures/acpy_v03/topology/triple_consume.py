"""One Queue with three consuming uses becomes one three-output fork."""

import agentic_circuit as ac


def increment(value: ac.u16) -> ac.u16:
    return value + 1


@ac.system
def triple_consume() -> None:
    source = ac.source(ac.u16)
    first = ac.compute(source, increment)
    second = ac.compute(source, increment)
    third = ac.compute(source, increment)
    ac.observe(first)
    ac.observe(second)
    ac.observe(third)
