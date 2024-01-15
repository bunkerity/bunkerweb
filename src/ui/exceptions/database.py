# -*- coding: utf-8 -*-

from werkzeug.exceptions import HTTPException
from hook import hooks
from utils import log_exception
from utils import format_exception


# Error while trying to access UI DB
class AccessDBException(HTTPException):
    code = 500
    description = "Error while accessing database"


@hooks(hooks=["DBException"])
@log_exception(AccessDBException)
def access_db_exception(e):
    return format_exception(e)


# Get data from DB succeed but error while proceeding data retrieved
class ProceedDataDBException(HTTPException):
    code = 500
    description = "Error while proceeding DB data"


@hooks(hooks=["DBException"])
@log_exception(ProceedDataDBException)
def proceed_db_data_exception(e):
    return format_exception(e)


# Export on main app to register
def setup_db_exceptions(app):
    app.register_error_handler(AccessDBException, access_db_exception)
    app.register_error_handler(ProceedDataDBException, proceed_db_data_exception)
