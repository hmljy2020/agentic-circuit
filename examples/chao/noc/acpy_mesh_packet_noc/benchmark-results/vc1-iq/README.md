# One-VC input-queued timing milestone

This durable result uses the same 2x2 uniform Bernoulli experiment as
`../vc1/`: one-flit Packets, one VC, depth two, XY routing, three seeds, 2000
warmup cycles, and 2000 measured cycles.

The AC model in `model_iq.py` uses:

- `flow_control="credit"`
- `router_pipeline="input_queued"`
- `vc_alloc_delay=1` and `sw_alloc_delay=1`
- `credit_delay=0` and `wait_for_tail_credit=True`
- round-robin VC allocation, with speedups fixed at one

Each ingress has explicit idle/VA/SA state. Each egress has one owner, so a
granted ingress retains the output VC through switch-allocation delay and
backpressure. A directed network egress becomes allocatable again only after
the downstream ingress removes the flit and its reverse credit becomes
visible. The topology-neutral scheduler receives ingress, egress, route, and
timing descriptors; it contains no Mesh direction or coordinate decisions.

At requested injection rate 1.0, the measured means are approximately 0.6842
for the original AC elastic model, 0.5676 for AC credit ownership, 0.2283 for
AC input-queued timing, and 0.1176 for BookSim. Thus the added stages move the
curve substantially toward BookSim but do not establish cycle equivalence.
Remaining differences include BookSim's complete routing/traversal pipeline
and allocator event ordering, its network/credit channel timing, and its
source/ejection buffering semantics. Those must be aligned before treating
the curves as a quantitative validation rather than a progression study.

`ac.csv` and `booksim.csv` retain all seed samples. `summary.csv` contains the
four-model means (including the preserved elastic and owner-only data), and
`throughput.png` plots those means with seed ranges. Two complete repeated
runs produced identical files with these SHA-256 hashes:

```text
c336cf14dddb2448ab9c67d501c84032ca6e31e816c7147124cb10671e7780b6  ac.csv
56b66d1fc49278e623c29711bdd054ae0515922c9b2e11749ebc3c609b9586e8  booksim.csv
9622cc6c964d8ece675d7438557db6f548ed4801c466138bb0177e78db16cfe5  summary.csv
e9cafb484f1b08bcf8063baafbb832de9fdba58ed694088f3286b42a7d4541b3  throughput.png
```

Reproduce with `./run-iq-booksim-comparison.sh` from the example directory.
The BookSim executable defaults to `/home/lc/NoC/booksim2/src/booksim`.
