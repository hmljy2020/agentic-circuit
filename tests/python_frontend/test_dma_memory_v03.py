from __future__ import annotations

from pathlib import Path
import unittest


SOURCE = """
import agentic_circuit as ac

@ac.struct
class DmaOp:
    src: ac.u64
    dst: ac.u64
    size: ac.u32
    tag: ac.u16

@ac.system
def pipeline() -> None:
    dram = ac.memory(
        kind="dram",
        capacity_bytes=1073741824,
        read_latency=40,
        write_latency=20,
        bytes_per_cycle=32,
    )
    sram = ac.memory(
        kind="sram",
        capacity_bytes=1048576,
        read_latency=2,
        write_latency=2,
        bytes_per_cycle=64,
    )
    tma = ac.source(DmaOp, depth=1, latency=1)
    with ac.scope("tma_engine"):
        def execute(op):
            data = dram.read(op.src, size=op.size)
            sram.write(op.dst, data)
            return op
        tma_done = tma.process(execute, inflight=1, depth=1)
    ac.sink(tma_done)
"""


class DmaMemoryV03Test(unittest.TestCase):
    def test_parses_memory_resources_and_serial_process(self) -> None:
        from agentic_circuit._queue_frontend import parse_queue_program

        program = parse_queue_program(SOURCE, "pipeline")

        self.assertEqual(
            ["dram", "sram"],
            [item.name for item in program.memory_resources],
        )
        self.assertEqual(1, len(program.processes))
        process = program.processes[0]
        self.assertEqual("tma", process.input_name)
        self.assertEqual("tma_done", process.output_name)
        self.assertEqual("dram", process.helper.read_memory)
        self.assertEqual("sram", process.helper.write_memory)
        self.assertEqual(("tma_engine",), process.scope)

    def test_lowers_to_deterministic_v03_acir(self) -> None:
        from agentic_circuit._queue_frontend import lower_queue_source

        lowered = lower_queue_source(SOURCE, "pipeline")

        self.assertIn('ac.contract_epoch = "0.3"', lowered)
        self.assertIn('ac.memory.resource @dram kind "dram"', lowered)
        self.assertIn('read_latency 40 write_latency 20 bytes_per_cycle 32', lowered)
        self.assertIn('ac.memory.resource @sram kind "sram"', lowered)
        self.assertIn('ac.scope @tma_engine', lowered)
        self.assertIn('ac.queue.process', lowered)
        self.assertIn('ac.memory.read @dram', lowered)
        self.assertIn('ac.memory.write @sram', lowered)
        self.assertLess(
            lowered.index("ac.memory.read @dram"),
            lowered.index("ac.memory.write @sram"),
        )
        self.assertLess(
            lowered.index("ac.memory.write @sram"),
            lowered.index("ac.queue.process.yield"),
        )
        self.assertEqual(lowered, lower_queue_source(SOURCE, "pipeline"))

    def test_rejects_non_linear_transfer(self) -> None:
        from agentic_circuit._queue_frontend import (
            QueueFrontendError,
            parse_queue_program,
        )

        malformed = SOURCE.replace(
            "sram.write(op.dst, data)", "sram.write(op.dst, op)"
        )
        with self.assertRaisesRegex(QueueFrontendError, "must consume the read transfer"):
            parse_queue_program(malformed, "pipeline")

    def test_rejects_multiple_clients_for_one_memory(self) -> None:
        from agentic_circuit._queue_frontend import (
            QueueFrontendError,
            parse_queue_program,
        )

        malformed = SOURCE.replace(
            "    ac.sink(tma_done)",
            """    other = ac.source(DmaOp)
    with ac.scope(\"other_engine\"):
        def other_execute(op):
            data = dram.read(op.src, size=op.size)
            sram.write(op.dst, data)
            return op
        other_done = other.process(other_execute)
    ac.sink(tma_done)
    ac.sink(other_done)""",
        )
        with self.assertRaisesRegex(QueueFrontendError, "exactly one process client"):
            parse_queue_program(malformed, "pipeline")

    def test_rejects_invalid_memory_contract(self) -> None:
        from agentic_circuit._queue_frontend import (
            QueueFrontendError,
            parse_queue_program,
        )

        malformed = SOURCE.replace("bytes_per_cycle=32", "bytes_per_cycle=0")
        with self.assertRaisesRegex(
            QueueFrontendError, "bytes_per_cycle must be positive"
        ):
            parse_queue_program(malformed, "pipeline")

    def test_rejects_reusing_process_helper(self) -> None:
        from agentic_circuit._queue_frontend import (
            QueueFrontendError,
            parse_queue_program,
        )

        malformed = SOURCE.replace(
            "        tma_done = tma.process(execute, inflight=1, depth=1)",
            """        tma_done = tma.process(execute, inflight=1, depth=1)
        duplicate = tma_done.process(execute)""",
        ).replace("    ac.sink(tma_done)", "    ac.sink(duplicate)")
        with self.assertRaisesRegex(QueueFrontendError, "consumed exactly once"):
            parse_queue_program(malformed, "pipeline")

    def test_process_participates_in_queue_fanout(self) -> None:
        from agentic_circuit._queue_frontend import lower_queue_source

        fanout = (
            SOURCE.replace(
                "    with ac.scope(\"tma_engine\"):",
                """    mirrored = tma.apply(lambda item: item)
    with ac.scope("tma_engine"):""",
            )
            .replace(
                "    ac.sink(tma_done)",
                "    ac.sink(tma_done)\n    ac.sink(mirrored)",
            )
        )

        lowered = lower_queue_source(fanout, "pipeline")

        self.assertIn("ac.broadcast %tma", lowered)
        self.assertIn("ac.queue.process %tma__fanout", lowered)

    def test_checked_in_example_matches_golden(self) -> None:
        from agentic_circuit._queue_frontend import lower_queue_source

        root = Path(__file__).resolve().parents[2]
        source = root / "examples" / "v03" / "tma_dma_memory.py"
        golden = source.with_suffix(".ac.mlir")

        self.assertEqual(
            golden.read_text(encoding="utf-8"),
            lower_queue_source(
                source.read_text(encoding="utf-8"), "tma_dma_memory"
            ),
        )


if __name__ == "__main__":
    unittest.main()
