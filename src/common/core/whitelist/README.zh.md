白名单插件允许您定义一个受信任的 IP 地址列表，这些地址可以绕过其他安全过滤器。
要阻止不需要的客户端，请参考 [黑名单插件](#blacklist)。

白名单插件提供了一种全面的方法，可以根据各种客户端属性明确允许访问您的网站。此功能提供了一种安全机制：符合特定条件的访问者将被授予立即访问权限，而所有其他访问者则必须通过常规的安全检查。

**工作原理：**

1.  您定义应被“列入白名单”的访问者的标准（_IP 地址、网络、反向 DNS、ASN、用户代理或 URI 模式_）。
2.  当访问者尝试访问您的网站时，BunkerWeb 会检查他们是否符合任何这些白名单标准。
3.  如果访问者符合任何白名单规则（并且不符合任何忽略规则），他们将被授予访问您网站的权限，并**绕过所有其他安全检查**。
4.  如果访问者不符合任何白名单标准，他们将照常通过所有正常的安全检查。
5.  白名单可以按计划从外部来源自动更新。

### 如何使用

请按照以下步骤配置和使用白名单功能：

1.  **启用该功能：** 白名单功能默认被禁用。将 `USE_WHITELIST` 设置为 `yes` 以启用它。
2.  **配置允许规则：** 定义哪些 IP、网络、反向 DNS 模式、ASN、用户代理或 URI 应被列入白名单。
3.  **设置忽略规则：** 指定任何应绕过白名单检查的例外情况。
4.  **添加外部来源：** 配置用于自动下载和更新白名单数据的 URL。
5.  **监控访问：** 检查 [Web UI](web-ui.md) 以查看哪些访问者被允许或拒绝。

!!! info "流模式"
    当使用流模式时，仅执行 IP、反向 DNS 和 ASN 检查。

### 配置设置

**通用**

| 设置            | 默认值 | 上下文    | 多选 | 描述                                             |
| --------------- | ------ | --------- | ---- | ------------------------------------------------ |
| `USE_WHITELIST` | `no`   | multisite | 否   | **启用白名单：** 设置为 `yes` 以启用白名单功能。 |

=== "IP 地址"
    **功能说明：** 根据访问者的 IP 地址或网络将其列入白名单。这些访问者将绕过所有安全检查。

    | 设置                       | 默认值 | 上下文    | 多选 | 描述                                                                          |
    | -------------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |        | multisite | 否   | **IP 白名单：** 允许的 IP 地址或网络（CIDR 表示法）列表，以空格分隔。         |
    | `WHITELIST_IGNORE_IP`      |        | multisite | 否   | **IP 忽略列表：** 应绕过 IP 白名单检查的 IP 地址或网络列表。                  |
    | `WHITELIST_IP_URLS`        |        | multisite | 否   | **IP 白名单 URL：** 包含要列入白名单的 IP 地址或网络的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_IP_URLS` |        | multisite | 否   | **IP 忽略列表 URL：** 包含要忽略的 IP 地址或网络的 URL 列表。                 |

=== "反向 DNS"
    **功能说明：** 根据访问者的域名（反向）将其列入白名单。这对于允许来自特定组织或网络的访问者按其域名访问非常有用。

    | 设置                         | 默认值 | 上下文    | 多选 | 描述                                                                           |
    | ---------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------ |
    | `WHITELIST_RDNS`             |        | multisite | 否   | **rDNS 白名单：** 允许的反向 DNS 后缀列表，以空格分隔。                        |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`  | multisite | 否   | **仅限全局 rDNS：** 当设置为 `yes` 时，仅对全局 IP 地址执行 rDNS 白名单检查。  |
    | `WHITELIST_IGNORE_RDNS`      |        | multisite | 否   | **rDNS 忽略列表：** 应绕过 rDNS 白名单检查的反向 DNS 后缀列表。                |
    | `WHITELIST_RDNS_URLS`        |        | multisite | 否   | **rDNS 白名单 URL：** 包含要列入白名单的反向 DNS 后缀的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_RDNS_URLS` |        | multisite | 否   | **rDNS 忽略列表 URL：** 包含要忽略的反向 DNS 后缀的 URL 列表。                 |

=== "ASN"
    **功能说明：** 使用自治系统编号（ASN）将来自特定网络提供商的访问者列入白名单。ASN 标识 IP 属于哪个提供商或组织。

    | 设置                        | 默认值 | 上下文    | 多选 | 描述                                                                  |
    | --------------------------- | ------ | --------- | ---- | --------------------------------------------------------------------- |
    | `WHITELIST_ASN`             |        | multisite | 否   | **ASN 白名单：** 允许的自治系统编号列表，以空格分隔。                 |
    | `WHITELIST_IGNORE_ASN`      |        | multisite | 否   | **ASN 忽略列表：** 应绕过 ASN 白名单检查的 ASN 列表。                 |
    | `WHITELIST_ASN_URLS`        |        | multisite | 否   | **ASN 白名单 URL：** 包含要列入白名单的 ASN 的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_ASN_URLS` |        | multisite | 否   | **ASN 忽略列表 URL：** 包含要忽略的 ASN 的 URL 列表。                 |

=== "用户代理"
    **功能说明：** 根据访问者声称使用的浏览器或工具将其列入白名单。这对于允许访问特定的已知工具或服务非常有效。

    | 设置                               | 默认值 | 上下文    | 多选 | 描述                                                                         |
    | ---------------------------------- | ------ | --------- | ---- | ---------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |        | multisite | 否   | **用户代理白名单：** 允许的用户代理模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `WHITELIST_IGNORE_USER_AGENT`      |        | multisite | 否   | **用户代理忽略列表：** 应绕过用户代理白名单检查的用户代理模式列表。          |
    | `WHITELIST_USER_AGENT_URLS`        |        | multisite | 否   | **用户代理白名单 URL：** 包含要列入白名单的用户代理模式的 URL 列表。         |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |        | multisite | 否   | **用户代理忽略列表 URL：** 包含要忽略的用户代理模式的 URL 列表。             |

=== "URI"
    **功能说明：** 将对您网站上特定 URL 的请求列入白名单。这对于允许访问特定端点而不考虑其他因素很有帮助。

    | 设置                        | 默认值 | 上下文    | 多选 | 描述                                                                      |
    | --------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------- |
    | `WHITELIST_URI`             |        | multisite | 否   | **URI 白名单：** 允许的 URI 模式（PCRE 正则表达式）列表，以空格分隔。     |
    | `WHITELIST_IGNORE_URI`      |        | multisite | 否   | **URI 忽略列表：** 应绕过 URI 白名单检查的 URI 模式列表。                 |
    | `WHITELIST_URI_URLS`        |        | multisite | 否   | **URI 白名单 URL：** 包含要列入白名单的 URI 模式的 URL 列表，以空格分隔。 |
    | `WHITELIST_IGNORE_URI_URLS` |        | multisite | 否   | **URI 忽略列表 URL：** 包含要忽略的 URI 模式的 URL 列表。                 |

!!! info "URL 格式支持"
    所有 `*_URLS` 设置都支持 HTTP/HTTPS URL 以及使用 `file:///` 前缀的本地文件路径。支持使用 `http://user:pass@url` 格式进行基本身份验证。

!!! tip "定期更新"
    从 URL 获取的白名单会每小时自动下载和更新，以确保您的保护与最新的受信任来源保持同步。

!!! warning "安全绕过"
    被列入白名单的访问者将完全**绕过 BunkerWeb 中的所有其他安全检查**，包括 WAF 规则、速率限制、恶意机器人检测以及任何其他安全机制。仅对您绝对信任的来源使用白名单。

### 配置示例

=== "基本组织访问"

    一个简单的配置，将公司办公室的 IP 列入白名单：

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "高级配置"

    一个更全面的配置，具有多个白名单标准：

    ```yaml
    USE_WHITELIST: "yes"

    # 公司和受信任的合作伙伴资产
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # 公司和合作伙伴的 ASN
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # 外部受信任的来源
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "使用本地文件"

    使用本地文件进行白名单的配置：

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///path/to/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///path/to/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///path/to/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///path/to/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///path/to/uri-whitelist.txt"
    ```

=== "API 访问模式"

    一个专注于仅允许访问特定 API 端点的配置：

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # 适用于所有端点的内部网络
    ```

=== "知名爬虫"

    一个将常见的搜索引擎和社交媒体爬虫列入白名单的配置：

    ```yaml
    USE_WHITELIST: "yes"

    # 使用反向 DNS 进行验证以增加安全性
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # 仅检查全局 IP
    ```

    此配置允许合法的爬虫索引您的网站，而不会受到可能阻止它们的速率限制或其他安全措施的影响。rDNS 检查有助于验证爬虫是否确实来自其声称的公司。
