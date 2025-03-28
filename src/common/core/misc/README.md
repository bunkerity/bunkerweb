The Miscellaneous plugin provides **essential baseline settings** that help maintain the security and functionality of your website. This core component offers comprehensive controls for:

- **Server behavior** - Configure how your server responds to various requests
- **HTTP settings** - Manage methods, request sizes, and protocol options
- **File management** - Control static file serving and optimize delivery
- **Protocol support** - Enable modern HTTP protocols for better performance
- **System configurations** - Extend functionality and improve security

Whether you need to restrict HTTP methods, manage request sizes, optimize file caching, or control how your server responds to various requests, this plugin gives you the tools to **fine-tune your web service's behavior** while optimizing both performance and security.

### Key Features

| Feature Category              | Description                                                                                        |
| ----------------------------- | -------------------------------------------------------------------------------------------------- |
| **HTTP Method Control**       | Define which HTTP methods are acceptable for your application                                      |
| **Default Server Protection** | Prevent unauthorized access through hostname mismatches and enforce SNI for secure connections     |
| **Request Size Management**   | Set limits for client request bodies and file uploads                                              |
| **Static File Serving**       | Configure and optimize delivery of static content from custom root folders                         |
| **File Caching**              | Improve performance through advanced file descriptor caching mechanisms with customizable settings |
| **Protocol Support**          | Configure modern HTTP protocol options (HTTP2/HTTP3) and Alt-Svc port settings                     |
| **Anonymous Reporting**       | Optional usage statistics reporting to help improve BunkerWeb                                      |
| **External Plugin Support**   | Extend functionality by integrating external plugins through URLs                                  |
| **HTTP Status Control**       | Configure how your server responds when denying requests (including connection termination)        |

### Configuration Guide

