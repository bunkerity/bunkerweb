备份插件提供了一个自动备份解决方案来保护您的 BunkerWeb 数据。此功能通过根据您首选的时间表创建定期备份，确保您重要数据库的安全性和可用性。备份存储在指定位置，并且可以通过自动化流程和手动命令轻松管理。

**工作原理：**

1.  您的数据库会根据您设置的时间表（每日、每周或每月）自动备份。
2.  备份存储在您系统上的指定目录中。
3.  旧的备份会根据您的保留设置自动轮换。
4.  您可以随时手动创建备份、列出现有备份或从备份中恢复。
5.  在任何恢复操作之前，当前状态都会自动备份作为安全措施。

### 如何使用

请按照以下步骤配置和使用备份功能：

1.  **启用该功能：** 备份功能默认启用。如果需要，您可以使用 `USE_BACKUP` 设置来控制此功能。
2.  **配置备份计划：** 通过设置 `BACKUP_SCHEDULE` 参数选择备份的频率。
3.  **设置保留策略：** 使用 `BACKUP_ROTATION` 设置指定要保留的备份数量。
4.  **定义存储位置：** 使用 `BACKUP_DIRECTORY` 设置选择备份的存储位置。
5.  **使用 CLI 命令：** 需要时，使用 `bwcli plugin backup` 命令手动管理备份。

### 配置设置

| 设置               | 默认值                       | 上下文 | 多个 | 描述                                                                  |
| ------------------ | ---------------------------- | ------ | ---- | --------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | 全局   | 否   | **启用备份：** 设置为 `yes` 以启用自动备份。                          |
| `BACKUP_SCHEDULE`  | `daily`                      | 全局   | 否   | **备份频率：** 执行备份的频率。选项：`daily`、`weekly` 或 `monthly`。 |
| `BACKUP_ROTATION`  | `7`                          | 全局   | 否   | **备份保留：** 要保留的备份文件数量。超过此数量的旧备份将被自动删除。 |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | 全局   | 否   | **备份位置：** 备份文件将存储的目录。                                 |

### 命令行界面

备份插件提供了几个 CLI 命令来管理您的备份：

```bash
# 列出所有可用的备份
bwcli plugin backup list

# 创建一个手动备份
bwcli plugin backup save

# 在自定义位置创建一个备份
bwcli plugin backup save --directory /path/to/custom/location

# 从最近的备份恢复
bwcli plugin backup restore

# 从特定的备份文件恢复
bwcli plugin backup restore /path/to/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "安全第一"
    在任何恢复操作之前，备份插件会自动在临时位置创建您当前数据库状态的备份。如果您需要还原恢复操作，这提供了一个额外的保障。

!!! warning "数据库兼容性"
    备份插件支持 SQLite、MySQL/MariaDB 和 PostgreSQL 数据库。目前不支持 Oracle 数据库的备份和恢复操作。

### 示例配置

=== "每日备份，保留 7 天"

    默认配置，创建每日备份并保留最近的 7 个文件：

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "每周备份，延长保留期"

    用于频率较低但保留时间较长的备份的配置：

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "每月备份到自定义位置"

    用于每月备份并存储在自定义位置的配置：

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
