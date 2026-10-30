from datetime import datetime
from json import JSONDecodeError, dumps, loads

from cachelib.file import FileSystemCache

_DATETIME_MARKER = "__dt__"


class SafeFileSystemSerializer:
    """JSON-based serializer replacing the default unsafe one for security.

    Handles datetime objects transparently via a marker dict.
    Returns None on decode failure (legacy or corrupted data) to force re-login
    rather than executing untrusted payloads.
    """

    def dump(self, value, f, protocol=None):
        f.write(dumps(value, default=self._encode_default, ensure_ascii=False).encode("utf-8"))

    def load(self, f):
        data = f.read()
        try:
            return loads(data.decode("utf-8"), object_hook=self._decode_hook)
        except (JSONDecodeError, UnicodeDecodeError):
            return None

    @staticmethod
    def _encode_default(obj):
        if isinstance(obj, datetime):
            return {_DATETIME_MARKER: obj.isoformat()}
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    @staticmethod
    def _decode_hook(obj):
        if _DATETIME_MARKER in obj and len(obj) == 1:
            return datetime.fromisoformat(obj[_DATETIME_MARKER])
        return obj


class SafeFileSystemCache(FileSystemCache):
    """FileSystemCache subclass with JSON serialization instead of the unsafe default."""

    serializer = SafeFileSystemSerializer()
