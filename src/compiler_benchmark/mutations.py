from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .models import MutationRecord, MutationResult, language_for_path, mutated_path_for

Lines = list[str]
MutationFn = Callable[[Lines, random.Random], tuple[Lines | None, MutationRecord | None]]


@dataclass(frozen=True)
class MutationSpec:
    mutation_id: str
    language: str
    category: str
    title: str
    expected_keywords: list[str]
    fix_hint: str
    fn: MutationFn


def _body(line: str) -> str:
    return line.rstrip("\n")


def _nl(line: str) -> str:
    return "\n" if line.endswith("\n") else ""


def _replace(lines: Lines, idx: int, text: str) -> Lines:
    out = lines[:]
    out[idx] = text + _nl(lines[idx])
    return out


def _record(
    spec: MutationSpec,
    idx: int,
    original: str,
    mutated: str,
    column: int | None = None,
    severity: str = "error",
) -> MutationRecord:
    return MutationRecord(
        mutation_id=spec.mutation_id,
        language=spec.language,
        category=spec.category,
        title=spec.title,
        line=idx + 1,
        column=column,
        original_code=original.rstrip("\n"),
        mutated_code=mutated.rstrip("\n"),
        expected_keywords=spec.expected_keywords,
        fix_hint=spec.fix_hint,
        severity=severity,
    )


def _choice(rng: random.Random, items: list[int]) -> int | None:
    return rng.choice(items) if items else None


def _not_comment(line: str) -> bool:
    return not line.strip().startswith(("//", "/*", "*", "#"))


def _c_statement_candidates(lines: Lines) -> list[int]:
    return [
        i
        for i, line in enumerate(lines)
        if _not_comment(line)
        and _body(line).rstrip().endswith(";")
        and not re.match(r"\s*(for|while|if|switch)\b", line)
    ]


def c_missing_semicolon(spec: MutationSpec, lines: Lines, rng: random.Random):
    idx = _choice(rng, _c_statement_candidates(lines))
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = _body(original).rstrip()[:-1]
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], len(mutated))


def c_extra_semicolon(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if _not_comment(l) and re.search(r"\b(if|for|while)\s*\(", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = _body(original) + ";"
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], len(mutated), "warning")


def c_missing_closing_brace(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if _body(l).strip() == "}"]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    out = lines[:]
    original = out.pop(idx)
    return out, _record(spec, idx, original, "<line deleted>")


