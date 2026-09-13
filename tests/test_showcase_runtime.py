"""Process ownership and port selection for the local showcase launcher."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location("showcase_runtime", Path(__file__).resolve().parents[1] / "scripts/showcase_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def test_port_selection_leaves_existing_listener_alone():
    with socket.socket() as listener:
        listener.bind(("0.0.0.0", 0))
        listener.listen()
        port = listener.getsockname()[1]
        chosen = runtime.free_port(port)
        assert chosen != port
        assert listener.getsockname()[1] == port


def test_stop_verifies_tag_and_start_time_before_signaling():
    tag = "teachintent-test-process"
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], env={**os.environ, runtime.TAG: tag})
    try:
        record = {"pid": child.pid, "start": runtime.process_start(child.pid)}
        assert runtime.owned(record, tag)
        runtime.stop_process(record, "unrelated-run")
        runtime.stop_process({**record, "start": "wrong-start"}, tag)
        assert child.poll() is None
        runtime.stop_process(record, tag)
        child.wait(timeout=3)
        assert not runtime.owned(record, tag)
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=3)


def test_foreign_state_is_rejected(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text('{"project":"not-this-project","run_id":"other"}')
    monkeypatch.setattr(runtime, "STATE", state)
    with pytest.raises(RuntimeError, match="does not belong"):
        runtime.read_state()


def test_stale_pid_is_not_signal_authority():
    assert not runtime.owned({"pid": 0, "start": "1"}, "test")
    assert not runtime.owned({"pid": os.getpid(), "start": runtime.process_start(os.getpid())}, "unrelated")
