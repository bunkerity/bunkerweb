Mutual TLS（mTLS）插件可在关键站点上强制执行客户端证书认证，确保只有受信任实体才能访问敏感资源。启用后，BunkerWeb 会在请求进入业务前完成身份鉴别，从而保护内部工具与合作伙伴集成。

BunkerWeb 会基于您配置的 CA 证书包和策略评估每一次 TLS 握手。未满足规则的客户端会被拦截，通过验证的连接则可以将证书细节传递给后端应用，以便执行更精细的授权控制。

**工作原理：**

1. 插件持续监控所选站点的 HTTPS 握手。
2. 在 TLS 交换阶段，BunkerWeb 检查客户端证书，并与指定的受信任存储进行链路校验。
3. 验证模式决定是拒绝、放行未携带证书的客户端，还是仅用于诊断地接受。参见下文“各模式保护什么”。
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
3. **选择验证模式：** `on` 强制要求证书，`optional` 放行未携带证书的客户端（仅在 `MTLS_URL` 列出的路径上要求证书），`optional_no_ca` 仅用于短期诊断。
4. **调节链路深度：** 若组织存在多级中间证书，可调整 `MTLS_VERIFY_DEPTH`。
5. **转发验证结果（可选）：** 若后端需要检查证书信息，请保持 `MTLS_FORWARD_CLIENT_HEADERS` 为 `yes`。
6. **维护吊销数据：** 若发布 CRL，请配置 `MTLS_CRL`（或 `MTLS_CRL_DATA`），使 BunkerWeb 能拒绝已吊销的证书。
7. **选择明文 HTTP 的处理方式：** `MTLS_HTTP_POLICY`（默认 `redirect`）决定本应受 mTLS 保护的明文 HTTP 请求如何处理。
8. **决定证书失败是否计入封禁（可选）：** `MTLS_COUNT_BAD_BEHAVIOR`（默认 `no`）可让 Bad Behavior 统计这些失败。

Scheduler 会先验证完整的候选 CA 证书包以及每个 CRL，再替换缓存文件。若 CRL 无法解析，或其签发者存在于证书包中而签名校验失败，该 CRL 会被拒绝；若签发 CRL 的 CA 不在证书包内，则记录警告后照常发布，因为 NGINX 会使用客户端提供的中间证书构建证书链。如果数据无法读取、格式无效或不匹配，则保留原有的 CA/CRL 配对并记录错误。请同时轮换 CA 和对应的 CRL，并及时修复无效来源，尤其要在 CRL 到期前完成。同时清空 `MTLS_CRL` 和 `MTLS_CRL_DATA` 表示主动移除吊销检查。移除 CA 配置、禁用 mTLS 或删除服务会移除相应的缓存文件；只要 `USE_MTLS` 仍为 `yes` 且模式不是 `optional_no_ca`，`ssl_verify_client` 就会继续针对内置的占位 CA 生效：`on` 模式下所有客户端都会收到 400，`optional` 模式下所有出示证书的客户端都会收到 400，直到重新配置 CA 为止。实际发生的移除会请求重新加载配置。

`client-cert` 任务每小时运行一次，因此您在磁盘上替换的 CA 证书包或 CRL 文件会在一小时内被获取。对于已过期的 CRL（在发布新的 CRL 之前，由该 CA 签发的所有客户端都会被拒绝）和已过期的 CA 证书，任务会记录错误。对于 7 天内到期的 CRL、30 天内到期的 CA 证书、证书包中不是 CA 的证书，以及（一旦配置了至少一个 CRL）证书包中没有 CRL 的每个 CA，任务会记录警告。缺少 CRL 的警告会点名每个没有 CRL 的 CA：证书链中每个签发证书的 CA（包括根 CA）都必须在 CRL 集合中有对应的 CRL，否则证书链包含其签发证书的客户端会被拒绝。上述各种情况下，任务仍会发布这些材料：无论如何 NGINX 都会拒绝受影响的客户端，保留旧材料也不会更好。

### 各模式保护什么

“到达您的后端”指其他 BunkerWeb 插件也接受该请求之后，请求被转发到服务。

