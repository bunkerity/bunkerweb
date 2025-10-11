The Metrics plugin provides comprehensive monitoring and data collection capabilities for your BunkerWeb instance. This feature enables you to track various performance indicators, security events, and system statistics, giving you valuable insights into the behavior and health of your protected websites and services.

**How it works:**

1. BunkerWeb collects key metrics during the processing of requests and responses.
2. These metrics include counters for blocked requests, performance measurements, and various security-related statistics.
3. The data is stored efficiently in memory, with configurable limits to prevent excessive resource usage.
4. For multi-instance setups, Redis can be used to centralize and aggregate metrics data.
5. The collected metrics can be accessed through the API or visualized in the [web UI](web-ui.md).
6. This information helps you identify security threats, troubleshoot issues, and optimize your configuration.

### Technical Implementation

The metrics plugin works by:

- Using shared dictionaries in NGINX, where `metrics_datastore` is used for HTTP and `metrics_datastore_stream` for TCP/UDP traffic
- Leveraging an LRU cache for efficient in-memory storage
- Periodically synchronizing data between workers using timers
- Storing detailed information about blocked requests, including the client IP address, country, timestamp, request details, and block reason
- Supporting plugin-specific metrics through a common metrics collection interface
- Providing API endpoints for querying collected metrics

### How to Use

Follow these steps to configure and use the Metrics feature:

1. **Enable the feature:** Metrics collection is enabled by default. You can control this with the `USE_METRICS` setting.
2. **Configure memory allocation:** Set the amount of memory to allocate for metrics storage using the `METRICS_MEMORY_SIZE` setting.
3. **Set storage limits:** Define how many blocked requests to store per worker and in Redis with the respective settings.
4. **Access the data:** View the collected metrics through the [web UI](web-ui.md) or API endpoints.
5. **Analyze the information:** Use the gathered data to identify patterns, detect security issues, and optimize your configuration.

### Collected Metrics

The metrics plugin collects the following information:

1. **Blocked Requests**: For each blocked request, the following data is stored:
      - Request ID and timestamp
      - Client IP address and country (when available)
      - HTTP method and URL
      - HTTP status code
      - User agent
      - Block reason and security mode
      - Server name
      - Additional data related to the block reason

2. **Plugin Counters**: Various plugin-specific counters that track activities and events.

### API Access

Metrics data can be accessed via BunkerWeb's internal API endpoints:

- **Endpoint**: `/metrics/{filter}`
- **Method**: GET
- **Description**: Retrieves metrics data based on the specified filter
- **Response Format**: JSON object containing the requested metrics

For example, `/metrics/requests` returns information about blocked requests.

!!! info "API Access Configuration"
    To access metrics via the API, you must ensure that:

    1. The API feature is enabled with `USE_API: "yes"` (enabled by default)
    2. Your client IP is included in the `API_WHITELIST_IP` setting (default is `127.0.0.0/8`)
    3. You are accessing the API on the configured port (default is `5000` via the `API_HTTP_PORT` setting)
    4. You are using the correct `API_SERVER_NAME` value in the Host header (default is `bwapi`)
    5. If `API_TOKEN` is configured, include `Authorization: Bearer <token>` in the request headers.

    Typical requests:

    Without token (when `API_TOKEN` is not set):
    ```bash
    curl -H "Host: bwapi" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    With token (when `API_TOKEN` is set):
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://your-bunkerweb-instance:5000/metrics/requests
    ```

    If you have customized the `API_SERVER_NAME` to something other than the default `bwapi`, use that value in the Host header instead.

    For secure production environments, restrict API access to trusted IPs and enable `API_TOKEN`.

### Configuration Settings

| Setting                              | Default  | Context   | Multiple | Description                                                                                                          |
| ------------------------------------ | -------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`    | multisite | no       | **Enable Metrics:** Set to `yes` to enable collection and retrieval of metrics.                                      |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | no       | **Memory Size:** Size of the internal storage for metrics (e.g., `16m`, `32m`).                                      |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | no       | **Max Blocked Requests:** Maximum number of blocked requests to store per worker.                                    |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | no       | **Max Redis Blocked Requests:** Maximum number of blocked requests to store in Redis.                                |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | no       | **Save Metrics to Redis:** Set to `yes` to save metrics (counters and tables) to Redis for cluster-wide aggregation. |

!!! tip "Sizing Memory Allocation"
    The `METRICS_MEMORY_SIZE` setting should be adjusted based on your traffic volume and the number of instances. For high-traffic sites, consider increasing this value to ensure all metrics are captured without data loss.

!!! info "Redis Integration"
    When BunkerWeb is configured to use [Redis](#redis), the metrics plugin will automatically synchronize blocked request data to the Redis server. This provides a centralized view of security events across multiple BunkerWeb instances.

!!! warning "Performance Considerations"
    Setting very high values for `METRICS_MAX_BLOCKED_REQUESTS` or `METRICS_MAX_BLOCKED_REQUESTS_REDIS` can increase memory usage. Monitor your system resources and adjust these values according to your actual needs and available resources.

!!! note "Worker-Specific Storage"
    Each NGINX worker maintains its own metrics in memory. When accessing metrics through the API, data from all workers is automatically aggregated to provide a complete view.

### Example Configurations

=== "Basic Configuration"

    Default configuration suitable for most deployments:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Low-Resource Environment"

    Configuration optimized for environments with limited resources:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "High-Traffic Environment"

    Configuration for high-traffic websites that need to track more security events:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Metrics Disabled"

    Configuration with metrics collection disabled:

    ```yaml
    USE_METRICS: "no"
    ```
