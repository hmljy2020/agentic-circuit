#include "Analysis/ProcessStatePlanInternal.h"
#include "Analysis/ProcessStatePlanTestHooks.h"
#include "ProcessStatePlanTestSupport.h"
#include "acir/Analysis/ProcessStatePlan.h"
#include "acir/InitAllDialects.h"

#include "gtest/gtest.h"

namespace acir {
namespace {

using PlanSetBuilder = detail::PlanSetBuilder;

static ProcessStatePlanSet getYieldOnlyPlan() {
  mlir::DialectRegistry registry;
  registerAllDialects(registry);
  mlir::MLIRContext context(registry);
  auto module = test::parseAndFreezeYieldOnly(context);
  auto built = PlanSetBuilder::buildYieldOnly(*module);
  assert(mlir::succeeded(built));
  return *built;
}

TEST(ProcessStatePlanWakeTest, YieldOnlyWakeIsNextDelta) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  ASSERT_GE(process.wakes().size(), 1u);
  EXPECT_EQ(process.wakes()[0].kind(), ProcessWakeKind::NextDelta);
}

TEST(ProcessStatePlanWakeTest, YieldOnlyWakeHasCorrectTypeKey) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  ASSERT_GE(process.wakes().size(), 1u);
  EXPECT_EQ(process.wakes()[0].typeKey(), "@acir_wake_next_delta");
}

TEST(ProcessStatePlanWakeTest, TransitionLinksWakeCorrectly) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  ASSERT_GE(process.transitions().size(), 1u);
  ASSERT_GE(process.wakes().size(), 1u);
  EXPECT_EQ(process.transitions()[0].wake().value(),
            process.wakes()[0].id().value());
}

TEST(ProcessStatePlanWakeTest, TransitionSourceIsEntryPc) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  ASSERT_GE(process.transitions().size(), 1u);
  EXPECT_EQ(process.transitions()[0].sourcePc().value(), 0u);
  EXPECT_EQ(process.transitions()[0].targetPc().value(), 0u);
}

TEST(ProcessStatePlanWakeTest, QueueWakesRetainExactQueueAndMode) {
  mlir::DialectRegistry registry;
  registerAllDialects(registry);
  mlir::MLIRContext context(registry);
  auto module = test::parseAndFreezeQueueActions(context);
  ASSERT_TRUE(module);
  auto built = planProcessState(*module);
  ASSERT_TRUE(mlir::succeeded(built));
  ASSERT_EQ(built->processes().size(), 1u);

  bool sawReadable = false;
  bool sawWritable = false;
  for (const ProcessWakePlan &wake : built->processes()[0].wakes()) {
    if (wake.kind() == ProcessWakeKind::QueueReadable) {
      sawReadable = true;
      EXPECT_EQ(wake.target(), "fifo_queue");
      EXPECT_EQ(wake.typeKey(), "@acir_wake_queue_readable");
    }
    if (wake.kind() == ProcessWakeKind::QueueWritable) {
      sawWritable = true;
      EXPECT_EQ(wake.target(), "fifo_queue");
      EXPECT_EQ(wake.typeKey(), "@acir_wake_queue_writable");
    }
  }
  EXPECT_TRUE(sawReadable);
  EXPECT_TRUE(sawWritable);
}

} // namespace
} // namespace acir
