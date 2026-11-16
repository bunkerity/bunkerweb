"""Restoring the previous config recovers service, but the requested apply still failed."""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

JOB = Path(__file__).resolve().parents[3] / "src/common/core/jobs/jobs/push-configs.py"


@pytest.mark.parametrize("accepted,exit_code", [(False, 2), (True, 0)])
def test_failed_reload_is_not_hidden_by_successful_failover(accepted, exit_code):
    tree = ast.parse(JOB.read_text())
    push = next(
        node
        for node in tree.body
        if isinstance(node, ast.Try) and any(isinstance(stmt, ast.If) and ast.unparse(stmt.test) == "reload_ok" for stmt in node.body)
    )
    start = next(i for i, stmt in enumerate(push.body) if isinstance(stmt, ast.Assign) and ast.unparse(stmt.targets[0]) == "(reload_ok, reload_responses)")
    body = ast.Module(body=push.body[start:], type_ignores=[])
    ack, restore = Mock(), Mock(return_value=True)

    def exit_job(code):
        raise SystemExit(code)

    namespace = dict(
        _trigger_reload=Mock(return_value=(accepted, {})),
        _record_failover=Mock(),
        _remember_rendered_config=Mock(),
        rendered_path=Path("/private/render"),
        _restore_from_snapshot=restore,
        _mark_failover=Mock(),
        acknowledge_changes=ack,
        LOGGER=Mock(),
        db=Mock(),
        api_caller=Mock(),
        instances=[],
        snapshot=object(),
        target_hostnames=[],
        metadata_snapshot={},
        push_ok=True,
        caches_materialized=True,
        custom_configs_materialized=True,
        status=0,
        sys_exit=exit_job,
    )
    with pytest.raises(SystemExit) as result:
        exec(compile(body, str(JOB), "exec"), namespace)
    assert result.value.code == exit_code
    assert ack.call_count == int(accepted)
    assert restore.call_count == int(not accepted)
