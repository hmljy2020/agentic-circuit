#include "ProcessStatePlanInternal.h"

#include "acir/Dialect/ACIR/ACIROps.h"

#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/IR/Diagnostics.h"
#include "llvm/ADT/DenseMap.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/Support/ErrorHandling.h"

#include <array>
#include <functional>
#include <iomanip>
#include <limits>
#include <memory>
#include <sstream>

using namespace mlir;

namespace acir::detail {
namespace {

static bool isSuspensionOp(Operation *op) {
  return isa<ac::WaitUntilOp>(op) || isa<ac::WaitForOp>(op) ||
         isa<ac::AwaitEventOp>(op) || isa<ac::AwaitQueueOp>(op) ||
         isa<ac::YieldSimOp>(op);
}

static bool isYieldSim(Operation *op) { return isa<ac::YieldSimOp>(op); }

static ProcessWakeKind wakeKindForOp(Operation *op) {
  if (isa<ac::WaitUntilOp>(op))
    return ProcessWakeKind::Condition;
  if (isa<ac::WaitForOp>(op))
    return ProcessWakeKind::Resource;
  if (isa<ac::AwaitEventOp>(op))
    return ProcessWakeKind::EventQueue;
  if (isa<ac::YieldSimOp>(op))
    return ProcessWakeKind::NextDelta;
  if (auto await = dyn_cast<ac::AwaitQueueOp>(op))
    return await.getUntil() == "readable" ? ProcessWakeKind::QueueReadable
                                          : ProcessWakeKind::QueueWritable;
  llvm_unreachable("unknown suspension op");
}

static std::string wakeTypeKeyForOp(Operation *op) {
  if (isa<ac::WaitUntilOp>(op))
    return "@acir_wake_condition";
  if (isa<ac::WaitForOp>(op))
    return "@acir_wake_resource";
  if (isa<ac::AwaitEventOp>(op))
    return "@acir_wake_event_queue";
  if (isa<ac::YieldSimOp>(op))
    return "@acir_wake_next_delta";
  if (auto await = dyn_cast<ac::AwaitQueueOp>(op))
    return await.getUntil() == "readable" ? "@acir_wake_queue_readable"
                                          : "@acir_wake_queue_writable";
  llvm_unreachable("unknown suspension op");
}

static std::string pcName(uint32_t index) {
  if (index == 0)
    return "entry";
  std::ostringstream s;
  s << "pc" << std::setfill('0') << std::setw(8) << index;
  return s.str();
}

static std::string blockPath(const std::string &defKey,
                             const std::string &pcNameStr, uint32_t blockIdx) {
  std::ostringstream s;
  s << defKey << "/plan/pc/" << pcNameStr << "/b" << std::setfill('0')
    << std::setw(8) << blockIdx;
  return s.str();
}

} // namespace

ProcessActionPlan
PlanSetBuilder::makePlannedAction(const ExpandedAction &expanded, uint32_t id) {
  auto action = std::make_shared<ProcessActionPlan::Impl>();
  action->id = id;
  action->kind = expanded.kind;
  action->emission = ProcessEmissionClass::ForwardOnly;
  if (action->kind == ProcessActionKind::ForCondition ||
      action->kind == ProcessActionKind::ForIncrement)
    action->emission = ProcessEmissionClass::CopyScalar;
  action->occurrence = expanded.occurrence;
  action->sourceOperation = action->kind == ProcessActionKind::Constant
                                ? nullptr
                                : expanded.operation;
  action->iterationVector = expanded.iterationVector;
  action->operands = expanded.operands;
  action->results = expanded.results;
  action->cost = action->emission == ProcessEmissionClass::ForwardOnly ? 0 : 1;
  for (const ProcessPlannedValue &result : action->results)
    action->resultTypes.push_back(result.type());
  action->scalarOp = expanded.scalarOperation;
  if (action->kind == ProcessActionKind::Constant) {
    action->emission = ProcessEmissionClass::CopyScalar;
    action->cost = 1;
    auto scalar = std::make_shared<ProcessScalarOperationPlan::Impl>();
    scalar->name = "index.constant";
    scalar->properties = "{}";
    action->scalarOp = ProcessScalarOperationPlan(std::move(scalar));
  }
  if (action->kind == ProcessActionKind::Original && action->sourceOperation) {
    if (isa<ac::TrySendOp, ac::TryRecvOp, ac::TryTransferOp, ac::PeekOp,
            ac::SpaceOp, ac::ScheduleOp, ac::TryEventOp, ac::StateReadOp,
            ac::StateWriteOp, ac::AssertOp,
            ac::ArbitrateOp>(
            action->sourceOperation)) {
      action->emission = ProcessEmissionClass::Invoke;
      action->cost = 1;
    }
    if (isa<ac::RecordCreateOp, ac::RecordGetOp, ac::RecordWithOp,
            ac::PacketSerializeOp, ac::PacketDeserializeOp>(
            action->sourceOperation)) {
      action->emission = ProcessEmissionClass::Inline;
      action->cost = 1;
    }
    llvm::StringRef dialect =
        action->sourceOperation->getName().getDialectNamespace();
    if ((dialect == "arith" || dialect == "index" || dialect == "builtin") &&
        action->sourceOperation->getNumRegions() == 0) {
      action->emission = ProcessEmissionClass::CopyScalar;
      action->cost = 1;
      if (!action->scalarOp) {
        auto scalar = std::make_shared<ProcessScalarOperationPlan::Impl>();
        scalar->name = action->sourceOperation->getName().getStringRef().str();
        scalar->properties = "{}";
        action->scalarOp = ProcessScalarOperationPlan(std::move(scalar));
      }
    }
  }
  return ProcessActionPlan(action);
}

struct StructuredNode {
  enum class Kind { Action, Branch, Jump } kind = Kind::Action;
  Operation *operation = nullptr;
  const ExpandedAction *action = nullptr;
  std::optional<ProcessPlannedValue> condition;
  StructuredNode *next = nullptr;
  StructuredNode *thenNode = nullptr;
  StructuredNode *elseNode = nullptr;
};

static bool isNestedInProcess(Operation *operation, ac::ProcessOp process) {
  for (Operation *owner = operation; owner; owner = owner->getParentOp())
    if (owner == process.getOperation())
      return true;
  return false;
}

FailureOr<std::unique_ptr<PlanSetBuilder::ControlPlan>>
PlanSetBuilder::planStructuredIfContinuation(const ExpandedProcess &expanded,
                                             const ProcessStateLimits &limits) {
  auto plan = std::make_unique<PlanSetBuilder::ControlPlan>();
  ac::ProcessOp process = expanded.process;

  DenseMap<Operation *, SmallVector<const ExpandedAction *, 2>>
      actionsByOperation;
  DenseMap<Operation *, std::array<const ExpandedAction *, 3>> loopActions;
  DenseMap<Value, ProcessPlannedValue> values;
  for (const ExpandedAction &action : expanded.actions) {
    bool reachedThroughPureCall =
        action.occurrence &&
        action.occurrence->kind() == ProcessOccurrenceKind::Original &&
        !action.occurrence->original().callSites().empty();
    if (!action.operation ||
        (!isNestedInProcess(action.operation, process) &&
         !reachedThroughPureCall))
      return failure();
    if (action.kind == ProcessActionKind::ForInitialize ||
        action.kind == ProcessActionKind::ForCondition ||
        action.kind == ProcessActionKind::ForIncrement) {
      unsigned phase = action.kind == ProcessActionKind::ForInitialize
                           ? 0
                       : action.kind == ProcessActionKind::ForCondition ? 1
                                                                        : 2;
      auto [found, inserted] = loopActions.try_emplace(
          action.operation,
          std::array<const ExpandedAction *, 3>{nullptr, nullptr, nullptr});
      if (found->second[phase])
        return failure();
      found->second[phase] = &action;
    } else {
      actionsByOperation[action.operation].push_back(&action);
    }
    if (action.kind == ProcessActionKind::Original)
      for (auto [result, planned] :
           llvm::zip_equal(action.operation->getResults(), action.results))
        values.try_emplace(result, planned);
  }

  // Calls are expansion-time aliases rather than runtime actions.  Retain the
  // mapping from their SSA results (and callee block arguments) to the actual
  // planned producer so a call result can directly control structured flow.
  for (const ExpandedForwarding &forwarding : expanded.forwarding)
    if (forwarding.to.kind() == ProcessPlannedValueKind::Original)
      values.insert_or_assign(forwarding.to.original().value(),
                              forwarding.from);

  // Loop induction variables, region iter_args, and loop results are aliases
  // of the synthetic values produced by the compact loop actions rather than
  // results of an Original action.  Publish those aliases for structured
  // branch conditions.  This is required when a loop reduction directly
  // controls a following scf.if (for example an arbitration winner).
  for (const auto &[operation, phases] : loopActions) {
    auto loop = cast<scf::ForOp>(operation);
    const ExpandedAction *initialize = phases[0];
    if (!initialize || initialize->results.size() !=
                           1 + loop.getNumRegionIterArgs())
      return failure();
    values.try_emplace(loop.getInductionVar(), initialize->results.front());
    for (auto [index, pair] : llvm::enumerate(
             llvm::zip_equal(loop.getRegionIterArgs(), loop.getResults()))) {
      auto [argument, result] = pair;
      ProcessPlannedValue carried = initialize->results[index + 1];
      values.try_emplace(argument, carried);
      values.try_emplace(result, carried);
    }
  }

  std::vector<std::unique_ptr<StructuredNode>> nodes;
  DenseMap<Value, StructuredNode *> definitionsByValue;
  auto makeNode = [&]() {
    nodes.push_back(std::make_unique<StructuredNode>());
    return nodes.back().get();
  };
  bool supported = true;
  auto actionForContext = [&](Operation *operation,
                              ArrayRef<Operation *> callContext)
      -> const ExpandedAction * {
    auto found = actionsByOperation.find(operation);
    if (found == actionsByOperation.end())
      return nullptr;
    for (const ExpandedAction *action : found->second) {
      auto callSites = action->occurrence->original().callSites();
      if (callSites.size() == callContext.size() &&
          llvm::all_of(llvm::zip_equal(callSites, callContext),
                       [](auto pair) {
                         return std::get<0>(pair).operation() ==
                                std::get<1>(pair);
                       }))
        return action;
    }
    return nullptr;
  };
  std::function<StructuredNode *(Block &, StructuredNode *,
                                 SmallVector<Operation *>)>
      buildSequence =
      [&](Block &block, StructuredNode *continuation,
          SmallVector<Operation *> callContext) -> StructuredNode * {
    StructuredNode *head = continuation;
    for (Operation &operation : llvm::reverse(block)) {
      if (isa<scf::YieldOp, func::ReturnOp>(operation))
        continue;
      if (auto call = dyn_cast<func::CallOp>(operation)) {
        auto callee = SymbolTable::lookupNearestSymbolFrom<func::FuncOp>(
            call, call.getCalleeAttr());
        if (!callee || !callee.getBody().hasOneBlock()) {
          supported = false;
          return head;
        }
        SmallVector<Operation *> calleeContext = callContext;
        calleeContext.push_back(&operation);
        head = buildSequence(callee.getBody().front(), head,
                             std::move(calleeContext));
        continue;
      }
      if (auto ifOp = dyn_cast<scf::IfOp>(operation)) {
        if (ifOp.getNumResults() != 0) {
          supported = false;
          return head;
        }
        auto condition = values.find(ifOp.getCondition());
        if (condition == values.end()) {
          supported = false;
          return head;
        }
        StructuredNode *node = makeNode();
        node->kind = StructuredNode::Kind::Branch;
        node->operation = &operation;
        node->condition = condition->second;
        node->next = head;
        node->thenNode =
            buildSequence(ifOp.getThenRegion().front(), head, callContext);
        node->elseNode =
            ifOp.getElseRegion().empty()
                ? head
                : buildSequence(ifOp.getElseRegion().front(), head,
                                callContext);
        head = node;
        continue;
      }
      if (auto forOp = dyn_cast<scf::ForOp>(operation)) {
        auto phases = loopActions.find(&operation);
        if (phases == loopActions.end() || llvm::any_of(phases->second,
                         [](const ExpandedAction *action) { return !action; })) {
          supported = false;
          return head;
        }
        // Build init -> header -> body -> latch -> header, with exit flowing
        // to the already-built continuation.  All nodes remain in one PC.
        StructuredNode *header = makeNode();
        header->kind = StructuredNode::Kind::Branch;
        header->operation = &operation;
        header->action = phases->second[1];
        header->condition = phases->second[1]->results.front();
        header->elseNode = head;

        StructuredNode *latch = makeNode();
        latch->kind = StructuredNode::Kind::Jump;
        latch->operation = &operation;
        latch->action = phases->second[2];
        latch->next = header;
        header->thenNode = buildSequence(*forOp.getBody(), latch, callContext);

        StructuredNode *initialize = makeNode();
        initialize->kind = StructuredNode::Kind::Jump;
        initialize->operation = &operation;
        initialize->action = phases->second[0];
        initialize->next = header;
        head = initialize;
        continue;
      }
      if (operation.getNumRegions() != 0 || isa<scf::WhileOp>(operation)) {
        supported = false;
        return head;
      }
      const ExpandedAction *action = actionForContext(&operation, callContext);
      if (!action) {
        supported = false;
        return head;
      }
      StructuredNode *node = makeNode();
      node->kind = StructuredNode::Kind::Action;
      node->operation = &operation;
      node->action = action;
      node->next = head;
      for (Value result : operation.getResults())
        definitionsByValue.try_emplace(result, node);
      head = node;
    }
    return head;
  };

  StructuredNode *entryRoot =
      buildSequence(process.getBody().front(), nullptr, {});
  if (!supported || !entryRoot)
    return failure();

  DenseMap<StructuredNode *, StructuredNode *> retryRoots;
  for (const auto &ownedNode : nodes) {
    StructuredNode *node = ownedNode.get();
    auto await = dyn_cast_or_null<ac::AwaitQueueOp>(node->operation);
    auto awaitEvent = dyn_cast_or_null<ac::AwaitEventOp>(node->operation);
    auto ifOp = node->operation ? node->operation->getParentOfType<scf::IfOp>()
                                : scf::IfOp();
    if ((!await && !awaitEvent) || !ifOp)
      continue;
    auto definition = definitionsByValue.find(ifOp.getCondition());
    if (definition == definitionsByValue.end())
      continue;
    Operation *operation = definition->second->operation;
    FlatSymbolRefAttr queue;
    if (auto send = dyn_cast<ac::TrySendOp>(operation))
      queue = send.getQueueAttr();
    else if (auto recv = dyn_cast<ac::TryRecvOp>(operation))
      queue = recv.getQueueAttr();
    else if (auto peek = dyn_cast<ac::PeekOp>(operation))
      queue = peek.getQueueAttr();
    else if (auto recv = dyn_cast<ac::TryEventOp>(operation))
      queue = recv.getEventQueueAttr();
    FlatSymbolRefAttr awaited =
        await ? await.getQueueAttr() : awaitEvent.getEventQueueAttr();
    if (queue && queue == awaited)
      retryRoots.try_emplace(node, definition->second);
  }

  uint32_t nextBlockId = 0;
  uint32_t nextWakeId = 0;
  uint32_t nextTransitionId = 0;
  DenseMap<StructuredNode *, ProcessPcId> pcsByRoot;

  std::function<FailureOr<ProcessPcId>(StructuredNode *)> createPc;
  createPc = [&](StructuredNode *root) -> FailureOr<ProcessPcId> {
    if (auto found = pcsByRoot.find(root); found != pcsByRoot.end())
      return found->second;
    if (plan->pcs.size() >= limits.maxProgramCounters)
      return failure();
    ProcessPcId pcId(static_cast<uint32_t>(plan->pcs.size()));
    pcsByRoot.try_emplace(root, pcId);
    auto pc = std::make_shared<ProcessPcPlan::Impl>();
    pc->id = pcId;
    pc->name = pcName(pcId.value());
    plan->pcs.push_back(pc);

    DenseMap<StructuredNode *, ProcessBlockId> blocksByNode;
    std::function<FailureOr<ProcessBlockId>(StructuredNode *)> buildBlock;
    buildBlock = [&](StructuredNode *start) -> FailureOr<ProcessBlockId> {
      if (auto found = blocksByNode.find(start); found != blocksByNode.end())
        return found->second;
      ProcessBlockId blockId(nextBlockId++);
      auto block = std::make_shared<ProcessBlockPlan::Impl>();
      block->id = blockId;
      block->pc = pcId;
      block->originBlock =
          start ? start->operation->getBlock() : &process.getBody().front();
      block->originRegion = block->originBlock->getParent();
      block->path =
          blockPath(expanded.definitionKey, pc->name, blockId.value());
      blocksByNode.try_emplace(start, blockId);
      pc->blocks.push_back(blockId);
      if (pc->entryPath.empty())
        pc->entryPath = block->path;
      plan->blocks.push_back(block);

      StructuredNode *cursor = start;
      while (cursor && cursor->kind == StructuredNode::Kind::Action &&
             !isSuspensionOp(cursor->operation)) {
        block->actions.push_back(makePlannedAction(
            *cursor->action, static_cast<uint32_t>(block->actions.size())));
        cursor = cursor->next;
      }

      if (!cursor) {
        auto edge = std::make_shared<ProcessControlEdgePlan::Impl>();
        edge->kind = ProcessControlEdgeKind::Terminate;
        edge->status = ProcessTerminateStatus::Success;
        block->edge = ProcessControlEdgePlan(edge);
        return blockId;
      }

      if (cursor->kind == StructuredNode::Kind::Branch) {
        if (cursor->action)
          block->actions.push_back(makePlannedAction(
              *cursor->action, static_cast<uint32_t>(block->actions.size())));
        auto thenBlock = buildBlock(cursor->thenNode);
        auto elseBlock = buildBlock(cursor->elseNode);
        if (failed(thenBlock) || failed(elseBlock))
          return failure();
        auto edge = std::make_shared<ProcessControlEdgePlan::Impl>();
        edge->kind = ProcessControlEdgeKind::Branch;
        edge->condition = cursor->condition;
        edge->trueBlock = *thenBlock;
        edge->falseBlock = *elseBlock;
        block->edge = ProcessControlEdgePlan(edge);
        return blockId;
      }

      if (cursor->kind == StructuredNode::Kind::Jump) {
        block->actions.push_back(makePlannedAction(
            *cursor->action, static_cast<uint32_t>(block->actions.size())));
        auto target = buildBlock(cursor->next);
        if (failed(target))
          return failure();
        auto edge = std::make_shared<ProcessControlEdgePlan::Impl>();
        edge->kind = ProcessControlEdgeKind::LocalContinue;
        edge->targetBlock = *target;
        block->edge = ProcessControlEdgePlan(edge);
        return blockId;
      }

      block->actions.push_back(makePlannedAction(
          *cursor->action, static_cast<uint32_t>(block->actions.size())));
      const ProcessWakeId wakeId(nextWakeId++);
      const ProcessTransitionId transitionId(nextTransitionId++);
      auto wake = std::make_shared<ProcessWakePlan::Impl>();
      wake->id = wakeId;
      auto transition = std::make_shared<ProcessTransitionPlan::Impl>();
      transition->id = transitionId;
      transition->sourcePc = pcId;
      transition->wake = wakeId;
      plan->wakes.push_back(wake);
      plan->transitions.push_back(transition);

      ProcessPcId targetPc(0);
      if (!isYieldSim(cursor->operation)) {
        StructuredNode *resume = cursor->next;
        if (auto retry = retryRoots.find(cursor); retry != retryRoots.end())
          resume = retry->second;
        auto created = createPc(resume);
        if (failed(created))
          return failure();
        targetPc = *created;
      }

      wake->kind = wakeKindForOp(cursor->operation);
      wake->typeKey = wakeTypeKeyForOp(cursor->operation);
      wake->operation = cursor->operation;
      wake->operationPath = cursor->action->operationPath;
      wake->target = "";
      wake->occurrence = cursor->action->occurrence;
      wake->iterationVector = cursor->action->iterationVector;
      for (const ProcessPlannedValue &operand : cursor->action->operands) {
        auto source = std::make_shared<ProcessSubscriptionSourcePlan::Impl>();
        if (operand.kind() == ProcessPlannedValueKind::Original) {
          source->kind = ProcessSubscriptionSourceKind::Value;
          source->value = operand.original().value();
          source->owner =
              operand.original().occurrence().original().operation();
          source->path = operand.original().path().str();
        } else if (operand.kind() == ProcessPlannedValueKind::Capture) {
          source->kind = ProcessSubscriptionSourceKind::Capture;
          source->capture = operand.capture().capture();
        } else {
          source->kind = ProcessSubscriptionSourceKind::Value;
        }
        wake->sources.push_back(ProcessSubscriptionSourcePlan(source));
      }

      transition->targetPc = targetPc;

      auto edge = std::make_shared<ProcessControlEdgePlan::Impl>();
      edge->kind = ProcessControlEdgeKind::Suspend;
      edge->transition = transitionId;
      block->edge = ProcessControlEdgePlan(edge);
      return blockId;
    };

    if (failed(buildBlock(root)))
      return failure();
    return pcId;
  };

  auto entry = createPc(entryRoot);
  if (failed(entry) || entry->value() != 0)
    return failure();
  if (!loopActions.empty()) {
    plan->hasBoundedLocalLoops = true;
    // Start with every action and CFG edge once, then add the repeated loop
    // body work.  The previous loop-only estimate undercounted large straight-
    // line prefixes/suffixes (for example M1's scheduling decision logic) and
    // could publish a fairness cap below the actual local execution path.
    uint64_t boundedWork = expanded.actions.size() + plan->blocks.size();
    process.walk([&](scf::ForOp loop) {
      if (auto trip = ac::analyzeStaticFor(loop); succeeded(trip)) {
        uint64_t bodyOps =
            std::max<uint64_t>(1, std::distance(loop.getBody()->begin(),
                                                loop.getBody()->end()) - 1);
        uint64_t loopWork = 3 + trip->tripCount * bodyOps;
        if (boundedWork <=
            std::numeric_limits<uint64_t>::max() - loopWork)
          boundedWork += loopWork;
        else
          boundedWork = std::numeric_limits<uint64_t>::max();
      }
    });
    plan->boundedLocalWork = boundedWork;
  }
  return plan;
}

FailureOr<std::unique_ptr<PlanSetBuilder::ControlPlan>>
PlanSetBuilder::planProcessContinuation(const ExpandedProcess &expanded,
                                        const ProcessStateLimits &limits) {
  bool hasStructuredControl = false;
  bool structuredSubset = true;
  ac::ProcessOp sourceProcess = expanded.process;
  sourceProcess.walk([&](Operation *operation) {
    hasStructuredControl |= isa<scf::IfOp, scf::ForOp>(operation);
    if (isa<scf::WhileOp>(operation))
      structuredSubset = false;
    if (auto loop = dyn_cast<scf::ForOp>(operation))
      structuredSubset &= succeeded(ac::analyzeStaticFor(loop));
  });
  if (hasStructuredControl && structuredSubset)
    return planStructuredIfContinuation(expanded, limits);

  auto plan = std::make_unique<ControlPlan>();

  if (expanded.actions.empty())
    return mlir::failure();

  uint32_t nextPcId = 0;
  uint32_t nextBlockId = 0;
  uint32_t nextWakeId = 0;
  uint32_t nextTransitionId = 0;

  // Entry PC
  auto entryPc = std::make_shared<ProcessPcPlan::Impl>();
  entryPc->id = ProcessPcId(nextPcId++);
  entryPc->name = pcName(0);
  plan->pcs.push_back(entryPc);

  struct Susp {
    size_t idx;
    ProcessWakeKind kind;
    std::string typeKey;
    Operation *op;
  };
  SmallVector<Susp> suspensions;
  for (auto [i, a] : llvm::enumerate(expanded.actions)) {
    if (isSuspensionOp(a.operation))
      suspensions.push_back({i, wakeKindForOp(a.operation),
                             wakeTypeKeyForOp(a.operation), a.operation});
  }

  // Resume PCs
  uint32_t resumeIdx = 1;
  SmallVector<uint32_t> pcMap(expanded.actions.size(), 0);
  for (const auto &s : suspensions) {
    if (!isYieldSim(s.op)) {
      auto rpc = std::make_shared<ProcessPcPlan::Impl>();
      rpc->id = ProcessPcId(nextPcId);
      rpc->name = pcName(resumeIdx);
      plan->pcs.push_back(rpc);
      pcMap[s.idx] = nextPcId;
      ++nextPcId;
      ++resumeIdx;
    } else {
      pcMap[s.idx] = 0; // yield_sim resumes at entry
    }
  }

  // Segment starts
  SmallVector<size_t> starts;
  starts.push_back(0);
  for (const auto &s : suspensions)
    starts.push_back(s.idx + 1);

  for (size_t seg = 0; seg < suspensions.size(); ++seg) {
    size_t start = starts[seg];
    size_t end = suspensions[seg].idx;
    uint32_t pcId = (seg == 0) ? 0 : pcMap[suspensions[seg - 1].idx];
    const auto &susp = suspensions[seg];

    auto block = std::make_shared<ProcessBlockPlan::Impl>();
    block->id = ProcessBlockId(nextBlockId);
    block->pc = ProcessPcId(pcId);
    block->originBlock = expanded.actions[start].operation->getBlock();
    block->originRegion = block->originBlock->getParent();
    block->path =
        blockPath(expanded.definitionKey, plan->pcs[pcId]->name, nextBlockId);
    plan->pcs[pcId]->blocks.push_back(ProcessBlockId(nextBlockId));
    if (plan->pcs[pcId]->entryPath.empty())
      plan->pcs[pcId]->entryPath = block->path;

    // Actions in segment
    for (size_t i = start; i <= end; ++i) {
      auto act = std::make_shared<ProcessActionPlan::Impl>();
      act->id = static_cast<uint32_t>(i - start);
      act->kind = expanded.actions[i].kind;
      act->emission = ProcessEmissionClass::ForwardOnly;
      if (act->kind == ProcessActionKind::ForCondition ||
          act->kind == ProcessActionKind::ForIncrement)
        act->emission = ProcessEmissionClass::CopyScalar;
      act->occurrence = expanded.actions[i].occurrence;
      act->sourceOperation = act->kind == ProcessActionKind::Constant
                                 ? nullptr
                                 : expanded.actions[i].operation;
      act->iterationVector = expanded.actions[i].iterationVector;
      act->operands = expanded.actions[i].operands;
      act->results = expanded.actions[i].results;
      act->cost = act->emission == ProcessEmissionClass::ForwardOnly ? 0 : 1;
      for (const ProcessPlannedValue &result : act->results)
        act->resultTypes.push_back(result.type());
      act->scalarOp = expanded.actions[i].scalarOperation;
      if (act->kind == ProcessActionKind::Constant) {
        act->emission = ProcessEmissionClass::CopyScalar;
        act->cost = 1;
        auto scalar = std::make_shared<ProcessScalarOperationPlan::Impl>();
        scalar->name = "index.constant";
        scalar->properties = "{}";
        act->scalarOp = ProcessScalarOperationPlan(std::move(scalar));
      }
      if (act->kind == ProcessActionKind::Original && act->sourceOperation) {
      if (isa<ac::TrySendOp, ac::TryRecvOp, ac::TryTransferOp, ac::PeekOp,
              ac::SpaceOp, ac::ScheduleOp, ac::TryEventOp, ac::StateReadOp,
              ac::StateWriteOp, ac::AssertOp,
              ac::ArbitrateOp>(
                act->sourceOperation)) {
          act->emission = ProcessEmissionClass::Invoke;
          act->cost = 1;
        }
        if (isa<ac::RecordCreateOp, ac::RecordGetOp, ac::RecordWithOp,
                ac::PacketSerializeOp, ac::PacketDeserializeOp>(
                act->sourceOperation)) {
          act->emission = ProcessEmissionClass::Inline;
          act->cost = 1;
        }
        llvm::StringRef dialect =
            act->sourceOperation->getName().getDialectNamespace();
        if ((dialect == "arith" || dialect == "index" ||
             dialect == "builtin") &&
            act->sourceOperation->getNumRegions() == 0) {
          act->emission = ProcessEmissionClass::CopyScalar;
          act->cost = 1;
          if (!act->scalarOp) {
            auto scalar = std::make_shared<ProcessScalarOperationPlan::Impl>();
            scalar->name = act->sourceOperation->getName().getStringRef().str();
            scalar->properties = "{}";
            act->scalarOp = ProcessScalarOperationPlan(std::move(scalar));
          }
        }
      }
      block->actions.push_back(ProcessActionPlan(act));
    }

    // Suspension edge
    auto edge = std::make_shared<ProcessControlEdgePlan::Impl>();
    edge->kind = ProcessControlEdgeKind::Suspend;

    // Wake
    auto wake = std::make_shared<ProcessWakePlan::Impl>();
    wake->id = ProcessWakeId(nextWakeId);
    wake->kind = susp.kind;
    wake->typeKey = susp.typeKey;
    wake->operation = susp.op;
    wake->operationPath = expanded.actions[susp.idx].operationPath;
    wake->target = "";
    wake->occurrence = expanded.actions[susp.idx].occurrence;
    wake->iterationVector = expanded.actions[susp.idx].iterationVector;

    // Subscription sources
    for (const auto &opd : expanded.actions[susp.idx].operands) {
      auto src = std::make_shared<ProcessSubscriptionSourcePlan::Impl>();
      if (opd.kind() == ProcessPlannedValueKind::Original) {
        src->kind = ProcessSubscriptionSourceKind::Value;
        src->value = opd.original().value();
        src->owner = opd.original().occurrence().original().operation();
        src->path = opd.original().path().str();
      } else if (opd.kind() == ProcessPlannedValueKind::Capture) {
        src->kind = ProcessSubscriptionSourceKind::Capture;
        src->capture = opd.capture().capture();
      } else {
        src->kind = ProcessSubscriptionSourceKind::Value;
      }
      wake->sources.push_back(ProcessSubscriptionSourcePlan(src));
    }

    // Transition
    auto tr = std::make_shared<ProcessTransitionPlan::Impl>();
    tr->id = ProcessTransitionId(nextTransitionId);
    tr->sourcePc = ProcessPcId(pcId);
    tr->targetPc = ProcessPcId(pcMap[susp.idx]);
    tr->wake = ProcessWakeId(nextWakeId);

    edge->transition = ProcessTransitionId(nextTransitionId);
    block->edge = ProcessControlEdgePlan(edge);

    plan->blocks.push_back(block);
    plan->wakes.push_back(wake);
    plan->transitions.push_back(tr);

    ++nextWakeId;
    ++nextTransitionId;
    ++nextBlockId;
  }

  // A suspension nested directly in an scf.if does not dominate the
  // continuation after the if.  Materialize the branch in the current PC and
  // clone the post-if continuation for the non-suspending arm.  The original
  // continuation remains the resume PC for the suspending arm.
  //
  // Expansion deliberately keeps occurrence-qualified leaf actions, so this
  // repair operates on the immutable action records and never rewrites the
  // frozen source IR.
  ac::ProcessOp process = expanded.process;
  for (const Susp &susp : suspensions) {
    auto ifOp = susp.op->getParentOfType<scf::IfOp>();
    if (!ifOp || ifOp->getParentOp() != process.getOperation())
      continue;

    auto belongsTo = [&](Operation *operation, Region &region) {
      if (!operation)
        return false;
      Operation *nested = operation;
      while (nested && nested->getParentOp() != ifOp.getOperation())
        nested = nested->getParentOp();
      return nested && nested->getParentRegion() == &region;
    };
    bool suspendedInThen = belongsTo(susp.op, ifOp.getThenRegion());
    bool suspendedInElse = !ifOp.getElseRegion().empty() &&
                           belongsTo(susp.op, ifOp.getElseRegion());
    if (!suspendedInThen && !suspendedInElse)
      continue;
    Region *otherRegion =
        suspendedInThen ? &ifOp.getElseRegion() : &ifOp.getThenRegion();
    if (llvm::any_of(suspensions, [&](const Susp &candidate) {
          return candidate.op != susp.op && !otherRegion->empty() &&
                 belongsTo(candidate.op, *otherRegion);
        }))
      continue;

    auto branchBlockIt = llvm::find_if(plan->blocks, [&](const auto &block) {
      return llvm::any_of(block->actions, [&](const ProcessActionPlan &action) {
        return action.sourceOperation() == susp.op;
      });
    });
    if (branchBlockIt == plan->blocks.end() ||
        !(*branchBlockIt)->edge.has_value() ||
        (*branchBlockIt)->edge->kind() != ProcessControlEdgeKind::Suspend)
      continue;

    auto appendRenumbered = [](std::vector<ProcessActionPlan> &target,
                               const ProcessActionPlan &source) {
      auto action = std::make_shared<ProcessActionPlan::Impl>(*source.impl_);
      action->id = static_cast<uint32_t>(target.size());
      target.push_back(ProcessActionPlan(action));
    };
    std::vector<ProcessActionPlan> prefix;
    std::vector<ProcessActionPlan> thenActions;
    std::vector<ProcessActionPlan> elseActions;
    for (const ProcessActionPlan &action : (*branchBlockIt)->actions) {
      if (belongsTo(action.sourceOperation(), ifOp.getThenRegion()))
        appendRenumbered(thenActions, action);
      else if (!ifOp.getElseRegion().empty() &&
               belongsTo(action.sourceOperation(), ifOp.getElseRegion()))
        appendRenumbered(elseActions, action);
      else
        appendRenumbered(prefix, action);
    }
    std::vector<ProcessActionPlan> &suspendingActions =
        suspendedInThen ? thenActions : elseActions;
    std::vector<ProcessActionPlan> &continuingActions =
        suspendedInThen ? elseActions : thenActions;
    if (llvm::none_of(suspendingActions, [&](const ProcessActionPlan &action) {
          return action.sourceOperation() == susp.op;
        }))
      continue;

    ProcessTransitionId originalTransition =
        (*branchBlockIt)->edge->transition();
    if (originalTransition.value() >= plan->transitions.size())
      return failure();
    ProcessPcId resumePc =
        plan->transitions[originalTransition.value()]->targetPc.value();
    auto resumeBlockIt = llvm::find_if(plan->blocks, [&](const auto &block) {
      return block->pc == resumePc &&
             block->path == plan->pcs[resumePc.value()]->entryPath;
    });
    if (resumeBlockIt == plan->blocks.end() ||
        !(*resumeBlockIt)->edge.has_value())
      return failure();

    ProcessPcId branchPc = (*branchBlockIt)->pc.value();
    auto suspendingBlock = std::make_shared<ProcessBlockPlan::Impl>();
    suspendingBlock->id = ProcessBlockId(nextBlockId++);
    suspendingBlock->pc = branchPc;
    suspendingBlock->originBlock = susp.op->getBlock();
    suspendingBlock->originRegion = susp.op->getParentRegion();
    suspendingBlock->path =
        blockPath(expanded.definitionKey, plan->pcs[branchPc.value()]->name,
                  suspendingBlock->id->value());
    suspendingBlock->actions = std::move(suspendingActions);
    suspendingBlock->edge = (*branchBlockIt)->edge;

    auto continuingBlock = std::make_shared<ProcessBlockPlan::Impl>();
    continuingBlock->id = ProcessBlockId(nextBlockId++);
    continuingBlock->pc = branchPc;
    continuingBlock->originBlock =
        otherRegion->empty() ? ifOp->getBlock() : &otherRegion->front();
    continuingBlock->originRegion =
        otherRegion->empty() ? ifOp->getParentRegion() : otherRegion;
    continuingBlock->path =
        blockPath(expanded.definitionKey, plan->pcs[branchPc.value()]->name,
                  continuingBlock->id->value());
    continuingBlock->actions = std::move(continuingActions);
    for (const ProcessActionPlan &action : (*resumeBlockIt)->actions)
      appendRenumbered(continuingBlock->actions, action);

    const ProcessControlEdgePlan &resumeEdge = *(*resumeBlockIt)->edge;
    if (resumeEdge.kind() == ProcessControlEdgeKind::Suspend) {
      ProcessTransitionId resumeTransition = resumeEdge.transition();
      if (resumeTransition.value() >= plan->transitions.size())
        return failure();
      auto transition = std::make_shared<ProcessTransitionPlan::Impl>(
          *plan->transitions[resumeTransition.value()]);
      transition->id = ProcessTransitionId(nextTransitionId++);
      transition->sourcePc = branchPc;
      ProcessWakeId resumeWake = transition->wake.value();
      if (resumeWake.value() >= plan->wakes.size())
        return failure();
      auto wake = std::make_shared<ProcessWakePlan::Impl>(
          *plan->wakes[resumeWake.value()]);
      wake->id = ProcessWakeId(nextWakeId++);
      transition->wake = wake->id;
      auto edge = std::make_shared<ProcessControlEdgePlan::Impl>();
      edge->kind = ProcessControlEdgeKind::Suspend;
      edge->transition = transition->id;
      continuingBlock->edge = ProcessControlEdgePlan(edge);
      plan->wakes.push_back(std::move(wake));
      plan->transitions.push_back(std::move(transition));
    } else {
      continuingBlock->edge = resumeEdge;
    }

    std::optional<ProcessPlannedValue> condition;
    for (const ExpandedAction &action : expanded.actions) {
      for (const ProcessPlannedValue &result : action.results) {
        if (result.kind() == ProcessPlannedValueKind::Original &&
            result.original().value() == ifOp.getCondition()) {
          condition = result;
          break;
        }
      }
      if (condition)
        break;
    }
    if (!condition)
      return failure();

    auto edge = std::make_shared<ProcessControlEdgePlan::Impl>();
    edge->kind = ProcessControlEdgeKind::Branch;
    edge->condition = *condition;
    edge->trueBlock =
        suspendedInThen ? suspendingBlock->id : continuingBlock->id;
    edge->falseBlock =
        suspendedInThen ? continuingBlock->id : suspendingBlock->id;
    (*branchBlockIt)->actions = std::move(prefix);
    (*branchBlockIt)->edge = ProcessControlEdgePlan(edge);

    plan->pcs[branchPc.value()]->blocks.push_back(*suspendingBlock->id);
    plan->pcs[branchPc.value()]->blocks.push_back(*continuingBlock->id);
    plan->blocks.push_back(std::move(suspendingBlock));
    plan->blocks.push_back(std::move(continuingBlock));
  }

  return plan;
}

} // namespace acir::detail
