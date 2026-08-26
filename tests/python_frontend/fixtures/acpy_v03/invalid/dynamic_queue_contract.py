"""Boundary: Queue depth/latency/rate/domain values must be statically known."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def dynamic_queue_contract() -> None:
    source = ac.source(ac.u16)
    buffered = ac.queue(source, depth=runtime_depth)
    ac.observe(buffered)

