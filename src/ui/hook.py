# -*- coding: utf-8 -*-
from functools import wraps

from os.path import join, sep

import os
import operator

from importlib import import_module
from pathlib import Path

# HOOKS
login_hooks = ["BeforeLogin", "AfterLogin", "BeforeLogout", "AfterLogout", "LoginException", "LogoutException"]
jwt_token_hooks = ["BeforeRefreshToken", "AfterRefreshToken", "TokenException"]
validator_hooks = ["BeforeValidator", "AfterValidator", "ValidatorException"]
api_hooks = ["BeforeReqAPI", "AfterReqAPI", "BeforeCoreReq", "AfterCoreReq", "BeforeProceedCore", "AfterProceedCore"]
pages_hooks = ["BeforeAccessPage", "AfterAccessPage", "AccessPageException"]
db_hooks = ["BeforeAccessDB", "AfterAccessDB", "DBException"]
global_hooks = ["BeforeReq", "AfterReq", "GlobalException"]
total_hooks = login_hooks + jwt_token_hooks + validator_hooks + api_hooks + pages_hooks + db_hooks + global_hooks

# hooks params need to be a list
def hooks(hooks):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from exceptions.hook import HookNameException

            # Split hooks
            before_hooks = []
            after_hooks = []
            exception_hooks = []

            for hook in hooks:
                # Case hook name doesn't exist
                if hook not in total_hooks:
                    raise HookNameException(f"Hook name {hook} doesn't exist")

                # Else split
                before_hooks.append(hook) if "Before" in hook else False
                after_hooks.append(hook) if "After" in hook else False
                exception_hooks.append(hook) if "Exception" in hook else False

            # Before hooks
            run_hooks(before_hooks, args, kwargs)
            run_hooks(exception_hooks, args, kwargs)
         
            # Run main
            main_f = f(*args, **kwargs)

            # After hooks
            run_hooks(after_hooks, args, kwargs, main_f)

            return main_f

        return wrapped

    return decorator

def run_hooks(hooks, args, kwargs, main_f = {}):
    for hook in hooks:
        # Get files for current hook, run if at least one
        files = get_files(hook)

        if not files:
            return

        run_hook_files(files, hook, args, kwargs, main_f)


def get_files(hook_name):
    from exceptions.hook import HookFilesException

    # Need a hook folder
    if not Path(os.path.abspath(".") + join(sep, "hooks", hook_name)).is_dir():
        return

    try:
        # Get .py from hooks dir
        hooks_path = Path(os.path.abspath(".") + join(sep, "hooks", hook_name))

        files = [f for f in os.listdir(hooks_path) if f.endswith(".py")]

        # Order base on name format id_name_order.py
        for index, file in enumerate(files):
            files[index] = {"name": file, "order": file.split("_")[-1].split(".")[0]}

        files.sort(key=operator.itemgetter("order"))
    except:
        raise HookFilesException(f"Error while getting files for hook {hook_name}")

    return files


def run_hook_files(files, hook_name, args, kwargs, main_f_res = {}):
    from exceptions.hook import HookRunException

    # Run every files
    for file in files:
        import_name = f"hooks.{hook_name}.{file.get('name').replace('.py', '')}"
        try:
            # Get file as module and execute it
            hook_f = getattr(import_module(import_name), "main")
            hook_f(args, kwargs, main_f_res)
        except:
            raise HookRunException(f"Hook exception on file {file} with hook {hook_name}")

