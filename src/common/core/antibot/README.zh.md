攻击者通常使用自动化工具（机器人）来尝试利用您的网站。为了防止这种情况，BunkerWeb 包含一个“Antibot”功能，它会挑战用户以证明他们是人类。如果用户成功完成挑战，他们将被授予访问您网站的权限。此功能默认禁用。

**工作原理：**

1.  当用户访问您的网站时，BunkerWeb 会检查他们是否已经通过了 antibot 挑战。
2.  如果没有，用户将被重定向到一个挑战页面。
3.  用户必须完成挑战（例如，解决一个 CAPTCHA，运行 JavaScript）。
4.  如果挑战成功，用户将被重定向回他们最初试图访问的页面，并可以正常浏览您的网站。

### 如何使用

请按照以下步骤启用和配置 Antibot 功能：

1.  **选择一个挑战类型：** 决定使用哪种类型的 antibot 挑战（例如，[captcha](#__tabbed_3_3)、[hcaptcha](#__tabbed_3_5)、[javascript](#__tabbed_3_2)）。
2.  **启用该功能：** 在您的 BunkerWeb 配置中将 `USE_ANTIBOT` 设置为您选择的挑战类型。
3.  **配置设置：** 根据需要调整其他 `ANTIBOT_*` 设置。对于 reCAPTCHA、hCaptcha、Turnstile 和 mCaptcha，您必须在相应的服务上创建一个帐户并获取 API 密钥。
4.  **重要提示：** 确保 `ANTIBOT_URI` 是您网站上一个未被使用的唯一 URL。

!!! important "关于 `ANTIBOT_URI` 设置"
确保 `ANTIBOT_URI` 是您网站上一个未被使用的唯一 URL。

!!! warning "集群环境中的会话配置"
antibot 功能使用 cookie 来跟踪用户是否已完成挑战。如果您在集群环境中运行 BunkerWeb（多个 BunkerWeb 实例），您**必须**正确配置会话管理。这涉及在所有 BunkerWeb 实例中将 `SESSIONS_SECRET` 和 `SESSIONS_NAME` 设置设置为**相同的值**。如果您不这样做，用户可能会被反复提示完成 antibot 挑战。您可以在[此处](#sessions)找到有关会话配置的更多信息。

### 通用设置

以下设置在所有挑战机制中共享：

| 设置                   | 默认值       | 上下文    | 多个 | 描述                                                                                        |
| ---------------------- | ------------ | --------- | ---- | ------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge` | multisite | 否   | **挑战 URL：** 用户将被重定向到以完成挑战的 URL。确保此 URL 未用于您网站上的任何其他内容。  |
| `ANTIBOT_TIME_RESOLVE` | `60`         | multisite | 否   | **挑战时间限制：** 用户完成挑战的最长时间（以秒为单位）。此时间过后，将生成新的挑战。       |
| `ANTIBOT_TIME_VALID`   | `86400`      | multisite | 否   | **挑战有效期：** 已完成的挑战的有效时间（以秒为单位）。此时间过后，用户将必须解决新的挑战。 |

### 从挑战中排除流量

BunkerWeb 允许您指定某些用户、IP 或请求应完全绕过 antibot 挑战。这对于将受信任的服务、内部网络或应始终无需挑战即可访问的特定页面列入白名单非常有用：

| 设置                        | 默认值 | 上下文    | 多个 | 描述                                                                      |
| --------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |        | multisite | 否   | **排除的 URL：** 应绕过挑战的以空格分隔的 URI 正则表达式模式列表。        |
| `ANTIBOT_IGNORE_IP`         |        | multisite | 否   | **排除的 IP：** 应绕过挑战的以空格分隔的 IP 地址或 CIDR 范围列表。        |
| `ANTIBOT_IGNORE_RDNS`       |        | multisite | 否   | **排除的反向 DNS：** 应绕过挑战的以空格分隔的反向 DNS 后缀列表。          |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`  | multisite | 否   | **仅限全局 IP：** 如果设置为 `yes`，则仅对公共 IP 地址执行反向 DNS 检查。 |
| `ANTIBOT_IGNORE_ASN`        |        | multisite | 否   | **排除的 ASN：** 应绕过挑战的以空格分隔的 ASN 编号列表。                  |
| `ANTIBOT_IGNORE_USER_AGENT` |        | multisite | 否   | **排除的用户代理：** 应绕过挑战的以空格分隔的用户代理正则表达式模式列表。 |

**示例：**

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  这将从 antibot 挑战中排除所有以 `/api/`、`/webhook/` 或 `/assets/` 开头的 URI。

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  这将从 antibot 挑战中排除内部网络 `192.168.1.0/24` 和特定 IP `10.0.0.1`。

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  这将从 antibot 挑战中排除来自反向 DNS 以 `googlebot.com` 或 `bingbot.com` 结尾的主机的请求。

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  这将从 antibot 挑战中排除来自 ASN 15169 (Google) 和 ASN 8075 (Microsoft) 的请求。

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  这将从 antibot 挑战中排除用户代理与指定正则表达式模式匹配的请求。

### 支持的挑战机制

=== "Cookie"

    Cookie 挑战是一种轻量级的机制，它依赖于在用户的浏览器中设置一个 cookie。当用户访问网站时，服务器会向客户端发送一个 cookie。在后续的请求中，服务器会检查这个 cookie 是否存在，以验证用户是否是合法的。这种方法对于基本的机器人防护简单有效，无需额外的用户交互。

    **工作原理：**

    1.  服务器生成一个唯一的 cookie 并将其发送给客户端。
    2.  客户端必须在后续的请求中返回该 cookie。
    3.  如果 cookie 缺失或无效，用户将被重定向到挑战页面。

    **配置设置：**

    | 设置          | 默认值 | 上下文    | 多个 | 描述                                                    |
    | ------------- | ------ | --------- | ---- | ------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | no   | **启用 Antibot：** 设置为 `cookie` 以启用 Cookie 挑战。 |

=== "JavaScript"

    JavaScript 挑战要求客户端使用 JavaScript 解决一个计算任务。这种机制确保客户端启用了 JavaScript 并且可以执行所需的代码，这通常超出了大多数机器人的能力。

    **工作原理：**

    1.  服务器向客户端发送一个 JavaScript 脚本。
    2.  该脚本执行一个计算任务（例如，哈希）并将结果提交回服务器。
    3.  服务器验证结果以确认客户端的合法性。

    **主要特点：**

    -   该挑战为每个客户端动态生成一个独特的任务。
    -   计算任务涉及具有特定条件的哈希（例如，找到具有某个前缀的哈希）。

    **配置设置：**

    | 设置          | 默认值 | 上下文    | 多个 | 描述                                                            |
    | ------------- | ------ | --------- | ---- | --------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | no   | **启用 Antibot：** 设置为 `javascript` 以启用 JavaScript 挑战。 |

=== "Captcha"

    Captcha 挑战是一种自制的机制，它可以在您的 BunkerWeb 环境中完全托管生成基于图像的挑战。它测试用户识别和解释随机字符的能力，确保在不依赖外部服务的情况下有效阻止自动化机器人。

    **工作原理：**

    1.  服务器生成一个包含随机字符的 CAPTCHA 图像。
    2.  用户必须将图像中显示的字符输入文本字段。
    3.  服务器根据生成的 CAPTCHA 验证用户的输入。

    **主要特点：**

    -   完全自托管，无需第三方 API。
    -   动态生成的挑战确保每个用户会话的唯一性。
    -   使用可自定义的字符集生成 CAPTCHA。

    **支持的字符：**

    CAPTCHA 系统支持以下字符类型：

    -   **字母：** 所有小写 (a-z) 和大写 (A-Z) 字母
    -   **数字：** 2, 3, 4, 5, 6, 7, 8, 9（不包括 0 和 1 以避免混淆）
    -   **特殊字符：** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    要获取支持的完整字符集，请参阅用于 CAPTCHA 的字体的[字体字符映射](https://www.dafont.com/moms-typewriter.charmap?back=theme)。

    **配置设置：**

    | 设置                       | 默认值                                                 | 上下文    | 多个 | 描述                                                                                                                                                                 |
    | -------------------------- | ------------------------------------------------------ | --------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                                                   | multisite | no   | **启用 Antibot：** 设置为 `captcha` 以启用 Captcha 挑战。                                                                                                            |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | multisite | no   | **Captcha 字母表：** 用于生成 CAPTCHA 的字符字符串。支持的字符：所有字母 (a-z, A-Z)、数字 2-9（不包括 0 和 1）以及特殊字符：```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

=== "reCAPTCHA"

    启用后，reCAPTCHA 会在后台运行 (v3)，根据用户行为分配一个分数。低于配置阈值的分数将提示进一步验证或阻止请求。对于可见的挑战 (v2)，用户必须与 reCAPTCHA 小部件交互才能继续。

    现在有两种集成 reCAPTCHA 的方法：
    - 经典版本（站点/密钥，v2/v3 验证端点）
    - 使用 Google Cloud 的新版本（项目 ID + API 密钥）。经典版本仍然可用，可以通过 `ANTIBOT_RECAPTCHA_CLASSIC` 进行切换。

    对于经典版本，请从 [Google reCAPTCHA 管理控制台](https://www.google.com/recaptcha/admin)获取您的站点和密钥。
    对于新版本，请在您的 Google Cloud 项目中创建一个 reCAPTCHA 密钥，并使用项目 ID 和一个 API 密钥（请参阅 [Google Cloud reCAPTCHA 控制台](https://console.cloud.google.com/security/recaptcha)）。仍然需要一个站点密钥。

    **配置设置：**

    | 设置                           | 默认值 | 上下文    | 多个 | 描述                                                                     |
    | ------------------------------ | ------ | --------- | ---- | ------------------------------------------------------------------------ |
    | `USE_ANTIBOT`                  | `no`   | multisite | no   | 启用 antibot；设置为 `recaptcha` 以启用 reCAPTCHA。                      |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`  | multisite | no   | 使用经典 reCAPTCHA。设置为 `no` 以使用新的基于 Google Cloud 的版本。     |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |        | multisite | no   | reCAPTCHA 站点密钥。经典版和新版都需要。                                 |
    | `ANTIBOT_RECAPTCHA_SECRET`     |        | multisite | no   | reCAPTCHA 密钥。仅经典版需要。                                           |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |        | multisite | no   | Google Cloud 项目 ID。仅新版需要。                                       |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |        | multisite | no   | 用于调用 reCAPTCHA Enterprise API 的 Google Cloud API 密钥。仅新版需要。 |
    | `ANTIBOT_RECAPTCHA_JA3`        |        | multisite | no   | 可选的 JA3 TLS 指纹，包含在企业评估中。                                  |
    | `ANTIBOT_RECAPTCHA_JA4`        |        | multisite | no   | 可选的 JA4 TLS 指纹，包含在企业评估中。                                  |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`  | multisite | no   | 通过所需的最低分数（适用于经典 v3 和新版本）。                           |

=== "hCaptcha"

    启用后，hCaptcha 提供了一个有效的 reCAPTCHA 替代方案，它通过验证用户交互而无需依赖评分机制。它用一个简单的交互式测试来挑战用户，以确认他们的合法性。

    要将 hCaptcha 与 BunkerWeb 集成，您必须从 hCaptcha 仪表板 [hCaptcha](https://www.hcaptcha.com) 获取必要的凭据。这些凭据包括一个站点密钥和一个密钥。

    **配置设置：**

    | 设置                       | 默认值 | 上下文    | 多个 | 描述                                                                 |
    | -------------------------- | ------ | --------- | ---- | -------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`   | multisite | no   | **启用 Antibot：** 设置为 `hcaptcha` 以启用 hCaptcha 挑战。          |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |        | multisite | no   | **hCaptcha 站点密钥：** 您的 hCaptcha 站点密钥（从 hCaptcha 获取）。 |
    | `ANTIBOT_HCAPTCHA_SECRET`  |        | multisite | no   | **hCaptcha 密钥：** 您的 hCaptcha 密钥（从 hCaptcha 获取）。         |

=== "Turnstile"

    Turnstile 是一种现代、注重隐私的挑战机制，它利用 Cloudflare 的技术来检测和阻止自动化流量。它以一种无缝、后台的方式验证用户交互，为合法用户减少了摩擦，同时有效地阻止了机器人。

    要将 Turnstile 与 BunkerWeb 集成，请确保您从 [Cloudflare Turnstile](https://www.cloudflare.com/turnstile) 获取了必要的凭据。

    **配置设置：**

    | 设置                        | 默认值 | 上下文    | 多个 | 描述                                                                     |
    | --------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------ |
    | `USE_ANTIBOT`               | `no`   | multisite | no   | **启用 Antibot：** 设置为 `turnstile` 以启用 Turnstile 挑战。            |
    | `ANTIBOT_TURNSTILE_SITEKEY` |        | multisite | no   | **Turnstile 站点密钥：** 您的 Turnstile 站点密钥（从 Cloudflare 获取）。 |
    | `ANTIBOT_TURNSTILE_SECRET`  |        | multisite | no   | **Turnstile 密钥：** 您的 Turnstile 密钥（从 Cloudflare 获取）。         |

=== "mCaptcha"

    mCaptcha 是一种替代的 CAPTCHA 挑战机制，它通过呈现一个与其他 antibot 解决方案类似的交互式测试来验证用户的合法性。启用后，它会用 mCaptcha 提供的 CAPTCHA 来挑战用户，确保只有真正的用户才能绕过自动安全检查。

    mCaptcha 的设计考虑了隐私。它完全符合 GDPR，确保挑战过程中涉及的所有用户数据都遵守严格的数据保护标准。此外，mCaptcha 提供了自托管的灵活性，允许组织完全控制其数据和基础设施。这种自托管能力不仅增强了隐私，还优化了性能和定制，以适应特定的部署需求。

    要将 mCaptcha 与 BunkerWeb 集成，您必须从 [mCaptcha](https://mcaptcha.org/) 平台或您自己的提供商那里获取必要的凭据。这些凭据包括用于验证的站点密钥和密钥。

    **配置设置：**

    | 设置                       | 默认值                      | 上下文    | 多个 | 描述                                                                 |
    | -------------------------- | --------------------------- | --------- | ---- | -------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | no   | **启用 Antibot：** 设置为 `mcaptcha` 以启用 mCaptcha 挑战。          |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | no   | **mCaptcha 站点密钥：** 您的 mCaptcha 站点密钥（从 mCaptcha 获取）。 |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | no   | **mCaptcha 密钥：** 您的 mCaptcha 密钥（从 mCaptcha 获取）。         |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | no   | **mCaptcha 域：** 用于 mCaptcha 挑战的域。                           |

### 示例配置

=== "Cookie 挑战"

    启用 Cookie 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "JavaScript 挑战"

    启用 JavaScript 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Captcha 挑战"

    启用 Captcha 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    注意：上面的示例使用了数字 2-9 和所有字母，这是 CAPTCHA 挑战最常用的字符。您可以根据需要自定义字母表以包含特殊字符。

=== "reCAPTCHA 经典版"

    经典 reCAPTCHA（站点/密钥）的示例配置：

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "yes"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "reCAPTCHA (新)"

    新的基于 Google Cloud 的 reCAPTCHA（项目 ID + API 密钥）的示例配置：

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # 可选的指纹以改善企业评估
    # ANTIBOT_RECAPTCHA_JA3: "<ja3-fingerprint>"
    # ANTIBOT_RECAPTCHA_JA4: "<ja4-fingerprint>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "hCaptcha 挑战"

    启用 hCaptcha 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Turnstile 挑战"

    启用 Turnstile 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "mCaptcha 挑战"

    启用 mCaptcha 挑战的示例配置：

    ```yaml
    USE_ANTIBOT: "mcaptcha"
    ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```
