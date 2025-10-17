# 高级用法

GitHub 仓库的 [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.5/examples) 文件夹中提供了许多真实世界的用例示例。

我们还提供了许多样板文件，例如用于各种集成和数据库类型的 YAML 文件。这些都可以在 [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5/misc/integrations) 文件夹中找到。

本节仅关注高级用法和安全调整，请参阅文档的[功能部分](features.md)以查看所有可用的设置。

## 用例

!!! tip "测试"
    当启用多站点模式时（并且如果您没有为域设置正确的 DNS 条目），要执行快速测试，您可以使用 curl 并带上您选择的 HTTP 主机头：
    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```

    如果您使用 HTTPS，您将需要处理 SNI：
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

### 在负载均衡器或反向代理之后

!!! info "真实 IP"

    当 BunkerWeb 本身位于负载均衡器或反向代理之后时，您需要对其进行配置，以便它可以获取客户端的真实 IP 地址。**如果您不这样做，安全功能将阻止负载均衡器或反向代理的 IP 地址，而不是客户端的 IP 地址**。

BunkerWeb 实际上支持两种方法来检索客户端的真实 IP 地址：

- 使用 `PROXY 协议`
- 使用像 `X-Forwarded-For` 这样的 HTTP 头

可以使用以下设置：

- `USE_REAL_IP`：启用/禁用真实 IP 检索
- `USE_PROXY_PROTOCOL`：启用/禁用 PROXY 协议支持。
- `REAL_IP_FROM`：允许向我们发送“真实 IP”的受信任 IP/网络地址列表
- `REAL_IP_HEADER`：包含真实 IP 的 HTTP 头或在使用 PROXY 协议时的特殊值 `proxy_protocol`

您将在文档的[功能部分](features.md#real-ip)找到更多关于真实 IP 的设置。

=== "HTTP 头"

    我们将对负载均衡器或反向代理做出以下假设（您需要根据您的配置更新设置）：

    - 它们使用 `X-Forwarded-For` 头来设置真实 IP
    - 它们的 IP 位于 `1.2.3.0/24` 和 `100.64.0.0/10` 网络中

    === "Web UI"

        导航到**全局配置**页面，选择 **Real IP** 插件并填写以下设置：

        <figure markdown>![使用 Web UI 的真实 IP 设置（HTTP 头）](assets/img/advanced-proxy1.png){ align=center }<figcaption>使用 Web UI 的真实 IP 设置（HTTP 头）</figcaption></figure>

        请注意，当您更改与真实 IP 相关的设置时，建议重新启动 BunkerWeb。

    === "Linux"

        您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        请注意，在配置与真实 IP 相关的设置时，建议执行重启而不是重新加载：

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        在运行 All-in-one 容器时，您需要将设置添加到环境变量中：

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.5
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker autoconf"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Kubernetes"

        您需要将设置添加到 BunkerWeb 和调度程序 Pod 的环境变量中。

        这是您可以使用的 `values.yaml` 文件的相应部分：

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        ```

    === "Swarm"

        !!! warning "已弃用"
            Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

            **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

        您需要将设置添加到 BunkerWeb 和调度程序服务的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        请注意，如果您的服务已经创建，您需要删除并重新创建它，以便更新新的环境变量。

=== "Proxy protocol"

    !!! warning "请仔细阅读"

        只有在您确定您的负载均衡器或反向代理正在发送 PROXY 协议时才使用它。**如果您启用它而未使用，将会出现错误**。

    我们将对负载均衡器或反向代理做出以下假设（您需要根据您的配置更新设置）：

    - 它们使用 `PROXY 协议` v1 或 v2 来设置真实 IP
    - 它们的 IP 位于 `1.2.3.0/24` 和 `100.64.0.0/10` 网络中

    === "Web UI"

        导航到**全局配置**页面，选择 **Real IP** 插件并填写以下设置：

        <figure markdown>![使用 Web UI 的真实 IP 设置（PROXY 协议）](assets/img/advanced-proxy2.png){ align=center }<figcaption>使用 Web UI 的真实 IP 设置（PROXY 协议）</figcaption></figure>

        请注意，当您更改与真实 IP 相关的设置时，建议重新启动 BunkerWeb。

    === "Linux"

        您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        请注意，在配置与代理协议相关的设置时，建议执行重启而不是重新加载：

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "All-in-one"

        在运行 All-in-one 容器时，您需要将设置添加到环境变量中：

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e USE_PROXY_PROTOCOL="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.5
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Docker autoconf"

        您需要将设置添加到 BunkerWeb 和调度程序容器的环境变量中：

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        请注意，如果您的容器已经创建，您需要删除并重新创建它，以便更新新的环境变量。

    === "Kubernetes"

        您需要将设置添加到 BunkerWeb 和调度程序 Pod 的环境变量中。

        这是您可以使用的 `values.yaml` 文件的相应部分：

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        ```

    === "Swarm"

        !!! warning "已弃用"
            Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

            **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

        您需要将设置添加到 BunkerWeb 和调度程序服务的环境变量中。

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        请注意，如果您的服务已经创建，您需要删除并重新创建它，以便更新新的环境变量。

### 使用自定义 DNS 解析机制

BunkerWeb 的 NGINX 配置可以根据您的需求定制，以使用不同的 DNS 解析器。这在各种场景中特别有用：

1. 为了遵循您本地 `/etc/hosts` 文件中的条目
2. 当您需要为某些域使用自定义 DNS 服务器时
3. 为了与本地 DNS 缓存解决方案集成

#### 使用 systemd-resolved

许多现代 Linux 系统使用 `systemd-resolved` 进行 DNS 解析。如果您希望 BunkerWeb 遵循您 `/etc/hosts` 文件的内容并使用系统的 DNS 解析机制，您可以将其配置为使用本地的 systemd-resolved DNS 服务。

要验证 systemd-resolved 是否在您的系统上运行，您可以使用：

```bash
systemctl status systemd-resolved
```

要在 BunkerWeb 中启用 systemd-resolved 作为您的 DNS 解析器，请将 `DNS_RESOLVERS` 设置为 `127.0.0.53`，这是 systemd-resolved 的默认监听地址：

=== "Web UI"

    导航到**全局配置**页面，并将 DNS 解析器设置为 `127.0.0.53`

    <figure markdown>![使用 Web UI 设置 DNS 解析器](assets/img/advanced-dns-resolvers.png){ align=center }<figcaption>使用 Web UI 设置 DNS 解析器</figcaption></figure>

=== "Linux"

    您需要修改 `/etc/bunkerweb/variables.env` 文件：

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    进行此更改后，重新加载调度程序以应用配置：

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

#### 使用 dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) 是一个轻量级的 DNS、DHCP 和 TFTP 服务器，通常用于本地 DNS 缓存和定制。当您需要比 systemd-resolved 提供更多对 DNS 解析的控制时，它特别有用。

=== "Linux"

    首先，在您的 Linux 系统上安装和配置 dnsmasq：

    === "Debian/Ubuntu"

        ```bash
        # 安装 dnsmasq
        sudo apt-get update && sudo apt-get install dnsmasq

        # 配置 dnsmasq 仅在 localhost 上监听
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # 如果需要，添加自定义 DNS 条目
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # 重启 dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # 安装 dnsmasq
        sudo dnf install dnsmasq

        # 配置 dnsmasq 仅在 localhost 上监听
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # 如果需要，添加自定义 DNS 条目
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # 重启 dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    然后配置 BunkerWeb 使用 dnsmasq，方法是将 `DNS_RESOLVERS` 设置为 `127.0.0.1`：

    === "Web UI"

        导航到**全局配置**页面，选择 **NGINX** 插件并将 DNS 解析器设置为 `127.0.0.1`。

        <figure markdown>![使用 Web UI 设置 DNS 解析器](assets/img/advanced-dns-resolvers2.png){ align=center }<figcaption>使用 Web UI 设置 DNS 解析器</figcaption></figure>

    === "Linux"

        您需要修改 `/etc/bunkerweb/variables.env` 文件：

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        进行此更改后，重新加载调度程序：

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "All-in-one"

    当使用 All-in-one 容器时，在单独的容器中运行 dnsmasq 并配置 BunkerWeb 使用它：

    ```bash
    # 为 DNS 通信创建一个自定义网络
    docker network create bw-dns

    # 使用 dockurr/dnsmasq 运行 dnsmasq 容器，并使用 Quad9 DNS
    # Quad9 提供专注于安全的 DNS 解析，并带有恶意软件拦截功能
    docker run -d \
        --name dnsmasq \
        --network bw-dns \
        -e DNS1="9.9.9.9" \
        -e DNS2="149.112.112.112" \
        -p 53:53/udp \
        -p 53:53/tcp \
        --cap-add=NET_ADMIN \
        --restart=always \
        dockurr/dnsmasq

    # 运行 BunkerWeb All-in-one 并使用 dnsmasq DNS 解析器
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.5
    ```

