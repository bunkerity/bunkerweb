# API

## API 角色

BunkerWeb API 是用于管理实例、服务、封禁、插件、任务和自定义配置的控制平面。它运行在 Gunicorn 后的 FastAPI 上，应放在可信的内部网络。交互式文档位于 `/docs`（或 `<API_ROOT_PATH>/docs`），OpenAPI 模型在 `/openapi.json`。

!!! warning "保持私有"
    不要将 API 直接暴露到公网。置于内网，限制来源 IP，并要求认证。

!!! info "快速要点"
    - 健康检查：`GET /ping` 和 `GET /health`
    - 根路径：反向代理挂载子路径时设置 `API_ROOT_PATH`，确保 docs 和 OpenAPI 链接可用
    - 认证必需：Biscuit token、管理员 Basic 或 override Bearer token
    - IP 白名单默认是 RFC1918 范围（`API_WHITELIST_IPS`）；仅在上游已控制访问时禁用
    - 速率限制默认开启；`/auth` 始终有自己的限制

## 安全清单

- 网络：保持内部流量；绑定到回环或内网接口，并用 `API_WHITELIST_IPS` 限制来源 IP（默认启用）。
- 认证到位：设置 `API_USERNAME`/`API_PASSWORD`（管理员），需要时用 `API_ACL_BOOTSTRAP_FILE` 添加更多用户/ACL；仅将 `API_TOKEN` 作为应急备用。
- 隐藏路径：反向代理时选择不易猜到的 `API_ROOT_PATH`，并在代理上同步。
- 速率限制：保持启用，除非其他层有同等限制；`/auth` 始终限速。
- TLS：在代理终止，或设置 `API_SSL_ENABLED=yes` 并提供证书/密钥路径。

## 运行方式

选择适合你环境的方式。

=== "Docker"

    最小化的 Compose 风格，API 在 BunkerWeb 后面。使用前调整版本和密码。

    ```yaml
    x-bw-env: &bw-env
      # 使用锚点避免在多个服务重复相同配置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 设置正确的 IP 范围以便调度器把配置推到实例（内部 BunkerWeb API）
      # 可选：设置 API token 并在两个容器中保持一致（内部 BunkerWeb API）
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 请使用更强的数据库密码

    services:
      bunkerweb:
        # 调度器识别实例的名称
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 支持 QUIC / HTTP3
        environment:
          <<: *bw-env # 复用锚点避免重复
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 确保填写正确的实例名
          SERVER_NAME: "api.example.com"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
          DISABLE_DEFAULT_SERVER: "yes"
          AUTO_LETS_ENCRYPT: "yes"
          api.example.com_USE_TEMPLATE: "api"
          api.example.com_USE_REVERSE_PROXY: "yes"
          api.example.com_REVERSE_PROXY_URL: "/"
          api.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data # 持久化缓存和备份
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.8-rc3
        environment:
          <<: *bw-env
          API_USERNAME: "admin"
          API_PASSWORD: "Str0ng&P@ss!"
          # API_TOKEN: "admin-override-token" # 可选
          FORWARDED_ALLOW_IPS: "*" # 小心使用：仅在 reverse proxy 为唯一入口时开启
          API_ROOT_PATH: "/"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # 提高 max allowed packet 以避免大查询问题
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # 请设置更强的 DB 密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis 用于持久化报告/封禁/统计
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
            - subnet: 10.20.30.0/24 # 设置正确的 IP 范围以便调度器把配置推到实例
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "All-in-One"

    ```bash
    docker run -d \
      --name bunkerweb-aio \
      -e SERVICE_API=yes \
      -e API_WHITELIST_IPS="127.0.0.0/8" \
      -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

=== "Linux"

    DEB/RPM 包含 `bunkerweb-api.service`，通过 `/usr/share/bunkerweb/scripts/bunkerweb-api.sh` 管理。

    - 启用/启动：`sudo systemctl enable --now bunkerweb-api.service`
    - 重载：`sudo systemctl reload bunkerweb-api.service`
    - 日志：journal 加 `/var/log/bunkerweb/api.log`
    - 默认监听：`127.0.0.1:8888`，`API_WHITELIST_IPS=127.0.0.1`
    - 配置文件：`/etc/bunkerweb/api.env`（首次启动生成带注释默认值）和 `/etc/bunkerweb/api.yml`
    - 环境来源：`api.env`、`variables.env`、`/run/secrets/<VAR>`，随后导出到 Gunicorn 进程

    编辑 `/etc/bunkerweb/api.env` 设置 `API_USERNAME`/`API_PASSWORD`、白名单、TLS、速率限制或 `API_ROOT_PATH`，然后 `systemctl reload bunkerweb-api`。

