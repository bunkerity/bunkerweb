# Upgrading

## Upgrade from 1.6.X

### Procedure

#### Docker

1. **Backup the database**:

    - Before proceeding with the database upgrade, ensure that you perform a complete backup of the current state of the database.
    - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

    ```bash
    docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
    ```

    ```bash
    docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
    ```

2. **Upgrade BunkerWeb**:
    - Upgrade BunkerWeb to the latest version.
        1. **Update the Docker Compose file**: Update the Docker Compose file to use the new version of the BunkerWeb image.
            ```yaml
            services:
                bunkerweb:
                    image: bunkerity/bunkerweb:1.6.7-rc1
                    ...
                bw-scheduler:
                    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                    ...
                bw-autoconf:
                    image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                    ...
                bw-ui:
                    image: bunkerity/bunkerweb-ui:1.6.7-rc1
                    ...
            ```

        2. **Restart the containers**: Restart the containers to apply the changes.
            ```bash
            docker compose down
            docker compose up -d
            ```

3. **Check the logs**: Check the logs of the scheduler service to ensure that the migration was successful.

    ```bash
    docker compose logs <scheduler_container>
    ```

4. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database container.

#### Linux

=== "Easy upgrade using the install script"

    * **Quick start**:

        To get started, download the installation script and its checksum, then verify the script's integrity before running it.

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | jq -r .tag_name)

        # Download the script and its checksum
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # Verify the checksum
        sha256sum -c install-bunkerweb.sh.sha256

        # If the check is successful, run the script
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "Security Notice"
            **Always verify the integrity of the installation script before running it.**

            Download the checksum file and use a tool like `sha256sum` to confirm the script has not been altered or tampered with.

            If the checksum verification fails, **do not execute the script**—it may be unsafe.

    * **How it works**:

        The same multi‑purpose install script used for fresh installs can also perform an in‑place upgrade. When it detects an existing installation and a different target version, it switches to upgrade mode and applies the following workflow:

        1. Detection & validation
            * Detects OS / version and confirms support matrix.
            * Reads currently installed BunkerWeb version from `/usr/share/bunkerweb/VERSION`.
        2. Upgrade scenario decision
            * If the requested version equals the installed one it aborts (unless you explicitly re-run for status).
            * If versions differ it flags an upgrade.
        3. (Optional) Automatic pre‑upgrade backup
            * If `bwcli` and the scheduler are available and auto‑backup is enabled, it creates a backup via the built‑in backup plugin.
            * Destination: either the directory you supplied with `--backup-dir` or a generated path like `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
            * You can disable this with `--no-auto-backup` (manual backup then becomes your responsibility).
        4. Service quiescing
            * Stops `bunkerweb`, `bunkerweb-ui`, and `bunkerweb-scheduler` to ensure a consistent upgrade (matches the manual procedure recommendations).
        5. Package locks removal
            * Temporarily removes `apt-mark hold` / `dnf versionlock` on `bunkerweb` and `nginx` so the targeted version can be installed.
        6. Upgrade execution
            * Installs only the new BunkerWeb package version (NGINX is not reinstalled in upgrade mode unless missing—this avoids touching a correctly pinned NGINX).
            * Re‑applies holds/versionlocks to freeze the upgraded versions.
        7. Finalization & status
            * Displays systemd status for core services and next steps.
            * Leaves your configuration and database intact—only the application code and managed files are updated.

        Key behaviors / notes:

        * The script does NOT modify your `/etc/bunkerweb/variables.env` or database content.
        * If automatic backup failed (or was disabled) you can still do a manual restore using the Rollback section below.
        * Upgrade mode intentionally avoids reinstalling or downgrading NGINX outside the supported pinned version already present.
        * Logs for troubleshooting remain in `/var/log/bunkerweb/`.

    * **Mode-aware behavior**:

        - The installer reuses the same installation-type logic during upgrades: manager mode keeps the setup wizard disabled, binds the API to `0.0.0.0`, and requires a whitelist IP (pass `--manager-ip` for unattended runs), while worker mode still enforces the manager IP list.
        - Manager upgrades can opt to start or skip the Web UI service, and the summary explicitly reports the API service state so you can decide whether to enable it via `--api` / `--no-api`.
        - CrowdSec options remain limited to full-stack upgrades, and the script continues to validate both the operating system and CPU architecture before touching packages, gating unsupported combinations behind `--force`.

        Rollback summary:

        * Use the generated backup directory (or your manual backup) + the steps in the Rollback section to restore DB, then reinstall the previous image / package version and re‑lock packages.

    *  **Command-Line Options**:

        You can drive unattended upgrades with the same flags used for installation. The most relevant for upgrades:

        | Option                  | Purpose                                                                                           |
        | ----------------------- | ------------------------------------------------------------------------------------------------- |
        | `-v, --version <X.Y.Z>` | Target BunkerWeb version to upgrade to.                                                           |
        | `-y, --yes`             | Non‑interactive (assumes upgrade confirmation and enables auto backup unless `--no-auto-backup`). |
        | `--backup-dir <PATH>`   | Destination for the automatic pre‑upgrade backup. Created if missing.                             |
        | `--no-auto-backup`      | Skip automatic backup (NOT recommended). You must have a manual backup.                           |
        | `-q, --quiet`           | Suppress output (combine with logging / monitoring).                                              |
        | `-f, --force`           | Proceed on an otherwise unsupported OS version.                                                   |
        | `--dry-run`             | Show detected environment, intended actions, then exit without changing anything.                 |

        Examples:

        ```bash
        # Upgrade to 1.6.7~rc1 interactively (will prompt for backup)
        sudo ./install-bunkerweb.sh --version 1.6.7~rc1

        # Non-interactive upgrade with automatic backup to custom directory
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --backup-dir /var/backups/bw-2025-01 -y

        # Silent unattended upgrade (logs suppressed) – relies on default auto-backup
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 -y -q

        # Perform a dry run (plan) without applying changes
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --dry-run

        # Upgrade skipping automatic backup (NOT recommended)
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --no-auto-backup -y
        ```

        !!! warning "Skipping backups"
            Using `--no-auto-backup` without having a verified manual backup may result in irreversible data loss if the upgrade encounters issues. Always keep at least one recent, tested backup.

=== "Manual"

    1. **Backup the database**:

        - Before proceeding with the database upgrade, ensure that you perform a complete backup of the current state of the database.
        - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

        ??? warning "Information for Red Hat Enterprise Linux (RHEL) 8.10 users"
            If you are using **RHEL 8.10** and plan on using an **external database**, you will need to install the `mysql-community-client` package to ensure the `mysqldump` command is available. You can install the package by executing the following commands:

            === "MySQL/MariaDB"

                1. **Install the MySQL repository configuration package**

                    ```bash
                    sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                    ```

                2. **Enable the MySQL repository**

                    ```bash
                    sudo dnf config-manager --enable mysql80-community
                    ```

                3. **Install the MySQL client**

                    ```bash
                    sudo dnf install mysql-community-client
                    ```

            === "PostgreSQL"

                4. **Install the PostgreSQL repository configuration package**

                    ```bash
                    dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                    ```

                5. **Install the PostgreSQL client**

                    ```bash
                    dnf install postgresql<version>
                    ```

        ```bash
        BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
        ```

    1. **Upgrade BunkerWeb**:
        - Upgrade BunkerWeb to the latest version.

            1. **Stop the services**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            2. **Update BunkerWeb**:

                === "Debian/Ubuntu"

                    First, if you have previously held the BunkerWeb package, unhold it :

                    You can print a list of packages on hold with `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Then, you can update the BunkerWeb package :

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
                    ```

                    To prevent the BunkerWeb package from upgrading when executing `apt upgrade`, you can use the following command :

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    More details in the [integration Linux page](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    First, if you have previously held the BunkerWeb package, unhold it :

                    You can print a list of packages on hold with `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Then, you can update the BunkerWeb package :

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
                    ```

                    To prevent the BunkerWeb package from upgrading when executing `dnf upgrade`, you can use the following command :

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    More details in the [integration Linux page](integrations.md#__tabbed_1_3).

            3. **Start the services**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
                    ```
                    Or reboot the system:
                    ```bash
                    sudo reboot
                    ```


    3. **Check the logs**: Check the logs of the scheduler service to ensure that the migration was successful.

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

    4. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database container.