=== "Docker"

    将 dnsmasq 服务添加到您的 docker-compose 文件中，并配置 BunkerWeb 使用它：

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # 使用 Quad9 DNS 服务器以增强安全性和隐私
          # 主服务器：9.9.9.9 (Quad9，带恶意软件拦截)
          # 备用服务器：149.112.112.112 (Quad9 备用服务器)
          DNS1: "9.9.9.9"
          DNS2: "149.112.112.112"
        ports:
          - 53:53/udp
          - 53:53/tcp
        cap_add:
          - NET_ADMIN
        restart: always
        networks:
          - bw-dns

      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...现有网络...
      bw-dns:
        name: bw-dns
    ```

### 自定义配置 {#custom-configurations}

要自定义并向 BunkerWeb 添加自定义配置，您可以利用其 NGINX 基础。自定义 NGINX 配置可以添加到不同的 NGINX 上下文中，包括 ModSecurity Web 应用程序防火墙 (WAF) 的配置，这是 BunkerWeb 的核心组件。有关 ModSecurity 配置的更多详细信息，请参见[此处](features.md#custom-configurations)。

以下是可用的自定义配置类型：

- **http**：NGINX 的 HTTP 级别的配置。
- **server-http**：NGINX 的 HTTP/服务器级别的配置。
- **default-server-http**：NGINX 的服务器级别的配置，特别用于当提供的客户端名称与 `SERVER_NAME` 中的任何服务器名称都不匹配时的“默认服务器”。
- **modsec-crs**：在加载 OWASP 核心规则集之前应用的配置。
- **modsec**：在加载 OWASP 核心规则集之后应用的配置，或在未加载核心规则集时使用。
- **crs-plugins-before**：CRS 插件的配置，在加载 CRS 插件之前应用。
- **crs-plugins-after**：CRS 插件的配置，在加载 CRS 插件之后应用。
- **stream**：NGINX 的 Stream 级别的配置。
- **server-stream**：NGINX 的 Stream/服务器级别的配置。

自定义配置可以全局应用，也可以针对特定服务器应用，具体取决于适用的上下文以及是否启用了[多站点模式](concepts.md#multisite-mode)。

应用自定义配置的方法取决于所使用的集成。然而，其底层过程涉及将带有 `.conf` 后缀的文件添加到特定文件夹中。要为特定服务器应用自定义配置，该文件应放置在以主服务器名称命名的子文件夹中。

某些集成提供了更方便的应用配置方式，例如在 Docker Swarm 中使用 [Configs](https://docs.docker.com/engine/swarm/configs/) 或在 Kubernetes 中使用 [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)。这些选项为管理和应用配置提供了更简单的方法。

=== "Web UI"

    导航到**配置**页面，点击**创建新的自定义配置**，然后您可以选择是全局配置还是特定于服务的配置，以及配置类型和配置名称：

    <figure markdown>![使用 Web UI 的自定义配置](assets/img/advanced-config.png){ align=center }<figcaption>使用 Web UI 的自定义配置</figcaption></figure>

    别忘了点击 `💾 保存` 按钮。

=== "Linux"

    当使用 [Linux 集成](integrations.md#linux)时，自定义配置必须写入 `/etc/bunkerweb/configs` 文件夹。

    这是一个 server-http/hello-world.conf 的示例：

    ```nginx
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    因为 BunkerWeb 以非特权用户 (nginx:nginx) 运行，您需要编辑权限：

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    现在让我们检查调度程序的状态：

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    如果它们已经在运行，我们可以重新加载它：

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "All-in-one"

    当使用 [All-in-one 镜像](integrations.md#all-in-one-aio-image)时，您有两种选择来添加自定义配置：

    - 在运行容器时使用特定的 `*_CUSTOM_CONF_*` 设置作为环境变量（推荐）。
    - 将 `.conf` 文件写入挂载到 `/data` 的卷内的 `/data/configs/` 目录。

    **使用设置（环境变量）**

    要使用的设置必须遵循 `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` 的模式：

    - `<SITE>`：可选的主服务器名称，如果启用了多站点模式并且配置必须应用于特定服务。
    - `<TYPE>`：配置的类型，可接受的值为 `HTTP`、`DEFAULT_SERVER_HTTP`、`SERVER_HTTP`、`MODSEC`、`MODSEC_CRS`、`CRS_PLUGINS_BEFORE`、`CRS_PLUGINS_AFTER`、`STREAM` 和 `SERVER_STREAM`。
    - `<NAME>`：不带 `.conf` 后缀的配置名称。

    这是一个在运行 All-in-one 容器时的示例：

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e "CUSTOM_CONF_SERVER_HTTP_hello-world=location /hello { \
            default_type 'text/plain'; \
            content_by_lua_block { \
              ngx.say('world'); \
            } \
          }" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.5
    ```

    请注意，如果您的容器已经创建，您需要删除并重新创建它，以便应用新的环境变量。

    **使用文件**

    首先要做的是创建文件夹：

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    现在您可以编写您的配置了：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    因为调度程序以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    启动调度程序容器时，您需要将文件夹挂载到 /data 上：

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.5
    ```

=== "Docker"

    当使用 [Docker 集成](integrations.md#docker)时，您有两种选择来添加自定义配置：

    - 使用特定的 `*_CUSTOM_CONF_*` 设置作为环境变量（推荐）
    - 将 .conf 文件写入挂载在调度程序 /data 上的卷中

    **使用设置**

    要使用的设置必须遵循 `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` 的模式：

    - `<SITE>`：可选的主服务器名称，如果启用了多站点模式并且配置必须应用于特定服务
    - `<TYPE>`：配置的类型，可接受的值为 `HTTP`、`DEFAULT_SERVER_HTTP`、`SERVER_HTTP`、`MODSEC`、`MODSEC_CRS`、`CRS_PLUGINS_BEFORE`、`CRS_PLUGINS_AFTER`、`STREAM` 和 `SERVER_STREAM`
    - `<NAME>`：不带 .conf 后缀的配置名称

    这是一个使用 docker-compose 文件的示例：

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.5
      environment:
        - |
          CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
              ngx.say('world')
            }
          }
      ...
    ```

    **使用文件**

    首先要做的是创建文件夹：

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    现在您可以编写您的配置了：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    因为调度程序以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    启动调度程序容器时，您需要将文件夹挂载到 /data 上：

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.5
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    当使用 [Docker autoconf 集成](integrations.md#docker-autoconf)时，您有两种选择来添加自定义配置：

    - 使用特定的 `*_CUSTOM_CONF_*` 设置作为标签（最简单）
    - 将 .conf 文件写入挂载在调度程序 /data 上的卷中

    **使用标签**

    !!! warning "使用标签的限制"
        当使用 Docker autoconf 集成的标签时，您只能为相应的 Web 服务应用自定义配置。应用 **http**、**default-server-http**、**stream** 或任何全局配置（例如所有服务的 **server-http** 或 **server-stream**）是不可能的：您需要为此挂载文件。

    要使用的标签必须遵循 `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` 的模式：

    - `<TYPE>`：配置的类型，可接受的值为 `SERVER_HTTP`、`MODSEC`、`MODSEC_CRS`、`CRS_PLUGINS_BEFORE`、`CRS_PLUGINS_AFTER` 和 `SERVER_STREAM`
    - `<NAME>`：不带 .conf 后缀的配置名称

    这是一个使用 docker-compose 文件的示例：

    ```yaml
    myapp:
      image: nginxdemos/nginx-hello
      labels:
        - |
          bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
                ngx.say('world')
            }
          }
      ...
    ```

    **使用文件**

    首先要做的是创建文件夹：

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    现在您可以编写您的配置了：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    因为调度程序以 UID 和 GID 101 的非特权用户运行，您需要编辑权限：

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    启动调度程序容器时，您需要将文件夹挂载到 /data 上：

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.5
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    当使用 [Kubernetes 集成](integrations.md#kubernetes)时，
    自定义配置通过 [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) 管理。

    无需将 ConfigMap 挂载到 Pod（例如作为环境变量或卷）。
    Autoconf Pod 会监听 ConfigMap 事件并在检测到更改时立即更新配置。

    请为需要由 Ingress 控制器管理的 ConfigMap 添加以下注解：

    - `bunkerweb.io/CONFIG_TYPE`：必填。请选择受支持的类型（`http`、`server-http`、`default-server-http`、`modsec`,
      `modsec-crs`、`crs-plugins-before`、`crs-plugins-after`、`stream` 或 `server-stream`）。
    - `bunkerweb.io/CONFIG_SITE`：可选。设置为主要服务器名称（在 `Ingress` 中声明）以仅作用于该服务；不设置则表示全局生效。

    这是一个示例：

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: cfg-bunkerweb-all-server-http
      annotations:
        bunkerweb.io/CONFIG_TYPE: "server-http"
    data:
      myconf: |
      location /hello {
        default_type 'text/plain';
        content_by_lua_block {
          ngx.say('world')
        }
      }
    ```

    !!! info "同步方式"
        - Ingress 控制器会持续监听带注解的 ConfigMap。
        - 如果设置了 `NAMESPACES` 环境变量，则仅处理这些命名空间中的 ConfigMap。
        - 创建或更新受管 ConfigMap 会立即触发配置重新加载。
        - 删除 ConfigMap，或移除 `bunkerweb.io/CONFIG_TYPE` 注解，会清除对应的自定义配置。
        - 当指定 `bunkerweb.io/CONFIG_SITE` 时，引用的服务必须已经存在；否则该 ConfigMap 会被忽略，直到服务出现。

    !!! tip "自定义额外配置"
        自 `1.6.0` 版本起，您可以使用 `bunkerweb.io/CONFIG_TYPE=settings` 注解来添加/覆盖设置。这是一个示例：

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # 多站点设置，将应用于所有未覆盖它的服务
          USE_REDIS: "yes" # 全局设置，将全局应用
          ...
        ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    当使用 [Swarm 集成](integrations.md#swarm)时，自定义配置是使用 [Docker Configs](https://docs.docker.com/engine/swarm/configs/) 管理的。

    为了简单起见，您甚至不需要将配置附加到服务上：autoconf 服务正在监听配置事件，并会在需要时更新自定义配置。

    创建配置时，您需要添加特殊的标签：

    *   **bunkerweb.CONFIG_TYPE**：必须设置为有效的自定义配置类型（http、server-http、default-server-http、modsec、modsec-crs、crs-plugins-before、crs-plugins-after、stream 或 server-stream）
    *   **bunkerweb.CONFIG_SITE**：设置为服务器名称以将配置应用于该特定服务器（可选，如果未设置则将全局应用）

    这是一个示例：

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    没有更新机制：替代方法是使用 `docker config rm` 删除现有配置，然后重新创建它。

### 在生产环境中运行大量服务 {#running-many-services-in-production}

#### 全局 CRS

!!! warning "CRS 插件"
    当 CRS 全局加载时，**不支持 CRS 插件**。如果您需要使用它们，则需要为每个服务加载 CRS。

如果您在生产环境中使用 BunkerWeb 并有大量服务，并且您全局启用了带有 CRS 规则的 **ModSecurity 功能**，那么加载 BunkerWeb 配置所需的时间可能会变得过长，从而可能导致超时。

解决方法是全局加载 CRS 规则，而不是按服务加载。出于向后兼容性的原因，此行为默认未启用，并且因为它有一个缺点：如果您启用全局 CRS 规则加载，**将不再可能按服务定义 modsec-crs 规则**（在 CRS 规则之前执行）。然而，这个限制可以通过编写如下所示的全局 `modsec-crs` 排除规则来绕过：

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

您可以通过将 `USE_MODSECURITY_GLOBAL_CRS` 设置为 `yes` 来启用全局 CRS 加载。

#### 为 MariaDB/MySQL 调整 max_allowed_packet

在使用 BunkerWeb 并有大量服务时，MariaDB 和 MySQL 数据库服务器中 `max_allowed_packet` 参数的默认值似乎不足。

如果您遇到这样的错误，尤其是在调度程序上：

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

您需要在您的数据库服务器上增加 `max_allowed_packet` 的值。

### 封禁和报告的持久化 {#persistence-of-bans-and-reports}

默认情况下，BunkerWeb 将封禁和报告存储在本地的 Lua 数据存储中。虽然这种设置简单高效，但意味着当实例重启时数据会丢失。为了确保封禁和报告在重启后仍然存在，您可以将 BunkerWeb 配置为使用远程的 [Redis](https://redis.io/) 或 [Valkey](https://valkey.io/) 服务器。

**为什么使用 Redis/Valkey？**

Redis 和 Valkey 是功能强大的内存数据存储，通常用作数据库、缓存和消息代理。它们具有高度可扩展性，并支持多种数据结构，包括：

- **字符串**：基本的键值对。
- **哈希**：单个键内的字段-值对。
- **列表**：有序的字符串集合。
- **集合**：无序的唯一字符串集合。
- **有序集合**：带有分数的有序集合。

通过利用 Redis 或 Valkey，BunkerWeb 可以持久地存储封禁、报告和缓存数据，确保其持久性和可扩展性。

**启用 Redis/Valkey 支持**

要启用 Redis 或 Valkey 支持，请在您的 BunkerWeb 配置文件中配置以下设置：

```conf
# 启用 Redis/Valkey 支持
USE_REDIS=yes

# Redis/Valkey 服务器主机名或 IP 地址
REDIS_HOST=<hostname>

# Redis/Valkey 服务器端口号（默认：6379）
REDIS_PORT=6379

# Redis/Valkey 数据库编号（默认：0）
REDIS_DATABASE=0
```

- **`USE_REDIS`**：设置为 `yes` 以启用 Redis/Valkey 集成。
- **`REDIS_HOST`**：指定 Redis/Valkey 服务器的主机名或 IP 地址。
- **`REDIS_PORT`**：指定 Redis/Valkey 服务器的端口号。默认为 `6379`。
- **`REDIS_DATABASE`**：指定要使用的 Redis/Valkey 数据库编号。默认为 `0`。

如果您需要更高级的设置，例如身份验证、SSL/TLS 支持或 Sentinel 模式，请参阅 [Redis 插件设置文档](features.md#redis)以获取详细指导。

### 保护 UDP/TCP 应用程序

!!! example "实验性功能"

      此功能尚未准备好用于生产。欢迎您进行测试，并通过 GitHub 仓库中的 [issues](https://github.com/bunkerity/bunkerweb/issues) 向我们报告任何错误。

BunkerWeb 能够作为**通用的 UDP/TCP 反向代理**，让您可以保护任何至少在 OSI 模型第 4 层运行的网络应用程序。BunkerWeb 并未使用“传统”的 HTTP 模块，而是利用了 NGINX 的 [stream 模块](https://nginx.org/en/docs/stream/ngx_stream_core_module.html)。

需要注意的是，**在使用 stream 模块时，并非所有设置和安全功能都可用**。有关此方面的更多信息，可以在文档的[功能](features.md)部分找到。

配置一个基本的反向代理与 HTTP 设置非常相似，因为它涉及使用相同的设置：`USE_REVERSE_PROXY=yes` 和 `REVERSE_PROXY_HOST=myapp:9000`。即使当 BunkerWeb 位于负载均衡器之后时，设置也保持不变（由于显而易见的原因，支持的选项是**PROXY 协议**）。

除此之外，还使用了以下特定设置：

- `SERVER_TYPE=stream`：激活 `stream` 模式（通用 UDP/TCP）而不是 `http` 模式（默认）
- `LISTEN_STREAM_PORT=4242`：BunkerWeb 将监听的“普通”（无 SSL/TLS）端口
- `LISTEN_STREAM_PORT_SSL=4343`：BunkerWeb 将监听的“ssl/tls”端口
- `USE_UDP=no`：监听并转发 UDP 数据包而不是 TCP

有关 `stream` 模式的完整设置列表，请参阅文档的[功能](features.md)部分。

!!! tip "多个监听端口"

    自 `1.6.0` 版本起，BunkerWeb 支持 `stream` 模式的多个监听端口。您可以使用 `LISTEN_STREAM_PORT` 和 `LISTEN_STREAM_PORT_SSL` 设置来指定它们。

    这是一个示例：

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "All-in-one"

    在运行 All-in-one 容器时，您需要将设置添加到环境变量中。您还需要暴露流端口。

    此示例将 BunkerWeb 配置为代理两个基于流的应用程序 `app1.example.com` 和 `app2.example.com`。

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e SERVICE_UI="no" \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e USE_REVERSE_PROXY="yes" \
        -e SERVER_TYPE="stream" \
        -e app1.example.com_REVERSE_PROXY_HOST="myapp1:9000" \
        -e app1.example.com_LISTEN_STREAM_PORT="10000" \
        -e app2.example.com_REVERSE_PROXY_HOST="myapp2:9000" \
        -e app2.example.com_LISTEN_STREAM_PORT="20000" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        -p 10000:10000/tcp \
        -p 20000:20000/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.5
    ```

    请注意，如果您的容器已经创建，您需要删除并重新创建它，以便应用新的环境变量。

    您的应用程序（`myapp1`, `myapp2`）应该在单独的容器中运行（或以其他方式可访问），并且它们的主机名/IP（例如，在 `_REVERSE_PROXY_HOST` 中使用的 `myapp1`, `myapp2`）必须可以从 `bunkerweb-aio` 容器解析和访问。这通常涉及将它们连接到共享的 Docker 网络。

    !!! note "停用 UI 服务"
        建议停用 UI 服务（例如，通过设置环境变量 `SERVICE_UI=no`），因为 Web UI 与 `SERVER_TYPE=stream` 不兼容。

=== "Docker"

    当使用 Docker 集成时，保护现有网络应用程序的最简单方法是将服务添加到 `bw-services` 网络中：

    ```yaml
    x-bw-api-env: &bw-api-env
      # 我们使用锚点来避免为所有服务重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
      # 可选的 API 令牌，用于经过身份验证的 API 调用
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        ports:
          - "80:8080" # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
          - "10000:10000" # app1
          - "20000:20000" # app2
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 此设置是指定 BunkerWeb 实例所必需的
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # 将应用于所有服务
          SERVER_TYPE: "stream" # 将应用于所有服务
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services

    volumes:
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
    ```

=== "Docker autoconf"

    在您的机器上运行 [Docker autoconf 集成](integrations.md#docker-autoconf)堆栈之前，您需要编辑端口：

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        ports:
          - "80:8080" # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
          - "10000:10000" # app1
          - "20000:20000" # app2
    ...
    ```

    一旦堆栈运行，您可以将现有应用程序连接到 `bw-services` 网络，并使用标签配置 BunkerWeb：

    ```yaml
    services:
      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app1.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app2.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! example "实验性功能"

        目前，[Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) 不支持 `stream` 模式。**我们在这里所做的是一个使其工作的变通方法。**

        欢迎您进行测试，并通过 GitHub 仓库中的 [issues](https://github.com/bunkerity/bunkerweb/issues) 向我们报告任何错误。

    在您的机器上运行 [Kubernetes 集成](integrations.md#kubernetes)堆栈之前，您需要在您的负载均衡器上打开端口：

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
          port: 80
          targetPort: 8080
        - name: app1
          port: 10000
          targetPort: 10000
        - name: app2
          port: 20000
          targetPort: 20000
      selector:
        app: bunkerweb
    ```

    一旦堆栈运行，您可以创建您的 ingress 资源：

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # 将应用于所有服务
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # 在 stream 模式下不使用，但必须填写
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # 在 stream 模式下不使用，但必须填写
                pathType: Prefix
                backend:
                  service:
                    name: svc-app2
                    port:
                      number: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app1
      namespace: services
      labels:
        app: app1
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app1
      template:
        metadata:
          labels:
            app: app1
        spec:
          containers:
            - name: app1
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app1"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app1
      namespace: services
    spec:
      selector:
        app: app1
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app2
      namespace: services
      labels:
        app: app2
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app2
      template:
        metadata:
          labels:
            app: app2
        spec:
          containers:
            - name: app2
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app2"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app2
      namespace: services
    spec:
      selector:
        app: app2
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ```

=== "Linux"

    您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

    ```conf
    ...
    SERVER_NAME=app1.example.com app2.example.com
    MULTISITE=yes
    USE_REVERSE_PROXY=yes
    SERVER_TYPE=stream
    app1.example.com_REVERSE_PROXY_HOST=myapp1.domain.or.ip:9000
    app1.example.com_LISTEN_STREAM_PORT=10000
    app2.example.com_REVERSE_PROXY_HOST=myapp2.domain.or.ip:9000
    app2.example.com_LISTEN_STREAM_PORT=20000
    ...
    ```

    现在让我们检查调度程序的状态：

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    如果它们已经在运行，我们可以重新加载它：

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    在您的机器上运行 [Swarm 集成](integrations.md#swarm)堆栈之前，您需要编辑端口：

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        ports:
          # 如果您想在使用 http 挑战类型时使用 Let's Encrypt 自动化，请保留此项
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          # app1
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
          # app2
          - published: 20000
            target: 20000
            mode: host
            protocol: tcp
    ...
    ```

    一旦堆栈运行，您可以将现有应用程序连接到 `bw-services` 网络，并使用标签配置 BunkerWeb：

    ```yaml
    services:

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

### PHP

!!! example "实验性功能"
      目前，BunkerWeb 对 PHP 的支持仍处于测试阶段，我们建议您如果可以的话，使用反向代理架构。顺便说一句，对于某些集成（如 Kubernetes），PHP 完全不受支持。

BunkerWeb 支持使用外部或远程的 [PHP-FPM](https://www.php.net/manual/en/install.fpm.php) 实例。我们将假设您已经熟悉管理此类服务。

可以使用以下设置：

- `REMOTE_PHP`：远程 PHP-FPM 实例的主机名。
- `REMOTE_PHP_PATH`：远程 PHP-FPM 实例中包含文件的根文件夹。
- `REMOTE_PHP_PORT`：远程 PHP-FPM 实例的端口（*默认为 9000*）。
- `LOCAL_PHP`：本地 PHP-FPM 实例的套接字文件路径。
- `LOCAL_PHP_PATH`：本地 PHP-FPM 实例中包含文件的根文件夹。

=== "All-in-one"

    当使用 [All-in-one 镜像](integrations.md#all-in-one-aio-image)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中。
    - 为您的应用程序设置一个 PHP-FPM 容器，并挂载包含 PHP 文件的文件夹。
    - 在运行 BunkerWeb 时，使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为环境变量。

    如果您启用[多站点模式](concepts.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 directories, 2 files
    ```

    我们将假设您的 PHP 应用程序位于名为 `www` 的文件夹中。请注意，您需要修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    现在您可以运行 BunkerWeb，为您的 PHP 应用程序配置它，并运行 PHP 应用程序。您需要创建一个自定义的 Docker 网络，以允许 BunkerWeb 与您的 PHP-FPM 容器通信。

    ```bash
    # 创建一个自定义网络
    docker network create php-network

    # 运行 PHP-FPM 容器
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # 运行 BunkerWeb All-in-one
    docker run -d \
        --name bunkerweb-aio \
        --network php-network \
        -v ./www:/var/www/html \
        -v bw-storage:/data \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e REMOTE_PHP_PATH="/app" \
        -e app1.example.com_REMOTE_PHP="myapp1-php" \
        -e app2.example.com_REMOTE_PHP="myapp2-php" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.5
    ```

    请注意，如果您的容器已经创建，您需要删除并重新创建它，以便应用新的环境变量。

=== "Docker"

    当使用 [Docker 集成](integrations.md#docker)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中
    - 为您的应用程序设置一个 PHP-FPM 容器，并挂载包含 PHP 文件的文件夹
    - 在启动 BunkerWeb 时，使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为环境变量

    如果您启用[多站点模式](concepts.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    我们将假设您的 PHP 应用程序位于名为 `www` 的文件夹中。请注意，您需要修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    现在您可以运行 BunkerWeb，为您的 PHP 应用程序配置它，并运行 PHP 应用程序：

    ```yaml
    x-bw-api-env: &bw-api-env
      # 我们使用锚点来避免为所有服务重复相同的设置
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # 此设置是指定 BunkerWeb 实例所必需的
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # 由于 MULTISITE 设置，将应用于所有服务
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: php:fpm
        volumes:
          - ./www/app1.example.com:/app
        networks:
          - bw-services

      myapp2:
        image: php:fpm
        volumes:
          - ./www/app2.example.com:/app
        networks:
          - bw-services

      myapp3:
        image: php:fpm
        volumes:
          - ./www/app3.example.com:/app
        networks:
          - bw-services

    volumes:
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
    ```

=== "Docker autoconf"

    !!! info "已启用多站点模式"
        [Docker autoconf 集成](integrations.md#docker-autoconf)意味着使用多站点模式：保护一个 PHP 应用程序与保护多个应用程序相同。

    当使用 [Docker autoconf 集成](integrations.md#docker-autoconf)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中
    - 为您的应用程序设置 PHP-FPM 容器，并挂载包含 PHP 应用程序的文件夹
    - 使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为您的 PHP-FPM 容器的标签

    由于 Docker autoconf 意味着使用[多站点模式](concepts.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    创建文件夹后，复制您的文件并修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    当您启动 BunkerWeb autoconf 堆栈时，将 `www` 文件夹挂载到 **Scheduler** 容器的 `/var/www/html` 中：

    ```yaml
    x-bw-api-env: &bw-api-env
      # 我们使用锚点来避免为所有服务重复相同的设置
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # 我们不需要在这里指定 BunkerWeb 实例，因为它们由 autoconf 服务自动检测
          SERVER_NAME: "" # 服务器名称将由服务标签填充
          MULTISITE: "yes" # autoconf 的强制设置
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置更强的密码
        volumes:
          - bw-storage:/data # 用于持久化缓存和备份等其他数据
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          AUTOCONF_MODE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # 记得为数据库设置更强的密码
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
          MYSQL_PASSWORD: "changeme" # 记得为数据库设置更强的密码
        volumes:
          - bw-data:/var/lib/mysql
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
      bw-docker:
        name: bw-docker
    ```

    现在您可以创建您的 PHP-FPM 容器，挂载正确的子文件夹并使用标签来配置 BunkerWeb：

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.REMOTE_PHP=myapp1"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.REMOTE_PHP=myapp2"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          labels:
            - "bunkerweb.SERVER_NAME=app3.example.com"
            - "bunkerweb.REMOTE_PHP=myapp3"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! warning "Kubernetes 不支持 PHP"
        Kubernetes 集成允许通过 [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) 进行配置，而 BunkerWeb 控制器目前仅支持 HTTP 应用程序。

=== "Linux"

    我们将假设您已经在您的机器上运行了 [Linux 集成](integrations.md#linux)堆栈。

    默认情况下，BunkerWeb 将在 `/var/www/html` 文件夹内搜索 Web 文件。您可以用它来存储您的 PHP 应用程序。请注意，您需要配置您的 PHP-FPM 服务来获取或设置运行进程的用户/组以及用于与 BunkerWeb 通信的 UNIX 套接字文件。

    首先，您需要确保您的 PHP-FPM 实例可以访问 `/var/www/html` 文件夹内的文件，并且 BunkerWeb 可以访问 UNIX 套接字文件以便与 PHP-FPM 通信。我们建议为 PHP-FPM 服务设置一个不同的用户，如 `www-data`，并给予 nginx 组访问 UNIX 套接字文件的权限。以下是相应的 PHP-FPM 配置：

    ```ini
    ...
    [www]
    user = www-data
    group = www-data
    listen = /run/php/php-fpm.sock
    listen.owner = www-data
    listen.group = nginx
    listen.mode = 0660
    ...
    ```

    不要忘记重启您的 PHP-FPM 服务：

    ```shell
    systemctl restart php-fpm
    ```

    如果您启用[多站点模式](concepts.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

    ```
    /var/www/html
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    请注意，您需要修复权限，以便 BunkerWeb（`nginx` 组）至少可以读取文件和列出文件夹，而 PHP-FPM（`www-data` 用户，但这可能因您的系统而异）是文件和文件夹的所有者：

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    现在您可以编辑 `/etc/bunkerweb/variable.env` 文件：

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    现在让我们检查调度程序的状态：

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    如果它们已经在运行，我们可以重新加载它：

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "已弃用"
        Swarm 集成已弃用，并将在未来版本中删除。请考虑改用 [Kubernetes 集成](integrations.md#kubernetes)。

        **更多信息可以在 [Swarm 集成文档](integrations.md#swarm)中找到。**

    !!! info "已启用多站点模式"
        [Swarm 集成](integrations.md#docker-autoconf)意味着使用多站点模式：保护一个 PHP 应用程序与保护多个应用程序相同。

    !!! info "共享卷"
        在 Docker Swarm 集成中使用 PHP 需要在所有 BunkerWeb 和 PHP-FPM 实例之间共享一个卷，这不在本文档的讨论范围之内。

    当使用 [Swarm](integrations.md#swarm)时，要支持 PHP 应用程序，您需要：

    - 将您的 PHP 文件挂载到 BunkerWeb 的 `/var/www/html` 文件夹中
    - 为您的应用程序设置 PHP-FPM 容器，并挂载包含 PHP 应用程序的文件夹
    - 使用特定的设置 `REMOTE_PHP` 和 `REMOTE_PHP_PATH` 作为您的 PHP-FPM 容器的标签

    由于 Swarm 集成意味着使用[多站点模式](concepts.md#multisite-mode)，您需要为每个应用程序创建单独的目录。每个子目录应使用 `SERVER_NAME` 的第一个值来命名。这是一个示例：

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directories, 3 files
    ```

    作为一个例子，我们将假设您有一个共享文件夹挂载在您的工作节点上的 `/shared` 端点。

    创建文件夹后，复制您的文件并修复权限，以便 BunkerWeb (UID/GID 101) 至少可以读取文件和列出文件夹，而 PHP-FPM (UID/GID 33，如果您使用 `php:fpm` 镜像) 是文件和文件夹的所有者：

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

    当您启动 BunkerWeb 堆栈时，将 `/shared/www` 文件夹挂载到 **Scheduler** 容器的 `/var/www/html` 中：

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    现在您可以创建您的 PHP-FPM 服务，挂载正确的子文件夹并使用标签来配置 BunkerWeb：

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app1.example.com"
              - "bunkerweb.REMOTE_PHP=myapp1"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app2.example.com"
              - "bunkerweb.REMOTE_PHP=myapp2"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app3.example.com"
              - "bunkerweb.REMOTE_PHP=myapp3"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

### IPv6

!!! example "实验性功能"

    此功能尚未准备好用于生产。欢迎您进行测试，并通过 GitHub 仓库中的 [issues](https://github.com/bunkerity/bunkerweb/issues) 向我们报告任何错误。

默认情况下，BunkerWeb 只会监听 IPv4 地址，不会使用 IPv6 进行网络通信。如果您想启用 IPv6 支持，需要将 `USE_IPV6=yes`。请注意，您的网络和环境的 IPv6 配置超出了本文档的范围。

=== "Docker / Autoconf / Swarm"

    首先，您需要配置您的 Docker 守护进程以启用容器的 IPv6 支持，并在需要时使用 ip6tables。这是您 `/etc/docker/daemon.json` 文件的示例配置：

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    现在您可以重启 Docker 服务以应用更改：

    ```shell
    systemctl restart docker
    ```

    一旦 Docker 设置好支持 IPv6，您就可以添加 `USE_IPV6` 设置并为 `bw-services` 配置 IPv6：

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5
        environment:
          USE_IPv6: "yes"

    ...

    networks:
      bw-services:
        name: bw-services
        enable_ipv6: true
        ipam:
          config:
            - subnet: fd00:13:37::/48
              gateway: fd00:13:37::1

    ...
    ```

=== "Linux"

    您需要将设置添加到 `/etc/bunkerweb/variables.env` 文件中：

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

    让我们检查 BunkerWeb 的状态：

    ```shell
    systemctl status bunkerweb
    ```

    如果它们已经在运行，我们可以重启它：

    ```shell
    systemctl restart bunkerweb
    ```

    否则，我们需要启动它：

    ```shell
    systemctl start bunkerweb
    ```

### Docker 日志记录最佳实践

使用 Docker 时，管理容器日志以防止其占用过多磁盘空间非常重要。默认情况下，Docker 使用 `json-file` 日志记录驱动程序，如果未进行配置，可能会导致日志文件非常大。

为避免这种情况，您可以配置日志轮换。这可以在您的 `docker-compose.yml` 文件中为特定服务配置，也可以为 Docker 守护进程全局配置。

**按服务配置**

您可以在 `docker-compose.yml` 文件中为您的服务配置日志记录驱动程序以自动轮换日志。以下是一个示例，最多保留 10 个每个 20MB 的日志文件：

```yaml
services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.5
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "10"
    ...
```

此配置可确保日志轮换，防止它们占满您的磁盘。您可以将其应用于 Docker Compose 设置中的任何服务。

**全局配置 (daemon.json)**

如果您想默认将这些日志记录设置应用于主机上的所有容器，您可以通过编辑（或创建）`/etc/docker/daemon.json` 文件来配置 Docker 守护进程：

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "10"
  }
}
```

修改 `daemon.json` 后，您需要重新启动 Docker 守护进程才能使更改生效：

```shell
sudo systemctl restart docker
```

此全局配置将由所有容器继承。但是，在 `docker-compose.yml` 文件中按服务定义的任何日志记录配置都将覆盖 `daemon.json` 中的全局设置。

## 安全性调整 {#security-tuning}

BunkerWeb 提供了许多安全功能，您可以通过[功能](features.md)进行配置。尽管设置的默认值确保了最低限度的“默认安全”，我们强烈建议您对它们进行调整。这样做，您不仅能够确保您所选择的安全级别，还能管理误报。

!!! tip "其他功能"
    本节仅关注安全调整，有关其他设置，请参阅文档的[功能](features.md)部分。

<figure markdown>
  ![概述](assets/img/core-order.svg){ align=center }
  <figcaption>核心安全插件的概述和顺序</figcaption>
</figure>

## CrowdSec 控制台集成

如果您还不熟悉 CrowdSec 控制台集成，[CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) 利用众包情报来对抗网络威胁。可以把它想象成“网络安全界的 Waze”——当一台服务器受到攻击时，全球其他系统都会收到警报，并受到保护，免受同一攻击者的侵害。您可以在[这里](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog)了解更多信息。

**恭喜，您的 BunkerWeb 实例现已注册到您的 CrowdSec 控制台！**

专业提示：查看警报时，点击“列”选项并勾选“上下文”复选框，以访问 BunkerWeb 特定的数据。

<figure markdown>
  ![概述](assets/img/crowdity4.png){ align=center }
  <figcaption>在上下文列中显示的 BunkerWeb 数据</figcaption>
</figure>

## 监控和报告

#### 监控 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

监控插件让您可以收集和检索关于 BunkerWeb 的指标。启用它后，您的实例将开始收集与攻击、请求和性能相关的各种数据。然后，您可以通过定期调用 `/monitoring` API 端点或使用其他插件（如 Prometheus 导出器）来检索它们。

**功能列表**

- 启用各种 BunkerWeb 指标的收集
- 从 API 检索指标
- 与其他插件结合使用（例如 Prometheus 导出器）
- 专用 UI 页面监控您的实例

**设置列表**

| 设置                           | 默认  | 上下文 | 多个 | 描述                         |
| ------------------------------ | ----- | ------ | ---- | ---------------------------- |
| `USE_MONITORING`               | `yes` | 全局   | 否   | 启用 BunkerWeb 的监控。      |
| `MONITORING_METRICS_DICT_SIZE` | `10M` | 全局   | 否   | 用于存储监控指标的字典大小。 |

#### Prometheus 导出器 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

Prometheus 导出器插件在您的 BunkerWeb 实例上添加了一个 [Prometheus 导出器](https://prometheus.io/docs/instrumenting/exporters/)。启用后，您可以配置您的 Prometheus 实例来抓取 BunkerWeb 上的特定端点并收集内部指标。

我们还提供了一个 [Grafana 仪表板](https://grafana.com/grafana/dashboards/20755-bunkerweb/)，您可以将其导入到自己的实例中，并连接到您自己的 Prometheus 数据源。

**请注意，使用 Prometheus 导出器插件需要启用监控插件 (`USE_MONITORING=yes`)**

**功能列表**

- 提供内部 BunkerWeb 指标的 Prometheus 导出器
- 专用且可配置的端口、监听 IP 和 URL
- 白名单 IP/网络以实现最高安全性

**设置列表**

| 设置                           | 默认                                                  | 上下文 | 多个 | 描述                                           |
| ------------------------------ | ----------------------------------------------------- | ------ | ---- | ---------------------------------------------- |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | 全局   | 否   | 启用 Prometheus 导出。                         |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | 全局   | 否   | Prometheus 导出器的监听 IP。                   |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | 全局   | 否   | Prometheus 导出器的监听端口。                  |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | 全局   | 否   | Prometheus 导出器的 HTTP URL。                 |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | 全局   | 否   | 允许联系 Prometheus 导出器端点的 IP/网络列表。 |

#### 报告 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

!!! warning "需要监控插件"
    此插件需要安装并启用监控专业版插件，并且 `USE_MONITORING` 设置为 `yes`。

报告插件提供了一个全面的解决方案，用于定期报告 BunkerWeb 的重要数据，包括全局统计、攻击、封禁、请求、原因和 AS 信息。它提供了广泛的功能，包括自动报告创建、自定义选项以及与监控专业版插件的无缝集成。使用报告插件，您可以轻松生成和管理报告，以监控应用程序的性能和安全性。

**功能列表**

- 定期报告 BunkerWeb 的重要数据，包括全局统计、攻击、封禁、请求、原因和 AS 信息。
- 与监控专业版插件集成，实现无缝集成和增强的报告功能。
- 支持 webhooks（经典、Discord 和 Slack）以进行实时通知。
- 支持 SMTP 以进行电子邮件通知。
- 用于自定义和灵活性的配置选项。

**设置列表**

| 设置                           | 默认               | 上下文 | 描述                                                                         |
| ------------------------------ | ------------------ | ------ | ---------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | 全局   | 启用通过电子邮件发送报告。                                                   |
| `USE_REPORTING_WEBHOOK`        | `no`               | 全局   | 启用通过 webhook 发送报告。                                                  |
| `REPORTING_SCHEDULE`           | `weekly`           | 全局   | 发送报告的频率。                                                             |
| `REPORTING_WEBHOOK_URLS`       |                    | 全局   | 用于接收 Markdown 格式报告的 webhook URL 列表（以空格分隔）。                |
| `REPORTING_SMTP_EMAILS`        |                    | 全局   | 用于接收 HTML 格式报告的电子邮件地址列表（以空格分隔）。                     |
| `REPORTING_SMTP_HOST`          |                    | 全局   | 用于 SMTP 发送的主机服务器。                                                 |
| `REPORTING_SMTP_PORT`          | `465`              | 全局   | 用于 SMTP 的端口。请注意，根据连接类型有不同的标准（SSL = 465，TLS = 587）。 |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | 全局   | 用作发件人的电子邮件地址。请注意，此电子邮件地址必须禁用 2FA。               |
| `REPORTING_SMTP_FROM_USER`     |                    | 全局   | 通过发件人电子邮件地址发送的用户身份验证值。                                 |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | 全局   | 通过发件人电子邮件地址发送的密码身份验证值。                                 |
| `REPORTING_SMTP_SSL`           | `SSL`              | 全局   | 确定是否为 SMTP 使用安全连接。                                               |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | 全局   | 电子邮件的主题行。                                                           |

!!! info "信息和行为"
    - 如果 `USE_REPORTING_SMTP` 设置为 `yes`，则必须设置 `REPORTING_SMTP_EMAILS`。
    - 如果 `USE_REPORTING_WEBHOOK` 设置为 `yes`，则必须设置 `REPORTING_WEBHOOK_URLS`。
    - `REPORTING_SCHEDULE` 接受的值为 `daily`、`weekly` 和 `monthly`。
    - 如果未设置 `REPORTING_SMTP_FROM_USER` 和 `REPORTING_SMTP_FROM_PASSWORD`，插件将尝试在没有身份验证的情况下发送电子邮件。
    - 如果未设置 `REPORTING_SMTP_FROM_USER` 但设置了 `REPORTING_SMTP_FROM_PASSWORD`，插件将使用 `REPORTING_SMTP_FROM_EMAIL` 作为用户名。
    - 如果作业失败，插件将在下一次执行中重试发送报告。

### 备份和恢复

#### S3 备份 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :white_check_mark:

S3 备份工具可以无缝地自动化数据保护，类似于社区备份插件。然而，它的突出之处在于将备份直接安全地存储在 S3 存储桶中。

通过激活此功能，您正在主动保护您的**数据完整性**。将备份**远程**存储可以保护关键信息免受**硬件故障**、**网络攻击**或**自然灾害**等威胁。这确保了**安全**和**可用性**，能够在**意外事件**期间快速恢复，维护**运营连续性**，并确保**高枕无忧**。

??? warning "给红帽企业 Linux (RHEL) 8.9 用户的信息"
    如果您正在使用 **RHEL 8.9** 并计划使用**外部数据库**，您需要安装 `mysql-community-client` 包以确保 `mysqldump` 命令可用。您可以通过执行以下命令来安装该包：

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

        1.  **安装 PostgreSQL 仓库配置包**

            ```bash
            dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
            ```

        2.  **安装 PostgreSQL 客户端**

            ```bash
            dnf install postgresql<version>
            ```

**功能列表**

- 自动将数据备份到 S3 存储桶
- 灵活的调度选项：每日、每周或每月
- 轮换管理，用于控制要保留的备份数量
- 可自定义的备份文件压缩级别

**设置列表**

| 设置                          | 默认    | 上下文 | 描述                    |
| ----------------------------- | ------- | ------ | ----------------------- |
| `USE_BACKUP_S3`               | `no`    | 全局   | 启用或禁用 S3 备份功能  |
| `BACKUP_S3_SCHEDULE`          | `daily` | 全局   | 备份频率                |
| `BACKUP_S3_ROTATION`          | `7`     | 全局   | 要保留的备份数量        |
| `BACKUP_S3_ENDPOINT`          |         | 全局   | S3 端点                 |
| `BACKUP_S3_BUCKET`            |         | 全局   | S3 存储桶               |
| `BACKUP_S3_DIR`               |         | 全局   | S3 目录                 |
| `BACKUP_S3_REGION`            |         | 全局   | S3 区域                 |
| `BACKUP_S3_ACCESS_KEY_ID`     |         | 全局   | S3 访问密钥 ID          |
| `BACKUP_S3_ACCESS_KEY_SECRET` |         | 全局   | S3 访问密钥 Secret      |
| `BACKUP_S3_COMP_LEVEL`        | `6`     | 全局   | 备份 zip 文件的压缩级别 |

##### 手动备份

要手动启动备份，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

此命令将创建您的数据库备份，并将其存储在 `BACKUP_S3_BUCKET` 设置中指定的 S3 存储桶中。

您还可以在执行命令时通过提供 `BACKUP_S3_BUCKET` 环境变量来为备份指定自定义 S3 存储桶：

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "MariaDB/MySQL 的特别说明"

    如果您正在使用 MariaDB/MySQL，在尝试备份数据库时可能会遇到以下错误：

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    要解决此问题，您可以执行以下命令将身份验证插件更改为 `mysql_native_password`：

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    如果您正在使用 Docker 集成，可以将以下命令添加到 `docker-compose.yml` 文件中，以自动更改身份验证插件：

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

##### 手动恢复

要手动启动恢复，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

此命令将在 `BACKUP_S3_BUCKET` 设置中指定的 S3 存储桶中创建您数据库的临时备份，并将您的数据库恢复到存储桶中可用的最新备份。

您还可以在执行命令时通过提供备份文件的路径作为参数来为恢复指定自定义备份文件：

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "如果失败"

    如果恢复失败，请不要担心，您可以随时通过再次执行命令将数据库恢复到先前的状态，因为在恢复之前会创建一个备份：

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

### 迁移 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :white_check_mark:

迁移插件通过其**用户友好的 Web 界面**，彻底改变了 BunkerWeb 实例之间的配置传输，简化了整个迁移过程。无论您是升级系统、扩展基础设施还是转换环境，此工具都能让您轻松自信地传输**设置、首选项和数据**。告别繁琐的手动流程，迎接**无缝、无忧的迁移体验**。

**功能列表**

- **轻松迁移：** 轻松在实例之间传输 BunkerWeb 配置，无需复杂的手动操作。

- **直观的 Web 界面：** 通过为直观操作设计的用户友好 Web 界面，轻松导航迁移过程。

- **跨数据库兼容性：** 在各种数据库平台之间实现无缝迁移，包括 SQLite、MySQL、MariaDB 和 PostgreSQL，确保与您首选的数据库环境兼容。

#### 创建迁移文件

要手动创建迁移文件，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin migration create /path/to/migration/file
    ```

=== "Docker"

    1.  创建迁移文件：

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /path/to/migration/file
        ```

    2.  将迁移文件复制到您的本地计算机：

        ```bash
        docker cp <scheduler_container>:/path/to/migration/file /path/to/migration/file
        ```

此命令将创建您的数据库备份，并将其存储在命令中指定的备份目录中。

!!! note "MariaDB/MySQL 的特别说明"

    如果您正在使用 MariaDB/MySQL，在尝试备份数据库时可能会遇到以下错误：

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    要解决此问题，您可以执行以下命令将身份验证插件更改为 `mysql_native_password`：

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    如果您正在使用 Docker 集成，可以将以下命令添加到 `docker-compose.yml` 文件中，以自动更改身份验证插件：

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

#### 初始化迁移

要手动初始化迁移，请执行以下命令：

=== "Linux"

    ```bash
    bwcli plugin migration migrate /path/to/migration/file
    ```

=== "Docker"

    1.  将迁移文件复制到容器中：

        ```bash
        docker cp /path/to/migration/file <scheduler_container>:/path/to/migration/file
        ```

    2.  初始化迁移：

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /path/to/migration/file
        ```

=== "All-in-one"

    1.  将迁移文件复制到容器中：

        ```bash
        docker cp /path/to/migration/file bunkerweb-aio:/path/to/migration/file
        ```

    2.  初始化迁移：

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /path/to/migration/file
        ```

此命令将您的 BunkerWeb 数据无缝迁移，以精确匹配迁移文件中概述的配置。

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

STREAM 支持 :x:

**Anti DDoS** 插件通过实时监控、分析和过滤可疑流量，提供针对分布式拒绝服务 (DDoS) 攻击的高级保护。

通过采用**滑动窗口机制**，该插件在内存中维护一个请求时间戳字典，以检测来自单个 IP 地址的异常流量峰值。根据配置的安全模式，它可以阻止违规连接或记录可疑活动以供进一步审查。

#### 功能

- **实时流量分析：** 持续监控传入请求以检测潜在的 DDoS 攻击。
- **滑动窗口机制：** 在可配置的时间窗口内跟踪最近的请求活动。
- **可配置的阈值：** 允许您定义每个 IP 的最大可疑请求数。
- **高级阻止逻辑：** 评估每个 IP 的请求计数和超过阈值的不同 IP 数量。
- **灵活的安全模式：** 在立即阻止连接或仅检测（记录）模式之间进行选择。
- **优化的内存数据存储：** 确保高速查找和高效的指标跟踪。
- **自动清理：** 定期清除过时数据以保持最佳性能。

#### 配置

使用以下设置自定义插件行为：

| 设置                         | 默认          | 上下文 | 多个 | 描述                                                            |
| ---------------------------- | ------------- | ------ | ---- | --------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | 全局   | 否   | 启用或禁用 Anti DDoS 保护。设置为 `"yes"` 以激活插件。          |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | 全局   | 否   | 用于跟踪 DDoS 指标的内存数据存储的大小（例如，`10M`, `500k`）。 |
| `ANTIDDOS_THRESHOLD`         | `100`         | 全局   | 否   | 在定义的时间窗口内，每个 IP 允许的最大可疑请求数。              |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | 全局   | 否   | 统计可疑请求的时间窗口（秒）。                                  |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | 全局   | 否   | 被认为是可疑并用于触发反 DDoS 操作的 HTTP 状态码。              |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | 全局   | 否   | 在强制执行阻止模式之前，必须超过阈值的最少不同 IP 数量。        |

#### 最佳实践

- **阈值调整：** 根据您的典型流量模式调整 `ANTIDDOS_THRESHOLD` 和 `ANTIDDOS_WINDOW_TIME`。
- **状态码审查：** 定期更新 `ANTIDDOS_STATUS_CODES` 以捕获新的或不断演变的可疑行为。
- **监控：** 定期分析日志和指标以微调设置并提高整体保护。

## 用户管理器 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="用户管理器页面" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

用户管理插件提供了一个强大的界面，用于管理系统内的用户帐户。

借助此插件，管理员可以轻松创建、更新和禁用用户帐户，管理用户角色，切换双因素身份验证 (2FA)，并查看详细的用户信息，例如上次登录时间戳和帐户状态（活动或非活动）。该插件在设计时考虑了安全性和易用性，简化了常规的用户管理任务，同时确保了合规性和可审计性。

#### 功能

- **用户帐户操作：** 支持以 CSV/XSLX 格式导入，轻松创建、编辑和删除用户帐户。
- **基于角色的访问控制：** 分配和修改用户角色以管理权限和访问级别。
- **2FA 管理：** 根据管理决策禁用双因素身份验证。
- **全面的用户洞察：** 监控关键用户数据，包括上次登录时间、帐户创建日期以及活动/非活动状态。
- **审计日志记录：** 维护所有用户管理操作的审计跟踪，以增强安全性和合规性。

<figure markdown>
  ![概述](assets/img/user-manager.png){ align=center }
  <figcaption>用户管理器页面</figcaption>
</figure>

<figure markdown>
  ![创建用户表单](assets/img/user-manager-create.png){ align=center }
  <figcaption>用户管理器 - 创建用户表单</figcaption>
</figure>

<figure markdown>
  ![活动页面](assets/img/user-manager-activities.png){ align=center }
  <figcaption>用户管理器 - 活动页面</figcaption>
</figure>

## 轻松解决 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

轻松解决插件让您可以直接从报告页面快速修复误报和重复出现的问题。它将引导式的“解决”操作转化为安全、范围受限的配置更新——无需手动编辑。

#### 功能

- 从报告和报告详情中一键操作。
- 针对 ModSecurity、黑名单和 DNSBL 的上下文感知建议。
- 生成安全的 ModSecurity 排除规则或更新忽略列表。
- 在服务或全局范围内应用更改，并进行权限检查。
- 应用后可选择自动打开相关配置页面。

<figure markdown>
  ![概述](assets/img/easy-resolve.png){ align=center }
  <figcaption>报告页面 - 带有轻松解决功能</figcaption>
</figure>

<div class="grid grid-2" markdown>
<figure markdown>
  ![ModSecurity 解决](assets/img/easy-resolve-modsecurity.png){ width="100%" }
  <figcaption>ModSecurity 解决</figcaption>
</figure>
<figure markdown>
  ![DNSBL 解决](assets/img/easy-resolve-dnsbl.png){ width="100%" }
  <figcaption>DNSBL 解决</figcaption>
</figure>
</div>

<div class="grid grid-5" markdown>
<figure markdown>
  ![黑名单解决 - IP](assets/img/easy-resolve-blacklist-ip.png){ width="100%" }
  <figcaption>黑名单 - IP</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - User-Agent](assets/img/easy-resolve-blacklist-ua.png){ width="100%" }
  <figcaption>黑名单 - User-Agent</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - rDNS](assets/img/easy-resolve-blacklist-rdns.png){ width="100%" }
  <figcaption>黑名单 - rDNS</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - ASN](assets/img/easy-resolve-blacklist-asn.png){ width="100%" }
  <figcaption>黑名单 - ASN</figcaption>
</figure>
<figure markdown>
  ![黑名单解决 - URI](assets/img/easy-resolve-blacklist-uri.png){ width="100%" }
  <figcaption>黑名单 - URI</figcaption>
</figure>
</div>
