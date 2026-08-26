"""Show Queue transport contracts on both a boundary and an explicit block."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def queue_contracts() -> None:
    source = ac.source(
        ac.u32, depth=3, latency=2, rate=4, domain="ingress"
    )
    buffered = ac.queue(
        source, depth=8, latency=3, rate=2, domain="execute"
    )
    ac.observe(buffered)

