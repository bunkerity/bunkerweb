from contextlib import suppress
from json import loads
from glob import glob
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for template module")


# Load and parse all BunkerWeb templates from the templates directory.
# Returns formatted template data with steps and settings for UI consumption and configuration wizard.
def get_ui_templates():
    if DEBUG_MODE:
        logger.debug("get_ui_templates() called - scanning for template files")
    
    ui_templates = []
    template_pattern = join(sep, "usr", "share", "bunkerweb", "templates", "*.json")
    template_files = glob(template_pattern)
    
    if DEBUG_MODE:
        logger.debug(f"Found {len(template_files)} template files to process")
    
    for template_file in template_files:
        if DEBUG_MODE:
            logger.debug(f"Processing template file: {template_file}")
        
        try:
            ui_template = {}
            with open(template_file, "r") as f:
                bw_template = loads(f.read())
            
            if DEBUG_MODE:
                logger.debug(f"Successfully loaded template: {bw_template.get('name', 'Unknown')}")
            
            # Extract basic template information
            ui_template = {
                "name": bw_template["name"], 
                "description": bw_template["description"]
            }
            ui_template["steps"] = []
            
            # Process template steps
            step_count = len(bw_template.get("steps", []))
            if DEBUG_MODE:
                logger.debug(f"Processing {step_count} steps for template: {ui_template['name']}")
            
            for step_index, bw_step in enumerate(bw_template["steps"]):
                ui_step = {}
                ui_step["name"] = bw_step["name"]
                ui_step["description"] = bw_step["description"]
                ui_step["settings"] = []
                
                # Process step settings
                setting_count = len(bw_step.get("settings", {}))
                if DEBUG_MODE:
                    logger.debug(f"Processing {setting_count} settings for step {step_index + 1}: {ui_step['name']}")
                
                for setting, value in bw_step["settings"].items():
                    ui_setting = {"setting_id": setting, "value": value}
                    ui_step["settings"].append(ui_setting)
                
                ui_template["steps"].append(ui_step)
            
            ui_templates.append(ui_template)
            
            if DEBUG_MODE:
                logger.debug(f"Successfully processed template: {ui_template['name']} with {len(ui_template['steps'])} steps")
                
        except Exception as e:
            logger.exception(f"Failed to process template file: {template_file}")
            # Continue processing other templates even if one fails
            continue
    
    if DEBUG_MODE:
        logger.debug(f"get_ui_templates() completed - returning {len(ui_templates)} valid templates")
    
    return ui_templates
