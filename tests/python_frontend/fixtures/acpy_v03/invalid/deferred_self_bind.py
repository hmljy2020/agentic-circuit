"""Invalid: binding a deferred Queue to its own output defines no producer."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def deferred_self_bind() -> None:
    feedback = ac.queue.deferred(ac.u16)
    feedback.bind(feedback.output)
