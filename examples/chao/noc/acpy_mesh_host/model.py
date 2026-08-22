from __future__ import annotations

from agentic_circuit import (
    export_flow,
    host_input_queue,
    import_flow,
    module,
    process,
    queue,
    system,
    try_recv,
    yield_sim,
)


MeshNoC = None


class ReadyValid:
    pass


tx00 = host_input_queue("tx00", depth=2, host_name="node0")
tx10 = host_input_queue("tx10", depth=2, host_name="node1")
tx01 = host_input_queue("tx01", depth=2, host_name="node2")
tx11 = host_input_queue("tx11", depth=2, host_name="node3")
in00 = export_flow((tx00,), protocol=ReadyValid)
in10 = export_flow((tx10,), protocol=ReadyValid)
in01 = export_flow((tx01,), protocol=ReadyValid)
in11 = export_flow((tx11,), protocol=ReadyValid)

rx00 = queue("rx00", payload_type="i32", protocol="ready_valid", depth=2)
rx10 = queue("rx10", payload_type="i32", protocol="ready_valid", depth=2)
rx01 = queue("rx01", payload_type="i32", protocol="ready_valid", depth=2)
rx11 = queue("rx11", payload_type="i32", protocol="ready_valid", depth=2)


@module
def fabric() -> None:
    (out00, out10, out01, out11) = MeshNoC(
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
    import_flow(out00, (rx00,))
    import_flow(out10, (rx10,))
    import_flow(out01, (rx01,))
    import_flow(out11, (rx11,))


@process(kind="workload")
def capture00() -> None:
    value, arrived = try_recv(rx00)
    yield_sim()


@process
def capture10() -> None:
    value, arrived = try_recv(rx10)
    yield_sim()


@process
def capture01() -> None:
    value, arrived = try_recv(rx01)
    yield_sim()


@process
def capture11() -> None:
    value, arrived = try_recv(rx11)
    yield_sim()


@system(root="fabric")
def main() -> None:
    return None
