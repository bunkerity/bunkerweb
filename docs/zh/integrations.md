# 集成

## BunkerWeb 云

<figure markdown>
  ![概述](assets/img/bunkerweb-cloud.png){ align=center, width="600" }
  <figcaption>BunkerWeb 云</figcaption>
</figure>

BunkerWeb Cloud 是一种托管的 Web 应用程序防火墙 (WAF) 和反向代理解决方案，使您无需在基础设施中安装 BunkerWeb 即可保护您的 Web 应用程序。通过订阅 BunkerWeb Cloud，您将受益于托管在云端的完整 BunkerWeb 堆栈，并拥有专用资源（8GB RAM，**每**实例 2 CPU，跨 2 个实例复制以实现高可用性，标准版）。

### 主要优势

订购您的 [BunkerWeb Cloud 实例](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc)并获得：

- **即时部署**：无需在您的基础设施中进行安装
- **高可用性**：具有自动负载均衡的复制实例
- **集成监控**：访问 Grafana 以进行日志和指标可视化
- **可扩展性**：适应繁重工作负载的专用资源
- **增强的安全性**：针对 Web 威胁的实时 WAF 保护

如果您对 BunkerWeb Cloud 服务感兴趣，请随时[联系我们](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc)，以便我们讨论您的需求。

### 架构概述

#### 简单架构 - 单一服务

```mermaid
graph LR
    A[客户端] -->|HTTPS| B[example.com]
    B -->|DNS 解析| C[负载均衡器54984654.bunkerweb.cloud]
    C -->|流量| D[BunkerWeb CloudWAF + 反向代理]
    D -->|HTTPS/HTTP| E[服务器 example.com客户端基础设施]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#e8f5e8,color:#222
```

#### 复杂架构 - 多服务

```mermaid
graph LR
    A[客户端] -->|HTTPS| B[example.comother-example.coman-other-example.com]
    B -->|DNS 解析| C[负载均衡器54984654.bunkerweb.cloud]
    C -->|流量| D[BunkerWeb CloudWAF + 反向代理SSL SNI 已启用]
    D -->|带 SNI 的 HTTPS| E[客户端网关反向代理/LB]
    E -->|内部路由| F[服务 1]
    E -->|内部路由| G[服务 2]
    E -->|内部路由| H[服务 N]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#fff3e0,color:#222
    style F fill:#e8f5e8,color:#222
    style G fill:#e8f5e8,color:#222
    style H fill:#e8f5e8,color:#222
```

### 初始配置

#### 1. 管理界面访问

订阅 BunkerWeb Cloud 后，您将收到：

- **BunkerWeb UI 访问 URL**：用于配置服务的界面
- **负载均衡器端点**：格式为 `http://[ID].bunkerweb.cloud` 的唯一 URL
- **Grafana 访问权限**：监控界面和指标可视化
- **分配的资源**：2 个实例，每个实例 8GB RAM 和 2 CPU

#### 2. 首次连接

1. 连接到 BunkerWeb Cloud 界面
2. 配置要保护的服务
3. 访问 Grafana 以可视化您的 BunkerWeb 日志和指标

### DNS 配置

#### 流量重定向到 BunkerWeb Cloud

为了使您的域流量由 BunkerWeb Cloud 处理，您必须配置 DNS 记录：

**所需配置：**

```dns
example.com.        IN  CNAME  54984654.bunkerweb.cloud.
www.example.com.    IN  CNAME  54984654.bunkerweb.cloud.
```

**重要提示：** 将 `54984654` 替换为您在订阅期间提供的负载均衡器标识符。

#### 配置验证

验证 DNS 解析：

```bash
dig example.com
nslookup example.com
```

结果应指向您的 BunkerWeb Cloud 端点。

### 服务配置

#### 单一服务

对于托管在您基础设施上的简单服务：

**在 BunkerWeb UI 中的配置：**

1. **Server Name**：`example.com`
2. **Use Reverse Proxy**：`yes`
3. **Reverse Proxy Host**：`185.87.1.100:443`（您的服务器 IP）

您可以在[反向代理文档](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)中找到所有配置选项

#### 带 SNI 的多服务

##### 为什么要启用 SNI？

当出现以下情况时，服务器名称指示 (SNI) 是**必不可少**的：

- 多个域指向同一个后端基础设施
- 您的基础设施托管多个具有不同 SSL 证书的服务
- 您在客户端使用了反向代理/网关

##### SNI 配置

**在 BunkerWeb UI 中，针对每个服务：**

```yaml
# 服务 1
SERVICE_NAME: example-com
SERVER_NAME: example.com
REVERSE_PROXY_HOST: https://gateway.internal.domain.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: example.com

# 服务 2
SERVICE_NAME: other-example-com
SERVER_NAME: other-example.com
REVERSE_PROXY_HOST: https://gateway.internal.domain.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: other-example.com
```

您可以在[反向代理文档](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)中找到所有配置选项

##### SNI 技术细节

SNI 允许 BunkerWeb Cloud：

1. 在 TLS 连接期间**识别目标服务**
2. **将正确的域名传输**到后端
3. **允许客户端网关**选择正确的证书
4. **正确路由**到适当的服务

**未启用 SNI：**

```mermaid
graph LR
    A[客户端] --> B[BunkerWeb]
    B --> C["网关 (默认证书)"]
    C --> D[SSL 错误]

    style B fill:#f3e5f5,color:#222
    style C fill:#fff3e0,color:#222
    style D fill:#ff4d4d,color:#fff,stroke:#b30000,stroke-width:2px
```

**已启用 SNI：**

```mermaid
graph LR
    A[客户端] --> B[BunkerWeb]
    B --> C["网关 (example.com 特定证书)"]
    C --> D[正确服务]

    style B fill:#f3e5f5,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
```

### SSL/TLS 和 SNI 管理

#### SSL 证书

##### BunkerWeb Cloud 侧

BunkerWeb Cloud 自动管理：

- 您的域的 Let's Encrypt 证书
- 自动续订
- 优化的 TLS 配置

##### 客户端基础设施侧

**重要建议：**

1. **使用 HTTPS** 进行 BunkerWeb 与您的服务之间的通信
2. **管理您自己的证书**在您的基础设施上
3. **正确配置 SNI**在您的网关/反向代理上

#### 详细的 SNI 配置

##### 用例：带网关的基础设施

如果您的架构如下所示：

```mermaid
graph LR
    A[BunkerWeb Cloud] --> B[客户端网关]
    B --> C[服务 1]
    B --> D[服务 2]
    B --> E[服务 3]

    style A fill:#f3e5f5,color:#222
    style B fill:#fff3e0,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
    style E fill:#e8f5e8,color:#222
```

**BunkerWeb 侧所需的配置：**

```yaml
# example.com 的配置
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: example.com
REVERSE_PROXY_SSL_VERIFY: no  # 如果客户端是自签名证书
REVERSE_PROXY_HEADERS: Host $host

# api.example.com 的配置
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: api.example.com
REVERSE_PROXY_SSL_VERIFY: no
REVERSE_PROXY_HEADERS: Host $host
```

### 客户端网关配置

#### 概述

当您的架构使用客户端的网关/反向代理将流量路由到多个服务时，需要特定的配置来支持 SNI 并确保与 BunkerWeb Cloud 的安全通信。

#### 按技术分类的配置

##### Nginx

<details>
<summary>Nginx 配置</summary>

```nginx
# 支持多服务 SNI 的配置
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /path/to/example.com.crt;
    ssl_certificate_key /path/to/example.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # 安全标头
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://service1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Server $host;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /path/to/api.example.com.crt;
    ssl_certificate_key /path/to/api.example.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://api-service:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # API 特定配置
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

</details>

##### Traefik

<details>
<summary>Traefik 配置</summary>

**使用 Docker Compose：**

```yaml
services:
  traefik:
    image: traefik:v3.0
    command:
      - --api.dashboard=true
      - --providers.docker=true
      - --providers.file.filename=/etc/traefik/dynamic.yml
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.myresolver.acme.tlschallenge=true
      - --certificatesresolvers.myresolver.acme.email=admin@example.com
      - --certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json
    ports:
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
      - ./dynamic.yml:/etc/traefik/dynamic.yml:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.example.com`)"
      - "traefik.http.routers.dashboard.tls.certresolver=myresolver"

  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`example.com`)"
      - "traefik.http.routers.service1.entrypoints=websecure"
      - "traefik.http.routers.service1.tls.certresolver=myresolver"
      - "traefik.http.services.service1.loadbalancer.server.port=8080"
      - "traefik.http.routers.service1.middlewares=security-headers"

  api-service:
    image: your-api:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.example.com`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=myresolver"
      - "traefik.http.services.api.loadbalancer.server.port=3000"
      - "traefik.http.routers.api.middlewares=security-headers,rate-limit"
