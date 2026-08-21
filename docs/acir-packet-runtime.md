# ACIR Packet runtime contract

`!ac.packet<...>` is a fixed-layout, immutable value.  A Packet occupies one
Queue entry and is transferred atomically; its serialized byte width does not
imply flits, packetization, virtual channels, or link cycles.

The native lowering supports signless `i8/i16/i32/i64`, `f32`/`f64`, fixed
ACIR vectors, and non-recursive nested records.  Fields use declaration order,
natural alignment, and the declared little- or big-endian encoding.  The
derived size and alignment must exactly match DLTI, and a Packet's `size` and
`serialization_width` must match.  Invalid or incomplete layouts are rejected
before ACSim emission.

Within a process, `ac.record.create`, `ac.record.get`, `ac.record.with`,
`ac.packet.serialize`, and `ac.packet.deserialize` lower to pure generated
helpers.  Packet Queue operations use the normal proposal and Work/Xfer
barriers, so backpressure and atomic commit behavior are unchanged.  Equal-size
schemas have distinct generated C++ `gfsim::AtomicPacket` types.

ACPy exposes the same model with `@struct` and `@packet` declaration functions.
Fields may use `i8/i16/i32/i64`, `f32/f64`, `Vector[T, N]`, or a named,
non-recursive nested record. Natural layout is derived automatically. Processes
use explicit `record_get`, `record_with`, `packet_serialize`, and
`packet_deserialize` operations rather than Python attribute mutation.

Root compiler-native Queues may declare `ac.host_input` and/or
`ac.host_output`. Generated ABI version 3 retains the i32 `ac_model_offer`
entry point, provides byte-oriented `ac_model_offer_bytes` and
`ac_model_take_bytes`, and exposes exact input and output sizes. The Python
`ModelRuntime` accepts only ABI 3. Byte calls require the exact serialized
size; the caller supplies raw bytes in the Packet's declared endianness. Host
ingress and egress still commit through the Queue Work/Xfer barriers; they do
not mutate committed Queue state directly.

`RingNoC` and `MeshNoC` accept either their original `i32` payload or one
Packet payload shared by all nodes. For a Packet, `route_field` must name a
top-level `i32` field. Existing `route_offset` and topology-specific X/Y or
Ring destination widths are applied to that field, while the complete Packet
is transferred unchanged.

This layer intentionally does not define multi-flit packets.  Multi-flit NoC
support requires separate Packetizer/Reassembler components plus router VC
ownership, head/body/tail state, and credit or equivalent buffer accounting.
