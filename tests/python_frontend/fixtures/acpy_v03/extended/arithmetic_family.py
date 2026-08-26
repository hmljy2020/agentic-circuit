"""Exercise every binary operator currently accepted in a pure compute helper.

The closed v0.3 subset is add, subtract, multiply, bitwise-and, bitwise-or, and
bitwise-xor.  The adjacent ACIR makes each operator spelling directly visible.
"""

from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Operands:
    left: ac.u16
    right: ac.u16
    mask: ac.u16


@ac.struct
class Results:
    added: ac.u16
    subtracted: ac.u16
    multiplied: ac.u16
    conjunction: ac.u16
    disjunction: ac.u16
    exclusive: ac.u16


def evaluate(value: Operands) -> Results:
    return Results(
        added=value.left + value.right,
        subtracted=value.left - value.right,
        multiplied=value.left * value.right,
        conjunction=value.left & value.mask,
        disjunction=value.left | value.mask,
        exclusive=value.left ^ value.mask,
    )


@ac.system
def arithmetic_family() -> None:
    source = ac.source(Operands)
    result = ac.compute(source, evaluate)
    ac.observe(result)

