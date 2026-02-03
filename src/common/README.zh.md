通用插件为 BunkerWeb 提供了核心配置框架，允许您定义控制 Web 服务如何受保护和交付的基本设置。这个基础插件管理着整个 BunkerWeb 生态系统的基本方面，如安全模式、服务器默认值、日志记录行为和关键操作参数。

**工作原理：**

1.  当 BunkerWeb 启动时，通用插件会加载并应用您的核心配置设置。
2.  安全模式可以全局设置或按站点设置，以确定应用
    的保护级别。
3.  默认服务器设置为任何未指定的多站点配置建立
    了回退值。
4.  日志记录参数控制记录哪些信息以及如何格式化。
5.  这些设置构成了所有其他 BunkerWeb 插件和功能运行的基础。

### 多站点模式 {#multisite-mode}

当 `MULTISITE` 设置为 `yes` 时，BunkerWeb 可以托管和保护多个网站，每个网站都有其独特的配置。此功能在以下场景中特别有用：

- 托管具有不同配置的多个域
- 运行具有不同安全要求的多个应用程序
- 对不同服务应用量身定制的安全策略

在多站点模式下，每个站点都由一个唯一的 `SERVER_NAME` 标识。要应用特定于站点的设置，请将主 `SERVER_NAME` 作为前缀添加到设置名称中。例如：

- `www.example.com_USE_ANTIBOT=captcha` 为 `www.example.com` 启用验证码。
- `myapp.example.com_USE_GZIP=yes` 为 `myapp.example.com` 启用 GZIP 压缩。

这种方法可确保在多站点环境中将设置应用于正确的站点。

### 多个设置 {#multiple-settings}

BunkerWeb 中的某些设置支持同一功能的多个配置。要定义多组设置，请在设置名称后附加一个数字后缀。例如：

- `REVERSE_PROXY_URL_1=/subdir` 和 `REVERSE_PROXY_HOST_1=http://myhost1` 配置第一个反向代理。
- `REVERSE_PROXY_URL_2=/anotherdir` 和 `REVERSE_PROXY_HOST_2=http://myhost2` 配置第二个反向代理。

这种模式允许您为需要不同用例的不同值的功能（如反向代理、端口或其他设置）管理多个配置。

### 插件执行顺序 {#plugin-order}

可以使用空格分隔的列表调整顺序：

- 全局阶段：`PLUGINS_ORDER_INIT`、`PLUGINS_ORDER_INIT_WORKER`、`PLUGINS_ORDER_TIMER`。
- 按站点的阶段：`PLUGINS_ORDER_SET`、`PLUGINS_ORDER_ACCESS`、`PLUGINS_ORDER_SSL_CERTIFICATE`、`PLUGINS_ORDER_HEADER`、`PLUGINS_ORDER_LOG`、`PLUGINS_ORDER_PREREAD`、`PLUGINS_ORDER_LOG_STREAM`、`PLUGINS_ORDER_LOG_DEFAULT`。
- 语义：列出的插件在该阶段优先执行；其余插件仍按正常顺序执行。仅使用空格分隔插件 ID。

### 安全模式 {#security-modes}

`SECURITY_MODE` 设置决定了 BunkerWeb 如何处理检测到的威胁。这个灵活的功能允许您根据具体需求在监控或主动阻止可疑活动之间进行选择：

- **`detect`**：记录潜在威胁而不阻止访问。此模式对于以安全、无干扰的方式识别和分析误报非常有用。
- **`block`**（默认）：主动阻止检测到的威胁，同时记录事件以防止未经授权的访问并保护您的应用程序。

切换到 `detect` 模式可以帮助您识别和解决潜在的误报，而不会干扰合法客户端。一旦这些问题得到解决，您就可以自信地切换回 `block` 模式以获得全面保护。

### 配置设置

=== "核心设置"

    | 设置                  | 默认值            | 上下文    | 多个 | 描述                                                               |
    | --------------------- | ----------------- | --------- | ---- | ------------------------------------------------------------------ |
    | `SERVER_NAME`         | `www.example.com` | multisite | 否   | **主域名：** 此站点的主域名。在多站点模式下为必需。                |
    | `BUNKERWEB_INSTANCES` | `127.0.0.1`       | global    | 否   | **BunkerWeb 实例：** 以空格分隔的 BunkerWeb 实例列表。             |
    | `MULTISITE`           | `no`              | global    | 否   | **多站点：** 设置为 `yes` 以启用托管具有不同配置的多个网站。       |
    | `SECURITY_MODE`       | `block`           | multisite | 否   | **安全级别：** 控制安全强制执行的级别。选项：`detect` 或 `block`。 |
    | `SERVER_TYPE`         | `http`            | multisite | 否   | **服务器类型：** 定义服务器是 `http` 还是 `stream` 类型。          |

