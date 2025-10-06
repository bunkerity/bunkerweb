Brotli 插件使用 Brotli 算法实现对 HTTP 响应的高效压缩。此功能通过在将 Web 内容发送到客户端浏览器之前对其进行压缩，帮助减少带宽使用并缩短页面加载时间。

与其他压缩方法（如 gzip）相比，Brotli 通常能实现更高的压缩率，从而减小文件大小，加快内容交付速度。

**工作原理：**

1.  当客户端从您的网站请求内容时，BunkerWeb 会检查客户端是否支持 Brotli 压缩。
2.  如果支持，BunkerWeb 会在您配置的压缩级别下使用 Brotli 算法对响应进行压缩。
3.  压缩后的内容会连同指示 Brotli 压缩的适当标头一起发送给客户端。
4.  客户端的浏览器在向用户呈现内容之前会对其进行解压缩。
5.  带宽使用量和页面加载时间都得到了减少，从而改善了整体用户体验。

### 如何使用

请按照以下步骤配置和使用 Brotli 压缩功能：

1.  **启用该功能：** Brotli 功能默认禁用。通过将 `USE_BROTLI` 设置为 `yes` 来启用它。
2.  **配置 MIME 类型：** 使用 `BROTLI_TYPES` 设置指定应压缩的内容类型。
3.  **设置最小大小：** 使用 `BROTLI_MIN_LENGTH` 定义压缩的最小响应大小，以避免压缩过小的文件。
4.  **选择压缩级别：** 使用 `BROTLI_COMP_LEVEL` 选择您偏好的速度与压缩率之间的平衡。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，压缩会自动对符合条件的响应进行。

### 配置设置

| 设置                | 默认值                                                                                                                                                                                                                                                                                                                                                                                                                           | 上下文    | 多个 | 描述                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- | ---------------------------------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | 否   | **启用 Brotli：** 设置为 `yes` 以启用 Brotli 压缩。                                |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | 否   | **MIME 类型：** 将使用 Brotli 压缩的内容类型列表。                                 |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | 否   | **最小大小：** 应用 Brotli 压缩的最小响应大小（以字节为单位）。                    |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | 否   | **压缩级别：** 压缩级别从 0（不压缩）到 11（最大压缩）。较高的值会使用更多的 CPU。 |

!!! tip "优化压缩级别"
    默认的压缩级别 (6) 在压缩率和 CPU 使用率之间提供了良好的平衡。对于静态内容或服务器 CPU 资源充足的情况，可以考虑增加到 9-11 以获得最大压缩。对于动态内容或 CPU 资源有限的情况，您可能希望使用 4-5 以实现更快的压缩和合理的尺寸减小。

!!! info "浏览器支持"
    所有现代浏览器，包括 Chrome、Firefox、Edge、Safari 和 Opera，都支持 Brotli。旧版浏览器会自动接收未压缩的内容，以确保兼容性。

### 示例配置

=== "基本配置"

    一个使用默认设置启用 Brotli 的标准配置：

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "最大压缩"

    为实现最大压缩节省而优化的配置：

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "平衡性能"

    在压缩率和 CPU 使用率之间取得平衡的配置：

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```
