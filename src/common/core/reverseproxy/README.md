The Reverse Proxy plugin provides seamless proxying capabilities for BunkerWeb, allowing you to route requests to backend servers and services. This feature enables BunkerWeb to act as a secure frontend for your applications while providing additional benefits such as SSL termination and security filtering.

**How it works:**

1. When a client sends a request to BunkerWeb, the Reverse Proxy plugin forwards the request to your configured backend server.
2. BunkerWeb adds security headers, applies WAF rules, and performs other security checks before passing requests to your application.
3. The backend server processes the request and returns a response to BunkerWeb.
4. BunkerWeb applies additional security measures to the response before sending it back to the client.
5. The plugin supports both HTTP and TCP/UDP stream proxying, enabling a wide range of applications, including WebSockets and other non-HTTP protocols.

### How to Use

Follow these steps to configure and use the Reverse Proxy feature:

1. **Enable the feature:** Set the `USE_REVERSE_PROXY` setting to `yes` to enable reverse proxy functionality.
2. **Configure your backend servers:** Specify the upstream servers using the `REVERSE_PROXY_HOST` setting.
3. **Adjust proxy settings:** Fine-tune behavior with optional settings for timeouts, buffer sizes, and other parameters.
4. **Configure protocol-specific options:** For WebSockets or special HTTP requirements, adjust the corresponding settings.
5. **Set up caching (optional):** Enable and configure proxy caching to improve performance for frequently accessed content.

### Configuration Guide

=== "Basic Configuration"

    **Core Settings**

    The essential configuration settings enable and control the basic functionality of the reverse proxy feature.

    !!! success "Benefits of Reverse Proxy"
        - **Security Enhancement:** All traffic passes through BunkerWeb's security layers before reaching your applications
        - **SSL Termination:** Manage SSL/TLS certificates centrally while backend services can use unencrypted connections
        - **Protocol Handling:** Support for HTTP, HTTPS, WebSockets, and other protocols
        - **Error Interception:** Customize error pages for a consistent user experience

    | Setting                          | Default | Context   | Multiple | Description                                                                              |
    | -------------------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`              | `no`    | multisite | no       | **Enable Reverse Proxy:** Set to `yes` to enable reverse proxy functionality.            |
    | `REVERSE_PROXY_HOST`             |         | multisite | yes      | **Backend Host:** Full URL of the proxied resource (proxy_pass).                         |
    | `REVERSE_PROXY_URL`              | `/`     | multisite | yes      | **Location URL:** Path that will be proxied to the backend server.                       |
    | `REVERSE_PROXY_BUFFERING`        | `yes`   | multisite | yes      | **Response Buffering:** Enable or disable buffering of responses from proxied resource.  |
    | `REVERSE_PROXY_REQUEST_BUFFERING`| `yes`   | multisite | yes      | **Request Buffering:** Enable or disable buffering of requests to the proxied resource.  |
    | `REVERSE_PROXY_KEEPALIVE`        | `no`    | multisite | yes      | **Keep-Alive:** Enable or disable keepalive connections with the proxied resource.       |
    | `REVERSE_PROXY_CUSTOM_HOST`      |         | multisite | no       | **Custom Host:** Override Host header sent to upstream server.                           |
    | `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`   | multisite | no       | **Intercept Errors:** Whether to intercept and rewrite error responses from the backend. |

    !!! tip "Best Practices"
        - Always specify the full URL in `REVERSE_PROXY_HOST` including the protocol (http:// or https://)
        - Use `REVERSE_PROXY_INTERCEPT_ERRORS` to provide consistent error pages across all your services
        - When configuring multiple backends, use the numbered suffix format (e.g., `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

    !!! warning "Request buffering behavior"
        Disabling `REVERSE_PROXY_REQUEST_BUFFERING` only takes effect when ModSecurity is disabled, because request buffering is otherwise enforced.

