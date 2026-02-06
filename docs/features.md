# Features

This section contains the full list of settings supported by BunkerWeb. If you are not yet familiar with BunkerWeb, you should first read the [concepts](concepts.md) section of the documentation. Please follow the instructions for your own [integration](integrations.md) on how to apply the settings.

## Global settings


STREAM support :warning:

The General plugin provides the core configuration framework for BunkerWeb, allowing you to define essential settings that control how your web services are protected and delivered. This foundational plugin manages fundamental aspects like security modes, server defaults, logging behavior, and critical operational parameters for the entire BunkerWeb ecosystem.

**How it works:**

1. When BunkerWeb starts, the General plugin loads and applies your core configuration settings.
2. Security modes are set either globally or per-site, determining the level of protection applied.
3. Default server settings establish fallback values for any unspecified multisite configurations.
4. Logging parameters control what information is recorded and how it's formatted.
5. These settings create the foundation upon which all other BunkerWeb plugins and functionality operate.

### Multisite Mode {#multisite-mode}

When `MULTISITE` is set to `yes`, BunkerWeb can host and protect multiple websites, each with its own unique configuration. This feature is particularly useful for scenarios such as:

- Hosting multiple domains with distinct configurations
- Running multiple applications with varying security requirements
- Applying tailored security policies to different services

In multisite mode, each site is identified by a unique `SERVER_NAME`. To apply settings specific to a site, prepend the primary `SERVER_NAME` to the setting name. For example:

- `www.example.com_USE_ANTIBOT=captcha` enables CAPTCHA for `www.example.com`.
- `myapp.example.com_USE_GZIP=yes` enables GZIP compression for `myapp.example.com`.

This approach ensures that settings are applied to the correct site in a multisite environment.

### Multiple Settings {#multiple-settings}

Some settings in BunkerWeb support multiple configurations for the same feature. To define multiple groups of settings, append a numeric suffix to the setting name. For example:

- `REVERSE_PROXY_URL_1=/subdir` and `REVERSE_PROXY_HOST_1=http://myhost1` configure the first reverse proxy.
- `REVERSE_PROXY_URL_2=/anotherdir` and `REVERSE_PROXY_HOST_2=http://myhost2` configure the second reverse proxy.

This pattern allows you to manage multiple configurations for features like reverse proxies, ports, or other settings that require distinct values for different use cases.

### Plugin Execution Order {#plugin-order}

You can reorder plugin execution with space-separated lists:

- Global phases: `PLUGINS_ORDER_INIT`, `PLUGINS_ORDER_INIT_WORKER`, `PLUGINS_ORDER_TIMER`.
- Per-site phases: `PLUGINS_ORDER_SET`, `PLUGINS_ORDER_ACCESS`, `PLUGINS_ORDER_SSL_CERTIFICATE`, `PLUGINS_ORDER_HEADER`, `PLUGINS_ORDER_LOG`, `PLUGINS_ORDER_PREREAD`, `PLUGINS_ORDER_LOG_STREAM`, `PLUGINS_ORDER_LOG_DEFAULT`.
- Semantics: listed plugins run first for that phase; all remaining plugins still run afterward in their normal sequence. Separate IDs with spaces only.

### Security Modes {#security-modes}

The `SECURITY_MODE` setting determines how BunkerWeb handles detected threats. This flexible feature allows you to choose between monitoring or actively blocking suspicious activity, depending on your specific needs:

- **`detect`**: Logs potential threats without blocking access. This mode is useful for identifying and analyzing false positives in a safe, non-disruptive manner.
- **`block`** (default): Actively blocks detected threats while logging incidents to prevent unauthorized access and protect your application.

Switching to `detect` mode can help you identify and resolve potential false positives without disrupting legitimate clients. Once these issues are addressed, you can confidently switch back to `block` mode for full protection.

### Configuration Settings

=== "Core Settings"

    | Setting               | Default           | Context   | Multiple | Description                                                                                         |
    | --------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------- |
    | `SERVER_NAME`         | `www.example.com` | multisite | No       | **Primary Domain:** The main domain name for this site. Required in multisite mode.                 |
    | `BUNKERWEB_INSTANCES` | `127.0.0.1`       | global    | No       | **BunkerWeb Instances:** List of BunkerWeb instances separated with spaces.                         |
    | `MULTISITE`           | `no`              | global    | No       | **Multiple Sites:** Set to `yes` to enable hosting multiple websites with different configurations. |
    | `SECURITY_MODE`       | `block`           | multisite | No       | **Security Level:** Controls the level of security enforcement. Options: `detect` or `block`.       |
    | `SERVER_TYPE`         | `http`            | multisite | No       | **Server Type:** Defines if the server is `http` or `stream` type.                                  |

=== "API Settings"

    | Setting            | Default       | Context | Multiple | Description                                                                                             |
    | ------------------ | ------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `USE_API`          | `yes`         | global  | No       | **Activate API:** Activate the API to control BunkerWeb.                                                |
    | `API_HTTP_PORT`    | `5000`        | global  | No       | **API Port:** Listen port number for the API.                                                           |
    | `API_HTTPS_PORT`   | `5443`        | global  | No       | **API HTTPS Port:** Listen port number (TLS) for the API.                                               |
    | `API_LISTEN_HTTP`  | `yes`         | global  | No       | **API Listen HTTP:** Enable HTTP listener for the API.                                                  |
    | `API_LISTEN_HTTPS` | `no`          | global  | No       | **API Listen HTTPS:** Enable HTTPS (TLS) listener for the API.                                          |
    | `API_LISTEN_IP`    | `0.0.0.0`     | global  | No       | **API Listen IP:** Listen IP address for the API.                                                       |
    | `API_SERVER_NAME`  | `bwapi`       | global  | No       | **API Server Name:** Server name (virtual host) for the API.                                            |
    | `API_WHITELIST_IP` | `127.0.0.0/8` | global  | No       | **API Whitelist IP:** List of IP/network allowed to contact the API.                                    |
    | `API_TOKEN`        |               | global  | No       | **API Access Token (optional):** If set, all API requests must include `Authorization: Bearer <token>`. |

    Note: for bootstrap reasons, if you enable `API_TOKEN` you must set it in the environment of BOTH the BunkerWeb instance and the Scheduler. The Scheduler automatically includes the `Authorization` header when `API_TOKEN` is present in its environment. If not set, no header is sent and BunkerWeb will not enforce token auth. You can expose the API over HTTPS by setting `API_LISTEN_HTTPS=yes` (port: `API_HTTPS_PORT`, default `5443`).

    Example test with curl (replace token and host):

    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://<bunkerweb-host>:5000/ping

    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         --insecure \
         https://<bunkerweb-host>:5443/ping
    ```

=== "Network & Port Settings"

    | Setting         | Default      | Context | Multiple | Description                                           |
    | --------------- | ------------ | ------- | -------- | ----------------------------------------------------- |
    | `HTTP_PORT`     | `8080`       | global  | Yes      | **HTTP Port:** Port number for HTTP traffic.          |
    | `HTTPS_PORT`    | `8443`       | global  | Yes      | **HTTPS Port:** Port number for HTTPS traffic.        |
    | `USE_IPV6`      | `no`         | global  | No       | **IPv6 Support:** Enable IPv6 connectivity.           |
    | `DNS_RESOLVERS` | `127.0.0.11` | global  | No       | **DNS Resolvers:** DNS addresses of resolvers to use. |

=== "Stream Server Settings"

    | Setting                  | Default | Context   | Multiple | Description                                                    |
    | ------------------------ | ------- | --------- | -------- | -------------------------------------------------------------- |
    | `LISTEN_STREAM`          | `yes`   | multisite | No       | **Listen Stream:** Enable listening for non-ssl (passthrough). |
    | `LISTEN_STREAM_PORT`     | `1337`  | multisite | Yes      | **Stream Port:** Listening port for non-ssl (passthrough).     |
    | `LISTEN_STREAM_PORT_SSL` | `4242`  | multisite | Yes      | **Stream SSL Port:** Listening port for ssl (passthrough).     |
    | `USE_TCP`                | `yes`   | multisite | No       | **TCP Listen:** Enable TCP listening (stream).                 |
    | `USE_UDP`                | `no`    | multisite | No       | **UDP Listen:** Enable UDP listening (stream).                 |

=== "Worker Settings"

    | Setting                | Default | Context | Multiple | Description                                                                             |
    | ---------------------- | ------- | ------- | -------- | --------------------------------------------------------------------------------------- |
    | `WORKER_PROCESSES`     | `auto`  | global  | No       | **Worker Processes:** Number of worker processes. Set to `auto` to use available cores. |
    | `WORKER_CONNECTIONS`   | `1024`  | global  | No       | **Worker Connections:** Maximum number of connections per worker.                       |
    | `WORKER_RLIMIT_NOFILE` | `2048`  | global  | No       | **File Descriptors Limit:** Maximum number of open files per worker.                    |

=== "Memory Settings"

    | Setting                        | Default | Context | Multiple | Description                                                                     |
    | ------------------------------ | ------- | ------- | -------- | ------------------------------------------------------------------------------- |
    | `WORKERLOCK_MEMORY_SIZE`       | `48k`   | global  | No       | **Workerlock Memory Size:** Size of lua_shared_dict for initialization workers. |
    | `DATASTORE_MEMORY_SIZE`        | `64m`   | global  | No       | **Datastore Memory Size:** Size of the internal datastore.                      |
    | `CACHESTORE_MEMORY_SIZE`       | `64m`   | global  | No       | **Cachestore Memory Size:** Size of the internal cachestore.                    |
    | `CACHESTORE_IPC_MEMORY_SIZE`   | `16m`   | global  | No       | **Cachestore IPC Memory Size:** Size of the internal cachestore (ipc).          |
    | `CACHESTORE_MISS_MEMORY_SIZE`  | `16m`   | global  | No       | **Cachestore Miss Memory Size:** Size of the internal cachestore (miss).        |
    | `CACHESTORE_LOCKS_MEMORY_SIZE` | `16m`   | global  | No       | **Cachestore Locks Memory Size:** Size of the internal cachestore (locks).      |

=== "Logging Settings"

    | Setting            | Default                                                                                                                                    | Context | Multiple | Description                                                                                                                                      |
    | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `LOG_FORMAT`       | `$host $remote_addr - $request_id $remote_user [$time_local] \"$request\" $status $body_bytes_sent \"$http_referer\" \"$http_user_agent\"` | global  | No       | **Log Format:** The format to use for access logs.                                                                                               |
    | `ACCESS_LOG`       | `/var/log/bunkerweb/access.log`                                                                                                            | global  | Yes      | **Access Log Path:** File path, `syslog:server=host[:port][,param=value]`, or shared buffer `memory:name:size`; set to `off` to disable logging. |
    | `ERROR_LOG`        | `/var/log/bunkerweb/error.log`                                                                                                             | global  | Yes      | **Error Log Path:** File path, `stderr`, `syslog:server=host[:port][,param=value]`, or `memory:size`.                                            |
    | `LOG_LEVEL`        | `notice`                                                                                                                                   | global  | Yes      | **Log Level:** Verbosity level for error logs. Options: `debug`, `info`, `notice`, `warn`, `error`, `crit`, `alert`, `emerg`.                    |
    | `TIMERS_LOG_LEVEL` | `debug`                                                                                                                                    | global  | No       | **Timers Log Level:** Log level for timers. Options: `debug`, `info`, `notice`, `warn`, `err`, `crit`, `alert`, `emerg`.                         |

    !!! tip "Logging Best Practices"
        - For production environments, use the `notice`, `warn`, or `error` log levels to minimize log volume.
        - For debugging issues, temporarily set the log level to `debug` to get more detailed information.

=== "Integration Settings"

    | Setting                  | Default | Context   | Multiple | Description                                                                                                     |
    | ------------------------ | ------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
    | `AUTOCONF_MODE`          | `no`    | global    | No       | **Autoconf Mode:** Enable Autoconf Docker integration.                                                          |
    | `SWARM_MODE`             | `no`    | global    | No       | **Swarm Mode:** Enable Docker Swarm integration.                                                                |
    | `KUBERNETES_MODE`        | `no`    | global    | No       | **Kubernetes Mode:** Enable Kubernetes integration.                                                             |
    | `KEEP_CONFIG_ON_RESTART` | `no`    | global    | No       | **Keep Config on Restart:** Keep the configuration on restart. Set to 'yes' to prevent config reset on restart. |
    | `USE_TEMPLATE`           |         | multisite | No       | **Use Template:** Config template to use that will override the default values of specific settings.            |

=== "Nginx Settings"

    | Setting                         | Default       | Context | Multiple | Description                                                                               |
    | ------------------------------- | ------------- | ------- | -------- | ----------------------------------------------------------------------------------------- |
    | `NGINX_PREFIX`                  | `/etc/nginx/` | global  | No       | **Nginx Prefix:** Where nginx will search for configurations.                             |
    | `SERVER_NAMES_HASH_BUCKET_SIZE` |               | global  | No       | **Server Names Hash Bucket Size:** Value for the server_names_hash_bucket_size directive. |

### Example Configurations

=== "Basic Production Setup"

    A standard configuration for a production site with strict security:

    ```yaml
    SECURITY_MODE: "block"
    SERVER_NAME: "example.com"
    LOG_LEVEL: "notice"
    ```

=== "Development Mode"

    Configuration for a development environment with extra logging:

    ```yaml
    SECURITY_MODE: "detect"
    SERVER_NAME: "dev.example.com"
    LOG_LEVEL: "debug"
    ```

=== "Multisite Configuration"

    Configuration for hosting multiple websites:

    ```yaml
    MULTISITE: "yes"

    # First site
    site1.example.com_SERVER_NAME: "site1.example.com"
    site1.example.com_SECURITY_MODE: "block"

    # Second site
    site2.example.com_SERVER_NAME: "site2.example.com"
    site2.example.com_SECURITY_MODE: "detect"
    ```

=== "Stream Server Configuration"

    Configuration for a TCP/UDP server:

    ```yaml
    SERVER_TYPE: "stream"
    SERVER_NAME: "stream.example.com"
    LISTEN_STREAM: "yes"
    LISTEN_STREAM_PORT: "1337"
    USE_TCP: "yes"
    USE_UDP: "no"
    ```

## Anti DDoS <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


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

**How it works:**

1.  When a user visits your site, BunkerWeb checks if they've already passed the antibot challenge.
2.  If not, the user is redirected to a challenge page.
3.  The user must complete the challenge (e.g., solve a CAPTCHA, run JavaScript).
4.  If the challenge is successful, the user is redirected back to the page they were originally trying to visit and can browse your website normally.

### How to Use

Follow these steps to enable and configure the Antibot feature:

