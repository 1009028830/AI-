"""隔离恢复行为测试：只使用临时目录、合成配置和模拟注册表。"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock
import zipfile

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

# 支持尚未安装工具环境时直接使用随包的纯 Python wheel，不联网安装。
try:
    import tomlkit
except ImportError:
    candidates = sorted((PACKAGE / 'assets/wheelhouse').glob('*/python/tomlkit-*-py3-none-any.whl'))
    if candidates:
        sys.path.insert(0, str(candidates[0]))
try:
    import yaml
except ImportError:
    candidates = sorted((PACKAGE / 'assets/wheelhouse').glob('*/python/*YAML*.whl'))
    if candidates:
        sys.path.insert(0, str(candidates[0]))

from engine import common
from engine import configure as configure_module
import restore

try:
    import tomlkit
    import yaml
    CONFIG_DEPS = True
except ImportError:
    CONFIG_DEPS = False


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='agent-unified-test-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def make_symlink(self, target, link, directory=False, allow_junction=True):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as exc:
            if os.name == 'nt' and directory and allow_junction:
                try:
                    import _winapi
                    _winapi.CreateJunction(str(target), str(link))
                    return
                except (OSError, AttributeError):
                    pass
            self.skipTest('当前系统不允许临时符号链接: ' + str(exc))


class PathAndArchiveTests(TemporaryCase):
    def test_relative_paths_reject_escape(self):
        for value in ('../x', 'a/../../x', '/absolute', 'C:/x', r'a\b', '//server/share', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                common.relative_path(value)
        self.assertEqual(common.relative_path('中文 空格/file.txt'), Path('中文 空格/file.txt'))

    def test_zip_traversal_does_not_write_outside(self):
        archive = self.base / 'unsafe.zip'
        outside = self.base / 'outside.txt'
        outside.write_bytes(b'original')
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.writestr('../outside.txt', b'changed')
        with self.assertRaises(ValueError):
            common.extract(archive, self.base / 'destination')
        self.assertEqual(outside.read_bytes(), b'original')

    def test_zip_rejects_symlink_members(self):
        archive = self.base / 'symlink.zip'
        member = zipfile.ZipInfo('link')
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.writestr(member, 'target')
        with self.assertRaises(ValueError):
            common.extract(archive, self.base / 'destination')

    def test_zip_rejects_existing_link_to_outside(self):
        destination, outside = self.base / 'destination', self.base / 'outside'
        destination.mkdir()
        outside.mkdir()
        self.make_symlink(outside, destination / 'linked', directory=True)
        archive = self.base / 'archive.zip'
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.writestr('linked/escaped.txt', b'escape')
        with self.assertRaises(ValueError):
            common.extract(archive, destination)
        self.assertFalse((outside / 'escaped.txt').exists())

    def test_tar_special_file_rejected(self):
        archive = self.base / 'device.tar'
        with tarfile.open(archive, 'w') as stream:
            member = tarfile.TarInfo('device')
            member.type = tarfile.FIFOTYPE
            stream.addfile(member)
        with self.assertRaises(ValueError):
            common.extract(archive, self.base / 'destination')

    def test_tar_link_chain_rejected_without_data_filter(self):
        """旧 Python 缺安全过滤器时应在创建任何链接前拒绝链接归档。"""
        archive = self.base / 'link-chain.tar'
        outside = self.base / 'outside'
        outside.mkdir()
        with tarfile.open(archive, 'w') as stream:
            directory = tarfile.TarInfo('directory')
            directory.type = tarfile.DIRTYPE
            stream.addfile(directory)
            parent = tarfile.TarInfo('directory/parent')
            parent.type = tarfile.SYMTYPE
            parent.linkname = '..'
            stream.addfile(parent)
            escape = tarfile.TarInfo('directory/parent/link')
            escape.type = tarfile.SYMTYPE
            escape.linkname = '../outside'
            stream.addfile(escape)
            payload = b'must not escape'
            file = tarfile.TarInfo('directory/parent/link/escaped.txt')
            file.size = len(payload)
            stream.addfile(file, io.BytesIO(payload))
        real_tarfile = common.tarfile
        without_filter = types.SimpleNamespace(open=real_tarfile.open)
        with mock.patch.object(common, 'tarfile', without_filter):
            with self.assertRaises(ValueError):
                common.extract(archive, self.base / 'destination')
        self.assertFalse((outside / 'escaped.txt').exists(), 'TAR 链接链写出了目标目录')

    def test_manifest_rejects_file_beneath_linked_payload_directory(self):
        bundle, outside = self.base / 'bundle', self.base / 'outside'
        bundle.mkdir()
        outside.mkdir()
        payload = outside / 'file.txt'
        payload.write_bytes(b'valid hash but outside bundle')
        self.make_symlink(outside, bundle / 'payload', directory=True)
        common.write_json(bundle / 'MANIFEST.json', {'files': [{'path': 'payload/file.txt', 'sha256': common.sha256(payload)}]})
        with mock.patch.object(restore, 'BUNDLE', bundle), self.assertRaises(ValueError):
            restore.verify_bundle()


class TransactionTests(TemporaryCase):
    def transaction(self):
        return common.Transaction(self.base / 'backups')

    def test_backup_roundtrip_and_repeat_rollback(self):
        old, new = self.base / 'old.txt', self.base / 'new.txt'
        old.write_bytes(b'before')
        transaction = self.transaction()
        transaction.save(old, b'after')
        transaction.save(new, b'created')
        transaction.commit()
        common.rollback(transaction.directory)
        self.assertEqual(old.read_bytes(), b'before')
        self.assertFalse(new.exists())
        common.rollback(transaction.directory)
        self.assertEqual(old.read_bytes(), b'before')

    def test_unchanged_file_is_skipped(self):
        target = self.base / 'same.txt'
        target.write_bytes(b'same')
        transaction = self.transaction()
        self.assertFalse(transaction.save(target, b'same'))
        self.assertEqual(transaction.records, [])

    def test_transactions_get_distinct_backup_directories(self):
        first = self.transaction()
        second = self.transaction()
        first.save(self.base / 'first', b'first')
        second.save(self.base / 'second', b'second')
        self.assertNotEqual(first.directory, second.directory)
        first.commit()
        second.commit()
        common.rollback(first.directory)
        self.assertFalse((self.base / 'first').exists())
        self.assertEqual((self.base / 'second').read_bytes(), b'second')

    def test_save_detects_edit_after_backup(self):
        target = self.base / 'file'
        target.write_bytes(b'before')
        transaction = self.transaction()
        persist = transaction.persist

        def change_after_backup(state):
            persist(state)
            target.write_bytes(b'concurrent')

        with mock.patch.object(transaction, 'persist', side_effect=change_after_backup):
            with self.assertRaises(RuntimeError):
                transaction.save(target, b'after')
        self.assertEqual(target.read_bytes(), b'concurrent')

    def test_rollback_prechecks_all_conflicts_before_any_write(self):
        first, second = self.base / 'first', self.base / 'second'
        first.write_bytes(b'first before')
        second.write_bytes(b'second before')
        transaction = self.transaction()
        transaction.save(first, b'first after')
        transaction.save(second, b'second after')
        transaction.commit()
        first.write_bytes(b'concurrent')
        with self.assertRaises(RuntimeError):
            common.rollback(transaction.directory)
        self.assertEqual(first.read_bytes(), b'concurrent')
        self.assertEqual(second.read_bytes(), b'second after')

    def test_rollback_rejects_directory_replacing_created_file(self):
        created, existing = self.base / 'created', self.base / 'existing'
        existing.write_bytes(b'before')
        transaction = self.transaction()
        transaction.save(created, b'created')
        transaction.save(existing, b'after')
        transaction.commit()
        created.unlink()
        created.mkdir()
        with self.assertRaises((RuntimeError, ValueError, OSError)):
            common.rollback(transaction.directory)
        self.assertEqual(existing.read_bytes(), b'after', '检测到目标类型冲突前不应回滚其他文件')
        self.assertTrue(created.is_dir())

    def test_rollback_detects_edit_arriving_during_preflight(self):
        first, second = self.base / 'first', self.base / 'second'
        first.write_bytes(b'first before')
        second.write_bytes(b'second before')
        transaction = self.transaction()
        transaction.save(first, b'first after')
        transaction.save(second, b'second after')
        transaction.commit()
        original_sha256 = common.sha256
        last_backup = transaction.directory / transaction.records[-1]['backup']
        changed = False

        def change_during_check(path):
            nonlocal changed
            result = original_sha256(path)
            # Windows CI 的临时目录可能采用 8.3 短路径；回退器已解析为长路径。
            if Path(path).resolve() == last_backup.resolve() and not changed:
                changed = True
                first.write_bytes(b'concurrent')
            return result

        with mock.patch.object(common, 'sha256', side_effect=change_during_check):
            with self.assertRaises(RuntimeError):
                common.rollback(transaction.directory)
        self.assertTrue(changed, '必须实际注入并发修改，不能只验证正常回退')
        self.assertEqual(first.read_bytes(), b'concurrent')

    def test_bad_backup_blocks_all_rollback(self):
        target = self.base / 'target'
        target.write_bytes(b'before')
        transaction = self.transaction()
        transaction.save(target, b'after')
        transaction.commit()
        (transaction.directory / transaction.records[0]['backup']).write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            common.rollback(transaction.directory)
        self.assertEqual(target.read_bytes(), b'after')


class ConfigurationBase(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.fake_home = self.base / 'fake-home'
        self.fake_home.mkdir()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(Path, 'home', return_value=self.fake_home).start()
        mock.patch.dict(os.environ, {'CODEX_HOME': str(self.fake_home / '.codex')}).start()
        self.bundle = self.base / 'bundle'
        (self.bundle / 'config').mkdir(parents=True)
        (self.bundle / 'config/AGENTS.md').write_text('# 统一规则\n', encoding='utf-8')
        skill = self.bundle / 'payload/skills/example'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('---\nname: example\ndescription: 示例\n---\n', encoding='utf-8')
        (self.bundle / 'payload/project-fox').mkdir(parents=True)
        self.root = self.base / 'tools'
        self.codex = self.base / 'isolated-codex'
        self.codex.mkdir()
        self.skills = self.codex / 'skills'
        self.commands = {
            'node': [str(self.root / 'runtime/node')],
            'serena': [str(self.root / 'envs/serena/serena')],
            'agent-python': [str(self.root / 'envs/tools/python')],
            'clangd': [str(self.root / 'native/clangd')],
            'pyright-langserver': [str(self.root / 'runtime/node'), str(self.root / 'js/pyright.js')],
            'context7-mcp': [str(self.root / 'runtime/node'), str(self.root / 'js/context7.js')],
            'dbhub': [str(self.root / 'runtime/node'), str(self.root / 'js/dbhub.js')],
        }

    def configure(self, **kwargs):
        return configure_module.configure(self.bundle, self.root, self.codex, self.skills, self.commands, update_path=False, **kwargs)


@unittest.skipUnless(CONFIG_DEPS, '需要随包 tomlkit 与 PyYAML，测试不会联网安装')
class ConfigurationTests(ConfigurationBase):
    def test_replaced_global_rules_and_skill_are_restorable(self):
        original_rules = self.codex / 'AGENTS.md'
        original_rules.write_bytes(b'user previous global rules')
        original_skill = self.skills / 'example/SKILL.md'
        original_skill.parent.mkdir(parents=True)
        original_skill.write_bytes(b'user previous skill')
        result = self.configure(replace_skills=True)
        self.assertNotEqual(original_rules.read_bytes(), b'user previous global rules')
        common.rollback(result['backup'])
        self.assertEqual(original_rules.read_bytes(), b'user previous global rules')
        self.assertEqual(original_skill.read_bytes(), b'user previous skill')

    def test_unmanaged_skill_conflict_prevents_global_overwrite(self):
        original_rules = self.codex / 'AGENTS.md'
        original_rules.write_bytes(b'user previous global rules')
        original_skill = self.skills / 'example/SKILL.md'
        original_skill.parent.mkdir(parents=True)
        original_skill.write_bytes(b'user custom skill')
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(original_rules.read_bytes(), b'user previous global rules')
        self.assertEqual(original_skill.read_bytes(), b'user custom skill')

    def test_repeat_configuration_is_idempotent_and_keeps_unrelated_settings(self):
        original = '# 用户原有注释\nmodel = "keep-model"\n[features]\ncustom_flag = true\n'
        cfg = self.codex / 'config.toml'
        cfg.write_text(original, encoding='utf-8')
        unrelated = self.skills / 'user-only/notes.txt'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_bytes(b'preserve')
        self.configure()
        snapshot = cfg.read_bytes()
        second = self.configure()
        self.assertEqual(second['changed_files'], 0)
        self.assertEqual(cfg.read_bytes(), snapshot)
        document = tomlkit.parse(snapshot.decode('utf-8'))
        self.assertEqual(document['model'], 'keep-model')
        self.assertTrue(document['features']['custom_flag'])
        self.assertIn('# 用户原有注释', snapshot.decode('utf-8'))
        self.assertEqual(unrelated.read_bytes(), b'preserve')

    def test_mcp_conflict_is_rejected_before_configuration_writes(self):
        cfg = self.codex / 'config.toml'
        cfg.write_text('[mcp_servers.serena]\ncommand = "somebody-elses-serena"\n', encoding='utf-8')
        before = cfg.read_bytes()
        with self.assertRaises(RuntimeError):
            self.configure()
        self.assertEqual(cfg.read_bytes(), before)
        self.assertFalse((self.codex / 'AGENTS.md').exists())
        self.assertFalse(self.skills.exists())
        self.assertFalse((self.fake_home / '.serena').exists())

    def test_custom_codex_home_equal_to_environment_does_not_touch_real_home(self):
        with mock.patch.dict(os.environ, {'CODEX_HOME': str(self.codex)}):
            self.configure()
        self.assertFalse((self.fake_home / '.serena').exists(), '隔离 CODEX_HOME 不应触碰用户真实 .serena')
        document = tomlkit.parse((self.codex / 'config.toml').read_text(encoding='utf-8'))
        serena_home = Path(document['mcp_servers']['serena']['env']['SERENA_HOME'])
        self.assertTrue(self.root in serena_home.parents or self.codex in serena_home.parents)
        self.assertTrue((serena_home / 'serena_config.yml').is_file())

    def test_project_conflict_prevents_all_configuration_changes(self):
        source = self.bundle / 'payload/project-fox/AGENTS.md'
        source.write_bytes(b'project from bundle')
        project = self.base / 'fox'
        (project / 'battery_pack_platform/apps').mkdir(parents=True)
        (project / 'battery_pack_platform/apps/Makefile').write_bytes(b'all:')
        (project / 'AGENTS.md').write_bytes(b'user project')
        with self.assertRaises(ValueError):
            self.configure(project_dir=project)
        self.assertEqual((project / 'AGENTS.md').read_bytes(), b'user project')
        self.assertFalse((self.codex / 'AGENTS.md').exists())
        self.assertFalse(self.skills.exists())

    def test_project_is_untouched_without_project_option(self):
        project = self.base / 'unrelated-project'
        project.mkdir()
        (project / 'AGENTS.md').write_bytes(b'user project')
        self.configure()
        self.assertEqual((project / 'AGENTS.md').read_bytes(), b'user project')
        self.assertEqual(list(project.iterdir()), [project / 'AGENTS.md'])

    def test_symlink_skill_target_is_rejected_before_global_write(self):
        outside = self.base / 'outside-skills'
        outside.mkdir()
        self.make_symlink(outside, self.skills, directory=True)
        with self.assertRaises(ValueError):
            self.configure()
        self.assertFalse((self.codex / 'AGENTS.md').exists())
        self.assertEqual(list(outside.iterdir()), [])


class CliBehaviorTests(TemporaryCase):
    def test_foreign_platform_preview_does_not_install_or_create_targets(self):
        root, codex = self.base / 'tools', self.base / 'codex'
        with mock.patch.object(restore, 'verify_bundle', return_value=0), mock.patch.object(restore, 'install') as install, mock.patch.object(sys, 'argv', ['restore.py', '--platform', 'linux-aarch64', '--root', str(root), '--codex-home', str(codex)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(restore.main(), 0)
        install.assert_not_called()
        self.assertFalse(root.exists())
        self.assertFalse(codex.exists())

    def test_foreign_platform_apply_rejected_before_mutation(self):
        args = types.SimpleNamespace(offline=True, skip_system=True)
        with mock.patch.object(restore, 'host_platform', return_value='windows-x86_64'):
            with self.assertRaises(ValueError):
                restore.install(args, 'linux-aarch64', self.base / 'tools', self.base / 'codex', self.base / 'skills')
        self.assertEqual(list(self.base.iterdir()), [])

    def test_linked_install_root_rejected_before_resource_writes(self):
        actual, linked = self.base / 'actual', self.base / 'linked'
        actual.mkdir()
        state = actual / 'INSTALLATION.json'
        common.write_json(state, {'manager': 'agent-unified', 'state': 'installed'})
        before = state.read_bytes()
        self.make_symlink(actual, linked, directory=True)
        args = types.SimpleNamespace(offline=True, skip_system=True)
        with mock.patch.object(restore, 'host_platform', return_value='linux-x86_64'), mock.patch.object(restore.platform, 'libc_ver', return_value=('glibc', '2.35')), mock.patch.object(restore, 'selected', return_value=[]), mock.patch.object(restore, 'restore_archives', side_effect=AssertionError('不应开始写资源')):
            with self.assertRaises(ValueError):
                restore.install(args, 'linux-x86_64', linked, self.base / 'codex', self.base / 'skills')
        self.assertEqual(state.read_bytes(), before)


class FakeRegistry(types.ModuleType):
    HKEY_CURRENT_USER = object()
    REG_EXPAND_SZ = 2
    REG_SZ = 1

    def __init__(self, values):
        super().__init__('winreg')
        self.values = copy.deepcopy(values)
        self.fail_once = None

    def CreateKey(self, *args):
        return contextlib.nullcontext(object())

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        item = self.values[name]
        return item['value'], item['type']

    def SetValueEx(self, key, name, reserved, kind, value):
        if self.fail_once == name:
            self.fail_once = None
            raise OSError('injected registry write failure')
        self.values[name] = {'value': value, 'type': kind}

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


@unittest.skipUnless(os.name == 'nt' and CONFIG_DEPS, '仅 Windows 上以模拟注册表验证，不触碰真实注册表')
class WindowsRegistryTests(ConfigurationBase):
    def registry_context(self, registry):
        import ctypes
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.dict(sys.modules, {'winreg': registry}))
        user32 = types.SimpleNamespace(SendMessageTimeoutW=mock.Mock(return_value=1))
        stack.enter_context(mock.patch.object(ctypes, 'windll', types.SimpleNamespace(user32=user32)))
        return stack

    def test_registry_only_failure_restores_first_written_value(self):
        self.configure()
        before = {'Path': {'value': 'C:/Existing', 'type': 2}, 'AGENT_TOOLBOX_HOME': {'value': 'C:/Previous', 'type': 1}}
        registry = FakeRegistry(before)
        registry.fail_once = 'AGENT_TOOLBOX_HOME'
        with self.registry_context(registry):
            with self.assertRaises(OSError):
                configure_module.configure(self.bundle, self.root, self.codex, self.skills, self.commands, update_path=True)
        self.assertEqual(registry.values, before, '第二个注册表值写入失败后应恢复第一个值')

    def test_registry_edit_after_backup_is_not_overwritten(self):
        registry = FakeRegistry({'Path': {'value': 'C:/Existing', 'type': 2}})
        transaction = common.Transaction(self.codex / 'backups')
        original_write_json = configure_module.write_json

        def change_after_backup(path, value):
            original_write_json(path, value)
            if Path(path).name == 'windows-environment.json':
                registry.values['Path'] = {'value': 'C:/Concurrent', 'type': 2}

        with self.registry_context(registry), mock.patch.object(configure_module, 'write_json', side_effect=change_after_backup):
            with self.assertRaises(RuntimeError):
                configure_module.update_environment(self.root, transaction)
        self.assertEqual(registry.values['Path']['value'], 'C:/Concurrent')

    def test_registry_edit_during_file_rollback_is_preserved(self):
        registry = FakeRegistry({'Path': {'value': 'C:/Existing', 'type': 2}})
        target = self.base / 'tracked-file'
        target.write_bytes(b'before')
        transaction = common.Transaction(self.codex / 'backups')
        transaction.save(target, b'after')
        with self.registry_context(registry):
            configure_module.update_environment(self.root, transaction)
            transaction.commit()
            original_sha256 = common.sha256
            changed = False

            def edit_registry_after_preflight(path):
                nonlocal changed
                result = original_sha256(path)
                if Path(path) == target and not changed:
                    changed = True
                    registry.values['Path'] = {'value': 'C:/Concurrent', 'type': 2}
                return result

            with mock.patch.object(common, 'sha256', side_effect=edit_registry_after_preflight):
                with self.assertRaises(RuntimeError):
                    common.rollback(transaction.directory)
        self.assertEqual(registry.values['Path']['value'], 'C:/Concurrent')


if __name__ == '__main__':
    unittest.main(verbosity=2)
