# 升级

## 从 1.6.X 升级

### 步骤

#### Docker

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
        1.  **更新 Docker Compose 文件**：更新 Docker Compose 文件以使用新版本的 BunkerWeb 镜像。
            ```yaml
            services:
                bunkerweb:
                    image: bunkerity/bunkerweb:1.6.7-rc1
                    ...
                bw-scheduler:
                    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                    ...
                bw-autoconf:
                    image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                    ...
                bw-ui:
                    image: bunkerity/bunkerweb-ui:1.6.7-rc1
                    ...
            ```

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

#### Linux

=== "使用安装脚本轻松升级"

    *   **快速开始**：

        要开始使用，请下载安装脚本及其校验和，然后在运行前验证脚本的完整性。

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | jq -r .tag_name)

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
        | `--backup-dir <PATH>`   | 自动升级前备份的目的地。如果不存在则创建。                            |
        | `--no-auto-backup`      | 跳过自动备份（不推荐）。您必须有手动备份。                            |
        | `-q, --quiet`           | 抑制输出（与日志记录/监控结合使用）。                                 |
        | `-f, --force`           | 在不受支持的操作系统版本上继续。                                      |
        | `--dry-run`             | 显示检测到的环境、预期的操作，然后退出而不做任何更改。                |

        示例：

        ```bash
        # 交互式升级到 1.6.7~rc1（会提示备份）
        sudo ./install-bunkerweb.sh --version 1.6.7~rc1

        # 使用自动备份到自定义目录的非交互式升级
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --backup-dir /var/backups/bw-2025-01 -y

        # 静默无人值守升级（抑制日志）– 依赖默认的自动备份
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 -y -q

        # 执行一次空运行（计划）而不应用更改
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --dry-run

        # 跳过自动备份进行升级（不推荐）
        sudo ./install-bunkerweb.sh -v 1.6.7~rc1 --no-auto-backup -y
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
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
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
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
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
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
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
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
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
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
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
                        image: bunkerity/bunkerweb:1.6.7-rc1
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.6.7-rc1
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
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
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
                    sudo dnf install -y --allowerasing bunkerweb-1.6.7~rc1
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
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
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
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
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
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8.  **降级 BunkerWeb**。
        -   按照[Linux 集成页面](integrations.md#linux)中升级 BunkerWeb 的相同步骤，将 BunkerWeb 降级到以前的版本。
