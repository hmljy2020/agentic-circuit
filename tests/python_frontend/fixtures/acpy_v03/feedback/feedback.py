from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Token:
    value: ac.u16


def identity(value: Token) -> Token:
    return value


@ac.system
def feedback() -> None:
    completion = ac.queue.deferred(Token)
    source = ac.source(Token)
    selected = ac.merge((source, completion.output), policy="round_robin")
    buffered = ac.queue(
        selected, depth=2, latency=1, rate=1, domain="core"
    )
    completed = ac.compute(buffered, identity)
    completion.bind(completed)
    ac.observe(completion.output)
