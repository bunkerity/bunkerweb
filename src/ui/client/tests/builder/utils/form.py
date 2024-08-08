import copy
from typing import Union


def get_setting_data(template_settings: dict, settings: dict, setting: str, value: dict, is_multiple_setting: bool = False, is_new: bool = False) -> tuple:
    template_value = template_settings.get(setting, None)
    current_value = settings[setting].get("value", None) if setting in settings else None
    default_value = value.get("default")
    is_disabled_method = (
        True if settings.get(setting, {}).get("method", "ui") not in ("ui", "default", "manual") and not is_new and not is_multiple_setting else False
    )
    is_current_from_template = True if settings.get(setting, {}).get("template", None) is not None and template_value is not None else False
    is_current_default = current_value is not None and current_value == default_value
    setting_value = current_value if current_value is not None and not is_new and not is_multiple_setting else default_value
    return template_value, current_value, default_value, is_disabled_method, is_current_from_template, is_current_default, setting_value


def get_service_settings(service_name: str, global_config: dict, total_config: dict) -> dict:
    """
    total_config is a dict that contains global settings and services settings (format SERVICE_NAME_SETTING - www.example.com_USE_ANTIBOT for example -).
    We will only keep settings that are related to the service_name (with prefix SERVICE_NAME_).
    Then we will loop on global key and override value from global config by service config if exists.
    """

    # Get service settings
    service_settings = {}
    for key, value in total_config.items():
        if not key.startswith(f"{service_name}_"):
            continue

        service_settings[key.replace(f"{service_name}_", "")] = value

    # Loop on global settings to override by service settings
    for key, value in service_settings.items():
        global_config[key] = value

    return global_config


def get_plugins_multisite(plugins: list) -> list:
    # loop on plugins with list index
    plugins_multisite = []
    for index, plugin in enumerate(plugins):
        multisite_settings = {}
        # loop on settings
        for setting, value in plugin.get("settings").items():
            # check if setting is multisite
            if value.get("context") != "multisite":
                continue
                # add multisite key to plugin
            multisite_settings[setting] = value

        # add multisite settings to plugin
        if len(multisite_settings):
            plugin_multisite = copy.deepcopy(plugin)
            plugin_multisite["settings"] = multisite_settings
            plugins_multisite.append(plugin_multisite)

    return plugins_multisite


def get_forms(
    templates_ui: list = [],
    plugins: list = [],
    settings: dict = {},
    render_forms: tuple = ("advanced", "easy", "raw"),
    is_new: bool = False,
    only_multisite: bool = False,
) -> dict:
    """
    Will generate every needed form using templates, plugins and settings.
    We will run on each plugins, set template value if one, and override by the custom settings value if exists.
    We will format to fit each form type (easy, advanced, raw) in case
    """
    # Copy of the plugins, and get the plugins by context if needed
    # In services page, we want only multisite settings, but in global config we want both
    plugins_base = get_plugins_multisite(plugins) if only_multisite else plugins

    # This template will be used to show default value or value if exists
    templates = [
        {
            "name": "default",
            "steps": [],
            "configs": {},
            "settings": {},
        }
    ]

    for key, value in templates_ui.items():
        value["label"] = value["name"]
        value["name"] = key
        templates.append(value)

    # Update SERVER_NAME to be empty if new
    if is_new and "SERVER_NAME" in settings:
        settings["SERVER_NAME"]["value"] = ""

    if is_new and not "SERVER_NAME" in settings:
        settings["SERVER_NAME"] = {"value": "", "method": "ui", "global": False}

    forms = {}
    for form in render_forms:
        forms[form] = {}

    for template in templates:
        if "advanced" in forms:
            forms["advanced"][template.get("name")] = set_advanced(template, plugins_base, settings, is_new)

        if "raw" in forms:
            forms["raw"][template.get("name")] = set_raw(template, plugins_base, settings, is_new)

        if "easy" in forms:
            forms["easy"][template.get("name")] = set_easy(template, plugins_base, settings, is_new)

    return forms


