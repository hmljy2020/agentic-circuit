from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]


def elaborate(source: str):
    from agentic_circuit._frontend import CaptureRequest, elaborate_frontend
    from agentic_circuit._schemas import SchemaRegistry

    temporary = tempfile.TemporaryDirectory()
    path = Path(temporary.name) / "model.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("packet_model", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registry = SchemaRegistry.from_catalog(
        REPOSITORY / "schemas" / "stdlib" / "catalog.json", REPOSITORY
    )
    result = elaborate_frontend(
        CaptureRequest(entry=path, workspace=Path(temporary.name), system="main"),
        vars(module),
        registry,
    )
    temporary.cleanup()
    return result


class PacketFrontendTest(unittest.TestCase):
    def test_packet_and_nested_struct_emit_natural_layout(self) -> None:
        source = '''from __future__ import annotations
from agentic_circuit import Vector, i8, i16, i32, module, packet, struct, system
@struct(endianness="little")
def Header(opcode: i8, tag: i16) -> None: pass
@packet(endianness="little")
def Message(destination: i32, header: Header, payload: Vector[i8, 4]) -> None: pass
@module
def top() -> None: pass
@system(root="top")
def main() -> None: return None
'''
        result = elaborate(source)
        self.assertEqual((), result.diagnostics)
        assert result.acir is not None and result.document is not None
        self.assertIn("ac.struct @Header fields", result.acir)
        self.assertIn("ac.packet @Message fields", result.acir)
        self.assertIn("serialization_width = 12 : i64", result.acir)
        self.assertEqual(
            ("struct", "packet"),
            tuple(entity.kind for entity in result.document.entities if entity.kind in {"struct", "packet"}),
        )
        verifier = REPOSITORY / "build" / "dev-llvm22" / "bin" / "acir-opt"
        completed = subprocess.run(
            (str(verifier), "-o", "/dev/null", "-"),
            input=result.acir,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_recursive_and_invalid_layout_declarations_fail(self) -> None:
        recursive = '''from __future__ import annotations
from agentic_circuit import module, packet, struct, system
@struct
def Header(other: Header) -> None: pass
@packet
def Message(header: Header) -> None: pass
@module
def top() -> None: pass
@system(root="top")
def main() -> None: return None
'''
        result = elaborate(recursive)
        self.assertEqual(("ACPY-TYPE-PACKET",), tuple(item.code for item in result.diagnostics))

    def test_packet_process_operations_lower_and_verify(self) -> None:
        source = '''from __future__ import annotations
from agentic_circuit import i32, module, packet, packet_deserialize, packet_serialize, process, queue, record_get, record_with, system, try_send, yield_sim
@packet
def Message(destination: i32, payload: i32) -> None: pass
out = queue("out", payload_type=Message, protocol="ready_valid", depth=2)
@module
def top() -> None: pass
@process(kind="workload")
def worker() -> None:
    message = Message(destination=3, payload=17)
    destination = record_get(message, field="destination")
    updated = record_with(message, field="destination", value=destination)
    raw = packet_serialize(updated)
    copy = packet_deserialize(Message, raw)
    accepted = try_send(out, copy)
    yield_sim()
@system(root="top")
def main() -> None: return None
'''
        result = elaborate(source)
        self.assertEqual((), result.diagnostics)
        assert result.acir is not None
        for operation in (
            "ac.record.create",
            "ac.record.get",
            "ac.record.with",
            "ac.packet.serialize",
            "ac.packet.deserialize",
        ):
            self.assertIn(operation, result.acir)
        verifier = REPOSITORY / "build" / "dev-llvm22" / "bin" / "acir-opt"
        completed = subprocess.run(
            (str(verifier), "-o", "/dev/null", "-"),
            input=result.acir,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_packet_mesh_routes_by_named_i32_field(self) -> None:
        source = '''from __future__ import annotations
from agentic_circuit import export_flow, i32, import_flow, module, packet, queue, system
MeshNoC = None
class ReadyValid: pass
@packet
def Message(destination: i32, payload: i32) -> None: pass
tx0 = queue("tx0", payload_type=Message, protocol="ready_valid", depth=2)
tx1 = queue("tx1", payload_type=Message, protocol="ready_valid", depth=2)
tx2 = queue("tx2", payload_type=Message, protocol="ready_valid", depth=2)
tx3 = queue("tx3", payload_type=Message, protocol="ready_valid", depth=2)
rx0 = queue("rx0", payload_type=Message, protocol="ready_valid", depth=2)
rx1 = queue("rx1", payload_type=Message, protocol="ready_valid", depth=2)
rx2 = queue("rx2", payload_type=Message, protocol="ready_valid", depth=2)
rx3 = queue("rx3", payload_type=Message, protocol="ready_valid", depth=2)
in0 = export_flow((tx0,), protocol=ReadyValid)
in1 = export_flow((tx1,), protocol=ReadyValid)
in2 = export_flow((tx2,), protocol=ReadyValid)
in3 = export_flow((tx3,), protocol=ReadyValid)
@module
def fabric() -> None:
    (r0, r1, r2, r3) = MeshNoC(inputs=(in0, in1, in2, in3), width=2, height=2, queue_depth=2, route_offset=0, route_field="destination", virtual_channels=1, flow_control="ready_valid", link_latency=1, router_pipeline="single_stage_elastic", input_speedup=1, output_speedup=1, routing="xy", arbitration="greedy_fixed_priority", name="mesh")
    import_flow(r0, (rx0,))
    import_flow(r1, (rx1,))
    import_flow(r2, (rx2,))
    import_flow(r3, (rx3,))
@system(root="fabric")
def main() -> None: return None
'''
        result = elaborate(source)
        self.assertEqual((), result.diagnostics)
        assert result.acir is not None
        self.assertIn("payload !ac.packet<@types::@Message>", result.acir)
        self.assertIn('ac.record.get %head_local {field = "destination"}', result.acir)
        verifier = REPOSITORY / "build" / "dev-llvm22" / "bin" / "acir-opt"
        completed = subprocess.run(
            (str(verifier), "-o", "/dev/null", "-"),
            input=result.acir,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_packet_ring_routes_and_rejects_unknown_route_field(self) -> None:
        source = '''from __future__ import annotations
from agentic_circuit import export_flow, i32, import_flow, module, packet, queue, system
RingNoC = None
class ReadyValid: pass
@packet
def Message(destination: i32, payload: i32) -> None: pass
tx0 = queue("tx0", payload_type=Message, protocol="ready_valid", depth=2)
tx1 = queue("tx1", payload_type=Message, protocol="ready_valid", depth=2)
rx0 = queue("rx0", payload_type=Message, protocol="ready_valid", depth=2)
rx1 = queue("rx1", payload_type=Message, protocol="ready_valid", depth=2)
in0 = export_flow((tx0,), protocol=ReadyValid)
in1 = export_flow((tx1,), protocol=ReadyValid)
@module
def fabric() -> None:
    (r0, r1) = RingNoC(inputs=(in0, in1), queue_depth=2, route_offset=0, route_field="destination", routing="clockwise", arbitration="greedy_fixed_priority", name="ring")
    import_flow(r0, (rx0,))
    import_flow(r1, (rx1,))
@system(root="fabric")
def main() -> None: return None
'''
        result = elaborate(source)
        self.assertEqual((), result.diagnostics)
        assert result.acir is not None
        self.assertIn("link_n1_to_n0_cw", result.acir)
        self.assertIn('ac.record.get %head_cw {field = "destination"}', result.acir)
        invalid = elaborate(source.replace('route_field="destination"', 'route_field="missing"'))
        self.assertEqual(
            ("ACPY-NOC-001", "ACPY-FLOW-007", "ACPY-FLOW-007"),
            tuple(item.code for item in invalid.diagnostics),
        )
        self.assertIsNone(invalid.acir)


if __name__ == "__main__":
    unittest.main()
