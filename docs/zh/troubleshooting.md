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

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

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

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

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

### 访问数据库

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
