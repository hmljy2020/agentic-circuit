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
  limits.maxTicks = 4;
  model.configure(limits);
  const gfsim::TerminationResult result = model.run();
  const auto stats = collectStats(model, true);

  std::map<std::uint64_t, std::uint64_t> completedPerTick;
  for (const gfsim::CommittedEvent &event : model.observations()) {
    std::cout << "event tick=" << event.epoch.time << " owner=" << event.ownerId
              << " category=" << event.category << " name=" << event.name
              << '\n';
    if (event.category == "transaction" && event.name == "completed")
      ++completedPerTick[event.epoch.time];
  }

  const std::string prefix = "/generated/root-model/";
  auto stat = [&](const char *object, const char *name) {
    return stats.at(prefix + std::string(object) + "." + name);
  };
  auto conservation = [&](const char *object) {
    return stat(object, "accepted_transactions") ==
               stat(object, "completed_transactions") +
                   stat(object, "queue_occupancy") &&
           stat(object, "queue_occupancy_peak") <= 1;
  };
  std::uint64_t maxCompletedPerTick = 0;
  for (const auto &[tick, count] : completedPerTick)
    if (count > maxCompletedPerTick)
      maxCompletedPerTick = count;

  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{4, 0} && conservation("source0") &&
      conservation("source1") && conservation("destination") &&
      stat("source0", "accepted_transactions") == 2 &&
      stat("source0", "completed_transactions") == 1 &&
      stat("source0", "queue_occupancy") == 1 &&
      stat("source1", "accepted_transactions") == 1 &&
      stat("source1", "completed_transactions") == 0 &&
      stat("source1", "queue_occupancy") == 1 &&
      stat("destination", "accepted_transactions") == 1 &&
      stat("destination", "completed_transactions") == 0 &&
      stat("destination", "queue_occupancy") == 1 &&
      maxCompletedPerTick <= 1;

  std::cout << "classification="
            << (result.classification == gfsim::TerminationClass::Incomplete
                    ? "incomplete"
                    : "unexpected")
            << '\n'
            << "final_tick=" << result.finalEpoch.time << '\n'
            << "observations=" << model.observations().size() << '\n'
            << "max_completed_per_tick=" << maxCompletedPerTick << '\n'
            << "arbitrate_transfer_passed=" << (passed ? "true" : "false")
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
  std::cout << "benchmark_case=arbitrate_transfer ticks=" << ticks
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
