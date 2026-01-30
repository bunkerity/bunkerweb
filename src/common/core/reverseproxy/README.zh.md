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
    | `REVERSE_PROXY_REQUEST_BUFFERING`| `yes`  | multisite | 是   | **请求缓冲：** 启用或禁用向代理资源发送请求时的缓冲。 |
    | `REVERSE_PROXY_KEEPALIVE`        | `no`   | multisite | 是   | **保持连接：** 启用或禁用与代理资源的保持连接。      |
    | `REVERSE_PROXY_CUSTOM_HOST`      |        | multisite | 否   | **自定义主机：** 覆盖发送到上游服务器的 Host 标头。  |
    | `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`  | multisite | 否   | **拦截错误：** 是否拦截和重写来自后端的错误响应。    |

    !!! tip "最佳实践"
        - 始终在 `REVERSE_PROXY_HOST` 中指定完整的 URL，包括协议（http:// 或 https://）
        - 使用 `REVERSE_PROXY_INTERCEPT_ERRORS` 在您所有服务中提供一致的错误页面
        - 当配置多个后端时，使用带编号的后缀格式（例如，`REVERSE_PROXY_HOST_2`、`REVERSE_PROXY_URL_2`）

    !!! warning "请求缓冲行为"
        禁用 `REVERSE_PROXY_REQUEST_BUFFERING` 仅在 ModSecurity 被禁用时才会生效，因为否则会强制执行请求缓冲。

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
