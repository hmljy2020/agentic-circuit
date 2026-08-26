"""Invalid: a Queue transport rate is a positive static integer."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def queue_bad_rate() -> None:
    source = ac.source(ac.u16)
    buffered = ac.queue(source, depth=2, latency=1, rate=0, domain="core")
    ac.observe(buffered)