def set_easy(template: list, plugins_base: list, settings: dict, is_new: bool) -> dict:
    """
    Prepare the easy form based on the template and plugins data.
    We need to loop on each steps and prepare settings and configs for each step.
    """
    template_settings = template.get("settings")
    plugins = copy.deepcopy(plugins_base)
    steps = template.get("steps")
    print(steps)
    for step in steps:
        step_settings = step.get("settings", {})
        # Loop on step settings to set the settings value
        loop_id = 0
        step_settings_output = {}
        for setting in step_settings:
            loop_id += 1
            # Get relate setting from plugins using setting name
            plugin = next(
                (plugin for plugin in plugins if setting in plugin.get("settings")),
                None,
            )

            if not plugin:
                continue

            if not plugin.get("settings").get(setting):
                continue

            plugin_setting = copy.deepcopy(plugin.get("settings").get(setting))

            plugin_setting = format_setting(setting, plugin_setting, len(step_settings), loop_id, template_settings, settings, is_new)

            step_settings_output[setting] = plugin_setting

        step["settings"] = step_settings_output

    return steps


def set_raw(template: list, plugins_base: list, settings: dict, is_new: bool = False) -> dict:
    """
    Set the raw form based on the template and plugins data.
    It consists of keeping only the value or default value for each plugin settings.
    """
    template_settings = template.get("settings")
    raw_settings = {}
    # Copy of the plugins base
    plugins = copy.deepcopy(plugins_base)
    # Update settings with global config data
    for plugin in plugins:
        for setting, value in plugin.get("settings").items():

            is_multiple_setting = "multiple" in value

            # By default, we will loop on one setting (not multiple)
            total_settings = {setting: value}

            # Case multiple, retrieve all settings that start with setting name
            if is_multiple_setting:
                # get all settings that start with setting name
                total_settings = {k: v for k, v in settings.items() if k.startswith(f"{setting}")}

            # Loop in a same way it is a multiple or regular setting
            for mult_setting, mult_value in total_settings.items():

                # Get setting data
                # We need to send setting and not mult_setting because mult_setting is unknown on plugin side
                template_value, current_value, default_value, is_disabled_method, is_current_from_template, is_current_default, setting_value = (
                    get_setting_data(template_settings, settings, mult_setting, mult_value)
                )

                if current_value is not None:
                    raw_settings[mult_setting] = current_value
                    continue

                if template_value is not None:
                    raw_settings[mult_setting] = template_value
                    continue

    return raw_settings


def set_advanced(template: list, plugins_base: list, settings: dict, is_new: bool) -> dict:
    """
    Set the advanced form based on the template and plugins data.
    It consists of formatting each plugin settings to be used in the advanced form.
    """
    template_settings = template.get("settings")
    # Copy of the plugins base data
    plugins = copy.deepcopy(plugins_base)
    # Update settings with global config data
    for plugin in plugins:
        loop_id = 0
        total_settings = len(plugin.get("settings"))
        for setting, value in plugin.get("settings").items():
            loop_id += 1
            value = format_setting(setting, value, total_settings, loop_id, template_settings, settings, is_new)

    set_multiples(template, plugins, settings)

    return plugins


