# Advanced usages

Many real-world use case examples are available in the [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) folder of the GitHub repository.

We also provide numerous boilerplates, such as YAML files for various integrations and database types. These are available in the [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/misc/integrations) folder.

This section only focuses on advanced usages and security tuning, see the [features section](features.md) of the documentation to see all the available settings.

!!! tip "Testing"
    To perform quick tests when multisite mode is enabled (and if you don't have the proper DNS entries set up for the domains) you can use curl with the HTTP Host header of your choice :
    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```

    If you are using HTTPS, you will need to play with SNI :
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

## Behind load balancer or reverse proxy {#behind-load-balancer-or-reverse-proxy}

!!! info "Real IP"

    When BunkerWeb is itself behind a load balancer or a reverse proxy, you need to configure it so it can get the real IP address of the clients. **If you don't, the security features will block the IP address of the load balancer or reverse proxy instead of the client's one**.

BunkerWeb actually supports two methods to retrieve the real IP address of the client :

- Using the `PROXY protocol`
- Using a HTTP header like `X-Forwarded-For`

The following settings can be used :

- `USE_REAL_IP` : enable/disable real IP retrieval
- `USE_PROXY_PROTOCOL` : enable/disable PROXY protocol support.
- `REAL_IP_FROM` : list of trusted IP/network address allowed to send us the "real IP"
- `REAL_IP_HEADER` : the HTTP header containing the real IP or special value `proxy_protocol` when using PROXY protocol

You will find more settings about real IP in the [features section](features.md#real-ip) of the documentation.

=== "HTTP header"

    We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

    - They use the `X-Forwarded-For` header to set the real IP
    - They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

    === "Web UI"

        Navigate to the **Global Settings** page, select the **Real IP** plugin and fill out the following settings :

        <figure markdown>![Real IP settings (header) using web UI](assets/img/advanced-proxy1.png){ align=center }<figcaption>Real IP settings (header) using web UI</figcaption></figure>

        Please note that it's recommended to restart BunkerWeb when you change settings related to real IP.

    === "Linux"

        You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        Please note that it's recommended to issue a restart instead of reload when configuring settings related to real IP :

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        You will need to add the settings to the environment variables when running the All-in-one container :

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.8-rc3
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker autoconf"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Kubernetes"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler pods.

        Here is the corresponding part of your `values.yaml` file that you can use :

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        ```

    === "Swarm"

        !!! warning "Deprecated"
            The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

            **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler services:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Please note that if your service is already created, you will need to delete it and recreate it so the new environment variables will be updated.

=== "Proxy protocol"

    !!! warning "Read carefully"

        Only use the PROXY protocol if you are sure that your load balancer or reverse proxy is sending it. **If you enable it and it's not used, you will get errors**.

    We will assume the following regarding the load balancers or reverse proxies (you will need to update the settings depending on your configuration) :

    - They use the `PROXY protocol` v1 or v2 to set the real IP
    - They have IPs in the `1.2.3.0/24` and `100.64.0.0/10` networks

    === "Web UI"

        Navigate to the **Global Settings** page, select the **Real IP** plugin and fill out the following settings :

        <figure markdown>![Real IP settings (PROXY protocol) using web UI](assets/img/advanced-proxy2.png){ align=center }<figcaption>Real IP settings (PROXY protocol) using web UI</figcaption></figure>

        Please note that it's recommended to restart BunkerWeb when you change settings related to real IP.

    === "Linux"

        You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        Please note that it's recommended to issue a restart instead of reload when configuring settings related to proxy protocols :

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        You will need to add the settings to the environment variables when running the All-in-one container :

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e USE_PROXY_PROTOCOL="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.8-rc3
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Docker autoconf"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler containers:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Please note that if your container is already created, you will need to delete it and recreate it so the new environment variables will be updated.

    === "Kubernetes"

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler pods.

        Here is the corresponding part of your `values.yaml` file that you can use:

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        ```

    === "Swarm"

        !!! warning "Deprecated"
            The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

            **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

        You will need to add the settings to the environment variables of both the BunkerWeb and scheduler services.

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Please note that if your service is already created, you will need to delete it and recreate it so the new environment variables will be updated.

## High Availability and Load Balancing

To ensure your applications remain available even if a server fails, you can deploy BunkerWeb in a **High Availability (HA)** cluster. This setup involves a **Manager** (Scheduler) that orchestrates configurations and multiple **Workers** (BunkerWeb instances) that handle the traffic.

```mermaid
flowchart LR

  %% ================ Styles =================
  classDef manager     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;
  classDef database fill:#d1fae5,stroke:#059669,stroke-width:1px,rx:4px,ry:4px;
  classDef datastore     fill:#fee2e2,stroke:#b91c1c,stroke-width:1px,rx:4px,ry:4px;
  classDef backend       fill:#ede9fe,stroke:#7c3aed,stroke-width:1px,rx:4px,ry:4px;
  classDef client        fill:#e5e7eb,stroke:#4b5563,stroke-width:1px,rx:4px,ry:4px;

  %% Container styles
  style CLUSTER fill:#f3f4f6,stroke:#d1d5db,stroke-width:1px,stroke-dasharray:6 3;
  style WORKERS fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:4 2;

  %% ============== Outside left =============
  Client["Client"]:::client
  LB["Load Balancer"]:::lb

  %% ============== Cluster ==================
  subgraph CLUSTER[" "]
    direction TB

    %% ---- Top row: Manager + Redis ----
    subgraph TOP["Manager & Data Stores"]
      direction LR
      Manager["Manager<br/>(Scheduler)"]:::manager
      BDD["BDD"]:::database
      Redis["Redis/Valkey"]:::datastore
      UI["Web Interface"]:::manager
    end

    %% ---- Middle: Workers ----
    subgraph WORKERS["Workers (BunkerWeb)"]
      direction TB
      Worker1["Worker 1"]:::component
      WorkerN["Worker N"]:::component
    end

    %% ---- Bottom: App ----
    App["App"]:::backend
  end

  %% ============ Outside right ============
  Admin["Admin"]:::client

  %% ============ Traffic & control ===========
  %% Manager / control plane
  Manager -->|API 5000| Worker1
  Manager -->|API 5000| WorkerN
  Manager -->|bwcli| Redis
  Manager -->|Config| BDD

  %% User interface (UI)
  UI -->|Config| BDD
  UI -->|Reports / Bans| Redis
  BDD --- UI
  Redis --- UI
  linkStyle 6 stroke-width:0px;
  linkStyle 7 stroke-width:0px;

  %% Workers <-> Redis
  Worker1 -->|Shared cache| Redis
  WorkerN -->|Shared cache| Redis

  %% Workers -> App
  Worker1 -->|Legitimate traffic| App
  WorkerN -->|Legitimate traffic| App

  %% Client (right side) -> Load balancer -> Workers -> App
  Client -->|Request| LB
  LB -->|HTTP/TCP| Worker1
  LB -->|HTTP/TCP| WorkerN

  %% Admin -> UI
  UI --- Admin
  Admin -->|HTTP| UI
  linkStyle 15 stroke-width:0px;
```

!!! info "Understanding BunkerWeb APIs"
    BunkerWeb has two different API concepts:

    - An **internal API** that automatically connects managers and workers for orchestration. This is always enabled and does not require manual configuration.
    - An optional **API service** (`bunkerweb-api`) that exposes a public REST interface for automation tools (bwcli, CI/CD, etc.). This is disabled by default on Linux installations and is independent of the internal manager↔worker communications.

### Prerequisites

Before setting up a cluster, ensure you have:

- **2+ Linux hosts** with root/sudo access.
- **Network connectivity** between hosts (specifically on TCP port 5000 for the internal API).
- **Target Application** IP or hostname to protect.
- *(Optional)* **Load Balancer** (e.g., HAProxy) to distribute traffic among workers.

### 1. Install the Manager

The Manager is the brain of the cluster. It runs the Scheduler, Database, and optionally the Web UI.

!!! warning "Web UI Security"
    The Web UI listens on a specific port (default 7000) and should only be accessed by administrators. If you plan to expose the Web UI to the internet, we **strongly recommend** protecting it with a BunkerWeb instance in front of it.

=== "Linux"

    1. **Download and run the installer** on the manager host:

        ```bash
        # Download script and checksum
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc3/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc3/install-bunkerweb.sh.sha256

        # Verify checksum
        sha256sum -c install-bunkerweb.sh.sha256

        # Run installer
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "Security Notice"
            Always verify the script integrity with the provided checksum before executing it.

    2. **Select Option 2) Manager** and follow the prompts:

        | Prompt                     | Action                                                                                      |
        | :------------------------- | :------------------------------------------------------------------------------------------ |
        | **BunkerWeb instances**    | Enter space-separated IPs of your worker nodes (e.g., `192.168.10.11 192.168.10.12`).       |
        | **Whitelist IP**           | Accept the detected IP or enter a subnet (e.g., `192.168.10.0/24`) to allow API access.     |
        | **DNS resolvers**          | Press `N` for default or provide custom ones.                                               |
        | **HTTPS for internal API** | **Recommended:** `Y` to auto-generate certificates for secure manager-worker communication. |
        | **Web UI service**         | `Y` to enable the web interface (highly recommended).                                       |
        | **API service**            | `N` unless you need the public REST API for external tools.                                 |

    #### Secure and Expose the UI

    If you enabled the Web UI, you should secure it. You can host it on the Manager or a separate machine.

    === "Hosted on Manager"

        1. Edit `/etc/bunkerweb/ui.env` to set strong credentials:

        ```ini
        # OVERRIDE_ADMIN_CREDS=no
        ADMIN_USERNAME=admin
        ADMIN_PASSWORD=changeme
        # FLASK_SECRET=changeme
        # TOTP_ENCRYPTION_KEYS=changeme
        LISTEN_ADDR=0.0.0.0
        # LISTEN_PORT=7000
        FORWARDED_ALLOW_IPS=127.0.0.1
        # ENABLE_HEALTHCHECK=no
        ```

        !!! warning "Change default credentials"
            Replace `admin` and `changeme` with strong credentials before starting the UI service in production.

        2. Restart the UI:

        ```bash
        sudo systemctl restart bunkerweb-ui
        ```

    === "External Host"

        For better isolation, install the UI on a separate node.

        1. Run the installer and choose **Option 5) Web UI Only**.
        2. Edit `/etc/bunkerweb/ui.env` to connect to the Manager's database:

            ```ini
            # Database configuration (must match your manager's database)
            DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb
            # For PostgreSQL: postgresql://bunkerweb:changeme@db-host:5432/bunkerweb
            # For MySQL: mysql+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb

            # Redis configuration (if using Redis/Valkey for persistence)
            # If not provided, it is automatically taken from the database
            # REDIS_HOST=redis-host

            # Security credentials
            ADMIN_USERNAME=admin
            ADMIN_PASSWORD=changeme

            # Network settings
            LISTEN_ADDR=0.0.0.0
            # LISTEN_PORT=7000
            ```

        3. Restart the service:

            ```bash
            sudo systemctl restart bunkerweb-ui
            ```

        !!! tip "Firewall configuration"
            Ensure the UI host can reach the database and Redis ports. You may need to configure firewall rules on both the UI host and the database/Redis hosts.

=== "Docker"

    Create a `docker-compose.yml` file on the manager host:

    ```yaml title="docker-compose.yml"
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "192.168.1.11 192.168.1.12" # Replace with your worker IPs
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16" # Allow local networks
          # API_LISTEN_HTTPS: "yes" # Recommended to enable HTTPS for internal API
          # API_TOKEN: "my_secure_token" # Optional: set a token for added security
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        ports:
          - "7000:7000" # Expose the Web UI port
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the admin user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
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

      redis: # Redis service for the persistence of reports/bans/stats
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-redis

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-db:
        name: bw-db
      bw-redis:
        name: bw-redis
    ```

    Start the manager stack:

    ```bash
    docker compose up -d
    ```

### 2. Install the Workers

Workers are the nodes that process incoming traffic.

