#!/usr/bin/env bash
set -euo pipefail

ulimit -v 1900000

m0_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${m0_root}/../../../.." && pwd)"
build_root="${m0_root}/build"
acir_opt="${repo_root}/build/dev-llvm22/bin/acir-opt"
acir_cxxgen="${repo_root}/build/dev-llvm22/bin/acir-cxxgen"
gfsim_lib="${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a"
bindings_lib="${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a"
lit="/usr/lib/llvm-22/bin/lit"

if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi

for required in "${acir_opt}" "${acir_cxxgen}" "${gfsim_lib}" \
                "${bindings_lib}" "${lit}" /usr/bin/c++ /usr/bin/time; do
  if [[ ! -e "${required}" ]]; then
    echo "missing required tool or library: ${required}" >&2
    exit 1
  fi
done

if [[ -z "${m0_root}" || -z "${build_root}" ||
      "${build_root}" != "${m0_root}/build" ||
      "$(dirname -- "${build_root}")" != "${m0_root}" ||
      "$(basename -- "${build_root}")" != "build" ||
      -L "${build_root}" ]]; then
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

metrics="${build_root}/timing.tsv"
sizes="${build_root}/sizes.tsv"
printf 'case\tstage\telapsed_seconds\tmax_rss_kb\n' > "${metrics}"
printf 'case\tsource_bytes\tfrozen_bytes\tacsim_bytes\tgenerated_source_bytes\tgenerated_source_lines\tobjects\n' > "${sizes}"

time_stage() {
  local case_name="$1"
  local stage="$2"
  shift 2
  /usr/bin/time -f "${case_name}\t${stage}\t%e\t%M" \
    -o "${metrics}" -a "$@"
}

build_case() {
  local case_name="$1"
  local system_name="$2"
  local expected_objects="$3"
  local case_root="${m0_root}/cases/${case_name}"
  local case_build="${build_root}/${case_name}"
  local generated="${case_build}/generated"
  local binary="${generated}/bin/${case_name}-m0"

  if [[ ! -f "${case_root}/model.mlir" ||
        ! -f "${case_root}/runner.cpp" ]]; then
    echo "incomplete M0 case: ${case_name}" >&2
    exit 1
  fi
  mkdir -p -- "${case_build}"

  time_stage "${case_name}" verify "${acir_opt}" \
    "${case_root}/model.mlir" -o /dev/null
  time_stage "${case_name}" freeze "${acir_opt}" --verify-each=false \
    --pass-pipeline='builtin.module(ac-freeze-topology)' \
    "${case_root}/model.mlir" -o "${case_build}/model.frozen.mlir"
  time_stage "${case_name}" lower "${acir_opt}" --ac-lower-to-acsim \
    --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
    "${case_build}/model.frozen.mlir" -o "${case_build}/model.acsim.mlir"

  /usr/bin/time -f "${case_name}\tmodel-plan\t%e\t%M" \
    -o "${metrics}" -a "${acir_cxxgen}" \
    "${case_build}/model.acsim.mlir" --stop-after=model-plan \
    > "${case_build}/model-plan.txt"

  time_stage "${case_name}" cxxgen "${acir_cxxgen}" \
    "${case_build}/model.acsim.mlir" --stop-after=link \
    --output-root="${generated}" \
    --project-name="superscalar-m0-${case_name}" \
    --project-identity="project.chao.superscalar.m0.${case_name}" \
    --system-name="${system_name}" \
    --system-identity="system.chao.superscalar.m0.${case_name}" \
    --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
    --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
    --include-root="${repo_root}/include" \
    --link-input="${gfsim_lib}" --link-input="${bindings_lib}" \
    --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM

  local generated_objects=()
  while IFS= read -r object; do
    if [[ "${object}" != *_main_cpp.o ]]; then
      generated_objects+=("${object}")
    fi
  done < <(find "${generated}/obj" -maxdepth 1 -type f -name '*.o' | sort)
  if [[ ${#generated_objects[@]} -ne ${expected_objects} ]]; then
    echo "${case_name}: expected ${expected_objects} generated objects, got ${#generated_objects[@]}" >&2
    exit 1
  fi

  time_stage "${case_name}" runner-link /usr/bin/c++ -std=c++20 \
    -I"${generated}/include" -I"${repo_root}/include" \
    -I/usr/lib/llvm-22/include "${case_root}/runner.cpp" \
    "${generated_objects[@]}" "${gfsim_lib}" "${bindings_lib}" \
    -L/usr/lib/llvm-22/lib -lLLVM -o "${binary}"

  /usr/bin/time -f "${case_name}\tsemantic-run\t%e\t%M" \
    -o "${metrics}" -a "${binary}" > "${case_build}/semantic-1.txt"
  "${binary}" > "${case_build}/semantic-2.txt"
  diff -u "${case_build}/semantic-1.txt" "${case_build}/semantic-2.txt"
  /usr/bin/time -f "${case_name}\tbenchmark\t%e\t%M" \
    -o "${metrics}" -a "${binary}" --benchmark \
    > "${case_build}/benchmark.txt"

  local generated_bytes
  local generated_lines
  generated_bytes="$(find "${generated}/include" "${generated}/src" -type f \
    \( -name '*.h' -o -name '*.cpp' \) -printf '%s\n' | \
    awk '{sum += $1} END {print sum + 0}')"
  generated_lines="$(find "${generated}/include" "${generated}/src" -type f \
    \( -name '*.h' -o -name '*.cpp' \) -exec wc -l {} + | \
    awk '$2 != "total" {sum += $1} END {print sum + 0}')"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${case_name}" \
    "$(wc -c < "${case_root}/model.mlir")" \
    "$(wc -c < "${case_build}/model.frozen.mlir")" \
    "$(wc -c < "${case_build}/model.acsim.mlir")" \
    "${generated_bytes}" "${generated_lines}" "${#generated_objects[@]}" \
    >> "${sizes}"

  cat "${case_build}/semantic-1.txt"
  cat "${case_build}/benchmark.txt"
}

# C API + model + one module + N processes.
build_case queue m0_queue 5
build_case event_latency m0_event_latency 8
build_case arbitrate_transfer m0_arbitrate_transfer 7

lit_log="${build_root}/targeted-lit.txt"
/usr/bin/time -f "repository\ttargeted-lit\t%e\t%M" \
  -o "${metrics}" -a "${lit}" -j1 -sv "${repo_root}/build/dev-llvm22/test" \
  --filter='(ACIR/(arbitrate|event-queue|peek-invalid|queue-await-invalid|space-invalid|try-transfer-invalid)|Conversion/(arbitrate|native-event-queue|native-queue|try-transfer)|CodeGen/(arbitrate|native-event-queue|native-queue|try-transfer))' \
  > "${lit_log}" 2>&1

echo "M0 acceptance passed"
echo "timing: ${metrics}"
echo "sizes: ${sizes}"
echo "targeted lit: ${lit_log}"
