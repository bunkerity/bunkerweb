# 高级用法

GitHub 仓库的 [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/examples) 文件夹中提供了许多真实世界的用例示例。

我们还提供了许多样板文件，例如用于各种集成和数据库类型的 YAML 文件。这些都可以在 [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) 文件夹中找到。

本节仅关注高级用法和安全调整，请参阅文档的[功能部分](features.md)以查看所有可用的设置。

!!! tip "测试"
    当启用多站点模式时（并且如果您没有为域设置正确的 DNS 条目），要执行快速测试，您可以使用 curl 并带上您选择的 HTTP 主机头：
    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```

    如果您使用 HTTPS，您将需要处理 SNI：
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

## 在负载均衡器或反向代理之后 {#behind-load-balancer-or-reverse-proxy}

!!! info "真实 IP"

    当 BunkerWeb 本身位于负载均衡器或反向代理之后时，您需要对其进行配置，以便它可以获取客户端的真实 IP 地址。**如果您不这样做，安全功能将阻止负载均衡器或反向代理的 IP 地址，而不是客户端的 IP 地址**。

BunkerWeb 实际上支持两种方法来检索客户端的真实 IP 地址：

- 使用 `PROXY 协议`
- 使用像 `X-Forwarded-For` 这样的 HTTP 头

可以使用以下设置：

- `USE_REAL_IP`：启用/禁用真实 IP 检索
- `USE_PROXY_PROTOCOL`：启用/禁用 PROXY 协议支持。
- `REAL_IP_FROM`：允许向我们发送“真实 IP”的受信任 IP/网络地址列表
- `REAL_IP_HEADER`：包含真实 IP 的 HTTP 头或在使用 PROXY 协议时的特殊值 `proxy_protocol`

您将在文档的[功能部分](features.md#real-ip)找到更多关于真实 IP 的设置。

=== "HTTP 头"

    我们将对负载均衡器或反向代理做出以下假设（您需要根据您的配置更新设置）：

    - 它们使用 `X-Forwarded-For` 头来设置真实 IP
    - 它们的 IP 位于 `1.2.3.0/24` 和 `100.64.0.0/10` 网络中

    === "Web UI"

        导航到**全局设置**页面，选择 **Real IP** 插件并填写以下设置：

        <figure markdown>![使用 Web UI 的真实 IP 设置（HTTP 头）](assets/img/advanced-proxy1.png){ align=center }<figcaption>使用 Web UI 的真实 IP 设置（HTTP 头）</figcaption></figure>

        请注意，当您更改与真实 IP 相关的设置时，建议重新启动 BunkerWeb。

    === "Linux"

        您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        请注意，在配置与真实 IP 相关的设置时，建议执行重启而不是重新加载：

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        在运行 All-in-one 容器时，您需要将设置添加到环境变量中：

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
            bunkerity/bunkerweb-all-in-one:1.6.7-rc1
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker autoconf"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Kubernetes"

        您需要将设置添加到 BunkerWeb 和调度程序 Pod 的环境变量中。

        这是您可以使用的 `values.yaml` 文件的相应部分：

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

        !!! warning "已弃用"
            Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

            **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

        您需要将设置添加到 BunkerWeb 和调度程序服务的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        请注意，如果您的服务已经创建，您需要删除并重新创建它，以便更新新的环境变量。

=== "Proxy protocol"

    !!! warning "请仔细阅读"

        只有在您确定您的负载均衡器或反向代理正在发送 PROXY 协议时才使用它。**如果您启用它而未使用，将会出现错误**。

    我们将对负载均衡器或反向代理做出以下假设（您需要根据您的配置更新设置）：

    - 它们使用 `PROXY 协议` v1 或 v2 来设置真实 IP
    - 它们的 IP 位于 `1.2.3.0/24` 和 `100.64.0.0/10` 网络中

    === "Web UI"

        导航到**全局设置**页面，选择 **Real IP** 插件并填写以下设置：

        <figure markdown>![使用 Web UI 的真实 IP 设置（PROXY 协议）](assets/img/advanced-proxy2.png){ align=center }<figcaption>使用 Web UI 的真实 IP 设置（PROXY 协议）</figcaption></figure>

        请注意，当您更改与真实 IP 相关的设置时，建议重新启动 BunkerWeb。

    === "Linux"

        您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        请注意，在配置与代理协议相关的设置时，建议执行重启而不是重新加载：

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        在运行 All-in-one 容器时，您需要将设置添加到环境变量中：

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
            bunkerity/bunkerweb-all-in-one:1.6.7-rc1
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker autoconf"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Kubernetes"

        您需要将设置添加到 BunkerWeb 和调度程序 Pod 的环境变量中。

        这是您可以使用的 `values.yaml` 文件的相应部分：

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

        !!! warning "已弃用"
            Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

            **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

        您需要将设置添加到 BunkerWeb 和调度程序服务的环境变量中。

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        请注意，如果您的服务已经创建，您需要删除并重新创建它，以便更新新的环境变量。

## 高可用性和负载均衡

为了确保即使某台服务器宕机，您的应用依然可用，可以将 BunkerWeb 部署成一个 **HA 集群**。该架构包含一个负责编排配置的 **Manager**（Scheduler）以及多个处理流量的 **Worker**（BunkerWeb 实例）。

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
  Client["客户端"]:::client
  LB["负载均衡器"]:::lb

  %% ============== Cluster ==================
  subgraph CLUSTER[" "]
    direction TB

    %% ---- Top row: Manager + Redis ----
    subgraph TOP["Manager 与数据存储"]
      direction LR
      Manager["Manager<br/>(Scheduler)"]:::manager
      BDD["数据库"]:::database
      Redis["Redis/Valkey"]:::datastore
      UI["Web 界面"]:::manager
    end

    %% ---- Middle: Workers ----
    subgraph WORKERS["Workers (BunkerWeb)"]
      direction TB
      Worker1["Worker 1"]:::component
      WorkerN["Worker N"]:::component
    end

    %% ---- Bottom: App ----
    App["应用"]:::backend
  end

  %% ============ Outside right ============
  Admin["管理员"]:::client

  %% ============ Traffic & control ===========
  %% Manager / control plane
  Manager -->|API 5000| Worker1
  Manager -->|API 5000| WorkerN
  Manager -->|bwcli| Redis
  Manager -->|配置| BDD

  %% User interface (UI)
  UI -->|配置| BDD
  UI -->|报告 / 封禁| Redis
  BDD --- UI
  Redis --- UI
  linkStyle 6 stroke-width:0px;
  linkStyle 7 stroke-width:0px;

  %% Workers <-> Redis
  Worker1 -->|共享缓存| Redis
  WorkerN -->|共享缓存| Redis

  %% Workers -> App
  Worker1 -->|合法流量| App
  WorkerN -->|合法流量| App

  %% Client (right side) -> Load balancer -> Workers -> App
  Client -->|请求| LB
  LB -->|HTTP/TCP| Worker1
  LB -->|HTTP/TCP| WorkerN

  %% Admin -> UI
  UI --- Admin
  Admin -->|HTTP| UI
  linkStyle 15 stroke-width:0px;
```

!!! info "理解 BunkerWeb 的 API"
    BunkerWeb 有两个不同的 API 概念：

    - **内部 API**：自动连接 Manager 与 Worker 以完成编排。始终启用，无需手动配置。
    - 可选的 **API 服务**（`bunkerweb-api`）：为自动化工具（bwcli、CI/CD 等）提供公开的 REST 接口。Linux 安装默认禁用，与内部 Manager↔Worker 通信无关。

### 前提条件

在搭建集群前，请确保：

- **至少 2 台 Linux 主机**，可使用 root/sudo。
- 主机之间 **网络互通**（尤其是内部 API 的 TCP 5000 端口）。
- 需要保护的 **应用 IP 或主机名**。
- *(可选)* **负载均衡器**（例如 HAProxy）用于在 Worker 之间分发流量。

### 1. 安装 Manager

Manager 是集群的大脑，运行 Scheduler、数据库以及可选的 Web 界面。

!!! warning "Web 界面的安全性"
    Web 界面监听专用端口（默认 7000），应仅供管理员访问。如果要暴露到互联网，**强烈建议** 在前面加一层 BunkerWeb 进行保护。

=== "Linux"

    1. **在 Manager 主机下载并运行安装脚本**：

        ```bash
        # 下载脚本及校验文件
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.7-rc1/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.7-rc1/install-bunkerweb.sh.sha256

        # 校验完整性
        sha256sum -c install-bunkerweb.sh.sha256

        # 运行安装器
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "安全提示"
            在执行脚本前务必通过提供的校验值验证其完整性。

    2. **选择 2) Manager** 并按提示操作：

        | 提示                    | 操作                                                                      |
        | :---------------------- | :------------------------------------------------------------------------ |
        | **BunkerWeb 实例**      | 输入 Worker 节点 IP，空格分隔（例如 `192.168.10.11 192.168.10.12`）。     |
        | **Whitelist IP**        | 接受检测到的 IP，或输入网段（例如 `192.168.10.0/24`）以允许访问内部 API。 |
        | **DNS 解析器**          | 按 `N` 使用默认值，或指定自定义解析器。                                   |
        | **内部 API 启用 HTTPS** | **推荐：** 选择 `Y` 生成证书，保护 Manager-Worker 通信。                  |
        | **Web UI 服务**         | 选择 `Y` 启用界面（强烈推荐）。                                           |
        | **API 服务**            | 除非需要公共 REST API，否则选择 `N`。                                     |

    #### 保护并暴露 UI

    如果启用了 Web UI，需要妥善保护。可以部署在 Manager 上或单独的机器上。

    === "部署在 Manager 上"

        1. 编辑 `/etc/bunkerweb/ui.env`，设置强密码：

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

        !!! warning "修改默认凭据"
            在生产环境启动 UI 前，将 `admin` 和 `changeme` 替换为强凭据。

        2. 重启 UI：

        ```bash
        sudo systemctl restart bunkerweb-ui
        ```

    === "独立主机"

        为了更好的隔离，可在单独节点安装 UI。

        1. 运行安装器并选择 **5) Web UI Only**。
        2. 编辑 `/etc/bunkerweb/ui.env` 指向 Manager 的数据库：

            ```ini
            # 数据库配置（需与 Manager 数据库一致）
            DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb
            # PostgreSQL: postgresql://bunkerweb:changeme@db-host:5432/bunkerweb
            # MySQL: mysql+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb

            # Redis 配置（若使用 Redis/Valkey 持久化）
            # 若未提供，将自动从数据库中获取
            # REDIS_HOST=redis-host

            # 安全凭据
            ADMIN_USERNAME=admin
            ADMIN_PASSWORD=changeme

            # 网络设置
            LISTEN_ADDR=0.0.0.0
            # LISTEN_PORT=7000
            ```

        3. 重启服务：

            ```bash
            sudo systemctl restart bunkerweb-ui
            ```

        !!! tip "防火墙设置"
            确保 UI 主机可以访问数据库和 Redis 端口。可能需要在 UI 主机以及数据库/Redis 主机上调整防火墙规则。

=== "Docker"

    在 Manager 主机创建 `docker-compose.yml`：

    ```yaml title="docker-compose.yml"
    x-ui-env: &bw-ui-env
      # 通过锚点避免重复环境变量
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 请使用更强的数据库密码

    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "192.168.1.11 192.168.1.12" # 替换为 Worker IP
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16" # 允许本地网段
          # API_LISTEN_HTTPS: "yes" # 推荐启用 HTTPS 保护内部 API
          # API_TOKEN: "my_secure_token" # 可选：额外的 Token
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # 持久化缓存和备份
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.7-rc1
        ports:
          - "7000:7000" # 暴露 UI 端口
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # 请使用更强密码
          TOTP_ENCRYPTION_KEYS: "mysecret" # 请使用更强密钥（见前提条件）
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-db:
        image: mariadb:11
        # 设置更大的 max_allowed_packet 以避免大查询问题
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # 请使用更强密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis 用于报告/封禁/统计的持久化
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

    启动 Manager 组合：

    ```bash
    docker compose up -d
    ```

