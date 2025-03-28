Headers play a crucial role in HTTP security. The Headers plugin provides robust management of both standard and custom HTTP headers—enhancing security and functionality. It dynamically applies security measures, such as [HSTS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security), [CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy) (including a reporting mode), and custom header injection, while preventing information leakage.

**How it works**

1. When a client requests content from your website, BunkerWeb processes the response headers.
2. Security headers are applied in accordance with your configuration.
3. Custom headers can be added to provide additional information or functionality to clients.
4. Unwanted headers that might reveal server information are automatically removed.
5. Cookies are modified to include appropriate security flags based on your settings.
6. Headers from upstream servers can be selectively preserved when needed.

### How to Use

Follow these steps to configure and use the Headers feature:

1. **Configure security headers:** Set values for common headers.
2. **Add custom headers:** Define any custom headers using the `CUSTOM_HEADER` setting.
3. **Remove unwanted headers:** Use `REMOVE_HEADERS` to ensure headers that could expose server details are stripped out.
4. **Set cookie security:** Enable robust cookie security by configuring `COOKIE_FLAGS` and setting `COOKIE_AUTO_SECURE_FLAG` to `yes` so that the Secure flag is automatically added on HTTPS connections.
5. **Preserve upstream headers:** Specify which upstream headers to retain by using `KEEP_UPSTREAM_HEADERS`.
6. **Leverage conditional header application:** If you wish to test policies without disruption, enable [CSP Report-Only](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) mode via `CONTENT_SECURITY_POLICY_REPORT_ONLY`.

### Configuration Guide

=== "Security Headers"

    **Overview**

    Security headers enforce secure communication, restrict resource loading, and prevent attacks like clickjacking and injection. Properly configured headers create a robust defensive layer for your website.

    !!! success "Benefits of Security Headers"
        - **HSTS:** Ensures all connections are encrypted, protecting against protocol downgrade attacks.
        - **CSP:** Prevents malicious scripts from executing, reducing the risk of XSS attacks.
        - **X-Frame-Options:** Blocks clickjacking attempts by controlling iframe embedding.
        - **Referrer Policy:** Limits sensitive information leakage through referrer headers.

    | Setting                               | Default                                                                                             | Context   | Multiple | Description                                                                                                                  |
    | ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
    | `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | no       | **HSTS:** Enforces secure HTTPS connections, reducing risks of man-in-the-middle attacks.                                    |
    | `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | no       | **CSP:** Restricts resource loading to trusted sources, mitigating cross-site scripting and data injection attacks.          |
    | `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | no       | **CSP Report Mode:** Reports violations without blocking content, helping in testing security policies while capturing logs. |
    | `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | no       | **X-Frame-Options:** Prevents clickjacking by controlling whether your site can be framed.                                   |
    | `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | no       | **X-Content-Type-Options:** Prevents browsers from MIME-sniffing, protecting against drive-by download attacks.              |
    | `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | no       | **X-DNS-Prefetch-Control:** Regulates DNS prefetching to reduce unintentional network requests and enhance privacy.          |
    | `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | no       | **Referrer Policy:** Controls the amount of referrer information sent, safeguarding user privacy.                            |
    | `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | no       | **Permissions Policy:** Restricts browser feature access, reducing potential attack vectors.                                 |
    | `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | no       | **Keep Headers:** Preserves selected upstream headers, aiding legacy integration while maintaining security.                 |

    !!! tip "Best Practices"
        - Regularly review and update your security headers to align with evolving security standards.
        - Use tools like [Mozilla Observatory](https://observatory.mozilla.org/) to validate your header configuration.
        - Test CSP in `Report-Only` mode before enforcing it to avoid breaking functionality.

=== "Cookie Settings"

    **Overview**

    Proper cookie settings ensure secure user sessions by preventing hijacking, fixation, and cross-site scripting. Secure cookies maintain session integrity over HTTPS and enhance overall user data protection.

    !!! success "Benefits of Secure Cookies"
        - **HttpOnly Flag:** Prevents client-side scripts from accessing cookies, mitigating XSS risks.
        - **SameSite Flag:** Reduces CSRF attacks by restricting cross-origin cookie usage.
        - **Secure Flag:** Ensures cookies are transmitted only over encrypted HTTPS connections.

    | Setting                   | Default                   | Context   | Multiple | Description                                                                                                                                            |
    | ------------------------- | ------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | yes      | **Cookie Flags:** Automatically adds security flags such as HttpOnly and SameSite, protecting cookies from client-side script access and CSRF attacks. |
    | `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | no       | **Auto Secure Flag:** Ensures cookies are only sent over secure HTTPS connections by appending the Secure flag automatically.                          |

    !!! tip "Best Practices"
        - Use `SameSite=Strict` for sensitive cookies to prevent cross-origin access.
        - Regularly audit your cookie settings to ensure compliance with security and privacy regulations.
        - Avoid setting cookies without the Secure flag in production environments.

=== "Custom Headers"

    **Overview**

    Custom headers allow you to add specific HTTP headers to meet application or performance requirements. They offer flexibility but must be carefully configured to avoid exposing sensitive server details.

    !!! success "Benefits of Custom Headers"
        - Enhance security by removing unnecessary headers that may leak server details.
        - Add application-specific headers to improve functionality or debugging.

    | Setting          | Default                                                                              | Context   | Multiple | Description                                                                                                                                                 |
    | ---------------- | ------------------------------------------------------------------------------------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `CUSTOM_HEADER`  |                                                                                      | multisite | yes      | **Custom Header:** Provides a means to add user-defined headers in the format HeaderName: HeaderValue for specialized security or performance enhancements. |
    | `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | no       | **Remove Headers:** Specifies headers to remove, decreasing the chance of exposing internal server details and known vulnerabilities.                       |

    !!! warning "Security Considerations"
        - Avoid exposing sensitive information through custom headers.
        - Regularly review and update custom headers to align with your application's requirements.

    !!! tip "Best Practices"
        - Use `REMOVE_HEADERS` to strip out headers like `Server` and `X-Powered-By` to reduce fingerprinting risks.
        - Test custom headers in a staging environment before deploying them to production.

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
