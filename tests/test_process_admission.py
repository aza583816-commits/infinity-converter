from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core import admission


@pytest.mark.skipif(admission.fcntl is None, reason="process-shared flock gate is a Linux production feature")
def test_one_slot_blocks_second_holder_until_release(tmp_path, monkeypatch):
    monkeypatch.setattr(admission, "_ADMISSION_DIR", tmp_path)
    first = admission.acquire_slot("conversion-test", 1, 0.1)
    assert first is not None
    started = time.monotonic()
    second = admission.acquire_slot("conversion-test", 1, 0.08)
    elapsed = time.monotonic() - started
    assert second is None
    assert elapsed >= 0.05
    first.release()
    third = admission.acquire_slot("conversion-test", 1, 0.1)
    assert third is not None
    third.release()


@pytest.mark.skipif(admission.fcntl is None, reason="process-shared flock gate is a Linux production feature")
def test_lock_is_shared_across_processes(tmp_path, monkeypatch):
    monkeypatch.setattr(admission, "_ADMISSION_DIR", tmp_path)
    token = admission.acquire_slot("cross-process", 1, 0.1)
    assert token is not None

    script = (
        "from pathlib import Path; import core.admission as a; "
        f"a._ADMISSION_DIR=Path({str(tmp_path)!r}); "
        "t=a.acquire_slot('cross-process',1,0.05); "
        "print('acquired' if t else 'blocked'); "
        "t.release() if t else None"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    assert result.stdout.strip() == "blocked"
    token.release()


def test_admission_token_release_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(admission, "_ADMISSION_DIR", tmp_path)
    token = admission.acquire_slot("idempotent", 1, 0.1)
    assert token is not None
    token.release()
    token.release()