=== "Default Server Security"

    **Default Server Controls**

    In HTTP, the `Host` header specifies the target server, but it may be missing or unknown, often due to bots scanning for vulnerabilities.

    To block such requests:

    - Set `DISABLE_DEFAULT_SERVER` to `yes` to silently deny such requests using [NGINX's `444` status code](https://http.dev/444).
    - For stricter security, enable `DISABLE_DEFAULT_SERVER_STRICT_SNI` to reject SSL/TLS connections without valid SNI.

    !!! success "Security Benefits"
        - Blocks Host header manipulation and virtual host scanning
        - Mitigates HTTP request smuggling risks
        - Removes the default server as an attack vector

    | Setting                             | Default | Context | Multiple | Description                                                                                                      |
    | ----------------------------------- | ------- | ------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `DISABLE_DEFAULT_SERVER`            | `no`    | global  | no       | **Default Server:** Set to `yes` to disable the default server when no hostname matches the request.             |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`    | global  | no       | **Strict SNI:** When set to `yes`, requires SNI for HTTPS connections and rejects connections without valid SNI. |

    !!! warning "SNI Enforcement"
        Enabling strict SNI validation provides stronger security but may cause issues if BunkerWeb is behind a reverse proxy that forwards HTTPS requests without preserving SNI information. Test thoroughly before enabling in production environments.

=== "Deny HTTP Status"

    **HTTP Status Control**

    The first step in handling denied client access is defining the appropriate action. This can be configured using the `DENY_HTTP_STATUS` setting. When BunkerWeb denies a request, you can control its response using this setting. By default, it returns a `403 Forbidden` status, displaying a web page or custom content to the client.

    Alternatively, setting it to `444` closes the connection immediately without sending any response. This [non-standard status code](https://http.dev/444), specific to NGINX, is useful for silently dropping unwanted requests.

    | Setting            | Default | Context | Multiple | Description                                                                                                         |
    | ------------------ | ------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `DENY_HTTP_STATUS` | `403`   | global  | no       | **Deny HTTP Status:** HTTP status code to send when request is denied (403 or 444). Code 444 closes the connection. |

    !!! warning "444 Status Code considerations"
        Since clients receive no feedback, troubleshooting can be more challenging. Setting `444` is recommended only if you have thoroughly addressed false positives, are experienced with BunkerWeb, and require a higher level of security.

    !!! info "Stream mode"
        In **stream mode**, this setting is always enforced as `444`, meaning the connection will be closed, regardless of the configured value.

=== "HTTP Methods"

    **HTTP Method Control**

    Restricting HTTP methods to only those required by your application is a fundamental security measure that adheres to the principle of least privilege. By explicitly defining acceptable HTTP methods, you can minimize the risk of exploitation through unused or dangerous methods.

    This feature is configured using the `ALLOWED_METHODS` setting, where methods are listed and separated by a `|` (default: `GET|POST|HEAD`). If a client attempts to use a method not listed, the server will respond with a **405 - Method Not Allowed** status.

    For most websites, the default `GET|POST|HEAD` is sufficient. If your application uses RESTful APIs, you may need to include methods like `PUT` and `DELETE`.

    !!! success "Security Benefits"
        - Prevents exploitation of unused or unnecessary HTTP methods
        - Reduces the attack surface by disabling potentially harmful methods
        - Blocks HTTP method enumeration techniques used by attackers

    | Setting           | Default           | Context   | Multiple | Description                                                                            |
    | ----------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------- |
    | `ALLOWED_METHODS` | `GET\|POST\|HEAD` | multisite | no       | **HTTP Methods:** List of HTTP methods that are allowed, separated by pipe characters. |

    !!! abstract "CORS and Pre-flight Requests"
        If your application supports [Cross-Origin Resource Sharing (CORS)](#cors), you should include the `OPTIONS` method in the `ALLOWED_METHODS` setting to handle pre-flight requests. This ensures proper functionality for browsers making cross-origin requests.

    !!! danger "Security Considerations"
        - **Avoid enabling `TRACE` or `CONNECT`:** These methods are rarely needed and can introduce significant security risks, such as enabling Cross-Site Tracing (XST) or tunneling attacks.
        - **Regularly review allowed methods:** Periodically audit the `ALLOWED_METHODS` setting to ensure it aligns with your application's current requirements.
        - **Test thoroughly before deployment:** Changes to HTTP method restrictions can impact application functionality. Validate your configuration in a staging environment before applying it to production.

=== "Request Size Limits"

    **Request Size Limits**

    The maximum request body size can be controlled using the `MAX_CLIENT_SIZE` setting (default: `10m`). Accepted values follow the syntax described [here](https://nginx.org/en/docs/syntax.html).

    !!! success "Security Benefits"
        - Protects against denial-of-service attacks caused by excessive payload sizes
        - Mitigates buffer overflow vulnerabilities
        - Prevents file upload attacks
        - Reduces the risk of server resource exhaustion

    | Setting           | Default | Context   | Multiple | Description                                                                                        |
    | ----------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`   | multisite | no       | **Maximum Request Size:** The maximum allowed size for client request bodies (e.g., file uploads). |

    !!! tip "Request Size Configuration Best Practices"
        If you need to allow a request body of unlimited size, you can set the `MAX_CLIENT_SIZE` value to `0`. However, this is **not recommended** due to potential security and performance risks.

        **Best Practices:**

        - Always configure `MAX_CLIENT_SIZE` to the smallest value that meets your application's legitimate requirements.
        - Regularly review and adjust this setting to align with your application's evolving needs.
        - Avoid setting `0` unless absolutely necessary, as it can expose your server to denial-of-service attacks and resource exhaustion.

        By carefully managing this setting, you can ensure optimal security and performance for your application.

=== "Protocol Support"

    **HTTP Protocol Settings**

    Modern HTTP protocols like HTTP/2 and HTTP/3 improve performance and security. BunkerWeb allows easy configuration of these protocols.

    !!! success "Security and Performance Benefits"
        - **Security Advantages:** Modern protocols like HTTP/2 and HTTP/3 enforce TLS/HTTPS by default, reduce susceptibility to certain attacks, and improve privacy through encrypted headers (HTTP/3).
        - **Performance Benefits:** Features like multiplexing, header compression, server push, and binary data transfer enhance speed and efficiency.

    | Setting              | Default | Context   | Multiple | Description                                                             |
    | -------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`   | multisite | no       | **HTTP Listen:** Respond to (insecure) HTTP requests when set to `yes`. |
    | `HTTP2`              | `yes`   | multisite | no       | **HTTP2:** Support HTTP2 protocol when HTTPS is enabled.                |
    | `HTTP3`              | `yes`   | multisite | no       | **HTTP3:** Support HTTP3 protocol when HTTPS is enabled.                |
    | `HTTP3_ALT_SVC_PORT` | `443`   | multisite | no       | **HTTP3 Alt-Svc Port:** Port to use in the Alt-Svc header for HTTP3.    |

    !!! example "About HTTP/3"
        HTTP/3, the latest version of the Hypertext Transfer Protocol, uses QUIC over UDP instead of TCP, addressing issues like head-of-line blocking for faster, more reliable connections.

        NGINX introduced experimental support for HTTP/3 and QUIC starting with version 1.25.0. However, this feature is still experimental, and caution is advised for production use. For more details, see [NGINX's official documentation](https://nginx.org/en/docs/quic.html).

        Thorough testing is recommended before enabling HTTP/3 in production environments.

=== "Static File Serving"

    **File Serving Configuration**

    BunkerWeb can serve static files directly or act as a reverse proxy to an application server. By default, files are served from `/var/www/html/{server_name}`.

    | Setting       | Default                       | Context   | Multiple | Description                                                                                            |
    | ------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `SERVE_FILES` | `yes`                         | multisite | no       | **Serve Files:** When set to `yes`, BunkerWeb will serve static files from the configured root folder. |
    | `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | no       | **Root Folder:** The directory from which to serve static files. Empty means use the default location. |

    !!! tip "Best Practices for Static File Serving"
        - **Direct Serving:** Enable file serving (`SERVE_FILES=yes`) when BunkerWeb is responsible for serving static files directly.
        - **Reverse Proxy:** If BunkerWeb acts as a reverse proxy, **deactivate file serving** (`SERVE_FILES=no`) to reduce the attack surface and avoid exposing unnecessary directories.
        - **Permissions:** Ensure proper file permissions and path configurations to prevent unauthorized access.
        - **Security:** Avoid exposing sensitive directories or files through misconfigurations.

        By carefully managing static file serving, you can optimize performance while maintaining a secure environment.

=== "System Settings"

    **Plugin and System Management**

    These settings manage BunkerWeb's interaction with external systems and contribute to improving the product through optional anonymous usage statistics.

    **Anonymous Reporting**

    Anonymous reporting provides the BunkerWeb team with insights into how the software is being used. This helps identify areas for improvement and prioritize feature development. The reports are strictly statistical and do not include any sensitive or personally identifiable information. They cover:

    - Enabled features
    - General configuration patterns

    You can disable this feature if desired by setting `SEND_ANONYMOUS_REPORT` to `no`.

    **External Plugins**

    External plugins enable you to extend BunkerWeb's functionality by integrating third-party modules. This allows for additional customization and advanced use cases.

    !!! danger "External Plugin Security"
        **External plugins can introduce security risks if not properly vetted.** Follow these best practices to minimize potential threats:

        - Only use plugins from trusted sources.
        - Verify plugin integrity using checksums when available.
        - Regularly review and update plugins to ensure security and compatibility.

        For more details, refer to the [Plugins documentation](plugins.md).

    | Setting                 | Default | Context | Multiple | Description                                                                    |
    | ----------------------- | ------- | ------- | -------- | ------------------------------------------------------------------------------ |
    | `SEND_ANONYMOUS_REPORT` | `yes`   | global  | no       | **Anonymous Reports:** Send anonymous usage reports to BunkerWeb maintainers.  |
    | `EXTERNAL_PLUGIN_URLS`  |         | global  | no       | **External Plugins:** URLs for external plugins to download (space-separated). |

=== "File Caching"

    **File Cache Optimization**

    The open file cache improves performance by storing file descriptors and metadata in memory, reducing the need for repeated file system operations.

    !!! success "Benefits of File Caching"
        - **Performance:** Reduces filesystem I/O, decreases latency, and lowers CPU usage for file operations.
        - **Security:** Mitigates timing attacks by caching error responses and reduces the impact of DoS attacks targeting the filesystem.

    | Setting                    | Default                 | Context   | Multiple | Description                                                                                          |
    | -------------------------- | ----------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no       | **Enable Cache:** Enable caching of file descriptors and metadata to improve performance.            |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no       | **Cache Configuration:** Configure the open file cache (e.g., maximum entries and inactive timeout). |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no       | **Cache Errors:** Cache file descriptor lookup errors as well as successful lookups.                 |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no       | **Minimum Uses:** Minimum number of accesses during the inactive period for a file to remain cached. |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no       | **Cache Validity:** Time after which cached elements are revalidated.                                |

    **Configuration Guide**

    To enable and configure file caching:
    1. Set `USE_OPEN_FILE_CACHE` to `yes` to activate the feature.
    2. Adjust `OPEN_FILE_CACHE` parameters to define the maximum number of cached entries and their inactive timeout.
    3. Use `OPEN_FILE_CACHE_ERRORS` to cache both successful and failed lookups, reducing repeated filesystem operations.
    4. Set `OPEN_FILE_CACHE_MIN_USES` to specify the minimum number of accesses required for a file to remain cached.
    5. Define the cache validity period with `OPEN_FILE_CACHE_VALID` to control how often cached elements are revalidated.

    !!! tip "Best Practices"
        - Enable file caching for websites with many static files to improve performance.
        - Regularly review and fine-tune cache settings to balance performance and resource usage.
        - In dynamic environments where files change frequently, consider reducing the cache validity period or disabling the feature to ensure content freshness.

### Example Configurations

=== "Default Server Security"

    Example configuration for disabling the default server and enforcing strict SNI:

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "Deny HTTP Status"

    Example configuration for silently dropping unwanted requests:

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "HTTP Methods"

    Example configuration for restricting HTTP methods to only those required by a RESTful API:

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "Request Size Limits"

    Example configuration for limiting the maximum request body size:

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "Protocol Support"

    Example configuration for enabling HTTP/2 and HTTP/3 with a custom Alt-Svc port:

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "Static File Serving"

    Example configuration for serving static files from a custom root folder:

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "File Caching"

    Example configuration for enabling and optimizing file caching:

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"
