The Metrics plugin provides comprehensive monitoring and data collection capabilities for your BunkerWeb instance. This feature enables you to track various performance indicators, security events, and system statistics, giving you valuable insights into the behavior and health of your protected websites and services.

**Here's how the Metrics feature works:**

1. BunkerWeb collects key metrics during the processing of requests and responses.
2. These metrics include counters for blocked requests, performance measurements, and various security-related statistics.
3. The data is stored efficiently in memory, with configurable limits to prevent excessive resource usage.
4. For multi-instance setups, Redis can be used to centralize and aggregate metrics data.
5. The collected metrics can be accessed through the API or visualized in the [web UI](web-ui.md).
6. This information helps you identify security threats, troubleshoot issues, and optimize your configuration.

### How to Use

Follow these steps to configure and use the Metrics feature:

1. **Enable the feature:** Metrics collection is enabled by default. You can control this with the `USE_METRICS` setting.
2. **Configure memory allocation:** Set the amount of memory to allocate for metrics storage using the `METRICS_MEMORY_SIZE` setting.
3. **Set storage limits:** Define how many blocked requests to store per worker and in Redis with the respective settings.
4. **Access the data:** View the collected metrics through the [web UI](web-ui.md) or API endpoints.
5. **Analyze the information:** Use the gathered data to identify patterns, detect security issues, and optimize your configuration.

### Configuration Settings

| Setting                              | Default  | Context   | Multiple | Description                                                                           |
| ------------------------------------ | -------- | --------- | -------- | ------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`    | multisite | no       | **Enable Metrics:** Set to `yes` to enable collection and retrieval of metrics.       |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | no       | **Memory Size:** Size of the internal storage for metrics (e.g., `16m`, `32m`).       |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | no       | **Max Blocked Requests:** Maximum number of blocked requests to store per worker.     |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | no       | **Max Redis Blocked Requests:** Maximum number of blocked requests to store in Redis. |

!!! tip "Sizing Memory Allocation"
    The `METRICS_MEMORY_SIZE` setting should be adjusted based on your traffic volume and the number of instances. For high-traffic sites, consider increasing this value to ensure all metrics are captured without data loss.

!!! info "Redis Integration"
    When BunkerWeb is configured to use [Redis](#redis), the metrics plugin will automatically synchronize blocked request data to the Redis server. This provides a centralized view of security events across multiple BunkerWeb instances.

!!! warning "Performance Considerations"
    Setting very high values for `METRICS_MAX_BLOCKED_REQUESTS` or `METRICS_MAX_BLOCKED_REQUESTS_REDIS` can increase memory usage. Monitor your system resources and adjust these values according to your actual needs and available resources.

### Example Configurations

=== "Basic Configuration"

    Default configuration suitable for most deployments:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    ```

=== "Low-Resource Environment"

    Configuration optimized for environments with limited resources:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    ```

=== "High-Traffic Environment"

    Configuration for high-traffic websites that need to track more security events:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    ```

=== "Metrics Disabled"

    Configuration with metrics collection disabled:

    ```yaml
    USE_METRICS: "no"
    ```
