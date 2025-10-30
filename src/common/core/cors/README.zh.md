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
