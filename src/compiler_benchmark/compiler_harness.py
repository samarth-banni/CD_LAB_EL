from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import CompilerResult, Diagnostic, language_for_path


@dataclass(frozen=True)
class CompilerProfile:
    name: str
    language: str
    binaries: list[str]
    flags: list[str]
    version_flag: str = "--version"
    install_hint: str = ""


PROFILES: dict[str, CompilerProfile] = {
    "gcc": CompilerProfile(
        name="gcc",
        language="c",
        binaries=["gcc"],
        flags=["-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-fsyntax-only", "-fdiagnostics-color=never"],
        install_hint="Install gcc with your Linux package manager, for example: apt install gcc / dnf install gcc / pacman -S gcc",
    ),
    "clang": CompilerProfile(
        name="clang",
        language="c",
        binaries=["clang"],
        flags=[
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Wconversion",
            "-fsyntax-only",
            "-fno-color-diagnostics",
            "-fdiagnostics-parseable-fixits",
        ],
        install_hint="Install clang with your Linux package manager, for example: apt install clang / dnf install clang / pacman -S clang",
    ),
    "gfortran": CompilerProfile(
        name="gfortran",
        language="fortran",
        binaries=["gfortran"],
        flags=["-std=f2008", "-Wall", "-Wextra", "-Wconversion", "-fsyntax-only", "-fdiagnostics-color=never"],
        install_hint="Install gfortran with your Linux package manager, for example: apt install gfortran / dnf install gcc-gfortran / pacman -S gcc-fortran",
    ),
    "flang": CompilerProfile(
        name="flang",
        language="fortran",
        binaries=["flang-new", "flang-new-19", "flang-new-18", "flang-new-17", "flang-new-16", "flang"],
        flags=["-fsyntax-only"],
        install_hint="Install LLVM Flang from your Linux distribution or LLVM packages; the binary is often flang-new.",
    ),
}


_GNU_CLANG_RE = re.compile(
    r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+):\s*(?P<severity>fatal error|error|warning|note):\s*(?P<message>.+)$",
    re.I,
)
_GNU_NO_COL_RE = re.compile(
    r"^(?P<file>.*?):(?P<line>\d+):\s*(?P<severity>fatal error|error|warning|note):\s*(?P<message>.+)$",
    re.I,
)
_GNU_LOC_ONLY_RE = re.compile(r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+):\s*$")
_GNU_SEVERITY_ONLY_RE = re.compile(r"^(?P<severity>fatal error|error|warning|note):\s*(?P<message>.+)$", re.I)
_FLANG_RE = re.compile(r"^(?P<severity>error|warning):\s*(?P<message>.+)$", re.I)
_FLANG_LOC_RE = re.compile(r"^\s*-->\s*(?P<file>.*?):(?P<line>\d+):(?P<col>\d+)")
_FIXIT_RE = re.compile(r"(fix-it|fixit|did you mean|suggestion|insert|replace|remove)", re.I)
_CLANG_FIXIT_RE = re.compile(
    r'^fix-it:"(?P<file>.*?)":\{(?P<start_line>\d+):(?P<start_col>\d+)-(?P<end_line>\d+):(?P<end_col>\d+)\}:"(?P<text>.*)"$'
)


def compiler_names_for_language(language: str) -> list[str]:
    return [name for name, profile in PROFILES.items() if profile.language == language]


def _resolve_binary(profile: CompilerProfile) -> str | None:
    for binary in profile.binaries:
        found = shutil.which(binary)
        if found:
            return binary
    return None


def _version(binary: str, profile: CompilerProfile) -> str:
    try:
        proc = subprocess.run([binary, profile.version_flag], capture_output=True, text=True, timeout=10)
    except Exception:
        return "unknown"
    lines = (proc.stdout + proc.stderr).splitlines()
    return lines[0].strip() if lines else "unknown"