=== "Linux"

    1. **Run the installer** on each worker node (same commands as Manager).
    2. **Select Option 3) Worker** and configure:

        | Prompt                     | Action                                                     |
        | :------------------------- | :--------------------------------------------------------- |
        | **Manager IP**             | Enter the IP of your Manager node (e.g., `192.168.10.10`). |
        | **HTTPS for internal API** | Must match the Manager's setting (`Y` or `N`).             |

    The worker will automatically register with the Manager.

=== "Docker"

    Create a `docker-compose.yml` file on each worker node:

    ```yaml title="docker-compose.yml"
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
          - "5000:5000/tcp" # Internal API port
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
          # API_LISTEN_HTTPS: "yes" # Recommended to enable HTTPS for internal API (must match the Manager setting)
          # API_TOKEN: "my_secure_token" # Optional: set a token for added security (must match the Manager setting)
        restart: "unless-stopped"
    ```

    Start the worker:

    ```bash
    docker compose up -d
    ```

### 3. Manage Workers

You can add more workers later using the Web UI or CLI.

=== "Via the Web UI"

    1. **Go to the Instances tab**.
    2. **Click Add instance**.
    3. **Enter the worker's IP/Hostname** and save.

    <div class="grid grid-2" markdown style="display:grid; align-items:center;">
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - Create Instance](assets/img/ui-ha-create-instance.webp){ width="100%" }
      <figcaption>BunkerWeb UI - Create Instance</figcaption>
    </figure>
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - Create Instance Form](assets/img/ui-ha-create-instance-form.webp){ width="100%" }
      <figcaption>BunkerWeb UI - Create Instance Form</figcaption>
    </figure>
    </div>

=== "Via Configuration"

    === "Linux"

        1. **Edit** `/etc/bunkerweb/variables.env` on the Manager:

            ```bash
            BUNKERWEB_INSTANCES=192.168.10.11 192.168.10.12 192.168.10.13
            ```

        2. **Restart the Scheduler**:

            ```bash
            sudo systemctl restart bunkerweb-scheduler
            ```

    === "Docker"

        1. **Edit** the `docker-compose.yml` file on the Manager to update `BUNKERWEB_INSTANCES`.

        2. **Recreate the Scheduler container**:

            ```bash
            docker compose up -d bw-scheduler
            ```

### 4. Verify Setup

=== "Linux"

    1. **Check Status**: Log in to the Web UI (`http://<manager-ip>:7000`) and check the **Instances** tab. All workers should be **Up**.
    2. **Test Failover**: Stop BunkerWeb on one worker (`sudo systemctl stop bunkerweb`) and ensure traffic still flows.

=== "Docker"

    1. **Check Status**: Log in to the Web UI (`http://<manager-ip>:7000`) and check the **Instances** tab. All workers should be **Up**.
    2. **Test Failover**: Stop BunkerWeb on one worker (`docker compose stop bunkerweb`) and ensure traffic still flows.

### 5. Load Balancing

To distribute traffic across your workers, use a Load Balancer. We recommend using a Layer 4 (TCP) load balancer that supports the **PROXY protocol** to preserve client IP addresses.

=== "HAProxy - Layer 4 (TCP)"

    Here is a sample **HAProxy** configuration that passes traffic (TCP mode) while preserving client IPs via **PROXY protocol**.

    ```cfg title="haproxy.cfg"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode tcp
        bind *:80
        default_backend http_back

    frontend https_front
        mode tcp
        bind *:443
        default_backend https_back

    backend http_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:80 check send-proxy-v2
        server worker02 192.168.10.12:80 check send-proxy-v2

    backend https_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:443 check send-proxy-v2
        server worker02 192.168.10.12:443 check send-proxy-v2
    ```

=== "HAProxy - Layer 7 (HTTP)"

    Here is a sample **HAProxy** configuration for Layer 7 (HTTP) load balancing. It adds the `X-Forwarded-For` header so BunkerWeb can retrieve the client IP.

    ```cfg title="haproxy.cfg"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode http
        bind *:80
        default_backend http_back

    frontend https_front
        mode http
        bind *:443
        default_backend https_back

    backend http_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:80 check
        server worker02 192.168.10.12:80 check

    backend https_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:443 check
        server worker02 192.168.10.12:443 check
    ```

Reload HAProxy once the configuration is saved:

```bash
sudo systemctl restart haproxy
```

