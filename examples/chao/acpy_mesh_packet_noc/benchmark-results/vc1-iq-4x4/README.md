# 4x4 one-VC input-queued throughput benchmark

This durable result compares the compiled AC 4x4 Mesh IQ profile with BookSim
under uniform Bernoulli traffic. Both configurations use deterministic XY
routing, one-flit packets, one VC, depth two, one-cycle routing/VC/switch/link
stages where the respective models expose them, three seeds, 1000 warmup
cycles, and 1000 measured cycles.

`ac.csv` and `booksim.csv` retain every seed sample. `summary.csv` contains the
mean throughput per requested injection rate, `booksim.cfg` is the exact
BookSim configuration, and `throughput.png` plots the two curves. Two complete
repeated runs produced byte-identical data and image files:

```text
30a879208026b6fbdc04fdece9c7a33e1abcbf9d61b8535c5c360fff6ba67d7c  ac.csv
c87b971c4efcc19dc5a011742c81d65c2ee7deff6eed0aaa5cf0260fadcddbf0  booksim.csv
8918c962e70af0030daaf0f095d505bdd4cc075625d946de606bbbd03513e563  summary.csv
b241660377a8b81403c48f3669d32400915cea6cbe44bb8b8b99cb24be528198  throughput.png
```

At requested injection rate 1.0, AC measures about 0.1246 delivered packets per
node per tick and BookSim reports about 0.0781 accepted packets per node per
cycle. This is a reproducible trend comparison, not a claim of cycle-level
equivalence: switch traversal/channel event ordering, credit visibility,
source/ejection buffering, allocator details, and RNG traces still differ.

Reproduce from the example directory with:

```sh
PROFILE=iq-4x4 MODEL_FILE=model_iq_4x4.py RUNNER_FILE=run_iq_4x4.py ./build-run.sh
./run-iq-4x4-booksim-comparison.sh
```

The BookSim executable defaults to `/home/lc/NoC/booksim2/src/booksim` and can
be overridden with `BOOKSIM=/path/to/booksim`.
