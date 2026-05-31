#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

mkdir -p reports

echo "[run] Running compiler diagnostic benchmark..."
PYTHONPATH="$ROOT_DIR/src" python3 benchmark_runner.py \
  testcases/c/basic_mixed.c \
  testcases/c/functions_arrays.c \
  testcases/c/pointers_structs.c \
  testcases/c/control_flow.c \
  testcases/c/strings_memory.c \
  testcases/c/preprocessor_typedefs.c \
  testcases/fortran/basic_subroutine.f90 \
  testcases/fortran/arrays_control.f90 \
  testcases/fortran/procedures_intrinsics.f90 \
  testcases/fortran/modules_kinds.f90 \
  testcases/fortran/io_select_case.f90 \
  --output-dir reports \
  --mutations all

echo
echo "[run] Main outputs:"
echo "  reports/benchmark_report.md"
echo "  reports/benchmark_report.json"
echo "  reports/benchmark_scores.csv"
