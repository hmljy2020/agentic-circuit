from __future__ import annotations

import unittest
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acpy_v03"


class FrontendV03Test(unittest.TestCase):
    @staticmethod
    def _consts():
        from agentic_circuit._static_eval import FrozenMap

        return (("cfg", FrozenMap((("bias", 1),))),)

    def _capture(self, relative: str, system: str):
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )

        return elaborate_semantic_v03(
            SemanticCaptureRequest(
                FIXTURES / relative,
                ROOT,
                system,
                self._consts(),
            )
        )

    def test_minimal_system_lowers_to_typed_semantic_graph(self) -> None:
        result = self._capture("minimal/system.py", "minimal")

        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        self.assertEqual(("source", "compute", "observe"), tuple(
            block.opcode for block in result.program.blocks
        ))
        self.assertEqual(2, len(result.program.queues))
        self.assertEqual(1, len(result.program.var_regions))
        self.assertEqual(
            (FIXTURES / "minimal/system.semantic.json").read_bytes().rstrip(b"\n"),
            result.program.canonical_bytes(),
        )

    def test_minimal_capture_is_byte_deterministic(self) -> None:
        first = self._capture("minimal/system.py", "minimal")
        second = self._capture("minimal/system.py", "minimal")

        assert first.program is not None
        assert second.program is not None
        self.assertEqual(first.program.canonical_bytes(), second.program.canonical_bytes())

    def test_equivalent_workspace_roots_are_byte_deterministic(self) -> None:
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )

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
                        entry, workspace, "minimal", self._consts()
                    )
                )
                self.assertEqual((), result.diagnostics)
                assert result.program is not None
                artifacts.append(result.program.canonical_bytes())
        self.assertEqual(artifacts[0], artifacts[1])

    def test_impure_compute_helper_is_rejected(self) -> None:
        result = self._capture("invalid/impure.py", "invalid")

        self.assertIsNone(result.program)
        self.assertEqual("ACPY-V03-VAR-001", result.diagnostics[0].code)

    def test_const_binding_is_closed(self) -> None:
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )

        result = elaborate_semantic_v03(
            SemanticCaptureRequest(
                FIXTURES / "minimal/system.py", ROOT, "minimal", ()
            )
        )
        self.assertIsNone(result.program)
        self.assertEqual("ACPY-V03-CONST-001", result.diagnostics[0].code)


if __name__ == "__main__":
    unittest.main()
