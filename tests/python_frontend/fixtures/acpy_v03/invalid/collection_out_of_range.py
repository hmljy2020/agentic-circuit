"""Invalid: Queue collection indexing is static and bounds checked."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def collection_out_of_range() -> None:
    source = ac.source(ac.u16)
    copies = ac.fork(source, outputs=2)
    ac.observe(copies[2])

