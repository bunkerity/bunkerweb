Zstandard 插件使用 Zstandard (zstd) 算法压缩 HTTP 响应。对于声明 `Accept-Encoding: zstd` 的客户端，它可以减少带宽使用量。

### 如何使用

1.  **启用压缩：** 将 `USE_ZSTD` 设置为 `yes`（默认禁用）。
2.  **配置 MIME 类型和最小大小：** 使用 `ZSTD_TYPES` 指定要压缩的内容类型，使用 `ZSTD_MIN_LENGTH` 指定最小响应大小。
3.  **设置压缩级别：** 将 `ZSTD_COMP_LEVEL` 设置在 `1`（最快）到 `19`（支持的最高压缩率）之间。默认值为 `3`。

支持 zstd 的客户端会收到 `Content-Encoding: zstd` 和 `Vary: Accept-Encoding`。不支持 zstd 的客户端（包括发送 `zstd;q=0` 的客户端）在启用 Brotli 或 gzip 插件时可以使用这两种压缩方式；否则将收到未压缩的响应。

当启用多个压缩插件时，服务器的优先顺序为 zstd、Brotli、gzip。每种编码各自遵循自己的 `q=0`；不同压缩插件之间不会比较正权重。

### 配置设置

| 设置              | 默认值                                                                                                                                                                                                                                                                                                                                                                                                                           | 上下文    | 多个 | 描述                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- | -------------------------------------------------------------------------- |
| `USE_ZSTD`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | 否   | **启用 Zstandard：** 启用 Zstandard 响应压缩。                             |
| `ZSTD_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | 否   | **MIME 类型：** 要压缩的 MIME 类型，`text/html` 始终包含在内。             |
| `ZSTD_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | 否   | **最小大小：** 最小响应大小（以字节为单位）。长度未知的响应也可能被压缩。  |
| `ZSTD_COMP_LEVEL` | `3`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | 否   | **压缩级别：** 压缩级别从 `1` 到 `19`。较高的级别会使用更多的 CPU 和内存。 |

!!! tip "压缩级别"
    建议从级别 `3` 开始。较高的级别会增加每个请求的 CPU 和内存使用量；请为并发请求保留足够的容量。级别上限为 `19`，以符合 HTTP 的 8 MB zstd 窗口限制。

!!! warning "敏感响应"
    当响应同时包含机密信息和攻击者可控的输入时，压缩可能通过响应大小的差异泄露机密信息。请对敏感服务禁用压缩，或在应用程序中解决此风险。启用 zstd 后，即使 `ZSTD_TYPES` 中省略了 `text/html`，它也始终可被压缩。

!!! info "上游压缩"
    上游已压缩的响应不会被再次压缩。inject 插件需要未压缩的上游响应才能修改 HTML；同时使用这两项功能时，请相应地配置上游。

### 示例配置

启用 zstd，并以 Brotli 和 gzip 作为回退：

```yaml
USE_ZSTD: "yes"
ZSTD_MIN_LENGTH: "1000"
ZSTD_COMP_LEVEL: "3"
USE_BROTLI: "yes"
USE_GZIP: "yes"
```
