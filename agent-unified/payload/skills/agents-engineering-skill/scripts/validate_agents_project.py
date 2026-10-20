#!/usr/bin/env python3
"""Validate an AGENTS.md engineering workflow project."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".py",
    ".sh",
    ".cmd",
}
IGNORED_DIRECTORY_NAMES = {
    ".verification",
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
REQUIRED_AGENTS_HEADINGS = (
    "作用域与优先级",
    "每次开始前",
    "任务分级与工作流",
    "验证",
    "常用命令",
)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


@dataclass(frozen=True)
class Finding:
    level: str
    path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate AGENTS.md, skills, references, and template integrity."
    )
    parser.add_argument(
        "target",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Project or bundled template directory to validate.",
    )
    parser.add_argument(
        "--template",
        action="store_true",
        help="Allow {{TOKEN}} placeholders used by a distributable template.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write a machine-readable JSON report to stdout.",
    )
    parser.add_argument(
        "--skills-only",
        action="store_true",
        help="Validate skills and links without requiring an AGENTS.md file.",
    )
    return parser.parse_args()


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def is_ignored(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part in IGNORED_DIRECTORY_NAMES for part in relative_parts)


def add(
    findings: list[Finding],
    level: str,
    path: Path,
    root: Path,
    message: str,
) -> None:
    findings.append(Finding(level=level, path=relative(path, root), message=message))


def read_utf8(path: Path, root: Path, findings: list[Finding]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        add(findings, "error", path, root, f"不是有效 UTF-8：{error}")
    except OSError as error:
        add(findings, "error", path, root, f"无法读取：{error}")
    return None


def parse_frontmatter(content: str) -> dict[str, str] | None:
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None

    values: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def validate_text_files(root: Path, template: bool, findings: list[Finding]) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or is_ignored(path, root):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            "AGENTS.md",
            "SKILL.md",
        }:
            continue

        content = read_utf8(path, root, findings)
        if content is None:
            continue

        if path.suffix.lower() == ".json":
            try:
                json.loads(content)
            except json.JSONDecodeError as error:
                add(findings, "error", path, root, f"JSON 无效：{error}")

        placeholders = sorted(set(PLACEHOLDER_RE.findall(content)))
        if placeholders and not template:
            add(
                findings,
                "warning",
                path,
                root,
                "仍含模板占位符：" + ", ".join(placeholders),
            )


def validate_agents(root: Path, findings: list[Finding]) -> None:
    agents_files = sorted(
        path for path in root.rglob("AGENTS.md") if not is_ignored(path, root)
    )
    if not agents_files:
        add(findings, "error", root / "AGENTS.md", root, "缺少 AGENTS.md")
        return

    root_agents = root / "AGENTS.md"
    if not root_agents.exists():
        add(
            findings,
            "warning",
            agents_files[0],
            root,
            "目标目录没有根 AGENTS.md；仅发现嵌套规则。",
        )
        return

    content = read_utf8(root_agents, root, findings)
    if content is None:
        return

    line_count = len(content.splitlines())
    if line_count > 160:
        add(
            findings,
            "warning",
            root_agents,
            root,
            f"共 {line_count} 行；建议将根 AGENTS.md 控制在约 100 行并作为导航入口。",
        )

    for heading in REQUIRED_AGENTS_HEADINGS:
        if not re.search(rf"^##\s+.*{re.escape(heading)}", content, re.MULTILINE):
            add(findings, "error", root_agents, root, f"缺少章节：{heading}")


def validate_skill_file(
    skill_file: Path,
    root: Path,
    findings: list[Finding],
    expected_name: str | None,
) -> None:
    content = read_utf8(skill_file, root, findings)
    if content is None:
        return

    frontmatter = parse_frontmatter(content)
    if frontmatter is None:
        add(findings, "error", skill_file, root, "缺少有效 YAML frontmatter。")
        return

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        add(
            findings,
            "error",
            skill_file,
            root,
            f"frontmatter name={name!r} 必须使用小写连字符格式。",
        )
    if expected_name is not None and name != expected_name:
        add(
            findings,
            "error",
            skill_file,
            root,
            f"frontmatter name={name!r} 与目录名 {expected_name!r} 不一致。",
        )
    if not description:
        add(findings, "error", skill_file, root, "frontmatter 缺少 description。")
    elif not any(
        marker in description.lower()
        for marker in ("use when", "用于", "时使用", "需要")
    ):
        add(
            findings,
            "warning",
            skill_file,
            root,
            "description 应同时说明技能做什么以及何时触发。",
        )

    line_count = len(content.splitlines())
    if line_count > 500:
        add(
            findings,
            "warning",
            skill_file,
            root,
            f"共 {line_count} 行；建议使用 references/ 渐进披露。",
        )


def validate_skills(root: Path, findings: list[Finding]) -> None:
    skills_root = root / "skills"
    bundled_skills = root / "assets" / "agents-project-template" / "skills"
    workspace_skills = root / ".agents" / "skills"
    top_level_skill_packages = sorted(
        path / "SKILL.md"
        for path in root.iterdir()
        if path.is_dir()
        and not is_ignored(path, root)
        and (path / "SKILL.md").is_file()
    )
    if (
        not skills_root.exists()
        and (root / "SKILL.md").exists()
        and bundled_skills.exists()
    ):
        skills_root = bundled_skills
    elif not skills_root.exists() and workspace_skills.exists():
        skills_root = workspace_skills
    if not skills_root.exists():
        if top_level_skill_packages:
            for skill_file in top_level_skill_packages:
                validate_skill_file(skill_file, root, findings, expected_name=None)
            return
        add(findings, "warning", skills_root, root, "缺少 skills/；仅适合简单项目。")
        return

    root_skill = root / "SKILL.md"
    if root_skill.exists():
        validate_skill_file(root_skill, root, findings, expected_name=None)

    skill_dirs = sorted(path for path in skills_root.iterdir() if path.is_dir())
    if not skill_dirs:
        add(findings, "error", skills_root, root, "skills/ 中没有技能目录。")

    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            add(findings, "error", skill_file, root, "技能目录缺少 SKILL.md。")
            continue
        validate_skill_file(
            skill_file,
            root,
            findings,
            expected_name=skill_dir.name,
        )


def validate_links(root: Path, findings: list[Finding]) -> None:
    for path in sorted(root.rglob("*.md")):
        if is_ignored(path, root):
            continue
        content = read_utf8(path, root, findings)
        if content is None:
            continue
        for raw_target in MARKDOWN_LINK_RE.findall(content):
            target = raw_target.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "#")):
                continue
            decoded_target = target.replace("%20", " ")
            resolved = (path.parent / decoded_target).resolve()
            if not resolved.exists():
                add(
                    findings,
                    "error",
                    path,
                    root,
                    f"Markdown 链接目标不存在：{target}",
                )


def validate_project(
    root: Path,
    template: bool = False,
    skills_only: bool = False,
) -> list[Finding]:
    resolved_root = root.resolve()
    findings: list[Finding] = []
    if not resolved_root.exists():
        return [Finding("error", str(resolved_root), "目标目录不存在。")]
    if not resolved_root.is_dir():
        return [Finding("error", str(resolved_root), "目标不是目录。")]

    validate_text_files(resolved_root, template, findings)
    if not skills_only:
        validate_agents(resolved_root, findings)
    validate_skills(resolved_root, findings)
    validate_links(resolved_root, findings)
    return findings


def report(root: Path, findings: list[Finding], as_json: bool) -> None:
    counts = {
        "errors": sum(item.level == "error" for item in findings),
        "warnings": sum(item.level == "warning" for item in findings),
    }
    payload = {
        "target": str(root.resolve()),
        "valid": counts["errors"] == 0,
        **counts,
        "findings": [asdict(item) for item in findings],
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for item in findings:
        print(
            f"{item.level.upper()}: {item.path}: {item.message}",
            file=sys.stderr,
        )
    status = "PASS" if payload["valid"] else "FAIL"
    print(
        f"{status}: {payload['target']} "
        f"({counts['errors']} error(s), {counts['warnings']} warning(s))"
    )


def main() -> int:
    args = parse_args()
    findings = validate_project(
        args.target,
        template=args.template,
        skills_only=args.skills_only,
    )
    report(args.target, findings, as_json=args.json)
    return 1 if any(item.level == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
