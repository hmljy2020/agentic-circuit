"""Boundary: runtime ``while`` cannot change a statically elaborated topology."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def runtime_while() -> None:
    source = ac.source(ac.u16)
    while source:
        ac.observe(source)

