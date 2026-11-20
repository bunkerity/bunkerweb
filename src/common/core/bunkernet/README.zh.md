BunkerNet 插件通过 BunkerWeb 实例之间的集体威胁情报共享，创建了一个强大的恶意行为者防护网络。通过参与 BunkerNet，您的实例不仅受益于全球已知威胁数据库，同时也为其做出贡献，从而增强了整个 BunkerWeb 社区的安全性。

**工作原理：**

1.  您的 BunkerWeb 实例会自动向 BunkerNet API 注册，以获取一个唯一标识符。
2.  当您的实例检测并阻止了恶意 IP 地址或行为时，它会向 BunkerNet 报告该威胁。报告包含的字段见下文“报告包含的内容”。
3.  BunkerNet 聚合来自所有参与实例的威胁情报，并分发整合后的数据库。
4.  您的实例会定期从 BunkerNet 下载更新的已知威胁数据库。
5.  这种集体情报使您的实例能够主动阻止在其他 BunkerWeb 实例上表现出恶意行为的 IP 地址。

!!! success "主要优点"

      1. **集体防御：** 利用全球成千上万个其他 BunkerWeb 实例的安全发现。
      2. **主动防护：** 根据恶意行为者在别处的行为，在他们攻击您的网站之前就将其阻止。
      3. **社区贡献：** 通过分享关于攻击者的威胁数据，帮助保护其他 BunkerWeb 用户。
      4. **零配置：** 开箱即用，带有合理的默认值，只需最少的设置。
      5. **受控分享：** 报告包含一组固定的字段，`BUNKERNET_FILTER_HEADERS` 可将其请求头限制为一份简短的白名单（见下文）。

### 如何使用

请按照以下步骤配置和使用 BunkerNet 功能：

1.  **启用该功能：** BunkerNet 功能默认启用。如果需要，您可以使用 `USE_BUNKERNET` 设置来控制此功能。
2.  **初始注册：** 首次启动时，您的实例将自动向 BunkerNet API 注册并收到一个唯一标识符。
3.  **自动更新：** 您的实例将按常规计划自动下载最新的威胁数据库。
4.  **自动报告：** 当您的实例阻止了一个恶意 IP 地址时，它会自动将此数据贡献给社区。
5.  **监控保护：** 查看 [web UI](web-ui.md) 以查看由 BunkerNet 情报阻止的威胁统计信息。

### 配置设置

| 设置                       | 默认值                     | 上下文    | 多个 | 描述                                                                                                                                                                  |
| -------------------------- | -------------------------- | --------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`            | `yes`                      | multisite | 否   | **启用 BunkerNet：** 设置为 `yes` 以启用 BunkerNet 威胁情报共享。                                                                                                     |
| `BUNKERNET_FILTER_HEADERS` | `no`                       | multisite | 否   | **过滤上报的请求头：** 设置为 `yes` 时，只发送一份简短的请求头白名单，并清空 ModSecurity 在请求头和 Cookie 中命中的值。设置为 `no` 时，报告包含除 `Cookie`、`Authorization` 和 `Proxy-Authorization` 之外的所有请求头，以及命中的值（在 Cookie 和这些请求头中命中的值除外）。 |
| `BUNKERNET_SERVER`         | `https://api.bunkerweb.io` | global    | 否   | **BunkerNet 服务器：** 用于共享威胁情报的 BunkerNet API 服务器地址。                                                                                                  |

!!! tip "网络保护"
    当 BunkerNet 检测到某个 IP 地址在多个 BunkerWeb 实例中参与了恶意活动时，它会将该 IP 添加到集体黑名单中。这提供了一个主动的防御层，在威胁直接攻击您之前就保护您的网站。

