from __future__ import annotations

from agentic_circuit import (
    export_flow,
    import_flow,
    module,
    process,
    queue,
    system,
    try_recv,
    try_send,
    yield_sim,
)


RingNoC = None


class ReadyValid:
    pass


tx0 = queue("tx0", payload_type="i32", protocol="ready_valid", depth=2)
tx1 = queue("tx1", payload_type="i32", protocol="ready_valid", depth=2)
tx2 = queue("tx2", payload_type="i32", protocol="ready_valid", depth=2)
tx3 = queue("tx3", payload_type="i32", protocol="ready_valid", depth=2)
in0 = export_flow((tx0,), protocol=ReadyValid)
in1 = export_flow((tx1,), protocol=ReadyValid)
in2 = export_flow((tx2,), protocol=ReadyValid)
in3 = export_flow((tx3,), protocol=ReadyValid)

rx0_queue = queue("rx0", payload_type="i32", protocol="ready_valid", depth=2)
rx1_queue = queue("rx1", payload_type="i32", protocol="ready_valid", depth=2)
rx2_queue = queue("rx2", payload_type="i32", protocol="ready_valid", depth=2)
rx3_queue = queue("rx3", payload_type="i32", protocol="ready_valid", depth=2)

invalid_tx0 = queue("invalid_tx0", payload_type="i32", protocol="ready_valid", depth=2)
invalid_tx1 = queue("invalid_tx1", payload_type="i32", protocol="ready_valid", depth=2)
invalid_tx2 = queue("invalid_tx2", payload_type="i32", protocol="ready_valid", depth=2)
invalid_in0 = export_flow((invalid_tx0,), protocol=ReadyValid)
invalid_in1 = export_flow((invalid_tx1,), protocol=ReadyValid)
invalid_in2 = export_flow((invalid_tx2,), protocol=ReadyValid)
invalid_rx0 = queue("invalid_rx0", payload_type="i32", protocol="ready_valid", depth=2)
invalid_rx1 = queue("invalid_rx1", payload_type="i32", protocol="ready_valid", depth=2)
invalid_rx2 = queue("invalid_rx2", payload_type="i32", protocol="ready_valid", depth=2)


@module
def fabric() -> None:
    (rx0, rx1, rx2, rx3) = RingNoC(
        inputs=(in0, in1, in2, in3),
        queue_depth=2,
        route_offset=0,
        routing="clockwise",
        arbitration="greedy_fixed_priority",
        name="ring",
    )
    import_flow(rx0, (rx0_queue,))
    import_flow(rx1, (rx1_queue,))
    import_flow(rx2, (rx2_queue,))
    import_flow(rx3, (rx3_queue,))
    (bad_rx0, bad_rx1, bad_rx2) = RingNoC(
        inputs=(invalid_in0, invalid_in1, invalid_in2),
        queue_depth=2,
        route_offset=0,
        routing="clockwise",
        arbitration="greedy_fixed_priority",
        name="invalid_ring",
    )
    import_flow(bad_rx0, (invalid_rx0,))
    import_flow(bad_rx1, (invalid_rx1,))
    import_flow(bad_rx2, (invalid_rx2,))


@process(kind="workload")
def inject() -> None:
    # Low two bits are the Ring destination. 0x101 is node3 -> node1 and
    # crosses the wrap link; 0x202 is node2 -> node2 and remains Local.
    try_send(tx3, 0x101)
    try_send(tx2, 0x301)  # node2 -> node1 contends with node3 on wrap link.
    try_send(tx2, 0x202)
    try_send(invalid_tx0, 0x3)  # Destination 3 is invalid in a 3-node Ring.
    try_send(invalid_tx2, 0x1)  # Independent legal traffic must keep moving.
    yield_sim()


@process
def capture0() -> None:
    value0, arrived0 = try_recv(rx0_queue)
    yield_sim()


@process
def capture1() -> None:
    value1, arrived1 = try_recv(rx1_queue)
    yield_sim()


@process
def capture2() -> None:
    value2, arrived2 = try_recv(rx2_queue)
    yield_sim()


@process
def capture3() -> None:
    value3, arrived3 = try_recv(rx3_queue)
    yield_sim()


@process
def capture_invalid0() -> None:
    invalid_value0, invalid_arrived0 = try_recv(invalid_rx0)
    yield_sim()


@process
def capture_invalid1() -> None:
    invalid_value1, invalid_arrived1 = try_recv(invalid_rx1)
    yield_sim()


@process
def capture_invalid2() -> None:
    invalid_value2, invalid_arrived2 = try_recv(invalid_rx2)
    yield_sim()


@system(root="fabric")
def main() -> None:
    return None
