from __future__ import annotations

from agentic_circuit import export_flow, import_flow, module, process, queue, system, yield_sim


# Component names are resolved from the closed schema registry during capture;
# function bodies are never executed as Python.
Crossbar = None


class ReadyValid:
    pass


def queues(prefix: str):
    return tuple(
        queue(
            f"{prefix}_vc{vc}",
            payload_type="i32",
            protocol="ready_valid",
            depth=2,
        )
        for vc in range(2)
    )


a_west_queues = queues("a_west")
a_south_queues = queues("a_south")
c_west_queues = queues("c_west")
c_south_queues = queues("c_south")

a_west = export_flow(a_west_queues, protocol=ReadyValid)
a_south = export_flow(a_south_queues, protocol=ReadyValid)
c_west = export_flow(c_west_queues, protocol=ReadyValid)
c_south = export_flow(c_south_queues, protocol=ReadyValid)

a_north_sink = queues("a_north_sink")
c_east_sink = queues("c_east_sink")
b_east_sink = queues("b_east_sink")
b_north_sink = queues("b_north_sink")


@module
def fabric() -> None:
    (a_east, a_north) = Crossbar(
        inputs=(a_west, a_south),
        virtual_channels=2,
        ingress_depth=2,
        egress_depth=2,
        route_width=1,
        name="a",
    )
    (c_east, c_north) = Crossbar(
        inputs=(c_west, c_south),
        virtual_channels=2,
        ingress_depth=2,
        egress_depth=2,
        route_width=1,
        name="c",
    )
    (b_east, b_north) = Crossbar(
        inputs=(a_east, c_north),
        virtual_channels=2,
        ingress_depth=2,
        egress_depth=2,
        route_width=1,
        name="b",
    )

    import_flow(a_north, (a_north_sink[0], a_north_sink[1]))
    import_flow(c_east, (c_east_sink[0], c_east_sink[1]))
    import_flow(b_east, (b_east_sink[0], b_east_sink[1]))
    import_flow(b_north, (b_north_sink[0], b_north_sink[1]))


@process(kind="workload")
def traffic() -> None:
    yield_sim()


@system(root="fabric")
def main() -> None:
    return None
