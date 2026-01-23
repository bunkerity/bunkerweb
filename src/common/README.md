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

    | Setting           | Default | Context   | Multiple | Description                                                                                          |
    | ----------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
    | `AUTOCONF_MODE`   | `no`    | global    | No       | **Autoconf Mode:** Enable Autoconf Docker integration.                                               |
    | `SWARM_MODE`      | `no`    | global    | No       | **Swarm Mode:** Enable Docker Swarm integration.                                                     |
    | `KUBERNETES_MODE` | `no`    | global    | No       | **Kubernetes Mode:** Enable Kubernetes integration.                                                  |
    | `KEEP_CONFIG_ON_RESTART` | `no` | global | No | **Keep Config on Restart:** Keep the configuration on restart. Set to 'yes' to prevent config reset on restart. |
    | `USE_TEMPLATE`    |         | multisite | No       | **Use Template:** Config template to use that will override the default values of specific settings. |

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
