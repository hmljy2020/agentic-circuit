from __future__ import annotations

import agentic_circuit as ac


@ac.config
class Config:
    bias: ac.u16


@ac.struct
class Token:
    value: ac.u16


def mutate(record: Token) -> Token:
    print(record)
    return record


@ac.system
def invalid(cfg: ac.const[Config]) -> None:
    source = ac.source(Token)
    result = ac.compute(source, mutate)
    ac.observe(result)

