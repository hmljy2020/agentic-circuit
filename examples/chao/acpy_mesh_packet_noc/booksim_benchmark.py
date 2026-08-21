from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path


ACCEPTED_RE = re.compile(r"^Accepted packet rate average = ([0-9.eE+-]+)", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("booksim", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument(
        "--rates", default="0.05,0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.85,1.00"
    )
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--warmup", type=int, default=500)
    parser.add_argument("--measure", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmup <= 0 or args.measure <= 0:
        raise ValueError("warmup and measure must be positive")
    if args.warmup != args.measure:
        raise ValueError(
            "BookSim uses one sample_period for warmup and measurement; "
            "warmup and measure must match"
        )

    rates = tuple(float(value) for value in args.rates.split(","))
    seeds = tuple(int(value) for value in args.seeds.split(","))
    rows: list[tuple[float, int, float]] = []
    for rate in rates:
        for seed in seeds:
            command = (
                str(args.booksim),
                str(args.config),
                f"injection_rate={rate}",
                f"seed={seed}",
                "warmup_periods=1",
                f"sample_period={args.measure}",
                "max_samples=2",
            )
            completed = subprocess.run(command, capture_output=True, text=True)
            # This BookSim checkout's main.cpp returns -1 when Run() succeeds.
            # Require its complete success output before accepting exit 255.
            inverted_success = (
                completed.returncode == 255
                and "====== Overall Traffic Statistics ======" in completed.stdout
                and "Simulation unstable" not in completed.stdout
            )
            if completed.returncode != 0 and not inverted_success:
                raise RuntimeError(
                    f"BookSim failed with exit {completed.returncode}:\n"
                    f"{completed.stdout}{completed.stderr}"
                )
            match = ACCEPTED_RE.search(completed.stdout)
            if match is None:
                raise RuntimeError("BookSim output lacks accepted packet throughput")
            throughput = float(match.group(1))
            rows.append((rate, seed, throughput))
            print(f"rate={rate:.2f} seed={seed} throughput={throughput:.6f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("injection_rate", "seed", "throughput"))
        for rate, seed, throughput in rows:
            writer.writerow((f"{rate:.6f}", seed, f"{throughput:.9f}"))


if __name__ == "__main__":
    main()
