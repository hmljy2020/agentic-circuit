"""Invalid: a variadic fork requires at least one result Queue."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def fork_zero_outputs() -> None:
    source = ac.source(ac.u16)
    copies = ac.fork(source, outputs=0)
    ac.observe(copies[0])

