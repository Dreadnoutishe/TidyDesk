"""A committed intent precedes every rename. Recovery only observes the disk."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import Entry
from .safety import Unsafe, digest, leaf, locked, pin_dir, pinned, rename_locked


@dataclass
class Result:
    done: int = 0
    issues: list[str] = field(default_factory=list)


def endpoints(root, entry, target):
    return root / leaf(entry.name), root / entry.group / leaf(target)


def run_rows(history, session, rows, undo, progress, moved):
    root = Path(session["root"])
    root_id = json.loads(session["root_id"])
    result = Result()
    for index, row in enumerate(rows):
        entry = Entry(**json.loads(row["entry"]))
        progress(index, len(rows), f"{'Restoring' if undo else 'Checking'} {entry.name}")
        renamed = False
        try:
            original, target = endpoints(root, entry, row["target"])
            source, dest = (target, original) if undo else (original, target)
            with pinned(root, root_id, destination=undo) as (stack, _, root_handle):
                if not undo:
                    target.parent.mkdir(exist_ok=True)
                category_handle, _ = pin_dir(stack, target.parent, destination=not undo)
                with locked(source, entry, moving=True) as stream:
                    if os.path.lexists(dest):
                        raise Unsafe("Destination is occupied. No file was replaced.")
                    fingerprint = digest(stream)
                    if undo and fingerprint != row["digest"]:
                        raise Unsafe("Contents changed since organization.")
                    history.set_state(row["id"], "restoring" if undo else "moving", digest=fingerprint)
                    rename_locked(stream, dest, root_handle if undo else category_handle)
                    renamed = True
                    if Entry.from_stat(entry.name, dest.lstat()) != entry:
                        raise Unsafe("Rename requires verification. Reopen TidyDesk to reconcile.")
                    history.set_state(row["id"], "restored" if undo else "moved")
                    result.done += 1
            moved(entry.group, undo)
        except (OSError, Unsafe) as error:
            note = str(error)
            state = ("restoring" if undo else "moving") if renamed else ("moved" if undo else "failed")
            history.set_state(row["id"], state, note)
            result.issues.append(f"{entry.name} — {note}")
        progress(index + 1, len(rows), f"{index + 1} of {len(rows)} checked")
    return result


def organize(history, snapshot, moves, progress=lambda *a: None, moved=lambda *a: None):
    if not moves:
        return Result()
    with pinned(snapshot.root, snapshot.root_id):
        session_id = history.begin(snapshot, moves)
    session = next(s for s in history.sessions() if s["id"] == session_id)
    return run_rows(history, session, history.rows(session_id), False, progress, moved)


def undo_last(history, expected_session, progress=lambda *a: None, moved=lambda *a: None):
    session = history.latest_undo()
    if not session or session["id"] != expected_session:
        raise Unsafe("History changed. Review the latest session again.")
    rows = [r for r in reversed(history.rows(session["id"])) if r["state"] == "moved"]
    return run_rows(history, session, rows, True, progress, moved)


def recover(history):
    for session in history.sessions():
        if not session["pending"]:
            continue
        root = Path(session["root"])
        for row in history.rows(session["id"]):
            state = row["state"]
            if state == "planned":
                history.set_state(row["id"], "failed", "Interrupted before moving.")
                continue
            if state not in {"moving", "restoring"}:
                continue
            entry = Entry(**json.loads(row["entry"]))
            try:
                original, target = endpoints(root, entry, row["target"])
                with pinned(root, json.loads(session["root_id"])) as (stack, _, _handle):
                    pin_dir(stack, target.parent)
                    present = [p for p in (original, target) if os.path.lexists(p)]
                    if len(present) != 1:
                        raise Unsafe("Cannot identify a single surviving location.")
                    with locked(present[0], entry) as stream:
                        if digest(stream) != row["digest"]:
                            raise Unsafe("File contents changed.")
                    if present[0] == target:
                        final = "moved"
                    else:
                        final = "restored" if state == "restoring" else "failed"
                    note = "Interrupted before moving." if final == "failed" else ""
                    history.set_state(row["id"], final, note)
            except (OSError, Unsafe) as error:
                history.set_state(row["id"], state, f"Review required: {error}")

