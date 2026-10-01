"""M18: the scheduler loop must never write the NGINX failover flag.

It used to write ``{"failover": not success, "failover_message": ""}`` every pass, where ``success``
is whether every instance answered a ping: deleting an unreachable instance raised the UI's
"configuration error on NGINX" banner with an empty message. It then wrote ``failover False`` every
pass, which would erase what push-configs records. The producer is push-configs, from the reload
responses (``tests/unit/push_configs/test_failover_metadata.py``).

``main.py`` runs its loop at import, so ``set_metadata`` payloads are read from its syntax tree.
"""

import ast
from pathlib import Path

MAIN = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"


def test_the_scheduler_never_writes_the_failover_flag():
    written = []
    for node in ast.walk(ast.parse(MAIN.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("set_metadata") and node.args and isinstance(node.args[0], ast.Dict):
            written += [key.value for key in node.args[0].keys if isinstance(key, ast.Constant) and str(key.value).startswith("failover")]
    assert not written, f"the scheduler writes {written}: push-configs owns the failover metadata"