1. **Choose a challenge type:** Decide which type of antibot challenge to use (e.g., [captcha](#__tabbed_3_3), [hcaptcha](#__tabbed_3_5), [javascript](#__tabbed_3_2)).
2. **Enable the feature:** Set the `USE_ANTIBOT` setting to your chosen challenge type in your BunkerWeb configuration.
3. **Configure the settings:** Adjust the other `ANTIBOT_*` settings as needed. For reCAPTCHA, hCaptcha, Turnstile, and mCaptcha, you must create an account with the respective service and obtain API keys.
4. **Important:** Ensure the `ANTIBOT_URI` is a unique URL on your site that is not in use.

!!! important "About the `ANTIBOT_URI` Setting"
    Ensure the `ANTIBOT_URI` is a unique URL on your site that is not in use.

!!! warning "Session Configuration in Clustered Environments"
    The antibot feature uses cookies to track whether a user has completed the challenge. If you are running BunkerWeb in a clustered environment (multiple BunkerWeb instances), you **must** configure session management properly. This involves setting the `SESSIONS_SECRET` and `SESSIONS_NAME` settings to the **same values** across all BunkerWeb instances. If you don't do this, users may be repeatedly prompted to complete the antibot challenge. You can find more information about session configuration [here](#sessions).

### Common Settings

The following settings are shared across all challenge mechanisms:

| Setting                | Default      | Context   | Multiple | Description                                                                                                                                         |
| ---------------------- | ------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
| `ANTIBOT_TIME_RESOLVE` | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
| `ANTIBOT_TIME_VALID`   | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

### Excluding Traffic from Challenges

BunkerWeb allows you to specify certain users, IPs, or requests that should bypass the antibot challenge completely. This is useful for whitelisting trusted services, internal networks, or specific pages that should always be accessible without challenge:

| Setting                     | Default | Context   | Multiple | Description                                                                                                                            |
| --------------------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |         | multisite | no       | **Excluded URLs:** List of URI regex patterns separated by spaces that should bypass the challenge.                                    |
| `ANTIBOT_IGNORE_IP`         |         | multisite | no       | **Excluded IPs:** List of IP addresses or CIDR ranges separated by spaces that should bypass the challenge.                            |
| `ANTIBOT_IGNORE_RDNS`       |         | multisite | no       | **Excluded Reverse DNS:** List of reverse DNS suffixes separated by spaces that should bypass the challenge.                           |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`   | multisite | no       | **Global IPs Only:** If set to `yes`, only perform reverse DNS checks on public IP addresses.                                          |
| `ANTIBOT_IGNORE_ASN`        |         | multisite | no       | **Excluded ASNs:** List of ASN numbers separated by spaces that should bypass the challenge.                                           |
| `ANTIBOT_IGNORE_USER_AGENT` |         | multisite | no       | **Excluded User Agents:** List of User-Agent regex patterns separated by spaces that should bypass the challenge.                      |
| `ANTIBOT_IGNORE_COUNTRY`    |         | multisite | no       | **Excluded Countries:** List of ISO 3166-1 alpha-2 country codes separated by spaces that should bypass the challenge.                 |
| `ANTIBOT_ONLY_COUNTRY`      |         | multisite | no       | **Only Challenge Countries:** List of ISO 3166-1 alpha-2 country codes that must solve the challenge. All other countries are skipped. |

!!! note "Behavior of Country-Based Settings"
      - When both `ANTIBOT_IGNORE_COUNTRY` and `ANTIBOT_ONLY_COUNTRY` are set, the ignore list takes precedence—countries listed in both will bypass the challenge.
      - Private or unknown IP addresses bypass the challenge when `ANTIBOT_ONLY_COUNTRY` is set because no country code can be determined.

**Examples:**

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  This will exclude all URIs starting with `/api/`, `/webhook/`, or `/assets/` from the antibot challenge.

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  This will exclude the internal network `192.168.1.0/24` and the specific IP `10.0.0.1` from the antibot challenge.

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  This will exclude requests from hosts with reverse DNS ending with `googlebot.com` or `bingbot.com` from the antibot challenge.

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  This will exclude requests from ASN 15169 (Google) and ASN 8075 (Microsoft) from the antibot challenge.

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  This will exclude requests with User-Agents matching the specified regex pattern from the antibot challenge.

- `ANTIBOT_IGNORE_COUNTRY: "US CA"`
  This will bypass the antibot challenge for visitors located in the United States or Canada.

- `ANTIBOT_ONLY_COUNTRY: "CN RU"`
  This will only challenge visitors from China or Russia. Requests from other countries (or private IP ranges) skip the challenge.

### Supported Challenge Mechanisms

=== "Cookie"

    The Cookie challenge is a lightweight mechanism that relies on setting a cookie in the user's browser. When a user accesses the site, the server sends a cookie to the client. On subsequent requests, the server checks for the presence of this cookie to verify that the user is legitimate. This method is simple and effective for basic bot protection without requiring additional user interaction.

    **How it works:**

    1. The server generates a unique cookie and sends it to the client.
    2. The client must return the cookie in subsequent requests.
    3. If the cookie is missing or invalid, the user is redirected to the challenge page.

    **Configuration Settings:**

    | Setting       | Default | Context   | Multiple | Description                                                         |
    | ------------- | ------- | --------- | -------- | ------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`    | multisite | no       | **Enable Antibot:** Set to `cookie` to enable the Cookie challenge. |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "JavaScript"

    The JavaScript challenge requires the client to solve a computational task using JavaScript. This mechanism ensures that the client has JavaScript enabled and can execute the required code, which is typically beyond the capability of most bots.

    **How it works:**

    1. The server sends a JavaScript script to the client.
    2. The script performs a computational task (e.g., hashing) and submits the result back to the server.
    3. The server verifies the result to confirm the client's legitimacy.

    **Key Features:**

    - The challenge dynamically generates a unique task for each client.
    - The computational task involves hashing with specific conditions (e.g., finding a hash with a certain prefix).

    **Configuration Settings:**

    | Setting       | Default | Context   | Multiple | Description                                                                 |
    | ------------- | ------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`    | multisite | no       | **Enable Antibot:** Set to `javascript` to enable the JavaScript challenge. |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "Captcha"

    The Captcha challenge is a homemade mechanism that generates image-based challenges hosted entirely within your BunkerWeb environment. It tests users' ability to recognize and interpret randomized characters, ensuring automated bots are effectively blocked without relying on external services.

    **How it works:**

    1. The server generates a CAPTCHA image containing randomized characters.
    2. The user must enter the characters displayed in the image into a text field.
    3. The server validates the user's input against the generated CAPTCHA.

    **Key Features:**

    - Fully self-hosted, eliminating the need for third-party APIs.
    - Dynamically generated challenges ensure uniqueness for each user session.
    - Uses a customizable character set for CAPTCHA generation.

    **Supported Characters:**

    The CAPTCHA system supports the following character types:

    - **Letters:** All lowercase (a-z) and uppercase (A-Z) letters
    - **Numbers:** 2, 3, 4, 5, 6, 7, 8, 9 (excludes 0 and 1 to avoid confusion)
    - **Special characters:** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    To have the complete set of supported characters, refer to the [Font charmap](https://www.dafont.com/moms-typewriter.charmap?back=theme) of the font used for the CAPTCHA.

    **Configuration Settings:**

    | Setting                    | Default                                                | Context   | Multiple | Description                                                                                                                                                                                                                    |
    | -------------------------- | ------------------------------------------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `USE_ANTIBOT`              | `no`                                                   | multisite | no       | **Enable Antibot:** Set to `captcha` to enable the Captcha challenge.                                                                                                                                                          |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | multisite | no       | **Captcha Alphabet:** A string of characters to use for generating the CAPTCHA. Supported characters: all letters (a-z, A-Z), numbers 2-9 (excludes 0 and 1), and special characters: ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "reCAPTCHA"

    When enabled, reCAPTCHA runs in the background (v3) to assign a score based on user behavior. A score lower than the configured threshold will prompt further verification or block the request. For visible challenges (v2), users must interact with the reCAPTCHA widget before continuing.

    There are now two ways to integrate reCAPTCHA:
    - The classic version (site/secret keys, v2/v3 verify endpoint)
    - The new version using Google Cloud (Project ID + API key). The classic version remains available and can be toggled with `ANTIBOT_RECAPTCHA_CLASSIC`.

    For the classic version, obtain your site and secret keys from the [Google reCAPTCHA admin console](https://www.google.com/recaptcha/admin).
    For the new version, create a reCAPTCHA key in your Google Cloud project and use the Project ID and an API key (see the [Google Cloud reCAPTCHA console](https://console.cloud.google.com/security/recaptcha)). A site key is still required.

    **Configuration Settings:**

    | Setting                        | Default | Context   | Multiple | Description                                                                                        |
    | ------------------------------ | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`                  | `no`    | multisite | no       | Enable antibot; set to `recaptcha` to enable reCAPTCHA.                                            |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`   | multisite | no       | Use classic reCAPTCHA. Set to `no` to use the new Google Cloud-based version.                      |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |         | multisite | no       | reCAPTCHA site key. Required for both classic and new versions.                                    |
    | `ANTIBOT_RECAPTCHA_SECRET`     |         | multisite | no       | reCAPTCHA secret key. Required for the classic version only.                                       |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |         | multisite | no       | Google Cloud Project ID. Required for the new version only.                                        |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |         | multisite | no       | Google Cloud API key used to call the reCAPTCHA Enterprise API. Required for the new version only. |
    | `ANTIBOT_RECAPTCHA_JA3`        |         | multisite | no       | Optional JA3 TLS fingerprint to include in Enterprise assessments.                                 |
    | `ANTIBOT_RECAPTCHA_JA4`        |         | multisite | no       | Optional JA4 TLS fingerprint to include in Enterprise assessments.                                 |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`   | multisite | no       | Minimum score required to pass (applies to both classic v3 and the new version).                   |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "hCaptcha"

    When enabled, hCaptcha provides an effective alternative to reCAPTCHA by verifying user interactions without relying on a scoring mechanism. It challenges users with a simple, interactive test to confirm their legitimacy.

    To integrate hCaptcha with BunkerWeb, you must obtain the necessary credentials from the hCaptcha dashboard at [hCaptcha](https://www.hcaptcha.com). These credentials include a site key and a secret key.

    **Configuration Settings:**

    | Setting                    | Default | Context   | Multiple | Description                                                                 |
    | -------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`    | multisite | no       | **Enable Antibot:** Set to `hcaptcha` to enable the hCaptcha challenge.     |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |         | multisite | no       | **hCaptcha Site Key:** Your hCaptcha site key (get this from hCaptcha).     |
    | `ANTIBOT_HCAPTCHA_SECRET`  |         | multisite | no       | **hCaptcha Secret Key:** Your hCaptcha secret key (get this from hCaptcha). |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "Turnstile"

    Turnstile is a modern, privacy-friendly challenge mechanism that leverages Cloudflare’s technology to detect and block automated traffic. It validates user interactions in a seamless, background manner, reducing friction for legitimate users while effectively discouraging bots.

    To integrate Turnstile with BunkerWeb, ensure you obtain the necessary credentials from [Cloudflare Turnstile](https://www.cloudflare.com/turnstile).

    **Configuration Settings:**

    | Setting                     | Default | Context   | Multiple | Description                                                                     |
    | --------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`    | multisite | no       | **Enable Antibot:** Set to `turnstile` to enable the Turnstile challenge.       |
    | `ANTIBOT_TURNSTILE_SITEKEY` |         | multisite | no       | **Turnstile Site Key:** Your Turnstile site key (get this from Cloudflare).     |
    | `ANTIBOT_TURNSTILE_SECRET`  |         | multisite | no       | **Turnstile Secret Key:** Your Turnstile secret key (get this from Cloudflare). |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "mCaptcha"

    mCaptcha is an alternative CAPTCHA challenge mechanism that verifies the legitimacy of users by presenting an interactive test similar to other antibot solutions. When enabled, it challenges users with a CAPTCHA provided by mCaptcha, ensuring that only genuine users bypass the automated security checks.

    mCaptcha is designed with privacy in mind. It is fully GDPR compliant, ensuring that all user data involved in the challenge process adheres to strict data protection standards. Additionally, mCaptcha offers the flexibility to be self-hosted, allowing organizations to maintain full control over their data and infrastructure. This self-hosting capability not only enhances privacy but also optimizes performance and customization to suit specific deployment needs.

    To integrate mCaptcha with BunkerWeb, you must obtain the necessary credentials from the [mCaptcha](https://mcaptcha.org/) platform or your own provider. These credentials include a site key and a secret key for verification.

    **Configuration Settings:**

    | Setting                    | Default                     | Context   | Multiple | Description                                                                 |
    | -------------------------- | --------------------------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | no       | **Enable Antibot:** Set to `mcaptcha` to enable the mCaptcha challenge.     |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | no       | **mCaptcha Site Key:** Your mCaptcha site key (get this from mCaptcha).     |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | no       | **mCaptcha Secret Key:** Your mCaptcha secret key (get this from mCaptcha). |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | no       | **mCaptcha Domain:** The domain to use for the mCaptcha challenge.          |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

### Example Configurations

=== "Cookie Challenge"

    Example configuration for enabling the Cookie challenge:

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "JavaScript Challenge"

    Example configuration for enabling the JavaScript challenge:

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Captcha Challenge"

    Example configuration for enabling the Captcha challenge:

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    Note: The example above uses numbers 2-9 and all letters, which are the most commonly used characters for CAPTCHA challenges. You can customize the alphabet to include special characters as needed.

=== "reCAPTCHA Classic"

    Example configuration for the classic reCAPTCHA (site/secret keys):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "yes"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "reCAPTCHA (new)"

    Example configuration for the new Google Cloud-based reCAPTCHA (Project ID + API key):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # Optional fingerprints to improve Enterprise assessments
    # ANTIBOT_RECAPTCHA_JA3: "<ja3-fingerprint>"
    # ANTIBOT_RECAPTCHA_JA4: "<ja4-fingerprint>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "hCaptcha Challenge"

    Example configuration for enabling the hCaptcha challenge:

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Turnstile Challenge"

    Example configuration for enabling the Turnstile challenge:

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "mCaptcha Challenge"

    Example configuration for enabling the mCaptcha challenge:

    ```yaml
    USE_ANTIBOT: "mcaptcha"
    ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

## Auth basic

STREAM support :x:

The Auth Basic plugin provides HTTP basic authentication to protect your website or specific resources. This feature adds an extra layer of security by requiring users to enter a username and password before accessing protected content. This type of authentication is simple to implement and widely supported by browsers.

**How it works:**

1. When a user tries to access a protected area of your website, the server sends an authentication challenge.
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

| Setting               | Default           | Context   | Multiple | Description                                                                                                                                                                                               |
| --------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | no       | **Enable Auth Basic:** Set to `yes` to enable basic authentication.                                                                                                                                       |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | no       | **Protection Scope:** Set to `sitewide` to protect the entire site, or specify a URL path (e.g., `/admin`) to protect only specific areas. You can also use Nginx-style modifiers (`=`, `~`, `~*`, `^~`). |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | yes      | **Username:** The username required for authentication. You can define multiple username/password pairs.                                                                                                  |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | yes      | **Password:** The password required for authentication. Passwords are hashed using scrypt for maximum security.                                                                                           |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | no       | **Prompt Text:** The message displayed in the authentication prompt shown to users.                                                                                                                       |

!!! warning "Security Considerations"
    HTTP Basic Authentication transmits credentials encoded (not encrypted) in Base64. While this is acceptable when used over HTTPS, it should not be considered secure over plain HTTP. Always enable SSL/TLS when using basic authentication.

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

The Backup plugin provides an automated backup solution to protect your BunkerWeb data. This feature ensures the safety and availability of your important database by creating regular backups according to your preferred schedule. Backups are stored in a designated location and can be easily managed through both automated processes and manual commands.

**How it works:**

1. Your database is automatically backed up according to the schedule you set (daily, weekly, or monthly).
2. Backups are stored in a specified directory on your system.
3. Old backups are automatically rotated based on your retention settings.
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
    Before any restore operation, the Backup plugin automatically creates a backup of your current database state in a temporary location. This provides an extra safeguard in case you need to revert the restore operation.

!!! warning "Database Compatibility"
    The Backup plugin supports SQLite, MySQL/MariaDB, and PostgreSQL databases. Oracle databases are not currently supported for backup and restore operations.

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

## Backup S3 <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


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

Attackers often generate "suspicious" HTTP status codes when probing for or exploiting vulnerabilities—codes that a typical user is unlikely to trigger within a given time frame. By detecting this behavior, BunkerWeb can automatically ban the offending IP address, forcing the attacker to use a new IP address to continue their attempts.

**How it works:**

1. The plugin monitors HTTP responses from your site.
2. When a visitor receives a "bad" HTTP status code (like 400, 401, 403, 404, etc.), the counter for that IP address is incremented.
3. If an IP address exceeds the configured threshold of bad status codes within the specified time period, the IP is automatically banned.
4. Banned IPs can be blocked either at the service level (just for the specific site) or globally (across all sites), depending on your configuration.
5. Bans automatically expire after the configured ban duration, or remain permanent if configured with `0`.

!!! success "Key benefits"

      1. **Automatic Protection:** Detects and blocks potentially malicious clients without requiring manual intervention.
      2. **Customizable Rules:** Fine-tune what constitutes "bad behavior" based on your specific needs.
      3. **Resource Conservation:** Prevents malicious actors from consuming server resources with repeated invalid requests.
      4. **Flexible Scope:** Choose whether bans should apply just to the current service or globally across all services.
      5. **Ban Duration Control:** Set temporary bans that automatically expire after the configured duration, or permanent bans that remain until manually removed.

### How to Use

Follow these steps to configure and use the Bad Behavior feature:

1. **Enable the feature:** The Bad Behavior feature is enabled by default. If needed, you can control this with the `USE_BAD_BEHAVIOR` setting.
2. **Configure status codes:** Define which HTTP status codes should be considered "bad" using the `BAD_BEHAVIOR_STATUS_CODES` setting.
3. **Set threshold values:** Determine how many "bad" responses should trigger a ban using the `BAD_BEHAVIOR_THRESHOLD` setting.
4. **Configure time periods:** Specify the duration for counting bad responses and the ban duration using the `BAD_BEHAVIOR_COUNT_TIME` and `BAD_BEHAVIOR_BAN_TIME` settings.
5. **Choose ban scope:** Decide whether the bans should apply only to the current service or globally across all services using the `BAD_BEHAVIOR_BAN_SCOPE` setting. When traffic hits the default server (server name `_`), bans are always enforced globally so the offending IP is blocked everywhere.

!!! tip "Stream Mode"
    In **stream mode**, only the `444` status code is considered "bad" and will trigger this behavior.

### Configuration Settings

| Setting                     | Default                       | Context   | Multiple | Description                                                                                                                                                                           |
| --------------------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | no       | **Enable Bad Behavior:** Set to `yes` to enable the bad behavior detection and banning feature.                                                                                       |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | no       | **Bad Status Codes:** List of HTTP status codes that will be counted as "bad" behavior when returned to a client.                                                                     |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | no       | **Threshold:** The number of "bad" status codes an IP can generate within the counting period before being banned.                                                                    |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | no       | **Count Period:** The time window (in seconds) during which bad status codes are counted toward the threshold.                                                                        |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | no       | **Ban Duration:** How long (in seconds) an IP will remain banned after exceeding the threshold. Default is 24 hours (86400 seconds). Set to `0` for permanent bans that never expire. |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | no       | **Ban Scope:** Determines whether bans apply only to the current service (`service`) or to all services (`global`). Bans triggered on the default server (`_`) are always global.     |

!!! warning "False Positives"
    Be careful when setting the threshold and count time. Setting these values too low may inadvertently ban legitimate users who encounter errors while browsing your site.

!!! tip "Tuning Your Configuration"
    Start with conservative settings (higher threshold, shorter ban time) and adjust based on your specific needs and traffic patterns. Monitor your logs to ensure that legitimate users are not mistakenly banned.

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

=== "Permanent Ban Configuration"

    For scenarios where you want detected attackers permanently banned until manually unbanned:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"  # Permanent ban (never expires)
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Ban across all services
    ```

## Blacklist

STREAM support :warning:

The Blacklist plugin provides robust protection for your website by blocking access based on various client attributes. This feature defends against known malicious entities, scanners, and suspicious visitors by denying access based on IP addresses, networks, reverse DNS entries, ASNs, user agents, and specific URI patterns.

**How it works:**

1. The plugin checks incoming requests against multiple blacklist criteria (IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns).
2. Blacklists can be specified directly in your configuration or loaded from external URLs.
3. If a visitor matches any blacklist rule (and does not match any ignore rule), access is denied.
4. Blacklists are automatically updated on a regular schedule from configured URLs.
5. You can customize exactly which criteria are checked and ignored based on your specific security needs.

### How to Use

Follow these steps to configure and use the Blacklist feature:

1. **Enable the feature:** The Blacklist feature is enabled by default. If needed, you can control this with the `USE_BLACKLIST` setting.
2. **Configure block rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be blocked.
3. **Set up ignore rules:** Specify any exceptions that should bypass the blacklist checks.
4. **Add external sources:** Configure URLs for automatically downloading and updating blacklist data.
5. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on blocked requests.

!!! info "stream mode"
    When using stream mode, only IP, rDNS, and ASN checks will be performed.

### Configuration Settings

**General**

| Setting                     | Default                                                 | Context   | Multiple | Description                                                                                             |
| --------------------------- | ------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | no       | **Enable Blacklist:** Set to `yes` to enable the blacklist feature.                                     |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | no       | **Community Blacklists:** Select pre-configured community-maintained blacklists to include in blocking. |

=== "Community Blacklists"
    **What this does:** Enables you to quickly add well-maintained, community-sourced blacklists without having to manually configure URLs.

    The `BLACKLIST_COMMUNITY_LISTS` setting allows you to select from curated blacklist sources. Available options include:

    | ID                                        | Description                                                                                                                                                                                                              | Source                                                                                                                                |
    | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
    | `ip:danmeuk-tor-exit`                     | Tor Exit Nodes IPs (dan.me.uk)                                                                                                                                                                                           | `https://www.dan.me.uk/torlist/?exit`                                                                                                 |
    | `ua:mitchellkrogza-bad-user-agents`       | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, with anti-DDOS, Wordpress Theme Detector Blocking and Fail2Ban Jail for Repeat Offenders | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list`        |
    | `ip:laurent-minne-data-shield-aggressive` | Data-Shield IPv4 Blocklist - Laurent M. - For Web Apps, WordPress, VPS (Apache/Nginx)                                                                                                                                    | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt`          |
    | `ip:laurent-minne-data-shield-critical`   | Data-Shield IPv4 Blocklist - Laurent M. - For DMZs, SaaS, API & Critical Assets                                                                                                                                          | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_critical_data-shield_ipv4_blocklist.txt` |

    **Configuration:** Specify multiple lists separated by spaces. For example:
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Community vs Manual Configuration"
        Community blacklists provide a convenient way to get started with proven blacklist sources. You can use them alongside manual URL configurations for maximum flexibility.

    !!! note "Acknowledgements"
        Thank you Laurent Minne for contributing the [Data-Shield blocklists](https://duggytuxy.github.io/#)!

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
    **What this does:** Blocks visitors based on their reverse domain name. This is useful for blocking known scanners and crawlers based on their organization domains.

    | Setting                      | Default                 | Context   | Multiple | Description                                                                                          |
    | ---------------------------- | ----------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | no       | **rDNS Blacklist:** List of reverse DNS suffixes to block, separated by spaces.                      |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | no       | **rDNS Global Only:** Only perform rDNS checks on global IP addresses when set to `yes`.             |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | no       | **rDNS Ignore List:** List of reverse DNS suffixes that should bypass rDNS blacklist checks.         |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | no       | **rDNS Blacklist URLs:** List of URLs containing reverse DNS suffixes to block, separated by spaces. |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | no       | **rDNS Ignore List URLs:** List of URLs containing reverse DNS suffixes to ignore.                   |

    The default `BLACKLIST_RDNS` setting includes common scanner domains like **Shodan** and **Censys**. These are often used by security researchers and scanners to identify vulnerable sites.

=== "ASN"
    **What this does:** Blocks visitors from specific network providers. ASNs are like ZIP codes for the Internet—they identify which provider or organization an IP belongs to.

    | Setting                     | Default | Context   | Multiple | Description                                                                         |
    | --------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |         | multisite | no       | **ASN Blacklist:** List of Autonomous System Numbers to block, separated by spaces. |
    | `BLACKLIST_IGNORE_ASN`      |         | multisite | no       | **ASN Ignore List:** List of ASNs that should bypass ASN blacklist checks.          |
    | `BLACKLIST_ASN_URLS`        |         | multisite | no       | **ASN Blacklist URLs:** List of URLs containing ASNs to block, separated by spaces. |
    | `BLACKLIST_IGNORE_ASN_URLS` |         | multisite | no       | **ASN Ignore List URLs:** List of URLs containing ASNs to ignore.                   |

=== "User Agent"
    **What this does:** Blocks visitors based on the browser or tool they claim to be using. This is effective against bots that honestly identify themselves (such as "ScannerBot" or "WebHarvestTool").

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

    A simple configuration that blocks known Tor exit nodes and common bad user agents using community blacklists:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternatively, you can use manual URL configuration:

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

### Working with local list files

The `*_URLS` settings provided by the whitelist, greylist, and blacklist plugins all use the same downloader. When you reference a `file:///` URL:

- The path is resolved inside the **scheduler** container (for Docker deployments this is typically `bunkerweb-scheduler`). Mount the files there and ensure they are readable by the scheduler user.
- Each file is plain text encoded in UTF-8 with one entry per line. Empty lines are ignored and comment lines must begin with `#` or `;`. `//` comments are not supported.
- Expected value per list type:
  - **IP lists** accept IPv4/IPv6 addresses or CIDR networks (for example `192.0.2.10` or `2001:db8::/48`).
  - **rDNS lists** expect a suffix without spaces (for example `.search.msn.com`). Values are normalised to lowercase automatically.
  - **ASN lists** may contain just the number (`32934`) or the number prefixed with `AS` (`AS15169`).
  - **User-Agent lists** are treated as PCRE patterns and the whole line is preserved (including spaces). Keep comments on their own line so they are not interpreted as part of the pattern.
  - **URI lists** must start with `/` and may use PCRE tokens such as `^` or `$`.

Example files that match the expected format:

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Brotli

STREAM support :x:

The Brotli plugin enables efficient compression of HTTP responses using the Brotli algorithm. This feature helps reduce bandwidth usage and improve page load times by compressing web content before it is sent to the client's browser.

Compared to other compression methods like gzip, Brotli typically achieves higher compression ratios, resulting in smaller file sizes and faster content delivery.

**How it works:**

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

**How it works:**

1. Your BunkerWeb instance automatically registers with the BunkerNet API to receive a unique identifier.
2. When your instance detects and blocks a malicious IP address or behavior, it anonymously reports the threat to BunkerNet.
3. BunkerNet aggregates threat intelligence from all participating instances and distributes the consolidated database.
4. Your instance regularly downloads an updated database of known threats from BunkerNet.
5. This collective intelligence allows your instance to proactively block IP addresses that have exhibited malicious behavior on other BunkerWeb instances.

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
4. **Automatic reporting:** When your instance blocks a malicious IP address, it will automatically contribute this data to the community.
5. **Monitor protection:** Check the [web UI](web-ui.md) to see statistics on threats blocked by BunkerNet intelligence.

### Configuration Settings

| Setting            | Default                    | Context   | Multiple | Description                                                                                    |
| ------------------ | -------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | no       | **Enable BunkerNet:** Set to `yes` to enable the BunkerNet threat intelligence sharing.        |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | no       | **BunkerNet Server:** The address of the BunkerNet API server for sharing threat intelligence. |

!!! tip "Network Protection"
    When BunkerNet detects that an IP address has been involved in malicious activity across multiple BunkerWeb instances, it adds that IP to a collective blacklist. This provides a proactive defense layer, protecting your site from threats before they can target you directly.

!!! info "Anonymous Reporting"
    When reporting threat information to BunkerNet, your instance only shares the necessary data to identify the threat: the IP address, the reason for blocking, and minimal contextual data. No personal information about your users or sensitive details about your site is shared.

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

### CrowdSec Console integration

If you aren’t already familiar with CrowdSec Console integration, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) leverages crowdsourced intelligence to combat cyber threats. Think of it as the "Waze of cybersecurity"—when one server is attacked, other systems worldwide are alerted and protected from the same attackers. You can learn more about it [here](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

Through our partnership with CrowdSec, you can enroll your BunkerWeb instances into your [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration). This means that attacks blocked by BunkerWeb will be visible in your CrowdSec Console alongside attacks blocked by CrowdSec Security Engines, giving you a unified view of threats.

Importantly, CrowdSec does not need to be installed for this integration (though we highly recommend trying it out with the [CrowdSec plugin for BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) to further enhance the security of your web services). Additionally, you can enroll your CrowdSec Security Engines into the same Console account for even greater synergy.

**Step #1: Create your CrowdSec Console account**

Go to the [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) and register if you don’t already have an account. Once done, note the enroll key found under "Security Engines" after clicking on "Add Security Engine":

<figure markdown>
  ![Overview](assets/img/crowdity1.png){ align=center }
  <figcaption>Get your Crowdsec Console enroll key</figcaption>
</figure>

**Step #2: Get your BunkerNet ID**

Activating the BunkerNet feature (enabled by default) is mandatory if you want to enroll your BunkerWeb instance(s) in your CrowdSec Console. Enable it by setting `USE_BUNKERNET` to `yes`.

For Docker, get your BunkerNet ID using:

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

For Linux, use:

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**Step #3: Enroll your instance using the Panel**

Once you have your BunkerNet ID and CrowdSec Console enroll key, [order the free product "BunkerNet / CrowdSec" on the Panel](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc). You may be prompted to create an account if you haven’t already.

You can now select the "BunkerNet / CrowdSec" service and fill out the form by pasting your BunkerNet ID and CrowdSec Console enroll key:

<figure markdown>
  ![Overview](assets/img/crowdity2.png){ align=center }
  <figcaption>Enroll your BunkerWeb instance into the CrowdSec Console</figcaption>
</figure>

**Step #4: Accept the new security engine on the Console**

Then, go back to your CrowdSec Console and accept the new Security Engine:

<figure markdown>
  ![Overview](assets/img/crowdity3.png){ align=center }
  <figcaption>Accept enroll into the CrowdSec Console</figcaption>
</figure>

**Congratulations, your BunkerWeb instance is now enrolled in your CrowdSec Console!**

Pro tip: When viewing your alerts, click the "columns" option and check the "context" checkbox to access BunkerWeb-specific data.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb data shown in the context column</figcaption>
</figure>

## CORS

STREAM support :x:

The CORS plugin enables Cross-Origin Resource Sharing for your website, allowing controlled access to your resources from different domains. This feature helps you safely share your content with trusted third-party websites while maintaining security by explicitly defining which origins, methods, and headers are permitted.

**How it works:**

1. When a browser makes a cross-origin request to your website, it first sends a preflight request with the `OPTIONS` method.
2. BunkerWeb checks if the requesting origin is permitted based on your configuration.
3. If allowed, BunkerWeb responds with the appropriate CORS headers that define what the requesting site can do.
4. For non-permitted origins, the request can be either completely denied or served without CORS headers.
5. Additional cross-origin policies, such as [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy), and [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy), can be configured to further enhance security.

### How to Use

Follow these steps to configure and use the CORS feature:

1. **Enable the feature:** The CORS feature is disabled by default. Set the `USE_CORS` setting to `yes` to enable it.
2. **Configure allowed origins:** Specify which domains can access your resources using the `CORS_ALLOW_ORIGIN` setting.
3. **Set permitted methods:** Define which HTTP methods are allowed for cross-origin requests with `CORS_ALLOW_METHODS`.
4. **Configure allowed headers:** Specify which headers can be used in requests with `CORS_ALLOW_HEADERS`.
5. **Control credentials:** Decide whether cross-origin requests can include credentials using `CORS_ALLOW_CREDENTIALS`.

### Configuration Settings

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Enable CORS:** Set to `yes` to enable Cross-Origin Resource Sharing.                                                             |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Allowed Origins:** PCRE regular expression representing allowed origins; use `*` for any origin, or `self` for same-origin only. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Allowed Methods:** HTTP methods that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Allowed Headers:** HTTP headers that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Allow Credentials:** Set to `yes` to allow credentials (cookies, HTTP authentication) in CORS requests.                          |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Exposed Headers:** HTTP headers that browsers are permitted to access from cross-origin responses.                               |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controls communication between browsing contexts.                                                  |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controls whether a document can load resources from other origins.                               |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controls which websites can embed your resources.                                                |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Preflight Cache Duration:** How long (in seconds) browsers should cache the preflight response.                                  |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Deny Unauthorized Origins:** When `yes`, requests from unauthorized origins are denied with an error code.                       |

!!! tip "Optimizing Preflight Requests"
    The `CORS_MAX_AGE` setting determines how long browsers will cache the results of a preflight request. Setting this to a higher value (like the default 86400 seconds/24 hours) reduces the number of preflight requests, improving performance for frequently accessed resources.

!!! warning "Security Considerations"
    Be cautious when setting `CORS_ALLOW_ORIGIN` to `*` (all origins) or `CORS_ALLOW_CREDENTIALS` to `yes` because these configurations may introduce security risks if not properly managed. It's generally safer to explicitly list trusted origins and limit the allowed methods and headers.

### Example Configurations

Here are examples of possible values for the `CORS_ALLOW_ORIGIN` setting, along with their behavior:

- **`*`**: Allows requests from all origins.
- **`self`**: Automatically allows requests from the same origin as the configured server_name.
- **`^https://www\.example\.com$`**: Allows requests only from `https://www.example.com`.
- **`^https://.+\.example\.com$`**: Allows requests from any subdomain ending with `.example.com`.
- **`^https://(www\.example1\.com|www\.example2\.com)$`**: Allows requests from either `https://www.example1.com` or `https://www.example2.com`.
- **`^https?://www\.example\.com$`**: Allows requests from both `https://www.example.com` and `http://www.example.com`.

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

    Configuration for allowing multiple specific domains with a single PCRE regular expression pattern:

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

    Configuration allowing all subdomains of a primary domain using a PCRE regular expression pattern:

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

## Cache <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Provides caching functionality at the reverse proxy level.

| Setting                     | Default                           | Context   | Multiple | Description                                                                    |
| --------------------------- | --------------------------------- | --------- | -------- | ------------------------------------------------------------------------------ |
| `CACHE_PATH`                |                                   | global    | yes      | Path and parameters for a cache.                                               |
| `CACHE_ZONE`                |                                   | multisite | no       | Name of cache zone to use (specified in a CACHE_PATH setting).                 |
| `CACHE_HEADER`              | `X-Cache`                         | multisite | no       | Add header about cache status.                                                 |
| `CACHE_BACKGROUND_UPDATE`   | `no`                              | multisite | no       | Enable or disable background update of the cache.                              |
| `CACHE_BYPASS`              |                                   | multisite | no       | List of variables to determine if the cache should be bypassed or not.         |
| `CACHE_NO_CACHE`            | `$http_pragma$http_authorization` | multisite | no       | Disable caching if variables are set.                                          |
| `CACHE_KEY`                 | `$scheme$proxy_host$request_uri`  | multisite | no       | Key used to identify cached elements.                                          |
| `CACHE_CONVERT_HEAD_TO_GET` | `yes`                             | multisite | no       | Convert HEAD requests to GET when caching.                                     |
| `CACHE_LOCK`                | `no`                              | multisite | no       | Lock concurrent requests when populating the cache.                            |
| `CACHE_LOCK_AGE`            | `5s`                              | multisite | no       | Pass request to upstream if cache is locked for that time (possible cache).    |
| `CACHE_LOCK_TIMEOUT`        | `5s`                              | multisite | no       | Pass request to upstream if cache is locked for that time (no cache).          |
| `CACHE_METHODS`             | `GET HEAD`                        | multisite | no       | Only cache response if corresponding method is present.                        |
| `CACHE_MIN_USES`            | `1`                               | multisite | no       | Number of requests before we put the corresponding response in cache.          |
| `CACHE_REVALIDATE`          | `no`                              | multisite | no       | Revalidate expired items using conditional requests to upstream.               |
| `CACHE_USE_STALE`           | `off`                             | multisite | no       | Determines the use of staled cache response (proxy_cache_use_stale directive). |
| `CACHE_VALID`               | `10m`                             | multisite | yes      | Defines default caching with optional status code.                             |

## Client cache

STREAM support :x:

The Client Cache plugin optimizes website performance by controlling how browsers cache static content. It reduces bandwidth usage, lowers server load, and improves page load times by instructing browsers to store and reuse static assets—such as images, CSS, and JavaScript files—locally instead of requesting them on every page visit.

**How it works:**

1. When enabled, BunkerWeb adds Cache-Control headers to responses for static files.
2. These headers tell browsers how long they should cache the content locally.
3. For files with specified extensions (like images, CSS, JavaScript), BunkerWeb applies the configured caching policy.
4. Optional ETag support provides an additional validation mechanism to determine whether cached content is still fresh.
5. When visitors return to your site, their browsers can use locally cached files instead of downloading them again, resulting in faster page load times.

### How to Use

Follow these steps to configure and use the Client Cache feature:

1. **Enable the feature:** The Client Cache feature is disabled by default; set the `USE_CLIENT_CACHE` setting to `yes` to enable it.
2. **Configure file extensions:** Specify which file types should be cached using the `CLIENT_CACHE_EXTENSIONS` setting.
3. **Set cache control directives:** Customize how clients should cache content using the `CLIENT_CACHE_CONTROL` setting.
4. **Configure ETag support:** Decide whether to enable ETags for validating cache freshness with the `CLIENT_CACHE_ETAG` setting.
5. **Let BunkerWeb handle the rest:** Once configured, caching headers are applied automatically to eligible responses.

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

The Country plugin enables geo-blocking functionality for your website, allowing you to restrict access based on the geographic location of your visitors. This feature helps you comply with regional regulations, prevent fraudulent activities often associated with high-risk regions, and implement content restrictions based on geographic boundaries.

**How it works:**

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
    If both whitelist and blacklist are configured, the whitelist takes precedence. This means the system first checks if a country is whitelisted; if not, access is denied regardless of the blacklist configuration.

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

CrowdSec is a modern, open-source security engine that detects and blocks malicious IP addresses based on behavioral analysis and collective intelligence from its community. You can also configure [scenarios](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) to automatically ban IP addresses based on suspicious behavior, benefiting from a crowdsourced blacklist.

**How it works:**

1. The CrowdSec engine analyzes logs and detects suspicious activities on your infrastructure.
2. When malicious activity is detected, CrowdSec creates a decision to block the offending IP address.
3. BunkerWeb, acting as a bouncer, queries the CrowdSec Local API for decisions about incoming requests.
4. If a client's IP address has an active block decision, BunkerWeb denies access to the protected services.
5. Optionally, the Application Security Component can perform deep request inspection for enhanced security.

!!! success "Key benefits"

      1. **Community-Powered Security:** Benefit from threat intelligence shared across the CrowdSec user community.
      2. **Behavioral Analysis:** Detect sophisticated attacks based on behavior patterns, not just signatures.
      3. **Lightweight Integration:** Minimal performance impact on your BunkerWeb instance.
      4. **Multi-Level Protection:** Combine perimeter defense (IP blocking) with application security for in-depth protection.

### Prerequisites

- A CrowdSec Local API that BunkerWeb can reach (typically the agent running on the same host or inside the same Docker network).
- Access to BunkerWeb access logs (`/var/log/bunkerweb/access.log` by default) so the CrowdSec agent can analyse requests.
- `cscli` access on the CrowdSec host to register the BunkerWeb bouncer key.

### Integration workflow

1. Prepare the CrowdSec agent so it ingests BunkerWeb logs.
2. Configure BunkerWeb to query the CrowdSec Local API.
3. Validate the link with the `/crowdsec/ping` API or the admin UI CrowdSec card.

The detailed instructions below follow this sequence.

### Step&nbsp;1 – Prepare CrowdSec to ingest BunkerWeb logs

Follow one of the environment-specific guides below so the CrowdSec agent ingests BunkerWeb access, error, and ModSecurity audit logs. This is what drives the remediation decisions that the plugin will later enforce.

=== "Docker"
    **Acquisition file**

    You will need to run a CrowdSec instance and configure it to parse BunkerWeb logs. Use the dedicated `bunkerweb` value for the `type` parameter in your acquisition file (assuming that BunkerWeb logs are stored as is without additional data):

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    If the collection is not visible from inside the CrowdSec container, execute `docker exec -it <crowdsec-container> cscli hub update` and then restart that container (`docker restart <crowdsec-container>`) so the new assets become available. Replace `<crowdsec-container>` with the name of your CrowdSec container.

    **Application Security Component (*optional*)**

    CrowdSec also provides an [Application Security Component](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) that can be used to protect your application from attacks. If you want to use it, you must create another acquisition file for the AppSec Component:

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    For container-based integrations, we recommend redirecting the logs of the BunkerWeb container to a syslog service so CrowdSec can access them easily. Here is an example configuration for syslog-ng that will store raw logs coming from BunkerWeb to a local `/var/log/bunkerweb.log` file:

    ```syslog
    @version: 4.10

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
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    Here is the docker-compose boilerplate that you can use (don’t forget to update the bouncer key):

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for both services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.6.8
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
        logging:
          driver: syslog # Send logs to syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # The IP address of the syslog service

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
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
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
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
        image: crowdsecurity/crowdsec:v1.7.4 # Use the latest version but always pin the version for a better stability/security
        volumes:
          - cs-data:/var/lib/crowdsec/data # To persist the CrowdSec data
          - bw-logs:/var/log:ro # The logs of BunkerWeb for CrowdSec to parse
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # The acquisition file for BunkerWeb logs
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Comment if you don't want to use the AppSec Component
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # Remember to set a stronger key for the bouncer
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # If you don't want to use the AppSec Component use this line instead
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
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
            bw-universe:
              ipv4_address: 10.20.30.254

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
    ```

=== "Linux"

    You need to install CrowdSec and configure it to parse BunkerWeb logs. Follow the [official documentation](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    To enable CrowdSec to parse BunkerWeb logs, add the following lines to your acquisition file located at `/etc/crowdsec/acquis.yaml`:

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    Update the CrowdSec hub and install the BunkerWeb collection:

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    Now, add your custom bouncer to the CrowdSec API using the `cscli` tool:

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "API key"
        Keep the key generated by the `cscli` command; you will need it later.

    Then restart the CrowdSec service:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Application Security Component (*optional*)**

    If you want to use the AppSec Component, you must create another acquisition file for it located at `/etc/crowdsec/acquis.d/appsec.yaml`:

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    You will also need to install the AppSec Component's collections:

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Finally, restart the CrowdSec service:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Settings**

    Configure the plugin by adding the following settings to your BunkerWeb configuration file:

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<The key provided by cscli>
    # Comment if you don't want to use the AppSec Component
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    Finally, reload the BunkerWeb service:

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "All-in-one"

    The BunkerWeb All-In-One (AIO) Docker image comes with CrowdSec fully integrated. You don't need to set up a separate CrowdSec instance or manually configure acquisition files for BunkerWeb logs when using the internal CrowdSec agent.

    Refer to the [All-In-One (AIO) Image integration documentation](integrations.md#crowdsec-integration).

### Step&nbsp;2 – Configure BunkerWeb settings

Apply the following environment variables (or values via the scheduler UI/API) so the BunkerWeb instance can talk to the CrowdSec Local API. At a minimum you must set `USE_CROWDSEC`, `CROWDSEC_API`, and a valid `CROWDSEC_API_KEY` that you created with `cscli bouncers add`.

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
    - **Stream mode** periodically downloads all decisions from the CrowdSec API and caches them locally, reducing latency with a slight delay in applying new decisions.

### Example Configurations

=== "Basic Configuration"

    This is a simple configuration for when CrowdSec runs on the same host:

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

### Step&nbsp;3 – Validate the integration

- In the scheduler logs, look for `CrowdSec configuration successfully generated` and `CrowdSec bouncer denied request` entries to verify that the plugin is active.
- On the CrowdSec side, monitor `cscli metrics show` or the CrowdSec Console to ensure BunkerWeb decisions appear as expected.
- In the BunkerWeb UI, open the CrowdSec plugin page to see the status of the integration.

## Custom Pages <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Tweak BunkerWeb error/antibot/default pages with custom HTML.

| Setting                          | Default | Context   | Multiple | Description                                                                                                        |
| -------------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| `CUSTOM_ERROR_PAGE`              |         | multisite | no       | Full path of the custom error page (must be readable by the scheduler) (Can be a lua template).                    |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |         | global    | no       | Full path of the custom default server page (must be readable by the scheduler) (Can be a lua template).           |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |         | multisite | no       | Full path of the custom antibot captcha page (must be readable by the scheduler) (Can be a lua template).          |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |         | multisite | no       | Full path of the custom antibot javascript check page (must be readable by the scheduler) (Can be a lua template). |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |         | multisite | no       | Full path of the custom antibot recaptcha page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |         | multisite | no       | Full path of the custom antibot hcaptcha page (must be readable by the scheduler) (Can be a lua template).         |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |         | multisite | no       | Full path of the custom antibot turnstile page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |         | multisite | no       | Full path of the custom antibot mcaptcha page (must be readable by the scheduler) (Can be a lua template).         |

## Custom SSL certificate

STREAM support :white_check_mark:

The Custom SSL certificate plugin allows you to use your own SSL/TLS certificates with BunkerWeb instead of the automatically generated ones. This feature is particularly useful if you have existing certificates from a trusted Certificate Authority (CA), need to use certificates with specific configurations, or want to maintain consistent certificate management across your infrastructure.

**How it works:**

1. You provide BunkerWeb with your certificate and private key files, either by specifying file paths or by providing the data in base64-encoded or plaintext PEM format.
2. BunkerWeb validates your certificate and key to ensure they are properly formatted and usable.
3. When a secure connection is established, BunkerWeb serves your custom certificate instead of the auto-generated one.
4. BunkerWeb automatically monitors your certificate's validity and displays warnings if it is approaching expiration.
5. You have full control over certificate management, allowing you to use certificates from any issuer you prefer.

!!! info "Automatic Certificate Monitoring"
    When you enable custom SSL/TLS by setting `USE_CUSTOM_SSL` to `yes`, BunkerWeb automatically monitors the custom certificate specified in `CUSTOM_SSL_CERT`. It checks for changes daily and reloads NGINX if any modifications are detected, ensuring the latest certificate is always in use.

### How to Use

Follow these steps to configure and use the Custom SSL certificate feature:

1. **Enable the feature:** Set the `USE_CUSTOM_SSL` setting to `yes` to enable custom certificate support.
2. **Choose a method:** Decide whether to provide certificates via file paths or as base64-encoded/plaintext data, and set the priority using `CUSTOM_SSL_CERT_PRIORITY`.
3. **Provide certificate files:** If using file paths, specify the locations of your certificate and private key files.
4. **Or provide certificate data:** If using data, provide your certificate and key as either base64-encoded strings or plaintext PEM format.
5. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb automatically uses your custom certificates for all HTTPS connections.

!!! tip "Stream Mode Configuration"
    For stream mode, you must configure the `LISTEN_STREAM_PORT_SSL` setting to specify the SSL/TLS listening port. This step is essential for proper operation in stream mode.

### Configuration Settings

| Setting                    | Default | Context   | Multiple | Description                                                                                                                   |
| -------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`    | multisite | no       | **Enable Custom SSL:** Set to `yes` to use your own certificate instead of the auto-generated one.                            |
| `CUSTOM_SSL_CERT_PRIORITY` | `file`  | multisite | no       | **Certificate Priority:** Choose whether to prioritize the certificate from file path or from base64 data (`file` or `data`). |
| `CUSTOM_SSL_CERT`          |         | multisite | no       | **Certificate Path:** Full path to your SSL certificate or certificate bundle file.                                           |
| `CUSTOM_SSL_KEY`           |         | multisite | no       | **Private Key Path:** Full path to your SSL private key file.                                                                 |
| `CUSTOM_SSL_CERT_DATA`     |         | multisite | no       | **Certificate Data:** Your certificate encoded in base64 format or as plaintext PEM.                                          |
| `CUSTOM_SSL_KEY_DATA`      |         | multisite | no       | **Private Key Data:** Your private key encoded in base64 format or as plaintext PEM.                                          |

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

=== "Using Plaintext PEM Data"

    A configuration using plaintext certificate and key data in PEM format:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
      -----BEGIN CERTIFICATE-----
      MIIDdzCCAl+gAwIBAgIUJH...certificate content...AAAA
      -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
      -----BEGIN PRIVATE KEY-----
      MIIEvQIBADAN...key content...AAAA
      -----END PRIVATE KEY-----
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

The DNSBL (Domain Name System Blacklist) plugin provides protection against known malicious IP addresses by checking client IP addresses against external DNSBL servers. This feature helps guard your website against spam, botnets, and various types of cyber threats by leveraging community-maintained lists of problematic IP addresses.

**How it works:**

1. When a client connects to your website, BunkerWeb queries the DNSBL servers you have chosen using the DNS protocol.
2. The check is performed by sending a reverse DNS query to each DNSBL server with the client's IP address.
3. If any DNSBL server confirms that the client's IP address is listed as malicious, BunkerWeb will automatically ban the client, preventing potential threats from reaching your application.
4. Results are cached to improve performance for repeat visitors from the same IP address.
5. Lookups are performed efficiently using asynchronous queries to minimize impact on page load times.

### How to Use

Follow these steps to configure and use the DNSBL feature:

1. **Enable the feature:** The DNSBL feature is disabled by default. Set the `USE_DNSBL` setting to `yes` to enable it.
2. **Configure DNSBL servers:** Add the domain names of the DNSBL services you want to use to the `DNSBL_LIST` setting.
3. **Apply settings:** Once configured, BunkerWeb will automatically check incoming connections against the specified DNSBL servers.
4. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on requests blocked by DNSBL checks.

### Configuration Settings

**General**

| Setting      | Default                                             | Context   | Multiple | Description                                                                 |
| ------------ | --------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | no       | Enable DNSBL: set to `yes` to enable DNSBL checks for incoming connections. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | no       | DNSBL servers: list of DNSBL server domains to check, separated by spaces.  |

**Ignore Lists**

| Setting                | Default | Context   | Multiple | Description                                                                                    |
| ---------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``      | multisite | yes      | Space-separated IPs/CIDRs to skip DNSBL checks for (whitelist).                                |
| `DNSBL_IGNORE_IP_URLS` | ``      | multisite | yes      | Space-separated URLs providing IPs/CIDRs to skip. Supports `http(s)://` and `file://` schemes. |

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

=== "Excluding Trusted IPs"

    You can exclude specific clients from DNSBL checks using static values and/or remote files:

    - `DNSBL_IGNORE_IP`: Add space-separated IPs and CIDR ranges. Example: `192.0.2.10 203.0.113.0/24 2001:db8::/32`.
    - `DNSBL_IGNORE_IP_URLS`: Provide URLs whose contents list one IP/CIDR per line. Comments starting with `#` or `;` are ignored. Duplicate entries are de-duplicated.

    When an incoming client IP matches the ignore list, BunkerWeb skips DNSBL lookups and caches the result as “ok” for faster subsequent requests.

=== "Using Remote URLs"

    The `dnsbl-download` job downloads and caches ignore IPs hourly:

    - Protocols: `https://`, `http://`, and local `file://` paths.
    - Per-URL cache with checksum prevents redundant downloads (1-hour grace).
    - Per-service merged file: `/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`.
    - Loaded at startup and merged with `DNSBL_IGNORE_IP`.

    Example combining static and URL sources:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://example.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "Using Local Files"

    Load ignore IPs from local files using `file://` URLs:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```

## Database

STREAM support :white_check_mark:

The Database plugin provides a robust database integration for BunkerWeb by enabling centralized storage and management of configuration data, logs, and other essential information.

This core component supports multiple database engines, including SQLite, PostgreSQL, MySQL/MariaDB, and Oracle, allowing you to choose the database solution that best fits your environment and requirements.

**How it works:**

1. BunkerWeb connects to your configured database using the provided URI in the SQLAlchemy format.
2. Critical configuration data, runtime information, and job logs are stored securely in the database.
3. Automatic maintenance processes optimize your database by managing data growth and cleaning up excess records.
4. For high-availability scenarios, you can configure a read-only database URI that serves both as a failover and as a method to offload read operations.
5. Database operations are logged according to your specified log level, providing appropriate visibility into database interactions.

### How to Use

Follow these steps to configure and use the Database feature:

1. **Choose a database engine:** Select from SQLite (default), PostgreSQL, MySQL/MariaDB, or Oracle based on your requirements.
2. **Configure the database URI:** Set the `DATABASE_URI` to connect to your primary database using the SQLAlchemy format.
3. **Optional read-only database:** For high-availability setups, configure a `DATABASE_URI_READONLY` as a fallback or for read operations.

### Configuration Settings

| Setting                         | Default                                   | Context | Multiple | Description                                                                                                           |
| ------------------------------- | ----------------------------------------- | ------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URI`                  | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global  | no       | **Database URI:** The primary database connection string in the SQLAlchemy format.                                    |
| `DATABASE_URI_READONLY`         |                                           | global  | no       | **Read-Only Database URI:** Optional database for read-only operations or as a failover if the main database is down. |
| `DATABASE_LOG_LEVEL`            | `warning`                                 | global  | no       | **Log Level:** The verbosity level for database logs. Options: `debug`, `info`, `warn`, `warning`, or `error`.        |
| `DATABASE_MAX_JOBS_RUNS`        | `10000`                                   | global  | no       | **Maximum Job Runs:** The maximum number of job execution records to retain in the database before automatic cleanup. |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                                      | global  | no       | **Session Retention:** The maximum age (in days) for UI user sessions before they are purged automatically.           |

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
    The plugin automatically runs daily maintenance jobs:

    - **Cleanup Excess Job Runs:** Purges job execution history beyond the `DATABASE_MAX_JOBS_RUNS` limit.
    - **Cleanup Expired UI Sessions:** Removes UI user sessions older than `DATABASE_MAX_SESSION_AGE_DAYS`.

    Together, these jobs prevent unbounded database growth while preserving useful operational history.

## Easy Resolve <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Provides a simpler way to fix false positives in reports.

## Errors

STREAM support :x:

The Errors plugin provides customizable error handling for your website, letting you configure how HTTP error responses appear to users. This feature helps you present user-friendly, branded error pages that enhance the user experience during error scenarios, rather than displaying default server error pages, which can seem technical and confusing to visitors.

**How it works:**

1. When a client encounters an HTTP error (for example, 400, 404, or 500), BunkerWeb intercepts the error response.
2. Instead of showing the default error page, BunkerWeb displays a custom, professionally designed error page.
3. Error pages are fully customizable through your configuration, allowing you to specify custom pages for specific error codes. **Custom error page files must be placed in the directory defined by the `ROOT_FOLDER` setting (see the Miscellaneous plugin documentation).**
   - By default, `ROOT_FOLDER` is `/var/www/html/{server_name}` (where `{server_name}` is replaced by the actual server name).
   - In multisite mode, each site can have its own `ROOT_FOLDER`, so custom error pages must be placed in the corresponding directory for each site.
4. The default error pages provide clear explanations, helping users understand what went wrong and what they can do next.

### How to Use

Follow these steps to configure and use the Errors feature:

1. **Define custom error pages:** Specify which HTTP error codes should use custom error pages using the `ERRORS` setting. The custom error page files must be located in the folder specified by the `ROOT_FOLDER` setting for the site. In multisite mode, this means each site/server can have its own folder for custom error pages.
2. **Configure your error pages:** For each error code, you can use the default BunkerWeb error page or provide your own custom HTML page (placed in the appropriate `ROOT_FOLDER`).
3. **Set intercepted error codes:** Select which error codes should always be handled by BunkerWeb with the `INTERCEPTED_ERROR_CODES` setting.
4. **Let BunkerWeb handle the rest:** Once configured, error handling occurs automatically for all specified error codes.

### Configuration Settings

| Setting                   | Default                                           | Context   | Multiple | Description                                                                                                                                 |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | multisite | no       | **Custom Error Pages:** Map specific error codes to custom HTML files using the format `ERROR_CODE=/path/to/file.html`.                     |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | no       | **Intercepted Errors:** List of HTTP error codes that BunkerWeb should handle with its default error page when no custom page is specified. |

!!! tip "Error Page Design"
    The default BunkerWeb error pages are designed to be informative, user-friendly, and professional in appearance. They include:

    - Clear error descriptions
    - Information about what might have caused the error
    - Suggested actions for users to resolve the issue
    - Visual indicators that help users understand whether the issue is on the client or the server side

!!! info "Error Types"
    Error codes are categorized by type:

    - **4xx errors (client-side):** These indicate issues with the client's request, such as attempting to access non-existent pages or lacking proper authentication.
    - **5xx errors (server-side):** These indicate issues with the server's ability to fulfill a valid request, such as internal server errors or temporary unavailability.

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

The Greylist plugin provides a flexible security approach that allows visitors access while still maintaining essential security features.

Unlike traditional [blacklist](#blacklist)/[whitelist](#whitelist) approaches—that completely block or allow access—greylisting creates a middle ground by granting access to certain visitors while still subjecting them to security checks.

**How it works:**

1. You define criteria for visitors to be greylisted (*IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns*).
2. When a visitor matches any of these criteria, they are granted access to your site while the other security features remain active.
3. If a visitor does not match any greylist criteria, their access is denied.
4. Greylist data can be automatically updated from external sources on a regular schedule.

### How to Use

Follow these steps to configure and use the Greylist feature:

1. **Enable the feature:** The Greylist feature is disabled by default. Set the `USE_GREYLIST` setting to `yes` to enable it.
2. **Configure greylist rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be greylisted.
3. **Add external sources:** Optionally, configure URLs for automatically downloading and updating greylist data.
4. **Monitor access:** Check the [web UI](web-ui.md) to see which visitors are being allowed or denied.

!!! tip "Access Control Behavior"
    When the greylist feature is enabled with the `USE_GREYLIST` setting set to `yes`:

    1. **Greylisted visitors:** Are allowed access but are still subject to all security checks.
    2. **Non-greylisted visitors:** Are completely denied access.

!!! info "stream mode"
    When using stream mode, only IP, rDNS, and ASN checks are performed.

### Configuration Settings

**General**

| Setting        | Default | Context   | Multiple | Description                                              |
| -------------- | ------- | --------- | -------- | -------------------------------------------------------- |
| `USE_GREYLIST` | `no`    | multisite | no       | **Enable Greylist:** Set to `yes` to enable greylisting. |

=== "IP Address"
    **What this does:** Greylist visitors based on their IP address or network. These visitors gain access but remain subject to security checks.

    | Setting            | Default | Context   | Multiple | Description                                                                                              |
    | ------------------ | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |         | multisite | no       | **IP Greylist:** List of IP addresses or networks (in CIDR notation) to greylist, separated by spaces.   |
    | `GREYLIST_IP_URLS` |         | multisite | no       | **IP Greylist URLs:** List of URLs containing IP addresses or networks to greylist, separated by spaces. |

=== "Reverse DNS"
    **What this does:** Greylist visitors based on their domain name (in reverse). Useful for allowing conditional access to visitors from specific organizations or networks.

    | Setting                | Default | Context   | Multiple | Description                                                                                            |
    | ---------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `GREYLIST_RDNS`        |         | multisite | no       | **rDNS Greylist:** List of reverse DNS suffixes to greylist, separated by spaces.                      |
    | `GREYLIST_RDNS_GLOBAL` | `yes`   | multisite | no       | **rDNS Global Only:** Only perform rDNS greylist checks on global IP addresses when set to `yes`.      |
    | `GREYLIST_RDNS_URLS`   |         | multisite | no       | **rDNS Greylist URLs:** List of URLs containing reverse DNS suffixes to greylist, separated by spaces. |

=== "ASN"
    **What this does:** Greylist visitors from specific network providers using Autonomous System Numbers. ASNs identify which provider or organization an IP belongs to.

    | Setting             | Default | Context   | Multiple | Description                                                                           |
    | ------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |         | multisite | no       | **ASN Greylist:** List of Autonomous System Numbers to greylist, separated by spaces. |
    | `GREYLIST_ASN_URLS` |         | multisite | no       | **ASN Greylist URLs:** List of URLs containing ASNs to greylist, separated by spaces. |

=== "User Agent"
    **What this does:** Greylist visitors based on the browser or tool they claim to be using. This allows controlled access for specific tools while maintaining security checks.

    | Setting                    | Default | Context   | Multiple | Description                                                                                         |
    | -------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |         | multisite | no       | **User-Agent Greylist:** List of User-Agent patterns (PCRE regex) to greylist, separated by spaces. |
    | `GREYLIST_USER_AGENT_URLS` |         | multisite | no       | **User-Agent Greylist URLs:** List of URLs containing User-Agent patterns to greylist.              |

=== "URI"
    **What this does:** Greylist requests to specific URLs on your site. This allows conditional access to certain endpoints while maintaining security checks.

    | Setting             | Default | Context   | Multiple | Description                                                                                   |
    | ------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |         | multisite | no       | **URI Greylist:** List of URI patterns (PCRE regex) to greylist, separated by spaces.         |
    | `GREYLIST_URI_URLS` |         | multisite | no       | **URI Greylist URLs:** List of URLs containing URI patterns to greylist, separated by spaces. |

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Greylists from URLs are automatically downloaded and updated hourly to ensure that your protection remains current with the latest trusted sources.


### Example Configurations

=== "Basic Configuration"

    A simple configuration that applies greylisting to a company's internal network and crawler:

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

=== "Selective API Access"

    A configuration allowing access to specific API endpoints:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # External partner network
    ```

### Working with local list files

The `*_URLS` settings provided by the whitelist, greylist, and blacklist plugins all use the same downloader. When you reference a `file:///` URL:

- The path is resolved inside the **scheduler** container (for Docker deployments this is typically `bunkerweb-scheduler`). Mount the files there and ensure they are readable by the scheduler user.
- Each file is plain text encoded in UTF-8 with one entry per line. Empty lines are ignored and comment lines must begin with `#` or `;`. `//` comments are not supported.
- Expected value per list type:
  - **IP lists** accept IPv4/IPv6 addresses or CIDR networks (for example `192.0.2.10` or `2001:db8::/48`).
  - **rDNS lists** expect a suffix without spaces (for example `.search.msn.com`). Values are normalised to lowercase automatically.
  - **ASN lists** may contain just the number (`32934`) or the number prefixed with `AS` (`AS15169`).
  - **User-Agent lists** are treated as PCRE patterns and the whole line is preserved (including spaces). Keep comments on their own line so they are not interpreted as part of the pattern.
  - **URI lists** must start with `/` and may use PCRE tokens such as `^` or `$`.

Example files that match the expected format:

```text
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Gzip

STREAM support :x:

The GZIP plugin enhances website performance by compressing HTTP responses using the GZIP algorithm. This feature reduces bandwidth usage and improves page load times by compressing web content before it is sent to the client's browser, resulting in faster delivery and an improved user experience.

### How It Works

1. When a client requests content from your website, BunkerWeb checks if the client supports GZIP compression.
2. If supported, BunkerWeb compresses the response using the GZIP algorithm at your configured compression level.
3. The compressed content is sent to the client with appropriate headers indicating GZIP compression.
4. The client's browser decompresses the content before rendering it.
5. Both bandwidth usage and page load times are reduced, enhancing overall site performance and user experience.

### How to Use

Follow these steps to configure and use the GZIP compression feature:

1. **Enable the feature:** The GZIP feature is disabled by default. Enable it by setting the `USE_GZIP` setting to `yes`.
2. **Configure MIME types:** Specify which content types should be compressed using the `GZIP_TYPES` setting.
3. **Set minimum size:** Define the minimum response size required for compression with the `GZIP_MIN_LENGTH` setting to avoid compressing small files.
4. **Choose a compression level:** Select your preferred balance between speed and compression ratio using the `GZIP_COMP_LEVEL` setting.
5. **Configure proxied requests:** Specify which proxied requests should be compressed using the `GZIP_PROXIED` setting.

### Configuration Settings

| Setting           | Default                                                                                                                                                                                                                                                                                                                                                                                                                          | Context   | Multiple | Description                                                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Enable GZIP:** Set to `yes` to enable GZIP compression.                                                                        |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **MIME Types:** List of content types that will be compressed with GZIP.                                                         |
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

**How it works:**

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
    - Place CSS and critical JavaScript in the head section to avoid a flash of unstyled content.
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

Headers play a crucial role in HTTP security. The Headers plugin provides robust management of both standard and custom HTTP headers—enhancing security and functionality. It dynamically applies security measures, such as [HSTS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security), [CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy) (including a reporting mode), and custom header injection, while preventing information leakage.

**How it works**

1. When a client requests content from your website, BunkerWeb processes the response headers.
2. Security headers are applied in accordance with your configuration.
3. Custom headers can be added to provide additional information or functionality to clients.
4. Unwanted headers that might reveal server information are automatically removed.
5. Cookies are modified to include appropriate security flags based on your settings.
6. Headers from upstream servers can be selectively preserved when needed.

### How to Use

Follow these steps to configure and use the Headers feature:

1. **Configure security headers:** Set values for common headers.
2. **Add custom headers:** Define any custom headers using the `CUSTOM_HEADER` setting.
3. **Remove unwanted headers:** Use `REMOVE_HEADERS` to ensure headers that could expose server details are stripped out.
4. **Set cookie security:** Enable robust cookie security by configuring `COOKIE_FLAGS` and setting `COOKIE_AUTO_SECURE_FLAG` to `yes` so that the Secure flag is automatically added on HTTPS connections.
5. **Preserve upstream headers:** Specify which upstream headers to retain by using `KEEP_UPSTREAM_HEADERS`.
6. **Leverage conditional header application:** If you wish to test policies without disruption, enable [CSP Report-Only](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) mode via `CONTENT_SECURITY_POLICY_REPORT_ONLY`.

### Configuration Guide

=== "Security Headers"

    **Overview**

    Security headers enforce secure communication, restrict resource loading, and prevent attacks like clickjacking and injection. Properly configured headers create a robust defensive layer for your website.

    !!! success "Benefits of Security Headers"
        - **HSTS:** Ensures all connections are encrypted, protecting against protocol downgrade attacks.
        - **CSP:** Prevents malicious scripts from executing, reducing the risk of XSS attacks.
        - **X-Frame-Options:** Blocks clickjacking attempts by controlling iframe embedding.
        - **Referrer Policy:** Limits sensitive information leakage through referrer headers.

    | Setting                               | Default                                                                                             | Context   | Multiple | Description                                                                                                                  |
    | ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
    | `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | no       | **HSTS:** Enforces secure HTTPS connections, reducing risks of man-in-the-middle attacks.                                    |
    | `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | no       | **CSP:** Restricts resource loading to trusted sources, mitigating cross-site scripting and data injection attacks.          |
    | `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | no       | **CSP Report Mode:** Reports violations without blocking content, helping in testing security policies while capturing logs. |
    | `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | no       | **X-Frame-Options:** Prevents clickjacking by controlling whether your site can be framed.                                   |
    | `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | no       | **X-Content-Type-Options:** Prevents browsers from MIME-sniffing, protecting against drive-by download attacks.              |
    | `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | no       | **X-DNS-Prefetch-Control:** Regulates DNS prefetching to reduce unintentional network requests and enhance privacy.          |
    | `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | no       | **Referrer Policy:** Controls the amount of referrer information sent, safeguarding user privacy.                            |
    | `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | no       | **Permissions Policy:** Restricts browser feature access, reducing potential attack vectors.                                 |
    | `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | no       | **Keep Headers:** Preserves selected upstream headers, aiding legacy integration while maintaining security.                 |

    !!! tip "Best Practices"
        - Regularly review and update your security headers to align with evolving security standards.
        - Use tools like [Mozilla Observatory](https://observatory.mozilla.org/) to validate your header configuration.
        - Test CSP in `Report-Only` mode before enforcing it to avoid breaking functionality.

=== "Cookie Settings"

    **Overview**

    Proper cookie settings ensure secure user sessions by preventing hijacking, fixation, and cross-site scripting. Secure cookies maintain session integrity over HTTPS and enhance overall user data protection.

    !!! success "Benefits of Secure Cookies"
        - **HttpOnly Flag:** Prevents client-side scripts from accessing cookies, mitigating XSS risks.
        - **SameSite Flag:** Reduces CSRF attacks by restricting cross-origin cookie usage.
        - **Secure Flag:** Ensures cookies are transmitted only over encrypted HTTPS connections.

    | Setting                   | Default                   | Context   | Multiple | Description                                                                                                                                            |
    | ------------------------- | ------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | yes      | **Cookie Flags:** Automatically adds security flags such as HttpOnly and SameSite, protecting cookies from client-side script access and CSRF attacks. |
    | `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | no       | **Auto Secure Flag:** Ensures cookies are only sent over secure HTTPS connections by appending the Secure flag automatically.                          |

    !!! tip "Best Practices"
        - Use `SameSite=Strict` for sensitive cookies to prevent cross-origin access.
        - Regularly audit your cookie settings to ensure compliance with security and privacy regulations.
        - Avoid setting cookies without the Secure flag in production environments.

=== "Custom Headers"

    **Overview**

    Custom headers allow you to add specific HTTP headers to meet application or performance requirements. They offer flexibility but must be carefully configured to avoid exposing sensitive server details.

    !!! success "Benefits of Custom Headers"
        - Enhance security by removing unnecessary headers that may leak server details.
        - Add application-specific headers to improve functionality or debugging.

    | Setting          | Default                                                                              | Context   | Multiple | Description                                                                                                                                                 |
    | ---------------- | ------------------------------------------------------------------------------------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `CUSTOM_HEADER`  |                                                                                      | multisite | yes      | **Custom Header:** Provides a means to add user-defined headers in the format HeaderName: HeaderValue for specialized security or performance enhancements. |
    | `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | no       | **Remove Headers:** Specifies headers to remove, decreasing the chance of exposing internal server details and known vulnerabilities.                       |

    !!! warning "Security Considerations"
        - Avoid exposing sensitive information through custom headers.
        - Regularly review and update custom headers to align with your application's requirements.

    !!! tip "Best Practices"
        - Use `REMOVE_HEADERS` to strip out headers like `Server` and `X-Powered-By` to reduce fingerprinting risks.
        - Test custom headers in a staging environment before deploying them to production.

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

**How it works:**

1. When enabled, BunkerWeb automatically detects the domains configured for your website.
2. BunkerWeb requests free SSL/TLS certificates from Let's Encrypt's certificate authority.
3. Domain ownership is verified through either HTTP challenges (proving you control the website) or DNS challenges (proving you control your domain's DNS).
4. Certificates are automatically installed and configured for your domains.
5. BunkerWeb handles certificate renewals in the background before expiration, ensuring continuous HTTPS availability.
6. The entire process is fully automated, requiring minimal intervention after the initial setup.

!!! info "Prerequisites"
    To use this feature, ensure that proper DNS **A records** are configured for each domain, pointing to the public IP(s) where BunkerWeb is accessible. Without correct DNS configuration, the domain verification process will fail.

### How to Use

Follow these steps to configure and use the Let's Encrypt feature:

1. **Enable the feature:** Set the `AUTO_LETS_ENCRYPT` setting to `yes` to enable automatic certificate issuance and renewal.
2. **Provide contact email (recommended):** Enter your email address using the `EMAIL_LETS_ENCRYPT` setting so Let's Encrypt can warn you before certificates expire. If you leave it blank, BunkerWeb registers without an address (Certbot's `--register-unsafely-without-email`), but you won't receive renewal reminders or recovery emails.
3. **Choose challenge type:** Select either `http` or `dns` verification with the `LETS_ENCRYPT_CHALLENGE` setting.
4. **Configure DNS provider:** If using DNS challenges, specify your DNS provider and credentials.
5. **Select certificate profile:** Choose your preferred certificate profile using the `LETS_ENCRYPT_PROFILE` setting (classic, tlsserver, or shortlived).
6. **Let BunkerWeb handle the rest:** Once configured, certificates are automatically issued, installed, and renewed as needed.

!!! tip "Certificate Profiles"
    Let's Encrypt provides different certificate profiles for different use cases:

    - **classic**: General-purpose certificates with 90-day validity (default)
    - **tlsserver**: Optimized for TLS server authentication with 90-day validity and smaller payload
    - **shortlived**: Enhanced security with 7-day validity for automated environments
    - **custom**: If your ACME server supports a different profile, set it using `LETS_ENCRYPT_CUSTOM_PROFILE`.

!!! info "Profile Availability"
    Note that the `tlsserver` and `shortlived` profiles may not be available in all environments or with all ACME clients at this time. The `classic` profile has the widest compatibility and is recommended for most users. If a selected profile is not available, the system will automatically fall back to the `classic` profile.

### Configuration Settings

| Setting                                     | Default   | Context   | Multiple | Description                                                                                                                                                                                                                                                                    |
| ------------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | no       | **Enable Let's Encrypt:** Set to `yes` to enable automatic certificate issuance and renewal.                                                                                                                                                                                   |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | no       | **Pass Through Let's Encrypt:** Set to `yes` to pass through Let's Encrypt requests to the web server. This is useful when BunkerWeb is behind another reverse proxy handling SSL.                                                                                             |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | no       | **Contact Email:** Email address used for Let's Encrypt expiry reminders. Leave blank only if you accept that no alerts or recovery emails will be sent (Certbot registers with `--register-unsafely-without-email`).                                                          |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | no       | **Challenge Type:** Method used to verify domain ownership. Options: `http` or `dns`.                                                                                                                                                                                          |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | no       | **DNS Provider:** When using DNS challenges, the DNS provider to use (e.g., cloudflare, route53, digitalocean).                                                                                                                                                                |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | no       | **DNS Propagation:** The time to wait for DNS propagation in seconds. If no value is provided, the provider's default propagation time is used.                                                                                                                                |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | yes      | **Credential Item:** Configuration items for DNS provider authentication (e.g., `cloudflare_api_token 123456`). Values can be raw text, base64 encoded, or a JSON object.                                                                                                      |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | no       | **Decode Base64 DNS credentials:** Automatically decode base64-encoded DNS provider credentials when set to `yes`. Values matching base64 format are decoded before use (except for the `rfc2136` provider). Set to `no` if your credentials are intentionally base64 strings. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | no       | **Wildcard Certificates:** When set to `yes`, creates wildcard certificates for all domains. Only available with DNS challenges.                                                                                                                                               |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | no       | **Use Staging:** When set to `yes`, uses Let's Encrypt's staging environment for testing. Staging has higher rate limits but produces certificates that are not trusted by browsers.                                                                                           |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | no       | **Clear Old Certificates:** When set to `yes`, removes old certificates that are no longer needed during renewal.                                                                                                                                                              |
| `LETS_ENCRYPT_CONCURRENT_REQUESTS`          | `no`      | global    | no       | **Concurrent Requests:** When set to `yes`, certbot-new issues certificate requests concurrently. Use with caution to avoid rate limits.                                                                                                                                       |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | no       | **Certificate Profile:** Select the certificate profile to use. Options: `classic` (general-purpose), `tlsserver` (optimized for TLS servers), or `shortlived` (7-day certificates).                                                                                           |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | no       | **Custom Certificate Profile:** Enter a custom certificate profile if your ACME server supports non-standard profiles. This overrides `LETS_ENCRYPT_PROFILE` if set.                                                                                                           |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | no       | **Maximum Retries:** Number of times to retry certificate generation on failure. Set to `0` to disable retries. Useful for handling temporary network issues or API rate limits.                                                                                               |

!!! info "Information and behavior"
    - The `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting is a multiple setting and can be used to set multiple items for the DNS provider. The items will be saved as a cache file, and Certbot will read the credentials from it.
    - If no `LETS_ENCRYPT_DNS_PROPAGATION` setting is provided, the provider's default propagation time is used.
    - Full Let's Encrypt automation using the `http` challenge works in stream mode as long as you open the `80/tcp` port from the outside. Use the `LISTEN_STREAM_PORT_SSL` setting to choose your listening SSL/TLS port.
    - If `LETS_ENCRYPT_PASSTHROUGH` is set to `yes`, BunkerWeb will not handle the ACME challenge requests itself but will pass them to the backend web server. This is useful in scenarios where BunkerWeb is acting as a reverse proxy in front of another server that is configured to handle Let's Encrypt challenges

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

| Provider          | Description      | Mandatory Settings                                                                                           | Optional Settings                                                                                                                                                                                                                                                        | Documentation                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | either `api_token`<br>or `email` and `api_key`                                                               |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (default: `600`)                                                                                                                                                                                                                                                   | [Documentation](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (default: `service_account`)<br>`auth_uri` (default: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (default: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (default: `https://www.googleapis.com/oauth2/v1/certs`) | [Documentation](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (default: `https://api.hosting.ionos.com`)                                                                                                                                                                                                                    | [Documentation](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (default: `ovh-eu`)                                                                                                                                                                                                                                           | [Documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (default: `53`)<br>`algorithm` (default: `HMAC-SHA512`)<br>`sign_query` (default: `false`)                                                                                                                                                                        | [Documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |
| `transip`         | TransIP          | `key_file`<br>`username`                                                                                     |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-transip.readthedocs.io/en/stable/)                                |

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
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token YOUR_API_TOKEN"
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

=== "Testing with Staging Environment and Retries"

    Configuration for testing setup with the staging environment and enhanced retry settings:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean with Custom Propagation Time"

    Configuration using DigitalOcean DNS with a longer propagation wait time:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token YOUR_API_TOKEN"
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

The Limit plugin in BunkerWeb provides robust capabilities to enforce limiting policies on your website, ensuring fair usage and protecting your resources from abuse, denial-of-service attacks, and excessive resource consumption. These policies include:

- **Number of connections per IP address** (STREAM support :white_check_mark:)
- **Number of requests per IP address and URL within a specific time period** (STREAM support :x:)

### How it Works

1. **Rate Limiting:** Tracks the number of requests from each client IP address to specific URLs. If a client exceeds the configured rate limit, subsequent requests are temporarily denied.
2. **Connection Limiting:** Monitors and restricts the number of concurrent connections from each client IP address. Different connection limits can be applied based on the protocol used (HTTP/1, HTTP/2, HTTP/3, or stream).
3. In both cases, clients that exceed the defined limits receive an HTTP status code **"429 - Too Many Requests"**, which helps prevent server overload.

### Steps to Use

1. **Enable Request Rate Limiting:** Use `USE_LIMIT_REQ` to enable request rate limiting and define URL patterns along with their corresponding rate limits.
2. **Enable Connection Limiting:** Use `USE_LIMIT_CONN` to enable connection limiting and set the maximum number of concurrent connections for different protocols.
3. **Apply Granular Control:** Create multiple rate limit rules for different URLs to provide varying levels of protection across your site.
4. **Monitor Effectiveness:** Use the [web UI](web-ui.md) to view statistics on limited requests and connections.

### Configuration Settings

=== "Request Rate Limiting"

    | Setting          | Default | Context   | Multiple | Description                                                                                                                                                        |
    | ---------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `USE_LIMIT_REQ`  | `yes`   | multisite | no       | **Enable Request Limiting:** Set to `yes` to enable the request rate limiting feature.                                                                             |
    | `LIMIT_REQ_URL`  | `/`     | multisite | yes      | **URL Pattern:** URL pattern (PCRE regex) to which the rate limit will be applied; use `/` to apply for all requests.                                              |
    | `LIMIT_REQ_RATE` | `2r/s`  | multisite | yes      | **Rate Limit:** Maximum request rate in the format `Nr/t`, where N is the number of requests and t is the time unit: s (second), m (minute), h (hour), or d (day). |

    !!! tip "Rate Limiting Format"
        The rate limit format is specified as `Nr/t` where:

        - `N` is the number of requests allowed
        - `r` is a literal 'r' (for 'requests')
        - `/` is a literal slash
        - `t` is the time unit: `s` (second), `m` (minute), `h` (hour), or `d` (day)

        For example, `5r/m` means that 5 requests per minute are allowed from each IP address.

=== "Connection Limiting"

    | Setting                 | Default | Context   | Multiple | Description                                                                                 |
    | ----------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_CONN`        | `yes`   | multisite | no       | **Enable Connection Limiting:** Set to `yes` to enable the connection limiting feature.     |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`    | multisite | no       | **HTTP/1.X Connections:** Maximum number of concurrent HTTP/1.X connections per IP address. |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`   | multisite | no       | **HTTP/2 Streams:** Maximum number of concurrent HTTP/2 streams per IP address.             |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`   | multisite | no       | **HTTP/3 Streams:** Maximum number of concurrent HTTP/3 streams per IP address.             |
    | `LIMIT_CONN_MAX_STREAM` | `10`    | multisite | no       | **Stream Connections:** Maximum number of concurrent stream connections per IP address.     |

!!! info "Connection vs. Request Limiting"
    - **Connection limiting** restricts the number of simultaneous connections that a single IP address can maintain.
    - **Request rate limiting** restricts the number of requests an IP address can make within a defined period of time.

    Using both methods provides comprehensive protection against various types of abuse.

!!! warning "Setting Appropriate Limits"
    Setting limits too restrictively may impact legitimate users, especially for HTTP/2 and HTTP/3 where browsers often use multiple streams. The default values are balanced for most use cases, but consider adjusting them based on your application's needs and user behavior.

### Example Configurations

=== "Basic Protection"

    A simple configuration using default settings to protect your entire site:

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

## Load Balancer <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/cOVp0rAt5nw' title='Load Balancer' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

STREAM support :x:

Provides load balancing feature to group of upstreams with optional healthchecks.

| Setting                                   | Default       | Context | Multiple | Description                                                        |
| ----------------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------ |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`         | global  | no       | Shared dict size (datastore for all healthchecks).                 |
| `LOADBALANCER_UPSTREAM_NAME`              |               | global  | yes      | Name of the upstream (used in REVERSE_PROXY_HOST).                 |
| `LOADBALANCER_UPSTREAM_SERVERS`           |               | global  | yes      | List of servers/IPs in the server group.                           |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin` | global  | yes      | Load balancing mode (round-robin or sticky).                       |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`          | global  | yes      | Sticky session method (ip or cookie).                              |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`          | global  | yes      | Dynamically resolve upstream hostnames.                            |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |               | global  | yes      | Number of keepalive connections to cache per worker.               |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`         | global  | yes      | Keepalive timeout for upstream connections.                        |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`          | global  | yes      | Keepalive time for upstream connections.                           |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status`     | global  | yes      | The healthcheck URL.                                               |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`        | global  | yes      | Healthcheck interval in milliseconds.                              |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`        | global  | yes      | Healthcheck timeout in milliseconds.                               |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`           | global  | yes      | Number of failed healthchecks before marking the server as down.   |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`           | global  | yes      | Number of successful healthchecks before marking the server as up. |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`         | global  | yes      | HTTP status considered valid in healthchecks.                      |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`          | global  | yes      | Maximum number of concurrent healthchecks.                         |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`        | global  | yes      | Type of healthcheck (http or https).                               |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`         | global  | yes      | Verify SSL certificate in healthchecks.                            |
| `LOADBALANCER_HEALTHCHECK_HOST`           |               | global  | yes      | Host header for healthchecks (useful for HTTPS).                   |

## Metrics

STREAM support :warning:

The Metrics plugin provides comprehensive monitoring and data collection capabilities for your BunkerWeb instance. This feature enables you to track various performance indicators, security events, and system statistics, giving you valuable insights into the behavior and health of your protected websites and services.

**How it works:**

1. BunkerWeb collects key metrics during the processing of requests and responses.
2. These metrics include counters for blocked requests, performance measurements, and various security-related statistics.
3. The data is stored efficiently in memory, with configurable limits to prevent excessive resource usage.
4. For multi-instance setups, Redis can be used to centralize and aggregate metrics data.
5. The collected metrics can be accessed through the API or visualized in the [web UI](web-ui.md).
6. This information helps you identify security threats, troubleshoot issues, and optimize your configuration.

### Technical Implementation

The metrics plugin works by:

- Using shared dictionaries in NGINX, where `metrics_datastore` is used for HTTP and `metrics_datastore_stream` for TCP/UDP traffic
- Leveraging an LRU cache for efficient in-memory storage
- Periodically synchronizing data between workers using timers
- Storing detailed information about blocked requests, including the client IP address, country, timestamp, request details, and block reason
- Supporting plugin-specific metrics through a common metrics collection interface
- Providing API endpoints for querying collected metrics

### How to Use

Follow these steps to configure and use the Metrics feature:

1. **Enable the feature:** Metrics collection is enabled by default. You can control this with the `USE_METRICS` setting.
2. **Configure memory allocation:** Set the amount of memory to allocate for metrics storage using the `METRICS_MEMORY_SIZE` setting.
3. **Set storage limits:** Define how many blocked requests to store per worker and in Redis with the respective settings.
4. **Access the data:** View the collected metrics through the [web UI](web-ui.md) or API endpoints.
5. **Analyze the information:** Use the gathered data to identify patterns, detect security issues, and optimize your configuration.

### Collected Metrics

The metrics plugin collects the following information:

1. **Blocked Requests**: For each blocked request, the following data is stored:
      - Request ID and timestamp
      - Client IP address and country (when available)
      - HTTP method and URL
      - HTTP status code
      - User agent
      - Block reason and security mode
      - Server name
      - Additional data related to the block reason

2. **Plugin Counters**: Various plugin-specific counters that track activities and events.

### API Access

Metrics data can be accessed via BunkerWeb's internal API endpoints:

- **Endpoint**: `/metrics/{filter}`
- **Method**: GET
- **Description**: Retrieves metrics data based on the specified filter
- **Response Format**: JSON object containing the requested metrics

For example, `/metrics/requests` returns information about blocked requests.

!!! info "API Access Configuration"
    To access metrics via the API, you must ensure that:

    1. The API feature is enabled with `USE_API: "yes"` (enabled by default)
    2. Your client IP is included in the `API_WHITELIST_IP` setting (default is `127.0.0.0/8`)
    3. You are accessing the API on the configured port (default is `5000` via the `API_HTTP_PORT` setting)
    4. You are using the correct `API_SERVER_NAME` value in the Host header (default is `bwapi`)
    5. If `API_TOKEN` is configured, include `Authorization: Bearer <token>` in the request headers.

    Typical requests:

    Without token (when `API_TOKEN` is not set):
    ```bash
    curl -H "Host: bwapi" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    With token (when `API_TOKEN` is set):
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    If you have customized the `API_SERVER_NAME` to something other than the default `bwapi`, use that value in the Host header instead.

    For secure production environments, restrict API access to trusted IPs and enable `API_TOKEN`.

### Configuration Settings

| Setting                              | Default  | Context   | Multiple | Description                                                                                                          |
| ------------------------------------ | -------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`    | multisite | no       | **Enable Metrics:** Set to `yes` to enable collection and retrieval of metrics.                                      |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | no       | **Memory Size:** Size of the internal storage for metrics (e.g., `16m`, `32m`).                                      |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | no       | **Max Blocked Requests:** Maximum number of blocked requests to store per worker.                                    |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | no       | **Max Redis Blocked Requests:** Maximum number of blocked requests to store in Redis.                                |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | no       | **Save Metrics to Redis:** Set to `yes` to save metrics (counters and tables) to Redis for cluster-wide aggregation. |

!!! tip "Sizing Memory Allocation"
    The `METRICS_MEMORY_SIZE` setting should be adjusted based on your traffic volume and the number of instances. For high-traffic sites, consider increasing this value to ensure all metrics are captured without data loss.

!!! info "Redis Integration"
    When BunkerWeb is configured to use [Redis](#redis), the metrics plugin will automatically synchronize blocked request data to the Redis server. This provides a centralized view of security events across multiple BunkerWeb instances.

!!! warning "Performance Considerations"
    Setting very high values for `METRICS_MAX_BLOCKED_REQUESTS` or `METRICS_MAX_BLOCKED_REQUESTS_REDIS` can increase memory usage. Monitor your system resources and adjust these values according to your actual needs and available resources.

!!! note "Worker-Specific Storage"
    Each NGINX worker maintains its own metrics in memory. When accessing metrics through the API, data from all workers is automatically aggregated to provide a complete view.

### Example Configurations

=== "Basic Configuration"

    Default configuration suitable for most deployments:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Low-Resource Environment"

    Configuration optimized for environments with limited resources:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "High-Traffic Environment"

    Configuration for high-traffic websites that need to track more security events:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Metrics Disabled"

    Configuration with metrics collection disabled:

    ```yaml
    USE_METRICS: "no"
    ```

## Migration <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


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

    In HTTP, the `Host` header specifies the target server, but it may be missing or unknown, often due to bots scanning for vulnerabilities.

    To block such requests:

    - Set `DISABLE_DEFAULT_SERVER` to `yes` to silently deny such requests using [NGINX's `444` status code](https://http.dev/444).
    - For stricter security, enable `DISABLE_DEFAULT_SERVER_STRICT_SNI` to reject SSL/TLS connections without valid SNI.

    !!! success "Security Benefits"
        - Blocks Host header manipulation and virtual host scanning
        - Mitigates HTTP request smuggling risks
        - Removes the default server as an attack vector

    | Setting                             | Default | Context | Multiple | Description                                                                                                      |
    | ----------------------------------- | ------- | ------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `DISABLE_DEFAULT_SERVER`            | `no`    | global  | no       | **Default Server:** Set to `yes` to disable the default server when no hostname matches the request.             |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`    | global  | no       | **Strict SNI:** When set to `yes`, requires SNI for HTTPS connections and rejects connections without valid SNI. |

    !!! warning "SNI Enforcement"
        Enabling strict SNI validation provides stronger security but may cause issues if BunkerWeb is behind a reverse proxy that forwards HTTPS requests without preserving SNI information. Test thoroughly before enabling in production environments.

=== "Deny HTTP Status"

    **HTTP Status Control**

    The first step in handling denied client access is defining the appropriate action. This can be configured using the `DENY_HTTP_STATUS` setting. When BunkerWeb denies a request, you can control its response using this setting. By default, it returns a `403 Forbidden` status, displaying a web page or custom content to the client.

    Alternatively, setting it to `444` closes the connection immediately without sending any response. This [non-standard status code](https://http.dev/444), specific to NGINX, is useful for silently dropping unwanted requests.

    | Setting            | Default | Context | Multiple | Description                                                                                                         |
    | ------------------ | ------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `DENY_HTTP_STATUS` | `403`   | global  | no       | **Deny HTTP Status:** HTTP status code to send when request is denied (403 or 444). Code 444 closes the connection. |

    !!! warning "444 Status Code considerations"
        Since clients receive no feedback, troubleshooting can be more challenging. Setting `444` is recommended only if you have thoroughly addressed false positives, are experienced with BunkerWeb, and require a higher level of security.

    !!! info "Stream mode"
        In **stream mode**, this setting is always enforced as `444`, meaning the connection will be closed, regardless of the configured value.

=== "HTTP Methods"

    **HTTP Method Control**

    Restricting HTTP methods to only those required by your application is a fundamental security measure that adheres to the principle of least privilege. By explicitly defining acceptable HTTP methods, you can minimize the risk of exploitation through unused or dangerous methods.

    This feature is configured using the `ALLOWED_METHODS` setting, where methods are listed and separated by a `|` (default: `GET|POST|HEAD`). If a client attempts to use a method not listed, the server will respond with a **405 - Method Not Allowed** status.

    For most websites, the default `GET|POST|HEAD` is sufficient. If your application uses RESTful APIs, you may need to include methods like `PUT` and `DELETE`.

    !!! success "Security Benefits"
        - Prevents exploitation of unused or unnecessary HTTP methods
        - Reduces the attack surface by disabling potentially harmful methods
        - Blocks HTTP method enumeration techniques used by attackers

    | Setting           | Default | Context | Multiple | Description |
    | ----------------- | ------- | ------- | -------- | ----------- |
    | `ALLOWED_METHODS` | `GET    | POST    | HEAD`    | multisite   | no | **HTTP Methods:** List of HTTP methods that are allowed, separated by pipe characters. |

    !!! abstract "CORS and Pre-flight Requests"
        If your application supports [Cross-Origin Resource Sharing (CORS)](#cors), you should include the `OPTIONS` method in the `ALLOWED_METHODS` setting to handle pre-flight requests. This ensures proper functionality for browsers making cross-origin requests.

    !!! danger "Security Considerations"
        - **Avoid enabling `TRACE` or `CONNECT`:** These methods are rarely needed and can introduce significant security risks, such as enabling Cross-Site Tracing (XST) or tunneling attacks.
        - **Regularly review allowed methods:** Periodically audit the `ALLOWED_METHODS` setting to ensure it aligns with your application's current requirements.
        - **Test thoroughly before deployment:** Changes to HTTP method restrictions can impact application functionality. Validate your configuration in a staging environment before applying it to production.

=== "Request Size Limits"

    **Request Size Limits**

    The maximum request body size can be controlled using the `MAX_CLIENT_SIZE` setting (default: `10m`). Accepted values follow the syntax described [here](https://nginx.org/en/docs/syntax.html).

    !!! success "Security Benefits"
        - Protects against denial-of-service attacks caused by excessive payload sizes
        - Mitigates buffer overflow vulnerabilities
        - Prevents file upload attacks
        - Reduces the risk of server resource exhaustion

    | Setting           | Default | Context   | Multiple | Description                                                                                        |
    | ----------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`   | multisite | no       | **Maximum Request Size:** The maximum allowed size for client request bodies (e.g., file uploads). |

    !!! tip "Request Size Configuration Best Practices"
        If you need to allow a request body of unlimited size, you can set the `MAX_CLIENT_SIZE` value to `0`. However, this is **not recommended** due to potential security and performance risks.

        **Best Practices:**

        - Always configure `MAX_CLIENT_SIZE` to the smallest value that meets your application's legitimate requirements.
        - Regularly review and adjust this setting to align with your application's evolving needs.
        - Avoid setting `0` unless absolutely necessary, as it can expose your server to denial-of-service attacks and resource exhaustion.

        By carefully managing this setting, you can ensure optimal security and performance for your application.

=== "Protocol Support"

    **HTTP Protocol Settings**

    Modern HTTP protocols like HTTP/2 and HTTP/3 improve performance and security. BunkerWeb allows easy configuration of these protocols.

    !!! success "Security and Performance Benefits"
        - **Security Advantages:** Modern protocols like HTTP/2 and HTTP/3 enforce TLS/HTTPS by default, reduce susceptibility to certain attacks, and improve privacy through encrypted headers (HTTP/3).
        - **Performance Benefits:** Features like multiplexing, header compression, server push, and binary data transfer enhance speed and efficiency.

    | Setting              | Default | Context   | Multiple | Description                                                             |
    | -------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`   | multisite | no       | **HTTP Listen:** Respond to (insecure) HTTP requests when set to `yes`. |
    | `HTTP2`              | `yes`   | multisite | no       | **HTTP2:** Support HTTP2 protocol when HTTPS is enabled.                |
    | `HTTP3`              | `yes`   | multisite | no       | **HTTP3:** Support HTTP3 protocol when HTTPS is enabled.                |
    | `HTTP3_ALT_SVC_PORT` | `443`   | multisite | no       | **HTTP3 Alt-Svc Port:** Port to use in the Alt-Svc header for HTTP3.    |

    !!! example "About HTTP/3"
        HTTP/3, the latest version of the Hypertext Transfer Protocol, uses QUIC over UDP instead of TCP, addressing issues like head-of-line blocking for faster, more reliable connections.

        NGINX introduced experimental support for HTTP/3 and QUIC starting with version 1.25.0. However, this feature is still experimental, and caution is advised for production use. For more details, see [NGINX's official documentation](https://nginx.org/en/docs/quic.html).

        Thorough testing is recommended before enabling HTTP/3 in production environments.

=== "Static File Serving"

    **File Serving Configuration**

    BunkerWeb can serve static files directly or act as a reverse proxy to an application server. By default, files are served from `/var/www/html/{server_name}`.

    | Setting       | Default                       | Context   | Multiple | Description                                                                                            |
    | ------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `SERVE_FILES` | `yes`                         | multisite | no       | **Serve Files:** When set to `yes`, BunkerWeb will serve static files from the configured root folder. |
    | `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | no       | **Root Folder:** The directory from which to serve static files. Empty means use the default location. |

    !!! tip "Best Practices for Static File Serving"
        - **Direct Serving:** Enable file serving (`SERVE_FILES=yes`) when BunkerWeb is responsible for serving static files directly.
        - **Reverse Proxy:** If BunkerWeb acts as a reverse proxy, **deactivate file serving** (`SERVE_FILES=no`) to reduce the attack surface and avoid exposing unnecessary directories.
        - **Permissions:** Ensure proper file permissions and path configurations to prevent unauthorized access.
        - **Security:** Avoid exposing sensitive directories or files through misconfigurations.

        By carefully managing static file serving, you can optimize performance while maintaining a secure environment.

=== "System Settings"

    **Plugin and System Management**

    These settings manage BunkerWeb's interaction with external systems and contribute to improving the product through optional anonymous usage statistics.

    **Anonymous Reporting**

    Anonymous reporting provides the BunkerWeb team with insights into how the software is being used. This helps identify areas for improvement and prioritize feature development. The reports are strictly statistical and do not include any sensitive or personally identifiable information. They cover:

    - Enabled features
    - General configuration patterns

    You can disable this feature if desired by setting `SEND_ANONYMOUS_REPORT` to `no`.

    **External Plugins**

    External plugins enable you to extend BunkerWeb's functionality by integrating third-party modules. This allows for additional customization and advanced use cases.

    !!! danger "External Plugin Security"
        **External plugins can introduce security risks if not properly vetted.** Follow these best practices to minimize potential threats:

        - Only use plugins from trusted sources.
        - Verify plugin integrity using checksums when available.
        - Regularly review and update plugins to ensure security and compatibility.

        For more details, refer to the [Plugins documentation](plugins.md).

    | Setting                 | Default | Context | Multiple | Description                                                                    |
    | ----------------------- | ------- | ------- | -------- | ------------------------------------------------------------------------------ |
    | `SEND_ANONYMOUS_REPORT` | `yes`   | global  | no       | **Anonymous Reports:** Send anonymous usage reports to BunkerWeb maintainers.  |
    | `EXTERNAL_PLUGIN_URLS`  |         | global  | no       | **External Plugins:** URLs for external plugins to download (space-separated). |

=== "File Caching"

    **File Cache Optimization**

    The open file cache improves performance by storing file descriptors and metadata in memory, reducing the need for repeated file system operations.

    !!! success "Benefits of File Caching"
        - **Performance:** Reduces filesystem I/O, decreases latency, and lowers CPU usage for file operations.
        - **Security:** Mitigates timing attacks by caching error responses and reduces the impact of DoS attacks targeting the filesystem.

    | Setting                    | Default                 | Context   | Multiple | Description                                                                                          |
    | -------------------------- | ----------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no       | **Enable Cache:** Enable caching of file descriptors and metadata to improve performance.            |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no       | **Cache Configuration:** Configure the open file cache (e.g., maximum entries and inactive timeout). |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no       | **Cache Errors:** Cache file descriptor lookup errors as well as successful lookups.                 |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no       | **Minimum Uses:** Minimum number of accesses during the inactive period for a file to remain cached. |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no       | **Cache Validity:** Time after which cached elements are revalidated.                                |

    **Configuration Guide**

    To enable and configure file caching:
    1. Set `USE_OPEN_FILE_CACHE` to `yes` to activate the feature.
    2. Adjust `OPEN_FILE_CACHE` parameters to define the maximum number of cached entries and their inactive timeout.
    3. Use `OPEN_FILE_CACHE_ERRORS` to cache both successful and failed lookups, reducing repeated filesystem operations.
    4. Set `OPEN_FILE_CACHE_MIN_USES` to specify the minimum number of accesses required for a file to remain cached.
    5. Define the cache validity period with `OPEN_FILE_CACHE_VALID` to control how often cached elements are revalidated.

    !!! tip "Best Practices"
        - Enable file caching for websites with many static files to improve performance.
        - Regularly review and fine-tune cache settings to balance performance and resource usage.
        - In dynamic environments where files change frequently, consider reducing the cache validity period or disabling the feature to ensure content freshness.

### Example Configurations

=== "Default Server Security"

    Example configuration for disabling the default server and enforcing strict SNI:

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "Deny HTTP Status"

    Example configuration for silently dropping unwanted requests:

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "HTTP Methods"

    Example configuration for restricting HTTP methods to only those required by a RESTful API:

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "Request Size Limits"

    Example configuration for limiting the maximum request body size:

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "Protocol Support"

    Example configuration for enabling HTTP/2 and HTTP/3 with a custom Alt-Svc port:

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "Static File Serving"

    Example configuration for serving static files from a custom root folder:

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "File Caching"

    Example configuration for enabling and optimizing file caching:

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"

## ModSecurity

STREAM support :x:

The ModSecurity plugin integrates the powerful [ModSecurity](https://modsecurity.org) Web Application Firewall (WAF) into BunkerWeb. This integration delivers robust protection against a wide range of web attacks by leveraging the [OWASP Core Rule Set (CRS)](https://coreruleset.org) to detect and block threats such as SQL injection, cross-site scripting (XSS), local file inclusion, and more.

**How it works:**

1. When a request is received, ModSecurity evaluates it against the active rule set.
2. The OWASP Core Rule Set inspects headers, cookies, URL parameters, and body content.
3. Each detected violation contributes to an overall anomaly score.
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

1. **Enable the feature:** ModSecurity is enabled by default. This can be controlled using the `USE_MODSECURITY` setting.
2. **Select a CRS version:** Choose a version of the OWASP Core Rule Set (v3, v4, or nightly).
3. **Add plugins:** Optionally activate CRS plugins to enhance rule coverage.
4. **Monitor and tune:** Use logs and the [web UI](web-ui.md) to identify false positives and adjust settings.

### Configuration Settings

| Setting                               | Default        | Context   | Multiple | Description                                                                                                                                                                               |
| ------------------------------------- | -------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`          | multisite | no       | **Enable ModSecurity:** Turn on ModSecurity Web Application Firewall protection.                                                                                                          |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | no       | **Use Core Rule Set:** Enable the OWASP Core Rule Set for ModSecurity.                                                                                                                    |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | no       | **CRS Version:** The version of the OWASP Core Rule Set to use. Options: `3`, `4`, or `nightly`.                                                                                          |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | no       | **Rule Engine:** Control whether rules are enforced. Options: `On`, `DetectionOnly`, or `Off`.                                                                                            |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | no       | **Audit Engine:** Control how audit logging works. Options: `On`, `Off`, or `RelevantOnly`.                                                                                               |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | no       | **Audit Log Parts:** Which parts of requests/responses to include in audit logs.                                                                                                          |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | no       | **Request Body Limit (No Files):** Maximum size for request bodies without file uploads. Accepts plain bytes or human‑readable suffix (`k`, `m`, `g`), e.g. `131072`, `256k`, `1m`, `2g`. |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | no       | **Enable CRS Plugins:** Enable additional plugin rule sets for the Core Rule Set.                                                                                                         |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | no       | **CRS Plugins List:** Space-separated list of plugins to download and install (`plugin-name[/tag]` or URL).                                                                               |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | no       | **Global CRS:** When enabled, applies CRS rules globally at the HTTP level rather than per server.                                                                                        |

!!! warning "ModSecurity and the OWASP Core Rule Set"
    **We strongly recommend keeping both ModSecurity and the OWASP Core Rule Set (CRS) enabled** to provide robust protection against common web vulnerabilities. While occasional false positives may occur, they can be resolved with some effort by fine-tuning rules or using predefined exclusions.

    The CRS team actively maintains a list of exclusions for popular applications such as WordPress, Nextcloud, Drupal, and Cpanel, making it easier to integrate without impacting functionality. The security benefits far outweigh the minimal configuration effort required to address false positives.

### Available CRS Versions

Select a CRS version to best match your security needs:

- **`3`**: Stable [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8).
- **`4`**: Stable [v4.23.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.23.0) (**default**).
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

### Custom Configurations {#custom-configurations}

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

!!! note "Human-readable size values"
    For size settings like `MODSECURITY_REQ_BODY_NO_FILES_LIMIT`, the suffixes `k`, `m`, and `g` (case-insensitive) are supported and represent kibibytes, mebibytes, and gibibytes (multiples of 1024). Examples: `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.

## Monitoring <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

BunkerWeb monitoring pro system. This plugin is a prerequisite for some other plugins.

| Setting                        | Default | Context | Multiple | Description                                                                 |
| ------------------------------ | ------- | ------- | -------- | --------------------------------------------------------------------------- |
| `USE_MONITORING`               | `yes`   | global  | no       | Enable monitoring of BunkerWeb.                                             |
| `MONITORING_METRICS_DICT_SIZE` | `10M`   | global  | no       | Size of the dict to store monitoring metrics.                               |
| `MONITORING_IGNORE_URLS`       |         | global  | no       | List of URLs to ignore when monitoring separated with spaces (e.g. /health) |

## Mutual TLS

STREAM support :white_check_mark:

The Mutual TLS (mTLS) plugin protects sensitive applications by requiring visiting clients to present certificates issued by authorities you trust. With it enabled, BunkerWeb authenticates callers before their requests reach your services, keeping internal tools and partner integrations locked down.

BunkerWeb evaluates each handshake against the CA bundle and policy you configure. Clients that fail the verification rules are stopped, while compliant connections can optionally pass certificate details to upstream applications for deeper authorization decisions.

**How it works:**

1. The plugin watches HTTPS handshakes on the selected site.
2. During the TLS exchange, BunkerWeb inspects the client certificate and verifies its chain against your configured trust store.
3. The verification mode decides whether unauthenticated clients are rejected, allowed with warnings, or accepted for diagnostics.
4. (Optional) BunkerWeb exposes the verification outcome through `X-SSL-Client-*` headers so your application layer can apply finer-grained logic.

!!! success "Key benefits"

      1. **Strong perimeter control:** Allow only authenticated machines and users onto sensitive routes.
      2. **Flexible trust policies:** Combine strict and optional verification modes to match onboarding workflows.
      3. **Visibility for apps:** Forward certificate fingerprints and identities to downstream services for auditing.
      4. **Layered security:** Pair mTLS with other BunkerWeb plugins (rate limiting, IP filtering) for defense in depth.

### How to Use

Follow these steps to deploy mutual TLS with confidence:

1. **Enable the feature:** Set `USE_MTLS` to `yes` on the sites that require certificate authentication.
2. **Provide the CA bundle:** Store the trusted issuers in a PEM file and point `MTLS_CA_CERTIFICATE` to its absolute path.
3. **Select the verification mode:** Pick `on` for mandatory certificates, `optional` to allow fallbacks, or `optional_no_ca` for temporary diagnostics.
4. **Tune chain depth:** Adjust `MTLS_VERIFY_DEPTH` if your organization issues intermediate certificates beyond the default depth.
5. **Forward results (optional):** Keep `MTLS_FORWARD_CLIENT_HEADERS` at `yes` when upstream services should inspect the presented certificate.
6. **Maintain revocation data:** If you publish a CRL, set `MTLS_CRL` so BunkerWeb can deny revoked certificates.

### Configuration Settings

| Setting                       | Default | Context   | Multiple | Description                                                                                                                                            |
| ----------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_MTLS`                    | `no`    | multisite | no       | **Use mutual TLS:** Enable client certificate authentication for the current site.                                                                     |
| `MTLS_CA_CERTIFICATE`         |         | multisite | no       | **Client CA bundle:** Absolute path to the trusted client CA bundle (PEM). Required when `MTLS_VERIFY_CLIENT` is `on` or `optional`; must be readable. |
| `MTLS_VERIFY_CLIENT`          | `on`    | multisite | no       | **Verify client mode:** Choose whether certificates are required (`on`), optional (`optional`), or accepted without CA validation (`optional_no_ca`).  |
| `MTLS_VERIFY_DEPTH`           | `2`     | multisite | no       | **Verify depth:** Maximum certificate chain depth accepted for client certificates.                                                                    |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`   | multisite | no       | **Forward client headers:** Propagate verification results (`X-SSL-Client-*` headers with status, DN, issuer, serial, fingerprint, validity window).   |
| `MTLS_CRL`                    |         | multisite | no       | **Client CRL path:** Optional path to a PEM-encoded certificate revocation list. Applied only when the CA bundle is successfully loaded.               |

!!! tip "Keep certificates up to date"
    Store CA bundles and revocation lists in a mounted volume that the Scheduler can read so that restarts pick up the latest trust anchors.

!!! warning "Provide the CA bundle for strict modes"
    When `MTLS_VERIFY_CLIENT` is `on` or `optional`, the CA file must exist at runtime. If it is missing, BunkerWeb skips the mTLS directives so the service does not boot with an invalid path. Use `optional_no_ca` only for diagnostics because it weakens client authentication.

!!! info "Trusted certificate vs. verification"
    BunkerWeb reuses the same CA bundle for client verification and for building trust chains, keeping revocation checks and handshake validation consistent.

### Example Configurations

=== "Strict access control"

    Require valid client certificates issued by your private CA and forward verification information to the backend:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Optional client authentication"

    Allow anonymous users but forward certificate details when a client presents one:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnostics without a CA"

    Allow connections to complete even if a certificate cannot be chained to a trusted CA bundle. Useful only for troubleshooting:

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

## OpenAPI Validator <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

Validates incoming HTTP requests against an OpenAPI / Swagger specification.

| Setting                      | Default                             | Context   | Multiple | Description                                                                                     |
| ---------------------------- | ----------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------- |
| `USE_OPENAPI_VALIDATOR`      | `no`                                | multisite | no       | Enable OpenAPI route validation for this site.                                                  |
| `OPENAPI_SPEC`               |                                     | multisite | no       | Absolute path or HTTP(S) URL to the OpenAPI (swagger) document in JSON/YAML format.             |
| `OPENAPI_BASE_PATH`          |                                     | multisite | no       | Optional base path prefix to prepend to every path in the spec (overrides servers[*].url path). |
| `OPENAPI_ALLOW_UNSPECIFIED`  | `no`                                | multisite | no       | Allow requests to paths not listed in the specification (otherwise they are denied).            |
| `OPENAPI_ALLOW_INSECURE_URL` | `no`                                | multisite | no       | Allow fetching the OpenAPI spec over plain HTTP (not recommended).                              |
| `OPENAPI_IGNORE_URLS`        | `^/docs$ ^/redoc$ ^/openapi\.json$` | multisite | no       | List of URL regexes to bypass OpenAPI validation (space separated).                             |
| `OPENAPI_MAX_SPEC_SIZE`      | `2M`                                | global    | no       | Maximum allowed size of the OpenAPI document (accepts suffix k/M/G).                            |
| `OPENAPI_VALIDATE_PARAMS`    | `yes`                               | multisite | no       | Validate query, header, cookie, and path parameters against the OpenAPI specification.          |

## OpenID Connect <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM support :x:

OpenID Connect authentication plugin providing SSO capabilities with identity providers.

| Setting                                   | Default                | Context   | Multiple | Description                                                                                                                                             |
| ----------------------------------------- | ---------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_OPENIDC`                             | `no`                   | multisite | no       | Enable or disable OpenID Connect authentication.                                                                                                        |
| `OPENIDC_DISCOVERY`                       |                        | multisite | no       | OpenID Connect discovery URL (e.g. https://idp.example.com/.well-known/openid-configuration).                                                           |
| `OPENIDC_CLIENT_ID`                       |                        | multisite | no       | OAuth 2.0 client identifier registered with the IdP.                                                                                                    |
| `OPENIDC_CLIENT_SECRET`                   |                        | multisite | no       | OAuth 2.0 client secret registered with the IdP.                                                                                                        |
| `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD`      | `basic`                | multisite | no       | Token endpoint auth method: basic (recommended, HTTP Basic), post (POST body), secret_jwt (JWT with client secret), private_key_jwt (JWT with RSA key). |
| `OPENIDC_CLIENT_RSA_PRIVATE_KEY`          |                        | multisite | no       | PEM-encoded RSA private key for private_key_jwt authentication.                                                                                         |
| `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`       |                        | multisite | no       | Optional key ID (kid) for private_key_jwt authentication.                                                                                               |
| `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN` |                        | multisite | no       | JWT assertion lifetime in seconds (empty to use library default).                                                                                       |
| `OPENIDC_REDIRECT_URI`                    | `/callback`            | multisite | no       | URI path where the IdP redirects after authentication.                                                                                                  |
| `OPENIDC_SCOPE`                           | `openid email profile` | multisite | no       | Space-separated list of OAuth 2.0 scopes to request.                                                                                                    |
| `OPENIDC_AUTHORIZATION_PARAMS`            |                        | multisite | no       | Additional authorization params as comma-separated key=value pairs (e.g. audience=api,resource=xyz). URL-encode values if needed.                       |
| `OPENIDC_USE_NONCE`                       | `yes`                  | multisite | no       | Use nonce in authentication requests to prevent replay attacks.                                                                                         |
| `OPENIDC_USE_PKCE`                        | `no`                   | multisite | no       | Use PKCE (Proof Key for Code Exchange) for authorization code flow.                                                                                     |
| `OPENIDC_FORCE_REAUTHORIZE`               | `no`                   | multisite | no       | Force re-authorization on every request (not recommended for production).                                                                               |
| `OPENIDC_REFRESH_SESSION_INTERVAL`        |                        | multisite | no       | Interval in seconds to silently re-authenticate (empty to disable).                                                                                     |
| `OPENIDC_IAT_SLACK`                       | `120`                  | multisite | no       | Allowed clock skew in seconds for token validation.                                                                                                     |
| `OPENIDC_ACCESS_TOKEN_EXPIRES_IN`         | `3600`                 | multisite | no       | Default access token lifetime (seconds) if not provided by IdP.                                                                                         |
| `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY`    | `yes`                  | multisite | no       | Automatically renew access token using refresh token when expired.                                                                                      |
| `OPENIDC_ACCEPT_UNSUPPORTED_ALG`          | `no`                   | multisite | no       | Accept tokens signed with unsupported algorithms (not recommended).                                                                                     |
| `OPENIDC_LOGOUT_PATH`                     | `/logout`              | multisite | no       | URI path for logout requests.                                                                                                                           |
| `OPENIDC_REVOKE_TOKENS_ON_LOGOUT`         | `no`                   | multisite | no       | Revoke tokens at the IdP when logging out.                                                                                                              |
| `OPENIDC_REDIRECT_AFTER_LOGOUT_URI`       |                        | multisite | no       | URI to redirect after logout (leave empty for IdP default).                                                                                             |
| `OPENIDC_POST_LOGOUT_REDIRECT_URI`        |                        | multisite | no       | URI to redirect after IdP logout is complete.                                                                                                           |
| `OPENIDC_TIMEOUT_CONNECT`                 | `10000`                | multisite | no       | Connection timeout in milliseconds for IdP requests.                                                                                                    |
| `OPENIDC_TIMEOUT_SEND`                    | `10000`                | multisite | no       | Send timeout in milliseconds for IdP requests.                                                                                                          |
| `OPENIDC_TIMEOUT_READ`                    | `10000`                | multisite | no       | Read timeout in milliseconds for IdP requests.                                                                                                          |
| `OPENIDC_SSL_VERIFY`                      | `yes`                  | multisite | no       | Verify SSL certificates when communicating with the IdP.                                                                                                |
| `OPENIDC_KEEPALIVE`                       | `yes`                  | multisite | no       | Enable HTTP keepalive for connections to the IdP.                                                                                                       |
| `OPENIDC_HTTP_PROXY`                      |                        | multisite | no       | HTTP proxy URL for IdP connections (e.g. http://proxy:8080).                                                                                            |
| `OPENIDC_HTTPS_PROXY`                     |                        | multisite | no       | HTTPS proxy URL for IdP connections (e.g. http://proxy:8080).                                                                                           |
| `OPENIDC_USER_HEADER`                     | `X-User`               | multisite | no       | Header to pass user info to upstream (empty to disable).                                                                                                |
| `OPENIDC_USER_HEADER_CLAIM`               | `sub`                  | multisite | no       | ID token claim to use for the user header (e.g. sub, email, preferred_username).                                                                        |
| `OPENIDC_DISPLAY_CLAIM`                   | `preferred_username`   | multisite | no       | Claim to use for display in logs and metrics (e.g. preferred_username, name, email). Falls back to User Header Claim if not found.                      |
| `OPENIDC_DISCOVERY_DICT_SIZE`             | `1m`                   | global    | no       | Size of the shared dictionary to cache discovery data.                                                                                                  |
| `OPENIDC_JWKS_DICT_SIZE`                  | `1m`                   | global    | no       | Size of the shared dictionary to cache JWKS data.                                                                                                       |

## PHP

STREAM support :x:

The PHP plugin provides seamless integration with PHP-FPM for BunkerWeb, enabling dynamic PHP processing for your websites. This feature supports both local PHP-FPM instances running on the same machine and remote PHP-FPM servers, giving you flexibility in how you configure your PHP environment.

**How it works:**

1. When a client requests a PHP file from your website, BunkerWeb routes the request to the configured PHP-FPM instance.
2. For local PHP-FPM, BunkerWeb communicates with the PHP interpreter through a Unix socket file.
3. For remote PHP-FPM, BunkerWeb forwards requests to the specified host and port using the FastCGI protocol.
4. PHP-FPM processes the script and returns the generated content to BunkerWeb, which then delivers it to the client.
5. URL rewriting is automatically configured to support common PHP frameworks and applications that use "pretty URLs".

### How to Use

Follow these steps to configure and use the PHP feature:

1. **Choose your PHP-FPM setup:** Decide whether you'll use a local or remote PHP-FPM instance.
2. **Configure the connection:** For local PHP, specify the socket path; for remote PHP, provide the hostname and port.
3. **Set the document root:** Configure the root folder that contains your PHP files using the appropriate path setting.
4. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb automatically routes PHP requests to your PHP-FPM instance.

### Configuration Settings

| Setting           | Default | Context   | Multiple | Description                                                                                          |
| ----------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `REMOTE_PHP`      |         | multisite | no       | **Remote PHP Host:** Hostname of the remote PHP-FPM instance. Leave empty to use local PHP.          |
| `REMOTE_PHP_PATH` |         | multisite | no       | **Remote Path:** Root folder containing files in the remote PHP-FPM instance.                        |
| `REMOTE_PHP_PORT` | `9000`  | multisite | no       | **Remote Port:** Port of the remote PHP-FPM instance.                                                |
| `LOCAL_PHP`       |         | multisite | no       | **Local PHP Socket:** Path to the PHP-FPM socket file. Leave empty to use a remote PHP-FPM instance. |
| `LOCAL_PHP_PATH`  |         | multisite | no       | **Local Path:** Root folder containing files in the local PHP-FPM instance.                          |

!!! tip "Local vs. Remote PHP-FPM"
    Choose the setup that best fits your infrastructure:

    - **Local PHP-FPM** offers better performance due to socket-based communication and is ideal when PHP runs on the same machine as BunkerWeb.
    - **Remote PHP-FPM** provides more flexibility and scalability by allowing PHP processing to occur on separate servers.

!!! warning "Path Configuration"
    The `REMOTE_PHP_PATH` or `LOCAL_PHP_PATH` must match the actual filesystem path where your PHP files are stored; otherwise, a "File not found" error will occur.

!!! info "URL Rewriting"
    The PHP plugin automatically configures URL rewriting to support modern PHP applications. Requests for non-existent files will be directed to `index.php` with the original request URI available as a query parameter.

### Example Configurations

=== "Local PHP-FPM Configuration"

    Configuration for using a local PHP-FPM instance:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "Remote PHP-FPM Configuration"

    Configuration for using a remote PHP-FPM instance:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Custom Port Configuration"

    Configuration for using PHP-FPM on a non-standard port:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress Configuration"

    Configuration optimized for WordPress:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```

## Pro

STREAM support :x:

The Pro plugin bundles advanced features and enhancements for enterprise deployments of BunkerWeb. It unlocks additional capabilities, premium plugins, and extended functionality that complement the core BunkerWeb platform. It delivers enhanced security, performance, and management options for enterprise-grade deployments.

**How it works:**

1. With a valid Pro license key, BunkerWeb connects to the Pro API server to validate your subscription.
2. Once authenticated, the plugin automatically downloads and installs Pro-exclusive plugins and extensions.
3. Your Pro status is periodically verified to ensure continued access to premium features.
4. Premium plugins are seamlessly integrated with your existing BunkerWeb configuration.
5. All Pro features work harmoniously with the open-source core, enhancing rather than replacing functionality.

!!! success "Key benefits"

      1. **Premium Extensions:** Access to exclusive plugins and features not available in the community edition.
      2. **Enhanced Performance:** Optimized configurations and advanced caching mechanisms.
      3. **Enterprise Support:** Priority assistance and dedicated support channels.
      4. **Seamless Integration:** Pro features work alongside community features without configuration conflicts.
      5. **Automatic Updates:** Premium plugins are automatically downloaded and kept current.

### How to Use

Follow these steps to configure and use the Pro features:

1. **Obtain a license key:** Purchase a Pro license from the [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc).
2. **Configure your license key:** Use the `PRO_LICENSE_KEY` setting to configure your license.
3. **Let BunkerWeb handle the rest:** Once configured with a valid license, Pro plugins are automatically downloaded and activated.
4. **Monitor your Pro status:** Check the health indicators in the [web UI](web-ui.md) to confirm your Pro subscription status.

### Configuration Settings

| Setting           | Default | Context | Multiple | Description                                                             |
| ----------------- | ------- | ------- | -------- | ----------------------------------------------------------------------- |
| `PRO_LICENSE_KEY` |         | global  | no       | **Pro License Key:** Your BunkerWeb Pro license key for authentication. |

!!! tip "License Management"
    Your Pro license is tied to your specific deployment environment. If you need to transfer your license or have questions about your subscription, please contact support through the [BunkerWeb Panel](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Pro Features"
    The specific Pro features available may evolve over time as new capabilities are added. The Pro plugin automatically handles the installation and configuration of all available features.

!!! warning "Network Requirements"
    The Pro plugin requires outbound internet access to connect to the BunkerWeb API for license verification and to download premium plugins. Ensure your firewall allows connections to `api.bunkerweb.io` on port 443 (HTTPS).

### Frequently Asked Questions

**Q: What happens if my Pro license expires?**

A: If your Pro license expires, access to premium features and plugins will be disabled. However, your BunkerWeb installation will continue to operate with all community edition features intact. To regain access to Pro features, simply renew your license.

**Q: Will Pro features disrupt my existing configuration?**

A: No, Pro features are designed to integrate seamlessly with your current BunkerWeb setup. They enhance functionality without altering or interfering with your existing configuration, ensuring a smooth and reliable experience.

**Q: Can I try Pro features before committing to a purchase?**

A: Absolutely! BunkerWeb offers two Pro plans to suit your needs:

- **BunkerWeb PRO Standard:** Full access to Pro features without technical support.
- **BunkerWeb PRO Enterprise:** Full access to Pro features with dedicated technical support.

You can explore Pro features with a free 1-month trial by using the promo code `freetrial`. Visit the [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) to activate your trial and learn more about flexible pricing options based on the number of services protected by BunkerWeb PRO.

## Prometheus exporter <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


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

The Real IP plugin ensures that BunkerWeb correctly identifies the client’s IP address even when behind proxies. This is essential for applying security rules, rate limiting, and logging properly; without it, all requests would appear to come from your proxy's IP rather than the client's actual IP.

**How it works:**

1. When enabled, BunkerWeb examines incoming requests for specific headers (like [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)) that contain the client's original IP address.
2. BunkerWeb checks if the incoming IP is in your trusted proxy list (`REAL_IP_FROM`), ensuring that only legitimate proxies can pass client IPs.
3. The original client IP is extracted from the specified header (`REAL_IP_HEADER`) and used for all security evaluations and logging.
4. For recursive IP chains, BunkerWeb can trace through multiple proxy hops to determine the originating client IP.
5. Additionally, [PROXY protocol](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) support can be enabled to receive client IPs directly from compatible proxies such as [HAProxy](https://www.haproxy.org/).
6. Trusted proxy IP lists can be automatically downloaded and updated from external sources via URLs.

### How to Use

Follow these steps to configure and use the Real IP feature:

1. **Enable the feature:** Set the `USE_REAL_IP` setting to `yes` to enable real IP detection.
2. **Define trusted proxies:** List the IP addresses or networks of your trusted proxies using the `REAL_IP_FROM` setting.
3. **Specify the header:** Configure which header contains the real IP using the `REAL_IP_HEADER` setting.
4. **Configure recursion:** Decide whether to trace IP chains recursively with the `REAL_IP_RECURSIVE` setting.
5. **Optional URL sources:** Set up automatic downloads of trusted proxy lists with `REAL_IP_FROM_URLS`.
6. **PROXY protocol:** For direct proxy communication, enable with `USE_PROXY_PROTOCOL` if your upstream supports it.

!!! danger "PROXY Protocol Warning"
    Enabling `USE_PROXY_PROTOCOL` without properly configuring your upstream proxy to send PROXY protocol headers will **break your application**. Only enable this setting if you are certain that your upstream proxy is properly configured to send PROXY protocol information. If your proxy is not sending PROXY protocol headers, all connections to BunkerWeb will fail with protocol errors.

### Configuration Settings

| Setting              | Default                                   | Context   | Multiple | Description                                                                                                           |
| -------------------- | ----------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | no       | **Enable Real IP:** Set to `yes` to enable retrieving client's real IP from headers or PROXY protocol.                |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | no       | **Trusted Proxies:** List of trusted IP addresses or networks where proxied requests come from, separated by spaces.  |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | no       | **Real IP Header:** HTTP header containing the real IP or special value `proxy_protocol` for PROXY protocol.          |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | no       | **Recursive Search:** When set to `yes`, performs a recursive search in header containing multiple IP addresses.      |
| `REAL_IP_FROM_URLS`  |                                           | multisite | no       | **IP List URLs:** URLs containing trusted proxy IPs/networks to download, separated by spaces. Supports file:// URLs. |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | no       | **PROXY Protocol:** Set to `yes` to enable PROXY protocol support for direct proxy-to-BunkerWeb communication.        |

!!! tip "Cloud Provider Networks"
    If you're using a cloud provider like AWS, GCP, or Azure, consider adding their load balancer IP ranges to your `REAL_IP_FROM` setting to ensure proper client IP identification.

!!! danger "Security Considerations"
    Only include trusted proxy IPs in your configuration. Adding untrusted sources could allow IP spoofing attacks, where malicious actors could forge the client IP by manipulating headers.

!!! info "Multiple IP Addresses"
    When `REAL_IP_RECURSIVE` is enabled and a header contains multiple IPs (e.g., `X-Forwarded-For: client, proxy1, proxy2`), BunkerWeb will identify the leftmost IP not in your trusted proxy list as the client IP.

### Example Configurations

=== "Basic Configuration"

    A simple configuration for a site behind a reverse proxy:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Cloud Load Balancer"

    Configuration for a site behind a cloud load balancer:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "PROXY Protocol"

    Configuration using PROXY protocol with a compatible load balancer:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "Multiple Proxy Sources with URLs"

    Advanced configuration with automatically updated proxy IP lists:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "CDN Configuration"

    Configuration for a website behind a CDN:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Example for Cloudflare
    REAL_IP_RECURSIVE: "no"  # Not needed with single IP headers
    ```

=== "Behind Cloudflare"

    Configuration for a website behind Cloudflare:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # We only trust Cloudflare IPs
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # Download Cloudflare IPs automatically
    REAL_IP_HEADER: "CF-Connecting-IP"  # Cloudflare header for client IP
    REAL_IP_RECURSIVE: "yes"
    ```

## Redirect

STREAM support :x:

The Redirect plugin provides simple and efficient HTTP redirection capabilities for your BunkerWeb-protected websites. This feature enables you to easily redirect visitors from one URL to another, supporting both full-domain redirects, specific path redirects and path-preserving redirections.

**How it works:**

1. When a visitor accesses your website, BunkerWeb verifies whether a redirection is configured.
2. If enabled, BunkerWeb redirects the visitor to the specified destination URL.
3. You can configure whether to preserve the original request path (automatically appending it to the destination URL) or redirect to the exact destination URL.
4. The HTTP status code used for the redirection can be customized between permanent (301) and temporary (302) redirects.
5. This functionality is ideal for domain migrations, establishing canonical domains, or redirecting deprecated URLs.

### How to Use

Follow these steps to configure and use the Redirect feature:

1. **Set the source path:** Configure the path to redirect from using the `REDIRECT_FROM` setting (e.g. `/`, `/old-page`).
2. **Set the destination URL:** Configure the target URL where visitors should be redirected using the `REDIRECT_TO` setting.
3. **Choose redirection type:** Decide whether to preserve the original request path with the `REDIRECT_TO_REQUEST_URI` setting.
4. **Select status code:** Set the appropriate HTTP status code with the `REDIRECT_TO_STATUS_CODE` setting to indicate permanent or temporary redirection.
5. **Let BunkerWeb handle the rest:** Once configured, all requests to the site will be automatically redirected based on your settings.

### Configuration Settings

| Setting                   | Default | Context   | Multiple | Description                                                                                                       |
| ------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`     | multisite | yes      | **Path to redirect from:** The path that will be redirected.                                                      |
| `REDIRECT_TO`             |         | multisite | yes      | **Destination URL:** The target URL where visitors will be redirected. Leave empty to disable redirection.        |
| `REDIRECT_TO_REQUEST_URI` | `no`    | multisite | yes      | **Preserve Path:** When set to `yes`, appends the original request URI to the destination URL.                    |
| `REDIRECT_TO_STATUS_CODE` | `301`   | multisite | yes      | **HTTP Status Code:** The HTTP status code to use for redirection. Options: `301`, `302`, `303`, `307`, or `308`. |

!!! tip "Choosing the Right Status Code"
    - **`301` (Moved Permanently):** The resource has permanently moved. Browsers cache this redirect. May change POST to GET. Ideal for domain migrations and canonical URLs.
    - **`302` (Found):** Temporary redirect. May change POST to GET. Use when the redirect is temporary or you may reuse the original URL.
    - **`303` (See Other):** Always redirects using GET method regardless of the original request method. Useful after form submissions to prevent resubmission on refresh.
    - **`307` (Temporary Redirect):** Temporary redirect that preserves the HTTP method (POST stays POST). Ideal for API redirects or form handling.
    - **`308` (Permanent Redirect):** Permanent redirect that preserves the HTTP method. Use for permanent API endpoint migrations where method preservation is critical.

!!! info "Path Preservation"
    When `REDIRECT_TO_REQUEST_URI` is set to `yes`, BunkerWeb preserves the original request path. For example, if a user visits `https://old-domain.com/blog/post-1` and you've set up a redirect to `https://new-domain.com`, they'll be redirected to `https://new-domain.com/blog/post-1`.

### Example Configurations

=== "Multiple Paths Redirect"

    A configuration that redirects multiple paths to different destinations:

    ```yaml
    # Redirect /blog to a new blog domain
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    # Redirect /shop to another domain
    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    # Redirect the rest of the site
    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Simple Domain Redirect"

    A configuration that redirects all visitors to a new domain:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Path-Preserving Redirect"

    A configuration that redirects visitors to a new domain while preserving the requested path:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Temporary Redirect"

    A configuration for a temporary redirect to a maintenance site:

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Subdomain Consolidation"

    A configuration to redirect a subdomain to a specific path on the main domain:

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "API Endpoint Migration"

    A configuration for permanently redirecting an API endpoint while preserving the HTTP method:

    ```yaml
    REDIRECT_FROM: "/api/v1/"
    REDIRECT_TO: "https://api.example.com/v2/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "308"
    ```

=== "Post-Form Submission Redirect"

    A configuration to redirect after a form submission using GET method:

    ```yaml
    REDIRECT_TO: "https://example.com/thank-you"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "303"
    ```

## Redis

STREAM support :white_check_mark:

The Redis plugin integrates [Redis](https://redis.io/) or [Valkey](https://valkey.io/) into BunkerWeb for caching and fast data retrieval. This feature is essential for deploying BunkerWeb in high-availability environments where session data, metrics, and other shared information must be accessible across multiple nodes.

**How it works:**

1. When enabled, BunkerWeb establishes a connection to your configured Redis or Valkey server.
2. Critical data such as session information, metrics, and security-related data are stored in Redis/Valkey.
3. Multiple BunkerWeb instances can share this data, enabling seamless clustering and load balancing.
4. The plugin supports various Redis/Valkey deployment options, including standalone servers, password authentication, SSL/TLS encryption, and Redis Sentinel for high availability.
5. Automatic reconnection and configurable timeouts ensure robustness in production environments.

### How to Use

Follow these steps to configure and use the Redis plugin:

1. **Enable the feature:** Set the `USE_REDIS` setting to `yes` to enable Redis/Valkey integration.
2. **Configure connection details:** Specify your Redis/Valkey server's hostname/IP address and port.
3. **Set security options:** Configure authentication credentials if your Redis/Valkey server requires them.
4. **Configure advanced options:** Set the database selection, SSL options, and timeouts as needed.
5. **For high availability,** configure Sentinel settings if you're using Redis Sentinel.

### Configuration Settings

| Setting                   | Default    | Context | Multiple | Description                                                                                      |
| ------------------------- | ---------- | ------- | -------- | ------------------------------------------------------------------------------------------------ |
| `USE_REDIS`               | `no`       | global  | no       | **Enable Redis:** Set to `yes` to enable Redis/Valkey integration for cluster mode.              |
| `REDIS_HOST`              |            | global  | no       | **Redis/Valkey Server:** IP address or hostname of the Redis/Valkey server.                      |
| `REDIS_PORT`              | `6379`     | global  | no       | **Redis/Valkey Port:** Port number of the Redis/Valkey server.                                   |
| `REDIS_DATABASE`          | `0`        | global  | no       | **Redis/Valkey Database:** Database number to use on the Redis/Valkey server (0-15).             |
| `REDIS_SSL`               | `no`       | global  | no       | **Redis/Valkey SSL:** Set to `yes` to enable SSL/TLS encryption for the Redis/Valkey connection. |
| `REDIS_SSL_VERIFY`        | `yes`      | global  | no       | **Redis/Valkey SSL Verify:** Set to `yes` to verify the Redis/Valkey server's SSL certificate.   |
| `REDIS_TIMEOUT`           | `5`        | global  | no       | **Redis/Valkey Timeout:** Connection timeout in seconds for Redis/Valkey operations.             |
| `REDIS_USERNAME`          |            | global  | no       | **Redis/Valkey Username:** Username for Redis/Valkey authentication (Redis 6.0+).                |
| `REDIS_PASSWORD`          |            | global  | no       | **Redis/Valkey Password:** Password for Redis/Valkey authentication.                             |
| `REDIS_SENTINEL_HOSTS`    |            | global  | no       | **Sentinel Hosts:** Space-separated list of Redis Sentinel hosts (hostname:port).                |
| `REDIS_SENTINEL_USERNAME` |            | global  | no       | **Sentinel Username:** Username for Redis Sentinel authentication.                               |
| `REDIS_SENTINEL_PASSWORD` |            | global  | no       | **Sentinel Password:** Password for Redis Sentinel authentication.                               |
| `REDIS_SENTINEL_MASTER`   | `mymaster` | global  | no       | **Sentinel Master:** Name of the master in Redis Sentinel configuration.                         |
| `REDIS_KEEPALIVE_IDLE`    | `300`      | global  | no       | **Keepalive Idle:** Time (in seconds) between TCP keepalive probes for idle connections.         |
| `REDIS_KEEPALIVE_POOL`    | `3`        | global  | no       | **Keepalive Pool:** Maximum number of Redis/Valkey connections kept in the pool.                 |

!!! tip "High Availability with Redis Sentinel"
    For production environments requiring high availability, configure Redis Sentinel settings. This provides automatic failover capabilities if the primary Redis server becomes unavailable.

!!! warning "Security Considerations"
    When using Redis in production:

    - Always set strong passwords for both Redis and Sentinel authentication
    - Consider enabling SSL/TLS encryption for Redis connections
    - Ensure your Redis server is not exposed to the public internet
    - Restrict access to the Redis port using firewalls or network segmentation

!!! info "Cluster Requirements"
    When deploying BunkerWeb in a cluster:

    - All BunkerWeb instances should connect to the same Redis or Valkey server or Sentinel cluster
    - Configure the same database number across all instances
    - Ensure network connectivity between all BunkerWeb instances and Redis/Valkey servers

### Example Configurations

=== "Basic Configuration"

    A simple configuration for connecting to a Redis or Valkey server on the local machine:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Secure Configuration"

    Configuration with password authentication and SSL enabled:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Redis Sentinel Configuration"

    Configuration for high availability using Redis Sentinel:

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Advanced Tuning"

    Configuration with advanced connection parameters for performance optimization:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3"
    REDIS_KEEPALIVE_IDLE: "60"
    REDIS_KEEPALIVE_POOL: "5"
    ```

### Redis Best Practices

When using Redis or Valkey with BunkerWeb, consider these best practices to ensure optimal performance, security, and reliability:

#### Memory Management
- **Monitor memory usage:** Configure Redis with appropriate `maxmemory` settings to prevent out-of-memory errors
- **Set an eviction policy:** Use `maxmemory-policy` (e.g., `volatile-lru` or `allkeys-lru`) appropriate for your use case
- **Avoid large keys:** Ensure individual Redis keys are kept to a reasonable size to prevent performance degradation

#### Data Persistence
- **Enable RDB snapshots:** Configure periodic snapshots for data persistence without significant performance impact
- **Consider AOF:** For critical data, enable AOF (Append-Only File) persistence with an appropriate fsync policy
- **Backup strategy:** Implement regular Redis backups as part of your disaster recovery plan

#### Performance Optimization
- **Connection pooling:** BunkerWeb already implements this, but ensure other applications follow this practice
- **Pipelining:** When possible, use pipelining for bulk operations to reduce network overhead
- **Avoid expensive operations:** Be cautious with commands like KEYS in production environments
- **Benchmark your workload:** Use redis-benchmark to test your specific workload patterns

### Further Resources

- [Redis Documentation](https://redis.io/documentation)
- [Redis Security Guide](https://redis.io/topics/security)
- [Redis High Availability](https://redis.io/topics/sentinel)
- [Redis Persistence](https://redis.io/topics/persistence)

## Reporting <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


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

The Reverse Proxy plugin provides seamless proxying capabilities for BunkerWeb, allowing you to route requests to backend servers and services. This feature enables BunkerWeb to act as a secure frontend for your applications while providing additional benefits such as SSL termination and security filtering.

**How it works:**

1. When a client sends a request to BunkerWeb, the Reverse Proxy plugin forwards the request to your configured backend server.
2. BunkerWeb adds security headers, applies WAF rules, and performs other security checks before passing requests to your application.
3. The backend server processes the request and returns a response to BunkerWeb.
4. BunkerWeb applies additional security measures to the response before sending it back to the client.
5. The plugin supports both HTTP and TCP/UDP stream proxying, enabling a wide range of applications, including WebSockets and other non-HTTP protocols.

### How to Use

Follow these steps to configure and use the Reverse Proxy feature:

1. **Enable the feature:** Set the `USE_REVERSE_PROXY` setting to `yes` to enable reverse proxy functionality.
2. **Configure your backend servers:** Specify the upstream servers using the `REVERSE_PROXY_HOST` setting.
3. **Adjust proxy settings:** Fine-tune behavior with optional settings for timeouts, buffer sizes, and other parameters.
4. **Configure protocol-specific options:** For WebSockets or special HTTP requirements, adjust the corresponding settings.
5. **Set up caching (optional):** Enable and configure proxy caching to improve performance for frequently accessed content.

### Configuration Guide

=== "Basic Configuration"

    **Core Settings**

    The essential configuration settings enable and control the basic functionality of the reverse proxy feature.

    !!! success "Benefits of Reverse Proxy"
        - **Security Enhancement:** All traffic passes through BunkerWeb's security layers before reaching your applications
        - **SSL Termination:** Manage SSL/TLS certificates centrally while backend services can use unencrypted connections
        - **Protocol Handling:** Support for HTTP, HTTPS, WebSockets, and other protocols
        - **Error Interception:** Customize error pages for a consistent user experience

    | Setting                           | Default | Context   | Multiple | Description                                                                              |
    | --------------------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`               | `no`    | multisite | no       | **Enable Reverse Proxy:** Set to `yes` to enable reverse proxy functionality.            |
    | `REVERSE_PROXY_HOST`              |         | multisite | yes      | **Backend Host:** Full URL of the proxied resource (proxy_pass).                         |
    | `REVERSE_PROXY_URL`               | `/`     | multisite | yes      | **Location URL:** Path that will be proxied to the backend server.                       |
    | `REVERSE_PROXY_BUFFERING`         | `yes`   | multisite | yes      | **Response Buffering:** Enable or disable buffering of responses from proxied resource.  |
    | `REVERSE_PROXY_REQUEST_BUFFERING` | `yes`   | multisite | yes      | **Request Buffering:** Enable or disable buffering of requests to the proxied resource.  |
    | `REVERSE_PROXY_KEEPALIVE`         | `no`    | multisite | yes      | **Keep-Alive:** Enable or disable keepalive connections with the proxied resource.       |
    | `REVERSE_PROXY_CUSTOM_HOST`       |         | multisite | no       | **Custom Host:** Override Host header sent to upstream server.                           |
    | `REVERSE_PROXY_INTERCEPT_ERRORS`  | `yes`   | multisite | no       | **Intercept Errors:** Whether to intercept and rewrite error responses from the backend. |

    !!! tip "Best Practices"
        - Always specify the full URL in `REVERSE_PROXY_HOST` including the protocol (http:// or https://)
        - Use `REVERSE_PROXY_INTERCEPT_ERRORS` to provide consistent error pages across all your services
        - When configuring multiple backends, use the numbered suffix format (e.g., `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

    !!! warning "Request buffering behavior"
        Disabling `REVERSE_PROXY_REQUEST_BUFFERING` only takes effect when ModSecurity is disabled, because request buffering is otherwise enforced.

=== "Connection Settings"

    **Connection and Timeout Configuration**

    These settings control connection behavior, buffering, and timeout values for the proxied connections.

    !!! success "Benefits"
        - **Optimized Performance:** Adjust buffer sizes and connection settings based on your application needs
        - **Resource Management:** Control memory usage through appropriate buffer configurations
        - **Reliability:** Configure appropriate timeouts to handle slow connections or backend issues

    | Setting                         | Default | Context   | Multiple | Description                                                                                             |
    | ------------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`   | multisite | yes      | **Connect Timeout:** Maximum time to establish a connection to the backend server.                      |
    | `REVERSE_PROXY_READ_TIMEOUT`    | `60s`   | multisite | yes      | **Read Timeout:** Maximum time between transmissions of two successive packets from the backend server. |
    | `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`   | multisite | yes      | **Send Timeout:** Maximum time between transmissions of two successive packets to the backend server.   |
    | `PROXY_BUFFERS`                 |         | multisite | no       | **Buffers:** Number and size of buffers for reading the response from the backend server.               |
    | `PROXY_BUFFER_SIZE`             |         | multisite | no       | **Buffer Size:** Size of the buffer for reading the first part of the response from the backend server. |
    | `PROXY_BUSY_BUFFERS_SIZE`       |         | multisite | no       | **Busy Buffers Size:** Size of buffers that can be busy sending response to the client.                 |

    !!! warning "Timeout Considerations"
        - Setting timeouts too low may cause legitimate but slow connections to be terminated
        - Setting timeouts too high may leave connections open unnecessarily, potentially exhausting resources
        - For WebSocket applications, increase the read and send timeouts significantly (300s or more recommended)

=== "SSL/TLS Configuration"

    **SSL/TLS Settings for Backend Connections**

    These settings control how BunkerWeb establishes secure connections to backend servers.

    !!! success "Benefits"
        - **End-to-End Encryption:** Maintain encrypted connections from client to backend
        - **Certificate Validation:** Control how backend server certificates are validated
        - **SNI Support:** Specify Server Name Indication for backends that host multiple sites

    | Setting                      | Default | Context   | Multiple | Description                                                                          |
    | ---------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------ |
    | `REVERSE_PROXY_SSL_SNI`      | `no`    | multisite | no       | **SSL SNI:** Enable or disable sending SNI (Server Name Indication) to upstream.     |
    | `REVERSE_PROXY_SSL_SNI_NAME` |         | multisite | no       | **SSL SNI Name:** Sets the SNI hostname to send to upstream when SSL SNI is enabled. |

    !!! info "SNI Explained"
        Server Name Indication (SNI) is a TLS extension that allows a client to specify the hostname it is attempting to connect to during the handshake process. This enables servers to present multiple certificates on the same IP address and port, allowing multiple secure (HTTPS) websites to be served from a single IP address without requiring all those sites to use the same certificate.

=== "Protocol Support"

    **Protocol-Specific Configuration**

    Configure special protocol handling, particularly for WebSockets and other non-HTTP protocols.

    !!! success "Benefits"
        - **Protocol Flexibility:** Support for WebSockets enables real-time applications
        - **Modern Web Applications:** Enable interactive features requiring bidirectional communication

    | Setting            | Default | Context   | Multiple | Description                                                       |
    | ------------------ | ------- | --------- | -------- | ----------------------------------------------------------------- |
    | `REVERSE_PROXY_WS` | `no`    | multisite | yes      | **WebSocket Support:** Enable WebSocket protocol on the resource. |

    !!! tip "WebSocket Configuration"
        - When enabling WebSockets with `REVERSE_PROXY_WS: "yes"`, consider increasing timeout values
        - WebSocket connections stay open longer than typical HTTP connections
        - For WebSocket applications, a recommended configuration is:
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Header Management"

    **HTTP Header Configuration**

    Control which headers are sent to backend servers and to clients, allowing you to add, modify, or preserve HTTP headers.

    !!! success "Benefits"
        - **Information Control:** Precisely manage what information is shared between clients and backends
        - **Security Enhancement:** Add security-related headers or remove headers that might leak sensitive information
        - **Integration Support:** Provide necessary headers for authentication and proper backend operation

    | Setting                                | Default   | Context   | Multiple | Description                                                                           |
    | -------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_HEADERS`                |           | multisite | yes      | **Custom Headers:** HTTP headers to send to backend separated with semicolons.        |
    | `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade` | multisite | yes      | **Hide Headers:** HTTP headers to hide from clients when received from the backend.   |
    | `REVERSE_PROXY_HEADERS_CLIENT`         |           | multisite | yes      | **Client Headers:** HTTP headers to send to client separated with semicolons.         |
    | `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`      | multisite | no       | **Underscores in Headers:** Enable or disable the `underscores_in_headers` directive. |

    !!! warning "Security Considerations"
        When using the reverse proxy feature, be cautious about what headers you forward to your backend applications. Certain headers might expose sensitive information about your infrastructure or bypass security controls.

    !!! example "Header Format Examples"
        Custom headers to backend servers:
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        Custom headers to clients:
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Authentication"

    **External Authentication Configuration**

    Integrate with external authentication systems to centralize authorization logic across your applications.

    !!! success "Benefits"
        - **Centralized Authentication:** Implement a single authentication point for multiple applications
        - **Consistent Security:** Apply uniform authentication policies across different services
        - **Enhanced Control:** Forward authentication details to backend applications via headers or variables

    | Setting                                 | Default | Context   | Multiple | Description                                                                 |
    | --------------------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `REVERSE_PROXY_AUTH_REQUEST`            |         | multisite | yes      | **Auth Request:** Enable authentication using an external provider.         |
    | `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |         | multisite | yes      | **Sign-in URL:** Redirect clients to sign-in URL when authentication fails. |
    | `REVERSE_PROXY_AUTH_REQUEST_SET`        |         | multisite | yes      | **Auth Request Set:** Variables to set from the authentication provider.    |

    !!! tip "Authentication Integration"
        - The auth request feature enables implementation of centralized authentication microservices
        - Your authentication service should return a 200 status code for successful authentication or 401/403 for failures
        - Use the auth_request_set directive to extract and forward information from the authentication service

=== "Advanced Configuration"

    **Additional Configuration Options**

    These settings provide further customization of the reverse proxy behavior for specialized scenarios.

    !!! success "Benefits"
        - **Customization:** Include additional configuration snippets for complex requirements
        - **Performance Optimization:** Fine-tune request handling for specific use cases
        - **Flexibility:** Adapt to unique application requirements with specialized configurations

    | Setting                           | Default | Context   | Multiple | Description                                                                  |
    | --------------------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |         | multisite | yes      | **Additional Configurations:** Include additional configs in location block. |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`   | multisite | yes      | **Pass Request Body:** Enable or disable passing the request body.           |

    !!! warning "Security Considerations"
        Be careful when including custom configuration snippets as they may override BunkerWeb's security settings or introduce vulnerabilities if not properly configured.

=== "Caching Configuration"

    **Response Caching Settings**

    Improve performance by caching responses from backend servers, reducing load and improving response times.

    !!! success "Benefits"
        - **Performance:** Reduce load on backend servers by serving cached content
        - **Reduced Latency:** Faster response times for frequently requested content
        - **Bandwidth Savings:** Minimize internal network traffic by caching responses
        - **Customization:** Configure exactly what, when, and how content is cached

    | Setting                      | Default                            | Context   | Multiple | Description                                                                    |
    | ---------------------------- | ---------------------------------- | --------- | -------- | ------------------------------------------------------------------------------ |
    | `USE_PROXY_CACHE`            | `no`                               | multisite | no       | **Enable Caching:** Set to `yes` to enable caching of backend responses.       |
    | `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | no       | **Cache Path Levels:** How to structure the cache directory hierarchy.         |
    | `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | no       | **Cache Zone Size:** Size of the shared memory zone used for cache metadata.   |
    | `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | no       | **Cache Path Parameters:** Additional parameters for the cache path.           |
    | `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | no       | **Cache Methods:** HTTP methods that can be cached.                            |
    | `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | no       | **Cache Min Uses:** Minimum number of requests before a response is cached.    |
    | `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | no       | **Cache Key:** The key used to uniquely identify a cached response.            |
    | `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | no       | **Cache Valid:** How long to cache specific response codes.                    |
    | `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | no       | **No Cache:** Conditions for not caching responses even if normally cacheable. |
    | `PROXY_CACHE_BYPASS`         | `0`                                | multisite | no       | **Cache Bypass:** Conditions under which to bypass the cache.                  |

    !!! tip "Caching Best Practices"
        - Cache only content that doesn't change frequently or isn't personalized
        - Use appropriate cache durations based on content type (static assets can be cached longer)
        - Configure `PROXY_NO_CACHE` to avoid caching sensitive or personalized content
        - Monitor cache hit rates and adjust settings accordingly

!!! danger "Docker Compose Users - NGINX Variables"
    When using Docker Compose with NGINX variables in your configurations, you must escape the dollar sign (`$`) by using double dollar signs (`$$`). This applies to all settings that contain NGINX variables like `$remote_addr`, `$proxy_add_x_forwarded_for`, etc.

    Without this escaping, Docker Compose will try to substitute these variables with environment variables, which typically don't exist, resulting in empty values in your NGINX configuration.

### Example Configurations

=== "Basic HTTP Proxy"

    A simple configuration for proxying HTTP requests to a backend application server:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "WebSocket Application"

    Configuration optimized for a WebSocket application with longer timeouts:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Multiple Locations"

    Configuration for routing different paths to different backend services:

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # API Backend
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Admin Backend
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Frontend App
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Caching Configuration"

    Configuration with proxy caching enabled for better performance:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Advanced Header Management"

    Configuration with custom header manipulation:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Custom headers to backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # Custom headers to client
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Authentication Integration"

    Configuration with external authentication:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Authentication configuration
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Auth service backend
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```

## Reverse scan

STREAM support :white_check_mark:

The Reverse Scan plugin robustly protects against proxy bypass attempts by scanning clients' ports to detect whether they are running proxy servers or other network services. This feature helps identify and block potential threats from clients that may be attempting to hide their true identity or origin, thereby enhancing your website's security posture.

**How it works:**

1. When a client connects to your server, BunkerWeb attempts to scan specific ports on the client's IP address.
2. The plugin checks if any common proxy ports (such as 80, 443, 8080, etc.) are open on the client side.
3. If open ports are detected, indicating that the client may be running a proxy server, the connection is denied.
4. This adds an extra layer of security against automated tools, bots, and malicious users attempting to mask their identity.

!!! success "Key benefits"

      1. **Enhanced Security:** Identifies clients potentially running proxy servers that could be used for malicious purposes.
      2. **Proxy Detection:** Helps detect and block clients attempting to hide their true identity.
      3. **Configurable Settings:** Customize which ports to scan based on your specific security requirements.
      4. **Performance Optimized:** Intelligent scanning with configurable timeouts to minimize impact on legitimate users.
      5. **Seamless Integration:** Works transparently with your existing security layers.

### How to Use

Follow these steps to configure and use the Reverse Scan feature:

1. **Enable the feature:** Set the `USE_REVERSE_SCAN` setting to `yes` to enable client port scanning.
2. **Configure ports to scan:** Customize the `REVERSE_SCAN_PORTS` setting to specify which client ports should be checked.
3. **Set scan timeout:** Adjust the `REVERSE_SCAN_TIMEOUT` to balance thorough scanning with performance.
4. **Monitor scan activity:** Check logs and the [web UI](web-ui.md) to review scan results and potential security incidents.

### Configuration Settings

| Setting                | Default                    | Context   | Multiple | Description                                                                   |
| ---------------------- | -------------------------- | --------- | -------- | ----------------------------------------------------------------------------- |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | no       | **Enable Reverse Scan:** Set to `yes` to enable scanning of clients ports.    |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | no       | **Ports to Scan:** Space-separated list of ports to check on the client side. |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | no       | **Scan Timeout:** Maximum time in milliseconds allowed for scanning a port.   |

!!! warning "Performance Considerations"
    Scanning multiple ports can add latency to client connections. Use an appropriate timeout value and limit the number of ports scanned to maintain good performance.

!!! info "Common Proxy Ports"
    The default configuration includes common ports used by proxy servers (80, 443, 8080, 3128) and SSH (22). You may want to customize this list based on your threat model.

### Example Configurations

=== "Basic Configuration"

    A simple configuration for enabling client port scanning:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Comprehensive Scanning"

    A more thorough configuration that checks additional ports:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Performance-Optimized Configuration"

    Configuration tuned for better performance by checking fewer ports with lower timeout:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "High-Security Configuration"

    Configuration focused on maximum security with extended scanning:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```

## Robots.txt

STREAM support :white_check_mark:

The Robots.txt plugin manages the [robots.txt](https://www.robotstxt.org/) file for your website. This file tells web crawlers and robots which parts of your site they can or cannot access.

**How it works:**

When enabled, BunkerWeb dynamically generates the `/robots.txt` file at the root of your website. The rules within this file are aggregated from multiple sources in the following order:

1.  **DarkVisitors API:** If `ROBOTSTXT_DARKVISITORS_TOKEN` is provided, rules are fetched from the [DarkVisitors](https://darkvisitors.com/) API, allowing dynamic blocking of malicious bots and AI crawlers based on configured agent types and disallowed user agents.
2.  **Community Lists:** Rules from pre-defined, community-maintained `robots.txt` lists (specified by `ROBOTSTXT_COMMUNITY_LISTS`) are included.
3.  **Custom URLs:** Rules are fetched from user-provided URLs (specified by `ROBOTSTXT_URLS`).
4.  **Manual Rules:** Rules defined directly via `ROBOTSTXT_RULE` environment variables are added.

All rules from these sources are combined. After aggregation, `ROBOTSTXT_IGNORE_RULE` are applied to filter out any unwanted rules using PCRE regex patterns. Finally, if no rules remain after this entire process, a default `User-agent: *` and `Disallow: /` rule is automatically applied to ensure a basic level of protection. Optional sitemap URLs (specified by `ROBOTSTXT_SITEMAP`) are also included in the final `robots.txt` output.

### Dynamic Bot Circumvention with DarkVisitors API

[DarkVisitors](https://darkvisitors.com/) is a service that provides a dynamic `robots.txt` file to help block known malicious bots and AI crawlers. By integrating with DarkVisitors, BunkerWeb can automatically fetch and serve an up-to-date `robots.txt` that helps protect your site from unwanted automated traffic.

To enable this, you need to sign up at [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) and obtain a bearer token.

### How to Use

1.  **Enable the feature:** Set the `USE_ROBOTSTXT` setting to `yes`.
2.  **Configure rules:** Choose one or more methods to define your `robots.txt` rules:
    -   **DarkVisitors API:** Provide `ROBOTSTXT_DARKVISITORS_TOKEN` and optionally `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` and `ROBOTSTXT_DARKVISITORS_DISALLOW`.
    -   **Community Lists:** Specify `ROBOTSTXT_COMMUNITY_LISTS` (space-separated IDs).
    -   **Custom URLs:** Provide `ROBOTSTXT_URLS` (space-separated URLs).
    -   **Manual Rules:** Use `ROBOTSTXT_RULE` for individual rules (multiple rules can be specified with `ROBOTSTXT_RULE_N`).
3.  **Filter rules (optional):** Use `ROBOTSTXT_IGNORE_RULE_N` to exclude specific rules by regex pattern.
4.  **Add sitemaps (optional):** Use `ROBOTSTXT_SITEMAP_N` for sitemap URLs.
5.  **Obtain the generated robots.txt file:** Once BunkerWeb is running with the above settings, you can access the dynamically generated `robots.txt` file by making an HTTP GET request to `http(s)://your-domain.com/robots.txt`.

### Configuration Settings

| Setting                              | Default | Context   | Multiple | Description                                                                                                                           |
| ------------------------------------ | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`    | multisite | No       | Enables or disables the `robots.txt` feature.                                                                                         |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |         | multisite | No       | Bearer token for the DarkVisitors API.                                                                                                |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |         | multisite | No       | Comma-separated list of agent types (e.g., `AI Data Scraper`) to include from DarkVisitors.                                           |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`     | multisite | No       | A string specifying which URLs are disallowed. This value will be sent as the disallow field when contacting the DarkVisitors API.    |
| `ROBOTSTXT_COMMUNITY_LISTS`          |         | multisite | No       | Space-separated list of community-maintained rule set IDs to include.                                                                 |
| `ROBOTSTXT_URLS`                     |         | multisite | No       | Space-separated list of URLs to fetch additional `robots.txt` rules from. Supports `file://` and basic auth (`http://user:pass@url`). |
| `ROBOTSTXT_RULE`                     |         | multisite | Yes      | A single rule for `robots.txt`.                                                                                                       |
| `ROBOTSTXT_HEADER`                   |         | multisite | Yes      | Header for `robots.txt` file (before rules). Can be Base64 encoded.                                                                   |
| `ROBOTSTXT_FOOTER`                   |         | multisite | Yes      | Footer for `robots.txt` file (after rules). Can be Base64 encoded.                                                                    |
| `ROBOTSTXT_IGNORE_RULE`              |         | multisite | Yes      | A single PCRE regex pattern to ignore rules.                                                                                          |
| `ROBOTSTXT_SITEMAP`                  |         | multisite | Yes      | A single sitemap URL.                                                                                                                 |

### Example Configurations

**Basic Manual Rules**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Using Dynamic Sources (DarkVisitors & Community List)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

**Combined Configuration**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**With Header and Footer**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# This is a custom header"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# This is a custom footer"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

---

For more information, see the [robots.txt documentation](https://www.robotstxt.org/robotstxt.html).

## SSL

STREAM support :white_check_mark:

The SSL plugin provides robust SSL/TLS encryption capabilities for your BunkerWeb-protected websites. This core component enables secure HTTPS connections by configuring and optimizing cryptographic protocols, ciphers, and related security settings to protect data in transit between clients and your web services.

**How it works:**

1. When a client initiates an HTTPS connection to your website, BunkerWeb handles the SSL/TLS handshake using your configured settings.
2. The plugin enforces modern encryption protocols and strong cipher suites while disabling known vulnerable options.
3. Optimized SSL session parameters improve connection performance without sacrificing security.
4. Certificate presentation is configured according to best practices to ensure compatibility and security.

!!! success "Security Benefits"
    - **Data Protection:** Encrypts data in transit, preventing eavesdropping and man-in-the-middle attacks
    - **Authentication:** Verifies the identity of your server to clients
    - **Integrity:** Ensures data hasn't been tampered with during transmission
    - **Modern Standards:** Configured for compliance with industry best practices and security standards

### How to Use

Follow these steps to configure and use the SSL feature:

1. **Configure protocols:** Choose which SSL/TLS protocol versions to support using the `SSL_PROTOCOLS` setting.
2. **Select cipher suites:** Specify the encryption strength using the `SSL_CIPHERS_LEVEL` setting or provide custom ciphers with `SSL_CIPHERS_CUSTOM`.
3. **Configure HTTP to HTTPS redirection:** Set up automatic redirection using the `AUTO_REDIRECT_HTTP_TO_HTTPS` or `REDIRECT_HTTP_TO_HTTPS` settings.

### Configuration Settings

| Setting                       | Default           | Context   | Multiple | Description                                                                                                                        |
| ----------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | no       | **Redirect HTTP to HTTPS:** When set to `yes`, all HTTP requests are redirected to HTTPS.                                          |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | no       | **Auto Redirect HTTP to HTTPS:** When set to `yes`, automatically redirects HTTP to HTTPS if HTTPS is detected.                    |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | no       | **SSL Protocols:** Space-separated list of SSL/TLS protocols to support.                                                           |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | no       | **SSL Ciphers Level:** Preset security level for cipher suites (`modern`, `intermediate`, or `old`).                               |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | no       | **Custom SSL Ciphers:** Colon-separated list of cipher suites to use for SSL/TLS connections (overrides level).                    |
| `SSL_ECDH_CURVE`              | `auto`            | multisite | no       | **SSL ECDH Curves:** Colon-separated list of ECDH curves (TLS groups) or `auto` for smart selection (prefers PQC on OpenSSL 3.5+). |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | multisite | no       | **SSL Session Cache Size:** Size of the SSL session cache (e.g., `10m`, `512k`). Set to `off` or `none` to disable.                |

!!! tip "SSL Labs Testing"
    After configuring your SSL settings, use the [Qualys SSL Labs Server Test](https://www.ssllabs.com/ssltest/) to verify your configuration and check for potential security issues. A proper BunkerWeb SSL configuration should achieve an A+ rating.

!!! warning "Protocol Selection"
    Support for older protocols like SSLv3, TLSv1.0, and TLSv1.1 is intentionally disabled by default due to known vulnerabilities. Only enable these protocols if you absolutely need to support legacy clients and understand the security implications of doing so.

### Example Configurations

=== "Modern Security (Default)"

    The default configuration that provides strong security while maintaining compatibility with modern browsers:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Maximum Security"

    Configuration focused on maximum security, potentially with reduced compatibility for older clients:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Legacy Compatibility"

    Configuration with broader compatibility for older clients (use only if necessary):

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Custom Ciphers"

    Configuration using custom cipher specification:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

## Security.txt

STREAM support :white_check_mark:

The Security.txt plugin implements the [Security.txt](https://securitytxt.org/) standard ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) for your website. This feature helps security researchers access your security policies and provides a standardized way for them to report security vulnerabilities they discover in your systems.

**How it works:**

1. When enabled, BunkerWeb creates a `/.well-known/security.txt` file at the root of your website.
2. This file contains information about your security policies, contacts, and other relevant details.
3. Security researchers and automated tools can easily find this file at the standard location.
4. The content is configured using simple settings that allow you to specify contact information, encryption keys, policies, and acknowledgments.
5. BunkerWeb automatically formats the file in accordance with RFC 9116.

### How to Use

Follow these steps to configure and use the Security.txt feature:

1. **Enable the feature:** Set the `USE_SECURITYTXT` setting to `yes` to enable the security.txt file.
2. **Configure contact information:** Specify at least one contact method using the `SECURITYTXT_CONTACT` setting.
3. **Set additional information:** Configure optional fields like expiration date, encryption, acknowledgments, and policy URLs.
4. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb will automatically create and serve the security.txt file at the standard location.

### Configuration Settings

| Setting                        | Default                     | Context   | Multiple | Description                                                                                              |
| ------------------------------ | --------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | no       | **Enable Security.txt:** Set to `yes` to enable the security.txt file.                                   |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | no       | **Security.txt URI:** Indicates the URI where the security.txt file will be accessible.                  |
| `SECURITYTXT_CONTACT`          |                             | multisite | yes      | **Contact Information:** How security researchers can contact you (e.g., `mailto:security@example.com`). |
| `SECURITYTXT_EXPIRES`          |                             | multisite | no       | **Expiration Date:** When this security.txt file should be considered expired (ISO 8601 format).         |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | yes      | **Encryption:** URL pointing to encryption keys to be used for secure communication.                     |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | yes      | **Acknowledgements:** URL where security researchers are recognized for their reports.                   |
| `SECURITYTXT_POLICY`           |                             | multisite | yes      | **Security Policy:** URL pointing to the security policy describing how to report vulnerabilities.       |
| `SECURITYTXT_HIRING`           |                             | multisite | yes      | **Security Jobs:** URL pointing to security-related job openings.                                        |
| `SECURITYTXT_CANONICAL`        |                             | multisite | yes      | **Canonical URL:** The canonical URI(s) for this security.txt file.                                      |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | no       | **Preferred Language:** The language(s) used in communications. Specified as an ISO 639-1 language code. |
| `SECURITYTXT_CSAF`             |                             | multisite | yes      | **CSAF:** Link to the provider-metadata.json of your Common Security Advisory Framework provider.        |

!!! warning "Expiration Date Required"
    According to RFC 9116, the `Expires` field is required. If you don't provide a value for `SECURITYTXT_EXPIRES`, BunkerWeb automatically sets the expiration date to one year from the current date.

!!! info "Contact Information Is Essential"
    The `Contact` field is the most important part of the security.txt file. You should provide at least one way for security researchers to contact you. This can be an email address, a web form, a phone number, or any other method that works for your organization.

!!! warning "URLs Must Use HTTPS"
    According to RFC 9116, all URLs in the security.txt file (except for `mailto:` and `tel:` links) MUST use HTTPS. Non-HTTPS URLs will automatically be converted to HTTPS by BunkerWeb to ensure compliance with the standard.

### Example Configurations

=== "Basic Configuration"

    A minimal configuration with just contact information:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Comprehensive Configuration"

    A more complete configuration with all fields:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Multiple Contacts Configuration"

    Configuration with multiple contact methods:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```

## Self-signed certificate

STREAM support :white_check_mark:

The Self-signed Certificate plugin automatically generates and manages SSL/TLS certificates directly within BunkerWeb, enabling secure HTTPS connections without requiring an external certificate authority. This feature is particularly useful in development environments, internal networks, or whenever you need to quickly deploy HTTPS without configuring external certificates.

**How it works:**

1. When enabled, BunkerWeb automatically generates a self-signed SSL/TLS certificate for your configured domains.
2. The certificate includes all server names defined in your configuration, ensuring proper SSL validation for each domain.
3. Certificates are stored securely and used to encrypt all HTTPS traffic to your websites.
4. The certificate is automatically renewed before expiration, ensuring continuous HTTPS availability.

!!! warning "Browser Security Warnings"
    Browsers will display security warnings when users visit sites using self-signed certificates, as these certificates aren't validated by a trusted certificate authority. For production environments, consider using [Let's Encrypt](#lets-encrypt) instead.

### How to Use

Follow these steps to configure and use the Self-signed Certificate feature:

1. **Enable the feature:** Set the `GENERATE_SELF_SIGNED_SSL` setting to `yes` to enable self-signed certificate generation.
2. **Choose cryptographic algorithm:** Select your preferred algorithm using the `SELF_SIGNED_SSL_ALGORITHM` setting.
3. **Configure validity period:** Optionally set how long the certificate should be valid using the `SELF_SIGNED_SSL_EXPIRY` setting.
4. **Set certificate subject:** Configure the certificate subject using the `SELF_SIGNED_SSL_SUBJ` setting.
5. **Let BunkerWeb handle the rest:** Once configured, certificates are automatically generated and applied to your domains.

!!! tip "Stream Mode Configuration"
    For stream mode, configure the `LISTEN_STREAM_PORT_SSL` setting to specify the SSL/TLS listening port. This step is essential for proper operation in stream mode.

### Configuration Settings

| Setting                     | Default                | Context   | Multiple | Description                                                                                                                       |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | no       | **Enable Self-signed:** Set to `yes` to enable automatic self-signed certificate generation.                                      |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | no       | **Certificate Algorithm:** Algorithm used for certificate generation: `ec-prime256v1`, `ec-secp384r1`, `rsa-2048`, or `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | no       | **Certificate Validity:** Number of days the self-signed certificate should be valid (default: 1 year).                           |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | no       | **Certificate Subject:** Subject field for the certificate that identifies the domain.                                            |

!!! tip "Development Environments"
    Self-signed certificates are ideal for development and testing environments where you need HTTPS but do not require certificates trusted by public browsers.

!!! info "Certificate Information"
    The generated self-signed certificates use the specified algorithm (defaulting to Elliptic Curve cryptography with the prime256v1 curve) and include the configured subject, ensuring proper functionality for your domains.

### Example Configurations

=== "Basic Configuration"

    A simple configuration using self-signed certificates with default settings:

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Short-lived Certificates"

    Configuration with certificates that expire more frequently (useful for regularly testing certificate renewal processes):

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Testing with RSA Certificates"

    Configuration for a testing environment where a domain uses self-signed RSA certificates:

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```

## Sessions

STREAM support :white_check_mark:

The Sessions plugin provides robust HTTP session management for BunkerWeb, enabling secure and reliable user session tracking across requests. This core feature is essential for maintaining user state, authentication persistence, and supporting other features that require identity continuity, such as [anti‑bot](#antibot) protection and user authentication systems.

**How it works:**

1. When a user first interacts with your website, BunkerWeb creates a unique session identifier.
2. This identifier is securely stored in a cookie on the user's browser.
3. On subsequent requests, BunkerWeb retrieves the session identifier from the cookie and uses it to access the user's session data.
4. Session data can be stored locally or in [Redis](#redis) for distributed environments with multiple BunkerWeb instances.
5. Sessions are automatically managed with configurable timeouts, ensuring security while maintaining usability.
6. The cryptographic security of sessions is ensured through a secret key that is used to sign session cookies.

### How to Use

Follow these steps to configure and use the Sessions feature:

1. **Configure session security:** Set a strong, unique `SESSIONS_SECRET` to ensure session cookies cannot be forged. (The default value is "random" which triggers BunkerWeb to generate a random secret key.)
2. **Choose a session name:** Optionally customize the `SESSIONS_NAME` to define what your session cookie will be called in the browser. (The default value is "random" which triggers BunkerWeb to generate a random name.)
3. **Set session timeouts:** Configure how long sessions remain valid with the timeout settings (`SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`).
4. **Configure Redis integration:** For distributed environments, set `USE_REDIS` to "yes" and configure your [Redis connection](#redis) to share session data across multiple BunkerWeb nodes.
5. **Let BunkerWeb handle the rest:** Once configured, session management happens automatically for your website.

### Configuration Settings

| Setting                     | Default  | Context | Multiple | Description                                                                                                                |
| --------------------------- | -------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global  | no       | **Session Secret:** Cryptographic key used to sign session cookies. Should be a strong, random string unique to your site. |
| `SESSIONS_NAME`             | `random` | global  | no       | **Cookie Name:** The name of the cookie that will store the session identifier.                                            |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global  | no       | **Idling Timeout:** Maximum time (in seconds) of inactivity before the session is invalidated.                             |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global  | no       | **Rolling Timeout:** Maximum time (in seconds) before a session must be renewed.                                           |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global  | no       | **Absolute Timeout:** Maximum time (in seconds) before a session is destroyed regardless of activity.                      |
| `SESSIONS_CHECK_IP`         | `yes`    | global  | no       | **Check IP:** When set to `yes`, destroys the session if the client IP address changes.                                    |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global  | no       | **Check User-Agent:** When set to `yes`, destroys the session if the client User-Agent changes.                            |

!!! warning "Security Considerations"
    The `SESSIONS_SECRET` setting is critical for security. In production environments:

    1. Use a strong, random value (at least 32 characters)
    2. Keep this value confidential
    3. Use the same value across all BunkerWeb instances in a cluster
    4. Consider using environment variables or secrets management to avoid storing this in plain text

!!! tip "Clustered Environments"
    If you're running multiple BunkerWeb instances behind a load balancer:

    1. Set `USE_REDIS` to `yes` and configure your Redis connection
    2. Ensure all instances use the exact same `SESSIONS_SECRET` and `SESSIONS_NAME`
    3. This ensures users maintain their session regardless of which BunkerWeb instance handles their requests

### Example Configurations

=== "Basic Configuration"

    A simple configuration for a single BunkerWeb instance:

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "myappsession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Enhanced Security"

    Configuration with increased security settings:

    ```yaml
    SESSIONS_SECRET: "your-very-strong-random-secret-key-here"
    SESSIONS_NAME: "securesession"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 minutes
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 minutes
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 hours
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Clustered Environment with Redis"

    Configuration for multiple BunkerWeb instances sharing session data:

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "clustersession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Ensure Redis connection is configured correctly
    ```

=== "Long-lived Sessions"

    Configuration for applications requiring extended session persistence:

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "persistentsession"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 day
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 days
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 days
    ```

## UI

STREAM support :x:

Integrate easily the BunkerWeb UI.

| Setting   | Default | Context   | Multiple | Description                                  |
| --------- | ------- | --------- | -------- | -------------------------------------------- |
| `USE_UI`  | `no`    | multisite | no       | Use UI                                       |
| `UI_HOST` |         | global    | no       | Address of the web UI used for initial setup |

## User Manager <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/EIohiUf9Fg4' title='User Manager' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

STREAM support :x:

Add the possibility to manage users on the web interface

| Setting             | Default | Context | Multiple | Description                                     |
| ------------------- | ------- | ------- | -------- | ----------------------------------------------- |
| `USERS_REQUIRE_2FA` | `no`    | global  | no       | Require two-factor authentication for all users |

## Whitelist

STREAM support :warning:

The Whitelist plugin lets you define a list of trusted IP addresses that bypass other security filters.
For blocking unwanted clients instead, refer to the [Blacklist plugin](#blacklist).

The Whitelist plugin provides a comprehensive approach to explicitly allow access to your website based on various client attributes. This feature provides a security mechanism: visitors matching specific criteria are granted immediate access, while all others must pass regular security checks.

**How it works:**

1. You define criteria for visitors who should be "whitelisted" (*IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns*).
2. When a visitor attempts to access your site, BunkerWeb checks whether they match any of these whitelist criteria.
3. If a visitor matches any whitelist rule (and doesn't match any ignore rule), they are granted access to your site and **bypass all other security checks**.
4. If a visitor doesn't match any whitelist criteria, they proceed through all normal security checks as usual.
5. Whitelists can be automatically updated from external sources on a regular schedule.

### How to Use

Follow these steps to configure and use the Whitelist feature:

1. **Enable the feature:** The Whitelist feature is disabled by default. Set the `USE_WHITELIST` setting to `yes` to enable it.
2. **Configure allow rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be whitelisted.
3. **Set up ignore rules:** Specify any exceptions that should bypass the whitelist checks.
4. **Add external sources:** Configure URLs for automatically downloading and updating whitelist data.
5. **Monitor access:** Check the [web UI](web-ui.md) to see which visitors are being allowed or denied.

!!! info "stream mode"
    When using stream mode, only IP, rDNS, and ASN checks are performed.

### Configuration Settings

**General**

| Setting         | Default | Context   | Multiple | Description                                                         |
| --------------- | ------- | --------- | -------- | ------------------------------------------------------------------- |
| `USE_WHITELIST` | `no`    | multisite | no       | **Enable Whitelist:** Set to `yes` to enable the whitelist feature. |

=== "IP Address"
    **What this does:** Whitelists visitors based on their IP address or network. These visitors will bypass all security checks.

    | Setting                    | Default | Context   | Multiple | Description                                                                                                |
    | -------------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |         | multisite | no       | **IP Whitelist:** List of IP addresses or networks (CIDR notation) to allow, separated by spaces.          |
    | `WHITELIST_IGNORE_IP`      |         | multisite | no       | **IP Ignore List:** List of IP addresses or networks that should bypass IP whitelist checks.               |
    | `WHITELIST_IP_URLS`        |         | multisite | no       | **IP Whitelist URLs:** List of URLs containing IP addresses or networks to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_IP_URLS` |         | multisite | no       | **IP Ignore List URLs:** List of URLs containing IP addresses or networks to ignore.                       |

=== "Reverse DNS"
    **What this does:** Whitelists visitors based on their domain name (in reverse). This is useful for allowing access to visitors from specific organizations or networks by their domain.

    | Setting                      | Default | Context   | Multiple | Description                                                                                              |
    | ---------------------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_RDNS`             |         | multisite | no       | **rDNS Whitelist:** List of reverse DNS suffixes to allow, separated by spaces.                          |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`   | multisite | no       | **rDNS Global Only:** Only perform rDNS whitelist checks on global IP addresses when set to `yes`.       |
    | `WHITELIST_IGNORE_RDNS`      |         | multisite | no       | **rDNS Ignore List:** List of reverse DNS suffixes that should bypass rDNS whitelist checks.             |
    | `WHITELIST_RDNS_URLS`        |         | multisite | no       | **rDNS Whitelist URLs:** List of URLs containing reverse DNS suffixes to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_RDNS_URLS` |         | multisite | no       | **rDNS Ignore List URLs:** List of URLs containing reverse DNS suffixes to ignore.                       |

=== "ASN"
    **What this does:** Whitelists visitors from specific network providers using Autonomous System Numbers. ASNs identify which provider or organization an IP belongs to.

    | Setting                     | Default | Context   | Multiple | Description                                                                             |
    | --------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------- |
    | `WHITELIST_ASN`             |         | multisite | no       | **ASN Whitelist:** List of Autonomous System Numbers to allow, separated by spaces.     |
    | `WHITELIST_IGNORE_ASN`      |         | multisite | no       | **ASN Ignore List:** List of ASNs that should bypass ASN whitelist checks.              |
    | `WHITELIST_ASN_URLS`        |         | multisite | no       | **ASN Whitelist URLs:** List of URLs containing ASNs to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_ASN_URLS` |         | multisite | no       | **ASN Ignore List URLs:** List of URLs containing ASNs to ignore.                       |

=== "User Agent"
    **What this does:** Whitelists visitors based on what browser or tool they claim to be using. This is effective for allowing access to specific known tools or services.

    | Setting                            | Default | Context   | Multiple | Description                                                                                             |
    | ---------------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |         | multisite | no       | **User-Agent Whitelist:** List of User-Agent patterns (PCRE regex) to allow, separated by spaces.       |
    | `WHITELIST_IGNORE_USER_AGENT`      |         | multisite | no       | **User-Agent Ignore List:** List of User-Agent patterns that should bypass User-Agent whitelist checks. |
    | `WHITELIST_USER_AGENT_URLS`        |         | multisite | no       | **User-Agent Whitelist URLs:** List of URLs containing User-Agent patterns to whitelist.                |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |         | multisite | no       | **User-Agent Ignore List URLs:** List of URLs containing User-Agent patterns to ignore.                 |

=== "URI"
    **What this does:** Whitelists requests to specific URLs on your site. This is helpful for allowing access to specific endpoints regardless of other factors.

    | Setting                     | Default | Context   | Multiple | Description                                                                                     |
    | --------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------- |
    | `WHITELIST_URI`             |         | multisite | no       | **URI Whitelist:** List of URI patterns (PCRE regex) to allow, separated by spaces.             |
    | `WHITELIST_IGNORE_URI`      |         | multisite | no       | **URI Ignore List:** List of URI patterns that should bypass URI whitelist checks.              |
    | `WHITELIST_URI_URLS`        |         | multisite | no       | **URI Whitelist URLs:** List of URLs containing URI patterns to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_URI_URLS` |         | multisite | no       | **URI Ignore List URLs:** List of URLs containing URI patterns to ignore.                       |

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Whitelists from URLs are automatically downloaded and updated hourly to ensure your protection remains current with the latest trusted sources.

!!! warning "Security Bypass"
    Whitelisted visitors will completely **bypass all other security checks** in BunkerWeb, including WAF rules, rate limiting, bad bot detection, and any other security mechanisms. Only use the whitelist for trusted sources you're absolutely confident in.


### Example Configurations

=== "Basic Organization Access"

    A simple configuration that whitelists company office IPs:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "Advanced Configuration"

    A more comprehensive configuration with multiple whitelist criteria:

    ```yaml
    USE_WHITELIST: "yes"

    # Company and trusted partner assets
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # Company and partner ASNs
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # External trusted sources
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Using Local Files"

    Configuration using local files for whitelists:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///path/to/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///path/to/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///path/to/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///path/to/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///path/to/uri-whitelist.txt"
    ```

=== "API Access Pattern"

    A configuration focused on allowing access to only specific API endpoints:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # Internal network for all endpoints
    ```

=== "Well-Known Crawlers"

    A configuration that whitelists common search engine and social media crawlers:

    ```yaml
    USE_WHITELIST: "yes"

    # Verification with reverse DNS for added security
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # Only check global IPs
    ```

    This configuration allows legitimate crawlers to index your site without being subject to rate limiting or other security measures that might block them. The rDNS checks help verify that crawlers are actually coming from their claimed companies.

### Working with local list files

The `*_URLS` settings provided by the whitelist, greylist, and blacklist plugins all use the same downloader. When you reference a `file:///` URL:

- The path is resolved inside the **scheduler** container (for Docker deployments this is typically `bunkerweb-scheduler`). Mount the files there and ensure they are readable by the scheduler user.
- Each file is plain text encoded in UTF-8 with one entry per line. Empty lines are ignored and comment lines must begin with `#` or `;`. `//` comments are not supported.
- Expected value per list type:
  - **IP lists** accept IPv4/IPv6 addresses or CIDR networks (for example `192.0.2.10` or `2001:db8::/48`).
  - **rDNS lists** expect a suffix without spaces (for example `.search.msn.com`). Values are normalised to lowercase automatically.
  - **ASN lists** may contain just the number (`32934`) or the number prefixed with `AS` (`AS15169`).
  - **User-Agent lists** are treated as PCRE patterns and the whole line is preserved (including spaces). Keep comments on their own line so they are not interpreted as part of the pattern.
  - **URI lists** must start with `/` and may use PCRE tokens such as `^` or `$`.

Example files that match the expected format:

```text
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
