# 集成

## BunkerWeb 云

<figure markdown>
  ![概述](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb 云</figcaption>
</figure>

BunkerWeb Cloud 将是开始使用 BunkerWeb 的最简单方式。它为您提供一个完全托管的 BunkerWeb 服务，无需任何麻烦。可以把它想象成一个 BunkerWeb 即服务！

试试我们的 [BunkerWeb Cloud 服务](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc)，您将获得：

- 一个完全托管在我们云端的 BunkerWeb 实例
- 所有 BunkerWeb 功能，包括 PRO 功能
- 一个带有仪表板和警报的监控平台
- 协助您进行配置的技术支持

如果您对 BunkerWeb Cloud 服务感兴趣，请随时[联系我们](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc)，以便我们讨论您的需求。

## 一体化 (AIO) 镜像 {#all-in-one-aio-image}

<figure markdown>
  ![AIO 架构图占位符](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>BunkerWeb 一体化架构 (AIO)</figcaption>
</figure>

### 部署 {#deployment}

要部署一体化容器，您只需运行以下命令：

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

默认情况下，容器暴露：

- 8080/tcp 用于 HTTP
- 8443/tcp 用于 HTTPS
- 8443/udp 用于 QUIC
- 7000/tcp 用于在没有 BunkerWeb 前置的情况下的 Web UI 访问（不建议在生产环境中使用）
- 当 `SERVICE_API=yes` 时，8888/tcp 用于 API（内部使用；建议通过 BunkerWeb 作为反向代理暴露，而不是直接发布）

需要一个命名卷（或绑定挂载）来持久化容器内 `/data` 目录下的 SQLite 数据库、缓存和备份：

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.6-rc3
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "使用本地文件夹存储持久化数据"
    一体化容器以内置的 **非特权用户（UID 101、GID 101）** 运行各项服务。这能够提升安全性：即便组件被攻破，也无法在宿主机上获得 root 权限（UID/GID 0）。

    如果挂载了一个**本地文件夹**，请确保目录权限允许该非特权用户写入：

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    如果目录已存在，可以执行：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    在使用 [Docker 无根模式](https://docs.docker.com/engine/security/rootless) 或 [Podman](https://podman.io/) 时，容器内的 UID/GID 会被重新映射。请先检查自己的 `subuid` 与 `subgid` 范围：

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    例如，如果起始值是 **100000**，对应的映射 UID/GID 将是 **100100**（100000 + 100）：

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    或者，如果目录已存在：

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

一体化镜像内置了几个服务，可以通过环境变量来控制：

- `SERVICE_UI=yes` (默认) - 启用 Web UI 服务
- `SERVICE_SCHEDULER=yes` (默认) - 启用调度器服务
- `SERVICE_API=no` (默认) - 启用 API 服务 (FastAPI 控制平面)
- `AUTOCONF_MODE=no` (默认) - 启用自动配置服务
- `USE_REDIS=yes` (默认) - 启用内置的 [Redis](#redis-integration) 实例
- `USE_CROWDSEC=no` (默认) - [CrowdSec](#crowdsec-integration) 集成默认禁用
- `HIDE_SERVICE_LOGS=`（可选）- 以逗号分隔的服务列表，用于在容器日志中静音这些服务。支持的值：`api`、`autoconf`、`bunkerweb`、`crowdsec`、`redis`、`scheduler`、`ui`、`nginx.access`、`nginx.error`、`modsec`。日志仍会写入 `/var/log/bunkerweb/<service>.log`。

### API 集成

一体化镜像内嵌了 BunkerWeb API。它默认是禁用的，可以通过设置 `SERVICE_API=yes` 来启用。

!!! warning "安全"
    API 是一个特权控制平面。不要直接将其暴露在互联网上。请将其保留在内部网络上，使用 `API_WHITELIST_IPS` 限制源 IP，要求身份验证（`API_TOKEN` 或 API 用户 + Biscuit），并最好通过 BunkerWeb 作为反向代理在一个难以猜测的路径上访问它。

快速启用（独立）— 发布 API 端口；仅用于测试：

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e SERVICE_API=yes \
  -e API_WHITELIST_IPS="127.0.0.0/8" \
  -e API_USERNAME=changeme \
  -e API_PASSWORD=StrongP@ssw0rd \
  -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
  -p 8888:8888/tcp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

推荐（在 BunkerWeb 之后）— 不要发布 `8888`；而是反向代理它：

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.6-rc3
    container_name: bunkerweb-aio
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp"
    environment:
      SERVER_NAME: "api.example.com"
      MULTISITE: "yes"
      DISABLE_DEFAULT_SERVER: "yes"
      api.example.com_USE_TEMPLATE: "bw-api"
      api.example.com_USE_REVERSE_PROXY: "yes"
      api.example.com_REVERSE_PROXY_URL: "/api-<unguessable>"
      api.example.com_REVERSE_PROXY_HOST: "http://127.0.0.1:8888" # 内部 API 端点

      # API 设置
      SERVICE_API: "yes"
      # 设置强壮的凭据并且只允许可信的 IP/网络（详见下文）
      API_USERNAME: "changeme"
      API_PASSWORD: "StrongP@ssw0rd"
      API_ROOT_PATH: "/api-<unguessable>" # 需与 REVERSE_PROXY_URL 保持一致

      # 默认停用 UI；改为 "yes" 可启用
      SERVICE_UI: "no"
    volumes:
      - bw-storage:/data
    networks:
      - bw-universe

volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
```

有关身份验证、权限 (ACL)、速率限制、TLS 和配置选项的详细信息，请参阅 [API 文档](api.md)。

### 访问设置向导

默认情况下，当您首次运行 AIO 容器时，设置向导会自动启动。要访问它，请按照以下步骤操作：

1.  **启动 AIO 容器**，如[上文](#deployment)所述，确保 `SERVICE_UI=yes` (默认)。
2.  通过您的主要 BunkerWeb 端点**访问 UI**，例如 `https://your-domain`。

> 请按照[快速入门指南](quickstart-guide.md#complete-the-setup-wizard)中的后续步骤设置 Web UI。

### Redis 集成 {#redis-integration}

BunkerWeb **一体化**镜像开箱即用地包含了 Redis，用于[持久化封禁和报告](advanced.md#persistence-of-bans-and-reports)。请注意：

- 只有在 `USE_REDIS=yes` **且** `REDIS_HOST` 保持默认值 (`127.0.0.1`/`localhost`) 时，内置 Redis 服务才会启动。
- 它仅监听容器的回环接口，因此只能被容器内部的进程访问，其他容器或宿主机无法直接访问。
- 仅当你已经准备好外部 Redis/Valkey 终端时才覆盖 `REDIS_HOST`，否则内置实例将不会启动。
- 若要完全禁用 Redis，请设置 `USE_REDIS=no`。
- Redis 日志在 Docker 日志和 `/var/log/bunkerweb/redis.log` 中以 `[REDIS]` 前缀出现。

### CrowdSec 集成 {#crowdsec-integration}

BunkerWeb **一体化** Docker 镜像完全集成了 CrowdSec——无需额外的容器或手动设置。请按照以下步骤在您的部署中启用、配置和扩展 CrowdSec。

默认情况下，CrowdSec 是**禁用**的。要开启它，只需添加 `USE_CROWDSEC` 环境变量：

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

*   当 `USE_CROWDSEC=yes` 时，入口点将：

    1.  **注册**并**启动**本地 CrowdSec 代理（通过 `cscli`）。
    2.  **安装或升级**默认的集合和解析器。
    3.  **配置** `crowdsec-bunkerweb-bouncer/v1.6` 拦截器。

---

#### 默认集合和解析器

在首次启动时（或升级后），这些资产会自动安装并保持最新：

| 类型       | 名称                                    | 目的                                                                                                                                                         |
| ---------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **集合**   | `bunkerity/bunkerweb`                   | 保护 Nginx 服务器免受各种基于 HTTP 的攻击，从暴力破解到注入尝试。                                                                                            |
| **集合**   | `crowdsecurity/appsec-virtual-patching` | 提供一个动态更新的 WAF 风格规则集，针对已知的 CVE，每日自动修补以保护 Web 应用程序免受新发现的漏洞影响。                                                     |
| **集合**   | `crowdsecurity/appsec-generic-rules`    | 对 `crowdsecurity/appsec-virtual-patching` 进行补充，提供针对通用应用层攻击模式的启发式规则——例如枚举、路径遍历和自动化探测——填补了尚无 CVE 特定规则的空白。 |
| **解析器** | `crowdsecurity/geoip-enrich`            | 用 GeoIP 上下文丰富事件                                                                                                                                      |

<details>
<summary><strong>内部工作原理</strong></summary>

入口点脚本调用：

```bash
cscli hub update
cscli install collection bunkerity/bunkerweb
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

!!! info "Docker 中看不到集合？"
    如果在容器内执行 `cscli collections list` 仍然看不到 `bunkerity/bunkerweb`，请运行 `docker exec -it bunkerweb-aio cscli hub update`，然后重启容器（`docker restart bunkerweb-aio`），以刷新本地 hub 缓存。

---

#### 添加额外的集合

需要更多的覆盖范围？使用一个以空格分隔的 Hub 集合列表来定义 `CROWDSEC_EXTRA_COLLECTIONS`：

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/apache2 crowdsecurity/mysql" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

!!! info "内部工作原理"

    脚本会遍历每个名称并根据需要进行安装或升级——无需手动步骤。

---

#### 禁用特定解析器

如果您想保留默认设置但明确禁用一个或多个解析器，请通过 `CROWDSEC_DISABLED_PARSERS` 提供一个以空格分隔的列表：

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_DISABLED_PARSERS="crowdsecurity/geoip-enrich foo/bar-parser" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

注意：
- 该列表在安装/更新所需项目后应用；只有您列出的解析器会被移除。
- 使用 `cscli parsers list` 显示的 hub slug（例如，`crowdsecurity/geoip-enrich`）。

---

#### AppSec 开关

CrowdSec [AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) 功能——由 `appsec-virtual-patching` 和 `appsec-generic-rules` 集合提供支持——**默认启用**。

要**禁用**所有 AppSec (WAF/虚拟补丁) 功能，请设置：

```bash
-e CROWDSEC_APPSEC_URL=""
```

这实际上会关闭 AppSec 端点，因此不会应用任何规则。

---

#### 外部 CrowdSec API

如果您操作一个远程 CrowdSec 实例，请将容器指向您的 API：

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_API="https://crowdsec.example.com:8000" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6-rc3
```

*   当 `CROWDSEC_API` 不是 `127.0.0.1` 或 `localhost` 时，将跳过**本地注册**。
*   使用外部 API 时，**AppSec** 默认是禁用的。要启用它，请将 `CROWDSEC_APPSEC_URL` 设置为您期望的端点。
*   拦截器注册仍然会针对远程 API 进行。
*   要重用现有的拦截器密钥，请提供 `CROWDSEC_API_KEY` 并附上您预先生成的令牌。

---

!!! tip "更多选项"
    有关所有 CrowdSec 选项的全面介绍（自定义场景、日志、故障排除等），请参阅 [BunkerWeb CrowdSec 插件文档](features.md#crowdsec)或访问[官方 CrowdSec 网站](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs)。

## Docker {#docker}

<figure markdown>
  ![概述](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker 集成</figcaption>
</figure>

使用 BunkerWeb 作为 [Docker](https://www.docker.com/) 容器提供了一种方便直接的方法来测试和使用该解决方案，特别是如果您已经熟悉 Docker 技术。

为了方便您的 Docker 部署，我们在 [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb) 上提供了支持多种架构的预构建镜像。这些预构建镜像经过优化，可用于以下架构：

- x64 (64位)
- x86
- armv8 (ARM 64位)
- armv7 (ARM 32位)

通过从 Docker Hub 获取这些预构建镜像，您可以快速在您的 Docker 环境中拉取并运行 BunkerWeb，无需进行广泛的配置或设置过程。这种简化的方法让您能够专注于利用 BunkerWeb 的功能，而无需不必要的复杂性。

无论您是进行测试、开发应用程序还是在生产中部署 BunkerWeb，Docker 容器化选项都提供了灵活性和易用性。采用这种方法使您能够充分利用 BunkerWeb 的功能，同时利用 Docker 技术的优势。

```shell
docker pull bunkerity/bunkerweb:1.6.6-rc3
```

Docker 镜像也可在 [GitHub packages](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) 上找到，可以使用 `ghcr.io` 仓库地址下载：

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.6-rc3```

Docker 集成的关键概念包括：

- **环境变量**：使用环境变量轻松配置 BunkerWeb。这些变量允许您自定义 BunkerWeb 行为的各个方面，例如网络设置、安全选项和其他参数。
- **调度器容器**：使用一个名为[调度器](concepts.md#scheduler)的专用容器来管理配置和执行作业。
- **网络**：Docker 网络在 BunkerWeb 的集成中扮演着至关重要的角色。这些网络有两个主要目的：向客户端公开端口以及连接到上游 Web 服务。通过公开端口，BunkerWeb 可以接受来自客户端的传入请求，允许他们访问受保护的 Web 服务。此外，通过连接到上游 Web 服务，BunkerWeb 可以高效地路由和管理流量，提供增强的安全性和性能。

!!! info "数据库后端"
    请注意，我们的说明假设您正在使用 SQLite 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，也支持其他数据库后端。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations)中的 docker-compose 文件。

### 环境变量

设置通过 Docker 环境变量传递给调度器：

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # 用于持久化缓存和备份等其他数据
...
```

!!! info "完整列表"
    有关环境变量的完整列表，请参阅文档的[设置部分](features.md)。

### 使用 Docker secrets

与其通过环境变量传递敏感设置，不如将它们存储为 Docker secrets。对于每个您想要保护的设置，创建一个名称与设置键（大写）匹配的 Docker secret。BunkerWeb 的入口点脚本会自动从 `/run/secrets` 加载 secrets 并将它们导出为环境变量。

示例：
```bash
# 为 ADMIN_PASSWORD 创建一个 Docker secret
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

部署时挂载 secrets：
```yaml
services:
  bw-ui:
    secrets:
      - ADMIN_PASSWORD
...
secrets:
  ADMIN_PASSWORD:
    external: true
```

这确保了敏感设置不会出现在环境和日志中。

### 调度器

[调度器](concepts.md#scheduler) 在其自己的容器中运行，该容器也可在 Docker Hub 上找到：

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.6-rc3
```

!!! info "BunkerWeb 设置"

    自 `1.6.0` 版本起，调度器容器是您定义 BunkerWeb 设置的地方。然后，调度器将配置推送到 BunkerWeb 容器。

    ⚠ **重要提示**：所有与 API 相关的设置（例如 `API_HTTP_PORT`、`API_LISTEN_IP`、`API_SERVER_NAME`、`API_WHITELIST_IP`，如果您使用 `API_TOKEN` 的话也包括它）**也必须在 BunkerWeb 容器中定义**。这些设置必须在两个容器中保持一致；否则，BunkerWeb 容器将不接受来自调度器的 API 请求。

    ```yaml
    x-bw-api-env: &bw-api-env
      # 我们使用一个锚点来避免在两个容器中重复相同的设置
      API_HTTP_PORT: "5000" # 默认值
      API_LISTEN_IP: "0.0.0.0" # 默认值
      API_SERVER_NAME: "bwapi" # 默认值
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # 根据您的网络设置来配置
      # 可选的令牌；如果设置，调度器会发送 Authorization: Bearer <token>
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        environment:
          # 这将为 BunkerWeb 容器设置 API
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
        environment:
          # 这将为调度器容器设置 API
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

需要一个卷来存储调度器使用的 SQLite 数据库和备份：

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "为持久化数据使用本地文件夹"
    调度器在容器内以**UID 101 和 GID 101 的非特权用户**身份运行。这增强了安全性：万一漏洞被利用，攻击者将不会拥有完全的 root (UID/GID 0) 权限。

    但是，如果您为持久化数据使用**本地文件夹**，您必须**设置正确的权限**，以便非特权用户可以向其中写入数据。例如：

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    或者，如果文件夹已经存在：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    如果您正在使用[无根模式的 Docker](https://docs.docker.com/engine/security/rootless) 或 [Podman](https://podman.io/)，容器中的 UID 和 GID 将映射到主机上不同的 UID 和 GID。您首先需要检查您的初始 subuid 和 subgid：

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    例如，如果您的值为 **100000**，则映射的 UID/GID 将为 **100100** (100000 + 100)：

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    或者如果文件夹已经存在：

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### 网络

默认情况下，BunkerWeb 容器在（容器内部）**8080/tcp** 端口上监听 **HTTP**，在 **8443/tcp** 端口上监听 **HTTPS**，在 **8443/udp** 端口上监听 **QUIC**。

!!! warning "在无根模式或使用 Podman 时的特权端口"
    如果您正在使用[无根模式的 Docker](https://docs.docker.com/engine/security/rootless) 并希望将特权端口（< 1024），如 80 和 443，重定向到 BunkerWeb，请参阅[此处](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports)的先决条件。

    如果您正在使用 [Podman](https://podman.io/)，可以降低非特权端口的最小数量：
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

使用 Docker 集成时，典型的 BunkerWeb 堆栈包含以下容器：

- BunkerWeb
- 调度器
- 您的服务

出于深度防御的目的，我们强烈建议创建至少三个不同的 Docker 网络：

- `bw-services`：用于 BunkerWeb 和您的 Web 服务
- `bw-universe`：用于 BunkerWeb 和调度器
- `bw-db`：用于数据库（如果您正在使用）

为了保护调度器和 BunkerWeb API 之间的通信，**请授权 API 调用**。使用 `API_WHITELIST_IP` 设置来指定允许的 IP 地址和子网。为了更强的保护，请在两个容器中设置 `API_TOKEN`；调度器将自动包含 `Authorization: Bearer <token>`。

**强烈建议为 `bw-universe` 网络使用静态子网**以增强安全性。通过实施这些措施，您可以确保只有授权的源才能访问 BunkerWeb API，从而降低未经授权的访问或恶意活动的风险：

```yaml
x-bw-api-env: &bw-api-env
  # 我们使用一个锚点来避免在两个容器中重复相同的设置
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  API_TOKEN: "" # 可选的 API 令牌
  # 可选的 API 令牌，用于经过身份验证的 API 访问
  API_TOKEN: ""

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-services
      - bw-universe
...
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # 这个设置是强制性的，用来指定 BunkerWeb 实例
    volumes:
      - bw-storage:/data # 用于持久化缓存和备份等其他数据
    restart: "unless-stopped"
    networks:
      - bw-universe
...
volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # 静态子网，以便只有授权的源可以访问 BunkerWeb API
  bw-services:
    name: bw-services
```

### 完整的 compose 文件

```yaml
x-bw-api-env: &bw-api-env
  # 我们使用一个锚点来避免在两个容器中重复相同的设置
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    depends_on:
      - bunkerweb
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # 这个设置是强制性的，用来指定 BunkerWeb 实例
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-storage:/data # 用于持久化缓存和备份等其他数据
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # 静态子网，以便只有授权的源可以访问 BunkerWeb API
  bw-services:
    name: bw-services
```

### 从源代码构建

或者，如果您更喜欢亲自动手，您可以选择直接从[源代码](https://github.com/bunkerity/bunkerweb)构建 Docker 镜像。从源代码构建镜像可以让您对部署过程有更大的控制和定制。但是，请注意，这种方法可能需要一些时间才能完成，具体取决于您的硬件配置（如果需要，您可以去喝杯咖啡 ☕）。

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t bw -f src/bw/Dockerfile . && \
docker build -t bw-scheduler -f src/scheduler/Dockerfile . && \
docker build -t bw-autoconf -f src/autoconf/Dockerfile . && \
docker build -t bw-ui -f src/ui/Dockerfile .
```

## Linux

<figure markdown>
  ![概述](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Linux 集成</figcaption>
</figure>

支持 BunkerWeb 的 Linux 发行版（amd64/x86_64 和 arm64/aarch64 架构）包括：

- Debian 12 "Bookworm"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41 和 42
- Red Hat Enterprise Linux (RHEL) 8, 9 和 10

### 简易安装脚本

为了简化安装体验，BunkerWeb 提供了一个简易安装脚本，可以自动处理整个设置过程，包括 NGINX 安装、仓库配置和服务设置。

#### 快速开始

要开始使用，请下载安装脚本及其校验和，然后在运行前验证脚本的完整性。

```bash
# 下载脚本及其校验和
wget https://github.com/bunkerity/bunkerweb/releases/download/v1.6.6-rc3/install-bunkerweb.sh
wget https://github.com/bunkerity/bunkerweb/releases/download/v1.6.6-rc3/install-bunkerweb.sh.sha256

# 验证校验和
sha256sum -c install-bunkerweb.sh.sha256

# 如果检查成功，则运行脚本
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! danger "安全提示"
    **在运行安装脚本之前，请务必验证其完整性。**

    下载校验和文件，并使用像 `sha256sum` 这样的工具来确认脚本没有被更改或篡改。

    如果校验和验证失败，**请不要执行该脚本**——它可能不安全。

#### 工作原理

简易安装脚本是一个强大的工具，旨在简化在全新的 Linux 系统上设置 BunkerWeb 的过程。它会自动执行以下关键步骤：

1.  **系统分析**：检测您的操作系统并对照支持的发行版列表进行验证。
2.  **安装定制**：在交互模式下，它会提示您选择安装类型（一体化、管理器、工作节点等），并决定是否启用基于 Web 的设置向导。
3.  **可选集成**：提供自动安装和配置 [CrowdSec 安全引擎](#crowdsec-integration-with-the-script)的选项。
4.  **依赖管理**：从官方源安装 BunkerWeb 所需的正确版本的 NGINX，并锁定版本以防止意外升级。
5.  **BunkerWeb 安装**：添加 BunkerWeb 软件包仓库，安装必要的软件包，并锁定版本。
6.  **服务配置**：根据您选择的安装类型设置并启用 `systemd` 服务。
7.  **安装后指导**：提供清晰的后续步骤，帮助您开始使用新的 BunkerWeb 实例。

#### 交互式安装

当不带任何选项运行时，脚本会进入一个交互模式，引导您完成设置过程。您将被要求做出以下选择：

1.  **安装类型**：选择您想要安装的组件。
    *   **完整堆栈（默认）**：一个一体化的安装，包括 BunkerWeb、调度器和 Web UI。
    *   **管理器**：安装调度器和 Web UI，用于管理一个或多个远程 BunkerWeb 工作节点。
    *   **工作节点**：仅安装 BunkerWeb 实例，可由远程管理器管理。
    *   **仅调度器**：仅安装调度器组件。
    *   **仅 Web UI**：仅安装 Web UI 组件。
2.  **设置向导**：选择是否启用基于 Web 的配置向导。强烈建议初次使用的用户选择此项。
3.  **CrowdSec 集成**：选择安装 CrowdSec 安全引擎，以获得先进的实时威胁防护。
4.  **CrowdSec AppSec**：如果您选择安装 CrowdSec，您还可以启用应用程序安全 (AppSec) 组件，它增加了 WAF 功能。
5.  **API 服务**：选择是否启用可选的 BunkerWeb API 服务。在 Linux 安装中，它默认是禁用的。

!!! info "管理器和调度器安装"
    如果您选择**管理器**或**仅调度器**安装类型，系统还会提示您提供您的 BunkerWeb 工作节点实例的 IP 地址或主机名。

#### 命令行选项

对于非交互式或自动化设置，可以使用命令行标志来控制脚本：

**通用选项：**

| 选项                    | 描述                                              |
| ----------------------- | ------------------------------------------------- |
| `-v, --version VERSION` | 指定要安装的 BunkerWeb 版本（例如 `1.6.6-rc3`）。 |
| `-w, --enable-wizard`   | 启用设置向导。                                    |
| `-n, --no-wizard`       | 禁用设置向导。                                    |
| `-y, --yes`             | 以非交互模式运行，对所有提示使用默认答案。        |
| `-f, --force`           | 即使在不受支持的操作系统版本上，也强制继续安装。  |
| `-q, --quiet`           | 静默安装（抑制输出）。                            |
| `--api`, `--enable-api` | 启用 API (FastAPI) systemd 服务（默认禁用）。     |
| `--no-api`              | 明确禁用 API 服务。                               |
| `-h, --help`            | 显示包含所有可用选项的帮助信息。                  |
| `--dry-run`             | 显示将要安装的内容，但不实际执行。                |

**安装类型：**

| 选项               | 描述                                                  |
| ------------------ | ----------------------------------------------------- |
| `--full`           | 完整堆栈安装（BunkerWeb、调度器、UI）。这是默认选项。 |
| `--manager`        | 安装调度器和 UI 以管理远程工作节点。                  |
| `--worker`         | 仅安装 BunkerWeb 实例。                               |
| `--scheduler-only` | 仅安装调度器组件。                                    |
| `--ui-only`        | 仅安装 Web UI 组件。                                  |

**安全集成：**

| 选项                | 描述                                               |
| ------------------- | -------------------------------------------------- |
| `--crowdsec`        | 安装并配置 CrowdSec 安全引擎。                     |
| `--no-crowdsec`     | 跳过 CrowdSec 安装。                               |
| `--crowdsec-appsec` | 安装带有 AppSec 组件的 CrowdSec（包括 WAF 功能）。 |

**高级选项：**

| 选项                    | 描述                                                             |
| ----------------------- | ---------------------------------------------------------------- |
| `--instances "IP1 IP2"` | 以空格分隔的 BunkerWeb 实例列表（在管理器/调度器模式下为必需）。 |

**用法示例：**

```bash
# 以交互模式运行（推荐给大多数用户）
sudo ./install-bunkerweb.sh

# 使用默认设置进行非交互式安装（完整堆栈，启用向导）
sudo ./install-bunkerweb.sh --yes

# 安装一个不带设置向导的工作节点
sudo ./install-bunkerweb.sh --worker --no-wizard

# 安装一个特定版本
sudo ./install-bunkerweb.sh --version 1.6.6-rc3

# 带有远程工作实例的管理器设置（需要 instances）
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# 带有 CrowdSec 和 AppSec 的完整安装
sudo ./install-bunkerweb.sh --crowdsec-appsec

# 静默非交互式安装
sudo ./install-bunkerweb.sh --quiet --yes

# 预览安装而不执行
sudo ./install-bunkerweb.sh --dry-run

# 在简易安装期间启用 API（非交互式）
sudo ./install-bunkerweb.sh --yes --api

# 错误：CrowdSec 不能用于工作节点安装
# sudo ./install-bunkerweb.sh --worker --crowdsec  # 这将失败

# 错误：在非交互模式下，管理器需要 instances
# sudo ./install-bunkerweb.sh --manager --yes  # 如果没有 --instances，这将失败
```

!!! warning "关于选项兼容性的重要说明"

    **CrowdSec 限制：**
    - CrowdSec 选项（`--crowdsec`, `--crowdsec-appsec`）仅与 `--full`（默认）和 `--manager` 安装类型兼容
    - 它们不能与 `--worker`, `--scheduler-only` 或 `--ui-only` 安装一起使用

    **Instances 要求：**
    - `--instances` 选项仅对 `--manager` 和 `--scheduler-only` 安装类型有效
    - 当使用 `--manager` 或 `--scheduler-only` 并带有 `--yes`（非交互模式）时，`--instances` 选项是强制性的
    - 格式：`--instances "192.168.1.10 192.168.1.11 192.168.1.12"`

    **交互式与非交互式：**
    - 交互模式（默认）将提示输入缺失的必需值
    - 非交互模式（`--yes`）要求通过命令行提供所有必要的选项

#### CrowdSec 与脚本的集成 {#crowdsec-integration-with-the-script}

如果您选择在交互式设置过程中安装 CrowdSec，脚本会完全自动化其与 BunkerWeb 的集成：

- 它会添加官方的 CrowdSec 仓库并安装代理。
- 它会创建一个新的采集文件，让 CrowdSec 解析 BunkerWeb 的日志（`access.log`、`error.log` 和 `modsec_audit.log`）。
- 它会安装必要的集合（`bunkerity/bunkerweb`）和解析器（`crowdsecurity/geoip-enrich`）。
- 它会为 BunkerWeb 注册一个拦截器，并自动在 `/etc/bunkerweb/variables.env` 中配置 API 密钥。
- 如果您还选择了**AppSec 组件**，它会安装 `appsec-virtual-patching` 和 `appsec-generic-rules` 集合，并为 BunkerWeb 配置 AppSec 端点。

这提供了一个无缝、开箱即用的集成，以实现强大的入侵防护。

#### RHEL 注意事项

!!! warning "RHEL-based 系统上的外部数据库支持"
    如果您计划使用外部数据库（推荐用于生产环境），您必须安装相应的数据库客户端软件包：

    ```bash
    # 对于 MariaDB
    sudo dnf install mariadb

    # 对于 MySQL
    sudo dnf install mysql

    # 对于 PostgreSQL
    sudo dnf install postgresql
    ```

    这是 BunkerWeb 调度器连接到您的外部数据库所必需的。

#### 安装后

根据您在安装过程中的选择：

**启用设置向导：**

1.  在以下地址访问设置向导：`https://your-server-ip/setup`
2.  按照引导配置来设置您的第一个受保护的服务
3.  配置 SSL/TLS 证书和其他安全设置

**未启用设置向导：**

1.  编辑 `/etc/bunkerweb/variables.env` 来手动配置 BunkerWeb
2.  添加您的服务器设置和受保护的服务
3.  重启调度器：`sudo systemctl restart bunkerweb-scheduler`

### 使用包管理器安装

请确保在安装 BunkerWeb 之前**已经安装了 NGINX 1.28.0**。对于除 Fedora 之外的所有发行版，强制要求使用来自[官方 NGINX 仓库](https://nginx.org/en/linux_packages.html)的预构建包。从源代码编译 NGINX 或使用来自不同仓库的包将无法与 BunkerWeb 的官方预构建包一起工作。但是，您可以选择从源代码构建 BunkerWeb。

=== "Debian Bookworm/Trixie"

    第一步是添加 NGINX 官方仓库：

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    您现在应该能够安装 NGINX 1.28.0：

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "测试/开发版本"
        如果您使用 `testing` 或 `dev` 版本，您需要在安装 BunkerWeb 之前将 `force-bad-version` 指令添加到您的 `/etc/dpkg/dpkg.cfg` 文件中。

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "禁用设置向导"
        如果您不希望在安装 BunkerWeb 时使用 Web UI 的设置向导，请导出以下变量：

        ```shell
        export UI_WIZARD=no
        ```

    最后安装 BunkerWeb 1.6.6-rc3：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.6-rc3
    ```

    要防止在执行 `apt upgrade` 时升级 NGINX 和/或 BunkerWeb 包，您可以使用以下命令：

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    第一步是添加 NGINX 官方仓库：

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    您现在应该能够安装 NGINX 1.28.0：

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "测试/开发版本"
        如果您使用 `testing` 或 `dev` 版本，您需要在安装 BunkerWeb 之前将 `force-bad-version` 指令添加到您的 `/etc/dpkg/dpkg.cfg` 文件中。

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "禁用设置向导"
        如果您不希望在安装 BunkerWeb 时使用 Web UI 的设置向导，请导出以下变量：

        ```shell
        export UI_WIZARD=no
        ```

    最后安装 BunkerWeb 1.6.6-rc3：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.6-rc3
    ```

    要防止在执行 `apt upgrade` 时升级 NGINX 和/或 BunkerWeb 包，您可以使用以下命令：

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora 更新测试"
        如果您在稳定仓库中找不到列出的 NGINX 版本，可以启用 `updates-testing` 仓库：

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora 已经提供了我们支持的 NGINX 1.28.0

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.0
    ```

    !!! example "禁用设置向导"
        如果您不希望在安装 BunkerWeb 时使用 Web UI 的设置向导，请导出以下变量：

        ```shell
        export UI_WIZARD=no
        ```

    最后安装 BunkerWeb 1.6.6-rc3：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y --allowerasing bunkerweb-1.6.6-rc3
    ```

    要防止在执行 `dnf upgrade` 时升级 NGINX 和/或 BunkerWeb 包，您可以使用以下命令：

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    第一步是添加 NGINX 官方仓库。在 `/etc/yum.repos.d/nginx.repo` 处创建以下文件：

    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true

    [nginx-mainline]
    name=nginx mainline repo
    baseurl=http://nginx.org/packages/mainline/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=0
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
    ```

    您现在应该能够安装 NGINX 1.28.0：

    ```shell
    sudo dnf install --allowerasing nginx-1.28.0
    ```

    !!! example "禁用设置向导"
        如果您不希望在安装 BunkerWeb 时使用 Web UI 的设置向导，请导出以下变量：

        ```shell
        export UI_WIZARD=no
        ```

    最后安装 BunkerWeb 1.6.6-rc3：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.6-rc3
    ```

    要防止在执行 `dnf upgrade` 时升级 NGINX 和/或 BunkerWeb 包，您可以使用以下命令：

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### 配置和服务

BunkerWeb 的手动配置是通过编辑 `/etc/bunkerweb/variables.env` 文件来完成的：

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

安装后，BunkerWeb 带有三个服务 `bunkerweb`、`bunkerweb-scheduler` 和 `bunkerweb-ui`，您可以使用 `systemctl` 来管理它们。

如果您手动编辑了 BunkerWeb 的配置（使用 `/etc/bunkerweb/variables.env`），重启 `bunkerweb-scheduler` 服务就足以生成并重新加载配置，而不会有任何停机时间。但在某些情况下（例如更改监听端口），您可能需要重启 `bunkerweb` 服务。

### 高可用性

调度器可以与 BunkerWeb 实例分离，以提供高可用性。在这种情况下，调度器将安装在一台独立的服务器上，并能够管理多个 BunkerWeb 实例。

#### 管理器

要仅在服务器上安装调度器，您可以在执行 BunkerWeb 安装之前导出以下变量：

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

或者，您也可以导出以下变量以仅启用调度器：

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

#### 工作节点

在另一台服务器上，要仅安装 BunkerWeb，您可以在执行 BunkerWeb 安装之前导出以下变量：

```shell
export WORKER_MODE=yes
```

或者，您也可以导出以下变量以仅启用 BunkerWeb：

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

#### Web UI

Web UI 可以安装在一台独立的服务器上，以提供一个专门用于管理 BunkerWeb 实例的界面。要仅安装 Web UI，您可以在执行 BunkerWeb 安装之前导出以下变量：

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

## Docker 自动配置 {#docker-autoconf}

<figure markdown>
  ![概述](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Docker 自动配置集成</figcaption>
</figure>

!!! info "Docker 集成"
    Docker 自动配置集成是 Docker 集成的一个“演进”。如果需要，请先阅读[Docker 集成部分](#docker)。

有一种替代方法可以解决每次更新时都需要重新创建容器的不便。通过使用另一个名为 **autoconf** 的镜像，您可以自动实时重新配置 BunkerWeb，而无需重新创建容器。

要利用此功能，您可以为您的 Web 应用程序容器添加**标签**，而不是为 BunkerWeb 容器定义环境变量。然后，**autoconf** 镜像将监听 Docker 事件，并无缝处理 BunkerWeb 的配置更新。

这个“*自动化*”过程简化了 BunkerWeb 配置的管理。通过为您的 Web 应用程序容器添加标签，您可以将重新配置任务委托给 **autoconf**，而无需手动干预容器的重新创建。这简化了更新过程并增强了便利性。

通过采用这种方法，您可以享受 BunkerWeb 的实时重新配置，而无需重新创建容器的麻烦，使其更高效、更用户友好。

!!! info "多站点模式"
    Docker 自动配置集成意味着使用**多站点模式**。有关更多信息，请参阅文档的[多站点部分](concepts.md#multisite-mode)。

!!! info "数据库后端"
    请注意，我们的说明假设您正在使用 MariaDB 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，我们理解您可能更喜欢为您的 Docker 集成使用其他后端。如果是这样，请放心，其他数据库后端仍然是可行的。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations)中的 docker-compose 文件。

要启用自动配置更新，请在堆栈中包含一个名为 `bw-autoconf` 的额外容器。此容器承载自动配置服务，该服务管理 BunkerWeb 的动态配置更改。

为了支持此功能，请使用一个专用的“真实”数据库后端（例如，MariaDB、MySQL 或 PostgreSQL）进行同步配置存储。通过集成 `bw-autoconf` 和合适的数据库后端，您为 BunkerWeb 中无缝的自动配置管理建立了基础设施。

```yaml
x-bw-env: &bw-env
  # 我们使用一个锚点来避免在两个容器中重复相同的设置
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    labels:
      - "bunkerweb.INSTANCE=yes" # 自动配置服务识别 BunkerWeb 实例的强制性标签
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # 我们不需要在这里指定 BunkerWeb 实例，因为它们由自动配置服务自动检测
      SERVER_NAME: "" # 服务器名称将由服务标签填充
      MULTISITE: "yes" # 自动配置的强制性设置
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
    volumes:
      - bw-storage:/data # 用于持久化缓存和备份等其他数据
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
    depends_on:
      - bunkerweb
      - bw-docker
    environment:
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
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
    restart: "unless-stopped"
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
      MYSQL_PASSWORD: "changeme" # 记得为数据库设置一个更强的密码
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
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
  bw-docker:
    name: bw-docker
  bw-db:
    name: bw-db
```

!!! info "数据库在 `bw-db` 网络中"
    数据库容器有意未包含在 `bw-universe` 网络中。它由 `bw-autoconf` 和 `bw-scheduler` 容器使用，而不是直接由 BunkerWeb 使用。因此，数据库容器是 `bw-db` 网络的一部分，这通过使对数据库的外部访问更具挑战性来增强安全性。**这种刻意的设计选择有助于保护数据库并加强系统的整体安全视角**。

!!! warning "在无根模式下使用 Docker"
    如果您正在使用[无根模式的 Docker](https://docs.docker.com/engine/security/rootless)，您需要将 docker 套接字的挂载替换为以下值：`$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`。

### 自动配置服务

一旦堆栈设置好，您将能够创建 Web 应用程序容器，并使用“bunkerweb.”前缀将设置添加为标签，以便自动设置 BunkerWeb：

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### 命名空间 {#namespaces}

从 `1.6.0` 版本开始，BunkerWeb 的自动配置堆栈现在支持命名空间。此功能使您能够在同一个 Docker 主机上管理多个 BunkerWeb 实例和服务的“*集群*”。要利用命名空间，只需在您的服务上设置 `NAMESPACE` 标签。这是一个示例：

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.NAMESPACE=my-namespace" # 为服务设置命名空间
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "命名空间行为"

    默认情况下，所有自动配置堆栈都监听所有命名空间。如果您想将一个堆栈限制在特定的命名空间，可以在 `bw-autoconf` 服务中设置 `NAMESPACES` 环境变量：

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # 为 BunkerWeb 实例设置命名空间，以便自动配置服务可以检测到它
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # 只监听这些命名空间
    ...
    ```

    请记住，`NAMESPACES` 环境变量是一个以空格分隔的命名空间列表。

!!! warning "命名空间规范"

    每个命名空间只能有**一个数据库**和**一个调度器**。如果您尝试在同一个命名空间中创建多个数据库或调度器，配置最终会相互冲突。

    调度器不需要 `NAMESPACE` 标签即可正常工作。它只需要正确配置 `DATABASE_URI` 设置，以便它可以访问与自动配置服务相同的数据库。

## Kubernetes

<figure markdown>
  ![概述](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Kubernetes 集成</figcaption>
</figure>

为了在 Kubernetes 环境中自动化 BunkerWeb 实例的配置，
autoconf 服务充当一个 [Ingress 控制器](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)。
它根据 [Ingress 资源](https://kubernetes.io/docs/concepts/services-networking/ingress/) 配置 BunkerWeb 实例，
并监控其他 Kubernetes 对象，例如 [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)，以获取自定义配置。

!!! info "ConfigMap 同步"
    - Ingress 控制器仅管理带有 `bunkerweb.io/CONFIG_TYPE` 注解的 ConfigMap。
    - 如果需要将配置限定到单个服务（服务器名必须已存在），请添加 `bunkerweb.io/CONFIG_SITE`；
      未设置时表示全局应用。
    - 删除该注解或删除 ConfigMap 会移除对应的自定义配置。

为了获得最佳设置，建议将 BunkerWeb 定义为一个 **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)**，这样可以确保在所有节点上都创建一个 pod，而将 **autoconf 和 scheduler** 定义为**单个副本的 [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)**。

鉴于存在多个 BunkerWeb 实例，有必要建立一个共享数据存储，实现为一个 [Redis](https://redis.io/) 或 [Valkey](https://valkey.io/) 服务。这些实例将利用该服务来缓存和共享彼此之间的数据。有关 Redis/Valkey 设置的更多信息，请参见[此处](features.md#redis)。

!!! info "数据库后端"
    请注意，我们的说明假设您正在使用 MariaDB 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，我们理解您可能更喜欢为您的 Docker 集成使用其他后端。如果是这样，请放心，其他数据库后端仍然是可行的。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations)中的 docker-compose 文件。

    集群数据库后端的设置超出了本文档的范围。

请确保自动配置服务有权访问 Kubernetes API。建议为此目的利用 [RBAC 授权](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)。

!!! warning "Kubernetes API 的自定义 CA"
    如果您为您的 Kubernetes API 使用自定义 CA，您可以在 ingress 控制器上挂载一个包含您的中间证书和根证书的捆绑文件，并将 `KUBERNETES_SSL_CA_CERT` 环境变量的值设置为容器内捆绑文件的路径。或者，即使不推荐，您也可以通过将 ingress 控制器的 `KUBERNETES_SSL_VERIFY` 环境变量设置为 `no`（默认为 `yes`）来禁用证书验证。

此外，**在使用 Kubernetes 集成时，将 `KUBERNETES_MODE` 环境变量设置为 `yes` 至关重要**。此变量是正常运行所必需的。

### 安装方法

#### 使用 helm chart（推荐）

安装 Kubernetes 的推荐方法是使用位于 `https://repo.bunkerweb.io/charts` 的 Helm chart：

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

然后您可以使用该仓库中的 bunkerweb helm chart：

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

值的完整列表在 [bunkerity/bunkerweb-helm 仓库](https://github.com/bunkerity/bunkerweb-helm) 的 [charts/bunkerweb/values.yaml 文件](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) 中列出。

#### 完整的 YAML 文件

除了使用 helm chart，您还可以使用 GitHub 仓库中 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations)内的 YAML 样板文件。请注意，我们强烈建议您改用 helm chart。

### Ingress 资源

一旦 BunkerWeb Kubernetes 堆栈成功设置并运行（有关详细信息，请参阅自动配置日志），您就可以继续在集群内部署 Web 应用程序并声明您的 Ingress 资源。

需要注意的是，BunkerWeb 设置需要作为 Ingress 资源的注解来指定。对于域部分，请使用特殊值 **`bunkerweb.io`**。通过包含适当的注解，您可以相应地为 Ingress 资源配置 BunkerWeb。

!!! tip "忽略嘈杂的注解"
    当某些注解不应影响 autoconf 时，请在控制器部署中设置 `KUBERNETES_IGNORE_ANNOTATIONS`。提供以空格或逗号分隔的注解键列表（例如 `bunkerweb.io/EXTRA_FOO`）或仅后缀（`EXTRA_FOO`）。匹配的注解将从 ingress 派生的设置中剥离，并且在实例发现期间完全跳过携带它们的 pod。

!!! info "TLS 支持"
    BunkerWeb ingress 控制器完全支持使用 tls 规范的自定义 HTTPS 证书，如示例所示。配置诸如 `cert-manager` 之类的解决方案以自动生成 tls secret 超出了本文档的范围。

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # 将应用于此 ingress 中的所有主机
    bunkerweb.io/MY_SETTING: "value"
    # 将仅应用于 www.example.com 主机
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  # TLS 是可选的，您也可以使用内置的 Let's Encrypt 等
  # tls:
  #   - hosts:
  #       - www.example.com
  #     secretName: secret-example-tls
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
...
```

### 命名空间 {#namespaces_1}

从 `1.6.0` 版本开始，BunkerWeb 的自动配置堆栈现在支持命名空间。此功能使您能够在同一个 Kubernetes 集群上管理多个 BunkerWeb 实例和服务的集群。要利用命名空间，只需在您的 BunkerWeb 实例和服务上设置 `namespace` 元数据字段。这是一个示例：

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # 为 BunkerWeb 实例设置命名空间
...
```

!!! info "命名空间行为"

    默认情况下，所有自动配置堆栈都监听所有命名空间。如果您想将一个堆栈限制在特定的命名空间，可以在 `bunkerweb-controller` 部署中设置 `NAMESPACES` 环境变量：

    ```yaml
    ...
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
      namespace: my-namespace # 为控制器设置命名空间
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-controller
      template:
        metadata:
          labels:
            app: bunkerweb-controller
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-controller
              image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
              imagePullPolicy: Always
              env:
                - name: NAMESPACES
                  value: "my-namespace my-other-namespace" # 只监听这些命名空间
                ...
    ...
    ```

    请记住，`NAMESPACES` 环境变量是一个以空格分隔的命名空间列表。

!!! warning "命名空间规范"

    每个命名空间只能有**一个数据库**和**一个调度器**。如果您尝试在同一个命名空间中创建多个数据库或调度器，配置最终会相互冲突。

    调度器不需要 `NAMESPACE` 注解即可正常工作。它只需要正确配置 `DATABASE_URI` 设置，以便它可以访问与自动配置服务相同的数据库。

### Ingress 类

当使用文档中的官方方法安装时，BunkerWeb 带有以下 `IngressClass` 定义：

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

为了限制 ingress 控制器监控的 `Ingress` 资源，您可以将 `KUBERNETES_INGRESS_CLASS` 环境变量的值设置为 `bunkerweb`。然后，您可以在您的 `Ingress` 定义中利用 `ingressClassName` 指令：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    bunkerweb.io/MY_SETTING: "value"
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  ingressClassName: bunkerweb
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
```

### 自定义域名

如果您为您的 Kubernetes 集群使用不同于默认 `kubernetes.local` 的自定义域名，您可以在调度器容器上使用 `KUBERNETES_DOMAIN_NAME` 环境变量来设置该值。

### 与现有 ingress 控制器一起使用

!!! info "同时保留现有 ingress 控制器和 BunkerWeb"

    这是一个您希望保留现有 ingress 控制器（例如 nginx）的用例。典型的流量流将是：负载均衡器 => Ingress 控制器 => BunkerWeb => 应用程序。

#### nginx ingress 控制器安装

安装 ingress nginx helm 仓库：

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

使用默认值安装 nginx ingress 控制器（可能无法在您自己的集群上开箱即用，请查看[文档](https://kubernetes.github.io/ingress-nginx/)）：

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

提取 LB 的 IP 地址：

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

设置 DNS 条目指向 LB 的 IP（例如 `bunkerweb` 子域用于 BW UI，`myapp` 用于应用程序）：

```bash
$ nslookup bunkerweb.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   bunkerweb.example.com
Address: 1.2.3.4
$ nslookup myapp.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   myapp.example.com
Address: 1.2.3.4
```

**BunkerWeb 安装**

安装 BunkerWeb helm 仓库：

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

创建 `values.yaml` 文件：

```yaml
# 这里我们将设置在现有 ingress 控制器后面设置 BunkerWeb 所需的值
# 带 BW 的流量流：LB => 现有 Ingress 控制器 => BunkerWeb => 服务
# 不带 BW 的流量流：LB => 现有 Ingress 控制器 => 服务

# 全局设置
settings:
  misc:
    # 替换为您的 DNS 解析器
    # 获取方法：在任意 pod 中执行 kubectl exec，然后 cat /etc/resolv.conf
    # 如果您的 nameserver 是一个 IP，则执行反向 DNS 查找：nslookup <IP>
    # 大多数情况下是 coredns.kube-system.svc.cluster.local 或 kube-dns.kube-system.svc.cluster.local
    dnsResolvers: "kube-dns.kube-system.svc.cluster.local"
  kubernetes:
    # 我们只考虑带有 ingressClass bunkerweb 的 Ingress 资源，以避免与现有 ingress 控制器冲突
    ingressClass: "bunkerweb"
    # 可选：您可以选择 BunkerWeb 将监听 Ingress/ConfigMap 更改的命名空间
    # 默认值（空白）是所有命名空间
    namespaces: ""

# 覆盖 bunkerweb-external 服务类型为 ClusterIP
# 因为我们不需要将其暴露给外部世界
# 我们将使用现有的 ingress 控制器将流量路由到 BunkerWeb
service:
  type: ClusterIP

# BunkerWeb 设置
bunkerweb:
  tag: 1.6.6-rc3

# 调度器设置
scheduler:
  tag: 1.6.6-rc3
  extraEnvs:
    # 启用 real IP 模块以获取客户端的真实 IP
    - name: USE_REAL_IP
      value: "yes"

# 控制器设置
controller:
  tag: 1.6.6-rc3

# UI 设置
ui:
  tag: 1.6.6-rc3
```

使用自定义值安装 BunkerWeb：

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

检查日志并等待一切就绪。

**Web UI 安装**

设置以下 ingress（假设已安装 nginx 控制器）：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ui-bunkerweb
  # 如果需要，替换为您的 BW 命名空间
  namespace: bunkerweb
  annotations:
    # 即使流量是内部的，Web UI 也必须使用 HTTPS
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    # 我们必须设置 SNI，以便 BW 可以提供正确的虚拟主机
    # 替换为您的域名
    nginx.ingress.kubernetes.io/proxy-ssl-name: "bunkerweb.example.com"
    nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"
spec:
  # 仅由 nginx 控制器提供服务，而不是 BW
  ingressClassName: nginx
  # 如果要使用自己的证书，请取消注释并进行编辑
  # tls:
  # - hosts:
  #   - bunkerweb.example.com
  #   secretName: tls-secret
  rules:
  # 替换为您的域名
  - host: bunkerweb.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # 由 Helm chart 创建
            name: bunkerweb-external
            port:
              # UI 必须使用 HTTPS 端口
              number: 443
```

现在您可以通过浏览 `https://bunkerweb.example.com/setup` 进入设置向导。

**保护现有应用程序**

**首先，您需要进入全局配置，选择 SSL 插件，然后禁用自动将 HTTP 重定向到 HTTPS。请注意，您只需要执行一次。**

假设您在 `myapp` 命名空间中有一个应用程序，该应用程序可以通过 `myapp-service` 服务在端口 `5000` 上访问。

您需要在 Web UI 上添加一个新服务并填写所需信息：

- 服务器名称：您的应用程序的公共域名（例如 `myapp.example.com`）
- SSL/TLS：您的 ingress 控制器负责该部分，因此不要在 BunkerWeb 上启用它，因为流量在集群内部
- 反向代理主机：您在集群内的应用程序的完整 URL（例如 `http://myapp-service.myapp.svc.cluster.local:5000`）

添加新服务后，您现在可以为该服务声明一个 Ingress 资源，并将其路由到 BunkerWeb 服务的 HTTP 端口：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  # 如果需要，替换为您的 BW 命名空间
  namespace: bunkerweb
spec:
  # 仅由 nginx 控制器提供服务，而不是 BW
  ingressClassName: nginx
  # 如果要使用自己的证书，请取消注释并进行编辑
  # tls:
  # - hosts:
  #   - myapp.example.com
  #   secretName: tls-secret
  rules:
  # 替换为您的域名
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # 由 Helm chart 创建
            name: bunkerweb-external
            port:
              number: 80
```

您可以访问 `http(s)://myapp.example.com`，现在它已受到 BunkerWeb 的保护 🛡️

## Swarm

<figure markdown>
  ![概述](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Docker Swarm 集成</figcaption>
</figure>

!!! warning "已弃用"
    Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](#kubernetes)。

!!! tip "PRO 支持"
    **如果您需要 Swarm 支持**，请通过 [contact@bunkerity.com](mailto:contact@bunkerity.com) 或[联系表单](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc)与我们联系。

!!! info "Docker 自动配置"
    Swarm 集成与 Docker 自动配置集成类似（但使用服务而不是容器）。如果需要，请先阅读[Docker 自动配置集成部分](#docker-autoconf)。

为了实现 BunkerWeb 实例的自动配置，**autoconf** 服务需要访问 Docker API。该服务监听 Docker Swarm 事件，例如服务的创建或删除，并实时无缝地配置 **BunkerWeb 实例**，而不会造成任何停机。它还监控其他 Swarm 对象，例如用于自定义配置的 [configs](https://docs.docker.com/engine/swarm/configs/)。

与 [Docker autoconf 集成](#docker-autoconf)类似，Web 服务的配置是使用以 **bunkerweb** 前缀开头的标签来定义的。

为了获得最佳设置，建议将 **BunkerWeb 服务**调度为所有节点上的***全局服务***，而将 **autoconf、scheduler 和 Docker API 代理服务**调度为***单个副本的服务***。请注意，Docker API 代理服务需要调度在管理器节点上，除非您将其配置为使用远程 API（这不在文档的讨论范围内）。

由于运行着多个 BunkerWeb 实例，必须创建一个共享数据存储，实现为 [Redis](https://redis.io/) 或 [Valkey](https://valkey.io/) 服务。这些实例将利用 Redis/Valkey 服务来缓存和共享数据。有关 Redis/Valkey 设置的更多详细信息，请参见[此处](features.md#redis)。

至于数据库卷，文档并未指定具体的方法。为数据库卷选择共享文件夹或特定驱动程序取决于您的独特用例，留给读者自行决定。

!!! info "数据库后端"
    请注意，我们的说明假设您正在使用 MariaDB 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，我们理解您可能更喜欢为您的 Docker 集成使用其他后端。如果是这样，请放心，其他数据库后端仍然是可行的。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6-rc3/misc/integrations)中的 docker-compose 文件。

    集群数据库后端的设置超出了本文档的范围。

这是您可以使用 `docker stack deploy` 部署的堆栈样板：

```yaml
x-bw-env: &bw-env
  # 我们使用一个锚点来避免在两个服务中重复相同的设置
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6-rc3
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
        protocol: udp # QUIC
    environment:
      <<: *bw-env
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
        - "bunkerweb.INSTANCE=yes" # autoconf 服务识别 BunkerWeb 实例的强制性标签

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6-rc3
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # 我们不需要在这里指定 BunkerWeb 实例，因为它们由 autoconf 服务自动检测
      SERVER_NAME: "" # 服务器名称将由服务标签填充
      MULTISITE: "yes" # autoconf 的强制性设置
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-storage:/data # 用于持久化缓存和备份等其他数据
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
    environment:
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
      DOCKER_HOST: "tcp://bw-docker:2375" # Docker 套接字
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-docker
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    environment:
      CONFIGS: "1"
      CONTAINERS: "1"
      SERVICES: "1"
      SWARM: "1"
      TASKS: "1"
      LOG_LEVEL: "warning"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: "unless-stopped"
    networks:
      - bw-docker
    deploy:
      placement:
        constraints:
          - "node.role == manager"

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
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-redis:
    image: redis:7-alpine
    restart: "unless-stopped"
    networks:
      - bw-universe
    deploy:
      placement:
        constraints:
          - "node.role == worker"

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

!!! info "Swarm 强制设置"
    请注意，在使用 Swarm 集成时，`SWARM_MODE: "yes"` 环境变量是强制性的。

### Swarm 服务

一旦 BunkerWeb Swarm 堆栈设置并运行（有关更多信息，请参阅 autoconf 和 scheduler 日志），您将能够在该集群中部署 Web 应用程序，并使用标签来动态配置 BunkerWeb：

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### 命名空间 {#namespaces_2}

从 `1.6.0` 版本开始，BunkerWeb 的自动配置堆栈现在支持命名空间。此功能使您能够在同一个 Docker 主机上管理多个 BunkerWeb 实例和服务的“*集群*”。要利用命名空间，只需在您的服务上设置 `NAMESPACE` 标签。这是一个示例：

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.NAMESPACE=my-namespace" # 为服务设置命名空间
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "命名空间行为"

    默认情况下，所有自动配置堆栈都监听所有命名空间。如果您想将一个堆栈限制在特定的命名空间，可以在 `bw-autoconf` 服务中设置 `NAMESPACES` 环境变量：

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6-rc3
        ...
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"
            - "bunkerweb.NAMESPACE=my-namespace" # 为 BunkerWeb 实例设置命名空间
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6-rc3
        environment:
          NAMESPACES: "my-namespace my-other-namespace" # 只监听这些命名空间
          ...
        deploy:
          placement:
            constraints:
              - "node.role == worker"
    ...
    ```

    请记住，`NAMESPACES` 环境变量是一个以空格分隔的命名空间列表。

!!! warning "命名空间规范"

    每个命名空间只能有**一个数据库**和**一个调度器**。如果您尝试在同一个命名空间中创建多个数据库或调度器，配置最终会相互冲突。

    调度器不需要 `NAMESPACE` 标签即可正常工作。它只需要正确配置 `DATABASE_URI` 设置，以便它可以访问与自动配置服务相同的数据库。

## Microsoft Azure

<figure markdown>
  ![概述](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Azure 集成</figcaption>
</figure>

!!! info "推荐的虚拟机大小"
    请在选择虚拟机的 SKU 时注意。您必须选择与 Gen2 虚拟机兼容的 SKU，我们建议从 B2s 或 Ds2 系列开始以获得最佳使用效果。

您可以轻松地通过多种方式在您的 Azure 订阅上部署 BunkerWeb：

- Cloud Shell 中的 Azure CLI
- Azure ARM 模板
- 通过 Marketplace 的 Azure 门户

=== "Cloud Shell"

    创建一个资源组。替换值 `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    在资源组的位置创建一个 `Standard_B2s` SKU 的虚拟机。替换值 `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    完整命令。替换值 `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "ARM 模板"

    !!! info "权限要求"
        要部署 ARM 模板，您需要对您正在部署的资源具有写入权限，并有权访问 Microsoft.Resources/deployments 资源类型的所有操作。
        要部署虚拟机，您需要 Microsoft.Compute/virtualMachines/write 和 Microsoft.Resources/deployments/* 权限。what-if 操作具有相同的权限要求。

    部署 ARM 模板：

    [![部署到 Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    登录到 [Azure 门户](https://portal.azure.com){:target="_blank"}。

    从[创建资源菜单](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}获取 BunkerWeb。

    您也可以通过 [Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"}。

您可以通过浏览虚拟机的 `https://your-ip-address/setup` URI 来访问设置向导。
