# -*- coding: utf-8 -*-
from werkzeug.exceptions import HTTPException
from hook import hooks
from utils import format_exception


# Missing a data to execute validator
class ValidatorFormatException(HTTPException):
    code = 400
    description = "Bad format, missing parameters to execute validation"


@hooks(hooks=["ValidatorException"])
@format_exception()
def validator_format_exception(e):
    return e


# Body data doesn't match model
class ValidatorBodyException(HTTPException):
    code = 500
    description = "Request body doesn't match model"


@hooks(hooks=["ValidatorException"])
@format_exception()
def validator_body_exception(e):
    return e


# queries doesn't match model
class ValidatorQueryException(HTTPException):
    code = 500
    description = "Request queries don't match model"


@hooks(hooks=["ValidatorException"])
@format_exception()
def validator_query_exception(e):
    return e


# Export on main app to register
def setup_validator_exceptions(app):
    app.register_error_handler(ValidatorFormatException, validator_format_exception)
    app.register_error_handler(ValidatorBodyException, validator_body_exception)
    app.register_error_handler(ValidatorQueryException, validator_query_exception)
