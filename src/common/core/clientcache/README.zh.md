客户端缓存插件通过控制浏览器如何缓存静态内容来优化网站性能。它通过指示浏览器在本地存储和重用静态资产（例如图像、CSS 和 JavaScript 文件），而不是在每次页面访问时都请求它们，从而减少了带宽使用量，降低了服务器负载，并缩短了页面加载时间。

**工作原理：**

1.  启用后，BunkerWeb 会向静态文件的响应中添加 Cache-Control 标头。
2.  这些标头会告诉浏览器应在本地缓存内容多长时间。
3.  对于具有指定扩展名的文件（例如图像、CSS、JavaScript），BunkerWeb 会应用配置的缓存策略。
4.  可选的 ETag 支持提供了一个额外的验证机制，以确定缓存的内容是否仍然是新鲜的。
5.  当访问者返回您的网站时，他们的浏览器可以使用本地缓存的文件，而不是再次下载它们，从而缩短了页面加载时间。

### 如何使用

请按照以下步骤配置和使用客户端缓存功能：

1.  **启用该功能：** 客户端缓存功能默认禁用；将 `USE_CLIENT_CACHE` 设置为 `yes` 以启用它。
2.  **配置扩展名：** 使用 `CLIENT_CACHE_EXTENSIONS` 设置指定应缓存的文件类型。
3.  **设置缓存控制指令：** 使用 `CLIENT_CACHE_CONTROL` 设置自定义客户端应如何缓存内容。
4.  **配置 ETag 支持：** 使用 `CLIENT_CACHE_ETAG` 设置决定是否启用 ETag 来验证缓存新鲜度。
5.  **让 BunkerWeb 处理其余部分：** 配置完成后，缓存标头会自动应用于符合条件的响应。

### 配置设置

| 设置                      | 默认值                                                                    | 上下文    | 多个 | 描述                                                                      |
| ------------------------- | ------------------------------------------------------------------------- | --------- | ---- | ------------------------------------------------------------------------- |
| `USE_CLIENT_CACHE`        | `no`                                                                      | multisite | 否   | **启用客户端缓存：** 设置为 `yes` 以启用静态文件的客户端缓存。            |
| `CLIENT_CACHE_EXTENSIONS` | `jpg\|jpeg\|png\|bmp\|ico\|svg\|tif\|css\|js\|otf\|ttf\|eot\|woff\|woff2` | 全局      | 否   | **可缓存的扩展名：** 应由客户端缓存的文件扩展名列表（以管道符分隔）。     |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000`                                                | multisite | 否   | **Cache-Control 标头：** 用于控制缓存行为的 Cache-Control HTTP 标头的值。 |
| `CLIENT_CACHE_ETAG`       | `yes`                                                                     | multisite | 否   | **启用 ETags：** 设置为 `yes` 以发送静态资源的 HTTP ETag 标头。           |

!!! tip "优化缓存设置"
对于频繁更新的内容，请考虑使用较短的 max-age 值。对于很少更改的内容（如带版本的 JavaScript 库或徽标），请使用较长的缓存时间。默认值 15552000 秒（180 天）适用于大多数静态资产。

!!! info "浏览器行为"
不同的浏览器对缓存的实现略有不同，但所有现代浏览器都遵循标准的 Cache-Control 指令。ETags 提供了一个额外的验证机制，可以帮助浏览器确定缓存的内容是否仍然有效。

### 示例配置

=== "基本配置"

    一个简单的配置，为常见的静态资产启用缓存：

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"  # 1 天
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "积极缓存"

    为实现最大缓存而优化的配置，适用于静态内容更新不频繁的网站：

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"  # 1 年
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "混合内容策略"

    对于同时包含频繁更新和不频繁更新内容的网站，请考虑在您的应用程序中使用文件版本控制，并采用如下配置：

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"  # 1 周
    CLIENT_CACHE_ETAG: "yes"
    ```
