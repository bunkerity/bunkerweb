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
    appsec_configs:
      - crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    `appsec_configs`（复数）是一个列表并且是追加式的，因此额外的 AppSec 配置会扩展 `appsec-default` 而不是替换它。单数形式的 `appsec_config` 只接受一个名称，且不能与复数键同时使用——如果打算启用机器人检测，请使用复数形式。

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
        image: bunkerity/bunkerweb:1.7.0-beta
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
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
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
        image: crowdsecurity/crowdsec:v1.7.8 # 使用最新版本，但为了更好的稳定性和安全性，请始终固定版本
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
    appsec_configs:
      - crowdsecurity/appsec-default
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

应用以下环境变量（或通过调度器设置的值），让 BunkerWeb 实例能够与 CrowdSec 本地 API 通信。至少需要设置 `USE_CROWDSEC`、`CROWDSEC_API` 和 `CROWDSEC_API_KEY`，并使用通过 `cscli bouncers add` 生成的有效密钥。

| 设置                        | 默认值                 | 上下文    | 多个 | 描述                                                                                                  |
| --------------------------- | ---------------------- | --------- | ---- | ----------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | 否   | **启用 CrowdSec：** 设置为 `yes` 以启用 CrowdSec 拦截器。                                             |
| `CROWDSEC_API`              | `http://crowdsec:8080` | multisite    | 否   | **CrowdSec API URL：** CrowdSec 本地 API 服务的地址。                                                 |
| `CROWDSEC_API_KEY`          |                        | multisite    | 否   | **CrowdSec API 密钥：** 用于向 CrowdSec API 进行身份验证的 API 密钥，使用 `cscli bouncers add` 获取。 |
| `CROWDSEC_MODE`             | `live`                 | multisite    | 否   | **操作模式：** `live`（为每个请求查询 API）或 `stream`（定期缓存所有决策）。                          |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | multisite    | 否   | **内部流量：** 设置为 `yes` 以根据 CrowdSec 决策检查内部流量。                                        |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | multisite    | 否   | **请求超时：** 在实时模式下向 CrowdSec 本地 API 发出 HTTP 请求的超时时间（以毫秒为单位）。            |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | multisite    | 否   | **排除的位置：** 从 CrowdSec 检查中排除的位置（URI）列表，以逗号分隔。                                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | multisite    | 否   | **缓存过期时间：** 在实时模式下，IP 决策的缓存过期时间（以秒为单位）。                                |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | multisite    | 否   | **更新频率：** 在流模式下，从 CrowdSec API 拉取新的/过期的决策的频率（以秒为单位）。                  |

!!! info "`CROWDSEC_EXCLUDE_LOCATION` 的匹配方式"
    每个以逗号分隔的条目都会排除该 URI **及其下的所有内容**：`/health` 会跳过 `/health` 和 `/health/live`，但不会跳过 `/healthcheck`——路径其余部分之前始终需要一个分隔符。排除是彻底的：被排除的请求既不会到达 Local API，也不会到达 AppSec 组件，因此不要排除仍希望被检查的路径。尤其不要排除 `/crowdsec-internal`：机器人检测从该路径提供其质询资源，排除它会静默地禁用质询。

#### 应用程序安全组件设置

| 设置                              | 默认值        | 上下文 | 多个 | 描述                                                                              |
| --------------------------------- | ------------- | ------ | ---- | --------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |               | multisite | 否   | **AppSec URL：** CrowdSec 应用程序安全组件的 URL。留空以禁用 AppSec。             |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | multisite | 否   | **失败操作：** 当 AppSec 返回错误时要采取的操作。可以是 `passthrough` 或 `deny`。 |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | multisite | 否   | **连接超时：** 连接到 AppSec 组件的超时时间（以毫秒为单位）。                     |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | multisite | 否   | **发送超时：** 向 AppSec 组件发送数据的超时时间（以毫秒为单位）。                 |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | multisite | 否   | **处理超时：** 在 AppSec 组件中处理请求的超时时间（以毫秒为单位）。               |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | multisite | 否   | **始终发送：** 设置为 `yes` 以始终将请求发送到 AppSec，即使存在 IP 级别的决策。   |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | multisite | 否   | **SSL 验证：** 设置为 `yes` 以验证 AppSec 组件的 SSL 证书。                       |

