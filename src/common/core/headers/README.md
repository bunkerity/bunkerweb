The Headers plugin enables comprehensive management of HTTP headers sent to clients, enhancing both security and functionality of your website. This feature allows you to control which headers are sent, removed, or preserved from upstream servers, helping you implement security best practices like Content Security Policy, prevent information leakage, and set cookie security flags.

**Here's how the Headers feature works:**

1. When a client requests content from your website, BunkerWeb processes the response headers.
2. Security headers like `Strict-Transport-Security`, `Content-Security-Policy`, and `X-Frame-Options` are applied according to your configuration.
3. Custom headers can be added to provide additional information or functionality to clients.
4. Unwanted headers that might leak server information are automatically removed.
5. Cookies are modified to include appropriate security flags based on your settings.
6. Headers from upstream servers can be selectively preserved when needed.

### How to Use

Follow these steps to configure and use the Headers feature:

1. **Configure security headers:** Set values for common security headers like `Strict-Transport-Security`, `Content-Security-Policy`, and `X-Frame-Options`.
2. **Add custom headers:** Define any custom headers you want to add to responses using the `CUSTOM_HEADER` setting.
3. **Remove information leakage:** Use `REMOVE_HEADERS` to specify headers that should not be sent to clients.
4. **Set cookie security:** Configure cookie flags to enhance security with settings like `HttpOnly`, `SameSite`, and `Secure`.
5. **Preserve upstream headers:** If needed, specify which headers from upstream servers should be preserved using `KEEP_UPSTREAM_HEADERS`.

### Configuration Settings

| Setting                               | Default                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Context   | Multiple | Description                                                                                                         |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `CUSTOM_HEADER`                       |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | multisite | yes      | **Custom Header:** Add custom headers to responses in the format `HeaderName: HeaderValue`.                         |
| `REMOVE_HEADERS`                      | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Remove Headers:** List of headers to remove from responses, separated by spaces.                                  |
| `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | multisite | no       | **Keep Upstream Headers:** Headers to preserve from upstream servers, separated by spaces (or `*` for all).         |
| `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | multisite | no       | **HSTS:** Value for the Strict-Transport-Security header to enforce HTTPS connections.                              |
| `COOKIE_FLAGS`                        | `* HttpOnly SameSite=Lax`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | multisite | yes      | **Cookie Flags:** Flags automatically added to cookies (using nginx_cookie_flag_module format).                     |
| `COOKIE_AUTO_SECURE_FLAG`             | `yes`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | multisite | no       | **Auto Secure Flag:** When set to `yes`, automatically adds the Secure flag to all cookies on HTTPS connections.    |
| `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | multisite | no       | **CSP:** Value for the Content-Security-Policy header to control resource loading.                                  |
| `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **CSP Report Mode:** When `yes`, sends violations as reports instead of blocking them.                              |
| `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Referrer Policy:** Controls how much referrer information is included with requests.                              |
| `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=(), interest-cohort=()` | multisite | no       | **Permissions Policy:** Controls which browser features and APIs can be used in your site.                          |
| `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | multisite | no       | **X-Frame-Options:** Controls whether your site can be embedded in frames (helps prevent clickjacking).             |
| `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | multisite | no       | **X-Content-Type-Options:** Prevents browsers from MIME-sniffing a response away from its declared content type.    |
| `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | multisite | no       | **X-DNS-Prefetch-Control:** Controls DNS prefetching, a feature by which browsers proactively resolve domain names. |

!!! tip "Security Headers"
    The default header values follow security best practices and are suitable for most websites. These headers help protect against various attacks including XSS, clickjacking, and information leakage. Mozilla's [Observatory](https://observatory.mozilla.org/) is a great tool to check your site's security headers.

!!! info "Content Security Policy"
    Content-Security-Policy (CSP) is a powerful defense against content injection attacks. The default policy blocks inline scripts and restricts frame embedding, but you may need to customize it based on your site's requirements. Consider starting with CSP Report-Only mode (`CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"`) to identify needed changes before enforcing the policy.

!!! warning "Custom Headers"
    When adding custom headers, be aware that certain headers might have security implications. Custom headers should follow the format `HeaderName: HeaderValue` and be added individually using the `CUSTOM_HEADER` setting.

### Example Configurations

=== "Basic Security Headers"

    A standard configuration with essential security headers:

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "Enhanced Cookie Security"

    Configuration with robust cookie security settings:

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "Custom Headers for API"

    Configuration for an API service with custom headers:

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "Content Security Policy - Reporting Mode"

    Configuration to test CSP without breaking functionality:

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```
