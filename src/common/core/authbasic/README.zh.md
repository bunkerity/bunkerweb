Auth Basic 插件提供 HTTP 基本认证来保护您的网站或特定资源。此功能通过要求用户在访问受保护内容之前输入用户名和密码来增加额外的安全层。这种类型的身份验证实现简单，并得到浏览器的广泛支持。

**工作原理：**

1.  当用户尝试访问您网站的受保护区域时，服务器会发送一个身份验证质询。
2.  浏览器会显示一个登录对话框，提示用户输入用户名和密码。
3.  用户输入他们的凭据，这些凭据将被发送到服务器。
4.  如果凭据有效，用户将被授予访问所请求内容的权限。
5.  如果凭据无效，将向用户提供一个错误消息，状态码为 401 Unauthorized。

### 如何使用

请按照以下步骤启用和配置 Auth Basic 身份验证：

1.  **启用该功能：** 在您的 BunkerWeb 配置中将 `USE_AUTH_BASIC` 设置为 `yes`。
2.  **选择保护范围：** 通过配置 `AUTH_BASIC_LOCATION` 设置，决定是保护整个网站还是仅保护特定 URL。
3.  **定义凭据：** 使用 `AUTH_BASIC_USER` 和 `AUTH_BASIC_PASSWORD` 设置至少设置一对用户名和密码。
4.  **自定义消息：** 可选地更改 `AUTH_BASIC_TEXT` 以在登录提示中显示自定义消息。

### 配置设置

| 设置                  | 默认值            | 上下文    | 多个 | 描述                                                                                                    |
| --------------------- | ----------------- | --------- | ---- | ------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | 否   | **启用基本认证：** 设置为 `yes` 以启用基本身份验证。                                                    |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | 否   | **保护范围：** 设置为 `sitewide` 以保护整个站点，或指定一个 URL 路径（例如 `/admin`）以仅保护特定区域。 |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | 是   | **用户名：** 身份验证所需的用户名。您可以定义多个用户名/密码对。                                        |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | 是   | **密码：** 身份验证所需的密码。密码使用 bcrypt 哈希以实现最大安全性。                                   |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | 否   | **提示文本：** 显示给用户的身份验证提示中的消息。                                                       |

!!! warning "安全注意事项"
    HTTP 基本认证以 Base64 编码（非加密）传输凭据。虽然在通过 HTTPS 使用时这是可以接受的，但在普通 HTTP 上不应被认为是安全的。使用基本身份验证时，请务必启用 SSL/TLS。

!!! tip "使用多个凭据"
    您可以为访问配置多个用户名/密码对。每个 `AUTH_BASIC_USER` 设置都应有一个对应的 `AUTH_BASIC_PASSWORD` 设置。

### 示例配置

=== "全站保护"

    要用一组凭据保护您的整个网站：

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "保护特定区域"

    仅保护特定路径，例如管理面板：

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "多个用户"

    为多个用户设置不同的凭据：

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # 第一个用户
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # 第二个用户
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # 第三个用户
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```
