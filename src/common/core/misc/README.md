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

    | Setting                             | Default | Context | Multiple | Description                                                                                                         |
    | ----------------------------------- | ------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `DISABLE_DEFAULT_SERVER`            | `no`    | global  | no       | **Default Server:** Set to `yes` to disable the default server when no hostname matches the request.                |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`    | global  | no       | **Strict SNI:** When set to `yes`, requires SNI for HTTPS connections and rejects connections without valid SNI.    |
    | `DENY_HTTP_STATUS`                  | `403`   | global  | no       | **Deny HTTP Status:** HTTP status code to send when request is denied (403 or 444). Code 444 closes the connection. |

    !!! warning "Default Server Security"
        The default server settings can have significant security implications. When `DISABLE_DEFAULT_SERVER` is set to `yes`, clients that don't specify a valid hostname will receive an error, which can help prevent certain reconnaissance techniques.

        For SSL/TLS connections, enabling `DISABLE_DEFAULT_SERVER_STRICT_SNI` provides an additional layer of security by requiring a valid Server Name Indication.

=== "System Settings"

    **Plugin and System Management**

    | Setting                 | Default | Context | Multiple | Description                                                                    |
    | ----------------------- | ------- | ------- | -------- | ------------------------------------------------------------------------------ |
    | `SEND_ANONYMOUS_REPORT` | `yes`   | global  | no       | **Anonymous Reports:** Send anonymous usage reports to BunkerWeb maintainers.  |
    | `EXTERNAL_PLUGIN_URLS`  |         | global  | no       | **External Plugins:** URLs for external plugins to download (space-separated). |

    !!! info "Anonymous Reporting"
        Anonymous usage reports help the BunkerWeb team understand how the software is being used and identify areas for improvement. No sensitive data is collected.

=== "HTTP Methods"

    **HTTP Method Control**

    | Setting           | Default           | Context   | Multiple | Description                                                                            |
    | ----------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------- |
    | `ALLOWED_METHODS` | `GET\|POST\|HEAD` | multisite | no       | **HTTP Methods:** List of HTTP methods that are allowed, separated by pipe characters. |

    !!! tip "Allowed Methods"
        Restricting HTTP methods to only those needed by your application is a security best practice. For most websites, the default `GET|POST|HEAD` is sufficient. Add `PUT` and `DELETE` only if your application uses RESTful APIs that require these methods.

=== "Request Handling"

    **Request Size Limits**

    | Setting           | Default | Context   | Multiple | Description                                                                                        |
    | ----------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`   | multisite | no       | **Maximum Request Size:** The maximum allowed size for client request bodies (e.g., file uploads). |

    Common `MAX_CLIENT_SIZE` values:

    - `1m` - Suitable for forms with small file uploads
    - `10m` - Default, balanced for most websites
    - `100m` - For services that handle large file uploads

=== "Protocol Support"

    **HTTP Protocol Settings**

    | Setting              | Default | Context   | Multiple | Description                                                             |
    | -------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`   | multisite | no       | **HTTP Listen:** Respond to (insecure) HTTP requests when set to `yes`. |
    | `HTTP2`              | `yes`   | multisite | no       | **HTTP2:** Support HTTP2 protocol when HTTPS is enabled.                |
    | `HTTP3`              | `yes`   | multisite | no       | **HTTP3:** Support HTTP3 protocol when HTTPS is enabled.                |
    | `HTTP3_ALT_SVC_PORT` | `443`   | multisite | no       | **HTTP3 Alt-Svc Port:** Port to use in the Alt-Svc header for HTTP3.    |

    !!! info "Modern Protocol Support"
        HTTP/2 and HTTP/3 provide significant performance improvements over HTTP/1.1, including multiplexing, header compression, and reduced latency. Enabling these protocols is recommended for most websites.

=== "Static File Serving"

    **File Serving Configuration**

    | Setting       | Default | Context   | Multiple | Description                                                                                            |
    | ------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `SERVE_FILES` | `yes`   | multisite | no       | **Serve Files:** When set to `yes`, BunkerWeb will serve static files from the configured root folder. |
    | `ROOT_FOLDER` |         | multisite | no       | **Root Folder:** The directory from which to serve static files. Empty means use the default location. |

    To configure static file serving:

    - Enable or disable serving static files with the `SERVE_FILES` setting
    - Specify a custom root directory with `ROOT_FOLDER` or leave empty to use the default location

=== "File Caching"

    **File Cache Optimization**

    | Setting                    | Default                 | Context   | Multiple | Description                                                                                                     |
    | -------------------------- | ----------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no       | **Open File Cache:** Set to `yes` to enable caching of file descriptors and metadata to improve performance.    |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no       | **Cache Configuration:** Settings for the open file cache in nginx format.                                      |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no       | **Cache Errors:** Set to `yes` to cache file descriptor lookup errors as well as successful lookups.            |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no       | **Minimum Uses:** The minimum number of file accesses during the inactive period for the file to remain cached. |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no       | **Cache Valid:** The time after which open file cache elements are validated.                                   |

    To optimize file caching:

    - Enable the open file cache with `USE_OPEN_FILE_CACHE`
    - Configure cache parameters with `OPEN_FILE_CACHE` (format: `max=N inactive=Ts`)
    - Control error caching with `OPEN_FILE_CACHE_ERRORS`
    - Set minimum access count with `OPEN_FILE_CACHE_MIN_USES`
    - Define validation period with `OPEN_FILE_CACHE_VALID`

    !!! info "Open File Cache"
        Enabling the open file cache can significantly improve performance for websites serving many static files, as it reduces the need for repeated file system operations. However, in dynamic environments where files change frequently, you may need to adjust the cache validity period or disable this feature.
