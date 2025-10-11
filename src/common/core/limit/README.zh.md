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