=== "Connection Settings"

    **Connection and Timeout Configuration**

    These settings control connection behavior, buffering, and timeout values for the proxied connections.

    !!! success "Benefits"
        - **Optimized Performance:** Adjust buffer sizes and connection settings based on your application needs
        - **Resource Management:** Control memory usage through appropriate buffer configurations
        - **Reliability:** Configure appropriate timeouts to handle slow connections or backend issues

    | Setting                         | Default | Context   | Multiple | Description                                                                                             |
    | ------------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`   | multisite | yes      | **Connect Timeout:** Maximum time to establish a connection to the backend server.                      |
    | `REVERSE_PROXY_READ_TIMEOUT`    | `60s`   | multisite | yes      | **Read Timeout:** Maximum time between transmissions of two successive packets from the backend server. |
    | `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`   | multisite | yes      | **Send Timeout:** Maximum time between transmissions of two successive packets to the backend server.   |
    | `PROXY_BUFFERS`                 |         | multisite | no       | **Buffers:** Number and size of buffers for reading the response from the backend server.               |
    | `PROXY_BUFFER_SIZE`             |         | multisite | no       | **Buffer Size:** Size of the buffer for reading the first part of the response from the backend server. |
    | `PROXY_BUSY_BUFFERS_SIZE`       |         | multisite | no       | **Busy Buffers Size:** Size of buffers that can be busy sending response to the client.                 |

    !!! warning "Timeout Considerations"
        - Setting timeouts too low may cause legitimate but slow connections to be terminated
        - Setting timeouts too high may leave connections open unnecessarily, potentially exhausting resources
        - For WebSocket applications, increase the read and send timeouts significantly (300s or more recommended)

=== "SSL/TLS Configuration"

    **SSL/TLS Settings for Backend Connections**

    These settings control how BunkerWeb establishes secure connections to backend servers.

    !!! success "Benefits"
        - **End-to-End Encryption:** Maintain encrypted connections from client to backend
        - **Certificate Validation:** Control how backend server certificates are validated
        - **SNI Support:** Specify Server Name Indication for backends that host multiple sites

    | Setting                      | Default | Context   | Multiple | Description                                                                          |
    | ---------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------ |
    | `REVERSE_PROXY_SSL_SNI`      | `no`    | multisite | no       | **SSL SNI:** Enable or disable sending SNI (Server Name Indication) to upstream.     |
    | `REVERSE_PROXY_SSL_SNI_NAME` |         | multisite | no       | **SSL SNI Name:** Sets the SNI hostname to send to upstream when SSL SNI is enabled. |

    !!! info "SNI Explained"
        Server Name Indication (SNI) is a TLS extension that allows a client to specify the hostname it is attempting to connect to during the handshake process. This enables servers to present multiple certificates on the same IP address and port, allowing multiple secure (HTTPS) websites to be served from a single IP address without requiring all those sites to use the same certificate.

=== "Protocol Support"

    **Protocol-Specific Configuration**

    Configure special protocol handling, particularly for WebSockets and other non-HTTP protocols.

    !!! success "Benefits"
        - **Protocol Flexibility:** Support for WebSockets enables real-time applications
        - **Modern Web Applications:** Enable interactive features requiring bidirectional communication

    | Setting            | Default | Context   | Multiple | Description                                                       |
    | ------------------ | ------- | --------- | -------- | ----------------------------------------------------------------- |
    | `REVERSE_PROXY_WS` | `no`    | multisite | yes      | **WebSocket Support:** Enable WebSocket protocol on the resource. |

    !!! tip "WebSocket Configuration"
        - When enabling WebSockets with `REVERSE_PROXY_WS: "yes"`, consider increasing timeout values
        - WebSocket connections stay open longer than typical HTTP connections
        - For WebSocket applications, a recommended configuration is:
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Header Management"

    **HTTP Header Configuration**

    Control which headers are sent to backend servers and to clients, allowing you to add, modify, or preserve HTTP headers.

    !!! success "Benefits"
        - **Information Control:** Precisely manage what information is shared between clients and backends
        - **Security Enhancement:** Add security-related headers or remove headers that might leak sensitive information
        - **Integration Support:** Provide necessary headers for authentication and proper backend operation

    | Setting                                | Default   | Context   | Multiple | Description                                                                           |
    | -------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_HEADERS`                |           | multisite | yes      | **Custom Headers:** HTTP headers to send to backend separated with semicolons.        |
    | `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade` | multisite | yes      | **Hide Headers:** HTTP headers to hide from clients when received from the backend.   |
    | `REVERSE_PROXY_HEADERS_CLIENT`         |           | multisite | yes      | **Client Headers:** HTTP headers to send to client separated with semicolons.         |
    | `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`      | multisite | no       | **Underscores in Headers:** Enable or disable the `underscores_in_headers` directive. |

    !!! warning "Security Considerations"
        When using the reverse proxy feature, be cautious about what headers you forward to your backend applications. Certain headers might expose sensitive information about your infrastructure or bypass security controls.

    !!! example "Header Format Examples"
        Custom headers to backend servers:
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        Custom headers to clients:
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Authentication"

    **External Authentication Configuration**

    Integrate with external authentication systems to centralize authorization logic across your applications.

    !!! success "Benefits"
        - **Centralized Authentication:** Implement a single authentication point for multiple applications
        - **Consistent Security:** Apply uniform authentication policies across different services
        - **Enhanced Control:** Forward authentication details to backend applications via headers or variables

    | Setting                                 | Default | Context   | Multiple | Description                                                                 |
    | --------------------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `REVERSE_PROXY_AUTH_REQUEST`            |         | multisite | yes      | **Auth Request:** Enable authentication using an external provider.         |
    | `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |         | multisite | yes      | **Sign-in URL:** Redirect clients to sign-in URL when authentication fails. |
    | `REVERSE_PROXY_AUTH_REQUEST_SET`        |         | multisite | yes      | **Auth Request Set:** Variables to set from the authentication provider.    |

    !!! tip "Authentication Integration"
        - The auth request feature enables implementation of centralized authentication microservices
        - Your authentication service should return a 200 status code for successful authentication or 401/403 for failures
        - Use the auth_request_set directive to extract and forward information from the authentication service

=== "Advanced Configuration"

    **Additional Configuration Options**

    These settings provide further customization of the reverse proxy behavior for specialized scenarios.

    !!! success "Benefits"
        - **Customization:** Include additional configuration snippets for complex requirements
        - **Performance Optimization:** Fine-tune request handling for specific use cases
        - **Flexibility:** Adapt to unique application requirements with specialized configurations

    | Setting                           | Default | Context   | Multiple | Description                                                                  |
    | --------------------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |         | multisite | yes      | **Additional Configurations:** Include additional configs in location block. |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`   | multisite | yes      | **Pass Request Body:** Enable or disable passing the request body.           |

    !!! warning "Security Considerations"
        Be careful when including custom configuration snippets as they may override BunkerWeb's security settings or introduce vulnerabilities if not properly configured.