=== "API 设置"

    | 设置               | 默认值        | 上下文 | 多个 | 描述                                                                                           |
    | ------------------ | ------------- | ------ | ---- | ---------------------------------------------------------------------------------------------- |
    | `USE_API`          | `yes`         | global | 否   | **激活 API：** 激活 API 以控制 BunkerWeb。                                                     |
    | `API_HTTP_PORT`    | `5000`        | global | 否   | **API 端口：** API 的监听端口号。                                                              |
    | `API_HTTPS_PORT`   | `5443`        | global | 否   | **API HTTPS 端口：** API 的监听端口号 (TLS)。                                                  |
    | `API_LISTEN_HTTP`  | `yes`         | global | 否   | **API 监听 HTTP：** 启用 API 的 HTTP 监听器。                                                  |
    | `API_LISTEN_HTTPS` | `no`          | global | 否   | **API 监听 HTTPS：** 启用 API 的 HTTPS (TLS) 监听器。                                          |
    | `API_LISTEN_IP`    | `0.0.0.0`     | global | 否   | **API 监听 IP：** API 的监听 IP 地址。                                                         |
    | `API_SERVER_NAME`  | `bwapi`       | global | 否   | **API 服务器名称：** API 的服务器名称（虚拟主机）。                                            |
    | `API_WHITELIST_IP` | `127.0.0.0/8` | global | 否   | **API 白名单 IP：** 允许联系 API 的 IP/网络列表。                                              |
    | `API_TOKEN`        |               | global | 否   | **API 访问令牌（可选）：** 如果设置，所有 API 请求都必须包含 `Authorization: Bearer <token>`。 |

    注意：出于引导原因，如果您启用 `API_TOKEN`，您必须在 BunkerWeb 实例和调度程序的**两个**环境中都设置它。当 `API_TOKEN` 存在于其环境中时，调度程序会自动包含 `Authorization` 标头。如果未设置，则不发送标头，BunkerWeb 将不强制执行令牌身份验证。您可以通过设置 `API_LISTEN_HTTPS=yes`（端口：`API_HTTPS_PORT`，默认 `5443`）通过 HTTPS 公开 API。

    使用 curl 的测试示例（替换令牌和主机）：

    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://<bunkerweb-host>:5000/ping

    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         --insecure \
         https://<bunkerweb-host>:5443/ping
    ```

=== "网络和端口设置"

    | 设置            | 默认值       | 上下文 | 多个 | 描述                                         |
    | --------------- | ------------ | ------ | ---- | -------------------------------------------- |
    | `HTTP_PORT`     | `8080`       | global | 是   | **HTTP 端口：** HTTP 流量的端口号。          |
    | `HTTPS_PORT`    | `8443`       | global | 是   | **HTTPS 端口：** HTTPS 流量的端口号。        |
    | `USE_IPV6`      | `no`         | global | 否   | **IPv6 支持：** 启用 IPv6 连接。             |
    | `DNS_RESOLVERS` | `127.0.0.11` | global | 否   | **DNS 解析器：** 要使用的解析器的 DNS 地址。 |

=== "流服务器设置"

    | 设置                     | 默认值 | 上下文    | 多个 | 描述                                      |
    | ------------------------ | ------ | --------- | ---- | ----------------------------------------- |
    | `LISTEN_STREAM`          | `yes`  | multisite | 否   | **监听流：** 启用对非 SSL（直通）的监听。 |
    | `LISTEN_STREAM_PORT`     | `1337` | multisite | 是   | **流端口：** 非 SSL（直通）的监听端口。   |
    | `LISTEN_STREAM_PORT_SSL` | `4242` | multisite | 是   | **流 SSL 端口：** SSL（直通）的监听端口。 |
    | `USE_TCP`                | `yes`  | multisite | 否   | **TCP 监听：** 启用 TCP 监听（流）。      |
    | `USE_UDP`                | `no`   | multisite | 否   | **UDP 监听：** 启用 UDP 监听（流）。      |

=== "工作进程设置"

    | 设置                   | 默认值 | 上下文 | 多个 | 描述                                                              |
    | ---------------------- | ------ | ------ | ---- | ----------------------------------------------------------------- |
    | `WORKER_PROCESSES`     | `auto` | global | 否   | **工作进程数：** 工作进程的数量。设置为 `auto` 以使用可用核心数。 |
    | `WORKER_CONNECTIONS`   | `1024` | global | 否   | **工作连接数：** 每个工作进程的最大连接数。                       |
    | `WORKER_RLIMIT_NOFILE` | `2048` | global | 否   | **文件描述符限制：** 每个工作进程的最大打开文件数。               |

=== "内存设置"

    | 设置                           | 默认值 | 上下文 | 多个 | 描述                                                             |
    | ------------------------------ | ------ | ------ | ---- | ---------------------------------------------------------------- |
    | `WORKERLOCK_MEMORY_SIZE`       | `48k`  | global | 否   | **工作锁内存大小：** 用于初始化工作进程的 lua_shared_dict 大小。 |
    | `DATASTORE_MEMORY_SIZE`        | `64m`  | global | 否   | **数据存储内存大小：** 内部数据存储的大小。                      |
    | `CACHESTORE_MEMORY_SIZE`       | `64m`  | global | 否   | **缓存存储内存大小：** 内部缓存存储的大小。                      |
    | `CACHESTORE_IPC_MEMORY_SIZE`   | `16m`  | global | 否   | **缓存存储 IPC 内存大小：** 内部缓存存储 (ipc) 的大小。          |
    | `CACHESTORE_MISS_MEMORY_SIZE`  | `16m`  | global | 否   | **缓存存储未命中内存大小：** 内部缓存存储（未命中）的大小。      |
    | `CACHESTORE_LOCKS_MEMORY_SIZE` | `16m`  | global | 否   | **缓存存储锁内存大小：** 内部缓存存储（锁）的大小。              |

=== "日志设置"

    | 设置               | 默认值                                                                                                                                     | 上下文 | 多个 | 描述                                                                                                                        |
    | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ------ | ---- | --------------------------------------------------------------------------------------------------------------------------- |
    | `LOG_FORMAT`       | `$host $remote_addr - $request_id $remote_user [$time_local] \"$request\" $status $body_bytes_sent \"$http_referer\" \"$http_user_agent\"` | global | 否   | **日志格式：** 用于访问日志的格式。                                                                                         |
    | `ACCESS_LOG`       | `/var/log/bunkerweb/access.log`                                                                                                            | global | 是   | **访问日志路径：** 文件路径、`syslog:server=地址[:端口][,参数=值]` 或共享缓冲 `memory:名称:大小`；设置为 `off` 可禁用日志。 |
    | `ERROR_LOG`        | `/var/log/bunkerweb/error.log`                                                                                                             | global | 是   | **错误日志路径：** 文件路径、`stderr`、`syslog:server=地址[:端口][,参数=值]` 或 `memory:大小`。                             |
    | `LOG_LEVEL`        | `notice`                                                                                                                                   | global | 是   | **日志级别：** 错误日志的详细程度。选项：`debug`, `info`, `notice`, `warn`, `error`, `crit`, `alert`, `emerg`。             |
    | `TIMERS_LOG_LEVEL` | `debug`                                                                                                                                    | global | 否   | **计时器日志级别：** 计时器的日志级别。选项：`debug`, `info`, `notice`, `warn`, `err`, `crit`, `alert`, `emerg`。           |

    !!! tip "日志记录最佳实践"
        - 对于生产环境，请使用 `notice`、`warn` 或 `error` 日志级别以最小化日志量。
        - 为了调试问题，请暂时将日志级别设置为 `debug` 以获取更详细的信息。

