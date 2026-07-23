Mutual TLS（mTLS）插件可在关键站点上强制执行客户端证书认证，确保只有受信任实体才能访问敏感资源。启用后，BunkerWeb 会在请求进入业务前完成身份鉴别，从而保护内部工具与合作伙伴集成。

BunkerWeb 会基于您配置的 CA 证书包和策略评估每一次 TLS 握手。未满足规则的客户端会被拦截，通过验证的连接则可以将证书细节传递给后端应用，以便执行更精细的授权控制。

**工作原理：**

1. 插件持续监控所选站点的 HTTPS 握手。
2. 在 TLS 交换阶段，BunkerWeb 检查客户端证书，并与指定的受信任存储进行链路校验。
3. 验证模式决定是否拒绝、宽松接受或仅用于诊断地放行未携带证书的客户端。
4. （可选）BunkerWeb 通过 `X-SSL-Client-*` 请求头暴露验证结果，便于上游应用实现自定义的访问逻辑。

!!! success "主要优势"

      1. **强化边界防护：** 只有完成身份验证的机器与用户才能访问核心路径。
      2. **灵活信任策略：** 可根据接入流程在严格与可选模式之间切换。
      3. **应用层可见性：** 将证书指纹和身份信息传递给下游服务，便于审计。
      4. **多层安全防护：** 将 mTLS 与 BunkerWeb 其他插件（如限流、黑白名单）组合使用，构建纵深防御。

### 使用步骤

遵循以下步骤安全部署 Mutual TLS：

1. **启用功能：** 在目标站点将 `USE_MTLS` 设置为 `yes`。
2. **提供 CA 证书包：** 将 `MTLS_CA_CERTIFICATE` 指向 Scheduler 可读取的 PEM 文件，或通过 `MTLS_CA_CERTIFICATE_DATA` 直接提供 base64/PEM 内联数据。Scheduler 会验证、缓存并将证书包分发到每个实例，无需逐实例挂载。
3. **选择验证模式：** `on` 强制要求证书，`optional` 允许回退，`optional_no_ca` 仅用于短期诊断。
4. **调节链路深度：** 若组织存在多级中间证书，可调整 `MTLS_VERIFY_DEPTH`。
5. **转发验证结果（可选）：** 若后端需要检查证书信息，请保持 `MTLS_FORWARD_CLIENT_HEADERS` 为 `yes`。
6. **维护吊销数据：** 若发布 CRL，请配置 `MTLS_CRL`（或 `MTLS_CRL_DATA`），使 BunkerWeb 能拒绝已吊销的证书。

### 配置设置

| 设置                            | 默认值 | 上下文    | 多个 | 说明                                                                                                                                              |
| -------------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                      | `no`   | multisite | 否   | **启用 mutual TLS：** 为当前站点启用客户端证书认证。                                                                                                |
| `MTLS_CA_CERTIFICATE_PRIORITY`  | `file` | multisite | 否   | **客户端 CA 证书包优先级：** 客户端 CA 证书包的来源：`file`（路径）或 `data`（base64/PEM）。                                                        |
| `MTLS_CA_CERTIFICATE`           |        | multisite | 否   | **客户端 CA 证书包路径：** 受信任客户端 CA 证书包（PEM）的路径，需 Scheduler 可读。当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时必填。            |
| `MTLS_CA_CERTIFICATE_DATA`      |        | multisite | 否   | **客户端 CA 证书包数据：** 直接以 base64 或 PEM 提供的受信任客户端 CA 证书包（例如通过 Web UI）。                                                   |
| `MTLS_VERIFY_CLIENT`            | `on`   | multisite | 否   | **验证模式：** 选择是否强制要求证书（`on`）、允许可选证书（`optional`），或在不验证 CA 的情况下接受证书（`optional_no_ca`）。                         |
| `MTLS_URL`                      |        | multisite | 是   | **mTLS URL：** 用于与请求 URI 匹配的正则表达式，仅在匹配的路径上强制要求有效的客户端证书（仅 HTTP）。需要将 `MTLS_VERIFY_CLIENT` 设置为 `optional` 或 `optional_no_ca`。留空则对整个站点强制 mTLS。 |
| `MTLS_VERIFY_DEPTH`             | `2`    | multisite | 否   | **验证深度：** 接受的客户端证书最大链深。                                                                                                          |
| `MTLS_FORWARD_CLIENT_HEADERS`   | `yes`  | multisite | 否   | **转发客户端请求头：** 传播验证结果（状态、DN、签发者、序列号、指纹和有效期等 `X-SSL-Client-*` 请求头）。                                          |
| `MTLS_CRL_PRIORITY`             | `file` | multisite | 否   | **客户端 CRL 优先级：** CRL 的来源：`file`（路径）或 `data`（base64/PEM）。                                                                        |
| `MTLS_CRL`                      |        | multisite | 否   | **客户端 CRL 路径：** 指向 PEM 编码证书吊销列表的可选路径，需 Scheduler 可读。仅在成功加载 CA 证书包时生效。NGINX 要求 CRL 文件包含验证链中每个 CA 的吊销列表。 |
| `MTLS_CRL_DATA`                 |        | multisite | 否   | **客户端 CRL 数据：** 直接以 base64 或 PEM 提供的吊销列表。                                                                                        |

