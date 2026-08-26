"""Use flat tuple/list result targets and a literal Queue collection.

Route results are assigned to a tuple, merge consumes a list literal, and fork
results are assigned to a list.  These are static Python shapes, not runtime
containers.
"""

from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Packet:
    lane: ac.i1
    payload: ac.u32


@ac.system
def destructuring() -> None:
    source = ac.source(Packet)
    even, odd = ac.route(source, by=Packet.lane, outputs=2)
    joined = ac.merge([even, odd], policy="round_robin")
    [primary, mirror] = ac.fork(joined, outputs=2)
    ac.observe(primary)
    ac.observe(mirror)
