"""公开安装器仅使用临时目录，验证冲突、回退及并发修改保护。"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install_skills
from engine.common import rollback, Transaction


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.home = self.root / 'home'
        skill = self.bundle / 'payload/skills/example'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('---\nname: example\ndescription: test\n---\n', encoding='utf-8')
        (self.bundle / 'config').mkdir()
        (self.bundle / 'config/AGENTS.md').write_text('# Rules\n', encoding='utf-8')

    def test_preview_has_no_writes(self):
        self.assertEqual(len(install_skills.plan_install(self.bundle, self.home)), 1)
        self.assertFalse(self.home.exists())

    def test_agents_share_install_transaction_and_rollback(self):
        folder = self.bundle / 'payload/agents'
        folder.mkdir()
        content = b'name = "example"\ndescription = "test"\ndeveloper_instructions = "read only"\n'
        (folder / 'example.toml').write_bytes(content)
        plan = install_skills.plan_install(self.bundle, self.home, True)
        backup = install_skills.apply_plan(plan, self.home)
        self.assertEqual((self.home / 'agents/example.toml').read_bytes(), content)
        self.assertEqual(install_skills.plan_install(self.bundle, self.home, True), [])
        rollback(backup)
        self.assertFalse((self.home / 'agents/example.toml').exists())
        self.assertFalse((self.home / 'skills/example/SKILL.md').exists())

    def test_agent_conflict_blocks_skill_writes(self):
        folder = self.bundle / 'payload/agents'
        folder.mkdir()
        content = b'name = "example"\ndescription = "test"\ndeveloper_instructions = "read only"\n'
        (folder / 'example.toml').write_bytes(content)
        target = self.home / 'agents/example.toml'
        target.parent.mkdir(parents=True)
        target.write_bytes(content.replace(b'read only', b'custom'))
        with self.assertRaises(ValueError):
            install_skills.plan_install(self.bundle, self.home)
        self.assertFalse((self.home / 'skills').exists())

    def test_new_duplicate_role_during_install_aborts_and_preserves_edit(self):
        folder = self.bundle / 'payload/agents'
        folder.mkdir()
        content = b'name = "example"\ndescription = "test"\ndeveloper_instructions = "read only"\n'
        (folder / 'example.toml').write_bytes(content)
        plan = install_skills.plan_install(self.bundle, self.home)
        concurrent = self.home / 'agents/other.toml'
        original_save = Transaction.save

        def save_with_concurrent_role(transaction, target, data, mode=0o644):
            result = original_save(transaction, target, data, mode)
            if target.name == 'example.toml':
                concurrent.write_bytes(content)
            return result

        with mock.patch.object(Transaction, 'save', save_with_concurrent_role):
            with self.assertRaises(RuntimeError):
                install_skills.apply_plan(plan, self.home)
        self.assertEqual(concurrent.read_bytes(), content)
        self.assertFalse((self.home / 'agents/example.toml').exists())
        self.assertFalse((self.home / 'skills/example/SKILL.md').exists())

    def test_install_idempotence_and_rollback(self):
        plan = install_skills.plan_install(self.bundle, self.home, True)
        backup = install_skills.apply_plan(plan, self.home)
        self.assertEqual(install_skills.plan_install(self.bundle, self.home, True), [])
        self.assertTrue((self.home / 'AGENTS.md').is_file())
        rollback(backup)
        self.assertFalse((self.home / 'AGENTS.md').exists())
        self.assertFalse((self.home / 'skills/example/SKILL.md').exists())

    def test_conflict_is_detected_before_changes(self):
        self.home.mkdir()
        (self.home / 'AGENTS.md').write_text('keep', encoding='utf-8')
        with self.assertRaises(ValueError):
            install_skills.plan_install(self.bundle, self.home, True)
        self.assertFalse((self.home / 'skills').exists())

    def test_replace_keeps_backup(self):
        self.home.mkdir()
        (self.home / 'AGENTS.md').write_text('keep', encoding='utf-8')
        plan = install_skills.plan_install(self.bundle, self.home, True, True)
        backup = install_skills.apply_plan(plan, self.home)
        rollback(backup)
        self.assertEqual((self.home / 'AGENTS.md').read_text(), 'keep')

    def test_concurrent_edit_is_preserved(self):
        plan = install_skills.plan_install(self.bundle, self.home)
        target = plan[0][0]
        target.parent.mkdir(parents=True)
        target.write_text('concurrent', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            install_skills.apply_plan(plan, self.home)
        self.assertEqual(target.read_text(), 'concurrent')

    def test_partial_failure_rolls_back(self):
        plan = install_skills.plan_install(self.bundle, self.home, True)
        original = Transaction.save
        def fail_second(transaction, target, data, mode=0o644):
            if transaction.records:
                raise OSError('simulated write failure')
            return original(transaction, target, data, mode)
        with mock.patch.object(Transaction, 'save', fail_second), self.assertRaises(OSError):
            install_skills.apply_plan(plan, self.home)
        self.assertFalse((self.home / 'skills/example/SKILL.md').exists())

    def test_symlink_target_is_rejected(self):
        actual = self.root / 'actual'
        actual.mkdir()
        try:
            self.home.symlink_to(actual, target_is_directory=True)
        except OSError:
            self.skipTest('当前系统未允许符号链接；完整恢复器另测 Windows 联接')
        with self.assertRaises(ValueError):
            install_skills.plan_install(self.bundle, self.home)


if __name__ == '__main__':
    unittest.main()
