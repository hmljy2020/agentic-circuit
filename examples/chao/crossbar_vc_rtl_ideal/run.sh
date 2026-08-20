#!/usr/bin/env bash
set -euo pipefail

ulimit -v 1900000

example_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${example_root}/../../.." && pwd)"
model_name="model.mlir"
build_name="build-rtl-ideal"
if [[ $# -ne 0 ]]; then
  echo "usage: $0" >&2
  exit 2
fi
build_root="${example_root}/${build_name}"

if [[ "${build_root}" != "${example_root}/${build_name}" ||
      "${build_name}" != build-* || -L "${build_root}" ]]; then
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
  "${example_root}/${model_name}" -o "${build_root}/model.frozen.mlir"

"${repo_root}/build/dev-llvm22/bin/acir-opt" --ac-lower-to-acsim \
  --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu \
  "${build_root}/model.frozen.mlir" -o "${build_root}/model.acsim.mlir"

out_root="${build_root}/generated"
"${repo_root}/build/dev-llvm22/bin/acir-cxxgen" \
  "${build_root}/model.acsim.mlir" --stop-after=model-plan \
  > "${build_root}/model-plan.txt"

"${repo_root}/build/dev-llvm22/bin/acir-cxxgen" \
  "${build_root}/model.acsim.mlir" --stop-after=link \
  --output-root="${out_root}" \
  --project-name=chao-crossbar-vc --project-identity=project.chao.crossbar_vc \
  --system-name=crossbar_vc_demo --system-identity=system.crossbar_vc_demo \
  --profile=fast --compiler=/usr/bin/c++ --standard-library=libstdc++ \
  --abi-mode=default --object-format=elf --contract-flag=-std=c++20 \
  --include-root="${repo_root}/include" \
  --link-input="${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" \
  --link-input="${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" \
  --linker-flag=-L/usr/lib/llvm-22/lib --linker-flag=-lLLVM

generated_objects=()
while IFS= read -r object; do
  if [[ "${object}" != *_main_cpp.o ]]; then
    generated_objects+=("${object}")
  fi
done < <(find "${out_root}/obj" -maxdepth 1 -type f -name '*.o' | sort)

# model + 1 module + 5 processes (producer0, producer1, scheduler, sink0, sink1).
if [[ ${#generated_objects[@]} -ne 7 ]]; then
  echo "unexpected generated object set (${#generated_objects[@]} objects)" >&2
  exit 1
fi

/usr/bin/c++ -std=c++20 -I"${out_root}/include" \
  -I"${repo_root}/include" -I/usr/lib/llvm-22/include \
  "${example_root}/runner.cpp" "${generated_objects[@]}" \
  "${repo_root}/build/dev-llvm22/lib/gfsim/libgfsim.a" \
  "${repo_root}/build/dev-llvm22/lib/Bindings/libACIRBindings.a" \
  -L/usr/lib/llvm-22/lib -lLLVM -o "${out_root}/bin/crossbar-demo"

# Test 8 (determinism): the binary must produce byte-identical output across
# two runs of the same input.
"${out_root}/bin/crossbar-demo" > "${out_root}/run1.txt"
"${out_root}/bin/crossbar-demo" > "${out_root}/run2.txt"
diff -u "${out_root}/run1.txt" "${out_root}/run2.txt"
cat "${out_root}/run1.txt"
