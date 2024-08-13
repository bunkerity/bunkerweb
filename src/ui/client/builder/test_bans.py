from utils import save_builder
from pages.bans import bans_builder

bans = [
    {
        "ip": "127.0.0.1",
        "reason": "antibot",
        "ban_start_date": "",
        "ban_end_date": "",
        "remain": "hour(s)",
    },
    {
        "ip": "127.0.0.1",
        "reason": "test",
        "ban_start_date": "",
        "ban_end_date": "",
        "remain": "day(s)",
    },
    {
        "ip": "127.0.0.1",
        "reason": "antibot",
        "ban_start_date": "",
        "ban_end_date": "",
        "remain": "hour(s)",
    },
]

reasons = ["all", "antibot", "test"]
remains = ["all", "hour(s)", "day(s)"]

builder = bans_builder(bans, reasons, remains)

save_builder(page_name="bans", output=builder, script_name="bans")
