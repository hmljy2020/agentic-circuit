from __future__ import annotations

from agentic_circuit import (
    export_flow,
    host_input_queue,
    host_output_queue,
    i32,
    import_flow,
    module,
    packet,
    process,
    system,
    yield_sim,
)


MeshNoC = None


class ReadyValid:
    pass


@packet(endianness="little")
def Message(destination: i32, payload: i32) -> None:
    pass


tx0 = host_input_queue("tx0", payload_type=Message, depth=2, host_name="node0")
tx1 = host_input_queue("tx1", payload_type=Message, depth=2, host_name="node1")
tx2 = host_input_queue("tx2", payload_type=Message, depth=2, host_name="node2")
tx3 = host_input_queue("tx3", payload_type=Message, depth=2, host_name="node3")
in0 = export_flow((tx0,), protocol=ReadyValid)
in1 = export_flow((tx1,), protocol=ReadyValid)
in2 = export_flow((tx2,), protocol=ReadyValid)
in3 = export_flow((tx3,), protocol=ReadyValid)

rx0 = host_output_queue("rx0", payload_type=Message, depth=2, host_name="node0")
rx1 = host_output_queue("rx1", payload_type=Message, depth=2, host_name="node1")
rx2 = host_output_queue("rx2", payload_type=Message, depth=2, host_name="node2")
rx3 = host_output_queue("rx3", payload_type=Message, depth=2, host_name="node3")


@module
def fabric() -> None:
    (out0, out1, out2, out3) = MeshNoC(
        inputs=(in0, in1, in2, in3),
        width=2,
        height=2,
        queue_depth=2,
        route_offset=0,
        route_field="destination",
        virtual_channels=1,
        flow_control="credit",
        link_latency=1,
        router_pipeline="single_stage_elastic",
        credit_delay=0,
        vc_alloc_delay=0,
        sw_alloc_delay=0,
        wait_for_tail_credit=True,
        input_speedup=1,
        output_speedup=1,
        routing="xy",
        arbitration="round_robin",
        name="mesh_credit",
    )
    import_flow(out0, (rx0,))
    import_flow(out1, (rx1,))
    import_flow(out2, (rx2,))
    import_flow(out3, (rx3,))


@process(kind="workload")
def clock_driver() -> None:
    yield_sim()


@system(root="fabric")
def main() -> None:
    return None
