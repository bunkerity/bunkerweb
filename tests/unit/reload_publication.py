"""Plain stub checks: generation backoff must fence publication and survive rejected or busy reloads."""

import ast
import logging
import sys
import unittest

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace


def stub(name, **values):
    module = ModuleType(name)
    module.__dict__.update(values)
    sys.modules[name] = module


stub("schedule", jobs=[], Job=object)
stub("cache_restore", cache_tree=lambda *args: None)
stub("common_utils", effective_cpu_count=lambda: 1, parse_duration=lambda value, unit: int(value))
stub("Database", Database=object, DEFAULT_POOL_MAX_OVERFLOW=10, DEFAULT_POOL_SIZE=5)
stub("logger", getLogger=logging.getLogger)


class ApiCaller:
    def __init__(self, apis):
        self.apis = apis


leaf = ast.parse(Path("src/common/utils/ApiCaller.py").read_text())
floor_values = {}
for node in leaf.body:
    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "MIN_RELOAD_TIMEOUT" for target in node.targets):
        exec(compile(ast.Module(body=[node], type_ignores=[]), "ApiCaller.py", "exec"), floor_values)
stub("ApiCaller", ApiCaller=ApiCaller, MIN_RELOAD_TIMEOUT=floor_values.get("MIN_RELOAD_TIMEOUT", 15), folder_push_timeout=lambda minimum, count: (5, minimum))
spec = spec_from_file_location("JobScheduler", "src/scheduler/JobScheduler.py")
module = module_from_spec(spec)
spec.loader.exec_module(module)
JobScheduler = module.JobScheduler


