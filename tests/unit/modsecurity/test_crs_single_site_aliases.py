"""Single-site aliases share the primary service's CRS plugin metadata."""

from io import BytesIO
from json import loads
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest

from crs_plugins_job_source import JOB_PATH, load_job_helpers


@pytest.mark.parametrize("multisite", [False, True], ids=["single-site", "multisite"])
def test_published_plugin_mapping_uses_service_ids(tmp_path, multisite):
    namespace = load_job_helpers()
    names = ["a.example", "b.example", "c.example"]
    url = "https://example.invalid/plugin.zip"
    env = {"MULTISITE": "yes" if multisite else "no", "SERVER_NAME": " ".join(names)}
    if multisite:
        env.update({f"{name}_MODSECURITY_CRS_PLUGINS": url for name in names})
    else:
        env["MODSECURITY_CRS_PLUGINS"] = url

    archive = BytesIO()
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("alias-test-config.conf", "# Plugin name: alias-test\n# Plugin version: 1.0\n")
    response = MagicMock(status_code=200)
    response.iter_content.return_value = [archive.getvalue()]
    job = MagicMock()
    job.cache_hash.return_value = b""
    job.cache_file.return_value = (True, "")
    job.cache_dir.return_value = (True, "")
    job.db.checked_changes.return_value = None
    namespace.update(
        getenv=env.get,
        Job=MagicMock(return_value=job),
        get=MagicMock(return_value=response),
        Magic=MagicMock(return_value=MagicMock(from_buffer=MagicMock(return_value="application/zip"))),
        run=MagicMock(),
        PATCH_SCRIPT=JOB_PATH.parent.parent / "misc" / "patch.sh",
        CRS_PLUGINS_DIR=tmp_path / "live",
        NEW_PLUGINS_DIR=tmp_path / "staging",
        TMP_DIR=tmp_path / "downloads",
    )

    source = JOB_PATH.read_text()
    body = source[source.index("\ntry:\n") :]
    with pytest.raises(SystemExit) as result:
        exec(compile(body, str(JOB_PATH), "exec"), namespace)  # noqa: S102 - trusted job, isolated boundaries
    assert result.value.code == 1
    publication = next(call for call in job.cache_file.call_args_list if call.args[0] == "crs-plugins.json")
    expected_names = names if multisite else names[:1]
    assert loads(publication.args[1]) == {name: ["alias-test-1.0"] for name in expected_names}
    assert (tmp_path / "live" / "alias-test-1.0" / "alias-test-config.conf").is_file()
