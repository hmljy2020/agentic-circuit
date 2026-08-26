from __future__ import annotations

import dataclasses
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
            (str(verifier), "-o", "/dev/null", "-"),
            input=first.stdout,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, second.returncode, second.stderr)

    def test_minimal_matches_golden_hash_source_map_and_native_verifier(self) -> None:
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
                self.assertEqual(count, artifact.text.count(needle))
                self._verify_native(artifact.text)

    def test_equivalent_workspace_roots_emit_identical_acir(self) -> None:
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
        result = self._capture("invalid/double_consume.py", "double_consume")

        self.assertIsNone(result.program)
        self.assertEqual("ACPY-V03-VERIFY-001", result.diagnostics[0].code)
        self.assertIn("multiple consuming uses", result.diagnostics[0].message)

    def test_emitter_rejects_semantically_known_but_unimplemented_primitive(self) -> None:
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
            AcirV03LoweringError, "P3 emitter does not support primitive 'queue'"
        ):
            lower_semantic_v03(program)


if __name__ == "__main__":
    unittest.main()
