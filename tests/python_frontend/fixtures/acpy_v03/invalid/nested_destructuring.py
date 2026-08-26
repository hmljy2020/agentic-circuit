"""Boundary: primitive results support flat, but not nested, destructuring."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def nested_destructuring() -> None:
    source = ac.source(ac.u16)
    first, [second, third] = ac.fork(source, outputs=3)
    ac.observe(first)
    ac.observe(second)
    ac.observe(third)

