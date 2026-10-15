#!/usr/bin/env python3
"""Run the dependency-free AGENTS engineering quality gate."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from codegraph_readiness import assess_project, render_summary


SKILL_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = SKILL_ROOT / "scripts" / "validate_agents_project.py"
TEMPLATE = SKILL_ROOT / "assets" / "agents-project-template"
IGNORED_DIRECTORY_NAMES = {
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


def detect_workspace_root() -> Path:
    """Support both this monorepo layout and a standalone skill checkout."""
    if (SKILL_ROOT / ".git").exists():
        return SKILL_ROOT
    if (SKILL_ROOT.parent / ".git").exists():
        return SKILL_ROOT.parent
    return SKILL_ROOT.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the AGENTS engineering skill, bundled template, "
            "workspace skills, tests, and available optional linters."
        )
    )
    parser.add_argument(
        "--workspace-root",
        "-WorkspaceRoot",
        type=Path,
        default=detect_workspace_root(),
        help=(
            "Workspace containing an optional .agents/skills directory. "
            "Defaults to the surrounding Git checkout."
        ),
    )
    optional = parser.add_mutually_exclusive_group()
    optional.add_argument(
        "--skip-optional-tools",
        "-SkipOptionalTools",
        action="store_true",
        help="Run only the dependency-free checks.",
    )
    optional.add_argument(
        "--require-optional-tools",
        "-RequireOptionalTools",
        action="store_true",
        help=(
            "Fail when any relevant enhanced tool is unavailable "
            "(intended for the pinned Linux CI job)."
        ),
    )
    return parser.parse_args()


class CheckRunner:
    def __init__(self, require_optional_tools: bool) -> None:
        self.failures = 0
        self.skipped = 0
        self.require_optional_tools = require_optional_tools
        self.environment = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def run(
        self,
        name: str,
        command: list[str],
        cwd: Path = SKILL_ROOT,
    ) -> bool:
        print(f"[RUN ] {name}", flush=True)
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                env=self.environment,
            )
        except OSError as error:
            print(f"[FAIL] {name} - {error}", file=sys.stderr, flush=True)
            self.failures += 1
            return False

        if result.returncode == 0:
            print(f"[PASS] {name}", flush=True)
            return True

        print(
            f"[FAIL] {name} - exit code {result.returncode}",
            file=sys.stderr,
            flush=True,
        )
        self.failures += 1
        return False

    def skip(self, message: str, required: bool = False) -> None:
        self.skipped += 1
        if required:
            self.failures += 1
            print(f"[FAIL] {message}", file=sys.stderr, flush=True)
        else:
            print(f"[SKIP] {message}", flush=True)

    def find_optional(
        self,
        name: str,
        command_names: tuple[str, ...],
    ) -> str | None:
        for command_name in command_names:
            executable = shutil.which(command_name)
            if executable is not None:
                return executable
        self.skip(
            f"{name} is not installed",
            required=self.require_optional_tools,
        )
        return None

    def run_optional(
        self,
        name: str,
        command_names: tuple[str, ...],
        arguments: list[str],
        cwd: Path,
    ) -> None:
        executable = self.find_optional(name, command_names)
        if executable is not None:
            self.run(name, [executable, *arguments], cwd=cwd)


def validate_core(runner: CheckRunner, workspace_root: Path) -> None:
    python = sys.executable
    runner.run(
        "Validate AGENTS engineering skill",
        [python, str(VALIDATOR), str(SKILL_ROOT), "--template"],
    )
    runner.run(
        "Validate bundled project template",
        [python, str(VALIDATOR), str(TEMPLATE), "--template"],
    )

    workspace_agents = workspace_root.resolve() / ".agents"
    if (workspace_agents / "skills").is_dir():
        runner.run(
            "Validate workspace-level skills",
            [python, str(VALIDATOR), str(workspace_agents), "--skills-only"],
        )
    else:
        runner.skip("No workspace-level .agents/skills directory")

    runner.run(
        "Run regression tests",
        [python, "-m", "unittest", "discover", "-s", "tests", "-v"],
    )


def report_git_status(runner: CheckRunner, workspace_root: Path) -> None:
    git = shutil.which("git")
    if git is None:
        runner.skip("git is not installed")
        return

    try:
        probe = subprocess.run(
            [
                git,
                "-C",
                str(workspace_root),
                "rev-parse",
                "--is-inside-work-tree",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            env=runner.environment,
        )
    except OSError as error:
        runner.skip(f"git status is unavailable: {error}")
        return

    if probe.returncode != 0:
        runner.skip("Skill directory is not inside a Git working tree")
        return

    runner.run(
        "Git working tree status",
        [git, "-C", str(workspace_root), "status", "--short"],
    )


def _relevant_files(root: Path, suffix: str) -> list[Path]:
    return sorted(
        path
        for path in root.rglob(f"*{suffix}")
        if path.is_file()
        and not any(
            part in IGNORED_DIRECTORY_NAMES for part in path.relative_to(root).parts
        )
    )


def _is_git_worktree(root: Path) -> bool:
    git = shutil.which("git")
    if git is None:
        return False
    try:
        result = subprocess.run(
            [git, "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def run_optional_tools(runner: CheckRunner, workspace_root: Path) -> None:
    root = workspace_root.resolve()
    markdown_files = _relevant_files(root, ".md")
    if markdown_files:
        runner.run_optional(
            "Markdown lint",
            ("markdownlint-cli2", "markdownlint-cli2.cmd"),
            ["**/*.md"],
            cwd=root,
        )
        runner.run_optional(
            "Local Markdown link check",
            ("lychee", "lychee.exe"),
            [
                "--offline",
                "--no-progress",
                "--exclude-path",
                r"(^|[\\/])(node_modules|\.codegraph|\.git|vendor|build|dist|target)"
                r"([\\/]|$)",
                "**/*.md",
            ],
            cwd=root,
        )
    else:
        runner.skip("No Markdown files require enhanced checks")

    workflow_files = sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in root.rglob(pattern)
        if path.is_file()
        and ".github" in path.parts
        and "workflows" in path.parts
        and not any(
            part in IGNORED_DIRECTORY_NAMES for part in path.relative_to(root).parts
        )
    )
    if workflow_files:
        runner.run_optional(
            "GitHub Actions lint",
            ("actionlint", "actionlint.exe"),
            [str(path) for path in workflow_files],
            cwd=root,
        )
        runner.run_optional(
            "GitHub Actions security audit",
            ("zizmor", "zizmor.exe"),
            ["--offline", "--strict-collection", "."],
            cwd=root,
        )
    else:
        runner.skip("No GitHub Actions workflows require enhanced checks")

    if _relevant_files(root, ".py"):
        ruff = runner.find_optional("Ruff", ("ruff", "ruff.exe"))
        if ruff is not None:
            runner.run("Python lint", [ruff, "check", "."], cwd=root)
            runner.run(
                "Python format check",
                [ruff, "format", "--check", "."],
                cwd=root,
            )
    else:
        runner.skip("No Python files require Ruff")

    shell_files = _relevant_files(root, ".sh")
    if shell_files:
        shellcheck = runner.find_optional(
            "ShellCheck",
            ("shellcheck", "shellcheck.exe"),
        )
        if shellcheck is not None:
            runner.run(
                "Shell script lint",
                [shellcheck, *[str(path) for path in shell_files]],
                cwd=root,
            )
    else:
        runner.skip("No shell scripts require ShellCheck")

    gitleaks = runner.find_optional(
        "Gitleaks",
        ("gitleaks", "gitleaks.exe"),
    )
    if gitleaks is not None:
        scan_mode = "git" if _is_git_worktree(root) else "dir"
        runner.run(
            "Secret scan",
            [
                gitleaks,
                "--no-banner",
                "--no-color",
                "--redact",
                scan_mode,
                ".",
            ],
            cwd=root,
        )


def main() -> int:
    args = parse_args()
    runner = CheckRunner(require_optional_tools=args.require_optional_tools)
    workspace_root = args.workspace_root.resolve()

    validate_core(runner, workspace_root)
    print(f"[INFO] {render_summary(assess_project(workspace_root))}", flush=True)
    report_git_status(runner, workspace_root)
    if not args.skip_optional_tools:
        run_optional_tools(runner, workspace_root)

    print()
    if runner.failures == 0:
        print(f"PASS: all required checks completed ({runner.skipped} skipped).")
        return 0

    print(
        f"FAIL: {runner.failures} check(s) failed ({runner.skipped} skipped).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
