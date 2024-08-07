from os.path import join, sep
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)


from builder.utils.form import get_forms


def global_config_builder(templates: list[dict], plugins: list, settings: dict) -> str:
    """Render forms with global config data.
    ATM we don't need templates but we need to pass at least one to the function (it will simply not override anything).
    """

    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [
                {
                    "type": "Title",
                    "data": {"title": "global_config_title", "type": "container"},
                },
                {
                    "type": "Subtitle",
                    "data": {"subtitle": "global_config_subtitle", "type": "container"},
                },
                {
                    "type": "Templates",
                    "data": {
                        "templates": get_forms(templates, plugins, settings, ("advanced", "raw")),
                    },
                },
            ],
        }
    ]
    return builder
