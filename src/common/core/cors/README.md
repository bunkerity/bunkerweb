# CORS Plugin

The CORS plugin enables Cross-Origin Resource Sharing for your website, allowing controlled access to your resources from different domains. This feature helps you safely share your content with trusted third-party websites while maintaining security by explicitly defining which origins, methods, and headers are permitted.

**How it works:**

1. When a browser makes a cross-origin request to your website, it first sends a preflight request with the `OPTIONS` method.
2. BunkerWeb checks if the requesting origin is permitted based on your configuration.
3. If allowed, BunkerWeb responds with the appropriate CORS headers that define what the requesting site can do.
4. For non-permitted origins, the request can be either completely denied or served without CORS headers.
5. Additional cross-origin policies, such as [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy), and [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy), can be configured to further enhance security.

## How to Use

Follow these steps to configure and use the CORS feature:

1. **Enable the feature:** The CORS feature is disabled by default. Set the `USE_CORS` setting to `yes` to enable it.
2. **Configure allowed origins:** Specify which domains can access your resources using the `CORS_ALLOW_ORIGIN` setting.
3. **Set permitted methods:** Define which HTTP methods are allowed for cross-origin requests with `CORS_ALLOW_METHODS`.
4. **Configure allowed headers:** Specify which headers can be used in requests with `CORS_ALLOW_HEADERS`.
5. **Control credentials:** Decide whether cross-origin requests can include credentials using `CORS_ALLOW_CREDENTIALS`.

## Configuration Settings

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Enable CORS:** Set to `yes` to enable Cross-Origin Resource Sharing.                                                             |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Allowed Origins:** PCRE regular expression representing allowed origins; use `*` for any origin, or `self` for same-origin only. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Allowed Methods:** HTTP methods that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Allowed Headers:** HTTP headers that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Allow Credentials:** Set to `yes` to allow credentials (cookies, HTTP authentication) in CORS requests.                          |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Exposed Headers:** HTTP headers that browsers are permitted to access from cross-origin responses.                               |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controls communication between browsing contexts.                                                  |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controls whether a document can load resources from other origins.                               |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controls which websites can embed your resources.                                                |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Preflight Cache Duration:** How long (in seconds) browsers should cache the preflight response.                                  |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Deny Unauthorized Origins:** When `yes`, requests from unauthorized origins are denied with an error code.                       |

!!! tip "Optimizing Preflight Requests"
    The `CORS_MAX_AGE` setting determines how long browsers will cache the results of a preflight request. Setting this to a higher value (like the default 86400 seconds/24 hours) reduces the number of preflight requests, improving performance for frequently accessed resources.

!!! warning "Security Considerations"
    Be cautious when setting `CORS_ALLOW_ORIGIN` to `*` (all origins) or `CORS_ALLOW_CREDENTIALS` to `yes` because these configurations may introduce security risks if not properly managed. It's generally safer to explicitly list trusted origins and limit the allowed methods and headers.

## Example Configurations

Here are examples of possible values for the `CORS_ALLOW_ORIGIN` setting, along with their behavior:

