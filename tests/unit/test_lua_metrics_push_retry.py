"""PUSH_SCRIPT uncertain-retry scan, run against a throwaway redis-server.

The script text is extracted from metrics.lua itself. Set METRICS_LUA_SOURCE to another copy
(for example `git show HEAD:...`) to run the same checks against an older revision.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import redis

SOURCE = Path(os.environ.get("METRICS_LUA_SOURCE") or Path(__file__).resolve().parents[2] / "src/common/core/metrics/metrics.lua")
SCRIPT = re.search(r"PUSH_SCRIPT = \[==\[(.*?)\]==\]", SOURCE.read_text(), re.S).group(1)
KEYS = ["reports", "reports:state", "reports:k3", "reports:probe"] + [f"reports:f{i}" for i in range(8)]
ROWS = 32000

SEED = """
for i = 1, tonumber(ARGV[1]) do
  local id = string.format('%032x', i)
  redis.call('RPUSH', KEYS[1], cjson.encode({id=id, date=i, ip='1.2.3.4', url='/x', status=403, reason='modsecurity',
    server_name='example.com', data={msg=string.rep('x', 200)}}))
end
"""


def row(n):
    return json.dumps({"id": f"{n:032x}", "date": n, "ip": "1.2.3.4", "url": "/x", "status": 403, "reason": "modsecurity"}, separators=(",", ":"))


class PushRetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        cls.dir = tempfile.mkdtemp()
        cls.proc = subprocess.Popen(
            ["redis-server", "--port", str(port), "--bind", "127.0.0.1", "--save", "", "--appendonly", "no", "--dir", cls.dir],
            stdout=subprocess.DEVNULL,
        )
        cls.r = redis.Redis(port=port, decode_responses=True)
        for _ in range(50):
            try:
                cls.r.ping()
                break
            except redis.ConnectionError:
                time.sleep(0.1)

    def setUp(self):
        self.r.delete(*KEYS)
        self.r.eval(SEED, 1, KEYS[0], ROWS)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def push(self, payload, uncertain):
        before = self.r.info("commandstats").get("cmdstat_lrange", {}).get("calls", 0)
        res = self.r.eval(SCRIPT, len(KEYS), *KEYS, payload, *["a"] * 8, "1" if uncertain else "0")
        after = self.r.info("commandstats").get("cmdstat_lrange", {}).get("calls", 0)
        return res, after - before

    def test_tail_hit_is_bounded(self):
        length = self.r.llen(KEYS[0])
        res, lranges = self.push(self.r.lindex(KEYS[0], -1), True)
        self.assertEqual(res, [length, 1])
        self.assertLessEqual(lranges, 4)
        self.assertEqual(self.r.llen(KEYS[0]), length)

    def test_id_match_inside_window_returns_position(self):
        length = self.r.llen(KEYS[0])
        stored = json.loads(self.r.lindex(KEYS[0], -500))
        res, lranges = self.push(json.dumps({"id": stored["id"], "date": 1}), True)  # same id, different payload
        self.assertEqual(res, [length - 499, 1])
        self.assertLessEqual(lranges, 4)

    def test_miss_pushes_once(self):
        length = self.r.llen(KEYS[0])
        payload = row(10**9)
        res, lranges = self.push(payload, True)
        self.assertLessEqual(lranges, 4)
        self.assertEqual(res[0], length + 1)
        self.assertEqual(self.r.llen(KEYS[0]), length + 1)
        res, _ = self.push(payload, True)  # the retry of the row just pushed finds it
        self.assertEqual(res, [length + 1, 1])
        self.assertEqual(self.r.llen(KEYS[0]), length + 1)

    def test_beyond_window_is_pushed_again(self):
        length = self.r.llen(KEYS[0])
        res, _ = self.push(self.r.lindex(KEYS[0], 2000), True)
        self.assertEqual(res[0], length + 1)

    def test_certain_push_never_scans(self):
        _, lranges = self.push(row(10**9 + 1), False)
        self.assertEqual(lranges, 0)

    def test_empty_list_return_shape(self):
        self.r.delete(*KEYS)
        self.r.set(KEYS[1], json.dumps({"version": 2, "length": 0, "valid": 0, "nonfast": 0, "tail": ""}))
        res, _ = self.push(row(1), True)
        self.assertEqual(res, [1, 1])
        self.assertEqual(self.r.hget(KEYS[4], "a"), "1")


if __name__ == "__main__":
    unittest.main()
