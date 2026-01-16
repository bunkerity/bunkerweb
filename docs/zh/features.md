# 功能

本节包含 BunkerWeb 支持的完整设置列表。若尚未熟悉 BunkerWeb，建议先阅读文档中的[概念](concepts.md)部分。请根据您的[集成](integrations.md)说明应用相应的设置。

## 全局设置


STREAM 支持 :warning:

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

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

Provides enhanced protection against DDoS attacks by analyzing and filtering suspicious traffic.

| 参数                         | 默认值        | 上下文 | 可重复 | 描述                                                                    |
| ---------------------------- | ------------- | ------ | ------ | ----------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global | 否     | Enable or disable anti DDoS protection to mitigate high traffic spikes. |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global | 否     | Size of in-memory storage for DDoS metrics (e.g., 10M, 500k).           |
| `ANTIDDOS_THRESHOLD`         | `100`         | global | 否     | Maximum suspicious requests allowed from a single IP before blocking.   |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global | 否     | Time window (seconds) to detect abnormal request patterns.              |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global | 否     | HTTP status codes treated as suspicious for DDoS analysis.              |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global | 否     | Minimum distinct IP count before enabling anti DDoS measures.           |

## Antibot

STREAM 支持 :x:

攻击者通常使用自动化工具（机器人）来尝试利用您的网站。为了防止这种情况，BunkerWeb 包含一个“Antibot”功能，它会挑战用户以证明他们是人类。如果用户成功完成挑战，他们将被授予访问您网站的权限。此功能默认禁用。

**工作原理：**

1.  当用户访问您的网站时，BunkerWeb 会检查他们是否已经通过了 antibot 挑战。
2.  如果没有，用户将被重定向到一个挑战页面。
3.  用户必须完成挑战（例如，解决一个 CAPTCHA，运行 JavaScript）。
4.  如果挑战成功，用户将被重定向回他们最初试图访问的页面，并可以正常浏览您的网站。

### 如何使用

请按照以下步骤启用和配置 Antibot 功能：

