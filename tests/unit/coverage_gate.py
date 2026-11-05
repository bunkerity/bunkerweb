"""Enforce component line and branch coverage floors, including unimported files."""

import argparse
from fnmatch import fnmatch
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from coverage import Coverage, CoverageData
from coverage.exceptions import CoverageException

# Floors only go up.
FLOORS = {
    "src/common/gen": 88,
    "src/common/db": 78,
    "src/common/utils + src/common/cli": 90,
    "src/api": 90,
    "src/ui": 92,
    "src/autoconf": 95,
    "src/scheduler": 92,
    "src/common/core/*/jobs": 86,
    "src/common/core/*/ui": 94,
}
OVERALL_FLOOR = 89
BRANCH_FLOORS = {
    "src/common/gen": 82,
    "src/common/db": 71,
    "src/common/utils + src/common/cli": 84,
    "src/api": 86,
    "src/ui": 87,
    "src/autoconf": 93,
    "src/scheduler": 86,
    "src/common/core/*/jobs": 79,
    "src/common/core/*/ui": 91,
}
OVERALL_BRANCH_FLOOR = 83

ROOT = Path(__file__).resolve().parents[2]


def component_for(path):
    if path.startswith(("src/common/utils/", "src/common/cli/", "src/common/api/")):
        return "src/common/utils + src/common/cli"
    if path.startswith("src/common/core/"):
        if "/ui/" in path:
            return "src/common/core/*/ui"
        if "/jobs/" in path or path.startswith("src/common/core/backup/"):
            return "src/common/core/*/jobs"
    for component in FLOORS:
        if path.startswith(component + "/"):
            return component
    raise ValueError(f"No coverage component configured for {path}")


def collect_components(root, data_files):
    rows = {
        component: {
            "component": component,
            "statements": 0,
            "covered": 0,
            "branches": None,
            "covered_branches": None,
            "floor": floor,
            "branch_floor": BRANCH_FLOORS[component],
        }
        for component, floor in FLOORS.items()
    }
    with TemporaryDirectory(prefix="bw-coverage-gate-") as directory:
        coverage = Coverage(data_file=str(Path(directory) / ".coverage"), config_file=str(root / "pyproject.toml"))
        combined = coverage.get_data()
        for index, path in enumerate(data_files):
            if not path.is_file():
                raise ValueError(f"Coverage data file does not exist: {path}")
            # Coverage.py can initialize an empty input database while reading it.
            copied = Path(directory) / f"input-{index}"
            copyfile(path, copied)
            data = CoverageData(basename=str(copied))
            data.read()
            combined.update(data)

        if combined.has_arcs():
            for row in rows.values():
                row.update(branches=0, covered_branches=0)
        omit = coverage.get_option("run:omit") or []
        for path in sorted((root / "src").rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if any(fnmatch(relative, pattern) for pattern in omit):
                continue
            row = rows[component_for(relative)]
            _, statements, _, missing, _ = coverage.analysis2(str(path))
            row["statements"] += len(statements)
            row["covered"] += len(statements) - len(missing)
            if combined.has_arcs():
                # analysis2 has no branch counts; use the same Coverage.py analysis behind it.
                numbers = coverage._analyze(str(path)).numbers
                row["branches"] += numbers.n_branches
                row["covered_branches"] += numbers.n_branches - numbers.n_missing_branches

    for row in rows.values():
        evaluate(row)
    return list(rows.values())


def evaluate(row):
    row["coverage"] = 100 * row["covered"] / row["statements"] if row["statements"] else 100.0
    row["branch_coverage"] = None if row["branches"] is None else (100 * row["covered_branches"] / row["branches"] if row["branches"] else 100.0)
    row["gap"] = max(0, (row["statements"] * row["floor"] + 99) // 100 - row["covered"])
    row["branch_gap"] = None if row["branches"] is None else max(0, (row["branches"] * row["branch_floor"] + 99) // 100 - row["covered_branches"])
    row["passed"] = row["gap"] == 0 and row["branch_gap"] in (None, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_files", nargs="+", type=Path, help="Coverage.py data files to union (inputs are preserved)")
    parser.add_argument("--json", type=Path, help="Write component results as JSON")
    args = parser.parse_args()
    try:
        if args.json and args.json.resolve() in {path.resolve() for path in args.data_files}:
            raise ValueError("JSON output must not overwrite a coverage data input")
        rows = collect_components(ROOT, args.data_files)
        overall = {"component": "Overall", "floor": OVERALL_FLOOR, "branch_floor": OVERALL_BRANCH_FLOOR}
        for key in ("statements", "covered", "branches", "covered_branches"):
            overall[key] = None if any(row[key] is None for row in rows) else sum(row[key] for row in rows)
        evaluate(overall)
        passed = overall["passed"] and all(row["passed"] for row in rows)
        if args.json:
            args.json.write_text(json.dumps({"passed": passed, "components": rows, "overall": overall}, indent=2) + "\n", encoding="utf-8")
    except (CoverageException, OSError, ValueError) as error:
        parser.error(str(error))

    width = max(len(row["component"]) for row in rows)
    print(
        f"{'Component':<{width}}  {'Statements':>10}  {'Covered':>7}  {'%':>7}  {'Branch %':>8}  "
        f"{'Floor':>5}  {'Branch floor':>12}  {'Gap':>7}  {'Branch gap':>10}"
    )
    for row in [*rows, overall]:
        branches = "n/a" if row["branch_coverage"] is None else f"{row['branch_coverage']:.2f}%"
        branch_gap = "n/a" if row["branch_gap"] is None else str(row["branch_gap"])
        print(
            f"{row['component']:<{width}}  {row['statements']:>10}  {row['covered']:>7}  {row['coverage']:>6.2f}%  "
            f"{branches:>8}  {row['floor']:>4}%  {row['branch_floor']:>11}%  {row['gap']:>7}  {branch_gap:>10}"
        )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
