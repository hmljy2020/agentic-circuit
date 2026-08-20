# Primitive vs. Component: the ACIR v0.2 design taxonomy

Reference summary of what the design classifies as a **primitive** (ACIR Core
semantics) versus a **component** (the `ac.std.*` catalog). Authoritative
sources: `contracts/acir-v0.2.yaml` (op/type inventory) and
`docs/specs/acir-stdlib-v0.2.md` (component catalog). Last synced 2026-08-19.

## Boundary rule

> "Compute units, schedulers, links, buses, crossbars, routers, DMA engines,
> storage, caches, and protocol adapters are component families, **not separate
> ACIR Core operations**." — `docs/specs/acir-stdlib-v0.2.md:42`

A component is a conventional architecture module *composed* from Core
semantics (queues, resources, processes, protocols) and frozen as a
`ComponentSchema`. A primitive is an irreducible semantic building block.
Instantiation of a `declared_unavailable` component fails at schema resolution
with a hard availability diagnostic — no stub, no substitution, no link-time
deferral.

---

## 1. Primitive — ACIR Core operations (59 ops, epoch 0.2)

| Family | Operations | Count |
|---|---|---|
| **Hierarchy / structure** | `ac.system` `ac.module` `ac.module.extern` `ac.module.generated` `ac.instance` `ac.array` `ac.instances` `ac.view` `ac.port` `ac.return` | 10 |
| **Declarations / collections** | `ac.type_scope` `ac.type_alias` `ac.struct` `ac.enum` `ac.union` `ac.packet` `ac.transaction` `ac.interface` | 8 |
| **Protocols** | `ac.protocol` `ac.role` `ac.state` `ac.event` `ac.transition` `ac.guarantee` | 6 |
| **Topology / resources** | `ac.queue` `ac.event_queue` `ac.resource` `ac.address_space` `ac.address_map` `ac.time_domain` | 6 |
| **Process** | `ac.process` | 1 |
| **Record / packet ops** | `ac.record.create` `ac.record.get` `ac.record.with` `ac.packet.serialize` `ac.packet.deserialize` | 5 |
| **Queue / event runtime** | `ac.try_send` `ac.try_recv` `ac.peek` `ac.space` `ac.schedule` `ac.try_event` `ac.wait_until` `ac.wait_for` `ac.await_event` `ac.await_queue` `ac.yield_sim` | 11 |
| **Trace** | `ac.trace.open` `ac.trace.next` `ac.trace.decode` `ac.trace.eof` `ac.trace.position` | 5 |
| **Verification / assertion** | `ac.require` `ac.ensure` `ac.assert` | 3 |
| **Statistics / observation** | `ac.probe` `ac.stat` `ac.stat.add` `ac.instrumentation` | 4 |

### Core types (9 manifest types + value forms)

`struct` `packet` `transaction` `enum` `union` `optional` `list` `vector`
`flow`; value forms `!ac.endpoint<...>` `!ac.resource_ref<...>`
`!ac.channel<...>` `!ac.duration` `!ac.rate` `!ac.event<T>`
`!ac.address<@space>` `!ac.resource_token<@res>`.

---

## 2. Component — `ac.std.*` catalog (37 schemas)

### Available (initial executable baseline, 9)

| Name | Kind |
|---|---|
| `ac.std.TraceSource` `ac.std.Queue` `ac.std.Scheduler` `ac.std.Compute` `ac.std.Link` `ac.std.Memory` `ac.std.Sink` | components |
| `ac.std.ready_valid` `ac.std.request_response` | protocols |

### `declared_unavailable` (27, instantiation is a hard failure)

| Family | Components |
|---|---|
| control | `Arbiter` `Dispatcher` `Scoreboard` `DependencyTracker` |
| interconnect | `Bus` `Crossbar` `Router` `Switch` |
| transport | `Dma` `Packetizer` `Reassembler` `LoadStore` |
| storage | `RegisterFile` `Scratchpad` `Cache` `Tlb` `MemoryController` |
| synchronization | `Fork` `Join` `Broadcast` `Barrier` |
| adaptation | `ProtocolAdapter` `WidthAdapter` `TimeDomainBridge` `AddressTranslator` `MemoryManagement` |
| workload | `TrafficSource` |

Plus 4 `declared_unavailable` protocol schemas: `fifo_push_pop` `credit`
`fire_and_forget` `event_notification`.

---

## Takeaway for this examples tree

- There is **no `ac.crossbar` op** and none is planned: crossbar belongs to the
  `interconnect` component family and would surface only as an
  `ac.std.Crossbar` schema marked `available` by a build profile once a
  conforming C++20 template exists.
- A crossbar today is written in ACIR Core directly — see
  [`crossbar_vc/`](crossbar_vc/) (8 queues + one centralized scheduler process),
  which is structurally identical to how `ac.std.Crossbar` would be implemented.
- `ac.space` (epoch 0.2, the newest queue op) exists precisely to let such
  scheduler processes observe *free capacity* of depth ≥ 1 queues.
