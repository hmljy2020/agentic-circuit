#!/usr/bin/env bash
set -euo pipefail
ulimit -v 1900000

example_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${example_root}/../../../.." && pwd)"
result_root="${example_root}/benchmark-results/vc1-iq-4x4"
build_root="${example_root}/build-iq-4x4"
library="${build_root}/generated/bin/libmodel.so"
booksim="${BOOKSIM:-/home/lc/NoC/booksim2/src/booksim}"
rates="${RATES:-0.02,0.04,0.06,0.08,0.10,0.12,0.15,0.20,0.30,0.50,0.70,1.00}"
seeds="${SEEDS:-1,2,3}"
warmup="${WARMUP:-1000}"
measure="${MEASURE:-1000}"

if [[ ! -x "${booksim}" ]]; then
  printf 'BookSim executable not found: %s\n' "${booksim}" >&2
  exit 1
fi
if [[ ! -f "${library}" ]]; then
  PROFILE=iq-4x4 MODEL_FILE=model_iq_4x4.py RUNNER_FILE=run_iq_4x4.py \
    "${example_root}/build-run.sh"
fi

PYTHONPATH="${repo_root}/src" python "${example_root}/benchmark.py" "${library}" \
  --rates="${rates}" --seeds="${seeds}" --warmup="${warmup}" \
  --measure="${measure}" --output="${result_root}/ac.csv"
python "${example_root}/booksim_benchmark.py" "${booksim}" \
  "${result_root}/booksim.cfg" --rates="${rates}" --seeds="${seeds}" \
  --warmup="${warmup}" --measure="${measure}" --output="${result_root}/booksim.csv"
MPLCONFIGDIR="${build_root}/matplotlib" python "${example_root}/plot_comparison.py" \
  "${result_root}/ac.csv" "${result_root}/booksim.csv" \
  --ac-label="AC input queued (4×4)" \
  --title="4×4 Uniform Traffic: AC vs BookSim (1 VC, depth 2)" \
  --output="${result_root}/throughput.png" --summary="${result_root}/summary.csv"

printf 'results=%s\n' "${result_root}"