### 2. 安装 Worker

Worker 负责处理进入的流量。

=== "Linux"

    1. **在每个 Worker 节点运行安装器**（与 Manager 相同的命令）。
    2. **选择 3) Worker** 并配置：

        | 提示                    | 操作                                      |
        | :---------------------- | :---------------------------------------- |
        | **Manager IP**          | 输入 Manager IP（例如 `192.168.10.10`）。 |
        | **内部 API 启用 HTTPS** | 必须与 Manager 保持一致（`Y` 或 `N`）。   |

    Worker 会自动向 Manager 注册。

=== "Docker"

    在每个 Worker 主机创建 `docker-compose.yml`：

    ```yaml title="docker-compose.yml"
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 支持 QUIC / HTTP3
          - "5000:5000/tcp" # 内部 API 端口
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
          # API_LISTEN_HTTPS: "yes" # 推荐开启（需与 Manager 一致）
          # API_TOKEN: "my_secure_token" # 可选：额外 Token（需与 Manager 一致）
        restart: "unless-stopped"
    ```

    启动 Worker：

    ```bash
    docker compose up -d
    ```

### 3. 管理 Worker

可以通过 Web UI 或 CLI 随时添加更多 Worker。

=== "通过 Web UI"

    1. 打开 **Instances** 选项卡。
    2. 点击 **Add instance**。
    3. 输入 Worker 的 IP/主机名并保存。

    <div class="grid grid-2" markdown style="display:grid; align-items:center;">
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - 创建实例](assets/img/ui-ha-create-instance.webp){ width="100%" }
      <figcaption>BunkerWeb UI - 创建实例</figcaption>
    </figure>
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - 创建实例表单](assets/img/ui-ha-create-instance-form.webp){ width="100%" }
      <figcaption>BunkerWeb UI - 创建实例表单</figcaption>
    </figure>
    </div>

=== "通过配置"

    === "Linux"

        1. 在 Manager 上修改 `/etc/bunkerweb/variables.env`：

            ```bash
            BUNKERWEB_INSTANCES=192.168.10.11 192.168.10.12 192.168.10.13
            ```

        2. 重启 Scheduler：

            ```bash
            sudo systemctl restart bunkerweb-scheduler
            ```

    === "Docker"

        1. 编辑 Manager 上的 `docker-compose.yml` 更新 `BUNKERWEB_INSTANCES`。

        2. 重新创建 Scheduler 容器：

            ```bash
            docker compose up -d bw-scheduler
            ```

### 4. 验证部署

=== "Linux"

    1. **检查状态**：登录 UI（`http://<manager-ip>:7000`）并打开 **Instances** 选项卡，所有 Worker 应显示 **Up**。
    2. **测试故障转移**：停止某个 Worker 上的 BunkerWeb（`sudo systemctl stop bunkerweb`），确认流量仍然可达。

=== "Docker"

    1. **检查状态**：登录 UI（`http://<manager-ip>:7000`）并打开 **Instances** 选项卡，所有 Worker 应显示 **Up**。
    2. **测试故障转移**：停止某个 Worker 上的 BunkerWeb（`docker compose stop bunkerweb`），确认流量仍然可达。

### 5. 负载均衡

要在 Worker 之间分发流量，使用负载均衡器。建议使用支持 **PROXY protocol** 的四层（TCP）负载均衡器以保留客户端 IP。

=== "HAProxy - 第 4 层 (TCP)"

    以下是一个 **HAProxy** TCP 模式示例，使用 **PROXY protocol** 传递客户端 IP。

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

=== "HAProxy - 第 7 层 (HTTP)"

    以下是一个 **HAProxy** 七层（HTTP）示例。它会添加 `X-Forwarded-For` 头，便于 BunkerWeb 获取客户端 IP。

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

保存配置后重载 HAProxy：

```bash
sudo systemctl restart haproxy
```