def get_multiple_from_template(template, multiples):
    """
    We are gonna loop on each plugins multiples group, in case a setting is matching a template setting,
    we will create a group using the prefix as key (or "0" if no prefix) with default settings at first.
    Then we will override by the template value in case there is one.
    This will return something of this type :
    {'0' : {'setting' : value, 'setting2': value2}, '1' : {'setting_1': value, 'setting2_1': value}} }
    """
    # Loop on each plugin and loop on multiples key
    # Check if the name us matching a template key
    multiple_plugin = copy.deepcopy(multiples)

    multiple_template = {}
    for setting, value in template.get("settings").items():
        # Sanitize setting name to remove prefix of type _1 if exists
        # Slipt by _ and check if last element is a digit
        format_setting = setting
        setting_split = setting.split("_")
        prefix = "0"
        if setting_split[-1].isdigit():
            prefix = setting_split[-1]
            format_setting = "_".join(setting_split[:-1])
        # loop on settings of a multiple group
        for mult_name, mult_settings in multiple_plugin.items():

            # Check if at least one settign is matching a multiple setting
            if not format_setting in mult_settings:
                continue

            # Case we have at least one multiple setting, we can check if multiple name exists or create it
            if not mult_name in multiple_template:
                multiple_template[mult_name] = {}

            # Case it is, we will check if already a group with the right prefix exists
            # If not, we will create it
            if not prefix in multiple_template[mult_name]:
                # We want each settings to have the prefix if exists
                # We will get the value of the setting without the prefix and create a prefix key with the same value
                # And after that we can delete the original setting
                new_multiple_group = {}
                for multSett, multValue in mult_settings.items():
                    new_multiple_group[f"{multSett}{f'_{prefix}' if prefix != '0' else ''}"] = multValue

                new_multiple_group = copy.deepcopy(new_multiple_group)

                # Update id for each settings
                for multSett, multValue in new_multiple_group.items():
                    multValue["id"] = f"{multValue['id']}{f'-{prefix}' if prefix != '0' else ''}"

                multiple_template[mult_name][prefix] = new_multiple_group

            # We can now add the template value to setting using the same setting name with prefix
            multiple_template[mult_name][prefix][setting]["value"] = value
            multiple_template[mult_name][prefix][setting]["prev_value"] = value
            multiple_template[mult_name][prefix][setting]["method"] = "default"

            # Sort key incrementally
            for mult_name, mult_settings in multiple_template.items():
                multiple_template[mult_name] = dict(sorted(mult_settings.items(), key=lambda item: int(item[0])))
    return multiple_template


def get_multiple_from_settings(settings, multiples):
    """
    We are gonna loop on each plugins multiples group, in case a setting is matching a service / global config setting,
    we will create a group using the prefix as key (or "0" if no prefix) with default settings at first.
    Then we will override by the service / global config value in case there is one.
    This will return something of this type :
    {'0' : {'setting' : value, 'setting2': value2}, '1' : {'setting_1': value, 'setting2_1': value}} }
    """

    # Loop on each plugin and loop on multiples key
    # Check if the name us matching a template key
    multiple_plugins = copy.deepcopy(multiples)

    multiple_settings = {}
    for setting, value in settings.items():
        # Sanitize setting name to remove prefix of type _1 if exists
        # Slipt by _ and check if last element is a digit
        format_setting = setting
        setting_split = setting.split("_")
        prefix = "0"
        if setting_split[-1].isdigit():
            prefix = setting_split[-1]
            format_setting = "_".join(setting_split[:-1])

        # loop on settings of a multiple group
        for mult_name, mult_settings in multiple_plugins.items():

            # Check if at least one settign is matching a multiple setting
            if not format_setting in mult_settings:
                continue

            # Case we have at least one multiple setting, we can check if multiple name exists or create it
            if not mult_name in multiple_settings:
                multiple_settings[mult_name] = {}
            # Now check if prefix exist for this mult
            if not prefix in multiple_settings[mult_name]:
                # We want each settings to have the prefix if exists
                # We will get the value of the setting without the prefix and create a prefix key with the same value
                # And after that we can delete the original setting
                new_multiple_group = {}
                for multSett, multValue in mult_settings.items():
                    new_multiple_group[f"{multSett}{f'_{prefix}' if prefix != '0' else ''}"] = multValue

                new_multiple_group = copy.deepcopy(new_multiple_group)

                # Update id for each settings
                for multSett, multValue in new_multiple_group.items():
                    multValue["id"] = f"{multValue['id']}{f'-{prefix}' if prefix != '0' else ''}"

                multiple_settings[mult_name][prefix] = new_multiple_group

            # Update multiple template with real data
            multiple_settings[mult_name][prefix][setting]["value"] = value.get("value", multiple_settings[mult_name][prefix][setting]["value"])
            multiple_settings[mult_name][prefix][setting]["prev_value"] = value.get("value", multiple_settings[mult_name][prefix][setting]["value"])
            multiple_settings[mult_name][prefix][setting]["method"] = value.get("method", "ui")
            multiple_settings[mult_name][prefix][setting]["disabled"] = False if value.get("method", "ui") in ("ui", "default", "manual") else True

            # Add popovers if setting is disabled else stop
            if not multiple_settings[mult_name][prefix][setting].get("disabled", False):
                continue

            multiple_settings[mult_name][prefix][setting]["popovers"] = [
                {
                    "iconName": "trespass",
                    "text": "inp_popover_method_disabled",
                }
            ] + multiple_settings[
                mult_name
            ][prefix][setting].get("popovers", [])

    return multiple_settings


