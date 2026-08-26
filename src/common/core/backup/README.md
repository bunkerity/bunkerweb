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
3. **Set retention policy:** Specify how many backups to keep using the `BACKUP_ROTATION` setting. Which ones are kept is decided by `BACKUP_ROTATION_STRATEGY`, `hanoi` by default.
4. **Define storage location:** Choose where backups will be stored using the `BACKUP_DIRECTORY` setting.
5. **Use CLI commands:** Manage backups manually with the `bwcli plugin backup` commands when needed.

### Configuration Settings

| Setting            | Default                      | Context | Multiple | Description                                                                                                               |
| ------------------ | ---------------------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global  | no       | **Enable Backup:** Set to `yes` to enable automatic backups.                                                              |
| `BACKUP_SCHEDULE`  | `daily`                      | global  | no       | **Backup Frequency:** How often to perform backups. Options: `daily`, `weekly`, or `monthly`.                             |
| `BACKUP_ROTATION`  | `7`                          | global  | no       | **Backup Retention:** The number of backup files to keep. Older backups beyond this number will be automatically deleted. |
| `BACKUP_ROTATION_STRATEGY` | `hanoi`              | global  | no       | **Rotation Strategy:** How backups are picked for deletion once the limit is reached. `hanoi` keeps a Tower of Hanoi ladder — fine near the present, exponentially coarser further back; `fifo` keeps the most recent ones. Both keep the same number of files. |
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

    A backup can only be restored into the same database engine it was taken from — the engine is part of the file name (`backup-mariadb-…`), and a restore into a different one is refused before anything is touched. If you migrated between engines, both sets of backups stay in the directory: `restore` without an argument takes the most recent file of any engine, so pass the path explicitly to restore an older backup of your current one.

### Example Configurations

=== "Daily Backups with 7-File Retention"

    Default configuration: daily backups, 7 files kept, spread by the Tower of Hanoi ladder.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Daily Backups, Last 7 Days (FIFO)"

    The previous default: the 7 most recent files and nothing older.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_ROTATION_STRATEGY: "fifo"
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

=== "Daily Backups with Deeper Retention"

    24 files spread out by the default ladder instead of covering only the last 24 days. The most
    recent backups are kept at full granularity and older ones are thinned exponentially, so the
    oldest restore point moves further back every time the install doubles in age — a problem
    noticed late is still recoverable:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Monthly Backups to Custom Location"

    Configuration for monthly backups stored in a custom location:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```

!!! info "Which backups are kept"
    `hanoi` is the default. Both strategies delete the same **number** of files — `hanoi` never
    removes more backups than `fifo` would — but they do not delete the same ones, and the
    difference is not only at the old end. The ladder buys its depth by thinning the recent window
    too: with a daily schedule at the default `BACKUP_ROTATION: "7"`, an established archive keeps
    one backup from each of roughly the last 1, 2, 4, 8, 16 and 32-day windows — ages of about
    0, 1, 2–3, 4–7, 8–15, 16–31 and 32–63 days, the exact ages depending on where the current day
    falls on the ladder's fixed grid — where `fifo` keeps the last 7 days. **Three or four of the
    last seven days are given up** in exchange for those older restore points.
    The most recent backup is always kept; with one backup per day and `BACKUP_ROTATION` of at
    least 2, so are the two most recent days. The trade is milder the larger `BACKUP_ROTATION` is —
    at `"24"` roughly the last three weeks stay contiguous, a span that shrinks slowly as the
    archive ages.

    **Several backups in the same day count as one restore point, and the extras are the first
    files a rotation gives up** — ahead of anything older. Only the newest backup of each day
    survives once the file budget is spent. So a manual save taken before a risky change is safe
    only until the next backup of that same day, and by becoming that day's newest it displaces the
    day's scheduled backup, which is then the one deleted. Under `fifo` you would have kept both.

    Nothing already on disk is deleted by the upgrade itself — the change takes effect at the next
    rotation. Set `BACKUP_ROTATION_STRATEGY: "fifo"` for the previous behaviour. Every deletion is
    logged with the reason it was picked.

!!! info "How the ladder is built"
    The ladder counts in **periods**, and a period is one `BACKUP_SCHEDULE`: one day for `daily`,
    seven for `weekly`, twenty-eight (four weeks, not a calendar month) for `monthly`. Every backup
    taken inside one period is the same restore point, and the newest of them is the one that
    represents it.

    `BACKUP_ROTATION` is both the file budget and the depth of the ladder: it builds
    `BACKUP_ROTATION - 1` levels, level `k` cutting the timeline into fixed blocks of `2^k` periods
    and keeping the oldest backup of its two most recent non-empty blocks, with the newest backup
    always pinned on top. Each level costs at most one file more than the one below it, so the
    whole ladder fits in the budget — while its reach doubles at every level. Its deepest blocks are
    `2^(BACKUP_ROTATION - 2)` periods wide, so on a daily schedule the oldest restore point sits
    between **32 and 63 days** back at the default `BACKUP_ROTATION: "7"`, and between **1024 and
    2047 days** at `"12"` — the number of files grows linearly, the depth exponentially. `fifo` at
    the same budget never reaches further back than `BACKUP_ROTATION` periods.

    The blocks sit on an absolute grid rather than on windows measured back from today, which is
    what makes a deletion safe: a backup the ladder lets go can never be wanted again, so the deep
    levels do not empty out over time. It also means the ladder **fills in as the archive ages** —
    reaching level `k` takes `2^k` periods, so a young install keeps everything it has and the deep
    restore points appear as it gets older. Until then the unspent budget goes to the most recent
    backups, at full granularity.

!!! info "How backups are dated"
    Rotation reads the timestamp in each archive's name. An archive whose name does not carry a
    usable one — a file copied in by hand, or renamed — is dated by its modification time instead,
    under both strategies.