!!! info "关于操作模式"
    - **实时模式**会为每个传入的请求查询 CrowdSec API，提供实时的保护，但会增加延迟。
    - **流模式**会定期从 CrowdSec API 下载所有决策并将其本地缓存，从而减少延迟，但应用新决策会略有延迟。

### 机器人检测（CrowdSec 1.8+）

CrowdSec 1.8 为 AppSec 组件加入了机器人检测。AppSec 组件不再直接封禁可疑客户端，而是可以返回一个**质询**：一个自包含的页面，对浏览器进行指纹识别并要求其完成工作量证明，随后由 CrowdSec 端对结果评分。BunkerWeb 会原样提供该页面——状态码、响应头、Cookie 均与 CrowdSec 生成的完全一致，且仍位于原始 URI 上——并且绝不会把该请求转发给您的应用。未通过的客户端仍由 BunkerWeb 自己的封禁页面拒绝，因此封禁体验没有任何变化。

机器人检测**默认未启用**：只要引擎发出质询，bouncer 就会转发它；但只有在您安装该集合并加载其配置之后，引擎才会发出质询。

**在独立的 CrowdSec 引擎上启用**

```shell
cscli collections install crowdsecurity/appsec-bot-challenge
```

然后把它安装的配置与 `appsec-default` 一起加入 AppSec 采集文件：

```yaml
appsec_configs:
  - crowdsecurity/appsec-default
  - crowdsecurity/appsec-bot-*
labels:
  type: appsec
listen_addr: 0.0.0.0:7422
source: appsec
```

重启 CrowdSec，然后用 `cscli alerts list --kind bot-detection` 确认拒绝记录。

三个现成的捆绑包决定拒绝阈值：`crowdsecurity/appsec-bot-challenge` 在评分达到 75 时拒绝，`crowdsecurity/appsec-bot-challenge-strict` 为 45，`crowdsecurity/appsec-bot-challenge-permissive` 为 100。请只安装您需要的那个——它们是可选项，而不是叠加层。

**在 All-In-One 镜像上启用**

在容器上设置 `CROWDSEC_EXTRA_COLLECTIONS` 并重启；入口脚本会安装该集合，并替您把它的配置加入 AppSec 采集文件：

```shell
docker run -d --name bunkerweb-aio \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_APPSEC_URL=http://127.0.0.1:7422 \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/appsec-bot-challenge" \
  bunkerity/bunkerweb-all-in-one:1.7.0-beta
```

!!! warning "被质询的客户端需要 JavaScript 和 Cookie"
    质询页面会运行脚本并把结果保存在 Cookie 中。任何两者皆无的正常客户端——API 调用方、监控探针、订阅源阅读器、大多数命令行工具——都无法完成质询，并会被反复质询。请**在 CrowdSec 一侧**排除或放行它们（该捆绑包自带针对搜索引擎、监控、订阅源、静态文件和 API 路径的排除配置），而不要使用 `CROWDSEC_EXCLUDE_LOCATION`——它会关闭该路径上的所有 CrowdSec 检查，而不仅仅是质询。

!!! warning "CrowdSec 主机需要可执行内存映射"
    质询由一个 WebAssembly 运行时在服务端进行混淆，而 CrowdSec 只以编译器模式运行它——没有解释器回退。因此**运行 CrowdSec 的主机**在 amd64 上需要 SSE4.1（arm64 无此要求），并且内核必须允许把可写映射转为可执行。在启用 W^X 加固的主机上，或在严格的 seccomp、SELinux 策略下，CrowdSec 会在启动时记录 `failed to create wasm runtime in compiler mode` 或 `the kernel likely denied an executable memory mapping`，机器人检测将保持关闭。这是对引擎所在主机的要求，而不是对访问者浏览器的要求。

