#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "[build] Compiler Error Message Fuzzer"
echo "[build] Checking Python..."
python3 --version

echo "[build] Checking optional compilers..."
for tool in gcc clang gfortran flang-new flang; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  found: $tool -> $($tool --version 2>&1 | head -n 1)"
  else
    echo "  missing: $tool"
  fi
done

echo "[build] Checking Python source syntax..."
PYTHONPATH="$ROOT_DIR/src" python3 -m compileall -q src benchmark_runner.py compiler_harness.py error_injection_engine.py feature_extractor.py

mkdir -p reports demo/screenshots
echo "[build] Build check completed."
