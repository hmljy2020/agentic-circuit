#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

// Runner for the 2x2 input-queued crossbar (two VCs per physical channel,
// output VCs depth 2, writability via ac.space free-capacity).
// Proves, on the committed statistics and observation streams:
//   * Test 1 (concurrency): two independent transfers commit in one cycle.
//     The scheduler is the sole pop proposer and runs exactly once per epoch
//     (single-PC, ac.yield_sim-only body), issuing at most one try_recv per
//     input VC, so input completions per epoch <= 2 and <= 1 per queue.
//     Therefore total input completions > maxTicks forces at least one epoch
//     with two input completions; the in-model asserts in @scheduler rule out
//     the two coming from the same physical input (per-input <= 1), so they are
//     two independent input->output transfers in the same cycle.
//   * Test 6 (per-input/output <= 1): enforced in-model by ac.assert in
//     @scheduler (any matching regression fails the run before this runner).
//   * Test 7 (backpressure / no loss): accepted == completed + occupancy and
//     occupancy_peak <= entries on all 8 queues.
//   * Test 8 (determinism): run.sh executes the binary twice and diffs.
//   * Test 10 (B starvation, now the primary observable): with depth-2 output
//     VCs the A-phase grants every tick, so B never finds a free output VC:
//     in*_B fill to depth 2 and never drain, out*_B stay empty. The A queues
//     reach 11 completions in 12 ticks; the B queues complete 0.
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

  // Per-epoch scan of the committed observation stream (all completed events:
  // input transfers + sink drains). Informational; the decisive concurrency
  // proof is the aggregate over the input VCs below.
  std::map<std::uint64_t, std::uint64_t> completedPerEpoch;
  for (const gfsim::CommittedEvent &ev : model.observations()) {
    if (ev.category == "transaction" && ev.name == "completed")
      ++completedPerEpoch[ev.epoch.time];
  }
  std::uint64_t maxCompletedPerEpoch = 0;
  for (const auto &[epoch, count] : completedPerEpoch) {
    if (count > maxCompletedPerEpoch)
      maxCompletedPerEpoch = count;
    std::cout << "epoch " << epoch << " completed=" << count << '\n';
  }

  const std::string prefix = "/generated/root-model/";
  auto stat = [&](const char *object, const char *name) {
    return stats[prefix + object + "." + name];
  };

  // Test 7: every queue conserves flits and never overfills.
  auto conservation = [&](const char *object, std::uint64_t entries) {
    return stat(object, "accepted_transactions") ==
               stat(object, "completed_transactions") +
                   stat(object, "queue_occupancy") &&
           stat(object, "queue_occupancy_peak") <= entries;
  };

  // Test 1: two independent transfers in one cycle (aggregate proof).
  const std::uint64_t inCompletions =
      stat("in0_A", "completed_transactions") +
      stat("in0_B", "completed_transactions") +
      stat("in1_A", "completed_transactions") +
      stat("in1_B", "completed_transactions");

  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{12, 0} &&
      conservation("in0_A", 2) && conservation("in0_B", 2) &&
      conservation("in1_A", 2) && conservation("in1_B", 2) &&
      conservation("out0_A", 2) && conservation("out0_B", 2) &&
      conservation("out1_A", 2) && conservation("out1_B", 2) &&
      inCompletions > 12 &&
      // Pinned from the deterministic run (A grants every tick, B starved).
      stat("in0_A", "accepted_transactions") == 12 &&
      stat("in0_A", "completed_transactions") == 11 &&
      stat("in0_A", "queue_occupancy_peak") == 1 &&
      stat("in0_B", "accepted_transactions") == 2 &&
      stat("in0_B", "completed_transactions") == 0 &&
      stat("in0_B", "queue_occupancy_peak") == 2 &&
      stat("in1_A", "accepted_transactions") == 12 &&
      stat("in1_A", "completed_transactions") == 11 &&
      stat("in1_A", "queue_occupancy_peak") == 1 &&
      stat("in1_B", "accepted_transactions") == 2 &&
      stat("in1_B", "completed_transactions") == 0 &&
      stat("in1_B", "queue_occupancy_peak") == 2 &&
      stat("out0_A", "accepted_transactions") == 11 &&
      stat("out0_A", "completed_transactions") == 10 &&
      stat("out0_A", "queue_occupancy_peak") == 1 &&
      stat("out0_B", "accepted_transactions") == 0 &&
      stat("out0_B", "completed_transactions") == 0 &&
      stat("out0_B", "queue_occupancy_peak") == 0 &&
      stat("out1_A", "accepted_transactions") == 11 &&
      stat("out1_A", "completed_transactions") == 10 &&
      stat("out1_A", "queue_occupancy_peak") == 1 &&
      stat("out1_B", "accepted_transactions") == 0 &&
      stat("out1_B", "completed_transactions") == 0 &&
      stat("out1_B", "queue_occupancy_peak") == 0 &&
      inCompletions == 22;
  std::cout << "crossbar_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
