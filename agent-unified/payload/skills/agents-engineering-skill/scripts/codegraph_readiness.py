#!/usr/bin/env python3
"""Assess when a local CodeGraph index is likely to repay its overhead."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess


# These are project heuristics, not limits imposed by CodeGraph.
FILE_THRESHOLD = 500
LINE_THRESHOLD = 50_000
POLYGLOT_FILE_THRESHOLD = 200
LANGUAGE_THRESHOLD = 3

# Keep this list aligned with languages advertised in CodeGraph's official README.
SOURCE_LANGUAGES = {
    ".astro": "Astro",
    ".c": "C",
    ".cbl": "COBOL",
    ".cfc": "CFML",
    ".cfm": "CFML",
    ".cc": "C++",
    ".cob": "COBOL",
    ".cs": "C#",
    ".cu": "CUDA",
    ".cuh": "CUDA",
    ".cpp": "C++",
    ".cxx": "C++",
    ".dart": "Dart",
    ".erl": "Erlang",
    ".ets": "ArkTS",
    ".go": "Go",
    ".h": "C/C++",
    ".hh": "C++",
    ".hpp": "C++",
    ".hrl": "Erlang",
    ".hxx": "C++",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".liquid": "Liquid",
    ".lua": "Lua",
    ".luau": "Luau",
    ".m": "Objective-C",
    ".metal": "Metal",
    ".mjs": "JavaScript",
    ".mm": "Objective-C++",
    ".nix": "Nix",
    ".pas": "Pascal",
    ".php": "PHP",
    ".py": "Python",
    ".r": "R",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scala": "Scala",
    ".sol": "Solidity",
    ".svelte": "Svelte",
    ".swift": "Swift",
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vb": "VB.NET",
    ".vue": "Vue",
}
IGNORED_DIRECTORIES = {
    ".codegraph",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}


@dataclass(frozen=True)
class Readiness:
    root: str
    status: str
    active: bool
    recommended: bool
    source_files: int
    source_lines: int | None
    source_lines_complete: bool
    languages: tuple[str, ...]
    reasons: tuple[str, ...]


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in IGNORED_DIRECTORIES for part in relative_parts)


def _git_visible_files(root: Path) -> list[Path] | None:
    """Return tracked and unignored untracked files, or None outside Git."""
    git = shutil.which("git")
    if git is None:
        return None

    try:
        top_level = subprocess.run(
            [git, "-C", str(root), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if top_level.returncode != 0:
        return None

    repository_root = Path(top_level.stdout.strip()).resolve()
    try:
        relative_root = root.relative_to(repository_root)
    except ValueError:
        return None

    pathspec = "." if relative_root == Path(".") else relative_root.as_posix()
    try:
        result = subprocess.run(
            [
                git,
                "-C",
                str(repository_root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                pathspec,
            ],
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None

    files: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = (repository_root / os.fsdecode(raw_path)).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file():
            files.append(path)
    return files


def _fallback_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and not _is_ignored(path, root)
    ]


def discover_source_files(root: Path) -> list[Path]:
    candidates = _git_visible_files(root)
    if candidates is None:
        candidates = _fallback_files(root)
    return sorted(
        path
        for path in candidates
        if path.suffix.lower() in SOURCE_LANGUAGES and not _is_ignored(path, root)
    )


def _count_lines(path: Path, stop_at: int) -> tuple[int, bool]:
    lines = 0
    last_byte = b""
    had_content = False
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(65_536):
                had_content = True
                last_byte = chunk[-1:]
                lines += chunk.count(b"\n")
                if lines >= stop_at:
                    return lines, False
    except OSError:
        return 0, True
    if had_content and last_byte != b"\n":
        lines += 1
    return lines, True


def assess_project(project_root: Path) -> Readiness:
    root = project_root.resolve()
    files = discover_source_files(root)
    languages = tuple(sorted({SOURCE_LANGUAGES[path.suffix.lower()] for path in files}))
    active = (root / ".codegraph").is_dir()
    reasons: list[str] = []

    if len(files) >= FILE_THRESHOLD:
        reasons.append(f"source files reached {FILE_THRESHOLD}")
    if len(files) >= POLYGLOT_FILE_THRESHOLD and len(languages) >= LANGUAGE_THRESHOLD:
        reasons.append(
            f"{POLYGLOT_FILE_THRESHOLD}+ files span {LANGUAGE_THRESHOLD}+ languages"
        )

    source_lines: int | None = None
    source_lines_complete = False
    if not reasons:
        source_lines = 0
        source_lines_complete = True
        for path in files:
            line_count, complete = _count_lines(
                path,
                stop_at=LINE_THRESHOLD - source_lines,
            )
            source_lines += line_count
            if not complete or source_lines >= LINE_THRESHOLD:
                source_lines_complete = False
                reasons.append(f"source lines reached {LINE_THRESHOLD}")
                break

    recommended = bool(reasons)
    status = "active" if active else "recommended" if recommended else "defer"
    return Readiness(
        root=str(root),
        status=status,
        active=active,
        recommended=recommended,
        source_files=len(files),
        source_lines=source_lines,
        source_lines_complete=source_lines_complete,
        languages=languages,
        reasons=tuple(reasons),
    )


def render_summary(readiness: Readiness) -> str:
    if readiness.source_lines is None:
        line_text = "line count skipped after an earlier threshold"
    elif readiness.source_lines_complete:
        line_text = f"{readiness.source_lines} lines"
    else:
        line_text = f"at least {readiness.source_lines} lines"
    language_text = (
        ", ".join(readiness.languages)
        if readiness.languages
        else "no supported source language"
    )
    if readiness.status == "active":
        decision = "active; keep .codegraph/ local and untracked"
    elif readiness.status == "recommended":
        decision = f"recommended ({'; '.join(readiness.reasons)})"
    else:
        decision = (
            "defer; reconsider at 500 files, 50,000 lines, or "
            "200 files across 3 languages"
        )
    return (
        f"CodeGraph readiness: {decision}. "
        f"Observed {readiness.source_files} source files, {line_text}; "
        f"languages: {language_text}."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report whether a repository has enough supported source code "
            "to justify an optional local CodeGraph index."
        )
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Project root to assess. Defaults to the current directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.project_root.is_dir():
        print(f"Project root is not a directory: {args.project_root}")
        return 2

    readiness = assess_project(args.project_root)
    if args.json:
        print(json.dumps(asdict(readiness), ensure_ascii=False, indent=2))
    else:
        print(render_summary(readiness))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
