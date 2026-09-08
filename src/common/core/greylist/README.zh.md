Greylist 插件提供了一种灵活的安全方法，允许访问者访问，同时仍然保持必要的安全功能。

与传统的[黑名单](#blacklist)/[白名单](#whitelist)方法——完全阻止或允许访问——不同，灰名单通过授予某些访问者访问权限，同时仍然对他们进行安全检查，创造了一个中间地带。

**工作原理：**

1.  您定义了要被列入灰名单的访问者的标准（_IP 地址、网络、rDNS、ASN、用户代理或 URI 模式_）。
2.  当访问者匹配这些标准中的任何一个时，他们将被授予访问您网站的权限，而其他安全功能仍然有效。
3.  如果访问者不匹配任何灰名单标准，他们的访问将被拒绝。
4.  灰名单数据可以定期从外部来源自动更新。

### 如何使用

请按照以下步骤配置和使用灰名单功能：

1.  **启用该功能：** 灰名单功能默认禁用。将 `USE_GREYLIST` 设置为 `yes` 以启用它。
2.  **配置灰名单规则：** 定义哪些 IP、网络、rDNS 模式、ASN、用户代理或 URI 应被列入灰名单。
3.  **添加外部源：** 可选地，配置用于自动下载和更新灰名单数据的 URL。
4.  **监控访问：** 查看 [web UI](web-ui.md) 以查看哪些访问者被允许或拒绝。

!!! tip "访问控制行为"
    当使用 `USE_GREYLIST` 设置为 `yes` 启用灰名单功能时：

    1.  **灰名单中的访问者：** 允许访问，但仍会受到所有安全检查。
    2.  **非灰名单中的访问者：** 完全拒绝访问。

!!! info "流模式"
    当使用流模式时，只会执行 IP、rDNS 和 ASN 检查。

### 配置设置

**通用**

| 设置           | 默认值 | 上下文    | 多个 | 描述                                         |
| -------------- | ------ | --------- | ---- | -------------------------------------------- |
| `USE_GREYLIST` | `no`   | multisite | 否   | **启用灰名单：** 设置为 `yes` 以启用灰名单。 |

=== "IP 地址"
    **这是做什么的：** 根据访问者的 IP 地址或网络将访问者列入灰名单。这些访问者可以获得访问权限，但仍会受到安全检查。

    | 设置               | 默认值 | 上下文    | 多个 | 描述                                                                          |
    | ------------------ | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |        | multisite | 否   | **IP 灰名单：** 要列入灰名单的 IP 地址或网络（CIDR 表示法）列表，以空格分隔。 |
    | `GREYLIST_IP_URLS` |        | multisite | 否   | **IP 灰名单 URL：** 包含要列入灰名单的 IP 地址或网络的 URL 列表，以空格分隔。 |

=== "反向 DNS"
    **这是做什么的：** 根据访问者的域名（反向）将访问者列入灰名单。对于允许来自特定组织或网络的访问者有条件地访问非常有用。

    | 设置                   | 默认值 | 上下文    | 多个 | 描述                                                                           |
    | ---------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------ |
    | `GREYLIST_RDNS`        |        | multisite | 否   | **rDNS 灰名单：** 要列入灰名单的反向 DNS 后缀列表，以空格分隔。                |
    | `GREYLIST_RDNS_GLOBAL` | `yes`  | multisite | 否   | **仅限 rDNS 全局：** 当设置为 `yes` 时，仅对全局 IP 地址执行 rDNS 灰名单检查。 |
    | `GREYLIST_RDNS_URLS`   |        | multisite | 否   | **rDNS 灰名单 URL：** 包含要列入灰名单的反向 DNS 后缀的 URL 列表，以空格分隔。 |

    !!! info "正向确认的反向 DNS (FCrDNS)"
        `GREYLIST_RDNS` 后缀会经过正向确认：匹配的 PTR 主机名会被解析回一个 IP，只有当该 IP 与客户端 IP 匹配时，才会授予灰名单访问权限。无法通过正向确认的 PTR 会被视为可能的伪造，访问不会被授予。这可以防止控制自己 PTR 记录的攻击者将其设置为已列入灰名单的后缀来获得访问权限。

=== "ASN"
    **这是做什么的：** 使用自治系统号将来自特定网络提供商的访问者列入灰名单。ASN 标识一个 IP 属于哪个提供商或组织。

    | 设置                | 默认值 | 上下文    | 多个 | 描述                                                                  |
    | ------------------- | ------ | --------- | ---- | --------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |        | multisite | 否   | **ASN 灰名单：** 要列入灰名单的自治系统号列表，以空格分隔。           |
    | `GREYLIST_ASN_URLS` |        | multisite | 否   | **ASN 灰名单 URL：** 包含要列入灰名单的 ASN 的 URL 列表，以空格分隔。 |

=== "用户代理"
    **这是做什么的：** 根据访问者声称使用的浏览器或工具将访问者列入灰名单。这允许对特定工具进行受控访问，同时保持安全检查。

    | 设置                       | 默认值 | 上下文    | 多个 | 描述                                                                                 |
    | -------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------------------ |
    | `GREYLIST_USER_AGENT`      |        | multisite | 否   | **用户代理灰名单：** 要列入灰名单的用户代理模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `GREYLIST_USER_AGENT_URLS` |        | multisite | 否   | **用户代理灰名单 URL：** 包含要列入灰名单的用户代理模式的 URL 列表。                 |

=== "URI"
    **这是做什么的：** 将对您网站上特定 URL 的请求列入灰名单。这允许有条件地访问某些端点，同时保持安全检查。

    | 设置                | 默认值 | 上下文    | 多个 | 描述                                                                          |
    | ------------------- | ------ | --------- | ---- | ----------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |        | multisite | 否   | **URI 灰名单：** 要列入灰名单的 URI 模式（PCRE 正则表达式）列表，以空格分隔。 |
    | `GREYLIST_URI_URLS` |        | multisite | 否   | **URI 灰名单 URL：** 包含要列入灰名单的 URI 模式的 URL 列表，以空格分隔。     |

=== "复合规则（AND）"
    **作用：** 同时满足多项条件。上面的平面列表使用 OR，任意一项匹配即可允许进入灰名单访客。规则使用 AND，只有所有条件都匹配才生效。

    | 设置 | 默认值 | 上下文 | 多个 | 描述 |
    | ---- | ------ | ------ | ---- | ---- |
    | `GREYLIST_RULE` | | multisite | yes | **灰名单规则：** 条件以 ` AND ` 连接，必须全部匹配。 |

    条件使用字面量 ` AND ` 分隔：大写，左右各一个空格。语法为：

    ```
    <rule> := <term> ( " AND " <term> )*
    <term> := [ "NOT " ] <kind> ":" <value>
    <kind> := ip | country | asn | rdns | ua | uri
    ```

    `user_agent` 是 `ua` 的别名。`<value>` 可以是 `@office` 等资源组标记，按条件类型解析。规则使用数字后缀，例如 `GREYLIST_RULE_1`、`GREYLIST_RULE_2`。

    ```yaml
    USE_GREYLIST: "yes"
    # a partner's crawler, but only when it comes from the partner's own network
    GREYLIST_RULE_1: "ip:203.0.113.0/24 AND ua:^PartnerCrawler"
    # everything from one ASN, except its scanners
    GREYLIST_RULE_2: "asn:12345 AND NOT ua:(?:nmap|masscan)"
    # a country plus a path, using a resource group for the country list
    GREYLIST_RULE_3: "country:@internal-markets AND uri:^/api/v1/"
    ```

    !!! warning "规则之间是 OR，单条规则内部是 AND"
        多条规则彼此之间，以及规则与平面列表之间都是 **OR**：匹配 `GREYLIST_IP` 或任意一条规则即可允许进入灰名单。单条规则内的条件是 **AND**，必须全部匹配。把两个条件写成两条规则是 OR；把它们放进同一规则才是 AND。

    !!! info "限制"
        * 请求无法提供所需信息时，条件为 **unknown**；含未知条件的规则永不匹配，`NOT` 也不能改变这一点。stream 模式中 `ua:` 和 `uri:` 始终未知；没有 `User-Agent` 头时 `ua:` 也未知。GeoIP 数据库缺失或解析错误同样未知；私网客户端 IP 则不是未知：它确定没有 ASN，国家为 `local`，因此 `NOT asn:…` 可以合法匹配。
        * 含 `ua:` 或 `uri:` 的规则在 stream 服务中无法匹配。由于同一配置也可能服务 HTTP，不会拒绝该规则，但加载配置时会记录带规则名的警告。
        * 只含 `NOT` 的规则有效，但会匹配几乎所有请求；也会通过相同日志渠道警告。
        * 不支持转义语法。由于 ` AND ` 是分隔符，`ua:` 或 `uri:` 正则表达式不能包含任何大小写形式的 " and "；保存时会拒绝这样的规则。
        * `rdns:` 与平面 `GREYLIST_RDNS` 一样进行正向确认：把匹配的 PTR 主机名再次解析，只有结果包含客户端 IP 才为真。

!!! info "URL 格式支持"
    所有 `*_URLS` 设置都支持 HTTP/HTTPS URL 以及使用 `file:///` 前缀的本地文件路径。使用 `http://user:pass@url` 格式支持基本身份验证。

!!! tip "定期更新"
    来自 URL 的灰名单会每小时自动下载和更新，以确保您的保护始终与最新的受信任来源保持同步。

### 示例配置

=== "基本配置"

    一个简单的配置，将灰名单应用于公司的内部网络和爬虫：

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "高级配置"

    一个更全面的配置，具有多个灰名单标准：

    ```yaml
    USE_GREYLIST: "yes"

    # 公司资产和批准的爬虫
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # 公司和合作伙伴的 ASN
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # 外部受信任的来源
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "使用本地文件"

    使用本地文件作为灰名单的配置：

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///path/to/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///path/to/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///path/to/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///path/to/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///path/to/uri-greylist.txt"
    ```

=== "选择性 API 访问"

    允许访问特定 API 端点的配置：

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # 外部合作伙伴网络
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
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
