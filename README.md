# Compiler Error Message Fuzzer and Quality Benchmark

This project builds a small benchmark for something programmers feel every day: how useful is a compiler error message?

Compilers are usually compared on speed, optimization, and standards support. This benchmark compares them on diagnostics. It takes valid C and Fortran programs, injects common mistakes, runs the broken programs through multiple compilers, and scores the error messages for accuracy, location, clarity, and usefulness.

## What It Supports

Languages:

- C
- Fortran

Compilers:

- GCC for C
- Clang for C
- gfortran for Fortran
- Flang / `flang-new` for Fortran

The project is designed for Linux. It does not depend on one specific distribution. On Ubuntu, Debian, Fedora, Arch, or similar systems, install Python 3 plus whichever compilers are available from your package manager.

## Repository Layout

```text
.
├── README.md
├── DESIGN.md
├── IMPLEMENTATION.md
├── EVALUATION.md
├── build.sh
├── run.sh
├── src/
│   └── compiler_benchmark/
├── testcases/
│   ├── c/
│   └── fortran/
├── reports/
└── demo/
    └── screenshots/
```

## Quick Start

Build/check the project:

```bash
chmod +x build.sh run.sh
./build.sh
```

Run the full benchmark:

```bash
./run.sh
```

The main outputs are:

```text
reports/benchmark_report.md
reports/benchmark_report.json
reports/benchmark_scores.csv
```

## Running Individual Parts

List available mutations for a C file:

```bash
python3 error_injection_engine.py testcases/c/basic_mixed.c --list
```

Inject one mutation:

```bash
python3 error_injection_engine.py testcases/c/basic_mixed.c --mutations C01 --output-dir reports
```

Run compilers on a mutated file:

```bash
python3 compiler_harness.py reports/basic_mixed_mutated.c
```

Extract features:

```bash
python3 feature_extractor.py testcases/c/basic_mixed.c testcases/fortran/basic_subroutine.f90
```

## Mutation Coverage

The benchmark currently includes:

- 24 C mutation categories
- 22 Fortran mutation categories
- 11 valid sample programs under `testcases/`

Examples include missing semicolons, type mismatches, undeclared variables, wrong argument counts, pointer mistakes, bad format strings, missing `END IF`, wrong subroutine calls, malformed literals, and declarations after executable statements.

## Scoring

The scorer gives each compiler diagnostic a score from 0 to 100 using fuzzy logic. The inputs are:

- diagnosis accuracy
- source location precision
- severity correctness
- fix-it/helpfulness
- explanation clarity
- signal-to-noise

This is fuzzy rather than binary because real compiler messages are often partly useful. A message can point to the right line but explain the wrong concept, or identify the right concept but give no repair hint. For Clang, the harness also captures parseable fix-it suggestions and checks whether the suggested source range is close to the injected mistake.

The scorer uses a Mamdani-style fuzzy approach. Each metric is normalized to 0.0-1.0, mapped into low/medium/high memberships, evaluated through fuzzy rules, and defuzzified into a final 0-100 score.

## Documentation

- [DESIGN.md](DESIGN.md): architecture, alternatives, and why the project is structured this way
- [IMPLEMENTATION.md](IMPLEMENTATION.md): module-by-module implementation details
- [EVALUATION.md](EVALUATION.md): metrics, test cases, baseline comparison, and expected report interpretation

## Notes for Evaluation

If a compiler is not installed, the benchmark does not crash. It records the compiler as unavailable and gives it a score of zero for that run. This is intentional because the report should be honest about the environment.

For the strongest demo, run this on Linux with all four compilers installed, then include screenshots of:

- `./build.sh`
- `./run.sh`
- `reports/benchmark_report.md`
- one generated mutated source file
- one missing-compiler failure case, if applicable
