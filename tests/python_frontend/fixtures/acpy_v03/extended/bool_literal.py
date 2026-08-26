"""Check that a Python bool literal becomes a typed ``!ac.var<i1>`` constant."""

from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Flag:
    value: ac.i1


def set_flag(value: Flag) -> Flag:
    return Flag(value=True)


@ac.system
def bool_literal() -> None:
    source = ac.source(Flag)
    result = ac.compute(source, set_flag)
    ac.observe(result)
