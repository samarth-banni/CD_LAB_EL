# Implementation

This document explains how the project is implemented and where to look in the code.

## Source Layout

```text
src/compiler_benchmark/
├── benchmark.py
├── compiler_harness.py
├── feature_extractor.py
├── models.py
├── mutations.py
└── scorer.py
```

The root-level Python files are small wrappers. They add `src/` to the Python path and call the actual package modules.

## Data Models

File: `src/compiler_benchmark/models.py`

Important models:

- `MutationRecord`: what mistake was injected, where it happened, and what keywords are expected in a good diagnostic
- `MutationResult`: full result of mutation generation
- `Diagnostic`: normalized compiler diagnostic
- `CompilerResult`: result of running one compiler

These models make the rest of the code easier to connect because every stage passes structured data instead of raw strings.

## Mutation Engine

File: `src/compiler_benchmark/mutations.py`

The mutation engine:

1. Detects the language from the file extension.
2. Selects mutations for that language.
3. Applies each mutation using a small targeted transformation.
4. Writes the mutated source file.
5. Writes a JSON injection report.

Examples:

- `C01`: remove a semicolon
- `C05`: assign a string to an integer
- `C13`: change the number of function arguments
- `F01`: delete `END IF`
- `F14`: assign to an `INTENT(IN)` argument
- `F21`: insert a declaration after an executable statement

Each mutation also stores expected diagnostic keywords. These keywords are later used by the fuzzy scorer.

## Compiler Harness

File: `src/compiler_benchmark/compiler_harness.py`

The harness supports:

- `gcc`
- `clang`
- `gfortran`
- `flang-new` / `flang`

It checks whether each compiler is installed. If a compiler is missing, the report records it as unavailable instead of failing the entire benchmark.

Compiler commands use syntax-only style flags where possible:

```bash
gcc -std=c11 -Wall -Wextra -Wpedantic -Wconversion -fsyntax-only file.c
clang -std=c11 -Wall -Wextra -Wpedantic -Wconversion -fsyntax-only file.c
gfortran -std=f2008 -Wall -Wextra -Wconversion -fsyntax-only file.f90
flang-new -fsyntax-only file.f90
```

For Clang, the actual harness also enables `-fdiagnostics-parseable-fixits` so machine-readable fix-it suggestions can be captured and scored. The project says “Flang” because LLVM Flang is commonly exposed as `flang-new` on many Linux systems. The harness tries several names because package naming differs across distributions.

## Diagnostic Parsing

The diagnostic parser handles common compiler output styles.

GCC/Clang style:

```text
file.c:10:5: error: expected ';'
```

gfortran style:

```text
file.f90:4:20:

  integer :: value = "hello"
                   1
Error: Can't convert CHARACTER(1) to INTEGER(4) at (1)
```

The parser turns both into a normalized `Diagnostic` object with file, line, column, severity, and message.

## Fuzzy Scorer

File: `src/compiler_benchmark/scorer.py`

The scorer compares a compiler diagnostic against the known injected mutation.

It calculates six input values:

| Input | Description |
|---|---|
| diagnosis | Does the message match the expected error category? |
| location | Is the line number close to the injected mutation line? |
| severity | Is error/warning classification appropriate? |
| fixit | Is there repair guidance or a fix-it style suggestion? |
| clarity | Is the message specific and understandable? |
| signal | Is the useful diagnostic early and not buried in noise? |

Those values are fuzzified into low, medium, and high membership values. Then rules produce an output quality level such as weak, fair, good, or excellent. The final output is a 0-100 score.

For fix-it validity, the scorer gives the strongest credit to parseable fix-it ranges that point near the injected mutation line. Vague text like “did you mean” still receives some credit, but less than a structured fix-it that identifies a source range.

## Benchmark Runner

File: `src/compiler_benchmark/benchmark.py`

The full benchmark:

1. Reads each source file.
2. Generates one mutated file per mutation.
3. Runs the relevant compilers.
4. Scores each compiler diagnostic.
5. Aggregates by compiler and category.
6. Writes JSON, CSV, and Markdown reports.

Main command:

```bash
./run.sh
```

## Scripts

`build.sh` checks:

- Python availability
- compiler availability
- Python syntax
- required folders

`run.sh` runs the benchmark over the included test cases.

Both scripts are Linux shell scripts and are intended to be run from the repository root.
