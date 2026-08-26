"""Close two independent deferred names through one shared topology cycle."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def multiple_feedback() -> None:
    first = ac.queue.deferred(ac.u16)
    second = ac.queue.deferred(ac.u16)
    source = ac.source(ac.u16)
    selected = ac.merge(
        (source, first.output, second.output), policy="round_robin"
    )
    branches = ac.fork(selected, outputs=2)
    first_buffer = ac.queue(branches[0], depth=2, latency=1)
    second_buffer = ac.queue(branches[1], depth=3, latency=2)
    first.bind(first_buffer)
    second.bind(second_buffer)
    ac.observe(first.output)
    ac.observe(second.output)

