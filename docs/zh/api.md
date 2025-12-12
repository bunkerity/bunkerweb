# API

## API 角色

BunkerWeb API 是用于管理实例、服务、封禁、任务、插件和配置的控制平面。它运行在 Gunicorn 后的 FastAPI 上，应该放在可信的内部网络。交互式文档在 `/docs`（或 `<API_ROOT_PATH>/docs`），OpenAPI 在 `/openapi.json`。

!!! warning "保持私有"
    不要把 API 暴露到公网。将其放在内网，限制来源 IP，并要求认证。

## 安全清单

- 网络：内部监听，保持 `API_WHITELIST_IPS` 开启或在上游限制。
- 认证：设置 `API_USERNAME`/`API_PASSWORD`，可选 `API_TOKEN` 作为紧急备用。
- 路径：反向代理时设置并同步 `API_ROOT_PATH`。
- 速率限制：保持开启，`/auth` 有单独的限制。
- TLS：在代理终止，或开启 `API_SSL_ENABLED=yes` 并提供证书。

## 运行方式

- Docker/Compose 或 all-in-one 镜像，细节见英文 `docs/api.md`。
- Linux 包：`bunkerweb-api.service`，日志在 `/var/log/bunkerweb/api.log`。

## 认证与权限

- `/auth` 颁发 Biscuit；支持 Basic、表单、JSON 或 Bearer 等于 `API_TOKEN`。
- 管理员也可直接用 Basic。
- Biscuit 含用户、客户端 IP、角色/ACL、TTL（`API_BISCUIT_TTL_SECONDS`，`0/off` 关闭过期）。

## 速率限制

默认启用两个字符串：`API_RATE_LIMIT`（全局，默认 `100r/m`）和 `API_RATE_LIMIT_AUTH`（默认 `10r/m` 或 `off`）。支持 NGINX 风格（`3r/s`、`40r/m`、`200r/h`）或冗长格式（`100/minute`、`200 per 30 minutes`）。

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES`（内联 CSV/JSON/YAML 或文件路径）
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- 存储：内存或 Redis/Valkey（`USE_REDIS=yes` + `REDIS_*`，支持 Sentinel）

策略（由 `limits` 提供）：

- `fixed-window`（默认）：桶在每个时间窗口边界重置；最轻，适合粗粒度限制。
- `moving-window`：真正的滑动窗口，使用精确时间戳；更平滑但对存储操作要求更高。
- `sliding-window-counter`：使用前一窗口的加权计数进行平滑；比 moving 更轻，比 fixed 更平滑。

更多细节与取舍：<https://limits.readthedocs.io/en/stable/strategies.html>

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

## 配置来源（优先级）

1. 环境变量
2. `/run/secrets/<VAR>` 下的 secrets
3. YAML `/etc/bunkerweb/api.yml`
3. Env 文件 `/etc/bunkerweb/api.env`
4. 代码默认值

## 关键设置（摘录）

- **文档**：`API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`
- **认证**：`API_USERNAME`, `API_PASSWORD`, `API_TOKEN`, `API_ACL_BOOTSTRAP_FILE`
- **Biscuit**：`API_BISCUIT_TTL_SECONDS`, `CHECK_PRIVATE_IP`
- **白名单**：`API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`
- **速率限制**：`API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_HEADERS_ENABLED`, `API_RATE_LIMIT_STORAGE_OPTIONS`
- **Redis/Valkey**：`USE_REDIS`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_SSL`，Sentinel 变量
- **网络/TLS**：`API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`