def set_multiples(template, format_plugins, settings):
    """
    Set the multiples settings for each plugin.
    """
    # copy of format plugins
    for plugin in format_plugins:
        # Get multiples
        multiples = {}
        settings_to_delete = []
        total_settings = len(plugin.get("settings"))
        zindex = 0
        for setting, value in plugin.get("settings").items():

            if not value.get("multiple"):
                continue

            zindex += 1

            value["containerClass"] = f"z-{total_settings - zindex}"

            mult_name = value.get("multiple")
            # Get the multiple value and set it as key if not in multiples dict
            if mult_name not in multiples:
                multiples[mult_name] = {}

            multiples[mult_name][setting] = value
            settings_to_delete.append(setting)

        # Delete multiple settings from regular settings
        for setting in settings_to_delete:
            del plugin["settings"][setting]

        if len(multiples):
            # Add multiple schema with default values to plugin
            plugin["multiples_schema"] = multiples
            # Now that we have for each plugin the multiples settings, we need to do the following
            # Get all settings from template that are multiples
            template_multiples = get_multiple_from_template(template, multiples)
            # Get all settings from service settings / global config that are multiples
            service_multiples = get_multiple_from_settings(settings, multiples)
            # Get service multiples if at least one, else use template multiples
            plugin["multiples"] = service_multiples if len(service_multiples) else template_multiples

    return format_plugins


def format_setting(
    name: str,
    value: Union[str, int],
    total_settings: Union[str, int],
    loop_id: Union[str, int],
    template_settings: dict,
    settings: dict,
    is_new: bool = False,
) -> dict:
    """
    Format a setting in order to be used with form builder.
    This will only set value for none multiple settings.
    Additionnel set_multiples function will handle multiple settings.
    """

    is_multiple_setting = value.get("multiple", False)

    template_value, current_value, default_value, is_disabled_method, is_current_from_template, is_current_default, setting_value = get_setting_data(
        template_settings, settings, name, value, is_multiple_setting, is_new
    )  # regex by pattern

    value["pattern"] = value.get("regex", "")

    # set inpType based on type define for each settings
    inpType = (
        "checkbox"
        if value.get("type") == "check"
        else ("select" if value.get("type") == "select" else "datepicker" if value.get("type") == "date" else "input")
    )
    value["inpType"] = inpType

    if inpType == "select":
        # replace "select" key by "values"
        value["values"] = value.pop("select")

    value["columns"] = {"pc": 4, "tablet": 6, "mobile": 12}
    value["disabled"] = is_disabled_method
    value["value"] = default_value
    value["name"] = value.get("label")
    value["prev_value"] = value.get("value")

    # Prepare popover checking "help", "context"
    popovers = []

    if is_disabled_method:
        popovers.append(
            {
                "iconName": "trespass",
                "text": "inp_popover_method_disabled",
            }
        )

    if value.get("context"):
        popovers.append(
            {
                "iconName": ("disk" if value.get("context") == "multisite" else "globe"),
                "text": ("inp_popover_multisite" if value.get("context") == "multisite" else "inp_popover_global"),
            }
        )

    if value.get("help"):
        popovers.append(
            {
                "iconName": "info",
                "text": value.get("help"),
            }
        )

    value["popovers"] = popovers

    # Case multiple, stop here
    if "multiple" in value:
        return value

    # Else, we can add additionnal final data
    value["method"] = settings.get(name, {}).get("method", "ui")
    value["containerClass"] = f"z-{total_settings - loop_id}"

    if current_value is not None and not is_current_default:
        value["value"] = current_value
    elif template_value is not None:
        value["value"] = template_value
    else:
        value["value"] = setting_value

    return value
