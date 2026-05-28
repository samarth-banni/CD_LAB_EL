#!/usr/bin/env python3
"""Run the full Assignment 40 benchmark pipeline."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from compiler_benchmark.benchmark import main


if __name__ == "__main__":
    main()