For more information, please refer to the [official HAProxy documentation](http://docs.haproxy.org/).

!!! tip "Configure Real IP"
    Don't forget to configure BunkerWeb to receive the real client IP (using PROXY protocol or X-Forwarded-For header).

    Please refer to the [Behind load balancer or reverse proxy](#behind-load-balancer-or-reverse-proxy) section to ensure you have the right client's IP address.

    Review `/var/log/bunkerweb/access.log` on each worker to confirm that requests arrive from the PROXY protocol network and that both workers share the load. Your BunkerWeb cluster is now ready to protect production workloads with high availability.

## Using custom DNS resolution mechanisms

BunkerWeb's NGINX configuration can be customized to use different DNS resolvers depending on your needs. This can be particularly useful in various scenarios:

1. To respect entries in your local `/etc/hosts` file
2. When you need to use custom DNS servers for certain domains
3. To integrate with local DNS caching solutions

### Using systemd-resolved

Many modern Linux systems use `systemd-resolved` for DNS resolution. If you want BunkerWeb to respect the content of your `/etc/hosts` file and use the system's DNS resolution mechanism, you can configure it to use the local systemd-resolved DNS service.

To verify that systemd-resolved is running on your system, you can use:

```bash
systemctl status systemd-resolved
```

To enable systemd-resolved as your DNS resolver in BunkerWeb, set the `DNS_RESOLVERS` setting to `127.0.0.53`, which is the default listening address for systemd-resolved:

=== "Web UI"

    Navigate to the **Global Settings** page and set the DNS resolvers to `127.0.0.53`

    <figure markdown>![DNS resolvers setting using web UI](assets/img/advanced-dns-resolvers.png){ align=center }<figcaption>DNS resolvers setting using web UI</figcaption></figure>

=== "Linux"

    You will need to modify the `/etc/bunkerweb/variables.env` file:

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    After making this change, reload the Scheduler to apply the configuration:

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

### Using dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) is a lightweight DNS, DHCP, and TFTP server that's commonly used for local DNS caching and customization. It's particularly useful when you need more control over your DNS resolution than systemd-resolved provides.

=== "Linux"

    First, install and configure dnsmasq on your Linux system:

    === "Debian/Ubuntu"

        ```bash
        # Install dnsmasq
        sudo apt-get update && sudo apt-get install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # Install dnsmasq
        sudo dnf install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    Then configure BunkerWeb to use dnsmasq by setting `DNS_RESOLVERS` to `127.0.0.1`:

    === "Web UI"

        Navigate to the **Global Settings** page, select the **NGINX** plugin and set the DNS resolvers to `127.0.0.1`.

        <figure markdown>![DNS resolvers setting using web UI](assets/img/advanced-dns-resolvers2.png){ align=center }<figcaption>DNS resolvers setting using web UI</figcaption></figure>

    === "Linux"

        You will need to modify the `/etc/bunkerweb/variables.env` file:

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        After making this change, reload the Scheduler:

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "All-in-one"

    When using the All-in-one container, run dnsmasq in a separate container and configure BunkerWeb to use it:

    ```bash
    # Create a custom network for DNS communication
    docker network create bw-dns

    # Run dnsmasq container using dockurr/dnsmasq with Quad9 DNS
    # Quad9 provides security-focused DNS resolution with malware blocking
    docker run -d \
        --name dnsmasq \
        --network bw-dns \
        -e DNS1="9.9.9.9" \
        -e DNS2="149.112.112.112" \
        -p 53:53/udp \
        -p 53:53/tcp \
        --cap-add=NET_ADMIN \
        --restart=always \
        dockurr/dnsmasq

    # Run BunkerWeb All-in-one with dnsmasq DNS resolver
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

=== "Docker"

    Add a dnsmasq service to your docker-compose file and configure BunkerWeb to use it:

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # Using Quad9 DNS servers for enhanced security and privacy
          # Primary: 9.9.9.9 (Quad9 with malware blocking)
          # Secondary: 149.112.112.112 (Quad9 backup server)
          DNS1: "9.9.9.9"
          DNS2: "149.112.112.112"
        ports:
          - 53:53/udp
          - 53:53/tcp
        cap_add:
          - NET_ADMIN
        restart: always
        networks:
          - bw-dns

      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...existing networks...
      bw-dns:
        name: bw-dns
    ```

## Custom configurations {#custom-configurations}

To customize and add custom configurations to BunkerWeb, you can take advantage of its NGINX foundation. Custom NGINX configurations can be added in different NGINX contexts, including configurations for the ModSecurity Web Application Firewall (WAF), which is a core component of BunkerWeb. More details about ModSecurity configurations can be found [here](features.md#custom-configurations).

Here are the available types of custom configurations:

- **http**: Configurations at the HTTP level of NGINX.
- **server-http**: Configurations at the HTTP/Server level of NGINX.
- **default-server-http**: Configurations at the Server level of NGINX, specifically for the "default server" when the supplied client name doesn't match any server name in `SERVER_NAME`.
- **modsec-crs**: Configurations applied before the OWASP Core Rule Set is loaded.
- **modsec**: Configurations applied after the OWASP Core Rule Set is loaded, or used when the Core Rule Set is not loaded.
- **crs-plugins-before**: Configurations for the CRS plugins, applied before the CRS plugins are loaded.
- **crs-plugins-after**: Configurations for the CRS plugins, applied after the CRS plugins are loaded.
- **stream**: Configurations at the Stream level of NGINX.
- **server-stream**: Configurations at the Stream/Server level of NGINX.

Custom configurations can be applied globally or specifically for a particular server, depending on the applicable context and whether the [multisite mode](features.md#multisite-mode) is enabled.

The method for applying custom configurations depends on the integration being used. However, the underlying process involves adding files with the `.conf` suffix to specific folders. To apply a custom configuration for a specific server, the file should be placed in a subfolder named after the primary server name.

Some integrations provide more convenient ways to apply configurations, such as using [Configs](https://docs.docker.com/engine/swarm/configs/) in Docker Swarm or [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) in Kubernetes. These options offer simpler approaches for managing and applying configurations.

=== "Web UI"

    Navigate to the **Configs** page, click on **Create new custom config**, you can then choose if it's a global one or specific to a service, the configuration type and the configuration name :

    <figure markdown>![Custom configurations using web UI](assets/img/advanced-config.png){ align=center }<figcaption>Custom configurations using web UI</figcaption></figure>

    Don't forget to click on the `💾 Save` button.

=== "Linux"

    When using the [Linux integration](integrations.md#linux), custom configurations must be written to the `/etc/bunkerweb/configs` folder.

    Here is an example for server-http/hello-world.conf :

    ```nginx
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Because BunkerWeb runs as an unprivileged user (nginx:nginx), you will need to edit the permissions :

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    Now let's check the status of the Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    If they are already running, we can reload it :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "All-in-one"

    When using the [All-in-one image](integrations.md#all-in-one-aio-image), you have two choices for adding custom configurations:

    - Using specific settings `*_CUSTOM_CONF_*` as environment variables when running the container (recommended).
    - Writing `.conf` files to the `/data/configs/` directory within the volume mounted to `/data`.

    **Using settings (Environment Variables)**

    The settings to use must follow the pattern `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<SITE>` : Optional primary server name if multisite mode is enabled and the config must be applied to a specific service.
    - `<TYPE>` : The type of config, accepted values are `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` and `SERVER_STREAM`.
    - `<NAME>` : The name of config without the `.conf` suffix.

    Here is a dummy example when running the All-in-one container:

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e "CUSTOM_CONF_SERVER_HTTP_hello-world=location /hello { \
            default_type 'text/plain'; \
            content_by_lua_block { \
              ngx.say('world'); \
            } \
          }" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Please note that if your container is already created, you will need to delete it and recreate it for the new environment variables to be applied.

    **Using files**

    The first thing to do is to create the folders :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    You can now write your configurations :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the scheduler container, you will need to mount the folder on /data :

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

=== "Docker"

    When using the [Docker integration](integrations.md#docker), you have two choices for the addition of custom configurations :

    - Using specific settings `*_CUSTOM_CONF_*` as environment variables (recommended)
    - Writing .conf files to the volume mounted on /data of the scheduler

    **Using settings**

    The settings to use must follow the pattern `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<SITE>` : optional primary server name if multisite mode is enabled and the config must be applied to a specific service
    - `<TYPE>` : the type of config, accepted values are `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` and `SERVER_STREAM`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
      environment:
        - |
          CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
              ngx.say('world')
            }
          }
      ...
    ```

    **Using files**

    The first thing to do is to create the folders :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    You can now write your configurations :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the scheduler container, you will need to mount the folder on /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), you have two choices for adding custom configurations :

    - Using specific settings `*_CUSTOM_CONF_*` as labels (easiest)
    - Writing .conf files to the volume mounted on /data of the scheduler

    **Using labels**

    !!! warning "Limitations using labels"
        When using labels with the Docker autoconf integration, you can only apply custom configurations for the corresponding web service. Applying **http**, **default-server-http**, **stream** or any global settings (like **server-http** or **server-stream** for all services) is not possible : you will need to mount files for that purpose.

    The labels to use must follow the pattern `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<TYPE>` : the type of config, accepted values are `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER` and `SERVER_STREAM`
    - `<NAME>` : the name of config without the .conf suffix

    Here is a dummy example using a docker-compose file :

    ```yaml
    myapp:
      image: bunkerity/bunkerweb-hello:v1.0
      labels:
        - |
          bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
                ngx.say('world')
            }
          }
      ...
    ```

    **Using files**

    The first thing to do is to create the folders :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    You can now write your configurations :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Because the scheduler runs as an unprivileged user with UID and GID 101, you will need to edit the permissions :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When starting the scheduler container, you will need to mount the folder on /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    When using the [Kubernetes integration](integrations.md#kubernetes),
    custom configurations are managed using [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    You do not need to mount the ConfigMap inside a Pod (for example as an environment variable or volume).
    The autoconf Pod watches ConfigMap events and updates the custom configuration whenever a change is detected.

    Annotate each ConfigMap you want the ingress controller to manage:

    - `bunkerweb.io/CONFIG_TYPE`: Required. Choose one of the supported custom configuration types (`http`, `server-http`,
      `default-server-http`, `modsec`, `modsec-crs`, `crs-plugins-before`, `crs-plugins-after`, `stream`, `server-stream`, or `settings`).
    - `bunkerweb.io/CONFIG_SITE`: Optional. Set to the primary server name (as exposed through your `Ingress`) to scope the configuration to that service;
      omit it to apply the config globally.

    Here is the example :

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: cfg-bunkerweb-all-server-http
      annotations:
        bunkerweb.io/CONFIG_TYPE: "server-http"
    data:
      myconf: |
      location /hello {
        default_type 'text/plain';
        content_by_lua_block {
          ngx.say('world')
        }
      }
    ```

    !!! info "How reconciliation works"
        - The ingress controller continuously watches annotated ConfigMaps.
        - If the `NAMESPACES` environment variable is set, only ConfigMaps from those namespaces are considered.
        - Creating or updating a managed ConfigMap triggers an immediate configuration reload.
        - Deleting the ConfigMap—or removing the `bunkerweb.io/CONFIG_TYPE` annotation—removes the associated custom configuration.
        - If you set `bunkerweb.io/CONFIG_SITE`, the referenced service must already exist; otherwise, the ConfigMap is ignored until the service appears.

    !!! tip "Custom Extra Config"
        Since version `1.6.0`, you can add or override settings by annotating a ConfigMap with `bunkerweb.io/CONFIG_TYPE=settings`.
        The autoconf ingress controller reads each entry under `data` and applies it like an environment variable:

        - Without `bunkerweb.io/CONFIG_SITE`, all keys are applied globally.
        - When `bunkerweb.io/CONFIG_SITE` is set, the controller automatically prefixes each key with `<server-name>_` (every `/` replaced by `_`) if the key is not already scoped. Add the prefix yourself if you need to mix global and site-specific keys in the same ConfigMap.
        - Invalid setting names or values are skipped and a warning is logged by the autoconf controller.

        Here is an example :

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # multisite setting that will be applied to all services that do not override it
          USE_REDIS: "yes" # global setting that will be applied globally
          ...
        ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    When using the [Swarm integration](integrations.md#swarm), custom configurations are managed using [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    To keep it simple, you don't even need to attach the Config to a service : the autoconf service is listening for Config events and will update the custom configurations when needed.

    When creating a Config, you will need to add special labels :

    * **bunkerweb.CONFIG_TYPE** : must be set to a valid custom configuration type (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream, server-stream or settings)
    * **bunkerweb.CONFIG_SITE** : set to a server name to apply configuration to that specific server (optional, will be applied globally if unset)

    Here is the example :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    There is no update mechanism : the alternative is to remove an existing config using `docker config rm` and then recreate it.

## Running many services in production {#running-many-services-in-production}

### Global CRS

!!! warning "CRS plugins"
    When the CRS is loaded globally, **CRS plugins are not supported**. If you need to use them, you will need to load the CRS per service.

If you use BunkerWeb in production with a large number of services, and you enable the **ModSecurity feature globally** with CRS rules, the time required to load BunkerWeb configurations may become too long, potentially resulting in a timeout.

The workaround is to load the CRS rules globally rather than per service. This behavior is not enabled by default for backward compatibility reasons and because it has a drawback: if you enable global CRS rule loading, **it will no longer be possible to define modsec-crs rules** (executed before the CRS rules) on a per-service basis. However, this limitation can be bypassed by writing global `modsec-crs` exclusion rules like this:

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

You can enable the global CRS loading by setting `USE_MODSECURITY_GLOBAL_CRS` to `yes`.

### Adjust max_allowed_packet for MariaDB/MySQL

It appears that the default value for the `max_allowed_packet` parameter in MariaDB and MySQL database servers is not sufficient when using BunkerWeb with a large number of services.

If you encounter errors like this, especially on the scheduler:

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

You will need to increase the `max_allowed_packet` on your database server.

## Persistence of bans and reports {#persistence-of-bans-and-reports}

By default, BunkerWeb stores bans and reports in a local Lua datastore. While simple and efficient, this setup means that data is lost when the instance is restarted. To ensure that bans and reports persist across restarts, you can configure BunkerWeb to use a remote [Redis](https://redis.io/) or [Valkey](https://valkey.io/) server.

**Why Use Redis/Valkey?**

Redis and Valkey are powerful, in-memory data stores commonly used as databases, caches, and message brokers. They are highly scalable and support a variety of data structures, including:

- **Strings**: Basic key-value pairs.
- **Hashes**: Field-value pairs within a single key.
- **Lists**: Ordered collections of strings.
- **Sets**: Unordered collections of unique strings.
- **Sorted Sets**: Ordered collections with scores.

By leveraging Redis or Valkey, BunkerWeb can persistently store bans, reports, and cache data, ensuring durability and scalability.

**Enabling Redis/Valkey Support**

To enable Redis or Valkey support, configure the following settings in your BunkerWeb configuration file:

```conf
# Enable Redis/Valkey support
USE_REDIS=yes

# Redis/Valkey server hostname or IP address
REDIS_HOST=<hostname>

# Redis/Valkey server port number (default: 6379)
REDIS_PORT=6379

# Redis/Valkey database number (default: 0)
REDIS_DATABASE=0
```

- **`USE_REDIS`**: Set to `yes` to enable Redis/Valkey integration.
- **`REDIS_HOST`**: Specify the hostname or IP address of the Redis/Valkey server.
- **`REDIS_PORT`**: Specify the port number for the Redis/Valkey server. Defaults to `6379`.
- **`REDIS_DATABASE`**: Specify the Redis/Valkey database number to use. Defaults to `0`.

If you require more advanced settings, such as authentication, SSL/TLS support, or Sentinel mode, refer to the [Redis plugin settings documentation](features.md#redis) for detailed guidance.

## Protect UDP/TCP applications

!!! example "Experimental feature"

	  This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

BunkerWeb offers the capability to function as a **generic UDP/TCP reverse proxy**, allowing you to protect any network-based applications operating at least on layer 4 of the OSI model. Instead of utilizing the "classical" HTTP module, BunkerWeb leverages the [stream module](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) of NGINX.

It's important to note that **not all settings and security features are available when using the stream module**. Additional information on this can be found in the [features](features.md) sections of the documentation.

Configuring a basic reverse proxy is quite similar to the HTTP setup, as it involves using the same settings: `USE_REVERSE_PROXY=yes` and `REVERSE_PROXY_HOST=myapp:9000`. Even when BunkerWeb is positioned behind a Load Balancer, the settings remain the same (with **PROXY protocol** being the supported option due to evident reasons).

On top of that, the following specific settings are used :

- `SERVER_TYPE=stream` : activate `stream` mode (generic UDP/TCP) instead of `http` one (which is the default)
- `LISTEN_STREAM_PORT=4242` : the listening "plain" (without SSL/TLS) port that BunkerWeb will listen on
- `LISTEN_STREAM_PORT_SSL=4343` : the listening "ssl/tls" port that BunkerWeb will listen on
- `USE_UDP=no` : listen for and forward UDP packets instead of TCP

For complete list of settings regarding `stream` mode, please refer to the [features](features.md) section of the documentation.

!!! tip "multiple listening ports"

    Since the `1.6.0` version, BunkerWeb supports multiple listening ports for the `stream` mode. You can specify them using the `LISTEN_STREAM_PORT` and `LISTEN_STREAM_PORT_SSL` settings.

    Here is an example :

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "All-in-one"

    You will need to add the settings to the environment variables when running the All-in-one container. You will also need to expose the stream ports.

    This example configures BunkerWeb to proxy two stream-based applications, `app1.example.com` and `app2.example.com`.

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e SERVICE_UI="no" \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e USE_REVERSE_PROXY="yes" \
        -e SERVER_TYPE="stream" \
        -e app1.example.com_REVERSE_PROXY_HOST="myapp1:9000" \
        -e app1.example.com_LISTEN_STREAM_PORT="10000" \
        -e app2.example.com_REVERSE_PROXY_HOST="myapp2:9000" \
        -e app2.example.com_LISTEN_STREAM_PORT="20000" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        -p 10000:10000/tcp \
        -p 20000:20000/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Please note that if your container is already created, you will need to delete it and recreate it for the new environment variables to be applied.

    Your applications (`myapp1`, `myapp2`) should be running in separate containers (or be otherwise accessible) and their hostnames/IPs (e.g., `myapp1`, `myapp2` used in `_REVERSE_PROXY_HOST`) must be resolvable and reachable from the `bunkerweb-aio` container. This typically involves connecting them to a shared Docker network.

    !!! note "Deactivate UI Service"
        Deactivating the UI service (e.g., by setting `SERVICE_UI=no` as an environment variable) is recommended as the Web UI is not compatible with `SERVER_TYPE=stream`.

=== "Docker"

    When using Docker integration, the easiest way of protecting existing network applications is to add the services in the `bw-services` network :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
      # Optional API token for authenticated API calls
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - "10000:10000" # app1
          - "20000:20000" # app2
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # Will be applied to all services
          SERVER_TYPE: "stream" # Will be applied to all services
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services

    volumes:
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
    ```

=== "Docker autoconf"

    Before running the [Docker autoconf integration](integrations.md#docker-autoconf) stack on your machine, you will need to edit the ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - "10000:10000" # app1
          - "20000:20000" # app2
    ...
    ```

    Once the stack is running, you can connect your existing applications to the `bw-services` network and configure BunkerWeb with labels :

    ```yaml
    services:
      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app1.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app2.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! example "Experimental feature"

        At the moment, [Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) does not support the `stream` mode. **What we are doing here is a workaround to make it work.**

        Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

    Before running the [Kubernetes integration](integrations.md#kubernetes) stack on your machine, you will need to open the ports on your load balancer :

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # Keep it if you want to use Let's Encrypt automation when using http challenge type
          port: 80
          targetPort: 8080
        - name: app1
          port: 10000
          targetPort: 10000
        - name: app2
          port: 20000
          targetPort: 20000
      selector:
        app: bunkerweb
    ```

    Once the stack is running, you can create your ingress resources :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # Will be applied to all services
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
                pathType: Prefix
                backend:
                  service:
                    name: svc-app2
                    port:
                      number: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app1
      namespace: services
      labels:
        app: app1
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app1
      template:
        metadata:
          labels:
            app: app1
        spec:
          containers:
            - name: app1
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app1"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app1
      namespace: services
    spec:
      selector:
        app: app1
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app2
      namespace: services
      labels:
        app: app2
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app2
      template:
        metadata:
          labels:
            app: app2
        spec:
          containers:
            - name: app2
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app2"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app2
      namespace: services
    spec:
      selector:
        app: app2
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ```

=== "Linux"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    SERVER_NAME=app1.example.com app2.example.com
    MULTISITE=yes
    USE_REVERSE_PROXY=yes
    SERVER_TYPE=stream
    app1.example.com_REVERSE_PROXY_HOST=myapp1.domain.or.ip:9000
    app1.example.com_LISTEN_STREAM_PORT=10000
    app2.example.com_REVERSE_PROXY_HOST=myapp2.domain.or.ip:9000
    app2.example.com_LISTEN_STREAM_PORT=20000
    ...
    ```

    Now let's check the status of the Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    If they are already running, we can reload it :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    Before running the [Swarm integration](integrations.md#swarm) stack on your machine, you will need to edit the ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          # app1
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
          # app2
          - published: 20000
            target: 20000
            mode: host
            protocol: tcp
    ...
    ```

    Once the stack is running, you can connect your existing applications to the `bw-services` network and configure BunkerWeb with labels :

    ```yaml
    services:

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## PHP

!!! example "Experimental feature"
	  At the moment, PHP support with BunkerWeb is still in beta and we recommend you use a reverse-proxy architecture if you can. By the way, PHP is not supported at all for some integrations like Kubernetes.

BunkerWeb supports PHP using external or remote [PHP-FPM](https://www.php.net/manual/en/install.fpm.php) instances. We will assume that you are already familiar with managing that kind of services.

 The following settings can be used :

- `REMOTE_PHP` : Hostname of the remote PHP-FPM instance.
- `REMOTE_PHP_PATH` : Root folder containing files in the remote PHP-FPM instance.
- `REMOTE_PHP_PORT` : Port of the remote PHP-FPM instance (*default is 9000*).
- `LOCAL_PHP` : Path to the local socket file of PHP-FPM instance.
- `LOCAL_PHP_PATH` : Root folder containing files in the local PHP-FPM instance.

=== "All-in-one"

    When using the [All-in-one image](integrations.md#all-in-one-aio-image), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb.
    - Set up a PHP-FPM container for your application and mount the folder containing PHP files.
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables when running BunkerWeb.

    If you enable the [multisite mode](features.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 directories, 2 files
    ```

    We will assume that your PHP apps are located into a folder named `www`. Please note that you will need to fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    You can now run BunkerWeb, configure it for your PHP application and also run the PHP apps. You will need to create a custom Docker network to allow BunkerWeb to communicate with your PHP-FPM containers.

    ```bash
    # Create a custom network
    docker network create php-network

    # Run PHP-FPM containers
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # Run BunkerWeb All-in-one
    docker run -d \
        --name bunkerweb-aio \
        --network php-network \
        -v ./www:/var/www/html \
        -v bw-storage:/data \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e REMOTE_PHP_PATH="/app" \
        -e app1.example.com_REMOTE_PHP="myapp1-php" \
        -e app2.example.com_REMOTE_PHP="myapp2-php" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Please note that if your container is already created, you will need to delete it and recreate it for the new environment variables to be applied.

=== "Docker"

    When using the [Docker integration](integrations.md#docker), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM container for your application and mount the folder containing PHP files
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as environment variables when starting BunkerWeb

    If you enable the [multisite mode](features.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    We will assume that your PHP apps are located into a folder named `www`. Please note that you will need to fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    You can now run BunkerWeb, configure it for your PHP application and also run the PHP apps :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # Will be applied to all services thanks to the MULTISITE setting
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: php:fpm
        volumes:
          - ./www/app1.example.com:/app
        networks:
          - bw-services

      myapp2:
        image: php:fpm
        volumes:
          - ./www/app2.example.com:/app
        networks:
          - bw-services

      myapp3:
        image: php:fpm
        volumes:
          - ./www/app3.example.com:/app
        networks:
          - bw-services

    volumes:
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
    ```

=== "Docker autoconf"

    !!! info "Multisite mode enabled"
        The [Docker autoconf integration](integrations.md#docker-autoconf) integration implies the use of multisite mode : protecting one PHP application is the same as protecting multiple ones.

    When using the [Docker autoconf integration](integrations.md#docker-autoconf), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM containers for your applications and mount the folder containing PHP apps
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as labels for your PHP-FPM container

    Since the Docker autoconf implies using the [multisite mode](features.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Once the folders are created, copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    When you start the BunkerWeb autoconf stack, mount the `www` folder into `/var/www/html` for the **Scheduler** container :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.8-rc3
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
        networks:
          - bw-docker

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-docker

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
    ```

    You can now create your PHP-FPM containers, mount the correct subfolders and use labels to configure BunkerWeb :

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.REMOTE_PHP=myapp1"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.REMOTE_PHP=myapp2"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          labels:
            - "bunkerweb.SERVER_NAME=app3.example.com"
            - "bunkerweb.REMOTE_PHP=myapp3"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! warning "PHP is not supported for Kubernetes"
        Kubernetes integration allows configuration through [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) and the BunkerWeb controller only supports HTTP applications at the moment.

=== "Linux"

    We will assume that you already have the [Linux integration](integrations.md#linux) stack running on your machine.

    By default, BunkerWeb will search for web files inside the `/var/www/html` folder. You can use it to store your PHP applications. Please note that you will need to configure your PHP-FPM service to get or set the user/group of the running processes and the UNIX socket file used to communicate with BunkerWeb.

    First of all, you will need to make sure that your PHP-FPM instance can access the files inside the `/var/www/html` folder and also that BunkerWeb can access the UNIX socket file in order to communicate with PHP-FPM. We recommend to set a different user like `www-data` for the PHP-FPM service and to give the nginx group access to the UNIX socket file. Here is corresponding PHP-FPM configuration :

    ```ini
    ...
    [www]
    user = www-data
    group = www-data
    listen = /run/php/php-fpm.sock
    listen.owner = www-data
    listen.group = nginx
    listen.mode = 0660
    ...
    ```

    Don't forget to restart your PHP-FPM service :

    ```shell
    systemctl restart php-fpm
    ```

    If you enable the [multisite mode](features.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    /var/www/html
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    Please note that you will need to fix the permissions so BunkerWeb (group `nginx`) can at least read files and list folders and PHP-FPM (user `www-data` but it might be different depending on your system) is the owner of the files and folders :

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    You can now edit the `/etc/bunkerweb/variable.env` file :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    Now let's check the status of the Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    If they are already running, we can reload it :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Deprecated"
        The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](integrations.md#kubernetes) instead.

        **More information can be found in the [Swarm integration documentation](integrations.md#swarm).**

    !!! info "Multisite mode enabled"
        The [Swarm integration](integrations.md#docker-autoconf) integration implies the use of multisite mode : protecting one PHP application is the same as protecting multiple ones.

    !!! info "Shared volume"
        Using PHP with the Docker Swarm integration needs a shared volume between all BunkerWeb and PHP-FPM instances which is not covered in this documentation.

    When using the [Swarm](integrations.md#swarm), to support PHP applications, you will need to :

    - Mount your PHP files into the `/var/www/html` folder of BunkerWeb
    - Set up a PHP-FPM containers for your applications and mount the folder containing PHP apps
    - Use the specific settings `REMOTE_PHP` and `REMOTE_PHP_PATH` as labels for your PHP-FPM container

    Since the Swarm integration implies using the [multisite mode](features.md#multisite-mode), you will need to create separate directories for each of your applications. Each subdirectory should be named using the first value of `SERVER_NAME`. Here is a dummy example :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    As an example, we will consider that you have a shared folder mounted on your worker nodes on the `/shared` endpoint.

    Once the folders are created, copy your files and fix the permissions so BunkerWeb (UID/GID 101) can at least read files and list folders and PHP-FPM (UID/GID 33 if you use the `php:fpm` image) is the owner of the files and folders :

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

    When you start the BunkerWeb stack, mount the `/shared/www` folder into `/var/www/html` for the **Scheduler** container :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    You can now create your PHP-FPM services, mount the correct subfolders and use labels to configure BunkerWeb :

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app1.example.com"
              - "bunkerweb.REMOTE_PHP=myapp1"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app2.example.com"
              - "bunkerweb.REMOTE_PHP=myapp2"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app3.example.com"
              - "bunkerweb.REMOTE_PHP=myapp3"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## IPv6

!!! example "Experimental feature"

    This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

By default, BunkerWeb will only listen on IPv4 addresses and won't use IPv6 for network communications. If you want to enable IPv6 support, you need to set `USE_IPV6=yes`. Please note that IPv6 configuration of your network and environment is out-of-the-scope of this documentation.

=== "Docker / Autoconf / Swarm"

    First of all, you will need to configure your Docker daemon to enable IPv6 support for containers and use ip6tables if needed. Here is sample configuration for your `/etc/docker/daemon.json` file :

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    You can now restart the Docker service to apply the changes :

    ```shell
    systemctl restart docker
    ```

    Once Docker is setup to support IPv6 you can add the `USE_IPV6` setting and configure the `bw-services` for IPv6 :

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          USE_IPv6: "yes"

    ...

    networks:
      bw-services:
        name: bw-services
        enable_ipv6: true
        ipam:
          config:
            - subnet: fd00:13:37::/48
              gateway: fd00:13:37::1

    ...
    ```

=== "Linux"

    You will need to add the settings to the `/etc/bunkerweb/variables.env` file :

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

    Let's check the status of BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    If they are already running, we can restart it :

    ```shell
    systemctl restart bunkerweb
    ```

    Otherwise, we will need to start it :

    ```shell
    systemctl start bunkerweb
    ```

## Logging configuration options

BunkerWeb offers flexible logging configuration, allowing you to send logs to multiple destinations (like files, stdout/stderr, or syslog) simultaneously. This is particularly useful for integrating with external log collectors while keeping local logs for the Web UI.

There are two main categories of logs to configure:

1. **Service Logs**: Logs generated by BunkerWeb components (Scheduler, UI, Autoconf, etc.). Controlled per service by `LOG_TYPES` (and optionally `LOG_FILE_PATH`, `LOG_SYSLOG_ADDRESS`, `LOG_SYSLOG_TAG`).
2. **Access & Error Logs**: HTTP access and error logs generated by NGINX. Only the `bunkerweb` service uses these (`ACCESS_LOG` / `ERROR_LOG` / `LOG_LEVEL`).

### Service Logs

Service logs are controlled by the `LOG_TYPES` setting, which can accept multiple values separated by spaces (e.g., `LOG_TYPES="stderr syslog"`).

| Value    | Description                                                                             |
| :------- | :-------------------------------------------------------------------------------------- |
| `file`   | Writes logs to a file. Required for the Web UI log viewer.                              |
| `stderr` | Writes logs to standard error. Standard for containerized environments (`docker logs`). |
| `syslog` | Sends logs to a syslog server. Requires `LOG_SYSLOG_ADDRESS` to be set.                 |

When using `syslog`, you should also configure:

- `LOG_SYSLOG_ADDRESS`: The address of the syslog server (e.g., `udp://bw-syslog:514` or `/dev/log`).
- `LOG_SYSLOG_TAG`: A unique tag for the service (e.g., `bw-scheduler`) to distinguish its entries.
- `LOG_FILE_PATH`: Path for file output when `LOG_TYPES` includes `file` (for example, `/var/log/bunkerweb/scheduler.log`).

### Access and Error Logs

These are standard NGINX logs, configured via **the `bunkerweb` service only**. They support multiple destinations by suffixing the setting name (e.g., `ACCESS_LOG`, `ACCESS_LOG_1` and matching `LOG_FORMAT`, `LOG_FORMAT_1` or `ERROR_LOG`, `ERROR_LOG_1` and their respective `LOG_LEVEL`, `LOG_LEVEL_1`).

- `ACCESS_LOG`: Destination for access logs (default: `/var/log/bunkerweb/access.log`). Accepts file path, `syslog:server=host[:port][,param=value]`, shared buffer `memory:name:size`, or `off` to disable. See [NGINX access_log documentation](https://nginx.org/en/docs/http/ngx_http_log_module.html#access_log) for details.
- `ERROR_LOG`: Destination for error logs (default: `/var/log/bunkerweb/error.log`). Accepts file path, `stderr`, `syslog:server=host[:port][,param=value]`, or shared buffer `memory:size`. See [NGINX error_log documentation](https://nginx.org/en/docs/ngx_core_module.html#error_log) for details.
- `LOG_LEVEL`: Verbosity of error logs (default: `notice`).

These settings accept standard NGINX values, including file paths, `stderr`, `syslog:server=...` (see [NGINX syslog documentation](https://nginx.org/en/docs/syslog.html)), or shared memory buffers. They support multiple destinations via numbered suffixes (see the [multiple settings convention](features.md#multiple-settings)). Other services (Scheduler, UI, Autoconf, etc.) rely solely on `LOG_TYPES`/`LOG_FILE_PATH`/`LOG_SYSLOG_*`.

**Example with multiple access/error logs (bunkerweb only, numbered suffixes):**

```conf
ACCESS_LOG=/var/log/bunkerweb/access.log
ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_FORMAT=$host $remote_addr - $request_id $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
LOG_FORMAT_1=$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
ERROR_LOG=/var/log/bunkerweb/error.log
ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_LEVEL=notice
LOG_LEVEL_1=error
```

### Integration Defaults & Examples

=== "Linux"

    **Default behavior**: `LOG_TYPES="file"`. Logs are written to `/var/log/bunkerweb/*.log`.

    **Example**: Keep local files (for Web UI) and also mirror to the system syslog.

    ```conf
    # Service logs (set in /etc/bunkerweb/variables.env or specific service env files)
    LOG_TYPES="file syslog"
    LOG_SYSLOG_ADDRESS=/dev/log
    SCHEDULER_LOG_FILE_PATH=/var/log/bunkerweb/scheduler.log
    UI_LOG_FILE_PATH=/var/log/bunkerweb/ui.log
    # ...
    # LOG_SYSLOG_TAG is automatically set per service (override per-service if needed)

    # NGINX logs (bunkerweb service only; set in /etc/bunkerweb/variables.env)
    ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb_access
    ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
    ```

=== "Docker / Autoconf / Swarm"

    **Default behavior**: `LOG_TYPES="stderr"`. Logs are visible via `docker logs`.

    **Example (Adapted from the quickstart guide)**: Keep `docker logs` (stderr) AND send to a central syslog container (needed for Web UI and CrowdSec).

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for both services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      # Optional: set an API token and mirror it in both containers
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      # Service Logs
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"
      # LOG_SYSLOG_TAG will be automatically set per service (override per-service if needed)
      # NGINX Logs: Send to Syslog (bunkerweb only)
      ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
      ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          <<: *bw-env # We use the anchor to avoid repeating the same settings for all services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *bw-env
        volumes:
          - bw-logs:/var/log/bunkerweb # This is used to read the syslog logs from the Web UI
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
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

      redis: # Redis service for the persistence of reports/bans/stats
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
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
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      redis-data:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

### Syslog-ng configuration

Here is an example of a `syslog-ng.conf` file that you can use to forward the logs to a file:

```conf
@version: 4.10

# Source configuration to receive logs sent by BunkerWeb services (ACCESS_LOG / ERROR_LOG and LOG_TYPES=syslog)
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
    logrotate(
      enable(yes),
      size(100MB),
      rotations(7)
    )
  );
};

# Log path to direct logs to dynamically named files
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Docker logging best practices

When using Docker, it's important to manage container logs to prevent them from consuming excessive disk space. By default, Docker uses the `json-file` logging driver, which can lead to very large log files if left unconfigured.

To avoid this, you can configure log rotation. This can be done for specific services in your `docker-compose.yml` file, or globally for the Docker daemon.

**Per-service configuration**

You can configure the logging driver for your services in your `docker-compose.yml` file to automatically rotate the logs. Here is an example that keeps up to 10 log files of 20MB each:

```yaml
services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8-rc3
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "10"
    ...
```

This configuration ensures that logs are rotated, preventing them from filling up your disk. You can apply this to any service in your Docker Compose setup.

**Global settings (daemon.json)**

If you want to apply these logging settings to all containers on the host by default, you can configure the Docker daemon by editing (or creating) the `/etc/docker/daemon.json` file:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "10"
  }
}
```

After modifying `daemon.json`, you need to restart the Docker daemon for the changes to take effect:

```shell
sudo systemctl restart docker
```

These global settings will be inherited by all containers. However, any logging configuration defined on a per-service basis in a `docker-compose.yml` file will override the global settings in `daemon.json`.

## Security tuning {#security-tuning}

BunkerWeb offers many security features that you can configure with [features](features.md). Even if the default values of settings ensure a minimal "security by default", we strongly recommend you tune them. By doing so you will be able to ensure the security level of your choice but also manage false positives.

!!! tip "Other features"
    This section only focuses on security tuning, see the [features](features.md) section of the documentation for other settings.

<figure markdown>
  ![Overview](assets/img/core-order.svg){ align=center }
  <figcaption>Overview and order of the core security plugins</figcaption>
</figure>

## CrowdSec Console integration

If you aren’t already familiar with CrowdSec Console integration, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) leverages crowdsourced intelligence to combat cyber threats. Think of it as the "Waze of cybersecurity"—when one server is attacked, other systems worldwide are alerted and protected from the same attackers. You can learn more about it [here](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

**Congratulations, your BunkerWeb instance is now enrolled in your CrowdSec Console!**

Pro tip: When viewing your alerts, click the "columns" option and check the "context" checkbox to access BunkerWeb-specific data.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb data shown in the context column</figcaption>
</figure>

## Monitoring and reporting

### Monitoring <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

The monitoring plugin lets you collect and retrieve metrics about BunkerWeb. By enabling it, your instance(s) will start collecting various data related to attacks, requests and performance. You can then retrieve them by calling the `/monitoring` API endpoint on regular basis or by using other plugins like the Prometheus exporter one.

**List of features**

- Enable collection of various BunkerWeb metrics
- Retrieve metrics from the API
- Use in combination with other plugins (e.g. Prometheus exporter)
- Dedicate UI page to monitor your instance(s)

**List of settings**

| Setting                        | Default | Context | Multiple | Description                                   |
| ------------------------------ | ------- | ------- | -------- | --------------------------------------------- |
| `USE_MONITORING`               | `yes`   | global  | no       | Enable monitoring of BunkerWeb.               |
| `MONITORING_METRICS_DICT_SIZE` | `10M`   | global  | no       | Size of the dict to store monitoring metrics. |

### Prometheus exporter <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

The Prometheus exporter plugin adds a [Prometheus exporter](https://prometheus.io/docs/instrumenting/exporters/) on your BunkerWeb instance(s). When enabled, you can configure your Prometheus instance(s) to scrape a specific endpoint on Bunkerweb and gather internal metrics.

We also provide a [Grafana dashboard](https://grafana.com/grafana/dashboards/20755-bunkerweb/) that you can import into your own instance and connect to your own Prometheus datasource.

**Please note that the use of Prometheus exporter plugin requires to enable the Monitoring plugin (`USE_MONITORING=yes`)**

**List of features**

- Prometheus exporter providing internal BunkerWeb metrics
- Dedicated and configurable port, listen IP and URL
- Whitelist IP/network for maximum security

**List of settings**

| Setting                        | Default                                               | Context | Multiple | Description                                                              |
| ------------------------------ | ----------------------------------------------------- | ------- | -------- | ------------------------------------------------------------------------ |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global  | no       | Enable the Prometheus export.                                            |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global  | no       | Listening IP of the Prometheus exporter.                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global  | no       | Listening port of the Prometheus exporter.                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global  | no       | HTTP URL of the Prometheus exporter.                                     |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global  | no       | List of IP/networks allowed to contact the Prometheus exporter endpoint. |

### Reporting <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

!!! warning "Monitoring plugin needed"
    This plugins requires the Monitoring Pro plugin to be installed and enabled with the `USE_MONITORING` setting set to `yes`.

The Reporting plugin provides a comprehensive solution for regular reporting of important data from BunkerWeb, including global statistics, attacks, bans, requests, reasons, and AS information. It offers a wide range of features, including automatic report creation, customization options, and seamless integration with monitoring pro plugin. With the Reporting plugin, you can easily generate and manage reports to monitor the performance and security of your application.

**List of features**

- Regular reporting of important data from BunkerWeb, including global statistics, attacks, bans, requests, reasons, and AS information.
- Integration with Monitoring Pro plugin for seamless integration and enhanced reporting capabilities.
- Support for webhooks (classic, Discord, and Slack) for real-time notifications.
- Support for SMTP for email notifications.
- Configuration options for customization and flexibility.

**List of settings**

| Setting                        | Default            | Context | Description                                                                        |
| ------------------------------ | ------------------ | ------- | ---------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global  | Enable sending the report via email (HTML).                                        |
| `USE_REPORTING_WEBHOOK`        | `no`               | global  | Enable sending the report via webhook (Markdown).                                  |
| `REPORTING_SCHEDULE`           | `weekly`           | global  | Report cadence: `daily`, `weekly`, or `monthly`.                                   |
| `REPORTING_WEBHOOK_URLS`       |                    | global  | Space-separated webhook URLs; Discord and Slack are auto-detected.                 |
| `REPORTING_SMTP_EMAILS`        |                    | global  | Space-separated email recipients.                                                  |
| `REPORTING_SMTP_HOST`          |                    | global  | SMTP server hostname or IP.                                                        |
| `REPORTING_SMTP_PORT`          | `465`              | global  | SMTP port. Use `465` for SSL, `587` for TLS.                                       |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global  | Sender address (disable 2FA if required by your provider).                         |
| `REPORTING_SMTP_FROM_USER`     |                    | global  | SMTP username (falls back to the sender email when omitted and a password is set). |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global  | SMTP password.                                                                     |
| `REPORTING_SMTP_SSL`           | `SSL`              | global  | Connection security: `no`, `SSL`, or `TLS`.                                        |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global  | Subject line for email deliveries.                                                 |

!!! info "Behavior notes"
    - `REPORTING_SMTP_EMAILS` is required when SMTP delivery is enabled; `REPORTING_WEBHOOK_URLS` is required when webhook delivery is enabled.
    - If both webhooks and SMTP fail, delivery is retried on the next scheduled run.
    - HTML and Markdown templates live in `reporting/files/`; customize with caution to keep placeholders intact.

## Backup and restore

### Backup S3 <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :white_check_mark:

The Backup S3 tool seamlessly automates data protection, similar to the community backup plugin. However, it stands out by securely storing backups directly in an S3 bucket.

By activating this feature, you're proactively safeguarding your **data's integrity**. Storing backups **remotely** shields crucial information from threats like **hardware failures**, **cyberattacks**, or **natural disasters**. This ensures both **security** and **availability**, enabling swift recovery during **unexpected events**, preserving **operational continuity**, and ensuring **peace of mind**.

??? warning "Information for Red Hat Enterprise Linux (RHEL) 8.9 users"
    If you are using **RHEL 8.9** and plan on using an **external database**, you will need to install the `mysql-community-client` package to ensure the `mysqldump` command is available. You can install the package by executing the following commands:

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

        1. **Install the PostgreSQL repository configuration package**

            ```bash
            dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
            ```

        2. **Install the PostgreSQL client**

            ```bash
            dnf install postgresql<version>
            ```

**List of features**

- Automatic data backup to an S3 bucket
- Flexible scheduling options: daily, weekly, or monthly
- Rotation management for controlling the number of backups to keep
- Customizable compression level for backup files

**List of settings**

| Setting                       | Default | Context | Description                                  |
| ----------------------------- | ------- | ------- | -------------------------------------------- |
| `USE_BACKUP_S3`               | `no`    | global  | Enable or disable the S3 backup feature      |
| `BACKUP_S3_SCHEDULE`          | `daily` | global  | The frequency of the backup                  |
| `BACKUP_S3_ROTATION`          | `7`     | global  | The number of backups to keep                |
| `BACKUP_S3_ENDPOINT`          |         | global  | The S3 endpoint                              |
| `BACKUP_S3_BUCKET`            |         | global  | The S3 bucket                                |
| `BACKUP_S3_DIR`               |         | global  | The S3 directory                             |
| `BACKUP_S3_REGION`            |         | global  | The S3 region                                |
| `BACKUP_S3_ACCESS_KEY_ID`     |         | global  | The S3 access key ID                         |
| `BACKUP_S3_ACCESS_KEY_SECRET` |         | global  | The S3 access key secret                     |
| `BACKUP_S3_COMP_LEVEL`        | `6`     | global  | The compression level of the backup zip file |

#### Manual backup

To manually initiate a backup, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

This command will create a backup of your database and store it in the S3 bucket specified in the `BACKUP_S3_BUCKET` setting.

You can also specify a custom S3 bucket for the backup by providing the `BACKUP_S3_BUCKET` environment variable when executing the command:

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "Specifications for MariaDB/MySQL"

    In case you are using MariaDB/MySQL, you may encounter the following error when trying to backup your database:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    To resolve this issue, you can execute the following command to change the authentication plugin to `mysql_native_password`:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    If you're using the Docker integration, you can add the following command to the `docker-compose.yml` file to automatically change the authentication plugin:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

#### Manual restore

To manually initiate a restore, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

This command will create a temporary backup of your database in the S3 bucket specified in the `BACKUP_S3_BUCKET` setting and restore your database to the latest backup available in the bucket.

You can also specify a custom backup file for the restore by providing the path to it as an argument when executing the command:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "In case of failure"

    Don't worry if the restore fails, you can always restore your database to the previous state by executing the command again as a backup is created before the restore:

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

## Migration <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :white_check_mark:

The Migration plugin **revolutionizes** BunkerWeb configuration transfers between instances with its **user-friendly web interface**, simplifying the entire migration journey. Whether you're upgrading systems, scaling infrastructure, or transitioning environments, this tool empowers you to effortlessly transfer **settings, preferences, and data** with unmatched ease and confidence. Say goodbye to cumbersome manual processes and hello to a **seamless, hassle-free migration experience**.

**List of features**

- **Effortless Migration:** Easily transfer BunkerWeb configurations between instances without the complexities of manual procedures.

- **Intuitive Web Interface:** Navigate through the migration process effortlessly with a user-friendly web interface designed for intuitive operation.

- **Cross-Database Compatibility:** Enjoy seamless migration across various database platforms, including SQLite, MySQL, MariaDB, and PostgreSQL, ensuring compatibility with your preferred database environment.

### Create a migration file

To manually create a migration file, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin migration create /path/to/migration/file
    ```

=== "Docker"

    1. Create a migration file:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /path/to/migration/file
        ```

    2. Copy the migration file to your local machine:

        ```bash
        docker cp <scheduler_container>:/path/to/migration/file /path/to/migration/file
        ```

This command will create a backup of your database and store it in the backup directory specified in the command.

!!! note "Specifications for MariaDB/MySQL"

    In case you are using MariaDB/MySQL, you may encounter the following error when trying to backup your database:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    To resolve this issue, you can execute the following command to change the authentication plugin to `mysql_native_password`:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    If you're using the Docker integration, you can add the following command to the `docker-compose.yml` file to automatically change the authentication plugin:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

### Initialize a migration

To manually initialize a migration, execute the following command:

=== "Linux"

    ```bash
    bwcli plugin migration migrate /path/to/migration/file
    ```

=== "Docker"

    1. Copy the migration file to the container:

        ```bash
        docker cp /path/to/migration/file <scheduler_container>:/path/to/migration/file
        ```

    2. Initialize the migration:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /path/to/migration/file
        ```

=== "All-in-one"

    1. Copy the migration file to the container:

        ```bash
        docker cp /path/to/migration/file bunkerweb-aio:/path/to/migration/file
        ```

    2. Initialize the migration:

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /path/to/migration/file
        ```

This command seamlessly migrates your BunkerWeb data to precisely match the configuration outlined in the migration file.

## Anti DDoS <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM support :x:

The **Anti DDoS** Plugin provides advanced protection against Distributed Denial of Service (DDoS) attacks by monitoring, analyzing, and filtering suspicious traffic in real-time.

By employing a **sliding window mechanism**, the plugin maintains an in-memory dictionary of request timestamps to detect abnormal traffic spikes from individual IP addresses. Based on the configured security mode, it can either block offending connections or log the suspicious activity for further review.

### Features

- **Real-Time Traffic Analysis:** Continuously monitors incoming requests to detect potential DDoS attacks.
- **Sliding Window Mechanism:** Tracks recent request activity within a configurable time window.
- **Configurable Thresholds:** Allows you to define the maximum number of suspicious requests per IP.
- **Advanced Blocking Logic:** Evaluates both per-IP request counts and the number of distinct IPs exceeding the threshold.
- **Flexible Security Modes:** Choose between immediate connection blocking or detection-only (logging) mode.
- **Optimized In-Memory Datastore:** Ensures high-speed lookups and efficient metric tracking.
- **Automatic Housekeeping:** Periodically clears outdated data to maintain optimal performance.

### Configuration

Customize the plugin behavior using the following settings:

| Setting                      | Default       | Context | Multiple | Description                                                                                    |
| ---------------------------- | ------------- | ------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global  | no       | Enable or disable the Anti DDoS protection. Set to `"yes"` to activate the plugin.             |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global  | no       | Size of the in-memory datastore for tracking DDoS metrics (e.g., `10M`, `500k`).               |
| `ANTIDDOS_THRESHOLD`         | `100`         | global  | no       | Maximum number of suspicious requests allowed per IP within the defined time window.           |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global  | no       | Time window in seconds during which suspicious requests are tallied.                           |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global  | no       | HTTP status codes considered suspicious and used to trigger anti-DDoS actions.                 |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global  | no       | Minimum number of distinct IPs that must exceed the threshold before enforcing the block mode. |

### Best Practices

- **Threshold Tuning:** Adjust `ANTIDDOS_THRESHOLD` and `ANTIDDOS_WINDOW_TIME` based on your typical traffic patterns.
- **Status Code Review:** Regularly update `ANTIDDOS_STATUS_CODES` to capture new or evolving suspicious behaviors.
- **Monitoring:** Analyze logs and metrics periodically to fine-tune settings and improve overall protection.

## User Manager <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="User Manager" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The User Management Plugin offers a robust interface for administering user accounts within your system.

With this plugin, administrators can effortlessly create, update, and disable user accounts, manage user roles, toggle two-factor authentication (2FA), and view detailed user information such as last login timestamps and account statuses (active or inactive). Designed with security and ease-of-use in mind, this plugin simplifies routine user management tasks while ensuring compliance and auditability.

### Features

- **User Account Operations:** Import in CSV/XSLX format, Create, edit, and delete user accounts with ease.
- **Role-Based Access Control:** Assign and modify user roles to manage permissions and access levels.
- **2FA Management:** Disable two-factor authentication based on administrative decisions.
- **Comprehensive User Insights:** Monitor key user data including last login times, account creation dates, and active/inactive status.
- **Audit Logging:** Maintain an audit trail for all user management actions for enhanced security and compliance.

<figure markdown>
  ![Overview](assets/img/user-manager.png){ align=center }
  <figcaption>User Manager page</figcaption>
</figure>

<figure markdown>
  ![Create user form](assets/img/user-manager-create.png){ align=center }
  <figcaption>User Manager - Create user form</figcaption>
</figure>

<figure markdown>
  ![Activities page](assets/img/user-manager-activities.png){ align=center }
  <figcaption>User Manager - Activities page</figcaption>
</figure>

## Easy Resolve <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/45vX0WJqjxo" title="Easy Resolve" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The Easy Resolve Plugin lets you quickly remediate false positives and recurring issues directly from the Reports page. It turns guided "Resolve" actions into safe, scoped configuration updates—without manual editing.

### Features

- One‑click actions from Reports and report details.
- Context‑aware suggestions for ModSecurity, blacklist, DNSBL, Rate limiting, Allowed HTTP methods and whitelisted/blacklisted Country.
- Generates safe ModSecurity exclusions or updates ignore lists.
- Applies changes at service or global scope with permission checks.
- Optional auto‑open of the related configuration page after apply.

<figure markdown>
  ![Overview](assets/img/easy-resolve.png){ align=center }
  <figcaption>Reports page - with Easy Resolve</figcaption>
</figure>

## Load Balancer <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/cOVp0rAt5nw?si=iVhDio8o8S4F_uag" title="Load Balancer" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The Load Balancer Plugin turns BunkerWeb into a traffic director with guardrails. Declare upstream pools once, point your reverse proxy at them, and let health-aware balancing keep users on responsive backends. Sticky cookie mode issues a `BWLBID` cookie automatically so sessions stay anchored where you want them.

### Features

- Per-upstream blocks: name pools and reuse them across reverse proxy hosts.
- Flexible balancing: round-robin by default, or sticky via IP or signed cookie.
- Smart targets: optional DNS resolution for hostname backends plus keepalive tuning.
- Built-in health: HTTP/HTTPS probes with custom paths, intervals, status codes, and SSL checks.
- Session continuity: automatic `BWLBID` cookie when sticky-cookie mode is enabled.

### Configuration

**Upstream definition**

| Setting                                   | Default       | Context | Multiple | Description                                                                     |
| ----------------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------------------- |
| `LOADBALANCER_UPSTREAM_NAME`              |               | global  | yes      | Upstream identifier (referenced by `REVERSE_PROXY_HOST`).                       |
| `LOADBALANCER_UPSTREAM_SERVERS`           |               | global  | yes      | Space-separated list of backend addresses (e.g. `10.0.0.1:8080 10.0.0.2:8080`). |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin` | global  | yes      | Balancing strategy (`round-robin` or `sticky`).                                 |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`          | global  | yes      | Sticky method (`ip` or `cookie`). Cookie mode issues `BWLBID`.                  |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`          | global  | yes      | Resolve upstream hostnames via DNS.                                             |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |               | global  | yes      | Keepalive connections per worker.                                               |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`         | global  | yes      | Idle timeout for keepalive connections.                                         |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`          | global  | yes      | Maximum lifetime for keepalive connections.                                     |

**Healthchecks**

| Setting                                   | Default   | Context | Multiple | Description                                          |
| ----------------------------------------- | --------- | ------- | -------- | ---------------------------------------------------- |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`     | global  | no       | Shared dictionary size for healthcheck state.        |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status` | global  | yes      | Path to probe on each backend.                       |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`    | global  | yes      | Interval between checks (ms).                        |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`    | global  | yes      | Timeout per check (ms).                              |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`       | global  | yes      | Consecutive failures before marking down.            |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`       | global  | yes      | Consecutive successes before marking up.             |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`     | global  | yes      | Space-separated list of valid HTTP status codes.     |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`      | global  | yes      | Maximum concurrent probes.                           |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`    | global  | yes      | Protocol for healthchecks (`http` or `https`).       |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`     | global  | yes      | Verify TLS certificates when using HTTPS checks.     |
| `LOADBALANCER_HEALTHCHECK_HOST`           |           | global  | yes      | Override Host header during checks (useful for SNI). |

### Quick Start

1. Define your pool: set `LOADBALANCER_UPSTREAM_NAME=my-app` and list targets in `LOADBALANCER_UPSTREAM_SERVERS` (e.g. `10.0.0.1:8080 10.0.0.2:8080`).
2. Point traffic: set `REVERSE_PROXY_HOST=http://my-app` so the reverse proxy uses the named upstream.
3. Pick a mode: keep default round-robin or set `LOADBALANCER_UPSTREAM_MODE=sticky` with `LOADBALANCER_UPSTREAM_STICKY_METHOD=cookie` or `ip`.
4. Add health: keep `/status` or adjust URLs, intervals, and valid statuses to mirror your app behavior.
5. Tune connections: configure keepalive values to reuse backend connections and reduce handshake overhead.

### Usage Tips

- Match `REVERSE_PROXY_HOST` to `LOADBALANCER_UPSTREAM_NAME` when using sticky cookies so clients pin to the right pool.
- Keep healthcheck intervals and timeouts balanced to avoid flapping on slow links.
- Enable `LOADBALANCER_UPSTREAM_RESOLVE` when pointing to hostnames that may change via DNS.
- Tune keepalive values to mirror backend capacity and connection reuse goals.

## Custom Pages <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

The Custom Pages plugin lets you replace BunkerWeb's built-in pages (error pages, default server page, and antibot challenge pages) with your own custom HTML or Lua templates. This allows you to maintain consistent branding across all user-facing pages served by BunkerWeb.

### Features

- **Per-service custom error pages** and **antibot challenge pages** (captcha, JavaScript check, reCAPTCHA, hCaptcha, Turnstile, mCaptcha).
- **Global custom default server page** for the fallback/default vhost.
- **HTML parsing and Lua template tag balance checks** before a template is accepted.
- **Automatic caching** to `/var/cache/bunkerweb/custom_pages` with change detection to trigger reloads.
- **Per-site or global configuration** through settings/UI or environment variables.

### How It Works

1. On start (or when settings change), the `custom-pages.py` job reads the configured template paths.
2. Each file must exist and be readable by the scheduler; the job validates HTML structure and balanced Lua template tags (`{% %}`, `{{ }}`, `{* *}`).
3. Accepted files are cached under `/var/cache/bunkerweb/custom_pages/<type>.html`; missing/empty settings remove the cached file.
4. NGINX is pointed to the cache directory via `$template_root` when at least one cached page exists, so your templates are served instead of the defaults.

### Configuration Settings

| Setting                          | Default | Context   | Description                                                 |
| -------------------------------- | ------- | --------- | ----------------------------------------------------------- |
| `CUSTOM_ERROR_PAGE`              |         | multisite | Absolute path to the custom error page template.            |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |         | global    | Absolute path to the custom default server page template.   |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |         | multisite | Absolute path to the custom antibot CAPTCHA challenge page. |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |         | multisite | Absolute path to the custom antibot JavaScript check page.  |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |         | multisite | Absolute path to the custom antibot reCAPTCHA page.         |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |         | multisite | Absolute path to the custom antibot hCaptcha page.          |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |         | multisite | Absolute path to the custom antibot Turnstile page.         |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |         | multisite | Absolute path to the custom antibot mCaptcha page.          |

### Template Variables Reference

BunkerWeb templates use the [lua-resty-template](https://github.com/bungle/lua-resty-template) engine. The following variables are available depending on the page type:

#### Error Page Variables

These variables are available in custom error page templates (`CUSTOM_ERROR_PAGE`):

| Variable         | Type   | Description                                                  |
| ---------------- | ------ | ------------------------------------------------------------ |
| `title`          | string | Full page title (e.g., `403                                  | Forbidden`) |
| `error_title`    | string | Error title text (e.g., `Forbidden`)                         |
| `error_code`     | string | HTTP status code (e.g., `403`, `404`, `500`)                 |
| `error_text`     | string | Descriptive error message                                    |
| `error_type`     | string | Error category: `client` (4xx) or `server` (5xx)             |
| `error_solution` | string | Suggested solution text                                      |
| `nonce_script`   | string | Nonce value for inline `<script>` tags (CSP compliance)      |
| `nonce_style`    | string | Nonce value for inline `<style>` tags (CSP compliance)       |
| `request_id`     | string | Unique request identifier for debugging                      |
| `client_ip`      | string | Client's IP address                                          |
| `request_time`   | string | Timestamp of the request (format: `YYYY-MM-DD HH:MM:SS UTC`) |

#### Default Server Page Variables

These variables are available in custom default server page templates (`CUSTOM_DEFAULT_SERVER_PAGE`):

| Variable      | Type   | Description                                            |
| ------------- | ------ | ------------------------------------------------------ |
| `nonce_style` | string | Nonce value for inline `<style>` tags (CSP compliance) |

#### Antibot Challenge Page Variables

These variables are available in antibot challenge page templates:

**Common variables (all antibot pages):**

| Variable       | Type   | Description                                             |
| -------------- | ------ | ------------------------------------------------------- |
| `antibot_uri`  | string | Form action URI for submitting the challenge            |
| `nonce_script` | string | Nonce value for inline `<script>` tags (CSP compliance) |
| `nonce_style`  | string | Nonce value for inline `<style>` tags (CSP compliance)  |

**JavaScript challenge (`CUSTOM_ANTIBOT_JAVASCRIPT_PAGE`):**

| Variable | Type   | Description                                  |
| -------- | ------ | -------------------------------------------- |
| `random` | string | Random string used for proof-of-work solving |

**Captcha (`CUSTOM_ANTIBOT_CAPTCHA_PAGE`):**

| Variable  | Type   | Description                                |
| --------- | ------ | ------------------------------------------ |
| `captcha` | string | Base64-encoded captcha image (JPEG format) |

**reCAPTCHA (`CUSTOM_ANTIBOT_RECAPTCHA_PAGE`):**

| Variable            | Type    | Description                                       |
| ------------------- | ------- | ------------------------------------------------- |
| `recaptcha_sitekey` | string  | Your reCAPTCHA site key                           |
| `recaptcha_classic` | boolean | `true` if using classic reCAPTCHA, `false` for v3 |

**hCaptcha (`CUSTOM_ANTIBOT_HCAPTCHA_PAGE`):**

| Variable           | Type   | Description            |
| ------------------ | ------ | ---------------------- |
| `hcaptcha_sitekey` | string | Your hCaptcha site key |

**Turnstile (`CUSTOM_ANTIBOT_TURNSTILE_PAGE`):**

| Variable            | Type   | Description                        |
| ------------------- | ------ | ---------------------------------- |
| `turnstile_sitekey` | string | Your Cloudflare Turnstile site key |

**mCaptcha (`CUSTOM_ANTIBOT_MCAPTCHA_PAGE`):**

| Variable           | Type   | Description            |
| ------------------ | ------ | ---------------------- |
| `mcaptcha_sitekey` | string | Your mCaptcha site key |
| `mcaptcha_url`     | string | Your mCaptcha URL      |

### Template Syntax

Templates use Lua template syntax with the following delimiters:

- `{{ variable }}` – Output a variable (HTML-escaped)
- `{* variable *}` – Output a variable (raw, unescaped)
- `{% lua_code %}` – Execute Lua code (conditionals, loops, etc.)
- `{-raw-}` ... `{-raw-}` – Raw block (no processing)

**Important**: Always use nonce attributes for inline scripts and styles to comply with Content Security Policy (CSP):

```html
<style nonce="{*nonce_style*}">
  /* Your CSS here */
</style>
<script nonce="{*nonce_script*}">
  // Your JavaScript here
</script>
```

### Examples

=== "Custom Error Page"

    Create a custom error page template at `/etc/bunkerweb/templates/error.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>{{ title }}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f5f5f5;
            color: #333;
          }
          .container {
            text-align: center;
            padding: 2rem;
          }
          .error-code {
            font-size: 6rem;
            font-weight: bold;
            color: {% if error_type == "server" %}#dc3545{% else %}#ffc107{% end %};
            margin: 0;
          }
          .error-title {
            font-size: 1.5rem;
            margin: 1rem 0;
          }
          .error-text {
            color: #666;
            margin-bottom: 1rem;
          }
          .request-info {
            font-size: 0.8rem;
            color: #999;
            margin-top: 2rem;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <p class="error-code">{{ error_code }}</p>
          <h1 class="error-title">{{ error_title }}</h1>
          <p class="error-text">{{ error_text }}</p>
          <p class="error-text">{{ error_solution }}</p>
          <div class="request-info">
            {% if request_id %}
            <p>Request ID: <code>{{ request_id }}</code></p>
            {% end %}
            {% if request_time %}
            <p>Time: {{ request_time }}</p>
            {% end %}
          </div>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Custom Captcha Page"

    Create a custom captcha challenge page at `/etc/bunkerweb/templates/captcha.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Security Check</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          }
          .card {
            background: white;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 400px;
          }
          h1 {
            color: #333;
            margin-bottom: 1rem;
          }
          .captcha-img {
            margin: 1rem 0;
            border-radius: 0.5rem;
          }
          input[type="text"] {
            width: 100%;
            padding: 0.75rem;
            font-size: 1.2rem;
            border: 2px solid #ddd;
            border-radius: 0.5rem;
            text-align: center;
            box-sizing: border-box;
          }
          button {
            margin-top: 1rem;
            padding: 0.75rem 2rem;
            font-size: 1rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
          }
          button:hover {
            background: #5a6fd6;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="card">
          <h1>🔒 Security Check</h1>
          <p>Please enter the text you see below to continue.</p>
          {-raw-}
          <form method="POST" action="{*antibot_uri*}">
            <img class="captcha-img" src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
            {-raw-}
            <input type="text" name="captcha" placeholder="Enter the code" required autocomplete="off" />
            <button type="submit">Verify</button>
          </form>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Custom Default Server Page"

    Create a custom default server page at `/etc/bunkerweb/templates/default.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Welcome</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #1a1a2e;
            color: #eee;
          }
          .container {
            text-align: center;
          }
          h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
          }
          p {
            color: #888;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <h1>🛡️ Protected by BunkerWeb</h1>
          <p>This server is secure and ready.</p>
        </div>
      </body>
    </html>
    {-raw-}
    ```

### Deployment Examples

=== "Linux"

    1. Create your template files in a directory of your choice (e.g., `/opt/bunkerweb/templates/`):

        ```bash
        sudo mkdir -p /opt/bunkerweb/templates
        sudo nano /opt/bunkerweb/templates/error.html
        # Paste your custom error page template
        ```

    2. Configure BunkerWeb by editing `/etc/bunkerweb/variables.env`:

        ```conf
        # Custom error page for all services (or use per-service with prefix)
        CUSTOM_ERROR_PAGE=/opt/bunkerweb/templates/error.html

        # Custom default server page (global only)
        CUSTOM_DEFAULT_SERVER_PAGE=/opt/bunkerweb/templates/default.html

        # Custom captcha page (per-service or global)
        CUSTOM_ANTIBOT_CAPTCHA_PAGE=/opt/bunkerweb/templates/captcha.html
        ```

    3. Reload BunkerWeb:

        ```bash
        sudo systemctl reload bunkerweb
        ```

=== "Docker"

    The **scheduler** is responsible for reading, validating, and caching your custom templates. Only the scheduler needs access to the template files—BunkerWeb receives the validated configuration automatically.

    1. Create your template files in a local directory (e.g., `./templates/`) and set the correct permissions:

        ```bash
        mkdir templates && \
        chown root:101 templates && \
        chmod 770 templates
        ```

        !!! info "Why UID/GID 101?"
            The scheduler container runs as an **unprivileged user with UID 101 and GID 101**. The directory must be readable by this user for the scheduler to access your templates.

        If the folder already exists:

        ```bash
        chown -R root:101 templates && \
        chmod -R 770 templates
        ```

        When using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [Podman](https://podman.io/), container UIDs/GIDs are remapped. Check your subuid/subgid ranges:

        ```bash
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        For example, if the range starts at **100000**, the effective GID becomes **100100** (100000 + 100):

        ```bash
        mkdir templates && \
        sudo chgrp 100100 templates && \
        chmod 770 templates
        ```

    2. Mount the templates directory to the **scheduler** and configure the settings on the scheduler (the scheduler acts as the manager and distributes the configuration to BunkerWeb workers). You can mount the templates to any path inside the container:

        ```yaml
        services:
          bunkerweb:
            image: bunkerity/bunkerweb:1.6.8-rc3
            # ... other settings (no environment variables needed here for custom pages)

          bw-scheduler:
            image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
            volumes:
              - ./templates:/custom_templates:ro
            environment:
              - CUSTOM_ERROR_PAGE=/custom_templates/error.html
              - CUSTOM_DEFAULT_SERVER_PAGE=/custom_templates/default.html
              - CUSTOM_ANTIBOT_CAPTCHA_PAGE=/custom_templates/captcha.html
              # ... other settings
        ```

    !!! warning "Scheduler Access Required"
        If the scheduler cannot read the template files (due to missing mount or incorrect permissions), the templates will be silently ignored and the default pages will be used instead. Check the scheduler logs for validation errors.

=== "Kubernetes"

    The **scheduler** is responsible for reading, validating, and caching your custom templates. You need to mount the templates to the scheduler pod.

    1. Create a ConfigMap with your templates:

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: bunkerweb-custom-templates
        data:
          error.html: |
            {-raw-}<!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <title>{{ title }}</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                  .error-code { font-size: 4rem; color: #dc3545; }
                </style>
                {-raw-}
              </head>
              <body>
                <p class="error-code">{{ error_code }}</p>
                <h1>{{ error_title }}</h1>
                <p>{{ error_text }}</p>
              </body>
            </html>
            {-raw-}
          captcha.html: |
            {-raw-}<!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <title>Security Check</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                </style>
                {-raw-}
              </head>
              <body>
                <h1>Please verify you are human</h1>
                {-raw-}
                <form method="POST" action="{*antibot_uri*}">
                  <img src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
                  {-raw-}
                  <input type="text" name="captcha" placeholder="Enter the code" required />
                  <button type="submit">Verify</button>
                </form>
              </body>
            </html>
            {-raw-}
        ```

    2. Mount the templates ConfigMap to the **scheduler** pod and configure the settings as environment variables:

        ```yaml
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: bunkerweb-scheduler
        spec:
          template:
            spec:
              containers:
                - name: bunkerweb-scheduler
                  image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
                  env:
                    - name: CUSTOM_ERROR_PAGE
                      value: "/custom_templates/error.html"
                    - name: CUSTOM_ANTIBOT_CAPTCHA_PAGE
                      value: "/custom_templates/captcha.html"
                    # ... other settings
                  volumeMounts:
                    - name: custom-templates
                      mountPath: /custom_templates
                      readOnly: true
                  # ... other container settings
              volumes:
                - name: custom-templates
                  configMap:
                    name: bunkerweb-custom-templates
              # ... other pod settings
        ```

    !!! tip "Using the BunkerWeb Ingress Controller"
        If you are using the BunkerWeb Ingress Controller, the scheduler is embedded in the controller. Mount the ConfigMap to the controller pod instead.

### Notes and Troubleshooting

- **Paths must be absolute** and end with a filename; blank values disable the corresponding custom page and remove its cache.
- **If validation fails** (bad HTML or unbalanced Lua tags), the template is skipped and the default page stays active. Check the scheduler logs for details.
- **Cached files** live in `/var/cache/bunkerweb/custom_pages`; updating the source file is enough—the job detects the new hash and reloads NGINX automatically.
- **CSP compliance**: Always use the `nonce_script` and `nonce_style` variables for inline scripts and styles to ensure proper Content Security Policy handling.
- **Testing templates**: You can test your templates locally by rendering them with a Lua template engine before deploying to BunkerWeb.

## OpenID Connect <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/0e4lcXTIIfs" title="OpenID Connect" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

The **OpenID Connect** plugin (PRO) adds Single Sign-On (SSO) in front of your application using the standard OAuth 2.0 / OIDC **Authorization Code** flow.

It runs inside BunkerWeb (NGINX/Lua) and enforces authentication during the **access phase**, so unauthenticated requests are stopped *before* they reach your upstream.

### How the request flow works

When a browser requests a protected URL:

1. If there is no valid session, BunkerWeb redirects the user to the Identity Provider (IdP).
2. The IdP authenticates the user and redirects back to BunkerWeb on `OPENIDC_REDIRECT_URI` (default: `/callback`) with an authorization code.
3. BunkerWeb exchanges the code for tokens at the IdP token endpoint.
4. Tokens are validated (issuer, audience, expiry, `iat` with slack, and signature using JWKS).
5. A session is created and the browser is redirected back to the original URL.

```mermaid
sequenceDiagram
  participant B as Browser
  participant BW as BunkerWeb (OpenIDC)
  participant IdP as Identity Provider
  participant Up as Upstream

  B->>BW: GET /protected
  alt Not authenticated
    BW-->>B: 302 Redirect to IdP authorize endpoint
    B->>IdP: Authorization request (nonce/PKCE optional)
    IdP-->>B: 302 Redirect to /callback?code=...
    B->>BW: GET /callback?code=...
    BW->>IdP: Token request (code exchange)
    IdP-->>BW: ID token + access token (+ refresh token)
    BW-->>B: 302 Redirect back to original URL
  end
  B->>BW: GET /protected (authenticated)
  BW->>Up: Forward request (+ optional identity header)
  Up-->>BW: Response
  BW-->>B: Response
```

!!! warning "Callback URL must match the IdP client configuration"
    Register the full callback URL on the IdP side (scheme + host + path). For example with default settings: `https://app.example.com/callback`.

### Settings (explained)

!!! info "Required settings"
    At minimum, `OPENIDC_DISCOVERY` and `OPENIDC_CLIENT_ID` must be set for the plugin to operate.

#### Core enablement

- `USE_OPENIDC` (default: `no`): enable or disable OpenID Connect authentication for the site.

#### Identity Provider (IdP) + client registration

- `OPENIDC_DISCOVERY`: discovery URL (e.g. `https://idp.example.com/.well-known/openid-configuration`).
- `OPENIDC_CLIENT_ID`: OAuth 2.0 client identifier registered with the IdP.
- `OPENIDC_CLIENT_SECRET`: OAuth 2.0 client secret (used by `basic`, `post`, and `secret_jwt`).

#### Callback / redirect

- `OPENIDC_REDIRECT_URI` (default: `/callback`): callback path used by the IdP after authentication (must be registered on the IdP).

#### Scopes and authorization parameters

- `OPENIDC_SCOPE` (default: `openid email profile`): space-separated list of scopes to request.
- `OPENIDC_AUTHORIZATION_PARAMS`: extra authorization parameters as comma-separated `key=value` pairs.

#### Security hardening

- `OPENIDC_USE_NONCE` (default: `yes`): add a nonce to authorization requests.
- `OPENIDC_USE_PKCE` (default: `no`): enable PKCE for the Authorization Code flow.
- `OPENIDC_IAT_SLACK` (default: `120`): allowed clock skew in seconds for token validation.
- `OPENIDC_ACCEPT_UNSUPPORTED_ALG` (default: `no`): accept tokens with unsupported algorithms (not recommended).
- `OPENIDC_FORCE_REAUTHORIZE` (default: `no`): force re-authorization on every request (debug-only).

#### Session/token lifecycle

- `OPENIDC_REFRESH_SESSION_INTERVAL`: interval in seconds to silently re-authenticate/refresh the session (empty disables).
- `OPENIDC_ACCESS_TOKEN_EXPIRES_IN` (default: `3600`): default access token lifetime if not provided by the IdP.
- `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY` (default: `yes`): renew access token using refresh token when expired.

#### Token endpoint authentication settings

- `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD` (default: `basic`): `basic`, `post`, `secret_jwt`, `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY`: required when using `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`: optional `kid` for `private_key_jwt`.
- `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN`: JWT assertion lifetime in seconds.

#### Logout behavior

- `OPENIDC_LOGOUT_PATH` (default: `/logout`): local logout path handled by BunkerWeb.
- `OPENIDC_REVOKE_TOKENS_ON_LOGOUT` (default: `no`): revoke tokens at the IdP during logout.
- `OPENIDC_REDIRECT_AFTER_LOGOUT_URI`: redirect after local logout (empty uses IdP default behavior).
- `OPENIDC_POST_LOGOUT_REDIRECT_URI`: redirect after IdP logout completes (if supported).

#### Connectivity and TLS to the IdP

- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` (default: `10000` ms each): timeouts for IdP HTTP calls.
- `OPENIDC_SSL_VERIFY` (default: `yes`): verify IdP TLS certificates.
- `OPENIDC_KEEPALIVE` (default: `yes`): keepalive for IdP connections.
- `OPENIDC_HTTP_PROXY` / `OPENIDC_HTTPS_PROXY`: proxies for IdP calls.

#### Forwarding identity to upstreams

- `OPENIDC_USER_HEADER` (default: `X-User`): header used to pass identity to the upstream (empty disables).
- `OPENIDC_USER_HEADER_CLAIM` (default: `sub`): claim to extract for the user header value.
- `OPENIDC_DISPLAY_CLAIM` (default: `preferred_username`): claim used for display in logs/metrics.

#### Caching

- `OPENIDC_DISCOVERY_DICT_SIZE` (default: `1m`): shared dict size for discovery cache.
- `OPENIDC_JWKS_DICT_SIZE` (default: `1m`): shared dict size for JWKS cache.

!!! tip "Redis session storage"
    When `USE_REDIS=yes` is configured globally in BunkerWeb, the OpenIDC plugin stores sessions in Redis instead of cookies (with automatic fallback to cookies if Redis becomes unavailable). This is the recommended mode for multi-instance / HA deployments.

### Discovery + JWKS caching

The plugin uses `OPENIDC_DISCOVERY` (the IdP `.well-known/openid-configuration` URL) to discover endpoints, then fetches and caches JWKS keys to validate token signatures.

Discovery and JWKS data are cached in NGINX shared dictionaries. If you have many tenants/IdPs or large key sets, increase:

- `OPENIDC_DISCOVERY_DICT_SIZE` (global)
- `OPENIDC_JWKS_DICT_SIZE` (global)

### Sessions (cookies vs Redis)

By default, sessions are stored as secure cookies managed by the OpenID Connect library.

If `USE_REDIS=yes` is enabled globally in BunkerWeb and Redis is configured, the plugin automatically switches to **Redis-backed sessions** (with automatic fallback to cookie sessions if Redis is temporarily unavailable). This is recommended for load-balanced / HA deployments and avoids cookie size limits when token payloads are large.

### Forwarding user identity to the upstream

If `OPENIDC_USER_HEADER` is set (default: `X-User`), the plugin injects a header value extracted from a claim (default: `OPENIDC_USER_HEADER_CLAIM=sub`).

Important security behavior:

- The plugin **clears any incoming** header matching `OPENIDC_USER_HEADER` to prevent client-side spoofing.
- If the configured claim is missing, the header is not set.
- Set `OPENIDC_USER_HEADER` to an empty value to disable identity forwarding.

!!! tip "Choosing a claim"
    Prefer stable identifiers that are present in tokens (e.g. `sub`, `email`, `preferred_username`). Claims are read from the ID token first, then from userinfo if present.

### Logout

Logout requests are handled on `OPENIDC_LOGOUT_PATH` (default: `/logout`).

- To revoke tokens at the IdP during logout, set `OPENIDC_REVOKE_TOKENS_ON_LOGOUT=yes`.
- Use `OPENIDC_REDIRECT_AFTER_LOGOUT_URI` and `OPENIDC_POST_LOGOUT_REDIRECT_URI` to control browser redirects after logout.

### Token endpoint authentication

Most IdPs work with the default `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD=basic` (client secret in HTTP Basic auth). Advanced methods are also supported:

- `post`
- `secret_jwt`
- `private_key_jwt` (requires `OPENIDC_CLIENT_RSA_PRIVATE_KEY`, optional `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`)

### Minimal configuration examples

Minimum required settings per protected service:

- `USE_OPENIDC=yes`
- `OPENIDC_DISCOVERY=...`
- `OPENIDC_CLIENT_ID=...`
- `OPENIDC_CLIENT_SECRET=...` (or a JWT key configuration for `private_key_jwt`)

Common hardening/tuning options:

- `OPENIDC_USE_NONCE=yes` (default)
- `OPENIDC_USE_PKCE=yes`
- `OPENIDC_IAT_SLACK=...` if you have clock skew
- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` to match IdP latency
- `OPENIDC_SSL_VERIFY=yes` (default)

### Troubleshooting

- **403 with "Authentication failed"**: most commonly a wrong discovery URL, a callback URL mismatch on the IdP side, or the IdP being unreachable.
- **Clock skew / "token not yet valid"**: ensure NTP is enabled; tune `OPENIDC_IAT_SLACK` if needed.
- **No user header injected**: verify the claim name in `OPENIDC_USER_HEADER_CLAIM` exists in the ID token/userinfo.
- **Multi-instance deployments**: enable `USE_REDIS=yes` and configure `REDIS_HOST` (or Sentinel) so sessions are shared.
