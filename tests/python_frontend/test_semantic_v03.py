from __future__ import annotations

import unittest
from pathlib import Path


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acpy_v03"


class SemanticV03CoreTest(unittest.TestCase):
    def _payload(self):
        from agentic_circuit._semantic_v03 import NamedType

        return NamedType("struct", "PTOInst")

    def _constraint(self, **overrides):
        from agentic_circuit._semantic_v03 import QueueConstraint

        values = {
            "payload": self._payload(),
            "depth": 2,
            "latency": 1,
            "rate": 1,
            "domain": "core",
        }
        values.update(overrides)
        return QueueConstraint(**values)

    def test_queue_constraints_merge_and_freeze(self) -> None:
        from agentic_circuit._semantic_v03 import QueueConstraint

        left = QueueConstraint(self._payload(), depth=2, latency=1)
        right = QueueConstraint(self._payload(), rate=1, domain="core")

        frozen = left.merge(right).freeze()

        self.assertEqual((2, 1, 1, "core"), (
            frozen.depth,
            frozen.latency,
            frozen.rate,
            frozen.domain,
        ))

    def test_conflicting_or_unresolved_queue_constraints_are_rejected(self) -> None:
        from agentic_circuit._semantic_v03 import QueueConstraint, SemanticError

        with self.assertRaisesRegex(SemanticError, "disagree on depth"):
            QueueConstraint(self._payload(), depth=1).merge(
                QueueConstraint(self._payload(), depth=2)
            )
        with self.assertRaisesRegex(SemanticError, "unresolved"):
            QueueConstraint(self._payload(), depth=1).freeze()

    def test_linear_queue_allows_observation_beside_one_consumer(self) -> None:
        from agentic_circuit._semantic_v03 import (
            BlockInstance,
            PortGroup,
            QueueValue,
            Scope,
            SemanticProgram,
        )

        program = SemanticProgram(
            system="minimal",
            root_scope="s0",
            declarations=(),
            queues=(QueueValue("q0", self._constraint()),),
            blocks=(
                BlockInstance(
                    "b0",
                    "source",
                    "s0",
                    (),
                    (PortGroup("output", "produce", ("q0",)),),
                ),
                BlockInstance(
                    "b1",
                    "sink",
                    "s0",
                    (PortGroup("input", "consume", ("q0",)),),
                    (),
                ),
                BlockInstance(
                    "b2",
                    "observe",
                    "s0",
                    (PortGroup("input", "observe", ("q0",)),),
                    (),
                ),
            ),
            scopes=(Scope("s0", "minimal", None, ("b0", "b1", "b2")),),
        )

        program.verify(require_frozen_queues=True)
        self.assertIn(b'"contract_epoch":"0.3"', program.canonical_bytes())

    def test_multiple_consumers_and_missing_producer_are_rejected(self) -> None:
        from agentic_circuit._semantic_v03 import (
            BlockInstance,
            PortGroup,
            QueueValue,
            Scope,
            SemanticError,
            SemanticProgram,
        )

        consumers = tuple(
            BlockInstance(
                f"b{index}",
                "sink",
                "s0",
                (PortGroup("input", "consume", ("q0",)),),
                (),
            )
            for index in range(2)
        )
        missing = SemanticProgram(
            "bad",
            "s0",
            (),
            (QueueValue("q0", self._constraint()),),
            consumers,
            (Scope("s0", "bad", None, ("b0", "b1")),),
        )
        with self.assertRaisesRegex(SemanticError, "exactly one producer"):
            missing.verify()

        source = BlockInstance(
            "b0",
            "source",
            "s0",
            (),
            (PortGroup("output", "produce", ("q0",)),),
        )
        two_consumers = SemanticProgram(
            "bad",
            "s0",
            (),
            (QueueValue("q0", self._constraint()),),
            (
                source,
                BlockInstance(
                    "b1",
                    "sink",
                    "s0",
                    (PortGroup("input", "consume", ("q0",)),),
                    (),
                ),
                BlockInstance(
                    "b2",
                    "sink",
                    "s0",
                    (PortGroup("input", "consume", ("q0",)),),
                    (),
                ),
            ),
            (Scope("s0", "bad", None, ("b0", "b1", "b2")),),
        )
        with self.assertRaisesRegex(SemanticError, "multiple consuming uses"):
            two_consumers.verify()

    def test_payload_and_policy_records_are_closed(self) -> None:
        from agentic_circuit._semantic_v03 import (
            ArrayType,
            FieldDescriptor,
            NamedType,
            PayloadDeclaration,
            PayloadField,
            Policy,
            ScalarType,
        )

        u16 = ScalarType("u16", 16)
        operand = NamedType("struct", "TileOperand")
        instruction = NamedType("struct", "PTOInst")
        declaration = PayloadDeclaration(
            "struct",
            "PTOInst",
            (PayloadField("sources", ArrayType(4, operand)),),
        )
        field = FieldDescriptor(instruction, ("rob_id",), u16)
        policy = Policy("oldest", fields=(("by", field),))

        self.assertEqual("array", declaration.to_json()["fields"][0]["type"]["kind"])
        self.assertEqual("oldest", policy.to_json()["kind"])


