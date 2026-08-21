from __future__ import annotations

import argparse
import csv
import random
import struct
from dataclasses import dataclass
from pathlib import Path

from agentic_circuit.runtime import ModelRuntime


NODES = 4


def packet(destination: int, sequence: int) -> bytes:
    return struct.pack("<ii", destination, sequence)


@dataclass
class UniformTraffic:
    model: ModelRuntime
    seed: int

    def __post_init__(self) -> None:
        self.random = random.Random(self.seed)
        self.pending: list[bytes | None] = [None] * NODES
        self.sequence = 0

    def inject(self, rate: float) -> int:
        accepted = 0
        for source, ingress in enumerate(self.model.inputs):
            if self.pending[source] is None and self.random.random() < rate:
                destination = self.random.randrange(NODES)
                self.pending[source] = packet(destination, self.sequence)
                self.sequence += 1
            value = self.pending[source]
            if value is not None and self.model.offer_bytes(ingress, value):
                self.pending[source] = None
                accepted += 1
        return accepted


def advance(model: ModelRuntime, traffic: UniformTraffic, rate: float) -> tuple[int, int]:
    accepted = traffic.inject(rate)
    model.step()
    delivered = 0
    for output in model.outputs:
        if model.output_ready(output):
            value = model.take_bytes(output)
            if value is None or len(value) != 8:
                raise RuntimeError("Packet ejection returned an invalid value")
            destination, _sequence = struct.unpack("<ii", value)
            if output != f"node{destination}":
                raise RuntimeError(
                    f"Packet for node{destination} was ejected at {output}"
                )
            delivered += 1
    return accepted, delivered


def run_point(
    model: ModelRuntime, rate: float, seed: int, warmup: int, measure: int
) -> tuple[int, int, float]:
    model.reset()
    traffic = UniformTraffic(model, seed)
    for _ in range(warmup):
        advance(model, traffic, rate)
    accepted = 0
    delivered = 0
    for _ in range(measure):
        tick_accepted, tick_delivered = advance(model, traffic, rate)
        accepted += tick_accepted
        delivered += tick_delivered
    return accepted, delivered, delivered / (measure * NODES)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("library", type=Path)
    parser.add_argument(
        "--rates", default="0.05,0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.85,1.00"
    )
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--warmup", type=int, default=500)
    parser.add_argument("--measure", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmup < 0 or args.measure <= 0:
        raise ValueError("warmup must be non-negative and measure must be positive")

    rates = tuple(float(value) for value in args.rates.split(","))
    seeds = tuple(int(value) for value in args.seeds.split(","))
    rows: list[tuple[float, int, int, int, float]] = []
    with ModelRuntime(args.library) as model:
        if model.input_sizes != {f"node{node}": 8 for node in range(NODES)}:
            raise RuntimeError("benchmark requires four eight-byte Packet inputs")
        if model.output_sizes != {f"node{node}": 8 for node in range(NODES)}:
            raise RuntimeError("benchmark requires four eight-byte Packet outputs")
        for rate in rates:
            for seed in seeds:
                accepted, delivered, throughput = run_point(
                    model, rate, seed, args.warmup, args.measure
                )
                rows.append((rate, seed, accepted, delivered, throughput))
                print(
                    f"rate={rate:.2f} seed={seed} accepted={accepted} "
                    f"delivered={delivered} throughput={throughput:.6f}"
                )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("injection_rate", "seed", "accepted", "delivered", "throughput"))
        for rate, seed, accepted, delivered, throughput in rows:
            writer.writerow(
                (f"{rate:.6f}", seed, accepted, delivered, f"{throughput:.9f}")
            )


if __name__ == "__main__":
    main()
