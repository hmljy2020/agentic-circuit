from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE = '''
import agentic_circuit as ac

@ac.struct
class Request:
    address: ac.u8
    id: ac.u8
    write: ac.u1
    data: ac.u16

@ac.system
def memory_array():
    requests = ac.source(Request, depth=4)
    with ac.scope("sram"):
        banks = ac.array(
            (2, 2),
            ac.memory(ac.u16, entries=16, init=0, latency=2),
        )

        def decode(request):
            row = (request.address >> 5) & 1
            col = (request.address >> 4) & 1
            address = request.address & 15
            return row, col, address, request.id, request.write, request.data

        (row, col, address, request_id, write, data) = requests.apply(decode)
        responses = banks[row, col].request(
            id=request_id,
            address=address,
            write=write,
            data=data,
            depth=2,
        )
    ac.sink(responses)
'''


class QueueArrayTest(unittest.TestCase):
    def test_tuple_decode_and_array_invoke_lower_as_one_queue(self) -> None:
        from agentic_circuit._queue_frontend import lower_queue_source

        lowered = lower_queue_source(SOURCE, "memory_array")
        self.assertEqual(1, lowered.count("ac.array @banks"))
        self.assertEqual(1, lowered.count(" = ac.array.invoke "))
        self.assertEqual(1, lowered.count("ac.transform %"))
        self.assertIn("ac.var.create", lowered)
        self.assertNotIn("ac.memory.instance @banks__", lowered)
        self.assertNotIn("ac.route ", lowered)

    def test_lowered_acir_verifies(self) -> None:
        from agentic_circuit._queue_frontend import lower_queue_source

        acir_opt = ROOT / "build/dev-llvm22/bin/acir-opt"
        if not acir_opt.is_file():
            self.skipTest("acir-opt is not built")
        result = subprocess.run(
            (str(acir_opt), "--canonicalize", "--cse", "-o", "/dev/null"),
            input=lower_queue_source(SOURCE, "memory_array"),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_memory_array_rejects_multirate_input(self) -> None:
        from agentic_circuit._queue_frontend import (
            QueueFrontendError,
            lower_queue_source,
        )

        with self.assertRaisesRegex(QueueFrontendError, "requires Queue rate 1"):
            lower_queue_source(
                SOURCE.replace(
                    "ac.source(Request, depth=4)",
                    "ac.source(Request, depth=4, rate=2)",
                ),
                "memory_array",
            )


if __name__ == "__main__":
    unittest.main()
