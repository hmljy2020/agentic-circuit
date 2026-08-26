"""Four-lane DavinciOO frontend with two heterogeneous engine clusters.

This example is compile-time only: ACPy elaborates it into frozen v0.3 ACIR.
The issue queue has four physical lanes but may issue at most three operations
per epoch.  Integer and vector lanes then use separate engine contracts before
their completions are combined for dependency wakeup and ordered retirement.
"""

import agentic_circuit as ac


@ac.struct
class MicroOp:
    cluster: ac.u2
    rob_tag: ac.u16
    operands_ready: ac.i1
    exec_latency: ac.u8
    value: ac.u32


def decode(op: MicroOp) -> MicroOp:
    return MicroOp(
        cluster=op.cluster,
        rob_tag=op.rob_tag,
        operands_ready=op.operands_ready,
        exec_latency=op.exec_latency,
        value=op.value + 1,
    )


@ac.system
def davincioo_dual_cluster() -> None:
    fetched = ac.source(MicroOp)
    decoded = ac.compute(fetched, decode)
    enqueue_lanes = ac.route(decoded, by=MicroOp.cluster, outputs=4)

    completion_feedback = ac.queue.deferred(MicroOp)
    issued = ac.issue(
        enqueue_lanes,
        wakeup=completion_feedback.output,
        dependency_key=MicroOp.rob_tag,
        dependency_ready=MicroOp.operands_ready,
        wakeup_key=MicroOp.rob_tag,
        entries=24,
        width=3,
        policy="oldest_ready",
    )

    integer_completed = ac.engine(
        (issued[0], issued[1]),
        latency_by=MicroOp.exec_latency,
        inflight=8,
        initiation_interval=1,
        kind="integer",
    )
    vector_completed = ac.engine(
        (issued[2], issued[3]),
        latency_by=MicroOp.exec_latency,
        inflight=12,
        initiation_interval=2,
        kind="vector",
    )

    wakeups = ac.merge(
        (
            integer_completed[0],
            integer_completed[1],
            vector_completed[0],
            vector_completed[1],
        ),
        policy="round_robin",
    )
    completion_feedback.bind(wakeups)

    retired = ac.reorder(
        (
            integer_completed[0],
            integer_completed[1],
            vector_completed[0],
            vector_completed[1],
        ),
        by=MicroOp.rob_tag,
        entries=48,
        width=2,
        policy="in_order",
    )
    ac.sink(retired)