```

**动态配置 (dynamic.yml)：**

```yaml
http:
  middlewares:
    security-headers:
      headers:
        frameDeny: true
        contentTypeNosniff: true
        browserXssFilter: true
        forceSTSHeader: true
        stsIncludeSubdomains: true
        stsPreload: true
        stsSeconds: 31536000
        customRequestHeaders:
          X-Forwarded-Proto: "https"

    rate-limit:
      rateLimit:
        burst: 100
        average: 50

  routers:
    service1:
      rule: "Host(`example.com`)"
      service: "service1"
      tls:
        certResolver: "myresolver"
      middlewares:
        - "security-headers"

    api:
      rule: "Host(`api.example.com`)"
      service: "api-service"
      tls:
        certResolver: "myresolver"
      middlewares:
        - "security-headers"
        - "rate-limit"

  services:
    service1:
      loadBalancer:
        servers:
          - url: "http://service1:8080"
        healthCheck:
          path: "/health"
          interval: "30s"

    api-service:
      loadBalancer:
        servers:
          - url: "http://api-service:3000"
        healthCheck:
          path: "/api/health"
          interval: "30s"
```

</details>

##### Apache

<details>
<summary>Apache 配置</summary>

```apache
# 带 SNI 的 Apache 配置
<VirtualHost *:443>
    ServerName example.com
    DocumentRoot /var/www/html

    # SSL 配置
    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLHonorCipherOrder off
    SSLCertificateFile /path/to/example.com.crt
    SSLCertificateKeyFile /path/to/example.com.key

    # 安全标头
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # 反向代理配置
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # 自定义标头
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    <Proxy *>
        Require all granted
    </Proxy>

    # 日志
    ErrorLog ${APACHE_LOG_DIR}/example.com_error.log
    CustomLog ${APACHE_LOG_DIR}/example.com_access.log combined
</VirtualHost>

<VirtualHost *:443>
    ServerName api.example.com

    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLCertificateFile /path/to/api.example.com.crt
    SSLCertificateKeyFile /path/to/api.example.com.key

    ProxyPass / http://api-service:3000/
    ProxyPassReverse / http://api-service:3000/
    ProxyPreserveHost On

    # API 特定配置
    ProxyTimeout 300
    ProxyBadHeader Ignore

    ErrorLog ${APACHE_LOG_DIR}/api.example.com_error.log
    CustomLog ${APACHE_LOG_DIR}/api.example.com_access.log combined
</VirtualHost>

# 所需模块配置
LoadModule ssl_module modules/mod_ssl.so
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
LoadModule headers_module modules/mod_headers.so
```

</details>

##### HAProxy

<details>
<summary>HAProxy 配置</summary>

```haproxy
global
    maxconn 4096
    log stdout local0
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

    # SSL 配置
    ssl-default-bind-ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    option httplog
    option dontlognull
    option redispatch
    retries 3
    maxconn 2000

frontend https_frontend
    bind *:443 ssl crt /etc/ssl/certs/example.com.pem crt /etc/ssl/certs/api.example.com.pem

    # 安全标头
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff
    http-response set-header X-XSS-Protection "1; mode=block"
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # 基于 SNI 的路由
    acl is_example hdr(host) -i example.com
    acl is_api hdr(host) -i api.example.com

    use_backend service1_backend if is_example
    use_backend api_backend if is_api

    default_backend service1_backend

backend service1_backend
    balance roundrobin
    option httpchk GET /health
    http-check expect status 200

    server service1-1 service1:8080 check
    server service1-2 service1-backup:8080 check backup

backend api_backend
    balance roundrobin
    option httpchk GET /api/health
    http-check expect status 200

    server api-1 api-service:3000 check
    server api-2 api-service-backup:3000 check backup

# 统计界面（可选）
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE
```

</details>

#### SSL 配置验证

测试 SSL 配置：

```bash
# SSL 连接测试
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# 标头验证
curl -I https://your-domain.com

