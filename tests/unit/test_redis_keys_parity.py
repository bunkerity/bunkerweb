import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src" / "common" / "utils"))

from redis_keys import ban_ip, ban_key, escape, facet_key, initialized_key, requests_key, unescape  # noqa: E402

CASES = [
    ("bans_ip_1.2.3.4", "bans_ip_{1.2.3.4}"),
    ("bans_service_app.example_ip_1.2.3.4", "bans_service_app.example_ip_{1.2.3.4}"),
    ("bans_ip_2001:db8::1", "bans_ip_{2001:db8::1}"),
    ("bans_service_s_ip_::ffff:1.2.3.4", "bans_service_s_ip_{::ffff:1.2.3.4}"),
    ("bans_service_my_ip_app_ip_1.2.3.4", "bans_service_my_ip_app_ip_{1.2.3.4}"),
    ("bans_service_{a}.example_ip_1.2.3.4", "bans_service_%7Ba%7D.example_ip_{1.2.3.4}"),
    ("bans_service_a%7Bb_ip_1.2.3.4", "bans_service_a%257Bb_ip_{1.2.3.4}"),
    ("bans_service_a%b_ip_1.2.3.4", "bans_service_a%25b_ip_{1.2.3.4}"),
]

LUA = """
package.path = "{repo}/src/bw/lua/?.lua;" .. package.path
package.loaded["bunkerweb.utils"] = {{ get_variable = function() return "" end }}
local rk = require "bunkerweb.rediskeys"
for i = 1, #arg do io.write(rk.ban(arg[i], true), "\\n") end
"""
ESCAPE_CASES = ("a%7Bb", "a{b", "a%b", "%25")


class Parity(unittest.TestCase):
    def test_python_expected(self):
        for local, cluster in CASES:
            self.assertEqual(ban_key(local, False), local)
            self.assertEqual(ban_key(local, True), cluster)

    def test_lua_matches_python(self):
        # `lua -e <chunk> -- <args>` treats the first positional after `--` as a script
        # filename to load, not as arg[1] for the -e chunk (verified: it tries to open
        # it and fails). Write the chunk to a real file so positional args land in `arg`.
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
            f.write(LUA.format(repo=REPO))
            script_path = f.name
        try:
            out = subprocess.check_output(["lua", script_path, *[c[0] for c in CASES]], text=True)
        finally:
            Path(script_path).unlink()
        self.assertEqual(out.splitlines(), [ban_key(c[0], True) for c in CASES])

    def test_lua_escape_matches_python(self):
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
            f.write(LUA.replace("rk.ban(arg[i], true)", "rk.escape(arg[i])").format(repo=REPO))
            script_path = f.name
        try:
            out = subprocess.check_output(["lua", script_path, *ESCAPE_CASES], text=True)
        finally:
            Path(script_path).unlink()
        self.assertEqual(out.splitlines(), [escape(raw) for raw in ESCAPE_CASES])

    def test_parsers_round_trip(self):
        for local, cluster in CASES:
            raw_ip = cluster.rsplit("_ip_", 1)[1]
            self.assertEqual(ban_ip(raw_ip), local.rsplit("_ip_", 1)[1])

    def test_cluster_config_error(self):
        from redis_keys import cluster_config_error

        self.assertIsNone(cluster_config_error("", "s:26379", "3"))
        self.assertIsNone(cluster_config_error("a:7000", "", "0"))
        self.assertIsNone(cluster_config_error("a:7000", [], 0))
        self.assertIn("REDIS_SENTINEL_HOSTS", cluster_config_error("a:7000", "s:26379", "0"))
        self.assertIsNone(cluster_config_error("a:7000", "", "00"))
        self.assertIn("REDIS_DATABASE", cluster_config_error("a:7000", "", "2"))
        self.assertIn("REDIS_DATABASE", cluster_config_error("a:7000", "", "x"))
        self.assertIsNone(cluster_config_error("  ", "s:26379", "3"))

    def test_reports(self):
        self.assertEqual(requests_key(False), "requests")
        self.assertEqual(requests_key(True), "{requests}")
        self.assertEqual(initialized_key(True), "{requests}:facets:initialized")
        self.assertEqual(facet_key(False, "ip"), "requests:facet:ip")
        self.assertEqual(escape("a{b}c"), "a%7Bb%7Dc")

    def test_escape_round_trip(self):
        for raw, encoded in (("a%7Bb", "a%257Bb"), ("a{b", "a%7Bb"), ("a%b", "a%25b"), ("%25", "%2525")):
            self.assertEqual(escape(raw), encoded)
            self.assertEqual(unescape(escape(raw)), raw)


if __name__ == "__main__":
    unittest.main()
