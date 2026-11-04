"""app/models/ui_data.py (file-backed shared dict) and app/models/template.py (wizard templates)."""

import json

from app.models import template as template_module
from app.models.template import get_ui_templates
from app.models.ui_data import UIData


class TestUIData:
    def test_every_mutation_is_written_to_the_file(self, tmp_path):
        path = tmp_path / "data.json"
        data = UIData(path)
        data["a"] = 1
        assert json.loads(path.read_text()) == {"a": 1}
        data.update({"b": 2}, c=3)
        assert json.loads(path.read_text()) == {"a": 1, "b": 2, "c": 3}
        del data["a"]
        assert json.loads(path.read_text()) == {"b": 2, "c": 3}

    def test_a_second_instance_loads_what_the_first_wrote(self, tmp_path):
        path = tmp_path / "data.json"
        UIData(path)["k"] = "v"
        assert dict(UIData(path)) == {"k": "v"}

    def test_load_picks_up_a_peer_write_only_when_the_file_changed(self, tmp_path):
        path = tmp_path / "data.json"
        mine = UIData(path)
        peer = UIData(path)
        peer["from_peer"] = 1
        mine.load_from_file()
        assert mine["from_peer"] == 1

        # unchanged signature: a local, unsaved edit made through dict.__setitem__ must not be clobbered
        dict.__setitem__(mine, "from_peer", "local")
        mine.load_from_file()
        assert mine["from_peer"] == "local"

    def test_empty_file_loads_nothing(self, tmp_path):
        path = tmp_path / "data.json"
        path.write_text("")
        assert dict(UIData(path)) == {}

    def test_missing_file_is_not_created_until_a_write(self, tmp_path):
        path = tmp_path / "data.json"
        data = UIData(path)
        assert not path.exists()
        data["x"] = 1
        assert path.exists()


class TestGetUiTemplates:
    def _write(self, directory, name, body):
        (directory / name).write_text(body if isinstance(body, str) else json.dumps(body))

    def test_templates_are_flattened_for_the_ui(self, tmp_path, monkeypatch):
        self._write(
            tmp_path,
            "a.json",
            {
                "name": "A",
                "description": "first",
                "steps": [{"name": "s1", "description": "d1", "settings": {"USE_X": "yes", "Y": "1"}}],
                "extra": "ignored",
            },
        )
        monkeypatch.setattr(template_module, "glob", lambda pattern: [str(p) for p in sorted(tmp_path.glob("*.json"))])
        assert get_ui_templates() == [
            {
                "name": "A",
                "description": "first",
                "steps": [{"name": "s1", "description": "d1", "settings": [{"setting_id": "USE_X", "value": "yes"}, {"setting_id": "Y", "value": "1"}]}],
            }
        ]

    def test_broken_templates_are_skipped_not_fatal(self, tmp_path, monkeypatch):
        self._write(tmp_path, "bad.json", "{not json")
        self._write(tmp_path, "missing.json", {"name": "M"})
        self._write(tmp_path, "ok.json", {"name": "OK", "description": "", "steps": []})
        monkeypatch.setattr(template_module, "glob", lambda pattern: [str(p) for p in sorted(tmp_path.glob("*.json"))])
        assert [t["name"] for t in get_ui_templates()] == ["OK"]

    def test_the_search_pattern_is_the_install_dir(self, monkeypatch):
        seen = []
        monkeypatch.setattr(template_module, "glob", lambda pattern: seen.append(pattern) or [])
        assert get_ui_templates() == []
        assert seen == ["/usr/share/bunkerweb/templates/*.json"]
