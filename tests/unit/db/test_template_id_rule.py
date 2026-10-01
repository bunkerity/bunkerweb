"""Template ids are checked on creation (QA-UI H14).

`bad id!` used to be stored: USE_TEMPLATE splits on a literal " " (common_utils.split_templates),
so the service read the layers `bad` and `id!` and the template could never be applied. The rule
is creation-only on purpose -- an id stored before it existed must keep working.
"""

import pytest

import db_methods.templates as templates_module  # type: ignore
from fixtures.seed import seed_minimal


def _args(name="Low"):
    return {
        "name": name,
        "settings": {"USE_REVERSE_PROXY": "yes"},
        "steps": [{"title": "Step 1", "settings": ["USE_REVERSE_PROXY"]}],
    }


@pytest.mark.parametrize("template_id", ["bad id!", "a b", "tab\tid", "slash/id", "-leading", ".hidden", "é", "x" * 257, "line\nbreak"])
def test_an_id_outside_the_rule_is_refused(db, template_id):
    seed_minimal(db)
    assert db.create_template(template_id, **_args()) == templates_module.TEMPLATE_ID_RULE
    assert template_id.strip() not in db.get_templates()


@pytest.mark.parametrize("template_id", ["low", "wordpress", "my_template-2", "v1.2", "A", "x" * 256])
def test_an_id_inside_the_rule_is_created(db, template_id):
    seed_minimal(db)
    assert db.create_template(template_id, **_args()) == ""
    assert template_id in db.get_templates()


def test_an_id_stored_before_the_rule_keeps_working(db, monkeypatch):
    seed_minimal(db)
    with monkeypatch.context() as patched:
        patched.setattr(templates_module, "TEMPLATE_ID_RX", templates_module.re_compile(r"^.+$"))
        assert db.create_template("legacy id!", **_args()) == ""

    assert db.update_template("legacy id!", name="Legacy renamed") == ""
    assert db.get_template_details("legacy id!")["name"] == "Legacy renamed"
    assert db.delete_template("legacy id!") == ""
