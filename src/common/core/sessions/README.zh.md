会话插件为 BunkerWeb 提供了强大的 HTTP 会话管理功能，可在请求之间实现安全可靠的用户会话跟踪。此核心功能对于维护用户状态、身份验证持久性以及支持需要身份连续性的其他功能（例如[反机器人](#antibot)保护和用户身份验证系统）至关重要。

**工作原理：**

1.  当用户首次与您的网站互动时，BunkerWeb 会创建一个唯一的会话标识符。
2.  此标识符安全地存储在用户浏览器的 Cookie 中。
3.  在后续请求中，BunkerWeb 从 Cookie 中检索会话标识符，并使用它来访问用户的会话数据。
4.  对于具有多个 BunkerWeb 实例的分布式环境，会话数据可以本地存储或存储在 [Redis](#redis) 中。
5.  会话通过可配置的超时进行自动管理，在保持可用性的同时确保安全性。
6.  会话的加密安全性通过用于签署会话 Cookie 的密钥来保证。

### 如何使用

请按照以下步骤配置和使用会话功能：

1.  **配置会话安全性：** 设置一个强大的、唯一的 `SESSIONS_SECRET`，以确保会话 Cookie 无法被伪造。（默认值为“random”，这会触发 BunkerWeb 生成一个随机的密钥。）
2.  **选择会话名称：** 可选地自定义 `SESSIONS_NAME`，以定义您的会话 Cookie 在浏览器中的名称。（默认值为“random”，这会触发 BunkerWeb 生成一个随机的名称。）
3.  **设置会话超时：** 使用超时设置（`SESSIONS_IDLING_TIMEOUT`、`SESSIONS_ROLLING_TIMEOUT`、`SESSIONS_ABSOLUTE_TIMEOUT`）配置会话的有效时长。
4.  **配置 Redis 集成：** 对于分布式环境，将 `USE_REDIS` 设置为“yes”，并配置您的 [Redis 连接](#redis) 以在多个 BunkerWeb 节点之间共享会话数据。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，您的网站会自动进行会话管理。

### 配置设置

| 设置                        | 默认值   | 上下文 | 多选 | 描述                                                                                              |
| --------------------------- | -------- | ------ | ---- | ------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global | 否   | **会话密钥：** 用于签署会话 Cookie 的加密密钥。应该是一个强大的、随机的、对您的站点唯一的字符串。 |
| `SESSIONS_NAME`             | `random` | global | 否   | **Cookie 名称：** 将存储会话标识符的 Cookie 的名称。                                              |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global | 否   | **空闲超时：** 会话在失效前不活动的最长时间（以秒为单位）。                                       |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global | 否   | **滚动超时：** 会话必须续订前的最长时间（以秒为单位）。                                           |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global | 否   | **绝对超时：** 无论活动如何，会话被销毁前的最长时间（以秒为单位）。                               |
| `SESSIONS_CHECK_IP`         | `yes`    | global | 否   | **检查 IP：** 设置为 `yes` 时，如果客户端 IP 地址发生变化，则销毁会话。                           |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global | 否   | **检查 User-Agent：** 设置为 `yes` 时，如果客户端 User-Agent 发生变化，则销毁会话。               |

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