- **`on`：** 每个 HTTPS 请求都需要能通过 CA 证书包验证的证书。没有证书或证书无效的请求会收到 NGINX 返回的 `400`，永远不会到达您的后端。明文 HTTP 遵循 `MTLS_HTTP_POLICY`，覆盖所有路径。
- **不带 `MTLS_URL` 的 `optional`：** 本身不强制任何内容。没有证书的客户端可到达您的后端，无论 HTTPS 还是明文 HTTP。出示无效证书的客户端在 HTTPS 上仍会被拒绝（`400`）。当您的应用读取转发的 `X-SSL-Client-*` 请求头并自行决定时，可使用该模式。
- **带 `MTLS_URL` 的 `optional`：** 只有匹配规则的路径需要有效证书。在 HTTPS 上，没有证书的客户端在这些路径上会收到 `403`。在明文 HTTP 上，这些路径遵循 `MTLS_HTTP_POLICY`。其他路径无论有无证书都可到达您的后端，HTTPS 和 HTTP 均如此。出示无效证书的客户端在所有路径上都会被拒绝（`400`）。
- **`optional_no_ca`：** 用于诊断，而非保护。NGINX 会请求证书，并容忍信任链错误（自签名证书、未知颁发者、不受信任的证书链），因此没有任何 CA 担保的客户端仍能完成握手。其他任何验证错误仍会在 HTTPS 上以 `400` 拒绝客户端，例如已过期或已吊销的证书。不带 `MTLS_URL` 时不强制任何内容。带 `MTLS_URL` 时，匹配的路径仍需要能通过 CA 证书包验证的证书；若未配置 CA 证书包，则无法验证任何证书，这些路径会拒绝所有客户端。

在 `SECURITY_MODE=detect` 下，BunkerWeb 自身发出的拒绝和重定向（按路径规则、明文 HTTP 策略、无效的 `MTLS_URL` 规则）只会被记录而不会执行，请求会继续交给下一个插件。`on` 和 `optional` 在握手层面的检查由 NGINX 完成，不受安全模式影响。

### 明文 HTTP 请求

客户端证书只在 TLS 内传输，因此握手层面的检查无法保护明文 HTTP。对于 `USE_MTLS` 为 `yes` 的服务，`MTLS_HTTP_POLICY` 决定本应受 mTLS 保护的明文 HTTP 请求如何处理：`MTLS_VERIFY_CLIENT` 为 `on` 时是所有路径，否则是 `MTLS_URL` 匹配的路径。在不带 `MTLS_URL` 的 `optional` 或 `optional_no_ca` 下，mTLS 在 HTTPS 上不保护任何内容，因此在 HTTP 上同样不保护。

- `redirect`（默认）：客户端会收到指向同一 URL 的 HTTPS 地址的 `301`。没有可用 `Host` 请求头的请求则会被拒绝。该重定向会保留 `Host` 请求头中的端口，与 SSL 插件的重定向一致：当 HTTP 与 HTTPS 端口不同且不是标准的 80/443 组合时，客户端会被通过 HTTPS 重定向到 HTTP 端口号。此时请使用 `MTLS_HTTP_POLICY=deny`，或在 BunkerWeb 前端做重定向。
- `deny`：请求以拒绝状态码被拒绝（`DENY_HTTP_STATUS`，默认 `403`）。
- `allow`：当 `MTLS_VERIFY_CLIENT` 为 `on` 时，明文 HTTP 像以前一样被提供服务。`MTLS_URL` 路径仍被拒绝。

SSL 插件已经发出的 HTTPS 重定向（`REDIRECT_HTTP_TO_HTTPS`，或其检测到 HTTPS 时的 `AUTO_REDIRECT_HTTP_TO_HTTPS`）优先生效，因此该策略只会看到这种重定向放行的明文 HTTP 请求。ACME HTTP-01 质询仍可访问：当某个 solver 拥有它时，对 `/.well-known/acme-challenge/<token>` 的明文 HTTP `GET` 或 `HEAD` 不会被处理，即存在令牌的本地 Let's Encrypt solver，或将 `LETS_ENCRYPT_PASSTHROUGH` 或 `ACME_PASSTHROUGH` 设为 `yes`。`/.well-known/acme-challenge/` 下的其他任何路径都遵循该策略。在服务上将 `LISTEN_HTTP` 设为 `no` 可完全关闭明文 HTTP 端口。

### 配置设置

