from base64 import b64encode
from datetime import datetime
from typing import Union
from bs4 import BeautifulSoup, Tag
import magic
import json
import os
import re


def get_variables():
    vars = {}
    vars["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    vars["ABSOLUTE_URI"] = ""
    vars["FLASK_SECRET"] = os.urandom(32)
    vars["FLASK_ENV"] = "development"
    vars["ADMIN_USERNAME"] = "admin"
    vars["ADMIN_PASSWORD"] = "changeme"

    for k in vars:
        if k in os.environ:
            vars[k] = os.environ[k]

    return vars


def log(event):
    with open("/var/log/nginx/ui.log", "a") as f:
        f.write("[" + str(datetime.now().replace(microsecond=0)) + "] " + event + "\n")


def env_to_summary_class(var, value):
    if type(var) is list and type(value) is list:
        for i in range(0, len(var)):
            if not isinstance(var[i], str):
                continue
            if re.search(value[i], var[i]):
                return "check text-success"
        return "times text-danger"
    if not isinstance(var, str):
        return "times text-danger"
    if re.search(value, var):
        return "check text-success"
    return "times text-danger"


def form_service_gen(
    _id,
    _help,
    label,
    _type,
    value,
    name,
    default,
    selects,
    regex,
    from_html: bool = True,
    root: Tag = None,
) -> str:
    if root is None:
        root = BeautifulSoup()

    tooltip = Tag(
        name="div",
        attrs={
            "class": "px-2 d-sm-inline",
            "data-bs-toggle": "tooltip",
            "data-bs-placement": "bottom",
            "title": _help,
        },
    )
    tooltip.append(Tag(name="i", attrs={"class": "fas fa-question-circle"}))
    root.append(tooltip)
    pt = ""
    invalid_div = None

    if _type in ("text", "number"):
        edit = Tag(
            name="input",
            attrs={
                "type": _type,
                "class": "form-control",
                "id": _id,
                "name": name,
                "value": value if value else default,
                "pattern": regex,
            },
        )

        invalid_div = Tag(name="div", attrs={"class": "invalid-feedback"})
        invalid_div.append(
            BeautifulSoup(
                f"{label} is invalid and must match this pattern: <i><b>{regex}</b></i>",
                "html.parser",
            )
        )
    elif _type == "check":
        edit = Tag(
            name="div",
            attrs={"class": "form-check form-switch"},
        )
        edit.append(
            BeautifulSoup(
                f"<input type='checkbox' role='switch' class='form-check-input' id='{_id}' name='{name}' {'checked' if value and value == 'yes' or not value and default and default == 'yes' else ''}>",
                "html.parser",
            )
        )
        edit.append(
            Tag(
                name="input",
                attrs={
                    "type": "hidden",
                    "id": f"{_id}-hidden",
                    "name": name,
                    "value": "off",
                },
            )
        )
        pt = "pt-0"
    elif _type == "select":
        edit = Tag(
            name="select",
            attrs={
                "type": "form-select",
                "class": "form-control form-select",
                "id": _id,
                "name": name,
            },
        )

        for select in selects:
            edit.append(
                BeautifulSoup(
                    f"<option value='{select}' {'selected' if value and select == value or not value and select == default else ''}>{select}</option>",
                    "html.parser",
                )
            )

    label_tag = Tag(
        name="label", attrs={"for": _id, "class": f"flex-grow-1 d-sm-inline {pt}"}
    )
    label_tag.append(label)
    root.append(label_tag)

    div = Tag(name="div", attrs={"class": "d-sm-inline"})
    div.append(edit)

    if invalid_div:
        div.append(invalid_div)

    root.append(div)

    if from_html:
        return root.prettify()
    else:
        return root


def form_service_gen_multiple(_id, label, params, root) -> Tag:
    label_tag = Tag(
        name="label",
        attrs={"for": f"{_id}-btn", "class": "flex-grow-1 d-sm-inline"},
    )
    label_tag.append(label)
    root.append(label_tag)

    buttons = Tag(name="div", attrs={"class": "d-sm-inline", "id": _id})

    add_button = Tag(
        name="button",
        attrs={
            "class": "btn btn-outline-success",
            "type": "button",
            "onClick": f"addMultiple('{_id}', '{json.dumps(params)}');",
        },
    )
    add_button.append(Tag(name="i", attrs={"class": "fas fa-plus"}))
    add_button.append(" Add")
    buttons.append(add_button)

    del_button = Tag(
        name="button",
        attrs={
            "class": "btn btn-outline-danger",
            "type": "button",
            "onClick": f"delMultiple('{_id}', '{json.dumps(params)}');",
        },
    )
    del_button.append(Tag(name="i", attrs={"class": "fas fa-trash"}))
    del_button.append(" Delete")
    buttons.append(del_button)

    root.append(buttons)
    return root


def form_service_gen_multiple_values(_id, params, service) -> Union[Tag, str]:
    script = Tag(name="script", attrs={"defer": True})
    values = []
    for env in sorted(
        service,
        reverse=True,
        key=lambda x: int(re.search(r"\d+$", x).group()) if x[-1].isdigit() else 0,
    ):
        for param, param_value in params.items():
            add = env == param or (re.search(r"_\d+$", env) is not None and "_".join(env.split("_")[:-1]) == param)
            if not add :
                continue
            suffix = env.replace(param, "")
            values.append(
                {
                    "default": service.get(
                        f"{param}{suffix}", param_value["default"]
                    ),
                    "env": param,
                    "help": param_value["help"],
                    "id": param_value["id"],
                    "label": param_value["label"],
                    "selects": param_value.get("selects", []),
                    "type": param_value["type"],
                }
            )

        if len(values) >= len(params):
            script.append(f"addMultiple('{_id}', '{json.dumps(values)}');")
            values = []

    return script if script.children else ""


def form_plugin_gen(
    service: dict,
    plugin: dict,
    action: str,
    id_server_name: str = None,
    *,
    context: str = "multisite",
) -> str:
    soup = BeautifulSoup()
    soup.append(
        Tag(
            name="div",
            attrs={
                "class": "tab-pane fade",
                "id": f"{action}-{plugin['id']}"
                + (f"-{id_server_name}" if id_server_name else ""),
                "role": "tabpanel",
                "aria-labelledby": f"{action}-{plugin['id']}"
                + (f"-{id_server_name}" if id_server_name else "")
                + "-tab",
            },
        )
    )
    multiple_plugins = {}
    multiple = None

    for setting, value in plugin["settings"].items():
        if value["context"] == context:
            if "multiple" in value:
                if multiple != value["multiple"]:
                    multiple = value["multiple"]
                    multiple_plugins[multiple] = {}
                multiple_plugins[multiple][setting] = value
                multiple_plugins[multiple][setting]["env"] = setting
            else:
                div = Tag(
                    name="div",
                    attrs={
                        "class": "d-flex flex-row justify-content-between align-items-center mb-3",
                        "id": f"form-{action}"
                        + (f"-{id_server_name}" if id_server_name else "")
                        + f"-{value['id']}",
                    },
                )

                div = form_service_gen(
                    f"form-{action}"
                    + (f"-{id_server_name}" if id_server_name else "")
                    + f"-{value['id']}",
                    value["help"],
                    value["label"],
                    value["type"],
                    service.get(setting, value["default"]),
                    setting,
                    value["default"],
                    value.get("select", None),
                    value["regex"],
                    False,
                    div,
                )

                soup.div.append(div)

    for multiple_plugin in multiple_plugins:
        div = Tag(
            name="div",
            attrs={
                "class": "d-flex flex-row justify-content-between align-items-center mb-3",
                "id": f"form-{action}"
                + (f"-{id_server_name}" if id_server_name else "")
                + f"-{multiple_plugin}",
            },
        )

        div = form_service_gen_multiple(
            f"form-{action}"
            + (f"-{id_server_name}" if id_server_name else "")
            + f"-{multiple_plugin}",
            plugin["name"],
            multiple_plugins[multiple_plugin],
            div,
        )
        if service:
            div.append(
                form_service_gen_multiple_values(
                    f"form-{action}"
                    + (f"-{id_server_name}" if id_server_name else "")
                    + f"-{multiple_plugin}",
                    multiple_plugins[multiple_plugin],
                    service,
                )
            )

        soup.div.append(div)

    return soup.prettify()


def path_to_dict(path, *, level: int = 0, is_cache: bool = False) -> dict:
    d = {"name": os.path.basename(path)}

    if os.path.isdir(path):
        d.update(
            {
                "type": "folder",
                "path": path,
                "can_create_files": level > 0 and not is_cache,
                "can_create_folders": level > 0 and not is_cache,
                "can_edit": level > 1 and not is_cache,
                "can_delete": level > 1 and not is_cache,
                "children": [
                    path_to_dict(
                        os.path.join(path, x), level=level + 1, is_cache=is_cache
                    )
                    for x in sorted(os.listdir(path))
                ],
            }
        )
    else:
        d.update(
            {
                "type": "file",
                "path": path,
                "can_edit": level > 1 and not is_cache,
                "can_download": is_cache,
            }
        )

        magic_file = magic.from_file(path, mime=True)

        if (
            not is_cache
            or magic_file.startswith("text/")
            or magic_file.startswith("application/json")
        ):
            with open(path, "rb") as f:
                d["content"] = b64encode(f.read()).decode("utf-8")

    return d


options = {
    "can_edit": {
        "button_style": "btn-outline-primary",
        "data-bs-target": "#modal-edit-new-folder",
        "icon": "fa-solid fa-pen-to-square",
    },
    "can_delete": {
        "button_style": "btn-outline-danger",
        "data-bs-target": "#modal-delete",
        "icon": "fa-solid fa-trash-can",
    },
    "can_create_folders": {
        "button_style": "btn-outline-success",
        "data-bs-target": "#modal-edit-new-folder",
        "icon": "fa-solid fa-folder",
    },
    "can_create_files": {
        "button_style": "btn-outline-success",
        "data-bs-target": "#modal-edit-new-file",
        "icon": "fa-solid fa-file",
    },
}


def gen_folders_tree_html(data: list) -> str:
    html = "<ul class='folder-container'>"

    for _dict in sorted(data, key=lambda x: x["type"] == "file", reverse=True):
        path_id = _dict["path"].replace("/", "-")[1:]
        root_li = Tag(
            name="li",
            attrs={
                "class": f"{_dict['type']}-item d-flex align-items-center",
            },
        )

        if _dict["type"] == "folder":
            root_div = Tag(
                name="div",
                attrs={
                    "class": "collapse-div",
                    "data-bs-toggle": "collapse",
                    "href": f"#{path_id}",
                    "role": "button",
                    "aria-expanded": "true",
                    "aria-controls": path_id,
                },
            )

            h6 = Tag(name="span", attrs={"class": "mb-0 pl-2"})
            h6.append(_dict["name"])

            if _dict.get("children", False):
                root_div.append(
                    Tag(
                        name="span",
                        attrs={"class": f"fa-solid fa-play fa-xs rotate-icon down"},
                    )
                )

            root_div.append(h6)

            root_li.append(root_div)

            if any(
                [
                    _dict["can_create_files"],
                    _dict["can_create_folders"],
                    _dict["can_edit"],
                    _dict["can_delete"],
                ]
            ):
                div = Tag(
                    name="div", attrs={"class": "ms-2 d-sm-flex align-items-between"}
                )
                dropdown = None

                if any(
                    [
                        _dict["can_create_files"],
                        _dict["can_create_folders"],
                    ]
                ):
                    dropdown = Tag(name="div", attrs={"class": "badge dropdown"})
                    button = Tag(
                        name="button",
                        attrs={
                            "type": "button",
                            "class": "btn btn-outline-success",
                            "id": "dropdownSettingsButton",
                            "data-bs-toggle": "dropdown",
                            "aria-expanded": "false",
                        },
                    )
                    button.append(Tag(name="i", attrs={"class": "fa-solid fa-plus"}))
                    dropdown.append(button)
                    ul = Tag(
                        name="ul",
                        attrs={
                            "class": "dropdown-menu",
                            "aria-labelledby": "dropdownSettingsButton",
                        },
                    )

                for option in options:
                    if _dict[option]:
                        if option in ("can_create_files", "can_create_folders"):
                            li = Tag(name="li")

                            button = Tag(
                                name="button",
                                attrs={
                                    "class": "dropdown-item",
                                    "data-bs-toggle": "modal",
                                    "data-bs-target": options[option]["data-bs-target"],
                                    "data-path": _dict["path"],
                                    "data-action": "new",
                                },
                            )
                            button.append(
                                Tag(
                                    name="i",
                                    attrs={
                                        "class": options[option]["icon"],
                                    },
                                )
                            )

                            span = Tag(
                                name="span",
                                attrs={"class": "pl-2"},
                            )
                            span.append(option.split("_")[-1][0:-1].title())
                            button.append(span)

                            li.append(button)
                            ul.append(li)
                        else:
                            badge = Tag(name="div", attrs={"class": "badge px-1"})
                            action = option.split("_")[1]
                            button = Tag(
                                name="button",
                                attrs={
                                    "class": f"btn {options[option]['button_style']}",
                                    "data-bs-toggle": "modal",
                                    "data-bs-target": options[option]["data-bs-target"],
                                    "data-path": _dict["path"],
                                }
                                | (
                                    {"data-action": action}
                                    if action != "delete"
                                    else {}
                                ),
                            )
                            button.append(
                                Tag(name="i", attrs={"class": options[option]["icon"]})
                            )

                            badge.append(button)
                            div.append(badge)

                if dropdown:
                    dropdown.append(ul)
                    div.append(dropdown)

                root_li.append(div)

            html += root_li.prettify()
            html += (
                f"<li class='collapse folder-wrapper show' id={path_id}>"
                if _dict.get("children", False)
                else "<li class='folder-wrapper'>"
            )

            if _dict.get("children", False):
                html += gen_folders_tree_html(_dict["children"])
                html += "</ul></li>"
        else:
            h6 = Tag(name="h6", attrs={"class": "mb-0"})
            h6.append(_dict["name"])
            root_li.append(h6)

            div = Tag(name="div", attrs={"class": "ms-2 d-sm-flex align-items-between"})

            if _dict["can_edit"]:
                badge = Tag(name="div", attrs={"class": "badge px-1"})
                button = Tag(
                    name="button",
                    attrs={
                        "class": f"btn btn-outline-primary",
                        "data-bs-toggle": "modal",
                        "data-bs-target": "#modal-edit-new-file",
                        "data-path": _dict["path"],
                        "data-content": _dict["content"],
                        "data-action": "edit",
                    },
                )
                button.append(
                    Tag(name="i", attrs={"class": "fa-solid fa-pen-to-square"})
                )
                badge.append(button)
                div.append(badge)

                badge = Tag(name="div", attrs={"class": "badge px-1"})
                button = Tag(
                    name="button",
                    attrs={
                        "class": f"btn btn-outline-danger",
                        "data-bs-toggle": "modal",
                        "data-bs-target": "#modal-delete",
                        "data-path": _dict["path"],
                    },
                )
                button.append(Tag(name="i", attrs={"class": "fa-solid fa-trash-can"}))
                badge.append(button)
                div.append(badge)
            elif "content" in _dict:
                badge = Tag(name="div", attrs={"class": "badge px-1"})
                button = Tag(
                    name="button",
                    attrs={
                        "class": f"btn btn-outline-secondary",
                        "data-bs-toggle": "modal",
                        "data-bs-target": "#modal-see-file",
                        "data-path": _dict["path"],
                        "data-content": _dict["content"],
                    },
                )
                button.append(Tag(name="i", attrs={"class": "fa-solid fa-eye"}))
                badge.append(button)
                div.append(badge)

            if _dict["can_download"]:
                badge = Tag(name="div", attrs={"class": "badge px-1"})
                button = Tag(
                    name="button",
                    attrs={
                        "class": f"btn btn-outline-primary download-button",
                        "data-path": _dict["path"],
                    },
                )
                button.append(Tag(name="i", attrs={"class": "fa-solid fa-download"}))
                badge.append(button)
                div.append(badge)

            root_li.append(div)
            html += root_li.prettify()

    return html


def check_settings(settings: dict, check: str) -> bool:
    return any(setting["context"] == check for setting in settings.values())
