"""Exercise UI stored-hash checks in an isolated app-package interpreter."""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("target", ["helper", "model", "recovery"])
def test_ui_malformed_stored_hash_is_refused(target, tmp_path):
    root = Path(__file__).resolve().parents[3]
    script = r"""
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

root, temporary, target = sys.argv[1:]
for path in ("src/ui", "src/common/db", "src/common/utils"):
    sys.path.insert(0, str(Path(root) / path))
import app.utils as utils
from app.models.models import UiUsers

logger = Mock()
utils.LOGGER = logger
if target == "helper":
    assert utils.check_password("private-password", b"private-invalid-hash") is False
elif target == "model":
    user = UiUsers(username="alice", password="private-invalid-hash")
    assert user.check_password("private-password") is False
else:
    # Only import-time integrations are stubbed; recovery checking uses real bcrypt.
    for name in ("passlib", "passlib.totp", "passlib.pwd", "qrcode", "qrcode.image", "qrcode.image.pil", "app.dependencies"):
        sys.modules[name] = ModuleType(name)
    sys.modules["passlib.totp"].TOTP = SimpleNamespace(using=lambda **kwargs: None)
    for name in ("MalformedTokenError", "TokenError", "TotpMatch"):
        setattr(sys.modules["passlib.totp"], name, type(name, (Exception,), {}))
    sys.modules["passlib.pwd"].genword = Mock()
    sys.modules["qrcode"].make = Mock()
    sys.modules["qrcode.image.pil"].PilImage = Mock()
    sys.modules["app.dependencies"].DB = Mock()
    utils.LIB_DIR = Path(temporary)
    (utils.LIB_DIR / ".totp_encryption_keys.json").write_text("{}")
    from app.models.totp import totp
    user = SimpleNamespace(list_recovery_codes=["private-invalid-hash"])
    assert totp.verify_recovery_code("private-password", user) is None
    assert user.list_recovery_codes == ["private-invalid-hash"]
logger.warning.assert_called_once()
assert "private" not in str(logger.warning.call_args)
"""
    result = subprocess.run([sys.executable, "-c", script, str(root), str(tmp_path), target], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
