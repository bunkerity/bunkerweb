from json import loads
from glob import glob
from os import sep
from os.path import join


def get_ui_templates():
    ui_templates = []
    for template_file in glob(join(sep, "usr", "share", "bunkerweb", "templates", "*.json")):
        try:
            ui_template = {}
            with open(template_file, "r") as f:
                bw_template = loads(f.read())
            ui_template = {"name": bw_template["name"], "description": bw_template["description"]}
            ui_template["steps"] = []
            for bw_step in bw_template["steps"]:
                ui_step = {}
                ui_step["name"] = bw_step["name"]
                ui_step["description"] = bw_step["description"]
                ui_step["settings"] = []
                for setting, value in bw_step["settings"].items():
                    ui_setting = {"setting_id": setting, "value": value}
                    ui_step["settings"].append(ui_setting)
                ui_template["steps"].append(ui_step)
            ui_templates.append(ui_template)
        except Exception as e:
            # print(e)
            # TODO: log
            pass
    # print(ui_templates, flush=True)
    return ui_templates
