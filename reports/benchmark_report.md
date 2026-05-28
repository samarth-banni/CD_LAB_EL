# Compiler Diagnostic Quality Benchmark Report

Generated: 2026-05-28T22:57:39

## Overall Scores

| Compiler | Language | Average Score | Availability |
|---|---:|---:|---:|
| gfortran | fortran | 67.05 | 3/3 |
| gcc | c | 50.38 | 4/4 |
| clang | c | 0.0 | 0/4 |
| flang | fortran | 0.0 | 0/3 |

## Weak Spots

### basic_mixed.c
- **gcc**
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `format` scored 0.0: Pair each printf/format specifier with the actual argument type.
  - Category `scope` scored 18.33: Include the unresolved identifier and nearest similar declarations when possible.
  - Mutation `C02` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C09` scored 0.0: Use keywords that describe the real mistake category, not only the parser symptom.
- **clang**
  - Category `array` scored 0.0: Report declared rank/size and the offending index or initializer count.
  - Category `control-flow` scored 0.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Mutation `C01` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C02` scored 0.0: Reduce noise and improve the first diagnostic for this category.

### functions_arrays.c
- **gcc**
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `format` scored 0.0: Pair each printf/format specifier with the actual argument type.
  - Category `scope` scored 27.5: Include the unresolved identifier and nearest similar declarations when possible.
  - Mutation `C02` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C09` scored 0.0: Use keywords that describe the real mistake category, not only the parser symptom.
- **clang**
  - Category `array` scored 0.0: Report declared rank/size and the offending index or initializer count.
  - Category `control-flow` scored 0.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Mutation `C01` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C02` scored 0.0: Reduce noise and improve the first diagnostic for this category.

### pointers_structs.c
- **gcc**
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `format` scored 0.0: Pair each printf/format specifier with the actual argument type.
  - Category `include` scored 35.0: Make the diagnostic more specific, local, and action-oriented.
  - Mutation `C11` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C14` scored 0.0: Reduce noise and improve the first diagnostic for this category.
- **clang**
  - Category `control-flow` scored 0.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `format` scored 0.0: Pair each printf/format specifier with the actual argument type.
  - Mutation `C01` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C03` scored 0.0: Reduce noise and improve the first diagnostic for this category.

### control_flow.c
- **gcc**
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `format` scored 0.0: Pair each printf/format specifier with the actual argument type.
  - Category `scope` scored 27.5: Include the unresolved identifier and nearest similar declarations when possible.
  - Mutation `C02` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C09` scored 0.0: Use keywords that describe the real mistake category, not only the parser symptom.
- **clang**
  - Category `control-flow` scored 0.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Category `dataflow` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `format` scored 0.0: Pair each printf/format specifier with the actual argument type.
  - Mutation `C01` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `C02` scored 0.0: Reduce noise and improve the first diagnostic for this category.

### basic_subroutine.f90
- **gfortran**
  - Category `syntax` scored 42.66: Improve parser recovery and mention the exact missing or mismatched token.
  - Category `literal` scored 49.8: Make the diagnostic more specific, local, and action-oriented.
  - Category `control-flow` scored 53.7: Point to the unmatched block opener and the statement that closes or escapes it.
  - Mutation `F12` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `F01` scored 35.0: Prioritize the injected line or nearest syntax construct instead of a later cascade error.
- **flang**
  - Category `argument` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `array` scored 0.0: Report declared rank/size and the offending index or initializer count.
  - Category `control-flow` scored 0.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Mutation `F01` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `F02` scored 0.0: Reduce noise and improve the first diagnostic for this category.

### arrays_control.f90
- **gfortran**
  - Category `syntax` scored 17.6: Improve parser recovery and mention the exact missing or mismatched token.
  - Category `type` scored 63.57: Name both expected and actual types, then show the expression that caused conversion.
  - Category `declaration` scored 67.97: Make the diagnostic more specific, local, and action-oriented.
  - Mutation `F12` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `F08` scored 35.0: Prioritize the injected line or nearest syntax construct instead of a later cascade error.
- **flang**
  - Category `array` scored 0.0: Report declared rank/size and the offending index or initializer count.
  - Category `control-flow` scored 0.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Category `declaration` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Mutation `F01` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `F02` scored 0.0: Reduce noise and improve the first diagnostic for this category.

### procedures_intrinsics.f90
- **gfortran**
  - Category `control-flow` scored 35.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Category `syntax` scored 42.66: Improve parser recovery and mention the exact missing or mismatched token.
  - Category `literal` scored 49.8: Make the diagnostic more specific, local, and action-oriented.
  - Mutation `F12` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `F01` scored 35.0: Prioritize the injected line or nearest syntax construct instead of a later cascade error.
- **flang**
  - Category `argument` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Category `control-flow` scored 0.0: Point to the unmatched block opener and the statement that closes or escapes it.
  - Category `declaration` scored 0.0: Make the diagnostic more specific, local, and action-oriented.
  - Mutation `F01` scored 0.0: Reduce noise and improve the first diagnostic for this category.
  - Mutation `F02` scored 0.0: Reduce noise and improve the first diagnostic for this category.
