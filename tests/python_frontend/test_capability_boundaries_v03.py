"""Executable map of the implemented ACPy v0.3 surface and its hard edges.

Positive cases must emit their adjacent ACIR through the real frontend and pass
the native verifier.  Negative cases assert a precise early diagnostic and
therefore prove that unsupported Python is not silently interpreted.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acpy_v03"


class CapabilityBoundariesV03Test(unittest.TestCase):
    def _capture(self, relative: str, system: str, consts=()):
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )

        return elaborate_semantic_v03(
            SemanticCaptureRequest(FIXTURES / relative, REPOSITORY, system, consts)
        )

    def _verify_native(self, text: str) -> None:
        """Use the built dialect parser and model verifier, never a text stub."""
        verifier = REPOSITORY / "build" / "dev-llvm22" / "bin" / "acir-opt"
        if not verifier.is_file():
            self.skipTest("acir-opt is not built")
        result = subprocess.run(
            (
                str(verifier),
                "--pass-pipeline=builtin.module(ac-verify-model)",
                "-o",
                "/dev/null",
                "-",
            ),
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_supported_surface_matches_adjacent_acir_and_native_verifier(self) -> None:
        """Each major P3-P5 capability has an independently reviewable program."""
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03
        from agentic_circuit._static_eval import FrozenMap

        specialization = (
            ("cfg", FrozenMap((("copies", 3), ("enabled", True)))),
        )
        cases = (
            ("extended/arithmetic_family.py", "arithmetic_family", ()),
            ("extended/queue_contracts.py", "queue_contracts", ()),
            ("topology/destructuring.py", "destructuring", ()),
            (
                "topology/static_specialization.py",
                "static_specialization",
                specialization,
            ),
            ("feedback/multiple_feedback.py", "multiple_feedback", ()),
        )
        for relative, system, consts in cases:
            with self.subTest(relative=relative):
                result = self._capture(relative, system, consts)
                self.assertEqual((), result.diagnostics)
                assert result.program is not None
                artifact = lower_semantic_v03(result.program)
                golden = (FIXTURES / relative).with_suffix(".ac.mlir")
                self.assertEqual(golden.read_text(encoding="utf-8"), artifact.text)
                self._verify_native(artifact.text)

    def test_compute_expression_boundaries_fail_before_acir_emission(self) -> None:
        """The pure helper subset is deliberately closed and source-diagnosed."""
        cases = (
            ("compute_division", "ACPY-V03-VAR-003", "unsupported binary operator"),
            ("compute_conditional", "ACPY-V03-VAR-004", "IfExp"),
            ("compute_open_capture", "ACPY-V03-VAR-004", "open name 'BIAS'"),
            (
                "compute_multiple_statements",
                "ACPY-V03-VAR-001",
                "one pure return expression",
            ),
            (
                "struct_field_order",
                "ACPY-V03-VAR-003",
                "fields in declaration order",
            ),
        )
        for name, code, message in cases:
            with self.subTest(name=name):
                result = self._capture(f"invalid/{name}.py", name)
                self.assertIsNone(result.program)
                self.assertEqual(code, result.diagnostics[0].code)
                self.assertIn(message, result.diagnostics[0].message)

    def test_priority_policy_reaches_semantic_graph_but_not_acir_emitter(self) -> None:
        """Expose a real partial capability instead of calling it end-to-end support."""
        from agentic_circuit._lower_acir_v03 import (
            AcirV03LoweringError,
            lower_semantic_v03,
        )
        from agentic_circuit._semantic_v03 import Policy

        result = self._capture("boundary/merge_priority.py", "merge_priority")
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        self.assertEqual(Policy("priority"), result.program.blocks[2].parameters[0].value)
        with self.assertRaisesRegex(
            AcirV03LoweringError,
            "supports only parameter-free round_robin policy",
        ):
            lower_semantic_v03(result.program)

    def test_topology_and_static_boundaries_fail_deterministically(self) -> None:
        """Dynamic shapes, invalid arity, and SSA-name reuse are never guessed."""
        cases = (
            ("fork_zero_outputs", "ACPY-V03-CALL-002", "outputs must be positive"),
            ("merge_bad_policy", "ACPY-V03-CALL-002", "unsupported merge policy"),
            (
                "collection_out_of_range",
                "ACPY-V03-CALL-003",
                "index is out of range",
            ),
            ("runtime_while", "ACPY-V03-SYNTAX-001", "While"),
            ("dynamic_queue_contract", "ACPY-V03-STATIC-001", "runtime_depth"),
            (
                "nested_destructuring",
                "ACPY-V03-SYNTAX-001",
                "result arity does not match assignment target",
            ),
            ("queue_rebind", "ACPY-V03-SYNTAX-001", "name is rebound"),
        )
        for name, code, message in cases:
            with self.subTest(name=name):
                result = self._capture(f"invalid/{name}.py", name)
                self.assertIsNone(result.program)
                self.assertEqual(code, result.diagnostics[0].code)
                self.assertIn(message, result.diagnostics[0].message)


if __name__ == "__main__":
    unittest.main()
