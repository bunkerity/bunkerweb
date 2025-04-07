The Brotli plugin enables efficient compression of HTTP responses using the Brotli algorithm. This feature helps reduce bandwidth usage and improve page load times by compressing web content before it is sent to the client's browser.

Compared to other compression methods like gzip, Brotli typically achieves higher compression ratios, resulting in smaller file sizes and faster content delivery.

**How it works:**

1. When a client requests content from your website, BunkerWeb checks if the client supports Brotli compression.
2. If supported, BunkerWeb compresses the response using the Brotli algorithm at your configured compression level.
3. The compressed content is sent to the client with appropriate headers indicating Brotli compression.
4. The client's browser decompresses the content before rendering it to the user.
5. Both bandwidth usage and page load times are reduced, improving overall user experience.

### How to Use

Follow these steps to configure and use the Brotli compression feature:

1. **Enable the feature:** The Brotli feature is disabled by default. Enable it by setting the `USE_BROTLI` setting to `yes`.
2. **Configure MIME types:** Specify which content types should be compressed using the `BROTLI_TYPES` setting.
3. **Set minimum size:** Define the minimum response size for compression with `BROTLI_MIN_LENGTH` to avoid compressing tiny files.
4. **Choose compression level:** Select your preferred balance between speed and compression ratio with `BROTLI_COMP_LEVEL`.
5. **Let BunkerWeb handle the rest:** Once configured, compression happens automatically for eligible responses.

### Configuration Settings

| Setting             | Default                                                                                                                                                                                                                                                                                                                                                                                                                          | Context   | Multiple | Description                                                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | no       | **Enable Brotli:** Set to `yes` to enable Brotli compression.                                                                |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no       | **MIME Types:** List of content types that will be compressed with Brotli.                                                   |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | no       | **Minimum Size:** The minimum response size (in bytes) for Brotli compression to be applied.                                 |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | no       | **Compression Level:** Level of compression from 0 (no compression) to 11 (maximum compression). Higher values use more CPU. |

!!! tip "Optimizing Compression Level"
    The default compression level (6) offers a good balance between compression ratio and CPU usage. For static content or when server CPU resources are plentiful, consider increasing to 9-11 for maximum compression. For dynamic content or when CPU resources are limited, you might want to use 4-5 for faster compression with reasonable size reduction.

!!! info "Browser Support"
    Brotli is supported by all modern browsers including Chrome, Firefox, Edge, Safari, and Opera. Older browsers will automatically receive uncompressed content, ensuring compatibility.

### Example Configurations

=== "Basic Configuration"

    A standard configuration that enables Brotli with default settings:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "Maximum Compression"

    Configuration optimized for maximum compression savings:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "Balanced Performance"

    Configuration that balances compression ratio with CPU usage:

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```
