# Host-driven 2x2 Mesh saturation benchmark

`model.py` keeps topology and microarchitecture static in ACPy. Four explicitly
declared `host_input_queue` objects become the only runtime injection entries.
The Python `TrafficManager` owns Bernoulli rate, seed, destination pattern, and
pending packets; `ModelRuntime.step()` advances one complete model tick through
the versioned C ABI. Offers use the normal ready-valid Queue Work/Xfer barrier.

Build the model shared library and run a short deterministic curve:

```sh
./build-run.sh
```

For a longer AC curve:

```sh
PYTHONPATH=../../../src python benchmark.py \
  build-host/generated/bin/libmodel.so --warmup=1000 --measure=5000 \
  --output=build-host/ac-saturation.csv
```

Run the matching BookSim sweep:

```sh
python booksim_sweep.py --booksim=/home/lc/NoC/booksim2/src/booksim \
  --output=build-host/booksim-saturation.csv
```

Both sides use a 2x2 mesh, DOR/XY, one single-flit packet, one VC, depth 2,
unit speedups, round-robin arbitration, Bernoulli injection, and uniform or
transpose traffic. The comparison is intentionally a throughput-curve
cross-check, not cycle equivalence: BookSim's `iq` router requires explicit VC,
switch-allocation, traversal, and credit-return stages, while AC's fixed profile
is a single-stage elastic router with next-tick links. Those unavoidable timing
differences are recorded in `booksim.cfg`; no calibration factor is applied.

AC CSV throughput is delivered flits divided by measurement ticks and four
nodes. Queue statistics remain cumulative, so the script snapshots ejection
completion counters at the warmup boundary. Fixed seeds and sorted iteration
make repeated output byte-identical.
