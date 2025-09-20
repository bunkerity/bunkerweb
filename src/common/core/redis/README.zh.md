Redis 插件将 [Redis](https://redis.io/) 或 [Valkey](https://valkey.io/) 集成到 BunkerWeb 中，用于缓存和快速数据检索。此功能对于在需要跨多个节点访问会话数据、指标和其他共享信息的高可用性环境中部署 BunkerWeb 至关重要。

**工作原理：**

1.  启用后，BunkerWeb 会与您配置的 Redis 或 Valkey 服务器建立连接。
2.  会话信息、指标和安全相关数据等关键数据存储在 Redis/Valkey 中。
3.  多个 BunkerWeb 实例可以共享这些数据，从而实现无缝集群和负载均衡。
4.  该插件支持各种 Redis/Valkey 部署选项，包括独立服务器、密码验证、SSL/TLS 加密和用于高可用性的 Redis Sentinel。
5.  自动重新连接和可配置的超时可确保在生产环境中的稳健性。

### 如何使用

请按照以下步骤配置和使用 Redis 插件：

1.  **启用该功能：** 将 `USE_REDIS` 设置为 `yes` 以启用 Redis/Valkey 集成。
2.  **配置连接详细信息：** 指定您的 Redis/Valkey 服务器的主机名/IP 地址和端口。
3.  **设置安全选项：** 如果您的 Redis/Valkey 服务器需要，请配置身份验证凭据。
4.  **配置高级选项：** 根据需要设置数据库选择、SSL 选项和超时。
5.  **对于高可用性，**如果您正在使用 Redis Sentinel，请配置 Sentinel 设置。

### 配置设置

| 设置                      | 默认值     | 上下文 | 多选 | 描述                                                                             |
| ------------------------- | ---------- | ------ | ---- | -------------------------------------------------------------------------------- |
| `USE_REDIS`               | `no`       | global | 否   | **启用 Redis：** 设置为 `yes` 以启用 Redis/Valkey 集成以用于集群模式。           |
| `REDIS_HOST`              |            | global | 否   | **Redis/Valkey 服务器：** Redis/Valkey 服务器的 IP 地址或主机名。                |
| `REDIS_PORT`              | `6379`     | global | 否   | **Redis/Valkey 端口：** Redis/Valkey 服务器的端口号。                            |
| `REDIS_DATABASE`          | `0`        | global | 否   | **Redis/Valkey 数据库：** 在 Redis/Valkey 服务器上使用的数据库编号 (0-15)。      |
| `REDIS_SSL`               | `no`       | global | 否   | **Redis/Valkey SSL：** 设置为 `yes` 以启用 Redis/Valkey 连接的 SSL/TLS 加密。    |
| `REDIS_SSL_VERIFY`        | `yes`      | global | 否   | **Redis/Valkey SSL 验证：** 设置为 `yes` 以验证 Redis/Valkey 服务器的 SSL 证书。 |
| `REDIS_TIMEOUT`           | `5`        | global | 否   | **Redis/Valkey 超时：** Redis/Valkey 操作的连接超时时间（秒）。                  |
| `REDIS_USERNAME`          |            | global | 否   | **Redis/Valkey 用户名：** 用于 Redis/Valkey 身份验证的用户名 (Redis 6.0+)。      |
| `REDIS_PASSWORD`          |            | global | 否   | **Redis/Valkey 密码：** 用于 Redis/Valkey 身份验证的密码。                       |
| `REDIS_SENTINEL_HOSTS`    |            | global | 否   | **Sentinel 主机：** Redis Sentinel 主机的空格分隔列表 (hostname:port)。          |
| `REDIS_SENTINEL_USERNAME` |            | global | 否   | **Sentinel 用户名：** 用于 Redis Sentinel 身份验证的用户名。                     |
| `REDIS_SENTINEL_PASSWORD` |            | global | 否   | **Sentinel 密码：** 用于 Redis Sentinel 身份验证的密码。                         |
| `REDIS_SENTINEL_MASTER`   | `mymaster` | global | 否   | **Sentinel 主节点：** Redis Sentinel 配置中主节点的名称。                        |
| `REDIS_KEEPALIVE_IDLE`    | `300`      | global | 否   | **Keepalive 空闲时间：** 空闲连接的 TCP keepalive 探测之间的时间（秒）。         |
| `REDIS_KEEPALIVE_POOL`    | `3`        | global | 否   | **Keepalive 池：** 池中保留的最大 Redis/Valkey 连接数。                          |

!!! tip "使用 Redis Sentinel 实现高可用性"
对于需要高可用性的生产环境，请配置 Redis Sentinel 设置。如果主 Redis 服务器不可用，这将提供自动故障转移功能。

!!! warning "安全注意事项"
在生产环境中使用 Redis 时：

    -   始终为 Redis 和 Sentinel 身份验证设置强密码
    -   考虑为 Redis 连接启用 SSL/TLS 加密
    -   确保您的 Redis 服务器未暴露于公共互联网
    -   使用防火墙或网络分段限制对 Redis 端口的访问

!!! info "集群要求"
在集群中部署 BunkerWeb 时：

    -   所有 BunkerWeb 实例都应连接到相同的 Redis 或 Valkey 服务器或 Sentinel 集群
    -   在所有实例中配置相同的数据库编号
    -   确保所有 BunkerWeb 实例与 Redis/Valkey 服务器之间的网络连接

### 配置示例

=== "基本配置"

    一个用于连接到本地计算机上的 Redis 或 Valkey 服务器的简单配置：

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "安全配置"

    启用了密码身份验证和 SSL 的配置：

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Redis Sentinel 配置"

    使用 Redis Sentinel 实现高可用性的配置：

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "高级调优"

    具有用于性能优化的高级连接参数的配置：

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3"
    REDIS_KEEPALIVE_IDLE: "60"
    REDIS_KEEPALIVE_POOL: "5"
    ```

### Redis 最佳实践

在使用 Redis 或 Valkey 与 BunkerWeb 时，请考虑以下最佳实践以确保最佳性能、安全性和可靠性：

#### 内存管理

- **监控内存使用情况：** 使用适当的 `maxmemory` 设置配置 Redis，以防止内存不足错误
- **设置淘汰策略：** 使用适合您用例的 `maxmemory-policy`（例如 `volatile-lru` 或 `allkeys-lru`）
- **避免大键：** 确保将单个 Redis 键保持在合理的大小，以防止性能下降

#### 数据持久性

- **启用 RDB 快照：** 配置定期快照以实现数据持久性，而不会对性能产生重大影响
- **考虑 AOF：** 对于关键数据，启用具有适当 fsync 策略的 AOF（仅追加文件）持久性
- **备份策略：** 将定期 Redis 备份作为灾难恢复计划的一部分

#### 性能优化

- **连接池：** BunkerWeb 已经实现了这一点，但请确保其他应用程序遵循此实践
- **管道：** 如果可能，请使用管道进行批量操作以减少网络开销
- **避免昂贵的操作：** 在生产环境中谨慎使用像 KEYS 这样的命令
- **对您的工作负载进行基准测试：** 使用 redis-benchmark 测试您的特定工作负载模式

### 更多资源

- [Redis 文档](https://redis.io/documentation)
- [Redis 安全指南](https://redis.io/topics/security)
- [Redis 高可用性](https://redis.io/topics/sentinel)
- [Redis 持久性](https://redis.io/topics/persistence)
