import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from app.database.history import History, status
from app.services.catalog import Move, category
from app.services.operations import organize, recover, undo_last
from app.services.safety import Unsafe, locked, pinned, rename_locked
from app.services.scanner import extra_bytes, find_duplicates, preview, scan


@pytest.fixture
def desk(tmp_path, monkeypatch):
    # Windows pytest temp directories often live inside protected LocalAppData.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "mock-appdata"))
    folder = tmp_path / "Desk"
    folder.mkdir()
    return folder, History(tmp_path / "journal.sqlite")


def put(folder, name, data=b"content"):
    path = folder / name
    path.write_bytes(data)
    return path


def arrange(root, db):
    snap = scan(root)
    moves, issues = preview(snap)
    assert not issues
    return organize(db, snap, moves)


@pytest.mark.parametrize("name,expected", [
    ("photo.JPG", "Images"), ("talk.pdf", "Documents"), ("cut.MOV", "Videos"),
    ("song.flac", "Audio"), ("source.tar.gz", "Archives"), ("main.py", "Code"),
    ("setup.msi", "Installers"), ("LICENSE", "Other")])
def test_categories(name, expected):
    assert category(name) == expected


def test_preview_collision_and_roundtrip(desk):
    root, db = desk
    put(root, "hello.txt")
    (root / "Documents").mkdir()
    old = put(root / "Documents", "hello.txt", b"original")
    snap = scan(root)
    moves, issues = preview(snap)
    assert not issues and moves[0].target == "hello (2).txt"
    assert (root / "hello.txt").exists()
    assert organize(db, snap, moves).done == 1
    assert (root / "Documents" / moves[0].target).read_bytes() == b"content"
    session = db.latest_undo()
    assert status(session) == "Success"
    assert undo_last(db, session["id"]).done == 1
    assert (root / "hello.txt").read_bytes() == b"content"
    assert old.read_bytes() == b"original"
    assert status(db.sessions()[0]) == "Undone"


def test_hashes_only_same_content_and_top_level(desk):
    root, _ = desk
    for name, data in [("a", b"12"), ("b", b"12"), ("c", b"21"), ("d", b"123")]:
        put(root, name, data)
    (root / "nested").mkdir()
    put(root / "nested", "copy", b"12")
    groups, issues = find_duplicates(scan(root))
    assert not issues and [[e.name for e in g] for g in groups] == [["a", "b"]]


@pytest.mark.parametrize("change", ["missing", "modified", "occupied", "replaced"])
def test_unsafe_undo_is_retryable(desk, change):
    root, db = desk
    put(root, "a.txt")
    assert arrange(root, db).done == 1
    path = root / "Documents" / "a.txt"
    if change == "missing":
        path.rename(path.with_suffix(".away"))
    elif change == "occupied":
        put(root, "a.txt", b"someone else")
    elif change == "replaced":
        path.rename(path.with_suffix(".away"))
        put(path.parent, path.name)
    else:
        stamp = path.stat()
        path.write_bytes(b"altered")
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    result = undo_last(db, db.latest_undo()["id"])
    assert result.done == 0 and result.issues
    assert db.latest_undo()["available"] == 1
    assert status(db.sessions()[0]) == "Undo incomplete"


def test_collision_after_preview_and_changed_source(desk):
    root, db = desk
    for name in ["a.txt", "b.txt", "c.txt"]:
        put(root, name)
    snap = scan(root)
    plan, _ = preview(snap)
    (root / "Documents").mkdir()
    other = put(root / "Documents", "a.txt", b"mine")
    put(root, "b.txt", b"changed contents")
    result = organize(db, snap, plan)
    assert result.done == 1 and len(result.issues) == 2
    assert other.read_bytes() == b"mine"
    assert status(db.sessions()[0]) == "Partial success"


def test_traversal_and_protected_folders(desk):
    root, db = desk
    put(root, "a.txt")
    snap = scan(root)
    assert organize(db, snap, [Move(snap.files[0], "../escape")]).done == 0
    with pytest.raises(Unsafe):
        scan(Path(os.environ["SystemRoot"]))
    with pytest.raises(Unsafe):
        scan(Path(root.anchor))


def test_junction_rejected_in_scan_preview_and_move(desk):
    root, db = desk
    put(root, "a.txt")
    snap = scan(root)
    plan, _ = preview(snap)
    outside = root.parent / "outside"
    outside.mkdir()
    junction = root / "Documents"
    subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
                   check=True, capture_output=True)
    assert scan(root).issues
    assert not preview(snap)[0]
    assert organize(db, snap, plan).done == 0
    assert not list(outside.iterdir())
    with pytest.raises(Unsafe):
        scan(junction)


@pytest.mark.parametrize("phase,landed,expected", [
    ("moving", False, "failed"), ("moving", True, "moved"),
    ("restoring", False, "moved"), ("restoring", True, "restored")])
def test_recover_crash_boundary(desk, phase, landed, expected):
    root, db = desk
    source = put(root, "a.txt")
    snap = scan(root)
    plan, _ = preview(snap)
    sid = db.begin(snap, plan)
    row = db.rows(sid)[0]
    db.set_state(row["id"], phase, digest=hashlib.sha256(source.read_bytes()).hexdigest())
    target = root / "Documents" / source.name
    target.parent.mkdir()
    if (phase == "moving" and landed) or (phase == "restoring" and not landed):
        source.rename(target)
    recover(History(db.path))
    assert db.rows(sid)[0]["state"] == expected


def test_recovery_never_claims_unverified_move(desk):
    root, db = desk
    source = put(root, "a.txt")
    put(root, "b.txt")
    snap = scan(root)
    sid = db.begin(snap, preview(snap)[0])
    row = db.rows(sid)[0]
    db.set_state(row["id"], "moving", digest=hashlib.sha256(source.read_bytes()).hexdigest())
    (root / "Documents").mkdir()
    put(root / "Documents", "a.txt", b"unrelated")
    recover(db)
    assert [r["state"] for r in db.rows(sid)] == ["moving", "failed"]
    assert db.sessions()[0]["moved"] == 0


def test_directory_and_source_pinned_until_rename(desk):
    root, _ = desk
    source = put(root, "a.txt")
    snap = scan(root)
    with pinned(root, snap.root_id):
        with pytest.raises(PermissionError):
            root.rename(root.with_name("swapped"))
        with locked(source, snap.files[0], moving=True):
            with pytest.raises(PermissionError):
                source.rename(root / "other.txt")
            with pytest.raises(PermissionError):
                source.open("wb")
    assert source.read_bytes() == b"content"


def test_atomic_rename_rejects_already_occupied_name(desk):
    root, _ = desk
    src = put(root, "x.txt")
    snap = scan(root)
    target = put(root, "taken.txt", b"original")
    with pinned(root, snap.root_id, destination=True) as (_, _, directory):
        with locked(src, snap.files[0], moving=True) as stream:
            with pytest.raises(OSError):
                rename_locked(stream, target, directory)
    assert src.read_bytes() == b"content"
    assert target.read_bytes() == b"original"


def test_hard_links_share_storage(desk):
    root, _ = desk
    original = put(root, "a.txt")
    (root / "b.txt").hardlink_to(original)
    groups, issues = find_duplicates(scan(root))
    assert not issues and len(groups[0]) == 2
    assert extra_bytes(groups[0]) == 0

