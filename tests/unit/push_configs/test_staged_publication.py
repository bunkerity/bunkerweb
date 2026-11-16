"""The renderer must not modify live NGINX output before the coordinated upload."""

import ast
import __future__
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
JOB = ROOT / "src/common/core/jobs/jobs/push-configs.py"


def functions():
    tree = ast.parse(JOB.read_text())
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    namespace = dict(
        Path=Path,
        getenv=lambda name, default=None: default,
        BUNKERWEB_PATH=Path("/usr/share/bunkerweb"),
        CONFIG_PATH=Path("/etc/nginx"),
        LOGGER=Mock(),
        DEVNULL=-3,
        STDOUT=-2,
    )
    exec(compile(tree, str(JOB), "exec", flags=__future__.annotations.compiler_flag), namespace)
    return namespace


def test_renderer_uses_private_output(tmp_path):
    namespace = functions()
    command = []
    namespace["subprocess_run"] = lambda args, **kwargs: command.extend(args) or Mock(returncode=0)
    assert namespace["_render_nginx_configs"](tmp_path)
    assert command[command.index("--output") + 1] == str(tmp_path)
    assert namespace["CONFIG_PATH"] == Path("/etc/nginx")


def test_push_all_uploads_the_candidate(tmp_path):
    namespace = functions()
    namespace.update(CACHE_PATH=tmp_path, CUSTOM_CONFIGS_PATH=tmp_path, EXTERNAL_PLUGINS_PATH=tmp_path, PRO_PLUGINS_PATH=tmp_path)
    seen = []
    namespace["_push_configs"] = lambda instances, src: seen.append(src) or True
    namespace["_push_one_kind"] = lambda *args: True
    assert namespace["_push_all"](object(), [], tmp_path)
    assert seen == [tmp_path]


def test_only_confirmed_render_is_retained(tmp_path, monkeypatch):
    import shutil
    from tempfile import TemporaryDirectory

    monkeypatch.syspath_prepend(str(ROOT / "src/common/gen"))
    namespace = functions()
    namespace.update(copytree=shutil.copytree, TemporaryDirectory=TemporaryDirectory, FAILOVER_PATH=tmp_path / "failover")
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "policy.conf").write_text("deny all;")
    namespace["_remember_rendered_config"](source)
    assert (tmp_path / "generated/policy.conf").read_text() == "deny all;"
    assert (source / "policy.conf").read_text() == "deny all;"


def test_failed_apply_never_replaces_accepted_output(tmp_path):
    tree = ast.parse(JOB.read_text())
    main = next(
        node
        for node in tree.body
        if isinstance(node, ast.Try) and any(isinstance(stmt, ast.If) and ast.unparse(stmt.test) == "reload_ok" for stmt in node.body)
    )
    begin = next(i for i, stmt in enumerate(main.body) if isinstance(stmt, ast.Assign) and ast.unparse(stmt.targets[0]) == "(reload_ok, reload_responses)")
    remember = Mock()
    namespace = dict(
        _trigger_reload=lambda caller: (False, {}),
        _record_failover=Mock(),
        _restore_from_snapshot=Mock(return_value=True),
        _remember_rendered_config=remember,
        LOGGER=Mock(),
        api_caller=object(),
        db=object(),
        instances=[],
        target_hostnames=[],
        snapshot=object(),
        status=0,
        sys_exit=lambda code: (_ for _ in ()).throw(SystemExit(code)),
    )
    import pytest

    with pytest.raises(SystemExit) as failure:
        exec(compile(ast.Module(body=main.body[begin:], type_ignores=[]), str(JOB), "exec"), namespace)
    assert failure.value.code == 2
    remember.assert_not_called()


def test_temporary_cleanup_failure_still_releases_push_lease():
    from contextlib import suppress

    tree = ast.parse(JOB.read_text())
    main = next(node for node in tree.body if isinstance(node, ast.Try) and node.finalbody)
    client = Mock()
    namespace = dict(
        render_dir=Mock(cleanup=Mock(side_effect=OSError("cleanup failed"))),
        LOGGER=Mock(),
        lock_acquired=True,
        client=client,
        LOCK_KEY="push-lease",
        suppress=suppress,
    )
    exec(compile(ast.Module(body=main.finalbody, type_ignores=[]), str(JOB), "exec"), namespace)
    client.delete.assert_called_once_with("push-lease")


def test_failed_artifact_install_never_reloads_partial_tree():
    import pytest

    tree = ast.parse(JOB.read_text())
    main = next(node for node in tree.body if isinstance(node, ast.Try) and node.finalbody)
    begin = next(i for i, stmt in enumerate(main.body) if isinstance(stmt, ast.Assign) and ast.unparse(stmt.targets[0]) == "push_ok")
    end = next(
        i
        for i, stmt in enumerate(main.body)
        if isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Name)
        and stmt.value.func.id == "_record_failover"
    )
    reload = Mock(return_value=(True, {}))
    namespace = dict(
        _push_all=Mock(return_value=False),
        _trigger_reload=reload,
        LOGGER=Mock(),
        api_caller=object(),
        instances=[],
        rendered_path=Path("/private/render"),
        sys_exit=lambda code: (_ for _ in ()).throw(SystemExit(code)),
    )
    with pytest.raises(SystemExit) as failure:
        exec(compile(ast.Module(body=main.body[begin:end], type_ignores=[]), str(JOB), "exec"), namespace)
    assert failure.value.code == 2
    reload.assert_not_called()
