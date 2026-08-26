"""Demonstrate that config-dependent control flow is elaborated, not emitted.

The test specializes ``enabled=True`` and ``copies=3``.  The false branch must
not appear in ACIR, and the loop must become three explicit observations.
"""

from __future__ import annotations

import agentic_circuit as ac


@ac.config
class BuildConfig:
    enabled: ac.i1
    copies: ac.u16


@ac.system
def static_specialization(cfg: ac.const[BuildConfig]) -> None:
    source = ac.source(ac.u8)
    if cfg.enabled:
        with ac.scope("replication"):
            copies = ac.fork(source, outputs=cfg.copies)
        for index in range(0, cfg.copies, 1):
            ac.observe(copies[index])
    else:
        ac.observe(source)

