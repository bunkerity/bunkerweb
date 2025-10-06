自定义 SSL 证书插件允许您在 BunkerWeb 中使用您自己的 SSL/TLS 证书，而不是自动生成的证书。如果您拥有来自受信任的证书颁发机构 (CA) 的现有证书、需要使用具有特定配置的证书，或者希望在整个基础设施中保持一致的证书管理，此功能特别有用。

**工作原理：**

1.  您通过指定文件路径或以 base64 编码或纯文本 PEM 格式提供数据的方式，向 BunkerWeb 提供您的证书和私钥文件。
2.  BunkerWeb 会验证您的证书和密钥，以确保它们的格式正确且可用。
3.  建立安全连接时，BunkerWeb 会提供您的自定义证书，而不是自动生成的证书。
4.  BunkerWeb 会自动监控您的证书的有效性，并在其即将到期时显示警告。
5.  您可以完全控制证书管理，允许您使用来自您偏好的任何颁发机构的证书。

!!! info "自动证书监控"
    当您通过将 `USE_CUSTOM_SSL` 设置为 `yes` 来启用自定义 SSL/TLS 时，BunkerWeb 会自动监控 `CUSTOM_SSL_CERT` 中指定的自定义证书。它会每天检查更改，并在检测到任何修改时重新加载 NGINX，确保始终使用最新的证书。

### 如何使用

请按照以下步骤配置和使用自定义 SSL 证书功能：

1.  **启用该功能：** 将 `USE_CUSTOM_SSL` 设置为 `yes` 以启用自定义证书支持。
2.  **选择一种方法：** 决定是通过文件路径还是以 base64 编码/纯文本数据提供证书，并使用 `CUSTOM_SSL_CERT_PRIORITY` 设置优先级。
3.  **提供证书文件：** 如果使用文件路径，请指定您的证书和私钥文件的位置。
4.  **或者提供证书数据：** 如果使用数据，请以 base64 编码的字符串或纯文本 PEM 格式提供您的证书和密钥。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，BunkerWeb 会自动将您的自定义证书用于所有 HTTPS 连接。

!!! tip "流模式配置"
    对于流模式，您必须配置 `LISTEN_STREAM_PORT_SSL` 设置以指定 SSL/TLS 监听端口。此步骤对于在流模式下正常运行至关重要。

### 配置设置

| 设置                       | 默认值 | 上下文    | 多个 | 描述                                                                                        |
| -------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`   | multisite | 否   | **启用自定义 SSL：** 设置为 `yes` 以使用您自己的证书而不是自动生成的证书。                  |
| `CUSTOM_SSL_CERT_PRIORITY` | `file` | multisite | 否   | **证书优先级：** 选择优先使用文件路径中的证书还是 base64 数据中的证书（`file` 或 `data`）。 |
| `CUSTOM_SSL_CERT`          |        | multisite | 否   | **证书路径：** 您的 SSL 证书或证书捆绑包文件的完整路径。                                    |
| `CUSTOM_SSL_KEY`           |        | multisite | 否   | **私钥路径：** 您的 SSL 私钥文件的完整路径。                                                |
| `CUSTOM_SSL_CERT_DATA`     |        | multisite | 否   | **证书数据：** 以 base64 格式编码或以纯文本 PEM 格式表示的您的证书。                        |
| `CUSTOM_SSL_KEY_DATA`      |        | multisite | 否   | **私钥数据：** 以 base64 格式编码或以纯文本 PEM 格式表示的您的私钥。                        |

!!! warning "安全注意事项"
    使用自定义证书时，请确保您的私钥得到妥善保护并具有适当的权限。文件必须可由 BunkerWeb 调度器读取。

!!! tip "证书格式"
    BunkerWeb 需要 PEM 格式的证书。如果您的证书是其他格式，您可能需要先进行转换。

!!! info "证书链"
    如果您的证书包含一个链（中间证书），您应该按正确的顺序提供完整的证书链，首先是您的证书，然后是任何中间证书。

### 示例配置

=== "使用文件路径"

    一个使用磁盘上的证书和密钥文件的配置：

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "使用 Base64 数据"

    一个使用 base64 编码的证书和密钥数据的配置：

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```

=== "使用纯文本 PEM 数据"

    一个使用 PEM 格式的纯文本证书和密钥数据的配置：

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
      -----BEGIN CERTIFICATE-----
      MIIDdzCCAl+gAwIBAgIUJH...certificate content...AAAA
      -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
      -----BEGIN PRIVATE KEY-----
      MIIEvQIBADAN...key content...AAAA
      -----END PRIVATE KEY-----
    ```

=== "回退配置"

    一个优先使用文件，但如果文件不可用则回退到 base64 数据的配置：

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```
