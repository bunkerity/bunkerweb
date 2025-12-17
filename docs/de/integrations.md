# Integrationen

## BunkerWeb Cloud

<figure markdown>
  ![Übersicht](assets/img/bunkerweb-cloud.png){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

BunkerWeb Cloud ist eine verwaltete Web Application Firewall (WAF) und Reverse-Proxy-Lösung, mit der Sie Ihre Webanwendungen sichern können, ohne BunkerWeb in Ihrer Infrastruktur zu installieren. Wenn Sie BunkerWeb Cloud abonnieren, profitieren Sie von einem vollständigen BunkerWeb-Stack, der in der Cloud gehostet wird und über dedizierte Ressourcen verfügt (8 GB RAM, 2 CPU **pro** Instanz, repliziert auf 2 Instanzen für Hochverfügbarkeit, Standardangebot).

### Hauptvorteile

Bestellen Sie Ihre [BunkerWeb Cloud-Instanz](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) und erhalten Sie Zugriff auf:

- **Sofortige Bereitstellung**: Keine Installation in Ihrer Infrastruktur erforderlich
- **Hochverfügbarkeit**: Replizierte Instanzen mit automatischem Lastausgleich
- **Integrierte Überwachung**: Zugriff auf Grafana zur Visualisierung von Protokollen und Metriken
- **Skalierbarkeit**: Dedizierte Ressourcen, die an hohe Arbeitslasten angepasst sind
- **Erhöhte Sicherheit**: Echtzeit-WAF-Schutz vor Webbedrohungen

Wenn Sie am BunkerWeb Cloud-Angebot interessiert sind, zögern Sie nicht, uns zu [kontaktieren](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc), damit wir Ihre Bedürfnisse besprechen können.

### Architekturübersicht

#### Einfache Architektur - Einzelner Dienst

```mermaid
graph LR
    A[Client] -->|HTTPS| B[beispiel.de]
    B -->|DNS-Auflösung| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Verkehr| D[BunkerWeb CloudWAF + Reverse Proxy]
    D -->|HTTPS/HTTP| E[Server beispiel.deClient-Infrastruktur]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#e8f5e8,color:#222
```

#### Komplexe Architektur - Multi-Dienste

```mermaid
graph LR
    A[Clients] -->|HTTPS| B[beispiel.deanderes-beispiel.deein-anderes-beispiel.de]
    B -->|DNS-Auflösung| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Verkehr| D[BunkerWeb CloudWAF + Reverse ProxySSL SNI Aktiviert]
    D -->|HTTPS mit SNI| E[Client GatewayReverse Proxy/LB]
    E -->|Internes Routing| F[Dienst 1]
    E -->|Internes Routing| G[Dienst 2]
    E -->|Internes Routing| H[Dienst N]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#fff3e0,color:#222
    style F fill:#e8f5e8,color:#222
    style G fill:#e8f5e8,color:#222
    style H fill:#e8f5e8,color:#222
```

### Erstkonfiguration

#### 1. Zugang zur Verwaltungsoberfläche

Nach dem Abonnement von BunkerWeb Cloud erhalten Sie:

- **URL für BunkerWeb-UI-Zugriff**: Schnittstelle zur Konfiguration Ihrer Dienste
- **Load Balancer-Endpunkt**: Eindeutige URL im Format `http://[ID].bunkerweb.cloud`
- **Grafana-Zugang**: Überwachungsschnittstelle und Visualisierung von Metriken
- **Zugewiesene Ressourcen**: 2 Instanzen mit je 8 GB RAM und 2 CPUs

#### 2. Erste Verbindung

1. Verbinden Sie sich mit der BunkerWeb Cloud-Schnittstelle
2. Konfigurieren Sie Ihre zu schützenden Dienste
3. Greifen Sie auf Grafana zu, um Ihre BunkerWeb-Protokolle und Metriken zu visualisieren

### DNS-Konfiguration

#### Verkehrsumleitung zu BunkerWeb Cloud

Damit der Datenverkehr Ihrer Domain von BunkerWeb Cloud verarbeitet wird, müssen Sie Ihre DNS-Einträge konfigurieren:

**Erforderliche Konfiguration:**

```dns
beispiel.de.        IN  CNAME  54984654.bunkerweb.cloud.
www.beispiel.de.    IN  CNAME  54984654.bunkerweb.cloud.
```

**Wichtig:** Ersetzen Sie `54984654` durch Ihre Load Balancer-Kennung, die Sie beim Abonnement erhalten haben.

#### Konfigurationsüberprüfung

Überprüfen Sie die DNS-Auflösung:

```bash
dig beispiel.de
nslookup beispiel.de
```

Das Ergebnis sollte auf Ihren BunkerWeb Cloud-Endpunkt verweisen.

### Dienstkonfiguration

#### Einzelner Dienst

Für einen einfachen Dienst, der auf Ihrer Infrastruktur gehostet wird:

**Konfiguration in der BunkerWeb-UI:**

1. **Server Name**: `beispiel.de`
2. **Use Reverse Proxy**: `yes`
3. **Reverse Proxy Host**: `185.87.1.100:443` (Ihre Server-IP)

Sie finden alle Konfigurationsoptionen in der [Reverse-Proxy-Dokumentation](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

#### Multi-Dienste mit SNI

##### Warum SNI aktivieren?

Server Name Indication (SNI) ist **essenziell**, wenn:

- Mehrere Domains auf dieselbe Backend-Infrastruktur zeigen
- Ihre Infrastruktur mehrere Dienste mit unterschiedlichen SSL-Zertifikaten hostet
- Sie einen Reverse Proxy/Gateway auf Client-Seite verwenden

##### SNI-Konfiguration

**In der BunkerWeb-UI, für jeden Dienst:**

```yaml
# Dienst 1
SERVICE_NAME: beispiel-de
SERVER_NAME: beispiel.de
REVERSE_PROXY_HOST: https://gateway.intern.domain.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: beispiel.de

# Dienst 2
SERVICE_NAME: anderes-beispiel-de
SERVER_NAME: anderes-beispiel.de
REVERSE_PROXY_HOST: https://gateway.intern.domain.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: anderes-beispiel.de
```

Sie finden alle Konfigurationsoptionen in der [Reverse-Proxy-Dokumentation](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

##### Technische Details zu SNI

SNI ermöglicht BunkerWeb Cloud:

1. **Den Zieldienst zu identifizieren** während der TLS-Verbindung
2. **Den korrekten Domainnamen** an das Backend zu übermitteln
3. **Dem Client-Gateway zu ermöglichen**, das richtige Zertifikat auszuwählen
4. **Korrekt** zum entsprechenden Dienst zu routen

**Ohne aktiviertes SNI:**

```mermaid
graph LR
    A[Client] --> B[BunkerWeb]
    B --> C["Gateway (Standardzertifikat)"]
    C --> D[SSL-Fehler]

    style B fill:#f3e5f5,color:#222
    style C fill:#fff3e0,color:#222
    style D fill:#ff4d4d,color:#fff,stroke:#b30000,stroke-width:2px
```

**Mit aktiviertem SNI:**

```mermaid
graph LR
    A[Client] --> B[BunkerWeb]
    B --> C["Gateway (beispiel.de spezifisches Zertifikat)"]
    C --> D[Korrekter Dienst]

    style B fill:#f3e5f5,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
```

### SSL/TLS- und SNI-Management

#### SSL-Zertifikate

##### Auf Seite von BunkerWeb Cloud

BunkerWeb Cloud verwaltet automatisch:

- Let's Encrypt-Zertifikate für Ihre Domains
- Automatische Erneuerung
- Optimierte TLS-Konfiguration

##### Auf Seite der Client-Infrastruktur

**Wichtige Empfehlungen:**

1. **Verwenden Sie HTTPS** für die Kommunikation zwischen BunkerWeb und Ihren Diensten
2. **Verwalten Sie Ihre eigenen Zertifikate** auf Ihrer Infrastruktur
3. **Konfigurieren Sie SNI ordnungsgemäß** auf Ihrem Gateway/Reverse Proxy

#### Detaillierte SNI-Konfiguration

##### Anwendungsfall: Infrastruktur mit Gateway

Wenn Ihre Architektur so aussieht:

```mermaid
graph LR
    A[BunkerWeb Cloud] --> B[Client Gateway]
    B --> C[Dienst 1]
    B --> D[Dienst 2]
    B --> E[Dienst 3]

    style A fill:#f3e5f5,color:#222
    style B fill:#fff3e0,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
    style E fill:#e8f5e8,color:#222
```

**Erforderliche Konfiguration auf BunkerWeb-Seite:**

```yaml
# Konfiguration für beispiel.de
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: beispiel.de
REVERSE_PROXY_SSL_VERIFY: no  # Bei selbstsigniertem Zertifikat auf Client-Seite
REVERSE_PROXY_HEADERS: Host $host

# Konfiguration für api.beispiel.de
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: api.beispiel.de
REVERSE_PROXY_SSL_VERIFY: no
REVERSE_PROXY_HEADERS: Host $host
```

### Client-Gateway-Konfiguration

#### Übersicht

Wenn Ihre Architektur ein Gateway/Reverse Proxy auf der Client-Seite verwendet, um den Verkehr zu mehreren Diensten zu leiten, ist eine spezifische Konfiguration erforderlich, um SNI zu unterstützen und eine sichere Kommunikation mit BunkerWeb Cloud zu gewährleisten.

#### Konfigurationen nach Technologie

##### Nginx

<details>
<summary>Nginx-Konfiguration</summary>

```nginx
# Konfiguration zur Unterstützung von SNI mit mehreren Diensten
server {
    listen 443 ssl http2;
    server_name beispiel.de;

    ssl_certificate /path/to/beispiel.de.crt;
    ssl_certificate_key /path/to/beispiel.de.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Sicherheits-Header
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
    server_name api.beispiel.de;

    ssl_certificate /path/to/api.beispiel.de.crt;
    ssl_certificate_key /path/to/api.beispiel.de.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://api-service:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # API-spezifische Konfiguration
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

</details>

##### Traefik

<details>
<summary>Traefik-Konfiguration</summary>

**Mit Docker Compose:**

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
      - --certificatesresolvers.myresolver.acme.email=admin@beispiel.de
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
      - "traefik.http.routers.dashboard.rule=Host(`traefik.beispiel.de`)"
      - "traefik.http.routers.dashboard.tls.certresolver=myresolver"

  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`beispiel.de`)"
      - "traefik.http.routers.service1.entrypoints=websecure"
      - "traefik.http.routers.service1.tls.certresolver=myresolver"
      - "traefik.http.services.service1.loadbalancer.server.port=8080"
      - "traefik.http.routers.service1.middlewares=security-headers"

  api-service:
    image: your-api:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.beispiel.de`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=myresolver"
      - "traefik.http.services.api.loadbalancer.server.port=3000"
      - "traefik.http.routers.api.middlewares=security-headers,rate-limit"
```

**Dynamische Konfiguration (dynamic.yml):**

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
      rule: "Host(`beispiel.de`)"
      service: "service1"
      tls:
        certResolver: "myresolver"
      middlewares:
        - "security-headers"

    api:
      rule: "Host(`api.beispiel.de`)"
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
<summary>Apache-Konfiguration</summary>

```apache
# Apache-Konfiguration mit SNI
<VirtualHost *:443>
    ServerName beispiel.de
    DocumentRoot /var/www/html

    # SSL-Konfiguration
    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLHonorCipherOrder off
    SSLCertificateFile /path/to/beispiel.de.crt
    SSLCertificateKeyFile /path/to/beispiel.de.key

    # Sicherheits-Header
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # Reverse-Proxy-Konfiguration
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Benutzerdefinierte Header
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    <Proxy *>
        Require all granted
    </Proxy>

    # Protokolle
    ErrorLog ${APACHE_LOG_DIR}/beispiel.de_error.log
    CustomLog ${APACHE_LOG_DIR}/beispiel.de_access.log combined
</VirtualHost>

<VirtualHost *:443>
    ServerName api.beispiel.de

    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLCertificateFile /path/to/api.beispiel.de.crt
    SSLCertificateKeyFile /path/to/api.beispiel.de.key

    ProxyPass / http://api-service:3000/
    ProxyPassReverse / http://api-service:3000/
    ProxyPreserveHost On

    # API-spezifische Konfiguration
    ProxyTimeout 300
    ProxyBadHeader Ignore

    ErrorLog ${APACHE_LOG_DIR}/api.beispiel.de_error.log
    CustomLog ${APACHE_LOG_DIR}/api.beispiel.de_access.log combined
</VirtualHost>

# Erforderliche Modulkonfiguration
LoadModule ssl_module modules/mod_ssl.so
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
LoadModule headers_module modules/mod_headers.so
```

</details>

##### HAProxy

<details>
<summary>HAProxy-Konfiguration</summary>

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

    # SSL-Konfiguration
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
    bind *:443 ssl crt /etc/ssl/certs/beispiel.de.pem crt /etc/ssl/certs/api.beispiel.de.pem

    # Sicherheits-Header
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff
    http-response set-header X-XSS-Protection "1; mode=block"
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # SNI-basiertes Routing
    acl is_beispiel hdr(host) -i beispiel.de
    acl is_api hdr(host) -i api.beispiel.de

    use_backend service1_backend if is_beispiel
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

# Statistik-Schnittstelle (optional)
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE
```

</details>

#### Validierung der SSL-Konfiguration

SSL-Konfiguration testen:

```bash
# SSL-Konnektivitätstest
openssl s_client -connect ihre-domain.de:443 -servername ihre-domain.de

# Header-Überprüfung
curl -I https://ihre-domain.de

# SNI-Test
curl -H "Host: beispiel.de" https://54984654.bunkerweb.cloud
```

#### Best Practices für Gateways

1. **Health Checks**: Konfigurieren Sie Integritätsprüfungen für Ihre Dienste
2. **Lastenausgleich**: Verwenden Sie mehrere Instanzen für Hochverfügbarkeit
3. **Überwachung**: Überwachen Sie Ihre Gateway-Metriken
4. **Sicherheits-Header**: Fügen Sie geeignete Sicherheits-Header hinzu
5. **Timeouts**: Konfigurieren Sie angemessene Timeouts, um Blockierungen zu vermeiden

### BunkerWeb Cloud IP-Whitelist

#### Warum eine Whitelist konfigurieren?

Um Ihre Infrastruktur weiter zu sichern, wird empfohlen, eine Whitelist von BunkerWeb Cloud-IP-Adressen auf der Seite der Client-Infrastruktur zu konfigurieren. Dadurch wird sichergestellt, dass nur Datenverkehr von BunkerWeb Cloud Ihre Backend-Dienste erreichen kann.

Wir empfehlen das Whitelisting auf Firewall-Ebene (iptables usw.).

#### BunkerWeb Cloud IP-Adressen zur Whitelist hinzufügen

**Liste der zuzulassenden IP-Adressen:**

Aktualisierte Liste ist hier verfügbar: https://repo.bunkerweb.io/cloud/ips

```
# BunkerWeb Cloud IP-Adressen
4.233.128.18
20.19.161.132
```

#### Whitelist-Konfiguration nach Technologie

##### Nginx

<details>
<summary>Nginx-Konfiguration</summary>

```nginx
# In Ihrer Serverkonfiguration
server {
    listen 443 ssl;
    server_name beispiel.de;

    # BunkerWeb Cloud IP-Whitelist
    allow 192.168.1.0/24;
    allow 10.0.0.0/16;
    allow 172.16.0.0/12;
    deny all;

    ssl_certificate /path/to/beispiel.de.crt;
    ssl_certificate_key /path/to/beispiel.de.key;

    location / {
        proxy_pass http://service1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# Konfiguration mit Geo-Modul für mehr Flexibilität
geo $bunkerweb_ip {
    default 0;
    192.168.1.0/24 1;
    10.0.0.0/16 1;
    172.16.0.0/12 1;
}

server {
    listen 443 ssl;
    server_name beispiel.de;

    if ($bunkerweb_ip = 0) {
        return 403;
    }

    # ... Rest der Konfiguration
}
```

</details>

##### Traefik

<details>
<summary>Traefik-Konfiguration</summary>

```yaml
# Konfiguration in dynamic.yml
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
    beispiel-router:
      rule: "Host(`beispiel.de`)"
      service: "beispiel-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"

    api-router:
      rule: "Host(`api.beispiel.de`)"
      service: "api-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"
```

**Mit Docker Compose-Labels:**

```yaml
services:
  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`beispiel.de`)"
      - "traefik.http.routers.service1.middlewares=bunkerweb-whitelist"
      - "traefik.http.middlewares.bunkerweb-whitelist.ipwhitelist.sourcerange=192.168.1.0/24,10.0.0.0/16,172.16.0.0/12"
```

</details>

##### Apache

<details>
<summary>Apache-Konfiguration</summary>

```apache
<VirtualHost *:443>
    ServerName beispiel.de

    # BunkerWeb Cloud IP-Whitelist
    <RequireAll>
        Require ip 192.168.1.0/24
        Require ip 10.0.0.0/16
        Require ip 172.16.0.0/12
    </RequireAll>

    SSLEngine on
    SSLCertificateFile /path/to/beispiel.de.crt
    SSLCertificateKeyFile /path/to/beispiel.de.key

    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Konfiguration für verweigerte Zugriffsprotokolle
    LogFormat "%h %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined
    CustomLog logs/access.log combined
    ErrorLog logs/error.log
</VirtualHost>

# Alternative Konfiguration mit mod_authz_core
<VirtualHost *:443>
    ServerName api.beispiel.de

    <Directory />
        <RequireAny>
            Require ip 192.168.1.0/24
            Require ip 10.0.0.0/16
            Require ip 172.16.0.0/12
        </RequireAny>
    </Directory>

    # ... Rest der Konfiguration
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>HAProxy-Konfiguration</summary>

```haproxy
# Konfiguration in haproxy.cfg
frontend bunkerweb_frontend
    bind *:443 ssl crt /path/to/certificates/

    # ACL für BunkerWeb Cloud Whitelist
    acl bunkerweb_ips src 192.168.1.0/24 10.0.0.0/16 172.16.0.0/12

    # Alles blockieren außer BunkerWeb Cloud
    http-request deny unless bunkerweb_ips

    # Sicherheits-Header
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff

    # Routing
    acl is_beispiel hdr(host) -i beispiel.de
    acl is_api hdr(host) -i api.beispiel.de

    use_backend app_servers if is_beispiel
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

##### System-Firewall (iptables)

<details>
<summary>iptables-Konfiguration</summary>

```bash
#!/bin/bash
# iptables-Konfigurationsskript für BunkerWeb Cloud Whitelist

# Vorhandene Regeln löschen
iptables -F
iptables -X

# Standardrichtlinien
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Loopback zulassen
iptables -A INPUT -i lo -j ACCEPT

# Etablierte Verbindungen zulassen
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# BunkerWeb Cloud-IPs für HTTPS zulassen
iptables -A INPUT -p tcp --dport 443 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 10.0.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 172.16.0.0/12 -j ACCEPT

# HTTP für Let's Encrypt zulassen (optional)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# SSH zulassen (an Ihre Bedürfnisse anpassen)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Protokolle für Debugging
iptables -A INPUT -j LOG --log-prefix "DROPPED: "

# Regeln speichern
iptables-save > /etc/iptables/rules.v4

echo "iptables-Konfiguration erfolgreich angewendet"
```

</details>

#### Whitelist Best Practices

1. **Ablehnungen überwachen**: Überwachen Sie blockierte Zugriffsversuche
2. **Regelmäßige Updates**: Halten Sie die IP-Liste aktuell
3. **Regelmäßige Tests**: Validieren Sie, dass die Whitelist korrekt funktioniert
4. **Dokumentation**: Dokumentieren Sie IP-Änderungen
5. **Alarmierung**: Konfigurieren Sie Alarme für BunkerWeb-IP-Änderungen
6. **Backup**: Bewahren Sie eine Backup-Konfiguration für den Fall von Problemen auf

### REAL_IP-Konfiguration und Client-Adresswiederherstellung

#### Warum REAL_IP konfigurieren?

Wenn Sie BunkerWeb Cloud als Reverse Proxy verwenden, sind die IP-Adressen, die Ihre Backend-Anwendungen sehen, die von BunkerWeb Cloud und nicht die der echten Clients. Um die echten Client-IP-Adressen abzurufen, ist eine spezifische Konfiguration erforderlich.

#### Konfiguration auf Seite von BunkerWeb Cloud

In der BunkerWeb-UI konfigurieren Sie Real IP:

```yaml
USE_REAL_IP: yes # Standard ist no
REAL_IP_FROM: 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8 # Standard
REAL_IP_HEADER: X-Forwarded-For # Standard
REAL_IP_RECURSIVE: yes # Standard
# Beispiel, wenn Sie auch Cloudflare Proxy vor BunkerWeb verwenden
REAL_IP_FROM_URLS: https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/
```

Sie finden alle Konfigurationsoptionen in der [Dokumentation Real Ip](https://docs.bunkerweb.io/latest/settings/#real-ip)

#### Konfiguration auf Seite der Client-Infrastruktur

##### Nginx

<details>
<summary>Nginx-Konfiguration für REAL_IP</summary>

```nginx
# Vertrauenswürdige IP-Adressen konfigurieren (BunkerWeb Cloud)
set_real_ip_from 4.233.128.18/32
set_real_ip_from 20.19.161.132/32

# Header zur Ermittlung der echten IP verwenden
real_ip_header X-Real-IP;

# Alternative mit X-Forwarded-For
# real_ip_header X-Forwarded-For;

server {
    listen 443 ssl http2;
    server_name beispiel.de;

    # SSL-Konfiguration
    ssl_certificate /path/to/beispiel.de.crt;
    ssl_certificate_key /path/to/beispiel.de.key;

    location / {
        proxy_pass http://service1:8080;

        # Echte IP-Header an das Backend weiterleiten
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Protokoll mit echter Client-IP
        access_log /var/log/nginx/access.log combined;
    }
}

# Benutzerdefiniertes Protokollformat mit echter IP
log_format real_ip '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent" '
                   'real_ip="$realip_remote_addr"';
```

</details>

##### Apache

<details>
<summary>Apache-Konfiguration für REAL_IP</summary>

```apache
# Modul mod_remoteip laden
LoadModule remoteip_module modules/mod_remoteip.so

<VirtualHost *:443>
    ServerName beispiel.de

    # SSL-Konfiguration
    SSLEngine on
    SSLCertificateFile /path/to/beispiel.de.crt
    SSLCertificateKeyFile /path/to/beispiel.de.key

    # Vertrauenswürdige IP-Adressen konfigurieren
    RemoteIPHeader X-Real-IP
    RemoteIPTrustedProxy 4.233.128.18/32
    RemoteIPTrustedProxy 20.19.161.132/32

    # Alternative mit X-Forwarded-For
    # RemoteIPHeader X-Forwarded-For

    # Reverse-Proxy-Konfiguration
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # IP-Header weiterleiten
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    # Protokolle mit echter IP
    LogFormat "%a %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined_real_ip
    CustomLog logs/access.log combined_real_ip
    ErrorLog logs/error.log
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>HAProxy-Konfiguration für REAL_IP</summary>

```haproxy
global
    maxconn 4096
    log stdout local0

defaults
    mode http
    option httplog
    option dontlognull
    option forwardfor

    # Protokollformat mit echter IP
    log-format "%ci:%cp [%t] %ft %b/%s %Tq/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"

frontend https_frontend
    bind *:443 ssl crt /etc/ssl/certs/

    # BunkerWeb Cloud IP-Whitelist
    acl bunkerweb_ips src 4.233.128.18/32 20.19.161.132/32
    http-request deny unless bunkerweb_ips

    # Echte IP aus Headern erfassen
    capture request header X-Real-IP len 15
    capture request header X-Forwarded-For len 50

    # Routing
    acl is_beispiel hdr(host) -i beispiel.de
    use_backend app_servers if is_beispiel

    default_backend app_servers

backend app_servers
    balance roundrobin

    # Echte IP-Header hinzufügen/erhalten
    http-request set-header X-Original-Forwarded-For %[req.hdr(X-Forwarded-For)]
    http-request set-header X-Client-IP %[req.hdr(X-Real-IP)]

    server app1 service1:8080 check
    server app2 service2:8080 check backup
```

</details>

##### Traefik

<details>
<summary>Traefik-Konfiguration für REAL_IP</summary>

```yaml
# Konfiguration in dynamic.yml
http:
  middlewares:
    real-ip:
      ipWhiteList:
        sourceRange:
          - "4.233.128.18/32"
          - "20.19.161.132/32"
        ipStrategy:
          depth: 2  # Anzahl der vertrauenswürdigen Proxies
          excludedIPs:
            - "127.0.0.1/32"

  routers:
    beispiel-router:
      rule: "Host(`beispiel.de`)"
      service: "beispiel-service"
      middlewares:
        - "real-ip"
      tls:
        certResolver: "myresolver"

  services:
    beispiel-service:
      loadBalancer:
        servers:
          - url: "http://service1:8080"
        passHostHeader: true
```

**Konfiguration in traefik.yml (statisch):**

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

#### Tests und Validierung

##### Konfigurationsüberprüfung

```bash
# Test 1: Empfangene Header prüfen
curl -H "X-Real-IP: 203.0.113.1" \
     -H "X-Forwarded-For: 203.0.113.1, 192.168.1.100" \
     https://beispiel.de/test-ip

# Test 2: Protokolle analysieren
tail -f /var/log/nginx/access.log | grep "203.0.113.1"

# Test 3: Test von verschiedenen Quellen
curl -v https://beispiel.de/whatismyip
```

#### REAL_IP Best Practices

1. **Sicherheit**: Vertrauen Sie nur IP-Headern von bekannten Quellen (BunkerWeb Cloud)
2. **Validierung**: Validieren Sie immer die in Headern empfangenen IP-Adressen
3. **Protokollierung**: Protokollieren Sie sowohl Proxy-IP als auch echte IP für das Debugging
4. **Fallback**: Haben Sie immer einen Standardwert, wenn Header fehlen
5. **Tests**: Testen Sie regelmäßig, ob die IP-Erkennung korrekt funktioniert
6. **Überwachung**: Überwachen Sie IP-Muster, um Anomalien zu erkennen

#### REAL_IP-Fehlerbehebung

##### Häufige Probleme

1. **IP zeigt immer die von BunkerWeb**: Überprüfen Sie die Konfiguration der vertrauenswürdigen Proxies
2. **Fehlende Header**: Überprüfen Sie die Konfiguration auf Seite von BunkerWeb Cloud
3. **Ungültige IPs**: Implementieren Sie eine strikte IP-Validierung
4. **Falsche Protokolle**: Überprüfen Sie das Protokollformat und die real_ip-Modulkonfiguration

##### Diagnosebefehle

__IP-Erkennung testen__

```bash
curl -H "X-Real-IP: 1.2.3.4" https://ihre-domain.de/debug-headers
```

### Überwachung und Observabilität

#### Grafana-Zugang

Ihre verwaltete Grafana-Instanz gibt Ihnen Zugriff auf:

##### Verfügbare Metriken

1. **Verkehrsübersicht**

  - Anfragen pro Sekunde
  - HTTP-Statuscodes
  - Anfragen-Geolokalisierung
2. **Sicherheit**

  - Blockierte Angriffsversuche
  - Erkannte Bedrohungstypen
  - Ausgelöste WAF-Regeln
3. **Leistungsmetriken**

  - Anfragelatenz
  - Backend-Antwortzeit
  - Ressourcennutzung

##### Verfügbare Protokolle

1. **Access Logs**: Alle HTTP/HTTPS-Anfragen
2. **Security Logs**: Sicherheitsereignisse und Blockierungen
3. **Error Logs**: Anwendungs- und Systemfehler

##### Alarmkonfiguration

Konfigurieren Sie Grafana-Alarme für:

- Abnormale Verkehrsspitzen
- Anstieg von 5xx-Fehlern
- Erkennung von DDoS-Angriffen
- Backend-Gesundheitsfehler

### Best Practices

#### Sicherheit

1. **Verwenden Sie HTTPS** für die gesamte Backend-Kommunikation
2. **Implementieren Sie eine IP-Whitelist**, wenn möglich
3. **Konfigurieren Sie angemessene Timeouts**
4. **Aktivieren Sie Komprimierung**, um die Leistung zu optimieren

#### Leistung

1. **Optimieren Sie die Cache-Konfiguration**
2. **Verwenden Sie HTTP/2** auf Client-Seite
3. **Konfigurieren Sie Health Checks** für Ihre Backends
4. **Überwachen Sie Metriken** regelmäßig

### Fehlerbehebung

#### Häufige Probleme

##### 1. SSL/TLS-Fehler

**Symptom:** SSL-Zertifikatsfehler

**Lösungen:**

```bash
# SNI-Konfiguration prüfen
openssl s_client -connect backend.com:443 -servername beispiel.de

# Backend-Zertifikate prüfen
openssl x509 -in certificate.crt -text -noout
```

##### 2. Backend-Timeout

**Symptom:** 504 Gateway Timeout-Fehler

**Lösungen:**

- Erhöhen Sie `REVERSE_PROXY_CONNECT_TIMEOUT` & `REVERSE_PROXY_SEND_TIMEOUT`
- Überprüfen Sie die Backend-Gesundheit
- Optimieren Sie die Anwendungsleistung

##### 3. Routing-Probleme

**Symptom:** Falscher Dienst wird bereitgestellt

**Lösungen:**

- Überprüfen Sie die `SERVER_NAME`-Konfiguration
- Validieren Sie die SNI-Konfiguration
- Überprüfen Sie die `Host`-Header

#### Diagnosebefehle

```bash
# Konnektivitätstest
curl -v https://ihre-domain.de

# Test mit benutzerdefinierten Headern
curl -H "Host: beispiel.de" -v https://54984654.bunkerweb.cloud

# DNS-Überprüfung
dig +trace beispiel.de

# SSL-Test
openssl s_client -connect beispiel.de:443 -servername beispiel.de
```

#### Technischer Support

Für technische Unterstützung:

1. **Überprüfen Sie die Protokolle** in Grafana
2. **Überprüfen Sie die Konfiguration** in der BunkerWeb-UI
3. **Kontaktieren Sie den Support** mit Konfigurationsdetails und Fehlerprotokollen

## All-In-One (AIO) Image {#all-in-one-aio-image}

<figure markdown>
  ![AIO Architekturdiagramm Platzhalter](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>BunkerWeb All-In-One Architektur (AIO)</figcaption>
</figure>

### Bereitstellung {#deployment}

Um den All-in-One-Container bereitzustellen, müssen Sie nur den folgenden Befehl ausführen:

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1
```

Standardmäßig stellt der Container Folgendes bereit:

- 8080/tcp für HTTP
- 8443/tcp für HTTPS
- 8443/udp für QUIC
- 7000/tcp für den Zugriff auf die Web-UI ohne BunkerWeb davor (nicht für die Produktion empfohlen)
- 8888/tcp für die API, wenn `SERVICE_API=yes` (interne Verwendung; vorzugsweise über BunkerWeb als Reverse-Proxy bereitstellen, anstatt direkt zu veröffentlichen)

Ein benanntes Volume (oder Bind-Mount) ist erforderlich, um die unter `/data` gespeicherten SQLite-Datenbanken, Caches und Backups zu persistieren:

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.7-rc1
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Verwendung eines lokalen Ordners für persistente Daten"
    Der All-In-One-Container führt seine Dienste als **unprivilegierter Benutzer mit der UID 101 und GID 101** aus. Das erhöht die Sicherheit: Selbst wenn eine Komponente kompromittiert wird, erhält sie keine Root-Rechte (UID/GID 0) auf dem Host.

    Wenn Sie einen **lokalen Ordner** einbinden, stellen Sie sicher, dass die Verzeichnisberechtigungen es diesem unprivilegierten Benutzer erlauben, darin zu schreiben:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Oder, falls der Ordner bereits existiert:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Bei Verwendung von [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) oder [Podman](https://podman.io/) werden Container-UIDs/GIDs auf andere Werte des Hosts abgebildet. Prüfen Sie daher zuerst Ihre subuid-/subgid-Bereiche:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Beginnt der Bereich beispielsweise bei **100000**, lautet die zugeordnete UID/GID **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Oder, wenn der Ordner bereits existiert:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

Das All-In-One-Image enthält mehrere integrierte Dienste, die über Umgebungsvariablen gesteuert werden können:

- `SERVICE_UI=yes` (Standard) - Aktiviert den Web-UI-Dienst
- `SERVICE_SCHEDULER=yes` (Standard) - Aktiviert den Scheduler-Dienst
- `SERVICE_API=no` (Standard) - Aktiviert den API-Dienst (FastAPI-Steuerungsebene)
- `AUTOCONF_MODE=no` (Standard) - Aktiviert den Autoconf-Dienst
- `USE_REDIS=yes` (Standard) - Aktiviert die integrierte [Redis-Instanz](#redis-integration)
- `USE_CROWDSEC=no` (Standard) - Die [CrowdSec-Integration](#crowdsec-integration) ist standardmäßig deaktiviert
- `HIDE_SERVICE_LOGS=` (optional) - Kommagetrennte Liste von Diensten, deren Ausgaben in den Container-Logs unterdrückt werden. Unterstützte Werte: `api`, `autoconf`, `bunkerweb`, `crowdsec`, `redis`, `scheduler`, `ui`, `nginx.access`, `nginx.error`, `modsec`. Die Dateien in `/var/log/bunkerweb/<service>.log` werden weiterhin beschrieben.

### API-Integration

Das All-In-One-Image enthält die BunkerWeb-API. Sie ist standardmäßig deaktiviert und kann durch Setzen von `SERVICE_API=yes` aktiviert werden.

!!! warning "Sicherheit"
    Die API ist eine privilegierte Steuerungsebene. Setzen Sie sie nicht direkt dem Internet aus. Halten Sie sie in einem internen Netzwerk, beschränken Sie die Quell-IPs mit `API_WHITELIST_IPS`, erfordern Sie eine Authentifizierung (`API_TOKEN` oder API-Benutzer + Biscuit) und greifen Sie vorzugsweise über BunkerWeb als Reverse-Proxy auf einem nicht erratbaren Pfad darauf zu.

Schnelle Aktivierung (eigenständig) — veröffentlicht den API-Port; nur zu Testzwecken:

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
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1
```

Empfohlen (hinter BunkerWeb) — veröffentlichen Sie `8888` nicht; verwenden Sie stattdessen einen Reverse-Proxy:

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.7-rc1
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
      api.example.com_REVERSE_PROXY_HOST: "http://127.0.0.1:8888" # Interner API-Endpunkt

      # API-Einstellungen
      SERVICE_API: "yes"
      # Verwenden Sie starke Zugangsdaten und erlauben Sie nur vertrauenswürdige IPs/Netze (Details unten)
      API_USERNAME: "changeme"
      API_PASSWORD: "StrongP@ssw0rd"
      API_ROOT_PATH: "/api-<unguessable>" # Muss mit REVERSE_PROXY_URL übereinstimmen

      # Wir deaktivieren die UI – zum Aktivieren auf "yes" setzen
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

Details zu Authentifizierung, Berechtigungen (ACL), Ratenbegrenzung, TLS und Konfigurationsoptionen finden Sie in der [API-Dokumentation](api.md).

### Zugriff auf den Einrichtungsassistenten

Standardmäßig wird der Einrichtungsassistent automatisch gestartet, wenn Sie den AIO-Container zum ersten Mal ausführen. Um darauf zuzugreifen, führen Sie die folgenden Schritte aus:

1. **Starten Sie den AIO-Container** wie [oben](#deployment) beschrieben und stellen Sie sicher, dass `SERVICE_UI=yes` (Standard) ist.
2. **Greifen Sie auf die UI** über Ihren Haupt-BunkerWeb-Endpunkt zu, z. B. `https://ihre-domain`.

> Folgen Sie den nächsten Schritten im [Schnellstart-Leitfaden](quickstart-guide.md#complete-the-setup-wizard), um die Web-UI einzurichten.

### Redis-Integration {#redis-integration}

Das BunkerWeb **All-In-One**-Image enthält standardmäßig Redis für die [Persistenz von Sperren und Berichten](advanced.md#persistence-of-bans-and-reports). Beachten Sie dabei:

- Der eingebettete Redis-Dienst startet nur, wenn `USE_REDIS=yes` **und** `REDIS_HOST` auf dem Standardwert (`127.0.0.1`/`localhost`) bleibt.
- Er lauscht auf dem Loopback-Interface des Containers und ist daher nur aus dem Container heraus erreichbar – nicht von anderen Containern oder vom Host.
- Überschreiben Sie `REDIS_HOST` nur, wenn ein externer Redis-/Valkey-Endpunkt verfügbar ist; andernfalls wird die eingebettete Instanz nicht gestartet.
- Um Redis vollständig zu deaktivieren, setzen Sie `USE_REDIS=no`.
- Redis-Protokolle erscheinen mit dem Präfix `[REDIS]` in den Docker-Protokollen sowie in `/var/log/bunkerweb/redis.log`.

### CrowdSec-Integration {#crowdsec-integration}

Das BunkerWeb **All-In-One**-Docker-Image wird mit vollständig integriertem CrowdSec geliefert – keine zusätzlichen Container oder manuelle Einrichtung erforderlich. Befolgen Sie die nachstehenden Schritte, um CrowdSec in Ihrer Bereitstellung zu aktivieren, zu konfigurieren und zu erweitern.

Standardmäßig ist CrowdSec **deaktiviert**. Um es zu aktivieren, fügen Sie einfach die Umgebungsvariable `USE_CROWDSEC` hinzu:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1```

* Wenn `USE_CROWDSEC=yes`, wird das Einstiegsskript:

    1. Den lokalen CrowdSec-Agenten **registrieren** und **starten** (über `cscli`).
    2. Standard-Sammlungen und -Parser **installieren oder aktualisieren**.
    3. Den Bouncer `crowdsec-bunkerweb-bouncer/v1.6` **konfigurieren**.

---

#### Standard-Sammlungen & Parser

Beim ersten Start (oder nach einem Upgrade) werden diese Assets automatisch installiert und auf dem neuesten Stand gehalten:

| Typ          | Name                                    | Zweck                                                                                                                                                                                                                                              |
| ------------ | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Sammlung** | `bunkerity/bunkerweb`                   | Verteidigt Nginx-Server gegen eine breite Palette von HTTP-basierten Angriffen, von Brute-Force- bis zu Injektionsversuchen.                                                                                                                       |
| **Sammlung** | `crowdsecurity/appsec-virtual-patching` | Liefert einen dynamisch aktualisierten WAF-artigen Regelsatz, der auf bekannte CVEs abzielt und täglich automatisch gepatcht wird, um Webanwendungen vor neu entdeckten Schwachstellen zu schützen.                                                |
| **Sammlung** | `crowdsecurity/appsec-generic-rules`    | Ergänzt `crowdsecurity/appsec-virtual-patching` mit Heuristiken für generische Angriffsmuster auf Anwendungsebene – wie Enumeration, Pfad-Traversal und automatisierte Sonden – und füllt Lücken, wo CVE-spezifische Regeln noch nicht existieren. |
| **Parser**   | `crowdsecurity/geoip-enrich`            | Bereichert Ereignisse mit GeoIP-Kontext                                                                                                                                                                                                            |

<details>
<summary><strong>Wie es intern funktioniert</strong></summary>

Das Einstiegsskript ruft auf:

```bash
cscli hub update
cscli install collection bunkerity/bunkerweb
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

!!! info "Sammlung fehlt in Docker?"
    Wenn `cscli collections list` im Container `bunkerity/bunkerweb` weiterhin nicht anzeigt, führen Sie `docker exec -it bunkerweb-aio cscli hub update` aus und starten Sie anschließend den Container neu (`docker restart bunkerweb-aio`), um den lokalen Hub-Cache zu aktualisieren.

---

#### Hinzufügen zusätzlicher Sammlungen

Benötigen Sie mehr Abdeckung? Definieren Sie `CROWDSEC_EXTRA_COLLECTIONS` mit einer durch Leerzeichen getrennten Liste von Hub-Sammlungen:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/apache2 crowdsecurity/mysql" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1
```

!!! info "Wie es intern funktioniert"

    Das Skript durchläuft jeden Namen und installiert oder aktualisiert ihn nach Bedarf – keine manuellen Schritte erforderlich.

---

#### Deaktivieren bestimmter Parser

Wenn Sie die Standardeinrichtung beibehalten, aber einen oder mehrere Parser explizit deaktivieren möchten, geben Sie eine durch Leerzeichen getrennte Liste über `CROWDSEC_DISABLED_PARSERS` an:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_DISABLED_PARSERS="crowdsecurity/geoip-enrich foo/bar-parser" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1
```

Hinweise:
- Die Liste wird angewendet, nachdem die erforderlichen Elemente installiert/aktualisiert wurden; nur die von Ihnen aufgelisteten Parser werden entfernt.
- Verwenden Sie Hub-Slugs, wie sie von `cscli parsers list` angezeigt werden (z. B. `crowdsecurity/geoip-enrich`).

---

#### AppSec-Umschalter

CrowdSec [AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs)-Funktionen – angetrieben durch die Sammlungen `appsec-virtual-patching` und `appsec-generic-rules` – sind **standardmäßig aktiviert**.

Um alle AppSec-Funktionen (WAF/virtuelles Patchen) zu **deaktivieren**, setzen Sie:

```bash
-e CROWDSEC_APPSEC_URL=""
```

Dies schaltet den AppSec-Endpunkt effektiv aus, sodass keine Regeln angewendet werden.

---

#### Externe CrowdSec-API

Wenn Sie eine entfernte CrowdSec-Instanz betreiben, verweisen Sie den Container auf Ihre API:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_API="https://crowdsec.example.com:8000" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1
```

* Die **lokale Registrierung** wird übersprungen, wenn `CROWDSEC_API` nicht `127.0.0.1` oder `localhost` ist.
* **AppSec** ist standardmäßig deaktiviert, wenn eine externe API verwendet wird. Um es zu aktivieren, setzen Sie `CROWDSEC_APPSEC_URL` auf Ihren gewünschten Endpunkt.
* Die Bouncer-Registrierung erfolgt weiterhin gegen die entfernte API.
* Um einen vorhandenen Bouncer-Schlüssel wiederzuverwenden, geben Sie `CROWDSEC_API_KEY` mit Ihrem vorab generierten Token an.

---

!!! tip "Weitere Optionen"
    Eine vollständige Übersicht über alle CrowdSec-Optionen (benutzerdefinierte Szenarien, Protokolle, Fehlerbehebung und mehr) finden Sie in der [BunkerWeb CrowdSec-Plugin-Dokumentation](features.md#crowdsec) oder besuchen Sie die [offizielle CrowdSec-Website](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs).

## Docker

<figure markdown>
  ![Übersicht](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Docker-Integration</figcaption>
</figure>

Die Verwendung von BunkerWeb als [Docker](https://www.docker.com/)-Container bietet einen bequemen und unkomplizierten Ansatz zum Testen und Nutzen der Lösung, insbesondere wenn Sie bereits mit der Docker-Technologie vertraut sind.

Um Ihre Docker-Bereitstellung zu erleichtern, stellen wir auf [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb) vorgefertigte Images zur Verfügung, die mehrere Architekturen unterstützen. Diese vorgefertigten Images sind für die Verwendung auf den folgenden Architekturen optimiert und vorbereitet:

- x64 (64-Bit)
- x86
- armv8 (ARM 64-Bit)
- armv7 (ARM 32-Bit)

Durch den Zugriff auf diese vorgefertigten Images von Docker Hub können Sie BunkerWeb schnell in Ihrer Docker-Umgebung ziehen und ausführen, wodurch umfangreiche Konfigurations- oder Einrichtungsprozesse entfallen. Dieser optimierte Ansatz ermöglicht es Ihnen, sich auf die Nutzung der Funktionen von BunkerWeb zu konzentrieren, ohne unnötige Komplexität.

```shell
docker pull bunkerity/bunkerweb:1.6.7-rc1
```

Docker-Images sind auch auf [GitHub-Paketen](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) verfügbar und können über die Repository-Adresse `ghcr.io` heruntergeladen werden:

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.7-rc1
```

Schlüsselkonzepte für die Docker-Integration sind:

- **Umgebungsvariablen**: Konfigurieren Sie BunkerWeb einfach über Umgebungsvariablen. Mit diesen Variablen können Sie verschiedene Aspekte des Verhaltens von BunkerWeb anpassen, z. B. Netzwerkeinstellungen, Sicherheitsoptionen und andere Parameter.
- **Scheduler-Container**: Verwalten Sie die Konfiguration und führen Sie Jobs mit einem dedizierten Container namens [Scheduler](concepts.md#scheduler) aus.
- **Netzwerke**: Docker-Netzwerke spielen eine wichtige Rolle bei der Integration von BunkerWeb. Diese Netzwerke dienen zwei Hauptzwecken: dem Bereitstellen von Ports für Clients und dem Verbinden mit Upstream-Webdiensten. Durch das Bereitstellen von Ports kann BunkerWeb eingehende Anfragen von Clients annehmen und ihnen den Zugriff auf die geschützten Webdienste ermöglichen. Darüber hinaus kann BunkerWeb durch die Verbindung mit Upstream-Webdiensten den Datenverkehr effizient weiterleiten und verwalten und so eine verbesserte Sicherheit und Leistung bieten.

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie SQLite als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Es werden jedoch auch andere Datenbank-Backends unterstützt. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) des Repositorys.

### Umgebungsvariablen

Einstellungen werden dem Scheduler über Docker-Umgebungsvariablen übergeben:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
...
```

!!! info "Vollständige Liste"
    Die vollständige Liste der Umgebungsvariablen finden Sie im [Einstellungsbereich](features.md) der Dokumentation.

!!! tip "Beschriftete Container überspringen"
    Wenn ein Container von autoconf ignoriert werden soll, setzen Sie `DOCKER_IGNORE_LABELS` auf dem Controller. Geben Sie eine durch Leerzeichen oder Kommas getrennte Liste von Label-Schlüsseln an (zum Beispiel `bunkerweb.SERVER_NAME`) oder nur das Suffix (`SERVER_NAME`). Jeder Container oder jede benutzerdefinierte Konfigurationsquelle mit einem übereinstimmenden Label wird bei der Erkennung übersprungen, und das Label wird bei der Übersetzung der Einstellungen ignoriert.

### Verwendung von Docker-Secrets

Anstatt sensible Einstellungen über Umgebungsvariablen zu übergeben, können Sie sie als Docker-Secrets speichern. Erstellen Sie für jede Einstellung, die Sie sichern möchten, ein Docker-Secret mit dem Namen, der dem Einstellungsschlüssel entspricht (in Großbuchstaben). Die Einstiegsskripte von BunkerWeb laden Secrets automatisch aus `/run/secrets` und exportieren sie als Umgebungsvariablen.

Beispiel:
```bash
# Ein Docker-Secret für ADMIN_PASSWORD erstellen
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

Mounten Sie die Secrets bei der Bereitstellung:
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

Dadurch wird sichergestellt, dass sensible Einstellungen aus der Umgebung und den Protokollen herausgehalten werden.

### Scheduler

Der [Scheduler](concepts.md#scheduler) läuft in seinem eigenen Container, der auch auf Docker Hub verfügbar ist:

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.7-rc1
```

!!! info "BunkerWeb-Einstellungen"

    Seit Version `1.6.0` ist der Scheduler-Container der Ort, an dem Sie die Einstellungen für BunkerWeb definieren. Der Scheduler pusht die Konfiguration dann an den BunkerWeb-Container.

    ⚠ **Wichtig**: Alle API-bezogenen Einstellungen (wie `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME`, `API_WHITELIST_IP` und `API_TOKEN`, wenn Sie es verwenden) **müssen auch im BunkerWeb-Container definiert werden**. Die Einstellungen müssen in beiden Containern gespiegelt werden; andernfalls akzeptiert der BunkerWeb-Container keine API-Anfragen vom Scheduler.

    ```yaml
    x-bw-api-env: &bw-api-env
      # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
      API_HTTP_PORT: "5000" # Standardwert
      API_LISTEN_IP: "0.0.0.0" # Standardwert
      API_SERVER_NAME: "bwapi" # Standardwert
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Setzen Sie dies entsprechend Ihren Netzwerkeinstellungen
      # Optionaler Token; wenn gesetzt, sendet der Scheduler Authorization: Bearer <token>
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        environment:
          # Dies setzt die API-Einstellungen für den BunkerWeb-Container
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          # Dies setzt die API-Einstellungen für den Scheduler-Container
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

Ein Volume wird benötigt, um die vom Scheduler verwendete SQLite-Datenbank und Backups zu speichern:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Verwendung eines lokalen Ordners für persistente Daten"
    Der Scheduler läuft als **unprivilegierter Benutzer mit UID 101 und GID 101** im Container. Dies erhöht die Sicherheit: Im Falle einer ausgenutzten Schwachstelle hat der Angreifer keine vollen Root-Rechte (UID/GID 0).

    Wenn Sie jedoch einen **lokalen Ordner für persistente Daten** verwenden, müssen Sie **die richtigen Berechtigungen festlegen**, damit der unprivilegierte Benutzer Daten darin schreiben kann. Zum Beispiel:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternativ, wenn der Ordner bereits existiert:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) oder [Podman](https://podman.io/) verwenden, werden UIDs und GIDs im Container auf andere auf dem Host abgebildet. Sie müssen zuerst Ihre anfängliche subuid und subgid überprüfen:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Wenn Sie beispielsweise einen Wert von **100000** haben, ist die abgebildete UID/GID **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Oder wenn der Ordner bereits existiert:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### Scheduler-Container-Einstellungen

Der Scheduler ist der Control-Plane-Worker, der Einstellungen liest, Konfigurationen rendert und sie an BunkerWeb-Instanzen pusht. Die Einstellungen sind hier zentralisiert, inklusive Defaults und akzeptierter Werte.

#### Konfigurationsquellen und Priorität

1. Umgebungsvariablen (inkl. Docker/Compose `environment:`)
2. Secrets in `/run/secrets/<VAR>` (vom Entrypoint automatisch geladen)
3. Eingebaute Defaults

#### Konfigurationsreferenz (Power User)

##### Laufzeit & Sicherheit

| Setting                         | Beschreibung                                                                    | Akzeptierte Werte                                     | Standard                                   |
| ------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------ |
| `HEALTHCHECK_INTERVAL`          | Sekunden zwischen Scheduler-Healthchecks                                        | Ganze Sekunden                                        | `30`                                       |
| `RELOAD_MIN_TIMEOUT`            | Mindestsekunden zwischen aufeinanderfolgenden Reloads                           | Ganze Sekunden                                        | `5`                                        |
| `DISABLE_CONFIGURATION_TESTING` | Konfigtests vor dem Anwenden überspringen                                       | `yes` oder `no`                                       | `no`                                       |
| `IGNORE_FAIL_SENDING_CONFIG`    | Fortfahren, auch wenn einige Instanzen keine Konfig erhalten                    | `yes` oder `no`                                       | `no`                                       |
| `IGNORE_REGEX_CHECK`            | Regex-Validierung für Einstellungen überspringen (geteilt mit Autoconf)         | `yes` oder `no`                                       | `no`                                       |
| `TZ`                            | Zeitzone für Scheduler-Logs, Cron-ähnliche Jobs, Backups und Zeitstempel        | TZ-Datenbank-Name (z. B. `UTC`, `Europe/Paris`)        | unset (Container-Standard, meist UTC)      |

##### Datenbank

| Setting                 | Beschreibung                                                                             | Akzeptierte Werte      | Standard                                   |
| ----------------------- | ----------------------------------------------------------------------------------------- | ---------------------- | ------------------------------------------ |
| `DATABASE_URI`          | Primärer Datenbank-DSN (geteilt mit Autoconf und Instanzen)                               | SQLAlchemy-DSN         | `sqlite:////var/lib/bunkerweb/db.sqlite3`  |
| `DATABASE_URI_READONLY` | Optionaler Readonly-DSN; Scheduler fällt auf Readonly zurück, wenn nur dieser funktioniert | SQLAlchemy-DSN oder leer | unset                                   |

##### Logging

| Setting                         | Beschreibung                                                                | Akzeptierte Werte                                   | Standard                                                             |
| ------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Basis/Override Log-Level                                                     | `debug`, `info`, `warning`, `error`, `critical`     | `info`                                                               |
| `LOG_TYPES`                     | Ziele                                                                       | Leerzeichen-getrennt `stderr`/`file`/`syslog`       | `stderr`                                                             |
| `SCHEDULER_LOG_TO_FILE`         | File-Logging aktivieren und Standardpfad setzen                             | `yes` oder `no`                                     | `no`                                                                |
| `LOG_FILE_PATH`                 | Benutzerdefinierter Log-Pfad (genutzt wenn `LOG_TYPES` `file` enthält)       | Dateipfad                                           | `/var/log/bunkerweb/scheduler.log` bei `SCHEDULER_LOG_TO_FILE=yes`, sonst unset |
| `LOG_SYSLOG_ADDRESS`            | Syslog-Ziel (`udp://host:514`, `tcp://host:514` oder Socket-Pfad)            | Host:Port, Protokoll-präfixter Host oder Socket     | unset                                                                |
| `LOG_SYSLOG_TAG`                | Syslog-Ident/Tag                                                            | String                                              | `bw-scheduler`                                                       |

### UI-Container-Einstellungen

Der UI-Container respektiert ebenfalls `TZ`, um Logs und geplante Wartungsaufgaben (z. B. Cleanup-Jobs der UI) zu lokalisieren.

| Setting | Beschreibung                                    | Akzeptierte Werte                                | Standard                                 |
| ------- | ----------------------------------------------- | ---------------------------------------------- | ---------------------------------------- |
| `TZ`    | Zeitzone für UI-Logs und geplante Aktionen      | TZ-Datenbank-Name (z. B. `UTC`, `Europe/Paris`) | unset (Container-Standard, meist UTC)    |

#### Logging

| Setting                         | Beschreibung                                                                | Akzeptierte Werte                                   | Standard                                                             |
| ------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Basis-Log-Level / Override                                                  | `debug`, `info`, `warning`, `error`, `critical`     | `info`                                                               |
| `LOG_TYPES`                     | Ziele                                                                       | Leerzeichen-getrennt `stderr`/`file`/`syslog`       | `stderr`                                                             |
| `LOG_FILE_PATH`                 | Pfad für File-Logging (bei `LOG_TYPES` mit `file` oder `CAPTURE_OUTPUT=yes`) | Dateipfad                                           | `/var/log/bunkerweb/ui.log` bei file/capture, sonst unset           |
| `LOG_SYSLOG_ADDRESS`            | Syslog-Ziel (`udp://host:514`, `tcp://host:514`, Socket)                    | Host:Port, Protokoll-präfixter Host oder Pfad       | unset                                                                |
| `LOG_SYSLOG_TAG`                | Syslog-Ident/Tag                                                            | String                                              | `bw-ui`                                                              |
| `CAPTURE_OUTPUT`                | Gunicorn stdout/stderr an die konfigurierten Log-Ausgaben senden            | `yes` oder `no`                                     | `no`                                                                 |

### Netzwerke

Standardmäßig lauscht der BunkerWeb-Container (innerhalb des Containers) auf **8080/tcp** für **HTTP**, **8443/tcp** für **HTTPS** und **8443/udp** für **QUIC**.

!!! warning "Privilegierte Ports im rootless-Modus oder bei Verwendung von Podman"
    Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) verwenden und privilegierte Ports (< 1024) wie 80 und 443 an BunkerWeb weiterleiten möchten, beachten Sie bitte die Voraussetzungen [hier](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    Wenn Sie [Podman](https://podman.io/) verwenden, können Sie die Mindestanzahl für unprivilegierte Ports senken:
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

Der typische BunkerWeb-Stack bei Verwendung der Docker-Integration enthält die folgenden Container:

- BunkerWeb
- Scheduler
- Ihre Dienste

Aus Gründen der Tiefenverteidigung empfehlen wir dringend, mindestens drei verschiedene Docker-Netzwerke zu erstellen:

- `bw-services`: für BunkerWeb und Ihre Webdienste
- `bw-universe`: für BunkerWeb und den Scheduler
- `bw-db`: für die Datenbank (wenn Sie eine verwenden)

Um die Kommunikation zwischen dem Scheduler und der BunkerWeb-API zu sichern, **autorisieren Sie API-Aufrufe**. Verwenden Sie die Einstellung `API_WHITELIST_IP`, um zulässige IP-Adressen und Subnetze anzugeben. Für einen stärkeren Schutz setzen Sie `API_TOKEN` in beiden Containern; der Scheduler wird automatisch `Authorization: Bearer <token>` einschließen.

**Es wird dringend empfohlen, ein statisches Subnetz für das `bw-universe`-Netzwerk zu verwenden**, um die Sicherheit zu erhöhen. Durch die Umsetzung dieser Maßnahmen können Sie sicherstellen, dass nur autorisierte Quellen auf die BunkerWeb-API zugreifen können, was das Risiko von unbefugtem Zugriff oder böswilligen Aktivitäten verringert:

```yaml
x-bw-api-env: &bw-api-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  API_TOKEN: "" # Optionaler API-Token
  # Optionaler API-Token für authentifizierten API-Zugriff
  API_TOKEN: ""

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.7-rc1
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
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # Diese Einstellung ist obligatorisch, um die BunkerWeb-Instanz anzugeben
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
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
        - subnet: 10.20.30.0/24 # Statisches Subnetz, damit nur autorisierte Quellen auf die BunkerWeb-API zugreifen können
  bw-services:
    name: bw-services
```

### Vollständige Compose-Datei

```yaml
x-bw-api-env: &bw-api-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.7-rc1
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
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    depends_on:
      - bunkerweb
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # Diese Einstellung ist obligatorisch, um die BunkerWeb-Instanz anzugeben
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
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
        - subnet: 10.20.30.0/24 # Statisches Subnetz, damit nur autorisierte Quellen auf die BunkerWeb-API zugreifen können
  bw-services:
    name: bw-services
```

### Aus dem Quellcode erstellen

Alternativ, wenn Sie einen praxisorientierteren Ansatz bevorzugen, haben Sie die Möglichkeit, das Docker-Image direkt aus dem [Quellcode](https://github.com/bunkerity/bunkerweb) zu erstellen. Das Erstellen des Images aus dem Quellcode gibt Ihnen mehr Kontrolle und Anpassungsmöglichkeiten über den Bereitstellungsprozess. Bitte beachten Sie jedoch, dass diese Methode je nach Ihrer Hardwarekonfiguration einige Zeit in Anspruch nehmen kann (Sie können bei Bedarf einen Kaffee ☕ trinken).

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
  ![Übersicht](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Linux-Integration</figcaption>
</figure>

Unterstützte Linux-Distributionen für BunkerWeb (amd64/x86_64 und arm64/aarch64 Architekturen) sind:

- Debian 12 "Bookworm"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41, 42 und 43
- Red Hat Enterprise Linux (RHEL) 8, 9 und 10

### Einfaches Installationsskript

Für eine vereinfachte Installation bietet BunkerWeb ein einfaches Installationsskript, das den gesamten Einrichtungsprozess automatisch abwickelt, einschließlich NGINX-Installation, Repository-Konfiguration und Service-Setup.

#### Schnellstart

Um zu beginnen, laden Sie das Installationsskript und seine Prüfsumme herunter und überprüfen Sie dann die Integrität des Skripts, bevor Sie es ausführen.

```bash
# Skript und Prüfsumme herunterladen
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.7-rc1/install-bunkerweb.sh
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.7-rc1/install-bunkerweb.sh.sha256

# Prüfsumme überprüfen
sha256sum -c install-bunkerweb.sh.sha256

# Wenn die Überprüfung erfolgreich ist, Skript ausführen
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! danger "Sicherheitshinweis"
    **Überprüfen Sie immer die Integrität des Installationsskripts, bevor Sie es ausführen.**

    Laden Sie die Prüfsummendatei herunter und verwenden Sie ein Werkzeug wie `sha256sum`, um zu bestätigen, dass das Skript nicht verändert oder manipuliert wurde.

    Wenn die Überprüfung der Prüfsumme fehlschlägt, **führen Sie das Skript nicht aus** – es könnte unsicher sein.

#### Wie es funktioniert

Das einfache Installationsskript ist ein leistungsstarkes Werkzeug, das entwickelt wurde, um die Einrichtung von BunkerWeb auf einem frischen Linux-System zu optimieren. Es automatisiert die folgenden wichtigen Schritte:

1.  **Systemanalyse**: Erkennt Ihr Betriebssystem und überprüft es anhand der Liste der unterstützten Distributionen.
2.  **Anpassung der Installation**: Im interaktiven Modus werden Sie aufgefordert, einen Installationstyp (All-In-One, Manager, Worker usw.) auszuwählen und zu entscheiden, ob der webbasierte Einrichtungsassistent aktiviert werden soll.
3.  **Optionale Integrationen**: Bietet an, die [CrowdSec Security Engine](#crowdsec-integration-with-the-script) automatisch zu installieren und zu konfigurieren.
4.  **Abhängigkeitsmanagement**: Installiert die korrekte Version von NGINX, die von BunkerWeb benötigt wird, aus offiziellen Quellen und sperrt die Version, um unbeabsichtigte Upgrades zu verhindern.
5.  **BunkerWeb-Installation**: Fügt das BunkerWeb-Paket-Repository hinzu, installiert die erforderlichen Pakete und sperrt die Version.
6.  **Dienstkonfiguration**: Richtet die `systemd`-Dienste entsprechend dem von Ihnen gewählten Installationstyp ein und aktiviert sie.
7.  **Anleitung nach der Installation**: Bietet klare nächste Schritte, um Ihnen den Einstieg in Ihre neue BunkerWeb-Instanz zu erleichtern.

#### Interaktive Installation

Wenn das Skript ohne Optionen ausgeführt wird, wechselt es in einen interaktiven Modus, der Sie durch den Einrichtungsprozess führt. Sie werden gebeten, die folgenden Entscheidungen zu treffen:

1.  **Installationstyp**: Wählen Sie die Komponenten aus, die Sie installieren möchten.
    *   **Full Stack (Standard)**: Eine All-in-One-Installation mit BunkerWeb, dem Scheduler und der Web-UI.
    *   **Manager**: Installiert den Scheduler und die Web-UI, um einen oder mehrere entfernte BunkerWeb-Worker zu verwalten.
    *   **Worker**: Installiert nur die BunkerWeb-Instanz, die von einem entfernten Manager verwaltet werden kann.
    *   **Nur Scheduler**: Installiert nur die Scheduler-Komponente.
    *   **Nur Web-UI**: Installiert nur die Web-UI-Komponente.
    *   **Nur API**: Installiert nur den API-Dienst für programmgesteuerten Zugriff.
2.  **Einrichtungsassistent**: Wählen Sie, ob der webbasierte Konfigurationsassistent aktiviert werden soll. Dies wird für Erstanwender dringend empfohlen.
3.  **CrowdSec-Integration**: Entscheiden Sie sich für die Installation der CrowdSec-Sicherheits-Engine für erweiterten Echtzeit-Bedrohungsschutz. Nur für Full Stack-Installationen verfügbar.
4.  **CrowdSec AppSec**: Wenn Sie sich für die Installation von CrowdSec entscheiden, können Sie auch die Application Security (AppSec)-Komponente aktivieren, die WAF-Funktionen hinzufügt.
5.  **DNS-Resolver**: Für Full Stack-, Manager- und Worker-Installationen können Sie optional benutzerdefinierte DNS-Resolver-IPs angeben.
6.  **Interne API HTTPS**: Für Full Stack-, Manager- und Worker-Installationen können Sie HTTPS für die interne API-Kommunikation zwischen Scheduler/Manager und BunkerWeb/Worker-Instanzen aktivieren (Standard: nur HTTP).
7.  **API-Dienst**: Für Full Stack- und Manager-Installationen können Sie den optionalen externen API-Dienst aktivieren. Er ist bei Linux-Installationen standardmäßig deaktiviert.

!!! info "Manager- und Scheduler-Installationen"
    Wenn Sie den Installationstyp **Manager** oder **Nur Scheduler** wählen, werden Sie auch aufgefordert, die IP-Adressen oder Hostnamen Ihrer BunkerWeb-Worker-Instanzen anzugeben.

#### Befehlszeilenoptionen

Für nicht-interaktive oder automatisierte Setups kann das Skript mit Befehlszeilen-Flags gesteuert werden:

**Allgemeine Optionen:**

| Option                  | Beschreibung                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------- |
| `-v, --version VERSION` | Gibt die zu installierende BunkerWeb-Version an (z. B. `1.6.7~rc1`).                            |
| `-w, --enable-wizard`   | Aktiviert den Einrichtungsassistenten.                                                      |
| `-n, --no-wizard`       | Deaktiviert den Einrichtungsassistenten.                                                    |
| `-y, --yes`             | Führt im nicht-interaktiven Modus mit Standardantworten für alle Eingabeaufforderungen aus. |
| `-f, --force`           | Erzwingt die Installation, auch auf einer nicht unterstützten Betriebssystemversion.        |
| `-q, --quiet`           | Stille Installation (unterdrückt die Ausgabe).                                              |
| `--api`, `--enable-api` | Aktiviert den API (FastAPI) systemd-Dienst (standardmäßig deaktiviert).                     |
| `--no-api`              | Deaktiviert den API-Dienst explizit.                                                        |
| `-h, --help`            | Zeigt die Hilfenachricht mit allen verfügbaren Optionen an.                                 |
| `--dry-run`             | Zeigt an, was installiert würde, ohne es zu tun.                                            |

**Installationstypen:**

| Option             | Beschreibung                                                                       |
| ------------------ | ---------------------------------------------------------------------------------- |
| `--full`           | Vollständige Stack-Installation (BunkerWeb, Scheduler, UI). Dies ist der Standard. |
| `--manager`        | Installiert den Scheduler und die UI zur Verwaltung von Remote-Workern.            |
| `--worker`         | Installiert nur die BunkerWeb-Instanz.                                             |
| `--scheduler-only` | Installiert nur die Scheduler-Komponente.                                          |
| `--ui-only`        | Installiert nur die Web-UI-Komponente.                                             |
| `--api-only`       | Installiert nur den API-Dienst (Port 8000).                                        |

**Sicherheitsintegrationen:**

| Option              | Beschreibung                                                                    |
| ------------------- | ------------------------------------------------------------------------------- |
| `--crowdsec`        | Installiert und konfiguriert die CrowdSec-Sicherheits-Engine.                   |
| `--no-crowdsec`     | Überspringt die CrowdSec-Installation.                                          |
| `--crowdsec-appsec` | Installiert CrowdSec mit der AppSec-Komponente (einschließlich WAF-Funktionen). |

**Erweiterte Optionen:**

| Option                      | Beschreibung                                                                                          |
| --------------------------- | ----------------------------------------------------------------------------------------------------- |
| `--instances "IP1 IP2"`     | Durch Leerzeichen getrennte Liste von BunkerWeb-Instanzen (erforderlich für Manager-/Scheduler-Modi). |
| `--manager-ip IPs`          | Manager-/Scheduler-IPs zur Whitelist (erforderlich für Worker im nicht-interaktiven Modus).           |
| `--dns-resolvers "IP1 IP2"` | Benutzerdefinierte DNS-Resolver-IPs (für Full-, Manager- oder Worker-Installationen).                 |
| `--api-https`               | HTTPS für interne API-Kommunikation aktivieren (Standard: nur HTTP).                                  |
| `--backup-dir PATH`         | Verzeichnis zum Speichern der automatischen Sicherung vor dem Upgrade.                                |
| `--no-auto-backup`          | Automatische Sicherung überspringen (Sie MÜSSEN es manuell getan haben).                              |

**Beispielverwendung:**

```bash
# Im interaktiven Modus ausführen (für die meisten Benutzer empfohlen)
sudo ./install-bunkerweb.sh

# Nicht-interaktive Installation mit Standardeinstellungen (vollständiger Stack, Assistent aktiviert)
sudo ./install-bunkerweb.sh --yes

# Einen Worker-Knoten ohne Einrichtungsassistent installieren
sudo ./install-bunkerweb.sh --worker --no-wizard

# Eine bestimmte Version installieren
sudo ./install-bunkerweb.sh --version 1.6.7~rc1

# Manager-Setup mit entfernten Worker-Instanzen (Instanzen erforderlich)
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# Manager mit interner HTTPS-API-Kommunikation
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11" --api-https

# Worker mit benutzerdefinierten DNS-Resolvern und interner HTTPS-API
sudo ./install-bunkerweb.sh --worker --dns-resolvers "1.1.1.1 1.0.0.1" --api-https

# Vollständige Installation mit CrowdSec und AppSec
sudo ./install-bunkerweb.sh --crowdsec-appsec

# Stille nicht-interaktive Installation
sudo ./install-bunkerweb.sh --quiet --yes

# Installationsvorschau ohne Ausführung
sudo ./install-bunkerweb.sh --dry-run

# API während der einfachen Installation aktivieren (nicht-interaktiv)
sudo ./install-bunkerweb.sh --yes --api

# Fehler: CrowdSec kann nicht mit Worker-Installationen verwendet werden
# sudo ./install-bunkerweb.sh --worker --crowdsec  # Dies schlägt fehl

# Fehler: Instanzen für Manager im nicht-interaktiven Modus erforderlich
# sudo ./install-bunkerweb.sh --manager --yes  # Dies schlägt ohne --instances fehl
```

!!! warning "Wichtige Hinweise zur Optionskompatibilität"

    **CrowdSec-Einschränkungen:**

    - CrowdSec-Optionen (`--crowdsec`, `--crowdsec-appsec`) sind nur mit dem Installationstyp `--full` (Standard) kompatibel
    - Sie können nicht mit `--manager`, `--worker`, `--scheduler-only`, `--ui-only` oder `--api-only` Installationen verwendet werden

    **Verfügbarkeit des API-Dienstes:**

    - Der externe API-Dienst (Port 8000) ist für die Installationstypen `--full` und `--manager` verfügbar
    - Er ist nicht verfügbar für `--worker`, `--scheduler-only` oder `--ui-only` Installationen
    - Verwenden Sie `--api-only` für eine dedizierte API-Dienst-Installation

    **Anforderungen für Instanzen:**
    - Die Option `--instances` ist nur mit den Installationstypen `--manager` und `--scheduler-only` gültig
    - Bei Verwendung von `--manager` oder `--scheduler-only` mit `--yes` (nicht-interaktiver Modus) ist die Option `--instances` obligatorisch
    - Format: `--instances "192.168.1.10 192.168.1.11 192.168.1.12"`

    **Interaktiv vs. Nicht-interaktiv:**
    - Der interaktive Modus (Standard) fordert zur Eingabe fehlender erforderlicher Werte auf
    - Der nicht-interaktive Modus (`--yes`) erfordert, dass alle erforderlichen Optionen über die Befehlszeile bereitgestellt werden

#### CrowdSec-Integration mit dem Skript {#crowdsec-integration-with-the-script}

Wenn Sie sich für die Installation von CrowdSec während der interaktiven Einrichtung entscheiden, automatisiert das Skript die Integration mit BunkerWeb vollständig:

- Es fügt das offizielle CrowdSec-Repository hinzu und installiert den Agenten.
- Es erstellt eine neue Erfassungsdatei, damit CrowdSec die Protokolle von BunkerWeb (`access.log`, `error.log` und `modsec_audit.log`) parsen kann.
- Es installiert wesentliche Sammlungen (`bunkerity/bunkerweb`) und Parser (`crowdsecurity/geoip-enrich`).
- Es registriert einen Bouncer für BunkerWeb und konfiguriert den API-Schlüssel automatisch in `/etc/bunkerweb/variables.env`.
- Wenn Sie auch die **AppSec-Komponente** auswählen, installiert es die Sammlungen `appsec-virtual-patching` und `appsec-generic-rules` und konfiguriert den AppSec-Endpunkt für BunkerWeb.

Dies bietet eine nahtlose, sofort einsatzbereite Integration für einen leistungsstarken Einbruchschutz.

#### RHEL-Überlegungen

!!! warning "Unterstützung externer Datenbanken auf RHEL-basierten Systemen"
    Wenn Sie eine externe Datenbank verwenden möchten (empfohlen für die Produktion), müssen Sie das entsprechende Datenbank-Client-Paket installieren:

    ```bash
    # Für MariaDB
    sudo dnf install mariadb

    # Für MySQL
    sudo dnf install mysql

    # Für PostgreSQL
    sudo dnf install postgresql
    ```

    Dies ist erforderlich, damit der BunkerWeb-Scheduler eine Verbindung zu Ihrer externen Datenbank herstellen kann.

#### Nach der Installation

Abhängig von Ihren Entscheidungen während der Installation:

**Mit aktiviertem Einrichtungsassistenten:**

1. Greifen Sie auf den Einrichtungsassistenten unter `https://ihre-server-ip/setup` zu
2. Befolgen Sie die geführte Konfiguration, um Ihren ersten geschützten Dienst einzurichten
3. Konfigurieren Sie SSL/TLS-Zertifikate und andere Sicherheitseinstellungen

**Ohne Einrichtungsassistent:**

1. Bearbeiten Sie `/etc/bunkerweb/variables.env`, um BunkerWeb manuell zu konfigurieren
2. Fügen Sie Ihre Servereinstellungen und geschützten Dienste hinzu
3. Starten Sie den Scheduler neu: `sudo systemctl restart bunkerweb-scheduler`

### Installation über den Paketmanager

Bitte stellen Sie sicher, dass Sie **NGINX 1.28.0 installiert haben, bevor Sie BunkerWeb installieren**. Für alle Distributionen außer Fedora ist es zwingend erforderlich, vorgefertigte Pakete aus dem [offiziellen NGINX-Repository](https://nginx.org/en/linux_packages.html) zu verwenden. Das Kompilieren von NGINX aus dem Quellcode oder die Verwendung von Paketen aus verschiedenen Repositories funktioniert nicht mit den offiziellen vorgefertigten Paketen von BunkerWeb. Sie haben jedoch die Möglichkeit, BunkerWeb aus dem Quellcode zu erstellen.

=== "Debian Bookworm/Trixie"

    Der erste Schritt ist das Hinzufügen des offiziellen NGINX-Repositorys:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Sie sollten jetzt NGINX 1.28.0 installieren können:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev-Version"
        Wenn Sie die `testing`- oder `dev`-Version verwenden, müssen Sie die Direktive `force-bad-version` zu Ihrer `/etc/dpkg/dpkg.cfg`-Datei hinzufügen, bevor Sie BunkerWeb installieren.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `apt upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    Der erste Schritt ist das Hinzufügen des offiziellen NGINX-Repositorys:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Sie sollten jetzt NGINX 1.28.0 installieren können:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Testing/dev-Version"
        Wenn Sie die `testing`- oder `dev`-Version verwenden, müssen Sie die Direktive `force-bad-version` zu Ihrer `/etc/dpkg/dpkg.cfg`-Datei hinzufügen, bevor Sie BunkerWeb installieren.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `apt upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora Update Testing"
        Wenn Sie die NGINX-Version nicht im stabilen Repository finden können, können Sie das `updates-testing`-Repository aktivieren:

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora stellt bereits NGINX 1.28.0 zur Verfügung, das wir unterstützen

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.0
    ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y --allowerasing bunkerweb-1.6.7~rc1
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `dnf upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    Der erste Schritt ist das Hinzufügen des offiziellen NGINX-Repositorys. Erstellen Sie die folgende Datei unter `/etc/yum.repos.d/nginx.repo`:

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

    Sie sollten jetzt NGINX 1.28.0 installieren können:

    ```shell
    sudo dnf install --allowerasing nginx-1.28.0
    ```

    !!! example "Einrichtungsassistenten deaktivieren"
        Wenn Sie den Einrichtungsassistenten der Web-UI bei der Installation von BunkerWeb nicht verwenden möchten, exportieren Sie die folgende Variable:

        ```shell
        export UI_WIZARD=no
        ```

    Und installieren Sie schließlich BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.7~rc1
    ```

    Um ein Upgrade der NGINX- und/oder BunkerWeb-Pakete bei der Ausführung von `dnf upgrade` zu verhindern, können Sie den folgenden Befehl verwenden:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### Konfiguration und Dienst

Die manuelle Konfiguration von BunkerWeb erfolgt durch Bearbeiten der Datei `/etc/bunkerweb/variables.env`:

```conf
MEINE_EINSTELLUNG_1=wert1
MEINE_EINSTELLUNG_2=wert2
...```

Bei der Installation wird BunkerWeb mit drei Diensten `bunkerweb`, `bunkerweb-scheduler` und `bunkerweb-ui` geliefert, die Sie mit `systemctl` verwalten können.

Wenn Sie die BunkerWeb-Konfiguration manuell über `/etc/bunkerweb/variables.env` bearbeiten, reicht ein Neustart des `bunkerweb-scheduler`-Dienstes aus, um die Konfiguration ohne Ausfallzeit zu generieren und neu zu laden. In bestimmten Fällen (z. B. bei Änderung der lauschenden Ports) müssen Sie jedoch möglicherweise den `bunkerweb`-Dienst neu starten.

### Hochverfügbarkeit

Der Scheduler kann von der BunkerWeb-Instanz getrennt werden, um eine hohe Verfügbarkeit zu gewährleisten. In diesem Fall wird der Scheduler auf einem separaten Server installiert und kann mehrere BunkerWeb-Instanzen verwalten.

#### Manager

Um nur den Scheduler auf einem Server zu installieren, können Sie die folgenden Variablen exportieren, bevor Sie die BunkerWeb-Installation ausführen:

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

Alternativ können Sie auch die folgenden Variablen exportieren, um nur den Scheduler zu aktivieren:

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

#### Worker

Um nur BunkerWeb auf einem anderen Server zu installieren, können Sie die folgenden Variablen exportieren, bevor Sie die BunkerWeb-Installation ausführen:

```shell
export WORKER_MODE=yes
```

Alternativ können Sie auch die folgenden Variablen exportieren, um nur BunkerWeb zu aktivieren:

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

#### Web-UI

Die Web-UI kann auf einem separaten Server installiert werden, um eine dedizierte Schnittstelle zur Verwaltung von BunkerWeb-Instanzen bereitzustellen. Um nur die Web-UI zu installieren, können Sie die folgenden Variablen exportieren, bevor Sie die BunkerWeb-Installation ausführen:

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

## Docker Autoconf

<figure markdown>
  ![Übersicht](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Docker Autoconf-Integration</figcaption>
</figure>

!!! info "Docker-Integration"
    Die Docker Autoconf-Integration ist eine "Weiterentwicklung" der Docker-Integration. Bitte lesen Sie bei Bedarf zuerst den [Docker-Integrationsabschnitt](#docker).

Ein alternativer Ansatz ist verfügbar, um die Unannehmlichkeit zu beheben, den Container bei jedem Update neu erstellen zu müssen. Durch die Verwendung eines anderen Images namens **autoconf** können Sie die Echtzeit-Rekonfiguration von BunkerWeb automatisieren, ohne dass eine Neuerstellung des Containers erforderlich ist.

Um diese Funktionalität zu nutzen, können Sie anstelle von Umgebungsvariablen für den BunkerWeb-Container **Labels** zu Ihren Webanwendungs-Containern hinzufügen. Das **autoconf**-Image lauscht dann auf Docker-Ereignisse und übernimmt nahtlos die Konfigurationsupdates für BunkerWeb.

Dieser "*automagische*" Prozess vereinfacht die Verwaltung von BunkerWeb-Konfigurationen. Durch das Hinzufügen von Labels zu Ihren Webanwendungs-Containern können Sie die Rekonfigurationsaufgaben an **autoconf** delegieren, ohne den manuellen Eingriff der Neuerstellung des Containers. Dies optimiert den Aktualisierungsprozess und erhöht den Komfort.

Durch die Übernahme dieses Ansatzes können Sie eine Echtzeit-Rekonfiguration von BunkerWeb ohne den Aufwand der Neuerstellung von Containern genießen, was es effizienter und benutzerfreundlicher macht.

!!! info "Multisite-Modus"
    Die Docker Autoconf-Integration impliziert die Verwendung des **Multisite-Modus**. Weitere Informationen finden Sie im [Multisite-Abschnitt](concepts.md#multisite-mode) der Dokumentation.

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie MariaDB als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Wir verstehen jedoch, dass Sie möglicherweise alternative Backends für Ihre Docker-Integration bevorzugen. In diesem Fall können Sie sicher sein, dass auch andere Datenbank-Backends möglich sind. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) des Repositorys.

Um automatisierte Konfigurationsupdates zu ermöglichen, fügen Sie einen zusätzlichen Container namens `bw-autoconf` zum Stack hinzu. Dieser Container hostet den Autoconf-Dienst, der dynamische Konfigurationsänderungen für BunkerWeb verwaltet.

Um diese Funktionalität zu unterstützen, verwenden Sie ein dediziertes "echtes" Datenbank-Backend (z. B. MariaDB, MySQL oder PostgreSQL) zur synchronisierten Konfigurationsspeicherung. Durch die Integration von `bw-autoconf` und einem geeigneten Datenbank-Backend schaffen Sie die Infrastruktur für eine nahtlose automatisierte Konfigurationsverwaltung in BunkerWeb.

```yaml
x-bw-env: &bw-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Container zu vermeiden
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.7-rc1
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    labels:
      - "bunkerweb.INSTANCE=yes" # Obligatorisches Label für den Autoconf-Dienst, um die BunkerWeb-Instanz zu identifizieren
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # Wir müssen die BunkerWeb-Instanz hier nicht angeben, da sie automatisch vom Autoconf-Dienst erkannt werden
      SERVER_NAME: "" # Der Servername wird mit Dienst-Labels gefüllt
      MULTISITE: "yes" # Obligatorische Einstellung für Autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
    depends_on:
      - bunkerweb
      - bw-docker
    environment:
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
      DOCKER_HOST: "tcp://bw-docker:2375" # Der Docker-Socket
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
    # Wir setzen die maximal zulässige Paketgröße, um Probleme mit großen Abfragen zu vermeiden
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
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

!!! info "Datenbank im `bw-db`-Netzwerk"
    Der Datenbankcontainer ist absichtlich nicht im `bw-universe`-Netzwerk enthalten. Er wird von den Containern `bw-autoconf` und `bw-scheduler` und nicht direkt von BunkerWeb verwendet. Daher ist der Datenbankcontainer Teil des `bw-db`-Netzwerks, was die Sicherheit erhöht, indem der externe Zugriff auf die Datenbank erschwert wird. **Diese bewusste Designentscheidung hilft, die Datenbank zu schützen und die allgemeine Sicherheitsperspektive des Systems zu stärken**.

!!! warning "Verwendung von Docker im rootless-Modus"
    Wenn Sie [Docker im rootless-Modus](https://docs.docker.com/engine/security/rootless) verwenden, müssen Sie den Mount des Docker-Sockets durch den folgenden Wert ersetzen: `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Autoconf-Container-Einstellungen

Der `bw-autoconf`-Controller überwacht Ihren Orchestrator und schreibt Änderungen in die gemeinsame Datenbank.

#### Konfigurationsquellen und Priorität

1. Umgebungsvariablen (inkl. Docker/Compose `environment:`)
2. Secrets in `/run/secrets/<VAR>` (vom Entrypoint automatisch geladen)
3. Eingebaute Defaults

#### Konfigurationsreferenz (Power User)

##### Modus & Laufzeit

| Setting               | Beschreibung                                                 | Akzeptierte Werte                        | Standard                        |
| --------------------- | ------------------------------------------------------------- | ---------------------------------------- | -------------------------------- |
| `AUTOCONF_MODE`       | Autoconf-Controller aktivieren                               | `yes` oder `no`                          | `no`                             |
| `SWARM_MODE`          | Swarm-Services statt Docker-Containern beobachten            | `yes` oder `no`                          | `no`                             |
| `KUBERNETES_MODE`     | Kubernetes Ingresses/Pods statt Docker beobachten            | `yes` oder `no`                          | `no`                             |
| `DOCKER_HOST`         | Docker-Socket / Remote-API-URL                               | z. B. `unix:///var/run/docker.sock`      | `unix:///var/run/docker.sock`    |
| `WAIT_RETRY_INTERVAL` | Sekunden zwischen Readiness-Checks für Instanzen             | Ganze Sekunden                           | `5`                              |
| `LOG_SYSLOG_TAG`      | Syslog-Tag für Autoconf-Logs                                 | String                                   | `bw-autoconf`                    |
| `TZ`                  | Zeitzone für Autoconf-Logs und Zeitstempel                   | TZ-Datenbank-Name (z. B. `Europe/Paris`) | unset (Container-Standard, meist UTC) |

##### Datenbank & Validierung

| Setting                 | Beschreibung                                                                          | Akzeptierte Werte         | Standard                                   |
| ----------------------- | -------------------------------------------------------------------------------------- | ------------------------- | ------------------------------------------ |
| `DATABASE_URI`          | Primärer Datenbank-DSN (muss mit der Scheduler-DB übereinstimmen)                      | SQLAlchemy-DSN            | `sqlite:////var/lib/bunkerweb/db.sqlite3`  |
| `DATABASE_URI_READONLY` | Optionaler Readonly-DSN; Autoconf wechselt auf Readonly, wenn nur dieser funktioniert  | SQLAlchemy-DSN oder leer  | unset                                      |
| `IGNORE_REGEX_CHECK`    | Regex-Validierung für Einstellungen aus Labels/Annotationen überspringen               | `yes` oder `no`           | `no`                                       |

##### Logging

| Setting                         | Beschreibung                                                | Akzeptierte Werte                                   | Standard                                     |
| ------------------------------- | ----------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Basis-Log-Level / Override                                  | `debug`, `info`, `warning`, `error`, `critical`     | `info`                                       |
| `LOG_TYPES`                     | Ziele                                                       | Leerzeichen-getrennt `stderr`/`file`/`syslog`       | `stderr`                                     |
| `LOG_FILE_PATH`                 | Pfad für File-Logging (wenn `LOG_TYPES` `file` enthält)     | Dateipfad                                           | unset (eigenen Pfad setzen, wenn `file`)     |
| `LOG_SYSLOG_ADDRESS`            | Syslog-Ziel (`udp://host:514`, `tcp://host:514`, Socket)    | Host:Port, Protokoll-präfixter Host oder Pfad       | unset                                        |
| `LOG_SYSLOG_TAG`                | Syslog-Ident/Tag                                            | String                                              | `bw-autoconf`                                |

##### Umfang & Discovery-Filter

| Setting                         | Beschreibung                                                                | Akzeptierte Werte                             | Standard |
| ------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------- | ------- |
| `NAMESPACES`                    | Durch Leerzeichen getrennte Liste verwalteter Namespaces/Projekte; unset = alle | Leerzeichen-getrennte Strings                 | unset   |
| `DOCKER_IGNORE_LABELS`          | Container/Labels beim Sammeln von Instanzen/Services/Configs überspringen    | Leer-/kommagetrennte volle Keys oder Suffixe  | unset   |
| `SWARM_IGNORE_LABELS`           | Swarm-Services/Configs mit passenden Labels ignorieren                       | Leer-/kommagetrennte volle Keys oder Suffixe  | unset   |
| `KUBERNETES_IGNORE_ANNOTATIONS` | Ingress/Pod-Annotationen bei der Discovery ignorieren                        | Leer-/kommagetrennte volle Keys oder Suffixe  | unset   |

##### Nur Kubernetes

| Setting                                 | Beschreibung                                                                                   | Akzeptierte Werte        | Standard          |
| --------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------ | ----------------- |
| `KUBERNETES_VERIFY_SSL`                 | TLS der Kubernetes-API verifizieren                                                            | `yes` oder `no`          | `yes`             |
| `KUBERNETES_SSL_CA_CERT`                | Pfad zu einem benutzerdefinierten CA-Bundle für die Kubernetes-API                             | Dateipfad                | unset             |
| `USE_KUBERNETES_FQDN`                   | `<pod>.<ns>.pod.<domain>` statt Pod-IP als Instanz-Hostname verwenden                          | `yes` oder `no`          | `yes`             |
| `KUBERNETES_INGRESS_CLASS`              | Nur Ingresses mit dieser Klasse verarbeiten                                                    | String                   | unset (alle)      |
| `KUBERNETES_DOMAIN_NAME`                | Cluster-Domain-Suffix beim Bauen von Upstream-Hosts                                            | String                   | `cluster.local`   |
| `KUBERNETES_SERVICE_PROTOCOL`           | Schema für generierte Reverse-Proxy-Hosts                                                      | `http` oder `https`      | `http`            |
| `BUNKERWEB_SERVICE_NAME`                | Service-Name, der beim Patchen des Ingress-Status gelesen wird                                 | String                   | `bunkerweb`       |
| `BUNKERWEB_NAMESPACE`                   | Namespace dieses Services                                                                      | String                   | `bunkerweb`       |
| `KUBERNETES_REVERSE_PROXY_SUFFIX_START` | Startindex für generierte `REVERSE_PROXY_HOST_n`/`REVERSE_PROXY_URL_n` bei Multi-Path-Ingresses | Integer (>=0)            | `1`               |

### Autoconf-Dienste

Sobald der Stack eingerichtet ist, können Sie den Webanwendungs-Container erstellen und die Einstellungen als Labels mit dem Präfix "bunkerweb" hinzufügen, um BunkerWeb automatisch einzurichten:

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

Ab Version `1.6.0` unterstützen die Autoconf-Stacks von BunkerWeb Namespaces. Mit dieser Funktion können Sie mehrere "*Cluster*" von BunkerWeb-Instanzen und -Diensten auf demselben Docker-Host verwalten. Um Namespaces zu nutzen, setzen Sie einfach das `NAMESPACE`-Label auf Ihre Dienste. Hier ist ein Beispiel:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für den Dienst
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace-Verhalten"

    Standardmäßig lauschen alle Autoconf-Stacks auf alle Namespaces. Wenn Sie einen Stack auf bestimmte Namespaces beschränken möchten, können Sie die Umgebungsvariable `NAMESPACES` im `bw-autoconf`-Dienst setzen:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für die BunkerWeb-Instanz, damit der Autoconf-Dienst sie erkennen kann
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # Lauschen Sie nur auf diese Namespaces
    ...
    ```

    Beachten Sie, dass die Umgebungsvariable `NAMESPACES` eine durch Leerzeichen getrennte Liste von Namespaces ist.

!!! warning "Namespace-Spezifikationen"

    Es kann nur **eine Datenbank** und **ein Scheduler** pro Namespace geben. Wenn Sie versuchen, mehrere Datenbanken oder Scheduler im selben Namespace zu erstellen, kommt es zu Konfigurationskonflikten.

    Der Scheduler benötigt das `NAMESPACE`-Label nicht, um ordnungsgemäß zu funktionieren. Er benötigt nur die korrekt konfigurierte Einstellung `DATABASE_URI`, damit er auf dieselbe Datenbank wie der Autoconf-Dienst zugreifen kann.

## Kubernetes

<figure markdown>
  ![Übersicht](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Kubernetes-Integration</figcaption>
</figure>

Um die Konfiguration von BunkerWeb-Instanzen in einer Kubernetes-Umgebung zu automatisieren,
dient der Autoconf-Dienst als [Ingress-Controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/).
Er konfiguriert die BunkerWeb-Instanzen basierend auf [Ingress-Ressourcen](https://kubernetes.io/docs/concepts/services-networking/ingress/)
und überwacht auch andere Kubernetes-Objekte wie [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/)
für benutzerdefinierte Konfigurationen.

!!! info "ConfigMap-Abgleich"
    - Der Ingress-Controller verwaltet nur ConfigMaps, die die Annotation `bunkerweb.io/CONFIG_TYPE` enthalten.
    - Ergänzen Sie `bunkerweb.io/CONFIG_SITE`, wenn die Konfiguration auf einen einzelnen Dienst eingeschränkt werden soll
      (der Servername muss bereits existieren); lassen Sie die Annotation weg, um sie global anzuwenden.
    - Wird die Annotation entfernt oder die ConfigMap gelöscht, verschwindet die zugehörige benutzerdefinierte Konfiguration in BunkerWeb.

Für eine optimale Einrichtung wird empfohlen, BunkerWeb als **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)** zu definieren, was sicherstellt, dass auf allen Knoten ein Pod erstellt wird, während **Autoconf und Scheduler** als **einzeln repliziertes [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)** definiert werden.

Angesichts des Vorhandenseins mehrerer BunkerWeb-Instanzen ist es erforderlich, einen gemeinsamen Datenspeicher zu implementieren, der als [Redis](https://redis.io/)- oder [Valkey](https://valkey.io/)-Dienst realisiert wird. Dieser Dienst wird von den Instanzen genutzt, um Daten zwischen ihnen zu cachen und zu teilen. Weitere Informationen zu den Redis/Valkey-Einstellungen finden Sie [hier](features.md#redis).

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie MariaDB als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Wir verstehen jedoch, dass Sie möglicherweise alternative Backends für Ihre Docker-Integration bevorzugen. In diesem Fall können Sie sicher sein, dass auch andere Datenbank-Backends möglich sind. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) des Repositorys.

    Die Einrichtung von geclusterten Datenbank-Backends liegt außerhalb des Geltungsbereichs dieser Dokumentation.

Bitte stellen Sie sicher, dass die Autoconf-Dienste Zugriff auf die Kubernetes-API haben. Es wird empfohlen, hierfür die [RBAC-Autorisierung](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) zu verwenden.

!!! warning "Benutzerdefinierte CA für die Kubernetes-API"
    Wenn Sie eine benutzerdefinierte CA für Ihre Kubernetes-API verwenden, können Sie eine Bundle-Datei mit Ihren Zwischen- und Stammzertifikaten auf dem Ingress-Controller mounten und den Umgebungswert `KUBERNETES_SSL_CA_CERT` auf den Pfad des Bundles im Container setzen. Alternativ können Sie, auch wenn es nicht empfohlen wird, die Zertifikatsüberprüfung deaktivieren, indem Sie die Umgebungsvariable `KUBERNETES_SSL_VERIFY` des Ingress-Controllers auf `no` setzen (Standard ist `yes`).

Darüber hinaus **ist es entscheidend, die Umgebungsvariable `KUBERNETES_MODE` auf `yes` zu setzen, wenn die Kubernetes-Integration verwendet wird**. Diese Variable ist für die ordnungsgemäße Funktionalität obligatorisch.

### Installationsmethoden

#### Verwendung des Helm-Charts (empfohlen)

Die empfohlene Methode zur Installation von Kubernetes ist die Verwendung des Helm-Charts, das unter `https://repo.bunkerweb.io/charts` verfügbar ist:

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

Sie können dann das BunkerWeb-Helm-Chart aus diesem Repository verwenden:

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

Die vollständige Liste der Werte ist in der Datei [charts/bunkerweb/values.yaml](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) des [bunkerity/bunkerweb-helm-Repositorys](https://github.com/bunkerity/bunkerweb-helm) aufgeführt.

#### Sidecar Container + Helm

This documentation explains how to deploy BunkerWeb as a sidecar to protect your Kubernetes applications. In this architecture, each application has its own BunkerWeb container acting as a security reverse proxy.

##### Architecture

```mermaid
flowchart TB

  %% ---------- Stil ----------
  classDef scheduler     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef podContainer  fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:6 3,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;

  %% ---------- Oben: Scheduler ----------
  SCHED["BunkerWeb Scheduler (zentralisiert)<br/>+ UI + MariaDB + Redis"]:::scheduler

  %% ---------- Pods-Gruppe ----------
  subgraph PODS["Pods"]
    %% Anwendungs-Pod 1 ----------
    subgraph POD1["Anwendungs-Pod"]
      BW1["BunkerWeb"]:::component
      APP1["Anwendung<br/>(Port 80)"]:::component
      BW1 -->|legitime Anfragen| APP1
    end
    class POD1 podContainer

    %% Anwendungs-Pod 2 ----------
    subgraph POD2["Anwendungs-Pod"]
      BW2["BunkerWeb"]:::component
      APP2["Anwendung<br/>(Port XX)"]:::component
      BW2 -->|legitime Anfragen| APP2
    end
    class POD2 podContainer
  end

  %% ---------- Lastenausgleich (unten) ----------
  LB["Lastenausgleich"]:::lb

  %% ---------- Verbindungen (sichtbar, semantisch) ----------
  %% Der Scheduler steuert die BunkerWeb-Instanzen (API)
  SCHED -->|API 5000| BW1
  SCHED -->|API 5000| BW2

  %% Der Load Balancer leitet den Datenverkehr an BunkerWeb weiter
  LB -->|HTTP/HTTPS| BW1
  LB -->|HTTP/HTTPS| BW2

  %% ---------- Layout-Hilfe (versteckt) ----------
  %% Platziere den Load Balancer unter der gesamten PODS-Gruppe
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
  tag: "1.6.7~rc1"
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
  tag: "1.6.7~rc1"
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
          image: bunkerity/bunkerweb:1.6.7-rc1
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

#### Vollständige YAML-Dateien

Anstatt das Helm-Chart zu verwenden, können Sie auch die YAML-Vorlagen im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) des GitHub-Repositorys verwenden. Bitte beachten Sie, dass wir dringend empfehlen, stattdessen das Helm-Chart zu verwenden.

### Ingress-Ressourcen

Sobald der BunkerWeb-Kubernetes-Stack erfolgreich eingerichtet und betriebsbereit ist (weitere Informationen finden Sie in den Autoconf-Protokollen), können Sie mit der Bereitstellung von Webanwendungen im Cluster fortfahren und Ihre Ingress-Ressource deklarieren.

Es ist wichtig zu beachten, dass die BunkerWeb-Einstellungen als Annotationen für die Ingress-Ressource angegeben werden müssen. Für den Domain-Teil verwenden Sie bitte den speziellen Wert **`bunkerweb.io`**. Durch das Einfügen der entsprechenden Annotationen können Sie BunkerWeb entsprechend für die Ingress-Ressource konfigurieren.

!!! tip "Störende Annotationen ignorieren"
    Wenn einige Annotationen autoconf nicht beeinflussen sollen, setzen Sie `KUBERNETES_IGNORE_ANNOTATIONS` auf dem Controller-Deployment. Geben Sie eine durch Leerzeichen oder Kommas getrennte Liste von Annotationsschlüsseln an (zum Beispiel `bunkerweb.io/EXTRA_FOO`) oder nur das Suffix (`EXTRA_FOO`). Übereinstimmende Annotationen werden aus den vom Ingress abgeleiteten Einstellungen entfernt, und Pods, die sie tragen, werden bei der Instanzerkennung vollständig übersprungen.

!!! info "TLS-Unterstützung"
    Der BunkerWeb-Ingress-Controller unterstützt vollständig benutzerdefinierte HTTPS-Zertifikate unter Verwendung der TLS-Spezifikation, wie im Beispiel gezeigt. Die Konfiguration von Lösungen wie `cert-manager` zur automatischen Generierung von TLS-Secrets liegt außerhalb des Geltungsbereichs dieser Dokumentation.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # Wird auf alle Hosts in diesem Ingress angewendet
    bunkerweb.io/MY_SETTING: "value"
    # Wird nur auf den Host www.example.com angewendet
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  # TLS ist optional, Sie können beispielsweise auch das integrierte Let's Encrypt verwenden
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

Ab Version `1.6.0` unterstützen die Autoconf-Stacks von BunkerWeb Namespaces. Mit dieser Funktion können Sie mehrere Cluster von BunkerWeb-Instanzen und -Diensten auf demselben Kubernetes-Cluster verwalten. Um Namespaces zu nutzen, setzen Sie einfach das Metadatenfeld `namespace` auf Ihre BunkerWeb-Instanzen und -Dienste. Hier ist ein Beispiel:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Setzen Sie den Namespace für die BunkerWeb-Instanz
...
```

!!! info "Namespace-Verhalten"

    Standardmäßig lauschen alle Autoconf-Stacks auf alle Namespaces. Wenn Sie einen Stack auf bestimmte Namespaces beschränken möchten, können Sie die Umgebungsvariable `NAMESPACES` im `bunkerweb-controller`-Deployment setzen:

    ```yaml
    ...
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
      namespace: my-namespace # Setzen Sie den Namespace für den Controller
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
              image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
              imagePullPolicy: Always
              env:
                - name: NAMESPACES
                  value: "my-namespace my-other-namespace" # Lauschen Sie nur auf diese Namespaces
                ...
    ...
    ```

    Beachten Sie, dass die Umgebungsvariable `NAMESPACES` eine durch Leerzeichen getrennte Liste von Namespaces ist.

!!! warning "Namespace-Spezifikationen"

    Es kann nur **eine Datenbank** und **ein Scheduler** pro Namespace geben. Wenn Sie versuchen, mehrere Datenbanken oder Scheduler im selben Namespace zu erstellen, kommt es zu Konfigurationskonflikten.

    Der Scheduler benötigt die `NAMESPACE`-Annotation nicht, um ordnungsgemäß zu funktionieren. Er benötigt nur die korrekt konfigurierte Einstellung `DATABASE_URI`, damit er auf dieselbe Datenbank wie der Autoconf-Dienst zugreifen kann.

### Ingress-Klasse

Bei der Installation mit den offiziellen Methoden in der Dokumentation wird BunkerWeb mit der folgenden `IngressClass`-Definition geliefert:

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

Um die vom Ingress-Controller überwachten `Ingress`-Ressourcen einzuschränken, können Sie die Umgebungsvariable `KUBERNETES_INGRESS_CLASS` auf den Wert `bunkerweb` setzen. Dann können Sie die Direktive `ingressClassName` in Ihren `Ingress`-Definitionen nutzen:

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

### Benutzerdefinierter Domainname

Wenn Sie für Ihren Kubernetes-Cluster einen benutzerdefinierten Domainnamen anstelle des standardmäßigen `kubernetes.local` verwenden, können Sie den Wert über die Umgebungsvariable `KUBERNETES_DOMAIN_NAME` auf dem Scheduler-Container festlegen.

### Verwendung mit einem vorhandenen Ingress-Controller

!!! info "Beibehaltung des vorhandenen Ingress-Controllers und von BunkerWeb"

    Dies ist ein Anwendungsfall, bei dem Sie einen vorhandenen Ingress-Controller wie den Nginx-Controller beibehalten möchten. Der typische Datenfluss wird sein: Load Balancer => Ingress Controller => BunkerWeb => Anwendung.

#### Nginx-Ingress-Controller-Installation

Installieren Sie das Nginx-Ingress-Helm-Repo:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

Installieren Sie den Nginx-Ingress-Controller mit Standardwerten (funktioniert möglicherweise nicht auf Ihrem eigenen Cluster sofort, bitte überprüfen Sie die [Dokumentation](https://kubernetes.github.io/ingress-nginx/)):

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

Extrahieren Sie die IP-Adresse des LB:

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Richten Sie DNS-Einträge auf die IP-Adresse des LB ein (z. B. `bunkerweb`-Subdomain für die BW-UI und `myapp` für die Anwendung):

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

**BunkerWeb-Installation**

Installieren Sie das BunkerWeb-Helm-Repo:

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

Erstellen Sie die Datei `values.yaml`:

```yaml
# Hier richten wir die Werte ein, die für die Einrichtung von BunkerWeb hinter einem vorhandenen Ingress-Controller erforderlich sind
# Datenfluss mit BW: LB => vorhandener Ingress Controller => BunkerWeb => Dienst
# Datenfluss ohne BW: LB => vorhandener Ingress Controller => Dienst

# Globale Einstellungen
settings:
  misc:
    # Ersetzen Sie dies durch Ihren DNS-Resolver
    # um ihn zu erhalten: kubectl exec in einem zufälligen Pod, dann cat /etc/resolv.conf
    # wenn Sie eine IP als Nameserver haben, führen Sie eine umgekehrte DNS-Suche durch: nslookup <IP>
    # meistens ist es coredns.kube-system.svc.cluster.local oder kube-dns.kube-system.svc.cluster.local
    dnsResolvers: "kube-dns.kube-system.svc.cluster.local"
  kubernetes:
    # Wir berücksichtigen nur Ingress-Ressourcen mit ingressClass bunkerweb, um Konflikte mit dem vorhandenen Ingress-Controller zu vermeiden
    ingressClass: "bunkerweb"
    # Optional: Sie können Namespace(s) auswählen, in denen BunkerWeb auf Ingress/ConfigMap-Änderungen lauschen wird
    # Standard (leerer Wert) sind alle Namespaces
    namespaces: ""

# Überschreiben Sie den Diensttyp bunkerweb-external auf ClusterIP
# Da wir ihn nicht nach außen verfügbar machen müssen
# Wir werden den vorhandenen Ingress-Controller verwenden, um den Datenverkehr an BunkerWeb weiterzuleiten
service:
  type: ClusterIP

# BunkerWeb-Einstellungen
bunkerweb:
  tag: 1.6.7~rc1

# Scheduler-Einstellungen
scheduler:
  tag: 1.6.7~rc1
  extraEnvs:
    # Aktivieren Sie das Real-IP-Modul, um die echte IP der Clients zu erhalten
    - name: USE_REAL_IP
      value: "yes"

# Controller-Einstellungen
controller:
  tag: 1.6.7~rc1

# UI-Einstellungen
ui:
  tag: 1.6.7~rc1
```

Installieren Sie BunkerWeb mit benutzerdefinierten Werten:

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

Überprüfen Sie die Protokolle und warten Sie, bis alles bereit ist.

**Web-UI-Installation**

Richten Sie den folgenden Ingress ein (vorausgesetzt, der Nginx-Controller ist installiert):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ui-bunkerweb
  # Ersetzen Sie dies bei Bedarf durch Ihren Namespace von BW
  namespace: bunkerweb
  annotations:
    # HTTPS ist für die Web-UI obligatorisch, auch wenn der Datenverkehr intern ist
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    # Wir müssen SNI setzen, damit BW den richtigen vhost bedienen kann
    # Ersetzen Sie dies durch Ihre Domain
    nginx.ingress.kubernetes.io/proxy-ssl-name: "bunkerweb.example.com"
    nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"
spec:
  # Wird nur vom Nginx-Controller und nicht von BW bedient
  ingressClassName: nginx
  # Entkommentieren und bearbeiten, wenn Sie Ihr eigenes Zertifikat verwenden möchten
  # tls:
  # - hosts:
  #   - bunkerweb.example.com
  #   secretName: tls-secret
  rules:
  # Ersetzen Sie dies durch Ihre Domain
  - host: bunkerweb.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Erstellt vom Helm-Chart
            name: bunkerweb-external
            port:
              # Die Verwendung des HTTPS-Ports ist für die UI obligatorisch
              number: 443
```

Und Sie können nun zum Einrichtungsassistenten gehen, indem Sie zu `https://bunkerweb.example.com/setup` navigieren.

**Schutz einer bestehenden Anwendung**

**Zuerst müssen Sie zu den Globalen Einstellungen gehen, das SSL-Plugin auswählen und dann die automatische Weiterleitung von HTTP zu HTTPS deaktivieren. Bitte beachten Sie, dass Sie dies nur einmal tun müssen.**

Nehmen wir an, Sie haben eine Anwendung im Namespace `myapp`, die über den Dienst `myapp-service` auf Port `5000` zugänglich ist.

Sie müssen einen neuen Dienst in der Web-UI hinzufügen und die erforderlichen Informationen ausfüllen:

- Servername: die öffentlich zugängliche Domain Ihrer Anwendung (z. B. `myapp.example.com`)
- SSL/TLS: Ihr Ingress-Controller kümmert sich um diesen Teil, also aktivieren Sie es nicht auf BunkerWeb, da der Datenverkehr innerhalb des Clusters intern ist
- Reverse-Proxy-Host: die vollständige URL Ihrer Anwendung innerhalb des Clusters (z. B. `http://myapp-service.myapp.svc.cluster.local:5000`)

Sobald der neue Dienst hinzugefügt wurde, können Sie nun eine Ingress-Ressource für diesen Dienst deklarieren und ihn an den BunkerWeb-Dienst auf dem HTTP-Port weiterleiten:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  # Ersetzen Sie dies bei Bedarf durch Ihren Namespace von BW
  namespace: bunkerweb
spec:
  # Wird nur vom Nginx-Controller und nicht von BW bedient
  ingressClassName: nginx
  # Entkommentieren und bearbeiten, wenn Sie Ihr eigenes Zertifikat verwenden möchten
  # tls:
  # - hosts:
  #   - myapp.example.com
  #   secretName: tls-secret
  rules:
  # Ersetzen Sie dies durch Ihre Domain
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Erstellt vom Helm-Chart
            name: bunkerweb-external
            port:
              number: 80
```

Sie können `http(s)://myapp.example.com` besuchen, das jetzt mit BunkerWeb geschützt ist 🛡️

## Swarm

<figure markdown>
  ![Übersicht](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Docker Swarm-Integration</figcaption>
</figure>

!!! warning "Veraltet"
    Die Swarm-Integration ist veraltet und wird in einer zukünftigen Version entfernt. Bitte erwägen Sie stattdessen die Verwendung der [Kubernetes-Integration](#kubernetes).

!!! tip "PRO-Unterstützung"
    **Wenn Sie Swarm-Unterstützung benötigen**, kontaktieren Sie uns bitte unter [contact@bunkerity.com](mailto:contact@bunkerity.com) oder über das [Kontaktformular](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Docker Autoconf"
    Die Swarm-Integration ähnelt der Docker Autoconf-Integration (jedoch mit Diensten anstelle von Containern). Bitte lesen Sie bei Bedarf zuerst den [Docker Autoconf-Integrationsabschnitt](#docker-autoconf).

Um die automatische Konfiguration von BunkerWeb-Instanzen zu ermöglichen, benötigt der **autoconf**-Dienst Zugriff auf die Docker-API. Dieser Dienst lauscht auf Docker Swarm-Ereignisse wie die Erstellung oder Löschung von Diensten und konfiguriert die **BunkerWeb-Instanzen** nahtlos in Echtzeit ohne Ausfallzeiten. Er überwacht auch andere Swarm-Objekte wie [Konfigurationen](https://docs.docker.com/engine/swarm/configs/) für benutzerdefinierte Konfigurationen.

Ähnlich wie bei der [Docker Autoconf-Integration](#docker-autoconf) wird die Konfiguration für Webdienste über Labels definiert, die mit dem Präfix **bunkerweb** beginnen.

Für eine optimale Einrichtung wird empfohlen, den **BunkerWeb-Dienst** als ***globalen Dienst*** auf allen Knoten zu planen, während die **autoconf-, Scheduler- und Docker-API-Proxy-Dienste** als ***einzeln replizierte Dienste*** geplant werden sollten. Bitte beachten Sie, dass der Docker-API-Proxy-Dienst auf einem Manager-Knoten geplant werden muss, es sei denn, Sie konfigurieren ihn für die Verwendung einer Remote-API (was in der Dokumentation nicht behandelt wird).

Da mehrere Instanzen von BunkerWeb ausgeführt werden, muss ein gemeinsamer Datenspeicher implementiert als [Redis](https://redis.io/)- oder [Valkey](https://valkey.io/)-Dienst erstellt werden. Diese Instanzen nutzen den Redis/Valkey-Dienst, um Daten zu cachen und zu teilen. Weitere Details zu den Redis/Valkey-Einstellungen finden Sie [hier](features.md#redis).

Was das Datenbank-Volume betrifft, so gibt die Dokumentation keinen spezifischen Ansatz vor. Die Wahl eines freigegebenen Ordners oder eines bestimmten Treibers für das Datenbank-Volume hängt von Ihrem einzigartigen Anwendungsfall ab und bleibt dem Leser als Übung überlassen.

!!! info "Datenbank-Backend"
    Bitte beachten Sie, dass unsere Anweisungen davon ausgehen, dass Sie MariaDB als Standard-Datenbank-Backend verwenden, wie durch die Einstellung `DATABASE_URI` konfiguriert. Wir verstehen jedoch, dass Sie möglicherweise alternative Backends für Ihre Docker-Integration bevorzugen. In diesem Fall können Sie sicher sein, dass auch andere Datenbank-Backends möglich sind. Weitere Informationen finden Sie in den docker-compose-Dateien im Ordner [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) des Repositorys.

    Die Einrichtung von geclusterten Datenbank-Backends liegt außerhalb des Geltungsbereichs dieser Dokumentation.

Hier ist die Stack-Vorlage, die Sie mit `docker stack deploy` bereitstellen können:

```yaml
x-bw-env: &bw-env
  # Wir verwenden einen Anker, um die Wiederholung derselben Einstellungen für beide Dienste zu vermeiden
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.7-rc1
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
        - "bunkerweb.INSTANCE=yes" # Obligatorisches Label für den Autoconf-Dienst, um die BunkerWeb-Instanz zu identifizieren

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # Wir müssen die BunkerWeb-Instanz hier nicht angeben, da sie automatisch vom Autoconf-Dienst erkannt werden
      SERVER_NAME: "" # Der Servername wird mit Dienst-Labels gefüllt
      MULTISITE: "yes" # Obligatorische Einstellung für Autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-storage:/data # Wird verwendet, um den Cache und andere Daten wie Backups zu persistieren
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
    environment:
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
      DOCKER_HOST: "tcp://bw-docker:2375" # Der Docker-Socket
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
    # Wir setzen die maximal zulässige Paketgröße, um Probleme mit großen Abfragen zu vermeiden
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Denken Sie daran, ein stärkeres Passwort für die Datenbank festzulegen
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

!!! info "Obligatorische Swarm-Einstellung"
    Bitte beachten Sie, dass die Umgebungsvariable `SWARM_MODE: "yes"` bei Verwendung der Swarm-Integration obligatorisch ist.

!!! tip "Beschriftete Dienste überspringen"
    Müssen Sie einen Swarm-Dienst von autoconf ausschließen? Setzen Sie `SWARM_IGNORE_LABELS` auf dem Controller. Geben Sie eine durch Leerzeichen oder Kommas getrennte Liste von Label-Schlüsseln an (z.B. `bunkerweb.SERVER_NAME`) oder Suffixen (`SERVER_NAME`), und jeder Dienst mit diesen Labels wird bei der Erkennung ignoriert.

### Swarm-Dienste

Sobald der BunkerWeb-Swarm-Stack eingerichtet ist und läuft (weitere Informationen finden Sie in den Autoconf- und Scheduler-Protokollen), können Sie Webanwendungen im Cluster bereitstellen und Labels verwenden, um BunkerWeb dynamisch zu konfigurieren:

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

Ab Version `1.6.0` unterstützen die Autoconf-Stacks von BunkerWeb Namespaces. Mit dieser Funktion können Sie mehrere "*Cluster*" von BunkerWeb-Instanzen und -Diensten auf demselben Docker-Host verwalten. Um Namespaces zu nutzen, setzen Sie einfach das `NAMESPACE`-Label auf Ihre Dienste. Hier ist ein Beispiel:

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
        - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für den Dienst
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Namespace-Verhalten"

    Standardmäßig lauschen alle Autoconf-Stacks auf alle Namespaces. Wenn Sie einen Stack auf bestimmte Namespaces beschränken möchten, können Sie die Umgebungsvariable `NAMESPACES` im `bw-autoconf`-Dienst setzen:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        ...
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"
            - "bunkerweb.NAMESPACE=my-namespace" # Setzen Sie den Namespace für die BunkerWeb-Instanz
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
        environment:
          NAMESPACES: "my-namespace my-other-namespace" # Lauschen Sie nur auf diese Namespaces
          ...
        deploy:
          placement:
            constraints:
              - "node.role == worker"
    ...
    ```

    Beachten Sie, dass die Umgebungsvariable `NAMESPACES` eine durch Leerzeichen getrennte Liste von Namespaces ist.

!!! warning "Namespace-Spezifikationen"

    Es kann nur **eine Datenbank** und **ein Scheduler** pro Namespace geben. Wenn Sie versuchen, mehrere Datenbanken oder Scheduler im selben Namespace zu erstellen, kommt es zu Konfigurationskonflikten.

    Der Scheduler benötigt das `NAMESPACE`-Label nicht, um ordnungsgemäß zu funktionieren. Er benötigt nur die korrekt konfigurierte Einstellung `DATABASE_URI`, damit er auf dieselbe Datenbank wie der Autoconf-Dienst zugreifen kann.

## Terraform

### Einführung

Der Terraform-Provider für BunkerWeb ermöglicht es Ihnen, Ihre BunkerWeb-Instanzen, -Dienste und -Konfigurationen über Infrastructure as Code (IaC) zu verwalten. Dieser Provider interagiert mit der BunkerWeb-API, um die Bereitstellung und Verwaltung Ihrer Sicherheitskonfigurationen zu automatisieren.

### Voraussetzungen

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.12
- Eine BunkerWeb-Instanz mit aktivierter API
- Ein API-Token oder Basic-Authentication-Anmeldedaten

### Installation

Der Provider ist im [Terraform Registry](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest) verfügbar. Fügen Sie ihn zu Ihrer Terraform-Konfiguration hinzu:

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

### Konfiguration

#### Bearer-Token-Authentifizierung (empfohlen)

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_token    = var.bunkerweb_token
}
```

#### Basis-Authentifizierung

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_username = var.bunkerweb_username
  api_password = var.bunkerweb_password
}
```

### Verwendungsbeispiele

#### Einen Webdienst erstellen

```terraform
resource "bunkerweb_service" "app" {
  server_name = "app.example.com"

  variables = {
    upstream = "10.0.0.12:8080"
    mode     = "production"
  }
}
```

#### Eine Instanz registrieren

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

#### Eine globale Einstellung konfigurieren

```terraform
resource "bunkerweb_global_config_setting" "retry" {
  key   = "retry_limit"
  value = "10"
}
```

#### Eine IP-Adresse sperren

```terraform
resource "bunkerweb_ban" "suspicious_ip" {
  ip       = "192.0.2.100"
  reason   = "Multiple failed login attempts"
  duration = 3600  # 1 Stunde in Sekunden
}
```

#### Benutzerdefinierte Konfiguration

```terraform
resource "bunkerweb_config" "custom_rules" {
  service_id = "app.example.com"
  type       = "http"
  name       = "custom-rules.conf"
  content    = file("${path.module}/configs/custom-rules.conf")
}
```

### Verfügbare Ressourcen

Der Provider stellt die folgenden Ressourcen bereit:

- **bunkerweb_service**: Webdienst-Verwaltung
- **bunkerweb_instance**: Instanz-Registrierung und -Verwaltung
- **bunkerweb_global_config_setting**: Globale Konfiguration
- **bunkerweb_config**: Benutzerdefinierte Konfigurationen
- **bunkerweb_ban**: IP-Sperrverwaltung
- **bunkerweb_plugin**: Plugin-Installation und -Verwaltung

### Datenquellen

Datenquellen ermöglichen das Lesen vorhandener Informationen:

- **bunkerweb_service**: Einen vorhandenen Dienst lesen
- **bunkerweb_global_config**: Globale Konfiguration lesen
- **bunkerweb_plugins**: Verfügbare Plugins auflisten
- **bunkerweb_cache**: Cache-Informationen
- **bunkerweb_jobs**: Status geplanter Jobs

### Ephemere Ressourcen

Für einmalige Operationen:

- **bunkerweb_run_jobs**: Jobs bei Bedarf auslösen
- **bunkerweb_instance_action**: Aktionen auf Instanzen ausführen (reload, stop, etc.)
- **bunkerweb_service_snapshot**: Dienstzustand erfassen
- **bunkerweb_config_upload**: Massen-Konfiguration hochladen

### Vollständiges Beispiel

Hier ist ein Beispiel einer vollständigen Infrastruktur mit BunkerWeb:

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

# Globale Konfiguration
resource "bunkerweb_global_config_setting" "rate_limit" {
  key   = "rate_limit"
  value = "10r/s"
}

# Hauptdienst
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

# API-Dienst mit unterschiedlicher Konfiguration
resource "bunkerweb_service" "api" {
  server_name = "api.example.com"

  variables = {
    upstream        = "10.0.1.20:3000"
    mode            = "production"
    use_cors        = "yes"
    cors_allow_origin = "*"
  }
}

# Worker-Instanz
resource "bunkerweb_instance" "worker1" {
  hostname     = "bw-worker-1.internal"
  name         = "Production Worker 1"
  port         = 8080
  listen_https = true
  https_port   = 8443
  server_name  = "bw-worker-1.internal"
  method       = "api"
}

# Benutzerdefinierte Konfiguration für webapp-Dienst
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

# Eine verdächtige IP sperren
resource "bunkerweb_ban" "blocked_ip" {
  ip       = "203.0.113.50"
  reason   = "Detected malicious activity"
  duration = 86400  # 24 Stunden
}

output "webapp_service_id" {
  value = bunkerweb_service.webapp.id
}

output "api_service_id" {
  value = bunkerweb_service.api.id
}
```

### Zusätzliche Ressourcen

- [Vollständige Provider-Dokumentation](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest/docs)
- [GitHub-Repository](https://github.com/bunkerity/terraform-provider-bunkerweb)
- [Verwendungsbeispiele](https://github.com/bunkerity/terraform-provider-bunkerweb/tree/main/examples)
- [BunkerWeb-API-Dokumentation](https://docs.bunkerweb.io/latest/api/)

### Support und Beiträge

Um Fehler zu melden oder Verbesserungen vorzuschlagen, besuchen Sie das [GitHub-Repository des Providers](https://github.com/bunkerity/terraform-provider-bunkerweb/issues).


## Microsoft Azure

<figure markdown>
  ![Übersicht](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Azure-Integration</figcaption>
</figure>

!!! info "Empfohlene VM-Größe"
    Bitte beachten Sie bei der Wahl der VM-SKU. Sie müssen eine SKU auswählen, die mit Gen2-VMs kompatibel ist, und wir empfehlen, mit der B2s- oder Ds2-Serie für eine optimale Nutzung zu beginnen.

Sie können BunkerWeb auf verschiedene Weisen einfach in Ihrem Azure-Abonnement bereitstellen:

- Azure CLI in der Cloud Shell
- Azure ARM-Vorlage
- Azure-Portal über den Marketplace

=== "Cloud Shell"

    Erstellen Sie eine Ressourcengruppe. Ersetzen Sie den Wert `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    Erstellen Sie eine VM mit der SKU `Standard_B2s` am Standort der Ressourcengruppe. Ersetzen Sie die Werte `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    Vollständiger Befehl. Ersetzen Sie die Werte `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "ARM-Vorlage"

    !!! info "Berechtigungsanforderung"
        Um eine ARM-Vorlage bereitzustellen, benötigen Sie Schreibzugriff auf die Ressourcen, die Sie bereitstellen, und Zugriff auf alle Operationen auf dem Ressourcentyp Microsoft.Resources/deployments.
        Um eine virtuelle Maschine bereitzustellen, benötigen Sie die Berechtigungen Microsoft.Compute/virtualMachines/write und Microsoft.Resources/deployments/*. Die What-if-Operation hat dieselben Berechtigungsanforderungen.

    Stellen Sie die ARM-Vorlage bereit:

    [![Bereitstellen in Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    Melden Sie sich im [Azure-Portal](https://portal.azure.com){:target="_blank"} an.

    Holen Sie sich BunkerWeb über das Menü [Ressource erstellen](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}.

    Sie können auch über den [Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"} gehen.

Sie können auf den Einrichtungsassistenten zugreifen, indem Sie die URI `https://ihre-ip-adresse/setup` Ihrer virtuellen Maschine aufrufen.
