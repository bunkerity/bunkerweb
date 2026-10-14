"""The durable cookie patch must retain bounded scans on refresh and Docker builds."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("src/deps/src/nginx_cookie_flag_module/ngx_http_cookie_flag_filter_module.c")
PATCH = Path("src/deps/misc/nginx-cookie-flag-samesite-none.patch")


def assert_cookie_contract(source):
    assert "ngx_flag_t samesite_none;" in source
    assert '"samesite=none", 13) == 0 && value[i].len == 13' in source
    calls = re.findall(r"\bngx_strlcasestrn\([^\n]+?\) (?:==|!=) NULL", source)
    assert len(calls) == 7
    assert all(".data + header" in call for call in calls)
    assert any('"; SameSite=None", 15 - 1' in call for call in calls)
    assert any("cookie_name, strlen(cookie_name) - 1" in call for call in calls)
    assert not re.search(r"(?m)^\s*(?:if|.*&&).*\bngx_strcasestrn\(", source)
    assert 'sizeof("=") + cookie[j].cookie_name.len' in source


def test_current_docker_source():
    assert_cookie_contract((ROOT / SOURCE).read_text())


def test_durable_refresh_and_repeat(tmp_path):
    source = tmp_path / SOURCE
    patch = tmp_path / PATCH
    source.parent.mkdir(parents=True)
    patch.parent.mkdir(parents=True)
    source.write_bytes((ROOT / SOURCE).read_bytes())
    patch.write_bytes((ROOT / PATCH).read_bytes())
    subprocess.run(["patch", "--reverse", "--batch", str(SOURCE), str(PATCH)], cwd=tmp_path, check=True)
    assert "samesite_none" not in source.read_text()
    assert "ngx_strlcasestrn" not in source.read_text()
    deps = json.loads((ROOT / "src/deps/deps.json").read_text())
    entry = next(dep for dep in deps["git_repository"] if dep["id"] == "nginx_cookie_flag_module")
    assert entry["commit"] == "4e48acf132952bbed43b28a8e6af0584dacb7b4c"
    for _ in range(2):
        subprocess.run(["bash", "-c", entry["post_install"]], cwd=tmp_path, check=True)
        assert source.read_bytes() == (ROOT / SOURCE).read_bytes()
        assert_cookie_contract(source.read_text())
    source.write_text(source.read_text().replace("ngx_flag_t samesite_none;", "ngx_flag_t corrupted;"))
    assert subprocess.run(["bash", "-c", entry["post_install"]], cwd=tmp_path).returncode != 0
