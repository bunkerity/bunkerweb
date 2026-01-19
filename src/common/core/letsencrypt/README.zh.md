Let's Encrypt 插件通过自动化创建、续订和配置来自 Let's Encrypt 的免费证书，简化了 SSL/TLS 证书管理。此功能可为您的网站启用安全的 HTTPS 连接，无需手动管理证书的复杂性，从而降低成本和管理开销。

**工作原理：**

1.  启用后，BunkerWeb 会自动检测为您的网站配置的域名。
2.  BunkerWeb 从 Let's Encrypt 的证书颁发机构请求免费的 SSL/TLS 证书。
3.  通过 HTTP 验证（证明您控制网站）或 DNS 验证（证明您控制域名的 DNS）来验证域名所有权。
4.  证书会自动为您的域名安装和配置。
5.  BunkerWeb 会在证书到期前在后台处理续订事宜，确保 HTTPS 的持续可用性。
6.  整个过程完全自动化，初次设置后几乎无需干预。

!!! info "先决条件"
    要使用此功能，请确保为每个域名配置了正确的 DNS **A 记录**，指向 BunkerWeb 可访问的公共 IP 地址。没有正确的 DNS 配置，域名验证过程将失败。

### 如何使用

请按照以下步骤配置和使用 Let's Encrypt 功能：

1.  **启用该功能：** 将 `AUTO_LETS_ENCRYPT` 设置为 `yes` 以启用自动证书颁发和续订。
2.  **提供联系电子邮件（建议填写）：** 使用 `EMAIL_LETS_ENCRYPT` 设置输入您的电子邮件地址，以便 Let's Encrypt 在证书即将过期时提醒您。如果留空，BunkerWeb 会在没有地址的情况下注册（使用 Certbot 的 `--register-unsafely-without-email` 选项），但您将不会收到任何提醒或恢复邮件。
3.  **选择验证类型：** 使用 `LETS_ENCRYPT_CHALLENGE` 设置选择 `http` 或 `dns` 验证。
4.  **配置 DNS 提供商：** 如果使用 DNS 验证，请指定您的 DNS 提供商和凭据。
5.  **选择证书配置文件：** 使用 `LETS_ENCRYPT_PROFILE` 设置选择您偏好的证书配置文件（classic、tlsserver 或 shortlived）。
6.  **让 BunkerWeb 处理其余部分：** 配置完成后，证书将根据需要自动颁发、安装和续订。

!!! tip "证书配置文件"
    Let's Encrypt 为不同的用例提供了不同的证书配置文件：- **classic**：通用证书，有效期为 90 天（默认）- **tlsserver**：针对 TLS 服务器身份验证进行了优化，有效期为 90 天，有效负载更小 - **shortlived**：增强安全性，有效期为 7 天，适用于自动化环境 - **custom**：如果您的 ACME 服务器支持不同的配置文件，请使用 `LETS_ENCRYPT_CUSTOM_PROFILE` 进行设置。

!!! info "配置文件可用性"
    请注意，`tlsserver` 和 `shortlived` 配置文件目前可能并非在所有环境或所有 ACME 客户端中都可用。`classic` 配置文件具有最广泛的兼容性，推荐给大多数用户。如果所选的配置文件不可用，系统将自动回退到 `classic` 配置文件。

### 配置设置

| 设置                                        | 默认值    | 上下文    | 多选 | 描述                                                                                                                                                                               |
| ------------------------------------------- | --------- | --------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | 否   | **启用 Let's Encrypt：** 设置为 `yes` 以启用自动证书颁发和续订。                                                                                                                   |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | 否   | **传递 Let's Encrypt 请求：** 设置为 `yes` 以将 Let's Encrypt 请求传递给 Web 服务器。当 BunkerWeb 位于处理 SSL 的另一个反向代理后面时，此功能很有用。                              |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | 否   | **联系电子邮件：** 用于 Let's Encrypt 到期提醒的电子邮件地址。只有在接受不接收任何警报或恢复邮件的情况下才可留空（此时 Certbot 会使用 `--register-unsafely-without-email` 注册）。 |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | 否   | **验证类型：** 用于验证域名所有权的方法。选项：`http` 或 `dns`。                                                                                                                   |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | 否   | **DNS 提供商：** 使用 DNS 验证时，要使用的 DNS 提供商（例如 cloudflare、route53、digitalocean）。                                                                                  |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | 否   | **DNS 传播：** 等待 DNS 传播的时间（秒）。如果未提供值，则使用提供商的默认传播时间。                                                                                               |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | 是   | **凭证项：** 用于 DNS 提供商身份验证的配置项（例如 `cloudflare_api_token 123456`）。值可以是原始文本、base64 编码或 JSON 对象。                                                    |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | 否   | **自动解码 Base64 DNS 凭据：** 启用后自动解码 base64 编码的 DNS 提供商凭据（`rfc2136` 提供商除外）。如果凭据故意为 base64，请设置为 `no`。                                         |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | 否   | **通配符证书：** 设置为 `yes` 时，为所有域名创建通配符证书。仅适用于 DNS 验证。                                                                                                    |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | 否   | **使用测试环境：** 设置为 `yes` 时，使用 Let's Encrypt 的测试环境进行测试。测试环境的速率限制较高，但生成的证书不受浏览器信任。                                                    |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | 否   | **清除旧证书：** 设置为 `yes` 时，在续订期间删除不再需要的旧证书。                                                                                                                 |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | 否   | **证书配置文件：** 选择要使用的证书配置文件。选项：`classic`（通用）、`tlsserver`（针对 TLS 服务器优化）或 `shortlived`（7 天证书）。                                              |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | 否   | **自定义证书配置文件：** 如果您的 ACME 服务器支持非标准配置文件，请输入自定义证书配置文件。如果设置了此项，它将覆盖 `LETS_ENCRYPT_PROFILE`。                                       |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | 否   | **最大重试次数：** 证书生成失败时重试的次数。设置为 `0` 以禁用重试。用于处理临时网络问题或 API 速率限制。                                                                          |

