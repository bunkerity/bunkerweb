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

### 可复用的上游池

下面这些设置把一个 `location` 指向单个后端。当多个后端服务于同一个应用，或多个服务共用同一批后端时，您可以改为声明一个**具名、可复用的池**——即上游（upstream）——可在 Web 界面的 **Upstreams** 页面或通过 `/upstreams` API 端点创建，并附加到任意多个服务上。修改池会同时更新所有附加了它的服务。

- 一个池带有名称、**协议**、负载均衡方法（`round_robin`、`least_conn` 或 `ip_hash`）、可选的 `keepalive` 连接数，以及一个或多个服务器。
- 每个服务器带有地址（`主机` 或 `主机:端口`，不含协议前缀）、`weight`，以及被动健康检查参数 `max_fails` 和 `fail_timeout`；还可以标记为 `backup`（仅在其他服务器失败时使用）或 `down`（临时摘除）。
- **协议**决定由哪个消费方使用该池以及如何附加：
    - `http` —— 反向代理（`proxy_pass`）。附加到一个**服务加一个路径**，因此同一个服务可以把 `/` 代理到一个池、把 `/api` 代理到另一个池。
    - `grpc` —— gRPC 插件（`grpc_pass`），附加方式相同。HTTP 与 gRPC 池共享同一个路径命名空间，因为二者都会向同一个 server 渲染 `location`。
    - `stream` —— TCP/UDP 服务。没有路径：池接管整个服务，取代 stream 配置根据 `REVERSE_PROXY_HOST` 构建的那个隐式单后端。一个服务只能带一个，且 `keepalive` 不适用。
- `backend_ssl` 开关决定是否对后端服务器使用 TLS：用 `https://` 代替 `http://`，用 `grpcs://` 代替 `grpc://`。
- 协议必须与服务匹配：HTTP 或 gRPC 池只能用于 `SERVER_TYPE` 为 `http` 的服务，stream 池只能用于 `SERVER_TYPE` 为 `stream` 的服务。Web 界面只列出匹配的服务；API 会拒绝其余的并给出说明。
- 内联的 `REVERSE_PROXY_HOST` 和 `GRPC_HOST` 设置的行为与以往完全一致。附加的池在它们**之后**渲染，占用接下来空闲的后缀，因此现有配置不受影响，也不需要任何迁移。附加了池的服务会自动启用 `USE_REVERSE_PROXY`（或 `USE_GRPC`）。
- **一个路径，只有一个归属。** 反向代理、gRPC 和**重定向**都会向同一个 server 渲染 `location`，而 NGINX 拒绝两个 URI 相同的 `location` 块。因此一个路径会被这三者共同占用——无论占用它的是附加的池、附加的重定向，还是内联设置——冲突的改动会被拒绝，并给出说明是谁已经占用了该路径的消息。
- 没有附加到任何服务的池不会渲染出任何内容；只要池仍附加在某个服务上，删除它就会被拒绝，请先解除附加。出于同样的原因，修改已附加池的协议也会被拒绝。
- 池名只接受字母、数字、连字符和下划线。点号是有意拒绝的：NGINX 会先在已声明的上游中解析名称，然后才走 DNS 解析器，因此一个与真实主机同名的池会截走本该发往该主机的流量。

### 与上游之间的双向 TLS

下面的 `REVERSE_PROXY_SSL_VERIFY` 系列设置校验的是*后端的*证书。若还要向后端出示证书——即双向 TLS——请配置客户端证书对：

- 使用 `REVERSE_PROXY_SSL_CLIENT_CERT` / `REVERSE_PROXY_SSL_CLIENT_KEY` 指定调度器可读的文件路径，或使用 `REVERSE_PROXY_SSL_CLIENT_CERT_DATA` / `REVERSE_PROXY_SSL_CLIENT_KEY_DATA` 直接给出 base64 或明文 PEM，由 `REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY`（`file` 或 `data`）决定取哪一种。
- 该证书对会用 OpenSSL 校验，并由处理受信任 CA 的同一个任务缓存并分发到每个实例，写入时权限仅限属主与属组。
- **两半都必须提供。** 只有证书而没有对应的私钥（或反之）会被拒绝，而不会只应用一半，因为 NGINX 要么需要这两条指令，要么一条都不要。
- 该身份是**按服务生效的，并与 gRPC 和 stream 共享**：无论由哪个插件转发流量，一个服务都以同一份证书向其后端认证。在 stream 上下文中，它同时也是启用到后端的 TLS（`proxy_ssl on`）的开关，因此未配置客户端证书对的服务会保持其现有的明文行为。
- 清空这些设置后，下一次运行会删除这些文件，双向 TLS 随之关闭。

