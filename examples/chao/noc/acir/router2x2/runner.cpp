#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 24;
  model.configure(limits);

  const gfsim::TerminationResult result = model.run();
  std::map<std::string, std::uint64_t> stats;
  for (const gfsim::StatSnapshot &stat : model.statistics()) {
    const std::string key = stat.objectPath + "." + stat.name;
    stats.emplace(key, stat.value);
    std::cout << "stat " << key << '=' << stat.value << '\n';
  }

  std::cout << "classification="
            << (result.classification == gfsim::TerminationClass::Incomplete
                    ? "incomplete"
                    : "unexpected")
            << '\n'
            << "final_tick=" << result.finalEpoch.time << '\n'
            << "observations=" << model.observations().size() << '\n';

  const std::string prefix = "/generated/root-model/";
  auto stat = [&](const char *object, const char *name) {
    return stats[prefix + object + "." + name];
  };

  // Invariants. The run is continuous: every process body terminates in
  // ac.yield_sim, which resumes the process at its entry next tick, so the
  // producers re-propose their bursts and a full queue soft-rejects. There is
  // therefore no fixed "16 flits, no loss" total; the meaningful checks are
  // conservation and capacity:
  //
  //  * accepted == completed + occupancy on every queue (no flit is lost or
  //    duplicated; the in-model per-flit asserts in model.mlir already fail
  //    the run on any corruption or misroute),
  //  * occupancy_peak <= entries (16) on every queue,
  //  * every flit drained from @in0 lands on exactly one output
  //    (in0.completed == out0.accepted + out1.accepted),
  //  * and the exact steady-state values below, calibrated from the
  //    deterministic run (see the README stats table; run the binary twice
  //    and diff — output is byte-identical).
  //
  // The headline is the arbitration result: strict priority (in0 > in1) under
  // saturated inputs starves @in1 — zero completions, pinned at the 16-entry
  // capacity — while @in0 saturates at 15/16 and drains one flit per tick
  // into out0/out1 by destination parity. Deterministic and observable.
  auto conservation = [&](const char *object) {
    return stat(object, "accepted_transactions") ==
               stat(object, "completed_transactions") +
                   stat(object, "queue_occupancy") &&
           stat(object, "queue_occupancy_peak") <= 16;
  };

  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{24, 0} &&
      conservation("in0") && conservation("in1") &&
      conservation("out0") && conservation("out1") &&
      stat("in0", "completed_transactions") ==
          stat("out0", "accepted_transactions") +
              stat("out1", "accepted_transactions") &&
      stat("in0", "accepted_transactions") == 38 &&
      stat("in0", "completed_transactions") == 23 &&
      stat("in0", "queue_occupancy_peak") == 15 &&
      stat("in1", "accepted_transactions") == 16 &&
      stat("in1", "completed_transactions") == 0 &&
      stat("in1", "queue_occupancy_peak") == 16 &&
      stat("out0", "accepted_transactions") == 15 &&
      stat("out0", "completed_transactions") == 14 &&
      stat("out0", "queue_occupancy_peak") == 1 &&
      stat("out1", "accepted_transactions") == 8 &&
      stat("out1", "completed_transactions") == 8 &&
      stat("out1", "queue_occupancy_peak") == 1;
  std::cout << "router2x2_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
