# Settings

!!! info "Settings generator tool"

    To help you tune BunkerWeb, we have made an easy-to-use settings generator tool available at [config.bunkerweb.io](https://config.bunkerweb.io/?utm_campaign=self&utm_source=doc).

This section contains the full list of settings supported by BunkerWeb. If you are not yet familiar with BunkerWeb, you should first read the [concepts](concepts.md) section of the documentation. Please follow the instructions for your own [integration](integrations.md) on how to apply the settings.

As a general rule when multisite mode is enabled, if you want to apply settings with multisite context to a specific server, you will need to add the primary (first) server name as a prefix like `www.example.com_USE_ANTIBOT=captcha` or `myapp.example.com_USE_GZIP=yes` for example.

When settings are considered as "multiple", it means that you can have multiple groups of settings for the same feature by adding numbers as suffix like `REVERSE_PROXY_URL_1=/subdir`, `REVERSE_PROXY_HOST_1=http://myhost1`, `REVERSE_PROXY_URL_2=/anotherdir`, `REVERSE_PROXY_HOST_2=http://myhost2`, ... for example.

## Global settings


STREAM support :warning:

|           Setting            |                                                        Default                                                         | Context |Multiple|                                        Description                                         |
|------------------------------|------------------------------------------------------------------------------------------------------------------------|---------|--------|--------------------------------------------------------------------------------------------|
|`IS_LOADING`                  |`no`                                                                                                                    |global   |no      |Internal use : set to yes when BW is loading.                                               |
|`NGINX_PREFIX`                |`/etc/nginx/`                                                                                                           |global   |no      |Where nginx will search for configurations.                                                 |
|`HTTP_PORT`                   |`8080`                                                                                                                  |global   |no      |HTTP port number which bunkerweb binds to.                                                  |
|`HTTPS_PORT`                  |`8443`                                                                                                                  |global   |no      |HTTPS port number which bunkerweb binds to.                                                 |
|`MULTISITE`                   |`no`                                                                                                                    |global   |no      |Multi site activation.                                                                      |
|`SERVER_NAME`                 |`www.example.com`                                                                                                       |multisite|no      |List of the virtual hosts served by bunkerweb.                                              |
|`WORKER_PROCESSES`            |`auto`                                                                                                                  |global   |no      |Number of worker processes.                                                                 |
|`WORKER_RLIMIT_NOFILE`        |`2048`                                                                                                                  |global   |no      |Maximum number of open files for worker processes.                                          |
|`WORKER_CONNECTIONS`          |`1024`                                                                                                                  |global   |no      |Maximum number of connections per worker.                                                   |
|`LOG_FORMAT`                  |`$host $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"`|global   |no      |The format to use for access logs.                                                          |
|`LOG_LEVEL`                   |`notice`                                                                                                                |global   |no      |The level to use for error logs.                                                            |
|`DNS_RESOLVERS`               |`127.0.0.11`                                                                                                            |global   |no      |DNS addresses of resolvers to use.                                                          |
|`WORKERLOCK_MEMORY_SIZE`      |`48k`                                                                                                                   |global   |no      |Size of lua_shared_dict for initialization workers                                          |
|`DATASTORE_MEMORY_SIZE`       |`64m`                                                                                                                   |global   |no      |Size of the internal datastore.                                                             |
|`CACHESTORE_MEMORY_SIZE`      |`64m`                                                                                                                   |global   |no      |Size of the internal cachestore.                                                            |
|`CACHESTORE_IPC_MEMORY_SIZE`  |`16m`                                                                                                                   |global   |no      |Size of the internal cachestore (ipc).                                                      |
|`CACHESTORE_MISS_MEMORY_SIZE` |`16m`                                                                                                                   |global   |no      |Size of the internal cachestore (miss).                                                     |
|`CACHESTORE_LOCKS_MEMORY_SIZE`|`16m`                                                                                                                   |global   |no      |Size of the internal cachestore (locks).                                                    |
|`USE_API`                     |`yes`                                                                                                                   |global   |no      |Activate the API to control BunkerWeb.                                                      |
|`API_HTTP_PORT`               |`5000`                                                                                                                  |global   |no      |Listen port number for the API.                                                             |
|`API_LISTEN_IP`               |`0.0.0.0`                                                                                                               |global   |no      |Listen IP address for the API.                                                              |
|`API_SERVER_NAME`             |`bwapi`                                                                                                                 |global   |no      |Server name (virtual host) for the API.                                                     |
|`API_WHITELIST_IP`            |`127.0.0.0/8`                                                                                                           |global   |no      |List of IP/network allowed to contact the API.                                              |
|`AUTOCONF_MODE`               |`no`                                                                                                                    |global   |no      |Enable Autoconf Docker integration.                                                         |
|`SWARM_MODE`                  |`no`                                                                                                                    |global   |no      |Enable Docker Swarm integration.                                                            |
|`KUBERNETES_MODE`             |`no`                                                                                                                    |global   |no      |Enable Kubernetes integration.                                                              |

|`API_TIMEOUT`                 |`10`                                                                                                                   |global   |no      |Manually set the timeout for BunkerWeb API requests.                               |                                                      |
|`API_READ_TIMEOUT`            |`30`                                                                                                                   |global   |no      |Manually set the read timeout for BunkerWeb API requests.                                |

|`SERVER_TYPE`                 |`http`                                                                                                                  |multisite|no      |Server type : http or stream.                                                               |
|`LISTEN_STREAM`               |`yes`                                                                                                                   |multisite|no      |Enable listening for non-ssl (passthrough).                                                 |
|`LISTEN_STREAM_PORT`          |`1337`                                                                                                                  |multisite|no      |Listening port for non-ssl (passthrough).                                                   |
|`LISTEN_STREAM_PORT_SSL`      |`4242`                                                                                                                  |multisite|no      |Listening port for ssl (passthrough).                                                       |
|`USE_UDP`                     |`no`                                                                                                                    |multisite|no      |UDP listen instead of TCP (stream).                                                         |
|`USE_IPV6`                    |`no`                                                                                                                    |global   |no      |Enable IPv6 connectivity.                                                                   |
|`IS_DRAFT`                    |`no`                                                                                                                    |multisite|no      |Internal use : set to yes when the service is in draft mode.                                |
|`TIMERS_LOG_LEVEL`            |`debug`                                                                                                                 |global   |no      |Log level for timers.                                                                       |
|`OVERRIDE_INSTANCES`          |                                                                                                                        |global   |no      |List of BunkerWeb instances separated with spaces (format : fqdn-or-ip:5000 fqdn-or-ip:5000)|
|`DISABLE_CONFIGURATION_TESTING`                     |`no`                                                                                                                   |global   |no      |Disable sanity checks for all other environment variables.                                                      |

## Antibot

STREAM support :x:

Bot detection by using a challenge.

|          Setting          |  Default   | Context |Multiple|                                                         Description                                                          |
|---------------------------|------------|---------|--------|------------------------------------------------------------------------------------------------------------------------------|
|`USE_ANTIBOT`              |`no`        |multisite|no      |Activate antibot feature.                                                                                                     |
|`ANTIBOT_URI`              |`/challenge`|multisite|no      |Unused URI that clients will be redirected to to solve the challenge.                                                         |
|`ANTIBOT_TIME_RESOLVE`     |`60`        |multisite|no      |Maximum time (in seconds) clients have to resolve the challenge. Once this time has passed, a new challenge will be generated.|
|`ANTIBOT_TIME_VALID`       |`86400`     |multisite|no      |Maximum validity time of solved challenges. Once this time has passed, clients will need to resolve a new one.                |
|`ANTIBOT_RECAPTCHA_SCORE`  |`0.7`       |multisite|no      |Minimum score required for reCAPTCHA challenge (Only compatible with reCAPTCHA v3).                                           |
|`ANTIBOT_RECAPTCHA_SITEKEY`|            |multisite|no      |Sitekey for reCAPTCHA challenge.                                                                                              |
|`ANTIBOT_RECAPTCHA_SECRET` |            |multisite|no      |Secret for reCAPTCHA challenge.                                                                                               |
|`ANTIBOT_HCAPTCHA_SITEKEY` |            |multisite|no      |Sitekey for hCaptcha challenge.                                                                                               |
|`ANTIBOT_HCAPTCHA_SECRET`  |            |multisite|no      |Secret for hCaptcha challenge.                                                                                                |
|`ANTIBOT_TURNSTILE_SITEKEY`|            |multisite|no      |Sitekey for Turnstile challenge.                                                                                              |
|`ANTIBOT_TURNSTILE_SECRET` |            |multisite|no      |Secret for Turnstile challenge.                                                                                               |

## Auth basic

STREAM support :x:

Enforce login before accessing a resource or the whole site using HTTP basic auth method.

|       Setting       |     Default     | Context |Multiple|                  Description                   |
|---------------------|-----------------|---------|--------|------------------------------------------------|
|`USE_AUTH_BASIC`     |`no`             |multisite|no      |Use HTTP basic auth                             |
|`AUTH_BASIC_LOCATION`|`sitewide`       |multisite|no      |URL of the protected resource or sitewide value.|
|`AUTH_BASIC_USER`    |`changeme`       |multisite|no      |Username                                        |
|`AUTH_BASIC_PASSWORD`|`changeme`       |multisite|no      |Password                                        |
|`AUTH_BASIC_TEXT`    |`Restricted area`|multisite|no      |Text to display                                 |

## Backup

STREAM support :white_check_mark:

Backup your data to a custom location. Ensure the safety and availability of your important files by creating regular backups.

|     Setting      |          Default           |Context|Multiple|                     Description                      |
|------------------|----------------------------|-------|--------|------------------------------------------------------|
|`USE_BACKUP`      |`yes`                       |global |no      |Enable or disable the backup feature                  |
|`BACKUP_SCHEDULE` |`daily`                     |global |no      |The frequency of the backup (daily, weekly or monthly)|
|`BACKUP_ROTATION` |`7`                         |global |no      |The number of backups to keep                         |
|`BACKUP_DIRECTORY`|`/var/lib/bunkerweb/backups`|global |no      |The directory where the backup will be stored         |

## Backup S3 <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :white_check_mark:

Automatically backup your data to an S3 bucket

|           Setting           |Default|Context|Multiple|                Description                 |
|-----------------------------|-------|-------|--------|--------------------------------------------|
|`USE_BACKUP_S3`              |`no`   |global |no      |Enable or disable the S3 backup feature     |
|`BACKUP_S3_SCHEDULE`         |`daily`|global |no      |The frequency of the backup                 |
|`BACKUP_S3_ROTATION`         |`7`    |global |no      |The number of backups to keep               |
|`BACKUP_S3_ENDPOINT`         |       |global |no      |The S3 endpoint                             |
|`BACKUP_S3_BUCKET`           |       |global |no      |The S3 bucket                               |
|`BACKUP_S3_DIR`              |       |global |no      |The S3 directory                            |
|`BACKUP_S3_REGION`           |       |global |no      |The S3 region                               |
|`BACKUP_S3_ACCESS_KEY_ID`    |       |global |no      |The S3 access key ID                        |
|`BACKUP_S3_ACCESS_KEY_SECRET`|       |global |no      |The S3 access key secret                    |
|`BACKUP_S3_COMP_LEVEL`       |`6`    |global |no      |The compression level of the backup zip file|

## Bad behavior

STREAM support :white_check_mark:

Ban IP generating too much 'bad' HTTP status code in a period of time.

|          Setting          |           Default           | Context |Multiple|                                        Description                                         |
|---------------------------|-----------------------------|---------|--------|--------------------------------------------------------------------------------------------|
|`USE_BAD_BEHAVIOR`         |`yes`                        |multisite|no      |Activate Bad behavior feature.                                                              |
|`BAD_BEHAVIOR_STATUS_CODES`|`400 401 403 404 405 429 444`|multisite|no      |List of HTTP status codes considered as 'bad'.                                              |
|`BAD_BEHAVIOR_THRESHOLD`   |`10`                         |multisite|no      |Maximum number of 'bad' HTTP status codes within the period of time before IP is banned.    |
|`BAD_BEHAVIOR_COUNT_TIME`  |`60`                         |multisite|no      |Period of time (in seconds) during which we count 'bad' HTTP status codes.                  |
|`BAD_BEHAVIOR_BAN_TIME`    |`86400`                      |multisite|no      |The duration time (in seconds) of a ban when the corresponding IP has reached the threshold.|

## Blacklist

STREAM support :warning:

Deny access based on internal and external IP/network/rDNS/ASN blacklists.

|             Setting              |                                                           Default                                                            | Context |Multiple|                                                                                   Description                                                                                   |
|----------------------------------|------------------------------------------------------------------------------------------------------------------------------|---------|--------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`USE_BLACKLIST`                   |`yes`                                                                                                                         |multisite|no      |Activate blacklist feature.                                                                                                                                                      |
|`BLACKLIST_IP`                    |                                                                                                                              |multisite|no      |List of IP/network, separated with spaces, to block.                                                                                                                             |
|`BLACKLIST_RDNS`                  |`.shodan.io .censys.io`                                                                                                       |multisite|no      |List of reverse DNS suffixes, separated with spaces, to block.                                                                                                                   |
|`BLACKLIST_RDNS_GLOBAL`           |`yes`                                                                                                                         |multisite|no      |Only perform RDNS blacklist checks on global IP addresses.                                                                                                                       |
|`BLACKLIST_ASN`                   |                                                                                                                              |multisite|no      |List of ASN numbers, separated with spaces, to block.                                                                                                                            |
|`BLACKLIST_USER_AGENT`            |                                                                                                                              |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to block.                                                                                                                |
|`BLACKLIST_URI`                   |                                                                                                                              |multisite|no      |List of URI (PCRE regex), separated with spaces, to block.                                                                                                                       |
|`BLACKLIST_IGNORE_IP`             |                                                                                                                              |multisite|no      |List of IP/network, separated with spaces, to ignore in the blacklist.                                                                                                           |
|`BLACKLIST_IGNORE_RDNS`           |                                                                                                                              |multisite|no      |List of reverse DNS suffixes, separated with spaces, to ignore in the blacklist.                                                                                                 |
|`BLACKLIST_IGNORE_ASN`            |                                                                                                                              |multisite|no      |List of ASN numbers, separated with spaces, to ignore in the blacklist.                                                                                                          |
|`BLACKLIST_IGNORE_USER_AGENT`     |                                                                                                                              |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to ignore in the blacklist.                                                                                              |
|`BLACKLIST_IGNORE_URI`            |                                                                                                                              |multisite|no      |List of URI (PCRE regex), separated with spaces, to ignore in the blacklist.                                                                                                     |
|`BLACKLIST_IP_URLS`               |`https://www.dan.me.uk/torlist/?exit`                                                                                         |global   |no      |List of URLs, separated with spaces, containing bad IP/network to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                        |
|`BLACKLIST_RDNS_URLS`             |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                  |
|`BLACKLIST_ASN_URLS`              |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing ASN to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                                   |
|`BLACKLIST_USER_AGENT_URLS`       |`https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list`|global   |no      |List of URLs, separated with spaces, containing bad User-Agent to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                        |
|`BLACKLIST_URI_URLS`              |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing bad URI to block. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                               |
|`BLACKLIST_IGNORE_IP_URLS`        |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing IP/network to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.          |
|`BLACKLIST_IGNORE_RDNS_URLS`      |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.|
|`BLACKLIST_IGNORE_ASN_URLS`       |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing ASN to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                 |
|`BLACKLIST_IGNORE_USER_AGENT_URLS`|                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing User-Agent to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.          |
|`BLACKLIST_IGNORE_URI_URLS`       |                                                                                                                              |global   |no      |List of URLs, separated with spaces, containing URI to ignore in the blacklist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                 |

## Brotli

STREAM support :x:

Compress HTTP requests with the brotli algorithm.

|      Setting      |                                                                                                                                                                                                            Default                                                                                                                                                                                                             | Context |Multiple|                      Description                      |
|-------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|--------|-------------------------------------------------------|
|`USE_BROTLI`       |`no`                                                                                                                                                                                                                                                                                                                                                                                                                            |multisite|no      |Use brotli                                             |
|`BROTLI_TYPES`     |`application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml`|multisite|no      |List of MIME types that will be compressed with brotli.|
|`BROTLI_MIN_LENGTH`|`1000`                                                                                                                                                                                                                                                                                                                                                                                                                          |multisite|no      |Minimum length for brotli compression.                 |
|`BROTLI_COMP_LEVEL`|`6`                                                                                                                                                                                                                                                                                                                                                                                                                             |multisite|no      |The compression level of the brotli algorithm.         |

## BunkerNet

STREAM support :white_check_mark:

Share threat data with other BunkerWeb instances via BunkerNet.

|     Setting      |         Default          | Context |Multiple|         Description         |
|------------------|--------------------------|---------|--------|-----------------------------|
|`USE_BUNKERNET`   |`yes`                     |multisite|no      |Activate BunkerNet feature.  |
|`BUNKERNET_SERVER`|`https://api.bunkerweb.io`|global   |no      |Address of the BunkerNet API.|

## CORS

STREAM support :x:

Cross-Origin Resource Sharing.

|           Setting            |                                      Default                                       | Context |Multiple|                            Description                            |
|------------------------------|------------------------------------------------------------------------------------|---------|--------|-------------------------------------------------------------------|
|`USE_CORS`                    |`no`                                                                                |multisite|no      |Use CORS                                                           |
|`CORS_ALLOW_ORIGIN`           |`*`                                                                                 |multisite|no      |Allowed origins to make CORS requests : PCRE regex or *.           |
|`CORS_ALLOW_METHODS`          |`GET, POST, OPTIONS`                                                                |multisite|no      |Value of the Access-Control-Allow-Methods header.                  |
|`CORS_ALLOW_HEADERS`          |`DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range`|multisite|no      |Value of the Access-Control-Allow-Headers header.                  |
|`CORS_ALLOW_CREDENTIALS`      |`no`                                                                                |multisite|no      |Send the Access-Control-Allow-Credentials header.                  |
|`CORS_EXPOSE_HEADERS`         |`Content-Length,Content-Range`                                                      |multisite|no      |Value of the Access-Control-Expose-Headers header.                 |
|`CROSS_ORIGIN_OPENER_POLICY`  |                                                                                    |multisite|no      |Value for the Cross-Origin-Opener-Policy header.                   |
|`CROSS_ORIGIN_EMBEDDER_POLICY`|                                                                                    |multisite|no      |Value for the Cross-Origin-Embedder-Policy header.                 |
|`CROSS_ORIGIN_RESOURCE_POLICY`|                                                                                    |multisite|no      |Value for the Cross-Origin-Resource-Policy header.                 |
|`CORS_MAX_AGE`                |`86400`                                                                             |multisite|no      |Value of the Access-Control-Max-Age header.                        |
|`CORS_DENY_REQUEST`           |`yes`                                                                               |multisite|no      |Deny request and don't send it to backend if Origin is not allowed.|

## Client cache

STREAM support :x:

Manage caching for clients.

|         Setting         |                          Default                           | Context |Multiple|                            Description                             |
|-------------------------|------------------------------------------------------------|---------|--------|--------------------------------------------------------------------|
|`USE_CLIENT_CACHE`       |`no`                                                        |multisite|no      |Tell client to store locally static files.                          |
|`CLIENT_CACHE_EXTENSIONS`|`jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2`|global   |no      |List of file extensions, separated with pipes that should be cached.|
|`CLIENT_CACHE_ETAG`      |`yes`                                                       |multisite|no      |Send the HTTP ETag header for static resources.                     |
|`CLIENT_CACHE_CONTROL`   |`public, max-age=15552000`                                  |multisite|no      |Value of the Cache-Control HTTP header.                             |

## Country

STREAM support :white_check_mark:

Deny access based on the country of the client IP.

|      Setting      |Default| Context |Multiple|                                                 Description                                                  |
|-------------------|-------|---------|--------|--------------------------------------------------------------------------------------------------------------|
|`BLACKLIST_COUNTRY`|       |multisite|no      |Deny access if the country of the client is in the list (ISO 3166-1 alpha-2 format separated with spaces).    |
|`WHITELIST_COUNTRY`|       |multisite|no      |Deny access if the country of the client is not in the list (ISO 3166-1 alpha-2 format separated with spaces).|

## Custom HTTPS certificate

STREAM support :white_check_mark:

Choose custom certificate for HTTPS.

|       Setting        |Default| Context |Multiple|                                  Description                                   |
|----------------------|-------|---------|--------|--------------------------------------------------------------------------------|
|`USE_CUSTOM_SSL`      |`no`   |multisite|no      |Use custom HTTPS certificate.                                                   |
|`CUSTOM_SSL_CERT`     |       |multisite|no      |Full path of the certificate or bundle file (must be readable by the scheduler).|
|`CUSTOM_SSL_KEY`      |       |multisite|no      |Full path of the key file (must be readable by the scheduler).                  |
|`CUSTOM_SSL_CERT_DATA`|       |multisite|no      |Certificate data encoded in base64.                                             |
|`CUSTOM_SSL_KEY_DATA` |       |multisite|no      |Key data encoded in base64.                                                     |

## DB

STREAM support :white_check_mark:

Integrate easily the Database.

|        Setting        |                 Default                 |Context|Multiple|                                                               Description                                                               |
|-----------------------|-----------------------------------------|-------|--------|-----------------------------------------------------------------------------------------------------------------------------------------|
|`DATABASE_URI`         |`sqlite:////var/lib/bunkerweb/db.sqlite3`|global |no      |The database URI, following the sqlalchemy format.                                                                                       |
|`DATABASE_URI_READONLY`|                                         |global |no      |The database URI for read-only operations, it can also serve as a fallback if the main database is down. Following the sqlalchemy format.|
|`DATABASE_LOG_LEVEL`   |`warning`                                |global |no      |The level to use for database logs.                                                                                                      |

## DNSBL

STREAM support :white_check_mark:

Deny access based on external DNSBL servers.

|  Setting   |                                  Default                                   | Context |Multiple|      Description      |
|------------|----------------------------------------------------------------------------|---------|--------|-----------------------|
|`USE_DNSBL` |`yes`                                                                       |multisite|no      |Activate DNSBL feature.|
|`DNSBL_LIST`|`bl.blocklist.de problems.dnsbl.sorbs.net sbl.spamhaus.org xbl.spamhaus.org`|global   |no      |List of DNSBL servers. |

## Errors

STREAM support :x:

Manage default error pages

|         Setting         |                     Default                     | Context |Multiple|                                                      Description                                                       |
|-------------------------|-------------------------------------------------|---------|--------|------------------------------------------------------------------------------------------------------------------------|
|`ERRORS`                 |                                                 |multisite|no      |List of HTTP error code and corresponding error pages, separated with spaces (404=/my404.html 403=/errors/403.html ...).|
|`INTERCEPTED_ERROR_CODES`|`400 401 403 404 405 413 429 500 501 502 503 504`|multisite|no      |List of HTTP error code intercepted by BunkerWeb                                                                        |

## Greylist

STREAM support :warning:

Allow access while keeping security features based on internal and external IP/network/rDNS/ASN greylists.

|         Setting          |Default| Context |Multiple|                                                                                  Description                                                                                  |
|--------------------------|-------|---------|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`USE_GREYLIST`            |`no`   |multisite|no      |Activate greylist feature.                                                                                                                                                     |
|`GREYLIST_IP`             |       |multisite|no      |List of IP/network, separated with spaces, to put into the greylist.                                                                                                           |
|`GREYLIST_RDNS`           |       |multisite|no      |List of reverse DNS suffixes, separated with spaces, to put into the greylist.                                                                                                 |
|`GREYLIST_RDNS_GLOBAL`    |`yes`  |multisite|no      |Only perform RDNS greylist checks on global IP addresses.                                                                                                                      |
|`GREYLIST_ASN`            |       |multisite|no      |List of ASN numbers, separated with spaces, to put into the greylist.                                                                                                          |
|`GREYLIST_USER_AGENT`     |       |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to put into the greylist.                                                                                              |
|`GREYLIST_URI`            |       |multisite|no      |List of URI (PCRE regex), separated with spaces, to put into the greylist.                                                                                                     |
|`GREYLIST_IP_URLS`        |       |global   |no      |List of URLs, separated with spaces, containing good IP/network to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.     |
|`GREYLIST_RDNS_URLS`      |       |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.|
|`GREYLIST_ASN_URLS`       |       |global   |no      |List of URLs, separated with spaces, containing ASN to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                 |
|`GREYLIST_USER_AGENT_URLS`|       |global   |no      |List of URLs, separated with spaces, containing good User-Agent to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.     |
|`GREYLIST_URI_URLS`       |       |global   |no      |List of URLs, separated with spaces, containing bad URI to put into the greylist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.             |

## Gzip

STREAM support :x:

Compress HTTP requests with the gzip algorithm.

|     Setting     |                                                                                                                                                                                                            Default                                                                                                                                                                                                             | Context |Multiple|                     Description                     |
|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|--------|-----------------------------------------------------|
|`USE_GZIP`       |`no`                                                                                                                                                                                                                                                                                                                                                                                                                            |multisite|no      |Use gzip                                             |
|`GZIP_TYPES`     |`application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml`|multisite|no      |List of MIME types that will be compressed with gzip.|
|`GZIP_MIN_LENGTH`|`1000`                                                                                                                                                                                                                                                                                                                                                                                                                          |multisite|no      |Minimum length for gzip compression.                 |
|`GZIP_COMP_LEVEL`|`5`                                                                                                                                                                                                                                                                                                                                                                                                                             |multisite|no      |The compression level of the gzip algorithm.         |
|`GZIP_PROXIED`   |`no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                        |multisite|no      |Which kind of proxied requests we should compress.   |

## HTML injection

STREAM support :x:

Inject custom HTML code before the </body> tag.

|   Setting   |Default| Context |Multiple|      Description       |
|-------------|-------|---------|--------|------------------------|
|`INJECT_BODY`|       |multisite|no      |The HTML code to inject.|

## Headers

STREAM support :x:

Manage HTTP headers sent to clients.

|               Setting               |                                                                                                                                                                                                                                                                                                                                                       Default                                                                                                                                                                                                                                                                                                                                                       | Context |Multiple|                                         Description                                          |
|-------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|--------|----------------------------------------------------------------------------------------------|
|`CUSTOM_HEADER`                      |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |multisite|yes     |Custom header to add (HeaderName: HeaderValue).                                               |
|`REMOVE_HEADERS`                     |`Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |multisite|no      |Headers to remove (Header1 Header2 Header3 ...)                                               |
|`KEEP_UPSTREAM_HEADERS`              |`Content-Security-Policy Permissions-Policy Feature-Policy X-Frame-Options`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |multisite|no      |Headers to keep from upstream (Header1 Header2 Header3 ... or * for all).                     |
|`STRICT_TRANSPORT_SECURITY`          |`max-age=31536000`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |multisite|no      |Value for the Strict-Transport-Security header.                                               |
|`COOKIE_FLAGS`                       |`* HttpOnly SameSite=Lax`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |multisite|yes     |Cookie flags automatically added to all cookies (value accepted for nginx_cookie_flag_module).|
|`COOKIE_AUTO_SECURE_FLAG`            |`yes`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |multisite|no      |Automatically add the Secure flag to all cookies.                                             |
|`CONTENT_SECURITY_POLICY`            |`object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |multisite|no      |Value for the Content-Security-Policy header.                                                 |
|`CONTENT_SECURITY_POLICY_REPORT_ONLY`|`no`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |multisite|no      |Send reports for violations of the Content-Security-Policy header instead of blocking them.   |
|`REFERRER_POLICY`                    |`strict-origin-when-cross-origin`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |multisite|no      |Value for the Referrer-Policy header.                                                         |
|`PERMISSIONS_POLICY`                 |`accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), camera=(), cross-origin-isolated=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), geolocation=(), gyroscope=(), hid=(), idle-detection=(), magnetometer=(), microphone=(), midi=(), navigation-override=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), usb=(), web-share=(), xr-spatial-tracking=()`                                                                                                                                                                                   |multisite|no      |Value for the Permissions-Policy header.                                                      |
|`FEATURE_POLICY`                     |`accelerometer 'none'; ambient-light-sensor 'none'; autoplay 'none'; battery 'none'; camera 'none'; display-capture 'none'; document-domain 'none'; encrypted-media 'none'; execution-while-not-rendered 'none'; execution-while-out-of-viewport 'none'; fullscreen 'none'; geolocation 'none'; gyroscope 'none'; layout-animation 'none'; legacy-image-formats 'none'; magnetometer 'none'; microphone 'none'; midi 'none'; navigation-override 'none'; payment 'none'; picture-in-picture 'none'; publickey-credentials-get 'none'; speaker-selection 'none'; sync-xhr 'none'; unoptimized-images 'none'; unsized-media 'none'; usb 'none'; screen-wake-lock 'none'; web-share 'none'; xr-spatial-tracking 'none';`|multisite|no      |Value for the Feature-Policy header.                                                          |
|`X_FRAME_OPTIONS`                    |`SAMEORIGIN`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |multisite|no      |Value for the X-Frame-Options header.                                                         |
|`X_CONTENT_TYPE_OPTIONS`             |`nosniff`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |multisite|no      |Value for the X-Content-Type-Options header.                                                  |
|`X_XSS_PROTECTION`                   |`1; mode=block`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |multisite|no      |Value for the X-XSS-Protection header.                                                        |

## Let's Encrypt

STREAM support :white_check_mark:

Automatic creation, renewal and configuration of Let's Encrypt certificates.

|           Setting            |Default| Context |Multiple|                                                                                 Description                                                                                 |
|------------------------------|-------|---------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`AUTO_LETS_ENCRYPT`           |`no`   |multisite|no      |Activate automatic Let's Encrypt mode.                                                                                                                                       |
|`EMAIL_LETS_ENCRYPT`          |       |multisite|no      |Email used for Let's Encrypt notification and in certificate.                                                                                                                |
|`USE_LETS_ENCRYPT_STAGING`    |`no`   |multisite|no      |Use the staging environment for Let’s Encrypt certificate generation. Useful when you are testing your deployments to avoid being rate limited in the production environment.|
|`LETS_ENCRYPT_CLEAR_OLD_CERTS`|`no`   |global   |no      |Clear old certificates when renewing.                                                                                                                                        |

## Let's Encrypt DNS <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :white_check_mark:

Automatic creation, renewal and configuration of Let's Encrypt certificates using DNS challenges.

|             Setting              | Default | Context |Multiple|                                                        Description                                                         |
|----------------------------------|---------|---------|--------|----------------------------------------------------------------------------------------------------------------------------|
|`AUTO_LETS_ENCRYPT_DNS`           |`no`     |multisite|no      |Activate automatic Let's Encrypt DNS.                                                                                       |
|`LETS_ENCRYPT_DNS_EMAIL`          |         |multisite|no      |The email address to use for Let's Encrypt notifications.                                                                   |
|`USE_LETS_ENCRYPT_DNS_STAGING`    |`no`     |multisite|no      |Use the Let's Encrypt staging environment.                                                                                  |
|`LETS_ENCRYPT_DNS_PROVIDER`       |         |multisite|no      |The DNS provider to use for DNS challenges.                                                                                 |
|`USE_LETS_ENCRYPT_DNS_WILDCARD`   |`yes`    |multisite|no      |Create wildcard certificates for all domains using DNS challenges.                                                          |
|`LETS_ENCRYPT_DNS_PROPAGATION`    |`default`|multisite|no      |The time to wait for DNS propagation in seconds.                                                                            |
|`LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`|         |multisite|yes     |Configuration item that will be added to the credentials.ini file for the DNS provider (e.g. 'cloudflare_api_token 123456').|
|`LETS_ENCRYPT_DNS_CLEAR_OLD_CERTS`|`no`     |global   |no      |Clear old certificates when renewing.                                                                                       |

## Limit

STREAM support :warning:

Limit maximum number of requests and connections.

|        Setting        |Default| Context |Multiple|                                         Description                                         |
|-----------------------|-------|---------|--------|---------------------------------------------------------------------------------------------|
|`USE_LIMIT_REQ`        |`yes`  |multisite|no      |Activate limit requests feature.                                                             |
|`LIMIT_REQ_URL`        |`/`    |multisite|yes     |URL (PCRE regex) where the limit request will be applied or special value / for all requests.|
|`LIMIT_REQ_RATE`       |`2r/s` |multisite|yes     |Rate to apply to the URL (s for second, m for minute, h for hour and d for day).             |
|`USE_LIMIT_CONN`       |`yes`  |multisite|no      |Activate limit connections feature.                                                          |
|`LIMIT_CONN_MAX_HTTP1` |`10`   |multisite|no      |Maximum number of connections per IP when using HTTP/1.X protocol.                           |
|`LIMIT_CONN_MAX_HTTP2` |`100`  |multisite|no      |Maximum number of streams per IP when using HTTP/2 protocol.                                 |
|`LIMIT_CONN_MAX_STREAM`|`10`   |multisite|no      |Maximum number of connections per IP when using stream.                                      |

## Metrics

STREAM support :warning:

Metrics collection and retrieve.

|           Setting            |Default| Context |Multiple|                       Description                       |
|------------------------------|-------|---------|--------|---------------------------------------------------------|
|`USE_METRICS`                 |`yes`  |multisite|no      |Enable collection and retrieval of internal metrics.     |
|`METRICS_MEMORY_SIZE`         |`16m`  |global   |no      |Size of the internal storage for metrics.                |
|`METRICS_MAX_BLOCKED_REQUESTS`|`100`  |global   |no      |Maximum number of blocked requests to store (per worker).|

## Migration <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :white_check_mark:

Migration of BunkerWeb configuration between instances made easy via the web UI

## Miscellaneous

STREAM support :warning:

Miscellaneous settings.

|              Setting              |        Default        | Context |Multiple|                                                         Description                                                         |
|-----------------------------------|-----------------------|---------|--------|-----------------------------------------------------------------------------------------------------------------------------|
|`DISABLE_DEFAULT_SERVER`           |`no`                   |global   |no      |Deny HTTP request if the request vhost is unknown.                                                                           |
|`DISABLE_DEFAULT_SERVER_STRICT_SNI`|`no`                   |global   |no      |Close SSL/TLS connection if the SNI is unknown.                                                                              |
|`REDIRECT_HTTP_TO_HTTPS`           |`no`                   |multisite|no      |Redirect all HTTP request to HTTPS.                                                                                          |
|`AUTO_REDIRECT_HTTP_TO_HTTPS`      |`yes`                  |multisite|no      |Try to detect if HTTPS is used and activate HTTP to HTTPS redirection if that's the case.                                    |
|`ALLOWED_METHODS`                  |`GET|POST|HEAD`        |multisite|no      |Allowed HTTP and WebDAV methods, separated with pipes to be sent by clients.                                                 |
|`MAX_CLIENT_SIZE`                  |`10m`                  |multisite|no      |Maximum body size (0 for infinite).                                                                                          |
|`SERVE_FILES`                      |`yes`                  |multisite|no      |Serve files from the local folder.                                                                                           |
|`ROOT_FOLDER`                      |                       |multisite|no      |Root folder containing files to serve (/var/www/html/{server_name} if unset).                                                |
|`SSL_PROTOCOLS`                    |`TLSv1.2 TLSv1.3`      |multisite|no      |The supported version of TLS. We recommend the default value TLSv1.2 TLSv1.3 for compatibility reasons.                      |
|`HTTP2`                            |`yes`                  |multisite|no      |Support HTTP2 protocol when HTTPS is enabled.                                                                                |
|`HTTP3`                            |`no`                   |multisite|no      |Support HTTP3 protocol when HTTPS is enabled.                                                                                |
|`HTTP3_ALT_SVC_PORT`               |`443`                  |multisite|no      |HTTP3 alternate service port. This value will be used as part of the Alt-Svc header.                                         |
|`LISTEN_HTTP`                      |`yes`                  |multisite|no      |Respond to (insecure) HTTP requests.                                                                                         |
|`USE_OPEN_FILE_CACHE`              |`no`                   |multisite|no      |Enable open file cache feature                                                                                               |
|`OPEN_FILE_CACHE`                  |`max=1000 inactive=20s`|multisite|no      |Open file cache directive                                                                                                    |
|`OPEN_FILE_CACHE_ERRORS`           |`yes`                  |multisite|no      |Enable open file cache for errors                                                                                            |
|`OPEN_FILE_CACHE_MIN_USES`         |`2`                    |multisite|no      |Enable open file cache minimum uses                                                                                          |
|`OPEN_FILE_CACHE_VALID`            |`30s`                  |multisite|no      |Open file cache valid time                                                                                                   |
|`EXTERNAL_PLUGIN_URLS`             |                       |global   |no      |List of external plugins URLs (direct download to .zip or .tar file) to download and install (URLs are separated with space).|
|`DENY_HTTP_STATUS`                 |`403`                  |global   |no      |HTTP status code to send when the request is denied (403 or 444). When using 444, BunkerWeb will close the connection.       |
|`SEND_ANONYMOUS_REPORT`            |`yes`                  |global   |no      |Send anonymous report to BunkerWeb maintainers.                                                                              |

## ModSecurity

STREAM support :x:

Management of the ModSecurity WAF.

|             Setting             |   Default    | Context |Multiple|                                 Description                                 |
|---------------------------------|--------------|---------|--------|-----------------------------------------------------------------------------|
|`USE_MODSECURITY`                |`yes`         |multisite|no      |Enable ModSecurity WAF.                                                      |
|`USE_MODSECURITY_CRS`            |`yes`         |multisite|no      |Enable OWASP Core Rule Set.                                                  |
|`MODSECURITY_CRS_VERSION`        |`3`           |multisite|no      |Version of the OWASP Core Rule Set to use with ModSecurity (3, 4 or nightly).|
|`MODSECURITY_SEC_AUDIT_ENGINE`   |`RelevantOnly`|multisite|no      |SecAuditEngine directive of ModSecurity.                                     |
|`MODSECURITY_SEC_RULE_ENGINE`    |`On`          |multisite|no      |SecRuleEngine directive of ModSecurity.                                      |
|`MODSECURITY_SEC_AUDIT_LOG_PARTS`|`ABCFHZ`      |multisite|no      |SecAuditLogParts directive of ModSecurity.                                   |

## Monitoring <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

BunkerWeb monitoring pro system. This plugin is a prerequisite for some other plugins.

|           Setting            |Default|Context|Multiple|                                Description                                |
|------------------------------|-------|-------|--------|---------------------------------------------------------------------------|
|`USE_MONITORING`              |`yes`  |global |no      |Enable monitoring of BunkerWeb.                                            |
|`MONITORING_METRICS_DICT_SIZE`|`10M`  |global |no      |Size of the dict to store monitoring metrics.                              |
|`MONITORING_IGNORE_URLS`      |       |global |no      |List of URLs to ignore when monitoring separated with spaces (e.g. /health)|

## PHP

STREAM support :x:

Manage local or remote PHP-FPM.

|     Setting     |Default| Context |Multiple|                        Description                         |
|-----------------|-------|---------|--------|------------------------------------------------------------|
|`REMOTE_PHP`     |       |multisite|no      |Hostname of the remote PHP-FPM instance.                    |
|`REMOTE_PHP_PATH`|       |multisite|no      |Root folder containing files in the remote PHP-FPM instance.|
|`LOCAL_PHP`      |       |multisite|no      |Path to the PHP-FPM socket file.                            |
|`LOCAL_PHP_PATH` |       |multisite|no      |Root folder containing files in the local PHP-FPM instance. |

## Pro

STREAM support :x:

Pro settings for the Pro version of BunkerWeb.

|     Setting     |Default|Context|Multiple|                   Description                   |
|-----------------|-------|-------|--------|-------------------------------------------------|
|`PRO_LICENSE_KEY`|       |global |no      |The License Key for the Pro version of BunkerWeb.|

## Prometheus exporter <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Prometheus exporter for BunkerWeb internal metrics.

|           Setting            |                       Default                       |Context|Multiple|                              Description                               |
|------------------------------|-----------------------------------------------------|-------|--------|------------------------------------------------------------------------|
|`USE_PROMETHEUS_EXPORTER`     |`no`                                                 |global |no      |Enable the Prometheus export.                                           |
|`PROMETHEUS_EXPORTER_IP`      |`0.0.0.0`                                            |global |no      |Listening IP of the Prometheus exporter.                                |
|`PROMETHEUS_EXPORTER_PORT`    |`9113`                                               |global |no      |Listening port of the Prometheus exporter.                              |
|`PROMETHEUS_EXPORTER_URL`     |`/metrics`                                           |global |no      |HTTP URL of the Prometheus exporter.                                    |
|`PROMETHEUS_EXPORTER_ALLOW_IP`|`127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16`|global |no      |List of IP/networks allowed to contact the Prometheus exporter endpoint.|

## Real IP

STREAM support :warning:

Get real IP of clients when BunkerWeb is behind a reverse proxy / load balancer.

|      Setting       |                 Default                 | Context |Multiple|                                                                                       Description                                                                                       |
|--------------------|-----------------------------------------|---------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`USE_REAL_IP`       |`no`                                     |multisite|no      |Retrieve the real IP of client.                                                                                                                                                          |
|`USE_PROXY_PROTOCOL`|`no`                                     |multisite|no      |Enable PROXY protocol communication.                                                                                                                                                     |
|`REAL_IP_FROM`      |`192.168.0.0/16 172.16.0.0/12 10.0.0.0/8`|multisite|no      |List of trusted IPs / networks, separated with spaces, where proxied requests come from.                                                                                                 |
|`REAL_IP_HEADER`    |`X-Forwarded-For`                        |multisite|no      |HTTP header containing the real IP or special value proxy_protocol for PROXY protocol.                                                                                                   |
|`REAL_IP_RECURSIVE` |`yes`                                    |multisite|no      |Perform a recursive search in the header container IP address.                                                                                                                           |
|`REAL_IP_FROM_URLS` |                                         |global   |no      |List of URLs containing trusted IPs / networks, separated with spaces, where proxied requests come from. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.|

## Redirect

STREAM support :x:

Manage HTTP redirects.

|         Setting         |Default| Context |Multiple|                   Description                   |
|-------------------------|-------|---------|--------|-------------------------------------------------|
|`REDIRECT_TO`            |       |multisite|no      |Redirect a whole site to another one.            |
|`REDIRECT_TO_REQUEST_URI`|`no`   |multisite|no      |Append the requested URI to the redirect address.|
|`REDIRECT_TO_STATUS_CODE`|`301`  |multisite|no      |Status code to send to client when redirecting.  |

## Redis

STREAM support :white_check_mark:

Redis server configuration when using BunkerWeb in cluster mode.

|         Setting         |Default|Context|Multiple|                            Description                            |
|-------------------------|-------|-------|--------|-------------------------------------------------------------------|
|`USE_REDIS`              |`no`   |global |no      |Activate Redis.                                                    |
|`REDIS_HOST`             |       |global |no      |Redis server IP or hostname.                                       |
|`REDIS_PORT`             |`6379` |global |no      |Redis server port.                                                 |
|`REDIS_DATABASE`         |`0`    |global |no      |Redis database number.                                             |
|`REDIS_SSL`              |`no`   |global |no      |Use SSL/TLS connection with Redis server.                          |
|`REDIS_SSL_VERIFY`       |`no`   |global |no      |Verify the certificate of Redis server.                            |
|`REDIS_TIMEOUT`          |`1000` |global |no      |Redis server timeout (in ms) for connect, read and write.          |
|`REDIS_USERNAME`         |       |global |no      |Redis username used in AUTH command.                               |
|`REDIS_PASSWORD`         |       |global |no      |Redis password used in AUTH command.                               |
|`REDIS_SENTINEL_HOSTS`   |       |global |no      |Redis sentinel hosts with format host:[port] separated with spaces.|
|`REDIS_SENTINEL_USERNAME`|       |global |no      |Redis sentinel username.                                           |
|`REDIS_SENTINEL_PASSWORD`|       |global |no      |Redis sentinel password.                                           |
|`REDIS_SENTINEL_MASTER`  |       |global |no      |Redis sentinel master name.                                        |
|`REDIS_KEEPALIVE_IDLE`   |`30000`|global |no      |Max idle time (in ms) before closing redis connection in the pool. |
|`REDIS_KEEPALIVE_POOL`   |`10`   |global |no      |Max number of redis connection(s) kept in the pool.                |

## Reporting <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Regular reporting of important data from BunkerWeb (global, attacks, bans, requests, reasons, AS...). Monitoring pro plugin needed to work.

|           Setting            |     Default      |Context|Multiple|                                                           Description                                                            |
|------------------------------|------------------|-------|--------|----------------------------------------------------------------------------------------------------------------------------------|
|`USE_REPORTING_SMTP`          |`no`              |global |no      |Enable sending the report via email.                                                                                              |
|`USE_REPORTING_WEBHOOK`       |`no`              |global |no      |Enable sending the report via webhook.                                                                                            |
|`REPORTING_SCHEDULE`          |`weekly`          |global |no      |The frequency at which reports are sent.                                                                                          |
|`REPORTING_WEBHOOK_URLS`      |                  |global |no      |List of webhook URLs to receive the report in Markdown (separated by spaces).                                                     |
|`REPORTING_SMTP_EMAILS`       |                  |global |no      |List of email addresses to receive the report in HTML format (separated by spaces).                                               |
|`REPORTING_SMTP_HOST`         |                  |global |no      |The host server used for SMTP sending.                                                                                            |
|`REPORTING_SMTP_PORT`         |`465`             |global |no      |The port used for SMTP. Please note that there are different standards depending on the type of connection (SSL = 465, TLS = 587).|
|`REPORTING_SMTP_FROM_EMAIL`   |                  |global |no      |The email address used as the sender. Note that 2FA must be disabled for this email address.                                      |
|`REPORTING_SMTP_FROM_USER`    |                  |global |no      |The user authentication value for sending via the from email address.                                                             |
|`REPORTING_SMTP_FROM_PASSWORD`|                  |global |no      |The password authentication value for sending via the from email address.                                                         |
|`REPORTING_SMTP_SSL`          |`SSL`             |global |no      |Determine whether or not to use a secure connection for SMTP.                                                                     |
|`REPORTING_SMTP_SUBJECT`      |`BunkerWeb Report`|global |no      |The subject line of the email.                                                                                                    |

## Reverse proxy

STREAM support :warning:

Manage reverse proxy configurations.

|                Setting                |             Default              | Context |Multiple|                                                         Description                                                         |
|---------------------------------------|----------------------------------|---------|--------|-----------------------------------------------------------------------------------------------------------------------------|
|`USE_REVERSE_PROXY`                    |`no`                              |multisite|no      |Activate reverse proxy mode.                                                                                                 |
|`REVERSE_PROXY_INTERCEPT_ERRORS`       |`yes`                             |multisite|no      |Intercept and rewrite errors.                                                                                                |
|`REVERSE_PROXY_CUSTOM_HOST`            |                                  |multisite|no      |Override Host header sent to upstream server.                                                                                |
|`REVERSE_PROXY_SSL_SNI`                |`no`                              |multisite|no      |Enable or disable sending SNI to upstream server.                                                                            |
|`REVERSE_PROXY_SSL_SNI_NAME`           |                                  |multisite|no      |Sets the SNI host to send to upstream server.                                                                                |
|`REVERSE_PROXY_HOST`                   |                                  |multisite|yes     |Full URL of the proxied resource (proxy_pass).                                                                               |
|`REVERSE_PROXY_URL`                    |`/`                               |multisite|yes     |Location URL that will be proxied.                                                                                           |
|`REVERSE_PROXY_WS`                     |`no`                              |multisite|yes     |Enable websocket on the proxied resource.                                                                                    |
|`REVERSE_PROXY_HEADERS`                |                                  |multisite|yes     |List of HTTP headers to send to proxied resource separated with semicolons (values for proxy_set_header directive).          |
|`REVERSE_PROXY_HEADERS_CLIENT`         |                                  |multisite|yes     |List of HTTP headers to send to client separated with semicolons (values for add_header directive).                          |
|`REVERSE_PROXY_BUFFERING`              |`yes`                             |multisite|yes     |Enable or disable buffering of responses from proxied resource.                                                              |
|`REVERSE_PROXY_KEEPALIVE`              |`no`                              |multisite|yes     |Enable or disable keepalive connections with the proxied resource.                                                           |
|`REVERSE_PROXY_AUTH_REQUEST`           |                                  |multisite|yes     |Enable authentication using an external provider (value of auth_request directive).                                          |
|`REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL`|                                  |multisite|yes     |Redirect clients to sign-in URL when using REVERSE_PROXY_AUTH_REQUEST (used when auth_request call returned 401).            |
|`REVERSE_PROXY_AUTH_REQUEST_SET`       |                                  |multisite|yes     |List of variables to set from the authentication provider, separated with semicolons (values of auth_request_set directives).|
|`REVERSE_PROXY_CONNECT_TIMEOUT`        |`60s`                             |multisite|yes     |Timeout when connecting to the proxied resource.                                                                             |
|`REVERSE_PROXY_READ_TIMEOUT`           |`60s`                             |multisite|yes     |Timeout when reading from the proxied resource.                                                                              |
|`REVERSE_PROXY_SEND_TIMEOUT`           |`60s`                             |multisite|yes     |Timeout when sending to the proxied resource.                                                                                |
|`REVERSE_PROXY_INCLUDES`               |                                  |multisite|yes     |Additional configuration to include in the location block, separated with spaces.                                            |
|`USE_PROXY_CACHE`                      |`no`                              |multisite|no      |Enable or disable caching of the proxied resources.                                                                          |
|`PROXY_CACHE_PATH_LEVELS`              |`1:2`                             |global   |no      |Hierarchy levels of the cache.                                                                                               |
|`PROXY_CACHE_PATH_ZONE_SIZE`           |`10m`                             |global   |no      |Maximum size of cached metadata when caching proxied resources.                                                              |
|`PROXY_CACHE_PATH_PARAMS`              |`max_size=100m`                   |global   |no      |Additional parameters to add to the proxy_cache directive.                                                                   |
|`PROXY_CACHE_METHODS`                  |`GET HEAD`                        |multisite|no      |HTTP methods that should trigger a cache operation.                                                                          |
|`PROXY_CACHE_MIN_USES`                 |`2`                               |multisite|no      |The minimum number of requests before a response is cached.                                                                  |
|`PROXY_CACHE_KEY`                      |`$scheme$host$request_uri`        |multisite|no      |The key used to uniquely identify a cached response.                                                                         |
|`PROXY_CACHE_VALID`                    |`200=24h 301=1h 302=24h`          |multisite|no      |Define the caching time depending on the HTTP status code (list of status=time), separated with spaces.                      |
|`PROXY_NO_CACHE`                       |`$http_pragma $http_authorization`|multisite|no      |Conditions to disable caching of responses.                                                                                  |
|`PROXY_CACHE_BYPASS`                   |`0`                               |multisite|no      |Conditions to bypass caching of responses.                                                                                   |

## Reverse scan

STREAM support :white_check_mark:

Scan clients ports to detect proxies or servers.

|       Setting        |         Default          | Context |Multiple|                           Description                            |
|----------------------|--------------------------|---------|--------|------------------------------------------------------------------|
|`USE_REVERSE_SCAN`    |`no`                      |multisite|no      |Enable scanning of clients ports and deny access if one is opened.|
|`REVERSE_SCAN_PORTS`  |`22 80 443 3128 8000 8080`|multisite|no      |List of port to scan when using reverse scan feature.             |
|`REVERSE_SCAN_TIMEOUT`|`500`                     |multisite|no      |Specify the maximum timeout (in ms) when scanning a port.         |

## Self-signed certificate

STREAM support :white_check_mark:

Generate self-signed certificate.

|         Setting          |       Default        | Context |Multiple|               Description               |
|--------------------------|----------------------|---------|--------|-----------------------------------------|
|`GENERATE_SELF_SIGNED_SSL`|`no`                  |multisite|no      |Generate and use self-signed certificate.|
|`SELF_SIGNED_SSL_EXPIRY`  |`365`                 |multisite|no      |Self-signed certificate expiry in days.  |
|`SELF_SIGNED_SSL_SUBJ`    |`/CN=www.example.com/`|multisite|no      |Self-signed certificate subject.         |

## Sessions

STREAM support :white_check_mark:

Management of session used by other plugins.

|          Setting          |Default |Context|Multiple|                                   Description                                   |
|---------------------------|--------|-------|--------|---------------------------------------------------------------------------------|
|`SESSIONS_SECRET`          |`random`|global |no      |Secret used to encrypt sessions variables for storing data related to challenges.|
|`SESSIONS_NAME`            |`random`|global |no      |Name of the cookie given to clients.                                             |
|`SESSIONS_IDLING_TIMEOUT`  |`1800`  |global |no      |Maximum time (in seconds) of inactivity before the session is invalidated.       |
|`SESSIONS_ROLLING_TIMEOUT` |`3600`  |global |no      |Maximum time (in seconds) before a session must be renewed.                      |
|`SESSIONS_ABSOLUTE_TIMEOUT`|`86400` |global |no      |Maximum time (in seconds) before a session is destroyed.                         |
|`SESSIONS_CHECK_IP`        |`yes`   |global |no      |Destroy session if IP address is different than original one.                    |
|`SESSIONS_CHECK_USER_AGENT`|`yes`   |global |no      |Destroy session if User-Agent is different than original one.                    |

## UI

STREAM support :x:

Integrate easily the BunkerWeb UI.

| Setting |Default| Context |Multiple|                Description                 |
|---------|-------|---------|--------|--------------------------------------------|
|`USE_UI` |`no`   |multisite|no      |Use UI                                      |
|`UI_HOST`|       |global   |no      |Address of the web UI used for initial setup|

## Whitelist

STREAM support :warning:

Allow access based on internal and external IP/network/rDNS/ASN whitelists.

|          Setting          |                                                                                  Default                                                                                   | Context |Multiple|                                                                            Description                                                                            |
|---------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`USE_WHITELIST`            |`yes`                                                                                                                                                                       |multisite|no      |Activate whitelist feature.                                                                                                                                        |
|`WHITELIST_IP`             |`20.191.45.212 40.88.21.235 40.76.173.151 40.76.163.7 20.185.79.47 52.142.26.175 20.185.79.15 52.142.24.149 40.76.162.208 40.76.163.23 40.76.162.191 40.76.162.247`         |multisite|no      |List of IP/network, separated with spaces, to put into the whitelist.                                                                                              |
|`WHITELIST_RDNS`           |`.google.com .googlebot.com .yandex.ru .yandex.net .yandex.com .search.msn.com .baidu.com .baidu.jp .crawl.yahoo.net .fwd.linkedin.com .twitter.com .twttr.com .discord.com`|multisite|no      |List of reverse DNS suffixes, separated with spaces, to whitelist.                                                                                                 |
|`WHITELIST_RDNS_GLOBAL`    |`yes`                                                                                                                                                                       |multisite|no      |Only perform RDNS whitelist checks on global IP addresses.                                                                                                         |
|`WHITELIST_ASN`            |`32934`                                                                                                                                                                     |multisite|no      |List of ASN numbers, separated with spaces, to whitelist.                                                                                                          |
|`WHITELIST_USER_AGENT`     |                                                                                                                                                                            |multisite|no      |List of User-Agent (PCRE regex), separated with spaces, to whitelist.                                                                                              |
|`WHITELIST_URI`            |                                                                                                                                                                            |multisite|no      |List of URI (PCRE regex), separated with spaces, to whitelist.                                                                                                     |
|`WHITELIST_IP_URLS`        |                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing good IP/network to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.     |
|`WHITELIST_RDNS_URLS`      |                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing reverse DNS suffixes to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.|
|`WHITELIST_ASN_URLS`       |                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing ASN to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                 |
|`WHITELIST_USER_AGENT_URLS`|                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing good User-Agent to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.     |
|`WHITELIST_URI_URLS`       |                                                                                                                                                                            |global   |no      |List of URLs, separated with spaces, containing bad URI to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.             |
