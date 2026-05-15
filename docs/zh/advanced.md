# 高级用法

GitHub 仓库的 [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.10/examples) 文件夹中提供了许多真实世界的用例示例。

我们还提供了许多样板文件，例如用于各种集成和数据库类型的 YAML 文件。这些都可以在 [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.10/misc/integrations) 文件夹中找到。

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
            bunkerity/bunkerweb-all-in-one:1.6.10
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.10
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.10
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
          image: bunkerity/bunkerweb:1.6.10
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.10
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
          image: bunkerity/bunkerweb:1.6.10
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.10
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
            bunkerity/bunkerweb-all-in-one:1.6.10
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.10
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.10
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
          image: bunkerity/bunkerweb:1.6.10
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.10
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
          image: bunkerity/bunkerweb:1.6.10
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.10
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
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.10/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.10/install-bunkerweb.sh.sha256

        # 校验完整性
        sha256sum -c install-bunkerweb.sh.sha256

        # 运行安装器
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "安全提示"
            在执行脚本前务必通过提供的校验值验证其完整性。

    2. 在安装类型菜单中**选择 Manager**（使用 ↑/↓ 然后按回车），并按提示操作：

        | 提示                    | 操作                                                                          |
        | :---------------------- | :---------------------------------------------------------------------------- |
        | **BunkerWeb 实例**      | 输入 Worker 节点 IP，空格分隔（例如 `192.168.10.11 192.168.10.12`）。         |
        | **Whitelist IP**        | 接受检测到的 IP，或输入网段（例如 `192.168.10.0/24`）以允许访问内部 API。     |
        | **DNS 解析器**          | 选择 **否** 以保留默认值，或指定自定义解析器。                                |
        | **内部 API 启用 HTTPS** | **推荐：** 选择 **是** 自动生成证书，保护 Manager-Worker 通信。               |
        | **Web UI 服务**         | 选择 **是** 启用界面（强烈推荐）。                                            |
        | **API 服务**            | 除非需要公共 REST API，否则选择 **否**。                                      |

        !!! note "提示交互界面"
            安装器使用 [gum](https://github.com/charmbracelet/gum) TUI。首次交互运行时，会从 GitHub 发布页下载官方 `gum` 二进制（SHA256 已固定），从临时目录运行，并在脚本退出时删除该临时目录 —— 不会安装任何系统包。使用方向键 + 回车作答。若希望使用纯文本提示，请传入 `--no-tui`。

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
        FORWARDED_ALLOW_IPS=127.0.0.1,::1
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

        1. 运行安装器并选择 **Web UI Only** 安装类型。
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
        image: bunkerity/bunkerweb-scheduler:1.6.10
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
        image: bunkerity/bunkerweb-ui:1.6.10
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
          --maxmemory-policy volatile-lru
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
        image: bunkerity/bunkerweb:1.6.10
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
        bunkerity/bunkerweb-all-in-one:1.6.10
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
        image: bunkerity/bunkerweb:1.6.10
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.10
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
        bunkerity/bunkerweb-all-in-one:1.6.10
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
        bunkerity/bunkerweb-all-in-one:1.6.10
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
      image: bunkerity/bunkerweb-scheduler:1.6.10
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
      image: bunkerity/bunkerweb-scheduler:1.6.10
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
      image: bunkerity/bunkerweb-scheduler:1.6.10
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
        bunkerity/bunkerweb-all-in-one:1.6.10
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
        image: bunkerity/bunkerweb:1.6.10
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
        image: bunkerity/bunkerweb-scheduler:1.6.10
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
        image: bunkerity/bunkerweb:1.6.10
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
        image: bunkerity/bunkerweb:1.6.10
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
        bunkerity/bunkerweb-all-in-one:1.6.10
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
        image: bunkerity/bunkerweb:1.6.10
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
        image: bunkerity/bunkerweb-scheduler:1.6.10
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
        image: bunkerity/bunkerweb:1.6.10
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
        image: bunkerity/bunkerweb-scheduler:1.6.10
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
        image: bunkerity/bunkerweb-autoconf:1.6.10
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
        image: bunkerity/bunkerweb:1.6.10
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
        image: bunkerity/bunkerweb-scheduler:1.6.10
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

    如果它们已经在运行，我们可以重启调度器，让它在启用 IPv6 的情况下重新生成 NGINX 配置：

    ```shell
    systemctl restart bunkerweb-scheduler
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

| 值       | 描述                                                                                                                              |
| :------- | :-------------------------------------------------------------------------------------------------------------------------------- |
| `file`   | 将日志写入普通文件。外部轮转在 Linux 安装中由 `logrotate` 负责，在 Docker 中由您的容器日志驱动负责。Web UI 的日志查看器需要此项。 |
| `stderr` | 将日志写入标准错误（stderr）。容器化环境（如 `docker logs`）的标准做法。                                                          |
| `syslog` | 将日志发送到 syslog 服务器。使用此项时需要设置 `LOG_SYSLOG_ADDRESS`。                                                             |

使用 `file` 时，您还应该配置：

- `LOG_FILE_PATH`：当 `LOG_TYPES` 包含 `file` 时，日志文件写入的路径。

在使用 `syslog` 时，您还应该配置：

- `LOG_SYSLOG_ADDRESS`：syslog 服务器地址（例如 `udp://bw-syslog:514` 或 `/dev/log`）。
- `LOG_SYSLOG_TAG`：用于区分服务条目的唯一标签（例如 `bw-scheduler`）。

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

    **默认行为**：`LOG_TYPES="file"`。日志写入 `/var/log/bunkerweb/*.log`。轮转由安装到 `/etc/logrotate.d/bunkerweb` 的系统 `logrotate` 配置负责（每日轮转、保留 7 天，并通过 `copytruncate` 压缩）。

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
        image: bunkerity/bunkerweb:1.6.10
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
        image: bunkerity/bunkerweb-scheduler:1.6.10
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
        image: bunkerity/bunkerweb-ui:1.6.10
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
          --maxmemory-policy volatile-lru
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

=== "Kubernetes"

    **默认行为**：日志写入 `stderr`，可通过 `kubectl logs` 查看。

    **示例**：在 Helm chart 中启用内置的 syslog sidecar 以收集 Web UI 的日志（需要 BunkerWeb 1.6.7+）。

    ```yaml
    ui:
      logs:
        # 启用日志收集 sidecar
        enabled: true

        # 日志转发的 syslog 地址
        # 如果为空，将自动设置为 Sidecar 服务
        syslogAddress: ""

        # 用于日志收集的 syslog-ng 容器
        repository: docker.io/balabit/syslog-ng
        pullPolicy: Always
        tag: 4.8.0

        # 日志的持久化存储
        persistence:
          size: 5Gi
          storageClass: ""
    ```

    查看 [bunkerity/bunkerweb-helm 仓库](https://github.com/bunkerity/bunkerweb-helm) 中的完整 [logging.yaml 示例](https://github.com/bunkerity/bunkerweb-helm/blob/dev/examples/logging.yaml)。

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
    image: bunkerity/bunkerweb:1.6.10
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

## 出站流量的前向代理 {#forward-proxy-outgoing-traffic}

如果你的环境需要将出站 HTTP(S) 流量通过前向代理（例如企业代理或 Squid），可以使用标准的代理环境变量。BunkerWeb 没有专用配置。

**NGINX 本身不会使用这些变量来处理上游流量**，因此前向代理配置只影响发起出站请求的组件。实际使用中，请将其设置在 **Scheduler** 上，因为它负责 Let's Encrypt 证书续期、外部 API 调用以及 Webhook 等周期性任务。

常用变量如下：

- `HTTP_PROXY` / `HTTPS_PROXY`：代理 URL，可选带凭据。
- `NO_PROXY`：以逗号分隔的主机、域名或 CIDR 列表，用于绕过代理（根据集成调整：Docker/Swarm 的服务名、Kubernetes 的集群域名，或 Linux 上仅 localhost）。
- `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE`：可选，当代理使用自定义 CA 时需要。将 CA bundle 挂载到容器并指向该路径，以便 Python 请求验证 TLS（路径按基础镜像调整）。

!!! warning "NO_PROXY 对内部流量是必需的"
    如果省略内部网段或服务名，内部流量可能会走代理并失败。请根据集成调整列表（例如 Docker 服务名、Kubernetes 集群域名或 Linux 上仅 localhost）。

=== "Linux"

    将变量添加到 `/etc/bunkerweb/variables.env`。该文件会被两个服务加载，但只有 Scheduler 会使用它们：

    ```conf
    HTTP_PROXY=http://proxy.example.local:3128
    HTTPS_PROXY=http://proxy.example.local:3128
    NO_PROXY=localhost,127.0.0.1
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    ```

    重启服务以重新加载环境：

    ```shell
    sudo systemctl restart bunkerweb && \
    sudo systemctl restart bunkerweb-scheduler
    ```

=== "All-in-one"

    在创建容器时提供这些变量（如有需要请挂载 CA bundle）。All-in-one 镜像包含 Scheduler，因此可覆盖出站任务：

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -v /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro \
        -e HTTP_PROXY="http://proxy.example.local:3128" \
        -e HTTPS_PROXY="http://proxy.example.local:3128" \
        -e NO_PROXY="localhost,127.0.0.1" \
        -e REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt" \
        -e SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.10
    ```

    如果容器已存在，请重新创建以应用新的环境变量。

=== "Docker"

    将变量添加到 scheduler 容器：

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.10
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

=== "Docker autoconf"

    将变量应用到 scheduler 容器：

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.10
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

=== "Kubernetes"

    使用 `extraEnvs` 将变量添加到 Scheduler Pod。如需自定义 CA，可通过 `extraVolumes`/`extraVolumeMounts` 挂载并指向挂载路径：

    ```yaml
    scheduler:
      extraEnvs:
        - name: HTTP_PROXY
          value: "http://proxy.example.local:3128"
        - name: HTTPS_PROXY
          value: "http://proxy.example.local:3128"
        - name: NO_PROXY
          value: "localhost,127.0.0.1,.svc,.cluster.local"
        - name: REQUESTS_CA_BUNDLE
          value: "/etc/ssl/certs/ca-certificates.crt"
        - name: SSL_CERT_FILE
          value: "/etc/ssl/certs/ca-certificates.crt"
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息请参阅 [Swarm 集成文档](integrations.md#swarm)。**

    将变量添加到 scheduler 服务：

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.10
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

## 监控和报告

### 监控 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

监控插件让您可以收集和检索关于 BunkerWeb 的指标。启用它后，您的实例将开始收集与攻击、请求和性能相关的各种数据。然后，您可以通过定期调用 `/monitoring` API 端点或使用其他插件（如 Prometheus 导出器）来检索它们。

**功能列表**

- 启用各种 BunkerWeb 指标的收集
- 从 API 检索指标
- 与其他插件结合使用（例如 Prometheus 导出器）
- 专用 UI 页面监控您的实例

**设置列表**

| 设置                           | 默认  | 上下文 | 多个 | 描述                                                                     |
| ------------------------------ | ----- | ------ | ---- | ------------------------------------------------------------------------ |
| `USE_MONITORING`               | `yes` | 全局   | 否   | 启用 BunkerWeb 的监控。                                                  |
| `MONITORING_METRICS_DICT_SIZE` | `10M` | 全局   | 否   | 用于存储监控指标的字典大小。                                             |
| `MONITORING_IGNORE_URLS`       |       | 全局   | 否   | 以空格分隔的 URL 路径列表，用于排除在监控之外（例如 `/health /ready`）。 |

### Prometheus 导出器 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

### 报告 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

### S3 备份 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

## MCP 服务器

**BunkerWeb MCP 服务器**允许 **Claude Code** 和 **Claude Desktop** 等 AI 助手通过 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 管理您的 BunkerWeb 安装。

!!! warning "前提条件"
    MCP 服务器需要部署 **BunkerWeb 外部 API**（`bunkerity/bunkerweb-api`）。它专门通过此 API 与 BunkerWeb 通信。

### 功能

- **37 个工具**用于管理实例、服务、配置、封禁、插件、任务和缓存
- **MCP 资源**用于只读访问（`@config://global`、`@bans://active` 等）
- **多种传输方式**：Stdio、HTTP、WebSocket

### Docker Compose 示例

完整示例可在 [`examples/mcp-stack/`](https://github.com/bunkerity/bunkerweb/tree/v1.6.10/examples/mcp-stack) 中找到：

```yaml
services:
  bw-api:
    image: bunkerity/bunkerweb-api:1.6.10
    environment:
      API_TOKEN: "my-bearer-token-for-mcp"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
      FORWARDED_ALLOW_IPS: "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    networks:
      - bw-universe
      - bw-db
      - bw-mcp

  bw-mcp:
    image: bunkerity/bunkerweb-mcp:v0.1.0
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      BUNKERWEB_BASE_URL: "http://bw-api:8888"
      BUNKERWEB_API_TOKEN: "my-bearer-token-for-mcp"
      BUNKERWEB_LOG_LEVEL: INFO
    networks:
      - bw-mcp
```

### 在 Claude Code 中使用

=== "项目配置"

    在项目根目录添加 `.mcp.json` 文件（或在 `~/.claude/.mcp.json` 中进行全局配置）：

    ```json
    {
      "mcpServers": {
        "bunkerweb": {
          "type": "http",
          "url": "http://127.0.0.1:8080/mcp/"
        }
      }
    }
    ```

=== "CLI"

    ```bash
    # 通过 HTTP 添加 MCP 服务器
    claude mcp add --transport http bunkerweb --scope local http://localhost:8080/mcp

    # 或通过 stdio（本地安装）
    pip install mcp-bunkerweb
    claude mcp add --transport stdio bunkerweb --scope local -- mcp-bunkerweb
    ```

查询示例：

```
> 列出所有 BunkerWeb 实例
> 显示当前的封禁列表
> 分析 @config://global 并建议安全改进
```

### Kubernetes 集成

MCP 服务器可以使用官方 Helm chart 与 BunkerWeb 一起部署。完整示例可在 [`examples/mcp-integration.yaml`](https://github.com/bunkerity/bunkerweb-helm/blob/main/examples/mcp-integration.yaml) 中找到。

#### Helm 配置值

```yaml
mcp:
  # 启用 MCP 服务器
  enabled: true

  # 容器镜像配置
  repository: docker.io/bunkerity/bunkerweb-mcp
  tag: v0.1.0

  # MCP 服务器设置
  config:
    logLevel: "INFO"
    enableDnsRebindingProtection: true
    allowedHosts: "localhost,127.0.0.1,mcp.example.com"
    cacheEnabled: true

  # MCP 连接 BunkerWeb API 的认证凭据
  secrets:
    bunkerwebApiToken: "你的安全API令牌"

  # Ingress 配置（可选）
  ingress:
    enabled: false
    ingressClassName: "bunkerweb"
    serverName: "mcp.example.com"
    annotations:
      bunkerweb.io/AUTO_LETS_ENCRYPT: "yes"
      bunkerweb.io/USE_REVERSE_PROXY: "yes"
      bunkerweb.io/REVERSE_PROXY_URL: "/"
      bunkerweb.io/REVERSE_PROXY_HOST: "http://mcp-bunkerweb.bunkerweb.svc.cluster.local:8080"
      # 安全：仅限受信任的 IP 访问
      bunkerweb.io/USE_WHITELIST: "yes"
      bunkerweb.io/WHITELIST_IP: "10.0.0.0/8 192.168.0.0/16"
```

#### 部署

```bash
# 部署启用 MCP 的 BunkerWeb
helm install bunkerweb bunkerweb/bunkerweb -f mcp-integration.yaml

# 通过 port-forward 本地访问 MCP（安全推荐）
kubectl port-forward svc/mcp-bunkerweb 8080:8080

# 使用 http://localhost:8080/mcp 配置 Claude Code
```

!!! warning "安全"
    MCP 服务器的 `/mcp` 端点没有内置身份验证。请使用以下方式保护访问：

    - 通过 BunkerWeb 注解配置 **IP 白名单**（`USE_WHITELIST`、`WHITELIST_IP`）
    - 使用**网络策略**限制 Pod 间通信
    - 使用 **port-forward** 而不是外部暴露（推荐用于开发环境）

完整文档请访问 [BunkerWeb MCP 仓库](https://github.com/bunkerity/mcp-bunkerweb)。

## 迁移 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#migration-pro}

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

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#anti-ddos-pro}

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

## 用户管理器 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#user-manager-pro}

STREAM 支持 :x:

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="User Manager" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

**用户管理器**插件提供了一个强大的界面，用于管理系统内的用户帐户。

借助此插件，管理员可以轻松创建、更新和禁用用户帐户，管理用户角色，切换双因素身份验证 (2FA)，并查看详细的用户信息，例如上次登录时间戳和帐户状态（活动或非活动）。该插件在设计时考虑了安全性和易用性，简化了常规的用户管理任务，同时确保了合规性和可审计性。

### 功能

- **用户帐户操作：** 支持以 CSV/XLSX 格式导入，轻松创建、编辑和删除用户帐户。
- **基于角色的访问控制：** 分配和修改用户角色以管理权限和访问级别。
- **2FA 管理：** 根据管理决策禁用双因素身份验证。
- **全面的用户洞察：** 监控关键用户数据，包括上次登录时间、帐户创建日期以及活动/非活动状态。
- **审计日志记录：** 维护所有用户管理操作的审计跟踪，以增强安全性和合规性。

### 配置

| 设置                | 默认 | 上下文 | 多个 | 描述                             |
| ------------------- | ---- | ------ | ---- | -------------------------------- |
| `USERS_REQUIRE_2FA` | `no` | 全局   | 否   | 要求所有用户启用双因素身份验证。 |

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

## UI 单点登录 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#ui-single-sign-on-pro}

STREAM 支持 :x:

**UI 单点登录**插件通过读取放置在 Web UI 前方的外部认证代理（如 Authentik、Authelia、Keycloak 或 Traefik Forward Auth）设置的请求头，为 BunkerWeb Web 界面启用 SSO 认证。

管理员无需为 BunkerWeb 单独管理凭据，可以将认证委托给现有的身份提供方。认证代理完成用户登录后，在将请求转发到 BunkerWeb Web UI 之前注入身份头信息。

!!! danger "请求头伪造风险"
    SSO 请求头可以被任何客户端轻松伪造。您**必须**将 `UI_SSO_TRUSTED_IPS` 限制为认证代理的 IP 地址。如果此设置配置不正确，任何客户端都可以发送伪造的请求头并获取未授权访问——包括管理员权限。

    默认值 `127.0.0.1,::1` 仅信任本地回环地址。在 **Docker、Swarm 或 Kubernetes** 部署中，认证代理运行在具有独立 IP 的单独容器中。请将 `UI_SSO_TRUSTED_IPS` 设置为认证代理容器的实际 IP 或 CIDR（例如 `10.20.30.5` 或 `172.18.0.0/16`）。切勿设为 `0.0.0.0/0`。

### 功能

- **基于请求头的认证：** 从认证代理的请求头中读取用户名、邮箱、显示名称和分组信息。
- **分组到角色的映射：** 将 IdP 的分组映射到 BunkerWeb 的角色（admin、writer、reader）。
- **自动用户创建：** 首次 SSO 登录时自动创建本地帐户，可配置默认角色。
- **帐户关联：** 通过用户名或邮箱将 SSO 用户与现有本地帐户匹配。
- **可信 IP 强制执行：** 仅接受来自已配置 IP 地址或 CIDR 范围的 SSO 请求头。
- **回退到普通登录：** 当 SSO 请求头不存在时，可选允许密码登录。
- **登出重定向：** 本地登出后将用户重定向到 SSO 提供方的登出端点。

### 配置

| 设置                          | 默认                | 上下文 | 多个 | 描述                                                                        |
| ----------------------------- | ------------------- | ------ | ---- | --------------------------------------------------------------------------- |
| `USE_UI_SSO`                  | `no`                | 全局   | 否   | 启用或禁用 Web 界面的 UI 单点登录认证。                                     |
| `UI_SSO_HEADER_USERNAME`      | `X-User`            | 全局   | 否   | 包含已认证用户名的 HTTP 请求头。                                            |
| `UI_SSO_HEADER_EMAIL`         | `X-Email`           | 全局   | 否   | 包含用户邮箱地址的 HTTP 请求头。                                            |
| `UI_SSO_HEADER_GROUPS`        | `X-Groups`          | 全局   | 否   | 包含用户分组的 HTTP 请求头（逗号或空格分隔）。                              |
| `UI_SSO_HEADER_NAME`          | `X-Name`            | 全局   | 否   | 包含用户显示名称的 HTTP 请求头。                                            |
| `UI_SSO_TRUSTED_IPS`          | `127.0.0.1,::1`     | 全局   | 否   | 逗号分隔的可信 IP 地址或 CIDR 范围列表，允许发送 SSO 请求头。               |
| `UI_SSO_AUTO_CREATE_USERS`    | `yes`               | 全局   | 否   | 首次通过 SSO 认证时自动创建新用户。                                         |
| `UI_SSO_DEFAULT_ROLE`         | `reader`            | 全局   | 否   | 当无分组映射匹配时，分配给新 SSO 用户的默认角色。                           |
| `UI_SSO_GROUP_ADMIN`          |                     | 全局   | 否   | 授予 admin 角色的分组名称（最高优先级）。                                   |
| `UI_SSO_GROUP_WRITER`         |                     | 全局   | 否   | 授予 writer 角色的分组名称。                                                |
| `UI_SSO_GROUP_READER`         |                     | 全局   | 否   | 授予 reader 角色的分组名称。                                                |
| `UI_SSO_FALLBACK_TO_LOGIN`    | `yes`               | 全局   | 否   | 当 SSO 请求头不存在时，允许用户回退到普通登录。                             |
| `UI_SSO_UPDATE_USER_ON_LOGIN` | `yes`               | 全局   | 否   | 每次登录时从 SSO 请求头更新用户信息（邮箱、角色）。                         |
| `UI_SSO_ACCOUNT_LINKING`      | `username_or_email` | 全局   | 否   | 将 SSO 用户与本地帐户匹配的方式（`username_only` 或 `username_or_email`）。 |
| `UI_SSO_LOGOUT_REDIRECT_URL`  |                     | 全局   | 否   | 登出后重定向的 URL（例如 SSO 提供方的登出端点）。                           |

### 快速开始

1. 在 BunkerWeb Web UI 前放置认证代理（Authentik、Authelia、Keycloak 等）。
2. 启用插件：`USE_UI_SSO=yes`。
3. 确保认证代理设置了预期的请求头（`X-User`、`X-Email`、`X-Groups`、`X-Name`）——或通过 `UI_SSO_HEADER_*` 设置调整请求头名称。
4. 限制可信来源：将 `UI_SSO_TRUSTED_IPS` 设置为认证代理的 IP 地址。
5. 映射分组到角色：将 `UI_SSO_GROUP_ADMIN`、`UI_SSO_GROUP_WRITER` 和 `UI_SSO_GROUP_READER` 设置为与 IdP 分组名称匹配。

### 使用提示

- 在生产环境中设置 `UI_SSO_FALLBACK_TO_LOGIN=no` 以强制仅通过 SSO 访问。当保持默认值 `yes` 时，用户可以绕过 SSO 使用本地凭据登录，从而跳过身份提供方强制执行的 MFA 或会话策略。
- 保持 `UI_SSO_UPDATE_USER_ON_LOGIN` 的默认值（`yes`），以确保角色与 IdP 分组变更保持同步。
- 使用 `UI_SSO_ACCOUNT_LINKING=username_or_email` 时，首次 SSO 登录会自动关联用户名或邮箱匹配的现有本地帐户。如果您的 IdP 允许用户设置任意邮箱地址，请使用 `username_only` 以防止通过邮箱伪造接管帐户。

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#easy-resolve-pro}

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/45vX0WJqjxo" title="Easy Resolve" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

轻松解决插件让您可以直接从报告页面快速修复误报和重复出现的问题。它将引导式的“解决”操作转化为安全、范围受限的配置更新——无需手动编辑。

### 功能

- 从报告和报告详情中一键操作。
- 针对 ModSecurity、黑名单、DNSBL、速率限制、允许的 HTTP 方法和白名单/黑名单国家的上下文感知建议。
- 生成安全的 ModSecurity 排除规则或更新忽略列表。
- 在服务或全局范围内应用更改，并进行权限检查。
- 应用后可选择自动打开相关配置页面。

<figure markdown>
  ![概述](assets/img/easy-resolve.png){ align=center }
  <figcaption>报告页面 - 带有轻松解决功能</figcaption>
</figure>

## Load Balancer <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#load-balancer-pro}

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

## Custom Pages <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#custom-pages-pro}

Custom Pages 插件允许您将 BunkerWeb 的内置页面（错误页面、默认服务器页面和反机器人挑战页面）替换为您自己的自定义 HTML 或 Lua 模板。这使您能够在 BunkerWeb 提供的所有面向用户的页面上保持一致的品牌形象。

### 功能

- **每个服务的自定义错误页面**和**反机器人挑战页面**（验证码、JavaScript 检查、reCAPTCHA、hCaptcha、Turnstile、mCaptcha、Cap.js）。
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
| `CUSTOM_ANTIBOT_CAPJS_PAGE`      |      | multisite | 自定义反机器人 Cap.js 页面的绝对路径。         |

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

**Cap.js（`CUSTOM_ANTIBOT_CAPJS_PAGE`）：**

| 变量            | 类型   | 描述                     |
| --------------- | ------ | ------------------------ |
| `capjs_sitekey` | string | 您的 Cap.js 站点密钥     |
| `capjs_url`     | string | 您的 Cap.js 前端基础 URL |

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

    3. 重新加载 BunkerWeb 调度器，使其加载新的模板：

        ```bash
        sudo systemctl reload bunkerweb-scheduler
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
            image: bunkerity/bunkerweb:1.6.10
            # ... 其他设置（自定义页面无需在此处设置环境变量）

          bw-scheduler:
            image: bunkerity/bunkerweb-scheduler:1.6.10
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
                  image: bunkerity/bunkerweb-scheduler:1.6.10
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

## OpenID Connect <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#openid-connect-pro}

<p align="center">
  <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/0e4lcXTIIfs" title="OpenID Connect" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

**OpenID Connect** 插件（PRO）通过标准 OAuth 2.0 / OIDC **Authorization Code** 流程，在您的应用前增加单点登录（SSO）。

该插件运行在 BunkerWeb（NGINX/Lua）内部，并在 **access 阶段**强制执行认证，因此未认证请求会在到达上游之前被拦截。

### 请求流程如何工作

当浏览器访问受保护的 URL 时：

1. 若没有有效会话，BunkerWeb 会将用户重定向到身份提供方（IdP）。
2. IdP 完成用户认证后，会携带授权码重定向回 BunkerWeb 的 `OPENIDC_REDIRECT_URI`（默认：`/callback`）。
3. BunkerWeb 在 IdP 的 token endpoint 用授权码交换令牌。
4. 令牌会被校验（issuer、audience、过期时间、`iat` 容差，以及通过 JWKS 校验签名）。
5. 创建会话并将浏览器重定向回原始 URL。

```mermaid
sequenceDiagram
  participant B as 浏览器
  participant BW as BunkerWeb (OpenIDC)
  participant IdP as 身份提供方
  participant Up as 上游

  B->>BW: GET /protected
  alt 未认证
  BW-->>B: 302 重定向到 IdP 的 authorize 端点
  B->>IdP: 授权请求（nonce/PKCE 可选）
  IdP-->>B: 302 重定向到 /callback?code=...
  B->>BW: GET /callback?code=...
  BW->>IdP: Token 请求（授权码交换）
  IdP-->>BW: ID token + access token（+ refresh token）
  BW-->>B: 302 重定向回原始 URL
  end
  B->>BW: GET /protected（已认证）
  BW->>Up: 转发请求（+ 可选身份 Header）
  Up-->>BW: 响应
  BW-->>B: 响应
```

!!! warning "回调 URL 必须与 IdP 客户端配置一致"
    请在 IdP 侧注册完整的回调 URL（协议 + 主机 + 路径）。例如默认配置下为：`https://app.example.com/callback`。

### 设置（说明）

!!! info "必需设置"
    至少需要配置 `OPENIDC_DISCOVERY` 与 `OPENIDC_CLIENT_ID`，插件才能工作。

#### 基础启用

- `USE_OPENIDC`（默认：`no`）：启用/禁用该站点的 OpenID Connect 认证。

#### 身份提供方（IdP）+ 客户端注册

- `OPENIDC_DISCOVERY`：discovery URL（例如 `https://idp.example.com/.well-known/openid-configuration`）。
- `OPENIDC_CLIENT_ID`：在 IdP 注册的 OAuth 2.0 客户端 ID。
- `OPENIDC_CLIENT_SECRET`：OAuth 2.0 客户端密钥（`basic`、`post`、`secret_jwt` 使用）。

#### 回调 / 重定向

- `OPENIDC_REDIRECT_URI`（默认：`/callback`）：IdP 认证完成后回调的路径（必须在 IdP 注册）。

#### Scope 与授权参数

- `OPENIDC_SCOPE`（默认：`openid email profile`）：以空格分隔的 scope 列表。
- `OPENIDC_AUTHORIZATION_PARAMS`：额外授权参数，使用逗号分隔 `key=value`。

#### 安全加固

- `OPENIDC_USE_NONCE`（默认：`yes`）：在授权请求中加入 nonce。
- `OPENIDC_USE_PKCE`（默认：`no`）：为 Authorization Code 流程启用 PKCE。
- `OPENIDC_IAT_SLACK`（默认：`120`）：令牌校验允许的时钟偏差（秒）。
- `OPENIDC_ACCEPT_UNSUPPORTED_ALG`（默认：`no`）：接受不支持算法签名的令牌（不推荐）。
- `OPENIDC_FORCE_REAUTHORIZE`（默认：`no`）：每次请求都强制重新授权（仅调试）。

#### 基于 claim 的访问控制（ACL）

Claim 是 OIDC 令牌中描述用户属性的键值对（例如 `email`、`groups`、`sub`）。ACL 功能允许您根据特定的 claim 值限制访问。

| 设置                      | 默认  | 上下文    | 多个 | 描述                                                                                                      |
| ------------------------- | ----- | --------- | ---- | --------------------------------------------------------------------------------------------------------- |
| `OPENIDC_USE_ACL`         | `no`  | multisite | 否   | 在 OIDC 认证后启用基于 claim 的访问控制。只有 claim 匹配配置规则的用户才能获得访问权限。                  |
| `OPENIDC_ACL_MATCH_MODE`  | `all` | multisite | 否   | 多条 ACL 规则的评估方式。`all` = 所有规则必须通过（AND）。`any` = 至少一条规则通过即可（OR）。            |
| `OPENIDC_ACL_DENIED_URL`  |       | multisite | 否   | ACL 拒绝访问时重定向的 URL。如果为空，返回 403 Forbidden 响应。                                           |
| `OPENIDC_ACL_CLAIM`       |       | multisite | 是   | 要检查的 OIDC claim 名称（例如 `groups`、`email`、`sub`）。与 `OPENIDC_ACL_CLAIM_VALUE` 成对使用。        |
| `OPENIDC_ACL_CLAIM_VALUE` |       | multisite | 是   | claim 的期望值。对于数组类型的 claim（如 `groups`），检查成员关系。对于字符串类型的 claim，检查严格相等。 |

!!! tip "多条 ACL 规则"
    使用数字后缀定义多条规则。每对 `OPENIDC_ACL_CLAIM` / `OPENIDC_ACL_CLAIM_VALUE` 构成一条规则：

    ```yaml
    OPENIDC_USE_ACL: "yes"
    OPENIDC_ACL_MATCH_MODE: "any"
    OPENIDC_ACL_CLAIM: "groups"
    OPENIDC_ACL_CLAIM_VALUE: "engineering"
    OPENIDC_ACL_CLAIM_1: "email"
    OPENIDC_ACL_CLAIM_VALUE_1: "admin@example.com"
    ```

    当 `OPENIDC_ACL_MATCH_MODE=any` 时，用户属于 `engineering` 分组**或**邮箱为 `admin@example.com` 即可获得访问权限。当设为 `all` 时，两个条件必须同时满足。

#### 会话/令牌生命周期

- `OPENIDC_REFRESH_SESSION_INTERVAL`：静默重新认证/刷新会话的间隔（秒，空值禁用）。
- `OPENIDC_ACCESS_TOKEN_EXPIRES_IN`（默认：`3600`）：当 IdP 未返回时使用的 access token 默认有效期。
- `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY`（默认：`yes`）：access token 过期时使用 refresh token 自动续期。

#### Token endpoint 认证设置

- `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD`（默认：`basic`）：`basic`、`post`、`secret_jwt`、`private_key_jwt`。
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY`：使用 `private_key_jwt` 时必需。
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`：`private_key_jwt` 可选 `kid`。
- `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN`：JWT 断言有效期（秒）。

#### 登出行为

- `OPENIDC_LOGOUT_PATH`（默认：`/logout`）：由 BunkerWeb 处理的本地登出路径。
- `OPENIDC_REVOKE_TOKENS_ON_LOGOUT`（默认：`no`）：登出时在 IdP 侧吊销令牌。
- `OPENIDC_REDIRECT_AFTER_LOGOUT_URI`：本地登出后的跳转（空值使用 IdP 默认行为）。
- `OPENIDC_POST_LOGOUT_REDIRECT_URI`：IdP 登出完成后的跳转（若 IdP 支持）。

#### 到 IdP 的连接与 TLS

- `OPENIDC_TIMEOUT_CONNECT|SEND|READ`（默认：每项 `10000` ms）：访问 IdP 的 HTTP 超时。
- `OPENIDC_SSL_VERIFY`（默认：`yes`）：校验 IdP TLS 证书。
- `OPENIDC_KEEPALIVE`（默认：`yes`）：IdP 连接 keepalive。
- `OPENIDC_HTTP_PROXY` / `OPENIDC_HTTPS_PROXY`：访问 IdP 的代理配置。

#### 向上游传递身份

- `OPENIDC_USER_HEADER`（默认：`X-User`）：传递到上游的身份 header（空值禁用）。
- `OPENIDC_USER_HEADER_CLAIM`（默认：`sub`）：用于生成 header 值的 claim。
- `OPENIDC_DISPLAY_CLAIM`（默认：`preferred_username`）：用于日志/指标展示的 claim。

#### 缓存

- `OPENIDC_DISCOVERY_DICT_SIZE`（默认：`1m`）：discovery 缓存的 shared dict 大小。
- `OPENIDC_JWKS_DICT_SIZE`（默认：`1m`）：JWKS 缓存的 shared dict 大小。

!!! tip "Redis 会话存储"
    当全局配置 `USE_REDIS=yes` 且 Redis 可用时，OpenIDC 插件会把会话存储到 Redis 而不是 Cookie（若 Redis 暂不可用会自动回退到 Cookie）。这是多实例/高可用部署的推荐模式。

### Discovery + JWKS 缓存

插件通过 `OPENIDC_DISCOVERY`（IdP 的 `.well-known/openid-configuration`）发现各端点，然后获取并缓存 JWKS，用于校验令牌签名。

Discovery/JWKS 数据会缓存在 NGINX shared dict 中。如果您有很多租户/IdP 或非常大的密钥集合，可增大：

- `OPENIDC_DISCOVERY_DICT_SIZE`（global）
- `OPENIDC_JWKS_DICT_SIZE`（global）

### 会话（Cookie vs Redis）

默认情况下，会话以安全 Cookie 的形式存储，由 OpenID Connect 库管理。

当 `USE_REDIS=yes` 且 Redis 配置正确时，插件会自动切换为 **Redis 会话**（Redis 临时不可用时会自动回退到 Cookie）。推荐用于负载均衡/高可用场景，并可避免令牌较大时的 Cookie 大小限制。

### 向上游传递用户身份

如果设置了 `OPENIDC_USER_HEADER`（默认：`X-User`），插件会从某个 claim 中提取值注入到 header（默认：`OPENIDC_USER_HEADER_CLAIM=sub`）。

重要的安全行为：

- 插件会**清除所有传入**的同名 header（`OPENIDC_USER_HEADER`），防止客户端伪造。
- 如果找不到配置的 claim，则不会设置 header。
- 将 `OPENIDC_USER_HEADER` 设为空值可禁用身份传递。

!!! tip "选择 claim"
    优先使用令牌中稳定存在的标识（例如 `sub`、`email`、`preferred_username`）。claim 先从 ID token 读取，不存在时再从 userinfo 读取（若有）。

### 登出

登出请求在 `OPENIDC_LOGOUT_PATH`（默认：`/logout`）处理。

- 如需登出时在 IdP 侧吊销令牌，请设置 `OPENIDC_REVOKE_TOKENS_ON_LOGOUT=yes`。
- 使用 `OPENIDC_REDIRECT_AFTER_LOGOUT_URI` 与 `OPENIDC_POST_LOGOUT_REDIRECT_URI` 控制登出后的跳转。

### Token endpoint 认证

大多数 IdP 使用默认的 `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD=basic`（HTTP Basic 携带 client secret）即可工作。也支持：

- `post`
- `secret_jwt`
- `private_key_jwt`（需要 `OPENIDC_CLIENT_RSA_PRIVATE_KEY`，可选 `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`）

### 最小配置示例

每个受保护服务至少需要：

- `USE_OPENIDC=yes`
- `OPENIDC_DISCOVERY=...`
- `OPENIDC_CLIENT_ID=...`
- `OPENIDC_CLIENT_SECRET=...`（或 `private_key_jwt` 的 JWT 密钥配置）

常见的加固/调优选项：

- `OPENIDC_USE_NONCE=yes`（默认）
- `OPENIDC_USE_PKCE=yes`
- 若存在时钟偏差，调整 `OPENIDC_IAT_SLACK=...`
- 根据 IdP 延迟调整 `OPENIDC_TIMEOUT_CONNECT|SEND|READ`
- `OPENIDC_SSL_VERIFY=yes`（默认）

### 故障排除

- **403 且显示 "Authentication failed"**：常见原因是 discovery URL 错误、IdP 侧回调 URL 不匹配或 IdP 不可达。
- **时钟偏差 / "token not yet valid"**：确保启用 NTP；必要时调整 `OPENIDC_IAT_SLACK`。
- **未注入用户 header**：确认 `OPENIDC_USER_HEADER_CLAIM` 指定的 claim 在 ID token/userinfo 中存在。
- **多实例部署**：启用 `USE_REDIS=yes` 并配置 `REDIS_HOST`（或 Sentinel）以共享会话。

## LDAP SSO <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#ldap-sso-pro}

STREAM 支持 :x:

**LDAP SSO** 插件为 BunkerWeb 服务添加基于 LDAP 的单点登录功能。它提供登录表单、通过 LDAP 目录认证用户、创建会话，并可选地通过可配置的请求头将已认证的用户名传递给上游。

该插件支持两种认证模式：

- **搜索后绑定模式**（推荐，也称为"企业搜索模式"）：服务帐户在目录中搜索用户，然后以找到的 DN 绑定以验证密码。当设置了 `LDAP_USER_SEARCH_BASE_DN` 时启用。
- **直接绑定模式**：通过模板（`LDAP_USER_DN_TEMPLATE`）构造用户 DN 并直接绑定。当未配置搜索模式时作为回退使用。

### 功能

- **LDAP/LDAPS/STARTTLS：** 支持通过明文 LDAP、LDAPS（从连接开始即 TLS）或 STARTTLS 升级进行连接。
- **搜索后绑定模式：** 服务帐户执行用户发现，支持可配置的搜索基础、过滤器、范围以及大小/时间限制。
- **直接绑定回退：** 当不需要搜索模式时，基于 DN 模板进行认证。
- **授权过滤器：** 可选的额外 LDAP 过滤器，用于在基本认证之外进一步限制访问。
- **连接池：** 支持 keepalive，具有可配置的池大小和超时，减少 LDAP 往返。
- **会话管理：** 可配置的 TTL，支持自动会话清理。
- **用户头转发：** 通过可配置的请求头（默认：`X-User`）将已认证用户名传递给上游。
- **登录/登出路径：** 专用的认证和会话终止端点。

!!! danger "默认情况下凭据以明文传输"
    使用默认设置（`LDAP_LDAPS=no`、`LDAP_STARTTLS=no`）时，用户密码会以明文传输到 LDAP 服务器。**在生产环境中务必启用 `LDAP_LDAPS=yes`（配合 `LDAP_PORT=636`）或 `LDAP_STARTTLS=yes`。** 保持 `LDAP_SSL_VERIFY=yes` 以防止 TLS 降级攻击。

### 配置

**核心设置**

| 设置              | 默认    | 上下文    | 多个 | 描述                                                        |
| ----------------- | ------- | --------- | ---- | ----------------------------------------------------------- |
| `USE_LDAP`        | `no`    | multisite | 否   | 启用或禁用 LDAP SSO 认证。                                  |
| `LDAP_HOST`       |         | multisite | 否   | LDAP 服务器主机名或 IP 地址。                               |
| `LDAP_PORT`       | `389`   | multisite | 否   | LDAP 服务器端口（389 用于 LDAP/STARTTLS，636 用于 LDAPS）。 |
| `LDAP_LDAPS`      | `no`    | multisite | 否   | 使用 LDAPS（从连接开始即 TLS）。                            |
| `LDAP_STARTTLS`   | `no`    | multisite | 否   | 在 LDAP 连接上使用 STARTTLS 升级。                          |
| `LDAP_SSL_VERIFY` | `yes`   | multisite | 否   | 验证服务器 TLS 证书。                                       |
| `LDAP_TIMEOUT`    | `10000` | multisite | 否   | LDAP 套接字超时（毫秒）。                                   |

**连接池**

| 设置                       | 默认    | 上下文    | 多个 | 描述                                 |
| -------------------------- | ------- | --------- | ---- | ------------------------------------ |
| `LDAP_KEEPALIVE_TIMEOUT`   | `60000` | multisite | 否   | LDAP keepalive 超时（毫秒）。        |
| `LDAP_KEEPALIVE_POOL_SIZE` | `10`    | multisite | 否   | LDAP keepalive 连接池大小。          |
| `LDAP_KEEPALIVE_POOL_NAME` |         | multisite | 否   | 可选的自定义 LDAP keepalive 池名称。 |

**企业搜索模式**

| 设置                              | 默认                                                                                                                    | 上下文    | 多个 | 描述                                                                                                  |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | --------- | ---- | ----------------------------------------------------------------------------------------------------- |
| `LDAP_BIND_DN`                    |                                                                                                                         | multisite | 否   | 用于执行 LDAP 用户搜索的服务帐户 DN。                                                                 |
| `LDAP_BIND_PASSWORD`              |                                                                                                                         | multisite | 否   | LDAP 绑定 DN 服务帐户的密码。                                                                         |
| `LDAP_USER_SEARCH_BASE_DN`        |                                                                                                                         | multisite | 否   | 用户发现搜索的基础 DN（设置此项启用企业搜索模式）。                                                   |
| `LDAP_USER_SEARCH_FILTER`         | `(&(objectClass=person)(\|(uid={username})(mail={username})(sAMAccountName={username})(userPrincipalName={username})))` | multisite | 否   | LDAP 用户搜索过滤器模板。使用 `{username}` 占位符。                                                   |
| `LDAP_AUTHZ_FILTER`               |                                                                                                                         | multisite | 否   | 可选的额外 LDAP 授权过滤器（与用户搜索过滤器进行 AND 运算）。                                         |
| `LDAP_USER_SEARCH_SCOPE`          | `subtree`                                                                                                               | multisite | 否   | LDAP 搜索范围：`base`、`onelevel` 或 `subtree`。                                                      |
| `LDAP_USER_SEARCH_DEREF_ALIASES`  | `always`                                                                                                                | multisite | 否   | LDAP 别名解引用模式：`always`、`never`、`in_searching` 或 `finding_base`。                            |
| `LDAP_USER_SEARCH_SIZE_LIMIT`     | `10`                                                                                                                    | multisite | 否   | 用户搜索返回的最大 LDAP 条目数。                                                                      |
| `LDAP_USER_SEARCH_TIME_LIMIT`     | `10`                                                                                                                    | multisite | 否   | LDAP 用户搜索的最大时间（秒）。                                                                       |
| `LDAP_USER_SEARCH_ATTRIBUTES`     | `dn`                                                                                                                    | multisite | 否   | 用户搜索期间请求的属性（空格分隔）。                                                                  |
| `LDAP_USER_SEARCH_DN_FIELD`       | `object_name`                                                                                                           | multisite | 否   | 搜索响应中用于提取用户 DN 的字段名。默认的 `object_name` 是底层 LDAP 库返回的 DN 字段；通常无需更改。 |
| `LDAP_USER_SEARCH_REQUIRE_UNIQUE` | `yes`                                                                                                                   | multisite | 否   | 认证用户前要求搜索结果恰好为一条。                                                                    |

**直接绑定模式**

| 设置                    | 默认                                         | 上下文    | 多个 | 描述                                                      |
| ----------------------- | -------------------------------------------- | --------- | ---- | --------------------------------------------------------- |
| `LDAP_USER_DN_TEMPLATE` | `uid={username},ou=people,dc=example,dc=com` | multisite | 否   | 直接绑定使用的用户 DN 模板。设置时必须包含 `{username}`。 |

**会话和路径**

| 设置                         | 默认                 | 上下文    | 多个 | 描述                                         |
| ---------------------------- | -------------------- | --------- | ---- | -------------------------------------------- |
| `LDAP_USERNAME_REGEX`        | `^[A-Za-z0-9@._-]+$` | multisite | 否   | 用于验证提交用户名的 PCRE 正则表达式。       |
| `LDAP_LOGIN_PATH`            | `/ldap/login`        | multisite | 否   | LDAP 插件暴露的登录页面路径。                |
| `LDAP_LOGOUT_PATH`           | `/ldap/logout`       | multisite | 否   | LDAP 插件暴露的登出路径。                    |
| `LDAP_SESSION_TTL`           | `3600`               | multisite | 否   | LDAP 会话有效期（秒）。                      |
| `LDAP_REALM`                 | `LDAP SSO`           | multisite | 否   | LDAP 登录表单上显示的认证领域。              |
| `LDAP_USER_HEADER`           | `X-User`             | multisite | 否   | 传递已认证用户名到上游的请求头（空值禁用）。 |
| `LDAP_REDIRECT_AFTER_LOGIN`  | `/`                  | multisite | 否   | 登录成功且无重定向目标时的回退相对路径。     |
| `LDAP_REDIRECT_AFTER_LOGOUT` | `/`                  | multisite | 否   | 登出后重定向的相对路径。                     |

### 快速开始

1. 为每个受保护的服务设置最小值：
    - `USE_LDAP=yes`
    - `LDAP_HOST=ldap.example.com`
2. 对于企业搜索模式（推荐），还需设置：
    - `LDAP_BIND_DN=cn=readonly,dc=example,dc=com`
    - `LDAP_BIND_PASSWORD=secret`（生产环境中请使用 [Docker secrets](integrations.md#docker)）
    - `LDAP_USER_SEARCH_BASE_DN=ou=people,dc=example,dc=com`
3. 对于直接绑定模式，请调整 `LDAP_USER_DN_TEMPLATE` 以匹配您的目录结构。
4. 可选地使用 `LDAP_AUTHZ_FILTER` 限制访问（例如 `(memberOf=cn=allowed,ou=groups,dc=example,dc=com)`）。

### 使用提示

- 优先使用搜索后绑定模式而非直接绑定——它支持跨多个属性（uid、mail、sAMAccountName、UPN）的灵活用户查找。
- 在生产环境中使用 LDAPS（`LDAP_LDAPS=yes`）或 STARTTLS（`LDAP_STARTTLS=yes`）以加密传输中的凭据。
- 启用 LDAPS（`LDAP_LDAPS=yes`）时，请记得同时设置 `LDAP_PORT=636`。端口不会自动更改。
- 除非使用自签名证书进行测试，否则保持 `LDAP_SSL_VERIFY=yes`。
- 调整 `LDAP_KEEPALIVE_POOL_SIZE` 以匹配预期的并发用户量，减少 LDAP 连接开销。
- 将 `LDAP_USER_HEADER` 设为空值可禁用向上游传递身份信息。

## OpenAPI Validator <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#openapi-validator-pro}

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/3oZOO1XdSlc" title="OpenAPI Validator" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

**OpenAPI Validator** 插件通过根据 OpenAPI / Swagger 规范验证传入请求来执行您的 API 合约。它确保请求的路径存在，HTTP 方法是被允许的，并可选地根据架构定义验证查询、请求头、cookie 和路径参数。

### 工作原理

1. 计划任务 (`openapi-download.py`) 从 URL 或文件获取 OpenAPI 文档并将其缓存到磁盘（默认每小时一次）。
2. 在 NGINX 初始化时，插件从缓存的规范中编译路由并将其存储在共享的内部存储中。
3. 在请求处理期间，插件将请求与编译的路由进行匹配并执行验证。

### 功能

- 路径和方法验证，当方法不被允许时返回 `405` 响应。
- 可选的查询、请求头、cookie 和路径参数验证。
- 通过 `OPENAPI_BASE_PATH` 覆盖基础路径或从规范中自动推导。
- 允许或拒绝指向规范中未列出路径的请求。
- 可配置的忽略列表，用于文档或规范文件等端点。
- 缓存的规范每小时刷新一次，不会阻塞请求。

### 配置

| 设置                         | 默认值                               | 上下文    | 多选 | 描述                                                     |
| ---------------------------- | ------------------------------------ | --------- | ---- | -------------------------------------------------------- |
| `USE_OPENAPI_VALIDATOR`      | `no`                                 | multisite | 否   | 为该站点启用 OpenAPI 路由验证。                          |
| `OPENAPI_SPEC`               |                                      | multisite | 否   | JSON/YAML 格式的 OpenAPI 文档的绝对路径或 HTTP(S) URL。  |
| `OPENAPI_BASE_PATH`          |                                      | multisite | 否   | 可选的基础路径前缀，将添加到规范中的每个路径前。         |
| `OPENAPI_ALLOW_UNSPECIFIED`  | `no`                                 | multisite | 否   | 允许指向规范中未列出路径的请求。                         |
| `OPENAPI_ALLOW_INSECURE_URL` | `no`                                 | multisite | 否   | 允许通过普通 HTTP 获取 OpenAPI 规范（不推荐）。          |
| `OPENAPI_IGNORE_URLS`        | `^/docs$ ^/redoc$ ^/openapi\\.json$` | multisite | 否   | 以空格分隔的 URL 正则表达式列表，用于绕过 OpenAPI 验证。 |
| `OPENAPI_MAX_SPEC_SIZE`      | `2M`                                 | global    | 否   | 允许的 OpenAPI 文档最大大小（接受后缀 k/M/G）。          |
| `OPENAPI_VALIDATE_PARAMS`    | `yes`                                | multisite | 否   | 根据规范验证查询、请求头、cookie 和路径参数。            |

### 行为说明

- `OPENAPI_SPEC` 可以是本地文件或 HTTPS URL。除非 `OPENAPI_ALLOW_INSECURE_URL=yes`，否则 HTTP URL 将被屏蔽。
- 如果 `OPENAPI_BASE_PATH` 为空，插件将从 `servers[*].url` (OpenAPI 3) 或 `basePath` (Swagger 2) 中推导基础路径（如果存在）。
- 当为同一路径定义了 `GET` 时，接受 `HEAD` 请求，且路径匹配容忍末尾斜杠。
- 当规范中缺少某个路径且 `OPENAPI_ALLOW_UNSPECIFIED=no` 时，请求将被拒绝并返回配置的拒绝状态。
- 参数验证失败将被拒绝，且仅记录第一个错误以保持日志简洁。

### 快速开始

为每个受保护的服务设置最小值：

- `USE_OPENAPI_VALIDATOR=yes`
- `OPENAPI_SPEC=/path/to/openapi.yaml` (或 `https://...`)

（可选）在部署期间允许未知路径：

- `OPENAPI_ALLOW_UNSPECIFIED=yes`

## Cache <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#cache-pro}

STREAM 支持 :x:

Cache PRO 插件使用 NGINX `proxy_cache*` 指令在反向代理层启用响应缓存。它适合用于吸收对可缓存内容的重复读取、在流量高峰期保护上游服务，以及在后端短暂故障期间提供陈旧缓存内容。

**工作原理**

1. 每个全局 `CACHE_PATH*` 值都会在 HTTP 上下文中生成一条 `proxy_cache_path` 指令。
2. 只有当 `CACHE_ZONE` 设置为 `CACHE_PATH*` 中声明的某个区域时，服务才会启用缓存。
3. 服务级设置随后控制缓存键、bypass/no-cache 条件、锁、stale 使用方式以及有效期规则。
4. 如果设置了 `CACHE_HEADER`，BunkerWeb 会添加一个响应头，公开 `$upstream_cache_status`，例如 `HIT`、`MISS`、`BYPASS`、`EXPIRED` 或 `STALE`。

**功能列表**

- 具有可配置缓存路径和区域的反向代理响应缓存。
- 通过 `CACHE_ZONE` 按服务启用缓存。
- 可选响应头，使用 `$upstream_cache_status` 暴露缓存状态。
- 针对 bypass、no-cache、缓存键、方法、锁、stale 和重新验证的细粒度控制。
- 通过重复的 `CACHE_VALID*` 设置定义多条缓存有效期规则。

**设置列表**

| 设置                        | 默认                              | 上下文    | 多个 | 描述                                                 |
| --------------------------- | --------------------------------- | --------- | ---- | ---------------------------------------------------- |
| `CACHE_PATH`                |                                   | 全局      | 是   | 缓存路径及其参数。                                   |
| `CACHE_ZONE`                |                                   | multisite | 否   | 要使用的缓存区域名称（在 `CACHE_PATH` 设置中定义）。 |
| `CACHE_HEADER`              | `X-Cache`                         | multisite | 否   | 添加一个暴露缓存状态的响应头。                       |
| `CACHE_BACKGROUND_UPDATE`   | `no`                              | multisite | 否   | 启用或禁用后台缓存更新。                             |
| `CACHE_BYPASS`              |                                   | multisite | 否   | 用于判断是否绕过缓存的变量列表。                     |
| `CACHE_NO_CACHE`            | `$http_pragma$http_authorization` | multisite | 否   | 当变量被设置时，不将响应写入缓存。                   |
| `CACHE_KEY`                 | `$scheme$proxy_host$request_uri`  | multisite | 否   | 用于标识缓存对象的键。                               |
| `CACHE_CONVERT_HEAD_TO_GET` | `yes`                             | multisite | 否   | 缓存时将 HEAD 请求转换为 GET。                       |
| `CACHE_LOCK`                | `no`                              | multisite | 否   | 填充缓存时锁定并发请求。                             |
| `CACHE_LOCK_AGE`            | `5s`                              | multisite | 否   | 缓存锁持续该时间后，将请求转发到上游。               |
| `CACHE_LOCK_TIMEOUT`        | `5s`                              | multisite | 否   | 等待缓存锁超过该时间后，将请求转发到上游。           |
| `CACHE_METHODS`             | `GET HEAD`                        | multisite | 否   | 仅缓存这些 HTTP 方法对应的响应。                     |
| `CACHE_MIN_USES`            | `1`                               | multisite | 否   | 在写入缓存前，相同请求需要出现的次数。               |
| `CACHE_REVALIDATE`          | `no`                              | multisite | 否   | 通过条件请求向上游重新验证过期缓存项。               |
| `CACHE_USE_STALE`           | `off`                             | multisite | 否   | 决定何时允许返回陈旧缓存内容。                       |
| `CACHE_VALID`               | `10m`                             | multisite | 是   | 定义缓存时长，可选附带一个或多个 HTTP 状态码。       |

**使用示例**

1. 定义一个全局缓存路径和区域：

   ```yaml
   CACHE_PATH: "/var/cache/bunkerweb/proxy levels=1:2 keys_zone=htmlcache:10m max_size=1g inactive=60m use_temp_path=off"
   ```

2. 启用反向代理并将该区域绑定到一个服务：

   ```yaml
   www.example.com_USE_REVERSE_PROXY: "yes"
   www.example.com_REVERSE_PROXY_HOST: "http://app:8080"
   www.example.com_CACHE_ZONE: "htmlcache"
   www.example.com_CACHE_HEADER: "X-Cache"
   www.example.com_CACHE_VALID: "200 301 302 10m"
   www.example.com_CACHE_VALID_1: "404 1m"
   ```

3. 根据需要添加可选控制项：

   ```yaml
   www.example.com_CACHE_BYPASS: "$cookie_nocache $arg_nocache"
   www.example.com_CACHE_NO_CACHE: "$http_pragma $http_authorization"
   www.example.com_CACHE_LOCK: "yes"
   www.example.com_CACHE_BACKGROUND_UPDATE: "yes"
   www.example.com_CACHE_USE_STALE: "error timeout updating http_500 http_502 http_503 http_504"
   ```

!!! info "重要行为"
    - 此插件仅适用于反向代理流量。它不会缓存直接由本地静态文件提供的内容，也不适用于 stream/TCP 服务。
    - `CACHE_ZONE` 必须通过 `keys_zone=<名称>:<大小>` 匹配某个 `CACHE_PATH*` 中定义的区域。
    - 如果某个服务的 `CACHE_ZONE` 为空，则不会为该服务应用缓存指令。
    - 对于重复值，请使用数字后缀，例如 `CACHE_PATH_1`、`CACHE_PATH_2`、`CACHE_VALID_1` 和 `CACHE_VALID_2`。
    - 认证流量或用户特定流量通常不应进入缓存，除非 `CACHE_KEY` 明确根据该状态变化。
    - `CACHE_LOCK=yes` 和 `CACHE_BACKGROUND_UPDATE=yes` 有助于减少对源站的瞬时冲击。

## ACME <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#acme}

STREAM 支持 :white_check_mark:

**ACME** 插件通过 ACME 协议提供高级证书管理功能，支持自定义证书颁发机构（Step CA、Vault PKI、Sectigo、Google Trust Services 等）。它作为内置 Let's Encrypt 插件的补充，增加了自定义 CA 支持、DNS-01 和 TLS-ALPN-01 挑战、通配符证书、带过期告警的证书监控、证书透明度日志监控以及增强的 OCSP Stapling。

!!! tip "何时使用 ACME 而非内置 Let's Encrypt 插件"
    如果您只需要使用 HTTP-01 挑战的 Let's Encrypt 证书，内置的 Let's Encrypt 插件（`AUTO_LETS_ENCRYPT=yes`）即可满足需求。当您需要自定义 CA、DNS-01 或 TLS-ALPN-01 挑战、通配符证书，或需要带告警的证书监控时，请使用 ACME 插件。

### 功能

- **自定义 CA 支持：** 使用任何兼容 ACME 的证书颁发机构，不限于 Let's Encrypt。
- **多种挑战类型：** HTTP-01、DNS-01（通配符必需）和 TLS-ALPN-01。
- **DNS 提供商集成：** 内置支持 Cloudflare、Route53、DigitalOcean、OVH 等。
- **外部帐户绑定（EAB）：** 适用于需要预注册密钥的 CA（Sectigo、Google Trust Services）。
- **通配符证书：** 通过 DNS-01 挑战实现。
- **证书监控：** 跟踪所有受管证书（包括 OSS Let's Encrypt）的过期时间，可配置告警阈值。
- **过期告警：** 当证书即将到期时，通过 webhook 或邮件发送告警。
- **证书透明度监控：** 查询 crt.sh 以检测对您域名的未授权证书签发。
- **增强的 OCSP Stapling：** 主动获取和缓存 OCSP 响应。
- **可配置的密钥类型：** ECDSA（256/384）或 RSA（2048/4096）。

### 前提条件

#### HTTP-01 挑战需要 `LETS_ENCRYPT_PASSTHROUGH=yes`

当使用 `ACME_CHALLENGE=http`（默认值）时，您**必须**在同一服务上设置 `LETS_ENCRYPT_PASSTHROUGH=yes`。

BunkerWeb 的核心 Let's Encrypt 插件包含一个 NGINX location 块和一个用于 `/.well-known/acme-challenge/` 的 Lua access 处理器。由于 NGINX location 块在任何 Lua 插件代码运行之前匹配，它会在 ACME PRO 能够处理之前拦截挑战请求。设置 `LETS_ENCRYPT_PASSTHROUGH=yes` 可以禁用这两个机制，使 ACME PRO 能够正确处理 HTTP-01 挑战令牌。

此设置**仅在 HTTP-01 时需要**。DNS-01 和 TLS-ALPN-01 挑战不受影响。

#### 上游 ACME 透传（`ACME_PASSTHROUGH`）

如果 BunkerWeb 背后的上游服务器已经运行自己的 ACME 客户端，并应由其自行处理 HTTP-01 验证，请在该服务上设置 `ACME_PASSTHROUGH=yes`。此时 ACME PRO 将不再渲染 `/.well-known/acme-challenge/` location 块，也不会在 `access` 阶段将挑战路径加入白名单，从而让上游提供的验证文件原样到达 CA。

当您希望 ACME PRO 自行签发和续期证书时，请将 `ACME_PASSTHROUGH` 保持为 `no`（默认值）。ACME PRO 管理服务的标准 HTTP-01 组合是：`LETS_ENCRYPT_PASSTHROUGH=yes`（让 OSS 核心 Let's Encrypt 插件让出其挑战 location 块），再配合 `ACME_PASSTHROUGH=no`。仅当上游完全拥有证书生命周期时才将 `ACME_PASSTHROUGH` 设为 `yes` —— 在该模式下 BunkerWeb 不会尝试为该服务签发证书。

此设置与 OSS 核心的 `LETS_ENCRYPT_PASSTHROUGH` 行为一致，并且仅影响 HTTP-01；DNS-01 和 TLS-ALPN-01 挑战不受影响。

#### 插件执行顺序

ACME 插件会自动将自身重新排序，以在 `ssl_certificate` NGINX 阶段最先执行，确保 TLS-ALPN-01 挑战证书在其他证书提供插件（selfsigned、letsencrypt、customcert）短路循环之前被提供。

当 ACME 与其他依赖有效 TLS 的 PRO 插件（如 OpenID Connect、UI SSO）一起使用时，建议在相关的阶段排序设置中，将 `acme` 明确放在 `customcert` 之后：

```env
PLUGINS_ORDER_SSL_CERTIFICATE=customcert acme letsencrypt selfsigned
PLUGINS_ORDER_INIT=sessions whitelist blacklist greylist bunkernet limit authbasic securitytxt robotstxt crowdsec dnsbl headers customcert acme letsencrypt selfsigned
```

未列在 `PLUGINS_ORDER_*` 设置中的外部/PRO 插件会按字母顺序追加到已明确排序的核心插件之后。

!!! warning "不要在同一服务上同时启用 `USE_ACME` 和 `AUTO_LETS_ENCRYPT`"
    ACME 插件和内置 Let's Encrypt 插件使用各自独立的存储和挑战路径，但在同一服务上同时启用二者会导致冲突。请对每个服务只使用其中之一。在多站点模式下，不同服务可以使用不同的插件——例如 `app1.example.com_USE_ACME=yes` 和 `app2.example.com_AUTO_LETS_ENCRYPT=yes`。

### 配置

**核心 ACME 设置**

| 设置                   | 默认    | 上下文    | 多个 | 描述                                                              |
| ---------------------- | ------- | --------- | ---- | ----------------------------------------------------------------- |
| `USE_ACME`             | `no`    | multisite | 否   | 为此服务启用 ACME 证书管理。                                      |
| `ACME_PASSTHROUGH`     | `no`    | multisite | 否   | 将 HTTP-01 挑战请求透传给上游服务器（上游自行运行 ACME 客户端）。 |
| `ACME_DIRECTORY_URL`   |         | multisite | 否   | 证书颁发机构的 ACME 目录 URL。                                    |
| `ACME_EMAIL`           |         | multisite | 否   | 用于 ACME 帐户注册和通知的邮箱地址。                              |
| `ACME_CHALLENGE`       | `http`  | multisite | 否   | ACME 挑战类型：`http`、`dns` 或 `alpn`。                          |
| `ACME_KEY_TYPE`        | `ecdsa` | multisite | 否   | 证书的密钥类型：`ecdsa` 或 `rsa`。                                |
| `ACME_KEY_SIZE`        | `256`   | multisite | 否   | 密钥大小（位）。ECDSA：`256` 或 `384`。RSA：`2048` 或 `4096`。    |
| `ACME_RENEWAL_DAYS`    | `30`    | multisite | 否   | 当证书距过期天数少于此值时进行续期。                              |
| `ACME_SSL_VERIFY`      | `yes`   | multisite | 否   | 与 ACME 服务器通信时验证 SSL 证书。                               |
| `ACME_WILDCARD`        | `no`    | multisite | 否   | 请求通配符证书（需要 DNS-01 挑战）。                              |
| `ACME_MUST_STAPLE`     | `no`    | multisite | 否   | 在证书中请求 OCSP Must-Staple 扩展。                              |
| `ACME_MAX_RETRIES`     | `3`     | multisite | 否   | 证书生成失败时的重试次数（0 禁用重试）。                          |
| `ACME_PREFERRED_CHAIN` |         | multisite | 否   | 当 CA 提供多条证书链时，首选的证书链签发者 CN。                   |
| `ACME_CA_CERT_PATH`    |         | multisite | 否   | 私有 ACME 服务器的根 CA 证书文件路径。                            |

**外部帐户绑定（EAB）**

| 设置                | 默认 | 上下文    | 多个 | 描述                                    |
| ------------------- | ---- | --------- | ---- | --------------------------------------- |
| `ACME_EAB_KID`      |      | multisite | 否   | 外部帐户绑定密钥 ID（某些 CA 要求）。   |
| `ACME_EAB_HMAC_KEY` |      | multisite | 否   | 外部帐户绑定 HMAC 密钥（base64 编码）。 |

**DNS-01 挑战**

| 设置                                | 默认      | 上下文    | 多个 | 描述                                                                                                                                                            |
| ----------------------------------- | --------- | --------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ACME_DNS_PROVIDER`                 |           | multisite | 否   | DNS-01 挑战使用的 DNS 提供商。                                                                                                                                  |
| `ACME_DNS_CREDENTIAL_ITEM`          |           | multisite | 是   | DNS 提供商凭据，格式为 `key value`（例如 `cloudflare_api_token YOUR_TOKEN`）。多项时使用数字后缀（例如 `ACME_DNS_CREDENTIAL_ITEM_1`）。值可以进行 base64 编码。 |
| `ACME_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | 是   | 自动解码 base64 编码的 DNS 提供商凭据。如果您的凭据是恰好为有效 base64 的明文，请禁用此选项。                                                                   |
| `ACME_DNS_PROPAGATION`              | `default` | multisite | 否   | 等待 DNS 传播的时间（秒）（`default` 或数字）。                                                                                                                 |

**证书监控**

| 设置                  | 默认        | 上下文 | 多个 | 描述                                                   |
| --------------------- | ----------- | ------ | ---- | ------------------------------------------------------ |
| `USE_ACME_MONITORING` | `yes`       | 全局   | 否   | 启用所有受管证书（包括 OSS Let's Encrypt）的过期监控。 |
| `ACME_ALERT_DAYS`     | `30 14 7 1` | 全局   | 否   | 以空格分隔的天数阈值列表，触发过期告警。               |

**告警（webhook）**

| 设置                      | 默认 | 上下文 | 多个 | 描述                                |
| ------------------------- | ---- | ------ | ---- | ----------------------------------- |
| `USE_ACME_ALERT_WEBHOOK`  | `no` | 全局   | 否   | 通过 webhook 发送证书告警。         |
| `ACME_ALERT_WEBHOOK_URLS` |      | 全局   | 否   | 以空格分隔的告警 webhook URL 列表。 |

**告警（邮件）**

| 设置                            | 默认  | 上下文 | 多个 | 描述                             |
| ------------------------------- | ----- | ------ | ---- | -------------------------------- |
| `USE_ACME_ALERT_EMAIL`          | `no`  | 全局   | 否   | 通过邮件发送证书告警。           |
| `ACME_ALERT_SMTP_EMAILS`        |       | 全局   | 否   | 以空格分隔的邮件收件人列表。     |
| `ACME_ALERT_SMTP_HOST`          |       | 全局   | 否   | 证书告警邮件的 SMTP 主机。       |
| `ACME_ALERT_SMTP_PORT`          | `465` | 全局   | 否   | SMTP 端口（SSL=465，TLS=587）。  |
| `ACME_ALERT_SMTP_FROM_EMAIL`    |       | 全局   | 否   | 证书告警的发件人邮箱地址。       |
| `ACME_ALERT_SMTP_FROM_USER`     |       | 全局   | 否   | SMTP 认证用户名。                |
| `ACME_ALERT_SMTP_FROM_PASSWORD` |       | 全局   | 否   | SMTP 认证密码。                  |
| `ACME_ALERT_SMTP_SSL`           | `SSL` | 全局   | 否   | 连接类型：`no`、`SSL` 或 `TLS`。 |

**证书透明度监控**

| 设置                        | 默认 | 上下文 | 多个 | 描述                                                   |
| --------------------------- | ---- | ------ | ---- | ------------------------------------------------------ |
| `USE_ACME_CT_MONITORING`    | `no` | 全局   | 否   | 启用通过 crt.sh 的 CT 日志监控，检测未授权的证书签发。 |
| `ACME_CT_MONITORED_DOMAINS` |      | 全局   | 否   | 以空格分隔的要监控的域名列表。留空则自动检测。         |

**OCSP Stapling**

| 设置                     | 默认 | 上下文    | 多个 | 描述                                                 |
| ------------------------ | ---- | --------- | ---- | ---------------------------------------------------- |
| `USE_ACME_OCSP_STAPLING` | `no` | multisite | 否   | 启用增强的 OCSP Stapling，主动获取和缓存 OCSP 响应。 |
| `ACME_OCSP_CACHE_SIZE`   | `1m` | 全局      | 否   | OCSP 响应缓存的共享字典大小。                        |

### 快速开始

1. 为每个受保护的服务设置最小值：
    - `USE_ACME=yes`
    - `ACME_DIRECTORY_URL=https://ca.example.com/acme/directory`
    - `ACME_EMAIL=admin@example.com`
2. 对于通配符证书，切换到 DNS-01 挑战：
    - `ACME_CHALLENGE=dns`
    - `ACME_DNS_PROVIDER=cloudflare`
    - `ACME_DNS_CREDENTIAL_ITEM=cloudflare_api_token YOUR_TOKEN`（生产环境中请使用 [Docker secrets](integrations.md#docker)）
    - `ACME_WILDCARD=yes`
3. 对于需要外部帐户绑定的 CA：
    - `ACME_EAB_KID=your-key-id`
    - `ACME_EAB_HMAC_KEY=your-base64-hmac-key`（生产环境中请使用 [Docker secrets](integrations.md#docker)）
4. 对于使用自签名根证书的私有 CA：
    - `ACME_CA_CERT_PATH=/path/to/ca-root.pem`
    - `ACME_SSL_VERIFY=yes`（提供 `ACME_CA_CERT_PATH` 可以让验证通过私有 CA 而无需禁用 SSL 验证）

### 使用提示

- 证书监控（`USE_ACME_MONITORING`）默认启用，也会跟踪 OSS Let's Encrypt 证书。配置 `ACME_ALERT_DAYS` 阈值并至少配置一个告警渠道（webhook 或邮件）以接收过期警告。
- 启用 CT 监控（`USE_ACME_CT_MONITORING=yes`）可通过证书透明度日志检测为您域名未授权签发的证书。
- 默认使用 ECDSA 密钥，证书更小、更快。仅在需要与旧版客户端兼容时才切换到 RSA。
- 使用 DNS-01 挑战时，如果您的 DNS 提供商传播记录较慢，请调整 `ACME_DNS_PROPAGATION`。
- 设置 `ACME_MAX_RETRIES=0` 可禁用自动重试，适合需要手动排查故障的场景。

### 与内置 Let's Encrypt 共存

ACME PRO 与 OSS Let's Encrypt 插件使用完全独立的存储、API 端点和缓存键。在多站点模式下，二者可以同时在不同服务上运行：

```yaml
MULTISITE: "yes"
SERVER_NAME: "app1.example.com app2.example.com"

# ACME PRO 用于 app1（私有 CA）
app1.example.com_USE_ACME: "yes"
app1.example.com_ACME_DIRECTORY_URL: "https://ca.internal:9000/acme/acme/directory"
app1.example.com_ACME_CA_CERT_PATH: "/certs/step-ca-root.pem"
app1.example.com_LETS_ENCRYPT_PASSTHROUGH: "yes"  # HTTP-01 所需

# 内置 Let's Encrypt 用于 app2
app2.example.com_AUTO_LETS_ENCRYPT: "yes"
```

### 故障排除

- **HTTP-01 挑战失败**：确保设置了 `LETS_ENCRYPT_PASSTHROUGH=yes`——否则 BunkerWeb 的核心 location 块会在 ACME PRO 能够处理之前拦截挑战请求。同时确认 ACME 服务器可访问端口 80，且同一服务未同时启用 `AUTO_LETS_ENCRYPT`。
- **TLS-ALPN-01 挑战失败**：确保 ACME 服务器可访问端口 443，且在 `ssl_certificate` 阶段没有其他插件在 ACME 之前提供证书。如有疑问，请检查 `PLUGINS_ORDER_SSL_CERTIFICATE`。
- **DNS-01 挑战失败**：验证 `ACME_DNS_CREDENTIAL_ITEM` 中的 DNS 提供商凭据，如果您的提供商传播记录较慢，请调整 `ACME_DNS_PROPAGATION`。
- **证书未续期**：检查 `ACME_RENEWAL_DAYS` 和调度器日志。`acme-renew` 作业每天运行，续期处于配置阈值内的证书。

## Wildcard <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO) {#wildcard-pro}

STREAM 支持 :x:

**Wildcard** 插件允许单个 BunkerWeb 服务响应：

* 其精确主机名
* 该主机名下任意**直接子域名**

启用后，插件会从 `SERVER_NAME` 中取出**第一个条目**，并在生成的 NGINX 配置中添加一个通配符 `server_name`。

例如，如果第一个条目是 `example.com`，插件会添加：

```nginx
server_name *.example.com;
```

这样该服务就会响应：

* `example.com`
* `www.example.com`
* `api.example.com`

这是一个最小化、纯配置型插件：

* 无 jobs
* 无 Lua
* 无 UI

---

### 工作原理

该插件从 `SERVER_NAME` 的**第一个值**推导出通配符主机名，并在生成配置时注入标准 NGINX 通配符服务器名。

除主机名匹配外，它不会改变请求处理逻辑。

!!! info "通配符主机并不等于通配符证书"
    此插件只影响 **HTTP 路由**。它告诉 NGINX 服务应接受哪些主机名。

    它**不会**签发通配符 TLS 证书。

    如果要通过 HTTPS 提供 `*.example.com`，您仍然需要匹配的通配符证书，通常可以使用以下其中一种方式：

    - 使用内置 Let's Encrypt 插件并设置 `USE_LETS_ENCRYPT_WILDCARD=yes`
    - 使用 [ACME PRO](#acme) 插件并设置 `ACME_WILDCARD=yes`，同时使用 DNS-01 挑战

---

### 功能

* **启用简单**：通过 `USE_WILDCARD=yes` 启用通配符路由
* **自动推导**：通配符主机基于 `SERVER_NAME` 的第一个条目构建
* **原生 NGINX 语义**：匹配遵循标准 `server_name` 行为
* **支持多站点**：每个服务都可以独立启用或禁用通配符路由

---

### 配置

| 参数           | 默认值 | 上下文    | 可重复 | 描述                                                                             |
| -------------- | ------ | --------- | ------ | -------------------------------------------------------------------------------- |
| `USE_WILDCARD` | `no`   | multisite | 否     | 为服务启用通配符 `server_name`，即为 `SERVER_NAME` 的第一个条目添加 `*.domain`。 |

---

### 快速开始

1. 将您想要使用通配符的域名放在 `SERVER_NAME` 的**第一位**
2. 设置 `USE_WILDCARD=yes`
3. 将通配符 DNS 记录指向 BunkerWeb，通常是通配符 `A` 或 `AAAA` 记录
4. 如果需要 HTTPS，请单独签发通配符证书
5. 重新加载或重启 BunkerWeb

---

### 示例

#### Single-site

```yaml
SERVER_NAME: "example.com"
USE_WILDCARD: "yes"
```

该服务将响应：

* `example.com`
* `www.example.com`
* `api.example.com`
* 任何其他解析到 BunkerWeb 的 `*.example.com` 主机名

#### Multisite

```yaml
MULTISITE: "yes"
SERVER_NAME: "app.example.com docs.example.org"

# 只有 app.example.com 会启用通配符路由
app.example.com_USE_WILDCARD: "yes"
```

在此配置中：

* `app.example.com` 和 `*.app.example.com` 会路由到第一个服务
* `docs.example.org` 仍然只保留精确匹配

---

### 重要行为

!!! warning "只有第一个域名会被通配"
    如果 `SERVER_NAME` 是：

    ```yaml
    SERVER_NAME: "example.com example.org"
    ```

    则只会添加 `*.example.com`。

    请将您想要使用通配符的域名放在第一位。

!!! note "已有通配符条目会被保留"
    如果第一个域名已经以 `*.` 开头，例如：

    ```yaml
    SERVER_NAME: "*.example.com"
    ```

    插件将不会输出任何内容。

!!! note "通配符匹配仅支持单层标签"
    `*.example.com` 可以匹配 `foo.example.com`，但不能匹配 `a.b.example.com`。

    对于更深层的子域名，请使用显式的 `SERVER_NAME` 条目或单独的服务。

!!! note "精确匹配优先"
    如果另一个服务显式定义了 `foo.example.com`，NGINX 会优先将该主机名路由到精确匹配。

---

### 与 Let's Encrypt 通配符证书配合时的推荐方式

如果您将此插件与 `USE_LETS_ENCRYPT_WILDCARD=yes` 一起使用，请采用以下模式：

```yaml
SERVER_NAME: "<root_domain> <any_app>.<root_domain>"
```

**根域名必须放在第一位**。

示例：

```yaml
SERVER_NAME: "example.com app.example.com"
USE_WILDCARD: "yes"
AUTO_LETS_ENCRYPT: "yes"
EMAIL_LETS_ENCRYPT: "admin@example.com"
LETS_ENCRYPT_CHALLENGE: "dns"
LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token YOUR_API_TOKEN"
USE_LETS_ENCRYPT_WILDCARD: "yes"
```

!!! tip "为什么这个模式很重要"
    - **只有 `SERVER_NAME` 的第一个条目会被通配**

    如果 `example.com` 放在第一位，插件会生成 `*.example.com`。

    如果 `app.example.com` 放在第一位，它会生成 `*.app.example.com`，这通常不是您想要的通配层级。

    - **第二个条目有助于 Let's Encrypt 检测正确的基础域名**
      如果只有裸 apex 域名，在某些公共后缀域名（例如 `example.co.uk`）上，通配符证书检测可能会失败。

    - **第二个主机名不需要真实后端**
      使用任何稳定的值即可，例如 `app.example.com` 或 `www.example.com`。

#### Multisite with Let's Encrypt wildcard

```yaml
MULTISITE: "yes"
SERVER_NAME: "example.com app.example.com"
example.com_USE_WILDCARD: "yes"
example.com_USE_LETS_ENCRYPT_WILDCARD: "yes"
example.com_LETS_ENCRYPT_CHALLENGE: "dns"
example.com_LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
example.com_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token YOUR_API_TOKEN"
```

---

### 使用提示

* **请单独规划 TLS**
  仅有通配符路由不足以支持 HTTPS。您仍然需要为子域名准备相应的证书覆盖。

* **保持 `SERVER_NAME` 顺序稳定**
  调整条目顺序会改变哪个域名成为通配目标。

* **与 `REVERSE_PROXY_HOST` 配合良好**
  当大量子域名通过共享上游（例如租户路由器）进行转发时，这会很有用。

* **注意重叠服务**
  NGINX 总是优先选择最具体的 `server_name` 匹配。