| 设置                           | 默认值     | 上下文    | 多个 | 说明                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------ | ---------- | --------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                     | `no`       | multisite | 否   | **启用 mutual TLS：** 为当前站点启用客户端证书认证。                                                                                                                                                                                                                                                                                   |
| `MTLS_CA_CERTIFICATE_PRIORITY` | `file`     | multisite | 否   | **客户端 CA 证书包优先级：** 客户端 CA 证书包的来源：`file`（路径）或 `data`（base64/PEM）。                                                                                                                                                                                                                                           |
| `MTLS_CA_CERTIFICATE`          |            | multisite | 否   | **客户端 CA 证书包路径：** 受信任客户端 CA 证书包（PEM）的路径，需 Scheduler 可读。当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时必填。                                                                                                                                                                                              |
| `MTLS_CA_CERTIFICATE_DATA`     |            | multisite | 否   | **客户端 CA 证书包数据：** 直接以 base64 或 PEM 提供的受信任客户端 CA 证书包（例如通过 Web UI）。                                                                                                                                                                                                                                      |
| `MTLS_VERIFY_CLIENT`           | `on`       | multisite | 否   | **验证模式：** `on` 要求每个 HTTPS 请求都带有效证书。`optional` 请求证书、拒绝无效证书，除非设置了 `MTLS_URL`，否则不再强制其他内容。`optional_no_ca` 请求证书但不对照 CA 验证（仅用于诊断）。参见“各模式保护什么”。                                                                                                                   |
| `MTLS_URL`                     |            | multisite | 是   | **mTLS URL：** 作用于规范化请求 URI 的正则表达式，仅在匹配的路径上要求有效的客户端证书，HTTPS 与明文 HTTP 均适用。需要将 `MTLS_VERIFY_CLIENT` 设置为 `optional`。区分大小写，请锚定到目录。留空表示没有按路径的规则：在 `optional` 或 `optional_no_ca` 下不强制任何内容，要对整个站点要求证书，需将 `MTLS_VERIFY_CLIENT` 设置为 `on`。 |
| `MTLS_HTTP_POLICY`             | `redirect` | multisite | 否   | **HTTP 策略：** 对本应受 mTLS 保护的明文 HTTP 请求如何处理：`redirect` 重定向到 HTTPS，`deny` 拒绝，`allow` 放行（仅限全站模式，`MTLS_URL` 路径仍被拒绝）。                                                                                                                                                                            |
| `MTLS_COUNT_BAD_BEHAVIOR`      | `no`       | multisite | 否   | **在 Bad Behavior 中统计 mTLS 失败：** 让 Bad Behavior 统计客户端证书缺失或无效时 NGINX 返回的 `400`，以及 mTLS 自身发出的拒绝。设为 `no` 时，没有有效证书的客户端不会仅因此被封禁。                                                                                                                                                   |
| `MTLS_VERIFY_DEPTH`            | `2`        | multisite | 否   | **验证深度：** 接受的客户端证书最大链深。                                                                                                                                                                                                                                                                                              |
| `MTLS_FORWARD_CLIENT_HEADERS`  | `yes`      | multisite | 否   | **转发客户端请求头：** 传播验证结果（状态、DN、签发者、序列号、指纹和有效期等 `X-SSL-Client-*` 请求头）。客户端自行发送的 `X-SSL-*` 请求头总是在入口处被剥离，因此这些值无法被伪造。                                                                                                                                                   |
| `MTLS_CRL_PRIORITY`            | `file`     | multisite | 否   | **客户端 CRL 优先级：** CRL 的来源：`file`（路径）或 `data`（base64/PEM）。                                                                                                                                                                                                                                                            |
| `MTLS_CRL`                     |            | multisite | 否   | **客户端 CRL 路径：** 指向 PEM 编码证书吊销列表的可选路径，需 Scheduler 可读。仅在成功加载 CA 证书包时生效。NGINX 要求链中每个签发证书的 CA（包括根 CA）都提供 CRL。过期的 CRL 会导致其 CA 的客户端被拒绝。                                                                                                                            |
| `MTLS_CRL_DATA`                |            | multisite | 否   | **客户端 CRL 数据：** 直接以 base64 或 PEM 提供的吊销列表。                                                                                                                                                                                                                                                                            |

!!! warning "已吊销的证书在其 TLS 会话结束前仍然有效"
    发布 CRL 不会终止已吊销客户端此前保存的 TLS 会话。NGINX 允许该客户端恢复这样的会话而不再检查证书，直到会话过期（`ssl_session_timeout`，默认一天）或 NGINX 重启为止。重新加载不会清除它。吊销证书时请把这一延迟考虑在内，若吊销不能等待，请重启 NGINX。只有新会话才会对照 CRL 检查。

