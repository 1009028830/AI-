from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
INIT_SCRIPT = ROOT / "scripts" / "init_agents_project.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_agents_project.py"
CHECK_SCRIPT = ROOT / "scripts" / "check_project.py"
CODEGRAPH_SCRIPT = ROOT / "scripts" / "codegraph_readiness.py"
CHECK_SH_WRAPPER = ROOT / "scripts" / "check-project.sh"
CHECK_CMD_WRAPPER = ROOT / "scripts" / "check-project.cmd"
TEMPLATE = ROOT / "assets" / "agents-project-template"


class AgentsEngineeringTests(unittest.TestCase):
    def run_command(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

    def test_bundled_template_is_valid(self) -> None:
        result = self.run_command(
            str(VALIDATE_SCRIPT),
            str(TEMPLATE),
            "--template",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], 0)

        agents = (TEMPLATE / "AGENTS.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(agents.splitlines()), 120)
        for level in ("L0", "L1", "L2", "L3"):
            self.assertIn(level, agents)
        self.assertIn("references/definition-of-done.md", agents)

    def test_openai_metadata_matches_skill(self) -> None:
        metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$agents-engineering-skill", metadata)
        self.assertIn('display_name: "AGENTS 工程系统"', metadata)
        self.assertIn("创建、审计或升级", metadata)

    def test_initializer_renders_project_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sample-project"
            result = self.run_command(
                str(INIT_SCRIPT),
                "--target",
                str(target),
                "--project-name",
                "CAN Console",
                "--project-overview",
                "Qt/C++ CAN diagnostics application.",
                "--build-command",
                "cmake --build build",
                "--test-command",
                "ctest --test-dir build",
                "--run-command",
                "./build/can-console --smoke",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            agents = (target / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("CAN Console", agents)
            self.assertIn("cmake --build build", agents)
            self.assertIn("ctest --test-dir build", agents)
            self.assertNotIn("{{PROJECT_NAME}}", agents)
            self.assertTrue(
                (target / "scripts" / "validate_agents_project.py").exists()
            )

            validation = self.run_command(
                str(target / "scripts" / "validate_agents_project.py"),
                str(target),
                "--json",
            )
            self.assertEqual(
                validation.returncode,
                0,
                validation.stderr + validation.stdout,
            )

    def test_initializer_does_not_overwrite_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "existing"
            target.mkdir()
            agents_path = target / "AGENTS.md"
            agents_path.write_text("# Existing\n", encoding="utf-8")

            result = self.run_command(
                str(INIT_SCRIPT),
                "--target",
                str(target),
                "--no-validate",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(agents_path.read_text(encoding="utf-8"), "# Existing\n")
            self.assertIn("Skipped 1 existing file", result.stdout)

    def test_validator_rejects_skill_name_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            (target / "skills" / "right-name").mkdir(parents=True)
            (target / "AGENTS.md").write_text(
                "\n".join(
                    [
                        "# AGENTS.md",
                        "## 作用域与优先级",
                        "## 每次开始前",
                        "## 任务分级与工作流",
                        "## 验证",
                        "## 常用命令",
                    ]
                ),
                encoding="utf-8",
            )
            (target / "skills" / "right-name" / "SKILL.md").write_text(
                "---\nname: wrong-name\ndescription: 用于测试时使用。\n---\n# Test\n",
                encoding="utf-8",
            )

            result = self.run_command(
                str(VALIDATE_SCRIPT),
                str(target),
                "--json",
            )
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertFalse(report["valid"])
            self.assertTrue(
                any("目录名" in item["message"] for item in report["findings"])
            )

    def test_skills_only_mode_does_not_require_agents_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            skill = target / "skills" / "focused-check"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: focused-check\n"
                "description: Validate focused checks. Use when a project needs proof.\n"
                "---\n"
                "# Focused check\n",
                encoding="utf-8",
            )

            result = self.run_command(
                str(VALIDATE_SCRIPT),
                str(target),
                "--skills-only",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertTrue(report["valid"])
            self.assertEqual(report["errors"], 0)

    def test_validator_ignores_dependencies_and_local_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "sample-project"
            initialized = self.run_command(
                str(INIT_SCRIPT),
                "--target",
                str(target),
                "--no-validate",
            )
            self.assertEqual(
                initialized.returncode,
                0,
                initialized.stderr + initialized.stdout,
            )

            dependency = target / "node_modules" / "dependency"
            dependency.mkdir(parents=True)
            (dependency / "README.md").write_text(
                "[missing](not-packaged.md)\n",
                encoding="utf-8",
            )
            local_index = target / ".codegraph"
            local_index.mkdir()
            (local_index / "invalid.json").write_text("{", encoding="utf-8")

            result = self.run_command(
                str(VALIDATE_SCRIPT),
                str(target),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertTrue(report["valid"])
            self.assertEqual(report["errors"], 0)

    def test_top_level_skill_package_is_valid_for_catalog_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            package = target / "reusable-agent-workflow"
            package.mkdir()
            (target / "AGENTS.md").write_text(
                "\n".join(
                    [
                        "# AGENTS.md",
                        "## 作用域与优先级",
                        "## 每次开始前",
                        "## 任务分级与工作流",
                        "## 验证",
                        "## 常用命令",
                    ]
                ),
                encoding="utf-8",
            )
            (package / "SKILL.md").write_text(
                "---\n"
                "name: agent-workflow\n"
                "description: Build agent workflows. Use when a repository needs one.\n"
                "---\n"
                "# Agent workflow\n",
                encoding="utf-8",
            )

            result = self.run_command(
                str(VALIDATE_SCRIPT),
                str(target),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["errors"], 0)
            self.assertEqual(report["warnings"], 0)

    def test_unified_check_is_cross_platform_and_covers_tools(self) -> None:
        content = CHECK_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("validate_agents_project.py", content)
        self.assertIn('"unittest"', content)
        for tool in (
            "markdownlint-cli2",
            "lychee",
            "actionlint",
            "zizmor",
            "ruff",
            "shellcheck",
            "gitleaks",
        ):
            self.assertIn(tool, content)
        self.assertIn("assess_project", content)
        self.assertIn("--skills-only", content)
        self.assertNotIn("powershell", content.lower())
        self.assertNotIn("cmd.exe", content.lower())

        shell_wrapper = CHECK_SH_WRAPPER.read_text(encoding="utf-8")
        self.assertIn("python3", shell_wrapper)
        self.assertIn("check_project.py", shell_wrapper)

        cmd_wrapper = CHECK_CMD_WRAPPER.read_text(encoding="utf-8")
        self.assertNotIn("powershell", cmd_wrapper.lower())
        self.assertIn("check_project.py", cmd_wrapper)

    def test_unified_check_help_is_available(self) -> None:
        result = self.run_command(str(CHECK_SCRIPT), "--help")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("--workspace-root", result.stdout)
        self.assertIn("--skip-optional-tools", result.stdout)

    def test_codegraph_readiness_ignores_docs_and_defers_for_small_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "build" / "sample-project"
            target.mkdir(parents=True)
            (target / "first.py").write_text("print('first')\n", encoding="utf-8")
            (target / "second.py").write_text("print('second')\n", encoding="utf-8")
            (target / "README.md").write_text("# Documentation\n", encoding="utf-8")

            result = self.run_command(str(CODEGRAPH_SCRIPT), str(target), "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "defer")
            self.assertEqual(report["source_files"], 2)
            self.assertEqual(report["languages"], ["Python"])

    def test_codegraph_readiness_recommends_at_file_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            for index in range(500):
                (target / f"module_{index:03}.py").touch()

            result = self.run_command(str(CODEGRAPH_SCRIPT), str(target), "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "recommended")
            self.assertTrue(report["recommended"])
            self.assertEqual(report["source_files"], 500)

    def test_codegraph_readiness_reports_existing_local_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            (target / ".codegraph").mkdir()

            result = self.run_command(str(CODEGRAPH_SCRIPT), str(target), "--json")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "active")
            self.assertTrue(report["active"])

    def test_enhanced_ci_is_pinned_and_reproducible(self) -> None:
        # 技能既可独立安装，也可位于聚合仓库；父仓库 CI 不是技能载荷。
        workflows = [ROOT / ".github" / "workflows" / "validate.yml"]
        parent_workflow = REPOSITORY_ROOT / ".github" / "workflows" / "validate-agents-engineering.yml"
        if parent_workflow.is_file():
            workflows.append(parent_workflow)
        for workflow in workflows:
            content = workflow.read_text(encoding="utf-8")
            action_refs = re.findall(
                r"^\s*-\s+uses:\s+\S+@(\S+)",
                content,
                flags=re.MULTILINE,
            )
            self.assertTrue(action_refs, workflow)
            for action_ref in action_refs:
                self.assertRegex(action_ref, r"^[0-9a-f]{40}$")
            self.assertIn("persist-credentials: false", content)
            self.assertIn("concurrency:", content)
            self.assertIn("cancel-in-progress: true", content)
            self.assertIn("ruff==0.15.14", content)
            self.assertIn("zizmor==1.28.0", content)
            self.assertNotIn("zizmor==1.27.0", content)

        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads(
            (ROOT / "package-lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            package["devDependencies"]["markdownlint-cli2"],
            "0.23.2",
        )
        self.assertEqual(package_lock["lockfileVersion"], 3)
        self.assertIn(".codegraph/", (ROOT / ".gitignore").read_text())
        self.assertIn("--redact", CHECK_SCRIPT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
