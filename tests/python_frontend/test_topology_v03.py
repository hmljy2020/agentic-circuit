from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acpy_v03"


class TopologyV03FrontendTest(unittest.TestCase):
    @staticmethod
    def _consts(*, tap_input: bool):
        from agentic_circuit._static_eval import FrozenMap

        return (
            (
                "cfg",
                FrozenMap(
                    (
                        ("lanes", 2),
                        ("observers", 1),
                        ("tap_input", tap_input),
                    )
                ),
            ),
        )

    def _capture(self, relative: str, system: str, consts=()):
        from agentic_circuit._frontend_v03 import (
            SemanticCaptureRequest,
            elaborate_semantic_v03,
        )

        return elaborate_semantic_v03(
            SemanticCaptureRequest(
                FIXTURES / relative,
                REPOSITORY,
                system,
                consts,
            )
        )

    def test_static_topology_has_named_ports_contracts_and_inferred_scope_io(self) -> None:
        from agentic_circuit._semantic_v03 import FieldDescriptor, Policy

        result = self._capture(
            "topology/static_topology.py",
            "static_topology",
            self._consts(tap_input=True),
        )
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        program = result.program

        self.assertEqual(
            ("source", "observe", "route", "merge", "fork", "queue", "observe", "observe"),
            tuple(block.opcode for block in program.blocks),
        )
        route = program.blocks[2]
        self.assertEqual(("q1", "q2"), route.results[0].queues)
        self.assertIsInstance(route.parameters[0].value, FieldDescriptor)
        merge = program.blocks[3]
        self.assertEqual(("q1", "q2"), merge.inputs[0].queues)
        self.assertEqual(Policy("round_robin"), merge.parameters[0].value)

        dispatch, arbitration = program.scopes[1:]
        self.assertEqual(("q0",), dispatch.inputs)
        self.assertEqual(("q4", "q5"), dispatch.outputs)
        self.assertEqual(("q1", "q2"), arbitration.inputs)
        self.assertEqual(("q3",), arbitration.outputs)
        self.assertEqual((4, 2, 1, "core"), (
            program.queues[6].constraint.depth,
            program.queues[6].constraint.latency,
            program.queues[6].constraint.rate,
            program.queues[6].constraint.domain,
        ))

    def test_static_if_prunes_unselected_observation(self) -> None:
        with_tap = self._capture(
            "topology/static_topology.py",
            "static_topology",
            self._consts(tap_input=True),
        )
        without_tap = self._capture(
            "topology/static_topology.py",
            "static_topology",
            self._consts(tap_input=False),
        )
        assert with_tap.program is not None and without_tap.program is not None

        self.assertEqual(8, len(with_tap.program.blocks))
        self.assertEqual(7, len(without_tap.program.blocks))
        self.assertEqual(
            3,
            sum(block.opcode == "observe" for block in with_tap.program.blocks),
        )
        self.assertEqual(
            2,
            sum(block.opcode == "observe" for block in without_tap.program.blocks),
        )

    def test_static_topology_is_byte_deterministic(self) -> None:
        first = self._capture(
            "topology/static_topology.py",
            "static_topology",
            self._consts(tap_input=True),
        )
        second = self._capture(
            "topology/static_topology.py",
            "static_topology",
            self._consts(tap_input=True),
        )
        assert first.program is not None and second.program is not None
        self.assertEqual(first.program.canonical_bytes(), second.program.canonical_bytes())

    def test_zero_route_outputs_is_rejected(self) -> None:
        result = self._capture(
            "invalid/route_zero_outputs.py", "route_zero_outputs"
        )

        self.assertIsNone(result.program)
        self.assertEqual("ACPY-V03-CALL-002", result.diagnostics[0].code)
        self.assertIn("route outputs must be positive", result.diagnostics[0].message)

    def test_payload_rate_and_selector_shape_errors_are_rejected(self) -> None:
        cases = (
            (
                "invalid/merge_payload_mismatch.py",
                "merge_payload_mismatch",
                "ACPY-V03-TYPE-003",
                "one payload type",
            ),
            (
                "invalid/queue_bad_rate.py",
                "queue_bad_rate",
                "ACPY-V03-VERIFY-001",
                "Queue rate must be positive",
            ),
            (
                "invalid/route_foreign_field.py",
                "route_foreign_field",
                "ACPY-V03-TYPE-003",
                "selector root must match",
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