### Rollback

!!! failure "In case of issues"

    If you encounter any issues during the upgrade, you can rollback to the previous version of the database by restoring the backup taken in [step 1](#__tabbed_1_1).

    Get support and more information :

    - [Order professional support](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Create an issue on GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Join the BunkerWeb Discord server](https://discord.bunkerity.com)

=== "Docker"

    1. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restore the backup**.

        === "SQLite"

            1. **Remove the existing database file.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restore the backup.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Fix permissions.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restore the backup.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

    3. **Downgrade BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Start the containers**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Stop the services**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Restore the backup**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Start the services**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Downgrade BunkerWeb**.
        - Downgrade BunkerWeb to the previous version by following the same steps as when upgrading BunkerWeb in the [integration Linux page](integrations.md#linux)

## Upgrade from 1.5.X

### What changed?

#### Scheduler

Unlike the 1.5.X releases, the Scheduler service **no longer uses the *docker socket proxy* to fetch BunkerWeb's instances**. Instead, it uses the new `BUNKERWEB_INSTANCES` environment variable.

!!! info "About the `BUNKERWEB_INSTANCES` environment variable"

    This new variable is a list of BunkerWeb instances separated by spaces in this format: `http://bunkerweb:5000 bunkerweb1:5000 bunkerweb2:5000 ...`. The scheduler will then use this list to fetch the instances' configuration and to send the configuration to them.

    * The `http://` prefix is optional.
    * The port is optional and defaults to the value of the `API_HTTP_PORT` environment variable.
    * The default value of the `BUNKERWEB_INSTANCES` environment variable is `127.0.0.1`.

In other words, the new system is fully agnostic and generic: the scheduler is in charge of managing a list of BunkerWeb instances and doesn't need to care about the environment.

!!! tip "Autoconf/Kubernetes/Swarm integrations"

    If you are using the `Autoconf`, `Kubernetes`, or `Swarm` integrations, you can set the `BUNKERWEB_INSTANCES` environment variable to an empty string (so that it doesn't try to send the configuration to the default one which is `127.0.0.1`).

    **The instances will be automatically fetched by the controller**. You can also add custom instances to the list that may not be picked up by the controller.

Since the `1.6`, the Scheduler also have a new [built-in healthcheck system](concepts.md), that will check the health of the instances. If an instance becomes unhealthy, the scheduler will stop sending the configuration to it. If the instance becomes healthy again, the scheduler will start sending the configuration to it again.

#### BunkerWeb container

Another important change is that the **settings** that were previously declared on the BunkerWeb container **are now declared on the scheduler**. This means that you'll have to move your settings from the BunkerWeb container to the Scheduler container.

While the settings are now declared on the Scheduler container, **you'll still need to declare API-related mandatory settings on the BunkerWeb container** like the `API_WHITELIST_IP` setting which is used to whitelist the Scheduler's IP address, so that it can send the configuration to the instance. If you use `API_TOKEN`, you must also set it on the BunkerWeb container (and mirror it on the Scheduler) to allow authenticated API calls.

!!! warning "BunkerWeb's container settings"

    Every API related setting that you declare on the BunkerWeb container **have to be mirrored on the Scheduler container** so that it keeps working, as the configuration will be overwritten by the Scheduler's generated configuration.

#### Default values and new settings

We tried our best not to change default value but we have added many other settings. It's highly recommended to read the [security tuning](advanced.md#security-tuning) and [settings](features.md) sections of the documentation.

#### Templates

We added a new feature called **templates**. Templates provide a structured and standardized approach to defining settings and custom configurations, check the [concepts/templates](concepts.md#templates) section for more information.

#### Autoconf namespaces

We added a **namespace** feature to the autoconf integrations. Namespaces allow you to group your instances and apply settings only to them. Check the following sections according to your Integration for more information:

- [Autoconf/namespaces](integrations.md#namespaces)
- [Kubernetes/namespaces](integrations.md#namespaces_1)
- [Swarm/namespaces](integrations.md#namespaces_2)

### Procedure

1. **Backup the database**:
      - Before proceeding with the database upgrade, ensure that you perform a complete backup of the current state of the database.
      - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

    === "1\.5\.7 and later"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        === "Linux"

            ??? warning "Information for Red Hat Enterprise Linux (RHEL) 8.10 users"
                If you are using **RHEL 8.10** and plan on using an **external database**, you will need to install the `mysql-community-client` package to ensure the `mysqldump` command is available. You can install the package by executing the following commands:

                === "MySQL/MariaDB"

                    1. **Install the MySQL repository configuration package**

                        ```bash
                        sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                        ```

                    2. **Enable the MySQL repository**

                        ```bash
                        sudo dnf config-manager --enable mysql80-community
                        ```

                    3. **Install the MySQL client**

                        ```bash
                        sudo dnf install mysql-community-client
                        ```

                === "PostgreSQL"

                    4. **Install the PostgreSQL repository configuration package**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5. **Install the PostgreSQL client**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

    === "1\.5\.6 and earlier"

        === "SQLite"

            === "Docker"

                We first need to install the `sqlite` package in the container.

                ```bash
                docker exec -u 0 -it <scheduler_container> apk add sqlite
                ```

                Then, backup the database.

                ```bash
                docker exec -it <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

        === "MariaDB"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "MySQL"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it -e PGPASSWORD=<database_password> <database_container> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                PGPASSWORD=<database_password> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

2. **Upgrade BunkerWeb**:
      - Upgrade BunkerWeb to the latest version.

        === "Docker"

            1. **Update the Docker Compose file**: Update the Docker Compose file to use the new version of the BunkerWeb image.
                ```yaml
                services:
                    bunkerweb:
                        image: bunkerity/bunkerweb:1.6.7-rc1
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.6.7-rc1
                        ...
                ```

            2. **Restart the containers**: Restart the containers to apply the changes.
                ```bash
                docker compose down
                docker compose up -d
                ```

        === "Linux"

            3. **Stop the services**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            4. **Update BunkerWeb**:

                === "Debian/Ubuntu"

                    First, if you have previously held the BunkerWeb package, unhold it :

                    You can print a list of packages on hold with `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Then, you can update the BunkerWeb package :

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
                    ```

                    To prevent the BunkerWeb package from upgrading when executing `apt upgrade`, you can use the following command :

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    More details in the [integration Linux page](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    First, if you have previously held the BunkerWeb package, unhold it :

                    You can print a list of packages on hold with `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Then, you can update the BunkerWeb package :

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
                    ```

                    To prevent the BunkerWeb package from upgrading when executing `dnf upgrade`, you can use the following command :

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    More details in the [integration Linux page](integrations.md#__tabbed_1_3).

            5. **Start the services**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
                    ```
                    Or reboot the system:
                    ```bash
                    sudo reboot
                    ```


3. **Check the logs**: Check the logs of the scheduler service to ensure that the migration was successful.

    === "Docker"

        ```bash
        docker compose logs <scheduler_container>
        ```

    === "Linux"

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

4. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database container.

### Rollback

!!! failure "In case of issues"

    If you encounter any issues during the upgrade, you can rollback to the previous version of the database by restoring the backup taken in [step 1](#__tabbed_1_1).

    Get support and more information :

    - [Order professional support](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Create an issue on GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Join the BunkerWeb Discord server](https://discord.bunkerity.com)

=== "Docker"

    1. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restore the backup**.

        === "SQLite"

            1. **Remove the existing database file.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restore the backup.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Fix permissions.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restore the backup.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

    3. **Downgrade BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Start the containers**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Stop the services**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Restore the backup**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Start the services**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Downgrade BunkerWeb**.
        - Downgrade BunkerWeb to the previous version by following the same steps as when upgrading BunkerWeb in the [integration Linux page](integrations.md#linux)