!!! tip "保留质询页面的 Content-Security-Policy"
    CrowdSec 始终会为质询页面附加一个 Content-Security-Policy，页面运行时需要它。BunkerWeb 会保留它，因为 `Content-Security-Policy` 在 `KEEP_UPSTREAM_HEADERS` 的默认值中。有两个设置会绕过该列表并破坏质询：用 `CUSTOM_HEADER` 自行设置 `Content-Security-Policy`，以及把它列入 `REMOVE_HEADERS`。若使用其中任何一个，实例会在启动时记录一条指明该设置的警告。

**在「报告」页面读取 CrowdSec 的裁决**

每一次 CrowdSec 处置都会记录为一条报告，报告现在会说明裁决内容，而不再只写 `crowdsec`。**报告**页面会把它显示为一句话 —— *CrowdSec AppSec: bot-detection challenge*、*CrowdSec LAPI: request blocked (scenario: crowdsecurity/http-probing)* —— 报告详情则在下方保留原始字段：`source`（`appsec` 或 `lapi`）、`action`（`ban`、`captcha` 或 `challenge`）、`http_status`（处置所*声明*的状态码，未必就是实际下发的：LAPI 封禁不带该字段，而 AppSec 封禁声明 403，BunkerWeb 却以 `DENY_HTTP_STATUS` 应答），以及决策来自本地 API 时的 `scenario`、`origin` 和 `duration`。

已下发的质询返回的是 200 而不是拦截状态码，而报告过滤器保留的是 4xx、`detect` 和 stream 行 —— 只看状态码的话，该质询会被丢弃。现在过滤器改为按**原因**保留 CrowdSec 的处置，无论以什么状态结束，因此质询会被显示。在 `SECURITY_MODE=detect` 下不会下发任何内容，裁决会说明*本应*执行的处置，否则它是不可见的 —— bouncer 自身的告警行只在产生响应的分支上触发。

!!! info "只有新鲜决策才带场景"
    本地 API 的决策只在实时查询时携带场景。处置一旦进入缓存，缓存只保存处置本身，因此同一客户端的后续请求只会报告动作而没有场景。AppSec 裁决从不携带场景：它根本不来自某个决策。

### 验证码处置（由 BunkerWeb 的 antibot 渲染）

CrowdSec 的 `captcha` 决策意思是*证明你是人类*，而不是*走开*。BunkerWeb 用**自己的 antibot 挑战**来回应它，而不是 CrowdSec 的验证码页面：站点提供的所有挑战外观统一，无需管理第二套验证码密钥，而且 CrowdSec 不提供的方式 —— `javascript`、`cookie`、`mcaptcha`、`capjs` —— 也可用于 CrowdSec 决策。

| 参数                        | 默认值    | 上下文    | 多个 | 描述                                                                                            |
| --------------------------- | --------- | --------- | ---- | ------------------------------------------------------------------------------------------------- |
| `CROWDSEC_CAPTCHA_PROVIDER` | `captcha` | multisite | 否   | **验证码挑战：** 当 CrowdSec 要求验证码时显示哪种 antibot 挑战。设为 `no` 可忽略验证码决策。      |

它接受与 `USE_ANTIBOT` 相同的取值：`cookie`、`javascript`、`captcha`、`recaptcha`、`hcaptcha`、`turnstile`、`mcaptcha`、`capjs`。第三方方式从 antibot 自身的 `ANTIBOT_*` 设置中读取密钥，无需重复配置。

!!! warning "服务上必须启用 antibot"
    只有 `USE_ANTIBOT` 设为 `no` 以外的值（或存在 workflow 挑战规则）的服务才有挑战页面。在没有它的服务上，`captcha` 决策会被**封禁**而不是挑战，实例会记录一行同时点名这两个设置的日志。`USE_ANTIBOT: "cookie"` 是最省事的开启方式：普通访客一个来回即可通过，而被 CrowdSec 标记的客户端会看到 `CROWDSEC_CAPTCHA_PROVIDER` 指定的挑战。

