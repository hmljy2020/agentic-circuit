#!/usr/bin/env bash
set -euo pipefail
ulimit -v 1900000

example_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${example_root}/../../../.." && pwd)"
result_root="${example_root}/benchmark-results/vc1-iq"
build_root="${example_root}/build-iq"
library="${build_root}/generated/bin/libmodel.so"
booksim="${BOOKSIM:-/home/lc/NoC/booksim2/src/booksim}"
rates="${RATES:-0.05,0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.85,1.00}"
seeds="${SEEDS:-1,2,3}"
warmup="${WARMUP:-2000}"
measure="${MEASURE:-2000}"

if [[ ! -x "${booksim}" ]]; then
  printf 'BookSim executable not found: %s\n' "${booksim}" >&2
  exit 1
fi
if [[ ! -f "${library}" ]]; then
  PROFILE=iq MODEL_FILE=model_iq.py RUNNER_FILE=run_iq.py "${example_root}/build-run.sh"
fi

PYTHONPATH="${repo_root}/src" python "${example_root}/benchmark.py" "${library}" \
  --rates="${rates}" --seeds="${seeds}" --warmup="${warmup}" \
  --measure="${measure}" --output="${result_root}/ac.csv"
python "${example_root}/booksim_benchmark.py" "${booksim}" \
  "${result_root}/booksim.cfg" --rates="${rates}" --seeds="${seeds}" \
  --warmup="${warmup}" --measure="${measure}" --output="${result_root}/booksim.csv"
MPLCONFIGDIR="${build_root}/matplotlib" python "${example_root}/plot_timing_comparison.py" \
  "${example_root}/benchmark-results/vc1/ac.csv" \
  "${example_root}/benchmark-results/vc1-credit/ac.csv" \
  "${result_root}/ac.csv" "${result_root}/booksim.csv" \
  --output="${result_root}/throughput.png" --summary="${result_root}/summary.csv"

printf 'results=%s\n' "${result_root}"
