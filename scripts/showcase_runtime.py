"""Own only the two local showcase servers; never provision models or services."""
from __future__ import annotations

import argparse
import ctypes
import fcntl
import json
import os
import platform
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "outputs/showcase-runtime"
STATE = RUNTIME / "state.json"
TAG = "TEACHINTENT_SHOWCASE_RUN_ID"


def pidfd_open(pid: int) -> int:
    if hasattr(os, "pidfd_open"):
        return os.pidfd_open(pid)
    # Some Conda builds omit os.pidfd_open because of old build-time headers.
    # Linux x86_64/aarch64 use syscall 434; never fall back to an unpinned PID.
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise RuntimeError("This Python/platform lacks safe pidfd process management.")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    fd = libc.syscall(ctypes.c_long(434), ctypes.c_int(pid), ctypes.c_uint(0))
    if fd < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return fd


def process_start(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except (OSError, IndexError):
        return None


def owned(record: dict, run_id: str) -> bool:
    """A PID alone is never authority: verify UID, start time and private run tag."""
    pid = record.get("pid", 0)
    if not isinstance(pid, int) or pid <= 1:
        return False
    try:
        proc = Path(f"/proc/{pid}")
        return (proc.stat().st_uid == os.getuid()
                and process_start(pid) == record.get("start")
                and f"{TAG}={run_id}".encode() in (proc / "environ").read_bytes().split(b"\0"))
    except OSError:
        return False


def stop_process(record: dict, run_id: str) -> None:
    pid = record.get("pid", 0)
    if not owned(record, run_id):
        return
    # pidfds prevent signaling an unrelated process if a PID is recycled.
    try:
        fd = pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        if not owned(record, run_id):
            return
        signal.pidfd_send_signal(fd, signal.SIGTERM)
        deadline = time.monotonic() + 10
        while owned(record, run_id) and time.monotonic() < deadline:
            time.sleep(.1)
        if owned(record, run_id):
            signal.pidfd_send_signal(fd, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        os.close(fd)


def read_state() -> dict | None:
    if not STATE.exists():
        return None
    value = json.loads(STATE.read_text())
    if value.get("project") != str(ROOT) or not isinstance(value.get("run_id"), str):
        raise RuntimeError("Runtime state does not belong to this project; refusing to signal processes.")
    return value


def stop(state: dict | None) -> None:
    if not state:
        return
    for name in ("frontend", "backend"):
        stop_process(state.get(name, {}), state["run_id"])
    STATE.unlink(missing_ok=True)


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 100):
        with socket.socket() as candidate:
            try:
                candidate.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port near {preferred}; no existing service was stopped.")


def ready(url: str) -> bool:
    try:
        # Local readiness must not pass through a configured external HTTP proxy.
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def addresses(state: dict) -> None:
    backend = state["backend"]["port"]
    frontend = state["frontend"]["port"]
    print(f"Frontend: http://127.0.0.1:{frontend}/")
    print(f"Showcase: http://127.0.0.1:{frontend}/showcase")
    print(f"Live Studio: http://127.0.0.1:{frontend}/live")
    print(f"Backend: http://127.0.0.1:{backend}/api/health")
    print(f"Listening on 0.0.0.0; remote URL: http://<server-host>:{frontend}/showcase")
    print(f"SSH tunnel: ssh -N -L {frontend}:127.0.0.1:{frontend} <user>@<server-host>")
    print(f"PID state and logs: {RUNTIME}")


def start() -> None:
    state = read_state()
    if state and all(owned(state.get(name, {}), state["run_id"]) for name in ("backend", "frontend")):
        if (ready(f"http://127.0.0.1:{state['backend']['port']}/api/health")
                and ready(f"http://127.0.0.1:{state['frontend']['port']}/showcase")):
            addresses(state)
            return
        raise RuntimeError("Owned servers exist but are unhealthy; inspect logs or use stop_showcase.sh.")
    if state:
        stop(state)
    python = os.environ.get("SHOWCASE_PYTHON") or str(ROOT / ".venv/bin/python")
    if not Path(python).is_file():
        if os.environ.get("SHOWCASE_PYTHON"):
            raise RuntimeError("SHOWCASE_PYTHON must point to an existing Python executable.")
        python = sys.executable
    check = subprocess.run([python, "-c", "import fastapi, uvicorn, dotenv, teachintent.web_api"],
                           cwd=ROOT, capture_output=True, env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"})
    if check.returncode:
        raise RuntimeError("Python dependencies unavailable. Activate the app environment or set SHOWCASE_PYTHON; no install was attempted.")
    node = shutil.which("node")
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not node or not vite.is_file():
        raise RuntimeError("Node/Vite unavailable. Follow README frontend installation; no install was attempted.")
    backend, frontend = free_port(8000), free_port(5173)
    run_id = uuid4().hex
    run_dir = RUNTIME / run_id
    run_dir.mkdir()
    for name in ("tmp", "cache"):
        (RUNTIME / name).mkdir(exist_ok=True)
    env = {**os.environ, TAG: run_id, "PYTHONPATH": str(ROOT / "src"),
           "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(RUNTIME / "tmp"),
           "XDG_CACHE_HOME": str(RUNTIME / "cache"),
           "TEACHINTENT_API_TARGET": f"http://127.0.0.1:{backend}"}
    state = {"project": str(ROOT), "run_id": run_id}
    children = []
    try:
        for name, command, cwd, port in (
            ("backend", [python, "-B", "scripts/run_web_api.py", "--host", "0.0.0.0", "--port", str(backend)], ROOT, backend),
            ("frontend", [node, str(vite), "--host", "0.0.0.0", "--port", str(frontend), "--strictPort"], ROOT / "frontend", frontend),
        ):
            with (run_dir / f"{name}.log").open("ab") as log:
                process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            children.append(process)
            state[name] = {"pid": process.pid, "start": process_start(process.pid), "port": port,
                           "log": str(run_dir / f"{name}.log")}
            # Record each owned child immediately so stop can recover from an interrupted start.
            temporary = RUNTIME / "state.next.json"
            temporary.write_text(json.dumps(state, indent=2) + "\n")
            temporary.replace(STATE)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in children):
                raise RuntimeError(f"A showcase server exited; inspect logs in {run_dir}.")
            if ready(f"http://127.0.0.1:{backend}/api/health") and ready(f"http://127.0.0.1:{frontend}/showcase"):
                addresses(state)
                return
            time.sleep(.2)
        raise RuntimeError(f"Showcase startup timed out; inspect logs in {run_dir}.")
    except BaseException:
        stop(state)
        for child in children:
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop"))
    args = parser.parse_args()
    if not hasattr(signal, "pidfd_send_signal"):
        parser.error("Showcase process management requires Linux with Python 3.9+ pidfd support.")
    try:
        os.close(pidfd_open(os.getpid()))
    except (OSError, RuntimeError) as exc:
        parser.error(f"Safe process management unavailable: {exc}")
    if not RUNTIME.resolve().is_relative_to(ROOT.resolve()):
        parser.error("Runtime files must remain inside TeachIntent.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / "manager.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if args.action == "start":
                start()
            else:
                stop(read_state())
                print("Owned showcase servers stopped; other services and logs preserved.")
        except (OSError, ValueError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
