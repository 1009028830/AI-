"""规划可移植 Codex 角色配置；不修改账号、模型、权限或全局配置。"""
import os
from pathlib import Path
import re
import tomllib

from .common import ensure_no_links

FIELDS = {'name', 'description', 'developer_instructions'}
NAME = re.compile(r'[a-z][a-z0-9_]*\Z')


class AgentPlan(list):
    """保留列表接口，同时记录预检查时的角色目录内容。"""
    def __init__(self, entries, codex_home, snapshot):
        super().__init__(entries)
        self.codex_home = codex_home
        self.snapshot = snapshot


class AgentWriteGuard:
    """跨入口维护预期角色目录，阻止事务期间到达的并发编辑。"""
    def __init__(self, plan):
        validate_agent_plan(plan)
        self.plan = plan if isinstance(plan, AgentPlan) else None
        self.expected = dict(self.plan.snapshot) if self.plan is not None else {}
        self.targets = {target for target, _, _ in plan}
        self.check()

    def check(self):
        if self.plan is not None and snapshot_agents(self.plan.codex_home) != self.expected:
            raise RuntimeError('预检查后角色目录被修改，停止安装')

    def saved(self, target, data):
        if target in self.targets:
            self.expected[target.name] = data
        self.check()


def snapshot_agents(codex_home):
    """只读取角色 TOML；链接、目录占位和异常配置由调用者阻断。"""
    root = codex_home / 'agents'
    ensure_no_links(root)
    if not root.exists():
        return {}
    if not root.is_dir():
        raise ValueError('agents 目标不是目录: ' + str(root))
    snapshot = {}
    for path in sorted(root.iterdir()):
        if path.suffix.lower() != '.toml':
            continue
        ensure_no_links(path)
        if not path.is_file():
            raise ValueError('角色目标不是文件: ' + str(path))
        snapshot[path.name] = path.read_bytes()
    return snapshot


def validate_agent_plan(plan):
    """事务首次写入前核对规划时的目录快照与每个目标的原内容。"""
    if not plan:
        return
    if not isinstance(plan, AgentPlan):
        raise ValueError('必须使用 plan_agents 返回的计划')
    if snapshot_agents(plan.codex_home) != plan.snapshot:
        raise RuntimeError('预检查后角色目录被修改，停止安装')
    for target, _data, expected in plan:
        ensure_no_links(target)
        if target.parent != plan.codex_home / 'agents':
            raise ValueError('角色目标路径越界: ' + str(target))
        if target.exists() and not target.is_file():
            raise ValueError('角色目标不是文件: ' + str(target))
        current = target.read_bytes() if target.exists() else None
        if current != expected:
            raise RuntimeError('预检查后角色文件被修改，停止: ' + str(target))


def _parse(data, path, strict=False):
    try:
        document = tomllib.loads(data.decode('utf-8'))
    except (UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError('角色 TOML 无效: ' + str(path)) from error
    name = document.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('角色缺少有效 name: ' + str(path))
    if strict:
        if set(document) != FIELDS:
            raise ValueError('角色仅允许 name、description、developer_instructions 三个必需字段: ' + str(path))
        if not NAME.fullmatch(name) or name != path.stem or path.suffix != '.toml':
            raise ValueError('角色 name 必须与小写下划线文件名一致: ' + str(path))
        if any(not isinstance(document[field], str) or not document[field].strip() for field in FIELDS):
            raise ValueError('角色字段必须为非空字符串: ' + str(path))
    return name


def plan_agents(bundle, codex_home, replace_existing=False):
    """全部预检查后返回 (target, data, expected)；缺少载荷兼容旧包。"""
    bundle = Path(os.path.abspath(Path(bundle).expanduser()))
    codex_home = Path(os.path.abspath(Path(codex_home).expanduser()))
    source_root = bundle / 'payload' / 'agents'
    ensure_no_links(source_root)
    ensure_no_links(codex_home)
    if not source_root.exists():
        return []
    if not source_root.is_dir():
        raise ValueError('角色载荷不是目录: ' + str(source_root))
    candidates = {}
    for source in sorted(source_root.iterdir()):
        ensure_no_links(source)
        if not source.is_file() or source.suffix.lower() != '.toml':
            raise ValueError('角色载荷只允许直接包含 TOML 文件: ' + str(source))
        data = source.read_bytes()
        name = _parse(data, source, strict=True)
        if name in candidates:
            raise ValueError('角色载荷名称重复: ' + name)
        candidates[name] = (source.name, data)
    snapshot = snapshot_agents(codex_home)
    existing = {}
    for filename, data in snapshot.items():
        name = _parse(data, codex_home / 'agents' / filename)
        if name in existing:
            raise ValueError('目标目录已有重复角色名称: ' + name)
        existing[name] = filename
    plan = []
    for name, (filename, data) in candidates.items():
        if name in existing and existing[name] != filename:
            raise ValueError('其他文件已定义同名角色: ' + name)
        target = codex_home / 'agents' / filename
        ensure_no_links(target)
        # Linux 上同样拒绝大小写别名，保证迁移到 Windows 后没有文件冲突。
        if any(other.casefold() == filename.casefold() and other != filename for other in snapshot):
            raise ValueError('角色文件存在大小写冲突: ' + filename)
        current = snapshot.get(filename)
        if current == data:
            continue
        if current is not None and not replace_existing:
            raise ValueError('已有角色不同，审阅后才使用 --replace-existing: ' + str(target))
        plan.append((target, data, current))
    return AgentPlan(plan, codex_home, snapshot)
