import agentic_circuit as ac


@ac.struct
class Work:
    lane: ac.u2
    sequence: ac.u16
    ready: ac.i1
    latency: ac.u8
    value: ac.u32


def identity(work: Work) -> Work:
    return work


@ac.system
def davincioo() -> None:
    source = ac.source(Work)
    decoded = ac.compute(source, identity)
    lanes = ac.route(decoded, by=Work.lane, outputs=4)

    completion_feedback = ac.queue.deferred(Work)
    issued = ac.issue(
        lanes,
        wakeup=completion_feedback.output,
        dependency_key=Work.sequence,
        dependency_ready=Work.ready,
        wakeup_key=Work.sequence,
        entries=16,
        width=4,
        policy="oldest_ready",
    )
    completed = ac.engine(
        issued,
        latency_by=Work.latency,
        inflight=16,
        initiation_interval=1,
        kind="integer",
    )

    wakeups = ac.merge(completed, policy="round_robin")
    completion_feedback.bind(wakeups)

    retired = ac.reorder(
        completed,
        by=Work.sequence,
        entries=32,
        width=4,
        policy="in_order",
    )
    ac.sink(retired)
