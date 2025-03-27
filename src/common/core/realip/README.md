The Real IP plugin allows BunkerWeb to accurately identify the true IP address of visitors when operating behind reverse proxies, load balancers, or CDNs. This is essential for properly applying security rules, rate limiting, and logging, as without it, all requests would appear to come from your proxy's IP rather than the actual client's IP.

**How it works:**

1. When enabled, BunkerWeb examines incoming requests for specific headers (like [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)) that contain the client's original IP address.
2. BunkerWeb checks if the connecting IP is in your trusted proxy list (`REAL_IP_FROM`), ensuring only legitimate proxies can pass client IPs.
3. The original client IP is extracted from the specified header (`REAL_IP_HEADER`) and used for all security evaluations and logging.
4. For recursive IP chains, BunkerWeb can trace through multiple proxy hops to find the originating client IP.
5. Additionally, PROXY protocol support can be enabled to receive client IPs directly from compatible proxies like [HAProxy](https://www.haproxy.org/).
6. Trusted proxy IP lists can be automatically downloaded and updated from external sources via URLs.

### How to Use

Follow these steps to configure and use the Real IP feature:

1. **Enable the feature:** Set the `USE_REAL_IP` setting to `yes` to enable real IP detection.
2. **Define trusted proxies:** List the IP addresses or networks of your trusted proxies using the `REAL_IP_FROM` setting.
3. **Specify the header:** Configure which header contains the real IP using the `REAL_IP_HEADER` setting.
4. **Configure recursion:** Decide whether to trace IP chains recursively with the `REAL_IP_RECURSIVE` setting.
5. **Optional URL sources:** Set up automatic downloads of trusted proxy lists with `REAL_IP_FROM_URLS`.
6. **PROXY protocol:** For direct proxy communication, enable with `USE_PROXY_PROTOCOL` if your upstream supports it.

!!! danger "PROXY Protocol Warning"
    Enabling `USE_PROXY_PROTOCOL` without properly configuring your upstream proxy to send PROXY protocol headers will **break your application**. Only enable this setting if you are certain that your upstream proxy is properly configured to send PROXY protocol information. If your proxy is not sending PROXY protocol headers, all connections to BunkerWeb will fail with protocol errors.

### Configuration Settings

| Setting              | Default                                   | Context   | Multiple | Description                                                                                                           |
| -------------------- | ----------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | no       | **Enable Real IP:** Set to `yes` to enable retrieving client's real IP from headers or PROXY protocol.                |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | no       | **Trusted Proxies:** List of trusted IP addresses or networks where proxied requests come from, separated by spaces.  |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | no       | **Real IP Header:** HTTP header containing the real IP or special value `proxy_protocol` for PROXY protocol.          |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | no       | **Recursive Search:** When set to `yes`, performs a recursive search in header containing multiple IP addresses.      |
| `REAL_IP_FROM_URLS`  |                                           | multisite | no       | **IP List URLs:** URLs containing trusted proxy IPs/networks to download, separated by spaces. Supports file:// URLs. |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | no       | **PROXY Protocol:** Set to `yes` to enable PROXY protocol support for direct proxy-to-BunkerWeb communication.        |

!!! tip "Cloud Provider Networks"
    If you're using a cloud provider like AWS, GCP, or Azure, consider adding their load balancer IP ranges to your `REAL_IP_FROM` setting to ensure proper client IP identification.

!!! danger "Security Considerations"
    Only include trusted proxy IPs in your configuration. Adding untrusted sources could allow IP spoofing attacks, where malicious actors could forge the client IP by manipulating headers.

!!! info "Multiple IP Addresses"
    When `REAL_IP_RECURSIVE` is enabled and a header contains multiple IPs (e.g., `X-Forwarded-For: client, proxy1, proxy2`), BunkerWeb will identify the leftmost IP not in your trusted proxy list as the client IP.

### Example Configurations

=== "Basic Configuration"

    A simple configuration for a site behind a reverse proxy:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Cloud Load Balancer"

    Configuration for a site behind a cloud load balancer:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "PROXY Protocol"

    Configuration using PROXY protocol with a compatible load balancer:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "Multiple Proxy Sources with URLs"

    Advanced configuration with automatically updated proxy IP lists:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "CDN Configuration"

    Configuration for a website behind a CDN:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Example for Cloudflare
    REAL_IP_RECURSIVE: "no"  # Not needed with single IP headers
    ```

=== "Behind Cloudflare"

    Configuration for a website behind Cloudflare:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # We only trust Cloudflare IPs
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # Download Cloudflare IPs automatically
    REAL_IP_HEADER: "CF-Connecting-IP"  # Cloudflare header for client IP
    REAL_IP_RECURSIVE: "yes"
    ```
