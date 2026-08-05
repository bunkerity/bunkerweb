import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "certificates" / "jobs" / "deploy-certificates.py"


def _load_functions(db):
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    module = ModuleType("certificate_deploy_safety")
    module.JOB = SimpleNamespace(db=db, job_path=Path("/unused"))
    exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


def test_undecryptable_attached_services_are_excluded_from_removal():
    db = Mock()
    db.get_certificates.return_value = {
        "items": [
            {"revoked": False, "attachments": [{"service_id": "keep.example"}]},
            {"revoked": True, "attachments": [{"service_id": "remove.example"}]},
        ],
        "total": 2,
    }
    module = _load_functions(db)

    attached = module.attached_services()
    candidates = {"keep.example", "remove.example"} - set() - attached

    assert attached == {"keep.example"}
    assert candidates == {"remove.example"}
    assert "deployed_services() - set(deployable) - still_attached" in JOB_PATH.read_text(encoding="utf-8")
