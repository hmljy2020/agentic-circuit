from __future__ import annotations

import importlib
import unittest
from dataclasses import FrozenInstanceError


PUBLIC = {
    "system",
    "module",
    "extern_module",
    "generated_module",
    "struct",
    "packet",
    "transaction",
    "protocol",
    "interface",
    "process",
    "scope",
    "array",
    "instances",
    "view",
    "queue",
    "ResourceRef",
    "address_space",
    "address_map",
    "Static",
    "Flow",
    "FlowBundle",
    "export_flow",
    "import_flow",
    "Endpoint",
    "try_send",
    "try_recv",
    "yield_sim",
}


class ReadyValid:
    """Local schema marker used to form a public Flow annotation."""


class PublicApiTest(unittest.TestCase):
    def test_exact_public_inventory_is_importable(self) -> None:
        api = importlib.import_module("agentic_circuit")

        self.assertEqual(PUBLIC, set(api.__all__))
        for name in PUBLIC:
            self.assertIsNotNone(getattr(api, name))

    def test_symbolic_values_reject_python_coercion(self) -> None:
        types = importlib.import_module("agentic_circuit._types")
        value = types._test_symbolic("request", types.Flow[int, ReadyValid])

        for operation in (bool, int, hash, iter):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(TypeError, "ACPY-STATIC-002"):
                    operation(value)

    def test_symbolic_values_reject_python_equality(self) -> None:
        types = importlib.import_module("agentic_circuit._types")
        left = types._test_symbolic("left", object())
        right = types._test_symbolic("right", object())

        with self.assertRaisesRegex(TypeError, "ACPY-STATIC-002"):
            left == right

    def test_symbolic_value_repr_uses_only_stable_identity(self) -> None:
        types = importlib.import_module("agentic_circuit._types")

        value = types._test_symbolic("request", object())

        self.assertEqual("SymbolicValue('request')", repr(value))

    def test_queue_flow_constructors_preserve_payload_and_protocol(self) -> None:
        api = importlib.import_module("agentic_circuit")
        queue = api.queue(
            "out", payload_type="i32", protocol="ready_valid", depth=2
        )

        flow = api.export_flow(queue, protocol=ReadyValid)
        self.assertEqual("out.flow", flow.stable_name)
        self.assertEqual(api.Flow["i32", ReadyValid], flow.annotation)
        self.assertIsNone(api.import_flow(flow, queue))

        with self.assertRaisesRegex(TypeError, "ACPY-FLOW-001"):
            api.export_flow(object(), protocol=ReadyValid)
        with self.assertRaisesRegex(TypeError, "ACPY-FLOW-004"):
            api.import_flow(object(), queue)

    def test_import_flow_rejects_fanout(self) -> None:
        api = importlib.import_module("agentic_circuit")
        source = api.queue(
            "source", payload_type="i32", protocol="ready_valid", depth=1
        )
        first = api.queue(
            "first", payload_type="i32", protocol="ready_valid", depth=1
        )
        second = api.queue(
            "second", payload_type="i32", protocol="ready_valid", depth=1
        )
        flow = api.export_flow(source, protocol=ReadyValid)

        api.import_flow(flow, first)
        with self.assertRaisesRegex(TypeError, "ACPY-FLOW-006"):
            api.import_flow(flow, second)

    def test_flow_bundle_queue_boundaries_are_shape_checked(self) -> None:
        api = importlib.import_module("agentic_circuit")
        sources = tuple(
            api.queue(f"source{index}", payload_type="i32", protocol="ready_valid", depth=1)
            for index in range(2)
        )
        sinks = tuple(
            api.queue(f"sink{index}", payload_type="i32", protocol="ready_valid", depth=1)
            for index in range(2)
        )

        bundle = api.export_flow(sources, protocol=ReadyValid)

        self.assertIsInstance(bundle, api.FlowBundle)
        self.assertEqual((2,), bundle.shape)
        self.assertEqual(2, len(bundle.leaves))
        self.assertIsNone(api.import_flow(bundle, sinks))

    def test_decorators_create_immutable_definition_metadata(self) -> None:
        api = importlib.import_module("agentic_circuit")

        @api.module
        def producer() -> None:
            raise AssertionError("decorating a definition must not execute it")

        self.assertEqual("module", producer.kind)
        self.assertEqual(producer.function.__qualname__, producer.qualified_name)
        self.assertTrue(producer.qualified_name.endswith(".<locals>.producer"))
        self.assertEqual((), producer.explicit_options)
        with self.assertRaises(FrozenInstanceError):
            producer.kind = "system"

    def test_decorator_options_are_canonicalized(self) -> None:
        api = importlib.import_module("agentic_circuit")

        @api.generated_module(zeta=2, alpha=1)
        def generated() -> None:
            pass

        self.assertEqual(
            (("alpha", 1), ("zeta", 2)), generated.explicit_options
        )

    def test_ast_only_markers_reject_runtime_execution(self) -> None:
        api = importlib.import_module("agentic_circuit")

        operations = (
            lambda: api.scope("nested"),
            lambda: api.array(1, 2),
            lambda: api.instances(1, 2),
            lambda: api.view(object(), "field"),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(NotImplementedError):
                    operation()


if __name__ == "__main__":
    unittest.main()
