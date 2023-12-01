#!/usr/bin/python3

from typing import Optional
from flask_login import UserMixin
from bcrypt import checkpw, hashpw, gensalt


class User(UserMixin):
    def __init__(self, username: str, password: Optional[str] = None, password_hash: Optional[bytes] = None):
        self.id = username

        if not password:
            assert password_hash, "Either password or password_hash must be provided"

        self.__password = password_hash or hashpw(password.encode("utf-8"), gensalt())  # type: ignore

    @property
    def password_hash(self) -> bytes:
        """
        Get the password hash

        :return: The password hash
        """
        return self.__password

    def check_password(self, password: str):
        """
        Check if the password is correct by hashing it and comparing it to the stored hash

        :param password: The password to be checked
        :return: The password is being checked against the password hash. If the password is correct,
        the user is returned.
        """
        return checkpw(password.encode("utf-8"), self.__password)
