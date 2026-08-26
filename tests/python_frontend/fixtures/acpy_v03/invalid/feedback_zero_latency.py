"""Invalid: every feedback cycle needs a Queue edge with positive latency."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def feedback_zero_latency() -> None:
    feedback = ac.queue.deferred(ac.u16)
    source = ac.source(ac.u16)
    joined = ac.merge((source, feedback.output), policy="round_robin")
    completed = ac.queue(
        joined, depth=1, latency=0, rate=1, domain="core"
    )
    feedback.bind(completed)
