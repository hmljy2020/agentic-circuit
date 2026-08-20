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

TEST(ProcessStatePlanEmissionTest, YieldOnlyBlockCostIsTwo) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  ASSERT_GE(process.blocks().size(), 1u);
  EXPECT_EQ(process.blocks()[0].cost(), 2u);
}

TEST(ProcessStatePlanEmissionTest, YieldOnlyNoLiveSlots) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  EXPECT_EQ(process.liveSlots().size(), 0u);
}

TEST(ProcessStatePlanEmissionTest, YieldOnlyFairnessEqualsBlockCost) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  EXPECT_EQ(process.fairnessWork(), 2u);
}

TEST(ProcessStatePlanEmissionTest, YieldOnlyEdgeIsSuspend) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  ASSERT_GE(process.blocks().size(), 1u);
  EXPECT_EQ(process.blocks()[0].edge().kind(), ProcessControlEdgeKind::Suspend);
}

TEST(ProcessStatePlanEmissionTest, NoCapturesInYieldOnly) {
  auto plans = getYieldOnlyPlan();
  const auto &process = plans.processes()[0];
  EXPECT_EQ(process.captures().size(), 0u);
}

TEST(ProcessStatePlanEmissionTest, NoValueTypesInYieldOnly) {
  auto plans = getYieldOnlyPlan();
  EXPECT_EQ(plans.valueTypes().size(), 0u);
}

TEST(ProcessStatePlanEmissionTest, OneCalleeInYieldOnly) {
  auto plans = getYieldOnlyPlan();
  ASSERT_GE(plans.callees().size(), 1u);
  EXPECT_EQ(plans.callees()[0].id().value(), 0u);
  EXPECT_EQ(plans.callees()[0].role(), ProcessHelperRole::WakeNextDelta);
}

TEST(ProcessStatePlanEmissionTest,
     QueueActionsHaveTypedRefsDeclarationsAndDeterministicCallees) {
  mlir::DialectRegistry registry;
  registerAllDialects(registry);
  mlir::MLIRContext context(registry);
  auto module = test::parseAndFreezeQueueActions(context);
  ASSERT_TRUE(module);
  auto built = planProcessState(*module);
  ASSERT_TRUE(mlir::succeeded(built));
  ASSERT_TRUE(mlir::succeeded(verifyProcessStatePlan(*built)));

  const ProcessGeneratedCalleePlan *send = nullptr;
  const ProcessGeneratedCalleePlan *recv = nullptr;
  const ProcessGeneratedCalleePlan *peek = nullptr;
  const ProcessGeneratedCalleePlan *space = nullptr;
  const ProcessGeneratedCalleePlan *readable = nullptr;
  const ProcessGeneratedCalleePlan *writable = nullptr;
  for (auto [index, callee] : llvm::enumerate(built->callees())) {
    EXPECT_EQ(callee.id().value(), index);
    switch (callee.role()) {
    case ProcessHelperRole::QueueTrySend:
      send = &callee;
      break;
    case ProcessHelperRole::QueueTryRecv:
      recv = &callee;
      break;
    case ProcessHelperRole::QueuePeek:
      peek = &callee;
      break;
    case ProcessHelperRole::QueueSpace:
      space = &callee;
      break;
    case ProcessHelperRole::WakeQueueReadable:
      readable = &callee;
      break;
    case ProcessHelperRole::WakeQueueWritable:
      writable = &callee;
      break;
    default:
      break;
    }
  }
  ASSERT_NE(send, nullptr);
  ASSERT_NE(recv, nullptr);
  ASSERT_NE(peek, nullptr);
  ASSERT_NE(space, nullptr);
  ASSERT_NE(readable, nullptr);
  ASSERT_NE(writable, nullptr);
  ASSERT_EQ(send->inputTypeKeys().size(), 2u);
  EXPECT_EQ(send->inputTypeKeys()[0], "queue-ref:@queue");
  EXPECT_EQ(send->inputTypeKeys()[1], "mlir:i32");
  ASSERT_EQ(recv->inputTypeKeys().size(), 1u);
  EXPECT_EQ(recv->inputTypeKeys()[0], "queue-ref:@queue");
  ASSERT_EQ(peek->inputTypeKeys().size(), 1u);
  EXPECT_EQ(peek->inputTypeKeys()[0], "queue-ref:@queue");
  ASSERT_EQ(peek->resultTypeKeys().size(), 2u);
  EXPECT_EQ(peek->resultTypeKeys()[0], "mlir:i32");
  EXPECT_EQ(peek->resultTypeKeys()[1], "mlir:i1");
  ASSERT_EQ(space->inputTypeKeys().size(), 1u);
  EXPECT_EQ(space->inputTypeKeys()[0], "queue-ref:@queue");
  ASSERT_EQ(space->resultTypeKeys().size(), 1u);
  EXPECT_EQ(space->resultTypeKeys()[0], "mlir:i32");
  EXPECT_EQ(send->declarations().size(), 1u);
  EXPECT_EQ(recv->declarations().size(), 1u);
  EXPECT_EQ(peek->declarations().size(), 1u);
  EXPECT_EQ(space->declarations().size(), 1u);
  EXPECT_TRUE(readable->declarations().empty());
  EXPECT_TRUE(writable->declarations().empty());
  EXPECT_FALSE(readable->sourceOperations().empty());
  EXPECT_FALSE(writable->sourceOperations().empty());
  EXPECT_EQ(send->sourceOperations().size(), 1u);
  EXPECT_EQ(recv->sourceOperations().size(), 1u);
  EXPECT_EQ(peek->sourceOperations().size(), 1u);
  EXPECT_EQ(space->sourceOperations().size(), 1u);

  auto first = serializeProcessStatePlan(*built);
  auto second = serializeProcessStatePlan(*built);
  ASSERT_TRUE(static_cast<bool>(first));
  ASSERT_TRUE(static_cast<bool>(second));
  EXPECT_EQ(*first, *second);
}

