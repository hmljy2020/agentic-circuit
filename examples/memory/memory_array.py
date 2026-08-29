"""Dynamic 2-D memory-bank array example for contract epoch 0.4."""

import agentic_circuit as ac


@ac.struct
class Request:
    address: ac.u8
    id: ac.u8
    write: ac.u1
    data: ac.u16


@ac.system
def memory_array() -> None:
    # requests -> tuple decode -> selected bank (latency 3) -> responses -> sink
    requests = ac.source(Request, depth=8)

    with ac.scope("sram"):
        banks = ac.array(
            (2, 2),
            ac.memory(ac.u16, entries=16, init=0, latency=3),
        )

        def decode(request):
            row = (request.address >> 5) & 1
            col = (request.address >> 4) & 1
            address = request.address & 15
            return row, col, address, request.id, request.write, request.data

        (row, col, address, request_id, write, data) = requests.apply(decode)
        responses = banks[row, col].request(
            id=request_id,
            address=address,
            write=write,
            data=data,
            depth=4,
        )

    ac.sink(responses)
