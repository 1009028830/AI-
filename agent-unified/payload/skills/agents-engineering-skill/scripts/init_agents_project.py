#!/usr/bin/env python3
"""Initialize a reusable AGENTS.md engineering workflow in a target project."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import shutil
import sys

from validate_agents_project import validate_project


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = SKILL_DIR / "assets" / "agents-project-template"
VALIDATOR_SOURCE = SKILL_DIR / "scripts" / "validate_agents_project.py"
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".py",
    ".sh",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy the bundled AGENTS.md engineering workflow template into a project."
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="Target project directory to initialize.",
    )
    parser.add_argument(
        "--project-name",
        help="Project name rendered into AGENTS.md. Defaults to the target directory name.",
    )
    parser.add_argument(
        "--project-overview",
        default="在这里补充项目定位、业务目标、主要运行环境和验收口径。",
        help="Short project overview rendered into AGENTS.md.",
    )
    parser.add_argument(
        "--build-command",
        default="# TODO: 补充本项目构建命令",
        help="Primary build command rendered into AGENTS.md.",
    )
    parser.add_argument(
        "--test-command",
        default="# TODO: 补充本项目测试命令",
        help="Primary test command rendered into AGENTS.md.",
    )
    parser.add_argument(
        "--run-command",
        default="# TODO: 补充本项目运行命令",
        help="Primary run or smoke-test command rendered into AGENTS.md.",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Date rendered into template files. Defaults to today.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in the target project.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned file actions without writing files.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation after files are written.",
    )
    return parser.parse_args()


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {
        "AGENTS.md",
        "SKILL.md",
    }


def render_text(raw: str, replacements: dict[str, str]) -> str:
    rendered = raw
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def copy_template(
    target: Path,
    replacements: dict[str, str],
    overwrite: bool,
    dry_run: bool,
) -> tuple[list[Path], list[Path]]:
    written: list[Path] = []
    skipped: list[Path] = []

    for source in sorted(TEMPLATE_DIR.rglob("*")):
        relative = source.relative_to(TEMPLATE_DIR)
        destination = target / relative

        if source.is_dir():
            if not dry_run:
                destination.mkdir(parents=True, exist_ok=True)
            continue

        if destination.exists() and not overwrite:
            skipped.append(relative)
            continue

        written.append(relative)
        if dry_run:
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        if is_text_file(source):
            content = render_text(source.read_text(encoding="utf-8"), replacements)
            destination.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(source, destination)

    validator_relative = Path("scripts/validate_agents_project.py")
    validator_destination = target / validator_relative
    if validator_destination.exists() and not overwrite:
        skipped.append(validator_relative)
    else:
        written.append(validator_relative)
        if not dry_run:
            validator_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(VALIDATOR_SOURCE, validator_destination)

    return written, skipped


def main() -> int:
    args = parse_args()

    if not TEMPLATE_DIR.exists():
        print(f"Template directory not found: {TEMPLATE_DIR}", file=sys.stderr)
        return 2
    if not VALIDATOR_SOURCE.exists():
        print(f"Validator not found: {VALIDATOR_SOURCE}", file=sys.stderr)
        return 2

    target = args.target.resolve()
    project_name = args.project_name or target.name
    replacements = {
        "{{PROJECT_NAME}}": project_name,
        "{{PROJECT_OVERVIEW}}": args.project_overview,
        "{{DATE}}": args.date,
        "{{BUILD_COMMAND}}": args.build_command,
        "{{TEST_COMMAND}}": args.test_command,
        "{{RUN_COMMAND}}": args.run_command,
    }

    if not args.dry_run:
        target.mkdir(parents=True, exist_ok=True)

    written, skipped = copy_template(
        target=target,
        replacements=replacements,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    action = "Would write" if args.dry_run else "Wrote"
    print(f"{action} {len(written)} file(s) into {target}")
    for path in written:
        print(f"  + {path}")

    if skipped:
        print(
            f"Skipped {len(skipped)} existing file(s); rerun with --overwrite to replace them."
        )
        for path in skipped:
            print(f"  = {path}")

    if not args.dry_run and not args.no_validate:
        findings = validate_project(target)
        errors = [item for item in findings if item.level == "error"]
        warnings = [item for item in findings if item.level == "warning"]
        print(f"Validation: {len(errors)} error(s), {len(warnings)} warning(s).")
        for item in errors + warnings:
            print(f"  {item.level.upper()}: {item.path}: {item.message}")
        if errors:
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
