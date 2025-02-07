# Troubleshooting

!!! info "BunkerWeb Panel"
	If you are unable to resolve your problems, you can [contact us directly via our panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc). This centralises all requests relating to the BunkerWeb solution.

## Logs

When troubleshooting, logs are your best friends. We try our best to provide user-friendly logs to help you understand what's happening.

Please note that you can set `LOG_LEVEL` setting to `info` (default : `notice`) to increase the verbosity of BunkerWeb.

Here is how you can access the logs, depending on your integration :

=== "Docker"

    !!! tip "List containers"
    	To list the running containers, you can use the following command :
    	```shell
    	docker ps
    	```

    You can use the `docker logs` command (replace `mybunker` with the name of your container) :
    ```shell
    docker logs mybunker
    ```

    Here is the docker-compose equivalent (replace `mybunker` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs mybunker
    ```

=== "Docker autoconf"

    !!! tip "List containers"
    	To list the running containers, you can use the following command :
    	```shell
    	docker ps
    	```

    You can use the `docker logs` command (replace `mybunker` and `myautoconf` with the name of your containers) :
    ```shell
    docker logs mybunker
    docker logs myautoconf
    ```

    Here is the docker-compose equivalent (replace `mybunker` and `myautoconf` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs mybunker
    docker-compose logs myautoconf
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_1_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    !!! tip "List services"
    	To list the services, you can use the following command :
    	```shell
    	docker service ls
    	```

    You can use the `docker service logs` command (replace `mybunker` and `myautoconf` with the name of your services) :
    ```shell
    docker service logs mybunker
    docker service logs myautoconf
    ```

=== "Kubernetes"

    !!! tip "List pods"
    	To list the pods, you can use the following command :
    	```shell
    	kubectl get pods
    	```
    You can use the `kubectl logs` command (replace `mybunker` and `myautoconf` with the name of your pods) :
    ```shell
    kubectl logs mybunker
    kubectl logs myautoconf
    ```

=== "Linux"

    For errors related to BunkerWeb services (e.g. not starting), you can use `journalctl` :
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Common logs are located inside the `/var/log/bunkerweb` directory :
    ```shell
    cat /var/log/bunkerweb/error.log
    cat /var/log/bunkerweb/access.log
    ```

## Permissions

Don't forget that BunkerWeb runs as an unprivileged user for obvious security reasons. Double-check the permissions of files and folders used by BunkerWeb, especially if you use custom configurations (more info [here](advanced.md#custom-configurations)). You will need to set at least **RW** rights on files and **_RWX_** on folders.

## Disable security checks

For debugging purposes, you may need to temporarily disable the security checks made by BunkerWeb. One quick way of doing it is by adding everyone in the whitelist (e.g. `WHITELIST_IP=0.0.0.0/0`).

## ModSecurity

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

## Bad Behavior

A common false-positive case is when the client is banned because of the "bad behavior" feature which means that too many suspicious HTTP status codes were generated within a time period (more info [here](security-tuning.md#bad-behavior)). You should start by reviewing the settings and then edit them according to your web application(s) like removing a suspicious HTTP code, decreasing the count time, increasing the threshold, ...

## IP unban

You can manually unban an IP which can be useful when doing some tests but it needs the setting `USE_API` set to `yes` (which is not the default) so you can contact the internal API of BunkerWeb (replace `1.2.3.4` with the IP address to unban) :

=== "Docker"

    You can use the `docker exec` command (replace `mybunker` with the name of your container) :
    ```shell
    docker exec mybunker bwcli unban 1.2.3.4
    ```

    Here is the docker-compose equivalent (replace `mybunker` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose exec mybunker bwcli unban 1.2.3.4
    ```

=== "Docker autoconf"

    You can use the `docker exec` command (replace `myautoconf` with the name of your container) :
    ```shell
    docker exec myautoconf bwcli unban 1.2.3.4
    ```

    Here is the docker-compose equivalent (replace `myautoconf` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose exec myautoconf bwcli unban 1.2.3.4
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Docker autoconf integration](#__tabbed_2_2) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    You can use the `docker exec` command (replace `myautoconf` with the name of your service) :
    ```shell
    docker exec $(docker ps -q -f name=myautoconf) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    You can use the `kubectl exec` command (replace `myautoconf` with the name of your pod) :
    ```shell
    kubectl exec myautoconf bwcli unban 1.2.3.4
    ```

=== "Linux"

    You can use the `bwcli` command (as root) :
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

## Whitelisting

If you have bots that need to access your website, the recommended way to avoid any false positive is to whitelist them using the [whitelisting feature](security-tuning.md#blacklisting-whitelisting-and-greylisting). We don't recommend using the `WHITELIST_URI*` or `WHITELIST_USER_AGENT*` settings unless they are set to secret and unpredictable values. Common use cases are :

- Healthcheck / status bot
- Callback like IPN or webhook
- Social media crawler

## Timezone

When using container-based integrations, the timezone of the container may not match the one of the host machine. To resolve that, you can set the `TZ` environment variable to the timezone of your choice on your containers (e.g. `TZ=Europe/Paris`). You will find the list of timezone identifiers [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List).

## Web UI

In case you lost your UI credentials or have 2FA issues, you can connect to the database to retrieve access.

**Access database**

=== "SQLite"

    === "Linux"

        Install SQLite (Debian/Ubuntu) :

        ```shell
        sudo apt install sqlite3
        ```

        Install SQLite (Fedora/RedHat) :

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

    Access your database :

    !!! note "Database path"
        We assume that you are using the default database path. If you are using a custom path, you will need to adapt the command.

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

        Then enter your password of the database user and you should be able to access your database.

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

        Then enter your password of the database user and you should be able to access your database.

**Troubleshooting actions**

!!! info "Tables schema"
    The schema of the `bw_ui_users` table is the following :

    ```sql
    username VARCHAR(256) PRIMARY KEY NOT NULL
    email VARCHAR(256) UNIQUE DEFAULT NULL
    password VARCHAR(60) NOT NULL
    method ENUM('ui', 'scheduler', 'autoconf', 'manual', 'wizard') NOT NULL
    admin BOOLEAN NOT NULL DEFAULT 0
    theme ENUM('light', 'dark') NOT NULL DEFAULT 'light'
    totp_secret VARCHAR(256) DEFAULT NULL
    creation_date DATETIME NOT NULL
    update_date DATETIME NOT NULL
    ```

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

**Upload plugin**

It may not be possible to upload a plugin from the UI in certain situations:

- Missing package to manage compressed files on your integration, in which case you will need to add the necessary packages
- Safari browser : the 'safe mode' may prevent you from being able to add a plugin. You will need to make the necessary changes on your machine
