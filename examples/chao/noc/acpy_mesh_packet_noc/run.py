from __future__ import annotations

import struct
import sys
from pathlib import Path

from agentic_circuit.runtime import ModelRuntime


def message(destination: int, payload: int) -> bytes:
    return struct.pack("<ii", destination, payload)


def main() -> None:
    expected = {
        "node0": [message(0, 100), message(0, 300)],
        "node1": [],
        "node2": [],
        # The one-hop node2 ingress has fixed priority over node0's two-hop
        # arrival at node3, so this order is part of the directed check.
        "node3": [message(3, 400), message(3, 200)],
    }
    received = {name: [] for name in expected}
    with ModelRuntime(Path(sys.argv[1])) as model:
        assert model.input_sizes == {name: 8 for name in expected}
        assert model.output_sizes == {name: 8 for name in expected}
        offers = (
            ("node0", message(0, 100)),   # Local.
            ("node0", message(3, 200)),   # East, then North.
            ("node3", message(0, 300)),   # West, then South.
            ("node2", message(3, 400)),   # One East hop.
        )
        pending = list(offers)
        for _tick in range(40):
            next_pending = []
            for ingress, raw in pending:
                if not model.offer_bytes(ingress, raw):
                    next_pending.append((ingress, raw))
            pending = next_pending
            model.step()
            for output in model.outputs:
                if model.output_ready(output):
                    raw = model.take_bytes(output)
                    assert raw is not None
                    received[output].append(raw)
            if not pending and received == expected:
                break
        assert not pending
        assert received == expected, (received, expected)
        print(f"ticks={model.tick} delivered=4 packet_bytes=8")


if __name__ == "__main__":
    main()
