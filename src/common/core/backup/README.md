The Backup plugin provides an automated backup solution to protect your BunkerWeb data. This feature ensures the safety and availability of your important database by creating regular backups according to your preferred schedule. Backups are stored in a designated location and can be easily managed through both automated processes and manual commands.

**How it works:**

1. Your database is automatically backed up according to the schedule you set (daily, weekly, or monthly).
2. Backups are stored in a specified directory on your system.
3. Old backups are automatically rotated based on your retention settings.
4. You can manually create backups, list existing backups, or restore from a backup at any time.
5. Before any restore operation, the current state is automatically backed up as a safety measure.

### How to Use

Follow these steps to configure and use the Backup feature:

1. **Enable the feature:** The backup feature is enabled by default. If needed, you can control this with the `USE_BACKUP` setting.
2. **Configure backup schedule:** Choose how often backups should occur by setting the `BACKUP_SCHEDULE` parameter.
3. **Set retention policy:** Specify how many backups to keep using the `BACKUP_ROTATION` setting, and how they are picked with `BACKUP_ROTATION_STRATEGY`.
4. **Define storage location:** Choose where backups will be stored using the `BACKUP_DIRECTORY` setting.
5. **Use CLI commands:** Manage backups manually with the `bwcli plugin backup` commands when needed.

### Configuration Settings

| Setting            | Default                      | Context | Multiple | Description                                                                                                               |
| ------------------ | ---------------------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | no       | **Enable Backup:** Set to `yes` to enable automatic backups.                                                              |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | no       | **Backup Frequency:** How often to perform backups. Options: `daily`, `weekly`, or `monthly`.                             |
| `BACKUP_ROTATION`  | `7`                          | global  | no       | **Backup Retention:** The number of backup files to keep. Older backups beyond this number will be automatically deleted. |
| `BACKUP_ROTATION_STRATEGY` | `fifo`               | global  | no       | **Rotation Strategy:** How backups are picked for deletion once the limit is reached. `fifo` keeps the most recent ones; `hanoi` keeps a Tower of Hanoi ladder — fine near the present, exponentially coarser further back — for the same number of files. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global  | no       | **Backup Location:** The directory where backup files will be stored.                                                     |

### Command Line Interface

The Backup plugin provides several CLI commands to manage your backups:

```bash
# List all available backups
bwcli plugin backup list

# Create a manual backup
bwcli plugin backup save

# Create a backup in a custom location
bwcli plugin backup save --directory /path/to/custom/location

# Restore from the most recent backup
bwcli plugin backup restore

# Restore from a specific backup file
bwcli plugin backup restore /path/to/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "Safety First"
    Before any restore operation, the Backup plugin automatically creates a backup of your current database state in a temporary location. This provides an extra safeguard in case you need to revert the restore operation.

!!! warning "Database Compatibility"
    The Backup plugin supports SQLite, MySQL/MariaDB, and PostgreSQL databases. Oracle databases are not currently supported for backup and restore operations.

### Example Configurations

=== "Daily Backups with 7-Day Retention"

    Default configuration that creates daily backups and keeps the most recent 7 files:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Weekly Backups with Extended Retention"

    Configuration for less frequent backups with longer retention:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Daily Backups with Tower of Hanoi Rotation"

    The same 24 files, spread out instead of covering only the last 24 days. The most recent
    backups are kept at full granularity and older ones are thinned exponentially, so the oldest
    restore point moves further back every time the install doubles in age — a problem noticed
    late is still recoverable:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "24"
    BACKUP_ROTATION_STRATEGY: "hanoi"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

    Both strategies delete the same number of files, so switching to `hanoi` never removes more
    backups than `fifo` would — only different ones. Every deletion is logged with the reason.

!!! info "How backups are dated"
    Rotation reads the timestamp in each archive's name. An archive whose name does not carry a
    usable one — a file copied in by hand, or renamed — is dated by its modification time instead,
    under both strategies.

=== "Monthly Backups to Custom Location"

    Configuration for monthly backups stored in a custom location:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
