# Web 界面

## Web 界面的角色

Web 界面是 BunkerWeb 的可视化控制平面。它无需 CLI 即可管理服务、全局设置、封禁、插件、任务、缓存、日志和升级。它是 Flask + Gunicorn 应用，通常部署在 BunkerWeb 反向代理之后。

!!! warning "请放在 BunkerWeb 后面"
    UI 可以更改配置、运行任务并部署自定义片段。请放在受信任的网络中，通过 BunkerWeb 暴露，并使用强凭据与 2FA 保护。

!!! info "要点"
    - 默认监听：容器 `0.0.0.0:7000`，包版 `127.0.0.1:7000`（可用 `UI_LISTEN_ADDR` / `UI_LISTEN_PORT` 修改）
    - 反代感知：通过 `UI_FORWARDED_ALLOW_IPS` 信任 `X-Forwarded-*`；若多级代理附加头部，请设置 `PROXY_NUMBERS`
    - 认证：本地管理员（密码策略强制），可选角色，TOTP 2FA 依赖 `TOTP_ENCRYPTION_KEYS`
    - 会话：由 `FLASK_SECRET` 签名，默认 12 小时，绑定 IP 与 User-Agent；`ALWAYS_REMEMBER` 控制持久 Cookie
    - 日志：`/var/log/bunkerweb/ui.log`（捕获时包含 access log），容器内 UID/GID 为 101
    - 健康检查：`ENABLE_HEALTHCHECK=yes` 时提供 `GET /healthcheck`
    - 依赖：通过 API 访问配置和数据；UI 不直接访问数据库，API 管理数据并触发实例操作

## 安全清单

- 在内部网络通过 BunkerWeb 暴露 UI；选择难猜的 `REVERSE_PROXY_URL` 并限制来源 IP。
- 设置强 `ADMIN_USERNAME` / `ADMIN_PASSWORD`；仅在需要时开启 `OVERRIDE_ADMIN_CREDS=yes` 来重置。
- 提供 `TOTP_ENCRYPTION_KEYS` 并为管理员启用 TOTP；妥善保存恢复码。
- 优先使用通行密钥：设置 `UI_WEBAUTHN_RP_ID`（或单一 `UI_ALLOWED_HOSTS` 条目），每个帐户至少注册两枚，以免设备丢失后无法登录。通行密钥不会为错误来源签名，可抵御钓鱼。
- 使用 TLS（在 BunkerWeb 终止或 `UI_SSL_ENABLED=yes` 并提供证书/密钥路径）；将 `UI_FORWARDED_ALLOW_IPS` 设为可信代理。
- 持久化秘密：挂载 `/var/lib/bunkerweb` 以保留 `FLASK_SECRET`、Biscuit 密钥与 TOTP 数据。
- 保持 `CHECK_PRIVATE_IP=yes`（默认）以绑定会话到客户端 IP；若无长期会话需求，将 `ALWAYS_REMEMBER` 维持为 `no`。
- 确保 `/var/log/bunkerweb` 对 UID/GID 101（或 rootless 映射 UID）可读，便于 UI 读取日志。

## 运行方式

UI 需要能够访问 BunkerWeb API；控制平面堆栈还需要调度器、任务 Worker、任务代理和共享数据库。