## 认证与授权

- `/auth` 签发 Biscuit token。凭据可来自 Basic auth、表单字段、JSON body，或 Bearer 头等于 `API_TOKEN`（管理员 override）。
- 管理员也可直接用 HTTP Basic 调用受保护路由（无需 Biscuit）。
- Bearer 与 `API_TOKEN` 匹配则拥有完全/管理员访问，否则 Biscuit guard 执行 ACL。
- Biscuit 负载包含用户、时间、客户端 IP、主机、版本、粗粒度 `role("api_user", ["read", "write"])`，以及 `admin(true)` 或精细 `api_perm(resource_type, resource_id|*, permission)`。
- TTL 为 `API_BISCUIT_TTL_SECONDS`（0/off 关闭过期）。密钥存放在 `/var/lib/bunkerweb/.api_biscuit_private_key` 与 `.api_biscuit_public_key`，除非通过 `BISCUIT_PRIVATE_KEY`/`BISCUIT_PUBLIC_KEY` 提供。
- 只有当数据库里至少存在一个 API 用户时，Auth 端点才会暴露。

!!! tip "Auth 快速开始"
    1. 设置 `API_USERNAME` 和 `API_PASSWORD`（如需重新播种则加 `OVERRIDE_API_CREDS=yes`）。
    2. 以 Basic 调用 `POST /auth`；从响应中读取 `.token`。
    3. 后续调用使用 `Authorization: Bearer <token>`。

## 权限与 ACL

- 粗粒度角色：GET/HEAD/OPTIONS 需要 `read`；写操作需要 `write`。
- 当路由声明权限时启用精细 ACL；`admin(true)` 可跳过检查。
- 资源类型：`instances`、`global_settings`、`services`、`configs`、`plugins`、`cache`、`bans`、`jobs`。
- 权限名称：
  - `instances_*`: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
  - `global_settings_*`: `global_settings_read`, `global_settings_update`
  - `services`: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
  - `configs`: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
  - `plugins`: `plugin_read`, `plugin_create`, `plugin_delete`
  - `cache`: `cache_read`, `cache_delete`
  - `bans`: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
  - `jobs`: `job_read`, `job_run`
- `resource_id` 通常是第二个路径段（如 `/services/{id}`）；"*" 表示全局访问。
- 通过 `API_ACL_BOOTSTRAP_FILE` 或挂载的 `/var/lib/bunkerweb/api_acl_bootstrap.json` 启动非管理员用户和权限。密码可为明文或 bcrypt hash。

??? example "最小 ACL 启动"
    ```json
    {
      "users": {
        "ci": {
          "admin": false,
          "password": "Str0ng&P@ss!",
          "permissions": {
            "services": { "*": { "service_read": true } },
            "configs": { "*": { "config_read": true, "config_update": true } }
          }
        }
      }
    }
    ```

## 速率限制

