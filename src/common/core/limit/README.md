The Limit plugin in BunkerWeb provides robust capabilities to enforce limiting policies on your website, ensuring fair usage and protecting your resources from abuse, denial-of-service attacks, and excessive resource consumption. These policies include:

- **Number of connections per IP address** (STREAM support :white_check_mark:)
- **Number of requests per IP address and URL within a specific time period** (STREAM support :x:)

### How it Works

1. **Rate Limiting:** Tracks the number of requests from each client IP address to specific URLs. If a client exceeds the configured rate limit, subsequent requests are temporarily denied.
2. **Connection Limiting:** Monitors and restricts the number of concurrent connections from each client IP address. Different connection limits can be applied based on the protocol used (HTTP/1, HTTP/2, HTTP/3, or stream).
3. In both cases, clients that exceed the defined limits receive an HTTP status code **"429 - Too Many Requests"**, which helps prevent server overload.

### Steps to Use

1. **Enable Request Rate Limiting:** Use `USE_LIMIT_REQ` to enable request rate limiting and define URL patterns along with their corresponding rate limits.
2. **Enable Connection Limiting:** Use `USE_LIMIT_CONN` to enable connection limiting and set the maximum number of concurrent connections for different protocols.
3. **Apply Granular Control:** Create multiple rate limit rules for different URLs to provide varying levels of protection across your site.
4. **Monitor Effectiveness:** Use the [web UI](web-ui.md) to view statistics on limited requests and connections.

### Configuration Settings

=== "Request Rate Limiting"

    | Setting          | Default | Context   | Multiple | Description                                                                                                                                                        |
    | ---------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `USE_LIMIT_REQ`  | `yes`   | multisite | no       | **Enable Request Limiting:** Set to `yes` to enable the request rate limiting feature.                                                                             |
    | `LIMIT_REQ_URL`  | `/`     | multisite | yes      | **URL Pattern:** URL pattern (PCRE regex) to which the rate limit will be applied; use `/` to apply for all requests.                                              |
    | `LIMIT_REQ_RATE` | `2r/s`  | multisite | yes      | **Rate Limit:** Maximum request rate in the format `Nr/t`, where N is the number of requests and t is the time unit: s (second), m (minute), h (hour), or d (day). |

    !!! tip "Rate Limiting Format"
        The rate limit format is specified as `Nr/t` where:

        - `N` is the number of requests allowed
        - `r` is a literal 'r' (for 'requests')
        - `/` is a literal slash
        - `t` is the time unit: `s` (second), `m` (minute), `h` (hour), or `d` (day)

        For example, `5r/m` means that 5 requests per minute are allowed from each IP address.

=== "Connection Limiting"

    | Setting                 | Default | Context   | Multiple | Description                                                                                 |
    | ----------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_CONN`        | `yes`   | multisite | no       | **Enable Connection Limiting:** Set to `yes` to enable the connection limiting feature.     |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`    | multisite | no       | **HTTP/1.X Connections:** Maximum number of concurrent HTTP/1.X connections per IP address. |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`   | multisite | no       | **HTTP/2 Streams:** Maximum number of concurrent HTTP/2 streams per IP address.             |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`   | multisite | no       | **HTTP/3 Streams:** Maximum number of concurrent HTTP/3 streams per IP address.             |
    | `LIMIT_CONN_MAX_STREAM` | `10`    | multisite | no       | **Stream Connections:** Maximum number of concurrent stream connections per IP address.     |

!!! info "Connection vs. Request Limiting"
    - **Connection limiting** restricts the number of simultaneous connections that a single IP address can maintain.
    - **Request rate limiting** restricts the number of requests an IP address can make within a defined period of time.

    Using both methods provides comprehensive protection against various types of abuse.

!!! warning "Setting Appropriate Limits"
    Setting limits too restrictively may impact legitimate users, especially for HTTP/2 and HTTP/3 where browsers often use multiple streams. The default values are balanced for most use cases, but consider adjusting them based on your application's needs and user behavior.

### Example Configurations

=== "Basic Protection"

    A simple configuration using default settings to protect your entire site:

    ```yaml
    USE_LIMIT_REQ: "yes"
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "2r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Protecting Specific Endpoints"

    Configuration with different rate limits for various endpoints:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Default rule for all requests
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "10r/s"

    # Stricter limit for login page
    LIMIT_REQ_URL_2: "^/login"
    LIMIT_REQ_RATE_2: "1r/s"

    # Stricter limit for API
    LIMIT_REQ_URL_3: "^/api/"
    LIMIT_REQ_RATE_3: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "High-Traffic Site Configuration"

    Configuration tuned for high-traffic sites with more permissive limits:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # General limit
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "30r/s"

    # Admin area protection
    LIMIT_REQ_URL_2: "^/admin/"
    LIMIT_REQ_RATE_2: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "50"
    LIMIT_CONN_MAX_HTTP2: "200"
    LIMIT_CONN_MAX_HTTP3: "200"
    LIMIT_CONN_MAX_STREAM: "30"
    ```

=== "API Server Configuration"

    Configuration optimized for an API server with rate limits expressed in requests per minute:

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Public API endpoints
    LIMIT_REQ_URL: "^/api/public/"
    LIMIT_REQ_RATE: "120r/m"

    # Private API endpoints
    LIMIT_REQ_URL_2: "^/api/private/"
    LIMIT_REQ_RATE_2: "300r/m"

    # Authentication endpoint
    LIMIT_REQ_URL_3: "^/api/auth"
    LIMIT_REQ_RATE_3: "10r/m"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "20"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "20"
    ```
