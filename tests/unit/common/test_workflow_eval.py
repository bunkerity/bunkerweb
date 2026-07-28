"""The three-valued algebra a workflow condition tree is evaluated with.

Pinned exhaustively because every entry is a security decision: an UNKNOWN that should have
been FALSE makes a rule stop matching, and a rule that stops matching is an opening nothing
reports. The two short-circuit rules are checked with a sentinel child that raises if it is
evaluated — the only way to prove ALL stops on FALSE *and*, crucially, that it does not stop
on UNKNOWN.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "common" / "core" / "workflows" / "eval.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
local eval = dofile("%s")
local F, T, U = eval.FALSE, eval.TRUE, eval.UNKNOWN

local function leaf(value)
    return { f = function() return value end }
end

local function boom()
    return { f = function() error("this child must not be evaluated") end }
end

local function node(op, ...)
    return { op = op, ... }
end

local function check(label, got, want)
    assert(got == want, label .. " : expected " .. tostring(want) .. ", got " .. tostring(got))
end

-- ALL / ANY truth table, all nine combinations.
local table_all = { [F] = { [F] = F, [T] = F, [U] = F }, [T] = { [F] = F, [T] = T, [U] = U }, [U] = { [F] = F, [T] = U, [U] = U } }
local table_any = { [F] = { [F] = F, [T] = T, [U] = U }, [T] = { [F] = T, [T] = T, [U] = T }, [U] = { [F] = U, [T] = T, [U] = U } }
local names = { [F] = "F", [T] = "T", [U] = "U" }
for _, a in ipairs({ F, T, U }) do
    for _, b in ipairs({ F, T, U }) do
        check("ALL(" .. names[a] .. "," .. names[b] .. ")", eval.run(node(eval.ALL, leaf(a), leaf(b)), {}), table_all[a][b])
        check("ANY(" .. names[a] .. "," .. names[b] .. ")", eval.run(node(eval.ANY, leaf(a), leaf(b)), {}), table_any[a][b])
    end
end

-- NOT, including the fixed point on UNKNOWN.
check("NOT F", eval.run(node(eval.NOT, leaf(F)), {}), T)
check("NOT T", eval.run(node(eval.NOT, leaf(T)), {}), F)
check("NOT U", eval.run(node(eval.NOT, leaf(U)), {}), U)

-- ALL stops at the first FALSE, ANY at the first TRUE.
check("ALL short-circuits on FALSE", eval.run(node(eval.ALL, leaf(F), boom()), {}), F)
check("ANY short-circuits on TRUE", eval.run(node(eval.ANY, leaf(T), boom()), {}), T)

-- ...but neither may stop on UNKNOWN: a later FALSE still settles an ALL, a later TRUE an ANY.
check("ALL keeps going past UNKNOWN", eval.run(node(eval.ALL, leaf(U), leaf(F)), {}), F)
check("ANY keeps going past UNKNOWN", eval.run(node(eval.ANY, leaf(U), leaf(T)), {}), T)
local reached = false
eval.run(node(eval.ALL, leaf(U), { f = function() reached = true return T end }), {})
assert(reached, "ALL must evaluate the child after an UNKNOWN")

-- Nesting: leaves receive the request context, and depth composes.
local tree = node(eval.ALL, node(eval.ANY, leaf(F), leaf(T)), node(eval.NOT, leaf(F)))
check("nested", eval.run(tree, {}), T)
local seen
eval.run({ f = function(bw) seen = bw.country return T end }, { country = "FR" })
assert(seen == "FR", "the leaf must receive the request context")

-- A single-child ALL behaves as its child (what the compiler emits for a one-predicate rule).
check("single child", eval.run(node(eval.ALL, leaf(U)), {}), U)

print("OK")
"""


def test_the_three_valued_algebra():
    result = subprocess.run(["lua", "-e", HARNESS % MODULE.as_posix()], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
