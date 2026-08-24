# One-VC AC / BookSim throughput baseline

This directory is deliberately outside `build-*` so the example's clean build
does not remove the recorded data. It contains the measured data and exact
BookSim configuration for the 2026-08-21 baseline.

Common experiment parameters:

- 2x2 mesh with deterministic XY / DOR routing
- one VC, depth two, one-flit packets
- Bernoulli uniform random destinations, including self traffic
- one packet per link per cycle and speedup one
- seeds 1, 2, and 3
- 2000 warmup cycles followed by 2000 measured cycles
- throughput normalized as accepted packets per node per cycle

`ac.csv` and `booksim.csv` contain every seed. `summary.csv` contains their
means, and `throughput.png` plots the mean with the seed range shaded.

This is a baseline comparison, not a claim of cycle-identical
microarchitecture. AC uses its current greedy fixed-priority, single-stage
elastic atomic-Packet router. BookSim uses an input-queued router with
round-robin separable allocation, explicit VC/switch allocation stages, and
tail-credit ownership. These differences are intentionally retained and are
the likely cause of the different saturation points.

Reproduce from the repository root with:

```sh
examples/chao/noc/acpy_mesh_packet_noc/run-booksim-comparison.sh
```

The BookSim path defaults to `/home/lc/NoC/booksim2/src/booksim` and can be
overridden with `BOOKSIM=/path/to/booksim`. This BookSim checkout returns 255
after a successful run because `main.cpp` returns `-1` when `Run()` is true;
the adapter accepts that code only when complete overall statistics are
present and the simulation is not marked unstable.
