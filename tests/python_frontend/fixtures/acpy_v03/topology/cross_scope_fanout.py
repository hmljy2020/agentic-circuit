"""Fanout placement and ports are inferred from the normalized graph."""

import agentic_circuit as ac


def identity(value: ac.u16) -> ac.u16:
    return value


@ac.system
def cross_scope_fanout() -> None:
    source = ac.source(ac.u16)
    with ac.scope("producer"):
        produced = ac.compute(source, identity)
    with ac.scope("left"):
        ac.sink(produced)
    with ac.scope("right"):
        ac.sink(produced)
