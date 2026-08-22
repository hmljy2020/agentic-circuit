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


MeshNoC = None


class ReadyValid:
    pass


tx00 = queue("tx00", payload_type="i32", protocol="ready_valid", depth=2)
tx10 = queue("tx10", payload_type="i32", protocol="ready_valid", depth=2)
tx01 = queue("tx01", payload_type="i32", protocol="ready_valid", depth=2)
tx11 = queue("tx11", payload_type="i32", protocol="ready_valid", depth=2)
in00 = export_flow((tx00,), protocol=ReadyValid)
in10 = export_flow((tx10,), protocol=ReadyValid)
in01 = export_flow((tx01,), protocol=ReadyValid)
in11 = export_flow((tx11,), protocol=ReadyValid)

rx00_queue = queue("rx00", payload_type="i32", protocol="ready_valid", depth=2)
rx10_queue = queue("rx10", payload_type="i32", protocol="ready_valid", depth=2)
rx01_queue = queue("rx01", payload_type="i32", protocol="ready_valid", depth=2)
rx11_queue = queue("rx11", payload_type="i32", protocol="ready_valid", depth=2)

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
    (rx00, rx10, rx01, rx11) = MeshNoC(
        inputs=(in00, in10, in01, in11),
        width=2,
        height=2,
        queue_depth=2,
        route_offset=0,
        virtual_channels=1,
        flow_control="ready_valid",
        link_latency=1,
        router_pipeline="single_stage_elastic",
        input_speedup=1,
        output_speedup=1,
        routing="xy",
        arbitration="round_robin",
        name="mesh",
    )
    import_flow(rx00, (rx00_queue,))
    import_flow(rx10, (rx10_queue,))
    import_flow(rx01, (rx01_queue,))
    import_flow(rx11, (rx11_queue,))
    (bad_rx0, bad_rx1, bad_rx2) = MeshNoC(
        inputs=(invalid_in0, invalid_in1, invalid_in2),
        width=3,
        height=1,
        queue_depth=2,
        route_offset=0,
        routing="xy",
        arbitration="greedy_fixed_priority",
        name="invalid_mesh",
    )
    import_flow(bad_rx0, (invalid_rx0,))
    import_flow(bad_rx1, (invalid_rx1,))
    import_flow(bad_rx2, (invalid_rx2,))


@process(kind="workload")
def inject() -> None:
    # Destination layout is X then Y in the low two bits for a 2x2 mesh.
    try_send(tx00, 0x103)  # (0,0) -> (1,1): East, then North.
    try_send(tx10, 0x403)  # Local injection at node1 contends for North.
    try_send(tx11, 0x200)  # (1,1) -> (0,0): West, then South.
    try_send(tx01, 0x302)  # (0,1) -> (0,1): Local.
    try_send(invalid_tx0, 0x3)  # X=3 is invalid in a width-3 Mesh.
    try_send(invalid_tx2, 0x0)  # Independent legal traffic must keep moving.
    yield_sim()


@process
def capture00() -> None:
    value00, arrived00 = try_recv(rx00_queue)
    yield_sim()


@process
def capture10() -> None:
    value10, arrived10 = try_recv(rx10_queue)
    yield_sim()


@process
def capture01() -> None:
    value01, arrived01 = try_recv(rx01_queue)
    yield_sim()


@process
def capture11() -> None:
    value11, arrived11 = try_recv(rx11_queue)
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