默认启用两个字符串：`API_RATE_LIMIT`（全局，默认 `100r/m`）和 `API_RATE_LIMIT_AUTH`（默认 `10r/m` 或 `off`）。支持 NGINX 风格（`3r/s`、`40r/m`、`200r/h`）或冗长格式（`100/minute`、`200 per 30 minutes`）。通过以下方式配置：

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES`（CSV/JSON/YAML 字符串或文件路径）
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- 存储：内存或 Redis/Valkey（`USE_REDIS=yes` + `REDIS_*`，支持 Sentinel）。

限流策略（`limits` 提供）：

- `fixed-window`（默认）：桶在每个时间窗口边界重置；最省资源，适合粗粒度限制。
- `moving-window`：真实滑动窗口，使用精确时间戳；更平滑但对存储操作更重。
- `sliding-window-counter`：用前一窗口的加权计数平滑；比 moving 轻，比 fixed 更平滑。

更多细节与权衡：<https://limits.readthedocs.io/en/stable/strategies.html>

??? example "内联 CSV"
    ```
    API_RATE_LIMIT_RULES='POST /auth 10r/m, GET /instances* 200r/m, POST|PATCH /services* 40r/m'
    ```

??? example "YAML 文件"
    ```yaml
    API_RATE_LIMIT: 200r/m
    API_RATE_LIMIT_AUTH: 15r/m
    API_RATE_LIMIT_RULES:
      - path: "/auth"
        methods: "POST"
        rate: "10r/m"
      - path: "/instances*"
        methods: "GET|POST"
        rate: "100r/m"
    ```

## 配置来源与优先级

1. 环境变量（包含 Docker/Compose 的 `environment:`）
2. `/run/secrets/<VAR>` 下的 secrets（Docker）
3. `/etc/bunkerweb/api.yml` 的 YAML
4. `/etc/bunkerweb/api.env` 的 env 文件
5. 内置默认值

### 运行时与时区

| Setting | 描述                                                                                      | 接受的值                                       | 默认值                                      |
| ------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------- |
| `TZ`    | API 日志和基于时间的声明（如 Biscuit TTL、日志时间戳）的时区                               | TZ 数据库名称（如 `UTC`、`Europe/Paris`)        | unset（容器默认，通常为 UTC）               |

将 docs 或 schema 的 URL 设为 `off|disabled|none|false|0` 可禁用它们。设置 `API_SSL_ENABLED=yes` 并提供 `API_SSL_CERTFILE`、`API_SSL_KEYFILE` 以在 API 终止 TLS。反向代理时，将 `API_FORWARDED_ALLOW_IPS` 设为代理 IP，使 Gunicorn 信任 `X-Forwarded-*` 头。

### 配置参考（高级）

#### 表面与文档

| Setting                                            | 描述                                                                                       | 接受的值                 | 默认值                              |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------ | ----------------------------------- |
| `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL` | Swagger、ReDoc、OpenAPI 的路径；设为 `off/disabled/none/false/0` 可禁用                     | 路径或 `off`             | `/docs`, `/redoc`, `/openapi.json`  |
| `API_ROOT_PATH`                                    | 反向代理时的挂载前缀                                                                       | 路径（如 `/api`）        | 空                                  |
| `API_FORWARDED_ALLOW_IPS`                          | 可信的代理 IP（用于 `X-Forwarded-*`）                                                       | 逗号分隔 IP/CIDR         | `127.0.0.1`（包默认值）             |

#### Auth、ACL、Biscuit

| Setting                                     | 描述                                       | 接受的值                                                      | 默认值                  |
| ------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------ | ----------------------- |
| `API_USERNAME`, `API_PASSWORD`              | 引导管理员用户                             | 字符串；非调试环境需强密码                                    | unset                   |
| `OVERRIDE_API_CREDS`                        | 启动时重新应用管理员凭据                   | `yes/no/on/off/true/false/0/1`                                | `no`                    |
| `API_TOKEN`                                 | 管理员 override Bearer token               | 不透明字符串                                                  | unset                   |
| `API_ACL_BOOTSTRAP_FILE`                    | 用户/权限的 JSON 路径                      | 文件路径或挂载的 `/var/lib/bunkerweb/api_acl_bootstrap.json`  | unset                   |
| `BISCUIT_PRIVATE_KEY`, `BISCUIT_PUBLIC_KEY` | Biscuit 密钥（hex），若不使用文件          | 十六进制字符串                                                | 自动生成并持久化        |
| `API_BISCUIT_TTL_SECONDS`                   | Token 生命周期；`0/off` 禁用过期           | 整型秒数或 `off/disabled`                                     | `3600`                  |
| `CHECK_PRIVATE_IP`                          | 将 Biscuit 绑定到客户端 IP（私网除外）     | `yes/no/on/off/true/false/0/1`                                | `yes`                   |

#### 白名单

| Setting                 | 描述                             | 接受的值                     | 默认值                |
| ----------------------- | -------------------------------- | --------------------------- | --------------------- |
| `API_WHITELIST_ENABLED` | 切换 IP 白名单中间件             | `yes/no/on/off/true/false/0/1` | `yes`                 |
| `API_WHITELIST_IPS`     | 空格/逗号分隔的 IP/CIDR          | IP/CIDR                     | 代码中的 RFC1918 范围 |

#### 速率限制

| Setting                          | 描述                                       | 接受的值                                               | 默认值        |
| -------------------------------- | ------------------------------------------ | ----------------------------------------------------- | ------------- |
| `API_RATE_LIMIT`                 | 全局限制（NGINX 风格字符串）               | `3r/s`, `100/minute`, `500 per 30 minutes`            | `100r/m`      |
| `API_RATE_LIMIT_AUTH`            | `/auth` 限制（或 `off`）                   | 同上或 `off/disabled/none/false/0`                    | `10r/m`       |
| `API_RATE_LIMIT_ENABLED`         | 启用限流                                   | `yes/no/on/off/true/false/0/1`                        | `yes`         |
| `API_RATE_LIMIT_HEADERS_ENABLED` | 注入限流头部                               | 同上                                                 | `yes`         |
| `API_RATE_LIMIT_RULES`           | 路径规则（CSV/JSON/YAML 或文件路径）       | 字符串或路径                                          | unset         |
| `API_RATE_LIMIT_STRATEGY`        | 算法                                       | `fixed-window`, `moving-window`, `sliding-window-counter` | `fixed-window` |
| `API_RATE_LIMIT_KEY`             | 键选择器                                   | `ip`, `header:<Name>`                                 | `ip`          |
| `API_RATE_LIMIT_EXEMPT_IPS`      | 这些 IP/CIDR 跳过限流                      | 空格/逗号分隔                                         | unset         |
| `API_RATE_LIMIT_STORAGE_OPTIONS` | 合并到存储配置的 JSON                      | JSON 字符串                                           | unset         |

#### Redis/Valkey（用于限流）

| Setting                                              | 描述                 | 接受的值                     | 默认值              |
| ---------------------------------------------------- | -------------------- | --------------------------- | ------------------- |
| `USE_REDIS`                                          | 启用 Redis 后端      | `yes/no/on/off/true/false/0/1` | `no`                |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`         | 连接信息             | 主机，端口，数据库           | unset, `6379`, `0`  |
| `REDIS_USERNAME`, `REDIS_PASSWORD`                   | 认证                 | 字符串                       | unset               |
| `REDIS_SSL`, `REDIS_SSL_VERIFY`                      | TLS 与校验           | `yes/no/on/off/true/false/0/1` | `no`, `yes`         |
| `REDIS_TIMEOUT`                                      | 超时（毫秒）         | 整数                         | `1000`              |
| `REDIS_KEEPALIVE_POOL`                               | 连接池 keepalive     | 整数                         | `10`                |
| `REDIS_SENTINEL_HOSTS`                               | Sentinel 主机        | 空格分隔的 `host:port`       | unset               |
| `REDIS_SENTINEL_MASTER`                              | Sentinel 主节点名称  | 字符串                       | unset               |
| `REDIS_SENTINEL_USERNAME`, `REDIS_SENTINEL_PASSWORD` | Sentinel 认证        | 字符串                       | unset               |

