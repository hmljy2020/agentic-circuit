# ACPy Packet Mesh NoC

This executable example carries an atomic eight-byte `Message` Packet through a
2x2 XY Mesh. `route_field="destination"` selects the top-level `i32` field used
for routing; the complete Packet reaches the destination unchanged. The host
uses ABI 3 exact-width byte ingress and egress.

Run `./build-run.sh`. It reports each elaboration, freeze, lowering, C++
generation/link, shared-link, and runtime stage duration. The smoke test covers
Local, one-hop, two-hop forward, and two-hop reverse delivery.

Packet is an atomic Queue element. Its eight-byte size does not create multiple
flits, reserve a VC, add credits, or consume multiple link cycles.

Generate a deterministic Bernoulli uniform-traffic saturation curve with three
seeds:

```sh
./benchmark-plot.sh
```

The script writes `build-packet/packet-saturation.csv` and
`build-packet/packet-saturation.png`. Throughput is delivered whole Packets per
node per model tick. Every ejected Packet is decoded and checked against the
host output name; a wrong-node delivery fails the benchmark.

Run `./run-booksim-comparison.sh` for the checked-in one-VC comparison with
BookSim 2.0. Unlike disposable build output, its CSV data, exact BookSim
configuration, and plot are stored under `benchmark-results/vc1/`.
