黑名单插件通过根据各种客户端属性阻止访问来为您的网站提供强大的保护。此功能通过根据 IP 地址、网络、反向 DNS 条目、ASN、用户代理和特定的 URI 模式拒绝访问来防御已知的恶意实体、扫描器和可疑访问者。

**工作原理：**

1.  该插件会根据多个黑名单标准（IP 地址、网络、rDNS、ASN、用户代理或 URI 模式）检查传入的请求。
2.  黑名单可以直接在您的配置中指定，也可以从外部 URL 加载。
3.  如果访问者匹配任何黑名单规则（并且不匹配任何忽略规则），访问将被拒绝。
4.  黑名单会根据配置的 URL 定期自动更新。
5.  您可以根据您的特定安全需求自定义要检查和忽略的确切标准。

### 如何使用

请按照以下步骤配置和使用黑名单功能：

1.  **启用该功能：** 黑名单功能默认启用。如果需要，您可以使用 `USE_BLACKLIST` 设置来控制此功能。
2.  **配置阻止规则：** 定义应阻止的 IP、网络、rDNS 模式、ASN、用户代理或 URI。
3.  **设置忽略规则：** 指定应绕过黑名单检查的任何例外情况。
4.  **添加外部源：** 配置 URL 以自动下载和更新黑名单数据。
5.  **监控有效性：** 查看 [web UI](web-ui.md) 以查看有关被阻止请求的统计信息。

!!! info "流模式"
    当使用流模式时，只会执行 IP、rDNS 和 ASN 检查。

### 配置设置

**通用**

| 设置                        | 默认值                                                  | 上下文    | 多个 | 描述                                                          |
| --------------------------- | ------------------------------------------------------- | --------- | ---- | ------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | 否   | **启用黑名单：** 设置为 `yes` 以启用黑名单功能。              |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | 否   | **社区黑名单：** 选择预配置的社区维护的黑名单以包含在阻止中。 |

=== "社区黑名单"
    **这是做什么的：** 使您能够快速添加维护良好的、来自社区的黑名单，而无需手动配置 URL。

    `BLACKLIST_COMMUNITY_LISTS` 设置允许您从精选的黑名单源中进行选择。可用选项包括：

    | ID                                        | 描述                                                                                                                                                                        | 来源                                                                                                                                  |
    | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
    | `ip:danmeuk-tor-exit`                     | Tor 出口节点 IP (dan.me.uk)                                                                                                                                                 | `https://www.dan.me.uk/torlist/?exit`                                                                                                 |
    | `ua:mitchellkrogza-bad-user-agents`       | Nginx 阻止不良机器人、垃圾邮件引荐来源、漏洞扫描器、用户代理、恶意软件、广告软件、勒索软件、恶意网站，具有反 DDOS、Wordpress 主题检测器阻止和针对重复违规者的 Fail2Ban Jail | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list`        |
    | `ip:laurent-minne-data-shield-aggressive` | Data-Shield IPv4 Blocklist - Laurent M. - 适用于 Web 应用, WordPress, VPS (Apache/Nginx)                                                                                    | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt`          |
    | `ip:laurent-minne-data-shield-critical`   | Data-Shield IPv4 Blocklist - Laurent M. - 适用于 DMZs, SaaS, API 和关键资产                                                                                                 | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_critical_data-shield_ipv4_blocklist.txt` |

    **配置：** 指定多个列表，以空格分隔。例如：
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "社区与手动配置"
        社区黑名单提供了一种方便的方式来开始使用经过验证的黑名单源。您可以将它们与手动 URL 配置一起使用，以实现最大的灵活性。

    !!! note "致谢"
        感谢 Laurent Minne 贡献了 [Data-Shield 阻止列表](https://duggytuxy.github.io/#)！

=== "IP 地址"
    **这是做什么的：** 根据访问者的 IP 地址或网络阻止访问。

    | 设置                       | 默认值                                | 上下文    | 多个 | 描述                                                                    |
    | -------------------------- | ------------------------------------- | --------- | ---- | ----------------------------------------------------------------------- |
    | `BLACKLIST_IP`             |                                       | multisite | 否   | **IP 黑名单：** 要阻止的 IP 地址或网络（CIDR 表示法）列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | 否   | **IP 忽略列表：** 应绕过 IP 黑名单检查的 IP 地址或网络列表。            |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | 否   | **IP 黑名单 URL：** 包含要阻止的 IP 地址或网络的 URL 列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | 否   | **IP 忽略列表 URL：** 包含要忽略的 IP 地址或网络的 URL 列表。           |

    默认的 `BLACKLIST_IP_URLS` 设置包含一个提供**已知 Tor 出口节点列表**的 URL。这是恶意流量的常见来源，对于许多网站来说是一个很好的起点。

=== "反向 DNS"
    **这是做什么的：** 根据访问者的反向域名阻止访问。这对于根据其组织域名阻止已知的扫描器和爬虫非常有用。

    | 设置                         | 默认值                  | 上下文    | 多个 | 描述                                                                     |
    | ---------------------------- | ----------------------- | --------- | ---- | ------------------------------------------------------------------------ |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | 否   | **rDNS 黑名单：** 要阻止的反向 DNS 后缀列表，以空格分隔。                |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | 否   | **仅限 rDNS 全局：** 当设置为 `yes` 时，仅对全局 IP 地址执行 rDNS 检查。 |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | 否   | **rDNS 忽略列表：** 应绕过 rDNS 黑名单检查的反向 DNS 后缀列表。          |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | 否   | **rDNS 黑名单 URL：** 包含要阻止的反向 DNS 后缀的 URL 列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | 否   | **rDNS 忽略列表 URL：** 包含要忽略的反向 DNS 后缀的 URL 列表。           |

    默认的 `BLACKLIST_RDNS` 设置包括常见的扫描器域名，如 **Shodan** 和 **Censys**。这些通常被安全研究人员和扫描器用来识别易受攻击的网站。

=== "ASN"
    **这是做什么的：** 阻止来自特定网络提供商的访问者。ASN 就像互联网的邮政编码——它们标识一个 IP 属于哪个提供商或组织。

    | 设置                        | 默认值 | 上下文    | 多个 | 描述                                                            |
    | --------------------------- | ------ | --------- | ---- | --------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |        | multisite | 否   | **ASN 黑名单：** 要阻止的自治系统号列表，以空格分隔。           |
    | `BLACKLIST_IGNORE_ASN`      |        | multisite | 否   | **ASN 忽略列表：** 应绕过 ASN 黑名单检查的 ASN 列表。           |
    | `BLACKLIST_ASN_URLS`        |        | multisite | 否   | **ASN 黑名单 URL：** 包含要阻止的 ASN 的 URL 列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_ASN_URLS` |        | multisite | 否   | **ASN 忽略列表 URL：** 包含要忽略的 ASN 的 URL 列表。           |

