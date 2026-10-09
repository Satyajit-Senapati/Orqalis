"""Windows snapshot reads and atomic renames, without changing storage formats."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import ctypes
    import msvcrt as msvcrt
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _create_file = _kernel32.CreateFileW
    _create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _create_file.restype = wintypes.HANDLE
    _close_handle = _kernel32.CloseHandle
    _close_handle.argtypes = [wintypes.HANDLE]
    _close_handle.restype = wintypes.BOOL
    _set_information = _kernel32.SetFileInformationByHandle
    _set_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _set_information.restype = wintypes.BOOL

    class _RenameInfo(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("RootDirectory", wintypes.HANDLE),
            ("FileNameLength", wintypes.DWORD),
            ("FileName", wintypes.WCHAR * 1),
        ]

    def shared_read_opener(path: str, flags: int) -> int:
        """Return a read-only fd; its file object owns and closes the native handle."""

        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise ValueError("Snapshot opener only supports existing read-only files")
        # OPEN_EXISTING; READ|WRITE|DELETE sharing. Open the entry itself so a link
        # swapped in after the caller's path guard cannot redirect this read.
        handle = _create_file(path, 0x80000000, 0x7, None, 3, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.WinError(ctypes.get_last_error())
            error.filename = path
            raise error
        try:
            return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException as error:
            # Conversion did not transfer ownership to a CRT descriptor.
            if not _close_handle(handle):
                error.add_note("Failed to close the snapshot handle after descriptor conversion")
            raise

    def replace_file(source: Path, target: Path) -> None:
        """Rename one verified temporary atomically, retaining open-reader snapshots."""

        # Unlike ReplaceFileW, this is one rename and does not merge attributes or
        # remove the original path before moving the replacement. No ACL/read-only
        # bypass flags are requested. Caller retains its original bounded retries.
        name = str(target).encode("utf-16-le")
        size = max(ctypes.sizeof(_RenameInfo), _RenameInfo.FileName.offset + len(name) + 2)
        buffer = ctypes.create_string_buffer(size)
        info = _RenameInfo.from_buffer(buffer)
        info.Flags = 0x3  # REPLACE_IF_EXISTS | POSIX_SEMANTICS
        info.FileNameLength = len(name)
        ctypes.memmove(ctypes.addressof(buffer) + _RenameInfo.FileName.offset, name, len(name))
        # DELETE access to our own temporary; allow READ|WRITE|DELETE sharing.
        handle = _create_file(str(source), 0x00010000, 0x7, None, 3, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.WinError(ctypes.get_last_error())
            error.filename = str(source)
            raise error
        unsupported = False
        try:
            if not _set_information(handle, 22, buffer, size):  # FileRenameInfoEx
                code = ctypes.get_last_error()
                if code in {1, 50, 87}:  # Unsupported API/class/flags; no permission bypass.
                    unsupported = True
                else:
                    error = ctypes.WinError(code)
                    error.filename = str(source)
                    error.filename2 = str(target)
                    raise error
        finally:
            if not _close_handle(handle):
                error = ctypes.WinError(ctypes.get_last_error())
                primary = sys.exception()
                if primary is not None:
                    primary.add_note(f"Failed to close owned rename handle: {error}")
                else:
                    raise error
        if unsupported:
            # Older Windows/filesystems keep the previous atomic operation and its
            # error behavior; do not fall back on a permission/sharing denial.
            os.replace(source, target)

else:

    def shared_read_opener(path: str, flags: int) -> int:
        """Use the portable read opener outside Windows."""
        return os.open(path, flags)

    def replace_file(source: Path, target: Path) -> None:
        """Use the portable atomic replacement outside Windows."""
        os.replace(source, target)
