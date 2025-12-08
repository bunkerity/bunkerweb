# Integrations

## BunkerWeb Cloud

<figure markdown>
  ![Overview](assets/img/bunkerweb-cloud.png){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

BunkerWeb Cloud is a managed Web Application Firewall (WAF) and reverse proxy solution that allows you to secure your web applications without installing BunkerWeb in your infrastructure. By subscribing to BunkerWeb Cloud, you benefit from a complete BunkerWeb stack hosted in the cloud with dedicated resources (8GB RAM, 2 CPU **per** instance, replicated across 2 instances for high availability, Standard offering).

### Key Benefits

Order your [BunkerWeb Cloud instance](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) and get access to:

- **Instant Deployment**: No installation required in your infrastructure
- **High Availability**: Replicated instances with automatic load balancing
- **Integrated Monitoring**: Access to Grafana for logs and metrics visualization
- **Scalability**: Dedicated resources adapted to heavy workloads
- **Enhanced Security**: Real-time WAF protection against web threats

If you are interested in the BunkerWeb Cloud offering, don't hesitate to [contact us](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) so we can discuss your needs.

### Architecture Overview

#### Simple Architecture - Single Service

```mermaid
graph LR
    A[Client] -->|HTTPS| B[example.com]
    B -->|DNS Resolution| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Traffic| D[BunkerWeb CloudWAF + Reverse Proxy]
    D -->|HTTPS/HTTP| E[Server example.comClient Infrastructure]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#e8f5e8,color:#222
```

#### Complex Architecture - Multi-services

```mermaid
graph LR
    A[Clients] -->|HTTPS| B[example.comother-example.coman-other-example.com]
    B -->|DNS Resolution| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Traffic| D[BunkerWeb CloudWAF + Reverse ProxySSL SNI Enabled]
    D -->|HTTPS with SNI| E[Client GatewayReverse Proxy/LB]
    E -->|Internal routing| F[Service 1]
    E -->|Internal routing| G[Service 2]
    E -->|Internal routing| H[Service N]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#fff3e0,color:#222
    style F fill:#e8f5e8,color:#222
    style G fill:#e8f5e8,color:#222
    style H fill:#e8f5e8,color:#222
```

### Initial Configuration

#### 1. Management Interface Access

After subscribing to BunkerWeb Cloud, you will receive:

- **BunkerWeb UI access URL**: Interface for configuring your services
- **Load Balancer endpoint**: Unique URL in the format `http://[ID].bunkerweb.cloud`
- **Grafana Access**: Monitoring interface and metrics visualization
- **Allocated Resources**: 2 instances with 8GB RAM and 2 CPU each

#### 2. First Connection

1. Connect to the BunkerWeb Cloud interface
2. Configure your services to protect
3. Access Grafana to visualize your BunkerWeb logs and metrics

### DNS Configuration

#### Traffic Redirection to BunkerWeb Cloud

For your domain traffic to be processed by BunkerWeb Cloud, you must configure your DNS records:

**Required Configuration:**

```dns
example.com.        IN  CNAME  54984654.bunkerweb.cloud.
www.example.com.    IN  CNAME  54984654.bunkerweb.cloud.
```

**Important:** Replace `54984654` with your load balancer identifier provided during subscription.

#### Configuration Validation

Verify DNS resolution:

```bash
dig example.com
nslookup example.com
```

The result should point to your BunkerWeb Cloud endpoint.

### Service Configuration

#### Single Service

For a simple service hosted on your infrastructure:

**Configuration in BunkerWeb UI:**

1. **Server Name**: `example.com`
2. **Use Reverse Proxy**: `yes`
3. **Reverse Proxy Host**: `185.87.1.100:443` (your server IP)

You can find all configuration options in the [Reverse Proxy Documentation](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

#### Multi-services with SNI

##### Why Enable SNI?

Server Name Indication (SNI) is **essential** when:

- Multiple domains point to the same backend infrastructure
- Your infrastructure hosts multiple services with distinct SSL certificates
- You use a reverse proxy/gateway on the client side

##### SNI Configuration

**In BunkerWeb UI, for each service:**

```yaml
# Service 1
SERVICE_NAME: example-com
SERVER_NAME: example.com
REVERSE_PROXY_HOST: https://gateway.internal.domain.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: example.com

# Service 2
SERVICE_NAME: other-example-com
SERVER_NAME: other-example.com
REVERSE_PROXY_HOST: https://gateway.internal.domain.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: other-example.com
```

You can find all configuration options in the [Reverse Proxy Documentation](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

##### SNI Technical Details

SNI allows BunkerWeb Cloud to:

1. **Identify the target service** during TLS connection
2. **Transmit the correct domain name** to the backend
3. **Allow the client gateway** to select the right certificate
4. **Route correctly** to the appropriate service

**Without SNI enabled:**

```mermaid
graph LR
    A[Client] --> B[BunkerWeb]
    B --> C["Gateway (default certificate)"]
    C --> D[SSL Error]

    style B fill:#f3e5f5,color:#222
    style C fill:#fff3e0,color:#222
    style D fill:#ff4d4d,color:#fff,stroke:#b30000,stroke-width:2px
```

**With SNI enabled:**

```mermaid
graph LR
    A[Client] --> B[BunkerWeb]
    B --> C["Gateway (example.com specific certificate)"]
    C --> D[Correct Service]

    style B fill:#f3e5f5,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
```

### SSL/TLS and SNI Management

#### SSL Certificates

##### BunkerWeb Cloud Side

BunkerWeb Cloud automatically manages:

- Let's Encrypt certificates for your domains
- Automatic renewal
- Optimized TLS configuration

##### Client Infrastructure Side

**Important Recommendations:**

1. **Use HTTPS** for communication between BunkerWeb and your services
2. **Manage your own certificates** on your infrastructure
3. **Properly configure SNI** on your gateway/reverse proxy

#### Detailed SNI Configuration

##### Use Case: Infrastructure with Gateway

If your architecture looks like:

```mermaid
graph LR
    A[BunkerWeb Cloud] --> B[Client Gateway]
    B --> C[Service 1]
    B --> D[Service 2]
    B --> E[Service 3]

    style A fill:#f3e5f5,color:#222
    style B fill:#fff3e0,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
    style E fill:#e8f5e8,color:#222
```

**Required configuration on BunkerWeb side:**

```yaml
# Configuration for example.com
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: example.com
REVERSE_PROXY_SSL_VERIFY: no  # If self-signed certificate on client side
REVERSE_PROXY_HEADERS: Host $host

# Configuration for api.example.com
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: api.example.com
REVERSE_PROXY_SSL_VERIFY: no
REVERSE_PROXY_HEADERS: Host $host
```

### Client Gateway Configuration

#### Overview

When your architecture uses a gateway/reverse proxy on the client side to route traffic to multiple services, specific configuration is needed to support SNI and ensure secure communication with BunkerWeb Cloud.

#### Configurations by Technology

##### Nginx

<details>
<summary>Nginx Configuration</summary>

```nginx
# Configuration to support SNI with multiple services
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /path/to/example.com.crt;
    ssl_certificate_key /path/to/example.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
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

        # Timeouts
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

        # API-specific configuration
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

</details>

##### Traefik

<details>
<summary>Traefik Configuration</summary>

**With Docker Compose:**

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

**Dynamic configuration (dynamic.yml):**

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
<summary>Apache Configuration</summary>

```apache
# Apache configuration with SNI
<VirtualHost *:443>
    ServerName example.com
    DocumentRoot /var/www/html

    # SSL configuration
    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLHonorCipherOrder off
    SSLCertificateFile /path/to/example.com.crt
    SSLCertificateKeyFile /path/to/example.com.key

    # Security headers
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # Reverse proxy configuration
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Custom headers
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    <Proxy *>
        Require all granted
    </Proxy>

    # Logs
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

    # API-specific configuration
    ProxyTimeout 300
    ProxyBadHeader Ignore

    ErrorLog ${APACHE_LOG_DIR}/api.example.com_error.log
    CustomLog ${APACHE_LOG_DIR}/api.example.com_access.log combined
</VirtualHost>

# Required modules configuration
LoadModule ssl_module modules/mod_ssl.so
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
LoadModule headers_module modules/mod_headers.so
```

</details>

##### HAProxy

<details>
<summary>HAProxy Configuration</summary>

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

    # SSL configuration
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

    # Security headers
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff
    http-response set-header X-XSS-Protection "1; mode=block"
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # SNI-based routing
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

# Statistics interface (optional)
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE
```

</details>

#### SSL Configuration Validation

Test SSL configuration:

```bash
# SSL connectivity test
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Headers verification
curl -I https://your-domain.com

# SNI test
curl -H "Host: example.com" https://54984654.bunkerweb.cloud
```

#### Gateway Best Practices

1. **Health Checks**: Configure health checks for your services
2. **Load Balancing**: Use multiple instances for high availability
3. **Monitoring**: Monitor your gateway metrics
4. **Security Headers**: Add appropriate security headers
5. **Timeouts**: Configure appropriate timeouts to avoid blocking

### BunkerWeb Cloud IP Whitelist

#### Why Configure a Whitelist?

To further secure your infrastructure, it is recommended to configure a whitelist of BunkerWeb Cloud IP addresses on the client infrastructure side. This ensures that only traffic from BunkerWeb Cloud can reach your backend services.

We recommend whitelisting at firewall level (iptables ..etc).

#### BunkerWeb Cloud IP Addresses to Whitelist

**List of IP addresses to allow:**

Updated list is available here: https://repo.bunkerweb.io/cloud/ips

```
# BunkerWeb Cloud IP addresses
4.233.128.18
20.19.161.132
```

#### Whitelist Configuration by Technology

##### Nginx

<details>
<summary>Nginx Configuration</summary>

```nginx
# In your server configuration
server {
    listen 443 ssl;
    server_name example.com;

    # BunkerWeb Cloud IP whitelist
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

# Configuration with geo module for more flexibility
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

    # ... rest of configuration
}
```

</details>

##### Traefik

<details>
<summary>Traefik Configuration</summary>

```yaml
# Configuration in dynamic.yml
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

**With Docker Compose labels:**

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
<summary>Apache Configuration</summary>

```apache
<VirtualHost *:443>
    ServerName example.com

    # BunkerWeb Cloud IP whitelist
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

    # Configuration for denied access logs
    LogFormat "%h %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined
    CustomLog logs/access.log combined
    ErrorLog logs/error.log
</VirtualHost>

# Alternative configuration with mod_authz_core
<VirtualHost *:443>
    ServerName api.example.com

    <Directory />
        <RequireAny>
            Require ip 192.168.1.0/24
            Require ip 10.0.0.0/16
            Require ip 172.16.0.0/12
        </RequireAny>
    </Directory>

    # ... rest of configuration
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>HAProxy Configuration</summary>

```haproxy
# Configuration in haproxy.cfg
frontend bunkerweb_frontend
    bind *:443 ssl crt /path/to/certificates/

    # ACL for BunkerWeb Cloud whitelist
    acl bunkerweb_ips src 192.168.1.0/24 10.0.0.0/16 172.16.0.0/12

    # Block everything except BunkerWeb Cloud
    http-request deny unless bunkerweb_ips

    # Security headers
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff

    # Routing
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

##### System Firewall (iptables)

<details>
<summary>iptables Configuration</summary>

```bash
#!/bin/bash
# iptables configuration script for BunkerWeb Cloud whitelist

# Clear existing rules
iptables -F
iptables -X

# Default policies
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Whitelist BunkerWeb Cloud IPs for HTTPS
iptables -A INPUT -p tcp --dport 443 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 10.0.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 172.16.0.0/12 -j ACCEPT

# Allow HTTP for Let's Encrypt (optional)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# Allow SSH (adapt to your needs)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Logs for debugging
iptables -A INPUT -j LOG --log-prefix "DROPPED: "

# Save rules
iptables-save > /etc/iptables/rules.v4

echo "iptables configuration applied successfully"
```

</details>

#### Whitelist Best Practices

1. **Monitor Rejections**: Monitor blocked access attempts
2. **Regular Updates**: Keep the IP list up to date
3. **Regular Testing**: Validate that the whitelist works correctly
4. **Documentation**: Document IP changes
5. **Alerting**: Configure alerts for BunkerWeb IP changes
6. **Backup**: Keep a backup configuration in case of issues

### REAL_IP Configuration and Client Address Recovery

#### Why Configure REAL_IP?

When using BunkerWeb Cloud as a reverse proxy, the IP addresses that your backend applications see are those of BunkerWeb Cloud, not those of the real clients. To retrieve the real client IP addresses, specific configuration is required.

#### BunkerWeb Cloud Side Configuration

In the BunkerWeb UI, configure Real IP:

```yaml
USE_REAL_IP: yes # Default is no
REAL_IP_FROM: 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8 # Default
REAL_IP_HEADER: X-Forwarded-For # Default
REAL_IP_RECURSIVE: yes # Default
# Example if also using Cloudflare Proxy in front of BunkerWeb
REAL_IP_FROM_URLS: https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/
```

You can find all configuration options in the [Documentation Real Ip](https://docs.bunkerweb.io/latest/settings/#real-ip)

#### Client Infrastructure Side Configuration

##### Nginx

<details>
<summary>Nginx Configuration for REAL_IP</summary>

```nginx
# Configure trusted IP addresses (BunkerWeb Cloud)
set_real_ip_from 4.233.128.18/32
set_real_ip_from 20.19.161.132/32

# Header to use for retrieving real IP
real_ip_header X-Real-IP;

# Alternative with X-Forwarded-For
# real_ip_header X-Forwarded-For;

server {
    listen 443 ssl http2;
    server_name example.com;

    # SSL configuration
    ssl_certificate /path/to/example.com.crt;
    ssl_certificate_key /path/to/example.com.key;

    location / {
        proxy_pass http://service1:8080;

        # Forward real IP headers to backend
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Log with real client IP
        access_log /var/log/nginx/access.log combined;
    }
}

# Custom log format with real IP
log_format real_ip '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent" '
                   'real_ip="$realip_remote_addr"';
```

</details>

##### Apache

<details>
<summary>Apache Configuration for REAL_IP</summary>

```apache
# Load mod_remoteip module
LoadModule remoteip_module modules/mod_remoteip.so

<VirtualHost *:443>
    ServerName example.com

    # SSL configuration
    SSLEngine on
    SSLCertificateFile /path/to/example.com.crt
    SSLCertificateKeyFile /path/to/example.com.key

    # Configure trusted IP addresses
    RemoteIPHeader X-Real-IP
    RemoteIPTrustedProxy 4.233.128.18/32
    RemoteIPTrustedProxy 20.19.161.132/32

    # Alternative with X-Forwarded-For
    # RemoteIPHeader X-Forwarded-For

    # Reverse proxy configuration
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Forward IP headers
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    # Logs with real IP
    LogFormat "%a %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined_real_ip
    CustomLog logs/access.log combined_real_ip
    ErrorLog logs/error.log
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>HAProxy Configuration for REAL_IP</summary>

```haproxy
global
    maxconn 4096
    log stdout local0

defaults
    mode http
    option httplog
    option dontlognull
    option forwardfor

    # Log format with real IP
    log-format "%ci:%cp [%t] %ft %b/%s %Tq/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"

frontend https_frontend
    bind *:443 ssl crt /etc/ssl/certs/

    # BunkerWeb Cloud IP whitelist
    acl bunkerweb_ips src 4.233.128.18/32 20.19.161.132/32
    http-request deny unless bunkerweb_ips

    # Capture real IP from headers
    capture request header X-Real-IP len 15
    capture request header X-Forwarded-For len 50

    # Routing
    acl is_example hdr(host) -i example.com
    use_backend app_servers if is_example

    default_backend app_servers

backend app_servers
    balance roundrobin

    # Add/preserve real IP headers
    http-request set-header X-Original-Forwarded-For %[req.hdr(X-Forwarded-For)]
    http-request set-header X-Client-IP %[req.hdr(X-Real-IP)]

    server app1 service1:8080 check
    server app2 service2:8080 check backup
```

</details>

##### Traefik

<details>
<summary>Traefik Configuration for REAL_IP</summary>

```yaml
# Configuration in dynamic.yml
http:
  middlewares:
    real-ip:
      ipWhiteList:
        sourceRange:
          - "4.233.128.18/32"
          - "20.19.161.132/32"
        ipStrategy:
          depth: 2  # Number of trusted proxies
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

**Configuration in traefik.yml (static):**

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

#### Testing and Validation

##### Configuration Verification

```bash
# Test 1: Check received headers
curl -H "X-Real-IP: 203.0.113.1" \
     -H "X-Forwarded-For: 203.0.113.1, 192.168.1.100" \
     https://example.com/test-ip

# Test 2: Analyze logs
tail -f /var/log/nginx/access.log | grep "203.0.113.1"

# Test 3: Test from different sources
curl -v https://example.com/whatismyip
```

#### REAL_IP Best Practices

1. **Security**: Only trust IP headers from known sources (BunkerWeb Cloud)
2. **Validation**: Always validate IP addresses received in headers
3. **Logging**: Log both proxy IP and real IP for debugging
4. **Fallback**: Always have a default value if headers are missing
5. **Testing**: Regularly test that IP detection works correctly
6. **Monitoring**: Monitor IP patterns to detect anomalies

#### REAL_IP Troubleshooting

##### Common Issues

1. **IP always shows BunkerWeb's**: Check trusted proxy configuration
2. **Missing headers**: Check BunkerWeb Cloud side configuration
3. **Invalid IPs**: Implement strict IP validation
4. **Incorrect logs**: Check log format and real_ip module configuration

##### Diagnostic Commands

__Test IP detection__

```bash
curl -H "X-Real-IP: 1.2.3.4" https://your-domain.com/debug-headers
```

### Monitoring and Observability

#### Grafana Access

Your managed Grafana instance gives you access to:

##### Available Metrics

1. **Traffic Overview**

  - Requests per second
  - HTTP status codes
  - Request geolocation
2. **Security**

  - Blocked attack attempts
  - Detected threat types
  - Triggered WAF rules
3. **Performance Metrics**

  - Request latency
  - Backend response time
  - Resource utilization

##### Available Logs

1. **Access Logs**: All HTTP/HTTPS requests
2. **Security Logs**: Security events and blocks
3. **Error Logs**: Application and system errors

##### Alert Configuration

Configure Grafana alerts for:

- Abnormal traffic spikes
- Increase in 5xx errors
- DDoS attack detection
- Backend health failures

### Best Practices

#### Security

1. **Use HTTPS** for all backend communication
2. **Implement an IP whitelist** if possible
3. **Configure appropriate timeouts**
4. **Enable compression** to optimize performance

#### Performance

1. **Optimize cache configuration**
2. **Use HTTP/2** on client side
3. **Configure health checks** for your backends
4. **Monitor metrics** regularly

### Troubleshooting

#### Common Issues

##### 1. SSL/TLS Error

**Symptom:** SSL certificate errors

**Solutions:**

```bash
# Check SNI configuration
openssl s_client -connect backend.com:443 -servername example.com

# Check backend certificates
openssl x509 -in certificate.crt -text -noout
```

##### 2. Backend Timeout

**Symptom:** 504 Gateway Timeout errors

**Solutions:**

- Increase `REVERSE_PROXY_CONNECT_TIMEOUT` & `REVERSE_PROXY_SEND_TIMEOUT`
- Check backend health
- Optimize application performance

##### 3. Routing Issues

**Symptom:** Wrong service being served

**Solutions:**

- Check `SERVER_NAME` configuration
- Validate SNI configuration
- Check `Host` headers

#### Diagnostic Commands

```bash
# Connectivity test
curl -v https://your-domain.com

# Test with custom headers
curl -H "Host: example.com" -v https://54984654.bunkerweb.cloud

# DNS verification
dig +trace example.com

# SSL test
openssl s_client -connect example.com:443 -servername example.com
```

#### Technical Support

For any technical assistance:

1. **Check logs** in Grafana
2. **Verify configuration** in BunkerWeb UI
3. **Contact support** with configuration details and error logs

## All-In-One (AIO) Image {#all-in-one-aio-image}

<figure markdown>
  ![AIO Architecture Graph Placeholder](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>BunkerWeb All-In-One Architecture (AIO)</figcaption>
</figure>

### Deployment {#deployment}

To deploy the all-in-one container, all you have to do is run the following command:

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6
```

By default, the container exposes:

- 8080/tcp for HTTP
- 8443/tcp for HTTPS
- 8443/udp for QUIC
- 7000/tcp for the web UI access without BunkerWeb in front (not recommended for production)
- 8888/tcp for the API when `SERVICE_API=yes` (internal use; prefer exposing it through BunkerWeb as a reverse proxy rather than publishing directly)

The All-In-One image comes with several built-in services, which can be controlled using environment variables:

- `SERVICE_UI=yes` (default) - Enables the web UI service
- `SERVICE_SCHEDULER=yes` (default) - Enables the Scheduler service
- `SERVICE_API=no` (default) - Enables the API service (FastAPI control plane)
- `AUTOCONF_MODE=no` (default) - Enables the autoconf service
- `USE_REDIS=yes` (default) - Enables the built-in [Redis](#redis-integration) instance
- `USE_CROWDSEC=no` (default) - [CrowdSec](#crowdsec-integration) integration is disabled by default
- `HIDE_SERVICE_LOGS=` (optional) - Comma-separated list of services to silence in container logs. Accepted values: `api`, `autoconf`, `bunkerweb`, `crowdsec`, `redis`, `scheduler`, `ui`, `nginx.access`, `nginx.error`, `modsec`. Logs still reach `/var/log/bunkerweb/<service>.log`.

A named volume (or bind mount) is required to persist the SQLite database, cache, and backups stored under `/data` inside the container:

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.6
    container_name: bunkerweb-aio
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp"
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Using a local folder for persistent data"
    The All-In-One container runs services as an **unprivileged user with UID 101 and GID 101**. This improves security: even if a component is compromised, it does not gain root (UID/GID 0) on the host.

    If you bind mount a **local folder**, ensure the directory permissions allow that unprivileged user to write data:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Or, if the folder already exists:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    When using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [Podman](https://podman.io/), container UIDs/GIDs are remapped. Check your subuid/subgid ranges first:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    For example, if the range starts at **100000**, the effective UID/GID becomes **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Or, if the folder already exists:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### API Integration

The All-In-One image embeds the BunkerWeb API. It is disabled by default and can be enabled by setting `SERVICE_API=yes`.

!!! warning "Security"
    The API is a privileged control plane. Do not expose it directly to the Internet. Keep it on an internal network, restrict source IPs with `API_WHITELIST_IPS`, require authentication (`API_TOKEN` or API users + Biscuit), and preferably access it through BunkerWeb as a reverse proxy on an unguessable path.

Quick enable (standalone) — publishes the API port; for testing only:

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
  bunkerity/bunkerweb-all-in-one:1.6.6
```

Recommended (behind BunkerWeb) — do not publish `8888`; reverse‑proxy it instead:

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.6
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
      api.example.com_REVERSE_PROXY_HOST: "http://127.0.0.1:8888" # Internal API endpoint

      # API settings
      SERVICE_API: "yes"
      # Set a strong token and whitelist only trusted IPs/networks (more details below)
      API_USERNAME: "changeme"
      API_PASSWORD: "StrongP@ssw0rd"
      API_ROOT_PATH: "/api-<unguessable>" # Match REVERSE_PROXY_URL

      # We deactivate the UI - change to "yes" to enable it
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

Details about authentication, permissions (ACL), rate limiting, TLS, and configuration options are available in the [API documentation](api.md).

### Accessing the Setup wizard

By default, the setup wizard is automagically launched when you run the AIO container for the first time. To access it, follow these steps:

1. **Start the AIO container** as [above](#deployment), ensuring `SERVICE_UI=yes` (default).
2. **Access the UI** via your main BunkerWeb endpoint, e.g. `https://your-domain`.

> Follow the next steps in the [Quickstart guide](quickstart-guide.md#complete-the-setup-wizard) to set up the Web UI.

### Redis Integration {#redis-integration}

The BunkerWeb **All-In-One** image includes Redis out-of-the-box for the [persistence of bans and reports](advanced.md#persistence-of-bans-and-reports). Keep in mind:

- The embedded Redis service only starts when `USE_REDIS=yes` **and** `REDIS_HOST` is left at its default (`127.0.0.1`/`localhost`).
- It listens on the container loopback interface, so it is available to processes inside the container but not from other containers or the host.
- Override `REDIS_HOST` only when you have an external Redis/Valkey endpoint to connect to—doing so prevents the embedded instance from launching.
- To disable Redis entirely, set `USE_REDIS=no`.
- Redis logs appear with the `[REDIS]` prefix in Docker logs and in `/var/log/bunkerweb/redis.log`.

### CrowdSec Integration {#crowdsec-integration}

The BunkerWeb **All-In-One** Docker image comes with CrowdSec fully integrated—no extra containers or manual setup required. Follow the steps below to enable, configure, and extend CrowdSec in your deployment.

By default, CrowdSec is **disabled**. To turn it on, simply add the `USE_CROWDSEC` environment variable:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6
```

* When `USE_CROWDSEC=yes`, the entrypoint will:

    1. **Register** and **start** the local CrowdSec agent (via `cscli`).
    2. **Install or upgrade** default collections & parsers.
    3. **Configure** the `crowdsec-bunkerweb-bouncer/v1.6` bouncer.

---

#### Default Collections & Parsers

On first startup (or after upgrading), these assets are automatically installed and kept up to date:

| Type           | Name                                    | Purpose                                                                                                                                                                                                                            |
| -------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Collection** | `bunkerity/bunkerweb`                   | Defend Nginx servers against a broad array of HTTP-based attacks, from brute-force to injection attempts.                                                                                                                          |
| **Collection** | `crowdsecurity/appsec-virtual-patching` | Delivers a dynamically updated WAF-style rule set targeting known CVEs, automatically patched daily to shield web applications from newly discovered vulnerabilities.                                                              |
| **Collection** | `crowdsecurity/appsec-generic-rules`    | Complements `crowdsecurity/appsec-virtual-patching` with heuristics for generic application-layer attack patterns—such as enumeration, path traversal, and automated probes—filling gaps where CVE-specific rules don’t yet exist. |
| **Parser**     | `crowdsecurity/geoip-enrich`            | Enriches events with GeoIP context                                                                                                                                                                                                 |

<details>
<summary><strong>How it works internally</strong></summary>

The entrypoint script invokes:

```bash
cscli hub update
cscli install collection bunkerity/bunkerweb
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

!!! info "Collection missing in Docker?"
    If `cscli collections list` inside the container still does not show `bunkerity/bunkerweb`, run `docker exec -it bunkerweb-aio cscli hub update` and then restart the container (`docker restart bunkerweb-aio`) to refresh the local hub cache.

---

#### Adding Extra Collections

Need more coverage? Define `CROWDSEC_EXTRA_COLLECTIONS` with a space-separated list of Hubb collections:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/apache2 crowdsecurity/mysql" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6
```

!!! info "How it works internally"

    The script loops through each name and installs or upgrades as needed—no manual steps required.

---

#### Disable Specific Parsers

If you want to keep the default setup but explicitly disable one or more parsers, provide a space-separated list via `CROWDSEC_DISABLED_PARSERS`:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_DISABLED_PARSERS="crowdsecurity/geoip-enrich foo/bar-parser" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6
```

Notes:
- The list is applied after required items are installed/updated; only the parsers you list are removed.
- Use hub slugs as shown by `cscli parsers list` (e.g., `crowdsecurity/geoip-enrich`).

---

#### AppSec Toggle

CrowdSec [AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) features—powered by the `appsec-virtual-patching` and `appsec-generic-rules` collections—are **enabled by default**.

To **disable** all AppSec (WAF/virtual-patching) functionality, set:

```bash
-e CROWDSEC_APPSEC_URL=""
```

This effectively turns off the AppSec endpoint so no rules are applied.

---

#### External CrowdSec API

If you operate a remote CrowdSec instance, point the container to your API:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_API="https://crowdsec.example.com:8000" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.6
```

* **Local registration** is skipped when `CROWDSEC_API` is not `127.0.0.1` or `localhost`.
* **AppSec** is disabled by default when using an external API. To enable it, set `CROWDSEC_APPSEC_URL` to your desired endpoint.
* Bouncer registration still occurs against the remote API.
* To reuse an existing bouncer key, supply `CROWDSEC_API_KEY` with your pre-generated token.

---

!!! tip "More options"
    For full coverage of all CrowdSec options (custom scenarios, logs, troubleshooting, and more), see the [BunkerWeb CrowdSec plugin docs](features.md#crowdsec) or visit the [official CrowdSec website](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs).

## Docker

<figure markdown>
  ![Overview](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker integration</figcaption>
</figure>

Using BunkerWeb as a [Docker](https://www.docker.com/) container offers a convenient and straightforward approach for testing and utilizing the solution, particularly if you are already familiar with Docker technology.

To facilitate your Docker deployment, we provide readily available prebuilt images on [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb), supporting multiple architectures. These prebuilt images are optimized and prepared for use on the following architectures:

- x64 (64-bit)
- x86
- armv8 (ARM 64-bit)
- armv7 (ARM 32-bit)

By accessing these prebuilt images from Docker Hub, you can quickly pull and run BunkerWeb within your Docker environment, eliminating the need for extensive configuration or setup processes. This streamlined approach allows you to focus on leveraging the capabilities of BunkerWeb without unnecessary complexities.

Whether you're conducting tests, developing applications, or deploying BunkerWeb in production, the Docker containerization option provides flexibility and ease of use. Embracing this method empowers you to take full advantage of BunkerWeb's features while leveraging the benefits of Docker technology.

```shell
docker pull bunkerity/bunkerweb:1.6.6
```

Docker images are also available on [GitHub packages](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) and can be downloaded using the `ghcr.io` repository address:

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.6
```

Key concepts for Docker integration include:

- **Environment variables**: Configure BunkerWeb easily using environment variables. These variables allow you to customize various aspects of BunkerWeb's behavior, such as network settings, security options, and other parameters.
- **Scheduler container**: Manage configuration and execute jobs using a dedicated container called the [scheduler](concepts.md#scheduler).
- **Networks**: Docker networks play a vital role in the integration of BunkerWeb. These networks serve two main purposes: exposing ports to clients and connecting to upstream web services. By exposing ports, BunkerWeb can accept incoming requests from clients, allowing them to access the protected web services. Additionally, by connecting to upstream web services, BunkerWeb can efficiently route and manage traffic, providing enhanced security and performance.

!!! info "Database backend"
    Please note that our instructions assume you are using SQLite as the default database backend, as configured by the `DATABASE_URI` setting. However, other database backends are also supported. See the docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations) of the repository for more information.

### Environment variables

Settings are passed to the Scheduler using Docker environment variables:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
...
```

!!! info "Full list"
    For the complete list of environment variables, see the [settings section](features.md) of the documentation.

!!! tip "Skipping labelled containers"
    When a container should be ignored by autoconf, set `DOCKER_IGNORE_LABELS` on the controller. Provide a space- or comma-separated list of label keys (for example `bunkerweb.SERVER_NAME`) or just the suffix (`SERVER_NAME`). Any container or custom-config source carrying a matching label is skipped during discovery, and the label is ignored when translating settings.

### Using Docker secrets

Instead of passing sensitive settings via environment variables, you can store them as Docker secrets. For each setting you want to secure, create a Docker secret with the name matching the setting key (in uppercase). BunkerWeb's entrypoint scripts automatically load secrets from `/run/secrets` and export them as environment variables.

Example:
```bash
# Create a Docker secret for ADMIN_PASSWORD
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

Mount the secrets when deploying:
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

This ensures sensitive settings are kept out of the environment and logs.

### Scheduler

The [scheduler](concepts.md#scheduler) runs in its own container, which is also available on Docker Hub:

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.6
```

!!! info "BunkerWeb settings"

    Since version `1.6.0`, the Scheduler container is where you define the settings for BunkerWeb. The Scheduler then pushes the configuration to the BunkerWeb container.

    ⚠ **Important**: All API-related settings (like `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME`, `API_WHITELIST_IP`, and `API_TOKEN` if you use it) **must also be defined in the BunkerWeb container**. The settings must be mirrored in both containers; otherwise, the BunkerWeb container will not accept API requests from the Scheduler.

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for both containers
      API_HTTP_PORT: "5000" # Default value
      API_LISTEN_IP: "0.0.0.0" # Default value
      API_SERVER_NAME: "bwapi" # Default value
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Set this according to your network settings
      # Optional token; if set, Scheduler sends Authorization: Bearer <token>
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
        environment:
          # This will set the API settings for the BunkerWeb container
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.6
        environment:
          # This will set the API settings for the Scheduler container
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like backups
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

A volume is needed to store the SQLite database and backups used by the scheduler:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Using a local folder for persistent data"
    The scheduler runs as an **unprivileged user with UID 101 and GID 101** inside the container. This enhances security: in case a vulnerability is exploited, the attacker won't have full root (UID/GID 0) privileges.

    However, if you use a **local folder for persistent data**, you must **set the correct permissions** so the unprivileged user can write data to it. For example:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternatively, if the folder already exists:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [Podman](https://podman.io/), UIDs and GIDs in the container will be mapped to different ones on the host. You will first need to check your initial subuid and subgid:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    For example, if you have a value of **100000**, the mapped UID/GID will be **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Or if the folder already exists:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### Networks

By default, the BunkerWeb container listens (inside the container) on **8080/tcp** for **HTTP**, **8443/tcp** for **HTTPS**, and **8443/udp** for **QUIC**.

!!! warning "Privileged ports in rootless mode or when using Podman"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) and want to redirect privileged ports (< 1024) like 80 and 443 to BunkerWeb, please refer to the prerequisites [here](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    If you are using [Podman](https://podman.io/), you can lower the minimum number for unprivileged ports:
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

The typical BunkerWeb stack when using Docker integration contains the following containers:

- BunkerWeb
- Scheduler
- Your services

For defense-in-depth purposes, we strongly recommend creating at least three different Docker networks:

- `bw-services`: for BunkerWeb and your web services
- `bw-universe`: for BunkerWeb and the scheduler
- `bw-db`: for the database (if you are using one)

To secure communication between the scheduler and the BunkerWeb API, **authorize API calls**. Use the `API_WHITELIST_IP` setting to specify allowed IP addresses and subnets. For stronger protection, set `API_TOKEN` in both containers; the scheduler will automatically include `Authorization: Bearer <token>`.

**It is strongly recommended to use a static subnet for the `bw-universe` network** to enhance security. By implementing these measures, you can ensure that only authorized sources can access the BunkerWeb API, reducing the risk of unauthorized access or malicious activities:

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  API_TOKEN: "" # Optional API token
  # Optional API token for authenticated API access
  API_TOKEN: ""

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6
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
    image: bunkerity/bunkerweb-scheduler:1.6.6
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
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
        - subnet: 10.20.30.0/24 # Static subnet so only authorized sources can access the BunkerWeb API
  bw-services:
    name: bw-services
```

### Full compose file

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6
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
    image: bunkerity/bunkerweb-scheduler:1.6.6
    depends_on:
      - bunkerweb
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
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
        - subnet: 10.20.30.0/24 # Static subnet so only authorized sources can access the BunkerWeb API
  bw-services:
    name: bw-services
```

### Build from source

Alternatively, if you prefer a more hands-on approach, you have the option to build the Docker image directly from the [source](https://github.com/bunkerity/bunkerweb). Building the image from source gives you greater control and customization over the deployment process. However, please note that this method may take some time to complete, depending on your hardware configuration (you can take a coffee ☕ if needed).

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
  ![Overview](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Linux integration</figcaption>
</figure>

Supported Linux distributions for BunkerWeb (amd64/x86_64 and arm64/aarch64 architectures) include:

- Debian 12 "Bookworm"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41, 42 and 43
- Red Hat Enterprise Linux (RHEL) 8, 9 and 10

### Easy installation script

For a simplified installation experience, BunkerWeb provides an easy install script that automatically handles the entire setup process, including NGINX installation, repository configuration, and service setup.

#### Quick start

To get started, download the installation script and its checksum, then verify the script's integrity before running it.

```bash
# Download the script and its checksum
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.6/install-bunkerweb.sh
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.6/install-bunkerweb.sh.sha256

# Verify the checksum
sha256sum -c install-bunkerweb.sh.sha256

# If the check is successful, run the script
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! danger "Security Notice"
    **Always verify the integrity of the installation script before running it.**

    Download the checksum file and use a tool like `sha256sum` to confirm the script has not been altered or tampered with.

    If the checksum verification fails, **do not execute the script**—it may be unsafe.

#### How It Works

The easy install script is a powerful tool designed to streamline the setup of BunkerWeb on a fresh Linux system. It automates the following key steps:

1.  **System Analysis**: Detects your operating system and verifies it against the list of supported distributions.
2.  **Installation Customization**: In interactive mode, it prompts you to choose an installation type (All-In-One, Manager, Worker, etc.) and decide whether to enable the web-based setup wizard.
3.  **Optional Integrations**: Offers to automatically install and configure the [CrowdSec Security Engine](#crowdsec-integration-with-the-script).
4.  **Dependency Management**: Installs the correct version of NGINX required by BunkerWeb from official sources and locks the version to prevent unintended upgrades.
5.  **BunkerWeb Installation**: Adds the BunkerWeb package repository, installs the necessary packages, and locks the version.
6.  **Service Configuration**: Sets up and enables the `systemd` services corresponding to your chosen installation type.
7.  **Post-install Guidance**: Provides clear next steps to help you get started with your new BunkerWeb instance.

#### Interactive Installation

When run without any options, the script enters an interactive mode that guides you through the setup process. You will be asked to make the following choices:

1.  **Installation Type**: Select the components you want to install.
    *   **Full Stack (default)**: An all-in-one installation including BunkerWeb, the Scheduler, and the Web UI.
    *   **Manager**: Installs the Scheduler and Web UI, intended to manage one or more remote BunkerWeb workers. Can optionally include the API service.
    *   **Worker**: Installs only the BunkerWeb instance, which can be managed by a remote Manager.
    *   **Scheduler Only**: Installs only the Scheduler component.
    *   **Web UI Only**: Installs only the Web UI component.
    *   **API Only**: Installs only the API service for programmatic access.
2.  **Setup Wizard**: Choose whether to enable the web-based configuration wizard. This is highly recommended for first-time users.
3.  **CrowdSec Integration**: Opt-in to install the CrowdSec security engine for advanced, real-time threat protection. Available for Full Stack installations only.
4.  **CrowdSec AppSec**: If you choose to install CrowdSec, you can also enable the Application Security (AppSec) component, which adds WAF capabilities.
5.  **DNS Resolvers**: For Full Stack, Manager, and Worker installations, you can optionally specify custom DNS resolver IPs.
6.  **Internal API HTTPS**: For Full Stack, Manager, and Worker installations, choose whether to enable HTTPS for internal API communication between the scheduler/manager and BunkerWeb/worker instances (default: HTTP only).
7.  **API Service**: For Full Stack and Manager installations, choose whether to enable the optional external API service. It is disabled by default on Linux installations.

!!! info "Manager and Scheduler installations"
    If you choose the **Manager** or **Scheduler Only** installation type, you will also be prompted to provide the IP addresses or hostnames of your BunkerWeb worker instances.

#### Command-Line Options

For non-interactive or automated setups, the script can be controlled with command-line flags:

**General Options:**

| Option                  | Description                                                           |
| ----------------------- | --------------------------------------------------------------------- |
| `-v, --version VERSION` | Specifies the BunkerWeb version to install (e.g., `1.6.6`).           |
| `-w, --enable-wizard`   | Enables the setup wizard.                                             |
| `-n, --no-wizard`       | Disables the setup wizard.                                            |
| `-y, --yes`             | Runs in non-interactive mode using default answers for all prompts.   |
| `-f, --force`           | Forces the installation to proceed even on an unsupported OS version. |
| `-q, --quiet`           | Silent installation (suppress output).                                |
| `--api`, `--enable-api` | Enables the API (FastAPI) systemd service (disabled by default).      |
| `--no-api`              | Explicitly disables the API service.                                  |
| `-h, --help`            | Displays the help message with all available options.                 |
| `--dry-run`             | Show what would be installed without doing it.                        |

**Installation Types:**

| Option             | Description                                                              |
| ------------------ | ------------------------------------------------------------------------ |
| `--full`           | Full stack installation (BunkerWeb, Scheduler, UI). This is the default. |
| `--manager`        | Installs the Scheduler and UI to manage remote workers.                  |
| `--worker`         | Installs only the BunkerWeb instance.                                    |
| `--scheduler-only` | Installs only the Scheduler component.                                   |
| `--ui-only`        | Installs only the Web UI component.                                      |
| `--api-only`       | Installs only the API service (port 8000).                               |

**Security Integrations:**

| Option              | Description                                                         |
| ------------------- | ------------------------------------------------------------------- |
| `--crowdsec`        | Install and configure CrowdSec security engine.                     |
| `--no-crowdsec`     | Skip CrowdSec installation.                                         |
| `--crowdsec-appsec` | Install CrowdSec with AppSec component (includes WAF capabilities). |

**Advanced Options:**

| Option                      | Description                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------- |
| `--instances "IP1 IP2"`     | Space-separated list of BunkerWeb instances (required for manager/scheduler modes). |
| `--manager-ip IPs`          | Manager/Scheduler IPs to whitelist (required for worker in non-interactive mode).   |
| `--dns-resolvers "IP1 IP2"` | Custom DNS resolver IPs (for full, manager, or worker installations).               |
| `--api-https`               | Enable HTTPS for internal API communication (default: HTTP only).                   |
| `--backup-dir PATH`         | Directory to store automatic backup before upgrade.                                 |
| `--no-auto-backup`          | Skip automatic backup (you MUST have done it manually).                             |

**Example Usage:**

```bash
# Run in interactive mode (recommended for most users)
sudo ./install-bunkerweb.sh

# Non-interactive installation with defaults (full stack, wizard enabled)
sudo ./install-bunkerweb.sh --yes

# Install a Worker node without the setup wizard
sudo ./install-bunkerweb.sh --worker --no-wizard

# Install a specific version
sudo ./install-bunkerweb.sh --version 1.6.6

# Manager setup with remote worker instances (instances required)
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# Manager with HTTPS internal API communication
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11" --api-https

# Worker with custom DNS resolvers and HTTPS internal API
sudo ./install-bunkerweb.sh --worker --dns-resolvers "1.1.1.1 1.0.0.1" --api-https

# Full installation with CrowdSec and AppSec
sudo ./install-bunkerweb.sh --crowdsec-appsec

# Silent non-interactive installation
sudo ./install-bunkerweb.sh --quiet --yes

# Preview installation without executing
sudo ./install-bunkerweb.sh --dry-run

# Enable the API during easy install (non-interactive)
sudo ./install-bunkerweb.sh --yes --api

# Error: CrowdSec cannot be used with worker, scheduler-only, ui-only, or api-only installations
# sudo ./install-bunkerweb.sh --worker --crowdsec  # This will fail

# Error: API service not available for worker installations
# sudo ./install-bunkerweb.sh --worker --api  # This will fail

# Error: Instances required for manager in non-interactive mode
# sudo ./install-bunkerweb.sh --manager --yes  # This will fail without --instances

# Install API-only mode
sudo ./install-bunkerweb.sh --api-only

# Manager with API service enabled
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11" --api
```

!!! warning "Important Notes on Option Compatibility"

    **CrowdSec Limitations:**

    - CrowdSec options (`--crowdsec`, `--crowdsec-appsec`) are only compatible with `--full` (default) installation type
    - They cannot be used with `--manager`, `--worker`, `--scheduler-only`, `--ui-only`, or `--api-only` installations

    **API Service Availability:**

    - The external API service (port 8000) is available for `--full` and `--manager` installation types
    - It is not available for `--worker`, `--scheduler-only`, or `--ui-only` installations
    - Use `--api-only` for a dedicated API service installation

    **Instances Requirements:**

    - The `--instances` option is only valid with `--manager` and `--scheduler-only` installation types
    - When using `--manager` or `--scheduler-only` with `--yes` (non-interactive mode), the `--instances` option is mandatory
    - Format: `--instances "192.168.1.10 192.168.1.11 192.168.1.12"`

    **Interactive vs Non-Interactive:**

    - Interactive mode (default) will prompt for missing required values
    - Non-interactive mode (`--yes`) requires all necessary options to be provided via command line

#### CrowdSec Integration with the Script {#crowdsec-integration-with-the-script}

If you opt to install CrowdSec during the interactive setup, the script fully automates its integration with BunkerWeb:

- It adds the official CrowdSec repository and installs the agent.
- It creates a new acquisition file to make CrowdSec parse BunkerWeb's logs (`access.log`, `error.log`, and `modsec_audit.log`).
- It installs essential collections (`bunkerity/bunkerweb`) and parsers (`crowdsecurity/geoip-enrich`).
- It registers a bouncer for BunkerWeb and automatically configures the API key in `/etc/bunkerweb/variables.env`.
- If you also select the **AppSec Component**, it installs the `appsec-virtual-patching` and `appsec-generic-rules` collections and configures the AppSec endpoint for BunkerWeb.

This provides a seamless, out-of-the-box integration for powerful intrusion prevention.

#### RHEL considerations

!!! warning "External database support on RHEL-based systems"
    If you plan to use an external database (recommended for production), you must install the appropriate database client package:

    ```bash
    # For MariaDB
    sudo dnf install mariadb

    # For MySQL
    sudo dnf install mysql

    # For PostgreSQL
    sudo dnf install postgresql
    ```

    This is required for the BunkerWeb Scheduler to connect to your external database.

#### After installation

Once installation is complete, the script provides mode-specific next steps to help you get started with your BunkerWeb deployment.

**Installation Modes Overview:**

| Mode           | Components                 | Ports                                                                              | Configuration Files                                                                                                         |
| -------------- | -------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Full Stack     | BunkerWeb + Scheduler + UI | HTTP/HTTPS (80/443), UI (7000), Internal API (5000), Optional: External API (8000) | `/etc/bunkerweb/variables.env`, `/etc/bunkerweb/scheduler.env`, `/etc/bunkerweb/ui.env`, Optional: `/etc/bunkerweb/api.env` |
| Manager        | Scheduler + UI             | UI (7000), Internal API (5000), Optional: External API (8000)                      | `/etc/bunkerweb/scheduler.env`, `/etc/bunkerweb/ui.env`, `/etc/bunkerweb/variables.env`, Optional: `/etc/bunkerweb/api.env` |
| Worker         | BunkerWeb only             | HTTP/HTTPS (80/443)                                                                | `/etc/bunkerweb/variables.env`                                                                                              |
| Scheduler Only | Scheduler                  | Internal API (5000)                                                                | `/etc/bunkerweb/scheduler.env`, `/etc/bunkerweb/variables.env`                                                              |
| UI Only        | Web UI                     | UI (7000)                                                                          | `/etc/bunkerweb/ui.env`                                                                                                     |
| API Only       | External API               | API (8000)                                                                         | `/etc/bunkerweb/api.env`                                                                                                    |

**With setup wizard enabled (Full Stack or Manager):**

1. Access the setup wizard at: `https://your-server-ip/setup` (Full Stack) or `http://your-server-ip:7000/setup` (Manager)
2. Follow the guided configuration to set up your first protected service
3. Configure SSL/TLS certificates and other security settings

**Without setup wizard:**

Depending on your installation type:

- **Full Stack**: Edit `/etc/bunkerweb/variables.env` for BunkerWeb settings, then restart: `sudo systemctl restart bunkerweb-scheduler`
- **Manager**: Configure the database connection (`DATABASE_URI`) in `/etc/bunkerweb/scheduler.env` and manage worker instances via the Web UI at `http://your-server-ip:7000`
- **Worker**: Edit `/etc/bunkerweb/variables.env` for BunkerWeb settings, then restart: `sudo systemctl restart bunkerweb`
- **Scheduler Only**: Configure `DATABASE_URI` in `/etc/bunkerweb/scheduler.env`, then restart: `sudo systemctl restart bunkerweb-scheduler`
- **UI Only**: Configure `DATABASE_URI` in `/etc/bunkerweb/ui.env`, then restart: `sudo systemctl restart bunkerweb-ui`
- **API Only**: Configure `DATABASE_URI` in `/etc/bunkerweb/api.env`, then restart: `sudo systemctl restart bunkerweb-api`

!!! info "Database Configuration"
    For Manager, Scheduler, UI, and API installations, you must configure a shared database using the `DATABASE_URI` setting. The format is: `mariadb+pymysql://user:password@host:port/database` (or `postgresql://`, `mysql+pymysql://`, `sqlite:////path/to/db.sqlite`).

### Installation using package manager

Please ensure that you have **NGINX 1.28.0 installed before installing BunkerWeb**. For all distributions, except Fedora, it is mandatory to use prebuilt packages from the [official NGINX repository](https://nginx.org/en/linux_packages.html). Compiling NGINX from source or using packages from different repositories will not work with the official prebuilt packages of BunkerWeb. However, you have the option to build BunkerWeb from source.

=== "Debian Bookworm/Trixie"

    The first step is to add NGINX official repository:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.28.0:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.6:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.6
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    The first step is to add NGINX official repository:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    You should now be able to install NGINX 1.28.0:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev version"
        If you use the `testing` or `dev` version, you will need to add the `force-bad-version` directive to your `/etc/dpkg/dpkg.cfg` file before installing BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.6:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.6
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `apt upgrade`, you can use the following command:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora Update Testing"
        If you can't find the NGINX version listed in the stable repository, you can enable the `updates-testing` repository:

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora already provides NGINX 1.28.0 that we support

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.0
    ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.6:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y --allowerasing bunkerweb-1.6.6
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    The first step is to add NGINX official repository. Create the following file at `/etc/yum.repos.d/nginx.repo`:

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

    You should now be able to install NGINX 1.28.0:

    ```shell
    sudo dnf install --allowerasing nginx-1.28.0
    ```

    !!! example "Disable the setup wizard"
        If you don't want to use the setup wizard of the web UI when BunkerWeb is installed, export the following variable:

        ```shell
        export UI_WIZARD=no
        ```

    And finally install BunkerWeb 1.6.6:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.6
    ```

    To prevent upgrading NGINX and/or BunkerWeb packages when executing `dnf upgrade`, you can use the following command:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### Configuration and service

Manual configuration of BunkerWeb is done by editing the `/etc/bunkerweb/variables.env` file:

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

When installed, BunkerWeb comes with three services `bunkerweb`, `bunkerweb-scheduler` and `bunkerweb-ui` that you can manage using `systemctl`.

If you manually edit the BunkerWeb configuration using `/etc/bunkerweb/variables.env` a restart of the `bunkerweb-scheduler` service will be enough to generate and reload the configuration without any downtime. But depending on the case (such as changing listening ports) you might need to restart the `bunkerweb` service.

### High availability

The scheduler can be detached from the BunkerWeb instance to provide high availability. In this case, the scheduler will be installed on a separate server and will be able to manage multiple BunkerWeb instances.

#### Manager

To install only the scheduler on a server, you can export the following variables before executing the BunkerWeb installation:

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

Alternatively, you can also export the following variables to only enable the scheduler:

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

#### Worker

On another server, to install only BunkerWeb, you can export the following variables before executing the BunkerWeb installation:

```shell
export WORKER_MODE=yes
```

Alternatively, you can also export the following variables to only enable BunkerWeb:

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

#### Web UI

The Web UI can be installed on a separate server to provide a dedicated interface for managing BunkerWeb instances. To install only the Web UI, you can export the following variables before executing the BunkerWeb installation:

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

## Docker autoconf

<figure markdown>
  ![Overview](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Docker autoconf integration</figcaption>
</figure>

!!! info "Docker integration"
    The Docker autoconf integration is an "evolution" of the Docker one. Please read the [Docker integration section](#docker) first if needed.

An alternative approach is available to address the inconvenience of recreating the container every time there is an update. By utilizing another image called **autoconf**, you can automate the real-time reconfiguration of BunkerWeb without the need for container recreation.

To leverage this functionality, instead of defining environment variables for the BunkerWeb container, you can add **labels** to your web application containers. The **autoconf** image will then listen for Docker events and seamlessly handle the configuration updates for BunkerWeb.

This "*automagical*" process simplifies the management of BunkerWeb configurations. By adding labels to your web application containers, you can delegate the reconfiguration tasks to **autoconf** without the manual intervention of container recreation. This streamlines the update process and enhances convenience.

By adopting this approach, you can enjoy real-time reconfiguration of BunkerWeb without the hassle of container recreation, making it more efficient and user-friendly.

!!! info "Multisite mode"
    The Docker autoconf integration implies the use of **multisite mode**. Please refer to the [multisite section](concepts.md#multisite-mode) of the documentation for more information.

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations) of the repository for more information.

To enable automated configuration updates, include an additional container called `bw-autoconf` in the stack. This container hosts the autoconf service, which manages dynamic configuration changes for BunkerWeb.

To support this functionality, use a dedicated "real" database backend (e.g., MariaDB, MySQL, or PostgreSQL) for synchronized configuration storage. By integrating `bw-autoconf` and a suitable database backend, you establish the infrastructure for seamless automated configuration management in BunkerWeb.

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both containers
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.6
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    labels:
      - "bunkerweb.INSTANCE=yes" # Mandatory label for the autoconf service to identify the BunkerWeb instance
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.6
    depends_on:
      - bunkerweb
      - bw-docker
    environment:
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
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
    # We set the max allowed packet size to avoid issues with large queries
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
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

!!! info "Database in the `bw-db` network"
    The database container is intentionally not included in the `bw-universe` network. It is used by the `bw-autoconf` and `bw-scheduler` containers rather than directly by BunkerWeb. Therefore, the database container is part of the `bw-db` network, which enhances security by making external access to the database more challenging. **This deliberate design choice helps safeguard the database and strengthens the overall security perspective of the system**.

!!! warning "Using Docker in rootless mode"
    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless), you will need to replace the mount of the docker socket with the following value: `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Autoconf services

Once the stack is set up, you will be able to create the web application container and add the settings as labels using the "bunkerweb." prefix in order to automatically set up BunkerWeb:

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

### Namespaces {#namespaces}

Starting from version `1.6.0`, BunkerWeb's Autoconf stacks now support namespaces. This feature enables you to manage multiple "*clusters*" of BunkerWeb instances and services on the same Docker host. To take advantage of namespaces, simply set the `NAMESPACE` label on your services. Here's an example:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the service
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace behavior"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to specific namespaces, you can set the `NAMESPACES` environment variable in the `bw-autoconf` service:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the BunkerWeb instance so the autoconf service can detect it
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # Only listen to these namespaces
    ...
    ```

    Keep in mind that the `NAMESPACES` environment variable is a space-separated list of namespaces.

!!! warning "Namespace specifications"

    There can only be **one database** and **one Scheduler** per namespace. If you try to create multiple databases or Schedulers in the same namespace, the configurations will end up conflicting with each other.

    The Scheduler doesn't need the `NAMESPACE` label to work properly. It will only need the `DATABASE_URI` setting properly configured so that it can access the same database as the autoconf service.

## Kubernetes

<figure markdown>
  ![Overview](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Kubernetes integration</figcaption>
</figure>

To automate the configuration of BunkerWeb instances in a Kubernetes environment,
the autoconf service serves as an [Ingress controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/).
It configures the BunkerWeb instances based on [Ingress resources](https://kubernetes.io/docs/concepts/services-networking/ingress/)
and also monitors other Kubernetes objects, such as [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/), for custom configurations.

!!! info "ConfigMap reconciliation"
    - The ingress controller only manages ConfigMaps that carry the `bunkerweb.io/CONFIG_TYPE` annotation.
    - Add `bunkerweb.io/CONFIG_SITE` when you want to scope the configuration to a single service (the server name must already exist);
      omit it to apply the configuration globally.
    - Removing the annotation or deleting the ConfigMap removes the related custom configuration from BunkerWeb.

For an optimal setup, it is recommended to define BunkerWeb as a **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)**,
which ensures that a pod is created on all nodes,
while the **autoconf and scheduler** are defined as **single replicated [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)**.

Given the presence of multiple BunkerWeb instances,
it is necessary to establish a shared data store implemented as a [Redis](https://redis.io/) or [Valkey](https://valkey.io/) service.
This service will be utilized by the instances to cache and share data among themselves.
Further information about the Redis/Valkey settings can be found [here](features.md#redis).

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend,
    as configured by the `DATABASE_URI` setting.
    However, we understand that you may prefer to utilize alternative backends for your Docker integration.
    If that is the case, rest assured that other database backends are still possible.
    See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations)
    of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Please ensure that the autoconf services have access to the Kubernetes API.
It is recommended to utilize [RBAC authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) for this purpose.

!!! warning "Custom CA for Kubernetes API"
    If you use a custom CA for your Kubernetes API, you can mount a bundle file containing your intermediate(s) and root certificates on the ingress controller and set the `KUBERNETES_SSL_CA_CERT` environment value to the path of the bundle inside the container. Alternatively, even if it's not recommended, you can disable certificate verification by setting the `KUBERNETES_SSL_VERIFY` environment variable of the ingress controller to `no` (default is `yes`).

Additionally, **it is crucial to set the `KUBERNETES_MODE` environment variable to `yes` when utilizing the Kubernetes integration**. This variable is mandatory for proper functionality.

### Installation methods

#### Using helm chart (recommended)

The recommended way to install Kubernetes is to use the Helm chart available at `https://repo.bunkerweb.io/charts`:

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

You can then use the bunkerweb helm chart from that repository:

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

The full list of values are listed in the [charts/bunkerweb/values.yaml file](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) of the [bunkerity/bunkerweb-helm repository](https://github.com/bunkerity/bunkerweb-helm).

#### Sidecar Container + Helm

This documentation explains how to deploy BunkerWeb as a sidecar to protect your Kubernetes applications. In this architecture, each application has its own BunkerWeb container acting as a security reverse proxy.

##### Architecture

```mermaid
flowchart TB

  %% ---------- Styles ----------
  classDef scheduler     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef podContainer  fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:6 3,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;

  %% ---------- Top: Scheduler ----------
  SCHED["BunkerWeb Scheduler (centralized)<br/>+ UI + MariaDB + Redis"]:::scheduler

  %% ---------- Pods Group ----------
  subgraph PODS["Pods"]
    %% Application Pod 1 ----------
    subgraph POD1["Application Pod"]
      BW1["BunkerWeb"]:::component
      APP1["Application<br/>(port 80)"]:::component
      BW1 -->|legitimate requests| APP1
    end
    class POD1 podContainer

    %% Application Pod 2 ----------
    subgraph POD2["Application Pod"]
      BW2["BunkerWeb"]:::component
      APP2["Application<br/>(port XX)"]:::component
      BW2 -->|legitimate requests| APP2
    end
    class POD2 podContainer
  end

  %% ---------- Load Balancer (bottom) ----------
  LB["Load Balancer"]:::lb

  %% ---------- Wiring (visible, semantic) ----------
  %% The Scheduler controls the BunkerWeb instances (API)
  SCHED -->|API 5000| BW1
  SCHED -->|API 5000| BW2

  %% The load balancer sends traffic to BunkerWeb
  LB -->|HTTP/HTTPS| BW1
  LB -->|HTTP/HTTPS| BW2

  %% ---------- Layout helper (hidden) ----------
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
  tag: "1.6.5"
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
  tag: "1.6.5"
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
          image: bunkerity/bunkerweb:1.6.6-rc2
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


#### Full YAML files

Instead of using the helm chart, you can also use the YAML boilerplates inside the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations) of the GitHub repository. Please note that we highly recommend to use the helm chart instead.

### Ingress resources

Once the BunkerWeb Kubernetes stack is successfully set up and operational (refer to the autoconf logs for detailed information), you can proceed with deploying web applications within the cluster and declaring your Ingress resource.

It is important to note that the BunkerWeb settings need to be specified as annotations for the Ingress resource. For the domain part, please use the special value **`bunkerweb.io`**. By including the appropriate annotations, you can configure BunkerWeb accordingly for the Ingress resource.

!!! tip "Ignoring noisy annotations"
    When some annotations should not impact autoconf, set `KUBERNETES_IGNORE_ANNOTATIONS` on the controller deployment. Provide a space- or comma-separated list of annotation keys (for example `bunkerweb.io/EXTRA_FOO`) or just the suffix (`EXTRA_FOO`). Matching annotations are stripped from ingress-derived settings, and pods carrying them are skipped entirely during instance discovery.

!!! info "TLS support"
    BunkerWeb ingress controller fully supports custom HTTPS certificates using the tls spec as shown in the example. Configuring solutions such as `cert-manager` to automatically generate tls secrets is out of the scope of this documentation.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # Will be applied to all host in this ingress
    bunkerweb.io/MY_SETTING: "value"
    # Will only be applied to the www.example.com host
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  # TLS is optional, you can also use builtin Let's Encrypt for example
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

### Namespaces {#namespaces_1}

Starting from version `1.6.0`, BunkerWeb's autoconf stacks now support namespaces. This feature enables you to manage multiple clusters of BunkerWeb instances and services on the same Kubernetes cluster. To take advantage of namespaces, simply set the `namespace` metadata field on your BunkerWeb instances and services. Here's an example:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Set the namespace for the BunkerWeb instance
...
```

!!! info "Namespace behavior"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to specific namespaces, you can set the `NAMESPACES` environment variable in the `bunkerweb-controller` deployment:

    ```yaml
    ...
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
      namespace: my-namespace # Set the namespace for the Controller
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
              image: bunkerity/bunkerweb-autoconf:1.6.6
              imagePullPolicy: Always
              env:
                - name: NAMESPACES
                  value: "my-namespace my-other-namespace" # Only listen to these namespaces
                ...
    ...
    ```

    Keep in mind that the `NAMESPACES` environment variable is a space-separated list of namespaces.

!!! warning "Namespace specifications"

    There can only be **one database** and **one Scheduler** per namespace. If you try to create multiple databases or Schedulers in the same namespace, the configurations will end up conflicting with each other.

    The Scheduler doesn't need the `NAMESPACE` annotation to work properly. It will only need the `DATABASE_URI` setting properly configured so that it can access the same database as the autoconf service.

### Ingress class

When installed using the official methods in the documentation, BunkerWeb comes with the following `IngressClass` definition:

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

In order to restrict the `Ingress` resources monitored by the ingress controller, you can set the `KUBERNETES_INGRESS_CLASS` environment variable with the value `bunkerweb`. Then, you can leverage the `ingressClassName` directive in your `Ingress` definitions:

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

### Custom domain name

If you use a custom domain name for your Kubernetes cluster different than the default `kubernetes.local` one, you can set the value using the `KUBERNETES_DOMAIN_NAME` environment variable on the scheduler container.

### Use with existing ingress controller

!!! info "Keeping both existing ingress controller and BunkerWeb"

    This is a use-case where you want to keep an existing ingress controller such as the nginx one. Typical traffic flow will be: Load Balancer => Ingress Controller => BunkerWeb => Application.

#### nginx ingress controller install

Install ingress nginx helm repo:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

Install nginx ingress controller with default values (might not work on your own cluster out-of-the-box, please check the [documentation](https://kubernetes.github.io/ingress-nginx/)):

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

Extract IP address of LB:

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Setup DNS entries to IP of LB (e.g `bunkerweb` subdomain for BW UI and `myapp` for application):

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

**BunkerWeb install**

Install BunkerWeb helm repo:

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

Create `values.yaml` file:

```yaml
# Here we will setup the values needed to setup BunkerWeb behind an existing ingress controller
# Traffic flow with BW: LB => existing Ingress Controller => BunkerWeb => Service
# Traffic flow without BW: LB => existing Ingress Controller => Service

# Global settings
settings:
  misc:
    # Replace with your DNS resolver
    # to get it: kubectl exec in a random pod then cat /etc/resolv.conf
    # if you have an IP as nameserver then do a reverse DNS lookup: nslookup <IP>
    # most of the time it's coredns.kube-system.svc.cluster.local or kube-dns.kube-system.svc.cluster.local
    dnsResolvers: "kube-dns.kube-system.svc.cluster.local"
  kubernetes:
    # We only consider Ingress resources with ingressClass bunkerweb to avoid conflicts with existing ingress controller
    ingressClass: "bunkerweb"
    # Optional: you can choose namespace(s) where BunkerWeb will listen for Ingress/ConfigMap changes
    # Default (blank value) is all namespaces
    namespaces: ""

# Override the bunkerweb-external service type to ClusterIP
# Since we don't need to expose it to the outside world
# We will use the existing ingress controller to route traffic to BunkerWeb
service:
  type: ClusterIP

# BunkerWeb settings
bunkerweb:
  tag: 1.6.6

# Scheduler settings
scheduler:
  tag: 1.6.6
  extraEnvs:
    # Enable real IP module to get real IP of clients
    - name: USE_REAL_IP
      value: "yes"

# Controller settings
controller:
  tag: 1.6.6

# UI settings
ui:
  tag: 1.6.6
```

Install BunkerWeb with custom values:

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

Check logs and wait until everything is ready.

**Web UI install**

Setup the following ingress (assuming nginx controller is installed):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ui-bunkerweb
  # Replace with your namespace of BW if needed
  namespace: bunkerweb
  annotations:
    # HTTPS is mandatory for web UI even if traffic is internal
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    # We must set SNI so BW can serve the right vhost
    # Replace with your domain
    nginx.ingress.kubernetes.io/proxy-ssl-name: "bunkerweb.example.com"
    nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"
spec:
  # Only served by nginx controller and not BW
  ingressClassName: nginx
  # Uncomment and edit if you want to use your own certificate
  # tls:
  # - hosts:
  #   - bunkerweb.example.com
  #   secretName: tls-secret
  rules:
  # Replace with your domain
  - host: bunkerweb.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Created by Helm chart
            name: bunkerweb-ui
            port:
              # Using HTTPS port is mandatory for UI
              number: 443
```

And you can now proceed to the setup wizard by browsing to `https://bunkerweb.example.com/setup`.

**Protecting existing application**

**First of all, you will need to go to Global Config, select the SSL plugin and then disable the Auto redirect HTTP to HTTPS. Please note that you only need to do it one time.**

Let's assume that you have an application in the `myapp` namespace which is accessible using the `myapp-service` service on port `5000`.

You will need to add a new service on the web UI and fill the required information:

- Server name: the public facing domain of your application (e.g. `myapp.example.com`)
- SSL/TLS: your ingress controller takes care of that part so don't enable it on BunkerWeb since traffic is internal within the cluster
- Reverse proxy host: the full URL of your application within the cluster (e.g. `http://myapp-service.myapp.svc.cluster.local:5000`)

Once the new service has been added, you can now declare an Ingress resource for that service and route it to the BunkerWeb service on HTTP port:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  # Replace with your namespace of BW if needed
  namespace: bunkerweb
spec:
  # Only served by nginx controller and not BW
  ingressClassName: nginx
  # Uncomment and edit if you want to use your own certificate
  # tls:
  # - hosts:
  #   - myapp.example.com
  #   secretName: tls-secret
  rules:
  # Replace with your domain
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Created by Helm chart
            name: bunkerweb-external
            port:
              number: 80
```

You can visit `http(s)://myapp.example.com`, which is now protected with BunkerWeb 🛡️

## Swarm

<figure markdown>
  ![Overview](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Docker Swarm integration</figcaption>
</figure>

!!! warning "Deprecated"
    The Swarm integration is deprecated and will be removed in a future release. Please consider using the [Kubernetes integration](#kubernetes) instead.

!!! tip "PRO support"
    **If you need Swarm support**, please contact us at [contact@bunkerity.com](mailto:contact@bunkerity.com) or via the [contact form](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Docker autoconf"
    The Swarm integration is similar to the Docker autoconf one (but with services instead of containers). Please read the [Docker autoconf integration section](#docker-autoconf) first if needed.

To enable automatic configuration of BunkerWeb instances, the **autoconf** service requires access to the Docker API. This service listens for Docker Swarm events, such as service creation or deletion, and seamlessly configures the **BunkerWeb instances** in real-time without any downtime. It also monitors other Swarm objects, such as [configs](https://docs.docker.com/engine/swarm/configs/), for custom configurations.

Similar to the [Docker autoconf integration](#docker-autoconf), configuration for web services is defined using labels that start with the **bunkerweb**  prefix.

For an optimal setup, it is recommended to schedule the **BunkerWeb service** as a ***global service*** on all nodes, while the **autoconf, scheduler, and Docker API proxy services** should be scheduled as ***single replicated services***. Please note that the Docker API proxy service needs to be scheduled on a manager node unless you configure it to use a remote API (which is not covered in the documentation).

Since multiple instances of BunkerWeb are running, a shared data store implemented as a [Redis](https://redis.io/) or [Valkey](https://valkey.io/) service must be created. These instances will utilize the Redis/Valkey service to cache and share data. Further details regarding the Redis/Valkey settings can be found [here](features.md#redis).

As for the database volume, the documentation does not specify a specific approach. Choosing either a shared folder or a specific driver for the database volume is dependent on your unique use-case and is left as an exercise for the reader.

!!! info "Database backend"
    Please be aware that our instructions assume you are using MariaDB as the default database backend, as configured by the `DATABASE_URI` setting. However, we understand that you may prefer to utilize alternative backends for your Docker integration. If that is the case, rest assured that other database backends are still possible. See docker-compose files in the [misc/integrations folder](https://github.com/bunkerity/bunkerweb/tree/v1.6.6/misc/integrations) of the repository for more information.

    Clustered database backends setup are out-of-the-scope of this documentation.

Here is the stack boilerplate that you can deploy using `docker stack deploy`:

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both services
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

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
        - "bunkerweb.INSTANCE=yes" # Mandatory label for the autoconf service to identify the BunkerWeb instance

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.6
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.6
    environment:
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
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
    # We set the max allowed packet size to avoid issues with large queries
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
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

!!! info "Swarm mandatory setting"
    Please note that the `SWARM_MODE: "yes"` environment variable is mandatory when using the Swarm integration.

!!! tip "Skipping labelled services"
  Need to exclude a Swarm service from autoconf? Set `SWARM_IGNORE_LABELS` on the controller. Supply a space- or comma-separated list of label keys (e.g. `bunkerweb.SERVER_NAME`) or suffixes (`SERVER_NAME`) and any service carrying those labels will be ignored during discovery.

### Swarm services

Once the BunkerWeb Swarm stack is set up and running (see autoconf and scheduler logs for more information), you will be able to deploy web applications in the cluster and use labels to dynamically configure BunkerWeb:

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

### Namespaces {#namespaces_2}

Starting from version `1.6.0`, BunkerWeb's Autoconf stacks now support namespaces. This feature enables you to manage multiple "*clusters*" of BunkerWeb instances and services on the same Docker host. To take advantage of namespaces, simply set the `NAMESPACE` label on your services. Here's an example:

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
        - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the service
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace behavior"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to specific namespaces, you can set the `NAMESPACES` environment variable in the `bw-autoconf` service:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.6
        ...
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"
            - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the BunkerWeb instance
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.6
        environment:
          NAMESPACES: "my-namespace my-other-namespace" # Only listen to these namespaces
          ...
        deploy:
          placement:
            constraints:
              - "node.role == worker"
    ...
    ```

    Keep in mind that the `NAMESPACES` environment variable is a space-separated list of namespaces.

!!! warning "Namespace specifications"

    There can only be **one database** and **one Scheduler** per namespace. If you try to create multiple databases or Schedulers in the same namespace, the configurations will end up conflicting with each other.

    The Scheduler doesn't need the `NAMESPACE` label to work properly. It will only need the `DATABASE_URI` setting properly configured so that it can access the same database as the autoconf service.

## Microsoft Azure

<figure markdown>
  ![Overview](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Azure integration</figcaption>
</figure>

!!! info "Recommended VM size"
    Please be aware while you choose the SKU of the VM. You must select a SKU compatible with Gen2 VM and we recommend starting at B2s or Ds2 series for optimal use.

You can easily deploy BunkerWeb on your Azure subscription in several ways:

- Azure CLI in Cloud Shell
- Azure ARM Template
- Azure portal via the Marketplace

=== "Cloud Shell"

    Create a resource group. Replace value `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    Create a VM with `Standard_B2s` SKU in the location of the resource group. Replace values `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    Full command. Replace values `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "ARM Template"

    !!! info "Permissions requirement"
        To deploy a ARM template, you need write access on the resources you're deploying and access to all operations on the Microsoft.Resources/deployments resource type.
        To deploy a virtual machine, you need Microsoft.Compute/virtualMachines/write and Microsoft.Resources/deployments/* permissions. The what-if operation has the same permission requirements.

    Deploy the ARM Template:

    [![Deploy to Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    Login in [Azure portal](https://portal.azure.com){:target="_blank"}.

    Get BunkerWeb from the [Create resource menu](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}.

    You can also go through the [Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"}.

You can access the setup wizard by browsing the `https://your-ip-address/setup` URI of your virtual machine.
