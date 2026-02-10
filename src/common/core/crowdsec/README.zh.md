<figure markdown>
  ![概述](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

CrowdSec 插件将 BunkerWeb 与 CrowdSec 安全引擎集成，为抵御各种网络威胁提供额外的保护层。此插件充当 [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) 拦截器，根据 CrowdSec API 的决策拒绝请求。

CrowdSec 是一种现代的开源安全引擎，它基于行为分析和社区的集体情报来检测和阻止恶意 IP 地址。您还可以配置[场景](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios)来根据可疑行为自动封禁 IP 地址，从而受益于一个众包的黑名单。

**工作原理：**

1.  CrowdSec 引擎会分析日志并检测您基础设施上的可疑活动。
2.  当检测到恶意活动时，CrowdSec 会创建一个决策来阻止违规的 IP 地址。
3.  BunkerWeb 作为拦截器，会向 CrowdSec 本地 API 查询有关传入请求的决策。
4.  如果客户端的 IP 地址有活动的阻止决策，BunkerWeb 会拒绝其访问受保护的服务。
5.  可选地，应用程序安全组件可以执行深度请求检查以增强安全性。

!!! success "主要优点"

      1. **社区驱动的安全：** 受益于整个 CrowdSec 用户社区共享的威胁情报。
      2. **行为分析：** 基于行为模式而不是签名来检测复杂的攻击。
      3. **轻量级集成：** 对您的 BunkerWeb 实例的性能影响最小。
      4. **多层次保护：** 结合边界防御（IP 阻止）和应用程序安全，实现深度保护。

### 前置条件

- CrowdSec 本地 API，BunkerWeb 可以访问（通常为运行在同一主机或同一 Docker 网络中的代理）。
- 访问 BunkerWeb 访问日志（默认路径 `/var/log/bunkerweb/access.log`），以便 CrowdSec 代理分析请求。
- 在 CrowdSec 主机上可使用 `cscli`，用于注册 BunkerWeb 的 bouncer 密钥。

### 集成流程

1. 准备 CrowdSec 代理，使其能够摄取 BunkerWeb 日志。
2. 配置 BunkerWeb，以便查询 CrowdSec 本地 API。
3. 通过 `/crowdsec/ping` API 或管理界面中的 CrowdSec 卡片验证连接。

以下各节将依次说明这些步骤。

### 第&nbsp;1&nbsp;步 – 准备 CrowdSec 摄取 BunkerWeb 日志

=== "Docker"
    **采集文件**

    您需要运行一个 CrowdSec 实例，并将其配置为解析 BunkerWeb 日志。请在采集文件中将 `type` 参数设置为专用的 `bunkerweb` 值（假设 BunkerWeb 日志按原样存储，没有附加数据）：

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    如果在 CrowdSec 容器内仍然看不到该集合，请运行 `docker exec -it <crowdsec-container> cscli hub update`，然后重启该容器（`docker restart <crowdsec-container>`），以加载新的资源。请将 `<crowdsec-container>` 替换为 CrowdSec 容器的实际名称。

    **应用程序安全组件（*可选*）**

    CrowdSec 还提供了一个[应用程序安全组件](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs)，可用于保护您的应用程序免受攻击。如果您想使用它，必须为 AppSec 组件创建另一个采集文件：

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    对于基于容器的集成，我们建议将 BunkerWeb 容器的日志重定向到 syslog 服务，以便 CrowdSec 可以轻松访问它们。这是一个 syslog-ng 的示例配置，它会将来自 BunkerWeb 的原始日志存储到本地的 `/var/log/bunkerweb.log` 文件中：

    ```syslog
    @version: 4.10

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    这是您可以使用的 docker-compose 样板（不要忘记更新 bouncer 密钥）：

    ```yaml
    x-bw-env: &bw-env
      # 我们使用一个锚点来避免在两个服务中重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 确保设置正确的 IP 范围，以便调度器可以将配置发送到实例

    services:
      bunkerweb:
        # 这是将用于在调度器中识别实例的名称
        image: bunkerity/bunkerweb:1.6.8
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
        logging:
          driver: syslog # 将日志发送到 syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # syslog 服务的 IP 地址

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 确保设置正确的实例名称
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # 这是同一网络中 CrowdSec 容器 API 的地址
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # 如果您不想使用 AppSec 组件，请注释掉此行
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # 记得为 bouncer 设置一个更强的密钥
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
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

      crowdsec:
        image: crowdsecurity/crowdsec:v1.7.4 # 使用最新版本，但为了更好的稳定性和安全性，请始终固定版本
        volumes:
          - cs-data:/var/lib/crowdsec/data # 持久化 CrowdSec 数据
          - bw-logs:/var/log:ro # BunkerWeb 的日志，供 CrowdSec 解析
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # BunkerWeb 日志的采集文件
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # 如果您不想使用 AppSec 组件，请注释掉此行
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # 记得为 bouncer 设置一个更强的密钥
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # 如果您不想使用 AppSec 组件，请改用此行
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # 绑定到低端口
          - NET_BROADCAST  # 发送广播
          - NET_RAW  # 使用原始套接字
          - DAC_READ_SEARCH  # 绕过权限读取文件
          - DAC_OVERRIDE  # 覆盖文件权限
          - CHOWN  # 更改所有权
          - SYSLOG  # 写入系统日志
        volumes:
          - bw-logs:/var/log/bunkerweb # 用于存储日志的卷
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # syslog-ng 配置文件
        networks:
            bw-universe:
              ipv4_address: 10.20.30.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

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

=== "Linux"

    您需要安装 CrowdSec 并将其配置为解析 BunkerWeb 日志。请按照[官方文档](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios)进行操作。

    要使 CrowdSec 能够解析 BunkerWeb 日志，请将以下行添加到位于 `/etc/crowdsec/acquis.yaml` 的采集文件中：

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    更新 CrowdSec hub 并安装 BunkerWeb 集合：

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    现在，使用 `cscli` 工具将您的自定义 bouncer 添加到 CrowdSec API：

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "API 密钥"
        请保留 `cscli` 命令生成的密钥；稍后您将需要它。

    然后重启 CrowdSec 服务：

    ```shell
    sudo systemctl restart crowdsec
    ```

    **应用程序安全组件（*可选*）**

    如果您想使用 AppSec 组件，您必须为其创建一个位于 `/etc/crowdsec/acquis.d/appsec.yaml` 的另一个采集文件：

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    您还需要安装 AppSec 组件的集合：

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    最后，重启 CrowdSec 服务：

    ```shell
    sudo systemctl restart crowdsec
    ```

    **设置**

    通过将以下设置添加到您的 BunkerWeb 配置文件来配置插件：

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<The key provided by cscli>
    # 如果您不想使用 AppSec 组件，请注释掉
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    最后，重新加载 BunkerWeb 服务：

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "All-in-one"

    BunkerWeb All-In-One (AIO) Docker 镜像完全集成了 CrowdSec。当使用内部 CrowdSec 代理时，您无需为 BunkerWeb 日志设置单独的 CrowdSec 实例或手动配置文件。

    请参阅[一体化 (AIO) 镜像集成文档](integrations.md#crowdsec-integration)。

### 第&nbsp;2&nbsp;步 – 配置 BunkerWeb 参数

应用以下环境变量（或通过调度器设置的值），让 BunkerWeb 实例能够与 CrowdSec 本地 API 通信。至少需要设置 `USE_CROWDSEC`、`CROWDSEC_API` 以及通过 `cscli bouncers add` 生成的有效密钥。

| 设置                        | 默认值                 | 上下文    | 多个 | 描述                                                                                                  |
| --------------------------- | ---------------------- | --------- | ---- | ----------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | 否   | **启用 CrowdSec：** 设置为 `yes` 以启用 CrowdSec 拦截器。                                             |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | 否   | **CrowdSec API URL：** CrowdSec 本地 API 服务的地址。                                                 |
| `CROWDSEC_API_KEY`          |                        | global    | 否   | **CrowdSec API 密钥：** 用于向 CrowdSec API 进行身份验证的 API 密钥，使用 `cscli bouncers add` 获取。 |
| `CROWDSEC_MODE`             | `live`                 | global    | 否   | **操作模式：** `live`（为每个请求查询 API）或 `stream`（定期缓存所有决策）。                          |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | 否   | **内部流量：** 设置为 `yes` 以根据 CrowdSec 决策检查内部流量。                                        |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | 否   | **请求超时：** 在实时模式下向 CrowdSec 本地 API 发出 HTTP 请求的超时时间（以毫秒为单位）。            |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | 否   | **排除的位置：** 从 CrowdSec 检查中排除的位置（URI）列表，以逗号分隔。                                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | 否   | **缓存过期时间：** 在实时模式下，IP 决策的缓存过期时间（以秒为单位）。                                |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | 否   | **更新频率：** 在流模式下，从 CrowdSec API 拉取新的/过期的决策的频率（以秒为单位）。                  |

#### 应用程序安全组件设置

| 设置                              | 默认值        | 上下文 | 多个 | 描述                                                                              |
| --------------------------------- | ------------- | ------ | ---- | --------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |               | global | 否   | **AppSec URL：** CrowdSec 应用程序安全组件的 URL。留空以禁用 AppSec。             |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | global | 否   | **失败操作：** 当 AppSec 返回错误时要采取的操作。可以是 `passthrough` 或 `deny`。 |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | global | 否   | **连接超时：** 连接到 AppSec 组件的超时时间（以毫秒为单位）。                     |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | global | 否   | **发送超时：** 向 AppSec 组件发送数据的超时时间（以毫秒为单位）。                 |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | global | 否   | **处理超时：** 在 AppSec 组件中处理请求的超时时间（以毫秒为单位）。               |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | global | 否   | **始终发送：** 设置为 `yes` 以始终将请求发送到 AppSec，即使存在 IP 级别的决策。   |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | global | 否   | **SSL 验证：** 设置为 `yes` 以验证 AppSec 组件的 SSL 证书。                       |

!!! info "关于操作模式" - **实时模式**会为每个传入的请求查询 CrowdSec API，提供实时的保护，但会增加延迟。- **流模式**会定期从 CrowdSec API 下载所有决策并将其本地缓存，从而减少延迟，但应用新决策会略有延迟。

### 示例配置

=== "基本配置"

    这是一个当 CrowdSec 在同一台主机上运行时的一个简单配置：

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "live"
    ```

=== "带有 AppSec 的高级配置"

    一个更全面的配置，包括应用程序安全组件：

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # AppSec 配置
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

### 第&nbsp;3&nbsp;步 – 验证集成

- 在调度器日志中查找 `CrowdSec configuration successfully generated` 和 `CrowdSec bouncer denied request` 条目，以确认插件处于活动状态。
- 在 CrowdSec 端监控 `cscli metrics show` 或 CrowdSec Console，确保 BunkerWeb 的决策按预期显示。
- 在 BunkerWeb UI 中打开 CrowdSec 插件页面查看集成状态。
