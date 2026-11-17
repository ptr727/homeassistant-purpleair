"""Interrupt tests for scripts/setup, which holds a background download child while it runs."""

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

# Each stub stands in for a tool the run reaches before the HACS download.
# The uv stub seeds the .venv the script activates, and the git stub reports no checkout.
# So the pre-commit and aiopurpleair steps skip.
# The markdownlint-cli2 and go2rtc stubs report their pinned versions, so their installs skip too.
# The curl stub records its process ID and blocks, holding the run inside the download snippet until it is stopped.
STUBS = {
    "uv": '#!/bin/sh\nif [ "$1" = venv ]; then mkdir -p .venv/bin && : > .venv/bin/activate; fi\n',
    "python": "#!/bin/sh\nexit 0\n",
    "git": "#!/bin/sh\necho 'fatal: not a git repository' >&2\nexit 128\n",
    "markdownlint-cli2": "#!/bin/sh\necho 'markdownlint-cli2 v0.22.1'\n",
    "go2rtc": "#!/bin/sh\necho 'go2rtc version 1.9.14'\n",
    "curl": '#!/bin/sh\necho $$ > "$CURL_PID_FILE"\nexec sleep 60\n',
}


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
def test_setup_interrupted_stops_its_download_and_dies_by_the_signal(
    tmp_path: Path, signum: signal.Signals
) -> None:
    """A signal mid-download stops the download, leaves nothing behind, prints one line, and re-raises."""
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    shutil.copy2(SETUP, checkout / "scripts" / "setup")

    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in STUBS.items():
        stub = stubs / name
        stub.write_text(body)
        stub.chmod(0o755)

    curl_pid_file = tmp_path / "curl.pid"
    env = {
        **os.environ,
        "PATH": os.pathsep.join(
            [str(stubs), str(Path(sys.executable).parent), "/usr/bin", "/bin"]
        ),
        "CURL_PID_FILE": str(curl_pid_file),
    }
    process = subprocess.Popen(
        ["bash", str(checkout / "scripts" / "setup")],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    curl_pid = 0
    try:
        curl_pid = int(_wait_for_file(curl_pid_file, timeout=30))
        process.send_signal(signum)
        _, stderr = process.communicate(timeout=10)
        curl_survived = _alive(curl_pid)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if curl_pid and _alive(curl_pid):
            os.kill(curl_pid, signal.SIGKILL)

    assert process.returncode == -signum
    assert stderr.splitlines()[-1:] == [f"scripts/setup: interrupted by {signum.name}"]
    assert "Traceback" not in stderr
    assert not curl_survived
    assert not (checkout / "config" / "custom_components").exists()