这与 `mtls` 插件无关，后者认证的是*连接到 BunkerWeb 的客户端*——方向正好相反。

!!! warning "无法解析的后端会导致重载失败"
    NGINX 在加载配置时会解析上游服务器的地址。如果已附加池中的某个服务器无法解析，整份配置都会被拒绝，BunkerWeb 会继续使用上一份有效配置。请使用在重载时可解析的地址，或在服务器不可用期间将其标记为 `down`。

### 配置指南

=== "基本配置"

    **核心设置**

    基本的配置设置启用并控制反向代理功能的基本功能。

    !!! success "反向代理的好处"
        - **安全增强：** 所有流量在到达您的应用程序之前都会经过 BunkerWeb 的安全层
        - **SSL 终止：** 集中管理 SSL/TLS 证书，而后端服务可以使用未加密的连接
        - **协议处理：** 支持 HTTP、HTTPS、WebSockets 和其他协议
        - **错误拦截：** 自定义错误页面以获得一致的用户体验

    | 设置                              | 默认值 | 上下文    | 多选 | 描述                                                                                                                                               |
    | --------------------------------- | ------ | --------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`               | `no`   | multisite | 否   | **启用反向代理：** 设置为 `yes` 以启用反向代理功能。                                                                                               |
    | `REVERSE_PROXY_HOST`              |        | multisite | 是   | **后端主机：** 代理资源的完整 URL (proxy_pass)。                                                                                                   |
    | `REVERSE_PROXY_URL`               | `/`    | multisite | 是   | **位置 URL：** 将被代理到后端服务器的路径。以 `^` 开头或以 `$` 结尾的值将被视为正则表达式 location。                                                 |
    | `REVERSE_PROXY_BUFFERING`         | `yes`  | multisite | 是   | **响应缓冲：** 启用或禁用来自代理资源的响应缓冲。                                                                                                  |
    | `REVERSE_PROXY_REQUEST_BUFFERING` | `yes`  | multisite | 是   | **请求缓冲：** 启用或禁用向代理资源发送请求时的缓冲。                                                                                              |
    | `REVERSE_PROXY_KEEPALIVE`         | `no`   | multisite | 是   | **保持连接：** 启用或禁用与代理资源的保持连接。                                                                                                    |
    | `REVERSE_PROXY_HTTP_VERSION`      | `1.1`  | multisite | 是   | **HTTP 版本：** 用于与上游通信的 HTTP 协议版本（`1.0`、`1.1` 或 `2`）。设为 `2` 可在上游连接上启用 HTTP/2 多路复用。WebSocket 位置始终固定为 1.1。 |
    | `REVERSE_PROXY_CUSTOM_HOST`       |        | multisite | 否   | **自定义主机：** 覆盖发送到上游服务器的 Host 标头。                                                                                                |
    | `REVERSE_PROXY_INTERCEPT_ERRORS`  | `yes`  | multisite | 否   | **拦截错误：** 是否拦截和重写来自后端的错误响应。                                                                                                  |

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
    | `REVERSE_PROXY_STREAM_HALF_CLOSE` | `no` | multisite | 是 | **Stream 半关闭：** 设为 `yes` 时，在客户端关闭其写方向后仍保持与后端的连接。某些 TCP 协议要求客户端先半关闭再等待响应，而 nginx 默认会同时关闭两个方向。仅适用于 stream（TCP/UDP）服务。 |
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
    | `REVERSE_PROXY_SSL_VERIFY`                       | `no`   | multisite | 否   | **SSL 验证：** 启用或禁用对上游服务器 SSL 证书的验证。                  |
    | `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file` | multisite | 否   | **受信任证书优先级：** 受信任 CA 的来源：`file`（路径）或 `data`（base64/PEM）。 |
    | `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE`          |        | multisite | 否   | **SSL 受信任证书路径：** 用于验证上游的 PEM CA 包路径（需调度器可读）。 |
    | `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA`     |        | multisite | 否   | **SSL 受信任证书数据：** 以 base64 或 PEM 直接提供的受信任 CA（例如通过 Web UI）。 |
    | `REVERSE_PROXY_SSL_VERIFY_DEPTH`                 | `1`    | multisite | 否   | **SSL 验证深度：** 上游服务器证书链中的验证深度。                       |
    | `REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY` | `file` | multisite | 否 | **客户端证书优先级：** 向上游出示的证书与私钥的来源：`file`（路径）或 `data`（base64/PEM）。 |
    | `REVERSE_PROXY_SSL_CLIENT_CERT` | | multisite | 否 | **客户端证书路径：** BunkerWeb 向上游出示的 PEM 客户端证书路径，需可被调度器读取。必须同时提供配对的私钥。 |
    | `REVERSE_PROXY_SSL_CLIENT_CERT_DATA` | | multisite | 否 | **客户端证书数据：** 直接以 base64 或 PEM 形式提供的客户端证书（例如通过 Web 界面）。 |
    | `REVERSE_PROXY_SSL_CLIENT_KEY` | | multisite | 否 | **客户端私钥路径：** 与客户端证书配对的 PEM 私钥路径，需可被调度器读取。 |
    | `REVERSE_PROXY_SSL_CLIENT_KEY_DATA` | | multisite | 否 | **客户端私钥数据：** 直接以 base64 或 PEM 形式提供的客户端私钥。条件允许时请优先使用文件路径：在此填入的私钥会作为设置值存储。 |

    !!! info "证书验证"
        当 `REVERSE_PROXY_SSL_VERIFY` 设置为 `yes` 时，NGINX 会同时验证上游证书链及其名称：

        - **受信任 CA：** 以文件路径（`REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE`，需调度器可读）或 base64/PEM 数据（`REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA`）提供，由 `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY` 选择。调度器会验证、缓存并将其分发到每个实例，因此只需配置一次，无需逐实例挂载。
        - **必需：** 必须提供受信任证书；NGINX 对上游验证没有隐式的系统存储。要验证公共上游，请将路径指向系统 CA 包（例如 `/etc/ssl/certs/ca-certificates.crt`）。
        - **名称：** 默认针对从 `REVERSE_PROXY_HOST` 获取的主机进行检查。如果后端证书的 CN/SAN 不同，请将 `REVERSE_PROXY_SSL_SNI` 设置为 `yes`，并将 `REVERSE_PROXY_SSL_SNI_NAME` 设置为预期名称。
        - **故障安全：** 如果没有可用的有效受信任证书，则会为该服务器禁用验证，而不是中断每个上游连接。

        这些设置按服务生效：一个服务的所有上游条目（`REVERSE_PROXY_HOST`、`REVERSE_PROXY_HOST_1`、……）共享相同的验证配置。

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

    | 设置                              | 默认值 | 上下文    | 多选 | 描述                                                                                                                                                  |
    | --------------------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |        | multisite | 是   | **附加配置：** 在 location 块中包含额外的配置。                                                                                                       |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`  | multisite | 是   | **传递请求体：** 启用或禁用传递请求体。                                                                                                               |
    | `REVERSE_PROXY_MODSECURITY`       | `yes`  | multisite | 是   | **ModSecurity（按 location）：** 设置为 `no` 可在此 location 中生成 `modsecurity off;`，从而在大文件上传端点上绕过 WAF 以避免 OOM（请参阅下方说明）。 |
    | `REVERSE_PROXY_SEND_PROXY_PROTOCOL` | `auto` | multisite | 否 | **发送 PROXY 协议：** 向 stream 上游发送 PROXY 协议头。`auto` 跟随全局的 `USE_PROXY_PROTOCOL`，也就是该设置出现之前 BunkerWeb 的行为；`yes` 和 `no` 则与入站监听器无关地独立决定。仅适用于 stream（TCP/UDP）服务。 |

    !!! warning "安全注意事项"
        包含自定义配置片段时请小心，因为如果配置不当，它们可能会覆盖 BunkerWeb 的安全设置或引入漏洞。

    !!! warning "大文件上传的安全建议"
        ModSecurity 会将完整请求体缓冲到内存中，并且无法为数 GB 的上传设置上限，这可能导致 worker OOM。如果**（并且仅当）**某个反向代理 URL *专门* 用于文件上传（例如专用的 `/upload` 端点），请在该 URL 上设置 `REVERSE_PROXY_MODSECURITY_N: "no"`。不要在混合用途的 URL 上禁用它：否则该 location 提供的所有内容都会失去 WAF 覆盖。

        为了在绕过 ModSecurity 后仍保护上传内容，请将其与文件扫描插件配合使用，例如 [ClamAV](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav) 或 [VirusTotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal)，它们检查上传文件本身，而不是原始请求体。

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
