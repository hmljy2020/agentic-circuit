from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Packet:
    kind: ac.u2


@ac.system
def route_zero_outputs() -> None:
    source = ac.source(Packet)
    lanes = ac.route(source, by=Packet.kind, outputs=0)
    ac.observe(lanes[0])
