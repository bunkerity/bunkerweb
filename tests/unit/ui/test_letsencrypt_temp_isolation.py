"""LE dashboard cleanup leaves concurrent requests' files alone."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("failure", [False, True])
def test_cleanup_only_removes_own_request(tmp_path, monkeypatch, failure):
    spec = spec_from_file_location("le_actions_isolation", ROOT / "src/common/core/letsencrypt/ui/actions.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "Path", lambda *args: tmp_path)
    monkeypatch.setattr(module, "uuid4", lambda: "own-request")
    sibling = tmp_path / "letsencrypt" / "other-request" / "cert.pem"
    sibling.parent.mkdir(parents=True)
    sibling.write_bytes(b"other request")
    api = Mock()
    api.get_cache_files.return_value = []
    if failure:
        api.get_cache_files.side_effect = RuntimeError("original API error")
    result = module.pre_render(None, api_client=api)
    assert sibling.read_bytes() == b"other request"
    assert not (tmp_path / "letsencrypt" / "own-request").exists()
    assert result.get("error") == ("original API error" if failure else None)
