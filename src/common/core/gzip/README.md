The GZIP plugin enhances website performance by compressing HTTP responses using the gzip algorithm. This feature helps reduce bandwidth usage and improve page load times by compressing web content before it's sent to the client's browser, resulting in faster content delivery and improved user experience.

**Here's how the GZIP feature works:**

1. When a client requests content from your website, BunkerWeb checks if the client supports gzip compression.
2. If supported, BunkerWeb compresses the response using the gzip algorithm at your configured compression level.
3. The compressed content is sent to the client with appropriate headers indicating gzip compression.
4. The client's browser decompresses the content before rendering it to the user.
5. Both bandwidth usage and page load times are reduced, improving overall site performance and user experience.

### How to Use

Follow these steps to configure and use the GZIP compression feature:

1. **Enable the feature:** The GZIP feature is disabled by default. Enable it by setting the `USE_GZIP` setting to `yes`.
2. **Configure MIME types:** Specify which content types should be compressed using the `GZIP_TYPES` setting.
3. **Set minimum size:** Define the minimum response size for compression with `GZIP_MIN_LENGTH` to avoid compressing tiny files.
4. **Choose compression level:** Select your preferred balance between speed and compression ratio with `GZIP_COMP_LEVEL`.
5. **Configure proxied settings:** Determine which proxied requests should be compressed using the `GZIP_PROXIED` setting.

### Configuration Settings

| Setting           | Default                                                                                                                                                                                                                                                                                                                                                                                                                          | Context   | Multiple | Description                                                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Enable GZIP:** Set to `yes` to enable GZIP compression.                                                                        |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **MIME Types:** List of content types that will be compressed with gzip.                                                         |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Minimum Size:** The minimum response size (in bytes) for GZIP compression to be applied.                                       |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Compression Level:** Level of compression from 1 (minimum compression) to 9 (maximum compression). Higher values use more CPU. |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | no       | **Proxied Requests:** Specifies which proxied requests should be compressed based on response headers.                           |

!!! tip "Optimizing Compression Level"
    The default compression level (5) offers a good balance between compression ratio and CPU usage. For static content or when server CPU resources are plentiful, consider increasing to 7-9 for maximum compression. For dynamic content or when CPU resources are limited, you might want to use 1-3 for faster compression with reasonable size reduction.

!!! info "Browser Support"
    GZIP is supported by all modern browsers and has been the standard compression method for HTTP responses for many years, ensuring excellent compatibility across devices and browsers.

!!! warning "Compression vs. CPU Usage"
    While GZIP compression reduces bandwidth and improves load times, higher compression levels consume more CPU resources. For high-traffic sites, find the right balance between compression efficiency and server performance.

### Example Configurations

=== "Basic Configuration"

    A standard configuration that enables GZIP with default settings:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Maximum Compression"

    Configuration optimized for maximum compression savings:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Balanced Performance"

    Configuration that balances compression ratio with CPU usage:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Proxied Content Focus"

    Configuration that focuses on properly handling compression for proxied content:

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```
