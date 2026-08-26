"""Invalid: deferred output and bound Queue payload types must agree."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def deferred_type_conflict() -> None:
    feedback = ac.queue.deferred(ac.u16)
    source = ac.source(ac.u32)
    feedback.bind(source)
