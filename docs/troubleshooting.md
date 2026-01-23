# Troubleshooting

!!! info "BunkerWeb Panel"
    If you are unable to resolve your issue, you can [contact us directly via our panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc). This centralizes all requests related to the BunkerWeb solution.

## Logs

When troubleshooting, logs are your best friends. We try our best to provide user-friendly logs to help you understand what's happening.

Please note that you can set the `LOG_LEVEL` to `info` (default: `notice`) to increase BunkerWeb’s verbosity.

Here is how you can access the logs, depending on your integration :

=== "Docker"

    !!! tip "List containers"
        To list the running containers, you can use the following command :
        ```shell
        docker ps
        ```

    You can use the `docker logs` command (replace `bunkerweb` with the name of your container) :
    ```shell
    docker logs bunkerweb
    ```

    Here is the docker-compose equivalent (replace `bunkerweb` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs bunkerweb
    ```

=== "Docker autoconf"

    !!! tip "List containers"
        To list the running containers, you can use the following command :
        ```shell
        docker ps
        ```

    You can use the `docker logs` command (replace `bunkerweb` and `bw-autoconf` with the name of your containers) :
    ```shell
    docker logs bunkerweb
    docker logs bw-autoconf
    ```

    Here is the docker-compose equivalent (replace `bunkerweb` and `bw-autoconf` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs bunkerweb
    docker-compose logs bw-autoconf
    ```

=== "All-in-one"

    !!! tip "Container name"
        The default container name for the All-in-one image is `bunkerweb-aio`. If you've used a different name, please adjust the command accordingly.

    You can use the `docker logs` command:
    ```shell
    docker logs bunkerweb-aio
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    !!! tip "List services"
        To list the services, you can use the following command :
        ```shell
        docker service ls
        ```

    You can use the `docker service logs` command (replace `bunkerweb` and `bw-autoconf` with the name of your services) :
    ```shell
    docker service logs bunkerweb
    docker service logs bw-autoconf
    ```

=== "Kubernetes"

    !!! tip "List pods"
        To list the pods, you can use the following command :
        ```shell
        kubectl get pods
        ```

    You can use the `kubectl logs` command (replace `bunkerweb` and `bunkerweb-controler` with the name of your pods) :
    ```shell
    kubectl logs bunkerweb
    kubectl logs bunkerweb-controler
    ```

=== "Linux"

    For errors related to BunkerWeb services (e.g., not starting), you can use `journalctl` :
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Common logs are located inside the `/var/log/bunkerweb` directory :
    ```shell
    cat /var/log/bunkerweb/error.log
    cat /var/log/bunkerweb/access.log
    ```

## Permissions

Don't forget that BunkerWeb runs as an unprivileged user for obvious security reasons. Double-check the permissions of files and folders used by BunkerWeb, especially if you use custom configurations (more info [here](advanced.md#custom-configurations)). You will need to set at least **_RW_** rights on files and **_RWX_** on folders.

## IP unban

You can manually unban an IP, which is useful when performing tests so that you can contact the internal API of BunkerWeb (replace `1.2.3.4` with the IP address to unban) :

=== "Docker / Docker Autoconf"

    You can use the `docker exec` command (replace `bw-scheduler` with the name of your container) :
    ```shell
    docker exec bw-scheduler bwcli unban 1.2.3.4
    ```

    Here is the docker-compose equivalent (replace `bw-scheduler` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose exec bw-scheduler bwcli unban 1.2.3.4
    ```

=== "All-in-one"

    !!! tip "Container name"
        The default container name for the All-in-one image is `bunkerweb-aio`. If you've used a different name, please adjust the command accordingly.

    You can use the `docker exec` command:
    ```shell
    docker exec bunkerweb-aio bwcli unban 1.2.3.4
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    You can use the `docker exec` command (replace `bw-scheduler` with the name of your service) :
    ```shell
    docker exec $(docker ps -q -f name=bw-scheduler) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    You can use the `kubectl exec` command (replace `bunkerweb-scheduler` with the name of your pod) :
    ```shell
    kubectl exec bunkerweb-scheduler bwcli unban 1.2.3.4
    ```

=== "Linux"

    You can use the `bwcli` command (as root) :
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

## False positives

### Detect only mode

For debugging/test purposes, you can set BunkerWeb in [detect only mode](features.md#security-modes) so it won't block request and will act as a classical reverse proxy.

### ModSecurity

The default BunkerWeb configuration of ModSecurity is to load the Core Rule Set in anomaly scoring mode with a paranoia level (PL) of 1 :

- Each matched rule will increase an anomaly score (so many rules can match a single request)
- PL1 includes rules with fewer chances of false positives (but less security than PL4)
- the default threshold for anomaly score is 5 for requests and 4 for responses

Let's take the following logs as an example of ModSecurity detection using default configuration (formatted for better readability) :

```log
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `lfi-os-files.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf"]
	[line "78"]
	[id "930120"]
	[rev ""]
	[msg "OS File Access Attempt"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-lfi"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/255/153/126"]
	[tag "PCI/6.5.4"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:utf8toUnicode,t:urlDecodeUni,t:normalizePathWin,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `unix-shell.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf"]
	[line "480"]
	[id "932160"]
	[rev ""]
	[msg "Remote Command Execution: Unix Shell Code Found"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-shell"]
	[tag "platform-unix"]
	[tag "attack-rce"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/152/248/88"]
	[tag "PCI/6.5.2"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:urlDecodeUni,t:cmdLine,t:normalizePath,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [error] 85#85: *11 [client 172.17.0.1] ModSecurity: Access denied with code 403 (phase 2). Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `10' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-949-BLOCKING-EVALUATION.conf"]
	[line "80"]
	[id "949110"]
	[rev ""]
	[msg "Inbound Anomaly Score Exceeded (Total Score: 10)"]
	[data ""]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-generic"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref ""],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
```

As we can see, there are 3 different logs :

1. Rule **930120** matched
2. Rule **932160** matched
3. Access denied (rule **949110**)

One important thing to understand is that rule **949110** is not a "real" one : it's the one that will deny the request because the anomaly threshold is reached (which is **10** in this example). You should never remove the **949110** rule !

If it's a false-positive, you should then focus on both **930120** and **932160** rules. ModSecurity and/or CRS tuning is out of the scope of this documentation but don't forget that you can apply custom configurations before and after the CRS is loaded (more info [here](advanced.md#custom-configurations)).

### Bad Behavior

A common false-positive case is when the client is banned because of the "bad behavior" feature which means that too many suspicious HTTP status codes were generated within a time period (more info [here](features.md#bad-behavior)). You should start by reviewing the settings and then edit them according to your web application(s) like removing a suspicious HTTP code, decreasing the count time, increasing the threshold, ...

### Whitelisting

If you have bots (or admins) that need to access your website, the recommended way to avoid any false positive is to whitelist them using the [whitelisting feature](features.md#whitelist). We don't recommend using the `WHITELIST_URI*` or `WHITELIST_USER_AGENT*` settings unless they are set to secret and unpredictable values. Common use cases are :

- Healthcheck / status bot
- Callback like IPN or webhook
- Social media crawler

## Common errors

### Upstream sent too big header

If you see the following error `upstream sent too big header while reading response header from upstream` in the logs, you will need to tweak the various proxy buffers size using the following settings :

- `PROXY_BUFFERS`
- `PROXY_BUFFER_SIZE`
- `PROXY_BUSY_BUFFERS_SIZE`

### Could not build server_names_hash

If you see the following error `could not build server_names_hash, you should increase server_names_hash_bucket_size` in the logs, you will need to tweak the `SERVER_NAMES_HASH_BUCKET_SIZE` setting.

## Timezone

When using container-based integrations, the timezone of the container may not match that of the host machine. To resolve that, you can set the `TZ` environment variable to the timezone of your choice on your containers (e.g. `TZ=Europe/Paris`). You will find the list of timezone identifiers [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List).

## Clear old instances from database {#clear-old-instances-db}

BunkerWeb stores known instances in the `bw_instances` table (primary key: `hostname`).
If you frequently redeploy, old rows may remain (for example, instances that haven’t checked in for a long time) and you may want to purge them.

!!! warning "Backup first"
    Before editing the database manually, create a backup (snapshot the SQLite volume or use your DB engine backup tools).

!!! warning "Stop writers"
    To avoid races while deleting, stop (or scale down) components that can update instances
    (typically the scheduler / autoconf depending on your deployment), run the cleanup, then start them again.

### Table and columns (reference)

The instance model is defined as:

- Table: `bw_instances`
- Primary key: `hostname`
- “Last seen” timestamp: `last_seen`
- Also contains:
  `name`, `port`, `listen_https`, `https_port`,
  `server_name`, `type`, `status`, `method`,
  `creation_date`

### 1 - Connect to the database

Use the existing [Access database](#access-database) section to connect
(SQLite / MariaDB / PostgreSQL).

### 2 - Dry-run: list stale instances

Pick a retention window (example: 90 days) and review what would be deleted.

=== "SQLite"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days')
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "MariaDB / MySQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY)
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "PostgreSQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days'
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

### 3 - Delete stale instances

Once verified, delete the rows.

=== "SQLite"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days');

    COMMIT;
    ```

=== "MariaDB / MySQL"

    ```sql
    START TRANSACTION;

    DELETE FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY);

    COMMIT;
    ```

=== "PostgreSQL"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days';

    COMMIT;
    ```

!!! tip "Delete by hostname"
    To delete a specific instance, use its hostname (the primary key).

    ```sql
    DELETE FROM bw_instances WHERE hostname = '<hostname>';
    ```

### 4 - Mark instances as changed (optional)

BunkerWeb tracks instance changes in the `bw_metadata` table
(`instances_changed`, `last_instances_change`).

If the UI does not refresh as expected after manual cleanup,
you can force a “change marker” update:

=== "SQLite / PostgreSQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = CURRENT_TIMESTAMP
    WHERE id = 1;
    ```

=== "MariaDB / MySQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = NOW()
    WHERE id = 1;
    ```

### 5 - Reclaim space (optional)

=== "SQLite"

    ```sql
    VACUUM;
    ```

=== "PostgreSQL"

    ```sql
    VACUUM (ANALYZE);
    ```

=== "MariaDB / MySQL"

    ```sql
    OPTIMIZE TABLE bw_instances;
    ```

## Web UI {#web-ui}

In case you forgot your UI credentials or are experiencing 2FA issues, you can connect to the database to regain access.

### Access database

=== "SQLite"

    === "Linux"

        Install SQLite (Debian/Ubuntu):

        ```shell
        sudo apt install sqlite3
        ```

        Install SQLite (Fedora/RedHat):

        ```shell
        sudo dnf install sqlite
        ```

    === "Docker"

        Get a shell into your scheduler container :

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory)
            - the `-it` options are to run the command interactively (mandatory)
            - `<bunkerweb_scheduler_container>` : the name or ID of your scheduler container

        ```shell
        docker exec -u 0 -it <bunkerweb_scheduler_container> bash
        ```

        Install SQLite :

        ```bash
        apk add sqlite
        ```

    === "All-in-one"

        Get a shell into your All-in-one container:

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory).
            - the `-it` options are to run the command interactively (mandatory).
            - `bunkerweb-aio` is the default container name; adjust if you used a custom name.

        ```shell
        docker exec -u 0 -it bunkerweb-aio bash
        ```

    Access your database :

    !!! note "Database path"
        We assume that you are using the default database path. If you are using a custom path, you will need to adapt the command.
        For All-in-one, we assume the database is `db.sqlite3` located in the persistent `/data` volume (`/data/db.sqlite3`).

    ```bash
    sqlite3 /var/lib/bunkerweb/db.sqlite3
    ```

    You should see something like this :

    ```text
    SQLite version <VER> <DATE>
    Enter ".help" for usage hints.
    sqlite>
    ```

=== "MariaDB / MySQL"

    !!! note "MariaDB / MySQL only"
        The following steps are only valid for MariaDB / MySQL databases. If you are using another database, please refer to the documentation of your database.

    !!! note "Credentials and database name"
        You will need to use the same credentials and database named used in the `DATABASE_URI` setting.

    === "Linux"

        Access your local database :

        ```bash
        mysql -u <user> -p <database>
        ```

        Then enter the database user’s password and you should be able to access your database.

    === "Docker"

        Access your database container :

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory)
            - the `-it` options are to run the command interactively (mandatory)
            - `<bunkerweb_db_container>` : the name or ID of your database container
            - `<user>` : the database user
            - `<database>` : the database name

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> mysql -u <user> -p <database>
        ```

        Then enter the database user’s password and you should be able to access your database.

    === "All-in-one"

        The All-in-One image does not include a MariaDB/MySQL server. If you have configured the AIO to use an external MariaDB/MySQL database (by setting the `DATABASE_URI` environment variable), you should connect to that database directly using standard MySQL client tools.

        The connection method would be similar to the "Linux" tab (if connecting from the host where AIO runs or another machine) or by running a MySQL client in a separate Docker container if preferred, targeting your external database's host and credentials.

=== "PostgreSQL"

    !!! note "PostgreSQL only"
        The following steps are only valid for PostgreSQL databases. If you are using another database, please refer to the documentation of your database.

    !!! note "Credentials, host and database name"
        You will need to use the same credentials (user/password), host and database name used in the `DATABASE_URI` setting.

    === "Linux"

        Access your local database:

        ```bash
        psql -U <user> -d <database>
        ```

        If your database is on another host, include the hostname/IP and port:

        ```bash
        psql -h <host> -p 5432 -U <user> -d <database>
        ```

        Then enter the database user’s password and you should be able to access your database.

    === "Docker"

        Access your database container:

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory)
            - the `-it` options are to run the command interactively (mandatory)
            - `<bunkerweb_db_container>` : the name or ID of your database container
            - `<user>` : the database user
            - `<database>` : the database name

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> psql -U <user> -d <database>
        ```

        If the database is hosted elsewhere, add the `-h <host>` and `-p 5432` options accordingly.

    === "All-in-one"

        The All-in-One image does not include a PostgreSQL server. If you have configured the AIO to use an external PostgreSQL database (by setting the `DATABASE_URI` environment variable), you should connect to that database directly using standard PostgreSQL client tools.

        The connection method would be similar to the "Linux" tab (if connecting from the host where AIO runs or another machine) or by running a PostgreSQL client in a separate Docker container if preferred, targeting your external database's host and credentials.

### Troubleshooting actions

!!! info "Tables schema"
    The schema of the `bw_ui_users` table is the following:

    | Field         | Type                                                | Null | Key | Default | Extra |
    | ------------- | --------------------------------------------------- | ---- | --- | ------- | ----- |
    | username      | varchar(256)                                        | NO   | PRI | NULL    |       |
    | email         | varchar(256)                                        | YES  | UNI | NULL    |       |
    | password      | varchar(60)                                         | NO   |     | NULL    |       |
    | method        | enum('ui','scheduler','autoconf','manual','wizard') | NO   |     | NULL    |       |
    | admin         | tinyint(1)                                          | NO   |     | NULL    |       |
    | theme         | enum('light','dark')                                | NO   |     | NULL    |       |
    | language      | varchar(2)                                          | NO   |     | NULL    |       |
    | totp_secret   | varchar(256)                                        | YES  |     | NULL    |       |
    | creation_date | datetime                                            | NO   |     | NULL    |       |
    | update_date   | datetime                                            | NO   |     | NULL    |       |

=== "Retrieve username"

    Execute the following command to extract data from the `bw_ui_users` table :

    ```sql
    SELECT * FROM bw_ui_users;
    ```

    You should see something like this :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

=== "Update admin user password"

    You first need to hash the new password using the bcrypt algorithm.

    Install the Python bcrypt library :

    ```shell
    pip install bcrypt
    ```

    Generate your hash (replace `mypassword` with your own password) :

    ```shell
    python3 -c 'from bcrypt import hashpw, gensalt ; print(hashpw(b"""mypassword""", gensalt(rounds=10)).decode("utf-8"))'
    ```

    You can update your username / password executing this command :

    ```sql
    UPDATE bw_ui_users SET password = '<password_hash>' WHERE admin = 1;
    ```

    If you check again your `bw_ui_users` table following this command :

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    You should see something like this :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

    You should now be able to use the new credentials to log into the web UI.

=== "Disable 2FA authentication for admin user"

    You can deactivate 2FA by executing this command :

    ```sql
    UPDATE bw_ui_users SET totp_secret = NULL WHERE admin = 1;
    ```

    If you check again your `bw_ui_users` table by following this command :

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    You should see something like this :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | NULL        | ***           | ***         |

    You should now be able to log into the web UI only using your username and password without 2FA.

=== "Refresh 2FA recovery codes"

    The recovery codes can be refreshed in your **profile page** of the web UI under the `Security` tab.

=== "Export configuration and anonymized logs"

    Use the **Support page** in the Web UI to quickly gather configuration and logs for troubleshooting.

    - Open the Web UI and go to the Support page.
    - Choose the scope: export the global settings or select a specific Service.
    - Click to download the configuration archive for the chosen scope.
    - Optionally download logs: the exported logs are automatically anonymized (all IP addresses and domains are masked).

### Upload plugin

It may not be possible to upload a plugin from the UI in certain situations:

- Missing package to manage compressed files on your integration, in which case you will need to add the necessary packages
- Safari browser : the 'safe mode' may prevent you from being able to add a plugin. You will need to make the necessary changes on your machine
