import flask_login, bcrypt

class User(flask_login.UserMixin) :

    def __init__(self, id, password) :
        self.__id               = id
        self.__password         = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    
    def get_id(self) :
        return self.__id

    def check_password(self, password) :
        return bcrypt.checkpw(password.encode("utf-8"), self.__password)