!!! info "信息和行为"
    - `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` 设置是一个多选设置，可用于为 DNS 提供商设置多个项目。这些项目将保存为缓存文件，Certbot 将从中读取凭据。
    - 如果未提供 `LETS_ENCRYPT_DNS_PROPAGATION` 设置，则使用提供商的默认传播时间。
    - 只要您从外部打开 `80/tcp` 端口，使用 `http` 验证的完全 Let's Encrypt 自动化就可以在流模式下工作。使用 `LISTEN_STREAM_PORT_SSL` 设置来选择您的侦听 SSL/TLS 端口。
    - 如果 `LETS_ENCRYPT_PASSTHROUGH` 设置为 `yes`，BunkerWeb 将不会自行处理 ACME 验证请求，而是将它们传递给后端 Web 服务器。这在 BunkerWeb 作为反向代理位于已配置为处理 Let's Encrypt 验证的另一台服务器前面的场景中很有用。

!!! tip "HTTP 与 DNS 验证"
    **HTTP 验证** 更容易设置，并且适用于大多数网站：

    - 要求您的网站在端口 80 上可公开访问
    - 由 BunkerWeb 自动配置
    - 不能用于通配符证书

    **DNS 验证** 提供更大的灵活性，并且是通配符证书所必需的：

    - 即使您的网站无法公开访问也能正常工作
    - 需要 DNS 提供商的 API 凭据
    - 通配符证书（例如 *.example.com）所必需
    - 在端口 80 被阻止或不可用时很有用

!!! warning "通配符证书"
    通配符证书仅适用于 DNS 验证。如果要使用它们，必须将 `USE_LETS_ENCRYPT_WILDCARD` 设置为 `yes` 并正确配置您的 DNS 提供商凭据。

!!! warning "速率限制"
    Let's Encrypt 对证书颁发施加速率限制。在测试配置时，通过将 `USE_LETS_ENCRYPT_STAGING` 设置为 `yes` 来使用测试环境，以避免达到生产环境的速率限制。测试证书不受浏览器信任，但对于验证您的设置很有用。

### 支持的 DNS 提供商

Let's Encrypt 插件支持广泛的 DNS 提供商进行 DNS 验证。每个提供商都需要使用 `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` 设置提供特定的凭据。

| 提供商            | 描述             | 强制性设置                                                                                                   | 可选设置                                                                                                                                                                                                                                                     | 文档                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                              | [文档](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | `api_token` 或 `email` 和 `api_key`                                                                          |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                              | [文档](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                              | [文档](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                              | [文档](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                              | [文档](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (默认: `600`)                                                                                                                                                                                                                                          | [文档](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (默认: `service_account`)<br>`auth_uri` (默认: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (默认: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (默认: `https://www.googleapis.com/oauth2/v1/certs`) | [文档](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (默认: `https://api.hosting.ionos.com`)                                                                                                                                                                                                           | [文档](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                              | [文档](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (默认: `ovh-eu`)                                                                                                                                                                                                                                  | [文档](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                              | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)            |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (默认: `53`)<br>`algorithm` (默认: `HMAC-SHA512`)<br>`sign_query` (默认: `false`)                                                                                                                                                                     | [文档](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                              | [文档](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                              | [文档](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |

### 配置示例

=== "基本 HTTP 验证"

    使用 HTTP 验证为单个域进行简单配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "使用通配符的 Cloudflare DNS"

    使用 Cloudflare DNS 为通配符证书进行配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token YOUR_API_TOKEN"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "AWS Route53 配置"

    使用 Amazon Route53 进行 DNS 验证的配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id YOUR_ACCESS_KEY"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key YOUR_SECRET_KEY"
    ```

=== "使用测试环境和重试进行测试"

    使用测试环境和增强的重试设置进行测试的配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "具有自定义传播时间的 DigitalOcean"

    使用 DigitalOcean DNS 并设置更长传播等待时间的配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token YOUR_API_TOKEN"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    使用 Google Cloud DNS 和服务帐户凭据的配置：

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id your-project-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id your-private-key-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key your-private-key"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email your-service-account-email"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id your-client-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url your-cert-url"
    ```
