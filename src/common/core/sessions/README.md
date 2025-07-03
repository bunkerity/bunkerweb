The Sessions plugin provides robust HTTP session management for BunkerWeb, enabling secure and reliable user session tracking across requests. This core feature is essential for maintaining user state, authentication persistence, and supporting other features that require identity continuity, such as [anti‑bot](#antibot) protection and user authentication systems.

**How it works:**

1. When a user first interacts with your website, BunkerWeb creates a unique session identifier.
2. This identifier is securely stored in a cookie on the user's browser.
3. On subsequent requests, BunkerWeb retrieves the session identifier from the cookie and uses it to access the user's session data.
4. Session data can be stored locally or in [Redis](#redis) for distributed environments with multiple BunkerWeb instances.
5. Sessions are automatically managed with configurable timeouts, ensuring security while maintaining usability.
6. The cryptographic security of sessions is ensured through a secret key that is used to sign session cookies.

### How to Use

Follow these steps to configure and use the Sessions feature:

1. **Configure session security:** Set a strong, unique `SESSIONS_SECRET` to ensure session cookies cannot be forged. (The default value is "random" which triggers BunkerWeb to generate a random secret key.)
2. **Choose a session name:** Optionally customize the `SESSIONS_NAME` to define what your session cookie will be called in the browser. (The default value is "random" which triggers BunkerWeb to generate a random name.)
3. **Set session timeouts:** Configure how long sessions remain valid with the timeout settings (`SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`).
4. **Configure Redis integration:** For distributed environments, set `USE_REDIS` to "yes" and configure your [Redis connection](#redis) to share session data across multiple BunkerWeb nodes.
5. **Let BunkerWeb handle the rest:** Once configured, session management happens automatically for your website.

### Configuration Settings

| Setting                     | Default  | Context | Multiple | Description                                                                                                                |
| --------------------------- | -------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global  | no       | **Session Secret:** Cryptographic key used to sign session cookies. Should be a strong, random string unique to your site. |
| `SESSIONS_NAME`             | `random` | global  | no       | **Cookie Name:** The name of the cookie that will store the session identifier.                                            |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global  | no       | **Idling Timeout:** Maximum time (in seconds) of inactivity before the session is invalidated.                             |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global  | no       | **Rolling Timeout:** Maximum time (in seconds) before a session must be renewed.                                           |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global  | no       | **Absolute Timeout:** Maximum time (in seconds) before a session is destroyed regardless of activity.                      |
| `SESSIONS_CHECK_IP`         | `yes`    | global  | no       | **Check IP:** When set to `yes`, destroys the session if the client IP address changes.                                    |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global  | no       | **Check User-Agent:** When set to `yes`, destroys the session if the client User-Agent changes.                            |

!!! warning "Security Considerations"
    The `SESSIONS_SECRET` setting is critical for security. In production environments:

    1. Use a strong, random value (at least 32 characters)
    2. Keep this value confidential
    3. Use the same value across all BunkerWeb instances in a cluster
    4. Consider using environment variables or secrets management to avoid storing this in plain text

!!! tip "Clustered Environments"
    If you're running multiple BunkerWeb instances behind a load balancer:

    1. Set `USE_REDIS` to `yes` and configure your Redis connection
    2. Ensure all instances use the exact same `SESSIONS_SECRET` and `SESSIONS_NAME`
    3. This ensures users maintain their session regardless of which BunkerWeb instance handles their requests

### Example Configurations

=== "Basic Configuration"

    A simple configuration for a single BunkerWeb instance:

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "myappsession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Enhanced Security"

    Configuration with increased security settings:

    ```yaml
    SESSIONS_SECRET: "your-very-strong-random-secret-key-here"
    SESSIONS_NAME: "securesession"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 minutes
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 minutes
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 hours
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Clustered Environment with Redis"

    Configuration for multiple BunkerWeb instances sharing session data:

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "clustersession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Ensure Redis connection is configured correctly
    ```

=== "Long-lived Sessions"

    Configuration for applications requiring extended session persistence:

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "persistentsession"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 day
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 days
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 days
    ```
