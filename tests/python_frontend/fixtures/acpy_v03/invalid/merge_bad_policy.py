"""Boundary: merge policy is one of round_robin, priority, or oldest."""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def merge_bad_policy() -> None:
    left = ac.source(ac.u16)
    right = ac.source(ac.u16)
    joined = ac.merge((left, right), policy="random")
    ac.observe(joined)

