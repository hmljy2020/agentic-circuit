# v0.3 ACPy prototypes

`tma_dma_memory.py` models one blocking DMA engine without spelling request and
response queues by hand. The local `execute` helper is serial: the SRAM write
starts after the DRAM read produces its opaque transfer token, and the input
Queue item completes after the write.

For a transfer of `size` bytes, a memory access contributes
`base_latency + ceil(size / bytes_per_cycle)` cycles. The v0.3 prototype permits
one in-flight item and one process client per declared memory resource. It
models timing and backpressure, not the transferred byte values.

Lower the example with the Python frontend's `lower_queue_source` entry point.
The checked-in `tma_dma_memory.ac.mlir` is the expected ACIR. Native ACIR
parsing and verification are supported; C++, PYC, Verilog, and gfsim lowering
are outside this prototype.