TEST(ProcessStatePlanEmissionTest,
     EightIdenticalQueuesShareSendAndWritableSpecializations) {
  mlir::MLIRContext context;
  mlir::DialectRegistry registry;
  registerAllDialects(registry);
  context.appendDialectRegistry(registry);
  auto module = test::parseAndFreezeManyQueueActions(context, 8);
  ASSERT_TRUE(module);
  auto built = planProcessState(*module);
  ASSERT_TRUE(mlir::succeeded(built));

  const ProcessGeneratedCalleePlan *send = nullptr;
  const ProcessGeneratedCalleePlan *writable = nullptr;
  size_t sendCallees = 0;
  size_t writableCallees = 0;
  for (const ProcessGeneratedCalleePlan &callee : built->callees()) {
    if (callee.role() == ProcessHelperRole::QueueTrySend) {
      send = &callee;
      ++sendCallees;
    }
    if (callee.role() == ProcessHelperRole::WakeQueueWritable) {
      writable = &callee;
      ++writableCallees;
    }
  }
  ASSERT_NE(send, nullptr);
  ASSERT_NE(writable, nullptr);
  EXPECT_EQ(sendCallees, 1u);
  EXPECT_EQ(writableCallees, 1u);
  EXPECT_EQ(send->sourceOperations().size(), 8u);
  EXPECT_EQ(send->declarations().size(), 8u);
  EXPECT_EQ(writable->sourceOperations().size(), 8u);
  EXPECT_EQ(built->processes().front().pcs().size(), 9u);
  EXPECT_GE(built->processes().front().wakes().size(), 9u);
}

TEST(ProcessStatePlanEmissionTest,
     QueueTransfersShareOnePayloadSpecializationWithOrderedOwners) {
  mlir::DialectRegistry registry;
  registerAllDialects(registry);
  mlir::MLIRContext context(registry);
  auto module = test::parseAndFreezeQueueTransfers(context);
  ASSERT_TRUE(module);
  auto built = planProcessState(*module);
  ASSERT_TRUE(mlir::succeeded(built));
  ASSERT_TRUE(mlir::succeeded(verifyProcessStatePlan(*built)));

  const ProcessGeneratedCalleePlan *transfer = nullptr;
  size_t count = 0;
  for (const ProcessGeneratedCalleePlan &callee : built->callees())
    if (callee.role() == ProcessHelperRole::QueueTryTransfer) {
      transfer = &callee;
      ++count;
    }
  ASSERT_NE(transfer, nullptr);
  EXPECT_EQ(count, 1u);
  EXPECT_EQ(transfer->effect(), ProcessEffectKind::Stateful);
  ASSERT_EQ(transfer->inputTypeKeys().size(), 3u);
  EXPECT_EQ(transfer->inputTypeKeys()[0], "queue-ref:@source");
  EXPECT_EQ(transfer->inputTypeKeys()[1], "queue-ref:@destination");
  EXPECT_EQ(transfer->inputTypeKeys()[2], "mlir:i1");
  ASSERT_EQ(transfer->resultTypeKeys().size(), 1u);
  EXPECT_EQ(transfer->resultTypeKeys()[0], "mlir:i1");
  EXPECT_EQ(transfer->payload().queueTryTransfer().element(), "mlir:i32");
  EXPECT_EQ(transfer->payload().queueTryTransfer().source(), "@source");
  EXPECT_EQ(transfer->payload().queueTryTransfer().destination(),
            "@destination");
  EXPECT_EQ(transfer->sourceOperations().size(), 2u);
  EXPECT_EQ(transfer->declarations().size(), 4u);

  auto report = serializeProcessStatePlan(*built);
  ASSERT_TRUE(static_cast<bool>(report));
  EXPECT_NE(report->find("\"role\":\"queue_try_transfer\""), std::string::npos);
  EXPECT_NE(report->find("\"destination\":\"@destination\""),
            std::string::npos);
}

} // namespace
} // namespace acir
