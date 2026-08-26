The Redis plugin integrates [Redis](https://redis.io/) or [Valkey](https://valkey.io/) into BunkerWeb for caching and fast data retrieval. This feature is essential for deploying BunkerWeb in high-availability environments where session data, metrics, and other shared information must be accessible across multiple nodes.

**How it works:**

1. When enabled, BunkerWeb establishes a connection to your configured Redis or Valkey server.
2. Critical data such as session information, metrics, and security-related data are stored in Redis/Valkey.
3. Multiple BunkerWeb instances can share this data, enabling seamless clustering and load balancing.
4. The plugin supports various Redis/Valkey deployment options, including standalone servers, password authentication, SSL/TLS encryption, and Redis Sentinel for high availability.
5. Automatic reconnection and configurable timeouts ensure robustness in production environments.

### How to Use

Follow these steps to configure and use the Redis plugin:

1. **Enable the feature:** Set the `USE_REDIS` setting to `yes` to enable Redis/Valkey integration.
2. **Configure connection details:** Specify your Redis/Valkey server's hostname/IP address and port.
3. **Set security options:** Configure authentication credentials if your Redis/Valkey server requires them.
4. **Configure advanced options:** Set the database selection, SSL options, and timeouts as needed.
5. **For high availability,** configure Sentinel settings if you're using Redis Sentinel.

### Configuration Settings

| Setting                   | Default    | Context | Multiple | Description                                                                                      |
| ------------------------- | ---------- | ------- | -------- | ------------------------------------------------------------------------------------------------ |
| `USE_REDIS`               | `no`       | global  | no       | **Enable Redis:** Set to `yes` to enable Redis/Valkey integration for cluster mode.              |
| `REDIS_HOST`              |            | global  | no       | **Redis/Valkey Server:** IP address or hostname of the Redis/Valkey server. Not required when `REDIS_SENTINEL_HOSTS` is set (the master is resolved through the Sentinels). |
| `REDIS_PORT`              | `6379`     | global  | no       | **Redis/Valkey Port:** Port number of the Redis/Valkey server.                                   |
| `REDIS_DATABASE`          | `0`        | global  | no       | **Redis/Valkey Database:** Database number to use on the Redis/Valkey server (0-15).             |
| `REDIS_SSL`               | `no`       | global  | no       | **Redis/Valkey SSL:** Set to `yes` to enable SSL/TLS encryption for the Redis/Valkey connection. |
| `REDIS_SSL_VERIFY`        | `yes`      | global  | no       | **Redis/Valkey SSL Verify:** Set to `yes` to verify the Redis/Valkey server's SSL certificate.   |
| `REDIS_SSL_CA`            |            | global  | no       | **Redis/Valkey SSL CA bundle:** Path to a PEM CA bundle used to verify the server certificate (private CA). Trusted by the Python clients and, via the generated trust bundle, by the request path — see the note below. |
| `REDIS_TIMEOUT`           | `1000`     | global  | no       | **Redis/Valkey Timeout:** Connect/read/write timeout in milliseconds for Redis/Valkey operations. |
| `REDIS_USERNAME`          |            | global  | no       | **Redis/Valkey Username:** Username for Redis/Valkey authentication (Redis 6.0+).                |
| `REDIS_PASSWORD`          |            | global  | no       | **Redis/Valkey Password:** Password for Redis/Valkey authentication.                             |
| `REDIS_SENTINEL_HOSTS`    |            | global  | no       | **Sentinel Hosts:** Space-separated list of Redis Sentinel hosts (hostname:port).                |
| `REDIS_SENTINEL_USERNAME` |            | global  | no       | **Sentinel Username:** Username for Redis Sentinel authentication.                               |
| `REDIS_SENTINEL_PASSWORD` |            | global  | no       | **Sentinel Password:** Password for Redis Sentinel authentication.                               |
| `REDIS_SENTINEL_MASTER`   | `mymaster` | global  | no       | **Sentinel Master:** Name of the master in Redis Sentinel configuration.                         |
| `REDIS_KEEPALIVE_IDLE`    | `30000`    | global  | no       | **Keepalive Idle:** Maximum idle time (in milliseconds) before closing a pooled Redis/Valkey connection. |
| `REDIS_KEEPALIVE_POOL`    | `10`       | global  | no       | **Keepalive Pool:** Maximum number of Redis/Valkey connections kept in the pool.                 |

!!! info "Private CA: how `REDIS_SSL_CA` is trusted"
    With `REDIS_SSL_VERIFY: "yes"` (the default), verification uses the system/certifi trust store, which never contains a private CA — a perfectly valid certificate still fails `CERTIFICATE_VERIFY_FAILED`, and the only escape used to be turning verification off for every consumer at once. `REDIS_SSL_CA` names a PEM CA bundle to trust instead. It reaches both halves of the product, by two different routes:

    - **Python clients — the path is passed to the client.** The Celery broker URL (worker and API), the jobs (`push-configs`, `sync-bans`), the API rate limiter, `bwcli` and the web UI. The broker URL and the API rate limiter carry the CA only while verification is on: with `REDIS_SSL_VERIFY: "no"` nothing is verified, so no CA is sent.
    - **The NGINX Lua request path (`clusterstore.lua`, used when `USE_REDIS: "yes"`) — the CA is appended to the trust bundle.** An OpenResty cosocket has no per-connection trust store; it verifies against the single global `lua_ssl_trusted_certificate` file. So the config generator appends your CA onto the shipped root bundle and points that directive at the result, which travels to every instance with the configuration. Appended, never replaced: antibot, BunkerNet and CrowdSec verify their own HTTPS against the same store and keep trusting everything they trusted before.

    **Where the file must exist.** It is read where the configuration is generated (the worker) and by each Python client in its own filesystem, so mount it at the same path in the scheduler, worker, API and UI. BunkerWeb instances need nothing mounted — they receive the combined bundle. A `REDIS_SSL_CA` that is missing, unreadable or not a valid PEM bundle **fails configuration generation** on purpose: `lua_ssl_trusted_certificate` pointing at a bad file makes NGINX refuse to start, so nothing is pushed and the fleet keeps serving the configuration it already has.

    An explicit `CELERY_BROKER_URL` still wins over the derived one: put `ssl_cert_reqs=required&ssl_ca_certs=/path/to/ca.pem` in it yourself if you set it by hand.

!!! tip "High Availability with Redis Sentinel"
    For production environments requiring high availability, configure Redis Sentinel settings. This provides automatic failover capabilities if the primary Redis server becomes unavailable.

!!! warning "Security Considerations"
    When using Redis in production:

    - Always set strong passwords for both Redis and Sentinel authentication
    - Consider enabling SSL/TLS encryption for Redis connections
    - Ensure your Redis server is not exposed to the public internet
    - Restrict access to the Redis port using firewalls or network segmentation

!!! info "Cluster Requirements"
    When deploying BunkerWeb in a cluster:

    - All BunkerWeb instances should connect to the same Redis or Valkey server or Sentinel cluster
    - Configure the same database number across all instances
    - Ensure network connectivity between all BunkerWeb instances and Redis/Valkey servers

### Example Configurations

=== "Basic Configuration"

    A simple configuration for connecting to a Redis or Valkey server on the local machine:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Secure Configuration"

    Configuration with password authentication and SSL enabled:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    # Only for a certificate signed by a private CA; omit it for a publicly trusted one
    REDIS_SSL_CA: "/etc/bunkerweb/redis-ca.pem"
    ```

=== "Redis Sentinel Configuration"

    Configuration for high availability using Redis Sentinel:

    ```yaml
    USE_REDIS: "yes"
    # REDIS_HOST is not needed: the master is resolved through the Sentinels
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Advanced Tuning"

    Configuration with advanced connection parameters for performance optimization:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3000"
    REDIS_KEEPALIVE_IDLE: "60000"
    REDIS_KEEPALIVE_POOL: "5"
    ```

!!! info "Redis on Kubernetes (scheduler-driven config)"
    On Kubernetes the **scheduler** reads the settings and pushes the generated configuration to the
    BunkerWeb instances — the instances do not read these Redis settings from their own pod
    environment. With the official Helm chart, configure Redis under `settings.redis`, including
    Sentinel via `settings.redis.redisSentinelHosts` and `settings.redis.redisSentinelMaster`
    (chart ≥ v1.0.21). For any setting without a dedicated chart key, use `scheduler.extraEnvs`.
    Setting these only on `bunkerweb.extraEnvs` has **no effect**.

### Redis Best Practices

When using Redis or Valkey with BunkerWeb, consider these best practices to ensure optimal performance, security, and reliability:

#### Memory Management
- **Monitor memory usage:** Configure Redis with appropriate `maxmemory` settings to prevent out-of-memory errors
- **Set an eviction policy:** Use `maxmemory-policy` (e.g., `volatile-lru` for general use or `allkeys-lru` for cache-heavy workloads) appropriate for your use case
- **All-in-one defaults:** The AIO Docker image ships Redis with `maxmemory=256mb` and `maxmemory-policy=volatile-lru`; override via the `REDIS_MAXMEMORY` and `REDIS_MAXMEMORY_POLICY` environment variables. With `volatile-lru`, transient counters (rate-limit, bad-behavior) are evicted before keys with TTLs that matter for sessions and timed bans, and keys without an expiry (permanent bans) are immune. The same policy is recommended for external Redis or Valkey servers used by BunkerWeb.
- **Avoid large keys:** Ensure individual Redis keys are kept to a reasonable size to prevent performance degradation

#### Data Persistence
- **Enable RDB snapshots:** Configure periodic snapshots for data persistence without significant performance impact
- **Consider AOF:** For critical data, enable AOF (Append-Only File) persistence with an appropriate fsync policy
- **Backup strategy:** Implement regular Redis backups as part of your disaster recovery plan

#### Performance Optimization
- **Connection pooling:** BunkerWeb already implements this, but ensure other applications follow this practice
- **Pipelining:** When possible, use pipelining for bulk operations to reduce network overhead
- **Avoid expensive operations:** Be cautious with commands like KEYS in production environments
- **Benchmark your workload:** Use redis-benchmark to test your specific workload patterns

### Further Resources

- [Redis Documentation](https://redis.io/documentation)
- [Redis Security Guide](https://redis.io/topics/security)
- [Redis High Availability](https://redis.io/topics/sentinel)
- [Redis Persistence](https://redis.io/topics/persistence)
