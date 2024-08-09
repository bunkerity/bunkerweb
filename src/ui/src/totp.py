from base64 import b64encode
from io import BytesIO
from bcrypt import checkpw
from typing import Dict, List, Optional, Union
from flask import Flask
from passlib.totp import TOTP, MalformedTokenError, TokenError, TotpMatch
from passlib.pwd import genword
from qrcode import make
from qrcode.image.svg import SvgImage

from models import Users


class Totp:
    def __init__(self, app: Flask, secrets: Dict[Union[str, int], str]):
        """Initialize a totp factory.
        secrets are used to encrypt the per-user totp_secret on disk.
        recovery_codes_keys are used to encrypt the per-user recovery codes on disk.
        """
        # This should be a dict with at least one entry
        self.app = app
        self._totp = TOTP.using(secrets=secrets, issuer="BunkerWeb UI")

    def generate_totp_secret(self) -> str:
        """Create new user-unique totp_secret."""
        return self._totp.new().to_json(encrypt=True)

    def get_totp_pretty_key(self, totp_secret: str) -> str:
        """Generate pretty key for manual input"""
        if not totp_secret:
            return ""
        return self._totp.from_source(totp_secret).pretty_key()

    def generate_recovery_codes(self) -> List[str]:
        return ["-".join([pwd[i : i + 4] for i in range(0, len(pwd), 4)]) for pwd in genword(length=16, charset="hex", returns=5)]  # noqa: E203

    def verify_recovery_code(self, code: str, user: Users) -> Optional[str]:
        """Check if recovery code is valid for user."""
        if not user.list_recovery_codes:
            return

        for i, encrypted_code in enumerate(user.list_recovery_codes):
            if checkpw(code.encode("utf-8"), encrypted_code.encode("utf-8")):
                return user.list_recovery_codes.pop(i)

    def verify_totp(self, token: str, *, totp_secret: Optional[str] = None, user: Optional[Users] = None) -> bool:
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
        totp_image = make(self.get_totp_uri(username, totp), image_factory=SvgImage)
        with BytesIO() as virtual_file:
            totp_image.save(virtual_file)
            image_as_str = b64encode(virtual_file.getvalue()).decode("ascii")

        return f"data:image/svg+xml;base64,{image_as_str}"

    def get_last_counter(self, user: Users) -> Optional[int]:
        """Fetch stored last_counter from cache."""
        return self.app.data.get("totp_last_counter", {}).get(user.get_id())

    def set_last_counter(self, user: Users, tmatch: TotpMatch) -> None:
        """Cache last_counter."""
        if "totp_last_counter" not in self.app.data:
            self.app.data["totp_last_counter"] = {}
        self.app.data["totp_last_counter"][user.get_id()] = tmatch.counter