!!! tip "配置一次，处处分发"
    CA 证书包和吊销列表无需挂载到 BunkerWeb 容器中。只需将文件路径或内联数据提供给 Scheduler；Scheduler 会验证、缓存并将其分发到每个实例。更新会在下一次任务运行时自动获取并重新分发。

!!! warning "严格模式需提供 CA 证书包"
    当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时，Scheduler 必须能够验证并缓存客户端 CA 证书包。如果没有可用的证书包，BunkerWeb 会在每个实例上跳过 mTLS 指令，避免服务在证书引用无效或缺失的情况下运行。`optional_no_ca` 仅建议用于排查问题，因为它会降低认证强度。若 Scheduler 在 `/var/cache/bunkerweb` 非持久化的情况下重启，mTLS 将保持禁用，直到首次任务运行完成并重新分发 CA 证书包；因此在需要严格执行策略的场景下，请使用持久化的缓存卷。

!!! info "受信证书与验证"
    BunkerWeb 使用同一份 CA 证书包完成链路校验与信任构建，确保吊销检查和握手验证保持一致。

!!! warning "按路径的 mTLS 需要可选模式"
    NGINX 的 `ssl_verify_client` 指令仅在 `server` 上下文有效，无法置于 `location` 块中。若只想在部分路径上要求证书，请将 `MTLS_VERIFY_CLIENT` 设为 `optional`（或 `optional_no_ca`），使所有路径都能完成握手，然后在 `MTLS_URL_n` 中列出受保护的路径。BunkerWeb 随后会在 Lua 中按请求对匹配的 URL 强制证书。如果在设置 `MTLS_URL_n` 的同时仍将 `MTLS_VERIFY_CLIENT` 保持为 `on`，NGINX 会在握手阶段直接拒绝无证书的客户端，按路径逻辑无从生效，强制仍是全站范围。

!!! info "可选模式下浏览器的证书提示"
    TLS 握手发生在 NGINX 获知请求 URL 之前，因此在 `optional` 模式下，NGINX 仍会在每次连接时发送 `CertificateRequest`。强制变为按路径，但握手层面的请求邀请不会——浏览器在未受保护的路径上仍可能提示选择证书（行为因浏览器而异）。在这些路径上，无论是否提供证书，BunkerWeb 都会放行请求。

### 配置示例

=== "严格访问控制"

    要求客户端提供由您的私有 CA 签发的有效证书，并将验证信息转发给后端：

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "可选客户端认证"

    允许匿名用户访问，但在客户端提供证书时转发证书详情：

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "无 CA 的诊断"

    即便证书无法链到受信任的 CA 证书包，也允许连接完成。仅用于排查问题：

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

=== "按路径的 mTLS（例如仅 `/login`）"

    仅在选定路径上要求客户端证书，同时保持站点其余部分开放。验证以 `optional` 模式运行，使未认证路径能够完成握手；随后 BunkerWeb 会在 Lua 中按请求对匹配 `MTLS_URL_n` 的 URL 强制证书（每个条目一个正则）：

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_URL_1: "^/login"
    MTLS_URL_2: "^/admin"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | 请求         | 证书        | 结果                          |
    | ------------ | ----------- | ----------------------------- |
    | `GET /`      | 无          | 允许（路径不受 mTLS 约束）    |
    | `GET /login` | 无          | 拒绝（`403`）                 |
    | `GET /login` | 有效        | 允许，转发 `X-SSL-Client-*`   |
    | `GET /login` | 无效 / 过期 | 拒绝（`403`）                 |
