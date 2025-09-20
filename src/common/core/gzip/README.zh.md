GZIP 插件通过使用 GZIP 算法压缩 HTTP 响应来增强网站性能。此功能通过在将 Web 内容发送到客户端浏览器之前对其进行压缩，减少了带宽使用并缩短了页面加载时间，从而实现了更快的交付和更好的用户体验。

### 工作原理

1.  当客户端从您的网站请求内容时，BunkerWeb 会检查客户端是否支持 GZIP 压缩。
2.  如果支持，BunkerWeb 会在您配置的压缩级别下使用 GZIP 算法对响应进行压缩。
3.  压缩后的内容会连同指示 GZIP 压缩的适当标头一起发送给客户端。
4.  客户端的浏览器在呈现内容之前会对其进行解压缩。
5.  带宽使用量和页面加载时间都得到了减少，从而增强了网站的整体性能和用户体验。

### 如何使用

请按照以下步骤配置和使用 GZIP 压缩功能：

1.  **启用该功能：** GZIP 功能默认禁用。通过将 `USE_GZIP` 设置为 `yes` 来启用它。
2.  **配置 MIME 类型：** 使用 `GZIP_TYPES` 设置指定应压缩的内容类型。
3.  **设置最小大小：** 使用 `GZIP_MIN_LENGTH` 设置定义压缩所需的最小响应大小，以避免压缩小文件。
4.  **选择一个压缩级别：** 使用 `GZIP_COMP_LEVEL` 设置在速度和压缩率之间选择您偏好的平衡。
5.  **配置代理请求：** 使用 `GZIP_PROXIED` 设置指定应压缩哪些代理请求。

### 配置设置

| 设置              | 默认值                                                                                                                                                                                                                                                                                                                                                                                                                           | 上下文    | 多个 | 描述                                                                                |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- | ----------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | 否   | **启用 GZIP：** 设置为 `yes` 以启用 GZIP 压缩。                                     |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | 否   | **MIME 类型：** 将使用 GZIP 压缩的内容类型列表。                                    |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | 否   | **最小大小：** 应用 GZIP 压缩的最小响应大小（以字节为单位）。                       |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | 否   | **压缩级别：** 压缩级别从 1（最小压缩）到 9（最大压缩）。较高的值会使用更多的 CPU。 |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | 否   | **代理请求：** 根据响应标头指定应压缩哪些代理请求。                                 |

!!! tip "优化压缩级别"
默认的压缩级别 (5) 在压缩率和 CPU 使用率之间提供了良好的平衡。对于静态内容或服务器 CPU 资源充足的情况，可以考虑增加到 7-9 以获得最大压缩。对于动态内容或 CPU 资源有限的情况，您可能希望使用 1-3 以实现更快的压缩和合理的尺寸减小。

!!! info "浏览器支持"
所有现代浏览器都支持 GZIP，并且多年来一直是 HTTP 响应的标准压缩方法，确保了在设备和浏览器之间具有出色的兼容性。

!!! warning "压缩与 CPU 使用率"
虽然 GZIP 压缩减少了带宽并缩短了加载时间，但更高的压缩级别会消耗更多的 CPU 资源。对于高流量的网站，请在压缩效率和服务器性能之间找到适当的平衡。

### 示例配置

=== "基本配置"

    一个使用默认设置启用 GZIP 的标准配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "最大压缩"

    为实现最大压缩节省而优化的配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "平衡性能"

    在压缩率和 CPU 使用率之间取得平衡的配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "代理内容焦点"

    专注于正确处理代理内容压缩的配置：

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```
