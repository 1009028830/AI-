#!/usr/bin/env python3
"""调用工程技能内的统一验证器；保留参数，项目根默认是本目录。"""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    runner = root / "payload/skills/agents-engineering-skill/assets/agents-project-template/scripts/verify.py"
    sys.argv[1:1] = ["--root", str(root)]
    runpy.run_path(str(runner), run_name="__main__")
