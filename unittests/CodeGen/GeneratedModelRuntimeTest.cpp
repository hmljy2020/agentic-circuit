#include "gfsim/object.h"
#include "gfsim/process.h"
#include "gfsim/queue.h"

#include "gtest/gtest.h"

#include <array>
#include <cstddef>
#include <memory>
#include <vector>

namespace gfsim {
namespace {

class OneShotObject final : public SimObject {
public:
  OneShotObject(ObjectId id, bool active)
      : SimObject(ObjectKind::Compute, "object", id), active_(active) {}

  void doWork(Epoch) override {
    ++workInvocations;
    if (active_ && !committed_)
      pending_ = true;
  }
  void doXfer(Epoch) override {
    if (pending_) {
      committed_ = true;
      pending_ = false;
    }
  }
  bool hasPendingCommit() const override { return pending_; }

  size_t workInvocations = 0;
  bool committed() const { return committed_; }

private:
  bool active_ = false;
  bool pending_ = false;
  bool committed_ = false;
};

class DomainTickObject final : public SimObject {
public:
  DomainTickObject(ObjectId id, SimSystem &system)
      : SimObject(ObjectKind::Process, "domain_tick", id), system_(system) {}

  void doWork(Epoch epoch) override {
    ++workInvocations;
    EXPECT_TRUE(system_.scheduleEvent({{epoch.time + 1, 0}, id(), 0, 0}));
  }

  size_t workInvocations = 0;

private:
  SimSystem &system_;
};

class GeneratedQueueProducer final
    : public ProcessRuntime<GeneratedQueueProducer> {
public:
  GeneratedQueueProducer(ObjectId id, Queue<int> &queue)
      : ProcessRuntime("producer", id, nullptr, 0, 1), queue_(queue) {}

  ProcessStep executeProcessStep(uint32_t pc, Epoch epoch) {
    workEpochs.push_back(epoch.time);
    const int value = pc == 0 ? 10 : 20;
    if (!queue_.proposePush(value)) {
      ++fullRetries;
      return ProcessStep::suspendAt(
          pc, {ProcessWakeKind::QueueWritable, queue_.id()}, pc + 1);
    }
    if (pc == 0)
      return ProcessStep::suspendAt(
          1, {ProcessWakeKind::QueueWritable, queue_.id()}, 1);
    return ProcessStep::terminate();
  }

  std::vector<Tick> workEpochs;
  size_t fullRetries = 0;

private:
  Queue<int> &queue_;
};

class GeneratedQueueConsumer final
    : public ProcessRuntime<GeneratedQueueConsumer> {
public:
  GeneratedQueueConsumer(ObjectId id, Queue<int> &queue)
      : ProcessRuntime("consumer", id, nullptr, 0, 1), queue_(queue) {}

  ProcessStep executeProcessStep(uint32_t, Epoch epoch) {
    workEpochs.push_back(epoch.time);
    auto [value, received] = queue_.tryRecv();
    if (!received) {
      emptyValues.push_back(value);
      return ProcessStep::suspendAt(
          0, {ProcessWakeKind::QueueReadable, queue_.id()}, 1);
    }
    values.push_back(value);
    if (values.size() == 2)
      return ProcessStep::terminate();
    return ProcessStep::suspendAt(
        0, {ProcessWakeKind::QueueReadable, queue_.id()}, 1);
  }

  std::vector<Tick> workEpochs;
  std::vector<int> emptyValues;
  std::vector<int> values;

private:
  Queue<int> &queue_;
};

class FlowProducer final : public ProcessRuntime<FlowProducer> {
public:
  FlowProducer(ObjectId id, Queue<int> &queue)
      : ProcessRuntime("flow_producer", id, nullptr, 0, 1), queue_(queue) {}

  ProcessStep executeProcessStep(uint32_t, Epoch epoch) {
    workEpochs.push_back(epoch.time);
    if (!queue_.proposePush(7))
      return ProcessStep::suspendAt(
          0, {ProcessWakeKind::QueueWritable, queue_.id()}, 1);
    return ProcessStep::terminate();
  }

  std::vector<Tick> workEpochs;

private:
  Queue<int> &queue_;
};

class FlowConsumer final : public ProcessRuntime<FlowConsumer> {
public:
  FlowConsumer(ObjectId id, Queue<int> &queue)
      : ProcessRuntime("flow_consumer", id, nullptr, 0, 1), queue_(queue) {}

