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


def _contending_process(directory, start, active, peak, guard, results):
    from pathlib import Path
    import core.admission as gate
    gate._ADMISSION_DIR=Path(directory)
    start.wait(5)
    token=gate.acquire_slot('stress-shared',3,5)
    if token is None:
        results.put(False);return
    with guard:
        active.value+=1;peak.value=max(peak.value,active.value)
    time.sleep(.15)
    with guard:active.value-=1
    token.release();results.put(True)


@pytest.mark.skipif(admission.fcntl is None,reason='Requires Linux process-shared production gate')
def test_eight_competing_processes_never_exceed_three_conversion_slots(tmp_path):
    import multiprocessing
    context=multiprocessing.get_context('spawn')
    start=context.Event();active=context.Value('i',0);peak=context.Value('i',0)
    guard=context.Lock();results=context.Queue()
    workers=[context.Process(target=_contending_process,args=(str(tmp_path),start,active,peak,guard,results)) for _ in range(8)]
    try:
        for worker in workers:worker.start()
        start.set()
        for worker in workers:worker.join(10)
        assert all(worker.exitcode==0 for worker in workers)
        assert all(results.get(timeout=2) for _ in workers)
        assert peak.value==3 and active.value==0
    finally:
        for worker in workers:
            if worker.is_alive():worker.terminate();worker.join(2)
        results.close();results.join_thread()


@pytest.mark.skipif(admission.fcntl is None,reason='Requires Linux kernel lock release')
def test_crashed_worker_slot_is_reclaimed_without_stale_lock_cleanup(tmp_path,monkeypatch):
    monkeypatch.setattr(admission,'_ADMISSION_DIR',tmp_path)
    script=("from pathlib import Path; import os; import core.admission as a; "
            f"a._ADMISSION_DIR=Path({str(tmp_path)!r}); "
            "t=a.acquire_slot('crashed-worker',1,1); assert t is not None; os._exit(17)")
    result=subprocess.run([sys.executable,'-c',script],capture_output=True,timeout=5)
    assert result.returncode==17
    recovered=admission.acquire_slot('crashed-worker',1,.1)
    assert recovered is not None
    recovered.release()
