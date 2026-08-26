"""Invalid: all inputs of one merge must carry the same payload type."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def merge_payload_mismatch() -> None:
    narrow = ac.source(ac.u16)
    wide = ac.source(ac.u32)
    merged = ac.merge((narrow, wide), policy="round_robin")
    ac.observe(merged)
