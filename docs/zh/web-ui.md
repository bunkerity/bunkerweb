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
    - 依赖：共享 BunkerWeb 数据库并通过 API 进行重载、封禁或查询实例

## 安全清单

- 在内部网络通过 BunkerWeb 暴露 UI；选择难猜的 `REVERSE_PROXY_URL` 并限制来源 IP。
- 设置强 `ADMIN_USERNAME` / `ADMIN_PASSWORD`；仅在需要时开启 `OVERRIDE_ADMIN_CREDS=yes` 来重置。
- 提供 `TOTP_ENCRYPTION_KEYS` 并为管理员启用 TOTP；妥善保存恢复码。
- 使用 TLS（在 BunkerWeb 终止或 `UI_SSL_ENABLED=yes` 并提供证书/密钥路径）；将 `UI_FORWARDED_ALLOW_IPS` 设为可信代理。
- 持久化秘密：挂载 `/var/lib/bunkerweb` 以保留 `FLASK_SECRET`、Biscuit 密钥与 TOTP 数据。
- 保持 `CHECK_PRIVATE_IP=yes`（默认）以绑定会话到客户端 IP；若无长期会话需求，将 `ALWAYS_REMEMBER` 维持为 `no`。
- 确保 `/var/log/bunkerweb` 对 UID/GID 101（或 rootless 映射 UID）可读，便于 UI 读取日志。

## 运行方式

UI 需要可访问的 scheduler /（BunkerWeb）API / redis / 数据库。

