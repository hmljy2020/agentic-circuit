#!/usr/bin/env python3
"""Emit the M1 scheduler ACIR.

The generator keeps bounded scans and reductions structural in ACIR.  It does
not simulate the scheduler in Python: decisions remain visible as SCF,
arithmetic, record, state, event, and queue operations.
"""

from __future__ import annotations

import sys


class IR:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.next_value = 0
        self.indent = 4

    def line(self, text: str = "") -> None:
        self.lines.append(" " * self.indent + text)

    def value(self, stem: str) -> str:
        value = f"%{stem}_{self.next_value}"
        self.next_value += 1
        return value

    def result(self, stem: str, expression: str) -> str:
        value = self.value(stem)
        self.line(f"{value} = {expression}")
        return value

    def c32(self, value: int) -> str:
        return self.result(f"c{value}", f"arith.constant {value} : i32")

    def c64(self, value: int) -> str:
        return self.result(f"c64_{value}", f"arith.constant {value} : i64")

    def cindex(self, value: int) -> str:
        return self.result(f"ci{value}", f"arith.constant {value} : index")

    def cb(self, value: bool) -> str:
        return self.result("true" if value else "false",
                           f"arith.constant {'true' if value else 'false'}")

    def cmp(self, predicate: str, left: str, right: str) -> str:
        return self.result("cmp", f"arith.cmpi {predicate}, {left}, {right} : i32")

    def and_(self, left: str, right: str) -> str:
        return self.result("and", f"arith.andi {left}, {right} : i1")

    def or_(self, left: str, right: str) -> str:
        return self.result("or", f"arith.ori {left}, {right} : i1")

    def not_(self, value: str, true_value: str) -> str:
        return self.result("not", f"arith.xori {value}, {true_value} : i1")

    def add(self, left: str, right: str) -> str:
        return self.result("add", f"arith.addi {left}, {right} : i32")

    def sub(self, left: str, right: str) -> str:
        return self.result("sub", f"arith.subi {left}, {right} : i32")

    def select(self, condition: str, yes: str, no: str, ty: str = "i32") -> str:
        return self.result("select", f"arith.select {condition}, {yes}, {no} : {ty}")

    def zext(self, value: str) -> str:
        return self.result("zext", f"arith.extui {value} : i1 to i32")

    def get(self, record: str, field: str, record_type: str) -> str:
        return self.result(field,
                           f'ac.record.get {record} {{field = "{field}"}} : '
                           f"({record_type}) -> i32")

    def with_(self, record: str, field: str, value: str,
              record_type: str) -> str:
        return self.result("record",
                           f'ac.record.with {record}, {value} '
                           f'{{field = "{field}"}} : ({record_type}, i32) -> {record_type}')

    def create(self, fields: list[tuple[str, str]], record_type: str) -> str:
        names = ", ".join(f'"{name}"' for name, _ in fields)
        operands = ", ".join(value for _, value in fields)
        types = ", ".join("i32" for _ in fields)
        return self.result("record",
                           f'ac.record.create {operands} '
                           f'{{field_names = [{names}]}} : ({types}) -> {record_type}')

    def for_iter(self, stem: str, lower: str, upper: str, step: str,
                 carried: list[tuple[str, str]], body) -> list[str]:
        """Emit one compact scf.for and return its loop-carried results."""
        induction = self.value(f"{stem}_iv")
        arguments = [self.value(f"{stem}_arg") for _ in carried]
        results = [self.value(f"{stem}_result") for _ in carried]
        result_prefix = ", ".join(results) + " = " if results else ""
        iter_text = ""
        result_text = ""
        if carried:
            iter_text = " iter_args(" + ", ".join(
                f"{argument} = {initial}"
                for argument, (_, initial) in zip(arguments, carried)) + ")"
            result_text = " -> (" + ", ".join(ty for ty, _ in carried) + ")"
        self.line(f"{result_prefix}scf.for {induction} = {lower} to {upper} "
                  f"step {step}{iter_text}{result_text} {{")
        self.indent += 2
        yielded = body(induction, arguments)
        if carried:
            if len(yielded) != len(carried):
                raise ValueError("scf.for body returned the wrong yield arity")
            self.line("scf.yield " + ", ".join(yielded) + " : " +
                      ", ".join(ty for ty, _ in carried))
        else:
            self.line("scf.yield")
        self.indent -= 2
        self.line("}")
        return results


def decl_packet(name: str, fields: list[str], size: int) -> str:
    body = ", ".join(f'{{name = "{field}", type = i32}}' for field in fields)
    return f"    ac.packet @{name} fields [{body}]\n"


def next_ring(ir: IR, value: str, increment: str, constants: list[str]) -> str:
    added = ir.add(value, increment)
    eight = constants[8]
    wraps = ir.cmp("uge", added, eight)
    wrapped = ir.sub(added, eight)
    return ir.select(wraps, wrapped, added)


