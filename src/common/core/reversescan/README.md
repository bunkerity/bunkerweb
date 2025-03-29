The Reverse Scan plugin robustly protects against proxy bypass attempts by scanning clients' ports to detect whether they are running proxy servers or other network services. This feature helps identify and block potential threats from clients that may be attempting to hide their true identity or origin, thereby enhancing your website's security posture.

**How it works:**

1. When a client connects to your server, BunkerWeb attempts to scan specific ports on the client's IP address.
2. The plugin checks if any common proxy ports (such as 80, 443, 8080, etc.) are open on the client side.
3. If open ports are detected, indicating that the client may be running a proxy server, the connection is denied.
4. This adds an extra layer of security against automated tools, bots, and malicious users attempting to mask their identity.

!!! success "Key benefits"

      1. **Enhanced Security:** Identifies clients potentially running proxy servers that could be used for malicious purposes.
      2. **Proxy Detection:** Helps detect and block clients attempting to hide their true identity.
      3. **Configurable Settings:** Customize which ports to scan based on your specific security requirements.
      4. **Performance Optimized:** Intelligent scanning with configurable timeouts to minimize impact on legitimate users.
      5. **Seamless Integration:** Works transparently with your existing security layers.

### How to Use

Follow these steps to configure and use the Reverse Scan feature:

1. **Enable the feature:** Set the `USE_REVERSE_SCAN` setting to `yes` to enable client port scanning.
2. **Configure ports to scan:** Customize the `REVERSE_SCAN_PORTS` setting to specify which client ports should be checked.
3. **Set scan timeout:** Adjust the `REVERSE_SCAN_TIMEOUT` to balance thorough scanning with performance.
4. **Monitor scan activity:** Check logs and the [web UI](web-ui.md) to review scan results and potential security incidents.

### Configuration Settings

| Setting                | Default                    | Context   | Multiple | Description                                                                   |
| ---------------------- | -------------------------- | --------- | -------- | ----------------------------------------------------------------------------- |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | no       | **Enable Reverse Scan:** Set to `yes` to enable scanning of clients ports.    |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | no       | **Ports to Scan:** Space-separated list of ports to check on the client side. |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | no       | **Scan Timeout:** Maximum time in milliseconds allowed for scanning a port.   |

!!! warning "Performance Considerations"
    Scanning multiple ports can add latency to client connections. Use an appropriate timeout value and limit the number of ports scanned to maintain good performance.

!!! info "Common Proxy Ports"
    The default configuration includes common ports used by proxy servers (80, 443, 8080, 3128) and SSH (22). You may want to customize this list based on your threat model.

### Example Configurations

=== "Basic Configuration"

    A simple configuration for enabling client port scanning:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Comprehensive Scanning"

    A more thorough configuration that checks additional ports:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Performance-Optimized Configuration"

    Configuration tuned for better performance by checking fewer ports with lower timeout:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "High-Security Configuration"

    Configuration focused on maximum security with extended scanning:

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```
