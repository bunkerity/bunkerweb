# Integrations

## BunkerWeb Cloud

<figure markdown>
  ![Overview](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

BunkerWeb Cloud will be the easiest way to get started with BunkerWeb. It offers you a fully managed BunkerWeb service with no hassle. Think of it as a BunkerWeb-as-a-Service!

Try our [BunkerWeb Cloud offer](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) and get access to:

- A fully managed BunkerWeb instance hosted in our cloud
- All BunkerWeb features, including PRO ones
- A monitoring platform with dashboards and alerts
- Technical support to assist you with configuration

If you are interested in the BunkerWeb Cloud offering, don't hesitate to [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) so we can discuss your needs.

## All-In-One (AIO) Image

<figure markdown>
  ![AIO Architecture Graph Placeholder](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>BunkerWeb All-In-One Architecture (AIO)</figcaption>
</figure>

### Deployment

To deploy the all-in-one container, all you have to do is run the following command:

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.3-rc2
```

By default, the container exposes:

- 8080/tcp for HTTP
- 8443/tcp for HTTPS
- 8443/udp for QUIC
- 7000/tcp for the web UI access without BunkerWeb in front (not recommended for production)

The All-In-One image comes with several built-in services, which can be controlled using environment variables:

- `SERVICE_UI=yes` (default) - Enables the web UI service
- `SERVICE_SCHEDULER=yes` (default) - Enables the Scheduler service
- `SERVICE_AUTOCONF=no` (default) - Enables the autoconf service
- `USE_REDIS=yes` (default) - Enables the built-in [Redis](#redis-integration) instance
- `USE_CROWDSEC=no` (default) - [CrowdSec](#crowdsec-integration) integration is disabled by default

### Accessing the Setup wizard

By default, the setup wizard is automagically launched when you run the AIO container for the first time. To access it, follow these steps:

1. **Start the AIO container** as [above](#deployment), ensuring `SERVICE_UI=yes` (default).
2. **Access the UI** via your main BunkerWeb endpoint, e.g. `https://your-domain`.

> Follow the next steps in the [Quickstart guide](quickstart-guide.md#complete-the-setup-wizard) to set up the Web UI.

### Redis Integration

The BunkerWeb **All-In-One** image includes Redis out-of-the-box for the [persistence of bans and reports](advanced.md#persistence-of-bans-and-reports). To manage Redis:

- To disable Redis, set `USE_REDIS=no` or point `REDIS_HOST` to an external host.
- Redis logs appear with `[REDIS]` prefix in Docker logs and `/var/log/bunkerweb/redis.log`.

### CrowdSec Integration

The BunkerWeb **All-In-One** Docker image comes with CrowdSec fully integrated—no extra containers or manual setup required. Follow the steps below to enable, configure, and extend CrowdSec in your deployment.

By default, CrowdSec is **disabled**. To turn it on, simply add the `USE_CROWDSEC` environment variable:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.3-rc2
```

* When `USE_CROWDSEC=yes`, the entrypoint will:

    1. **Register** and **start** the local CrowdSec agent (via `cscli`).
    2. **Install or upgrade** default collections & parsers.
    3. **Configure** the `crowdsec-bunkerweb-bouncer/v1.6` bouncer.

---

#### Default Collections & Parsers

On first startup (or after upgrading), these assets are automatically installed and kept up to date:

| Type           | Name                                    | Purpose                                                                                                                                                                                                                            |
| -------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Collection** | `crowdsecurity/nginx`                   | Defend Nginx servers against a broad array of HTTP-based attacks, from brute-force to injection attempts.                                                                                                                          |
| **Collection** | `crowdsecurity/appsec-virtual-patching` | Delivers a dynamically updated WAF-style rule set targeting known CVEs, automatically patched daily to shield web applications from newly discovered vulnerabilities.                                                              |
| **Collection** | `crowdsecurity/appsec-generic-rules`    | Complements `crowdsecurity/appsec-virtual-patching` with heuristics for generic application-layer attack patterns—such as enumeration, path traversal, and automated probes—filling gaps where CVE-specific rules don’t yet exist. |
| **Parser**     | `crowdsecurity/geoip-enrich`            | Enriches events with GeoIP context                                                                                                                                                                                                 |

<details>
<summary><strong>How it works internally</strong></summary>

The entrypoint script invokes:

```bash
cscli install collection crowdsecurity/nginx
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

---

#### Adding Extra Collections

Need more coverage? Define `CROWDSEC_EXTRA_COLLECTIONS` with a space-separated list of Hubb collections:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/apache2 crowdsecurity/mysql" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.3-rc2
```

!!! info "How it works internally"

    The script loops through each name and installs or upgrades as needed—no manual steps required.

---

#### AppSec Toggle

CrowdSec [AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) features—powered by the `appsec-virtual-patching` and `appsec-generic-rules` collections—are **enabled by default**.

To **disable** all AppSec (WAF/virtual-patching) functionality, set:

```bash
-e CROWDSEC_APPSEC_URL=""
```

This effectively turns off the AppSec endpoint so no rules are applied.

---

#### External CrowdSec API

If you operate a remote CrowdSec instance, point the container to your API:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_API="https://crowdsec.example.com:8000" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.3-rc2
```

* **Local registration** is skipped when `CROWDSEC_API` is not `127.0.0.1` or `localhost`.
* **AppSec** is disabled by default when using an external API. To enable it, set `CROWDSEC_APPSEC_URL` to your desired endpoint.
* Bouncer registration still occurs against the remote API.
* To reuse an existing bouncer key, supply `CROWDSEC_API_KEY` with your pre-generated token.

---

!!! tip "More options"
    For full coverage of all CrowdSec options (custom scenarios, logs, troubleshooting, and more), see the [BunkerWeb CrowdSec plugin docs](features.md#crowdsec) or visit the [official CrowdSec website](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs).

## Docker

<figure markdown>
  ![Overview](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker integration</figcaption>
</figure>

Using BunkerWeb as a [Docker](https://www.docker.com/) container offers a convenient and straightforward approach for testing and utilizing the solution, particularly if you are already familiar with Docker technology.

To facilitate your Docker deployment, we provide readily available prebuilt images on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb), supporting multiple architectures. These prebuilt images are optimized and prepared for use on the following architectures:

- x64 (64-bit)
- x86
- armv8 (ARM 64-bit)
- armv7 (ARM 32-bit)

By accessing these prebuilt images from Docker Hub, you can quickly pull and run BunkerWeb within your Docker environment, eliminating the need for extensive configuration or setup processes. This streamlined approach allows you to focus on leveraging the capabilities of BunkerWeb without unnecessary complexities.

Whether you're conducting tests, developing applications, or deploying BunkerWeb in production, the Docker containerization option provides flexibility and ease of use. Embracing this method empowers you to take full advantage of BunkerWeb's features while leveraging the benefits of Docker technology.

```shell
docker pull bunkerity/bunkerweb:1.6.3-rc2
```

Docker images are also available on [GitHub packages](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) and can be downloaded using the `ghcr.io` repository address:

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.3-rc2
```

Key concepts for Docker integration include:

- **Environment variables**: Configure BunkerWeb easily using environment variables. These variables allow you to customize various aspects of BunkerWeb's behavior, such as network settings, security options, and other parameters.
- **Scheduler container**: Manage configuration and execute jobs using a dedicated container called the [scheduler](concepts.md#scheduler).
- **Networks**: Docker networks play a vital role in the integration of BunkerWeb. These networks serve two main purposes: exposing ports to clients and connecting to upstream web services. By exposing ports, BunkerWeb can accept incoming requests from clients, allowing them to access the protected web services. Additionally, by connecting to upstream web services, BunkerWeb can efficiently route and manage traffic, providing enhanced security and performance.

!!! info "Database backend"
    Please note that our instructions assume you are using SQLite as the default database backend, as configured by the `DATABASE_URI` setting. However, other database backends are also supported. See the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.3-rc2/misc/integrations) of the repository for more information.

### Environment variables

Settings are passed to the Scheduler using Docker environment variables:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.3-rc2
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
...
```

!!! info "Full list"
    For the complete list of environment variables, see the [settings section](features.md) of the documentation.

### Using Docker secrets

Instead of passing sensitive settings via environment variables, you can store them as Docker secrets. For each setting you want to secure, create a Docker secret with the name matching the setting key (in uppercase). BunkerWeb's entrypoint scripts automatically load secrets from `/run/secrets` and export them as environment variables.

Example:
```bash
# Create a Docker secret for ADMIN_PASSWORD
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

Mount the secrets when deploying:
```yaml
services:
  bw-ui:
    secrets:
      - ADMIN_PASSWORD
...
secrets:
  ADMIN_PASSWORD:
    external: true
```

This ensures sensitive settings are kept out of the environment and logs.

### Scheduler

The [scheduler](concepts.md#scheduler) runs in its own container, which is also available on Docker Hub:

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.3-rc2
```

!!! info "BunkerWeb settings"

    Since version `1.6.0`, the Scheduler container is where you define the settings for BunkerWeb. The Scheduler then pushes the configuration to the BunkerWeb container.

    ⚠ **Important**: All API-related settings (like `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME`, and `API_WHITELIST_IP`) **must also be defined in the BunkerWeb container**. (The settings must be mirrored in both containers; otherwise, the BunkerWeb container will not accept API requests from the Scheduler).

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for both containers
      API_HTTP_PORT: "5000" # Default value
      API_LISTEN_IP: "0.0.0.0" # Default value
      API_SERVER_NAME: "bwapi" # Default value
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Set this according to your network settings

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.3-rc2
        environment:
          # This will set the API settings for the BunkerWeb container
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.3-rc2
        environment:
          # This will set the API settings for the Scheduler container
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like backups
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

A volume is needed to store the SQLite database and backups used by the scheduler:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.3-rc2
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Using a local folder for persistent data"
    The scheduler runs as an **unprivileged user with UID 101 and GID 101** inside the container. This enhances security: in case a vulnerability is exploited, the attacker won't have full root (UID/GID 0) privileges.

    However, if you use a **local folder for persistent data**, you must **set the correct permissions** so the unprivileged user can write data to it. For example:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternatively, if the folder already exists:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [Podman](https://podman.io/), UIDs and GIDs in the container will be mapped to different ones on the host. You will first need to check your initial subuid and subgid:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    For example, if you have a value of **100000**, the mapped UID/GID will be **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Or if the folder already exists:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### Networks

By default, the BunkerWeb container listens (inside the container) on **8080/tcp** for **HTTP**, **8443/tcp** for **HTTPS**, and **8443/udp** for **QUIC**.

!!! warning "Privileged ports in rootless mode or when using Podman"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) and want to redirect privileged ports (< 1024) like 80 and 443 to BunkerWeb, please refer to the prerequisites [here](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    If you are using [Podman](https://podman.io/), you can lower the minimum number for unprivileged ports:
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

The typical BunkerWeb stack when using Docker integration contains the following containers:

- BunkerWeb
- Scheduler
- Your services

For defense-in-depth purposes, we strongly recommend creating at least three different Docker networks:

- `bw-services`: for BunkerWeb and your web services
- `bw-universe`: for BunkerWeb and the scheduler
- `bw-db`: for the database (if you are using one)

To secure communication between the scheduler and the BunkerWeb API, **it is important to authorize API calls**. You can use the `API_WHITELIST_IP` setting to specify allowed IP addresses and subnets.

**It is strongly recommended to use a static subnet for the `bw-universe` network** to enhance security. By implementing these measures, you can ensure that only authorized sources can access the BunkerWeb API, reducing the risk of unauthorized access or malicious activities:

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.3-rc2
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
    image: bunkerity/bunkerweb-scheduler:1.6.3-rc2
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
...
volumes:
  bw-storage:

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
    image: bunkerity/bunkerweb:1.6.3-rc2
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
    image: bunkerity/bunkerweb-scheduler:1.6.3-rc2
    depends_on:
      - bunkerweb
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-storage:

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

### Build from source

Alternatively, if you prefer a more hands-on approach, you have the option to build the Docker image directly from the [source](https://github.com/bunkerity/bunkerweb). Building the image from source gives you greater control and customization over the deployment process. However, please note that this method may take some time to complete, depending on your hardware configuration (you can take a coffee ☕ if needed).

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t bw -f src/bw/Dockerfile . && \
docker build -t bw-scheduler -f src/scheduler/Dockerfile . && \
docker build -t bw-autoconf -f src/autoconf/Dockerfile . && \
docker build -t bw-ui -f src/ui/Dockerfile .
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
- Fedora 42
- Red Hat Enterprise Linux (RHEL) 8.10
- Red Hat Enterprise Linux (RHEL) 9.6

### Easy installation script

For a simplified installation experience, BunkerWeb provides an easy install script that automatically handles the entire setup process, including NGINX installation, repository configuration, and service setup.

#### Quick start

Download and run the installation script:

```bash
wget https://raw.githubusercontent.com/bunkerity/bunkerweb/v1.6.3-rc2/misc/install-bunkerweb.sh
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! warning "Security Notice"
    Before running any installation script, especially with elevated privileges, it's recommended to review the script content first.

    ```bash
    cat install-bunkerweb.sh
    ```

#### Interactive installation

By default, the script runs in interactive mode and will:

1. **Detect your operating system** and verify compatibility
2. **Ask about the setup wizard** - choose whether to enable the web-based configuration interface
3. **Show RHEL database recommendations** (if applicable) for external database support
4. **Install NGINX** with the correct version for your distribution
5. **Install BunkerWeb** and configure all services
6. **Provide next steps** based on your configuration choices

#### Command line options

The script supports various options for different installation scenarios:

```bash
# Interactive installation (default)
sudo ./install-bunkerweb.sh

# Non-interactive with defaults (wizard enabled)
sudo ./install-bunkerweb.sh --yes

# Install without the setup wizard
sudo ./install-bunkerweb.sh --no-wizard

# Install a specific version
sudo ./install-bunkerweb.sh --version 1.6.0

# Force installation on unsupported OS versions
sudo ./install-bunkerweb.sh --force

# Show help
./install-bunkerweb.sh --help
```

#### What the script does

The easy install script automatically:

- **Validates OS compatibility** and warns about unsupported versions
- **Installs NGINX** from official repositories with the correct version
- **Adds BunkerWeb repositories** for your distribution
- **Installs BunkerWeb packages** and locks versions to prevent accidental upgrades
- **Configures systemd services** (bunkerweb, bunkerweb-scheduler, bunkerweb-ui)
- **Sets up the setup wizard** (if enabled) for easy web-based configuration
- **Provides comprehensive next steps** and resource links

#### RHEL considerations

!!! warning "External database support on RHEL-based systems"
    If you plan to use an external database (recommended for production), you must install the appropriate database client package:

    ```bash
    # For MariaDB
    sudo dnf install mariadb

    # For MySQL
    sudo dnf install mysql

    # For PostgreSQL
    sudo dnf install postgresql
    ```

    This is required for the BunkerWeb Scheduler to connect to your external database.

#### After installation

Depending on your choices during installation:

**With setup wizard enabled:**

1. Access the setup wizard at: `https://your-server-ip/setup`
2. Follow the guided configuration to set up your first protected service
3. Configure SSL/TLS certificates and other security settings

**Without setup wizard:**

1. Edit `/etc/bunkerweb/variables.env` to configure BunkerWeb manually
2. Add your server settings and protected services
3. Restart the scheduler: `sudo systemctl restart bunkerweb-scheduler`

### Installation using package manager

Please ensure that you have **NGINX 1.28.0 installed before installing BunkerWeb**. For all distributions, except Fedora, it is mandatory to use prebuilt packages from the [official NGINX repository](https://nginx.org/en/linux_packages.html). Compiling NGINX from source or using packages from different repositories will not work with the official prebuilt packages of BunkerWeb. However, you have the option to build BunkerWeb from source.

=== "Debian"

    The first step is to add NGINX official repository:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.28.0:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.3-rc2:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.3-rc2
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    The first step is to add NGINX official repository:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.28.0:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.3-rc2:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.3-rc2
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora Update Testing"
        If you can't find the NGINX version listed in the stable repository, you can enable the `updates-testing` repository:

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora already provides NGINX 1.28.0 that we support

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.0
    ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.3-rc2:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y --allowerasing bunkerweb-1.6.3-rc2
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    The first step is to add NGINX official repository. Create the following file at `/etc/yum.repos.d/nginx.repo`:

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

    You should now be able to install NGINX 1.28.0:

    ```shell
    sudo dnf install --allowerasing nginx-1.28.0
    ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.3-rc2:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.3-rc2
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### Configuration and service

Manual configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file:

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

When installed, BunkerWeb comes with three services `bunkerweb`, `bunkerweb-scheduler` and `bunkerweb-ui` that you can manage using `systemctl`.

If you manually edit the BunkerWeb configuration using `/etc/bunkerweb/variables.env` a restart of the `bunkerweb-scheduler` service will be enough to generate and reload the configuration without any downtime. But depending on the case (such as changing listening ports) you might need to restart the `bunkerweb` service.

### High availability

The scheduler can be detached from the BunkerWeb instance to provide high availability. In this case, the scheduler will be installed on a separate server and will be able to manage multiple BunkerWeb instances.

**Manager**

To install only the scheduler on a server, you can export the following variables before executing the BunkerWeb installation:

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

Alternatively, you can also export the following variables to only enable the scheduler:

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

**Worker**

On another server, to install only BunkerWeb, you can export the following variables before executing the BunkerWeb installation:

```shell
export WORKER_MODE=yes
```

Alternatively, you can also export the following variables to only enable BunkerWeb:

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

**Web UI**

The Web UI can be installed on a separate server to provide a dedicated interface for managing BunkerWeb instances. To install only the Web UI, you can export the following variables before executing the BunkerWeb installation:

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

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
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.3-rc2/misc/integrations) of the repository for more information.

To enable automated configuration updates, include an additional container called `bw-autoconf` in the stack. This container hosts the autoconf service, which manages dynamic configuration changes for BunkerWeb.

To support this functionality, use a dedicated "real" database backend (e.g., MariaDB, MySQL, or PostgreSQL) for synchronized configuration storage. By integrating `bw-autoconf` and a suitable database backend, you establish the infrastructure for seamless automated configuration management in BunkerWeb.

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both containers
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.3-rc2
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
    image: bunkerity/bunkerweb-scheduler:1.6.3-rc2
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.3-rc2
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
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
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
  bw-docker:
    name: bw-docker
  bw-db:
    name: bw-db
```

!!! info "Database in the `bw-db` network"
    The database container is intentionally not included in the `bw-universe` network. It is used by the `bw-autoconf` and `bw-scheduler` containers rather than directly by BunkerWeb. Therefore, the database container is part of the `bw-db` network, which enhances security by making external access to the database more challenging. **This deliberate design choice helps safeguard the database and strengthens the overall security perspective of the system**.

!!! warning "Using Docker in rootless mode"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless), you will need to replace the mount of the docker socket with the following value: `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Autoconf services

Once the stack is set up, you will be able to create the web application container and add the settings as labels using the "bunkerweb." prefix in order to automatically set up BunkerWeb:

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

Starting from version `1.6.0`, BunkerWeb's Autoconf stacks now support namespaces. This feature enables you to manage multiple "*clusters*" of BunkerWeb instances and services on the same Docker host. To take advantage of namespaces, simply set the `NAMESPACE` label on your services. Here's an example:

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

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to specific namespaces, you can set the `NAMESPACES` environment variable in the `bw-autoconf` service:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.3-rc2
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the BunkerWeb instance so the autoconf service can detect it
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.3-rc2
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

Given the presence of multiple BunkerWeb instances, it is necessary to establish a shared data store implemented as a [Redis](https://redis.io/) or [Valkey](https://valkey.io/) service. This service will be utilized by the instances to cache and share data among themselves. Further information about the Redis/Valkey settings can be found [here](features.md#redis).

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.3-rc2/misc/integrations) of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Please ensure that the autoconf services have access to the Kubernetes API. It is recommended to utilize [RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) for this purpose.

!!! warn "Custom CA for Kubernetes API"
    If you use a custom CA for your Kubernetes API, you can mount a bundle file containing your intermediate(s) and root certificates on the ingress controller and set the `KUBERNETES_SSL_CA_CERT` environment value to the path of the bundle inside the container. Alternatively, even if it's not recommended, you can disable certificate verification by setting the `KUBERNETES_SSL_VERIFY` environment variable of the ingress controller to `no` (default is `yes`).

Additionally, **it is crucial to set the `KUBERNETES_MODE` environment variable to `yes` when utilizing the Kubernetes integration**. This variable is mandatory for proper functionality.

### Installation methods

#### Using helm chart (recommended)

The recommended way to install Kubernetes is to use the Helm chart available at `https://repo.bunkerweb.io/charts`:

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

You can then use the bunkerweb helm chart from that repository:

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

The full list of values are listed in the [charts/bunkerweb/values.yaml file](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) of the [bunkerity/bunkerweb-helm repository](https://github.com/bunkerity/bunkerweb-helm).

#### Full YAML files

Instead of using the helm chart, you can also use the YAML boilerplates inside the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.3-rc2/misc/integrations) of the GitHub repository. Please note that we highly recommend to use the helm chart instead.

### Ingress resources

Once the BunkerWeb Kubernetes stack is successfully set up and operational (refer to the autoconf logs for detailed information), you can proceed with deploying web applications within the cluster and declaring your Ingress resource.

It is important to note that the BunkerWeb settings need to be specified as annotations for the Ingress resource. For the domain part, please use the special value **`bunkerweb.io`**. By including the appropriate annotations, you can configure BunkerWeb accordingly for the Ingress resource.

!!! info "TLS support"
    BunkerWeb ingress controller fully supports custom HTTPS certificates using the tls spec as shown in the example. Configuring solutions such as `cert-manager` to automatically generate tls secrets is out of the scope of this documentation.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # Will be applied to all host in this ingress
    bunkerweb.io/MY_SETTING: "value"
    # Will only be applied to the www.example.com host
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  # TLS is optional, you can also use builtin Let's Encrypt for example
  # tls:
  #   - hosts:
  #       - www.example.com
  #     secretName: secret-example-tls
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

Starting from version `1.6.0`, BunkerWeb's autoconf stacks now support namespaces. This feature enables you to manage multiple clusters of BunkerWeb instances and services on the same Kubernetes cluster. To take advantage of namespaces, simply set the `namespace` metadata field on your BunkerWeb instances and services. Here's an example:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Set the namespace for the BunkerWeb instance
...
```

!!! info "Namespace behavior"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to specific namespaces, you can set the `NAMESPACES` environment variable in the `bunkerweb-controller` deployment:

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
              image: bunkerity/bunkerweb-autoconf:1.6.3-rc2
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

When installed using the official methods in the documentation, BunkerWeb comes with the following `IngressClass` definition:

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

In order to restrict the `Ingress` resources monitored by the ingress controller, you can set the `KUBERNETES_INGRESS_CLASS` environment variable with the value `bunkerweb`. Then, you can leverage the `ingressClassName` directive in your `Ingress` definitions:

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

### Custom domain name

If you use a custom domain name for your Kubernetes cluster different than the default `kubernetes.local` one, you can set the value using the `KUBERNETES_DOMAIN_NAME` environment variable on the scheduler container.

### Use with existing ingress controller

!!! info "Keeping both existing ingress controller and BunkerWeb"

    This is a use-case where you want to keep an existing ingress controller such as the nginx one. Typical traffic flow will be: Load Balancer => Ingress Controller => BunkerWeb => Application.

**nginx ingress controller install**

Install ingress nginx helm repo:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

Install nginx ingress controller with default values (might not work on your own cluster out-of-the-box, please check the [documentation](https://kubernetes.github.io/ingress-nginx/)):

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

Extract IP address of LB:

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Setup DNS entries to IP of LB (e.g `bunkerweb` subdomain for BW UI and `myapp` for application):

```bash
$ nslookup bunkerweb.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   bunkerweb.example.com
Address: 1.2.3.4
$ nslookup myapp.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   myapp.example.com
Address: 1.2.3.4
```

**BunkerWeb install**

Install BunkerWeb helm repo:

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

Create `values.yaml` file:

```yaml
# Here we will setup the values needed to setup BunkerWeb behind an existing ingress controller
# Traffic flow with BW: LB => existing Ingress Controller => BunkerWeb => Service
# Traffic flow without BW: LB => existing Ingress Controller => Service

# Global settings
settings:
  misc:
    # Replace with your DNS resolver
    # to get it: kubectl exec in a random pod then cat /etc/resolv.conf
    # if you have an IP as nameserver then do a reverse DNS lookup: nslookup <IP>
    # most of the time it's coredns.kube-system.svc.cluster.local or kube-dns.kube-system.svc.cluster.local
    dnsResolvers: "kube-dns.kube-system.svc.cluster.local"
  kubernetes:
    # We only consider Ingress resources with ingressClass bunkerweb to avoid conflicts with existing ingress controller
    ingressClass: "bunkerweb"
    # Optional: you can choose namespace(s) where BunkerWeb will listen for Ingress/ConfigMap changes
    # Default (blank value) is all namespaces
    namespaces: ""

# Override the bunkerweb-external service type to ClusterIP
# Since we don't need to expose it to the outside world
# We will use the existing ingress controller to route traffic to BunkerWeb
service:
  type: ClusterIP

# BunkerWeb settings
bunkerweb:
  tag: 1.6.3-rc2

# Scheduler settings
scheduler:
  tag: 1.6.3-rc2
  extraEnvs:
    # Enable real IP module to get real IP of clients
    - name: USE_REAL_IP
      value: "yes"

# Controller settings
controller:
  tag: 1.6.3-rc2

# UI settings
ui:
  tag: 1.6.3-rc2
```

Install BunkerWeb with custom values:

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

Check logs and wait until everything is ready.

**Web UI install**

Setup the following ingress (assuming nginx controller is installed):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ui-bunkerweb
  # Replace with your namespace of BW if needed
  namespace: bunkerweb
  annotations:
    # HTTPS is mandatory for web UI even if traffic is internal
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    # We must set SNI so BW can serve the right vhost
    # Replace with your domain
    nginx.ingress.kubernetes.io/proxy-ssl-name: "bunkerweb.example.com"
    nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"
spec:
  # Only served by nginx controller and not BW
  ingressClassName: nginx
  # Uncomment and edit if you want to use your own certificate
  # tls:
  # - hosts:
  #   - bunkerweb.example.com
  #   secretName: tls-secret
  rules:
  # Replace with your domain
  - host: bunkerweb.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Created by Helm chart
            name: bunkerweb-external
            port:
              # Using HTTPS port is mandatory for UI
              number: 443
```

And you can now proceed to the setup wizard by browsing to `https://bunkerweb.example.com/setup`.

**Protecting existing application**

**First of all, you will need to go to Global Config, select the SSL plugin and then disable the Auto redirect HTTP to HTTPS. Please note that you only need to do it one time.**

Let's assume that you have an application in the `myapp` namespace which is accessible using the `myapp-service` service on port `5000`.

You will need to add a new service on the web UI and fill the required information:

- Server name: the public facing domain of your application (e.g. `myapp.example.com`)
- SSL/TLS: your ingress controller takes care of that part so don't enable it on BunkerWeb since traffic is internal within the cluster
- Reverse proxy host: the full URL of your application within the cluster (e.g. `http://myapp-service.myapp.svc.cluster.local:5000`)

Once the new service has been added, you can now declare an Ingress resource for that service and route it to the BunkerWeb service on HTTP port:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  # Replace with your namespace of BW if needed
  namespace: bunkerweb
spec:
  # Only served by nginx controller and not BW
  ingressClassName: nginx
  # Uncomment and edit if you want to use your own certificate
  # tls:
  # - hosts:
  #   - myapp.example.com
  #   secretName: tls-secret
  rules:
  # Replace with your domain
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Created by Helm chart
            name: bunkerweb-external
            port:
              number: 80
```

You can visit `http(s)://myapp.example.com`, which is now protected with BunkerWeb 🛡️

## Swarm

<figure markdown>
  ![Overview](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Docker Swarm integration</figcaption>
</figure>

!!! warning "Deprecated"
    The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](#kubernetes) instead.

!!! tip "PRO support"
    **If you need Swarm support**, please contact us at [contact@bunkerity.com](mailto:contact@bunkerity.com) or via the [contact form](https://panel.bunkerweb.io/contact.php).

!!! info "Docker autoconf"
    The Swarm integration is similar to the Docker autoconf one (but with services instead of containers). Please read the [Docker autoconf integration section](#docker-autoconf) first if needed.

To enable automatic configuration of BunkerWeb instances, the **autoconf** service requires access to the Docker API. This service listens for Docker Swarm events, such as service creation or deletion, and seamlessly configures the **BunkerWeb instances** in real-time without any downtime. It also monitors other Swarm objects, such as [configs](https://docs.docker.com/engine/swarm/configs/), for custom configurations.

Similar to the [Docker autoconf integration](#docker-autoconf), configuration for web services is defined using labels that start with the **bunkerweb**  prefix.

For an optimal setup, it is recommended to schedule the **BunkerWeb service** as a ***global service*** on all nodes, while the **autoconf, scheduler, and Docker API proxy services** should be scheduled as ***single replicated services***. Please note that the Docker API proxy service needs to be scheduled on a manager node unless you configure it to use a remote API (which is not covered in the documentation).

Since multiple instances of BunkerWeb are running, a shared data store implemented as a [Redis](https://redis.io/) or [Valkey](https://valkey.io/) service must be created. These instances will utilize the Redis/Valkey service to cache and share data. Further details regarding the Redis/Valkey settings can be found [here](features.md#redis).

As for the database volume, the documentation does not specify a specific approach. Choosing either a shared folder or a specific driver for the database volume is dependent on your unique use-case and is left as an exercise for the reader.

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.3-rc2/misc/integrations) of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Here is the stack boilerplate that you can deploy using `docker stack deploy`:

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both services
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.3-rc2
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
    image: bunkerity/bunkerweb-scheduler:1.6.3-rc2
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.3-rc2
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
      - bw-data:/var/lib/mysql
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

!!! info "Swarm mandatory setting"
    Please note that the `SWARM_MODE: "yes"` environment variable is mandatory when using the Swarm integration.

### Swarm services

Once the BunkerWeb Swarm stack is set up and running (see autoconf and scheduler logs for more information), you will be able to deploy web applications in the cluster and use labels to dynamically configure BunkerWeb:

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

Starting from version `1.6.0`, BunkerWeb's Autoconf stacks now support namespaces. This feature enables you to manage multiple "*clusters*" of BunkerWeb instances and services on the same Docker host. To take advantage of namespaces, simply set the `NAMESPACE` label on your services. Here's an example:

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

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to specific namespaces, you can set the `NAMESPACES` environment variable in the `bw-autoconf` service:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.3-rc2
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
        image: bunkerity/bunkerweb-autoconf:1.6.3-rc2
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
