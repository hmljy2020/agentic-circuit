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
  limits.maxTicks = 6;
  model.configure(limits);
  const gfsim::TerminationResult result = model.run();
  const auto stats = collectStats(model, true);

  for (const gfsim::CommittedEvent &event : model.observations())
    std::cout << "event tick=" << event.epoch.time << " owner=" << event.ownerId
              << " category=" << event.category << " name=" << event.name
              << '\n';

  const std::string prefix = "/generated/root-model/messages.";
  auto stat = [&](const char *name) { return stats.at(prefix + name); };
  const bool conservation =
      stat("accepted_transactions") == stat("completed_transactions") +
                                               stat("queue_occupancy");
  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete &&
      result.finalEpoch == gfsim::Epoch{6, 0} && conservation &&
      stat("accepted_transactions") == 3 &&
      stat("completed_transactions") == 3 &&
      stat("queue_occupancy") == 0 &&
      stat("queue_occupancy_peak") == 1;

  std::cout << "classification="
            << (result.classification == gfsim::TerminationClass::Incomplete
                    ? "incomplete"
                    : "unexpected")
            << '\n'
            << "final_tick=" << result.finalEpoch.time << '\n'
            << "observations=" << model.observations().size() << '\n'
            << "queue_passed=" << (passed ? "true" : "false") << '\n';
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
  std::cout << "benchmark_case=queue ticks=" << ticks
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
