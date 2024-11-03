# Integrations

## BunkerWeb Cloud

<figure markdown>
  ![Overview](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

!!! example "Beta phase"
    BunkerWeb Cloud offer is in beta phase. We are actively getting feedbacks from our precious beta tester to improve the offer.

BunkerWeb Cloud is the easiest way to get started with BunkerWeb. It offers you a fully managed BunkerWeb service with no hassle. Think of a like a BunkerWeb-as-a-Service !

You will find more information about BunkerWeb Cloud beta [here](https://www.bunkerweb.io/cloud?utm_campaign=self&utm_source=docs) and you can apply for free [in the BunkerWeb panel](https://panel.bunkerweb.io/order/bunkerweb-cloud/14?utm_campaign=self&utm_source=docs).

## Docker

<figure markdown>
  ![Overview](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker integration</figcaption>
</figure>

Utilizing BunkerWeb as a [Docker](https://www.docker.com/) container offers a convenient and straightforward approach for testing and utilizing the solution, particularly if you are already familiar with Docker technology.

To facilitate your Docker deployment, we provide readily available prebuilt images on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb), supporting multiple architectures. These prebuilt images are optimized and prepared for use on the following architectures:

- x64 (64-bit)
- x86
- armv8 (ARM 64-bit)
- armv7 (ARM 32-bit)

By accessing these prebuilt images from Docker Hub, you can quickly pull and run BunkerWeb within your Docker environment, eliminating the need for extensive configuration or setup processes. This streamlined approach allows you to focus on leveraging the capabilities of BunkerWeb without unnecessary complexities.

Whether you're conducting tests, developing applications, or deploying BunkerWeb in production, the Docker containerization option provides flexibility and ease of use. Embracing this method empowers you to take full advantage of BunkerWeb's features while leveraging the benefits of Docker technology.

```shell
docker pull bunkerity/bunkerweb:1.6.0-beta
```

Docker images are also available on [GitHub packages](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) and can be downloaded using the `ghcr.io` repository address :

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.0-beta
```

Alternatively, if you prefer a more hands-on approach, you have the option to build the Docker image directly from the [source](https://github.com/bunkerity/bunkerweb). Building the image from source gives you greater control and customization over the deployment process. However, please note that this method may take some time to complete, depending on your hardware configuration.

While the image is being built, you can take a moment to relax and enjoy a cup of coffee ☕, as the process may require some patience. Once the image is successfully built, you can proceed to deploy and utilize BunkerWeb within your Docker environment. This method allows you to tailor the image to your specific requirements and ensures a more personalized deployment of BunkerWeb.

So, whether you choose to use the ready-to-use prebuilt images or embark on the journey of building the image from source, BunkerWeb in Docker provides you with the flexibility and options to seamlessly integrate it into your environment.

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t my-bunkerweb -f src/bw/Dockerfile .
```

Docker integration key concepts are :

- **Environment variables** to configure BunkerWeb
- **Scheduler** container to store configuration and execute jobs
- **Networks** to expose ports for clients and connect to upstream web services

When integrating BunkerWeb with Docker, there are key concepts to keep in mind, ensuring a smooth and efficient deployment:

- **Environment variables**: BunkerWeb can be easily configured using environment variables. These variables allow you to customize various aspects of BunkerWeb's behavior, such as network settings, security options, and other parameters.

- **Scheduler container**: To effectively manage the configuration and execution of jobs, BunkerWeb utilizes a dedicated container called the [scheduler](concepts.md#scheduler).

- **Networks**: Docker networks play a vital role in the integration of BunkerWeb. These networks serve two main purposes: exposing ports to clients and connecting to upstream web services. By exposing ports, BunkerWeb can accept incoming requests from clients, allowing them to access the protected web services. Additionally, by connecting to upstream web services, BunkerWeb can efficiently route and manage the traffic, providing enhanced security and performance.

!!! info "Database backend"
    Please be aware that our instructions assume you are using SQLite as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-beta/misc/integrations) folder of the repository for more information.

### Environment variables

Settings are passed to the Scheduler using Docker environment variables :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.0-beta
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
...
```

!!! info "Full list"
    For the complete list of environment variables, see the [settings section](settings.md) of the documentation.

### Scheduler

The [scheduler](concepts.md#scheduler) is executed in its own container which is also available on Docker Hub :

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.0-beta
```

Alternatively, you can build the Docker image directly from the [source](https://github.com/bunkerity/bunkerweb) (less coffee ☕ needed than the BunkerWeb image) :

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t my-scheduler -f src/scheduler/Dockerfile .
```

!!! info "BunkerWeb settings"

    Since the `1.6.0-beta` version, the Scheduler container is the one who you will define the settings for BunkerWeb. The Scheduler will then push the configuration to the BunkerWeb container.

    ⚠ **Important** : All API related settings (like `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME` and `API_WHITELIST_IP`) **must be defined in the BunkerWeb container as well**. (The settings have to be mirrored in both containers, else the BunkerWeb container will not accept API requests from the Scheduler).

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for both containers
      API_HTTP_PORT: "5000" # Default value
      API_LISTEN_IP: "0.0.0.0" # Default value
      API_SERVER_NAME: "bwapi" # Default value
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Set this according to your network settings

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-beta
        environment:
          # This will set the API settings for the BunkerWeb container
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.0-beta
        environment:
          # This will set the API settings for the Scheduler container
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```


A volume is needed to store the SQLite database that will be used by the scheduler :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.0-beta
    volumes:
      - bw-data:/data
...
volumes:
  bw-data:
```

!!! warning "Using local folder for persistent data"
    The scheduler runs as an **unprivileged user with UID 101 and GID 101** inside the container. The reason behind this is security : in case a vulnerability is exploited, the attacker won't have full root (UID/GID 0) privileges.
    But there is a downside : if you use a **local folder for the persistent data**, you will need to **set the correct permissions** so the unprivileged user can write data to it. Something like that should do the trick :

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternatively, if the folder already exists :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [podman](https://podman.io/), UIDs and GIDs in the container will be mapped to different ones in the host. You will first need to check your initial subuid and subgid :

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    For example, if you have a value of **100000**, the mapped UID/GID will be **100100** (100000 + 100) :

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

	  Or if the folder already exists :

	  ```shell
    sudo chgrp -R 100100 bw-data && \
    chmod -R 770 bw-data
    ```

### Networks

By default, BunkerWeb container is listening (inside the container) on **8080/tcp** for **HTTP**, **8443/tcp** for **HTTPS** and **8443/udp** for **QUIC**.

!!! warning "Privileged ports in rootless mode or when using podman"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) and want to redirect privileged ports (< 1024) like 80 and 443 to BunkerWeb, please refer to the prerequisites [here](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    If you are using [podman](https://podman.io/) you can lower the minimum number for unprivileged ports :
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

The typical BunkerWeb stack when using the Docker integration contains the following containers :

- BunkerWeb
- Scheduler
- Your services

For defense in depth purposes, we strongly recommend to create at least three different Docker networks :

- `bw-services` : for BunkerWeb and your web services
- `bw-universe` : for BunkerWeb and scheduler

To secure the communication between the scheduler and BunkerWeb API, **it is important to authorize API calls**. You can use the `API_WHITELIST_IP` setting to specify allowed IP addresses and subnets.

**It is strongly recommended to use a static subnet for the `bw-universe` network** to enhance security. By implementing these measures, you can ensure that only authorized sources can access the BunkerWeb API, reducing the risk of unauthorized access or malicious activities:

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.0-beta
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-services
      - bw-universe
...
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.0-beta
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
    restart: "unless-stopped"
    networks:
      - bw-universe
...
networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # Static subnet so only authorized sources can access the BunkerWeb API
  bw-services:
    name: bw-services
```

### Full compose file

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.0-beta
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.0-beta
    depends_on:
      - bunkerweb
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-data:/data
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-data:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # Static subnet so only authorized sources can access the BunkerWeb API
  bw-services:
    name: bw-services
```

## Linux

<figure markdown>
  ![Overview](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Linux integration</figcaption>
</figure>

Supported Linux distributions for BunkerWeb (amd64/x86_64 and arm64/aarch64 architectures) include:

- Debian 12 "Bookworm"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41
- Red Hat Enterprise Linux (RHEL) 8.9
- Red Hat Enterprise Linux (RHEL) 9.4

Please ensure that you have **NGINX 1.26.2 installed before installing BunkerWeb**. For all distributions, except Fedora, it is mandatory to use prebuilt packages from the [official NGINX repository](https://nginx.org/en/linux_packages.html). Compiling NGINX from source or using packages from different repositories will not work with the official prebuilt packages of BunkerWeb. However, you have the option to build BunkerWeb from source.

=== "Debian"

    The first step is to add NGINX official repository :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.26.2 :

    ```shell
    sudo apt update && \
    sudo apt install -y nginx=1.26.2-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    Optional step : if you don't want to use the automatically enabled [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=no
    ```

    And finally install BunkerWeb 1.6.0-beta :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y bunkerweb=1.6.0-beta
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    The first step is to add NGINX official repository :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.26.2 :

    ```shell
    sudo apt update && \
    sudo apt install -y nginx=1.26.2-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    Optional step : if you don't want to use the automatically enabled [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=no
    ```

    And finally install BunkerWeb 1.6.0-beta :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y bunkerweb=1.6.0-beta
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora Update Testing"
        If you can't find the NGINX version listed in the stable repository, you can enable the `updates-testing` repository :

        ```shell
        sudo dnf config-manager --set-enabled updates-testing
        ```

    Fedora already provides NGINX 1.26.2 that we support :

    ```shell
    sudo dnf install -y nginx-1.26.2
    ```

    Optional step : if you don't want to use the automatically enabled [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=no
    ```

    And finally install BunkerWeb 1.6.0-beta :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | \
  	sed 's/yum install -y pygpgme --disablerepo='\''bunkerity_bunkerweb'\''/yum install -y python-gnupg/g' | \
  	sed 's/pypgpme_check=`rpm -qa | grep -qw pygpgme`/python-gnupg_check=`rpm -qa | grep -qw python-gnupg`/g' | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y bunkerweb-1.6.0-beta
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    The first step is to add NGINX official repository. Create the following file at `/etc/yum.repos.d/nginx.repo` :

    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true

    [nginx-mainline]
    name=nginx mainline repo
    baseurl=http://nginx.org/packages/mainline/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=0
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
    ```

    You should now be able to install NGINX 1.26.2 :

    ```shell
    sudo dnf install nginx-1.26.2
    ```

    Optional step : if you don't want to use the automatically enabled [setup wizard](web-ui.md#setup-wizard) when BunkerWeb is installed, export the following variable :

    ```shell
    export UI_WIZARD=no
    ```

    And finally install BunkerWeb 1.6.0-beta :

    ```shell
	  sudo dnf install -y epel-release && \
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y bunkerweb-1.6.0-beta
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

The configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file :

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

BunkerWeb is managed using systemctl :

- Check BunkerWeb status : `systemctl status bunkerweb`
- Start it if it's stopped : `systemctl start bunkerweb`
- Stop it if it's started : `systemctl stop bunkerweb`
- Reload it to apply new configuration : `systemctl reload bunkerweb`
- And restart it : `systemctl restart bunkerweb`

## Docker autoconf

<figure markdown>
  ![Overview](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Docker autoconf integration</figcaption>
</figure>

!!! info "Docker integration"
    The Docker autoconf integration is an "evolution" of the Docker one. Please read the [Docker integration section](#docker) first if needed.

An alternative approach is available to address the inconvenience of recreating the container every time there is an update. By utilizing another image called **autoconf**, you can automate the real-time reconfiguration of BunkerWeb without the need for container recreation.

To leverage this functionality, instead of defining environment variables for the BunkerWeb container, you can add **labels** to your web application containers. The **autoconf** image will then listen for Docker events and seamlessly handle the configuration updates for BunkerWeb.

This "*automagical*" process simplifies the management of BunkerWeb configurations. By adding labels to your web application containers, you can delegate the reconfiguration tasks to **autoconf** without the manual intervention of container recreation. This streamlines the update process and enhances convenience.

By adopting this approach, you can enjoy real-time reconfiguration of BunkerWeb without the hassle of container recreation, making it more efficient and user-friendly.

!!! info "Multisite mode"
    The Docker autoconf integration implies the use of **multisite mode**. Please refer to the [multisite section](concepts.md#multisite-mode) of the documentation for more information.

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-beta/misc/integrations) folder of the repository for more information.

To enable automated configuration updates, include an additional container called `bw-autoconf` in the stack. This container hosts the autoconf service, which manages dynamic configuration changes for BunkerWeb.

To support this functionality, use a dedicated "real" database backend (e.g., MariaDB, MySQL, or PostgreSQL) for synchronized configuration storage. By integrating `bw-autoconf` and a suitable database backend, you establish the infrastructure for seamless automated configuration management in BunkerWeb.

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both containers
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.0-beta
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    labels:
      - "bunkerweb.INSTANCE=yes" # Mandatory label for the autoconf service to identify the BunkerWeb instance
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.0-beta
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
    volumes:
      - bw-data:/data # This is used to persist data like the backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.0-beta
    depends_on:
      - bunkerweb
      - bw-docker
    environment:
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
    restart: "unless-stopped"
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
    restart: "unless-stopped"
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
      - bw-db:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db

volumes:
  bw-data:
  bw-db:

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

!!! info "Database in the `bw-db` network"
    The database container is intentionally not included in the `bw-universe` network. It is used by the `bw-autoconf` and `bw-scheduler` containers rather than directly by BunkerWeb. Therefore, the database container is part of the `bw-db` network, which enhances security by making external access to the database more challenging. **This deliberate design choice helps safeguard the database and strengthens the overall security perspective of the system**.

!!! warning "Using Docker in rootless mode"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless), you will need to replace the mount of the docker socket with the following value : `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Autoconf services

Once the stack is set up, you will be able to create the web application container and add the settings as labels using the "bunkerweb." prefix in order to automatically set up BunkerWeb :

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### Namespaces

Starting from version `1.6.0-beta`, BunkerWeb's Autoconf stacks now support namespaces. This feature enables you to manage multiple "*clusters*" of BunkerWeb instances and services on the same Docker host. To take advantage of namespaces, simply set the `NAMESPACE` label on your services. Here's an example:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the service
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace behavior"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to a specific namespaces, you can set the `NAMESPACES` environment variable in the `bw-autoconf` service :

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-beta
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the BunkerWeb instance so the autoconf service can detect it
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-beta
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # Only listen to these namespaces
    ...
    ```

    Keep in mind that the `NAMESPACES` environment variable is a space-separated list of namespaces.

!!! warning "Namespace specifications"

    There can only be **one database** and **one Scheduler** per namespace. If you try to create multiple databases or Schedulers in the same namespace, the configurations will end up conflicting with each other.

    The Scheduler doesn't need the `NAMESPACE` label to work properly. It will only need the `DATABASE_URI` setting properly configured so that it can access the same database as the autoconf service.

## Kubernetes

<figure markdown>
  ![Overview](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Kubernetes integration</figcaption>
</figure>

To automate the configuration of BunkerWeb instances in a Kubernetes environment, the autoconf service serves as an [Ingress controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/). It configures the BunkerWeb instances based on [Ingress resources](https://kubernetes.io/docs/concepts/services-networking/ingress/) and also monitors other Kubernetes objects, such as [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/), for custom configurations.

For an optimal setup, it is recommended to define BunkerWeb as a **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)**, which ensures that a pod is created on all nodes, while the **autoconf and scheduler** are defined as **single replicated [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)**.

Given the presence of multiple BunkerWeb instances, it is necessary to establish a shared data store implemented as a [Redis](https://redis.io/) service. This Redis service will be utilized by the instances to cache and share data among themselves. Further information about the Redis settings can be found [here](settings.md#redis).

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-beta/misc/integrations) folder of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Please ensure that the autoconf services have access to the Kubernetes API. It is recommended to utilize [RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) for this purpose.

!!! warn "Custom CA for Kubernetes API"
    If you use a custom CA for your Kubernetes API, you can mount a bundle file containing your intermediate(s) and root certificates on the ingress controller and set the `KUBERNETES_SSL_CA_FILE` environment value to the path of the bundle inside the container. Alternatively, even if it's not recommended, you can disable certificate verification by setting the `KUBERNETES_SSL_VERIFY` environment variable of the ingress controller to `no` (default is `yes`).

Additionally, **it is crucial to set the `KUBERNETES_MODE` environment variable to `yes` when utilizing the Kubernetes integration**. This variable is mandatory for proper functionality.

To assist you, here is a YAML boilerplate that can serve as a foundation for your configuration:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cr-bunkerweb
rules:
  - apiGroups: [""]
    resources: ["services", "pods", "configmaps", "secrets"]
    verbs: ["get", "watch", "list"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "watch", "list"]
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sa-bunkerweb
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: crb-bunkerweb
subjects:
  - kind: ServiceAccount
    name: sa-bunkerweb
    namespace: default
    apiGroup: ""
roleRef:
  kind: ClusterRole
  name: cr-bunkerweb
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
spec:
  selector:
    matchLabels:
      app: bunkerweb
  template:
    metadata:
      labels:
        app: bunkerweb
      # mandatory annotation
      annotations:
        bunkerweb.io/INSTANCE: "yes"
    spec:
      serviceAccountName: sa-bunkerweb
      containers:
        # using bunkerweb as name is mandatory
        - name: bunkerweb
          image: bunkerity/bunkerweb:1.6.0-beta
          imagePullPolicy: Always
          securityContext:
            runAsUser: 101
            runAsGroup: 101
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          ports:
            - containerPort: 8080
              hostPort: 80
            - containerPort: 8443
              hostPort: 443
          env:
            - name: KUBERNETES_MODE
              value: "yes"
            # replace with your DNS resolvers
            # e.g. : kube-dns.kube-system.svc.cluster.local
            - name: DNS_RESOLVERS
              value: "coredns.kube-system.svc.cluster.local"
            # 10.0.0.0/8 is the cluster internal subnet
            - name: API_WHITELIST_IP
              value: "127.0.0.0/8 10.0.0.0/8"
          livenessProbe:
            exec:
              command:
                - /usr/share/bunkerweb/helpers/healthcheck.sh
            initialDelaySeconds: 30
            periodSeconds: 5
            timeoutSeconds: 1
            failureThreshold: 3
          readinessProbe:
            exec:
              command:
                - /usr/share/bunkerweb/helpers/healthcheck.sh
            initialDelaySeconds: 30
            periodSeconds: 1
            timeoutSeconds: 1
            failureThreshold: 3
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bunkerweb-controller
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: bunkerweb-controller
  template:
    metadata:
      labels:
        app: bunkerweb-controller
    spec:
      serviceAccountName: sa-bunkerweb
      containers:
        - name: bunkerweb-controller
          image: bunkerity/bunkerweb-autoconf:1.6.0-beta
          imagePullPolicy: Always
          env:
            - name: KUBERNETES_MODE
              value: "yes"
            - name: DATABASE_URI
              value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bunkerweb-scheduler
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: bunkerweb-scheduler
  template:
    metadata:
      labels:
        app: bunkerweb-scheduler
    spec:
      serviceAccountName: sa-bunkerweb
      containers:
        - name: bunkerweb-scheduler
          image: bunkerity/bunkerweb-scheduler:1.6.0-beta
          imagePullPolicy: Always
          env:
            - name: KUBERNETES_MODE
              value: "yes"
            - name: DATABASE_URI
              value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db" # Remember to set a stronger password for the database
            # replace with your DNS resolvers
            # e.g. : kube-dns.kube-system.svc.cluster.local
            - name: DNS_RESOLVERS
              value: "coredns.kube-system.svc.cluster.local"
            # 10.0.0.0/8 is the cluster internal subnet
            - name: API_WHITELIST_IP
              value: "127.0.0.0/8 10.0.0.0/8"
            - name: BUNKERWEB_INSTANCES
              value: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the ingress controller
            - name: SERVER_NAME
              value: "" # The server name will be filled with services annotations
            - name: MULTISITE
              value: "yes" # Mandatory setting for autoconf
            - name: USE_REDIS
              value: "yes"
            - name: REDIS_HOST
              value: "svc-bunkerweb-redis.default.svc.cluster.local"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bunkerweb-redis
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: bunkerweb-redis
  template:
    metadata:
      labels:
        app: bunkerweb-redis
    spec:
      containers:
        - name: bunkerweb-redis
          image: redis:7-alpine
          imagePullPolicy: Always
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bunkerweb-db
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: bunkerweb-db
  template:
    metadata:
      labels:
        app: bunkerweb-db
    spec:
      containers:
        - name: bunkerweb-db
          image: mariadb:11
          imagePullPolicy: Always
          env:
            - name: MYSQL_RANDOM_ROOT_PASSWORD
              value: "yes"
            - name: MYSQL_DATABASE
              value: "db"
            - name: MYSQL_USER
              value: "bunkerweb"
            - name: MYSQL_PASSWORD
              value: "changeme" # Remember to set a stronger password for the database
          volumeMounts:
            - mountPath: "/var/lib/mysql"
              name: vol-db
      volumes:
        - name: vol-db
          persistentVolumeClaim:
            claimName: pvc-bunkerweb
---
apiVersion: v1
kind: Service
metadata:
  name: svc-bunkerweb
spec:
  clusterIP: None
  selector:
    app: bunkerweb
---
apiVersion: v1
kind: Service
metadata:
  name: svc-bunkerweb-db
spec:
  type: ClusterIP
  selector:
    app: bunkerweb-db
  ports:
    - name: sql
      protocol: TCP
      port: 3306
      targetPort: 3306
---
apiVersion: v1
kind: Service
metadata:
  name: svc-bunkerweb-redis
spec:
  type: ClusterIP
  selector:
    app: bunkerweb-redis
  ports:
    - name: redis
      protocol: TCP
      port: 6379
      targetPort: 6379
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-bunkerweb
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

### Ingress resources

Once the BunkerWeb Kubernetes stack is successfully set up and operational (refer to the autoconf logs for detailed information), you can proceed with deploying web applications within the cluster and declaring your Ingress resource.

It is important to note that the BunkerWeb settings need to be specified as annotations for the Ingress resource. For the domain part, please use the special value **`bunkerweb.io`**. By including the appropriate annotations, you can configure BunkerWeb accordingly for the Ingress resource.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    bunkerweb.io/MY_SETTING: "value"
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
...
```

### Namespaces

Starting from version `1.6.0-beta`, BunkerWeb's autoconf stacks now support namespaces. This feature enables you to manage multiple clusters of BunkerWeb instances and services on the same Kubernetes cluster. To take advantage of namespaces, simply set the `namespace` metadata field on your BunkerWeb instances and services. Here's an example:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Set the namespace for the BunkerWeb instance
...
```

!!! info "Namespace behavior"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to a specific namespaces, you can set the `NAMESPACES` environment variable in the `bunkerweb-controller` deployment :

    ```yaml
    ...
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
      namespace: my-namespace # Set the namespace for the Controller
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-controller
      template:
        metadata:
          labels:
            app: bunkerweb-controller
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-controller
              image: bunkerity/bunkerweb-autoconf:1.6.0-beta
              imagePullPolicy: Always
              env:
                - name: NAMESPACES
                  value: "my-namespace my-other-namespace" # Only listen to these namespaces
                ...
    ...
    ```

    Keep in mind that the `NAMESPACES` environment variable is a space-separated list of namespaces.

!!! warning "Namespace specifications"

    There can only be **one database** and **one Scheduler** per namespace. If you try to create multiple databases or Schedulers in the same namespace, the configurations will end up conflicting with each other.

    The Scheduler doesn't need the `NAMESPACE` annotation to work properly. It will only need the `DATABASE_URI` setting properly configured so that it can access the same database as the autoconf service.

### Ingress class

When installed using the official methods in the documentation, BunkerWeb comes with the following `IngressClass` definition :

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

In order to restrict the `Ingress` resources monitored by the ingress controller, you can set the `KUBERNETES_INGRESS_CLASS` environment variable with the value `bunkerweb`. Then, you can leverage the `ingressClassName` directive in your `Ingress` definitions :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    bunkerweb.io/MY_SETTING: "value"
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  ingressClassName: bunkerweb
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
```

### Minikube specificities

We are aware of issues with Minikube and internal hostname resolution. To work around this, there is a specific setting that you can use in the `bunkerweb-controller` deployment :

```yaml
...
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bunkerweb-controller
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: bunkerweb-controller
  template:
    metadata:
      labels:
        app: bunkerweb-controller
    spec:
      serviceAccountName: sa-bunkerweb
      containers:
        - name: bunkerweb-controller
          image: bunkerity/bunkerweb-autoconf:1.6.0-beta
          imagePullPolicy: Always
          env:
            - name: USE_KUBERNETES_FQDN
              value: "no" # Disable the usage of FQDN and use the pods IPs instead (default is "yes")
            ...
...
```


## Swarm

<figure markdown>
  ![Overview](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Docker Swarm integration</figcaption>
</figure>

!!! info "Docker autoconf"
    The Swarm integration is similar to the Docker autoconf one (but with services instead of containers). Please read the [Docker autoconf integration section](#docker-autoconf) first if needed.

To enable automatic configuration of BunkerWeb instances, the **autoconf** service requires access to the Docker API. This service listens for Docker Swarm events, such as service creation or deletion, and seamlessly configures the **BunkerWeb instances** in real-time without any downtime. It also monitors other Swarm objects, such as [configs](https://docs.docker.com/engine/swarm/configs/), for custom configurations.

Similar to the [Docker autoconf integration](#docker-autoconf), configuration for web services is defined using labels that start with the **bunkerweb**  prefix.

For an optimal setup, it is recommended to schedule the **BunkerWeb service** as a ***global service*** on all nodes, while the **autoconf, scheduler, and Docker API proxy services** should be scheduled as ***single replicated services***. Please note that the Docker API proxy service needs to be scheduled on a manager node unless you configure it to use a remote API (which is not covered in the documentation).

Since multiple instances of BunkerWeb are running, a shared data store implemented as a [Redis](https://redis.io/) service must be created. These instances will utilize the Redis service to cache and share data. Further details regarding the Redis settings can be found [here](settings.md#redis).

As for the database volume, the documentation does not specify a specific approach. Choosing either a shared folder or a specific driver for the database volume is dependent on your unique use-case and is left as an exercise for the reader.

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.0-beta/misc/integrations) folder of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Here is the stack boilerplate that you can deploy using `docker stack deploy` :

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both services
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.0-beta
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
        protocol: udp # QUIC
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services
    deploy:
      mode: global
      placement:
        constraints:
          - "node.role == worker"
      labels:
        - "bunkerweb.INSTANCE=yes" # Mandatory label for the autoconf service to identify the BunkerWeb instance

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.0-beta
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-data:/data # This is used to persist data like the backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.0-beta
    environment:
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-docker
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    environment:
      CONFIGS: "1"
      CONTAINERS: "1"
      SERVICES: "1"
      SWARM: "1"
      TASKS: "1"
      LOG_LEVEL: "warning"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: "unless-stopped"
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
      - bw-db:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-redis:
    image: redis:7-alpine
    restart: "unless-stopped"
    networks:
      - bw-universe
    deploy:
      placement:
        constraints:
          - "node.role == worker"

volumes:
  bw-data:
  bw-db:

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

!!! info "Swarm mandatory setting"
    Please note that the `SWARM_MODE: "yes"` environment variable is mandatory when using the Swarm integration.

### Swarm services

Once the BunkerWeb Swarm stack is set up and running (see autoconf and scheduler logs for more information), you will be able to deploy web applications in the cluster and use labels to dynamically configure BunkerWeb :

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### Namespaces

Starting from version `1.6.0-beta`, BunkerWeb's Autoconf stacks now support namespaces. This feature enables you to manage multiple "*clusters*" of BunkerWeb instances and services on the same Docker host. To take advantage of namespaces, simply set the `NAMESPACE` label on your services. Here's an example:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the service
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace behavior"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to a specific namespaces, you can set the `NAMESPACES` environment variable in the `bw-autoconf` service :

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.0-beta
        ...
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"
            - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the BunkerWeb instance
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.0-beta
        environment:
          NAMESPACES: "my-namespace my-other-namespace" # Only listen to these namespaces
          ...
        deploy:
          placement:
            constraints:
              - "node.role == worker"
    ...
    ```

    Keep in mind that the `NAMESPACES` environment variable is a space-separated list of namespaces.

!!! warning "Namespace specifications"

    There can only be **one database** and **one Scheduler** per namespace. If you try to create multiple databases or Schedulers in the same namespace, the configurations will end up conflicting with each other.

    The Scheduler doesn't need the `NAMESPACE` label to work properly. It will only need the `DATABASE_URI` setting properly configured so that it can access the same database as the autoconf service.

## Microsoft Azure

<figure markdown>
  ![Overview](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Azure integration</figcaption>
</figure>

!!! info "Recommended VM size"
    Please be aware while you choose the SKU of the VM. You must select a SKU compatible with Gen2 VM and we recommend starting at B2s or Ds2 series for optimal use.

You can easily deploy BunkerWeb on your Azure subscription in several ways:

- Azure CLI in Cloud Shell
- Azure ARM Template
- Azure portal via the Marketplace

=== "Cloud Shell"

    Create a resource group. Replace value `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    Create a VM with `Standard_B2s` SKU in the location of the resource group. Replace values `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    Full command. Replace values `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "ARM Template"

    !!! info "Permissions requirement"
        To deploy a ARM template, you need write access on the resources you're deploying and access to all operations on the Microsoft.Resources/deployments resource type.
        To deploy a virtual machine, you need Microsoft.Compute/virtualMachines/write and Microsoft.Resources/deployments/* permissions. The what-if operation has the same permission requirements.

    Deploy the ARM Template:

    [![Deploy to Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    Login in [Azure portal](https://portal.azure.com){:target="_blank"}.

    Get BunkerWeb from the [Create resource menu](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}.

    You can also go through the [Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"}.

You can access the setup wizard by browsing the `https://your-ip-address/setup` URI of your virtual machine.
