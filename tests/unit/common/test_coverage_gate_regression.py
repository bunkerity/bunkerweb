"""Coverage floors must count unimported code and preserve their input datasets.

The gate must union executed lines, honor exclusions, round required lines up and refuse destructive output paths.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from coverage import CoverageData


@pytest.fixture
def gate_tree(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "coverage_gate.py"
    spec = importlib.util.spec_from_file_location("u3_coverage_gate", script)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.coverage.run]\nomit = ["src/deps/**", "src/common/db/alembic/**", "**/gunicorn.conf.py", "src/common/core/modsecurity/files/**"]\n'
    )

    def source(name, content="value = 1\n"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def dataset(name, lines):
        path = tmp_path / name
        data = CoverageData(basename=str(path))
        data.add_lines({str(path): executed for path, executed in lines.items()})
        data.write()
        return path

    def gen(*inputs):
        return next(row for row in gate.collect_components(tmp_path, inputs) if row["component"] == "src/common/gen")

    return SimpleNamespace(gate=gate, source=source, dataset=dataset, gen=gen, root=tmp_path)


def test_never_imported_python_counts_toward_floor(gate_tree):
    tree = gate_tree
    known = tree.source("src/common/gen/known.py")
    tree.source("src/common/gen/unseen.py", "first = 1\nsecond = 2\n")
    row = tree.gen(tree.dataset("data", {known: [1]}))
    assert (row["statements"], row["covered"], row["gap"], row["passed"]) == (3, 1, 2, False)


@pytest.mark.parametrize(
    "omitted",
    ["src/deps/vendor.py", "src/common/db/alembic/sqlite_versions/revision.py", "src/api/gunicorn.conf.py", "src/common/core/modsecurity/files/tool.py"],
)
def test_configured_omissions_do_not_count(gate_tree, omitted):
    tree = gate_tree
    known = tree.source("src/common/gen/known.py")
    tree.source(omitted)
    rows = tree.gate.collect_components(tree.root, [tree.dataset("data", {known: [1]})])
    assert sum(row["statements"] for row in rows) == 1
    assert sum(row["covered"] for row in rows) == 1


def test_datasets_union_without_double_counting(gate_tree):
    tree = gate_tree
    known = tree.source("src/common/gen/known.py", "first = 1\nsecond = 2\nthird = 3\n")
    first = tree.dataset("first", {known: [1, 2]})
    second = tree.dataset("second", {known: [2, 3]})
    before = [path.read_bytes() for path in (first, second)]
    row = tree.gen(first, second)
    assert (row["statements"], row["covered"], row["gap"], row["passed"]) == (3, 3, 0, True)
    assert [path.read_bytes() for path in (first, second)] == before


def test_zero_byte_input_remains_zero_bytes(gate_tree):
    tree = gate_tree
    tree.source("src/common/gen/unseen.py")
    empty = tree.root / "empty"
    empty.touch()
    assert tree.gen(empty)["covered"] == 0
    assert empty.read_bytes() == b""


def test_cli_rounds_fractional_floor_up_and_writes_results(gate_tree, monkeypatch):
    tree = gate_tree
    known = tree.source("src/common/gen/known.py", "first = 1\nsecond = 2\nthird = 3\n")
    first = tree.dataset("first", {known: [1, 2]})
    second = tree.dataset("second", {known: [3]})
    output = tree.root / "result.json"
    for inputs, code, covered, gap in [([first], 1, 2, 1), ([first, second], 0, 3, 0)]:
        monkeypatch.setattr(sys, "argv", ["coverage_gate.py", *map(str, inputs), "--json", str(output)])
        assert tree.gate.main() == code
        report = json.loads(output.read_text())
        row = next(row for row in report["components"] if row["component"] == "src/common/gen")
        assert (row["statements"], row["covered"], row["gap"], report["passed"]) == (3, covered, gap, code == 0)


@pytest.mark.parametrize("alias", [False, True], ids=["same-path", "symlink"])
def test_cli_refuses_output_input_collision(gate_tree, monkeypatch, capsys, alias):
    tree = gate_tree
    known = tree.source("src/common/gen/known.py")
    data = tree.dataset("data", {known: [1]})
    output = data
    if alias:
        output = tree.root / "alias"
        output.symlink_to(data)
    before = data.read_bytes()
    monkeypatch.setattr(sys, "argv", ["coverage_gate.py", str(data), "--json", str(output)])
    with pytest.raises(SystemExit) as error:
        tree.gate.main()
    assert error.value.code == 2
    assert "must not overwrite a coverage data input" in capsys.readouterr().err
    assert data.read_bytes() == before


@pytest.mark.parametrize("branch_config", [False, True])
def test_cli_reports_branches_without_changing_statement_coverage(gate_tree, monkeypatch, capsys, branch_config):
    tree = gate_tree
    config = tree.root / "pyproject.toml"
    config.write_text(config.read_text().replace("[tool.coverage.run]", f"[tool.coverage.run]\nbranch = {str(branch_config).lower()}"))
    known = tree.source("src/common/gen/known.py", "if flag:\n    value = 1\nelse:\n    value = 2\n")
    tree.source("src/common/gen/unseen.py", "if flag:\n    value = 1\nelse:\n    value = 2\n")
    data_path = tree.root / "branches"
    data = CoverageData(basename=str(data_path))
    data.add_arcs({str(known): [(-1, 1), (1, 2), (2, -1)]})
    data.write()
    before = data_path.read_bytes()
    output = tree.root / "result.json"
    monkeypatch.setattr(sys, "argv", ["coverage_gate.py", str(data_path), "--json", str(output)])
    assert tree.gate.main() == 1
    row = next(row for row in json.loads(output.read_text())["components"] if row["component"] == "src/common/gen")
    assert (row["statements"], row["covered"]) == (6, 2)
    assert (row["branches"], row["covered_branches"], row["branch_coverage"]) == (4, 1, 25.0)
    table = capsys.readouterr().out
    assert "Branch %" in table
    assert "25.00%" in table
    assert data_path.read_bytes() == before


def test_line_only_data_reports_branches_as_unmeasured(gate_tree):
    tree = gate_tree
    known = tree.source("src/common/gen/known.py")
    assert tree.gen(tree.dataset("data", {known: [1]}))["branch_coverage"] is None


def test_cli_enforces_overall_floor_even_when_components_pass(gate_tree, monkeypatch, capsys):
    tree = gate_tree
    monkeypatch.setattr(tree.gate, "FLOORS", {"src/common/gen": 70})
    known = tree.source("src/common/gen/known.py", "first = 1\nsecond = 2\nthird = 3\nfourth = 4\nfifth = 5\n")
    output = tree.root / "result.json"
    for lines, code, covered, gap in [([1, 2, 3, 4], 1, 4, 1), ([1, 2, 3, 4, 5], 0, 5, 0)]:
        data = tree.dataset(f"data-{covered}", {known: lines})
        monkeypatch.setattr(sys, "argv", ["coverage_gate.py", str(data), "--json", str(output)])
        assert tree.gate.main() == code
        report = json.loads(output.read_text())
        assert all(row["passed"] for row in report["components"])
        assert report["passed"] == (code == 0)
        row = report["overall"]
        assert (row["statements"], row["covered"], row["gap"], row["passed"]) == (5, covered, gap, code == 0)
        assert row["floor"] >= 83
    assert "Overall" in capsys.readouterr().out
