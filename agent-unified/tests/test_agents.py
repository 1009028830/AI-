"""角色安装行为测试，仅操作临时目录。"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install_agents
from engine.agents import plan_agents, validate_agent_plan
from engine.common import Transaction, rollback


def role(name='reviewer', description='审查本次差异'):
    return ('name = "' + name + '"\ndescription = "' + description
            + '"\ndeveloper_instructions = "遵守授权范围。"\n').encode('utf-8')


class AgentInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / 'bundle'
        self.home = self.root / 'home'
        self.payload = self.bundle / 'payload/agents'
        self.payload.mkdir(parents=True)
        (self.payload / 'reviewer.toml').write_bytes(role())

    def existing(self, filename='reviewer.toml', data=None):
        target = self.home / 'agents' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(role(description='旧描述') if data is None else data)
        return target

    def test_preview_does_not_write(self):
        self.assertEqual(len(plan_agents(self.bundle, self.home)), 1)
        self.assertFalse(self.home.exists())

    def test_old_bundle_without_agents(self):
        self.assertEqual(plan_agents(self.root / 'old_bundle', self.home), [])
        self.assertFalse(self.home.exists())

    def test_shipped_roles_are_valid_and_preserve_client_config(self):
        bundle = Path(__file__).resolve().parents[1]
        self.home.mkdir()
        config = self.home / 'config.toml'
        config.write_bytes(b'model = "keep"\n[agents]\nenabled = false\n')
        before = config.read_bytes()
        plan = plan_agents(bundle, self.home)
        self.assertEqual(
            {p.stem for p, _, _ in plan},
            {'architecture_explorer', 'docs_researcher', 'software_worker',
             'firmware_worker', 'linux_worker', 'test_engineer',
             'code_reviewer', 'protocol_safety'},
        )
        install_agents.apply_plan(plan, self.home)
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(plan_agents(bundle, self.home), [])

    def test_install_idempotent_and_rollback(self):
        plan = plan_agents(self.bundle, self.home)
        backup = install_agents.apply_plan(plan, self.home)
        self.assertEqual((self.home / 'agents/reviewer.toml').read_bytes(), role())
        self.assertEqual(plan_agents(self.bundle, self.home), [])
        self.assertIsNone(install_agents.apply_plan([], self.home))
        rollback(backup)
        self.assertFalse((self.home / 'agents/reviewer.toml').exists())

    def test_conflict_before_any_changes(self):
        target = self.existing()
        (self.payload / 'implementer.toml').write_bytes(role('implementer'))
        with self.assertRaises(ValueError):
            plan_agents(self.bundle, self.home)
        self.assertEqual(target.read_bytes(), role(description='旧描述'))
        self.assertFalse((self.home / 'agents/implementer.toml').exists())

    def test_explicit_replace_can_rollback(self):
        target = self.existing()
        backup = install_agents.apply_plan(plan_agents(self.bundle, self.home, True), self.home)
        self.assertEqual(target.read_bytes(), role())
        rollback(backup)
        self.assertEqual(target.read_bytes(), role(description='旧描述'))

    def test_other_file_same_name_never_overridden(self):
        self.existing('other.toml', role())
        for replace in (False, True):
            with self.assertRaisesRegex(ValueError, '同名'):
                plan_agents(self.bundle, self.home, replace)

    def test_existing_duplicate_names_block(self):
        self.existing('one.toml', role('other'))
        self.existing('two.toml', role('other'))
        with self.assertRaisesRegex(ValueError, '重复'):
            plan_agents(self.bundle, self.home)

    def test_unrelated_official_fields_are_preserved(self):
        target = self.existing('other.toml', role('other') + b'model = "existing"\n')
        before = target.read_bytes()
        install_agents.apply_plan(plan_agents(self.bundle, self.home), self.home)
        self.assertEqual(target.read_bytes(), before)

    def test_invalid_source_fields_syntax_and_name(self):
        cases = [
            b'not toml',
            b'name = "reviewer"\n',
            role() + b'model = "override"\n',
            role() + b'sandbox_mode = "danger-full-access"\n',
            role('different'),
            role('Wrong-Name'),
            role(description=''),
            b'name = 3\ndescription = "x"\ndeveloper_instructions = "x"\n',
        ]
        for data in cases:
            with self.subTest(data=data):
                (self.payload / 'reviewer.toml').write_bytes(data)
                with self.assertRaises(ValueError):
                    plan_agents(self.bundle, self.home)
                self.assertFalse(self.home.exists())

    def test_source_nested_directory_rejected(self):
        (self.payload / 'nested').mkdir()
        with self.assertRaises(ValueError):
            plan_agents(self.bundle, self.home)

    def test_invalid_existing_toml_blocks_without_write(self):
        self.existing('other.toml', b'not toml')
        with self.assertRaises(ValueError):
            plan_agents(self.bundle, self.home)
        self.assertFalse((self.home / 'agents/reviewer.toml').exists())

    def test_concurrent_target_edit_preserved(self):
        plan = plan_agents(self.bundle, self.home)
        target = self.existing(data=role(description='并发编辑'))
        with self.assertRaises(RuntimeError):
            install_agents.apply_plan(plan, self.home)
        self.assertEqual(target.read_bytes(), role(description='并发编辑'))
        self.assertFalse((self.home / 'agent-unified-backups').exists())

    def test_concurrent_new_role_file_blocks(self):
        plan = plan_agents(self.bundle, self.home)
        self.existing('new.toml', role())
        with self.assertRaises(RuntimeError):
            install_agents.apply_plan(plan, self.home)
        self.assertFalse((self.home / 'agents/reviewer.toml').exists())

    def test_validate_plan_detects_changed_snapshot(self):
        plan = plan_agents(self.bundle, self.home)
        validate_agent_plan(plan)
        self.existing('new.toml', role('other'))
        with self.assertRaises(RuntimeError):
            validate_agent_plan(plan)

    def test_validate_plan_rejects_modified_expected_content(self):
        plan = plan_agents(self.bundle, self.home)
        target, data, _expected = plan[0]
        plan[0] = (target, data, b'unexpected')
        with self.assertRaises(RuntimeError):
            validate_agent_plan(plan)

    def test_partial_failure_rolls_back(self):
        (self.payload / 'implementer.toml').write_bytes(role('implementer'))
        plan = plan_agents(self.bundle, self.home)
        original = Transaction.save

        def fail_second(transaction, target, data, mode=0o644):
            if transaction.records:
                raise OSError('simulated write failure')
            return original(transaction, target, data, mode)

        with mock.patch.object(Transaction, 'save', fail_second), self.assertRaises(OSError):
            install_agents.apply_plan(plan, self.home)
        self.assertFalse((self.home / 'agents/implementer.toml').exists())
        self.assertFalse((self.home / 'agents/reviewer.toml').exists())

    def test_rollback_preserves_later_edits(self):
        backup = install_agents.apply_plan(plan_agents(self.bundle, self.home), self.home)
        self.existing(data=role(description='后续编辑'))
        with self.assertRaises(RuntimeError):
            rollback(backup)
        self.assertEqual((self.home / 'agents/reviewer.toml').read_bytes(), role(description='后续编辑'))

    def test_symlink_target_rejected(self):
        actual = self.root / 'actual'
        actual.mkdir()
        try:
            self.home.symlink_to(actual, target_is_directory=True)
        except OSError:
            self.skipTest('当前系统未允许符号链接')
        with self.assertRaises(ValueError):
            plan_agents(self.bundle, self.home)


if __name__ == '__main__':
    unittest.main()
