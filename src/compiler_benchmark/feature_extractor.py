from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .models import language_for_path


def _strip_comments_and_strings(source: str, language: str) -> str:
    if language == "c":
        source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
        source = re.sub(r"//[^\n]*", " ", source)
    else:
        source = re.sub(r"![^\n]*", " ", source)
    source = re.sub(r'"(?:[^"\\]|\\.)*"', '""', source)
    source = re.sub(r"'(?:[^'\\]|\\.)*'", "''", source)
    return source


def extract_features(source_file: str | Path) -> dict:
    path = Path(source_file)
    raw = path.read_text(errors="replace")
    language = language_for_path(path)
    src = _strip_comments_and_strings(raw, language)
    lines = raw.splitlines()
    blank = sum(1 for line in lines if not line.strip())
    comments = sum(1 for line in lines if line.strip().startswith(("!", "//", "/*", "*")))

    if language == "c":
        function_names = re.findall(r"\b(?:int|void|char|float|double|long|short|unsigned|struct\s+\w+)\s+\*?(\w+)\s*\([^;)]*\)\s*\{", src)
        features = {
            "has_pointers": bool(re.search(r"\b(?:int|char|float|double|void|long|short)\s*\*+\s*\w+", src)),
            "has_structures": bool(re.search(r"\bstruct\b", src)),
            "has_preprocessor": bool(re.search(r"^\s*#", raw, re.M)),
            "printf_count": len(re.findall(r"\bprintf\s*\(", src)),
        }
    else:
        function_names = re.findall(r"\b(?:subroutine|function)\s+(\w+)", src, flags=re.I)
        features = {
            "has_modules": bool(re.search(r"\bmodule\s+\w+", src, re.I)),
            "has_subroutines": bool(re.search(r"\bsubroutine\s+\w+", src, re.I)),
            "has_implicit_none": bool(re.search(r"\bimplicit\s+none\b", src, re.I)),
            "print_count": len(re.findall(r"\bprint\s*\*", src, re.I)),
        }

    common = {
        "filename": path.name,
        "filepath": str(path.resolve()),
        "language": language,
        "lines": len(lines),
        "code_lines": max(0, len(lines) - blank - comments),
        "blank_lines": blank,
        "comment_lines": comments,
        "has_loops": bool(re.search(r"\b(for|while|do)\b", src, re.I)),
        "has_conditionals": bool(re.search(r"\b(if|switch|select\s+case)\b", src, re.I)),
        "has_arrays": bool(re.search(r"\w+\s*(?:\[[^\]]+\]|\([^)]*:\s*[^)]*\))", src)),
        "function_count": len(function_names),
        "function_names": list(dict.fromkeys(function_names)),
    }
    common.update(features)
    common["program_class"] = _classify(common)
    return common


def _classify(features: dict) -> str:
    booleans = [value for value in features.values() if isinstance(value, bool)]
    score = sum(booleans) + min(3, features.get("function_count", 0))
    if score <= 3:
        return "Beginner"
    if score <= 7:
        return "Intermediate"
    return "Advanced"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract source features for C and Fortran benchmark programs.")
    parser.add_argument("sources", nargs="+")
    args = parser.parse_args()
    results = [extract_features(source) for source in args.sources]
    print(json.dumps(results[0] if len(results) == 1 else results, indent=2))


if __name__ == "__main__":
    main()
