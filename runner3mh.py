#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 3MH TECHNOLOGIES | t.me/j49_c | t.me/bshshshkk | http://3mh.pages.dev

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import termios
    import tty
except ImportError:
    termios = tty = None

EXECUTION_HOST = "https://repl.online-cpp.com"
FALLBACK_EXECUTION_HOST = "https://code-executor.online-cpp.com"
SITE_URL = "https://www.online-python.com/"
SHARE_ENDPOINT = SITE_URL + "Ide/share_code"
CODE_ENDPOINT = SITE_URL + "Ide/get_code"
SOCKET_PATH = "/socket.io/"
REQUEST_ORIGIN = "https://www.online-python.com"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
ENGINEIO_VERSION = "3"
DEFAULT_LANGUAGE = "python3"
DEFAULT_TIMEOUT = 120.0
CONNECT_RETRIES = 3
PING_INTERVAL = 20.0
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BYTES = 768 * 1024
MAX_ARGUMENT_CHARS = 500
MAX_API_PAYLOAD_BYTES = 4 * 768 * 1024
KILLED_EXIT_CODE = 1000
LOCAL_TIMEOUT_CODE = 124
LOCAL_KILLED_CODE = 137
SHARE_EXPIRY_DAYS = 30
API_BIND_HOST = "127.0.0.1"
API_BIND_PORT = 8377
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
VERIFY_TLS = True
PROJECT_WEBSITE = "http://3mh.pages.dev"
SUPPORT_CHANNEL = "t.me/bshshshkk"
SUPPORT_CONTACT = "t.me/j49_c"
BANNER = f"3MH TECHNOLOGIES — Python Remote Runner | {PROJECT_WEBSITE} | {SUPPORT_CHANNEL}"

ENVIRONMENT_PROBE = """
import sys, platform, os, json, importlib
print("@@INFO@@" + json.dumps({
    "python": sys.version.split()[0],
    "implementation": platform.python_implementation(),
    "platform": platform.platform(),
    "machine": platform.machine(),
    "working_directory": os.getcwd(),
    "user": os.environ.get("USER"),
    "cpus": os.cpu_count(),
}))
names = ["numpy", "pandas", "scipy", "matplotlib", "requests", "flask", "sympy",
         "sklearn", "seaborn", "plotly", "bs4", "PIL", "yaml", "sqlalchemy", "pytest"]
found = []
for name in names:
    try:
        found.append(name + "==" + str(getattr(importlib.import_module(name), "__version__", "?")))
    except Exception:
        pass
print("@@MODS@@" + ", ".join(found))
"""

COLORS = sys.stderr.isatty() and not os.environ.get("NO_COLOR")


class RunnerError(Exception):
    pass


class TransportError(RunnerError):
    pass


class SocketClosed(TransportError):
    pass


