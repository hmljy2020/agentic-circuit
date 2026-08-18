# Three-router tree

This example lowers a self-contained ACIR model to native ACSim/GFSim C++.
One root router and two child routers steer `i32` flits through seven
capacity-one FIFO queues to four sinks.

Flit bits `[1:0]` are the destination (`0` through `3`); bits `[31:2]` are
the payload. The producer repeatedly injects payloads `1` through `8` with
destinations `0, 1, 2, 3, 0, 1, 2, 3`. Each sink asserts its exact two-flit
subsequence, so routing errors, loss, duplication, and reordering fail at
runtime.

Run the sequential, memory-limited end-to-end build from the repository root:

```sh
bash examples/chao/router_tree/build-run.sh
```

The workload is intentionally cyclic. A successful run reaches the 32-tick
limit with `Incomplete`, every queue reports peak occupancy one, and every leaf
has accepted and completed at least two transactions.
