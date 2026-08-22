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
tx4 = host_input_queue("tx4", payload_type=Message, depth=2, host_name="node4")
tx5 = host_input_queue("tx5", payload_type=Message, depth=2, host_name="node5")
tx6 = host_input_queue("tx6", payload_type=Message, depth=2, host_name="node6")
tx7 = host_input_queue("tx7", payload_type=Message, depth=2, host_name="node7")
tx8 = host_input_queue("tx8", payload_type=Message, depth=2, host_name="node8")
tx9 = host_input_queue("tx9", payload_type=Message, depth=2, host_name="node9")
tx10 = host_input_queue("tx10", payload_type=Message, depth=2, host_name="node10")
tx11 = host_input_queue("tx11", payload_type=Message, depth=2, host_name="node11")
tx12 = host_input_queue("tx12", payload_type=Message, depth=2, host_name="node12")
tx13 = host_input_queue("tx13", payload_type=Message, depth=2, host_name="node13")
tx14 = host_input_queue("tx14", payload_type=Message, depth=2, host_name="node14")
tx15 = host_input_queue("tx15", payload_type=Message, depth=2, host_name="node15")

in0 = export_flow((tx0,), protocol=ReadyValid)
in1 = export_flow((tx1,), protocol=ReadyValid)
in2 = export_flow((tx2,), protocol=ReadyValid)
in3 = export_flow((tx3,), protocol=ReadyValid)
in4 = export_flow((tx4,), protocol=ReadyValid)
in5 = export_flow((tx5,), protocol=ReadyValid)
in6 = export_flow((tx6,), protocol=ReadyValid)
in7 = export_flow((tx7,), protocol=ReadyValid)
in8 = export_flow((tx8,), protocol=ReadyValid)
in9 = export_flow((tx9,), protocol=ReadyValid)
in10 = export_flow((tx10,), protocol=ReadyValid)
in11 = export_flow((tx11,), protocol=ReadyValid)
in12 = export_flow((tx12,), protocol=ReadyValid)
in13 = export_flow((tx13,), protocol=ReadyValid)
in14 = export_flow((tx14,), protocol=ReadyValid)
in15 = export_flow((tx15,), protocol=ReadyValid)

rx0 = host_output_queue("rx0", payload_type=Message, depth=2, host_name="node0")
rx1 = host_output_queue("rx1", payload_type=Message, depth=2, host_name="node1")
rx2 = host_output_queue("rx2", payload_type=Message, depth=2, host_name="node2")
rx3 = host_output_queue("rx3", payload_type=Message, depth=2, host_name="node3")
rx4 = host_output_queue("rx4", payload_type=Message, depth=2, host_name="node4")
rx5 = host_output_queue("rx5", payload_type=Message, depth=2, host_name="node5")
rx6 = host_output_queue("rx6", payload_type=Message, depth=2, host_name="node6")
rx7 = host_output_queue("rx7", payload_type=Message, depth=2, host_name="node7")
rx8 = host_output_queue("rx8", payload_type=Message, depth=2, host_name="node8")
rx9 = host_output_queue("rx9", payload_type=Message, depth=2, host_name="node9")
rx10 = host_output_queue("rx10", payload_type=Message, depth=2, host_name="node10")
rx11 = host_output_queue("rx11", payload_type=Message, depth=2, host_name="node11")
rx12 = host_output_queue("rx12", payload_type=Message, depth=2, host_name="node12")
rx13 = host_output_queue("rx13", payload_type=Message, depth=2, host_name="node13")
rx14 = host_output_queue("rx14", payload_type=Message, depth=2, host_name="node14")
rx15 = host_output_queue("rx15", payload_type=Message, depth=2, host_name="node15")


@module
def fabric() -> None:
    (
        out0, out1, out2, out3, out4, out5, out6, out7,
        out8, out9, out10, out11, out12, out13, out14, out15,
    ) = MeshNoC(
        inputs=(
            in0, in1, in2, in3, in4, in5, in6, in7,
            in8, in9, in10, in11, in12, in13, in14, in15,
        ),
        width=4,
        height=4,
        queue_depth=2,
        route_offset=0,
        route_field="destination",
        virtual_channels=1,
        flow_control="credit",
        link_latency=1,
        router_pipeline="input_queued",
        credit_delay=0,
        vc_alloc_delay=1,
        sw_alloc_delay=1,
        wait_for_tail_credit=True,
        input_speedup=1,
        output_speedup=1,
        routing="xy",
        arbitration="round_robin",
        name="mesh_iq_4x4",
    )
    import_flow(out0, (rx0,))
    import_flow(out1, (rx1,))
    import_flow(out2, (rx2,))
    import_flow(out3, (rx3,))
    import_flow(out4, (rx4,))
    import_flow(out5, (rx5,))
    import_flow(out6, (rx6,))
    import_flow(out7, (rx7,))
    import_flow(out8, (rx8,))
    import_flow(out9, (rx9,))
    import_flow(out10, (rx10,))
    import_flow(out11, (rx11,))
    import_flow(out12, (rx12,))
    import_flow(out13, (rx13,))
    import_flow(out14, (rx14,))
    import_flow(out15, (rx15,))


@process(kind="workload")
def clock_driver() -> None:
    yield_sim()


@system(root="fabric")
def main() -> None:
    return None