!!! info "DB 提供的 Redis"
    如果 BunkerWeb 数据库配置中存在 Redis/Valkey 设置，即使未在环境中设置 `USE_REDIS`，API 也会自动复用它们用于限流。需要不同后端时可通过环境变量覆盖。

#### Listener 与 TLS

| Setting                               | 描述                         | 接受的值                     | 默认值                              |
| ------------------------------------- | ---------------------------- | --------------------------- | ----------------------------------- |
| `API_LISTEN_ADDR`, `API_LISTEN_PORT`  | Gunicorn 绑定地址/端口       | IP 或主机名，整型           | `127.0.0.1`, `8888`（包脚本）      |
| `API_SSL_ENABLED`                     | 在 API 内启用 TLS            | `yes/no/on/off/true/false/0/1` | `no`                               |
| `API_SSL_CERTFILE`, `API_SSL_KEYFILE` | PEM 证书与密钥路径           | 文件路径                     | unset                               |
| `API_SSL_CA_CERTS`                    | 可选 CA/链                   | 文件路径                     | unset                               |

#### 日志与运行时（包默认）

| Setting                         | 描述                                                                               | 接受的值                                       | 默认值                                                            |
| ------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | 基础日志级别 / 覆盖                                                                 | `debug`, `info`, `warning`, `error`, `critical` | `info`                                                           |
| `LOG_TYPES`                     | 目标                                                                               | 空格分隔的 `stderr`/`file`/`syslog`             | `stderr`                                                         |
| `LOG_FILE_PATH`                 | 日志文件位置（当 `LOG_TYPES` 含 `file` 或 `CAPTURE_OUTPUT=yes` 时使用）             | 文件路径                                        | 当启用 file/capture 时为 `/var/log/bunkerweb/api.log`，否则 unset |
| `LOG_SYSLOG_ADDRESS`            | Syslog 目标（`udp://host:514`、`tcp://host:514`、socket）                          | Host:port、带协议前缀的主机或 socket 路径       | unset                                                            |
| `LOG_SYSLOG_TAG`                | Syslog tag                                                                         | 字符串                                          | `bw-api`                                                         |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn worker/线程                                                               | 整数或 unset 表示自动                          | unset                                                            |
| `CAPTURE_OUTPUT`                | 将 Gunicorn stdout/stderr 汇入配置的处理器                                         | `yes` 或 `no`                                  | `no`                                                             |

