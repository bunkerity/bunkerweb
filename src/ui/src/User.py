#!/usr/bin/env python3

from typing import Optional

from bcrypt import checkpw, hashpw, gensalt
from flask_login import AnonymousUserMixin, UserMixin
from pyotp import random_base32
from pyotp.totp import TOTP


class User(UserMixin):
    def __init__(
        self,
        username: str,
        password: Optional[str] = None,
        *,
        is_two_factor_enabled: bool = False,
        password_hash: Optional[bytes] = None,
        secret_token: Optional[str] = None,
        method: str = "manual",
    ):
        self.id = username

        if not password:
            assert password_hash, "Either password or password_hash must be provided"

        self.__password = password_hash or hashpw(password.encode("utf-8"), gensalt(rounds=13))  # type: ignore
        self.is_two_factor_enabled = is_two_factor_enabled
        self.secret_token = secret_token
        self.method = method
        self.__totp = TOTP(secret_token) if secret_token else None

    @property
    def password_hash(self) -> bytes:
        """
        Get the password hash

        :return: The password hash
        """
        return self.__password

    def update_password(self, password: str):
        """
        Set the password by hashing it

        :param password: The password to be hashed
        """
        self.__password = hashpw(password.encode("utf-8"), gensalt(rounds=13))

    def check_password(self, password: str):
        """
        Check if the password is correct by hashing it and comparing it to the stored hash

        :param password: The password to be checked
        :return: The password is being checked against the password hash. If the password is correct,
        the user is returned.
        """
        return checkpw(password.encode("utf-8"), self.__password)

    def get_authentication_setup_uri(self) -> str:
        if not self.__totp:
            return ""
        return self.__totp.provisioning_uri(name=self.id, issuer_name="BunkerWeb UI")

    def refresh_totp(self):
        self.secret_token = random_base32()
        self.__totp = TOTP(self.secret_token)

    def check_otp(self, otp: str, *, secret: Optional[str] = None) -> bool:
        """
        Check if the otp is correct by comparing it to the stored secret token

        :param otp: The otp to be checked
        :return: The otp is being checked against the secret token. If the otp is correct,
        the user is returned.
        """
        if secret:
            return TOTP(secret).verify(otp, valid_window=3)
        if not self.__totp:
            return False
        return self.__totp.verify(otp, valid_window=3)

    def __repr__(self):
        return f"User({self.id!r}, {self.__password!r}, {self.is_two_factor_enabled!r}, {self.secret_token!r}, {self.method!r})"


class AnonymousUser(AnonymousUserMixin):
    def __init__(self):
        self.id = None
        self.is_two_factor_enabled = False
        self.secret_token = None
        self.method = "manual"

    @property
    def password_hash(self) -> None:
        """
        Get the password hash

        :return: The password hash
        """
        return None

    def update_password(self, password: str):
        """
        Set the password by hashing it

        :param password: The password to be hashed
        """
        self.__password = hashpw(password.encode("utf-8"), gensalt(rounds=13))

    def check_password(self, password: str):
        """
        Check if the password is correct by hashing it and comparing it to the stored hash

        :param password: The password to be checked
        :return: The password is being checked against the password hash. If the password is correct,
        the user is returned.
        """
        return False

    def get_authentication_setup_uri(self) -> str:
        return ""

    def refresh_totp(self):
        return

    def check_otp(self, otp: str, *, secret: Optional[str] = None) -> bool:
        """
        Check if the otp is correct by comparing it to the stored secret token

        :param otp: The otp to be checked
        :return: The otp is being checked against the secret token. If the otp is correct,
        the user is returned.
        """
        if secret:
            return TOTP(secret).verify(otp, valid_window=3)
        return False
