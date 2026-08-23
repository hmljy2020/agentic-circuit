#include "generated/model.h"

#include <chrono>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>

namespace {

std::map<std::string, std::uint64_t>
collectStats(acsim_generated::Model &model, bool print) {
  std::map<std::string, std::uint64_t> stats;
  for (const gfsim::StatSnapshot &stat : model.statistics()) {
    const std::string key = stat.objectPath + "." + stat.name;
    stats.emplace(key, stat.value);
    if (print)
      std::cout << "stat " << key << '=' << stat.value << '\n';
  }
  return stats;
}

int runSemantic() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 12;
  model.configure(limits);
  const gfsim::TerminationResult result = model.run();
  const auto stats = collectStats(model, true);

  for (const gfsim::CommittedEvent &event : model.observations())
    std::cout << "event tick=" << event.epoch.time << " owner=" << event.ownerId
              << " category=" << event.category << " name=" << event.name
              << '\n';

  const std::string prefix = "/generated/root-model/";
  auto stat = [&](const char *object, const char *name) {
    return stats.at(prefix + std::string(object) + "." + name);
  };
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
      stat("ordered", "accepted_events") == 24 &&
      stat("ordered", "completed_events") == 20 &&
      stat("ordered", "event_queue_occupancy") == 4 &&
      stat("ordered", "event_queue_occupancy_peak") == 4 &&
      stat("results", "accepted_transactions") == 5 &&
      stat("results", "completed_transactions") == 4 &&
      stat("results", "queue_occupancy") == 1 &&
      stat("results", "queue_occupancy_peak") == 1 &&
      model.observations().size() == 18;

  std::cout << "classification="
            << (result.classification == gfsim::TerminationClass::Incomplete
                    ? "incomplete"
                    : "unexpected")
            << '\n'
            << "final_tick=" << result.finalEpoch.time << '\n'
            << "observations=" << model.observations().size() << '\n'
            << "event_latency_passed=" << (passed ? "true" : "false")
            << '\n';
  return passed ? 0 : 1;
}

int runBenchmark() {
  constexpr std::uint64_t ticks = 10000;
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = ticks;
  model.configure(limits);
  const auto start = std::chrono::steady_clock::now();
  const gfsim::TerminationResult result = model.run();
  const auto stop = std::chrono::steady_clock::now();
  const double seconds = std::chrono::duration<double>(stop - start).count();
  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{ticks, 0};
  std::cout << "benchmark_case=event_latency ticks=" << ticks
            << " seconds=" << seconds
            << " ticks_per_second=" << static_cast<double>(ticks) / seconds
            << " passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}

} // namespace

int main(int argc, char **argv) {
  if (argc == 1)
    return runSemantic();
  if (argc == 2 && std::string(argv[1]) == "--benchmark")
    return runBenchmark();
  std::cerr << "usage: " << argv[0] << " [--benchmark]\n";
  return 2;
}
