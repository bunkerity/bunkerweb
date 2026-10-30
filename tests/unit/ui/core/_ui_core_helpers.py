"""Plain helpers for the UI core tests (fixtures live in conftest.py; never import conftest)."""

import json

from redis_keys import facet_key, initialized_key, requests_key  # type: ignore


class FakeApiCaller:
    """Scripted ``ApiCaller``: ``replies`` maps ``(method, path-prefix)`` to the tuple ``send_to_apis`` returns."""

    def __init__(self, replies=None, default=(True, {})):
        self.replies = replies or {}
        self.default = default
        self.calls = []

    def send_to_apis(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        for (reply_method, prefix), reply in self.replies.items():
            if method == reply_method and url.startswith(prefix):
                if isinstance(reply, BaseException):
                    raise reply
                return reply
        if isinstance(self.default, BaseException):
            raise self.default
        return self.default


class FakeRedis:
    """In-memory slice of redis-py used by ``InstancesUtils``: lists, hashes, strings, SCAN, pipelines and scripted failures."""

    def __init__(self):
        self.lists, self.kv, self.hashes, self.key_types = {}, {}, {}, {}
        self.errors = {}  # method name -> exception raised by it
        self.calls = []
        self.evals = []

    def _hit(self, name):
        self.calls.append(name)
        if name in self.errors:
            raise self.errors[name]

    def llen(self, key):
        self._hit("llen")
        return len(self.lists.get(key, []))

    def lrange(self, key, start, end):
        self._hit("lrange")
        items = self.lists.get(key, [])
        return list(items[start : None if end == -1 else end + 1])  # noqa: E203

    def get(self, key):
        self._hit("get")
        return self.kv.get(key)

    def set(self, name, value, px=None, **kwargs):
        self._hit("set")
        self.kv[name] = value if isinstance(value, bytes) else str(value).encode()
        return True

    def hlen(self, key):
        self._hit("hlen")
        return len(self.hashes.get(key, {}))

    def hgetall(self, key):
        self._hit("hgetall")
        return dict(self.hashes.get(key, {}))

    def hscan(self, key, cursor=0, count=1000):
        self._hit("hscan")
        items = list(self.hashes.get(key, {}).items())
        page = items[cursor : cursor + 2]  # noqa: E203
        nxt = cursor + 2
        return (0 if nxt >= len(items) else nxt), dict(page)

    def eval(self, script, numkeys, *args):
        self._hit("eval")
        self.evals.append((script, numkeys, args))
        key, expected = args
        if self.kv.get(key) == expected:
            del self.kv[key]
            return 1
        return 0

    def scan_iter(self, match=None, count=None):
        self._hit("scan_iter")
        from fnmatch import fnmatchcase

        return iter([k for k in list(self.kv) + list(self.lists) if fnmatchcase(k, match)])

    def mget(self, keys):
        self._hit("mget")
        return [self.kv.get(k) for k in keys]

    mget_nonatomic = mget

    def type(self, key):
        self._hit("type")
        return self.key_types.get(key) or ("string" if key in self.kv else "list" if key in self.lists else "none")

    def pipeline(self, transaction=False):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis):
        self.redis, self.ops = redis, []

    def __getattr__(self, name):
        def queue(*args, **kwargs):
            self.ops.append((name, args, kwargs))

        return queue

    def execute(self):
        self.redis._hit("pipeline.execute")
        return [getattr(self.redis, name)(*args, **kwargs) for name, args, kwargs in self.ops]


FIELDS = ["ip", "country", "method", "url", "status", "reason", "server_name", "security_mode"]


def report(i, **extra):
    base = {
        "id": f"r{i}",
        "date": 1000 + i,
        "ip": f"10.0.0.{i % 3}",
        "country": "FR" if i % 2 else "US",
        "method": "GET",
        "url": f"/p{i}",
        "status": 403,
        "reason": "antibot",
        "server_name": "www.example.com",
        "security_mode": "block",
        "user_agent": "curl",
        "data": {"k": i},
    }
    base.update(extra)
    return base


def seed(redis, reports, *, certified=True, nonfast=0):
    redis.lists[requests_key(False)] = [json.dumps(r).encode() for r in reports]
    for field in FIELDS:
        counts = {}
        for r in reports:
            counts[str(r.get(field, "N/A"))] = counts.get(str(r.get(field, "N/A")), 0) + 1
        redis.hashes[facet_key(False, field)] = {k.encode(): str(v).encode() for k, v in counts.items()}
    if certified:
        redis.kv[initialized_key(False)] = json.dumps({"version": 2, "length": len(reports), "valid": len(reports), "nonfast": nonfast}).encode()
