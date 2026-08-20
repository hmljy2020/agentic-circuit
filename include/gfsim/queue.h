#ifndef GFSIM_QUEUE_H
#define GFSIM_QUEUE_H

#include "gfsim/core.h"
#include "gfsim/object.h"
#include "gfsim/packet.h"

#include <algorithm>
#include <cstddef>
#include <limits>
#include <optional>
#include <queue>
#include <set>
#include <tuple>
#include <utility>
#include <vector>

namespace gfsim {

// ── SimQueue<T> ───────────────────────────────────────────────────────

/// FIFO data queue with entry capacity, optional byte capacity,
/// ordered read/write proposals, deterministic arbitration,
/// and occupancy/watermark statistics.
template <typename T> class SimQueue : public SimObject {
public:
  SimQueue(std::string name, ObjectId id, SimObject *parent,
           size_t entryCapacity, size_t byteCapacity = SIZE_MAX,
           ObservationSink *observations = nullptr)
      : SimObject(ObjectKind::Queue, std::move(name), id, parent, observations),
        entryCapacity_(entryCapacity), byteCapacity_(byteCapacity) {}

  // ── Capacity ────────────────────────────────────────────────────────

  size_t entryCapacity() const { return entryCapacity_; }
  size_t byteCapacity() const { return byteCapacity_; }

  size_t committedSize() const { return committed_.size(); }
  size_t committedBytes() const {
    if constexpr (PacketTraits<T>::serializedSize == 0)
      return 0;
    return committed_.size() * PacketTraits<T>::serializedSize;
  }
  bool isFull() const {
    return committedSize() >= entryCapacity_ ||
           exceedsByteCapacity(committedSize() + 1);
  }
  bool isEmpty() const { return committed_.empty(); }

  // ── Proposal interface ──────────────────────────────────────────────

  /// Propose to enqueue an element. Returns false if capacity exceeded.
  bool proposePush(T element) {
    size_t occupied = pushProposals_.size() + committedSize();
    if (occupied >= entryCapacity_ || exceedsByteCapacity(occupied + 1))
      return false;
    if (system_ && !system_->registerCommitParticipant(id()))
      return false;
    pushProposals_.push_back(std::move(element));
    return true;
  }

  /// Propose to dequeue the next element in FIFO order.
  std::optional<T> proposePop() {
    if (popProposalCount_ >= committed_.size())
      return std::nullopt;
    if (system_ && !system_->registerCommitParticipant(id()))
      return std::nullopt;
    size_t index = popProposalCount_;
    ++popProposalCount_;
    return std::optional<T>(committed_[index]);
  }

  /// Atomically propose one snapshot-visible FIFO transfer into another
  /// queue.  No proposal is published unless both endpoints can participate.
  /// The compiler verifies that the caller is the source's sole pop proposer
  /// and the destination's sole push proposer.
  bool proposeTransferTo(SimQueue<T> &destination) {
    if (popProposalCount_ >= committed_.size())
      return false;
    const size_t destinationOccupied =
        destination.pushProposals_.size() + destination.committedSize();
    if (destinationOccupied >= destination.entryCapacity_ ||
        destination.exceedsByteCapacity(destinationOccupied + 1))
      return false;
    if (system_ && !system_->registerCommitParticipant(id()))
      return false;
    if (destination.system_ &&
        !destination.system_->registerCommitParticipant(destination.id()))
      return false;

    destination.pushProposals_.push_back(committed_[popProposalCount_]);
    ++popProposalCount_;
    return true;
  }

  /// Typed process helper: failed receives return the normative zero value.
  std::pair<T, bool> tryRecv() {
    std::optional<T> value = proposePop();
    return value ? std::pair<T, bool>{std::move(*value), true}
                 : std::pair<T, bool>{T{}, false};
  }

  /// Peek at the front without proposing a pop.
  const T *peek() const {
    return committed_.empty() ? nullptr : &committed_.front();
  }

  /// Typed process helper: observe the committed head without proposing a pop.
  std::pair<T, bool> tryPeek() const {
    const T *value = peek();
    return value ? std::pair<T, bool>{*value, true}
                 : std::pair<T, bool>{T{}, false};
  }

  /// Free entry slots the queue can accept right now: how many proposePush
  /// calls would succeed this epoch. Pending pushes count as occupied, so the
  /// value is max(0, entryCapacity - committed - pending pushes).
  std::int32_t space() const {
    size_t occupied = pushProposals_.size() + committedSize();
    if (occupied >= entryCapacity_)
      return 0;
    return static_cast<std::int32_t>(entryCapacity_ - occupied);
  }

  // ── Arbitration ─────────────────────────────────────────────────────

  void doArbitrate(Epoch) override {
    // Deterministic local arbitration: FIFO order.
    // Push proposals are appended in order.
    // Pop proposals are served from the front.
    // In v0.2, arbitration is simple FIFO.
    for (size_t index = 0; index < pushProposals_.size(); ++index)
      emitObservation({.category = "transaction",
                       .name = "accepted",
                       .phase = TraceEventPhase::Instant});
    for (size_t index = 0; index < popProposalCount_; ++index)
      emitObservation({.category = "transaction",
                       .name = "completed",
                       .phase = TraceEventPhase::Instant});
    if (!pushProposals_.empty() || popProposalCount_ != 0) {
      const uint64_t occupancy =
          committed_.size() + pushProposals_.size() - popProposalCount_;
      emitObservation({.category = "queue",
                       .name = "occupancy",
                       .phase = TraceEventPhase::Counter,
                       .arguments = {{"occupancy", occupancy}}});
    }
  }

  // ── Xfer ────────────────────────────────────────────────────────────

  void doXfer(Epoch epoch) override {
    bool changed = hasPendingCommit();
    // Commit push proposals
    for (auto &elem : pushProposals_) {
      committed_.push_back(std::move(elem));
      ++totalPushes_;
    }
    pushProposals_.clear();

    // Commit pop proposals
    for (size_t i = 0; i < popProposalCount_ && !committed_.empty(); ++i) {
      committed_.erase(committed_.begin());
      ++totalPops_;
    }
    popProposalCount_ = 0;

    // Update statistics
    if (committedSize() > highWatermark_)
      highWatermark_ = committedSize();
    if (changed)
      lastUpdate_ = epoch;
  }

  bool hasPendingCommit() const override {
    return !pushProposals_.empty() || popProposalCount_ != 0;
  }

  RuntimeObjectState runtimeState(Epoch epoch) const override {
    RuntimeObjectState state = SimObject::runtimeState(epoch);
    state.queueOccupancy = committedSize();
    state.pendingOffers = pushProposals_.size();
    state.quiescent = committed_.empty() && !hasPendingCommit();
    if (!state.quiescent)
      state.reason = hasPendingCommit() ? "pending_commit" : "queue_not_empty";
    return state;
  }

  void collectStatistics(std::vector<StatSnapshot> &out) const override {
    auto append = [&](std::string suffix, uint64_t value, StatisticKind kind) {
      out.push_back({.name = std::move(suffix),
                     .objectPath = std::string(path()),
                     .kind = kind,
                     .value = value,
                     .lastUpdate = lastUpdate_});
    };
    append("queue_occupancy", committedSize(), StatisticKind::Gauge);
    append("queue_occupancy_peak", highWatermark_, StatisticKind::Gauge);
    append("accepted_transactions", totalPushes_, StatisticKind::Counter);
    append("completed_transactions", totalPops_, StatisticKind::Counter);
  }

  // ── Statistics ──────────────────────────────────────────────────────

  size_t highWatermark() const { return highWatermark_; }
  uint64_t totalPushes() const { return totalPushes_; }
  uint64_t totalPops() const { return totalPops_; }

  void bindSystem(SimSystem *system) override { system_ = system; }

  void reset() override {
    committed_.clear();
    pushProposals_.clear();
    popProposalCount_ = 0;
    highWatermark_ = 0;
    totalPushes_ = 0;
    totalPops_ = 0;
    lastUpdate_ = {};
    clearRuntimeFailureCode();
  }

private:
  bool exceedsByteCapacity(size_t elementCount) const {
    if constexpr (PacketTraits<T>::serializedSize == 0)
      return false;
    return elementCount > byteCapacity_ / PacketTraits<T>::serializedSize;
  }

  size_t entryCapacity_;
  size_t byteCapacity_;
  std::vector<T> committed_;
  std::vector<T> pushProposals_;
  size_t popProposalCount_ = 0;
  size_t highWatermark_ = 0;
  uint64_t totalPushes_ = 0;
  uint64_t totalPops_ = 0;
  Epoch lastUpdate_;
  SimSystem *system_ = nullptr;
};

/// Standard-library finite FIFO component. The distinct name is the public
/// component contract; SimQueue remains the underlying runtime primitive.
template <typename T> class Queue final : public SimQueue<T> {
public:
  static constexpr std::string_view contractName = "ac.std.Queue";
  static constexpr ObjectKind componentKind = ObjectKind::Queue;
  using SimQueue<T>::SimQueue;

  Queue<T> &flowSource() { return *this; }
  const Queue<T> &flowSource() const { return *this; }
  Queue<T> &flowSink() { return *this; }
  const Queue<T> &flowSink() const { return *this; }
};

/// Compiler-native, exactly-once link between two typed queues.  Work observes
/// only committed endpoint state and proposes at most one transfer per epoch;
/// the endpoint queues publish the paired pop/push at the Xfer barrier.
template <typename T> class QueueLink final : public SimObject {
public:
  QueueLink(std::string name, ObjectId id, SimObject *parent, Queue<T> &source,
            Queue<T> &destination)
      : SimObject(ObjectKind::Link, std::move(name), id, parent),
        source_(source), destination_(destination) {}

  void doWork(Epoch epoch) override {
    if (lastWorkEpoch_ && *lastWorkEpoch_ == epoch)
      return;
    lastWorkEpoch_ = epoch;
    if (source_.isEmpty()) {
      ++stalledEmpty_;
      return;
    }
    if (destination_.isFull()) {
      ++stalledFull_;
      return;
    }
    if (system_ && !system_->registerCommitParticipant(id())) {
      setRuntimeFailureCode("queue_link_commit_registration_failed");
      return;
    }
    if (!source_.proposeTransferTo(destination_)) {
      setRuntimeFailureCode("queue_link_atomic_proposal_failed");
      return;
    }
    pendingTransfer_ = true;
  }

  void doXfer(Epoch epoch) override {
    if (!pendingTransfer_)
      return;
    pendingTransfer_ = false;
    ++transferred_;
    lastUpdate_ = epoch;
  }

  bool hasPendingCommit() const override { return pendingTransfer_; }
  bool isRunnable(Epoch) const override {
    return !source_.isEmpty() && !destination_.isFull();
  }

  void bindSystem(SimSystem *system) override { system_ = system; }

  uint64_t transferred() const { return transferred_; }
  uint64_t stalledEmpty() const { return stalledEmpty_; }
  uint64_t stalledFull() const { return stalledFull_; }

  void collectStatistics(std::vector<StatSnapshot> &out) const override {
    auto append = [&](std::string name, uint64_t value) {
      out.push_back({.name = std::move(name),
                     .objectPath = std::string(path()),
                     .kind = StatisticKind::Counter,
                     .value = value,
                     .lastUpdate = lastUpdate_});
    };
    append("transferred", transferred_);
    append("stalled_empty", stalledEmpty_);
    append("stalled_full", stalledFull_);
  }

  void reset() override {
    pendingTransfer_ = false;
    lastWorkEpoch_.reset();
    transferred_ = 0;
    stalledEmpty_ = 0;
    stalledFull_ = 0;
    lastUpdate_ = {};
    clearRuntimeFailureCode();
  }

private:
  Queue<T> &source_;
  Queue<T> &destination_;
  SimSystem *system_ = nullptr;
  std::optional<Epoch> lastWorkEpoch_;
  bool pendingTransfer_ = false;
  uint64_t transferred_ = 0;
  uint64_t stalledEmpty_ = 0;
  uint64_t stalledFull_ = 0;
  Epoch lastUpdate_;
};

// ── EventQueue ────────────────────────────────────────────────────────

/// Internal system notification queue. Events are ordered by exact ready
/// epoch followed by their globally assigned acceptance sequence.
class EventQueue : public SimObject {
public:
  EventQueue(std::string name, ObjectId id, SimObject *parent,
             size_t capacity = 1024)
      : SimObject(ObjectKind::EventQueue, std::move(name), id, parent),
        capacity_(capacity) {}