=== "快速开始（向导）"

    使用已发布镜像与[快速入门](quickstart-guide.md#__tabbed_1_3)的布局启动栈，然后在浏览器完成向导。

    ```bash
    docker compose -f https://raw.githubusercontent.com/bunkerity/bunkerweb/v1.6.8~rc3-rc1/misc/integrations/docker-compose.yml up -d
    ```

    访问 scheduler 主机名（如 `https://www.example.com/changeme`），运行 `/setup` 向导以配置 UI、scheduler 与实例。

=== "高级（预设环境变量）"

    预置凭据和网络以跳过向导；下面是带 syslog sidecar 的 Compose 示例：

    ```yaml
    x-service-env: &service-env
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"
        environment:
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks: [bw-universe, bw-services]

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb"
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
          ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"
          DISABLE_DEFAULT_SERVER: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme"
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data
        restart: "unless-stopped"
        networks: [bw-universe, bw-db]

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *service-env
          ADMIN_USERNAME: "admin"
          ADMIN_PASSWORD: "Str0ng&P@ss!"
          TOTP_ENCRYPTION_KEYS: "set-me"
          UI_FORWARDED_ALLOW_IPS: "10.20.30.0/24"
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks: [bw-universe, bw-db]

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
        restart: "unless-stopped"
        networks: [bw-db]

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        volumes:
          - bw-logs:/var/log/bunkerweb
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf
        restart: "unless-stopped"
        networks: [bw-universe]

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      bw-lib:

    networks:
      bw-universe:
        ipam:
          config: [{ subnet: 10.20.30.0/24 }]
      bw-services:
      bw-db:
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
- 代理头：`UI_FORWARDED_ALLOW_IPS` 默认 `*`；在 Linux 安装中将其设为反代 IP 以更严格。
- 秘密与状态：`/var/lib/bunkerweb` 保存 `FLASK_SECRET`、Biscuit 密钥和 TOTP 数据。Docker 需挂载；Linux 由包脚本创建管理。
- 日志：`/var/log/bunkerweb` 需对 UID/GID 101（或 rootless 映射 UID）可读。包会创建路径；容器需挂载权限正确的卷。
- 向导行为：Linux easy-install 自动启动 UI 和向导；Docker 需通过反代 URL 访问向导，除非预置环境变量。

## 认证与会话

- 管理员账户：通过向导或 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 创建。密码必须包含大小写字母、数字和特殊字符。`OVERRIDE_ADMIN_CREDS=yes` 会在已有账户时强制重置。
- 角色：`admin`、`writer`、`reader` 会自动创建；账户存储在数据库。
- 秘密：`FLASK_SECRET` 存于 `/var/lib/bunkerweb/.flask_secret`；Biscuit 密钥位于同目录，可用 `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY` 提供。
- 2FA：用 `TOTP_ENCRYPTION_KEYS`（空格分隔或 JSON）开启 TOTP。生成密钥：

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    恢复码在 UI 中仅显示一次；若丢失加密密钥，将清除已存的 TOTP 秘钥。
- 会话：默认 12 小时（`SESSION_LIFETIME_HOURS`）。绑定 IP 与 User-Agent；`CHECK_PRIVATE_IP=no` 仅对私网放宽 IP 检查。`ALWAYS_REMEMBER=yes` 始终启用持久 Cookie。
- 若多级代理附加 `X-Forwarded-*`，请设置 `PROXY_NUMBERS`。

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

| 设置                                | 描述                       | 可接受值              | 默认值                                  |
| ----------------------------------- | -------------------------- | --------------------- | --------------------------------------- |
| `UI_LISTEN_ADDR`                    | UI 监听地址                | IP 或主机名           | `0.0.0.0`（Docker） / `127.0.0.1`（包） |
| `UI_LISTEN_PORT`                    | UI 监听端口                | 整数                  | `7000`                                  |
| `LISTEN_ADDR`, `LISTEN_PORT`        | UI 变量缺失时的备用        | IP/主机名，整数       | `0.0.0.0`, `7000`                       |
| `UI_SSL_ENABLED`                    | 在 UI 容器中启用 TLS       | `yes` 或 `no`         | `no`                                    |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | 启用 TLS 时的证书/密钥路径 | 文件路径              | 未设                                    |
| `UI_SSL_CA_CERTS`                   | 可选 CA/链                 | 文件路径              | 未设                                    |
| `UI_FORWARDED_ALLOW_IPS`            | 信任的代理 IP/CIDR         | 空格/逗号分隔 IP/CIDR | `*`                                     |

### 认证、会话与 Cookie

| 设置                                        | 描述                                                    | 可接受值                     | 默认值         |
| ------------------------------------------- | ------------------------------------------------------- | ---------------------------- | -------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | 初始化管理员账户（执行密码策略）                        | 字符串                       | 未设           |
| `OVERRIDE_ADMIN_CREDS`                      | 强制用环境变量更新管理员凭据                            | `yes` 或 `no`                | `no`           |
| `FLASK_SECRET`                              | 会话签名密钥（存于 `/var/lib/bunkerweb/.flask_secret`） | 十六进制/Base64/不透明字符串 | 自动生成       |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | TOTP 秘钥加密键（空格或 JSON）                          | 字符串 / JSON                | 缺失时自动生成 |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Biscuit 密钥（hex），用于 UI token                      | Hex 字符串                   | 自动生成并存储 |
| `SESSION_LIFETIME_HOURS`                    | 会话时长                                                | 数值（小时）                 | `12`           |
| `ALWAYS_REMEMBER`                           | 总是启用 “remember me”                                  | `yes` 或 `no`                | `no`           |
| `CHECK_PRIVATE_IP`                          | 绑定会话到 IP（`no` 时放宽私网变更）                    | `yes` 或 `no`                | `yes`          |
| `PROXY_NUMBERS`                             | 信任的 `X-Forwarded-*` 代理层数                         | 整数                         | `1`            |

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

| 设置                            | 描述                      | 可接受值      | 默认值                                 |
| ------------------------------- | ------------------------- | ------------- | -------------------------------------- |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn worker/线程数    | 整数          | `cpu_count()-1`（至少 1），`workers*2` |
| `ENABLE_HEALTHCHECK`            | 暴露 `GET /healthcheck`   | `yes` 或 `no` | `no`                                   |
| `FORWARDED_ALLOW_IPS`           | 代理允许列表的弃用别名    | IP/CIDR       | `*`                                    |
| `DISABLE_CONFIGURATION_TESTING` | 应用配置时跳过测试 reload | `yes` 或 `no` | `no`                                   |
| `IGNORE_REGEX_CHECK`            | 跳过设置的正则校验        | `yes` 或 `no` | `no`                                   |

## 日志访问

UI 从 `/var/log/bunkerweb` 读取 NGINX/服务日志。通过 syslog 守护或卷填充该目录：

- 容器 UID/GID 为 101。宿主上设置权限：`chown root:101 bw-logs && chmod 770 bw-logs`（rootless 需调整）。
- 使用 `ACCESS_LOG` / `ERROR_LOG` 将 BunkerWeb 访问/错误日志发送到 syslog sidecar；组件日志用 `LOG_TYPES=syslog`。

写入按程序分文件的 `syslog-ng.conf` 示例：

```conf
@version: 4.10
source s_net { udp(ip("0.0.0.0")); };
template t_imp { template("$MSG\n"); template_escape(no); };
destination d_dyna_file {
  file("/var/log/bunkerweb/${PROGRAM}.log"
       template(t_imp) owner("101") group("101")
       dir_owner("root") dir_group("101")
       perm(0440) dir_perm(0770) create_dirs(yes));
};
log { source(s_net); destination(d_dyna_file); };
```

## 功能

- 请求、封禁、缓存和任务的仪表板；重启/重载实例。
- 创建/更新/删除服务和全局设置，并按插件模式校验。
- 上传和管理自定义配置（NGINX/ModSecurity）与插件（外部或 PRO）。
- 查看日志、搜索报表、检查缓存制品。
- 管理 UI 用户、角色、会话及 TOTP（含恢复码）。
- 升级到 BunkerWeb PRO 并在专页查看许可证状态。

## 升级到 PRO {#upgrade-to-pro}

!!! tip "BunkerWeb PRO 免费试用"
    在 [BunkerWeb 面板](https://panel.bunkerweb.io/store/bunkerweb-pro?language=chinese&utm_campaign=self&utm_source=doc) 使用代码 `freetrial` 可试用一个月。

将 PRO 许可证粘贴到 UI 的 **PRO** 页面（或预先设置 `PRO_LICENSE_KEY` 供向导使用）。升级由 scheduler 在后台下载；应用后在 UI 中查看到期时间和服务上限。

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO 许可证信息</figcaption>
</figure>

## 翻译（i18n）

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