更多信息请参阅 [HAProxy 官方文档](http://docs.haproxy.org/)。

!!! tip "配置真实 IP"
    别忘了在 BunkerWeb 中启用真实客户端 IP（使用 PROXY protocol 或 X-Forwarded-For 头）。

    详见 [在负载均衡器或反向代理之后](#behind-load-balancer-or-reverse-proxy) 章节，确保获取到正确的客户端 IP。

    在每个 Worker 上查看 `/var/log/bunkerweb/access.log`，确认请求来自 PROXY protocol 网段，且多个 Worker 分担流量。此时 BunkerWeb 集群即可以高可用方式保护生产业务。

## 使用自定义 DNS 解析机制

BunkerWeb 的 NGINX 配置可以根据您的需求定制，以使用不同的 DNS 解析器。这在各种场景中特别有用：

1. 为了遵循您本地 `/etc/hosts` 文件中的条目
2. 当您需要为某些域使用自定义 DNS 服务器时
3. 为了与本地 DNS 缓存解决方案集成

### 使用 systemd-resolved

许多现代 Linux 系统使用 `systemd-resolved` 进行 DNS 解析。如果您希望 BunkerWeb 遵循您 `/etc/hosts` 文件的内容并使用系统的 DNS 解析机制，您可以将其配置为使用本地的 systemd-resolved DNS 服务。

要验证 systemd-resolved 是否在您的系统上运行，您可以使用：

```bash
systemctl status systemd-resolved
```

要在 BunkerWeb 中启用 systemd-resolved 作为您的 DNS 解析器，请将 `DNS_RESOLVERS` 设置为 `127.0.0.53`，这是 systemd-resolved 的默认监听地址：

=== "Web UI"

    导航到**全局设置**页面，并将 DNS 解析器设置为 `127.0.0.53`

    <figure markdown>![使用 Web UI 设置 DNS 解析器](assets/img/advanced-dns-resolvers.png){ align=center }<figcaption>使用 Web UI 设置 DNS 解析器</figcaption></figure>

=== "Linux"

    您需要修改 `/etc/bunkerweb/variables.env` 文件：

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    进行此更改后，重新加载调度程序以应用配置：

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

### 使用 dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) 是一个轻量级的 DNS、DHCP 和 TFTP 服务器，通常用于本地 DNS 缓存和定制。当您需要比 systemd-resolved 提供更多对 DNS 解析的控制时，它特别有用。

=== "Linux"

    首先，在您的 Linux 系统上安装和配置 dnsmasq：

    === "Debian/Ubuntu"

        ```bash
        # 安装 dnsmasq
        sudo apt-get update && sudo apt-get install dnsmasq

        # 配置 dnsmasq 仅在 localhost 上监听
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # 如果需要，添加自定义 DNS 条目
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # 重启 dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # 安装 dnsmasq
        sudo dnf install dnsmasq

        # 配置 dnsmasq 仅在 localhost 上监听
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # 如果需要，添加自定义 DNS 条目
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # 重启 dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    然后配置 BunkerWeb 使用 dnsmasq，方法是将 `DNS_RESOLVERS` 设置为 `127.0.0.1`：

    === "Web UI"

        导航到**全局设置**页面，选择 **NGINX** 插件并将 DNS 解析器设置为 `127.0.0.1`。

        <figure markdown>![使用 Web UI 设置 DNS 解析器](assets/img/advanced-dns-resolvers2.png){ align=center }<figcaption>使用 Web UI 设置 DNS 解析器</figcaption></figure>

    === "Linux"

        您需要修改 `/etc/bunkerweb/variables.env` 文件：

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        进行此更改后，重新加载调度程序：

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "All-in-one"

    当使用 All-in-one 容器时，在单独的容器中运行 dnsmasq 并配置 BunkerWeb 使用它：

    ```bash
    # 为 DNS 通信创建一个自定义网络
    docker network create bw-dns

    # 使用 dockurr/dnsmasq 运行 dnsmasq 容器，并使用 Quad9 DNS
    # Quad9 提供专注于安全的 DNS 解析，并带有恶意软件拦截功能
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

    # 运行 BunkerWeb All-in-one 并使用 dnsmasq DNS 解析器
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.7-rc1
    ```

=== "Docker"

    将 dnsmasq 服务添加到您的 docker-compose 文件中，并配置 BunkerWeb 使用它：

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # 使用 Quad9 DNS 服务器以增强安全性和隐私
          # 主服务器：9.9.9.9 (Quad9，带恶意软件拦截)
          # 备用服务器：149.112.112.112 (Quad9 备用服务器)
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
        image: bunkerity/bunkerweb:1.6.7-rc1
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...现有网络...
      bw-dns:
        name: bw-dns
    ```

## 自定义配置 {#custom-configurations}

要自定义并向 BunkerWeb 添加自定义配置，您可以利用其 NGINX 基础。自定义 NGINX 配置可以添加到不同的 NGINX 上下文中，包括 ModSecurity Web 应用程序防火墙 (WAF) 的配置，这是 BunkerWeb 的核心组件。有关 ModSecurity 配置的更多详细信息，请参见[此处](features.md#custom-configurations)。

以下是可用的自定义配置类型：

- **http**：NGINX 的 HTTP 级别的配置。
- **server-http**：NGINX 的 HTTP/服务器级别的配置。
- **default-server-http**：NGINX 的服务器级别的配置，特别用于当提供的客户端名称与 `SERVER_NAME` 中的任何服务器名称都不匹配时的“默认服务器”。
- **modsec-crs**：在加载 OWASP 核心规则集之前应用的配置。
- **modsec**：在加载 OWASP 核心规则集之后应用的配置，或在未加载核心规则集时使用。
- **crs-plugins-before**：CRS 插件的配置，在加载 CRS 插件之前应用。
- **crs-plugins-after**：CRS 插件的配置，在加载 CRS 插件之后应用。
- **stream**：NGINX 的 Stream 级别的配置。
- **server-stream**：NGINX 的 Stream/服务器级别的配置。

自定义配置可以全局应用，也可以针对特定服务器应用，具体取决于适用的上下文以及是否启用了[多站点模式](features.md#multisite-mode)。

应用自定义配置的方法取决于所使用的集成。然而，其底层过程涉及将带有 `.conf` 后缀的文件添加到特定文件夹中。要为特定服务器应用自定义配置，该文件应放置在以主服务器名称命名的子文件夹中。

某些集成提供了更方便的应用配置方式，例如在 Docker Swarm 中使用 [Configs](https://docs.docker.com/engine/swarm/configs/) 或在 Kubernetes 中使用 [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)。这些选项为管理和应用配置提供了更简单的方法。

=== "Web UI"

    导航到**配置**页面，点击**创建新的自定义配置**，然后您可以选择是全局设置还是特定于服务的配置，以及配置类型和配置名称：

    <figure markdown>![使用 Web UI 的自定义配置](assets/img/advanced-config.png){ align=center }<figcaption>使用 Web UI 的自定义配置</figcaption></figure>

    别忘了点击 `💾 保存` 按钮。

=== "Linux"

    当使用 [Linux 集成](integrations.md#linux)时，自定义配置必须写入 `/etc/bunkerweb/configs` 文件夹。

    这是一个 server-http/hello-world.conf 的示例：

    ```nginx
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    因为 BunkerWeb 以非特权用户 (nginx:nginx) 运行，您需要编辑权限：

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    现在让我们检查调度程序的状态：

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    如果它们已经在运行，我们可以重新加载它：

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "All-in-one"

    当使用 [All-in-one 镜像](integrations.md#all-in-one-aio-image)时，您有两种选择来添加自定义配置：

    - 在运行容器时使用特定的 `*_CUSTOM_CONF_*` 设置作为环境变量（推荐）。
    - 将 `.conf` 文件写入挂载到 `/data` 的卷内的 `/data/configs/` 目录。

    **使用设置（环境变量）**

    要使用的设置必须遵循 `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` 的模式：

    - `<SITE>`：可选的主服务器名称，如果启用了多站点模式并且配置必须应用于特定服务。
    - `<TYPE>`：配置的类型，可接受的值为 `HTTP`、`DEFAULT_SERVER_HTTP`、`SERVER_HTTP`、`MODSEC`、`MODSEC_CRS`、`CRS_PLUGINS_BEFORE`、`CRS_PLUGINS_AFTER`、`STREAM` 和 `SERVER_STREAM`。
    - `<NAME>`：不带 `.conf` 后缀的配置名称。

    这是一个在运行 All-in-one 容器时的示例：

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
        bunkerity/bunkerweb-all-in-one:1.6.7-rc1
    ```

    请注意，如果您的容器已经创建，您需要删除并重新创建它，以便应用新的环境变量。

    **使用文件**

    首先要做的是创建文件夹：

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    现在您可以编写您的配置了：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    因为调度程序以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    启动调度程序容器时，您需要将文件夹挂载到 /data 上：

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.7-rc1
    ```

=== "Docker"

    当使用 [Docker 集成](integrations.md#docker)时，您有两种选择来添加自定义配置：

    - 使用特定的 `*_CUSTOM_CONF_*` 设置作为环境变量（推荐）
    - 将 .conf 文件写入挂载在调度程序 /data 上的卷中

    **使用设置**

    要使用的设置必须遵循 `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` 的模式：

    - `<SITE>`：可选的主服务器名称，如果启用了多站点模式并且配置必须应用于特定服务
    - `<TYPE>`：配置的类型，可接受的值为 `HTTP`、`DEFAULT_SERVER_HTTP`、`SERVER_HTTP`、`MODSEC`、`MODSEC_CRS`、`CRS_PLUGINS_BEFORE`、`CRS_PLUGINS_AFTER`、`STREAM` 和 `SERVER_STREAM`
    - `<NAME>`：不带 .conf 后缀的配置名称

    这是一个使用 docker-compose 文件的示例：

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
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

    **使用文件**

    首先要做的是创建文件夹：

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    现在您可以编写您的配置了：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    因为调度程序以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    启动调度程序容器时，您需要将文件夹挂载到 /data 上：

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    当使用 [Docker autoconf 集成](integrations.md#docker-autoconf)时，您有两种选择来添加自定义配置：

    - 使用特定的 `*_CUSTOM_CONF_*` 设置作为标签（最简单）
    - 将 .conf 文件写入挂载在调度程序 /data 上的卷中

    **使用标签**

    !!! warning "使用标签的限制"
        当使用 Docker autoconf 集成的标签时，您只能为相应的 Web 服务应用自定义配置。应用 **http**、**default-server-http**、**stream** 或任何全局设置（例如所有服务的 **server-http** 或 **server-stream**）是不可能的：您需要为此挂载文件。

    要使用的标签必须遵循 `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` 的模式：

    - `<TYPE>`：配置的类型，可接受的值为 `SERVER_HTTP`、`MODSEC`、`MODSEC_CRS`、`CRS_PLUGINS_BEFORE`、`CRS_PLUGINS_AFTER` 和 `SERVER_STREAM`
    - `<NAME>`：不带 .conf 后缀的配置名称

    这是一个使用 docker-compose 文件的示例：

    ```yaml
    myapp:
      image: nginxdemos/nginx-hello
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

    **使用文件**

    首先要做的是创建文件夹：

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    现在您可以编写您的配置了：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    因为调度程序以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    启动调度程序容器时，您需要将文件夹挂载到 /data 上：

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    当使用 [Kubernetes 集成](integrations.md#kubernetes)时，
    自定义配置通过 [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) 管理。

    无需将 ConfigMap 挂载到 Pod（例如作为环境变量或卷）。
    Autoconf Pod 会监听 ConfigMap 事件并在检测到更改时立即更新配置。

    请为需要由 Ingress 控制器管理的 ConfigMap 添加以下注解：

    - `bunkerweb.io/CONFIG_TYPE`：必填。请选择受支持的类型（`http`、`server-http`、`default-server-http`、`modsec`,
      `modsec-crs`、`crs-plugins-before`、`crs-plugins-after`、`stream`、`server-stream` 或 `settings`）。
    - `bunkerweb.io/CONFIG_SITE`：可选。设置为主要服务器名称（在 `Ingress` 中声明）以仅作用于该服务；不设置则表示全局生效。

    这是一个示例：

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

    !!! info "同步方式"
        - Ingress 控制器会持续监听带注解的 ConfigMap。
        - 如果设置了 `NAMESPACES` 环境变量，则仅处理这些命名空间中的 ConfigMap。
        - 创建或更新受管 ConfigMap 会立即触发配置重新加载。
        - 删除 ConfigMap，或移除 `bunkerweb.io/CONFIG_TYPE` 注解，会清除对应的自定义配置。
        - 当指定 `bunkerweb.io/CONFIG_SITE` 时，引用的服务必须已经存在；否则该 ConfigMap 会被忽略，直到服务出现。

    !!! tip "自定义额外配置"
        自 `1.6.0` 版本起，您可以在 ConfigMap 上添加 `bunkerweb.io/CONFIG_TYPE=settings` 注解来新增或覆盖设置。
        autoconf 的 Ingress 控制器会读取 `data` 下的每个键值对，并像处理环境变量一样应用它们：

        - 未定义 `bunkerweb.io/CONFIG_SITE` 时，所有键都会全局生效。
        - 定义了 `bunkerweb.io/CONFIG_SITE` 时，控制器会自动为尚未限定的键添加 `<服务器名称>_` 前缀（其中所有 `/` 会被替换为 `_`）。如果需要在同一份 ConfigMap 中混合全局键和特定键，请自行添加该前缀。
        - 无效的键名或取值会被跳过，并在 autoconf 控制器日志中记录警告。

        示例：

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # 多站点设置，将应用于所有未覆盖它的服务
          USE_REDIS: "yes" # 全局设置，将全局应用
          ...
        ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    当使用 [Swarm 集成](integrations.md#swarm)时，自定义配置是使用 [Docker Configs](https://docs.docker.com/engine/swarm/configs/) 管理的。

    为了简单起见，您甚至不需要将配置附加到服务上：autoconf 服务正在监听配置事件，并会在需要时更新自定义配置。

    创建配置时，您需要添加特殊的标签：

    *   **bunkerweb.CONFIG_TYPE**：必须设置为有效的自定义配置类型（http、server-http、default-server-http、modsec、modsec-crs、crs-plugins-before、crs-plugins-after、stream、server-stream 或 settings）
    *   **bunkerweb.CONFIG_SITE**：设置为服务器名称以将配置应用于该特定服务器（可选，如果未设置则将全局应用）

    这是一个示例：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    没有更新机制：替代方法是使用 `docker config rm` 删除现有配置，然后重新创建它。

## 在生产环境中运行大量服务 {#running-many-services-in-production}

### 全局 CRS

!!! warning "CRS 插件"
    当 CRS 全局加载时，**不支持 CRS 插件**。如果您需要使用它们，则需要为每个服务加载 CRS。

如果您在生产环境中使用 BunkerWeb 并有大量服务，并且您全局启用了带有 CRS 规则的 **ModSecurity 功能**，那么加载 BunkerWeb 配置所需的时间可能会变得过长，从而可能导致超时。

解决方法是全局加载 CRS 规则，而不是按服务加载。出于向后兼容性的原因，此行为默认未启用，并且因为它有一个缺点：如果您启用全局 CRS 规则加载，**将不再可能按服务定义 modsec-crs 规则**（在 CRS 规则之前执行）。然而，这个限制可以通过编写如下所示的全局 `modsec-crs` 排除规则来绕过：

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

您可以通过将 `USE_MODSECURITY_GLOBAL_CRS` 设置为 `yes` 来启用全局 CRS 加载。

### 为 MariaDB/MySQL 调整 max_allowed_packet

在使用 BunkerWeb 并有大量服务时，MariaDB 和 MySQL 数据库服务器中 `max_allowed_packet` 参数的默认值似乎不足。

如果您遇到这样的错误，尤其是在调度程序上：

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

您需要在您的数据库服务器上增加 `max_allowed_packet` 的值。

## 封禁和报告的持久化 {#persistence-of-bans-and-reports}

默认情况下，BunkerWeb 将封禁和报告存储在本地的 Lua 数据存储中。虽然这种设置简单高效，但意味着当实例重启时数据会丢失。为了确保封禁和报告在重启后仍然存在，您可以将 BunkerWeb 配置为使用远程的 [Redis](https://redis.io/) 或 [Valkey](https://valkey.io/) 服务器。

**为什么使用 Redis/Valkey？**

Redis 和 Valkey 是功能强大的内存数据存储，通常用作数据库、缓存和消息代理。它们具有高度可扩展性，并支持多种数据结构，包括：

- **字符串**：基本的键值对。
- **哈希**：单个键内的字段-值对。
- **列表**：有序的字符串集合。
- **集合**：无序的唯一字符串集合。
- **有序集合**：带有分数的有序集合。

通过利用 Redis 或 Valkey，BunkerWeb 可以持久地存储封禁、报告和缓存数据，确保其持久性和可扩展性。

**启用 Redis/Valkey 支持**

要启用 Redis 或 Valkey 支持，请在您的 BunkerWeb 配置文件中配置以下设置：

```conf
# 启用 Redis/Valkey 支持
USE_REDIS=yes

# Redis/Valkey 服务器主机名或 IP 地址
REDIS_HOST=<hostname>

# Redis/Valkey 服务器端口号（默认：6379）
REDIS_PORT=6379

# Redis/Valkey 数据库编号（默认：0）
REDIS_DATABASE=0
```

- **`USE_REDIS`**：设置为 `yes` 以启用 Redis/Valkey 集成。
- **`REDIS_HOST`**：指定 Redis/Valkey 服务器的主机名或 IP 地址。
- **`REDIS_PORT`**：指定 Redis/Valkey 服务器的端口号。默认为 `6379`。
- **`REDIS_DATABASE`**：指定要使用的 Redis/Valkey 数据库编号。默认为 `0`。

如果您需要更高级的设置，例如身份验证、SSL/TLS 支持或 Sentinel 模式，请参阅 [Redis 插件设置文档](features.md#redis)以获取详细指导。

## 保护 UDP/TCP 应用程序

!!! example "实验性功能"

      此功能尚未准备好用于生产。欢迎您进行测试，并通过 GitHub 仓库中的 [issues](https://github.com/bunkerity/bunkerweb/issues) 向我们报告任何错误。

BunkerWeb 能够作为**通用的 UDP/TCP 反向代理**，让您可以保护任何至少在 OSI 模型第 4 层运行的网络应用程序。BunkerWeb 并未使用“传统”的 HTTP 模块，而是利用了 NGINX 的 [stream 模块](https://nginx.org/en/docs/stream/ngx_stream_core_module.html)。

需要注意的是，**在使用 stream 模块时，并非所有设置和安全功能都可用**。有关此方面的更多信息，可以在文档的[功能](features.md)部分找到。

配置一个基本的反向代理与 HTTP 设置非常相似，因为它涉及使用相同的设置：`USE_REVERSE_PROXY=yes` 和 `REVERSE_PROXY_HOST=myapp:9000`。即使当 BunkerWeb 位于负载均衡器之后时，设置也保持不变（由于显而易见的原因，支持的选项是**PROXY 协议**）。

除此之外，还使用了以下特定设置：

- `SERVER_TYPE=stream`：激活 `stream` 模式（通用 UDP/TCP）而不是 `http` 模式（默认）
- `LISTEN_STREAM_PORT=4242`：BunkerWeb 将监听的“普通”（无 SSL/TLS）端口
- `LISTEN_STREAM_PORT_SSL=4343`：BunkerWeb 将监听的“ssl/tls”端口
- `USE_UDP=no`：监听并转发 UDP 数据包而不是 TCP

有关 `stream` 模式的完整设置列表，请参阅文档的[功能](features.md)部分。

!!! tip "多个监听端口"

    自 `1.6.0` 版本起，BunkerWeb 支持 `stream` 模式的多个监听端口。您可以使用 `LISTEN_STREAM_PORT` 和 `LISTEN_STREAM_PORT_SSL` 设置来指定它们。

    这是一个示例：

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "All-in-one"

    在运行 All-in-one 容器时，您需要将设置添加到环境变量中。您还需要暴露流端口。

    此示例将 BunkerWeb 配置为代理两个基于流的应用程序 `app1.example.com` 和 `app2.example.com`。

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
        bunkerity/bunkerweb-all-in-one:1.6.7-rc1
    ```

    请注意，如果您的容器已经创建，您需要删除并重新创建它，以便应用新的环境变量。

    您的应用程序（`myapp1`, `myapp2`）应该在单独的容器中运行（或以其他方式可访问），并且它们的主机名/IP（例如，在 `_REVERSE_PROXY_HOST` 中使用的 `myapp1`, `myapp2`）必须可以从 `bunkerweb-aio` 容器解析和访问。这通常涉及将它们连接到共享的 Docker 网络。

    !!! note "停用 UI 服务"
        建议停用 UI 服务（例如，通过设置环境变量 `SERVICE_UI=no`），因为 Web UI 与 `SERVER_TYPE=stream` 不兼容。

=== "Docker"

    当使用 Docker 集成时，保护现有网络应用程序的最简单方法是将服务添加到 `bw-services` 网络中：

    ```yaml
    x-bw-api-env: &bw-api-env
      # 我们使用锚点来避免为所有服务重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
      # 可选的 API 令牌，用于经过身份验证的 API 调用
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          - "80:8080" # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
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
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 此设置是指定 BunkerWeb 实例所必需的
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # 将应用于所有服务
          SERVER_TYPE: "stream" # 将应用于所有服务
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
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

    在您的机器上运行 [Docker autoconf 集成](integrations.md#docker-autoconf)堆栈之前，您需要编辑端口：

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          - "80:8080" # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
          - "10000:10000" # app1
          - "20000:20000" # app2
    ...
    ```

    一旦堆栈运行，您可以将现有应用程序连接到 `bw-services` 网络，并使用标签配置 BunkerWeb：

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

    !!! example "实验性功能"

        目前，[Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) 不支持 `stream` 模式。**我们在这里所做的是一个使其工作的变通方法。**

        欢迎您进行测试，并通过 GitHub 仓库中的 [issues](https://github.com/bunkerity/bunkerweb/issues) 向我们报告任何错误。

    在您的机器上运行 [Kubernetes 集成](integrations.md#kubernetes)堆栈之前，您需要在您的负载均衡器上打开端口：

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
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

    一旦堆栈运行，您可以创建您的 ingress 资源：

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # 将应用于所有服务
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # 在 stream 模式下不使用，但必须填写
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # 在 stream 模式下不使用，但必须填写
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

    您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

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

    现在让我们检查调度程序的状态：

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    如果它们已经在运行，我们可以重新加载它：

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    在您的机器上运行 [Swarm 集成](integrations.md#swarm)堆栈之前，您需要编辑端口：

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
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

    一旦堆栈运行，您可以将现有应用程序连接到 `bw-services` 网络，并使用标签配置 BunkerWeb：

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

!!! example "实验性功能"
      目前，BunkerWeb 对 PHP 的支持仍处于测试阶段，我们建议您如果可以的话，使用反向代理架构。顺便说一句，对于某些集成（如 Kubernetes），PHP 完全不受支持。

BunkerWeb 支持使用外部或远程的 [PHP-FPM](https://www.php.net/manual/en/install.fpm.php) 实例。我们将假设您已经熟悉管理此类服务。

可以使用以下设置：

- `REMOTE_PHP`：远程 PHP-FPM 实例的主机名。
- `REMOTE_PHP_PATH`：远程 PHP-FPM 实例中包含文件的根文件夹。
- `REMOTE_PHP_PORT`：远程 PHP-FPM 实例的端口（*默认为 9000*）。
- `LOCAL_PHP`：本地 PHP-FPM 实例的套接字文件路径。
- `LOCAL_PHP_PATH`：本地 PHP-FPM 实例中包含文件的根文件夹。

=== "All-in-one"

    当使用 [All-in-one 镜像](integrations.md#all-in-one-aio-image)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中。
    - 为您的应用程序设置一个 PHP-FPM 容器，并挂载包含 PHP 文件的文件夹。
    - 在运行 BunkerWeb 时，使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为环境变量。

    如果您启用[多站点模式](features.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 directories, 2 files
    ```

    我们将假设您的 PHP 应用程序位于名为 `www` 的文件夹中。请注意，您需要修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    现在您可以运行 BunkerWeb，为您的 PHP 应用程序配置它，并运行 PHP 应用程序。您需要创建一个自定义的 Docker 网络，以允许 BunkerWeb 与您的 PHP-FPM 容器通信。

    ```bash
    # 创建一个自定义网络
    docker network create php-network

    # 运行 PHP-FPM 容器
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # 运行 BunkerWeb All-in-one
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
        bunkerity/bunkerweb-all-in-one:1.6.7-rc1
    ```

    请注意，如果您的容器已经创建，您需要删除并重新创建它，以便应用新的环境变量。

=== "Docker"

    当使用 [Docker 集成](integrations.md#docker)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中
    - 为您的应用程序设置一个 PHP-FPM 容器，并挂载包含 PHP 文件的文件夹
    - 在启动 BunkerWeb 时，使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为环境变量

    如果您启用[多站点模式](features.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

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

    我们将假设您的 PHP 应用程序位于名为 `www` 的文件夹中。请注意，您需要修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    现在您可以运行 BunkerWeb，为您的 PHP 应用程序配置它，并运行 PHP 应用程序：

    ```yaml
    x-bw-api-env: &bw-api-env
      # 我们使用锚点来避免为所有服务重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
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
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 此设置是指定 BunkerWeb 实例所必需的
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # 由于 MULTISITE 设置，将应用于所有服务
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
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

    !!! info "已启用多站点模式"
        [Docker autoconf 集成](integrations.md#docker-autoconf)意味着使用多站点模式：保护一个 PHP 应用程序与保护多个应用程序相同。

    当使用 [Docker autoconf 集成](integrations.md#docker-autoconf)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中
    - 为您的应用程序设置 PHP-FPM 容器，并挂载包含 PHP 应用程序的文件夹
    - 使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为您的 PHP-FPM 容器的标签

    由于 Docker autoconf 意味着使用[多站点模式](features.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

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

    创建文件夹后，复制您的文件并修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    当您启动 BunkerWeb autoconf 堆栈时，将 `www` 文件夹挂载到 **Scheduler** 容器的 `/var/www/html` 中：

    ```yaml
    x-bw-api-env: &bw-api-env
      # 我们使用锚点来避免为所有服务重复相同的设置
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
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
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # 我们不需要在这里指定 BunkerWeb 实例，因为它们由 autoconf 服务自动检测
          SERVER_NAME: "" # 服务器名称将由服务标签填充
          MULTISITE: "yes" # autoconf 的强制设置
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置更强的密码
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          AUTOCONF_MODE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置更强的密码
          DOCKER_HOST: "tcp://bw-docker:2375" # Docker 套接字
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
        # 我们设置了最大允许的数据包大小以避免大查询的问题
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # 记得为数据库设置更强的密码
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

    现在您可以创建您的 PHP-FPM 容器，挂载正确的子文件夹并使用标签来配置 BunkerWeb：

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

    !!! warning "Kubernetes 不支持 PHP"
        Kubernetes 集成允许通过 [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) 进行配置，而 BunkerWeb 控制器目前仅支持 HTTP 应用程序。

=== "Linux"

    我们将假设您已经在您的机器上运行了 [Linux 集成](integrations.md#linux)堆栈。

    默认情况下，BunkerWeb 将在 `/var/www/html` 文件夹内搜索 Web 文件。您可以用它来存储您的 PHP 应用程序。请注意，您需要配置您的 PHP-FPM 服务来获取或设置运行进程的用户/组以及用于与 BunkerWeb 通信的 UNIX 套接字文件。

    首先，您需要确保您的 PHP-FPM 实例可以访问 `/var/www/html` 文件夹内的文件，并且 BunkerWeb 可以访问 UNIX 套接字文件以便与 PHP-FPM 通信。我们建议为 PHP-FPM 服务设置一个不同的用户，如 `www-data`，并给予 nginx 组访问 UNIX 套接字文件的权限。以下是相应的 PHP-FPM 配置：

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

    不要忘记重启您的 PHP-FPM 服务：

    ```shell
    systemctl restart php-fpm
    ```

    如果您启用[多站点模式](features.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

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

    请注意，您需要修复权限，以便 BunkerWeb（`nginx` 组）至少可以读取文件和列出文件夹，而 PHP-FPM（`www-data` 用户，但这可能因您的系统而异）是文件和文件夹的所有者：

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    现在您可以编辑 `/etc/bunkerweb/variable.env` 文件：

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

    现在让我们检查调度程序的状态：

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    如果它们已经在运行，我们可以重新加载它：

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    !!! info "已启用多站点模式"
        [Swarm 集成](integrations.md#docker-autoconf)意味着使用多站点模式：保护一个 PHP 应用程序与保护多个应用程序相同。

    !!! info "共享卷"
        在 Docker Swarm 集成中使用 PHP 需要在所有 BunkerWeb 和 PHP-FPM 实例之间共享一个卷，这不在本文档的讨论范围之内。

    当使用 [Swarm](integrations.md#swarm)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中
    - 为您的应用程序设置 PHP-FPM 容器，并挂载包含 PHP 应用程序的文件夹
    - 使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为您的 PHP-FPM 容器的标签

    由于 Swarm 集成意味着使用[多站点模式](features.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

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

    作为一个例子，我们将假设您有一个共享文件夹挂载在您的工作节点上的 `/shared` 端点。

    创建文件夹后，复制您的文件并修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

    当您启动 BunkerWeb 堆栈时，将 `/shared/www` 文件夹挂载到 **Scheduler** 容器的 `/var/www/html` 中：

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    现在您可以创建您的 PHP-FPM 服务，挂载正确的子文件夹并使用标签来配置 BunkerWeb：

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

!!! example "实验性功能"

    此功能尚未准备好用于生产。欢迎您进行测试，并通过 GitHub 仓库中的 [issues](https://github.com/bunkerity/bunkerweb/issues) 向我们报告任何错误。

默认情况下，BunkerWeb 只会监听 IPv4 地址，不会使用 IPv6 进行网络通信。如果您想启用 IPv6 支持，需要将 `USE_IPV6=yes`。请注意，您的网络和环境的 IPv6 配置超出了本文档的范围。

=== "Docker / Autoconf / Swarm"

    首先，您需要配置您的 Docker 守护进程以启用容器的 IPv6 支持，并在需要时使用 ip6tables。这是您 `/etc/docker/daemon.json` 文件的示例配置：

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    现在您可以重启 Docker 服务以应用更改：

    ```shell
    systemctl restart docker
    ```

    一旦 Docker 设置好支持 IPv6，您就可以添加 `USE_IPV6` 设置并为 `bw-services` 配置 IPv6：

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
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

    您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

    让我们检查 BunkerWeb 的状态：

    ```shell
    systemctl status bunkerweb
    ```

    如果它们已经在运行，我们可以重启它：

    ```shell
    systemctl restart bunkerweb
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb
    ```

## 日志配置选项

BunkerWeb 提供灵活的日志配置，允许您同时将日志发送到多个目标（例如文件、stdout/stderr 或 syslog）。这对于将日志集成到外部收集器并同时在 Web UI 中保留本地日志非常有用。

可以配置的日志主要分为两类：

1. **服务日志（Service Logs）**：由 BunkerWeb 的组件（Scheduler、UI、Autoconf 等）生成。每个服务按 `LOG_TYPES` 控制（可选地配合 `LOG_FILE_PATH`、`LOG_SYSLOG_ADDRESS`、`LOG_SYSLOG_TAG`）。
2. **访问与错误日志（Access & Error Logs）**：由 NGINX 生成的 HTTP 访问日志和错误日志。仅由 `bunkerweb` 服务使用（`ACCESS_LOG` / `ERROR_LOG` / `LOG_LEVEL`）。

### 服务日志

服务日志由 `LOG_TYPES` 设置控制，支持以空格分隔的多个值（例如 `LOG_TYPES="stderr syslog"`）。

| 值       | 描述                                                                     |
| :------- | :----------------------------------------------------------------------- |
| `file`   | 将日志写入文件。Web UI 的日志查看器需要此项。                            |
| `stderr` | 将日志写入标准错误（stderr）。容器化环境（如 `docker logs`）的标准做法。 |
| `syslog` | 将日志发送到 syslog 服务器。使用此项时需要设置 `LOG_SYSLOG_ADDRESS`。    |

在使用 `syslog` 时，您还应该配置：

- `LOG_SYSLOG_ADDRESS`：syslog 服务器地址（例如 `udp://bw-syslog:514` 或 `/dev/log`）。
- `LOG_SYSLOG_TAG`：用于区分服务条目的唯一标签（例如 `bw-scheduler`）。
- `LOG_FILE_PATH`：当 `LOG_TYPES` 包含 `file` 时用于文件输出的路径（例如 `/var/log/bunkerweb/scheduler.log`）。

### 访问与错误日志

这些是标准的 NGINX 日志，仅通过 **`bunkerweb` 服务** 配置。它们支持通过在设置名称后添加编号后缀来配置多个目标（例如 `ACCESS_LOG`、`ACCESS_LOG_1` 与匹配的 `LOG_FORMAT` / `LOG_FORMAT_1`，或 `ERROR_LOG`、`ERROR_LOG_1` 与对应的 `LOG_LEVEL` / `LOG_LEVEL_1`）。

- `ACCESS_LOG`：访问日志目标（默认：`/var/log/bunkerweb/access.log`）。接受文件路径、`syslog:server=host[:port][,param=value]`、共享缓冲 `memory:name:size` 或 `off`（禁用）。详见 NGINX 的 [access_log 文档](https://nginx.org/en/docs/http/ngx_http_log_module.html#access_log)。
- `ERROR_LOG`：错误日志目标（默认：`/var/log/bunkerweb/error.log`）。接受文件路径、`stderr`、`syslog:server=host[:port][,param=value]` 或共享缓冲 `memory:size`。详见 NGINX 的 [error_log 文档](https://nginx.org/en/docs/ngx_core_module.html#error_log)。
- `LOG_LEVEL`：错误日志的详细级别（默认：`notice`）。

这些设置接受标准的 NGINX 值，包括文件路径、`stderr`、`syslog:server=...`（参见 [NGINX syslog 文档](https://nginx.org/en/docs/syslog.html)）或共享内存缓冲。它们支持通过编号后缀配置多个目标（参见 [多设置约定](features.md#multiple-settings)）。其他服务（Scheduler、UI、Autoconf 等）仅依赖 `LOG_TYPES` / `LOG_FILE_PATH` / `LOG_SYSLOG_*`。

**仅针对 bunkerweb（编号后缀示例，配置多个访问/错误日志）：**

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

### 集成默认值与示例

=== "Linux"

    **默认行为**：`LOG_TYPES="file"`。日志写入 `/var/log/bunkerweb/*.log`。

    **示例**：保留本地文件（供 Web UI 使用），同时镜像到系统 syslog。

    ```conf
      # 服务日志（在 /etc/bunkerweb/variables.env 或 特定服务的环境变量文件中设置）
      LOG_TYPES="file syslog"
      LOG_SYSLOG_ADDRESS=/dev/log
      SCHEDULER_LOG_FILE_PATH=/var/log/bunkerweb/scheduler.log
      UI_LOG_FILE_PATH=/var/log/bunkerweb/ui.log
      # ...
      # LOG_SYSLOG_TAG 将为每个服务自动设置（如需覆盖，可在每个服务中单独设置）

      # NGINX 日志（仅 bunkerweb 服务；在 /etc/bunkerweb/variables.env 中设置）
      ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb_access
      ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
    ```

=== "Docker / Autoconf / Swarm"

    **默认行为**：`LOG_TYPES="stderr"`。日志可通过 `docker logs` 查看。

    **示例（改编自快速入门指南）**：保留 `docker logs`（stderr），并发送到中央 syslog 容器（Web UI 和 CrowdSec 所需）。

    ```yaml
    x-bw-env: &bw-env # 使用锚点以避免为两个服务重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 确保设置正确的 IP 范围，以便调度程序可以将配置发送到实例
      # 可选：设置 API 令牌并在两个容器中镜像它
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置更强的密码
      # 服务日志
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"
      # LOG_SYSLOG_TAG 将为每个服务自动设置（如需覆盖，可在每个服务中单独设置）
      # NGINX 日志：发送到 Syslog（仅 bunkerweb）
      ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
      ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"

    services:
      bunkerweb:
        # 这将是用于在调度程序中识别实例的名称
        image: bunkerity/bunkerweb:1.6.7-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 用于 QUIC / HTTP3 支持
        environment:
          <<: *bw-env # 使用锚点以避免为所有服务重复相同的设置
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 确保设置正确的实例名称
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # 如需更改则修改此项
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # 用于持久化缓存和其他数据（例如备份）
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.7-rc1
        environment:
          <<: *bw-env
        volumes:
          - bw-logs:/var/log/bunkerweb # 用于 Web UI 读取 syslog 日志
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # 我们设置了最大允许的数据包大小以避免大查询的问题
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # 记得为数据库设置更强的密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis 服务，用于持久化报告/封禁/统计
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
          - NET_BIND_SERVICE # 绑定低端口
          - NET_BROADCAST # 发送广播
          - NET_RAW # 使用原始套接字
          - DAC_READ_SEARCH # 绕过权限读取文件
          - DAC_OVERRIDE # 覆盖文件权限
          - CHOWN # 更改所有者
          - SYSLOG # 写入系统日志
        volumes:
          - bw-logs:/var/log/bunkerweb # 用于存储日志的卷
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # syslog-ng 配置文件
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
          - subnet: 10.20.30.0/24 # 确保设置正确的 IP 范围，以便调度程序可以将配置发送到实例
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

### Syslog-ng 配置

下面是一个可将日志转发到文件的 `syslog-ng.conf` 示例：

```conf
@version: 4.10

# 源：接收 BunkerWeb 服务发送的日志（ACCESS_LOG / ERROR_LOG 且 LOG_TYPES=syslog）
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# 用于格式化日志消息的模板
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# 目标：将日志写入按程序名动态命名的文件
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

# 日志路径：将日志定向到按程序名动态命名的文件
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Docker 日志记录最佳实践

使用 Docker 时，管理容器日志以防止其占用过多磁盘空间非常重要。默认情况下，Docker 使用 `json-file` 日志记录驱动程序，如果未进行配置，可能会导致日志文件非常大。

为避免这种情况，您可以配置日志轮换。这可以在您的 `docker-compose.yml` 文件中为特定服务配置，也可以为 Docker 守护进程全局设置。

**按服务配置**

您可以在 `docker-compose.yml` 文件中为您的服务配置日志记录驱动程序以自动轮换日志。以下是一个示例，最多保留 10 个每个 20MB 的日志文件：

```yaml
services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.7-rc1
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "10"
    ...
```

此配置可确保日志轮换，防止它们占满您的磁盘。您可以将其应用于 Docker Compose 设置中的任何服务。

**全局设置 (daemon.json)**

如果您想默认将这些日志记录设置应用于主机上的所有容器，您可以通过编辑（或创建）`/etc/docker/daemon.json` 文件来配置 Docker 守护进程：

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "10"
  }
}
```

修改 `daemon.json` 后，您需要重新启动 Docker 守护进程才能使更改生效：

```shell
sudo systemctl restart docker
```

这些全局设置将由所有容器继承。但是，在 `docker-compose.yml` 文件中按服务定义的任何日志记录配置都将覆盖 `daemon.json` 中的全局设置。

## 安全性调整 {#security-tuning}

BunkerWeb 提供了许多安全功能，您可以通过[功能](features.md)进行配置。尽管设置的默认值确保了最低限度的“默认安全”，我们强烈建议您对它们进行调整。这样做，您不仅能够确保您所选择的安全级别，还能管理误报。

!!! tip "其他功能"
    本节仅关注安全调整，有关其他设置，请参阅文档的[功能](features.md)部分。

<figure markdown>
  ![概述](assets/img/core-order.svg){ align=center }
  <figcaption>核心安全插件的概述和顺序</figcaption>
</figure>

## CrowdSec 控制台集成

如果您还不熟悉 CrowdSec 控制台集成，[CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) 利用众包情报来对抗网络威胁。可以把它想象成“网络安全界的 Waze”——当一台服务器受到攻击时，全球其他系统都会收到警报，并受到保护，免受同一攻击者的侵害。您可以在[这里](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog)了解更多信息。

**恭喜，您的 BunkerWeb 实例现已注册到您的 CrowdSec 控制台！**

专业提示：查看警报时，点击“列”选项并勾选“上下文”复选框，以访问 BunkerWeb 特定的数据。

<figure markdown>
  ![概述](assets/img/crowdity4.png){ align=center }
  <figcaption>在上下文列中显示的 BunkerWeb 数据</figcaption>
</figure>

## 监控和报告

### 监控 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

监控插件让您可以收集和检索关于 BunkerWeb 的指标。启用它后，您的实例将开始收集与攻击、请求和性能相关的各种数据。然后，您可以通过定期调用 `/monitoring` API 端点或使用其他插件（如 Prometheus 导出器）来检索它们。

**功能列表**

- 启用各种 BunkerWeb 指标的收集
- 从 API 检索指标
- 与其他插件结合使用（例如 Prometheus 导出器）
- 专用 UI 页面监控您的实例

**设置列表**

| 设置                           | 默认  | 上下文 | 多个 | 描述                         |
| ------------------------------ | ----- | ------ | ---- | ---------------------------- |
| `USE_MONITORING`               | `yes` | 全局   | 否   | 启用 BunkerWeb 的监控。      |
| `MONITORING_METRICS_DICT_SIZE` | `10M` | 全局   | 否   | 用于存储监控指标的字典大小。 |

### Prometheus 导出器 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

Prometheus 导出器插件在您的 BunkerWeb 实例上添加了一个 [Prometheus 导出器](https://prometheus.io/docs/instrumenting/exporters/)。启用后，您可以配置您的 Prometheus 实例来抓取 BunkerWeb 上的特定端点并收集内部指标。

我们还提供了一个 [Grafana 仪表板](https://grafana.com/grafana/dashboards/20755-bunkerweb/)，您可以将其导入到自己的实例中，并连接到您自己的 Prometheus 数据源。

**请注意，使用 Prometheus 导出器插件需要启用监控插件 (`USE_MONITORING=yes`)**

**功能列表**

- 提供内部 BunkerWeb 指标的 Prometheus 导出器
- 专用且可配置的端口、监听 IP 和 URL
- 白名单 IP/网络以实现最高安全性

**设置列表**

| 设置                           | 默认                                                  | 上下文 | 多个 | 描述                                           |
| ------------------------------ | ----------------------------------------------------- | ------ | ---- | ---------------------------------------------- |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | 全局   | 否   | 启用 Prometheus 导出。                         |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | 全局   | 否   | Prometheus 导出器的监听 IP。                   |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | 全局   | 否   | Prometheus 导出器的监听端口。                  |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | 全局   | 否   | Prometheus 导出器的 HTTP URL。                 |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | 全局   | 否   | 允许联系 Prometheus 导出器端点的 IP/网络列表。 |

### 报告 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

!!! warning "需要监控插件"
  此插件需要安装并启用监控 Pro 插件，并将 `USE_MONITORING` 设置为 `yes`。

报告插件为 BunkerWeb 的重要数据提供全面的定期报告解决方案，包括全局统计、攻击、封禁、请求、原因和 AS 信息。它提供广泛的功能，包括自动报告创建、自定义选项以及与监控 Pro 插件的无缝集成。通过报告插件，您可以轻松生成和管理报告，以监控应用程序的性能和安全性。

**功能列表**

- 定期报告 BunkerWeb 的重要数据，包括全局统计、攻击、封禁、请求、原因和 AS 信息。
- 与监控 Pro 插件集成，实现无缝集成和增强的报告功能。
- 支持 Webhook（经典、Discord 和 Slack）以实现实时通知。
- 支持 SMTP 以进行电子邮件通知。
- 配置选项以实现自定义和灵活性。

**设置列表**

| 设置                           | 默认值             | 上下文 | 描述                                                          |
| ------------------------------ | ------------------ | ------ | ------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | 全局   | 启用通过电子邮件发送报告（HTML）。                            |
| `USE_REPORTING_WEBHOOK`        | `no`               | 全局   | 启用通过 Webhook 发送报告（Markdown）。                       |
| `REPORTING_SCHEDULE`           | `weekly`           | 全局   | 报告频率：`daily`、`weekly` 或 `monthly`。                    |
| `REPORTING_WEBHOOK_URLS`       |                    | 全局   | 以空格分隔的 Webhook URL；Discord 和 Slack 会自动检测。       |
| `REPORTING_SMTP_EMAILS`        |                    | 全局   | 以空格分隔的电子邮件收件人。                                  |
| `REPORTING_SMTP_HOST`          |                    | 全局   | SMTP 服务器主机名或 IP。                                      |
| `REPORTING_SMTP_PORT`          | `465`              | 全局   | SMTP 端口。使用 `465` 表示 SSL，`587` 表示 TLS。              |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | 全局   | 发送者地址（如果您的提供商要求，请禁用 2FA）。                |
| `REPORTING_SMTP_FROM_USER`     |                    | 全局   | SMTP 用户名（如果省略且设置了密码，则回退到发送者电子邮件）。 |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | 全局   | SMTP 密码。                                                   |
| `REPORTING_SMTP_SSL`           | `SSL`              | 全局   | 连接安全性：`no`、`SSL` 或 `TLS`。                            |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | 全局   | 电子邮件发送的主题行。                                        |

!!! info "行为说明"
  - 启用 SMTP 发送时需要 `REPORTING_SMTP_EMAILS`；启用 Webhook 发送时需要 `REPORTING_WEBHOOK_URLS`。
  - 如果 Webhook 和 SMTP 都失败，发送将在下一次计划运行时重试。
  - HTML 和 Markdown 模板位于 `reporting/files/`；自定义时请谨慎保留占位符。

## 备份和恢复

### S3 备份 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :white_check_mark:

S3 备份工具可以无缝地自动化数据保护，类似于社区备份插件。然而，它的突出之处在于将备份直接安全地存储在 S3 存储桶中。

通过激活此功能，您正在主动保护您的**数据完整性**。将备份**远程**存储可以保护关键信息免受**硬件故障**、**网络攻击**或**自然灾害**等威胁。这确保了**安全**和**可用性**，能够在**意外事件**期间快速恢复，维护**运营连续性**，并确保**高枕无忧**。

??? warning "给红帽企业 Linux (RHEL) 8.9 用户的信息"
    如果您正在使用 **RHEL 8.9** 并计划使用**外部数据库**，您需要安装 `mysql-community-client` 包以确保 `mysqldump` 命令可用。您可以通过执行以下命令来安装该包：

    === "MySQL/MariaDB"

        1.  **安装 MySQL 仓库配置包**

            ```bash
            sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
            ```

        2.  **启用 MySQL 仓库**

            ```bash
            sudo dnf config-manager --enable mysql80-community
            ```

        3.  **安装 MySQL 客户端**

            ```bash
            sudo dnf install mysql-community-client
            ```

    === "PostgreSQL"

        1.  **安装 PostgreSQL 仓库配置包**

            ```bash
            dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
            ```

        2.  **安装 PostgreSQL 客户端**

            ```bash
            dnf install postgresql<version>
            ```

**功能列表**

- 自动将数据备份到 S3 存储桶
- 灵活的调度选项：每日、每周或每月
- 轮换管理，用于控制要保留的备份数量
- 可自定义的备份文件压缩级别

**设置列表**

| 设置                          | 默认    | 上下文 | 描述                    |
| ----------------------------- | ------- | ------ | ----------------------- |
| `USE_BACKUP_S3`               | `no`    | 全局   | 启用或禁用 S3 备份功能  |
| `BACKUP_S3_SCHEDULE`          | `daily` | 全局   | 备份频率                |
| `BACKUP_S3_ROTATION`          | `7`     | 全局   | 要保留的备份数量        |
| `BACKUP_S3_ENDPOINT`          |         | 全局   | S3 端点                 |
| `BACKUP_S3_BUCKET`            |         | 全局   | S3 存储桶               |
| `BACKUP_S3_DIR`               |         | 全局   | S3 目录                 |
| `BACKUP_S3_REGION`            |         | 全局   | S3 区域                 |
| `BACKUP_S3_ACCESS_KEY_ID`     |         | 全局   | S3 访问密钥 ID          |
| `BACKUP_S3_ACCESS_KEY_SECRET` |         | 全局   | S3 访问密钥 Secret      |
| `BACKUP_S3_COMP_LEVEL`        | `6`     | 全局   | 备份 zip 文件的压缩级别 |

#### 手动备份

要手动启动备份，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

此命令将创建您的数据库备份，并将其存储在 `BACKUP_S3_BUCKET` 设置中指定的 S3 存储桶中。

您还可以在执行命令时通过提供 `BACKUP_S3_BUCKET` 环境变量来为备份指定自定义 S3 存储桶：

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "MariaDB/MySQL 的特别说明"

    如果您正在使用 MariaDB/MySQL，在尝试备份数据库时可能会遇到以下错误：

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    要解决此问题，您可以执行以下命令将身份验证插件更改为 `mysql_native_password`：

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    如果您正在使用 Docker 集成，可以将以下命令添加到 `docker-compose.yml` 文件中，以自动更改身份验证插件：

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

#### 手动恢复

要手动启动恢复，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

此命令将在 `BACKUP_S3_BUCKET` 设置中指定的 S3 存储桶中创建您数据库的临时备份，并将您的数据库恢复到存储桶中可用的最新备份。

您还可以在执行命令时通过提供备份文件的路径作为参数来为恢复指定自定义备份文件：

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "如果失败"

    如果恢复失败，请不要担心，您可以随时通过再次执行命令将数据库恢复到先前的状态，因为在恢复之前会创建一个备份：

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

## 迁移 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :white_check_mark:

迁移插件通过其**用户友好的 Web 界面**，彻底改变了 BunkerWeb 实例之间的配置传输，简化了整个迁移过程。无论您是升级系统、扩展基础设施还是转换环境，此工具都能让您轻松自信地传输**设置、首选项和数据**。告别繁琐的手动流程，迎接**无缝、无忧的迁移体验**。

**功能列表**

- **轻松迁移：** 轻松在实例之间传输 BunkerWeb 配置，无需复杂的手动操作。

- **直观的 Web 界面：** 通过为直观操作设计的用户友好 Web 界面，轻松导航迁移过程。

- **跨数据库兼容性：** 在各种数据库平台之间实现无缝迁移，包括 SQLite、MySQL、MariaDB 和 PostgreSQL，确保与您首选的数据库环境兼容。

### 创建迁移文件

要手动创建迁移文件，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin migration create /path/to/migration/file
    ```

=== "Docker"

    1.  创建迁移文件：

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /path/to/migration/file
        ```

    2.  将迁移文件复制到您的本地计算机：

        ```bash
        docker cp <scheduler_container>:/path/to/migration/file /path/to/migration/file
        ```

此命令将创建您的数据库备份，并将其存储在命令中指定的备份目录中。

!!! note "MariaDB/MySQL 的特别说明"

    如果您正在使用 MariaDB/MySQL，在尝试备份数据库时可能会遇到以下错误：

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    要解决此问题，您可以执行以下命令将身份验证插件更改为 `mysql_native_password`：

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    如果您正在使用 Docker 集成，可以将以下命令添加到 `docker-compose.yml` 文件中，以自动更改身份验证插件：

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

### 初始化迁移

要手动初始化迁移，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin migration migrate /path/to/migration/file
    ```

=== "Docker"

    1.  将迁移文件复制到容器中：

        ```bash
        docker cp /path/to/migration/file <scheduler_container>:/path/to/migration/file
        ```

    2.  初始化迁移：

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /path/to/migration/file
        ```

=== "All-in-one"

    1.  将迁移文件复制到容器中：

        ```bash
        docker cp /path/to/migration/file bunkerweb-aio:/path/to/migration/file
        ```

    2.  初始化迁移：

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /path/to/migration/file
        ```

此命令将您的 BunkerWeb 数据无缝迁移，以精确匹配迁移文件中概述的配置。

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

**Anti DDoS** 插件通过实时监控、分析和过滤可疑流量，提供针对分布式拒绝服务 (DDoS) 攻击的高级保护。

通过采用**滑动窗口机制**，该插件在内存中维护一个请求时间戳字典，以检测来自单个 IP 地址的异常流量峰值。根据配置的安全模式，它可以阻止违规连接或记录可疑活动以供进一步审查。

### 功能

- **实时流量分析：** 持续监控传入请求以检测潜在的 DDoS 攻击。
- **滑动窗口机制：** 在可配置的时间窗口内跟踪最近的请求活动。
- **可配置的阈值：** 允许您定义每个 IP 的最大可疑请求数。
- **高级阻止逻辑：** 评估每个 IP 的请求计数和超过阈值的不同 IP 数量。
- **灵活的安全模式：** 在立即阻止连接或仅检测（记录）模式之间进行选择。
- **优化的内存数据存储：** 确保高速查找和高效的指标跟踪。
- **自动清理：** 定期清除过时数据以保持最佳性能。

### 配置

使用以下设置自定义插件行为：

| 设置                         | 默认          | 上下文 | 多个 | 描述                                                            |
| ---------------------------- | ------------- | ------ | ---- | --------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | 全局   | 否   | 启用或禁用 Anti DDoS 保护。设置为 `"yes"` 以激活插件。          |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | 全局   | 否   | 用于跟踪 DDoS 指标的内存数据存储的大小（例如，`10M`, `500k`）。 |
| `ANTIDDOS_THRESHOLD`         | `100`         | 全局   | 否   | 在定义的时间窗口内，每个 IP 允许的最大可疑请求数。              |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | 全局   | 否   | 统计可疑请求的时间窗口（秒）。                                  |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | 全局   | 否   | 被认为是可疑并用于触发反 DDoS 操作的 HTTP 状态码。              |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | 全局   | 否   | 在强制执行阻止模式之前，必须超过阈值的最少不同 IP 数量。        |

### 最佳实践

- **阈值调整：** 根据您的典型流量模式调整 `ANTIDDOS_THRESHOLD` 和 `ANTIDDOS_WINDOW_TIME`。
- **状态码审查：** 定期更新 `ANTIDDOS_STATUS_CODES` 以捕获新的或不断演变的可疑行为。
- **监控：** 定期分析日志和指标以微调设置并提高整体保护。

## 用户管理器 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="用户管理器页面" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

用户管理插件提供了一个强大的界面，用于管理系统内的用户帐户。

借助此插件，管理员可以轻松创建、更新和禁用用户帐户，管理用户角色，切换双因素身份验证 (2FA)，并查看详细的用户信息，例如上次登录时间戳和帐户状态（活动或非活动）。该插件在设计时考虑了安全性和易用性，简化了常规的用户管理任务，同时确保了合规性和可审计性。

### 功能

- **用户帐户操作：** 支持以 CSV/XSLX 格式导入，轻松创建、编辑和删除用户帐户。
- **基于角色的访问控制：** 分配和修改用户角色以管理权限和访问级别。
- **2FA 管理：** 根据管理决策禁用双因素身份验证。
- **全面的用户洞察：** 监控关键用户数据，包括上次登录时间、帐户创建日期以及活动/非活动状态。
- **审计日志记录：** 维护所有用户管理操作的审计跟踪，以增强安全性和合规性。

<figure markdown>
  ![概述](assets/img/user-manager.png){ align=center }
  <figcaption>用户管理器页面</figcaption>
</figure>

<figure markdown>
  ![创建用户表单](assets/img/user-manager-create.png){ align=center }
  <figcaption>用户管理器 - 创建用户表单</figcaption>
</figure>

<figure markdown>
  ![活动页面](assets/img/user-manager-activities.png){ align=center }
  <figcaption>用户管理器 - 活动页面</figcaption>
</figure>

## 轻松解决 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

轻松解决插件让您可以直接从报告页面快速修复误报和重复出现的问题。它将引导式的“解决”操作转化为安全、范围受限的配置更新——无需手动编辑。

### 功能

- 从报告和报告详情中一键操作。
- 针对 ModSecurity、黑名单和 DNSBL 的上下文感知建议。
- 生成安全的 ModSecurity 排除规则或更新忽略列表。
- 在服务或全局范围内应用更改，并进行权限检查。
- 应用后可选择自动打开相关配置页面。

<figure markdown>
  ![概述](assets/img/easy-resolve.png){ align=center }
  <figcaption>报告页面 - 带有轻松解决功能</figcaption>
</figure>

<div class="grid grid-2" markdown>
<figure markdown>
  ![ModSecurity 解决](assets/img/easy-resolve-modsecurity.png){ width="100%" }
  <figcaption>ModSecurity 解决</figcaption>
</figure>
<figure markdown>
  ![DNSBL 解决](assets/img/easy-resolve-dnsbl.png){ width="100%" }
  <figcaption>DNSBL 解决</figcaption>
</figure>
</div>

<div class="grid grid-5" markdown>
<figure markdown>
  ![黑名单解决 - IP](assets/img/easy-resolve-blacklist-ip.png){ width="100%" }
  <figcaption>黑名单 - IP</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - User-Agent](assets/img/easy-resolve-blacklist-ua.png){ width="100%" }
  <figcaption>黑名单 - User-Agent</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - rDNS](assets/img/easy-resolve-blacklist-rdns.png){ width="100%" }
  <figcaption>黑名单 - rDNS</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - ASN](assets/img/easy-resolve-blacklist-asn.png){ width="100%" }
  <figcaption>黑名单 - ASN</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - URI](assets/img/easy-resolve-blacklist-uri.png){ width="100%" }
  <figcaption>黑名单 - URI</figcaption>
</figure>
</div>

## Load Balancer <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/cOVp0rAt5nw?si=iVhDio8o8S4F_uag" title="Load Balancer" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Load Balancer 插件将 BunkerWeb 转变为带有护栏的流量导向器。一次声明上游池，将您的反向代理指向它们，并让健康感知平衡将用户保持在响应式后端上。粘性 cookie 模式自动发出 `BWLBID` cookie，以便会话保持在您想要的地方。

### 功能

- 每个上游块：命名池并在反向代理主机上重用。
- 灵活平衡：默认 round-robin，或通过 IP 或签名 cookie 粘性。
- 智能目标：可选 DNS 解析用于主机名后端加上 keepalive 调整。
- 内置健康：HTTP/HTTPS 探测，具有自定义路径、间隔、状态代码和 SSL 检查。
- 会话连续性：启用粘性 cookie 模式时自动 `BWLBID` cookie。

### 配置

**上游定义**

| 设置                                      | 默认          | 上下文 | 多个 | 描述                                                           |
| ----------------------------------------- | ------------- | ------ | ---- | -------------------------------------------------------------- |
| `LOADBALANCER_UPSTREAM_NAME`              |               | global | 是   | 上游标识符（由 `REVERSE_PROXY_HOST` 引用）。                   |
| `LOADBALANCER_UPSTREAM_SERVERS`           |               | global | 是   | 后端地址的空格分隔列表（例如 `10.0.0.1:8080 10.0.0.2:8080`）。 |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin` | global | 是   | 平衡策略（`round-robin` 或 `sticky`）。                        |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`          | global | 是   | 粘性方法（`ip` 或 `cookie`）。Cookie 模式发出 `BWLBID`。       |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`          | global | 是   | 通过 DNS 解析上游主机名。                                      |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |               | global | 是   | 每个 worker 的 keepalive 连接。                                |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`         | global | 是   | Keepalive 连接的空闲超时。                                     |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`          | global | 是   | Keepalive 连接的最大寿命。                                     |

**健康检查**

| 设置                                      | 默认      | 上下文 | 多个 | 描述                                  |
| ----------------------------------------- | --------- | ------ | ---- | ------------------------------------- |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`     | global | 否   | 健康检查状态的共享字典大小。          |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status` | global | 是   | 在每个后端上探测的路径。              |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`    | global | 是   | 检查之间的间隔（ms）。                |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`    | global | 是   | 每次检查的超时（ms）。                |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`       | global | 是   | 标记为 down 前的连续失败次数。        |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`       | global | 是   | 标记为 up 前的连续成功次数。          |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`     | global | 是   | 有效 HTTP 状态代码的空格分隔列表。    |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`      | global | 是   | 最大并发探测。                        |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`    | global | 是   | 健康检查协议（`http` 或 `https`）。   |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`     | global | 是   | 使用 HTTPS 检查时验证 TLS 证书。      |
| `LOADBALANCER_HEALTHCHECK_HOST`           |           | global | 是   | 检查期间覆盖 Host 头（对 SNI 有用）。 |

### 快速开始

1. 定义您的池：设置 `LOADBALANCER_UPSTREAM_NAME=my-app` 并在 `LOADBALANCER_UPSTREAM_SERVERS` 中列出目标（例如 `10.0.0.1:8080 10.0.0.2:8080`）。
2. 指向流量：设置 `REVERSE_PROXY_HOST=http://my-app` 以便反向代理使用命名的上游。
3. 选择模式：保持默认 round-robin 或设置 `LOADBALANCER_UPSTREAM_MODE=sticky` 与 `LOADBALANCER_UPSTREAM_STICKY_METHOD=cookie` 或 `ip`。
4. 添加健康：保持 `/status` 或调整 URL、间隔和有效状态以反映您的应用行为。
5. 调整连接：配置 keepalive 值以重用后端连接并减少握手开销。

### 使用提示

- 使用粘性 cookie 时，将 `REVERSE_PROXY_HOST` 与 `LOADBALANCER_UPSTREAM_NAME` 匹配，以便客户端固定到正确的池。
- 保持健康检查间隔和超时平衡，以避免在慢速链路上波动。
- 当指向可能通过 DNS 更改的主机名时启用 `LOADBALANCER_UPSTREAM_RESOLVE`。
- 调整 keepalive 值以反映后端容量和连接重用目标。

## Custom Pages <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Custom Pages 插件允许您将 BunkerWeb 的内置页面（错误页面、默认服务器页面和反机器人挑战页面）替换为您自己的自定义 HTML 或 Lua 模板。这使您能够在 BunkerWeb 提供的所有面向用户的页面上保持一致的品牌形象。

### 功能

- **每个服务的自定义错误页面**和**反机器人挑战页面**（验证码、JavaScript 检查、reCAPTCHA、hCaptcha、Turnstile、mCaptcha）。
- **全局自定义默认服务器页面**用于回退/默认虚拟主机。
- **HTML 解析和 Lua 模板标签平衡检查**在接受模板之前。
- **自动缓存**到 `/var/cache/bunkerweb/custom_pages`，带有变更检测以触发重新加载。
- **每站点或全局配置**通过设置/UI 或环境变量。

### 工作原理

1. 在启动时（或当设置更改时），`custom-pages.py` 作业读取配置的模板路径。
2. 每个文件必须存在且可被调度器读取；作业验证 HTML 结构和平衡的 Lua 模板标签（`{% %}`、`{{ }}`、`{* *}`）。
3. 接受的文件缓存在 `/var/cache/bunkerweb/custom_pages/<type>.html` 下；缺失/空设置会删除缓存文件。
4. 当至少存在一个缓存页面时，NGINX 通过 `$template_root` 指向缓存目录，因此您的模板将替代默认页面提供服务。

### 配置设置

| 设置                             | 默认 | 上下文    | 描述                                           |
| -------------------------------- | ---- | --------- | ---------------------------------------------- |
| `CUSTOM_ERROR_PAGE`              |      | multisite | 自定义错误页面模板的绝对路径。                 |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |      | global    | 自定义默认服务器页面模板的绝对路径。           |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |      | multisite | 自定义反机器人验证码挑战页面的绝对路径。       |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |      | multisite | 自定义反机器人 JavaScript 检查页面的绝对路径。 |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |      | multisite | 自定义反机器人 reCAPTCHA 页面的绝对路径。      |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |      | multisite | 自定义反机器人 hCaptcha 页面的绝对路径。       |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |      | multisite | 自定义反机器人 Turnstile 页面的绝对路径。      |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |      | multisite | 自定义反机器人 mCaptcha 页面的绝对路径。       |

### 模板变量参考

BunkerWeb 模板使用 [lua-resty-template](https://github.com/bungle/lua-resty-template) 引擎。以下变量根据页面类型可用：

#### 错误页面变量

这些变量在自定义错误页面模板（`CUSTOM_ERROR_PAGE`）中可用：

| 变量             | 类型   | 描述                                            |
| ---------------- | ------ | ----------------------------------------------- |
| `title`          | string | 完整页面标题（例如 `403 - Forbidden`）          |
| `error_title`    | string | 错误标题文本（例如 `Forbidden`）                |
| `error_code`     | string | HTTP 状态码（例如 `403`、`404`、`500`）         |
| `error_text`     | string | 描述性错误消息                                  |
| `error_type`     | string | 错误类别：`client`（4xx）或 `server`（5xx）     |
| `error_solution` | string | 建议的解决方案文本                              |
| `nonce_script`   | string | 内联 `<script>` 标签的 Nonce 值（CSP 合规）     |
| `nonce_style`    | string | 内联 `<style>` 标签的 Nonce 值（CSP 合规）      |
| `request_id`     | string | 用于调试的唯一请求标识符                        |
| `client_ip`      | string | 客户端的 IP 地址                                |
| `request_time`   | string | 请求的时间戳（格式：`YYYY-MM-DD HH:MM:SS UTC`） |

#### 默认服务器页面变量

这些变量在自定义默认服务器页面模板（`CUSTOM_DEFAULT_SERVER_PAGE`）中可用：

| 变量          | 类型   | 描述                                       |
| ------------- | ------ | ------------------------------------------ |
| `nonce_style` | string | 内联 `<style>` 标签的 Nonce 值（CSP 合规） |

#### 反机器人挑战页面变量

这些变量在反机器人挑战页面模板中可用：

**通用变量（所有反机器人页面）：**

| 变量           | 类型   | 描述                                        |
| -------------- | ------ | ------------------------------------------- |
| `antibot_uri`  | string | 提交挑战的表单操作 URI                      |
| `nonce_script` | string | 内联 `<script>` 标签的 Nonce 值（CSP 合规） |
| `nonce_style`  | string | 内联 `<style>` 标签的 Nonce 值（CSP 合规）  |

**JavaScript 挑战（`CUSTOM_ANTIBOT_JAVASCRIPT_PAGE`）：**

| 变量     | 类型   | 描述                           |
| -------- | ------ | ------------------------------ |
| `random` | string | 用于工作量证明求解的随机字符串 |

**验证码（`CUSTOM_ANTIBOT_CAPTCHA_PAGE`）：**

| 变量      | 类型   | 描述                                 |
| --------- | ------ | ------------------------------------ |
| `captcha` | string | Base64 编码的验证码图像（JPEG 格式） |

**reCAPTCHA（`CUSTOM_ANTIBOT_RECAPTCHA_PAGE`）：**

| 变量                | 类型    | 描述                                              |
| ------------------- | ------- | ------------------------------------------------- |
| `recaptcha_sitekey` | string  | 您的 reCAPTCHA 站点密钥                           |
| `recaptcha_classic` | boolean | 如果使用经典 reCAPTCHA 则为 `true`，v3 为 `false` |

**hCaptcha（`CUSTOM_ANTIBOT_HCAPTCHA_PAGE`）：**

| 变量               | 类型   | 描述                   |
| ------------------ | ------ | ---------------------- |
| `hcaptcha_sitekey` | string | 您的 hCaptcha 站点密钥 |

**Turnstile（`CUSTOM_ANTIBOT_TURNSTILE_PAGE`）：**

| 变量                | 类型   | 描述                               |
| ------------------- | ------ | ---------------------------------- |
| `turnstile_sitekey` | string | 您的 Cloudflare Turnstile 站点密钥 |

**mCaptcha（`CUSTOM_ANTIBOT_MCAPTCHA_PAGE`）：**

| 变量               | 类型   | 描述                   |
| ------------------ | ------ | ---------------------- |
| `mcaptcha_sitekey` | string | 您的 mCaptcha 站点密钥 |
| `mcaptcha_url`     | string | 您的 mCaptcha URL      |

### 模板语法

模板使用 Lua 模板语法，具有以下分隔符：

- `{{ variable }}` – 输出变量（HTML 转义）
- `{* variable *}` – 输出变量（原始，未转义）
- `{% lua_code %}` – 执行 Lua 代码（条件、循环等）
- `{-raw-}` ... `{-raw-}` – 原始块（不处理）

**重要**：始终对内联脚本和样式使用 nonce 属性以符合内容安全策略（CSP）：

```html
<style nonce="{*nonce_style*}">
  /* 您的 CSS */
</style>
<script nonce="{*nonce_script*}">
  // 您的 JavaScript
</script>
```

### 示例

=== "自定义错误页面"

    在 `/etc/bunkerweb/templates/error.html` 创建自定义错误页面模板：

    ```html
    {-raw-}<!doctype html>
    <html lang="zh">
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
            <p>请求 ID：<code>{{ request_id }}</code></p>
            {% end %}
            {% if request_time %}
            <p>时间：{{ request_time }}</p>
            {% end %}
          </div>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "自定义验证码页面"

    在 `/etc/bunkerweb/templates/captcha.html` 创建自定义验证码挑战页面：

    ```html
    {-raw-}<!doctype html>
    <html lang="zh">
      <head>
        <meta charset="utf-8" />
        <title>安全检查</title>
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
          <h1>🔒 安全检查</h1>
          <p>请输入下方显示的文字以继续。</p>
          {-raw-}
          <form method="POST" action="{*antibot_uri*}">
            <img class="captcha-img" src="data:image/jpeg;base64,{*captcha*}" alt="验证码" />
            {-raw-}
            <input type="text" name="captcha" placeholder="输入验证码" required autocomplete="off" />
            <button type="submit">验证</button>
          </form>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "自定义默认服务器页面"

    在 `/etc/bunkerweb/templates/default.html` 创建自定义默认服务器页面：

    ```html
    {-raw-}<!doctype html>
    <html lang="zh">
      <head>
        <meta charset="utf-8" />
        <title>欢迎</title>
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
          <h1>🛡️ 受 BunkerWeb 保护</h1>
          <p>此服务器安全且已就绪。</p>
        </div>
      </body>
    </html>
    {-raw-}
    ```

### 部署示例

=== "Linux"

    1. 在您选择的目录中创建模板文件（例如 `/opt/bunkerweb/templates/`）：

        ```bash
        sudo mkdir -p /opt/bunkerweb/templates
        sudo nano /opt/bunkerweb/templates/error.html
        # 粘贴您的自定义错误页面模板
        ```

    2. 通过编辑 `/etc/bunkerweb/variables.env` 配置 BunkerWeb：

        ```conf
        # 所有服务的自定义错误页面（或使用前缀按服务配置）
        CUSTOM_ERROR_PAGE=/opt/bunkerweb/templates/error.html

        # 自定义默认服务器页面（仅全局）
        CUSTOM_DEFAULT_SERVER_PAGE=/opt/bunkerweb/templates/default.html

        # 自定义验证码页面（按服务或全局）
        CUSTOM_ANTIBOT_CAPTCHA_PAGE=/opt/bunkerweb/templates/captcha.html
        ```

    3. 重新加载 BunkerWeb：

        ```bash
        sudo systemctl reload bunkerweb
        ```

=== "Docker"

    **调度器**负责读取、验证和缓存您的自定义模板。只有调度器需要访问模板文件—BunkerWeb 自动接收验证后的配置。

    1. 在本地目录中创建模板文件（例如 `./templates/`）并设置正确的权限：

        ```bash
        mkdir templates && \
        chown root:101 templates && \
        chmod 770 templates
        ```

        !!! info "为什么是 UID/GID 101？"
            调度器容器以**UID 101 和 GID 101 的非特权用户**运行。目录必须对此用户可读，以便调度器访问您的模板。

        如果文件夹已存在：

        ```bash
        chown -R root:101 templates && \
        chmod -R 770 templates
        ```

        使用 [Docker rootless 模式](https://docs.docker.com/engine/security/rootless) 或 [Podman](https://podman.io/) 时，容器 UID/GID 会被重新映射。检查您的 subuid/subgid 范围：

        ```bash
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        例如，如果范围从 **100000** 开始，有效 GID 变为 **100100**（100000 + 100）：

        ```bash
        mkdir templates && \
        sudo chgrp 100100 templates && \
        chmod 770 templates
        ```

    2. 将模板目录挂载到**调度器**并在调度器上配置设置（调度器充当管理器并将配置分发给 BunkerWeb 工作器）。您可以将模板挂载到容器内的任何路径：

        ```yaml
        services:
          bunkerweb:
            image: bunkerity/bunkerweb:1.6.7-rc1
            # ... 其他设置（自定义页面无需在此处设置环境变量）

          bw-scheduler:
            image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
            volumes:
              - ./templates:/custom_templates:ro
            environment:
              - CUSTOM_ERROR_PAGE=/custom_templates/error.html
              - CUSTOM_DEFAULT_SERVER_PAGE=/custom_templates/default.html
              - CUSTOM_ANTIBOT_CAPTCHA_PAGE=/custom_templates/captcha.html
              # ... 其他设置
        ```

    !!! warning "需要调度器访问权限"
        如果调度器无法读取模板文件（由于缺少挂载或权限不正确），模板将被静默忽略，将使用默认页面。检查调度器日志以了解验证错误。

=== "Kubernetes"

    **调度器**负责读取、验证和缓存您的自定义模板。您需要将模板挂载到调度器 Pod。

    1. 创建包含模板的 ConfigMap：

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: bunkerweb-custom-templates
        data:
          error.html: |
            {-raw-}<!doctype html>
            <html lang="zh">
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
            <html lang="zh">
              <head>
                <meta charset="utf-8" />
                <title>安全检查</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                </style>
                {-raw-}
              </head>
              <body>
                <h1>请验证您是人类</h1>
                {-raw-}
                <form method="POST" action="{*antibot_uri*}">
                  <img src="data:image/jpeg;base64,{*captcha*}" alt="验证码" />
                  {-raw-}
                  <input type="text" name="captcha" placeholder="输入验证码" required />
                  <button type="submit">验证</button>
                </form>
              </body>
            </html>
            {-raw-}
        ```

    2. 将模板 ConfigMap 挂载到**调度器** Pod 并将设置配置为环境变量：

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
                  image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                  env:
                    - name: CUSTOM_ERROR_PAGE
                      value: "/custom_templates/error.html"
                    - name: CUSTOM_ANTIBOT_CAPTCHA_PAGE
                      value: "/custom_templates/captcha.html"
                    # ... 其他设置
                  volumeMounts:
                    - name: custom-templates
                      mountPath: /custom_templates
                      readOnly: true
                  # ... 其他容器设置
              volumes:
                - name: custom-templates
                  configMap:
                    name: bunkerweb-custom-templates
              # ... 其他 Pod 设置
        ```

    !!! tip "使用 BunkerWeb Ingress Controller"
        如果您使用 BunkerWeb Ingress Controller，调度器嵌入在控制器中。请将 ConfigMap 挂载到控制器 Pod。

### 注意事项和故障排除

- **路径必须是绝对路径**并以文件名结尾；空值会禁用相应的自定义页面并删除其缓存。
- **如果验证失败**（错误的 HTML 或不平衡的 Lua 标签），模板将被跳过，默认页面保持活动状态。检查调度器日志以获取详细信息。
- **缓存文件**位于 `/var/cache/bunkerweb/custom_pages`；更新源文件就足够了—作业检测到新哈希并自动重新加载 NGINX。
- **CSP 合规**：始终对内联脚本和样式使用 `nonce_script` 和 `nonce_style` 变量，以确保正确的内容安全策略处理。
- **测试模板**：您可以在部署到 BunkerWeb 之前使用 Lua 模板引擎在本地渲染测试您的模板。
