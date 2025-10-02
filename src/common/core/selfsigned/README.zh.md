自签名证书插件可直接在 BunkerWeb 中自动生成和管理 SSL/TLS 证书，无需外部证书颁发机构即可启用安全的 HTTPS 连接。此功能在开发环境、内部网络或需要快速部署 HTTPS 而无需配置外部证书时特别有用。

**工作原理：**

1.  启用后，BunkerWeb 会为您的已配置域名自动生成一个自签名 SSL/TLS 证书。
2.  该证书包含您配置中定义的所有服务器名称，确保每个域名的 SSL 验证正确无误。
3.  证书被安全地存储，并用于加密所有到您网站的 HTTPS 流量。
4.  证书在到期前会自动续订，确保 HTTPS 的持续可用性。

!!! warning "浏览器安全警告"
当用户访问使用自签名证书的网站时，浏览器会显示安全警告，因为这些证书未经受信任的证书颁发机构验证。对于生产环境，请考虑改用 [Let's Encrypt](#lets-encrypt)。

### 如何使用

请按照以下步骤配置和使用自签名证书功能：

1.  **启用该功能：** 将 `GENERATE_SELF_SIGNED_SSL` 设置为 `yes` 以启用自签名证书生成。
2.  **选择加密算法：** 使用 `SELF_SIGNED_SSL_ALGORITHM` 设置选择您偏好的算法。
3.  **配置有效期：** 可选地使用 `SELF_SIGNED_SSL_EXPIRY` 设置证书的有效时长。
4.  **设置证书主题：** 使用 `SELF_SIGNED_SSL_SUBJ` 设置配置证书主题。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，证书会自动生成并应用于您的域名。

!!! tip "流模式配置"
对于流模式，请配置 `LISTEN_STREAM_PORT_SSL` 设置以指定 SSL/TLS 监听端口。此步骤对于在流模式下正常运行至关重要。

### 配置设置

| 设置                        | 默认值                 | 上下文    | 多选 | 描述                                                                                           |
| --------------------------- | ---------------------- | --------- | ---- | ---------------------------------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | 否   | **启用自签名：** 设置为 `yes` 以启用自动自签名证书生成。                                       |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | 否   | **证书算法：** 用于证书生成的算法：`ec-prime256v1`、`ec-secp384r1`、`rsa-2048` 或 `rsa-4096`。 |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | 否   | **证书有效期：** 自签名证书的有效天数（默认为 1 年）。                                         |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | 否   | **证书主题：** 证书的主题字段，用于标识域名。                                                  |

!!! tip "开发环境"
自签名证书非常适合开发和测试环境，在这些环境中您需要 HTTPS，但不需要受公共浏览器信任的证书。

!!! info "证书信息"
生成的自签名证书使用指定的算法（默认为使用 prime256v1 曲线的椭圆曲线加密），并包含配置的主题，确保您的域名功能正常。

### 配置示例

=== "基本配置"

    一个使用默认设置的自签名证书的简单配置：

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "短期证书"

    证书过期更频繁的配置（用于定期测试证书续订流程）：

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "使用 RSA 证书进行测试"

    一个测试环境的配置，其中域名使用自签名的 RSA 证书：

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```
