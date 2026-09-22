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

!!! tip "可复用的 gRPC 后端池"
    一个 `GRPC_HOST` 只指向单个后端。若要在多个后端之间做负载均衡，或在多个服务之间共用同一批后端，请在 **Upstreams** 页面（或通过 `/upstreams` API）声明一个 **gRPC 上游池**，并按路径附加到某个服务上——BunkerWeb 会替您把 `grpc://<池名>` 写入对应的 `GRPC_HOST`。请注意，在同一个服务上 gRPC 与反向代理的 `location` 共享同一个路径命名空间：同一路径不能被占用两次，无论由哪个插件提供服务。参见反向代理文档中的*可复用的上游池*一节。

!!! tip "与 gRPC 后端的双向 TLS"
    gRPC 拥有独立于反向代理的自有上游身份。对于 TLS 上游，请使用 `grpcs://` 并按需配置 `GRPC_SSL_SNI` 与 `GRPC_SSL_SNI_NAME`。要校验上游证书，请设置 `GRPC_SSL_VERIFY=yes`，并通过 `GRPC_SSL_TRUSTED_CERTIFICATE` 或 `_DATA` 提供 PEM CA 包，由 `_PRIORITY`（`file` 或 `data`）选择来源。`GRPC_SSL_VERIFY_DEPTH` 默认为 `1`。系统不会自动选择 CA 包：若没有已缓存的 CA，生成的配置会禁用验证，并附带说明如何配置的注释。CRL 是可选的（`GRPC_SSL_CRL` 或 `_DATA`），仅在启用验证且存在已缓存 CA 时才会应用。`GRPC_SSL_PROTOCOLS` 和 `GRPC_SSL_CIPHERS` 留空时不改变 NGINX 默认值。

    要启用双向 TLS，请设置 `GRPC_SSL_CLIENT_CERT` 和 `GRPC_SSL_CLIENT_KEY`，或其 `_DATA` 变体；`GRPC_SSL_CLIENT_CERT_PRIORITY` 用于选择证书对使用文件路径还是数据。两者都必须有效且匹配——BunkerWeb 会检查上游客户端证书是否与其私钥匹配；临时的文件读取失败会保留已缓存的 TLS 材料并报告任务失败，而清空设置或提供无效材料则会移除受影响的缓存。该身份归属于 gRPC；反向代理和 stream 各自独立使用 `REVERSE_PROXY_SSL_CLIENT_*`。共享的 `trusted-cert` 任务会将 gRPC 的 CA、CRL 和客户端证书对缓存到 reverseproxy 缓存目录中，并在材料发生变化时触发配置重新生成。不存在单独的 gRPC 证书任务。TLS 设置适用于整个服务，包括已挂载的上游池；它们不是按 location 生效的设置。参见反向代理文档中的*与上游的双向 TLS*。

### 配置设置

