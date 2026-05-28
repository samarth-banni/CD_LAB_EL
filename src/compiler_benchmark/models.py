from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MutationRecord:
    mutation_id: str
    language: str
    category: str
    title: str
    line: int
    column: int | None
    original_code: str
    mutated_code: str
    expected_keywords: list[str]
    fix_hint: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MutationResult:
    source_file: str
    mutated_file: str
    language: str
    requested: list[str]
    applied: list[MutationRecord] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "mutated_file": self.mutated_file,
            "language": self.language,
            "requested": self.requested,
            "applied_count": len(self.applied),
            "applied": [item.to_dict() for item in self.applied],
            "skipped": self.skipped,
        }


@dataclass
class Diagnostic:
    file: str
    line: int | None
    column: int | None
    severity: str
    message: str
    context: list[str] = field(default_factory=list)
    fixits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompilerResult:
    compiler: str
    language: str
    available: bool
    version: str | None
    command: list[str]
    return_code: int | None
    raw_output: str
    diagnostics: list[Diagnostic]
    timed_out: bool = False

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if "error" in d.severity.lower())

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity.lower() == "warning")

    @property
    def note_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity.lower() == "note")

    @property
    def compile_clean(self) -> bool:
        return self.return_code == 0 and self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiler": self.compiler,
            "language": self.language,
            "available": self.available,
            "version": self.version,
            "command": self.command,
            "return_code": self.return_code,
            "timed_out": self.timed_out,
            "compile_clean": self.compile_clean,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "note_count": self.note_count,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "raw_output": self.raw_output,
        }


def language_for_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".c", ".h"}:
        return "c"
    if suffix in {".f", ".for", ".f90", ".f95", ".f03", ".f08"}:
        return "fortran"
    raise ValueError(f"Unsupported source extension: {suffix}")


def mutated_path_for(path: str | Path, output_dir: str | Path | None = None) -> Path:
    source = Path(path)
    target_dir = Path(output_dir) if output_dir else source.parent
    return target_dir / f"{source.stem}_mutated{source.suffix}"