- **`*`**: Allows requests from all origins.
- **`self`**: Automatically allows requests from the same origin as the configured server_name.
- **`^https://www\.example\.com# CORS Plugin

The CORS plugin enables Cross-Origin Resource Sharing for your website, allowing controlled access to your resources from different domains. This feature helps you safely share your content with trusted third-party websites while maintaining security by explicitly defining which origins, methods, and headers are permitted.

**How it works:**

1. When a browser makes a cross-origin request to your website, it first sends a preflight request with the `OPTIONS` method.
2. BunkerWeb checks if the requesting origin is permitted based on your configuration.
3. If allowed, BunkerWeb responds with the appropriate CORS headers that define what the requesting site can do.
4. For non-permitted origins, the request can be either completely denied or served without CORS headers.
5. Additional cross-origin policies, such as [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy), and [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy), can be configured to further enhance security.

## How to Use

Follow these steps to configure and use the CORS feature:

1. **Enable the feature:** The CORS feature is disabled by default. Set the `USE_CORS` setting to `yes` to enable it.
2. **Configure allowed origins:** Specify which domains can access your resources using the `CORS_ALLOW_ORIGIN` setting.
3. **Set permitted methods:** Define which HTTP methods are allowed for cross-origin requests with `CORS_ALLOW_METHODS`.
4. **Configure allowed headers:** Specify which headers can be used in requests with `CORS_ALLOW_HEADERS`.
5. **Control credentials:** Decide whether cross-origin requests can include credentials using `CORS_ALLOW_CREDENTIALS`.

## Configuration Settings

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Enable CORS:** Set to `yes` to enable Cross-Origin Resource Sharing.                                                             |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Allowed Origins:** PCRE regular expression representing allowed origins; use `*` for any origin, or `self` for same-origin only. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Allowed Methods:** HTTP methods that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Allowed Headers:** HTTP headers that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Allow Credentials:** Set to `yes` to allow credentials (cookies, HTTP authentication) in CORS requests.                          |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Exposed Headers:** HTTP headers that browsers are permitted to access from cross-origin responses.                               |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controls communication between browsing contexts.                                                  |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controls whether a document can load resources from other origins.                               |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controls which websites can embed your resources.                                                |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Preflight Cache Duration:** How long (in seconds) browsers should cache the preflight response.                                  |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Deny Unauthorized Origins:** When `yes`, requests from unauthorized origins are denied with an error code.                       |

!!! tip "Optimizing Preflight Requests"
    The `CORS_MAX_AGE` setting determines how long browsers will cache the results of a preflight request. Setting this to a higher value (like the default 86400 seconds/24 hours) reduces the number of preflight requests, improving performance for frequently accessed resources.

!!! warning "Security Considerations"
    Be cautious when setting `CORS_ALLOW_ORIGIN` to `*` (all origins) or `CORS_ALLOW_CREDENTIALS` to `yes` because these configurations may introduce security risks if not properly managed. It's generally safer to explicitly list trusted origins and limit the allowed methods and headers.

**: Allows requests only from `https://www.example.com`.
- **`^https://.+\.example\.com# CORS Plugin

The CORS plugin enables Cross-Origin Resource Sharing for your website, allowing controlled access to your resources from different domains. This feature helps you safely share your content with trusted third-party websites while maintaining security by explicitly defining which origins, methods, and headers are permitted.

**How it works:**

1. When a browser makes a cross-origin request to your website, it first sends a preflight request with the `OPTIONS` method.
2. BunkerWeb checks if the requesting origin is permitted based on your configuration.
3. If allowed, BunkerWeb responds with the appropriate CORS headers that define what the requesting site can do.
4. For non-permitted origins, the request can be either completely denied or served without CORS headers.
5. Additional cross-origin policies, such as [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy), and [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy), can be configured to further enhance security.

## How to Use

Follow these steps to configure and use the CORS feature:

1. **Enable the feature:** The CORS feature is disabled by default. Set the `USE_CORS` setting to `yes` to enable it.
2. **Configure allowed origins:** Specify which domains can access your resources using the `CORS_ALLOW_ORIGIN` setting.
3. **Set permitted methods:** Define which HTTP methods are allowed for cross-origin requests with `CORS_ALLOW_METHODS`.
4. **Configure allowed headers:** Specify which headers can be used in requests with `CORS_ALLOW_HEADERS`.
5. **Control credentials:** Decide whether cross-origin requests can include credentials using `CORS_ALLOW_CREDENTIALS`.

## Configuration Settings

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Enable CORS:** Set to `yes` to enable Cross-Origin Resource Sharing.                                                             |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Allowed Origins:** PCRE regular expression representing allowed origins; use `*` for any origin, or `self` for same-origin only. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Allowed Methods:** HTTP methods that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Allowed Headers:** HTTP headers that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Allow Credentials:** Set to `yes` to allow credentials (cookies, HTTP authentication) in CORS requests.                          |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Exposed Headers:** HTTP headers that browsers are permitted to access from cross-origin responses.                               |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controls communication between browsing contexts.                                                  |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controls whether a document can load resources from other origins.                               |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controls which websites can embed your resources.                                                |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Preflight Cache Duration:** How long (in seconds) browsers should cache the preflight response.                                  |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Deny Unauthorized Origins:** When `yes`, requests from unauthorized origins are denied with an error code.                       |

!!! tip "Optimizing Preflight Requests"
    The `CORS_MAX_AGE` setting determines how long browsers will cache the results of a preflight request. Setting this to a higher value (like the default 86400 seconds/24 hours) reduces the number of preflight requests, improving performance for frequently accessed resources.

!!! warning "Security Considerations"
    Be cautious when setting `CORS_ALLOW_ORIGIN` to `*` (all origins) or `CORS_ALLOW_CREDENTIALS` to `yes` because these configurations may introduce security risks if not properly managed. It's generally safer to explicitly list trusted origins and limit the allowed methods and headers.

**: Allows requests from any subdomain ending with `.example.com`.
- **`^https://(www\.example1\.com|www\.example2\.com)# CORS Plugin

