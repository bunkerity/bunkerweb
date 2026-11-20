"""Built images minify ``javascript.html``; the PoW solver must still hash the real 20-character random.

The solver used to size its prefix from the literal ``"{*random*}"`` placeholder, which html-minifier-terser folds to
``10``: the browser then hashed half of the random the server hashes and every solve was rejected. This test minifies the
page with the flags of ``src/all-in-one/Dockerfile``, renders it with a real random, runs the shipped solver under node
and checks the nonce the way ``antibot:check_challenge`` does (``sha256(random .. nonce)`` with enough leading zero bits).
Refs: antibot JavaScript challenge 429 loop on built images.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(os.environ.get("BW_UNIT_T2_SRC") or ROOT / "src")
PAGE = SRC / "common" / "core" / "antibot" / "files" / "javascript.html"
MINIFIER = ROOT / "src" / "deps" / "node_modules" / ".bin" / "html-minifier-terser"
NODE = shutil.which("node") or "node"

pytestmark = pytest.mark.skipif(shutil.which("node") is None or not MINIFIER.exists(), reason="node and html-minifier-terser are required")

RANDOM = "q7Zk2RmXb9LpT4vNw8Ys"  # the server's rand(20): 20 characters
DIFFICULTY = 16
# Flags of the "Minify HTML files" step of src/all-in-one/Dockerfile.
MINIFY_FLAGS = [
    "--collapse-whitespace",
    "--remove-comments",
    "--remove-optional-tags",
    "--remove-redundant-attributes",
    "--remove-script-type-attributes",
    "--remove-style-link-type-attributes",
    "--minify-css",
    "true",
    "--minify-js",
    "true",
]

# Runs the page's only inline script on a DOM stub; no Worker, so the main-thread solver is the one exercised.
DRIVER = r"""
const vm = require("vm");
const { script, random, difficulty } = JSON.parse(require("fs").readFileSync(0, "utf8"));
const rendered = script.split("{*random*}").join(random).split("{*antibot_difficulty*}").join(String(difficulty));
let submitted = null;
const form = {
  getAttribute: (name) => (name === "data-random" ? random : null),
  submit: () => { submitted = String(challenge.value); },
};
const challenge = { value: "" };
const element = () => new Proxy(function () {}, {
  get: (t, k) => (k === Symbol.toPrimitive ? () => 1 : k === "classList" ? { add() {}, remove() {}, toggle() {}, contains: () => false } : k === "style" ? {} : element()),
  set: () => true,
  apply: () => element(),
});
const document = {
  getElementById: (id) => (id === "form" ? form : id === "challenge" ? challenge : element()),
  querySelector: () => element(),
  querySelectorAll: () => [],
  documentElement: element(),
  body: element(),
  addEventListener() {},
  createElement: () => element(),
};
const raf = (fn) => setImmediate(fn);
const window = {
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }), addEventListener() {},
  setTimeout, clearTimeout, requestAnimationFrame: raf, devicePixelRatio: 1, innerWidth: 800, innerHeight: 600,
};
const context = vm.createContext({
  document, window, navigator: { hardwareConcurrency: 1 }, performance, Date, Uint8Array, Uint32Array, Math, parseInt, String,
  console, localStorage: { getItem: () => null, setItem() {} }, setTimeout, clearTimeout,
  requestAnimationFrame: raf,
});
vm.runInContext(rendered, context);
const started = Date.now();
(function wait() {
  if (submitted !== null) { process.stdout.write(JSON.stringify({ nonce: submitted })); process.exit(0); }
  if (Date.now() - started > 20000) { process.stdout.write(JSON.stringify({ nonce: null })); process.exit(0); }
  setTimeout(wait, 5);
})();
"""


def _leading_zero_bits(digest: bytes) -> int:
    value = int.from_bytes(digest, "big")
    return 256 - value.bit_length()


def _solve(page: Path) -> str | None:
    match = re.search(r"<script[^>]*>(.*?)</script>", page.read_text(), re.S)
    assert match, "no inline script in the page"
    script = match.group(1)
    payload = json.dumps({"script": script, "random": RANDOM, "difficulty": DIFFICULTY})
    out = subprocess.run([NODE, "-e", DRIVER], input=payload, capture_output=True, text=True, check=True, timeout=60)
    return json.loads(out.stdout)["nonce"]


def _minified(tmp_path: Path) -> Path:
    target = tmp_path / "javascript.html"
    shutil.copy(PAGE, target)
    subprocess.run([NODE, str(MINIFIER.resolve()), *MINIFY_FLAGS, "--output", str(target), str(target)], check=True, capture_output=True, timeout=120)
    return target


def test_minified_solver_nonce_verifies_against_the_real_random(tmp_path):
    assert len(RANDOM) == 20
    nonce = _solve(_minified(tmp_path))
    assert nonce is not None, "solver never submitted a nonce"
    digest = hashlib.sha256((RANDOM + nonce).encode()).digest()
    assert _leading_zero_bits(digest) >= DIFFICULTY


def test_unminified_solver_nonce_verifies_too():
    nonce = _solve(PAGE)
    assert nonce is not None
    assert _leading_zero_bits(hashlib.sha256((RANDOM + nonce).encode()).digest()) >= DIFFICULTY
