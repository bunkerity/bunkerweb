"""Native scheduler startup diagnostics."""

from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "src" / "linux" / "scripts" / "bunkerweb-scheduler.sh"


def test_incompatible_database_version_has_recovery_action():
    text = SCRIPT.read_text(encoding="utf-8")
    assert (
        '"Database version $current_version cannot be used by installed BunkerWeb $installed_version; '
        'restore a compatible database backup before starting this version"' in text
    )
