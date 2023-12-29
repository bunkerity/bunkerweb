# -*- coding: utf-8 -*-
from functools import wraps
from flask import request
from flask import abort

from exceptions.hook import HookRunException, HookNameException, HookFilesException

from os.path import join, sep
from sys import path as sys_path

import os
import pathlib
from os.path import join, sep
from sys import path as sys_path

import operator

from importlib import import_module
from pathlib import Path

import itertools

login_hooks = ["BeforeLogin", "AfterLogin",  "BeforeLogout", "AfterLogout","LoginException"]
jwt_token_hooks = ["BeforeRefreshToken", "AfterRefreshToken", "TokenException"]
validator_hooks = ["BeforeValidator", "AfterValidator", "ValidatorException"]
api_hooks = ["BeforeReqAPI", "AfterReqAPI", "BeforeCoreReq", "AfterCoreReq", "BeforeProceedCore", "AfterProceedCore", "APIException"]
pages_hooks = ["BeforeAccessPage", "AfterAccessPage", "AccessPageException"]
db_hooks = ["BeforeAccessDB", "AfterAccessDB", "DBException"]
global_hooks = ["GlobalException"]
total_hooks = login_hooks + jwt_token_hooks + validator_hooks + api_hooks + pages_hooks + db_hooks + global_hooks

def hooks(hooks):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):

            # Split hooks
            before_hooks = []
            after_hooks = []
            exception_hooks = []

            for hook in hooks:
                # Case hook name doesn't exist
                if not hook in total_hooks:
                    raise HookNameException(f"Hook name {hook} doesn't exist")

                # Else split
                before_hooks.append(hook) if "Before" in hook else False
                after_hooks.append(hook) if "After" in hook else False
                exception_hooks.append(hook) if "Exception" in hook else False

            # Before hooks
            for hook in before_hooks:
                # Get files and prepare data
                files = get_files(hook)
                run_hook_files(files, hook)

            # Exception hooks
            for hook in exception_hooks:
                # Get files and prepare data
                files = get_files(hook)
                run_hook_files(files, hook)

            # Run main
            main_function = f(*args, **kwargs)

            # After hooks
            for hook in after_hooks:
                # Get files and prepare data
                files = get_files(hook)
                run_hook_files(files, hook)

            return main_function

        return wrapped

    return decorator


def get_files(hook_name):
    try :
        # Get .py from hooks dir
        hooks_path = Path(os.path.abspath('.') + join(sep, "hooks", hook_name))

        files = [f for f in os.listdir(hooks_path) if f.endswith('.py')]

        # Order base on name format id_name_order.py
        for index, file in enumerate(files):
            files[index] = {"name" : file, "order" : file.split('_')[-1].split('.')[0]}

        files.sort(key=operator.itemgetter('order'))
    except:
        raise HookFilesException(f"Error while getting files for hook {hook_name}")

    return files

def run_hook_files(files, hook_name):

    # Run every files
    for file in files:
        import_name = f"hooks.{hook_name}.{file.get('name').replace('.py', '')}"
        try:
            # Get file as module and execute it
            hook_f = getattr(import_module(import_name), 'main')
            hook_f()
        except: 
            raise HookRunException(f'Hook exception on file {file} with hook {hook_name}')

