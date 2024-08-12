from utils import save_builder

from pages.configs2 import configs_builder


configs = [
    {
        "filename": "my-config-1",
        "type": "http",
        "is_global": "no",
        "services": ["service1"],
    },
    {
        "filename": "my-config-1",
        "type": "http",
        "is_global": "yes",
        "services": ["service1", "service2"],
    },
    {
        "filename": "my-config-2",
        "type": "https",
        "is_global": "no",
        "services": ["service2"],
    },
]

config_types = ["http", "https", "socks4", "socks5"]

builder = configs_builder(configs, config_types)

save_builder("configs2", builder, update_page=False)
