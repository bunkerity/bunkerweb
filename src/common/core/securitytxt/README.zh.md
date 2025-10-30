Security.txt 插件为您的网站实施 [Security.txt](https://securitytxt.org/) 标准 ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116))。此功能可帮助安全研究人员访问您的安全策略，并为他们提供一种标准化的方式来报告他们在您的系统中发现的安全漏洞。

**工作原理：**

1.  启用后，BunkerWeb 会在您网站的根目录下创建一个 `/.well-known/security.txt` 文件。
2.  此文件包含有关您的安全策略、联系人和其他相关详细信息。
3.  安全研究人员和自动化工具可以轻松地在标准位置找到此文件。
4.  内容使用简单的设置进行配置，允许您指定联系信息、加密密钥、策略和致谢。
5.  BunkerWeb 会自动根据 RFC 9116 格式化该文件。

### 如何使用

请按照以下步骤配置和使用 Security.txt 功能：

1.  **启用该功能：** 将 `USE_SECURITYTXT` 设置为 `yes` 以启用 security.txt 文件。
2.  **配置联系信息：** 使用 `SECURITYTXT_CONTACT` 设置至少指定一种联系方式。
3.  **设置附加信息：** 配置可选字段，如到期日期、加密、致谢和策略 URL。
4.  **让 BunkerWeb 处理其余部分：** 配置完成后，BunkerWeb 将自动在标准位置创建并提供 security.txt 文件。

### 配置设置

| 设置                           | 默认值                      | 上下文    | 多选 | 描述                                                                             |
| ------------------------------ | --------------------------- | --------- | ---- | -------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | 否   | **启用 Security.txt：** 设置为 `yes` 以启用 security.txt 文件。                  |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | 否   | **Security.txt URI：** 指示 security.txt 文件可访问的 URI。                      |
| `SECURITYTXT_CONTACT`          |                             | multisite | 是   | **联系信息：** 安全研究人员如何与您联系（例如，`mailto:security@example.com`）。 |
| `SECURITYTXT_EXPIRES`          |                             | multisite | 否   | **到期日期：** 此 security.txt 文件应被视为到期的日期（ISO 8601 格式）。         |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | 是   | **加密：** 指向用于安全通信的加密密钥的 URL。                                    |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | 是   | **致谢：** 认可安全研究人员报告的 URL。                                          |
| `SECURITYTXT_POLICY`           |                             | multisite | 是   | **安全策略：** 指向描述如何报告漏洞的安全策略的 URL。                            |
| `SECURITYTXT_HIRING`           |                             | multisite | 是   | **安全职位：** 指向与安全相关的职位空缺的 URL。                                  |
| `SECURITYTXT_CANONICAL`        |                             | multisite | 是   | **规范 URL：** 此 security.txt 文件的规范 URI。                                  |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | 否   | **首选语言：** 通信中使用的语言。指定为 ISO 639-1 语言代码。                     |
| `SECURITYTXT_CSAF`             |                             | multisite | 是   | **CSAF：** 指向您的通用安全咨询框架提供商的 provider-metadata.json 的链接。      |

!!! warning "需要到期日期"
    根据 RFC 9116，`Expires` 字段是必需的。如果您没有为 `SECURITYTXT_EXPIRES` 提供值，BunkerWeb 会自动将到期日期设置为从当前日期算起的一年。

!!! info "联系信息至关重要"
    `Contact` 字段是 security.txt 文件中最重要的部分。您应该至少提供一种方式让安全研究人员与您联系。这可以是电子邮件地址、Web 表单、电话号码或任何其他适合您组织的方式。

!!! warning "URL 必须使用 HTTPS"
    根据 RFC 9116，security.txt 文件中的所有 URL（`mailto:` 和 `tel:` 链接除外）都必须使用 HTTPS。非 HTTPS URL 将被 BunkerWeb 自动转换为 HTTPS，以确保符合标准。

### 配置示例

=== "基本配置"

    一个仅包含联系信息的最小配置：

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "综合配置"

    一个包含所有字段的更完整的配置：

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "多联系人配置"

    具有多种联系方式的配置：

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```
