"""由已恢复的 Python 工具环境执行，保留现有 TOML/YAML 配置。"""
import json
import os
from pathlib import Path
import shlex
import sqlite3
import sys
from contextlib import closing

from .common import Transaction, read_json, rollback, sha256, write_json
from .agents import AgentWriteGuard, plan_agents


def wrapper_content(command, windows, environment=None):
    environment = environment or {}
    if windows:
        # UTF-8 与独立参数引用；安装根必须避免 cmd 元字符。
        for item in command:
            if any(c in str(item) for c in '\r\n"%'):
                raise ValueError('Windows 命令路径包含不支持的字符: ' + str(item))
        variables = ''.join('set "' + k + '=' + v + '"\r\n' for k, v in environment.items())
        return ('@echo off\r\nchcp 65001 >nul\r\n' + variables + ' '.join('"' + str(x) + '"' for x in command) + ' %*\r\n').encode('utf-8')
    variables = ''.join('export ' + k + '=' + shlex.quote(v) + '\n' for k, v in environment.items())
    return ('#!/bin/sh\n' + variables + 'exec ' + ' '.join(shlex.quote(str(x)) for x in command) + ' "$@"\n').encode('utf-8')


def configure(bundle, root, codex_home, skills_dir, commands, replace_mcp=False, project_dir=None, update_path=True, replace_skills=False, replace_agents=False):
    import tomlkit
    import yaml
    windows = os.name == 'nt'
    cfg = codex_home / 'config.toml'
    original = cfg.read_text(encoding='utf-8-sig') if cfg.exists() else ''
    document = tomlkit.parse(original)
    before_document = document.unwrap()
    suffix = '.cmd' if windows else ''
    node = commands['node'][0]
    serena_exe = commands['serena'][0]
    config_dir = root / 'config'
    database = config_dir / 'demo.sqlite'
    dbconfig = config_dir / 'dbhub.toml'
    servers = {
        'serena': {'command': str(serena_exe), 'args': ['start-mcp-server', '--context', 'codex', '--project-from-cwd', '--open-web-dashboard', 'false', '--enable-web-dashboard', 'false', '--enable-gui-log-window', 'false'], 'env': {'SERENA_HOME': str(config_dir / 'serena')}, 'startup_timeout_sec': 120, 'tool_timeout_sec': 180},
        'context7': {'command': str(node), 'args': [str(x) for x in commands['context7-mcp'][1:]], 'env_vars': ['CONTEXT7_API_KEY'], 'startup_timeout_sec': 60, 'tool_timeout_sec': 90},
        'dbhub': {'command': str(node), 'args': [str(x) for x in commands['dbhub'][1:]] + ['--transport', 'stdio', '--config', str(dbconfig)], 'cwd': str(root), 'startup_timeout_sec': 60, 'tool_timeout_sec': 90},
    }
    table = document.setdefault('mcp_servers', tomlkit.table())
    for name, desired in servers.items():
        if name in table and table[name].unwrap() != desired:
            existing_command = str(table[name].get('command', ''))
            owned = existing_command.startswith(str(root) + os.sep)
            if not owned and not replace_mcp:
                raise RuntimeError('已有不同配置的 MCP: ' + name + '。先检查；确需替换时使用 --replace-existing-mcp，原配置将备份。')
        table[name] = desired
    after_document = document.unwrap()
    for value in (before_document, after_document):
        for key in servers:
            value.get('mcp_servers', {}).pop(key, None)
        if not value.get('mcp_servers'):
            value.pop('mcp_servers', None)
    if before_document != after_document:
        raise RuntimeError('MCP 合并意外改变其他设置')
    new_config = tomlkit.dumps(document).encode('utf-8')
    agent_plan = plan_agents(bundle, codex_home, replace_agents)
    # 所有跨文件预检查应在第一次配置写入前结束。
    if project_dir is not None:
        if not (project_dir / 'battery_pack_platform/apps/Makefile').is_file():
            raise ValueError('--project-dir 只能指向完整 Fox 仓库；通用规则不需要此参数')
        for source in (bundle / 'payload/project-fox').rglob('*'):
            if source.is_file():
                target = project_dir / source.relative_to(bundle / 'payload/project-fox')
                if target.exists() and sha256(target) != sha256(source):
                    raise ValueError('Fox 项目文件有冲突，未覆盖: ' + str(target))
    plan = [(codex_home / 'AGENTS.md', (bundle / 'config/AGENTS.md').read_bytes(), 0o644)]
    plan.extend((target, data, 0o644) for target, data, _ in agent_plan)
    provenance_path = bundle / 'config/payload-provenance.json'
    provenance = {x['path']: x['source_sha256'] for x in read_json(provenance_path)} if provenance_path.exists() else {}
    managed_path = root / 'config/managed-skills.json'
    managed = read_json(managed_path) if managed_path.exists() else {}
    for source in sorted((bundle / 'payload/skills').rglob('*')):
        if source.is_file():
            relative = source.relative_to(bundle / 'payload/skills')
            target = skills_dir / relative
            if target.is_file() and not replace_skills:
                current = sha256(target)
                allowed = {sha256(source), provenance.get(source.relative_to(bundle).as_posix()), managed.get(relative.as_posix())}
                if current not in allowed:
                    raise ValueError('已有技能包含未合并修改: ' + str(target) + '；检查后可用 --replace-existing-skills，替换前会备份。')
            plan.append((target, source.read_bytes(), 0o644))
    for name, command in commands.items():
        plan.append((root / 'bin' / (name + suffix), wrapper_content(command, windows, servers['serena']['env'] if name == 'serena' else None), 0o755))
    plan.append((cfg, new_config, 0o600))
    # 显式命令路径避免依赖父进程 PATH 是否刷新；不追加项目信任。
    serena_cfg = config_dir / 'serena/serena_config.yml'
    serena_config = yaml.safe_load(serena_cfg.read_text(encoding='utf-8')) if serena_cfg.exists() else {}
    serena_config = serena_config or {}
    serena_config.setdefault('projects', [])
    settings = serena_config.setdefault('ls_specific_settings', {})
    if 'clangd' in commands:
        settings.setdefault('cpp', {})['ls_path'] = str(commands['clangd'][0])
    settings.setdefault('python', {})['ls_path'] = str(root / 'bin' / ('pyright-langserver' + suffix))
    serena_config['web_dashboard_open_on_launch'] = False
    serena_config['gui_log_window'] = False
    plan.append((serena_cfg, yaml.safe_dump(serena_config, allow_unicode=True, sort_keys=False).encode('utf-8'), 0o600))
    # DBHub 的 SQLite DSN 要求三条斜线，并用正斜线保留 Windows 盘符。
    dsn = 'sqlite:///' + database.as_posix().lstrip('/')
    dbtext = '[[sources]]\nid = "agent_demo"\ndsn = ' + json.dumps(dsn) + '\n\n[[tools]]\nname = "execute_sql"\nsource = "agent_demo"\nreadonly = true\nmax_rows = 1000\n\n[[tools]]\nname = "search_objects"\nsource = "agent_demo"\n'
    legacy_dbtext = dbtext.replace(json.dumps(dsn), json.dumps('sqlite://' + str(database)), 1)
    if not dbconfig.exists() or dbconfig.read_text(encoding='utf-8') == legacy_dbtext:
        plan.append((dbconfig, dbtext.encode('utf-8'), 0o600))
    if project_dir is not None:
        for source in sorted((bundle / 'payload/project-fox').rglob('*')):
            if source.is_file():
                plan.append((project_dir / source.relative_to(bundle / 'payload/project-fox'), source.read_bytes(), 0o644))
    from .common import ensure_no_links
    for target, _, _ in plan:
        ensure_no_links(target.absolute())
        if target.exists() and not target.is_file():
            raise ValueError('配置文件被目录占用: ' + str(target))
    if cfg.exists() and cfg.read_text(encoding='utf-8-sig') != original:
        raise RuntimeError('Codex 配置在准备期间被修改，请重试')
    guard = AgentWriteGuard(agent_plan)
    transaction = Transaction(codex_home / 'agent-unified-backups')
    try:
        for target, content, mode in plan:
            guard.check()
            transaction.save(target, content, mode)
            guard.saved(target, content)
        if not database.exists():
            with closing(sqlite3.connect(database)) as connection:
                with connection:
                    connection.execute('CREATE TABLE migration_test (id INTEGER PRIMARY KEY, label TEXT)')
                    connection.execute("INSERT INTO migration_test VALUES (1, 'synthetic fixture')")
        if update_path:
            update_environment(root, transaction)
        guard.check()
        transaction.commit()
    except Exception:
        transaction.persist('failed')
        if transaction.records or (transaction.directory / 'windows-environment.json').exists():
            rollback(transaction.directory)
        raise
    write_json(root / 'config/mcp-servers.json', servers)
    write_json(managed_path, {p.relative_to(bundle / 'payload/skills').as_posix(): sha256(p) for p in (bundle / 'payload/skills').rglob('*') if p.is_file()})
    return {'backup': str(transaction.directory) if transaction.records or (transaction.directory / 'windows-environment.json').exists() else None, 'changed_files': len(transaction.records), 'skills': len(list((bundle / 'payload/skills').glob('*/SKILL.md'))), 'mcp': list(servers)}


