#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 12;
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

  // Invariants. The register pipeline must conserve every flit and never
  // exceed the capacity-1 entries:
  //   * accepted == completed + occupancy on every queue,
  //   * occupancy_peak <= 1 on every queue,
  //   * every input operand the ALU loaded was stored in its register
  //     (op_a.completed == reg_a.accepted, op_b.completed == reg_b.accepted),
  //   * every stored pair was computed exactly once and produced one result
  //     (reg_a.completed == reg_b.completed == result.accepted).
  // The in-model ac.assert in @alu (sum == 5) already fails the run on any
  // wrong sum, so the counts below are the pipeline-level checks.
  auto conservation = [&](const char *object) {
    return stat(object, "accepted_transactions") ==
               stat(object, "completed_transactions") +
                   stat(object, "queue_occupancy") &&
           stat(object, "queue_occupancy_peak") <= 1;
  };

  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{12, 0} &&
      conservation("op_a") && conservation("op_b") &&
      conservation("op_b_delay") && conservation("reg_a") &&
      conservation("reg_b") && conservation("result") &&
      stat("op_a", "completed_transactions") ==
          stat("reg_a", "accepted_transactions") &&
      stat("op_b", "completed_transactions") ==
          stat("reg_b", "accepted_transactions") &&
      stat("reg_a", "completed_transactions") ==
          stat("reg_b", "completed_transactions") &&
      stat("reg_a", "completed_transactions") ==
          stat("result", "accepted_transactions") &&
      stat("op_a", "accepted_transactions") == 6 &&
      stat("op_a", "completed_transactions") == 5 &&
      stat("op_a", "queue_occupancy_peak") == 1 &&
      stat("op_b", "accepted_transactions") == 6 &&
      stat("op_b", "completed_transactions") == 5 &&
      stat("op_b", "queue_occupancy_peak") == 1 &&
      stat("op_b_delay", "accepted_transactions") == 6 &&
      stat("op_b_delay", "completed_transactions") == 6 &&
      stat("op_b_delay", "queue_occupancy_peak") == 1 &&
      stat("reg_a", "accepted_transactions") == 5 &&
      stat("reg_a", "completed_transactions") == 5 &&
      stat("reg_a", "queue_occupancy_peak") == 1 &&
      stat("reg_b", "accepted_transactions") == 5 &&
      stat("reg_b", "completed_transactions") == 5 &&
      stat("reg_b", "queue_occupancy_peak") == 1 &&
      stat("result", "accepted_transactions") == 5 &&
      stat("result", "completed_transactions") == 4 &&
      stat("result", "queue_occupancy_peak") == 1;
  std::cout << "adder_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
