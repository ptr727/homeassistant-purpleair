"""Interrupt tests for scripts/setup, which holds a background child while it runs."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

SETUP = Path(__file__).parents[2] / "scripts" / "setup"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows cannot deliver SIGINT or SIGTERM to a script",
)


def _alive(pid: int) -> bool:
    """Return whether a process with this ID still exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_for_file(path: Path, timeout: float) -> str:
    """Return the file's content once a writer has filled it, or fail at the timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and (text := path.read_text().strip()):
            return text
        time.sleep(0.05)
    pytest.fail(f"{path.name} was not written within {timeout} seconds")


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_setup_interrupted_stops_its_child_and_dies_by_the_signal(
    tmp_path: Path, signum: signal.Signals
) -> None:
    """A signal mid-run stops the running child, prints one line, and re-raises."""
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    shutil.copy2(SETUP, checkout / "scripts" / "setup")

    # The stub stands in for uv, whose first call creates the .venv, and blocks until it is stopped.
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    child_pid_file = tmp_path / "child.pid"
    stub = stubs / "uv"
    stub.write_text(f'#!/bin/sh\necho $$ > "{child_pid_file}"\nexec sleep 60\n')
    stub.chmod(0o755)

    env = {**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"}
    process = subprocess.Popen(
        ["bash", str(checkout / "scripts" / "setup")],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = 0
    try:
        child_pid = int(_wait_for_file(child_pid_file, timeout=10))
        process.send_signal(signum)
        _, stderr = process.communicate(timeout=10)
        child_survived = _alive(child_pid)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if child_pid and _alive(child_pid):
            os.kill(child_pid, signal.SIGKILL)

    assert process.returncode == -signum
    assert stderr.splitlines() == [f"scripts/setup: interrupted by {signum.name}"]
    assert not child_survived
