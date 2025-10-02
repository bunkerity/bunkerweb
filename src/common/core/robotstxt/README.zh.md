Robots.txt 插件为您的网站管理 [robots.txt](https://www.robotstxt.org/) 文件。此文件告知网络爬虫和机器人它们可以或不可以访问您网站的哪些部分。

**工作原理：**

启用后，BunkerWeb 会在您网站的根目录下动态生成 `/robots.txt` 文件。此文件中的规则按以下顺序从多个来源聚合而成：

1.  **DarkVisitors API：** 如果提供了 `ROBOTSTXT_DARKVISITORS_TOKEN`，规则将从 [DarkVisitors](https://darkvisitors.com/) API 获取，从而可以根据配置的代理类型和不允许的用户代理动态阻止恶意机器人和 AI 爬虫。
2.  **社区列表：** 包含来自预定义、社区维护的 `robots.txt` 列表（由 `ROBOTSTXT_COMMUNITY_LISTS` 指定）的规则。
3.  **自定义 URL：** 规则从用户提供的 URL（由 `ROBOTSTXT_URLS` 指定）获取。
4.  **手动规则：** 添加直接通过 `ROBOTSTXT_RULE` 环境变量定义的规则。

所有这些来源的规则都会被合并。聚合后，将应用 `ROBOTSTXT_IGNORE_RULE` 来使用 PCRE 正则表达式模式过滤掉任何不需要的规则。最后，如果整个过程后没有任何规则剩下，将自动应用默认的 `User-agent: *` 和 `Disallow: /` 规则，以确保基本级别的保护。可选的站点地图 URL（由 `ROBOTSTXT_SITEMAP` 指定）也会包含在最终的 `robots.txt` 输出中。

### 使用 DarkVisitors API 动态规避机器人

[DarkVisitors](https://darkvisitors.com/) 是一项提供动态 `robots.txt` 文件的服务，以帮助阻止已知的恶意机器人和 AI 爬虫。通过与 DarkVisitors 集成，BunkerWeb 可以自动获取并提供最新的 `robots.txt`，帮助保护您的网站免受不必要的自动化流量。

要启用此功能，您需要在 [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) 注册并获取一个 bearer 令牌。

### 如何使用

1.  **启用该功能：** 将 `USE_ROBOTSTXT` 设置为 `yes`。
2.  **配置规则：** 选择一种或多种方法来定义您的 `robots.txt` 规则：
    - **DarkVisitors API：** 提供 `ROBOTSTXT_DARKVISITORS_TOKEN`，并可选择性地提供 `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` 和 `ROBOTSTXT_DARKVISITORS_DISALLOW`。
    - **社区列表：** 指定 `ROBOTSTXT_COMMUNITY_LISTS`（以空格分隔的 ID）。
    - **自定义 URL：** 提供 `ROBOTSTXT_URLS`（以空格分隔的 URL）。
    - **手动规则：** 使用 `ROBOTSTXT_RULE` 定义单个规则（可以使用 `ROBOTSTXT_RULE_N` 指定多个规则）。
3.  **过滤规则（可选）：** 使用 `ROBOTSTXT_IGNORE_RULE_N` 通过正则表达式模式排除特定规则。
4.  **添加站点地图（可选）：** 使用 `ROBOTSTXT_SITEMAP_N` 定义站点地图 URL。
5.  **获取生成的 robots.txt 文件：** 在 BunkerWeb 使用上述设置运行后，您可以通过向 `http(s)://your-domain.com/robots.txt` 发出 HTTP GET 请求来访问动态生成的 `robots.txt` 文件。

### 配置设置

| 设置                                 | 默认值 | 上下文    | 多选 | 描述                                                                                                          |
| ------------------------------------ | ------ | --------- | ---- | ------------------------------------------------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`   | multisite | 否   | 启用或禁用 `robots.txt` 功能。                                                                                |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |        | multisite | 否   | 用于 DarkVisitors API 的 Bearer 令牌。                                                                        |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |        | multisite | 否   | 从 DarkVisitors 包含的代理类型（例如 `AI Data Scraper`）的逗号分隔列表。                                      |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`    | multisite | 否   | 指定不允许哪些 URL 的字符串。在联系 DarkVisitors API 时，此值将作为 disallow 字段发送。                       |
| `ROBOTSTXT_COMMUNITY_LISTS`          |        | multisite | 否   | 要包含的社区维护规则集 ID 的空格分隔列表。                                                                    |
| `ROBOTSTXT_URLS`                     |        | multisite | 否   | 用于获取额外 `robots.txt` 规则的 URL 的空格分隔列表。支持 `file://` 和基本身份验证 (`http://user:pass@url`)。 |
| `ROBOTSTXT_RULE`                     |        | multisite | 是   | `robots.txt` 的单条规则。                                                                                     |
| `ROBOTSTXT_HEADER`                   |        | multisite | 是   | `robots.txt` 文件的页眉（在规则之前）。可以是 Base64 编码。                                                   |
| `ROBOTSTXT_FOOTER`                   |        | multisite | 是   | `robots.txt` 文件的页脚（在规则之后）。可以是 Base64 编码。                                                   |
| `ROBOTSTXT_IGNORE_RULE`              |        | multisite | 是   | 用于忽略规则的单个 PCRE 正则表达式模式。                                                                      |
| `ROBOTSTXT_SITEMAP`                  |        | multisite | 是   | 单个站点地图 URL。                                                                                            |

### 配置示例

**基本手动规则**

````yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"```

**使用动态源 (DarkVisitors & 社区列表)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTT_IGNORE_RULE: "User-agent: Googlebot-Image"
````

**组合配置**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**带页眉和页脚**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# 这是一个自定义页眉"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# 这是一个自定义页脚"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

---

更多信息，请参阅 [robots.txt 文档](https://www.robotstxt.org/robotstxt.html)。
