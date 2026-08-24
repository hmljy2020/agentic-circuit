#!/usr/bin/env bash
set -euo pipefail
ulimit -v 1900000

example_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${example_root}/../../../.." && pwd)"
build_root="${example_root}/build-host"
if [[ "${build_root}" != "${example_root}/build-host" || -L "${build_root}" ]]; then exit 1; fi
if [[ -d "${build_root}" ]]; then rm -rf -- "${build_root}"; fi
mkdir -p -- "${build_root}"

run_stage() {
  local label="$1"; shift
  local start="${EPOCHREALTIME/./}" rc=0 end
  "$@" || rc=$?
  end="${EPOCHREALTIME/./}"
  printf 'timing stage=%s status=%s elapsed_us=%d\n' "${label}" "$([[ ${rc} -eq 0 ]] && printf passed || printf failed)" "$((end-start))"
  return "${rc}"
}

elaborate() { cd -- "${example_root}" && PYTHONPATH="${repo_root}/src:${repo_root}/build/dev-llvm22/python" python -m agentic_circuit._cli elaborate model.py --system main -o "${build_root}/model.ac.mlir"; }
freeze() { "${repo_root}/build/dev-llvm22/bin/acir-opt" --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' "${build_root}/model.ac.mlir" -o "${build_root}/model.frozen.mlir"; }
lower() { "${repo_root}/build/dev-llvm22/bin/acir-opt" --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu "${build_root}/model.frozen.mlir" -o "${build_root}/model.acsim.mlir"; }
generate() { "${repo_root}/build/dev-llvm22/bin/acir-cxxgen" "${build_root}/model.acsim.mlir" --stop-after=link --output-root="${build_root}/generated" --project-name=acpy-mesh-host --project-identity=project.chao.acpy-mesh-host --system-name=mesh_host --system-identity=system.chao.mesh-host --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --compiler-flag=-fPIC --include-root="${repo_root}/include" --link-input="${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" --link-input="${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM; }
shared() { local objects=(); mapfile -t objects < <(find "${build_root}/generated/obj" -maxdepth 1 -type f -name '*.o' ! -name '*_main_cpp.o' | sort); /usr/bin/c++ -shared "${objects[@]}" "${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" "${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" -L/usr/lib/llvm-22/lib -lLLVM -o "${build_root}/generated/bin/libmodel.so"; }
smoke() { PYTHONPATH="${repo_root}/src" python "${example_root}/benchmark.py" "${build_root}/generated/bin/libmodel.so" --rates=0.1,0.5,1.0 --seeds=1 --warmup=20 --measure=100 --output="${build_root}/saturation.csv"; }

run_stage elaborate elaborate
run_stage freeze freeze
run_stage lower lower
run_stage cxxgen-link generate
run_stage shared-link shared
run_stage benchmark-smoke smoke
cat "${build_root}/saturation.csv"
