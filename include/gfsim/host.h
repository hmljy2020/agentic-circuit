#ifndef GFSIM_HOST_H
#define GFSIM_HOST_H

#include "gfsim/object.h"
#include "gfsim/queue.h"

#include <cstdint>
#include <optional>
#include <string>
#include <utility>

namespace gfsim {

/// A statically owned bridge from a host-side, one-entry mailbox into a
/// modeled Queue. stage() never mutates the Queue; normal Work/Xfer performs
/// and commits the Queue proposal.
template <typename T> class HostIngress final : public SimObject {
public:
  HostIngress(std::string name, ObjectId id, SimObject *parent,
              Queue<T> &destination)
      : SimObject(ObjectKind::Compute, std::move(name), id, parent),
        destination_(destination) {}

  bool stage(T value) {
    if (mailbox_ || proposed_)
      return false;
    mailbox_ = std::move(value);
    ++hostAccepted_;
    return true;
  }

  bool mailboxOccupied() const { return mailbox_.has_value(); }
  uint64_t hostAccepted() const { return hostAccepted_; }
  uint64_t queueCommitted() const { return queueCommitted_; }

  void doWork(Epoch) override {
    if (mailbox_ && !proposed_)
      proposed_ = destination_.proposePush(*mailbox_);
  }

  bool hasPendingCommit() const override { return proposed_; }

  void doXfer(Epoch epoch) override {
    if (!proposed_)
      return;
    mailbox_.reset();
    proposed_ = false;
    ++queueCommitted_;
    lastUpdate_ = epoch;
  }

  bool isRunnable(Epoch) const override { return mailbox_.has_value(); }

  RuntimeObjectState runtimeState(Epoch epoch) const override {
    RuntimeObjectState state = SimObject::runtimeState(epoch);
    state.pendingOffers = mailbox_ ? 1 : 0;
    state.quiescent = !mailbox_ && !proposed_;
    if (!state.quiescent)
      state.reason = proposed_ ? "pending_commit" : "host_mailbox_pending";
    return state;
  }

  void collectStatistics(std::vector<StatSnapshot> &snapshots) const override {
    auto append = [&](std::string name, uint64_t value, StatisticKind kind) {
      snapshots.push_back({.name = std::move(name),
                           .objectPath = std::string(path()),
                           .kind = kind,
                           .value = value,
                           .lastUpdate = lastUpdate_});
    };
    append("host_accepted", hostAccepted_, StatisticKind::Counter);
    append("queue_committed", queueCommitted_, StatisticKind::Counter);
    append("mailbox_occupancy", mailbox_ ? 1 : 0, StatisticKind::Gauge);
  }

  void reset() override {
    mailbox_.reset();
    proposed_ = false;
    hostAccepted_ = 0;
    queueCommitted_ = 0;
    lastUpdate_ = {};
    clearRuntimeFailureCode();
  }

private:
  Queue<T> &destination_;
  std::optional<T> mailbox_;
  bool proposed_ = false;
  uint64_t hostAccepted_ = 0;
  uint64_t queueCommitted_ = 0;
  Epoch lastUpdate_{};
};

/// A statically owned bridge that removes committed Queue entries through the
/// normal Work/Xfer barriers and retains one value until the host takes it.
template <typename T> class HostEgress final : public SimObject {
public:
  HostEgress(std::string name, ObjectId id, SimObject *parent, Queue<T> &source)
      : SimObject(ObjectKind::Compute, std::move(name), id, parent),
        source_(source) {}

  bool ready() const { return mailbox_.has_value(); }
  std::optional<T> take() {
    if (!mailbox_)
      return std::nullopt;
    std::optional<T> result = std::move(mailbox_);
    mailbox_.reset();
    ++hostCompleted_;
    return result;
  }

  void doWork(Epoch) override {
    if (!mailbox_ && !proposed_) {
      if (auto value = source_.proposePop()) {
        proposedValue_ = std::move(*value);
        proposed_ = true;
      }
    }
  }
  bool hasPendingCommit() const override { return proposed_; }
  void doXfer(Epoch epoch) override {
    if (!proposed_)
      return;
    mailbox_ = std::move(proposedValue_);
    proposedValue_.reset();
    proposed_ = false;
    proposedValue_.reset();
    ++queueCommitted_;
    lastUpdate_ = epoch;
  }
  bool isRunnable(Epoch) const override { return !mailbox_.has_value(); }
  void reset() override {
    mailbox_.reset();
    proposed_ = false;
    queueCommitted_ = 0;
    hostCompleted_ = 0;
    lastUpdate_ = {};
    clearRuntimeFailureCode();
  }

private:
  Queue<T> &source_;
  std::optional<T> mailbox_;
  std::optional<T> proposedValue_;
  bool proposed_ = false;
  uint64_t queueCommitted_ = 0;
  uint64_t hostCompleted_ = 0;
  Epoch lastUpdate_{};
};

} // namespace gfsim

#endif // GFSIM_HOST_H
