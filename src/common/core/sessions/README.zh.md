会话插件为 BunkerWeb 提供了强大的 HTTP 会话管理功能，可在请求之间实现安全可靠的用户会话跟踪。此核心功能对于维护用户状态、身份验证持久性以及支持需要身份连续性的其他功能（例如[反机器人](#antibot)保护和用户身份验证系统）至关重要。

**工作原理：**

1. 当用户首次与您的网站互动时，BunkerWeb 会创建一个唯一的会话标识符。
2. 此标识符安全地存储在用户浏览器的 Cookie 中。
3. 在后续请求中，BunkerWeb 从 Cookie 中检索会话标识符，并使用它来访问用户的会话数据。
4. 对于具有多个 BunkerWeb 实例的分布式环境，会话数据可以本地存储或存储在 [Redis](#redis) 中。
5. 会话通过可配置的超时进行自动管理，在保持可用性的同时确保安全性。
6. 会话的加密安全性通过用于签署会话 Cookie 的密钥来保证。

### 如何使用

请按照以下步骤配置和使用会话功能：

1. **配置会话安全性：** 设置一个强大的、唯一的 `SESSIONS_SECRET`，以确保会话 Cookie 无法被伪造。（默认值为“random”，这会触发 BunkerWeb 生成一个随机的密钥。）
2. **选择会话名称：** 可选地自定义 `SESSIONS_NAME`，以定义您的会话 Cookie 在浏览器中的名称。（默认值为“random”，这会触发 BunkerWeb 生成一个随机的名称。）
3. **设置会话超时：** 使用超时设置（`SESSIONS_IDLING_TIMEOUT`、`SESSIONS_ROLLING_TIMEOUT`、`SESSIONS_ABSOLUTE_TIMEOUT`）配置会话的有效时长。
4. **在子域之间共享 Cookie（可选，按服务器配置）：** 默认情况下，会话 Cookie 仅作用于主机本身。如果某个服务器托管了同一可注册域名下的多个子域（例如 `a.example.com` 和 `b.example.com`），并且您希望反机器人/挑战状态能够共用，请仅在该服务器上将 `SESSIONS_DOMAIN` 设置为父域名（`example.com`）。`SESSIONS_DOMAIN` 是一项 multisite 设置，因此同一 BunkerWeb 实例上的无关租户不会收到跨租户共享的 `Domain` 属性。
5. **配置 Redis 集成：** 对于分布式环境，将 `USE_REDIS` 设置为“yes”，并配置您的 [Redis 连接](#redis) 以在多个 BunkerWeb 节点之间共享会话数据。
6. **让 BunkerWeb 处理其余部分：** 配置完成后，您的网站会自动进行会话管理。

### 配置设置

| 设置                        | 默认值   | 上下文    | 多选 | 描述                                                                                                                                                                                                                  |
| --------------------------- | -------- | --------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global    | 否   | **会话密钥：** 用于签署会话 Cookie 的加密密钥。应该是一个强大的、随机的、对您的站点唯一的字符串。                                                                                                                   |
| `SESSIONS_NAME`             | `random` | global    | 否   | **Cookie 名称：** 将存储会话标识符的 Cookie 的名称。                                                                                                                                                                  |
| `SESSIONS_DOMAIN`           |          | multisite | 否   | **Cookie 域：** 应用于会话 Cookie 的可选 `Domain` 属性（例如 `example.com`）。留空则保持 Cookie 仅作用于主机。按服务器配置它，以便在同一可注册域名下的同级子域之间共享会话状态（反机器人、挑战等）。             |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global    | 否   | **空闲超时：** 会话在失效前允许保持不活动的最长时间（以秒为单位）。                                                                                                                                                   |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global    | 否   | **滚动超时：** 会话在必须续订之前允许存在的最长时间（以秒为单位）。                                                                                                                                                   |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global    | 否   | **绝对超时：** 无论活动情况如何，会话在被销毁前允许存在的最长时间（以秒为单位）。                                                                                                                                     |
| `SESSIONS_CHECK_IP`         | `yes`    | global    | 否   | **检查 IP：** 设置为 `yes` 时，如果客户端 IP 地址发生变化，则销毁会话。                                                                                                                                               |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global    | 否   | **检查 User-Agent：** 设置为 `yes` 时，如果客户端 User-Agent 发生变化，则销毁会话。                                                                                                                                   |

!!! warning "安全注意事项"
    `SESSIONS_SECRET` 设置对安全至关重要。在生产环境中：

    1. 使用一个强大的、随机的值（至少 32 个字符）
    2. 对此值保密
    3. 在集群中的所有 BunkerWeb 实例中使用相同的值
    4. 考虑使用环境变量或密钥管理，以避免以纯文本形式存储此值

!!! tip "集群环境"
    如果您在负载均衡器后面运行多个 BunkerWeb 实例：

    1. 将 `USE_REDIS` 设置为 `yes` 并配置您的 Redis 连接
    2. 确保所有实例使用完全相同的 `SESSIONS_SECRET` 和 `SESSIONS_NAME`
    3. 这确保了无论哪个 BunkerWeb 实例处理用户的请求，他们都能保持其会话

### 配置示例

=== "基本配置"

    单个 BunkerWeb 实例的简单配置：

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "myappsession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "增强安全性"

    具有更高安全设置的配置：

    ```yaml
    SESSIONS_SECRET: "your-very-strong-random-secret-key-here"
    SESSIONS_NAME: "securesession"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 分钟
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 分钟
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 小时
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "带 Redis 的集群环境"

    用于多个 BunkerWeb 实例共享会话数据的配置：

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "clustersession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # 确保 Redis 连接配置正确
    ```

=== "长效会话"

    用于需要延长会话持久性的应用程序的配置：

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "persistentsession"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 天
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 天
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 天
    ```

=== "跨子域会话（单一租户）"

    在 `example.com` 的所有子域之间共享会话 Cookie，这样整个站点的反机器人/挑战状态只需解决一次：

    ```yaml
    SERVER_NAME: "app.example.com api.example.com shop.example.com"
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "crossdomainsession"
    # SESSIONS_DOMAIN 是一项 multisite 设置：使用服务器名作为前缀，使其仅应用于匹配的主机
    app.example.com_SESSIONS_DOMAIN: "example.com"
    api.example.com_SESSIONS_DOMAIN: "example.com"
    shop.example.com_SESSIONS_DOMAIN: "example.com"
    USE_ANTIBOT: "turnstile"
    ```

=== "跨子域会话（混合租户）"

    当同一个 BunkerWeb 实例托管多个彼此无关的可注册域名时，只应在需要共享 Cookie 的服务器上设置 `SESSIONS_DOMAIN`。未设置的服务器将保留默认的仅主机 Cookie，从而确保租户隔离：

    ```yaml
    SERVER_NAME: "app.example.com api.example.com billing.acme.org www.unrelated.io"
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "tenantsession"
    # 仅在 example.com 子域之间共享 Cookie
    app.example.com_SESSIONS_DOMAIN: "example.com"
    api.example.com_SESSIONS_DOMAIN: "example.com"
    # billing.acme.org 和 www.unrelated.io 有意保持为仅主机 Cookie
    USE_ANTIBOT: "turnstile"
    ```

    !!! note
        `SESSIONS_DOMAIN` 必须始终是其所应用服务器的父域名。例如，`example.com` 对 `example.com` 本身以及任意 `*.example.com` 主机都有效，而前导点（`.example.com`）也会因兼容旧配置而被接受。如果将其设置为无关的可注册域名，浏览器将拒绝该 Cookie。
