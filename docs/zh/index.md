# 简介

## 概述

<figure markdown>
  ![概述](assets/img/intro-overview.svg){ align=center, width="800" }
  <figcaption>让您的网络服务默认安全！</figcaption>
</figure>

BunkerWeb 是新一代的开源 Web 应用程序防火墙 (WAF)。

作为一款功能齐全的 Web 服务器（底层基于 [NGINX](https://nginx.org/)），它能保护您的 Web 服务，使其“默认安全”。BunkerWeb 能够无缝集成到您现有的环境中（[Linux](integrations.md#linux)、[Docker](integrations.md#docker)、[Swarm](integrations.md#swarm)、[Kubernetes](integrations.md#kubernetes) 等），作为反向代理运行，并且完全可配置（别担心，如果您不喜欢命令行，我们有一个[出色的 Web UI](web-ui.md)）以满足您的特定用例。换句话说，网络安全不再是件麻烦事。

BunkerWeb 的核心包含主要的[安全功能](advanced.md#security-tuning)，但借助[插件系统](plugins.md)，可以轻松扩展其他功能。

## 为何选择 BunkerWeb？

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/oybLtyhWJIo" title="BunkerWeb 概述" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

- **轻松集成到现有环境**：无缝地将 BunkerWeb 集成到 Linux、Docker、Swarm、Kubernetes 等各种环境中。享受平滑过渡和无忧实施。

- **高度可定制**：轻松地根据您的特定需求定制 BunkerWeb。毫不费力地启用、禁用和配置功能，让您能够根据自己独特的用例自定义安全设置。

- **默认安全**：BunkerWeb 为您的 Web 服务提供开箱即用、无忧的最低限度安全保障。从一开始就体验安心和增强的保护。

- **出色的 Web UI**：通过卓越的 Web 用户界面 (UI) 更有效地控制 BunkerWeb。通过用户友好的图形界面轻松导航设置和配置，无需使用命令行界面 (CLI)。

- **插件系统**：扩展 BunkerWeb 的功能以满足您自己的用例。无缝集成额外的安全措施，并根据您的特定要求自定义 BunkerWeb 的功能。

- **“自由”软件**：BunkerWeb 采用自由的 [AGPLv3 许可证](https://www.gnu.org/licenses/agpl-3.0.en.html)，拥抱自由和开放的原则。享受使用、修改和分发该软件的自由，并得到一个支持性社区的支持。

- **专业服务**：直接从 BunkerWeb 的维护者那里获得技术支持、量身定制的咨询和自定义开发。请访问 [BunkerWeb 面板](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc)获取更多信息。

## 安全特性

探索 BunkerWeb 提供的令人印象深刻的安全特性。虽然并非详尽无遗，但以下是一些值得注意的亮点：

- **HTTPS** 支持及透明的 **Let's Encrypt** 自动化：通过自动化的 Let's Encrypt 集成，轻松保护您的 Web 服务，确保客户端与服务器之间的通信加密。

- **顶尖的网络安全**：受益于前沿的网络安全措施，包括全面的 HTTP 安全标头、防止数据泄露和 TLS 加固技术。

- 集成 **ModSecurity WAF** 和 **OWASP 核心规则集**：通过集成 ModSecurity，并由著名的 OWASP 核心规则集加固，享受针对 Web 应用程序攻击的增强保护。

- **根据 HTTP 状态码自动封禁**异常行为：BunkerWeb 通过自动封禁触发异常 HTTP 状态码的行为，智能地识别和阻止可疑活动。

- 对客户端施加**连接和请求限制**：对来自客户端的连接和请求数量设置限制，防止资源耗尽，并确保服务器资源的公平使用。

- 通过**基于挑战的验证拦截机器人**：通过挑战机器人解决诸如 Cookie、JavaScript 测试、验证码、hCaptcha、reCAPTCHA 或 Turnstile 等谜题，有效地阻止恶意机器人，防止未经授权的访问。

- 通过外部黑名单和 **DNSBL 拦截已知的恶意 IP**：利用外部黑名单和基于 DNS 的黑洞列表 (DNSBL) 来主动拦截已知的恶意 IP 地址，加强您对潜在威胁的防御。

- **以及更多...**：BunkerWeb 还包含了许多超出此列表的其他安全特性，为您提供全面的保护和安心。

要更深入地了解核心安全特性，我们邀请您探索文档的[安全调整](advanced.md#security-tuning)部分。了解 BunkerWeb 如何使您能够根据自己的特定需求微调和优化安全措施。

## 演示

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/ZhYV-QELzA4" title="欺骗自动化工具和扫描器" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

一个受 BunkerWeb 保护的演示网站可在 [demo.bunkerweb.io](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc) 访问。欢迎访问并进行一些安全测试。

## Web UI

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb Web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

BunkerWeb 提供了一个可选的[用户界面](web-ui.md)来管理您的实例及其配置。一个在线的只读演示可在 [demo-ui.bunkerweb.io](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc) 访问。欢迎您亲自试用。

## BunkerWeb Cloud

<figure markdown>
  ![概述](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb 云</figcaption>
</figure>

不想自己托管和管理您的 BunkerWeb 实例吗？您可能会对 BunkerWeb Cloud 感兴趣，这是我们为 BunkerWeb 提供的完全托管的 SaaS 产品。

订购您的 [BunkerWeb Cloud 实例](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc)，您将获得：

- 一个完全托管在我们云端的 BunkerWeb 实例
- 所有 BunkerWeb 功能，包括 PRO 功能
- 一个带有仪表板和警报的监控平台
- 协助您进行配置的技术支持

如果您对 BunkerWeb Cloud 服务感兴趣，请随时[联系我们](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc)，以便我们讨论您的需求。

## PRO 版本

!!! tip "BunkerWeb PRO 免费试用"
    想要快速试用 BunkerWeb PRO 一个月吗？在 [BunkerWeb 面板](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc)下单时使用代码 `freetrial`，或者点击[这里](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc)直接应用促销代码（将在结账时生效）。

使用 BunkerWeb 时，您可以选择您想要使用的版本：开源版或 PRO 版。

无论是增强的安全性、丰富的用户体验还是技术监控，BunkerWeb PRO 版本都能让您充分利用 BunkerWeb，满足您的专业需求。

在文档或用户界面中，PRO 功能会用一个皇冠图标 <img src="../../assets/img/pro-icon.svg" alt="crown pro icon" height="32px" width="32px"> 标注，以区别于集成在开源版本中的功能。

您可以随时轻松地从开源版本升级到 PRO 版本。过程非常简单：

- 在结账时使用 `freetrial` 促销代码，在 [BunkerWeb 面板上领取您的免费试用](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc)
- 连接到客户区后，复制您的 PRO 许可证密钥
- 使用 [Web UI](web-ui.md#upgrade-to-pro) 或[特定设置](features.md#pro)将您的私钥粘贴到 BunkerWeb 中

如果您对 PRO 版本有任何疑问，请随时访问 [BunkerWeb 面板](https://panel.bunkerweb.io/knowledgebase?utm_campaign=self&utm_source=doc)或[联系我们](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc)。

## 专业服务

通过直接从项目维护者那里获得专业服务，充分利用 BunkerWeb。从技术支持到量身定制的咨询和开发，我们随时准备协助您保护您的 Web 服务。

您可以通过访问 [BunkerWeb 面板](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc)找到更多信息，这是我们为专业服务设立的专用平台。

如果您有任何疑问，请随时[联系我们](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc)。我们将非常乐意满足您的需求。

## 生态系统、社区和资源

关于 BunkerWeb 的官方网站、工具和资源：

- [**网站**](https://www.bunkerweb.io/?utm_campaign=self&utm_source=doc)：获取有关 BunkerWeb 的更多信息、新闻和文章。
- [**面板**](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc)：一个专门用于订购和管理 BunkerWeb 周边专业服务（例如技术支持）的平台。
- [**文档**](https://docs.bunkerweb.io)：BunkerWeb 解决方案的技术文档。
- [**演示**](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc)：BunkerWeb 的演示网站。欢迎尝试攻击以测试该解决方案的稳健性。
- [**Web UI**](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc)：BunkerWeb Web UI 的在线只读演示。
- [**威胁地图**](https://www.bunkerweb.io/threatmap/?utm_campaign=self&utm_source=doc)：全球 BunkerWeb 实例实时拦截的网络攻击。
- [**状态**](https://status.bunkerweb.io/?utm_campaign=self&utm_source=doc)：BunkerWeb 服务运行状况和可用性的实时更新。

社区和社交网络：

- [**Discord**](https://discord.com/invite/fTf46FmtyD)
- [**LinkedIn**](https://www.linkedin.com/company/bunkerity/)
- [**X (Formerly Twitter)**](https://x.com/bunkerity)
- [**Reddit**](https://www.reddit.com/r/BunkerWeb/)
