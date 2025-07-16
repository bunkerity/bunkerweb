from contextlib import suppress
from json import loads
from glob import glob
from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-template",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-template")


def get_ui_templates():
    logger.debug("get_ui_templates() called")
    ui_templates = []
    template_files = glob(join(sep, "usr", "share", "bunkerweb", "templates", "*.json"))
    logger.debug(f"Found {len(template_files)} template files")
    
    for template_file in template_files:
        logger.debug(f"Processing template: {template_file}")
        with suppress(BaseException):  # TODO: log exceptions
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
            logger.debug(f"Successfully processed template: {bw_template.get('name', 'unknown')}")
    # print(ui_templates, flush=True)
    logger.debug(f"Returning {len(ui_templates)} processed templates")
    return ui_templates
