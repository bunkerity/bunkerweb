# 故障排除

!!! info "BunkerWeb 面板"
    如果您无法解决您的问题，您可以通过我们的面板[直接联系我们](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc)。这里集中了与 BunkerWeb 解决方案相关的所有请求。

## 日志

在进行故障排除时，日志是您最好的朋友。我们尽力提供用户友好的日志，以帮助您了解正在发生的事情。

请注意，您可以将 `LOG_LEVEL` 设置为 `info`（默认值为 `notice`），以增加 BunkerWeb 的详细程度。

根据您的集成方式，以下是如何访问日志的方法：

=== "Docker"

    !!! tip "列出容器"
        要列出正在运行的容器，您可以使用以下命令：
        ```shell
        docker ps
        ```

    您可以使用 `docker logs` 命令（将 `bunkerweb` 替换为您的容器名称）：
    ```shell
    docker logs bunkerweb
    ```

    这是 docker-compose 的等效命令（将 `bunkerweb` 替换为 docker-compose.yml 文件中声明的服务名称）：
    ```shell
    docker-compose logs bunkerweb
    ```

=== "Docker autoconf"

    !!! tip "列出容器"
        要列出正在运行的容器，您可以使用以下命令：
        ```shell
        docker ps
        ```

    您可以使用 `docker logs` 命令（将 `bunkerweb` 和 `bw-autoconf` 替换为您的容器名称）：
    ```shell
    docker logs bunkerweb
    docker logs bw-autoconf
    ```

    这是 docker-compose 的等效命令（将 `bunkerweb` 和 `bw-autoconf` 替换为 docker-compose.yml 文件中声明的服务名称）：
    ```shell
    docker-compose logs bunkerweb
    docker-compose logs bw-autoconf
    ```

=== "All-in-one"

    !!! tip "容器名称"
        一体化镜像的默认容器名称是 `bunkerweb-aio`。如果您使用了不同的名称，请相应地调整命令。

    您可以使用 `docker logs` 命令：
    ```shell
    docker logs bunkerweb-aio
    ```

=== "Swarm"

    !!! tip "列出服务"
        要列出服务，您可以使用以下命令：
        ```shell
        docker service ls
        ```

    您可以使用 `docker service logs` 命令（将 `bunkerweb` 和 `bw-autoconf` 替换为您的服务名称）：
    ```shell
    docker service logs bunkerweb
    docker service logs bw-autoconf
    ```

=== "Kubernetes"

    !!! tip "列出 Pod"
        要列出 Pod，您可以使用以下命令：
        ```shell
        kubectl get pods
        ```

    您可以使用 `kubectl logs` 命令（将 `bunkerweb` 和 `bunkerweb-controler` 替换为您的 Pod 名称）：
    ```shell
    kubectl logs bunkerweb
    kubectl logs bunkerweb-controler
    ```

=== "Linux"

    对于与 BunkerWeb 服务相关的错误（例如，无法启动），您可以使用 `journalctl`：
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    通用日志位于 `/var/log/bunkerweb` 目录中：
    ```shell
    cat /var/log/bunkerweb/error.log
    cat /var/log/bunkerweb/access.log
    ```

## 权限

