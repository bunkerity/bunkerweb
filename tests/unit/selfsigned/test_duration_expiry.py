"""SELF_SIGNED_SSL_EXPIRY accepts the 1.6.16 time suffixes and reaches openssl as a count of days."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from test_key_pair_integrity import SELF_SIGNED


def _days_passed_to_openssl(tmp_path, expiry):
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        for flag in ("-keyout", "-out"):
            open(command[command.index(flag) + 1], "wb").write(b"x")
        return SimpleNamespace(returncode=0)

    job = Mock()
    job.cache_file.return_value = (True, None)
    job.get_cache.return_value = None
    with patch.object(SELF_SIGNED, "JOB", job), patch.object(SELF_SIGNED, "sep", str(tmp_path)), patch.object(SELF_SIGNED, "run", fake_run), patch.object(
        SELF_SIGNED, "LOGGER", Mock()
    ):
        ret, _ = SELF_SIGNED.generate_cert("www.example.com", expiry, "/CN=www.example.com/", tmp_path / "selfsigned", ["www.example.com"])
    assert ret
    return commands[0][commands[0].index("-days") + 1]


@pytest.mark.parametrize(
    ("expiry", "days"),
    [("365", "365"), ("1y", "365"), ("30d", "30"), ("2w", "14"), ("1M", "30"), ("48h", "2"), ("12h", "1"), ("90", "90"), ("abc", "365"), ("", "365")],
)
def test_expiry_is_passed_to_openssl_as_days(tmp_path, expiry, days):
    assert _days_passed_to_openssl(tmp_path, expiry) == days
