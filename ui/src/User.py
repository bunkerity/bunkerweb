import flask_login, bcrypt

class User(flask_login.UserMixin) :

    def __init__(self, id, password) :
        self.is_authenticated   = True
        self.is_active          = True
        self.is_anonymous       = False
        self.__id               = id
        self.__password         = bcrypt.hashpw(password, bcrypt.gensalt())
    
    def get_id(self) :
        return self.__id

    def check_password(self, password) :
        return bcrypt.checkpw(password, self.__password)