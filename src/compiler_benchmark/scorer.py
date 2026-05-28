from __future__ import annotations

import argparse
import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .models import CompilerResult, Diagnostic, MutationRecord


QUALITY_CENTERS = {
    "poor": 15.0,
    "weak": 35.0,
    "fair": 55.0,
    "good": 75.0,
    "excellent": 92.0,
}


def _triangular(x: float, a: float, b: float, c: float) -> float:
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


def _left_shoulder(x: float, a: float, b: float) -> float:
    if x <= a:
        return 1.0
    if x >= b:
        return 0.0
    return (b - x) / (b - a)


def _right_shoulder(x: float, a: float, b: float) -> float:
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    return (x - a) / (b - a)


def fuzzify(x: float) -> dict[str, float]:
    x = max(0.0, min(1.0, x))
    return {
        "low": _left_shoulder(x, 0.25, 0.45),
        "medium": _triangular(x, 0.25, 0.55, 0.8),
        "high": _right_shoulder(x, 0.65, 0.9),
    }


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_+%-]*", text.lower())
        if len(token) > 1 and token not in {"the", "and", "for", "with", "this", "that", "from"}
    }


def _keyword_score(message: str, expected: list[str]) -> float:
    msg = message.lower()
    hits = sum(1 for kw in expected if kw.lower() in msg)
    direct = hits / max(1, len(expected))
    fuzzy = 0.0
    msg_tokens = _tokens(msg)
    for kw in expected:
        kw_tokens = _tokens(kw)
        if not kw_tokens:
            continue
        best = max((SequenceMatcher(None, kt, mt).ratio() for kt in kw_tokens for mt in msg_tokens), default=0.0)
        fuzzy += best
    fuzzy = fuzzy / max(1, len(expected))
    return max(direct, fuzzy * 0.75)


def _location_score(diag: Diagnostic, mutation: MutationRecord, tolerance: int) -> float:
    if diag.line is None:
        return 0.0
    distance = abs(diag.line - mutation.line)
    if distance == 0:
        return 1.0
    if distance <= tolerance:
        return 1.0 - (distance / (tolerance + 1))
    return max(0.0, 0.15 - math.log1p(distance - tolerance) * 0.05)


def _severity_score(diag: Diagnostic, mutation: MutationRecord) -> float:
    actual = diag.severity.lower()
    expected = mutation.severity.lower()
    if expected in actual:
        return 1.0
    if expected == "error" and actual in {"fatal error", "severe"}:
        return 0.9
    if expected == "warning" and actual == "error":
        return 0.55
    if expected == "error" and actual == "warning":
        return 0.45
    return 0.25


def _fixit_score(diag: Diagnostic, mutation: MutationRecord) -> float:
    text = " ".join([diag.message, *diag.context, *diag.fixits]).lower()
    parseable = [
        item for item in diag.fixits
        if item.startswith("parseable-fixit:")
    ]
    if parseable:
        best = 0.0
        fix_tokens = _tokens(mutation.fix_hint)
        for item in parseable:
            match = re.match(
                r"parseable-fixit:.*?:(\d+):(\d+)-(\d+):(\d+):(.*)",
                item,
            )
            if not match:
                continue
            start_line = int(match.group(1))
            end_line = int(match.group(3))
            replacement = match.group(5)
            location_ok = 1.0 if start_line <= mutation.line <= end_line else _location_score(
                Diagnostic(diag.file, start_line, diag.column, diag.severity, diag.message),
                mutation,
                2,
            )
            replacement_tokens = _tokens(replacement)
            expected_overlap = len(fix_tokens & (_tokens(text) | replacement_tokens)) / max(1, len(fix_tokens))
            # Parseable compiler fix-its are more valuable than vague advice, but
            # they still need to point near the injected mistake to count as valid.
            best = max(best, min(1.0, 0.55 + 0.3 * location_ok + 0.15 * expected_overlap))
        if best:
            return best

    has_explicit_fix = bool(diag.fixits) or bool(re.search(r"did you mean|insert|remove|replace|suggest", text))
    if has_explicit_fix:
        fix_tokens = _tokens(mutation.fix_hint)
        overlap = len(fix_tokens & _tokens(text)) / max(1, len(fix_tokens))
        return max(0.7, min(1.0, 0.7 + overlap * 0.3))
    if re.search(r"expected|missing|undeclared|too few|too many|incompatible|invalid", text):
        return 0.45
    return 0.15


def _clarity_score(diag: Diagnostic, mutation: MutationRecord) -> float:
    message = diag.message.strip()
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_'-]*", message)
    if not words:
        return 0.0
    length_score = 1.0 if 5 <= len(words) <= 24 else max(0.35, 1.0 - abs(len(words) - 15) / 40)
    keyword = _keyword_score(message, mutation.expected_keywords)
    has_subject = 1.0 if re.search(r"\b(expected|undeclared|incompatible|invalid|missing|return|argument|type|array|pointer)\b", message, re.I) else 0.55
    jargon_penalty = 0.15 if re.search(r"\btoken|primary-expression|lvalue|required before\b", message, re.I) else 0.0
    return max(0.0, min(1.0, (0.35 * length_score) + (0.45 * keyword) + (0.2 * has_subject) - jargon_penalty))


def _signal_score(best_index: int, compiler_result: CompilerResult) -> float:
    if not compiler_result.diagnostics:
        return 0.0
    first_bonus = 1.0 if best_index == 0 else max(0.45, 1.0 - best_index * 0.12)
    noise_penalty = min(0.35, max(0, len(compiler_result.diagnostics) - 3) * 0.05)
    return max(0.0, first_bonus - noise_penalty)


