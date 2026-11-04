"""A failed config generation is retried with backoff and never reported as applied.

src/scheduler/main.py runs the whole scheduler at import time, so the units under test are pulled
out of its AST and executed in a small namespace instead of importing the module. MAIN_PY points the
test at another copy of the file (the unfixed one, to watch it fail).
"""

import ast
import os
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAIN = Path(os.environ.get("MAIN_PY", REPO / "src" / "scheduler" / "main.py"))
SOURCE = MAIN.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def segment(node):
    return ast.get_source_segment(SOURCE, node)


def find(kind, predicate, what):
    matches = [n for n in ast.walk(TREE) if isinstance(n, kind) and predicate(n)]
    if not matches:
        raise AssertionError(f"{what} not found in {MAIN}")
    return min(matches, key=lambda n: n.end_lineno - n.lineno)


def run_state_update(namespace):
    """Execute the real block that counts a failed generation, or resets the count on a good one."""
    node = find(ast.If, lambda n: "generation_failures += 1" in "\n".join(segment(b) for b in n.body), "the generation failure bookkeeping")
    # cd6807b33 builds the message by prefixing the reload branch's failover_message, which is empty when nothing reloaded.
    namespace.setdefault("failover_message", "")
    exec(compile(ast.Module([node], []), "state", "exec"), namespace)
    return namespace


class GenerationBackoffTest(unittest.TestCase):
    def setUp(self):
        delays = find(ast.Assign, lambda n: getattr(n.targets[0], "id", "") == "GENERATION_RETRY_DELAYS", "GENERATION_RETRY_DELAYS")
        func = find(ast.FunctionDef, lambda n: n.name == "generation_retry_delay", "generation_retry_delay")
        self.ns = {}
        exec(segment(delays), self.ns)
        exec(segment(func), self.ns)

    def fail(self, state):
        state = {"generation_failed": True, "generation_failures": state["generation_failures"], "generation_retry_delay": self.ns["generation_retry_delay"]}
        return run_state_update(state)

    def test_schedule_is_30s_1m_2m_then_every_5m(self):
        self.assertEqual([self.ns["generation_retry_delay"](n) for n in range(1, 8)], [30, 60, 120, 300, 300, 300, 300])

    def test_each_failure_arms_the_next_delay_and_says_so(self):
        state = {"generation_failures": 0}
        for expected in (30, 60, 120, 300, 300):
            state = self.fail(state)
            self.assertEqual(state["retry_delay"], expected)
            self.assertIn(f"Retrying in {expected}s", state["failover_message"])

    def test_a_good_generation_resets_the_backoff(self):
        state = {"generation_failures": 0}
        for _ in range(4):
            state = self.fail(state)
        state = run_state_update({"generation_failed": False, "generation_failures": state["generation_failures"]})
        self.assertEqual(state["generation_failures"], 0)
        self.assertEqual(self.fail(state)["retry_delay"], 30)


class FailedGenerationIsNotAppliedTest(unittest.TestCase):
    def test_the_change_stays_pending_after_a_failed_generation(self):
        assign = find(
            ast.Assign,
            lambda n: getattr(n.targets[0], "id", "") == "CONFIG_NEED_GENERATION" and isinstance(n.value, (ast.Name, ast.BoolOp)),
            "the end-of-iteration CONFIG_NEED_GENERATION assignment",
        )
        namespace = {"pre_push_failed": False, "generation_failed": True}
        exec(segment(assign), namespace)
        self.assertTrue(namespace["CONFIG_NEED_GENERATION"], "the flag is cleared although the generator failed: the change is lost")

    def test_no_reload_and_no_success_after_a_failed_generation(self):
        guard = find(ast.If, lambda n: segment(n.test) == "generation_failed" and "success = False" in segment(n.body[-1]), "the generation_failed guard")
        # The cache push and the reload live in the branch that only runs when the guard did not fire.
        self.assertIsInstance(guard.orelse[0], ast.If)
        self.assertIn("/reload", segment(guard.orelse[0]))
        self.assertNotIn("/reload", "\n".join(segment(b) for b in guard.body))

    def test_a_failed_generation_skips_the_failover_and_success_branches(self):
        guard = find(
            ast.If,
            lambda n: segment(n.test) == "generation_failed" and "was not confirmed" in "\n".join(segment(b) for b in n.body),
            "the generation_failed branch of the failover logic",
        )
        self.assertIn("Successfully reloaded bunkerweb", segment(guard))
        self.assertNotIn("Successfully reloaded bunkerweb", "\n".join(segment(b) for b in guard.body))


def run_block(source_fragment, namespace):
    """Execute the real `if` whose body contains `source_fragment`."""
    node = find(ast.If, lambda n: source_fragment in "\n".join(segment(b) for b in n.body), source_fragment)
    exec(compile(ast.Module([node], []), "block", "exec"), namespace)
    return namespace


class OnceJobsRerunAfterLateGenerationTest(unittest.TestCase):
    def mark(self, generation_failed, pre_push_failed):
        ns = {"generation_failed": generation_failed, "pre_push_failed": pre_push_failed, "jobs_ran_stale": False}
        return run_block("jobs_ran_stale = True", ns)["jobs_ran_stale"]

    def rearm(self, jobs_ran_stale, generation_failed):
        ns = {
            "jobs_ran_stale": jobs_ran_stale,
            "generation_failed": generation_failed,
            "RUN_JOBS_ONCE": False,
            "CONFIG_NEED_GENERATION": False,
            "retry_delay": None,
        }
        return run_block("RUN_JOBS_ONCE = CONFIG_NEED_GENERATION = True", ns)

    def test_jobs_that_ran_while_the_generator_was_failing_are_marked_stale(self):
        self.assertTrue(self.mark(generation_failed=True, pre_push_failed=False))

    def test_jobs_deferred_or_run_against_a_good_generation_are_not_marked(self):
        self.assertFalse(self.mark(generation_failed=True, pre_push_failed=True), "deferred jobs have not run yet")
        self.assertFalse(self.mark(generation_failed=False, pre_push_failed=False), "ran against a successful generation")

    def test_a_late_successful_generation_rearms_the_once_jobs(self):
        ns = self.rearm(jobs_ran_stale=True, generation_failed=False)
        self.assertTrue(ns["RUN_JOBS_ONCE"])
        self.assertTrue(ns["CONFIG_NEED_GENERATION"])
        self.assertEqual(ns["retry_delay"], 1)
        self.assertFalse(ns["jobs_ran_stale"], "they must not rerun a second time")

    def test_nothing_is_rearmed_while_the_generator_still_fails_or_when_not_stale(self):
        for stale, failed in ((True, True), (False, False), (False, True)):
            ns = self.rearm(jobs_ran_stale=stale, generation_failed=failed)
            self.assertFalse(ns["RUN_JOBS_ONCE"], (stale, failed))
            self.assertIsNone(ns["retry_delay"], (stale, failed))


if __name__ == "__main__":
    unittest.main()
