指标插件为您的 BunkerWeb 实例提供全面的监控和数据收集功能。此功能使您能够跟踪各种性能指标、安全事件和系统统计信息，从而为您提供有关受保护网站和服务行为及健康状况的宝贵见解。

**工作原理：**

1.  BunkerWeb 在处理请求和响应期间收集关键指标。
2.  这些指标包括被阻止请求的计数器、性能测量以及各种与安全相关的统计信息。
3.  数据高效地存储在内存中，并具有可配置的限制以防止过多的资源使用。
4.  对于多实例设置，可以使用 Redis 来集中和聚合指标数据。
5.  收集到的指标可以通过 API 访问或在[Web UI](web-ui.md)中可视化。
6.  此信息可帮助您识别安全威胁、解决问题并优化您的配置。

### 技术实现

指标插件的工作方式如下：

- 在 NGINX 中使用共享字典，其中 `metrics_datastore` 用于 HTTP，`metrics_datastore_stream` 用于 TCP/UDP 流量
- 利用 LRU 缓存进行高效的内存存储
- 使用计时器在工作进程之间定期同步数据
- 存储有关被阻止请求的详细信息，包括客户端 IP 地址、国家/地区、时间戳、请求详情和阻止原因
- 通过通用的指标收集接口支持插件特定的指标
- 提供用于查询收集到的指标的 API 端点

### 如何使用

请按照以下步骤配置和使用指标功能：

1.  **启用该功能：** 指标收集默认启用。您可以使用 `USE_METRICS` 设置来控制此功能。
2.  **配置内存分配：** 使用 `METRICS_MEMORY_SIZE` 设置来设置用于指标存储的内存量。
3.  **设置存储限制：** 使用相应的设置定义每个工作进程和 Redis 中要存储的被阻止请求的数量。
4.  **访问数据：** 通过[Web UI](web-ui.md)或 API 端点查看收集到的指标。
5.  **分析信息：** 使用收集到的数据来识别模式、检测安全问题并优化您的配置。

### 收集的指标

指标插件收集以下信息：

1.  **被阻止的请求**：对于每个被阻止的请求，将存储以下数据：
    - 请求 ID 和时间戳
    - 客户端 IP 地址和国家/地区（如果可用）
    - HTTP 方法和 URL
    - HTTP 状态码
    - 用户代理
    - 阻止原因和安全模式
    - 服务器名称
    - 与阻止原因相关的其他数据

2.  **插件计数器**：跟踪活动和事件的各种插件特定计数器。

### API 访问

指标数据可以通过 BunkerWeb 的内部 API 端点访问：

- **端点**：`/metrics/{filter}`
- **方法**：GET
- **描述**：根据指定的过滤器检索指标数据
- **响应格式**：包含所请求指标的 JSON 对象

例如，`/metrics/requests` 返回有关被阻止请求的信息。

!!! info "API 访问配置"
要通过 API 访问指标，您必须确保：

    1.  API 功能已通过 `USE_API: "yes"` 启用（默认启用）
    2.  您的客户端 IP 包含在 `API_WHITELIST_IP` 设置中（默认为 `127.0.0.0/8`）
    3.  您正在通过配置的端口访问 API（默认为 `5000`，通过 `API_HTTP_PORT` 设置）
    4.  您在 Host 标头中使用了正确的 `API_SERVER_NAME` 值（默认为 `bwapi`）
    5.  如果配置了 `API_TOKEN`，请在请求标头中包含 `Authorization: Bearer <token>`。

    典型请求：

    不带令牌（当未设置 `API_TOKEN` 时）：
    ```bash
    curl -H "Host: bwapi" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    带令牌（当设置了 `API_TOKEN` 时）：
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    如果您已将 `API_SERVER_NAME` 自定义为默认 `bwapi` 以外的值，请在 Host 标头中使用该值。

    对于安全的生产环境，请将 API 访问限制为受信任的 IP，并启用 `API_TOKEN`。

### 配置设置

| 设置                                 | 默认值   | 上下文    | 多选 | 描述                                                                                             |
| ------------------------------------ | -------- | --------- | ---- | ------------------------------------------------------------------------------------------------ |
| `USE_METRICS`                        | `yes`    | multisite | 否   | **启用指标：** 设置为 `yes` 以启用指标的收集和检索。                                             |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | 否   | **内存大小：** 指标内部存储的大小（例如，`16m`、`32m`）。                                        |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | 否   | **最大被阻止请求数：** 每个工作进程要存储的最大被阻止请求数。                                    |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | 否   | **Redis 最大被阻止请求数：** 在 Redis 中要存储的最大被阻止请求数。                               |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | 否   | **将指标保存到 Redis：** 设置为 `yes` 以将指标（计数器和表）保存到 Redis，以实现集群范围的聚合。 |

!!! tip "调整内存分配大小"
应根据您的流量和实例数量调整 `METRICS_MEMORY_SIZE` 设置。对于高流量网站，请考虑增加此值以确保所有指标都能被捕获而不会丢失数据。

!!! info "Redis 集成"
当 BunkerWeb 配置为使用[Redis](#redis)时，指标插件将自动将被阻止的请求数据同步到 Redis 服务器。这提供了跨多个 BunkerWeb 实例的安全事件的集中视图。

!!! warning "性能注意事项"
为 `METRICS_MAX_BLOCKED_REQUESTS` 或 `METRICS_MAX_BLOCKED_REQUESTS_REDIS` 设置非常高的值会增加内存使用量。请监控您的系统资源，并根据您的实际需求和可用资源调整这些值。

!!! note "工作进程特定存储"
每个 NGINX 工作进程都在内存中维护自己的指标。通过 API 访问指标时，会自动聚合所有工作进程的数据以提供完整的视图。

### 配置示例

=== "基本配置"

    适用于大多数部署的默认配置：

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "低资源环境"

    为资源有限的环境优化的配置：

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "高流量环境"

    需要跟踪更多安全事件的高流量网站的配置：

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "禁用指标"

    禁用指标收集的配置：

    ```yaml
    USE_METRICS: "no"
    ```