# SNI 测试
curl -H "Host: example.com" https://54984654.bunkerweb.cloud
```

#### 网关最佳实践

1. **运行状况检查**：为您的服务配置运行状况检查
2. **负载均衡**：使用多个实例以实现高可用性
3. **监控**：监控您的网关指标
4. **安全标头**：添加适当的安全标头
5. **超时**：配置适当的超时以避免阻塞

### BunkerWeb Cloud IP 白名单

#### 为什么要配置白名单？

为了进一步保护您的基础设施，建议在客户端基础设施侧配置 BunkerWeb Cloud IP 地址的白名单。这确保只有来自 BunkerWeb Cloud 的流量才能到达您的后端服务。

我们建议在防火墙级别（iptables 等）进行白名单设置。

#### 要列入白名单的 BunkerWeb Cloud IP 地址

**允许的 IP 地址列表：**

更新的列表可在此处获得：https://repo.bunkerweb.io/cloud/ips

```
# BunkerWeb Cloud IP 地址
4.233.128.18
20.19.161.132
```

#### 按技术分类的白名单配置

##### Nginx

<details>
<summary>Nginx 配置</summary>

```nginx
# 在您的服务器配置中
server {
    listen 443 ssl;
    server_name example.com;

    # BunkerWeb Cloud IP 白名单
    allow 192.168.1.0/24;
    allow 10.0.0.0/16;
    allow 172.16.0.0/12;
    deny all;

    ssl_certificate /path/to/example.com.crt;
    ssl_certificate_key /path/to/example.com.key;

    location / {
        proxy_pass http://service1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# 使用 geo 模块进行更灵活的配置
geo $bunkerweb_ip {
    default 0;
    192.168.1.0/24 1;
    10.0.0.0/16 1;
    172.16.0.0/12 1;
}

server {
    listen 443 ssl;
    server_name example.com;

    if ($bunkerweb_ip = 0) {
        return 403;
    }

    # ... 其余配置
}
```

</details>

##### Traefik

<details>
<summary>Traefik 配置</summary>

```yaml
# dynamic.yml 中的配置
http:
  middlewares:
    bunkerweb-whitelist:
      ipWhiteList:
        sourceRange:
          - "192.168.1.0/24"
          - "10.0.0.0/16"
          - "172.16.0.0/12"
        ipStrategy:
          depth: 1

  routers:
    example-router:
      rule: "Host(`example.com`)"
      service: "example-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"

    api-router:
      rule: "Host(`api.example.com`)"
      service: "api-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"
```

**使用 Docker Compose 标签：**

```yaml
services:
  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`example.com`)"
      - "traefik.http.routers.service1.middlewares=bunkerweb-whitelist"
      - "traefik.http.middlewares.bunkerweb-whitelist.ipwhitelist.sourcerange=192.168.1.0/24,10.0.0.0/16,172.16.0.0/12"
```

</details>

##### Apache

<details>
<summary>Apache 配置</summary>

```apache
<VirtualHost *:443>
    ServerName example.com

    # BunkerWeb Cloud IP 白名单
    <RequireAll>
        Require ip 192.168.1.0/24
        Require ip 10.0.0.0/16
        Require ip 172.16.0.0/12
    </RequireAll>

    SSLEngine on
    SSLCertificateFile /path/to/example.com.crt
    SSLCertificateKeyFile /path/to/example.com.key

    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # 拒绝访问日志配置
    LogFormat "%h %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined
    CustomLog logs/access.log combined
    ErrorLog logs/error.log
</VirtualHost>

# 使用 mod_authz_core 的替代配置
<VirtualHost *:443>
    ServerName api.example.com

    <Directory />
        <RequireAny>
            Require ip 192.168.1.0/24
            Require ip 10.0.0.0/16
            Require ip 172.16.0.0/12
        </RequireAny>
    </Directory>

    # ... 其余配置
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>HAProxy 配置</summary>

```haproxy
# haproxy.cfg 中的配置
frontend bunkerweb_frontend
    bind *:443 ssl crt /path/to/certificates/

    # BunkerWeb Cloud 白名单 ACL
    acl bunkerweb_ips src 192.168.1.0/24 10.0.0.0/16 172.16.0.0/12

    # 阻止除非是 BunkerWeb Cloud
    http-request deny unless bunkerweb_ips

    # 安全标头
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff

    # 路由
    acl is_example hdr(host) -i example.com
    acl is_api hdr(host) -i api.example.com

    use_backend app_servers if is_example
    use_backend api_servers if is_api

    default_backend app_servers

backend app_servers
    balance roundrobin
    server app1 service1:8080 check
    server app2 service2:8080 check

backend api_servers
    balance roundrobin
    server api1 api-service:3000 check
    server api2 api-service-backup:3000 check
```

</details>

##### 系统防火墙 (iptables)

<details>
<summary>iptables 配置</summary>

```bash
#!/bin/bash
# BunkerWeb Cloud 白名单的 iptables 配置脚本

# 清除现有规则
iptables -F
iptables -X

# 默认策略
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# 允许环回
iptables -A INPUT -i lo -j ACCEPT

# 允许已建立的连接
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# HTTPS 允许 BunkerWeb Cloud IP
iptables -A INPUT -p tcp --dport 443 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 10.0.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 172.16.0.0/12 -j ACCEPT

# 允许 HTTP 用于 Let's Encrypt（可选）
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# 允许 SSH（适应您的需求）
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# 调试日志
iptables -A INPUT -j LOG --log-prefix "DROPPED: "

# 保存规则
iptables-save > /etc/iptables/rules.v4

echo "iptables 配置已成功应用"
```

</details>

#### 白名单最佳实践

1. **监控拒绝**：监控被阻止的访问尝试
2. **定期更新**：保持 IP 列表最新
3. **定期测试**：验证白名单是否正常工作
4. **文档**：记录 IP 更改
5. **警报**：配置 BunkerWeb IP 更改的警报
6. **备份**：保留备份配置以防万一

### REAL_IP 配置和客户端地址恢复

#### 为什么要配置 REAL_IP？

当使用 BunkerWeb Cloud 作为反向代理时，您的后端应用程序看到的 IP 地址是 BunkerWeb Cloud 的 IP 地址，而不是真实客户端的 IP 地址。要检索真实的客户端 IP 地址，需要进行特定配置。

#### BunkerWeb Cloud 侧配置

在 BunkerWeb UI 中，配置 Real IP：

```yaml
USE_REAL_IP: yes # 默认为 no
REAL_IP_FROM: 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8 # 默认
REAL_IP_HEADER: X-Forwarded-For # 默认
REAL_IP_RECURSIVE: yes # 默认
# 如果在 BunkerWeb 前面还使用了 Cloudflare 代理的示例
REAL_IP_FROM_URLS: https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/
```

您可以在[Real Ip 文档](https://docs.bunkerweb.io/latest/settings/#real-ip)中找到所有配置选项

#### 客户端基础设施侧配置

##### Nginx

<details>
<summary>Nginx REAL_IP 配置</summary>

```nginx
# 配置受信任的 IP 地址 (BunkerWeb Cloud)
set_real_ip_from 4.233.128.18/32
set_real_ip_from 20.19.161.132/32

# 用于检索真实 IP 的标头
real_ip_header X-Real-IP;

# 使用 X-Forwarded-For 的替代方案
# real_ip_header X-Forwarded-For;

server {
    listen 443 ssl http2;
    server_name example.com;

    # SSL 配置
    ssl_certificate /path/to/example.com.crt;
    ssl_certificate_key /path/to/example.com.key;

    location / {
        proxy_pass http://service1:8080;

        # 将真实 IP 标头转发到后端
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 使用真实客户端 IP 记录日志
        access_log /var/log/nginx/access.log combined;
    }
}

# 带真实 IP 的自定义日志格式
log_format real_ip '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent" '
                   'real_ip="$realip_remote_addr"';
```

</details>

##### Apache

<details>
<summary>Apache REAL_IP 配置</summary>

```apache
# 加载 mod_remoteip 模块
LoadModule remoteip_module modules/mod_remoteip.so

<VirtualHost *:443>
    ServerName example.com

    # SSL 配置
    SSLEngine on
    SSLCertificateFile /path/to/example.com.crt
    SSLCertificateKeyFile /path/to/example.com.key

    # 配置受信任的 IP 地址
    RemoteIPHeader X-Real-IP
    RemoteIPTrustedProxy 4.233.128.18/32
    RemoteIPTrustedProxy 20.19.161.132/32

    # 使用 X-Forwarded-For 的替代方案
    # RemoteIPHeader X-Forwarded-For

    # 反向代理配置
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # 转发 IP 标头
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    # 带真实 IP 的日志
    LogFormat "%a %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined_real_ip
    CustomLog logs/access.log combined_real_ip
    ErrorLog logs/error.log
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>HAProxy REAL_IP 配置</summary>

```haproxy
global
    maxconn 4096
    log stdout local0

defaults
    mode http
    option httplog
    option dontlognull
    option forwardfor

    # 带真实 IP 的日志格式
    log-format "%ci:%cp [%t] %ft %b/%s %Tq/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"

frontend https_frontend
    bind *:443 ssl crt /etc/ssl/certs/

    # BunkerWeb Cloud IP 白名单
    acl bunkerweb_ips src 4.233.128.18/32 20.19.161.132/32
    http-request deny unless bunkerweb_ips

    # 从标头捕获真实 IP
    capture request header X-Real-IP len 15
    capture request header X-Forwarded-For len 50

    # 路由
    acl is_example hdr(host) -i example.com
    use_backend app_servers if is_example

    default_backend app_servers

backend app_servers
    balance roundrobin

    # 添加/保留真实 IP 标头
    http-request set-header X-Original-Forwarded-For %[req.hdr(X-Forwarded-For)]
    http-request set-header X-Client-IP %[req.hdr(X-Real-IP)]

    server app1 service1:8080 check
    server app2 service2:8080 check backup
```

</details>

##### Traefik

<details>
<summary>Traefik REAL_IP 配置</summary>

```yaml
# dynamic.yml 中的配置
http:
  middlewares:
    real-ip:
      ipWhiteList:
        sourceRange:
          - "4.233.128.18/32"
          - "20.19.161.132/32"
        ipStrategy:
          depth: 2  # 受信任代理的数量
          excludedIPs:
            - "127.0.0.1/32"

  routers:
    example-router:
      rule: "Host(`example.com`)"
      service: "example-service"
      middlewares:
        - "real-ip"
      tls:
        certResolver: "myresolver"

  services:
    example-service:
      loadBalancer:
        servers:
          - url: "http://service1:8080"
        passHostHeader: true
```

**traefik.yml (静态) 中的配置：**

```yaml
entryPoints:
  websecure:
    address: ":443"
    forwardedHeaders:
      trustedIPs:
        - "4.233.128.18/32"
        - "20.19.161.132/32"
      insecure: false

accessLog:
  format: json
  fields:
    defaultMode: keep
    names:
      ClientUsername: drop
    headers:
      defaultMode: keep
      names:
        X-Real-IP: keep
        X-Forwarded-For: keep
```

</details>

#### 测试和验证

##### 配置验证

```bash
# 测试 1：检查接收到的标头
curl -H "X-Real-IP: 203.0.113.1" \
     -H "X-Forwarded-For: 203.0.113.1, 192.168.1.100" \
     https://example.com/test-ip

# 测试 2：分析日志
tail -f /var/log/nginx/access.log | grep "203.0.113.1"

# 测试 3：从不同来源测试
curl -v https://example.com/whatismyip
```

#### REAL_IP 最佳实践

1. **安全**：仅信任来自已知来源 (BunkerWeb Cloud) 的 IP 标头
2. **验证**：始终验证标头中接收到的 IP 地址
3. **日志记录**：记录代理 IP 和真实 IP 以进行调试
4. **回退**：如果缺少标头，始终有一个默认值
5. **测试**：定期测试 IP 检测是否正常工作
6. **监控**：监控 IP 模式以检测异常

#### REAL_IP 故障排除

##### 常见问题

1. **IP 总是显示 BunkerWeb 的**：检查受信任代理配置
2. **缺少标头**：检查 BunkerWeb Cloud 侧配置
3. **无效 IP**：实施严格的 IP 验证
4. **日志不正确**：检查日志格式和 real_ip 模块配置

##### 诊断命令

__测试 IP 检测__

```bash
curl -H "X-Real-IP: 1.2.3.4" https://your-domain.com/debug-headers
```

### 监控和可观测性

#### Grafana 访问

您的托管 Grafana 实例使您可以访问：

##### 可用指标

1. **流量概览**

  - 每秒请求数
  - HTTP 状态码
  - 请求地理位置
2. **安全**

  - 被阻止的攻击尝试
  - 检测到的威胁类型
  - 触发的 WAF 规则
3. **性能指标**

  - 请求延迟
  - 后端响应时间
  - 资源利用率

##### 可用日志

1. **访问日志**：所有 HTTP/HTTPS 请求
2. **安全日志**：安全事件和阻止
3. **错误日志**：应用程序和系统错误

##### 警报配置

为以下情况配置 Grafana 警报：

- 异常流量峰值
- 5xx 错误增加
- DDoS 攻击检测
- 后端健康故障

### 最佳实践

#### 安全

1. **使用 HTTPS** 进行所有后端通信
2. **实施 IP 白名单**（如果可能）
3. **配置适当的超时**
4. **启用压缩**以优化性能

#### 性能

1. **优化缓存配置**
2. **使用 HTTP/2** 在客户端
3. **配置运行状况检查** 为您的后端
4. **定期监控指标**

### 故障排除

#### 常见问题

##### 1. SSL/TLS 错误

**症状：** SSL 证书错误

**解决方案：**

```bash
# 检查 SNI 配置
openssl s_client -connect backend.com:443 -servername example.com

# 检查后端证书
openssl x509 -in certificate.crt -text -noout
```

##### 2. 后端超时

**症状：** 504 Gateway Timeout 错误

**解决方案：**

- 增加 `REVERSE_PROXY_CONNECT_TIMEOUT` & `REVERSE_PROXY_SEND_TIMEOUT`
- 检查后端健康状况
- 优化应用程序性能

##### 3. 路由问题

**症状：** 提供错误的服务

**解决方案：**

- 检查 `SERVER_NAME` 配置
- 验证 SNI 配置
- 检查 `Host` 标头

#### 诊断命令

```bash
# 连接测试
curl -v https://your-domain.com

# 使用自定义标头测试
curl -H "Host: example.com" -v https://54984654.bunkerweb.cloud

# DNS 验证
dig +trace example.com

# SSL 测试
openssl s_client -connect example.com:443 -servername example.com
```

#### 技术支持

如需任何技术帮助：

1. **检查日志**在 Grafana 中
2. **验证配置**在 BunkerWeb UI 中
3. **联系支持**并提供配置详细信息和错误日志

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
  bunkerity/bunkerweb-all-in-one:1.6.8-rc1
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
    image: bunkerity/bunkerweb-all-in-one:1.6.8-rc1
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
  bunkerity/bunkerweb-all-in-one:1.6.8-rc1
```

推荐（在 BunkerWeb 之后）— 不要发布 `8888`；而是反向代理它：

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.8-rc1
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
  bunkerity/bunkerweb-all-in-one:1.6.8-rc1
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
  bunkerity/bunkerweb-all-in-one:1.6.8-rc1
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
  bunkerity/bunkerweb-all-in-one:1.6.8-rc1
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
  bunkerity/bunkerweb-all-in-one:1.6.8-rc1
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
docker pull bunkerity/bunkerweb:1.6.8-rc1
```

Docker 镜像也可在 [GitHub packages](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) 上找到，可以使用 `ghcr.io` 仓库地址下载：

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.8-rc1
```

Docker 集成的关键概念包括：

- **环境变量**：使用环境变量轻松配置 BunkerWeb。这些变量允许您自定义 BunkerWeb 行为的各个方面，例如网络设置、安全选项和其他参数。
- **调度器容器**：使用一个名为[调度器](concepts.md#scheduler)的专用容器来管理配置和执行作业。
- **网络**：Docker 网络在 BunkerWeb 的集成中扮演着至关重要的角色。这些网络有两个主要目的：向客户端公开端口以及连接到上游 Web 服务。通过公开端口，BunkerWeb 可以接受来自客户端的传入请求，允许他们访问受保护的 Web 服务。此外，通过连接到上游 Web 服务，BunkerWeb 可以高效地路由和管理流量，提供增强的安全性和性能。

!!! info "数据库后端"
    请注意，我们的说明假设您正在使用 SQLite 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，也支持其他数据库后端。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc1/misc/integrations)中的 docker-compose 文件。

### 环境变量

设置通过 Docker 环境变量传递给调度器：

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.8-rc1
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
docker pull bunkerity/bunkerweb-scheduler:1.6.8-rc1
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
        image: bunkerity/bunkerweb:1.6.8-rc1
        environment:
          # 这将为 BunkerWeb 容器设置 API
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc1
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
    image: bunkerity/bunkerweb-scheduler:1.6.8-rc1
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

### 调度器容器设置

调度器是控制面的 worker，会读取设置、渲染配置并推送到 BunkerWeb 实例。配置在此集中，包含默认值和可接受值。

#### 配置来源与优先级

1. 环境变量（包含 Docker/Compose `environment:`）
2. `/run/secrets/<VAR>` 下的 secrets（由 entrypoint 自动加载）
3. 内置默认值

#### 配置参考（高级用户）

##### 运行时与安全

| Setting                         | 描述                                             | 接受的值                                | 默认值                        |
| ------------------------------- | ------------------------------------------------ | --------------------------------------- | ----------------------------- |
| `HEALTHCHECK_INTERVAL`          | 调度器健康检查的间隔秒数                         | 整秒                                    | `30`                          |
| `RELOAD_MIN_TIMEOUT`            | 连续两次 reload 之间的最小秒数                   | 整秒                                    | `5`                           |
| `DISABLE_CONFIGURATION_TESTING` | 应用前跳过配置测试                               | `yes` 或 `no`                           | `no`                          |
| `IGNORE_FAIL_SENDING_CONFIG`    | 即便部分实例未收到配置也继续                     | `yes` 或 `no`                           | `no`                          |
| `IGNORE_REGEX_CHECK`            | 跳过设置的正则校验（与 autoconf 共享）           | `yes` 或 `no`                           | `no`                          |
| `TZ`                            | 调度器日志、类 cron 任务、备份和时间戳使用的时区 | TZ 数据库名（如 `UTC`、`Europe/Paris`） | unset（容器默认，通常为 UTC） |

##### 数据库

| Setting                 | 描述                                           | 接受的值              | 默认值                                    |
| ----------------------- | ---------------------------------------------- | --------------------- | ----------------------------------------- |
| `DATABASE_URI`          | 主数据库 DSN（与 autoconf 和实例共享）         | SQLAlchemy DSN        | `sqlite:////var/lib/bunkerweb/db.sqlite3` |
| `DATABASE_URI_READONLY` | 可选只读 DSN；若只有它可用，调度器会降级为只读 | SQLAlchemy DSN 或留空 | unset                                     |

##### 日志

| Setting                         | 描述                                                             | 接受的值                                        | 默认值                                                                          |
| ------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | 基础/覆盖日志级别                                                | `debug`, `info`, `warning`, `error`, `critical` | `info`                                                                          |
| `LOG_TYPES`                     | 目标                                                             | 空格分隔 `stderr`/`file`/`syslog`               | `stderr`                                                                        |
| `SCHEDULER_LOG_TO_FILE`         | 启用文件日志并设置默认路径                                       | `yes` 或 `no`                                   | `no`                                                                            |
| `LOG_FILE_PATH`                 | 自定义日志路径（当 `LOG_TYPES` 包含 `file` 时使用）              | 文件路径                                        | `SCHEDULER_LOG_TO_FILE=yes` 时为 `/var/log/bunkerweb/scheduler.log`，否则 unset |
| `LOG_SYSLOG_ADDRESS`            | Syslog 目标（`udp://host:514`、`tcp://host:514` 或 socket 路径） | Host:port、带协议前缀的主机或 socket            | unset                                                                           |
| `LOG_SYSLOG_TAG`                | Syslog 标识/tag                                                  | 字符串                                          | `bw-scheduler`                                                                  |

### UI 容器设置

UI 容器同样遵循 `TZ`，用于本地化日志和计划任务（例如 UI 发起的清理任务）。

| Setting | 描述                    | 接受的值                                | 默认值                        |
| ------- | ----------------------- | --------------------------------------- | ----------------------------- |
| `TZ`    | UI 日志和计划动作的时区 | TZ 数据库名（如 `UTC`、`Europe/Paris`） | unset（容器默认，通常为 UTC） |

#### 日志

| Setting                         | 描述                                                                    | 接受的值                                        | 默认值                                                           |
| ------------------------------- | ----------------------------------------------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | 基础日志级别 / 覆盖                                                     | `debug`, `info`, `warning`, `error`, `critical` | `info`                                                           |
| `LOG_TYPES`                     | 目标                                                                    | 空格分隔的 `stderr`/`file`/`syslog`             | `stderr`                                                         |
| `LOG_FILE_PATH`                 | 文件日志路径（当 `LOG_TYPES` 含 `file` 或 `CAPTURE_OUTPUT=yes` 时使用） | 文件路径                                        | 当启用 file/capture 时为 `/var/log/bunkerweb/ui.log`，否则 unset |
| `LOG_SYSLOG_ADDRESS`            | Syslog 目标（`udp://host:514`、`tcp://host:514`、socket）               | Host:port、带协议前缀的主机或路径               | unset                                                            |
| `LOG_SYSLOG_TAG`                | Syslog 标识/tag                                                         | 字符串                                          | `bw-ui`                                                          |
| `CAPTURE_OUTPUT`                | 将 Gunicorn stdout/stderr 发送到配置的日志输出                          | `yes` 或 `no`                                   | `no`                                                             |

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
    image: bunkerity/bunkerweb:1.6.8-rc1
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
    image: bunkerity/bunkerweb-scheduler:1.6.8-rc1
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
    image: bunkerity/bunkerweb:1.6.8-rc1
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
    image: bunkerity/bunkerweb-scheduler:1.6.8-rc1
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
- Fedora 42 和 43
- Red Hat Enterprise Linux (RHEL) 8, 9 和 10

### 简易安装脚本

为了简化安装体验，BunkerWeb 提供了一个简易安装脚本，可以自动处理整个设置过程，包括 NGINX 安装、仓库配置和服务设置。

#### 快速开始

要开始使用，请下载安装脚本及其校验和，然后在运行前验证脚本的完整性。

```bash
# 下载脚本及其校验和
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc1/install-bunkerweb.sh
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc1/install-bunkerweb.sh.sha256

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
3.  **可选集成**：提供自动安装和配置 [CrowdSec 安全引擎](#crowdsec-integration-with-the-script)以及 Redis/Valkey（用于共享缓存与会话数据）的选项。
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
    *   **仅 API**：仅安装 API 服务以便进行编程访问。
2.  **设置向导**：选择是否启用基于 Web 的配置向导。强烈建议初次使用的用户选择此项。
3.  **CrowdSec 集成**：选择安装 CrowdSec 安全引擎，以获得先进的实时威胁防护。仅适用于完整堆栈安装。
4.  **CrowdSec AppSec**：如果您选择安装 CrowdSec，您还可以启用应用程序安全 (AppSec) 组件，它增加了 WAF 功能。
5.  **Redis/Valkey**：启用 Redis/Valkey 以在节点之间共享会话、指标和安全数据（用于集群与负载均衡）。可本地安装或使用已有服务器。仅适用于完整堆栈和管理器安装。
6.  **DNS 解析器**：对于完整堆栈、管理器和工作节点安装，您可以选择指定自定义 DNS 解析器 IP。
7.  **内部 API HTTPS**：对于完整堆栈、管理器和工作节点安装，选择是否为调度器/管理器与 BunkerWeb/工作节点实例之间的内部 API 通信启用 HTTPS（默认：仅 HTTP）。
8.  **API 服务**：对于完整堆栈和管理器安装，选择是否启用可选的外部 API 服务。在 Linux 安装中，它默认是禁用的。

!!! info "管理器和调度器安装"
    如果您选择**管理器**或**仅调度器**安装类型，系统还会提示您提供您的 BunkerWeb 工作节点实例的 IP 地址或主机名。

#### 命令行选项

对于非交互式或自动化设置，可以使用命令行标志来控制脚本：

**通用选项：**

| 选项                    | 描述                                              |
| ----------------------- | ------------------------------------------------- |
| `-v, --version VERSION` | 指定要安装的 BunkerWeb 版本（例如 `1.6.8~rc1`）。 |
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
| `--api-only`       | 仅安装 API 服务（端口 8000）。                        |

**安全集成：**

| 选项                | 描述                                               |
| ------------------- | -------------------------------------------------- |
| `--crowdsec`        | 安装并配置 CrowdSec 安全引擎。                     |
| `--no-crowdsec`     | 跳过 CrowdSec 安装。                               |
| `--crowdsec-appsec` | 安装带有 AppSec 组件的 CrowdSec（包括 WAF 功能）。 |
| `--redis`           | 本地安装并配置 Redis。                             |
| `--no-redis`        | 跳过 Redis 集成。                                  |

**高级选项：**

| 选项                        | 描述                                                             |
| --------------------------- | ---------------------------------------------------------------- |
| `--instances "IP1 IP2"`     | 以空格分隔的 BunkerWeb 实例列表（在管理器/调度器模式下为必需）。 |
| `--manager-ip IPs`          | 管理器/调度器 IP 白名单（在非交互模式下的工作节点中为必需）。    |
| `--dns-resolvers "IP1 IP2"` | 自定义 DNS 解析器 IP（用于完整、管理器或工作节点安装）。         |
| `--api-https`               | 为内部 API 通信启用 HTTPS（默认：仅 HTTP）。                     |
| `--backup-dir PATH`         | 升级前存储自动备份的目录。                                       |
| `--no-auto-backup`          | 跳过自动备份（您必须手动完成）。                                 |
| `--redis-host HOST`         | 现有 Redis/Valkey 服务器的主机。                                 |
| `--redis-port PORT`         | 现有 Redis/Valkey 服务器的端口。                                 |
| `--redis-database DB`       | Redis 数据库编号。                                               |
| `--redis-username USER`     | Redis 用户名（Redis 6+）。                                       |
| `--redis-password PASS`     | Redis 密码。                                                     |
| `--redis-ssl`               | 为 Redis 连接启用 SSL/TLS。                                      |
| `--redis-no-ssl`            | 禁用 Redis 连接的 SSL/TLS。                                      |
| `--redis-ssl-verify`        | 验证 Redis SSL 证书。                                            |
| `--redis-no-ssl-verify`     | 不验证 Redis SSL 证书。                                          |

**用法示例：**

```bash
# 以交互模式运行（推荐给大多数用户）
sudo ./install-bunkerweb.sh

# 使用默认设置进行非交互式安装（完整堆栈，启用向导）
sudo ./install-bunkerweb.sh --yes

# 安装一个不带设置向导的工作节点
sudo ./install-bunkerweb.sh --worker --no-wizard

# 安装一个特定版本
sudo ./install-bunkerweb.sh --version 1.6.8~rc1

# 带有远程工作实例的管理器设置（需要 instances）
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# 具有内部 HTTPS API 通信的管理器
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11" --api-https

# 具有自定义 DNS 解析器和内部 HTTPS API 的工作节点
sudo ./install-bunkerweb.sh --worker --dns-resolvers "1.1.1.1 1.0.0.1" --api-https

# 带有 CrowdSec 和 AppSec 的完整安装
sudo ./install-bunkerweb.sh --crowdsec-appsec

# 使用现有 Redis 服务器的完整安装
sudo ./install-bunkerweb.sh --redis-host redis.example.com --redis-password "your-strong-password"

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

    - CrowdSec 选项（`--crowdsec`, `--crowdsec-appsec`）仅与 `--full`（默认）安装类型兼容
    - 它们不能与 `--manager`, `--worker`, `--scheduler-only`, `--ui-only` 或 `--api-only` 安装一起使用

    **Redis 限制：**

    - Redis 选项（`--redis`, `--redis-*`）仅与 `--full`（默认）和 `--manager` 安装类型兼容
    - 它们不能与 `--worker`, `--scheduler-only`, `--ui-only` 或 `--api-only` 安装一起使用

    **API 服务可用性：**

    - 外部 API 服务（端口 8000）适用于 `--full` 和 `--manager` 安装类型
    - 它不适用于 `--worker`, `--scheduler-only` 或 `--ui-only` 安装
    - 使用 `--api-only` 进行专用的 API 服务安装

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

### 使用软件包管理器安装

请确保在安装 BunkerWeb 之前**已经安装了 NGINX 1.28.1**。对于除 Fedora 之外的所有发行版，强制要求使用来自[官方 NGINX 仓库](https://nginx.org/en/linux_packages.html)的预构建包。从源代码编译 NGINX 或使用来自不同仓库的包将无法与 BunkerWeb 的官方预构建包一起工作。但是，您可以选择从源代码构建 BunkerWeb。

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

    您现在应该能够安装 NGINX 1.28.1：

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.1-1~$(lsb_release -cs)
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

    最后安装 BunkerWeb 1.6.8~rc1：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.8~rc1
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

    您现在应该能够安装 NGINX 1.28.1：

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.1-1~$(lsb_release -cs)
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

    最后安装 BunkerWeb 1.6.8~rc1：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.8~rc1
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

    Fedora 已经提供了我们支持的 NGINX 1.28.1

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.1
    ```

    !!! example "禁用设置向导"
        如果您不希望在安装 BunkerWeb 时使用 Web UI 的设置向导，请导出以下变量：

        ```shell
        export UI_WIZARD=no
        ```

    最后安装 BunkerWeb 1.6.8~rc1：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y --allowerasing bunkerweb-1.6.8~rc1
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

    您现在应该能够安装 NGINX 1.28.1：

    ```shell
    sudo dnf install --allowerasing nginx-1.28.1
    ```

    !!! example "禁用设置向导"
        如果您不希望在安装 BunkerWeb 时使用 Web UI 的设置向导，请导出以下变量：

        ```shell
        export UI_WIZARD=no
        ```

    最后安装 BunkerWeb 1.6.8~rc1：

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.8~rc1
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
    请注意，我们的说明假设您正在使用 MariaDB 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，我们理解您可能更喜欢为您的 Docker 集成使用其他后端。如果是这样，请放心，其他数据库后端仍然是可行的。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc1/misc/integrations)中的 docker-compose 文件。

要启用自动配置更新，请在堆栈中包含一个名为 `bw-autoconf` 的额外容器。此容器承载自动配置服务，该服务管理 BunkerWeb 的动态配置更改。

为了支持此功能，请使用一个专用的“真实”数据库后端（例如，MariaDB、MySQL 或 PostgreSQL）进行同步配置存储。通过集成 `bw-autoconf` 和合适的数据库后端，您为 BunkerWeb 中无缝的自动配置管理建立了基础设施。

```yaml
x-bw-env: &bw-env
  # 我们使用一个锚点来避免在两个容器中重复相同的设置
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8-rc1
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
    image: bunkerity/bunkerweb-scheduler:1.6.8-rc1
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
    image: bunkerity/bunkerweb-autoconf:1.6.8-rc1
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

### Autoconf 容器设置

`bw-autoconf` 控制器监控编排器并将变更写入共享数据库。

#### 配置来源与优先级

1. 环境变量（包括 Docker/Compose 的 `environment:`）
2. `/run/secrets/<VAR>` 下的 secrets（entrypoint 自动加载）
3. 内置默认值

#### 配置参考（高级）

##### 模式与运行时

| Setting               | 描述                                    | 接受的值                           | 默认值                        |
| --------------------- | --------------------------------------- | ---------------------------------- | ----------------------------- |
| `AUTOCONF_MODE`       | 启用 autoconf 控制器                    | `yes` 或 `no`                      | `no`                          |
| `SWARM_MODE`          | 监控 Swarm 服务而非 Docker 容器         | `yes` 或 `no`                      | `no`                          |
| `KUBERNETES_MODE`     | 监控 Kubernetes ingress/pod 而非 Docker | `yes` 或 `no`                      | `no`                          |
| `DOCKER_HOST`         | Docker 套接字 / 远程 API URL            | 例如 `unix:///var/run/docker.sock` | `unix:///var/run/docker.sock` |
| `WAIT_RETRY_INTERVAL` | 实例就绪检查之间的秒数                  | 整秒                               | `5`                           |
| `LOG_SYSLOG_TAG`      | Autoconf 日志的 syslog tag              | 字符串                             | `bw-autoconf`                 |
| `TZ`                  | Autoconf 日志和时间戳使用的时区         | TZ 数据库名（如 `Europe/Paris`）   | unset（容器默认，通常为 UTC） |

##### 数据库与校验

| Setting                 | 描述                                                | 接受的值              | 默认值                                    |
| ----------------------- | --------------------------------------------------- | --------------------- | ----------------------------------------- |
| `DATABASE_URI`          | 主数据库 DSN（必须与调度器数据库匹配）              | SQLAlchemy DSN        | `sqlite:////var/lib/bunkerweb/db.sqlite3` |
| `DATABASE_URI_READONLY` | 可选只读 DSN；若只有它可用，autoconf 将退回只读模式 | SQLAlchemy DSN 或留空 | unset                                     |
| `IGNORE_REGEX_CHECK`    | 跳过来自标签/注解的设置的正则校验                   | `yes` 或 `no`         | `no`                                      |

##### 日志

| Setting                         | 描述                                                      | 接受的值                                        | 默认值                          |
| ------------------------------- | --------------------------------------------------------- | ----------------------------------------------- | ------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | 基础日志级别 / 覆盖                                       | `debug`, `info`, `warning`, `error`, `critical` | `info`                          |
| `LOG_TYPES`                     | 目标                                                      | 空格分隔的 `stderr`/`file`/`syslog`             | `stderr`                        |
| `LOG_FILE_PATH`                 | 文件日志路径（当 `LOG_TYPES` 包含 `file` 时使用）         | 文件路径                                        | unset（启用 `file` 时自行设置） |
| `LOG_SYSLOG_ADDRESS`            | Syslog 目标（`udp://host:514`、`tcp://host:514`、socket） | Host:port、带协议前缀的主机或路径               | unset                           |
| `LOG_SYSLOG_TAG`                | Syslog 标识/tag                                           | 字符串                                          | `bw-autoconf`                   |

##### 作用域与发现过滤

| Setting                         | 描述                                          | 接受的值                       | 默认值 |
| ------------------------------- | --------------------------------------------- | ------------------------------ | ------ |
| `NAMESPACES`                    | 需管理的命名空间/项目（空格分隔）；空表示全部 | 空格分隔字符串                 | unset  |
| `DOCKER_IGNORE_LABELS`          | 收集实例/服务/配置时忽略这些容器/标签         | 用空格或逗号分隔的完整键或后缀 | unset  |
| `SWARM_IGNORE_LABELS`           | 忽略带匹配标签的 Swarm 服务/配置              | 用空格或逗号分隔的完整键或后缀 | unset  |
| `KUBERNETES_IGNORE_ANNOTATIONS` | 发现时忽略 ingress/pod 注解                   | 用空格或逗号分隔的完整键或后缀 | unset  |

##### 仅 Kubernetes

| Setting                                 | 描述                                                                        | 接受的值          | 默认值          |
| --------------------------------------- | --------------------------------------------------------------------------- | ----------------- | --------------- |
| `KUBERNETES_VERIFY_SSL`                 | 校验 Kubernetes API 的 TLS                                                  | `yes` 或 `no`     | `yes`           |
| `KUBERNETES_SSL_CA_CERT`                | Kubernetes API 自定义 CA bundle 路径                                        | 文件路径          | unset           |
| `USE_KUBERNETES_FQDN`                   | 使用 `<pod>.<ns>.pod.<domain>` 而不是 Pod IP 作为实例主机名                 | `yes` 或 `no`     | `yes`           |
| `KUBERNETES_INGRESS_CLASS`              | 仅处理该类的 ingress                                                        | 字符串            | unset（全部）   |
| `KUBERNETES_DOMAIN_NAME`                | 构建上游主机时使用的集群域名后缀                                            | 字符串            | `cluster.local` |
| `KUBERNETES_SERVICE_PROTOCOL`           | 生成的反向代理主机所用的协议                                                | `http` 或 `https` | `http`          |
| `BUNKERWEB_SERVICE_NAME`                | 在补丁 Ingress 状态时读取的 Service 名称                                    | 字符串            | `bunkerweb`     |
| `BUNKERWEB_NAMESPACE`                   | 该 Service 的命名空间                                                       | 字符串            | `bunkerweb`     |
| `KUBERNETES_REVERSE_PROXY_SUFFIX_START` | 多路径 ingress 生成 `REVERSE_PROXY_HOST_n`/`REVERSE_PROXY_URL_n` 的起始索引 | 整数 (>=0)        | `1`             |

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
        image: bunkerity/bunkerweb:1.6.8-rc1
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # 为 BunkerWeb 实例设置命名空间，以便自动配置服务可以检测到它
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.8-rc1
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
    请注意，我们的说明假设您正在使用 MariaDB 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，我们理解您可能更喜欢为您的 Docker 集成使用其他后端。如果是这样，请放心，其他数据库后端仍然是可行的。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc1/misc/integrations)中的 docker-compose 文件。

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

#### Sidecar Container + Helm

This documentation explains how to deploy BunkerWeb as a sidecar to protect your Kubernetes applications. In this architecture, each application has its own BunkerWeb container acting as a security reverse proxy.

##### Architecture

```mermaid
flowchart TB

  %% ---------- 样式 ----------
  classDef scheduler     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef podContainer  fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:6 3,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;

  %% ---------- 顶部：调度器 ----------
  SCHED["BunkerWeb 调度器（集中式）<br/>+ UI + MariaDB + Redis"]:::scheduler

  %% ---------- Pods 组 ----------
  subgraph PODS["Pod 组"]
    %% 应用 Pod 1 ----------
    subgraph POD1["应用 Pod"]
      BW1["BunkerWeb"]:::component
      APP1["应用程序<br/>(端口 80)"]:::component
      BW1 -->|合法请求| APP1
    end
    class POD1 podContainer

    %% 应用 Pod 2 ----------
    subgraph POD2["应用 Pod"]
      BW2["BunkerWeb"]:::component
      APP2["应用程序<br/>(端口 XX)"]:::component
      BW2 -->|合法请求| APP2
    end
    class POD2 podContainer
  end

  %% ---------- 底部：负载均衡器 ----------
  LB["负载均衡器"]:::lb

  %% 调度器通过 API 控制 BunkerWeb 实例
  %% The Scheduler controls the BunkerWeb instances (API)
  SCHED -->|API 5000| BW1
  SCHED -->|API 5000| BW2
  %% 负载均衡器将流量发送到 BunkerWeb
  %% The load balancer sends traffic to BunkerWeb
  LB -->|HTTP/HTTPS| BW1
  LB -->|HTTP/HTTPS| BW2
  %% ---------- 布局辅助（隐藏） ----------
  %% 将负载均衡器放置在整个 Pod 组之下
  %% Place the load balancer under the entire PODS group
  PODS --> LB
  linkStyle 6 stroke-width:0px,stroke:transparent;
```

##### Prerequisites

- A working Kubernetes cluster
- Helm 3.x installed
- BunkerWeb Helm chart deployed with:
  - `scheduler` enabled
  - `ui` enabled
  - `mariadb` enabled (to store configurations)
  - `redis` enabled (for synchronization)
  - `controller` enabled (recommended for automatic sidecar discovery)
  - `bunkerweb.replicas: 0` (no standalone deployment)

##### Sidecar Discovery Modes

BunkerWeb offers two modes for sidecar discovery:

###### Mode 1: Automatic Discovery (Controller - Recommended)

The **BunkerWeb controller** automatically discovers pods with BunkerWeb sidecars without manual configuration.

**Advantages:**
- ✅ Automatic discovery of new sidecars
- ✅ No need to manually maintain `BUNKERWEB_INSTANCES`
- ✅ Automatic scaling

**Configuration:**

1. Enable the controller in `values.yaml`:
```yaml
controller:
  enabled: true
  tag: "1.6.8~rc1"
```

2. For each sidecar, add:
   - **Pod annotation**: `bunkerweb.io/INSTANCE: "yes"`
   - **Environment variable**: `KUBERNETES_MODE: "yes"`

  ```yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: nginx-bunkerweb
    namespace: bunkerweb
  spec:
    replicas: 1
    selector:
      matchLabels:
        app: nginx-bw
    template:
      metadata:
        labels:
          app: nginx-bw
        annotations:
          # Mandatory annotation for auto-discovery when using bunkerweb-controller
          bunkerweb.io/INSTANCE: "yes"
      spec:
        containers:
          # Random WebApp you want to protect
          - name: nginx
            image: nginx:latest
            ports:
              - containerPort: 80
          # Sidecar BunkerWeb
          - name: bunkerweb
            image: bunkerity/bunkerweb:latest
            ports:
              - containerPort: 8080
                name: entrypoint
              - containerPort: 5000
                name: bwapi
              - containerPort: 9113
                name: metrics
            env:
              - name: API_WHITELIST_IP
                value: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
              - name: KUBERNETES_MODE
                value: "yes"
  ---
  apiVersion: v1
  kind: Service
  metadata:
    name: nginx-bunkerweb
    namespace: bunkerweb
  spec:
    type: ClusterIP
    selector:
      app: nginx-bw
    ports:
      - name: http
        port: 80
        targetPort: 8080 # BunkerWeb exposed port
  ```

3. **No need for headless service** - the controller communicates directly with pods

4. **No need** to manually configure the scheduler with `BUNKERWEB_INSTANCES` - the controller handles discovery

###### Mode 2: Manual Configuration (BUNKERWEB_INSTANCES)

Explicit configuration of each instance via the `BUNKERWEB_INSTANCES` environment variable.

**Advantages:**
- ✅ Precise control over managed instances
- ✅ Useful for complex multi-namespace environments

**Configuration:**

See the following sections for details.

##### Step 1: Scheduler Configuration

The BunkerWeb scheduler is the central component that distributes configurations to all sidecars.

###### Option A: With Controller (Recommended)

If you're using the controller for automatic discovery, **no special configuration is needed** for the scheduler. The controller will automatically detect pods with the `bunkerweb.io/INSTANCE: "yes"` annotation.

###### Option B: Manual Configuration with `BUNKERWEB_INSTANCES`

In your BunkerWeb chart `values.yaml`, configure the `BUNKERWEB_INSTANCES` environment variable with the URLs of all your headless services:

```yaml
scheduler:
  tag: "1.6.8~rc1"
  extraEnvs:
    - name: BUNKERWEB_INSTANCES
      value: "http://app1-bunkerweb-workers.namespace.svc.cluster.local:5000 http://app2-bunkerweb-workers.namespace.svc.cluster.local:5000"
```

**Important:**
- Separate URLs with spaces
- Use port **5000** (BunkerWeb internal API)
- Format: `http://<service-name>.<namespace>.svc.cluster.local:5000`

##### Step 2: Creating the Deployment with Sidecar

###### Deployment Structure with Controller (Automatic Mode - Recommended)

**Recommended configuration** with automatic discovery:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-bunkerweb
  namespace: your-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
      annotations:
        bunkerweb.io/INSTANCE: "yes"  # Enable automatic discovery
    spec:
      containers:
        # Your application
        - name: my-app
          image: my-image:latest
          ports:
            - containerPort: 80  # Port your app listens on

        # BunkerWeb Sidecar
        - name: bunkerweb
          image: bunkerity/bunkerweb:1.6.8-rc1
          ports:
            - containerPort: 8080  # Exposed HTTP port
            - containerPort: 5000  # Internal API (mandatory)
          env:
            - name: KUBERNETES_MODE
              value: "yes"  # Enable Kubernetes mode
            - name: API_WHITELIST_IP
              value: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
            - name: MULTISITE
              value: "yes"
            - name: USE_REVERSE_PROXY
              value: "yes"
            - name: LOG_LEVEL
              value: "info"
```

**Key points for automatic mode:**
- ✅ **Mandatory annotation**: `bunkerweb.io/INSTANCE: "yes"` at pod level
- ✅ **Mandatory environment variable**: `KUBERNETES_MODE: "yes"`
- ✅ **No headless service needed**: the controller communicates directly with pods via Kubernetes API
- ✅ **No need to manually configure** `BUNKERWEB_INSTANCES`

###### Deployment Structure without Controller (Manual Mode)

If you're not using the controller:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-bunkerweb
  namespace: your-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        # Your application
        - name: my-app
          image: my-image:latest
          ports:
            - containerPort: 80  # Port your app listens on

        # BunkerWeb Sidecar
        - name: bunkerweb
          image: bunkerity/bunkerweb:1.6.5
          ports:
            - containerPort: 8080  # Exposed HTTP port
            - containerPort: 5000  # Internal API (mandatory)
          env:
            - name: API_WHITELIST_IP
              value: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
```

###### Important Environment Variables

| Variable           | Value                                                 | Description                                              |
| ------------------ | ----------------------------------------------------- | -------------------------------------------------------- |
| `KUBERNETES_MODE`  | `yes`                                                 | **Mandatory** for automatic discovery via the controller |
| `API_WHITELIST_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | IPs allowed to access the API                            |


##### Step 3: Creating Services

###### ClusterIP Service (external exposure)

Service to expose your application through BunkerWeb:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app-bunkerweb
  namespace: your-namespace
spec:
  type: ClusterIP  # or LoadBalancer depending on your needs
  selector:
    app: my-app
  ports:
    - name: http
      port: 80
      targetPort: 8080  # BunkerWeb port
```

###### Headless Service (internal API) - Conditional

**Only required in manual mode (without controller)**:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app-bunkerweb-workers
  namespace: your-namespace
spec:
  clusterIP: None  # Headless service
  selector:
    app: my-app
  ports:
    - name: bwapi
      protocol: TCP
      port: 5000
      targetPort: 5000
```

**Important:**
- ⚠️ **Not required with controller** - the controller communicates directly with pods via Kubernetes API
- ✅ **Mandatory without controller** - this service name must be manually added to `BUNKERWEB_INSTANCES`
- The `selector` must match your deployment labels

##### Step 4: Reverse Proxy Configuration

You have **two options** to configure the reverse proxy:

###### Option A: Via Web Interface (UI)

1. Access the BunkerWeb UI
2. Go to the **"Services"**
3. Create a new service with:
   - **Server name**: `my-app.example.com`
   - **Reverse proxy host**: `http://127.0.0.1:80` (or your app's port)
   - **Use reverse proxy**: `yes`
4. Save

The scheduler will automatically send the configuration to the sidecar via the API (port 5000).

###### Option B: Via Environment Variables

Add these variables in the `bunkerweb` container:

```yaml
env:
  - name: MULTISITE
    value: "yes"
  - name: SERVER_NAME
    value: "my-app.example.com"
  - name: my-app.example.com_USE_REVERSE_PROXY
    value: "yes"
  - name: my-app.example.com_REVERSE_PROXY_HOST
    value: "http://127.0.0.1:80"
  - name: my-app.example.com_REVERSE_PROXY_URL
    value: "/"
```

**Note:** The UI option is recommended for centralized and dynamic management.

##### Step 5: Deployment

###### With Controller (Automatic Mode - Recommended)

1. **Deploy your application with the sidecar**:
   ```bash
   kubectl apply -f my-app-deployment.yaml
   ```

   Make sure that:
   - The annotation `bunkerweb.io/INSTANCE: "yes"` is present in `template.metadata.annotations`
   - The variable `KUBERNETES_MODE: "yes"` is defined in the bunkerweb container

2. **Verify that the controller detects the sidecar**:
   ```bash
   kubectl logs -n bunkerweb deployment/bunkerweb-controller -f
   ```
   You should see logs indicating the discovery of the new pod.

3. **Create the reverse proxy configuration** via the BunkerWeb UI

4. **Test your application**:
   ```bash
   curl -H "Host: my-app.example.com" http://<service-ip>
   ```

###### Without Controller (Manual Mode)

1. **Deploy your application with the sidecar**:
   ```bash
   kubectl apply -f my-app-deployment.yaml
   ```

2. **Add the headless service to `BUNKERWEB_INSTANCES`**:
   Update your `values.yaml` and upgrade the Helm chart:
   ```bash
   helm upgrade bunkerweb bunkerity/bunkerweb -n bunkerweb -f values.yaml
   ```

3. **Verify that the scheduler detects the sidecar**:
   ```bash
   kubectl logs -n bunkerweb deployment/bunkerweb-scheduler -f
   ```
   You should see logs indicating the connection to the new worker.

4. **Create the reverse proxy configuration** via the BunkerWeb UI

5. **Test your application**:
   ```bash
   curl -H "Host: my-app.example.com" http://<service-ip>
   ```

###### Common Issues

| Issue                            | Cause                                     | Solution                                                   |
| -------------------------------- | ----------------------------------------- | ---------------------------------------------------------- |
| Scheduler can't find the sidecar | Missing or misconfigured headless service | Verify the service exists and is in `BUNKERWEB_INSTANCES`  |
| 502 Bad Gateway error            | App is not accessible from BunkerWeb      | Verify the reverse proxy URL is correct (`127.0.0.1:port`) |
| Configuration not applied        | Sidecar didn't receive the config         | Check scheduler and sidecar logs                           |
| Port 5000 not accessible         | Port not exposed in the container         | Add `- containerPort: 5000` in the bunkerweb container     |

##### Adding a New Application

###### With Controller (Automatic Mode)

To add a new application protected by BunkerWeb:

1. **Create a new deployment** with the BunkerWeb sidecar with:
   - Annotation `bunkerweb.io/INSTANCE: "yes"` in `template.metadata.annotations`
   - Environment variable `KUBERNETES_MODE: "yes"` in the bunkerweb container

2. **Create only the ClusterIP service** (no headless service needed!)

3. **Apply the deployment**:
   ```bash
   kubectl apply -f new-app-deployment.yaml
   ```

4. **The controller automatically detects the new pod** - no chart redeployment needed!

5. **Configure the reverse proxy** in the UI

###### Without Controller (Manual Mode)

To add a new application protected by BunkerWeb:

1. **Create a new deployment** with the BunkerWeb sidecar (as described above)

2. **Create both services** (ClusterIP + Headless)

3. **Add the new headless service** to `BUNKERWEB_INSTANCES`:
   ```yaml
   extraEnvs:
     - name: BUNKERWEB_INSTANCES
       value: "http://app1-workers.ns.svc.cluster.local:5000 http://app2-workers.ns.svc.cluster.local:5000"
   ```

4. **Redeploy the chart**:
   ```bash
   helm upgrade bunkerweb bunkerity/bunkerweb -n bunkerweb -f values.yaml
   ```

5. **Configure the reverse proxy** in the UI or via env vars

##### Best Practices

✅ **Use the controller** for automatic sidecar discovery (simpler, no headless service needed)
✅ **Use a single centralized scheduler** to manage all sidecars
✅ **Always add the annotation** `bunkerweb.io/INSTANCE: "yes"` and environment variable `KUBERNETES_MODE: "yes"` when using controller mode
✅ **No headless service needed with controller** - only ClusterIP service is sufficient
✅ **Use the UI** to manage configurations (more flexible)
✅ **Define resource limits** for containers
✅ **Use Kubernetes secrets** for sensitive configurations
✅ **Check logs** of scheduler and sidecars regularly

#### 完整的 YAML 文件

除了使用 helm chart，您还可以使用 GitHub 仓库中 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc1/misc/integrations)内的 YAML 样板文件。请注意，我们强烈建议您改用 helm chart。

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
              image: bunkerity/bunkerweb-autoconf:1.6.8-rc1
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
  tag: 1.6.8~rc1

# 调度器设置
scheduler:
  tag: 1.6.8~rc1
  extraEnvs:
    # 启用 real IP 模块以获取客户端的真实 IP
    - name: USE_REAL_IP
      value: "yes"

# 控制器设置
controller:
  tag: 1.6.8~rc1

# UI 设置
ui:
  tag: 1.6.8~rc1
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

**首先，您需要进入全局设置，选择 SSL 插件，然后禁用自动将 HTTP 重定向到 HTTPS。请注意，您只需要执行一次。**

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
    请注意，我们的说明假设您正在使用 MariaDB 作为默认的数据库后端，这是由 `DATABASE_URI` 设置配置的。但是，我们理解您可能更喜欢为您的 Docker 集成使用其他后端。如果是这样，请放心，其他数据库后端仍然是可行的。有关更多信息，请参阅仓库的 [misc/integrations 文件夹](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc1/misc/integrations)中的 docker-compose 文件。

    集群数据库后端的设置超出了本文档的范围。

这是您可以使用 `docker stack deploy` 部署的堆栈样板：

```yaml
x-bw-env: &bw-env
  # 我们使用一个锚点来避免在两个服务中重复相同的设置
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8-rc1
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
    image: bunkerity/bunkerweb-scheduler:1.6.8-rc1
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
    image: bunkerity/bunkerweb-autoconf:1.6.8-rc1
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
    image: redis:8-alpine
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
        image: bunkerity/bunkerweb:1.6.8-rc1
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
        image: bunkerity/bunkerweb-autoconf:1.6.8-rc1
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

## Terraform

### 简介

BunkerWeb 的 Terraform Provider 允许您通过基础设施即代码（IaC）管理 BunkerWeb 实例、服务和配置。该 Provider 与 BunkerWeb API 交互,自动化部署和管理您的安全配置。

### 先决条件

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.12
- 已启用 API 的 BunkerWeb 实例
- API 令牌或基本身份验证凭据

### 安装

该 Provider 可在 [Terraform Registry](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest) 上获得。将其添加到您的 Terraform 配置中:

```terraform
terraform {
  required_providers {
    bunkerweb = {
      source  = "bunkerity/bunkerweb"
      version = "~> 0.0.2"
    }
  }
}
```

### 配置

#### Bearer Token 身份验证(推荐)

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_token    = var.bunkerweb_token
}
```

#### 基本身份验证

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_username = var.bunkerweb_username
  api_password = var.bunkerweb_password
}
```

### 使用示例

#### 创建 Web 服务

```terraform
resource "bunkerweb_service" "app" {
  server_name = "app.example.com"

  variables = {
    upstream = "10.0.0.12:8080"
    mode     = "production"
  }
}
```

#### 注册实例

```terraform
resource "bunkerweb_instance" "worker1" {
  hostname     = "worker-1.internal"
  name         = "Worker 1"
  port         = 8080
  listen_https = true
  https_port   = 8443
  server_name  = "worker-1.internal"
  method       = "api"
}
```

#### 配置全局设置

```terraform
resource "bunkerweb_global_config_setting" "retry" {
  key   = "retry_limit"
  value = "10"
}
```

#### 封禁 IP 地址

```terraform
resource "bunkerweb_ban" "suspicious_ip" {
  ip       = "192.0.2.100"
  reason   = "Multiple failed login attempts"
  duration = 3600  # 1小时(秒)
}
```

#### 自定义配置

```terraform
resource "bunkerweb_config" "custom_rules" {
  service_id = "app.example.com"
  type       = "http"
  name       = "custom-rules.conf"
  content    = file("${path.module}/configs/custom-rules.conf")
}
```

### 可用资源

该 Provider 提供以下资源:

- **bunkerweb_service**: Web 服务管理
- **bunkerweb_instance**: 实例注册和管理
- **bunkerweb_global_config_setting**: 全局配置
- **bunkerweb_config**: 自定义配置
- **bunkerweb_ban**: IP 封禁管理
- **bunkerweb_plugin**: 插件安装和管理

### 数据源

数据源允许读取现有信息:

- **bunkerweb_service**: 读取现有服务
- **bunkerweb_global_config**: 读取全局配置
- **bunkerweb_plugins**: 列出可用插件
- **bunkerweb_cache**: 缓存信息
- **bunkerweb_jobs**: 计划作业状态

### 临时资源

用于一次性操作:

- **bunkerweb_run_jobs**: 按需触发作业
- **bunkerweb_instance_action**: 在实例上执行操作(重新加载、停止等)
- **bunkerweb_service_snapshot**: 捕获服务状态
- **bunkerweb_config_upload**: 批量配置上传

### 完整示例

以下是使用 BunkerWeb 的完整基础设施示例:

```terraform
terraform {
  required_providers {
    bunkerweb = {
      source  = "bunkerity/bunkerweb"
      version = "~> 0.0.1"
    }
  }
}

provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_token    = var.bunkerweb_token
}

# 全局配置
resource "bunkerweb_global_config_setting" "rate_limit" {
  key   = "rate_limit"
  value = "10r/s"
}

# 主服务
resource "bunkerweb_service" "webapp" {
  server_name = "webapp.example.com"

  variables = {
    upstream          = "10.0.1.10:8080"
    mode              = "production"
    auto_lets_encrypt = "yes"
    use_modsecurity   = "yes"
    use_antibot       = "cookie"
  }
}

# 具有不同配置的 API 服务
resource "bunkerweb_service" "api" {
  server_name = "api.example.com"

  variables = {
    upstream        = "10.0.1.20:3000"
    mode            = "production"
    use_cors        = "yes"
    cors_allow_origin = "*"
  }
}

# Worker 实例
resource "bunkerweb_instance" "worker1" {
  hostname     = "bw-worker-1.internal"
  name         = "Production Worker 1"
  port         = 8080
  listen_https = true
  https_port   = 8443
  server_name  = "bw-worker-1.internal"
  method       = "api"
}

# webapp 服务的自定义配置
resource "bunkerweb_config" "custom_security" {
  service_id = bunkerweb_service.webapp.id
  type       = "http"
  name       = "custom-security.conf"
  content    = <<-EOT
    # Custom security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
  EOT
}

# 封禁可疑 IP
resource "bunkerweb_ban" "blocked_ip" {
  ip       = "203.0.113.50"
  reason   = "Detected malicious activity"
  duration = 86400  # 24小时
}

output "webapp_service_id" {
  value = bunkerweb_service.webapp.id
}

output "api_service_id" {
  value = bunkerweb_service.api.id
}
```

### 其他资源

- [完整 Provider 文档](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest/docs)
- [GitHub 仓库](https://github.com/bunkerity/terraform-provider-bunkerweb)
- [使用示例](https://github.com/bunkerity/terraform-provider-bunkerweb/tree/main/examples)
- [BunkerWeb API 文档](https://docs.bunkerweb.io/latest/api/)

### 支持和贡献

要报告错误或提出改进建议,请访问 [Provider 的 GitHub 仓库](https://github.com/bunkerity/terraform-provider-bunkerweb/issues)。


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
