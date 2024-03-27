# Migrating

## Migrating from 1.4.X

!!! warning "Read this if you were a 1.4.X user"

    A lot of things changed since the 1.4.X releases. Container-based integrations stacks contain more services but, trust us, fundamental principles of BunkerWeb are still there. You will find ready to use boilerplates for various integrations in the [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.5.6/misc/integrations) folder of the repository.

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

=== "Docker"

    1. **Backup the database**:
        - Before proceeding with the database upgrade, ensure to perform a complete backup of the current state of the database.
        - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

    2. **Update the Docker Compose file**: Update the Docker Compose file to use the new version of the database image.

    3. **Restart the containers**: Restart the containers to apply the changes.
        ```bash
        docker-compose down
        docker-compose up -d
        ```

    4. **Check the logs**: Check the logs of the scheduler container to ensure that the migration was successful.
        ```bash
        docker-compose logs <your_scheduler_service_name>
        ```

    5. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database container.

    6. (Optional) **In case of issues**: If you encounter any issues during the upgrade, you can rollback to the previous version of the database by restoring the backup taken in **step 1**.

    7. (Optional) **Rollback if the restore fails**: If the restore fails, you can rollback to the previous version of the database by following these steps:

        1. Stop all containers.
            ```bash
            docker-compose down
            ```

        2. Connect to your database

        3. Drop the new tables created during the upgrade.
            ```sql
            DROP TABLE IF EXISTS bw_custom_configs;
            DROP TABLE IF EXISTS bw_global_values;
            DROP TABLE IF EXISTS bw_instances;
            DROP TABLE IF EXISTS bw_jobs;
            DROP TABLE IF EXISTS bw_jobs_cache;
            DROP TABLE IF EXISTS bw_metadata;
            DROP TABLE IF EXISTS bw_plugin_pages;
            DROP TABLE IF EXISTS bw_plugins;
            DROP TABLE IF EXISTS bw_selects;
            DROP TABLE IF EXISTS bw_services;
            DROP TABLE IF EXISTS bw_services_settings;
            DROP TABLE IF EXISTS bw_settings;
            DROP TABLE IF EXISTS bw_ui_users;
            ```

        4. Locate the old tables in the database backup and restore them.
            * SQLite:
                ```sql
                .tables
                ```
            * MySQL/MariaDB:
                ```sql
                SHOW TABLES;
                ```
            * PostgreSQL:
                ```sql
                \dt
                ```

        5. You should see tables with names like `<table_name>_<old_version>`. These are the old tables that were renamed during the upgrade.

        6. Rename the old tables to the original table names.
            ```sql
            ALTER TABLE <table_name>_<old_version> RENAME TO <table_name>;
            ```

     8. If you have any questions or need assistance, feel free to reach out to the BunkerWeb community for support.

        - [Create an issue on GitHub](https://github.com/bunkerity/bunkerweb/issues/new?assignees=&labels=bug&projects=&template=bug_report.yml&title=%5BBUG%5D+)
        - [Join the BunkerWeb Discord server](https://discord.bunkerity.com)


=== "Linux"

    1. **Backup the database**:
        - Before proceeding with the database upgrade, ensure to perform a complete backup of the current state of the database.
        - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

    2. **Update BunkerWeb**:
        - Update BunkerWeb to the latest version by following the instructions in the [integration Linux page](integrations.md#linux).

    3. **Check the logs**: Check the logs of the scheduler service to ensure that the migration was successful.
        ```bash
        journalctl -u bunkerweb-scheduler --no-pager
        ```

    4. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database.

    5. (Optional) **In case of issues**: If you encounter any issues during the upgrade, you can rollback to the previous version of the database by restoring the backup taken in **step 1**.

    6. (Optional) **Rollback if the restore fails**: If the restore fails, you can rollback to the previous version of the database by following these steps:

        1. Stop the BunkerWeb services.
            ```bash
            systemctl stop bunkerweb-scheduler
            systemctl stop bunkerweb-ui
            ```

        2. Connect to your database

        3. Drop the new tables created during the upgrade.
            ```sql
            DROP TABLE IF EXISTS bw_custom_configs;
            DROP TABLE IF EXISTS bw_global_values;
            DROP TABLE IF EXISTS bw_instances;
            DROP TABLE IF EXISTS bw_jobs;
            DROP TABLE IF EXISTS bw_jobs_cache;
            DROP TABLE IF EXISTS bw_metadata;
            DROP TABLE IF EXISTS bw_plugin_pages;
            DROP TABLE IF EXISTS bw_plugins;
            DROP TABLE IF EXISTS bw_selects;
            DROP TABLE IF EXISTS bw_services;
            DROP TABLE IF EXISTS bw_services_settings;
            DROP TABLE IF EXISTS bw_settings;
            DROP TABLE IF EXISTS bw_ui_users;
            ```

        4. Locate the old tables in the database backup and restore them.
            * SQLite:
                ```sql
                .tables
                ```
            * MySQL/MariaDB:
                ```sql
                SHOW TABLES;
                ```
            * PostgreSQL:
                ```sql
                \dt
                ```

        5. You should see tables with names like `<table_name>_<old_version>`. These are the old tables that were renamed during the upgrade.

        6. Rename the old tables to the original table names.
            ```sql
            ALTER TABLE <table_name>_<old_version> RENAME TO <table_name>;
            ```

    7. If you have any questions or need assistance, feel free to reach out to the BunkerWeb community for support.

        - [Create an issue on GitHub](https://github.com/bunkerity/bunkerweb/issues/new?assignees=&labels=bug&projects=&template=bug_report.yml&title=%5BBUG%5D+)
        - [Join the BunkerWeb Discord server](https://discord.bunkerity.com)
