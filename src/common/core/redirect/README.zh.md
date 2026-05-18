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
