from __future__ import annotations

import agentic_circuit as ac


@ac.config
class Config:
    bias: ac.u16


@ac.struct
class Input:
    value: ac.u16


@ac.struct
class Output:
    value: ac.u16


def transform(record: Input) -> Output:
    return Output(value=record.value + 1)


@ac.system
def minimal(cfg: ac.const[Config]) -> None:
    source = ac.source(Input)
    result = ac.compute(source, transform)
    ac.observe(result)

