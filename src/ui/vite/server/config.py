dev_mode = True
API_URL = "http://localhost:1337"
app_name = "BunkerWeb UI API"
description = """# BunkerWeb Internal API Documentation

The BunkerWeb Internal API is designed to manage BunkerWeb's instances, communicate with a Database, and interact with various BunkerWeb services, including the scheduler, autoconf, and Web UI. This API provides the necessary endpoints for performing operations related to instance management, database communication, and service interaction.

## Authentication

If the API is configured to check the authentication token, the token must be provided in the request header. Each request should include an authentication token in the request header. The token can be set in the configuration file or as an environment variable (`CORE_TOKEN`).

Example:

```
Authorization: Bearer YOUR_AUTH_TOKEN
```

## Whitelist

If the API is configured to check the whitelist, the IP address of the client must be in the whitelist. The whitelist can be set in the configuration file or as an environment variable (`API_WHITELIST`). The whitelist can contain IP addresses and/or IP networks.
"""
summary = "The API used for UI to communicate with core API"
version = "1"
contact = {
        "name": "BunkerWeb Team",
        "url": "https://bunkerweb.io",
        "email": "contact@bunkerity.com",
    },
license_info = {
        "name": "GNU Affero General Public License v3.0",
        "identifier": "AGPL-3.0",
        "url": "https://github.com/bunkerity/bunkerweb/blob/master/LICENSE.md",
    },
openapi_tags  =  [  # TODO: Add more tags and better descriptions: https://fastapi.tiangolo.com/tutorial/metadata/?h=swagger#metadata-for-tags
    {
        "name": "misc",
        "description": "Miscellaneous operations",
    },
    {
        "name": "instances",
        "description": "Operations related to instance management",
    },
    {
        "name": "plugins",
        "description": "Operations related to plugin management",
    },
    {
        "name": "config",
        "description": "Operations related to configuration management",
    },
    {
        "name": "custom_configs",
        "description": "Operations related to custom configuration management",
    },
    {
        "name": "jobs",
        "description": "Operations related to job management",
    },
],
