#!/usr/bin/env bash
set -euo pipefail

ulimit -v 1900000

scenario_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
example_root="$(cd -- "${scenario_root}/.." && pwd)"
repo_root="$(cd -- "${example_root}/../../../../.." && pwd)"

run_scenario() {
  local name="$1" system="$2" objects="$3"
  local build_root="${scenario_root}/build-${name}"
  if [[ "${build_root}" != "${scenario_root}/build-${name}" || -L "${build_root}" ]]; then
    echo "unsafe build directory: ${build_root}" >&2
    exit 1
  fi
  if [[ -e "${build_root}" && ! -d "${build_root}" ]]; then
    echo "build path is not a directory: ${build_root}" >&2
    exit 1
  fi
  if [[ -d "${build_root}" ]]; then
    rm -rf -- "${build_root}"
  fi
  mkdir -p -- "${build_root}"

  "${repo_root}/build/dev-llvm22/bin/acir-opt" --verify-each=false \
    --pass-pipeline='builtin.module(ac-freeze-topology)' \
    "${scenario_root}/${name}.mlir" -o "${build_root}/model.frozen.mlir"

  "${repo_root}/build/dev-llvm22/bin/acir-opt" --ac-lower-to-acsim \
    --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
    "${build_root}/model.frozen.mlir" -o "${build_root}/model.acsim.mlir"

  local out_root="${build_root}/generated"
  "${repo_root}/build/dev-llvm22/bin/acir-cxxgen" \
    "${build_root}/model.acsim.mlir" --stop-after=link \
    --output-root="${out_root}" \
    --project-name="chao-${name}" --project-identity="project.chao.${name}" \
    --system-name="${system}" --system-identity="system.${system}" \
    --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
    --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
    --include-root="${repo_root}/include" \
    --link-input="${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" \
    --link-input="${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" \
    --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM

  local generated_objects=()
  while IFS= read -r object; do
    if [[ "${object}" != *_main_cpp.o ]]; then
      generated_objects+=("${object}")
    fi
  done < <(find "${out_root}/obj" -maxdepth 1 -type f -name '*.o' | sort)

  if [[ ${#generated_objects[@]} -ne ${objects} ]]; then
    echo "FAIL ${name}: expected ${objects} generated objects, got ${#generated_objects[@]}" >&2
    exit 1
  fi

  /usr/bin/c++ -std=c++20 -I"${out_root}/include" \
    -I"${repo_root}/include" -I/usr/lib/llvm-22/include \
    "${scenario_root}/${name}_runner.cpp" "${generated_objects[@]}" \
    "${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" \
    "${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" \
    -L/usr/lib/llvm-22/lib -lLLVM -o "${out_root}/bin/${name}-demo"

  echo "=== ${name} ==="
  "${out_root}/bin/${name}-demo"
}

# scenario-name  system-name   generated-object count (C API + model + module + processes)
run_scenario sc02_contend_out0      sc02_demo 6
run_scenario sc03_a_over_b          sc03_demo 6
run_scenario sc04_b_without_a       sc04_demo 5
run_scenario sc05_a_blocked_b_moves sc05_demo 5
run_scenario sc06_same_input_two_vc sc06_demo 5
run_scenario sc09_fifo_order        sc09_demo 6

echo "all scenarios passed"
