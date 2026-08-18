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

  // Derivation (cross-checked against include/gfsim/queue.h and
  // lib/gfsim/system.cpp): ticks 0..11 execute. The producer schedules one
  // dispatch event per tick with delay 2 and never soft-rejects (occupancy
  // <= 2 < capacity 8) -> dispatch.accepted == 12. Fu pops at ticks 2..11 ->
  // dispatch.completed == 10, occupancy 2, peak 2. Each fu pop schedules one
  // completion (delay 1); @complete has capacity 8 so none is rejected ->
  // complete.accepted == 10 == dispatch.completed.
  //
  // The capacity-1 results queue throttles retire: when retire pops a
  // completion but results is full, it parks the value in a live slot and
  // retries the send (waiting for "writable") instead of popping again. So
  // retire forwards one completion every other tick -> complete.completed ==
  // results.accepted == 5, and @complete carries a backlog of
  // 10 - 5 == 5 (its occupancy and peak). Sink drains results one tick
  // behind -> results.completed == 4, final occupancy 1, peak 1.
  //
  // Exact values below were confirmed against a deterministic run (the
  // binary was executed twice and stdout diffed). If a future compiler or
  // runtime change alters the phase ordering, update these constants AND the
  // README stats table together. Structural relationships that must hold:
  // dispatch.accepted == maxTicks; dispatch.completed == accepted - 2;
  // complete.accepted == dispatch.completed; complete.completed ==
  // results.accepted; complete.occupancy == complete.accepted -
  // complete.completed; results.completed == results.accepted - 1.
  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{12, 0} &&
      stat("dispatch", "accepted_events") == 12 &&
      stat("dispatch", "completed_events") == 10 &&
      stat("dispatch", "event_queue_occupancy") == 2 &&
      stat("dispatch", "event_queue_occupancy_peak") == 2 &&
      stat("complete", "accepted_events") == 10 &&
      stat("complete", "completed_events") == 5 &&
      stat("complete", "event_queue_occupancy") == 5 &&
      stat("complete", "event_queue_occupancy_peak") == 5 &&
      stat("results", "accepted_transactions") == 5 &&
      stat("results", "completed_transactions") == 4 &&
      stat("results", "queue_occupancy") == 1 &&
      stat("results", "queue_occupancy_peak") == 1 &&
      model.observations().size() == 18;
  std::cout << "fu_latency_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
