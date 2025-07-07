from base64 import b64encode
from io import BytesIO
from json import loads as json_loads
from bcrypt import checkpw
from typing import List, Optional
from passlib.totp import TOTP, MalformedTokenError, TokenError, TotpMatch
from passlib.pwd import genword
from qrcode import make
from qrcode.image.pil import PilImage
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from app.models.models import UiUsers
from app.dependencies import DATA
from app.utils import LIB_DIR, stop

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for totp module")

# Load TOTP secrets from configuration file with validation
if not LIB_DIR.joinpath(".totp_secrets.json").is_file():
    logger.error("The .totp_secrets.json file is missing, exiting ...")
    stop(1)

try:
    TOTP_SECRETS = json_loads(LIB_DIR.joinpath(".totp_secrets.json").read_text(encoding="utf-8"))
    if DEBUG_MODE:
        logger.debug("Successfully loaded TOTP secrets from configuration file")
except Exception as e:
    logger.exception("Failed to load TOTP secrets configuration")
    stop(1)


class Totp:
    # Initialize a totp factory.
    # Secrets are used to encrypt the per-user totp_secret on disk with BunkerWeb UI as issuer.
    def __init__(self):
        if DEBUG_MODE:
            logger.debug("Totp.__init__() called - initializing TOTP factory")
        
        try:
            self._totp = TOTP.using(secrets=TOTP_SECRETS, issuer="BunkerWeb UI")
            if DEBUG_MODE:
                logger.debug("Successfully initialized TOTP factory with BunkerWeb UI issuer")
        except Exception as e:
            logger.exception("Failed to initialize TOTP factory")
            raise

    # Create new user-unique totp_secret.
    # Generates encrypted TOTP secret for secure storage and user authentication setup.
    def generate_totp_secret(self) -> str:
        if DEBUG_MODE:
            logger.debug("generate_totp_secret() called - creating new TOTP secret")
        
        try:
            secret = self._totp.new().to_json(encrypt=True)
            if DEBUG_MODE:
                logger.debug("Successfully generated new encrypted TOTP secret")
            return secret
        except Exception as e:
            logger.exception("Failed to generate TOTP secret")
            raise

    # Generate pretty key for manual input
    # Formats TOTP secret into user-friendly format for manual entry into authenticator apps.
    def get_totp_pretty_key(self, totp_secret: str) -> str:
        if DEBUG_MODE:
            logger.debug(f"get_totp_pretty_key() called with secret length: {len(totp_secret) if totp_secret else 0}")
        
        if not totp_secret:
            if DEBUG_MODE:
                logger.debug("Empty TOTP secret provided, returning empty string")
            return ""
        
        try:
            pretty_key = self._totp.from_source(totp_secret).pretty_key(sep=False)
            if DEBUG_MODE:
                logger.debug(f"Successfully generated pretty key with length: {len(pretty_key)}")
            return pretty_key
        except Exception as e:
            logger.exception("Failed to generate pretty TOTP key")
            return ""

    # Generate recovery codes for TOTP backup authentication.
    # Creates 6 hex-based recovery codes with dash separation for improved readability.
    def generate_recovery_codes(self) -> List[str]:
        if DEBUG_MODE:
            logger.debug("generate_recovery_codes() called - creating 6 recovery codes")
        
        try:
            codes = ["-".join([pwd[i : i + 4] for i in range(0, len(pwd), 4)]) for pwd in genword(length=16, charset="hex", returns=6)]  # noqa: E203
            if DEBUG_MODE:
                logger.debug(f"Successfully generated {len(codes)} recovery codes")
            return codes
        except Exception as e:
            logger.exception("Failed to generate recovery codes")
            return []

    # Check if recovery code is valid for user.
    # Verifies and removes used recovery code to prevent reuse, returns the matched code hash.
    def verify_recovery_code(self, code: str, user: UiUsers) -> Optional[str]:
        if DEBUG_MODE:
            logger.debug(f"verify_recovery_code() called for user: {user.username if user else 'None'}")
        
        if not user or not user.list_recovery_codes:
            if DEBUG_MODE:
                logger.debug("No user or recovery codes available for verification")
            return None

        if DEBUG_MODE:
            logger.debug(f"Checking recovery code against {len(user.list_recovery_codes)} stored codes")

        try:
            for i, encrypted_code in enumerate(user.list_recovery_codes):
                if checkpw(code.encode("utf-8"), encrypted_code.encode("utf-8")):
                    matched_code = user.list_recovery_codes.pop(i)
                    if DEBUG_MODE:
                        logger.debug(f"Recovery code verified and removed for user: {user.username}")
                    return matched_code
            
            if DEBUG_MODE:
                logger.debug(f"Recovery code verification failed for user: {user.username}")
            return None
        except Exception as e:
            logger.exception(f"Error during recovery code verification for user: {user.username if user else 'None'}")
            return None

    # Verifies token for specific user.
    # Validates TOTP token with time window and counter tracking to prevent replay attacks.
    def verify_totp(self, token: str, *, totp_secret: Optional[str] = None, user: Optional[UiUsers] = None) -> bool:
        if DEBUG_MODE:
            logger.debug(f"verify_totp() called with token length: {len(token)}, user: {user.username if user else 'None'}")
        
        if not totp_secret and not user:
            logger.error("Either totp_secret or user must be provided for TOTP verification")
            raise ValueError("Either totp_secret or user must be provided")
        elif not totp_secret:
            totp_secret = user.totp_secret

        if DEBUG_MODE:
            logger.debug(f"Using TOTP secret for verification, has user: {user is not None}")

        try:
            last_counter = self.get_last_counter(user) if user else None
            tmatch = self._totp.verify(token, totp_secret, window=3, last_counter=last_counter)
            
            if user:
                self.set_last_counter(user, tmatch)
                if DEBUG_MODE:
                    logger.debug(f"TOTP verification successful for user: {user.username}, counter updated")
            else:
                if DEBUG_MODE:
                    logger.debug("TOTP verification successful (no user provided)")
            
            return True
        except (MalformedTokenError, TokenError) as e:
            if DEBUG_MODE:
                logger.debug(f"TOTP verification failed: {type(e).__name__}")
            return False
        except Exception as e:
            logger.exception("Unexpected error during TOTP verification")
            return False

    # Generate provisioning url for use with the qrcode scanner built into the app
    # Creates standard TOTP URI format for authenticator app registration with username and issuer.
    def get_totp_uri(self, username: str, totp_secret: str) -> str:
        if DEBUG_MODE:
            logger.debug(f"get_totp_uri() called for username: {username}")
        
        try:
            uri = self._totp.from_source(totp_secret).to_uri(username, "BunkerWeb UI")
            if DEBUG_MODE:
                logger.debug(f"Successfully generated TOTP URI for user: {username}")
            return uri
        except Exception as e:
            logger.exception(f"Failed to generate TOTP URI for user: {username}")
            return ""

    # Generate QRcode Using username, totp, generate the actual QRcode image.
    # Creates base64-encoded JPEG QR code image for easy display in web interface.
    def generate_qrcode(self, username: str, totp: str) -> str:
        if DEBUG_MODE:
            logger.debug(f"generate_qrcode() called for username: {username}")
        
        try:
            totp_uri = self.get_totp_uri(username, totp)
            totp_image = make(totp_uri, image_factory=PilImage)
            
            with BytesIO() as virtual_file:
                totp_image.save(virtual_file, format="JPEG")
                image_as_str = b64encode(virtual_file.getvalue()).decode("ascii")

            qr_data = f"data:image/jpeg;base64,{image_as_str}"
            if DEBUG_MODE:
                logger.debug(f"Successfully generated QR code for user: {username}, data length: {len(qr_data)}")
            
            return qr_data
        except Exception as e:
            logger.exception(f"Failed to generate QR code for user: {username}")
            return ""

    # Fetch stored last_counter from cache.
    # Retrieves anti-replay counter for TOTP verification to prevent token reuse attacks.
    def get_last_counter(self, user: UiUsers) -> Optional[int]:
        if DEBUG_MODE:
            logger.debug(f"get_last_counter() called for user: {user.username if user else 'None'}")
        
        if not user:
            if DEBUG_MODE:
                logger.debug("No user provided for counter retrieval")
            return None
        
        try:
            DATA.load_from_file()
            counter = DATA.get("totp_last_counter", {}).get(user.get_id())
            if DEBUG_MODE:
                logger.debug(f"Retrieved last counter for user {user.username}: {counter}")
            return counter
        except Exception as e:
            logger.exception(f"Failed to get last counter for user: {user.username}")
            return None

    # Cache last_counter.
    # Stores TOTP counter value to prevent replay attacks and ensure token uniqueness.
    def set_last_counter(self, user: UiUsers, tmatch: TotpMatch) -> None:
        if DEBUG_MODE:
            logger.debug(f"set_last_counter() called for user: {user.username if user else 'None'}, counter: {tmatch.counter if tmatch else 'None'}")
        
        if not user or not tmatch:
            if DEBUG_MODE:
                logger.debug("Missing user or tmatch for counter storage")
            return
        
        try:
            DATA.load_from_file()
            if "totp_last_counter" not in DATA:
                DATA["totp_last_counter"] = {}
                if DEBUG_MODE:
                    logger.debug("Created totp_last_counter section in DATA")
            
            DATA["totp_last_counter"][user.get_id()] = tmatch.counter
            if DEBUG_MODE:
                logger.debug(f"Successfully stored counter {tmatch.counter} for user: {user.username}")
        except Exception as e:
            logger.exception(f"Failed to set last counter for user: {user.username}")


totp = Totp()

__all__ = ("totp",)
