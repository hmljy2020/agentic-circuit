from __future__ import annotations

import agentic_circuit as ac


@ac.system
def deferred_double_bind() -> None:
    feedback = ac.queue.deferred(ac.u16)
    source = ac.source(ac.u16)
    feedback.bind(source)
    feedback.bind(source)
