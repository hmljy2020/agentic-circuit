# One-VC credit-owner milestone

This durable result uses the same 2x2, uniform Bernoulli, one-flit, depth-two,
three-seed, 2000-warmup and 2000-measurement setup as `../vc1/`.

The AC model differs only in the intended microarchitecture experiment:

- `flow_control="credit"`
- `router_pipeline="single_stage_elastic"`
- `credit_delay=0`
- `wait_for_tail_credit=True`
- round-robin arbitration

Each directed network egress owns its downstream VC from data transfer until
the neighbor removes that single flit and returns a credit.  A zero configured
credit delay still crosses the reverse credit Queue and therefore returns no
earlier than the next tick.  Local ejection has no network VC owner.

The measured mean at requested injection rate 1.0 is approximately 0.5676
packets/node/tick, versus 0.6842 for the earlier elastic baseline and 0.1176
for this BookSim IQ configuration.  This milestone isolates VC reservation;
it intentionally does not yet include VA/SA pipeline stages.
