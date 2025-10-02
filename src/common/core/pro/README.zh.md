Pro 插件为 BunkerWeb 的企业部署捆绑了高级功能和增强功能。它解锁了额外的功能、高级插件和扩展功能，以补充核心 BunkerWeb 平台。它为企业级部署提供了增强的安全性、性能和管理选项。

**工作原理：**

1.  使用有效的 Pro 许可证密钥，BunkerWeb 会连接到 Pro API 服务器以验证您的订阅。
2.  一旦通过身份验证，该插件会自动下载并安装 Pro 专属插件和扩展。
3.  您的 Pro 状态会定期验证，以确保您能持续访问高级功能。
4.  高级插件会无缝集成到您现有的 BunkerWeb 配置中。
5.  所有 Pro 功能都与开源核心协调工作，是增强而非取代功能。

!!! success "主要优势"

      1. **高级扩展：** 访问社区版中没有的专属插件和功能。
      2. **增强性能：** 优化的配置和高级缓存机制。
      3. **企业支持：** 优先协助和专属支持渠道。
      4. **无缝集成：** Pro 功能与社区功能并行工作，不会产生配置冲突。
      5. **自动更新：** 高级插件会自动下载并保持最新状态。

### 如何使用

请按照以下步骤配置和使用 Pro 功能：

1.  **获取许可证密钥：** 从 [BunkerWeb 面板](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) 购买 Pro 许可证。
2.  **配置您的许可证密钥：** 使用 `PRO_LICENSE_KEY` 设置来配置您的许可证。
3.  **让 BunkerWeb 处理其余部分：** 一旦配置了有效的许可证，Pro 插件将自动下载并激活。
4.  **监控您的 Pro 状态：** 在 [Web UI](web-ui.md) 中检查健康指示器，以确认您的 Pro 订阅状态。

### 配置设置

| 设置              | 默认值 | 上下文 | 多选 | 描述                                                           |
| ----------------- | ------ | ------ | ---- | -------------------------------------------------------------- |
| `PRO_LICENSE_KEY` |        | global | 否   | **Pro 许可证密钥：** 用于身份验证的 BunkerWeb Pro 许可证密钥。 |

!!! tip "许可证管理"
您的 Pro 许可证与您的特定部署环境相关联。如果您需要转移许可证或对您的订阅有疑问，请通过 [BunkerWeb 面板](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) 联系支持。

!!! info "Pro 功能"
随着新功能的增加，可用的具体 Pro 功能可能会随时间演变。Pro 插件会自动处理所有可用功能的安装和配置。

!!! warning "网络要求"
Pro 插件需要出站互联网访问权限，以连接到 BunkerWeb API 进行许可证验证和下载高级插件。请确保您的防火墙允许连接到 `api.bunkerweb.io` 的 443 端口 (HTTPS)。

### 常见问题解答

**问：如果我的 Pro 许可证到期会怎样？**

答：如果您的 Pro 许可证到期，对高级功能和插件的访问将被禁用。但是，您的 BunkerWeb 安装将继续使用所有社区版功能正常运行。要重新获得对 Pro 功能的访问权限，只需续订您的许可证即可。

**问：Pro 功能会干扰我现有的配置吗？**

答：不会，Pro 功能旨在与您当前的 BunkerWeb 设置无缝集成。它们在不更改或干扰您现有配置的情况下增强功能，确保了平稳可靠的体验。

**问：我可以在购买前试用 Pro 功能吗？**

答：当然可以！BunkerWeb 提供两种 Pro 计划以满足您的需求：

- **BunkerWeb PRO Standard：** 完全访问 Pro 功能，但不提供技术支持。
- **BunkerWeb PRO Enterprise：** 完全访问 Pro 功能，并提供专属技术支持。

您可以使用促销码 `freetrial` 免费试用 Pro 功能 1 个月。请访问 [BunkerWeb 面板](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) 激活您的试用，并了解更多关于基于 BunkerWeb PRO 保护的服务数量的灵活定价选项。