def emit_model() -> str:
    ir = IR()
    instruction_t = "!ac.packet<@types::@Instruction>"
    completion_t = "!ac.packet<@types::@Completion>"
    trace_t = "!ac.packet<@types::@TraceEvent>"
    window_t = "!ac.packet<@types::@WindowEntry>"
    rob_t = "!ac.packet<@types::@RobEntry>"
    fu_t = "!ac.packet<@types::@FuState>"
    cube_stage_t = "!ac.packet<@types::@CubeStage>"
    control_t = "!ac.packet<@types::@ControlState>"

    out: list[str] = ['module attributes {ac.contract_epoch = "0.2"} {',
                      '  ac.type_scope @types {']
    out.append(decl_packet("Instruction", ["sequence_id", "opcode", "rd", "rs1", "rs2"], 20).rstrip())
    out.append(decl_packet("Completion", ["sequence_id", "rob_slot", "rd", "fu"], 16).rstrip())
    out.append(decl_packet("TraceEvent", ["tick", "sequence_id", "phase", "engine", "unit", "lane"], 24).rstrip())
    out.append(decl_packet("WindowEntry", ["valid", "sequence_id", "opcode", "rd", "dep1", "dep2", "rob_slot"], 28).rstrip())
    out.append(decl_packet("RobEntry", ["valid", "completed", "sequence_id", "rd", "opcode"], 20).rstrip())
    out.append(decl_packet("FuState", ["inflight", "next_issue"], 8).rstrip())
    out.append(decl_packet("CubeStage", ["valid", "sequence_id"], 8).rstrip())
    out.append(decl_packet("ControlState", ["tick", "rob_head", "rob_tail", "rob_count", "last_dispatch", "retired", "completion_cursor"], 28).rstrip())
    layouts = [("Instruction", 20), ("Completion", 16), ("TraceEvent", 24),
               ("WindowEntry", 28), ("RobEntry", 20), ("FuState", 8),
               ("CubeStage", 8),
               ("ControlState", 28)]
    layout_text = ",\n      ".join(
        f"!ac.packet<@types::@{name}> = {{abi_alignment = 4 : i64, endianness = \"little\", preferred_alignment = 4 : i64, serialization_width = {size} : i64, size = {size} : i64}}"
        for name, size in layouts)
    out.extend([f"  }} {{dlti.dl_spec = #dlti.dl_spec<\n      {layout_text}\n  >}}",
                "  ac.protocol @ready_valid {",
                "    ac.role @sender dual @receiver cardinality \"exclusive\"",
                "    ac.role @receiver dual @sender cardinality \"exclusive\"",
                "    ac.state @idle initial true terminal false",
                "    ac.state @done initial false terminal true",
                f"    ac.event @instruction from @sender to @receiver payload {instruction_t} action \"offer\"",
                f"    ac.event @trace from @sender to @receiver payload {trace_t} action \"offer\"",
                "    ac.transition from @idle to @done on @instruction transfer true retain false guard {}",
                "    ac.transition from @idle to @done on @trace transfer true retain false guard {}",
                "  }",
                "  ac.system @m1_scheduler root @Top as \"root\" tick 0 \"cycle\"",
                "      workload @Top::@scheduler seed {kind = \"fixed\", value = 7 : i64}",
                "      instrumentation [] results {id = \"default\", format = \"json\"} selected true",
                "  ac.module @Top() parameters {} graph {",
                "    ac.time_domain @core period 1 phase 0 scale 1",
                f"    ac.queue @in0 payload {instruction_t} entries 4 bytes 80 ordering \"fifo\" protocol @ready_valid ownership \"exclusive\" id \"in0\" path \"in0\" {{ac.host_input = \"lane0\"}}",
                f"    ac.queue @in1 payload {instruction_t} entries 4 bytes 80 ordering \"fifo\" protocol @ready_valid ownership \"exclusive\" id \"in1\" path \"in1\" {{ac.host_input = \"lane1\"}}",
                f"    ac.event_queue @completions payload !ac.event<{completion_t}> capacity 17 ordering \"time_then_sequence\" domain @core id \"completions\" path \"completions\"",
                f"    ac.state_array @window element {window_t} entries 8 read_ports 8 write_ports 8 ownership \"exclusive\" init \"zero\" id \"window\" path \"window\"",
                f"    ac.state_array @rob element {rob_t} entries 8 read_ports 10 write_ports 8 ownership \"exclusive\" init \"zero\" id \"rob\" path \"rob\"",
                "    ac.state_array @producer element i32 entries 16 read_ports 8 write_ports 4 ownership \"exclusive\" init \"zero\" id \"producer\" path \"producer\"",
                f"    ac.state_array @fu element {fu_t} entries 5 read_ports 5 write_ports 5 ownership \"exclusive\" init \"zero\" id \"fu\" path \"fu\"",
                f"    ac.state_array @cube_pipeline element {cube_stage_t} entries 8 read_ports 8 write_ports 8 ownership \"exclusive\" init \"zero\" id \"cube_pipeline\" path \"cube_pipeline\"",
                "    ac.state_array @completion_slots element i32 entries 9 read_ports 12 write_ports 3 ownership \"exclusive\" init \"zero\" id \"completion_slots\" path \"completion_slots\"",
                f"    ac.state_array @control element {control_t} entries 1 read_ports 1 write_ports 1 ownership \"exclusive\" init \"zero\" id \"control\" path \"control\""])
    for phase in ("dispatch", "issue", "complete", "retire"):
        for lane in range(2):
            out.append(f"    ac.queue @{phase}{lane} payload {trace_t} entries 4 bytes 96 ordering \"fifo\" protocol @ready_valid ownership \"exclusive\" id \"{phase}{lane}\" path \"{phase}{lane}\" {{ac.host_output = \"{phase}{lane}\"}}")
    out.append('    ac.process @scheduler kind "workload" {')
    ir.indent = 6

    constants = [ir.c32(i) for i in range(33)]
    cfalse, ctrue = ir.cb(False), ir.cb(True)
    c64 = [ir.c64(i) for i in range(9)]
    ci0, ci1, ci8 = ir.cindex(0), ir.cindex(1), ir.cindex(8)

    control = ir.result("control", f"ac.state_read @control[{constants[0]}] port {constants[0]} : {control_t}")
    ctrl = {field: ir.get(control, field, control_t) for field in
            ("tick", "rob_head", "rob_tail", "rob_count", "last_dispatch", "retired", "completion_cursor")}

    def read_window(index: str, port: str) -> dict[str, str]:
        record = ir.result(
            "window", f"ac.state_read @window[{index}] port {port} : {window_t}")
        fields = {field: ir.get(record, field, window_t) for field in
                  ("valid", "sequence_id", "opcode", "rd", "dep1", "dep2", "rob_slot")}
        fields["record"] = record
        return fields

    def read_rob(index: str, port: str) -> dict[str, str]:
        record = ir.result(
            "rob", f"ac.state_read @rob[{index}] port {port} : {rob_t}")
        fields = {field: ir.get(record, field, rob_t) for field in
                  ("valid", "completed", "sequence_id", "rd", "opcode")}
        fields["record"] = record
        return fields
    fus: list[dict[str, str]] = []
    for i in range(5):
        record = ir.result("fu", f"ac.state_read @fu[{constants[i]}] port {constants[i]} : {fu_t}")
        fus.append({"record": record,
                    "inflight": ir.get(record, "inflight", fu_t),
                    "next_issue": ir.get(record, "next_issue", fu_t)})
    cube_pipeline: list[dict[str, str]] = []
    for i in range(8):
        record = ir.result("cube_stage", f"ac.state_read @cube_pipeline[{constants[i]}] port {constants[i]} : {cube_stage_t}")
        cube_pipeline.append({"record": record,
                              "valid": ir.get(record, "valid", cube_stage_t),
                              "sequence_id": ir.get(record, "sequence_id", cube_stage_t)})
    completion_slots = [ir.result("completion_slot", f"ac.state_read @completion_slots[{constants[i]}] port {constants[i]} : i32")
                        for i in range(9)]

    inst0, in0_valid = ir.value("inst0"), ir.value("in0_valid")
    ir.line(f"{inst0}, {in0_valid} = ac.peek @in0 : {instruction_t}")
    inst1, in1_valid = ir.value("inst1"), ir.value("in1_valid")
    ir.line(f"{inst1}, {in1_valid} = ac.peek @in1 : {instruction_t}")
    inst_fields: list[dict[str, str]] = []
    for record in (inst0, inst1):
        inst_fields.append({field: ir.get(record, field, instruction_t) for field in
                            ("sequence_id", "opcode", "rd", "rs1", "rs2")})

    completions: list[dict[str, str]] = []
    for lane in range(2):
        value, ready = ir.value("completion"), ir.value("completion_ready")
        ir.line(f"{value}, {ready} = ac.try_event @completions : {completion_t}")
        fields = {field: ir.get(value, field, completion_t) for field in
                  ("sequence_id", "rob_slot", "rd", "fu")}
        fields.update({"record": value, "ready": ready})
        completions.append(fields)

    comp_by_fu: list[str] = []
    for fu in range(5):
        count = constants[0]
        for comp in completions:
            match = ir.and_(comp["ready"], ir.cmp("eq", comp["fu"], constants[fu]))
            count = ir.add(count, ir.zext(match))
        comp_by_fu.append(count)
    adjusted_inflight = [ir.sub(fus[i]["inflight"], comp_by_fu[i]) for i in range(5)]
    capacities = [1, 2, 2, 8, 4]
    available: list[str] = []
    for fu in range(5):
        below = ir.cmp("slt", adjusted_inflight[fu], constants[capacities[fu]])
        ii_ready = ir.cmp("sge", ctrl["tick"], fus[fu]["next_issue"])
        available.append(ir.and_(below, ii_ready))

    def completion_index(opcode: str) -> str:
        delay = constants[1]
        delay = ir.select(ir.cmp("eq", opcode, constants[1]), constants[2], delay)
        delay = ir.select(ir.cmp("eq", opcode, constants[2]), constants[8], delay)
        delay = ir.select(ir.cmp("eq", opcode, constants[3]), constants[4], delay)
        added = ir.add(ctrl["completion_cursor"], delay)
        wrapped = ir.sub(added, constants[9])
        return ir.select(ir.cmp("uge", added, constants[9]), wrapped, added)

    def completion_count(index: str) -> str:
        count = constants[0]
        for slot in range(9):
            count = ir.select(ir.cmp("eq", index, constants[slot]),
                              completion_slots[slot], count)
        return count

    def eligible(entry: dict[str, str], availability: list[str],
                 prior_issue: str | None = None,
                 prior_index: str | None = None) -> str:
        valid = ir.cmp("eq", entry["valid"], constants[1])
        deps = ir.and_(ir.cmp("eq", entry["dep1"], constants[0]),
                       ir.cmp("eq", entry["dep2"], constants[0]))
        op_ready = cfalse
        for opcode, units in ((0, [0]), (1, [1, 2]), (2, [3]), (3, [4])):
            unit_ready = availability[units[0]]
            for unit in units[1:]:
                unit_ready = ir.or_(unit_ready, availability[unit])
            op_ready = ir.or_(op_ready,
                              ir.and_(ir.cmp("eq", entry["opcode"], constants[opcode]), unit_ready))
        candidate_completion_index = completion_index(entry["opcode"])
        reserved = completion_count(candidate_completion_index)
        if prior_issue is not None and prior_index is not None:
            collides = ir.and_(prior_issue,
                               ir.cmp("eq", candidate_completion_index,
                                      prior_index))
            reserved = ir.add(reserved, ir.zext(collides))
        completion_ready = ir.cmp("slt", reserved, constants[2])
        return ir.and_(valid, ir.and_(deps, ir.and_(op_ready,
                                                    completion_ready)))

    # One compact scan selects lane 0 and, independently, the first two free
    # entries.  Winner fields travel with the reduction, so no indexed select
    # tree is needed after the loop.
    def issue0_body(iv: str, args: list[str]) -> list[str]:
        (found, best_seq, best_index, best_opcode, best_rd, best_rob,
         free_found0, free_idx0, free_found1, free_idx1) = args
        index = ir.result("window_index", f"arith.index_cast {iv} : index to i32")
        entry = read_window(index, index)
        candidate = eligible(entry, available)
        better = ir.and_(candidate,
                         ir.or_(ir.not_(found, ctrue),
                                ir.cmp("slt", entry["sequence_id"], best_seq)))
        next_found = ir.or_(found, candidate)
        next_seq = ir.select(better, entry["sequence_id"], best_seq)
        next_index = ir.select(better, index, best_index)
        next_opcode = ir.select(better, entry["opcode"], best_opcode)
        next_rd = ir.select(better, entry["rd"], best_rd)
        next_rob = ir.select(better, entry["rob_slot"], best_rob)

        free = ir.cmp("eq", entry["valid"], constants[0])
        choose0 = ir.and_(free, ir.not_(free_found0, ctrue))
        choose1 = ir.and_(free, ir.and_(free_found0,
                                       ir.not_(free_found1, ctrue)))
        next_free_idx0 = ir.select(choose0, index, free_idx0)
        next_free_idx1 = ir.select(choose1, index, free_idx1)
        next_free_found0 = ir.or_(free_found0, free)
        next_free_found1 = ir.or_(free_found1, choose1)
        return [next_found, next_seq, next_index, next_opcode, next_rd,
                next_rob, next_free_found0, next_free_idx0,
                next_free_found1, next_free_idx1]

    (issue0, issue_seq0, issue_idx0, issue_op0, issue_rd0, issue_rob0,
     free_found0, free_idx0, free_found1, free_idx1) = ir.for_iter(
        "issue0", ci0, ci8, ci1,
        [("i1", cfalse), ("i32", constants[32]),
         ("i32", constants[0]), ("i32", constants[0]),
         ("i32", constants[0]), ("i32", constants[0]),
         ("i1", cfalse), ("i32", constants[0]),
         ("i1", cfalse), ("i32", constants[0])], issue0_body)

    vec0 = ir.cmp("eq", issue_op0, constants[1])
    issue_unit0 = constants[0]
    issue_unit0 = ir.select(ir.cmp("eq", issue_op0, constants[3]), constants[4], issue_unit0)
    issue_unit0 = ir.select(ir.cmp("eq", issue_op0, constants[2]), constants[3], issue_unit0)
    vec_unit0 = ir.select(available[1], constants[1], constants[2])
    issue_unit0 = ir.select(vec0, vec_unit0, issue_unit0)
    used0 = [ir.and_(issue0, ir.cmp("eq", issue_unit0, constants[fu])) for fu in range(5)]
    available1 = [ir.and_(available[fu], ir.not_(used0[fu], ctrue)) for fu in range(5)]
    completion_index0 = completion_index(issue_op0)

    def issue1_body(iv: str, args: list[str]) -> list[str]:
        found, best_seq, best_index, best_opcode, best_rd, best_rob = args
        index = ir.result("window_index", f"arith.index_cast {iv} : index to i32")
        entry = read_window(index, index)
        candidate = eligible(entry, available1, issue0, completion_index0)
        is_lane0 = ir.and_(issue0, ir.cmp("eq", issue_idx0, index))
        candidate = ir.and_(candidate, ir.not_(is_lane0, ctrue))
        better = ir.and_(candidate,
                         ir.or_(ir.not_(found, ctrue),
                                ir.cmp("slt", entry["sequence_id"], best_seq)))
        return [ir.or_(found, candidate),
                ir.select(better, entry["sequence_id"], best_seq),
                ir.select(better, index, best_index),
                ir.select(better, entry["opcode"], best_opcode),
                ir.select(better, entry["rd"], best_rd),
                ir.select(better, entry["rob_slot"], best_rob)]

    (issue1, issue_seq1, issue_idx1, issue_op1, issue_rd1,
     issue_rob1) = ir.for_iter(
        "issue1", ci0, ci8, ci1,
        [("i1", cfalse), ("i32", constants[32]),
         ("i32", constants[0]), ("i32", constants[0]),
         ("i32", constants[0]), ("i32", constants[0])], issue1_body)

    issue_unit1 = constants[0]
    issue_unit1 = ir.select(ir.cmp("eq", issue_op1, constants[3]), constants[4], issue_unit1)
    issue_unit1 = ir.select(ir.cmp("eq", issue_op1, constants[2]), constants[3], issue_unit1)
    vec_unit1 = ir.select(available1[1], constants[1], constants[2])
    issue_unit1 = ir.select(ir.cmp("eq", issue_op1, constants[1]), vec_unit1, issue_unit1)

    issue_info = [
        {"valid": issue0, "index": issue_idx0, "opcode": issue_op0,
         "unit": issue_unit0, "sequence_id": issue_seq0,
         "rob_slot": issue_rob0, "rd": issue_rd0},
        {"valid": issue1, "index": issue_idx1, "opcode": issue_op1,
         "unit": issue_unit1, "sequence_id": issue_seq1,
         "rob_slot": issue_rob1, "rd": issue_rd1}]

    # Retirement observes only the committed ROB-completed snapshot.
    head_entry = read_rob(ctrl["rob_head"], constants[8])
    retire0 = ir.and_(ir.cmp("eq", head_entry["valid"], constants[1]),
                      ir.cmp("eq", head_entry["completed"], constants[1]))
    one_if_retire0 = ir.zext(retire0)
    head1_index = next_ring(ir, ctrl["rob_head"], one_if_retire0, constants)
    head1_entry = read_rob(head1_index, constants[9])
    retire1 = ir.and_(retire0,
                      ir.and_(ir.cmp("eq", head1_entry["valid"], constants[1]),
                              ir.cmp("eq", head1_entry["completed"], constants[1])))
    retire_count = ir.add(ir.zext(retire0), ir.zext(retire1))

    # Dispatch requires committed free slots/ROB credits; a two-lane bundle is
    # accepted atomically when both heads are present.
    rob_free1 = ir.cmp("slt", ctrl["rob_count"], constants[8])
    rob_free2 = ir.cmp("sle", ctrl["rob_count"], constants[6])
    both_inputs = ir.and_(in0_valid, in1_valid)
    pair_capacity = ir.and_(free_found1, rob_free2)
    pair_dispatch = ir.and_(both_inputs, pair_capacity)
    only0 = ir.and_(in0_valid, ir.not_(in1_valid, ctrue))
    only1 = ir.and_(in1_valid, ir.not_(in0_valid, ctrue))
    single_capacity = ir.and_(free_found0, rob_free1)
    dispatch0 = ir.or_(pair_dispatch, ir.and_(only0, single_capacity))
    dispatch1 = ir.or_(pair_dispatch, ir.and_(only1, single_capacity))
    dispatch_count = ir.add(ir.zext(dispatch0), ir.zext(dispatch1))
    dispatch_slot0 = free_idx0
    dispatch_slot1 = ir.select(dispatch0, free_idx1, free_idx0)
    rob_slot0 = ctrl["rob_tail"]
    rob_slot1 = next_ring(ir, ctrl["rob_tail"], ir.zext(dispatch0), constants)

    # Validate the externally supplied instruction schema.
    prior_seq1 = ir.select(dispatch0, inst_fields[0]["sequence_id"], ctrl["last_dispatch"])
    for lane, valid in ((0, in0_valid), (1, in1_valid)):
        fields = inst_fields[lane]
        opcode_ok = ir.cmp("ult", fields["opcode"], constants[4])
        regs_ok = ir.and_(ir.cmp("ult", fields["rd"], constants[16]),
                          ir.and_(ir.cmp("ult", fields["rs1"], constants[16]),
                                  ir.cmp("ult", fields["rs2"], constants[16])))
        prior = ctrl["last_dispatch"] if lane == 0 else prior_seq1
        seq_ok = ir.cmp("sgt", fields["sequence_id"], prior)
        valid_record = ir.and_(opcode_ok, ir.and_(regs_ok, seq_ok))
        contract = ir.or_(ir.not_(valid, ctrue), valid_record)
        ir.line(f'ac.assert {contract}, "invalid M1 instruction packet"')

    # Read the rename table by architectural register number.  All reads see
    # the same committed snapshot; completion clearing and older-lane rename
    # forwarding are pure combinational transforms of that snapshot.
    def completion_updates(reg: str, port: str) -> tuple[str, list[str]]:
        tag = ir.result("producer", f"ac.state_read @producer[{reg}] port {port} : i32")
        effects: list[str] = []
        for comp in completions:
            comp_tag = ir.add(comp["sequence_id"], constants[1])
            clear = ir.and_(comp["ready"],
                            ir.and_(ir.cmp("eq", comp["rd"], reg),
                                    ir.cmp("eq", tag, comp_tag)))
            effects.append(clear)
            tag = ir.select(clear, constants[0], tag)
        return tag, effects

    dispatch_deps: list[dict[str, str]] = []
    for lane, dispatch in ((0, dispatch0), (1, dispatch1)):
        fields = inst_fields[lane]
        deps: dict[str, str] = {}
        for source in ("rs1", "rs2"):
            source_port = constants[4 + lane * 2 + (0 if source == "rs1" else 1)]
            tag, _ = completion_updates(fields[source], source_port)
            # Lane 1 observes lane 0's rename when both instructions are
            # dispatched together, just as the former statically expanded
            # producer_final table did.
            if lane == 1:
                prior = inst_fields[0]
                prior_writes_source = ir.and_(
                    dispatch0,
                    ir.and_(ir.cmp("ne", prior["rd"], constants[0]),
                            ir.cmp("eq", fields[source], prior["rd"])))
                prior_tag = ir.add(prior["sequence_id"], constants[1])
                tag = ir.select(prior_writes_source, prior_tag, tag)
            tag = ir.select(ir.cmp("eq", fields[source], constants[0]), constants[0], tag)
            deps[source] = tag
        dispatch_deps.append(deps)

    # Side effects: consume accepted inputs, schedule issues, and publish trace.
    def guarded_recv(condition: str, queue: str, ty: str) -> None:
        ir.line(f"scf.if {condition} {{")
        ir.indent += 2
        value, received = ir.value("received_value"), ir.value("received")
        ir.line(f"{value}, {received} = ac.try_recv @{queue} : {ty}")
        ir.line(f'ac.assert {received}, "peeked dispatch input must remain readable"')
        ir.indent -= 2
        ir.line("}")

    def trace(condition: str, queue: str, tick: str, seq: str, phase: int,
              engine: str, unit: str, lane: int) -> None:
        ir.line(f"scf.if {condition} {{")
        ir.indent += 2
        packet = ir.create([("tick", tick), ("sequence_id", seq),
                            ("phase", constants[phase]), ("engine", engine),
                            ("unit", unit), ("lane", constants[lane])], trace_t)
        accepted = ir.result("trace_ok", f"ac.try_send @{queue} {packet} : {trace_t}")
        ir.line(f'ac.assert {accepted}, "trace output must not backpressure semantic run"')
        ir.indent -= 2
        ir.line("}")

    guarded_recv(dispatch0, "in0", instruction_t)
    guarded_recv(dispatch1, "in1", instruction_t)
    trace(dispatch0, "dispatch0", ctrl["tick"], inst_fields[0]["sequence_id"], 0,
          inst_fields[0]["opcode"], inst_fields[0]["opcode"], 0)
    trace(dispatch1, "dispatch1", ctrl["tick"], inst_fields[1]["sequence_id"], 0,
          inst_fields[1]["opcode"], inst_fields[1]["opcode"], 1)

    for lane, issue in enumerate(issue_info):
        ir.line(f"scf.if {issue['valid']} {{")
        ir.indent += 2
        completion = ir.create([("sequence_id", issue["sequence_id"]),
                                ("rob_slot", issue["rob_slot"]),
                                ("rd", issue["rd"]), ("fu", issue["unit"])], completion_t)
        delay = c64[1]
        delay = ir.select(ir.cmp("eq", issue["opcode"], constants[1]), c64[2], delay, "i64")
        delay = ir.select(ir.cmp("eq", issue["opcode"], constants[2]), c64[8], delay, "i64")
        delay = ir.select(ir.cmp("eq", issue["opcode"], constants[3]), c64[4], delay, "i64")
        accepted = ir.result("schedule_ok", f"ac.schedule @completions {completion} after {delay} : {completion_t}")
        ir.line(f'ac.assert {accepted}, "FU completion event capacity invariant"')
        ir.indent -= 2
        ir.line("}")
        trace(issue["valid"], f"issue{lane}", ctrl["tick"], issue["sequence_id"], 1,
              issue["opcode"], issue["unit"], lane)
    for lane, comp in enumerate(completions):
        trace(comp["ready"], f"complete{lane}", ctrl["tick"], comp["sequence_id"], 2,
              comp["fu"], comp["fu"], lane)

    # Differential timing oracle for CUBE: the functional completion remains
    # event-driven, while an explicit eight-stage committed-state pipeline
    # must expose the same sequence in the same cycle.
    cube_completion = cfalse
    cube_completion_seq = constants[0]
    for comp in completions:
        is_cube = ir.and_(comp["ready"], ir.cmp("eq", comp["fu"], constants[3]))
        cube_completion = ir.or_(cube_completion, is_cube)
        cube_completion_seq = ir.select(is_cube, comp["sequence_id"], cube_completion_seq)
    structural_cube = ir.cmp("eq", cube_pipeline[7]["valid"], constants[1])
    same_cube = ir.cmp("eq", cube_pipeline[7]["sequence_id"], cube_completion_seq)
    ir.line(f'ac.assert {ir.or_(ir.not_(cube_completion, ctrue), ir.and_(structural_cube, same_cube))}, "event CUBE completion must match structural stage 7"')
    ir.line(f'ac.assert {ir.or_(ir.not_(structural_cube, ctrue), ir.and_(cube_completion, same_cube))}, "structural CUBE completion must match event path"')
    trace(retire0, "retire0", ctrl["tick"], head_entry["sequence_id"], 3,
          head_entry["opcode"], head_entry["opcode"], 0)
    trace(retire1, "retire1", ctrl["tick"], head1_entry["sequence_id"], 3,
          head1_entry["opcode"], head1_entry["opcode"], 1)

    # Commit one final value per state-array entry.  The bounded loop is kept in
    # ACIR and each induction value names the corresponding physical port.
    def window_update_body(iv: str, args: list[str]) -> list[str]:
        del args
        index = ir.result("window_update_index",
                          f"arith.index_cast {iv} : index to i32")
        entry = read_window(index, index)
        dep1, dep2 = entry["dep1"], entry["dep2"]
        for comp in completions:
            tag = ir.add(comp["sequence_id"], constants[1])
            dep1 = ir.select(ir.and_(comp["ready"], ir.cmp("eq", dep1, tag)), constants[0], dep1)
            dep2 = ir.select(ir.and_(comp["ready"], ir.cmp("eq", dep2, tag)), constants[0], dep2)
        issue_here = ir.or_(ir.and_(issue0, ir.cmp("eq", issue_idx0, index)),
                            ir.and_(issue1, ir.cmp("eq", issue_idx1, index)))
        valid = ir.select(issue_here, constants[0], entry["valid"])
        values = {"valid": valid, "sequence_id": entry["sequence_id"],
                  "opcode": entry["opcode"], "rd": entry["rd"],
                  "dep1": dep1, "dep2": dep2, "rob_slot": entry["rob_slot"]}
        for lane, condition, slot, rob_slot in ((0, dispatch0, dispatch_slot0, rob_slot0),
                                                (1, dispatch1, dispatch_slot1, rob_slot1)):
            here = ir.and_(condition, ir.cmp("eq", slot, index))
            fields = inst_fields[lane]
            replacements = {"valid": constants[1], "sequence_id": fields["sequence_id"],
                            "opcode": fields["opcode"], "rd": fields["rd"],
                            "dep1": dispatch_deps[lane]["rs1"],
                            "dep2": dispatch_deps[lane]["rs2"], "rob_slot": rob_slot}
            for field, replacement in replacements.items():
                values[field] = ir.select(here, replacement, values[field])
        record = ir.create([(field, values[field]) for field in
                            ("valid", "sequence_id", "opcode", "rd", "dep1", "dep2", "rob_slot")],
                           window_t)
        changed = cfalse
        for field in ("valid", "sequence_id", "opcode", "rd", "dep1", "dep2", "rob_slot"):
            changed = ir.or_(changed, ir.cmp("ne", values[field], entry[field]))
        ir.line(f"ac.state_write @window[{index}] {record} when {changed} port {index} : {window_t}")
        return []

    ir.for_iter("window_update", ci0, ci8, ci1, [], window_update_body)

    def rob_update_body(iv: str, args: list[str]) -> list[str]:
        del args
        index = ir.result("rob_update_index",
                          f"arith.index_cast {iv} : index to i32")
        entry = read_rob(index, index)
        valid, completed = entry["valid"], entry["completed"]
        for comp in completions:
            matches = ir.and_(comp["ready"],
                              ir.and_(ir.cmp("eq", comp["rob_slot"], index),
                                      ir.cmp("eq", comp["sequence_id"], entry["sequence_id"])))
            completed = ir.select(matches, constants[1], completed)
        retire_here = ir.or_(ir.and_(retire0, ir.cmp("eq", ctrl["rob_head"], index)),
                             ir.and_(retire1, ir.cmp("eq", head1_index, index)))
        valid = ir.select(retire_here, constants[0], valid)
        completed = ir.select(retire_here, constants[0], completed)
        values = {"valid": valid, "completed": completed,
                  "sequence_id": entry["sequence_id"], "rd": entry["rd"],
                  "opcode": entry["opcode"]}
        for lane, condition, slot in ((0, dispatch0, rob_slot0), (1, dispatch1, rob_slot1)):
            here = ir.and_(condition, ir.cmp("eq", slot, index))
            fields = inst_fields[lane]
            for field, replacement in (("valid", constants[1]), ("completed", constants[0]),
                                       ("sequence_id", fields["sequence_id"]),
                                       ("rd", fields["rd"]), ("opcode", fields["opcode"])):
                values[field] = ir.select(here, replacement, values[field])
        record = ir.create([(field, values[field]) for field in
                            ("valid", "completed", "sequence_id", "rd", "opcode")],
                           rob_t)
        changed = cfalse
        for field in ("valid", "completed", "sequence_id", "rd", "opcode"):
            changed = ir.or_(changed, ir.cmp("ne", values[field], entry[field]))
        ir.line(f"ac.state_write @rob[{index}] {record} when {changed} port {index} : {rob_t}")
        return []

    ir.for_iter("rob_update", ci0, ci8, ci1, [], rob_update_body)

    # Sparse producer commit.  There are at most four candidate registers per
    # tick (two completions and two dispatches).  Each candidate recomputes the
    # final completion->lane0->lane1 value from the committed snapshot.  Only
    # the first effective candidate for an address proposes that final value,
    # which mechanically guarantees single-write-per-entry without scanning
    # all sixteen architectural registers.
    producer_candidates = [comp["rd"] for comp in completions]
    producer_candidates.extend(inst_fields[lane]["rd"] for lane in range(2))
    for candidate_slot, producer_reg in enumerate(producer_candidates):
        producer_tag, effects = completion_updates(
            producer_reg, constants[candidate_slot])
        for lane, dispatch in ((0, dispatch0), (1, dispatch1)):
            fields = inst_fields[lane]
            write_reg = ir.and_(
                dispatch,
                ir.and_(ir.cmp("ne", fields["rd"], constants[0]),
                        ir.cmp("eq", fields["rd"], producer_reg)))
            effects.append(write_reg)
            new_tag = ir.add(fields["sequence_id"], constants[1])
            producer_tag = ir.select(write_reg, new_tag, producer_tag)
        candidate_effect = effects[candidate_slot]
        prior_effect = cfalse
        for effect in effects[:candidate_slot]:
            prior_effect = ir.or_(prior_effect, effect)
        unique_effect = ir.and_(candidate_effect,
                                ir.not_(prior_effect, ctrue))
        ir.line(f"ac.state_write @producer[{producer_reg}] {producer_tag} when {unique_effect} port {constants[candidate_slot]} : i32")

    for fu in range(5):
        issue_for_fu = constants[0]
        used = cfalse
        for issue in issue_info:
            match = ir.and_(issue["valid"], ir.cmp("eq", issue["unit"], constants[fu]))
            issue_for_fu = ir.add(issue_for_fu, ir.zext(match))
            used = ir.or_(used, match)
        inflight = ir.add(adjusted_inflight[fu], issue_for_fu)
        next_issue = ir.select(used, ir.add(ctrl["tick"], constants[1]), fus[fu]["next_issue"])
        record = ir.create([("inflight", inflight), ("next_issue", next_issue)], fu_t)
        changed = ir.or_(ir.cmp("ne", inflight, fus[fu]["inflight"]),
                         ir.cmp("ne", next_issue, fus[fu]["next_issue"]))
        ir.line(f"ac.state_write @fu[{constants[fu]}] {record} when {changed} port {constants[fu]} : {fu_t}")

    completion_count_now = constants[0]
    for comp in completions:
        completion_count_now = ir.add(completion_count_now, ir.zext(comp["ready"]))
    expected_completion_count = completion_count(ctrl["completion_cursor"])
    ir.line(f'ac.assert {ir.cmp("eq", completion_count_now, expected_completion_count)}, "completion reservation must equal observed fixed-latency completions"')
    completion_targets = [completion_index(issue["opcode"])
                          for issue in issue_info]
    completion_candidates = [ctrl["completion_cursor"], *completion_targets]
    for candidate_slot, completion_slot in enumerate(completion_candidates):
        old_value = ir.result(
            "completion_slot_sparse",
            f"ac.state_read @completion_slots[{completion_slot}] port {constants[9 + candidate_slot]} : i32")
        clear = ir.and_(ir.cmp("eq", completion_slot,
                               ctrl["completion_cursor"]),
                        ir.cmp("ne", old_value, constants[0]))
        value = ir.select(clear, constants[0], old_value)
        effects = [clear]
        for issue, target in zip(issue_info, completion_targets):
            hits = ir.and_(issue["valid"],
                           ir.cmp("eq", target, completion_slot))
            effects.append(hits)
            value = ir.add(value, ir.zext(hits))
        candidate_effect = effects[candidate_slot]
        prior_effect = cfalse
        for effect in effects[:candidate_slot]:
            prior_effect = ir.or_(prior_effect, effect)
        unique_effect = ir.and_(candidate_effect,
                                ir.not_(prior_effect, ctrue))
        ir.line(f"ac.state_write @completion_slots[{completion_slot}] {value} when {unique_effect} port {constants[candidate_slot]} : i32")

    cube_issue = cfalse
    cube_issue_seq = constants[0]
    for issue in issue_info:
        is_cube = ir.and_(issue["valid"],
                          ir.cmp("eq", issue["opcode"], constants[2]))
        cube_issue = ir.or_(cube_issue, is_cube)
        cube_issue_seq = ir.select(is_cube, issue["sequence_id"], cube_issue_seq)
    for stage in range(8):
        valid = ir.zext(cube_issue) if stage == 0 else cube_pipeline[stage - 1]["valid"]
        sequence = cube_issue_seq if stage == 0 else cube_pipeline[stage - 1]["sequence_id"]
        record = ir.create([("valid", valid), ("sequence_id", sequence)],
                           cube_stage_t)
        changed = ir.or_(ir.cmp("ne", valid, cube_pipeline[stage]["valid"]),
                         ir.and_(ir.cmp("ne", valid, constants[0]),
                                 ir.cmp("ne", sequence,
                                        cube_pipeline[stage]["sequence_id"])))
        ir.line(f"ac.state_write @cube_pipeline[{constants[stage]}] {record} when {changed} port {constants[stage]} : {cube_stage_t}")

    next_head = next_ring(ir, ctrl["rob_head"], retire_count, constants)
    next_tail = next_ring(ir, ctrl["rob_tail"], dispatch_count, constants)
    next_count = ir.sub(ir.add(ctrl["rob_count"], dispatch_count), retire_count)
    last_seq = ir.select(dispatch0, inst_fields[0]["sequence_id"], ctrl["last_dispatch"])
    last_seq = ir.select(dispatch1, inst_fields[1]["sequence_id"], last_seq)
    next_retired = ir.add(ctrl["retired"], retire_count)
    next_completion_cursor_sum = ir.add(ctrl["completion_cursor"], constants[1])
    next_completion_cursor = ir.select(
        ir.cmp("eq", next_completion_cursor_sum, constants[9]), constants[0],
        next_completion_cursor_sum)
    control_next = ir.create([
        ("tick", ir.add(ctrl["tick"], constants[1])),
        ("rob_head", next_head), ("rob_tail", next_tail),
        ("rob_count", next_count), ("last_dispatch", last_seq),
        ("retired", next_retired),
        ("completion_cursor", next_completion_cursor)], control_t)
    ir.line(f"ac.state_write @control[{constants[0]}] {control_next} when {ctrue} port {constants[0]} : {control_t}")
    ir.line("ac.yield_sim")

    out.extend(ir.lines)
    out.extend(["    }", "    ac.return", "  }", "}"])
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("usage: gen_model.py")
    sys.stdout.write(emit_model())
