# API

## 概述

BunkerWeb API 是用于以编程方式管理 BunkerWeb 实例的控制平面：列出和管理实例、重新加载/停止、处理封禁、插件、作业、配置等。它公开了一个有文档记录的 FastAPI 应用程序，具有强大的身份验证、授权和速率限制功能。

在 `/docs`（如果设置了 `API_ROOT_PATH`，则为 `<root_path>/docs`）打开交互式文档。OpenAPI 模式可在 `/openapi.json` 获取。

!!! warning "安全"
    API 是一个特权控制平面。不要在没有额外保护的情况下将其暴露在公共互联网上。

    至少，限制源 IP (`API_WHITELIST_IPS`)，启用身份验证（`API_TOKEN` 或 API 用户 + Biscuit），并考虑将其置于 BunkerWeb 之后，使用一个难以猜测的路径和额外的访问控制。

## 先决条件

API 服务需要访问 BunkerWeb 数据库 (`DATABASE_URI`)。它通常与调度器和可选的 Web UI 一起部署。推荐的设置是在前端运行 BunkerWeb 作为反向代理，并将 API 隔离在内部网络上。

请参阅[快速入门指南](quickstart-guide.md)中的快速入门向导和架构指导。

## 推荐部署（独立容器）

在生产环境中，将 API 作为独立容器部署在 BunkerWeb 数据平面和调度器旁边。让 API 仅绑定在内部控制平面网络上，并只通过 BunkerWeb 作为反向代理对外发布。该布局与 [Docker 集成参考](integrations.md#networks) 保持一致，并确保调度器、BunkerWeb 和 API 使用相同的设置。

```yaml
x-bw-env: &bw-env
  # 使用锚点避免在两个服务上重复相同的配置
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 请设置正确的 IP 段，确保调度器可以将配置发送到实例
  DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 请为数据库设置更强的密码

services:
  bunkerweb:
    # 这是调度器用来识别实例的名称
    image: bunkerity/bunkerweb:1.6.6-rc1
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # 用于支持 QUIC / HTTP3
    environment:
      <<: *bw-env # 使用锚点避免在所有服务中重复相同的配置
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "bunkerweb" # 请确保实例名称正确
      SERVER_NAME: "api.example.com" # 可按需修改
      MULTISITE: "yes"
      USE_REDIS: "yes"
      REDIS_HOST: "redis"
      api.example.com_USE_TEMPLATE: "bw-api"
      api.example.com_GENERATE_SELF_SIGNED_SSL: "yes"
      api.example.com_USE_REVERSE_PROXY: "yes"
      api.example.com_REVERSE_PROXY_URL: "/"
      api.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
    volumes:
      - bw-storage:/data # 用于持久化缓存和备份等数据
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-api:
    image: bunkerity/bunkerweb-api:1.6.6-rc1
    environment:
      <<: *bw-env
      API_USERNAME: "admin"
      API_PASSWORD: "Str0ng&P@ss!" # 请为管理员用户设置更强的密码
      DEBUG: "1"
    restart: "unless-stopped"
    networks:
      bw-universe:
        aliases:
          - bw-api
      bw-db:
        aliases:
          - bw-api

  bw-db:
    image: mariadb:11
    # 设置最大允许的数据包大小以避免大查询导致的问题
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # 请为数据库设置更强的密码
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db

  redis: # Redis 服务，用于持久化报表/封禁/统计数据
    image: redis:7-alpine
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
        - subnet: 10.20.30.0/24 # 请设置正确的 IP 段，确保调度器可以将配置发送到实例
  bw-services:
    name: bw-services
  bw-db:
    name: bw-db
```

这样可以将 API 隔离在 BunkerWeb 后面，使流量保持在受信任的网络中，并让你能够在控制平面和暴露的主机名两侧同时实施身份验证、允许列表和速率限制。

## 亮点

- 实例感知：将操作性动作广播到已发现的实例。
- 强身份验证：管理员的基本认证、Bearer 管理员覆盖或用于细粒度权限的 Biscuit ACL。
- IP 允许列表和灵活的按路由速率限制。
- 标准的健康/就绪信号和启动安全检查。

## Compose 样板文件

=== "Docker"

    使用 BunkerWeb 将 API 反向代理到 `/api` 下。

    ```yaml
    x-bw-env: &bw-env
      # BunkerWeb/Scheduler 的共享实例控制平面允许列表
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          <<: *bw-env
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb"  # 匹配实例服务名称
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
          DISABLE_DEFAULT_SERVER: "yes"
          # 在 /api 上反向代理 API
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/api"
          www.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.6-rc1
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # 使用强密码
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"                      # API 允许列表
          API_TOKEN: "secret"                                                 # 可选的管理员覆盖令牌
          API_ROOT_PATH: "/api"                                               # 匹配反向代理路径
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # 避免大查询出现问题
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"  # 使用强密码
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
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
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"

    与上面相同，但利用 Autoconf 服务自动发现和配置服务。API 通过在 API 容器上使用标签暴露在 `/api` 下。

    ```yaml
    x-api-env: &api-env
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # 使用强密码

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc1
        environment:
          <<: *api-env
          BUNKERWEB_INSTANCES: ""    # 由 Autoconf 发现
          SERVER_NAME: ""            # 通过标签填充
          MULTISITE: "yes"           # Autoconf 必需
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc1
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *api-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.6-rc1
        environment:
          <<: *api-env
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"
          API_TOKEN: "secret"
          API_ROOT_PATH: "/api"
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/api"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-api:8888"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
        networks:
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
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
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

!!! warning "反向代理路径"
    保持 API 路径难以猜测，并与 API 允许列表和身份验证结合使用。

    如果您已经在同一服务器名称上使用模板（例如 `USE_TEMPLATE`）公开了另一个应用程序，请为 API 使用一个独立的主机名以避免冲突。

### 一体化 (All-In-One)

如果您使用一体化镜像，可以通过设置 `SERVICE_API=yes` 来启用 API：

```bash
docker run -d \
  --name bunkerweb-aio \
  -e SERVICE_API=yes \
  -e API_WHITELIST_IPS="127.0.0.0/8" \
  -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc1
```

## 身份验证

支持的请求身份验证方式：

- 基本管理员认证：当凭据属于管理员 API 用户时，受保护的端点接受 `Authorization: Basic <base64(username:password)>`。
- 管理员 Bearer 覆盖：如果配置了 `API_TOKEN`，`Authorization: Bearer <API_TOKEN>` 将授予完全访问权限。
- Biscuit 令牌（推荐）：使用基本凭据或包含 `username` 和 `password` 的 JSON/表单体从 `POST /auth` 获取令牌。在后续调用中将返回的令牌用作 `Authorization: Bearer <token>`。

示例：获取一个 Biscuit，列出实例，然后重新加载所有实例。

```bash
# 1) 使用管理员凭据获取一个 Biscuit 令牌
TOKEN=$(curl -s -X POST -u admin:changeme http://api.example.com/auth | jq -r .token)

# 2) 列出实例
curl -H "Authorization: Bearer $TOKEN" http://api.example.com/instances

# 3) 重新加载所有实例的配置（无测试）
curl -X POST -H "Authorization: Bearer $TOKEN" \
     "http://api.example.com/instances/reload?test=no"
```

### Biscuit 事实和检查

令牌嵌入了诸如 `user(<username>)`、`client_ip(<ip>)`、`domain(<host>)` 等事实，以及从数据库权限派生的粗粒度角色 `role("api_user", ["read", "write"])`。管理员包含 `admin(true)`，而非管理员则携带细粒度的事实，如 `api_perm(<resource_type>, <resource_id|*>, <permission>)`。

授权将路由/方法映射到所需的权限；`admin(true)` 总是通过。当缺少细粒度事实时，守卫会回退到粗粒度角色：GET/HEAD/OPTIONS 需要 `read`；写入动词需要 `write`。

密钥存储在 `/var/lib/bunkerweb/.api_biscuit_private_key` 和 `/var/lib/bunkerweb/.api_biscuit_public_key`。您还可以通过环境变量提供 `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY`；如果文件和环境变量都未设置，API 会在启动时生成一个密钥对并安全地持久化它。

## 权限 (ACL)

此 API 支持两个授权层：

- 粗粒度角色：令牌携带 `role("api_user", ["read"[, "write"]])` 用于没有细粒度映射的端点。Read 映射到 GET/HEAD/OPTIONS；write 映射到 POST/PUT/PATCH/DELETE。
- 细粒度 ACL：令牌嵌入 `api_perm(<resource_type>, <resource_id|*>, <permission>)`，并且路由声明它们需要什么。`admin(true)` 绕过所有检查。

支持的资源类型：`instances`、`global_config`、`services`、`configs`、`plugins`、`cache`、`bans`、`jobs`。

按资源类型划分的权限名称：

- instances: `instances_read`、`instances_update`、`instances_delete`、`instances_create`、`instances_execute`
- global_config: `global_config_read`、`global_config_update`
- services: `service_read`、`service_create`、`service_update`、`service_delete`、`service_convert`、`service_export`
- configs: `configs_read`、`config_read`、`config_create`、`config_update`、`config_delete`
- plugins: `plugin_read`、`plugin_create`、`plugin_delete`
- cache: `cache_read`、`cache_delete`
- bans: `ban_read`、`ban_update`、`ban_delete`、`ban_created`
- jobs: `job_read`、`job_run`

资源 ID：对于细粒度检查，当有意义时，第二个路径段被视为 `resource_id`。示例：`/services/{service}` -> `{service}`；`/configs/{service}/...` -> `{service}`。使用 `"*"`（或省略）为资源类型全局授予权限。

用户和 ACL 配置：

- 管理员用户：设置 `API_USERNAME` 和 `API_PASSWORD` 以在启动时创建第一个管理员。要稍后轮换凭据，请设置 `OVERRIDE_API_CREDS=yes`（或确保管理员是使用 `manual` 方法创建的）。只存在一个管理员；额外的尝试会回退到非管理员创建。
- 非管理员用户和授权：提供指向 JSON 文件的 `API_ACL_BOOTSTRAP_FILE`，或挂载 `/var/lib/bunkerweb/api_acl_bootstrap.json`。API 在启动时读取它以创建/更新用户和权限。
- ACL 缓存文件：一个只读的摘要在启动时写入 `/var/lib/bunkerweb/api_acl.json` 以供内省；授权评估嵌入在 Biscuit 令牌中的数据库支持的授权。

引导 JSON 示例（两种形式都支持）：

```json
{
  "users": {
    "ci": {
      "admin": false,
      "password": "Str0ng&P@ss!",
      "permissions": {
        "services": {
          "*": { "service_read": true },
          "app-frontend": { "service_update": true, "service_delete": false }
        },
        "configs": {
          "app-frontend": { "config_read": true, "config_update": true }
        }
      }
    },
    "ops": {
      "admin": false,
      "password_hash": "$2b$13$...bcrypt-hash...",
      "permissions": {
        "instances": { "*": { "instances_execute": true } },
        "jobs": { "*": { "job_run": true } }
      }
    }
  }
}
```

或列表形式：

```json
{
  "users": [
    {
      "username": "ci",
      "password": "Str0ng&P@ss!",
      "permissions": [
        { "resource_type": "services", "resource_id": "*", "permission": "service_read" },
        { "resource_type": "services", "resource_id": "app-frontend", "permission": "service_update" }
      ]
    }
  ]
}
```

注意：

- 密码可以是明文（`password`）或 bcrypt（`password_hash` / `password_bcrypt`）。在非调试版本中，弱明文密码会被拒绝；如果缺少，会生成一个随机密码并记录警告。
- `resource_id: "*"`（或 null/空）在该资源类型上全局授予权限。
- 现有用户可以通过引导更新密码并应用额外的授权。

## 功能参考

API 按资源聚焦的路由器组织。使用以下部分作为功能地图；`/docs` 处的交互式模式详细记录了请求/响应模型。

### 核心和身份验证

- `GET /ping`、`GET /health`：API 服务本身的轻量级存活探针。
- `POST /auth`：用基本凭据（或管理员覆盖令牌）交换 Biscuit。接受 JSON、表单或 `Authorization` 标头。管理员如果需要，也可以直接在受保护的路由上继续使用 HTTP 基本认证。

### 实例控制平面

- `GET /instances`：列出注册的实例，包括创建/最后一次看到的时间戳、注册方法和元数据。
- `POST /instances`：注册一个新的 API 管理的实例（主机名、可选端口、服务器名称、友好名称、方法）。
- `GET /instances/{hostname}` / `PATCH /instances/{hostname}` / `DELETE /instances/{hostname}`：检查、更新可变字段或删除 API 管理的实例。
- `DELETE /instances`：批量删除；跳过非 API 实例并在 `skipped` 中报告它们。
- `GET /instances/ping` 和 `GET /instances/{hostname}/ping`：对所有或单个实例进行健康检查。
- `POST /instances/reload?test=yes|no`、`POST /instances/{hostname}/reload`：触发配置重新加载（测试模式执行空跑验证）。
- `POST /instances/stop`、`POST /instances/{hostname}/stop`：向实例中继停止命令。

### 全局配置

- `GET /global_config`：获取非默认设置（使用 `full=true` 获取完整配置，`methods=true` 包含来源信息）。
- `PATCH /global_config`：更新或插入 API 拥有的（`method="api"`）全局设置；验证错误会指出未知或只读的键。

### 服务生命周期

- `GET /services`：枚举服务及其元数据，包括草稿状态和时间戳。
- `GET /services/{service}`：检索服务的非默认覆盖层（`full=false`）或完整配置快照（`full=true`）。
- `POST /services`：创建服务，可选择作为草稿，并设定带前缀的变量（`{service}_{KEY}`）。原子地更新 `SERVER_NAME` 名册。
- `PATCH /services/{service}`：重命名服务、切换草稿标志并更新带前缀的变量。为安全起见，忽略对 `variables` 内 `SERVER_NAME` 的直接编辑。
- `DELETE /services/{service}`：删除一个服务及其派生的配置键。
- `POST /services/{service}/convert?convert_to=online|draft`：快速切换草稿/在线状态，而不更改其他变量。

### 自定义配置片段

- `GET /configs`：列出服务的自定义配置片段（HTTP/服务器/流/ModSecurity/CRS 挂钩）（默认为 `service=global`）。`with_data=true` 在可打印时嵌入 UTF-8 内容。
- `POST /configs` 和 `POST /configs/upload`：从 JSON 负载或上传的文件创建新片段。接受的类型包括 `http`、`server_http`、`default_server_http`、`modsec`、`modsec_crs`、`stream`、`server_stream` 和 CRS 插件挂钩。名称必须匹配 `^[\w_-]{1,255}$`。
- `GET /configs/{service}/{type}/{name}`：检索带有可选内容的片段（`with_data=true`）。
- `PATCH /configs/{service}/{type}/{name}` 和 `PATCH .../upload`：更新或移动 API 管理的片段；模板或文件管理的条目保持只读。
- `DELETE /configs` 和 `DELETE /configs/{service}/{type}/{name}`：修剪 API 管理的片段，同时保留模板管理的片段，并为被忽略的条目返回一个 `skipped` 列表。

### 封禁编排

- `GET /bans`：聚合所有实例报告的活动封禁。
- `POST /bans` 或 `POST /bans/ban`：应用一个或多个封禁。负载可以是 JSON 对象、数组或字符串化的 JSON。`service` 是可选的；省略时封禁是全局的。
- `POST /bans/unban` 或 `DELETE /bans`：使用同样灵活的负载全局或按服务删除封禁。

### 插件管理

- `GET /plugins?type=all|external|ui|pro`：列出带有元数据的插件；`with_data=true` 在可用时包含打包的字节。
- `POST /plugins/upload`：从 `.zip`、`.tar.gz` 或 `.tar.xz` 存档安装 UI 插件。存档可以捆绑多个插件，只要每个插件都包含一个 `plugin.json`。
- `DELETE /plugins/{id}`：按 ID (`^[\w.-]{4,64}$`) 删除 UI 插件。

### 作业缓存和执行

- `GET /cache`：列出由调度器作业产生的缓存工件，按服务、插件 ID 或作业名称过滤。`with_data=true` 包含可打印的文件内容。
- `GET /cache/{service}/{plugin}/{job}/{file}`：获取特定的缓存文件（`download=true` 以附件形式流式传输）。
- `DELETE /cache` 或 `DELETE /cache/{service}/{plugin}/{job}/{file}`：删除缓存文件并通知调度器受影响的插件。
- `GET /jobs`：检查已知的作业、它们的调度元数据和缓存摘要。
- `POST /jobs/run`：通过将关联的插件标记为已更改来请求作业执行。

### 操作说明

- 写入端点持久化到共享数据库；实例通过调度器同步或在 `/instances/reload` 后获取更改。
- 错误被规范化为 `{ "status": "error", "message": "..." }`，并带有适当的 HTTP 状态码（422 验证，404 未找到，403 ACL，5xx 上游故障）。

## 速率限制

客户端的速率限制由 SlowAPI 处理。通过环境变量或 `/etc/bunkerweb/api.yml` 启用/禁用它并调整限制。

- `API_RATE_LIMIT_ENABLED` (默认: `yes`)
- 默认限制: `API_RATE_LIMIT_TIMES` 每 `API_RATE_LIMIT_SECONDS` (例如 `100` 每 `60`)
- `API_RATE_LIMIT_RULES`: 内联 JSON/CSV，或指向包含按路由规则的 YAML/JSON 文件的路径
- 存储后端: 内存或当 `USE_REDIS=yes` 且提供了 `REDIS_*` 变量时使用 Redis/Valkey (支持 Sentinel)
- 标头: `API_RATE_LIMIT_HEADERS_ENABLED` (默认: `yes`)

示例 YAML (挂载在 `/etc/bunkerweb/api.yml`):

```yaml
API_RATE_LIMIT_ENABLED: yes
API_RATE_LIMIT_DEFAULTS: ["200/minute"]
API_RATE_LIMIT_RULES:
  - path: "/auth"
    methods: "POST"
    times: 10
    seconds: 60
  - path: "/instances*"
    methods: "GET|POST"
    times: 100
    seconds: 60```

## 配置

您可以通过环境变量、Docker secrets 以及可选的 `/etc/bunkerweb/api.yml` 或 `/etc/bunkerweb/api.env` 文件来配置 API。关键设置：

- 文档和模式: `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`。
- 认证基础: `API_TOKEN` (管理员覆盖 Bearer), `API_USERNAME`/`API_PASSWORD` (创建/更新管理员), `OVERRIDE_API_CREDS`。
- ACL 和用户: `API_ACL_BOOTSTRAP_FILE` (JSON 路径)。
- Biscuit 策略: `API_BISCUIT_TTL_SECONDS` (0/关闭禁用 TTL), `CHECK_PRIVATE_IP` (将令牌绑定到客户端 IP，除非是私有 IP)。
- IP 允许列表: `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`。
- 速率限制 (核心): `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_TIMES`, `API_RATE_LIMIT_SECONDS`, `API_RATE_LIMIT_HEADERS_ENABLED`。
- 速率限制 (高级): `API_RATE_LIMIT_AUTH_TIMES`, `API_RATE_LIMIT_AUTH_SECONDS`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_DEFAULTS`, `API_RATE_LIMIT_APPLICATION_LIMITS`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_STORAGE_OPTIONS`。
- 速率限制存储: 内存或当 `USE_REDIS=yes` 且设置了 Redis 相关变量时使用 Redis/Valkey，如 `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DATABASE`, `REDIS_SSL` 或 Sentinel 变量。请参阅 `docs/features.md` 中的 Redis 设置表。
- 网络/TLS: `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`。

### 配置加载方式

优先级从高到低：

- 环境变量 (例如容器 `environment:` 或导出的 shell 变量)
- `/run/secrets` 下的 Secrets 文件 (Docker/K8s secrets; 文件名匹配变量名)
- `/etc/bunkerweb/api.yml` 处的 YAML 文件
- `/etc/bunkerweb/api.env` 处的 Env 文件 (key=value 行)
- 内置默认值

注意：

- YAML 支持使用 `<file:relative/path>` 内联 secret 文件；路径相对于 `/run/secrets` 解析。
- 将文档 URL 设置为 `off`/`disabled`/`none` 以禁用端点 (例如 `API_DOCS_URL=off`)。
- 如果 `API_SSL_ENABLED=yes`，您还必须设置 `API_SSL_CERTFILE` 和 `API_SSL_KEYFILE`。
- 如果启用了 Redis (`USE_REDIS=yes`)，请提供 Redis 详细信息；请参阅 `docs/features.md` 中的 Redis 部分。

### 身份验证和用户

- 管理员引导：设置 `API_USERNAME` 和 `API_PASSWORD` 以创建第一个管理员。要稍后重新应用，请设置 `OVERRIDE_API_CREDS=yes`。
- 非管理员和权限：提供 `API_ACL_BOOTSTRAP_FILE` 并指定一个 JSON 路径（或挂载到 `/var/lib/bunkerweb/api_acl_bootstrap.json`）。该文件可以列出用户和细粒度的授权。
- Biscuit 密钥：可以设置 `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY`，或在 `/var/lib/bunkerweb/.api_biscuit_public_key` 和 `/var/lib/bunkerweb/.api_biscuit_private_key` 处挂载文件。如果均未提供，API 将在启动时生成并持久化一个密钥对。

### TLS 和网络

- 绑定地址/端口：`API_LISTEN_ADDR` (默认 `0.0.0.0`)，`API_LISTEN_PORT` (默认 `8888`)。
- 反向代理：将 `API_FORWARDED_ALLOW_IPS` 设置为代理 IP，以便 Gunicorn 信任 `X-Forwarded-*` 标头。
- API 中的 TLS 终止：`API_SSL_ENABLED=yes` 加上 `API_SSL_CERTFILE` 和 `API_SSL_KEYFILE`；可选的 `API_SSL_CA_CERTS`。

### 速率限制快速配方

- 全局禁用：`API_RATE_LIMIT_ENABLED=no`
- 设置一个简单的全局限制：`API_RATE_LIMIT_TIMES=100`，`API_RATE_LIMIT_SECONDS=60`
- 按路由规则：将 `API_RATE_LIMIT_RULES` 设置为 JSON/YAML 文件路径或在 `/etc/bunkerweb/api.yml` 中内联 YAML。

!!! warning "启动安全"
    如果未配置身份验证路径（没有 Biscuit 密钥，没有管理员用户，也没有 `API_TOKEN`），API 将退出。请确保在启动前至少设置一种方法。

启动安全：如果没有任何身份验证路径可用（没有 Biscuit 密钥、没有管理员 API 用户、也没有 `API_TOKEN`），API 将退出。确保至少配置了一种。

!!! info "根路径和代理"
    如果您将 API 部署在 BunkerWeb 后面的子路径上，请将 `API_ROOT_PATH` 设置为该路径，以便 `/docs` 和相对路由在代理时能正常工作。

## 操作

- 健康状况：当服务正常时，`GET /health` 返回 `{"status":"ok"}`。
- Linux 服务：打包了一个名为 `bunkerweb-api.service` 的 `systemd` 单元。通过 `/etc/bunkerweb/api.env` 进行自定义，并使用 `systemctl` 进行管理。
- 启动安全：当没有可用的身份验证路径时（没有 Biscuit 密钥、没有管理员用户、没有 `API_TOKEN`），API 会快速失败。错误会写入 `/var/tmp/bunkerweb/api.error`。
