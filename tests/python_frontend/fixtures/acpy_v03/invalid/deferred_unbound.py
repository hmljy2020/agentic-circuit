"""Invalid: a used deferred Queue cannot remain unbound after elaboration."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def deferred_unbound() -> None:
    feedback = ac.queue.deferred(ac.u16)
    source = ac.source(ac.u16)
    joined = ac.merge((source, feedback.output), policy="round_robin")
    ac.observe(joined)
