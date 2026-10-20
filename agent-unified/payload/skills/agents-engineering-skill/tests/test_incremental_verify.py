"""验证可观察执行行为与缓存失效，不以文案匹配代替行为测试。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "assets/agents-project-template/scripts/verify.py"


class IncrementalVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src/a.txt").write_text("a", encoding="utf-8")
        (self.root / "check.py").write_text(
            "from pathlib import Path\nimport sys\n"
            "p=Path(sys.argv[1]); p.write_text(p.read_text()+'x' if p.exists() else 'x')\n",
            encoding="utf-8")
        self.tasks = [self.task("a")]

    def task(self, name, **extra):
        return {"id": name, "command": ["{python}", "check.py", name + ".count"],
                "inputs": ["src/*.txt", "check.py"], "cache": True, **extra}

    def invoke(self, *args, expected=0, env=None):
        (self.root / "verification.json").write_text(
            json.dumps({"version": 1, "tasks": self.tasks}), encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(RUNNER), "--root", str(self.root), *args],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})}, timeout=25)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def statuses(self):
        report = json.loads((self.root / ".verification/report.json").read_text(encoding="utf-8"))
        return {r["id"]: r["status"] for r in report["results"]}

    def test_preview_has_no_side_effects(self):
        self.invoke()
        self.assertFalse((self.root / ".verification").exists())
        self.assertFalse((self.root / "a.count").exists())

    def test_success_reuse_and_force(self):
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "passed"})
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "reused"})
        self.invoke("--run", "--force")
        self.assertEqual((self.root / "a.count").read_text(), "xx")

    def test_content_addition_and_deletion_invalidate(self):
        self.invoke("--run")
        (self.root / "src/a.txt").write_text("changed")
        self.invoke("--run")
        (self.root / "src/b.txt").write_text("new")
        self.invoke("--run")
        (self.root / "src/b.txt").unlink()
        self.invoke("--run")
        self.assertEqual((self.root / "a.count").read_text(), "xxxx")

    def test_unrelated_file_and_new_task_do_not_invalidate(self):
        self.invoke("--run")
        (self.root / "unrelated.md").write_text("notes")
        self.tasks.append(self.task("b"))
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "reused", "b": "passed"})

    def test_missing_input_blocks_instead_of_passing(self):
        self.invoke("--run")
        (self.root / "src/a.txt").unlink()
        self.invoke("--run", expected=1)
        self.assertEqual(self.statuses(), {"a": "blocked"})
        self.assertEqual(json.loads((self.root / ".verification/cache.json").read_text()), {})

    def test_missing_output_requires_rebuild(self):
        self.tasks[0]["outputs"] = ["a.count"]
        self.invoke("--run")
        (self.root / "a.count").unlink()
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "passed"})

    def test_failure_clears_previous_success_even_if_code_reverts(self):
        self.invoke("--run")
        p = self.root / "check.py"
        good = p.read_text()
        p.write_text("raise SystemExit(7)\n")
        self.invoke("--run", expected=1)
        self.assertEqual(self.statuses(), {"a": "failed"})
        p.write_text(good)
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "passed"})

    def test_input_mutation_during_run_is_not_cached(self):
        (self.root / "check.py").write_text("from pathlib import Path\nPath('src/a.txt').write_text('changed')\n")
        self.invoke("--run", expected=1)
        self.assertEqual(self.statuses(), {"a": "failed"})

    def test_dependencies_and_failed_parent(self):
        self.tasks.append(self.task("b", depends_on=["a"]))
        self.invoke("--run", "--only", "b")
        self.assertEqual(list(self.statuses()), ["a", "b"])
        (self.root / "check.py").write_text("raise SystemExit(3)\n")
        self.invoke("--run", "--only", "b", expected=1)
        self.assertEqual(self.statuses(), {"a": "failed", "b": "blocked"})

    def test_uncached_parent_prevents_child_reuse(self):
        self.tasks[0]["cache"] = False
        self.tasks.append(self.task("b", depends_on=["a"]))
        self.invoke("--run")
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "passed", "b": "passed"})

    def test_environment_change_invalidates(self):
        self.invoke("--run", env={"VERIFY_TEST_VARIANT": "one"})
        self.invoke("--run", env={"VERIFY_TEST_VARIANT": "two"})
        self.assertEqual(self.statuses(), {"a": "passed"})

    def test_device_requires_explicit_selection_and_never_caches(self):
        self.tasks[0].update(scope="device", cache=False)
        self.invoke("--run", expected=1)
        self.assertFalse((self.root / "a.count").exists())
        self.invoke("--run", "--allow-external", expected=1)
        # 此处仅执行临时文件计数脚本，不操作真实设备。
        self.invoke("--run", "--only", "a", "--allow-external")
        self.invoke("--run", "--only", "a", "--allow-external")
        self.assertEqual((self.root / "a.count").read_text(), "xx")

    def test_invalid_configs_fail_closed(self):
        original = self.tasks[0].copy()
        for change in ({"inputs": ["../outside"]}, {"inputs": ["missing.txt"], "cache": "yes"},
                       {"depends_on": ["a"]}, {"scope": "device", "cache": True},
                       {"timeout": -1}, {"commmand": ["typo"]}):
            with self.subTest(change=change):
                self.tasks = [{**original, **change}]
                self.invoke("--run", expected=2)
        self.tasks = [original]
        self.invoke("--run", "--only", "unknown", expected=2)

    def test_platform_skip_is_not_success(self):
        self.tasks[0]["platforms"] = ["linux" if sys.platform == "win32" else "windows"]
        self.invoke("--run", expected=1)
        self.assertEqual(self.statuses(), {"a": "not_applicable"})

    def test_timeout_is_failure_and_releases_lock(self):
        self.tasks[0]["timeout"] = 0.15
        (self.root / "check.py").write_text("import time\ntime.sleep(10)\n")
        self.invoke("--run", expected=1)
        self.assertEqual(self.statuses(), {"a": "failed"})
        self.assertFalse((self.root / ".verification/run.lock").exists())

    def test_lock_is_not_removed_by_second_invocation(self):
        (self.root / ".verification").mkdir()
        lock = self.root / ".verification/run.lock"
        lock.write_text("another run")
        self.invoke("--run", expected=2)
        self.assertEqual(lock.read_text(), "another run")

    def test_corrupt_cache_reruns(self):
        self.invoke("--run")
        (self.root / ".verification/cache.json").write_text("broken")
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "passed"})

    def test_missing_executable_is_blocked(self):
        self.tasks[0]["command"] = ["definitely-nonexistent-verify-tool-387431"]
        self.invoke("--run", expected=1)
        self.assertEqual(self.statuses(), {"a": "blocked"})

    def test_parent_change_invalidates_child_with_independent_inputs(self):
        (self.root / "b.txt").write_text("child")
        self.tasks.append(self.task("b", inputs=["b.txt", "check.py"], depends_on=["a"]))
        self.invoke("--run")
        (self.root / "src/a.txt").write_text("parent changed")
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "passed", "b": "passed"})

    def test_missing_declared_output_is_not_success(self):
        self.tasks[0]["outputs"] = ["never-produced.bin"]
        self.invoke("--run", expected=1)
        self.assertEqual(self.statuses(), {"a": "blocked"})

    def test_shell_characters_remain_literal_arguments(self):
        self.tasks[0]["command"] = ["{python}", "-c",
            "import sys; assert sys.argv[1] == 'a & echo unexpected'", "a & echo unexpected"]
        self.invoke("--run")
        self.assertEqual(self.statuses(), {"a": "passed"})

    def test_symlink_outside_root_is_blocked(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "secret.txt"
            target.write_text("outside")
            link = self.root / "src/link.txt"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("当前环境不允许创建符号链接")
            self.invoke("--run", expected=1)
            self.assertEqual(self.statuses(), {"a": "blocked"})


if __name__ == "__main__":
    unittest.main()