  // ── Capacity ────────────────────────────────────────────────────────

  size_t capacity() const { return capacity_; }
  bool setCapacity(size_t capacity) {
    if (capacity < committed_.size() + pushProposals_.size())
      return false;
    capacity_ = capacity;
    return true;
  }
  size_t size() const { return committed_.size(); }
  bool isFull() const {
    return committed_.size() + pushProposals_.size() >= capacity_;
  }

  // ── Proposal ────────────────────────────────────────────────────────

  bool proposeSchedule(Event event) {
    if (committed_.size() + pushProposals_.size() >= capacity_)
      return false;
    pushProposals_.insert(event);
    return true;
  }

  // ── Xfer ────────────────────────────────────────────────────────────

  void doXfer(Epoch epoch) override {
    for (auto &event : pushProposals_)
      committed_.insert(event);
    pushProposals_.clear();
  }

  bool hasPendingCommit() const override { return !pushProposals_.empty(); }

  // ── Query ───────────────────────────────────────────────────────────

  std::optional<Event> nextEvent() const {
    if (committed_.empty())
      return std::nullopt;
    return *committed_.begin();
  }

  /// Pop the earliest event and return it.
  std::optional<Event> popNext() {
    if (committed_.empty())
      return std::nullopt;
    auto it = committed_.begin();
    Event e = *it;
    committed_.erase(it);
    return e;
  }

