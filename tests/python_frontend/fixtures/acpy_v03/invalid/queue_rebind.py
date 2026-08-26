"""Invalid: Queue names are single-assignment names in the ACPy source graph."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def queue_rebind() -> None:
    stream = ac.source(ac.u16)
    stream = ac.queue(stream)
    ac.observe(stream)

