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
    parser.add_argument("elastic", type=Path)
    parser.add_argument("credit", type=Path)
    parser.add_argument("iq", type=Path)
    parser.add_argument("booksim", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    series = {
        "ac_elastic_mean": read_samples(args.elastic),
        "ac_credit_owner_mean": read_samples(args.credit),
        "ac_input_queued_mean": read_samples(args.iq),
        "booksim_mean": read_samples(args.booksim),
    }
    rate_sets = {tuple(sorted(samples)) for samples in series.values()}
    if len(rate_sets) != 1:
        raise RuntimeError("all timing series must use identical injection rates")
    rates = list(next(iter(rate_sets)))

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("injection_rate", *series))
        for rate in rates:
            writer.writerow(
                (f"{rate:.6f}", *(f"{mean(samples[rate]):.9f}" for samples in series.values()))
            )

    figure, axis = plt.subplots(figsize=(8.2, 5.2), dpi=150)
    axis.plot(rates, rates, "--", color="#8a8f98", label="ideal y = x")
    styles = (
        ("ac_elastic_mean", "#2878b5", "AC elastic"),
        ("ac_credit_owner_mean", "#2a9d55", "AC credit owner"),
        ("ac_input_queued_mean", "#8e44ad", "AC input queued (VA1/SA1)"),
        ("booksim_mean", "#d35400", "BookSim IQ mesh"),
    )
    for key, color, label in styles:
        samples = series[key]
        averages = [mean(samples[rate]) for rate in rates]
        lows = [min(samples[rate]) for rate in rates]
        highs = [max(samples[rate]) for rate in rates]
        axis.fill_between(rates, lows, highs, color=color, alpha=0.10)
        axis.plot(rates, averages, marker="o", linewidth=2.0, color=color, label=label)
    axis.set(
        title="2×2 Uniform Traffic: VC1 timing progression",
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
