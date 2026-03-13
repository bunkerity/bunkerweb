# 快速入门指南

!!! info "先决条件"

    我们希望您已经熟悉[核心概念](concepts.md)并已按照[集成说明](integrations.md)为您的环境进行了操作。

    本快速入门指南假设 BunkerWeb 可以从互联网访问，并且您已经配置了至少两个域：一个用于 Web UI，一个用于您的 Web 服务。

    **系统要求**

    BunkerWeb 的最低推荐规格是具有 2 个（虚拟）CPU 和 8 GB RAM 的机器。请注意，这对于测试环境或服务很少的设置应该足够了。

    对于需要保护大量服务的生产环境，我们建议至少配备 4 个（虚拟）CPU 和 16 GB RAM。应根据您的用例、网络流量以及您可能面临的潜在 DDoS 攻击来调整资源。

    如果您处于 RAM 有限的环境中或在拥有大量服务的生产环境中，强烈建议启用 CRS 规则的全局加载（通过将 `USE_MODSECURITY_GLOBAL_CRS` 参数设置为 `yes`）。更多详细信息可以在文档的[高级用法](advanced.md#running-many-services-in-production)部分找到。

本快速入门指南将帮助您快速安装 BunkerWeb 并使用 Web 用户界面保护 Web 服务。

保护已经可以通过 HTTP(S) 协议访问的现有 Web 应用程序是 BunkerWeb 的主要目标：它将充当一个带有额外安全功能的经典[反向代理](https://en.wikipedia.org/wiki/Reverse_proxy)。

有关真实世界的示例，请参阅仓库的 [examples 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.9/examples)。

## 基本设置

=== "一体化"

    要部署一体化容器，请运行以下命令：

    ```shell
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    默认情况下，容器暴露：

    *   8080/tcp 用于 HTTP
    *   8443/tcp 用于 HTTPS
    *   8443/udp 用于 QUIC
    *   7000/tcp 用于在没有 BunkerWeb 前置的情况下的 Web UI 访问（不建议在生产环境中使用）

    一体化镜像内置了几个服务，可以通过环境变量来控制。有关更多详细信息，请参阅集成页面的[一体化 (AIO) 镜像部分](integrations.md#all-in-one-aio-image)。

=== "Linux"

    使用简易安装脚本在支持的 Linux 发行版上设置 BunkerWeb。它会自动安装和配置 NGINX，添加 BunkerWeb 仓库，并设置所需的服务。

    ```bash
    # 下载脚本及其校验和
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.9/install-bunkerweb.sh
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.9/install-bunkerweb.sh.sha256

    # 验证校验和
    sha256sum -c install-bunkerweb.sh.sha256

    # 如果检查成功，则运行脚本
    chmod +x install-bunkerweb.sh
    sudo ./install-bunkerweb.sh
    ```

    !!! danger "安全提示"
        在执行脚本之前，请务必使用提供的校验和验证脚本的完整性。

    #### Easy Install 亮点

    - 在更改系统之前，会预先检测您的 Linux 发行版和 CPU 架构，并在超出支持矩阵时发出警告。
    - 交互式流程允许选择安装配置（全栈、manager、worker 等）；manager 模式始终将 API 绑定到 `0.0.0.0`、禁用设置向导并要求提供白名单 IP（非交互式运行可通过 `--manager-ip` 传入），而 worker 模式会强制收集 manager IP 以填充其白名单。
    - 即使向导被禁用，Manager 安装仍可决定是否启动 Web UI 服务。
    - 汇总信息会显示 FastAPI 服务是否会启动，便于使用 `--api` / `--no-api` 明确启用或禁用它。
    - CrowdSec 选项仅适用于全栈安装；manager / worker 模式会自动跳过它们，以专注于远程控制。

    有关高级安装方法（包管理器、安装类型、非交互式标志、CrowdSec 集成等），请参阅[Linux 集成](integrations.md#linux)。

=== "Docker"

    这是您可以使用的完整 docker compose 文件；请注意，我们稍后会将 Web 服务连接到 `bw-services` 网络：

    ```yaml
    x-bw-env: &bw-env
      # 我们使用一个锚点来避免在两个服务中重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 确保设置正确的 IP 范围，以便调度器可以将配置发送到实例
      # 可选：设置一个 API 令牌并在两个容器中镜像它
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码

    services:
      bunkerweb:
        # 这是将用于在调度器中识别实例的名称
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 用于 QUIC / HTTP3 支持
        environment:
          <<: *bw-env # 我们使用锚点来避免为所有服务重复相同的设置
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 确保设置正确的实例名称
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # 如果需要，请更改它
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        environment:
          <<: *bw-env
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
          MYSQL_PASSWORD: "changeme" # 记得为数据库设置一个更强的密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis 服务用于持久化报告/封禁/统计数据
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

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # 确保设置正确的 IP 范围，以便调度器可以将配置发送到实例
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    这是您可以使用的完整 docker compose 文件；请注意，我们稍后会将 Web 服务连接到 `bw-services` 网络：

    ```yaml
    x-ui-env: &bw-ui-env
      # 我们锚定环境变量以避免重复
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 用于 QUIC / HTTP3 支持
        labels:
          - "bunkerweb.INSTANCE=yes" # 我们设置实例标签以允许 autoconf 检测实例
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # 如果需要，请更改它
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.9
        depends_on:
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        environment:
          <<: *bw-ui-env
          TOTP_ENCRYPTION_KEYS: "mysecret" # 记得设置一个更强的密钥（请参阅先决条件部分）
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
          MYSQL_PASSWORD: "changeme" # 记得为数据库设置一个更强的密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis 服务用于持久化报告/封禁/统计数据
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

    volumes:
      bw-data:
      bw-storage:
      redis-data:

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

    安装 Kubernetes 的推荐方法是使用位于 `https://repo.bunkerweb.io/charts` 的 Helm chart：

    ```shell
    helm repo add bunkerweb https://repo.bunkerweb.io/charts
    ```

    然后您可以使用该仓库中的 `bunkerweb` helm chart：

    ```shell
    helm install mybw bunkerweb/bunkerweb --namespace bunkerweb --create-namespace
    ```

    安装后，您可以获取 `LoadBalancer` 的 IP 地址来设置您的域：

    ```shell
    kubectl -n bunkerweb get svc mybw-external -o=jsonpath='{.status.loadBalancer.ingress[0].ip}'
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    这是您可以使用的完整 docker compose 堆栈文件；请注意，我们稍后会将 Web 服务连接到 `bw-services` 网络：

    ```yaml
    x-ui-env: &bw-ui-env
      # 我们锚定环境变量以避免重复
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
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
            protocol: udp # 用于 QUIC / HTTP3 支持
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
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
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
          UI_HOST: "http://bw-ui:7000" # 如果需要，请更改它
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.9
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        environment:
          <<: *bw-ui-env
          TOTP_ENCRYPTION_KEYS: "mysecret" # 记得设置一个更强的密钥（请参阅先决条件部分）
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
          MYSQL_PASSWORD: "changeme" # 记得为数据库设置一个更强的密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      bw-redis:
        image: redis:8-alpine
        networks:
          - bw-universe

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

## 完成设置向导 {#complete-the-setup-wizard}

!!! tip "访问设置向导"

    您可以通过浏览服务器的 `https://your-fqdn-or-ip-addresss/setup` URI 来访问设置向导。

### 创建一个管理员帐户

您应该会看到一个像这样的设置页面：
<figure markdown>
  ![设置向导登录页面](assets/img/ui-wizard-step1.png){ align=center }
  <figcaption>设置向导登录页面</figcaption>
</figure>

进入设置页面后，您可以输入**管理员用户名、电子邮件和密码**，然后点击“下一步”按钮。

### 配置反向代理、HTTPS 和其他高级设置

=== "基本设置"

    下一步将要求您输入 Web UI 将使用的**服务器名称**（域名/FQDN）。

    您还可以选择启用 [Let's Encrypt](features.md#lets-encrypt)

    <figure markdown>
      ![设置向导第 2 步](assets/img/ui-wizard-step2.png){ align=center }
      <figcaption>设置向导第 2 步</figcaption>
    </figure>

=== "高级设置"

    下一步将要求您输入 Web UI 将使用的**服务器名称**（域名/FQDN）。

    您还可以选择启用 [Let's Encrypt](features.md#lets-encrypt)。

    如果您展开 `高级设置` 部分，您还可以配置以下选项：

    *   **反向代理**：调整您的管理员界面的反向代理设置（例如，如果您想使用一个路径）。
    *   [**真实 IP**](features.md#real-ip)：配置真实 IP 设置以正确识别客户端的 IP 地址（例如，如果您位于负载均衡器或 CDN 之后）。
    *   [**自定义证书**](features.md#custom-ssl-certificate)：如果您不想使用 Let's Encrypt，可以上传自定义 TLS 证书。

    <figure markdown>
      ![设置向导第 2 步](assets/img/ui-wizard-step2-advanced.png){ align=center }
      <figcaption>设置向导第 2 步（高级）</figcaption>
    </figure>

### PRO 激活

如果您拥有 PRO 许可证，可以在 `升级到 PRO` 部分输入您的许可证密钥来激活它。这将启用 BunkerWeb 的 PRO 功能。

<figure markdown>
  ![设置向导 PRO 步骤](assets/img/ui-wizard-step3.png){ align=center }
  <figcaption>设置向导 PRO 步骤</figcaption>
</figure>

### 您的设置概览

最后一步将为您提供您所输入设置的概览。您可以点击“设置”按钮来完成设置。

<figure markdown>
  ![设置向导最后一步](assets/img/ui-wizard-step4.png){ align=center }
  <figcaption>设置向导最后一步</figcaption>
</figure>


## 访问 Web 界面

您现在可以通过浏览您在上一步中配置的域以及如果您更改了 URI（默认为 `https://your-domain/`）来访问 Web 界面。

<figure markdown>
  ![Web 界面登录页面](assets/img/ui-login.png){ align=center }
  <figcaption>Web 界面登录页面</figcaption>
</figure>

您现在可以使用您在设置向导期间创建的管理员帐户登录。

<figure markdown>
  ![Web 界面主页](assets/img/ui-home.png){ align=center }
  <figcaption>Web 界面主页</figcaption>
</figure>

## 创建一个新服务

=== "Web UI"

    您可以通过导航到 Web 界面的 `服务` 部分并点击 `➕ 创建新服务` 按钮来创建一个新服务。

    使用 Web 界面创建服务有多种方式：

    *   **简单模式**将引导您完成创建新服务的过程。
    *   **高级模式**将允许您使用更多选项来配置服务。
    *   **原始模式**将允许您直接输入配置，就像编辑 `variables.env` 文件一样。

    !!! tip "草稿服务"

        您可以创建一个草稿服务来保存您的进度，并在以后返回。只需点击 `🌐 在线` 按钮即可将服务切换到草稿模式。

    === "简单模式"

        在此模式下，您可以从可用模板中选择并填写必填字段。

        <figure markdown>
          ![Web 界面创建服务简单模式](assets/img/ui-create-service-easy.png){ align=center }
          <figcaption>Web 界面创建服务简单模式</figcaption>
        </figure>

        *   选择模板后，您可以填写必填字段并按照说明创建服务。
        *   配置完服务后，您可以点击 `💾 保存` 按钮保存配置。

    === "高级模式"

        在此模式下，您可以使用更多选项来配置服务，同时可以看到所有不同插件的所有可用设置。

        <figure markdown>
          ![Web 界面创建服务高级模式](assets/img/ui-create-service-advanced.png){ align=center }
          <figcaption>Web 界面创建服务高级模式</figcaption>
        </figure>

        *   要在不同插件之间导航，您可以使用页面左侧的导航菜单。
        *   每个设置都有一小段信息，可以帮助您了解它的作用。
        *   配置完服务后，您可以点击 `💾 保存` 按钮保存配置。

    === "原始模式"

        在此模式下，您可以直接输入配置，就像编辑 `variables.env` 文件一样。

        <figure markdown>
          ![Web 界面创建服务原始模式](assets/img/ui-create-service-raw.png){ align=center }
          <figcaption>Web 界面创建服务原始模式</figcaption>
        </figure>

        *   配置完服务后，您可以点击 `💾 保存` 按钮保存配置。

    🚀 保存配置后，您应该会在服务列表中看到您的新服务。

    <figure markdown>
      ![Web 界面服务页面](assets/img/ui-services.png){ align=center }
      <figcaption>Web 界面服务页面</figcaption>
    </figure>

    如果您希望编辑服务，可以点击服务名称或 `📝 编辑` 按钮。

=== "一体化"

    当使用一体化镜像时，新服务是通过向 `bunkerweb-aio` 容器的 `docker run` 命令添加环境变量来配置的。如果容器已经在运行，您必须停止并删除它，然后用更新的环境变量重新运行它。

    假设您想保护一个应用程序 `myapp`（在另一个容器中运行，并可以从 BunkerWeb 作为 `http://myapp:8080` 访问），并使其在 `www.example.com` 上可用。您将在您的 `docker run` 命令中添加或修改以下环境变量：

    ```shell
    # 首先，如果现有容器正在运行，请停止并删除它：
    # docker stop bunkerweb-aio
    # docker rm bunkerweb-aio

    # 然后，用额外/更新的环境变量重新运行 bunkerweb-aio 容器：
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      # --- 为您的新服务添加/修改这些环境变量 ---
      -e MULTISITE=yes \
      -e SERVER_NAME="www.example.com" \
      -e "www.example.com_USE_REVERSE_PROXY=yes" \
      -e "www.example.com_REVERSE_PROXY_HOST=http://myapp:8080" \
      -e "www.example.com_REVERSE_PROXY_URL=/" \
      # --- 包括任何其他现有的用于 UI、Redis、CrowdSec 等的环境变量 ---
      bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    您的应用程序容器 (`myapp`) 和 `bunkerweb-aio` 容器必须在同一个 Docker 网络上，以便 BunkerWeb 能够使用主机名 `myapp` 访问它。

    **网络设置示例：**
    ```shell
    # 1. 创建一个自定义 Docker 网络（如果还没有的话）：
    docker network create my-app-network

    # 2. 在此网络上运行您的应用程序容器：
    docker run -d --name myapp --network my-app-network your-app-image

    # 3. 将 --network my-app-network 添加到 bunkerweb-aio 的 docker run 命令中：
    docker run -d \
      --name bunkerweb-aio \
      --network my-app-network \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
    #   ... （如上主示例所示的所有其他相关环境变量）...
      bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    请确保将 `myapp` 替换为您的应用程序容器的实际名称或 IP，并将 `http://myapp:8080` 替换为其正确的地址和端口。

=== "Linux variables.env 文件"

    我们假设您已经按照[基本设置](#__tabbed_1_2)进行了操作，并且 Linux 集成正在您的机器上运行。

    您可以通过编辑位于 `/etc/bunkerweb/` 目录中的 `variables.env` 文件来创建一个新服务。

    ```shell
    nano /etc/bunkerweb/variables.env
    ```

    然后您可以添加以下配置：

    ```shell
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/
    www.example.com_REVERSE_PROXY_HOST=http://myapp:8080
    ```

    然后您可以重新加载 `bunkerweb-scheduler` 服务以应用更改。

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

=== "Docker"

    我们假设您已经按照[基本设置](#__tabbed_1_3)进行了操作，并且 Docker 集成正在您的机器上运行。

    您必须有一个名为 `bw-services` 的网络，以便您可以连接您现有的应用程序并配置 BunkerWeb：

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    之后，您可以在您在上一步中创建的 docker compose 文件中手动添加服务：

    ```yaml
    ...

    services:
      ...
      bw-scheduler:
        ...
        environment:
          ...
          SERVER_NAME: "www.example.com" # 当使用 Docker 集成时，您可以直接在调度器中设置配置，确保设置正确的域名
          MULTISITE: "yes" # 启用多站点模式，以便您可以添加多个服务
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/"
          www.example.com_REVERSE_PROXY_HOST: "http://myapp:8080"
          ...
    ```

    然后您可以重启 `bw-scheduler` 服务以应用更改。

    ```shell
    docker compose down bw-scheduler && docker compose up -d bw-scheduler
    ```

=== "Docker autoconf 标签"

    我们假设您已经按照[基本设置](#__tabbed_1_4)进行了操作，并且 Docker autoconf 集成正在您的机器上运行。

    您必须有一个名为 `bw-services` 的网络，以便您可以连接您现有的应用程序并使用标签配置 BunkerWeb：

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services
    	  labels:
    	    - "bunkerweb.SERVER_NAME=www.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    这样做将自动创建一个新服务，并使用提供的标签作为配置。

=== "Kubernetes 注解"

    我们假设您已经按照[基本设置](#__tabbed_1_5)进行了操作，并且 Kubernetes 堆栈正在您的集群上运行。

    假设您有一个典型的 Deployment，并带有一个 Service，以便从集群内部访问 Web 应用程序：

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app
      labels:
    	app: app
    spec:
      replicas: 1
      selector:
    	matchLabels:
    	  app: app
      template:
    	metadata:
    	  labels:
    		app: app
    	spec:
    	  containers:
    	  - name: app
    		image: bunkerity/bunkerweb-hello:v1.0
    		ports:
    		- containerPort: 8080
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app
    spec:
      selector:
    	app: app
      ports:
    	- protocol: TCP
    	  port: 80
    	  targetPort: 8080
    ```

    这是相应的 Ingress 定义，用于服务和保护 Web 应用程序：

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/DUMMY_SETTING: "value"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app
                  port:
                    number: 80
    ```

=== "Swarm 标签"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    我们假设您已经按照[基本设置](#__tabbed_1_5)进行了操作，并且 Swarm 堆栈正在您的集群上运行，并连接到一个名为 `bw-services` 的网络，以便您可以连接您现有的应用程序并使用标签配置 BunkerWeb：

    ```yaml
    services:
      myapp:
        image: bunkerity/bunkerweb-hello:v1.0
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## 更进一步

恭喜！您刚刚安装了 BunkerWeb 并保护了您的第一个 Web 服务。请注意，BunkerWeb 在安全性和与其他系统和解决方案的集成方面提供了更多功能。以下是一些资源和行动，可以帮助您继续加深对该解决方案的了解：

- 加入 Bunker 社区：[Discord](https://discord.com/invite/fTf46FmtyD)、[LinkedIn](https://www.linkedin.com/company/bunkerity/)、[GitHub](https://github.com/bunkerity)、[X (Formerly Twitter)](https://x.com/bunkerity)
- 查看[官方博客](https://www.bunkerweb.io/blog?utm_campaign=self&utm_source=doc)
- 探索文档中的[高级用例](advanced.md)
- [与我们联系](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc)讨论您组织的需求
