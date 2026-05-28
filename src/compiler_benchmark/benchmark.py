from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import mean

from .compiler_harness import compiler_names_for_language, run_compilers
from .feature_extractor import extract_features
from .models import language_for_path
from .mutations import apply_mutations, parse_selection
from .scorer import score_compiler_result


def _weak_spots(scores: dict) -> dict:
    spots = {}
    for compiler, score_data in scores.items():
        category_scores = score_data.get("category_scores", {})
        mutation_scores = score_data.get("mutation_scores", [])
        weakest_categories = sorted(category_scores.items(), key=lambda item: item[1])[:3]
        weakest_mutations = sorted(mutation_scores, key=lambda item: item["score"])[:5]
        spots[compiler] = {
            "weakest_categories": [
                {"category": category, "score": score, "suggestion": _suggest_category_improvement(category)}
                for category, score in weakest_categories
            ],
            "weakest_mutations": [
                {
                    "mutation_id": item["mutation_id"],
                    "title": item["mutation_title"],
                    "score": item["score"],
                    "suggestion": _suggest_mutation_improvement(item),
                }
                for item in weakest_mutations
            ],
        }
    return spots


def _suggest_category_improvement(category: str) -> str:
    suggestions = {
        "syntax": "Improve parser recovery and mention the exact missing or mismatched token.",
        "type": "Name both expected and actual types, then show the expression that caused conversion.",
        "scope": "Include the unresolved identifier and nearest similar declarations when possible.",
        "function": "Show the declared signature and the actual call signature side by side.",
        "array": "Report declared rank/size and the offending index or initializer count.",
        "format": "Pair each printf/format specifier with the actual argument type.",
        "control-flow": "Point to the unmatched block opener and the statement that closes or escapes it.",
        "operator": "Name operand types and list valid operators or conversions.",
    }
    return suggestions.get(category, "Make the diagnostic more specific, local, and action-oriented.")


def _suggest_mutation_improvement(item: dict) -> str:
    inputs = item.get("inputs", {})
    weakest = sorted(inputs.items(), key=lambda kv: kv[1])[:2]
    labels = {name for name, _ in weakest}
    if "location" in labels:
        return "Prioritize the injected line or nearest syntax construct instead of a later cascade error."
    if "diagnosis" in labels:
        return "Use keywords that describe the real mistake category, not only the parser symptom."
    if "fixit" in labels:
        return "Add a concrete insert/remove/replace suggestion and validate it against the source span."
    if "clarity" in labels:
        return "Rewrite the message with expected vs actual information in plain language."
    return "Reduce noise and improve the first diagnostic for this category."


def _write_csv(path: Path, report: dict) -> None:
    rows = []
    for source_result in report["source_results"]:
        source = Path(source_result["source_file"]).name
        for compiler, score_data in source_result["scores"].items():
            rows.append({
                "source": source,
                "language": source_result["language"],
                "compiler": compiler,
                "overall_score": score_data["overall_score"],
                "available": score_data["available"],
            })
            for item in score_data["mutation_scores"]:
                rows.append({
                    "source": source,
                    "language": source_result["language"],
                    "compiler": compiler,
                    "mutation_id": item["mutation_id"],
                    "category": item["category"],
                    "mutation_score": item["score"],
                    "grade": item["grade"],
                    "available": score_data["available"],
                })
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Compiler Diagnostic Quality Benchmark Report",
        "",
        f"Generated: {report['timestamp']}",
        "",
        "## Overall Scores",
        "",
        "| Compiler | Language | Average Score | Availability |",
        "|---|---:|---:|---:|",
    ]
    for item in report["summary"]["compiler_rankings"]:
        lines.append(f"| {item['compiler']} | {item['language']} | {item['average_score']} | {item['available_runs']}/{item['total_runs']} |")

    lines.extend(["", "## Weak Spots", ""])
    for source_result in report["source_results"]:
        lines.append(f"### {Path(source_result['source_file']).name}")
        for compiler, spots in source_result["weak_spots"].items():
            lines.append(f"- **{compiler}**")
            for category in spots["weakest_categories"]:
                lines.append(f"  - Category `{category['category']}` scored {category['score']}: {category['suggestion']}")
            for mutation in spots["weakest_mutations"][:2]:
                lines.append(f"  - Mutation `{mutation['mutation_id']}` scored {mutation['score']}: {mutation['suggestion']}")
        lines.append("")
    path.write_text("\n".join(lines))


