import re
import subprocess
import unittest
from json import dumps
from pathlib import Path

from redis import Redis

REPO = Path(__file__).resolve().parents[2]
FILE = "src/common/core/metrics/metrics.lua"
FIELDS = ["ip", "country", "method", "url", "status", "reason", "server_name", "security_mode"]
KEYS = ["requests", "requests:facets:initialized", "requests:facets:rebuilding", "requests:facets:oomprobe"] + [f"requests:facet:{f}" for f in FIELDS]


def scripts(source: str) -> dict:
    return {name: body for name, body in re.findall(r"local (\w+_SCRIPT) = \[==\[(.*?)\]==\]", source, re.S)}


def dump(r: Redis) -> dict:
    out = {}
    for key in sorted(r.keys("requests*")):
        kind = r.type(key)
        if kind == b"list":
            out[key] = r.lrange(key, 0, -1)
        elif kind == b"hash":
            out[key] = sorted(r.hgetall(key).items())
        elif kind == b"string" and key != b"requests:facets:oomprobe":
            out[key] = r.get(key)
    return out


def report(i: int) -> tuple:
    row = {
        "id": f"id{i}",
        "date": 1700000000 + i,
        "ip": f"10.0.0.{i % 3}",
        "country": "FR",
        "method": "GET",
        "url": f"/p{i % 2}",
        "status": 403,
        "reason": "modsecurity",
        "server_name": "app",
        "security_mode": "block",
    }
    return dumps(row), [str(row[f]) for f in FIELDS]


class ReportScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cid = subprocess.check_output(["docker", "run", "-d", "--rm", "-p", "127.0.0.1:16399:6379", "valkey/valkey:8"], text=True).strip()
        cls.r = Redis(port=16399)
        for _ in range(50):
            try:
                cls.r.ping()
                break
            except Exception:
                subprocess.run(["sleep", "0.2"])
        cls.old = scripts(subprocess.check_output(["git", "-C", str(REPO), "show", f"HEAD:{FILE}"], text=True))
        cls.new = scripts((REPO / FILE).read_text())

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["docker", "rm", "-f", cls.cid], capture_output=True)

    def run_sequence(self, s: dict, new: bool) -> dict:
        self.r.flushall()
        keys = KEYS if new else ["requests"]

        def ev(name, *argv):
            return self.r.eval(s[name], len(keys), *keys, *argv)

        ev("REBUILD_SCRIPT", "0")
        for i in range(20):
            payload, facets = report(i)
            ev("PUSH_SCRIPT", payload, *facets, "0")
        ev("HEALTH_SCRIPT")
        ev("TRIM_SCRIPT", "12")
        self.r.delete("requests:facets:initialized", "requests:facets:rebuilding")
        ev("REBUILD_SCRIPT", "1")
        ev("TRIM_SCRIPT", "0")
        payload, facets = report(99)
        ev("PUSH_SCRIPT", payload, *facets, "1")
        return dump(self.r)

    def test_new_scripts_match_old(self):
        self.assertEqual(self.run_sequence(self.old, False), self.run_sequence(self.new, True))

    def test_no_undeclared_keys(self):
        for name, body in self.new.items():
            self.assertNotIn("'requests", body, name)


if __name__ == "__main__":
    unittest.main()
