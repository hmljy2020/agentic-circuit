from __future__ import annotations

import struct
import sys
from pathlib import Path

from agentic_circuit.runtime import ModelRuntime


def message(destination: int, payload: int) -> bytes:
    return struct.pack("<ii", destination, payload)


def main() -> None:
    packets = [message(1, 100), message(1, 101)]
    pending = list(packets)
    received: list[bytes] = []
    delivery_ticks: list[int] = []
    with ModelRuntime(Path(sys.argv[1])) as model:
        for _ in range(40):
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
            if not pending and len(received) == 2:
                break
        assert not pending
        assert received == packets, received
        assert delivery_ticks[1] - delivery_ticks[0] >= 2, delivery_ticks

        statistics = model.statistics()
        queue_paths = {path for path, name in statistics if name == "queue_occupancy"}
        for path in queue_paths:
            accepted = statistics[(path, "accepted_transactions")]
            completed = statistics[(path, "completed_transactions")]
            occupancy = statistics[(path, "queue_occupancy")]
            peak = statistics[(path, "queue_occupancy_peak")]
            assert accepted == completed + occupancy, (path, statistics)
            assert peak <= 2, (path, peak)

        model.reset()
        blocked_packets = [message(1, payload) for payload in range(200, 204)]
        blocked_pending = list(blocked_packets)
        for _ in range(16):
            if blocked_pending and model.offer_bytes("node0", blocked_pending[0]):
                blocked_pending.pop(0)
            model.step()
        assert model.output_ready("node1")
        blocked_received: list[bytes] = []
        for _ in range(40):
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

        model.reset()
        assert model.offer_bytes("node2", message(3, 300))
        legal_received = False
        for _ in range(20):
            model.step()
            if model.output_ready("node3"):
                legal_value = model.take_bytes("node3")
                assert legal_value == message(3, 300), legal_value
                legal_received = True
            for output in ("node0", "node1", "node2"):
                assert not model.output_ready(output), output
        assert legal_received
        print(
            f"owner_delivery_ticks={delivery_ticks[0]},{delivery_ticks[1]} "
            "backpressure_delivered=4 independent_delivered=1"
        )


if __name__ == "__main__":
    main()