不要忘记，出于明显的安全原因，BunkerWeb 是以非特权用户身份运行的。请仔细检查 BunkerWeb 使用的文件和文件夹的权限，特别是如果您使用自定义配置（更多信息请参见[此处](advanced.md#custom-configurations)）。您需要为文件设置至少 **_RW_** 权限，为文件夹设置 **_RWX_** 权限。

## IP 解封

您可以手动解封一个 IP，这在进行测试时很有用，这样您就可以联系 BunkerWeb 的内部 API（将 `1.2.3.4` 替换为要解封的 IP 地址）：

=== "Docker / Docker Autoconf"

    您可以使用 `docker exec` 命令（将 `bw-scheduler` 替换为您的容器名称）：
    ```shell
    docker exec bw-scheduler bwcli unban 1.2.3.4
    ```

    这是 docker-compose 的等效命令（将 `bw-scheduler` 替换为 docker-compose.yml 文件中声明的服务名称）：
    ```shell
    docker-compose exec bw-scheduler bwcli unban 1.2.3.4
    ```

=== "All-in-one"

    !!! tip "容器名称"
        一体化镜像的默认容器名称是 `bunkerweb-aio`。如果您使用了不同的名称，请相应地调整命令。

    您可以使用 `docker exec` 命令：
    ```shell
    docker exec bunkerweb-aio bwcli unban 1.2.3.4
    ```

=== "Swarm"

    您可以使用 `docker exec` 命令（将 `bw-scheduler` 替换为您的服务名称）：
    ```shell
    docker exec $(docker ps -q -f name=bw-scheduler) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    您可以使用 `kubectl exec` 命令（将 `bunkerweb-scheduler` 替换为您的 Pod 名称）：
    ```shell
    kubectl exec bunkerweb-scheduler bwcli unban 1.2.3.4
    ```

=== "Linux"

    您可以使用 `bwcli` 命令（以 root 身份）：
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

## 误报

### 仅检测模式

为了进行调试/测试，您可以将 BunkerWeb 设置为[仅检测模式](features.md#security-modes)，这样它就不会阻止请求，而是像一个经典的反向代理一样工作。

### ModSecurity

BunkerWeb 中 ModSecurity 的默认配置是以异常评分模式加载核心规则集，偏执级别 (PL) 为 1：

- 每条匹配的规则都会增加一个异常分数（因此许多规则可以匹配单个请求）
- PL1 包含误报率较低的规则（但安全性低于 PL4）
- 请求的异常分数默认阈值为 5，响应为 4

让我们以以下使用默认配置的 ModSecurity 检测日志为例（为了更好的可读性进行了格式化）：

```log
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `lfi-os-files.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf"]
	[line "78"]
	[id "930120"]
	[rev ""]
	[msg "OS File Access Attempt"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-lfi"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/255/153/126"]
	[tag "PCI/6.5.4"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:utf8toUnicode,t:urlDecodeUni,t:normalizePathWin,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `unix-shell.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf"]
	[line "480"]
	[id "932160"]
	[rev ""]
	[msg "Remote Command Execution: Unix Shell Code Found"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-shell"]
	[tag "platform-unix"]
	[tag "attack-rce"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/152/248/88"]
	[tag "PCI/6.5.2"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:urlDecodeUni,t:cmdLine,t:normalizePath,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [error] 85#85: *11 [client 172.17.0.1] ModSecurity: Access denied with code 403 (phase 2). Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `10' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-949-BLOCKING-EVALUATION.conf"]
	[line "80"]
	[id "949110"]
	[rev ""]
	[msg "Inbound Anomaly Score Exceeded (Total Score: 10)"]
	[data ""]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-generic"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref ""],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
```

正如我们所见，有 3 条不同的日志：

1. 规则 **930120** 匹配
2. 规则 **932160** 匹配
3. 访问被拒绝（规则 **949110**）

需要理解的一个重要事项是，规则 **949110** 并不是一个“真正”的规则：它是因为异常阈值达到（在本例中为 **10**）而拒绝请求的规则。您永远不应该删除 **949110** 规则！

如果是误报，您应该关注 **930120** 和 **932160** 规则。ModSecurity 和/或 CRS 的调整超出了本文档的范围，但不要忘记您可以在 CRS 加载前后应用自定义配置（更多信息请参见[此处](advanced.md#custom-configurations)）。

### 不良行为

一个常见的误报情况是由于“不良行为”功能导致客户端被封禁，这意味着在一段时间内产生了过多的可疑 HTTP 状态码（更多信息请参见[此处](features.md#bad-behavior)）。您应该首先查看设置，然后根据您的 Web 应用程序进行编辑，例如删除可疑的 HTTP 代码、减少计数时间、增加阈值等。

### 白名单

如果您有需要访问您网站的机器人（或管理员），推荐的方法是使用[白名单功能](features.md#whitelist)将它们列入白名单，以避免任何误报。我们不建议使用 `WHITELIST_URI*` 或 `WHITELIST_USER_AGENT*` 设置，除非它们被设置为秘密且不可预测的值。常见的用例是：

- 健康检查/状态机器人
- 回调，如 IPN 或 webhook
- 社交媒体爬虫

## 常见错误

### 上游发送了过大的标头

如果您在日志中看到以下错误 `upstream sent too big header while reading response header from upstream`，您将需要使用以下设置来调整各种代理缓冲区大小：

- `PROXY_BUFFERS`
- `PROXY_BUFFER_SIZE`
- `PROXY_BUSY_BUFFERS_SIZE`

### 无法构建 server_names_hash

如果您在日志中看到以下错误 `could not build server_names_hash, you should increase server_names_hash_bucket_size`，您将需要调整 `SERVER_NAMES_HASH_BUCKET_SIZE` 设置。

## 后台任务始终不运行 {#background-jobs}

如果证书不再续期、封禁列表过时、备份停止，而堆栈仍显示健康，请检查任务页的**上次运行**时间是否继续变化。也可以直接查询 API：

```bash
# 容器堆栈使用 API 服务名；Linux 使用 http://127.0.0.1:8888
curl -H "Authorization: Bearer $API_TOKEN" http://bw-api:8888/jobs
```

### Worker 未运行

从 1.6 升级后最常见的原因是根本没有添加 Worker：只更新 1.6 堆栈的镜像标签会缺少 `bw-api`、`bw-worker` 和 `bw-jobs-broker`。请参阅[升级说明](upgrading.md#breaking-changes)，按对应集成的参考堆栈重新部署。

=== "Docker"

    ```shell
    docker compose ps bw-api bw-worker bw-jobs-broker
    docker compose logs bw-worker
    ```

    找不到这些服务说明堆栈早于 1.7；添加三个服务及 `API_URL`、`API_TOKEN`、`CELERY_BROKER_URL` 后重新创建。

=== "Linux"

    ```shell
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    journalctl -u bunkerweb-worker --no-pager -n 100
    ```

    `bunkerweb-worker` 是 1.7 的新单元，软件包会在每台主机安装它，因此结果应为 `enabled`/`disabled`，而不是 “not found”。

    **在运行 `bunkerweb-scheduler` 的主机上检查。** 该主机应为 `enabled` 且 `active`；执行 `systemctl enable --now bunkerweb-worker` 可修复，同时自动启动任务代理单元。如果它运行中却空闲，应继续检查任务代理。

    **仅运行 BunkerWeb 实例的节点**（安装器 `--worker`，意为运行实例而非控制平面）应保持 `disabled`：此主机不负责执行任务，不要在这里启用它。

    !!! warning "每次软件包升级都会在仅实例节点上重新启用 Worker"
        软件包依据自身环境中的 `WORKER_MODE`/`MANAGER_MODE`/`SERVICE_*` 判断主机角色，但所有升级路径都没有设置这些变量，包括普通 `apt install bunkerweb=...` 和在导出变量前就退出升级路径的 `install-bunkerweb.sh`。因此每次升级都会把主机当作独立安装，启用并启动 `bunkerweb-worker`，以及找到的第一个 Redis 单元。仅实例安装不配置 `bunkerweb-broker`，所以通常启动的是发行版 `redis-server`（或 `valkey`/`redis`）。

        通常不会影响任务：Worker 回退到 `redis://127.0.0.1:6379/0`，没有控制平面向这里派发任务。但如果该节点的 `CELERY_BROKER_URL` 指向**可路由的**任务代理（来自 `--broker-url` 安装或手动配置），残留 Worker 就真的会消费任务。复制安装器生成的本地代理 URL 不属于这种情况：它绑定 `127.0.0.1`，在此节点仍指向自己的回环地址，只会因连接被拒绝而不断重试。需要关闭时，执行 `systemctl disable --now bunkerweb-worker`，并在**每次**升级后重复；只有全新安装或显式运行 `--worker` 安装器才会自动处理。

        **除非已确认 Redis 不是 WAF 数据存储，否则不要停用它。** `USE_REDIS` 和 `REDIS_HOST` 是集群设置，位于控制平面：Web UI → **全局设置** → Redis，或调度器主机的 `/etc/bunkerweb/variables.env`。实例节点自己的同名文件会忽略这些键，搜索它不能证明任何事情。至少接收过一次配置推送的节点可查询已渲染配置：

        ```bash
        grep -E '^(USE_REDIS|REDIS_HOST)=' /etc/nginx/variables.env
        ```

        首次推送前节点只使用启动默认值，必须到控制平面查看。如果 `REDIS_HOST` 是**此主机**的地址（可能是 LAN 地址，不一定是 `127.0.0.1`），此服务器可能存储共享封禁和限流计数器；停用它会丢失这些数据并停止共享。核实之后才能执行 `systemctl disable --now redis-server`（或 `valkey`、`redis`）。

        残留 Worker 指向 `127.0.0.1:6379`，如果本机数据存储受密码保护，它会持续记录 `NOAUTH`。这是此节点闲置 Worker 在访问数据存储，不代表任务执行链故障；下节诊断的是**调度器**主机。

### 任务代理拒绝连接（`NOAUTH`）

代理受密码保护而 `CELERY_BROKER_URL` 没有凭据时，会返回 `NOAUTH Authentication required`。Worker 保持 `active` 却不消费任务，API 的 `POST /jobs/dispatch` 返回 `502`。

```bash
journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'   # Linux
docker compose logs bw-worker | grep -i 'NOAUTH\|AuthenticationError'    # Docker
```

先确认此端点是使用 `maxmemory-policy noeviction` 的专用任务代理。如果端口 `6379` 运行的是会淘汰键的 WAF 数据存储，请通过 [Linux 安装器](integrations.md#easy-installation-script) 配置独立代理，或自行配置，然后使用其实际地址和端口。仅修复 `NOAUTH` 无法保护任务和租约免遭淘汰。

然后为任务代理配置自己的凭据。Linux 上写入 `/etc/bunkerweb/variables.env` 一次即可覆盖 Worker 和 API，因为它们先读取该文件，再读取自身环境；容器堆栈需要对两个服务都设置：

```bash
CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0     # Linux，使用 noeviction 的专用发行版 Redis
CELERY_BROKER_URL=redis://:<password>@bw-jobs-broker:6379/0 # 容器堆栈
```

修改前检查 `/etc/bunkerweb/broker.conf`。如果存在，安装器已配置专用 `bunkerweb-broker`，现有 `CELERY_BROKER_URL` 已包含密码并指向它；请编辑原有行，不要追加，并读取其中的实际端口。`6380` 只是默认值，被占用时安装器会向上选择。如果文件不存在，使用的是自行设置的 `CELERY_BROKER_URL`；未设置时 Linux Worker 和 API 均回退到 `redis://127.0.0.1:6379/0`，适用上面的修复。安装器只在全新安装，或主机 Redis 带有 `requirepass` 或会淘汰键的 `maxmemory` 设置时配置专用代理；使用普通发行版 Redis 的升级主机，以及使用 `--no-broker` 或 `--broker-url` 的安装没有 `broker.conf`。

随后重启两个组件：`systemctl restart bunkerweb-worker bunkerweb-api`，或重新创建 `bw-worker` 和 `bw-api`。

!!! warning "任务代理不是 WAF 数据存储"
    任务代理必须使用 `maxmemory-policy noeviction`。它持有防止两个 Worker 同时推送配置的租约，这些键带有 TTL，任何 `volatile-*` 策略都可能提前淘汰它们。数据存储通常设置上限并允许淘汰，丢失临时计数器比拒绝写入的代价更低。`maxmemory-policy` 按服务器而非数据库生效，使用同一服务器的不同数据库编号不能隔离两种角色。详见[升级说明](upgrading.md#breaking-changes)。

## 已注册实例拒绝启动 {#lost-instance-credential}

实例兑换注册代码后将凭据保存在 `/var/lib/bunkerweb/instance-credential.json`，此后只接受该凭据，永不回退到共享 `API_TOKEN`。若凭据文件消失但注册标记还在，实例会拒绝启动，并显示：

```
This instance was enrolled but its credential is gone (/var/lib/bunkerweb/instance-credential.json
is missing or contains no usable credential) [...] Refusing to start.
```

触发条件是注册标记仍在，但没有可用凭据：文件被删除、截断、还原时遗漏或不含凭据。如果文件存在却无法读取（例如升级后归 root 所有），实例会启动，但在权限修复前拒绝所有推送；此时应恢复权限，而不是重新注册。

另外两种情况会正常启动，却在控制平面表现为所有推送被拒绝：完全没有 `/data` 卷地重建容器（标记和凭据一同丢失，成为全新未注册实例），或从注册前的快照恢复（其中没有这两个文件）。实例只在每次调用时记录 `can't validate API token from IP …` 警告，不会指出注册状态丢失，需在控制平面诊断。

启动被拒绝后有两条恢复路径：

- **继续注册**：在 Web UI **实例**页点击钥匙按钮，或调用 API `POST /instances/{hostname}/enroll`，签发新注册代码，下一次启动时通过 `INSTANCE_ENROLLMENT_CODE` 传入。
- **恢复共享令牌**：必须同时处理两端。在实例上删除 `/var/lib/bunkerweb/instance-enrolled` 和 `instance-credential.json`；残留的空或截断凭据文件会让实例拒绝所有令牌，包括共享令牌。这样实例可用 `API_TOKEN` 启动，但控制平面仍持有此前签发的凭据，推送仍会被拒绝，因此还须清除数据库行中的凭据：

    ```bash
    curl -X PATCH -H "Authorization: Bearer $API_TOKEN" -H 'Content-Type: application/json' \
      -d '{"credential": ""}' http://bw-api:8888/instances/<hostname>
    ```

    空 `credential` 会清除已存储凭据，不受实例来源方法限制，控制平面恢复使用共享 `API_TOKEN`。此操作仅由 API 提供；**实例**页提供轮换和撤销，不提供清空。

    **清空不会解除撤销。** 如果先撤销了实例，清空凭据不起作用：该行继续被撤销，所有推送仍被拒绝。新注册代码可以解除撤销；对于声明自身令牌的实例（`BUNKERWEB_INSTANCE_API_TOKEN[_n]`，配合分组形式 `BUNKERWEB_INSTANCE_HOST_n`；扁平的 `BUNKERWEB_INSTANCES` 列表没有令牌），下一次调度器配置保存也会从环境重新读取凭据并解除撤销，且记录日志。声明的令牌必须**不同于全局 `API_TOKEN`**；再次声明共享令牌不算有效声明，不会解除撤销，也不会有日志。其他行只能通过重新注册恢复。如果不想调用 API，**UI 或 API 注册**的实例可在实例页（或 `DELETE /instances/{hostname}`）删除后重建；**通过环境声明**的实例可先从 `BUNKERWEB_INSTANCES` 移除，保存一次调度器配置，待该行连同 UI 设置的 TLS 指纹固定和名称一起删除后，再重新声明。这两种办法比 `PATCH` 丢弃更多配置。

    autoconf、Kubernetes 或 Swarm **发现的实例**不涉及此情况：控制平面拒绝为编排器来源的行签发凭据，因此它们从未注册。

    **重新注册是受支持的恢复方式，应优先使用。**

!!! tip "为实例提供持久 `/data`"
    参考堆栈在 `bunkerweb` 服务挂载 `bw-instance-data` 卷正是为此。缺少它时，每次 `docker compose down` 后再 `up` 都会丢失凭据，实例以未注册状态正常启动；控制平面则出现推送无法送达的问题。参见[实例注册](web-ui.md#instance-enrollment)。

## 时区

当使用基于容器的集成时，容器的时区可能与主机的时区不匹配。要解决此问题，您可以在您的容器上将 `TZ` 环境变量设置为您选择的时区（例如 `TZ=Europe/Paris`）。您可以在[此处](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List)找到时区标识符的列表。

## 从数据库清理旧实例 {#clear-old-instances-db}

BunkerWeb 会将已知实例存储在 `bw_instances` 表中（主键：`hostname`）。
如果你经常重新部署，可能会残留旧记录（例如长时间未上报的实例），此时你可能希望将其清理掉。

!!! warning "先备份"
    在手动修改数据库之前，请先创建备份（对 SQLite 卷做快照，或使用你的数据库引擎备份工具）。

!!! warning "停止写入端"
    为避免删除时发生竞态，请先停止（或缩容）会更新实例信息的组件
    （通常是 scheduler / autoconf，取决于你的部署方式），执行清理后再重新启动它们。

### 表与字段（参考）

实例模型定义如下：

- 表：`bw_instances`
- 主键：`hostname`
- “最后一次出现”时间戳：`last_seen`
- 还包含：
  `name`, `port`, `listen_https`, `https_port`,
  `server_name`, `type`, `status`, `method`,
  `creation_date`

### 1 - 连接数据库

使用现有的 [访问数据库](#access-database) 章节进行连接
（SQLite / MariaDB / PostgreSQL）。

### 2 - Dry-run：列出过期实例

选择一个保留窗口（示例：90 天），先查看将会被删除的内容。

=== "SQLite"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days')
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "MariaDB / MySQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY)
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "PostgreSQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days'
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

### 3 - 删除过期实例

确认无误后，删除这些记录。

=== "SQLite"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days');

    COMMIT;
    ```

=== "MariaDB / MySQL"

    ```sql
    START TRANSACTION;

    DELETE FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY);

    COMMIT;
    ```

=== "PostgreSQL"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days';

    COMMIT;
    ```

!!! tip "按 hostname 删除"
    如需删除某个特定实例，请使用其 hostname（主键）。

    ```sql
    DELETE FROM bw_instances WHERE hostname = '<hostname>';
    ```

### 4 - 标记实例已变更（可选）

BunkerWeb 会在 `bw_metadata` 表中跟踪实例变更
（`instances_changed`, `last_instances_change`）。

如果手动清理后 UI 没有按预期刷新，你可以强制更新“变更标记”：

=== "SQLite / PostgreSQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = CURRENT_TIMESTAMP
    WHERE id = 1;
    ```

=== "MariaDB / MySQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = NOW()
    WHERE id = 1;
    ```

### 5 - 回收空间（可选）

=== "SQLite"

    ```sql
    VACUUM;
    ```

=== "PostgreSQL"

    ```sql
    VACUUM (ANALYZE);
    ```

=== "MariaDB / MySQL"

    ```sql
    OPTIMIZE TABLE bw_instances;
    ```

## Web UI {#web-ui}

如果您忘记了 UI 凭据或遇到 2FA 问题，您可以连接到数据库以重新获得访问权限。

### 访问数据库 {#access-database}

=== "SQLite"

    === "Linux"

        安装 SQLite (Debian/Ubuntu)：

        ```shell
        sudo apt install sqlite3
        ```

        安装 SQLite (Fedora/RedHat)：

        ```shell
        sudo dnf install sqlite
        ```

    === "Docker"

        进入您的调度器容器的 shell：

        !!! note "Docker 参数"
            - `-u 0` 选项用于以 root 身份运行命令（强制）
            - `-it` 选项用于以交互方式运行命令（强制）
            - `<bunkerweb_scheduler_container>`：您的调度器容器的名称或 ID

        ```shell
        docker exec -u 0 -it <bunkerweb_scheduler_container> bash
        ```

        安装 SQLite：

        ```bash
        apk add sqlite
        ```

    === "All-in-one"

        进入您的 All-in-one 容器的 shell：

        !!! note "Docker 参数"
            - `-u 0` 选项用于以 root 身份运行命令（强制）。
            - `-it` 选项用于以交互方式运行命令（强制）。
            - `bunkerweb-aio` 是默认的容器名称；如果您使用了自定义名称，请进行调整。

        ```shell
        docker exec -u 0 -it bunkerweb-aio bash
        ```

    访问您的数据库：

    !!! note "数据库路径"
        我们假设您正在使用默认的数据库路径。如果您正在使用自定义路径，您需要调整该命令。
        对于 All-in-one，我们假设数据库是位于持久化 `/data` 卷中的 `db.sqlite3` (`/data/db.sqlite3`)。

    ```bash
    sqlite3 /var/lib/bunkerweb/db.sqlite3
    ```

    您应该会看到类似这样的内容：

    ```text
    SQLite version <VER> <DATE>
    Enter ".help" for usage hints.
    sqlite>
    ```

=== "MariaDB / MySQL"

    !!! note "仅限 MariaDB / MySQL"
        以下步骤仅适用于 MariaDB / MySQL 数据库。如果您正在使用其他数据库，请参阅您数据库的文档。

    !!! note "凭据和数据库名称"
        您将需要使用 `DATABASE_URI` 设置中使用的相同凭据和数据库名称。

    === "Linux"

        访问您的本地数据库：

        ```bash
        mysql -u <user> -p <database>
        ```

        然后输入数据库用户的密码，您就应该能够访问您的数据库了。

    === "Docker"

        访问您的数据库容器：

        !!! note "Docker 参数"
            - `-u 0` 选项用于以 root 身份运行命令（强制）
            - `-it` 选项用于以交互方式运行命令（强制）
            - `<bunkerweb_db_container>`：您的数据库容器的名称或 ID
            - `<user>`：数据库用户
            - `<database>`：数据库名称

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> mysql -u <user> -p <database>
        ```

        然后输入数据库用户的密码，您就应该能够访问您的数据库了。

    === "All-in-one"

        一体化镜像不包含 MariaDB/MySQL 服务器。如果您已将 AIO 配置为使用外部 MariaDB/MySQL 数据库（通过设置 `DATABASE_URI` 环境变量），您应使用标准的 MySQL 客户端工具直接连接到该数据库。

        连接方法将类似于“Linux”选项卡（如果从运行 AIO 的主机或另一台机器连接），或者如果愿意，可以在一个单独的 Docker 容器中运行 MySQL 客户端，并指定您的外部数据库的主机和凭据。

=== "PostgreSQL"

    !!! note "仅限 PostgreSQL"
        以下步骤仅适用于 PostgreSQL 数据库。如果您正在使用其他数据库，请参阅您数据库的文档。

    !!! note "凭据、主机和数据库名称"
        您将需要使用 `DATABASE_URI` 设置中使用的相同凭据（用户/密码）、主机和数据库名称。

    === "Linux"

        访问您的本地数据库：

        ```bash
        psql -U <user> -d <database>
        ```

        如果您的数据库在另一台主机上，请包含主机名/IP 和端口：

        ```bash
        psql -h <host> -p 5432 -U <user> -d <database>
        ```

        然后输入数据库用户的密码，您就应该能够访问您的数据库了。

    === "Docker"

        访问您的数据库容器：

        !!! note "Docker 参数"
            - `-u 0` 选项用于以 root 身份运行命令（强制）
            - `-it` 选项用于以交互方式运行命令（强制）
            - `<bunkerweb_db_container>`：您的数据库容器的名称或 ID
            - `<user>`：数据库用户
            - `<database>`：数据库名称

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> psql -U <user> -d <database>
        ```

        如果数据库托管在其他地方，请相应地添加 `-h <host>` 和 `-p 5432` 选项。

    === "All-in-one"

        一体化镜像不包含 PostgreSQL 服务器。如果您已将 AIO 配置为使用外部 PostgreSQL 数据库（通过设置 `DATABASE_URI` 环境变量），您应使用标准的 PostgreSQL 客户端工具直接连接到该数据库。

        连接方法将类似于“Linux”选项卡（如果从运行 AIO 的主机或另一台机器连接），或者如果愿意，可以在一个单独的 Docker 容器中运行 PostgreSQL 客户端，并指定您的外部数据库的主机和凭据。

### 故障排除操作

!!! info "表模式"
    `bw_ui_users` 表的模式如下：

    | 字段          | 类型                                                | 空  | 键  | 默认 | 额外 |
    | ------------- | --------------------------------------------------- | --- | --- | ---- | ---- |
    | username      | varchar(256)                                        | NO  | PRI | NULL |      |
    | email         | varchar(256)                                        | YES | UNI | NULL |      |
    | password      | varchar(60)                                         | NO  |     | NULL |      |
    | method        | enum('ui','scheduler','autoconf','manual','wizard') | NO  |     | NULL |      |
    | admin         | tinyint(1)                                          | NO  |     | NULL |      |
    | theme         | enum('light','dark')                                | NO  |     | NULL |      |
    | language      | varchar(2)                                          | NO  |     | NULL |      |
    | totp_secret   | varchar(256)                                        | YES |     | NULL |      |
    | creation_date | datetime                                            | NO  |     | NULL |      |
    | update_date   | datetime                                            | NO  |     | NULL |      |

=== "检索用户名"

    执行以下命令从 `bw_ui_users` 表中提取数据：

    ```sql
    SELECT * FROM bw_ui_users;
    ```

    您应该会看到类似这样的内容：

    | 用户名 | 电子邮件 | 密码 | 方法   | 管理员 | 主题  | totp_secret | 创建日期 | 更新日期 |
    | ------ | -------- | ---- | ------ | ------ | ----- | ----------- | -------- | -------- |
    | ***    | ***      | ***  | manual | 1      | light | ***         | ***      | ***      |

=== "更新管理员用户密码"

    您首先需要使用 bcrypt 算法对新密码进行哈希处理。

    安装 Python bcrypt 库：

    ```shell
    pip install bcrypt
    ```

    生成您的哈希值（将 `mypassword` 替换为您自己的密码）：

    ```shell
    python3 -c 'from bcrypt import hashpw, gensalt ; print(hashpw(b"""mypassword""", gensalt(rounds=10)).decode("utf-8"))'
    ```

    您可以通过执行此命令来更新您的用户名/密码：

    ```sql
    UPDATE bw_ui_users SET password = '<password_hash>' WHERE admin = 1;
    ```

    如果您在此命令之后再次检查您的 `bw_ui_users` 表：

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    您应该会看到类似这样的内容：

    | 用户名 | 电子邮件 | 密码 | 方法   | 管理员 | 主题  | totp_secret | 创建日期 | 更新日期 |
    | ------ | -------- | ---- | ------ | ------ | ----- | ----------- | -------- | -------- |
    | ***    | ***      | ***  | manual | 1      | light | ***         | ***      | ***      |

    您现在应该能够使用新凭据登录到 Web UI。

=== "为管理员用户禁用 2FA 认证"

    您可以通过执行此命令来停用 2FA：

    ```sql
    UPDATE bw_ui_users SET totp_secret = NULL WHERE admin = 1;
    ```

    如果您在此命令之后再次检查您的 `bw_ui_users` 表：

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    您应该会看到类似这样的内容：

    | 用户名 | 电子邮件 | 密码 | 方法   | 管理员 | 主题  | totp_secret | 创建日期 | 更新日期 |
    | ------ | -------- | ---- | ------ | ------ | ----- | ----------- | -------- | -------- |
    | ***    | ***      | ***  | manual | 1      | light | NULL        | ***      | ***      |

    您现在应该能够仅使用您的用户名和密码登录 Web UI，而无需 2FA。

=== "刷新 2FA 恢复码"

    恢复码可以在 Web UI 的**个人资料页面**的 `安全` 选项卡下刷新。

=== "导出配置和匿名日志"

    使用 Web UI 中的**支持页面**来快速收集配置和日志以进行故障排除。

    - 打开 Web UI 并转到支持页面。
    - 选择范围：导出全局设置或选择特定服务。
    - 点击下载所选范围的配置存档。
    - 可选地下载日志：导出的日志会自动匿名化（所有 IP 地址和域名都被屏蔽）。

### 上传插件

在某些情况下，可能无法从 UI 上传插件：

- 您的集成缺少管理压缩文件的软件包，在这种情况下，您需要添加必要的软件包
- Safari 浏览器：'安全模式'可能会阻止您添加插件。您需要在您的机器上进行必要的更改
