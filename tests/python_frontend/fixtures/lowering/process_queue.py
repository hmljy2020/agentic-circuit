from __future__ import annotations

from agentic_circuit import module, process, queue, system, try_recv, try_send, yield_sim


messages = queue(
    "messages", payload_type="i32", protocol="ready_valid", depth=2
)


@module
def top() -> None:
    return


@process(kind="workload")
def workload() -> None:
    accepted = try_send(messages, 7)
    (value, received) = try_recv(messages)
    yield_sim()


@system(root="top")
def main() -> None:
    return None
