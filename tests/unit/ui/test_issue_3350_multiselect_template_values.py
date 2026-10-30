"""A multiselect setting renders the value it is given, including on the new-service page (#3350).

Selections made in a template's multiselect settings did not reach a new service: on the new-service endpoint the macro
ignored the passed value and rendered the global default instead. This renders the real template and reads what the
browser would get: the hidden field that is posted and the options that appear ticked.
"""

import re
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

TEMPLATES = Path(__file__).resolve().parents[3] / "src/ui/app/templates"
SETTING_DATA = {
    "id": "multi-setting",
    "separator": " ",
    "multiselect": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}],
}


def render(**context):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)))
    html = env.get_template("models/multiselect_setting.html").render(
        setting="MULTI_SETTING",
        setting_data=SETTING_DATA,
        setting_id_prefix="",
        setting_id_suffix="",
        setting_method="default",
        disabled=False,
        **context,
    )
    posted = re.search(r'class="plugin-setting"\s+value="([^"]*)"', html).group(1)
    ticked = re.findall(r'<input class="form-check-input m-0"\s+type="checkbox"\s+value="([^"]+)"[^>]*?\bchecked\b', html)
    return posted, ticked


@pytest.mark.parametrize("endpoint", ["new", "edit"])
def test_issue_3350_values_from_the_template_are_rendered_on_every_endpoint(endpoint):
    """The passed value, not the default, is the posted value and decides the ticked options (#3350)."""
    posted, ticked = render(current_endpoint=endpoint, setting_value="a b", setting_default="c")

    assert posted == "a b"
    assert ticked == ["a", "b"]


def test_issue_3350_a_missing_value_falls_back_to_the_default():
    """Nothing passed by the template leaves the default selection in place (#3350)."""
    posted, ticked = render(current_endpoint="new", setting_value=None, setting_default="c")

    assert posted == "c"
    assert ticked == ["c"]
