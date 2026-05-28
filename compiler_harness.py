#!/usr/bin/env python3
"""Compatibility wrapper for the multi-compiler harness."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from compiler_benchmark.compiler_harness import main


if __name__ == "__main__":
    main()
