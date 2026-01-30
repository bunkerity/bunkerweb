# 概念

## 架构

<figure markdown>
  ![概述](assets/img/concepts.svg){ align=center, width="600" }
</figure>

在您的基础设施中，BunkerWeb 扮演着位于您 Web 服务之前的反向代理的角色。典型的架构是从互联网访问 BunkerWeb，然后 BunkerWeb 将请求转发到安全网络上的相应应用程序服务。

以这种方式（经典的反向代理架构）使用 BunkerWeb，通过 TLS 卸载和集中式安全策略，可以降低后端服务器的加密开销，从而提高性能，同时确保所有服务的一致访问控制、威胁缓解和合规性强制执行。

## 集成

第一个概念是将 BunkerWeb 集成到目标环境中。我们更喜欢使用“集成”这个词而不是“安装”，因为 BunkerWeb 的目标之一是无缝地集成到现有环境中。

官方支持以下集成：

- [Docker](integrations.md#docker)
- [Linux](integrations.md#linux)
- [Docker autoconf](integrations.md#docker-autoconf)
- [Kubernetes](integrations.md#kubernetes)
- [Swarm](integrations.md#swarm)

如果您认为应该支持新的集成，请不要犹豫，在 GitHub 仓库上开启一个 [新问题](https://github.com/bunkerity/bunkerweb/issues)。

!!! info "更进一步"

    所有 BunkerWeb 集成的技术细节都可以在文档的[集成部分](integrations.md)中找到。

## 设置

!!! tip "BunkerWeb PRO 设置"
    某些插件是为 **PRO 版本**保留的。想快速测试 BunkerWeb PRO 一个月吗？在 [BunkerWeb 面板](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc)下单时使用代码 `freetrial`，或者点击[这里](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc)直接应用促销代码（将在结账时生效）。

一旦 BunkerWeb 集成到您的环境中，您将需要配置它来服务和保护您的 Web 应用程序。

BunkerWeb 的配置是通过我们称之为“设置”或“变量”的东西来完成的。每个设置都由一个名称来标识，例如 `AUTO_LETS_ENCRYPT` 或 `USE_ANTIBOT`。您可以为这些设置分配值来配置 BunkerWeb。

这是一个 BunkerWeb 配置的示例：

```conf
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
USE_ANTIBOT=captcha
REFERRER_POLICY=no-referrer
USE_MODSECURITY=no
USE_GZIP=yes
USE_BROTLI=no
```

请注意，如果您正在使用 Web 用户界面，除了“人性化”的标签外，还会显示设置名称：

<figure markdown>
  ![概述](assets/img/settings-ui1.png){ align=center, width="800" }
  <figcaption>Web UI 中的设置名称</figcaption>
</figure>

您还可以使用搜索栏并直接指定一个设置名称：

<figure markdown>
  ![概述](assets/img/settings-ui2.png){ align=center, width="600" }
  <figcaption>Web UI 中的设置搜索</figcaption>
</figure>

!!! info "更进一步"

    包含描述和可能值的可用设置的完整列表可在文档的[功能部分](features.md)中找到。

## 多站点模式 {#multisite-mode}

在使用 BunkerWeb 时，理解多站点模式至关重要。由于我们的主要重点是保护 Web 应用程序，我们的解决方案与“虚拟主机”或“vhosts”的概念紧密相连（更多信息请参见[此处](https://en.wikipedia.org/wiki/Virtual_hosting)）。这些虚拟主机使得可以从单个实例或集群中提供多个 Web 应用程序。

默认情况下，BunkerWeb 禁用多站点模式。这意味着只提供一个 Web 应用程序，并且所有设置都将应用于它。当您只有一个应用程序需要保护时，这种设置是理想的，因为您不需要关心多站点配置。

然而，当启用多站点模式时，BunkerWeb 能够提供和保护多个 Web 应用程序。每个 Web 应用程序由一个唯一的服务器名称标识，并有自己的一组设置。当您有多个应用程序需要保护，并且您更喜欢使用单个实例（或集群）的 BunkerWeb 时，此模式被证明是有益的。

多站点模式的激活由 `MULTISITE` 设置控制，可以将其设置为 `yes` 来启用它，或者设置为 `no` 来禁用它（默认值）。

BunkerWeb 中的每个设置都有一个特定的上下文，决定了它可以应用在哪里。如果上下文设置为“global”，则该设置不能按服务器或站点应用，而是应用于整个配置。另一方面，如果上下文是“multisite”，则该设置可以全局和按服务器应用。要为特定服务器定义一个多站点设置，只需将服务器名称作为前缀添加到设置名称中。例如，`app1.example.com_AUTO_LETS_ENCRYPT` 或 `app2.example.com_USE_ANTIBOT` 是带有服务器名称前缀的设置名称示例。当一个多站点设置在没有服务器前缀的情况下全局定义时，所有服务器都会继承该设置。但是，如果为单个服务器定义了带有服务器名称前缀的相同设置，则该服务器仍然可以覆盖该设置。

理解多站点模式及其相关设置的复杂性，可以使您根据自己的特定要求定制 BunkerWeb 的行为，从而确保为您的 Web 应用程序提供最佳保护。

这是一个多站点 BunkerWeb 配置的示例：

```conf
MULTISITE=yes
SERVER_NAME=app1.example.com app2.example.com app3.example.com
AUTO_LETS_ENCRYPT=yes
USE_GZIP=yes
USE_BROTLI=yes
app1.example.com_USE_ANTIBOT=javascript
app1.example.com_USE_MODSECURITY=no
app2.example.com_USE_ANTIBOT=cookie
app2.example.com_WHITELIST_COUNTRY=FR
app3.example.com_USE_BAD_BEHAVIOR=no
```

请注意，在使用 Web 用户界面时，多站点模式是隐式的。您可以选择直接将配置应用于您的服务，也可以设置全局设置并将其应用于所有服务（您仍然可以对特定服务直接应用例外）：

<figure markdown>
  ![概述](assets/img/ui-multisite.png){ align=center, width="600" }
  <figcaption>从 Web UI 将设置应用于所有服务</figcaption>
</figure>

!!! info "更进一步"

    您将在文档的[高级用法](advanced.md)和仓库的 [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) 目录中找到多站点模式的具体示例。

## 自定义配置 {#custom-configurations}

为了应对独特的挑战并满足特定的用例，BunkerWeb 提供了自定义配置的灵活性。虽然提供的设置和[外部插件](plugins.md)涵盖了广泛的场景，但可能存在需要额外定制的情况。

BunkerWeb 基于著名的 NGINX Web 服务器构建，该服务器提供了一个强大的配置系统。这意味着您可以利用 NGINX 的配置功能来满足您的特定需求。自定义 NGINX 配置可以包含在各种[上下文](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts)中，例如 HTTP 或服务器，从而允许您根据您的要求微调 BunkerWeb 的行为。无论您需要自定义全局设置还是将配置应用于特定的服务器块，BunkerWeb 都能让您优化其行为，使其与您的用例完美对齐。

BunkerWeb 的另一个不可或缺的组件是 ModSecurity Web 应用程序防火墙。通过自定义配置，您可以灵活地处理误报或添加自定义规则，以进一步增强 ModSecurity 提供的保护。这些自定义配置允许您微调防火墙的行为，并确保其与您的 Web 应用程序的特定要求保持一致。

通过利用自定义配置，您可以解锁一个充满可能性的世界，从而根据您的需求精确地定制 BunkerWeb 的行为和安全措施。无论是调整 NGINX 配置还是微调 ModSecurity，BunkerWeb 都提供了灵活性，以有效地应对您的独特挑战。

通过 Web 用户界面管理自定义配置是通过**配置**菜单完成的：

<figure markdown>
  ![概述](assets/img/configs-ui.png){ align=center, width="800" }
  <figcaption>从 Web UI 管理自定义配置</figcaption>
</figure>

!!! info "更进一步"

    您将在文档的[高级用法](advanced.md#custom-configurations)和仓库的 [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) 目录中找到自定义配置的具体示例。

## 数据库

BunkerWeb 将其当前配置安全地存储在后端数据库中，该数据库包含平稳运行所需的基本数据。数据库中存储了以下信息：

- **所有服务的设置**：数据库保存了 BunkerWeb 提供的所有服务的已定义设置。这确保了您的配置和首选项得以保留并随时可用。

- **自定义配置**：您创建的任何自定义配置也存储在后端数据库中。这包括根据您的特定要求量身定制的个性化设置和修改。

- **BunkerWeb 实例**：有关 BunkerWeb 实例的信息，包括其设置和相关详细信息，都存储在数据库中。这便于在适用时轻松管理和监控多个实例。

- **关于作业执行的元数据**：数据库存储与 BunkerWeb 中各种作业执行相关的元数据。这包括有关计划任务、维护过程和其他自动化活动的信息。

- **缓存的文件**：BunkerWeb 利用缓存机制来提高性能。数据库保存缓存的文件，确保高效检索和交付频繁访问的资源。

在底层，每当您编辑设置或添加新配置时，BunkerWeb 都会自动将更改存储在数据库中，从而确保数据的持久性和一致性。BunkerWeb 支持多种后端数据库选项，包括 SQLite、MariaDB、MySQL 和 PostgreSQL。

!!! tip
    如果您使用 Web UI 进行日常管理，我们建议迁移到外部数据库引擎（PostgreSQL 或 MySQL/MariaDB），而不是继续使用 SQLite。外部数据库在多用户环境下处理并发请求和长期增长更加稳定。

使用 `DATABASE_URI` 设置配置数据库非常简单，该设置遵循每种支持的数据库的指定格式：

!!! warning
    当使用 Docker 集成时，您必须在所有 BunkerWeb 容器（除了 BunkerWeb 容器本身）中设置 `DATABASE_URI` 环境变量，以确保所有组件都能正确访问数据库。这对于维护系统的完整性和功能至关重要。

    在任何情况下，请确保在启动 BunkerWeb 之前设置 `DATABASE_URI`，因为这是正常运行所必需的。

- **SQLite**: `sqlite:///var/lib/bunkerweb/db.sqlite3`
- **MariaDB**: `mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **MySQL**: `mysql+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **PostgreSQL**: `postgresql://bunkerweb:changeme@bw-db:5432/db`

通过在配置中指定适当的数据库 URI，您可以将 BunkerWeb 与您首选的数据库后端无缝集成，从而确保高效可靠地存储您的配置数据。

### 数据库兼容性矩阵

| 集成             | PostgreSQL                         | MariaDB            | MySQL             | SQLite |
| :--------------- | :--------------------------------- | :----------------- | :---------------- | :----- |
| **Docker**       | ✅ `v18` 及更早版本（all-in-one：✅ `v17`） | ✅ `v11` 及更早版本 | ✅ `v9` 及更早版本 | ✅ 支持 |
| **Kubernetes**   | ✅ `v18` 及更早版本                 | ✅ `v11` 及更早版本 | ✅ `v9` 及更早版本 | ✅ 支持 |
| **Autoconf**     | ✅ `v18` 及更早版本                 | ✅ `v11` 及更早版本 | ✅ `v9` 及更早版本 | ✅ 支持 |
| **Linux 软件包** | 见下方说明                       | 见下方说明         | 见下方说明        | ✅ 支持 |

!!! info "说明"
    - **PostgreSQL**: 基于 Alpine 的软件包现在包含 `v18` 客户端，因此默认支持 `v18` 及更早版本；all-in-one 镜像仍然使用 `v17` 客户端，因此 `v18` 在该镜像中尚不受支持。
    - **Linux**: 支持情况取决于您的发行版软件包。如果需要，您可以从供应商仓库手动安装数据库客户端（RHEL 通常需要这样做）。
    - **SQLite**: 随软件包一起提供，可立即使用。

有助于安装数据库客户端的外部资源：

- [PostgreSQL 下载与仓库指南](https://www.postgresql.org/download/)
- [MariaDB 仓库配置工具](https://mariadb.org/download/?t=repo-config)
- [MySQL 仓库配置指南](https://dev.mysql.com/doc/mysql-yum-repo-quick-guide/en/)
- [SQLite 下载页面](https://www.sqlite.org/download.html)

<figure markdown>
  ![概述](assets/img/bunkerweb_db.svg){ align=center, width="800" }
  <figcaption>数据库模式</figcaption>
</figure>

## 调度器 {#scheduler}

为了实现无缝协调和自动化，BunkerWeb 采用了一个名为调度器的专门服务。调度器通过执行以下任务，在确保平稳运行方面发挥着至关重要的作用：

- **存储设置和自定义配置**：调度器负责在后端数据库中存储所有设置和自定义配置。这将配置数据集中起来，使其易于访问和管理。

- **执行各种任务（作业）**：调度器处理各种任务的执行，这些任务被称为作业。这些作业涵盖了一系列活动，例如定期维护、计划更新或 BunkerWeb 所需的任何其他自动化任务。

- **生成 BunkerWeb 配置**：调度器生成一个 BunkerWeb 易于理解的配置。该配置源自存储的设置和自定义配置，确保整个系统协调一致地运行。

- **充当其他服务的中介**：调度器充当中介，促进 BunkerWeb 不同组件之间的通信和协调。它与 Web UI 或 autoconf 等服务接口，确保信息和数据交换的无缝流动。

从本质上讲，调度器是 BunkerWeb 的大脑，负责协调各种操作并确保系统的平稳运行。

根据集成方法的不同，调度器的执行环境可能会有所不同。在基于容器的集成中，调度器在其专用容器中执行，提供了隔离性和灵活性。另一方面，对于基于 Linux 的集成，调度器自包含在 bunkerweb 服务中，简化了部署和管理过程。

通过使用调度器，BunkerWeb 简化了基本任务的自动化和协调，从而实现了整个系统的高效可靠运行。

如果您正在使用 Web 用户界面，您可以通过单击菜单中的**作业**来管理调度器作业：

<figure markdown>
  ![概述](assets/img/jobs-ui.png){ align=center, width="800" }
  <figcaption>从 Web UI 管理作业</figcaption>
</figure>

### 实例健康检查

自 1.6.0 版本起，调度器内置了一个健康检查系统，用于监控实例的健康状况。如果一个实例变得不健康，调度器将停止向其发送配置。如果该实例恢复健康，调度器将恢复发送配置。

健康检查间隔由 `HEALTHCHECK_INTERVAL` 环境变量设置，默认值为 `30`，这意味着调度器将每 30 秒检查一次实例的健康状况。

## 模板 {#templates}

BunkerWeb 利用模板的强大功能来简化配置过程并增强灵活性。模板提供了一种结构化和标准化的方法来定义设置和自定义配置，确保了一致性和易用性。

- **预定义模板**：社区版提供了三个预定义模板，其中封装了常见的自定义配置和设置。这些模板可作为配置 BunkerWeb 的起点，实现快速设置和部署。预定义的模板如下：
    - **low**：一个基本模板，提供 Web 应用程序保护的基本设置。
    - **medium**：一个平衡的模板，提供安全功能和性能优化的组合。
    - **high**：一个高级模板，专注于强大的安全措施和全面的保护。

- **自定义模板**：除了预定义模板外，BunkerWeb 还允许用户创建根据其特定要求量身定制的自定义模板。自定义模板可以对设置和自定义配置进行微调，确保 BunkerWeb 与用户的需求完美契合。

使用 Web 用户界面时，当您添加或编辑服务时，可以通过**简单模式**使用模板：

<figure markdown>
  ![概述](assets/img/templates-ui.png){ align=center, width="800" }
  <figcaption>从 Web UI 使用模板</figcaption>
</figure>

**创建自定义模板**

创建一个自定义模板是一个简单的过程，涉及以结构化格式定义所需的设置、自定义配置和步骤。

*   **模板结构**：自定义模板由一个名称、一系列设置、自定义配置和可选步骤组成。模板结构在符合指定格式的 JSON 文件中定义。自定义模板的关键组件包括：
    *   **设置**：设置由一个名称和相应的值定义。此值将覆盖设置的默认值。**仅支持多站点设置。**
    *   **配置**：自定义配置是 NGINX 配置文件的路径，该文件将作为自定义配置包含在内。要知道将自定义配置文件放置在何处，请参阅下面插件树的示例。**仅支持多站点配置类型。**
    *   **步骤**：一个步骤包含一个标题、副标题、设置和自定义配置。每个步骤代表一个配置步骤，用户可以按照该步骤在 Web UI 中根据自定义模板设置 BunkerWeb。

!!! info "关于步骤的说明"

    如果声明了步骤，**则不必在设置和配置部分中包含所有设置和自定义配置**。请记住，当在步骤中声明了设置或自定义配置时，将允许用户在 Web UI 中对其进行编辑。

*   **模板文件**：自定义模板在插件目录内的 `templates` 文件夹中的一个符合指定结构的 JSON 文件中定义。模板文件包含一个名称、设置、自定义配置以及根据用户偏好配置 BunkerWeb 所需的步骤。

*   **选择模板**：一旦定义了自定义模板，用户就可以在 Web UI 中服务的简单模式配置过程中选择它。也可以使用配置中的 `USE_TEMPLATE` 设置来选择模板。模板文件的名称（不带 `.json` 扩展名）应指定为 `USE_TEMPLATE` 设置的值。

自定义模板文件示例：
```json
{
    "name": "模板名称",
	// 可选
    "settings": {
        "SETTING_1": "值",
        "SETTING_2": "值"
    },
	// 可选
    "configs": [
        "modsec/false_positives.conf",
        "modsec/non_editable.conf",
		"modsec-crs/custom_rules.conf"
    ],
	// 可选
    "steps": [
        {
            "title": "标题 1",
            "subtitle": "副标题 1",
            "settings": [
                "SETTING_1"
            ],
            "configs": [
                "modsec-crs/custom_rules.conf"
            ]
        },
        {
            "title": "标题 2",
            "subtitle": "副标题 2",
            "settings": [
                "SETTING_2"
            ],
            "configs": [
                "modsec/false_positives.conf"
            ]
        }
    ]
}
```

包含自定义模板的插件树示例：
```tree
.
├── plugin.json
└── templates
    ├── my_other_template.json
    ├── my_template
    │   └── configs
    │       ├── modsec
    │       │   ├── false_positives.conf
    │       │   └── non_editable.conf
    │       └── modsec-crs
    │           └── custom_rules.conf
    └── my_template.json
```