| Setting                                 | 默认值 | 上下文    | 多值 | 描述                                                                                                                              |
| ---------------------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_GRPC`                              | `no`   | multisite | 否   | **启用 gRPC：** 设置为 `yes` 以启用 gRPC 代理。                                                                                   |
| `GRPC_HOST`                             |        | multisite | 是   | **gRPC 上游：** `grpc_pass` 使用的值（例如 `grpc://service:50051` 或 `grpcs://...`）。                                           |
| `GRPC_URL`                              | `/`    | multisite | 是   | **Location URL：** 将被代理到 gRPC 上游的路径。以 `^` 开头或以 `$` 结尾的值将被视为正则表达式 location。可选地以 `~`、`~*`、`=` 或 `^~` 加一个空格作为前缀，以显式设置 nginx location 修饰符；值的其余部分不允许包含空格、`;`、`{` 或 `}`。 |
| `GRPC_CUSTOM_HOST`                      |        | multisite | 否   | **自定义 Host 头：** 覆盖发送到上游的 `Host` 头。                                                                                 |
| `GRPC_HEADERS`                          |        | multisite | 是   | **上游请求头：** 分号分隔的 `grpc_set_header` 值；匹配的生成标头会被不区分大小写地替换。                                          |
| `GRPC_HIDE_HEADERS`                     |        | multisite | 是   | **隐藏响应头：** 空格分隔的 `grpc_hide_header` 值列表。                                                                           |
| `GRPC_HEADERS_CLIENT`                   |        | multisite | 是   | **客户端响应头：** 分号分隔的 `add_header` 值列表，发送给客户端。                                                                 |
| `GRPC_PASS_HEADERS`                     |        | multisite | 是   | **透传响应头：** 空格分隔的 `grpc_pass_header` 值列表，用于转发默认被隐藏的标头。                                                 |
| `GRPC_IGNORE_HEADERS`                   |        | multisite | 是   | **忽略的响应头：** 空格分隔的 `grpc_ignore_headers` 值列表，使 NGINX 不处理这些标头。                                             |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`   | multisite | 否   | **标头中使用下划线：** 启用/禁用 `underscores_in_headers`。该指令在服务器范围内与反向代理和 misc 插件共享：只要某个服务为其中一个 location 启用，就会对整个服务生效。 |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`  | multisite | 否   | **拦截错误：** 启用/禁用 `grpc_intercept_errors`。                                                                                |
| `GRPC_BUFFER_SIZE`                      |        | multisite | 是   | **缓冲区大小：** `grpc_buffer_size` 的值（用于读取上游响应的缓冲区）。                                                            |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`  | multisite | 是   | **连接超时：** 与上游建立连接的超时时间。                                                                                         |
| `GRPC_READ_TIMEOUT`                     | `60s`  | multisite | 是   | **读取超时：** 从上游读取数据的超时时间。                                                                                         |
| `GRPC_SEND_TIMEOUT`                     | `60s`  | multisite | 是   | **发送超时：** 向上游发送数据的超时时间。                                                                                         |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`  | multisite | 是   | **Socket Keepalive：** 启用/禁用与上游 socket 的 keepalive。                                                                      |
| `GRPC_SSL_SNI`                          | `no`   | multisite | 否   | **SSL SNI：** 启用/禁用 TLS 上游的 SNI。                                                                                          |
| `GRPC_SSL_SNI_NAME`                     |        | multisite | 否   | **SSL SNI 名称：** 当 `GRPC_SSL_SNI=yes` 时发送的 SNI 主机名。                                                                    |
| `GRPC_SSL_VERIFY`                       | `no`   | multisite | 否   | **SSL 验证：** 启用/禁用对 gRPC 上游证书的验证。                                                                                  |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file` | multisite | 否   | **受信任证书优先级：** CA 包的来源，`file` 或 `data`。                                                                            |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |        | multisite | 否   | **受信任证书路径：** 调度器可读的 PEM CA 包路径（优先级 `file`）。                                                                |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |        | multisite | 否   | **受信任证书数据：** 以 base64 或明文 PEM 形式提供的 CA 包（优先级 `data`）。                                                     |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`    | multisite | 否   | **SSL 验证深度：** 上游证书链中的验证深度。                                                                                       |
| `GRPC_SSL_CLIENT_CERT_PRIORITY`         | `file` | multisite | 否   | **客户端证书优先级：** 客户端证书与私钥的来源，`file` 或 `data`。                                                                 |
| `GRPC_SSL_CLIENT_CERT`                  |        | multisite | 否   | **客户端证书路径：** 用于双向 TLS 的、呈递给上游的 PEM 客户端证书（优先级 `file`）。                                              |
| `GRPC_SSL_CLIENT_CERT_DATA`             |        | multisite | 否   | **客户端证书数据：** 以 base64 或明文 PEM 形式提供的客户端证书（优先级 `data`）。                                                 |
| `GRPC_SSL_CLIENT_KEY`                   |        | multisite | 否   | **客户端私钥路径：** 与客户端证书匹配的 PEM 私钥（优先级 `file`）。不得加密。                                                     |
| `GRPC_SSL_CLIENT_KEY_DATA`              |        | multisite | 否   | **客户端私钥数据：** 以 base64 或明文 PEM 形式提供的客户端私钥（优先级 `data`）。                                                 |
| `GRPC_SSL_CRL`                          |        | multisite | 否   | **CRL 路径：** 验证上游时应用的 PEM 吊销列表；仅在 `GRPC_SSL_VERIFY=yes` 时应用。优先于 CRL 数据设置；路径已设置但文件缺失时视为错误，不会回退使用数据设置。 |
| `GRPC_SSL_CRL_DATA`                     |        | multisite | 否   | **CRL 数据：** 以 base64 或明文 PEM 形式提供的吊销列表。仅在 CRL 路径为空时使用。                                                 |
| `GRPC_SSL_PROTOCOLS`                    |        | multisite | 否   | **上游 SSL 协议：** 提供给上游的 TLS 版本。留空则保持 NGINX 默认值。                                                              |
| `GRPC_SSL_CIPHERS`                      |        | multisite | 否   | **上游 SSL 加密套件：** 提供给上游的加密套件字符串。留空则保持 NGINX 默认值。                                                     |
| `GRPC_NEXT_UPSTREAM`                    |        | multisite | 是   | **下一个上游条件：** `grpc_next_upstream` 的值。                                                                                  |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |        | multisite | 是   | **下一个上游超时：** `grpc_next_upstream_timeout` 的值。                                                                          |
| `GRPC_NEXT_UPSTREAM_TRIES`              |        | multisite | 是   | **下一个上游重试次数：** `grpc_next_upstream_tries` 的值。                                                                        |
| `GRPC_AUTH_REQUEST`                     |        | multisite | 是   | **认证请求：** `auth_request` 的值，用于通过外部提供者进行认证。                                                                  |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |        | multisite | 是   | **认证请求登录 URL：** 当认证请求返回 401 时的重定向目标。支持片段（`#`）。                                                       |
| `GRPC_AUTH_REQUEST_SET`                 |        | multisite | 是   | **认证请求 Set：** 分号分隔的 `auth_request_set` 值列表。                                                                         |
| `GRPC_INCLUDES`                         |        | multisite | 是   | **附加 include：** 在 gRPC `location` 块中追加的、以空格分隔的 include 文件列表。                                                 |
| `GRPC_MAX_CLIENT_SIZE`                  |        | multisite | 是   | **最大请求体大小：** 该 location 的 `client_max_body_size` 值（`0` 表示不限制）。留空时回退到服务级 `MAX_CLIENT_SIZE`。           |

