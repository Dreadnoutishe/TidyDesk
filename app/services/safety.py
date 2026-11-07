"""Windows handle-based reads and no-replace renames.

Keep the complete directory chain pinned during each operation. A file handle
denies writers and competing renames from identity validation through commit.
"""
import ctypes as c
import hashlib
import msvcrt
import os
import stat
from contextlib import ExitStack, contextmanager
from ctypes import wintypes as w
from pathlib import Path

from .catalog import Entry

kernel = c.WinDLL("kernel32", use_last_error=True)
open_handle = kernel.CreateFileW
open_handle.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
open_handle.restype = w.HANDLE
close_handle = kernel.CloseHandle
close_handle.argtypes = [w.HANDLE]
ntdll = c.WinDLL("ntdll")
set_info = ntdll.NtSetInformationFile
set_info.argtypes = [w.HANDLE, w.LPVOID, w.LPVOID, w.ULONG, c.c_int]
set_info.restype = w.LONG
ntdll.RtlNtStatusToDosError.argtypes = [w.LONG]
ntdll.RtlNtStatusToDosError.restype = w.ULONG
REPARSE = stat.FILE_ATTRIBUTE_REPARSE_POINT
SYSTEM = stat.FILE_ATTRIBUTE_SYSTEM


class Unsafe(ValueError):
    pass


def leaf(name):
    if (not name or name in {".", ".."} or name.endswith((" ", "."))
            or any(ch in '<>:"/\\|?*' or ord(ch) < 32 for ch in name)
            or Path(name).is_reserved()):
        raise Unsafe("Unsafe file or folder name.")
    return name


def check_root(root):
    if not root.is_absolute() or root.drive.startswith("\\") or root == Path(root.anchor):
        raise Unsafe("Choose a folder on a local drive.")
    if kernel.GetDriveTypeW(str(root.anchor)) not in (2, 3):
        raise Unsafe("Choose a folder on a local fixed or removable drive.")
    for part in root.parts[1:]:
        leaf(part)
    protected = ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData",
                 "LOCALAPPDATA", "APPDATA")
    if any(root.is_relative_to(Path(os.environ[k])) for k in protected if k in os.environ):
        raise Unsafe("Choose a personal folder outside system and application data.")
    if any(part.lower() in {"$recycle.bin", "system volume information", "recovery"}
           for part in root.parts):
        raise Unsafe("This is a protected folder.")


def handle(path, access, share, is_dir=False):
    flags = 0x00200000 | (0x02000000 if is_dir else 0)  # OPEN_REPARSE_POINT, BACKUP_SEMANTICS
    h = open_handle(str(path), access, share, None, 3, flags, None)
    if h == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    return h


def pin_dir(stack, path, *, destination=False):
    # LIST_DIRECTORY participates in sharing checks; attribute-only access
    # does not pin the directory against a competing rename or reparse write.
    # The kernel briefly requests add-file access on the rename destination.
    # Keep delete sharing disabled there and address it by this exact handle.
    h = handle(path, 0x81, 3 if destination else 1, True)
    stack.callback(close_handle, h)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_file_attributes & REPARSE:
        raise Unsafe("Linked or non-directory folder.")
    return h, info


@contextmanager
def pinned(root, expected=None, *, destination=False):
    check_root(root)
    with ExitStack() as stack:
        for ancestor in reversed(root.parents):
            pin_dir(stack, ancestor)
        root_handle, info = pin_dir(stack, root, destination=destination)
        # Resolve Windows short-name aliases after pinning every ancestor.
        check_root(root.resolve(strict=True))
        ident = (info.st_dev, info.st_ino)
        if expected is not None and tuple(expected) != ident:
            raise Unsafe("The selected folder has been replaced.")
        yield stack, ident, root_handle


@contextmanager
def locked(path, entry, *, moving=False):
    leaf(path.name)
    h = handle(path, 0x80000000 | (0x10000 if moving else 0), 1)
    try:
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY)
    except Exception:
        close_handle(h)
        raise
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_file_attributes & (REPARSE | SYSTEM)
                or not info.st_ino or Entry.from_stat(entry.name, info) != entry):
            raise Unsafe("File changed, is protected, or was replaced. Scan again.")
        yield stream


def digest(stream, tick=lambda: None):
    hasher = hashlib.sha256()
    while block := stream.read(1024 * 1024):
        hasher.update(block)
        tick()
    return hasher.hexdigest()


class RenameInfo(c.Structure):
    _fields_ = [("flags", w.DWORD), ("root", w.HANDLE), ("length", w.DWORD), ("name", w.WCHAR * 1)]


def rename_locked(stream, target, directory_handle):
    encoded = leaf(target.name).encode("utf-16-le")
    size = max(c.sizeof(RenameInfo), RenameInfo.name.offset + len(encoded) + 2)
    data = c.create_string_buffer(size)
    header = RenameInfo.from_buffer(data)
    header.root = directory_handle
    header.length = len(encoded)  # Zero flags prohibit replacement.
    c.memmove(c.addressof(data) + RenameInfo.name.offset, encoded, len(encoded))
    # The native call accepts an already-open destination directory. The
    # Win32 convenience wrapper requires a full path and reopens its parent.
    io_status = (c.c_void_p * 2)()
    status = set_info(msvcrt.get_osfhandle(stream.fileno()), io_status, data, size, 10)
    if status < 0:
        raise c.WinError(ntdll.RtlNtStatusToDosError(status))

