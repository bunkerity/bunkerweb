"""Job(logger) must infer the same identity as Job(logger, __file__)."""

import logging

import jobs


def test_job_infers_calling_script(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "sep", str(tmp_path / "cache"))
    script = tmp_path / "plugin/jobs/run.py"
    script.parent.mkdir(parents=True)
    script.write_text("result = Job(logger, db=db, deprecated=True)\n")
    namespace = {"Job": jobs.Job, "logger": logging.getLogger("inferred-job"), "db": object()}

    exec(compile(script.read_text(), str(script), "exec"), namespace)

    inferred = namespace["result"]
    explicit = jobs.Job(namespace["logger"], script, db=namespace["db"], deprecated=True)
    assert inferred.job_name == explicit.job_name == "run"
    assert inferred.job_path == explicit.job_path == tmp_path / "cache/var/cache/bunkerweb/plugin"
