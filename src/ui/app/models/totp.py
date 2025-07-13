from base64 import b64encode
from io import BytesIO
from json import loads as json_loads
from os import sep
from os.path import join
from sys import path as sys_path
from bcrypt import checkpw
from typing import List, Optional
from passlib.totp import TOTP, MalformedTokenError, TokenError, TotpMatch
from passlib.pwd import genword
from qrcode import make
from qrcode.image.pil import PilImage

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-totp",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-totp")

from app.models.models import UiUsers
from app.dependencies import DATA
from app.utils import LIB_DIR, stop


if not LIB_DIR.joinpath(".totp_secrets.json").is_file():
    logger.error("The .totp_secrets.json file is missing, exiting ...")
    stop(1)
TOTP_SECRETS = json_loads(LIB_DIR.joinpath(".totp_secrets.json").read_text(encoding="utf-8"))


class Totp:
    # Initialize TOTP factory with encryption secrets and issuer configuration.
    # Sets up secure TOTP generation using secrets for per-user encryption.
    def __init__(self):
        logger.debug("Totp.__init__() called")
        self._totp = TOTP.using(secrets=TOTP_SECRETS, issuer="BunkerWeb UI")

    # Create new user-unique TOTP secret with encryption.
    # Returns encrypted JSON string for secure storage in database.
    def generate_totp_secret(self) -> str:
        logger.debug("generate_totp_secret() called")
        try:
            secret = self._totp.new().to_json(encrypt=True)
            logger.debug("TOTP secret generated successfully")
            return secret
        except Exception as e:
            logger.exception("Exception while generating TOTP secret")
            raise

    # Generate human-readable TOTP key for manual input into authenticator apps.
    # Returns formatted key without separators for easy typing.
    def get_totp_pretty_key(self, totp_secret: str) -> str:
        logger.debug("get_totp_pretty_key() called")
        if not totp_secret:
            logger.debug("Empty TOTP secret provided")
            return ""
        try:
            pretty_key = self._totp.from_source(totp_secret).pretty_key(sep=False)
            logger.debug("Pretty key generated successfully")
            return pretty_key
        except Exception as e:
            logger.exception("Exception while generating pretty key")
            return ""

    # Generate list of backup recovery codes for account recovery.
    # Creates 6 hexadecimal codes formatted with dashes for readability.
    def generate_recovery_codes(self) -> List[str]:
        logger.debug("generate_recovery_codes() called")
        try:
            codes = ["-".join([pwd[i : i + 4] for i in range(0, len(pwd), 4)]) for pwd in genword(length=16, charset="hex", returns=6)]  # noqa: E203
            logger.debug(f"Generated {len(codes)} recovery codes")
            return codes
        except Exception as e:
            logger.exception("Exception while generating recovery codes")
            return []

    # Verify and consume a recovery code for user authentication.
    # Returns the matched code if valid or None if invalid/not found.
    def verify_recovery_code(self, code: str, user: UiUsers) -> Optional[str]:
        logger.debug(f"verify_recovery_code() called for user {user.username if user else 'None'}")
        if not user.list_recovery_codes:
            logger.debug("No recovery codes available for user")
            return

        try:
            for i, encrypted_code in enumerate(user.list_recovery_codes):
                if checkpw(code.encode("utf-8"), encrypted_code.encode("utf-8")):
                    logger.debug(f"Recovery code verified successfully for user {user.username}")
                    return user.list_recovery_codes.pop(i)
            logger.debug("Recovery code verification failed")
        except Exception as e:
            logger.exception("Exception while verifying recovery code")
        return None

    # Verify TOTP token against user's secret with time window tolerance.
    # Prevents replay attacks using last counter and supports 3-step window.
    def verify_totp(self, token: str, *, totp_secret: Optional[str] = None, user: Optional[UiUsers] = None) -> bool:
        logger.debug(f"verify_totp() called with token length={len(token) if token else 0}")
        if not totp_secret and not user:
            logger.debug("Neither totp_secret nor user provided")
            raise ValueError("Either totp_secret or user must be provided")
        elif not totp_secret:
            totp_secret = user.totp_secret

        try:
            tmatch = self._totp.verify(token, totp_secret, window=3, last_counter=self.get_last_counter(user))
            if user:
                self.set_last_counter(user, tmatch)
            logger.debug("TOTP verification successful")
            return True
        except (MalformedTokenError, TokenError) as e:
            logger.debug(f"TOTP verification failed: {type(e).__name__}")
            return False
        except Exception as e:
            logger.exception("Exception during TOTP verification")
            return False

    # Generate provisioning URI for QR code scanner integration.
    # Creates standard TOTP URI format compatible with authenticator apps.
    def get_totp_uri(self, username: str, totp_secret: str) -> str:
        logger.debug(f"get_totp_uri() called for username={username}")
        try:
            uri = self._totp.from_source(totp_secret).to_uri(username, "BunkerWeb UI")
            logger.debug("TOTP URI generated successfully")
            return uri
        except Exception as e:
            logger.exception("Exception while generating TOTP URI")
            return ""

    # Generate base64-encoded QR code image for TOTP setup.
    # Creates JPEG image data URI for display in web browsers.
    def generate_qrcode(self, username: str, totp: str) -> str:
        logger.debug(f"generate_qrcode() called for username={username}")
        try:
            totp_image = make(self.get_totp_uri(username, totp), image_factory=PilImage)
            with BytesIO() as virtual_file:
                totp_image.save(virtual_file, format="JPEG")
                image_as_str = b64encode(virtual_file.getvalue()).decode("ascii")

            logger.debug("QR code generated successfully")
            return f"data:image/jpeg;base64,{image_as_str}"
        except Exception as e:
            logger.exception("Exception while generating QR code")
            return ""

    # Fetch stored last counter value from persistent cache.
    # Prevents TOTP replay attacks by tracking previously used tokens.
    def get_last_counter(self, user: UiUsers) -> Optional[int]:
        if not user:
            return None
        logger.debug(f"get_last_counter() called for user {user.username}")
        try:
            DATA.load_from_file()
            counter = DATA.get("totp_last_counter", {}).get(user.get_id())
            logger.debug(f"Retrieved last counter: {counter}")
            return counter
        except Exception as e:
            logger.exception("Exception while getting last counter")
            return None

    # Store last counter value to persistent cache for replay prevention.
    # Updates counter after successful TOTP verification.
    def set_last_counter(self, user: UiUsers, tmatch: TotpMatch) -> None:
        logger.debug(f"set_last_counter() called for user {user.username}")
        try:
            DATA.load_from_file()
            if "totp_last_counter" not in DATA:
                DATA["totp_last_counter"] = {}
            DATA["totp_last_counter"][user.get_id()] = tmatch.counter
            logger.debug(f"Set last counter to {tmatch.counter}")
        except Exception as e:
            logger.exception("Exception while setting last counter")


totp = Totp()

__all__ = ("totp",)
