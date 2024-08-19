from utils import save_builder

from pages.configs import configs_builder


configs = [
    {
        "filename": "my-config-1",
        "config_type": "http",
        "service": "service1",
    },
    {"filename": "my-config-1", "config_type": "http", "service": "global"},
    {
        "filename": "my-config-2",
        "config_type": "https",
        "service": "service2",
    },
]

config_types = ["http", "https", "socks4", "socks5"]
services = ["global", "service1", "service2"]  # global apply to all, else apply to specific service
builder = configs_builder(configs=configs, config_types=config_types, services=services)

save_builder(page_name="configs", output=builder, script_name="configs")
