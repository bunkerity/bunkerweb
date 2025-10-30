Real IP 插件可确保 BunkerWeb 即使在代理后面也能正确识别客户端的 IP 地址。这对于正确应用安全规则、速率限制和日志记录至关重要；没有它，所有请求都将看起来来自您的代理 IP，而不是客户端的实际 IP。

**工作原理：**

1.  启用后，BunkerWeb 会检查传入请求中是否包含特定标头（如 [`X-Forwarded-For`](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)），这些标头包含客户端的原始 IP 地址。
2.  BunkerWeb 会检查传入的 IP 是否在您的受信任代理列表 (`REAL_IP_FROM`) 中，确保只有合法的代理才能传递客户端 IP。
3.  从指定的标头 (`REAL_IP_HEADER`) 中提取原始客户端 IP，并用于所有安全评估和日志记录。
4.  对于递归 IP 链，BunkerWeb 可以追溯多个代理跃点以确定始发客户端 IP。
5.  此外，可以启用 [PROXY 协议](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) 支持，以直接从兼容的代理（如 [HAProxy](https://www.haproxy.org/)）接收客户端 IP。
6.  受信任的代理 IP 列表可以通过 URL 从外部源自动下载和更新。

### 如何使用

请按照以下步骤配置和使用 Real IP 功能：

1.  **启用该功能：** 将 `USE_REAL_IP` 设置为 `yes` 以启用真实 IP 检测。
2.  **定义受信任的代理：** 使用 `REAL_IP_FROM` 设置列出您受信任的代理的 IP 地址或网络。
3.  **指定标头：** 使用 `REAL_IP_HEADER` 设置配置哪个标头包含真实 IP。
4.  **配置递归：** 使用 `REAL_IP_RECURSIVE` 设置决定是否递归地追溯 IP 链。
5.  **可选的 URL 源：** 使用 `REAL_IP_FROM_URLS` 设置自动下载受信任的代理列表。
6.  **PROXY 协议：** 对于直接的代理通信，如果您的上游支持，请使用 `USE_PROXY_PROTOCOL` 启用。

!!! danger "PROXY 协议警告"
    在未正确配置您的上游代理以发送 PROXY 协议标头的情况下启用 `USE_PROXY_PROTOCOL` 将**破坏您的应用程序**。仅当您确定您的上游代理已正确配置为发送 PROXY 协议信息时，才启用此设置。如果您的代理未发送 PROXY 协议标头，所有到 BunkerWeb 的连接都将因协议错误而失败。

### 配置设置

| 设置                 | 默认值                                    | 上下文    | 多选 | 描述                                                                                     |
| -------------------- | ----------------------------------------- | --------- | ---- | ---------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | 否   | **启用真实 IP：** 设置为 `yes` 以启用从标头或 PROXY 协议中检索客户端的真实 IP。          |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | 否   | **受信任的代理：** 代理请求来源的受信任 IP 地址或网络列表，以空格分隔。                  |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | 否   | **真实 IP 标头：** 包含真实 IP 的 HTTP 标头或用于 PROXY 协议的特殊值 `proxy_protocol`。  |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | 否   | **递归搜索：** 设置为 `yes` 时，在包含多个 IP 地址的标头中执行递归搜索。                 |
| `REAL_IP_FROM_URLS`  |                                           | multisite | 否   | **IP 列表 URL：** 包含要下载的受信任代理 IP/网络的 URL，以空格分隔。支持 file:// URL。   |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | 否   | **PROXY 协议：** 设置为 `yes` 以启用 PROXY 协议支持，用于直接的代理到 BunkerWeb 的通信。 |

!!! tip "云提供商网络"
    如果您正在使用像 AWS、GCP 或 Azure 这样的云提供商，请考虑将其负载均衡器的 IP 范围添加到您的 `REAL_IP_FROM` 设置中，以确保正确的客户端 IP 识别。

!!! danger "安全注意事项"
    仅在您的配置中包含受信任的代理 IP。添加不受信任的源可能会允许 IP 欺骗攻击，恶意行为者可以通过操纵标头来伪造客户端 IP。

!!! info "多个 IP 地址"
    当 `REAL_IP_RECURSIVE` 启用并且标头包含多个 IP（例如，`X-Forwarded-For: client, proxy1, proxy2`）时，BunkerWeb 会将不在您受信任代理列表中的最左侧 IP 识别为客户端 IP。

### 配置示例

=== "基本配置"

    一个用于位于反向代理后面的站点的简单配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "云负载均衡器"

    用于位于云负载均衡器后面的站点的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "PROXY 协议"

    使用 PROXY 协议与兼容的负载均衡器的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "带有 URL 的多个代理源"

    具有自动更新的代理 IP 列表的高级配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "CDN 配置"

    用于位于 CDN 后面的网站的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Cloudflare 示例
    REAL_IP_RECURSIVE: "no"  # 对于单个 IP 标头不需要
    ```

=== "位于 Cloudflare 后面"

    用于位于 Cloudflare 后面的网站的配置：

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # 我们只信任 Cloudflare 的 IP
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # 自动下载 Cloudflare IP
    REAL_IP_HEADER: "CF-Connecting-IP"  # Cloudflare 用于客户端 IP 的标头
    REAL_IP_RECURSIVE: "yes"
    ```
