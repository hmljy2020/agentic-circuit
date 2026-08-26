"""End-to-end ACPy v0.3 semantic-to-ACIR golden and verifier tests.

These tests always run the real AST elaborator and emitter.  Adjacent ACIR
files are expected output for review; they are never used to manufacture a
passing frontend result.
"""

from __future__ import annotations

import dataclasses
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acpy_v03"


def acir_opt() -> Path | None:
    candidate = REPOSITORY / "build" / "dev-llvm22" / "bin" / "acir-opt"
    return candidate if candidate.is_file() else None


class AcirV03LoweringTest(unittest.TestCase):
    @staticmethod
    def _minimal_consts():
        from agentic_circuit._static_eval import FrozenMap

        return (("cfg", FrozenMap((("bias", 1),))),)

    def _capture(
        self,
        relative: str,
        system: str,
        *,
        workspace: Path = REPOSITORY,
        consts=(),
    ):
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )

        return elaborate_semantic_v03(
            SemanticCaptureRequest(FIXTURES / relative, workspace, system, consts)
        )

    def _verify_native(self, text: str) -> None:
        verifier = acir_opt()
        if verifier is None:
            self.skipTest("acir-opt is not built")
        first = subprocess.run(
            (str(verifier), "-"),
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, first.returncode, first.stderr)
        second = subprocess.run(
            (
                str(verifier),
                "--pass-pipeline=builtin.module(ac-verify-model)",
                "-o",
                "/dev/null",
                "-",
            ),
            input=first.stdout,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, second.returncode, second.stderr)

    def _verify_native_failure(self, text: str, message: str) -> None:
        verifier = acir_opt()
        if verifier is None:
            self.skipTest("acir-opt is not built")
        result = subprocess.run(
            (str(verifier), "-"),
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn(message, result.stderr)

    def test_minimal_matches_golden_hash_source_map_and_native_verifier(self) -> None:
        """The smallest vertical slice is stable, attributable, and native-valid."""
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03

        result = self._capture(
            "minimal/system.py", "minimal", consts=self._minimal_consts()
        )
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        artifact = lower_semantic_v03(result.program)

        self.assertEqual(
            (FIXTURES / "minimal/system.ac.mlir").read_text(encoding="utf-8"),
            artifact.text,
        )
        self.assertRegex(artifact.sha256, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(
            (
                "b0",
                "b1",
                "b2",
                "vr0/vo0",
                "vr0/vo1",
                "vr0/vo2",
                "vr0/vo3",
                "vr0/vo4",
            ),
            tuple(identity for identity, _ in artifact.source_map),
        )
        self._verify_native(artifact.text)

    def test_extended_frontend_programs_emit_verified_acir(self) -> None:
        """Scalar, aggregate, and boolean examples exercise Var-region emission."""
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03

        cases = (
            ("extended/scalar_chain.py", "scalar_chain", "ac.compute", 2),
            ("extended/multi_field.py", "multi_field", "size = 8 : i64", 2),
            ("extended/bool_literal.py", "bool_literal", "true as !ac.var<i1>", 1),
        )
        for relative, system, needle, count in cases:
            with self.subTest(relative=relative):
                result = self._capture(relative, system)
                self.assertEqual((), result.diagnostics)
                assert result.program is not None
                artifact = lower_semantic_v03(result.program)
                golden = (FIXTURES / relative).with_suffix(".ac.mlir")
                self.assertEqual(
                    golden.read_text(encoding="utf-8"), artifact.text
                )
                self.assertEqual(count, artifact.text.count(needle))
                self._verify_native(artifact.text)

    def test_topology_and_feedback_emit_adjacent_native_verified_acir(self) -> None:
        """P4/P5 examples match adjacent ACIR and survive canonical round-trip."""
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03
        from agentic_circuit._static_eval import FrozenMap

        topology_consts = (
            (
                "cfg",
                FrozenMap(
                    (("lanes", 2), ("observers", 1), ("tap_input", True))
                ),
            ),
        )
        cases = (
            ("topology/static_topology.py", "static_topology", topology_consts),
            ("feedback/feedback.py", "feedback", ()),
        )
        for relative, system, consts in cases:
            with self.subTest(relative=relative):
                result = self._capture(relative, system, consts=consts)
                self.assertEqual((), result.diagnostics)
                assert result.program is not None
                artifact = lower_semantic_v03(result.program)
                golden = (FIXTURES / relative).with_suffix(".ac.mlir")
                self.assertEqual(golden.read_text(encoding="utf-8"), artifact.text)
                self._verify_native(artifact.text)

    def test_davincioo_main_chain_emits_frozen_lane_contracts(self) -> None:
        """The seven-block chain preserves lane segments and retirement rate."""
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03

        result = self._capture("davincioo/core.py", "davincioo")
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        artifact = lower_semantic_v03(result.program)

        self.assertEqual(
            "sha256:15653a033912a078ffc7358991b3301b358c83b4b81a541f1fb2d8de2ffc4f8b",
            artifact.sha256,
        )
        self.assertIn("ac.v03.issue", artifact.text)
        self.assertIn("entries 16 width 4", artifact.text)
        self.assertIn("dependency_key = #ac.field", artifact.text)
        self.assertIn("dependency_ready = #ac.field", artifact.text)
        self.assertIn("wakeup_key = #ac.field", artifact.text)
        self.assertIn("ac.v03.engine", artifact.text)
        self.assertIn("latency_by (#ac.field", artifact.text)
        self.assertIn("ac.v03.reorder", artifact.text)
        self.assertIn("rate = 4", artifact.text)
        self.assertIn("ac.v03.sink", artifact.text)
        self.assertNotIn("deferred", artifact.text)
        self._verify_native(artifact.text)

        bad_width = artifact.text.replace(
            "entries 16 width 4 policy", "entries 16 width 5 policy", 1
        )
        self._verify_native_failure(bad_width, "width cannot exceed")

        missing_wakeup_contract = re.sub(
            r" \{dependency_key = .*wakeup_key = .*\}",
            "",
            artifact.text,
            count=1,
        )
        self._verify_native_failure(
            missing_wakeup_contract,
            "wakeup lanes require dependency field descriptors",
        )

        bad_ready_descriptor = artifact.text.replace(
            'path = ["ready"], leaf = i1',
            'path = ["sequence"], leaf = i16',
            1,
        )
        self._verify_native_failure(
            bad_ready_descriptor,
            "dependency_ready must select an i1 field",
        )

        bad_retirement_rate = artifact.text.replace("rate = 4", "rate = 3")
        self._verify_native_failure(
            bad_retirement_rate,
            "retired Queue rate must equal retirement width",
        )

    def test_davincioo_dual_cluster_example_emits_two_engines(self) -> None:
        """One issue group may feed heterogeneous engine lane groups."""
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03

        entry = REPOSITORY / "examples" / "v03" / "davincioo_dual_cluster.py"
        result = elaborate_semantic_v03(
            SemanticCaptureRequest(
                entry,
                REPOSITORY,
                "davincioo_dual_cluster",
                (),
            )
        )
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        artifact = lower_semantic_v03(result.program)

        self.assertEqual(1, artifact.text.count("ac.v03.issue"))
        self.assertIn("entries 24 width 3", artifact.text)
        self.assertEqual(2, artifact.text.count("ac.v03.engine"))
        self.assertIn('kind "integer"', artifact.text)
        self.assertIn('kind "vector"', artifact.text)
        self.assertIn("entries 48 width 2", artifact.text)
        self.assertIn("rate = 2", artifact.text)
        self.assertNotIn("deferred", artifact.text)
        self._verify_native(artifact.text)

    def test_equivalent_workspace_roots_emit_identical_acir(self) -> None:
        """Absolute checkout paths must not leak into deterministic artifacts."""
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03

        artifacts = []
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            for name in ("left", "right"):
                workspace = parent / name
                workspace.mkdir()
                entry = workspace / "system.py"
                shutil.copyfile(FIXTURES / "minimal/system.py", entry)
                result = elaborate_semantic_v03(
                    SemanticCaptureRequest(
                        entry, workspace, "minimal", self._minimal_consts()
                    )
                )
                self.assertEqual((), result.diagnostics)
                assert result.program is not None
                artifacts.append(lower_semantic_v03(result.program))
        self.assertEqual(artifacts[0].text, artifacts[1].text)
        self.assertEqual(artifacts[0].sha256, artifacts[1].sha256)

    def test_double_consuming_use_is_rejected_before_emission(self) -> None:
        """Linear Queue ownership fails before dialect text is produced."""
        result = self._capture("invalid/double_consume.py", "double_consume")

        self.assertIsNone(result.program)
        self.assertEqual("ACPY-V03-VERIFY-001", result.diagnostics[0].code)
        self.assertIn("multiple consuming uses", result.diagnostics[0].message)

    def test_emitter_rejects_queue_with_compute_region(self) -> None:
        """Changing an opcode cannot smuggle a compute region into transport."""
        from agentic_circuit._lower_acir_v03 import (
            AcirV03LoweringError,
            lower_semantic_v03,
        )

        result = self._capture(
            "minimal/system.py", "minimal", consts=self._minimal_consts()
        )
        assert result.program is not None
        blocks = list(result.program.blocks)
        blocks[1] = dataclasses.replace(blocks[1], opcode="queue")
        program = dataclasses.replace(result.program, blocks=tuple(blocks))

        with self.assertRaisesRegex(
            AcirV03LoweringError, "queue cannot have Var regions"
        ):
            lower_semantic_v03(program)


if __name__ == "__main__":
    unittest.main()
