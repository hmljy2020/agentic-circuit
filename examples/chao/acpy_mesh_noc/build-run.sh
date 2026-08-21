#!/usr/bin/env bash
set -euo pipefail

ulimit -v 1900000
example_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${example_root}/../../.." && pwd)"
build_root="${example_root}/build-noc"
if [[ "${build_root}" != "${example_root}/build-noc" || -L "${build_root}" ]]; then
  echo "unsafe build directory: ${build_root}" >&2
  exit 1
fi
if [[ -d "${build_root}" ]]; then rm -rf -- "${build_root}"; fi
mkdir -p -- "${build_root}"

(
  cd -- "${example_root}"
  PYTHONPATH="${repo_root}/src:${repo_root}/build/dev-llvm22/python" \
    python -m agentic_circuit._cli elaborate model.py \
    --system main -o "${build_root}/model.ac.mlir"
)
"${repo_root}/build/dev-llvm22/bin/acir-opt" --verify-each=false \
  --pass-pipeline='builtin.module(ac-freeze-topology)' \
  "${build_root}/model.ac.mlir" -o "${build_root}/model.frozen.mlir"
"${repo_root}/build/dev-llvm22/bin/acir-opt" --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  "${build_root}/model.frozen.mlir" -o "${build_root}/model.acsim.mlir"

out_root="${build_root}/generated"
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

mapfile -t objects < <(find "${out_root}/obj" -maxdepth 1 -type f -name '*.o' ! -name '*_main_cpp.o' | sort)
/usr/bin/c++ -std=c++20 -I"${out_root}/include" -I"${repo_root}/include" \
  -I/usr/lib/llvm-22/include "${example_root}/runner.cpp" "${objects[@]}" \
  "${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" \
  "${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" \
  -L/usr/lib/llvm-22/lib -lLLVM -o "${out_root}/bin/mesh-noc"
"${out_root}/bin/mesh-noc"
