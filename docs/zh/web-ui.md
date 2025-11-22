# Web UI

## 概述

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb Web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

“Web UI”是一个 Web 应用程序，帮助您使用用户友好的界面来管理您的 BunkerWeb 实例，而不是仅仅依赖于命令行。

以下是 Web UI 提供的功能列表：

-   全面了解被阻止的攻击
-   启动、停止、重启和重新加载您的 BunkerWeb 实例
-   为您的 Web 应用程序添加、编辑和删除设置
-   为 NGINX 和 ModSecurity 添加、编辑和删除自定义配置
-   安装和卸载外部插件
-   浏览缓存的文件
-   监控作业执行并根据需要重新启动它们
-   查看日志并搜索模式

## 先决条件 {#prerequisites}

由于 Web UI 是一个 Web 应用程序，推荐的架构是在其前面运行 BunkerWeb 作为反向代理。推荐的安装过程是使用设置向导，它将按照[快速入门指南](quickstart-guide.md)中的描述一步一步地指导您。

!!! warning "安全注意事项"

    Web UI 的安全性极其重要。如果未经授权的人员获得了对该应用程序的访问权限，他们不仅能够编辑您的配置，还可能在 BunkerWeb 的上下文中执行代码（例如，通过包含 LUA 代码的自定义配置）。我们强烈建议您遵循最低限度的安全最佳实践，例如：

    *   为登录选择一个强密码（**至少 8 个字符，包括 1 个小写字母、1 个大写字母、1 个数字和 1 个特殊字符**）
    *   将 Web UI 放置在一个“难以猜测”的 URI 下
    *   启用双因素身份验证 (2FA)
    *   不要在没有额外限制的情况下将 Web UI 暴露在互联网上
    *   根据您的用例，应用文档的[高级用法部分](advanced.md#security-tuning)中列出的最佳实践

## 升级到 PRO {#upgrade-to-pro}

!!! tip "BunkerWeb PRO 免费试用"
    想要快速试用 BunkerWeb PRO 一个月吗？在 [BunkerWeb 面板](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc)下单时使用代码 `freetrial`，或者点击[这里](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc)直接应用促销代码（将在结账时生效）。

一旦您从 [BunkerWeb 面板](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc)获得了您的 PRO 许可证密钥，您可以将其粘贴到 Web UI 的 PRO 页面中。

<figure markdown>
  ![PRO 升级](assets/img/pro-ui-upgrade.png){ align=center, width="700" }
  <figcaption>从 Web UI 升级到 PRO</figcaption>
</figure>

!!! warning "升级时间"
    PRO 版本由调度器在后台下载，升级可能需要一些时间。

当您的 BunkerWeb 实例升级到 PRO 版本后，您将看到您的许可证到期日期和您可以保护的最大服务数量。

<figure markdown>
  ![PRO 升级](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>PRO 许可证信息</figcaption>
</figure>

## 访问日志

从 `1.6` 版本开始，访问日志的方法发生了变化。此更新特别影响基于容器的集成：Web UI 现在将从 `/var/log/bunkerweb` 目录读取日志文件。

为了使日志可以从 Web UI 访问，我们建议您使用一个 syslog 服务器，例如 `syslog-ng`，来读取日志并在 `/var/log/bunkerweb` 目录中创建相应的文件。

!!! warning "为日志使用本地文件夹"
    出于安全原因，Web UI 在容器内以**UID 101 和 GID 101 的非特权用户**身份运行：万一漏洞被利用，攻击者将不会拥有完全的 root (UID/GID 0) 权限。

    但是，有一个缺点：如果您为日志使用**本地文件夹**，您必须**设置正确的权限**，以便非特权用户可以读取日志文件。例如：

    ```shell
    mkdir bw-logs && \
    chown root:101 bw-logs && \
    chmod 770 bw-logs
    ```

    或者，如果文件夹已经存在：

    ```shell
    chown -R root:101 bw-logs && \
    chmod -R 770 bw-logs
    ```

    如果您正在使用[无根模式的 Docker](https://docs.docker.com/engine/security/rootless) 或 [podman](https://podman.io/)，容器中的 UID 和 GID 将映射到主机上不同的 UID 和 GID。您首先需要检查您的初始 subuid 和 subgid：

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    例如，如果您的值为 **100000**，则映射的 UID/GID 将为 **100100** (100000 + 100)：

    ```shell
    mkdir bw-logs && \
    sudo chgrp 100100 bw-logs && \
    chmod 770 bw-logs
    ```

    或者如果文件夹已经存在：

    ```shell
    sudo chgrp -R 100100 bw-logs && \
    sudo chmod -R 770 bw-logs
    ```

### Compose 样板文件

=== "Docker"

    要将日志正确转发到 Docker 集成的 `/var/log/bunkerweb` 目录，您需要使用 `syslog-ng` 将日志流式传输到文件中。这是一个如何执行此操作的示例：

    ```yaml
    x-bw-env: &bw-env
      # 我们锚定环境变量以避免重复
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
      # 可选的 API 令牌，用于保护 API 访问
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # 这将是 syslog-ng 用来创建日志文件的标签
            syslog-address: "udp://10.20.30.254:514" # 这是 syslog-ng 容器的地址

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 确保设置正确的实例名称
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # 将其更改为一个难以猜测的 URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # 这将是 syslog-ng 用来创建日志文件的标签
            syslog-address: "udp://10.20.30.254:514" # 这是 syslog-ng 容器的地址

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # 记得为管理员用户设置一个更强的密码
          TOTP_ENCRYPTION_KEYS: "mysecret" # 记得设置一个更强的密钥（请参阅先决条件部分）
        volumes:
          - bw-logs:/var/log/bunkerweb # 这是用于存储日志的卷
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # 这将是 syslog-ng 用来创建日志文件的标签
            syslog-address: "udp://10.20.30.254:514" # 这是 syslog-ng 容器的地址

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

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # 绑定到低端口
          - NET_BROADCAST  # 发送广播
          - NET_RAW  # 使用原始套接字
          - DAC_READ_SEARCH  # 绕过权限读取文件
          - DAC_OVERRIDE  # 覆盖文件权限
          - CHOWN  # 更改所有权
          - SYSLOG  # 写入系统日志
        volumes:
          - bw-logs:/var/log/bunkerweb # 这是用于存储日志的卷
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # 这是 syslog-ng 配置文件
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # 确保设置正确的 IP 地址

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

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

    要将日志正确转发到 Autoconf 集成的 `/var/log/bunkerweb` 目录，您需要使用 `syslog-ng` 将日志流式传输到文件中。这是一个如何执行此操作的示例：

    ```yaml
    x-ui-env: &bw-ui-env
      # 我们锚定环境变量以避免重复
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # 这将是 syslog-ng 用来创建日志文件的标签
            syslog-address: "udp://10.20.30.254:514" # 这是 syslog-ng 容器的地址

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "" # 我们不需要在这里指定 BunkerWeb 实例，因为它们由 autoconf 服务自动检测
          SERVER_NAME: "" # 服务器名称将由服务标签填充
          MULTISITE: "yes" # autoconf / ui 的强制设置
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # 这将是 syslog-ng 用来创建日志文件的标签
            syslog-address: "udp://10.20.30.254:514" # 这是 syslog-ng 容器的地址

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375" # 这是 Docker 套接字地址
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-autoconf" # 这将是 syslog-ng 用来创建日志文件的标签
            syslog-address: "udp://10.20.30.254:514" # 这是 syslog-ng 容器的地址

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # 记得为管理员用户设置一个更强的密码
          TOTP_ENCRYPTION_KEYS: "mysecret" # 记得设置一个更强的密钥（请参阅先决条件部分）
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme" # 将其更改为一个难以猜测的 URI
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # 这将是 syslog-ng 用来创建日志文件的标签
            syslog-address: "udp://10.20.30.254:514" # 这是 syslog-ng 容器的地址

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

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: "unless-stopped"
        networks:
          - bw-docker

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # 绑定到低端口
          - NET_BROADCAST  # 发送广播
          - NET_RAW  # 使用原始套接字
          - DAC_READ_SEARCH  # 绕过权限读取文件
          - DAC_OVERRIDE  # 覆盖文件权限
          - CHOWN  # 更改所有权
          - SYSLOG  # 写入系统日志
        volumes:
          - bw-logs:/var/log/bunkerweb # 这是用于存储日志的卷
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # 这是 syslog-ng 配置文件
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # 确保设置正确的 IP 地址

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

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

### Syslog-ng 配置

这是一个 `syslog-ng.conf` 文件的示例，您可以使用它将日志转发到文件中：

```conf
@version: 4.8

# 用于从 Docker 容器接收日志的源配置
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# 用于格式化日志消息的模板
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# 用于将日志写入动态命名文件的目标配置
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
  );
};

# 将日志定向到动态命名文件的日志路径
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## 帐户管理

您可以通过点击右上角的个人资料图片来访问帐户管理页面：

<figure markdown>
  ![概述](assets/img/manage-account.png){ align=center, width="400" }
  <figcaption>从右上角访问帐户页面</figcaption>
</figure>

### 用户名/密码

!!! warning "忘记密码/用户名"

    如果您忘记了 UI 凭据，您可以按照[故障排除部分中描述的步骤](troubleshooting.md#web-ui)从 CLI 重置它们。

您可以通过填写**安全**选项卡中的专用表单来更新您的用户名或密码。出于安全原因，即使您已连接，也需要输入您当前的密码。

请注意，当您的用户名或密码更新后，您将从 Web UI 注销，以便再次登录。

<figure markdown>
  ![概述](assets/img/profile-username-password.png){ align=center }
  <figcaption>用户名/密码表单</figcaption>
</figure>

### 双因素认证

!!! tip "强制性加密密钥"

    当启用 2FA 时，您必须提供至少一个加密密钥。此密钥将用于加密您的 TOTP 密钥。

    生成有效密钥的推荐方法是使用 `passlib` 包：

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    在 Web UI 的 `TOTP_ENCRYPTION_KEYS` 环境变量中设置生成的密钥。您还可以设置多个以空格分隔的密钥或一个字典（为了向后兼容）。

!!! warning "丢失密钥"

    如果您丢失了您的密钥，有两个可用的选项：

    -   您可以使用启用 2FA 时提供的恢复码之一来恢复您的帐户（一个恢复码只能使用一次）。
    -   您可以按照[故障排除部分中描述的步骤](troubleshooting.md#web-ui)从 CLI 禁用 2FA。

您可以通过为您的帐户添加**双因素身份验证 (2FA)** 来增强您的登录安全性。这样做之后，除了您的密码之外，还需要一个额外的代码。

Web UI 使用[基于时间的一次性密码 (TOTP)](https://en.wikipedia.org/wiki/Time-based_one-time_password) 作为 2FA 实现：使用**密钥**，该算法将生成**仅在短时间内有效的一次性密码**。

任何 TOTP 客户端，例如 Google Authenticator、Authy、FreeOTP 等，都可以用来存储密钥并生成代码。请注意，一旦启用 TOTP，**您将无法从 Web UI 中检索它**。

从 Web UI 启用 TOTP 功能需要以下步骤：

-   将密钥复制或使用二维码扫描到您的身份验证器应用程序中
-   在 2FA 输入框中输入当前的 TOTP 代码
-   输入您当前的密码

!!! info "密钥刷新"
    每次您访问页面或提交表单时都会**生成一个新的密钥**。如果出现问题（例如：TOTP 代码过期），您需要将新的密钥复制到您的身份验证器应用程序中，直到成功启用 2FA。

!!! tip "恢复码"

    当您启用 2FA 时，您将获得 **5 个恢复码**。如果您丢失了您的 TOTP 密钥，这些代码可用于恢复您的帐户。每个代码只能使用一次。**这些代码只会显示一次，因此请务必将它们存储在安全的地方**。

    如果您丢失了您的恢复码，**您可以通过帐户管理页面的 TOTP 部分刷新它们**。请注意，旧的恢复码将失效。

您可以在**安全**选项卡中启用或禁用 2FA，并刷新恢复码：

<figure markdown>
  ![概述](assets/img/profile-totp.png){ align=center }
  <figcaption>TOTP 启用/禁用/刷新恢复码表单</figcaption>
</figure>

成功登录/密码组合后，您将被提示输入您的 TOTP 代码：

<figure markdown>
  ![概述](assets/img/profile-2fa.png){ align=center, width="400" }
  <figcaption>登录页面上的 2FA</figcaption>
</figure>

### 当前会话

在**会话**选项卡中，您将能够列出和撤销当前会话：

<figure markdown>
  ![概述](assets/img/sessions.png){ align=center }
  <figcaption>管理会话</figcaption>
</figure>

## 高级安装

Web UI 可以不通过设置向导过程进行部署和配置：配置是通过环境变量完成的，这些变量可以直接添加到容器中，或者在 Linux 集成的情况下添加到 `/etc/bunkerweb/ui.env` 文件中。

!!! tip "Web UI 特定环境变量"

    Web UI 使用以下环境变量：

    -   `OVERRIDE_ADMIN_CREDS`：将其设置为 `yes` 以启用覆盖，即使管理员凭据已设置（默认为 `no`）。
    -   `ADMIN_USERNAME`：访问 Web UI 的用户名。
    -   `ADMIN_PASSWORD`：访问 Web UI 的密码。
    -   `FLASK_SECRET`：用于加密会话 cookie 的密钥（如果未设置，将生成一个随机密钥）。
    -   `TOTP_ENCRYPTION_KEYS` (或 `TOTP_SECRETS`)：以空格分隔的 TOTP 加密密钥列表或一个字典（例如：`{"1": "mysecretkey"}` 或 `mysecretkey` 或 `mysecretkey mysecretkey1`）。**如果您想使用 2FA，我们强烈建议您设置此变量，因为它将用于加密 TOTP 密钥**（如果未设置，将生成一个随机数量的密钥）。有关更多信息，请查看 [passlib 文档](https://passlib.readthedocs.io/en/stable/narr/totp-tutorial.html#application-secrets)。
    -   `UI_LISTEN_ADDR` (首选)：Web UI 将监听的地址（**Docker 镜像**中默认为 `0.0.0.0`，**Linux 安装**中默认为 `127.0.0.1`）。如果未设置，则回退到 `LISTEN_ADDR`。
    -   `UI_LISTEN_PORT` (首选)：Web UI 将监听的端口（默认为 `7000`）。如果未设置，则回退到 `LISTEN_PORT`。
    -   `MAX_WORKERS`：Web UI 使用的工作进程数（默认为 CPU 数量）。
    -   `MAX_THREADS`：Web UI 使用的线程数（默认为 `MAX_WORKERS` * 2）。
    -   `FORWARDED_ALLOW_IPS`：允许在 `X-Forwarded-For` 标头中使用的 IP 地址或网络列表（**Docker 镜像**中默认为 `*`，**Linux 安装**中默认为 `127.0.0.1`）。
    -   `CHECK_PRIVATE_IP`：将其设置为 `yes`，以便在会话期间 IP 地址发生更改但位于私有网络中的用户不会断开连接（默认为 `yes`）。（非私有 IP 地址总是会被检查）。
    -   `ENABLE_HEALTHCHECK`：将其设置为 `yes` 以启用 `/healthcheck` 端点，该端点返回一个包含状态信息的简单 JSON 响应（默认为 `no`）。

    Web UI 将使用这些变量来验证您的身份并处理 2FA 功能。

!!! example "生成推荐的密钥"

    要生成一个有效的 **ADMIN_PASSWORD**，我们建议您**使用密码管理器**或**密码生成器**。

    您可以使用以下命令生成一个有效的 **FLASK_SECRET**：

    ```shell
    python3 -c "import secrets; print(secrets.token_hex(64))"
    ```

    您可以使用以下命令生成有效的以空格分隔的 **TOTP_ENCRYPTION_KEYS**（您将需要 `passlib` 包）：

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

=== "Linux"

    使用[Linux 集成](integrations.md#linux)安装 Web UI 非常简单，因为它与 BunkerWeb 一起安装。

    Web UI 作为名为 `bunkerweb-ui` 的 systemd 服务提供，请确保它已启用：

    ```shell
    sudo systemctl enable bunkerweb-ui && \
    sudo systemctl status bunkerweb-ui
    ```

    位于 `/etc/bunkerweb/ui.env` 的专用环境文件用于配置 Web UI：

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    TOTP_ENCRYPTION_KEYS=mysecret
    ```

    将 `changeme` 数据替换为您自己的值。

    记得为 `TOTP_ENCRYPTION_KEYS` 设置一个更强的密钥。

    每次编辑 `/etc/bunkerweb/ui.env` 文件后，您都需要重启该服务：

    ```shell
    systemctl restart bunkerweb-ui
    ```

    通过 BunkerWeb 访问 Web UI 是一个经典的[反向代理设置](quickstart-guide.md)。请注意，Web UI 在 `7000` 端口上监听，并且只在环回接口上。

    这是您可以使用的 `/etc/bunkerweb/variables.env` 样板：

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_TEMPLATE=ui
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    ```

    不要忘记重新加载 `bunkerweb` 服务：

    ```shell
    systemctl reload bunkerweb
    ```

=== "Docker"

    Web UI 可以使用一个专用的容器来部署，该容器可在 [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) 上找到：

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    或者，您也可以自己构建它：

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    通过 BunkerWeb 访问 Web UI 是一个经典的反向代理设置](quickstart-guide.md)。我们建议您使用一个专用网络（例如也由调度器使用的 `bw-universe`）连接 BunkerWeb 和 Web UI，这样它就不会与您的 Web 服务在同一个网络上，出于明显的安全原因。请注意，Web UI 容器在 `7000` 端口上监听。

    !!! info "数据库后端"

        如果您想要一个除 MariaDB 之外的数据库后端，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations)中的 docker-compose 文件。

    这是您可以使用的 docker-compose 样板（不要忘记编辑 `changeme` 数据）：

    ```yaml
    x-ui-env: &ui-env
      # 我们锚定环境变量以避免重复
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 用于 QUIC / HTTP3 支持
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 确保设置正确的 IP 范围，以便调度器可以将配置发送到实例
          API_TOKEN: "" # 如果使用，镜像 API_TOKEN
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 确保设置正确的实例名称
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # 我们从 bunkerweb 服务镜像 API_WHITELIST_IP
          API_TOKEN: "" # 如果使用，镜像 API_TOKEN
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # 记得设置一个更强的 URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000" # Web UI 容器默认在 7000 端口监听
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # 记得为 changeme 用户设置一个更强的密码
          TOTP_ENCRYPTION_KEYS: "mysecret" # 记得设置一个更强的密钥（请参阅先决条件部分）
        networks:
          - bw-universe
          - bw-db

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

=== "Docker autoconf"

    Web UI 可以使用一个专用的容器来部署，该容器可在 [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) 上找到：

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    或者，您也可以自己构建它：

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "环境变量"

        请阅读[先决条件](#prerequisites)部分，查看所有可以设置来自定义 Web UI 的环境变量。

    通过 BunkerWeb 访问 Web UI 是一个经典的反向代理设置](quickstart-guide.md)。我们建议您使用一个专用网络（例如也由调度器和 autoconf 使用的 `bw-universe`）连接 BunkerWeb 和 Web UI，这样它就不会与您的 Web 服务在同一个网络上，出于明显的安全原因。请注意，Web UI 容器在 `7000` 端口上监听。

    !!! info "数据库后端"

        如果您想要一个除 MariaDB 之外的数据库后端，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations)中的 docker-compose 文件。

    这是您可以使用的 docker-compose 样板（不要忘记编辑 `changeme` 数据）：

    ```yaml
    x-ui-env: &ui-env
      # 我们锚定环境变量以避免重复
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # 用于 QUIC / HTTP3 支持
        labels:
          - "bunkerweb.INSTANCE=yes" # 我们设置实例标签以允许 autoconf 检测实例
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6
        depends_on:
          - bw-docker
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
        networks:
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # 记得为 changeme 用户设置一个更强的密码
          TOTP_ENCRYPTION_KEYS: "mysecret" # 记得设置一个更强的密钥（请参阅先决条件部分）
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        networks:
          - bw-universe
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

=== "Kubernetes"

    Web UI 可以使用一个专用的容器来部署，该容器可在 [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) 上找到，您可以将其作为标准的 [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) 进行部署。

    通过 BunkerWeb 访问 Web UI 是一个经典的反向代理设置](quickstart-guide.md)。本文档不涉及 Web UI 和 Web 服务之间的网络分段。请注意，Web UI 容器在 `7000` 端口上监听。

    !!! info "数据库后端"

        如果您想要一个除 MariaDB 之外的数据库后端，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations)中的 yaml 文件。

    这是您可以使用的 values.yaml 文件的相应部分：

    ```yaml
    settings:
      # 使用一个名为 bunkerweb 的现有 secret，其中包含以下值：
      # - admin-username
      # - admin-password
      # - flask-secret
      # - totp-secrets
      existingSecret: "secret-bunkerweb"
    ui:
      wizard: false
      ingress:
        enabled: true
        serverName: "www.example.com"
        serverPath: "/admin"
      overrideAdminCreds: "yes"
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    Web UI 可以使用一个专用的容器来部署，该容器可在 [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) 上找到：

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    或者，您也可以自己构建它：

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    通过 BunkerWeb 访问 Web UI 是一个经典的反向代理设置](quickstart-guide.md)。我们建议您使用一个专用网络（例如也由调度器和 autoconf 使用的 `bw-universe`）连接 BunkerWeb 和 Web UI，这样它就不会与您的 Web 服务在同一个网络上，出于明显的安全原因。请注意，Web UI 容器在 `7000` 端口上监听。

    !!! info "数据库后端"

        如果您想要一个除 MariaDB 之外的数据库后端，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations)中的堆栈文件。

    这是您可以使用的堆栈样板（不要忘记编辑 `changeme` 数据）：

    ```yaml
    x-ui-env: &ui-env
      # 我们锚定环境变量以避免重复
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置一个更强的密码

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
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
            protocol: udp # 用于 QUIC / HTTP3 支持
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
          UI_HOST: "http://bw-ui:7000" # 如果需要，请更改它
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONFIGS: "1"
          CONTAINERS: "1"
          SERVICES: "1"
          SWARM: "1"
          TASKS: "1"
          LOG_LEVEL: "warning"
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
        networks:
          - bw-db

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.6
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # 记得为 changeme 用户设置一个更强的密码
          TOTP_ENCRYPTION_KEYS: "mysecret" # 记得设置一个更强的密钥（请参阅先决条件部分）
        networks:
          - bw-universe
          - bw-db
        deploy:
          labels:
            - "bunkerweb.SERVER_NAME=www.example.com"
            - "bunkerweb.USE_TEMPLATE=ui"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_URL=/changeme"
            - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"

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

## 语言支持与本地化

BunkerWeb UI 支持多种语言。翻译文件在 `src/ui/app/static/locales` 目录中管理。目前支持以下语言：

- 英语 (en)
- 法语 (fr)
- 阿拉伯语 (ar)
- 孟加拉语 (bn)
- 西班牙语 (es)
- 印地语 (hi)
- 葡萄牙语 (pt)
- 俄语 (ru)
- 乌尔都语 (ur)
- 中文 (zh)
- 德语 (de)
- 意大利语 (it)

有关翻译来源和审核状态的详细信息，请参阅 [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.6/src/ui/app/static/locales/README.md)。

### 贡献翻译

我们欢迎您为改进或添加新的语言文件做出贡献！

**如何贡献翻译：**

1.  编辑 `src/ui/app/lang_config.py` 文件以添加您的语言（代码、名称、国旗、英文名称）。
2.  将 `en.json` 复制为 `src/ui/app/static/locales/` 中的模板，并将其重命名为您的语言代码（例如，德语为 `de.json`）。
3.  在新文件中翻译值。
4.  更新 `locales/README.md` 中的表格，添加您的语言并注明创建者/审阅者。
5.  提交一个拉取请求。

对于更新，请编辑相关文件并根据需要更新来源表。

有关完整指南，请参阅 [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.6/src/ui/app/static/locales/README.md)。