def fuzzy_quality(inputs: dict[str, float]) -> tuple[float, list[dict[str, Any]]]:
    f = {name: fuzzify(value) for name, value in inputs.items()}
    rules: list[tuple[float, str, str]] = [
        (min(f["diagnosis"]["high"], f["location"]["high"], f["clarity"]["high"]), "excellent", "accurate diagnosis, precise location, clear message"),
        (min(f["diagnosis"]["high"], f["location"]["high"], f["fixit"]["medium"]), "good", "accurate and localized with at least usable repair guidance"),
        (min(f["diagnosis"]["high"], f["location"]["medium"], f["clarity"]["medium"]), "good", "right diagnosis with acceptable location and explanation"),
        (min(f["diagnosis"]["medium"], f["location"]["high"], f["clarity"]["medium"]), "fair", "localized but only partly descriptive"),
        (min(f["diagnosis"]["medium"], f["location"]["medium"]), "fair", "partially correct and close enough to investigate"),
        (max(f["diagnosis"]["low"], f["location"]["low"]), "weak", "wrong diagnosis or poor location"),
        (min(f["diagnosis"]["low"], f["location"]["low"]), "poor", "both diagnosis and location are weak"),
        (f["severity"]["low"], "weak", "severity classification is misleading"),
        (f["signal"]["low"], "weak", "diagnostic is buried in noisy output"),
    ]
    active = [
        {"strength": round(strength, 4), "quality": quality, "reason": reason}
        for strength, quality, reason in rules
        if strength > 0
    ]
    if not active:
        return 0.0, []
    numerator = sum(item["strength"] * QUALITY_CENTERS[item["quality"]] for item in active)
    denominator = sum(item["strength"] for item in active)
    return round(numerator / denominator, 2), active


def score_diagnostic(
    compiler_result: CompilerResult,
    mutation: MutationRecord,
    location_tolerance: int = 3,
) -> dict[str, Any]:
    if not compiler_result.available:
        return {
            "score": 0.0,
            "grade": "unavailable",
            "compiler": compiler_result.compiler,
            "mutation_id": mutation.mutation_id,
            "mutation_title": mutation.title,
            "category": mutation.category,
            "reason": compiler_result.raw_output,
            "inputs": {},
            "matched_diagnostic": None,
            "rules": [],
        }
    if not compiler_result.diagnostics:
        return {
            "score": 0.0,
            "grade": "poor",
            "compiler": compiler_result.compiler,
            "mutation_id": mutation.mutation_id,
            "mutation_title": mutation.title,
            "category": mutation.category,
            "reason": "compiler produced no structured diagnostics",
            "inputs": {},
            "matched_diagnostic": None,
            "rules": [],
        }

    candidates = []
    for idx, diag in enumerate(compiler_result.diagnostics):
        diagnosis = _keyword_score(diag.message + " " + " ".join(diag.context), mutation.expected_keywords)
        location = _location_score(diag, mutation, location_tolerance)
        severity = _severity_score(diag, mutation)
        fixit = _fixit_score(diag, mutation)
        clarity = _clarity_score(diag, mutation)
        signal = _signal_score(idx, compiler_result)
        pre_score = 0.32 * diagnosis + 0.28 * location + 0.12 * severity + 0.12 * fixit + 0.1 * clarity + 0.06 * signal
        candidates.append((pre_score, idx, diag, {
            "diagnosis": round(diagnosis, 4),
            "location": round(location, 4),
            "severity": round(severity, 4),
            "fixit": round(fixit, 4),
            "clarity": round(clarity, 4),
            "signal": round(signal, 4),
        }))

    _, best_index, best_diag, inputs = max(candidates, key=lambda item: item[0])
    score, rules = fuzzy_quality(inputs)
    grade = "excellent" if score >= 85 else "good" if score >= 70 else "fair" if score >= 50 else "weak" if score >= 30 else "poor"
    return {
        "score": score,
        "grade": grade,
        "compiler": compiler_result.compiler,
        "mutation_id": mutation.mutation_id,
        "mutation_title": mutation.title,
        "category": mutation.category,
        "inputs": inputs,
        "matched_diagnostic": best_diag.to_dict(),
        "diagnostic_index": best_index,
        "rules": rules,
    }


def score_compiler_result(
    compiler_result: CompilerResult,
    mutations: list[MutationRecord],
    location_tolerance: int = 3,
) -> dict[str, Any]:
    scores = [score_diagnostic(compiler_result, mutation, location_tolerance) for mutation in mutations]
    numeric = [item["score"] for item in scores]
    category_totals: dict[str, list[float]] = {}
    for item in scores:
        category_totals.setdefault(item["category"], []).append(item["score"])
    return {
        "compiler": compiler_result.compiler,
        "language": compiler_result.language,
        "available": compiler_result.available,
        "overall_score": round(sum(numeric) / len(numeric), 2) if numeric else 0.0,
        "mutation_scores": scores,
        "category_scores": {
            category: round(sum(values) / len(values), 2)
            for category, values in sorted(category_totals.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score compiler diagnostics using fuzzy quality rules.")
    parser.add_argument("compiler_report", help="JSON report produced by the benchmark runner.")
    args = parser.parse_args()
    data = json.loads(Path(args.compiler_report).read_text())
    print(json.dumps(data.get("scores", {}), indent=2))


if __name__ == "__main__":
    main()