=== "快速开始（向导）"

    使用已发布镜像与[快速入门](quickstart-guide.md#__tabbed_1_3)的布局启动栈，然后在浏览器完成向导。

=== "高级（预设环境变量）"

    预置凭据和网络以跳过向导；下面是带 syslog sidecar 的 Compose 示例：

    ```yaml
    x-service-env: &service-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      API_URL: "http://bw-api:8888"
      API_TOKEN: "changeme" # Replace this shared token before deploying
      CELERY_BROKER_URL: "redis://bw-jobs-broker:6379/0"
      LOG_TYPES: "stderr syslog" # Service logs from supporting components
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.7.0-beta
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *service-env
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-instance-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-api:
        image: bunkerity/bunkerweb-api:1.7.0-beta
        restart: "unless-stopped"
        environment:
          <<: *service-env
          API_USERNAME: "changeme"
          API_PASSWORD: "Ch@ngeme1234"
        networks:
          - bw-universe
          - bw-db

      bw-worker:
        image: bunkerity/bunkerweb-worker:1.7.0-beta
        restart: "unless-stopped"
        depends_on:
          - bw-api
          - bw-jobs-broker
        volumes:
          # Its own volume: DATABASE_URI points at a real server here, so this /data holds
          # nothing but a scratch tree the worker rebuilds from the database -- no reason to
          # share the scheduler's. The SQLite stack (docker.yml) does share it, because there
          # the database IS a file under /data.
          - bw-worker-storage:/data
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb"
        networks:
          - bw-universe
          - bw-db

      bw-jobs-broker:
        image: valkey/valkey:8-alpine
        # noeviction on purpose: a broker that evicts under memory pressure drops queued
        # jobs on the floor, and nothing upstream would notice.
        # appendonly on purpose: a broker restart must not vaporise queued jobs.
        # AOF, not RDB ("--save" stays empty) — a 60s RDB loss window on a job queue
        # means silently dropped work, which is what the at-least-once acks exist to stop.
        command:
          [
            "valkey-server",
            "--save",
            "",
            "--appendonly",
            "yes",
            "--maxmemory",
            "256mb",
            "--maxmemory-policy",
            "noeviction",
          ]
        volumes:
          - bw-jobs-broker-data:/data
        healthcheck:
          test: ["CMD", "valkey-cli", "ping"]
          interval: 5s
          timeout: 3s
          retries: 10
          start_period: 5s
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
          ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"
          DISABLE_DEFAULT_SERVER: "yes"
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

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.7.0-beta
        environment:
          <<: *service-env
          ADMIN_USERNAME: "admin"
          ADMIN_PASSWORD: "Str0ng&P@ss!" # Remember to set a stronger password for the admin user
          # TOTP_ENCRYPTION_KEYS: "changeme" # Optional: generated in the bw-ui-data volume when unset; a key must be 43 characters
          UI_FORWARDED_ALLOW_IPS: "10.20.30.0/24"
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - bw-ui-data:/data # This is used to persist the UI secrets (Flask secret, TOTP encryption keys, Biscuit keys)
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
      bw-instance-data:
      bw-worker-storage:
      bw-jobs-broker-data:
      bw-data:
      bw-storage:
      bw-logs:
      bw-ui-data:

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

    添加 `bunkerweb-autoconf`，并在 UI 容器上使用标签而不是显式的 `BUNKERWEB_INSTANCES`。Scheduler 仍通过 `ui` 模板和秘密的 `REVERSE_PROXY_URL` 为 UI 做反代。

=== "Linux"

    软件包提供 `bunkerweb-ui` systemd 服务。通过 easy-install 会自动启用（向导默认也会启动）。需要调整时编辑 `/etc/bunkerweb/ui.env`，然后：

    ```bash
    sudo systemctl enable --now bunkerweb-ui
    sudo systemctl restart bunkerweb-ui  # 修改后
    ```

    通过 BunkerWeb 做反代（模板 `ui`，`REVERSE_PROXY_URL=/changeme`，上游 `http://127.0.0.1:7000`）。挂载 `/var/lib/bunkerweb` 和 `/var/log/bunkerweb` 以持久化秘密和日志。

### Linux 与 Docker 差异

- 监听默认值：Docker 镜像在 `0.0.0.0:7000`，Linux 包在 `127.0.0.1:7000`。可用 `UI_LISTEN_ADDR` / `UI_LISTEN_PORT` 覆盖。
- 代理头：`UI_FORWARDED_ALLOW_IPS` 默认 `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`；`UI_PROXY_ALLOW_IPS` 默认取 `FORWARDED_ALLOW_IPS` 的值。在 Linux 安装中将其设为反代 IP 以更严格。
- 秘密与状态：`/var/lib/bunkerweb` 保存 `FLASK_SECRET`、Biscuit 密钥和 TOTP 数据。Docker 需挂载；Linux 由包脚本创建管理。
- 日志：`/var/log/bunkerweb` 需对 UID/GID 101（或 rootless 映射 UID）可读。包会创建路径；容器需挂载权限正确的卷。
- 向导行为：Linux easy-install 自动启动 UI 和向导；Docker 需通过反代 URL 访问向导，除非预置环境变量。

## 认证与会话

- 管理员账户：通过向导或 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 创建。密码必须包含大小写字母、数字和特殊字符。`OVERRIDE_ADMIN_CREDS=yes` 会在已有账户时强制重置。
- 密码长度限制：bcrypt 只使用秘密的前 **72 字节**，因此所有设置密码的位置（设置向导、个人资料页面、`ADMIN_PASSWORD` / `API_PASSWORD`）都会将密码限制为 72 字节。更长的值会被拒绝，并给出明确的错误或日志，而不是静默截断。请注意，非 ASCII 字符（重音字符、emoji）每个都会占用多个字节；由这些字符组成的“72 字符”口令可能超过该限制。预哈希的 bcrypt 值不受影响（哈希本身已经编码了该限制）。
- 角色：`admin`、`writer`、`reader` 会自动创建；账户存储在数据库。
- 秘密：`FLASK_SECRET` 存于 `/var/lib/bunkerweb/.flask_secret`；Biscuit 密钥位于同目录，可用 `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY` 提供。
- 2FA：用 `TOTP_ENCRYPTION_KEYS`（空格分隔或 JSON）开启 TOTP。生成密钥：

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    恢复码在 UI 中仅显示一次；若丢失加密密钥，将清除已存的 TOTP 秘钥。
- 通行密钥（WebAuthn / FIDO2）：`UI_WEBAUTHN_RP_ID` 解析成功后，个人资料的**安全**选项卡显示**通行密钥**卡片。已注册通行密钥可不输入用户名或密码直接登录，由认证器本地验证用户，也无需 TOTP。可注册多枚，通常每个设备一枚；每枚可命名，并显示创建和最近使用时间。较旧的不可发现 FIDO2 安全密钥不能独立登录，但可在输入密码后替代 TOTP。

    通行密钥是替代登录方式，不是额外关卡。注册后不会要求密码登录再提供通行密钥，因为它没有恢复代码，丢失设备可能永久锁定帐户。密码和 TOTP 保持原有行为；需要强制第二因素时，请使用带恢复代码的 TOTP。
- 会话：默认空闲时长 12 小时（`SESSION_LIFETIME_HOURS`），每次请求刷新。`SESSION_ABSOLUTE_HOURS`（默认 `168` = 7 天）设定绝对上限——无论是否活跃，超过即强制登出。可选的会话 ID 轮换（`SESSION_ROLLING_HOURS`，默认 `0` = 关闭）按该间隔重新生成会话 ID。会话绑定 IP 与 User-Agent；`CHECK_PRIVATE_IP=no` 仅对私网放宽 IP 检查。`ALWAYS_REMEMBER=yes` 始终启用持久 Cookie。
- 若多级代理附加 `X-Forwarded-*`，请设置 `PROXY_NUMBERS`。

!!! tip "预哈希管理员密码"
    `ADMIN_PASSWORD` 接受 **bcrypt 哈希**（`$2a$`/`$2b$`/`$2y$`）并按原样存储，明文不再留在环境文件或密钥中。跳过强度策略（源密码由你负责）；成本因子低于 `10` 会被拒绝，`10`–`11` 会记录警告（推荐 `12`+）。仅限环境创建和 `OVERRIDE_ADMIN_CREDS`；向导和个人资料页面仍需明文。

    生成哈希：

    ```bash
    python3 -c "import bcrypt; print(bcrypt.hashpw(b'Str0ng&P@ss!', bcrypt.gensalt(rounds=13)).decode())"
    ```

!!! warning "错误的哈希会将你锁定"
    仅在知道哈希对应的明文时才使用。首次创建时使用有效但错误的哈希不可逆，重启也无法修复；需用不同的 `ADMIN_PASSWORD` 配合 `OVERRIDE_ADMIN_CREDS=yes` 恢复。

!!! warning "重建容器后 2FA 会丢失"
    TOTP 密钥以加密形式存储在数据库中，但用于解密它们的密钥保存在**磁盘上**，而不是数据库里。每次启动时，界面会采用第一个可用来源：`/var/lib/bunkerweb/.totp_encryption_keys.json`，然后是旧的 `.totp_secrets.json`，再然后是 `TOTP_ENCRYPTION_KEYS`（别名 `TOTP_SECRETS`）。若都不可用，它会生成一组新的随机密钥，已存储的密钥将无法再解密，管理员的绑定会从数据库中移除，所有用户都必须重新绑定。

    重启容器没有影响。真正导致密钥丢失的是丢掉容器文件系统：先 `docker compose down` 再 `up`、镜像或环境变更后的重建、`docker rm`，或者一个新的 Pod。只需在 `bw-ui` 容器的 `/data` 上挂载持久卷即可，本页的每个示例都这样做——镜像中 `/var/lib/bunkerweb` 是指向 `/data/lib` 的符号链接——因此 `TOTP_ENCRYPTION_KEYS` 是可选的。

    只有在该卷无法持久化，或需要自行控制轮换时，才手动设置该变量。若要设置，请注意长度：像 `changeme` 这样的占位符**不是**有效密钥——密钥长度为 43 个字符，由 `passlib` 的 `generate_secret()` 生成。无效值会被丢弃并替换为随机密钥；并且与未设置该变量不同，它还会阻止管理员绑定被重置，因此在手动清除之前 2FA 将一直不可用。轮换可通过 JSON 映射完成：把旧密钥与新密钥一并保留，已有的绑定仍然有效。

## 配置来源与优先级

1. 环境变量（含 Docker/Compose `environment:`）
2. `/run/secrets/<VAR>` 中的秘密（Docker）
3. `/etc/bunkerweb/ui.env`（Linux 包）
4. 内置默认值

## 配置参考

### 运行时与时区

| 设置 | 描述                    | 可接受值                             | 默认值               |
| ---- | ----------------------- | ------------------------------------ | -------------------- |
| `TZ` | UI 日志和计划任务的时区 | TZ 名称（如 `UTC`、`Asia/Shanghai`） | 未设（容器通常 UTC） |

### 监听与 TLS

| 设置                                | 描述                         | 可接受值              | 默认值                                                |
| ----------------------------------- | ---------------------------- | --------------------- | ----------------------------------------------------- |
| `UI_LISTEN_ADDR`                    | UI 监听地址                  | IP 或主机名           | `0.0.0.0`（Docker） / `127.0.0.1`（包）               |
| `UI_LISTEN_PORT`                    | UI 监听端口                  | 整数                  | `7000`                                                |
| `LISTEN_ADDR`, `LISTEN_PORT`        | UI 变量缺失时的备用          | IP/主机名，整数       | `0.0.0.0`, `7000`                                     |
| `UI_SSL_ENABLED`                    | 在 UI 容器中启用 TLS         | `yes` 或 `no`         | `no`                                                  |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | 启用 TLS 时的证书/密钥路径   | 文件路径              | 未设                                                  |
| `UI_SSL_CA_CERTS`                   | 可选 CA/链                   | 文件路径              | 未设                                                  |
| `UI_FORWARDED_ALLOW_IPS`            | 信任的代理 IP/CIDR           | 空格/逗号分隔 IP/CIDR | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `UI_PROXY_ALLOW_IPS`                | PROXY 协议的可信代理 IP/CIDR | 空格/逗号分隔 IP/CIDR | `FORWARDED_ALLOW_IPS`                                 |

### 认证、会话与 Cookie

| 设置                                        | 描述                                                                              | 可接受值                     | 默认值         |
| ------------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------- | -------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | 初始化管理员账户（执行密码策略；`ADMIN_PASSWORD` 也接受 bcrypt 哈希，按原样存储） | 字符串 / bcrypt 哈希         | 未设           |
| `OVERRIDE_ADMIN_CREDS`                      | 强制用环境变量更新管理员凭据                                                      | `yes` 或 `no`                | `no`           |
| `FLASK_SECRET`                              | 会话签名密钥（存于 `/var/lib/bunkerweb/.flask_secret`）                           | 十六进制/Base64/不透明字符串 | 自动生成       |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | TOTP 秘钥加密键（空格或 JSON）                                                    | 字符串 / JSON                | 缺失时自动生成 |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Biscuit 密钥（hex），用于 UI token                                                | Hex 字符串                   | 自动生成并存储 |
| `SESSION_LIFETIME_HOURS`                    | 会话空闲时长（滑动 TTL，每次请求刷新）                                            | 数值（小时）                 | `12`           |
| `SESSION_ABSOLUTE_HOURS`                    | 与活动无关的绝对会话上限                                                          | 数值（小时）                 | `168`          |
| `SESSION_ROLLING_HOURS`                     | 会话 ID 轮换间隔（`0` 关闭轮换）                                                  | 数值（小时）                 | `0`            |
| `ALWAYS_REMEMBER`                           | 总是启用 “remember me”                                                            | `yes` 或 `no`                | `no`           |
| `CHECK_PRIVATE_IP`                          | 绑定会话到 IP（`no` 时放宽私网变更）                                              | `yes` 或 `no`                | `yes`          |
| `PROXY_NUMBERS`                             | 信任的 `X-Forwarded-*` 代理层数                                                   | 整数                         | `1`            |
| `UI_WEBAUTHN_RP_ID` | WebAuthn 依赖方 ID，不带协议或端口；默认取唯一非通配 `UI_ALLOWED_HOSTS` 条目 | 域名 | 可推导则使用，否则关闭 |
| `UI_WEBAUTHN_ORIGINS` | 认证流程接受的精确来源 | 空格或逗号分隔的 URL | `https://<RP ID>` |

!!! warning "RP ID 是安全边界的一部分"
    WebAuthn 凭据与依赖方 ID 加密绑定，绝不从攻击者可控的请求 `Host` 头推导。解析顺序：显式 `UI_WEBAUTHN_RP_ID`；否则唯一且非通配的 `UI_ALLOWED_HOSTS` 条目（去掉 `:port`）；否则关闭通行密钥并在启动时记录原因。

    **改变 UI 域名会让所有已注册通行密钥失效。** RP ID 由认证器写入凭据，不能迁移；用户须在新域名重新注册。迁移域名前保留 TOTP 或密码登录方式。认证流程要求 HTTPS 安全上下文，规范豁免的 `localhost` 除外，因此开发堆栈 `http://localhost:7000` 可用。

### 证书管理器

| 设置 | 说明 | 接受的值 | 默认值 |
| ---- | ---- | -------- | ------ |
| `CERTIFICATE_ENCRYPTION_KEYS` | 用 AES-256-GCM 加密已存证书私钥的密钥环 | 密钥 ID 到 base64 编码 32 字节密钥的 JSON 对象 | 未设置 |
| `CERTIFICATE_ENCRYPTION_ACTIVE_KEY` | 新导入或生成私钥使用的密钥 ID | 密钥环中已有的密钥 | 未设置 |

创建、导入和续期自签名证书需要这两个变量。只要已存证书仍使用旧密钥 ID，就必须保留它；所有处理证书的 API 和 Worker 进程应使用相同密钥环。证书下载端点永不提供私钥。

`/certificates` 管理共享清单（列表、元数据、分配、非托管证书删除、公开下载）。生命周期由提供者插件负责：`/selfsigned/certificates` 创建和续期自签名证书，`/customcert/certificates/upload` 导入 PEM，`/letsencrypt/certificates` 调度 ACME 任务并提供孤立状态只读查询。UI 始终通过 API 操作。

证书管理器中的服务分配用于组织清单，不替代控制实际 TLS 部署的逐服务 Let's Encrypt 或自定义证书设置。

Let's Encrypt 清单从 certbot 缓存同步。在证书 Worker 能持久确认并重试定向缓存操作前，不提供由提供者管理的删除操作；移除 ACME 状态尚不会自动删除对应托管清单记录。

### 日志

| 设置                            | 描述                                                       | 可接受值                                        | 默认值                                        |
| ------------------------------- | ---------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | 日志级别 / 覆盖                                            | `debug`, `info`, `warning`, `error`, `critical` | `info`                                        |
| `LOG_TYPES`                     | 目标                                                       | 空格分隔 `stderr`/`file`/`syslog`               | `stderr`                                      |
| `LOG_FILE_PATH`                 | 文件日志路径（`file` 或 `CAPTURE_OUTPUT=yes` 时）          | 文件路径                                        | 启用文件/捕获时为 `/var/log/bunkerweb/ui.log` |
| `CAPTURE_OUTPUT`                | 将 Gunicorn stdout/stderr 发给日志处理                     | `yes` 或 `no`                                   | `no`                                          |
| `LOG_SYSLOG_ADDRESS`            | Syslog 目标（`udp://host:514`、`tcp://host:514` 或套接字） | 主机:端口 / URL / 套接字路径                    | 未设                                          |
| `LOG_SYSLOG_TAG`                | Syslog 标签                                                | 字符串                                          | `bw-ui`                                       |

### 其他运行时

| 设置                            | 描述                                            | 可接受值                                | 默认值                                                |
| ------------------------------- | ----------------------------------------------- | --------------------------------------- | ----------------------------------------------------- |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn worker/线程数                          | 整数                                    | `cpu_count()-1`（至少 1），`workers*2`                |
| `MAX_REQUESTS`                  | Worker 回收前的请求数（Gunicorn，防止内存膨胀） | 整数                                    | `1000`                                                |
| `ENABLE_HEALTHCHECK`            | 暴露 `GET /healthcheck`                         | `yes` 或 `no`                           | `no`                                                  |
| `FORWARDED_ALLOW_IPS`           | 代理允许列表的别名                              | IP/CIDR                                 | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `PROXY_ALLOW_IPS`               | PROXY 允许列表的别名                            | IP/CIDR                                 | `FORWARDED_ALLOW_IPS`                                 |
| `DISABLE_CONFIGURATION_TESTING` | 应用配置时跳过测试 reload                       | `yes` 或 `no`                           | `no`                                                  |
| `IGNORE_REGEX_CHECK`            | 跳过设置的正则校验                              | `yes` 或 `no`                           | `no`                                                  |
| `MAX_CONTENT_LENGTH`            | 最大上传大小（Flask `MAX_CONTENT_LENGTH`）      | 带单位的大小（`50M`、`1G`、`52428800`） | `50MB`                                                |

## 日志访问

UI 从 `/var/log/bunkerweb` 读取 NGINX/服务日志。通过 syslog 守护或卷填充该目录：

- 容器 UID/GID 为 101。宿主上设置权限：`chown root:101 bw-logs && chmod 770 bw-logs`（rootless 需调整）。
- 使用 `ACCESS_LOG` / `ERROR_LOG` 将 BunkerWeb 访问/错误日志发送到 syslog sidecar；组件日志用 `LOG_TYPES=syslog`。

写入按程序分文件的 `syslog-ng.conf` 示例：

```conf
@version: 4.10

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

## 功能

- 请求、封禁、缓存和任务的仪表板；重启/重载实例。
- 创建/更新/删除服务和全局设置，并按插件模式校验。
- 上传和管理自定义配置（NGINX/ModSecurity）与插件（外部或 PRO）。
- 查看日志、搜索报表、检查缓存制品。
- 管理 UI 用户、角色、会话及 TOTP（含恢复码）。
- 升级到 BunkerWeb PRO 并在专页查看许可证状态。

### 默认服务器条目 {#the-default-server-entry}

`MULTISITE=yes` 时，服务列表顶部固定显示**默认服务器**，带一行说明；`MULTISITE=no` 时没有此保留条目。它是保留服务 `default-server`，处理不匹配任何服务的请求，如未知主机名、裸 IP、无人提供服务的 `Host`。

打开它可配置证书、TLS、响应头、错误页面和白名单。它没有可路由的主机名或可绑定的服务身份，因此不提供反向代理、gRPC、重定向、会话、Antibot、mTLS、CORS 或 HTTP 基本认证，也没有删除、克隆或转换操作。此服务永久存在且不占 PRO 服务配额。

### 实例注册 {#instance-enrollment}

**实例** 页面上显示的实例可以获得专属于自己的控制面凭据，而不必共用全局 `API_TOKEN`。该行的钥匙按钮（或历史菜单）会签发一个仅显示一次的一次性注册码，实例在启动时通过 `INSTANCE_ENROLLMENT_CODE` 兑换该码；此后它只响应控制面为其铸造的凭据。完整机制，包括 API 端点以及 `manual` 与 `autoconf` 的区别，见 [API 参考](api.md#enrollment-an-alternative-to-setting-credential-by-hand)。

注册适用于通过 UI 或 API 创建的行，也适用于通过环境变量声明的行（`BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*`）——这是 Docker 或 Linux 部署的默认形态。它**不**适用于由 autoconf 发现的行：该行在每次协调时都会从活动的编排器重新取值，这会让环境变量中的令牌重新覆盖已铸造的凭据，因此该行上的注册、轮换和撤销按钮均被禁用。

声明了自己的 `BUNKERWEB_INSTANCE_API_TOKEN_<n>` 的实例，会显示与通过注册码注册相同的**已注册**徽标，因为该页面读取的是"拥有按实例凭据"，而声明的令牌正是以这种方式存储的。此时按钮并非危险操作，但几乎无效：调度器下一次保存配置时会重新取用声明的令牌，这会覆盖已铸造的凭据，并且无论如何都会解除撤销状态。对于给定实例，请二选一——要么注册它，要么为它声明令牌，不要两者都做。

!!! warning "为实例提供持久卷"
    凭据保存在 `/var/lib/bunkerweb` 下，Docker 镜像将其符号链接到 `/data`。如果容器在**没有**为 `/data` 挂载卷的情况下被重新创建，它会丢失凭据，也会丢失本可检测到这种丢失的标记：它会以一个全新、未注册的实例身份回来，而控制面仍然认为它已注册，此后向它推送的每一次配置都会被拒绝，且不会说明原因。挂载了卷之后，实例会自行检测到丢失并**拒绝启动**，并指出原因和修复方法。Linux 软件包本就会持久化 `/var/lib/bunkerweb`，因此这只是容器场景下的注意事项——参见[快速入门指南](quickstart-guide.md)以及 `misc/integrations/` 下的 compose 文件，它们都挂载了该卷。

!!! note "`manual` 行仍然无法在此处删除"
    在此页面上可以注册、轮换或撤销环境中声明的行，但无法删除它——下一次配置保存会依据 `BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*` 重新创建该行。请改为从环境变量中移除该主机名，这同时也会取消其注册。

### 资源组

打开**配置 → 资源组**可维护可复用的 IP/CIDR、国家、ASN、反向 DNS 后缀、User-Agent 模式和 URI 模式列表。每项带有类型和可选注释；可以克隆、导出 JSON，并在修改前检查所有引用。

支持的列表设置通过 `@alias` 引用，例如 `@office 203.0.113.5`。白名单、黑名单、灰名单、Real IP、DNSBL 和 Antibot 支持这些引用。数据库保留别名，生成配置时按设置类型展开，修改资源组后下一次推送会更新所有使用方。工作流通过编辑器选择资源组并保存稳定 ID。

别名包含 1 到 64 个字母、数字、下划线或连字符；`@EU`、`@G7`、`@SCHENGEN` 等内置国家别名被保留。不存在或不含所需类型条目的资源组会被拒绝；被设置或工作流引用的组不能删除。

### 上游池

打开**配置 → 上游池**可维护同时附加到多个服务的可复用 HTTP、gRPC 或 stream 后端池。每个池包括名称、协议 (`http`、`grpc`、`stream`)、负载均衡方式 (`round_robin`、`least_conn`、`ip_hash`)、最多 64 个成员（各自的权重、最大失败次数、失败超时，以及主用/备用/停用角色）、可选 keepalive 连接数和 `backend_ssl` 开关。附加时记录反向代理路径，默认为 `/`；一个池最多附加到 100 个服务。

页面使用 API `/upstreams`：`GET /upstreams` 列出，`POST /upstreams` 创建，`PATCH /upstreams/{id}` 编辑，`DELETE /upstreams/{id}` 删除，`POST/DELETE /upstreams/{id}/attachments[/{service}]` 附加或解除服务。

### 模板

打开**配置 → 模板**可浏览、创建和管理通过 `USE_TEMPLATE` 应用到服务的设置、有序配置步骤和自定义配置。图库显示使用数量（包括草稿服务）和功能徽章；编辑器使用与服务相同的多站点设置目录，可从空白创建或克隆现有模板。社区**模板目录**提供预建模板；安装需要 `admin`，普通 `write` 不够，因为模板可能含未做内容校验的自定义 NGINX 配置。安装或保存时仍会检查所有设置是否存在于当前版本的实时设置表，未知设置会被拒绝。

从 1.7 起，每个服务可按顺序使用多个模板，冲突设置以后者为准。

### Web 缓存管理

**Web 缓存**页面管理反向代理使用的 NGINX 响应缓存。显示实例报告状态、磁盘条目数和大小、实际启用 `USE_PROXY_CACHE` 的服务，以及指标插件提供的 `HIT`、`MISS`、`BYPASS`、`STALE` 等计数器。

可清除一个绝对 HTTP(S) URL 或完整缓存。按 URL 清除会重建精确 `PROXY_CACHE_KEY`；若服务使用自定义键模板，请提供该模板。API 每次最多接受 100 个 URL。

!!! warning "完整清除影响所有使用缓存的服务"
    `scope: "all"` 清除每个可达实例的共享 `proxycache` 区域，不针对单个服务，也不触发 NGINX 重载。不可达实例会被跳过，不会为其排队；请检查逐实例结果后再确认整个集群已清除。

### 报告仪表盘

**报告**页面涵盖被阻断的 HTTP 请求和 STREAM 会话。**概览**绘制所选时段的活动，**攻击模式**按 ModSecurity 规则和攻击类别分组，**主要攻击源**对客户端 IP、国家、ASN 排名，**事件日志**提供服务端搜索、筛选、列排序、事件详情以及 CSV 或 Excel 导出。管理员可封禁单个攻击源、所选行或当前筛选结果中的所有 IP。

报告包括插件阻断的每个请求（4xx）、`SECURITY_MODE=detect` 下仅检测到的请求，以及被阻断的 STREAM 会话。另有三种非阻断状态码的安全动作按其原因保留：由 BunkerWeb 自行返回 200 而不转发到应用的 CrowdSec 1.8 机器人检测挑战页面；返回 3xx 的 `workflows` 重定向规则；以及同样直接提供的 Antibot 挑战页。Antibot 会向受保护服务的每个未识别访客显示挑战，并不限于攻击者，因此繁忙服务会为每次挑战增加报告。首先达到容量上限的是 `METRICS_MAX_BLOCKED_REQUESTS`（每 Worker 内存缓冲区，默认 `1k`；使用 Redis 时为 `METRICS_MAX_BLOCKED_REQUESTS_REDIS`）；满后先淘汰最旧项，真实阻断请求也可能为挑战报告腾出空间。应先增加该值，再调整 `METRICS_RETENTION_DAYS` 和 `METRICS_RETENTION_MAX_ROWS`。分析选项卡不受影响：**概览**、**主要攻击源**和威胁地图仅统计阻断及检测请求，不统计已提供的挑战。

插件记录决策时，**原因**列会显示语句，例如 “CrowdSec AppSec: bot-detection challenge”、“CrowdSec LAPI: request blocked (scenario: …)”、“Antibot challenge (captcha) served” 或 “Security workflow api-shield: redirect”，而不仅是 `crowdsec`、`antibot`、`workflows`。事件详情仍保留原始字段。排序和原因筛选仍使用底层值，因此已保存筛选条件的含义不变。

`METRICS_PERSIST_TO_DB=yes` 默认提供可持久、集中查询的事件日志；`METRICS_RETENTION_DAYS` 和 `METRICS_RETENTION_MAX_ROWS` 限制历史保留。关闭持久化时报告留在实例内存或 Redis，可能更早过期。指标 API 不可用时，事件日志回退到旧的实例/Redis 查询；分析选项卡显示空状态，直到指标恢复。

### 威胁地图

**威胁地图**是面向个人和大屏的持久报告视图：世界地图上的弧线从被阻断请求的来源国家连到象征性中心，表示来源而非地理定位攻击；不收集坐标，服务名也没有地理位置。页面还有按国家着色的流量图、主要攻击源面板和近期事件滚动条。需要 `METRICS_PERSIST_TO_DB=yes`；关闭时会说明原因。全屏可隐藏应用外框，数据从 `GET /threatmap/data` 刷新，比实际流量晚约一到两分钟，即底层报告采集任务的间隔。

### 耗时

**耗时**页面展示 `METRICS_COLLECT_TIMINGS` 数据，按插件和阶段汇总整个集群的请求耗时，并按总开销排序。百分比分母是指标插件始终记录的 `request` 阶段整请求时长。不是每请求运行一次的阶段（`init`、`init_worker(s)`、`timer`、内部 API）没有百分比，因为无法分摊到单个请求。没有实例报告时，页面会区分功能未启用（查询 `METRICS_COLLECT_TIMINGS`）与 API 不可达。

### 延迟的任务运行

**任务** 页面除了常见的绿色成功和红色失败徽标外，还可能显示第三种运行结果：**已延迟 — 等待实例启动**，采用警告色并带有时钟图标。当某个任务——常见情形是 `push-configs` 发现所有已注册实例均不可达——刻意停止而不应用任何内容，而不是直接失败时，就会出现这种情况：没有推送任何内容，但也没有出错，待处理的更改会在实例再次响应后自动重试。将鼠标悬停在徽标上可查看具体原因；该简短标签也是页面状态筛选器所匹配的内容。

成功运行后的首次延迟还会在每个页面顶部触发一个可关闭的警告横幅，与现有的（更严重的）"推送失败"横幅相区分，这样仅仅是在等待某个实例重启的集群就不会显得像出了故障。

## 引导式演示

新安装会通过顶部栏的火箭图标打开一个**入门指引**抽屉。它列出剩余待办事项，逐项自动勾选，并在全部完成后消失——或者在你关闭它时立即消失。

系统不会记录你*看过*什么：每次打开抽屉时，每个条目都会根据当前运行的配置重新计算。通过 API 或 Docker 标签注册一个服务后，下次查看时对应条目已被勾选。反之，删除最后一个服务会让该条目重新出现。

你看到的内容取决于你的角色：

| 角色 | 引导指引提供的内容 |
| --- | --- |
| Admin | 安装、首个服务、HTTPS、首次拦截的请求、MFA，以及可选的 workflow 和 PRO 条目 |
| Writer | 与上相同，但没有仅限 admin 的 PRO 条目 |
| Reader | 提供导览而非任务：dashboard、reports、bans 和 logs 在哪里，以及如何解读它们 |

Reader 首次访问这四个页面时会各获得一条简短提示；点击**知道了**确认即可勾选对应条目。任何指向界面某处的条目还带有**带我去看看**按钮，会在导航中高亮该处。

可选条目——安全 workflow、PRO——从不影响进度计数：Community 版安装无需它们也能达到"全部完成"。

!!! info "不小心关闭了？"
    **个人资料 → 引导式演示 → 重新开始引导** 可以重新打开抽屉。在只读数据库上该按钮被禁用，因为无法保存任何内容。

## 升级后的新变化

升级后，你打开的第一个页面会显示你上次使用的版本与当前运行版本之间的变化摘要。它基于镜像内附带的 `CHANGELOG.md` 生成——不会从互联网获取任何内容，因此隔离网络（air-gapped）安装显示的摘要与联网安装相同。

该摘要按用户和版本区分：关闭它只会将该版本标记为你的账户已读。所有内容始终可在 **/whats-new** 查看，点击侧边栏底部的版本号即可访问——关闭摘要不会丢失任何内容。

有两个行为值得了解：

- **从未看过摘要的账户会被静默标记为已是最新。** 启用此功能不会用完整历史记录"欢迎"已有用户；你将从下一次升级开始看到摘要。
- **降级不显示任何内容。** 运行比记录版本更旧的构建时不显示摘要，而不是宣布当前运行的二进制文件并不包含的发布内容。

在只读数据库上无法保存任何内容，因此摘要会在下次登录时再次出现。

## 升级到 PRO {#upgrade-to-pro}

!!! tip "BunkerWeb PRO 免费试用"
    通过 [BunkerWeb 面板](https://panel.bunkerweb.io/store/bunkerweb-pro?language=chinese&utm_campaign=self&utm_source=doc)开始 BunkerWeb PRO 的 30 天免费试用。

将 PRO 许可证粘贴到 UI 的 **PRO** 页面（或预先设置 `PRO_LICENSE_KEY` 供向导使用）。升级由 scheduler 在后台下载；应用后在 UI 中查看到期时间和服务上限。

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO 许可证信息</figcaption>
</figure>

## 翻译（i18n） {#translations-i18n}

Web 界面支持多种语言，这得益于社区的贡献。翻译内容以按语言划分的 JSON 文件形式存储（例如 `en.json`、`fr.json` 等）。每种语言都会明确标注其来源（人工翻译或由 AI 生成）以及审核状态。

### 可用语言与贡献者

| 语言         | Locale | 创建者                         | 审核者                    |
| ------------ | ------ | ------------------------------ | ------------------------- |
| 阿拉伯语     | `ar`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 孟加拉语     | `bn`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 布列塔尼语   | `br`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 德语         | `de`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 英语         | `en`   | 人工（@TheophileDiot）         | 人工（@TheophileDiot）    |
| 西班牙语     | `es`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 法语         | `fr`   | 人工（@TheophileDiot）         | 人工（@TheophileDiot）    |
| 印地语       | `hi`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 意大利语     | `it`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 韩语         | `ko`   | 人工（@rayshoo）               | 人工（@rayshoo）          |
| 波兰语       | `pl`   | 人工（@tomkolp，经由 Weblate） | 人工（@tomkolp）          |
| 葡萄牙语     | `pt`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 俄语         | `ru`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 土耳其语     | `tr`   | 人工（@wiseweb-works）         | 人工（@wiseweb-works）    |
| 中文（繁体） | `tw`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 乌尔都语     | `ur`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |
| 中文（简体） | `zh`   | AI（Google:Gemini-2.5-pro）    | AI（Google:Gemini-3-pro） |

> 💡 部分翻译可能尚不完整。强烈建议对关键界面元素进行人工校对。

### 如何参与贡献

翻译贡献遵循 BunkerWeb 的标准贡献流程：

1. **创建或更新翻译文件**
   - 复制 `src/ui/app/static/locales/en.json`，并将其重命名为对应的语言代码（例如 `de.json`）。
   - **仅翻译值**，不要修改任何键名。

2. **注册语言**
   - 在 `src/ui/app/lang_config.py` 中添加或更新语言条目（语言代码、显示名称、国旗、英文名称）。
     该文件是支持语言的唯一权威来源。

3. **更新文档与来源说明**
   - `src/ui/app/static/locales/README.md` → 在来源表中添加新语言（创建者 / 审核者）。
   - `README.md` → 更新项目的总体文档，以反映新增的支持语言。
   - `docs/web-ui.md` → 更新 Web 界面文档（本翻译章节）。
   - `docs/*/web-ui.md` → 在对应语言的 Web 界面文档中同步更新相同的翻译章节。

4. **提交 Pull Request**
   - 明确说明翻译是人工完成还是使用了 AI 工具。
   - 对于较大的改动（新增语言或大规模更新），建议先创建一个 issue 进行讨论。

通过参与翻译工作，您将帮助 BunkerWeb 触达更广泛的国际用户群体。
