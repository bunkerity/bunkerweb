from utils import save_builder

from pages.plugins import plugins_builder

plugins = [
    {"name": "plugin1", "version": "1.0.0", "description": "This is plugin1", "type": "core", "is_deletable": False, "page": "/mypage"},
    {"name": "plugin2", "version": "1.0.0", "description": "This is plugin2", "type": "external", "is_deletable": False, "page": "/mypag1"},
    {"name": "plugin3", "version": "1.0.0", "description": "This is plugin3", "type": "pro", "is_deletable": True, "page": ""},
    {"name": "plugin4", "version": "1.0.0", "description": "This is plugin4", "type": "pro", "is_deletable": True, "page": ""},
]

types = ["core", "external", "pro"]

output = plugins_builder(plugins)


builder = plugins_builder(plugins=plugins, types=types)

save_builder(page_name="plugins", output=builder, script_name="plugins")
