"""A renewal lineage is healthy only when all four certbot files are referenced and usable.

Certbot requires ``cert``, ``privkey``, ``chain`` and ``fullchain`` in the renewal conf, and every
``live/<name>/*.pem`` to be a symlink that resolves. A lineage missing one of them was reported healthy
by the cache check, so ``certbot renew`` failed on it and then issued a fresh certificate on every pass.

Refs: #3324
"""

from pathlib import Path

import pytest

import letsencrypt_consistency as le

KINDS = ("cert", "privkey", "chain", "fullchain")


def make_lineage(root: Path, name="example.com", *, omit_ref=None):
    renewal = root / "renewal"
    renewal.mkdir(exist_ok=True)
    live = root / "live" / name
    archive = root / "archive" / name
    live.mkdir(parents=True)
    archive.mkdir(parents=True)
    lines = [f"archive_dir = {archive}"]
    for kind in KINDS:
        (archive / f"{kind}1.pem").write_text(kind)
        (live / f"{kind}.pem").symlink_to(Path("../../archive") / name / f"{kind}1.pem")
        if kind != omit_ref:
            lines.append(f"{kind} = {live / (kind + '.pem')}")
    (renewal / f"{name}.conf").write_text("\n".join(lines + ["[renewalparams]", "account = None"]) + "\n")
    return live, archive


def reasons(root):
    return {item["cert_name"]: item["reason"] for item in le.detect_broken_lineages(root)}


def test_a_complete_lineage_is_healthy(tmp_path):
    make_lineage(tmp_path)

    assert le.detect_broken_lineages(tmp_path) == []


@pytest.mark.parametrize("kind", ["privkey", "chain"])
def test_a_conf_without_one_required_reference_is_broken(tmp_path, kind):
    make_lineage(tmp_path, omit_ref=kind)

    found = reasons(tmp_path)

    assert list(found) == ["example.com"]
    assert kind in found["example.com"]


@pytest.mark.parametrize("kind", ["privkey", "chain"])
def test_a_dangling_live_symlink_is_broken(tmp_path, kind):
    _, archive = make_lineage(tmp_path)
    (archive / f"{kind}1.pem").unlink()

    found = reasons(tmp_path)

    assert f"{kind}.pem" in found["example.com"]


def test_a_dereferenced_live_file_is_broken(tmp_path):
    live, _ = make_lineage(tmp_path)
    (live / "chain.pem").unlink()
    (live / "chain.pem").write_text("regular file")

    assert "chain.pem" in reasons(tmp_path)["example.com"]
