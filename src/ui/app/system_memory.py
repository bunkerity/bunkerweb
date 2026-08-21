"""Memory reader for the dashboard RAM card.

``psutil.virtual_memory()`` reads ``/proc/meminfo``, which is **not** cgroup-aware: inside a
container it reports the *host*'s RAM, so the card describes a machine the operator is not
looking at. When a memory cgroup with a real limit is mounted we read that instead, and only
fall back to psutil when there is none (bare metal, or an unlimited cgroup).

"Used" excludes reclaimable page cache (``inactive_file``), the same subtraction ``docker
stats`` makes -- ``memory.current`` on its own drifts up to the limit as soon as the process
reads files, which would make the card cry wolf permanently.
"""

from pathlib import Path
from typing import Dict, Optional

from psutil import virtual_memory

CGROUP_ROOT = Path("/sys/fs/cgroup")

# cgroup v1 writes a sentinel rather than a keyword for "no limit": LONG_MAX rounded *down* to
# PAGE_SIZE. The value therefore depends on the page size -- 9223372036854771712 on a 4K-page
# kernel, but 9223372036854710272 on a 64K-page one (aarch64 RHEL, Ampere), which is *smaller*.
# Comparing against the 4K value would read the 64K sentinel as a real 8 EiB limit and the card
# would report "0.0 % of 8388608.0 GB". Test against a bound no real limit can reach instead:
# 4 EiB is ~500 million times the largest machine anyone runs this on.
_V1_UNLIMITED = 1 << 62


def _read_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _stat_field(path: Path, field: str) -> int:
    """Read one ``<key> <value>`` line out of a cgroup ``memory.stat``; 0 when absent."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(" ")
            if key == field:
                return int(value)
    except (OSError, ValueError):
        pass
    return 0


def _cgroup_v2(root: Path) -> Optional[Dict[str, int]]:
    limit_file = root / "memory.max"
    try:
        raw = limit_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if raw == "max":  # cgroup present but unlimited -- the host figures are the honest ones
        return None
    try:
        limit = int(raw)
    except ValueError:
        return None
    current = _read_int(root / "memory.current")
    if limit <= 0 or current is None:
        return None
    return {"total": limit, "used": max(0, current - _stat_field(root / "memory.stat", "inactive_file"))}


def _cgroup_v1(root: Path) -> Optional[Dict[str, int]]:
    limit = _read_int(root / "memory" / "memory.limit_in_bytes")
    usage_root = root / "memory"
    if limit is None:
        limit = _read_int(root / "memory.limit_in_bytes")
        usage_root = root
    if limit is None or limit <= 0 or limit >= _V1_UNLIMITED:
        return None
    usage = _read_int(usage_root / "memory.usage_in_bytes")
    if usage is None:
        return None
    return {"total": limit, "used": max(0, usage - _stat_field(usage_root / "memory.stat", "total_inactive_file"))}


def read_memory(cgroup_root: Path = CGROUP_ROOT) -> Dict[str, int]:
    """Total/used/available bytes for whatever this process is actually constrained by."""
    figures = _cgroup_v2(cgroup_root) or _cgroup_v1(cgroup_root)
    if figures is None:
        memory = virtual_memory()
        return {"total": memory.total, "used": memory.used, "available": memory.available}
    figures["used"] = min(figures["used"], figures["total"])
    figures["available"] = figures["total"] - figures["used"]
    return figures


def memory_state(used_percent: float) -> str:
    """Colour band for the RAM card -- driven by USAGE only, never by how big the box is."""
    if used_percent >= 95:
        return "danger"
    if used_percent >= 85:
        return "warning"
    if used_percent >= 70:
        return "neutral"
    return "good"
