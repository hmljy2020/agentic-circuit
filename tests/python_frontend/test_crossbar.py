from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
EXAMPLE = REPOSITORY / "examples" / "chao" / "acpy_crossbar_directed" / "model.py"


def load(path: Path):
    spec = importlib.util.spec_from_file_location(f"crossbar_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def registry():
    from agentic_circuit._schemas import SchemaRegistry

    return SchemaRegistry.from_catalog(
        REPOSITORY / "schemas" / "stdlib" / "catalog.json", REPOSITORY
    )


def elaborate(path: Path, workspace: Path):
    from agentic_circuit._frontend import CaptureRequest, elaborate_frontend

    module = load(path)
    return elaborate_frontend(
        CaptureRequest(entry=path, workspace=workspace, system="main"),
        vars(module),
        registry(),
    )


class CrossbarFrontendTest(unittest.TestCase):
    def test_directed_three_crossbar_topology_flattens_and_verifies(self) -> None:
        result = elaborate(EXAMPLE, EXAMPLE.parent)
        repeated = elaborate(EXAMPLE, EXAMPLE.parent)

        self.assertEqual((), result.diagnostics)
        assert result.acir is not None and result.document is not None
        assert repeated.acir is not None and repeated.document is not None
        self.assertEqual(result.acir, repeated.acir)
        self.assertEqual(
            result.document.canonical_bytes(), repeated.document.canonical_bytes()
        )
        self.assertNotIn("ac.connect", result.acir)
        instances = [
            line.strip()
            for line in result.acir.splitlines()
            if "ac.instance" in line and " of @Crossbar__" in line
        ]
        self.assertEqual(3, len(instances))
        b = next(line for line in instances if "ac.instance @b " in line)
        self.assertIn(
            "(%a_east_0_vc0, %a_east_0_vc1, %c_north_0_vc0, %c_north_0_vc1)",
            b,
        )
        calls = [entity for entity in result.document.entities if entity.kind == "call"]
        self.assertEqual((2, 2, 2), tuple(dict((p.name, p.value) for p in c.properties)["output_ports"] for c in calls))

        from agentic_circuit._inspect import InspectionRequest, inspect_model, render_text

        connections = inspect_model(
            result.document.canonical_bytes(),
            result.acir.encode(),
            InspectionRequest("connections", "main", format="text"),
        )
        text = render_text(connections)
        self.assertIn("b.input[0] <- a.output[0]  # a_east", text)
        self.assertIn("b.input[1] <- c.output[1]  # c_north", text)

        verifier = REPOSITORY / "build" / "dev-llvm22" / "bin" / "acir-opt"
        if verifier.is_file():
            completed = subprocess.run(
                (str(verifier), "-o", "/dev/null", "-"),
                input=result.acir,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)

    def test_assignment_arity_is_part_of_specialization(self) -> None:
        source = '''from agentic_circuit import export_flow, import_flow, module, queue, system
Crossbar = None
class ReadyValid: pass
def qs(name): return tuple(queue(f"{name}{i}", payload_type="i32", protocol="ready_valid", depth=1) for i in range(2))
q0=qs("q0"); q1=qs("q1"); i0=export_flow(q0, protocol=ReadyValid); i1=export_flow(q1, protocol=ReadyValid)
s0=qs("s0"); s1=qs("s1"); s2=qs("s2")
@module
def top() -> None:
    (one,) = Crossbar(inputs=(i0,), virtual_channels=2, ingress_depth=1, egress_depth=1, route_width=1, name="one")
    (two0, two1) = Crossbar(inputs=(i1,), virtual_channels=2, ingress_depth=1, egress_depth=1, route_width=1, name="two")
    import_flow(one, (s0[0], s0[1])); import_flow(two0, (s1[0], s1[1])); import_flow(two1, (s2[0], s2[1]))
@system(root="top")
def main() -> None: return None
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.py"
            path.write_text(source)
            result = elaborate(path, Path(temporary))

        self.assertEqual((), result.diagnostics)
        assert result.document is not None and result.acir is not None
        calls = [entity for entity in result.document.entities if entity.kind == "call"]
        fingerprints = [
            dict((item.name, item.value) for item in call.properties)["specialization"]
            for call in calls
        ]
        self.assertEqual(2, len(set(fingerprints)))
        self.assertIn("Crossbar__1x1_v2", result.acir)
        self.assertIn("Crossbar__1x2_v2", result.acir)

    def test_invalid_context_targets_are_rejected(self) -> None:
        targets = ("output", "()", "(o, (p, q))", "(o, *rest)", "(o, o)")
        for target in targets:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                source = f'''from agentic_circuit import export_flow, module, queue, system
Crossbar = None
class ReadyValid: pass
q=(queue("q0", payload_type="i32", protocol="ready_valid", depth=1),)
i=export_flow(q, protocol=ReadyValid)
@module
def top() -> None:
    {target} = Crossbar(inputs=(i,), virtual_channels=1, ingress_depth=1, egress_depth=1, route_width=2)
@system(root="top")
def main() -> None: return None
'''
                path = Path(temporary) / "invalid.py"
                path.write_text(source)
                result = elaborate(path, Path(temporary))
            self.assertIn("ACPY-CROSSBAR-001", tuple(item.code for item in result.diagnostics))

    def test_16_by_16_has_exactly_256_static_candidates(self) -> None:
        declarations = "\n".join(
            f'q{i}=(queue("q{i}", payload_type="i32", protocol="ready_valid", depth=1),); '
            f'i{i}=export_flow(q{i}, protocol=ReadyValid); '
            f's{i}=(queue("s{i}", payload_type="i32", protocol="ready_valid", depth=1),)'
            for i in range(16)
        )
        inputs = ", ".join(f"i{i}" for i in range(16))
        outputs = ", ".join(f"o{i}" for i in range(16))
        imports = "\n".join(f"    import_flow(o{i}, (s{i}[0],))" for i in range(16))
        source = f'''from agentic_circuit import export_flow, import_flow, module, queue, system
Crossbar = None
class ReadyValid: pass
{declarations}
@module
def top() -> None:
    ({outputs}) = Crossbar(inputs=({inputs}), virtual_channels=1, ingress_depth=1, egress_depth=1, route_width=4)
{imports}
@system(root="top")
def main() -> None: return None
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scale.py"
            path.write_text(source)
            result = elaborate(path, Path(temporary))

        self.assertEqual((), result.diagnostics)
        assert result.acir is not None
        self.assertEqual(1, result.acir.count("ac.arbitrate greedy_fixed_priority"))
        self.assertEqual(256, result.acir.count(" uses [@pin"))
        self.assertNotIn("runtime Crossbar", result.acir)


if __name__ == "__main__":
    unittest.main()
