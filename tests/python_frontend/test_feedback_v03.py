from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acpy_v03"


class FeedbackV03FrontendTest(unittest.TestCase):
    def _capture(self, relative: str, system: str):
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )

        return elaborate_semantic_v03(
            SemanticCaptureRequest(
                FIXTURES / relative,
                REPOSITORY,
                system,
            )
        )

    def test_deferred_alias_disappears_and_closes_feedback_queue(self) -> None:
        result = self._capture("feedback/feedback.py", "feedback")

        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        program = result.program
        self.assertEqual(
            ("source", "merge", "queue", "compute", "observe"),
            tuple(block.opcode for block in program.blocks),
        )
        self.assertEqual(("q1", "q0"), program.blocks[1].inputs[0].queues)
        self.assertEqual(("q0",), program.blocks[3].results[0].queues)
        self.assertEqual(4, len(program.queues))
        self.assertEqual(2, program.queues[3].constraint.depth)
        artifact = program.canonical_bytes()
        self.assertNotIn(b"deferred", artifact)
        self.assertEqual(artifact, program.canonical_bytes())

    def test_unbound_double_bind_and_payload_conflict_are_rejected(self) -> None:
        cases = (
            (
                "invalid/deferred_unbound.py",
                "deferred_unbound",
                "ACPY-V03-DEFERRED-003",
                "is unbound",
            ),
            (
                "invalid/deferred_double_bind.py",
                "deferred_double_bind",
                "ACPY-V03-DEFERRED-002",
                "more than once",
            ),
            (
                "invalid/deferred_type_conflict.py",
                "deferred_type_conflict",
                "ACPY-V03-DEFERRED-002",
                "payload type does not match",
            ),
            (
                "invalid/deferred_self_bind.py",
                "deferred_self_bind",
                "ACPY-V03-DEFERRED-002",
                "own output",
            ),
            (
                "invalid/feedback_zero_latency.py",
                "feedback_zero_latency",
                "ACPY-V03-VERIFY-001",
                "latency must be at least one",
            ),
        )
        for relative, system, code, message in cases:
            with self.subTest(relative=relative):
                result = self._capture(relative, system)
                self.assertIsNone(result.program)
                self.assertEqual(code, result.diagnostics[0].code)
                self.assertIn(message, result.diagnostics[0].message)


if __name__ == "__main__":
    unittest.main()
