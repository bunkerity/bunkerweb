#!/usr/bin/python3

from flask_login import UserMixin
from bcrypt import checkpw, hashpw, gensalt


class User(UserMixin):
    def __init__(self, id, password):
        self.__id = id
        self.__password = hashpw(password.encode("utf-8"), gensalt())

    def get_id(self):
        """
        Get the id of the user
        :return: The id of the user
        """
        return self.__id

    def check_password(self, password):
        """
        Check if the password is correct by hashing it and comparing it to the stored hash

        :param password: The password to be checked
        :return: The password is being checked against the password hash. If the password is correct,
        the user is returned.
        """
        return checkpw(password.encode("utf-8"), self.__password)
