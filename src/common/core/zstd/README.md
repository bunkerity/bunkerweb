The Zstandard plugin compresses HTTP responses using the Zstandard (zstd) algorithm. It reduces bandwidth usage for clients that advertise `Accept-Encoding: zstd`.

### How to Use

1. Enable compression with `USE_ZSTD=yes` (disabled by default).
2. Choose MIME types with `ZSTD_TYPES` and a minimum response size with `ZSTD_MIN_LENGTH`.
3. Set `ZSTD_COMP_LEVEL` between `1` (fastest) and `19` (highest supported compression). The default is `3`.

Clients that support zstd receive `Content-Encoding: zstd` and `Vary: Accept-Encoding`. Clients without zstd support, including those sending `zstd;q=0`, can use Brotli or gzip when those plugins are enabled; otherwise they receive uncompressed responses.

When several compression plugins are enabled, the server preference is zstd, then Brotli, then gzip. Each coding honors its own `q=0`; positive weights are not compared across compression plugins.

### Configuration Settings

| Setting | Default | Context | Multiple | Description |
| ------- | ------- | ------- | -------- | ----------- |
| `USE_ZSTD` | `no` | multisite | no | Enable Zstandard response compression. |
| `ZSTD_TYPES` | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | no | MIME types to compress, in addition to `text/html` which is always included. |
| `ZSTD_MIN_LENGTH` | `1000` | multisite | no | Minimum response size in bytes. Responses of unknown length may also be compressed. |
| `ZSTD_COMP_LEVEL` | `3` | multisite | no | Compression level from `1` to `19`. Higher levels use more CPU and memory. |

!!! tip "Compression Level"
    Start with level `3`. Higher levels increase per-request CPU and memory usage; keep capacity for concurrent requests. Levels are limited to `19` to stay within the 8 MB zstd window limit for HTTP.

!!! warning "Sensitive Responses"
    Compression can expose secrets through response-size differences when a response contains both secrets and attacker-controlled input. Disable compression for sensitive services or address this risk in the application. `text/html` is always eligible when zstd is enabled, even if omitted from `ZSTD_TYPES`.

!!! info "Upstream Compression"
    Responses already compressed by the upstream are not compressed again. The inject plugin needs an uncompressed upstream response to modify HTML; configure the upstream accordingly when using both features.

### Example Configuration

Enable zstd with Brotli and gzip fallback:

```yaml
USE_ZSTD: "yes"
ZSTD_MIN_LENGTH: "1000"
ZSTD_COMP_LEVEL: "3"
USE_BROTLI: "yes"
USE_GZIP: "yes"
```