class PublicationChecks(unittest.TestCase):
    def test_other_reload_callers_allow_readiness_confirmation(self):
        calls = []

        def send(method, url, timeout=(5, 10)):
            self.assertEqual(method, "POST")
            self.assertTrue(url.startswith("/reload?test="))
            calls.append(timeout)
            return True, {}

        caller = SimpleNamespace(send_to_apis=send)
        shared = {
            "MIN_RELOAD_TIMEOUT": sys.modules["ApiCaller"].MIN_RELOAD_TIMEOUT,
            "getenv": lambda key, default=None: default,
            "JSONResponse": lambda **kwargs: SimpleNamespace(**kwargs),
            "Depends": lambda dep: None,
            "get_instances_api_caller": lambda: None,
            "get_api_for_hostname": lambda: None,
            "ApiCaller": lambda apis: caller,
        }
        router = ast.parse(Path("src/api/app/routers/instances.py").read_text())
        for name in ("reload_config", "reload_one"):
            with self.subTest(caller=name):
                function = next(node for node in router.body if isinstance(node, ast.FunctionDef) and node.name == name)
                function.decorator_list = []
                exec(compile(ast.Module(body=[function], type_ignores=[]), "instances.py", "exec"), shared)
                if name == "reload_config":
                    result = shared[name](api_caller=caller)
                else:
                    result = shared[name]("node", api=object())
                self.assertEqual(result.status_code, 200)
                self.assertGreaterEqual(calls[-1][1] if isinstance(calls[-1], tuple) else calls[-1], 15)

        with self.subTest(caller="ui"):
            tree = ast.parse(Path("src/ui/app/models/instance.py").read_text())
            instance_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Instance")
            function = next(node for node in instance_class.body if isinstance(node, ast.FunctionDef) and node.name == "reload")
            exec(compile(ast.Module(body=[function], type_ignores=[]), "instance.py", "exec"), shared)
            self.assertIn("has been reloaded", shared["reload"](SimpleNamespace(apiCaller=caller, hostname="node")))
            self.assertGreaterEqual(calls[-1][1] if isinstance(calls[-1], tuple) else calls[-1], 15)

    def test_certificate_reload_budget_preserves_larger_values(self):
        tree = ast.parse(Path("src/common/core/letsencrypt/jobs/certbot-deploy.py").read_text())
        loop = next(node for node in ast.walk(tree) if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "instance")
        code = compile(ast.Module(body=[loop], type_ignores=[]), "certbot-deploy.py", "exec")
        for minimum, count, expected in ((5, 1, 15), (40, 1, 40), (5, 7, 21)):
            with self.subTest(minimum=minimum, services=count):
                calls = []
                caller = SimpleNamespace(send_to_apis=lambda *args, **kwargs: calls.append(kwargs["timeout"]) or (True, {}))
                api = SimpleNamespace(endpoint="http://node/", request=lambda *args, **kwargs: (True, None, 200, {}))
                context = {
                    "MIN_RELOAD_TIMEOUT": sys.modules["ApiCaller"].MIN_RELOAD_TIMEOUT,
                    "instances": [{}],
                    "services": ["service"] * count,
                    "reload_min_timeout": minimum,
                    "API": SimpleNamespace(from_instance=lambda instance: api),
                    "ApiCaller": lambda apis: caller,
                    "files": {},
                    "LOGGER": logging.getLogger("check"),
                    "getenv": lambda key, default=None: default,
                }
                exec(code, context)
                self.assertEqual(calls, [expected])

    def test_main_pre_push_and_healthcheck_use_floored_budget(self):
        tree = ast.parse(Path("src/scheduler/main.py").read_text())
        context = {
            "MIN_RELOAD_TIMEOUT": sys.modules["ApiCaller"].MIN_RELOAD_TIMEOUT,
            "parse_duration": lambda value, unit: int(value),
            "getenv": lambda key, default=None: default,
            "LOGGER": logging.getLogger("check"),
            "env": {},
        }
        setup = [
            node
            for node in tree.body
            if (
                isinstance(node, ast.Try)
                and any(
                    isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "RELOAD_MIN_TIMEOUT" for target in item.targets)
                    for item in node.body
                )
            )
            or (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "RELOAD_MIN_TIMEOUT" for target in node.targets))
        ]
        exec(compile(ast.Module(body=setup, type_ignores=[]), "main.py", "exec"), context)
        for name in ("pre_push_configuration", "healthcheck_job"):
            with self.subTest(caller=name):
                function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
                call = next(
                    node
                    for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "send_to_apis"
                    and len(node.args) > 1
                    and isinstance(node.args[1], ast.JoinedStr)
                    and any(isinstance(value, ast.Constant) and str(value.value).startswith("/reload?") for value in node.args[1].values)
                )
                budget = next(keyword.value for keyword in call.keywords if keyword.arg == "timeout")
                self.assertGreaterEqual(eval(compile(ast.Expression(body=budget), "main.py", "eval"), context), 15)

    def scheduler(self):
        scheduler = JobScheduler(logger=logging.getLogger("check"), db=object())
        self.addCleanup(scheduler._JobScheduler__executor.shutdown)
        scheduler.apis = [object()]
        scheduler._JobScheduler__job_reload = True
        self.effects = []
        scheduler.send_files = lambda *args, **kwargs: self.effects.append(("push", args, kwargs)) or True
        scheduler.send_to_apis = lambda *args, **kwargs: self.effects.append(("reload", args, kwargs)) or (True, {})
        return scheduler

    def test_generation_pending_holds_cache_and_render_publication(self):
        for regenerate in (False, True):
            with self.subTest(regenerate=regenerate):
                scheduler = self.scheduler()
                scheduler.generation_pending = True
                scheduler._JobScheduler__job_regenerate = regenerate
                scheduler._JobScheduler__generate_configs = lambda: self.effects.append(("render",)) or True
                self.assertFalse(scheduler._JobScheduler__publish_pending())
                self.assertEqual(self.effects, [])
                self.assertEqual(scheduler.consume_pending_publication(), (True, regenerate))

    def test_publication_resumes_after_generation_succeeds(self):
        scheduler = self.scheduler()
        scheduler.generation_pending = False
        self.assertTrue(scheduler._JobScheduler__publish_pending())
        self.assertEqual([effect[0] for effect in self.effects], ["push", "reload"])
        self.assertGreater(self.effects[-1][2]["timeout"], 10)

    def test_periodic_jobs_run_but_publication_stays_pending(self):
        scheduler = self.scheduler()
        scheduler.generation_pending = True
        scheduler.try_database_readonly = lambda: False
        scheduler._JobScheduler__update_cache_permissions = lambda: None
        original_jobs = sys.modules["schedule"].jobs
        self.addCleanup(setattr, sys.modules["schedule"], "jobs", original_jobs)
        sys.modules["schedule"].jobs = [SimpleNamespace(should_run=True, run=lambda: self.effects.append(("job",)))]
        self.assertFalse(scheduler.run_pending())
        self.assertEqual([effect[0] for effect in self.effects], ["job"])
        self.assertEqual(scheduler.consume_pending_publication(), (True, False))

    def test_reload_outcomes_keep_expected_generation_state(self):
        tree = ast.parse(Path("src/scheduler/main.py").read_text())
        outer_loop = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.While)
            and any(
                isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "generation_failed" for target in item.targets)
                for item in node.body
            )
        )
        apply_try = next(
            node
            for node in outer_loop.body
            if isinstance(node, ast.Try)
            and isinstance(node.body[0], ast.Assign)
            and isinstance(node.body[0].targets[0], ast.Name)
            and node.body[0].targets[0].id == "success"
        )
        retry_blocks = [
            node
            for node in outer_loop.body
            if isinstance(node, ast.If)
            and any(isinstance(item, ast.AugAssign) and isinstance(item.target, ast.Name) and item.target.id == "generation_failures" for item in node.body)
        ]
        pending_assignment = next(
            node
            for node in outer_loop.body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "CONFIG_NEED_GENERATION" for target in node.targets)
        )
        failover_try = next(
            node
            for node in outer_loop.body
            if isinstance(node, ast.Try) and any(isinstance(item, ast.Constant) and item.value == "Successfully reloaded bunkerweb" for item in ast.walk(node))
        )
        retry_schedule = next(
            node
            for node in outer_loop.body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "pending_retry_at" for target in node.targets)
        )
        retry_function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "generation_retry_delay")
        code = compile(
            ast.Module(
                body=sorted([retry_function, apply_try, *retry_blocks, failover_try, pending_assignment, retry_schedule], key=lambda node: node.lineno),
                type_ignores=[],
            ),
            "src/scheduler/main.py",
            "exec",
        )
        for outcome, partial_success in (
            ("rejected", False),
            ("rejected", True),
            ("unconfirmed", False),
            ("unconfirmed", True),
            ("confirmed", False),
            ("legacy", False),
            ("a reload is in progress (/var/tmp/bunkerweb/reloading exists). If none is running, restart BunkerWeb", False),
            ("a reload is in progress (/var/tmp/bunkerweb/reloading exists). If none is running, restart BunkerWeb", True),
            ("a push swap is in progress", False),
            ("a push swap is in progress", True),
            ("a configuration generation is in progress", False),
            ("a configuration generation is in progress", True),
        ):
            with self.subTest(outcome=outcome, partial_success=partial_success):
                busy = outcome.startswith("a ")
                rejected = outcome == "rejected" or busy
                nodes = [{"hostname": "node", "port": 5000}]
                responses = {
                    "node": {"status": "error" if rejected else "success", "msg": "reload failed: initialization rejected" if rejected else "reload signalled"}
                }
                if busy:
                    responses["node"]["msg"] = outcome
                if not rejected and outcome != "legacy":
                    responses["node"]["confirmed"] = outcome == "confirmed"
                apis = [SimpleNamespace(endpoint="http://node:5000/")]
                if partial_success:
                    nodes.append({"hostname": "other", "port": 5000})
                    responses["other"] = {"status": "success", "msg": "reload successful"}
                    apis.append(SimpleNamespace(endpoint="http://other:5000/"))
                statuses = {}
                warnings = []
                successes = []
                scheduler = SimpleNamespace(
                    apis=apis,
                    send_to_apis=lambda *args, **kwargs: (not rejected, responses),
                    db=SimpleNamespace(get_instances=lambda: nodes, update_instance=lambda host, status: statuses.update({host: status})),
                )
                context = {
                    "generation_failed": False,
                    "generation_failures": 0 if rejected else 3,
                    "pre_push_failed": False,
                    "republish_after_jobs": True,
                    "retry_delay": None,
                    "monotonic": lambda: 1000,
                    "failover_message": "",
                    "GENERATION_RETRY_DELAYS": (30, 60, 120, 300),
                    "SCHEDULER": scheduler,
                    "task_futures": [],
                    "SCHEDULER_TASKS_EXECUTOR": SimpleNamespace(submit=lambda *args: SimpleNamespace(result=lambda: None)),
                    "send_file_to_bunkerweb": lambda *args: None,
                    "CACHE_PATH": Path("/unused"),
                    "DISABLE_CONFIGURATION_TESTING": False,
                    "RELOAD_MIN_TIMEOUT": 15,
                    "env": {},
                    "LOGGER": SimpleNamespace(debug=lambda *args: None, error=lambda *args: None, warning=warnings.append, info=successes.append),
                    "backup_failover": lambda: None,
                    "_instance_endpoint": lambda instance: "http://" + instance["hostname"] + ":5000",
                }
                exec(code, context)
                self.assertEqual(context["CONFIG_NEED_GENERATION"], rejected)
                self.assertEqual(context["success"], not rejected)
                self.assertEqual(context["generation_failures"], 1 if rejected else 0)
                self.assertEqual(context["retry_delay"], 30 if rejected else None)
                self.assertEqual(context["pending_retry_at"], 1030 if rejected else None)
                self.assertEqual(statuses["node"], "failover" if rejected and not busy else "up")
                self.assertEqual(successes, [] if rejected else ["Successfully reloaded bunkerweb"])
                if partial_success:
                    self.assertEqual(statuses["other"], "up")
                self.assertIn("http://node:5000/", [api.endpoint for api in scheduler.apis])
                if outcome == "unconfirmed":
                    self.assertEqual(len(warnings), 1)
                    self.assertIn("node", warnings[0])
                    self.assertIn("unconfirmed", warnings[0])
                else:
                    self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
