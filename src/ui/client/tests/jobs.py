import json
import base64

from builder.jobs import jobs_builder


jobs = {
    "anonymous-report": {
        "plugin_id": "misc",
        "every": "day",
        "reload": False,
        "success": True,
        "last_run": "2024/06/14, 01:33:11 PM",
        "cache": [],
    },
    "backup-data": {
        "plugin_id": "backup",
        "every": "day",
        "reload": False,
        "success": True,
        "last_run": "2024/06/14, 01:33:10 PM",
        "cache": [],
    },
    "blacklist-download": {
        "plugin_id": "blacklist",
        "every": "hour",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:09 PM",
        "cache": [],
    },
    "bunkernet-data": {
        "plugin_id": "bunkernet",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:11 PM",
        "cache": [],
    },
    "bunkernet-register": {
        "plugin_id": "bunkernet",
        "every": "hour",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:09 PM",
        "cache": [],
    },
    "certbot-new": {
        "plugin_id": "letsencrypt",
        "every": "once",
        "reload": False,
        "success": True,
        "last_run": "2024/06/14, 01:33:08 PM",
        "cache": [],
    },
    "certbot-renew": {
        "plugin_id": "letsencrypt",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:09 PM",
        "cache": [],
    },
    "coreruleset-nightly": {
        "plugin_id": "modsecurity",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:09 PM",
        "cache": [],
    },
    "custom-cert": {
        "plugin_id": "customcert",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:10 PM",
        "cache": [],
    },
    "default-server-cert": {
        "plugin_id": "misc",
        "every": "once",
        "reload": False,
        "success": True,
        "last_run": "2024/06/14, 01:33:10 PM",
        "cache": [
            {
                "service_id": None,
                "file_name": "default-server-cert.pem",
                "last_update": "2024/06/14, 01:33:10 PM",
            },
            {
                "service_id": None,
                "file_name": "default-server-cert.key",
                "last_update": "2024/06/14, 01:33:10 PM",
            },
        ],
    },
    "download-plugins": {
        "plugin_id": "misc",
        "every": "once",
        "reload": False,
        "success": True,
        "last_run": "2024/06/14, 01:33:13 PM",
        "cache": [],
    },
    "download-pro-plugins": {
        "plugin_id": "pro",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:10 PM",
        "cache": [],
    },
    "failover-backup": {
        "plugin_id": "jobs",
        "every": "once",
        "reload": False,
        "success": True,
        "last_run": "2024/06/14, 01:33:16 PM",
        "cache": [
            {
                "service_id": None,
                "file_name": "folder:/var/tmp/bunkerweb/failover.tgz",
                "last_update": "2024/06/14, 01:33:27 PM",
            }
        ],
    },
    "greylist-download": {
        "plugin_id": "greylist",
        "every": "hour",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:09 PM",
        "cache": [],
    },
    "mmdb-asn": {
        "plugin_id": "jobs",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:14 PM",
        "cache": [
            {
                "service_id": None,
                "file_name": "asn.mmdb",
                "last_update": "2024/06/14, 01:33:13 PM",
            }
        ],
    },
    "mmdb-country": {
        "plugin_id": "jobs",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:12 PM",
        "cache": [
            {
                "service_id": None,
                "file_name": "country.mmdb",
                "last_update": "2024/06/14, 01:33:11 PM",
            }
        ],
    },
    "realip-download": {
        "plugin_id": "realip",
        "every": "hour",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:09 PM",
        "cache": [],
    },
    "self-signed": {
        "plugin_id": "selfsigned",
        "every": "day",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:10 PM",
        "cache": [
            {
                "service_id": "www.example.com",
                "file_name": "cert.pem",
                "last_update": "2024/06/14, 01:33:10 PM",
            },
            {
                "service_id": "www.example.com",
                "file_name": "key.pem",
                "last_update": "2024/06/14, 01:33:10 PM",
            },
        ],
    },
    "update-check": {
        "plugin_id": "jobs",
        "every": "day",
        "reload": False,
        "success": True,
        "last_run": "2024/06/14, 01:33:15 PM",
        "cache": [],
    },
    "whitelist-download": {
        "plugin_id": "whitelist",
        "every": "hour",
        "reload": True,
        "success": True,
        "last_run": "2024/06/14, 01:33:09 PM",
        "cache": [],
    },
}


output = jobs_builder(jobs)

# store on a file
with open("jobs.json", "w") as f:
    json.dump(output, f, indent=4)
output_base64_bytes = base64.b64encode(bytes(json.dumps(output), "utf-8"))
output_base64_string = output_base64_bytes.decode("ascii")

with open("jobs.txt", "w") as f:
    f.write(output_base64_string)
