"""Publish complete renders for startup and offline output; runtime uses /confs."""

from os import replace
from pathlib import Path
from shutil import rmtree

RESERVED_PREFIX = ".bw-"
INSTALL_SENTINEL = f"{RESERVED_PREFIX}install-incomplete"


def _remove(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        rmtree(path)


def sync_tree(source: Path, destination: Path) -> None:
    """Install on one filesystem, retaining the sentinel on any failure."""
    destination.mkdir(parents=True, exist_ok=True)
    sentinel = destination / INSTALL_SENTINEL
    sentinel.touch()

    def walk(src: Path, dst: Path, root: bool = False) -> None:
        if not root and (dst.is_symlink() or (dst.exists() and not dst.is_dir())):
            _remove(dst)
        dst.mkdir(parents=True, exist_ok=True)
        wanted = set()
        for entry in src.iterdir():
            if root and entry.name.startswith(RESERVED_PREFIX):
                continue
            wanted.add(entry.name)
            target = dst / entry.name
            if entry.is_dir() and not entry.is_symlink():
                walk(entry, target)
            else:
                if target.is_dir() and not target.is_symlink():
                    _remove(target)
                replace(entry, target)
        for entry in dst.iterdir():
            if entry.name not in wanted and not (root and entry.name.startswith(RESERVED_PREFIX)):
                _remove(entry)

    walk(source, destination, True)
    sentinel.unlink()
