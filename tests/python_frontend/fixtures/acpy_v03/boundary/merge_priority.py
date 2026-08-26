"""Known seam: semantic capture accepts priority, but ACIR emission does not.

This is not an invalid semantic program, so it lives outside ``invalid/``.  It
documents a capability that stops specifically at the semantic-to-ACIR step.
"""

from __future__ import annotations

import agentic_circuit as ac


@ac.system
def merge_priority() -> None:
    left = ac.source(ac.u16)
    right = ac.source(ac.u16)
    joined = ac.merge((left, right), policy="priority")
    ac.observe(joined)

