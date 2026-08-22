#!/usr/bin/env bash
set -euo pipefail
ulimit -v 1900000

example_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${example_root}/../../.." && pwd)"
build_root="${example_root}/build-packet"
library="${build_root}/generated/bin/libmodel.so"
csv="${build_root}/packet-saturation.csv"
plot="${build_root}/packet-saturation.png"

if [[ ! -f "${library}" ]]; then
  "${example_root}/build-run.sh"
fi

MPLCONFIGDIR="${build_root}/matplotlib" PYTHONPATH="${repo_root}/src" \
  python "${example_root}/benchmark.py" "${library}" \
  --warmup="${WARMUP:-500}" --measure="${MEASURE:-2000}" --output="${csv}"
MPLCONFIGDIR="${build_root}/matplotlib" \
  python "${example_root}/plot.py" "${csv}" --output="${plot}"

printf 'csv=%s\nplot=%s\n' "${csv}" "${plot}"
