#!/bin/sh
# 使用随包 Python，支持尚未安装 Python 的 GNU/Linux。
set -eu
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$(uname -s):$(uname -m)" in
  Linux:x86_64) target=linux-x86_64 ;;
  Linux:aarch64|Linux:arm64) target=linux-aarch64 ;;
  *) printf '%s\n' '此入口支持 GNU/Linux x64/ARM64；Windows 请使用 restore.ps1。' >&2; exit 2 ;;
esac
archive=$(find "$bundle/assets/runtimes/$target" -maxdepth 1 -name 'cpython-3.13.13*.tar.gz' -type f -print)
if [ ! -f "$archive" ]; then printf '%s\n' '缺少随包 Python 运行时，请完整解压迁移包。' >&2; exit 2; fi
expected=$(tr -d ' \r\n\t' < "$archive.sha256")
actual=$(sha256sum "$archive")
actual=${actual%% *}
if [ "$expected" != "$actual" ]; then printf '%s\n' 'Python 归档校验失败。' >&2; exit 2; fi
bootstrap=$(mktemp -d "${TMPDIR:-/tmp}/agent-unified-bootstrap.XXXXXXXX")
# 仅清理由本脚本 mktemp 创建的目录，安装结果位于另一个明确的 --root。
cleanup() { if [ -n "$bootstrap" ] && [ -d "$bootstrap" ]; then rm -rf -- "$bootstrap"; fi; }
trap cleanup EXIT HUP INT TERM
tar -xzf "$archive" -C "$bootstrap"
export PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
"$bootstrap/python/bin/python3" "$bundle/restore.py" "$@"
