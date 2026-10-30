"""Enforce component line-coverage floors, including files never imported by tests."""

import argparse
from fnmatch import fnmatch
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from coverage import Coverage, CoverageData
from coverage.exceptions import CoverageException

FLOORS = {
    "src/common/gen": 70,
    "src/common/db": 70,
    "src/common/utils + src/common/cli": 70,
    "src/api": 70,
    "src/ui": 50,
    "src/autoconf": 50,
    "src/scheduler": 50,
    "src/common/core/*/jobs": 50,
    "src/common/core/*/ui": 50,
}

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
    rows = {component: {"component": component, "statements": 0, "covered": 0, "floor": floor} for component, floor in FLOORS.items()}
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

        omit = coverage.get_option("run:omit") or []
        for path in sorted((root / "src").rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if any(fnmatch(relative, pattern) for pattern in omit):
                continue
            row = rows[component_for(relative)]
            _, statements, _, missing, _ = coverage.analysis2(str(path))
            row["statements"] += len(statements)
            row["covered"] += len(statements) - len(missing)

    for row in rows.values():
        row["coverage"] = 100 * row["covered"] / row["statements"] if row["statements"] else 100.0
        row["gap"] = max(0, (row["statements"] * row["floor"] + 99) // 100 - row["covered"])
        row["passed"] = row["gap"] == 0
    return list(rows.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_files", nargs="+", type=Path, help="Coverage.py data files to union (inputs are preserved)")
    parser.add_argument("--json", type=Path, help="Write component results as JSON")
    args = parser.parse_args()
    try:
        if args.json and args.json.resolve() in {path.resolve() for path in args.data_files}:
            raise ValueError("JSON output must not overwrite a coverage data input")
        rows = collect_components(ROOT, args.data_files)
        passed = all(row["passed"] for row in rows)
        if args.json:
            args.json.write_text(json.dumps({"passed": passed, "components": rows}, indent=2) + "\n", encoding="utf-8")
    except (CoverageException, OSError, ValueError) as error:
        parser.error(str(error))

    width = max(len(row["component"]) for row in rows)
    print(f"{'Component':<{width}}  {'Statements':>10}  {'Covered':>7}  {'%':>7}  {'Floor':>5}  {'Gap':>7}")
    for row in rows:
        print(f"{row['component']:<{width}}  {row['statements']:>10}  {row['covered']:>7}  {row['coverage']:>6.2f}%  {row['floor']:>4}%  {row['gap']:>7}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