class SemanticV03IntermediateTest(unittest.TestCase):
    def test_var_region_is_closed_and_dominance_checked(self) -> None:
        from agentic_circuit._semantic_v03 import (
            NamedType,
            SemanticError,
            VarOperation,
            VarRegion,
            VarValue,
        )

        payload = NamedType("struct", "PTOInst")
        valid = VarRegion(
            "vr0",
            (VarValue("v0", payload),),
            (
                VarOperation("vo0", "update", ("v0",), (VarValue("v1", payload),)),
                VarOperation("vo1", "yield", ("v1",), ()),
            ),
            ("v1",),
        )
        valid.verify()

        invalid = VarRegion(
            "vr0",
            (VarValue("v0", payload),),
            (
                VarOperation("vo0", "update", ("v2",), (VarValue("v1", payload),)),
                VarOperation("vo1", "yield", ("v1",), ()),
            ),
            ("v1",),
        )
        with self.assertRaisesRegex(SemanticError, "does not dominate"):
            invalid.verify()

    def test_deferred_edge_is_exactly_once_and_elaboration_only(self) -> None:
        from agentic_circuit._semantic_v03 import DeferredEdge, NamedType, SemanticError

        edge = DeferredEdge("d0", "q0", NamedType("struct", "PTOInst"))
        with self.assertRaisesRegex(SemanticError, "unbound"):
            edge.require_bound()

        bound = edge.bind("q1")
        self.assertEqual("q1", bound.require_bound())
        with self.assertRaisesRegex(SemanticError, "exactly once"):
            bound.bind("q2")

    def test_block_spec_checks_named_groups_arity_parameters_and_payload(self) -> None:
        from agentic_circuit._semantic_v03 import (
            BlockInstance,
            BlockSpec,
            NamedType,
            ParameterSpec,
            PayloadRelation,
            PortGroup,
            PortSpec,
            QueueConstraint,
            QueueValue,
            SemanticError,
            SemanticParameter,
        )

        payload = NamedType("struct", "PTOInst")
        queues = tuple(
            QueueValue(
                f"q{index}",
                QueueConstraint(payload, 1, 1, 1, "core"),
            )
            for index in range(2)
        )
        spec = BlockSpec(
            "queue",
            (PortSpec("input", "consume", "fixed", 1),),
            (PortSpec("output", "produce", "fixed", 1),),
            (ParameterSpec("enabled", "bool"),),
            (PayloadRelation(("input", "output")),),
            True,
        )
        valid = BlockInstance(
            "b0",
            "queue",
            "s0",
            (PortGroup("input", "consume", ("q0",)),),
            (PortGroup("output", "produce", ("q1",)),),
            parameters=(SemanticParameter("enabled", True),),
        )
        spec.verify_instance(valid, queues)

        wrong_group = BlockInstance(
            "b0",
            "queue",
            "s0",
            (PortGroup("wrong", "consume", ("q0",)),),
            (PortGroup("output", "produce", ("q1",)),),
            parameters=(SemanticParameter("enabled", True),),
        )
        with self.assertRaisesRegex(SemanticError, "port groups"):
            spec.verify_instance(wrong_group, queues)

    def test_catalog_rejects_private_opcode(self) -> None:
        from agentic_circuit._semantic_v03 import BlockCatalog, SemanticError

        catalog = BlockCatalog(())
        with self.assertRaisesRegex(SemanticError, "outside the official catalog"):
            catalog.lookup("private.decode")


class SemanticV03ArtifactTest(unittest.TestCase):
    def _program(self):
        from agentic_circuit._semantic_v03 import (
            NamedType,
            PortGroup,
            QueueConstraint,
            SemanticBuilder,
            VarOperation,
            VarRegion,
            VarValue,
            davincioo_core_catalog,
        )

        payload = NamedType("struct", "Token")
        constraint = QueueConstraint(payload, 1, 1, 1, "core")
        builder = SemanticBuilder("minimal", "minimal")
        source_queue = builder.add_queue(constraint)
        result_queue = builder.add_queue(constraint)
        region = VarRegion(
            "vr0",
            (VarValue("v0", payload),),
            (VarOperation("vo0", "yield", ("v0",), ()),),
            ("v0",),
        )
        builder.add_region(region)
        catalog = davincioo_core_catalog()
        builder.add_block(
            "source",
            "s0",
            (),
            (PortGroup("output", "produce", (source_queue,)),),
            catalog=catalog,
        )
        builder.add_block(
            "compute",
            "s0",
            (PortGroup("input", "consume", (source_queue,)),),
            (PortGroup("output", "produce", (result_queue,)),),
            regions=("vr0",),
            catalog=catalog,
        )
        builder.add_block(
            "observe",
            "s0",
            (PortGroup("input", "observe", (result_queue,)),),
            (),
            catalog=catalog,
        )
        return builder.freeze()

    def test_core_catalog_is_the_frozen_thirteen_op_set(self) -> None:
        from agentic_circuit._semantic_v03 import davincioo_core_catalog

        self.assertEqual(
            (
                "compute",
                "engine",
                "fork",
                "issue",
                "merge",
                "observe",
                "pool",
                "queue",
                "reorder",
                "route",
                "sink",
                "source",
                "table",
            ),
            tuple(spec.opcode for spec in davincioo_core_catalog().specs),
        )

    def test_builder_matches_canonical_semantic_golden(self) -> None:
        from agentic_circuit._semantic_v03 import SemanticArtifact

        artifact = SemanticArtifact.from_program(self._program())
        self.assertEqual(
            (FIXTURES / "minimal.semantic.json").read_bytes().rstrip(b"\n"),
            artifact.data,
        )
        self.assertTrue(artifact.sha256.startswith("sha256:"))

    def test_equivalent_builders_are_byte_identical(self) -> None:
        self.assertEqual(
            self._program().canonical_bytes(), self._program().canonical_bytes()
        )


if __name__ == "__main__":
    unittest.main()
