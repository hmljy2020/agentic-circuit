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
