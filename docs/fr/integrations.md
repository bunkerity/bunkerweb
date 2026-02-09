# Intégrations

## BunkerWeb Cloud

<figure markdown>
  ![Vue d'ensemble](assets/img/bunkerweb-cloud.png){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

BunkerWeb Cloud est une solution gérée de Web Application Firewall (WAF) et de reverse proxy qui vous permet de sécuriser vos applications web sans installer BunkerWeb dans votre infrastructure. En souscrivant à BunkerWeb Cloud, vous bénéficiez d'une pile BunkerWeb complète hébergée dans le cloud avec des ressources dédiées (8 Go de RAM, 2 CPU **par** instance, répliqué sur 2 instances pour la haute disponibilité, offre Standard).

### Avantages clés

Commandez votre [instance BunkerWeb Cloud](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) et accédez à :

- **Déploiement instantané** : Aucune installation requise dans votre infrastructure
- **Haute disponibilité** : Instances répliquées avec équilibrage de charge automatique
- **Surveillance intégrée** : Accès à Grafana pour la visualisation des journaux et des métriques
- **Scalabilité** : Ressources dédiées adaptées aux charges de travail importantes
- **Sécurité renforcée** : Protection WAF en temps réel contre les menaces web

Si vous êtes intéressé par l'offre BunkerWeb Cloud, n'hésitez pas à [nous contacter](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) afin que nous puissions discuter de vos besoins.

### Vue d'ensemble de l'architecture

#### Architecture simple - Service unique

```mermaid
graph LR
    A[Client] -->|HTTPS| B[exemple.com]
    B -->|Résolution DNS| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Trafic| D[BunkerWeb CloudWAF + Reverse Proxy]
    D -->|HTTPS/HTTP| E[Serveur exemple.comInfrastructure Client]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#e8f5e8,color:#222
```

#### Architecture complexe - Multi-services

```mermaid
graph LR
    A[Clients] -->|HTTPS| B[exemple.comautre-exemple.comun-autre-exemple.com]
    B -->|Résolution DNS| C[Load Balancer54984654.bunkerweb.cloud]
    C -->|Trafic| D[BunkerWeb CloudWAF + Reverse ProxySSL SNI Activé]
    D -->|HTTPS avec SNI| E[Gateway ClientReverse Proxy/LB]
    E -->|Routage interne| F[Service 1]
    E -->|Routage interne| G[Service 2]
    E -->|Routage interne| H[Service N]

    style C fill:#e1f5fe,color:#222
    style D fill:#f3e5f5,color:#222
    style E fill:#fff3e0,color:#222
    style F fill:#e8f5e8,color:#222
    style G fill:#e8f5e8,color:#222
    style H fill:#e8f5e8,color:#222
```

### Configuration initiale

#### 1. Accès à l'interface de gestion

Après avoir souscrit à BunkerWeb Cloud, vous recevrez :

- **URL d'accès à l'UI BunkerWeb** : Interface pour configurer vos services
- **Point de terminaison Load Balancer** : URL unique au format `http://[ID].bunkerweb.cloud`
- **Accès Grafana** : Interface de surveillance et visualisation des métriques
- **Ressources allouées** : 2 instances avec 8 Go de RAM et 2 CPU chacune

#### 2. Première connexion

1. Connectez-vous à l'interface BunkerWeb Cloud
2. Configurez vos services à protéger
3. Accédez à Grafana pour visualiser vos journaux et métriques BunkerWeb

### Configuration DNS

#### Redirection du trafic vers BunkerWeb Cloud

Pour que le trafic de votre domaine soit traité par BunkerWeb Cloud, vous devez configurer vos enregistrements DNS :

**Configuration requise :**

```dns
exemple.com.        IN  CNAME  54984654.bunkerweb.cloud.
www.exemple.com.    IN  CNAME  54984654.bunkerweb.cloud.
```

**Important :** Remplacez `54984654` par votre identifiant de load balancer fourni lors de la souscription.

#### Validation de la configuration

Vérifiez la résolution DNS :

```bash
dig exemple.com
nslookup exemple.com
```

Le résultat doit pointer vers votre point de terminaison BunkerWeb Cloud.

### Configuration du service

#### Service unique

Pour un service simple hébergé sur votre infrastructure :

**Configuration dans l'UI BunkerWeb :**

1. **Server Name** : `exemple.com`
2. **Use Reverse Proxy** : `yes`
3. **Reverse Proxy Host** : `185.87.1.100:443` (IP de votre serveur)

Vous pouvez trouver toutes les options de configuration dans la [Documentation Reverse Proxy](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

#### Multi-services avec SNI

##### Pourquoi activer le SNI ?

Le Server Name Indication (SNI) est **essentiel** lorsque :

- Plusieurs domaines pointent vers la même infrastructure backend
- Votre infrastructure héberge plusieurs services avec des certificats SSL distincts
- Vous utilisez un reverse proxy/gateway côté client

##### Configuration SNI

**Dans l'UI BunkerWeb, pour chaque service :**

```yaml
# Service 1
SERVICE_NAME: exemple-com
SERVER_NAME: exemple.com
REVERSE_PROXY_HOST: https://gateway.interne.domaine.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: exemple.com

# Service 2
SERVICE_NAME: autre-exemple-com
SERVER_NAME: autre-exemple.com
REVERSE_PROXY_HOST: https://gateway.interne.domaine.com
REVERSE_PROXY_PORT: 443
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: autre-exemple.com
```

Vous pouvez trouver toutes les options de configuration dans la [Documentation Reverse Proxy](https://docs.bunkerweb.io/latest/settings/#reverse-proxy)

##### Détails techniques SNI

Le SNI permet à BunkerWeb Cloud de :

1. **Identifier le service cible** lors de la connexion TLS
2. **Transmettre le bon nom de domaine** au backend
3. **Permettre au gateway client** de sélectionner le bon certificat
4. **Router correctement** vers le service approprié

**Sans SNI activé :**

```mermaid
graph LR
    A[Client] --> B[BunkerWeb]
    B --> C["Gateway (certificat par défaut)"]
    C --> D[Erreur SSL]

    style B fill:#f3e5f5,color:#222
    style C fill:#fff3e0,color:#222
    style D fill:#ff4d4d,color:#fff,stroke:#b30000,stroke-width:2px
```

**Avec SNI activé :**

```mermaid
graph LR
    A[Client] --> B[BunkerWeb]
    B --> C["Gateway (certificat spécifique exemple.com)"]
    C --> D[Service Correct]

    style B fill:#f3e5f5,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
```

### Gestion SSL/TLS et SNI

#### Certificats SSL

##### Côté BunkerWeb Cloud

BunkerWeb Cloud gère automatiquement :

- Les certificats Let's Encrypt pour vos domaines
- Le renouvellement automatique
- La configuration TLS optimisée

##### Côté Infrastructure Client

**Recommandations importantes :**

1. **Utilisez HTTPS** pour la communication entre BunkerWeb et vos services
2. **Gérez vos propres certificats** sur votre infrastructure
3. **Configurez correctement le SNI** sur votre gateway/reverse proxy

#### Configuration SNI détaillée

##### Cas d'usage : Infrastructure avec Gateway

Si votre architecture ressemble à :

```mermaid
graph LR
    A[BunkerWeb Cloud] --> B[Gateway Client]
    B --> C[Service 1]
    B --> D[Service 2]
    B --> E[Service 3]

    style A fill:#f3e5f5,color:#222
    style B fill:#fff3e0,color:#222
    style C fill:#e8f5e8,color:#222
    style D fill:#e8f5e8,color:#222
    style E fill:#e8f5e8,color:#222
```

**Configuration requise côté BunkerWeb :**

```yaml
# Configuration pour exemple.com
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: exemple.com
REVERSE_PROXY_SSL_VERIFY: no  # Si certificat auto-signé côté client
REVERSE_PROXY_HEADERS: Host $host

# Configuration pour api.exemple.com
REVERSE_PROXY_SSL_SNI: yes
REVERSE_PROXY_SSL_SNI_NAME: api.exemple.com
REVERSE_PROXY_SSL_VERIFY: no
REVERSE_PROXY_HEADERS: Host $host
```

### Configuration Gateway Client

#### Vue d'ensemble

Lorsque votre architecture utilise un gateway/reverse proxy côté client pour router le trafic vers plusieurs services, une configuration spécifique est nécessaire pour supporter le SNI et assurer une communication sécurisée avec BunkerWeb Cloud.

#### Configurations par technologie

##### Nginx

<details>
<summary>Configuration Nginx</summary>

```nginx
# Configuration pour supporter SNI avec plusieurs services
server {
    listen 443 ssl http2;
    server_name exemple.com;

    ssl_certificate /path/to/exemple.com.crt;
    ssl_certificate_key /path/to/exemple.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # En-têtes de sécurité
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
    server_name api.exemple.com;

    ssl_certificate /path/to/api.exemple.com.crt;
    ssl_certificate_key /path/to/api.exemple.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://api-service:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Configuration spécifique API
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

</details>

##### Traefik

<details>
<summary>Configuration Traefik</summary>

**Avec Docker Compose :**

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
      - --certificatesresolvers.myresolver.acme.email=admin@exemple.com
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
      - "traefik.http.routers.dashboard.rule=Host(`traefik.exemple.com`)"
      - "traefik.http.routers.dashboard.tls.certresolver=myresolver"

  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`exemple.com`)"
      - "traefik.http.routers.service1.entrypoints=websecure"
      - "traefik.http.routers.service1.tls.certresolver=myresolver"
      - "traefik.http.services.service1.loadbalancer.server.port=8080"
      - "traefik.http.routers.service1.middlewares=security-headers"

  api-service:
    image: your-api:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.exemple.com`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=myresolver"
      - "traefik.http.services.api.loadbalancer.server.port=3000"
      - "traefik.http.routers.api.middlewares=security-headers,rate-limit"
```

**Configuration dynamique (dynamic.yml) :**

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
      rule: "Host(`exemple.com`)"
      service: "service1"
      tls:
        certResolver: "myresolver"
      middlewares:
        - "security-headers"

    api:
      rule: "Host(`api.exemple.com`)"
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
<summary>Configuration Apache</summary>

```apache
# Configuration Apache avec SNI
<VirtualHost *:443>
    ServerName exemple.com
    DocumentRoot /var/www/html

    # Configuration SSL
    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLHonorCipherOrder off
    SSLCertificateFile /path/to/exemple.com.crt
    SSLCertificateKeyFile /path/to/exemple.com.key

    # En-têtes de sécurité
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # Configuration reverse proxy
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # En-têtes personnalisés
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    <Proxy *>
        Require all granted
    </Proxy>

    # Logs
    ErrorLog ${APACHE_LOG_DIR}/exemple.com_error.log
    CustomLog ${APACHE_LOG_DIR}/exemple.com_access.log combined
</VirtualHost>

<VirtualHost *:443>
    ServerName api.exemple.com

    SSLEngine on
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    SSLCertificateFile /path/to/api.exemple.com.crt
    SSLCertificateKeyFile /path/to/api.exemple.com.key

    ProxyPass / http://api-service:3000/
    ProxyPassReverse / http://api-service:3000/
    ProxyPreserveHost On

    # Configuration spécifique API
    ProxyTimeout 300
    ProxyBadHeader Ignore

    ErrorLog ${APACHE_LOG_DIR}/api.exemple.com_error.log
    CustomLog ${APACHE_LOG_DIR}/api.exemple.com_access.log combined
</VirtualHost>

# Configuration des modules requis
LoadModule ssl_module modules/mod_ssl.so
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
LoadModule headers_module modules/mod_headers.so
```

</details>

##### HAProxy

<details>
<summary>Configuration HAProxy</summary>

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

    # Configuration SSL
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
    bind *:443 ssl crt /etc/ssl/certs/exemple.com.pem crt /etc/ssl/certs/api.exemple.com.pem

    # En-têtes de sécurité
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff
    http-response set-header X-XSS-Protection "1; mode=block"
    http-response set-header Strict-Transport-Security "max-age=31536000; includeSubDomains"

    # Routage basé sur SNI
    acl is_exemple hdr(host) -i exemple.com
    acl is_api hdr(host) -i api.exemple.com

    use_backend service1_backend if is_exemple
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

# Interface de statistiques (optionnel)
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE
```

</details>

#### Validation de la configuration SSL

Tester la configuration SSL :

```bash
# Test de connectivité SSL
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Vérification des en-têtes
curl -I https://your-domain.com

# Test SNI
curl -H "Host: exemple.com" https://54984654.bunkerweb.cloud
```

#### Bonnes pratiques Gateway

1. **Health Checks** : Configurez des vérifications de santé pour vos services
2. **Load Balancing** : Utilisez plusieurs instances pour la haute disponibilité
3. **Surveillance** : Surveillez les métriques de votre gateway
4. **En-têtes de sécurité** : Ajoutez les en-têtes de sécurité appropriés
5. **Timeouts** : Configurez des timeouts appropriés pour éviter les blocages

### Liste blanche d'IP BunkerWeb Cloud

#### Pourquoi configurer une liste blanche ?

Pour sécuriser davantage votre infrastructure, il est recommandé de configurer une liste blanche des adresses IP de BunkerWeb Cloud côté infrastructure client. Cela garantit que seul le trafic provenant de BunkerWeb Cloud peut atteindre vos services backend.

Nous recommandons de configurer la liste blanche au niveau du pare-feu (iptables ..etc).

#### Adresses IP BunkerWeb Cloud à autoriser

**Liste des adresses IP à autoriser :**

La liste mise à jour est disponible ici : https://repo.bunkerweb.io/cloud/ips

```
# Adresses IP BunkerWeb Cloud
4.233.128.18
20.19.161.132
```

#### Configuration de la liste blanche par technologie

##### Nginx

<details>
<summary>Configuration Nginx</summary>

```nginx
# Dans votre configuration serveur
server {
    listen 443 ssl;
    server_name exemple.com;

    # Liste blanche IP BunkerWeb Cloud
    allow 192.168.1.0/24;
    allow 10.0.0.0/16;
    allow 172.16.0.0/12;
    deny all;

    ssl_certificate /path/to/exemple.com.crt;
    ssl_certificate_key /path/to/exemple.com.key;

    location / {
        proxy_pass http://service1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# Configuration avec module geo pour plus de flexibilité
geo $bunkerweb_ip {
    default 0;
    192.168.1.0/24 1;
    10.0.0.0/16 1;
    172.16.0.0/12 1;
}

server {
    listen 443 ssl;
    server_name exemple.com;

    if ($bunkerweb_ip = 0) {
        return 403;
    }

    # ... reste de la configuration
}
```

</details>

##### Traefik

<details>
<summary>Configuration Traefik</summary>

```yaml
# Configuration dans dynamic.yml
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
    exemple-router:
      rule: "Host(`exemple.com`)"
      service: "exemple-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"

    api-router:
      rule: "Host(`api.exemple.com`)"
      service: "api-service"
      middlewares:
        - "bunkerweb-whitelist"
        - "security-headers"
      tls:
        certResolver: "myresolver"
```

**Avec les labels Docker Compose :**

```yaml
services:
  service1:
    image: your-app:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service1.rule=Host(`exemple.com`)"
      - "traefik.http.routers.service1.middlewares=bunkerweb-whitelist"
      - "traefik.http.middlewares.bunkerweb-whitelist.ipwhitelist.sourcerange=192.168.1.0/24,10.0.0.0/16,172.16.0.0/12"
```

</details>

##### Apache

<details>
<summary>Configuration Apache</summary>

```apache
<VirtualHost *:443>
    ServerName exemple.com

    # Liste blanche IP BunkerWeb Cloud
    <RequireAll>
        Require ip 192.168.1.0/24
        Require ip 10.0.0.0/16
        Require ip 172.16.0.0/12
    </RequireAll>

    SSLEngine on
    SSLCertificateFile /path/to/exemple.com.crt
    SSLCertificateKeyFile /path/to/exemple.com.key

    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Configuration pour les logs d'accès refusés
    LogFormat "%h %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined
    CustomLog logs/access.log combined
    ErrorLog logs/error.log
</VirtualHost>

# Configuration alternative avec mod_authz_core
<VirtualHost *:443>
    ServerName api.exemple.com

    <Directory />
        <RequireAny>
            Require ip 192.168.1.0/24
            Require ip 10.0.0.0/16
            Require ip 172.16.0.0/12
        </RequireAny>
    </Directory>

    # ... reste de la configuration
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>Configuration HAProxy</summary>

```haproxy
# Configuration dans haproxy.cfg
frontend bunkerweb_frontend
    bind *:443 ssl crt /path/to/certificates/

    # ACL pour la liste blanche BunkerWeb Cloud
    acl bunkerweb_ips src 192.168.1.0/24 10.0.0.0/16 172.16.0.0/12

    # Bloquer tout sauf BunkerWeb Cloud
    http-request deny unless bunkerweb_ips

    # En-têtes de sécurité
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff

    # Routage
    acl is_exemple hdr(host) -i exemple.com
    acl is_api hdr(host) -i api.exemple.com

    use_backend app_servers if is_exemple
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

##### Pare-feu Système (iptables)

<details>
<summary>Configuration iptables</summary>

```bash
#!/bin/bash
# Script de configuration iptables pour la liste blanche BunkerWeb Cloud

# Effacer les règles existantes
iptables -F
iptables -X

# Politiques par défaut
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Autoriser loopback
iptables -A INPUT -i lo -j ACCEPT

# Autoriser les connexions établies
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Liste blanche IPs BunkerWeb Cloud pour HTTPS
iptables -A INPUT -p tcp --dport 443 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 10.0.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -s 172.16.0.0/12 -j ACCEPT

# Autoriser HTTP pour Let's Encrypt (optionnel)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# Autoriser SSH (adapter selon vos besoins)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Logs pour débogage
iptables -A INPUT -j LOG --log-prefix "DROPPED: "

# Sauvegarder les règles
iptables-save > /etc/iptables/rules.v4

echo "Configuration iptables appliquée avec succès"
```

</details>

#### Bonnes pratiques Liste Blanche

1. **Surveiller les rejets** : Surveillez les tentatives d'accès bloquées
2. **Mises à jour régulières** : Gardez la liste des IP à jour
3. **Tests réguliers** : Validez que la liste blanche fonctionne correctement
4. **Documentation** : Documentez les changements d'IP
5. **Alertes** : Configurez des alertes pour les changements d'IP BunkerWeb
6. **Sauvegarde** : Gardez une configuration de sauvegarde en cas de problème

### Configuration REAL_IP et Récupération de l'Adresse Client

#### Pourquoi configurer REAL_IP ?

Lorsque vous utilisez BunkerWeb Cloud comme reverse proxy, les adresses IP que vos applications backend voient sont celles de BunkerWeb Cloud, et non celles des clients réels. Pour récupérer les adresses IP réelles des clients, une configuration spécifique est requise.

#### Configuration Côté BunkerWeb Cloud

Dans l'UI BunkerWeb, configurez Real IP :

```yaml
USE_REAL_IP: yes # Défaut est no
REAL_IP_FROM: 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8 # Défaut
REAL_IP_HEADER: X-Forwarded-For # Défaut
REAL_IP_RECURSIVE: yes # Défaut
# Exemple si vous utilisez aussi Cloudflare Proxy devant BunkerWeb
REAL_IP_FROM_URLS: https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/
```

Vous pouvez trouver toutes les options de configuration dans la [Documentation Real Ip](https://docs.bunkerweb.io/latest/settings/#real-ip)

#### Configuration Côté Infrastructure Client

##### Nginx

<details>
<summary>Configuration Nginx pour REAL_IP</summary>

```nginx
# Configurer les adresses IP de confiance (BunkerWeb Cloud)
set_real_ip_from 4.233.128.18/32
set_real_ip_from 20.19.161.132/32

# En-tête à utiliser pour récupérer l'IP réelle
real_ip_header X-Real-IP;

# Alternative avec X-Forwarded-For
# real_ip_header X-Forwarded-For;

server {
    listen 443 ssl http2;
    server_name exemple.com;

    # Configuration SSL
    ssl_certificate /path/to/exemple.com.crt;
    ssl_certificate_key /path/to/exemple.com.key;

    location / {
        proxy_pass http://service1:8080;

        # Transmettre les en-têtes d'IP réelle au backend
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Log avec l'IP client réelle
        access_log /var/log/nginx/access.log combined;
    }
}

# Format de log personnalisé avec IP réelle
log_format real_ip '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent" '
                   'real_ip="$realip_remote_addr"';
```

</details>

##### Apache

<details>
<summary>Configuration Apache pour REAL_IP</summary>

```apache
# Charger le module mod_remoteip
LoadModule remoteip_module modules/mod_remoteip.so

<VirtualHost *:443>
    ServerName exemple.com

    # Configuration SSL
    SSLEngine on
    SSLCertificateFile /path/to/exemple.com.crt
    SSLCertificateKeyFile /path/to/exemple.com.key

    # Configurer les adresses IP de confiance
    RemoteIPHeader X-Real-IP
    RemoteIPTrustedProxy 4.233.128.18/32
    RemoteIPTrustedProxy 20.19.161.132/32

    # Alternative avec X-Forwarded-For
    # RemoteIPHeader X-Forwarded-For

    # Configuration reverse proxy
    ProxyPass / http://service1:8080/
    ProxyPassReverse / http://service1:8080/
    ProxyPreserveHost On

    # Transmettre les en-têtes IP
    ProxyPassReverse / http://service1:8080/
    ProxyPassReverseInterpolateEnv On

    # Logs avec IP réelle
    LogFormat "%a %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined_real_ip
    CustomLog logs/access.log combined_real_ip
    ErrorLog logs/error.log
</VirtualHost>
```

</details>

##### HAProxy

<details>
<summary>Configuration HAProxy pour REAL_IP</summary>

```haproxy
global
    maxconn 4096
    log stdout local0

defaults
    mode http
    option httplog
    option dontlognull
    option forwardfor

    # Format de log avec IP réelle
    log-format "%ci:%cp [%t] %ft %b/%s %Tq/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"

frontend https_frontend
    bind *:443 ssl crt /etc/ssl/certs/

    # Liste blanche IP BunkerWeb Cloud
    acl bunkerweb_ips src 4.233.128.18/32 20.19.161.132/32
    http-request deny unless bunkerweb_ips

    # Capturer l'IP réelle depuis les en-têtes
    capture request header X-Real-IP len 15
    capture request header X-Forwarded-For len 50

    # Routage
    acl is_exemple hdr(host) -i exemple.com
    use_backend app_servers if is_exemple

    default_backend app_servers

backend app_servers
    balance roundrobin

    # Ajouter/préserver les en-têtes d'IP réelle
    http-request set-header X-Original-Forwarded-For %[req.hdr(X-Forwarded-For)]
    http-request set-header X-Client-IP %[req.hdr(X-Real-IP)]

    server app1 service1:8080 check
    server app2 service2:8080 check backup
```

</details>

##### Traefik

<details>
<summary>Configuration Traefik pour REAL_IP</summary>

```yaml
# Configuration dans dynamic.yml
http:
  middlewares:
    real-ip:
      ipWhiteList:
        sourceRange:
          - "4.233.128.18/32"
          - "20.19.161.132/32"
        ipStrategy:
          depth: 2  # Nombre de proxies de confiance
          excludedIPs:
            - "127.0.0.1/32"

  routers:
    exemple-router:
      rule: "Host(`exemple.com`)"
      service: "exemple-service"
      middlewares:
        - "real-ip"
      tls:
        certResolver: "myresolver"

  services:
    exemple-service:
      loadBalancer:
        servers:
          - url: "http://service1:8080"
        passHostHeader: true
```

**Configuration dans traefik.yml (static) :**

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

#### Tests et Validation

##### Vérification de la configuration

```bash
# Test 1: Vérifier les en-têtes reçus
curl -H "X-Real-IP: 203.0.113.1" \
     -H "X-Forwarded-For: 203.0.113.1, 192.168.1.100" \
     https://exemple.com/test-ip

# Test 2: Analyser les logs
tail -f /var/log/nginx/access.log | grep "203.0.113.1"

# Test 3: Test depuis différentes sources
curl -v https://exemple.com/whatismyip
```

#### Bonnes pratiques REAL_IP

1. **Sécurité** : Ne faites confiance qu'aux en-têtes IP provenant de sources connues (BunkerWeb Cloud)
2. **Validation** : Validez toujours les adresses IP reçues dans les en-têtes
3. **Journalisation** : Loguez à la fois l'IP du proxy et l'IP réelle pour le débogage
4. **Fallback** : Ayez toujours une valeur par défaut si les en-têtes sont manquants
5. **Tests** : Testez régulièrement que la détection d'IP fonctionne correctement
6. **Surveillance** : Surveillez les modèles d'IP pour détecter les anomalies

#### Dépannage REAL_IP

##### Problèmes courants

1. **L'IP affichée est toujours celle de BunkerWeb** : Vérifiez la configuration des proxies de confiance
2. **En-têtes manquants** : Vérifiez la configuration côté BunkerWeb Cloud
3. **IPs invalides** : Implémentez une validation stricte des IPs
4. **Logs incorrects** : Vérifiez le format des logs et la configuration du module real_ip

##### Commandes de diagnostic

__Tester la détection d'IP__

```bash
curl -H "X-Real-IP: 1.2.3.4" https://your-domain.com/debug-headers
```

### Surveillance et Observabilité

#### Accès Grafana

Votre instance Grafana gérée vous donne accès à :

##### Métriques disponibles

1. **Vue d'ensemble du trafic**

  - Requêtes par seconde
  - Codes de statut HTTP
  - Géolocalisation des requêtes
2. **Sécurité**

  - Tentatives d'attaques bloquées
  - Types de menaces détectés
  - Règles WAF déclenchées
3. **Métriques de performance**

  - Latence des requêtes
  - Temps de réponse backend
  - Utilisation des ressources

##### Journaux disponibles

1. **Access Logs** : Toutes les requêtes HTTP/HTTPS
2. **Security Logs** : Événements de sécurité et blocages
3. **Error Logs** : Erreurs système et d'application

##### Configuration des alertes

Configurez des alertes Grafana pour :

- Pics de trafic anormaux
- Augmentation des erreurs 5xx
- Détection d'attaques DDoS
- Échecs de santé backend

### Bonnes pratiques

#### Sécurité

1. **Utilisez HTTPS** pour toute communication backend
2. **Implémentez une liste blanche d'IP** si possible
3. **Configurez des timeouts appropriés**
4. **Activez la compression** pour optimiser les performances

#### Performance

1. **Optimisez la configuration du cache**
2. **Utilisez HTTP/2** côté client
3. **Configurez des health checks** pour vos backends
4. **Surveillez les métriques** régulièrement

### Dépannage

#### Problèmes courants

##### 1. Erreur SSL/TLS

**Symptôme :** Erreurs de certificat SSL

**Solutions :**

```bash
# Vérifier la configuration SNI
openssl s_client -connect backend.com:443 -servername exemple.com

# Vérifier les certificats backend
openssl x509 -in certificate.crt -text -noout
```

##### 2. Timeout Backend

**Symptôme :** Erreurs 504 Gateway Timeout

**Solutions :**

- Augmenter `REVERSE_PROXY_CONNECT_TIMEOUT` & `REVERSE_PROXY_SEND_TIMEOUT`
- Vérifier la santé du backend
- Optimiser la performance de l'application

##### 3. Problèmes de routage

**Symptôme :** Mauvais service servi

**Solutions :**

- Vérifier la configuration `SERVER_NAME`
- Valider la configuration SNI
- Vérifier les en-têtes `Host`

#### Commandes de diagnostic

```bash
# Test de connectivité
curl -v https://your-domain.com

# Test avec en-têtes personnalisés
curl -H "Host: exemple.com" -v https://54984654.bunkerweb.cloud

# Vérification DNS
dig +trace exemple.com

# Test SSL
openssl s_client -connect exemple.com:443 -servername exemple.com
```

#### Support Technique

Pour toute assistance technique :

1. **Vérifiez les logs** dans Grafana
2. **Vérifiez la configuration** dans l'UI BunkerWeb
3. **Contactez le support** avec les détails de configuration et les logs d'erreur

## Image tout-en-un (AIO) {#all-in-one-aio-image}

<figure markdown>
  ![Architecture AIO Graph Placeholder](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>Architecture tout-en-un (AIO) BunkerWeb</figcaption>
</figure>

### Déploiement {#deployment}

Pour déployer le conteneur tout-en-un, il vous suffit d'exécuter la commande suivante :

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.8
```

Par défaut, le conteneur expose :

- 8080/tcp pour HTTP
- 8443/tcp pour HTTPS
- 8443/udp pour QUIC
- 7000/tcp pour l'accès à l'interface utilisateur web sans BunkerWeb en façade (non recommandé pour la production)

Un volume nommé (ou un bind mount) est nécessaire pour conserver la base SQLite, le cache et les sauvegardes stockés sous `/data` dans le conteneur :

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.8
    container_name: bunkerweb-aio
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Utilisation d'un dossier local pour les données persistantes"
    Le conteneur tout-en-un exécute ses services en tant qu'**utilisateur non privilégié UID 101 / GID 101**. Cela renforce la sécurité : même si une composante est compromise, elle n'obtient pas les privilèges root (UID/GID 0) sur l'hôte.

    Si vous montez un **dossier local**, assurez-vous que les permissions permettent à cet utilisateur non privilégié d'écrire dedans :

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Ou, si le dossier existe déjà :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Lorsque vous utilisez [Docker en mode rootless](https://docs.docker.com/engine/security/rootless) ou [Podman](https://podman.io/), les UID/GID du conteneur sont remappés. Vérifiez d'abord vos plages `subuid` et `subgid` :

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Par exemple, si la plage commence à **100000**, l'UID/GID effectif sera **100100** (100000 + 100) :

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Ou, si le dossier existe déjà :

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

L'image tout-en-un est livrée avec plusieurs services intégrés, qui peuvent être contrôlés à l'aide de variables d'environnement :

- `SERVICE_UI=yes` (par défaut) - Active le service d'interface utilisateur Web
- `SERVICE_SCHEDULER=yes` (par défaut) - Active le service Scheduler
- `SERVICE_API=no` (par défaut) - Active le service API (plan de contrôle FastAPI)
- `AUTOCONF_MODE=no` (par défaut) - Active le service autoconf
- `USE_REDIS=yes` (par défaut) : active l' [ instance](#redis-integration) Redis intégrée
- `USE_CROWDSEC=no` (par défaut) - [ L'intégration CrowdSec](#crowdsec-integration) est désactivée par défaut
- `HIDE_SERVICE_LOGS=` (optionnel) - Liste de services séparés par des virgules à masquer dans les logs du conteneur. Valeurs acceptées : `api`, `autoconf`, `bunkerweb`, `crowdsec`, `redis`, `scheduler`, `ui`, `nginx.access`, `nginx.error`, `modsec`. Les fichiers sous `/var/log/bunkerweb/<service>.log` continuent d'être alimentés.

### Intégration de l'API

L'image tout-en-un embarque l'API BunkerWeb. Elle est désactivée par défaut et peut être activée en définissant `SERVICE_API=yes`.

!!! warning "Sécurité"
    L'API constitue un plan de contrôle privilégié. Ne l'exposez pas directement à Internet. Conservez-la sur un réseau interne, restreignez les IP sources avec `API_WHITELIST_IPS`, imposez une authentification (`API_TOKEN` ou utilisateurs API + Biscuit) et, idéalement, passez par BunkerWeb en proxy inverse sur un chemin difficile à deviner.

Activation rapide (autonome) — publie le port de l'API ; à réserver aux tests :

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
  bunkerity/bunkerweb-all-in-one:1.6.8
```

Configuration recommandée (derrière BunkerWeb) — ne publiez pas `8888` ; utilisez plutôt un proxy inverse :

```yaml
services:
  bunkerweb-aio:
    image: bunkerity/bunkerweb-all-in-one:1.6.8
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
      api.example.com_REVERSE_PROXY_HOST: "http://127.0.0.1:8888" # Point d'accès API interne

      # Paramètres API
      SERVICE_API: "yes"
      # Définissez des identifiants robustes et autorisez uniquement des IP ou réseaux de confiance (plus de détails ci-dessous)
      API_USERNAME: "changeme"
      API_PASSWORD: "StrongP@ssw0rd"
      API_ROOT_PATH: "/api-<unguessable>" # Doit correspondre à REVERSE_PROXY_URL

      # Nous désactivons l'UI - passez à "yes" pour l'activer
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

Des informations détaillées concernant l'authentification, les permissions (ACL), la limitation de débit, le TLS et les options de configuration sont disponibles dans la [documentation de l'API](api.md).

### Accès à l'assistant d'installation

Par défaut, l'assistant d'installation est lancé automatiquement lorsque vous exécutez le conteneur AIO pour la première fois. Pour y accéder, procédez comme suit :

1. **Démarrez le conteneur AIO** comme [ci-dessus](#deployment), en vous assurant que `SERVICE_UI=yes` (valeur par défaut).
2. **Accédez à l'interface utilisateur** via votre point de terminaison BunkerWeb principal, par exemple `https://your-domain`.

> Suivez les étapes suivantes du guide de [démarrage rapide](quickstart-guide.md#complete-the-setup-wizard) pour configurer l'interface utilisateur Web.

### Intégration Redis {#redis-integration}

L'image **BunkerWeb All-In-One** inclut Redis prêt à l'emploi pour la [persistance des bannissements et des rapports](advanced.md#persistence-of-bans-and-reports). Gardez en tête :

- Le service Redis embarqué ne démarre que si `USE_REDIS=yes` **et** si `REDIS_HOST` reste sur sa valeur par défaut (`127.0.0.1`/`localhost`).
- Il écoute sur l'interface loopback du conteneur ; il est donc accessible depuis les processus du conteneur, mais pas depuis d'autres conteneurs ni l'hôte.
- Ne redéfinissez `REDIS_HOST` que si vous disposez d'un point de terminaison Redis/Valkey externe, autrement l'instance embarquée ne sera pas lancée.
- Pour désactiver Redis complètement, définissez `USE_REDIS=no`.
- Les journaux Redis apparaissent avec le préfixe `[REDIS]` dans les journaux Docker et dans `/var/log/bunkerweb/redis.log`.

### Intégration CrowdSec {#crowdsec-integration}

L'image Docker **tout-en-un** de BunkerWeb est livrée avec CrowdSec entièrement intégré, sans conteneurs supplémentaires ni configuration manuelle requise. Suivez les étapes ci-dessous pour activer, configurer et étendre CrowdSec dans votre déploiement.

Par défaut, CrowdSec est **désactivé**. Pour l'activer, il suffit d'ajouter la `USE_CROWDSEC` variable d'environnement :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.8
```

* Lorsque `USE_CROWDSEC=yes`, le point d'entrée :

    1. **Inscrivez-vous** et **démarrez** l'agent CrowdSec local (via `cscli`).
    2. **Installez ou mettez à niveau** les collections et les analyseurs par défaut.
    3. **Configurez** le `crowdsec-bunkerweb-bouncer/v1.6` videur.

---

#### Collections et analyseurs par défaut

Au premier démarrage (ou après la mise à niveau), les ressources suivantes sont automatiquement installées et maintenues à jour :

| Type           | Nom                                     | But                                                                                                                                                                                                                                                                                                 |
| -------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Collection** | `bunkerity/bunkerweb`                   | Protégez les serveurs Nginx contre un large éventail d'attaques basées sur HTTP, de la force brute aux tentatives d'injection.                                                                                                                                                                      |
| **Collection** | `crowdsecurity/appsec-virtual-patching` | Fournit un ensemble de règles de type WAF mis à jour dynamiquement ciblant les CVE connues, automatiquement corrigé quotidiennement pour protéger les applications Web contre les vulnérabilités nouvellement découvertes.                                                                          |
| **Collection** | `crowdsecurity/appsec-generic-rules`    | Compléments `crowdsecurity/appsec-virtual-patching` avec des heuristiques pour les modèles d'attaque génériques de la couche application, tels que l'énumération, la traversée de chemin et les sondes automatisées, comblant les lacunes là où il n'existe pas encore de règles spécifiques à CVE. |
| **Analyseur**  | `crowdsecurity/geoip-enrich`            | Enrichit les événements avec le contexte GeoIP                                                                                                                                                                                                                                                      |

<details>
<summary><strong>Comment ça marche en interne</strong></summary>

Le script entrypoint appelle :

```bash
cscli hub update
cscli install collection bunkerity/bunkerweb
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

!!! info "Collection absente dans Docker ?"
    Si `cscli collections list` à l'intérieur du conteneur n'affiche toujours pas `bunkerity/bunkerweb`, exécutez `docker exec -it bunkerweb-aio cscli hub update` puis redémarrez le conteneur (`docker restart bunkerweb-aio`) pour rafraîchir le cache local du hub.

---

#### Ajouter des collections supplémentaires

Vous avez besoin d'une couverture supplémentaire ? Définissez `CROWDSEC_EXTRA_COLLECTIONS` à l'aide d'une liste de collections Hubb séparées par des espaces :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/apache2 crowdsecurity/mysql" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.8
```

!!! info "Comment ça marche en interne"
    Le script parcourt chaque nom et installe ou met à jour si nécessaire — aucune intervention manuelle n'est requise.

---

#### Désactiver des analyseurs spécifiques

Si vous souhaitez conserver la configuration par défaut tout en désactivant explicitement un ou plusieurs analyseurs, fournissez une liste séparée par des espaces via `CROWDSEC_DISABLED_PARSERS` :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_DISABLED_PARSERS="crowdsecurity/geoip-enrich foo/bar-parser" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.8
```

Notes :
- La liste est appliquée après l'installation/mise à jour des éléments requis ; seuls les analyseurs indiqués sont supprimés.
- Utilisez les slugs du hub tels qu'affichés par `cscli parsers list` (ex. : `crowdsecurity/geoip-enrich`).

---

#### Basculement AppSec

Les  fonctionnalités [CrowdSec AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs), optimisées par les  collections `appsec-virtual-patching` et `appsec-generic-rules` , sont **activées par défaut**.

Pour **désactiver** toutes les fonctionnalités AppSec (WAF/virtual-patching), définissez :

```bash
-e CROWDSEC_APPSEC_URL=""
```

Cela désactive effectivement le point de terminaison AppSec, de sorte qu'aucune règle n'est appliquée.

---

#### API CrowdSec externe

Si vous exploitez une instance CrowdSec distante, pointez le conteneur vers votre API :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_API="https://crowdsec.example.com:8000" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.8
```

* **L'enregistrement local** est ignoré lorsque n' `CROWDSEC_API` est pas `127.0.0.1` ou `localhost`.
* **AppSec** est désactivé par défaut lors de l'utilisation d'une API externe. Pour l'activer, définissez-le `CROWDSEC_APPSEC_URL` sur le point de terminaison de votre choix.
* L'inscription du videur se produit toujours sur l'API distante.
* Pour réutiliser une clé de videur existante, fournissez-la `CROWDSEC_API_KEY` avec votre jeton pré-généré.

---

!!! tip "Plus d'options"
    Pour une couverture complète de toutes les options CrowdSec (scénarios personnalisés, journaux, dépannage, etc.), consultez la [documentation du plugin BunkerWeb CrowdSec](features.md#crowdsec) ou visitez le [site officiel de CrowdSec](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs).

## Docker

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Intégration Docker</figcaption>
</figure>

L'utilisation de BunkerWeb en tant que [ conteneur Docker](https://www.docker.com/) offre une approche pratique et simple pour tester et utiliser la solution, en particulier si vous êtes déjà familiarisé avec la technologie Docker.

Pour faciliter votre déploiement Docker, nous fournissons des images prédéfinies facilement disponibles sur [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb), prenant en charge plusieurs architectures. Ces images prédéfinies sont optimisées et préparées pour être utilisées sur les architectures suivantes :

- x64 (64 bits)
- x86
- armv8 (ARM 64 bits)
- armv7 (ARM 32 bits)

En accédant à ces images prédéfinies à partir de Docker Hub, vous pouvez rapidement extraire et exécuter BunkerWeb dans votre environnement Docker, éliminant ainsi le besoin de processus de configuration ou d'installation étendus. Cette approche simplifiée vous permet de vous concentrer sur l'exploitation des capacités de BunkerWeb sans complexités inutiles.

Que vous effectuiez des tests, développiez des applications ou déployiez BunkerWeb en production, l'option de conteneurisation Docker offre flexibilité et facilité d'utilisation. L'adoption de cette méthode vous permet de tirer pleinement parti des fonctionnalités de BunkerWeb tout en tirant parti des avantages de la technologie Docker.

```shell
docker pull bunkerity/bunkerweb:1.6.8
```

Les images Docker sont également disponibles sur [les packages GitHub](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) et peuvent être téléchargées à l'aide de l'adresse du `ghcr.io` dépôt :

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.8
```

Les concepts clés de l'intégration Docker sont les suivants :

- **Variables d'environnement**: Configurez facilement BunkerWeb à l'aide de variables d'environnement. Ces variables vous permettent de personnaliser divers aspects du comportement de BunkerWeb, tels que les paramètres réseau, les options de sécurité et d'autres paramètres.
- **Conteneur du Scheduler** : gérez la configuration et exécutez les tâches à l'aide d'un conteneur dédié appelé [Scheduler](concepts.md#scheduler).
- **Réseaux**: Les réseaux Docker jouent un rôle essentiel dans l'intégration de BunkerWeb. Ces réseaux ont deux objectifs principaux : exposer les ports aux clients et se connecter aux services Web en amont. En exposant les ports, BunkerWeb peut accepter les demandes entrantes des clients, leur permettant d'accéder aux services Web protégés. De plus, en se connectant aux services Web en amont, BunkerWeb peut acheminer et gérer efficacement le trafic, offrant ainsi une sécurité et des performances améliorées.

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez SQLite comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, d'autres backends de base de données sont également pris en charge. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/misc/integrations) du dépôt.

### Variables d'environnement

Les paramètres sont transmis au Scheduler à l'aide de variables d'environnement Docker :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.8
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
...
```

!!! info "Liste complète"
    Pour obtenir la liste complète des variables d'environnement, consultez la [section des paramètres](features.md) de la documentation.

!!! tip "Ignorer les conteneurs étiquetés"
    Lorsqu'un conteneur doit être ignoré par autoconf, définissez `DOCKER_IGNORE_LABELS` sur le contrôleur. Fournissez une liste de clés d'étiquettes séparées par des espaces ou des virgules (par exemple `bunkerweb.SERVER_NAME`) ou simplement le suffixe (`SERVER_NAME`). Tout conteneur ou source de configuration personnalisée portant une étiquette correspondante est ignoré lors de la découverte, et l'étiquette est ignorée lors de la traduction des paramètres.

### Utilisation des secrets Docker

Au lieu de transmettre des paramètres sensibles via des variables d'environnement, vous pouvez les stocker en tant que secrets Docker. Pour chaque paramètre que vous souhaitez sécuriser, créez un secret Docker dont le nom correspond à la clé de paramètre (en majuscules). Les scripts d'entrée de BunkerWeb chargent automatiquement les secrets `/run/secrets` et les exportent en tant que variables d'environnement.

Exemple:
```bash
# Create a Docker secret for ADMIN_PASSWORD
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

Montez les secrets lors du déploiement :
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

Cela garantit que les paramètres sensibles sont tenus à l'écart de l'environnement et des journaux.

### Programmateur

Le [Scheduler](concepts.md#scheduler) s'exécute dans son propre conteneur, qui est également disponible sur Docker Hub :

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.8
```

!!! info "Paramètres BunkerWeb"

    Depuis la version `1.6.0`, le conteneur Scheduler est l’endroit où vous définissez les paramètres de BunkerWeb. Le Scheduler pousse ensuite la configuration vers le conteneur BunkerWeb.

    ⚠ **Important**: Tous les paramètres liés à l'API (comme `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME`, `API_WHITELIST_IP`, et `API_TOKEN` si vous l'utilisez) **doivent également être définis dans le conteneur BunkerWeb**. Les paramètres doivent être répliqués dans les deux conteneurs, sinon le conteneur BunkerWeb n'acceptera pas les requêtes API du Scheduler.

    ```yaml
    x-bw-api-env: &bw-api-env
      # Nous utilisons une ancre pour éviter de répéter les mêmes réglages pour les deux conteneurs
      API_HTTP_PORT: "5000" # Valeur par défaut
      API_LISTEN_IP: "0.0.0.0" # Valeur par défaut
      API_SERVER_NAME: "bwapi" # Valeur par défaut
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Adaptez selon votre réseau
      # Jeton optionnel ; si défini, le Scheduler enverra Authorization: Bearer <token>
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        environment:
          # Paramètres API pour le conteneur BunkerWeb
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          # Paramètres API pour le conteneur Scheduler
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # Pour persister le cache et d'autres données comme les sauvegardes
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

Un volume est nécessaire pour stocker la base de données SQLite et les sauvegardes utilisées par le Scheduler :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.8
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Utilisation d'un dossier local pour les données persistantes"
    Le Scheduler s'exécute en tant qu' **utilisateur non privilégié avec UID 101 et GID 101** à l'intérieur du conteneur. Cela renforce la sécurité : en cas d'exploitation d'une vulnérabilité, l'attaquant ne disposera pas des privilèges de root complet (UID/GID 0).

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

### Paramètres du conteneur Scheduler

Le Scheduler est le worker du plan de contrôle qui lit les paramètres, rend les configs et les pousse vers les instances BunkerWeb. Les réglages sont centralisés ici avec leurs valeurs par défaut et acceptées.

#### Sources de configuration et priorité

1. Variables d'environnement (y compris `environment:` Docker/Compose)
2. Secrets dans `/run/secrets/<VAR>` (chargés automatiquement par l'entrypoint)
3. Valeurs par défaut intégrées

#### Référence de configuration (power users)

##### Runtime & sécurité

| Setting                         | Description                                                                       | Valeurs acceptées                          | Défaut                                     |
| ------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------ |
| `HEALTHCHECK_INTERVAL`          | Secondes entre les healthchecks du Scheduler                                      | Secondes entières                          | `30`                                       |
| `RELOAD_MIN_TIMEOUT`            | Secondes minimales entre deux reloads successifs                                  | Secondes entières                          | `5`                                        |
| `DISABLE_CONFIGURATION_TESTING` | Sauter les tests de configuration avant application                               | `yes` ou `no`                              | `no`                                       |
| `IGNORE_FAIL_SENDING_CONFIG`    | Continuer même si certaines instances ne reçoivent pas la config                  | `yes` ou `no`                              | `no`                                       |
| `IGNORE_REGEX_CHECK`            | Ignorer la validation regex des paramètres (partagé avec autoconf)                | `yes` ou `no`                              | `no`                                       |
| `TZ`                            | Fuseau horaire pour les logs du Scheduler, tâches type cron, sauvegardes et dates | Nom de base TZ (ex. `UTC`, `Europe/Paris`) | unset (défaut conteneur, généralement UTC) |

##### Base de données

| Setting                 | Description                                                                                 | Valeurs acceptées      | Défaut                                    |
| ----------------------- | ------------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------- |
| `DATABASE_URI`          | DSN principal de base de données (partagé avec autoconf et les instances)                   | DSN SQLAlchemy         | `sqlite:////var/lib/bunkerweb/db.sqlite3` |
| `DATABASE_URI_READONLY` | DSN optionnel en lecture seule ; le Scheduler bascule en RO si c'est tout ce qui fonctionne | DSN SQLAlchemy ou vide | unset                                     |

##### Logging

| Setting                         | Description                                                            | Valeurs acceptées                               | Défaut                                                                           |
| ------------------------------- | ---------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Niveau de log de base / override                                       | `debug`, `info`, `warning`, `error`, `critical` | `info`                                                                           |
| `LOG_TYPES`                     | Destinations                                                           | `stderr`/`file`/`syslog` séparés par espaces    | `stderr`                                                                         |
| `SCHEDULER_LOG_TO_FILE`         | Activer le log fichier et définir le chemin par défaut                 | `yes` ou `no`                                   | `no`                                                                             |
| `LOG_FILE_PATH`                 | Chemin de log personnalisé (utilisé quand `LOG_TYPES` inclut `file`)   | Chemin de fichier                               | `/var/log/bunkerweb/scheduler.log` avec `SCHEDULER_LOG_TO_FILE=yes`, sinon unset |
| `LOG_SYSLOG_ADDRESS`            | Cible syslog (`udp://host:514`, `tcp://host:514`, ou chemin de socket) | Host:port, hôte préfixé protocole ou socket     | unset                                                                            |
| `LOG_SYSLOG_TAG`                | Ident/tag syslog                                                       | Chaîne                                          | `bw-scheduler`                                                                   |

### Paramètres du conteneur UI

Le conteneur UI respecte aussi `TZ` pour localiser les logs et les tâches planifiées (ex. nettoyages lancés via l'UI).

| Setting | Description                                           | Valeurs acceptées                               | Défaut                                     |
| ------- | ----------------------------------------------------- | ----------------------------------------------- | ------------------------------------------ |
| `TZ`    | Fuseau horaire pour les logs UI et actions planifiées | Nom dans la base TZ (ex. `UTC`, `Europe/Paris`) | unset (défaut conteneur, généralement UTC) |

#### Logging

| Setting                         | Description                                                                               | Valeurs acceptées                               | Défaut                                                      |
| ------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Niveau de base / override                                                                 | `debug`, `info`, `warning`, `error`, `critical` | `info`                                                      |
| `LOG_TYPES`                     | Destinations                                                                              | `stderr`/`file`/`syslog` séparés par espaces    | `stderr`                                                    |
| `LOG_FILE_PATH`                 | Chemin pour le log fichier (utilisé si `LOG_TYPES` inclut `file` ou `CAPTURE_OUTPUT=yes`) | Chemin de fichier                               | `/var/log/bunkerweb/ui.log` quand file/capture, sinon unset |
| `LOG_SYSLOG_ADDRESS`            | Cible syslog (`udp://host:514`, `tcp://host:514`, socket)                                 | Host:port, hôte préfixé protocole ou chemin     | unset                                                       |
| `LOG_SYSLOG_TAG`                | Ident/tag syslog                                                                          | Chaîne                                          | `bw-ui`                                                     |
| `CAPTURE_OUTPUT`                | Envoyer stdout/stderr Gunicorn vers les sorties de log configurées                        | `yes` ou `no`                                   | `no`                                                        |

### Réseau

Par défaut, le conteneur BunkerWeb écoute (à l'intérieur du conteneur) sur **8080/tcp** pour **HTTP**, **8443/tcp** pour **HTTPS** et **8443/udp** pour **QUIC**.

!! avertissement "Ports privilégiés en mode rootless ou lors de l'utilisation de Podman"
    Si vous utilisez [Docker en mode rootless](https://docs.docker.com/engine/security/rootless) et que vous souhaitez rediriger les ports privilégiés (< 1024) tels que 80 et 443 vers BunkerWeb, veuillez vous référer aux prérequis [ici](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    If you are using [Podman](https://podman.io/), you can lower the minimum number for unprivileged ports:
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

La pile BunkerWeb typique lors de l'utilisation de l'intégration Docker contient les conteneurs suivants :

- BunkerWeb (en anglais)
- Programmateur
- Vos services

À des fins de défense en profondeur, nous vous recommandons vivement de créer au moins trois réseaux Docker différents :

- `bw-services`: pour BunkerWeb et vos services web
- `bw-universe`: pour BunkerWeb et le Scheduler
- `bw-db`: pour la base de données (si vous en utilisez une)

Pour sécuriser la communication entre le Scheduler et l'API BunkerWeb, **autorisez les appels d'API**. Utilisez le paramètre `API_WHITELIST_IP` pour spécifier les adresses IP et sous-réseaux autorisés. Pour un niveau de protection supérieur, définissez `API_TOKEN` dans les deux conteneurs ; le Scheduler inclura automatiquement l'en-tête `Authorization: Bearer <token>`.

**Il est fortement recommandé d'utiliser un sous-réseau statique pour le `bw-universe` réseau** afin d'améliorer la sécurité. En mettant en œuvre ces mesures, vous pouvez vous assurer que seules les sources autorisées peuvent accéder à l'API BunkerWeb, réduisant ainsi le risque d'accès non autorisé ou d'activités malveillantes :

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  API_TOKEN: "" # Jeton API optionnel
  # Jeton API optionnel pour l'accès authentifié à l'API
  API_TOKEN: ""

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8
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
    image: bunkerity/bunkerweb-scheduler:1.6.8
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

### Fichier de composition complet

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8
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
    image: bunkerity/bunkerweb-scheduler:1.6.8
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

### Construire à partir de la source

Sinon, si vous préférez une approche plus pratique, vous avez la possibilité de créer l'image Docker directement à partir de la [source](https://github.com/bunkerity/bunkerweb). La création de l'image à partir de la source vous offre un meilleur contrôle et une meilleure personnalisation du processus de déploiement. Cependant, veuillez noter que cette méthode peut prendre un certain temps, en fonction de votre configuration matérielle (vous pouvez prendre un café ☕ si nécessaire).

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
  ![Vue d'ensemble](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Intégration Linux</figcaption>
</figure>

Les distributions Linux prises en charge par BunkerWeb (architectures amd64/x86_64 et arm64/aarch64) comprennent :

- Debian 12 "Rat de bibliothèque"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 42 et 43
- Red Hat Enterprise Linux (RHEL) 8, 9 et 10

### Script d'installation facile

Pour une expérience d'installation simplifiée, BunkerWeb fournit un script d'installation facile qui gère automatiquement l'ensemble du processus d'installation, y compris l'installation de NGINX, la configuration du référentiel et la configuration du service.

#### Démarrage rapide

Pour commencer, téléchargez le script d'installation et sa somme de contrôle, puis vérifiez l'intégrité du script avant de l'exécuter.

```bash
# Download the script and its checksum
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8/install-bunkerweb.sh
curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8/install-bunkerweb.sh.sha256

# Verify the checksum
sha256sum -c install-bunkerweb.sh.sha256

# If the check is successful, run the script
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! danger "Avis de sécurité"
    **Vérifiez toujours l'intégrité du script d'installation avant de l'exécuter.**

    Téléchargez le fichier de somme de contrôle et utilisez un outil comme `sha256sum` pour confirmer que le script n'a pas été modifié ou altéré.

    Si la vérification de la somme de contrôle échoue, **n'exécutez pas le script** — il pourrait être dangereux.

#### Comment ça marche

Le script d'installation facile est un outil puissant conçu pour rationaliser l'installation de BunkerWeb sur un nouveau système Linux. Il automatise les étapes clés suivantes :

1.  **Analyse du système**: détecte votre système d'exploitation et le compare à la liste des distributions prises en charge.
2.  **Personnalisation de l'installation**: en mode interactif, il vous invite à choisir un type d'installation (Tout en un, Manager, Worker, etc.) et à décider d'activer ou non l'assistant de configuration Web.
3.  **Intégrations facultatives**: propose d'installer et de configurer automatiquement le [moteur de sécurité CrowdSec](#crowdsec-integration-with-the-script) ainsi que Redis/Valkey pour le cache et les sessions partagés.
4.  **Gestion des **dépendances : Installe la version correcte de NGINX requise par BunkerWeb à partir de sources officielles et verrouille la version pour éviter les mises à niveau involontaires.
5.  **Installation de BunkerWeb**: Ajoute le référentiel de paquets BunkerWeb, installe les paquets nécessaires et verrouille la version.
6.  **Configuration du service** : Configure et active les `systemd` services correspondant au type d'installation que vous avez choisi.
7.  **Conseils post-installation**: Fournit des étapes suivantes claires pour vous aider à démarrer avec votre nouvelle instance BunkerWeb.

#### Installation interactive

Lorsqu'il est exécuté sans aucune option, le script passe en mode interactif qui vous guide tout au long du processus d'installation. Il vous sera demandé de faire les choix suivants :

1.  **Type d'installation**: sélectionnez les composants que vous souhaitez installer.
    *   **Full Stack (par défaut)**: une installation tout-en-un comprenant BunkerWeb, le Scheduler et l'interface utilisateur Web.
    *   **Manager**: Installe le Scheduler et l'interface utilisateur Web, destinés à gérer un ou plusieurs travailleurs BunkerWeb distants.
    *   **Worker**: Installe uniquement l'instance BunkerWeb, qui peut être gérée par un gestionnaire distant.
    *   **Planificateur uniquement** : installe uniquement le composant Planificateur.
    *   **Interface utilisateur Web uniquement** : installe uniquement le composant Interface utilisateur Web.
2.  **Assistant d'installation**: choisissez d'activer ou non l'assistant de configuration Web. Ceci est fortement recommandé pour les nouveaux utilisateurs.
3.  **Intégration CrowdSec**: choisissez d'installer le moteur de sécurité CrowdSec pour une protection avancée et en temps réel contre les menaces (Full Stack uniquement).
4.  **CrowdSec AppSec**: si vous choisissez d'installer CrowdSec, vous pouvez également activer le composant Application Security (AppSec), qui ajoute des fonctionnalités WAF.
5.  **Redis/Valkey**: active Redis/Valkey pour partager les sessions, métriques et données de sécurité entre nœuds (clustering et équilibrage de charge). Installation locale ou serveur existant. Disponible pour Full Stack et Manager uniquement.
6.  **Service API** : choisissez d'activer le service API BunkerWeb optionnel. Il est désactivé par défaut sur les installations Linux.

!!! info "Installations du gestionnaire et du Scheduler"
    Si vous choisissez le type d'installation **Manager** ou **Scheduler Only**, vous serez également invité à fournir les adresses IP ou les noms d'hôte de vos instances de travail BunkerWeb.

#### Options de ligne de commande

Pour les configurations non interactives ou automatisées, le script peut être contrôlé à l'aide d'indicateurs de ligne de commande :

**Options générales :**

| Option                  | Description                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------------------- |
| `-v, --version VERSION` | Spécifie la version de BunkerWeb à installer (par exemple, `1.6.8`).                                 |
| `-w, --enable-wizard`   | Active l'assistant de configuration.                                                                     |
| `-n, --no-wizard`       | Désactive l'assistant d'installation.                                                                    |
| `--api`, `--enable-api` | Active le service API (FastAPI) systemd (désactivé par défaut).                                          |
| `--no-api`              | Désactive explicitement le service API.                                                                  |
| `-y, --yes`             | S'exécute en mode non interactif en utilisant les réponses par défaut pour toutes les invites.           |
| `-f, --force`           | Force l'installation à se poursuivre même sur une version du système d'exploitation non prise en charge. |
| `-q, --quiet`           | Installation silencieuse (suppression de la sortie).                                                     |
| `-h, --help`            | Affiche le message d'aide avec toutes les options disponibles.                                           |
| `--dry-run`             | Montrez ce qui serait installé sans le faire.                                                            |

**Types d'installation :**

| Option             | Description                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| `--full`           | Installation complète de la pile (BunkerWeb, Scheduler, UI). Il s'agit de l'option par défaut. |
| `--manager`        | Installe le Scheduler et l'interface utilisateur pour gérer les travailleurs à distance.       |
| `--worker`         | Installe uniquement l'instance BunkerWeb.                                                      |
| `--scheduler-only` | Installe uniquement le composant Scheduler.                                                    |
| `--ui-only`        | Installe uniquement le composant Interface utilisateur Web.                                    |
| `--api-only`       | Installe uniquement le service API (port 8000).                                                |

**Intégrations de sécurité :**

| Option              | Description                                                                   |
| ------------------- | ----------------------------------------------------------------------------- |
| `--crowdsec`        | Installez et configurez le moteur de sécurité CrowdSec.                       |
| `--no-crowdsec`     | Ignorez l'installation de CrowdSec.                                           |
| `--crowdsec-appsec` | Installez CrowdSec avec le composant AppSec (inclut les fonctionnalités WAF). |
| `--redis`           | Installe et configure Redis localement.                                       |
| `--no-redis`        | Ignore l'intégration Redis.                                                   |

**Options avancées :**

| Option                      | Description                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------ |
| `--instances "IP1 IP2"`     | Liste séparée par des espaces des instances BunkerWeb (requise pour les modes gestionnaire/Scheduler). |
| `--manager-ip IPs`          | IPs du gestionnaire/Scheduler à mettre en liste blanche (requis pour worker en mode non-interactif).   |
| `--dns-resolvers "IP1 IP2"` | IPs des résolveurs DNS personnalisés (pour les installations full, manager ou worker).                 |
| `--api-https`               | Activer HTTPS pour la communication API interne (par défaut : HTTP uniquement).                        |
| `--backup-dir PATH`         | Répertoire pour stocker la sauvegarde automatique avant la mise à jour.                                |
| `--no-auto-backup`          | Ignorer la sauvegarde automatique (vous DEVEZ l'avoir fait manuellement).                              |
| `--redis-host HOST`         | Hôte Redis pour un serveur Redis/Valkey existant.                                                      |
| `--redis-port PORT`         | Port Redis pour un serveur Redis/Valkey existant.                                                      |
| `--redis-database DB`       | Numéro de base de données Redis.                                                                       |
| `--redis-username USER`     | Nom d'utilisateur Redis (Redis 6+).                                                                    |
| `--redis-password PASS`     | Mot de passe Redis.                                                                                    |
| `--redis-ssl`               | Activer SSL/TLS pour la connexion Redis.                                                               |
| `--redis-no-ssl`            | Désactiver SSL/TLS pour la connexion Redis.                                                            |
| `--redis-ssl-verify`        | Vérifier le certificat SSL de Redis.                                                                   |
| `--redis-no-ssl-verify`     | Ne pas vérifier le certificat SSL de Redis.                                                            |

**Exemple d'utilisation :**

```bash
# Run in interactive mode (recommended for most users)
sudo ./install-bunkerweb.sh

# Non-interactive installation with defaults (full stack, wizard enabled)
sudo ./install-bunkerweb.sh --yes

# Install a Worker node without the setup wizard
sudo ./install-bunkerweb.sh --worker --no-wizard

# Install a specific version
sudo ./install-bunkerweb.sh --version 1.6.8

# Manager setup with remote worker instances (instances required)
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# Manager avec communication API interne HTTPS
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11" --api-https

# Worker avec résolveurs DNS personnalisés et API interne HTTPS
sudo ./install-bunkerweb.sh --worker --dns-resolvers "1.1.1.1 1.0.0.1" --api-https

# Full installation with CrowdSec and AppSec
sudo ./install-bunkerweb.sh --crowdsec-appsec

# Installation complète avec un serveur Redis existant
sudo ./install-bunkerweb.sh --redis-host redis.example.com --redis-password "your-strong-password"

# Silent non-interactive installation
sudo ./install-bunkerweb.sh --quiet --yes

# Preview installation without executing
sudo ./install-bunkerweb.sh --dry-run

# Error: CrowdSec cannot be used with worker installations
# sudo ./install-bunkerweb.sh --worker --crowdsec  # This will fail

# Error: Instances required for manager in non-interactive mode
# sudo ./install-bunkerweb.sh --manager --yes  # This will fail without --instances
```

!!! warning "Remarques importantes sur la compatibilité des options"

    **CrowdSec Limitations:**

    - Les options CrowdSec (`--crowdsec`, `--crowdsec-appsec`) ne sont compatibles qu'avec le type d'installation `--full` (par défaut)
    - Ils ne peuvent pas être utilisés avec les installations `--manager`, `--worker`, `--scheduler-only`, `--ui-only` ou `--api-only`

    **Limitations Redis :**

    - Les options Redis (`--redis`, `--redis-*`) ne sont compatibles qu'avec `--full` (par défaut) et `--manager`
    - Elles ne peuvent pas être utilisées avec `--worker`, `--scheduler-only`, `--ui-only` ou `--api-only`

    **Disponibilité du service API :**

    - Le service API externe (port 8000) est disponible pour les types d'installation `--full` et `--manager`
    - Il n'est pas disponible pour les installations `--worker`, `--scheduler-only` ou `--ui-only`
    - Utilisez `--api-only` pour une installation dédiée du service API

    **Exigences relatives aux instances :**
    - L `--instances` 'option n'est valable qu'avec `--manager` les types d `--scheduler-only` 'installation et
    - Lors de l'utilisation `--manager` ou `--scheduler-only` avec `--yes` (mode non interactif), l' `--instances` option est obligatoire
    - Format: `--instances "192.168.1.10 192.168.1.11 192.168.1.12"`

    **Interactif vs non interactif :**
    - Le mode interactif (par défaut) vous demandera les valeurs requises manquantes
    - Le mode non interactif (`--yes`) nécessite que toutes les options nécessaires soient fournies via la ligne de commande

#### Intégration de CrowdSec avec le script {#crowdsec-integration-with-the-script}

Si vous choisissez d'installer CrowdSec lors de la configuration interactive, le script automatise entièrement son intégration avec BunkerWeb :

- Il ajoute le dépôt officiel CrowdSec et installe l'agent.
- Il crée un nouveau fichier d'acquisition pour que CrowdSec analyse les journaux de BunkerWeb (`access.log`, `error.log`, et `modsec_audit.log`).
- Il installe les collections essentielles (`bunkerity/bunkerweb`) et les analyseurs syntaxiques (`crowdsecurity/geoip-enrich`).
- Il enregistre un videur pour BunkerWeb et configure automatiquement la clé API dans `/etc/bunkerweb/variables.env`.
- Si vous sélectionnez également le **composant AppSec**, il installe les `appsec-virtual-patching` collections  et `appsec-generic-rules` configure  le point de terminaison AppSec pour BunkerWeb.

Cela permet une intégration transparente et prête à l'emploi pour une prévention puissante des intrusions.

#### Considérations RHEL

!!! warning "Prise en charge des bases de données externes sur les systèmes basés sur RHEL"
    Si vous envisagez d'utiliser une base de données externe (recommandée pour la production), installez le paquet client approprié:

    ```bash
    # Pour MariaDB
    sudo dnf install mariadb

    # Pour MySQL
    sudo dnf install mysql

    # Pour PostgreSQL
    sudo dnf install postgresql
    ```

    Ceci est nécessaire pour que le Scheduler de BunkerWeb puisse se connecter à votre base de données externe.

#### Après l'installation

En fonction de vos choix lors de l'installation :

**Avec l'assistant d'installation activé :**

1. Accédez à l'assistant de configuration à l'adresse suivante : `https://your-server-ip/setup`
2. Suivez la configuration guidée pour configurer votre premier service protégé
3. Configurer les certificats SSL/TLS et d'autres paramètres de sécurité

**Sans assistant d'installation :**

1. Modifier `/etc/bunkerweb/variables.env` pour configurer BunkerWeb manuellement
2. Ajouter les paramètres de votre serveur et les services protégés
3. Redémarrez le Scheduler : `sudo systemctl restart bunkerweb-scheduler`

### Installation à l'aide du gestionnaire de paquets

Veuillez vous assurer que **NGINX 1.28.2 est installé avant d'installer BunkerWeb**. Pour toutes les distributions, à l'exception de Fedora, il est obligatoire d'utiliser des paquets préconstruits à partir du [dépôt officiel NGINX](https://nginx.org/en/linux_packages.html). La compilation de NGINX à partir des sources ou l'utilisation de paquets provenant de différents dépôts ne fonctionnera pas avec les paquets officiels préconstruits de BunkerWeb. Cependant, vous avez la possibilité de construire BunkerWeb à partir des sources.

=== "Debian Bookworm/Trixie"

    La première étape consiste à ajouter le dépôt officiel NGINX :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Vous devriez maintenant pouvoir installer NGINX 1.28.2 :

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.2-1~$(lsb_release -cs)
    ```

    !!! warning "Version testing/dev"
        Si vous utilisez la version `testing` ou `dev`, vous devrez ajouter la directive `force-bad-version` à votre fichier `/etc/dpkg/dpkg.cfg` avant d'installer BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Et enfin, installez BunkerWeb 1.6.8 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.8
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `apt upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    La première étape consiste à ajouter le dépôt officiel NGINX :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Vous devriez maintenant pouvoir installer NGINX 1.28.2 :

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.2-1~$(lsb_release -cs)
    ```

    !!! warning "Version testing/dev"
        Si vous utilisez la version `testing` ou `dev`, vous devrez ajouter la directive `force-bad-version` à votre fichier `/etc/dpkg/dpkg.cfg` avant d'installer BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Et enfin, installez BunkerWeb 1.6.8 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.8
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `apt upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora Update Testing"
        Si vous ne trouvez pas la version de NGINX répertoriée dans le dépôt stable, vous pouvez activer le dépôt `updates-testing` :

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora fournit déjà NGINX 1.28.1, que nous prenons en charge

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.1
    ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Et enfin, installez BunkerWeb 1.6.8 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf makecache && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.8
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `dnf upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    La première étape consiste à ajouter le dépôt officiel NGINX. Créez le fichier suivant dans /etc/yum.repos.d/nginx.repo :

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

    Vous devriez maintenant pouvoir installer NGINX 1.28.2 :

    ```shell
    sudo dnf install --allowerasing nginx-1.28.2
    ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Enfin, installez BunkerWeb 1.6.8 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.8
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `dnf upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### Configuration et service

La configuration manuelle de BunkerWeb se fait en éditant le `/etc/bunkerweb/variables.env` fichier :

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

Une fois installé, BunkerWeb est livré avec trois services `bunkerweb`, `bunkerweb-scheduler` et `bunkerweb-ui` que vous pouvez gérer à l'aide `systemctl`de .

Si vous modifiez manuellement la configuration de BunkerWeb à l'aide `/etc/bunkerweb/variables.env` d'un redémarrage du `bunkerweb-scheduler` service, il suffira de générer et de recharger la configuration sans aucun temps d'arrêt. Mais selon le cas (par exemple, en changeant de port d'écoute), vous devrez peut-être redémarrer le `bunkerweb` service.

### Haute disponibilité

Le Scheduler peut être détaché de l'instance BunkerWeb pour fournir une haute disponibilité. Dans ce cas, le Scheduler sera installé sur un serveur séparé et pourra gérer plusieurs instances BunkerWeb.

#### Manager

Pour installer uniquement le Scheduler sur un serveur, vous pouvez exporter les variables suivantes avant d'exécuter l'installation de BunkerWeb :

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

Vous pouvez également exporter les variables suivantes pour activer uniquement le Scheduler :

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

#### Worker

Sur un autre serveur, pour installer uniquement BunkerWeb, vous pouvez exporter les variables suivantes avant d'exécuter l'installation de BunkerWeb :

```shell
export WORKER_MODE=yes
```

Alternativement, vous pouvez également exporter les variables suivantes pour activer uniquement BunkerWeb :

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

#### Interface utilisateur Web

L'interface utilisateur Web peut être installée sur un serveur séparé pour fournir une interface dédiée à la gestion des instances BunkerWeb. Pour installer uniquement l'interface utilisateur Web, vous pouvez exporter les variables suivantes avant d'exécuter l'installation de BunkerWeb :

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

## Docker autoconf

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Intégration de Docker autoconf</figcaption>
</figure>

!!! info "Intégration Docker"
    L'intégration de Docker autoconf est une "évolution" de celle de Docker. Veuillez d'abord lire la section sur l' [intégration Docker](#docker) si nécessaire.

Une autre approche est disponible pour résoudre l'inconvénient de recréer le conteneur chaque fois qu'il y a une mise à jour. En utilisant une autre image appelée **autoconf**, vous pouvez automatiser la reconfiguration en temps réel de BunkerWeb sans avoir besoin de recréer des conteneurs.

Pour tirer parti de cette fonctionnalité, au lieu de définir des variables d'environnement pour le conteneur BunkerWeb, vous pouvez ajouter des **étiquettes** à vos conteneurs d'application Web. L'image **autoconf** écoutera alors les événements Docker et gérera de manière transparente les mises à jour de configuration pour BunkerWeb.

Ce processus «* automagique *» simplifie la gestion des configurations BunkerWeb. En ajoutant des étiquettes à vos conteneurs d'applications web, vous pouvez déléguer les tâches de reconfiguration à **autoconf** sans l'intervention manuelle de la recréation de conteneurs. Cela simplifie le processus de mise à jour et améliore la commodité.

En adoptant cette approche, vous pouvez profiter d'une reconfiguration en temps réel de BunkerWeb sans avoir à vous soucier de la recréation de conteneurs, ce qui le rend plus efficace et plus convivial.

!!! info "Mode multisite"
    L'intégration de Docker autoconf implique l'utilisation du **mode multisite**. Pour plus d'informations, reportez-vous à la [section multisite](concepts.md#multisite-mode) de la documentation.

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez MariaDB comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, nous comprenons que vous préférerez peut-être utiliser d'autres backends pour votre intégration Docker. Si c'est le cas, soyez assuré que d'autres backends de base de données sont toujours possibles. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/misc/integrations) du dépôt.

Pour activer les mises à jour automatiques de la configuration, incluez un conteneur supplémentaire appelé `bw-autoconf` dans la pile. Ce conteneur héberge le service autoconf, qui gère les modifications de configuration dynamiques pour BunkerWeb.

Pour prendre en charge cette fonctionnalité, utilisez un "vrai" backend de base de données dédié (par exemple, MariaDB, MySQL ou PostgreSQL) pour le stockage de configuration synchronisé. En intégrant `bw-autoconf` un backend de base de données approprié, vous établissez l'infrastructure pour une gestion automatisée de la configuration sans faille dans BunkerWeb.

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both containers
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8
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
    image: bunkerity/bunkerweb-scheduler:1.6.8
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
    image: bunkerity/bunkerweb-autoconf:1.6.8
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

!!! info "Base de données dans le `bw-db` réseau"
    Le conteneur de base de données n'est intentionnellement pas inclus dans le `bw-universe` réseau. Il est utilisé par les `bw-autoconf` `bw-scheduler` conteneurs et plutôt que directement par BunkerWeb. Par conséquent, le conteneur de base de données fait partie du `bw-db` réseau, ce qui renforce la sécurité en rendant l'accès externe à la base de données plus difficile. **Ce choix de conception délibéré permet de protéger la base de données et de renforcer la perspective de sécurité globale du système**.

!!! warning "Utilisation de Docker en mode rootless"
    Si vous utilisez [Docker en mode rootless](https://docs.docker.com/engine/security/rootless), vous devrez remplacer le support du socket docker par la valeur suivante : `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Paramètres du conteneur Autoconf

Le contrôleur `bw-autoconf` surveille votre orchestrateur et écrit les changements dans la base de données partagée.

#### Sources de configuration et priorité

1. Variables d'environnement (y compris `environment:` Docker/Compose)
2. Secrets dans `/run/secrets/<VAR>` (chargés automatiquement par l'entrypoint)
3. Valeurs par défaut intégrées

#### Référence de configuration (power users)

##### Mode & runtime

| Setting                   | Description                                                     | Valeurs acceptées                   | Défaut                                |
| ------------------------- | --------------------------------------------------------------- | ----------------------------------- | ------------------------------------- |
| `AUTOCONF_MODE`           | Activer le contrôleur autoconf                                  | `yes` ou `no`                       | `no`                                  |
| `SWARM_MODE`              | Surveiller les services Swarm au lieu des conteneurs Docker     | `yes` ou `no`                       | `no`                                  |
| `KUBERNETES_MODE`         | Surveiller les ingress/pods Kubernetes au lieu de Docker        | `yes` ou `no`                       | `no`                                  |
| `KUBERNETES_GATEWAY_MODE` | Utiliser le contrôleur Gateway API pour Kubernetes              | `yes` ou `no`                       | `no`                                  |
| `DOCKER_HOST`             | Socket Docker / URL API distante                                | ex. `unix:///var/run/docker.sock`   | `unix:///var/run/docker.sock`         |
| `WAIT_RETRY_INTERVAL`     | Secondes entre les vérifications de disponibilité des instances | Secondes entières                   | `5`                                   |
| `LOG_SYSLOG_TAG`          | Tag syslog pour les logs autoconf                               | Chaîne                              | `bw-autoconf`                         |
| `TZ`                      | Fuseau horaire pour les logs autoconf et les horodatages        | Nom de base TZ (ex. `Europe/Paris`) | unset (défaut conteneur, souvent UTC) |

##### Base de données & validation

| Setting                 | Description                                                                             | Valeurs acceptées      | Défaut                                    |
| ----------------------- | --------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------- |
| `DATABASE_URI`          | DSN principal de base de données (doit correspondre à la BD du Scheduler)               | DSN SQLAlchemy         | `sqlite:////var/lib/bunkerweb/db.sqlite3` |
| `DATABASE_URI_READONLY` | DSN optionnel en lecture seule ; autoconf bascule en RO si c'est tout ce qui fonctionne | DSN SQLAlchemy ou vide | unset                                     |
| `IGNORE_REGEX_CHECK`    | Ignorer la validation regex pour les paramètres issus des labels/annotations            | `yes` ou `no`          | `no`                                      |

##### Logging

| Setting                         | Description                                                  | Valeurs acceptées                               | Défaut                                             |
| ------------------------------- | ------------------------------------------------------------ | ----------------------------------------------- | -------------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Niveau de log de base / override                             | `debug`, `info`, `warning`, `error`, `critical` | `info`                                             |
| `LOG_TYPES`                     | Destinations                                                 | `stderr`/`file`/`syslog` séparés par espaces    | `stderr`                                           |
| `LOG_FILE_PATH`                 | Chemin pour le log fichier (quand `LOG_TYPES` inclut `file`) | Chemin de fichier                               | unset (définissez le vôtre si vous activez `file`) |
| `LOG_SYSLOG_ADDRESS`            | Cible syslog (`udp://host:514`, `tcp://host:514`, socket)    | Host:port, hôte préfixé protocole ou chemin     | unset                                              |
| `LOG_SYSLOG_TAG`                | Ident/tag syslog                                             | Chaîne                                          | `bw-autoconf`                                      |

##### Portée & filtres de découverte

| Setting                         | Description                                                                    | Valeurs acceptées                                 | Défaut |
| ------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------- | ------ |
| `NAMESPACES`                    | Liste d'espaces/ projets gérés (séparés par espaces) ; unset = tous            | Chaînes séparées par espaces                      | unset  |
| `DOCKER_IGNORE_LABELS`          | Ignorer des conteneurs/labels lors de la collecte d'instances/services/configs | Clés complètes ou suffixes séparés espace/virgule | unset  |
| `SWARM_IGNORE_LABELS`           | Ignorer les services/configs Swarm avec labels correspondants                  | Clés complètes ou suffixes séparés espace/virgule | unset  |
| `KUBERNETES_IGNORE_ANNOTATIONS` | Ignorer des annotations d'ingress/pod pendant la découverte                    | Clés complètes ou suffixes séparés espace/virgule | unset  |

##### Spécifique Kubernetes

| Setting                                 | Description                                                                                          | Valeurs acceptées                                  | Défaut          |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------- | --------------- |
| `KUBERNETES_VERIFY_SSL`                 | Vérifier le TLS de l'API Kubernetes                                                                  | `yes` ou `no`                                      | `yes`           |
| `KUBERNETES_SSL_CA_CERT`                | Chemin vers un bundle CA personnalisé pour l'API Kubernetes                                          | Chemin de fichier                                  | unset           |
| `USE_KUBERNETES_FQDN`                   | Utiliser `<pod>.<ns>.pod.<domain>` plutôt que l'IP du Pod comme hostname d'instance                  | `yes` ou `no`                                      | `yes`           |
| `KUBERNETES_INGRESS_CLASS`              | Ne traiter que les ingress avec cette classe                                                         | Chaîne                                             | unset (toutes)  |
| `KUBERNETES_GATEWAY_MODE`               | Utiliser le contrôleur Gateway API au lieu des Ingress                                               | `yes` ou `no`                                      | `no`            |
| `KUBERNETES_GATEWAY_CLASS`              | Ne traiter que les Gateways avec cette classe                                                        | Chaîne                                             | unset (toutes)  |
| `KUBERNETES_GATEWAY_API_VERSION`        | Version de l'API Gateway à utiliser (repli automatique si absente)                                   | `v1`, `v1beta1`, `v1beta2`, `v1alpha2`, `v1alpha1` | `v1`            |
| `KUBERNETES_DOMAIN_NAME`                | Suffixe de domaine du cluster lors de la construction des hôtes upstream                             | Chaîne                                             | `cluster.local` |
| `KUBERNETES_SERVICE_PROTOCOL`           | Schéma utilisé pour les hôtes de reverse proxy générés                                               | `http` ou `https`                                  | `http`          |
| `BUNKERWEB_SERVICE_NAME`                | Nom du Service lu lors du patch du statut Ingress/Gateway avec l'adresse du load balancer            | Chaîne                                             | `bunkerweb`     |
| `BUNKERWEB_NAMESPACE`                   | Namespace de ce Service                                                                              | Chaîne                                             | `bunkerweb`     |
| `KUBERNETES_REVERSE_PROXY_SUFFIX_START` | Index de départ pour `REVERSE_PROXY_HOST_n`/`REVERSE_PROXY_URL_n` générés sur les ingress multi-path | Entier (>=0)                                       | `1`             |

### Les services d'Autoconf

Une fois la pile configurée, vous pourrez créer le conteneur de l'application web et ajouter les paramètres sous forme d'étiquettes à l'aide du préfixe "bunkerweb." afin de configurer automatiquement BunkerWeb :

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

### Espaces de noms {#namespaces}

À partir de la version `1.6.0`, les piles Autoconf de BunkerWeb supportent désormais les espaces de noms. Cette fonctionnalité vous permet de gérer plusieurs «* clusters *» d'instances et de services BunkerWeb sur le même hôte Docker. Pour tirer parti des espaces de noms, il vous suffit de définir l' `NAMESPACE` étiquette sur vos services. Voici un exemple :

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

!!! info "Comportement de l'espace de nommage"

    Par défaut, toutes les piles Autoconf écoutent tous les espaces de noms. Si vous souhaitez restreindre une pile à des espaces de noms spécifiques, vous pouvez définir la variable d'environnement `NAMESPACES` dans le service `bw-autoconf` :

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Définir l'espace de noms pour l'instance BunkerWeb afin que le service autoconf puisse la détecter
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.8
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # Écouter uniquement ces espaces de noms
    ...
    ```

    Gardez à l'esprit que la variable d'environnement `NAMESPACES` est une liste d'espaces de noms séparés par des espaces.

!!! warning "Spécifications de l'espace de nommage"

    Il ne peut y avoir **qu'une seule base de données** et **un seul Scheduler** par espace de noms. Si vous tentez de créer plusieurs bases de données ou plusieurs Schedulers dans le même espace de noms, les configurations entreront en conflit.

    Le Scheduler n'a pas besoin de l'étiquette `NAMESPACE` pour fonctionner correctement. Il a seulement besoin que le paramètre `DATABASE_URI` soit correctement configuré afin qu'il puisse accéder à la même base de données que le service autoconf.

## Kubernetes

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Intégration Kubernetes</figcaption>
</figure>

Pour automatiser la configuration des instances BunkerWeb dans un environnement Kubernetes,
le service autoconf sert de [contrôleur d'entrée](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/) ou de [contrôleur Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/).
Il configure les instances BunkerWeb en fonction des [ressources d'entrée](https://kubernetes.io/docs/concepts/services-networking/ingress/)
et surveille également d'autres objets Kubernetes, tels que [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/), pour des configurations personnalisées.

!!! example "Mode Gateway API"
    Le mode Gateway API est actuellement en **bêta**.

    Assurez-vous que les CRD de la Gateway API sont installées dans le cluster (voir le [guide d'installation de la Gateway API](https://gateway-api.sigs.k8s.io/guides/getting-started/#installing-gateway-api)).

    Si vous utilisez la Gateway API Kubernetes, définissez `KUBERNETES_MODE=yes` et `KUBERNETES_GATEWAY_MODE=yes`.

    Le contrôleur surveille les ressources `Gateway`, `HTTPRoute`, `TLSRoute`, `TCPRoute` et `UDPRoute` au lieu des objets `Ingress`. Vous pouvez limiter ce qui est traité avec `KUBERNETES_GATEWAY_CLASS` et choisir `KUBERNETES_GATEWAY_API_VERSION` (`v1`, `v1beta1`, `v1beta2`, `v1alpha2` ou `v1alpha1`).

    Si votre Service ne s'appelle pas `bunkerweb`, définissez `BUNKERWEB_SERVICE_NAME` pour que le patch de statut lise le bon Service.

!!! info "Synchronisation des ConfigMap"
    - Le contrôleur d'entrée ne gère que les ConfigMap portant l'annotation `bunkerweb.io/CONFIG_TYPE`.
    - Ajoutez `bunkerweb.io/CONFIG_SITE` pour restreindre la configuration à un service (le nom de serveur doit déjà exister);
      laissez l'annotation vide pour qu'elle s'applique globalement.
    - Supprimer l'annotation ou la ConfigMap retire la configuration personnalisée correspondante dans BunkerWeb.

Pour une configuration optimale, il est recommandé de définir BunkerWeb en tant que **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)**, ce qui garantit qu'un pod est créé sur tous les nœuds, tandis que l'**autoconf et le scheduler** sont définis comme  un **seul déploiement[ répliqué](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)**.

Compte tenu de la présence de plusieurs instances BunkerWeb, il est nécessaire d'établir un magasin de données partagé implémenté en tant que [ service Redis](https://redis.io/) ou [Valkey](https://valkey.io/). Ce service sera utilisé par les instances pour mettre en cache et partager des données entre elles. Vous trouverez de plus amples informations sur les paramètres Redis/Valkey [ici](features.md#redis).

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez MariaDB comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, nous comprenons que vous préférerez peut-être utiliser d'autres backends pour votre intégration Docker. Si c'est le cas, soyez assuré que d'autres backends de base de données sont toujours possibles. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/misc/integrations) du dépôt.

      La configuration des backends de base de données en cluster est hors du périmètre de cette documentation.

Assurez-vous que les services autoconf ont accès à l'API Kubernetes. Il est recommandé d'utiliser l' [autorisation RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) à cette fin.

!!! warning "Autorité de certification personnalisée pour l'API Kubernetes"
    Si vous utilisez une autorité de certification personnalisée pour votre API Kubernetes, vous pouvez monter un fichier de bundle contenant vos certificats intermédiaires et racines sur le contrôleur d'entrée et définir la `KUBERNETES_SSL_CA_CERT` valeur de l'environnement sur le chemin d'accès du bundle à l'intérieur du conteneur. Sinon, même si cela n'est pas recommandé, vous pouvez désactiver la vérification du certificat en définissant la `KUBERNETES_SSL_VERIFY` variable d'environnement du contrôleur d'entrée sur `no` (la valeur par défaut `yes`est ).

De plus, **il est crucial de définir la `KUBERNETES_MODE` variable d'environnement lors `yes` de  l'utilisation de l'intégration Kubernetes**. Cette variable est obligatoire pour un bon fonctionnement. Si vous utilisez la Gateway API, définissez également `KUBERNETES_GATEWAY_MODE=yes`.

### Méthodes d'installation {#kubernetes-installation}

#### Utilisation de la charte Helm (recommandé)

La méthode recommandée pour installer Kubernetes est d'utiliser la charte Helm disponible à l'adresse `https://github.com/bunkerity/bunkerweb-helm`:

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

Vous pouvez ensuite utiliser le tableau de bord de bunkerweb à partir de ce dépôt :

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

La liste complète des valeurs est répertoriée dans le [fichier charts/bunkerweb/values.yaml](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) du [dépôt bunkerity/bunkerweb-helm](https://github.com/bunkerity/bunkerweb-helm).

#### Conteneur Sidecar + Helm

Cette documentation explique comment déployer BunkerWeb en tant que sidecar pour protéger vos applications Kubernetes. Dans cette architecture, chaque application possède son propre conteneur BunkerWeb qui agit comme un reverse proxy de sécurité.

##### Architecture

```mermaid
flowchart TB

  %% ---------- Styles ----------
  classDef scheduler     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef podContainer  fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:6 3,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;

  %% ---------- Haut : Scheduler ----------
  SCHED["Scheduler BunkerWeb (centralisé)<br/>+ UI + MariaDB + Redis"]:::scheduler

  %% ---------- Groupe de Pods ----------
  subgraph PODS["Pods"]
    %% Pod d'application 1 ----------
    subgraph POD1["Pod d'application"]
      BW1["BunkerWeb"]:::component
      APP1["Application<br/>(port 80)"]:::component
      BW1 -->|requêtes légitimes| APP1
    end
    class POD1 podContainer

    %% Pod d'application 2 ----------
    subgraph POD2["Pod d'application"]
      BW2["BunkerWeb"]:::component
      APP2["Application<br/>(port XX)"]:::component
      BW2 -->|requêtes légitimes| APP2
    end
    class POD2 podContainer
  end

  %% ---------- Équilibreur de charge (en bas) ----------
  LB["Équilibreur de charge"]:::lb

  %% ---------- Câblage (visible, sémantique) ----------
  %% Le Scheduler contrôle les instances BunkerWeb (API)
  SCHED -->|API 5000| BW1
  SCHED -->|API 5000| BW2

  %% L'équilibreur de charge envoie le trafic vers BunkerWeb
  LB -->|HTTP/HTTPS| BW1
  LB -->|HTTP/HTTPS| BW2

  %% ---------- Aide à la mise en page (caché) ----------
  %% Place l'équilibreur de charge sous tout le groupe PODS
  PODS --> LB
  linkStyle 6 stroke-width:0px,stroke:transparent;
```

##### Prérequis

- Un cluster Kubernetes fonctionnel
- Helm 3.x installé
- Le chart Helm BunkerWeb déployé avec :
  - `scheduler` activé
  - `ui` activée
  - `mariadb` activé (pour stocker les configurations)
  - `redis` activé (pour la synchronisation)
  - `controller` activé (recommandé pour la découverte automatique des sidecars)
  - `bunkerweb.replicas: 0` (pas de déploiement standalone)

##### Modes de Découverte des Sidecars

BunkerWeb propose deux modes de découverte des sidecars :

###### Mode 1 : Découverte Automatique (Controller - Recommandé)

Le **controller BunkerWeb** découvre automatiquement les pods avec sidecars BunkerWeb sans configuration manuelle.

**Avantages :**
- ✅ Découverte automatique des nouveaux sidecars
- ✅ Pas besoin de maintenir manuellement `BUNKERWEB_INSTANCES`
- ✅ Mise à l'échelle automatique

**Configuration :**

1. Activez le controller dans `values.yaml` :
```yaml
controller:
  enabled: true
  tag: "1.6.8"
```

2. Pour chaque sidecar, ajoutez :
   - **Annotation du pod** : `bunkerweb.io/INSTANCE: "yes"`
   - **Variable d'environnement** : `KUBERNETES_MODE: "yes"`

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

3. **Pas besoin de service headless** - le controller communique directement avec les pods

4. **Pas besoin** de configurer le scheduler manuellement `BUNKERWEB_INSTANCES` - le controller gère la découverte

###### Mode 2 : Configuration Manuelle (BUNKERWEB_INSTANCES)

Configuration explicite de chaque instance via la variable d'environnement `BUNKERWEB_INSTANCES`.

**Avantages :**
- ✅ Contrôle précis des instances gérées
- ✅ Utile pour des environnements multi-namespace complexes

**Configuration :**

Voir les sections suivantes pour les détails.

##### Étape 1 : Configuration du Scheduler

Le scheduler BunkerWeb est le composant central qui distribue les configurations à tous les sidecars.

###### Option A : Avec le Controller (Recommandé)

Si vous utilisez le controller pour la découverte automatique, **aucune configuration spéciale n'est nécessaire** pour le scheduler. Le controller détectera automatiquement les pods avec l'annotation `bunkerweb.io/INSTANCE: "yes"`.

###### Option B : Configuration Manuelle avec `BUNKERWEB_INSTANCES`

Dans votre fichier `values.yaml` du chart BunkerWeb, configurez la variable d'environnement `BUNKERWEB_INSTANCES` avec les URLs de tous vos services headless :

```yaml
scheduler:
  tag: "1.6.8"
  extraEnvs:
    - name: BUNKERWEB_INSTANCES
      value: "http://app1-bunkerweb-workers.namespace.svc.cluster.local:5000 http://app2-bunkerweb-workers.namespace.svc.cluster.local:5000"
```

**Important :**
- Séparez les URLs par des espaces
- Utilisez le port **5000** (API interne de BunkerWeb)
- Format : `http://<service-name>.<namespace>.svc.cluster.local:5000`

##### Étape 2 : Création du Déploiement avec Sidecar

###### Structure du Déploiement

Créez un déploiement Kubernetes avec deux conteneurs :

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mon-app-bunkerweb
  namespace: votre-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mon-app
  template:
    metadata:
      labels:
        app: mon-app
    spec:
      containers:
        # Votre application
        - name: mon-app
          image: mon-image:latest
          ports:
            - containerPort: 80  # Port sur lequel écoute votre app

        # Sidecar BunkerWeb
        - name: bunkerweb
          image: bunkerity/bunkerweb:1.6.8
          ports:
            - containerPort: 8080  # Port HTTP exposé
            - containerPort: 5000  # API interne (obligatoire)
              name: bwapi
            - containerPort: 9113 # Prometheus exporter
              name: metrics
          env:
            - name: KUBERNETES_MODE  # OBLIGATOIRE pour le mode controller
              value: "yes"
            - name: API_WHITELIST_IP
              value: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
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

**Points clés :**
- **Annotation obligatoire** : `bunkerweb.io/INSTANCE: "yes"` doit être ajoutée dans `template.metadata.annotations` (au même niveau que `labels`)
- **Variable d'environnement obligatoire** : `KUBERNETES_MODE: "yes"` active le mode Kubernetes
- **Pas de service headless nécessaire** : le controller communique directement avec les pods

###### Variables d'environnement importantes

| Variable                  | Valeur                                                | Description                                                      |
| ------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------- |
| `KUBERNETES_MODE`         | `yes`                                                 | **Obligatoire** pour la découverte automatique via le controller |
| `KUBERNETES_GATEWAY_MODE` | `yes` or `no` (if using Gateway API)                  | Use Gateway API mode                                             |
| `API_WHITELIST_IP`        | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | IPs autorisées à accéder à l'API                                 |

##### Étape 3 : Création des Services

###### Service ClusterIP (exposition externe)

Service pour exposer votre application via BunkerWeb :

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mon-app-bunkerweb
  namespace: votre-namespace
spec:
  type: ClusterIP  # ou LoadBalancer selon vos besoins
  selector:
    app: mon-app
  ports:
    - name: http
      port: 80
      targetPort: 8080  # Port BunkerWeb
```

###### Service Headless (API interne) - Conditionnel

**Uniquement requis en mode manuel (sans controller)** :

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mon-app-bunkerweb-workers
  namespace: votre-namespace
spec:
  clusterIP: None  # Service headless
  selector:
    app: mon-app
  ports:
    - name: bwapi
      protocol: TCP
      port: 5000
      targetPort: 5000
```

**Important :**
- ⚠️ **Non requis avec le controller** - le controller communique directement avec les pods via l'API Kubernetes
- ✅ **Obligatoire sans le controller** - le nom de ce service doit être ajouté manuellement dans `BUNKERWEB_INSTANCES`
- Le `selector` doit correspondre aux labels de votre déploiement

##### Étape 4 : Configuration du Reverse Proxy

Vous avez **deux options** pour configurer le reverse proxy :

###### Option A : Via l'Interface Web (UI)

1. Accédez à l'UI de BunkerWeb
2. Allez dans la section **"Services"**
3. Créez un nouveau service avec :
   - **Server name** : `mon-app.example.com`
   - **Reverse proxy host** : `http://127.0.0.1:80` (ou le port de votre app)
   - **Use reverse proxy** : `yes`
4. Sauvegardez

Le scheduler enverra automatiquement la configuration au sidecar via l'API (port 5000).

###### Option B : Via Variables d'Environnement

Ajoutez ces variables dans le conteneur `bunkerweb` :

```yaml
env:
  - name: MULTISITE
    value: "yes"
  - name: SERVER_NAME
    value: "mon-app.example.com"
  - name: mon-app.example.com_USE_REVERSE_PROXY
    value: "yes"
  - name: mon-app.example.com_REVERSE_PROXY_HOST
    value: "http://127.0.0.1:80"
  - name: mon-app.example.com_REVERSE_PROXY_URL
    value: "/"
```

**Note :** L'option UI est recommandée pour une gestion centralisée et dynamique.

##### Étape 5 : Déploiement

###### Avec le Controller (Mode Automatique - Recommandé)

1. **Déployez votre application avec le sidecar** :
   ```bash
   kubectl apply -f mon-app-deployment.yaml
   ```

   Assurez-vous que :
   - L'annotation `bunkerweb.io/INSTANCE: "yes"` est présente dans `template.metadata.annotations`
   - La variable `KUBERNETES_MODE: "yes"` est définie dans le conteneur bunkerweb

2. **Vérifiez que le controller détecte le sidecar** :
   ```bash
   kubectl logs -n bunkerweb deployment/bunkerweb-controller -f
   ```
   Vous devriez voir des logs indiquant la découverte du nouveau pod.

3. **Créez la configuration du reverse proxy** via l'UI de BunkerWeb

4. **Testez votre application** :
   ```bash
   curl -H "Host: mon-app.example.com" http://<service-ip>
   ```

###### Sans Controller (Mode Manuel)

1. **Déployez votre application avec le sidecar** :
   ```bash
   kubectl apply -f mon-app-deployment.yaml
   ```

2. **Ajoutez le service headless dans `BUNKERWEB_INSTANCES`** :
   Mettez à jour votre `values.yaml` et upgrader le chart Helm :
   ```bash
   helm upgrade bunkerweb bunkerity/bunkerweb -n bunkerweb -f values.yaml
   ```

3. **Vérifiez que le scheduler détecte le sidecar** :
   ```bash
   kubectl logs -n bunkerweb deployment/bunkerweb-scheduler -f
   ```
   Vous devriez voir des logs indiquant la connexion au nouveau worker.

4. **Créez la configuration du reverse proxy** via l'UI de BunkerWeb

5. **Testez votre application** :
   ```bash
   curl -H "Host: mon-app.example.com" http://<service-ip>
   ```


###### Problèmes courants

| Problème                              | Cause                                       | Solution                                                            |
| ------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------- |
| Le scheduler ne trouve pas le sidecar | Service headless manquant ou mal configuré  | Vérifier que le service existe et est dans `BUNKERWEB_INSTANCES`    |
| Erreur 502 Bad Gateway                | L'app n'est pas accessible depuis BunkerWeb | Vérifier que l'URL du reverse proxy est correcte (`127.0.0.1:port`) |
| Configuration non appliquée           | Le sidecar n'a pas reçu la config           | Vérifier les logs du scheduler et du sidecar                        |
| Port 5000 non accessible              | Port non exposé dans le conteneur           | Ajouter `- containerPort: 5000` dans le conteneur bunkerweb         |

##### Ajouter une Nouvelle Application

###### Avec le Controller (Mode Automatique)

Pour ajouter une nouvelle application protégée par BunkerWeb :

1. **Créez un nouveau déploiement** avec le sidecar BunkerWeb avec :
   - Annotation `bunkerweb.io/INSTANCE: "yes"` dans `template.metadata.annotations`
   - Variable d'environnement `KUBERNETES_MODE: "yes"` dans le conteneur bunkerweb

2. **Créez uniquement le service ClusterIP** (pas de service headless nécessaire !)

3. **Appliquez le déploiement** :
   ```bash
   kubectl apply -f nouvelle-app-deployment.yaml
   ```

4. **Le controller détecte automatiquement le nouveau pod** - pas besoin de redéployer le chart !

5. **Configurez le reverse proxy** dans l'UI

###### Sans le Controller (Mode Manuel)

Pour ajouter une nouvelle application protégée par BunkerWeb :

1. **Créez un nouveau déploiement** avec le sidecar BunkerWeb (comme décrit ci-dessus)

2. **Créez les deux services** (ClusterIP + Headless)

3. **Ajoutez le nouveau service headless** dans `BUNKERWEB_INSTANCES` :
   ```yaml
   extraEnvs:
     - name: BUNKERWEB_INSTANCES
       value: "http://app1-workers.ns.svc.cluster.local:5000 http://app2-workers.ns.svc.cluster.local:5000"
   ```

4. **Redéployez le chart** :
   ```bash
   helm upgrade bunkerweb bunkerity/bunkerweb -n bunkerweb -f values.yaml
   ```

5. **Configurez le reverse proxy** dans l'UI

##### Bonnes Pratiques

✅ **Utilisez le controller** pour la découverte automatique des sidecars (plus simple, pas de service headless nécessaire)
✅ **Utilisez un seul scheduler centralisé** pour gérer tous les sidecars
✅ **Ajoutez toujours l'annotation** `bunkerweb.io/INSTANCE: "yes"` et la variable `KUBERNETES_MODE: "yes"` en mode controller
✅ **Pas de service headless avec le controller** - seul le service ClusterIP est nécessaire
✅ **Utilisez l'UI** pour gérer les configurations (plus flexible)
✅ **Définissez des resource limits** pour les conteneurs
✅ **Utilisez des secrets Kubernetes** pour les configurations sensibles
✅ **Vérifiez les logs** du scheduler et des sidecars régulièrement


#### Fichiers YAML complets

Au lieu d'utiliser la charte Helm, vous pouvez également utiliser les modèles YAML dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/misc/integrations) du référentiel GitHub. Veuillez noter que nous vous recommandons vivement d'utiliser le tableau de barre à la place.

### Ressources d'entrée

Une fois que la pile Kubernetes de BunkerWeb est correctement configurée et opérationnelle (reportez-vous aux journaux autoconf pour plus d'informations), vous pouvez procéder au déploiement d'applications Web au sein du cluster et déclarer votre ressource d'entrée.

Il est important de noter que les paramètres BunkerWeb doivent être spécifiés en tant qu'annotations pour la ressource Ingress. Pour la partie domaine, veuillez utiliser la valeur spéciale **`bunkerweb.io`**. En incluant les annotations appropriées, vous pouvez configurer BunkerWeb en conséquence pour la ressource Ingress.

!!! tip "Ignorer les annotations bruyantes"
    Lorsque certaines annotations ne doivent pas impacter autoconf, définissez `KUBERNETES_IGNORE_ANNOTATIONS` sur le déploiement du contrôleur. Fournissez une liste de clés d'annotations séparées par des espaces ou des virgules (par exemple `bunkerweb.io/EXTRA_FOO`) ou simplement le suffixe (`EXTRA_FOO`). Les annotations correspondantes sont supprimées des paramètres dérivés de l'ingress, et les pods les portant sont entièrement ignorés lors de la découverte des instances.

!!! info "Prise en charge TLS"
    Le contrôleur d'entrée BunkerWeb prend entièrement en charge les certificats HTTPS personnalisés à l'aide de la spécification tls, comme indiqué dans l'exemple. La configuration de solutions telles que `cert-manager` la génération automatique de secrets tls n'entre pas dans le cadre de cette documentation.

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

### Ressources Gateway

Lorsque le mode Gateway API est activé, vous pouvez déclarer des ressources `Gateway`, `HTTPRoute`, `TLSRoute`, `TCPRoute` et `UDPRoute`.
Les paramètres BunkerWeb sont fournis via des annotations `bunkerweb.io/<SETTING>` sur le `HTTPRoute` ; pour limiter un
paramètre à un hôte, utilisez `bunkerweb.io/<hostname>_<SETTING>`. Le champ `hostnames` pilote les noms de serveur. Pour `TCPRoute`/`UDPRoute` (et `TLSRoute` sans `hostnames`), BunkerWeb génère un nom de serveur du type `<route>.<namespace>.<protocol>`. Voir [Classe Gateway](#gateway-class).
Les annotations sur le `Gateway` s'appliquent à toutes les routes qui y sont rattachées, tandis que les annotations sur un `HTTPRoute` ne s'appliquent qu'à cette route.
Vous pouvez limiter les annotations du Gateway à un nom de serveur avec `bunkerweb.io/<hostname>_<SETTING>` ; elles ne s'appliqueront que si cette route/ce nom de serveur existe.

#### Ressources prises en charge

- Ressources : `HTTPRoute`, `TLSRoute`, `TCPRoute` et `UDPRoute` (pas de `GRPCRoute`).
- Règles : seule la première règle est utilisée pour `TLSRoute`, `TCPRoute` et `UDPRoute`.
- Backends : uniquement `Service`, premier `backendRef` par règle.

#### Protocoles et TLS

- Protocoles de listener : `HTTP`/`HTTPS` pour `HTTPRoute`, `TLS` pour `TLSRoute`, `TCP` pour `TCPRoute` et `UDP` pour `UDPRoute`.
- TLS : certificats via les `certificateRefs` du listener avec `HTTPS` ou `TLS` + `mode: Terminate` (Passthrough n'est pas pris en charge pour la terminaison). `TLSRoute` fonctionne en mode stream.

!!! tip "Nom de serveur pour les routes stream"
    Pour `TLSRoute`, `TCPRoute` et `UDPRoute`, vous pouvez remplacer le nom de serveur généré en définissant `bunkerweb.io/SERVER_NAME` sur la route.

!!! note "Experimental Channel pour les routes stream"
    Si vous souhaitez utiliser `TLSRoute`, `TCPRoute` ou `UDPRoute`, installez les CRD de l'Experimental Channel : https://gateway-api.sigs.k8s.io/guides/getting-started/#install-experimental-channel

!!! info "Prise en charge TLS"
    La terminaison TLS est gérée via les listeners du `Gateway` et leurs `certificateRefs` (secrets TLS) pour `HTTPRoute` avec `HTTPS` ou `TLS` + `mode: Terminate`. `TLSRoute` fonctionne en mode stream.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: my-gateway
spec:
  gatewayClassName: bunkerweb
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      hostname: www.example.com
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-route
  annotations:
    # S'applique à tous les hostnames de cette route
    bunkerweb.io/MY_SETTING: "value"
    # S'applique uniquement au host www.example.com
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  parentRefs:
    - name: my-gateway
  hostnames:
    - www.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: svc-my-app
          port: 8000
```

### Espaces de noms {#namespaces_1}

À partir de la version `1.6.0`, les piles autoconf de BunkerWeb prennent désormais en charge les espaces de noms. Cette fonctionnalité vous permet de gérer plusieurs clusters d'instances et de services BunkerWeb sur le même cluster Kubernetes. Pour tirer parti des espaces de noms, il suffit de définir le `namespace` champ de métadonnées sur vos instances et services BunkerWeb. Voici un exemple :

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Set the namespace for the BunkerWeb instance
...
```

!!! info "Comportement de l'espace de nommage"

    Par défaut, toutes les piles Autoconf écoutent tous les namespaces. Si vous souhaitez restreindre une pile à des namespaces spécifiques, vous pouvez définir la variable d'environnement `NAMESPACES` dans le déploiement `bunkerweb-controller` :

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
              image: bunkerity/bunkerweb-autoconf:1.6.8
              imagePullPolicy: Always
              env:
                - name: NAMESPACES
                  value: "my-namespace my-other-namespace" # Only listen to these namespaces
                ...
    ...
    ```

    Gardez à l'esprit que la variable d'environnement `NAMESPACES` est une liste de namespaces séparés par des espaces.

!!! warning "Spécifications de l'espace de nommage"

    Il ne peut y avoir qu'une **seule base de données** et qu'un **seul Scheduler** par namespace. Si plusieurs bases de données ou plusieurs Schedulers sont créés dans le même namespace, les configurations entreront en conflit.

    Le Scheduler n'a pas besoin de l'annotation `NAMESPACE` pour fonctionner correctement. Il suffit que le paramètre `DATABASE_URI` soit correctement configuré afin qu'il puisse accéder à la même base de données que le service autoconf.

### Classe d'entrée

Lorsqu'il est installé en utilisant les méthodes officielles de la documentation, BunkerWeb est livré avec la définition suivante `IngressClass` :

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

Afin de limiter les `Ingress` ressources surveillées par le contrôleur d'entrée, vous pouvez définir la `KUBERNETES_INGRESS_CLASS` variable d'environnement avec la valeur `bunkerweb`. Ensuite, vous pouvez utiliser la `ingressClassName` directive dans vos `Ingress` définitions :

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

### Classe Gateway {#gateway-class}

Lorsque vous utilisez la Gateway API, BunkerWeb attend une `GatewayClass` pointant vers son contrôleur :

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: bunkerweb
spec:
  controllerName: bunkerweb.io/gateway-controller
```

Pour limiter les ressources `Gateway` surveillées, définissez `KUBERNETES_GATEWAY_CLASS` (par exemple `bunkerweb`) et utilisez
le `gatewayClassName` correspondant dans vos ressources `Gateway` :

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: my-gateway
spec:
  gatewayClassName: bunkerweb
  listeners:
    - name: http
      protocol: HTTP
      port: 80
      hostname: www.example.com
```

### Nom de domaine personnalisé

Si vous utilisez un nom de domaine personnalisé différent de celui par défaut pour votre cluster Kubernetes `kubernetes.local` , vous pouvez définir la valeur à l'aide de la `KUBERNETES_DOMAIN_NAME` variable d'environnement sur le conteneur du Scheduler.

### Utilisation avec le contrôleur d'entrée existant

!!! info "Conserver à la fois le contrôleur d'entrée existant et BunkerWeb"

    Il s'agit d'un cas d'utilisation où vous souhaitez conserver un contrôleur d'entrée existant, tel que nginx. Le flux de trafic typique sera : équilibreur de charge => contrôleur d'entrée => BunkerWeb => application.

#### Installation du contrôleur d'entrée nginx

Installez le dépôt helm nginx d'entrée :

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

Installez le contrôleur d'entrée nginx avec les valeurs par défaut (il se peut qu'il ne fonctionne pas sur votre propre cluster prêt à l'emploi, veuillez consulter la [documentation](https://kubernetes.github.io/ingress-nginx/)) :

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

Extraire l'adresse IP de LB :

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Configurez les entrées DNS sur l'adresse IP de LB (par exemple, `bunkerweb` le sous-domaine pour l'interface utilisateur BW et `myapp` pour l'application) :

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

**Installation de BunkerWeb**

Installez le dépôt helm de BunkerWeb :

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

Créer un `values.yaml` fichier :

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
  tag: 1.6.8

# Scheduler settings
scheduler:
  tag: 1.6.8
  extraEnvs:
    # Enable real IP module to get real IP of clients
    - name: USE_REAL_IP
      value: "yes"

# Controller settings
controller:
  tag: 1.6.8

# UI settings
ui:
  tag: 1.6.8
```

Installez BunkerWeb avec des valeurs personnalisées :

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

Vérifiez les journaux et attendez que tout soit prêt.

**Installation de l'interface utilisateur Web**

Configurez l'entrée suivante (en supposant que le contrôleur nginx est installé) :

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

Et vous pouvez maintenant passer à l'assistant de configuration en accédant à `https://bunkerweb.example.com/setup`.

**Protection de l'application existante**

**Tout d'abord, vous devrez vous rendre dans Paramètres globaux, sélectionner le plugin SSL, puis désactiver la redirection automatique HTTP vers HTTPS. Veuillez noter que vous n'avez besoin de le faire qu'une seule fois.**

Supposons que vous ayez une application dans l'espace de `myapp` noms qui est accessible à l'aide du `myapp-service` service sur le port `5000`.

Vous devrez ajouter un nouveau service sur l'interface utilisateur web et renseigner les informations requises :

- Nom du serveur : le domaine public de votre application (par ex. `myapp.example.com`)
- SSL/TLS : votre contrôleur d'entrée s'occupe de cette partie, donc ne l'activez pas sur BunkerWeb car le trafic est interne au sein du cluster
- Hôte proxy inverse : l'URL complète de votre application au sein du cluster (par exemple) `http://myapp-service.myapp.svc.cluster.local:5000`

Une fois le nouveau service ajouté, vous pouvez maintenant déclarer une ressource Ingress pour ce service et l'acheminer vers le service BunkerWeb sur le port HTTP :

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

Vous pouvez visiter `http(s)://myapp.example.com`, qui est maintenant protégé par BunkerWeb ️

### Migrer depuis le contrôleur d'ingress nginx {#migrate-from-nginx-ingress-controller}

#### Introduction

Ce guide pratique vous accompagne dans la migration de vos ressources **NGINX Ingress** vers **BunkerWeb**. Il se concentre sur la conversion de vos manifestes Kubernetes existants avec des exemples d'utilisation.

**Prérequis** : BunkerWeb doit être installé dans votre cluster (voir les [méthodes d'installation](#kubernetes-installation)).

#### Stratégie de migration

Approche recommandée : _Coexistence_

1. **Installer BunkerWeb en parallèle** avec NGINX Ingress
2. **Dupliquer votre Ingress** avec la classe `bunkerweb`
3. **Tester** avec l'IP du LoadBalancer BunkerWeb
4. **Basculer le DNS** une fois validé
5. **Supprimer** les anciennes ressources NGINX Ingress

#### Flux de travail de migration

```bash
# 1. Sauvegarder votre Ingress actuel
kubectl get ingress --all-namespaces -o yaml > nginx-ingress-backup.yaml

# 2. Convertir et créer le nouvel Ingress BunkerWeb
kubectl apply -f bunkerweb-ingress.yaml

# 3. Tester avec l'IP BunkerWeb
BUNKERWEB_IP=$(kubectl get svc -n bunkerweb bunkerweb-external -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl -H "Host: votre-domaine.com" http://$BUNKERWEB_IP

# 4. Une fois validé, basculer le DNS puis supprimer l'ancien
kubectl delete ingress <ancien-ingress> -n <namespace>
```

---

#### Exemple 1 : Ingress standard

##### Scénario

Une application web simple avec HTTPS automatique via cert-manager.

=== "NGINX Ingress"

    ```yaml title="nginx-ingress.yaml"
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: webapp-ingress
      namespace: production
      annotations:
        kubernetes.io/ingress.class: "nginx"
        cert-manager.io/cluster-issuer: "letsencrypt-prod"
    spec:
      tls:
      - hosts:
        - webapp.example.com
        secretName: webapp-tls
      rules:
      - host: webapp.example.com
        http:
          paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: webapp-service
                port:
                  number: 80
    ```

=== "BunkerWeb Ingress"

    ```yaml title="bunkerweb-ingress.yaml"
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: webapp-ingress
      namespace: production
      annotations:
        # Let's Encrypt automatique BunkerWeb (alternative à cert-manager)
        bunkerweb.io/AUTO_LETS_ENCRYPT: "yes"
        bunkerweb.io/EMAIL_LETS_ENCRYPT: "admin@example.com"

        # OU conserver cert-manager (commenter AUTO_LETS_ENCRYPT ci-dessus)
        # cert-manager.io/cluster-issuer: "letsencrypt-prod"
    spec:
      ingressClassName: bunkerweb  # Changement principal : classe Ingress
      tls:
      - hosts:
        - webapp.example.com
        secretName: webapp-tls
      rules:
      - host: webapp.example.com
        http:
          paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: webapp-service
                port:
                  number: 80
    ```

##### Différences clés

| Aspect          | NGINX                                    | BunkerWeb                             |
| --------------- | ---------------------------------------- | ------------------------------------- |
| Classe Ingress  | Annotation `kubernetes.io/ingress.class` | Champ `ingressClassName`              |
| Certificats SSL | cert-manager requis                      | cert-manager OU Let's Encrypt intégré |
| Sécurité        | Aucune par défaut                        | WAF activé par défaut                 |

---

#### Exemple 2 : Ingress avec annotations

##### Scénario

API REST avec limitation de débit, CORS, redirection HTTPS et configuration de timeout.

=== "NGINX Ingress"

    ```yaml title="nginx-ingress.yaml"
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: api-ingress
      namespace: production
      annotations:
        kubernetes.io/ingress.class: "nginx"
        cert-manager.io/cluster-issuer: "letsencrypt-prod"

        # Redirection HTTPS
        nginx.ingress.kubernetes.io/ssl-redirect: "true"
        nginx.ingress.kubernetes.io/force-ssl-redirect: "true"

        # CORS
        nginx.ingress.kubernetes.io/enable-cors: "true"
        nginx.ingress.kubernetes.io/cors-allow-origin: "https://app.example.com,https://admin.example.com"
        nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, DELETE, OPTIONS"
        nginx.ingress.kubernetes.io/cors-allow-credentials: "true"

        # Limitation de débit
        nginx.ingress.kubernetes.io/limit-rps: "20"
        nginx.ingress.kubernetes.io/limit-burst-multiplier: "5"

        # Timeouts et taille
        nginx.ingress.kubernetes.io/proxy-connect-timeout: "10"
        nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
        nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
        nginx.ingress.kubernetes.io/proxy-body-size: "20m"

        # En-têtes
        nginx.ingress.kubernetes.io/proxy-set-headers: "custom-headers"
    spec:
      tls:
      - hosts:
        - api.example.com
        secretName: api-tls
      rules:
      - host: api.example.com
        http:
          paths:
          - path: /v1
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 8080
    ```

=== "BunkerWeb Ingress"

    ```yaml title="bunkerweb-ingress.yaml"
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: api-ingress
      namespace: production
      annotations:
        # SSL automatique
        bunkerweb.io/AUTO_LETS_ENCRYPT: "yes"
        bunkerweb.io/EMAIL_LETS_ENCRYPT: "admin@example.com"

        # Redirection HTTPS
        bunkerweb.io/REDIRECT_HTTP_TO_HTTPS: "yes"

        # CORS
        bunkerweb.io/USE_CORS: "yes"
        bunkerweb.io/CORS_ALLOW_ORIGIN: "^https://(app|admin).example.com$"
        bunkerweb.io/CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
        bunkerweb.io/CORS_ALLOW_CREDENTIALS: "yes"

        # Limitation de débit
        bunkerweb.io/USE_LIMIT_REQ: "yes"
        bunkerweb.io/LIMIT_REQ_URL: "/"
        bunkerweb.io/LIMIT_REQ_RATE: "20r/s"

        # Timeouts
        bunkerweb.io/REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
        bunkerweb.io/REVERSE_PROXY_SEND_TIMEOUT: "60s"
        bunkerweb.io/REVERSE_PROXY_READ_TIMEOUT: "60s"

        # Taille maximale du corps
        bunkerweb.io/MAX_CLIENT_SIZE: "20m"

        # En-têtes personnalisés
        bunkerweb.io/CUSTOM_HEADER: "X-API-Version: v1"

        # Sécurité supplémentaire (bonus BunkerWeb)
        bunkerweb.io/USE_MODSECURITY: "yes"
        bunkerweb.io/USE_BAD_BEHAVIOR: "yes"
    spec:
      ingressClassName: bunkerweb
      tls:
      - hosts:
        - api.example.com
        secretName: api-tls
      rules:
      - host: api.example.com
        http:
          paths:
          - path: /v1
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 8080
    ```

##### Conversion des annotations

| Fonctionnalité         | NGINX Ingress                         | BunkerWeb Ingress                                                                     |
| ---------------------- | ------------------------------------- | ------------------------------------------------------------------------------------- |
| Redirection HTTPS      | `ssl-redirect: "true"`                | `REDIRECT_HTTP_TO_HTTPS: "yes"`                                                       |
| Activation CORS        | `enable-cors: "true"`                 | `USE_CORS: "yes"`                                                                     |
| Origines CORS          | `cors-allow-origin: "https://..."`    | `CORS_ALLOW_ORIGIN: "^https://..."` (expression régulière PCRE ou `*` ou `self`)      |
| Méthodes CORS          | `cors-allow-methods: "GET, POST"`     | `CORS_ALLOW_METHODS: "GET, POST"`                                                     |
| Limitation de débit    | `limit-rps: "20"`                     | `USE_LIMIT_REQ: "yes"` + `LIMIT_REQ_URL: "/"` + `LIMIT_REQ_RATE: "20r/s"`             |
| Timeouts               | `proxy-*-timeout: "60"`               | `REVERSE_PROXY_*_TIMEOUT: "60s"`                                                      |
| Taille du corps        | `proxy-body-size: "20m"`              | `MAX_CLIENT_SIZE: "20m"`                                                              |
| En-têtes personnalisés | `proxy-set-headers: "custom-headers"` | `CUSTOM_HEADER: "Header-Name: value"` (plusieurs annotations pour plusieurs en-têtes) |
| Sécurité               | N/A                                   | `USE_MODSECURITY: "yes"` + `USE_BAD_BEHAVIOR: "yes"`                                  |

---

#### Exemple 3 : Ingress avec configuration NGINX personnalisée

##### Scénario

Application avec règles NGINX personnalisées via `configuration-snippet` : règles de réécriture complexes, authentification, en-têtes spéciaux.

=== "NGINX Ingress"

    ```yaml title="nginx-ingress.yaml"
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: custom-app-ingress
      namespace: production
      annotations:
        kubernetes.io/ingress.class: "nginx"
        cert-manager.io/cluster-issuer: "letsencrypt-prod"

        # Authentification basique
        nginx.ingress.kubernetes.io/auth-type: basic
        nginx.ingress.kubernetes.io/auth-secret: basic-auth
        nginx.ingress.kubernetes.io/auth-realm: "Authentication Required"

        # Liste blanche IP
        nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,172.16.0.0/12"

        # Configuration personnalisée via snippet
        nginx.ingress.kubernetes.io/configuration-snippet: |
          # Réécriture personnalisée
          rewrite ^/old-path/(.*)$ /new-path/$1 permanent;

          # En-têtes conditionnels
          if ($request_uri ~* ^/api/) {
            add_header X-API-Gateway "true";
          }

          # Bloquer certains user agents
          if ($http_user_agent ~* (bot|crawler|spider)) {
            return 403;
          }

          # Cache pour les assets
          location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
            expires 7d;
            add_header Cache-Control "public, immutable";
          }

          # Limite de connexions concurrentes
          limit_conn addr 10;

          # Proxy vers un service externe pour un chemin
          location /external-api {
            proxy_pass https://external-service.com;
            proxy_set_header Host external-service.com;
          }
    spec:
      tls:
      - hosts:
        - custom-app.example.com
        secretName: custom-app-tls
      rules:
      - host: custom-app.example.com
        http:
          paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: custom-app-service
                port:
                  number: 80

    ---
    # ConfigMap pour l'authentification
    apiVersion: v1
    kind: Secret
    metadata:
      name: basic-auth
      namespace: production
    type: Opaque
    data:
      auth: dXNlcjokYXByMSRIRzJLbkZNTyR5ZnBmRUxYVXFTSGg0ME5pRC8uNGcuCg==  # user:password
    ```

=== "BunkerWeb Ingress"

    <!-- ###### Option A : Utilisation des fonctionnalités natives BunkerWeb -->

    ```yaml title="bunkerweb-ingress.yaml"
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: custom-app-ingress
      namespace: production
      annotations:
        # SSL
        bunkerweb.io/AUTO_LETS_ENCRYPT: "yes"
        bunkerweb.io/EMAIL_LETS_ENCRYPT: "admin@example.com"

        # Authentification basique (native BunkerWeb)
        bunkerweb.io/USE_AUTH_BASIC: "yes"
        bunkerweb.io/AUTH_BASIC_LOCATION: "sitewide" # Ou "/secure" ou "^~ /admin/"
        bunkerweb.io/AUTH_BASIC_USER: "user"
        bunkerweb.io/AUTH_BASIC_PASSWORD: "password"  # Ou utiliser un Secret
        bunkerweb.io/AUTH_BASIC_USER_1: "user1"
        bunkerweb.io/AUTH_BASIC_PASSWORD_1: "otherpassword"  # Ou utiliser un Secret
        bunkerweb.io/AUTH_BASIC_TEXT: "Authentication Required"

        # Liste blanche IP (native BunkerWeb)
        bunkerweb.io/WHITELIST_IP: "10.0.0.0/8 172.16.0.0/12"

        # Blocage User-Agent (native BunkerWeb)
        bunkerweb.io/USE_BAD_BEHAVIOR: "yes"
        bunkerweb.io/BLACKLIST_USER_AGENT: "bot crawler spider" # Ou regex PCRE

        # Cache (native BunkerWeb)
        bunkerweb.io/USE_CLIENT_CACHE: "yes"
        bunkerweb.io/CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|css|js|otf|ttf|eot|woff|woff2"
        bunkerweb.io/CLIENT_CACHE_CONTROL: "public, max-age=15552000" # Valeur pour l'en-tête HTTP Cache-Control
        bunkerweb.io/CLIENT_CACHE_ETAG: "yes" # Activer l'en-tête ETag

        # Limite de connexions
        bunkerweb.io/USE_LIMIT_CONN: "yes"
        bunkerweb.io/LIMIT_CONN_MAX_HTTP1: "10"
        bunkerweb.io/LIMIT_CONN_MAX_HTTP2: "100"
        bunkerweb.io/LIMIT_CONN_MAX_HTTP3: "100"
    spec:
      ingressClassName: bunkerweb
      tls:
      - hosts:
        - custom-app.example.com
        secretName: custom-app-tls
      rules:
      - host: custom-app.example.com
        http:
          paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: custom-app-service
                port:
                  number: 80
    ```

=== "BunkerWeb Ingress avec ConfigMap"

    <!-- ###### Option B : Utilisation de ConfigMaps pour la configuration personnalisée -->

    Pour les règles sans équivalent direct (réécritures complexes, proxy externe), utiliser une ConfigMap :

    ```yaml title="bunkerweb-ingress-configmap.yaml"
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: custom-app-ingress
      namespace: production
      annotations:
        bunkerweb.io/AUTO_LETS_ENCRYPT: "yes"
        bunkerweb.io/EMAIL_LETS_ENCRYPT: "admin@example.com"

        # Fonctionnalités natives
        bunkerweb.io/USE_AUTH_BASIC: "yes"
        bunkerweb.io/AUTH_BASIC_LOCATION: "sitewide" # Ou "/secure" ou "^~ /admin/"
        bunkerweb.io/AUTH_BASIC_USER: "user"
        bunkerweb.io/AUTH_BASIC_PASSWORD: "password"  # Ou utiliser un Secret
        bunkerweb.io/AUTH_BASIC_USER_1: "user1"
        bunkerweb.io/AUTH_BASIC_PASSWORD_1: "otherpassword"  # Ou utiliser un Secret
        bunkerweb.io/AUTH_BASIC_TEXT: "Authentication Required"

        bunkerweb.io/WHITELIST_IP: "10.0.0.0/8 172.16.0.0/12"

        bunkerweb.io/USE_BAD_BEHAVIOR: "yes"

        bunkerweb.io/BLACKLIST_USER_AGENT: "bot crawler spider" # Ou regex PCRE
    spec:
      ingressClassName: bunkerweb
      tls:
      - hosts:
        - custom-app.example.com
        secretName: custom-app-tls
      rules:
      - host: custom-app.example.com
        http:
          paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: custom-app-service
                port:
                  number: 80

    ---
    # ConfigMap pour la configuration NGINX personnalisée
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: custom-app-nginx-config
      namespace: production
      annotations:
        # Indiquer qu'il s'agit d'une config HTTP pour ce site
        bunkerweb.io/CONFIG_TYPE: "http"
        bunkerweb.io/CONFIG_SITE: "custom-app.example.com"
    data:
      custom-rules.conf: |
        # Réécriture personnalisée
        rewrite ^/old-path/(.*)$ /new-path/$1 permanent;

        # En-têtes conditionnels pour les APIs
        location ^~ /api/ {
          add_header X-API-Gateway "true";
          proxy_pass http://custom-app-service.production.svc.cluster.local;
        }

        # Cache pour les assets statiques
        location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
          expires 7d;
          add_header Cache-Control "public, immutable";
          proxy_pass http://custom-app-service.production.svc.cluster.local;
        }

        # Proxy vers un service externe
        location /external-api {
          proxy_pass https://external-service.com;
          proxy_set_header Host external-service.com;
          proxy_ssl_server_name on;
        }
    ```

##### Comparaison : Fonctionnalités natives vs ConfigMap

| Règle NGINX                | Approche BunkerWeb                           |
| -------------------------- | -------------------------------------------- |
| `auth-type: basic`         | ✅ Annotation native : `USE_AUTH_BASIC`       |
| `whitelist-source-range`   | ✅ Annotation native : `WHITELIST_IP`         |
| `if ($http_user_agent ~*)` | ✅ Annotation native : `BLACKLIST_USER_AGENT` |
| `expires 7d` pour le cache | ✅ Annotation native : `USE_CLIENT_CACHE`     |
| `limit_conn addr 10`       | ✅ Annotation native : `USE_LIMIT_CONN`       |
| `rewrite` complexe         | ⚠️ ConfigMap : `CONFIG_TYPE: http`            |
| `location` personnalisée   | ⚠️ ConfigMap : `CONFIG_TYPE: http`            |
| `proxy_pass` externe       | ⚠️ ConfigMap : `CONFIG_TYPE: http`            |

## Swarm

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Intégration de Docker Swarm</figcaption>
</figure>

!!! warning "Obsolète"
    L'intégration de Swarm est obsolète et sera supprimée dans une version ultérieure. Veuillez envisager d'utiliser l' [intégration Kubernetes](#kubernetes) à la place.

!!! tip "Support PRO"
    **Si vous avez besoin d'aide sur l'intégration Swarm**, veuillez nous contacter au [contact@bunkerity.com](mailto:contact@bunkerity.com) ou via le formulaire de [contact](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc).

!!! info "Docker autoconf"
    L'intégration de Swarm est similaire à celle de Docker autoconf (mais avec des services au lieu de conteneurs). Veuillez d'abord lire la section sur l ['intégration de Docker autoconf](#docker-autoconf) si nécessaire.

Pour permettre la configuration automatique des instances BunkerWeb, le ** service autoconf** nécessite l'accès à l'API Docker. Ce service est à l'écoute des événements Docker Swarm, tels que la création ou la suppression de services, et configure de manière transparente les **instances BunkerWeb** en temps réel sans aucun temps d'arrêt. Il surveille également d'autres objets Swarm, tels que [les configurations](https://docs.docker.com/engine/swarm/configs/), pour les configurations personnalisées.

Semblable à l'[intégration Docker autoconf](#docker-autoconf), la configuration des services Web est définie à l'aide d'étiquettes qui commencent par le ** préfixe **bunkerweb.

Pour une configuration optimale, il est recommandé de planifier le **service BunkerWeb** en tant que ***service global*** sur tous les nœuds, tandis que les **services autoconf, scheduler et proxy Docker API** doivent être planifiés en tant que ***services répliqués uniques***. Veuillez noter que le service proxy de l'API Docker doit être planifié sur un nœud de gestionnaire, sauf si vous le configurez pour utiliser une API distante (ce qui n'est pas couvert dans la documentation).

Étant donné que plusieurs instances de BunkerWeb sont en cours d'exécution, un magasin de données partagé implémenté en tant que [ service Redis](https://redis.io/) ou [Valkey](https://valkey.io/) doit être créé. Ces instances utiliseront le service Redis/Valkey pour mettre en cache et partager des données. Vous trouverez plus de détails sur les paramètres Redis/Valkey [ici](features.md#redis).

En ce qui concerne le volume de la base de données, la documentation ne spécifie pas d'approche spécifique. Le choix d'un dossier partagé ou d'un pilote spécifique pour le volume de base de données dépend de votre cas d'utilisation unique et est laissé à la disposition du lecteur.

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez MariaDB comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, nous comprenons que vous préférerez peut-être utiliser d'autres backends pour votre intégration Docker. Si c'est le cas, soyez assuré que d'autres backends de base de données sont toujours possibles. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/misc/integrations) du dépôt.

      La configuration des backends de base de données en cluster est hors du périmètre de cette documentation.

Voici le passe-partout de la pile que vous pouvez déployer à l'aide de `docker stack deploy`:

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both services
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8
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
    image: bunkerity/bunkerweb-scheduler:1.6.8
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
    image: bunkerity/bunkerweb-autoconf:1.6.8
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

!!! info "Réglage obligatoire de l'swarm"
    Veuillez noter que la `SWARM_MODE: "yes"` variable d'environnement est obligatoire lors de l'utilisation de l'intégration Swarm.

!!! tip "Ignorer les services étiquetés"
    Besoin d'exclure un service Swarm d'autoconf ? Définissez `SWARM_IGNORE_LABELS` sur le contrôleur. Fournissez une liste de clés d'étiquettes séparées par des espaces ou des virgules (par exemple `bunkerweb.SERVER_NAME`) ou des suffixes (`SERVER_NAME`) et tout service portant ces étiquettes sera ignoré lors de la découverte.

### Services Swarm

Une fois que la pile BunkerWeb Swarm est configurée et en cours d'exécution (voir les journaux autoconf et scheduler pour plus d'informations), vous pourrez déployer des applications Web dans le cluster et utiliser des étiquettes pour configurer dynamiquement BunkerWeb :

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

### Espaces de noms {#namespaces_2}

À partir de la version `1.6.0`, les piles Autoconf de BunkerWeb supportent désormais les espaces de noms. Cette fonctionnalité vous permet de gérer plusieurs «* clusters *» d'instances et de services BunkerWeb sur le même hôte Docker. Pour tirer parti des espaces de noms, il vous suffit de définir l' `NAMESPACE` étiquette sur vos services. Voici un exemple :

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

!!! info "Comportement de l'espace de nommage"

    Par défaut, toutes les piles Autoconf écoutent tous les espaces de noms. Si vous souhaitez restreindre une pile à des espaces de noms spécifiques, vous pouvez définir la variable d'environnement `NAMESPACES` dans le service `bw-autoconf` :

    ```yaml
    ...
    services:
      bunkerweb:
      image: bunkerity/bunkerweb:1.6.8
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
      image: bunkerity/bunkerweb-autoconf:1.6.8
      environment:
        NAMESPACES: "my-namespace my-other-namespace" # Only listen to these namespaces
        ...
      deploy:
        placement:
        constraints:
          - "node.role == worker"
    ...
    ```

    Gardez à l'esprit que la variable d'environnement `NAMESPACES` est une liste d'espaces de noms séparés par des espaces.

!!! warning "Spécifications de l'espace de nommage"

    Il ne peut y avoir **qu'une seule base de données** et **un seul Scheduler** par espace de noms. Si vous tentez de créer plusieurs bases de données ou plusieurs Schedulers dans le même espace de noms, les configurations entreront en conflit.

    Le Scheduler n'a pas besoin de l'étiquette `NAMESPACE` pour fonctionner correctement. Il a seulement besoin que le paramètre `DATABASE_URI` soit correctement configuré afin qu'il puisse accéder à la même base de données que le service autoconf.
## Terraform Provider

### Introduction

Le provider Terraform pour BunkerWeb vous permet de gérer vos instances, services et configurations BunkerWeb via l'Infrastructure as Code (IaC). Ce provider interagit avec l'API BunkerWeb pour automatiser le déploiement et la gestion de vos configurations de sécurité.

### Prérequis

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.12
- Une instance BunkerWeb avec l'API activée
- Un token d'API ou des identifiants d'authentification basique

### Installation

Le provider est disponible sur le [Terraform Registry](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest). Ajoutez-le à votre configuration Terraform :

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

### Configuration

#### Authentification par Bearer token (recommandée)

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_token    = var.bunkerweb_token
}
```

#### Authentification basique

```terraform
provider "bunkerweb" {
  api_endpoint = "https://bunkerweb.example.com:8888"
  api_username = var.bunkerweb_username
  api_password = var.bunkerweb_password
}
```

### Exemples d'utilisation

#### Créer un service web

```terraform
resource "bunkerweb_service" "app" {
  server_name = "app.example.com"

  variables = {
    upstream = "10.0.0.12:8080"
    mode     = "production"
  }
}
```

#### Enregistrer une instance

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

#### Configurer un paramètre global

```terraform
resource "bunkerweb_global_config_setting" "retry" {
  key   = "retry_limit"
  value = "10"
}
```

#### Bannir une adresse IP

```terraform
resource "bunkerweb_ban" "suspicious_ip" {
  ip       = "192.0.2.100"
  reason   = "Multiple failed login attempts"
  duration = 3600  # 1 heure en secondes
}
```

#### Configuration personnalisée

```terraform
resource "bunkerweb_config" "custom_rules" {
  service_id = "app.example.com"
  type       = "http"
  name       = "custom-rules.conf"
  content    = file("${path.module}/configs/custom-rules.conf")
}
```

### Ressources disponibles

Le provider expose les ressources suivantes :

- **bunkerweb_service** : Gestion des services web
- **bunkerweb_instance** : Enregistrement et gestion des instances
- **bunkerweb_global_config_setting** : Configuration globale
- **bunkerweb_config** : Configurations personnalisées
- **bunkerweb_ban** : Gestion des bannissements IP
- **bunkerweb_plugin** : Installation et gestion des plugins

### Data sources

Les data sources permettent de lire des informations existantes :

- **bunkerweb_service** : Lecture d'un service existant
- **bunkerweb_global_config** : Lecture de la configuration globale
- **bunkerweb_plugins** : Liste des plugins disponibles
- **bunkerweb_cache** : Informations sur le cache
- **bunkerweb_jobs** : État des jobs planifiés

### Ressources éphémères

Pour des opérations ponctuelles :

- **bunkerweb_run_jobs** : Déclencher des jobs à la demande
- **bunkerweb_instance_action** : Exécuter des actions sur les instances (reload, stop, etc.)
- **bunkerweb_service_snapshot** : Capturer l'état d'un service
- **bunkerweb_config_upload** : Upload en masse de configurations

### Exemple complet

Voici un exemple d'infrastructure complète avec BunkerWeb :

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

# Configuration globale
resource "bunkerweb_global_config_setting" "rate_limit" {
  key   = "rate_limit"
  value = "10r/s"
}

# Service principal
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

# Service API avec configuration différente
resource "bunkerweb_service" "api" {
  server_name = "api.example.com"

  variables = {
    upstream        = "10.0.1.20:3000"
    mode            = "production"
    use_cors        = "yes"
    cors_allow_origin = "*"
  }
}

# Instance worker
resource "bunkerweb_instance" "worker1" {
  hostname     = "bw-worker-1.internal"
  name         = "Production Worker 1"
  port         = 8080
  listen_https = true
  https_port   = 8443
  server_name  = "bw-worker-1.internal"
  method       = "api"
}

# Configuration personnalisée pour le service webapp
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

# Bannir une IP suspecte
resource "bunkerweb_ban" "blocked_ip" {
  ip       = "203.0.113.50"
  reason   = "Detected malicious activity"
  duration = 86400  # 24 heures
}

output "webapp_service_id" {
  value = bunkerweb_service.webapp.id
}

output "api_service_id" {
  value = bunkerweb_service.api.id
}
```

### Ressources additionnelles

- [Documentation complète du provider](https://registry.terraform.io/providers/bunkerity/bunkerweb/latest/docs)
- [Dépôt GitHub](https://github.com/bunkerity/terraform-provider-bunkerweb)
- [Exemples d'utilisation](https://github.com/bunkerity/terraform-provider-bunkerweb/tree/main/examples)
- [Documentation de l'API BunkerWeb](https://docs.bunkerweb.io/latest/api/)

### Support et contribution

Pour signaler des bugs ou proposer des améliorations, rendez-vous sur le [dépôt GitHub du provider](https://github.com/bunkerity/terraform-provider-bunkerweb/issues).


## Microsoft Azure

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Intégration Azure</figcaption>
</figure>

!!! info "Taille de machine virtuelle recommandée"
    Soyez vigilant lorsque vous choisissez la référence SKU de la machine virtuelle. Vous devez sélectionner une référence SKU compatible avec la machine virtuelle Gen2 et nous vous recommandons de commencer par la série B2s ou Ds2 pour une utilisation optimale.

Vous pouvez facilement déployer BunkerWeb sur votre abonnement Azure de plusieurs manières :

- Azure CLI dans Cloud Shell
- Modèle Azure ARM
- Portail Azure via la Place de marché

=== "Cloud Shell"

    Créez un groupe de ressources. Remplacez la valeur `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    Créez une machine virtuelle avec la taille (SKU) `Standard_B2s` dans la même région que le groupe de ressources. Remplacez les valeurs `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    Commande complète. Remplacez les valeurs `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "Modèle ARM"

    !!! info "Exigences en matière d'autorisations"
        Pour déployer un modèle ARM, vous devez disposer d'un accès en écriture sur les ressources que vous déployez ainsi que de l'accès à toutes les opérations sur le type de ressource Microsoft.Resources/deployments.
        Pour déployer une machine virtuelle, vous avez besoin des autorisations Microsoft.Compute/virtualMachines/write et Microsoft.Resources/deployments/*. L'opération what-if requiert les mêmes autorisations.

    Déployer le modèle ARM :

    [![Déployer sur Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    Connectez-vous au [portail Azure](https://portal.azure.com){:target="_blank"}.

    Obtenez BunkerWeb depuis le menu [Créer une ressource](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}.

    Vous pouvez également passer par [le Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"}.

Vous pouvez accéder à l'assistant d'installation en parcourant l' `https://your-ip-address/setup` URI de votre machine virtuelle.
