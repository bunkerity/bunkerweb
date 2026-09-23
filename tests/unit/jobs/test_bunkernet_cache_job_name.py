"""BunkerNet jobs read the instance ID from the job that registers it."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JOB_FILES = (
    ROOT / "src" / "common" / "core" / "bunkernet" / "jobs" / "bunkernet-data.py",
    ROOT / "src" / "common" / "core" / "bunkernet" / "jobs" / "bunkernet-send.py",
)


def test_data_and_send_jobs_look_up_the_register_job_cache():
    class FakeDatabase:
        def __init__(self):
            self.rows = {("bunkernet-register", "instance.id"): b"registered-instance"}
            self.lookups = []

        def get_job_cache_file(self, job_name, file_name):
            self.lookups.append((job_name, file_name))
            return self.rows.get((job_name, file_name))

    class FakeJob:
        def __init__(self, job_name, db):
            self.job_name = job_name
            self.db = db

        def get_cache(self, name, *, job_name=""):
            return self.db.get_job_cache_file(job_name or self.job_name, name)

    cache_values = []
    cache_lookups = []
    for job_file in JOB_FILES:
        tree = ast.parse(job_file.read_text(encoding="utf-8"), filename=str(job_file))
        lookup = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "bunkernet_id" for target in node.targets)
        )
        job_name = job_file.stem
        db = FakeDatabase()
        namespace = {"JOB": FakeJob(job_name, db)}
        exec(compile(ast.Module(body=[lookup], type_ignores=[]), str(job_file), "exec"), namespace)  # noqa: S102

        cache_values.append(namespace["bunkernet_id"])
        cache_lookups.extend(db.lookups)

    assert cache_values == [b"registered-instance"] * len(JOB_FILES)
    assert cache_lookups == [("bunkernet-register", "instance.id")] * len(JOB_FILES)
