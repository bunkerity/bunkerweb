
import json


jobs = {'anonymous-report': {'plugin_id': 'misc', 'every': 'day', 'reload': False, 'success': True, 'last_run': '2024/06/14, 01:33:11 PM', 'cache': []}, 'backup-data': {'plugin_id': 'backup', 'every': 'day', 'reload': False, 'success': True, 'last_run': '2024/06/14, 01:33:10 PM', 'cache': []}, 'blacklist-download': {'plugin_id': 'blacklist', 'every': 'hour', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:09 PM', 'cache': []}, 'bunkernet-data': {'plugin_id': 'bunkernet', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:11 PM', 'cache': []}, 'bunkernet-register': {'plugin_id': 'bunkernet', 'every': 'hour', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:09 PM', 'cache': []}, 'certbot-new': {'plugin_id': 'letsencrypt', 'every': 'once', 'reload': False, 'success': True, 'last_run': '2024/06/14, 01:33:08 PM', 'cache': []}, 'certbot-renew': {'plugin_id': 'letsencrypt', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:09 PM', 'cache': []}, 'coreruleset-nightly': {'plugin_id': 'modsecurity', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:09 PM', 'cache': []}, 'custom-cert': {'plugin_id': 'customcert', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:10 PM', 'cache': []}, 'default-server-cert': {'plugin_id': 'misc', 'every': 'once', 'reload': False, 'success': True, 'last_run': '2024/06/14, 01:33:10 PM', 'cache': [{'service_id': None, 'file_name': 'default-server-cert.pem', 'last_update': '2024/06/14, 01:33:10 PM'}, {'service_id': None, 'file_name': 'default-server-cert.key', 'last_update': '2024/06/14, 01:33:10 PM'}]}, 'download-plugins': {'plugin_id': 'misc', 'every': 'once', 'reload': False, 'success': True, 'last_run': '2024/06/14, 01:33:13 PM', 'cache': []}, 'download-pro-plugins': {'plugin_id': 'pro', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:10 PM', 'cache': []}, 'failover-backup': {'plugin_id': 'jobs', 'every': 'once', 'reload': False, 'success': True, 'last_run': '2024/06/14, 01:33:16 PM', 'cache': [{'service_id': None, 'file_name': 'folder:/var/tmp/bunkerweb/failover.tgz', 'last_update': '2024/06/14, 01:33:27 PM'}]}, 'greylist-download': {'plugin_id': 'greylist', 'every': 'hour', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:09 PM', 'cache': []}, 'mmdb-asn': {'plugin_id': 'jobs', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:14 PM', 'cache': [{'service_id': None, 'file_name': 'asn.mmdb', 'last_update': '2024/06/14, 01:33:13 PM'}]}, 'mmdb-country': {'plugin_id': 'jobs', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:12 PM', 'cache': [{'service_id': None, 'file_name': 'country.mmdb', 'last_update': '2024/06/14, 01:33:11 PM'}]}, 'realip-download': {'plugin_id': 'realip', 'every': 'hour', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:09 PM', 'cache': []}, 'self-signed': {'plugin_id': 'selfsigned', 'every': 'day', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:10 PM', 'cache': [{'service_id': 'www.example.com', 'file_name': 'cert.pem', 'last_update': '2024/06/14, 01:33:10 PM'}, {'service_id': 'www.example.com', 'file_name': 'key.pem', 'last_update': '2024/06/14, 01:33:10 PM'}]}, 'update-check': {'plugin_id': 'jobs', 'every': 'day', 'reload': False, 'success': True, 'last_run': '2024/06/14, 01:33:15 PM', 'cache': []}, 'whitelist-download': {'plugin_id': 'whitelist', 'every': 'hour', 'reload': True, 'success': True, 'last_run': '2024/06/14, 01:33:09 PM', 'cache': []}}

def jobs_to_list(jobs):
    data = []
    # loop on each dict
    for key, value in jobs.items():
        item = []
        item.append({ 'type': 'Text', 'data': {'text' : key } })
        # loop on each value
        for k, v in value.items():
            # override widget type for some keys
            if k in ('reload', 'success'):
                item.append({ 'type': 'Icons', 'data': {"iconColor": "success" if v else "error", "iconName": "check" if v else "cross" } })
                continue
            
            if k in ("plugin_id", "every", "last_run"):
                item.append({ 'type': 'Text', 'data': {'text' : v } })
                continue


            if k in ("cache") and len(v) <= 0:
                item.append({ 'type': 'Text', 'data': {'text' : "No cache" } })
                continue


            if k in ("cache") and len(v) > 0:
                files = ["none"]
                # loop on each cache item
                for cache in v:
                    file_name = f"{cache['service_id']}/{cache['file_name']}" if cache['service_id'] else cache['file_name']
                    files.append(file_name)
                    
                item.append({ 'type': 'Fields', 'data': {
                                                'setting' : {
                                                    "id": f"{key}_cache",
                                                    "label": f"{key}_cache",
                                                    "hideLabel": True,
                                                    "inpType": "select",
                                                    "name": f"{key}_cache",
                                                    "value": "none",
                                                    "values": files,
                                                    "columns": {
                                                    "pc": 12,
                                                    "tablet": 12,
                                                    "mobile": 12,
                                                    },
                                                    "overflowAttrEl" : "data-table-body",
                                                    "containerClass" : "table",
                                                    "popovers": [
                                                    {
                                                        "iconColor": "info",
                                                        "iconName": "info",
                                                        "text": "jobs_download_cache_file",
                                                    },
                                                    ],
                                                }
                                            },
                                    })
                continue
        


        data.append(item)

        # store on a file 
    with open('jobs.json', 'w') as f:
        json.dump(data, f, indent=4)

            



jobs_to_list(jobs)