"""Running the scheduler as a script must dispatch main exactly once.

A bounded child replaces main before dispatch, keeping startup filesystem, signals and loops out of this wiring test.
"""

import json
import subprocess
import sys
import textwrap


def test_main_bootstrap_dispatches_once(sched_main):
    runner = textwrap.dedent("""
        import json
        import runpy
        import sys

        script, paths = sys.argv[1:]
        sys.path[:] = json.loads(paths)
        calls = []
        previous = sys.gettrace()

        def main_stub():
            calls.append("main")

        def intercept(frame, event, arg):
            if frame.f_code.co_filename == script and frame.f_code.co_name == "<module>" and "main" in frame.f_globals:
                frame.f_globals["main"] = main_stub
                sys.settrace(previous)
                return previous
            return intercept

        sys.settrace(intercept)
        try:
            runpy.run_path(script, run_name="__main__")
        finally:
            sys.settrace(previous)
        print(json.dumps(calls))
        """)
    result = subprocess.run(
        [sys.executable, "-I", "-c", runner, sched_main.__file__, json.dumps(sys.path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip()) == ["main"]
