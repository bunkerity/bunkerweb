from utils import save_builder

from pages.configs import configs_builder


configs = [
    {
        "filename": "my-config-1",
        "config_type": "http",
        "is_global": False,
        "config_services": ["service1"],
    },
    {
        "filename": "my-config-1",
        "config_type": "http",
        "is_global": True,
        "config_services": [
            "service1",
            "service2",
            "service3",
            "service4",
            "service5",
            "service6",
            "services7",
            "service8",
            "service9",
            "service10",
            "services11",
        ],
    },
    {
        "filename": "my-config-2",
        "config_type": "https",
        "is_global": False,
        "config_services": ["service2"],
    },
]

config_types = ["http", "https", "socks4", "socks5"]
services = ["service1", "service2"]
builder = configs_builder(configs=configs, config_types=config_types, services=services)

save_builder(page_name="configs", output=builder, script_name="configs")
