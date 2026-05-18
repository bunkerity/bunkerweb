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

| 配置项                       | 默认值 | 上下文    | 可多值 | 说明                                                                                   |
| ---------------------------- | ------ | --------- | ------ | -------------------------------------------------------------------------------------- |
| `USE_GRPC`                   | `no`   | multisite | 否     | **启用 gRPC：** 设置为 `yes` 以启用 gRPC 代理。                                        |
| `GRPC_HOST`                  |        | multisite | 是     | **gRPC 上游：** `grpc_pass` 使用的值（例如 `grpc://service:50051` 或 `grpcs://...`）。 |
| `GRPC_URL`                   | `/`    | multisite | 是     | **Location URL：** 将被代理到 gRPC 上游的路径。                                        |
| `GRPC_CUSTOM_HOST`           |        | multisite | 否     | **自定义 Host 头：** 覆盖发送到上游的 `Host` 头。                                      |
| `GRPC_HEADERS`               |        | multisite | 是     | **额外上游请求头：** 分号分隔的 `grpc_set_header` 值列表。                             |
| `GRPC_HIDE_HEADERS`          |        | multisite | 是     | **隐藏响应头：** 空格分隔的 `grpc_hide_header` 值列表。                                |
| `GRPC_INTERCEPT_ERRORS`      | `yes`  | multisite | 否     | **拦截错误：** 启用/禁用 `grpc_intercept_errors`。                                     |
| `GRPC_CONNECT_TIMEOUT`       | `60s`  | multisite | 是     | **连接超时：** 与上游建立连接的超时时间。                                              |
| `GRPC_READ_TIMEOUT`          | `60s`  | multisite | 是     | **读取超时：** 从上游读取数据的超时时间。                                              |
| `GRPC_SEND_TIMEOUT`          | `60s`  | multisite | 是     | **发送超时：** 向上游发送数据的超时时间。                                              |
| `GRPC_SOCKET_KEEPALIVE`      | `off`  | multisite | 是     | **Socket Keepalive：** 启用/禁用与上游 socket 的 keepalive。                           |
| `GRPC_SSL_SNI`               | `no`   | multisite | 否     | **SSL SNI：** 启用/禁用 TLS 上游的 SNI。                                               |
| `GRPC_SSL_SNI_NAME`          |        | multisite | 否     | **SSL SNI 名称：** 当 `GRPC_SSL_SNI=yes` 时发送的 SNI 主机名。                         |
| `GRPC_NEXT_UPSTREAM`         |        | multisite | 是     | **下一个上游条件：** `grpc_next_upstream` 的值。                                       |
| `GRPC_NEXT_UPSTREAM_TIMEOUT` |        | multisite | 是     | **下一个上游超时：** `grpc_next_upstream_timeout` 的值。                               |
| `GRPC_NEXT_UPSTREAM_TRIES`   |        | multisite | 是     | **下一个上游重试次数：** `grpc_next_upstream_tries` 的值。                             |
| `GRPC_INCLUDES`              |        | multisite | 是     | **附加 include：** 在 gRPC `location` 块中追加的、以空格分隔的 include 文件列表。      |

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
    GRPC_NEXT_UPSTREAM: "error timeout unavailable"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```
