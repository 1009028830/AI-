"""文件校验、安全解压与可回滚的配置写入。"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    atomic_write(Path(path), (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('无效相对路径: ' + str(value))
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or '..' in parsed.parts or not parsed.parts:
        raise ValueError('路径越界: ' + value)
    return Path(*parsed.parts)


def ensure_no_links(path):
    """拒绝配置目标路径中的符号链接及 Windows 目录联接。"""
    for item in (path,) + tuple(path.parents):
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError('目标路径包含链接，请使用实际路径: ' + str(item))
        if os.name == 'nt' and item.exists() and getattr(item.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise ValueError('目标路径包含 Windows 重解析点: ' + str(item))


def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=str(path.parent))
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def extract(archive, destination):
    archive, destination = Path(archive), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as stream:
            for item in stream.infolist():
                path = (destination / relative_path(item.filename.rstrip('/'))).resolve()
                if destination not in path.parents and path != destination:
                    raise ValueError('ZIP 路径越界: ' + item.filename)
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError('ZIP 包含符号链接: ' + item.filename)
            stream.extractall(destination)
        return
    with tarfile.open(archive, 'r:*') as stream:
        for item in stream.getmembers():
            name = item.name.removeprefix('./') if hasattr(str, 'removeprefix') else item.name[2:] if item.name.startswith('./') else item.name
            if name in ('', '.'):
                continue
            path = (destination / relative_path(name.rstrip('/'))).resolve()
            if destination not in path.parents and path != destination:
                raise ValueError('TAR 路径越界: ' + item.name)
            if item.isdev() or item.isfifo():
                raise ValueError('TAR 包含特殊设备: ' + item.name)
            if item.issym() or item.islnk():
                if not hasattr(tarfile, 'data_filter'):
                    raise ValueError('此归档含链接，请使用随包 Python 3.13 恢复，不使用旧 Python 解压')
                if Path(item.linkname).is_absolute() or '\\' in item.linkname or ':' in item.linkname:
                    raise ValueError('TAR 链接越界: ' + item.name)
                linked = ((path.parent if item.issym() else destination) / item.linkname).resolve()
                if destination not in linked.parents and linked != destination:
                    raise ValueError('TAR 链接越界: ' + item.name)
        if hasattr(tarfile, 'data_filter'):
            stream.extractall(destination, filter='data')
        else:
            stream.extractall(destination)


def run(command, log=None, cwd=None, env=None, timeout=900):
    argv = [str(x) for x in command]
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with Path(log).open('wb') as stream:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            raise RuntimeError('命令失败，退出码 %s；查看日志 %s' % (result.returncode, log))
        return result
    return subprocess.run(argv, check=True, cwd=cwd, env=env, timeout=timeout)


class Transaction:
    """只备份和回滚本次管理的文件，保留并发修改。"""
    def __init__(self, backup_root):
        backup_root = Path(backup_root)
        ensure_no_links(backup_root.absolute())
        backup_root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S') + '-', dir=str(backup_root)))
        self.directory.chmod(0o700)
        self.records = []

    def save(self, target, data, mode=0o644):
        target = Path(target).absolute()
        ensure_no_links(target)
        if target.exists() and not target.is_file():
            raise ValueError('文件目标被目录占用: ' + str(target))
        before = target.read_bytes() if target.exists() else None
        if before == data:
            return False
        self.directory.mkdir(parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        entry = {'target': str(target), 'before': hashlib.sha256(before).hexdigest() if before is not None else None, 'after': hashlib.sha256(data).hexdigest(), 'mode': stat.S_IMODE(target.stat().st_mode) if before is not None else mode}
        if before is not None:
            backup = self.directory / ('file-%05d' % len(self.records))
            atomic_write(backup, before, 0o600)
            entry['backup'] = backup.name
        self.records.append(entry)
        self.persist('applying')
        # 备份之后再检查，避免覆盖配置的并发编辑。
        current = target.read_bytes() if target.exists() else None
        if current != before:
            raise RuntimeError('配置在恢复期间被其他程序修改: ' + str(target))
        atomic_write(target, data, mode)
        return True

    def persist(self, state):
        if self.records or (self.directory / 'windows-environment.json').exists():
            write_json(self.directory / 'transaction.json', {'manager': 'agent-unified', 'state': state, 'files': self.records})

    def commit(self):
        self.persist('committed')


def rollback(directory):
    directory = Path(directory).resolve()
    document = read_json(directory / 'transaction.json')
    if document.get('manager') != 'agent-unified':
        raise ValueError('不是统一恢复工具的备份')
    conflicts = []
    environment = None
    if (directory / 'windows-environment.json').exists():
        if os.name != 'nt':
            raise ValueError('Windows 环境变量备份应在原 Windows 用户下恢复')
        import winreg
        environment = read_json(directory / 'windows-environment.json')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
            for name, after in environment['after'].items():
                try:
                    value, kind = winreg.QueryValueEx(key, name)
                    current = {'value': value, 'type': kind}
                except FileNotFoundError:
                    current = None
                if current not in (after, environment['before'][name]):
                    conflicts.append('用户环境变量 ' + name)
    for entry in document['files']:
        target = Path(entry['target'])
        ensure_no_links(target)
        if target.exists() and not target.is_file():
            conflicts.append(str(target))
            continue
        current = sha256(target) if target.is_file() else None
        if current not in (entry['before'], entry['after']):
            conflicts.append(str(target))
        if entry['before'] is not None:
            backup = directory / relative_path(entry['backup'])
            if not backup.is_file() or sha256(backup) != entry['before']:
                raise ValueError('配置备份损坏: ' + str(backup))
    if conflicts:
        raise RuntimeError('这些文件已有后续修改，回滚未执行: ' + ', '.join(conflicts))
    for entry in reversed(document['files']):
        target = Path(entry['target'])
        ensure_no_links(target)
        current = sha256(target) if target.is_file() else None
        if current not in (entry['before'], entry['after']) or (target.exists() and not target.is_file()):
            raise RuntimeError('回滚期间检测到并发修改，停止剩余写入: ' + str(target))
        if entry['before'] is None:
            if target.exists():
                target.unlink()
        else:
            atomic_write(target, (directory / entry['backup']).read_bytes(), entry['mode'])
    if environment:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
            for name, before in environment['before'].items():
                try:
                    value, kind = winreg.QueryValueEx(key, name)
                    current = {'value': value, 'type': kind}
                except FileNotFoundError:
                    current = None
                if current not in (before, environment['after'][name]):
                    raise RuntimeError('回滚期间用户环境变量被修改，保留该修改: ' + name)
                if before is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                else:
                    winreg.SetValueEx(key, name, 0, before['type'], before['value'])
    document['state'] = 'rolled_back'
    write_json(directory / 'transaction.json', document)
