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


def read_samples(path: Path) -> dict[float, list[float]]:
    samples: dict[float, list[float]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            samples[float(row["injection_rate"])].append(float(row["throughput"]))
    if not samples:
        raise RuntimeError(f"{path} contains no samples")
    return samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ac", type=Path)
    parser.add_argument("booksim", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    ac = read_samples(args.ac)
    booksim = read_samples(args.booksim)
    if set(ac) != set(booksim):
        raise RuntimeError("AC and BookSim injection-rate samples differ")
    rates = sorted(ac)
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(("injection_rate", "ac_mean", "booksim_mean"))
            for rate in rates:
                writer.writerow(
                    (
                        f"{rate:.6f}",
                        f"{mean(ac[rate]):.9f}",
                        f"{mean(booksim[rate]):.9f}",
                    )
                )

    figure, axis = plt.subplots(figsize=(7.4, 4.8), dpi=150)
    axis.plot(rates, rates, "--", color="#8a8f98", label="ideal y = x")
    for samples, color, label in (
        (ac, "#2878b5", "AC Packet MeshNoC"),
        (booksim, "#d35400", "BookSim 2.0 IQ mesh"),
    ):
        averages = [mean(samples[rate]) for rate in rates]
        lows = [min(samples[rate]) for rate in rates]
        highs = [max(samples[rate]) for rate in rates]
        axis.fill_between(rates, lows, highs, color=color, alpha=0.14)
        axis.plot(rates, averages, marker="o", linewidth=2.2, color=color, label=label)
    axis.set(
        title="2×2 Uniform Traffic: AC vs BookSim (1 VC, 1-flit packets)",
        xlabel="Requested injection rate (packets / node / cycle)",
        ylabel="Accepted throughput (packets / node / cycle)",
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
