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

| 设置                          | 默认值            | 上下文    | 多选 | 描述                                                                                               |
| ----------------------------- | ----------------- | --------- | ---- | -------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | 否   | **HTTP 重定向到 HTTPS：** 当设置为 `yes` 时，所有 HTTP 请求都会重定向到 HTTPS。                    |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | 否   | **自动 HTTP 重定向到 HTTPS：** 当设置为 `yes` 时，如果检测到 HTTPS，则自动将 HTTP 重定向到 HTTPS。 |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | 否   | **SSL 协议：** 要支持的 SSL/TLS 协议的空格分隔列表。                                               |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | 否   | **SSL 密码级别：** 密码套件的预设安全级别（`modern`、`intermediate` 或 `old`）。                   |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | 否   | **自定义 SSL 密码：** 用于 SSL/TLS 连接的密码套件的冒号分隔列表（覆盖级别）。                      |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | multisite | 否   | **SSL 会话缓存大小：** SSL 会话缓存的大小（例如 `10m`、`512k`）。设置为 `off` 或 `none` 以禁用。   |

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
