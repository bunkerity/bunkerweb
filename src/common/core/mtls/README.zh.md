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
2. **提供 CA 证书包：** 使用 PEM 文件存放可信颁发者，并在 `MTLS_CA_CERTIFICATE` 中配置其绝对路径。
3. **选择验证模式：** `on` 强制要求证书，`optional` 允许回退，`optional_no_ca` 仅用于短期诊断。
4. **调节链路深度：** 若组织存在多级中间证书，可调整 `MTLS_VERIFY_DEPTH`。
5. **转发验证结果（可选）：** 若后端需要检查证书信息，请保持 `MTLS_FORWARD_CLIENT_HEADERS` 为 `yes`。
6. **维护吊销数据：** 若发布 CRL，请填写 `MTLS_CRL`，使 BunkerWeb 能拒绝已吊销的证书。

### 配置设置

| 设置                         | 默认值 | 上下文    | 多个 | 说明                                                                                                                                              |
| ---------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                   | `no`   | multisite | 否   | **启用 mutual TLS：** 为当前站点启用客户端证书认证。                                                                                                |
| `MTLS_CA_CERTIFICATE`        |        | multisite | 否   | **客户端 CA 证书包：** 指向受信任客户端 CA 证书包（PEM）的绝对路径。当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时必填；路径必须可读。               |
| `MTLS_VERIFY_CLIENT`         | `on`   | multisite | 否   | **验证模式：** 选择是否强制要求证书（`on`）、允许可选证书（`optional`），或在不验证 CA 的情况下接受证书（`optional_no_ca`）。                         |
| `MTLS_URL`                   |        | multisite | 是   | **mTLS URL：** 用于与请求 URI 匹配的正则表达式，仅在匹配的路径上强制要求有效的客户端证书（仅 HTTP）。需要将 `MTLS_VERIFY_CLIENT` 设置为 `optional` 或 `optional_no_ca`。留空则对整个站点强制 mTLS。 |
| `MTLS_VERIFY_DEPTH`          | `2`    | multisite | 否   | **验证深度：** 接受的客户端证书最大链深。                                                                                                          |
| `MTLS_FORWARD_CLIENT_HEADERS`| `yes`  | multisite | 否   | **转发客户端请求头：** 传播验证结果（状态、DN、签发者、序列号、指纹和有效期等 `X-SSL-Client-*` 请求头）。客户端自行发送的 `X-SSL-*` 请求头总是在入口处被剥离，因此这些值无法被伪造。 |
| `MTLS_CRL`                   |        | multisite | 否   | **客户端 CRL 路径：** 指向 PEM 编码证书吊销列表的可选路径。只要客户端证书校验处于启用状态即会生效，不会被静默跳过。                                                         |

!!! tip "保持证书最新"
    将 CA 证书包和吊销列表存放在 **BunkerWeb 实例**可读取的挂载卷中：`MTLS_CA_CERTIFICATE` 和 `MTLS_CRL` 由 NGINX 自行打开，没有任何 job 会分发它们，因此在组件分离部署中，仅挂载到 Scheduler 所在位置是不够的。

!!! warning "严格模式需提供 CA 证书包"
    当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时，必须提供 CA 证书包。如果 `MTLS_CA_CERTIFICATE` 为空，BunkerWeb 会拒绝该站点的 TLS 握手（`ssl_reject_handshake`），而不是在不校验客户端证书的情况下继续提供服务；明文 HTTP 仍会响应，因此 ACME `http-01` 续期不受影响。如果已设置路径但实例上的文件缺失或不可读，NGINX 将拒绝加载配置——重载时保留此前的配置，冷启动时实例无法启动。`MTLS_CRL` 同理：已配置的吊销列表一定会生效，不会被静默跳过。`optional_no_ca` 仅建议用于排查问题，因为它会降低认证强度。 被拒绝的握手**确实**会被记录为 `handshake rejected`，位置是 BunkerWeb 实例的 NGINX 错误日志（`ERROR_LOG`，默认 `/var/log/bunkerweb/error.log`），而不是 Scheduler 的日志。该记录的级别为 `info`，而 `LOG_LEVEL` 默认为 `notice`，因此需将 `LOG_LEVEL` 设为 `info` 才能看到。

!!! info "受信证书与验证"
    `ssl_client_certificate` 与 `ssl_trusted_certificate` 都是用于校验客户端证书的信任库，唯一区别在于前者会在 CertificateRequest 中向客户端声明其 CA，后者不会。BunkerWeb 此前把两者指向同一个文件，因此后者没有任何额外作用，现已移除。它同时也是启用 `ssl_stapling` 时用来校验 OCSP 响应的信任库——而 BunkerWeb 从不启用该功能，所以指向*客户端* CA 证书包时它始终无效，但这是一个陷阱，如今已经消除。

!!! info "入站 `X-SSL-*` 请求头总是被剥离"
    在请求到达您的应用之前，BunkerWeb 会移除客户端自行发送的每一个 `X-SSL-*` 请求头：适用于所有站点，无论是否启用 mTLS，HTTP/1.1、HTTP/2 与 HTTP/3 一视同仁。只有 BunkerWeb 从已验证的 TLS 握手中导出的值才会被转发，且仅当 `MTLS_FORWARD_CLIENT_HEADERS` 为 `yes` 时才转发，因此客户端无法伪造 `X-SSL-Client-Verify: SUCCESS`。 您的应用仍须校验 `X-SSL-Client-Verify` 是否为 `SUCCESS`：在 `MTLS_VERIFY_CLIENT=optional` 下，匿名请求同样会被转发，其 `X-SSL-Client-Verify` 为 `NONE` 且 `X-SSL-Client-DN` 为空，若把 DN 当作认证凭据就会放行该请求。

    如果 BunkerWeb 位于另一个自行终结 mTLS 并注入这些请求头的代理之后，请在剥离之前捕获该值并重新发布。添加一份自定义的 `server-http` 配置：

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    然后通过 `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"` 转发。仅使用 `REVERSE_PROXY_HEADERS` 无效：`proxy_set_header` 求值时 `$http_x_ssl_client_verify` 已经为空，而 `set` 运行在 server-rewrite 阶段，早于剥离。

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
