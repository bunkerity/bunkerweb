数据库插件通过启用配置数据、日志和其他基本信息的集中存储和管理，为 BunkerWeb 提供了强大的数据库集成。

这个核心组件支持多种数据库引擎，包括 SQLite、PostgreSQL、MySQL/MariaDB 和 Oracle，让您可以选择最适合您的环境和需求的数据库解决方案。

**工作原理：**

1.  BunkerWeb 使用 SQLAlchemy 格式提供的 URI 连接到您配置的数据库。
2.  关键配置数据、运行时信息和作业日志都安全地存储在数据库中。
3.  自动维护流程通过管理数据增长和清理多余记录来优化您的数据库。
4.  对于高可用性场景，您可以配置一个只读数据库 URI，它既可以作为故障转移，也可以作为分流读取操作的方法。
5.  数据库操作会根据您指定的日志级别进行记录，为数据库交互提供适当的可见性。

### 如何使用

请按照以下步骤配置和使用数据库功能：

1.  **选择一个数据库引擎：** 根据您的需求，从 SQLite（默认）、PostgreSQL、MySQL/MariaDB 或 Oracle 中选择。
2.  **配置数据库 URI：** 使用 SQLAlchemy 格式设置 `DATABASE_URI` 以连接到您的主数据库。
3.  **可选的只读数据库：** 对于高可用性设置，配置一个 `DATABASE_URI_READONLY` 作为后备或用于读取操作。

### 配置设置

| 设置                            | 默认值                                    | 上下文 | 多个 | 描述                                                                                       |
| ------------------------------- | ----------------------------------------- | ------ | ---- | ------------------------------------------------------------------------------------------ |
| `DATABASE_URI`                  | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global | 否   | **数据库 URI：** SQLAlchemy 格式的主数据库连接字符串。                                     |
| `DATABASE_URI_READONLY`         |                                           | global | 否   | **只读数据库 URI：** 用于只读操作或在主数据库宕机时作为故障转移的可选数据库。              |
| `DATABASE_LOG_LEVEL`            | `warning`                                 | global | 否   | **日志级别：** 数据库日志的详细程度。选项：`debug`、`info`、`warn`、`warning` 或 `error`。 |
| `DATABASE_MAX_JOBS_RUNS`        | `10000`                                   | global | 否   | **最大作业运行次数：** 在自动清理之前，数据库中保留的作业执行记录的最大数量。              |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                                      | global | 否   | **会话保留：** UI 用户会话在自动清理前允许存在的最大天数。                                 |

!!! tip "数据库选择" - **SQLite**（默认）：由于其简单和基于文件的特性，非常适合单节点部署或测试环境。- **PostgreSQL**：由于其健壮性和并发支持，推荐用于具有多个 BunkerWeb 实例的生产环境。- **MySQL/MariaDB**：是 PostgreSQL 的一个很好的替代品，具有类似的生产级功能。- **Oracle**：适用于 Oracle 已经是标准数据库平台的企业环境。

!!! info "SQLAlchemy URI 格式"
    数据库 URI 遵循 SQLAlchemy 格式：

    -   SQLite: `sqlite:////path/to/database.sqlite3`
    -   PostgreSQL: `postgresql://username:password@hostname:port/database`
    -   MySQL/MariaDB: `mysql://username:password@hostname:port/database` 或 `mariadb://username:password@hostname:port/database`
    -   Oracle: `oracle://username:password@hostname:port/database`

!!! warning "数据库维护"
    该插件会自动运行每日维护作业：

- **清理多余的作业运行记录：** 根据 `DATABASE_MAX_JOBS_RUNS` 限制清除超出的历史。
- **清理过期的 UI 会话：** 删除超过 `DATABASE_MAX_SESSION_AGE_DAYS` 的 UI 用户会话。

这些作业可以防止数据库无限增长，同时保留有价值的运行历史。
