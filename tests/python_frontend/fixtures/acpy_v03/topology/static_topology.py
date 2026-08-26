"""Cover the currently implemented static topology construction surface.

The config controls elaboration-time branching and expansion.  Nested scopes
exercise inferred lexical ports, while route/merge/fork and queue cover the
multi-port and explicit transport primitives.
"""

from __future__ import annotations

import agentic_circuit as ac


@ac.config
class TopologyConfig:
    lanes: ac.u16
    observers: ac.u16
    tap_input: ac.i1


@ac.struct
class Packet:
    kind: ac.i1
    value: ac.u32


@ac.system
def static_topology(cfg: ac.const[TopologyConfig]) -> None:
    source = ac.source(Packet, rate=2)

    if cfg.tap_input:
        ac.observe(source)

    with ac.scope("dispatch"):
        lanes = ac.route(source, by=Packet.kind, outputs=cfg.lanes)
        with ac.scope("arbitration"):
            joined = ac.merge(lanes, policy="round_robin")
        copies = ac.fork(joined, outputs=2)

    buffered = ac.queue(
        copies[0], depth=4, latency=2, rate=1, domain="core"
    )
    ac.observe(buffered)
    for index in range(cfg.observers):
        ac.observe(copies[index + 1])