!!! tip "谨慎编写 `MTLS_URL` 规则"
    - 匹配区分大小写：`^/admin` 不匹配 `/Admin`。在模式开头加上 `(?i)` 可忽略大小写。
    - 正则作用于经 NGINX 规范化后的 URI（已解码、点段已解析、重复斜杠已合并），不含查询字符串，因此 `/a/../admin` 和 `//admin` 已被覆盖。
    - 请锚定到目录，而不是文件名。请写 `^/admin(/|$)` 而不是 `^/admin$`，后者不匹配 `/admin/`。锚定到文件名的规则（如 `^/admin/index\.html$`）同样不覆盖 `/admin/`：NGINX 会通过内部重定向从该文件提供它。
    - 路径参数（如 `/admin;x=1`）以及您的后端在 NGINX 之外额外执行的任何规范化（例如 `..;/` 或反斜杠）需要由您自行在正则中覆盖。BunkerWeb 匹配的是 NGINX 看到的 URI。
    - 无效的正则会以关闭方式失败：任何此前没有规则匹配的请求都会被拒绝（`403`），直到您修复它。BunkerWeb 会在启动时以及每次重新加载后记录一条指明服务和模式的错误。

!!! tip "配置一次，处处分发"
    CA 证书包和吊销列表无需挂载到 BunkerWeb 容器中。只需将文件路径或内联数据提供给 Scheduler；Scheduler 会验证、缓存并将其分发到每个实例。更新会在下一次任务运行时自动获取并重新分发。

!!! warning "严格模式需提供 CA 证书包"
    当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时，Scheduler 必须能够验证并缓存客户端 CA 证书包。在证书包通过验证并分发之前，每个实例都会回退到一个没有任何客户端能够构建信任链的占位 CA。在 `on` 模式下，所有客户端都会被拒绝，而此前该服务是在完全不做客户端验证的情况下运行的。在 `optional` 模式下，不提供证书的客户端仍会被放行，这正是该模式的含义；此类请求的强制执行来自 `MTLS_URL`，且仅在其已设置时生效，若留空则没有任何强制执行。而提供了证书的客户端会被拒绝，因为没有任何东西可以用来验证它。`optional_no_ca` 仅建议用于排查问题，因为它会降低认证强度。若 Scheduler 在 `/var/cache/bunkerweb` 非持久化的情况下重启，该状态将一直持续，直到首次任务运行完成并重新分发 CA 证书包；因此在需要严格执行策略的场景下，请使用持久化的缓存卷。

!!! warning "mTLS 先于白名单运行"
    mTLS 在 SSL 插件之后、白名单之前被评估。匹配 `WHITELIST_IP`、`WHITELIST_URI`、`WHITELIST_USER_AGENT`（或 `WHITELIST_RDNS`、`WHITELIST_ASN` 的默认条目）的客户端，在 mTLS 要求证书的地方仍然需要证书。在 1.6.19 之前，白名单会跳过 `MTLS_URL` 检查。若要恢复该优先级，请将 `PLUGINS_ORDER_ACCESS` 设置为 `ssl whitelist mtls`。如果您自行设置了 `PLUGINS_ORDER_ACCESS`（全局或按服务），您的值会被保留：若其中未包含 `mtls`，mTLS 在该处仍会在白名单之后运行。请在该值中将 `mtls` 紧跟在 `ssl` 之后。

!!! info "Bad Behavior 默认不统计证书失败"
    当 `MTLS_COUNT_BAD_BEHAVIOR` 为 `no` 时，Bad Behavior 插件不会统计客户端证书缺失或无效时 NGINX 返回的 `400`，也不会统计 mTLS 自身发出的拒绝（按路径规则、明文 HTTP 策略、无效的 `MTLS_URL` 正则），因此没有有效证书的客户端不会仅因此被封禁。同一服务上的其他 `400` 仍会计入。设为 `yes` 可重新统计。对证书缺失或无效的响应现在是 BunkerWeb 的 `400` 错误页面，前提是 Errors 插件处理 `400`（默认如此，除非 `ERRORS` 为 `400` 设置了自定义页面）；否则仍是 NGINX 的标准页面。

