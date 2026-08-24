#!/usr/bin/env bash
set -euo pipefail

ulimit -v 1900000

m1_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${m1_root}/../../../.." && pwd)"
build_root="${m1_root}/build"
compiler_build="${ACIR_BUILD_PRESET:-dev-llvm22}"
if [[ ! "${compiler_build}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "invalid ACIR_BUILD_PRESET: ${compiler_build}" >&2
  exit 2
fi
compiler_root="${repo_root}/build/${compiler_build}"
acir_opt="${compiler_root}/bin/acir-opt"
acir_cxxgen="${compiler_root}/bin/acir-cxxgen"
gfsim_tests="${compiler_root}/bin/GfsimTests"
gfsim_lib="${compiler_root}/lib/gfsim/libgfsim.a"
bindings_lib="${compiler_root}/lib/Bindings/libACIRBindings.a"
lit="/usr/lib/llvm-22/bin/lit"

if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi
for required in "${acir_opt}" "${acir_cxxgen}" "${gfsim_tests}" \
                "${gfsim_lib}" "${bindings_lib}" "${lit}" \
                /usr/bin/c++ /usr/bin/time /usr/bin/python3; do
  if [[ ! -e "${required}" ]]; then
    echo "missing required tool or library: ${required}" >&2
    exit 1
  fi
done

if [[ -z "${m1_root}" || -z "${build_root}" ||
      "${build_root}" != "${m1_root}/build" ||
      "$(dirname -- "${build_root}")" != "${m1_root}" ||
      "$(basename -- "${build_root}")" != "build" ||
      -L "${build_root}" ]]; then
  echo "unsafe M1 build directory: ${build_root}" >&2
  exit 1
fi
if [[ -e "${build_root}" && ! -d "${build_root}" ]]; then
  echo "M1 build path is not a directory: ${build_root}" >&2
  exit 1
fi
if [[ -d "${build_root}" ]]; then
  rm -rf -- "${build_root}"
fi
mkdir -p -- "${build_root}"

metrics="${build_root}/timing.tsv"
printf 'stage\telapsed_seconds\tmax_rss_kb\n' > "${metrics}"
time_stage() {
  local stage="$1"
  shift
  /usr/bin/time -f "${stage}\t%e\t%M" -o "${metrics}" -a "$@"
}

/usr/bin/time -f "generate\t%e\t%M" -o "${metrics}" -a \
  /usr/bin/python3 "${m1_root}/gen_model.py" > "${build_root}/model.mlir"
time_stage verify "${acir_opt}" "${build_root}/model.mlir" -o /dev/null
time_stage optimize "${acir_opt}" \
  --pass-pipeline='builtin.module(canonicalize,cse)' \
  "${build_root}/model.mlir" -o "${build_root}/model.optimized.mlir"
time_stage freeze "${acir_opt}" --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  "${build_root}/model.optimized.mlir" -o "${build_root}/model.frozen.mlir"
time_stage lower "${acir_opt}" --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  "${build_root}/model.frozen.mlir" -o "${build_root}/model.acsim.mlir"

generated="${build_root}/generated"
time_stage cxxgen "${acir_cxxgen}" "${build_root}/model.acsim.mlir" \
  --stop-after=link --output-root="${generated}" \
  --project-name=superscalar-m1 \
  --project-identity=project.chao.superscalar.m1 \
  --system-name=m1_scheduler \
  --system-identity=system.chao.superscalar.m1 \
  --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
  --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
  --include-root="${repo_root}/include" \
  --link-input="${gfsim_lib}" --link-input="${bindings_lib}" \
  --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM

generated_objects=()
while IFS= read -r object; do
  if [[ "${object}" != *_main_cpp.o ]]; then
    generated_objects+=("${object}")
  fi
done < <(find "${generated}/obj" -maxdepth 1 -type f -name '*.o' | sort)
if [[ ${#generated_objects[@]} -ne 4 ]]; then
  echo "expected four generated non-main objects, got ${#generated_objects[@]}" >&2
  exit 1
fi

binary="${generated}/bin/superscalar-m1-runner"
time_stage runner-link /usr/bin/c++ -std=c++20 \
  -I"${generated}/include" -I"${repo_root}/include" \
  -I/usr/lib/llvm-22/include "${m1_root}/runner.cpp" \
  "${generated_objects[@]}" "${gfsim_lib}" "${bindings_lib}" \
  -L/usr/lib/llvm-22/lib -lLLVM -o "${binary}"
time_stage semantic "${binary}"
"${binary}" > "${build_root}/semantic-1.txt"
"${binary}" > "${build_root}/semantic-2.txt"
diff -u "${build_root}/semantic-1.txt" "${build_root}/semantic-2.txt"
time_stage benchmark "${binary}" --benchmark
"${binary}" --benchmark > "${build_root}/benchmark.txt"

time_stage runtime-state-array "${gfsim_tests}" \
  --gtest_filter='GfsimStateArrayTest.*'
time_stage targeted-lit "${lit}" -j1 -sv "${compiler_root}/test" \
  --filter='(ACIR/state-array|Conversion/native-state-array|CodeGen/native-state-array)'

generated_bytes="$(find "${generated}/include" "${generated}/src" -type f \
  \( -name '*.h' -o -name '*.cpp' \) -printf '%s\n' | \
  awk '{sum += $1} END {print sum + 0}')"
generated_lines="$(find "${generated}/include" "${generated}/src" -type f \
  \( -name '*.h' -o -name '*.cpp' \) -exec wc -l {} + | \
  awk '$2 != "total" {sum += $1} END {print sum + 0}')"
{
  printf 'artifact\tbytes\tlines_or_objects\n'
  printf 'acir\t%s\t%s\n' "$(wc -c < "${build_root}/model.mlir")" \
    "$(wc -l < "${build_root}/model.mlir")"
  printf 'frozen\t%s\t%s\n' "$(wc -c < "${build_root}/model.frozen.mlir")" \
    "$(wc -l < "${build_root}/model.frozen.mlir")"
  printf 'optimized\t%s\t%s\n' "$(wc -c < "${build_root}/model.optimized.mlir")" \
    "$(wc -l < "${build_root}/model.optimized.mlir")"
  printf 'acsim\t%s\t%s\n' "$(wc -c < "${build_root}/model.acsim.mlir")" \
    "$(wc -l < "${build_root}/model.acsim.mlir")"
  printf 'generated-cxx\t%s\t%s\n' "${generated_bytes}" "${generated_lines}"
  printf 'generated-objects\t0\t%s\n' "${#generated_objects[@]}"
} > "${build_root}/sizes.tsv"

cat "${build_root}/semantic-1.txt"
cat "${build_root}/benchmark.txt"
echo "M1 acceptance passed"
echo "timing: ${metrics}"
echo "sizes: ${build_root}/sizes.tsv"
