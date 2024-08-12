import json
import base64

from pages.reports2 import reports_builder

reports = [
    {
        "date": 1723491739954,
        "ip": "127.0.0.1",
        "country": "EN",
        "method": "POST",
        "url": "/admin",
        "code": "400",
        "user_agent": "Mozilla/5.0",
        "reason": "antibot",
        "data": "lore ipsum ad vitam aeternam",
    },
    {
        "date": 1723491738000,
        "ip": "127.0.0.2",
        "country": "EN",
        "method": "GET",
        "url": "/etc?",
        "code": "300",
        "user_agent": "Mozilla/0.1",
        "reason": "unknown",
        "data": "",
    },
]

# define a set
countries = set()
methods = set()
codes = set()
reasons = set()
for report in reports:
    countries.add(report["country"])
    methods.add(report["method"])
    codes.add(report["code"])
    reasons.add(report["reason"])

# convert set to list
countries = list(countries)
methods = list(methods)
codes = list(codes)
reasons = list(reasons)

builder = reports_builder(reports, reasons, countries, methods, codes)

print("builder", builder)

with open("test_reports2.json", "w") as f:
    json.dump(builder, f, indent=4)

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("test_reports2.txt", "w") as f:
    f.write(output_base64_string)
