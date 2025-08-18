# Web UI

## Overview

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The "Web UI" is a web application that helps you manage your BunkerWeb instance using a user-friendly interface instead of relying solely on the command line.

Here is a list of features offered by the web UI:

- Get a comprehensive view of blocked attacks
- Start, stop, restart, and reload your BunkerWeb instance
- Add, edit, and delete settings for your web applications
- Add, edit, and delete custom configurations for NGINX and ModSecurity
- Install and uninstall external plugins
- Explore cached files
- Monitor job execution and restart them as needed
- View logs and search for patterns

## Prerequisites

Since the web UI is a web application, the recommended architecture is to run BunkerWeb in front of it as a reverse proxy. The recommended installation procedure is to use the setup wizard, which will guide you step by step as described in the [quickstart guide](quickstart-guide.md).

!!! warning "Security considerations"

    The security of the web UI is extremely important. If an unauthorized person gains access to the application, not only will they be able to edit your configurations, but they might also execute code in the context of BunkerWeb (for example, via a custom configuration containing LUA code). We highly recommend that you follow minimal security best practices, such as:

    * Choose a strong password for the login (**at least 8 characters, including 1 lowercase letter, 1 uppercase letter, 1 digit, and 1 special character**)
    * Place the web UI under a "hard-to-guess" URI
    * Enable two-factor authentication (2FA)
    * Do not expose the web UI on the Internet without additional restrictions
    * Apply best practices listed in the [advanced usages section](advanced.md#security-tuning) of the documentation depending on your use case

## Upgrade to PRO

!!! tip "BunkerWeb PRO free trial"
    Want to quickly test BunkerWeb PRO for one month? Use the code `freetrial` when placing your order on the [BunkerWeb panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) or by clicking [here](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) to directly to apply the promo code (will be effective at checkout).

Once you have your PRO license key from the [BunkerWeb panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), you can paste it into the PRO page of the web UI.

<figure markdown>
  ![PRO upgrade](assets/img/pro-ui-upgrade.png){ align=center, width="700" }
  <figcaption>Upgrade to PRO from the web UI</figcaption>
</figure>

!!! warning "Upgrade time"
    The PRO version is downloaded in the background by the scheduler, it may take some time to upgrade.

When your BunkerWeb instance has upgraded to the PRO version, you will see your license expiration date and the maximum number of services you can protect.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO license information</figcaption>
</figure>

## Accessing logs

Beginning with version `1.6`, the method of accessing logs has changed. This update specifically impacts container-based integrations: the web UI will now read the log files from the `/var/log/bunkerweb` directory.

To keep the logs accessible from the web UI, we recommend that you use a syslog server, such as `syslog-ng`, to read the logs and create the corresponding files in the `/var/log/bunkerweb` directory.

!!! warning "Using local folder for logs"
    The web UI runs as an **unprivileged user with UID 101 and GID 101** inside the container for security reasons: in case a vulnerability is exploited, the attacker won't have full root (UID/GID 0) privileges.

    However, there is a downside: if you use a **local folder for logs**, you must **set the correct permissions** so that the unprivileged user can read the log files. For example:

    ```shell
    mkdir bw-logs && \
    chown root:101 bw-logs && \
    chmod 770 bw-logs
    ```

    Alternatively, if the folder already exists:

    ```shell
    chown -R root:101 bw-logs && \
    chmod -R 770 bw-logs
    ```

    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [podman](https://podman.io/), UIDs and GIDs in the container will be mapped to different ones in the host. You will first need to check your initial subuid and subgid:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    For example, if you have a value of **100000**, the mapped UID/GID will be **100100** (100000 + 100):

    ```shell
    mkdir bw-logs && \
    sudo chgrp 100100 bw-logs && \
    chmod 770 bw-logs
    ```

    Or if the folder already exists:

    ```shell
    sudo chgrp -R 100100 bw-logs && \
    sudo chmod -R 770 bw-logs
    ```

### Compose boilerplates

=== "Docker"

    To forward the logs correctly to the `/var/log/bunkerweb` directory on the Docker integration, you will need to stream the logs to a file using `syslog-ng`. Here is an example of how to do this:

    ```yaml
    x-bw-env: &bw-env
      # We anchor the environment variables to avoid duplication
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.4
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Change it to a hard-to-guess URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.4
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the admin user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-syslog:
        image: balabit/syslog-ng:4.8.0
        # image: lscr.io/linuxserver/syslog-ng:4.8.1-r1-ls147 # For aarch64 architecture
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Make sure to set the correct IP address

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"

    To forward the logs correctly to the `/var/log/bunkerweb` directory on the Autoconf integration, you will need to stream the logs to a file using `syslog-ng`. Here is an example of how to do this:

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.4
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf / ui
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.4
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375" # This is the Docker socket address
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-autoconf" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.4
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the admin user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme" # Change it to a hard-to-guess URI
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: "unless-stopped"
        networks:
          - bw-docker

      bw-syslog:
        image: balabit/syslog-ng:4.8.0
        # image: lscr.io/linuxserver/syslog-ng:4.8.1-r1-ls147 # For aarch64 architecture
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Make sure to set the correct IP address

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

### Syslog-ng configuration

Here is an example of a `syslog-ng.conf` file that you can use to forward the logs to a file:

```conf
@version: 4.8

# Source configuration to receive logs from Docker containers
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Template to format log messages
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Destination configuration to write logs to dynamically named files
destination d_dyna_file {
  file(
    "/var/log/bunkerweb/${PROGRAM}.log"
    template(t_imp)
    owner("101")
    group("101")
    dir_owner("root")
    dir_group("101")
    perm(0440)
    dir_perm(0770)
    create_dirs(yes)
  );
};

# Log path to direct logs to dynamically named files
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Account management

You can access the account management page by clicking on the profile image in the top right corner:

<figure markdown>
  ![Overview](assets/img/manage-account.png){ align=center, width="400" }
  <figcaption>Account page access from top right corner</figcaption>
</figure>

### Username / Password

!!! warning "Lost password/username"

    In case you forgot your UI credentials, you can reset them from the CLI following [the steps described in the troubleshooting section](troubleshooting.md#web-ui).

You can update your username or password by filling the dedicated forms in the **Security** tab. For security reason, you need to enter your current password even if you are connected.

Please note that when your username or password is updated, you will be logout from the web UI to log in again.

<figure markdown>
  ![Overview](assets/img/profile-username-password.png){ align=center, width="650" }
  <figcaption>Username / Password form</figcaption>
</figure>

### Two-Factor authentication

!!! tip "Mandatory encryption keys"

    When enabling 2FA, you must provide at least one encryption key. This key will be used to encrypt your TOTP secrets.

    The recommended way to generate a valid key is to use the `passlib` package:

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Set the generated key in the `TOTP_ENCRYPTION_KEYS` environment variable of the web UI. You can also set multiple keys separated by spaces or as a dictionary (for backward compatibility).

!!! warning "Lost secret key"

    In case you lost your secret key, two options are available:

    - You can recover your account using one of the provided recovery codes when you enabled 2FA (a recovery code can only be used once).
    - You can disable 2FA from the CLI following [the steps described in the troubleshooting section](troubleshooting.md#web-ui).

You can power-up your login security by adding **Two-Factor Authentication (2FA)** to your account. By doing so, an extra code will be needed in addition to your password.

The web UI uses [Time based One Time Password (TOTP)](https://en.wikipedia.org/wiki/Time-based_one-time_password) as 2FA implementation: using a **secret key**, the algorithm will generate **one time passwords only valid for a short period of time**.

Any TOTP client such as Google Authenticator, Authy, FreeOTP, ... can be used to store the secret key and generate the codes. Please note that once TOTP is enabled, **you won't be able to retrieve it from the web UI**.

The following steps are needed to enable the TOTP feature from the web UI:

- Copy the secret key or use the QR code on your authenticator app
- Enter the current TOTP code in the 2FA input
- Enter your current password

!!! info "Secret key refresh"
    A new secret key is **generated each time** you visit the page or submit the form. In case something went wrong (e.g.: expired TOTP code), you will need to copy the new secret key to your authenticator app until 2FA is successfully enabled.

!!! tip "Recovery codes"

    When you enable 2FA, you will be provided with **5 recovery codes**. These codes can be used to recover your account in case you have lost your TOTP secret key. Each code can only be used once. **These codes will only be shown once so make sure to store them in a safe place**.

    If you ever lose your recovery codes, **you can refresh them via the TOTP section of the account management page**. Please note that the old recovery codes will be invalidated.

You can enable or disable 2FA and also refresh recovery codes in the **Security** tab:

<figure markdown>
  ![Overview](assets/img/profile-totp.png){ align=center, width="800" }
  <figcaption>TOTP enable / disable / refresh recovery codes forms</figcaption>
</figure>

After a successful login/password combination, you will be prompted to enter your TOTP code:

<figure markdown>
  ![Overview](assets/img/profile-2fa.png){ align=center, width="400" }
  <figcaption>2FA on login page</figcaption>
</figure>

### Current sessions

In the **Session** tab, you will be able to list and revoke current sessions:

<figure markdown>
  ![Overview](assets/img/sessions.png){ align=center, width="800" }
  <figcaption>Manage sessions</figcaption>
</figure>

## Advanced installation

The web UI can be deployed and configured without going through the setup wizard process: configuration is done through environment variables, which can be added directly to the containers or in the `/etc/bunkerweb/ui.env` file in the case of a Linux integration.

!!! tip "Web UI specific environment variables"

    The web UI uses the following environment variables:

    - `OVERRIDE_ADMIN_CREDS`: set it to `yes` to enable the override even if the admin credentials are already set (default is `no`).
    - `ADMIN_USERNAME`: username to access the web UI.
    - `ADMIN_PASSWORD`: password to access the web UI.
    - `FLASK_SECRET`: a secret key used to encrypt the session cookie (if not set, a random key will be generated).
    - `TOTP_ENCRYPTION_KEYS` (or `TOTP_SECRETS`): a list of TOTP encryption keys separated by spaces or a dictionary (e.g.: `{"1": "mysecretkey"}` or `mysecretkey` or `mysecretkey mysecretkey1`). **We strongly recommend you to set this variable if you want to use 2FA, as it will be used to encrypt the TOTP secret keys** (if not set, a random number of secret keys will be generated). Check out the [passlib documentation](https://passlib.readthedocs.io/en/stable/narr/totp-tutorial.html#application-secrets) for more information.
    - `LISTEN_ADDR`: the address where the web UI will listen (default is `0.0.0.0` in **Docker images** and `127.0.0.1` on **Linux installations**).
    - `LISTEN_PORT`: the port where the web UI will listen (default is `7000`).
    - `MAX_WORKERS`: the number of workers used by the web UI (default is the number of CPUs).
    - `MAX_THREADS`: the number of threads used by the web UI (default is `MAX_WORKERS` * 2).
    - `FORWARDED_ALLOW_IPS`: a list of IP addresses or networks that are allowed to be used in the `X-Forwarded-For` header (default is `*` in **Docker images** and `127.0.0.1` on **Linux installations**).
    - `CHECK_PRIVATE_IP`: set it to `yes` to not disconnect users that have their IP address changed during a session if they are in a private network (default is `yes`). (Non-private IP addresses are always checked).
    - `ENABLE_HEALTHCHECK`: set it to `yes` to enable the `/healthcheck` endpoint that returns a simple JSON response with status information (default is `no`).

    The web UI will use these variables to authenticate you and handle the 2FA feature.

!!! example "Generating recommended secrets"

    To generate a valid **ADMIN_PASSWORD**, we recommend you to **use a password manager** or a **password generator**.

    You can generate a valid **FLASK_SECRET** using the following command:

    ```shell
    python3 -c "import secrets; print(secrets.token_hex(64))"
    ```

    You can generate valid space-separated **TOTP_ENCRYPTION_KEYS** using the following command (you will need the `passlib` package):

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

=== "Linux"

    The installation of the web UI using the [Linux integration](integrations.md#linux) is pretty straightforward because it is installed with BunkerWeb.

    The web UI comes as systemd service named `bunkerweb-ui`, please ensure that it's enabled:

    ```shell
    sudo systemctl enable bunkerweb-ui && \
    sudo systemctl status bunkerweb-ui
    ```

    A dedicated environment file located at `/etc/bunkerweb/ui.env` is used to configure the web UI:

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    TOTP_ENCRYPTION_KEYS=mysecret
    ```

    Replace the `changeme` data with your own values.

    Remember to set a stronger secret key for the `TOTP_ENCRYPTION_KEYS`.

    Each time you edit the `/etc/bunkerweb/ui.env` file, you will need to restart the service:

    ```shell
    systemctl restart bunkerweb-ui
    ```

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). Please note that the web UI is listening on the `7000` port and only on the loopback interface.

    Here is the `/etc/bunkerweb/variables.env` boilerplate you can use:

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_TEMPLATE=ui
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    ```

    Don't forget to reload the `bunkerweb` service:

    ```shell
    systemctl reload bunkerweb
    ```

=== "Docker"

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui):

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternatively, you can also build it yourself:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.4/misc/integrations) of the repository.

    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data):

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.4
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # We mirror the API_WHITELIST_IP from the bunkerweb service
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Remember to set a stronger URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000" # The web UI container is listening on the 7000 port by default
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.4
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-db

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui):

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternatively, you can also build it yourself:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "Environment variables"

        Please read the [Prerequisites](#prerequisites) section to check out all the environment variables you can set to customize the web UI.

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler and autoconf) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.4/misc/integrations) of the repository.

    Here is the docker-compose boilerplate that you can use (don't forget to edit the `changeme` data):

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        labels:
          - "bunkerweb.INSTANCE=yes" # We set the instance label to allow the autoconf to detect the instance
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.4
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.4
        depends_on:
          - bw-docker
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.4
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        networks:
          - bw-universe
          - bw-db

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-docker:
        name: bw-docker
      bw-db:
        name: bw-db
    ```

=== "Kubernetes"

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) and you can deploy as a standard [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). Network segmentation between web UI and web services is not covered in this documentation. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the yaml files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.4/misc/integrations) of the repository.

    Here is the corresponding part of your values.yaml file that you can use:

    ```yaml
    settings:
      # Use an existing secret named bunkerweb and containing the following values:
      # - admin-username
      # - admin-password
      # - flask-secret
      # - totp-secrets
      existingSecret: "secret-bunkerweb"
    ui:
      wizard: false
      ingress:
        enabled: true
        serverName: "www.example.com"
        serverPath: "/admin"
      overrideAdminCreds: "yes"
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    The web UI can be deployed using a dedicated container which is available on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui):

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternatively, you can also build it yourself:

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    Accessing the web UI through BunkerWeb is a classical [reverse proxy setup](quickstart-guide.md). We recommend you to connect BunkerWeb and web UI using a dedicated network (like `bw-universe` also used by the scheduler and autoconf) so it won't be on the same network of your web services for obvious security reasons. Please note that the web UI container is listening on the `7000` port.

    !!! info "Database backend"

        If you want another Database backend than MariaDB please refer to the stack files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.4/misc/integrations) of the repository.

    Here is the stack boilerplate that you can use (don't forget to edit the `changeme` data):

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.4
        ports:
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: tcp
          - published: 443
            target: 8443
            mode: host
            protocol: udp # For QUIC / HTTP3 support
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.4
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.4
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONFIGS: "1"
          CONTAINERS: "1"
          SERVICES: "1"
          SWARM: "1"
          TASKS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker
        deploy:
          placement:
            constraints:
              - "node.role == manager"

      bw-db:
        image: mariadb:11
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-db

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.4
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        networks:
          - bw-universe
          - bw-db
        deploy:
          labels:
            - "bunkerweb.SERVER_NAME=www.example.com"
            - "bunkerweb.USE_TEMPLATE=ui"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_URL=/changeme"
            - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        driver: overlay
        attachable: true
        ipam:
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
        driver: overlay
        attachable: true
      bw-docker:
        name: bw-docker
        driver: overlay
        attachable: true
      bw-db:
        name: bw-db
        driver: overlay
        attachable: true
    ```

## Language Support & Localization

The BunkerWeb UI supports multiple languages. Translations are managed in the `src/ui/app/static/locales` directory. The following languages are currently available:

- English (en)
- French (fr)
- Arabic (ar)
- Bengali (bn)
- Spanish (es)
- Hindi (hi)
- Portuguese (pt)
- Russian (ru)
- Urdu (ur)
- Chinese (zh)
- German (de)
- Italian (it)

See the [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.4/src/ui/app/static/locales/README.md) for details on translation provenance and review status.

### Contributing Translations

We welcome contributions to improve or add new locale files!

**How to contribute a translation:**

1. Edit the `src/ui/app/lang_config.py` file to add your language (code, name, flag, english_name).
2. Copy `en.json` as a template in `src/ui/app/static/locales/`, rename it to your language code (e.g., `de.json` for German).
3. Translate the values in your new file.
4. Update the table in `locales/README.md` to add your language and indicate who created/reviewed it.
5. Submit a pull request.

For updates, edit the relevant file and update the provenance table as needed.

See the [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.4/src/ui/app/static/locales/README.md) for full guidelines.
