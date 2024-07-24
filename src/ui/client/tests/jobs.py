import json
import base64


def title_widget(title):
    return {
        "type": "Title",
        "data": {"title": title},
    }


def table_widget(positions, header, items, filters, minWidth, title):
    return {
        "type": "Table",
        "data": {
            "title": title,
            "minWidth": minWidth,
            "header": header,
            "positions": positions,
            "items": items,
            "filters": filters,
        },
    }


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


def get_jobs_list(jobs):
    data = []
    # loop on each dict
    for key, value in jobs.items():
        item = []
        item.append({"name": key, "type": "Text", "data": {"text": key}})
        # loop on each value
        for k, v in value.items():
            # override widget type for some keys
            if k in ("reload", "success"):
                item.append(
                    {
                        k: "success" if v else "failed",
                        "type": "Icons",
                        "data": {
                            "iconName": "check" if v else "cross",
                        },
                    }
                )
                continue

            if k in ("plugin_id", "every", "last_run"):
                item.append({k: v, "type": "Text", "data": {"text": v}})
                continue

            if k in ("cache") and len(v) <= 0:
                item.append({k: v, "type": "Text", "data": {"text": ""}})
                continue

            if k in ("cache") and len(v) > 0:
                files = []
                # loop on each cache item
                for cache in v:
                    file_name = f"{cache['file_name']} [{cache['service_id']}]" if cache["service_id"] else f"{cache['file_name']}"
                    files.append(file_name)

                item.append(
                    {
                        k: " ".join(files),
                        "type": "Fields",
                        "data": {
                            "setting": {
                                "attrs": {
                                    "data-plugin-id": value.get("plugin_id", ""),
                                    "data-job-name": key,
                                },
                                "id": f"{key}_cache",
                                "label": f"{key}_cache",
                                "hideLabel": True,
                                "inpType": "select",
                                "name": f"{key}_cache",
                                "value": "download file",
                                "values": files,
                                "columns": {
                                    "pc": 12,
                                    "tablet": 12,
                                    "mobile": 12,
                                },
                                "overflowAttrEl": "data-table-body",
                                "containerClass": "table download-cache-file",
                                "maxBtnChars": 12,
                                "popovers": [
                                    {
                                        "iconName": "info",
                                        "text": "jobs_download_cache_file",
                                    },
                                ],
                            }
                        },
                    }
                )
                continue

        data.append(item)

    return data


def jobs_builder(jobs):

    jobs_list = get_jobs_list(jobs)

    intervals = ["all"]

    # loop on each job
    for job in jobs_list:
        # loop on each item
        for item in job:
            # get the interval if not already in intervals
            if item.get("every") and item.get("every") not in intervals:
                intervals.append(item.get("every"))

    builder = [
        {
            "type": "card",
            "containerColumns": {"pc": 12, "tablet": 12, "mobile": 12},
            "widgets": [
                title_widget("jobs_title"),
                table_widget(
                    positions=[2, 2, 1, 1, 1, 2, 3],
                    header=[
                        "jobs_table_name",
                        "jobs_table_plugin_id",
                        "jobs_table_interval",
                        "jobs_table_reload",
                        "jobs_table_success",
                        "jobs_table_last_run_date",
                        "jobs_table_cache_downloadable",
                    ],
                    items=jobs_list,
                    filters=[
                        {
                            "filter": "table",
                            "filterName": "keyword",
                            "type": "keyword",
                            "value": "",
                            "keys": ["name", "plugin_id", "last_run"],
                            "field": {
                                "id": "jobs-keyword",
                                "value": "",
                                "type": "text",
                                "name": "jobs-keyword",
                                "label": "jobs_search",
                                "placeholder": "inp_keyword",
                                "isClipboard": False,
                                "popovers": [
                                    {
                                        "text": "jobs_search_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "every",
                            "type": "select",
                            "value": "all",
                            "keys": ["every"],
                            "field": {
                                "id": "jobs-every",
                                "value": "all",
                                "values": intervals,
                                "name": "jobs-every",
                                "onlyDown": True,
                                "label": "jobs_interval",
                                "popovers": [
                                    {
                                        "text": "jobs_interval_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "reload",
                            "type": "select",
                            "value": "all",
                            "keys": ["reload"],
                            "field": {
                                "id": "jobs-last-run",
                                "value": "all",
                                "values": ["all", "success", "failed"],
                                "name": "jobs-last-run",
                                "onlyDown": True,
                                "label": "jobs_reload",
                                "popovers": [
                                    {
                                        "text": "jobs_reload_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                        {
                            "filter": "table",
                            "filterName": "success",
                            "type": "select",
                            "value": "all",
                            "keys": ["success"],
                            "field": {
                                "id": "jobs-success",
                                "value": "all",
                                "values": ["all", "success", "failed"],
                                "name": "jobs-success",
                                "onlyDown": True,
                                "label": "jobs_success",
                                "popovers": [
                                    {
                                        "text": "jobs_success_desc",
                                        "iconName": "info",
                                    },
                                ],
                                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                            },
                        },
                    ],
                    minWidth="lg",
                    title="jobs_table_title",
                ),
            ],
        }
    ]
    return builder


output = jobs_builder(jobs)

# store on a file
with open("jobs.json", "w") as f:
    json.dump(output, f, indent=4)
output_base64_bytes = base64.b64encode(bytes(json.dumps(output), "utf-8"))
output_base64_string = output_base64_bytes.decode("ascii")

with open("jobs.txt", "w") as f:
    f.write(output_base64_string)