!!! warning "升级后行为会改变"
    此前 BunkerWeb 只对 `ban` 决策作出反应，因此本地 API 的 `captcha` 决策从未被拉取，也毫无效果。现在它会被拉取、缓存并生效，渲染上述挑战。若要保留原有行为，请设置 `CROWDSEC_CAPTCHA_PROVIDER: "no"`：验证码决策将与以前完全一样被忽略。请注意，放宽后的过滤器是 `BOUNCING_ON_TYPE=all`，而不是 `ban`+`captcha` 的组合 —— bouncer 只接受一个值 —— 因此您的 CrowdSec 配置文件发出的**任何其他**类型的决策现在也会生效，并且由于 bouncer 无法识别，会按封禁处理。而且，**只有共享同一个 CrowdSec 本地 API 的每个服务都设置它**，退出选项才能完全恢复原有行为：决策缓存按本地 API 分区，而不是按服务分区（`cache_partition.lua`），因此保持默认值的同级服务会缓存该验证码决策，而选择退出的服务读回它并据此封禁。

!!! tip "`cookie` 在这里证明不了什么"
    `cookie` 方式会自行解开，不会向访客提出任何要求。作为 `USE_ANTIBOT` 的取值它便宜又合理，但作为 `CROWDSEC_CAPTCHA_PROVIDER`，它要付出两次重定向，并对一个意为*证明你是人类*的决策授予整个会话有效的通行证。请优先选择 `captcha`、`javascript` 或 `capjs`。

!!! info "CrowdSec 永远不会知道验证码已被解开"
    挑战是对 BunkerWeb 解开的，而不是对引擎，因此 `cscli metrics` 不会统计验证码，`CAPTCHA_EXPIRATION` 不适用，同一本地 API 上的其他 bouncer 仍会挑战同一客户端。保存答案的是访客的 BunkerWeb 会话：一旦解开，该浏览器在其会话有效期内不会再被挑战 —— 即使期间同一地址出现了**新的**验证码决策也是如此。任何没有该会话的客户端（另一个浏览器、另一台设备、清空过的 Cookie 存储）都会被正常挑战。

### 将裁决交给安全工作流

CrowdSec 的裁决可以由你自己的**安全工作流**来回应，而不是由 CrowdSec 自己的处置动作决定：带有*CrowdSec 裁决*条件的规则可以按你的方式对被标记的请求发起挑战、重定向或拦截。

| 设置                          | 默认值 | 上下文    | 多个 | 描述                                                                     |
| ----------------------------- | ------ | --------- | ---- | ------------------------------------------------------------------------ |
| `CROWDSEC_DEFER_TO_WORKFLOWS` | `no`   | multisite | 否   | **让安全工作流决定：** 把裁决交给附加到该服务的工作流，而不是在此处直接应用。 |

该条件读取两个事实：裁决的**来源**（`appsec` 或 `lapi`）以及 CrowdSec 要求的**处置**（`ban` 或 `captcha`；`challenge` 由 CrowdSec 在工作流运行之前自行响应，因此不提供该取值）。CrowdSec 未曾判断过的请求会让该条件处于未决状态，因此永远不会匹配；CrowdSec 判断过且没有异议的请求则使其为假。

!!! warning "默认不会放开任何东西"
    使用默认值 `no` 时，CrowdSec 仍像以前一样自行应用裁决。设为 `yes` 时，只要没有工作流规则匹配，裁决就会被原样应用；若该服务根本没有附加任何工作流，实例会记录一行同时指出这两个设置的日志。

!!! info "裁决等待期间仍有三种响应来自 BunkerWeb"
    CORS 预检（`204`）、`/robots.txt` 和 `/security.txt` 由 BunkerWeb 在工作流之前生成，因此被标记的客户端仍可能收到这三种响应。它们都不会到达你的应用，而所有会到达应用的请求都会先经过工作流阶梯。

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