!!! info "Stream 服务"
    在 stream 服务上只有握手层面的检查生效，因此只有将 `MTLS_VERIFY_CLIENT` 设为 `on` 才会强制任何内容。`optional` 和 `optional_no_ca` 会放行没有证书的客户端，而 `MTLS_URL` 和 `MTLS_HTTP_POLICY` 仅适用于 HTTP。

!!! info "`X-SSL-Client-*` 请求头只会到达反向代理和 gRPC 上游"
    BunkerWeb 会把验证结果转发给使用反向代理或 gRPC 插件配置的服务。PHP/FastCGI 和自定义 location 不会收到它们：请在您的配置中自行传递 NGINX 的 `$ssl_client_*` 变量。

!!! info "受信证书与验证"
    BunkerWeb 使用同一份 CA 证书包完成链路校验与信任构建，确保吊销检查和握手验证保持一致。

!!! info "入站 `X-SSL-*` 请求头总是被剥离"
    在请求到达您的应用之前，BunkerWeb 会移除客户端自行发送的每一个 `X-SSL-*` 请求头：适用于所有站点，无论是否启用 mTLS，HTTP/1.1、HTTP/2 与 HTTP/3 一视同仁。只有 BunkerWeb 从已验证的 TLS 握手中导出的值才会被转发，且仅当 `MTLS_FORWARD_CLIENT_HEADERS` 为 `yes` 时才转发，因此客户端无法伪造 `X-SSL-Client-Verify: SUCCESS`。

    如果 BunkerWeb 位于另一个自行终结 mTLS 并注入这些请求头的代理之后，请在剥离之前捕获该值并重新发布。添加一份自定义的 `server-http` 配置：

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    然后通过 `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"` 转发。仅使用 `REVERSE_PROXY_HEADERS` 无效：`proxy_set_header` 求值时 `$http_x_ssl_client_verify` 已经为空，而 `set` 运行在 server-rewrite 阶段，早于剥离。

!!! warning "按路径的 mTLS 需要可选模式"
    NGINX 的 `ssl_verify_client` 指令仅在 `server` 上下文有效，无法置于 `location` 块中。若只想在部分路径上要求证书，请将 `MTLS_VERIFY_CLIENT` 设为 `optional`，使所有路径都能完成握手，然后在 `MTLS_URL_n` 中列出受保护的路径。BunkerWeb 随后会在 Lua 中按请求对匹配的 URL 强制证书。要获得真正的强制效果请使用 `optional`：`optional_no_ca` 会在握手时跳过 CA 检查，而按路径的检查仍需要能通过 CA 证书包验证的证书，因此未配置 CA 证书包时，匹配的路径会拒绝所有客户端。如果在设置 `MTLS_URL_n` 的同时仍将 `MTLS_VERIFY_CLIENT` 保持为 `on`，NGINX 会在握手阶段直接拒绝无证书的客户端，按路径逻辑无从生效，强制仍是全站范围（此时 BunkerWeb 会在启动时记录一条警告）。

!!! info "可选模式下浏览器的证书提示"
    TLS 握手发生在 NGINX 获知请求 URL 之前，因此在 `optional` 模式下，NGINX 仍会在每次连接时发送 `CertificateRequest`。强制变为按路径，但握手层面的请求邀请不会：浏览器在未受保护的路径上仍可能提示选择证书（行为因浏览器而异）。在这些路径上，无论是否提供证书，BunkerWeb 都会放行请求。

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

    允许匿名用户访问，但在客户端提供证书时转发证书详情。这本身不强制任何内容：由您的应用根据转发的请求头决定：

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
    MTLS_URL_1: "^/login(/|$)"
    MTLS_URL_2: "^/admin(/|$)"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | 请求                 | 证书        | 结果                                               |
    | -------------------- | ----------- | -------------------------------------------------- |
    | `GET /`              | 无          | 允许（路径不受 mTLS 约束）                         |
    | `GET /login`         | 无          | 拒绝（`403`）                                      |
    | `GET /login`         | 有效        | 允许，转发 `X-SSL-Client-*`                        |
    | 任意路径             | 无效 / 过期 | 被 NGINX 拒绝（`400`）                             |
    | `GET /login`（HTTP） | 无          | 重定向到 HTTPS（`MTLS_HTTP_POLICY` 为 `redirect`） |
