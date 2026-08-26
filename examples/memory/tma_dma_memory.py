import agentic_circuit as ac


@ac.struct
class DmaOp:
    src: ac.u64
    dst: ac.u64
    size: ac.u32
    tag: ac.u16


@ac.system
def tma_dma_memory() -> None:
    dram = ac.memory(
        kind="dram",
        capacity_bytes=1073741824,
        read_latency=40,
        write_latency=20,
        bytes_per_cycle=32,
    )
    sram = ac.memory(
        kind="sram",
        capacity_bytes=1048576,
        read_latency=2,
        write_latency=2,
        bytes_per_cycle=64,
    )
    requests = ac.source(DmaOp, depth=4, latency=1)

    with ac.scope("tma_engine"):

        def execute(op):
            data = dram.read(op.src, size=op.size)
            sram.write(op.dst, data)
            return op

        completed = requests.process(execute, inflight=1, depth=1)

    ac.sink(completed)