=== "集成设置"

    | 设置              | 默认值 | 上下文    | 多个 | 描述                                                        |
    | ----------------- | ------ | --------- | ---- | ----------------------------------------------------------- |
    | `AUTOCONF_MODE`   | `no`   | global    | 否   | **自动配置模式：** 启用 Autoconf Docker 集成。              |
    | `SWARM_MODE`      | `no`   | global    | 否   | **Swarm 模式：** 启用 Docker Swarm 集成。                   |
    | `KUBERNETES_MODE` | `no`   | global    | 否   | **Kubernetes 模式：** 启用 Kubernetes 集成。                |
    | `KEEP_CONFIG_ON_RESTART` | `no` | global | 否 | **重启时保留配置：** 重启时保留配置。设置为 'yes' 以防止重启时重置配置。 |
    | `USE_TEMPLATE`    |        | multisite | 否   | **使用模板：** 要使用的配置模板，它将覆盖特定设置的默认值。 |

=== "Nginx 设置"

    | 设置                            | 默认值        | 上下文 | 多个 | 描述                                                                  |
    | ------------------------------- | ------------- | ------ | ---- | --------------------------------------------------------------------- |
    | `NGINX_PREFIX`                  | `/etc/nginx/` | global | 否   | **Nginx 前缀：** nginx 将搜索配置的位置。                             |
    | `SERVER_NAMES_HASH_BUCKET_SIZE` |               | global | 否   | **服务器名称哈希桶大小：** `server_names_hash_bucket_size` 指令的值。 |

### 示例配置

=== "基本生产设置"

    一个具有严格安全性的生产站点的标准配置：

    ```yaml
    SECURITY_MODE: "block"
    SERVER_NAME: "example.com"
    LOG_LEVEL: "notice"
    ```

=== "开发模式"

    一个带有额外日志记录的开发环境的配置：

    ```yaml
    SECURITY_MODE: "detect"
    SERVER_NAME: "dev.example.com"
    LOG_LEVEL: "debug"
    ```

=== "多站点配置"

    用于托管多个网站的配置：

    ```yaml
    MULTISITE: "yes"

    # 第一个站点
    site1.example.com_SERVER_NAME: "site1.example.com"
    site1.example.com_SECURITY_MODE: "block"

    # 第二个站点
    site2.example.com_SERVER_NAME: "site2.example.com"
    site2.example.com_SECURITY_MODE: "detect"
    ```

=== "流服务器配置"

    用于 TCP/UDP 服务器的配置：

    ```yaml
    SERVER_TYPE: "stream"
    SERVER_NAME: "stream.example.com"
    LISTEN_STREAM: "yes"
    LISTEN_STREAM_PORT: "1337"
    USE_TCP: "yes"
    USE_UDP: "no"
    ```
