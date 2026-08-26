"""Invalid: a route selector must be a field of its input payload type."""

from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Packet:
    kind: ac.u2


@ac.struct
class Foreign:
    kind: ac.u2


@ac.system
def route_foreign_field() -> None:
    source = ac.source(Packet)
    lanes = ac.route(source, by=Foreign.kind, outputs=2)
    ac.observe(lanes[0])
