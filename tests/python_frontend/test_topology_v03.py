"""Executable examples and contract boundaries for static ACPy topology."""

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
        """The main example exposes typed variadic ports and lexical scope I/O."""
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
        """Const control flow changes topology at elaboration, never at runtime."""
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

    def test_two_and_three_consumers_materialize_one_flat_fork(self) -> None:
        """Broadcast sugar emits one N-output fork in stable consumer order."""
        cases = (
            ("topology/double_consume.py", "double_consume", 2),
            ("topology/triple_consume.py", "triple_consume", 3),
        )
        for relative, system, outputs in cases:
            with self.subTest(relative=relative):
                result = self._capture(relative, system)
                self.assertEqual((), result.diagnostics)
                assert result.program is not None
                forks = tuple(
                    block for block in result.program.blocks
                    if block.opcode == "fork"
                )
                self.assertEqual(1, len(forks))
                self.assertEqual(outputs, len(forks[0].results[0].queues))
                for queue in forks[0].results[0].queues:
                    contract = result.program.queues[int(queue[1:])].constraint
                    self.assertEqual(
                        (1, 1, 1, "core"),
                        (
                            contract.depth,
                            contract.latency,
                            contract.rate,
                            contract.domain,
                        ),
                    )
                consumers = tuple(
                    block.inputs[0].queues[0]
                    for block in result.program.blocks
                    if block.opcode == "compute"
                )
                self.assertEqual(forks[0].results[0].queues, consumers)

    def test_observation_does_not_materialize_fork(self) -> None:
        """One sink plus any number of observations remains a linear Queue."""
        result = self._capture(
            "topology/consume_and_observe.py", "consume_and_observe"
        )
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        self.assertNotIn(
            "fork", tuple(block.opcode for block in result.program.blocks)
        )

    def test_explicit_fork_is_not_normalized_again(self) -> None:
        """An explicit fork already leaves its input with one consuming use."""
        result = self._capture(
            "topology/static_topology.py",
            "static_topology",
            self._consts(tap_input=True),
        )
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        self.assertEqual(
            1, sum(block.opcode == "fork" for block in result.program.blocks)
        )

    def test_cross_scope_fanout_rebuilds_ports_and_instances(self) -> None:
        """The synthesized fork lives beside its producer and exports its results."""
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03

        result = self._capture(
            "topology/cross_scope_fanout.py", "cross_scope_fanout"
        )
        self.assertEqual((), result.diagnostics)
        assert result.program is not None
        program = result.program
        producer, left, right = program.scopes[1:]
        fork = next(block for block in program.blocks if block.opcode == "fork")
        self.assertEqual(producer.id, fork.scope)
        self.assertEqual(("q0",), producer.inputs)
        self.assertEqual(fork.results[0].queues, producer.outputs)
        self.assertEqual((fork.results[0].queues[0],), left.inputs)
        self.assertEqual((fork.results[0].queues[1],), right.inputs)

        text = lower_semantic_v03(program).text
        self.assertIn("ac.v03.fork %q1", text)
        self.assertIn("ac.instance @left_s2", text)
        self.assertIn("ac.instance @right_s3", text)

    def test_static_topology_is_byte_deterministic(self) -> None:
        """Repeated elaboration and lowering reproduce the reviewable golden."""
        from agentic_circuit._lower_acir_v03 import lower_semantic_v03

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
        first_acir = lower_semantic_v03(first.program)
        second_acir = lower_semantic_v03(second.program)
        self.assertEqual(first_acir.text, second_acir.text)
        self.assertEqual(
            (FIXTURES / "topology/static_topology.ac.mlir").read_text(
                encoding="utf-8"
            ),
            first_acir.text,
        )

    def test_zero_route_outputs_is_rejected(self) -> None:
        """A variadic result port still enforces its declared minimum arity."""
        result = self._capture(
            "invalid/route_zero_outputs.py", "route_zero_outputs"
        )

        self.assertIsNone(result.program)
        self.assertEqual("ACPY-V03-CALL-002", result.diagnostics[0].code)
        self.assertIn("route outputs must be positive", result.diagnostics[0].message)

    def test_payload_rate_and_selector_shape_errors_are_rejected(self) -> None:
        """Independent Queue payload, rate, and field-selector contracts fail early."""
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
