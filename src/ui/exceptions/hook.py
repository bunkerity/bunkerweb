# -*- coding: utf-8 -*-
from werkzeug.exceptions import HTTPException
from utils import format_exception


# Hook name exception
class HookNameException(HTTPException):
    code = 400
    description = "Hook name doesn't exist"


@format_exception()
def hook_name_exception(e):
    return e


# Hook name get files exception
class HookFilesException(HTTPException):
    code = 500
    description = "Error while getting files from hook"


@format_exception()
def hook_files_exception(e):
    return e


# Executing hook files exception
class HookRunException(HTTPException):
    code = 500
    description = "Error while executing hook."


@format_exception()
def hook_run_exception(e):
    return e


# Export on main app to register
def setup_hook_exceptions(app):
    app.register_error_handler(HookNameException, hook_name_exception)
    app.register_error_handler(HookFilesException, hook_files_exception)
    app.register_error_handler(HookRunException, hook_run_exception)
