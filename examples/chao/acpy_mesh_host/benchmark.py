from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

from agentic_circuit.runtime import ModelRuntime


@dataclass
class TrafficManager:
    model: ModelRuntime
    seed: int
    pattern: str = "uniform"

    def __post_init__(self) -> None:
        self.random = random.Random(self.seed)
        self.pending: list[int | None] = [None] * len(self.model.inputs)
        self.sequence = 0

    def destination(self, source: int) -> int:
        if self.pattern == "uniform":
            return self.random.randrange(len(self.pending))
        x, y = source % 2, source // 2
        return y + 2 * x

    def tick(self, rate: float) -> int:
        accepted = 0
        for source, ingress in enumerate(self.model.inputs):
            if self.pending[source] is None and self.random.random() < rate:
                destination = self.destination(source)
                self.pending[source] = (self.sequence << 2) | destination
                self.sequence += 1
            value = self.pending[source]
            if value is not None and self.model.offer(ingress, value):
                self.pending[source] = None
                accepted += 1
        self.model.step()
        return accepted


def delivered(model: ModelRuntime) -> int:
    return sum(
        value
        for (path, name), value in model.statistics().items()
        if name == "completed_transactions"
        and any(path.endswith(f"/rx{node}") for node in ("00", "10", "01", "11"))
    )


def run_point(
    model: ModelRuntime, rate: float, seed: int, warmup: int, measure: int, pattern: str
) -> tuple[int, int, float]:
    model.reset()
    traffic = TrafficManager(model, seed, pattern)
    for _ in range(warmup):
        traffic.tick(rate)
    before = delivered(model)
    accepted = sum(traffic.tick(rate) for _ in range(measure))
    completed = delivered(model) - before
    return accepted, completed, completed / (measure * len(model.inputs))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("library", type=Path)
    parser.add_argument("--rates", default="0.05,0.10,0.20,0.30,0.40,0.50,0.70,1.00")
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--warmup", type=int, default=1000)
    parser.add_argument("--measure", type=int, default=5000)
    parser.add_argument("--pattern", choices=("uniform", "transpose"), default="uniform")
    parser.add_argument("--output", type=Path, default=Path("saturation.csv"))
    args = parser.parse_args()
    rates = tuple(float(value) for value in args.rates.split(","))
    seeds = tuple(int(value) for value in args.seeds.split(","))
    rows = []
    with ModelRuntime(args.library) as model:
        for rate in rates:
            for seed in seeds:
                accepted, completed, throughput = run_point(
                    model, rate, seed, args.warmup, args.measure, args.pattern
                )
                rows.append((rate, seed, accepted, completed, throughput))
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("injection_rate", "seed", "accepted", "delivered", "throughput"))
        for rate, seed, accepted, completed, throughput in rows:
            writer.writerow((f"{rate:.6f}", seed, accepted, completed, f"{throughput:.9f}"))


if __name__ == "__main__":
    main()
