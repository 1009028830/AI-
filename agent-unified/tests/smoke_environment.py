#!/usr/bin/env python3
"""验证已恢复的工具环境；仅使用独立样例、内存设备和127.0.0.1服务。"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import http.server
import json
import os
from pathlib import Path
import signal
import shutil
import sqlite3
import struct
import subprocess
import sys
import threading
import time
import uuid


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def stop_process_tree(process: subprocess.Popen) -> None:
    """仅清理本脚本创建、且仍在运行的子进程树。"""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15, check=False)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


def run_command(command: list[str], log: Path, *, cwd: Path, timeout: int = 90,
                environment: dict | None = None, expected: int = 0) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    if environment:
        env.update(environment)
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen([str(x) for x in command], cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, **options)
    output, error = b"", b""
    try:
        output, error = process.communicate(timeout=timeout)
    finally:
        stop_process_tree(process)
        log.with_suffix(".stdout.log").write_bytes(output)
        log.with_suffix(".stderr.log").write_bytes(error)
    if process.returncode != expected:
        raise AssertionError(f"{log.name} 返回 {process.returncode}，预期 {expected}；详见日志")
    return subprocess.CompletedProcess(command, process.returncode, output, error)


def command_list(root: Path) -> dict[str, list[str]]:
    return json.loads((root / "commands.json").read_text(encoding="utf-8"))


def protocol_test(root: Path, work: Path) -> dict:
    import can
    import cantools
    import serial
    from pymodbus.pdu.register_message import ReadHoldingRegistersRequest

    dbc = 'VERSION ""\nNS_ :\nBS_:\nBU_: ECU\nBO_ 256 VehicleStatus: 8 ECU\n SG_ Speed : 0|16@1+ (0.01,0) [0|655.35] "km/h" ECU\n'
    database = cantools.database.load_string(dbc, database_format="dbc")
    payload = database.encode_message(256, {"Speed": 123.45})
    assert database.decode_message(256, payload)["Speed"] == 123.45
    channel = "agent-unified-test-" + uuid.uuid4().hex
    with can.Bus(interface="virtual", channel=channel) as sender, can.Bus(interface="virtual", channel=channel) as receiver:
        sender.send(can.Message(arbitration_id=256, data=payload, is_extended_id=False), timeout=1)
        received = receiver.recv(timeout=2)
        assert received is not None and bytes(received.data) == payload
    with serial.serial_for_url("loop://", timeout=1) as port:
        payload = b"agent-unified-test"
        assert port.write(payload) == len(payload)
        assert port.read(len(payload)) == payload
    request = ReadHoldingRegistersRequest(address=10, count=2, dev_id=1)
    decoded = ReadHoldingRegistersRequest()
    decoded.decode(request.encode())
    assert decoded.address == 10 and decoded.count == 2
    return {"dbc_encode_decode": True, "virtual_can_send_receive": True, "serial_loopback": True,
            "modbus_pdu_encode_decode": True, "real_hardware_used": False}


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        return

    def do_GET(self) -> None:
        self.respond({"ok": True})

    def do_POST(self) -> None:
        size = int(self.headers.get("Content-Length", "0"))
        if size > 16384:
            self.send_error(413)
            return
        self.respond(json.loads(self.rfile.read(size)))

    def respond(self, data: dict) -> None:
        content = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def bruno_test(root: Path, work: Path) -> dict:
    collection = work / "bruno-collection"
    collection.mkdir(exist_ok=True)
    write_json(collection / "bruno.json", {"version": "1", "name": "统一恢复测试", "type": "collection",
                                           "ignore": ["node_modules", ".git"]})
    (collection / "health.bru").write_text('''meta {
  name: health
  type: http
  seq: 1
}
get {
  url: {{baseUrl}}/health
  body: none
  auth: none
}
tests {
  test("health status", function () {
    expect(res.getStatus()).to.equal(200);
    expect(res.getBody().ok).to.equal(true);
  });
}
''', encoding="utf-8")
    (collection / "echo.bru").write_text('''meta {
  name: echo
  type: http
  seq: 2
}
post {
  url: {{baseUrl}}/echo
  body: json
  auth: none
}
headers {
  Content-Type: application/json
}
body:json {
  {"value": "{{value}}", "guid": "{{$guid}}", "name": "{{$randomFullName}}"}
}
tests {
  test("echo and dynamic values", function () {
    expect(res.getStatus()).to.equal(200);
    expect(res.getBody().value).to.match(/^(alpha|beta)$/);
    expect(res.getBody().guid).to.match(/^[0-9a-f-]{36}$/i);
    expect(res.getBody().name).to.not.contain("{{");
    expect(res.getBody().name.length).to.be.above(0);
  });
}
''', encoding="utf-8")
    (collection / "data.csv").write_text("value\nalpha\nbeta\n", encoding="utf-8")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = work / "bruno-report.json"
    try:
        command = command_list(root)["bru"] + ["run", "--noproxy", "--env-var",
                   f"baseUrl=http://127.0.0.1:{server.server_port}", "--csv-file-path", "data.csv",
                   "--reporter-json", str(report)]
        run_command(command, work / "bruno", cwd=collection, timeout=90)
        data = json.loads(report.read_text(encoding="utf-8"))
        assert isinstance(data, list) and len(data) == 2, "Bruno报表应含两轮CSV迭代"
        requests = [result for iteration in data for result in iteration["results"]]
        tests = [test for result in requests for test in result.get("testResults", [])]
        assert len(requests) == 4 and all(result["status"] == "pass" for result in requests)
        assert len(tests) == 4 and all(test["status"] == "pass" for test in tests)
        return {"get_post_scripts_csv": True, "dynamic_uuid_faker": True,
                "requests_passed": len(requests), "tests_passed": len(tests),
                "report": str(report), "network_scope": "127.0.0.1 only"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def binary_test(root: Path, work: Path) -> dict:
    commands = command_list(root)
    source = work / "known-bug.c"
    source.write_text("int example(void) { int *p = 0; return *p; }\n", encoding="utf-8")
    result = run_command(commands["cppcheck"] + ["--enable=warning,style,performance,portability",
                         "--error-exitcode=1", "--xml", str(source)], work / "cppcheck", cwd=work, expected=1)
    assert b'id="nullPointer"' in result.stderr
    diagram = work / "architecture.puml"
    diagram.write_text('''@startuml
skinparam defaultFontName 宋体
title 统一环境恢复验证
actor 工程师
participant 上位机
participant 控制器
工程师 -> 上位机 : 发起诊断请求
上位机 -> 控制器 : 查询状态
控制器 --> 上位机 : 返回状态快照
上位机 --> 工程师 : 展示结果
@enduml
''', encoding="utf-8")
    run_command(commands["plantuml"] + ["-charset", "UTF-8", "-tpng", str(diagram)], work / "plantuml", cwd=work)
    png = diagram.with_suffix(".png")
    assert png.stat().st_size > 1000 and png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    result = run_command(commands["tshark"] + ["--version"], work / "tshark-version", cwd=work)
    assert b"Unable to load" not in result.stderr and b"Caught sinsp exception" not in result.stderr
    payload = b"agent-unified-synthetic-packet"
    udp = struct.pack("!HHHH", 12345, 23456, 8 + len(payload), 0) + payload
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 1, 0, 64, 17, 0,
                     bytes([192, 0, 2, 1]), bytes([192, 0, 2, 2]))
    packet = bytes.fromhex("00112233445566778899aabb0800") + ip + udp
    pcap = work / "synthetic-udp.pcap"
    pcap.write_bytes(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1) +
                     struct.pack("<IIII", 1, 0, len(packet), len(packet)) + packet)
    result = run_command(commands["tshark"] + ["-r", str(pcap), "-Y", "udp.dstport == 23456", "-T",
                         "fields", "-e", "ip.src", "-e", "udp.dstport"], work / "tshark-pcap", cwd=work)
    assert b"192.0.2.1\t23456" in result.stdout and b"Unable to load" not in result.stderr
    return {"cppcheck_known_null_pointer": True, "plantuml_chinese_png_generated": True,
            "plantuml_visual_review": "pending", "png": str(png), "tshark_synthetic_pcap": True,
            "tshark_falco_startup_errors": False, "live_capture_used": False}


def db_fixture_guard(root: Path) -> tuple[Path, str]:
    import tomllib
    config = tomllib.loads((root / "config/dbhub.toml").read_text(encoding="utf-8"))
    sources = config.get("sources", [])
    database = (root / "config/demo.sqlite").resolve()
    assert len(sources) == 1 and sources[0]["id"] == "agent_demo", "DBHub 不是独立测试源，拒绝运行数据库测试"
    assert sources[0]["dsn"] == "sqlite:///" + database.as_posix().lstrip('/'), "DBHub 未指向本安装的样例SQLite，拒绝测试"
    sql_tools = [tool for tool in config.get("tools", []) if tool.get("name") == "execute_sql"]
    assert len(sql_tools) == 1 and sql_tools[0].get("readonly") is True, "DBHub只读策略不符合预期"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute("SELECT id,label FROM migration_test ORDER BY id").fetchall()
    assert rows == [(1, "synthetic fixture")], "数据库非未修改样例，拒绝执行写入拒绝测试"
    return database, hashlib.sha256(database.read_bytes()).hexdigest()


async def one_mcp(root: Path, work: Path, name: str, settings: dict) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    environment.update(settings.get("env", {}))
    args = list(settings.get("args", []))
    working = Path(settings.get("cwd", str(work)))
    before_db = None
    if name == "serena":
        # Serena 注册测试项目时会写入自身配置；复制到测试目录，避免污染工作环境。
        test_serena_home = work / 'serena-home'
        test_serena_home.mkdir()
        shutil.copy2(root / 'config/serena/serena_config.yml', test_serena_home / 'serena_config.yml')
        environment["SERENA_HOME"] = str(test_serena_home)
        project = work / "serena-synthetic-project"
        project.mkdir(exist_ok=True)
        (project / ".serena").mkdir(exist_ok=True)
        (project / ".serena/project.yml").write_text("project_name: agent-unified-smoke\nlanguage_servers:\n  - cpp\nencoding: utf-8\nignore_all_files_in_gitignore: true\n", encoding="utf-8")
        source = project / "controller.cpp"
        source.write_text("class Controller { public: int read_status() const { return 42; } };\nint main() { Controller c; return c.read_status(); }\n", encoding="utf-8")
        write_json(project / "compile_commands.json", [{"directory": str(project), "file": str(source),
                   "arguments": ["clang++", "-std=c++17", "-c", str(source)]}])
        args = [arg for arg in args if arg != "--project-from-cwd"] + ["--project", str(project)]
        working = project
    elif name == "dbhub":
        before_db = db_fixture_guard(root)
    elif name == "context7":
        # 仅进行本地协议握手，不调用文档检索，也不需要向进程提供密钥。
        environment.pop("CONTEXT7_API_KEY", None)
    parameters = StdioServerParameters(command=settings["command"], args=args,
                                       cwd=str(working), env=environment)
    response = {}
    with (work / f"mcp-{name}.stderr.log").open("w", encoding="utf-8") as log:
        async with stdio_client(parameters, errlog=log) as (reader, writer):
            import importlib.metadata
            # MCP SDK 2 将超时类型从 timedelta 改为浮点秒；兼容旧恢复包测试。
            mcp_major = int(importlib.metadata.version("mcp").split(".")[0])
            timeout_value = 120.0 if mcp_major >= 2 else timedelta(seconds=120)
            async with ClientSession(reader, writer, read_timeout_seconds=timeout_value) as session:
                initialized = await session.initialize()
                available = await session.list_tools()
                names = [tool.name for tool in available.tools]
                write_json(work / f"mcp-{name}-tools.json", [tool.model_dump(mode="json") for tool in available.tools])
                assert names, f"{name}没有返回工具"
                server_info = initialized.server_info if mcp_major >= 2 else initialized.serverInfo
                response = {"initialize": True, "tool_count": len(names), "server": server_info.model_dump(mode="json")}
                if name == "serena":
                    assert "find_symbol" in names
                    value = await session.call_tool("find_symbol", {"name_path_pattern": "Controller", "relative_path": "controller.cpp", "depth": 1, "include_body": False})
                    write_json(work / "serena-symbols.json", value.model_dump(mode="json"))
                    text = "\n".join(part.text for part in value.content if hasattr(part, "text"))
                    assert not value.model_dump(by_alias=True).get("isError", False) and "read_status" in text, text
                    response["cpp_symbol_query"] = True
                    response["project_scope"] = "独立合成测试目录，未修改业务工程"
                elif name == "dbhub":
                    assert "execute_sql" in names
                    selected = await session.call_tool("execute_sql", {"sql": "SELECT id, label FROM migration_test ORDER BY id"})
                    write_json(work / "dbhub-read.json", selected.model_dump(mode="json"))
                    text = "\n".join(part.text for part in selected.content if hasattr(part, "text"))
                    assert not selected.model_dump(by_alias=True).get("isError", False) and "synthetic fixture" in text, text
                    refused = await session.call_tool("execute_sql", {"sql": "INSERT INTO migration_test(id,label) VALUES (999, 'blocked synthetic write')"})
                    write_json(work / "dbhub-write-denied.json", refused.model_dump(mode="json"))
                    text = "\n".join(part.text for part in refused.content if hasattr(part, "text"))
                    assert refused.model_dump(by_alias=True).get("isError", False) and ("READONLY" in text.upper() or "READ-ONLY" in text.upper()), text
                    response.update(sqlite_select=True, sqlite_insert_refused=True)
                else:
                    response["external_document_query"] = "not performed"
    if before_db is not None:
        database, before_hash = before_db
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before_hash, "样例数据库字节发生变化"
        db_fixture_guard(root)
        response["database_unchanged"] = True
    return response


async def mcp_test(root: Path, work: Path) -> dict:
    servers = json.loads((root / "config/mcp-servers.json").read_text(encoding="utf-8"))
    results = {}
    async def collect(name: str) -> None:
        try:
            results[name] = {"ok": True, "checks": await asyncio.wait_for(one_mcp(root, work, name, servers[name]), timeout=170)}
        except Exception as error:
            import traceback
            # 测试仅使用合成数据；保留 ExceptionGroup 内部原因以定位 SDK 兼容性。
            (work / f"mcp-{name}-failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
            results[name] = {"ok": False, "error": str(error), "type": type(error).__name__}
    await asyncio.gather(*(collect(name) for name in ("serena", "context7", "dbhub")))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--only", nargs="+", choices=["protocol", "bruno", "binaries", "mcp"])
    parser.add_argument("--worker", choices=["protocol", "bruno", "binaries", "mcp"], help=argparse.SUPPRESS)
    parser.add_argument("--work", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if args.worker:
        work = args.work.resolve()
        assert work.is_relative_to(root / "verification"), "测试输出必须位于安装根的verification"
        if args.worker == "mcp":
            result = asyncio.run(mcp_test(root, work))
        else:
            result = {"protocol": protocol_test, "bruno": bruno_test, "binaries": binary_test}[args.worker](root, work)
        write_json(work / (args.worker + "-result.json"), result)
        if args.worker == "mcp" and any(not entry["ok"] for entry in result.values()):
            raise SystemExit(1)
        return
    commands = command_list(root)
    verification = root / "verification"
    work = verification / ("smoke-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    work.mkdir(parents=True)
    (work / "README.txt").write_text("本目录仅含统一恢复功能验证的人工样例与日志；没有业务代码或真实硬件数据。Serena工程与编译数据库是独立测试资产，可整体归档或移除。\n", encoding="utf-8")
    python_tools = commands["agent-python"][0]
    python_serena = root / "envs/serena" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    summary = {"root": str(root), "started_at": datetime.now(timezone.utc).isoformat(), "work": str(work),
               "real_hardware_used": False, "business_database_used": False, "checks": {}}
    for group in args.only or ("protocol", "bruno", "binaries", "mcp"):
        started = time.monotonic()
        interpreter = python_serena if group == "mcp" else python_tools
        try:
            run_command([str(interpreter), "-X", "utf8", str(Path(__file__).resolve()), "--root", str(root),
                         "--worker", group, "--work", str(work)], work / (group + "-worker"), cwd=work,
                         timeout=210 if group == "mcp" else 180)
            details = json.loads((work / (group + "-result.json")).read_text(encoding="utf-8"))
            summary["checks"][group] = {"ok": True, "details": details}
        except Exception as error:
            summary["checks"][group] = {"ok": False, "error": str(error), "type": type(error).__name__}
            detail = work / (group + "-result.json")
            if detail.exists():
                summary["checks"][group]["details"] = json.loads(detail.read_text(encoding="utf-8"))
        summary["checks"][group]["elapsed_seconds"] = round(time.monotonic()-started, 2)
        print(group + ": " + ("通过" if summary["checks"][group]["ok"] else "失败"), flush=True)
        write_json(verification / "smoke-environment.json", summary)
    summary["ok"] = all(value["ok"] for value in summary["checks"].values())
    write_json(verification / "smoke-environment.json", summary)
    print("验证报告: " + str(verification / "smoke-environment.json"), flush=True)
    raise SystemExit(0 if summary["ok"] else 1)


if __name__ == "__main__":
    main()
