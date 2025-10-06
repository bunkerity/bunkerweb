PHP 插件为 BunkerWeb 提供了与 PHP-FPM 的无缝集成，从而为您的网站启用动态 PHP 处理。此功能支持在同一台机器上运行的本地 PHP-FPM 实例和远程 PHP-FPM 服务器，让您在配置 PHP 环境时拥有灵活性。

**工作原理：**

1.  当客户端从您的网站请求 PHP 文件时，BunkerWeb 会将请求路由到已配置的 PHP-FPM 实例。
2.  对于本地 PHP-FPM，BunkerWeb 通过 Unix 套接字文件与 PHP 解释器通信。
3.  对于远程 PHP-FPM，BunkerWeb 使用 FastCGI 协议将请求转发到指定的主机和端口。
4.  PHP-FPM 处理脚本并返回生成的内容给 BunkerWeb，然后由 BunkerWeb 将其交付给客户端。
5.  URL 重写会自动配置，以支持使用“美观 URL”的常见 PHP 框架和应用程序。

### 如何使用

请按照以下步骤配置和使用 PHP 功能：

1.  **选择您的 PHP-FPM 设置：** 决定您将使用本地还是远程 PHP-FPM 实例。
2.  **配置连接：** 对于本地 PHP，请指定套接字路径；对于远程 PHP，请提供主机名和端口。
3.  **设置文档根目录：** 使用适当的路径设置，配置包含您的 PHP 文件的根文件夹。
4.  **让 BunkerWeb 处理其余部分：** 配置完成后，BunkerWeb 会自动将 PHP 请求路由到您的 PHP-FPM 实例。

### 配置设置

| 设置              | 默认值 | 上下文    | 多选 | 描述                                                                          |
| ----------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
| `REMOTE_PHP`      |        | multisite | 否   | **远程 PHP 主机：** 远程 PHP-FPM 实例的主机名。留空以使用本地 PHP。           |
| `REMOTE_PHP_PATH` |        | multisite | 否   | **远程路径：** 远程 PHP-FPM 实例中包含文件的根文件夹。                        |
| `REMOTE_PHP_PORT` | `9000` | multisite | 否   | **远程端口：** 远程 PHP-FPM 实例的端口。                                      |
| `LOCAL_PHP`       |        | multisite | 否   | **本地 PHP 套接字：** PHP-FPM 套接字文件的路径。留空以使用远程 PHP-FPM 实例。 |
| `LOCAL_PHP_PATH`  |        | multisite | 否   | **本地路径：** 本地 PHP-FPM 实例中包含文件的根文件夹。                        |

!!! tip "本地与远程 PHP-FPM"
    选择最适合您基础架构的设置：

    -   **本地 PHP-FPM** 由于基于套接字的通信而提供更好的性能，并且在 PHP 与 BunkerWeb 在同一台机器上运行时是理想选择。
    -   **远程 PHP-FPM** 通过允许在单独的服务器上进行 PHP 处理，提供了更大的灵活性和可伸缩性。

!!! warning "路径配置"
    `REMOTE_PHP_PATH` 或 `LOCAL_PHP_PATH` 必须与存储 PHP 文件的实际文件系统路径匹配；否则，将发生“文件未找到”错误。

!!! info "URL 重写"
    PHP 插件会自动配置 URL 重写以支持现代 PHP 应用程序。对不存在的文件的请求将被定向到 `index.php`，原始请求 URI 将作为查询参数提供。

### 配置示例

=== "本地 PHP-FPM 配置"

    使用本地 PHP-FPM 实例的配置：

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "远程 PHP-FPM 配置"

    使用远程 PHP-FPM 实例的配置：

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "自定义端口配置"

    在非标准端口上使用 PHP-FPM 的配置：

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress 配置"

    为 WordPress 优化的配置：

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```
