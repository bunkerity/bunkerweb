The Redirect plugin provides simple and efficient HTTP redirection capabilities for your BunkerWeb-protected websites. This feature enables you to easily redirect visitors from one URL to another, supporting both full-domain redirects, specific path redirects and path-preserving redirections.

**How it works:**

1. When a visitor accesses your website, BunkerWeb verifies whether a redirection is configured.
2. If enabled, BunkerWeb redirects the visitor to the specified destination URL.
3. You can configure whether to preserve the original request path (automatically appending it to the destination URL) or redirect to the exact destination URL.
4. The HTTP status code used for the redirection can be customized between permanent (301) and temporary (302) redirects.
5. This functionality is ideal for domain migrations, establishing canonical domains, or redirecting deprecated URLs.

### How to Use

Follow these steps to configure and use the Redirect feature:

1. **Set the source path:** Configure the path to redirect from using the `REDIRECT_FROM` setting (e.g. `/`, `/old-page`).
2. **Set the destination URL:** Configure the target URL where visitors should be redirected using the `REDIRECT_TO` setting.
3. **Choose redirection type:** Decide whether to preserve the original request path with the `REDIRECT_TO_REQUEST_URI` setting.
4. **Select status code:** Set the appropriate HTTP status code with the `REDIRECT_TO_STATUS_CODE` setting to indicate permanent or temporary redirection.
5. **Let BunkerWeb handle the rest:** Once configured, all requests to the site will be automatically redirected based on your settings.

### Configuration Settings

| Setting                   | Default | Context   | Multiple | Description                                                                                                         |
| ------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`     | multisite | yes      | **Path to redirect from:** The path that will be redirected.                                                        |
| `REDIRECT_TO`             |         | multisite | yes      | **Destination URL:** The target URL where visitors will be redirected. Leave empty to disable redirection.          |
| `REDIRECT_TO_REQUEST_URI` | `no`    | multisite | yes      | **Preserve Path:** When set to `yes`, appends the original request URI to the destination URL.                      |
| `REDIRECT_TO_STATUS_CODE` | `301`   | multisite | yes      | **HTTP Status Code:** The HTTP status code to use for redirection. Options: `301` (permanent) or `302` (temporary). |

!!! tip "Choosing the Right Status Code"
    - Use `301` (Moved Permanently) when the redirect is permanent, such as for domain migrations or establishing canonical URLs. This helps search engines update their indexes.
    - Use `302` (Found/Temporary Redirect) when the redirect is temporary or if you may want to reuse the original URL in the future.

!!! info "Path Preservation"
    When `REDIRECT_TO_REQUEST_URI` is set to `yes`, BunkerWeb preserves the original request path. For example, if a user visits `https://old-domain.com/blog/post-1` and you've set up a redirect to `https://new-domain.com`, they'll be redirected to `https://new-domain.com/blog/post-1`.

### Example Configurations

=== "Multiple Paths Redirect"

    A configuration that redirects multiple paths to different destinations:

    ```yaml
    # Redirect /blog to a new blog domain
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    # Redirect /shop to another domain
    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    # Redirect the rest of the site
    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Simple Domain Redirect"

    A configuration that redirects all visitors to a new domain:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Path-Preserving Redirect"

    A configuration that redirects visitors to a new domain while preserving the requested path:

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Temporary Redirect"

    A configuration for a temporary redirect to a maintenance site:

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Subdomain Consolidation"

    A configuration to redirect a subdomain to a specific path on the main domain:

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```
