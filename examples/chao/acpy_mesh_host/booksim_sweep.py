from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--booksim", type=Path, default=Path("/home/lc/NoC/booksim2/src/booksim"))
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("booksim.cfg"))
    parser.add_argument("--rates", default="0.05,0.10,0.20,0.30,0.40,0.50,0.70,1.00")
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--output", type=Path, default=Path("booksim-saturation.csv"))
    args = parser.parse_args()
    rows = []
    for rate in (float(value) for value in args.rates.split(",")):
        for seed in (int(value) for value in args.seeds.split(",")):
            result = subprocess.run(
                (str(args.booksim), str(args.config), f"injection_rate={rate}", f"seed={seed}"),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            record = next(
                (line for line in result.stdout.splitlines() if line.startswith("results:0,")),
                None,
            )
            if record is None:
                raise RuntimeError(f"BookSim produced no result (exit {result.returncode})")
            fields = record.split(",")
            rows.append((rate, seed, float(fields[20])))
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("injection_rate", "seed", "throughput"))
        for rate, seed, throughput in rows:
            writer.writerow((f"{rate:.6f}", seed, f"{throughput:.9f}"))


if __name__ == "__main__":
    main()
