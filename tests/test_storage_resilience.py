import os
import time
from pathlib import Path

from core.storage import TempWorkspace, cleanup_stale_workspaces


def test_stale_workspace_sweep_removes_only_old_infinity_directories(tmp_path):
    now = time.time()
    old_dir = tmp_path / "infinity-v7-old"
    fresh_dir = tmp_path / "infinity-v7-fresh"
    unrelated = tmp_path / "other-old"
    old_dir.mkdir()
    fresh_dir.mkdir()
    unrelated.mkdir()
    (old_dir / "artifact.bin").write_bytes(b"old")
    (fresh_dir / "artifact.bin").write_bytes(b"fresh")
    (unrelated / "artifact.bin").write_bytes(b"keep")
    os.utime(old_dir, (now - 7200, now - 7200))
    os.utime(fresh_dir, (now, now))
    os.utime(unrelated, (now - 7200, now - 7200))

    removed = cleanup_stale_workspaces(root=tmp_path, older_than_seconds=3600, now=now)

    assert removed == 1
    assert not old_dir.exists()
    assert fresh_dir.exists()
    assert unrelated.exists()


def test_stale_workspace_sweep_ignores_symlinks(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "infinity-v7-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        return

    removed = cleanup_stale_workspaces(root=tmp_path, older_than_seconds=3600, now=time.time() + 7200)

    assert removed == 0
    assert link.is_symlink()
    assert target.exists()


def test_temp_workspace_cleanup_stays_idempotent_and_scoped():
    workspace = TempWorkspace().__enter__()
    assert workspace.path is not None
    root = Path(workspace.path)
    inside = workspace.input_dir / "input.txt"
    inside.write_text("safe", encoding="utf-8")
    assert workspace.contains_input(inside)
    workspace.cleanup()
    workspace.cleanup()
    assert not root.exists()
