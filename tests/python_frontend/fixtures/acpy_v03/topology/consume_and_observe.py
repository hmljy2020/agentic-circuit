"""Observation does not participate in consuming-use fanout."""

import agentic_circuit as ac


@ac.system
def consume_and_observe() -> None:
    source = ac.source(ac.u16)
    ac.sink(source)
    ac.observe(source)
    ac.observe(source)
