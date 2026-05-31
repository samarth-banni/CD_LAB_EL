# Design

The goal of this project is not only to break programs. The real goal is to measure how well compilers explain broken programs.

The benchmark follows this pipeline:

```text
valid source program
        |
        v
feature extractor
        |
        v
mutation engine
        |
        v
one isolated broken file per mutation
        |
        v
compiler harness
        |
        v
diagnostic parser
        |
        v
fuzzy scorer
        |
        v
benchmark report + weak spots
```

## Main Design Choices

### 1. Isolated Mutation Cases

The benchmark creates one broken file for each mutation instead of injecting every error into one file.

This matters because compilers often produce cascaded errors. If a missing brace appears early in a file, later diagnostics may be side effects. Scoring all of those together would be unfair. Isolating each mutation makes the comparison cleaner.

### 2. Language-Aware Mutation Catalogs

C and Fortran have different kinds of mistakes. The project uses separate mutation catalogs:

- C mutations: semicolons, pointers, structs, format strings, function calls, array initializers
- Fortran mutations: `END IF`, `END DO`, subroutine arguments, `INTENT(IN)`, modules, implicit typing

This keeps the benchmark realistic instead of forcing every language into the same error model.

### 3. Unified Compiler Result Model

Different compilers print diagnostics differently. GCC and Clang usually use:

```text
file:line:column: error: message
```

gfortran often prints:

```text
file:line:column:

source line
        1
Error: message at (1)
```

Flang has its own style too. Internally, the harness converts all of these into the same structure:

```json
{
  "file": "example.c",
  "line": 12,
  "column": 7,
  "severity": "error",
  "message": "expected ';' after expression"
}
```

That unified shape makes scoring possible.

### 4. Mamdani-Style Fuzzy Scoring Instead of Hard Rules

Diagnostic quality is not yes/no.

For example:

- A message with the correct line but vague wording is partly useful.
- A message with a good explanation but a line number five lines away is also partly useful.
- A compiler may give no explicit fix-it but still clearly say what is wrong.

Because of that, the scorer uses Mamdani-style fuzzy inference rather than a single hard threshold. It is Mamdani-style because each input is converted into linguistic membership values, rules infer linguistic output qualities, and the final numeric score is obtained by defuzzifying those output qualities.

The scorer does not use a Takagi-Sugeno model. It does not assign each rule a linear equation such as `a*x + b*y + c`. Instead, each active rule contributes to one of five output quality labels:

- `poor`
- `weak`
- `fair`
- `good`
- `excellent`

The six input variables are:

- diagnosis accuracy
- source location precision
- severity correctness
- fix-it/helpfulness
- explanation clarity
- signal-to-noise

Each input is normalized to the range 0.0 to 1.0 and assigned to three fuzzy sets:

| Membership | Shape | Range behavior |
|---|---|---|
| low | left-shoulder | Full membership at 0.25 or below, falling to zero by 0.45 |
| medium | triangular | Starts at 0.25, peaks at 0.55, falls to zero by 0.80 |
| high | right-shoulder | Starts at 0.65, reaches full membership by 0.90 |

Rules combine memberships using `min` for AND-like conditions and `max` for OR-like conditions. For example, a diagnostic with high diagnosis accuracy, high location precision, and high clarity activates an excellent-quality rule. A diagnostic with low diagnosis or low location activates a weak-quality rule.

The output labels are converted into numeric centers:

| Output quality | Center |
|---|---:|
| poor | 15 |
| weak | 35 |
| fair | 55 |
| good | 75 |
| excellent | 92 |

The final diagnostic quality score is the weighted average of the active output centers, using each rule's activation strength as the weight. This produces the final 0-100 score.

## Alternatives Considered

### Regex Mutation vs AST Mutation

An AST-based mutator would be more precise, especially for large projects. But it would also require language-specific parser dependencies and more setup for evaluators.

For this assignment, the project uses careful regex-based mutations over small benchmark programs. This keeps the project easy to run on Linux with only Python and compilers installed.

### Single Broken Program vs Many Broken Programs

One big broken program is faster to generate, but it creates noisy cascaded diagnostics. The project uses many small broken programs because the benchmark should measure the compiler's response to one known mistake at a time.

### Compiler-Specific Scores vs Unified Score

Compiler-specific scoring could account for every detail of GCC, Clang, gfortran, and Flang. The downside is that the benchmark would become hard to compare.

This project uses one common score model for all compilers. Compiler-specific parsing happens only before scoring.

## Why This Design Fits the Assignment

The assignment asks for:

- error injection
- multiple compilers
- diagnostic quality scoring
- benchmark comparison
- weak spots and suggestions

The design maps directly to those deliverables while staying simple enough to run from `./build.sh` and `./run.sh`.
