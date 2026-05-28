#!/usr/bin/env python3
"""Compatibility wrapper for the language-aware mutation engine."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from compiler_benchmark.mutations import main


if __name__ == "__main__":
    main()
