from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPOSITORY = Path(__file__).resolve().parents[2]


def _registry():
    from agentic_circuit._schemas import SchemaRegistry

    return SchemaRegistry.from_catalog(
        REPOSITORY / "schemas" / "stdlib" / "catalog.json", REPOSITORY
    )


def _source(kind: str, nodes: int, *, width: int = 1, height: int = 1,
            depth: int = 2, name: str = "noc",
            arbitration: str = "greedy_fixed_priority",
            flow_control: str = "ready_valid",
            router_pipeline: str = "single_stage_elastic",
            credit_delay: int = 0, vc_alloc_delay: int = 0,
            sw_alloc_delay: int = 0,
            wait_for_tail_credit: bool = False) -> str:
    declarations = []
    for node in range(nodes):
        declarations.extend(
            (
                f'q{node}=queue("q{node}", payload_type="i32", protocol="ready_valid", depth=2)',
                f'i{node}=export_flow((q{node},), protocol=ReadyValid)',
                f's{node}=queue("s{node}", payload_type="i32", protocol="ready_valid", depth=2)',
            )
        )
    inputs = ", ".join(f"i{node}" for node in range(nodes))
    outputs = ", ".join(f"r{node}" for node in range(nodes))
    if nodes == 1:
        inputs += ","
        outputs += ","
    imports = "\n".join(
        f"    import_flow(r{node}, (s{node},))" for node in range(nodes)
    )
    if kind == "RingNoC":
        arguments = (
            f'queue_depth={depth}, route_offset=0, routing="clockwise", '
            f'arbitration="greedy_fixed_priority", name="{name}"'
        )
    else:
        arguments = (
            f'width={width}, height={height}, queue_depth={depth}, route_offset=0, '
            f'virtual_channels=1, flow_control="{flow_control}", link_latency=1, '
            f'router_pipeline="{router_pipeline}", credit_delay={credit_delay}, '
            f'vc_alloc_delay={vc_alloc_delay}, sw_alloc_delay={sw_alloc_delay}, '
            f'wait_for_tail_credit={wait_for_tail_credit}, input_speedup=1, '
            f'output_speedup=1, routing="xy", arbitration="{arbitration}", '
            f'name="{name}"'
        )
    return f'''from agentic_circuit import export_flow, import_flow, module, process, queue, system, yield_sim
{kind} = None
class ReadyValid: pass
{chr(10).join(declarations)}
@module
def top() -> None:
    ({outputs}) = {kind}(inputs=({inputs}), {arguments})
{imports}
@process(kind="workload")
def traffic() -> None:
    yield_sim()
@system(root="top")
def main() -> None: return None
'''


def _elaborate(source: str):
    from agentic_circuit._frontend import CaptureRequest, elaborate_frontend

    temporary = tempfile.TemporaryDirectory()
    path = Path(temporary.name) / "model.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("noc_model", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = elaborate_frontend(
        CaptureRequest(entry=path, workspace=Path(temporary.name), system="main"),
        vars(module),
        _registry(),
    )
    temporary.cleanup()
    return result


