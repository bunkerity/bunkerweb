ModSecurity 插件将功能强大的 [ModSecurity](https://modsecurity.org) Web 应用程序防火墙 (WAF) 集成到 BunkerWeb 中。通过利用 [OWASP 核心规则集 (CRS)](https://coreruleset.org)，此集成可检测并阻止 SQL 注入、跨站脚本 (XSS)、本地文件包含等威胁，从而提供针对各种 Web 攻击的强大防护。

**工作原理：**

1.  当收到请求时，ModSecurity 会根据活动规则集对其进行评估。
2.  OWASP 核心规则集会检查标头、Cookie、URL 参数和正文内容。
3.  每个检测到的违规行为都会增加总体异常分数。
4.  如果此分数超过配置的阈值，则请求将被阻止。
5.  创建详细的日志以帮助诊断触发了哪些规则以及原因。

!!! success "主要优势"

      1. **行业标准保护：** 利用广泛使用的开源 ModSecurity 防火墙。
      2. **OWASP 核心规则集：** 采用社区维护的规则，涵盖 OWASP 十大漏洞及更多内容。
      3. **可配置的安全级别：** 调整偏执级别以在安全性与潜在的误报之间取得平衡。
      4. **详细日志记录：** 提供详尽的审计日志以进行攻击分析。
      5. **插件支持：** 通过为您的应用程序量身定制的可选 CRS 插件来扩展保护。

### 如何使用

请按照以下步骤配置和使用 ModSecurity：

1.  **启用该功能：** ModSecurity 默认启用。可以使用 `USE_MODSECURITY` 设置进行控制。
2.  **选择 CRS 版本：** 选择一个 OWASP 核心规则集版本（v3、v4 或 nightly）。
3.  **添加插件：** 可选择激活 CRS 插件以增强规则覆盖范围。
4.  **监控和调整：** 使用日志和 [Web UI](web-ui.md) 识别误报并调整设置。

### 配置设置

| 设置                                  | 默认值         | 上下文    | 多选 | 描述                                                                                                                                        |
| ------------------------------------- | -------------- | --------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`          | multisite | 否   | **启用 ModSecurity：** 开启 ModSecurity Web 应用程序防火墙保护。                                                                            |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | 否   | **使用核心规则集：** 为 ModSecurity 启用 OWASP 核心规则集。                                                                                 |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | 否   | **CRS 版本：** 要使用的 OWASP 核心规则集版本。选项：`3`、`4` 或 `nightly`。                                                                 |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | 否   | **规则引擎：** 控制是否强制执行规则。选项：`On`、`DetectionOnly` 或 `Off`。                                                                 |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | 否   | **审计引擎：** 控制审计日志的工作方式。选项：`On`、`Off` 或 `RelevantOnly`。                                                                |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | 否   | **审计日志部分：** 审计日志中要包含的请求/响应的哪些部分。                                                                                  |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | 否   | **请求体限制（无文件）：** 不含文件上传的请求体的最大大小。接受纯字节或人类可读的后缀（`k`、`m`、`g`），例如 `131072`、`256k`、`1m`、`2g`。 |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | 否   | **启用 CRS 插件：** 为核心规则集启用其他插件规则集。                                                                                        |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | 否   | **CRS 插件列表：** 要下载和安装的插件的空格分隔列表（`plugin-name[/tag]` 或 URL）。                                                         |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | 否   | **全局 CRS：** 启用后，在 HTTP 级别而不是每个服务器上全局应用 CRS 规则。                                                                    |

!!! warning "ModSecurity 和 OWASP 核心规则集"
    **我们强烈建议同时启用 ModSecurity 和 OWASP 核心规则集 (CRS)**，以提供针对常见 Web 漏洞的强大保护。虽然偶尔可能会出现误报，但可以通过微调规则或使用预定义的排除项来解决。

    CRS 团队积极维护着针对 WordPress、Nextcloud、Drupal 和 Cpanel 等流行应用程序的排除项列表，从而更容易在不影响功能的情况下进行集成。其安全优势远远超过了解决误报所需的最低配置工作量。

### 可用的 CRS 版本

选择一个 CRS 版本以最符合您的安全需求：

- **`3`**：稳定版 [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8)。
- **`4`**：稳定版 [v4.22.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.22.0) (**默认**)。
- **`nightly`**：[每日构建版](https://github.com/coreruleset/coreruleset/releases/tag/nightly)，提供最新的规则更新。

!!! example "每日构建版"
    **每日构建版**包含最新的规则，提供针对新兴威胁的最新保护。然而，由于它每天更新，并且可能包含实验性或未经测试的更改，建议在将其部署到生产环境之前，首先在**预演环境**中使用每日构建版。

!!! tip "偏执级别"
    OWASP 核心规则集使用“偏执级别”(PL) 来控制规则的严格性：

    -   **PL1 (默认):** 基本保护，误报最少
    -   **PL2:** 更严格的安全性，具有更严格的模式匹配
    -   **PL3:** 增强的安全性，具有更严格的验证
    -   **PL4:** 最高安全性，规则非常严格（可能导致许多误报）

    您可以通过在 `/etc/bunkerweb/configs/modsec-crs/` 中添加自定义配置文件来设置偏执级别。

### 自定义配置 {#custom-configurations}

可以通过自定义配置来调整 ModSecurity 和 OWASP 核心规则集 (CRS)。这些配置允许您在安全规则处理的特定阶段自定义行为：

- **`modsec-crs`**：在加载 OWASP 核心规则集**之前**应用。
- **`modsec`**：在加载 OWASP 核心规则集**之后**应用。如果根本没有加载 CRS，也会使用此配置。
- **`crs-plugins-before`**：在加载 CRS 插件**之前**应用。
- **`crs-plugins-after`**：在加载 CRS 插件**之后**应用。

这种结构提供了灵活性，允许您根据应用程序的特定需求微调 ModSecurity 和 CRS 设置，同时保持清晰的配置流程。

#### 使用 `modsec-crs` 添加 CRS 排除项

您可以使用 `modsec-crs` 类型的自定义配置来为特定用例添加排除项，例如为 WordPress 启用预定义的排除项：

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

在此示例中：

- 该操作在**阶段 1**（请求生命周期的早期）执行。
- 它通过设置变量 `tx.crs_exclusions_wordpress` 来启用 WordPress 特定的 CRS 排除项。

#### 使用 `modsec` 更新 CRS 规则

要微调已加载的 CRS 规则，您可以使用 `modsec` 类型的自定义配置。例如，您可以为某些请求路径删除特定的规则或标签：

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

在此示例中：

- **规则 1**：为对 `/wp-admin/admin-ajax.php` 的请求删除标记为 `attack-xss` 和 `attack-rce` 的规则。
- **规则 2**：为对 `/wp-admin/options.php` 的请求删除标记为 `attack-xss` 的规则。
- **规则 3**：为匹配 `/wp-json/yoast` 的请求删除特定规则（ID `930120`）。

!!! info "执行顺序"
    BunkerWeb 中 ModSecurity 的执行顺序如下，确保了规则应用的清晰和逻辑性：

    1.  **OWASP CRS 配置**：OWASP 核心规则集的基础配置。
    2.  **自定义插件配置 (`crs-plugins-before`)**：特定于插件的设置，在任何 CRS 规则之前应用。
    3.  **自定义插件规则（在 CRS 规则之前）(`crs-plugins-before`)**：在 CRS 规则之前执行的插件自定义规则。
    4.  **下载的插件配置**：外部下载插件的配置。
    5.  **下载的插件规则（在 CRS 规则之前）**：在 CRS 规则之前执行的下载插件规则。
    6.  **自定义 CRS 规则 (`modsec-crs`)**：在加载 CRS 规则之前应用的用户定义规则。
    7.  **OWASP CRS 规则**：由 OWASP 提供的核心安全规则集。
    8.  **自定义插件规则（在 CRS 规则之后）(`crs-plugins-after`)**：在 CRS 规则之后执行的自定义插件规则。
    9.  **下载的插件规则（在 CRS 规则之后）**：在 CRS 规则之后执行的下载插件规则。
    10. **自定义规则 (`modsec`)**：在所有 CRS 和插件规则之后应用的用户定义规则。

    **关键说明**：

    -   **CRS 前的自定义**（`crs-plugins-before`、`modsec-crs`）允许您在加载核心 CRS 规则之前定义例外或准备性规则。
    -   **CRS 后的自定义**（`crs-plugins-after`、`modsec`）是在应用 CRS 和插件规则之后覆盖或扩展规则的理想选择。
    -   这种结构提供了最大的灵活性，能够在保持强大安全基线的同时，精确控制规则的执行和自定义。

### OWASP CRS 插件

OWASP 核心规则集还支持一系列**插件**，旨在扩展其功能并提高与特定应用程序或环境的兼容性。这些插件可以帮助微调 CRS，以用于 WordPress、Nextcloud 和 Drupal 等流行平台，甚至是自定义设置。有关更多信息和可用插件列表，请参阅 [OWASP CRS 插件注册表](https://github.com/coreruleset/plugin-registry)。

!!! tip "插件下载"
    `MODSECURITY_CRS_PLUGINS` 设置允许您下载和安装插件，以扩展 OWASP 核心规则集 (CRS) 的功能。此设置接受带有可选标签或 URL 的插件名称列表，从而可以轻松集成根据您的特定需求量身定制的其他安全功能。

    以下是 `MODSECURITY_CRS_PLUGINS` 设置接受的值的非详尽列表：

    *   `fake-bot` - 下载插件的最新版本。
    *   `wordpress-rule-exclusions/v1.0.0` - 下载插件的 1.0.0 版本。
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - 直接从 URL 下载插件。

!!! warning "误报"
    较高的安全设置可能会阻止合法流量。请从默认设置开始，并在提高安全级别之前监控日志。请准备好为您的特定应用程序需求添加排除规则。

### 配置示例

=== "基本配置"

    启用 ModSecurity 和 CRS v4 的标准配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "仅检测模式"

    用于监控潜在威胁而不进行阻止的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "带插件的高级配置"

    启用 CRS v4 和插件以提供额外保护的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "旧版配置"

    使用 CRS v3 以与旧设置兼容的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "全局 ModSecurity"

    在所有 HTTP 连接上全局应用 ModSecurity 的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "带自定义插件的每日构建版"

    使用 CRS 的每日构建版并带有自定义插件的配置：

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "人类可读的大小值"
    对于像 `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` 这样的 大小设置，支持 `k`、`m` 和 `g`（不区分大小写）后缀，分别代表 kibibytes、mebibytes 和 gibibytes（1024 的倍数）。例如：`256k` = 262144，`1m` = 1048576，`2g` = 2147483648。
