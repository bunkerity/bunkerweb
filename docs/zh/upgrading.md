# 升级

!!! warning "重建 Web UI 容器时若无持久化 `/data`，2FA 将丢失"
    先 `docker compose down` 再 `up` 会替换 `bw-ui` 容器的文件系统，而用于解密所有已存储 TOTP 密钥的密钥正保存在那里。若未在 `/data` 上挂载卷，管理员绑定会被丢弃，所有用户都必须重新绑定。升级**之前**请确认您的 `bw-ui` 服务已挂载该卷——参见[重建容器后 2FA 会丢失](web-ui.md)。

## 从 1.6.X 升级

### 重大变更 {#breaking-changes}

!!! warning "`REDIS_SSL_VERIFY` 现在默认改为 `yes`"

    启用 `REDIS_SSL` 时，Redis/Valkey 客户端此前会接受**任意**证书：`REDIS_SSL_VERIFY` 文档中记载的默认值是 `yes`，但实际出厂默认值是 `no`，因此 TLS 协商时从未真正验证服务器。代码现已与文档一致。

    只有当以下条件**全部**满足时才会受到影响：`REDIS_SSL: "yes"`、Redis 或 Valkey 服务器提供的是自签名或其他不受信任的证书，并且你从未显式设置过 `REDIS_SSL_VERIFY`。在这种情况下，升级后连接会失败。

    要么信任服务器的 CA，要么显式恢复之前的行为：

    ```yaml
    REDIS_SSL_VERIFY: "no"
    ```

