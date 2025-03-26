# Core

!!! info "Settings generator tool"

    To help you tune BunkerWeb, we have made an easy-to-use settings generator tool available at [config.bunkerweb.io](https://config.bunkerweb.io/?utm_campaign=self&utm_source=doc).

This section contains the full list of settings supported by BunkerWeb. If you are not yet familiar with BunkerWeb, you should first read the [concepts](concepts.md) section of the documentation. Please follow the instructions for your own [integration](integrations.md) on how to apply the settings.

As a general rule when multisite mode is enabled, if you want to apply settings with multisite context to a specific server, you will need to add the primary (first) server name as a prefix like `www.example.com_USE_ANTIBOT=captcha` or `myapp.example.com_USE_GZIP=yes` for example.

When settings are considered as "multiple", it means that you can have multiple groups of settings for the same feature by adding numbers as suffix like `REVERSE_PROXY_URL_1=/subdir`, `REVERSE_PROXY_HOST_1=http://myhost1`, `REVERSE_PROXY_URL_2=/anotherdir`, `REVERSE_PROXY_HOST_2=http://myhost2`, ... for example.

## Global settings


STREAM support :warning:

| Setting                         | Default                                                                                                                  | Context   | Multiple | Description                                                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| `IS_LOADING`                    | `no`                                                                                                                     | global    | no       | Internal use : set to yes when BW is loading.                                                                 |
| `NGINX_PREFIX`                  | `/etc/nginx/`                                                                                                            | global    | no       | Where nginx will search for configurations.                                                                   |
| `HTTP_PORT`                     | `8080`                                                                                                                   | global    | yes      | HTTP port number which bunkerweb binds to.                                                                    |
| `HTTPS_PORT`                    | `8443`                                                                                                                   | global    | yes      | HTTPS port number which bunkerweb binds to.                                                                   |
| `MULTISITE`                     | `no`                                                                                                                     | global    | no       | Multi site activation.                                                                                        |
| `SERVER_NAME`                   | `www.example.com`                                                                                                        | multisite | no       | List of the virtual hosts served by bunkerweb.                                                                |
| `WORKER_PROCESSES`              | `auto`                                                                                                                   | global    | no       | Number of worker processes.                                                                                   |
| `WORKER_RLIMIT_NOFILE`          | `2048`                                                                                                                   | global    | no       | Maximum number of open files for worker processes.                                                            |
| `WORKER_CONNECTIONS`            | `1024`                                                                                                                   | global    | no       | Maximum number of connections per worker.                                                                     |
| `LOG_FORMAT`                    | `$host $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"` | global    | no       | The format to use for access logs.                                                                            |
| `LOG_LEVEL`                     | `notice`                                                                                                                 | global    | no       | The level to use for error logs.                                                                              |
| `DNS_RESOLVERS`                 | `127.0.0.11`                                                                                                             | global    | no       | DNS addresses of resolvers to use.                                                                            |
| `WORKERLOCK_MEMORY_SIZE`        | `48k`                                                                                                                    | global    | no       | Size of lua_shared_dict for initialization workers                                                            |
| `DATASTORE_MEMORY_SIZE`         | `64m`                                                                                                                    | global    | no       | Size of the internal datastore.                                                                               |
| `CACHESTORE_MEMORY_SIZE`        | `64m`                                                                                                                    | global    | no       | Size of the internal cachestore.                                                                              |
| `CACHESTORE_IPC_MEMORY_SIZE`    | `16m`                                                                                                                    | global    | no       | Size of the internal cachestore (ipc).                                                                        |
| `CACHESTORE_MISS_MEMORY_SIZE`   | `16m`                                                                                                                    | global    | no       | Size of the internal cachestore (miss).                                                                       |
| `CACHESTORE_LOCKS_MEMORY_SIZE`  | `16m`                                                                                                                    | global    | no       | Size of the internal cachestore (locks).                                                                      |
| `USE_API`                       | `yes`                                                                                                                    | global    | no       | Activate the API to control BunkerWeb.                                                                        |
| `API_HTTP_PORT`                 | `5000`                                                                                                                   | global    | no       | Listen port number for the API.                                                                               |
| `API_LISTEN_IP`                 | `0.0.0.0`                                                                                                                | global    | no       | Listen IP address for the API.                                                                                |
| `API_SERVER_NAME`               | `bwapi`                                                                                                                  | global    | no       | Server name (virtual host) for the API.                                                                       |
| `API_WHITELIST_IP`              | `127.0.0.0/8`                                                                                                            | global    | no       | List of IP/network allowed to contact the API.                                                                |
| `AUTOCONF_MODE`                 | `no`                                                                                                                     | global    | no       | Enable Autoconf Docker integration.                                                                           |
| `SWARM_MODE`                    | `no`                                                                                                                     | global    | no       | Enable Docker Swarm integration.                                                                              |
| `KUBERNETES_MODE`               | `no`                                                                                                                     | global    | no       | Enable Kubernetes integration.                                                                                |
| `SERVER_TYPE`                   | `http`                                                                                                                   | multisite | no       | Server type : http or stream.                                                                                 |
| `LISTEN_STREAM`                 | `yes`                                                                                                                    | multisite | no       | Enable listening for non-ssl (passthrough).                                                                   |
| `LISTEN_STREAM_PORT`            | `1337`                                                                                                                   | multisite | yes      | Listening port for non-ssl (passthrough).                                                                     |
| `LISTEN_STREAM_PORT_SSL`        | `4242`                                                                                                                   | multisite | yes      | Listening port for ssl (passthrough).                                                                         |
| `USE_TCP`                       | `yes`                                                                                                                    | multisite | no       | TCP listen (stream).                                                                                          |
| `USE_UDP`                       | `no`                                                                                                                     | multisite | no       | UDP listen (stream).                                                                                          |
| `USE_IPV6`                      | `no`                                                                                                                     | global    | no       | Enable IPv6 connectivity.                                                                                     |
| `IS_DRAFT`                      | `no`                                                                                                                     | multisite | no       | Internal use : set to yes when the service is in draft mode.                                                  |
| `TIMERS_LOG_LEVEL`              | `debug`                                                                                                                  | global    | no       | Log level for timers.                                                                                         |
| `BUNKERWEB_INSTANCES`           | `127.0.0.1`                                                                                                              | global    | no       | List of BunkerWeb instances separated with spaces (format : fqdn-or-ip:5000 http://fqdn-or-ip:5000)           |
| `USE_TEMPLATE`                  |                                                                                                                          | multisite | no       | Config template to use that will override the default values of specific settings.                            |
| `SECURITY_MODE`                 | `block`                                                                                                                  | multisite | no       | Defines the response to threats: "detect" to monitor and log, or "block" to prevent access and log incidents. |
| `SERVER_NAMES_HASH_BUCKET_SIZE` |                                                                                                                          | global    | no       | Value for the server_names_hash_bucket_size directive.                                                        |


## Anti DDoS <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Provides enhanced protection against DDoS attacks by analyzing and filtering suspicious traffic.

| Setting                      | Default       | Context | Multiple | Description                                                             |
| ---------------------------- | ------------- | ------- | -------- | ----------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global  | no       | Enable or disable anti DDoS protection to mitigate high traffic spikes. |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global  | no       | Size of in-memory storage for DDoS metrics (e.g., 10M, 500k).           |
| `ANTIDDOS_THRESHOLD`         | `100`         | global  | no       | Maximum suspicious requests allowed from a single IP before blocking.   |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global  | no       | Time window (seconds) to detect abnormal request patterns.              |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global  | no       | HTTP status codes treated as suspicious for DDoS analysis.              |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global  | no       | Minimum distinct IP count before enabling anti DDoS measures.           |

## Antibot

STREAM support :x:

Attackers often use automated tools (bots) to try and exploit your website. To protect against this, BunkerWeb includes an "Antibot" feature that challenges users to prove they are human. If a user successfully completes the challenge, they are granted access to your website. This feature is disabled by default.

**Here's a breakdown of how the Antibot feature works:**

1.  When a user visits your site, BunkerWeb checks if they've already passed the antibot challenge.
2.  If not, the user is redirected to a challenge page.
3.  The user must complete the challenge (e.g., solve a CAPTCHA, run JavaScript).
4.  If the challenge is successful, the user is redirected back to the page they were originally trying to visit and can browse your website normally.

### How to Use

Follow these steps to enable and configure the Antibot feature:

1.  **Choose a challenge type:** Decide which type of antibot challenge you want to use (e.g., [captcha](#__tabbed_1_3), [hcaptcha](#__tabbed_1_5), [javascript](#__tabbed_1_2)).
2.  **Enable the feature:** Set the `USE_ANTIBOT` setting to your chosen challenge type in your BunkerWeb configuration.
3.  **Configure the settings:** Adjust the other `ANTIBOT_*` settings as needed. For reCAPTCHA, hCaptcha, Turnstile and mCaptcha, you'll need to create an account with the respective service and obtain API keys.
4.  **Important:** Ensure the `ANTIBOT_URI` is a unique URL on your site that is not in use.

!!! important "About the `ANTIBOT_URI` Setting"
    Ensure the `ANTIBOT_URI` is a unique URL on your site that is not in use.

!!! warning "Session Configuration in Clustered Environments"
    The antibot feature uses cookies to track whether a user has completed the challenge. If you are running BunkerWeb in a clustered environment (multiple BunkerWeb instances), you **must** configure session management properly. This involves setting the `SESSIONS_SECRET` and `SESSIONS_NAME` settings to the **same values** across all BunkerWeb instances. If you don't do this, users may be repeatedly prompted to complete the antibot challenge. You can find more information about session configuration [here](#sessions).

### Supported Challenge Mechanisms

=== "Cookie"

    Sends a cookie to the client and expects it to be returned on subsequent requests.

    **Configuration Settings:**

    | Setting                | Default      | Context   | Multiple | Description                                                                                                                                         |
    | ---------------------- | ------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`          | `no`         | multisite | no       | **Enable Antibot:** Set to `cookie` to enable the Cookie challenge.                                                                                 |
    | `ANTIBOT_URI`          | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
    | `ANTIBOT_TIME_RESOLVE` | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
    | `ANTIBOT_TIME_VALID`   | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

=== "JavaScript"

    Requires the client to solve a computational challenge using JavaScript.

    **Configuration Settings:**

    | Setting                | Default      | Context   | Multiple | Description                                                                                                                                         |
    | ---------------------- | ------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`          | `no`         | multisite | no       | **Enable Antibot:** Set to `javascript` to enable the JavaScript challenge.                                                                         |
    | `ANTIBOT_URI`          | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
    | `ANTIBOT_TIME_RESOLVE` | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
    | `ANTIBOT_TIME_VALID`   | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

=== "Captcha"

    Our homemade Captcha mechanism offers a simple yet effective challenge designed and hosted entirely within your BunkerWeb environment. It generates dynamic, image-based challenges that test users' ability to recognize and interpret randomized characters, ensuring automated bots are effectively blocked without the need for any external API calls or third-party services.

    **Configuration Settings:**

    | Setting                | Default      | Context   | Multiple | Description                                                                                                                                         |
    | ---------------------- | ------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`          | `no`         | multisite | no       | **Enable Antibot:** Set to `captcha` to enable the Captcha challenge.                                                                               |
    | `ANTIBOT_URI`          | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
    | `ANTIBOT_TIME_RESOLVE` | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
    | `ANTIBOT_TIME_VALID`   | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

=== "reCAPTCHA"

    When enabled, reCAPTCHA runs in the background (v3) to assign a score based on user behavior. A score lower than the configured threshold will prompt further verification or block the request. For visible challenges (v2), users must interact with the reCAPTCHA widget before continuing.

    To use reCAPTCHA with BunkerWeb, you need to obtain your site and secret keys from the [Google reCAPTCHA admin console](https://www.google.com/recaptcha/admin). Once you have the keys, you can configure BunkerWeb to use reCAPTCHA as an antibot mechanism.

    **Configuration Settings:**

    | Setting                     | Default      | Context   | Multiple | Description                                                                                                                                                                |
    | --------------------------- | ------------ | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`         | multisite | no       | **Enable Antibot:** Set to `recaptcha` to enable the reCAPTCHA challenge.                                                                                                  |
    | `ANTIBOT_RECAPTCHA_SITEKEY` |              | multisite | no       | **reCAPTCHA Site Key:** Your reCAPTCHA site key (get this from Google).                                                                                                    |
    | `ANTIBOT_RECAPTCHA_SECRET`  |              | multisite | no       | **reCAPTCHA Secret Key:** Your reCAPTCHA secret key (get this from Google).                                                                                                |
    | `ANTIBOT_RECAPTCHA_SCORE`   | `0.7`        | multisite | no       | **reCAPTCHA Minimum Score:** The minimum score required for reCAPTCHA to pass a user (only for reCAPTCHA v3). A higher score means more confidence that the user is human. |
    | `ANTIBOT_URI`               | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site.                        |
    | `ANTIBOT_TIME_RESOLVE`      | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.                          |
    | `ANTIBOT_TIME_VALID`        | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.                                   |

=== "hCaptcha"

    When enabled, hCaptcha provides an effective alternative to reCAPTCHA by verifying user interactions without relying on a scoring mechanism. It challenges users with a simple, interactive test to confirm their legitimacy.

    To integrate hCaptcha with BunkerWeb, you must obtain the necessary credentials from the hCaptcha dashboard at [hCaptcha](https://www.hcaptcha.com). These credentials include a site key and a secret key.

    **Configuration Settings:**

    | Setting                    | Default      | Context   | Multiple | Description                                                                                                                                         |
    | -------------------------- | ------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`         | multisite | no       | **Enable Antibot:** Set to `hcaptcha` to enable the hCaptcha challenge.                                                                             |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |              | multisite | no       | **hCaptcha Site Key:** Your hCaptcha site key (get this from hCaptcha).                                                                             |
    | `ANTIBOT_HCAPTCHA_SECRET`  |              | multisite | no       | **hCaptcha Secret Key:** Your hCaptcha secret key (get this from hCaptcha).                                                                         |
    | `ANTIBOT_URI`              | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
    | `ANTIBOT_TIME_RESOLVE`     | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
    | `ANTIBOT_TIME_VALID`       | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

=== "Turnstile"

    Turnstile is a modern, privacy-friendly challenge mechanism that leverages Cloudflare’s technology to detect and block automated traffic. It validates user interactions in a seamless, background manner, reducing friction for legitimate users while effectively discouraging bots.

    To integrate Turnstile with BunkerWeb, ensure you obtain the necessary credentials from [Cloudflare Turnstile](https://www.cloudflare.com/turnstile).

    **Configuration Settings:**

    | Setting                     | Default      | Context   | Multiple | Description                                                                                                                                         |
    | --------------------------- | ------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`         | multisite | no       | **Enable Antibot:** Set to `turnstile` to enable the Turnstile challenge.                                                                           |
    | `ANTIBOT_TURNSTILE_SITEKEY` |              | multisite | no       | **Turnstile Site Key:** Your Turnstile site key (get this from Cloudflare).                                                                         |
    | `ANTIBOT_TURNSTILE_SECRET`  |              | multisite | no       | **Turnstile Secret Key:** Your Turnstile secret key (get this from Cloudflare).                                                                     |
    | `ANTIBOT_URI`               | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
    | `ANTIBOT_TIME_RESOLVE`      | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
    | `ANTIBOT_TIME_VALID`        | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

=== "mCaptcha"

    mCaptcha is an alternative CAPTCHA challenge mechanism that verifies the legitimacy of users by presenting an interactive test similar to other antibot solutions. When enabled, it challenges users with a CAPTCHA provided by mCaptcha, ensuring that only genuine users bypass the automated security checks.

    mCaptcha is designed with privacy in mind. It is fully GDPR compliant, ensuring that all user data involved in the challenge process adheres to strict data protection standards. Additionally, mCaptcha offers the flexibility to be self-hosted, allowing organizations to maintain full control over their data and infrastructure. This self-hosting capability not only enhances privacy but also optimizes performance and customization to suit specific deployment needs.

    To integrate mCaptcha with BunkerWeb, you must obtain the necessary credentials from the [mCaptcha](https://mcaptcha.org/) platform or yours. These credentials include a site key and a secret key for verification.

    **Configuration Settings:**

    | Setting                    | Default                     | Context   | Multiple | Description                                                                                                                                         |
    | -------------------------- | --------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | no       | **Enable Antibot:** Set to `mcaptcha` to enable the mCaptcha challenge.                                                                             |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | no       | **mCaptcha Site Key:** Your mCaptcha site key (get this from mCaptcha).                                                                             |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | no       | **mCaptcha Secret Key:** Your mCaptcha secret key (get this from mCaptcha).                                                                         |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | no       | **mCaptcha Domain:** The domain to use for the mCaptcha challenge. Generally, you should leave this as the default.                                 |
    | `ANTIBOT_URI`              | `/challenge`                | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
    | `ANTIBOT_TIME_RESOLVE`     | `60`                        | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
    | `ANTIBOT_TIME_VALID`       | `86400`                     | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

## Auth basic

STREAM support :x:

The Auth Basic plugin provides HTTP basic authentication to protect your website or specific resources. This feature adds an extra layer of security by requiring users to enter a username and password before they can access the protected content. This type of authentication is simple to implement and widely supported by browsers.

**Here's how the Auth Basic feature works:**

1. When a user tries to access a protected area of your website, the server sends a challenge requesting authentication.
2. The browser displays a login dialog box prompting the user for a username and password.
3. The user enters their credentials, which are sent to the server.
4. If the credentials are valid, the user is granted access to the requested content.
5. If the credentials are invalid, the user is served an error message with the 401 Unauthorized status code.

### How to Use

Follow these steps to enable and configure Auth Basic authentication:

1. **Enable the feature:** Set the `USE_AUTH_BASIC` setting to `yes` in your BunkerWeb configuration.
2. **Choose protection scope:** Decide whether to protect your entire site or just specific URLs by configuring the `AUTH_BASIC_LOCATION` setting.
3. **Define credentials:** Set up at least one username and password pair using the `AUTH_BASIC_USER` and `AUTH_BASIC_PASSWORD` settings.
4. **Customize the message:** Optionally change the `AUTH_BASIC_TEXT` to display a custom message in the login prompt.

### Configuration Settings

| Setting               | Default           | Context   | Multiple | Description                                                                                                                                |
| --------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_AUTH_BASIC`      | `no`              | multisite | no       | **Enable Auth Basic:** Set to `yes` to enable basic authentication.                                                                        |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | no       | **Protection Scope:** Set to `sitewide` to protect the entire site, or specify a URL path (e.g., `/admin`) to protect only specific areas. |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | yes      | **Username:** The username required for authentication. You can define multiple username/password pairs.                                   |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | yes      | **Password:** The password required for authentication. Each password corresponds to a username.                                           |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | no       | **Prompt Text:** The message displayed in the authentication prompt shown to users.                                                        |

!!! warning "Security Considerations"
    HTTP Basic Authentication transmits credentials encoded (not encrypted) in Base64. While this is fine when used over HTTPS, it should not be considered secure over plain HTTP. Always enable SSL/TLS when using basic authentication.

!!! tip "Using Multiple Credentials"
    You can configure multiple username/password pairs for access. Each `AUTH_BASIC_USER` setting should have a corresponding `AUTH_BASIC_PASSWORD` setting.

### Example Configurations

=== "Site-wide Protection"

    To protect your entire website with a single set of credentials:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Protecting Specific Areas"

    To only protect a specific path, such as an admin panel:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Multiple Users"

    To set up multiple users with different credentials:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # First user
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Second user
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Third user
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```

## Backup

STREAM support :white_check_mark:

The Backup plugin provides an automatic backup solution to protect your BunkerWeb data. This feature ensures the safety and availability of your important database by creating regular backups according to your preferred schedule. Backups are stored in a designated location and can be easily managed through both automatic processes and manual commands.

**Here's how the Backup feature works:**

1. Your database is automatically backed up according to the schedule you set (daily, weekly, or monthly).
2. Backups are stored in a specified directory on your system.
3. Old backups are automatically rotated out based on your retention settings.
4. You can manually create backups, list existing backups, or restore from a backup at any time.
5. Before any restore operation, the current state is automatically backed up as a safety measure.

### How to Use

Follow these steps to configure and use the Backup feature:

1. **Enable the feature:** The backup feature is enabled by default. If needed, you can control this with the `USE_BACKUP` setting.
2. **Configure backup schedule:** Choose how often backups should occur by setting the `BACKUP_SCHEDULE` parameter.
3. **Set retention policy:** Specify how many backups to keep using the `BACKUP_ROTATION` setting.
4. **Define storage location:** Choose where backups will be stored using the `BACKUP_DIRECTORY` setting.
5. **Use CLI commands:** Manage backups manually with the `bwcli plugin backup` commands when needed.

### Configuration Settings

| Setting            | Default                      | Context | Multiple | Description                                                                                                               |
| ------------------ | ---------------------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | no       | **Enable Backup:** Set to `yes` to enable automatic backups.                                                              |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | no       | **Backup Frequency:** How often to perform backups. Options: `daily`, `weekly`, or `monthly`.                             |
| `BACKUP_ROTATION`  | `7`                          | global  | no       | **Backup Retention:** The number of backup files to keep. Older backups beyond this number will be automatically deleted. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global  | no       | **Backup Location:** The directory where backup files will be stored.                                                     |

### Command Line Interface

The Backup plugin provides several CLI commands to manage your backups:

```bash
# List all available backups
bwcli plugin backup list

# Create a manual backup
bwcli plugin backup save

# Create a backup in a custom location
bwcli plugin backup save --directory /path/to/custom/location

# Restore from the most recent backup
bwcli plugin backup restore

# Restore from a specific backup file
bwcli plugin backup restore /path/to/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "Safety First"
    Before any restore operation, the Backup plugin automatically creates a backup of your current database state in a temporary location. This provides an additional safety net in case you need to revert the restore operation.

!!! warning "Database Compatibility"
    The Backup plugin supports SQLite, MySQL/MariaDB, and PostgreSQL databases. Oracle databases are currently not supported for backup and restore operations.

### Example Configurations

=== "Daily Backups with 7-Day Retention"

    Default configuration that creates daily backups and keeps the most recent 7 files:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Weekly Backups with Extended Retention"

    Configuration for less frequent backups with longer retention:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Monthly Backups to Custom Location"

    Configuration for monthly backups stored in a custom location:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```

## Backup S3 <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :white_check_mark:

Automatically backup your data to an S3 bucket

| Setting                       | Default | Context | Multiple | Description                                  |
| ----------------------------- | ------- | ------- | -------- | -------------------------------------------- |
| `USE_BACKUP_S3`               | `no`    | global  | no       | Enable or disable the S3 backup feature      |
| `BACKUP_S3_SCHEDULE`          | `daily` | global  | no       | The frequency of the backup                  |
| `BACKUP_S3_ROTATION`          | `7`     | global  | no       | The number of backups to keep                |
| `BACKUP_S3_ENDPOINT`          |         | global  | no       | The S3 endpoint                              |
| `BACKUP_S3_BUCKET`            |         | global  | no       | The S3 bucket                                |
| `BACKUP_S3_DIR`               |         | global  | no       | The S3 directory                             |
| `BACKUP_S3_REGION`            |         | global  | no       | The S3 region                                |
| `BACKUP_S3_ACCESS_KEY_ID`     |         | global  | no       | The S3 access key ID                         |
| `BACKUP_S3_ACCESS_KEY_SECRET` |         | global  | no       | The S3 access key secret                     |
| `BACKUP_S3_COMP_LEVEL`        | `6`     | global  | no       | The compression level of the backup zip file |

## Bad behavior

STREAM support :white_check_mark:

The Bad Behavior plugin protects your website by automatically detecting and banning IP addresses that generate too many errors or "bad" HTTP status codes within a specified period of time. This helps defend against brute force attacks, web scrapers, vulnerability scanners, and other malicious activities that might generate numerous error responses.

**Here's how the Bad Behavior feature works:**

1. The plugin monitors HTTP responses from your site.
2. When a visitor receives a "bad" HTTP status code (like 400, 401, 403, 404, etc.), the counter for that IP address is incremented.
3. If an IP address exceeds the configured threshold of bad status codes within the specified time period, the IP is automatically banned.
4. Banned IPs can be blocked either at the service level (just for the specific site) or globally (across all sites), depending on your configuration.
5. Bans automatically expire after the configured ban duration.

!!! success "Key benefits"

      1. **Automatic Protection:** Detects and blocks potentially malicious clients without requiring manual intervention.
      2. **Customizable Rules:** Fine-tune what constitutes "bad behavior" based on your specific needs.
      3. **Resource Conservation:** Prevents malicious actors from consuming server resources with repeated invalid requests.
      4. **Flexible Scope:** Choose whether bans should apply just to the current service or globally across all services.
      5. **Temporary Bans:** All bans automatically expire after the configured duration, preventing permanent lockouts.

### How to Use

Follow these steps to configure and use the Bad Behavior feature:

1. **Enable the feature:** The Bad Behavior feature is enabled by default. If needed, you can control this with the `USE_BAD_BEHAVIOR` setting.
2. **Configure status codes:** Define which HTTP status codes should be considered "bad" using the `BAD_BEHAVIOR_STATUS_CODES` setting.
3. **Set threshold values:** Determine how many "bad" responses should trigger a ban using the `BAD_BEHAVIOR_THRESHOLD` setting.
4. **Configure time periods:** Set how long to count bad responses and how long bans should last using the `BAD_BEHAVIOR_COUNT_TIME` and `BAD_BEHAVIOR_BAN_TIME` settings.
5. **Choose ban scope:** Decide whether bans should apply to just the current service or globally across all services using the `BAD_BEHAVIOR_BAN_SCOPE` setting.

### Configuration Settings

| Setting                     | Default                       | Context   | Multiple | Description                                                                                                                          |
| --------------------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | no       | **Enable Bad Behavior:** Set to `yes` to enable the bad behavior detection and banning feature.                                      |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | no       | **Bad Status Codes:** List of HTTP status codes that will be counted as "bad" behavior when returned to a client.                    |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | no       | **Threshold:** The number of "bad" status codes an IP can generate within the counting period before being banned.                   |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | no       | **Count Period:** The time window (in seconds) during which bad status codes are counted toward the threshold.                       |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | no       | **Ban Duration:** How long (in seconds) an IP will remain banned after exceeding the threshold. Default is 24 hours (86400 seconds). |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | multisite | no       | **Ban Scope:** Determines whether bans apply only to the current service (`service`) or to all services (`global`).                  |

!!! warning "False Positives"
    Be careful when setting the threshold and count time. Setting these values too low could potentially ban legitimate users who accidentally encounter errors while browsing your site.

!!! tip "Tuning Your Configuration"
    Start with conservative settings (higher threshold, shorter ban time) and adjust based on your specific needs and traffic patterns. Monitor your logs to ensure legitimate users aren't being incorrectly banned.

### Example Configurations

=== "Default Configuration"

    The default configuration provides a balanced approach suitable for most websites:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Strict Configuration"

    For high-security applications where you want to be more aggressive in banning potential threats:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"  # 7 days
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Ban across all services
    ```

=== "Lenient Configuration"

    For sites with high legitimate traffic where you want to avoid false positives:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"  # Only count unauthorized, forbidden, and rate limited
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"  # 1 hour
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

## Blacklist

STREAM support :warning:

The Blacklist plugin provides robust protection for your website by allowing you to block access based on various client attributes. This feature helps defend against known malicious entities, scanners, and suspicious visitors by denying access to IPs, networks, reverse DNS entries, ASNs, user agents, and specific URI patterns.

**Here's how the Blacklist feature works:**

1. The plugin checks incoming requests against multiple blacklist criteria (*IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns*).
2. Blacklists can be specified directly in your configuration or loaded from external URLs.
3. If a visitor matches any blacklist rule (and doesn't match any ignore rule), their access is denied.
4. Blacklists are automatically updated on a regular schedule from configured URLs.
5. You can customize exactly which criteria are checked and ignored based on your specific security needs.

### How to Use

Follow these steps to configure and use the Blacklist feature:

1. **Enable the feature:** The Blacklist feature is enabled by default. If needed, you can control this with the `USE_BLACKLIST` setting.
2. **Configure block rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be blocked.
3. **Set up ignore rules:** Specify any exceptions that should bypass the blacklist checks.
4. **Add external sources:** Configure URLs for automatically downloading and updating blacklist data.
5. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on blocked requests.

### Configuration Settings

**General**

| Setting         | Default | Context   | Multiple | Description                                                         |
| --------------- | ------- | --------- | -------- | ------------------------------------------------------------------- |
| `USE_BLACKLIST` | `yes`   | multisite | no       | **Enable Blacklist:** Set to `yes` to enable the blacklist feature. |

=== "IP Address"
    **What this does:** Blocks visitors based on their IP address or network.

    | Setting                    | Default                               | Context   | Multiple | Description                                                                                            |
    | -------------------------- | ------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_IP`             |                                       | multisite | no       | **IP Blacklist:** List of IP addresses or networks (CIDR notation) to block, separated by spaces.      |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | no       | **IP Ignore List:** List of IP addresses or networks that should bypass IP blacklist checks.           |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | no       | **IP Blacklist URLs:** List of URLs containing IP addresses or networks to block, separated by spaces. |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | no       | **IP Ignore List URLs:** List of URLs containing IP addresses or networks to ignore.                   |

    The default `BLACKLIST_IP_URLS` setting includes a URL that provides a **list of known Tor exit nodes**. This is a common source of malicious traffic and is a good starting point for many sites.

=== "Reverse DNS"
    **What this does:** Blocks visitors based on their domain name (in reverse). This is useful for blocking known scanners and crawlers by their organization's domain.

    | Setting                      | Default                 | Context   | Multiple | Description                                                                                          |
    | ---------------------------- | ----------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | no       | **rDNS Blacklist:** List of reverse DNS suffixes to block, separated by spaces.                      |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | no       | **rDNS Global Only:** Only perform rDNS checks on global IP addresses when set to `yes`.             |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | no       | **rDNS Ignore List:** List of reverse DNS suffixes that should bypass rDNS blacklist checks.         |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | no       | **rDNS Blacklist URLs:** List of URLs containing reverse DNS suffixes to block, separated by spaces. |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | no       | **rDNS Ignore List URLs:** List of URLs containing reverse DNS suffixes to ignore.                   |

    The default `BLACKLIST_RDNS` setting includes common scanner domains like **Shodan** and **Censys**. These are often used by security researchers and scanners to identify vulnerable sites.

=== "ASN"
    **What this does:** Blocks visitors from specific network providers. ASNs are like zip codes for the internet - they identify which provider or organization an IP belongs to.

    | Setting                     | Default | Context   | Multiple | Description                                                                         |
    | --------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |         | multisite | no       | **ASN Blacklist:** List of Autonomous System Numbers to block, separated by spaces. |
    | `BLACKLIST_IGNORE_ASN`      |         | multisite | no       | **ASN Ignore List:** List of ASNs that should bypass ASN blacklist checks.          |
    | `BLACKLIST_ASN_URLS`        |         | multisite | no       | **ASN Blacklist URLs:** List of URLs containing ASNs to block, separated by spaces. |
    | `BLACKLIST_IGNORE_ASN_URLS` |         | multisite | no       | **ASN Ignore List URLs:** List of URLs containing ASNs to ignore.                   |

=== "User Agent"
    **What this does:** Blocks visitors based on what browser or tool they claim to be using. This is effective against many bots that honestly identify themselves (like "ScannerBot" or "WebHarvestTool").

    | Setting                            | Default                                                                                                                        | Context   | Multiple | Description                                                                                             |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | no       | **User-Agent Blacklist:** List of User-Agent patterns (PCRE regex) to block, separated by spaces.       |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | no       | **User-Agent Ignore List:** List of User-Agent patterns that should bypass User-Agent blacklist checks. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | no       | **User-Agent Blacklist URLs:** List of URLs containing User-Agent patterns to block.                    |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | no       | **User-Agent Ignore List URLs:** List of URLs containing User-Agent patterns to ignore.                 |

    The default `BLACKLIST_USER_AGENT_URLS` setting includes a URL that provides a **list of known bad user agents**. These are often used by malicious bots and scanners to identify vulnerable sites.

=== "URI"
    **What this does:** Blocks requests to specific URLs on your site. This is helpful for blocking attempts to access admin pages, login forms, or other sensitive areas that might be targeted.

    | Setting                     | Default | Context   | Multiple | Description                                                                                 |
    | --------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |         | multisite | no       | **URI Blacklist:** List of URI patterns (PCRE regex) to block, separated by spaces.         |
    | `BLACKLIST_IGNORE_URI`      |         | multisite | no       | **URI Ignore List:** List of URI patterns that should bypass URI blacklist checks.          |
    | `BLACKLIST_URI_URLS`        |         | multisite | no       | **URI Blacklist URLs:** List of URLs containing URI patterns to block, separated by spaces. |
    | `BLACKLIST_IGNORE_URI_URLS` |         | multisite | no       | **URI Ignore List URLs:** List of URLs containing URI patterns to ignore.                   |

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Blacklists from URLs are automatically downloaded and updated hourly to ensure your protection remains current against the latest threats.

### Example Configurations

=== "Basic IP and User-Agent Protection"

    A simple configuration that blocks known Tor exit nodes and common bad user agents:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Advanced Protection with Custom Rules"

    A more comprehensive configuration with custom blacklist entries and exceptions:

    ```yaml
    USE_BLACKLIST: "yes"

    # Custom blacklist entries
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # AWS and Amazon ASNs
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Custom ignore rules
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # External blacklist sources
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Using Local Files"

    Configuration using local files for blacklists:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///path/to/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///path/to/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///path/to/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///path/to/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///path/to/uri-blacklist.txt"
    ```

## Brotli

STREAM support :x:

The Brotli plugin enables efficient compression of HTTP responses using the Brotli algorithm. This feature helps reduce bandwidth usage and improve page load times by compressing web content before it's sent to the client's browser.

Compared to other compression methods like gzip, Brotli typically achieves higher compression ratios, resulting in smaller file sizes and faster content delivery.

**Here's how the Brotli feature works:**

1. When a client requests content from your website, BunkerWeb checks if the client supports Brotli compression.
2. If supported, BunkerWeb compresses the response using the Brotli algorithm at your configured compression level.
3. The compressed content is sent to the client with appropriate headers indicating Brotli compression.
4. The client's browser decompresses the content before rendering it to the user.
5. Both bandwidth usage and page load times are reduced, improving overall user experience.

### How to Use

Follow these steps to configure and use the Brotli compression feature:

1. **Enable the feature:** The Brotli feature is disabled by default. Enable it by setting the `USE_BROTLI` setting to `yes`.
2. **Configure MIME types:** Specify which content types should be compressed using the `BROTLI_TYPES` setting.
3. **Set minimum size:** Define the minimum response size for compression with `BROTLI_MIN_LENGTH` to avoid compressing tiny files.
4. **Choose compression level:** Select your preferred balance between speed and compression ratio with `BROTLI_COMP_LEVEL`.
5. **Let BunkerWeb handle the rest:** Once configured, compression happens automatically for eligible responses.

### Configuration Settings

| Setting             | Default                                                                                                                                                                                                                                                                                                                                                                                                                          | Context   | Multiple | Description                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Enable Brotli:** Set to `yes` to enable Brotli compression.                                                                |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **MIME Types:** List of content types that will be compressed with Brotli.                                                   |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Minimum Size:** The minimum response size (in bytes) for Brotli compression to be applied.                                 |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Compression Level:** Level of compression from 0 (no compression) to 11 (maximum compression). Higher values use more CPU. |

!!! tip "Optimizing Compression Level"
    The default compression level (6) offers a good balance between compression ratio and CPU usage. For static content or when server CPU resources are plentiful, consider increasing to 9-11 for maximum compression. For dynamic content or when CPU resources are limited, you might want to use 4-5 for faster compression with reasonable size reduction.

!!! info "Browser Support"
    Brotli is supported by all modern browsers including Chrome, Firefox, Edge, Safari, and Opera. Older browsers will automatically receive uncompressed content, ensuring compatibility.

### Example Configurations

=== "Basic Configuration"

    A standard configuration that enables Brotli with default settings:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "Maximum Compression"

    Configuration optimized for maximum compression savings:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "Balanced Performance"

    Configuration that balances compression ratio with CPU usage:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```

## BunkerNet

STREAM support :white_check_mark:

The BunkerNet plugin enables collective threat intelligence sharing between BunkerWeb instances, creating a powerful network of protection against malicious actors. By participating in BunkerNet, your instance both benefits from and contributes to a global database of known threats, enhancing security for the entire BunkerWeb community.

**Here's how the BunkerNet feature works:**

1. Your BunkerWeb instance automatically registers with the BunkerNet API to receive a unique identifier.
2. When your instance detects and blocks a malicious IP address or behavior, it anonymously reports this threat to BunkerNet.
3. BunkerNet aggregates threat intelligence from all participating instances and distributes the consolidated database.
4. Your instance regularly downloads an updated database of known threats from BunkerNet.
5. This collective intelligence allows your instance to proactively block IPs that have exhibited malicious behavior on other BunkerWeb instances.

!!! success "Key benefits"

      1. **Collective Defense:** Leverage the security findings from thousands of other BunkerWeb instances globally.
      2. **Proactive Protection:** Block malicious actors before they can target your site based on their behavior elsewhere.
      3. **Community Contribution:** Help protect other BunkerWeb users by sharing anonymized threat data about attackers.
      4. **Zero Configuration:** Works out of the box with sensible defaults, requiring minimal setup.
      5. **Privacy Focused:** Only shares necessary threat information without compromising your or your users' privacy.

### How to Use

Follow these steps to configure and use the BunkerNet feature:

1. **Enable the feature:** The BunkerNet feature is enabled by default. If needed, you can control this with the `USE_BUNKERNET` setting.
2. **Initial registration:** Upon first startup, your instance will automatically register with the BunkerNet API and receive a unique identifier.
3. **Automatic updates:** Your instance will automatically download the latest threat database on a regular schedule.
4. **Automatic reporting:** When your instance blocks a malicious IP, it will automatically contribute this data to the community.
5. **Monitor protection:** Check the [web UI](web-ui.md) to see statistics on threats blocked by BunkerNet intelligence.

### Configuration Settings

| Setting            | Default                    | Context   | Multiple | Description                                                                                    |
| ------------------ | -------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | no       | **Enable BunkerNet:** Set to `yes` to enable the BunkerNet threat intelligence sharing.        |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | no       | **BunkerNet Server:** The address of the BunkerNet API server for sharing threat intelligence. |

!!! tip "Network Protection"
    When BunkerNet detects that an IP address has been involved in malicious activity across multiple BunkerWeb instances, it adds that IP to a collective blacklist. This provides a proactive defense layer, protecting your site from threats before they can target you directly.

!!! info "Anonymous Reporting"
    When reporting threat information to BunkerNet, your instance only shares the necessary data to identify the threat: the IP address, the reason for blocking, and minimal contextual data. No personal information about your users or sensitive details about your site are shared.

### Example Configurations

=== "Default Configuration (Recommended)"

    The default configuration enables BunkerNet with the official BunkerWeb API server:

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Disabled Configuration"

    If you prefer not to participate in the BunkerNet threat intelligence network:

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Custom Server Configuration"

    For organizations running their own BunkerNet server (uncommon):

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

## CORS

STREAM support :x:

The CORS plugin enables Cross-Origin Resource Sharing for your website, allowing controlled access to your resources from different domains. This feature helps you safely share your content with trusted third-party websites while maintaining security by explicitly defining which origins, methods, and headers are permitted.

**Here's how the CORS feature works:**

1. When a browser makes a cross-origin request to your website, it first sends a preflight request with the `OPTIONS` method.
2. BunkerWeb checks if the requesting origin is permitted based on your configuration.
3. If allowed, BunkerWeb responds with the appropriate CORS headers that define what the requesting site can do.
4. For non-permitted origins, the request can be either denied completely or served without CORS headers.
5. Additional cross-origin policies (COEP, COOP, CORP) can be configured to further enhance security.

### How to Use

Follow these steps to configure and use the CORS feature:

1. **Enable the feature:** The CORS feature is disabled by default. Set the `USE_CORS` setting to `yes` to enable it.
2. **Configure allowed origins:** Specify which domains can access your resources using the `CORS_ALLOW_ORIGIN` setting.
3. **Set permitted methods:** Define which HTTP methods are allowed for cross-origin requests with `CORS_ALLOW_METHODS`.
4. **Configure allowed headers:** Specify which headers can be used in requests with `CORS_ALLOW_HEADERS`.
5. **Control credentials:** Decide whether cross-origin requests can include credentials using `CORS_ALLOW_CREDENTIALS`.

### Configuration Settings

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                                                  |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Enable CORS:** Set to `yes` to enable Cross-Origin Resource Sharing.                                       |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Allowed Origins:** PCRE regex of allowed origins, `*` for any origin, or `self` for same-origin only.      |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Allowed Methods:** HTTP methods that can be used in cross-origin requests.                                 |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Allowed Headers:** HTTP headers that can be used in cross-origin requests.                                 |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Allow Credentials:** Set to `yes` to allow credentials (cookies, HTTP authentication) in CORS requests.    |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Exposed Headers:** HTTP headers that browsers are permitted to access from cross-origin responses.         |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controls communication between browsing contexts.                            |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controls whether document can load resources from other origins.           |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controls which websites can embed your resources.                          |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Preflight Cache Duration:** How long (in seconds) browsers should cache the preflight response.            |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Deny Unauthorized Origins:** When `yes`, requests from unauthorized origins are denied with an error code. |

!!! tip "Optimizing Preflight Requests"
    The `CORS_MAX_AGE` setting determines how long browsers will cache the results of a preflight request. Setting this to a higher value (like the default 86400 seconds/24 hours) reduces the number of preflight requests, improving performance for frequently accessed resources.

!!! warning "Security Considerations"
    Be cautious when setting `CORS_ALLOW_ORIGIN` to `*` (all origins) or `CORS_ALLOW_CREDENTIALS` to `yes`, as these configurations can introduce security risks if not properly managed. It's generally safer to explicitly list trusted origins and limit the allowed methods and headers.

### Example Configurations

=== "Basic Configuration"

    A simple configuration allowing cross-origin requests from the same domain:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "self"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Public API Configuration"

    Configuration for a public API that needs to be accessible from any origin:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "*"
    CORS_ALLOW_METHODS: "GET, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, X-API-Key"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "3600"
    CORS_DENY_REQUEST: "no"
    ```

=== "Multiple Trusted Domains"

    Configuration for allowing multiple specific domains with a single PCRE regex pattern:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(app|api|dashboard)\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Requested-With"
    CORS_ALLOW_CREDENTIALS: "yes"
    CORS_EXPOSE_HEADERS: "Content-Length, Content-Range, X-RateLimit-Remaining"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Subdomain Wildcard"

    Configuration allowing all subdomains of a primary domain using PCRE regex pattern:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://.*\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Multiple Domain Patterns"

    Configuration allowing requests from multiple domain patterns with alternation:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(.*\\.example\\.com|.*\\.trusted-partner\\.org|api\\.third-party\\.net)$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Custom-Header"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

## Client cache

STREAM support :x:

The Client Cache plugin optimizes website performance by controlling how browsers cache your static content. This feature helps reduce bandwidth usage, server load, and improves page load times by instructing client browsers to store and reuse static assets like images, CSS, and JavaScript files locally instead of requesting them on every page visit.

**Here's how the Client Cache feature works:**

1. When enabled, BunkerWeb adds Cache-Control headers to responses for static files.
2. These headers tell browsers how long they should cache the content locally.
3. For files with specified extensions (like images, CSS, JavaScript), BunkerWeb applies the configured caching policy.
4. Optional ETag support provides additional validation mechanisms to determine if cached content is still fresh.
5. When visitors return to your site, their browsers can use locally cached files instead of downloading them again, resulting in faster page loads.

### How to Use

Follow these steps to configure and use the Client Cache feature:

1. **Enable the feature:** The Client Cache feature is disabled by default. Set the `USE_CLIENT_CACHE` setting to `yes` to enable it.
2. **Configure file extensions:** Specify which file types should be cached using the `CLIENT_CACHE_EXTENSIONS` setting.
3. **Set cache control directives:** Customize how clients should cache content using the `CLIENT_CACHE_CONTROL` setting.
4. **Configure ETag support:** Decide whether to enable ETags for validating cache freshness with the `CLIENT_CACHE_ETAG` setting.
5. **Let BunkerWeb handle the rest:** Once configured, caching headers will be automatically applied to eligible responses.

### Configuration Settings

| Setting                   | Default                    | Context   | Multiple | Description                                                                                    |
| ------------------------- | -------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_CLIENT_CACHE`        | `no`                       | multisite | no       | **Enable Client Cache:** Set to `yes` to enable client-side caching of static files.           |
| `CLIENT_CACHE_EXTENSIONS` | `jpg                       | jpeg      | png      | bmp                                                                                            | ico | svg | tif | css | js | otf | ttf | eot | woff | woff2` | global | no | **Cacheable Extensions:** List of file extensions (separated by pipes) that should be cached by the client. |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000` | multisite | no       | **Cache-Control Header:** Value for the Cache-Control HTTP header to control caching behavior. |
| `CLIENT_CACHE_ETAG`       | `yes`                      | multisite | no       | **Enable ETags:** Set to `yes` to send the HTTP ETag header for static resources.              |

!!! tip "Optimizing Cache Settings"
    For frequently updated content, consider using shorter max-age values. For content that rarely changes (like versioned JavaScript libraries or logos), use longer cache times. The default value of 15552000 seconds (180 days) is appropriate for most static assets.

!!! info "Browser Behavior"
    Different browsers implement caching slightly differently, but all modern browsers honor standard Cache-Control directives. ETags provide an additional validation mechanism that helps browsers determine if cached content is still valid.

### Example Configurations

=== "Basic Configuration"

    A simple configuration that enables caching for common static assets:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 day
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Aggressive Caching"

    Configuration optimized for maximum caching, suitable for sites with infrequently updated static content:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 year
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Mixed Content Strategy"

    For sites with a mix of frequently and infrequently updated content, consider using file versioning in your application and a configuration like this:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 week
    CLIENT_CACHE_ETAG: "yes"
    ```

## Country

STREAM support :white_check_mark:

The Country plugin enables geo-blocking functionality for your website, allowing you to restrict access based on the geographic location of your visitors. This feature helps you comply with regional regulations, prevent fraudulent activities from high-risk regions, or implement content restrictions based on geographic boundaries.

**Here's how the Country feature works:**

1. When a visitor accesses your website, BunkerWeb determines their country based on their IP address.
2. Your configuration specifies either a whitelist (allowed countries) or a blacklist (blocked countries).
3. If you've set up a whitelist, only visitors from countries on that list will be granted access.
4. If you've set up a blacklist, visitors from countries on that list will be denied access.
5. The result is cached to improve performance for repeat visitors from the same IP address.

### How to Use

Follow these steps to configure and use the Country feature:

1. **Define your strategy:** Decide whether you want to use a whitelist approach (allow only specific countries) or a blacklist approach (block specific countries).
2. **Configure country codes:** Add the ISO 3166-1 alpha-2 country codes (two-letter codes like US, GB, FR) to either the `WHITELIST_COUNTRY` or `BLACKLIST_COUNTRY` setting.
3. **Apply settings:** Once configured, the country-based restrictions will apply to all visitors to your site.
4. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on blocked requests by country.

### Configuration Settings

| Setting             | Default | Context   | Multiple | Description                                                                                                                     |
| ------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |         | multisite | no       | **Country Whitelist:** List of country codes (ISO 3166-1 alpha-2 format) separated by spaces. Only these countries are allowed. |
| `BLACKLIST_COUNTRY` |         | multisite | no       | **Country Blacklist:** List of country codes (ISO 3166-1 alpha-2 format) separated by spaces. These countries are blocked.      |

!!! tip "Whitelist vs. Blacklist"
    Choose the approach that best fits your needs:

    - Use the whitelist when you want to restrict access to a small number of countries.
    - Use the blacklist when you want to block access from specific problematic regions while allowing everyone else.

!!! warning "Precedence Rule"
    If both whitelist and blacklist are configured, the whitelist takes precedence. This means the system will first check if a country is whitelisted; if not, access is denied regardless of the blacklist setting.

!!! info "Country Detection"
    BunkerWeb uses the [lite db-ip mmdb database](https://db-ip.com/db/download/ip-to-country-lite) to determine the country of origin based on IP addresses.

### Example Configurations

=== "Whitelist Only"

    Allow access only from the United States, Canada, and the United Kingdom:

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Blacklist Only"

    Block access from specific countries while allowing all others:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "EU Access Only"

    Allow access only from European Union member states:

    ```yaml
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "High-Risk Countries Blocked"

    Block access from countries often associated with certain cyber threats:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```

## CrowdSec

STREAM support :x:

<figure markdown>
  ![Overview](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

The CrowdSec plugin integrates BunkerWeb with the CrowdSec security engine, providing an additional layer of protection against various cyber threats. This plugin acts as a [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) bouncer, denying requests based on decisions from the CrowdSec API.

CrowdSec is a modern, open-source security engine that detects and blocks malicious IP addresses based on behavior analysis and collective intelligence from its community. You can also configure [scenarios](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) to automatically ban IPs based on suspicious behaviors, benefiting from a crowdsourced blacklist.

**Here's how the CrowdSec feature works:**

1. The CrowdSec engine analyzes logs and detects suspicious activities on your infrastructure.
2. When a malicious activity is detected, CrowdSec creates a "decision" to block the offending IP address.
3. BunkerWeb, acting as a "bouncer," queries the CrowdSec Local API for decisions about incoming requests.
4. If a client's IP address has an active block decision, BunkerWeb denies access to the protected services.
5. Optionally, the Application Security Component can perform deep request inspection for enhanced security.

!!! success "Key benefits"

      1. **Community-Powered Security:** Benefit from threat intelligence shared across the CrowdSec user community.
      2. **Behavioral Analysis:** Detect sophisticated attacks based on behavior patterns, not just signatures.
      3. **Lightweight Integration:** Minimal performance impact on your BunkerWeb instance.
      4. **Multi-Level Protection:** Combine perimeter defense (IP blocking) with application security for in-depth protection.

### Setup

=== "Docker"
    **Acquisition file**

    You will need to run CrowdSec instance and configure it to parse BunkerWeb logs. Because BunkerWeb is based on NGINX, you can use the `nginx` value for the `type` parameter in your acquisition file (assuming that BunkerWeb logs are stored "as is" without additional data) :

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: nginx
    ```

    **Application Security Component (*optional*)**

    CrowdSec also provides an [Application Security Component](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) that can be used to protect your application from attacks. You can configure the plugin to send requests to the AppSec Component for further analysis. If you want to use it, you will need to create another acquisition file for the AppSec Component :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    For container-based integrations, we recommend you to redirect the logs of the BunkerWeb container to a syslog service that will store the logs so CrowdSec can access it easily. Here is an example configuration for syslog-ng that will store raw logs coming from BunkerWeb to a local `/var/log/bunkerweb.log` file :

    ```syslog
    @version: 4.8

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    Here is the docker-compose boilerplate that you can use (**don't forget to edit the bouncer key**) :

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for both services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.6.2-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          <<: *bw-env # We use the anchor to avoid repeating the same settings for all services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
          - bw-plugins
        logging:
          driver: syslog # Send logs to syslog
          options:
            syslog-address: "udp://10.10.10.254:514" # The IP address of the syslog service

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.2-rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # This is the address of the CrowdSec container API in the same network
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # Comment if you don't want to use the AppSec Component
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # Remember to set a stronger key for the bouncer
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      crowdsec:
        image: crowdsecurity/crowdsec:v1.6.6 # Use the latest version but always pin the version for a better stability/security
        volumes:
          - cs-data:/var/lib/crowdsec/data # To persist the CrowdSec data
          - bw-logs:/var/log:ro # The logs of BunkerWeb for CrowdSec to parse
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # The acquisition file for BunkerWeb logs
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Comment if you don't want to use the AppSec Component
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # Remember to set a stronger key for the bouncer
          COLLECTIONS: "crowdsecurity/nginx crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "crowdsecurity/nginx" # If you don't want to use the AppSec Component use this line instead
        networks:
          - bw-plugins

      syslog:
        image: balabit/syslog-ng:4.8.0
        # image: lscr.io/linuxserver/syslog-ng:4.8.1-r1-ls147 # For aarch64 architecture
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
            bw-plugins:
              ipv4_address: 10.10.10.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
      bw-plugins:
        ipam:
          driver: default
          config:
            - subnet: 10.10.10.0/24
    ```

=== "Linux"

    You'll need to install CrowdSec and configure it to parse BunkerWeb logs. To do so, you can follow the [official documentation](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    For CrowdSec to parse BunkerWeb logs, you have to add the following lines to your acquisition file located in `/etc/crowdsec/acquis.yaml` :

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: nginx
    ```

    Now we have to add our custom bouncer to the CrowdSec API. To do so, you can use the `cscli` tool :

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "API key"
        Keep the key generated by the `cscli` command, you will need it later.

    Now restart the CrowdSec service :

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Application Security Component (*optional*)**

    If you want to use the AppSec Component, you will need to create another acquisition file for it located in `/etc/crowdsec/acquis.d/appsec.yaml` :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    And you will need to install the AppSec Component's collections :

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Now you just have to restart the CrowdSec service :

    ```shell
    sudo systemctl restart crowdsec
    ```

    If you need more information about the AppSec Component, you can refer to the [official documentation](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    **Settings**

    Now you can configure the plugin by adding the following settings to your BunkerWeb configuration file :

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<The key provided by cscli>
    # Comment if you don't want to use the AppSec Component
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    And finally reload the BunkerWeb service :

    ```shell
    sudo systemctl reload bunkerweb
    ```

### Configuration Settings

| Setting                     | Default                | Context   | Multiple | Description                                                                                                      |
| --------------------------- | ---------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Enable CrowdSec:** Set to `yes` to enable the CrowdSec bouncer.                                                |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | no       | **CrowdSec API URL:** The address of the CrowdSec Local API service.                                             |
| `CROWDSEC_API_KEY`          |                        | global    | no       | **CrowdSec API Key:** The API key for authenticating with the CrowdSec API, obtained using `cscli bouncers add`. |
| `CROWDSEC_MODE`             | `live`                 | global    | no       | **Operation Mode:** Either `live` (query API for each request) or `stream` (periodically cache all decisions).   |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | no       | **Internal Traffic:** Set to `yes` to check internal traffic against CrowdSec decisions.                         |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | no       | **Request Timeout:** Timeout in milliseconds for HTTP requests to the CrowdSec Local API in live mode.           |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | no       | **Excluded Locations:** Comma-separated list of locations (URIs) to exclude from CrowdSec checks.                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | no       | **Cache Expiration:** The cache expiration time in seconds for IP decisions in live mode.                        |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | no       | **Update Frequency:** How often (in seconds) to pull new/expired decisions from the CrowdSec API in stream mode. |

#### Application Security Component Settings

| Setting                           | Default       | Context | Multiple | Description                                                                                            |
| --------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `CROWDSEC_APPSEC_URL`             |               | global  | no       | **AppSec URL:** The URL of the CrowdSec Application Security Component. Leave empty to disable AppSec. |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | global  | no       | **Failure Action:** Action to take when AppSec returns an error. Can be `passthrough` or `deny`.       |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | global  | no       | **Connect Timeout:** The timeout in milliseconds for connecting to the AppSec Component.               |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | global  | no       | **Send Timeout:** The timeout in milliseconds for sending data to the AppSec Component.                |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | global  | no       | **Process Timeout:** The timeout in milliseconds for processing the request in the AppSec Component.   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | global  | no       | **Always Send:** Set to `yes` to always send requests to AppSec, even if there's an IP-level decision. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | global  | no       | **SSL Verify:** Set to `yes` to verify the AppSec Component's SSL certificate.                         |

!!! info "About Operation Modes"
    - **Live mode** queries the CrowdSec API for each incoming request, providing real-time protection at the cost of higher latency.
    - **Stream mode** periodically downloads all decisions from the CrowdSec API and caches them locally, reducing latency but with a slight delay in applying new decisions.

### Example Configurations

=== "Basic Configuration"

    A simple configuration with CrowdSec running on the same host:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "live"
    ```

=== "Advanced Configuration with AppSec"

    A more comprehensive configuration including the Application Security Component:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # AppSec Configuration
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

## Custom SSL certificate

STREAM support :white_check_mark:

The Custom SSL certificate plugin allows you to use your own SSL/TLS certificates with BunkerWeb instead of the automatically generated ones. This feature is particularly useful when you have existing certificates from a trusted Certificate Authority (CA), need to use certificates with specific configurations, or want to maintain consistent certificate management across your infrastructure.

**Here's how the Custom SSL certificate feature works:**

1. You provide BunkerWeb with your certificate and private key files, either by specifying file paths or by providing the data in base64-encoded format.
2. BunkerWeb validates your certificate and key to ensure they're properly formatted and usable.
3. When a secure connection is established, BunkerWeb serves your custom certificate instead of the auto-generated one.
4. BunkerWeb automatically monitors your certificate's validity and will display warnings if it's approaching expiration.
5. You have full control over certificate management, allowing you to use certificates from any issuer you prefer.

### How to Use

Follow these steps to configure and use the Custom SSL certificate feature:

1. **Enable the feature:** Set the `USE_CUSTOM_SSL` setting to `yes` to enable custom certificate support.
2. **Choose a method:** Decide whether to provide certificates via file paths or as base64-encoded data, and set the priority with `CUSTOM_SSL_CERT_PRIORITY`.
3. **Provide certificate files:** If using file paths, specify the locations of your certificate and private key files.
4. **Or provide certificate data:** If using base64 data, provide your certificate and key as base64-encoded strings.
5. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb will automatically use your custom certificates for all HTTPS connections.

### Configuration Settings

| Setting                    | Default | Context   | Multiple | Description                                                                                                                   |
| -------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`    | multisite | no       | **Enable Custom SSL:** Set to `yes` to use your own certificate instead of the auto-generated one.                            |
| `CUSTOM_SSL_CERT_PRIORITY` | `file`  | multisite | no       | **Certificate Priority:** Choose whether to prioritize the certificate from file path or from base64 data (`file` or `data`). |
| `CUSTOM_SSL_CERT`          |         | multisite | no       | **Certificate Path:** Full path to your SSL certificate or certificate bundle file.                                           |
| `CUSTOM_SSL_KEY`           |         | multisite | no       | **Private Key Path:** Full path to your SSL private key file.                                                                 |
| `CUSTOM_SSL_CERT_DATA`     |         | multisite | no       | **Certificate Data:** Your certificate encoded in base64 format.                                                              |
| `CUSTOM_SSL_KEY_DATA`      |         | multisite | no       | **Private Key Data:** Your private key encoded in base64 format.                                                              |

!!! warning "Security Considerations"
    When using custom certificates, ensure your private key is properly secured and has appropriate permissions. The files must be readable by the BunkerWeb scheduler.

!!! tip "Certificate Format"
    BunkerWeb expects certificates in PEM format. If your certificate is in a different format, you may need to convert it first.

!!! info "Certificate Chains"
    If your certificate includes a chain (intermediates), you should provide the full certificate chain in the correct order, with your certificate first, followed by any intermediate certificates.

### Example Configurations

=== "Using File Paths"

    A configuration using certificate and key files on disk:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "Using Base64 Data"

    A configuration using base64-encoded certificate and key data:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```

=== "Fallback Configuration"

    A configuration that prioritizes files but falls back to base64 data if files are unavailable:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```

## DNSBL

STREAM support :white_check_mark:

The DNSBL (DNS-based Blacklist) plugin enables protection against known malicious IP addresses by checking client IPs against external DNSBL servers. This feature helps guard your website against spam, botnets, and various types of cyber threats by leveraging community-maintained lists of problematic IP addresses.

**Here's how the DNSBL feature works:**

1. When a visitor connects to your website, BunkerWeb checks their IP address against configured DNSBL servers.
2. The check is performed by sending a reverse DNS query to each DNSBL server with the visitor's IP address.
3. If the IP is listed in any of the DNSBL servers, access to your website is denied.
4. Results are cached to improve performance for repeat visitors from the same IP address.
5. Lookups are performed efficiently using asynchronous queries to minimize impact on page load times.

### How to Use

Follow these steps to configure and use the DNSBL feature:

1. **Enable the feature:** The DNSBL feature is disabled by default. Set the `USE_DNSBL` setting to `yes` to enable it.
2. **Configure DNSBL servers:** Add the domain names of the DNSBL services you want to use to the `DNSBL_LIST` setting.
3. **Apply settings:** Once configured, BunkerWeb will automatically check incoming connections against the specified DNSBL servers.
4. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on requests blocked by DNSBL checks.

### Configuration Settings

| Setting      | Default                                             | Context   | Multiple | Description                                                                     |
| ------------ | --------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | no       | **Enable DNSBL:** Set to `yes` to enable DNSBL checks for incoming connections. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | no       | **DNSBL Servers:** List of DNSBL server domains to check, separated by spaces.  |

!!! tip "Choosing DNSBL Servers"
    Choose reputable DNSBL providers to minimize false positives. The default list includes well-established services that are suitable for most websites:

    - **bl.blocklist.de:** Lists IPs that have been detected attacking other servers.
    - **sbl.spamhaus.org:** Focuses on spam sources and other malicious activities.
    - **xbl.spamhaus.org:** Targets infected systems, such as compromised machines or open proxies.

!!! info "How DNSBL Works"
    DNSBL servers work by responding to specially formatted DNS queries. When BunkerWeb checks an IP address, it reverses the IP and appends the DNSBL domain name. If the resulting DNS query returns a "success" response, the IP is considered blacklisted.

!!! warning "Performance Considerations"
    While BunkerWeb optimizes DNSBL lookups for performance, adding a large number of DNSBL servers could potentially impact response times. Start with a few reputable DNSBL servers and monitor performance before adding more.

### Example Configurations

=== "Basic Configuration"

    A simple configuration using the default DNSBL servers:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Minimal Configuration"

    A minimal configuration focusing on the most reliable DNSBL services:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    This configuration uses only:

    - **zen.spamhaus.org**: Spamhaus' combined list is often considered sufficient as a standalone solution due to its wide coverage and reputation for accuracy. It combines the SBL, XBL, and PBL lists in a single query, making it efficient and comprehensive.

## Database

STREAM support :white_check_mark:

The Database plugin provides a robust database integration system for BunkerWeb, enabling centralized storage and management of configuration data, logs, and other important information.

This core component supports multiple database engines, including SQLite, PostgreSQL, MySQL/MariaDB, and Oracle - allowing you to choose the database solution that best fits your environment and requirements.

**Here's how the Database feature works:**

1. BunkerWeb connects to your configured database using the provided URI, following SQLAlchemy format.
2. Critical configuration data, runtime information, and job logs are stored securely in the database.
3. Automatic maintenance processes keep your database optimized by managing data growth and cleaning up excess records.
4. For high-availability scenarios, you can configure a read-only database URI that serves as both a failover and a way to offload read operations.
5. Database operations are logged according to your specified log level, providing visibility into database interactions as needed.

### How to Use

Follow these steps to configure and use the Database feature:

1. **Choose a database engine:** Select from SQLite (default), PostgreSQL, MySQL/MariaDB, or Oracle based on your requirements.
2. **Configure the database URI:** Set the `DATABASE_URI` to connect to your primary database using the SQLAlchemy format.
3. **Optional read-only database:** For high-availability setups, configure a `DATABASE_URI_READONLY` as a fallback or for read operations.

### Configuration Settings

| Setting                  | Default                                   | Context | Multiple | Description                                                                                                           |
| ------------------------ | ----------------------------------------- | ------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URI`           | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global  | no       | **Database URI:** The primary database connection string, following the SQLAlchemy format.                            |
| `DATABASE_URI_READONLY`  |                                           | global  | no       | **Read-Only Database URI:** Optional database for read-only operations or as a failover if the main database is down. |
| `DATABASE_LOG_LEVEL`     | `warning`                                 | global  | no       | **Log Level:** The verbosity level for database logs. Options: `debug`, `info`, `warn`, `warning`, or `error`.        |
| `DATABASE_MAX_JOBS_RUNS` | `10000`                                   | global  | no       | **Maximum Job Runs:** The maximum number of job execution records to retain in the database before automatic cleanup. |

!!! tip "Database Selection"
    - **SQLite** (default): Ideal for single-node deployments or testing environments due to its simplicity and file-based nature.
    - **PostgreSQL**: Recommended for production environments with multiple BunkerWeb instances due to its robustness and concurrency support.
    - **MySQL/MariaDB**: A good alternative to PostgreSQL with similar production-grade capabilities.
    - **Oracle**: Suitable for enterprise environments where Oracle is already the standard database platform.

!!! info "SQLAlchemy URI Format"
    The database URI follows the SQLAlchemy format:

    - SQLite: `sqlite:////path/to/database.sqlite3`
    - PostgreSQL: `postgresql://username:password@hostname:port/database`
    - MySQL/MariaDB: `mysql://username:password@hostname:port/database` or `mariadb://username:password@hostname:port/database`
    - Oracle: `oracle://username:password@hostname:port/database`

!!! warning "Database Maintenance"
    The plugin automatically runs a daily job to clean up excess job runs based on the `DATABASE_MAX_JOBS_RUNS` setting. This prevents unbounded database growth while maintaining a useful history of job executions.

## Errors

STREAM support :x:

The Errors plugin provides customizable error handling for your website, allowing you to configure how HTTP error responses are displayed to users. This feature helps you present user-friendly, branded error pages that enhance user experience during error scenarios, instead of displaying the default server error pages that can appear technical and confusing to visitors.

**Here's how the Errors feature works:**

1. When a client encounters an HTTP error (like 400, 404, 500), BunkerWeb intercepts the error response.
2. Instead of showing the default error page, BunkerWeb displays a custom, professionally designed error page.
3. Error pages are fully customizable through your configuration, letting you specify custom pages for specific error codes.
4. The default error pages provide clear explanations, helping users understand what went wrong and what they can do next.

### How to Use

Follow these steps to configure and use the Errors feature:

1. **Define custom error pages:** Specify which HTTP error codes should use custom error pages with the `ERRORS` setting.
2. **Configure your error pages:** For each error code, you can use the default BunkerWeb error page or provide your own custom HTML page.
3. **Set intercepted error codes:** Select which error codes should always be handled by BunkerWeb with the `INTERCEPTED_ERROR_CODES` setting.
4. **Let BunkerWeb handle the rest:** Once configured, error handling happens automatically for all specified error codes.

### Configuration Settings

| Setting                   | Default                                           | Context   | Multiple | Description                                                                                                                                 |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | multisite | no       | **Custom Error Pages:** Map specific error codes to custom HTML files using the format `ERROR_CODE=/path/to/file.html`.                     |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | no       | **Intercepted Errors:** List of HTTP error codes that BunkerWeb should handle with its default error page when no custom page is specified. |

!!! tip "Error Page Design"
    The default BunkerWeb error pages are designed to be informative, user-friendly, and provide a professional appearance. They include:

    - Clear error descriptions
    - Information about what might have caused the error
    - Suggested actions for the user to resolve the issue
    - Visual indicators to help users understand if the issue is on their side or the server side

!!! info "Error Types"
    Error codes are categorized by type:

    - **4xx errors (client-side):** These indicate issues with the client's request, such as trying to access non-existent pages or lacking proper authentication.
    - **5xx errors (server-side):** These indicate issues with the server's ability to fulfill a valid request, like internal server errors or temporary unavailability.

### Example Configurations

=== "Default Error Handling"

    Let BunkerWeb handle common error codes with its default error pages:

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Custom Error Pages"

    Use custom error pages for specific error codes:

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Selective Error Handling"

    Only handle specific error codes with BunkerWeb:

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```

## Greylist

STREAM support :warning:

The Greylist plugin provides a flexible security approach that allows access to visitors while still maintaining security features.

Unlike traditional blacklist/whitelist approaches that completely block or allow access, greylisting creates a middle ground where certain visitors get access while still being subject to security checks.

**Here's how the Greylist feature works:**

1. You define criteria for visitors who should be "greylisted" (*IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns*).
2. When a visitor matches any of these criteria, they are allowed access to your site while the other security features remain active.
3. If a visitor doesn't match any greylist criteria, their access is denied.

### How to Use

Follow these steps to configure and use the Greylist feature:

1. **Enable the feature:** The Greylist feature is disabled by default. Set the `USE_GREYLIST` setting to `yes` to enable it.
2. **Configure greylist rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be greylisted.
3. **Add external sources:** Optionally configure URLs for automatically downloading and updating greylist data.
4. **Let BunkerWeb handle the rest:** Once configured, visitors matching your greylist criteria will be given improved access while maintaining essential security protections.

### Configuration Settings

**General**

| Setting        | Default | Context   | Multiple | Description                                                          |
| -------------- | ------- | --------- | -------- | -------------------------------------------------------------------- |
| `USE_GREYLIST` | `no`    | multisite | no       | **Enable Greylist:** Set to `yes` to enable the greylisting feature. |

=== "IP Address"
    **What this does:** Greylists visitors based on their IP address or network.

    | Setting            | Default | Context   | Multiple | Description                                                                                              |
    | ------------------ | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |         | multisite | no       | **IP Greylist:** List of IP addresses or networks (CIDR notation) to greylist, separated by spaces.      |
    | `GREYLIST_IP_URLS` |         | multisite | no       | **IP Greylist URLs:** List of URLs containing IP addresses or networks to greylist, separated by spaces. |

=== "Reverse DNS"
    **What this does:** Greylists visitors based on their domain name (in reverse).

    | Setting                | Default | Context   | Multiple | Description                                                                                            |
    | ---------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `GREYLIST_RDNS`        |         | multisite | no       | **rDNS Greylist:** List of reverse DNS suffixes to greylist, separated by spaces.                      |
    | `GREYLIST_RDNS_GLOBAL` | `yes`   | multisite | no       | **rDNS Global Only:** Only perform rDNS greylist checks on global IP addresses when set to `yes`.      |
    | `GREYLIST_RDNS_URLS`   |         | multisite | no       | **rDNS Greylist URLs:** List of URLs containing reverse DNS suffixes to greylist, separated by spaces. |

=== "ASN"
    **What this does:** Greylists visitors from specific network providers using Autonomous System Numbers.

    | Setting             | Default | Context   | Multiple | Description                                                                           |
    | ------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |         | multisite | no       | **ASN Greylist:** List of Autonomous System Numbers to greylist, separated by spaces. |
    | `GREYLIST_ASN_URLS` |         | multisite | no       | **ASN Greylist URLs:** List of URLs containing ASNs to greylist, separated by spaces. |

=== "User Agent"
    **What this does:** Greylists visitors based on what browser or tool they claim to be using.

    | Setting                    | Default | Context   | Multiple | Description                                                                                         |
    | -------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |         | multisite | no       | **User-Agent Greylist:** List of User-Agent patterns (PCRE regex) to greylist, separated by spaces. |
    | `GREYLIST_USER_AGENT_URLS` |         | multisite | no       | **User-Agent Greylist URLs:** List of URLs containing User-Agent patterns to greylist.              |

=== "URI"
    **What this does:** Greylists requests to specific URLs on your site.

    | Setting             | Default | Context   | Multiple | Description                                                                                   |
    | ------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |         | multisite | no       | **URI Greylist:** List of URI patterns (PCRE regex) to greylist, separated by spaces.         |
    | `GREYLIST_URI_URLS` |         | multisite | no       | **URI Greylist URLs:** List of URLs containing URI patterns to greylist, separated by spaces. |

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Greylists from URLs are automatically downloaded and updated hourly to ensure your protection remains current with the latest trusted sources.

### Example Configurations

=== "Basic Configuration"

    A simple configuration that greylists a company's internal network and crawler:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "Advanced Configuration"

    A more comprehensive configuration with multiple greylist criteria:

    ```yaml
    USE_GREYLIST: "yes"

    # Company assets and approved crawlers
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # Company and partner ASNs
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # External trusted sources
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Using Local Files"

    Configuration using local files for greylists:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///path/to/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///path/to/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///path/to/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///path/to/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///path/to/uri-greylist.txt"
    ```

## Gzip

STREAM support :x:

The GZIP plugin enhances website performance by compressing HTTP responses using the gzip algorithm. This feature helps reduce bandwidth usage and improve page load times by compressing web content before it's sent to the client's browser, resulting in faster content delivery and improved user experience.

**Here's how the GZIP feature works:**

1. When a client requests content from your website, BunkerWeb checks if the client supports gzip compression.
2. If supported, BunkerWeb compresses the response using the gzip algorithm at your configured compression level.
3. The compressed content is sent to the client with appropriate headers indicating gzip compression.
4. The client's browser decompresses the content before rendering it to the user.
5. Both bandwidth usage and page load times are reduced, improving overall site performance and user experience.

### How to Use

Follow these steps to configure and use the GZIP compression feature:

1. **Enable the feature:** The GZIP feature is disabled by default. Enable it by setting the `USE_GZIP` setting to `yes`.
2. **Configure MIME types:** Specify which content types should be compressed using the `GZIP_TYPES` setting.
3. **Set minimum size:** Define the minimum response size for compression with `GZIP_MIN_LENGTH` to avoid compressing tiny files.
4. **Choose compression level:** Select your preferred balance between speed and compression ratio with `GZIP_COMP_LEVEL`.
5. **Configure proxied settings:** Determine which proxied requests should be compressed using the `GZIP_PROXIED` setting.

### Configuration Settings

| Setting           | Default                                                                                                                                                                                                                                                                                                                                                                                                                          | Context   | Multiple | Description                                                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Enable GZIP:** Set to `yes` to enable GZIP compression.                                                                        |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **MIME Types:** List of content types that will be compressed with gzip.                                                         |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Minimum Size:** The minimum response size (in bytes) for GZIP compression to be applied.                                       |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Compression Level:** Level of compression from 1 (minimum compression) to 9 (maximum compression). Higher values use more CPU. |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | no       | **Proxied Requests:** Specifies which proxied requests should be compressed based on response headers.                           |

!!! tip "Optimizing Compression Level"
    The default compression level (5) offers a good balance between compression ratio and CPU usage. For static content or when server CPU resources are plentiful, consider increasing to 7-9 for maximum compression. For dynamic content or when CPU resources are limited, you might want to use 1-3 for faster compression with reasonable size reduction.

!!! info "Browser Support"
    GZIP is supported by all modern browsers and has been the standard compression method for HTTP responses for many years, ensuring excellent compatibility across devices and browsers.

!!! warning "Compression vs. CPU Usage"
    While GZIP compression reduces bandwidth and improves load times, higher compression levels consume more CPU resources. For high-traffic sites, find the right balance between compression efficiency and server performance.

### Example Configurations

=== "Basic Configuration"

    A standard configuration that enables GZIP with default settings:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Maximum Compression"

    Configuration optimized for maximum compression savings:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Balanced Performance"

    Configuration that balances compression ratio with CPU usage:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Proxied Content Focus"

    Configuration that focuses on properly handling compression for proxied content:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```

## HTML injection

STREAM support :x:

The HTML Injection plugin enables you to seamlessly add custom HTML code to your website's pages before either the closing `</body>` or `</head>` tags. This feature is particularly useful for adding analytics scripts, tracking pixels, custom JavaScript, CSS styles, or other third-party integrations without modifying your website's source code.

**Here's how the HTML Injection feature works:**

1. When a page is served from your website, BunkerWeb examines the HTML response.
2. If you've configured body injection, BunkerWeb inserts your custom HTML code just before the closing `</body>` tag.
3. If you've configured head injection, BunkerWeb inserts your custom HTML code just before the closing `</head>` tag.
4. The insertion happens automatically for all HTML pages served by your website.
5. This allows you to add scripts, styles, or other elements without modifying your application's code.

### How to Use

Follow these steps to configure and use the HTML Injection feature:

1. **Prepare your custom HTML:** Decide what HTML code you want to inject into your pages.
2. **Choose injection locations:** Determine whether you need to inject code in the `<head>` section, the `<body>` section, or both.
3. **Configure the settings:** Add your custom HTML to the appropriate settings (`INJECT_HEAD` and/or `INJECT_BODY`).
4. **Let BunkerWeb handle the rest:** Once configured, the HTML will be automatically injected into all served HTML pages.

### Configuration Settings

| Setting       | Default | Context   | Multiple | Description                                                           |
| ------------- | ------- | --------- | -------- | --------------------------------------------------------------------- |
| `INJECT_HEAD` |         | multisite | no       | **Head HTML Code:** The HTML code to inject before the `</head>` tag. |
| `INJECT_BODY` |         | multisite | no       | **Body HTML Code:** The HTML code to inject before the `</body>` tag. |

!!! tip "Best Practices"
    - For performance reasons, place JavaScript files at the end of the body to prevent render blocking.
    - Place CSS and critical JavaScript in the head section to avoid flash of unstyled content.
    - Be careful with injected content that could potentially break your site's functionality.

!!! info "Common Use Cases"
    - Adding analytics scripts (like Google Analytics, Matomo)
    - Integrating chat widgets or customer support tools
    - Including tracking pixels for marketing campaigns
    - Adding custom CSS styles or JavaScript functionality
    - Including third-party libraries without modifying your application code

### Example Configurations

=== "Google Analytics"

    Adding Google Analytics tracking to your website:

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "Custom Styles"

    Adding custom CSS styles to your website:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Multiple Integrations"

    Adding both custom styles and JavaScript:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Cookie Consent Banner"

    Adding a simple cookie consent banner:

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">This website uses cookies to ensure you get the best experience. <button onclick=\"acceptCookies()\">Accept</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```

## Headers

STREAM support :x:

The Headers plugin enables comprehensive management of HTTP headers sent to clients, enhancing both security and functionality of your website. This feature allows you to control which headers are sent, removed, or preserved from upstream servers, helping you implement security best practices like Content Security Policy, prevent information leakage, and set cookie security flags.

**Here's how the Headers feature works:**

1. When a client requests content from your website, BunkerWeb processes the response headers.
2. Security headers like `Strict-Transport-Security`, `Content-Security-Policy`, and `X-Frame-Options` are applied according to your configuration.
3. Custom headers can be added to provide additional information or functionality to clients.
4. Unwanted headers that might leak server information are automatically removed.
5. Cookies are modified to include appropriate security flags based on your settings.
6. Headers from upstream servers can be selectively preserved when needed.

### How to Use

Follow these steps to configure and use the Headers feature:

1. **Configure security headers:** Set values for common security headers like `Strict-Transport-Security`, `Content-Security-Policy`, and `X-Frame-Options`.
2. **Add custom headers:** Define any custom headers you want to add to responses using the `CUSTOM_HEADER` setting.
3. **Remove information leakage:** Use `REMOVE_HEADERS` to specify headers that should not be sent to clients.
4. **Set cookie security:** Configure cookie flags to enhance security with settings like `HttpOnly`, `SameSite`, and `Secure`.
5. **Preserve upstream headers:** If needed, specify which headers from upstream servers should be preserved using `KEEP_UPSTREAM_HEADERS`.

### Configuration Settings

| Setting                               | Default                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Context   | Multiple | Description                                                                                                         |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `CUSTOM_HEADER`                       |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | multisite | yes      | **Custom Header:** Add custom headers to responses in the format `HeaderName: HeaderValue`.                         |
| `REMOVE_HEADERS`                      | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Remove Headers:** List of headers to remove from responses, separated by spaces.                                  |
| `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | multisite | no       | **Keep Upstream Headers:** Headers to preserve from upstream servers, separated by spaces (or `*` for all).         |
| `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | multisite | no       | **HSTS:** Value for the Strict-Transport-Security header to enforce HTTPS connections.                              |
| `COOKIE_FLAGS`                        | `* HttpOnly SameSite=Lax`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | multisite | yes      | **Cookie Flags:** Flags automatically added to cookies (using nginx_cookie_flag_module format).                     |
| `COOKIE_AUTO_SECURE_FLAG`             | `yes`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | multisite | no       | **Auto Secure Flag:** When set to `yes`, automatically adds the Secure flag to all cookies on HTTPS connections.    |
| `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | multisite | no       | **CSP:** Value for the Content-Security-Policy header to control resource loading.                                  |
| `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **CSP Report Mode:** When `yes`, sends violations as reports instead of blocking them.                              |
| `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Referrer Policy:** Controls how much referrer information is included with requests.                              |
| `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=(), interest-cohort=()` | multisite | no       | **Permissions Policy:** Controls which browser features and APIs can be used in your site.                          |
| `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | multisite | no       | **X-Frame-Options:** Controls whether your site can be embedded in frames (helps prevent clickjacking).             |
| `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | multisite | no       | **X-Content-Type-Options:** Prevents browsers from MIME-sniffing a response away from its declared content type.    |
| `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | multisite | no       | **X-DNS-Prefetch-Control:** Controls DNS prefetching, a feature by which browsers proactively resolve domain names. |

!!! tip "Security Headers"
    The default header values follow security best practices and are suitable for most websites. These headers help protect against various attacks including XSS, clickjacking, and information leakage. Mozilla's [Observatory](https://observatory.mozilla.org/) is a great tool to check your site's security headers.

!!! info "Content Security Policy"
    Content-Security-Policy (CSP) is a powerful defense against content injection attacks. The default policy blocks inline scripts and restricts frame embedding, but you may need to customize it based on your site's requirements. Consider starting with CSP Report-Only mode (`CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"`) to identify needed changes before enforcing the policy.

!!! warning "Custom Headers"
    When adding custom headers, be aware that certain headers might have security implications. Custom headers should follow the format `HeaderName: HeaderValue` and be added individually using the `CUSTOM_HEADER` setting.

### Example Configurations

=== "Basic Security Headers"

    A standard configuration with essential security headers:

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "Enhanced Cookie Security"

    Configuration with robust cookie security settings:

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "Custom Headers for API"

    Configuration for an API service with custom headers:

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "Content Security Policy - Reporting Mode"

    Configuration to test CSP without breaking functionality:

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```

## Let's Encrypt

STREAM support :white_check_mark:

The Let's Encrypt plugin simplifies SSL/TLS certificate management by automating the creation, renewal, and configuration of free certificates from Let's Encrypt. This feature enables secure HTTPS connections for your websites without the complexity of manual certificate management, reducing both cost and administrative overhead.

**Here's how the Let's Encrypt feature works:**

1. When enabled, BunkerWeb automatically detects the domain names configured for your site.
2. BunkerWeb requests free SSL/TLS certificates from Let's Encrypt's certificate authority.
3. Domain ownership is verified through either HTTP challenges (proving you control the website) or DNS challenges (proving you control the domain's DNS).
4. Certificates are automatically installed and configured for your domains.
5. BunkerWeb handles certificate renewals in the background before expiration, ensuring continuous HTTPS availability.
6. The entire process is fully automated, requiring minimal intervention after initial setup.

!!! info "Prerequisites"
    To use this feature, ensure proper DNS **A records** are set up for each domain, pointing to the public IP(s) where BunkerWeb is accessible. Without correct DNS configuration, the domain verification process will fail.

### How to Use

Follow these steps to configure and use the Let's Encrypt feature:

1. **Enable the feature:** Set the `AUTO_LETS_ENCRYPT` setting to `yes` to enable automatic certificate issuance and renewal.
2. **Provide contact email:** Enter your email address with the `EMAIL_LETS_ENCRYPT` setting for important notifications about your certificates.
3. **Choose challenge type:** Select either `http` or `dns` verification with the `LETS_ENCRYPT_CHALLENGE` setting.
4. **Configure DNS provider:** If using DNS challenges, specify your DNS provider and credentials.
5. **Let BunkerWeb handle the rest:** Once configured, certificates are automatically issued, installed, and renewed as needed.

### Configuration Settings

| Setting                            | Default                  | Context   | Multiple | Description                                                                                                                                                                 |
| ---------------------------------- | ------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                | `no`                     | multisite | no       | **Enable Let's Encrypt:** Set to `yes` to enable automatic certificate issuance and renewal.                                                                                |
| `EMAIL_LETS_ENCRYPT`               | `contact@{FIRST_SERVER}` | multisite | no       | **Contact Email:** Email address used for Let's Encrypt notifications and included in certificates.                                                                         |
| `LETS_ENCRYPT_CHALLENGE`           | `http`                   | multisite | no       | **Challenge Type:** Method used to verify domain ownership. Options: `http` or `dns`.                                                                                       |
| `LETS_ENCRYPT_DNS_PROVIDER`        |                          | multisite | no       | **DNS Provider:** When using DNS challenges, the DNS provider to use (e.g., cloudflare, route53, digitalocean).                                                             |
| `LETS_ENCRYPT_DNS_PROPAGATION`     | `default`                | multisite | no       | **DNS Propagation:** The time to wait for DNS propagation in seconds. Set to `default` to use provider's recommended value.                                                 |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` |                          | multisite | yes      | **Credential Item:** Configuration items for DNS provider authentication (e.g., `cloudflare_api_token 123456`). Values can be raw text, base64 encoded, or a JSON object.   |
| `USE_LETS_ENCRYPT_WILDCARD`        | `no`                     | multisite | no       | **Wildcard Certificates:** When set to `yes`, creates wildcard certificates for all domains. Only available with DNS challenges.                                            |
| `USE_LETS_ENCRYPT_STAGING`         | `no`                     | multisite | no       | **Use Staging:** When set to `yes`, uses Let's Encrypt's staging environment for testing. Staging has higher rate limits but produces certificates not trusted by browsers. |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`     | `no`                     | global    | no       | **Clear Old Certificates:** When set to `yes`, removes old certificates that are no longer needed during renewal.                                                           |

!!! info "Information and behavior"
    - The `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting is a multiple setting and can be used to set multiple items for the DNS provider. The items will be saved as a cache file and Certbot will read the credentials from it.
    - If no `LETS_ENCRYPT_DNS_PROPAGATION` setting is set, the provider's default propagation time will be used.
    - Full Let's Encrypt automation using the `http` challenge works in stream mode as long as you open the `80/tcp` port from the outside. Use the `LISTEN_STREAM_PORT_SSL` setting to choose your listening SSL/TLS port.

!!! tip "HTTP vs. DNS Challenges"
    **HTTP Challenges** are easier to set up and work well for most websites:

    - Requires your website to be publicly accessible on port 80
    - Automatically configured by BunkerWeb
    - Cannot be used for wildcard certificates

    **DNS Challenges** offer more flexibility and are required for wildcard certificates:

    - Works even when your website is not publicly accessible
    - Requires DNS provider API credentials
    - Required for wildcard certificates (e.g., *.example.com)
    - Useful when port 80 is blocked or unavailable

!!! warning "Wildcard certificates"
    Wildcard certificates are only available with DNS challenges. If you want to use them, you must set the `USE_LETS_ENCRYPT_WILDCARD` setting to `yes` and properly configure your DNS provider credentials.

!!! warning "Rate Limits"
    Let's Encrypt imposes rate limits on certificate issuance. When testing configurations, use the staging environment by setting `USE_LETS_ENCRYPT_STAGING` to `yes` to avoid hitting production rate limits. Staging certificates are not trusted by browsers but are useful for validating your setup.

### Supported DNS Providers

The Let's Encrypt plugin supports a wide range of DNS providers for DNS challenges. Each provider requires specific credentials that must be provided using the `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting.

| Provider       | Description     | Mandatory Settings                                                                                           | Optional Settings                                                                                                                                                                                                                                                        | Documentation                                                                         |
| -------------- | --------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `cloudflare`   | Cloudflare      | either `api_token`<br>or `email` and `api_key`                                                               |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)             |
| `desec`        | deSEC           | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)    |
| `digitalocean` | DigitalOcean    | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)           |
| `dnsimple`     | DNSimple        | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)               |
| `dnsmadeeasy`  | DNS Made Easy   | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)            |
| `gehirn`       | Gehirn DNS      | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                 |
| `google`       | Google Cloud    | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (default: `service_account`)<br>`auth_uri` (default: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (default: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (default: `https://www.googleapis.com/oauth2/v1/certs`) | [Documentation](https://certbot-dns-google.readthedocs.io/en/stable/)                 |
| `linode`       | Linode          | `key`                                                                                                        |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                 |
| `luadns`       | LuaDNS          | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                 |
| `nsone`        | NS1             | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                  |
| `ovh`          | OVH             | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (default: `ovh-eu`)                                                                                                                                                                                                                                           | [Documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                    |
| `rfc2136`      | RFC 2136        | `server`<br>`name`<br>`secret`                                                                               | `port` (default: `53`)<br>`algorithm` (default: `HMAC-SHA512`)<br>`sign_query` (default: `false`)                                                                                                                                                                        | [Documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                |
| `route53`      | Amazon Route 53 | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                |
| `sakuracloud`  | Sakura Cloud    | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)            |
| `scaleway`     | Scaleway        | `application_token`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst) |

### Example Configurations

=== "Basic HTTP Challenge"

    Simple configuration using HTTP challenges for a single domain:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "Cloudflare DNS with Wildcard"

    Configuration for wildcard certificates using Cloudflare DNS:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "dns_cloudflare_api_token YOUR_API_TOKEN"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "AWS Route53 Configuration"

    Configuration using Amazon Route53 for DNS challenges:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id YOUR_ACCESS_KEY"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key YOUR_SECRET_KEY"
    ```

=== "Testing with Staging Environment"

    Configuration for testing setup with the staging environment:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    ```

=== "DigitalOcean with Custom Propagation Time"

    Configuration using DigitalOcean DNS with a longer propagation wait time:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "dns_digitalocean_token YOUR_API_TOKEN"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    Configuration using Google Cloud DNS with service account credentials:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id your-project-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id your-private-key-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key your-private-key"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email your-service-account-email"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id your-client-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url your-cert-url"
    ```

## Limit

STREAM support :warning:

The Limit plugin provides powerful request rate limiting and connection control capabilities for your website. This feature helps protect your services from abuse, denial-of-service attacks, and excessive resource consumption by restricting the number of requests and concurrent connections from individual IP addresses.

**Here's how the Limit feature works:**

1. **Rate Limiting:** The plugin tracks the number of requests from each client IP address to specific URLs.
2. If a client exceeds the configured request rate limit, subsequent requests are temporarily denied.
3. **Connection Limiting:** The plugin monitors and restricts the number of concurrent connections from each client IP.
4. Different connection limits can be applied based on the protocol being used (HTTP/1, HTTP/2, HTTP/3, or stream).
5. When limits are exceeded, clients receive a 429 "Too Many Requests" response, preventing server overload.

### How to Use

Follow these steps to configure and use the Limit feature:

1. **Configure request rate limiting:** Enable the feature with `USE_LIMIT_REQ` and define URL patterns and their corresponding rate limits.
2. **Configure connection limiting:** Enable with `USE_LIMIT_CONN` and set the maximum number of concurrent connections for different protocols.
3. **Apply granular control:** Create multiple rate limit rules for different URLs to provide varying levels of protection across your site.
4. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on limited requests.

### Configuration Settings

=== "Request Rate Limiting"

    | Setting          | Default | Context   | Multiple | Description                                                                                                                        |
    | ---------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_REQ`  | `yes`   | multisite | no       | **Enable Request Limiting:** Set to `yes` to enable request rate limiting feature.                                                 |
    | `LIMIT_REQ_URL`  | `/`     | multisite | yes      | **URL Pattern:** URL pattern (PCRE regex) where the rate limit will be applied, or `/` for all requests.                           |
    | `LIMIT_REQ_RATE` | `2r/s`  | multisite | yes      | **Rate Limit:** Maximum request rate in format `Nr/t` where N is the number of requests and t is s/m/h/d (second/minute/hour/day). |

    !!! tip "Rate Limiting Format"
        The rate limit format is specified as `Nr/t` where:

        - `N` is the number of requests allowed
        - `r` is a literal 'r' (for 'requests')
        - `/` is a literal slash
        - `t` is the time unit: `s` (second), `m` (minute), `h` (hour), or `d` (day)

        For example, `5r/m` means 5 requests per minute are allowed from each IP address.

=== "Connection Limiting"

    | Setting                 | Default | Context   | Multiple | Description                                                                                 |
    | ----------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_CONN`        | `yes`   | multisite | no       | **Enable Connection Limiting:** Set to `yes` to enable connection limiting feature.         |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`    | multisite | no       | **HTTP/1.X Connections:** Maximum number of concurrent HTTP/1.X connections per IP address. |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`   | multisite | no       | **HTTP/2 Streams:** Maximum number of concurrent HTTP/2 streams per IP address.             |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`   | multisite | no       | **HTTP/3 Streams:** Maximum number of concurrent HTTP/3 streams per IP address.             |
    | `LIMIT_CONN_MAX_STREAM` | `10`    | multisite | no       | **Stream Connections:** Maximum number of concurrent stream connections per IP address.     |


!!! info "Connection vs. Request Limiting"
    - **Connection limiting** restricts the number of simultaneous connections that a single IP can maintain.
    - **Request rate limiting** restricts how many requests an IP can make within a defined period of time.

    Using both provides comprehensive protection against different types of abuse.

!!! warning "Setting Appropriate Limits"
    Setting limits too restrictively may impact legitimate users, especially for HTTP/2 and HTTP/3 where browsers commonly use multiple streams. The default values are balanced for most use cases, but consider adjusting based on your application's needs and user behavior.

### Example Configurations

=== "Basic Protection"

    A simple configuration with default settings to protect your entire site:

    ```yaml
    USE_LIMIT_REQ: "yes"
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "2r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Protecting Specific Endpoints"

    Configuration with different rate limits for various endpoints:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Default rule for all requests
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "10r/s"

    # Stricter limit for login page
    LIMIT_REQ_URL_2: "^/login"
    LIMIT_REQ_RATE_2: "1r/s"

    # Stricter limit for API
    LIMIT_REQ_URL_3: "^/api/"
    LIMIT_REQ_RATE_3: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "High-Traffic Site Configuration"

    Configuration tuned for high-traffic sites with more permissive limits:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # General limit
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "30r/s"

    # Admin area protection
    LIMIT_REQ_URL_2: "^/admin/"
    LIMIT_REQ_RATE_2: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "50"
    LIMIT_CONN_MAX_HTTP2: "200"
    LIMIT_CONN_MAX_HTTP3: "200"
    LIMIT_CONN_MAX_STREAM: "30"
    ```

=== "API Server Configuration"

    Configuration optimized for an API server with rate limits expressed in requests per minute:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Public API endpoints
    LIMIT_REQ_URL: "^/api/public/"
    LIMIT_REQ_RATE: "120r/m"

    # Private API endpoints
    LIMIT_REQ_URL_2: "^/api/private/"
    LIMIT_REQ_RATE_2: "300r/m"

    # Authentication endpoint
    LIMIT_REQ_URL_3: "^/api/auth"
    LIMIT_REQ_RATE_3: "10r/m"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "20"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "20"
    ```

## Metrics

STREAM support :warning:

The Metrics plugin provides comprehensive monitoring and data collection capabilities for your BunkerWeb instance. This feature enables you to track various performance indicators, security events, and system statistics, giving you valuable insights into the behavior and health of your protected websites and services.

**Here's how the Metrics feature works:**

1. BunkerWeb collects key metrics during the processing of requests and responses.
2. These metrics include counters for blocked requests, performance measurements, and various security-related statistics.
3. The data is stored efficiently in memory, with configurable limits to prevent excessive resource usage.
4. For multi-instance setups, Redis can be used to centralize and aggregate metrics data.
5. The collected metrics can be accessed through the API or visualized in the [web UI](web-ui.md).
6. This information helps you identify security threats, troubleshoot issues, and optimize your configuration.

### How to Use

Follow these steps to configure and use the Metrics feature:

1. **Enable the feature:** Metrics collection is enabled by default. You can control this with the `USE_METRICS` setting.
2. **Configure memory allocation:** Set the amount of memory to allocate for metrics storage using the `METRICS_MEMORY_SIZE` setting.
3. **Set storage limits:** Define how many blocked requests to store per worker and in Redis with the respective settings.
4. **Access the data:** View the collected metrics through the [web UI](web-ui.md) or API endpoints.
5. **Analyze the information:** Use the gathered data to identify patterns, detect security issues, and optimize your configuration.

### Configuration Settings

| Setting                              | Default  | Context   | Multiple | Description                                                                           |
| ------------------------------------ | -------- | --------- | -------- | ------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`    | multisite | no       | **Enable Metrics:** Set to `yes` to enable collection and retrieval of metrics.       |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | no       | **Memory Size:** Size of the internal storage for metrics (e.g., `16m`, `32m`).       |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | no       | **Max Blocked Requests:** Maximum number of blocked requests to store per worker.     |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | no       | **Max Redis Blocked Requests:** Maximum number of blocked requests to store in Redis. |

!!! tip "Sizing Memory Allocation"
    The `METRICS_MEMORY_SIZE` setting should be adjusted based on your traffic volume and the number of instances. For high-traffic sites, consider increasing this value to ensure all metrics are captured without data loss.

!!! info "Redis Integration"
    When BunkerWeb is configured to use [Redis](#redis), the metrics plugin will automatically synchronize blocked request data to the Redis server. This provides a centralized view of security events across multiple BunkerWeb instances.

!!! warning "Performance Considerations"
    Setting very high values for `METRICS_MAX_BLOCKED_REQUESTS` or `METRICS_MAX_BLOCKED_REQUESTS_REDIS` can increase memory usage. Monitor your system resources and adjust these values according to your actual needs and available resources.

### Example Configurations

=== "Basic Configuration"

    Default configuration suitable for most deployments:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    ```

=== "Low-Resource Environment"

    Configuration optimized for environments with limited resources:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    ```

=== "High-Traffic Environment"

    Configuration for high-traffic websites that need to track more security events:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    ```

=== "Metrics Disabled"

    Configuration with metrics collection disabled:

    ```yaml
    USE_METRICS: "no"
    ```

## Migration <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :white_check_mark:

Migration of BunkerWeb configuration between instances made easy via the web UI

## Miscellaneous

STREAM support :warning:

The Miscellaneous plugin provides **essential baseline settings** that help maintain the security and functionality of your website. This core component offers comprehensive controls for:

- **Server behavior** - Configure how your server responds to various requests
- **HTTP settings** - Manage methods, request sizes, and protocol options
- **File management** - Control static file serving and optimize delivery
- **Protocol support** - Enable modern HTTP protocols for better performance
- **System configurations** - Extend functionality and improve security

Whether you need to restrict HTTP methods, manage request sizes, optimize file caching, or control how your server responds to various requests, this plugin gives you the tools to **fine-tune your web service's behavior** while optimizing both performance and security.

### Key Features

| Feature Category              | Description                                                                                        |
| ----------------------------- | -------------------------------------------------------------------------------------------------- |
| **HTTP Method Control**       | Define which HTTP methods are acceptable for your application                                      |
| **Default Server Protection** | Prevent unauthorized access through hostname mismatches and enforce SNI for secure connections     |
| **Request Size Management**   | Set limits for client request bodies and file uploads                                              |
| **Static File Serving**       | Configure and optimize delivery of static content from custom root folders                         |
| **File Caching**              | Improve performance through advanced file descriptor caching mechanisms with customizable settings |
| **Protocol Support**          | Configure modern HTTP protocol options (HTTP2/HTTP3) and Alt-Svc port settings                     |
| **Anonymous Reporting**       | Optional usage statistics reporting to help improve BunkerWeb                                      |
| **External Plugin Support**   | Extend functionality by integrating external plugins through URLs                                  |
| **HTTP Status Control**       | Configure how your server responds when denying requests (including connection termination)        |

### Configuration Guide

=== "Default Server Security"

    **Default Server Controls**

    | Setting                             | Default | Context | Multiple | Description                                                                                                         |
    | ----------------------------------- | ------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `DISABLE_DEFAULT_SERVER`            | `no`    | global  | no       | **Default Server:** Set to `yes` to disable the default server when no hostname matches the request.                |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`    | global  | no       | **Strict SNI:** When set to `yes`, requires SNI for HTTPS connections and rejects connections without valid SNI.    |
    | `DENY_HTTP_STATUS`                  | `403`   | global  | no       | **Deny HTTP Status:** HTTP status code to send when request is denied (403 or 444). Code 444 closes the connection. |

    !!! warning "Default Server Security"
        The default server settings can have significant security implications. When `DISABLE_DEFAULT_SERVER` is set to `yes`, clients that don't specify a valid hostname will receive an error, which can help prevent certain reconnaissance techniques.

        For SSL/TLS connections, enabling `DISABLE_DEFAULT_SERVER_STRICT_SNI` provides an additional layer of security by requiring a valid Server Name Indication.

=== "System Settings"

    **Plugin and System Management**

    | Setting                 | Default | Context | Multiple | Description                                                                    |
    | ----------------------- | ------- | ------- | -------- | ------------------------------------------------------------------------------ |
    | `SEND_ANONYMOUS_REPORT` | `yes`   | global  | no       | **Anonymous Reports:** Send anonymous usage reports to BunkerWeb maintainers.  |
    | `EXTERNAL_PLUGIN_URLS`  |         | global  | no       | **External Plugins:** URLs for external plugins to download (space-separated). |

    !!! info "Anonymous Reporting"
        Anonymous usage reports help the BunkerWeb team understand how the software is being used and identify areas for improvement. No sensitive data is collected.

=== "HTTP Methods"

    **HTTP Method Control**

    | Setting           | Default | Context | Multiple | Description |
    | ----------------- | ------- | ------- | -------- | ----------- |
    | `ALLOWED_METHODS` | `GET    | POST    | HEAD`    | multisite   | no | **HTTP Methods:** List of HTTP methods that are allowed, separated by pipe characters. |

    !!! tip "Allowed Methods"
        Restricting HTTP methods to only those needed by your application is a security best practice. For most websites, the default `GET|POST|HEAD` is sufficient. Add `PUT` and `DELETE` only if your application uses RESTful APIs that require these methods.

=== "Request Handling"

    **Request Size Limits**

    | Setting           | Default | Context   | Multiple | Description                                                                                        |
    | ----------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`   | multisite | no       | **Maximum Request Size:** The maximum allowed size for client request bodies (e.g., file uploads). |

    Common `MAX_CLIENT_SIZE` values:

    - `1m` - Suitable for forms with small file uploads
    - `10m` - Default, balanced for most websites
    - `100m` - For services that handle large file uploads

=== "Protocol Support"

    **HTTP Protocol Settings**

    | Setting              | Default | Context   | Multiple | Description                                                             |
    | -------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`   | multisite | no       | **HTTP Listen:** Respond to (insecure) HTTP requests when set to `yes`. |
    | `HTTP2`              | `yes`   | multisite | no       | **HTTP2:** Support HTTP2 protocol when HTTPS is enabled.                |
    | `HTTP3`              | `yes`   | multisite | no       | **HTTP3:** Support HTTP3 protocol when HTTPS is enabled.                |
    | `HTTP3_ALT_SVC_PORT` | `443`   | multisite | no       | **HTTP3 Alt-Svc Port:** Port to use in the Alt-Svc header for HTTP3.    |

    !!! info "Modern Protocol Support"
        HTTP/2 and HTTP/3 provide significant performance improvements over HTTP/1.1, including multiplexing, header compression, and reduced latency. Enabling these protocols is recommended for most websites.

=== "Static File Serving"

    **File Serving Configuration**

    | Setting       | Default | Context   | Multiple | Description                                                                                            |
    | ------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `SERVE_FILES` | `yes`   | multisite | no       | **Serve Files:** When set to `yes`, BunkerWeb will serve static files from the configured root folder. |
    | `ROOT_FOLDER` |         | multisite | no       | **Root Folder:** The directory from which to serve static files. Empty means use the default location. |

    To configure static file serving:

    - Enable or disable serving static files with the `SERVE_FILES` setting
    - Specify a custom root directory with `ROOT_FOLDER` or leave empty to use the default location

=== "File Caching"

    **File Cache Optimization**

    | Setting                    | Default                 | Context   | Multiple | Description                                                                                                     |
    | -------------------------- | ----------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no       | **Open File Cache:** Set to `yes` to enable caching of file descriptors and metadata to improve performance.    |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no       | **Cache Configuration:** Settings for the open file cache in nginx format.                                      |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no       | **Cache Errors:** Set to `yes` to cache file descriptor lookup errors as well as successful lookups.            |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no       | **Minimum Uses:** The minimum number of file accesses during the inactive period for the file to remain cached. |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no       | **Cache Valid:** The time after which open file cache elements are validated.                                   |

    To optimize file caching:

    - Enable the open file cache with `USE_OPEN_FILE_CACHE`
    - Configure cache parameters with `OPEN_FILE_CACHE` (format: `max=N inactive=Ts`)
    - Control error caching with `OPEN_FILE_CACHE_ERRORS`
    - Set minimum access count with `OPEN_FILE_CACHE_MIN_USES`
    - Define validation period with `OPEN_FILE_CACHE_VALID`

    !!! info "Open File Cache"
        Enabling the open file cache can significantly improve performance for websites serving many static files, as it reduces the need for repeated file system operations. However, in dynamic environments where files change frequently, you may need to adjust the cache validity period or disable this feature.

## ModSecurity

STREAM support :x:

The ModSecurity plugin integrates the powerful [ModSecurity](https://modsecurity.org) Web Application Firewall (WAF) into BunkerWeb. This integration delivers robust protection against a wide range of web attacks by leveraging the [OWASP Core Rule Set (CRS)](https://coreruleset.org) to detect and block threats such as SQL injection, cross-site scripting (XSS), local file inclusion, and more.

**How the ModSecurity feature works:**

1. When a request is received, ModSecurity evaluates it against the active rule set.
2. The OWASP Core Rule Set inspects headers, cookies, URL parameters, and body content.
3. Each detected violation adds to an overall "anomaly score."
4. If this score exceeds the configured threshold, the request is blocked.
5. Detailed logs are created to help diagnose which rules were triggered and why.

!!! success "Key benefits"

      1. **Industry Standard Protection:** Utilizes the widely used open-source ModSecurity firewall.
      2. **OWASP Core Rule Set:** Employs community-maintained rules covering the OWASP Top Ten and more.
      3. **Configurable Security Levels:** Adjust paranoia levels to balance security with potential false positives.
      4. **Detailed Logging:** Provides thorough audit logs for attack analysis.
      5. **Plugin Support:** Extend protection with optional CRS plugins tailored to your applications.

### How to Use

Follow these steps to configure and use ModSecurity:

1. **Enable the feature:** ModSecurity is enabled by default. Control this via the `USE_MODSECURITY` setting.
2. **Select a CRS version:** Choose a version of the OWASP Core Rule Set (v3, v4, or nightly).
3. **Add plugins:** Optionally activate CRS plugins to enhance rule coverage.
4. **Monitor and tune:** Use logs and the [web UI](web-ui.md) to identify false positives and adjust settings.

### Configuration Settings

| Setting                               | Default        | Context   | Multiple | Description                                                                                                 |
| ------------------------------------- | -------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`          | multisite | no       | **Enable ModSecurity:** Turn on ModSecurity Web Application Firewall protection.                            |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | no       | **Use Core Rule Set:** Enable the OWASP Core Rule Set for ModSecurity.                                      |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | no       | **CRS Version:** The version of the OWASP Core Rule Set to use. Options: `3`, `4`, or `nightly`.            |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | no       | **Rule Engine:** Control whether rules are enforced. Options: `On`, `DetectionOnly`, or `Off`.              |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | no       | **Audit Engine:** Control how audit logging works. Options: `On`, `Off`, or `RelevantOnly`.                 |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | no       | **Audit Log Parts:** Which parts of requests/responses to include in audit logs.                            |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | no       | **Request Body Limit:** Maximum size (in bytes) for request bodies that don't include file uploads.         |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | no       | **Enable CRS Plugins:** Enable additional plugin rule sets for the Core Rule Set.                           |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | no       | **CRS Plugins List:** Space-separated list of plugins to download and install (`plugin-name[/tag]` or URL). |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | no       | **Global CRS:** When enabled, applies CRS rules globally at the HTTP level rather than per server.          |

!!! warning "ModSecurity and the OWASP Core Rule Set"
    **We strongly recommend keeping both ModSecurity and the OWASP Core Rule Set (CRS) enabled** to provide robust protection against common web vulnerabilities. While occasional false positives may occur, they can be resolved with some effort by fine-tuning rules or using predefined exclusions.

    The CRS team actively maintains a list of exclusions for popular applications such as WordPress, Nextcloud, Drupal, and Cpanel, making it easier to integrate without impacting functionality. The security benefits far outweigh the minimal configuration effort required to address false positives.

### Available CRS Versions

Select a CRS version to best match your security needs:

- **`3`**: Stable [v3.3.7](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.7).
- **`4`**: Stable [v4.12.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.12.0) (**default**).
- **`nightly`**: [Nightly build](https://github.com/coreruleset/coreruleset/releases/tag/nightly) offering the latest rule updates.

!!! example "Nightly Build"
    The **nightly build** contains the most up-to-date rules, offering the latest protections against emerging threats. However, since it is updated daily and may include experimental or untested changes, it is recommended to first use the nightly build in a **staging environment** before deploying it in production.

!!! tip "Paranoia Levels"
    The OWASP Core Rule Set uses "paranoia levels" (PL) to control rule strictness:

    - **PL1 (default):** Basic protection with minimal false positives
    - **PL2:** Tighter security with more strict pattern matching
    - **PL3:** Enhanced security with stricter validation
    - **PL4:** Maximum security with very strict rules (may cause many false positives)

    You can set the paranoia level by adding a custom configuration file in `/etc/bunkerweb/configs/modsec-crs/`.

### Custom Configurations

Tuning ModSecurity and the OWASP Core Rule Set (CRS) can be achieved through custom configurations. These configurations allow you to customize behavior at specific stages of the security rules processing:

- **`modsec-crs`**: Applied **before** the OWASP Core Rule Set is loaded.
- **`modsec`**: Applied **after** the OWASP Core Rule Set is loaded. This is also used if the CRS is not loaded at all.
- **`crs-plugins-before`**: Applied **before** the CRS plugins are loaded.
- **`crs-plugins-after`**: Applied **after** the CRS plugins are loaded.

This structure provides flexibility, allowing you to fine-tune ModSecurity and CRS settings to suit your application's specific needs while maintaining a clear configuration flow.

#### Adding CRS Exclusions with `modsec-crs`

You can use a custom configuration of type `modsec-crs` to add exclusions for specific use cases, such as enabling predefined exclusions for WordPress:

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

In this example:

- The action is executed in **Phase 1** (early in the request lifecycle).
- It enables WordPress-specific CRS exclusions by setting the variable `tx.crs_exclusions_wordpress`.

#### Updating CRS Rules with `modsec`

To fine-tune the loaded CRS rules, you can use a custom configuration of type `modsec`. For example, you can remove specific rules or tags for certain request paths:

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

In this example:

- **Rule 1**: Removes rules tagged as `attack-xss` and `attack-rce` for requests to `/wp-admin/admin-ajax.php`.
- **Rule 2**: Removes rules tagged as `attack-xss` for requests to `/wp-admin/options.php`.
- **Rule 3**: Removes a specific rule (ID `930120`) for requests matching `/wp-json/yoast`.

!!! info "Order of execution"
    The execution order for ModSecurity in BunkerWeb is as follows, ensuring a clear and logical progression of rule application:

    1. **OWASP CRS Configuration**: Base configuration for the OWASP Core Rule Set.
    2. **Custom Plugins Configuration (`crs-plugins-before`)**: Settings specific to plugins, applied before any CRS rules.
    3. **Custom Plugin Rules (Before CRS Rules) (`crs-plugins-before`)**: Custom rules for plugins executed prior to CRS rules.
    4. **Downloaded Plugins Configuration**: Configuration for externally downloaded plugins.
    5. **Downloaded Plugin Rules (Before CRS Rules)**: Rules for downloaded plugins executed before CRS rules.
    6. **Custom CRS Rules (`modsec-crs`)**: User-defined rules applied before loading the CRS rules.
    7. **OWASP CRS Rules**: The core set of security rules provided by OWASP.
    8. **Custom Plugin Rules (After CRS Rules) (`crs-plugins-after`)**: Custom plugin rules executed after CRS rules.
    9. **Downloaded Plugin Rules (After CRS Rules)**: Rules for downloaded plugins executed after CRS rules.
    10. **Custom Rules (`modsec`)**: User-defined rules applied after all CRS and plugin rules.

    **Key Notes**:

    - **Pre-CRS customizations** (`crs-plugins-before`, `modsec-crs`) allow you to define exceptions or preparatory rules before the core CRS rules are loaded.
    - **Post-CRS customizations** (`crs-plugins-after`, `modsec`) are ideal for overriding or extending rules after CRS and plugin rules have been applied.
    - This structure provides maximum flexibility, enabling precise control over rule execution and customization while maintaining a strong security baseline.

### OWASP CRS Plugins

The OWASP Core Rule Set also supports a range of **plugins** designed to extend its functionality and improve compatibility with specific applications or environments. These plugins can help fine-tune the CRS for use with popular platforms such as WordPress, Nextcloud, and Drupal, or even custom setups. For more information and a list of available plugins, refer to the [OWASP CRS plugin registry](https://github.com/coreruleset/plugin-registry).

!!! tip "Plugin download"
    The `MODSECURITY_CRS_PLUGINS` setting allows you to download and install plugins to extend the functionality of the OWASP Core Rule Set (CRS). This setting accepts a list of plugin names with optional tags or URLs, making it easy to integrate additional security features tailored to your specific needs.

    Here's a non-exhaustive list of accepted values for the `MODSECURITY_CRS_PLUGINS` setting:

    * `fake-bot` - Download the latest release of the plugin.
    * `wordpress-rule-exclusions/v1.0.0` - Download the version 1.0.0 of the plugin.
    * `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Download the plugin directly from the URL.

!!! warning "False Positives"
    Higher security settings may block legitimate traffic. Start with the default settings and monitor logs before increasing security levels. Be prepared to add exclusion rules for your specific application needs.

### Example Configurations

=== "Basic Configuration"

    A standard configuration with ModSecurity and CRS v4 enabled:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Detection-Only Mode"

    Configuration for monitoring potential threats without blocking:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Advanced Configuration with Plugins"

    Configuration with CRS v4 and plugins enabled for additional protection:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Legacy Configuration"

    Configuration using CRS v3 for compatibility with older setups:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Global ModSecurity"

    Configuration applying ModSecurity globally across all HTTP connections:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Nightly Build with Custom Plugins"

    Configuration using the nightly build of CRS with custom plugins:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

## Monitoring <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

BunkerWeb monitoring pro system. This plugin is a prerequisite for some other plugins.

| Setting                        | Default | Context | Multiple | Description                                                                 |
| ------------------------------ | ------- | ------- | -------- | --------------------------------------------------------------------------- |
| `USE_MONITORING`               | `yes`   | global  | no       | Enable monitoring of BunkerWeb.                                             |
| `MONITORING_METRICS_DICT_SIZE` | `10M`   | global  | no       | Size of the dict to store monitoring metrics.                               |
| `MONITORING_IGNORE_URLS`       |         | global  | no       | List of URLs to ignore when monitoring separated with spaces (e.g. /health) |

## PHP

STREAM support :x:

Manage local or remote PHP-FPM.

| Setting           | Default | Context   | Multiple | Description                                                  |
| ----------------- | ------- | --------- | -------- | ------------------------------------------------------------ |
| `REMOTE_PHP`      |         | multisite | no       | Hostname of the remote PHP-FPM instance.                     |
| `REMOTE_PHP_PATH` |         | multisite | no       | Root folder containing files in the remote PHP-FPM instance. |
| `REMOTE_PHP_PORT` | `9000`  | multisite | no       | Port of the remote PHP-FPM instance.                         |
| `LOCAL_PHP`       |         | multisite | no       | Path to the PHP-FPM socket file.                             |
| `LOCAL_PHP_PATH`  |         | multisite | no       | Root folder containing files in the local PHP-FPM instance.  |

## Pro

STREAM support :x:

Pro settings for the Pro version of BunkerWeb.

| Setting           | Default | Context | Multiple | Description                                       |
| ----------------- | ------- | ------- | -------- | ------------------------------------------------- |
| `PRO_LICENSE_KEY` |         | global  | no       | The License Key for the Pro version of BunkerWeb. |

## Prometheus exporter <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Prometheus exporter for BunkerWeb internal metrics.

| Setting                        | Default                                               | Context | Multiple | Description                                                              |
| ------------------------------ | ----------------------------------------------------- | ------- | -------- | ------------------------------------------------------------------------ |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global  | no       | Enable the Prometheus export.                                            |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global  | no       | Listening IP of the Prometheus exporter.                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global  | no       | Listening port of the Prometheus exporter.                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global  | no       | HTTP URL of the Prometheus exporter.                                     |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global  | no       | List of IP/networks allowed to contact the Prometheus exporter endpoint. |

## Real IP

STREAM support :warning:

Get real IP of clients when BunkerWeb is behind a reverse proxy / load balancer.

| Setting              | Default                                   | Context   | Multiple | Description                                                                                                                                                                               |
| -------------------- | ----------------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | no       | Retrieve the real IP of client.                                                                                                                                                           |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | no       | Enable PROXY protocol communication.                                                                                                                                                      |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | no       | List of trusted IPs / networks, separated with spaces, where proxied requests come from.                                                                                                  |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | no       | HTTP header containing the real IP or special value proxy_protocol for PROXY protocol.                                                                                                    |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | no       | Perform a recursive search in the header container IP address.                                                                                                                            |
| `REAL_IP_FROM_URLS`  |                                           | multisite | no       | List of URLs containing trusted IPs / networks, separated with spaces, where proxied requests come from. Also supports file:// URLs and and auth basic using http://user:pass@url scheme. |

## Redirect

STREAM support :x:

Manage HTTP redirects.

| Setting                   | Default | Context   | Multiple | Description                                       |
| ------------------------- | ------- | --------- | -------- | ------------------------------------------------- |
| `REDIRECT_TO`             |         | multisite | no       | Redirect a whole site to another one.             |
| `REDIRECT_TO_REQUEST_URI` | `no`    | multisite | no       | Append the requested URI to the redirect address. |
| `REDIRECT_TO_STATUS_CODE` | `301`   | multisite | no       | Status code to send to client when redirecting.   |

## Redis

STREAM support :white_check_mark:

Redis server configuration when using BunkerWeb in cluster mode.

| Setting                   | Default | Context | Multiple | Description                                                         |
| ------------------------- | ------- | ------- | -------- | ------------------------------------------------------------------- |
| `USE_REDIS`               | `no`    | global  | no       | Activate Redis.                                                     |
| `REDIS_HOST`              |         | global  | no       | Redis server IP or hostname.                                        |
| `REDIS_PORT`              | `6379`  | global  | no       | Redis server port.                                                  |
| `REDIS_DATABASE`          | `0`     | global  | no       | Redis database number.                                              |
| `REDIS_SSL`               | `no`    | global  | no       | Use SSL/TLS connection with Redis server.                           |
| `REDIS_SSL_VERIFY`        | `no`    | global  | no       | Verify the certificate of Redis server.                             |
| `REDIS_TIMEOUT`           | `1000`  | global  | no       | Redis server timeout (in ms) for connect, read and write.           |
| `REDIS_USERNAME`          |         | global  | no       | Redis username used in AUTH command.                                |
| `REDIS_PASSWORD`          |         | global  | no       | Redis password used in AUTH command.                                |
| `REDIS_SENTINEL_HOSTS`    |         | global  | no       | Redis sentinel hosts with format host:[port] separated with spaces. |
| `REDIS_SENTINEL_USERNAME` |         | global  | no       | Redis sentinel username.                                            |
| `REDIS_SENTINEL_PASSWORD` |         | global  | no       | Redis sentinel password.                                            |
| `REDIS_SENTINEL_MASTER`   |         | global  | no       | Redis sentinel master name.                                         |
| `REDIS_KEEPALIVE_IDLE`    | `30000` | global  | no       | Max idle time (in ms) before closing redis connection in the pool.  |
| `REDIS_KEEPALIVE_POOL`    | `10`    | global  | no       | Max number of redis connection(s) kept in the pool.                 |

## Reporting <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Regular reporting of important data from BunkerWeb (global, attacks, bans, requests, reasons, AS...). Monitoring pro plugin needed to work.

| Setting                        | Default            | Context | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------ | ------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global  | no       | Enable sending the report via email.                                                                                               |
| `USE_REPORTING_WEBHOOK`        | `no`               | global  | no       | Enable sending the report via webhook.                                                                                             |
| `REPORTING_SCHEDULE`           | `weekly`           | global  | no       | The frequency at which reports are sent.                                                                                           |
| `REPORTING_WEBHOOK_URLS`       |                    | global  | no       | List of webhook URLs to receive the report in Markdown (separated by spaces).                                                      |
| `REPORTING_SMTP_EMAILS`        |                    | global  | no       | List of email addresses to receive the report in HTML format (separated by spaces).                                                |
| `REPORTING_SMTP_HOST`          |                    | global  | no       | The host server used for SMTP sending.                                                                                             |
| `REPORTING_SMTP_PORT`          | `465`              | global  | no       | The port used for SMTP. Please note that there are different standards depending on the type of connection (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global  | no       | The email address used as the sender. Note that 2FA must be disabled for this email address.                                       |
| `REPORTING_SMTP_FROM_USER`     |                    | global  | no       | The user authentication value for sending via the from email address.                                                              |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global  | no       | The password authentication value for sending via the from email address.                                                          |
| `REPORTING_SMTP_SSL`           | `SSL`              | global  | no       | Determine whether or not to use a secure connection for SMTP.                                                                      |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global  | no       | The subject line of the email.                                                                                                     |

## Reverse proxy

STREAM support :warning:

Manage reverse proxy configurations.

| Setting                                 | Default                            | Context   | Multiple | Description                                                                                                                   |
| --------------------------------------- | ---------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `USE_REVERSE_PROXY`                     | `no`                               | multisite | no       | Activate reverse proxy mode.                                                                                                  |
| `REVERSE_PROXY_INTERCEPT_ERRORS`        | `yes`                              | multisite | no       | Intercept and rewrite errors.                                                                                                 |
| `REVERSE_PROXY_CUSTOM_HOST`             |                                    | multisite | no       | Override Host header sent to upstream server.                                                                                 |
| `REVERSE_PROXY_SSL_SNI`                 | `no`                               | multisite | no       | Enable or disable sending SNI to upstream server.                                                                             |
| `REVERSE_PROXY_SSL_SNI_NAME`            |                                    | multisite | no       | Sets the SNI host to send to upstream server.                                                                                 |
| `REVERSE_PROXY_HOST`                    |                                    | multisite | yes      | Full URL of the proxied resource (proxy_pass).                                                                                |
| `REVERSE_PROXY_URL`                     | `/`                                | multisite | yes      | Location URL that will be proxied.                                                                                            |
| `REVERSE_PROXY_WS`                      | `no`                               | multisite | yes      | Enable websocket on the proxied resource.                                                                                     |
| `REVERSE_PROXY_HEADERS`                 |                                    | multisite | yes      | List of HTTP headers to send to proxied resource separated with semicolons (values for proxy_set_header directive).           |
| `REVERSE_PROXY_HEADERS_CLIENT`          |                                    | multisite | yes      | List of HTTP headers to send to client separated with semicolons (values for add_header directive).                           |
| `REVERSE_PROXY_BUFFERING`               | `yes`                              | multisite | yes      | Enable or disable buffering of responses from proxied resource.                                                               |
| `REVERSE_PROXY_KEEPALIVE`               | `no`                               | multisite | yes      | Enable or disable keepalive connections with the proxied resource.                                                            |
| `REVERSE_PROXY_AUTH_REQUEST`            |                                    | multisite | yes      | Enable authentication using an external provider (value of auth_request directive).                                           |
| `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |                                    | multisite | yes      | Redirect clients to sign-in URL when using REVERSE_PROXY_AUTH_REQUEST (used when auth_request call returned 401).             |
| `REVERSE_PROXY_AUTH_REQUEST_SET`        |                                    | multisite | yes      | List of variables to set from the authentication provider, separated with semicolons (values of auth_request_set directives). |
| `REVERSE_PROXY_CONNECT_TIMEOUT`         | `60s`                              | multisite | yes      | Timeout when connecting to the proxied resource.                                                                              |
| `REVERSE_PROXY_READ_TIMEOUT`            | `60s`                              | multisite | yes      | Timeout when reading from the proxied resource.                                                                               |
| `REVERSE_PROXY_SEND_TIMEOUT`            | `60s`                              | multisite | yes      | Timeout when sending to the proxied resource.                                                                                 |
| `REVERSE_PROXY_INCLUDES`                |                                    | multisite | yes      | Additional configuration to include in the location block, separated with spaces.                                             |
| `REVERSE_PROXY_PASS_REQUEST_BODY`       | `yes`                              | multisite | yes      | Enable or disable passing the request body to the proxied resource.                                                           |
| `USE_PROXY_CACHE`                       | `no`                               | multisite | no       | Enable or disable caching of the proxied resources.                                                                           |
| `PROXY_CACHE_PATH_LEVELS`               | `1:2`                              | global    | no       | Hierarchy levels of the cache.                                                                                                |
| `PROXY_CACHE_PATH_ZONE_SIZE`            | `10m`                              | global    | no       | Maximum size of cached metadata when caching proxied resources.                                                               |
| `PROXY_CACHE_PATH_PARAMS`               | `max_size=100m`                    | global    | no       | Additional parameters to add to the proxy_cache directive.                                                                    |
| `PROXY_CACHE_METHODS`                   | `GET HEAD`                         | multisite | no       | HTTP methods that should trigger a cache operation.                                                                           |
| `PROXY_CACHE_MIN_USES`                  | `2`                                | multisite | no       | The minimum number of requests before a response is cached.                                                                   |
| `PROXY_CACHE_KEY`                       | `$scheme$host$request_uri`         | multisite | no       | The key used to uniquely identify a cached response.                                                                          |
| `PROXY_CACHE_VALID`                     | `200=24h 301=1h 302=24h`           | multisite | no       | Define the caching time depending on the HTTP status code (list of status=time), separated with spaces.                       |
| `PROXY_NO_CACHE`                        | `$http_pragma $http_authorization` | multisite | no       | Conditions to disable caching of responses.                                                                                   |
| `PROXY_CACHE_BYPASS`                    | `0`                                | multisite | no       | Conditions to bypass caching of responses.                                                                                    |
| `PROXY_BUFFERS`                         |                                    | multisite | no       | Value for proxy_buffers directive.                                                                                            |
| `PROXY_BUFFER_SIZE`                     |                                    | multisite | no       | Value for proxy_buffer_size directive.                                                                                        |
| `PROXY_BUSY_BUFFERS_SIZE`               |                                    | multisite | no       | Value for proxy_busy_buffers_size directive.                                                                                  |

## Reverse scan

STREAM support :white_check_mark:

Scan clients ports to detect proxies or servers.

| Setting                | Default                    | Context   | Multiple | Description                                                        |
| ---------------------- | -------------------------- | --------- | -------- | ------------------------------------------------------------------ |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | no       | Enable scanning of clients ports and deny access if one is opened. |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | no       | List of port to scan when using reverse scan feature.              |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | no       | Specify the maximum timeout (in ms) when scanning a port.          |

## SSL

STREAM support :white_check_mark:

Handle SSL/TLS related settings.

| Setting                       | Default           | Context   | Multiple | Description                                                                                                                  |
| ----------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | no       | Redirect all HTTP request to HTTPS.                                                                                          |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | no       | Try to detect if HTTPS is used and activate HTTP to HTTPS redirection if that's the case.                                    |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | no       | The supported version of TLS. We recommend the default value TLSv1.2 TLSv1.3 for compatibility reasons.                      |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | no       | Preset security level for SSL cipher suites. 'Modern' is most secure but may not work with older devices.                    |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | no       | Custom SSL cipher suite string. If specified, overrides the SSL Ciphers Level. Leave empty to use level-based configuration. |

## Security.txt

STREAM support :white_check_mark:

Manage the security.txt file. A proposed standard which allows websites to define security policies.

| Setting                        | Default                     | Context   | Multiple | Description                                                                                                                                                                                                                                                              |
| ------------------------------ | --------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_SECURITYTXT`              | `no`                        | multisite | no       | Enable security.txt file.                                                                                                                                                                                                                                                |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | no       | Indicates the URI where the "security.txt" file will be accessible from.                                                                                                                                                                                                 |
| `SECURITYTXT_CONTACT`          |                             | multisite | yes      | Indicates a method that researchers should use for reporting security vulnerabilities such as an email address, a phone number, and/or a web page with contact information. (If the value is empty, the security.txt file will not be created as it is a required field) |
| `SECURITYTXT_EXPIRES`          |                             | multisite | no       | Indicates the date and time after which the data contained in the "security.txt" file is considered stale and should not be used (If the value is empty, the value will always be the current date and time + 1 year).                                                   |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | yes      | Indicates an encryption key that security researchers should use for encrypted communication.                                                                                                                                                                            |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | yes      | Indicates a link to a page where security researchers are recognized for their reports.                                                                                                                                                                                  |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | no       | Can be used to indicate a set of natural languages that are preferred when submitting security reports.                                                                                                                                                                  |
| `SECURITYTXT_CANONICAL`        |                             | multisite | yes      | Indicates the canonical URIs where the "security.txt" file is located, which is usually something like "https://example.com/.well-known/security.txt". (If the value is empty, the default value will be automatically generated from the site URL + SECURITYTXT_URI)    |
| `SECURITYTXT_POLICY`           |                             | multisite | yes      | Indicates a link to where the vulnerability disclosure policy is located.                                                                                                                                                                                                |
| `SECURITYTXT_HIRING`           |                             | multisite | yes      | Used for linking to the vendor's security-related job positions.                                                                                                                                                                                                         |
| `SECURITYTXT_CSAF`             |                             | multisite | yes      | A link to the provider-metadata.json of your CSAF (Common Security Advisory Framework) provider.                                                                                                                                                                         |

## Self-signed certificate

STREAM support :white_check_mark:

Generate self-signed certificate.

| Setting                    | Default                | Context   | Multiple | Description                               |
| -------------------------- | ---------------------- | --------- | -------- | ----------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL` | `no`                   | multisite | no       | Generate and use self-signed certificate. |
| `SELF_SIGNED_SSL_EXPIRY`   | `365`                  | multisite | no       | Self-signed certificate expiry in days.   |
| `SELF_SIGNED_SSL_SUBJ`     | `/CN=www.example.com/` | multisite | no       | Self-signed certificate subject.          |

## Sessions

STREAM support :white_check_mark:

Management of session used by other plugins.

| Setting                     | Default  | Context | Multiple | Description                                                                       |
| --------------------------- | -------- | ------- | -------- | --------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global  | no       | Secret used to encrypt sessions variables for storing data related to challenges. |
| `SESSIONS_NAME`             | `random` | global  | no       | Name of the cookie given to clients.                                              |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global  | no       | Maximum time (in seconds) of inactivity before the session is invalidated.        |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global  | no       | Maximum time (in seconds) before a session must be renewed.                       |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global  | no       | Maximum time (in seconds) before a session is destroyed.                          |
| `SESSIONS_CHECK_IP`         | `yes`    | global  | no       | Destroy session if IP address is different than original one.                     |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global  | no       | Destroy session if User-Agent is different than original one.                     |

## UI

STREAM support :x:

Integrate easily the BunkerWeb UI.

| Setting   | Default | Context   | Multiple | Description                                  |
| --------- | ------- | --------- | -------- | -------------------------------------------- |
| `USE_UI`  | `no`    | multisite | no       | Use UI                                       |
| `UI_HOST` |         | global    | no       | Address of the web UI used for initial setup |

## User Manager <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Add the possibility to manage users on the web interface

| Setting             | Default | Context | Multiple | Description                                     |
| ------------------- | ------- | ------- | -------- | ----------------------------------------------- |
| `USERS_REQUIRE_2FA` | `no`    | global  | no       | Require two-factor authentication for all users |

## Whitelist

STREAM support :warning:

Allow access based on internal and external IP/network/rDNS/ASN whitelists.

| Setting                     | Default                                                                                                                                                                      | Context   | Multiple | Description                                                                                                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_WHITELIST`             | `yes`                                                                                                                                                                        | multisite | no       | Activate whitelist feature.                                                                                                                                         |
| `WHITELIST_IP`              |                                                                                                                                                                              | multisite | no       | List of IP/network, separated with spaces, to put into the whitelist.                                                                                               |
| `WHITELIST_RDNS`            | `.google.com .googlebot.com .yandex.ru .yandex.net .yandex.com .search.msn.com .baidu.com .baidu.jp .crawl.yahoo.net .fwd.linkedin.com .twitter.com .twttr.com .discord.com` | multisite | no       | List of reverse DNS suffixes, separated with spaces, to whitelist.                                                                                                  |
| `WHITELIST_RDNS_GLOBAL`     | `yes`                                                                                                                                                                        | multisite | no       | Only perform RDNS whitelist checks on global IP addresses.                                                                                                          |
| `WHITELIST_ASN`             | `32934`                                                                                                                                                                      | multisite | no       | List of ASN numbers, separated with spaces, to whitelist.                                                                                                           |
| `WHITELIST_USER_AGENT`      |                                                                                                                                                                              | multisite | no       | List of User-Agent (PCRE regex), separated with spaces, to whitelist.                                                                                               |
| `WHITELIST_URI`             |                                                                                                                                                                              | multisite | no       | List of URI (PCRE regex), separated with spaces, to whitelist.                                                                                                      |
| `WHITELIST_IP_URLS`         |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing good IP/network to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.      |
| `WHITELIST_RDNS_URLS`       |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing reverse DNS suffixes to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme. |
| `WHITELIST_ASN_URLS`        |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing ASN to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.                  |
| `WHITELIST_USER_AGENT_URLS` |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing good User-Agent to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.      |
| `WHITELIST_URI_URLS`        |                                                                                                                                                                              | multisite | no       | List of URLs, separated with spaces, containing bad URI to whitelist. Also supports file:// URLs and and auth basic using http://user:pass@url scheme.              |
