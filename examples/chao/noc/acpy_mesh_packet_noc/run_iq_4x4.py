from __future__ import annotations

import struct
import sys
from pathlib import Path

from agentic_circuit.runtime import ModelRuntime


def message(destination: int, payload: int) -> bytes:
    return struct.pack("<ii", destination, payload)


def main() -> None:
    expected = {
        "node0": message(0, 100),
        "node5": message(5, 200),
        "node15": message(15, 300),
    }
    offers = {
        "node0": expected["node15"],
        "node5": expected["node5"],
        "node15": expected["node0"],
    }
    received: dict[str, bytes] = {}
    with ModelRuntime(Path(sys.argv[1])) as model:
        assert model.input_sizes == {f"node{node}": 8 for node in range(16)}
        assert model.output_sizes == {f"node{node}": 8 for node in range(16)}
        for source, value in offers.items():
            assert model.offer_bytes(source, value)
        for _ in range(160):
            model.step()
            for output in model.outputs:
                if model.output_ready(output):
                    value = model.take_bytes(output)
                    assert value is not None
                    assert output not in received
                    received[output] = value
            if len(received) == len(expected):
                break
        assert received == expected, received

        statistics = model.statistics()
        queue_paths = {path for path, name in statistics if name == "queue_occupancy"}
        for path in queue_paths:
            accepted = statistics[(path, "accepted_transactions")]
            completed = statistics[(path, "completed_transactions")]
            occupancy = statistics[(path, "queue_occupancy")]
            peak = statistics[(path, "queue_occupancy_peak")]
            assert accepted == completed + occupancy, (path, statistics)
            assert peak <= 2, (path, peak)
        print(f"mesh=4x4 delivered={len(received)} ticks={model.tick}")


if __name__ == "__main__":
    main()
