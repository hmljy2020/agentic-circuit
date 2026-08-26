"""Boundary: struct constructor fields must follow frozen declaration order."""

from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Pair:
    first: ac.u16
    second: ac.u16


def swap_order(value: Pair) -> Pair:
    return Pair(second=value.second, first=value.first)


@ac.system
def struct_field_order() -> None:
    source = ac.source(Pair)
    result = ac.compute(source, swap_order)
    ac.observe(result)