def update_environment(root, transaction):
    if os.name == 'nt':
        import winreg
        import ctypes
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
            saved = {}
            for name in ('Path', 'AGENT_TOOLBOX_HOME'):
                try:
                    value, kind = winreg.QueryValueEx(key, name)
                    saved[name] = {'value': value, 'type': kind}
                except FileNotFoundError:
                    saved[name] = None
            old_path = saved['Path']['value'] if saved['Path'] else ''
            entry = str(root / 'bin')
            parts = [p for p in old_path.split(';') if p and p.lower().rstrip('\\/') != entry.lower().rstrip('\\/')]
            new_path = ';'.join([entry] + parts)
            desired = {'Path': {'value': new_path, 'type': winreg.REG_EXPAND_SZ}, 'AGENT_TOOLBOX_HOME': {'value': str(root), 'type': winreg.REG_SZ}}
            if saved != desired:
                transaction.directory.mkdir(parents=True, exist_ok=True)
                write_json(transaction.directory / 'windows-environment.json', {'before': saved, 'after': desired})
                transaction.persist('applying')
                for name, item in desired.items():
                    try:
                        current_value, current_type = winreg.QueryValueEx(key, name)
                        current = {'value': current_value, 'type': current_type}
                    except FileNotFoundError:
                        current = None
                    if current != saved[name]:
                        raise RuntimeError('用户环境变量在恢复期间被修改: ' + name)
                    winreg.SetValueEx(key, name, 0, item['type'], item['value'])
        result = ctypes.c_size_t()
        ctypes.windll.user32.SendMessageTimeoutW(0xffff, 0x1a, 0, 'Environment', 2, 2000, ctypes.byref(result))
    else:
        profile = Path.home() / '.profile'
        begin, end = '# >>> agent-unified >>>', '# <<< agent-unified <<<'
        original = profile.read_text(encoding='utf-8') if profile.exists() else ''
        block = begin + '\nexport AGENT_TOOLBOX_HOME=' + shlex.quote(str(root)) + '\nexport PATH="$AGENT_TOOLBOX_HOME/bin:$PATH"\n' + end
        if begin in original:
            if original.count(begin) != 1 or original.count(end) != 1 or original.index(end) < original.index(begin):
                raise ValueError('.profile 中受管区域不完整')
            start, stop = original.index(begin), original.index(end) + len(end)
            new = original[:start] + block + original[stop:]
        else:
            new = original.rstrip() + '\n\n' + block + '\n'
        transaction.save(profile, new.encode('utf-8'), 0o644)
