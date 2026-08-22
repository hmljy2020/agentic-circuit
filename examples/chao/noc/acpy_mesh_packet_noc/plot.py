from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean


os.environ.setdefault("MPLCONFIGDIR", "/tmp/agentic-circuit-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    samples: dict[float, list[float]] = defaultdict(list)
    with args.csv.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            samples[float(row["injection_rate"])].append(float(row["throughput"]))
    if not samples:
        raise RuntimeError("benchmark CSV contains no samples")

    rates = sorted(samples)
    averages = [mean(samples[rate]) for rate in rates]
    lows = [min(samples[rate]) for rate in rates]
    highs = [max(samples[rate]) for rate in rates]

    figure, axis = plt.subplots(figsize=(7.2, 4.6), dpi=150)
    axis.plot(rates, rates, linestyle="--", color="#8a8f98", label="ideal y = x")
    axis.fill_between(rates, lows, highs, color="#2878b5", alpha=0.18, label="seed range")
    axis.plot(rates, averages, marker="o", linewidth=2.2, color="#2878b5", label="Packet MeshNoC")
    axis.set(
        title="ACPy 2×2 Packet MeshNoC Saturation Throughput",
        xlabel="Requested injection rate (packets / node / tick)",
        ylabel="Delivered throughput (packets / node / tick)",
        xlim=(0.0, 1.02),
        ylim=(0.0, 1.02),
    )
    axis.grid(True, alpha=0.25)
    axis.legend(loc="upper left")
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
