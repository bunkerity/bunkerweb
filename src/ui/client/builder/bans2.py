import json
import base64

from pages.bans2 import bans_builder

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
print("builder", builder)
with open("bans2.json", "w") as f:
    json.dump(builder, f, indent=4)

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("bans2.txt", "w") as f:
    f.write(output_base64_string)
