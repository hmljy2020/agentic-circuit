#include "generated/model.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <map>
#include <set>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

enum Opcode : std::int32_t { Scalar = 0, Vec = 1, Cube = 2, Dma = 3 };

struct Instruction {
  std::int32_t sequenceId;
  std::int32_t opcode;
  std::int32_t rd;
  std::int32_t rs1;
  std::int32_t rs2;
};

struct TraceEvent {
  std::int32_t tick;
  std::int32_t sequenceId;
  std::int32_t phase;
  std::int32_t engine;
  std::int32_t unit;
  std::int32_t lane;
};

static_assert(sizeof(Instruction) == 20);
static_assert(sizeof(TraceEvent) == 24);

constexpr std::array<Instruction, 16> kProgram{{
    {1, Cube, 1, 0, 0},   {2, Vec, 2, 0, 0},
    {3, Vec, 3, 1, 0},    {4, Scalar, 4, 0, 0},
    {5, Dma, 5, 0, 0},    {6, Vec, 6, 2, 0},
    {7, Cube, 7, 0, 0},   {8, Scalar, 8, 4, 0},
    {9, Vec, 2, 0, 0},    {10, Scalar, 9, 2, 0},
    {11, Dma, 10, 0, 0},  {12, Vec, 11, 0, 0},
    {13, Scalar, 12, 3, 0}, {14, Vec, 13, 0, 0},
    {15, Cube, 14, 5, 0}, {16, Dma, 15, 0, 0},
}};

template <typename T> std::span<const std::byte> asBytes(const T &value) {
  return {reinterpret_cast<const std::byte *>(&value), sizeof(T)};
}

template <typename T> std::span<std::byte> asWritableBytes(T &value) {
  return {reinterpret_cast<std::byte *>(&value), sizeof(T)};
}

struct RunResult {
  std::vector<TraceEvent> trace;
  std::uint64_t ticks = 0;
  double seconds = 0.0;
};

std::size_t findInput(const acsim_generated::Model &model,
                      std::string_view name) {
  for (std::size_t i = 0; i < model.hostInputCount(); ++i)
    if (model.hostInputName(i) == name)
      return i;
  throw std::runtime_error("missing host input: " + std::string(name));
}

std::vector<std::size_t> traceOutputs(const acsim_generated::Model &model) {
  std::vector<std::size_t> result;
  for (std::size_t i = 0; i < model.hostOutputCount(); ++i) {
    if (model.hostOutputSize(i) != sizeof(TraceEvent))
      throw std::runtime_error("unexpected trace output packet size");
    result.push_back(i);
  }
  if (result.size() != 8)
    throw std::runtime_error("M1 must expose eight trace lanes");
  return result;
}

RunResult runProgram(bool benchmark) {
  acsim_generated::Model model;
  gfsim::RuntimeLimits limits;
  limits.maxTicks = benchmark ? 200000 : 256;
  model.configure(limits);
  const std::size_t lane0 = findInput(model, "lane0");
  const std::size_t lane1 = findInput(model, "lane1");
  const auto outputs = traceOutputs(model);

  std::size_t nextPair = 0;
  std::size_t retired = 0;
  RunResult result;
  const auto start = std::chrono::steady_clock::now();
  while (benchmark || retired < kProgram.size()) {
    if (!benchmark && nextPair < kProgram.size() &&
        model.hostInputReady(lane0) && model.hostInputReady(lane1)) {
      if (!model.offerBytes(lane0, asBytes(kProgram[nextPair])) ||
          !model.offerBytes(lane1, asBytes(kProgram[nextPair + 1])))
        throw std::runtime_error("an input became unavailable during bundle offer");
      nextPair += 2;
    }
    if (!model.stepTick())
      throw std::runtime_error("simulation stopped before acceptance criteria");
    ++result.ticks;
    for (std::size_t output : outputs) {
      while (model.hostOutputReady(output)) {
        TraceEvent event{};
        if (!model.takeBytes(output, asWritableBytes(event)))
          throw std::runtime_error("ready trace output rejected takeBytes");
        if (!benchmark) {
          result.trace.push_back(event);
          if (event.phase == 3)
            ++retired;
        }
      }
    }
    if (benchmark && result.ticks == limits.maxTicks)
      break;
    if (!benchmark && result.ticks == limits.maxTicks)
      throw std::runtime_error("semantic program timed out");
  }
  result.seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
          .count();
  return result;
}

