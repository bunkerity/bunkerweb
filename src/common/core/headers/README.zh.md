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
