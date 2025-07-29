from base64 import b64encode
from io import BytesIO
from json import loads as json_loads
from bcrypt import checkpw
from typing import List, Optional
from passlib.totp import TOTP, MalformedTokenError, TokenError, TotpMatch
from passlib.pwd import genword
from qrcode import make
from qrcode.image.pil import PilImage

from app.models.models import UiUsers
from app.dependencies import DATA
from app.utils import LIB_DIR, LOGGER, stop


# Try to load the new .totp_encryption_keys.json file first, fallback to .totp_secrets.json for backward compatibility
encryption_keys_path = LIB_DIR.joinpath(".totp_encryption_keys.json")
secrets_path = LIB_DIR.joinpath(".totp_secrets.json")

if encryption_keys_path.is_file():
    TOTP_ENCRYPTION_KEYS = json_loads(encryption_keys_path.read_text(encoding="utf-8"))
elif secrets_path.is_file():
    LOGGER.warning("The .totp_encryption_keys.json file is missing, using legacy .totp_secrets.json for backward compatibility.")
    TOTP_ENCRYPTION_KEYS = json_loads(secrets_path.read_text(encoding="utf-8"))
else:
    LOGGER.error("Neither .totp_encryption_keys.json nor .totp_secrets.json file found, exiting ...")
    stop(1)


class Totp:
    def __init__(self):
        """Initialize a totp factory.
        secrets are used to encrypt the per-user totp_secret on disk.
        recovery_codes_keys are used to encrypt the per-user recovery codes on disk.
        """
        self._totp = TOTP.using(secrets=TOTP_ENCRYPTION_KEYS, issuer="BunkerWeb UI")

    def generate_totp_secret(self) -> str:
        """Create new user-unique totp_secret."""
        return self._totp.new().to_json(encrypt=True)

    def get_totp_pretty_key(self, totp_secret: str) -> str:
        """Generate pretty key for manual input"""
        if not totp_secret:
            return ""
        return self._totp.from_source(totp_secret).pretty_key(sep=False)

    def generate_recovery_codes(self) -> List[str]:
        return ["-".join([pwd[i : i + 4] for i in range(0, len(pwd), 4)]) for pwd in genword(length=16, charset="hex", returns=6)]  # noqa: E203

    def verify_recovery_code(self, code: str, user: UiUsers) -> Optional[str]:
        """Check if recovery code is valid for user."""
        if not user.list_recovery_codes:
            return

        for i, encrypted_code in enumerate(user.list_recovery_codes):
            if checkpw(code.encode("utf-8"), encrypted_code.encode("utf-8")):
                return user.list_recovery_codes.pop(i)

    def verify_totp(self, token: str, *, totp_secret: Optional[str] = None, user: Optional[UiUsers] = None) -> bool:
        """Verifies token for specific user."""
        if not totp_secret and not user:
            raise ValueError("Either totp_secret or user must be provided")
        elif not totp_secret:
            totp_secret = user.totp_secret

        try:
            tmatch = self._totp.verify(token, totp_secret, window=3, last_counter=self.get_last_counter(user))
            if user:
                self.set_last_counter(user, tmatch)
            return True
        except (MalformedTokenError, TokenError):
            return False

    def get_totp_uri(self, username: str, totp_secret: str) -> str:
        """Generate provisioning url for use with the qrcode scanner built into the app"""
        return self._totp.from_source(totp_secret).to_uri(username, "BunkerWeb UI")

    def generate_qrcode(self, username: str, totp: str) -> str:
        """Generate QRcode Using username, totp, generate the actual QRcode image."""
        totp_image = make(self.get_totp_uri(username, totp), image_factory=PilImage)
        with BytesIO() as virtual_file:
            totp_image.save(virtual_file, format="JPEG")
            image_as_str = b64encode(virtual_file.getvalue()).decode("ascii")

        return f"data:image/jpeg;base64,{image_as_str}"

    def get_last_counter(self, user: UiUsers) -> Optional[int]:
        """Fetch stored last_counter from cache."""
        DATA.load_from_file()
        return DATA.get("totp_last_counter", {}).get(user.get_id())

    def set_last_counter(self, user: UiUsers, tmatch: TotpMatch) -> None:
        """Cache last_counter."""
        DATA.load_from_file()
        if "totp_last_counter" not in DATA:
            DATA["totp_last_counter"] = {}
        DATA["totp_last_counter"][user.get_id()] = tmatch.counter


totp = Totp()

__all__ = ("totp",)
