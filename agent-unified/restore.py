#!/usr/bin/env python3
"""Windows/Linux 统一 Agent 恢复器：默认预览，--apply 执行。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from engine.common import ensure_no_links, extract, read_json, relative_path, rollback, run, sha256, write_json

BUNDLE = Path(__file__).resolve().parent
TARGETS = ('windows-x86_64', 'linux-x86_64', 'linux-aarch64')
SYSTEM_PACKAGES = ['git', 'gcc', 'g++', 'make', 'pkg-config', 'cppcheck', 'clang', 'clang-tidy', 'clangd', 'gdb', 'strace', 'bear', 'cmake', 'ninja-build', 'can-utils', 'tshark', 'wireshark', 'graphviz']


def host_platform():
    system = platform.system().lower()
    machine = platform.machine().lower()
    machine = {'amd64': 'x86_64', 'x64': 'x86_64', 'arm64': 'aarch64'}.get(machine, machine)
    target = system + '-' + machine
    if target not in TARGETS:
        raise ValueError('支持 Windows x64 和 GNU/Linux x64/ARM64，当前为 ' + target)
    return target


def default_root(target):
    if target.startswith('windows'):
        drive = 'D:/' if Path('D:/').is_dir() else os.environ.get('SystemDrive', 'C:') + '/'
        return Path(drive) / 'AgentUnified'
    return Path.home() / '.local/share/agent-unified'


def verify_bundle():
    manifest = read_json(BUNDLE / 'MANIFEST.json')
    seen = set()
    for entry in manifest['files']:
        relative = relative_path(entry['path'])
        path = BUNDLE / relative
        ensure_no_links(path)
        if entry['path'] in seen:
            raise ValueError('重复清单路径: ' + entry['path'])
        seen.add(entry['path'])
        if path.is_symlink() or not path.is_file() or sha256(path) != entry['sha256']:
            raise ValueError('迁移包文件缺失或校验失败: ' + entry['path'])
    # 恢复所读取的载荷和资产必须全部在清单内，拒绝悄悄追加载荷。
    for prefix in ('payload', 'assets', 'config', 'locks', 'engine'):
        for path in (BUNDLE / prefix).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.relative_to(BUNDLE).as_posix() not in seen:
                raise ValueError('发现未登记载荷: ' + str(path))
    return len(seen)


def selected(path, target):
    return [x for x in read_json(path) if x['platform'] in ('all', target)]


def restore_archives(entries, root, folder):
    result = {}
    for item in entries:
        archive = BUNDLE / relative_path(item['path'])
        if sha256(archive) != item['sha256']:
            raise ValueError('安装资源校验失败: ' + item['path'])
        destination = root / folder / item['id']
        marker = destination / '.asset.json'
        executable_paths = {'default': item['executable']} if 'executable' in item else item.get('executables', {})
        ready = marker.exists() and read_json(marker).get('sha256') == item['sha256']
        ready = ready and all((destination / relative_path(p)).is_file() for p in executable_paths.values())
        if item['kind'] == 'file':
            ready = ready and (destination / archive.name).is_file()
        if not ready:
            print('恢复资源:', item['id'], flush=True)
            destination.mkdir(parents=True, exist_ok=True)
            if item['kind'] == 'file':
                shutil.copy2(archive, destination / archive.name)
            else:
                extract(archive, destination)
            write_json(marker, {'sha256': item['sha256']})
        if 'executable' in item:
            result[item['id']] = [str(destination / relative_path(item['executable']))]
        else:
            for name, path in executable_paths.items():
                result[name] = [str(destination / relative_path(path))]
                result[name] += [arg.replace('{install}', str(destination)) for arg in item.get('extra_args', {}).get(name, [])]
    return result


def preflight_system(target, offline, skip_system):
    if target.startswith('windows') or skip_system:
        return
    if not shutil.which('apt-get'):
        raise ValueError('自动系统包恢复目前支持 Debian/Ubuntu。其他发行版请先安装工具，再加 --skip-system。')
    if offline:
        raise ValueError('--offline 禁止联网安装系统包；请先装系统依赖，再使用 --offline --skip-system。旧 Ubuntu20.04 ARM64 deb 仅作可选兼容归档。')


def preflight_configuration(args, root, codex_home, skills_dir):
    from engine.common import ensure_no_links
    for path in (root, codex_home, skills_dir):
        ensure_no_links(path)
    cfg = codex_home / 'config.toml'
    if cfg.exists():
        import tomllib
        document = tomllib.loads(cfg.read_text(encoding='utf-8-sig'))
        for name in ('serena', 'context7', 'dbhub'):
            server = document.get('mcp_servers', {}).get(name)
            if server and not args.replace_existing_mcp:
                command = str(server.get('command', ''))
                if not command.startswith(str(root) + os.sep):
                    raise ValueError('已有不同来源的 MCP: ' + name + '；使用 --replace-existing-mcp 可备份后替换。')
    if not args.replace_existing_skills:
        provenance_path = BUNDLE / 'config/payload-provenance.json'
        provenance = {x['path']: x['source_sha256'] for x in read_json(provenance_path)} if provenance_path.exists() else {}
        managed_path = root / 'config/managed-skills.json'
        managed = read_json(managed_path) if managed_path.exists() else {}
        for source in (BUNDLE / 'payload/skills').rglob('*'):
            if source.is_file():
                relative = source.relative_to(BUNDLE / 'payload/skills')
                target = skills_dir / relative
                ensure_no_links(target)
                if target.exists() and (not target.is_file() or sha256(target) not in {sha256(source), provenance.get(source.relative_to(BUNDLE).as_posix()), managed.get(relative.as_posix())}):
                    raise ValueError('已有技能内容发生冲突: ' + str(target) + '；检查后可使用 --replace-existing-skills。')
    if args.project_dir:
        if not (args.project_dir / 'battery_pack_platform/apps/Makefile').is_file():
            raise ValueError('--project-dir 需要完整 Fox 仓库')
        for source in (BUNDLE / 'payload/project-fox').rglob('*'):
            if source.is_file():
                target = args.project_dir / source.relative_to(BUNDLE / 'payload/project-fox')
                ensure_no_links(target.absolute())
                if target.exists() and (not target.is_file() or sha256(target) != sha256(source)):
                    raise ValueError('Fox 项目配置冲突，未开始恢复: ' + str(target))


def install_system(target, offline, skip_system, root):
    preflight_system(target, offline, skip_system)
    if target.startswith('windows') or skip_system:
        return
    prefix = [] if os.geteuid() == 0 else ['sudo']
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
    print('安装当前发行版系统工具，需要 apt 和管理员权限。', flush=True)
    run(prefix + ['apt-get', 'update'], env=env, timeout=600)
    run(prefix + ['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', '--no-install-recommends'] + SYSTEM_PACKAGES, env=env, timeout=1800)


def make_environments(root, target, runtimes):
    env = dict(os.environ, UV_CACHE_DIR=str(root / 'cache/uv'), UV_PYTHON_DOWNLOADS='never', UV_NO_PROGRESS='1', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    commands = dict(runtimes)
    for item in selected(BUNDLE / 'config/python-environments.json', target):
        destination = root / 'envs' / item['name']
        python = destination / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        marker = destination / '.requirements.sha256'
        requirements = BUNDLE / relative_path(item['requirements'])
        wanted = sha256(requirements)
        if not (python.is_file() and marker.is_file() and marker.read_text().strip() == wanted):
            print('重建独立 Python 环境:', item['name'], flush=True)
            run(runtimes['uv'] + ['venv', '--allow-existing', '--python', runtimes['python'][0], str(destination)], env=env, log=root / ('logs/venv-' + item['name'] + '.log'))
            run(runtimes['uv'] + ['pip', 'sync', '--python', str(python), '--offline', '--no-index', '--find-links', str(BUNDLE / relative_path(item['wheelhouse'])), '--require-hashes', str(requirements)], env=env, log=root / ('logs/pip-' + item['name'] + '.log'))
            marker.write_text(wanted + '\n', encoding='ascii')
        if item['name'] == 'tools':
            commands['agent-python'] = [str(python)]
            commands['can-python'] = [str(python)]
            for module in ('cantools', 'gcovr', 'pytest', 'ruff', 'compiledb'):
                commands[module] = [str(python), '-m', module]
        elif item['name'] == 'serena':
            commands['serena'] = [str(destination / ('Scripts/serena.exe' if os.name == 'nt' else 'bin/serena'))]
    return commands


def install(args, target, root, codex_home, skills_dir):
    if target != host_platform():
        raise ValueError('只能安装当前平台；--platform 仅用于预览其他平台')
    if target.startswith('linux'):
        libc, version = platform.libc_ver()
        if libc != 'glibc' or tuple(int(x) for x in version.split('.')[:2]) < (2, 28):
            raise ValueError('当前离线资源要求 GNU/Linux glibc >=2.28，不支持 Alpine/musl')
    if root == BUNDLE or BUNDLE in root.parents or root == root.parent:
        raise ValueError('工具目录必须在迁移包之外，不能是磁盘或文件系统根目录')
    if target.startswith('windows') and not str(root).isascii():
        raise ValueError('为避免 Wireshark/Falco 的中文路径加载问题，Windows 工具根目录须使用英文路径，例如 D:\\AgentUnified；用户配置和技能目录允许中文。')
    state_path = root / 'INSTALLATION.json'
    if root.exists() and any(root.iterdir()) and not state_path.is_file():
        raise ValueError('工具目标非空且不属于本恢复器: ' + str(root))
    if state_path.exists() and read_json(state_path).get('manager') != 'agent-unified':
        raise ValueError('工具目标由其他程序管理: ' + str(root))
    preflight_system(target, args.offline, args.skip_system)
    preflight_configuration(args, root, codex_home, skills_dir)
    root.mkdir(parents=True, exist_ok=True)
    state = {'manager': 'agent-unified', 'state': 'installing', 'platform': target, 'root': str(root)}
    write_json(state_path, state)
    try:
        runtimes = restore_archives(selected(BUNDLE / 'config/runtime-assets.json', target), root, 'runtime')
        commands = make_environments(root, target, runtimes)
        native = restore_archives(selected(BUNDLE / 'config/native-assets.json', target), root, 'native')
        commands.update(native)
        plantuml_asset = next(x for x in selected(BUNDLE / 'config/native-assets.json', target) if x['id'] == 'plantuml')
        commands['plantuml-jar'] = [str(root / 'native/plantuml' / Path(plantuml_asset['path']).name)]
        js = restore_archives(selected(BUNDLE / 'config/node-assets.json', target), root, 'js')
        commands.update({name: runtimes['node'] + argv for name, argv in js.items()})
        install_system(target, args.offline, args.skip_system, root)
        if target.startswith('linux'):
            for name in ('cppcheck', 'clangd', 'clang-tidy', 'clang-format', 'clang', 'gdb', 'strace', 'bear', 'cmake', 'ninja', 'tshark', 'wireshark', 'candump', 'cansend', 'dot'):
                found = shutil.which(name)
                if not found and name in ('clangd', 'clang-tidy', 'clang-format', 'clang'):
                    found = next((p for version in range(30, 9, -1) for p in [shutil.which(name + '-' + str(version))] if p), None)
                if found:
                    commands[name] = [found]
        if 'plantuml-jar' in commands:
            commands['plantuml'] = commands['java'] + ['-Djava.awt.headless=true', '-jar'] + commands.pop('plantuml-jar')
        write_json(root / 'commands.json', commands)
        config_command = commands['agent-python'] + ['-X', 'utf8', str(BUNDLE / 'restore.py'), '--configure-worker', '--root', str(root), '--codex-home', str(codex_home), '--skills-dir', str(skills_dir)]
        if args.replace_existing_mcp:
            config_command.append('--replace-existing-mcp')
        if args.replace_existing_skills:
            config_command.append('--replace-existing-skills')
        if args.no_path:
            config_command.append('--no-path')
        if args.project_dir:
            config_command.extend(['--project-dir', str(args.project_dir.absolute())])
        run(config_command, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=180)
        state['state'] = 'installed'
        write_json(state_path, state)
        write_json(root / 'ENVIRONMENT.json', {'schema_version': 1, 'platform': target, 'root': str(root), 'commands': commands, 'codex_home': str(codex_home), 'skills_dir': str(skills_dir), 'mcp': ['serena', 'context7', 'dbhub'], 'system_packages_skipped': args.skip_system, 'restart_codex_required': True})
        report = doctor(root)
        if any(x['ok'] is False for x in report['checks']):
            raise RuntimeError('工具恢复后自检存在失败，请查看 ' + str(root / 'verification/doctor.json'))
        print('恢复完成。配置备份位于 Codex 目录的 agent-unified-backups；重启 Codex 加载。')
    except Exception as exc:
        state['state'] = 'failed'
        state['error'] = str(exc)
        write_json(state_path, state)
        raise


def doctor(root):
    commands = read_json(root / 'commands.json')
    flags = {'node': ['--version'], 'uv': ['--version'], 'agent-python': ['--version'], 'cppcheck': ['--version'], 'clangd': ['--version'], 'clang-tidy': ['--version'], 'bru': ['--version'], 'cantools': ['--version'], 'pytest': ['--version'], 'ruff': ['--version'], 'pyright': ['--version'], 'tshark': ['--version'], 'plantuml': ['-version'], 'pandoc': ['--version'], 'defuddle': ['--version']}
    checks = []
    flags['gdb'] = ['--version']
    environment = read_json(root / 'ENVIRONMENT.json') if (root / 'ENVIRONMENT.json').exists() else {}
    optional_system = {'cppcheck', 'clangd', 'clang-tidy', 'tshark', 'gdb'} if environment.get('platform', '').startswith('linux') and environment.get('system_packages_skipped') else set()
    for name, arguments in flags.items():
        if name not in commands:
            checks.append({'tool': name, 'ok': None if name in optional_system else False, 'status': 'missing-system-tool' if name in optional_system else 'failed', 'error': 'not installed'})
            continue
        try:
            result = subprocess.run(commands[name] + arguments, capture_output=True, timeout=60)
            check = {'tool': name, 'ok': result.returncode == 0 and not (name == 'tshark' and b'Unable to load' in result.stderr), 'exit_code': result.returncode, 'first_line': result.stdout.decode('utf-8', errors='replace').splitlines()[:1], 'stderr': result.stderr.decode('utf-8', errors='replace')[:600]}
            if name == 'plantuml' and environment.get('platform', '').startswith('linux') and environment.get('system_packages_skipped') and b'Dot executable does not exist' in result.stdout + result.stderr:
                check.update(ok=None, status='missing-system-dependency', dependency='graphviz/dot', note='PlantUML 可用，但需要 Graphviz 的布局尚不可用；时序图和 Smetana 布局可独立验证。')
            checks.append(check)
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append({'tool': name, 'ok': False, 'error': str(exc)})
    report = {'platform': host_platform(), 'checks': checks, 'scope': 'version/startup; no real hardware or network capture'}
    write_json(root / 'verification/doctor.json', report)
    print('工具自检:', sum(x['ok'] is True for x in checks), '通过，', sum(x['ok'] is None for x in checks), '项系统工具待安装，', sum(x['ok'] is False for x in checks), '失败', flush=True)
    return report


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError('请使用 restore.sh 或 restore.ps1 启动随包 Python 3.13，直接执行 restore.py 需要 Python >=3.11。')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--doctor', action='store_true')
    parser.add_argument('--rollback', type=Path, metavar='BACKUP_DIRECTORY')
    parser.add_argument('--root', type=Path)
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
    parser.add_argument('--skills-dir', type=Path)
    parser.add_argument('--platform', choices=TARGETS)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--skip-system', action='store_true')
    parser.add_argument('--no-path', action='store_true')
    parser.add_argument('--replace-existing-mcp', action='store_true')
    parser.add_argument('--replace-existing-skills', action='store_true')
    parser.add_argument('--project-dir', type=Path)
    parser.add_argument('--configure-worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    target = args.platform or host_platform()
    root = (args.root or default_root(target)).expanduser().absolute()
    codex_home = args.codex_home.expanduser().absolute()
    # 保留现有目录习惯；新安装与当前两个来源统一为 Codex 用户技能目录。
    skills_dir = (args.skills_dir or codex_home / 'skills').expanduser().absolute()
    if args.configure_worker:
        from engine.configure import configure
        result = configure(BUNDLE, root, codex_home, skills_dir, read_json(root / 'commands.json'), args.replace_existing_mcp, args.project_dir, not args.no_path, args.replace_existing_skills)
        write_json(root / 'verification/configuration.json', result)
        print('配置恢复:', result['skills'], '项技能，', result['changed_files'], '个变更文件')
        return 0
    if args.rollback:
        rollback(args.rollback)
        print('配置回滚完成。已安装工具文件保留。')
        return 0
    if args.doctor:
        return 0 if not any(x['ok'] is False for x in doctor(root)['checks']) else 1
    count = verify_bundle()
    print('校验通过:', count, '个文件；目标平台:', target)
    if args.verify:
        return 0
    print('工具目录:', root, '\nCodex 配置:', codex_home, '\n技能目录:', skills_dir)
    skill_count = len(list((BUNDLE / 'payload/skills').glob('*/SKILL.md')))
    print(f'恢复 {skill_count} 项个人/通用技能、统一 AGENTS、3 个 MCP 及当前平台工具。')
    if args.apply:
        install(args, target, root, codex_home, skills_dir)
    else:
        print('当前为预览，不修改目标。使用 --apply 执行；--offline --skip-system 可离线恢复用户工具。')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print('恢复失败:', str(exc), file=sys.stderr)
        sys.exit(1)
