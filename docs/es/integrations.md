# Integraciones

## BunkerWeb Cloud

<figure markdown>
  ![Descripción general](assets/img/bunkerweb-cloud.png){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

BunkerWeb Cloud es una solución gestionada de Web Application Firewall (WAF) y proxy inverso que te permite asegurar tus aplicaciones web sin instalar BunkerWeb en tu infraestructura. Al suscribirte a BunkerWeb Cloud, te beneficias de una pila completa de BunkerWeb alojada en la nube con recursos dedicados (8 GB de RAM, 2 CPU **por** instancia, replicada en 2 instancias para alta disponibilidad, oferta Estándar).

### Beneficios clave

Pide tu [instancia de BunkerWeb Cloud](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) y obtén acceso a:

- **Despliegue instantáneo**: No requiere instalación en tu infraestructura
- **Alta disponibilidad**: Instancias replicadas con balanceo de carga automático
- **Monitorización integrada**: Acceso a Grafana para visualización de registros y métricas
- **Escalabilidad**: Recursos dedicados adaptados a grandes cargas de trabajo
- **Seguridad mejorada**: Protección WAF en tiempo real contra amenazas web

Si estás interesado en la oferta de BunkerWeb Cloud, no dudes en [contactarnos](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) para que podamos discutir tus necesidades.

### Visión general de la arquitectura

#### Arquitectura simple - Servicio único

```mermaid
graph LR
    A[Cliente] -->|HTTPS| B[ejemplo.com]
    B -->|Resolución DNS| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Tráfico| D[BunkerWeb CloudWAF + Reverse Proxy]
    D -->|HTTPS/HTTP| E[Servidor ejemplo.comInfraestructura Cliente]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#e8f5e8,color:#222
```

#### Arquitectura compleja - Múltiples servicios

```mermaid
graph LR
    A[Clientes] -->|HTTPS| B[ejemplo.comotro-ejemplo.comun-otro-ejemplo.com]
    B -->|Resolución DNS| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Tráfico| D[BunkerWeb CloudWAF + Reverse ProxySSL SNI Habilitado]
    D -->|HTTPS con SNI| E[Gateway ClienteReverse Proxy/LB]
    E -->|Enrutamiento interno| F[Servicio 1]
    E -->|Enrutamiento interno| G[Servicio 2]
    E -->|Enrutamiento interno| H[Servicio N]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#fff3e0,color:#222
    style F fill:#e8f5e8,color:#222
    style G fill:#e8f5e8,color:#222
    style H fill:#e8f5e8,color:#222
```

### Configuración inicial

#### 1. Acceso a la interfaz de gestión

Después de suscribirte a BunkerWeb Cloud, recibirás:

- **URL de acceso a la IU de BunkerWeb**: Interfaz para configurar tus servicios
- **Punto final del Load Balancer**: URL única en el formato `http://[ID].bunkerweb.cloud`
- **Acceso a Grafana**: Interfaz de monitorización y visualización de métricas
- **Recursos asignados**: 2 instancias con 8 GB de RAM y 2 CPU cada una

#### 2. Primera conexión

1. Conéctate a la interfaz de BunkerWeb Cloud
2. Configura tus servicios a proteger
3. Accede a Grafana para visualizar tus registros y métricas de BunkerWeb

### Configuración DNS

#### Redirección de tráfico a BunkerWeb Cloud

Para que el tráfico de tu dominio sea procesado por BunkerWeb Cloud, debes configurar tus registros DNS:

**Configuración requerida:**

```dns
ejemplo.com.        IN  CNAME  54984654.bunkerweb.cloud.
www.ejemplo.com.    IN  CNAME  54984654.bunkerweb.cloud.
```

**Importante:** Reemplaza `54984654` con tu identificador de load balancer proporcionado durante la suscripción.

#### Validación de la configuración

Verifica la resolución DNS:

```bash
dig ejemplo.com
nslookup ejemplo.com
```

El resultado debería apuntar a tu punto final de BunkerWeb Cloud.

### Configuración del servicio

#### Servicio único

Para un servicio simple alojado en tu infraestructura:

**Configuración en la IU de BunkerWeb:**

1. **Server Name**: `ejemplo.com`
2. **Use Reverse Proxy**: `yes`
3. **Reverse Proxy Host**: `185.87.1.100:443` (IP de tu servidor)

Puedes encontrar todas las opciones de configuración en la [Documentación de Reverse Proxy](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

#### Múltiples servicios con SNI

##### ¿Por qué habilitar SNI?

Server Name Indication (SNI) es **esencial** cuando:

- Múltiples dominios apuntan a la misma infraestructura backend
- Tu infraestructura aloja múltiples servicios con certificados SSL distintos
- Usas un proxy inverso/gateway en el lado del cliente

##### Configuración SNI

**En la IU de BunkerWeb, para cada servicio:**

```yaml
# Servicio 1
SERVICE_NAME: ejemplo-com
SERVER_NAME: ejemplo.com
REVERSE_PROXY_HOST: https://gateway.interno.dominio.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: ejemplo.com

# Servicio 2
SERVICE_NAME: otro-ejemplo-com
SERVER_NAME: otro-ejemplo.com
REVERSE_PROXY_HOST: https://gateway.interno.dominio.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: otro-ejemplo.com
```

Puedes encontrar todas las opciones de configuración en la [Documentación de Reverse Proxy](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

##### Detalles técnicos de SNI

SNI permite a BunkerWeb Cloud:

1. **Identificar el servicio objetivo** durante la conexión TLS
2. **Transmitir el nombre de dominio correcto** al backend
3. **Permitir al gateway cliente** seleccionar el certificado correcto
4. **Enrutar correctamente** al servicio apropiado

**Sin SNI habilitado:**

```mermaid
graph LR
    A[Cliente] --> B[BunkerWeb]
    B --> C["Gateway (certificado por defecto)"]
    C --> D[Error SSL]

    style B fill:#f3e5f5,color:#222
    style C fill:#fff3e0,color:#222
    style D fill:#ff4d4d,color:#fff,stroke:#b30000,stroke-width:2px
```

**Con SNI habilitado:**

```mermaid
graph LR
    A[Cliente] --> B[BunkerWeb]
    B --> C["Gateway (certificado específico ejemplo.com)"]
    C --> D[Servicio Correcto]

    style B fill:#f3e5f5,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
```

### Gestión SSL/TLS y SNI

#### Certificados SSL

##### Lado de BunkerWeb Cloud

BunkerWeb Cloud gestiona automáticamente:

- Certificados Let's Encrypt para tus dominios
- Renovación automática
- Configuración TLS optimizada

##### Lado de la Infraestructura Cliente

**Recomendaciones importantes:**

1. **Usa HTTPS** para la comunicación entre BunkerWeb y tus servicios
2. **Gestiona tus propios certificados** en tu infraestructura
3. **Configura correctamente SNI** en tu gateway/proxy inverso

#### Configuración SNI detallada

##### Caso de uso: Infraestructura con Gateway

Si tu arquitectura se ve así:

```mermaid
graph LR
    A[BunkerWeb Cloud] --> B[Gateway Cliente]
    B --> C[Servicio 1]
    B --> D[Servicio 2]
    B --> E[Servicio 3]

    style A fill:#f3e5f5,color:#222
    style B fill:#fff3e0,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
    style E fill:#e8f5e8,color:#222
```

**Configuración requerida en el lado de BunkerWeb:**

```yaml
# Configuración para ejemplo.com
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: ejemplo.com
REVERSE_PROXY_SSL_VERIFY: no  # Si el certificado es autofirmado en el lado del cliente
REVERSE_PROXY_HEADERS: Host $host

# Configuración para api.ejemplo.com
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: api.ejemplo.com
REVERSE_PROXY_SSL_VERIFY: no
REVERSE_PROXY_HEADERS: Host $host
```

### Configuración Gateway Cliente

#### Visión general

Cuando tu arquitectura utiliza un gateway/proxy inverso en el lado del cliente para enrutar el tráfico a múltiples servicios, se necesita una configuración específica para soportar SNI y asegurar una comunicación segura con BunkerWeb Cloud.

#### Configuraciones por tecnología

##### Nginx

<details>
<summary>Configuración Nginx</summary>

```nginx
# Configuración para soportar SNI con múltiples servicios
server {
    listen 443 ssl http2;
    server_name ejemplo.com;

    ssl_certificate /path/to/ejemplo.com.crt;
    ssl_certificate_key /path/to/ejemplo.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Cabeceras de seguridad
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
    server_name api.ejemplo.com;

    ssl_certificate /path/to/api.ejemplo.com.crt;
    ssl_certificate_key /path/to/api.ejemplo.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://api-service:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Configuración específica de API
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

</details>

##### Traefik

<details>
<summary>Configuración Traefik</summary>

**Con Docker Compose:**

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
      - --certificatesresolvers.myresolver.acme.email=admin@ejemplo.com
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
      - "traefik.http.routers.dashboard.rule=Host(`traefik.ejemplo.com`)"
      - "traefik.http.routers.dashboard.tls.certresolver=myresolver"

  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`ejemplo.com`)"
      - "traefik.http.routers.service1.entrypoints=websecure"
      - "traefik.http.routers.service1.tls.certresolver=myresolver"
      - "traefik.http.services.service1.loadbalancer.server.port=8080"
      - "traefik.http.routers.service1.middlewares=security-headers"

  api-service:
    image: your-api:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.ejemplo.com`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=myresolver"
      - "traefik.http.services.api.loadbalancer.server.port=3000"
      - "traefik.http.routers.api.middlewares=security-headers,rate-limit"
```

**Configuración dinámica (dynamic.yml):**

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
      rule: "Host(`ejemplo.com`)"
      service: "service1"
      tls:
        certResolver: "myresolver"
      middlewares:
        - "security-headers"

    api:
      rule: "Host(`api.ejemplo.com`)"
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
<summary>Configuración Apache</summary>

```apache
# Configuración Apache con SNI
<VirtualHost *:443>
    ServerName ejemplo.com
    DocumentRoot /var/www/html

    # Configuración SSL
    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLHonorCipherOrder off
    SSLCertificateFile /path/to/ejemplo.com.crt
    SSLCertificateKeyFile /path/to/ejemplo.com.key

    # Cabeceras de seguridad
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # Configuración reverse proxy
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Cabeceras personalizadas
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    <Proxy *>
        Require all granted
    </Proxy>

    # Registros
    ErrorLog ${APACHE_LOG_DIR}/ejemplo.com_error.log
    CustomLog ${APACHE_LOG_DIR}/ejemplo.com_access.log combined
</VirtualHost>

<VirtualHost *:443>
    ServerName api.ejemplo.com

    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLCertificateFile /path/to/api.ejemplo.com.crt
    SSLCertificateKeyFile /path/to/api.ejemplo.com.key

    ProxyPass / http://api-service:3000/
    ProxyPassReverse / http://api-service:3000/
    ProxyPreserveHost On

    # Configuración específica de API
    ProxyTimeout 300
    ProxyBadHeader Ignore

    ErrorLog ${APACHE_LOG_DIR}/api.ejemplo.com_error.log
    CustomLog ${APACHE_LOG_DIR}/api.ejemplo.com_access.log combined
</VirtualHost>

# Configuración de módulos requeridos
LoadModule ssl_module modules/mod_ssl.so
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
LoadModule headers_module modules/mod_headers.so
```

</details>

##### HAProxy

<details>
<summary>Configuración HAProxy</summary>

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

    # Configuración SSL
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
    bind *:443 ssl crt /etc/ssl/certs/ejemplo.com.pem crt /etc/ssl/certs/api.ejemplo.com.pem

    # Cabeceras de seguridad
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff
    http-response set-header X-XSS-Protection "1; mode=block"
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # Enrutamiento basado en SNI
    acl is_ejemplo hdr(host) -i ejemplo.com
    acl is_api hdr(host) -i api.ejemplo.com

    use_backend service1_backend if is_ejemplo
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

# Interfaz de estadísticas (opcional)
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE
```

</details>

#### Validación de la configuración SSL

Probar la configuración SSL:

```bash
# Prueba de conectividad SSL
openssl s_client -connect tu-dominio.com:443 -servername tu-dominio.com

# Verificación de cabeceras
curl -I https://tu-dominio.com

# Prueba SNI
curl -H "Host: ejemplo.com" https://54984654.bunkerweb.cloud
```

#### Mejores prácticas para Gateways

1. **Health Checks**: Configura comprobaciones de salud para tus servicios
2. **Load Balancing**: Usa múltiples instancias para alta disponibilidad
3. **Monitorización**: Monitoriza las métricas de tu gateway
4. **Cabeceras de seguridad**: Añade cabeceras de seguridad apropiadas
5. **Timeouts**: Configura timeouts apropiados para evitar bloqueos

### Lista blanca de IP de BunkerWeb Cloud

#### ¿Por qué configurar una lista blanca?

Para asegurar aún más tu infraestructura, se recomienda configurar una lista blanca de direcciones IP de BunkerWeb Cloud en el lado de la infraestructura del cliente. Esto asegura que solo el tráfico de BunkerWeb Cloud pueda llegar a tus servicios backend.

Recomendamos el uso de listas blancas a nivel de firewall (iptables, etc.).

#### Direcciones IP de BunkerWeb Cloud para poner en lista blanca

**Lista de direcciones IP a permitir:**

La lista actualizada está disponible aquí: https://repo.bunkerweb.io/cloud/ips

```
# Direcciones IP de BunkerWeb Cloud
4.233.128.18
20.19.161.132
```

#### Configuración de lista blanca por tecnología

##### Nginx

<details>
<summary>Configuración Nginx</summary>

```nginx
# En tu configuración de servidor
server {
    listen 443 ssl;
    server_name ejemplo.com;

    # Lista blanca de IP de BunkerWeb Cloud
    allow 192.168.1.0/24;
    allow 10.0.0.0/16;
    allow 172.16.0.0/12;
    deny all;

    ssl_certificate /path/to/ejemplo.com.crt;
    ssl_certificate_key /path/to/ejemplo.com.key;

    location / {
        proxy_pass http://service1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# Configuración con módulo geo para más flexibilidad
geo $bunkerweb_ip {
    default 0;
    192.168.1.0/24 1;
    10.0.0.0/16 1;
    172.16.0.0/12 1;
}

server {
    listen 443 ssl;
    server_name ejemplo.com;

    if ($bunkerweb_ip = 0) {
        return 403;
    }

    # ... resto de la configuración
}
```

</details>

##### Traefik

<details>
<summary>Configuración Traefik</summary>

```yaml
# Configuración en dynamic.yml
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
    ejemplo-router:
      rule: "Host(`ejemplo.com`)"
      service: "ejemplo-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"

    api-router:
      rule: "Host(`api.ejemplo.com`)"
      service: "api-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"
```

**Con etiquetas de Docker Compose:**

```yaml
services:
  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`ejemplo.com`)"
      - "traefik.http.routers.service1.middlewares=bunkerweb-whitelist"
      - "traefik.http.middlewares.bunkerweb-whitelist.ipwhitelist.sourcerange=192.168.1.0/24,10.0.0.0/16,172.16.0.0/12"
```

</details>

##### Apache

<details>
<summary>Configuración Apache</summary>

```apache
<VirtualHost *:443>
    ServerName ejemplo.com

    # Lista blanca de IP de BunkerWeb Cloud
    <RequireAll>
        Require ip 192.168.1.0/24
        Require ip 10.0.0.0/16
        Require ip 172.16.0.0/12
    </RequireAll>

    SSLEngine on
    SSLCertificateFile /path/to/ejemplo.com.crt
    SSLCertificateKeyFile /path/to/ejemplo.com.key

    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Configuración para registros de acceso denegado
    LogFormat "%h %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined
    CustomLog logs/access.log combined
    ErrorLog logs/error.log
</VirtualHost>

# Configuración alternativa con mod_authz_core
<VirtualHost *:443>
    ServerName api.ejemplo.com

    <Directory />
        <RequireAny>
            Require ip 192.168.1.0/24
            Require ip 10.0.0.0/16
            Require ip 172.16.0.0/12
        </RequireAny>
    </Directory>

    # ... resto de la configuración
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>Configuración HAProxy</summary>

```haproxy
# Configuración en haproxy.cfg
frontend bunkerweb_frontend
    bind *:443 ssl crt /path/to/certificados/

    # ACL para la lista blanca de BunkerWeb Cloud
    acl bunkerweb_ips src 192.168.1.0/24 10.0.0.0/16 172.16.0.0/12

    # Bloquear todo excepto BunkerWeb Cloud
    http-request deny unless bunkerweb_ips

    # Cabeceras de seguridad
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff

    # Enrutamiento
    acl is_ejemplo hdr(host) -i ejemplo.com
    acl is_api hdr(host) -i api.ejemplo.com

    use_backend app_servers if is_ejemplo
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

##### Firewall del sistema (iptables)

<details>
<summary>Configuración iptables</summary>

```bash
#!/bin/bash
# Script de configuración de iptables para la lista blanca de BunkerWeb Cloud

# Limpiar reglas existentes
iptables -F
iptables -X

# Políticas por defecto
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Permitir loopback
iptables -A INPUT -i lo -j ACCEPT

# Permitir conexiones establecidas
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Lista blanca de IPs de BunkerWeb Cloud para HTTPS
iptables -A INPUT -p tcp --dport 443 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 10.0.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 172.16.0.0/12 -j ACCEPT

# Permitir HTTP para Let's Encrypt (opcional)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# Permitir SSH (adaptar a tus necesidades)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Registros para depuración
iptables -A INPUT -j LOG --log-prefix "DROPPED: "

# Guardar reglas
iptables-save > /etc/iptables/rules.v4

echo "Configuración de iptables aplicada con éxito"
```

</details>

#### Mejores prácticas de lista blanca

1. **Monitorizar rechazos**: Monitoriza los intentos de acceso bloqueados
2. **Actualizaciones regulares**: Mantén la lista de IP actualizada
3. **Pruebas regulares**: Valida que la lista blanca funciona correctamente
4. **Documentación**: Documenta los cambios de IP
5. **Alertas**: Configura alertas para cambios de IP de BunkerWeb
6. **Copia de seguridad**: Mantén una configuración de respaldo en caso de problemas

### Configuración REAL_IP y recuperación de dirección del cliente

#### ¿Por qué configurar REAL_IP?

Cuando se utiliza BunkerWeb Cloud como proxy inverso, las direcciones IP que ven tus aplicaciones backend son las de BunkerWeb Cloud, no las de los clientes reales. Para recuperar las direcciones IP reales de los clientes, se requiere una configuración específica.

#### Configuración del lado de BunkerWeb Cloud

En la IU de BunkerWeb, configura Real IP:

```yaml
USE_REAL_IP: yes # Por defecto es no
REAL_IP_FROM: 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8 # Por defecto
REAL_IP_HEADER: X-Forwarded-For # Por defecto
REAL_IP_RECURSIVE: yes # Por defecto
# Ejemplo si también usas Cloudflare Proxy frente a BunkerWeb
REAL_IP_FROM_URLS: https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/
```

Puedes encontrar todas las opciones de configuración en la [Documentación de Real Ip](https://docs.bunkerweb.io/latest/settings/#real-ip)

#### Configuración del lado de la infraestructura del cliente

##### Nginx

<details>
<summary>Configuración Nginx para REAL_IP</summary>

```nginx
# Configurar direcciones IP de confianza (BunkerWeb Cloud)
set_real_ip_from 4.233.128.18/32
set_real_ip_from 20.19.161.132/32

# Cabecera a usar para recuperar la IP real
real_ip_header X-Real-IP;

# Alternativa con X-Forwarded-For
# real_ip_header X-Forwarded-For;

server {
    listen 443 ssl http2;
    server_name ejemplo.com;

    # Configuración SSL
    ssl_certificate /path/to/ejemplo.com.crt;
    ssl_certificate_key /path/to/ejemplo.com.key;

    location / {
        proxy_pass http://service1:8080;

        # Reenviar cabeceras de IP real al backend
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Registro con IP real del cliente
        access_log /var/log/nginx/access.log combined;
    }
}

# Formato de registro personalizado con IP real
log_format real_ip '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent" '
                   'real_ip="$realip_remote_addr"';
```

</details>

##### Apache

<details>
<summary>Configuración Apache para REAL_IP</summary>

```apache
# Cargar módulo mod_remoteip
LoadModule remoteip_module modules/mod_remoteip.so

<VirtualHost *:443>
    ServerName ejemplo.com

    # Configuración SSL
    SSLEngine on
    SSLCertificateFile /path/to/ejemplo.com.crt
    SSLCertificateKeyFile /path/to/ejemplo.com.key

    # Configurar direcciones IP de confianza
    RemoteIPHeader X-Real-IP
    RemoteIPTrustedProxy 4.233.128.18/32
    RemoteIPTrustedProxy 20.19.161.132/32

    # Alternativa con X-Forwarded-For
    # RemoteIPHeader X-Forwarded-For

    # Configuración reverse proxy
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Reenviar cabeceras IP
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    # Registros con IP real
    LogFormat "%a %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined_real_ip
    CustomLog logs/access.log combined_real_ip
    ErrorLog logs/error.log
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>Configuración HAProxy para REAL_IP</summary>

```haproxy
global
    maxconn 4096
    log stdout local0

defaults
    mode http
    option httplog
    option dontlognull
    option forwardfor

    # Formato de registro con IP real
    log-format "%ci:%cp [%t] %ft %b/%s %Tq/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"

frontend https_frontend
    bind *:443 ssl crt /etc/ssl/certs/

    # Lista blanca de IP de BunkerWeb Cloud
    acl bunkerweb_ips src 4.233.128.18/32 20.19.161.132/32
    http-request deny unless bunkerweb_ips

    # Capturar IP real de cabeceras
    capture request header X-Real-IP len 15
    capture request header X-Forwarded-For len 50

    # Enrutamiento
    acl is_ejemplo hdr(host) -i ejemplo.com
    use_backend app_servers if is_ejemplo

    default_backend app_servers

backend app_servers
    balance roundrobin

    # Añadir/preservar cabeceras de IP real
    http-request set-header X-Original-Forwarded-For %[req.hdr(X-Forwarded-For)]
    http-request set-header X-Client-IP %[req.hdr(X-Real-IP)]

    server app1 service1:8080 check
    server app2 service2:8080 check backup
```

</details>

##### Traefik

<details>
<summary>Configuración Traefik para REAL_IP</summary>

```yaml
# Configuración en dynamic.yml
http:
  middlewares:
    real-ip:
      ipWhiteList:
        sourceRange:
          - "4.233.128.18/32"
          - "20.19.161.132/32"
        ipStrategy:
          depth: 2  # Número de proxies de confianza
          excludedIPs:
            - "127.0.0.1/32"

  routers:
    ejemplo-router:
      rule: "Host(`ejemplo.com`)"
      service: "ejemplo-service"
      middlewares:
        - "real-ip"
      tls:
        certResolver: "myresolver"

  services:
    ejemplo-service:
      loadBalancer:
        servers:
          - url: "http://service1:8080"
        passHostHeader: true
```

**Configuración en traefik.yml (estática):**

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

#### Pruebas y Validación

##### Verificación de la configuración

```bash
# Test 1: Verificar cabeceras recibidas
curl -H "X-Real-IP: 203.0.113.1" \
     -H "X-Forwarded-For: 203.0.113.1, 192.168.1.100" \
     https://ejemplo.com/test-ip

# Test 2: Analizar registros
tail -f /var/log/nginx/access.log | grep "203.0.113.1"

# Test 3: Prueba desde diferentes fuentes
curl -v https://ejemplo.com/whatismyip
```

#### Mejores prácticas de REAL_IP

1. **Seguridad**: Confía solo en cabeceras IP de fuentes conocidas (BunkerWeb Cloud)
2. **Validación**: Valida siempre las direcciones IP recibidas en las cabeceras
3. **Registro**: Registra tanto la IP del proxy como la IP real para depuración
4. **Respaldo**: Ten siempre un valor por defecto si faltan cabeceras
5. **Pruebas**: Prueba regularmente que la detección de IP funciona correctamente
6. **Monitorización**: Monitoriza los patrones de IP para detectar anomalías

#### Solución de problemas de REAL_IP

##### Problemas comunes

1. **La IP siempre muestra la de BunkerWeb**: Comprueba la configuración de proxies de confianza
2. **Faltan cabeceras**: Comprueba la configuración del lado de BunkerWeb Cloud
3. **IPs inválidas**: Implementa una validación estricta de IP
4. **Registros incorrectos**: Comprueba el formato de registro y la configuración del módulo real_ip

##### Comandos de diagnóstico

__Probar detección de IP__

```bash
curl -H "X-Real-IP: 1.2.3.4" https://tu-dominio.com/debug-headers
```

### Monitorización y Observabilidad

#### Acceso a Grafana

Tu instancia de Grafana gestionada te da acceso a:

##### Métricas disponibles

1. **Visión general del tráfico**

  - Solicitudes por segundo
  - Códigos de estado HTTP
  - Geolocalización de solicitudes
2. **Seguridad**

  - Intentos de ataque bloqueados
  - Tipos de amenazas detectados
  - Reglas WAF activadas
3. **Métricas de rendimiento**

  - Latencia de solicitud
  - Tiempo de respuesta del backend
  - Utilización de recursos

##### Registros disponibles

1. **Registros de acceso**: Todas las solicitudes HTTP/HTTPS
2. **Registros de seguridad**: Eventos de seguridad y bloqueos
3. **Registros de error**: Errores de aplicación y sistema

##### Configuración de alertas

Configura alertas de Grafana para:

- Picos de tráfico anormales
- Aumento de errores 5xx
- Detección de ataques DDoS
- Fallos de salud del backend

### Mejores prácticas

#### Seguridad

1. **Usa HTTPS** para toda la comunicación con el backend
2. **Implementa una lista blanca de IP** si es posible
3. **Configura timeouts apropiados**
4. **Habilita la compresión** para optimizar el rendimiento

#### Rendimiento

1. **Optimiza la configuración de caché**
2. **Usa HTTP/2** en el lado del cliente
3. **Configura comprobaciones de salud** para tus backends
4. **Monitoriza las métricas** regularmente

### Solución de problemas

#### Problemas comunes

##### 1. Error SSL/TLS

**Síntoma:** Errores de certificado SSL

**Soluciones:**

```bash
# Comprobar configuración SNI
openssl s_client -connect backend.com:443 -servername ejemplo.com

# Comprobar certificados de backend
openssl x509 -in certificate.crt -text -noout
```

##### 2. Timeout de Backend

**Síntoma:** Errores 504 Gateway Timeout

**Soluciones:**

- Aumentar `REVERSE_PROXY_CONNECT_TIMEOUT` & `REVERSE_PROXY_SEND_TIMEOUT`
- Comprobar salud del backend
- Optimizar rendimiento de la aplicación

##### 3. Problemas de enrutamiento

**Síntoma:** Se sirve el servicio incorrecto

**Soluciones:**

- Comprobar configuración `SERVER_NAME`
- Validar configuración SNI
- Comprobar cabeceras `Host`

#### Comandos de diagnóstico

```bash
# Prueba de conectividad
curl -v https://tu-dominio.com

# Prueba con cabeceras personalizadas
curl -H "Host: ejemplo.com" -v https://54984654.bunkerweb.cloud

# Verificación DNS
dig +trace ejemplo.com

# Prueba SSL
openssl s_client -connect ejemplo.com:443 -servername ejemplo.com
```

#### Soporte Técnico

Para cualquier asistencia técnica:

1. **Comprueba los registros** en Grafana
2. **Verifica la configuración** en la IU de BunkerWeb
3. **Contacta con soporte** con detalles de configuración y registros de error

## Imagen Todo en Uno (AIO) {#all-in-one-aio-image}

<figure markdown>
  ![Marcador de posición del gráfico de arquitectura AIO](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>Arquitectura Todo en Uno de BunkerWeb (AIO)</figcaption>
</figure>

### Despliegue {#deployment}

Para desplegar el contenedor todo en uno, todo lo que tienes que hacer es ejecutar el siguiente comando:

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1
```

Por defecto, el contenedor expone:

- 8080/tcp para HTTP
- 8443/tcp para HTTPS
- 8443/udp para QUIC
- 7000/tcp para el acceso a la interfaz de usuario web sin BunkerWeb delante (no recomendado para producción)
- 8888/tcp para la API cuando `SERVICE_API=yes` (uso interno; prefiere exponerla a través de BunkerWeb como un proxy inverso en lugar de publicarla directamente)

Se requiere un volumen nombrado (o un bind mount) para persistir la base de datos SQLite, la caché y las copias de seguridad almacenadas en `/data` dentro del contenedor:

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

!!! warning "Uso de una carpeta local para datos persistentes"
    El contenedor Todo en Uno ejecuta sus servicios como un **usuario no privilegiado con UID 101 y GID 101**. Esto mejora la seguridad: incluso si algún componente se ve comprometido, no obtiene privilegios de root (UID/GID 0) en el host.

    Si montas una **carpeta local**, asegúrate de que los permisos del directorio permitan que ese usuario no privilegiado pueda escribir datos:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    O, si la carpeta ya existe:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Cuando utilices [Docker en modo rootless](https://docs.docker.com/engine/security/rootless) o [Podman](https://podman.io/), los UID/GID del contenedor se remapean. Verifica primero tus rangos `subuid` y `subgid`:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Por ejemplo, si el rango comienza en **100000**, el UID/GID efectivo será **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    O, si la carpeta ya existe:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

La imagen Todo en Uno viene con varios servicios integrados, que se pueden controlar mediante variables de entorno:

- `SERVICE_UI=yes` (predeterminado) - Habilita el servicio de la interfaz de usuario web
- `SERVICE_SCHEDULER=yes` (predeterminado) - Habilita el servicio del Programador
- `SERVICE_API=no` (predeterminado) - Habilita el servicio de la API (plano de control de FastAPI)
- `AUTOCONF_MODE=no` (predeterminado) - Habilita el servicio de autoconfiguración
- `USE_REDIS=yes` (predeterminado) - Habilita la instancia de [Redis](#redis-integration) integrada
- `USE_CROWDSEC=no` (predeterminado) - La integración con [CrowdSec](#crowdsec-integration) está deshabilitada por defecto
- `HIDE_SERVICE_LOGS=` (opcional) - Lista separada por comas de servicios cuyos registros se silencian en los logs del contenedor. Valores admitidos: `api`, `autoconf`, `bunkerweb`, `crowdsec`, `redis`, `scheduler`, `ui`, `nginx.access`, `nginx.error`, `modsec`. Los archivos en `/var/log/bunkerweb/<service>.log` se siguen actualizando.

### Integración de la API

La imagen Todo en Uno incorpora la API de BunkerWeb. Está deshabilitada por defecto y se puede habilitar estableciendo `SERVICE_API=yes`.

!!! warning "Seguridad"
    La API es un plano de control privilegiado. No la expongas directamente a Internet. Mantenla en una red interna, restringe las IP de origen con `API_WHITELIST_IPS`, requiere autenticación (`API_TOKEN` o usuarios de API + Biscuit), y preferiblemente accede a ella a través de BunkerWeb como un proxy inverso en una ruta difícil de adivinar.

Habilitación rápida (independiente) — publica el puerto de la API; solo para pruebas:

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

Recomendado (detrás de BunkerWeb) — no publiques el `8888`; en su lugar, haz un proxy inverso:

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
      api.example.com_REVERSE_PROXY_HOST: "http://127.0.0.1:8888" # Punto interno de la API

      # Configuración de la API
      SERVICE_API: "yes"
      # Usa credenciales robustas y limita el acceso a IP/redes de confianza (más detalles abajo)
      API_USERNAME: "changeme"
      API_PASSWORD: "StrongP@ssw0rd"
      API_ROOT_PATH: "/api-<unguessable>" # Debe coincidir con REVERSE_PROXY_URL

      # Desactivamos la IU; cámbialo a "yes" para habilitarla
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

Los detalles sobre la autenticación, los permisos (ACL), la limitación de velocidad, TLS y las opciones de configuración están disponibles en la [documentación de la API](api.md).

### Accediendo al asistente de configuración

Por defecto, el asistente de configuración se inicia automáticamente cuando ejecutas el contenedor AIO por primera vez. Para acceder a él, sigue estos pasos:

1.  **Inicia el contenedor AIO** como se indicó [anteriormente](#deployment), asegurándote de que `SERVICE_UI=yes` (predeterminado).
2.  **Accede a la UI** a través de tu punto de acceso principal de BunkerWeb, p. ej., `https://tu-dominio`.

> Sigue los siguientes pasos en la [Guía de inicio rápido](quickstart-guide.md#complete-the-setup-wizard) para configurar la Interfaz de Usuario Web.

### Integración con Redis {#redis-integration}

La imagen **Todo en Uno** de BunkerWeb incluye Redis listo para usar para la [persistencia de baneos e informes](advanced.md#persistence-of-bans-and-reports). Ten en cuenta:

- El servicio Redis integrado solo se inicia cuando `USE_REDIS=yes` **y** `REDIS_HOST` se mantiene en su valor predeterminado (`127.0.0.1`/`localhost`).
- Escucha en la interfaz de loopback del contenedor, por lo que solo está disponible para los procesos del contenedor, no para otros contenedores ni para el host.
- Sobrescribe `REDIS_HOST` únicamente cuando tengas un extremo Redis/Valkey externo disponible; de lo contrario, la instancia integrada no se iniciará.
- Para deshabilitar Redis por completo, establece `USE_REDIS=no`.
- Los registros de Redis aparecen con el prefijo `[REDIS]` en los registros de Docker y en `/var/log/bunkerweb/redis.log`.

### Integración con CrowdSec {#crowdsec-integration}

La imagen Docker **Todo en Uno** de BunkerWeb viene con CrowdSec totalmente integrado, sin necesidad de contenedores adicionales ni configuración manual. Sigue los pasos a continuación para habilitar, configurar y ampliar CrowdSec en tu despliegue.

Por defecto, CrowdSec está **deshabilitado**. Para activarlo, simplemente añade la variable de entorno `USE_CROWDSEC`:

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.7-rc1
```

*   Cuando `USE_CROWDSEC=yes`, el punto de entrada hará lo siguiente:

    1.  **Registrará** e **iniciará** el agente local de CrowdSec (a través de `cscli`).
    2.  **Instalará o actualizará** las colecciones y analizadores predeterminados.
    3.  **Configurará** el bouncer `crowdsec-bunkerweb-bouncer/v1.6`.

---

#### Colecciones y Analizadores Predeterminados

En el primer inicio (o después de una actualización), estos activos se instalan y mantienen actualizados automáticamente:

| Tipo           | Nombre                                  | Propósito                                                                                                                                                                                                                                                          |
| :------------- | :-------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Colección**  | `bunkerity/bunkerweb`                   | Defiende los servidores Nginx contra una amplia gama de ataques basados en HTTP, desde fuerza bruta hasta intentos de inyección.                                                                                                                                   |
| **Colección**  | `crowdsecurity/appsec-virtual-patching` | Ofrece un conjunto de reglas de estilo WAF actualizado dinámicamente que apunta a CVEs conocidos, parcheado automáticamente a diario para proteger las aplicaciones web de vulnerabilidades recién descubiertas.                                                   |
| **Colección**  | `crowdsecurity/appsec-generic-rules`    | Complementa `crowdsecurity/appsec-virtual-patching` con heurísticas para patrones de ataque genéricos a nivel de aplicación, como enumeración, recorrido de rutas y sondeos automatizados, llenando los vacíos donde las reglas específicas de CVE aún no existen. |
| **Analizador** | `crowdsecurity/geoip-enrich`            | Enriquece los eventos con contexto de GeoIP.                                                                                                                                                                                                                       |

<details>
<summary><strong>Cómo funciona internamente</strong></summary>

El script de punto de entrada invoca:

```bash
cscli hub update
cscli install collection bunkerity/bunkerweb
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

!!! info "¿No aparece la colección en Docker?"
    Si dentro del contenedor `cscli collections list` sigue sin mostrar `bunkerity/bunkerweb`, ejecuta `docker exec -it bunkerweb-aio cscli hub update` y reinicia después el contenedor (`docker restart bunkerweb-aio`) para actualizar la caché local del hub.

---

#### Añadir Colecciones Adicionales

¿Necesitas más cobertura? Define `CROWDSEC_EXTRA_COLLECTIONS` con una lista de colecciones del Hub separadas por espacios:

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

!!! info "Cómo funciona internamente"

    El script recorre cada nombre e instala o actualiza según sea necesario, sin necesidad de pasos manuales.

---

#### Deshabilitar Analizadores Específicos

Si quieres mantener la configuración predeterminada pero deshabilitar explícitamente uno o más analizadores, proporciona una lista separada por espacios a través de `CROWDSEC_DISABLED_PARSERS`:

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

Notas:
- La lista se aplica después de que se instalen/actualicen los elementos requeridos; solo se eliminan los analizadores que listas.
- Usa los slugs del hub como se muestra en `cscli parsers list` (p. ej., `crowdsecurity/geoip-enrich`).

---

#### Conmutador de AppSec

Las características de [AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) de CrowdSec —impulsadas por las colecciones `appsec-virtual-patching` y `appsec-generic-rules`— están **habilitadas por defecto**.

Para **deshabilitar** toda la funcionalidad de AppSec (WAF/parches virtuales), establece:

```bash
-e CROWDSEC_APPSEC_URL=""
```

Esto desactiva efectivamente el punto final de AppSec para que no se apliquen reglas.

---

#### API Externa de CrowdSec

Si operas una instancia remota de CrowdSec, apunta el contenedor a tu API:

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

*   El **registro local** se omite cuando `CROWDSEC_API` no es `127.0.0.1` o `localhost`.
*   **AppSec** se deshabilita por defecto cuando se usa una API externa. Para habilitarlo, establece `CROWDSEC_APPSEC_URL` en tu punto final deseado.
*   El registro del bouncer todavía se realiza contra la API remota.
*   Para reutilizar una clave de bouncer existente, proporciona `CROWDSEC_API_KEY` con tu token pregenerado.

!!! tip "Más opciones"
    Para una cobertura completa de todas las opciones de CrowdSec (escenarios personalizados, registros, solución de problemas y más), consulta la [documentación del plugin de BunkerWeb CrowdSec](features.md#crowdsec) o visita el [sitio web oficial de CrowdSec](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs).

## Docker {#docker}

<figure markdown>
  ![Descripción general](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Integración con Docker</figcaption>
</figure>

Usar BunkerWeb como un contenedor de [Docker](https://www.docker.com/) ofrece un enfoque conveniente y sencillo para probar y utilizar la solución, especialmente si ya estás familiarizado con la tecnología Docker.

Para facilitar tu despliegue en Docker, proporcionamos imágenes preconstruidas listas para usar en [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb), compatibles con múltiples arquitecturas. Estas imágenes preconstruidas están optimizadas y preparadas para su uso en las siguientes arquitecturas:

- x64 (64 bits)
- x86
- armv8 (ARM 64 bits)
- armv7 (ARM 32 bits)

Al acceder a estas imágenes preconstruidas desde Docker Hub, puedes obtener y ejecutar rápidamente BunkerWeb dentro de tu entorno Docker, eliminando la necesidad de extensos procesos de configuración. Este enfoque simplificado te permite concentrarte en aprovechar las capacidades de BunkerWeb sin complejidades innecesarias.

Ya sea que estés realizando pruebas, desarrollando aplicaciones o desplegando BunkerWeb en producción, la opción de contenedorización de Docker proporciona flexibilidad y facilidad de uso. Adoptar este método te permite aprovechar al máximo las características de BunkerWeb mientras te beneficias de las ventajas de la tecnología Docker.

```shell
docker pull bunkerity/bunkerweb:1.6.7-rc1
```

Las imágenes de Docker también están disponibles en [GitHub packages](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) y se pueden descargar usando la dirección del repositorio `ghcr.io`:

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.7-rc1
```

Los conceptos clave para la integración con Docker incluyen:

- **Variables de entorno**: Configura BunkerWeb fácilmente usando variables de entorno. Estas variables te permiten personalizar varios aspectos del comportamiento de BunkerWeb, como la configuración de red, las opciones de seguridad y otros parámetros.
- **Contenedor del programador**: Gestiona la configuración y ejecuta trabajos usando un contenedor dedicado llamado el [programador](concepts.md#scheduler).
- **Redes**: Las redes de Docker desempeñan un papel vital en la integración de BunkerWeb. Estas redes tienen dos propósitos principales: exponer puertos a los clientes y conectarse a los servicios web ascendentes. Al exponer los puertos, BunkerWeb puede aceptar solicitudes entrantes de los clientes, permitiéndoles acceder a los servicios web protegidos. Además, al conectarse a los servicios web ascendentes, BunkerWeb puede enrutar y gestionar el tráfico de manera eficiente, proporcionando una mayor seguridad y rendimiento.

!!! info "Backend de la base de datos"
    Ten en cuenta que nuestras instrucciones asumen que estás utilizando SQLite como el backend de base de datos predeterminado, según lo configurado por el ajuste `DATABASE_URI`. Sin embargo, también se admiten otros backends de bases de datos. Consulta los archivos docker-compose en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) del repositorio para obtener más información.

### Variables de entorno

Las configuraciones se pasan al Programador usando las variables de entorno de Docker:

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # Esto se usa para persistir la caché y otros datos como las copias de seguridad
...
```

!!! info "Lista completa"
    Para la lista completa de variables de entorno, consulta la [sección de configuraciones](features.md) de la documentación.

!!! tip "Omitir contenedores etiquetados"
    Cuando un contenedor debe ser ignorado por autoconf, establece `DOCKER_IGNORE_LABELS` en el controlador. Proporciona una lista de claves de etiquetas separadas por espacios o comas (por ejemplo `bunkerweb.SERVER_NAME`) o solo el sufijo (`SERVER_NAME`). Cualquier contenedor o fuente de configuración personalizada que lleve una etiqueta coincidente se omite durante el descubrimiento, y la etiqueta se ignora al traducir las configuraciones.

### Usando secretos de Docker

En lugar de pasar configuraciones sensibles a través de variables de entorno, puedes almacenarlas como secretos de Docker. Para cada configuración que quieras asegurar, crea un secreto de Docker con el nombre que coincida con la clave de la configuración (en mayúsculas). Los scripts de punto de entrada de BunkerWeb cargan automáticamente los secretos desde `/run/secrets` y los exportan como variables de entorno.

Ejemplo:
```bash
# Crear un secreto de Docker para ADMIN_PASSWORD
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

Monta los secretos al desplegar:
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

Esto asegura que las configuraciones sensibles se mantengan fuera del entorno y de los registros.

### Programador

El [programador](concepts.md#scheduler) se ejecuta en su propio contenedor, que también está disponible en Docker Hub:

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.7-rc1
```

!!! info "Configuraciones de BunkerWeb"

    Desde la versión `1.6.0`, el contenedor del Programador es donde defines las configuraciones para BunkerWeb. El Programador luego envía la configuración al contenedor de BunkerWeb.

    ⚠ **Importante**: Todas las configuraciones relacionadas con la API (como `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME`, `API_WHITELIST_IP`, y `API_TOKEN` si lo usas) **también deben definirse en el contenedor de BunkerWeb**. Las configuraciones deben ser idénticas en ambos contenedores; de lo contrario, el contenedor de BunkerWeb no aceptará las solicitudes de la API del Programador.

    ```yaml
    x-bw-api-env: &bw-api-env
      # Usamos un ancla para evitar repetir las mismas configuraciones en ambos contenedores
      API_HTTP_PORT: "5000" # Valor predeterminado
      API_LISTEN_IP: "0.0.0.0" # Valor predeterminado
      API_SERVER_NAME: "bwapi" # Valor predeterminado
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Configura esto según tu red
      # Token opcional; si se establece, el Programador envía Authorization: Bearer <token>
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        environment:
          # Esto establecerá las configuraciones de la API para el contenedor de BunkerWeb
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
        environment:
          # Esto establecerá las configuraciones de la API para el contenedor del Programador
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # Esto se usa para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

Se necesita un volumen para almacenar la base de datos SQLite y las copias de seguridad utilizadas por el programador:

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

!!! warning "Usar una carpeta local para datos persistentes"
    El programador se ejecuta como un **usuario sin privilegios con UID 101 y GID 101** dentro del contenedor. Esto mejora la seguridad: en caso de que se explote una vulnerabilidad, el atacante no tendrá privilegios completos de root (UID/GID 0).

    Sin embargo, si usas una **carpeta local para datos persistentes**, debes **establecer los permisos correctos** para que el usuario sin privilegios pueda escribir datos en ella. Por ejemplo:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternativamente, si la carpeta ya existe:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Si estás utilizando [Docker en modo sin raíz](https://docs.docker.com/engine/security/rootless) o [Podman](https://podman.io/), los UID y GID en el contenedor se mapearán a diferentes en el host. Primero necesitarás verificar tu subuid y subgid iniciales:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Por ejemplo, si tienes un valor de **100000**, el UID/GID mapeado será **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    O si la carpeta ya existe:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### Configuraciones del contenedor del programador

El programador es el worker del plano de control que lee configuraciones, genera configs y las envía a las instancias de BunkerWeb. Las opciones están centralizadas aquí con defaults y valores aceptados.

#### Fuentes de configuración y prioridad

1. Variables de entorno (incluyendo `environment:` de Docker/Compose)
2. Secrets en `/run/secrets/<VAR>` (cargados automáticamente por el entrypoint)
3. Valores predeterminados integrados

#### Referencia de configuración (usuarios avanzados)

##### Runtime y seguridad

| Setting                         | Descripción                                                                       | Valores aceptados                                         | Predeterminado                               |
| ------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------- | -------------------------------------------- |
| `HEALTHCHECK_INTERVAL`          | Segundos entre healthchecks del programador                                       | Segundos enteros                                           | `30`                                         |
| `RELOAD_MIN_TIMEOUT`            | Segundos mínimos entre recargas consecutivas                                      | Segundos enteros                                           | `5`                                          |
| `DISABLE_CONFIGURATION_TESTING` | Saltar pruebas de configuración antes de aplicar                                   | `yes` o `no`                                               | `no`                                         |
| `IGNORE_FAIL_SENDING_CONFIG`    | Continuar incluso si algunas instancias no reciben la configuración               | `yes` o `no`                                               | `no`                                         |
| `IGNORE_REGEX_CHECK`            | Omitir validación regex de configuraciones (compartido con autoconf)              | `yes` o `no`                                               | `no`                                         |
| `TZ`                            | Zona horaria para logs del programador, jobs tipo cron, backups y marcas de tiempo | Nombre en base TZ (ej. `UTC`, `Europe/Paris`)             | unset (default de contenedor, suele ser UTC) |

##### Base de datos

| Setting                 | Descripción                                                                             | Valores aceptados           | Predeterminado                               |
| ----------------------- | --------------------------------------------------------------------------------------- | --------------------------- | -------------------------------------------- |
| `DATABASE_URI`          | DSN principal de base de datos (compartido con autoconf e instancias)                   | DSN de SQLAlchemy           | `sqlite:////var/lib/bunkerweb/db.sqlite3`    |
| `DATABASE_URI_READONLY` | DSN opcional solo-lectura; el programador cae a solo-lectura si es lo único que funciona | DSN de SQLAlchemy o vacío   | unset                                        |

##### Logging

| Setting                         | Descripción                                                                  | Valores aceptados                                         | Predeterminado                                                             |
| ------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Nivel base / override                                                        | `debug`, `info`, `warning`, `error`, `critical`           | `info`                                                                     |
| `LOG_TYPES`                     | Destinos                                                                     | `stderr`/`file`/`syslog` separados por espacios            | `stderr`                                                                   |
| `SCHEDULER_LOG_TO_FILE`         | Habilitar logging a archivo y ruta por defecto                               | `yes` o `no`                                               | `no`                                                                       |
| `LOG_FILE_PATH`                 | Ruta de log personalizada (usada cuando `LOG_TYPES` incluye `file`)          | Ruta de archivo                                            | `/var/log/bunkerweb/scheduler.log` con `SCHEDULER_LOG_TO_FILE=yes`, si no unset |
| `LOG_SYSLOG_ADDRESS`            | Destino syslog (`udp://host:514`, `tcp://host:514` o ruta de socket)         | Host:puerto, host con prefijo de protocolo o socket        | unset                                                                      |
| `LOG_SYSLOG_TAG`                | Ident/tag de syslog                                                          | Cadena                                                     | `bw-scheduler`                                                             |

### Configuraciones del contenedor de UI

El contenedor de UI también respeta `TZ` para localizar los logs y las tareas programadas (p. ej. tareas de limpieza iniciadas por la UI).

| Setting | Descripción                                   | Valores aceptados                                  | Predeterminado                                |
| ------- | --------------------------------------------- | -------------------------------------------------- | --------------------------------------------- |
| `TZ`    | Zona horaria para logs de UI y acciones programadas | Nombre en base TZ (ej. `UTC`, `Europe/Paris`)     | unset (default de contenedor, suele ser UTC)  |

#### Logging

| Setting                         | Descripción                                                              | Valores aceptados                                         | Predeterminado                                                         |
| ------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------- | ---------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Nivel base / override                                                    | `debug`, `info`, `warning`, `error`, `critical`           | `info`                                                                  |
| `LOG_TYPES`                     | Destinos                                                                 | `stderr`/`file`/`syslog` separados por espacios            | `stderr`                                                                |
| `LOG_FILE_PATH`                 | Ruta para logging a archivo (usada si `LOG_TYPES` incluye `file` o `CAPTURE_OUTPUT=yes`) | Ruta de archivo                                            | `/var/log/bunkerweb/ui.log` si file/capture, si no unset              |
| `LOG_SYSLOG_ADDRESS`            | Destino syslog (`udp://host:514`, `tcp://host:514`, socket)              | Host:puerto, host con prefijo de protocolo o ruta          | unset                                                                   |
| `LOG_SYSLOG_TAG`                | Ident/tag de syslog                                                      | Cadena                                                    | `bw-ui`                                                                 |
| `CAPTURE_OUTPUT`                | Enviar stdout/stderr de Gunicorn a las salidas de log configuradas       | `yes` o `no`                                              | `no`                                                                    |

### Redes

Por defecto, el contenedor de BunkerWeb escucha (dentro del contenedor) en **8080/tcp** para **HTTP**, **8443/tcp** para **HTTPS**, y **8443/udp** para **QUIC**.

!!! warning "Puertos privilegiados en modo sin raíz o al usar Podman"
    Si estás usando [Docker en modo sin raíz](https://docs.docker.com/engine/security/rootless) y quieres redirigir puertos privilegiados (< 1024) como el 80 y 443 a BunkerWeb, por favor consulta los prerrequisitos [aquí](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    Si estás usando [Podman](https://podman.io/), puedes reducir el número mínimo para puertos no privilegiados:
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

La pila típica de BunkerWeb cuando se usa la integración con Docker contiene los siguientes contenedores:

- BunkerWeb
- Programador
- Tus servicios

Para fines de defensa en profundidad, recomendamos encarecidamente crear al menos tres redes Docker diferentes:

- `bw-services`: para BunkerWeb y tus servicios web
- `bw-universe`: para BunkerWeb y el programador
- `bw-db`: para la base de datos (si estás usando una)

Para asegurar la comunicación entre el programador y la API de BunkerWeb, **autoriza las llamadas a la API**. Usa la configuración `API_WHITELIST_IP` para especificar las direcciones IP y subredes permitidas. Para una protección más fuerte, establece `API_TOKEN` en ambos contenedores; el programador incluirá automáticamente `Authorization: Bearer <token>`.

**Se recomienda encarecidamente usar una subred estática para la red `bw-universe`** para mejorar la seguridad. Al implementar estas medidas, puedes asegurar que solo las fuentes autorizadas puedan acceder a la API de BunkerWeb, reduciendo el riesgo de acceso no autorizado o actividades maliciosas:

```yaml
x-bw-api-env: &bw-api-env
  # Usamos un ancla para evitar repetir las mismas configuraciones en ambos contenedores
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  API_TOKEN: "" # Token de API opcional
  # Token de API opcional para acceso autenticado a la API
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
      BUNKERWEB_INSTANCES: "bunkerweb" # Esta configuración es obligatoria para especificar la instancia de BunkerWeb
    volumes:
      - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
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
        - subnet: 10.20.30.0/24 # Subred estática para que solo las fuentes autorizadas puedan acceder a la API de BunkerWeb
  bw-services:
    name: bw-services
```

### Archivo compose completo

```yaml
x-bw-api-env: &bw-api-env
  # Usamos un ancla para evitar repetir las mismas configuraciones para ambos contenedores
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
      BUNKERWEB_INSTANCES: "bunkerweb" # Esta configuración es obligatoria para especificar la instancia de BunkerWeb
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
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
        - subnet: 10.20.30.0/24 # Subred estática para que solo las fuentes autorizadas puedan acceder a la API de BunkerWeb
  bw-services:
    name: bw-services
```

### Compilar desde el código fuente

Alternativamente, si prefieres un enfoque más práctico, tienes la opción de compilar la imagen de Docker directamente desde el [código fuente](https://github.com/bunkerity/bunkerweb). Compilar la imagen desde el código fuente te da un mayor control y personalización sobre el proceso de despliegue. Sin embargo, ten en cuenta que este método puede tardar un tiempo en completarse, dependiendo de la configuración de tu hardware (puedes tomarte un café ☕ si es necesario).

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
  ![Descripción general](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Integración con Linux</figcaption>
</figure>

Las distribuciones de Linux compatibles con BunkerWeb (arquitecturas amd64/x86_64 y arm64/aarch64) incluyen:

- Debian 12 "Bookworm"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41, 42 y 43
- Red Hat Enterprise Linux (RHEL) 8, 9 y 10

### Script de instalación fácil

Para una experiencia de instalación simplificada, BunkerWeb proporciona un script de instalación fácil que maneja automáticamente todo el proceso de configuración, incluida la instalación de NGINX, la configuración del repositorio y la configuración del servicio.

#### Inicio rápido

Para empezar, descarga el script de instalación y su suma de verificación, luego verifica la integridad del script antes de ejecutarlo.

```bash
# Descargar el script y su suma de verificación
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.7-rc1/install-bunkerweb.sh
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.7-rc1/install-bunkerweb.sh.sha256

# Verificar la suma de verificación
sha256sum -c install-bunkerweb.sh.sha256

# Si la verificación es exitosa, ejecuta el script
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! danger "Aviso de seguridad"
    **Siempre verifica la integridad del script de instalación antes de ejecutarlo.**

    Descarga el archivo de suma de verificación y utiliza una herramienta como `sha256sum` para confirmar que el script no ha sido alterado o manipulado.

    Si la verificación de la suma de verificación falla, **no ejecutes el script**—puede que no sea seguro.

#### Cómo funciona

El script de instalación fácil es una herramienta poderosa diseñada para simplificar la configuración de BunkerWeb en un sistema Linux nuevo. Automatiza los siguientes pasos clave:

1.  **Análisis del sistema**: Detecta tu sistema operativo y lo verifica contra la lista de distribuciones compatibles.
2.  **Personalización de la instalación**: En modo interactivo, te pide que elijas un tipo de instalación (Todo en uno, Gestor, Trabajador, etc.) y decidas si habilitar el asistente de configuración basado en la web.
3.  **Integraciones opcionales**: Ofrece instalar y configurar automáticamente el [Motor de Seguridad CrowdSec](#crowdsec-integration-with-the-script).
4.  **Gestión de dependencias**: Instala la versión correcta de NGINX requerida por BunkerWeb desde fuentes oficiales y bloquea la versión para evitar actualizaciones no deseadas.
5.  **Instalación de BunkerWeb**: Añade el repositorio de paquetes de BunkerWeb, instala los paquetes necesarios y bloquea la versión.
6.  **Configuración del servicio**: Configura y habilita los servicios `systemd` correspondientes a tu tipo de instalación elegido.
7.  **Guía post-instalación**: Proporciona los siguientes pasos claros para ayudarte a empezar con tu nueva instancia de BunkerWeb.

#### Instalación interactiva

Cuando se ejecuta sin ninguna opción, el script entra en un modo interactivo que te guía a través del proceso de configuración. Se te pedirá que tomes las siguientes decisiones:

1.  **Tipo de instalación**: Selecciona los componentes que quieres instalar.
    *   **Pila completa (predeterminado)**: Una instalación todo en uno que incluye BunkerWeb, el Programador y la Interfaz de Usuario Web.
    *   **Gestor**: Instala el Programador y la Interfaz de Usuario Web, destinado a gestionar uno o más trabajadores remotos de BunkerWeb.
    *   **Trabajador**: Instala solo la instancia de BunkerWeb, que puede ser gestionada por un Gestor remoto.
    *   **Solo Programador**: Instala solo el componente del Programador.
    *   **Solo Interfaz de Usuario Web**: Instala solo el componente de la Interfaz de Usuario Web.
    *   **Solo API**: Instala solo el servicio API para acceso programático.
2.  **Asistente de configuración**: Elige si habilitar el asistente de configuración basado en la web. Esto es muy recomendable para los usuarios primerizos.
3.  **Integración con CrowdSec**: Opta por instalar el motor de seguridad CrowdSec para una protección avanzada contra amenazas en tiempo real. Disponible solo para instalaciones de Pila completa.
4.  **CrowdSec AppSec**: Si eliges instalar CrowdSec, también puedes habilitar el componente de Seguridad de Aplicaciones (AppSec), que añade capacidades de WAF.
5.  **Resolvers DNS**: Para instalaciones de Pila completa, Gestor y Trabajador, puede especificar opcionalmente IPs de resolvers DNS personalizados.
6.  **API interna HTTPS**: Para instalaciones de Pila completa, Gestor y Trabajador, elija si habilitar HTTPS para la comunicación API interna entre el programador/gestor y las instancias BunkerWeb/trabajador (predeterminado: solo HTTP).
7.  **Servicio de API**: Para instalaciones de Pila completa y Gestor, elige si habilitar el servicio API externo opcional. Está deshabilitado por defecto en las instalaciones de Linux.

!!! info "Instalaciones de Gestor y Programador"
    Si eliges el tipo de instalación **Gestor** o **Solo Programador**, también se te pedirá que proporciones las direcciones IP o los nombres de host de tus instancias de trabajador de BunkerWeb.

#### Opciones de línea de comandos

Para configuraciones no interactivas o automatizadas, el script se puede controlar con indicadores de línea de comandos:

**Opciones generales:**

| Opción                  | Descripción                                                                                       |
| :---------------------- | :------------------------------------------------------------------------------------------------ |
| `-v, --version VERSION` | Especifica la versión de BunkerWeb a instalar (p. ej., `1.6.7~rc1`).                                  |
| `-w, --enable-wizard`   | Habilita el asistente de configuración.                                                           |
| `-n, --no-wizard`       | Deshabilita el asistente de configuración.                                                        |
| `-y, --yes`             | Se ejecuta en modo no interactivo usando las respuestas predeterminadas para todas las preguntas. |
| `-f, --force`           | Fuerza a que la instalación continúe incluso en una versión de SO no compatible.                  |
| `-q, --quiet`           | Instalación silenciosa (suprime la salida).                                                       |
| `--api`, `--enable-api` | Habilita el servicio systemd de la API (FastAPI) (deshabilitado por defecto).                     |
| `--no-api`              | Deshabilita explícitamente el servicio de la API.                                                 |
| `-h, --help`            | Muestra el mensaje de ayuda con todas las opciones disponibles.                                   |
| `--dry-run`             | Muestra lo que se instalaría sin hacerlo.                                                         |

**Tipos de instalación:**

| Opción             | Descripción                                                                           |
| :----------------- | :------------------------------------------------------------------------------------ |
| `--full`           | Instalación de pila completa (BunkerWeb, Programador, UI). Este es el predeterminado. |
| `--manager`        | Instala el Programador y la UI para gestionar trabajadores remotos.                   |
| `--worker`         | Instala solo la instancia de BunkerWeb.                                               |
| `--scheduler-only` | Instala solo el componente del Programador.                                           |
| `--ui-only`        | Instala solo el componente de la Interfaz de Usuario Web.                             |
| `--api-only`       | Instala solo el servicio API (puerto 8000).                                           |

**Integraciones de seguridad:**

| Opción              | Descripción                                                             |
| :------------------ | :---------------------------------------------------------------------- |
| `--crowdsec`        | Instala y configura el motor de seguridad CrowdSec.                     |
| `--no-crowdsec`     | Omite la instalación de CrowdSec.                                       |
| `--crowdsec-appsec` | Instala CrowdSec con el componente AppSec (incluye capacidades de WAF). |

**Opciones avanzadas:**

| Opción                      | Descripción                                                                                           |
| :-------------------------- | :---------------------------------------------------------------------------------------------------- |
| `--instances "IP1 IP2"`     | Lista de instancias de BunkerWeb separadas por espacios (requerido para los modos manager/scheduler). |
| `--manager-ip IPs`          | IPs del manager/scheduler para la lista blanca (requerido para worker en modo no interactivo).        |
| `--dns-resolvers "IP1 IP2"` | IPs de resolvers DNS personalizados (para instalaciones full, manager o worker).                      |
| `--api-https`               | Habilitar HTTPS para la comunicación API interna (predeterminado: solo HTTP).                         |
| `--backup-dir PATH`         | Directorio para almacenar la copia de seguridad automática antes de la actualización.                 |
| `--no-auto-backup`          | Omitir copia de seguridad automática (DEBE haberla hecho manualmente).                                |

**Ejemplo de uso:**

```bash
# Ejecutar en modo interactivo (recomendado para la mayoría de los usuarios)
sudo ./install-bunkerweb.sh

# Instalación no interactiva con valores predeterminados (pila completa, asistente habilitado)
sudo ./install-bunkerweb.sh --yes

# Instalar un nodo Trabajador sin el asistente de configuración
sudo ./install-bunkerweb.sh --worker --no-wizard

# Instalar una versión específica
sudo ./install-bunkerweb.sh --version 1.6.7~rc1

# Configuración del Gestor con instancias de trabajador remotas (se requieren instancias)
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# Gestor con comunicación API interna HTTPS
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11" --api-https

# Trabajador con resolvers DNS personalizados y API interna HTTPS
sudo ./install-bunkerweb.sh --worker --dns-resolvers "1.1.1.1 1.0.0.1" --api-https

# Instalación completa con CrowdSec y AppSec
sudo ./install-bunkerweb.sh --crowdsec-appsec

# Instalación silenciosa no interactiva
sudo ./install-bunkerweb.sh --quiet --yes

# Vista previa de la instalación sin ejecutarla
sudo ./install-bunkerweb.sh --dry-run

# Habilitar la API durante la instalación fácil (no interactiva)
sudo ./install-bunkerweb.sh --yes --api

# Error: CrowdSec no se puede usar con instalaciones de trabajador
# sudo ./install-bunkerweb.sh --worker --crowdsec  # Esto fallará

# Error: Se requieren instancias para el gestor en modo no interactivo
# sudo ./install-bunkerweb.sh --manager --yes  # Esto fallará sin --instances
```

!!! warning "Notas importantes sobre la compatibilidad de las opciones"

    **Limitaciones de CrowdSec:**

    - Las opciones de CrowdSec (`--crowdsec`, `--crowdsec-appsec`) solo son compatibles con el tipo de instalación `--full` (predeterminado)
    - No se pueden usar con instalaciones `--manager`, `--worker`, `--scheduler-only`, `--ui-only` o `--api-only`

    **Disponibilidad del servicio API:**

    - El servicio API externo (puerto 8000) está disponible para los tipos de instalación `--full` y `--manager`
    - No está disponible para instalaciones `--worker`, `--scheduler-only` o `--ui-only`
    - Usa `--api-only` para una instalación dedicada del servicio API

    **Requisitos de las instancias:**
    - La opción `--instances` solo es válida con los tipos de instalación `--manager` y `--scheduler-only`
    - Cuando se usan `--manager` o `--scheduler-only` con `--yes` (modo no interactivo), la opción `--instances` es obligatoria
    - Formato: `--instances "192.168.1.10 192.168.1.11 192.168.1.12"`

    **Interactivo vs No interactivo:**
    - El modo interactivo (predeterminado) pedirá los valores requeridos que falten
    - El modo no interactivo (`--yes`) requiere que todas las opciones necesarias se proporcionen a través de la línea de comandos

#### Integración de CrowdSec con el script {#crowdsec-integration-with-the-script}

Si optas por instalar CrowdSec durante la configuración interactiva, el script automatiza completamente su integración con BunkerWeb:

- Añade el repositorio oficial de CrowdSec e instala el agente.
- Crea un nuevo archivo de adquisición para que CrowdSec analice los registros de BunkerWeb (`access.log`, `error.log` y `modsec_audit.log`).
- Instala colecciones esenciales (`bunkerity/bunkerweb`) y analizadores (`crowdsecurity/geoip-enrich`).
- Registra un bouncer para BunkerWeb y configura automáticamente la clave de la API en `/etc/bunkerweb/variables.env`.
- Si también seleccionas el **Componente AppSec**, instala las colecciones `appsec-virtual-patching` y `appsec-generic-rules` y configura el punto final de AppSec para BunkerWeb.

Esto proporciona una integración perfecta y lista para usar para una potente prevención de intrusiones.

#### Consideraciones sobre RHEL

!!! warning "Soporte de base de datos externa en sistemas basados en RHEL"
    Si planeas usar una base de datos externa (recomendado para producción), debes instalar el paquete de cliente de base de datos apropiado:

    ```bash
    # Para MariaDB
    sudo dnf install mariadb

    # Para MySQL
    sudo dnf install mysql

    # Para PostgreSQL
    sudo dnf install postgresql
    ```

    Esto es necesario para que el Programador de BunkerWeb se conecte a tu base de datos externa.

#### Después de la instalación

Dependiendo de tus elecciones durante la instalación:

**Con el asistente de configuración habilitado:**

1.  Accede al asistente de configuración en: `https://tu-ip-de-servidor/setup`
2.  Sigue la configuración guiada para configurar tu primer servicio protegido
3.  Configura los certificados SSL/TLS y otras configuraciones de seguridad

**Sin el asistente de configuración:**

1.  Edita `/etc/bunkerweb/variables.env` para configurar BunkerWeb manualmente
2.  Añade la configuración de tu servidor y los servicios protegidos
3.  Reinicia el programador: `sudo systemctl restart bunkerweb-scheduler`

### Instalación usando el gestor de paquetes

Asegúrate de tener **NGINX 1.28.0 instalado antes de instalar BunkerWeb**. Para todas las distribuciones, excepto Fedora, es obligatorio usar los paquetes precompilados del [repositorio oficial de NGINX](https://nginx.org/en/linux_packages.html). Compilar NGINX desde el código fuente o usar paquetes de diferentes repositorios no funcionará con los paquetes precompilados oficiales de BunkerWeb. Sin embargo, tienes la opción de compilar BunkerWeb desde el código fuente.

=== "Debian Bookworm/Trixie"

    El primer paso es añadir el repositorio oficial de NGINX:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Ahora deberías poder instalar NGINX 1.28.0:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Versión de prueba/desarrollo"
        Si usas la versión `testing` o `dev`, necesitarás añadir la directiva `force-bad-version` a tu archivo `/etc/dpkg/dpkg.cfg` antes de instalar BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Deshabilitar el asistente de configuración"
        Si no quieres usar el asistente de configuración de la interfaz de usuario web cuando se instale BunkerWeb, exporta la siguiente variable:

        ```shell
        export UI_WIZARD=no
        ```

    Y finalmente instala BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
    ```

    Para evitar la actualización de los paquetes de NGINX y/o BunkerWeb al ejecutar `apt upgrade`, puedes usar el siguiente comando:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    El primer paso es añadir el repositorio oficial de NGINX:

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Ahora deberías poder instalar NGINX 1.28.0:

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Versión de prueba/desarrollo"
        Si usas la versión `testing` o `dev`, necesitarás añadir la directiva `force-bad-version` a tu archivo `/etc/dpkg/dpkg.cfg` antes de instalar BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Deshabilitar el asistente de configuración"
        Si no quieres usar el asistente de configuración de la interfaz de usuario web cuando se instale BunkerWeb, exporta la siguiente variable:

        ```shell
        export UI_WIZARD=no
        ```

    Y finalmente instala BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.7~rc1
    ```

    Para evitar la actualización de los paquetes de NGINX y/o BunkerWeb al ejecutar `apt upgrade`, puedes usar el siguiente comando:

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Pruebas de actualización de Fedora"
        Si no encuentras la versión de NGINX listada en el repositorio estable, puedes habilitar el repositorio `updates-testing`:

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora ya proporciona NGINX que nosotros soportamos. Elige tu versión de Fedora a continuación para instalar el paquete NGINX correcto:

    === "Fedora 41"

        ```shell
        sudo dnf install -y --allowerasing nginx-1.28.0
        ```

    === "Fedora 42 / 43"

        !!! warning "NGINX 1.28.0 ya no está disponible"
            Fedora 42 y 43 han eliminado NGINX 1.28.0 de sus mirrors. Debes instalar NGINX 1.28.1 en su lugar.

        ```shell
        sudo dnf install -y --allowerasing nginx-1.28.1
        ```

    !!! example "Deshabilitar el asistente de configuración"
        Si no quieres usar el asistente de configuración de la interfaz de usuario web cuando se instale BunkerWeb, exporta la siguiente variable:

        ```shell
        export UI_WIZARD=no
        ```

    Y finalmente instala BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
  	sudo dnf makecache && \
  	sudo -E dnf install -y --allowerasing bunkerweb-1.6.7~rc1
    ```

    Para evitar la actualización de los paquetes de NGINX y/o BunkerWeb al ejecutar `dnf upgrade`, puedes usar el siguiente comando:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    El primer paso es añadir el repositorio oficial de NGINX. Crea el siguiente archivo en `/etc/yum.repos.d/nginx.repo`:

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

    Ahora deberías poder instalar NGINX 1.28.0:

    ```shell
    sudo dnf install --allowerasing nginx-1.28.0
    ```

    !!! example "Deshabilitar el asistente de configuración"
        Si no quieres usar el asistente de configuración de la interfaz de usuario web cuando se instale BunkerWeb, exporta la siguiente variable:

        ```shell
        export UI_WIZARD=no
        ```

    Y finalmente instala BunkerWeb 1.6.7~rc1:

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.7~rc1
    ```

    Para evitar la actualización de los paquetes de NGINX y/o BunkerWeb al ejecutar `dnf upgrade`, puedes usar el siguiente comando:

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### Configuración y servicio

La configuración manual de BunkerWeb se realiza editando el archivo `/etc/bunkerweb/variables.env`:

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

Cuando se instala, BunkerWeb viene con tres servicios `bunkerweb`, `bunkerweb-scheduler` y `bunkerweb-ui` que puedes gestionar usando `systemctl`.

Si editas manualmente la configuración de BunkerWeb usando `/etc/bunkerweb/variables.env`, un reinicio del servicio `bunkerweb-scheduler` será suficiente para generar y recargar la configuración sin ningún tiempo de inactividad. Pero dependiendo del caso (como cambiar los puertos de escucha) es posible que necesites reiniciar el servicio `bunkerweb`.

### Alta disponibilidad

El programador puede separarse de la instancia de BunkerWeb para proporcionar alta disponibilidad. En este caso, el programador se instalará en un servidor separado y podrá gestionar múltiples instancias de BunkerWeb.

#### Gestor

Para instalar solo el programador en un servidor, puedes exportar las siguientes variables antes de ejecutar la instalación de BunkerWeb:

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

Alternativamente, también puedes exportar las siguientes variables para habilitar solo el programador:

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

#### Trabajador

En otro servidor, para instalar solo BunkerWeb, puedes exportar las siguientes variables antes de ejecutar la instalación de BunkerWeb:

```shell
export WORKER_MODE=yes
```

Alternativamente, también puedes exportar las siguientes variables para habilitar solo BunkerWeb:

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

#### Interfaz de usuario web

La interfaz de usuario web se puede instalar en un servidor separado para proporcionar una interfaz dedicada para gestionar las instancias de BunkerWeb. Para instalar solo la interfaz de usuario web, puedes exportar las siguientes variables antes de ejecutar la instalación de BunkerWeb:

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

## Autoconfiguración de Docker {#docker-autoconf}

<figure markdown>
  ![Descripción general](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Integración de autoconfiguración de Docker</figcaption>
</figure>

!!! info "Integración con Docker"
    La integración de autoconfiguración de Docker es una "evolución" de la de Docker. Por favor, lee primero la [sección de integración con Docker](#docker) si es necesario.

Hay disponible un enfoque alternativo para solucionar el inconveniente de tener que recrear el contenedor cada vez que hay una actualización. Utilizando otra imagen llamada **autoconf**, puedes automatizar la reconfiguración en tiempo real de BunkerWeb sin necesidad de recrear el contenedor.

Para aprovechar esta funcionalidad, en lugar de definir variables de entorno para el contenedor de BunkerWeb, puedes añadir **etiquetas** a tus contenedores de aplicaciones web. La imagen **autoconf** escuchará entonces los eventos de Docker y gestionará sin problemas las actualizaciones de configuración para BunkerWeb.

Este proceso "*automágico*" simplifica la gestión de las configuraciones de BunkerWeb. Al añadir etiquetas a tus contenedores de aplicaciones web, puedes delegar las tareas de reconfiguración a **autoconf** sin la intervención manual de tener que recrear el contenedor. Esto agiliza el proceso de actualización y mejora la comodidad.

Al adoptar este enfoque, puedes disfrutar de la reconfiguración en tiempo real de BunkerWeb sin la molestia de tener que recrear el contenedor, lo que lo hace más eficiente y fácil de usar.

!!! info "Modo multisitio"
    La integración de autoconfiguración de Docker implica el uso del **modo multisitio**. Por favor, consulta la [sección de multisitio](concepts.md#multisite-mode) de la documentación para obtener más información.

!!! info "Backend de la base de datos"
    Ten en cuenta que nuestras instrucciones asumen que estás utilizando MariaDB como el backend de base de datos predeterminado, según lo configurado por el ajuste `DATABASE_URI`. Sin embargo, entendemos que puedes preferir utilizar backends alternativos para tu integración con Docker. Si ese es el caso, ten la seguridad de que otros backends de bases de datos también son posibles. Consulta los archivos docker-compose en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) del repositorio para obtener más información.

Para habilitar las actualizaciones de configuración automatizadas, incluye un contenedor adicional llamado `bw-autoconf` en la pila. Este contenedor aloja el servicio de autoconfiguración, que gestiona los cambios de configuración dinámicos para BunkerWeb.

Para admitir esta funcionalidad, utiliza un backend de base de datos "real" dedicado (p. ej., MariaDB, MySQL o PostgreSQL) para el almacenamiento de configuración sincronizado. Al integrar `bw-autoconf` y un backend de base de datos adecuado, estableces la infraestructura para una gestión de configuración automatizada y sin problemas en BunkerWeb.

```yaml
x-bw-env: &bw-env
  # Usamos un ancla para evitar repetir las mismas configuraciones para ambos contenedores
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
      - "bunkerweb.INSTANCE=yes" # Etiqueta obligatoria para que el servicio de autoconfiguración identifique la instancia de BunkerWeb
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
      BUNKERWEB_INSTANCES: "" # No necesitamos especificar la instancia de BunkerWeb aquí, ya que son detectadas automáticamente por el servicio de autoconfiguración
      SERVER_NAME: "" # El nombre del servidor se rellenará con las etiquetas de los servicios
      MULTISITE: "yes" # Configuración obligatoria para la autoconfiguración
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
    volumes:
      - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
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
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
      DOCKER_HOST: "tcp://bw-docker:2375" # El socket de Docker
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
    # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
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

!!! info "Base de datos en la red `bw-db`"
    El contenedor de la base de datos no está incluido intencionadamente en la red `bw-universe`. Es utilizado por los contenedores `bw-autoconf` y `bw-scheduler` en lugar de directamente por BunkerWeb. Por lo tanto, el contenedor de la base de datos forma parte de la red `bw-db`, lo que mejora la seguridad al dificultar el acceso externo a la base de datos. **Esta elección de diseño deliberada ayuda a proteger la base de datos y refuerza la perspectiva de seguridad general del sistema**.

!!! warning "Uso de Docker en modo sin raíz"
    Si estás utilizando [Docker en modo sin raíz](https://docs.docker.com/engine/security/rootless), necesitarás reemplazar el montaje del socket de docker con el siguiente valor: `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Configuraciones del contenedor de autoconf

El controlador `bw-autoconf` vigila tu orquestador y escribe cambios en la base de datos compartida.

#### Fuentes de configuración y prioridad

1. Variables de entorno (incluyendo `environment:` de Docker/Compose)
2. Secrets en `/run/secrets/<VAR>` (auto-cargados por el entrypoint)
3. Valores predeterminados integrados

#### Referencia de configuración (usuarios avanzados)

##### Modo y runtime

| Setting               | Descripción                                                  | Valores aceptados                         | Predeterminado                        |
| --------------------- | ------------------------------------------------------------ | ----------------------------------------- | ------------------------------------- |
| `AUTOCONF_MODE`       | Habilitar el controlador de autoconf                         | `yes` o `no`                              | `no`                                  |
| `SWARM_MODE`          | Observar servicios Swarm en lugar de contenedores Docker     | `yes` o `no`                              | `no`                                  |
| `KUBERNETES_MODE`     | Observar ingress/pods de Kubernetes en lugar de Docker       | `yes` o `no`                              | `no`                                  |
| `DOCKER_HOST`         | Socket Docker / URL de API remota                            | p. ej. `unix:///var/run/docker.sock`      | `unix:///var/run/docker.sock`         |
| `WAIT_RETRY_INTERVAL` | Segundos entre comprobaciones de disponibilidad de instancias | Segundos enteros                          | `5`                                   |
| `LOG_SYSLOG_TAG`      | Tag syslog para logs de autoconf                             | Cadena                                    | `bw-autoconf`                         |
| `TZ`                  | Zona horaria para logs de autoconf y marcas de tiempo        | Nombre en base TZ (ej. `Europe/Paris`)    | unset (default de contenedor, suele UTC) |

##### Base de datos y validación

| Setting                 | Descripción                                                                          | Valores aceptados            | Predeterminado                               |
| ----------------------- | ------------------------------------------------------------------------------------ | ---------------------------- | -------------------------------------------- |
| `DATABASE_URI`          | DSN principal de base de datos (debe coincidir con la BD del programador)            | DSN de SQLAlchemy            | `sqlite:////var/lib/bunkerweb/db.sqlite3`    |
| `DATABASE_URI_READONLY` | DSN opcional solo-lectura; autoconf cae a solo-lectura si es lo único que funciona   | DSN de SQLAlchemy o vacío    | unset                                        |
| `IGNORE_REGEX_CHECK`    | Saltar validación regex de configuraciones provenientes de etiquetas/anotaciones     | `yes` o `no`                 | `no`                                         |

##### Logging

| Setting                         | Descripción                                                | Valores aceptados                                         | Predeterminado                                  |
| ------------------------------- | ---------------------------------------------------------- | --------------------------------------------------------- | ----------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Nivel base / override                                      | `debug`, `info`, `warning`, `error`, `critical`           | `info`                                          |
| `LOG_TYPES`                     | Destinos                                                   | `stderr`/`file`/`syslog` separados por espacios            | `stderr`                                        |
| `LOG_FILE_PATH`                 | Ruta para logging a archivo (si `LOG_TYPES` incluye `file`) | Ruta de archivo                                            | unset (define la tuya al habilitar `file`)      |
| `LOG_SYSLOG_ADDRESS`            | Destino syslog (`udp://host:514`, `tcp://host:514`, socket) | Host:puerto, host con prefijo de protocolo o ruta          | unset                                           |
| `LOG_SYSLOG_TAG`                | Ident/tag de syslog                                        | Cadena                                                     | `bw-autoconf`                                   |

##### Alcance y filtros de descubrimiento

| Setting                         | Descripción                                                                 | Valores aceptados                               | Predeterminado |
| ------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------- | -------------- |
| `NAMESPACES`                    | Lista separada por espacios de namespaces/proyectos a gestionar; unset = todos | Cadenas separadas por espacios                  | unset          |
| `DOCKER_IGNORE_LABELS`          | Omitir contenedores/etiquetas al recopilar instancias/servicios/configs     | Claves completas o sufijos separados por espacio/coma | unset          |
| `SWARM_IGNORE_LABELS`           | Ignorar servicios/configs Swarm con etiquetas coincidentes                   | Claves completas o sufijos separados por espacio/coma | unset          |
| `KUBERNETES_IGNORE_ANNOTATIONS` | Ignorar anotaciones de ingress/pod durante el descubrimiento                | Claves completas o sufijos separados por espacio/coma | unset          |

##### Solo Kubernetes

| Setting                                 | Descripción                                                                                      | Valores aceptados         | Predeterminado        |
| --------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------- | --------------------- |
| `KUBERNETES_VERIFY_SSL`                 | Verificar TLS de la API de Kubernetes                                                            | `yes` o `no`              | `yes`                 |
| `KUBERNETES_SSL_CA_CERT`                | Ruta a un bundle de CA personalizado para la API de Kubernetes                                   | Ruta de archivo           | unset                 |
| `USE_KUBERNETES_FQDN`                   | Usar `<pod>.<ns>.pod.<domain>` en vez de la IP del pod como hostname de instancia                 | `yes` o `no`              | `yes`                 |
| `KUBERNETES_INGRESS_CLASS`              | Procesar solo los ingress con esta clase                                                         | Cadena                    | unset (todas)         |
| `KUBERNETES_DOMAIN_NAME`                | Sufijo de dominio del clúster al construir hosts upstream                                        | Cadena                    | `cluster.local`       |
| `KUBERNETES_SERVICE_PROTOCOL`           | Esquema usado para los hosts de reverse proxy generados                                          | `http` o `https`          | `http`                |
| `BUNKERWEB_SERVICE_NAME`                | Nombre del servicio que se lee al parchear el estado del Ingress con la dirección del LB         | Cadena                    | `bunkerweb`           |
| `BUNKERWEB_NAMESPACE`                   | Namespace de ese servicio                                                                        | Cadena                    | `bunkerweb`           |
| `KUBERNETES_REVERSE_PROXY_SUFFIX_START` | Índice inicial para `REVERSE_PROXY_HOST_n`/`REVERSE_PROXY_URL_n` generados en ingress multipath  | Entero (>=0)              | `1`                   |

### Servicios de Autoconfiguración

Una vez que la pila esté configurada, podrás crear el contenedor de la aplicación web y añadir las configuraciones como etiquetas usando el prefijo "bunkerweb." para configurar automáticamente BunkerWeb:

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

### Espacios de nombres {#namespaces}

A partir de la versión `1.6.0`, las pilas de Autoconfiguración de BunkerWeb ahora admiten espacios de nombres. Esta característica te permite gestionar múltiples "*clústeres*" de instancias y servicios de BunkerWeb en el mismo host de Docker. Para aprovechar los espacios de nombres, simplemente establece la etiqueta `NAMESPACE` en tus servicios. Aquí tienes un ejemplo:

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.NAMESPACE=my-namespace" # Establece el espacio de nombres para el servicio
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Comportamiento del espacio de nombres"

    Por defecto, todas las pilas de Autoconfiguración escuchan a todos los espacios de nombres. Si quieres restringir una pila a espacios de nombres específicos, puedes establecer la variable de entorno `NAMESPACES` en el servicio `bw-autoconf`:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.7-rc1
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Establece el espacio de nombres para la instancia de BunkerWeb para que el servicio de autoconfiguración pueda detectarla
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # Solo escucha a estos espacios de nombres
    ...
    ```

    Ten en cuenta que la variable de entorno `NAMESPACES` es una lista de espacios de nombres separados por espacios.

!!! warning "Especificaciones del espacio de nombres"

    Solo puede haber **una base de datos** y **un Programador** por espacio de nombres. Si intentas crear múltiples bases de datos o Programadores en el mismo espacio de nombres, las configuraciones terminarán en conflicto entre sí.

    El Programador no necesita la etiqueta `NAMESPACE` para funcionar correctamente. Solo necesitará que la configuración `DATABASE_URI` esté correctamente configurada para que pueda acceder a la misma base de datos que el servicio de autoconfiguración.

## Kubernetes

<figure markdown>
  ![Descripción general](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Integración con Kubernetes</figcaption>
</figure>

Para automatizar la configuración de las instancias de BunkerWeb en un entorno de Kubernetes,
el servicio de autoconfiguración sirve como un [controlador de Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/).
Configura las instancias de BunkerWeb basándose en los [recursos de Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
y también supervisa otros objetos de Kubernetes, como [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/),
para configuraciones personalizadas.

!!! info "Reconciliación de ConfigMap"
    - El controlador de Ingress solo gestiona las ConfigMap que tienen la anotación `bunkerweb.io/CONFIG_TYPE`.
    - Añade `bunkerweb.io/CONFIG_SITE` si quieres limitar la configuración a un único servicio (el nombre del servidor debe existir);
      déjala sin definir para aplicarla globalmente.
    - Al quitar la anotación o eliminar la ConfigMap, se elimina la configuración personalizada correspondiente en BunkerWeb.

Para una configuración óptima, se recomienda definir BunkerWeb como un **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)**, lo que asegura que se cree un pod en todos los nodos, mientras que la **autoconfiguración y el programador** se definen como un **único [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) replicado**.

Dada la presencia de múltiples instancias de BunkerWeb, es necesario establecer un almacén de datos compartido implementado como un servicio de [Redis](https://redis.io/) o [Valkey](https://valkey.io/). Este servicio será utilizado por las instancias para almacenar en caché y compartir datos entre ellas. Se puede encontrar más información sobre la configuración de Redis/Valkey [aquí](features.md#redis).

!!! info "Backend de la base de datos"
    Ten en cuenta que nuestras instrucciones asumen que estás utilizando MariaDB como el backend de base de datos predeterminado, según lo configurado por el ajuste `DATABASE_URI`. Sin embargo, entendemos que puedes preferir utilizar backends alternativos para tu integración con Docker. Si ese es el caso, ten la seguridad de que otros backends de bases de datos también son posibles. Consulta los archivos docker-compose en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) del repositorio para obtener más información.

    La configuración de backends de bases de datos en clúster está fuera del alcance de esta documentación.

Asegúrate de que los servicios de autoconfiguración tengan acceso a la API de Kubernetes. Se recomienda utilizar la [autorización RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) para este propósito.

!!! warning "CA personalizada para la API de Kubernetes"
    Si usas una CA personalizada para tu API de Kubernetes, puedes montar un archivo de paquete que contenga tus certificados intermedios y raíz en el controlador de ingress y establecer el valor del entorno `KUBERNETES_SSL_CA_CERT` en la ruta del paquete dentro del contenedor. Alternativamente, aunque no se recomienda, puedes deshabilitar la verificación de certificados estableciendo la variable de entorno `KUBERNETES_SSL_VERIFY` del controlador de ingress en `no` (el valor predeterminado es `yes`).

Además, **es crucial establecer la variable de entorno `KUBERNETES_MODE` en `yes` cuando se utiliza la integración con Kubernetes**. Esta variable es obligatoria para un funcionamiento correcto.

### Métodos de instalación

#### Usando el chart de Helm (recomendado)

La forma recomendada de instalar Kubernetes es usar el chart de Helm disponible en `https://repo.bunkerweb.io/charts`:

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

Luego puedes usar el chart de Helm de bunkerweb de ese repositorio:

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

La lista completa de valores se encuentra en el archivo [charts/bunkerweb/values.yaml](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) del repositorio [bunkerity/bunkerweb-helm](https://github.com/bunkerity/bunkerweb-helm).

#### Sidecar Container + Helm

This documentation explains how to deploy BunkerWeb as a sidecar to protect your Kubernetes applications. In this architecture, each application has its own BunkerWeb container acting as a security reverse proxy.

##### Architecture

```mermaid
flowchart TB

  %% ---------- Estilos ----------
  classDef scheduler     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef podContainer  fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:6 3,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;

  %% ---------- Arriba: Programador ----------
  SCHED["Programador de BunkerWeb (centralizado)<br/>+ IU + MariaDB + Redis"]:::scheduler

  %% ---------- Grupo de Pods ----------
  subgraph PODS["Pods"]
    %% Pod de aplicación 1 ----------
    subgraph POD1["Pod de aplicación"]
      BW1["BunkerWeb"]:::component
      APP1["Aplicación<br/>(puerto 80)"]:::component
      BW1 -->|solicitudes legítimas| APP1
    end
    class POD1 podContainer

    %% Pod de aplicación 2 ----------
    subgraph POD2["Pod de aplicación"]
      BW2["BunkerWeb"]:::component
      APP2["Aplicación<br/>(puerto XX)"]:::component
      BW2 -->|solicitudes legítimas| APP2
    end
    class POD2 podContainer
  end

  %% ---------- Balanceador de carga (inferior) ----------
  LB["Balanceador de carga"]:::lb

  %% El programador controla las instancias de BunkerWeb (API)---
  %% The Scheduler controls the BunkerWeb instances (API)
  SCHED -->|API 5000| BW1
  SCHED -->|API 5000| BW2
  %% El balanceador de carga envía tráfico a BunkerWeb
  %% The load balancer sends traffic to BunkerWeb
  LB -->|HTTP/HTTPS| BW1
  LB -->|HTTP/HTTPS| BW2
  %% ---------- Auxiliar de diseño (oculto) ----------
  %% Coloca el balanceador de carga debajo del grupo PODS
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

#### Archivos YAML completos

En lugar de usar el chart de Helm, también puedes usar las plantillas YAML dentro de la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) del repositorio de GitHub. Ten en cuenta que recomendamos encarecidamente usar el chart de Helm en su lugar.

### Recursos de Ingress

Una vez que la pila de BunkerWeb para Kubernetes esté configurada y operativa con éxito (consulta los registros de autoconfiguración para obtener información detallada), puedes proceder a desplegar aplicaciones web dentro del clúster y declarar tu recurso de Ingress.

Es importante tener en cuenta que las configuraciones de BunkerWeb deben especificarse como anotaciones para el recurso de Ingress. Para la parte del dominio, utiliza el valor especial **`bunkerweb.io`**. Al incluir las anotaciones apropiadas, puedes configurar BunkerWeb en consecuencia para el recurso de Ingress.

!!! tip "Ignorar anotaciones ruidosas"
    Cuando algunas anotaciones no deben impactar autoconf, establece `KUBERNETES_IGNORE_ANNOTATIONS` en el despliegue del controlador. Proporciona una lista de claves de anotaciones separadas por espacios o comas (por ejemplo `bunkerweb.io/EXTRA_FOO`) o solo el sufijo (`EXTRA_FOO`). Las anotaciones coincidentes se eliminan de las configuraciones derivadas del ingress, y los pods que las llevan se omiten por completo durante el descubrimiento de instancias.

!!! info "Soporte TLS"
    El controlador de ingress de BunkerWeb es totalmente compatible con certificados HTTPS personalizados utilizando la especificación tls como se muestra en el ejemplo. La configuración de soluciones como `cert-manager` para generar automáticamente secretos tls está fuera del alcance de esta documentación.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # Se aplicará a todos los hosts en este ingress
    bunkerweb.io/MY_SETTING: "value"
    # Solo se aplicará al host www.example.com
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  # TLS es opcional, también puedes usar Let's Encrypt integrado, por ejemplo
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

### Espacios de nombres {#namespaces_1}

A partir de la versión `1.6.0`, las pilas de autoconfiguración de BunkerWeb ahora admiten espacios de nombres. Esta característica te permite gestionar múltiples clústeres de instancias y servicios de BunkerWeb en el mismo clúster de Kubernetes. Para aprovechar los espacios de nombres, simplemente establece el campo de metadatos `namespace` en tus instancias y servicios de BunkerWeb. Aquí tienes un ejemplo:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Establece el espacio de nombres para la instancia de BunkerWeb
...
```

!!! info "Comportamiento del espacio de nombres"

    Por defecto, todas las pilas de Autoconfiguración escuchan a todos los espacios de nombres. Si quieres restringir una pila a espacios de nombres específicos, puedes establecer la variable de entorno `NAMESPACES` en el despliegue de `bunkerweb-controller`:

    ```yaml
    ...
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
      namespace: my-namespace # Establece el espacio de nombres para el Controlador
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
                  value: "my-namespace my-other-namespace" # Solo escucha a estos espacios de nombres
                ...
    ...
    ```

    Ten en cuenta que la variable de entorno `NAMESPACES` es una lista de espacios de nombres separados por espacios.

!!! warning "Especificaciones del espacio de nombres"

    Solo puede haber **una base de datos** y **un Programador** por espacio de nombres. Si intentas crear múltiples bases de datos o Programadores en el mismo espacio de nombres, las configuraciones terminarán en conflicto entre sí.

    El Programador no necesita la anotación `NAMESPACE` para funcionar correctamente. Solo necesitará que la configuración `DATABASE_URI` esté correctamente configurada para que pueda acceder a la misma base de datos que el servicio de autoconfiguración.

### Clase de Ingress

Cuando se instala usando los métodos oficiales de la documentación, BunkerWeb viene con la siguiente definición de `IngressClass`:

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

Para restringir los recursos `Ingress` monitoreados por el controlador de ingress, puedes establecer la variable de entorno `KUBERNETES_INGRESS_CLASS` con el valor `bunkerweb`. Luego, puedes aprovechar la directiva `ingressClassName` en tus definiciones de `Ingress`:

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

### Nombre de dominio personalizado

Si usas un nombre de dominio personalizado para tu clúster de Kubernetes diferente al predeterminado `kubernetes.local`, puedes establecer el valor usando la variable de entorno `KUBERNETES_DOMAIN_NAME` en el contenedor del programador.

### Usar con un controlador de ingress existente

!!! info "Mantener tanto el controlador de ingress existente como BunkerWeb"

    Este es un caso de uso en el que quieres mantener un controlador de ingress existente como el de nginx. El flujo de tráfico típico será: Balanceador de Carga => Controlador de Ingress => BunkerWeb => Aplicación.

#### Instalación del controlador de ingress de nginx

Instala el repositorio de helm de ingress nginx:

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

Instala el controlador de ingress de nginx con los valores predeterminados (puede que no funcione en tu propio clúster sin modificaciones, por favor consulta la [documentación](https://kubernetes.github.io/ingress-nginx/)):

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

Extrae la dirección IP del LB:

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Configura las entradas DNS a la IP del LB (p. ej., subdominio `bunkerweb` para la UI de BW y `myapp` para la aplicación):

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
Address: 1.2.3.4```

**Instalación de BunkerWeb**

Instala el repositorio de helm de BunkerWeb:

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

Crea el archivo `values.yaml`:

```yaml
# Aquí configuraremos los valores necesarios para configurar BunkerWeb detrás de un controlador de ingress existente
# Flujo de tráfico con BW: LB => Controlador de Ingress existente => BunkerWeb => Servicio
# Flujo de tráfico sin BW: LB => Controlador de Ingress existente => Servicio

# Configuraciones globales
settings:
  misc:
    # Reemplaza con tu resolvedor de DNS
    # para obtenerlo: kubectl exec en un pod aleatorio y luego cat /etc/resolv.conf
    # si tienes una IP como servidor de nombres, haz una búsqueda de DNS inversa: nslookup <IP>
    # la mayoría de las veces es coredns.kube-system.svc.cluster.local o kube-dns.kube-system.svc.cluster.local
    dnsResolvers: "kube-dns.kube-system.svc.cluster.local"
  kubernetes:
    # Solo consideramos los recursos de Ingress con ingressClass bunkerweb para evitar conflictos con el controlador de ingress existente
    ingressClass: "bunkerweb"
    # Opcional: puedes elegir el(los) espacio(s) de nombres donde BunkerWeb escuchará los cambios de Ingress/ConfigMap
    # El valor predeterminado (en blanco) es todos los espacios de nombres
    namespaces: ""

# Sobrescribe el tipo de servicio bunkerweb-external a ClusterIP
# Ya que no necesitamos exponerlo al mundo exterior
# Usaremos el controlador de ingress existente para enrutar el tráfico a BunkerWeb
service:
  type: ClusterIP

# Configuraciones de BunkerWeb
bunkerweb:
  tag: 1.6.7~rc1

# Configuraciones del programador
scheduler:
  tag: 1.6.7~rc1
  extraEnvs:
    # Habilita el módulo de IP real para obtener la IP real de los clientes
    - name: USE_REAL_IP
      value: "yes"

# Configuraciones del controlador
controller:
  tag: 1.6.7~rc1

# Configuraciones de la UI
ui:
  tag: 1.6.7~rc1
```

Instala BunkerWeb con valores personalizados:

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

Revisa los registros y espera hasta que todo esté listo.

**Instalación de la Interfaz de Usuario Web**

Configura el siguiente ingress (asumiendo que el controlador de nginx está instalado):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ui-bunkerweb
  # Reemplaza con tu espacio de nombres de BW si es necesario
  namespace: bunkerweb
  annotations:
    # HTTPS es obligatorio para la interfaz de usuario web, incluso si el tráfico es interno
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    # Debemos establecer SNI para que BW pueda servir el vhost correcto
    # Reemplaza con tu dominio
    nginx.ingress.kubernetes.io/proxy-ssl-name: "bunkerweb.example.com"
    nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"
spec:
  # Solo servido por el controlador de nginx y no por BW
  ingressClassName: nginx
  # Descomenta y edita si quieres usar tu propio certificado
  # tls:
  # - hosts:
  #   - bunkerweb.example.com
  #   secretName: tls-secret
  rules:
  # Reemplaza con tu dominio
  - host: bunkerweb.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Creado por el chart de Helm
            name: bunkerweb-external
            port:
              # Usar el puerto HTTPS es obligatorio para la UI
              number: 443
```

Y ahora puedes proceder al asistente de configuración navegando a `https://bunkerweb.example.com/setup`.

**Protegiendo una aplicación existente**

**En primer lugar, deberás ir a los Ajustes globales, seleccionar el plugin SSL y luego deshabilitar la redirección automática de HTTP a HTTPS. Ten en cuenta que solo necesitas hacerlo una vez.**

Supongamos que tienes una aplicación en el espacio de nombres `myapp` que es accesible a través del servicio `myapp-service` en el puerto `5000`.

Necesitarás añadir un nuevo servicio en la interfaz de usuario web y rellenar la información requerida:

- Nombre del servidor: el dominio público de tu aplicación (p. ej., `myapp.example.com`)
- SSL/TLS: tu controlador de ingress se encarga de esa parte, así que no lo habilites en BunkerWeb ya que el tráfico es interno dentro del clúster
- Host del proxy inverso: la URL completa de tu aplicación dentro del clúster (p. ej., `http://myapp-service.myapp.svc.cluster.local:5000`)

Una vez que se haya añadido el nuevo servicio, ahora puedes declarar un recurso de Ingress para ese servicio y enrutarlo al servicio de BunkerWeb en el puerto HTTP:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  # Reemplaza con tu espacio de nombres de BW si es necesario
  namespace: bunkerweb
spec:
  # Solo servido por el controlador de nginx y no por BW
  ingressClassName: nginx
  # Descomenta y edita si quieres usar tu propio certificado
  # tls:
  # - hosts:
  #   - myapp.example.com
  #   secretName: tls-secret
  rules:
  # Reemplaza con tu dominio
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Creado por el chart de Helm
            name: bunkerweb-external
            port:
              number: 80
```

Puedes visitar `http(s)://myapp.example.com`, que ahora está protegido con BunkerWeb 🛡️

## Swarm

<figure markdown>
  ![Descripción general](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Integración con Docker Swarm</figcaption>
</figure>

!!! warning "Obsoleto"
    La integración con Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración con Kubernetes](#kubernetes) en su lugar.

!!! tip "Soporte PRO"
    **Si necesitas soporte para Swarm**, por favor contáctanos en [contact@bunkerity.com](mailto:contact@bunkerity.com) o a través del [formulario de contacto](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Autoconfiguración de Docker"
    La integración con Swarm es similar a la de autoconfiguración de Docker (pero con servicios en lugar de contenedores). Por favor, lee primero la [sección de integración de autoconfiguración de Docker](#docker-autoconf) si es necesario.

Para permitir la configuración automática de las instancias de BunkerWeb, el servicio **autoconf** requiere acceso a la API de Docker. Este servicio escucha los eventos de Docker Swarm, como la creación o eliminación de servicios, y configura sin problemas las **instancias de BunkerWeb** en tiempo real sin ningún tiempo de inactividad. También supervisa otros objetos de Swarm, como los [configs](https://docs.docker.com/engine/swarm/configs/), para configuraciones personalizadas.

Al igual que en la [integración de autoconfiguración de Docker](#docker-autoconf), la configuración de los servicios web se define mediante etiquetas que comienzan con el prefijo **bunkerweb**.

Para una configuración óptima, se recomienda programar el **servicio BunkerWeb** como un ***servicio global*** en todos los nodos, mientras que los **servicios de autoconf, programador y proxy de la API de Docker** deben programarse como ***servicios replicados únicos***. Ten en cuenta que el servicio de proxy de la API de Docker debe programarse en un nodo gestor, a menos que lo configures para usar una API remota (lo que no se cubre en la documentación).

Dado que se están ejecutando múltiples instancias de BunkerWeb, se debe crear un almacén de datos compartido implementado como un servicio de [Redis](https://redis.io/) o [Valkey](https://valkey.io/). Estas instancias utilizarán el servicio Redis/Valkey para almacenar en caché y compartir datos. Se pueden encontrar más detalles sobre la configuración de Redis/Valkey [aquí](features.md#redis).

En cuanto al volumen de la base de datos, la documentación no especifica un enfoque concreto. La elección de una carpeta compartida o un controlador específico para el volumen de la base de datos depende de tu caso de uso particular y se deja como ejercicio para el lector.

!!! info "Backend de la base de datos"
    Ten en cuenta que nuestras instrucciones asumen que estás utilizando MariaDB como el backend de base de datos predeterminado, según lo configurado por el ajuste `DATABASE_URI`. Sin embargo, entendemos que puedes preferir utilizar backends alternativos para tu integración con Docker. Si ese es el caso, ten la seguridad de que otros backends de bases de datos también son posibles. Consulta los archivos docker-compose en la [carpeta misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.7-rc1/misc/integrations) del repositorio para obtener más información.

    La configuración de backends de bases de datos en clúster está fuera del alcance de esta documentación.

Aquí está la plantilla de la pila que puedes desplegar usando `docker stack deploy`:

```yaml
x-bw-env: &bw-env
  # Usamos un ancla para evitar repetir las mismas configuraciones para ambos servicios
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
        - "bunkerweb.INSTANCE=yes" # Etiqueta obligatoria para que el servicio de autoconfiguración identifique la instancia de BunkerWeb

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # No necesitamos especificar la instancia de BunkerWeb aquí, ya que son detectadas automáticamente por el servicio de autoconfiguración
      SERVER_NAME: "" # El nombre del servidor se rellenará con las etiquetas de los servicios
      MULTISITE: "yes" # Configuración obligatoria para la autoconfiguración
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
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
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
      DOCKER_HOST: "tcp://bw-docker:2375" # El socket de Docker
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
    # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
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

!!! info "Configuración obligatoria de Swarm"
    Ten en cuenta que la variable de entorno `SWARM_MODE: "yes"` es obligatoria cuando se utiliza la integración con Swarm.

!!! tip "Omitir servicios etiquetados"
    ¿Necesitas excluir un servicio de Swarm de autoconf? Establece `SWARM_IGNORE_LABELS` en el controlador. Proporciona una lista de claves de etiquetas separadas por espacios o comas (por ejemplo `bunkerweb.SERVER_NAME`) o sufijos (`SERVER_NAME`) y cualquier servicio que lleve esas etiquetas será ignorado durante el descubrimiento.

### Servicios de Swarm

Una vez que la pila de BunkerWeb Swarm esté configurada y en funcionamiento (consulta los registros de autoconfiguración y del programador para obtener más información), podrás desplegar aplicaciones web en el clúster y usar etiquetas para configurar dinámicamente BunkerWeb:

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

### Espacios de nombres {#namespaces_2}

A partir de la versión `1.6.0`, las pilas de Autoconfiguración de BunkerWeb ahora admiten espacios de nombres. Esta característica te permite gestionar múltiples "*clústeres*" de instancias y servicios de BunkerWeb en el mismo host de Docker. Para aprovechar los espacios de nombres, simplemente establece la etiqueta `NAMESPACE` en tus servicios. Aquí tienes un ejemplo:

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
        - "bunkerweb.NAMESPACE=my-namespace" # Establece el espacio de nombres para el servicio
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Comportamiento del espacio de nombres"

    Por defecto, todas las pilas de Autoconfiguración escuchan a todos los espacios de nombres. Si quieres restringir una pila a espacios de nombres específicos, puedes establecer la variable de entorno `NAMESPACES` en el servicio `bw-autoconf`:

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
            - "bunkerweb.NAMESPACE=my-namespace" # Establece el espacio de nombres para la instancia de BunkerWeb
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.7-rc1
        environment:
          NAMESPACES: "my-namespace my-other-namespace" # Solo escucha a estos espacios de nombres
          ...
        deploy:
          placement:
            constraints:
              - "node.role == worker"
    ...
    ```

    Ten en cuenta que la variable de entorno `NAMESPACES` es una lista de espacios de nombres separados por espacios.

!!! warning "Especificaciones del espacio de nombres"

    Solo puede haber **una base de datos** y **un Programador** por espacio de nombres. Si intentas crear múltiples bases de datos o Programadores en el mismo espacio de nombres, las configuraciones terminarán en conflicto entre sí.

    El Programador no necesita la etiqueta `NAMESPACE` para funcionar correctamente. Solo necesitará que la configuración `DATABASE_URI` esté correctamente configurada para que pueda acceder a la misma base de datos que el servicio de autoconfiguración.

## Terraform

### Introducción

El proveedor de Terraform para BunkerWeb le permite administrar sus instancias, servicios y configuraciones de BunkerWeb mediante Infraestructura como Código (IaC). Este proveedor interactúa con la API de BunkerWeb para automatizar el despliegue y la gestión de sus configuraciones de seguridad.

### Requisitos previos

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.12
- Una instancia de BunkerWeb con la API habilitada
- Un token de API o credenciales de autenticación básica

### Instalación

El proveedor está disponible en el [Terraform Registry](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest). Añádalo a su configuración de Terraform:

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

### Configuración

#### Autenticación por Bearer Token (recomendada)

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_token    = var.bunkerweb_token
}
```

#### Autenticación básica

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_username = var.bunkerweb_username
  api_password = var.bunkerweb_password
}
```

### Ejemplos de uso

#### Crear un servicio web

```terraform
resource "bunkerweb_service" "app" {
  server_name = "app.example.com"

  variables = {
    upstream = "10.0.0.12:8080"
    mode     = "production"
  }
}
```

#### Registrar una instancia

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

#### Configurar un parámetro global

```terraform
resource "bunkerweb_global_config_setting" "retry" {
  key   = "retry_limit"
  value = "10"
}
```

#### Banear una dirección IP

```terraform
resource "bunkerweb_ban" "suspicious_ip" {
  ip       = "192.0.2.100"
  reason   = "Multiple failed login attempts"
  duration = 3600  # 1 hora en segundos
}
```

#### Configuración personalizada

```terraform
resource "bunkerweb_config" "custom_rules" {
  service_id = "app.example.com"
  type       = "http"
  name       = "custom-rules.conf"
  content    = file("${path.module}/configs/custom-rules.conf")
}
```

### Recursos disponibles

El proveedor expone los siguientes recursos:

- **bunkerweb_service**: Gestión de servicios web
- **bunkerweb_instance**: Registro y gestión de instancias
- **bunkerweb_global_config_setting**: Configuración global
- **bunkerweb_config**: Configuraciones personalizadas
- **bunkerweb_ban**: Gestión de baneos de IP
- **bunkerweb_plugin**: Instalación y gestión de plugins

### Fuentes de datos

Las fuentes de datos permiten leer información existente:

- **bunkerweb_service**: Leer un servicio existente
- **bunkerweb_global_config**: Leer la configuración global
- **bunkerweb_plugins**: Listar plugins disponibles
- **bunkerweb_cache**: Información de la caché
- **bunkerweb_jobs**: Estado de trabajos programados

### Recursos efímeros

Para operaciones puntuales:

- **bunkerweb_run_jobs**: Desencadenar trabajos bajo demanda
- **bunkerweb_instance_action**: Ejecutar acciones en instancias (reload, stop, etc.)
- **bunkerweb_service_snapshot**: Capturar el estado de un servicio
- **bunkerweb_config_upload**: Carga masiva de configuraciones

### Ejemplo completo

Aquí hay un ejemplo de una infraestructura completa con BunkerWeb:

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

# Configuración global
resource "bunkerweb_global_config_setting" "rate_limit" {
  key   = "rate_limit"
  value = "10r/s"
}

# Servicio principal
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

# Servicio API con configuración diferente
resource "bunkerweb_service" "api" {
  server_name = "api.example.com"

  variables = {
    upstream        = "10.0.1.20:3000"
    mode            = "production"
    use_cors        = "yes"
    cors_allow_origin = "*"
  }
}

# Instancia worker
resource "bunkerweb_instance" "worker1" {
  hostname     = "bw-worker-1.internal"
  name         = "Production Worker 1"
  port         = 8080
  listen_https = true
  https_port   = 8443
  server_name  = "bw-worker-1.internal"
  method       = "api"
}

# Configuración personalizada para el servicio webapp
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

# Banear una IP sospechosa
resource "bunkerweb_ban" "blocked_ip" {
  ip       = "203.0.113.50"
  reason   = "Detected malicious activity"
  duration = 86400  # 24 horas
}

output "webapp_service_id" {
  value = bunkerweb_service.webapp.id
}

output "api_service_id" {
  value = bunkerweb_service.api.id
}
```

### Recursos adicionales

- [Documentación completa del proveedor](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest/docs)
- [Repositorio GitHub](https://github.com/bunkerity/terraform-provider-bunkerweb)
- [Ejemplos de uso](https://github.com/bunkerity/terraform-provider-bunkerweb/tree/main/examples)
- [Documentación de la API de BunkerWeb](https://docs.bunkerweb.io/latest/api/)

### Soporte y contribución

Para reportar errores o sugerir mejoras, visite el [repositorio GitHub del proveedor](https://github.com/bunkerity/terraform-provider-bunkerweb/issues).


## Microsoft Azure

<figure markdown>
  ![Descripción general](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Integración con Azure</figcaption>
</figure>

!!! info "Tamaño de VM recomendado"
    Ten en cuenta al elegir el SKU de la VM. Debes seleccionar un SKU compatible con VM de Gen2 y recomendamos empezar con la serie B2s o Ds2 para un uso óptimo.

Puedes desplegar fácilmente BunkerWeb en tu suscripción de Azure de varias maneras:

- Azure CLI en Cloud Shell
- Plantilla ARM de Azure
- Portal de Azure a través del Marketplace

=== "Cloud Shell"

    Crea un grupo de recursos. Reemplaza el valor `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    Crea una VM con el SKU `Standard_B2s` en la ubicación del grupo de recursos. Reemplaza los valores `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    Comando completo. Reemplaza los valores `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "Plantilla ARM"

    !!! info "Requisito de permisos"
        Para desplegar una plantilla ARM, necesitas acceso de escritura en los recursos que estás desplegando y acceso a todas las operaciones en el tipo de recurso Microsoft.Resources/deployments.
        Para desplegar una máquina virtual, necesitas los permisos Microsoft.Compute/virtualMachines/write y Microsoft.Resources/deployments/*. La operación what-if tiene los mismos requisitos de permisos.

    Despliega la plantilla ARM:

    [![Desplegar en Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    Inicia sesión en el [portal de Azure](https://portal.azure.com){:target="_blank"}.

    Obtén BunkerWeb desde el menú [Crear un recurso](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}.

    También puedes ir a través del [Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"}.

Puedes acceder al asistente de configuración navegando a la URI `https://your-ip-address/setup` de tu máquina virtual.