  ProcessStep executeProcessStep(uint32_t, Epoch epoch) {
    workEpochs.push_back(epoch.time);
    if (workEpochs.size() == 1)
      return ProcessStep::suspendAt(0, {ProcessWakeKind::NextDelta, 0}, 1);
    auto [value, received] = queue_.tryRecv();
    if (!received)
      return ProcessStep::suspendAt(
          0, {ProcessWakeKind::QueueReadable, queue_.id()}, 1);
    values.push_back(value);
    return values.size() == 2
               ? ProcessStep::terminate()
               : ProcessStep::suspendAt(
                     0, {ProcessWakeKind::QueueReadable, queue_.id()}, 1);
  }

  std::vector<Tick> workEpochs;
  std::vector<int> values;

private:
  Queue<int> &queue_;
};

struct RuntimeObservation {
  size_t activeWorkInvocations = 0;
  size_t idleWorkInvocations = 0;
  size_t activationEdges = 0;
  bool committedResult = false;
};

RuntimeObservation runActiveFrontier(size_t idleCount) {
  SimSystem system("sparse");
  std::vector<std::unique_ptr<OneShotObject>> objects;
  std::vector<DispatchRow> rows;
  objects.reserve(idleCount + 1);
  rows.reserve(idleCount + 1);
  for (size_t index = 0; index <= idleCount; ++index) {
    objects.push_back(std::make_unique<OneShotObject>(index, index == 0));
    rows.push_back(makeDispatchRow(objects.back().get()));
  }
  std::vector<uint32_t> offsets(idleCount + 2, 1);
  offsets.front() = 0;
  const std::array<ObjectId, 1> targets = {0};
  EXPECT_TRUE(system.setDispatchTable(rows));
  EXPECT_TRUE(system.setActivationPlan(offsets, targets));
  EXPECT_TRUE(system.scheduleWork(0, {0, 0}));
  const TerminationResult result = system.run();
  EXPECT_EQ(result.classification, TerminationClass::Completed);

  size_t idleInvocations = 0;
  for (size_t index = 1; index < objects.size(); ++index)
    idleInvocations += objects[index]->workInvocations;
  return {objects.front()->workInvocations, idleInvocations, targets.size(),
          objects.front()->committed()};
}

TEST(GeneratedModelRuntimeTest, PermanentlyIdleObjectsDoNotIncreaseHotWork) {
  const RuntimeObservation baseline = runActiveFrontier(0);
  const RuntimeObservation sparse = runActiveFrontier(4096);
  EXPECT_EQ(sparse.activeWorkInvocations, baseline.activeWorkInvocations);
  EXPECT_EQ(sparse.idleWorkInvocations, 0u);
  EXPECT_EQ(sparse.activationEdges, baseline.activationEdges);
  EXPECT_EQ(sparse.committedResult, baseline.committedResult);
}

TEST(GeneratedModelRuntimeTest, GeneratedDomainLimitStopsBeforeExcessWork) {
  SimSystem system("generated");
  DomainTickObject object(0, system);
  const std::array rows = {makeDispatchRow(&object)};
  ASSERT_TRUE(system.setDispatchTable(rows));
  const std::array domains = {TimeDomainRuntime{"core", 2, 1, 1}};
  ASSERT_TRUE(system.setTimeDomains(domains));
  RuntimeLimits limits;
  limits.maxDomainCycles = {{"core", 2}};
  ASSERT_TRUE(system.setRuntimeLimits(limits));

  const TerminationResult result = system.run();
  EXPECT_EQ(result.classification, TerminationClass::Incomplete);
  EXPECT_EQ(result.diagnosticCode, "max_domain_cycles_reached");
  EXPECT_EQ(result.finalEpoch, (Epoch{5, 0}));
  EXPECT_EQ(result.domainCycles.at("core"), 2u);
  EXPECT_EQ(object.workInvocations, 5u);
}

TEST(GeneratedModelRuntimeTest,
     QueueBackpressurePreservesFifoAndWakesOnFollowingTicks) {
  SimSystem system("generated_queue_backpressure");
  Queue<int> queue("fifo", 1, nullptr, 1, sizeof(int));
  GeneratedQueueProducer producer(0, queue);
  GeneratedQueueConsumer consumer(2, queue);
  const std::array rows = {makeDispatchRow(&producer), makeDispatchRow(&queue),
                           makeDispatchRow(&consumer)};
  constexpr std::array<uint32_t, 4> offsets = {0, 0, 2, 2};
  constexpr std::array<ObjectId, 2> targets = {0, 2};
  queue.bindSystem(&system);
  ASSERT_TRUE(system.setDispatchTable(rows));
  ASSERT_TRUE(system.setActivationPlan(offsets, targets));
  ASSERT_TRUE(system.scheduleWork(producer.id(), {0, 0}));
  ASSERT_TRUE(system.scheduleWork(consumer.id(), {0, 0}));

  const TerminationResult result = system.run();
  EXPECT_EQ(result.classification, TerminationClass::Completed);
  EXPECT_EQ(consumer.values, (std::vector<int>{10, 20}));
  ASSERT_EQ(consumer.emptyValues.size(), 2u);
  EXPECT_EQ(consumer.emptyValues, (std::vector<int>{0, 0}));
  EXPECT_EQ(producer.fullRetries, 1u);
  EXPECT_EQ(producer.workEpochs, (std::vector<Tick>{0, 1, 2}));
  EXPECT_EQ(consumer.workEpochs, (std::vector<Tick>{0, 1, 2, 3}));
  EXPECT_EQ(queue.highWatermark(), 1u);
  EXPECT_EQ(queue.totalPushes(), 2u);
  EXPECT_EQ(queue.totalPops(), 2u);
  EXPECT_TRUE(queue.isEmpty());
  EXPECT_EQ(producer.status(), ProcessStatus::Terminated);
  EXPECT_EQ(consumer.status(), ProcessStatus::Terminated);
}

TEST(GeneratedModelRuntimeTest,
     QueueLinkBackpressurePreservesDataAndHasTwoTickVisibility) {
  SimSystem system("generated_native_flow");
  Queue<int> source("source", 0, nullptr, 1);
  Queue<int> destination("destination", 1, nullptr, 1);
  QueueLink<int> link("link", 2, nullptr, source, destination);
  FlowProducer producer(3, source);
  FlowConsumer consumer(4, destination);

  ASSERT_TRUE(destination.proposePush(99));
  destination.doXfer({0, 0});
  source.bindSystem(&system);
  destination.bindSystem(&system);
  link.bindSystem(&system);
  const std::array rows = {
      makeDispatchRow(&source),   makeDispatchRow(&destination),
      makeDispatchRow(&link),     makeDispatchRow(&producer),
      makeDispatchRow(&consumer),
  };
  constexpr std::array<uint32_t, 6> offsets = {0, 2, 5, 8, 9, 10};
  constexpr std::array<ObjectId, 10> targets = {0, 2, 1, 2, 4, 0, 1, 2, 3, 4};
  ASSERT_TRUE(system.setDispatchTable(rows));
  ASSERT_TRUE(system.setActivationPlan(offsets, targets));
  ASSERT_TRUE(system.scheduleWork(producer.id(), {0, 0}));
  ASSERT_TRUE(system.scheduleWork(consumer.id(), {0, 0}));
  ASSERT_TRUE(system.scheduleWork(link.id(), {0, 0}));

  const TerminationResult result = system.run();
  EXPECT_EQ(result.classification, TerminationClass::Completed);
  EXPECT_EQ(consumer.values, (std::vector<int>{99, 7}));
  EXPECT_EQ(producer.workEpochs, (std::vector<Tick>{0}));
  EXPECT_EQ(consumer.workEpochs, (std::vector<Tick>{0, 1, 2, 3}));
  EXPECT_EQ(link.stalledFull(), 1u);
  EXPECT_EQ(link.transferred(), 1u);
  EXPECT_EQ(source.totalPushes(), 1u);
  EXPECT_EQ(source.totalPops(), 1u);
  EXPECT_EQ(destination.totalPushes(), 2u);
  EXPECT_EQ(destination.totalPops(), 2u);
  EXPECT_TRUE(source.isEmpty());
  EXPECT_TRUE(destination.isEmpty());
}

} // namespace
} // namespace gfsim