  bool hasEventAt(Epoch epoch) const {
    for (const auto &e : committed_)
      if (e.readyTime == epoch)
        return true;
    return false;
  }

  void reset() override {
    committed_.clear();
    pushProposals_.clear();
  }

private:
  size_t capacity_;
  std::multiset<Event> committed_;
  std::multiset<Event> pushProposals_;
};

// ── TimedEventQueue<T> ───────────────────────────────────────────────

/// Compiler-native named delayed queue. Schedule and pop operations are
/// proposals; neither becomes visible until the epoch's Xfer barrier.
template <typename T> class TimedEventQueue final : public SimObject {
public:
  TimedEventQueue(std::string name, ObjectId id, SimObject *parent,
                  size_t capacity, ObservationSink *observations = nullptr)
      : SimObject(ObjectKind::EventQueue, std::move(name), id, parent,
                  observations),
        capacity_(capacity) {}

  bool trySchedule(T value, Epoch epoch, int64_t delay) {
    if (delay < 0) {
      recordFailure("negative_event_delay");
      return false;
    }
    const auto unsignedDelay = static_cast<uint64_t>(delay);
    if (epoch.time > std::numeric_limits<Tick>::max() - unsignedDelay) {
      recordFailure("tick_overflow");
      return false;
    }
    // Pending pops deliberately do not release capacity in this snapshot.
    if (committed_.size() + scheduleProposals_.size() >= capacity_)
      return false;
    if (nextSequence_ == std::numeric_limits<uint64_t>::max()) {
      recordFailure("event_sequence_overflow");
      return false;
    }
    if (system_ && !system_->registerCommitParticipant(id()))
      return false;
    scheduleProposals_.push_back(
        Entry{{epoch.time + unsignedDelay, delay == 0 ? epoch.delta : 0},
              nextSequence_++,
              std::move(value)});
    return true;
  }

  std::pair<T, bool> tryRecv(Epoch epoch) {
    auto it = committed_.begin();
    std::advance(it, static_cast<std::ptrdiff_t>(popProposalCount_));
    if (it == committed_.end() || it->readyTime > epoch)
      return {T{}, false};
    if (system_ && !system_->registerCommitParticipant(id()))
      return {T{}, false};
    ++popProposalCount_;
    return {it->value, true};
  }

  void doXfer(Epoch epoch) override {
    const bool changed = hasPendingCommit();
    for (size_t index = 0; index < popProposalCount_ && !committed_.empty();
         ++index) {
      committed_.erase(committed_.begin());
      ++totalPops_;
    }
    popProposalCount_ = 0;
    for (Entry &entry : scheduleProposals_) {
      const uint64_t sequence = entry.sequence;
      const Epoch readyTime = entry.readyTime;
      committed_.insert(std::move(entry));
      ++totalPushes_;
      if (system_ && !system_->scheduleEvent(
                         {readyTime, id(), kNotificationKind, sequence})) {
        setRuntimeFailureCode("event_notification_failed");
        break;
      }
    }
    scheduleProposals_.clear();
    highWatermark_ = std::max(highWatermark_, committed_.size());
    if (changed)
      lastUpdate_ = epoch;
  }

  bool hasPendingCommit() const override {
    return popProposalCount_ != 0 || !scheduleProposals_.empty() ||
           !runtimeFailureCode().empty();
  }

  bool deliverEvent(uint32_t kind, uint64_t sequence, Epoch epoch) override {
    if (kind != kNotificationKind)
      return false;
    auto found = std::find_if(
        committed_.begin(), committed_.end(),
        [&](const Entry &entry) { return entry.sequence == sequence; });
    return found != committed_.end() && found->readyTime == epoch;
  }

  RuntimeObjectState runtimeState(Epoch epoch) const override {
    RuntimeObjectState state = SimObject::runtimeState(epoch);
    state.queueOccupancy = committed_.size();
    state.pendingOffers = scheduleProposals_.size();
    state.quiescent = committed_.empty() && !hasPendingCommit();
    if (!state.quiescent)
      state.reason = hasPendingCommit() ? "pending_commit" : "events_not_empty";
    return state;
  }

  size_t capacity() const { return capacity_; }
  size_t committedSize() const { return committed_.size(); }
  size_t highWatermark() const { return highWatermark_; }
  uint64_t totalPushes() const { return totalPushes_; }
  uint64_t totalPops() const { return totalPops_; }

  void collectStatistics(std::vector<StatSnapshot> &out) const override {
    auto append = [&](std::string name, uint64_t value, StatisticKind kind) {
      out.push_back({.name = std::move(name),
                     .objectPath = std::string(path()),
                     .kind = kind,
                     .value = value,
                     .lastUpdate = lastUpdate_});
    };
    append("event_queue_occupancy", committed_.size(), StatisticKind::Gauge);
    append("event_queue_occupancy_peak", highWatermark_, StatisticKind::Gauge);
    append("accepted_events", totalPushes_, StatisticKind::Counter);
    append("completed_events", totalPops_, StatisticKind::Counter);
  }

  void bindSystem(SimSystem *system) override { system_ = system; }

  void reset() override {
    committed_.clear();
    scheduleProposals_.clear();
    popProposalCount_ = 0;
    nextSequence_ = 0;
    highWatermark_ = 0;
    totalPushes_ = 0;
    totalPops_ = 0;
    lastUpdate_ = {};
    clearRuntimeFailureCode();
  }

private:
  static constexpr uint32_t kNotificationKind = 0x45565131u;
  struct Entry {
    Epoch readyTime;
    uint64_t sequence;
    T value;
  };
  struct Earlier {
    bool operator()(const Entry &left, const Entry &right) const {
      return std::tie(left.readyTime, left.sequence) <
             std::tie(right.readyTime, right.sequence);
    }
  };

  void recordFailure(std::string_view code) {
    if (system_)
      (void)system_->registerCommitParticipant(id());
    setRuntimeFailureCode(code);
  }

  size_t capacity_;
  std::multiset<Entry, Earlier> committed_;
  std::vector<Entry> scheduleProposals_;
  size_t popProposalCount_ = 0;
  uint64_t nextSequence_ = 0;
  size_t highWatermark_ = 0;
  uint64_t totalPushes_ = 0;
  uint64_t totalPops_ = 0;
  Epoch lastUpdate_;
  SimSystem *system_ = nullptr;
};

} // namespace gfsim

#endif // GFSIM_QUEUE_H