def _3mh_paint(text: str, code: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if COLORS else text


def _3mh_mask(buffer: bytes, key: bytes) -> bytes:
    if not buffer:
        return b""
    pad = key * (len(buffer) // 4 + 1)
    return (int.from_bytes(buffer, "big") ^ int.from_bytes(pad[:len(buffer)], "big")).to_bytes(len(buffer), "big")


def _3mh_int(value, fallback: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _3mh_stream(data) -> str:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data).decode("utf-8", "replace")
    if isinstance(data, list):
        try:
            return bytes(bytearray(item & 0xFF for item in data)).decode("utf-8", "replace")
        except (TypeError, ValueError):
            return "".join(map(str, data))
    return data if isinstance(data, str) else str(data)


def _3mh_safe_name(name: str) -> str:
    cleaned = os.path.basename(str(name).replace("\\", "/")).strip()
    if not cleaned or cleaned in {".", ".."} or "\x00" in cleaned:
        raise RunnerError(f"اسم ملف غير مسموح: {name!r}")
    return cleaned


def _3mh_bind(node, attachments):
    if isinstance(node, dict):
        if node.get("_placeholder") is True and "num" in node:
            index = node["num"]
            return attachments[index] if index < len(attachments) else b""
        return {key: _3mh_bind(value, attachments) for key, value in node.items()}
    if isinstance(node, list):
        return [_3mh_bind(value, attachments) for value in node]
    return node


class WebSocket:
    def __init__(self, url: str, headers: dict | None = None, timeout: float = 20.0, verify_tls: bool = True):
        parts = urllib.parse.urlsplit(url)
        secure = parts.scheme == "wss"
        self._3mh_host = parts.hostname or ""
        self._3mh_port = parts.port or (443 if secure else 80)
        self._3mh_buf = b""
        self._3mh_lock = threading.Lock()
        self.closed = False
        stream = socket.create_connection((self._3mh_host, self._3mh_port), timeout=timeout)
        stream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if secure:
            context = ssl.create_default_context()
            if not verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            stream = context.wrap_socket(stream, server_hostname=self._3mh_host)
        self._3mh_sock = stream
        self._3mh_sock.settimeout(timeout)
        self._3mh_open(parts, headers or {}, timeout)

    def _3mh_open(self, parts, headers: dict, timeout: float) -> None:
        key = base64.b64encode(os.urandom(16)).decode()
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        host = self._3mh_host if self._3mh_port in (80, 443) else f"{self._3mh_host}:{self._3mh_port}"
        lines = [f"GET {target} HTTP/1.1", f"Host: {host}", "Upgrade: websocket", "Connection: Upgrade",
                 f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13",
                 *(f"{name}: {value}" for name, value in headers.items())]
        self._3mh_sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        head = b""
        deadline = time.monotonic() + timeout
        while b"\r\n\r\n" not in head:
            if time.monotonic() > deadline:
                raise TransportError("انتهت مهلة مصافحة WebSocket")
            chunk = self._3mh_sock.recv(4096)
            if not chunk:
                raise TransportError("أغلق الخادم الاتصال أثناء المصافحة")
            head += chunk
        raw, self._3mh_buf = head.split(b"\r\n\r\n", 1)
        rows = raw.decode("latin-1").split("\r\n")
        fields = {k.strip().lower(): v.strip() for k, v in (row.split(":", 1) for row in rows[1:] if ":" in row)}
        status = rows[0].split(" ", 2)
        if len(status) < 2 or status[1] != "101":
            raise TransportError("رفض الخادم ترقية الاتصال: " + rows[0])
        if fields.get("sec-websocket-accept") != base64.b64encode(
                hashlib.sha1((key + WEBSOCKET_GUID).encode()).digest()).decode():
            raise TransportError("استجابة مصافحة غير صالحة")

    def _3mh_write(self, payload: bytes, opcode: int) -> None:
        head = bytearray([0x80 | opcode])
        size = len(payload)
        if size < 126:
            head.append(0x80 | size)
        elif size < 65536:
            head += bytes([0x80 | 126]) + size.to_bytes(2, "big")
        else:
            head += bytes([0x80 | 127]) + size.to_bytes(8, "big")
        key = os.urandom(4)
        self._3mh_sock.sendall(bytes(head) + key + _3mh_mask(payload, key))

    def _3mh_read(self, size: int) -> bytes:
        while len(self._3mh_buf) < size:
            chunk = self._3mh_sock.recv(max(65536, size - len(self._3mh_buf)))
            if not chunk:
                raise SocketClosed("أغلق الخادم الاتصال")
            self._3mh_buf += chunk
        head, self._3mh_buf = self._3mh_buf[:size], self._3mh_buf[size:]
        return head

    def send(self, data, binary: bool = False) -> None:
        if self.closed:
            raise SocketClosed("الاتصال مغلق")
        payload = data if isinstance(data, bytes) else str(data).encode()
        with self._3mh_lock:
            self._3mh_write(payload, 0x2 if binary else 0x1)

    def recv(self, timeout: float | None = None) -> tuple[bool, bytes | str]:
        if timeout is not None:
            self._3mh_sock.settimeout(timeout)
        chunks, opcode = [], None
        while True:
            flags, meta = self._3mh_read(2)
            size = meta & 0x7F
            if size == 126:
                size = int.from_bytes(self._3mh_read(2), "big")
            elif size == 127:
                size = int.from_bytes(self._3mh_read(8), "big")
            key = self._3mh_read(4) if meta & 0x80 else None
            body = self._3mh_read(size) if size else b""
            if key:
                body = _3mh_mask(body, key)
            kind = flags & 0x0F
            if kind == 0x8:
                self.close()
                raise SocketClosed("أنهى الخادم جلسة WebSocket")
            if kind == 0x9:
                with self._3mh_lock:
                    self._3mh_write(body, 0xA)
                continue
            if kind == 0xA:
                continue
            if kind == 0x0:
                chunks.append(body)
            else:
                opcode, chunks = kind, [body]
            if flags & 0x80:
                blob = b"".join(chunks)
                return (False, blob.decode("utf-8", "replace")) if opcode == 0x1 else (True, blob)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            with self._3mh_lock:
                self._3mh_write(b"\x03\xe8", 0x8)
        except OSError:
            pass
        try:
            self._3mh_sock.close()
        except OSError:
            pass


class SocketConnection:
    def __init__(self, url: str, headers: dict, timeout: float = 20.0, verify_tls: bool = True):
        self._3mh_ws = WebSocket(url, headers, timeout, verify_tls)
        self._3mh_atts: list[bytes] = []
        self._3mh_pending: tuple[int, str] | None = None
        self._3mh_beat = time.monotonic()
        binary, body = self._3mh_ws.recv(timeout)
        if binary or not str(body).startswith("0"):
            raise TransportError("استجابة افتتاح غير متوقعة من الخادم")
        self.session_id = json.loads(str(body)[1:]).get("sid", "")
        self._3mh_ws.send("40")

    def _3mh_keepalive(self) -> None:
        if time.monotonic() - self._3mh_beat >= PING_INTERVAL:
            self._3mh_beat = time.monotonic()
            self._3mh_ws.send("2")

    def emit(self, event: str, *args) -> None:
        self._3mh_ws.send("42" + json.dumps([event, *args], ensure_ascii=True))

    def _3mh_payload(self, packet: str):
        try:
            data = json.loads(packet)
        except json.JSONDecodeError:
            return None
        return (data[0], data[1:]) if isinstance(data, list) and data else None

    def _3mh_decode(self, packet: str):
        if not packet:
            return None
        kind, rest = packet[0], packet[1:]
        if kind == "2":
            return self._3mh_payload(rest)
        if kind == "5":
            match = re.match(r"(\d+)-(.*)", rest, re.S)
            if not match:
                return self._3mh_payload(rest)
            self._3mh_pending, self._3mh_atts = (int(match.group(1)), match.group(2)), []
            return None
        if kind == "4":
            return "error", [rest]
        if kind == "1":
            raise TransportError("قطع الخادم الاتصال")
        return None

    def _3mh_collect(self, body: bytes):
        self._3mh_atts.append(body[1:] if body[:1] == b"\x04" else body)
        if not self._3mh_pending or len(self._3mh_atts) < self._3mh_pending[0]:
            return None
        packet, self._3mh_pending = self._3mh_pending[1], None
        event = self._3mh_payload(packet)
        return None if not event else (event[0], _3mh_bind(event[1], self._3mh_atts))

    def read_event(self, timeout: float = 3.0):
        self._3mh_keepalive()
        try:
            binary, body = self._3mh_ws.recv(timeout)
        except (socket.timeout, TimeoutError):
            return None
        if binary:
            return self._3mh_collect(body)
        if not body:
            return None
        kind, rest = body[0], body[1:]
        if kind == "2":
            self._3mh_ws.send("3")
        elif kind == "1":
            raise TransportError("أغلق الخادم الجلسة")
        elif kind == "4":
            return self._3mh_decode(rest)
        return None

    def close(self) -> None:
        self._3mh_ws.close()


@dataclass(slots=True)
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    exit_message: str = ""
    elapsed: float = 0.0
    killed: bool = False
    timed_out: bool = False
    session_id: str = ""

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def as_dict(self) -> dict:
        return asdict(self) | {"ok": self.succeeded, "local_exit_code": local_exit_code(self)}


def local_exit_code(result: ExecutionResult) -> int:
    if result.succeeded:
        return 0
    if result.timed_out:
        return LOCAL_TIMEOUT_CODE
    if result.killed:
        return LOCAL_KILLED_CODE
    return result.exit_code if result.exit_code and 1 <= result.exit_code <= 255 else 1


def open_executor(mode: str = "script", language: str = DEFAULT_LANGUAGE, host: str = EXECUTION_HOST,
                  retries: int = CONNECT_RETRIES) -> SocketConnection:
    query = {"EIO": ENGINEIO_VERSION, "transport": "websocket", "type": mode}
    if mode == "script":
        query["lang"] = language
    headers = {"Origin": REQUEST_ORIGIN, "User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    targets = [host, FALLBACK_EXECUTION_HOST] if host == EXECUTION_HOST else [host]
    failures = []
    for attempt in range(retries):
        for target in targets:
            parts = urllib.parse.urlsplit(target if "://" in target else "https://" + target)
            try:
                return SocketConnection(f"wss://{parts.netloc}{SOCKET_PATH}?{urllib.parse.urlencode(query)}",
                                        headers, verify_tls=VERIFY_TLS)
            except (TransportError, OSError) as error:
                failures.append(f"{target}: {error}")
                time.sleep(min(1.2 * (attempt + 1), 4.0))
    raise TransportError("تعذّر الاتصال بخادم التنفيذ — " + " | ".join(failures[-3:]))


def read_source_file(path: str) -> dict:
    if not os.path.isfile(path):
        raise RunnerError(f"الملف غير موجود: {path}")
    with open(path, "rb") as handle:
        raw = handle.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        print(_3mh_paint(f"تحذير: {path} أكبر من {MAX_UPLOAD_BYTES // 1024}KB وقد يرفضه الخادم", "33"),
              file=sys.stderr)
    name = _3mh_safe_name(path)
    try:
        return {"code": raw.decode("utf-8"), "file_name": name, "binary": False}
    except UnicodeDecodeError:
        return {"code": base64.b64encode(raw).decode(), "file_name": name, "binary": True}


def collect_project_files(paths=(), directories=()) -> list[dict]:
    found: dict[str, dict] = {}
    for path in paths:
        entry = read_source_file(path)
        if entry["file_name"] in found:
            raise RunnerError(f"اسم ملف مكرر: {entry['file_name']} — الخادم يستخدم أسماء مسطّحة")
        found[entry["file_name"]] = entry
    for directory in directories:
        if not os.path.isdir(directory):
            raise RunnerError(f"مجلد غير موجود: {directory}")
        for root, _dirs, names in os.walk(directory):
            if "__pycache__" in root.split(os.sep):
                continue
            for name in sorted(names):
                if name.startswith("."):
                    continue
                entry = read_source_file(os.path.join(root, name))
                if entry["file_name"] not in found:
                    found[entry["file_name"]] = entry
    if not found:
        raise RunnerError("لا توجد ملفات للإرسال")
    return list(found.values())


def resolve_active_file(files: list[dict], requested: str | None = None) -> str:
    names = [entry["file_name"] for entry in files]
    if requested:
        if requested not in names:
            raise RunnerError(f"الملف النشط {requested!r} غير موجود ضمن: {', '.join(names)}")
        return requested
    active = "main.py" if "main.py" in names else next((name for name in names if name.endswith(".py")), "")
    if not active:
        raise RunnerError("لا يوجد ملف .py كنقطة دخول — حدده عبر --active")
    return active


def prepare_execution_payload(files: list[dict], active: str) -> tuple[list[dict], str]:
    blobs = {_3mh_safe_name(entry["file_name"]): entry["code"] for entry in files if entry.get("binary")}
    payload = [{"code": entry["code"], "file_name": _3mh_safe_name(entry["file_name"])}
               for entry in files if not entry.get("binary")]
    if not blobs:
        return payload, active
    prelude = ("import base64 as _b, json as _j; [open(_n, 'wb').write(_b.b64decode(_d)) for _n, _d in "
               f"_j.loads({json.dumps(json.dumps(blobs))}).items()]; del _b, _j\n")
    for entry in payload:
        if entry["file_name"] == active:
            entry["code"] = prelude + entry["code"]
            return payload, active
    raise RunnerError("تعذّر حقن الملفات الثنائية: الملف النشط غير نصي")


def run_python_files(files: list[dict], active: str | None = None, arguments: str = "", stdin_lines=(),
                     timeout: float = DEFAULT_TIMEOUT, language: str = DEFAULT_LANGUAGE, on_output=None,
                     on_error=None, connection: SocketConnection | None = None,
                     host: str = EXECUTION_HOST) -> ExecutionResult:
    if not files:
        raise RunnerError("لا يوجد كود للتشغيل")
    owned = connection is None
    link = connection or open_executor(language=language, host=host)
    payload, entry = prepare_execution_payload(files, active or resolve_active_file(files))
    result = ExecutionResult(session_id=link.session_id)
    started = time.monotonic()
    try:
        link.emit("code", payload, arguments[:MAX_ARGUMENT_CHARS], entry)
        for line in stdin_lines:
            link.emit("message", line)
        while True:
            if timeout and time.monotonic() - started > timeout:
                result.timed_out, result.exit_code = True, LOCAL_TIMEOUT_CODE
                result.exit_message = f"انتهت المهلة المحلية بعد {timeout:.0f} ثانية"
                break
            event = link.read_event(3.0)
            if event is None:
                continue
            name, args = event
            if name == "output":
                chunk = _3mh_stream(args[0] if args else "")
                result.stdout += chunk
                if on_output:
                    on_output(chunk)
            elif name == "err":
                chunk = _3mh_stream(args[0] if args else "")
                result.stderr += chunk
                if on_error:
                    on_error(chunk)
            elif name == "exit":
                result.exit_message = str(args[0]).strip() if args else ""
                result.exit_code = _3mh_int(args[1] if len(args) > 1 else 1)
                result.killed = result.exit_code == KILLED_EXIT_CODE
                break
    finally:
        result.elapsed = time.monotonic() - started
        if owned:
            link.close()
    return result


def run_python_code(code: str, arguments: str = "", stdin_lines=(), timeout: float = DEFAULT_TIMEOUT,
                    language: str = DEFAULT_LANGUAGE, on_output=None, on_error=None,
                    host: str = EXECUTION_HOST) -> ExecutionResult:
    return run_python_files([{"code": code, "file_name": "main.py", "binary": False}], "main.py", arguments,
                            stdin_lines, timeout, language, on_output, on_error, host=host)


def fetch_environment_info(language: str = DEFAULT_LANGUAGE) -> dict:
    result = run_python_code(ENVIRONMENT_PROBE, timeout=60, language=language)
    info, modules = {}, []
    for line in result.stdout.splitlines():
        if line.startswith("@@INFO@@"):
            info = json.loads(line[8:])
        elif line.startswith("@@MODS@@"):
            modules = [item for item in line[8:].split(", ") if item]
    return {"environment": info, "modules": modules,
            "limits": {"max_output_bytes": MAX_OUTPUT_BYTES, "max_upload_bytes": MAX_UPLOAD_BYTES,
                       "outbound_network": False, "killed_exit_code": KILLED_EXIT_CODE},
            "website": PROJECT_WEBSITE, "support": SUPPORT_CONTACT}


def _3mh_post_form(url: str, fields: dict) -> dict:
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode(), method="POST",
        headers={"User-Agent": USER_AGENT, "Origin": REQUEST_ORIGIN, "Referer": SITE_URL,
                 "X-Requested-With": "XMLHttpRequest",
                 "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        raise RunnerError(f"HTTP {error.code} من {urllib.parse.urlsplit(url).path}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RunnerError(f"تعذّر الاتصال بالموقع: {error}") from error


def share_code(files: list[dict], days: int = SHARE_EXPIRY_DAYS, language: str = DEFAULT_LANGUAGE,
               active: str | None = None) -> str:
    payload, entry = prepare_execution_payload(files, active or resolve_active_file(files))
    body = _3mh_post_form(SHARE_ENDPOINT, {
        "code_content": json.dumps([dict(item, active=int(item["file_name"] == entry)) for item in payload],
                                   ensure_ascii=True),
        "exp_days": max(1, min(days, 365)), "lang": language})
    if not body.get("output") or not body.get("share_id"):
        raise RunnerError("رفض الخادم حفظ الكود")
    return str(body["share_id"])


def fetch_shared_code(share_id: str) -> tuple[list[dict], str]:
    match = re.search(r"online-python\.com/([A-Za-z0-9_-]{6,})", share_id)
    body = _3mh_post_form(CODE_ENDPOINT, {"code_id": match.group(1) if match else share_id})
    if not body.get("code"):
        raise RunnerError("الكود غير موجود أو منتهية صلاحيته")
    return json.loads(body["code"]), body.get("lang") or DEFAULT_LANGUAGE


def save_shared_code(share_id: str, directory: str = ".") -> tuple[list[str], str]:
    files, language = fetch_shared_code(share_id)
    root = os.path.realpath(directory)
    os.makedirs(root, exist_ok=True)
    saved = []
    for entry in files:
        path = os.path.realpath(os.path.join(root, _3mh_safe_name(entry.get("file_name") or "main.py")))
        if os.path.commonpath([root, path]) != root:
            raise RunnerError("مسار غير آمن داخل الكود المشارك")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(entry.get("code") or "")
        saved.append(path)
    return saved, language


def resolve_stdin_lines(text: str | None = None, path: str | None = None, piped: bool = True) -> list[str]:
    lines: list[str] = []
    if text:
        lines += text.replace("\\n", "\n").split("\n")
    if path:
        with open(path, encoding="utf-8") as handle:
            lines += handle.read().split("\n")
    if not lines and piped and not sys.stdin.isatty():
        lines += sys.stdin.read().split("\n")
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _3mh_write_stdout(chunk: str) -> None:
    sys.stdout.write(chunk)
    sys.stdout.flush()


def _3mh_write_stderr(chunk: str) -> None:
    sys.stderr.write(_3mh_paint(chunk, "31"))
    sys.stderr.flush()


def print_status(result: ExecutionResult, quiet: bool = False) -> None:
    if quiet:
        return
    if result.timed_out:
        line = _3mh_paint(f"× {result.exit_message}", "33")
    elif result.succeeded:
        line = _3mh_paint(f"✓ انتهى بنجاح (exit=0) خلال {result.elapsed:.2f}s", "32")
    elif result.killed:
        line = _3mh_paint(f"× قتل الخادم العملية: {result.exit_message}", "33")
    else:
        line = _3mh_paint(f"× فشل (exit={result.exit_code}) خلال {result.elapsed:.2f}s", "31")
    print(line, file=sys.stderr)


def start_remote_repl(language: str = DEFAULT_LANGUAGE, delay: float = 0.5, grace: float = 2.0,
                      host: str = EXECUTION_HOST) -> int:
    link = open_executor(mode="shell", language=language, host=host)
    print(_3mh_paint(f"جلسة Python بعيدة — exit() أو Ctrl+D للخروج | {SUPPORT_CONTACT}", "36"), file=sys.stderr)
    stop = threading.Event()

    def _3mh_pump() -> None:
        while not stop.is_set():
            try:
                event = link.read_event(2.0)
            except (TransportError, SocketClosed) as error:
                print(_3mh_paint(f"\nانقطع الاتصال: {error}", "31"), file=sys.stderr)
                stop.set()
                return
            if not event:
                continue
            name, args = event
            if name in {"output", "err"}:
                _3mh_write_stdout(_3mh_stream(args[0] if args else ""))
            elif name == "exit":
                stop.set()
                return

    threading.Thread(target=_3mh_pump, daemon=True).start()
    raw = bool(sys.stdin.isatty() and termios)
    saved = termios.tcgetattr(sys.stdin) if raw else None
    if raw:
        tty.setraw(sys.stdin)
    buffer, block = "", False
    try:
        while not stop.is_set():
            if raw:
                char = sys.stdin.read(1)
                if not char or char == "\x04":
                    break
                if char == "\x03":
                    link.emit("message", "\x03")
                    buffer = ""
                elif char in "\r\n":
                    _3mh_write_stdout("\r\n")
                    link.emit("message", buffer)
                    buffer = ""
                elif char in "\x7f\b":
                    buffer = buffer[:-1]
                elif char >= " ":
                    buffer += char
                continue
            line = sys.stdin.readline()
            if not line:
                break
            line = line.rstrip("\n")
            if block and line.strip() and not line[:1].isspace():
                link.emit("message", "")
                time.sleep(delay)
            block = line.rstrip().endswith(":")
            link.emit("message", line)
            time.sleep(delay)
        if block:
            link.emit("message", "")
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and not stop.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if saved is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, saved)
        link.close()
    return 0


def _3mh_snapshot(paths, directories) -> dict:
    targets = list(paths) + [os.path.join(root, name) for directory in directories if os.path.isdir(directory)
                             for root, _dirs, names in os.walk(directory) for name in names]
    state = {}
    for target in targets:
        try:
            state[target] = os.stat(target).st_mtime_ns
        except OSError:
            state[target] = 0
    return state


def watch_files(paths, directories=(), active: str | None = None, arguments: str = "", stdin_lines=(),
                interval: float = 1.5, timeout: float = DEFAULT_TIMEOUT, language: str = DEFAULT_LANGUAGE,
                host: str = EXECUTION_HOST) -> int:
    link = open_executor(language=language, host=host)
    print(_3mh_paint(f"مراقبة الملفات كل {interval}s — Ctrl+C للتوقف | {PROJECT_WEBSITE}", "36"), file=sys.stderr)
    previous, pending = {}, True
    try:
        while True:
            current = _3mh_snapshot(paths, directories)
            if pending or current != previous:
                previous, pending = current, False
                print(_3mh_paint(f"\n── تشغيل {time.strftime('%H:%M:%S')} ──", "2"), file=sys.stderr)
                try:
                    print_status(run_python_files(collect_project_files(paths, directories), active, arguments,
                                                  stdin_lines, timeout, language, _3mh_write_stdout,
                                                  _3mh_write_stderr, link, host))
                except (TransportError, SocketClosed) as error:
                    print(_3mh_paint(f"انقطع الاتصال، إعادة المحاولة: {error}", "33"), file=sys.stderr)
                    link, pending = open_executor(language=language, host=host), True
            time.sleep(interval)
    except KeyboardInterrupt:
        print("", file=sys.stderr)
    finally:
        link.close()
    return 0


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "3MH-Runner/2.0"
    protocol_version = "HTTP/1.1"

    def _3mh_reply(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _3mh_body(self) -> dict:
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > MAX_API_PAYLOAD_BYTES:
            raise RunnerError("حجم الطلب غير مقبول")
        return json.loads(self.rfile.read(size))

    def _3mh_files(self, payload: dict) -> list[dict]:
        entries = payload.get("files") or [{"code": payload.get("code", ""), "file_name": "main.py"}]
        return [{"code": str(item.get("code", "")), "file_name": _3mh_safe_name(item.get("file_name", "main.py")),
                 "binary": bool(item.get("binary"))} for item in entries]

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path == "/health":
            self._3mh_reply(200, {"status": "ok", "website": PROJECT_WEBSITE})
        elif path == "/info":
            try:
                self._3mh_reply(200, fetch_environment_info())
            except (RunnerError, TransportError) as error:
                self._3mh_reply(502, {"error": str(error)})
        else:
            self._3mh_reply(404, {"error": "unknown endpoint"})

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path not in {"/run", "/share"}:
            self._3mh_reply(404, {"error": "unknown endpoint"})
            return
        try:
            payload = self._3mh_body()
            if path == "/run":
                self._3mh_reply(200, run_python_files(
                    self._3mh_files(payload), payload.get("active"), str(payload.get("args", "")),
                    payload.get("stdin") or [], float(payload.get("timeout") or DEFAULT_TIMEOUT),
                    str(payload.get("lang") or DEFAULT_LANGUAGE)).as_dict())
            else:
                share_id = share_code(self._3mh_files(payload),
                                      _3mh_int(payload.get("days"), SHARE_EXPIRY_DAYS),
                                      str(payload.get("lang") or DEFAULT_LANGUAGE), payload.get("active"))
                self._3mh_reply(200, {"share_id": share_id, "url": SITE_URL + share_id})
        except (RunnerError, TransportError, ValueError, KeyError, TypeError) as error:
            self._3mh_reply(400, {"error": str(error)})

    def log_message(self, *_args) -> None:
        pass


def serve_api(host: str = API_BIND_HOST, port: int = API_BIND_PORT) -> int:
    with ThreadingHTTPServer((host, port), ApiHandler) as server:
        print(f"API: http://{host}:{port}/run · /info · /health | {PROJECT_WEBSITE}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
    return 0


def _3mh_ask(prompt: str, default: str = "") -> str:
    answer = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return answer or default


def _3mh_read_block() -> str:
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def _3mh_split_paths(value: str) -> tuple[list[str], list[str]]:
    items = [item for item in value.split() if item]
    return [item for item in items if not os.path.isdir(item)], [item for item in items if os.path.isdir(item)]


def start_interactive_menu(host: str = EXECUTION_HOST, language: str = DEFAULT_LANGUAGE) -> int:
    print(_3mh_paint(BANNER, "36"))
    options = [("1", "تشغيل ملفات أو مشروع"), ("2", "تشغيل كود مباشر"), ("3", "جلسة REPL بعيدة"),
               ("4", "مشاركة كود والحصول على رابط"), ("5", "سحب كود من رابط مشاركة"),
               ("6", "معلومات البيئة البعيدة"), ("7", "تشغيل خادم API محلي"), ("0", "خروج")]
    while True:
        print()
        for key, label in options:
            print(f"  {key}) {label}")
        try:
            choice = input(_3mh_paint("\nاختيارك: ", "1")).strip()
            if choice == "1":
                files, dirs = _3mh_split_paths(_3mh_ask("الملفات/المجلدات", "main.py"))
                print_status(run_python_files(collect_project_files(files, dirs),
                                              _3mh_ask("الملف النشط") or None,
                                              _3mh_ask("وسائط البرنامج") or "",
                                              resolve_stdin_lines(_3mh_ask("stdin مفصول بـ \\n") or None,
                                                                  piped=False),
                                              float(_3mh_ask("المهلة بالثواني", "120") or 120), language,
                                              _3mh_write_stdout, _3mh_write_stderr, host=host))
            elif choice == "2":
                print("اكتب الكود ثم سطر فارغ للتشغيل:")
                print_status(run_python_code(_3mh_read_block(),
                                             _3mh_ask("وسائط البرنامج") or "",
                                             resolve_stdin_lines(_3mh_ask("stdin مفصول بـ \\n") or None,
                                                                 piped=False),
                                             float(_3mh_ask("المهلة بالثواني", "120") or 120), language,
                                             _3mh_write_stdout, _3mh_write_stderr, host=host))
            elif choice == "3":
                start_remote_repl(language, host=host)
            elif choice == "4":
                files, dirs = _3mh_split_paths(_3mh_ask("الملفات/المجلدات", "main.py"))
                share_id = share_code(collect_project_files(files, dirs),
                                      _3mh_int(_3mh_ask("مدة الصلاحية بالأيام", "30"), SHARE_EXPIRY_DAYS), language)
                print(_3mh_paint(f"✓ {SITE_URL}{share_id}", "32"))
            elif choice == "5":
                saved, lang = save_shared_code(_3mh_ask("معرّف أو رابط المشاركة"), _3mh_ask("مجلد الحفظ", "."))
                print(_3mh_paint(f"✓ {len(saved)} ملف ({lang}): " + ", ".join(saved), "32"))
            elif choice == "6":
                print(json.dumps(fetch_environment_info(language), ensure_ascii=False, indent=2))
            elif choice == "7":
                serve_api(_3mh_ask("عنوان الاستماع", API_BIND_HOST),
                          _3mh_int(_3mh_ask("المنفذ", str(API_BIND_PORT)), API_BIND_PORT))
            elif choice in {"0", "q", "exit"}:
                return 0
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
        except (RunnerError, TransportError, ValueError, OSError) as error:
            print(_3mh_paint(f"× {error}", "31"))


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runner3mh", description=BANNER, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"الموقع: {PROJECT_WEBSITE}\nالقناة: {SUPPORT_CHANNEL}\nالدعم: {SUPPORT_CONTACT}")
    parser.add_argument("--version", action="version", version="runner3mh 2.0.0 — 3MH TECHNOLOGIES")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--host", default=os.environ.get("RUNNER3MH_HOST", EXECUTION_HOST))
    shared.add_argument("--lang", default=DEFAULT_LANGUAGE)
    shared.add_argument("--retries", type=int, default=CONNECT_RETRIES)
    shared.add_argument("--insecure", action="store_true")
    shared.add_argument("--json", action="store_true")
    shared.add_argument("-q", "--quiet", action="store_true")
    commands = parser.add_subparsers(dest="command")

    run = commands.add_parser("run", parents=[shared], help="تشغيل ملفات بايثون بعيداً")
    run.add_argument("files", nargs="*")
    run.add_argument("-c", "--code")
    run.add_argument("-d", "--dir", action="append", default=[])
    run.add_argument("--active")
    run.add_argument("--args", default="")
    run.add_argument("--stdin")
    run.add_argument("--stdin-file", dest="stdin_file")
    run.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    run.add_argument("--save-output", dest="save_output")

    repl = commands.add_parser("repl", parents=[shared], help="جلسة Python تفاعلية بعيدة")
    repl.add_argument("--delay", type=float, default=0.5)
    repl.add_argument("--grace", type=float, default=2.0)

    watch = commands.add_parser("watch", parents=[shared], help="إعادة التشغيل عند تعديل الملفات")
    watch.add_argument("files", nargs="+")
    watch.add_argument("-d", "--dir", action="append", default=[])
    watch.add_argument("--active")
    watch.add_argument("--args", default="")
    watch.add_argument("--stdin")
    watch.add_argument("--stdin-file", dest="stdin_file")
    watch.add_argument("--interval", type=float, default=1.5)
    watch.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)

    share = commands.add_parser("share", parents=[shared], help="حفظ الكود والحصول على رابط")
    share.add_argument("files", nargs="+")
    share.add_argument("-d", "--dir", action="append", default=[])
    share.add_argument("--active")
    share.add_argument("--days", type=int, default=SHARE_EXPIRY_DAYS)

    pull = commands.add_parser("pull", parents=[shared], help="سحب كود محفوظ")
    pull.add_argument("share_id")
    pull.add_argument("-o", "--out", default=".")

    commands.add_parser("info", parents=[shared], help="معلومات البيئة البعيدة")
    commands.add_parser("menu", parents=[shared], help="القائمة التفاعلية")

    serve = commands.add_parser("serve", parents=[shared], help="تشغيل خادم API محلي")
    serve.add_argument("--bind", default=API_BIND_HOST)
    serve.add_argument("--port", type=int, default=API_BIND_PORT)
    return parser


def _3mh_paths(items, directories) -> tuple[list[str], list[str]]:
    return [item for item in items if not os.path.isdir(item)], \
        list(directories) + [item for item in items if os.path.isdir(item)]


def run_command(options) -> int:
    paths, dirs = _3mh_paths(options.files, options.dir)
    files = collect_project_files(paths, dirs) if (paths or dirs) else []
    code = sys.stdin.read() if options.code == "-" else options.code
    if code:
        if any(entry["file_name"] == "main.py" for entry in files):
            raise RunnerError("لا يمكن استخدام -c مع ملف اسمه main.py")
        files.insert(0, {"code": code, "file_name": "main.py", "binary": False})
    if not files:
        raise RunnerError("حدّد ملفاً أو مجلداً أو استخدم -c")
    active = resolve_active_file(files, options.active)
    lines = resolve_stdin_lines(options.stdin, options.stdin_file, options.code != "-")
    if not options.json and not options.quiet:
        print(_3mh_paint("→ " + ", ".join(entry["file_name"] + ("*" if entry["file_name"] == active else "")
                                          for entry in files) + f" | {options.host}", "2"), file=sys.stderr)
    result = run_python_files(files, active, options.args, lines, options.timeout, options.lang,
                              None if options.json else _3mh_write_stdout,
                              None if options.json else _3mh_write_stderr, host=options.host)
    if options.save_output:
        with open(options.save_output, "w", encoding="utf-8") as handle:
            handle.write(result.stdout + result.stderr)
    if options.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        print_status(result, options.quiet)
    return local_exit_code(result)


def share_command(options) -> int:
    share_id = share_code(collect_project_files(*_3mh_paths(options.files, options.dir)), options.days,
                          options.lang, options.active)
    if options.json:
        print(json.dumps({"share_id": share_id, "url": SITE_URL + share_id}, ensure_ascii=False))
    else:
        print(_3mh_paint(f"✓ {SITE_URL}{share_id}", "32"))
    return 0


def pull_command(options) -> int:
    saved, language = save_shared_code(options.share_id, options.out)
    if options.json:
        print(json.dumps({"files": saved, "lang": language}, ensure_ascii=False))
    else:
        print(_3mh_paint(f"✓ {len(saved)} ملف ({language}): " + ", ".join(saved), "32"))
    return 0


def info_command(options) -> int:
    info = fetch_environment_info(options.lang)
    if options.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    for key, value in info["environment"].items():
        print(f"  {key}: {value}")
    print(f"  modules: {', '.join(info['modules']) or '—'}")
    print(f"  limits: {json.dumps(info['limits'], ensure_ascii=False)}")
    print(f"  {PROJECT_WEBSITE} · {SUPPORT_CONTACT}")
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    known = {"run", "repl", "watch", "share", "pull", "info", "menu", "serve"}
    position = next((index for index, item in enumerate(arguments) if item in known), None)
    if position is None:
        if arguments and not arguments[0].startswith("-"):
            arguments = ["run"] + arguments
        elif not arguments:
            arguments = ["menu"]
    elif position:
        arguments = [arguments[position]] + arguments[:position] + arguments[position + 1:]
    options = build_argument_parser().parse_args(arguments)
    global VERIFY_TLS
    VERIFY_TLS = not getattr(options, "insecure", False)
    if options.command is None:
        return start_interactive_menu()
    handlers = {"run": run_command, "share": share_command, "pull": pull_command, "info": info_command,
                "menu": lambda item: start_interactive_menu(item.host, item.lang),
                "repl": lambda item: start_remote_repl(item.lang, item.delay, item.grace, item.host),
                "serve": lambda item: serve_api(item.bind, item.port),
                "watch": lambda item: watch_files(*_3mh_paths(item.files, item.dir), active=item.active,
                                                  arguments=item.args,
                                                  stdin_lines=resolve_stdin_lines(item.stdin, item.stdin_file, False),
                                                  interval=item.interval, timeout=item.timeout,
                                                  language=item.lang, host=item.host)}
    try:
        return handlers[options.command](options)
    except RunnerError as error:
        print(_3mh_paint(f"× {error}", "31"), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