=== "用户代理"
    **这是做什么的：** 根据访问者声称使用的浏览器或工具来阻止访问。这对于诚实地表明自己身份的机器人（例如“ScannerBot”或“WebHarvestTool”）是有效的。

    | 设置                               | 默认值                                                                                                                         | 上下文    | 多个 | 描述                                                                           |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- | ------------------------------------------------------------------------------ |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | 否   | **用户代理黑名单：** 要阻止的用户代理模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | 否   | **用户代理忽略列表：** 应绕过用户代理黑名单检查的用户代理模式列表。            |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | 否   | **用户代理黑名单 URL：** 包含要阻止的用户代理模式的 URL 列表。                 |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | 否   | **用户代理忽略列表 URL：** 包含要忽略的用户代理模式的 URL 列表。               |

    默认的 `BLACKLIST_USER_AGENT_URLS` 设置包含一个提供**已知恶意用户代理列表**的 URL。这些通常被恶意机器人和扫描器用来识别易受攻击的网站。

=== "URI"
    **这是做什么的：** 阻止对您网站上特定 URL 的请求。这对于阻止尝试访问管理页面、登录表单或其他可能成为攻击目标的敏感区域非常有用。

    | 设置                        | 默认值 | 上下文    | 多个 | 描述                                                                    |
    | --------------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |        | multisite | 否   | **URI 黑名单：** 要阻止的 URI 模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `BLACKLIST_IGNORE_URI`      |        | multisite | 否   | **URI 忽略列表：** 应绕过 URI 黑名单检查的 URI 模式列表。               |
    | `BLACKLIST_URI_URLS`        |        | multisite | 否   | **URI 黑名单 URL：** 包含要阻止的 URI 模式的 URL 列表，以空格分隔。     |
    | `BLACKLIST_IGNORE_URI_URLS` |        | multisite | 否   | **URI 忽略列表 URL：** 包含要忽略的 URI 模式的 URL 列表。               |

!!! info "URL 格式支持"
    所有 `*_URLS` 设置都支持 HTTP/HTTPS URL 以及使用 `file:///` 前缀的本地文件路径。使用 `http://user:pass@url` 格式支持基本身份验证。

!!! tip "定期更新"
    来自 URL 的黑名单会每小时自动下载和更新，以确保您的保护措施始终能应对最新的威胁。

### 示例配置

=== "基本的 IP 和用户代理保护"

    一个简单的配置，使用社区黑名单阻止已知的 Tor 出口节点和常见的恶意用户代理：

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    或者，您可以使用手动 URL 配置：

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "带有自定义规则的高级保护"

    一个更全面的配置，带有自定义黑名单条目和例外情况：

    ```yaml
    USE_BLACKLIST: "yes"

    # 自定义黑名单条目
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # AWS 和 Amazon 的 ASN
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # 自定义忽略规则
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # 外部黑名单源
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "使用本地文件"

    使用本地文件作为黑名单的配置：

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///path/to/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///path/to/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///path/to/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///path/to/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///path/to/uri-blacklist.txt"
    ```

### 使用本地列表文件

Whitelist、Greylist 和 Blacklist 插件提供的 `*_URLS` 设置共用同一个下载器。当你引用 `file:///` URL 时：

- 路径会在 **scheduler** 容器内解析（Docker 部署通常为 `bunkerweb-scheduler`）。请将文件挂载到该容器，并确保 scheduler 用户拥有读取权限。
- 每个文件都是 UTF-8 编码的纯文本，每行一个条目。空行会被忽略，注释行必须以 `#` 或 `;` 开头。不支持 `//` 注释。
- 各类列表的条目要求：
  - **IP 列表** 接受 IPv4/IPv6 地址或 CIDR 网段（例如 `192.0.2.10` 或 `2001:db8::/48`）。
  - **rDNS 列表** 需要没有空格的后缀（例如 `.search.msn.com`），并会自动转换为小写。
  - **ASN 列表** 可以仅包含编号（`32934`），或带 `AS` 前缀的编号（`AS15169`）。
  - **User-Agent 列表** 视为 PCRE 模式，整行（包括空格）都会保留。请把注释放在独立行，避免被当成模式。
  - **URI 列表** 必须以 `/` 开头，可以使用 `^`、`$` 等 PCRE 标记。

符合格式的示例文件：

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