The CORS plugin enables Cross-Origin Resource Sharing for your website, allowing controlled access to your resources from different domains. This feature helps you safely share your content with trusted third-party websites while maintaining security by explicitly defining which origins, methods, and headers are permitted.

**How it works:**

1. When a browser makes a cross-origin request to your website, it first sends a preflight request with the `OPTIONS` method.
2. BunkerWeb checks if the requesting origin is permitted based on your configuration.
3. If allowed, BunkerWeb responds with the appropriate CORS headers that define what the requesting site can do.
4. For non-permitted origins, the request can be either completely denied or served without CORS headers.
5. Additional cross-origin policies, such as [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy), and [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy), can be configured to further enhance security.

## How to Use

Follow these steps to configure and use the CORS feature:

1. **Enable the feature:** The CORS feature is disabled by default. Set the `USE_CORS` setting to `yes` to enable it.
2. **Configure allowed origins:** Specify which domains can access your resources using the `CORS_ALLOW_ORIGIN` setting.
3. **Set permitted methods:** Define which HTTP methods are allowed for cross-origin requests with `CORS_ALLOW_METHODS`.
4. **Configure allowed headers:** Specify which headers can be used in requests with `CORS_ALLOW_HEADERS`.
5. **Control credentials:** Decide whether cross-origin requests can include credentials using `CORS_ALLOW_CREDENTIALS`.

## Configuration Settings

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Enable CORS:** Set to `yes` to enable Cross-Origin Resource Sharing.                                                             |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Allowed Origins:** PCRE regular expression representing allowed origins; use `*` for any origin, or `self` for same-origin only. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Allowed Methods:** HTTP methods that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Allowed Headers:** HTTP headers that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Allow Credentials:** Set to `yes` to allow credentials (cookies, HTTP authentication) in CORS requests.                          |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Exposed Headers:** HTTP headers that browsers are permitted to access from cross-origin responses.                               |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controls communication between browsing contexts.                                                  |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controls whether a document can load resources from other origins.                               |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controls which websites can embed your resources.                                                |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Preflight Cache Duration:** How long (in seconds) browsers should cache the preflight response.                                  |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Deny Unauthorized Origins:** When `yes`, requests from unauthorized origins are denied with an error code.                       |

!!! tip "Optimizing Preflight Requests"
    The `CORS_MAX_AGE` setting determines how long browsers will cache the results of a preflight request. Setting this to a higher value (like the default 86400 seconds/24 hours) reduces the number of preflight requests, improving performance for frequently accessed resources.

!!! warning "Security Considerations"
    Be cautious when setting `CORS_ALLOW_ORIGIN` to `*` (all origins) or `CORS_ALLOW_CREDENTIALS` to `yes` because these configurations may introduce security risks if not properly managed. It's generally safer to explicitly list trusted origins and limit the allowed methods and headers.

