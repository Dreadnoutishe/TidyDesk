import os
import shutil
import stat
from collections import defaultdict
from pathlib import Path

from .catalog import Entry, Move, Scan
from .safety import REPARSE, SYSTEM, Unsafe, digest, leaf, locked, pin_dir, pinned


def scan(root, progress=lambda *args: None):
    root = Path(root)
    files, issues = [], []
    with pinned(root) as (_, ident, _handle):
        for i, path in enumerate(root.iterdir(), 1):
            progress(i, 0, "Scanning folder")
            try:
                info = path.lstat()
                if info.st_file_attributes & (REPARSE | SYSTEM):
                    issues.append(f"{path.name} — linked or protected item")
                elif stat.S_ISREG(info.st_mode):
                    leaf(path.name)
                    files.append(Entry.from_stat(path.name, info))
            except (OSError, Unsafe) as error:
                issues.append(f"{path.name} — {error}")
        try:
            free = shutil.disk_usage(root).free
        except OSError:
            free = None
    return Scan(root, ident, sorted(files, key=lambda e: e.name.casefold()), issues, free)


def extra_bytes(group):
    # Several hard-link names can refer to the same physical file.
    identities = {(entry.device, entry.inode) for entry in group}
    return group[0].size * (len(identities) - 1)


def by_size(entries):
    groups = defaultdict(list)
    for entry in entries:
        groups[entry.size].append(entry)
    return [g for g in groups.values() if len(g) > 1]


def find_duplicates(snapshot, progress=lambda *args: None):
    candidates = [entry for group in by_size(snapshot.files) for entry in group]
    matched = defaultdict(list)
    issues = list(snapshot.issues)
    with pinned(snapshot.root, snapshot.root_id):
        for i, entry in enumerate(candidates):
            def tick():
                progress(i, len(candidates), f"Checking {entry.name}")
            tick()
            try:
                with locked(snapshot.root / entry.name, entry) as stream:
                    matched[(entry.size, digest(stream, tick))].append(entry)
            except (OSError, Unsafe) as error:
                issues.append(f"{entry.name} — {error}")
    return [g for g in matched.values() if len(g) > 1], issues


def preview(snapshot):
    moves, issues, reserved = [], [], {}
    with pinned(snapshot.root, snapshot.root_id) as (stack, _, _handle):
        for entry in snapshot.files:
            folder = snapshot.root / entry.group
            if folder not in reserved:
                try:
                    if os.path.lexists(folder):
                        pin_dir(stack, folder)
                        reserved[folder] = {p.name.casefold() for p in folder.iterdir()}
                    else:
                        reserved[folder] = set()
                except (Unsafe, OSError) as error:
                    reserved[folder] = str(error)
            used = reserved[folder]
            if isinstance(used, str):
                issues.append(f"{entry.name} — {entry.group} unavailable: {used}")
                continue
            path = Path(entry.name)
            target, index = entry.name, 2
            while target.casefold() in used:
                target = f"{path.stem} ({index}){path.suffix}"
                index += 1
            used.add(target.casefold())
            moves.append(Move(entry, target))
    return moves, issues