=== "Caching Configuration"

    **Response Caching Settings**

    Improve performance by caching responses from backend servers, reducing load and improving response times.

    !!! success "Benefits"
        - **Performance:** Reduce load on backend servers by serving cached content
        - **Reduced Latency:** Faster response times for frequently requested content
        - **Bandwidth Savings:** Minimize internal network traffic by caching responses
        - **Customization:** Configure exactly what, when, and how content is cached

    | Setting                      | Default                            | Context   | Multiple | Description                                                                    |
    | ---------------------------- | ---------------------------------- | --------- | -------- | ------------------------------------------------------------------------------ |
    | `USE_PROXY_CACHE`            | `no`                               | multisite | no       | **Enable Caching:** Set to `yes` to enable caching of backend responses.       |
    | `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | no       | **Cache Path Levels:** How to structure the cache directory hierarchy.         |
    | `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | no       | **Cache Zone Size:** Size of the shared memory zone used for cache metadata.   |
    | `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | no       | **Cache Path Parameters:** Additional parameters for the cache path.           |
    | `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | no       | **Cache Methods:** HTTP methods that can be cached.                            |
    | `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | no       | **Cache Min Uses:** Minimum number of requests before a response is cached.    |
    | `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | no       | **Cache Key:** The key used to uniquely identify a cached response.            |
    | `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | no       | **Cache Valid:** How long to cache specific response codes.                    |
    | `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | no       | **No Cache:** Conditions for not caching responses even if normally cacheable. |
    | `PROXY_CACHE_BYPASS`         | `0`                                | multisite | no       | **Cache Bypass:** Conditions under which to bypass the cache.                  |

    !!! tip "Caching Best Practices"
        - Cache only content that doesn't change frequently or isn't personalized
        - Use appropriate cache durations based on content type (static assets can be cached longer)
        - Configure `PROXY_NO_CACHE` to avoid caching sensitive or personalized content
        - Monitor cache hit rates and adjust settings accordingly

!!! danger "Docker Compose Users - NGINX Variables"
    When using Docker Compose with NGINX variables in your configurations, you must escape the dollar sign (`$`) by using double dollar signs (`$$`). This applies to all settings that contain NGINX variables like `$remote_addr`, `$proxy_add_x_forwarded_for`, etc.

    Without this escaping, Docker Compose will try to substitute these variables with environment variables, which typically don't exist, resulting in empty values in your NGINX configuration.

### Example Configurations

=== "Basic HTTP Proxy"

    A simple configuration for proxying HTTP requests to a backend application server:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "WebSocket Application"

    Configuration optimized for a WebSocket application with longer timeouts:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Multiple Locations"

    Configuration for routing different paths to different backend services:

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # API Backend
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Admin Backend
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Frontend App
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Caching Configuration"

    Configuration with proxy caching enabled for better performance:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Advanced Header Management"

    Configuration with custom header manipulation:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Custom headers to backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # Custom headers to client
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Authentication Integration"

    Configuration with external authentication:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Authentication configuration
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Auth service backend
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```
