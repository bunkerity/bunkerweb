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
| `MTLS_VERIFY_DEPTH`          | `2`    | multisite | 否   | **验证深度：** 接受的客户端证书最大链深。                                                                                                          |
| `MTLS_FORWARD_CLIENT_HEADERS`| `yes`  | multisite | 否   | **转发客户端请求头：** 传播验证结果（状态、DN、签发者、序列号、指纹和有效期等 `X-SSL-Client-*` 请求头）。                                          |
| `MTLS_CRL`                   |        | multisite | 否   | **客户端 CRL 路径：** 指向 PEM 编码证书吊销列表的可选路径。仅在成功加载 CA 证书包时生效。                                                         |

!!! tip "保持证书最新"
    将 CA 证书包和吊销列表存放在 Scheduler 可读取的挂载卷中，以便重启时自动加载最新的信任锚。

!!! warning "严格模式需提供 CA 证书包"
    当 `MTLS_VERIFY_CLIENT` 为 `on` 或 `optional` 时，运行时必须存在 CA 文件。如果缺失，BunkerWeb 会跳过生成 mTLS 指令，避免服务因路径无效而启动失败。`optional_no_ca` 仅建议用于排查问题，因为它会降低认证强度。

!!! info "受信证书与验证"
    BunkerWeb 使用同一份 CA 证书包完成链路校验与信任构建，确保吊销检查和握手验证保持一致。

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
