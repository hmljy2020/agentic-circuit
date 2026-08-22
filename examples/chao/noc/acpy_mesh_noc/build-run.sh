#!/usr/bin/env bash
set -euo pipefail

ulimit -v 1900000
script_start_us="${EPOCHREALTIME/./}"
timing_labels=()
timing_values_us=()

run_stage() {
  local label="$1"
  shift
  local start_us="${EPOCHREALTIME/./}"
  local end_us elapsed_us rc
  printf 'timing stage=%s status=started\n' "${label}"
  if "$@"; then
    rc=0
  else
    rc=$?
  fi
  end_us="${EPOCHREALTIME/./}"
  elapsed_us=$((end_us - start_us))
  timing_labels+=("${label}")
  timing_values_us+=("${elapsed_us}")
  printf 'timing stage=%s status=%s elapsed=%d.%06ds\n' \
    "${label}" "$([[ ${rc} -eq 0 ]] && printf passed || printf failed)" \
    "$((elapsed_us / 1000000))" "$((elapsed_us % 1000000))"
  return "${rc}"
}

print_timing_summary() {
  local total_us index
  total_us=$((${EPOCHREALTIME/./} - script_start_us))
  printf 'timing summary:\n'
  for index in "${!timing_labels[@]}"; do
    printf '  %-20s %d.%06ds\n' "${timing_labels[index]}" \
      "$((timing_values_us[index] / 1000000))" \
      "$((timing_values_us[index] % 1000000))"
  done
  printf '  %-20s %d.%06ds\n' total \
    "$((total_us / 1000000))" "$((total_us % 1000000))"
}

example_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${example_root}/../../.." && pwd)"
build_root="${example_root}/build-noc"
if [[ "${build_root}" != "${example_root}/build-noc" || -L "${build_root}" ]]; then
  echo "unsafe build directory: ${build_root}" >&2
  exit 1
fi
if [[ -d "${build_root}" ]]; then rm -rf -- "${build_root}"; fi
mkdir -p -- "${build_root}"

elaborate() (
  cd -- "${example_root}" || return
  PYTHONPATH="${repo_root}/src:${repo_root}/build/dev-llvm22/python" \
    python -m agentic_circuit._cli elaborate model.py \
    --system main -o "${build_root}/model.ac.mlir"
)

freeze_topology() {
  "${repo_root}/build/dev-llvm22/bin/acir-opt" --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  "${build_root}/model.ac.mlir" -o "${build_root}/model.frozen.mlir"
}

lower_to_acsim() {
  "${repo_root}/build/dev-llvm22/bin/acir-opt" --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  "${build_root}/model.frozen.mlir" -o "${build_root}/model.acsim.mlir"
}

out_root="${build_root}/generated"
generate_and_link_cpp() {
  "${repo_root}/build/dev-llvm22/bin/acir-cxxgen" \
  "${build_root}/model.acsim.mlir" --stop-after=link \
  --output-root="${out_root}" \
  --project-name=acpy-mesh-noc --project-identity=project.chao.acpy-mesh-noc \
  --system-name=mesh_noc --system-identity=system.chao.mesh-noc \
  --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
  --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
  --include-root="${repo_root}/include" \
  --link-input="${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" \
  --link-input="${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" \
  --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM
}

compile_runner() {
  local objects=()
  mapfile -t objects < <(find "${out_root}/obj" -maxdepth 1 -type f -name '*.o' ! -name '*_main_cpp.o' | sort)
  /usr/bin/c++ -std=c++20 -I"${out_root}/include" -I"${repo_root}/include" \
    -I/usr/lib/llvm-22/include "${example_root}/runner.cpp" "${objects[@]}" \
    "${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" \
    "${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" \
    -L/usr/lib/llvm-22/lib -lLLVM -o "${out_root}/bin/mesh-noc"
}

run_stage elaborate elaborate
run_stage freeze-topology freeze_topology
run_stage lower-to-acsim lower_to_acsim
run_stage cxxgen-link generate_and_link_cpp
run_stage runner-compile compile_runner
run_stage runtime "${out_root}/bin/mesh-noc"
print_timing_summary
