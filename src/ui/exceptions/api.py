# -*- coding: utf-8 -*-

from werkzeug.exceptions import HTTPException
from hook import hooks
from utils import format_exception


# When request to CORE succeed but error proceeding data
class ProceedCoreException(HTTPException):
    code = 500
    description = "Error while proceeding CORE response"


@hooks(hooks=["APIException"])
@format_exception()
def proceed_core_exception(e):
    return e


# Error while sending request to CORE
class CoreReqException(HTTPException):
    code = 500
    description = "Error while sending request to CORE"


@hooks(hooks=["APIException"])
@format_exception()
def core_req_exception(e):
    return e


# Export on main app to register
def setup_api_exceptions(app):
    app.register_error_handler(ProceedCoreException, proceed_core_exception)
    app.register_error_handler(CoreReqException, core_req_exception)