!!! info "报告包含的内容"
    发送给 BunkerNet 的每份报告包含以下字段，仅此而已：

    - 每次请求发送的实例元数据：BunkerNet 实例 ID、BunkerWeb 版本、集成方式，以及操作系统名称、版本、版本 ID、代号、ID 和架构；
    - 客户端 IP 地址、阻止原因和日期；
    - HTTP 方法、**包含查询字符串的** URL，以及服务名称（`server_name`）；
    - 请求头及其值：收到的所有请求头（最多 `MAX_HEADERS` 个，不含 `Cookie`、`Authorization` 和 `Proxy-Authorization`），或在 `BUNKERNET_FILTER_HEADERS` 为 `yes` 时仅包含 `User-Agent`、`Accept`、`Accept-Encoding`、`Accept-Language`、`Content-Type` 和 `Content-Length`；
    - 与阻止原因相关的详细信息。根据阻止该客户端的插件不同，可能包含命中的 ModSecurity 规则 ID 和消息，以及触发这些规则的请求值（参数、请求体、请求头或 Cookie 的片段，每项截断为 512 字节；在 Cookie 以及 `Cookie`、`Authorization`、`Proxy-Authorization` 请求头中命中的值始终会被清空，`BUNKERNET_FILTER_HEADERS` 为 `yes` 时其他请求头中命中的值也会被清空，只发送变量名）；对于 Bad Behavior，则是导致封禁的近期请求的方法和 URL。

    默认情况下（`BUNKERNET_FILTER_HEADERS` 为 `no`），报告包含收到的所有请求头（最多 `MAX_HEADERS` 个），但不含从不发送的 `Cookie`、`Authorization` 和 `Proxy-Authorization`，以及 ModSecurity 命中的值（在 Cookie 和这些请求头中命中的值除外）。将 `BUNKERNET_FILTER_HEADERS` 设置为 `yes`，则只发送上面列出的六个请求头，并清空在请求头和 Cookie 中命中的值。仍在队列中的报告在发送前也会以同样方式处理（凭据始终清除，白名单在 `yes` 时应用）。

    URL 以及命中的值均来自请求，因此包含客户端发送的任何内容。对于 URL 中带有敏感值的服务，请将 `USE_BUNKERNET` 设置为 `no`。

### 示例配置

=== "默认配置（推荐）"

    默认配置使用官方 BunkerWeb API 服务器启用 BunkerNet：

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "禁用配置"

    如果您不想参与 BunkerNet 威胁情报网络：

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "自定义服务器配置"

    对于运行自己的 BunkerNet 服务器的组织（不常见）：

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

### CrowdSec 控制台集成

如果您还不熟悉 CrowdSec 控制台集成，[CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) 利用众包情报来对抗网络威胁。可以把它想象成“网络安全界的 Waze”——当一台服务器受到攻击时，全球其他系统都会收到警报，并受到保护，免受同一攻击者的侵害。您可以在[这里](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog)了解更多信息。

通过我们与 CrowdSec 的合作，您可以将您的 BunkerWeb 实例注册到您的 [CrowdSec 控制台](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration)。这意味着由 BunkerWeb 阻止的攻击将与由 CrowdSec 安全引擎阻止的攻击一起显示在您的 CrowdSec 控制台中，为您提供统一的威胁视图。

重要的是，此集成无需安装 CrowdSec（尽管我们强烈建议您使用 [BunkerWeb 的 CrowdSec 插件](https://docs.bunkerweb.io/1.6/features/#crowdsec)来进一步增强您的 Web 服务的安全性）。此外，您可以将您的 CrowdSec 安全引擎注册到同一个控制台帐户，以实现更大的协同作用。

**步骤 1：创建您的 CrowdSec 控制台帐户**

前往 [CrowdSec 控制台](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration)注册，如果您还没有帐户的话。完成后，记下在“安全引擎”下点击“添加安全引擎”后找到的注册密钥：

<figure markdown>
  ![概述](assets/img/crowdity1.png){ align=center }
  <figcaption>获取您的 Crowdsec 控制台注册密钥</figcaption>
</figure>

**步骤 2：获取您的 BunkerNet ID**

如果您想将您的 BunkerWeb 实例注册到您的 CrowdSec 控制台中，激活 BunkerNet 功能（默认启用）是强制性的。通过将 `USE_BUNKERNET` 设置为 `yes` 来启用它。

对于 Docker，使用以下命令获取您的 BunkerNet ID：

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

对于 Linux，使用：

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**步骤 3：使用面板注册您的实例**

一旦您有了您的 BunkerNet ID 和 CrowdSec 控制台注册密钥，请在[面板上订购免费产品“BunkerNet / CrowdSec”](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc)。如果您还没有帐户，可能会提示您创建一个。

您现在可以选择“BunkerNet / CrowdSec”服务并填写表格，粘贴您的 BunkerNet ID 和 CrowdSec 控制台注册密钥：

<figure markdown>
  ![概述](assets/img/crowdity2.png){ align=center }
  <figcaption>将您的 BunkerWeb 实例注册到 CrowdSec 控制台</figcaption>
</figure>

**步骤 4：在控制台上接受新的安全引擎**

然后，返回您的 CrowdSec 控制台并接受新的安全引擎：

<figure markdown>
  ![概述](assets/img/crowdity3.png){ align=center }
  <figcaption>接受注册到 CrowdSec 控制台</figcaption>
</figure>

**恭喜，您的 BunkerWeb 实例现已注册到您的 CrowdSec 控制台！**

专业提示：查看警报时，点击“列”选项并勾选“上下文”复选框，以访问 BunkerWeb 特定的数据。

<figure markdown>
  ![概述](assets/img/crowdity4.png){ align=center }
  <figcaption>在上下文列中显示的 BunkerWeb 数据</figcaption>
</figure>
