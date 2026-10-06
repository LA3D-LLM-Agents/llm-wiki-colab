"""Refuse to delete or rename a file this process still has open.

Windows refuses both; POSIX allows them, so code that relies on it passes
every test on Linux. Putting this directory on PYTHONPATH makes Python load
the module at startup, and the same code then fails here as it would there.
Open files are found through /proc/self/fd, so this works on Linux only.
"""
import os

_REAL = {name: getattr(os, name) for name in ("unlink", "remove", "replace", "rename")}


def _resolve(path, dir_fd):
    path = os.fsdecode(path)
    if dir_fd is not None and not os.path.isabs(path):
        path = os.path.join(os.readlink("/proc/self/fd/%d" % dir_fd), path)
    return os.path.realpath(path)


def _is_open(path, dir_fd):
    target = _resolve(path, dir_fd)
    for fd in os.listdir("/proc/self/fd"):
        try:
            if os.readlink("/proc/self/fd/" + fd) == target:
                return True
        except OSError:
            continue
    return False


def _refuse(path):
    # The errno and wording Python reports for ERROR_SHARING_VIOLATION.
    raise PermissionError(
        13, "The process cannot access the file because it is being used by another process",
        os.fsdecode(path))


# Callable objects, not functions: Python 3.9's pathlib stores os.unlink and
# friends as class attributes, where a plain function would bind as a method
# and receive an extra argument.
class _Unlink:
    def __init__(self, real):
        self._real = real

    def __call__(self, path, *, dir_fd=None):
        if _is_open(path, dir_fd):
            _refuse(path)
        return self._real(path, dir_fd=dir_fd)


class _Rename:
    def __init__(self, real):
        self._real = real

    def __call__(self, src, dst, *, src_dir_fd=None, dst_dir_fd=None):
        for path, dir_fd in ((src, src_dir_fd), (dst, dst_dir_fd)):
            if _is_open(path, dir_fd):
                _refuse(path)
        return self._real(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)


os.unlink = _Unlink(_REAL["unlink"])
os.remove = _Unlink(_REAL["remove"])
os.replace = _Rename(_REAL["replace"])
os.rename = _Rename(_REAL["rename"])