!!! warning "job broker 现在与 WAF 数据存储是独立实例"

    BunkerWeb 将 Redis/Valkey 用于两项互不相关的任务，二者所需配置相互矛盾：

    | 角色 | 设置 | 原因 |
    |------|---------|-----|
    | **Job broker** (`CELERY_BROKER_URL`) | `maxmemory-policy noeviction` | 它持有阻止两个 worker 同时推送配置的正确性租约（correctness lease）。这些键*带有* TTL，因此任何 `volatile-*` 策略都可能在租约生效期间将其淘汰。 |
    | **WAF 数据存储** (`USE_REDIS` / `REDIS_*`) | `maxmemory-policy volatile-lru`（推荐） | 设置内存上限并允许淘汰：丢失临时计数器比拒绝写入的代价更低。这不是强制要求；不设上限的 Redis 不会淘汰键，也可以使用。但数据存储通常这样配置，而任务代理不能如此。 |

    `maxmemory-policy` 是按服务器而非按数据库设置的，因此一个实例无法同时满足两种角色——把两种角色指向同一服务器上不同的数据库编号并不能将它们分开。多容器堆栈运行专用 `bw-jobs-broker`；AIO 镜像在回环端口 `6380` 上管理独立任务代理，Linux 安装器则可配置端口从 `6380` 起选择的 `bunkerweb-broker` 服务。

    **如果你使用安装器升级，这一切都会自动处理。** 它会配置 broker，将 `CELERY_BROKER_URL` 写入 `/etc/bunkerweb/variables.env`，并且不会改动未修改过的发行版自带 Redis（由于未设置 `maxmemory`，它从不淘汰任何数据，因此此前从未出过问题）。

    **如果你使用普通的 `apt`/`dnf` 升级，并且手动设置了 Redis 密码**，那么你会受到影响，后台任务已经在静默失败。worker 和 API 默认使用未认证的 `redis://127.0.0.1:6379/0`，因此设置了密码保护的服务器会返回 `NOAUTH`：`POST /jobs/dispatch` 返回 502，worker 保持 `active` 状态但不消费任何任务。在该状态下不会有证书续期、封禁列表刷新，也不会有备份。可通过以下命令检查：

    ```bash
    journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'
    ```

    容器和 Linux 的进一步诊断见[后台任务始终不运行](troubleshooting.md#background-jobs)。

    **修复认证前，先确认这是专用且不会淘汰键的任务代理。** 如果端口 `6379` 运行的是会淘汰键的 WAF 数据存储，请通过 [Linux 安装器](integrations.md#easy-installation-script) 配置独立任务代理，或自行配置使用 `maxmemory-policy noeviction` 的代理，并使用其实际地址和端口。下方的 `6379` 示例仅适用于专门执行任务的发行版 Redis；给会淘汰键的数据存储添加密码，并不能使它成为安全的任务代理。

    然后在 `/etc/bunkerweb/variables.env` 中为任务代理配置自己的凭据——一次写入即可覆盖两个组件，因为 Worker 和 API 都会先读取该文件，再读取各自的文件：

    ```bash
    CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0
    ```

    ```bash
    systemctl restart bunkerweb-worker bunkerweb-api
    ```

    TLS 通过 `rediss://` scheme 提供支持。**请显式设置 `ssl_cert_reqs`**——裸 `rediss://` URL 会在不验证服务器证书的情况下协商 TLS：

    ```bash
    CELERY_BROKER_URL=rediss://:<password>@broker.example.com:6379/0?ssl_cert_reqs=required
    ```

!!! warning "部分安装未启用 Celery worker"

    `bunkerweb-worker` 执行 scheduler 派发的每一个 job。在安装器推迟服务启动的安装场景中——`--redis`、外部数据库、CrowdSec、自定义 DNS 解析器，以及每种 `--manager` 安装——它从未被启用，因此整个 stack 健康启动却完全不运行任何后台任务。安装器现在会在这些路径上把它和 scheduler 一起启用。升级后请验证：

    ```bash
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    ```

!!! warning "Docker、autoconf 和 Kubernetes 堆栈需要三个新组件"

    1.6 堆栈包含 `bunkerweb` 和 `bw-scheduler`。1.7 还需要 **API**、**Worker** 和**任务代理**：Compose 堆栈中的 `bw-api`、`bw-worker`、`bw-jobs-broker`，或 Kubernetes 中的 `bunkerweb-api`、`bunkerweb-worker`、`bunkerweb-jobs-broker`。Worker 执行以前由调度器进程直接运行的所有任务，任务代理传递派发消息。每个 BunkerWeb 组件都获得 `API_URL`、`API_TOKEN` 和 `CELERY_BROKER_URL`，`bunkerweb` 实例还需要挂载到 `/data` 的 `bw-instance-data` 卷。

    仅修改镜像标签会留下一个显示健康却**完全不运行后台任务**的堆栈：没有证书续期、封禁列表刷新或备份（[诊断方法](troubleshooting.md#background-jobs)）。请使用对应集成的 1.7 参考堆栈重新部署：[Docker](integrations.md#docker)、[Docker autoconf](integrations.md#docker-autoconf)、[Kubernetes](integrations.md#kubernetes) 或 [Swarm](integrations.md#swarm)。各数据库引擎的参考文件位于仓库的 [`misc/integrations`](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/misc/integrations)。

    **All-In-One 镜像不受此影响**：它在单个容器内管理 API、Worker 和专用内嵌 Redis 任务代理。保留 `/data` 并替换容器即可完成升级，无需新增组件。

!!! warning "PostgreSQL：早于 1.6.0 的数据库必须先升级到 1.6.x"

    在 1.6.0 之前创建或最后迁移的 **PostgreSQL** 数据库不能直接升级到 1.7。整个迁移链在一个事务中运行，而升级到 1.6.1 的修订会打开第二个连接，在第一个连接已持有排他锁的表上删除约束。第二个连接等待迁移返回才会释放的锁，迁移又等待第二个连接完成。持锁方等待的是客户端套接字而不是锁，因此 PostgreSQL 的死锁检测器无法发现它。没有超时，也没有错误：调度器始终无法完成启动。

    如果此安装从未运行过 1.6.x，就会受到影响。可读取版本标记：

    ```bash
    psql -d <database> -c 'SELECT version_num FROM alembic_version;'
    ```

    `f85e36780e55` 是 1.6.0 修订，迁移链中在它之前的版本均受影响。先安装 1.6.14，等待调度器启动并完成迁移，然后升级到 1.7。SQLite、MariaDB 和 MySQL 不受影响；仅 PostgreSQL 修订会打开第二个连接。

!!! danger "含空白、`;`、`{` 或 `}` 的 location 值现在会被拒绝，并回退到 `/`"

    `REVERSE_PROXY_URL`、`GRPC_URL` 和 `REDIRECT_FROM` 在 1.6 接受任意值，现在会拒绝可能让值逃出所生成 `location` 块的字符。开头的 `~ `、`~* `、`^~ ` 或 `= ` 仍可用作 NGINX location 修饰符，但其后的这一个空格是整个值中唯一允许的空白字符，尾部空格也不允许；`;`、`{`、`}` 一律不允许。

    被拒绝的值不会让渲染失败。BunkerWeb 记录警告 (`Ignoring variable REVERSE_PROXY_URL_1 : ...`)，设置保留默认值；三者的默认值都是 `/`，因此规则会移到站点根路径，而不是您配置的路径。常见情况是带量词的正则 location，如 `^/v[0-9]{1,3}/`。

    升级前，在 Compose 文件、`variables.env`、容器标签、Kubernetes 注解等设置来源中检查：

    ```bash
    grep -rInE '(REVERSE_PROXY_URL|GRPC_URL|REDIRECT_FROM)[A-Z_0-9]*[:=].*[;{}]' .
    ```

    此命令查找含 `;`、`{`、`}` 的值。含空格的值也会被拒绝，除非空格仅用于分隔开头的 `~`、`~*`、`^~`、`=` 与路径；这些值请人工检查。

    此命令只检查文件。通过 Web UI 或 API 设置的值保存在数据库中，在渲染配置或保存无关设置时不会重新验证，因此升级后继续有效且**不会提示**。后续操作有三种不同表现：

    - **JSON 设置载荷会整体验证。** `POST`/`PATCH /services` 和 `PATCH /global_settings` 检查发送的每个键，无论是否修改；读取后原样回写旧值也会返回 `400` 并指出键名。这些路由使用不带服务前缀的键：`REVERSE_PROXY_URL_1`，不是 `www.example.com_REVERSE_PROXY_URL_1`。`MULTISITE=no` 时三项设置是全局设置，适用 `PATCH /global_settings`。
    - **保存完整配置时，会与数据库比较并跳过未变化的键**：包括 Web UI 服务和全局设置页、autoconf、调度器环境同步、`PUT /global_settings/config`。打开服务页再保存不会发现原有无效值。来自标签或 `variables.env` 的值不同：autoconf 和 Configurator 每次完整读取各自来源，非法值会被丢弃并记录日志，然后回退到默认值，因此上面的文件检查很重要。
    - **UI 实际检查某字段时**（因为您修改了它），不会拒绝整次保存。它将此字段恢复到数据库原值，显示 `Variable <key> is not valid.`，保存其余设置，仍报告保存成功。请查看红色和绿色提示，而不只看操作结果。

    这些行为都不会主动帮您找出旧值。请人工核查 UI 管理服务中的 `REVERSE_PROXY_URL`、`GRPC_URL` 和 `REDIRECT_FROM`。

!!! warning "`GET /bans` 现在从数据库返回结果"

    1.7 将封禁存储在数据库中，重启后仍然保留；控制平面的 `GET /bans` 返回此持久列表。以前返回的各实例当前共享内存中的实际封禁已原样移到 `GET /bans/instances`。1.6 自动化继续调用 `GET /bans` 不会报错，但结果含义已经变化，请明确调整调用端点。

!!! info "`HTTP_PORT` 和 `HTTPS_PORT` 现在可按服务设置"

    两者的上下文从 `global` 改为 `multisite`，因此现在接受 `www.example.com_HTTPS_PORT=9443`，而 1.6 会以 “context of ... isn't multisite” 拒绝。现有配置的渲染不变：全局值仍是每个服务的默认值。服务现在可以声明自己的列表，该列表会**替换**此服务继承的全局列表，而不是追加。

!!! warning "Swarm：`NAMESPACES` 现在也会过滤自定义配置"

    在 1.7 之前，`NAMESPACES` 会过滤 Swarm 控制器的事件路径及其服务发现，但**不会**过滤其配置发现：
    无论属于哪个命名空间，daemon 上的每个 autoconf 都会收集全局的 `docker config` 对象。1.7 现在也
    将该过滤器应用于配置，这本来就是 Docker 集成一直以来的做法。如果您设置了 `NAMESPACES`，而您的
    配置对象没有携带 `bunkerweb.NAMESPACE` 标签，那么升级后这些配置**将不再被应用，且不会报错**——
    携带 allow/deny 块的自定义片段会直接从生成的配置中消失。

    请为每个您希望被应用的配置对象打上标签。Swarm 的配置是不可变的——`docker config` 没有 `update`
    动作——因此每个配置都必须以新名称重新创建，并通过 `docker service update
    --config-rm/--config-add` 重新指向。升级前可用以下命令找出受影响的对象：

    ```bash
    docker config ls -q | xargs -r docker config inspect --format '{{.Spec.Name}} {{.Spec.Labels}}'
    ```

!!! info "Docker Swarm 在 1.7 中重新获得支持"

    Swarm 集成在 1.6 中被标记为已弃用，在 1.7 中重新获得支持。为 1.6 发布的堆栈在 1.7 上**无法**启动：
    它既没有 `bw-api` 也没有 `bw-worker`，导致 `bw-autoconf` 永远等待一个从未启动的 API，也没有任何
    后台任务运行。请从 [1.7 参考堆栈](integrations.md#swarm) 重新部署，而不是编辑旧的堆栈，并注意它
    携带的三项新要求：为拥有卷的服务打上 `bw-state=true` 节点标签、`bunkerweb` 服务使用
    `mode: global`，以及使用 `mode: host` 发布端口。

### 切换旧 AIO 的任务代理 {#aio-broker-upgrade}

本节适用于**现有 1.7 AIO 部署**；1.6 没有 Celery 任务队列。较早的 1.7 镜像从 `REDIS_*` 推导任务代理连接。默认值现在是 `redis://127.0.0.1:6380/0`，连接使用 `noeviction` 的独立 Redis，AOF 持久数据保存在 `/data/broker`。WAF 数据存储继续使用自己的设置和文件。

显式设置的 `CELERY_BROKER_URL` 会被保留。以前用来选择任务代理的 `REDIS_HOST`、`REDIS_PASSWORD` 和 Redis TLS 设置现在仅影响 WAF 数据存储。要继续使用外部任务代理，请显式设置完整 `CELERY_BROKER_URL`，包括凭据和 TLS 验证参数。启用 Worker 时不允许空值。

切换运行中 1.7 部署的任务代理前：

1. 停止直接写入 API 的自动化和其他操作。使用现有[备份静默保持流程](#rolling-back-to-1614) 暂停调度器派发、autoconf 和 UI 写入，等待队列任务、执行中任务和待处理重载确认全部完成。只保持静默，不执行降级步骤；目标版本在这里只是保持操作的标签，不是迁移请求。
2. 将静默保持命令连接到**旧**任务代理和 API。较早 AIO 镜像的新 shell 不继承入口脚本导出的 URL；请向该 shell 提供真实的旧 `CELERY_BROKER_URL` 和 API 凭据。如果 API 没有观察到保持状态，或排空超时，应先解决问题再切换。
3. 在旧容器停止之前始终维持保持状态。用相同 `/data` 卷重新创建容器，采用新默认值或显式外部代理 URL。不会在代理之间复制队列键，也不会删除旧 WAF Redis 数据。
4. 检查容器健康，并在任务页面确认派发的任务完成后再恢复 API 自动化。旧外部代理上的残留保持可通过现有静默保持命令释放，也可以等待其过期。

新任务代理先于 Worker 启动、晚于 Worker 停止。保留 `/data` 可让 AOF 跨容器重启保留；持久化不会转移遗留在旧代理上的任务。

### 升级后

以下变化不会阻止升级，也不需要额外操作才能完成升级，但会影响 1.7 的使用。

!!! info "多站点安装新增保留服务 `default-server`"

    `MULTISITE=yes` 时，处理不匹配任何已配置服务的请求（未知主机名、裸 IP 地址、无人提供服务的 `Host`）的配置块现在成为永久保留服务。它出现在 UI 服务列表和 `GET /services` 中，并标记为 `reserved: true`；不能删除、改名或设为草稿，也不占用 PRO 服务配额。您可以为其配置证书、TLS、响应头和错误页面。参见 [API 参考](api.md#api-surface-capability-map) 和 [Web UI](web-ui.md#the-default-server-entry)。

    `MULTISITE=no` 时不创建此行，默认服务器的渲染与 1.6 相同。

!!! info "实例注册可选"

    实例可兑换有时限的一次性代码，取得自己的控制平面凭据。未注册的实例继续使用全局 `API_TOKEN`，与 1.6 相同；注册后只接受自己的凭据，永不回退。原地降级会销毁存储的凭据。请在回滚前让实例恢复使用共享 `API_TOKEN`，或在回滚后重新注册。参见[实例注册](web-ui.md#instance-enrollment)。如果其他状态仍在而凭据文件丢失，已注册实例会拒绝启动，直到重新注册；详见[已注册实例拒绝启动](troubleshooting.md#lost-instance-credential)。

!!! info "1.7 新功能"

    - 三类访问列表均支持**复合 AND 规则**：`BLACKLIST_RULE_1`、`GREYLIST_RULE_1`、`WHITELIST_RULE_1` 等，只有每项条件都匹配才生效，如 `country:FR AND NOT ua:GoodBot`。
    - **独立 GeoIP 插件**：默认仍使用免费 DB-IP Lite 国家和 ASN 数据库，无需配置。新增 MaxMind 订阅 (`MAXMIND_LICENSE_KEY`、`MAXMIND_ACCOUNT_ID`)、城市库 (`GEOIP_CITY`) 和自定义 `.mmdb` 选项。参见 [GeoIP](features.md#geoip)。
    - **`BACKUP_ROTATION_STRATEGY`** 决定保留哪些备份，而非保留数量。默认 `hanoi` 通过减少近期恢复点来换取更早的恢复点；设为 `fifo` 可恢复 1.6 的选择方式。`BACKUP_ROTATION` 不变。
    - **每个服务支持多个模板**：`USE_TEMPLATE` 是按空格分隔的有序列表，后面的模板覆盖前面的设置。
    - **服务端翻译的 Web UI**，提供语言选择器。参见[翻译](web-ui.md#translations-i18n)。

### 回退到 1.6.14 {#rolling-back-to-1614}

回退并不是升级的逆过程。存在两条路径，BunkerWeb 会告诉您哪一条适用于您的安装，而不是让您自己猜测。

**从备份恢复**在任何情况下都可行，是官方支持的路径。它会将升级*之前*创建的备份还原到一个已清空的
数据库上，因此升级以来写入的一切都会丢失。每种数据库引擎的手动步骤请参见下方的[回滚](#rollback)。

**原地降级**仅针对已验证为无损的版本/引擎组合提供，且只能回退到紧邻的上一个版本。对 1.7.0 而言，
这意味着仅在 **SQLite 和 PostgreSQL** 上可以降级到 1.6.14。在 MariaDB 和 MySQL 上，1.7 的迁移无法
反向重放——它会在中途中止，留下一个既不属于旧版本也不属于新版本的 schema——因此这些安装必须从备份恢复。

按此顺序执行三条命令：

```bash
# 1. 此安装能否回退？只读操作：不创建任何数据库，也不写入任何内容。
bwcli plugin backup preflight 1.6.14

# 2. 让写入方保持静止。会停留在前台，直到您按下 Ctrl-C。
bwcli plugin backup quiesce 1.6.14

# 3. 在第二个 shell 中，趁步骤 2 仍在保持：
bwcli plugin backup downgrade 1.6.14            # 仅报告，不做任何更改
bwcli plugin backup downgrade 1.6.14 --execute  # 请求确认后再执行迁移
```

只有当步骤 2 针对同一版本的保持仍然有效、其自行重新运行的 preflight 结果干净，且兼容性清单将该组合
标记为已测试时，步骤 3 才会执行；否则会被拒绝。它会在迁移前立即创建自己的备份，并在出现任何问题时
将其还原。

开始之前，请停止或用防火墙阻止一切直接写入 API 的行为。保持状态会让 API 向集群*报告*自己为只读，
调度器、autoconf 和界面都依据这一状态行事；但它并不会阻止持有令牌的一方直接对 API 发起的写入。

!!! danger "原地降级会破坏什么"
    每一个集中存储的证书、每一个可附加资源（重定向、上游池、工作流、资源组）、所有请求指标和威胁地图、
    每一个已注册的通行密钥（passkey），以及每一个已存储的实例凭据——已注册的实例之后必须重新针对全局
    `API_TOKEN` 完成注册。按用户的界面偏好设置会保留下来，但会失去原本的含义：1.6.14 会将它们全部当作
    按表格的列布局来读取。封禁是唯一的轻度损失：`sync-bans` 任务会从各实例重新学习这些封禁，只会丢失
    其剩余时长。

    Preflight 会统计您的安装实际持有的内容，只要还存在任何不可替代的内容，就会拒绝执行原地降级——因此
    您得到的答案是关于您自己的数据，而不是关于该版本本身的抽象结论。

**数据库之外。** Job 缓存和 PRO 插件会在下一次运行时重新构建。自定义配置、`www` 内容、Let's
Encrypt 状态以及备份归档在两个版本之间保持不变。需要 1.7 版 API 的外部插件在 1.6.14 上无法使用，
必须移除或一并降级。

### 步骤

=== "Docker"

    === "使用安装脚本轻松升级"

        创建 Docker 安装的同一个脚本也可以升级由它生成的堆栈。请在包含
        `docker-compose.yml` 和 `.env` 的目录中运行它（或使用 `--compose-dir`
        指定该目录）：

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

        # 下载脚本及其校验和
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # 验证校验和
        sha256sum -c install-bunkerweb.sh.sha256

        # 如果校验成功，运行脚本
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh --docker --compose-dir /path/to/your/stack
        ```

        !!! danger "安全提示"
            **运行安装脚本前，请务必验证其完整性。**

            下载校验和文件，并使用 `sha256sum` 等工具确认脚本未被更改或篡改。

            如果校验失败，**请勿执行该脚本**——它可能不安全。

        !!! warning "仅适用于本脚本创建的堆栈"
            升级流程通过 `.env` 文件中的 `generated by install-bunkerweb.sh`
            标头来识别堆栈。手写的 `docker-compose.yml`、All-In-One 容器，
            以及 Swarm/Kubernetes 部署都不会由脚本升级——请对这些情况使用
            **手动**选项卡。

        * **工作原理**：

            1. 检测
                * 从 `.env` 中读回安装类型（full、manager、worker、scheduler、ui、api），因此您无需重新声明拓扑结构。
                * 从 `.env` 中恢复密钥、主机端口、worker 列表和 Compose 项目名称，因此升级不会轮换数据库密码、使已保存的 2FA 密钥失效，也不会改动您已发布的端口。
                * 从容器中读取实际运行的版本，而不是信任镜像标签，因此浮动标签（`latest`、`testing`）和上一次中断的升级都能被正确识别。
            2. 升级决策
                * 已在运行相同版本：打印堆栈状态并退出。
                * 目标版本更旧：**拒绝执行**。安装脚本本身没有降级自动化功能，针对已迁移过数据库的旧版本包启动调度器会失败并陷入重启循环。请参见[回退到 1.6.14](#rolling-back-to-1614)先恢复数据库，然后再用旧版本重新运行安装脚本。
                * 其他情况：请求确认（使用 `-y` 时直接继续）。
            3. 升级前备份
                * 在调度器容器内运行 `bwcli plugin backup save`，并将归档文件复制到主机。
                * 目标位置：`--backup-dir`，或生成的路径，例如 `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`。
                * 备份失败时中止升级，除非您传入 `--no-auto-backup`。
                * 对没有自身数据库的 `worker`、`ui` 和 `api` 堆栈会跳过此步骤。
            4. 文件更新
                * `.env` 会以新的镜像标签重写；您手动添加的任何条目都会被保留。
                * 仅当 `docker-compose.yml` 仍与脚本生成的内容一致时才会重新生成，因此本地修改得以保留。传入 `--overwrite-compose` 可强制重新生成。两种情况下都会保留一份 `.bak.<时间戳>` 副本。
            5. 应用与验证
                * 先执行 `docker compose pull`，再执行 `docker compose up -d`——只有镜像发生变化的容器会被重建，因此停机时间短于完整的 `down`/`up` 流程。
                * 如果拉取失败，则不会重建任何容器，`.env` 中会恢复为先前的标签，正在运行的堆栈保持不变。
                * 随后脚本会重新从容器读取版本，并检查调度器是否进入重启循环——数据库迁移失败正是以这种方式表现出来的。

        * **常用选项**：

            | 选项                    | 作用                                             |
            | ----------------------- | ------------------------------------------------ |
            | `--compose-dir PATH`    | 存放堆栈的目录（默认：当前目录）                 |
            | `-v, --version VERSION` | 目标版本；镜像标签由它推导得出                   |
            | `--image-tag TAG`       | 直接指定目标镜像标签，而不是推导                 |
            | `--backup-dir PATH`     | 升级前备份的存放位置                             |
            | `--no-auto-backup`      | 跳过自动备份（手动备份将由您负责）               |
            | `--overwrite-compose`   | 即使 `docker-compose.yml` 曾被本地修改也重新生成 |
            | `--force-type-change`   | 允许堆栈更改拓扑结构（具有破坏性）               |
            | `--no-pull`             | 重建堆栈前不拉取镜像                             |
            | `-y, --yes`             | 无人值守运行；不带该选项的管道调用会以错误退出   |

    === "手动"

        1.  **备份数据库**：

            -   在进行数据库升级之前，请确保对数据库的当前状态进行完整备份。
            -   使用适当的工具备份整个数据库，包括数据、模式和配置。

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        2.  **升级 BunkerWeb**：
            -   将 BunkerWeb 升级到最新版本。
                1. **更新 Docker Compose 文件**：从 1.6 升级不能只更新标签。还需添加 `bw-api`、`bw-worker`、`bw-jobs-broker` 服务，在组件上配置 `API_URL`、`API_TOKEN` 和 `CELERY_BROKER_URL`，并为 `bunkerweb` 添加 `bw-instance-data` 卷。参见上面的[重大变更](#breaking-changes)。请基于 [Docker](integrations.md#docker) 或 [Docker autoconf](integrations.md#docker-autoconf) 的 1.7 参考堆栈重建 `docker-compose.yml`，迁移自己的设置、卷和发布端口。

                2.  **重启容器**：重启容器以应用更改。
                    ```bash
                    docker compose down
                    docker compose up -d
                    ```

        3.  **检查日志**：检查调度器服务的日志以确保迁移成功。

            ```bash
            docker compose logs <scheduler_container>
            ```

        4.  **验证数据库**：通过检查新数据库容器中的数据和配置来验证数据库升级是否成功。

=== "All-In-One (AIO)"

    [All-In-One 镜像](integrations.md#all-in-one-aio-image)默认在名为 `bunkerweb-aio` 的**单个容器**中打包 BunkerWeb、Scheduler、Web UI，并可选打包 API、Redis 和 CrowdSec。所有持久状态——SQLite 数据库、缓存、自定义配置、插件、备份以及 Redis/CrowdSec 数据——都位于 `/data` 卷中，因此升级就是在保留该卷的同时替换容器。

    1.  **前提条件**：

        -   记录当前运行的镜像标签以及 `/data` 卷（或 bind mount）的名称，以便升级后复用完全相同的卷。

        !!! warning "保留 `/data` 卷"
            **升级期间绝不要删除 `/data` 卷。** 它保存数据库、内置 Redis 和 CrowdSec 状态、自定义配置以及备份。替换容器是安全的；删除该卷则不安全。

        !!! tip "外部数据库后端"
            如果 AIO 使用外部数据库（`DATABASE_URI` 指向 MySQL/MariaDB/PostgreSQL），则不会使用 `/data` 下的 SQLite 文件——也请使用常规工具备份该外部数据库。

    2.  **备份数据库**：

        -   在进行数据库升级之前，请确保对数据库的当前状态进行完整备份。Scheduler 在 `bunkerweb-aio` 容器内运行，因此备份命令直接在该容器中执行。

        ```bash
        docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory bunkerweb-aio bwcli plugin backup save
        ```

        ```bash
        docker cp bunkerweb-aio:/path/to/backup/directory /path/to/backup/directory
        ```

    3.  **升级 BunkerWeb**：

        === "docker run"

            3.  **停止并删除当前容器**（保留 `/data` 卷）：
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4.  **拉取新镜像**：
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

            5.  **用相同选项重新创建容器**，复用与之前相同的 `/data` 卷、端口和环境变量：
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

        === "Docker Compose"

            6.  **更新 Docker Compose 文件**：更新 Docker Compose 文件以使用新版 All-In-One 镜像。
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:1.7.0-beta
                        ...
                ```

            7.  **重启容器**：重启容器以应用更改。`/data` 卷会自动重新挂载。
                ```bash
                docker compose down
                docker compose up -d
                ```

    4.  **检查日志**：检查容器日志，确保内置 Scheduler 执行的迁移成功。

        ```bash
        docker logs bunkerweb-aio
        ```

    5.  **验证升级**：
        -   确认容器正在运行且健康：
            ```bash
            docker ps --filter name=bunkerweb-aio
            ```
            启动检查通过后，`STATUS` 列应显示 `(healthy)`。
        -   确认运行版本：
            ```bash
            docker exec bunkerweb-aio cat /usr/share/bunkerweb/VERSION
            ```
            也可以在 Web UI 的 *Support* 中检查版本。
        -   在 Web UI 中确认服务、设置和自定义配置保持完整，并且站点仍通过 HTTP/HTTPS 提供服务。

=== "Linux"

    === "使用安装脚本轻松升级"

        *   **快速开始**：

            要开始使用，请下载安装脚本及其校验和，然后在运行前验证脚本的完整性。

            ```bash
            LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

            # Download the script and its checksum
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

            # Verify the checksum
            sha256sum -c install-bunkerweb.sh.sha256

            # 如果检查成功，则运行脚本
            chmod +x install-bunkerweb.sh
            sudo ./install-bunkerweb.sh
            ```

            !!! danger "安全提示"
                **在运行安装脚本之前，请务必验证其完整性。**

                下载校验和文件，并使用像 `sha256sum` 这样的工具来确认脚本没有被更改或篡改。

                如果校验和验证失败，**请不要执行该脚本**——它可能不安全。

        !!! tip "交互式升级界面"
            升级流程使用与全新安装相同的 TUI：通过 [gum](https://github.com/charmbracelet/gum) 提供的内联提示；若无法获取 gum，则回退到 `whiptail` 对话框，最终退化为纯文本提示。`gum` 二进制从官方 [GitHub 发布页](https://github.com/charmbracelet/gum/releases) 下载（SHA256 已固定，若已安装 cosign 则进行 cosign 校验），从临时目录运行，并在脚本退出时删除该目录 —— 不会安装任何系统包，也不会添加 apt/dnf 源。使用 `--no-tui`（或设置 `BW_INSTALL_TUI=no`）跳过所有 TUI 层级；使用 `--tui` 在无可用 TUI 时中止。对于完全无人值守的升级，请使用 `-y` / `--yes` 配合相应标志 —— 通过管道调用（`curl … | bash`）会以清晰的错误退出，而不会静默接受每个默认值。**离线（air-gapped）升级**：组合 `--no-tui --yes`，TUI 层不会发起任何网络调用。

        *   **工作原理**：

            用于全新安装的多功能安装脚本也可以执行原地升级。当它检测到现有安装和不同的目标版本时，它会切换到升级模式并应用以下工作流程：

            1.  检测与验证
                *   检测操作系统/版本并确认支持矩阵。
                *   从 `/usr/share/bunkerweb/VERSION` 读取当前安装的 BunkerWeb 版本。
            2.  升级场景决策
                *   如果请求的版本与已安装的版本相同，则中止（除非您明确重新运行以获取状态）。
                *   如果版本不同，则标记为升级。
            3.  （可选）自动升级前备份
                *   如果 `bwcli` 和调度器可用且启用了自动备份，它会通过内置的备份插件创建一个备份。
                *   目的地：您使用 `--backup-dir` 提供的目录或生成的路径，如 `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`。
                *   您可以使用 `--no-auto-backup` 禁用此功能（然后手动备份就成了您的责任）。
            4.  服务静默
                *   停止 `bunkerweb`、`bunkerweb-ui` 和 `bunkerweb-scheduler` 以确保一致的升级（与手动过程建议相符）。
            5.  移除软件包锁定
                *   临时移除 `bunkerweb` 和 `nginx` 上的 `apt-mark hold` / `dnf versionlock`，以便可以安装目标版本。
            6.  执行升级
                *   仅安装新的 BunkerWeb 软件包版本（在升级模式下，除非 NGINX 缺失，否则不会重新安装——这避免了触及正确固定的 NGINX）。
                *   重新应用锁定/版本锁定以冻结升级后的版本。
            7.  完成与状态
                *   显示核心服务的 systemd 状态和后续步骤。
                *   保留您的配置和数据库不变——只更新应用程序代码和受管理的文件。

            关键行为/说明：

            *   该脚本不会修改您的 `/etc/bunkerweb/variables.env` 或数据库内容。
            *   如果自动备份失败（或被禁用），您仍然可以使用下面的回滚部分进行手动恢复。
            *   升级模式有意避免在已存在的受支持固定版本之外重新安装或降级 NGINX。
            *   用于故障排除的日志保留在 `/var/log/bunkerweb/` 中。

        *   **基于模式的行为**：

            - 升级期间将重复使用相同的安装类型逻辑：manager 模式保持设置向导禁用、将 API 绑定到 `0.0.0.0` 并仍然需要白名单 IP（无人值守运行时请通过 `--manager-ip` 传入），而 worker 模式继续强制要求提供 manager IP 列表。
            - Manager 升级可以选择启动或跳过 Web UI 服务，汇总信息会明确显示 API 服务的状态，以便通过 `--api` / `--no-api` 控制它。
            - CrowdSec 选项仍仅适用于全栈升级，脚本会在修改软件包之前持续验证操作系统和 CPU 架构，对不受支持的组合仍需使用 `--force`。

            回滚摘要：

            *   使用生成的备份目录（或您的手动备份）+ 回滚部分中的步骤来恢复数据库，然后重新安装以前的镜像/软件包版本并重新锁定软件包。

        *   **命令行选项**：

            您可以使用与安装相同的标志来驱动无人值守升级。与升级最相关的选项：

            | 选项                    | 目的                                                                  |
            | ----------------------- | --------------------------------------------------------------------- |
            | `-v, --version <X.Y.Z>` | 要升级到的目标 BunkerWeb 版本。                                       |
            | `-y, --yes`             | 非交互式（假定升级确认并启用自动备份，除非使用 `--no-auto-backup`）。 |
            | `--tui`                 | 强制使用 TUI（gum 或 whiptail）。若两者都无法安装则中止。             |
            | `--no-tui`              | 跳过所有 TUI 层级并使用纯文本提示。等同于 `BW_INSTALL_TUI=no`。       |
            | `--backup-dir <PATH>`   | 自动升级前备份的目的地。如果不存在则创建。                            |
            | `--no-auto-backup`      | 跳过自动备份（不推荐）。您必须有手动备份。                            |
            | `-q, --quiet`           | 抑制输出（与日志记录/监控结合使用）。                                 |
            | `-f, --force`           | 在不受支持的操作系统版本上继续。                                      |
            | `--dry-run`             | 显示检测到的环境、预期的操作，然后退出而不做任何更改。                |

            示例：

            ```bash
            # 交互式升级到 1.7.0~beta（会提示备份）
            sudo ./install-bunkerweb.sh --version 1.7.0~beta

            # 使用自动备份到自定义目录的非交互式升级
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --backup-dir /var/backups/bw-2025-01 -y

            # 静默无人值守升级（抑制日志）– 依赖默认的自动备份
            sudo ./install-bunkerweb.sh -v 1.7.0~beta -y -q

            # 执行一次空运行（计划）而不应用更改
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --dry-run

            # 跳过自动备份进行升级（不推荐）
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --no-auto-backup -y
            ```

            !!! warning "跳过备份"
                使用 `--no-auto-backup` 而没有经过验证的手动备份，可能会在升级遇到问题时导致不可逆转的数据丢失。请始终保留至少一个最近的、经过测试的备份。

    === "手动"

        1.  **备份数据库**：

            -   在进行数据库升级之前，请确保对数据库的当前状态进行完整备份。
            -   使用适当的工具备份整个数据库，包括数据、模式和配置。

            ??? warning "给红帽企业 Linux (RHEL) 8.10 用户的信息"
                如果您正在使用 **RHEL 8.10** 并计划使用**外部数据库**，您需要安装 `mysql-community-client` 包以确保 `mysqldump` 命令可用。您可以通过执行以下命令来安装该包：

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

                    4.  **安装 PostgreSQL 仓库配置包**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5.  **安装 PostgreSQL 客户端**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

        1.  **升级 BunkerWeb**：
            -   将 BunkerWeb 升级到最新版本。

                1.  **停止服务**：
                    ```bash
                    sudo systemctl stop bunkerweb
                    sudo systemctl stop bunkerweb-ui
                    sudo systemctl stop bunkerweb-scheduler
                    sudo systemctl stop bunkerweb-api
                    sudo systemctl stop bunkerweb-worker
                    ```

                2.  **更新 BunkerWeb**：

                    === "Debian/Ubuntu"

                        首先，如果您之前锁定了 BunkerWeb 软件包，请解锁它：

                        您可以使用 `apt-mark showhold` 打印锁定的软件包列表

                        ```shell
                        sudo apt-mark unhold bunkerweb nginx
                        ```

                        然后，您可以更新 BunkerWeb 软件包：

                        ```shell
                        sudo apt update && \
                        sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
                        ```

                        为了防止在执行 `apt upgrade` 时升级 BunkerWeb 软件包，您可以使用以下命令：

                        ```shell
                        sudo apt-mark hold bunkerweb nginx
                        ```

                        更多详细信息请参阅[Linux 集成页面](integrations.md#__tabbed_1_1)。

                    === "Fedora/RedHat"

                        首先，如果您之前锁定了 BunkerWeb 软件包，请解锁它：

                        您可以使用 `dnf versionlock list` 打印锁定的软件包列表

                        ```shell
                        sudo dnf versionlock delete package bunkerweb && \
                        sudo dnf versionlock delete package nginx
                        ```

                        然后，您可以更新 BunkerWeb 软件包：

                        ```shell
                        sudo dnf makecache && \
                        sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
                        ```

                        为了防止在执行 `dnf upgrade` 时升级 BunkerWeb 软件包，您可以使用以下命令：

                        ```shell
                        sudo dnf versionlock add bunkerweb && \
                        sudo dnf versionlock add nginx
                        ```

                        更多详细信息请参阅[Linux 集成页面](integrations.md#__tabbed_1_3)。

                3.  **启动服务**：
                        ```bash
                        sudo systemctl start bunkerweb
                        sudo systemctl start bunkerweb-api
                        sudo systemctl start bunkerweb-worker
                        sudo systemctl start bunkerweb-scheduler
                        sudo systemctl start bunkerweb-ui
                        ```
                        或者重启系统：
                        ```bash
                        sudo reboot
                        ```


        3.  **检查日志**：检查调度器服务的日志以确保迁移成功。

            ```bash
            journalctl -u bunkerweb --no-pager
            ```

        4.  **验证数据库**：通过检查新数据库容器中的数据和配置来验证数据库升级是否成功。
### 回滚 {#rollback}

!!! failure "如果出现问题"

    如果您在升级过程中遇到任何问题，您可以通过恢复在[步骤 1](#__tabbed_1_1)中创建的备份来回滚到数据库的先前版本。

    获取支持和更多信息：

    -   [订购专业支持](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    -   [在 GitHub 上创建问题](https://github.com/bunkerity/bunkerweb/issues)
    -   [加入 BunkerWeb Discord 服务器](https://discord.bunkerity.com)

=== "Docker"

    1.  **如果备份是 zip 文件，请先解压**。

        首先解压备份 zip 文件：

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2.  **恢复备份**。

        === "SQLite"

            1.  **删除现有的数据库文件。**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2.  **恢复备份。**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3.  **修复权限。**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4.  **停止堆栈。**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1.  **恢复备份。**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2.  **停止堆栈。**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1.  **删除现有的数据库。**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2.  **重新创建数据库。**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3.  **恢复备份。**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4.  **停止堆栈。**

                ```bash
                docker compose down
                ```

    3.  **降级 BunkerWeb**。

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4.  **启动容器**。

        ```bash
        docker compose up -d
        ```

=== "All-In-One (AIO)"

    Scheduler 在 `bunkerweb-aio` 容器内运行，因此恢复命令直接在其中执行。整个过程中都会保留 `/data` 卷（数据库、配置、插件、备份）——只回滚容器镜像。

    !!! tip "外部数据库后端"
        如果 AIO 使用外部数据库（`DATABASE_URI` 指向 MySQL/MariaDB/PostgreSQL），则不会使用 `/data` 下的 SQLite 文件。请使用常规工具恢复该外部数据库，或使用 **Docker** 标签页中指向数据库主机的 MySQL/MariaDB/PostgreSQL 命令，然后跳过下面的 SQLite 步骤。

    1.  **如果备份是 zip 文件，请先解压**。

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2.  **恢复备份**（内置 SQLite）：

        1.  **删除现有数据库文件。**

            ```bash
            docker exec -u 0 -i bunkerweb-aio rm -f /var/lib/bunkerweb/db.sqlite3
            ```

        2.  **恢复备份。**

            ```bash
            docker exec -i bunkerweb-aio sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            ```

        3.  **修正权限。**

            ```bash
            docker exec -u 0 -i bunkerweb-aio chown root:nginx /var/lib/bunkerweb/db.sqlite3
            docker exec -u 0 -i bunkerweb-aio chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

    3.  **回滚镜像**，复用同一个 `/data` 卷：

        === "docker run"

            3.  **停止并删除当前容器**（保留 `/data` 卷）：
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4.  **拉取旧镜像**：
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:<old_version>
                ```

            5.  **用与之前相同的选项、端口和 `/data` 卷重新创建容器**：
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:<old_version>
                ```

        === "Docker Compose"

            6.  **更新 Docker Compose 文件**以使用旧版 All-In-One 镜像：
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:<old_version>
                        ...
                ```

            7.  **重启容器**。`/data` 卷会自动重新挂载：
                ```bash
                docker compose down
                docker compose up -d
                ```

=== "Linux"

    4.  **如果备份是 zip 文件，请先解压**。

        首先解压备份 zip 文件：

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5.  **停止服务**。

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
        ```

    6.  **恢复备份**。

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1.  **删除现有的数据库。**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2.  **重新创建数据库。**

                ```bash
                createdb -U <username> <database_name>
                ```

            3.  **恢复备份。**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7.  **启动服务**。

        ```bash
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
        ```

    8.  **降级 BunkerWeb**。
        -   按照[Linux 集成页面](integrations.md#linux)中升级 BunkerWeb 的相同步骤，将 BunkerWeb 降级到以前的版本。

## 从 1.5.X 升级

### 有什么变化？

#### 调度器

与 1.5.X 版本不同，调度器服务**不再使用*docker 套接字代理*来获取 BunkerWeb 的实例**。相反，它使用了新的 `BUNKERWEB_INSTANCES` 环境变量。

!!! info "关于 `BUNKERWEB_INSTANCES` 环境变量"

    这个新变量是一个以空格分隔的 BunkerWeb 实例列表，格式如下：`http://bunkerweb:5000 bunkerweb1:5000 bunkerweb2:5000 ...`。然后调度器将使用此列表来获取实例的配置并将配置发送给它们。

    *   `http://` 前缀是可选的。
    *   端口是可选的，默认为 `API_HTTP_PORT` 环境变量的值。
    *   `BUNKERWEB_INSTANCES` 环境变量的默认值是 `127.0.0.1`。

换句话说，新系统是完全不可知和通用的：调度器负责管理一个 BunkerWeb 实例列表，并且不需要关心环境。

!!! tip "Autoconf/Kubernetes/Swarm 集成"

    如果您正在使用 `Autoconf`、`Kubernetes` 或 `Swarm` 集成，您可以将 `BUNKERWEB_INSTANCES` 环境变量设置为空字符串（这样它就不会尝试将配置发送到默认的 `127.0.0.1`）。

    **实例将由控制器自动获取**。您还可以向列表中添加自定义实例，这些实例可能不会被控制器选中。

自 `1.6` 版本起，调度器还拥有一个新的[内置健康检查系统](concepts.md)，它将检查实例的健康状况。如果一个实例变得不健康，调度器将停止向其发送配置。如果该实例恢复健康，调度器将再次开始向其发送配置。

#### BunkerWeb 容器

另一个重要的变化是，以前在 BunkerWeb 容器上声明的**设置**现在在调度器上声明。这意味着您必须将您的设置从 BunkerWeb 容器移动到调度器容器。

虽然设置现在在调度器容器上声明，但**您仍然需要在 BunkerWeb 容器上声明与 API 相关的强制性设置**，例如 `API_WHITELIST_IP` 设置，它用于将调度器的 IP 地址列入白名单，以便它可以将配置发送到实例。如果您使用 `API_TOKEN`，您还必须在 BunkerWeb 容器上设置它（并在调度器上镜像它）以允许经过身份验证的 API 调用。

!!! warning "BunkerWeb 的容器设置"

    您在 BunkerWeb 容器上声明的每个与 API 相关的设置**都必须在调度器容器上镜像**，以便它能继续工作，因为配置将被调度器生成的配置覆盖。

#### 默认值和新设置

我们尽力不更改默认值，但我们添加了许多其他设置。强烈建议阅读文档的[安全调整](advanced.md#security-tuning)和[设置](features.md)部分。

#### 模板

我们添加了一个名为**模板**的新功能。模板提供了一种结构化和标准化的方法来定义设置和自定义配置，有关更多信息，请查看[概念/模板](concepts.md#templates)部分。

#### Autoconf 命名空间

我们向自动配置集成添加了**命名空间**功能。命名空间允许您对实例进行分组，并仅对它们应用设置。根据您的集成，查看以下部分以获取更多信息：

-   [Autoconf/namespaces](integrations.md#namespaces)
-   [Kubernetes/namespaces](integrations.md#namespaces_1)
-   [Swarm/namespaces](integrations.md#namespaces_2)

### 步骤

1.  **备份数据库**：
    -   在进行数据库升级之前，请确保对数据库的当前状态进行完整备份。
    -   使用适当的工具备份整个数据库，包括数据、模式和配置。

    === "1.5.7 及更高版本"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        === "Linux"

            ??? warning "给红帽企业 Linux (RHEL) 8.10 用户的信息"
                如果您正在使用 **RHEL 8.10** 并计划使用**外部数据库**，您需要安装 `mysql-community-client` 包以确保 `mysqldump` 命令可用。您可以通过执行以下命令来安装该包：

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

                    4.  **安装 PostgreSQL 仓库配置包**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5.  **安装 PostgreSQL 客户端**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

    === "1.5.6 及更早版本"

        === "SQLite"

            === "Docker"

                我们首先需要在容器中安装 `sqlite` 包。

                ```bash
                docker exec -u 0 -it <scheduler_container> apk add sqlite
                ```

                然后，备份数据库。

                ```bash
                docker exec -it <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

        === "MariaDB"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "MySQL"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it -e PGPASSWORD=<database_password> <database_container> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                PGPASSWORD=<database_password> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

2.  **升级 BunkerWeb**：
    -   将 BunkerWeb 升级到最新版本。

        === "Docker"

            1.  **更新 Docker Compose 文件**：更新 Docker Compose 文件以使用新版本的 BunkerWeb 镜像。
                ```yaml
                services:
                    bunkerweb:
                        image: bunkerity/bunkerweb:1.7.0-beta
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.7.0-beta
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.7.0-beta
                        ...
                ```

            2.  **重启容器**：重启容器以应用更改。
                ```bash
                docker compose down
                docker compose up -d
                ```

        === "Linux"

            3.  **停止服务**：
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                sudo systemctl stop bunkerweb-api
                sudo systemctl stop bunkerweb-worker
                ```

            4.  **更新 BunkerWeb**：

                === "Debian/Ubuntu"

                    首先，如果您之前锁定了 BunkerWeb 软件包，请解锁它：

                    您可以使用 `apt-mark showhold` 打印锁定的软件包列表

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    然后，您可以更新 BunkerWeb 软件包：

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
                    ```

                    为了防止在执行 `apt upgrade` 时升级 BunkerWeb 软件包，您可以使用以下命令：

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    更多详细信息请参阅[Linux 集成页面](integrations.md#__tabbed_1_1)。

                === "Fedora/RedHat"

                    首先，如果您之前锁定了 BunkerWeb 软件包，请解锁它：

                    您可以使用 `dnf versionlock list` 打印锁定的软件包列表

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    然后，您可以更新 BunkerWeb 软件包：

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
                    ```

                    为了防止在执行 `dnf upgrade` 时升级 BunkerWeb 软件包，您可以使用以下命令：

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    更多详细信息请参阅[Linux 集成页面](integrations.md#__tabbed_1_3)。

            5.  **启动服务**：
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-api
                    sudo systemctl start bunkerweb-worker
                    sudo systemctl start bunkerweb-scheduler
                    sudo systemctl start bunkerweb-ui
                    ```
                    或者重启系统：
                    ```bash
                    sudo reboot
                    ```


3.  **检查日志**：检查调度器服务的日志以确保迁移成功。

    === "Docker"

        ```bash
        docker compose logs <scheduler_container>
        ```

    === "Linux"

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

4.  **验证数据库**：通过检查新数据库容器中的数据和配置来验证数据库升级是否成功。

### 回滚

!!! failure "如果出现问题"

    如果您在升级过程中遇到任何问题，您可以通过恢复在[步骤 1](#__tabbed_1_1)中创建的备份来回滚到数据库的先前版本。

    获取支持和更多信息：

    -   [订购专业支持](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    -   [在 GitHub 上创建问题](https://github.com/bunkerity/bunkerweb/issues)
    -   [加入 BunkerWeb Discord 服务器](https://discord.bunkerity.com)

=== "Docker"

    1.  **如果备份是 zip 文件，请先解压**。

        首先解压备份 zip 文件：

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2.  **恢复备份**。

        === "SQLite"

            1.  **删除现有的数据库文件。**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2.  **恢复备份。**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3.  **修复权限。**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4.  **停止堆栈。**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1.  **恢复备份。**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2.  **停止堆栈。**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1.  **删除现有的数据库。**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2.  **重新创建数据库。**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3.  **恢复备份。**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4.  **停止堆栈。**

                ```bash
                docker compose down
                ```

    3.  **降级 BunkerWeb**。

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4.  **启动容器**。

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4.  **如果备份是 zip 文件，请先解压**。

        首先解压备份 zip 文件：

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5.  **停止服务**。

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
        ```

    6.  **恢复备份**。

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1.  **删除现有的数据库。**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2.  **重新创建数据库。**

                ```bash
                createdb -U <username> <database_name>
                ```

            3.  **恢复备份。**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7.  **启动服务**。

        ```bash
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
        ```

    8.  **降级 BunkerWeb**。
        -   按照[Linux 集成页面](integrations.md#linux)中升级 BunkerWeb 的相同步骤，将 BunkerWeb 降级到以前的版本。
