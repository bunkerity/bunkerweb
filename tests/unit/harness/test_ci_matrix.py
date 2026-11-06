"""UB5-8/9: run the real parser and guard CI fan-out, spelling and empty matrices."""

import json
import runpy
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def matrix(monkeypatch, tmp_path):
    for suite in ("core", "api", "ui", "utils"):
        (tmp_path / "tests" / suite).mkdir(parents=True)
    shutil.copy2(ROOT / "tests/utils/integrations.yml", tmp_path / "tests/utils/integrations.yml")
    package = ModuleType("utils")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "utils", package)
    monkeypatch.setitem(sys.modules, "utils.logger", ModuleType("utils.logger"))
    monkeypatch.chdir(tmp_path)
    outputs = {}
    write_text = Path.write_text

    def capture(path, content, *args, **kwargs):
        if path.parent == Path("/tmp/tests"):
            outputs[path.stem.removesuffix("_tests")] = json.loads(content)
            return len(content)
        return write_text(path, content, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", capture)

    def run(suite="core", dev=False, specs=None):
        for path in (tmp_path / "tests" / suite).glob("*.yml"):
            path.unlink()
        if specs is None:
            for path in (ROOT / "tests" / suite).glob("*.yml"):
                shutil.copy2(path, tmp_path / "tests" / suite / path.name)
        else:
            for name, data in specs.items():
                (tmp_path / "tests" / suite / f"{name}.yml").write_text(yaml.safe_dump(data))
        outputs.clear()
        monkeypatch.setattr(sys, "argv", ["parse.py", suite] + (["--dev"] if dev else []))
        runpy.run_path(str(ROOT / "tests/parse.py"), run_name="__main__")
        return outputs.copy()

    return run


def test_dev_linux_smoke_and_all_in_one_upgrade(matrix):
    result = matrix(dev=True)
    assert sorted(result["Linux"]) == [
        'Linux;amd64;ubuntu/noble;["ubuntu-latest"];api',
        'Linux;amd64;ubuntu/noble;["ubuntu-latest"];general',
        'Linux;amd64;ubuntu/noble;["ubuntu-latest"];upgrade',
    ]
    assert 'All_in_one;amd64;["ubuntu-latest"];upgrade' in result["All_in_one"]


@pytest.mark.parametrize("dev", [False, True])
def test_explicit_all_in_one_and_linux_runner_expansion(matrix, dev):
    result = matrix(dev=dev, specs={"smoke": {"integrations": ["All-in-one", "Linux;amd64;ubuntu/noble"]}})
    assert result["All_in_one"] == ['All_in_one;amd64;["ubuntu-latest"];smoke']
    assert result["Linux"] == ['Linux;amd64;ubuntu/noble;["ubuntu-latest"];smoke']


@pytest.mark.parametrize("suite", ["core", "api", "ui"])
@pytest.mark.parametrize("dev", [False, True])
def test_every_spec_reaches_a_matrix_arm(matrix, suite, dev):
    result = matrix(suite=suite, dev=dev)
    assert {entry.rsplit(";", 1)[1] for entries in result.values() for entry in entries} == {path.stem for path in (ROOT / "tests" / suite).glob("*.yml")}
    assert all("TODO" not in entry and "{'" not in entry for entries in result.values() for entry in entries)


def test_unknown_arm_is_reported_and_cannot_pass_empty(matrix, caplog):
    with pytest.raises(SystemExit) as failed:
        matrix(specs={"unknown": {"integrations": ["Missing"]}})
    assert failed.value.code == 1
    assert "Skipping integration Missing for unknown" in caplog.text
    assert "No test parsed" in caplog.text


def test_empty_suite_fails(matrix):
    with pytest.raises(SystemExit) as failed:
        matrix(specs={})
    assert failed.value.code == 1
