# Migrating

## Migrating from 1.4.X

!!! warning "Read this if you were a 1.4.X user"

    A lot of things changed since the 1.4.X releases. Container-based integrations stacks contain more services but, trust us, fundamental principles of BunkerWeb are still there. You will find ready to use boilerplates for various integrations in the [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.5.7/misc/integrations) folder of the repository.

### Scheduler

Back to the 1.4.X releases, jobs (like Let's Encrypt certificate generation/renewal or blacklists download) **were executed in the same container as BunkerWeb**. For the purpose of [separation of concerns](https://en.wikipedia.org/wiki/Separation_of_concerns), we decided to create a **separate service** which is now responsible for managing jobs.

Called **Scheduler**, this service also generates the final configuration used by BunkerWeb and acts as an intermediary between autoconf and BunkerWeb. In other words, the scheduler is the **brain of the BunkerWeb 1.5.X stack**.

You will find more information about the scheduler [here](concepts.md#scheduler).

### Database

BunkerWeb configuration is **no more stored in a plain file** (located at `/etc/nginx/variables.env` if you didn't know it). That's it, we now support a **fully-featured database as a backend** to store settings, cache, custom configs, ... 🥳

Using a real database offers many advantages :

- Backup of the current configuration
- Usage with multiple services (scheduler, web UI, ...)
- Upgrade to a new BunkerWeb version

Please note that we actually support, **SQLite**, **MySQL**, **MariaDB** and **PostgreSQL** as backends.

You will find more information about the database [here](concepts.md#database).

### Redis

When BunkerWeb 1.4.X was used in cluster mode (Swarm or Kubernetes integrations), **data were not shared among the nodes**. For example, if an attacker was banned via the "bad behavior" feature on a specific node, **he could still connect to the other nodes**.

Security is not the only reason to have a shared data store for clustered integrations, **caching** is also another one. We can now **store results** of time-consuming operations like (reverse) dns lookups so they are **available for other nodes**.

We actually support **Redis** as a backend for the shared data store.

See the list of [redis settings](settings.md#redis) and the corresponding documentation of your integration for more information.

### Default values and new settings

The default value of some settings have changed and we have added many other settings, we recommend you read the [security tuning](security-tuning.md) and [settings](settings.md) sections of the documentation.

## Migrating from 1.5.X

!!! warning "Read this if you were a 1.5.X user"

    We often add new features and settings to BunkerWeb. We recommend you read the [settings](settings.md) sections of the documentation or the GitHub releases to see what's new.

### Database

1. **Backup the database**:
      - Before proceeding with the database upgrade, ensure to perform a complete backup of the current state of the database.
      - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

    === "1\.5\.7 and later"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory -v /path/to/backup/directory:/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

        === "Linux"

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

        === "MySQL/MariaDB"

            === "Docker"

                ```bash
                docker exec -it <database_container> mysqldump -u <username> -p <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                mysqldump -u <username> -p <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it <database_container> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

2. **Upgrade BunkerWeb**:
      - Upgrade BunkerWeb to the latest version.

    === "Docker"

        1. **Update the Docker Compose file**: Update the Docker Compose file to use the new version of the BunkerWeb image.
            ```yaml
            services:
                bunkerweb:
                    image: bunkerity/bunkerweb:1.5.7
                    ...
                bw-scheduler:
                    image: bunkerity/bunkerweb-scheduler:1.5.7
                    ...
                bw-autoconf:
                    image: bunkerity/bunkerweb-autoconf:1.5.7
                    ...
                bw-ui:
                    image: bunkerity/bunkerweb-ui:1.5.7
                    ...
            ```

        2. **Restart the containers**: Restart the containers to apply the changes.
            ```bash
            docker compose down
            docker compose up -d
            ```

    === "Linux"

        1. **Stop the services**:
            ```bash
            systemctl stop bunkerweb-scheduler
            systemctl stop bunkerweb-ui
            ```

        2. **Update BunkerWeb**:
            - Update BunkerWeb to the latest version by following the instructions in the [integration Linux page](integrations.md#linux).


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

!!! failure "In case of issues"
    If you encounter any issues during the upgrade, you can rollback to the previous version of the database by restoring the backup taken in [step 1](#__tabbed_1_1).

    === "Docker"

        1. **Restore the backup**.

            === "SQLite"

                1. **Remove the existing database file.**

                    ```bash
                    docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                    ```

                2. **Restore the backup.**

                    ```bash
                    docker exec -i -T <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                    ```

            === "MySQL/MariaDB"

                3. **Stop the Scheduler container.**

                    ```bash
                    docker compose down <scheduler_container>
                    ```

                4. **Restore the backup.**

                    ```bash
                    docker exec -e MYSQL_PWD=<your_password> -i -T <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                    ```

            === "PostgreSQL"

                5. **Stop the Scheduler container.**

                    ```bash
                    docker compose down <scheduler_container>
                    ```

                6. **Remove the existing database.**

                    ```bash
                    docker exec -i <database_container> dropdb -U <username> --force <database_name>
                    ```

                7. **Recreate the database.**

                    ```bash
                    docker exec -i <database_container> createdb -U <username> <database_name>
                    ```

                8. **Restore the backup.**

                    ```bash
                    docker exec -i -T <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                    ```

        2. **Downgrade BunkerWeb**.

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

        3. **Restart the containers**.

            ```bash
            docker compose down
            docker compose up -d
            ```

    === "Linux"

        4. **Stop the services**.

            ```bash
            systemctl stop bunkerweb-scheduler
            systemctl stop bunkerweb-ui
            ```

        5. **Restore the backup**.

            === "SQLite"

                ```bash
                rm -f /var/lib/bunkerweb/db.sqlite3
                sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
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

        6. **Downgrade BunkerWeb**.
            - Downgrade BunkerWeb to the previous version by following the same steps as when upgrading BunkerWeb in the [integration Linux page](integrations.md#linux)

    - [Create an issue on GitHub](https://github.com/bunkerity/bunkerweb/issues/new?assignees=&labels=bug&projects=&template=bug_report.yml&title=%5BBUG%5D+)
    - [Join the BunkerWeb Discord server](https://discord.bunkerity.com)
