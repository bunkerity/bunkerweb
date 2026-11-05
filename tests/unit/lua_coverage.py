"""Opt-in LuaCov collection for every Lua subprocess, plus LCOV/JSON coverage reports.

Install LuaCov as pinned in unit-tests.yml, export its LuaRocks path, then:
    python tests/unit/lua_coverage.py run .cache/lua-coverage -- python -m pytest tests/unit
    python tests/unit/lua_coverage.py report .cache/lua-coverage --fail-under 94
Use a fresh output directory for each measurement; repeated runs accumulate.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HELPER = Path(__file__).with_suffix(".lua")


def coverage_env(directory: Path) -> dict[str, str]:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "BW_LUA_COVERAGE_DIR": str(directory), "LUACOV_CONFIG": str(ROOT / ".luacov")}
    # Version-specific LUA_INIT overrides LUA_INIT; cover both Lua 5.4 and LuaJIT.
    for name in ("LUA_INIT", "LUA_INIT_5_1", "LUA_INIT_5_4"):
        env[name] = "@" + str(HELPER)
    return env


def report(directory: Path, *, root: Path = ROOT) -> dict:
    directory = directory.resolve()
    sources = sorted(path.resolve() for base in (root / "src/bw/lua", root / "src/common/core") for path in base.rglob("*.lua"))
    stats = sorted(directory.glob("*.stats.out"))
    if not stats:
        raise ValueError("No LuaCov stats: run the unit suite through lua_coverage.py run first")
    env = {key: value for key, value in os.environ.items() if not key.startswith("LUA_INIT") and key != "BW_LUA_COVERAGE_DIR"}
    env["LUACOV_CONFIG"] = str(ROOT / ".luacov")
    subprocess.run(
        ["lua", str(HELPER), "report", str(root.resolve()), str(directory / "coverage.lcov"), *(str(path) for path in stats)],
        input="".join(f"{path}\n" for path in sources),
        text=True,
        env=env,
        check=True,
        timeout=120,
    )
    files: list[dict[str, Any]] = []
    for record in (directory / "coverage.lcov").read_text().split("end_of_record\n"):
        if not record.strip():
            continue
        entries = record.splitlines()
        path = next(line[3:] for line in entries if line.startswith("SF:"))
        counts = [tuple(map(int, line[3:].split(","))) for line in entries if line.startswith("DA:")]
        files.append(
            {"path": path, "lines": len(counts), "covered": sum(hits > 0 for _, hits in counts), "missing": [line for line, hits in counts if not hits]}
        )
    expected = {str(path.relative_to(root.resolve())) for path in sources}
    if {row["path"] for row in files} != expected or not any(row["covered"] for row in files):
        raise ValueError("Incomplete Lua coverage report or no measured source lines")
    groups: dict[str, dict[str, Any]] = {}
    for row in files:
        source_path = Path(row["path"])
        group = "src/bw/lua/bunkerweb" if source_path.is_relative_to("src/bw/lua/bunkerweb") else "src/bw/lua (other)"
        if source_path.is_relative_to("src/common/core"):
            group = str(Path(*source_path.parts[:4]))
        aggregate = groups.setdefault(group, {"path": group, "lines": 0, "covered": 0})
        for key in ("lines", "covered"):
            aggregate[key] += row[key]
    total: dict[str, Any] = {"path": "TOTAL", "lines": sum(row["lines"] for row in files), "covered": sum(row["covered"] for row in files)}
    for row in [*files, *groups.values(), total]:
        row["percent"] = 100 * row["covered"] / row["lines"] if row["lines"] else 100.0
    data = {"total": total, "directories": list(groups.values()), "files": files}
    (directory / "coverage.json").write_text(json.dumps(data, indent=2) + "\n")
    table = "| Path | Lines hit | Executable lines | Coverage |\n| --- | ---: | ---: | ---: |\n"
    for row in [*groups.values(), total, *files]:
        table += f"| `{row['path']}` | {row['covered']} | {row['lines']} | {row['percent']:.2f}% |\n"
    (directory / "baseline.md").write_text(table)
    print(table, end="")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    run_parser = actions.add_parser("run", help="Collect coverage from a command")
    run_parser.add_argument("directory", type=Path)
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    report_parser = actions.add_parser("report", help="Report merged coverage and optionally enforce a floor")
    report_parser.add_argument("directory", type=Path)
    report_parser.add_argument("--fail-under", type=float, help="Fail below this percentage (0–100)")
    args = parser.parse_args()
    if args.action == "report":
        if args.fail_under is not None and not 0 <= args.fail_under <= 100:
            parser.error("--fail-under must be between 0 and 100")
        data = report(args.directory)
        if args.fail_under is not None:
            percent = data["total"]["percent"]
            print(f"Lua coverage {percent:.2f}% (floor {args.fail_under:g}%)")
            return int(percent < args.fail_under)
        return 0
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("run requires a command after --")
    return subprocess.run(command, env=coverage_env(args.directory), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
