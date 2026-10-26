"""资产维护回归；只使用临时小型资产，不下载、不访问旧工具目录。"""
from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import asset_cache
import package_node
import prepare_assets
import prepare_native


class AssetBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "bundle"
        (self.root / "config").mkdir(parents=True)
        self.output = redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def native_records(self):
        records = []
        for name in ("cppcheck", "llvm-tools", "gdb"):
            path = self.root / "assets/native" / f"{name}.zip"
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("bin/tool.exe", name)
            records.append(dict(id=name, platform="windows-x86_64", kind="zip",
                                path=path.relative_to(self.root).as_posix(),
                                sha256=asset_cache.digest(path), bytes=path.stat().st_size,
                                executables={name: "bin/tool.exe"}, source="fixture", extra="keep"))
        self.write_json(self.root / "config/native-assets.json", records)
        return records

    def node_records(self):
        records = []
        sources = {}
        for name in ("node-tools", "bruno"):
            source = Path(self.temp.name) / name
            entry = source / "node_modules/example/cli.js"
            entry.parent.mkdir(parents=True)
            entry.write_text("console.log('fixture');", encoding="utf-8")
            package = dict(name=name, version="1.0.0", dependencies={"example": "1.0.0"})
            lock = dict(lockfileVersion=3, packages={"": package})
            for filename, value in (("package.json", package), ("package-lock.json", lock)):
                self.write_json(source / filename, value)
                self.write_json(self.root / "locks" / f"{name}-{filename}", value)
            path = self.root / "assets/common" / f"{name}.tar.gz"
            path.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(path, "w:gz") as archive:
                for filename in ("package.json", "package-lock.json", "node_modules/example/cli.js"):
                    archive.add(source / filename, arcname=filename)
            records.append(dict(id=name, platform="all", kind="tar.gz",
                                path=path.relative_to(self.root).as_posix(),
                                sha256=asset_cache.digest(path), bytes=path.stat().st_size,
                                executables={name: "node_modules/example/cli.js"}, source="fixture", extra="keep"))
            sources[name] = source
        self.write_json(self.root / "config/node-assets.json", records)
        return records, sources

    def test_native_preview_does_not_create_missing_assets(self):
        records = self.native_records()
        for record in records:
            asset_cache.asset_path(self.root, record).unlink()
        before = self.snapshot()
        prepare_native.prepare(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_native_existing_cache_preserves_all_records_and_bytes(self):
        self.native_records()
        before = self.snapshot()
        prepare_native.prepare(self.root, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_native_missing_asset_does_not_change_lock(self):
        records = self.native_records()
        asset_cache.asset_path(self.root, records[-1]).unlink()
        before = self.snapshot()
        with self.assertRaises(FileNotFoundError):
            prepare_native.prepare(self.root, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_native_hash_mismatch_does_not_change_lock_or_asset(self):
        records = self.native_records()
        asset_cache.asset_path(self.root, records[0]).write_bytes(b"corrupt")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "SHA256"):
            prepare_native.prepare(self.root, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_native_import_preflights_every_record_before_writing(self):
        records = self.native_records()
        cache = Path(self.temp.name) / "cache"
        cache.mkdir()
        target = asset_cache.asset_path(self.root, records[0])
        (cache / target.name).write_bytes(target.read_bytes())
        target.unlink()
        asset_cache.asset_path(self.root, records[-1]).write_bytes(b"corrupt")
        before = self.snapshot()
        with self.assertRaises(FileNotFoundError):
            prepare_native.prepare(self.root, apply=True, source_dir=cache)
        self.assertEqual(self.snapshot(), before)

    def test_native_import_restores_matching_asset_without_rewriting_lock(self):
        records = self.native_records()
        before = self.snapshot()
        cache = Path(self.temp.name) / "cache"
        cache.mkdir()
        target = asset_cache.asset_path(self.root, records[0])
        (cache / target.name).write_bytes(target.read_bytes())
        target.unlink()
        prepare_native.prepare(self.root, apply=True, source_dir=cache)
        self.assertEqual(self.snapshot(), before)

    def test_native_rejects_escaping_asset_path(self):
        records = self.native_records()
        records[0]["path"] = "../outside.zip"
        self.write_json(self.root / "config/native-assets.json", records)
        with self.assertRaisesRegex(ValueError, "超出"):
            prepare_native.prepare(self.root, apply=True)

    def test_node_import_has_no_side_effects(self):
        with mock.patch("tarfile.open", side_effect=AssertionError("import must not write")):
            importlib.reload(package_node)

    def test_node_preview_and_existing_cache_do_not_write(self):
        self.node_records()
        before = self.snapshot()
        package_node.prepare(self.root)
        package_node.prepare(self.root, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_node_missing_source_cannot_make_empty_archive(self):
        self.node_records()
        before = self.snapshot()
        with self.assertRaises(FileNotFoundError):
            package_node.prepare(self.root, apply=True, sources={"bruno": self.root / "missing"})
        self.assertEqual(self.snapshot(), before)

    def test_node_accepts_tar_members_with_dot_prefix(self):
        records, sources = self.node_records()
        record = records[1]
        path = asset_cache.asset_path(self.root, record)
        with tarfile.open(path, "w:gz") as archive:
            for filename in ("package.json", "package-lock.json", "node_modules/example/cli.js"):
                archive.add(sources["bruno"] / filename, arcname="./" + filename)
        record.update(sha256=asset_cache.digest(path), bytes=path.stat().st_size)
        self.write_json(self.root / "config/node-assets.json", records)
        before = self.snapshot()
        package_node.prepare(self.root, verify=True)
        self.assertEqual(self.snapshot(), before)

    def test_node_repack_preserves_other_record_and_locked_inputs(self):
        records, sources = self.node_records()
        before = self.snapshot()
        package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        updated = json.loads((self.root / "config/node-assets.json").read_text(encoding="utf-8"))
        self.assertEqual(updated[0], records[0])
        self.assertEqual(updated[1]["extra"], "keep")
        asset_cache.verify_asset(asset_cache.asset_path(self.root, updated[1]), updated[1])
        after = self.snapshot()
        for path in before:
            if path not in ("config/node-assets.json", "assets/common/bruno.tar.gz"):
                # Windows 的 snapshot 使用反斜杠，统一成 POSIX 后再比对。
                if Path(path).as_posix() not in ("config/node-assets.json", "assets/common/bruno.tar.gz"):
                    self.assertEqual(after[path], before[path])

    def test_node_rejects_package_lock_mismatch_before_mutation(self):
        _, sources = self.node_records()
        lock = json.loads((sources["bruno"] / "package-lock.json").read_text(encoding="utf-8"))
        lock["packages"][""]["dependencies"]["example"] = "2.0.0"
        # 即使源与正式 lock 相同，也要检查它与 package.json 的约束关系。
        self.write_json(sources["bruno"] / "package-lock.json", lock)
        self.write_json(self.root / "locks/bruno-package-lock.json", lock)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "dependencies"):
            package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        self.assertEqual(self.snapshot(), before)

    def test_node_rejects_missing_entry_before_mutation(self):
        _, sources = self.node_records()
        (sources["bruno"] / "node_modules/example/cli.js").unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "缺少入口"):
            package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        self.assertEqual(self.snapshot(), before)

    def test_node_rejects_native_module_before_mutation(self):
        _, sources = self.node_records()
        (sources["bruno"] / "node_modules/example/addon.node").write_bytes(b"native")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "原生模块"):
            package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        self.assertEqual(self.snapshot(), before)

    def test_node_rejects_root_npmrc_without_changing_archive_or_lock(self):
        _, sources = self.node_records()
        (sources["bruno"] / ".npmrc").write_text("//registry.example.invalid/:_authToken=fixture", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, r"不允许归档.*\.npmrc"):
            package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        self.assertEqual(self.snapshot(), before)

    def test_node_rejects_root_env_without_changing_archive_or_lock(self):
        _, sources = self.node_records()
        (sources["bruno"] / ".env").write_text("EXAMPLE_SECRET=fixture", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, r"不允许归档.*\.env"):
            package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        self.assertEqual(self.snapshot(), before)

    def test_node_rejects_unrelated_project_root(self):
        _, sources = self.node_records()
        (sources["bruno"] / "src").mkdir()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "不允许归档.*src"):
            package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        self.assertEqual(self.snapshot(), before)

    def test_node_failed_commit_restores_archive_and_lock(self):
        _, sources = self.node_records()
        before = self.snapshot()
        actual = Path.replace
        target = self.root / "config/node-assets.json"

        def fail_lock_once(path, destination):
            if destination == target and path.name.endswith(".part"):
                raise OSError("simulated commit failure")
            return actual(path, destination)

        with mock.patch.object(Path, "replace", fail_lock_once):
            with self.assertRaisesRegex(OSError, "simulated"):
                package_node.prepare(self.root, apply=True, sources={"bruno": sources["bruno"]})
        self.assertEqual(self.snapshot(), before)

    def test_runtime_preview_does_not_download_or_write(self):
        before = self.snapshot()
        with mock.patch.object(prepare_assets, "ROOT", self.root), \
                mock.patch.object(prepare_assets, "fetch", side_effect=AssertionError("network forbidden")), \
                mock.patch.object(sys, "argv", ["prepare_assets.py"]):
            prepare_assets.main()
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
