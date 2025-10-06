DNSBL（域名系统黑名单）插件通过对照外部 DNSBL 服务器检查客户端 IP 地址，为您的网站提供针对已知恶意 IP 地址的保护。此功能通过利用社区维护的有问题的 IP 地址列表，帮助保护您的网站免受垃圾邮件、僵尸网络和各种类型的网络威胁。

**工作原理：**

1.  当客户端连接到您的网站时，BunkerWeb 会使用 DNS 协议查询您选择的 DNSBL 服务器。
2.  通过向每个 DNSBL 服务器发送带有客户端 IP 地址的反向 DNS 查询来执行检查。
3.  如果任何 DNSBL 服务器确认客户端的 IP 地址被列为恶意，BunkerWeb 将自动封禁该客户端，防止潜在威胁到达您的应用程序。
4.  结果会被缓存，以提高来自同一 IP 地址的重复访问者的性能。
5.  使用异步查询高效地执行查找，以最大限度地减少对页面加载时间的影响。

### 如何使用

请按照以下步骤配置和使用 DNSBL 功能：

1.  **启用该功能：** DNSBL 功能默认禁用。将 `USE_DNSBL` 设置为 `yes` 以启用它。
2.  **配置 DNSBL 服务器：** 将您要使用的 DNSBL 服务的域名添加到 `DNSBL_LIST` 设置中。
3.  **应用设置：** 配置完成后，BunkerWeb 将自动对照指定的 DNSBL 服务器检查传入的连接。
4.  **监控有效性：** 查看 [web UI](web-ui.md) 以查看因 DNSBL 检查而被阻止的请求的统计信息。

### 配置设置

**通用**

| 设置         | 默认值                                              | 上下文    | 多个 | 描述                                                      |
| ------------ | --------------------------------------------------- | --------- | ---- | --------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | 否   | 启用 DNSBL：设置为 `yes` 以启用对传入连接的 DNSBL 检查。  |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | 否   | DNSBL 服务器：要检查的 DNSBL 服务器域名列表，以空格分隔。 |

**忽略列表**

| 设置                   | 默认值 | 上下文    | 多个 | 描述                                                                          |
| ---------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``     | multisite | 是   | 以空格分隔的 IP/CIDR，用于跳过 DNSBL 检查（白名单）。                         |
| `DNSBL_IGNORE_IP_URLS` | ``     | multisite | 是   | 以空格分隔的 URL，提供要跳过的 IP/CIDR。支持 `http(s)://` 和 `file://` 方案。 |

!!! tip "选择 DNSBL 服务器"
    选择信誉良好的 DNSBL 提供商以最大限度地减少误报。默认列表包括适合大多数网站的成熟服务：

    -   **bl.blocklist.de：** 列出被检测到攻击其他服务器的 IP。
    -   **sbl.spamhaus.org：** 专注于垃圾邮件源和其他恶意活动。
    -   **xbl.spamhaus.org：** 针对受感染的系统，例如被入侵的机器或开放代理。

!!! info "DNSBL 的工作原理"
    DNSBL 服务器通过响应特殊格式的 DNS 查询来工作。当 BunkerWeb 检查一个 IP 地址时，它会反转该 IP 并附加 DNSBL 域名。如果生成的 DNS 查询返回“成功”响应，则该 IP 被视为已列入黑名单。

!!! warning "性能考虑"
    虽然 BunkerWeb 优化了 DNSBL 查找的性能，但添加大量 DNSBL 服务器可能会影响响应时间。从几个信誉良好的 DNSBL 服务器开始，并在添加更多服务器之前监控性能。

### 示例配置

=== "基本配置"

    一个使用默认 DNSBL 服务器的简单配置：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "最小配置"

    一个专注于最可靠的 DNSBL 服务的最小配置：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    此配置仅使用：

    -   **zen.spamhaus.org**：Spamhaus 的组合列表通常被认为是独立的解决方案，因为它覆盖范围广，准确性高。它在一个查询中结合了 SBL、XBL 和 PBL 列表，使其高效而全面。

=== "排除受信任的 IP"

    您可以使用静态值和/或远程文件从 DNSBL 检查中排除特定的客户端：

    -   `DNSBL_IGNORE_IP`：添加以空格分隔的 IP 和 CIDR 范围。示例：`192.0.2.10 203.0.113.0/24 2001:db8::/32`。
    -   `DNSBL_IGNORE_IP_URLS`：提供 URL，其内容每行列出一个 IP/CIDR。以 `#` 或 `;` 开头的注释将被忽略。重复的条目将被去重。

    当传入的客户端 IP 匹配忽略列表时，BunkerWeb 会跳过 DNSBL 查找并将结果缓存为“ok”，以便后续请求更快。

=== "使用远程 URL"

    `dnsbl-download` 作业每小时下载并缓存忽略的 IP：

    -   协议：`https://`、`http://` 和本地 `file://` 路径。
    -   带校验和的每个 URL 缓存可防止冗余下载（1 小时宽限期）。
    -   每个服务的合并文件：`/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`。
    -   在启动时加载并与 `DNSBL_IGNORE_IP` 合并。

    结合静态和 URL 源的示例：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://example.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "使用本地文件"

    使用 `file://` URL 从本地文件加载忽略的 IP：

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```
