gRPC 插件允许 BunkerWeb 通过 HTTP/2 使用 `grpc_pass` 代理 gRPC 服务。它适用于多站点场景，每个虚拟主机都可以在特定路径下暴露一个或多个 gRPC 后端。

!!! example "实验性功能"
    该功能尚未达到生产可用状态。欢迎测试并通过 GitHub 仓库中的 [issues](https://github.com/bunkerity/bunkerweb/issues) 向我们反馈任何 bug。

**工作原理：**

1. 客户端向 BunkerWeb 发送 HTTP/2 请求。
2. gRPC 插件匹配已配置的 `location`（`GRPC_URL`），并通过 `grpc_pass` 将请求转发到已配置的上游（`GRPC_HOST`）。
3. BunkerWeb 添加转发头，并应用超时/上游重试设置。
4. 上游 gRPC 服务器返回响应，BunkerWeb 再将响应回传给客户端。

### 使用方式

1. **启用功能：** 将 `USE_GRPC` 设置为 `yes`。
2. **配置上游：** 至少设置 `GRPC_HOST`（也可选配 `GRPC_HOST_2`、`GRPC_HOST_3` 等）。
3. **映射路径：** 为每个上游设置 `GRPC_URL`（多个条目时使用对应后缀）。
4. **调优行为：** 按需配置超时、重试、请求头以及 TLS SNI 选项。

### 配置项

| 配置项                                  | 默认值 | 上下文    | 可多值 | 说明                                                                                                                    |
| --------------------------------------- | ------ | --------- | ------ | ----------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`   | multisite | 否     | **启用 gRPC：** 设置为 `yes` 以启用 gRPC 代理。                                                                         |
| `GRPC_HOST`                             |        | multisite | 是     | **gRPC 上游：** `grpc_pass` 使用的值（例如 `grpc://service:50051` 或 `grpcs://...`）。                                  |
| `GRPC_URL`                              | `/`    | multisite | 是     | **Location URL：** 将被代理到 gRPC 上游的路径。                                                                         |
| `GRPC_CUSTOM_HOST`                      |        | multisite | 否     | **自定义 Host 头：** 覆盖发送到上游的 `Host` 头。                                                                       |
| `GRPC_HEADERS`                          |        | multisite | 是     | **额外上游请求头：** 分号分隔的 `grpc_set_header` 值列表。                                                              |
| `GRPC_HIDE_HEADERS`                     |        | multisite | 是     | **隐藏响应头：** 空格分隔的 `grpc_hide_header` 值列表。                                                                 |
| `GRPC_HEADERS_CLIENT`                   |        | multisite | 是     | **返回给客户端的响应头：** 分号分隔的 `add_header` 值列表。                                                             |
| `GRPC_PASS_HEADERS`                     |        | multisite | 是     | **透传的响应头：** 空格分隔的 `grpc_pass_header` 值列表，用于透传 NGINX 默认隐藏的响应头。                              |
| `GRPC_IGNORE_HEADERS`                   |        | multisite | 是     | **忽略的响应头：** 空格分隔的 `grpc_ignore_headers` 值列表，使 NGINX 不处理这些响应头。                                 |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`   | multisite | 否     | **允许请求头包含下划线：** 启用/禁用 `underscores_in_headers`。                                                         |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`  | multisite | 否     | **拦截错误：** 启用/禁用 `grpc_intercept_errors`。                                                                      |
| `GRPC_BUFFER_SIZE`                      |        | multisite | 是     | **缓冲区大小：** `grpc_buffer_size` 的值（读取上游响应所用的缓冲区）。                                                  |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`  | multisite | 是     | **连接超时：** 与上游建立连接的超时时间。                                                                               |
| `GRPC_READ_TIMEOUT`                     | `60s`  | multisite | 是     | **读取超时：** 从上游读取数据的超时时间。                                                                               |
| `GRPC_SEND_TIMEOUT`                     | `60s`  | multisite | 是     | **发送超时：** 向上游发送数据的超时时间。                                                                               |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`  | multisite | 是     | **Socket Keepalive：** 启用/禁用与上游 socket 的 keepalive。                                                            |
| `GRPC_SSL_SNI`                          | `no`   | multisite | 否     | **SSL SNI：** 启用/禁用 TLS 上游的 SNI。                                                                                |
| `GRPC_SSL_SNI_NAME`                     |        | multisite | 否     | **SSL SNI 名称：** 当 `GRPC_SSL_SNI=yes` 时发送的 SNI 主机名。                                                          |
| `GRPC_SSL_VERIFY`                       | `no`   | multisite | 否     | **SSL 校验：** 启用/禁用对 gRPC 上游证书的校验。                                                                        |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file` | multisite | 否     | **受信任证书来源：** CA 包的来源，`file` 或 `data`。                                                                    |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |        | multisite | 否     | **受信任证书路径：** 调度器 可读取的 PEM CA 包路径（来源为 `file` 时使用）。                                            |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |        | multisite | 否     | **受信任证书内容：** base64 或明文 PEM 形式的 CA 包（来源为 `data` 时使用）。                                           |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`    | multisite | 否     | **SSL 校验深度：** 上游证书链的校验深度。                                                                               |
| `GRPC_SSL_CERT_PRIORITY`                | `file` | multisite | 否     | **客户端证书来源：** 客户端证书与私钥的来源，`file` 或 `data`。                                                         |
| `GRPC_SSL_CERT`                         |        | multisite | 否     | **客户端证书路径：** 向上游出示的 PEM 客户端证书，用于双向 TLS（来源为 `file` 时使用）。                                |
| `GRPC_SSL_CERT_DATA`                    |        | multisite | 否     | **客户端证书内容：** base64 或明文 PEM 形式的客户端证书（来源为 `data` 时使用）。                                       |
| `GRPC_SSL_KEY`                          |        | multisite | 否     | **客户端私钥路径：** 与客户端证书匹配的 PEM 私钥（来源为 `file` 时使用）。私钥不能加密。                                |
| `GRPC_SSL_KEY_DATA`                     |        | multisite | 否     | **客户端私钥内容：** base64 或明文 PEM 形式的客户端私钥（来源为 `data` 时使用）。                                       |
| `GRPC_SSL_CRL`                          |        | multisite | 否     | **CRL 路径：** 校验上游时应用的 PEM 吊销列表。优先于 CRL 内容。                                                         |
| `GRPC_SSL_CRL_DATA`                     |        | multisite | 否     | **CRL 内容：** base64 或明文 PEM 形式的吊销列表。仅在 CRL 路径为空时使用。                                              |
| `GRPC_SSL_PROTOCOLS`                    |        | multisite | 否     | **上游 SSL 协议：** 向上游提供的 TLS 版本。留空则沿用 NGINX 默认值。                                                    |
| `GRPC_SSL_CIPHERS`                      |        | multisite | 否     | **上游 SSL 加密套件：** 向上游提供的加密套件字符串。留空则沿用 NGINX 默认值。                                           |
| `GRPC_NEXT_UPSTREAM`                    |        | multisite | 是     | **下一个上游条件：** `grpc_next_upstream` 的值。                                                                        |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |        | multisite | 是     | **下一个上游超时：** `grpc_next_upstream_timeout` 的值。                                                                |
| `GRPC_NEXT_UPSTREAM_TRIES`              |        | multisite | 是     | **下一个上游重试次数：** `grpc_next_upstream_tries` 的值。                                                              |
| `GRPC_AUTH_REQUEST`                     |        | multisite | 是     | **认证请求：** `auth_request` 的值，用于通过外部提供方进行认证。                                                        |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |        | multisite | 是     | **认证请求登录 URL：** 认证请求返回 401 时的跳转目标。                                                                  |
| `GRPC_AUTH_REQUEST_SET`                 |        | multisite | 是     | **认证请求变量：** 分号分隔的 `auth_request_set` 值列表。                                                               |
| `GRPC_INCLUDES`                         |        | multisite | 是     | **附加 include：** 在 gRPC `location` 块中追加的、以空格分隔的 include 文件列表。                                       |
| `GRPC_MAX_CLIENT_SIZE`                  |        | multisite | 是     | **最大请求体大小：** 当前 location 的 `client_max_body_size` 值（`0` 表示不限制）。留空则使用服务的 `MAX_CLIENT_SIZE`。 |

!!! tip "上游双向 TLS"
    客户端证书与私钥必须同时提供，且私钥不能加密。调度器 会校验该证书对、缓存并分发到各实例；若校验不通过，则不会生成证书相关指令。只有在启用上游校验时，CRL 才会生效。

!!! warning "gRPC Location 中的 ModSecurity"
    由于 ModSecurity 目前无法稳定支持 gRPC 流量模式，本插件生成的 gRPC `location` 块中会自动关闭 ModSecurity。

!!! tip "校验上游证书"
    只有在 CA 包可用时 `GRPC_SSL_VERIFY` 才会生效。可通过 `GRPC_SSL_TRUSTED_CERTIFICATE`（调度器 可读取的路径）或 `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`（base64 或明文 PEM）提供，并用 `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` 选择来源。调度器 会校验该 CA 包、缓存并分发到各实例。若没有可用的 CA 包，校验将保持关闭。

!!! warning "长连接流与核心超时"
    长连接或流式 RPC 可能需要高于全局默认值的通用 NGINX 超时。常见需要调整的是 General 插件设置中的 `CLIENT_BODY_TIMEOUT` 和 `CLIENT_HEADER_TIMEOUT`。

!!! tip "多个 gRPC 后端"
    多路由场景请使用带后缀的配置项：
    - `GRPC_HOST`, `GRPC_URL`
    - `GRPC_HOST_2`, `GRPC_URL_2`
    - `GRPC_HOST_3`, `GRPC_URL_3`

### 配置示例

=== "基础 gRPC 代理"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_CONNECT_TIMEOUT: "10s"
    GRPC_READ_TIMEOUT: "300s"
    GRPC_SEND_TIMEOUT: "300s"
    ```

=== "TLS 上游（grpcs + SNI）"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    ```

=== "多路径 / 多后端"

    ```yaml
    USE_GRPC: "yes"

    GRPC_HOST: "grpc://user-service:50051"
    GRPC_URL: "/users.UserService/"

    GRPC_HOST_2: "grpc://billing-service:50052"
    GRPC_URL_2: "/billing.BillingService/"

    GRPC_HOST_3: "grpc://inventory-service:50053"
    GRPC_URL_3: "/inventory.InventoryService/"
    ```

=== "请求头与重试策略"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_HEADERS: "x-request-source bunkerweb;x-env production"
    GRPC_NEXT_UPSTREAM: "error timeout unavailable"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```

=== "已校验的 TLS 上游"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    GRPC_SSL_VERIFY: "yes"
    GRPC_SSL_TRUSTED_CERTIFICATE: "/etc/ssl/certs/ca-certificates.crt"
    GRPC_SSL_VERIFY_DEPTH: "2"
    ```

=== "外部认证"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_AUTH_REQUEST: "/auth"
    GRPC_AUTH_REQUEST_SIGNIN_URL: "https://sso.example.com/login"
    GRPC_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_email $upstream_http_x_email"
    GRPC_HEADERS: "x-forwarded-user $auth_user"
    ```
