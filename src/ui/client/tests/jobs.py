import json
import base64

from builder.jobs import jobs_builder


jobs = {
    "anonymous-report": {
        "plugin_id": "misc",
        "every": "day",
        "reload": False,
        "history": [{"start_date": "07/08/2024, 01:10:03 PM", "end_date": "07/08/2024, 01:10:04 PM", "success": True}],
        "cache": [],
    },
    "backup-data": {
        "plugin_id": "backup",
        "every": "day",
        "reload": False,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "blacklist-download": {
        "plugin_id": "blacklist",
        "every": "hour",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:01 PM", "end_date": "07/08/2024, 01:10:02 PM", "success": True}],
        "cache": [],
    },
    "bunkernet-data": {
        "plugin_id": "bunkernet",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "bunkernet-register": {
        "plugin_id": "bunkernet",
        "every": "hour",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:02 PM", "success": True}],
        "cache": [],
    },
    "certbot-new": {
        "plugin_id": "letsencrypt",
        "every": "once",
        "reload": False,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "certbot-renew": {
        "plugin_id": "letsencrypt",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:03 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "cleanup-excess-jobs-runs": {
        "plugin_id": "db",
        "every": "day",
        "reload": False,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "coreruleset-nightly": {
        "plugin_id": "modsecurity",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:01 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "custom-cert": {
        "plugin_id": "customcert",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "default-server-cert": {
        "plugin_id": "misc",
        "every": "once",
        "reload": False,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [
            {
                "service_id": None,
                "file_name": "default-server-cert.pem",
                "last_update": "07/08/2024, 01:10:03 PM",
                "checksum": "203da9e16dabe522a3080c3b9efc5c2dc8054f47e98d995fe1812f4c498b4feb519ef080b7dfeaba0095c1393793815c23f22072daf5703b02762504b211db20",
            },
            {
                "service_id": None,
                "file_name": "default-server-cert.key",
                "last_update": "07/08/2024, 01:10:03 PM",
                "checksum": "7f86b1fffb8fe2011365d76e5a0955344a03c3bdb7b04aff13f8ad5b6178804290c0cd6c8f29dda9e981e3193cf5acda2a92f72312d514514305b8485667d573",
            },
        ],
    },
    "download-crs-plugins": {
        "plugin_id": "modsecurity",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:03 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "download-plugins": {
        "plugin_id": "misc",
        "every": "once",
        "reload": False,
        "history": [
            {"start_date": "07/08/2024, 01:10:04 PM", "end_date": "07/08/2024, 01:10:05 PM", "success": True},
            {"start_date": "07/08/2024, 01:09:59 PM", "end_date": "07/08/2024, 01:10:00 PM", "success": True},
        ],
        "cache": [],
    },
    "download-pro-plugins": {
        "plugin_id": "pro",
        "every": "day",
        "reload": True,
        "history": [
            {"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:04 PM", "success": True},
            {"start_date": "07/08/2024, 01:10:00 PM", "end_date": "07/08/2024, 01:10:01 PM", "success": False},
        ],
        "cache": [],
    },
    "failover-backup": {
        "plugin_id": "jobs",
        "every": "once",
        "reload": False,
        "history": [{"start_date": "07/08/2024, 01:10:07 PM", "end_date": "07/08/2024, 01:10:08 PM", "success": True}],
        "cache": [
            {
                "service_id": None,
                "file_name": "folder:/var/tmp/bunkerweb/failover.tgz",
                "last_update": "07/08/2024, 01:10:14 PM",
                "checksum": "d22a7a696d4b44bcef6a3ac06b2d7e2b2de128243000f58202c0e82b0bf54510ade7329eca14ca478a28d46201410ea1fd8002349b7b9aa51dd0d07d2fb2f51e",
            }
        ],
    },
    "greylist-download": {
        "plugin_id": "greylist",
        "every": "hour",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "mmdb-asn": {
        "plugin_id": "jobs",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:04 PM", "end_date": "07/08/2024, 01:10:06 PM", "success": True}],
        "cache": [
            {
                "service_id": None,
                "file_name": "asn.mmdb",
                "last_update": "07/08/2024, 01:10:05 PM",
                "checksum": "0beed65a84e63cf5dd6753ecc1aa6399dddaf5eb24fb22839f4cd72cbc9805cddf72be068649d111a3c21e2ac7de4a6f930c859286a25a7e937da017406d2596",
            }
        ],
    },
    "mmdb-country": {
        "plugin_id": "jobs",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:04 PM", "success": True}],
        "cache": [
            {
                "service_id": None,
                "file_name": "country.mmdb",
                "last_update": "07/08/2024, 01:10:03 PM",
                "checksum": "5f0d2e2c92840747886924adc1e6ff3668882990e0cd8a4d60750fe1bddb66c3e175c8717d073b48ebda41cce4c505d434dc2a6a469823fcd41c62c4f875b212",
            }
        ],
    },
    "realip-download": {
        "plugin_id": "realip",
        "every": "hour",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [],
    },
    "self-signed": {
        "plugin_id": "selfsigned",
        "every": "day",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:03 PM", "success": True}],
        "cache": [
            {
                "service_id": "www.example.com",
                "file_name": "cert.pem",
                "last_update": "07/08/2024, 01:10:03 PM",
                "checksum": "fc33700719f6a58336e3c3b735ad3fdf0b15ebd0afbe6b4a3b02a4a92e0ab4f1761409a7a1d1ca965d59b4196a81c1d150a12ae0170f7bb3a1bc7cf02300fbe9",
            },
            {
                "service_id": "www.example.com",
                "file_name": "key.pem",
                "last_update": "07/08/2024, 01:10:03 PM",
                "checksum": "0e6eee34ab7b2a41cb21e49ebd35ce29a1b8d12b55aad3911b6357c73792eef7084fbb4eeba8bff73eb7a8789b5f486f6edb6d4b1c38a54bd0dcee1bf438f23d",
            },
        ],
    },
    "update-check": {
        "plugin_id": "jobs",
        "every": "day",
        "reload": False,
        "history": [{"start_date": "07/08/2024, 01:10:06 PM", "end_date": "07/08/2024, 01:10:07 PM", "success": True}],
        "cache": [],
    },
    "whitelist-download": {
        "plugin_id": "whitelist",
        "every": "hour",
        "reload": True,
        "history": [{"start_date": "07/08/2024, 01:10:02 PM", "end_date": "07/08/2024, 01:10:02 PM", "success": True}],
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