class NoCFrontendTest(unittest.TestCase):
    def _verify(self, acir: str) -> None:
        verifier = REPOSITORY / "build" / "dev-llvm22" / "bin" / "acir-opt"
        if not verifier.is_file():
            self.skipTest("acir-opt is not built")
        completed = subprocess.run(
            (str(verifier), "-o", "/dev/null", "-"),
            input=acir,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_ring_is_deterministic_structural_and_verified(self) -> None:
        result = _elaborate(_source("RingNoC", 4, name="ring_a"))
        repeated = _elaborate(_source("RingNoC", 4, name="ring_a"))
        self.assertEqual((), result.diagnostics)
        self.assertEqual(result.acir, repeated.acir)
        assert result.acir is not None and result.document is not None
        self.assertEqual(4, result.acir.count("ac.queue @link_"))
        self.assertEqual(4, result.acir.count("_scheduler kind \"control\""))
        self.assertIn("@link_n3_to_n0_cw", result.acir)
        self.assertEqual(16, result.acir.count(" uses [@node"))
        results = [entity for entity in result.document.entities if entity.kind == "result"]
        self.assertEqual(
            (0, 1, 2, 3),
            tuple(dict((p.name, p.value) for p in entity.properties)["node_id"] for entity in results),
        )
        self._verify(result.acir)

    def test_host_input_is_root_owned_and_tagged_in_acir(self) -> None:
        source = _source("RingNoC", 2).replace(
            "from agentic_circuit import ",
            "from agentic_circuit import host_input_queue, ",
        ).replace(
            'q0=queue("q0", payload_type="i32", protocol="ready_valid", depth=2)',
            'q0=host_input_queue("q0", depth=2, host_name="node0")',
        )
        result = _elaborate(source)
        self.assertEqual((), result.diagnostics)
        assert result.acir is not None
        declaration = next(
            line
            for line in result.acir.splitlines()
            if "ac.queue @q0 " in line and "ac.host_input" in line
        )
        self.assertIn('ac.host_input = "node0"', declaration)
        self.assertEqual(1, result.acir.count('ac.host_input = "node0"'))
        self.assertIn("%i0_vc0 = ac.flow.export @q0", result.acir)
        self._verify(result.acir)

    def test_ring_supported_scales_and_specialization(self) -> None:
        fingerprints = []
        for nodes in (2, 4, 16):
            result = _elaborate(_source("RingNoC", nodes, name=f"ring_{nodes}"))
            self.assertEqual((), result.diagnostics)
            assert result.document is not None and result.acir is not None
            call = next(entity for entity in result.document.entities if entity.kind == "call")
            fingerprints.append(dict((p.name, p.value) for p in call.properties)["specialization"])
            self.assertEqual(nodes, result.acir.count("ac.queue @link_"))
        renamed = _elaborate(_source("RingNoC", 4, name="renamed"))
        assert renamed.document is not None
        renamed_call = next(entity for entity in renamed.document.entities if entity.kind == "call")
        renamed_fp = dict((p.name, p.value) for p in renamed_call.properties)["specialization"]
        self.assertEqual(fingerprints[1], renamed_fp)
        deeper = _elaborate(_source("RingNoC", 4, depth=3))
        assert deeper.document is not None
        deeper_call = next(entity for entity in deeper.document.entities if entity.kind == "call")
        deeper_fp = dict((p.name, p.value) for p in deeper_call.properties)["specialization"]
        self.assertNotEqual(fingerprints[1], deeper_fp)

    def test_mesh_shapes_links_xy_and_candidate_bound(self) -> None:
        for width, height in ((1, 1), (2, 2), (4, 4)):
            with self.subTest(shape=(width, height)):
                result = _elaborate(_source("MeshNoC", width * height, width=width, height=height))
                self.assertEqual((), result.diagnostics)
                assert result.acir is not None
                expected_links = 2 * ((width - 1) * height + (height - 1) * width)
                self.assertEqual(expected_links, result.acir.count("ac.queue @link_"))
                processes = result.acir.split("ac.process @node")[1:]
                self.assertTrue(all(part.split("ac.yield_sim", 1)[0].count(" uses [@node") <= 25 for part in processes))
        mesh = _elaborate(_source("MeshNoC", 4, width=2, height=2))
        assert mesh.acir is not None
        self.assertIn("%route_east_local", mesh.acir)
        self.assertIn("%route_north_local", mesh.acir)
        self.assertIn("%route_west_local", mesh.acir)
        self.assertIn("%route_south_local", mesh.acir)
        self.assertEqual(8, mesh.acir.count("ac.queue @link_"))
        self._verify(mesh.acir)

    def test_mesh_round_robin_is_explicit_stateful_and_verified(self) -> None:
        source = _source(
            "MeshNoC", 4, width=2, height=2, arbitration="round_robin"
        )
        result = _elaborate(source)
        repeated = _elaborate(source)
        fixed = _elaborate(_source("MeshNoC", 4, width=2, height=2))
        self.assertEqual((), result.diagnostics)
        self.assertEqual(result.acir, repeated.acir)
        assert result.acir is not None and result.document is not None
        assert fixed.acir is not None and fixed.document is not None
        self.assertEqual(20, result.acir.count("ac.queue @node"))
        self.assertEqual(12, result.acir.count(" = ac.try_recv @node"))
        self.assertEqual(12, result.acir.count(" = ac.try_send @node"))
        self.assertIn("%rr_pointer_east", result.acir)
        self.assertIn("arith.select %grant_", result.acir)
        call = next(
            entity for entity in result.document.entities if entity.kind == "call"
        )
        fixed_call = next(
            entity for entity in fixed.document.entities if entity.kind == "call"
        )
        properties = dict((p.name, p.value) for p in call.properties)
        fixed_properties = dict((p.name, p.value) for p in fixed_call.properties)
        self.assertEqual("round_robin", properties["arbitration"])
        self.assertEqual(1, properties["virtual_channels"])
        self.assertEqual("ready_valid", properties["flow_control"])
        self.assertEqual(1, properties["link_latency"])
        self.assertEqual("single_stage_elastic", properties["router_pipeline"])
        self.assertEqual(0, properties["credit_delay"])
        self.assertEqual(0, properties["vc_alloc_delay"])
        self.assertEqual(0, properties["sw_alloc_delay"])
        self.assertFalse(properties["wait_for_tail_credit"])
        self.assertEqual(1, properties["input_speedup"])
        self.assertEqual(1, properties["output_speedup"])
        self.assertNotIn("_rr_", fixed.acir)
        self.assertNotEqual(
            fixed_properties["specialization"], properties["specialization"]
        )
        self._verify(result.acir)

        scale = _elaborate(
            _source(
                "MeshNoC", 16, width=4, height=4,
                arbitration="round_robin",
            )
        )
        self.assertEqual((), scale.diagnostics)
        assert scale.acir is not None
        # Sixteen Local egresses plus 48 directed cardinal egresses each own
        # exactly one independent arbitration pointer.
        self.assertEqual(64, scale.acir.count(" = ac.try_recv @node"))
        self.assertEqual(64, scale.acir.count(" = ac.try_send @node"))
        processes = scale.acir.split("ac.process @node")[1:]
        self.assertTrue(
            all(
                part.split("ac.yield_sim", 1)[0].count(" uses [@node") <= 25
                for part in processes
            )
        )
        self._verify(scale.acir)

    def test_invalid_noc_declarations_have_noc_diagnostic(self) -> None:
        invalid = (
            _source("RingNoC", 2).replace("(r0, r1)", "(r0,)"),
            _source("RingNoC", 2).replace("queue_depth=2", "queue_depth=0"),
            _source("RingNoC", 2).replace('routing="clockwise"', 'routing="shortest"'),
            _source("MeshNoC", 4, width=2, height=2).replace("width=2", "width=3"),
            _source("MeshNoC", 4, width=2, height=2).replace('routing="xy"', 'routing="adaptive"'),
            _source("MeshNoC", 4, width=2, height=2).replace("virtual_channels=1", "virtual_channels=2"),
            _source("MeshNoC", 4, width=2, height=2).replace("link_latency=1", "link_latency=2"),
            _source("MeshNoC", 4, width=2, height=2).replace("input_speedup=1", "input_speedup=2"),
            _source("MeshNoC", 4, width=2, height=2).replace("output_speedup=1", "output_speedup=2"),
            _source("MeshNoC", 4, width=2, height=2).replace('flow_control="ready_valid"', 'flow_control="tokens"'),
            _source("MeshNoC", 4, width=2, height=2).replace('router_pipeline="single_stage_elastic"', 'router_pipeline="iq"'),
            _source("MeshNoC", 4, width=2, height=2).replace('arbitration="greedy_fixed_priority"', 'arbitration="age_based"'),
        )
        for source in invalid:
            with self.subTest(source=source.splitlines()[1]):
                result = _elaborate(source)
                self.assertIn("ACPY-NOC-001", tuple(item.code for item in result.diagnostics))
                self.assertTrue(all(item.source is not None for item in result.diagnostics))

    def test_mesh_credit_and_input_queued_parameter_contract(self) -> None:
        credit = _elaborate(
            _source(
                "MeshNoC", 4, width=2, height=2,
                flow_control="credit", credit_delay=3,
                wait_for_tail_credit=True,
            )
        )
        iq = _elaborate(
            _source(
                "MeshNoC", 4, width=2, height=2,
                flow_control="credit", router_pipeline="input_queued",
                credit_delay=2, vc_alloc_delay=1, sw_alloc_delay=3,
                wait_for_tail_credit=True,
            )
        )
        iq_rr = _elaborate(
            _source(
                "MeshNoC", 4, width=2, height=2,
                flow_control="credit", router_pipeline="input_queued",
                credit_delay=2, vc_alloc_delay=1, sw_alloc_delay=3,
                wait_for_tail_credit=True, arbitration="round_robin",
            )
        )
        self.assertEqual((), credit.diagnostics)
        self.assertEqual((), iq.diagnostics)
        self.assertEqual((), iq_rr.diagnostics)
        assert credit.document is not None and iq.document is not None
        credit_call = next(e for e in credit.document.entities if e.kind == "call")
        iq_call = next(e for e in iq.document.entities if e.kind == "call")
        credit_properties = dict((p.name, p.value) for p in credit_call.properties)
        iq_properties = dict((p.name, p.value) for p in iq_call.properties)
        self.assertEqual("credit", credit_properties["flow_control"])
        self.assertEqual(3, credit_properties["credit_delay"])
        self.assertEqual("input_queued", iq_properties["router_pipeline"])
        self.assertEqual(3, iq_properties["sw_alloc_delay"])
        self.assertNotEqual(
            credit_properties["specialization"], iq_properties["specialization"]
        )
        assert credit.acir is not None and iq.acir is not None
        self.assertEqual(8, credit.acir.count("ac.queue @credit_"))
        self.assertEqual(8, credit.acir.count("ac.queue @node") - 8)
        self.assertIn("%vc_busy_east", credit.acir)
        self.assertIn("ac.try_send @credit_", credit.acir)
        self._verify(credit.acir)
        self.assertEqual(8, iq.acir.count("ac.queue @credit_"))
        self.assertEqual(24, iq.acir.count("ac.queue @node") - 8)
        self.assertIn("ac.queue @node0_pipe_local", iq.acir)
        self.assertIn("ac.queue @node0_vc_local", iq.acir)
        self.assertIn("%va_grant_", iq.acir)
        self.assertIn("%sa_grant_", iq.acir)
        self.assertIn("arith.constant 101 : i32", iq.acir)
        self.assertIn("arith.constant 203 : i32", iq.acir)
        self._verify(iq.acir)
        assert iq_rr.acir is not None
        self.assertEqual(12, iq_rr.acir.count("ac.arbitrate round_robin"))
        self.assertNotIn("%va_rr_blocked", iq_rr.acir)
        self.assertNotIn("%va_rr_term", iq_rr.acir)
        self.assertNotIn("%va_rr_selected", iq_rr.acir)
        self._verify(iq_rr.acir)

        invalid = (
            _source("MeshNoC", 4, width=2, height=2, credit_delay=1),
            _source(
                "MeshNoC", 4, width=2, height=2,
                flow_control="credit", credit_delay=65,
                wait_for_tail_credit=True,
            ),
            _source(
                "MeshNoC", 4, width=2, height=2,
                flow_control="credit", vc_alloc_delay=1,
            ),
            _source(
                "MeshNoC", 4, width=2, height=2,
                flow_control="credit", router_pipeline="input_queued",
                vc_alloc_delay=0, sw_alloc_delay=1,
            ),
        )
        for source in invalid:
            result = _elaborate(source)
            self.assertIn("ACPY-NOC-001", tuple(item.code for item in result.diagnostics))

    def test_common_noc_scheduler_has_no_mesh_direction_dependency(self) -> None:
        from agentic_circuit._lower_acir import (
            _NoCEgress,
            _NoCIngress,
            _NoCTiming,
            _noc_iq_scheduler,
            _noc_scheduler,
        )

        ingresses = [
            _NoCIngress("transit", "link_prev", "credit_back"),
            _NoCIngress("inject", "local_in"),
        ]
        egresses = [
            _NoCEgress("capture", "local_out"),
            _NoCEgress("forward", "link_next", "vc_forward", "credit_forward"),
        ]
        routes = {
            (egress.name, ingress.name): f"%route_{egress.name}_{ingress.name}"
            for egress in egresses
            for ingress in ingresses
        }
        emitted = "\n".join(
            _noc_scheduler(
                7,
                ingresses,
                egresses,
                routes,
                ["      %zero = arith.constant 0 : i32"],
                "i32",
                timing=_NoCTiming(
                    flow_control="credit",
                    credit_delay=2,
                    wait_for_tail_credit=True,
                ),
            )
        )
        self.assertIn("@vc_forward", emitted)
        self.assertIn("@credit_forward", emitted)
        self.assertIn("@credit_back", emitted)
        self.assertIn("arith.constant 2 : i32", emitted)
        for mesh_direction in ("north", "east", "south", "west"):
            self.assertNotIn(mesh_direction, emitted)

        iq_emitted = "\n".join(
            _noc_iq_scheduler(
                7,
                ingresses,
                [
                    _NoCEgress("capture", "local_out", "vc_capture"),
                    _NoCEgress(
                        "forward", "link_next", "vc_forward", "credit_forward"
                    ),
                ],
                routes,
                ["      %zero = arith.constant 0 : i32"],
                "i32",
                arbitration="greedy_fixed_priority",
                timing=_NoCTiming(
                    flow_control="credit",
                    router_pipeline="input_queued",
                    credit_delay=2,
                    vc_alloc_delay=1,
                    sw_alloc_delay=1,
                    wait_for_tail_credit=True,
                ),
            )
        )
        self.assertIn("@node7_pipe_transit", iq_emitted)
        self.assertIn("@node7_va_pout_forward", iq_emitted)
        self.assertIn("@vc_capture", iq_emitted)
        self.assertIn("@credit_forward", iq_emitted)
        for mesh_direction in ("north", "east", "south", "west"):
            self.assertNotIn(mesh_direction, iq_emitted)

    def test_unknown_generator_dispatch_is_explicit(self) -> None:
        from agentic_circuit._lower_acir import _generator_declaration

        call = SimpleNamespace(schema=SimpleNamespace(identity="vendor.Unknown"))
        with self.assertRaisesRegex(ValueError, "unsupported compiler-native generator 'vendor.Unknown'"):
            _generator_declaration(call)


if __name__ == "__main__":
    unittest.main()