def run_benchmark(
    sources: list[str | Path],
    output_dir: str | Path = "reports",
    mutations: str = "all",
    compilers: list[str] | None = None,
    seed: int = 40,
    location_tolerance: int = 3,
) -> dict:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source_results = []

    for source in sources:
        source_path = Path(source)
        language = language_for_path(source_path)
        selected_mutations = parse_selection(mutations, language)
        selected_compilers = compilers or compiler_names_for_language(language)
        case_results = []
        compiler_score_buckets: dict[str, list[dict]] = {compiler: [] for compiler in selected_compilers}

        for mutation_id in selected_mutations:
            case_dir = out_dir / "cases" / source_path.stem / mutation_id
            mutation_result = apply_mutations(source_path, [mutation_id], case_dir, seed)
            compiler_results = run_compilers(mutation_result.mutated_file, selected_compilers)
            scores = {
                name: score_compiler_result(result, mutation_result.applied, location_tolerance)
                for name, result in compiler_results.items()
            }
            for compiler, score in scores.items():
                compiler_score_buckets.setdefault(compiler, []).extend(score["mutation_scores"])
            case_results.append({
                "mutation_id": mutation_id,
                "mutation_result": mutation_result.to_dict(),
                "compiler_results": {name: result.to_dict() for name, result in compiler_results.items()},
                "scores": scores,
            })

        scores = {}
        for compiler in selected_compilers:
            mutation_scores = compiler_score_buckets.get(compiler, [])
            category_totals: dict[str, list[float]] = {}
            for item in mutation_scores:
                category_totals.setdefault(item["category"], []).append(item["score"])
            first_case_score = next(
                (case["scores"][compiler] for case in case_results if compiler in case["scores"]),
                {"available": False},
            )
            scores[compiler] = {
                "compiler": compiler,
                "language": language,
                "available": bool(first_case_score.get("available")),
                "overall_score": round(mean([item["score"] for item in mutation_scores]), 2) if mutation_scores else 0.0,
                "mutation_scores": mutation_scores,
                "category_scores": {
                    category: round(mean(values), 2)
                    for category, values in sorted(category_totals.items())
                },
            }
        source_results.append({
            "source_file": str(source_path.resolve()),
            "language": language,
            "features": extract_features(source_path),
            "case_results": case_results,
            "scores": scores,
            "weak_spots": _weak_spots(scores),
        })

    ranking_bucket: dict[tuple[str, str], dict] = {}
    for source_result in source_results:
        for compiler, score in source_result["scores"].items():
            key = (compiler, source_result["language"])
            bucket = ranking_bucket.setdefault(key, {"scores": [], "available": 0, "total": 0})
            bucket["scores"].append(score["overall_score"])
            bucket["available"] += 1 if score["available"] else 0
            bucket["total"] += 1

    compiler_rankings = [
        {
            "compiler": compiler,
            "language": language,
            "average_score": round(mean(bucket["scores"]), 2) if bucket["scores"] else 0.0,
            "available_runs": bucket["available"],
            "total_runs": bucket["total"],
        }
        for (compiler, language), bucket in ranking_bucket.items()
    ]
    compiler_rankings.sort(key=lambda item: item["average_score"], reverse=True)

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "scoring_model": {
            "name": "Mamdani-style fuzzy diagnostic quality scorer",
            "inputs": ["diagnosis", "location", "severity", "fixit", "clarity", "signal"],
            "score_range": "0-100",
            "location_tolerance_lines": location_tolerance,
        },
        "summary": {"compiler_rankings": compiler_rankings},
        "source_results": source_results,
    }

    json_path = out_dir / "benchmark_report.json"
    csv_path = out_dir / "benchmark_scores.csv"
    md_path = out_dir / "benchmark_report.md"
    json_path.write_text(json.dumps(report, indent=2))
    _write_csv(csv_path, report)
    _write_markdown(md_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full compiler diagnostic quality benchmark.")
    parser.add_argument("sources", nargs="+")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--mutations", default="all")
    parser.add_argument("--compilers", default=None, help="Comma-separated compiler list. Defaults by language.")
    parser.add_argument("--seed", type=int, default=40)
    parser.add_argument("--location-tolerance", type=int, default=3)
    args = parser.parse_args()

    compilers = [item.strip() for item in args.compilers.split(",")] if args.compilers else None
    report = run_benchmark(args.sources, args.output_dir, args.mutations, compilers, args.seed, args.location_tolerance)
    print(json.dumps(report["summary"], indent=2))
    print(f"Reports written to: {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