def c_mismatched_parenthesis(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if ")" in l and _not_comment(l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = _body(original).replace(")", "]", 1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("]") + 1)


def c_type_mismatch_assignment(spec: MutationSpec, lines: Lines, rng: random.Random):
    patterns = [
        (re.compile(r"^(\s*)int\s+(\w+)\s*=\s*[-+]?\d+\s*;"), r'\1int \2 = "hello";'),
        (re.compile(r"^(\s*)char\s*\*\s*(\w+)\s*=\s*\"[^\"]*\"\s*;"), r"\1char *\2 = 42;"),
        (re.compile(r"^(\s*)double\s+(\w+)\s*=\s*[-+]?\d+(\.\d+)?\s*;"), r'\1double \2 = "text";'),
    ]
    cands: list[tuple[int, re.Pattern[str], str]] = []
    for i, line in enumerate(lines):
        for pat, repl in patterns:
            if pat.search(line):
                cands.append((i, pat, repl))
    if not cands:
        return None, None
    idx, pat, repl = rng.choice(cands)
    original = lines[idx]
    mutated = pat.sub(repl, _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("=") + 2)


def c_invalid_pointer_assignment(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [
        i for i, l in enumerate(lines)
        if re.search(r"\b(?:int|char|float|double)\s*\*\s*\w+\s*=\s*&", l)
    ]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = _body(original).replace("&", "", 1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("=") + 2)


def c_wrong_return_type(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*return\s+[^;]+;", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"return\s+[^;]+;", 'return "wrong";', _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("return") + 1)


def c_incompatible_argument_type(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [
        i for i, l in enumerate(lines)
        if re.search(r"\b\w+\s*\([^)]*\b\d+\b[^)]*\)\s*;", l)
        and not re.search(r"\b(printf|scanf|fprintf)\s*\(", l)
    ]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\b\d+\b", '"hello"', _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find('"hello"') + 1)


def c_undeclared_variable(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [
        i for i, l in enumerate(lines)
        if re.search(r"\b([a-zA-Z_]\w*)\s*=", l)
        and not re.match(r"\s*(int|float|double|char|long|short|unsigned|struct)\b", l)
        and _not_comment(l)
    ]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\b([a-zA-Z_]\w*)\s*=", r"missing_\1 =", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("missing_") + 1)


def c_redeclaration(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*(int|float|double|char)\s+\w+(\s*=.+)?;", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    out = lines[: idx + 1] + [original] + lines[idx + 1 :]
    return out, _record(spec, idx + 1, "<line inserted>", original)


def c_use_before_initialization(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = []
    pat = re.compile(r"^(\s*)(int|float|double|char)\s+(\w+)\s*=\s*(.+);")
    for i, line in enumerate(lines):
        if pat.match(line):
            cands.append(i)
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    match = pat.match(original)
    assert match is not None
    indent, dtype, var, value = match.groups()
    inserted = [f"{indent}{dtype} {var};\n", f"{indent}printf(\"%d\", {var});\n", f"{indent}{var} = {value};\n"]
    out = lines[:idx] + inserted + lines[idx + 1 :]
    return out, _record(spec, idx + 1, original, inserted[1], inserted[1].find(var) + 1, "warning")


def c_out_of_scope(spec: MutationSpec, lines: Lines, rng: random.Random):
    for i, line in enumerate(lines):
        match = re.match(r"\s*(for|if|while)\s*\(.*\)\s*\{", line)
        if not match:
            continue
        for j in range(i + 1, min(i + 8, len(lines))):
            decl = re.match(r"\s*int\s+(\w+)\s*=", lines[j])
            if decl:
                for k in range(j + 1, len(lines)):
                    if _body(lines[k]).strip() == "}":
                        use = f"    printf(\"%d\", {decl.group(1)});\n"
                        out = lines[: k + 1] + [use] + lines[k + 1 :]
                        return out, _record(spec, k + 1, "<line inserted>", use, use.find(decl.group(1)) + 1)
    return None, None


def c_wrong_argument_count(spec: MutationSpec, lines: Lines, rng: random.Random):
    skip = {"if", "for", "while", "switch", "return", "sizeof", "printf", "scanf"}
    cands = []
    pat = re.compile(r"\b([A-Za-z_]\w*)\s*\(([^();]*)\)\s*;")
    for i, line in enumerate(lines):
        m = pat.search(line)
        if m and m.group(1) not in skip and "," in m.group(2):
            cands.append(i)
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\(([^,]+),([^)]*)\)", r"(\1)", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("(") + 1)


def c_missing_return(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*return\s+[^;]+;", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    out = lines[:]
    original = out.pop(idx)
    return out, _record(spec, idx, original, "<line deleted>")


def c_call_non_function(spec: MutationSpec, lines: Lines, rng: random.Random):
    vars_seen = []
    for line in lines:
        m = re.match(r"\s*int\s+(\w+)\s*=", line)
        if m:
            vars_seen.append(m.group(1))
    if not vars_seen:
        return None, None
    var = rng.choice(vars_seen)
    cands = [i for i, l in enumerate(lines) if re.search(r"\b" + re.escape(var) + r"\b", l) and _not_comment(l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\b" + re.escape(var) + r"\b", f"{var}()", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find(f"{var}()") + 1)


def c_array_index_oob(spec: MutationSpec, lines: Lines, rng: random.Random):
    arrays: dict[str, int] = {}
    for line in lines:
        for m in re.finditer(r"\b\w+\s+(\w+)\s*\[(\d+)\]", line):
            arrays[m.group(1)] = int(m.group(2))
    cands = []
    for i, line in enumerate(lines):
        for name in arrays:
            if re.search(r"\b" + re.escape(name) + r"\s*\[\s*\d+\s*\]", line):
                cands.append((i, name))
    if not cands:
        return None, None
    idx, name = rng.choice(cands)
    original = lines[idx]
    mutated = re.sub(r"\b" + re.escape(name) + r"\s*\[\s*\d+\s*\]", f"{name}[{arrays[name]}]", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find(f"{name}[") + 1, "warning")


def c_array_initializer_overflow(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\w+\s+\w+\s*\[\s*\d+\s*\]\s*=\s*\{[^}]*\};", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = _body(original).replace("};", ", 999, 888};", 1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("999") + 1)


def c_assignment_in_condition(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\b(if|while)\s*\([^)]*==[^)]*\)", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = _body(original).replace("==", "=", 1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("=") + 1, "warning")


def c_invalid_operator(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\bfloat\s+\w+\s*=", l) or re.search(r"\bdouble\s+\w+\s*=", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"=\s*([^;]+);", r"= \1 % 2.0;", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("%") + 1)


def c_format_mismatch(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if "printf" in l and "%" in l]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"%[diu]", "%s", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("%s") + 1, "warning")


def c_missing_include(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*#include\s+<stdio\.h>", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    out = lines[:]
    original = out.pop(idx)
    return out, _record(spec, idx, original, "<line deleted>")


def c_const_assignment(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*int\s+(\w+)\s*=", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    m = re.match(r"(\s*)int\s+(\w+)\s*=", original)
    assert m is not None
    mutated_decl = re.sub(r"\bint\s+(\w+)\s*=", r"const int \1 =", _body(original), count=1)
    assign = f"{m.group(1)}{m.group(2)} = 7;"
    out = _replace(lines, idx, mutated_decl)
    out.insert(idx + 1, assign + "\n")
    return out, _record(spec, idx + 1, "<line inserted>", assign, assign.find("=") + 1)


def c_break_outside_loop(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*int\s+main\s*\(", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    insert_at = idx + 1
    line = "    break;\n"
    out = lines[:insert_at] + [line] + lines[insert_at:]
    return out, _record(spec, insert_at, "<line inserted>", line, 5)


def c_invalid_struct_member(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\.\w+\s*=", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\.\w+\s*=", ".missing_member =", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("missing_member") + 1)


def c_bad_cast_lvalue(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*int\s+\w+\s*=", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    m = re.match(r"\s*int\s+(\w+)\s*=", original)
    assert m is not None
    inserted = f"    (float){m.group(1)} = 3.0;\n"
    out = lines[: idx + 1] + [inserted] + lines[idx + 1 :]
    return out, _record(spec, idx + 1, "<line inserted>", inserted, inserted.find("=") + 1)


def c_preprocessor_error(spec: MutationSpec, lines: Lines, rng: random.Random):
    idx = 0
    inserted = "#if defined(\n"
    out = [inserted] + lines
    return out, _record(spec, idx, "<line inserted>", inserted, 5)


def _wrap(fn):
    return lambda spec, lines, rng: fn(spec, lines, rng)


def _mk(
    mid: str,
    language: str,
    category: str,
    title: str,
    keywords: list[str],
    fix: str,
    fn,
) -> MutationSpec:
    return MutationSpec(mid, language, category, title, keywords, fix, _wrap(fn))


C_MUTATIONS: list[MutationSpec] = [
    _mk("C01", "c", "syntax", "Missing semicolon", ["semicolon", "expected", ";"], "Restore the semicolon at the end of the statement.", c_missing_semicolon),
    _mk("C02", "c", "syntax", "Extra semicolon after control statement", ["empty body", "semicolon", "warning"], "Remove the stray semicolon after the control condition.", c_extra_semicolon),
    _mk("C03", "c", "syntax", "Missing closing brace", ["expected", "brace", "}"], "Restore the deleted closing brace.", c_missing_closing_brace),
    _mk("C04", "c", "syntax", "Mismatched parenthesis/bracket", ["expected", ")", "]", "bracket"], "Use the matching closing parenthesis.", c_mismatched_parenthesis),
    _mk("C05", "c", "type", "Type mismatch assignment", ["incompatible", "integer", "pointer", "conversion"], "Use a value whose type matches the declared variable.", c_type_mismatch_assignment),
    _mk("C06", "c", "pointer", "Invalid pointer assignment", ["pointer", "integer", "incompatible"], "Assign an address to a pointer or change the variable type.", c_invalid_pointer_assignment),
    _mk("C07", "c", "type", "Wrong return type", ["return", "pointer", "integer", "incompatible"], "Return a value compatible with the function return type.", c_wrong_return_type),
    _mk("C08", "c", "function", "Incompatible argument type", ["argument", "parameter", "incompatible"], "Pass an argument with the parameter's expected type.", c_incompatible_argument_type),
    _mk("C09", "c", "scope", "Undeclared variable", ["undeclared", "identifier", "not declared"], "Declare the variable or correct the spelling.", c_undeclared_variable),
    _mk("C10", "c", "scope", "Redeclaration in same scope", ["redefinition", "redeclaration", "previous"], "Remove one declaration or use a different name.", c_redeclaration),
    _mk("C11", "c", "dataflow", "Use before initialization", ["uninitialized", "may be used"], "Initialize the variable before its first use.", c_use_before_initialization),
    _mk("C12", "c", "scope", "Out-of-scope variable usage", ["undeclared", "scope", "not declared"], "Move the use inside scope or declare a new variable.", c_out_of_scope),
    _mk("C13", "c", "function", "Wrong number of function arguments", ["too few", "too many", "arguments"], "Call the function with the declared number of arguments.", c_wrong_argument_count),
    _mk("C14", "c", "control-flow", "Missing return statement", ["return", "control reaches", "non-void"], "Return a value from every path of a non-void function.", c_missing_return),
    _mk("C15", "c", "function", "Calling a non-function variable", ["called object", "function", "not a function"], "Remove parentheses or call a real function.", c_call_non_function),
    _mk("C16", "c", "array", "Array index out of bounds", ["bounds", "array", "subscript"], "Use an index between 0 and size-1.", c_array_index_oob),
    _mk("C17", "c", "array", "Too many array initializer elements", ["excess", "initializer", "array"], "Match the number of initializer elements to the array size.", c_array_initializer_overflow),
    _mk("C18", "c", "logic", "Assignment instead of comparison", ["assignment", "truth value", "parentheses"], "Use == for comparison or extra parentheses for intentional assignment.", c_assignment_in_condition),
    _mk("C19", "c", "operator", "Invalid operator usage", ["invalid operands", "binary", "%"], "Use an operator valid for the operand types.", c_invalid_operator),
    _mk("C20", "c", "format", "Format string mismatch", ["format", "expects", "argument"], "Use a printf conversion matching the argument type.", c_format_mismatch),
    _mk("C21", "c", "include", "Missing required include", ["implicit", "declaration", "printf"], "Include the header declaring the function.", c_missing_include),
    _mk("C22", "c", "qualifier", "Assignment to const variable", ["read-only", "const", "assignment"], "Do not assign to const storage after initialization.", c_const_assignment),
    _mk("C23", "c", "control-flow", "Break outside loop or switch", ["break", "not within", "loop"], "Move break inside a loop/switch or remove it.", c_break_outside_loop),
    _mk("C24", "c", "structure", "Invalid struct member", ["member", "structure", "no member"], "Use an existing struct member name.", c_invalid_struct_member),
]


def f_missing_end_if(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*end\s+if\b", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    out = lines[:]
    original = out.pop(idx)
    return out, _record(spec, idx, original, "<line deleted>")


def f_type_mismatch(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*integer\s*::\s*\w+\s*=", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"=\s*[^!]+", '= "hello"', _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("=") + 1)


def f_undeclared_variable(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\w+\s*=", l) and not re.match(r"\s*(integer|real|character|logical)", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\b(\w+)\s*=", r"missing_\1 =", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("missing_") + 1)


def f_wrong_arg_count(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\bcall\s+\w+\s*\([^)]*,[^)]*\)", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\(([^,]+),[^)]*\)", r"(\1)", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("(") + 1)


def f_missing_then(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\bif\s*\(.*\)\s*then\b", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\s*then\b", "", _body(original), flags=re.I)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx])


def f_bad_array_rank(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\w+\s*\(\s*\d+\s*\)", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"(\w+)\s*\(\s*\d+\s*\)", r"\1(1, 1)", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("(1, 1)") + 1)


def f_character_length(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*character\(len=\d+\)\s*::\s*\w+\s*=", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"len=\d+", "len=1", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("len=1") + 1, "warning")


def f_missing_do_end(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*end\s+do\b", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    out = lines[:]
    original = out.pop(idx)
    return out, _record(spec, idx, original, "<line deleted>")


def f_invalid_operator(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\.and\.|\.or\.", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\.(and|or)\.", "+", _body(original), count=1, flags=re.I)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("+") + 1)


def f_redeclaration(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*(integer|real|character|logical).*::\s*\w+", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    out = lines[: idx + 1] + [original] + lines[idx + 1 :]
    return out, _record(spec, idx + 1, "<line inserted>", original)


def f_bad_intrinsic_arg(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\bsqrt\s*\(", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"sqrt\s*\([^)]*\)", 'sqrt("text")', _body(original), count=1, flags=re.I)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("sqrt") + 1)


def f_missing_program_end(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*end\s+program\b", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        cands = [i for i, l in enumerate(lines) if re.match(r"\s*end\s*$", l, re.I)]
        idx = _choice(rng, cands)
    if idx is None:
        return None, None
    out = lines[:]
    original = out.pop(idx)
    return out, _record(spec, idx, original, "<line deleted>")


def f_bad_literal(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\d+\.\d+", l)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\d+\.\d+", "1.2.3", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("1.2.3") + 1)


def f_assign_intent_in(spec: MutationSpec, lines: Lines, rng: random.Random):
    for i, line in enumerate(lines):
        m = re.match(r"\s*integer\s*,\s*intent\(in\)\s*::\s*(\w+)", line, re.I)
        if m:
            inserted = f"    {m.group(1)} = 99\n"
            out = lines[: i + 1] + [inserted] + lines[i + 1 :]
            return out, _record(spec, i + 1, "<line inserted>", inserted, inserted.find("=") + 1)
    return None, None


def f_wrong_end_name(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*end\s+subroutine\s+\w+", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"(end\s+subroutine\s+)\w+", r"\1wrong_name", _body(original), flags=re.I)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("wrong_name") + 1)


def f_array_constructor_type(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"integer\s*::\s*\w+\([^)]*\)\s*=\s*\[[^\]]+\]", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\[([^\]]+)\]", r'[\1, "text"]', _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find('"text"') + 1)


def f_modify_do_variable(spec: MutationSpec, lines: Lines, rng: random.Random):
    for i, line in enumerate(lines):
        m = re.match(r"\s*do\s+(\w+)\s*=", line, re.I)
        if m:
            inserted = f"     {m.group(1)} = 99\n"
            out = lines[: i + 1] + [inserted] + lines[i + 1 :]
            return out, _record(spec, i + 1, "<line inserted>", inserted, inserted.find("=") + 1)
    return None, None


def f_unknown_intrinsic(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\bsqrt\s*\(", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\bsqrt\s*\(", "sqrtt(", _body(original), count=1, flags=re.I)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("sqrtt") + 1)


def f_missing_contains(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*contains\s*$", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    out = lines[:]
    original = out.pop(idx)
    return out, _record(spec, idx, original, "<line deleted>")


def f_missing_module(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.match(r"\s*program\s+\w+", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    inserted = "  use missing_module\n"
    out = lines[: idx + 1] + [inserted] + lines[idx + 1 :]
    return out, _record(spec, idx + 1, "<line inserted>", inserted, inserted.find("missing_module") + 1)


def f_late_declaration(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\b(print|call)\b", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    inserted = "  integer :: late_var\n"
    out = lines[: idx + 1] + [inserted] + lines[idx + 1 :]
    return out, _record(spec, idx + 1, "<line inserted>", inserted, 3)


def f_relational_type_mismatch(spec: MutationSpec, lines: Lines, rng: random.Random):
    cands = [i for i, l in enumerate(lines) if re.search(r"\bif\s*\([^)]*==[^)]*\)\s*then", l, re.I)]
    idx = _choice(rng, cands)
    if idx is None:
        return None, None
    original = lines[idx]
    mutated = re.sub(r"\([^)]*==[^)]*\)", "(name == 10)", _body(original), count=1)
    out = _replace(lines, idx, mutated)
    return out, _record(spec, idx, original, out[idx], mutated.find("==") + 1)


FORTRAN_MUTATIONS: list[MutationSpec] = [
    _mk("F01", "fortran", "control-flow", "Missing END IF", ["end if", "expecting", "if"], "Restore the matching END IF.", f_missing_end_if),
    _mk("F02", "fortran", "type", "Integer assigned character literal", ["cannot convert", "integer", "character"], "Assign an integer value or change the variable type.", f_type_mismatch),
    _mk("F03", "fortran", "scope", "Undeclared variable", ["implicit", "no implicit type", "undeclared"], "Declare the variable or fix the spelling.", f_undeclared_variable),
    _mk("F04", "fortran", "function", "Wrong subroutine argument count", ["argument", "more actual", "missing"], "Call the subroutine with its declared arguments.", f_wrong_arg_count),
    _mk("F05", "fortran", "syntax", "Missing THEN in IF block", ["then", "syntax", "if"], "Add THEN to the block IF statement.", f_missing_then),
    _mk("F06", "fortran", "array", "Array rank mismatch", ["rank", "array", "subscript"], "Use the declared array rank.", f_bad_array_rank),
    _mk("F07", "fortran", "type", "Character length truncation", ["truncated", "character", "conversion"], "Use a large enough character length.", f_character_length),
    _mk("F08", "fortran", "control-flow", "Missing END DO", ["end do", "expecting", "do"], "Restore the matching END DO.", f_missing_do_end),
    _mk("F09", "fortran", "operator", "Invalid logical operator usage", ["operands", "logical", "operator"], "Use logical operators only with logical operands.", f_invalid_operator),
    _mk("F10", "fortran", "scope", "Redeclaration in same scope", ["already", "declared", "symbol"], "Remove the duplicate declaration.", f_redeclaration),
    _mk("F11", "fortran", "function", "Bad intrinsic argument type", ["argument", "sqrt", "real"], "Pass a numeric argument to the intrinsic.", f_bad_intrinsic_arg),
    _mk("F12", "fortran", "syntax", "Missing END PROGRAM", ["unexpected end", "end program", "expecting"], "Restore the END PROGRAM statement.", f_missing_program_end),
    _mk("F13", "fortran", "literal", "Malformed numeric literal", ["invalid", "real", "literal"], "Use a valid numeric literal.", f_bad_literal),
    _mk("F14", "fortran", "argument", "Assignment to INTENT(IN) dummy argument", ["intent", "in", "assignment"], "Do not assign to an INTENT(IN) dummy argument.", f_assign_intent_in),
    _mk("F15", "fortran", "syntax", "Wrong END SUBROUTINE name", ["expected", "subroutine", "wrong"], "Match the END SUBROUTINE name with the declaration.", f_wrong_end_name),
    _mk("F16", "fortran", "array", "Mixed-type array constructor", ["array constructor", "integer", "character"], "Use elements of a consistent type in the constructor.", f_array_constructor_type),
    _mk("F17", "fortran", "control-flow", "Modification of DO loop variable", ["loop variable", "do variable", "redefined"], "Do not assign to the active DO loop variable.", f_modify_do_variable),
    _mk("F18", "fortran", "function", "Unknown intrinsic/function call", ["implicit", "function", "no implicit type"], "Declare the function or correct the intrinsic name.", f_unknown_intrinsic),
    _mk("F19", "fortran", "syntax", "Missing CONTAINS before internal subprogram", ["contains", "unexpected", "subroutine"], "Restore CONTAINS before internal procedures.", f_missing_contains),
    _mk("F20", "fortran", "module", "Missing module dependency", ["module file", "cannot open", "missing_module"], "Provide the module or remove the USE statement.", f_missing_module),
    _mk("F21", "fortran", "declaration", "Declaration after executable statement", ["unexpected data declaration", "declaration", "executable"], "Move declarations before executable statements.", f_late_declaration),
    _mk("F22", "fortran", "type", "Relational comparison type mismatch", ["comparison", "integer", "character"], "Compare values with compatible types.", f_relational_type_mismatch),
]

ALL_MUTATIONS = {spec.mutation_id: spec for spec in [*C_MUTATIONS, *FORTRAN_MUTATIONS]}
BY_LANGUAGE = {
    "c": {spec.mutation_id: spec for spec in C_MUTATIONS},
    "fortran": {spec.mutation_id: spec for spec in FORTRAN_MUTATIONS},
}


def list_mutations(language: str | None = None) -> list[dict[str, str]]:
    specs = BY_LANGUAGE[language].values() if language else ALL_MUTATIONS.values()
    return [
        {
            "id": spec.mutation_id,
            "language": spec.language,
            "category": spec.category,
            "title": spec.title,
        }
        for spec in specs
    ]


def parse_selection(selection: str | None, language: str) -> list[str]:
    available = BY_LANGUAGE[language]
    if not selection or selection.lower() == "all":
        return list(available)
    requested = []
    for raw in re.split(r"[,\s]+", selection.strip()):
        if not raw:
            continue
        mid = raw.upper()
        if mid.isdigit():
            mid = ("C" if language == "c" else "F") + mid.zfill(2)
        if mid not in available:
            raise ValueError(f"Unknown {language} mutation id: {raw}")
        requested.append(mid)
    return list(dict.fromkeys(requested))


def apply_mutations(
    source_file: str | Path,
    mutation_ids: list[str] | None = None,
    output_dir: str | Path | None = None,
    seed: int | None = None,
) -> MutationResult:
    source = Path(source_file)
    language = language_for_path(source)
    requested = mutation_ids or list(BY_LANGUAGE[language])
    rng = random.Random(seed)
    lines = source.read_text(errors="replace").splitlines(keepends=True)
    current = lines[:]
    applied: list[MutationRecord] = []
    skipped: list[dict[str, str]] = []

    for mid in requested:
        spec = BY_LANGUAGE[language][mid]
        mutated, record = spec.fn(spec, current, rng)
        if mutated is None or record is None:
            skipped.append({"mutation_id": mid, "reason": "no suitable mutation site found"})
            continue
        current = mutated
        applied.append(record)

    target = mutated_path_for(source, output_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(current))

    result = MutationResult(
        source_file=str(source.resolve()),
        mutated_file=str(target.resolve()),
        language=language,
        requested=requested,
        applied=applied,
        skipped=skipped,
    )
    report_path = target.with_name(f"{target.stem}_injection_report.json")
    report_path.write_text(json.dumps(result.to_dict(), indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject categorized compiler errors into C or Fortran programs.")
    parser.add_argument("source")
    parser.add_argument("--mutations", default="all", help="all, or comma-separated ids such as C01,C05 / F01,F03")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--seed", type=int, default=40)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        language = language_for_path(args.source)
        print(json.dumps(list_mutations(language), indent=2))
        return

    language = language_for_path(args.source)
    selected = parse_selection(args.mutations, language)
    result = apply_mutations(args.source, selected, args.output_dir, args.seed)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