**: Allows requests from either `https://www.example1.com` or `https://www.example2.com`.
- **`^https?://www\.example\.com# CORS Plugin

The CORS plugin enables Cross-Origin Resource Sharing for your website, allowing controlled access to your resources from different domains. This feature helps you safely share your content with trusted third-party websites while maintaining security by explicitly defining which origins, methods, and headers are permitted.

**How it works:**

1. When a browser makes a cross-origin request to your website, it first sends a preflight request with the `OPTIONS` method.
2. BunkerWeb checks if the requesting origin is permitted based on your configuration.
3. If allowed, BunkerWeb responds with the appropriate CORS headers that define what the requesting site can do.
4. For non-permitted origins, the request can be either completely denied or served without CORS headers.
5. Additional cross-origin policies, such as [COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Embedder-Policy), [COOP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Opener-Policy), and [CORP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cross-Origin-Resource-Policy), can be configured to further enhance security.

## How to Use

Follow these steps to configure and use the CORS feature:

1. **Enable the feature:** The CORS feature is disabled by default. Set the `USE_CORS` setting to `yes` to enable it.
2. **Configure allowed origins:** Specify which domains can access your resources using the `CORS_ALLOW_ORIGIN` setting.
3. **Set permitted methods:** Define which HTTP methods are allowed for cross-origin requests with `CORS_ALLOW_METHODS`.
4. **Configure allowed headers:** Specify which headers can be used in requests with `CORS_ALLOW_HEADERS`.
5. **Control credentials:** Decide whether cross-origin requests can include credentials using `CORS_ALLOW_CREDENTIALS`.

## Configuration Settings

| Setting                        | Default                                                                              | Context   | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | no       | **Enable CORS:** Set to `yes` to enable Cross-Origin Resource Sharing.                                                             |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | no       | **Allowed Origins:** PCRE regular expression representing allowed origins; use `*` for any origin, or `self` for same-origin only. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | no       | **Allowed Methods:** HTTP methods that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | no       | **Allowed Headers:** HTTP headers that can be used in cross-origin requests.                                                       |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | no       | **Allow Credentials:** Set to `yes` to allow credentials (cookies, HTTP authentication) in CORS requests.                          |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | no       | **Exposed Headers:** HTTP headers that browsers are permitted to access from cross-origin responses.                               |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | no       | **Cross-Origin-Opener-Policy:** Controls communication between browsing contexts.                                                  |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | no       | **Cross-Origin-Embedder-Policy:** Controls whether a document can load resources from other origins.                               |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | no       | **Cross-Origin-Resource-Policy:** Controls which websites can embed your resources.                                                |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | no       | **Preflight Cache Duration:** How long (in seconds) browsers should cache the preflight response.                                  |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | no       | **Deny Unauthorized Origins:** When `yes`, requests from unauthorized origins are denied with an error code.                       |

!!! tip "Optimizing Preflight Requests"
    The `CORS_MAX_AGE` setting determines how long browsers will cache the results of a preflight request. Setting this to a higher value (like the default 86400 seconds/24 hours) reduces the number of preflight requests, improving performance for frequently accessed resources.

!!! warning "Security Considerations"
    Be cautious when setting `CORS_ALLOW_ORIGIN` to `*` (all origins) or `CORS_ALLOW_CREDENTIALS` to `yes` because these configurations may introduce security risks if not properly managed. It's generally safer to explicitly list trusted origins and limit the allowed methods and headers.

**: Allows requests from both `https://www.example.com` and `http://www.example.com`.

=== "Basic Configuration"

    A simple configuration allowing cross-origin requests from the same domain:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "self"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Public API Configuration"

    Configuration for a public API that needs to be accessible from any origin:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "*"
    CORS_ALLOW_METHODS: "GET, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, X-API-Key"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "3600"
    CORS_DENY_REQUEST: "no"
    ```

=== "Multiple Trusted Domains"

    Configuration for allowing multiple specific domains with a single PCRE regular expression pattern:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(app|api|dashboard)\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Requested-With"
    CORS_ALLOW_CREDENTIALS: "yes"
    CORS_EXPOSE_HEADERS: "Content-Length, Content-Range, X-RateLimit-Remaining"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Subdomain Wildcard"

    Configuration allowing all subdomains of a primary domain using a PCRE regular expression pattern:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://.*\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Multiple Domain Patterns"

    Configuration allowing requests from multiple domain patterns with alternation:

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(.*\\.example\\.com|.*\\.trusted-partner\\.org|api\\.third-party\\.net)$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Custom-Header"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```