def parse_diagnostics(raw_output: str, source_file: str | Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    current: Diagnostic | None = None
    pending_flang: Diagnostic | None = None
    pending_gnu_location: dict[str, str] | None = None
    source_name = Path(source_file).name

    for raw_line in raw_output.splitlines():
        line = raw_line.rstrip()
        parseable_fixit = _CLANG_FIXIT_RE.match(line)
        if parseable_fixit:
            target = current or pending_flang
            if target:
                groups = parseable_fixit.groupdict()
                target.fixits.append(
                    "parseable-fixit:"
                    f"{Path(groups['file']).name}:"
                    f"{groups['start_line']}:{groups['start_col']}-"
                    f"{groups['end_line']}:{groups['end_col']}:"
                    f"{groups['text']}"
                )
            continue

        match = _GNU_CLANG_RE.match(line) or _GNU_NO_COL_RE.match(line)
        if match:
            if current:
                diagnostics.append(current)
            groups = match.groupdict()
            current = Diagnostic(
                file=Path(groups["file"]).name,
                line=int(groups["line"]),
                column=int(groups.get("col") or 1),
                severity=groups["severity"].lower(),
                message=groups["message"].strip(),
            )
            pending_flang = None
            pending_gnu_location = None
            continue

        loc_only = _GNU_LOC_ONLY_RE.match(line)
        if loc_only:
            if current:
                diagnostics.append(current)
                current = None
            pending_gnu_location = loc_only.groupdict()
            continue

        severity_only = _GNU_SEVERITY_ONLY_RE.match(line)
        if severity_only and pending_gnu_location:
            groups = pending_gnu_location
            current = Diagnostic(
                file=Path(groups["file"]).name,
                line=int(groups["line"]),
                column=int(groups["col"]),
                severity=severity_only.group("severity").lower(),
                message=severity_only.group("message").strip(),
            )
            pending_gnu_location = None
            pending_flang = None
            continue

        flang_match = _FLANG_RE.match(line)
        if flang_match:
            if current:
                diagnostics.append(current)
                current = None
            pending_flang = Diagnostic(
                file=source_name,
                line=None,
                column=None,
                severity=flang_match.group("severity").lower(),
                message=flang_match.group("message").strip(),
            )
            continue

        loc_match = _FLANG_LOC_RE.match(line)
        if loc_match and pending_flang:
            pending_flang.file = Path(loc_match.group("file")).name
            pending_flang.line = int(loc_match.group("line"))
            pending_flang.column = int(loc_match.group("col"))
            current = pending_flang
            pending_flang = None
            continue

        target = current or pending_flang
        if target and line.strip():
            if _FIXIT_RE.search(line):
                target.fixits.append(line.strip())
            else:
                target.context.append(line)

    if current:
        diagnostics.append(current)
    elif pending_flang:
        diagnostics.append(pending_flang)

    return diagnostics


def run_compiler(compiler: str, source_file: str | Path, timeout: int = 30) -> CompilerResult:
    source = Path(source_file)
    language = language_for_path(source)
    profile = PROFILES[compiler]
    if profile.language != language:
        raise ValueError(f"{compiler} is for {profile.language}, but {source} is {language}")

    binary = _resolve_binary(profile)
    if binary is None:
        return CompilerResult(
            compiler=compiler,
            language=language,
            available=False,
            version=None,
            command=[profile.binaries[0], *profile.flags, str(source)],
            return_code=None,
            raw_output=f"{compiler} not found. Install hint: {profile.install_hint}",
            diagnostics=[],
        )

    cmd = [binary, *profile.flags, str(source)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        raw = (proc.stderr or proc.stdout).strip()
        diagnostics = parse_diagnostics(raw, source)
        return CompilerResult(
            compiler=compiler,
            language=language,
            available=True,
            version=_version(binary, profile),
            command=cmd,
            return_code=proc.returncode,
            raw_output=raw,
            diagnostics=diagnostics,
        )
    except subprocess.TimeoutExpired as exc:
        raw = ((exc.stderr or b"") + (exc.stdout or b"")).decode(errors="replace") if isinstance(exc.stderr, bytes) else str(exc)
        return CompilerResult(
            compiler=compiler,
            language=language,
            available=True,
            version=_version(binary, profile),
            command=cmd,
            return_code=-1,
            raw_output=raw,
            diagnostics=[],
            timed_out=True,
        )


def run_compilers(
    source_file: str | Path,
    compilers: list[str] | None = None,
    timeout: int = 30,
) -> dict[str, CompilerResult]:
    language = language_for_path(source_file)
    selected = compilers or compiler_names_for_language(language)
    results: dict[str, CompilerResult] = {}
    for compiler in selected:
        if compiler not in PROFILES:
            raise ValueError(f"Unknown compiler: {compiler}")
        results[compiler] = run_compiler(compiler, source_file, timeout)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a source file through supported Linux compilers.")
    parser.add_argument("source")
    parser.add_argument("--compilers", default=None, help="Comma-separated compiler names. Defaults by language.")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    compilers = [c.strip() for c in args.compilers.split(",")] if args.compilers else None
    results = run_compilers(args.source, compilers, args.timeout)
    print(json.dumps({name: result.to_dict() for name, result in results.items()}, indent=2))


if __name__ == "__main__":
    main()
