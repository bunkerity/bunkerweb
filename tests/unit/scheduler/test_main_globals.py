"""src/scheduler/main.py: `main()` must declare `global` every module name it assigns and others share.

The signal handlers and a few helpers read SCHEDULER / JOB and write RELOAD_SCAN_CONFIGS as module
globals. `main()` assigns them, so without a `global` statement it would bind a local of the same
name and the handlers would keep reading the stale module value, with no error anywhere. The check
is made on the AST, so it never imports the module. MAIN_PY points it at another copy of the file
(one with a `global` removed, to watch it fail).
"""

import ast
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MAIN = Path(os.environ.get("MAIN_PY", REPO / "src" / "scheduler" / "main.py"))


def _scope_names(function):
    """Names a function body binds (assignments, loop targets, except-as, nested defs), nested scopes excluded."""
    bound, declared_global = set(), set()

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bound.add(child.name)
                continue
            if isinstance(child, (ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(child, ast.Global):
                declared_global.update(child.names)
            elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                bound.add(child.id)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                bound.add(child.name)
            visit(child)

    for argument in (*function.args.args, *function.args.kwonlyargs, function.args.vararg, function.args.kwarg):
        if argument:
            bound.add(argument.arg)
    visit(function)
    return bound, declared_global


def _free_loads(function):
    """Names a function reads without binding them locally (they resolve to module globals)."""
    bound, declared_global = _scope_names(function)
    loads = {n.id for n in ast.walk(function) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return (loads - bound) | (loads & declared_global)


def check_main_globals(source):
    """Return (missing, shadowed): shared names `main()` assigns without `global`, and top-level names it shadows."""
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    main = functions["main"]
    main_bound, main_globals = _scope_names(main)

    module_bound = set(functions)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_bound.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.ClassDef):
            module_bound.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.If, ast.Try, ast.For, ast.With)):
            module_bound.update(n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))

    shared = set()
    for name, function in functions.items():
        if name == "main":
            continue
        shared |= _free_loads(function) | _scope_names(function)[1]

    missing = (main_bound & shared) - main_globals
    # A module-level name `main()` binds without `global` is a shadow: harmless only when nothing else reads it.
    shadowed = (main_bound & module_bound) - main_globals
    return missing, shadowed


def test_main_exists_and_the_module_has_a_guarded_entry_point():
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body)
    guards = [n for n in tree.body if isinstance(n, ast.If) and ast.get_source_segment(MAIN.read_text(encoding="utf-8"), n.test) == '__name__ == "__main__"']
    assert len(guards) == 1
    assert [ast.get_source_segment(MAIN.read_text(encoding="utf-8"), s) for s in guards[0].body] == ["main()"]


def test_main_declares_every_shared_module_name_global():
    missing, _ = check_main_globals(MAIN.read_text(encoding="utf-8"))
    assert not missing, f"main() assigns {sorted(missing)} without `global`: the signal handlers and helpers would read stale module values"


def test_main_binds_no_module_level_name_by_accident():
    _, shadowed = check_main_globals(MAIN.read_text(encoding="utf-8"))
    assert not shadowed, f"main() rebinds module-level names {sorted(shadowed)} as locals"


def test_the_expected_shared_names_are_the_ones_found():
    """Pin the three shared names, so the detector is known to see JOB, SCHEDULER and RELOAD_SCAN_CONFIGS."""
    source = (REPO / "src" / "scheduler" / "main.py").read_text(encoding="utf-8")
    broken = source.replace("global SCHEDULER, JOB, RELOAD_SCAN_CONFIGS", "pass")
    assert broken != source
    missing, _ = check_main_globals(broken)
    assert missing == {"SCHEDULER", "JOB", "RELOAD_SCAN_CONFIGS"}
