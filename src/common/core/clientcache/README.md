The Client Cache plugin optimizes website performance by controlling how browsers cache your static content. This feature helps reduce bandwidth usage, server load, and improves page load times by instructing client browsers to store and reuse static assets like images, CSS, and JavaScript files locally instead of requesting them on every page visit.

**How it works:**

1. When enabled, BunkerWeb adds Cache-Control headers to responses for static files.
2. These headers tell browsers how long they should cache the content locally.
3. For files with specified extensions (like images, CSS, JavaScript), BunkerWeb applies the configured caching policy.
4. Optional ETag support provides additional validation mechanisms to determine if cached content is still fresh.
5. When visitors return to your site, their browsers can use locally cached files instead of downloading them again, resulting in faster page loads.

### How to Use

Follow these steps to configure and use the Client Cache feature:

1. **Enable the feature:** The Client Cache feature is disabled by default. Set the `USE_CLIENT_CACHE` setting to `yes` to enable it.
2. **Configure file extensions:** Specify which file types should be cached using the `CLIENT_CACHE_EXTENSIONS` setting.
3. **Set cache control directives:** Customize how clients should cache content using the `CLIENT_CACHE_CONTROL` setting.
4. **Configure ETag support:** Decide whether to enable ETags for validating cache freshness with the `CLIENT_CACHE_ETAG` setting.
5. **Let BunkerWeb handle the rest:** Once configured, caching headers will be automatically applied to eligible responses.

### Configuration Settings

| Setting                   | Default                                                                   | Context   | Multiple | Description                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `USE_CLIENT_CACHE`        | `no`                                                                      | multisite | no       | **Enable Client Cache:** Set to `yes` to enable client-side caching of static files.                        |
| `CLIENT_CACHE_EXTENSIONS` | `jpg\|jpeg\|png\|bmp\|ico\|svg\|tif\|css\|js\|otf\|ttf\|eot\|woff\|woff2` | global    | no       | **Cacheable Extensions:** List of file extensions (separated by pipes) that should be cached by the client. |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000`                                                | multisite | no       | **Cache-Control Header:** Value for the Cache-Control HTTP header to control caching behavior.              |
| `CLIENT_CACHE_ETAG`       | `yes`                                                                     | multisite | no       | **Enable ETags:** Set to `yes` to send the HTTP ETag header for static resources.                           |

!!! tip "Optimizing Cache Settings"
    For frequently updated content, consider using shorter max-age values. For content that rarely changes (like versioned JavaScript libraries or logos), use longer cache times. The default value of 15552000 seconds (180 days) is appropriate for most static assets.

!!! info "Browser Behavior"
    Different browsers implement caching slightly differently, but all modern browsers honor standard Cache-Control directives. ETags provide an additional validation mechanism that helps browsers determine if cached content is still valid.

### Example Configurations

=== "Basic Configuration"

    A simple configuration that enables caching for common static assets:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 day
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Aggressive Caching"

    Configuration optimized for maximum caching, suitable for sites with infrequently updated static content:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 year
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Mixed Content Strategy"

    For sites with a mix of frequently and infrequently updated content, consider using file versioning in your application and a configuration like this:

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 week
    CLIENT_CACHE_ETAG: "yes"
    ```