`GRPC_HOST`、`GRPC_URL`、`GRPC_HEADERS`、`GRPC_HIDE_HEADERS`、`GRPC_HEADERS_CLIENT`、`GRPC_PASS_HEADERS`、`GRPC_IGNORE_HEADERS`、`GRPC_BUFFER_SIZE`、`GRPC_CONNECT_TIMEOUT`、`GRPC_READ_TIMEOUT`、`GRPC_SEND_TIMEOUT`、`GRPC_SOCKET_KEEPALIVE`、`GRPC_NEXT_UPSTREAM{,_TIMEOUT,_TRIES}`、`GRPC_AUTH_REQUEST{,_SIGNIN_URL,_SET}`、`GRPC_INCLUDES` 和 `GRPC_MAX_CLIENT_SIZE` 均支持数字后缀，用于多个上游/location（`GRPC_HOST_2`、`GRPC_URL_2` 等）。`GRPC_HEADERS_CLIENT` 遵循 NGINX 的 `add_header` 语义（需要时追加 `always`）。认证登录 URL 仍支持片段（`#`）。ModSecurity 在 gRPC location 中仍保持禁用。

!!! warning "gRPC Location 中的 ModSecurity"
    由于 ModSecurity 目前无法稳定支持 gRPC 流量模式，本插件生成的 gRPC `location` 块中会自动关闭 ModSecurity。

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
    GRPC_NEXT_UPSTREAM: "error timeout http_502"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```