## API 面（能力映射）

- **Core**
  - `GET /ping`, `GET /health`: API 自身存活检查。
- **Auth**
  - `POST /auth`: 签发 Biscuit token；接受 Basic、表单、JSON，或当 `API_TOKEN` 匹配时的 Bearer override。
- **Instances**
  - `GET /instances`: 列出实例及创建/最近_seen 元数据。
  - `POST /instances`: 注册实例（hostname/port/server_name/method）。
  - `GET/PATCH/DELETE /instances/{hostname}`: 查看、更新可变字段或删除 API 管理的实例。
  - `DELETE /instances`: 批量删除 API 管理的实例；非 API 条目会被跳过。
  - 健康/操作：`GET /instances/ping`, `GET /instances/{hostname}/ping`, `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`, `POST /instances/stop`, `POST /instances/{hostname}/stop`。
- **Global settings**
  - `GET /global_settings`: 默认只返回非默认值；加 `full=true` 查看全部，加 `methods=true` 包含来源。
  - `PATCH /global_settings`: upsert API 拥有的全局设置；只读键被拒绝。
- **Services**
  - `GET /services`: 列出服务（默认包含草稿）。
  - `GET /services/{service}`: 获取非默认或完整配置（`full=true`）；`methods=true` 包含来源。
  - `POST /services`: 创建服务（draft 或 online），设置变量，并原子更新 `SERVER_NAME` 清单。
  - `PATCH /services/{service}`: 重命名、更新变量、切换 draft。
  - `DELETE /services/{service}`: 删除服务及派生的配置键。
  - `POST /services/{service}/convert?convert_to=online|draft`: 快速切换 draft/online。
- **Custom configs**
  - `GET /configs`: 列出片段（默认服务 `global`）；`with_data=true` 内嵌可打印内容。
  - `POST /configs`, `POST /configs/upload`: 通过 JSON 或文件上传创建片段。
  - `GET /configs/{service}/{type}/{name}`: 获取片段；`with_data=true` 返回内容。
  - `PATCH /configs/{service}/{type}/{name}`, `PATCH .../upload`: 更新或移动 API 管理的片段。
  - `DELETE /configs` 或 `DELETE /configs/{service}/{type}/{name}`: 删除 API 管理的片段；模板管理的会被跳过。
  - 支持类型：`http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`，以及 CRS/插件钩子。
- **Bans**
  - `GET /bans`: 汇总来自各实例的活动封禁。
  - `POST /bans` 或 `/bans/ban`: 应用一个或多个封禁；负载可为对象、数组或字符串化 JSON。
  - `POST /bans/unban` 或 `DELETE /bans`: 全局或按服务解除封禁。
- **Plugins（UI 插件）**
  - `GET /plugins`: 列出插件；`with_data=true` 包含可用的打包字节。
  - `POST /plugins/upload`: 从 `.zip`、`.tar.gz`、`.tar.xz` 安装 UI 插件。
  - `DELETE /plugins/{id}`: 按 ID 删除插件。
- **Cache（任务制品）**
  - `GET /cache`: 按筛选 (`service`, `plugin`, `job_name`) 列出缓存文件；`with_data=true` 内嵌可打印内容。
  - `GET /cache/{service}/{plugin}/{job}/{file}`: 获取/下载特定缓存文件（`download=true`）。
  - `DELETE /cache` 或 `DELETE /cache/{service}/{plugin}/{job}/{file}`: 删除缓存文件并通知调度器。
- **Jobs**
  - `GET /jobs`: 列出作业、计划和缓存摘要。
  - `POST /jobs/run`: 将插件标记为已变更以触发关联作业。

## 运行行为

- 错误响应统一为 `{"status": "error", "message": "..."}`，并使用合适的 HTTP 状态码。
- 写操作持久化到共享数据库；实例通过调度器同步或重载后获取更改。
- `API_ROOT_PATH` 必须与反向代理路径一致，确保 `/docs` 与链接正常。
- 如不存在任何认证路径（无 Biscuit 密钥、无管理员、无 `API_TOKEN`），启动会失败；错误记录到 `/var/tmp/bunkerweb/api.error`。
