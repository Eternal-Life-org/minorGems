#!/usr/bin/env python3
"""Exercise real WebRequest HTTP parsing and limits on a local TCP fixture.

Runs on macOS/Linux with a C++11 compiler; uses no external service.
"""
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading

root = Path(__file__).resolve().parents[3]
compiler = shutil.which("clang++") or shutil.which("g++")
if compiler is None:
    raise SystemExit("C++ compiler required")
sources = [
    "network/web/test/testWebRequest.cpp", "network/web/WebRequest.cpp",
    "network/LookupThread.cpp", "network/NetworkFunctionLocks.cpp",
    "network/linux/SocketLinux.cpp", "network/linux/SocketClientLinux.cpp",
    "network/linux/HostAddressLinux.cpp", "system/FinishedSignalThread.cpp",
    "system/linux/ThreadLinux.cpp", "system/linux/MutexLockLinux.cpp",
    "system/unix/TimeUnix.cpp", "io/linux/TypeIOLinux.cpp",
    "util/stringUtils.cpp", "util/StringBufferOutputStream.cpp",
]


def check(executable, name, response, cap, result, status=0, length=0):
    errors = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)
        port = listener.getsockname()[1]

        def serve():
            try:
                with listener.accept()[0] as peer:
                    peer.settimeout(5)
                    request = b""
                    while b"\r\n\r\n" not in request:
                        data = peer.recv(1024)
                        if not data:
                            raise AssertionError("client closed before HTTP request")
                        request += data
                    peer.sendall(response)
            except Exception as error:
                errors.append(error)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        completed = subprocess.run([executable, f"http://127.0.0.1:{port}/auth",
                                    str(cap), str(result), str(status), str(length)],
                                   capture_output=True, text=True, timeout=8)
        worker.join(timeout=6)
        assert not worker.is_alive() and not errors, (name, errors)
        assert completed.returncode == 0, (name, completed.stdout, completed.stderr)
        print("PASS", name, flush=True)


with tempfile.TemporaryDirectory(prefix="web-request-tests-") as scratch:
    executable = str(Path(scratch) / "web-request")
    subprocess.run([compiler, "-std=c++11", "-pthread", "-I", str(root.parent),
                    *[str(root / source) for source in sources], "-o", executable],
                   check=True)
    header = b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n"
    check(executable, "HTTP 200", header + b"VALID", 4096, 1, 200, 5)
    check(executable, "HTTP 500 with VALID body",
          b"HTTP/1.1 500 Error\r\n\r\nVALID", 4096, 1, 500, 5)
    check(executable, "malformed status", b"NOT_HTTP\r\n\r\nVALID", 4096, 1, 0, 5)
    check(executable, "overlong status number",
          b"HTTP/1.1 " + b"9" * 100 + b" OK\r\n\r\nVALID", 4096, 1, 0, 5)
    check(executable, "four-digit status", b"HTTP/1.1 2000 OK\r\n\r\nVALID", 4096, 1, 0, 5)
    check(executable, "status on another line", b"HTTP/1.1\n200 OK\r\n\r\nVALID", 4096, 1, 0, 5)
    check(executable, "binary-safe body length", header + b"VALID\0X", 4096, 1, 200, 7)
    check(executable, "response exactly at cap", header + b"x" * (4096 - len(header)),
          4096, 1, 200, 4096 - len(header))
    check(executable, "response over cap", header + b"x" * 4096, 4096, -1)
    check(executable, "legacy unlimited response", header + b"x" * 5000, -1, 1, 200, 5000)
