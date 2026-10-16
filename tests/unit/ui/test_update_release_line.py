"""The UI metadata refresh shares the job's release-line and prerelease policy."""

from unittest.mock import Mock

import pytest
import requests

from app import utils


@pytest.mark.parametrize(
    "current,releases,expected",
    [
        ("1.7.0", [("v1.8.0", False), ("v1.7.2", False), ("v1.6.99", False)], "1.7.2"),
        ("1.7.0-alpha", [("v1.8.0", False), ("v1.7.0-beta1", True)], "1.7.0-beta1"),
        ("1.7.0", [("v1.7.1-rc1", True)], "unknown"),
        ("1.7.0-alpha", [("v1.8.0", False), ("v1.6.99", False)], "unknown"),
    ],
)
def test_ui_selects_only_an_eligible_release(monkeypatch, current, releases, expected):
    response = Mock()
    response.json.return_value = [{"tag_name": tag, "prerelease": prerelease} for tag, prerelease in releases]
    monkeypatch.setattr(utils, "get", Mock(return_value=response))
    # raising=False lets the regression run against the old UI, which did not read its version.
    monkeypatch.setattr(utils, "get_version", lambda: current, raising=False)
    assert utils.get_latest_stable_release() == expected


def test_ui_fetches_an_older_page_for_its_own_line(monkeypatch):
    first, second = Mock(), Mock()
    first.json.return_value = [{"tag_name": "v1.8.0", "prerelease": False}] * 100
    second.json.return_value = [{"tag_name": "v1.7.2", "prerelease": False}]
    get = Mock(side_effect=[first, second])
    monkeypatch.setattr(utils, "get", get)
    monkeypatch.setattr(utils, "get_version", lambda: "1.7.0", raising=False)
    assert utils.get_latest_stable_release() == "1.7.2"
    assert get.call_count == 2


def test_ui_propagates_github_errors_for_metadata_refresh_to_retry(monkeypatch):
    monkeypatch.setattr(utils, "get", Mock(side_effect=requests.exceptions.HTTPError("GitHub rate limit")))
    with pytest.raises(requests.exceptions.HTTPError):
        utils.get_latest_stable_release()
