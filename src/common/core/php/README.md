The PHP plugin provides seamless integration with PHP-FPM for BunkerWeb, enabling dynamic PHP processing for your websites. This feature supports both local PHP-FPM instances running on the same machine and remote PHP-FPM servers, giving you flexibility in how you configure your PHP environment.

**How it works:**

1. When a client requests a PHP file from your website, BunkerWeb routes the request to the configured PHP-FPM instance.
2. For local PHP-FPM, BunkerWeb communicates with the PHP interpreter through a Unix socket file.
3. For remote PHP-FPM, BunkerWeb forwards requests to the specified host and port using FastCGI protocol.
4. PHP-FPM processes the script and returns the generated content to BunkerWeb, which then delivers it to the client.
5. URL rewriting is automatically configured to support common PHP frameworks and applications that use "pretty URLs".

### How to Use

Follow these steps to configure and use the PHP feature:

1. **Choose your PHP-FPM setup:** Decide whether you'll use a local or remote PHP-FPM instance.
2. **Configure the connection:** For local PHP, specify the socket path; for remote PHP, provide the hostname and port.
3. **Set the document root:** Configure the root folder that contains your PHP files using the appropriate path setting.
4. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb automatically routes PHP requests to your PHP-FPM instance.

### Configuration Settings

| Setting           | Default | Context   | Multiple | Description                                                                                 |
| ----------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------- |
| `REMOTE_PHP`      |         | multisite | no       | **Remote PHP Host:** Hostname of the remote PHP-FPM instance. Leave empty to use local PHP. |
| `REMOTE_PHP_PATH` |         | multisite | no       | **Remote Path:** Root folder containing files in the remote PHP-FPM instance.               |
| `REMOTE_PHP_PORT` | `9000`  | multisite | no       | **Remote Port:** Port of the remote PHP-FPM instance.                                       |
| `LOCAL_PHP`       |         | multisite | no       | **Local PHP Socket:** Path to the PHP-FPM socket file. Leave empty to use remote PHP.       |
| `LOCAL_PHP_PATH`  |         | multisite | no       | **Local Path:** Root folder containing files in the local PHP-FPM instance.                 |

!!! tip "Local vs. Remote PHP-FPM"
    Choose the setup that best fits your infrastructure:

    - **Local PHP-FPM** offers better performance due to socket-based communication and is ideal when PHP runs on the same machine as BunkerWeb.
    - **Remote PHP-FPM** provides more flexibility and scalability by allowing PHP processing to occur on separate servers.

!!! warning "Path Configuration"
    The `REMOTE_PHP_PATH` or `LOCAL_PHP_PATH` must match the actual filesystem path where your PHP files are stored. Incorrect paths will result in "File not found" errors.

!!! info "URL Rewriting"
    The PHP plugin automatically configures URL rewriting to support modern PHP applications. Requests for non-existent files will be directed to `index.php` with the original request URI available as a query parameter.

### Example Configurations

=== "Local PHP-FPM Configuration"

    Configuration for using a local PHP-FPM instance:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "Remote PHP-FPM Configuration"

    Configuration for using a remote PHP-FPM instance:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Custom Port Configuration"

    Configuration for using PHP-FPM on a non-standard port:

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress Configuration"

    Configuration optimized for WordPress:

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```