bool validate(const RunResult &run, bool print) {
  std::array<std::map<std::int32_t, TraceEvent>, 4> byPhase;
  std::map<std::pair<std::int32_t, std::int32_t>, unsigned> width;
  bool ok = true;
  for (const TraceEvent &event : run.trace) {
    ok &= event.phase >= 0 && event.phase < 4;
    if (event.phase < 0 || event.phase >= 4)
      continue;
    ok &= byPhase[event.phase].emplace(event.sequenceId, event).second;
    ++width[{event.phase, event.tick}];
  }
  for (const auto &phase : byPhase)
    ok &= phase.size() == kProgram.size();
  for (const auto &[key, count] : width)
    ok &= count <= 2;

  std::int32_t previousRetire = 0;
  for (const auto &[sequence, event] : byPhase[3]) {
    ok &= sequence == previousRetire + 1;
    previousRetire = sequence;
  }

  const std::array<std::int32_t, 4> latency{{1, 2, 8, 4}};
  for (const Instruction &instruction : kProgram) {
    const auto dispatch = byPhase[0].find(instruction.sequenceId);
    const auto issue = byPhase[1].find(instruction.sequenceId);
    const auto complete = byPhase[2].find(instruction.sequenceId);
    const auto retire = byPhase[3].find(instruction.sequenceId);
    if (dispatch == byPhase[0].end() || issue == byPhase[1].end() ||
        complete == byPhase[2].end() || retire == byPhase[3].end()) {
      ok = false;
      continue;
    }
    ok &= dispatch->second.tick <= issue->second.tick;
    ok &= complete->second.tick ==
          issue->second.tick + latency[instruction.opcode];
    ok &= complete->second.tick < retire->second.tick;
  }

  // Sequential rename oracle: every nonzero source waits for the most recent
  // older writer, including a writer in the other lane of the same bundle.
  std::array<std::int32_t, 16> producer{};
  for (const Instruction &instruction : kProgram) {
    for (std::int32_t source : {instruction.rs1, instruction.rs2}) {
      if (source == 0 || producer[source] == 0)
        continue;
      const std::int32_t dependency = producer[source];
      ok &= byPhase[1].at(instruction.sequenceId).tick >
            byPhase[2].at(dependency).tick;
    }
    if (instruction.rd != 0)
      producer[instruction.rd] = instruction.sequenceId;
  }

  // A short scalar/vector instruction must finish while the first CUBE is
  // still active: this is the minimum latency-hiding claim of M1.
  ok &= byPhase[2].at(2).tick < byPhase[2].at(1).tick;
  if (print) {
    for (const TraceEvent &event : run.trace)
      std::cout << "trace tick=" << event.tick << " seq=" << event.sequenceId
                << " phase=" << event.phase << " engine=" << event.engine
                << " unit=" << event.unit << " lane=" << event.lane << '\n';
    std::cout << "instructions=" << kProgram.size()
              << " trace_events=" << run.trace.size()
              << " ticks=" << run.ticks
              << " semantic_passed=" << (ok ? "true" : "false") << '\n';
  }
  return ok;
}

int semanticRun() {
  try {
    const RunResult first = runProgram(false);
    const RunResult second = runProgram(false);
    const bool deterministic =
        first.trace.size() == second.trace.size() &&
        std::equal(first.trace.begin(), first.trace.end(), second.trace.begin(),
                   [](const TraceEvent &a, const TraceEvent &b) {
                     return std::memcmp(&a, &b, sizeof(a)) == 0;
                   });
    const bool passed = validate(first, true) && validate(second, false) &&
                        deterministic;
    std::cout << "deterministic=" << (deterministic ? "true" : "false")
              << '\n';
    return passed ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << "semantic failure: " << error.what() << '\n';
    return 1;
  }
}

int benchmarkRun() {
  try {
    constexpr std::uint64_t kTicks = 10000;
    acsim_generated::Model model;
    gfsim::RuntimeLimits limits;
    // Keep the runtime limit one tick beyond the measured interval: stepTick
    // reports false when the configured terminal epoch is reached.
    limits.maxTicks = kTicks + 1;
    model.configure(limits);
    const auto start = std::chrono::steady_clock::now();
    for (std::uint64_t tick = 0; tick < kTicks; ++tick)
      if (!model.stepTick())
        throw std::runtime_error("benchmark stopped early");
    const double seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
            .count();
    std::cout << "benchmark_ticks=" << kTicks << " seconds=" << seconds
              << " ticks_per_second=" << static_cast<double>(kTicks) / seconds
              << " passed=true\n";
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "benchmark failure: " << error.what() << '\n';
    return 1;
  }
}

} // namespace

int main(int argc, char **argv) {
  if (argc == 1)
    return semanticRun();
  if (argc == 2 && std::string(argv[1]) == "--benchmark")
    return benchmarkRun();
  std::cerr << "usage: " << argv[0] << " [--benchmark]\n";
  return 2;
}
