from __future__ import annotations

import struct
import sys
from pathlib import Path

from agentic_circuit.runtime import ModelRuntime


def message(destination: int, payload: int) -> bytes:
    return struct.pack("<ii", destination, payload)


def assert_queue_invariants(model: ModelRuntime) -> None:
    statistics = model.statistics()
    queue_paths = {path for path, name in statistics if name == "queue_occupancy"}
    for path in queue_paths:
        accepted = statistics[(path, "accepted_transactions")]
        completed = statistics[(path, "completed_transactions")]
        occupancy = statistics[(path, "queue_occupancy")]
        peak = statistics[(path, "queue_occupancy_peak")]
        assert accepted == completed + occupancy, (path, statistics)
        assert peak <= 2, (path, peak)


def run_pair(model: ModelRuntime) -> tuple[list[bytes], list[int]]:
    packets = [message(1, 100), message(1, 101)]
    pending = list(packets)
    received: list[bytes] = []
    delivery_ticks: list[int] = []
    for _ in range(80):
        if pending and model.offer_bytes("node0", pending[0]):
            pending.pop(0)
        model.step()
        if model.output_ready("node1"):
            value = model.take_bytes("node1")
            assert value is not None
            received.append(value)
            delivery_ticks.append(model.tick)
        for output in ("node0", "node2", "node3"):
            assert not model.output_ready(output), output
        if not pending and len(received) == len(packets):
            break
    assert not pending
    assert received == packets, received
    return received, delivery_ticks


def main() -> None:
    with ModelRuntime(Path(sys.argv[1])) as model:
        _, delivery_ticks = run_pair(model)
        assert delivery_ticks == [10, 15], delivery_ticks
        assert_queue_invariants(model)

        model.reset()
        _, repeated_ticks = run_pair(model)
        assert repeated_ticks == delivery_ticks, (delivery_ticks, repeated_ticks)

        model.reset()
        blocked_packets = [message(1, payload) for payload in range(200, 204)]
        blocked_pending = list(blocked_packets)
        for _ in range(24):
            if blocked_pending and model.offer_bytes("node0", blocked_pending[0]):
                blocked_pending.pop(0)
            model.step()
        assert model.output_ready("node1")
        blocked_received: list[bytes] = []
        for _ in range(80):
            if blocked_pending and model.offer_bytes("node0", blocked_pending[0]):
                blocked_pending.pop(0)
            if model.output_ready("node1"):
                value = model.take_bytes("node1")
                assert value is not None
                blocked_received.append(value)
            model.step()
            if not blocked_pending and len(blocked_received) == len(blocked_packets):
                break
        if model.output_ready("node1"):
            value = model.take_bytes("node1")
            assert value is not None
            blocked_received.append(value)
        assert not blocked_pending
        assert blocked_received == blocked_packets, blocked_received
        assert_queue_invariants(model)

        model.reset()
        contending = {
            "node0": [message(1, 300 + index) for index in range(4)],
            "node2": [message(1, 400 + index) for index in range(4)],
        }
        received_payloads: list[int] = []
        for _ in range(160):
            for source, pending in contending.items():
                if pending and model.offer_bytes(source, pending[0]):
                    pending.pop(0)
            model.step()
            if model.output_ready("node1"):
                value = model.take_bytes("node1")
                assert value is not None
                destination, payload = struct.unpack("<ii", value)
                assert destination == 1
                received_payloads.append(payload)
            for output in ("node0", "node2", "node3"):
                assert not model.output_ready(output), output
            if not any(contending.values()) and len(received_payloads) == 8:
                break
        assert not any(contending.values()), contending
        assert sorted(received_payloads) == list(range(300, 304)) + list(range(400, 404))
        first_six = received_payloads[:6]
        assert any(value < 400 for value in first_six), received_payloads
        assert any(value >= 400 for value in first_six), received_payloads
        assert_queue_invariants(model)
        print(
            f"iq_delivery_ticks={delivery_ticks[0]},{delivery_ticks[1]} "
            f"backpressure_delivered={len(blocked_received)} "
            f"contention_order={','.join(map(str, received_payloads))} reset=passed"
        )


if __name__ == "__main__":
    main()