1.  **选择一个挑战类型：** 决定使用哪种类型的 antibot 挑战（例如，[captcha](#__tabbed_3_3)、[hcaptcha](#__tabbed_3_5)、[javascript](#__tabbed_3_2)）。
2.  **启用该功能：** 在您的 BunkerWeb 配置中将 `USE_ANTIBOT` 设置为您选择的挑战类型。
3.  **配置设置：** 根据需要调整其他 `ANTIBOT_*` 设置。对于 reCAPTCHA、hCaptcha、Turnstile 和 mCaptcha，您必须在相应的服务上创建一个帐户并获取 API 密钥。
4.  **重要提示：** 确保 `ANTIBOT_URI` 是您网站上一个未被使用的唯一 URL。

!!! important "关于 `ANTIBOT_URI` 设置"
    确保 `ANTIBOT_URI` 是您网站上一个未被使用的唯一 URL。

!!! warning "集群环境中的会话配置"
    antibot 功能使用 cookie 来跟踪用户是否已完成挑战。如果您在集群环境中运行 BunkerWeb（多个 BunkerWeb 实例），您**必须**正确配置会话管理。这涉及在所有 BunkerWeb 实例中将 `SESSIONS_SECRET` 和 `SESSIONS_NAME` 设置设置为**相同的值**。如果您不这样做，用户可能会被反复提示完成 antibot 挑战。您可以在[此处](#sessions)找到有关会话配置的更多信息。

### 通用设置

以下设置在所有挑战机制中共享：

| 设置                   | 默认值       | 上下文    | 多个 | 描述                                                                                        |
| ---------------------- | ------------ | --------- | ---- | ------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge` | multisite | 否   | **挑战 URL：** 用户将被重定向到以完成挑战的 URL。确保此 URL 未用于您网站上的任何其他内容。  |
| `ANTIBOT_TIME_RESOLVE` | `60`         | multisite | 否   | **挑战时间限制：** 用户完成挑战的最长时间（以秒为单位）。此时间过后，将生成新的挑战。       |
| `ANTIBOT_TIME_VALID`   | `86400`      | multisite | 否   | **挑战有效期：** 已完成的挑战的有效时间（以秒为单位）。此时间过后，用户将必须解决新的挑战。 |

### 从挑战中排除流量

BunkerWeb 允许您指定某些用户、IP 或请求应完全绕过 antibot 挑战。这对于将受信任的服务、内部网络或应始终无需挑战即可访问的特定页面列入白名单非常有用：

| 设置                        | 默认值 | 上下文    | 多个 | 描述                                                                                  |
| --------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |        | multisite | 否   | **排除的 URL：** 应绕过挑战的以空格分隔的 URI 正则表达式模式列表。                    |
| `ANTIBOT_IGNORE_IP`         |        | multisite | 否   | **排除的 IP：** 应绕过挑战的以空格分隔的 IP 地址或 CIDR 范围列表。                    |
| `ANTIBOT_IGNORE_RDNS`       |        | multisite | 否   | **排除的反向 DNS：** 应绕过挑战的以空格分隔的反向 DNS 后缀列表。                      |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`  | multisite | 否   | **仅限全局 IP：** 如果设置为 `yes`，则仅对公共 IP 地址执行反向 DNS 检查。             |
| `ANTIBOT_IGNORE_ASN`        |        | multisite | 否   | **排除的 ASN：** 应绕过挑战的以空格分隔的 ASN 编号列表。                              |
| `ANTIBOT_IGNORE_USER_AGENT` |        | multisite | 否   | **排除的用户代理：** 应绕过挑战的以空格分隔的用户代理正则表达式模式列表。             |
| `ANTIBOT_IGNORE_COUNTRY`    |        | multisite | 否   | **排除的国家：** 应绕过挑战的 ISO 3166-1 alpha-2 国家代码（用空格分隔）列表。         |
| `ANTIBOT_ONLY_COUNTRY`      |        | multisite | 否   | **仅挑战的国家：** 必须完成挑战的 ISO 3166-1 alpha-2 国家代码列表，其他国家将被跳过。 |

!!! note "国家设置的行为"
      - 当同时设置 `ANTIBOT_IGNORE_COUNTRY` 和 `ANTIBOT_ONLY_COUNTRY` 时，忽略列表优先——同时出现在两个列表中的国家将绕过挑战。
      - 当设置了 `ANTIBOT_ONLY_COUNTRY` 且 IP 为私有或无法解析的地址时，由于无法确定国家代码，请求会绕过挑战。

**示例：**

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  这将从 antibot 挑战中排除所有以 `/api/`、`/webhook/` 或 `/assets/` 开头的 URI。

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  这将从 antibot 挑战中排除内部网络 `192.168.1.0/24` 和特定 IP `10.0.0.1`。

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  这将从 antibot 挑战中排除来自反向 DNS 以 `googlebot.com` 或 `bingbot.com` 结尾的主机的请求。

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  这将从 antibot 挑战中排除来自 ASN 15169 (Google) 和 ASN 8075 (Microsoft) 的请求。

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  这将从 antibot 挑战中排除用户代理与指定正则表达式模式匹配的请求。

- `ANTIBOT_IGNORE_COUNTRY: "US CA"`
  这将使来自美国或加拿大的访问者绕过 antibot 挑战。

- `ANTIBOT_ONLY_COUNTRY: "CN RU"`
  这将仅要求来自中国或俄罗斯的访问者完成挑战。来自其他国家（或私有 IP 范围）的请求将被跳过。

### 支持的挑战机制

=== "Cookie"

    Cookie 挑战是一种轻量级的机制，它依赖于在用户的浏览器中设置一个 cookie。当用户访问网站时，服务器会向客户端发送一个 cookie。在后续的请求中，服务器会检查这个 cookie 是否存在，以验证用户是否是合法的。这种方法对于基本的机器人防护简单有效，无需额外的用户交互。

    **工作原理：**

    1.  服务器生成一个唯一的 cookie 并将其发送给客户端。
    2.  客户端必须在后续的请求中返回该 cookie。
    3.  如果 cookie 缺失或无效，用户将被重定向到挑战页面。

    **配置设置：**

    | 设置          | 默认值 | 上下文    | 多个 | 描述                                                    |
    | ------------- | ------ | --------- | ---- | ------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | no   | **启用 Antibot：** 设置为 `cookie` 以启用 Cookie 挑战。 |

=== "JavaScript"

    JavaScript 挑战要求客户端使用 JavaScript 解决一个计算任务。这种机制确保客户端启用了 JavaScript 并且可以执行所需的代码，这通常超出了大多数机器人的能力。

    **工作原理：**

    1.  服务器向客户端发送一个 JavaScript 脚本。
    2.  该脚本执行一个计算任务（例如，哈希）并将结果提交回服务器。
    3.  服务器验证结果以确认客户端的合法性。

    **主要特点：**

    -   该挑战为每个客户端动态生成一个独特的任务。
    -   计算任务涉及具有特定条件的哈希（例如，找到具有某个前缀的哈希）。

    **配置设置：**

    | 设置          | 默认值 | 上下文    | 多个 | 描述                                                            |
    | ------------- | ------ | --------- | ---- | --------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | no   | **启用 Antibot：** 设置为 `javascript` 以启用 JavaScript 挑战。 |

=== "Captcha"

    Captcha 挑战是一种自制的机制，它可以在您的 BunkerWeb 环境中完全托管生成基于图像的挑战。它测试用户识别和解释随机字符的能力，确保在不依赖外部服务的情况下有效阻止自动化机器人。

    **工作原理：**

    1.  服务器生成一个包含随机字符的 CAPTCHA 图像。
    2.  用户必须将图像中显示的字符输入文本字段。
    3.  服务器根据生成的 CAPTCHA 验证用户的输入。

    **主要特点：**

    -   完全自托管，无需第三方 API。
    -   动态生成的挑战确保每个用户会话的唯一性。
    -   使用可自定义的字符集生成 CAPTCHA。

    **支持的字符：**

    CAPTCHA 系统支持以下字符类型：

    -   **字母：** 所有小写 (a-z) 和大写 (A-Z) 字母
    -   **数字：** 2, 3, 4, 5, 6, 7, 8, 9（不包括 0 和 1 以避免混淆）
    -   **特殊字符：** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    要获取支持的完整字符集，请参阅用于 CAPTCHA 的字体的[字体字符映射](https://www.dafont.com/moms-typewriter.charmap?back=theme)。

    **配置设置：**

    | 设置                       | 默认值                                                 | 上下文    | 多个 | 描述                                                                                                                                                                 |
    | -------------------------- | ------------------------------------------------------ | --------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                                                   | multisite | no   | **启用 Antibot：** 设置为 `captcha` 以启用 Captcha 挑战。                                                                                                            |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | multisite | no   | **Captcha 字母表：** 用于生成 CAPTCHA 的字符字符串。支持的字符：所有字母 (a-z, A-Z)、数字 2-9（不包括 0 和 1）以及特殊字符：```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

=== "reCAPTCHA"

    启用后，reCAPTCHA 会在后台运行 (v3)，根据用户行为分配一个分数。低于配置阈值的分数将提示进一步验证或阻止请求。对于可见的挑战 (v2)，用户必须与 reCAPTCHA 小部件交互才能继续。

    现在有两种集成 reCAPTCHA 的方法：
    - 经典版本（站点/密钥，v2/v3 验证端点）
    - 使用 Google Cloud 的新版本（项目 ID + API 密钥）。经典版本仍然可用，可以通过 `ANTIBOT_RECAPTCHA_CLASSIC` 进行切换。

    对于经典版本，请从 [Google reCAPTCHA 管理控制台](https://www.google.com/recaptcha/admin)获取您的站点和密钥。
    对于新版本，请在您的 Google Cloud 项目中创建一个 reCAPTCHA 密钥，并使用项目 ID 和一个 API 密钥（请参阅 [Google Cloud reCAPTCHA 控制台](https://console.cloud.google.com/security/recaptcha)）。仍然需要一个站点密钥。

    **配置设置：**

    | 设置                           | 默认值 | 上下文    | 多个 | 描述                                                                     |
    | ------------------------------ | ------ | --------- | ---- | ------------------------------------------------------------------------ |
    | `USE_ANTIBOT`                  | `no`   | multisite | no   | 启用 antibot；设置为 `recaptcha` 以启用 reCAPTCHA。                      |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`  | multisite | no   | 使用经典 reCAPTCHA。设置为 `no` 以使用新的基于 Google Cloud 的版本。     |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |        | multisite | no   | reCAPTCHA 站点密钥。经典版和新版都需要。                                 |
    | `ANTIBOT_RECAPTCHA_SECRET`     |        | multisite | no   | reCAPTCHA 密钥。仅经典版需要。                                           |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |        | multisite | no   | Google Cloud 项目 ID。仅新版需要。                                       |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |        | multisite | no   | 用于调用 reCAPTCHA Enterprise API 的 Google Cloud API 密钥。仅新版需要。 |
    | `ANTIBOT_RECAPTCHA_JA3`        |        | multisite | no   | 可选的 JA3 TLS 指纹，包含在企业评估中。                                  |
    | `ANTIBOT_RECAPTCHA_JA4`        |        | multisite | no   | 可选的 JA4 TLS 指纹，包含在企业评估中。                                  |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`  | multisite | no   | 通过所需的最低分数（适用于经典 v3 和新版本）。                           |

=== "hCaptcha"

    启用后，hCaptcha 提供了一个有效的 reCAPTCHA 替代方案，它通过验证用户交互而无需依赖评分机制。它用一个简单的交互式测试来挑战用户，以确认他们的合法性。

    要将 hCaptcha 与 BunkerWeb 集成，您必须从 hCaptcha 仪表板 [hCaptcha](https://www.hcaptcha.com) 获取必要的凭据。这些凭据包括一个站点密钥和一个密钥。

    **配置设置：**

    | 设置                       | 默认值 | 上下文    | 多个 | 描述                                                                 |
    | -------------------------- | ------ | --------- | ---- | -------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`   | multisite | no   | **启用 Antibot：** 设置为 `hcaptcha` 以启用 hCaptcha 挑战。          |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |        | multisite | no   | **hCaptcha 站点密钥：** 您的 hCaptcha 站点密钥（从 hCaptcha 获取）。 |
    | `ANTIBOT_HCAPTCHA_SECRET`  |        | multisite | no   | **hCaptcha 密钥：** 您的 hCaptcha 密钥（从 hCaptcha 获取）。         |

=== "Turnstile"

    Turnstile 是一种现代、注重隐私的挑战机制，它利用 Cloudflare 的技术来检测和阻止自动化流量。它以一种无缝、后台的方式验证用户交互，为合法用户减少了摩擦，同时有效地阻止了机器人。

    要将 Turnstile 与 BunkerWeb 集成，请确保您从 [Cloudflare Turnstile](https://www.cloudflare.com/turnstile) 获取了必要的凭据。

    **配置设置：**

    | 设置                        | 默认值 | 上下文    | 多个 | 描述                                                                     |
    | --------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------ |
    | `USE_ANTIBOT`               | `no`   | multisite | no   | **启用 Antibot：** 设置为 `turnstile` 以启用 Turnstile 挑战。            |
    | `ANTIBOT_TURNSTILE_SITEKEY` |        | multisite | no   | **Turnstile 站点密钥：** 您的 Turnstile 站点密钥（从 Cloudflare 获取）。 |
    | `ANTIBOT_TURNSTILE_SECRET`  |        | multisite | no   | **Turnstile 密钥：** 您的 Turnstile 密钥（从 Cloudflare 获取）。         |

=== "mCaptcha"

    mCaptcha 是一种替代的 CAPTCHA 挑战机制，它通过呈现一个与其他 antibot 解决方案类似的交互式测试来验证用户的合法性。启用后，它会用 mCaptcha 提供的 CAPTCHA 来挑战用户，确保只有真正的用户才能绕过自动安全检查。

    mCaptcha 的设计考虑了隐私。它完全符合 GDPR，确保挑战过程中涉及的所有用户数据都遵守严格的数据保护标准。此外，mCaptcha 提供了自托管的灵活性，允许组织完全控制其数据和基础设施。这种自托管能力不仅增强了隐私，还优化了性能和定制，以适应特定的部署需求。

    要将 mCaptcha 与 BunkerWeb 集成，您必须从 [mCaptcha](https://mcaptcha.org/) 平台或您自己的提供商那里获取必要的凭据。这些凭据包括用于验证的站点密钥和密钥。

    **配置设置：**

    | 设置                       | 默认值                      | 上下文    | 多个 | 描述                                                                 |
    | -------------------------- | --------------------------- | --------- | ---- | -------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | no   | **启用 Antibot：** 设置为 `mcaptcha` 以启用 mCaptcha 挑战。          |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | no   | **mCaptcha 站点密钥：** 您的 mCaptcha 站点密钥（从 mCaptcha 获取）。 |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | no   | **mCaptcha 密钥：** 您的 mCaptcha 密钥（从 mCaptcha 获取）。         |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | no   | **mCaptcha 域：** 用于 mCaptcha 挑战的域。                           |

### 示例配置

=== "Cookie 挑战"

    启用 Cookie 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "JavaScript 挑战"

    启用 JavaScript 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Captcha 挑战"

    启用 Captcha 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    注意：上面的示例使用了数字 2-9 和所有字母，这是 CAPTCHA 挑战最常用的字符。您可以根据需要自定义字母表以包含特殊字符。

=== "reCAPTCHA 经典版"

    经典 reCAPTCHA（站点/密钥）的示例配置：

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

=== "reCAPTCHA (新)"

    新的基于 Google Cloud 的 reCAPTCHA（项目 ID + API 密钥）的示例配置：

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # 可选的指纹以改善企业评估
    # ANTIBOT_RECAPTCHA_JA3: "<ja3-fingerprint>"
    # ANTIBOT_RECAPTCHA_JA4: "<ja4-fingerprint>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "hCaptcha 挑战"

    启用 hCaptcha 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Turnstile 挑战"

    启用 Turnstile 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "mCaptcha 挑战"

    启用 mCaptcha 挑战的示例配置：

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

STREAM 支持 :x:

Auth Basic 插件提供 HTTP 基本认证来保护您的网站或特定资源。此功能通过要求用户在访问受保护内容之前输入用户名和密码来增加额外的安全层。这种类型的身份验证实现简单，并得到浏览器的广泛支持。

**工作原理：**

1.  当用户尝试访问您网站的受保护区域时，服务器会发送一个身份验证质询。
2.  浏览器会显示一个登录对话框，提示用户输入用户名和密码。
3.  用户输入他们的凭据，这些凭据将被发送到服务器。
4.  如果凭据有效，用户将被授予访问所请求内容的权限。
5.  如果凭据无效，将向用户提供一个错误消息，状态码为 401 Unauthorized。

### 如何使用

请按照以下步骤启用和配置 Auth Basic 身份验证：

1.  **启用该功能：** 在您的 BunkerWeb 配置中将 `USE_AUTH_BASIC` 设置为 `yes`。
2.  **选择保护范围：** 通过配置 `AUTH_BASIC_LOCATION` 设置，决定是保护整个网站还是仅保护特定 URL。
3.  **定义凭据：** 使用 `AUTH_BASIC_USER` 和 `AUTH_BASIC_PASSWORD` 设置至少设置一对用户名和密码。
4.  **自定义消息：** 可选地更改 `AUTH_BASIC_TEXT` 以在登录提示中显示自定义消息。

### 配置设置

| 设置                  | 默认值            | 上下文    | 多个 | 描述                                                                                                                                                            |
| --------------------- | ----------------- | --------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | 否   | **启用基本认证：** 设置为 `yes` 以启用基本身份验证。                                                                                                            |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | 否   | **保护范围：** 设置为 `sitewide` 以保护整个站点，或指定一个 URL 路径（例如 `/admin`）以仅保护特定区域。您还可以使用 Nginx 风格的修饰符 (`=`, `~`, `~*`, `^~`)。 |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | 是   | **用户名：** 身份验证所需的用户名。您可以定义多个用户名/密码对。                                                                                                |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | 是   | **密码：** 身份验证所需的密码。密码使用 scrypt 哈希以实现最大安全性。                                                                                           |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | 否   | **提示文本：** 显示给用户的身份验证提示中的消息。                                                                                                               |

!!! warning "安全注意事项"
    HTTP 基本认证以 Base64 编码（非加密）传输凭据。虽然在通过 HTTPS 使用时这是可以接受的，但在普通 HTTP 上不应被认为是安全的。使用基本身份验证时，请务必启用 SSL/TLS。

!!! tip "使用多个凭据"
    您可以为访问配置多个用户名/密码对。每个 `AUTH_BASIC_USER` 设置都应有一个对应的 `AUTH_BASIC_PASSWORD` 设置。

### 示例配置

=== "全站保护"

    要用一组凭据保护您的整个网站：

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "保护特定区域"

    仅保护特定路径，例如管理面板：

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "多个用户"

    为多个用户设置不同的凭据：

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # 第一个用户
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # 第二个用户
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # 第三个用户
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```

## Backup

STREAM 支持 :white_check_mark:

备份插件提供了一个自动备份解决方案来保护您的 BunkerWeb 数据。此功能通过根据您首选的时间表创建定期备份，确保您重要数据库的安全性和可用性。备份存储在指定位置，并且可以通过自动化流程和手动命令轻松管理。

**工作原理：**

1.  您的数据库会根据您设置的时间表（每日、每周或每月）自动备份。
2.  备份存储在您系统上的指定目录中。
3.  旧的备份会根据您的保留设置自动轮换。
4.  您可以随时手动创建备份、列出现有备份或从备份中恢复。
5.  在任何恢复操作之前，当前状态都会自动备份作为安全措施。

### 如何使用

请按照以下步骤配置和使用备份功能：

1.  **启用该功能：** 备份功能默认启用。如果需要，您可以使用 `USE_BACKUP` 设置来控制此功能。
2.  **配置备份计划：** 通过设置 `BACKUP_SCHEDULE` 参数选择备份的频率。
3.  **设置保留策略：** 使用 `BACKUP_ROTATION` 设置指定要保留的备份数量。
4.  **定义存储位置：** 使用 `BACKUP_DIRECTORY` 设置选择备份的存储位置。
5.  **使用 CLI 命令：** 需要时，使用 `bwcli plugin backup` 命令手动管理备份。

### 配置设置

| 设置               | 默认值                       | 上下文 | 多个 | 描述                                                                  |
| ------------------ | ---------------------------- | ------ | ---- | --------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | 全局   | 否   | **启用备份：** 设置为 `yes` 以启用自动备份。                          |
| `BACKUP_SCHEDULE`  | `daily`                      | 全局   | 否   | **备份频率：** 执行备份的频率。选项：`daily`、`weekly` 或 `monthly`。 |
| `BACKUP_ROTATION`  | `7`                          | 全局   | 否   | **备份保留：** 要保留的备份文件数量。超过此数量的旧备份将被自动删除。 |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | 全局   | 否   | **备份位置：** 备份文件将存储的目录。                                 |

### 命令行界面

备份插件提供了几个 CLI 命令来管理您的备份：

```bash
# 列出所有可用的备份
bwcli plugin backup list

# 创建一个手动备份
bwcli plugin backup save

# 在自定义位置创建一个备份
bwcli plugin backup save --directory /path/to/custom/location

# 从最近的备份恢复
bwcli plugin backup restore

# 从特定的备份文件恢复
bwcli plugin backup restore /path/to/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "安全第一"
    在任何恢复操作之前，备份插件会自动在临时位置创建您当前数据库状态的备份。如果您需要还原恢复操作，这提供了一个额外的保障。

!!! warning "数据库兼容性"
    备份插件支持 SQLite、MySQL/MariaDB 和 PostgreSQL 数据库。目前不支持 Oracle 数据库的备份和恢复操作。

### 示例配置

=== "每日备份，保留 7 天"

    默认配置，创建每日备份并保留最近的 7 个文件：

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "每周备份，延长保留期"

    用于频率较低但保留时间较长的备份的配置：

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "每月备份到自定义位置"

    用于每月备份并存储在自定义位置的配置：

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```

## Backup S3 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :white_check_mark:

Automatically backup your data to an S3 bucket

| 参数                          | 默认值  | 上下文 | 可重复 | 描述                                         |
| ----------------------------- | ------- | ------ | ------ | -------------------------------------------- |
| `USE_BACKUP_S3`               | `no`    | global | 否     | Enable or disable the S3 backup feature      |
| `BACKUP_S3_SCHEDULE`          | `daily` | global | 否     | The frequency of the backup                  |
| `BACKUP_S3_ROTATION`          | `7`     | global | 否     | The number of backups to keep                |
| `BACKUP_S3_ENDPOINT`          |         | global | 否     | The S3 endpoint                              |
| `BACKUP_S3_BUCKET`            |         | global | 否     | The S3 bucket                                |
| `BACKUP_S3_DIR`               |         | global | 否     | The S3 directory                             |
| `BACKUP_S3_REGION`            |         | global | 否     | The S3 region                                |
| `BACKUP_S3_ACCESS_KEY_ID`     |         | global | 否     | The S3 access key ID                         |
| `BACKUP_S3_ACCESS_KEY_SECRET` |         | global | 否     | The S3 access key secret                     |
| `BACKUP_S3_COMP_LEVEL`        | `6`     | global | 否     | The compression level of the backup zip file |

## Bad behavior

STREAM 支持 :white_check_mark:

不良行为插件通过自动检测并封禁在指定时间段内产生过多错误或“不良”HTTP 状态码的 IP 地址来保护您的网站。这有助于防御暴力破解攻击、网络爬虫、漏洞扫描器以及其他可能产生大量错误响应的恶意活动。

攻击者在探测或利用漏洞时，通常会产生“可疑”的 HTTP 状态码——这些代码是普通用户在给定时间范围内不太可能触发的。通过检测这种行为，BunkerWeb 可以自动封禁违规的 IP 地址，迫使攻击者使用新的 IP 地址才能继续尝试。

**工作原理：**

1.  该插件会监控您网站的 HTTP 响应。
2.  当访问者收到一个“不良”的 HTTP 状态码（例如 400、401、403、404 等）时，该 IP 地址的计数器会增加。
3.  如果一个 IP 地址在指定的时间段内超过了配置的不良状态码阈值，该 IP 将被自动封禁。
4.  根据您的配置，被封禁的 IP 可以在服务级别（仅针对特定站点）或全局级别（跨所有站点）被阻止。
5.  封禁会在配置的封禁持续时间后自动过期，或者如果配置为 `0` 则永久有效。

!!! success "主要优点"

      1. **自动保护：** 自动检测并阻止潜在的恶意客户端，无需人工干预。
      2. **可定制的规则：** 根据您的具体需求，微调构成“不良行为”的定义。
      3. **资源节约：** 防止恶意行为者通过重复的无效请求消耗服务器资源。
      4. **灵活的范围：** 选择封禁是仅适用于当前服务还是全局适用于所有服务。
      5. **封禁持续时间控制：** 设置临时封禁，在配置的持续时间后自动过期，或设置永久封禁，直到手动移除。

### 如何使用

请按照以下步骤配置和使用“不良行为”功能：

1.  **启用该功能：** “不良行为”功能默认启用。如果需要，您可以使用 `USE_BAD_BEHAVIOR` 设置来控制此功能。
2.  **配置状态码：** 使用 `BAD_BEHAVIOR_STATUS_CODES` 设置定义哪些 HTTP 状态码应被视为“不良”。
3.  **设置阈值：** 使用 `BAD_BEHAVIOR_THRESHOLD` 设置确定多少次“不良”响应会触发封禁。
4.  **配置时间段：** 使用 `BAD_BEHAVIOR_COUNT_TIME` 和 `BAD_BEHAVIOR_BAN_TIME` 设置指定计算不良响应的持续时间和封禁持续时间。
5.  **选择封禁范围：** 使用 `BAD_BEHAVIOR_BAN_SCOPE` 设置决定封禁是仅适用于当前服务还是全局适用于所有服务。当流量命中默认服务器（服务器名 `_`）时，封禁始终为全局，以便该 IP 在所有服务中被阻断。

!!! tip "流模式"
    在**流模式**下，只有 `444` 状态码被视为“不良”并会触发此行为。

### 配置设置

| 设置                        | 默认值                        | 上下文    | 多个 | 描述                                                                                                                               |
| --------------------------- | ----------------------------- | --------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | 否   | **启用不良行为检测：** 设置为 `yes` 以启用不良行为检测和封禁功能。                                                                 |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | 否   | **不良状态码：** 当返回给客户端时，将被计为“不良”行为的 HTTP 状态码列表。                                                          |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | 否   | **阈值：** 一个 IP 在计数周期内可以生成的“不良”状态码的数量，超过该数量将被封禁。                                                  |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | 否   | **计数周期：** 计算不良状态码以达到阈值的时间窗口（以秒为单位）。                                                                  |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | 否   | **封禁持续时间：** 一个 IP 超过阈值后将被封禁的时间（以秒为单位）。默认为 24 小时（86400 秒）。设置为 `0` 表示永不解封的永久封禁。 |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | 否   | **封禁范围：** 决定封禁是仅适用于当前服务 (`service`) 还是所有服务 (`global`)。命中默认服务器（`_`）时，封禁始终为全局。           |

!!! warning "误报"
    在设置阈值和计数时间时要小心。将这些值设置得太低可能会无意中封禁在浏览您网站时遇到错误的合法用户。

!!! tip "调整您的配置"
    从保守的设置开始（更高的阈值，更短的封禁时间），并根据您的具体需求和流量模式进行调整。监控您的日志以确保合法用户不会被错误地封禁。

### 示例配置

=== "默认配置"

    默认配置提供了一种适用于大多数网站的平衡方法：

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "严格配置"

    对于高安全性应用程序，您希望更积极地封禁潜在威胁：

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"  # 7 天
    BAD_BEHAVIOR_BAN_SCOPE: "global" # 在所有服务中封禁
    ```

=== "宽松配置"

    对于具有高合法流量且您希望避免误报的网站：

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"  # 仅计算未经授权、禁止和速率受限的请求
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"  # 1 小时
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "永久封禁配置"

    对于您希望检测到的攻击者被永久封禁，直到手动解封的情况：

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"  # 永久封禁（永不失效）
    BAD_BEHAVIOR_BAN_SCOPE: "global" # 在所有服务中封禁
    ```

## Blacklist

STREAM 支持 :warning:

黑名单插件通过根据各种客户端属性阻止访问来为您的网站提供强大的保护。此功能通过根据 IP 地址、网络、反向 DNS 条目、ASN、用户代理和特定的 URI 模式拒绝访问来防御已知的恶意实体、扫描器和可疑访问者。

**工作原理：**

1.  该插件会根据多个黑名单标准（IP 地址、网络、rDNS、ASN、用户代理或 URI 模式）检查传入的请求。
2.  黑名单可以直接在您的配置中指定，也可以从外部 URL 加载。
3.  如果访问者匹配任何黑名单规则（并且不匹配任何忽略规则），访问将被拒绝。
4.  黑名单会根据配置的 URL 定期自动更新。
5.  您可以根据您的特定安全需求自定义要检查和忽略的确切标准。

### 如何使用

请按照以下步骤配置和使用黑名单功能：

1.  **启用该功能：** 黑名单功能默认启用。如果需要，您可以使用 `USE_BLACKLIST` 设置来控制此功能。
2.  **配置阻止规则：** 定义应阻止的 IP、网络、rDNS 模式、ASN、用户代理或 URI。
3.  **设置忽略规则：** 指定应绕过黑名单检查的任何例外情况。
4.  **添加外部源：** 配置 URL 以自动下载和更新黑名单数据。
5.  **监控有效性：** 查看 [web UI](web-ui.md) 以查看有关被阻止请求的统计信息。

!!! info "流模式"
    当使用流模式时，只会执行 IP、rDNS 和 ASN 检查。

### 配置设置

**通用**

| 设置                        | 默认值                                                  | 上下文    | 多个 | 描述                                                          |
| --------------------------- | ------------------------------------------------------- | --------- | ---- | ------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | 否   | **启用黑名单：** 设置为 `yes` 以启用黑名单功能。              |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | 否   | **社区黑名单：** 选择预配置的社区维护的黑名单以包含在阻止中。 |

=== "社区黑名单"
    **这是做什么的：** 使您能够快速添加维护良好的、来自社区的黑名单，而无需手动配置 URL。

    `BLACKLIST_COMMUNITY_LISTS` 设置允许您从精选的黑名单源中进行选择。可用选项包括：

    | ID                                                                                                                           | 描述                                                                                                                                                                        | 来源                                                                                                                           |
    | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
    | `ip:laurent-minne-data-shield-aggressive`                                                                                    | Data-Shield IPv4 黑名单。DST = 欧洲                                                                                                                                         |
    | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt` |
    | `ip:danmeuk-tor-exit`                                                                                                        | Tor 出口节点 IP (dan.me.uk)                                                                                                                                                 | `https://www.dan.me.uk/torlist/?exit`                                                                                          |
    | `ua:mitchellkrogza-bad-user-agents`                                                                                          | Nginx 阻止不良机器人、垃圾邮件引荐来源、漏洞扫描器、用户代理、恶意软件、广告软件、勒索软件、恶意网站，具有反 DDOS、Wordpress 主题检测器阻止和针对重复违规者的 Fail2Ban Jail | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` |

    **配置：** 指定多个列表，以空格分隔。例如：
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "社区与手动配置"
        社区黑名单提供了一种方便的方式来开始使用经过验证的黑名单源。您可以将它们与手动 URL 配置一起使用，以实现最大的灵活性。

=== "IP 地址"
    **这是做什么的：** 根据访问者的 IP 地址或网络阻止访问。

    | 设置                       | 默认值                                | 上下文    | 多个 | 描述                                                                    |
    | -------------------------- | ------------------------------------- | --------- | ---- | ----------------------------------------------------------------------- |
    | `BLACKLIST_IP`             |                                       | multisite | 否   | **IP 黑名单：** 要阻止的 IP 地址或网络（CIDR 表示法）列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | 否   | **IP 忽略列表：** 应绕过 IP 黑名单检查的 IP 地址或网络列表。            |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | 否   | **IP 黑名单 URL：** 包含要阻止的 IP 地址或网络的 URL 列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | 否   | **IP 忽略列表 URL：** 包含要忽略的 IP 地址或网络的 URL 列表。           |

    默认的 `BLACKLIST_IP_URLS` 设置包含一个提供**已知 Tor 出口节点列表**的 URL。这是恶意流量的常见来源，对于许多网站来说是一个很好的起点。

=== "反向 DNS"
    **这是做什么的：** 根据访问者的反向域名阻止访问。这对于根据其组织域名阻止已知的扫描器和爬虫非常有用。

    | 设置                         | 默认值                  | 上下文    | 多个 | 描述                                                                     |
    | ---------------------------- | ----------------------- | --------- | ---- | ------------------------------------------------------------------------ |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | 否   | **rDNS 黑名单：** 要阻止的反向 DNS 后缀列表，以空格分隔。                |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | 否   | **仅限 rDNS 全局：** 当设置为 `yes` 时，仅对全局 IP 地址执行 rDNS 检查。 |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | 否   | **rDNS 忽略列表：** 应绕过 rDNS 黑名单检查的反向 DNS 后缀列表。          |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | 否   | **rDNS 黑名单 URL：** 包含要阻止的反向 DNS 后缀的 URL 列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | 否   | **rDNS 忽略列表 URL：** 包含要忽略的反向 DNS 后缀的 URL 列表。           |

    默认的 `BLACKLIST_RDNS` 设置包括常见的扫描器域名，如 **Shodan** 和 **Censys**。这些通常被安全研究人员和扫描器用来识别易受攻击的网站。

=== "ASN"
    **这是做什么的：** 阻止来自特定网络提供商的访问者。ASN 就像互联网的邮政编码——它们标识一个 IP 属于哪个提供商或组织。

    | 设置                        | 默认值 | 上下文    | 多个 | 描述                                                            |
    | --------------------------- | ------ | --------- | ---- | --------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |        | multisite | 否   | **ASN 黑名单：** 要阻止的自治系统号列表，以空格分隔。           |
    | `BLACKLIST_IGNORE_ASN`      |        | multisite | 否   | **ASN 忽略列表：** 应绕过 ASN 黑名单检查的 ASN 列表。           |
    | `BLACKLIST_ASN_URLS`        |        | multisite | 否   | **ASN 黑名单 URL：** 包含要阻止的 ASN 的 URL 列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_ASN_URLS` |        | multisite | 否   | **ASN 忽略列表 URL：** 包含要忽略的 ASN 的 URL 列表。           |

=== "用户代理"
    **这是做什么的：** 根据访问者声称使用的浏览器或工具来阻止访问。这对于诚实地表明自己身份的机器人（例如“ScannerBot”或“WebHarvestTool”）是有效的。

    | 设置                               | 默认值                                                                                                                         | 上下文    | 多个 | 描述                                                                           |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- | ------------------------------------------------------------------------------ |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | 否   | **用户代理黑名单：** 要阻止的用户代理模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | 否   | **用户代理忽略列表：** 应绕过用户代理黑名单检查的用户代理模式列表。            |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | 否   | **用户代理黑名单 URL：** 包含要阻止的用户代理模式的 URL 列表。                 |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | 否   | **用户代理忽略列表 URL：** 包含要忽略的用户代理模式的 URL 列表。               |

    默认的 `BLACKLIST_USER_AGENT_URLS` 设置包含一个提供**已知恶意用户代理列表**的 URL。这些通常被恶意机器人和扫描器用来识别易受攻击的网站。

=== "URI"
    **这是做什么的：** 阻止对您网站上特定 URL 的请求。这对于阻止尝试访问管理页面、登录表单或其他可能成为攻击目标的敏感区域非常有用。

    | 设置                        | 默认值 | 上下文    | 多个 | 描述                                                                    |
    | --------------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |        | multisite | 否   | **URI 黑名单：** 要阻止的 URI 模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_URI`      |        | multisite | 否   | **URI 忽略列表：** 应绕过 URI 黑名单检查的 URI 模式列表。               |
    | `BLACKLIST_URI_URLS`        |        | multisite | 否   | **URI 黑名单 URL：** 包含要阻止的 URI 模式的 URL 列表，以空格分隔。     |
    | `BLACKLIST_IGNORE_URI_URLS` |        | multisite | 否   | **URI 忽略列表 URL：** 包含要忽略的 URI 模式的 URL 列表。               |

!!! info "URL 格式支持"
    所有 `*_URLS` 设置都支持 HTTP/HTTPS URL 以及使用 `file:///` 前缀的本地文件路径。使用 `http://user:pass@url` 格式支持基本身份验证。

!!! tip "定期更新"
    来自 URL 的黑名单会每小时自动下载和更新，以确保您的保护措施始终能应对最新的威胁。

### 示例配置

=== "基本的 IP 和用户代理保护"

    一个简单的配置，使用社区黑名单阻止已知的 Tor 出口节点和常见的恶意用户代理：

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    或者，您可以使用手动 URL 配置：

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "带有自定义规则的高级保护"

    一个更全面的配置，带有自定义黑名单条目和例外情况：

    ```yaml
    USE_BLACKLIST: "yes"

    # 自定义黑名单条目
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # AWS 和 Amazon 的 ASN
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # 自定义忽略规则
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # 外部黑名单源
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "使用本地文件"

    使用本地文件作为黑名单的配置：

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///path/to/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///path/to/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///path/to/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///path/to/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///path/to/uri-blacklist.txt"
    ```

### 使用本地列表文件

Whitelist、Greylist 和 Blacklist 插件提供的 `*_URLS` 设置共用同一个下载器。当你引用 `file:///` URL 时：

- 路径会在 **scheduler** 容器内解析（Docker 部署通常为 `bunkerweb-scheduler`）。请将文件挂载到该容器，并确保 scheduler 用户拥有读取权限。
- 每个文件都是 UTF-8 编码的纯文本，每行一个条目。空行会被忽略，注释行必须以 `#` 或 `;` 开头。不支持 `//` 注释。
- 各类列表的条目要求：
  - **IP 列表** 接受 IPv4/IPv6 地址或 CIDR 网段（例如 `192.0.2.10` 或 `2001:db8::/48`）。
  - **rDNS 列表** 需要没有空格的后缀（例如 `.search.msn.com`），并会自动转换为小写。
  - **ASN 列表** 可以仅包含编号（`32934`），或带 `AS` 前缀的编号（`AS15169`）。
  - **User-Agent 列表** 视为 PCRE 模式，整行（包括空格）都会保留。请把注释放在独立行，避免被当成模式。
  - **URI 列表** 必须以 `/` 开头，可以使用 `^`、`$` 等 PCRE 标记。

符合格式的示例文件：

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Brotli

STREAM 支持 :x:

Brotli 插件使用 Brotli 算法实现对 HTTP 响应的高效压缩。此功能通过在将 Web 内容发送到客户端浏览器之前对其进行压缩，帮助减少带宽使用并缩短页面加载时间。

与其他压缩方法（如 gzip）相比，Brotli 通常能实现更高的压缩率，从而减小文件大小，加快内容交付速度。

**工作原理：**

1.  当客户端从您的网站请求内容时，BunkerWeb 会检查客户端是否支持 Brotli 压缩。
2.  如果支持，BunkerWeb 会在您配置的压缩级别下使用 Brotli 算法对响应进行压缩。
3.  压缩后的内容会连同指示 Brotli 压缩的适当标头一起发送给客户端。
4.  客户端的浏览器在向用户呈现内容之前会对其进行解压缩。
5.  带宽使用量和页面加载时间都得到了减少，从而改善了整体用户体验。

### 如何使用

请按照以下步骤配置和使用 Brotli 压缩功能：

1.  **启用该功能：** Brotli 功能默认禁用。通过将 `USE_BROTLI` 设置为 `yes` 来启用它。
2.  **配置 MIME 类型：** 使用 `BROTLI_TYPES` 设置指定应压缩的内容类型。
3.  **设置最小大小：** 使用 `BROTLI_MIN_LENGTH` 定义压缩的最小响应大小，以避免压缩过小的文件。
4.  **选择压缩级别：** 使用 `BROTLI_COMP_LEVEL` 选择您偏好的速度与压缩率之间的平衡。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，压缩会自动对符合条件的响应进行。

### 配置设置

| 设置                | 默认值                                                                                                                                                                                                                                                                                                                                                                                                                           | 上下文    | 多个 | 描述                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- | ---------------------------------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | 否   | **启用 Brotli：** 设置为 `yes` 以启用 Brotli 压缩。                                |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | 否   | **MIME 类型：** 将使用 Brotli 压缩的内容类型列表。                                 |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | 否   | **最小大小：** 应用 Brotli 压缩的最小响应大小（以字节为单位）。                    |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | 否   | **压缩级别：** 压缩级别从 0（不压缩）到 11（最大压缩）。较高的值会使用更多的 CPU。 |

!!! tip "优化压缩级别"
    默认的压缩级别 (6) 在压缩率和 CPU 使用率之间提供了良好的平衡。对于静态内容或服务器 CPU 资源充足的情况，可以考虑增加到 9-11 以获得最大压缩。对于动态内容或 CPU 资源有限的情况，您可能希望使用 4-5 以实现更快的压缩和合理的尺寸减小。

!!! info "浏览器支持"
    所有现代浏览器，包括 Chrome、Firefox、Edge、Safari 和 Opera，都支持 Brotli。旧版浏览器会自动接收未压缩的内容，以确保兼容性。

### 示例配置

=== "基本配置"

    一个使用默认设置启用 Brotli 的标准配置：

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "最大压缩"

    为实现最大压缩节省而优化的配置：

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "平衡性能"

    在压缩率和 CPU 使用率之间取得平衡的配置：

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```

## BunkerNet

STREAM 支持 :white_check_mark:

BunkerNet 插件通过 BunkerWeb 实例之间的集体威胁情报共享，创建了一个强大的恶意行为者防护网络。通过参与 BunkerNet，您的实例不仅受益于全球已知威胁数据库，同时也为其做出贡献，从而增强了整个 BunkerWeb 社区的安全性。

**工作原理：**

1.  您的 BunkerWeb 实例会自动向 BunkerNet API 注册，以获取一个唯一标识符。
2.  当您的实例检测并阻止了恶意 IP 地址或行为时，它会匿名地向 BunkerNet 报告该威胁。
3.  BunkerNet 聚合来自所有参与实例的威胁情报，并分发整合后的数据库。
4.  您的实例会定期从 BunkerNet 下载更新的已知威胁数据库。
5.  这种集体情报使您的实例能够主动阻止在其他 BunkerWeb 实例上表现出恶意行为的 IP 地址。

!!! success "主要优点"

      1. **集体防御：** 利用全球成千上万个其他 BunkerWeb 实例的安全发现。
      2. **主动防护：** 根据恶意行为者在别处的行为，在他们攻击您的网站之前就将其阻止。
      3. **社区贡献：** 通过分享关于攻击者的匿名威胁数据，帮助保护其他 BunkerWeb 用户。
      4. **零配置：** 开箱即用，带有合理的默认值，只需最少的设置。
      5. **注重隐私：** 只分享必要的威胁信息，不损害您或您用户的隐私。

### 如何使用

请按照以下步骤配置和使用 BunkerNet 功能：

1.  **启用该功能：** BunkerNet 功能默认启用。如果需要，您可以使用 `USE_BUNKERNET` 设置来控制此功能。
2.  **初始注册：** 首次启动时，您的实例将自动向 BunkerNet API 注册并收到一个唯一标识符。
3.  **自动更新：** 您的实例将按常规计划自动下载最新的威胁数据库。
4.  **自动报告：** 当您的实例阻止了一个恶意 IP 地址时，它会自动将此数据贡献给社区。
5.  **监控保护：** 查看 [web UI](web-ui.md) 以查看由 BunkerNet 情报阻止的威胁统计信息。

### 配置设置

| 设置               | 默认值                     | 上下文    | 多个 | 描述                                                                 |
| ------------------ | -------------------------- | --------- | ---- | -------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | 否   | **启用 BunkerNet：** 设置为 `yes` 以启用 BunkerNet 威胁情报共享。    |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | 否   | **BunkerNet 服务器：** 用于共享威胁情报的 BunkerNet API 服务器地址。 |

!!! tip "网络保护"
    当 BunkerNet 检测到某个 IP 地址在多个 BunkerWeb 实例中参与了恶意活动时，它会将该 IP 添加到集体黑名单中。这提供了一个主动的防御层，在威胁直接攻击您之前就保护您的网站。

!!! info "匿名报告"
    在向 BunkerNet 报告威胁信息时，您的实例只分享识别威胁所需的数据：IP 地址、阻止原因和最少的上下文数据。不会分享有关您的用户的个人信息或有关您网站的敏感详细信息。

### 示例配置

=== "默认配置（推荐）"

    默认配置使用官方 BunkerWeb API 服务器启用 BunkerNet：

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "禁用配置"

    如果您不想参与 BunkerNet 威胁情报网络：

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "自定义服务器配置"

    对于运行自己的 BunkerNet 服务器的组织（不常见）：

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

### CrowdSec 控制台集成

如果您还不熟悉 CrowdSec 控制台集成，[CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) 利用众包情报来对抗网络威胁。可以把它想象成“网络安全界的 Waze”——当一台服务器受到攻击时，全球其他系统都会收到警报，并受到保护，免受同一攻击者的侵害。您可以在[这里](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog)了解更多信息。

通过我们与 CrowdSec 的合作，您可以将您的 BunkerWeb 实例注册到您的 [CrowdSec 控制台](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration)。这意味着由 BunkerWeb 阻止的攻击将与由 CrowdSec 安全引擎阻止的攻击一起显示在您的 CrowdSec 控制台中，为您提供统一的威胁视图。

重要的是，此集成无需安装 CrowdSec（尽管我们强烈建议您使用 [BunkerWeb 的 CrowdSec 插件](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec)来进一步增强您的 Web 服务的安全性）。此外，您可以将您的 CrowdSec 安全引擎注册到同一个控制台帐户，以实现更大的协同作用。

**步骤 1：创建您的 CrowdSec 控制台帐户**

前往 [CrowdSec 控制台](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration)注册，如果您还没有帐户的话。完成后，记下在“安全引擎”下点击“添加安全引擎”后找到的注册密钥：

<figure markdown>
  ![概述](assets/img/crowdity1.png){ align=center }
  <figcaption>获取您的 Crowdsec 控制台注册密钥</figcaption>
</figure>

**步骤 2：获取您的 BunkerNet ID**

如果您想将您的 BunkerWeb 实例注册到您的 CrowdSec 控制台中，激活 BunkerNet 功能（默认启用）是强制性的。通过将 `USE_BUNKERNET` 设置为 `yes` 来启用它。

对于 Docker，使用以下命令获取您的 BunkerNet ID：

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

对于 Linux，使用：

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**步骤 3：使用面板注册您的实例**

一旦您有了您的 BunkerNet ID 和 CrowdSec 控制台注册密钥，请在[面板上订购免费产品“BunkerNet / CrowdSec”](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc)。如果您还没有帐户，可能会提示您创建一个。

您现在可以选择“BunkerNet / CrowdSec”服务并填写表格，粘贴您的 BunkerNet ID 和 CrowdSec 控制台注册密钥：

<figure markdown>
  ![概述](assets/img/crowdity2.png){ align=center }
  <figcaption>将您的 BunkerWeb 实例注册到 CrowdSec 控制台</figcaption>
</figure>

**步骤 4：在控制台上接受新的安全引擎**

然后，返回您的 CrowdSec 控制台并接受新的安全引擎：

<figure markdown>
  ![概述](assets/img/crowdity3.png){ align=center }
  <figcaption>接受注册到 CrowdSec 控制台</figcaption>
</figure>

**恭喜，您的 BunkerWeb 实例现已注册到您的 CrowdSec 控制台！**

专业提示：查看警报时，点击“列”选项并勾选“上下文”复选框，以访问 BunkerWeb 特定的数据。

<figure markdown>
  ![概述](assets/img/crowdity4.png){ align=center }
  <figcaption>在上下文列中显示的 BunkerWeb 数据</figcaption>
</figure>

## CORS

STREAM 支持 :x:

CORS 插件为您的网站启用跨源资源共享，允许从不同域受控地访问您的资源。此功能通过明确定义允许哪些源、方法和标头，帮助您安全地与受信任的第三方网站共享您的内容，同时维护安全性。

**工作原理：**

1.  当浏览器向您的网站发出跨源请求时，它首先会发送一个带有 `OPTIONS` 方法的预检请求。
2.  BunkerWeb 会根据您的配置检查请求的源是否被允许。
3.  如果允许，BunkerWeb 会响应适当的 CORS 标头，这些标头定义了请求站点可以执行的操作。
4.  对于不允许的源，请求可以被完全拒绝，也可以不带 CORS 标头地提供服务。
5.  可以配置其他跨源策略，例如 [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy)、[COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy) 和 [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy)，以进一步增强安全性。

### 如何使用

请按照以下步骤配置和使用 CORS 功能：

1.  **启用该功能：** CORS 功能默认禁用。将 `USE_CORS` 设置为 `yes` 以启用它。
2.  **配置允许的源：** 使用 `CORS_ALLOW_ORIGIN` 设置指定哪些域可以访问您的资源。
3.  **设置允许的方法：** 使用 `CORS_ALLOW_METHODS` 定义允许用于跨源请求的 HTTP 方法。
4.  **配置允许的标头：** 使用 `CORS_ALLOW_HEADERS` 指定可以在请求中使用的标头。
5.  **控制凭据：** 使用 `CORS_ALLOW_CREDENTIALS` 决定跨源请求是否可以包含凭据。

### 配置设置

| 设置                           | 默认值                                                                               | 上下文    | 多个 | 描述                                                                                             |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | ---- | ------------------------------------------------------------------------------------------------ |
| `USE_CORS`                     | `no`                                                                                 | multisite | 否   | **启用 CORS：** 设置为 `yes` 以启用跨源资源共享。                                                |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | 否   | **允许的来源：** 表示允许来源的 PCRE 正则表达式；使用 `*` 表示任何来源，或 `self` 表示仅限同源。 |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | 否   | **允许的方法：** 可在跨源请求中使用的 HTTP 方法。                                                |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | 否   | **允许的标头：** 可在跨源请求中使用的 HTTP 标头。                                                |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | 否   | **允许凭据：** 设置为 `yes` 以允许在 CORS 请求中使用凭据（cookie、HTTP 身份验证）。              |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | 否   | **公开的标头：** 浏览器允许从跨源响应中访问的 HTTP 标头。                                        |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | 否   | **跨源打开器策略：** 控制浏览上下文之间的通信。                                                  |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | 否   | **跨源嵌入器策略：** 控制文档是否可以加载来自其他来源的资源。                                    |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | 否   | **跨源资源策略：** 控制哪些网站可以嵌入您的资源。                                                |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | 否   | **预检缓存持续时间：** 浏览器应缓存预检响应的时间（以秒为单位）。                                |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | 否   | **拒绝未经授权的来源：** 当为 `yes` 时，来自未经授权来源的请求将被拒绝并返回错误代码。           |

!!! tip "优化预检请求"
    `CORS_MAX_AGE` 设置决定了浏览器缓存预检请求结果的时间。将其设置为一个较高的值（例如默认的 86400 秒/24 小时）可以减少预检请求的数量，从而提高频繁访问资源的性能。

!!! warning "安全注意事项"
    在将 `CORS_ALLOW_ORIGIN` 设置为 `*`（所有来源）或将 `CORS_ALLOW_CREDENTIALS` 设置为 `yes` 时要小心，因为如果管理不当，这些配置可能会引入安全风险。通常更安全的做法是明确列出受信任的来源，并限制允许的方法和标头。

### 示例配置

以下是 `CORS_ALLOW_ORIGIN` 设置的可能值及其行为的示例：

- **`*`**：允许来自所有来源的请求。
- **`self`**：自动允许来自与配置的 server_name 相同的来源的请求。
- **`^https://www\.example\.com$`**：仅允许来自 `https://www.example.com` 的请求。
- **`^https://.+\.example\.com$`**：允许来自以 `.example.com` 结尾的任何子域的请求。
- **`^https://(www\.example1\.com|www\.example2\.com)$`**：允许来自 `https://www.example1.com` 或 `https://www.example2.com` 的请求。
- **`^https?://www\.example\.com$`**：允许来自 `https://www.example.com` 和 `http://www.example.com` 的请求。

=== "基本配置"

    一个简单的配置，允许来自同一域的跨源请求：

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "self"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_DENY_REQUEST: "yes"
    ```

=== "公共 API 配置"

    需要从任何来源访问的公共 API 的配置：

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "*"
    CORS_ALLOW_METHODS: "GET, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, X-API-Key"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "3600"
    CORS_DENY_REQUEST: "no"
    ```

=== "多个受信任的域"

    使用单个 PCRE 正则表达式模式允许多个特定域的配置：

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

=== "子域通配符"

    使用 PCRE 正则表达式模式允许主域的所有子域的配置：

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://.*\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "多个域模式"

    使用交替允许多个域模式的请求的配置：

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(.*\\.example\\.com|.*\\.trusted-partner\\.org|api\\.third-party\\.net)$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Custom-Header"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

## Cache <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

Provides caching functionality at the reverse proxy level.

| 参数                        | 默认值                            | 上下文    | 可重复 | 描述                                                                           |
| --------------------------- | --------------------------------- | --------- | ------ | ------------------------------------------------------------------------------ |
| `CACHE_PATH`                |                                   | global    | 是     | Path and parameters for a cache.                                               |
| `CACHE_ZONE`                |                                   | multisite | 否     | Name of cache zone to use (specified in a CACHE_PATH setting).                 |
| `CACHE_HEADER`              | `X-Cache`                         | multisite | 否     | Add header about cache status.                                                 |
| `CACHE_BACKGROUND_UPDATE`   | `no`                              | multisite | 否     | Enable or disable background update of the cache.                              |
| `CACHE_BYPASS`              |                                   | multisite | 否     | List of variables to determine if the cache should be bypassed or not.         |
| `CACHE_NO_CACHE`            | `$http_pragma$http_authorization` | multisite | 否     | Disable caching if variables are set.                                          |
| `CACHE_KEY`                 | `$scheme$proxy_host$request_uri`  | multisite | 否     | Key used to identify cached elements.                                          |
| `CACHE_CONVERT_HEAD_TO_GET` | `yes`                             | multisite | 否     | Convert HEAD requests to GET when caching.                                     |
| `CACHE_LOCK`                | `no`                              | multisite | 否     | Lock concurrent requests when populating the cache.                            |
| `CACHE_LOCK_AGE`            | `5s`                              | multisite | 否     | Pass request to upstream if cache is locked for that time (possible cache).    |
| `CACHE_LOCK_TIMEOUT`        | `5s`                              | multisite | 否     | Pass request to upstream if cache is locked for that time (no cache).          |
| `CACHE_METHODS`             | `GET HEAD`                        | multisite | 否     | Only cache response if corresponding method is present.                        |
| `CACHE_MIN_USES`            | `1`                               | multisite | 否     | Number of requests before we put the corresponding response in cache.          |
| `CACHE_REVALIDATE`          | `no`                              | multisite | 否     | Revalidate expired items using conditional requests to upstream.               |
| `CACHE_USE_STALE`           | `off`                             | multisite | 否     | Determines the use of staled cache response (proxy_cache_use_stale directive). |
| `CACHE_VALID`               | `10m`                             | multisite | 是     | Defines default caching with optional status code.                             |

## Client cache

STREAM 支持 :x:

客户端缓存插件通过控制浏览器如何缓存静态内容来优化网站性能。它通过指示浏览器在本地存储和重用静态资产（例如图像、CSS 和 JavaScript 文件），而不是在每次页面访问时都请求它们，从而减少了带宽使用量，降低了服务器负载，并缩短了页面加载时间。

**工作原理：**

1.  启用后，BunkerWeb 会向静态文件的响应中添加 Cache-Control 标头。
2.  这些标头会告诉浏览器应在本地缓存内容多长时间。
3.  对于具有指定扩展名的文件（例如图像、CSS、JavaScript），BunkerWeb 会应用配置的缓存策略。
4.  可选的 ETag 支持提供了一个额外的验证机制，以确定缓存的内容是否仍然是新鲜的。
5.  当访问者返回您的网站时，他们的浏览器可以使用本地缓存的文件，而不是再次下载它们，从而缩短了页面加载时间。

### 如何使用

请按照以下步骤配置和使用客户端缓存功能：

1.  **启用该功能：** 客户端缓存功能默认禁用；将 `USE_CLIENT_CACHE` 设置为 `yes` 以启用它。
2.  **配置扩展名：** 使用 `CLIENT_CACHE_EXTENSIONS` 设置指定应缓存的文件类型。
3.  **设置缓存控制指令：** 使用 `CLIENT_CACHE_CONTROL` 设置自定义客户端应如何缓存内容。
4.  **配置 ETag 支持：** 使用 `CLIENT_CACHE_ETAG` 设置决定是否启用 ETag 来验证缓存新鲜度。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，缓存标头会自动应用于符合条件的响应。

### 配置设置

| 设置                      | 默认值                     | 上下文    | 多个 | 描述                                                                      |
| ------------------------- | -------------------------- | --------- | ---- | ------------------------------------------------------------------------- |
| `USE_CLIENT_CACHE`        | `no`                       | multisite | 否   | **启用客户端缓存：** 设置为 `yes` 以启用静态文件的客户端缓存。            |
| `CLIENT_CACHE_EXTENSIONS` | `jpg                       | jpeg      | png  | bmp                                                                       | ico | svg | tif | css | js | otf | ttf | eot | woff | woff2` | 全局 | 否 | **可缓存的扩展名：** 应由客户端缓存的文件扩展名列表（以管道符分隔）。 |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000` | multisite | 否   | **Cache-Control 标头：** 用于控制缓存行为的 Cache-Control HTTP 标头的值。 |
| `CLIENT_CACHE_ETAG`       | `yes`                      | multisite | 否   | **启用 ETags：** 设置为 `yes` 以发送静态资源的 HTTP ETag 标头。           |

!!! tip "优化缓存设置"
    对于频繁更新的内容，请考虑使用较短的 max-age 值。对于很少更改的内容（如带版本的 JavaScript 库或徽标），请使用较长的缓存时间。默认值 15552000 秒（180 天）适用于大多数静态资产。

!!! info "浏览器行为"
    不同的浏览器对缓存的实现略有不同，但所有现代浏览器都遵循标准的 Cache-Control 指令。ETags 提供了一个额外的验证机制，可以帮助浏览器确定缓存的内容是否仍然有效。

### 示例配置

=== "基本配置"

    一个简单的配置，为常见的静态资产启用缓存：

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 天
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "积极缓存"

    为实现最大缓存而优化的配置，适用于静态内容更新不频繁的网站：

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 年
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "混合内容策略"

    对于同时包含频繁更新和不频繁更新内容的网站，请考虑在您的应用程序中使用文件版本控制，并采用如下配置：

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 周
    CLIENT_CACHE_ETAG: "yes"
    ```

## Country

STREAM 支持 :white_check_mark:

国家/地区插件为您的网站启用地理封锁功能，允许您根据访问者的地理位置限制访问。此功能可帮助您遵守区域法规、防止通常与高风险地区相关的欺诈活动，并根据地理边界实施内容限制。

**工作原理：**

1.  当访问者访问您的网站时，BunkerWeb 会根据他们的 IP 地址确定他们的国家/地区。
2.  您的配置指定了白名单（允许的国家/地区）或黑名单（被阻止的国家/地区）。
3.  如果您设置了白名单，只有来自该列表中国家/地区的访问者才会被授予访问权限。
4.  如果您设置了黑名单，来自该列表中国家/地区的访问者将被拒绝访问。
5.  结果会被缓存，以提高来自同一 IP 地址的重复访问者的性能。

### 如何使用

请按照以下步骤配置和使用国家/地区功能：

1.  **定义您的策略：** 决定您是想使用白名单方法（仅允许特定国家/地区）还是黑名单方法（阻止特定国家/地区）。
2.  **配置国家/地区代码：** 将 ISO 3166-1 alpha-2 国家/地区代码（例如 US、GB、FR 等两位字母代码）添加到 `WHITELIST_COUNTRY` 或 `BLACKLIST_COUNTRY` 设置中。
3.  **应用设置：** 配置完成后，基于国家/地区的限制将适用于您网站的所有访问者。
4.  **监控有效性：** 查看 [web UI](web-ui.md) 以查看按国家/地区阻止的请求统计信息。

### 配置设置

| 设置                | 默认值 | 上下文    | 多个 | 描述                                                                                                    |
| ------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |        | multisite | 否   | **国家/地区白名单：** 以空格分隔的国家/地区代码（ISO 3166-1 alpha-2 格式）列表。只允许这些国家/地区。   |
| `BLACKLIST_COUNTRY` |        | multisite | 否   | **国家/地区黑名单：** 以空格分隔的国家/地区代码（ISO 3166-1 alpha-2 格式）列表。这些国家/地区将被阻止。 |

!!! tip "白名单与黑名单"
    选择最适合您需求的方法：

    - 当您想将访问限制在少数几个国家/地区时，请使用白名单。
    - 当您想阻止来自特定问题地区的访问，同时允许其他所有地区时，请使用黑名单。

!!! warning "优先规则"
    如果同时配置了白名单和黑名单，则白名单优先。这意味着系统首先检查一个国家/地区是否在白名单中；如果不在，无论黑名单配置如何，访问都将被拒绝。

!!! info "国家/地区检测"
    BunkerWeb 使用 [lite db-ip mmdb 数据库](https://db-ip.com/db/download/ip-to-country-lite)根据 IP 地址确定来源国家/地区。

### 示例配置

=== "仅白名单"

    仅允许来自美国、加拿大和英国的访问：

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "仅黑名单"

    阻止来自特定国家/地区的访问，同时允许所有其他国家/地区：

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "仅限欧盟访问"

    仅允许来自欧盟成员国的访问：

    ```yaml
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "高风险国家/地区被阻止"

    阻止来自通常与某些网络威胁相关的国家/地区的访问：

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```

## CrowdSec

STREAM 支持 :x:

<figure markdown>
  ![概述](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

CrowdSec 插件将 BunkerWeb 与 CrowdSec 安全引擎集成，为抵御各种网络威胁提供额外的保护层。此插件充当 [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) 拦截器，根据 CrowdSec API 的决策拒绝请求。

CrowdSec 是一种现代的开源安全引擎，它基于行为分析和社区的集体情报来检测和阻止恶意 IP 地址。您还可以配置[场景](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios)来根据可疑行为自动封禁 IP 地址，从而受益于一个众包的黑名单。

**工作原理：**

1.  CrowdSec 引擎会分析日志并检测您基础设施上的可疑活动。
2.  当检测到恶意活动时，CrowdSec 会创建一个决策来阻止违规的 IP 地址。
3.  BunkerWeb 作为拦截器，会向 CrowdSec 本地 API 查询有关传入请求的决策。
4.  如果客户端的 IP 地址有活动的阻止决策，BunkerWeb 会拒绝其访问受保护的服务。
5.  可选地，应用程序安全组件可以执行深度请求检查以增强安全性。

!!! success "主要优点"

      1. **社区驱动的安全：** 受益于整个 CrowdSec 用户社区共享的威胁情报。
      2. **行为分析：** 基于行为模式而不是签名来检测复杂的攻击。
      3. **轻量级集成：** 对您的 BunkerWeb 实例的性能影响最小。
      4. **多层次保护：** 结合边界防御（IP 阻止）和应用程序安全，实现深度保护。

### 前置条件

- CrowdSec 本地 API，BunkerWeb 可以访问（通常为运行在同一主机或同一 Docker 网络中的代理）。
- 访问 BunkerWeb 访问日志（默认路径 `/var/log/bunkerweb/access.log`），以便 CrowdSec 代理分析请求。
- 在 CrowdSec 主机上可使用 `cscli`，用于注册 BunkerWeb 的 bouncer 密钥。

### 集成流程

1. 准备 CrowdSec 代理，使其能够摄取 BunkerWeb 日志。
2. 配置 BunkerWeb，以便查询 CrowdSec 本地 API。
3. 通过 `/crowdsec/ping` API 或管理界面中的 CrowdSec 卡片验证连接。

以下各节将依次说明这些步骤。

### 第&nbsp;1&nbsp;步 – 准备 CrowdSec 摄取 BunkerWeb 日志

=== "Docker"
    **采集文件**

    您需要运行一个 CrowdSec 实例，并将其配置为解析 BunkerWeb 日志。请在采集文件中将 `type` 参数设置为专用的 `bunkerweb` 值（假设 BunkerWeb 日志按原样存储，没有附加数据）：

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    如果在 CrowdSec 容器内仍然看不到该集合，请运行 `docker exec -it <crowdsec-container> cscli hub update`，然后重启该容器（`docker restart <crowdsec-container>`），以加载新的资源。请将 `<crowdsec-container>` 替换为 CrowdSec 容器的实际名称。

    **应用程序安全组件（*可选*）**

    CrowdSec 还提供了一个[应用程序安全组件](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs)，可用于保护您的应用程序免受攻击。如果您想使用它，必须为 AppSec 组件创建另一个采集文件：

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    对于基于容器的集成，我们建议将 BunkerWeb 容器的日志重定向到 syslog 服务，以便 CrowdSec 可以轻松访问它们。这是一个 syslog-ng 的示例配置，它会将来自 BunkerWeb 的原始日志存储到本地的 `/var/log/bunkerweb.log` 文件中：

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

    这是您可以使用的 docker-compose 样板（不要忘记更新 bouncer 密钥）：

    ```yaml
    x-bw-env: &bw-env
      # 我们使用一个锚点来避免在两个服务中重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 确保设置正确的 IP 范围，以便调度器可以将配置发送到实例

    services:
      bunkerweb:
        # 这是将用于在调度器中识别实例的名称
        image: bunkerity/bunkerweb:1.6.7
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 用于 QUIC / HTTP3 支持
        environment:
          <<: *bw-env # 我们使用锚点来避免为所有服务重复相同的设置
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog # 将日志发送到 syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # syslog 服务的 IP 地址

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 确保设置正确的实例名称
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # 这是同一网络中 CrowdSec 容器 API 的地址
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # 如果您不想使用 AppSec 组件，请注释掉此行
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # 记得为 bouncer 设置一个更强的密钥
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # 我们设置了最大允许的数据包大小以避免大查询的问题
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # 记得为数据库设置一个更强的密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      crowdsec:
        image: crowdsecurity/crowdsec:v1.7.4 # 使用最新版本，但为了更好的稳定性和安全性，请始终固定版本
        volumes:
          - cs-data:/var/lib/crowdsec/data # 持久化 CrowdSec 数据
          - bw-logs:/var/log:ro # BunkerWeb 的日志，供 CrowdSec 解析
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # BunkerWeb 日志的采集文件
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # 如果您不想使用 AppSec 组件，请注释掉此行
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # 记得为 bouncer 设置一个更强的密钥
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # 如果您不想使用 AppSec 组件，请改用此行
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # 绑定到低端口
          - NET_BROADCAST  # 发送广播
          - NET_RAW  # 使用原始套接字
          - DAC_READ_SEARCH  # 绕过权限读取文件
          - DAC_OVERRIDE  # 覆盖文件权限
          - CHOWN  # 更改所有权
          - SYSLOG  # 写入系统日志
        volumes:
          - bw-logs:/var/log/bunkerweb # 用于存储日志的卷
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # syslog-ng 配置文件
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
            - subnet: 10.20.30.0/24 # 确保设置正确的 IP 范围，以便调度器可以将配置发送到实例
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Linux"

    您需要安装 CrowdSec 并将其配置为解析 BunkerWeb 日志。请按照[官方文档](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios)进行操作。

    要使 CrowdSec 能够解析 BunkerWeb 日志，请将以下行添加到位于 `/etc/crowdsec/acquis.yaml` 的采集文件中：

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    更新 CrowdSec hub 并安装 BunkerWeb 集合：

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    现在，使用 `cscli` 工具将您的自定义 bouncer 添加到 CrowdSec API：

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "API 密钥"
        请保留 `cscli` 命令生成的密钥；稍后您将需要它。

    然后重启 CrowdSec 服务：

    ```shell
    sudo systemctl restart crowdsec
    ```

    **应用程序安全组件（*可选*）**

    如果您想使用 AppSec 组件，您必须为其创建一个位于 `/etc/crowdsec/acquis.d/appsec.yaml` 的另一个采集文件：

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    您还需要安装 AppSec 组件的集合：

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    最后，重启 CrowdSec 服务：

    ```shell
    sudo systemctl restart crowdsec
    ```

    **设置**

    通过将以下设置添加到您的 BunkerWeb 配置文件来配置插件：

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<The key provided by cscli>
    # 如果您不想使用 AppSec 组件，请注释掉
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    最后，重新加载 BunkerWeb 服务：

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "All-in-one"

    BunkerWeb All-In-One (AIO) Docker 镜像完全集成了 CrowdSec。当使用内部 CrowdSec 代理时，您无需为 BunkerWeb 日志设置单独的 CrowdSec 实例或手动配置文件。

    请参阅[一体化 (AIO) 镜像集成文档](integrations.md#crowdsec-integration)。

### 第&nbsp;2&nbsp;步 – 配置 BunkerWeb 参数

应用以下环境变量（或通过调度器设置的值），让 BunkerWeb 实例能够与 CrowdSec 本地 API 通信。至少需要设置 `USE_CROWDSEC`、`CROWDSEC_API` 以及通过 `cscli bouncers add` 生成的有效密钥。

| 设置                        | 默认值                 | 上下文    | 多个 | 描述                                                                                                  |
| --------------------------- | ---------------------- | --------- | ---- | ----------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | 否   | **启用 CrowdSec：** 设置为 `yes` 以启用 CrowdSec 拦截器。                                             |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | 否   | **CrowdSec API URL：** CrowdSec 本地 API 服务的地址。                                                 |
| `CROWDSEC_API_KEY`          |                        | global    | 否   | **CrowdSec API 密钥：** 用于向 CrowdSec API 进行身份验证的 API 密钥，使用 `cscli bouncers add` 获取。 |
| `CROWDSEC_MODE`             | `live`                 | global    | 否   | **操作模式：** `live`（为每个请求查询 API）或 `stream`（定期缓存所有决策）。                          |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | 否   | **内部流量：** 设置为 `yes` 以根据 CrowdSec 决策检查内部流量。                                        |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | 否   | **请求超时：** 在实时模式下向 CrowdSec 本地 API 发出 HTTP 请求的超时时间（以毫秒为单位）。            |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | 否   | **排除的位置：** 从 CrowdSec 检查中排除的位置（URI）列表，以逗号分隔。                                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | 否   | **缓存过期时间：** 在实时模式下，IP 决策的缓存过期时间（以秒为单位）。                                |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | 否   | **更新频率：** 在流模式下，从 CrowdSec API 拉取新的/过期的决策的频率（以秒为单位）。                  |

#### 应用程序安全组件设置

| 设置                              | 默认值        | 上下文 | 多个 | 描述                                                                              |
| --------------------------------- | ------------- | ------ | ---- | --------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |               | global | 否   | **AppSec URL：** CrowdSec 应用程序安全组件的 URL。留空以禁用 AppSec。             |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | global | 否   | **失败操作：** 当 AppSec 返回错误时要采取的操作。可以是 `passthrough` 或 `deny`。 |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | global | 否   | **连接超时：** 连接到 AppSec 组件的超时时间（以毫秒为单位）。                     |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | global | 否   | **发送超时：** 向 AppSec 组件发送数据的超时时间（以毫秒为单位）。                 |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | global | 否   | **处理超时：** 在 AppSec 组件中处理请求的超时时间（以毫秒为单位）。               |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | global | 否   | **始终发送：** 设置为 `yes` 以始终将请求发送到 AppSec，即使存在 IP 级别的决策。   |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | global | 否   | **SSL 验证：** 设置为 `yes` 以验证 AppSec 组件的 SSL 证书。                       |

!!! info "关于操作模式" - **实时模式**会为每个传入的请求查询 CrowdSec API，提供实时的保护，但会增加延迟。- **流模式**会定期从 CrowdSec API 下载所有决策并将其本地缓存，从而减少延迟，但应用新决策会略有延迟。

### 示例配置

=== "基本配置"

    这是一个当 CrowdSec 在同一台主机上运行时的一个简单配置：

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "live"
    ```

=== "带有 AppSec 的高级配置"

    一个更全面的配置，包括应用程序安全组件：

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # AppSec 配置
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

### 第&nbsp;3&nbsp;步 – 验证集成

- 在调度器日志中查找 `CrowdSec configuration successfully generated` 和 `CrowdSec bouncer denied request` 条目，以确认插件处于活动状态。
- 在 CrowdSec 端监控 `cscli metrics show` 或 CrowdSec Console，确保 BunkerWeb 的决策按预期显示。
- 在 BunkerWeb UI 中打开 CrowdSec 插件页面查看集成状态。

## Custom Pages <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

Tweak BunkerWeb error/antibot/default pages with custom HTML.

| 参数                             | 默认值 | 上下文    | 可重复 | 描述                                                                                                               |
| -------------------------------- | ------ | --------- | ------ | ------------------------------------------------------------------------------------------------------------------ |
| `CUSTOM_ERROR_PAGE`              |        | multisite | 否     | Full path of the custom error page (must be readable by the scheduler) (Can be a lua template).                    |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |        | global    | 否     | Full path of the custom default server page (must be readable by the scheduler) (Can be a lua template).           |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |        | multisite | 否     | Full path of the custom antibot captcha page (must be readable by the scheduler) (Can be a lua template).          |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |        | multisite | 否     | Full path of the custom antibot javascript check page (must be readable by the scheduler) (Can be a lua template). |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |        | multisite | 否     | Full path of the custom antibot recaptcha page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |        | multisite | 否     | Full path of the custom antibot hcaptcha page (must be readable by the scheduler) (Can be a lua template).         |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |        | multisite | 否     | Full path of the custom antibot turnstile page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |        | multisite | 否     | Full path of the custom antibot mcaptcha page (must be readable by the scheduler) (Can be a lua template).         |

## Custom SSL certificate

STREAM 支持 :white_check_mark:

自定义 SSL 证书插件允许您在 BunkerWeb 中使用您自己的 SSL/TLS 证书，而不是自动生成的证书。如果您拥有来自受信任的证书颁发机构 (CA) 的现有证书、需要使用具有特定配置的证书，或者希望在整个基础设施中保持一致的证书管理，此功能特别有用。

**工作原理：**

1.  您通过指定文件路径或以 base64 编码或纯文本 PEM 格式提供数据的方式，向 BunkerWeb 提供您的证书和私钥文件。
2.  BunkerWeb 会验证您的证书和密钥，以确保它们的格式正确且可用。
3.  建立安全连接时，BunkerWeb 会提供您的自定义证书，而不是自动生成的证书。
4.  BunkerWeb 会自动监控您的证书的有效性，并在其即将到期时显示警告。
5.  您可以完全控制证书管理，允许您使用来自您偏好的任何颁发机构的证书。

!!! info "自动证书监控"
    当您通过将 `USE_CUSTOM_SSL` 设置为 `yes` 来启用自定义 SSL/TLS 时，BunkerWeb 会自动监控 `CUSTOM_SSL_CERT` 中指定的自定义证书。它会每天检查更改，并在检测到任何修改时重新加载 NGINX，确保始终使用最新的证书。

### 如何使用

请按照以下步骤配置和使用自定义 SSL 证书功能：

1.  **启用该功能：** 将 `USE_CUSTOM_SSL` 设置为 `yes` 以启用自定义证书支持。
2.  **选择一种方法：** 决定是通过文件路径还是以 base64 编码/纯文本数据提供证书，并使用 `CUSTOM_SSL_CERT_PRIORITY` 设置优先级。
3.  **提供证书文件：** 如果使用文件路径，请指定您的证书和私钥文件的位置。
4.  **或者提供证书数据：** 如果使用数据，请以 base64 编码的字符串或纯文本 PEM 格式提供您的证书和密钥。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，BunkerWeb 会自动将您的自定义证书用于所有 HTTPS 连接。

!!! tip "流模式配置"
    对于流模式，您必须配置 `LISTEN_STREAM_PORT_SSL` 设置以指定 SSL/TLS 监听端口。此步骤对于在流模式下正常运行至关重要。

### 配置设置

| 设置                       | 默认值 | 上下文    | 多个 | 描述                                                                                        |
| -------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`   | multisite | 否   | **启用自定义 SSL：** 设置为 `yes` 以使用您自己的证书而不是自动生成的证书。                  |
| `CUSTOM_SSL_CERT_PRIORITY` | `file` | multisite | 否   | **证书优先级：** 选择优先使用文件路径中的证书还是 base64 数据中的证书（`file` 或 `data`）。 |
| `CUSTOM_SSL_CERT`          |        | multisite | 否   | **证书路径：** 您的 SSL 证书或证书捆绑包文件的完整路径。                                    |
| `CUSTOM_SSL_KEY`           |        | multisite | 否   | **私钥路径：** 您的 SSL 私钥文件的完整路径。                                                |
| `CUSTOM_SSL_CERT_DATA`     |        | multisite | 否   | **证书数据：** 以 base64 格式编码或以纯文本 PEM 格式表示的您的证书。                        |
| `CUSTOM_SSL_KEY_DATA`      |        | multisite | 否   | **私钥数据：** 以 base64 格式编码或以纯文本 PEM 格式表示的您的私钥。                        |

!!! warning "安全注意事项"
    使用自定义证书时，请确保您的私钥得到妥善保护并具有适当的权限。文件必须可由 BunkerWeb 调度器读取。

!!! tip "证书格式"
    BunkerWeb 需要 PEM 格式的证书。如果您的证书是其他格式，您可能需要先进行转换。

!!! info "证书链"
    如果您的证书包含一个链（中间证书），您应该按正确的顺序提供完整的证书链，首先是您的证书，然后是任何中间证书。

### 示例配置

=== "使用文件路径"

    一个使用磁盘上的证书和密钥文件的配置：

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "使用 Base64 数据"

    一个使用 base64 编码的证书和密钥数据的配置：

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```

=== "使用纯文本 PEM 数据"

    一个使用 PEM 格式的纯文本证书和密钥数据的配置：

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

=== "回退配置"

    一个优先使用文件，但如果文件不可用则回退到 base64 数据的配置：

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```

## DNSBL

STREAM 支持 :white_check_mark:

DNSBL（域名系统黑名单）插件通过对照外部 DNSBL 服务器检查客户端 IP 地址，为您的网站提供针对已知恶意 IP 地址的保护。此功能通过利用社区维护的有问题的 IP 地址列表，帮助保护您的网站免受垃圾邮件、僵尸网络和各种类型的网络威胁。

**工作原理：**

1.  当客户端连接到您的网站时，BunkerWeb 会使用 DNS 协议查询您选择的 DNSBL 服务器。
2.  通过向每个 DNSBL 服务器发送带有客户端 IP 地址的反向 DNS 查询来执行检查。
3.  如果任何 DNSBL 服务器确认客户端的 IP 地址被列为恶意，BunkerWeb 将自动封禁该客户端，防止潜在威胁到达您的应用程序。
4.  结果会被缓存，以提高来自同一 IP 地址的重复访问者的性能。
5.  使用异步查询高效地执行查找，以最大限度地减少对页面加载时间的影响。

### 如何使用

请按照以下步骤配置和使用 DNSBL 功能：

1.  **启用该功能：** DNSBL 功能默认禁用。将 `USE_DNSBL` 设置为 `yes` 以启用它。
2.  **配置 DNSBL 服务器：** 将您要使用的 DNSBL 服务的域名添加到 `DNSBL_LIST` 设置中。
3.  **应用设置：** 配置完成后，BunkerWeb 将自动对照指定的 DNSBL 服务器检查传入的连接。
4.  **监控有效性：** 查看 [web UI](web-ui.md) 以查看因 DNSBL 检查而被阻止的请求的统计信息。

### 配置设置

**通用**

| 设置         | 默认值                                              | 上下文    | 多个 | 描述                                                      |
| ------------ | --------------------------------------------------- | --------- | ---- | --------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | 否   | 启用 DNSBL：设置为 `yes` 以启用对传入连接的 DNSBL 检查。  |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | 否   | DNSBL 服务器：要检查的 DNSBL 服务器域名列表，以空格分隔。 |

**忽略列表**

| 设置                   | 默认值 | 上下文    | 多个 | 描述                                                                          |
| ---------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``     | multisite | 是   | 以空格分隔的 IP/CIDR，用于跳过 DNSBL 检查（白名单）。                         |
| `DNSBL_IGNORE_IP_URLS` | ``     | multisite | 是   | 以空格分隔的 URL，提供要跳过的 IP/CIDR。支持 `http(s)://` 和 `file://` 方案。 |

!!! tip "选择 DNSBL 服务器"
    选择信誉良好的 DNSBL 提供商以最大限度地减少误报。默认列表包括适合大多数网站的成熟服务：

    -   **bl.blocklist.de：** 列出被检测到攻击其他服务器的 IP。
    -   **sbl.spamhaus.org：** 专注于垃圾邮件源和其他恶意活动。
    -   **xbl.spamhaus.org：** 针对受感染的系统，例如被入侵的机器或开放代理。

!!! info "DNSBL 的工作原理"
    DNSBL 服务器通过响应特殊格式的 DNS 查询来工作。当 BunkerWeb 检查一个 IP 地址时，它会反转该 IP 并附加 DNSBL 域名。如果生成的 DNS 查询返回“成功”响应，则该 IP 被视为已列入黑名单。

!!! warning "性能考虑"
    虽然 BunkerWeb 优化了 DNSBL 查找的性能，但添加大量 DNSBL 服务器可能会影响响应时间。从几个信誉良好的 DNSBL 服务器开始，并在添加更多服务器之前监控性能。

### 示例配置

=== "基本配置"

    一个使用默认 DNSBL 服务器的简单配置：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "最小配置"

    一个专注于最可靠的 DNSBL 服务的最小配置：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    此配置仅使用：

    -   **zen.spamhaus.org**：Spamhaus 的组合列表通常被认为是独立的解决方案，因为它覆盖范围广，准确性高。它在一个查询中结合了 SBL、XBL 和 PBL 列表，使其高效而全面。

=== "排除受信任的 IP"

    您可以使用静态值和/或远程文件从 DNSBL 检查中排除特定的客户端：

    -   `DNSBL_IGNORE_IP`：添加以空格分隔的 IP 和 CIDR 范围。示例：`192.0.2.10 203.0.113.0/24 2001:db8::/32`。
    -   `DNSBL_IGNORE_IP_URLS`：提供 URL，其内容每行列出一个 IP/CIDR。以 `#` 或 `;` 开头的注释将被忽略。重复的条目将被去重。

    当传入的客户端 IP 匹配忽略列表时，BunkerWeb 会跳过 DNSBL 查找并将结果缓存为“ok”，以便后续请求更快。

=== "使用远程 URL"

    `dnsbl-download` 作业每小时下载并缓存忽略的 IP：

    -   协议：`https://`、`http://` 和本地 `file://` 路径。
    -   带校验和的每个 URL 缓存可防止冗余下载（1 小时宽限期）。
    -   每个服务的合并文件：`/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`。
    -   在启动时加载并与 `DNSBL_IGNORE_IP` 合并。

    结合静态和 URL 源的示例：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://example.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "使用本地文件"

    使用 `file://` URL 从本地文件加载忽略的 IP：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```

## Database

STREAM 支持 :white_check_mark:

数据库插件通过启用配置数据、日志和其他基本信息的集中存储和管理，为 BunkerWeb 提供了强大的数据库集成。

这个核心组件支持多种数据库引擎，包括 SQLite、PostgreSQL、MySQL/MariaDB 和 Oracle，让您可以选择最适合您的环境和需求的数据库解决方案。

**工作原理：**

1.  BunkerWeb 使用 SQLAlchemy 格式提供的 URI 连接到您配置的数据库。
2.  关键配置数据、运行时信息和作业日志都安全地存储在数据库中。
3.  自动维护流程通过管理数据增长和清理多余记录来优化您的数据库。
4.  对于高可用性场景，您可以配置一个只读数据库 URI，它既可以作为故障转移，也可以作为分流读取操作的方法。
5.  数据库操作会根据您指定的日志级别进行记录，为数据库交互提供适当的可见性。

### 如何使用

请按照以下步骤配置和使用数据库功能：

1.  **选择一个数据库引擎：** 根据您的需求，从 SQLite（默认）、PostgreSQL、MySQL/MariaDB 或 Oracle 中选择。
2.  **配置数据库 URI：** 使用 SQLAlchemy 格式设置 `DATABASE_URI` 以连接到您的主数据库。
3.  **可选的只读数据库：** 对于高可用性设置，配置一个 `DATABASE_URI_READONLY` 作为后备或用于读取操作。

### 配置设置

| 设置                            | 默认值                                    | 上下文 | 多个 | 描述                                                                                       |
| ------------------------------- | ----------------------------------------- | ------ | ---- | ------------------------------------------------------------------------------------------ |
| `DATABASE_URI`                  | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global | 否   | **数据库 URI：** SQLAlchemy 格式的主数据库连接字符串。                                     |
| `DATABASE_URI_READONLY`         |                                           | global | 否   | **只读数据库 URI：** 用于只读操作或在主数据库宕机时作为故障转移的可选数据库。              |
| `DATABASE_LOG_LEVEL`            | `warning`                                 | global | 否   | **日志级别：** 数据库日志的详细程度。选项：`debug`、`info`、`warn`、`warning` 或 `error`。 |
| `DATABASE_MAX_JOBS_RUNS`        | `10000`                                   | global | 否   | **最大作业运行次数：** 在自动清理之前，数据库中保留的作业执行记录的最大数量。              |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                                      | global | 否   | **会话保留：** UI 用户会话在自动清理前允许存在的最大天数。                                 |

!!! tip "数据库选择" - **SQLite**（默认）：由于其简单和基于文件的特性，非常适合单节点部署或测试环境。- **PostgreSQL**：由于其健壮性和并发支持，推荐用于具有多个 BunkerWeb 实例的生产环境。- **MySQL/MariaDB**：是 PostgreSQL 的一个很好的替代品，具有类似的生产级功能。- **Oracle**：适用于 Oracle 已经是标准数据库平台的企业环境。

!!! info "SQLAlchemy URI 格式"
    数据库 URI 遵循 SQLAlchemy 格式：

    -   SQLite: `sqlite:////path/to/database.sqlite3`
    -   PostgreSQL: `postgresql://username:password@hostname:port/database`
    -   MySQL/MariaDB: `mysql://username:password@hostname:port/database` 或 `mariadb://username:password@hostname:port/database`
    -   Oracle: `oracle://username:password@hostname:port/database`

!!! warning "数据库维护"
    该插件会自动运行每日维护作业：

- **清理多余的作业运行记录：** 根据 `DATABASE_MAX_JOBS_RUNS` 限制清除超出的历史。
- **清理过期的 UI 会话：** 删除超过 `DATABASE_MAX_SESSION_AGE_DAYS` 的 UI 用户会话。

这些作业可以防止数据库无限增长，同时保留有价值的运行历史。

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

Provides a simpler way to fix false positives in reports.

## Errors

STREAM 支持 :x:

错误插件为您的网站提供了可定制的错误处理，让您可以配置 HTTP 错误响应如何向用户显示。此功能通过呈现用户友好、带有品牌标识的错误页面，在错误场景中增强了用户体验，而不是显示默认的服务器错误页面，后者对访问者来说可能显得技术性且令人困惑。

**工作原理：**

1.  当客户端遇到 HTTP 错误（例如，400、404 或 500）时，BunkerWeb 会拦截错误响应。
2.  BunkerWeb 会显示一个自定义的、专业设计的错误页面，而不是显示默认的错误页面。
3.  错误页面可以通过您的配置完全定制，允许您为特定的错误代码指定自定义页面。**自定义错误页面文件必须放置在由 `ROOT_FOLDER` 设置定义的目录中（请参阅杂项插件文档）。**
    - 默认情况下，`ROOT_FOLDER` 是 `/var/www/html/{server_name}`（其中 `{server_name}` 会被实际的服务器名称替换）。
    - 在多站点模式下，每个站点都可以有自己的 `ROOT_FOLDER`，因此自定义错误页面必须放置在每个站点的相应目录中。
4.  默认的错误页面提供了清晰的解释，帮助用户了解出了什么问题以及他们接下来可以做什么。

### 如何使用

请按照以下步骤配置和使用错误功能：

1.  **定义自定义错误页面：** 使用 `ERRORS` 设置指定哪些 HTTP 错误代码应使用自定义错误页面。自定义错误页面文件必须位于为该站点指定的 `ROOT_FOLDER` 设置的文件夹中。在多站点模式下，这意味着每个站点/服务器都可以有自己的自定义错误页面文件夹。
2.  **配置您的错误页面：** 对于每个错误代码，您可以使用默认的 BunkerWeb 错误页面或提供您自己的自定义 HTML 页面（放置在相应的 `ROOT_FOLDER` 中）。
3.  **设置拦截的错误代码：** 使用 `INTERCEPTED_ERROR_CODES` 设置选择哪些错误代码应始终由 BunkerWeb 处理。
4.  **让 BunkerWeb 处理其余部分：** 配置完成后，错误处理会自动对所有指定的错误代码进行。

### 配置设置

| 设置                      | 默认值                                            | 上下文    | 多个 | 描述                                                                                                     |
| ------------------------- | ------------------------------------------------- | --------- | ---- | -------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | multisite | 否   | **自定义错误页面：** 使用 `ERROR_CODE=/path/to/file.html` 的格式将特定的错误代码映射到自定义 HTML 文件。 |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | 否   | **拦截的错误：** 当未指定自定义页面时，BunkerWeb 应使用其默认错误页面处理的 HTTP 错误代码列表。          |

!!! tip "错误页面设计"
    默认的 BunkerWeb 错误页面旨在提供信息、用户友好且外观专业。它们包括：

    -   清晰的错误描述
    -   关于可能导致错误原因的信息
    -   建议用户解决问题的操作
    -   帮助用户了解问题是出在客户端还是服务器端的视觉指示器

!!! info "错误类型"
    错误代码按类型分类：

    -   **4xx 错误（客户端）：** 这些表示客户端请求存在问题，例如试图访问不存在的页面或缺少适当的身份验证。
    -   **5xx 错误（服务器端）：** 这些表示服务器无法满足有效请求，例如内部服务器错误或暂时不可用。

### 示例配置

=== "默认错误处理"

    让 BunkerWeb 使用其默认的错误页面处理常见的错误代码：

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "自定义错误页面"

    为特定的错误代码使用自定义错误页面：

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "选择性错误处理"

    仅使用 BunkerWeb 处理特定的错误代码：

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```

## Greylist

STREAM 支持 :warning:

Greylist 插件提供了一种灵活的安全方法，允许访问者访问，同时仍然保持必要的安全功能。

与传统的[黑名单](#blacklist)/[白名单](#whitelist)方法——完全阻止或允许访问——不同，灰名单通过授予某些访问者访问权限，同时仍然对他们进行安全检查，创造了一个中间地带。

**工作原理：**

1.  您定义了要被列入灰名单的访问者的标准（_IP 地址、网络、rDNS、ASN、用户代理或 URI 模式_）。
2.  当访问者匹配这些标准中的任何一个时，他们将被授予访问您网站的权限，而其他安全功能仍然有效。
3.  如果访问者不匹配任何灰名单标准，他们的访问将被拒绝。
4.  灰名单数据可以定期从外部来源自动更新。

### 如何使用

请按照以下步骤配置和使用灰名单功能：

1.  **启用该功能：** 灰名单功能默认禁用。将 `USE_GREYLIST` 设置为 `yes` 以启用它。
2.  **配置灰名单规则：** 定义哪些 IP、网络、rDNS 模式、ASN、用户代理或 URI 应被列入灰名单。
3.  **添加外部源：** 可选地，配置用于自动下载和更新灰名单数据的 URL。
4.  **监控访问：** 查看 [web UI](web-ui.md) 以查看哪些访问者被允许或拒绝。

!!! tip "访问控制行为"
    当使用 `USE_GREYLIST` 设置为 `yes` 启用灰名单功能时：

    1.  **灰名单中的访问者：** 允许访问，但仍会受到所有安全检查。
    2.  **非灰名单中的访问者：** 完全拒绝访问。

!!! info "流模式"
    当使用流模式时，只会执行 IP、rDNS 和 ASN 检查。

### 配置设置

**通用**

| 设置           | 默认值 | 上下文    | 多个 | 描述                                         |
| -------------- | ------ | --------- | ---- | -------------------------------------------- |
| `USE_GREYLIST` | `no`   | multisite | 否   | **启用灰名单：** 设置为 `yes` 以启用灰名单。 |

=== "IP 地址"
    **这是做什么的：** 根据访问者的 IP 地址或网络将访问者列入灰名单。这些访问者可以获得访问权限，但仍会受到安全检查。

    | 设置               | 默认值 | 上下文    | 多个 | 描述                                                                          |
    | ------------------ | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |        | multisite | 否   | **IP 灰名单：** 要列入灰名单的 IP 地址或网络（CIDR 表示法）列表，以空格分隔。 |
    | `GREYLIST_IP_URLS` |        | multisite | 否   | **IP 灰名单 URL：** 包含要列入灰名单的 IP 地址或网络的 URL 列表，以空格分隔。 |

=== "反向 DNS"
    **这是做什么的：** 根据访问者的域名（反向）将访问者列入灰名单。对于允许来自特定组织或网络的访问者有条件地访问非常有用。

    | 设置                   | 默认值 | 上下文    | 多个 | 描述                                                                           |
    | ---------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------ |
    | `GREYLIST_RDNS`        |        | multisite | 否   | **rDNS 灰名单：** 要列入灰名单的反向 DNS 后缀列表，以空格分隔。                |
    | `GREYLIST_RDNS_GLOBAL` | `yes`  | multisite | 否   | **仅限 rDNS 全局：** 当设置为 `yes` 时，仅对全局 IP 地址执行 rDNS 灰名单检查。 |
    | `GREYLIST_RDNS_URLS`   |        | multisite | 否   | **rDNS 灰名单 URL：** 包含要列入灰名单的反向 DNS 后缀的 URL 列表，以空格分隔。 |

=== "ASN"
    **这是做什么的：** 使用自治系统号将来自特定网络提供商的访问者列入灰名单。ASN 标识一个 IP 属于哪个提供商或组织。

    | 设置                | 默认值 | 上下文    | 多个 | 描述                                                                  |
    | ------------------- | ------ | --------- | ---- | --------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |        | multisite | 否   | **ASN 灰名单：** 要列入灰名单的自治系统号列表，以空格分隔。           |
    | `GREYLIST_ASN_URLS` |        | multisite | 否   | **ASN 灰名单 URL：** 包含要列入灰名单的 ASN 的 URL 列表，以空格分隔。 |

=== "用户代理"
    **这是做什么的：** 根据访问者声称使用的浏览器或工具将访问者列入灰名单。这允许对特定工具进行受控访问，同时保持安全检查。

    | 设置                       | 默认值 | 上下文    | 多个 | 描述                                                                                 |
    | -------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------ |
    | `GREYLIST_USER_AGENT`      |        | multisite | 否   | **用户代理灰名单：** 要列入灰名单的用户代理模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `GREYLIST_USER_AGENT_URLS` |        | multisite | 否   | **用户代理灰名单 URL：** 包含要列入灰名单的用户代理模式的 URL 列表。                 |

=== "URI"
    **这是做什么的：** 将对您网站上特定 URL 的请求列入灰名单。这允许有条件地访问某些端点，同时保持安全检查。

    | 设置                | 默认值 | 上下文    | 多个 | 描述                                                                          |
    | ------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |        | multisite | 否   | **URI 灰名单：** 要列入灰名单的 URI 模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `GREYLIST_URI_URLS` |        | multisite | 否   | **URI 灰名单 URL：** 包含要列入灰名单的 URI 模式的 URL 列表，以空格分隔。     |

!!! info "URL 格式支持"
    所有 `*_URLS` 设置都支持 HTTP/HTTPS URL 以及使用 `file:///` 前缀的本地文件路径。使用 `http://user:pass@url` 格式支持基本身份验证。

!!! tip "定期更新"
    来自 URL 的灰名单会每小时自动下载和更新，以确保您的保护始终与最新的受信任来源保持同步。

### 示例配置

=== "基本配置"

    一个简单的配置，将灰名单应用于公司的内部网络和爬虫：

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "高级配置"

    一个更全面的配置，具有多个灰名单标准：

    ```yaml
    USE_GREYLIST: "yes"

    # 公司资产和批准的爬虫
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # 公司和合作伙伴的 ASN
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # 外部受信任的来源
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "使用本地文件"

    使用本地文件作为灰名单的配置：

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///path/to/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///path/to/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///path/to/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///path/to/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///path/to/uri-greylist.txt"
    ```

=== "选择性 API 访问"

    允许访问特定 API 端点的配置：

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # 外部合作伙伴网络
    ```

### 使用本地列表文件

Whitelist、Greylist 和 Blacklist 插件提供的 `*_URLS` 设置共用同一个下载器。当你引用 `file:///` URL 时：

- 路径会在 **scheduler** 容器内解析（Docker 部署通常为 `bunkerweb-scheduler`）。请将文件挂载到该容器，并确保 scheduler 用户拥有读取权限。
- 每个文件都是 UTF-8 编码的纯文本，每行一个条目。空行会被忽略，注释行必须以 `#` 或 `;` 开头。不支持 `//` 注释。
- 各类列表的条目要求：
  - **IP 列表** 接受 IPv4/IPv6 地址或 CIDR 网段（例如 `192.0.2.10` 或 `2001:db8::/48`）。
  - **rDNS 列表** 需要没有空格的后缀（例如 `.search.msn.com`），并会自动转换为小写。
  - **ASN 列表** 可以仅包含编号（`32934`），或带 `AS` 前缀的编号（`AS15169`）。
  - **User-Agent 列表** 视为 PCRE 模式，整行（包括空格）都会保留。请把注释放在独立行，避免被当成模式。
  - **URI 列表** 必须以 `/` 开头，可以使用 `^`、`$` 等 PCRE 标记。

符合格式的示例文件：

```text
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Gzip

STREAM 支持 :x:

GZIP 插件通过使用 GZIP 算法压缩 HTTP 响应来增强网站性能。此功能通过在将 Web 内容发送到客户端浏览器之前对其进行压缩，减少了带宽使用并缩短了页面加载时间，从而实现了更快的交付和更好的用户体验。

### 工作原理

1.  当客户端从您的网站请求内容时，BunkerWeb 会检查客户端是否支持 GZIP 压缩。
2.  如果支持，BunkerWeb 会在您配置的压缩级别下使用 GZIP 算法对响应进行压缩。
3.  压缩后的内容会连同指示 GZIP 压缩的适当标头一起发送给客户端。
4.  客户端的浏览器在呈现内容之前会对其进行解压缩。
5.  带宽使用量和页面加载时间都得到了减少，从而增强了网站的整体性能和用户体验。

### 如何使用

请按照以下步骤配置和使用 GZIP 压缩功能：

1.  **启用该功能：** GZIP 功能默认禁用。通过将 `USE_GZIP` 设置为 `yes` 来启用它。
2.  **配置 MIME 类型：** 使用 `GZIP_TYPES` 设置指定应压缩的内容类型。
3.  **设置最小大小：** 使用 `GZIP_MIN_LENGTH` 设置定义压缩所需的最小响应大小，以避免压缩小文件。
4.  **选择一个压缩级别：** 使用 `GZIP_COMP_LEVEL` 设置在速度和压缩率之间选择您偏好的平衡。
5.  **配置代理请求：** 使用 `GZIP_PROXIED` 设置指定应压缩哪些代理请求。

### 配置设置

| 设置              | 默认值                                                                                                                                                                                                                                                                                                                                                                                                                           | 上下文    | 多个 | 描述                                                                                |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- | ----------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | 否   | **启用 GZIP：** 设置为 `yes` 以启用 GZIP 压缩。                                     |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | 否   | **MIME 类型：** 将使用 GZIP 压缩的内容类型列表。                                    |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | 否   | **最小大小：** 应用 GZIP 压缩的最小响应大小（以字节为单位）。                       |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | 否   | **压缩级别：** 压缩级别从 1（最小压缩）到 9（最大压缩）。较高的值会使用更多的 CPU。 |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | 否   | **代理请求：** 根据响应标头指定应压缩哪些代理请求。                                 |

!!! tip "优化压缩级别"
    默认的压缩级别 (5) 在压缩率和 CPU 使用率之间提供了良好的平衡。对于静态内容或服务器 CPU 资源充足的情况，可以考虑增加到 7-9 以获得最大压缩。对于动态内容或 CPU 资源有限的情况，您可能希望使用 1-3 以实现更快的压缩和合理的尺寸减小。

!!! info "浏览器支持"
    所有现代浏览器都支持 GZIP，并且多年来一直是 HTTP 响应的标准压缩方法，确保了在设备和浏览器之间具有出色的兼容性。

!!! warning "压缩与 CPU 使用率"
    虽然 GZIP 压缩减少了带宽并缩短了加载时间，但更高的压缩级别会消耗更多的 CPU 资源。对于高流量的网站，请在压缩效率和服务器性能之间找到适当的平衡。

### 示例配置

=== "基本配置"

    一个使用默认设置启用 GZIP 的标准配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "最大压缩"

    为实现最大压缩节省而优化的配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "平衡性能"

    在压缩率和 CPU 使用率之间取得平衡的配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "代理内容焦点"

    专注于正确处理代理内容压缩的配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```

## HTML injection

STREAM 支持 :x:

HTML 注入插件允许您无缝地将自定义 HTML 代码添加到您网站页面的 `</body>` 或 `</head>` 结束标签之前。此功能对于添加分析脚本、跟踪像素、自定义 JavaScript、CSS 样式或其他第三方集成非常有用，而无需修改您网站的源代码。

**工作原理：**

1.  当您的网站提供页面服务时，BunkerWeb 会检查 HTML 响应。
2.  如果您配置了 body 注入，BunkerWeb 会在 `</body>` 结束标签之前插入您的自定义 HTML 代码。
3.  如果您配置了 head 注入，BunkerWeb 会在 `</head>` 结束标签之前插入您的自定义 HTML 代码。
4.  此插入操作会自动应用于您网站提供的所有 HTML 页面。
5.  这使您无需修改应用程序代码即可添加脚本、样式或其他元素。

### 如何使用

请按照以下步骤配置和使用 HTML 注入功能：

1.  **准备您的自定义 HTML：** 决定要注入到页面中的 HTML 代码。
2.  **选择注入位置：** 确定您需要在 `<head>` 部分、`<body>` 部分还是两者都注入代码。
3.  **配置设置：** 将您的自定义 HTML 添加到适当的设置中 (`INJECT_HEAD` 和/或 `INJECT_BODY`)。
4.  **让 BunkerWeb 处理其余部分：** 配置完成后，HTML 将自动注入到所有提供的 HTML 页面中。

### 配置设置

| 设置          | 默认值 | 上下文    | 多选 | 描述                                                       |
| ------------- | ------ | --------- | ---- | ---------------------------------------------------------- |
| `INJECT_HEAD` |        | multisite | 否   | **头部 HTML 代码：** 在 `</head>` 标签前注入的 HTML 代码。 |
| `INJECT_BODY` |        | multisite | 否   | **主体 HTML 代码：** 在 `</body>` 标签前注入的 HTML 代码。 |

!!! tip "最佳实践" - 出于性能考虑，请将 JavaScript 文件放在 body 的末尾，以防止渲染阻塞。- 将 CSS 和关键的 JavaScript 放在 head 部分，以避免出现无样式内容的闪烁。- 请谨慎处理可能破坏您网站功能的注入内容。

!!! info "常见用例" - 添加分析脚本（如 Google Analytics, Matomo）- 集成聊天小部件或客户支持工具 - 为营销活动添加跟踪像素 - 添加自定义 CSS 样式或 JavaScript 功能 - 无需修改应用程序代码即可引入第三方库

### 配置示例

=== "谷歌分析"

    将谷歌分析跟踪添加到您的网站：

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "自定义样式"

    向您的网站添加自定义 CSS 样式：

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "多个集成"

    同时添加自定义样式和 JavaScript：

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Cookie 同意横幅"

    添加一个简单的 Cookie 同意横幅：

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">本网站使用 Cookie 以确保您获得最佳体验。 <button onclick=\"acceptCookies()\">接受</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```

## Headers

STREAM 支持 :x:

请求头在 HTTP 安全中扮演着至关重要的角色。请求头插件提供了对标准和自定义 HTTP 请求头的强大管理功能——增强了安全性和功能性。它动态地应用安全措施，例如 [HSTS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security)、[CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy)（包括报告模式）和自定义请求头注入，同时防止信息泄露。

**工作原理**

1.  当客户端从您的网站请求内容时，BunkerWeb 会处理响应头。
2.  安全头会根据您的配置进行应用。
3.  可以添加自定义头来为客户端提供额外的信息或功能。
4.  可能会泄露服务器信息的不需要的头会自动被移除。
5.  Cookie 会根据您的设置被修改以包含适当的安全标志。
6.  需要时，可以选择性地保留来自上游服务器的头。

### 如何使用

请按照以下步骤配置和使用请求头功能：

1.  **配置安全头：** 为常见的请求头设置值。
2.  **添加自定义头：** 使用 `CUSTOM_HEADER` 设置定义任何自定义请求头。
3.  **移除不需要的头：** 使用 `REMOVE_HEADERS` 确保可能会暴露服务器细节的请求头被剥离。
4.  **设置 Cookie 安全：** 通过配置 `COOKIE_FLAGS` 并将 `COOKIE_AUTO_SECURE_FLAG` 设置为 `yes` 来启用强大的 Cookie 安全，以便在 HTTPS 连接上自动添加 Secure 标志。
5.  **保留上游头：** 使用 `KEEP_UPSTREAM_HEADERS` 指定要保留的上游请求头。
6.  **利用条件性头应用：** 如果您希望在不中断的情况下测试策略，请通过 `CONTENT_SECURITY_POLICY_REPORT_ONLY` 启用 [CSP 仅报告](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only)模式。

### 配置指南

=== "安全头"

    **概述**

    安全头强制执行安全通信，限制资源加载，并防止诸如点击劫持和注入等攻击。正确配置的头为您的网站创建了一个强大的防御层。

    !!! success "安全头的好处"
        - **HSTS：** 确保所有连接都已加密，防止协议降级攻击。
        - **CSP：** 防止恶意脚本执行，降低 XSS 攻击的风险。
        - **X-Frame-Options：** 通过控制 iframe 嵌入来阻止点击劫持尝试。
        - **Referrer Policy：** 通过 referrer 头限制敏感信息的泄露。

    | 设置                                  | 默认值                                                                                              | 上下文    | 多个 | 描述                                                                              |
    | ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | ---- | --------------------------------------------------------------------------------- |
    | `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | 否   | **HSTS：** 强制执行安全的 HTTPS 连接，降低中间人攻击的风险。                      |
    | `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | 否   | **CSP：** 将资源加载限制在受信任的来源，减轻跨站脚本和数据注入攻击。              |
    | `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | 否   | **CSP 报告模式：** 报告违规行为而不阻止内容，有助于在测试安全策略的同时捕获日志。 |
    | `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | 否   | **X-Frame-Options：** 通过控制您的网站是否可以被框架化来防止点击劫持。            |
    | `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | 否   | **X-Content-Type-Options：** 防止浏览器进行 MIME 嗅探，防止路过式下载攻击。       |
    | `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | 否   | **X-DNS-Prefetch-Control：** 调节 DNS 预取以减少无意的网络请求并增强隐私。        |
    | `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | 否   | **Referrer Policy：** 控制发送的引荐来源信息的数量，保护用户隐私。                |
    | `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | 否   | **Permissions Policy：** 限制浏览器功能访问，减少潜在的攻击向量。                 |
    | `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | 否   | **保留标头：** 保留选定的上游标头，在保持安全性的同时帮助旧版集成。               |

    !!! tip "最佳实践"
        -   定期审查和更新您的安全标头，以与不断发展的安全标准保持一致。
        -   使用像 [Mozilla Observatory](https://observatory.mozilla.org/) 这样的工具来验证您的标头配置。
        -   在强制执行 CSP 之前，在 `Report-Only` 模式下进行测试，以避免破坏功能。

=== "Cookie 设置"

    **概述**

    正确的 cookie 设置通过防止劫持、固定和跨站脚本攻击来确保安全的用户会话。安全的 cookie 在 HTTPS 上维护会话完整性，并增强整体用户数据保护。

    !!! success "安全 Cookie 的好处"
        - **HttpOnly 标志：** 防止客户端脚本访问 cookie，减轻 XSS 风险。
        - **SameSite 标志：** 通过限制跨源 cookie 的使用来减少 CSRF 攻击。
        - **Secure 标志：** 确保 cookie 仅通过加密的 HTTPS 连接传输。

    | 设置                      | 默认值                    | 上下文    | 多个 | 描述                                                                                                      |
    | ------------------------- | ------------------------- | --------- | ---- | --------------------------------------------------------------------------------------------------------- |
    | `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | 是   | **Cookie 标志：** 自动添加安全标志，如 HttpOnly 和 SameSite，保护 cookie 免受客户端脚本访问和 CSRF 攻击。 |
    | `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | 否   | **自动安全标志：** 通过自动附加 Secure 标志，确保 cookie 仅通过安全的 HTTPS 连接发送。                    |

    !!! tip "最佳实践"
        -   对敏感 cookie 使用 `SameSite=Strict` 以防止跨源访问。
        -   定期审计您的 cookie 设置，以确保符合安全和隐私法规。
        -   避免在生产环境中设置没有 Secure 标志的 cookie。

=== "自定义头"

    **概述**

    自定义标头允许您添加特定的 HTTP 标头以满足应用程序或性能要求。它们提供了灵活性，但必须仔细配置以避免暴露敏感的服务器详细信息。

    !!! success "自定义标头的好处"
        -   通过删除可能泄露服务器详细信息的不必要标头来增强安全性。
        -   添加特定于应用程序的标头以改进功能或调试。

    | 设置             | 默认值                                                                               | 上下文    | 多个 | 描述                                                                                                         |
    | ---------------- | ------------------------------------------------------------------------------------ | --------- | ---- | ------------------------------------------------------------------------------------------------------------ |
    | `CUSTOM_HEADER`  |                                                                                      | multisite | 是   | **自定义标头：** 提供了以 `HeaderName: HeaderValue` 格式添加用户定义的标头的方法，用于专门的安全或性能增强。 |
    | `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | 否   | **删除标头：** 指定要删除的标头，降低暴露内部服务器详细信息和已知漏洞的几率。                                |

    !!! warning "安全注意事项"
        -   避免通过自定义标头暴露敏感信息。
        -   定期审查和更新自定义标头，以与您的应用程序的要求保持一致。

    !!! tip "最佳实践"
        -   使用 `REMOVE_HEADERS` 去除像 `Server` 和 `X-Powered-By` 这样的标头，以减少指纹识别风险。
        -   在将自定义标头部署到生产环境之前，在暂存环境中进行测试。

### 示例配置

=== "基本安全头"

    一个带有基本安全头的标准配置：

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "增强的 Cookie 安全性"

    具有强大 cookie 安全设置的配置：

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "API 的自定义头"

    一个带有自定义头的 API 服务配置：

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "内容安全策略 - 报告模式"

    用于在不破坏功能的情况下测试 CSP 的配置：

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```

## Let's Encrypt

STREAM 支持 :white_check_mark:

Let's Encrypt 插件通过自动化创建、续订和配置来自 Let's Encrypt 的免费证书，简化了 SSL/TLS 证书管理。此功能可为您的网站启用安全的 HTTPS 连接，无需手动管理证书的复杂性，从而降低成本和管理开销。

**工作原理：**

1.  启用后，BunkerWeb 会自动检测为您的网站配置的域名。
2.  BunkerWeb 从 Let's Encrypt 的证书颁发机构请求免费的 SSL/TLS 证书。
3.  通过 HTTP 验证（证明您控制网站）或 DNS 验证（证明您控制域名的 DNS）来验证域名所有权。
4.  证书会自动为您的域名安装和配置。
5.  BunkerWeb 会在证书到期前在后台处理续订事宜，确保 HTTPS 的持续可用性。
6.  整个过程完全自动化，初次设置后几乎无需干预。

!!! info "先决条件"
    要使用此功能，请确保为每个域名配置了正确的 DNS **A 记录**，指向 BunkerWeb 可访问的公共 IP 地址。没有正确的 DNS 配置，域名验证过程将失败。

### 如何使用

请按照以下步骤配置和使用 Let's Encrypt 功能：

1.  **启用该功能：** 将 `AUTO_LETS_ENCRYPT` 设置为 `yes` 以启用自动证书颁发和续订。
2.  **提供联系电子邮件（建议填写）：** 使用 `EMAIL_LETS_ENCRYPT` 设置输入您的电子邮件地址，以便 Let's Encrypt 在证书即将过期时提醒您。如果留空，BunkerWeb 会在没有地址的情况下注册（使用 Certbot 的 `--register-unsafely-without-email` 选项），但您将不会收到任何提醒或恢复邮件。
3.  **选择验证类型：** 使用 `LETS_ENCRYPT_CHALLENGE` 设置选择 `http` 或 `dns` 验证。
4.  **配置 DNS 提供商：** 如果使用 DNS 验证，请指定您的 DNS 提供商和凭据。
5.  **选择证书配置文件：** 使用 `LETS_ENCRYPT_PROFILE` 设置选择您偏好的证书配置文件（classic、tlsserver 或 shortlived）。
6.  **让 BunkerWeb 处理其余部分：** 配置完成后，证书将根据需要自动颁发、安装和续订。

!!! tip "证书配置文件"
    Let's Encrypt 为不同的用例提供了不同的证书配置文件：- **classic**：通用证书，有效期为 90 天（默认）- **tlsserver**：针对 TLS 服务器身份验证进行了优化，有效期为 90 天，有效负载更小 - **shortlived**：增强安全性，有效期为 7 天，适用于自动化环境 - **custom**：如果您的 ACME 服务器支持不同的配置文件，请使用 `LETS_ENCRYPT_CUSTOM_PROFILE` 进行设置。

!!! info "配置文件可用性"
    请注意，`tlsserver` 和 `shortlived` 配置文件目前可能并非在所有环境或所有 ACME 客户端中都可用。`classic` 配置文件具有最广泛的兼容性，推荐给大多数用户。如果所选的配置文件不可用，系统将自动回退到 `classic` 配置文件。

### 配置设置

| 设置                                        | 默认值    | 上下文    | 多选 | 描述                                                                                                                                                                               |
| ------------------------------------------- | --------- | --------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | 否   | **启用 Let's Encrypt：** 设置为 `yes` 以启用自动证书颁发和续订。                                                                                                                   |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | 否   | **传递 Let's Encrypt 请求：** 设置为 `yes` 以将 Let's Encrypt 请求传递给 Web 服务器。当 BunkerWeb 位于处理 SSL 的另一个反向代理后面时，此功能很有用。                              |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | 否   | **联系电子邮件：** 用于 Let's Encrypt 到期提醒的电子邮件地址。只有在接受不接收任何警报或恢复邮件的情况下才可留空（此时 Certbot 会使用 `--register-unsafely-without-email` 注册）。 |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | 否   | **验证类型：** 用于验证域名所有权的方法。选项：`http` 或 `dns`。                                                                                                                   |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | 否   | **DNS 提供商：** 使用 DNS 验证时，要使用的 DNS 提供商（例如 cloudflare、route53、digitalocean）。                                                                                  |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | 否   | **DNS 传播：** 等待 DNS 传播的时间（秒）。如果未提供值，则使用提供商的默认传播时间。                                                                                               |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | 是   | **凭证项：** 用于 DNS 提供商身份验证的配置项（例如 `cloudflare_api_token 123456`）。值可以是原始文本、base64 编码或 JSON 对象。                                                    |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | 否   | **自动解码 Base64 DNS 凭据：** 启用后自动解码 base64 编码的 DNS 提供商凭据（`rfc2136` 提供商除外）。如果凭据故意为 base64，请设置为 `no`。                                         |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | 否   | **通配符证书：** 设置为 `yes` 时，为所有域名创建通配符证书。仅适用于 DNS 验证。                                                                                                    |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | 否   | **使用测试环境：** 设置为 `yes` 时，使用 Let's Encrypt 的测试环境进行测试。测试环境的速率限制较高，但生成的证书不受浏览器信任。                                                    |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | 否   | **清除旧证书：** 设置为 `yes` 时，在续订期间删除不再需要的旧证书。                                                                                                                 |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | 否   | **证书配置文件：** 选择要使用的证书配置文件。选项：`classic`（通用）、`tlsserver`（针对 TLS 服务器优化）或 `shortlived`（7 天证书）。                                              |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | 否   | **自定义证书配置文件：** 如果您的 ACME 服务器支持非标准配置文件，请输入自定义证书配置文件。如果设置了此项，它将覆盖 `LETS_ENCRYPT_PROFILE`。                                       |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | 否   | **最大重试次数：** 证书生成失败时重试的次数。设置为 `0` 以禁用重试。用于处理临时网络问题或 API 速率限制。                                                                          |

!!! info "信息和行为"
    - `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` 设置是一个多选设置，可用于为 DNS 提供商设置多个项目。这些项目将保存为缓存文件，Certbot 将从中读取凭据。
    - 如果未提供 `LETS_ENCRYPT_DNS_PROPAGATION` 设置，则使用提供商的默认传播时间。
    - 只要您从外部打开 `80/tcp` 端口，使用 `http` 验证的完全 Let's Encrypt 自动化就可以在流模式下工作。使用 `LISTEN_STREAM_PORT_SSL` 设置来选择您的侦听 SSL/TLS 端口。
    - 如果 `LETS_ENCRYPT_PASSTHROUGH` 设置为 `yes`，BunkerWeb 将不会自行处理 ACME 验证请求，而是将它们传递给后端 Web 服务器。这在 BunkerWeb 作为反向代理位于已配置为处理 Let's Encrypt 验证的另一台服务器前面的场景中很有用。

!!! tip "HTTP 与 DNS 验证"
    **HTTP 验证** 更容易设置，并且适用于大多数网站：

    - 要求您的网站在端口 80 上可公开访问
    - 由 BunkerWeb 自动配置
    - 不能用于通配符证书

    **DNS 验证** 提供更大的灵活性，并且是通配符证书所必需的：

    - 即使您的网站无法公开访问也能正常工作
    - 需要 DNS 提供商的 API 凭据
    - 通配符证书（例如 *.example.com）所必需
    - 在端口 80 被阻止或不可用时很有用

!!! warning "通配符证书"
    通配符证书仅适用于 DNS 验证。如果要使用它们，必须将 `USE_LETS_ENCRYPT_WILDCARD` 设置为 `yes` 并正确配置您的 DNS 提供商凭据。

!!! warning "速率限制"
    Let's Encrypt 对证书颁发施加速率限制。在测试配置时，通过将 `USE_LETS_ENCRYPT_STAGING` 设置为 `yes` 来使用测试环境，以避免达到生产环境的速率限制。测试证书不受浏览器信任，但对于验证您的设置很有用。

### 支持的 DNS 提供商

Let's Encrypt 插件支持广泛的 DNS 提供商进行 DNS 验证。每个提供商都需要使用 `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` 设置提供特定的凭据。

| 提供商            | 描述             | 强制性设置                                                                                                   | 可选设置                                                                                                                                                                                                                                                     | 文档                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                              | [文档](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | `api_token` 或 `email` 和 `api_key`                                                                          |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                              | [文档](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                              | [文档](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                              | [文档](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                              | [文档](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (默认: `600`)                                                                                                                                                                                                                                          | [文档](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (默认: `service_account`)<br>`auth_uri` (默认: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (默认: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (默认: `https://www.googleapis.com/oauth2/v1/certs`) | [文档](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (默认: `https://api.hosting.ionos.com`)                                                                                                                                                                                                           | [文档](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (默认: `ovh-eu`)                                                                                                                                                                                                                                  | [文档](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                              | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)            |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (默认: `53`)<br>`algorithm` (默认: `HMAC-SHA512`)<br>`sign_query` (默认: `false`)                                                                                                                                                                     | [文档](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                              | [文档](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |

### 配置示例

=== "基本 HTTP 验证"

    使用 HTTP 验证为单个域进行简单配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "使用通配符的 Cloudflare DNS"

    使用 Cloudflare DNS 为通配符证书进行配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token YOUR_API_TOKEN"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "AWS Route53 配置"

    使用 Amazon Route53 进行 DNS 验证的配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id YOUR_ACCESS_KEY"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key YOUR_SECRET_KEY"
    ```

=== "使用测试环境和重试进行测试"

    使用测试环境和增强的重试设置进行测试的配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "具有自定义传播时间的 DigitalOcean"

    使用 DigitalOcean DNS 并设置更长传播等待时间的配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token YOUR_API_TOKEN"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    使用 Google Cloud DNS 和服务帐户凭据的配置：

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

STREAM 支持 :warning:

BunkerWeb 中的限制插件提供了强大的功能来对您的网站强制执行限制策略，确保公平使用并保护您的资源免受滥用、拒绝服务攻击和过度的资源消耗。这些策略包括：

- **每个 IP 地址的连接数** (流支持 :white_check_mark:)
- **在特定时间段内每个 IP 地址和 URL 的请求数** (流支持 :x:)

### 工作原理

1.  **速率限制：** 跟踪来自每个客户端 IP 地址到特定 URL 的请求数。如果客户端超过配置的速率限制，后续请求将被暂时拒绝。
2.  **连接限制：** 监控并限制来自每个客户端 IP 地址的并发连接数。可以根据使用的协议（HTTP/1、HTTP/2、HTTP/3 或流）应用不同的连接限制。
3.  在这两种情况下，超过定义限制的客户端都会收到一个 HTTP 状态码 **“429 - 请求过多”**，这有助于防止服务器过载。

### 使用步骤

1.  **启用请求速率限制：** 使用 `USE_LIMIT_REQ` 启用请求速率限制，并定义 URL 模式及其相应的速率限制。
2.  **启用连接限制：** 使用 `USE_LIMIT_CONN` 启用连接限制，并为不同协议设置最大并发连接数。
3.  **应用精细控制：** 为不同的 URL 创建多个速率限制规则，以便在您的网站上提供不同级别的保护。
4.  **监控有效性：** 使用[Web UI](web-ui.md)查看有关受限请求和连接的统计信息。

### 配置设置

=== "请求速率限制"

    | 设置             | 默认值 | 上下文    | 多选 | 描述                                                                                                                 |
    | ---------------- | ------ | --------- | ---- | -------------------------------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_REQ`  | `yes`  | multisite | 否   | **启用请求限制：** 设置为 `yes` 以启用请求速率限制功能。                                                             |
    | `LIMIT_REQ_URL`  | `/`    | multisite | 是   | **URL 模式：** 将应用速率限制的 URL 模式（PCRE 正则表达式）；使用 `/` 以应用于所有请求。                             |
    | `LIMIT_REQ_RATE` | `2r/s` | multisite | 是   | **速率限制：** 最大请求速率，格式为 `Nr/t`，其中 N 是请求数，t 是时间单位：s（秒）、m（分钟）、h（小时）或 d（天）。 |

    !!! tip "速率限制格式"
        速率限制格式指定为 `Nr/t`，其中：

        -   `N` 是允许的请求数
        -   `r` 是字面上的 'r'（代表 'requests'）
        -   `/` 是字面上的斜杠
        -   `t` 是时间单位：`s`（秒）、`m`（分钟）、`h`（小时）或 `d`（天）

        例如，`5r/m` 表示每个 IP 地址每分钟允许 5 个请求。

=== "连接限制"

    | 设置                    | 默认值 | 上下文    | 多选 | 描述                                                           |
    | ----------------------- | ------ | --------- | ---- | -------------------------------------------------------------- |
    | `USE_LIMIT_CONN`        | `yes`  | multisite | 否   | **启用连接限制：** 设置为 `yes` 以启用连接限制功能。           |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`   | multisite | 否   | **HTTP/1.X 连接数：** 每个 IP 地址的最大并发 HTTP/1.X 连接数。 |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`  | multisite | 否   | **HTTP/2 流数：** 每个 IP 地址的最大并发 HTTP/2 流数。         |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`  | multisite | 否   | **HTTP/3 流数：** 每个 IP 地址的最大并发 HTTP/3 流数。         |
    | `LIMIT_CONN_MAX_STREAM` | `10`   | multisite | 否   | **流连接数：** 每个 IP 地址的最大并发流连接数。                |

!!! info "连接限制与请求限制" - **连接限制** 限制单个 IP 地址可以维持的并发连接数。- **请求速率限制** 限制一个 IP 地址在定义的时间段内可以发出的请求数。

    同时使用这两种方法可以全面防护各种类型的滥用。

!!! warning "设置适当的限制"
    设置过于严格的限制可能会影响合法用户，特别是对于 HTTP/2 和 HTTP/3，浏览器通常会使用多个流。默认值在大多数用例中是平衡的，但请考虑根据您的应用程序需求和用户行为进行调整。

### 配置示例

=== "基本保护"

    一个使用默认设置来保护您整个网站的简单配置：

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

=== "保护特定端点"

    针对不同端点设置不同速率限制的配置：

    ```yaml
    USE_LIMIT_REQ: "yes"

    # 针对所有请求的默认规则
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "10r/s"

    # 对登录页面设置更严格的限制
    LIMIT_REQ_URL_2: "^/login"
    LIMIT_REQ_RATE_2: "1r/s"

    # 对 API 设置更严格的限制
    LIMIT_REQ_URL_3: "^/api/"
    LIMIT_REQ_RATE_3: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "高流量网站配置"

    为高流量网站调整的配置，具有更宽松的限制：

    ```yaml
    USE_LIMIT_REQ: "yes"

    # 通用限制
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "30r/s"

    # 管理区域保护
    LIMIT_REQ_URL_2: "^/admin/"
    LIMIT_REQ_RATE_2: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "50"
    LIMIT_CONN_MAX_HTTP2: "200"
    LIMIT_CONN_MAX_HTTP3: "200"
    LIMIT_CONN_MAX_STREAM: "30"
    ```

=== "API 服务器配置"

    为 API 服务器优化的配置，速率限制以每分钟请求数表示：

    ```yaml
    USE_LIMIT_REQ: "yes"

    # 公共 API 端点
    LIMIT_REQ_URL: "^/api/public/"
    LIMIT_REQ_RATE: "120r/m"

    # 私有 API 端点
    LIMIT_REQ_URL_2: "^/api/private/"
    LIMIT_REQ_RATE_2: "300r/m"

    # 认证端点
    LIMIT_REQ_URL_3: "^/api/auth"
    LIMIT_REQ_RATE_3: "10r/m"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "20"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "20"
    ```

## Load Balancer <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/cOVp0rAt5nw' title='负载均衡器' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

STREAM 支持 :x:

Provides load balancing feature to group of upstreams with optional healthchecks.

| 参数                                      | 默认值        | 上下文 | 可重复 | 描述                                                               |
| ----------------------------------------- | ------------- | ------ | ------ | ------------------------------------------------------------------ |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`         | global | 否     | Shared dict size (datastore for all healthchecks).                 |
| `LOADBALANCER_UPSTREAM_NAME`              |               | global | 是     | Name of the upstream (used in REVERSE_PROXY_HOST).                 |
| `LOADBALANCER_UPSTREAM_SERVERS`           |               | global | 是     | List of servers/IPs in the server group.                           |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin` | global | 是     | Load balancing mode (round-robin or sticky).                       |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`          | global | 是     | Sticky session method (ip or cookie).                              |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`          | global | 是     | Dynamically resolve upstream hostnames.                            |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |               | global | 是     | Number of keepalive connections to cache per worker.               |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`         | global | 是     | Keepalive timeout for upstream connections.                        |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`          | global | 是     | Keepalive time for upstream connections.                           |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status`     | global | 是     | The healthcheck URL.                                               |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`        | global | 是     | Healthcheck interval in milliseconds.                              |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`        | global | 是     | Healthcheck timeout in milliseconds.                               |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`           | global | 是     | Number of failed healthchecks before marking the server as down.   |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`           | global | 是     | Number of successful healthchecks before marking the server as up. |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`         | global | 是     | HTTP status considered valid in healthchecks.                      |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`          | global | 是     | Maximum number of concurrent healthchecks.                         |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`        | global | 是     | Type of healthcheck (http or https).                               |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`         | global | 是     | Verify SSL certificate in healthchecks.                            |
| `LOADBALANCER_HEALTHCHECK_HOST`           |               | global | 是     | Host header for healthchecks (useful for HTTPS).                   |

## Metrics

STREAM 支持 :warning:

指标插件为您的 BunkerWeb 实例提供全面的监控和数据收集功能。此功能使您能够跟踪各种性能指标、安全事件和系统统计信息，从而为您提供有关受保护网站和服务行为及健康状况的宝贵见解。

**工作原理：**

1.  BunkerWeb 在处理请求和响应期间收集关键指标。
2.  这些指标包括被阻止请求的计数器、性能测量以及各种与安全相关的统计信息。
3.  数据高效地存储在内存中，并具有可配置的限制以防止过多的资源使用。
4.  对于多实例设置，可以使用 Redis 来集中和聚合指标数据。
5.  收集到的指标可以通过 API 访问或在[Web UI](web-ui.md)中可视化。
6.  此信息可帮助您识别安全威胁、解决问题并优化您的配置。

### 技术实现

指标插件的工作方式如下：

- 在 NGINX 中使用共享字典，其中 `metrics_datastore` 用于 HTTP，`metrics_datastore_stream` 用于 TCP/UDP 流量
- 利用 LRU 缓存进行高效的内存存储
- 使用计时器在工作进程之间定期同步数据
- 存储有关被阻止请求的详细信息，包括客户端 IP 地址、国家/地区、时间戳、请求详情和阻止原因
- 通过通用的指标收集接口支持插件特定的指标
- 提供用于查询收集到的指标的 API 端点

### 如何使用

请按照以下步骤配置和使用指标功能：

1.  **启用该功能：** 指标收集默认启用。您可以使用 `USE_METRICS` 设置来控制此功能。
2.  **配置内存分配：** 使用 `METRICS_MEMORY_SIZE` 设置来设置用于指标存储的内存量。
3.  **设置存储限制：** 使用相应的设置定义每个工作进程和 Redis 中要存储的被阻止请求的数量。
4.  **访问数据：** 通过[Web UI](web-ui.md)或 API 端点查看收集到的指标。
5.  **分析信息：** 使用收集到的数据来识别模式、检测安全问题并优化您的配置。

### 收集的指标

指标插件收集以下信息：

1.  **被阻止的请求**：对于每个被阻止的请求，将存储以下数据：
    - 请求 ID 和时间戳
    - 客户端 IP 地址和国家/地区（如果可用）
    - HTTP 方法和 URL
    - HTTP 状态码
    - 用户代理
    - 阻止原因和安全模式
    - 服务器名称
    - 与阻止原因相关的其他数据

2.  **插件计数器**：跟踪活动和事件的各种插件特定计数器。

### API 访问

指标数据可以通过 BunkerWeb 的内部 API 端点访问：

- **端点**：`/metrics/{filter}`
- **方法**：GET
- **描述**：根据指定的过滤器检索指标数据
- **响应格式**：包含所请求指标的 JSON 对象

例如，`/metrics/requests` 返回有关被阻止请求的信息。

!!! info "API 访问配置"
    要通过 API 访问指标，您必须确保：

    1.  API 功能已通过 `USE_API: "yes"` 启用（默认启用）
    2.  您的客户端 IP 包含在 `API_WHITELIST_IP` 设置中（默认为 `127.0.0.0/8`）
    3.  您正在通过配置的端口访问 API（默认为 `5000`，通过 `API_HTTP_PORT` 设置）
    4.  您在 Host 标头中使用了正确的 `API_SERVER_NAME` 值（默认为 `bwapi`）
    5.  如果配置了 `API_TOKEN`，请在请求标头中包含 `Authorization: Bearer <token>`。

    典型请求：

    不带令牌（当未设置 `API_TOKEN` 时）：
    ```bash
    curl -H "Host: bwapi" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    带令牌（当设置了 `API_TOKEN` 时）：
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    如果您已将 `API_SERVER_NAME` 自定义为默认 `bwapi` 以外的值，请在 Host 标头中使用该值。

    对于安全的生产环境，请将 API 访问限制为受信任的 IP，并启用 `API_TOKEN`。

### 配置设置

| 设置                                 | 默认值   | 上下文    | 多选 | 描述                                                                                             |
| ------------------------------------ | -------- | --------- | ---- | ------------------------------------------------------------------------------------------------ |
| `USE_METRICS`                        | `yes`    | multisite | 否   | **启用指标：** 设置为 `yes` 以启用指标的收集和检索。                                             |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | 否   | **内存大小：** 指标内部存储的大小（例如，`16m`、`32m`）。                                        |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | 否   | **最大被阻止请求数：** 每个工作进程要存储的最大被阻止请求数。                                    |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | 否   | **Redis 最大被阻止请求数：** 在 Redis 中要存储的最大被阻止请求数。                               |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | 否   | **将指标保存到 Redis：** 设置为 `yes` 以将指标（计数器和表）保存到 Redis，以实现集群范围的聚合。 |

!!! tip "调整内存分配大小"
    应根据您的流量和实例数量调整 `METRICS_MEMORY_SIZE` 设置。对于高流量网站，请考虑增加此值以确保所有指标都能被捕获而不会丢失数据。

!!! info "Redis 集成"
    当 BunkerWeb 配置为使用[Redis](#redis)时，指标插件将自动将被阻止的请求数据同步到 Redis 服务器。这提供了跨多个 BunkerWeb 实例的安全事件的集中视图。

!!! warning "性能注意事项"
    为 `METRICS_MAX_BLOCKED_REQUESTS` 或 `METRICS_MAX_BLOCKED_REQUESTS_REDIS` 设置非常高的值会增加内存使用量。请监控您的系统资源，并根据您的实际需求和可用资源调整这些值。

!!! note "工作进程特定存储"
    每个 NGINX 工作进程都在内存中维护自己的指标。通过 API 访问指标时，会自动聚合所有工作进程的数据以提供完整的视图。

### 配置示例

=== "基本配置"

    适用于大多数部署的默认配置：

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "低资源环境"

    为资源有限的环境优化的配置：

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "高流量环境"

    需要跟踪更多安全事件的高流量网站的配置：

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "禁用指标"

    禁用指标收集的配置：

    ```yaml
    USE_METRICS: "no"
    ```

## Migration <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :white_check_mark:

Migration of BunkerWeb configuration between instances made easy via the web UI

## Miscellaneous

STREAM 支持 :warning:

杂项插件提供了**必要的基准设置**，有助于维护您网站的安全性和功能性。这个核心组件提供了全面的控制，包括：

- **服务器行为** - 配置您的服务器如何响应各种请求
- **HTTP 设置** - 管理方法、请求大小和协议选项
- **文件管理** - 控制静态文件的提供并优化交付
- **协议支持** - 启用现代 HTTP 协议以获得更好的性能
- **系统配置** - 扩展功能并提高安全性

无论您是需要限制 HTTP 方法、管理请求大小、优化文件缓存，还是控制服务器如何响应各种请求，此插件都为您提供了**微调 Web 服务行为**的工具，同时优化了性能和安全性。

### 主要功能

| 功能类别           | 描述                                                                  |
| ------------------ | --------------------------------------------------------------------- |
| **HTTP 方法控制**  | 定义您的应用程序可接受哪些 HTTP 方法                                  |
| **默认服务器保护** | 防止通过主机名不匹配进行未经授权的访问，并强制使用 SNI 以确保安全连接 |
| **请求大小管理**   | 为客户端请求体和文件上传设置限制                                      |
| **静态文件服务**   | 配置和优化从自定义根文件夹交付静态内容                                |
| **文件缓存**       | 通过具有可自定义设置的高级文件描述符缓存机制提高性能                  |
| **协议支持**       | 配置现代 HTTP 协议选项 (HTTP2/HTTP3) 和 Alt-Svc 端口设置              |
| **匿名报告**       | 可选的使用统计报告，以帮助改进 BunkerWeb                              |
| **外部插件支持**   | 通过 URL 集成外部插件来扩展功能                                       |
| **HTTP 状态控制**  | 配置您的服务器在拒绝请求时的响应方式（包括终止连接）                  |

### 配置指南

=== "默认服务器安全"

    **默认服务器控制**

    在 HTTP 中，`Host` 标头指定目标服务器，但它可能缺失或未知，这通常是由于机器人扫描漏洞造成的。

    要阻止此类请求：

    -   将 `DISABLE_DEFAULT_SERVER` 设置为 `yes`，以使用 [NGINX 的 `444` 状态码](https://http.dev/444) 静默拒绝此类请求。
    -   为了更严格的安全性，启用 `DISABLE_DEFAULT_SERVER_STRICT_SNI` 以拒绝没有有效 SNI 的 SSL/TLS 连接。

    !!! success "安全优势"
        - 阻止 Host 标头操纵和虚拟主机扫描
        - 减轻 HTTP 请求走私风险
        - 移除默认服务器作为攻击媒介

    | 设置                                | 默认值 | 上下文 | 多选 | 描述                                                                                   |
    | ----------------------------------- | ------ | ------ | ---- | -------------------------------------------------------------------------------------- |
    | `DISABLE_DEFAULT_SERVER`            | `no`   | global | no   | **默认服务器：** 设置为 `yes` 以在没有主机名与请求匹配时禁用默认服务器。               |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`   | global | no   | **严格 SNI：** 当设置为 `yes` 时，要求 HTTPS 连接使用 SNI，并拒绝没有有效 SNI 的连接。 |

    !!! warning "SNI 强制执行"
        启用严格的 SNI 验证可提供更强的安全性，但如果 BunkerWeb 位于一个转发 HTTPS 请求但未保留 SNI 信息的反向代理之后，可能会导致问题。在生产环境中启用之前请进行彻底测试。

=== "拒绝 HTTP 状态"

    **HTTP 状态控制**

    处理被拒绝的客户端访问的第一步是定义适当的操作。这可以使用 `DENY_HTTP_STATUS` 设置进行配置。当 BunkerWeb 拒绝一个请求时，您可以使用此设置控制其响应。默认情况下，它返回一个 `403 Forbidden` 状态，并向客户端显示一个网页或自定义内容。

    或者，将其设置为 `444` 会立即关闭连接而不发送任何响应。这个[非标准状态码](https://http.dev/444)，特定于 NGINX，对于静默丢弃不需要的请求很有用。

    | 设置               | 默认值 | 上下文 | 多选 | 描述                                                                                     |
    | ------------------ | ------ | ------ | ---- | ---------------------------------------------------------------------------------------- |
    | `DENY_HTTP_STATUS` | `403`  | global | no   | **拒绝 HTTP 状态：** 请求被拒绝时发送的 HTTP 状态码（403 或 444）。代码 444 会关闭连接。 |

    !!! warning "444 状态码的注意事项"
        由于客户端收不到任何反馈，故障排查可能会更具挑战性。只有在您已彻底解决误报问题、对 BunkerWeb 有丰富经验并需要更高安全级别时，才建议设置为 `444`。

    !!! info "流模式"
        在**流模式**下，此设置始终强制为 `444`，这意味着无论配置的值如何，连接都将被关闭。

=== "HTTP 方法"

    **HTTP 方法控制**

    将 HTTP 方法限制为应用程序所需的那些方法，是遵循最小权限原则的一项基本安全措施。通过明确定义可接受的 HTTP 方法，您可以最大限度地降低通过未使用或危险的方法被利用的风险。

    此功能使用 `ALLOWED_METHODS` 设置进行配置，其中方法用 `|` 分隔（默认值：`GET|POST|HEAD`）。如果客户端尝试使用未列出的方法，服务器将以 **405 - Method Not Allowed** 状态响应。

    对于大多数网站，默认的 `GET|POST|HEAD` 就足够了。如果您的应用程序使用 RESTful API，您可能需要包含 `PUT` 和 `DELETE` 等方法。

    !!! success "安全优势"
        - 防止利用未使用或不必要的 HTTP 方法
        - 通过禁用可能有害的方法来减少攻击面
        - 阻止攻击者使用的 HTTP 方法枚举技术

    | 设置              | 默认值 | 上下文 | 多选  | 描述      |
    | ----------------- | ------ | ------ | ----- | --------- |
    | `ALLOWED_METHODS` | `GET   | POST   | HEAD` | multisite | no | **HTTP 方法：** 允许的 HTTP 方法列表，用竖线字符分隔。 |

    !!! abstract "CORS 和预检请求"
        如果您的应用程序支持[跨源资源共享 (CORS)](#cors)，您应该在 `ALLOWED_METHODS` 设置中包含 `OPTIONS` 方法以处理预检请求。这确保了浏览器发出跨源请求时的正常功能。

    !!! danger "安全注意事项"
        - **避免启用 `TRACE` 或 `CONNECT`：** 这些方法很少需要，并且可能引入重大的安全风险，例如启用跨站跟踪 (XST) 或隧道攻击。
        - **定期审查允许的方法：** 定期审核 `ALLOWED_METHODS` 设置，以确保其与您应用程序的当前要求保持一致。
        - **部署前进行彻底测试：** 对 HTTP 方法限制的更改可能会影响应用程序功能。在将其应用于生产环境之前，请在预演环境中验证您的配置。

=== "请求大小限制"

    **请求大小限制**

    最大请求体大小可以使用 `MAX_CLIENT_SIZE` 设置进行控制（默认值：`10m`）。接受的值遵循[此处](https://nginx.org/en/docs/syntax.html)描述的语法。

    !!! success "安全优势"
        - 防止由过大负载大小引起的拒绝服务攻击
        - 减轻缓冲区溢出漏洞
        - 防止文件上传攻击
        - 降低服务器资源耗尽的风险

    | 设置              | 默认值 | 上下文    | 多选 | 描述                                                            |
    | ----------------- | ------ | --------- | ---- | --------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`  | multisite | no   | **最大请求大小：** 客户端请求体（例如文件上传）允许的最大大小。 |

    !!! tip "请求大小配置最佳实践"
        如果您需要允许无限大小的请求体，可以将 `MAX_CLIENT_SIZE` 的值设置为 `0`。但是，由于潜在的安全和性能风险，**不推荐**这样做。

        **最佳实践：**

        - 始终将 `MAX_CLIENT_SIZE` 配置为满足您应用程序合法要求的最小值。
        - 定期审查和调整此设置，以适应您应用程序不断变化的需求。
        - 除非绝对必要，否则避免设置为 `0`，因为它可能使您的服务器面临拒绝服务攻击和资源耗尽的风险。

        通过仔细管理此设置，您可以确保应用程序的最佳安全性和性能。

=== "协议支持"

    **HTTP 协议设置**

    像 HTTP/2 和 HTTP/3 这样的现代 HTTP 协议可以提高性能和安全性。BunkerWeb 允许轻松配置这些协议。

    !!! success "安全和性能优势"
        - **安全优势：** 像 HTTP/2 和 HTTP/3 这样的现代协议默认强制使用 TLS/HTTPS，减少了对某些攻击的易感性，并通过加密头（HTTP/3）提高了隐私性。
        - **性能优势：** 多路复用、头部压缩、服务器推送和二进制数据传输等功能提高了速度和效率。

    | 设置                 | 默认值 | 上下文    | 多选 | 描述                                                           |
    | -------------------- | ------ | --------- | ---- | -------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`  | multisite | no   | **HTTP 监听：** 当设置为 `yes` 时，响应（不安全的）HTTP 请求。 |
    | `HTTP2`              | `yes`  | multisite | no   | **HTTP2：** 当启用 HTTPS 时，支持 HTTP2 协议。                 |
    | `HTTP3`              | `yes`  | multisite | no   | **HTTP3：** 当启用 HTTPS 时，支持 HTTP3 协议。                 |
    | `HTTP3_ALT_SVC_PORT` | `443`  | multisite | no   | **HTTP3 Alt-Svc 端口：** 在 Alt-Svc 标头中用于 HTTP3 的端口。  |

    !!! example "关于 HTTP/3"
        HTTP/3 是超文本传输协议的最新版本，它使用 QUIC over UDP 而不是 TCP，解决了诸如队头阻塞等问题，以实现更快、更可靠的连接。

        NGINX 从 1.25.0 版本开始引入了对 HTTP/3 和 QUIC 的实验性支持。但是，此功能仍处于实验阶段，建议在生产中使用时保持谨慎。更多详情，请参阅 [NGINX 的官方文档](https://nginx.org/en/docs/quic.html)。

        建议在生产环境中启用 HTTP/3 之前进行彻底测试。

=== "静态文件服务"

    **文件服务配置**

    BunkerWeb 可以直接提供静态文件，也可以作为应用程序服务器的反向代理。默认情况下，文件从 `/var/www/html/{server_name}` 提供。

    | 设置          | 默认值                        | 上下文    | 多选 | 描述                                                                         |
    | ------------- | ----------------------------- | --------- | ---- | ---------------------------------------------------------------------------- |
    | `SERVE_FILES` | `yes`                         | multisite | no   | **提供文件：** 当设置为 `yes` 时，BunkerWeb 将从配置的根文件夹提供静态文件。 |
    | `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | no   | **根文件夹：** 提供静态文件的目录。为空表示使用默认位置。                    |

    !!! tip "静态文件服务最佳实践"
        - **直接服务：** 当 BunkerWeb 负责直接提供静态文件时，启用文件服务 (`SERVE_FILES=yes`)。
        - **反向代理：** 如果 BunkerWeb 作为反向代理，**停用文件服务** (`SERVE_FILES=no`) 以减少攻击面并避免暴露不必要的目录。
        - **权限：** 确保正确的文件权限和路径配置，以防止未经授权的访问。
        - **安全：** 避免因配置不当而暴露敏感目录或文件。

        通过仔细管理静态文件服务，您可以在保持安全环境的同时优化性能。

=== "系统设置"

    **插件和系统管理**

    这些设置管理 BunkerWeb 与外部系统的交互，并通过可选的匿名使用统计信息为改进产品做出贡献。

    **匿名报告**

    匿名报告为 BunkerWeb 团队提供了有关软件使用情况的见解。这有助于确定需要改进的领域并优先开发功能。报告严格是统计性的，不包含任何敏感或个人可识别信息。它们涵盖：

    - 启用的功能
    - 通用配置模式

    如果您愿意，可以通过将 `SEND_ANONYMOUS_REPORT` 设置为 `no` 来禁用此功能。

    **外部插件**

    外部插件使您能够通过集成第三方模块来扩展 BunkerWeb 的功能。这允许进行额外的定制和高级用例。

    !!! danger "外部插件安全"
        **如果未经适当审查，外部插件可能会引入安全风险。** 请遵循以下最佳实践以最大限度地减少潜在威胁：

        - 仅使用来自可信来源的插件。
        - 在可用时使用校验和验证插件的完整性。
        - 定期审查和更新插件以确保安全性和兼容性。

        更多详情，请参阅[插件文档](plugins.md)。

    | 设置                    | 默认值 | 上下文 | 多选 | 描述                                                  |
    | ----------------------- | ------ | ------ | ---- | ----------------------------------------------------- |
    | `SEND_ANONYMOUS_REPORT` | `yes`  | global | no   | **匿名报告：** 向 BunkerWeb 维护者发送匿名使用报告。  |
    | `EXTERNAL_PLUGIN_URLS`  |        | global | no   | **外部插件：** 用于下载外部插件的 URL（以空格分隔）。 |

=== "文件缓存"

    **文件缓存优化**

    打开文件缓存通过在内存中存储文件描述符和元数据来提高性能，减少了重复文件系统操作的需求。

    !!! success "文件缓存的好处"
        - **性能：** 减少文件系统 I/O，降低延迟，并降低文件操作的 CPU 使用率。
        - **安全：** 通过缓存错误响应来减轻时序攻击，并减少针对文件系统的 DoS 攻击的影响。

    | 设置                       | 默认值                  | 上下文    | 多选 | 描述                                                              |
    | -------------------------- | ----------------------- | --------- | ---- | ----------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no   | **启用缓存：** 启用文件描述符和元数据的缓存以提高性能。           |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no   | **缓存配置：** 配置打开文件缓存（例如，最大条目数和非活动超时）。 |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no   | **缓存错误：** 缓存文件描述符查找错误以及成功查找。               |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no   | **最少使用次数：** 在非活动期间，文件保持缓存所需的最少访问次数。 |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no   | **缓存有效期：** 缓存元素重新验证的时间。                         |

    **配置指南**

    要启用和配置文件缓存：
    1.  将 `USE_OPEN_FILE_CACHE` 设置为 `yes` 以激活该功能。
    2.  调整 `OPEN_FILE_CACHE` 参数以定义缓存条目的最大数量及其非活动超时。
    3.  使用 `OPEN_FILE_CACHE_ERRORS` 缓存成功和失败的查找，以减少重复的文件系统操作。
    4.  设置 `OPEN_FILE_CACHE_MIN_USES` 以指定文件保持缓存所需的最少访问次数。
    5.  使用 `OPEN_FILE_CACHE_VALID` 定义缓存有效期，以控制缓存元素的重新验证频率。

    !!! tip "最佳实践"
        - 为具有大量静态文件的网站启用文件缓存以提高性能。
        - 定期审查和微调缓存设置，以平衡性能和资源使用。
        - 在文件频繁更改的动态环境中，考虑缩短缓存有效期或禁用该功能以确保内容新鲜度。

### 配置示例

=== "默认服务器安全"

    禁用默认服务器并强制执行严格 SNI 的示例配置：

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "拒绝 HTTP 状态"

    静默丢弃不需要的请求的示例配置：

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "HTTP 方法"

    将 HTTP 方法限制为 RESTful API 所需方法的示例配置：

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "请求大小限制"

    限制最大请求体大小的示例配置：

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "协议支持"

    启用 HTTP/2 和 HTTP/3 并使用自定义 Alt-Svc 端口的示例配置：

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "静态文件服务"

    从自定义根文件夹提供静态文件的示例配置：

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "文件缓存"

    启用和优化文件缓存的示例配置：

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"
    ```

## ModSecurity

STREAM 支持 :x:

ModSecurity 插件将功能强大的 [ModSecurity](https://modsecurity.org) Web 应用程序防火墙 (WAF) 集成到 BunkerWeb 中。通过利用 [OWASP 核心规则集 (CRS)](https://coreruleset.org)，此集成可检测并阻止 SQL 注入、跨站脚本 (XSS)、本地文件包含等威胁，从而提供针对各种 Web 攻击的强大防护。

**工作原理：**

1.  当收到请求时，ModSecurity 会根据活动规则集对其进行评估。
2.  OWASP 核心规则集会检查标头、Cookie、URL 参数和正文内容。
3.  每个检测到的违规行为都会增加总体异常分数。
4.  如果此分数超过配置的阈值，则请求将被阻止。
5.  创建详细的日志以帮助诊断触发了哪些规则以及原因。

!!! success "主要优势"

      1. **行业标准保护：** 利用广泛使用的开源 ModSecurity 防火墙。
      2. **OWASP 核心规则集：** 采用社区维护的规则，涵盖 OWASP 十大漏洞及更多内容。
      3. **可配置的安全级别：** 调整偏执级别以在安全性与潜在的误报之间取得平衡。
      4. **详细日志记录：** 提供详尽的审计日志以进行攻击分析。
      5. **插件支持：** 通过为您的应用程序量身定制的可选 CRS 插件来扩展保护。

### 如何使用

请按照以下步骤配置和使用 ModSecurity：

1.  **启用该功能：** ModSecurity 默认启用。可以使用 `USE_MODSECURITY` 设置进行控制。
2.  **选择 CRS 版本：** 选择一个 OWASP 核心规则集版本（v3、v4 或 nightly）。
3.  **添加插件：** 可选择激活 CRS 插件以增强规则覆盖范围。
4.  **监控和调整：** 使用日志和 [Web UI](web-ui.md) 识别误报并调整设置。

### 配置设置

| 设置                                  | 默认值         | 上下文    | 多选 | 描述                                                                                                                                        |
| ------------------------------------- | -------------- | --------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`          | multisite | 否   | **启用 ModSecurity：** 开启 ModSecurity Web 应用程序防火墙保护。                                                                            |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | 否   | **使用核心规则集：** 为 ModSecurity 启用 OWASP 核心规则集。                                                                                 |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | 否   | **CRS 版本：** 要使用的 OWASP 核心规则集版本。选项：`3`、`4` 或 `nightly`。                                                                 |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | 否   | **规则引擎：** 控制是否强制执行规则。选项：`On`、`DetectionOnly` 或 `Off`。                                                                 |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | 否   | **审计引擎：** 控制审计日志的工作方式。选项：`On`、`Off` 或 `RelevantOnly`。                                                                |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | 否   | **审计日志部分：** 审计日志中要包含的请求/响应的哪些部分。                                                                                  |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | 否   | **请求体限制（无文件）：** 不含文件上传的请求体的最大大小。接受纯字节或人类可读的后缀（`k`、`m`、`g`），例如 `131072`、`256k`、`1m`、`2g`。 |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | 否   | **启用 CRS 插件：** 为核心规则集启用其他插件规则集。                                                                                        |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | 否   | **CRS 插件列表：** 要下载和安装的插件的空格分隔列表（`plugin-name[/tag]` 或 URL）。                                                         |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | 否   | **全局 CRS：** 启用后，在 HTTP 级别而不是每个服务器上全局应用 CRS 规则。                                                                    |

!!! warning "ModSecurity 和 OWASP 核心规则集"
    **我们强烈建议同时启用 ModSecurity 和 OWASP 核心规则集 (CRS)**，以提供针对常见 Web 漏洞的强大保护。虽然偶尔可能会出现误报，但可以通过微调规则或使用预定义的排除项来解决。

    CRS 团队积极维护着针对 WordPress、Nextcloud、Drupal 和 Cpanel 等流行应用程序的排除项列表，从而更容易在不影响功能的情况下进行集成。其安全优势远远超过了解决误报所需的最低配置工作量。

### 可用的 CRS 版本

选择一个 CRS 版本以最符合您的安全需求：

- **`3`**：稳定版 [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8)。
- **`4`**：稳定版 [v4.22.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.22.0) (**默认**)。
- **`nightly`**：[每日构建版](https://github.com/coreruleset/coreruleset/releases/tag/nightly)，提供最新的规则更新。

!!! example "每日构建版"
    **每日构建版**包含最新的规则，提供针对新兴威胁的最新保护。然而，由于它每天更新，并且可能包含实验性或未经测试的更改，建议在将其部署到生产环境之前，首先在**预演环境**中使用每日构建版。

!!! tip "偏执级别"
    OWASP 核心规则集使用“偏执级别”(PL) 来控制规则的严格性：

    -   **PL1 (默认):** 基本保护，误报最少
    -   **PL2:** 更严格的安全性，具有更严格的模式匹配
    -   **PL3:** 增强的安全性，具有更严格的验证
    -   **PL4:** 最高安全性，规则非常严格（可能导致许多误报）

    您可以通过在 `/etc/bunkerweb/configs/modsec-crs/` 中添加自定义配置文件来设置偏执级别。

### 自定义配置 {#custom-configurations}

可以通过自定义配置来调整 ModSecurity 和 OWASP 核心规则集 (CRS)。这些配置允许您在安全规则处理的特定阶段自定义行为：

- **`modsec-crs`**：在加载 OWASP 核心规则集**之前**应用。
- **`modsec`**：在加载 OWASP 核心规则集**之后**应用。如果根本没有加载 CRS，也会使用此配置。
- **`crs-plugins-before`**：在加载 CRS 插件**之前**应用。
- **`crs-plugins-after`**：在加载 CRS 插件**之后**应用。

这种结构提供了灵活性，允许您根据应用程序的特定需求微调 ModSecurity 和 CRS 设置，同时保持清晰的配置流程。

#### 使用 `modsec-crs` 添加 CRS 排除项

您可以使用 `modsec-crs` 类型的自定义配置来为特定用例添加排除项，例如为 WordPress 启用预定义的排除项：

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

在此示例中：

- 该操作在**阶段 1**（请求生命周期的早期）执行。
- 它通过设置变量 `tx.crs_exclusions_wordpress` 来启用 WordPress 特定的 CRS 排除项。

#### 使用 `modsec` 更新 CRS 规则

要微调已加载的 CRS 规则，您可以使用 `modsec` 类型的自定义配置。例如，您可以为某些请求路径删除特定的规则或标签：

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

在此示例中：

- **规则 1**：为对 `/wp-admin/admin-ajax.php` 的请求删除标记为 `attack-xss` 和 `attack-rce` 的规则。
- **规则 2**：为对 `/wp-admin/options.php` 的请求删除标记为 `attack-xss` 的规则。
- **规则 3**：为匹配 `/wp-json/yoast` 的请求删除特定规则（ID `930120`）。

!!! info "执行顺序"
    BunkerWeb 中 ModSecurity 的执行顺序如下，确保了规则应用的清晰和逻辑性：

    1.  **OWASP CRS 配置**：OWASP 核心规则集的基础配置。
    2.  **自定义插件配置 (`crs-plugins-before`)**：特定于插件的设置，在任何 CRS 规则之前应用。
    3.  **自定义插件规则（在 CRS 规则之前）(`crs-plugins-before`)**：在 CRS 规则之前执行的插件自定义规则。
    4.  **下载的插件配置**：外部下载插件的配置。
    5.  **下载的插件规则（在 CRS 规则之前）**：在 CRS 规则之前执行的下载插件规则。
    6.  **自定义 CRS 规则 (`modsec-crs`)**：在加载 CRS 规则之前应用的用户定义规则。
    7.  **OWASP CRS 规则**：由 OWASP 提供的核心安全规则集。
    8.  **自定义插件规则（在 CRS 规则之后）(`crs-plugins-after`)**：在 CRS 规则之后执行的自定义插件规则。
    9.  **下载的插件规则（在 CRS 规则之后）**：在 CRS 规则之后执行的下载插件规则。
    10. **自定义规则 (`modsec`)**：在所有 CRS 和插件规则之后应用的用户定义规则。

    **关键说明**：

    -   **CRS 前的自定义**（`crs-plugins-before`、`modsec-crs`）允许您在加载核心 CRS 规则之前定义例外或准备性规则。
    -   **CRS 后的自定义**（`crs-plugins-after`、`modsec`）是在应用 CRS 和插件规则之后覆盖或扩展规则的理想选择。
    -   这种结构提供了最大的灵活性，能够在保持强大安全基线的同时，精确控制规则的执行和自定义。

### OWASP CRS 插件

OWASP 核心规则集还支持一系列**插件**，旨在扩展其功能并提高与特定应用程序或环境的兼容性。这些插件可以帮助微调 CRS，以用于 WordPress、Nextcloud 和 Drupal 等流行平台，甚至是自定义设置。有关更多信息和可用插件列表，请参阅 [OWASP CRS 插件注册表](https://github.com/coreruleset/plugin-registry)。

!!! tip "插件下载"
    `MODSECURITY_CRS_PLUGINS` 设置允许您下载和安装插件，以扩展 OWASP 核心规则集 (CRS) 的功能。此设置接受带有可选标签或 URL 的插件名称列表，从而可以轻松集成根据您的特定需求量身定制的其他安全功能。

    以下是 `MODSECURITY_CRS_PLUGINS` 设置接受的值的非详尽列表：

    *   `fake-bot` - 下载插件的最新版本。
    *   `wordpress-rule-exclusions/v1.0.0` - 下载插件的 1.0.0 版本。
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - 直接从 URL 下载插件。

!!! warning "误报"
    较高的安全设置可能会阻止合法流量。请从默认设置开始，并在提高安全级别之前监控日志。请准备好为您的特定应用程序需求添加排除规则。

### 配置示例

=== "基本配置"

    启用 ModSecurity 和 CRS v4 的标准配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "仅检测模式"

    用于监控潜在威胁而不进行阻止的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "带插件的高级配置"

    启用 CRS v4 和插件以提供额外保护的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "旧版配置"

    使用 CRS v3 以与旧设置兼容的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "全局 ModSecurity"

    在所有 HTTP 连接上全局应用 ModSecurity 的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "带自定义插件的每日构建版"

    使用 CRS 的每日构建版并带有自定义插件的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "人类可读的大小值"
    对于像 `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` 这样的 大小设置，支持 `k`、`m` 和 `g`（不区分大小写）后缀，分别代表 kibibytes、mebibytes 和 gibibytes（1024 的倍数）。例如：`256k` = 262144，`1m` = 1048576，`2g` = 2147483648。

## Monitoring <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

BunkerWeb monitoring pro system. This plugin is a prerequisite for some other plugins.

| 参数                           | 默认值 | 上下文 | 可重复 | 描述                                                                        |
| ------------------------------ | ------ | ------ | ------ | --------------------------------------------------------------------------- |
| `USE_MONITORING`               | `yes`  | global | 否     | Enable monitoring of BunkerWeb.                                             |
| `MONITORING_METRICS_DICT_SIZE` | `10M`  | global | 否     | Size of the dict to store monitoring metrics.                               |
| `MONITORING_IGNORE_URLS`       |        | global | 否     | List of URLs to ignore when monitoring separated with spaces (e.g. /health) |

## Mutual TLS

STREAM 支持 :white_check_mark:

Mutual TLS（mTLS）插件可在关键站点上强制执行客户端证书认证，确保只有受信任实体才能访问敏感资源。启用后，BunkerWeb 会在请求进入业务前完成身份鉴别，从而保护内部工具与合作伙伴集成。

BunkerWeb 会基于您配置的 CA 证书包和策略评估每一次 TLS 握手。未满足规则的客户端会被拦截，通过验证的连接则可以将证书细节传递给后端应用，以便执行更精细的授权控制。

**工作原理：**

1. 插件持续监控所选站点的 HTTPS 握手。
2. 在 TLS 交换阶段，BunkerWeb 检查客户端证书，并与指定的受信任存储进行链路校验。
3. 验证模式决定是否拒绝、宽松接受或仅用于诊断地放行未携带证书的客户端。
4. （可选）BunkerWeb 通过 `X-SSL-Client-*` 请求头暴露验证结果，便于上游应用实现自定义的访问逻辑。

!!! success "主要优势"

      1. **强化边界防护：** 只有完成身份验证的机器与用户才能访问核心路径。
      2. **灵活信任策略：** 可根据接入流程在严格与可选模式之间切换。
      3. **应用层可见性：** 将证书指纹和身份信息传递给下游服务，便于审计。
      4. **多层安全防护：** 将 mTLS 与 BunkerWeb 其他插件（如限流、黑白名单）组合使用，构建纵深防御。

### 使用步骤

遵循以下步骤安全部署 Mutual TLS：

1. **启用功能：** 在目标站点将 `USE_MTLS` 设置为 `yes`。
2. **提供 CA 证书包：** 使用 PEM 文件存放可信颁发者，并在 `MTLS_CA_CERTIFICATE` 中配置其绝对路径。
3. **选择验证模式：** `on` 强制要求证书，`optional` 允许回退，`optional_no_ca` 仅用于短期诊断。
4. **调节链路深度：** 若组织存在多级中间证书，可调整 `MTLS_VERIFY_DEPTH`。
5. **转发验证结果（可选）：** 若后端需要检查证书信息，请保持 `MTLS_FORWARD_CLIENT_HEADERS` 为 `yes`。
6. **维护吊销数据：** 若发布 CRL，请填写 `MTLS_CRL`，使 BunkerWeb 能拒绝已吊销的证书。

### 配置设置

| 设置                          | 默认值 | 上下文    | 多个 | 说明                                                                                                                                     |
| ----------------------------- | ------ | --------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                    | `no`   | multisite | 否   | **启用 mutual TLS：** 为当前站点启用客户端证书认证。                                                                                     |
| `MTLS_CA_CERTIFICATE`         |        | multisite | 否   | **客户端 CA 证书包：** 指向受信任客户端 CA 证书包（PEM）的绝对路径。当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时必填；路径必须可读。 |
| `MTLS_VERIFY_CLIENT`          | `on`   | multisite | 否   | **验证模式：** 选择是否强制要求证书（`on`）、允许可选证书（`optional`），或在不验证 CA 的情况下接受证书（`optional_no_ca`）。            |
| `MTLS_VERIFY_DEPTH`           | `2`    | multisite | 否   | **验证深度：** 接受的客户端证书最大链深。                                                                                                |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`  | multisite | 否   | **转发客户端请求头：** 传播验证结果（状态、DN、签发者、序列号、指纹和有效期等 `X-SSL-Client-*` 请求头）。                                |
| `MTLS_CRL`                    |        | multisite | 否   | **客户端 CRL 路径：** 指向 PEM 编码证书吊销列表的可选路径。仅在成功加载 CA 证书包时生效。                                                |

!!! tip "保持证书最新"
    将 CA 证书包和吊销列表存放在 Scheduler 可读取的挂载卷中，以便重启时自动加载最新的信任锚。

!!! warning "严格模式需提供 CA 证书包"
    当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时，运行时必须存在 CA 文件。如果缺失，BunkerWeb 会跳过生成 mTLS 指令，避免服务因路径无效而启动失败。`optional_no_ca` 仅建议用于排查问题，因为它会降低认证强度。

!!! info "受信证书与验证"
    BunkerWeb 使用同一份 CA 证书包完成链路校验与信任构建，确保吊销检查和握手验证保持一致。

### 配置示例

=== "严格访问控制"

    要求客户端提供由您的私有 CA 签发的有效证书，并将验证信息转发给后端：

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "可选客户端认证"

    允许匿名用户访问，但在客户端提供证书时转发证书详情：

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "无 CA 的诊断"

    即便证书无法链到受信任的 CA 证书包，也允许连接完成。仅用于排查问题：

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

## OpenAPI Validator <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

Validates incoming HTTP requests against an OpenAPI / Swagger specification.

| 参数                         | 默认值                              | 上下文    | 可重复 | 描述                                                                                            |
| ---------------------------- | ----------------------------------- | --------- | ------ | ----------------------------------------------------------------------------------------------- |
| `USE_OPENAPI_VALIDATOR`      | `no`                                | multisite | 否     | Enable OpenAPI route validation for this site.                                                  |
| `OPENAPI_SPEC`               |                                     | multisite | 否     | Absolute path or HTTP(S) URL to the OpenAPI (swagger) document in JSON format.                  |
| `OPENAPI_BASE_PATH`          |                                     | multisite | 否     | Optional base path prefix to prepend to every path in the spec (overrides servers[*].url path). |
| `OPENAPI_ALLOW_UNSPECIFIED`  | `no`                                | multisite | 否     | Allow requests to paths not listed in the specification (otherwise they are denied).            |
| `OPENAPI_ALLOW_INSECURE_URL` | `no`                                | multisite | 否     | Allow fetching the OpenAPI spec over plain HTTP (not recommended).                              |
| `OPENAPI_IGNORE_URLS`        | `^/docs$ ^/redoc$ ^/openapi\.json$` | multisite | 否     | List of URL regexes to bypass OpenAPI validation (space separated).                             |
| `OPENAPI_CACHE_TTL`          | `300`                               | global    | 否     | Seconds to cache the parsed specification in shared cache.                                      |
| `OPENAPI_MAX_SPEC_SIZE`      | `2M`                                | global    | 否     | Maximum allowed size of the OpenAPI document (accepts suffix k/M/G).                            |

## OpenID Connect <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

OpenID Connect authentication plugin providing SSO capabilities with identity providers.

| 参数                                      | 默认值                 | 上下文    | 可重复 | 描述                                                                                                                                                    |
| ----------------------------------------- | ---------------------- | --------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_OPENIDC`                             | `no`                   | multisite | 否     | Enable or disable OpenID Connect authentication.                                                                                                        |
| `OPENIDC_DISCOVERY`                       |                        | multisite | 否     | OpenID Connect discovery URL (e.g. https://idp.example.com/.well-known/openid-configuration).                                                           |
| `OPENIDC_CLIENT_ID`                       |                        | multisite | 否     | OAuth 2.0 client identifier registered with the IdP.                                                                                                    |
| `OPENIDC_CLIENT_SECRET`                   |                        | multisite | 否     | OAuth 2.0 client secret registered with the IdP.                                                                                                        |
| `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD`      | `basic`                | multisite | 否     | Token endpoint auth method: basic (recommended, HTTP Basic), post (POST body), secret_jwt (JWT with client secret), private_key_jwt (JWT with RSA key). |
| `OPENIDC_CLIENT_RSA_PRIVATE_KEY`          |                        | multisite | 否     | PEM-encoded RSA private key for private_key_jwt authentication.                                                                                         |
| `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`       |                        | multisite | 否     | Optional key ID (kid) for private_key_jwt authentication.                                                                                               |
| `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN` |                        | multisite | 否     | JWT assertion lifetime in seconds (empty to use library default).                                                                                       |
| `OPENIDC_REDIRECT_URI`                    | `/callback`            | multisite | 否     | URI path where the IdP redirects after authentication.                                                                                                  |
| `OPENIDC_SCOPE`                           | `openid email profile` | multisite | 否     | Space-separated list of OAuth 2.0 scopes to request.                                                                                                    |
| `OPENIDC_AUTHORIZATION_PARAMS`            |                        | multisite | 否     | Additional authorization params as comma-separated key=value pairs (e.g. audience=api,resource=xyz). URL-encode values if needed.                       |
| `OPENIDC_USE_NONCE`                       | `yes`                  | multisite | 否     | Use nonce in authentication requests to prevent replay attacks.                                                                                         |
| `OPENIDC_USE_PKCE`                        | `no`                   | multisite | 否     | Use PKCE (Proof Key for Code Exchange) for authorization code flow.                                                                                     |
| `OPENIDC_FORCE_REAUTHORIZE`               | `no`                   | multisite | 否     | Force re-authorization on every request (not recommended for production).                                                                               |
| `OPENIDC_REFRESH_SESSION_INTERVAL`        |                        | multisite | 否     | Interval in seconds to silently re-authenticate (empty to disable).                                                                                     |
| `OPENIDC_IAT_SLACK`                       | `120`                  | multisite | 否     | Allowed clock skew in seconds for token validation.                                                                                                     |
| `OPENIDC_ACCESS_TOKEN_EXPIRES_IN`         | `3600`                 | multisite | 否     | Default access token lifetime (seconds) if not provided by IdP.                                                                                         |
| `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY`    | `yes`                  | multisite | 否     | Automatically renew access token using refresh token when expired.                                                                                      |
| `OPENIDC_ACCEPT_UNSUPPORTED_ALG`          | `no`                   | multisite | 否     | Accept tokens signed with unsupported algorithms (not recommended).                                                                                     |
| `OPENIDC_LOGOUT_PATH`                     | `/logout`              | multisite | 否     | URI path for logout requests.                                                                                                                           |
| `OPENIDC_REVOKE_TOKENS_ON_LOGOUT`         | `no`                   | multisite | 否     | Revoke tokens at the IdP when logging out.                                                                                                              |
| `OPENIDC_REDIRECT_AFTER_LOGOUT_URI`       |                        | multisite | 否     | URI to redirect after logout (leave empty for IdP default).                                                                                             |
| `OPENIDC_POST_LOGOUT_REDIRECT_URI`        |                        | multisite | 否     | URI to redirect after IdP logout is complete.                                                                                                           |
| `OPENIDC_TIMEOUT_CONNECT`                 | `10000`                | multisite | 否     | Connection timeout in milliseconds for IdP requests.                                                                                                    |
| `OPENIDC_TIMEOUT_SEND`                    | `10000`                | multisite | 否     | Send timeout in milliseconds for IdP requests.                                                                                                          |
| `OPENIDC_TIMEOUT_READ`                    | `10000`                | multisite | 否     | Read timeout in milliseconds for IdP requests.                                                                                                          |
| `OPENIDC_SSL_VERIFY`                      | `yes`                  | multisite | 否     | Verify SSL certificates when communicating with the IdP.                                                                                                |
| `OPENIDC_KEEPALIVE`                       | `yes`                  | multisite | 否     | Enable HTTP keepalive for connections to the IdP.                                                                                                       |
| `OPENIDC_HTTP_PROXY`                      |                        | multisite | 否     | HTTP proxy URL for IdP connections (e.g. http://proxy:8080).                                                                                            |
| `OPENIDC_HTTPS_PROXY`                     |                        | multisite | 否     | HTTPS proxy URL for IdP connections (e.g. http://proxy:8080).                                                                                           |
| `OPENIDC_USER_HEADER`                     | `X-User`               | multisite | 否     | Header to pass user info to upstream (empty to disable).                                                                                                |
| `OPENIDC_USER_HEADER_CLAIM`               | `sub`                  | multisite | 否     | ID token claim to use for the user header (e.g. sub, email, preferred_username).                                                                        |
| `OPENIDC_DISPLAY_CLAIM`                   | `preferred_username`   | multisite | 否     | Claim to use for display in logs and metrics (e.g. preferred_username, name, email). Falls back to User Header Claim if not found.                      |
| `OPENIDC_DISCOVERY_DICT_SIZE`             | `1m`                   | global    | 否     | Size of the shared dictionary to cache discovery data.                                                                                                  |
| `OPENIDC_JWKS_DICT_SIZE`                  | `1m`                   | global    | 否     | Size of the shared dictionary to cache JWKS data.                                                                                                       |

## PHP

STREAM 支持 :x:

PHP 插件为 BunkerWeb 提供了与 PHP-FPM 的无缝集成，从而为您的网站启用动态 PHP 处理。此功能支持在同一台机器上运行的本地 PHP-FPM 实例和远程 PHP-FPM 服务器，让您在配置 PHP 环境时拥有灵活性。

**工作原理：**

1.  当客户端从您的网站请求 PHP 文件时，BunkerWeb 会将请求路由到已配置的 PHP-FPM 实例。
2.  对于本地 PHP-FPM，BunkerWeb 通过 Unix 套接字文件与 PHP 解释器通信。
3.  对于远程 PHP-FPM，BunkerWeb 使用 FastCGI 协议将请求转发到指定的主机和端口。
4.  PHP-FPM 处理脚本并返回生成的内容给 BunkerWeb，然后由 BunkerWeb 将其交付给客户端。
5.  URL 重写会自动配置，以支持使用“美观 URL”的常见 PHP 框架和应用程序。

### 如何使用

请按照以下步骤配置和使用 PHP 功能：

1.  **选择您的 PHP-FPM 设置：** 决定您将使用本地还是远程 PHP-FPM 实例。
2.  **配置连接：** 对于本地 PHP，请指定套接字路径；对于远程 PHP，请提供主机名和端口。
3.  **设置文档根目录：** 使用适当的路径设置，配置包含您的 PHP 文件的根文件夹。
4.  **让 BunkerWeb 处理其余部分：** 配置完成后，BunkerWeb 会自动将 PHP 请求路由到您的 PHP-FPM 实例。

### 配置设置

| 设置              | 默认值 | 上下文    | 多选 | 描述                                                                          |
| ----------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
| `REMOTE_PHP`      |        | multisite | 否   | **远程 PHP 主机：** 远程 PHP-FPM 实例的主机名。留空以使用本地 PHP。           |
| `REMOTE_PHP_PATH` |        | multisite | 否   | **远程路径：** 远程 PHP-FPM 实例中包含文件的根文件夹。                        |
| `REMOTE_PHP_PORT` | `9000` | multisite | 否   | **远程端口：** 远程 PHP-FPM 实例的端口。                                      |
| `LOCAL_PHP`       |        | multisite | 否   | **本地 PHP 套接字：** PHP-FPM 套接字文件的路径。留空以使用远程 PHP-FPM 实例。 |
| `LOCAL_PHP_PATH`  |        | multisite | 否   | **本地路径：** 本地 PHP-FPM 实例中包含文件的根文件夹。                        |

!!! tip "本地与远程 PHP-FPM"
    选择最适合您基础架构的设置：

    -   **本地 PHP-FPM** 由于基于套接字的通信而提供更好的性能，并且在 PHP 与 BunkerWeb 在同一台机器上运行时是理想选择。
    -   **远程 PHP-FPM** 通过允许在单独的服务器上进行 PHP 处理，提供了更大的灵活性和可伸缩性。

!!! warning "路径配置"
    `REMOTE_PHP_PATH` 或 `LOCAL_PHP_PATH` 必须与存储 PHP 文件的实际文件系统路径匹配；否则，将发生“文件未找到”错误。

!!! info "URL 重写"
    PHP 插件会自动配置 URL 重写以支持现代 PHP 应用程序。对不存在的文件的请求将被定向到 `index.php`，原始请求 URI 将作为查询参数提供。

### 配置示例

=== "本地 PHP-FPM 配置"

    使用本地 PHP-FPM 实例的配置：

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "远程 PHP-FPM 配置"

    使用远程 PHP-FPM 实例的配置：

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "自定义端口配置"

    在非标准端口上使用 PHP-FPM 的配置：

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress 配置"

    为 WordPress 优化的配置：

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```

## Pro

STREAM 支持 :x:

Pro 插件为 BunkerWeb 的企业部署捆绑了高级功能和增强功能。它解锁了额外的功能、高级插件和扩展功能，以补充核心 BunkerWeb 平台。它为企业级部署提供了增强的安全性、性能和管理选项。

**工作原理：**

1.  使用有效的 Pro 许可证密钥，BunkerWeb 会连接到 Pro API 服务器以验证您的订阅。
2.  一旦通过身份验证，该插件会自动下载并安装 Pro 专属插件和扩展。
3.  您的 Pro 状态会定期验证，以确保您能持续访问高级功能。
4.  高级插件会无缝集成到您现有的 BunkerWeb 配置中。
5.  所有 Pro 功能都与开源核心协调工作，是增强而非取代功能。

!!! success "主要优势"

      1. **高级扩展：** 访问社区版中没有的专属插件和功能。
      2. **增强性能：** 优化的配置和高级缓存机制。
      3. **企业支持：** 优先协助和专属支持渠道。
      4. **无缝集成：** Pro 功能与社区功能并行工作，不会产生配置冲突。
      5. **自动更新：** 高级插件会自动下载并保持最新状态。

### 如何使用

请按照以下步骤配置和使用 Pro 功能：

1.  **获取许可证密钥：** 从 [BunkerWeb 面板](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) 购买 Pro 许可证。
2.  **配置您的许可证密钥：** 使用 `PRO_LICENSE_KEY` 设置来配置您的许可证。
3.  **让 BunkerWeb 处理其余部分：** 一旦配置了有效的许可证，Pro 插件将自动下载并激活。
4.  **监控您的 Pro 状态：** 在 [Web UI](web-ui.md) 中检查健康指示器，以确认您的 Pro 订阅状态。

### 配置设置

| 设置              | 默认值 | 上下文 | 多选 | 描述                                                           |
| ----------------- | ------ | ------ | ---- | -------------------------------------------------------------- |
| `PRO_LICENSE_KEY` |        | global | 否   | **Pro 许可证密钥：** 用于身份验证的 BunkerWeb Pro 许可证密钥。 |

!!! tip "许可证管理"
    您的 Pro 许可证与您的特定部署环境相关联。如果您需要转移许可证或对您的订阅有疑问，请通过 [BunkerWeb 面板](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) 联系支持。

!!! info "Pro 功能"
    随着新功能的增加，可用的具体 Pro 功能可能会随时间演变。Pro 插件会自动处理所有可用功能的安装和配置。

!!! warning "网络要求"
    Pro 插件需要出站互联网访问权限，以连接到 BunkerWeb API 进行许可证验证和下载高级插件。请确保您的防火墙允许连接到 `api.bunkerweb.io` 的 443 端口 (HTTPS)。

### 常见问题解答

**问：如果我的 Pro 许可证到期会怎样？**

答：如果您的 Pro 许可证到期，对高级功能和插件的访问将被禁用。但是，您的 BunkerWeb 安装将继续使用所有社区版功能正常运行。要重新获得对 Pro 功能的访问权限，只需续订您的许可证即可。

**问：Pro 功能会干扰我现有的配置吗？**

答：不会，Pro 功能旨在与您当前的 BunkerWeb 设置无缝集成。它们在不更改或干扰您现有配置的情况下增强功能，确保了平稳可靠的体验。

**问：我可以在购买前试用 Pro 功能吗？**

答：当然可以！BunkerWeb 提供两种 Pro 计划以满足您的需求：

- **BunkerWeb PRO Standard：** 完全访问 Pro 功能，但不提供技术支持。
- **BunkerWeb PRO Enterprise：** 完全访问 Pro 功能，并提供专属技术支持。

您可以使用促销码 `freetrial` 免费试用 Pro 功能 1 个月。请访问 [BunkerWeb 面板](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) 激活您的试用，并了解更多关于基于 BunkerWeb PRO 保护的服务数量的灵活定价选项。

## Prometheus exporter <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

Prometheus exporter for BunkerWeb internal metrics.

| 参数                           | 默认值                                                | 上下文 | 可重复 | 描述                                                                     |
| ------------------------------ | ----------------------------------------------------- | ------ | ------ | ------------------------------------------------------------------------ |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global | 否     | Enable the Prometheus export.                                            |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global | 否     | Listening IP of the Prometheus exporter.                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global | 否     | Listening port of the Prometheus exporter.                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global | 否     | HTTP URL of the Prometheus exporter.                                     |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global | 否     | List of IP/networks allowed to contact the Prometheus exporter endpoint. |

## Real IP

STREAM 支持 :warning:

Real IP 插件可确保 BunkerWeb 即使在代理后面也能正确识别客户端的 IP 地址。这对于正确应用安全规则、速率限制和日志记录至关重要；没有它，所有请求都将看起来来自您的代理 IP，而不是客户端的实际 IP。

**工作原理：**

1.  启用后，BunkerWeb 会检查传入请求中是否包含特定标头（如 [`X-Forwarded-For`](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)），这些标头包含客户端的原始 IP 地址。
2.  BunkerWeb 会检查传入的 IP 是否在您的受信任代理列表 (`REAL_IP_FROM`) 中，确保只有合法的代理才能传递客户端 IP。
3.  从指定的标头 (`REAL_IP_HEADER`) 中提取原始客户端 IP，并用于所有安全评估和日志记录。
4.  对于递归 IP 链，BunkerWeb 可以追溯多个代理跃点以确定始发客户端 IP。
5.  此外，可以启用 [PROXY 协议](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) 支持，以直接从兼容的代理（如 [HAProxy](https://www.haproxy.org/)）接收客户端 IP。
6.  受信任的代理 IP 列表可以通过 URL 从外部源自动下载和更新。

### 如何使用

请按照以下步骤配置和使用 Real IP 功能：

1.  **启用该功能：** 将 `USE_REAL_IP` 设置为 `yes` 以启用真实 IP 检测。
2.  **定义受信任的代理：** 使用 `REAL_IP_FROM` 设置列出您受信任的代理的 IP 地址或网络。
3.  **指定标头：** 使用 `REAL_IP_HEADER` 设置配置哪个标头包含真实 IP。
4.  **配置递归：** 使用 `REAL_IP_RECURSIVE` 设置决定是否递归地追溯 IP 链。
5.  **可选的 URL 源：** 使用 `REAL_IP_FROM_URLS` 设置自动下载受信任的代理列表。
6.  **PROXY 协议：** 对于直接的代理通信，如果您的上游支持，请使用 `USE_PROXY_PROTOCOL` 启用。

!!! danger "PROXY 协议警告"
    在未正确配置您的上游代理以发送 PROXY 协议标头的情况下启用 `USE_PROXY_PROTOCOL` 将**破坏您的应用程序**。仅当您确定您的上游代理已正确配置为发送 PROXY 协议信息时，才启用此设置。如果您的代理未发送 PROXY 协议标头，所有到 BunkerWeb 的连接都将因协议错误而失败。

### 配置设置

| 设置                 | 默认值                                    | 上下文    | 多选 | 描述                                                                                     |
| -------------------- | ----------------------------------------- | --------- | ---- | ---------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | 否   | **启用真实 IP：** 设置为 `yes` 以启用从标头或 PROXY 协议中检索客户端的真实 IP。          |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | 否   | **受信任的代理：** 代理请求来源的受信任 IP 地址或网络列表，以空格分隔。                  |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | 否   | **真实 IP 标头：** 包含真实 IP 的 HTTP 标头或用于 PROXY 协议的特殊值 `proxy_protocol`。  |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | 否   | **递归搜索：** 设置为 `yes` 时，在包含多个 IP 地址的标头中执行递归搜索。                 |
| `REAL_IP_FROM_URLS`  |                                           | multisite | 否   | **IP 列表 URL：** 包含要下载的受信任代理 IP/网络的 URL，以空格分隔。支持 file:// URL。   |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | 否   | **PROXY 协议：** 设置为 `yes` 以启用 PROXY 协议支持，用于直接的代理到 BunkerWeb 的通信。 |

!!! tip "云提供商网络"
    如果您正在使用像 AWS、GCP 或 Azure 这样的云提供商，请考虑将其负载均衡器的 IP 范围添加到您的 `REAL_IP_FROM` 设置中，以确保正确的客户端 IP 识别。

!!! danger "安全注意事项"
    仅在您的配置中包含受信任的代理 IP。添加不受信任的源可能会允许 IP 欺骗攻击，恶意行为者可以通过操纵标头来伪造客户端 IP。

!!! info "多个 IP 地址"
    当 `REAL_IP_RECURSIVE` 启用并且标头包含多个 IP（例如，`X-Forwarded-For: client, proxy1, proxy2`）时，BunkerWeb 会将不在您受信任代理列表中的最左侧 IP 识别为客户端 IP。

### 配置示例

=== "基本配置"

    一个用于位于反向代理后面的站点的简单配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "云负载均衡器"

    用于位于云负载均衡器后面的站点的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "PROXY 协议"

    使用 PROXY 协议与兼容的负载均衡器的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "带有 URL 的多个代理源"

    具有自动更新的代理 IP 列表的高级配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "CDN 配置"

    用于位于 CDN 后面的网站的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Cloudflare 示例
    REAL_IP_RECURSIVE: "no"  # 对于单个 IP 标头不需要
    ```

=== "位于 Cloudflare 后面"

    用于位于 Cloudflare 后面的网站的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # 我们只信任 Cloudflare 的 IP
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # 自动下载 Cloudflare IP
    REAL_IP_HEADER: "CF-Connecting-IP"  # Cloudflare 用于客户端 IP 的标头
    REAL_IP_RECURSIVE: "yes"
    ```

## Redirect

STREAM 支持 :x:

重定向插件为受 BunkerWeb 保护的网站提供了简单高效的 HTTP 重定向功能。此功能使您能够轻松地将访问者从一个 URL 重定向到另一个 URL，支持全域名重定向、特定路径重定向和路径保留重定向。

**工作原理：**

1.  当访问者访问您的网站时，BunkerWeb 会验证是否配置了重定向。
2.  如果启用，BunkerWeb 会将访问者重定向到指定的目标 URL。
3.  您可以配置是保留原始请求路径（自动将其附加到目标 URL）还是重定向到确切的目标 URL。
4.  用于重定向的 HTTP 状态码可以在永久（301）和临时（302）重定向之间进行自定义。
5.  此功能非常适用于域名迁移、建立规范域名或重定向已弃用的 URL。

### 如何使用

请按照以下步骤配置和使用重定向功能：

1.  **设置源路径：** 使用 `REDIRECT_FROM` 设置配置要重定向的路径（例如 `/`、`/old-page`）。
2.  **设置目标 URL：** 使用 `REDIRECT_TO` 设置配置访问者应被重定向到的目标 URL。
3.  **选择重定向类型：** 使用 `REDIRECT_TO_REQUEST_URI` 设置决定是否保留原始请求路径。
4.  **选择状态码：** 使用 `REDIRECT_TO_STATUS_CODE` 设置设置适当的 HTTP 状态码，以指示是永久重定向还是临时重定向。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，所有对该站点的请求都将根据您的设置自动重定向。

### 配置设置

| 设置                      | 默认值 | 上下文    | 多选 | 描述                                                                                    |
| ------------------------- | ------ | --------- | ---- | --------------------------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`    | multisite | 是   | **要重定向的源路径：** 将被重定向的路径。                                               |
| `REDIRECT_TO`             |        | multisite | 是   | **目标 URL：** 访问者将被重定向到的目标 URL。留空以禁用重定向。                         |
| `REDIRECT_TO_REQUEST_URI` | `no`   | multisite | 是   | **保留路径：** 设置为 `yes` 时，将原始请求 URI 附加到目标 URL。                         |
| `REDIRECT_TO_STATUS_CODE` | `301`  | multisite | 是   | **HTTP 状态码：** 用于重定向的 HTTP 状态码。选项：`301`、`302`、`303`、`307` 或 `308`。 |

!!! tip "选择正确的状态码"
    - **`301`（永久移动）：** 永久重定向，被浏览器缓存。可能将 POST 更改为 GET。适用于域名迁移。
    - **`302`（找到）：** 临时重定向。可能将 POST 更改为 GET。
    - **`303`（参见其他）：** 始终使用 GET 方法重定向。适用于表单提交后的重定向。
    - **`307`（临时重定向）：** 保留 HTTP 方法的临时重定向。适用于 API 重定向。
    - **`308`（永久重定向）：** 保留 HTTP 方法的永久重定向。适用于永久性 API 端点迁移。

!!! info "路径保留"
    当 `REDIRECT_TO_REQUEST_URI` 设置为 `yes` 时，BunkerWeb 会保留原始请求路径。例如，如果用户访问 `https://old-domain.com/blog/post-1`，并且您已设置为重定向到 `https://new-domain.com`，他们将被重定向到 `https://new-domain.com/blog/post-1`。

### 配置示例

=== "多路径重定向"

    一个将多个路径重定向到不同目标的配置：

    ```yaml
    # 将 /blog 重定向到一个新的博客域名
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    # 将 /shop 重定向到另一个域名
    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    # 重定向网站的其余部分
    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "简单域名重定向"

    一个将所有访问者重定向到一个新域名的配置：

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "保留路径的重定向"

    一个将访问者重定向到一个新域名，同时保留所请求路径的配置：

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "临时重定向"

    一个用于临时重定向到维护站点的配置：

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "子域名整合"

    一个将子域名重定向到主域名上特定路径的配置：

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "API 端点迁移"

    永久重定向 API 端点并保留 HTTP 方法的配置：

    ```yaml
    REDIRECT_FROM: "/api/v1/"
    REDIRECT_TO: "https://api.example.com/v2/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "308"
    ```

=== "表单提交后重定向"

    使用 GET 方法在表单提交后重定向的配置：

    ```yaml
    REDIRECT_TO: "https://example.com/thank-you"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "303"
    ```

## Redis

STREAM 支持 :white_check_mark:

Redis 插件将 [Redis](https://redis.io/) 或 [Valkey](https://valkey.io/) 集成到 BunkerWeb 中，用于缓存和快速数据检索。此功能对于在需要跨多个节点访问会话数据、指标和其他共享信息的高可用性环境中部署 BunkerWeb 至关重要。

**工作原理：**

1.  启用后，BunkerWeb 会与您配置的 Redis 或 Valkey 服务器建立连接。
2.  会话信息、指标和安全相关数据等关键数据存储在 Redis/Valkey 中。
3.  多个 BunkerWeb 实例可以共享这些数据，从而实现无缝集群和负载均衡。
4.  该插件支持各种 Redis/Valkey 部署选项，包括独立服务器、密码验证、SSL/TLS 加密和用于高可用性的 Redis Sentinel。
5.  自动重新连接和可配置的超时可确保在生产环境中的稳健性。

### 如何使用

请按照以下步骤配置和使用 Redis 插件：

1.  **启用该功能：** 将 `USE_REDIS` 设置为 `yes` 以启用 Redis/Valkey 集成。
2.  **配置连接详细信息：** 指定您的 Redis/Valkey 服务器的主机名/IP 地址和端口。
3.  **设置安全选项：** 如果您的 Redis/Valkey 服务器需要，请配置身份验证凭据。
4.  **配置高级选项：** 根据需要设置数据库选择、SSL 选项和超时。
5.  **对于高可用性，**如果您正在使用 Redis Sentinel，请配置 Sentinel 设置。

### 配置设置

| 设置                      | 默认值     | 上下文 | 多选 | 描述                                                                             |
| ------------------------- | ---------- | ------ | ---- | -------------------------------------------------------------------------------- |
| `USE_REDIS`               | `no`       | global | 否   | **启用 Redis：** 设置为 `yes` 以启用 Redis/Valkey 集成以用于集群模式。           |
| `REDIS_HOST`              |            | global | 否   | **Redis/Valkey 服务器：** Redis/Valkey 服务器的 IP 地址或主机名。                |
| `REDIS_PORT`              | `6379`     | global | 否   | **Redis/Valkey 端口：** Redis/Valkey 服务器的端口号。                            |
| `REDIS_DATABASE`          | `0`        | global | 否   | **Redis/Valkey 数据库：** 在 Redis/Valkey 服务器上使用的数据库编号 (0-15)。      |
| `REDIS_SSL`               | `no`       | global | 否   | **Redis/Valkey SSL：** 设置为 `yes` 以启用 Redis/Valkey 连接的 SSL/TLS 加密。    |
| `REDIS_SSL_VERIFY`        | `yes`      | global | 否   | **Redis/Valkey SSL 验证：** 设置为 `yes` 以验证 Redis/Valkey 服务器的 SSL 证书。 |
| `REDIS_TIMEOUT`           | `5`        | global | 否   | **Redis/Valkey 超时：** Redis/Valkey 操作的连接超时时间（秒）。                  |
| `REDIS_USERNAME`          |            | global | 否   | **Redis/Valkey 用户名：** 用于 Redis/Valkey 身份验证的用户名 (Redis 6.0+)。      |
| `REDIS_PASSWORD`          |            | global | 否   | **Redis/Valkey 密码：** 用于 Redis/Valkey 身份验证的密码。                       |
| `REDIS_SENTINEL_HOSTS`    |            | global | 否   | **Sentinel 主机：** Redis Sentinel 主机的空格分隔列表 (hostname:port)。          |
| `REDIS_SENTINEL_USERNAME` |            | global | 否   | **Sentinel 用户名：** 用于 Redis Sentinel 身份验证的用户名。                     |
| `REDIS_SENTINEL_PASSWORD` |            | global | 否   | **Sentinel 密码：** 用于 Redis Sentinel 身份验证的密码。                         |
| `REDIS_SENTINEL_MASTER`   | `mymaster` | global | 否   | **Sentinel 主节点：** Redis Sentinel 配置中主节点的名称。                        |
| `REDIS_KEEPALIVE_IDLE`    | `300`      | global | 否   | **Keepalive 空闲时间：** 空闲连接的 TCP keepalive 探测之间的时间（秒）。         |
| `REDIS_KEEPALIVE_POOL`    | `3`        | global | 否   | **Keepalive 池：** 池中保留的最大 Redis/Valkey 连接数。                          |

!!! tip "使用 Redis Sentinel 实现高可用性"
    对于需要高可用性的生产环境，请配置 Redis Sentinel 设置。如果主 Redis 服务器不可用，这将提供自动故障转移功能。

!!! warning "安全注意事项"
    在生产环境中使用 Redis 时：

    -   始终为 Redis 和 Sentinel 身份验证设置强密码
    -   考虑为 Redis 连接启用 SSL/TLS 加密
    -   确保您的 Redis 服务器未暴露于公共互联网
    -   使用防火墙或网络分段限制对 Redis 端口的访问

!!! info "集群要求"
    在集群中部署 BunkerWeb 时：

    -   所有 BunkerWeb 实例都应连接到相同的 Redis 或 Valkey 服务器或 Sentinel 集群
    -   在所有实例中配置相同的数据库编号
    -   确保所有 BunkerWeb 实例与 Redis/Valkey 服务器之间的网络连接

### 配置示例

=== "基本配置"

    一个用于连接到本地计算机上的 Redis 或 Valkey 服务器的简单配置：

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "安全配置"

    启用了密码身份验证和 SSL 的配置：

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Redis Sentinel 配置"

    使用 Redis Sentinel 实现高可用性的配置：

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "高级调优"

    具有用于性能优化的高级连接参数的配置：

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

### Redis 最佳实践

在使用 Redis 或 Valkey 与 BunkerWeb 时，请考虑以下最佳实践以确保最佳性能、安全性和可靠性：

#### 内存管理

- **监控内存使用情况：** 使用适当的 `maxmemory` 设置配置 Redis，以防止内存不足错误
- **设置淘汰策略：** 使用适合您用例的 `maxmemory-policy`（例如 `volatile-lru` 或 `allkeys-lru`）
- **避免大键：** 确保将单个 Redis 键保持在合理的大小，以防止性能下降

#### 数据持久性

- **启用 RDB 快照：** 配置定期快照以实现数据持久性，而不会对性能产生重大影响
- **考虑 AOF：** 对于关键数据，启用具有适当 fsync 策略的 AOF（仅追加文件）持久性
- **备份策略：** 将定期 Redis 备份作为灾难恢复计划的一部分

#### 性能优化

- **连接池：** BunkerWeb 已经实现了这一点，但请确保其他应用程序遵循此实践
- **管道：** 如果可能，请使用管道进行批量操作以减少网络开销
- **避免昂贵的操作：** 在生产环境中谨慎使用像 KEYS 这样的命令
- **对您的工作负载进行基准测试：** 使用 redis-benchmark 测试您的特定工作负载模式

### 更多资源

- [Redis 文档](https://redis.io/documentation)
- [Redis 安全指南](https://redis.io/topics/security)
- [Redis 高可用性](https://redis.io/topics/sentinel)
- [Redis 持久性](https://redis.io/topics/persistence)

## Reporting <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


STREAM 支持 :x:

Regular reporting of important data from BunkerWeb (global, attacks, bans, requests, reasons, AS...). Monitoring pro plugin needed to work.

| 参数                           | 默认值             | 上下文 | 可重复 | 描述                                                                                                                               |
| ------------------------------ | ------------------ | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global | 否     | Enable sending the report via email.                                                                                               |
| `USE_REPORTING_WEBHOOK`        | `no`               | global | 否     | Enable sending the report via webhook.                                                                                             |
| `REPORTING_SCHEDULE`           | `weekly`           | global | 否     | The frequency at which reports are sent.                                                                                           |
| `REPORTING_WEBHOOK_URLS`       |                    | global | 否     | List of webhook URLs to receive the report in Markdown (separated by spaces).                                                      |
| `REPORTING_SMTP_EMAILS`        |                    | global | 否     | List of email addresses to receive the report in HTML format (separated by spaces).                                                |
| `REPORTING_SMTP_HOST`          |                    | global | 否     | The host server used for SMTP sending.                                                                                             |
| `REPORTING_SMTP_PORT`          | `465`              | global | 否     | The port used for SMTP. Please note that there are different standards depending on the type of connection (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global | 否     | The email address used as the sender. Note that 2FA must be disabled for this email address.                                       |
| `REPORTING_SMTP_FROM_USER`     |                    | global | 否     | The user authentication value for sending via the from email address.                                                              |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global | 否     | The password authentication value for sending via the from email address.                                                          |
| `REPORTING_SMTP_SSL`           | `SSL`              | global | 否     | Determine whether or not to use a secure connection for SMTP.                                                                      |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global | 否     | The subject line of the email.                                                                                                     |

## Reverse proxy

STREAM 支持 :warning:

反向代理插件为 BunkerWeb 提供了无缝的代理功能，允许您将请求路由到后端服务器和服务。此功能使 BunkerWeb 能够充当您应用程序的安全前端，同时提供 SSL 终止和安全过滤等额外的好处。

**工作原理：**

1.  当客户端向 BunkerWeb 发送请求时，反向代理插件会将请求转发到您配置的后端服务器。
2.  在将请求传递给您的应用程序之前，BunkerWeb 会添加安全标头、应用 WAF 规则并执行其他安全检查。
3.  后端服务器处理请求并向 BunkerWeb 返回响应。
4.  BunkerWeb 在将响应发送回客户端之前，会对响应应用额外的安全措施。
5.  该插件支持 HTTP 和 TCP/UDP 流代理，从而支持包括 WebSockets 和其他非 HTTP 协议在内的广泛应用。

### 如何使用

请按照以下步骤配置和使用反向代理功能：

1.  **启用该功能：** 将 `USE_REVERSE_PROXY` 设置为 `yes` 以启用反向代理功能。
2.  **配置您的后端服务器：** 使用 `REVERSE_PROXY_HOST` 设置指定上游服务器。
3.  **调整代理设置：** 使用超时、缓冲区大小和其他参数的可选设置来微调行为。
4.  **配置特定于协议的选项：** 对于 WebSockets 或特殊的 HTTP 要求，请调整相应的设置。
5.  **设置缓存（可选）：** 启用和配置代理缓存，以提高频繁访问内容的性能。

### 配置指南

=== "基本配置"

    **核心设置**

    基本的配置设置启用并控制反向代理功能的基本功能。

    !!! success "反向代理的好处"
        - **安全增强：** 所有流量在到达您的应用程序之前都会经过 BunkerWeb 的安全层
        - **SSL 终止：** 集中管理 SSL/TLS 证书，而后端服务可以使用未加密的连接
        - **协议处理：** 支持 HTTP、HTTPS、WebSockets 和其他协议
        - **错误拦截：** 自定义错误页面以获得一致的用户体验

    | 设置                             | 默认值 | 上下文    | 多选 | 描述                                                 |
    | -------------------------------- | ------ | --------- | ---- | ---------------------------------------------------- |
    | `USE_REVERSE_PROXY`              | `no`   | multisite | 否   | **启用反向代理：** 设置为 `yes` 以启用反向代理功能。 |
    | `REVERSE_PROXY_HOST`             |        | multisite | 是   | **后端主机：** 代理资源的完整 URL (proxy_pass)。     |
    | `REVERSE_PROXY_URL`              | `/`    | multisite | 是   | **位置 URL：** 将被代理到后端服务器的路径。          |
    | `REVERSE_PROXY_BUFFERING`        | `yes`  | multisite | 是   | **响应缓冲：** 启用或禁用来自代理资源的响应缓冲。    |
    | `REVERSE_PROXY_KEEPALIVE`        | `no`   | multisite | 是   | **保持连接：** 启用或禁用与代理资源的保持连接。      |
    | `REVERSE_PROXY_CUSTOM_HOST`      |        | multisite | 否   | **自定义主机：** 覆盖发送到上游服务器的 Host 标头。  |
    | `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`  | multisite | 否   | **拦截错误：** 是否拦截和重写来自后端的错误响应。    |

    !!! tip "最佳实践"
        - 始终在 `REVERSE_PROXY_HOST` 中指定完整的 URL，包括协议（http:// 或 https://）
        - 使用 `REVERSE_PROXY_INTERCEPT_ERRORS` 在您所有服务中提供一致的错误页面
        - 当配置多个后端时，使用带编号的后缀格式（例如，`REVERSE_PROXY_HOST_2`、`REVERSE_PROXY_URL_2`）

=== "连接设置"

    **连接和超时配置**

    这些设置控制代理连接的连接行为、缓冲和超时值。

    !!! success "好处"
        - **优化性能：** 根据您的应用程序需求调整缓冲区大小和连接设置
        - **资源管理：** 通过适当的缓冲区配置控制内存使用
        - **可靠性：** 配置适当的超时以处理慢速连接或后端问题

    | 设置                            | 默认值 | 上下文    | 多选 | 描述                                                            |
    | ------------------------------- | ------ | --------- | ---- | --------------------------------------------------------------- |
    | `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`  | multisite | 是   | **连接超时：** 建立到后端服务器连接的最长时间。                 |
    | `REVERSE_PROXY_READ_TIMEOUT`    | `60s`  | multisite | 是   | **读取超时：** 从后端服务器传输两个连续数据包之间的最长时间。   |
    | `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`  | multisite | 是   | **发送超时：** 向后端服务器传输两个连续数据包之间的最长时间。   |
    | `PROXY_BUFFERS`                 |        | multisite | 否   | **缓冲区：** 用于从后端服务器读取响应的缓冲区的数量和大小。     |
    | `PROXY_BUFFER_SIZE`             |        | multisite | 否   | **缓冲区大小：** 用于从后端服务器读取响应第一部分的大小。       |
    | `PROXY_BUSY_BUFFERS_SIZE`       |        | multisite | 否   | **繁忙缓冲区大小：** 可用于向客户端发送响应的繁忙缓冲区的大小。 |

    !!! warning "超时注意事项"
        - 设置过低的超时可能会导致合法但缓慢的连接被终止
        - 设置过高的超时可能会不必要地保持连接打开，从而可能耗尽资源
        - 对于 WebSocket 应用程序，请显著增加读取和发送超时（建议 300 秒或更长）

=== "SSL/TLS 配置"

    **后端连接的 SSL/TLS 设置**

    这些设置控制 BunkerWeb 如何与后端服务器建立安全连接。

    !!! success "好处"
        - **端到端加密：** 保持从客户端到后端的加密连接
        - **证书验证：** 控制如何验证后端服务器证书
        - **SNI 支持：** 为托管多个站点的后端指定服务器名称指示

    | 设置                         | 默认值 | 上下文    | 多选 | 描述                                                                  |
    | ---------------------------- | ------ | --------- | ---- | --------------------------------------------------------------------- |
    | `REVERSE_PROXY_SSL_SNI`      | `no`   | multisite | 否   | **SSL SNI：** 启用或禁用向上游发送 SNI（服务器名称指示）。            |
    | `REVERSE_PROXY_SSL_SNI_NAME` |        | multisite | 否   | **SSL SNI 名称：** 当启用 SSL SNI 时，设置要发送到上游的 SNI 主机名。 |

    !!! info "SNI 解释"
        服务器名称指示 (SNI) 是 TLS 的一个扩展，它允许客户端在握手过程中指定它试图连接的主机名。这使服务器能够在同一个 IP 地址和端口上呈现多个证书，从而允许从单个 IP 地址提供多个安全 (HTTPS) 网站，而无需所有这些网站都使用相同的证书。

=== "协议支持"

    **协议特定配置**

    配置特殊的协议处理，特别是对于 WebSockets 和其他非 HTTP 协议。

    !!! success "好处"
        - **协议灵活性：** 支持 WebSockets 使实时应用程序成为可能
        - **现代 Web 应用：** 启用需要双向通信的交互式功能

    | 设置               | 默认值 | 上下文    | 多选 | 描述                                               |
    | ------------------ | ------ | --------- | ---- | -------------------------------------------------- |
    | `REVERSE_PROXY_WS` | `no`   | multisite | 是   | **WebSocket 支持：** 在资源上启用 WebSocket 协议。 |

    !!! tip "WebSocket 配置"
        - 当使用 `REVERSE_PROXY_WS: "yes"` 启用 WebSockets 时，请考虑增加超时值
        - WebSocket 连接的保持时间比典型的 HTTP 连接更长
        - 对于 WebSocket 应用程序，推荐的配置是：
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "标头管理"

    **HTTP 标头配置**

    控制哪些标头发送到后端服务器和客户端，允许您添加、修改或保留 HTTP 标头。

    !!! success "好处"
        - **信息控制：** 精确管理在客户端和后端之间共享的信息
        - **安全增强：** 添加与安全相关的标头或删除可能泄露敏感信息的标头
        - **集成支持：** 为身份验证和正常的后端操作提供必要的标头

    | 设置                                   | 默认值    | 上下文    | 多选 | 描述                                                              |
    | -------------------------------------- | --------- | --------- | ---- | ----------------------------------------------------------------- |
    | `REVERSE_PROXY_HEADERS`                |           | multisite | 是   | **自定义标头：** 发送到后端的 HTTP 标头，用分号分隔。             |
    | `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade` | multisite | 是   | **隐藏标头：** 从后端接收时向客户端隐藏的 HTTP 标头。             |
    | `REVERSE_PROXY_HEADERS_CLIENT`         |           | multisite | 是   | **客户端标头：** 发送给客户端的 HTTP 标头，用分号分隔。           |
    | `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`      | multisite | 否   | **标头中使用下划线：** 启用或禁用 `underscores_in_headers` 指令。 |

    !!! warning "安全注意事项"
        使用反向代理功能时，请谨慎转发哪些标头到您的后端应用程序。某些标头可能会暴露有关您的基础架构的敏感信息或绕过安全控制。

    !!! example "标头格式示例"
        发送到后端服务器的自定义标头：
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        发送给客户端的自定义标头：
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "认证"

    **外部认证配置**

    与外部认证系统集成，以集中管理您应用程序的授权逻辑。

    !!! success "好处"
        - **集中式认证：** 为多个应用程序实现单一认证点
        - **一致的安全性：** 在不同服务之间应用统一的认证策略
        - **增强的控制：** 通过标头或变量将认证详细信息转发到后端应用程序

    | 设置                                    | 默认值 | 上下文    | 多选 | 描述                                                    |
    | --------------------------------------- | ------ | --------- | ---- | ------------------------------------------------------- |
    | `REVERSE_PROXY_AUTH_REQUEST`            |        | multisite | 是   | **认证请求：** 使用外部提供商启用认证。                 |
    | `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |        | multisite | 是   | **登录 URL：** 当认证失败时，将客户端重定向到登录 URL。 |
    | `REVERSE_PROXY_AUTH_REQUEST_SET`        |        | multisite | 是   | **认证请求设置：** 从认证提供商设置的变量。             |

    !!! tip "认证集成"
        - 认证请求功能可以实现集中式认证微服务
        - 您的认证服务应在成功认证时返回 200 状态码，失败时返回 401/403
        - 使用 auth_request_set 指令从认证服务中提取并转发信息

=== "高级配置"

    **附加配置选项**

    这些设置为特殊场景提供了对反向代理行为的进一步定制。

    !!! success "好处"
        - **定制化：** 为复杂需求包含额外的配置片段
        - **性能优化：** 针对特定用例微调请求处理
        - **灵活性：** 通过专门的配置适应独特的应用程序需求

    | 设置                              | 默认值 | 上下文    | 多选 | 描述                                            |
    | --------------------------------- | ------ | --------- | ---- | ----------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |        | multisite | 是   | **附加配置：** 在 location 块中包含额外的配置。 |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`  | multisite | 是   | **传递请求体：** 启用或禁用传递请求体。         |

    !!! warning "安全注意事项"
        包含自定义配置片段时请小心，因为如果配置不当，它们可能会覆盖 BunkerWeb 的安全设置或引入漏洞。

=== "缓存配置"

    **响应缓存设置**

    通过缓存来自后端服务器的响应来提高性能，减少负载并改善响应时间。

    !!! success "好处"
        - **性能：** 通过提供缓存内容来减少后端服务器的负载
        - **减少延迟：** 对频繁请求的内容响应时间更快
        - **节省带宽：** 通过缓存响应来最小化内部网络流量
        - **定制化：** 精确配置缓存的内容、时间和方式

    | 设置                         | 默认值                             | 上下文    | 多选 | 描述                                                    |
    | ---------------------------- | ---------------------------------- | --------- | ---- | ------------------------------------------------------- |
    | `USE_PROXY_CACHE`            | `no`                               | multisite | 否   | **启用缓存：** 设置为 `yes` 以启用后端响应的缓存。      |
    | `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | 否   | **缓存路径级别：** 如何构建缓存目录层次结构。           |
    | `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | 否   | **缓存区域大小：** 用于缓存元数据的共享内存区域的大小。 |
    | `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | 否   | **缓存路径参数：** 缓存路径的附加参数。                 |
    | `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | 否   | **缓存方法：** 可以被缓存的 HTTP 方法。                 |
    | `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | 否   | **缓存最小使用次数：** 响应被缓存前的最小请求次数。     |
    | `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | 否   | **缓存键：** 用于唯一标识缓存响应的键。                 |
    | `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | 否   | **缓存有效期：** 特定响应码的缓存时间。                 |
    | `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | 否   | **不缓存：** 即使通常可缓存也不缓存响应的条件。         |
    | `PROXY_CACHE_BYPASS`         | `0`                                | multisite | 否   | **绕过缓存：** 绕过缓存的条件。                         |

    !!! tip "缓存最佳实践"
        - 只缓存不经常更改或非个性化的内容
        - 根据内容类型使用适当的缓存持续时间（静态资源可以缓存更长时间）
        - 配置 `PROXY_NO_CACHE` 以避免缓存敏感或个性化内容
        - 监控缓存命中率并相应地调整设置

!!! danger "Docker Compose 用户 - NGINX 变量"
    当在 Docker Compose 中使用 NGINX 变量进行配置时，您必须通过使用双美元符号 (`$$`) 来转义美元符号 (`$`)。这适用于所有包含 NGINX 变量的设置，如 `$remote_addr`、`$proxy_add_x_forwarded_for` 等。

    如果不进行此转义，Docker Compose 将尝试用环境变量替换这些变量，而这些环境变量通常不存在，导致您的 NGINX 配置中出现空值。

### 配置示例

=== "基本 HTTP 代理"

    一个用于将 HTTP 请求代理到后端应用服务器的简单配置：

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "WebSocket 应用"

    为 WebSocket 应用程序优化的配置，具有更长的超时时间：

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "多个位置"

    将不同路径路由到不同后端服务的配置：

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # API 后端
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # 管理后端
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # 前端应用
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "缓存配置"

    启用了代理缓存以提高性能的配置：

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "高级标头管理"

    具有自定义标头操作的配置：

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # 发送到后端的自定义标头
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # 发送给客户端的自定义标头
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "认证集成"

    与外部认证集成的配置：

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # 认证配置
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # 认证服务后端
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```

## Reverse scan

STREAM 支持 :white_check_mark:

反向扫描插件通过扫描客户端端口来检测其是否正在运行代理服务器或其他网络服务，从而有力地防止代理绕过企图。此功能有助于识别和阻止可能试图隐藏其真实身份或来源的客户端带来的潜在威胁，从而增强您网站的安全状况。

**工作原理：**

1.  当客户端连接到您的服务器时，BunkerWeb 会尝试扫描客户端 IP 地址上的特定端口。
2.  该插件会检查客户端上是否有任何常见的代理端口（例如 80、443、8080 等）处于打开状态。
3.  如果检测到打开的端口，表明客户端可能正在运行代理服务器，则连接将被拒绝。
4.  这为防止自动化工具、机器人和试图掩盖其身份的恶意用户增加了一层额外的安全保障。

!!! success "主要优势"

      1. **增强安全性：** 识别可能运行用于恶意目的的代理服务器的客户端。
      2. **代理检测：** 帮助检测并阻止试图隐藏其真实身份的客户端。
      3. **可配置设置：** 根据您的特定安全要求自定义要扫描的端口。
      4. **性能优化：** 智能扫描，具有可配置的超时，以最大限度地减少对合法用户的影响。
      5. **无缝集成：** 与您现有的安全层透明地协同工作。

### 如何使用

请按照以下步骤配置和使用反向扫描功能：

1.  **启用该功能：** 将 `USE_REVERSE_SCAN` 设置为 `yes` 以启用客户端端口扫描。
2.  **配置要扫描的端口：** 自定义 `REVERSE_SCAN_PORTS` 设置以指定应检查哪些客户端端口。
3.  **设置扫描超时：** 调整 `REVERSE_SCAN_TIMEOUT` 以在彻底扫描和性能之间取得平衡。
4.  **监控扫描活动：** 检查日志和 [Web UI](web-ui.md) 以审查扫描结果和潜在的安全事件。

### 配置设置

| 设置                   | 默认值                     | 上下文    | 多选 | 描述                                                    |
| ---------------------- | -------------------------- | --------- | ---- | ------------------------------------------------------- |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | 否   | **启用反向扫描：** 设置为 `yes` 以启用客户端端口扫描。  |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | 否   | **要扫描的端口：** 要在客户端检查的端口的空格分隔列表。 |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | 否   | **扫描超时：** 允许扫描端口的最长时间（毫秒）。         |

!!! warning "性能注意事项"
    扫描多个端口会增加客户端连接的延迟。请使用适当的超时值并限制扫描的端口数量以保持良好的性能。

!!! info "常见代理端口"
    默认配置包括代理服务器（80、443、8080、3128）和 SSH（22）使用的常见端口。您可能需要根据您的威胁模型自定义此列表。

### 配置示例

=== "基本配置"

    一个用于启用客户端端口扫描的简单配置：

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "全面扫描"

    一个更彻底的配置，检查其他端口：

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "性能优化配置"

    通过检查更少的端口和更低的超时来调整以获得更好性能的配置：

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "高安全性配置"

    专注于最大安全性并进行扩展扫描的配置：

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```

## Robots.txt

STREAM 支持 :white_check_mark:

Robots.txt 插件为您的网站管理 [robots.txt](https://www.robotstxt.org/) 文件。此文件告知网络爬虫和机器人它们可以或不可以访问您网站的哪些部分。

**工作原理：**

启用后，BunkerWeb 会在您网站的根目录下动态生成 `/robots.txt` 文件。此文件中的规则按以下顺序从多个来源聚合而成：

1.  **DarkVisitors API：** 如果提供了 `ROBOTSTXT_DARKVISITORS_TOKEN`，规则将从 [DarkVisitors](https://darkvisitors.com/) API 获取，从而可以根据配置的代理类型和不允许的用户代理动态阻止恶意机器人和 AI 爬虫。
2.  **社区列表：** 包含来自预定义、社区维护的 `robots.txt` 列表（由 `ROBOTSTXT_COMMUNITY_LISTS` 指定）的规则。
3.  **自定义 URL：** 规则从用户提供的 URL（由 `ROBOTSTXT_URLS` 指定）获取。
4.  **手动规则：** 添加直接通过 `ROBOTSTXT_RULE` 环境变量定义的规则。

所有这些来源的规则都会被合并。聚合后，将应用 `ROBOTSTXT_IGNORE_RULE` 来使用 PCRE 正则表达式模式过滤掉任何不需要的规则。最后，如果整个过程后没有任何规则剩下，将自动应用默认的 `User-agent: *` 和 `Disallow: /` 规则，以确保基本级别的保护。可选的站点地图 URL（由 `ROBOTSTXT_SITEMAP` 指定）也会包含在最终的 `robots.txt` 输出中。

### 使用 DarkVisitors API 动态规避机器人

[DarkVisitors](https://darkvisitors.com/) 是一项提供动态 `robots.txt` 文件的服务，以帮助阻止已知的恶意机器人和 AI 爬虫。通过与 DarkVisitors 集成，BunkerWeb 可以自动获取并提供最新的 `robots.txt`，帮助保护您的网站免受不必要的自动化流量。

要启用此功能，您需要在 [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) 注册并获取一个 bearer 令牌。

### 如何使用

1.  **启用该功能：** 将 `USE_ROBOTSTXT` 设置为 `yes`。
2.  **配置规则：** 选择一种或多种方法来定义您的 `robots.txt` 规则：
    - **DarkVisitors API：** 提供 `ROBOTSTXT_DARKVISITORS_TOKEN`，并可选择性地提供 `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` 和 `ROBOTSTXT_DARKVISITORS_DISALLOW`。
    - **社区列表：** 指定 `ROBOTSTXT_COMMUNITY_LISTS`（以空格分隔的 ID）。
    - **自定义 URL：** 提供 `ROBOTSTXT_URLS`（以空格分隔的 URL）。
    - **手动规则：** 使用 `ROBOTSTXT_RULE` 定义单个规则（可以使用 `ROBOTSTXT_RULE_N` 指定多个规则）。
3.  **过滤规则（可选）：** 使用 `ROBOTSTXT_IGNORE_RULE_N` 通过正则表达式模式排除特定规则。
4.  **添加站点地图（可选）：** 使用 `ROBOTSTXT_SITEMAP_N` 定义站点地图 URL。
5.  **获取生成的 robots.txt 文件：** 在 BunkerWeb 使用上述设置运行后，您可以通过向 `http(s)://your-domain.com/robots.txt` 发出 HTTP GET 请求来访问动态生成的 `robots.txt` 文件。

### 配置设置

| 设置                                 | 默认值 | 上下文    | 多选 | 描述                                                                                                          |
| ------------------------------------ | ------ | --------- | ---- | ------------------------------------------------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`   | multisite | 否   | 启用或禁用 `robots.txt` 功能。                                                                                |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |        | multisite | 否   | 用于 DarkVisitors API 的 Bearer 令牌。                                                                        |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |        | multisite | 否   | 从 DarkVisitors 包含的代理类型（例如 `AI Data Scraper`）的逗号分隔列表。                                      |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`    | multisite | 否   | 指定不允许哪些 URL 的字符串。在联系 DarkVisitors API 时，此值将作为 disallow 字段发送。                       |
| `ROBOTSTXT_COMMUNITY_LISTS`          |        | multisite | 否   | 要包含的社区维护规则集 ID 的空格分隔列表。                                                                    |
| `ROBOTSTXT_URLS`                     |        | multisite | 否   | 用于获取额外 `robots.txt` 规则的 URL 的空格分隔列表。支持 `file://` 和基本身份验证 (`http://user:pass@url`)。 |
| `ROBOTSTXT_RULE`                     |        | multisite | 是   | `robots.txt` 的单条规则。                                                                                     |
| `ROBOTSTXT_HEADER`                   |        | multisite | 是   | `robots.txt` 文件的页眉（在规则之前）。可以是 Base64 编码。                                                   |
| `ROBOTSTXT_FOOTER`                   |        | multisite | 是   | `robots.txt` 文件的页脚（在规则之后）。可以是 Base64 编码。                                                   |
| `ROBOTSTXT_IGNORE_RULE`              |        | multisite | 是   | 用于忽略规则的单个 PCRE 正则表达式模式。                                                                      |
| `ROBOTSTXT_SITEMAP`                  |        | multisite | 是   | 单个站点地图 URL。                                                                                            |

### 配置示例

**基本手动规则**

````yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"```

**使用动态源 (DarkVisitors & 社区列表)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTT_IGNORE_RULE: "User-agent: Googlebot-Image"
````

**组合配置**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**带页眉和页脚**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# 这是一个自定义页眉"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# 这是一个自定义页脚"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

---

更多信息，请参阅 [robots.txt 文档](https://www.robotstxt.org/robotstxt.html)。

## SSL

STREAM 支持 :white_check_mark:

SSL 插件为您的 BunkerWeb 保护的网站提供强大的 SSL/TLS 加密功能。这个核心组件通过配置和优化加密协议、密码套件以及相关的安全设置来启用安全的 HTTPS 连接，以保护客户端和您的 Web 服务之间传输中的数据。

**工作原理：**

1.  当客户端向您的网站发起 HTTPS 连接时，BunkerWeb 会使用您配置的设置处理 SSL/TLS 握手。
2.  该插件强制使用现代加密协议和强大的密码套件，同时禁用已知的易受攻击的选项。
3.  优化的 SSL 会话参数可在不牺牲安全性的情况下提高连接性能。
4.  证书的呈现根据最佳实践进行配置，以确保兼容性和安全性。

!!! success "安全优势" - **数据保护：** 加密传输中的数据，防止窃听和中间人攻击 - **身份验证：** 向客户端验证您服务器的身份 - **完整性：** 确保数据在传输过程中未被篡改 - **现代标准：** 配置符合行业最佳实践和安全标准

### 如何使用

请按照以下步骤配置和使用 SSL 功能：

1.  **配置协议：** 使用 `SSL_PROTOCOLS` 设置选择要支持的 SSL/TLS 协议版本。
2.  **选择密码套件：** 使用 `SSL_CIPHERS_LEVEL` 设置指定加密强度，或使用 `SSL_CIPHERS_CUSTOM` 提供自定义密码。
3.  **配置 HTTP 到 HTTPS 重定向：** 使用 `AUTO_REDIRECT_HTTP_TO_HTTPS` 或 `REDIRECT_HTTP_TO_HTTPS` 设置来设置自动重定向。

### 配置设置

| 设置                          | 默认值            | 上下文    | 多选 | 描述                                                                                                          |
| ----------------------------- | ----------------- | --------- | ---- | ------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | 否   | **HTTP 重定向到 HTTPS：** 当设置为 `yes` 时，所有 HTTP 请求都会重定向到 HTTPS。                               |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | 否   | **自动 HTTP 重定向到 HTTPS：** 当设置为 `yes` 时，如果检测到 HTTPS，则自动将 HTTP 重定向到 HTTPS。            |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | 否   | **SSL 协议：** 要支持的 SSL/TLS 协议的空格分隔列表。                                                          |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | 否   | **SSL 密码级别：** 密码套件的预设安全级别（`modern`、`intermediate` 或 `old`）。                              |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | 否   | **自定义 SSL 密码：** 用于 SSL/TLS 连接的密码套件的冒号分隔列表（覆盖级别）。                                 |
| `SSL_ECDH_CURVE`              | `auto`            | multisite | 否   | **SSL ECDH 曲线：** 以 `:` 分隔的 ECDH 曲线（TLS 组）列表，或 `auto` 启用智能选择（OpenSSL 3.5+ 的 PQC 组）。 |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | multisite | 否   | **SSL 会话缓存大小：** SSL 会话缓存的大小（例如 `10m`、`512k`）。设置为 `off` 或 `none` 以禁用。              |

!!! tip "SSL Labs 测试"
    配置 SSL 设置后，请使用 [Qualys SSL Labs 服务器测试](https://www.ssllabs.com/ssltest/) 来验证您的配置并检查潜在的安全问题。一个正确的 BunkerWeb SSL 配置应该能获得 A+ 评级。

!!! warning "协议选择"
    由于已知的漏洞，默认情况下有意禁用了对 SSLv3、TLSv1.0 和 TLSv1.1 等旧协议的支持。只有在您绝对需要支持旧版客户端并了解这样做的安全隐患时，才启用这些协议。

### 配置示例

=== "现代安全（默认）"

    默认配置提供了强大的安全性，同时保持了与现代浏览器的兼容性：

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "最高安全"

    专注于最高安全性的配置，可能会降低对旧版客户端的兼容性：

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "旧版兼容性"

    为旧版客户端提供更广泛兼容性的配置（仅在必要时使用）：

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "自定义密码"

    使用自定义密码规范的配置：

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

## Security.txt

STREAM 支持 :white_check_mark:

Security.txt 插件为您的网站实施 [Security.txt](https://securitytxt.org/) 标准 ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116))。此功能可帮助安全研究人员访问您的安全策略，并为他们提供一种标准化的方式来报告他们在您的系统中发现的安全漏洞。

**工作原理：**

1.  启用后，BunkerWeb 会在您网站的根目录下创建一个 `/.well-known/security.txt` 文件。
2.  此文件包含有关您的安全策略、联系人和其他相关详细信息。
3.  安全研究人员和自动化工具可以轻松地在标准位置找到此文件。
4.  内容使用简单的设置进行配置，允许您指定联系信息、加密密钥、策略和致谢。
5.  BunkerWeb 会自动根据 RFC 9116 格式化该文件。

### 如何使用

请按照以下步骤配置和使用 Security.txt 功能：

1.  **启用该功能：** 将 `USE_SECURITYTXT` 设置为 `yes` 以启用 security.txt 文件。
2.  **配置联系信息：** 使用 `SECURITYTXT_CONTACT` 设置至少指定一种联系方式。
3.  **设置附加信息：** 配置可选字段，如到期日期、加密、致谢和策略 URL。
4.  **让 BunkerWeb 处理其余部分：** 配置完成后，BunkerWeb 将自动在标准位置创建并提供 security.txt 文件。

### 配置设置

| 设置                           | 默认值                      | 上下文    | 多选 | 描述                                                                             |
| ------------------------------ | --------------------------- | --------- | ---- | -------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | 否   | **启用 Security.txt：** 设置为 `yes` 以启用 security.txt 文件。                  |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | 否   | **Security.txt URI：** 指示 security.txt 文件可访问的 URI。                      |
| `SECURITYTXT_CONTACT`          |                             | multisite | 是   | **联系信息：** 安全研究人员如何与您联系（例如，`mailto:security@example.com`）。 |
| `SECURITYTXT_EXPIRES`          |                             | multisite | 否   | **到期日期：** 此 security.txt 文件应被视为到期的日期（ISO 8601 格式）。         |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | 是   | **加密：** 指向用于安全通信的加密密钥的 URL。                                    |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | 是   | **致谢：** 认可安全研究人员报告的 URL。                                          |
| `SECURITYTXT_POLICY`           |                             | multisite | 是   | **安全策略：** 指向描述如何报告漏洞的安全策略的 URL。                            |
| `SECURITYTXT_HIRING`           |                             | multisite | 是   | **安全职位：** 指向与安全相关的职位空缺的 URL。                                  |
| `SECURITYTXT_CANONICAL`        |                             | multisite | 是   | **规范 URL：** 此 security.txt 文件的规范 URI。                                  |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | 否   | **首选语言：** 通信中使用的语言。指定为 ISO 639-1 语言代码。                     |
| `SECURITYTXT_CSAF`             |                             | multisite | 是   | **CSAF：** 指向您的通用安全咨询框架提供商的 provider-metadata.json 的链接。      |

!!! warning "需要到期日期"
    根据 RFC 9116，`Expires` 字段是必需的。如果您没有为 `SECURITYTXT_EXPIRES` 提供值，BunkerWeb 会自动将到期日期设置为从当前日期算起的一年。

!!! info "联系信息至关重要"
    `Contact` 字段是 security.txt 文件中最重要的部分。您应该至少提供一种方式让安全研究人员与您联系。这可以是电子邮件地址、Web 表单、电话号码或任何其他适合您组织的方式。

!!! warning "URL 必须使用 HTTPS"
    根据 RFC 9116，security.txt 文件中的所有 URL（`mailto:` 和 `tel:` 链接除外）都必须使用 HTTPS。非 HTTPS URL 将被 BunkerWeb 自动转换为 HTTPS，以确保符合标准。

### 配置示例

=== "基本配置"

    一个仅包含联系信息的最小配置：

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "综合配置"

    一个包含所有字段的更完整的配置：

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

=== "多联系人配置"

    具有多种联系方式的配置：

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```

## Self-signed certificate

STREAM 支持 :white_check_mark:

自签名证书插件可直接在 BunkerWeb 中自动生成和管理 SSL/TLS 证书，无需外部证书颁发机构即可启用安全的 HTTPS 连接。此功能在开发环境、内部网络或需要快速部署 HTTPS 而无需配置外部证书时特别有用。

**工作原理：**

1.  启用后，BunkerWeb 会为您的已配置域名自动生成一个自签名 SSL/TLS 证书。
2.  该证书包含您配置中定义的所有服务器名称，确保每个域名的 SSL 验证正确无误。
3.  证书被安全地存储，并用于加密所有到您网站的 HTTPS 流量。
4.  证书在到期前会自动续订，确保 HTTPS 的持续可用性。

!!! warning "浏览器安全警告"
    当用户访问使用自签名证书的网站时，浏览器会显示安全警告，因为这些证书未经受信任的证书颁发机构验证。对于生产环境，请考虑改用 [Let's Encrypt](#lets-encrypt)。

### 如何使用

请按照以下步骤配置和使用自签名证书功能：

1.  **启用该功能：** 将 `GENERATE_SELF_SIGNED_SSL` 设置为 `yes` 以启用自签名证书生成。
2.  **选择加密算法：** 使用 `SELF_SIGNED_SSL_ALGORITHM` 设置选择您偏好的算法。
3.  **配置有效期：** 可选地使用 `SELF_SIGNED_SSL_EXPIRY` 设置证书的有效时长。
4.  **设置证书主题：** 使用 `SELF_SIGNED_SSL_SUBJ` 设置配置证书主题。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，证书会自动生成并应用于您的域名。

!!! tip "流模式配置"
    对于流模式，请配置 `LISTEN_STREAM_PORT_SSL` 设置以指定 SSL/TLS 监听端口。此步骤对于在流模式下正常运行至关重要。

### 配置设置

| 设置                        | 默认值                 | 上下文    | 多选 | 描述                                                                                           |
| --------------------------- | ---------------------- | --------- | ---- | ---------------------------------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | 否   | **启用自签名：** 设置为 `yes` 以启用自动自签名证书生成。                                       |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | 否   | **证书算法：** 用于证书生成的算法：`ec-prime256v1`、`ec-secp384r1`、`rsa-2048` 或 `rsa-4096`。 |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | 否   | **证书有效期：** 自签名证书的有效天数（默认为 1 年）。                                         |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | 否   | **证书主题：** 证书的主题字段，用于标识域名。                                                  |

!!! tip "开发环境"
    自签名证书非常适合开发和测试环境，在这些环境中您需要 HTTPS，但不需要受公共浏览器信任的证书。

!!! info "证书信息"
    生成的自签名证书使用指定的算法（默认为使用 prime256v1 曲线的椭圆曲线加密），并包含配置的主题，确保您的域名功能正常。

### 配置示例

=== "基本配置"

    一个使用默认设置的自签名证书的简单配置：

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "短期证书"

    证书过期更频繁的配置（用于定期测试证书续订流程）：

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "使用 RSA 证书进行测试"

    一个测试环境的配置，其中域名使用自签名的 RSA 证书：

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```

## Sessions

STREAM 支持 :white_check_mark:

会话插件为 BunkerWeb 提供了强大的 HTTP 会话管理功能，可在请求之间实现安全可靠的用户会话跟踪。此核心功能对于维护用户状态、身份验证持久性以及支持需要身份连续性的其他功能（例如[反机器人](#antibot)保护和用户身份验证系统）至关重要。

**工作原理：**

1.  当用户首次与您的网站互动时，BunkerWeb 会创建一个唯一的会话标识符。
2.  此标识符安全地存储在用户浏览器的 Cookie 中。
3.  在后续请求中，BunkerWeb 从 Cookie 中检索会话标识符，并使用它来访问用户的会话数据。
4.  对于具有多个 BunkerWeb 实例的分布式环境，会话数据可以本地存储或存储在 [Redis](#redis) 中。
5.  会话通过可配置的超时进行自动管理，在保持可用性的同时确保安全性。
6.  会话的加密安全性通过用于签署会话 Cookie 的密钥来保证。

### 如何使用

请按照以下步骤配置和使用会话功能：

1.  **配置会话安全性：** 设置一个强大的、唯一的 `SESSIONS_SECRET`，以确保会话 Cookie 无法被伪造。（默认值为“random”，这会触发 BunkerWeb 生成一个随机的密钥。）
2.  **选择会话名称：** 可选地自定义 `SESSIONS_NAME`，以定义您的会话 Cookie 在浏览器中的名称。（默认值为“random”，这会触发 BunkerWeb 生成一个随机的名称。）
3.  **设置会话超时：** 使用超时设置（`SESSIONS_IDLING_TIMEOUT`、`SESSIONS_ROLLING_TIMEOUT`、`SESSIONS_ABSOLUTE_TIMEOUT`）配置会话的有效时长。
4.  **配置 Redis 集成：** 对于分布式环境，将 `USE_REDIS` 设置为“yes”，并配置您的 [Redis 连接](#redis) 以在多个 BunkerWeb 节点之间共享会话数据。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，您的网站会自动进行会话管理。

### 配置设置

| 设置                        | 默认值   | 上下文 | 多选 | 描述                                                                                              |
| --------------------------- | -------- | ------ | ---- | ------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global | 否   | **会话密钥：** 用于签署会话 Cookie 的加密密钥。应该是一个强大的、随机的、对您的站点唯一的字符串。 |
| `SESSIONS_NAME`             | `random` | global | 否   | **Cookie 名称：** 将存储会话标识符的 Cookie 的名称。                                              |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global | 否   | **空闲超时：** 会话在失效前不活动的最长时间（以秒为单位）。                                       |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global | 否   | **滚动超时：** 会话必须续订前的最长时间（以秒为单位）。                                           |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global | 否   | **绝对超时：** 无论活动如何，会话被销毁前的最长时间（以秒为单位）。                               |
| `SESSIONS_CHECK_IP`         | `yes`    | global | 否   | **检查 IP：** 设置为 `yes` 时，如果客户端 IP 地址发生变化，则销毁会话。                           |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global | 否   | **检查 User-Agent：** 设置为 `yes` 时，如果客户端 User-Agent 发生变化，则销毁会话。               |

!!! warning "安全注意事项"
    `SESSIONS_SECRET` 设置对安全至关重要。在生产环境中：

    1. 使用一个强大的、随机的值（至少 32 个字符）
    2. 对此值保密
    3. 在集群中的所有 BunkerWeb 实例中使用相同的值
    4. 考虑使用环境变量或密钥管理，以避免以纯文本形式存储此值

!!! tip "集群环境"
    如果您在负载均衡器后面运行多个 BunkerWeb 实例：

    1. 将 `USE_REDIS` 设置为 `yes` 并配置您的 Redis 连接
    2. 确保所有实例使用完全相同的 `SESSIONS_SECRET` 和 `SESSIONS_NAME`
    3. 这确保了无论哪个 BunkerWeb 实例处理用户的请求，他们都能保持其会话

### 配置示例

=== "基本配置"

    单个 BunkerWeb 实例的简单配置：

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "myappsession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "增强安全性"

    具有更高安全设置的配置：

    ```yaml
    SESSIONS_SECRET: "your-very-strong-random-secret-key-here"
    SESSIONS_NAME: "securesession"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 分钟
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 分钟
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 小时
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "带 Redis 的集群环境"

    用于多个 BunkerWeb 实例共享会话数据的配置：

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "clustersession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # 确保 Redis 连接配置正确
    ```

=== "长效会话"

    用于需要延长会话持久性的应用程序的配置：

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "persistentsession"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 天
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 天
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 天
    ```

## UI

STREAM 支持 :x:

Integrate easily the BunkerWeb UI.

| 参数      | 默认值 | 上下文    | 可重复 | 描述                                         |
| --------- | ------ | --------- | ------ | -------------------------------------------- |
| `USE_UI`  | `no`   | multisite | 否     | Use UI                                       |
| `UI_HOST` |        | global    | 否     | Address of the web UI used for initial setup |

## User Manager <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/EIohiUf9Fg4' title='用户管理器页面' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

STREAM 支持 :x:

Add the possibility to manage users on the web interface

| 参数                | 默认值 | 上下文 | 可重复 | 描述                                            |
| ------------------- | ------ | ------ | ------ | ----------------------------------------------- |
| `USERS_REQUIRE_2FA` | `no`   | global | 否     | Require two-factor authentication for all users |

## Whitelist

STREAM 支持 :warning:

白名单插件允许您定义一个受信任的 IP 地址列表，这些地址可以绕过其他安全过滤器。
要阻止不需要的客户端，请参考 [黑名单插件](#blacklist)。

白名单插件提供了一种全面的方法，可以根据各种客户端属性明确允许访问您的网站。此功能提供了一种安全机制：符合特定条件的访问者将被授予立即访问权限，而所有其他访问者则必须通过常规的安全检查。

**工作原理：**

1.  您定义应被“列入白名单”的访问者的标准（_IP 地址、网络、反向 DNS、ASN、用户代理或 URI 模式_）。
2.  当访问者尝试访问您的网站时，BunkerWeb 会检查他们是否符合任何这些白名单标准。
3.  如果访问者符合任何白名单规则（并且不符合任何忽略规则），他们将被授予访问您网站的权限，并**绕过所有其他安全检查**。
4.  如果访问者不符合任何白名单标准，他们将照常通过所有正常的安全检查。
5.  白名单可以按计划从外部来源自动更新。

### 如何使用

请按照以下步骤配置和使用白名单功能：

1.  **启用该功能：** 白名单功能默认被禁用。将 `USE_WHITELIST` 设置为 `yes` 以启用它。
2.  **配置允许规则：** 定义哪些 IP、网络、反向 DNS 模式、ASN、用户代理或 URI 应被列入白名单。
3.  **设置忽略规则：** 指定任何应绕过白名单检查的例外情况。
4.  **添加外部来源：** 配置用于自动下载和更新白名单数据的 URL。
5.  **监控访问：** 检查 [Web UI](web-ui.md) 以查看哪些访问者被允许或拒绝。

!!! info "流模式"
    当使用流模式时，仅执行 IP、反向 DNS 和 ASN 检查。

### 配置设置

**通用**

| 设置            | 默认值 | 上下文    | 多选 | 描述                                             |
| --------------- | ------ | --------- | ---- | ------------------------------------------------ |
| `USE_WHITELIST` | `no`   | multisite | 否   | **启用白名单：** 设置为 `yes` 以启用白名单功能。 |

=== "IP 地址"
    **功能说明：** 根据访问者的 IP 地址或网络将其列入白名单。这些访问者将绕过所有安全检查。

    | 设置                       | 默认值 | 上下文    | 多选 | 描述                                                                          |
    | -------------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |        | multisite | 否   | **IP 白名单：** 允许的 IP 地址或网络（CIDR 表示法）列表，以空格分隔。         |
    | `WHITELIST_IGNORE_IP`      |        | multisite | 否   | **IP 忽略列表：** 应绕过 IP 白名单检查的 IP 地址或网络列表。                  |
    | `WHITELIST_IP_URLS`        |        | multisite | 否   | **IP 白名单 URL：** 包含要列入白名单的 IP 地址或网络的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_IP_URLS` |        | multisite | 否   | **IP 忽略列表 URL：** 包含要忽略的 IP 地址或网络的 URL 列表。                 |

=== "反向 DNS"
    **功能说明：** 根据访问者的域名（反向）将其列入白名单。这对于允许来自特定组织或网络的访问者按其域名访问非常有用。

    | 设置                         | 默认值 | 上下文    | 多选 | 描述                                                                           |
    | ---------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------ |
    | `WHITELIST_RDNS`             |        | multisite | 否   | **rDNS 白名单：** 允许的反向 DNS 后缀列表，以空格分隔。                        |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`  | multisite | 否   | **仅限全局 rDNS：** 当设置为 `yes` 时，仅对全局 IP 地址执行 rDNS 白名单检查。  |
    | `WHITELIST_IGNORE_RDNS`      |        | multisite | 否   | **rDNS 忽略列表：** 应绕过 rDNS 白名单检查的反向 DNS 后缀列表。                |
    | `WHITELIST_RDNS_URLS`        |        | multisite | 否   | **rDNS 白名单 URL：** 包含要列入白名单的反向 DNS 后缀的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_RDNS_URLS` |        | multisite | 否   | **rDNS 忽略列表 URL：** 包含要忽略的反向 DNS 后缀的 URL 列表。                 |

=== "ASN"
    **功能说明：** 使用自治系统编号（ASN）将来自特定网络提供商的访问者列入白名单。ASN 标识 IP 属于哪个提供商或组织。

    | 设置                        | 默认值 | 上下文    | 多选 | 描述                                                                  |
    | --------------------------- | ------ | --------- | ---- | --------------------------------------------------------------------- |
    | `WHITELIST_ASN`             |        | multisite | 否   | **ASN 白名单：** 允许的自治系统编号列表，以空格分隔。                 |
    | `WHITELIST_IGNORE_ASN`      |        | multisite | 否   | **ASN 忽略列表：** 应绕过 ASN 白名单检查的 ASN 列表。                 |
    | `WHITELIST_ASN_URLS`        |        | multisite | 否   | **ASN 白名单 URL：** 包含要列入白名单的 ASN 的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_ASN_URLS` |        | multisite | 否   | **ASN 忽略列表 URL：** 包含要忽略的 ASN 的 URL 列表。                 |

=== "用户代理"
    **功能说明：** 根据访问者声称使用的浏览器或工具将其列入白名单。这对于允许访问特定的已知工具或服务非常有效。

    | 设置                               | 默认值 | 上下文    | 多选 | 描述                                                                         |
    | ---------------------------------- | ------ | --------- | ---- | ---------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |        | multisite | 否   | **用户代理白名单：** 允许的用户代理模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `WHITELIST_IGNORE_USER_AGENT`      |        | multisite | 否   | **用户代理忽略列表：** 应绕过用户代理白名单检查的用户代理模式列表。          |
    | `WHITELIST_USER_AGENT_URLS`        |        | multisite | 否   | **用户代理白名单 URL：** 包含要列入白名单的用户代理模式的 URL 列表。         |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |        | multisite | 否   | **用户代理忽略列表 URL：** 包含要忽略的用户代理模式的 URL 列表。             |

=== "URI"
    **功能说明：** 将对您网站上特定 URL 的请求列入白名单。这对于允许访问特定端点而不考虑其他因素很有帮助。

    | 设置                        | 默认值 | 上下文    | 多选 | 描述                                                                      |
    | --------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------- |
    | `WHITELIST_URI`             |        | multisite | 否   | **URI 白名单：** 允许的 URI 模式（PCRE 正则表达式）列表，以空格分隔。     |
    | `WHITELIST_IGNORE_URI`      |        | multisite | 否   | **URI 忽略列表：** 应绕过 URI 白名单检查的 URI 模式列表。                 |
    | `WHITELIST_URI_URLS`        |        | multisite | 否   | **URI 白名单 URL：** 包含要列入白名单的 URI 模式的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_URI_URLS` |        | multisite | 否   | **URI 忽略列表 URL：** 包含要忽略的 URI 模式的 URL 列表。                 |

!!! info "URL 格式支持"
    所有 `*_URLS` 设置都支持 HTTP/HTTPS URL 以及使用 `file:///` 前缀的本地文件路径。支持使用 `http://user:pass@url` 格式进行基本身份验证。

!!! tip "定期更新"
    从 URL 获取的白名单会每小时自动下载和更新，以确保您的保护与最新的受信任来源保持同步。

!!! warning "安全绕过"
    被列入白名单的访问者将完全**绕过 BunkerWeb 中的所有其他安全检查**，包括 WAF 规则、速率限制、恶意机器人检测以及任何其他安全机制。仅对您绝对信任的来源使用白名单。

### 配置示例

=== "基本组织访问"

    一个简单的配置，将公司办公室的 IP 列入白名单：

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "高级配置"

    一个更全面的配置，具有多个白名单标准：

    ```yaml
    USE_WHITELIST: "yes"

    # 公司和受信任的合作伙伴资产
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # 公司和合作伙伴的 ASN
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # 外部受信任的来源
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "使用本地文件"

    使用本地文件进行白名单的配置：

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///path/to/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///path/to/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///path/to/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///path/to/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///path/to/uri-whitelist.txt"
    ```

=== "API 访问模式"

    一个专注于仅允许访问特定 API 端点的配置：

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # 适用于所有端点的内部网络
    ```

=== "知名爬虫"

    一个将常见的搜索引擎和社交媒体爬虫列入白名单的配置：

    ```yaml
    USE_WHITELIST: "yes"

    # 使用反向 DNS 进行验证以增加安全性
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # 仅检查全局 IP
    ```

    此配置允许合法的爬虫索引您的网站，而不会受到可能阻止它们的速率限制或其他安全措施的影响。rDNS 检查有助于验证爬虫是否确实来自其声称的公司。

### 使用本地列表文件

Whitelist、Greylist 和 Blacklist 插件提供的 `*_URLS` 设置共用同一个下载器。当你引用 `file:///` URL 时：

- 路径会在 **scheduler** 容器内解析（Docker 部署通常为 `bunkerweb-scheduler`）。请将文件挂载到该容器，并确保 scheduler 用户拥有读取权限。
- 每个文件都是 UTF-8 编码的纯文本，每行一个条目。空行会被忽略，注释行必须以 `#` 或 `;` 开头。不支持 `//` 注释。
- 各类列表的条目要求：
  - **IP 列表** 接受 IPv4/IPv6 地址或 CIDR 网段（例如 `192.0.2.10` 或 `2001:db8::/48`）。
  - **rDNS 列表** 需要没有空格的后缀（例如 `.search.msn.com`），并会自动转换为小写。
  - **ASN 列表** 可以仅包含编号（`32934`），或带 `AS` 前缀的编号（`AS15169`）。
  - **User-Agent 列表** 视为 PCRE 模式，整行（包括空格）都会保留。请把注释放在独立行，避免被当成模式。
  - **URI 列表** 必须以 `/` 开头，可以使用 `^`、`$` 等 PCRE 标记。

符合格式的示例文件：

```text
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
