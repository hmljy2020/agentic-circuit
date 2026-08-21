#include "generated/model.h"

#include <cstdint>
#include <iostream>
#include <map>
#include <string>

namespace {
bool endsWith(const std::string &value, const std::string &suffix) {
  return value.size() >= suffix.size() &&
         value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}
} // namespace

int main() {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = 24;
  model.configure(limits);
  const gfsim::TerminationResult result = model.run();

  std::map<std::string, std::map<std::string, std::uint64_t>> stats;
  for (const gfsim::StatSnapshot &stat : model.statistics()) {
    stats[stat.objectPath][stat.name] = stat.value;
    std::cout << "stat " << stat.objectPath << '.' << stat.name << '='
              << stat.value << '\n';
  }
  auto findQueue = [&](const std::string &suffix)
      -> const std::map<std::string, std::uint64_t> * {
    for (const auto &[path, values] : stats)
      if (endsWith(path, suffix))
        return &values;
    return nullptr;
  };
  auto count = [&](const std::string &suffix, const char *name) {
    const auto *queue = findQueue(suffix);
    if (!queue)
      return std::uint64_t{0};
    const auto found = queue->find(name);
    return found == queue->end() ? std::uint64_t{0} : found->second;
  };

  bool conserved = true;
  for (const auto &[path, values] : stats) {
    const auto accepted = values.find("accepted_transactions");
    const auto completed = values.find("completed_transactions");
    const auto occupancy = values.find("queue_occupancy");
    const auto peak = values.find("queue_occupancy_peak");
    if (accepted == values.end())
      continue;
    conserved = conserved && completed != values.end() &&
                occupancy != values.end() && peak != values.end() &&
                accepted->second == completed->second + occupancy->second &&
                peak->second <= 2;
  }

  const bool passed =
      result.classification == gfsim::TerminationClass::Incomplete && conserved &&
      count("/rx1", "completed_transactions") > 0 &&
      count("/rx2", "completed_transactions") > 0 &&
      count("/rx0", "accepted_transactions") == 0 &&
      count("/rx3", "accepted_transactions") == 0 &&
      count("/ring/link_n3_to_n0_cw", "accepted_transactions") > 0 &&
      count("/ring/link_n2_to_n3_cw", "accepted_transactions") > 0;
  std::cout << "classification="
            << (result.classification == gfsim::TerminationClass::Incomplete
                    ? "incomplete"
                    : "unexpected")
            << '\n';
  std::cout << "ring_noc_passed=" << (passed ? "true" : "false") << '\n';
  return passed ? 0 : 1;
}
