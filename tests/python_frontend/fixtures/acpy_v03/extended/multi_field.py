from __future__ import annotations

import agentic_circuit as ac


@ac.struct
class Input:
    left: ac.u8
    right: ac.u32


@ac.struct
class Output:
    left: ac.u8
    right: ac.u32


def transform(value: Input) -> Output:
    return Output(left=value.left + 1, right=value.right + 2)


@ac.system
def multi_field() -> None:
    source = ac.source(Input)
    result = ac.compute(source, transform)
    ac.observe(result)
