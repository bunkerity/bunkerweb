# Utilisations avancées

De nombreux exemples de cas d'utilisation concrets sont disponibles dans le dossier [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.9/examples) du dépôt GitHub.

Nous fournissons également de nombreux modèles standard, tels que des fichiers YAML pour diverses intégrations et types de bases de données. Ceux-ci sont disponibles dans le dossier [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.9/misc/integrations).

Cette section se concentre uniquement sur les utilisations avancées et le réglage de la sécurité, consultez la [section fonctionnalités](features.md) de la documentation pour voir tous les paramètres disponibles.

!!! tip "Tester"
    Pour effectuer des tests rapides lorsque le mode multisite est activé (et si vous n'avez pas les bonnes entrées DNS configurées pour les domaines), vous pouvez utiliser curl avec l'en-tête HTTP Host de votre choix :
    ```shell
    curl -H "Host: app1.example.com" http://ip-or-fqdn-of-server
    ```

    Si vous utilisez HTTPS, vous devrez configurer le SNI :
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-of-server https://example.com
    ```

## Derrière l'équilibreur de charge ou le proxy inverse {#behind-load-balancer-or-reverse-proxy}

!!! info "Real IP"

    Lorsque BunkerWeb se trouve lui‑même derrière un équilibreur de charge ou un proxy inverse, vous devez le configurer afin qu'il puisse récupérer la véritable adresse IP des clients. **Si vous ne le faites pas, les fonctionnalités de sécurité bloqueront l'adresse IP de l'équilibreur de charge ou du proxy inverse au lieu de celle du client.**

BunkerWeb prend en fait en charge deux méthodes pour récupérer l'adresse IP réelle du client :

- À l'aide du `PROXY protocol`
- À l'aide d'un en-tête HTTP tel que `X-Forwarded-For`

Les paramètres suivants peuvent être utilisés :

- `USE_REAL_IP` : activer/désactiver la récupération d'IP réelle
- `USE_PROXY_PROTOCOL` : activer/désactiver la prise en charge du protocole PROXY.
- `REAL_IP_FROM` : liste d'adresses IP/réseau de confiance autorisées pour nous envoyer la "vraie IP"
- `REAL_IP_HEADER` : l'en-tête HTTP contenant l'IP réelle ou la valeur spéciale `proxy_protocol` lors de l'utilisation du protocole PROXY

Vous trouverez plus de paramètres sur l'IP réelle dans la [section des fonctionnalités](features.md#real-ip) de la documentation.

=== "En-tête HTTP"

    Nous supposerons ce qui suit concernant les équilibreurs de charge ou les proxies inverses (vous devrez mettre à jour les paramètres en fonction de votre configuration) :

    - Ils utilisent l'en-tête `X-Forwarded-For` pour définir l'adresse IP réelle
    - Ils ont des adresses IP dans les réseaux `1.2.3.0/24` et `100.64.0.0/10`

    === "Interface utilisateur Web"

        Accédez à la page **Config Globale**, sélectionnez le plugin **Real IP** et renseignez les paramètres suivants :

        <figure markdown>![Paramètres Real IP (en-tête) via l'interface Web](assets/img/advanced-proxy1.png){ align=center }<figcaption>Paramètres Real IP (en-tête) via l'interface Web</figcaption></figure>

        Veuillez noter qu'il est recommandé de redémarrer BunkerWeb lorsque vous modifiez des paramètres liés à la récupération de la vraie adresse IP.

    === "Linux"

        Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        Veuillez noter qu'il est recommandé de redémarrer plutôt que de recharger le service lorsque vous modifiez les paramètres liés à la récupération de la vraie adresse IP :

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "Tout-en-un"

        Vous devrez ajouter ces paramètres aux variables d'environnement lors de l'exécution du conteneur All-in-one :

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
            bunkerity/bunkerweb-all-in-one:1.6.9
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker autoconf"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Kubernetes"

        Vous devrez ajouter ces paramètres aux variables d'environnement des pods BunkerWeb et du Scheduler.

        Voici la partie correspondante de votre fichier `values.yaml` que vous pouvez utiliser :

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

        !!! warning "Obsolète"
            L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

            **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

        Vous devrez ajouter ces paramètres aux variables d'environnement des services BunkerWeb et scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

=== "Protocole proxy"

    !!! warning "Lire attentivement"

      N'utilisez le protocole `PROXY protocol` que si vous êtes certain que votre équilibreur de charge ou proxy inverse l'envoie. **Si vous l'activez et qu'il n'est pas utilisé, vous obtiendrez des erreurs**.

    Nous supposerons ce qui suit concernant les équilibreurs de charge ou les proxies inverses (vous devrez adapter les paramètres en fonction de votre configuration) :

    - Ils utilisent le `PROXY protocol` v1 ou v2 pour définir l'adresse IP réelle
    - Ils ont des adresses IP dans les réseaux `1.2.3.0/24` et `100.64.0.0/10`

    === "Interface utilisateur Web"

        Accédez à la page **Config Globale**, sélectionnez le plugin **Real IP** et renseignez les paramètres suivants :

        <figure markdown>![Paramètres Real IP (protocole PROXY) via l'interface Web](assets/img/advanced-proxy2.png){ align=center }<figcaption>Paramètres Real IP (protocole PROXY) via l'interface Web</figcaption></figure>

        Veuillez noter qu'il est recommandé de redémarrer BunkerWeb lorsque vous modifiez des paramètres liés à la récupération de la vraie adresse IP.

    === "Linux"

        Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        Veuillez noter qu'il est recommandé de redémarrer plutôt que de recharger le service lors de la configuration des paramètres liés au protocole PROXY :

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "Tout-en-un"

        Vous devrez ajouter ces paramètres aux variables d'environnement lors de l'exécution du conteneur All-in-one :

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
            bunkerity/bunkerweb-all-in-one:1.6.9
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Docker autoconf"

        Vous devrez ajouter ces paramètres aux variables d'environnement des conteneurs BunkerWeb et du Scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    === "Kubernetes"

        Vous devrez ajouter ces paramètres aux variables d'environnement des pods BunkerWeb et du Scheduler.

        Voici la partie correspondante de votre fichier `values.yaml` que vous pouvez utiliser :

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

        !!! warning "Obsolète"
            L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

            **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

        Vous devrez ajouter ces paramètres aux variables d'environnement des services BunkerWeb et scheduler :

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.9
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

## Haute disponibilité et répartition de charge

Pour garantir la disponibilité de vos applications même si un serveur tombe, vous pouvez déployer BunkerWeb en cluster **HA**. Cette architecture comporte un **Manager** (Scheduler) qui orchestre la configuration et plusieurs **Workers** (instances BunkerWeb) qui traitent le trafic.

```mermaid
flowchart LR

  %% ================ Styles =================
  classDef manager     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;
  classDef database fill:#d1fae5,stroke:#059669,stroke-width:1px,rx:4px,ry:4px;
  classDef datastore     fill:#fee2e2,stroke:#b91c1c,stroke-width:1px,rx:4px,ry:4px;
  classDef backend       fill:#ede9fe,stroke:#7c3aed,stroke-width:1px,rx:4px,ry:4px;
  classDef client        fill:#e5e7eb,stroke:#4b5563,stroke-width:1px,rx:4px,ry:4px;

  %% Container styles
  style CLUSTER fill:#f3f4f6,stroke:#d1d5db,stroke-width:1px,stroke-dasharray:6 3;
  style WORKERS fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:4 2;

  %% ============== Outside left =============
  Client["Client"]:::client
  LB["Load Balancer"]:::lb

  %% ============== Cluster ==================
  subgraph CLUSTER[" "]
    direction TB

    %% ---- Top row: Manager + Redis ----
    subgraph TOP["Manager & Data Stores"]
      direction LR
      Manager["Manager<br/>(Scheduler)"]:::manager
      BDD["BDD"]:::database
      Redis["Redis/Valkey"]:::datastore
      UI["Interface Web"]:::manager
    end

    %% ---- Middle: Workers ----
    subgraph WORKERS["Workers (BunkerWeb)"]
      direction TB
      Worker1["Worker 1"]:::component
      WorkerN["Worker N"]:::component
    end

    %% ---- Bottom: App ----
    App["App"]:::backend
  end

  %% ============ Outside right ============
  Admin["Admin"]:::client

  %% ============ Traffic & control ===========
  %% Manager / control plane
  Manager -->|API 5000| Worker1
  Manager -->|API 5000| WorkerN
  Manager -->|bwcli| Redis
  Manager -->|Config| BDD

  %% User interface (UI)
  UI -->|Config| BDD
  UI -->|Reports / Bans| Redis
  BDD --- UI
  Redis --- UI
  linkStyle 6 stroke-width:0px;
  linkStyle 7 stroke-width:0px;

  %% Workers <-> Redis
  Worker1 -->|Cache partagé| Redis
  WorkerN -->|Cache partagé| Redis

  %% Workers -> App
  Worker1 -->|Trafic légitime| App
  WorkerN -->|Trafic légitime| App

  %% Client (right side) -> Load balancer -> Workers -> App
  Client -->|Requête| LB
  LB -->|HTTP/TCP| Worker1
  LB -->|HTTP/TCP| WorkerN

  %% Admin -> UI
  UI --- Admin
  Admin -->|HTTP| UI
  linkStyle 15 stroke-width:0px;
```

!!! info "Comprendre les API BunkerWeb"
    BunkerWeb s'appuie sur deux notions d'API différentes :

    - Une **API interne** qui connecte automatiquement managers et workers pour l'orchestration. Elle est toujours activée et ne nécessite aucune configuration manuelle.
    - Un **service API** optionnel (`bunkerweb-api`) qui expose une interface REST publique pour les outils d'automatisation (bwcli, CI/CD, etc.). Il est désactivé par défaut sur les installations Linux et est indépendant des communications internes manager↔worker.

### Prérequis

Avant de mettre en place un cluster, assurez-vous de disposer de :

- **Au moins 2 hôtes Linux** avec accès root/sudo.
- **Connectivité réseau** entre les hôtes (en particulier sur le port TCP 5000 pour l'API interne).
- **L'IP ou le nom d'hôte** de l'application à protéger.
- *(Optionnel)* **Équilibreur de charge** (par ex. HAProxy) pour répartir le trafic entre les workers.

### 1. Installer le Manager

Le Manager est le cerveau du cluster. Il exécute le Scheduler, la base de données et, optionnellement, l'interface Web.

!!! warning "Sécurité de l'interface Web"
    L'interface Web écoute sur un port dédié (7000 par défaut) et ne doit être accessible qu'aux administrateurs. Si vous prévoyez de l'exposer à Internet, nous **recommandons fortement** de la protéger avec une instance BunkerWeb en frontal.

=== "Linux"

    1. **Télécharger et lancer l'installateur** sur l'hôte manager :

        ```bash
        # Télécharger le script et sa somme
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.9/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.9/install-bunkerweb.sh.sha256

        # Vérifier l'empreinte
        sha256sum -c install-bunkerweb.sh.sha256

        # Exécuter l'installateur
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "Avis de sécurité"
            Vérifiez toujours l'intégrité du script avec la somme fournie avant de l'exécuter.

    2. **Choisissez l'option 2) Manager** et suivez les invites :

        | Invite                       | Action                                                                                                      |
        | :--------------------------- | :---------------------------------------------------------------------------------------------------------- |
        | **Instances BunkerWeb**      | Saisissez les IP de vos nœuds worker séparées par des espaces (ex : `192.168.10.11 192.168.10.12`).         |
        | **Whitelist IP**             | Acceptez l'IP détectée ou saisissez un sous-réseau (ex : `192.168.10.0/24`) pour autoriser l'accès à l'API. |
        | **Résolveurs DNS**           | Appuyez sur `N` pour la valeur par défaut ou fournissez les vôtres.                                         |
        | **HTTPS pour l'API interne** | **Recommandé :** `Y` pour générer automatiquement des certificats et sécuriser les échanges manager-worker. |
        | **Service Web UI**           | `Y` pour activer l'interface Web (fortement recommandé).                                                    |
        | **Service API**              | `N` sauf besoin d'API REST publique pour des outils externes.                                               |

    #### Sécuriser et exposer l'UI

    Si vous avez activé l'interface Web, vous devez la sécuriser. Elle peut être hébergée sur le Manager ou une machine dédiée.

    === "Hébergée sur le Manager"

        1. Éditez `/etc/bunkerweb/ui.env` pour définir des identifiants forts :

        ```ini
        # OVERRIDE_ADMIN_CREDS=no
        ADMIN_USERNAME=admin
        ADMIN_PASSWORD=changeme
        # FLASK_SECRET=changeme
        # TOTP_ENCRYPTION_KEYS=changeme
        LISTEN_ADDR=0.0.0.0
        # LISTEN_PORT=7000
        FORWARDED_ALLOW_IPS=127.0.0.1,::1
        # ENABLE_HEALTHCHECK=no
        ```

        !!! warning "Changer les identifiants par défaut"
            Remplacez `admin` et `changeme` par des identifiants forts avant de démarrer le service UI en production.

        2. Redémarrez l'UI :

        ```bash
        sudo systemctl restart bunkerweb-ui
        ```

    === "Hôte externe"

        Pour plus d'isolation, installez l'UI sur un nœud séparé.

        1. Lancez l'installateur et choisissez **Option 5) Web UI Only**.
        2. Éditez `/etc/bunkerweb/ui.env` pour pointer vers la base du Manager :

            ```ini
            # Configuration base de données (doit correspondre à celle du Manager)
            DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb
            # Pour PostgreSQL : postgresql://bunkerweb:changeme@db-host:5432/bunkerweb
            # Pour MySQL : mysql+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb

            # Configuration Redis (si Redis/Valkey est utilisé pour la persistance)
            # Si non fourni, il est automatiquement pris depuis la base de données
            # REDIS_HOST=redis-host

            # Identifiants de sécurité
            ADMIN_USERNAME=admin
            ADMIN_PASSWORD=changeme

            # Réglages réseau
            LISTEN_ADDR=0.0.0.0
            # LISTEN_PORT=7000
            ```

        3. Redémarrez le service :

            ```bash
            sudo systemctl restart bunkerweb-ui
            ```

        !!! tip "Configuration du pare-feu"
            Assurez-vous que l'hôte UI peut joindre la base et Redis. Vous devrez peut-être ajuster les règles sur l'hôte UI ainsi que sur les hôtes base/Redis.

=== "Docker"

    Créez un fichier `docker-compose.yml` sur l'hôte manager :

    ```yaml title="docker-compose.yml"
    x-ui-env: &bw-ui-env
      # Nous ancrons les variables d'environnement pour éviter les duplications
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Pensez à mettre un mot de passe plus fort

    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "192.168.1.11 192.168.1.12" # Remplacez par les IPs de vos workers
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16" # Autoriser les réseaux locaux
          # API_LISTEN_HTTPS: "yes" # Recommandé pour sécuriser l'API interne
          # API_TOKEN: "my_secure_token" # Optionnel : définir un token supplémentaire
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # Persistance du cache et des sauvegardes
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        ports:
          - "7000:7000" # Exposer le port de l'UI
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remplacez par un mot de passe plus fort
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remplacez par une clé plus forte (voir la section Prérequis)
        restart: "unless-stopped"
        networks:
          - bw-db
          - bw-redis

      bw-db:
        image: mariadb:11
        # Nous fixons la taille max des paquets pour éviter les soucis de grosses requêtes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remplacez par un mot de passe plus fort
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis pour la persistance des rapports/bannissements/stats
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-redis

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-db:
        name: bw-db
      bw-redis:
        name: bw-redis
    ```

    Démarrez la pile manager :

    ```bash
    docker compose up -d
    ```

### 2. Installer les Workers

Les workers sont les nœuds qui traitent le trafic entrant.

=== "Linux"

    1. **Lancez l'installateur** sur chaque worker (mêmes commandes que pour le Manager).
    2. **Choisissez l'option 3) Worker** et répondez :

        | Invite                       | Action                                              |
        | :--------------------------- | :-------------------------------------------------- |
        | **IP du Manager**            | Saisissez l'IP du Manager (ex : `192.168.10.10`).   |
        | **HTTPS pour l'API interne** | Doit correspondre au choix du Manager (`Y` ou `N`). |

    Le worker s'enregistrera automatiquement auprès du Manager.

=== "Docker"

    Créez un fichier `docker-compose.yml` sur chaque worker :

    ```yaml title="docker-compose.yml"
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Support QUIC / HTTP3
          - "5000:5000/tcp" # Port de l'API interne
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16"
          # API_LISTEN_HTTPS: "yes" # Recommandé pour sécuriser l'API interne (doit correspondre au Manager)
          # API_TOKEN: "my_secure_token" # Optionnel : token supplémentaire (doit correspondre au Manager)
        restart: "unless-stopped"
    ```

    Démarrez le worker :

    ```bash
    docker compose up -d
    ```

### 3. Gérer les Workers

Vous pouvez ajouter d'autres workers plus tard via l'interface Web ou la CLI.

=== "Via l'interface Web"

    1. **Ouvrez l'onglet Instances**.
    2. **Cliquez sur Add instance**.
    3. **Renseignez l'IP/hostname du worker** puis enregistrez.

    <div class="grid grid-2" markdown style="display:grid; align-items:center;">
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - Création d'instance](assets/img/ui-ha-create-instance.webp){ width="100%" }
      <figcaption>BunkerWeb UI - Création d'instance</figcaption>
    </figure>
    <figure markdown style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;">
      ![BunkerWeb UI - Formulaire de création](assets/img/ui-ha-create-instance-form.webp){ width="100%" }
      <figcaption>BunkerWeb UI - Formulaire de création</figcaption>
    </figure>
    </div>

=== "Via la configuration"

    === "Linux"

        1. **Modifiez** `/etc/bunkerweb/variables.env` sur le Manager :

            ```bash
            BUNKERWEB_INSTANCES=192.168.10.11 192.168.10.12 192.168.10.13
            ```

        2. **Redémarrez le Scheduler** :

            ```bash
            sudo systemctl restart bunkerweb-scheduler
            ```

    === "Docker"

        1. **Modifiez** le fichier `docker-compose.yml` sur le Manager pour mettre à jour `BUNKERWEB_INSTANCES`.

        2. **Recréez le conteneur du Scheduler** :

            ```bash
            docker compose up -d bw-scheduler
            ```

### 4. Vérifier l'installation

=== "Linux"

    1. **Vérifier le statut** : connectez-vous à l'UI (`http://<ip-manager>:7000`) et ouvrez l'onglet **Instances**. Tous les workers doivent être **Up**.
    2. **Tester le basculement** : arrêtez BunkerWeb sur un worker (`sudo systemctl stop bunkerweb`) et vérifiez que le trafic continue de passer.

=== "Docker"

    1. **Vérifier le statut** : connectez-vous à l'UI (`http://<ip-manager>:7000`) et ouvrez l'onglet **Instances**. Tous les workers doivent être **Up**.
    2. **Tester le basculement** : arrêtez BunkerWeb sur un worker (`docker compose stop bunkerweb`) et vérifiez que le trafic continue de passer.

### 5. Répartition de charge

Pour répartir le trafic entre vos workers, utilisez un équilibreur de charge. Nous recommandons un équilibreur de couche 4 (TCP) qui supporte le **PROXY protocol** pour préserver l'IP client.

=== "HAProxy - Couche 4 (TCP)"

    Exemple de configuration **HAProxy** qui passe le trafic (mode TCP) tout en conservant l'IP client via le **PROXY protocol**.

    ```cfg title="haproxy.cfg"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode tcp
        bind *:80
        default_backend http_back

    frontend https_front
        mode tcp
        bind *:443
        default_backend https_back

    backend http_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:80 check send-proxy-v2
        server worker02 192.168.10.12:80 check send-proxy-v2

    backend https_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:443 check send-proxy-v2
        server worker02 192.168.10.12:443 check send-proxy-v2
    ```

=== "HAProxy - Couche 7 (HTTP)"

    Exemple de configuration **HAProxy** pour la répartition en couche 7 (HTTP). Elle ajoute l'en-tête `X-Forwarded-For` pour que BunkerWeb récupère l'IP client.

    ```cfg title="haproxy.cfg"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode http
        bind *:80
        default_backend http_back

    frontend https_front
        mode http
        bind *:443
        default_backend https_back

    backend http_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:80 check
        server worker02 192.168.10.12:80 check

    backend https_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:443 check
        server worker02 192.168.10.12:443 check
    ```

Rechargez HAProxy une fois la configuration enregistrée :

```bash
sudo systemctl restart haproxy
```

Pour plus d'informations, consultez la [documentation officielle HAProxy](http://docs.haproxy.org/).

!!! tip "Configurer l'IP réelle"
    N'oubliez pas de configurer BunkerWeb pour récupérer la véritable IP client (via PROXY protocol ou l'en-tête X-Forwarded-For).

    Reportez-vous à la section [Derrière l'équilibreur de charge ou le proxy inverse](#behind-load-balancer-or-reverse-proxy) pour vérifier que vous utilisez la bonne IP client.

    Consultez `/var/log/bunkerweb/access.log` sur chaque worker pour confirmer que les requêtes proviennent du réseau PROXY protocol et que les deux workers se partagent la charge. Votre cluster BunkerWeb est maintenant prêt pour la production avec haute disponibilité.

## Utilisation de mécanismes de résolution DNS personnalisés

La configuration NGINX de BunkerWeb peut être personnalisée pour utiliser différents résolveurs DNS en fonction de vos besoins. Cela peut être particulièrement utile dans divers scénarios :

1. Pour respecter les entrées de votre `/etc/hosts` fichier local
2. Lorsque vous devez utiliser des serveurs DNS personnalisés pour certains domaines
3. Pour s'intégrer à des solutions de mise en cache DNS locales

### Utilisation de systemd-resolved

De nombreux systèmes Linux modernes utilisent `systemd-resolved` la résolution DNS. Si vous souhaitez que BunkerWeb respecte le contenu de votre `/etc/hosts` fichier et utilise le mécanisme de résolution DNS du système, vous pouvez le configurer pour utiliser le service DNS local résolu par systemd.

Pour vérifier que systemd-resolved est en cours d'exécution sur votre système, vous pouvez utiliser :

```bash
systemctl status systemd-resolved
```

Pour activer systemd-resolved comme résolveur DNS dans BunkerWeb, définissez le `DNS_RESOLVERS` paramètre sur `127.0.0.53`, qui est l'adresse d'écoute par défaut pour systemd-resolved :

=== "Interface utilisateur Web"

    Accédez à la page **Config Globale** et définissez les résolveurs DNS sur `127.0.0.53`

    <figure markdown>![Paramètres des résolveurs DNS via l'interface Web](assets/img/advanced-dns-resolvers.png){ align=center }<figcaption>Paramètres des résolveurs DNS via l'interface Web</figcaption></figure>

=== "Linux"

    Vous devrez modifier le fichier /etc/bunkerweb/variables.env :

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    Après avoir effectué cette modification, rechargez le Scheduler pour appliquer la configuration :

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

### Utilisation de dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) est un serveur DNS, DHCP et TFTP léger qui est couramment utilisé pour la mise en cache et la personnalisation du DNS local. C'est particulièrement utile lorsque vous avez besoin de plus de contrôle sur votre résolution DNS que celui fourni par systemd-resolved.

=== "Linux"

    Tout d'abord, installez et configurez dnsmasq sur votre système Linux :

    === "Debian/Ubuntu"

        ```bash
        # Install dnsmasq
        sudo apt-get update && sudo apt-get install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # Install dnsmasq
        sudo dnf install dnsmasq

        # Configure dnsmasq to listen only on localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Add custom DNS entries if needed
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Restart dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    Ensuite, configurez BunkerWeb pour utiliser dnsmasq en définissant `DNS_RESOLVERS` sur `127.0.0.1` :

    === "Web UI"

        Accédez à la page **Config Globale** et sélectionnez le plugin **NGINX**, puis définissez les résolveurs DNS sur `127.0.0.1`.

        <figure markdown>![Paramètres des résolveurs DNS via l'interface Web](assets/img/advanced-dns-resolvers2.png){ align=center }<figcaption>Paramètres des résolveurs DNS via l'interface Web</figcaption></figure>

    === "Linux"

        Vous devrez modifier le fichier `/etc/bunkerweb/variables.env` :

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        Après avoir effectué cette modification, rechargez le Scheduler pour appliquer la configuration :

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "Tout-en-un"

    Lorsque vous utilisez l'image All-in-one, exécutez dnsmasq dans un conteneur séparé et configurez BunkerWeb pour l'utiliser :

    ```bash
    # Create a custom network for DNS communication
    docker network create bw-dns

    # Run dnsmasq container using dockurr/dnsmasq with Quad9 DNS
    # Quad9 provides security-focused DNS resolution with malware blocking
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

    # Run BunkerWeb All-in-one with dnsmasq DNS resolver
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.9
    ```

=== "Docker"

    Ajoutez un service dnsmasq à votre fichier docker-compose et configurez BunkerWeb pour l'utiliser :

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # Using Quad9 DNS servers for enhanced security and privacy
          # Primary: 9.9.9.9 (Quad9 with malware blocking)
          # Secondary: 149.112.112.112 (Quad9 backup server)
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
        image: bunkerity/bunkerweb:1.6.9
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...existing networks...
      bw-dns:
        name: bw-dns
    ```

## Configurations personnalisées {#custom-configurations}

Pour personnaliser et ajouter des configurations personnalisées à BunkerWeb, vous pouvez profiter de sa base NGINX. Des configurations NGINX personnalisées peuvent être ajoutées dans différents contextes NGINX, y compris des configurations pour le pare-feu d'applications Web (WAF) ModSecurity, qui est un composant central de BunkerWeb. Vous trouverez plus de détails sur les configurations de ModSecurity [ici](features.md#custom-configurations).

Voici les types de configurations personnalisées disponibles :

- **http** : Configurations au niveau HTTP de NGINX.
- **server-http** : configurations au niveau HTTP/Server de NGINX.
- **default-server-http**: configurations au niveau du serveur de NGINX, en particulier pour le "serveur par défaut" lorsque le nom de client fourni ne correspond à aucun nom de serveur dans `SERVER_NAME`.
- **modsec-crs**: Configurations appliquées avant le chargement de l'ensemble de règles de base OWASP.
- **modsec**: configurations appliquées après le chargement de l'ensemble de règles de base OWASP ou utilisées lorsque l'ensemble de règles de base n'est pas chargé.
- **crs-plugins-before**: Configurations pour les plugins CRS, appliquées avant le chargement des plugins CRS.
- **crs-plugins-after**: Configurations pour les plugins CRS, appliquées après le chargement des plugins CRS.
- **stream** : Configurations au niveau du flux de NGINX.
- **server-stream** : Configurations au niveau Stream/Server de NGINX.

Les configurations personnalisées peuvent être appliquées globalement ou spécifiquement pour un serveur particulier, en fonction du contexte applicable et de l'activation ou non du [mode multisite](features.md#multisite-mode) .

La méthode d'application des configurations personnalisées dépend de l'intégration utilisée. Cependant, le processus sous-jacent implique l'ajout de fichiers avec le `.conf` suffixe à des dossiers spécifiques. Pour appliquer une configuration personnalisée à un serveur spécifique, le fichier doit être placé dans un sous-dossier nommé d'après le nom du serveur principal.

Certaines intégrations offrent des moyens plus pratiques d'appliquer des configurations, par exemple à l'aide de [Configs](https://docs.docker.com/engine/swarm/configs/) dans Docker Swarm ou de [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) dans Kubernetes. Ces options offrent des approches plus simples pour la gestion et l'application des configurations.

=== "Interface utilisateur Web"

    Accédez à la page **Configs**, cliquez sur **Create new custom config**, puis choisissez s'il s'agit d'une configuration globale ou spécifique à un service, le type de configuration et le nom de la configuration :

    <figure markdown>![Configurations personnalisées via l'interface Web](assets/img/advanced-config.png){ align=center }<figcaption>Configurations personnalisées via l'interface Web</figcaption></figure>

    N'oubliez pas de cliquer sur le bouton `💾 Enregistrer`.

=== "Linux"

    Lorsque vous utilisez l'intégration [Linux](integrations.md#linux), les configurations personnalisées doivent être écrites dans le dossier `/etc/bunkerweb/configs`.

    Voici un exemple pour server-http/hello-world.conf :

    ```nginx
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Comme BunkerWeb s'exécute en tant qu'utilisateur non privilégié (nginx:nginx), vous devrez modifier les permissions :

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    Vérifions maintenant l'état du Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    S'ils sont déjà en cours d'exécution, nous pouvons le recharger :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Tout-en-un"

    Lorsque vous utilisez l'image [Tout-en-un](integrations.md#all-in-one-aio-image), vous avez deux options pour ajouter des configurations personnalisées :

    - Utilisation de paramètres spécifiques `*_CUSTOM_CONF_*` comme variables d'environnement lors de l'exécution du conteneur (recommandé).
    - Écriture `.conf` de fichiers dans le `/data/configs/` répertoire du volume monté sur `/data`.

    **Utilisation des paramètres (variables d'environnement)**

    Les paramètres à utiliser doivent suivre le schéma `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<SITE>` : Nom du serveur primaire facultatif si le mode multisite est activé et que la configuration doit être appliquée à un service spécifique.
    - `<TYPE>` : Le type de configuration, les valeurs acceptées sont `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP` `MODSEC` `MODSEC_CRS` `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER` `STREAM` , et `SERVER_STREAM`.
    - `<NAME>` : Le nom de la configuration sans le `.conf` suffixe.

    Voici un exemple fictif lors de l'exécution du conteneur All-in-one :

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
        bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    Veuillez noter que si votre conteneur est déjà créé, vous devrez le supprimer et le recréer pour que les nouvelles variables d'environnement soient appliquées.

    **Utilisation de fichiers**

    La première chose à faire est de créer les dossiers :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Vous pouvez maintenant écrire vos configurations :

    ```shell
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Étant donné que le Scheduler s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les autorisations :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Au démarrage du conteneur de l'ordonnanceur, vous devrez monter le dossier sur /data :

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.9
    ```

=== "Docker"

    Lorsque vous utilisez l'intégration [Docker](integrations.md#docker), vous avez deux options pour ajouter des configurations personnalisées :

    - Utilisation de paramètres spécifiques `*_CUSTOM_CONF_*` comme variables d'environnement (recommandé)
    - Écriture des fichiers .conf sur le volume monté sur /data de l'ordonnanceur

    **Utilisation des paramètres**

    Les paramètres à utiliser doivent suivre le schéma `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<SITE>` : nom de serveur primaire facultatif si le mode multisite est activé et que la configuration doit être appliquée à un service spécifique
    - `<TYPE>` : le type de configuration, les valeurs acceptées sont `HTTP`, `DEFAULT_SERVER_HTTP` `SERVER_HTTP` `MODSEC` `MODSEC_CRS` `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` , et `SERVER_STREAM`
    - `<NAME>` : le nom de config sans le suffixe .conf

    Voici un exemple factice utilisant un fichier docker-compose :

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.9
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

    **Utilisation de fichiers**

    La première chose à faire est de créer les dossiers :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Vous pouvez maintenant écrire vos configurations :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Étant donné que le Scheduler s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les autorisations :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Au démarrage du conteneur de l'ordonnanceur, vous devrez monter le dossier sur /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.9
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    Lorsque vous utilisez l'intégration [Docker autoconf](integrations.md#docker-autoconf), vous avez deux options pour ajouter des configurations personnalisées :

    - Utilisation de paramètres spécifiques `*_CUSTOM_CONF_*` comme étiquettes (le plus simple)
    - Écriture des fichiers .conf sur le volume monté sur /data de l'ordonnanceur

    **Utilisation des étiquettes**

    !!! warning "Limitations de l'utilisation des étiquettes"
        Lorsque vous utilisez des étiquettes avec l'intégration Docker autoconf, vous ne pouvez appliquer des configurations personnalisées que pour le service web correspondant. L'application de **http**, **default-server-http**, **stream** ou de tout paramètre global (comme **server-http** ou **server-stream** pour tous les services) n'est pas possible : vous devrez monter des fichiers à cet effet.

    Les étiquettes à utiliser doivent suivre le modèle `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>` :

    - `<TYPE>` : le type de configuration, les valeurs acceptées sont `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE` `CRS_PLUGINS_AFTER` et `SERVER_STREAM`
    - `<NAME>` : le nom de config sans le suffixe .conf

    Voici un exemple factice utilisant un fichier docker-compose :

    ```yaml
    myapp:
      image: bunkerity/bunkerweb-hello:v1.0
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

    **Utilisation de fichiers**

    La première chose à faire est de créer les dossiers :

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Vous pouvez maintenant écrire vos configurations :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Étant donné que le Scheduler s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les autorisations :

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Au démarrage du conteneur de l'ordonnanceur, vous devrez monter le dossier sur /data :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.9
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    Lors de l'utilisation de l'[intégration Kubernetes](integrations.md#kubernetes),
    les configurations personnalisées sont gérées à l'aide de [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    Vous n'avez pas besoin de monter la ConfigMap dans un Pod (par exemple en variable d'environnement ou en volume).
    Le pod autoconf surveille les événements ConfigMap et applique automatiquement la configuration dès qu'une modification est détectée.

    Annotez chaque ConfigMap que le contrôleur Ingress doit gérer :

    - `bunkerweb.io/CONFIG_TYPE` : obligatoire. Choisissez un type pris en charge (`http`, `server-http`, `default-server-http`, `modsec`,
      `modsec-crs`, `crs-plugins-before`, `crs-plugins-after`, `stream`, `server-stream` ou `settings`).
    - `bunkerweb.io/CONFIG_SITE` : optionnel. Indiquez le nom de serveur principal (tel qu'exposé via votre `Ingress`)
      pour limiter la configuration à ce service ; laissez vide pour l'appliquer globalement.

    Voici l'exemple :

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

    !!! info "Fonctionnement de la synchronisation"
        - Le contrôleur Ingress surveille en continu les ConfigMap annotées.
        - Si la variable d'environnement `NAMESPACES` est définie, seules les ConfigMap de ces espaces de noms sont prises en compte.
        - La création ou la mise à jour d'une ConfigMap gérée déclenche immédiatement un rechargement de la configuration.
        - La suppression de la ConfigMap – ou de l'annotation `bunkerweb.io/CONFIG_TYPE` – supprime la configuration personnalisée associée.
        - Si vous définissez `bunkerweb.io/CONFIG_SITE`, le service référencé doit déjà exister ; sinon, la ConfigMap est ignorée jusqu'à son apparition.

    !!! tip "Custom Extra Config"
        Depuis la version `1.6.0`, vous pouvez ajouter ou remplacer des paramètres en annotant une ConfigMap avec `bunkerweb.io/CONFIG_TYPE=settings`.
        Le contrôleur Ingress d'autoconf lit chaque entrée de `data` et l'applique comme une variable d'environnement :

        - Sans `bunkerweb.io/CONFIG_SITE`, toutes les clés sont appliquées globalement.
        - Lorsque `bunkerweb.io/CONFIG_SITE` est défini, le contrôleur ajoute automatiquement le préfixe `<nom-de-serveur>_` (chaque `/` est remplacé par `_`) aux clés qui ne sont pas déjà spécifiques. Ajoutez ce préfixe vous-même si vous devez mélanger des clés globales et spécifiques dans la même ConfigMap.
        - Les noms ou valeurs invalides sont ignorés et un avertissement est enregistré dans les journaux du contrôleur autoconf.

        Exemple :

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # multisite setting that will be applied to all services that do not override it
          USE_REDIS: "yes" # global setting that will be applied globally
          ...
        ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Lorsque vous utilisez l'[Swarm integration](integrations.md#swarm), les configurations personnalisées sont gérées à l'aide des [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    Pour simplifier, vous n'avez même pas besoin d'attacher le Config à un service : le service d'autoconf écoute les événements Config et mettra à jour les configurations personnalisées lorsque nécessaire.

    Lors de la création d'un Config, vous devrez ajouter des labels spéciaux :

    * **bunkerweb.CONFIG_TYPE** : doit être défini sur un type de configuration personnalisé valide (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream, server-stream ou settings)
    * **bunkerweb.CONFIG_SITE** : défini sur un nom de serveur pour appliquer la configuration à ce serveur spécifique (facultatif, sera appliqué globalement s'il n'est pas défini)

    Voici l'exemple :

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    Il n'y a pas de mécanisme de mise à jour : l'alternative est de supprimer une configuration existante à l'aide puis de `docker config rm` la recréer.

## Exécution de nombreux services en production {#running-many-services-in-production}

### CRS mondial

!!! warning "Plugins CRS"
    Lorsque le SCR est chargé globalement, les **plug-ins SCR ne sont pas pris en charge**. Si vous avez besoin de les utiliser, vous devrez charger le SCR par service.

Si vous utilisez BunkerWeb en production avec un grand nombre de services, et que vous activez la **fonctionnalité ModSecurity globalement** avec des règles CRS, le temps nécessaire pour charger les configurations BunkerWeb peut devenir trop long, ce qui peut entraîner un délai d'expiration.

La solution de contournement consiste à charger les règles CRS globalement plutôt que par service. Ce comportement n'est pas activé par défaut pour des raisons de compatibilité descendante et parce qu'il présente un inconvénient : si vous activez le chargement des règles CRS globales, **il ne sera plus possible de définir des règles modsec-crs** (exécutées avant les règles CRS) par service. Cependant, cette limitation peut être contournée en écrivant des règles d'exclusion globales `modsec-crs` comme suit :

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

Vous pouvez activer le chargement global du SCR en définissant `USE_MODSECURITY_GLOBAL_CRS` la valeur . `yes`

### Ajuster max_allowed_packet pour MariaDB/MySQL

Il semble que la valeur par défaut du `max_allowed_packet` paramètre dans les serveurs de bases de données MariaDB et MySQL ne soit pas suffisante lors de l'utilisation de BunkerWeb avec un grand nombre de services.

Si vous rencontrez des erreurs comme celle-ci, en particulier sur le Scheduler :

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

Vous devrez augmenter le `max_allowed_packet` sur votre serveur de base de données.

## Persistance des interdictions et des signalements {#persistence-of-bans-and-reports}

Par défaut, BunkerWeb stocke les bannissements et les rapports dans un magasin de données Lua local. Bien que simple et efficace, cette configuration signifie que des données sont perdues lors du redémarrage de l'instance. Pour vous assurer que les bannissements et les rapports persistent lors des redémarrages, vous pouvez configurer BunkerWeb pour utiliser un [ serveur Redis](https://redis.io/) ou [Valkey](https://valkey.io/) distant  .

**Pourquoi utiliser Redis/Valkey ?**

Redis et Valkey sont de puissants magasins de données en mémoire couramment utilisés comme bases de données, caches et courtiers de messages. Ils sont hautement évolutifs et prennent en charge une variété de structures de données, notamment :

- **Chaînes**: paires clé-valeur de base.
- **Hachages**: paires champ-valeur au sein d'une seule clé.
- **Listes**: collections ordonnées de chaînes.
- **Ensembles**: collections non ordonnées de chaînes uniques.
- **Ensembles triés**: Collections ordonnées avec partitions.

En tirant parti de Redis ou de Valkey, BunkerWeb peut stocker de manière persistante les bannissements, les rapports et les données de cache, garantissant ainsi la durabilité et l'évolutivité.

**Activation de la prise en charge Redis/Valkey**

Pour activer la prise en charge de Redis ou Valkey, configurez les paramètres suivants dans votre fichier de configuration BunkerWeb :

```conf
# Enable Redis/Valkey support
USE_REDIS=yes

# Redis/Valkey server hostname or IP address
REDIS_HOST=<hostname>

# Redis/Valkey server port number (default: 6379)
REDIS_PORT=6379

# Redis/Valkey database number (default: 0)
REDIS_DATABASE=0
```

- **`USE_REDIS`**: Réglez sur `yes` pour activer l'intégration Redis/Valkey.
- **`REDIS_HOST`**: Spécifiez le nom d'hôte ou l'adresse IP du serveur Redis/Valkey.
- **`REDIS_PORT`**: Spécifiez le numéro de port pour le serveur Redis/Valkey. La valeur par défaut est `6379`.
- **`REDIS_DATABASE`**: Indiquez le numéro de base de données Redis/Valkey à utiliser. La valeur par défaut est `0`.

Si vous avez besoin de paramètres plus avancés, tels que l'authentification, la prise en charge SSL/TLS ou le mode Sentinel, reportez-vous à la documentation sur les paramètres du [plug-in Redis](features.md#redis) pour obtenir des conseils détaillés.

## Protéger les applications UDP/TCP

!!! example "Fonctionnalité expérimentale"

	  This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

BunkerWeb offre la possibilité de fonctionner comme un **proxy inverse UDP/TCP générique**, ce qui vous permet de protéger toutes les applications basées sur le réseau fonctionnant au moins sur la couche 4 du modèle OSI. Au lieu d'utiliser le module HTTP "classique", BunkerWeb exploite le [module de flux](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) de NGINX.

Il est important de noter que **tous les paramètres et fonctionnalités de sécurité ne sont pas disponibles lors de l'utilisation du module de flux**. Vous trouverez de plus amples informations à ce sujet dans les sections des [fonctionnalités](features.md) de la documentation.

La configuration d'un proxy inverse de base est assez similaire à la configuration HTTP, car elle implique l'utilisation des mêmes paramètres : `USE_REVERSE_PROXY=yes` et `REVERSE_PROXY_HOST=myapp:9000`. Même lorsque BunkerWeb est positionné derrière un équilibreur de charge, les paramètres restent les mêmes (le **protocole PROXY** étant l'option prise en charge pour des raisons évidentes).

En plus de cela, les paramètres spécifiques suivants sont utilisés :

- `SERVER_TYPE=stream` : activer  le `stream` mode (UDP/TCP générique) au lieu d' `http` un (qui est la valeur par défaut)
- `LISTEN_STREAM_PORT=4242` : le port d'écoute "simple" (sans SSL/TLS) sur lequel BunkerWeb écoutera
- `LISTEN_STREAM_PORT_SSL=4343` : le port d'écoute "ssl/tls" sur lequel BunkerWeb écoutera
- `USE_UDP=no` : écouter et transférer les paquets UDP au lieu de TCP

Pour la liste complète des paramètres concernant `stream` le  mode, veuillez vous référer à la sections des [fonctionnalités](features.md) de la documentation.

!!! tip "Plusieurs ports d'écoute"

    Depuis la version `1.6.0`, BunkerWeb prend en charge plusieurs ports d'écoute pour le mode `stream`. Vous pouvez les spécifier à l'aide des paramètres `LISTEN_STREAM_PORT` et `LISTEN_STREAM_PORT_SSL`.

    Voici un exemple :

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "Tout-en-un"

    Vous devrez ajouter ces paramètres aux variables d'environnement lors de l'exécution du conteneur All-in-one. Vous devrez également exposer les ports de stream.

    Cet exemple configure BunkerWeb pour agir comme proxy inverse pour deux applications basées sur le mode stream : `app1.example.com` et `app2.example.com`.

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
        bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    Veuillez noter que si votre conteneur existe déjà, vous devrez le supprimer et le recréer afin que les nouvelles variables d'environnement soient prises en compte.

    Vos applications (`myapp1`, `myapp2`) doivent s'exécuter dans des conteneurs séparés (ou être autrement accessibles) et leurs noms d'hôte/adresses IP (par ex. `myapp1`, `myapp2` utilisés dans `_REVERSE_PROXY_HOST`) doivent être résolubles et atteignables depuis le conteneur `bunkerweb-aio`. Cela implique généralement de les connecter à un réseau Docker partagé.

    !!! note "Désactiver le service UI"
        Il est recommandé de désactiver le service d'interface Web (par exemple en définissant la variable d'environnement `SERVICE_UI=no`) car l'interface Web n'est pas compatible avec `SERVER_TYPE=stream`.

=== "Docker"

    Lors de l'utilisation de l'intégration Docker, la manière la plus simple de protéger des applications réseau existantes est d'ajouter les services au réseau `bw-services` :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
      # Jeton API optionnel pour les appels API authentifiés
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
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
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # Will be applied to all services
          SERVER_TYPE: "stream" # Will be applied to all services
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
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

    Avant d'exécuter la pile de l'intégration [Docker autoconf](integrations.md#docker-autoconf) sur votre machine, vous devrez modifier les ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080" # Keep it if you want to use Let's Encrypt automation when using http challenge type
          - "10000:10000" # app1
          - "20000:20000" # app2
    ...
    ```

    Une fois la pile en cours d'exécution, vous pouvez connecter vos applications existantes au réseau `bw-services` et configurer BunkerWeb avec des `labels` :

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

    !!! example "Fonctionnalité expérimentale"

        Actuellement, les [Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) ne prennent pas en charge le mode `stream`. **Ce que nous proposons ici est une solution de contournement pour le faire fonctionner.**

        N'hésitez pas à le tester et à nous signaler tout bug en ouvrant une issue via [issues](https://github.com/bunkerity/bunkerweb/issues) du dépôt GitHub.

    Avant d'exécuter la pile de l'[intégration Kubernetes](integrations.md#kubernetes) sur votre machine, vous devrez ouvrir les ports sur votre équilibreur de charge :

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # Keep it if you want to use Let's Encrypt automation when using http challenge type
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

    Une fois la pile en cours d'exécution, vous pouvez créer vos ressources Ingress :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # Will be applied to all services
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # This isn't used in stream mode but is required
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

    Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

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

    Vérifions maintenant l'état du Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    S'ils sont déjà en cours d'exécution, nous pouvons le recharger :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Avant d'exécuter la pile de l'intégration [Swarm](integrations.md#swarm) sur votre machine, vous devrez modifier les ports :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
        ports:
          # Keep it if you want to use Let's Encrypt automation when using http challenge type
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

    Une fois la pile en cours d'exécution, vous pouvez connecter vos applications existantes au réseau `bw-services` et configurer BunkerWeb à l'aide d'étiquettes :

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

## Le PHP

!!! example "Fonctionnalité expérimentale"
	  Pour le moment, le support PHP avec BunkerWeb est encore en version bêta et nous vous recommandons d'utiliser une architecture de proxy inverse si vous le pouvez. D'ailleurs, PHP n'est pas du tout pris en charge pour certaines intégrations comme Kubernetes.

BunkerWeb prend en charge PHP en utilisant des  instances [PHP-FPM externes ou ](https://www.php.net/manual/en/install.fpm.php) distantes. Nous supposerons que vous êtes déjà familiarisé avec la gestion de ce type de services.

 Les paramètres suivants peuvent être utilisés :

- `REMOTE_PHP` : Nom d'hôte de l'instance PHP-FPM distante.
- `REMOTE_PHP_PATH` : Dossier racine contenant les fichiers dans l'instance PHP-FPM distante.
- `REMOTE_PHP_PORT` : Port de l'instance PHP-FPM distante (*9000 par défaut*).
- `LOCAL_PHP` : Chemin d'accès au fichier socket local de l'instance PHP-FPM.
- `LOCAL_PHP_PATH` : Dossier racine contenant les fichiers dans l'instance locale PHP-FPM.

=== "Tout-en-un"

    Lorsque vous utilisez l'image [Tout-en-un](integrations.md#all-in-one-aio-image), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb.
    - Configurez un conteneur PHP-FPM pour votre application et montez le dossier contenant les fichiers PHP.
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme variables d'environnement lors de l'exécution de BunkerWeb.

    Si vous activez le [mode multisite](features.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 directories, 2 files
    ```

    Nous supposerons que vos applications PHP se trouvent dans un dossier nommé `www`. Veuillez noter que vous devrez corriger les permissions pour que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Vous pouvez maintenant exécuter BunkerWeb, le configurer pour votre application PHP et également exécuter les applications PHP. Vous devrez créer un réseau Docker personnalisé pour permettre à BunkerWeb de communiquer avec vos conteneurs PHP-FPM.

    ```bash
    # Create a custom network
    docker network create php-network

    # Run PHP-FPM containers
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # Run BunkerWeb All-in-one
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
        bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    Veuillez noter que si votre conteneur est déjà créé, vous devrez le supprimer et le recréer pour que les nouvelles variables d'environnement soient appliquées.

=== "Docker"

    Lors de l'utilisation de l'intégration [Docker](integrations.md#docker), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb
    - Configurez un conteneur PHP-FPM pour votre application et montez le dossier contenant les fichiers PHP
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme variables d'environnement lors du démarrage de BunkerWeb

    Si vous activez le [mode multisite](features.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

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

    Nous supposerons que vos applications PHP se trouvent dans un dossier nommé `www`. Veuillez noter que vous devrez corriger les permissions pour que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Vous pouvez maintenant exécuter BunkerWeb, le configurer pour votre application PHP et également exécuter les applications PHP :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
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
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # Will be applied to all services thanks to the MULTISITE setting
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
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

    !!! info "Mode multisite activé"
        L'intégration [Docker autoconf](integrations.md#docker-autoconf) implique l'utilisation du mode multisite : protéger une application PHP équivaut à protéger plusieurs.

    Lors de l'utilisation de l'intégration [Docker autoconf](integrations.md#docker-autoconf), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb
    - Configurez un conteneur PHP-FPM pour vos applications et montez le dossier contenant les applications PHP
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme étiquettes pour votre conteneur PHP-FPM

    Comme l'autoconf de Docker implique d'utiliser le [mode multisite](features.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

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

    Une fois les dossiers créés, copiez vos fichiers et corrigez les permissions afin que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Lorsque vous démarrez la pile autoconf de BunkerWeb, montez le `www` dossier dans `/var/www/html` le  conteneur **Scheduler** :

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for all services
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
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
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.9
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

    Vous pouvez maintenant créer vos conteneurs PHP-FPM, monter les bons sous-dossiers et utiliser des libellés pour configurer BunkerWeb :

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

    !!! warning "PHP n'est pas pris en charge pour Kubernetes"
      L'intégration Kubernetes permet la configuration via [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) et le contrôleur BunkerWeb ne prend actuellement en charge que les applications HTTP.

=== "Linux"

    Nous supposerons que vous avez déjà la pile d'intégration [Linux integration](integrations.md#linux) en cours d'exécution sur votre machine.

    Par défaut, BunkerWeb recherchera les fichiers web dans le dossier /var/www/html. Vous pouvez l'utiliser pour stocker vos applications PHP. Veuillez noter que vous devrez configurer votre service PHP-FPM pour définir l'utilisateur/groupe des processus en cours et le fichier de socket UNIX utilisé pour communiquer avec BunkerWeb.

    Tout d'abord, assurez-vous que votre instance PHP-FPM peut accéder aux fichiers situés dans /var/www/html et que BunkerWeb peut accéder au fichier de socket UNIX afin de communiquer avec PHP-FPM. Il est recommandé d'utiliser un utilisateur distinct tel que www-data pour le service PHP-FPM et d'autoriser le groupe nginx à accéder au fichier de socket UNIX. Voici la configuration PHP-FPM correspondante :

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

    N'oubliez pas de redémarrer votre service PHP-FPM :

    ```shell
    systemctl restart php-fpm
    ```

    Si vous activez le [mode multisite](features.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé en utilisant la première valeur de `SERVER_NAME`. Voici un exemple fictif :

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

    Veuillez noter que vous devrez corriger les permissions afin que BunkerWeb (groupe `nginx`) puisse au moins lire les fichiers et lister les dossiers, et que PHP-FPM (utilisateur `www-data`, qui peut varier selon votre système) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    Vous pouvez maintenant éditer le fichier `/etc/bunkerweb/variable.env` :

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

    Vérifions maintenant l'état du Scheduler :

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    S'il est déjà en cours d'exécution, nous pouvons le recharger :

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    !!! info "Mode multisite activé"
        L'intégration [Swarm](integrations.md#docker-autoconf) implique l'utilisation du mode multisite : protéger une application PHP équivaut à protéger plusieurs applications.

    !!! info "Volume partagé"
        L'utilisation de PHP avec l'intégration Docker Swarm nécessite un volume partagé entre toutes les instances BunkerWeb et PHP-FPM, ce qui n'est pas couvert dans cette documentation.

    Lors de l'utilisation de l'intégration [Swarm](integrations.md#swarm), pour prendre en charge les applications PHP, vous devrez :

    - Montez vos fichiers PHP dans le `/var/www/html` dossier de BunkerWeb
    - Configurez un conteneur PHP-FPM pour vos applications et montez le dossier contenant les applications PHP
    - Utilisez les paramètres spécifiques `REMOTE_PHP` et `REMOTE_PHP_PATH` comme étiquettes pour votre conteneur PHP-FPM

    Étant donné que l'intégration de Swarm implique l'utilisation du [mode multisite](features.md#multisite-mode), vous devrez créer des répertoires distincts pour chacune de vos applications. Chaque sous-répertoire doit être nommé à l'aide de la première valeur de `SERVER_NAME`. Voici un exemple fictif :

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

    À titre d'exemple, nous considérerons que vous avez un dossier partagé monté sur vos nœuds de travail sur le point de `/shared` terminaison.

    Une fois les dossiers créés, copiez vos fichiers et corrigez les permissions afin que BunkerWeb (UID/GID 101) puisse au moins lire les fichiers et lister les dossiers et PHP-FPM (UID/GID 33 si vous utilisez l' `php:fpm` image) soit le propriétaire des fichiers et dossiers :

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

    Lorsque vous démarrez la pile BunkerWeb, montez le dossier /shared/www sur /var/www/html dans le conteneur **Scheduler** :

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.9
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    Vous pouvez maintenant créer vos services PHP-FPM, monter les sous-dossiers appropriés et utiliser des labels pour configurer BunkerWeb :

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

## IPv6

!!! example "Fonctionnalité expérimentale"

    Cette fonctionnalité n'est pas prête pour la production. N'hésitez pas à la tester et à nous signaler tout bug via les [issues](https://github.com/bunkerity/bunkerweb/issues) du dépôt GitHub.

Par défaut, BunkerWeb n'écoutera que les adresses IPv4 et n'utilisera pas IPv6 pour les communications réseau. Si vous souhaitez activer la prise en charge d'IPv6, vous devez définir `USE_IPV6=yes`. Veuillez noter que la configuration IPv6 de votre réseau et de votre environnement n'entre pas dans le champ d'application de cette documentation.

=== "Docker / Autoconf / Swarm"

    Tout d'abord, vous devrez configurer le démon Docker pour activer la prise en charge d'IPv6 pour les conteneurs et utiliser ip6tables si nécessaire. Voici une configuration d'exemple pour votre fichier /etc/docker/daemon.json :

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    Vous pouvez maintenant redémarrer le service Docker pour appliquer les modifications :

    ```shell
    systemctl restart docker
    ```

    Une fois Docker configuré pour prendre en charge IPv6, vous pouvez ajouter le paramètre `USE_IPV6` et configurer le réseau bw-services pour IPv6 :

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
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

    Vous devrez ajouter ces paramètres au fichier /etc/bunkerweb/variables.env :

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

    Vérifions maintenant l'état de BunkerWeb :

    ```shell
    systemctl status bunkerweb
    ```

    S'il est déjà en cours d'exécution, nous pouvons le redémarrer :

    ```shell
    systemctl restart bunkerweb
    ```

    Sinon, nous devrons le démarrer :

    ```shell
    systemctl start bunkerweb
    ```

## Options de configuration de journalisation

BunkerWeb offre une configuration de journalisation flexible, vous permettant d'envoyer les journaux vers plusieurs destinations (comme des fichiers, stdout/stderr ou syslog) simultanément. Cela est particulièrement utile pour l'intégration avec des collecteurs de journaux externes tout en conservant des journaux locaux pour l'interface Web.

Il y a deux catégories principales de journaux à configurer :

1. **Journaux de service** : Journaux générés par les composants BunkerWeb (Scheduler, UI, Autoconf, etc.). Contrôlés par service via `LOG_TYPES` (et optionnellement `LOG_FILE_PATH`, `LOG_SYSLOG_ADDRESS`, `LOG_SYSLOG_TAG`).
2. **Journaux d'accès et d'erreur** : Journaux d'accès et d'erreur HTTP générés par NGINX. Seuls le service `bunkerweb` les utilise (`ACCESS_LOG` / `ERROR_LOG` / `LOG_LEVEL`).

### Journaux de service

Les journaux de service sont contrôlés par le paramètre `LOG_TYPES`, qui peut accepter plusieurs valeurs séparées par des espaces (par exemple, `LOG_TYPES="stderr syslog"`).

| Valeur   | Description                                                                                                |
| :------- | :--------------------------------------------------------------------------------------------------------- |
| `file`   | Écrit les journaux dans un fichier. Requis pour le visualiseur de journaux de l'interface Web.             |
| `stderr` | Écrit les journaux vers l'erreur standard. Standard pour les environnements conteneurisés (`docker logs`). |
| `syslog` | Envoie les journaux vers un serveur syslog. Nécessite que `LOG_SYSLOG_ADDRESS` soit défini.                |

Lors de l'utilisation de `syslog`, vous devriez également configurer :

- `LOG_SYSLOG_ADDRESS` : L'adresse du serveur syslog (par exemple, `udp://bw-syslog:514` ou `/dev/log`).
- `LOG_SYSLOG_TAG` : Une étiquette unique pour le service (par exemple, `bw-scheduler`) pour distinguer ses entrées.
- `LOG_FILE_PATH` : Chemin pour la sortie fichier lorsque `LOG_TYPES` inclut `file` (par exemple, `/var/log/bunkerweb/scheduler.log`).

### Journaux d'accès et d'erreur

Ce sont des journaux NGINX standard, configurés via **le service `bunkerweb` uniquement**. Ils prennent en charge plusieurs destinations en suffixant le nom du paramètre (par exemple, `ACCESS_LOG`, `ACCESS_LOG_1` et le `LOG_FORMAT` correspondant, `LOG_FORMAT_1` ou `ERROR_LOG`, `ERROR_LOG_1` et leur `LOG_LEVEL` respectif, `LOG_LEVEL_1`).

- `ACCESS_LOG` : Destination pour les journaux d'accès (par défaut : `/var/log/bunkerweb/access.log`). Accepte un chemin de fichier, `syslog:server=host[:port][,param=value]`, tampon partagé `memory:name:size`, ou `off` pour désactiver. Voir la [documentation NGINX access_log](https://nginx.org/en/docs/http/ngx_http_log_module.html#access_log) pour plus de détails.
- `ERROR_LOG` : Destination pour les journaux d'erreur (par défaut : `/var/log/bunkerweb/error.log`). Accepte un chemin de fichier, `stderr`, `syslog:server=host[:port][,param=value]`, ou tampon partagé `memory:size`. Voir la [documentation NGINX error_log](https://nginx.org/en/docs/ngx_core_module.html#error_log) pour plus de détails.
- `LOG_LEVEL` : Niveau de verbosité des journaux d'erreur (par défaut : `notice`).

Ces paramètres acceptent des valeurs NGINX standard, y compris des chemins de fichiers, `stderr`, `syslog:server=...` (voir la [documentation NGINX syslog](https://nginx.org/en/docs/syslog.html)), ou des tampons de mémoire partagée. Ils prennent en charge plusieurs destinations via des suffixes numérotés (voir la [convention des paramètres multiples](features.md#multiple-settings)). Les autres services (Scheduler, UI, Autoconf, etc.) reposent uniquement sur `LOG_TYPES`/`LOG_FILE_PATH`/`LOG_SYSLOG_*`.

**Exemple avec plusieurs journaux d'accès/erreur (bunkerweb uniquement, suffixes numérotés) :**

```conf
ACCESS_LOG=/var/log/bunkerweb/access.log
ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_FORMAT=$host $remote_addr - $request_id $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
LOG_FORMAT_1=$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
ERROR_LOG=/var/log/bunkerweb/error.log
ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_LEVEL=notice
LOG_LEVEL_1=error
```

### Valeurs par défaut et exemples d'intégration

=== "Linux"

    **Comportement par défaut** : `LOG_TYPES="file"`. Les journaux sont écrits dans `/var/log/bunkerweb/*.log`.

    **Exemple** : Conserver les fichiers locaux (pour l'interface Web) et les reproduire également vers le syslog système.

    ```conf
      # Logs de service (à définir dans /etc/bunkerweb/variables.env ou les fichiers d'environnement spécifiques aux services)
      LOG_TYPES="file syslog"
      LOG_SYSLOG_ADDRESS=/dev/log
      SCHEDULER_LOG_FILE_PATH=/var/log/bunkerweb/scheduler.log
      UI_LOG_FILE_PATH=/var/log/bunkerweb/ui.log
      # ...
      # LOG_SYSLOG_TAG est défini automatiquement par service (remplacez-le par service si nécessaire)

      # Logs NGINX (service bunkerweb uniquement ; à définir dans /etc/bunkerweb/variables.env)
      ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb_access
      ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
    ```

=== "Docker / Autoconf / Swarm"

    **Comportement par défaut** : `LOG_TYPES="stderr"`. Les journaux sont visibles via `docker logs`.

    **Exemple (Adapté du guide de démarrage rapide)** : Conserver `docker logs` (stderr) ET envoyer vers un conteneur syslog central (nécessaire pour l'interface Web et CrowdSec).

    ```yaml
    x-bw-env:
      &bw-env # On utilise une ancre pour éviter de répéter les mêmes paramètres pour les deux services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Assurez-vous de définir la plage IP correcte pour que le Scheduler puisse envoyer la configuration à l'instance
      # Optionnel : définissez un token API et répliquez-le dans les deux conteneurs
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # N'oubliez pas de définir un mot de passe plus fort pour la base de données
      # Logs des services
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"
      # LOG_SYSLOG_TAG sera défini automatiquement par service (remplacez-le par service si nécessaire)
      # Logs NGINX : envoyer au syslog (bunkerweb uniquement)
      ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
      ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"

    services:
      bunkerweb:
        # Ceci est le nom qui sera utilisé pour identifier l'instance dans le Scheduler
        image: bunkerity/bunkerweb:1.6.9
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Pour la prise en charge de QUIC / HTTP3
        environment:
          <<: *bw-env # Nous utilisons l'ancre pour éviter de répéter les mêmes paramètres pour tous les services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.9
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Assurez-vous de définir le nom d'instance correct
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Modifiez si nécessaire
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # Utilisé pour persister le cache et d'autres données (sauvegardes, etc.)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.9
        environment:
          <<: *bw-env
        volumes:
          - bw-logs:/var/log/bunkerweb # Permet à l'UI de lire les logs syslog
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Nous définissons max_allowed_packet pour éviter les problèmes avec de grandes requêtes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # N'oubliez pas de définir un mot de passe plus fort pour la base de données
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Service Redis pour la persistance des rapports/bans/statistiques
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE # Lier aux ports bas
          - NET_BROADCAST # Envoyer des broadcasts
          - NET_RAW # Utiliser des sockets bruts
          - DAC_READ_SEARCH # Lire des fichiers en contournant les permissions
          - DAC_OVERRIDE # Outrepasser les permissions de fichiers
          - CHOWN # Changer les propriétaires
          - SYSLOG # Écrire dans les journaux système
        volumes:
          - bw-logs:/var/log/bunkerweb # Volume utilisé pour stocker les logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Fichier de configuration syslog-ng
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      redis-data:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
      ipam:
        driver: default
        config:
          - subnet: 10.20.30.0/24 # Assurez-vous de définir la plage IP correcte pour que le Scheduler puisse envoyer la configuration à l'instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

### Configuration de syslog-ng

Voici un exemple de fichier `syslog-ng.conf` que vous pouvez utiliser pour rediriger les journaux vers un fichier :

```conf
@version: 4.10

# Configuration de la source pour recevoir les journaux envoyés par les services BunkerWeb (ACCESS_LOG / ERROR_LOG et LOG_TYPES=syslog)
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Modèle pour formater les messages de journalisation
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Destination : écrire les journaux dans des fichiers nommés dynamiquement
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
    logrotate(
      enable(yes),
      size(100MB),
      rotations(7)
    )
  );
};

# Chemin de journalisation pour diriger les logs vers des fichiers nommés dynamiquement
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Meilleures pratiques de journalisation Docker

Lors de l'utilisation de Docker, il est important de gérer les journaux des conteneurs pour éviter qu'ils ne consomment un espace disque excessif. Par défaut, Docker utilise le pilote de journalisation `json-file`, ce qui peut entraîner des fichiers journaux très volumineux s'il n'est pas configuré.

Pour éviter cela, vous pouvez configurer la rotation des journaux. Cela peut être fait pour des services spécifiques dans votre fichier `docker-compose.yml`, ou globalement pour le démon Docker.

**Configuration par service**

Vous pouvez configurer le pilote de journalisation pour vos services dans votre fichier `docker-compose.yml` afin de faire pivoter automatiquement les journaux. Voici un exemple qui conserve jusqu'à 10 fichiers journaux de 20 Mo chacun :

```yaml
services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.9
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "10"
    ...
```

Cette configuration garantit la rotation des journaux, les empêchant de remplir votre disque. Vous pouvez l'appliquer à n'importe quel service de votre configuration Docker Compose.

**Paramètres globaux (daemon.json)**

Si vous souhaitez appliquer ces paramètres de journalisation à tous les conteneurs de l'hôte par défaut, vous pouvez configurer le démon Docker en modifiant (ou en créant) le fichier `/etc/docker/daemon.json` :

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "10"
  }
}
```

Après avoir modifié `daemon.json`, vous devez redémarrer le démon Docker pour que les modifications prennent effet :

```shell
sudo systemctl restart docker
```

Ces paramètres globaux seront hérités par tous les conteneurs. Cependant, toute configuration de journalisation définie par service dans un fichier `docker-compose.yml` remplacera les paramètres globaux dans `daemon.json`.

## Réglage de la sécurité {#security-tuning}

BunkerWeb offre de nombreuses fonctionnalités de sécurité que vous pouvez configurer avec les [fonctionnalités](features.md). Même si les valeurs par défaut des paramètres assurent une "sécurité par défaut" minimale, nous vous recommandons vivement de les régler. Ce faisant, vous serez en mesure de vous assurer du niveau de sécurité de votre choix, mais aussi de gérer les faux positifs.

!!! tip "Autres fonctionnalités"
    Cette section se concentre uniquement sur le réglage de la sécurité, voir la section [fonctionnalités](features.md) de la documentation pour d'autres paramètres.

<figure markdown>
  ![Vue d'ensemble](assets/img/core-order.svg){ align=center }
  <figcaption>Vue d'ensemble et ordre des plugins de sécurité de base</figcaption>
</figure>

## Intégration de la console CrowdSec

Si vous n'êtes pas déjà familier avec l'intégration de la console CrowdSec, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) exploite l'intelligence participative pour lutter contre les cybermenaces. Considérez-le comme le "Waze de la cybersécurité" : lorsqu'un serveur est attaqué, les autres systèmes du monde entier sont alertés et protégés contre les mêmes attaquants. Vous pouvez en savoir plus à ce sujet [ici](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

**Félicitations, votre instance BunkerWeb est maintenant inscrite dans votre console CrowdSec !**

Conseil professionnel : Lorsque vous consultez vos alertes, cliquez sur l'option "colonnes" et cochez la case "contexte" pour accéder aux données spécifiques à BunkerWeb.

<figure markdown>
  ![Vue d'ensemble](assets/img/crowdity4.png){ align=center }
  <figcaption>Données BunkerWeb affichées dans la colonne de contexte</figcaption>
</figure>

## Proxy direct pour le trafic sortant {#forward-proxy-outgoing-traffic}

Si votre environnement doit faire passer le trafic HTTP(S) sortant par un proxy direct (par exemple un proxy d'entreprise ou Squid), vous pouvez utiliser les variables d'environnement de proxy standard. Il n'existe pas de réglage BunkerWeb dédié.

**NGINX lui-même n'utilise pas ces variables pour le trafic upstream**, donc la configuration du proxy direct ne concerne que les composants qui initient des requêtes sortantes. En pratique, configurez-les sur le **Scheduler**, car il gère des tâches périodiques comme les renouvellements de certificats Let's Encrypt, les appels d'API externes et les webhooks.

Les variables couramment utilisées sont :

- `HTTP_PROXY` / `HTTPS_PROXY` : URL du proxy, éventuellement avec identifiants.
- `NO_PROXY` : liste séparée par des virgules des hôtes, domaines ou CIDR à exclure du proxy (adaptez selon l'intégration : noms de services en Docker/Swarm, domaines de cluster en Kubernetes, ou simplement localhost sous Linux).
- `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` : optionnel, requis si le proxy utilise une AC personnalisée. Montez le bundle CA dans le conteneur et pointez ces variables vers celui-ci afin que les requêtes Python puissent valider TLS (adaptez le chemin à votre image de base).

!!! warning "NO_PROXY est requis pour le trafic interne"
    Si vous omettez les plages internes ou les noms de services, le trafic interne peut être envoyé au proxy et échouer. Adaptez la liste à votre intégration (par exemple noms de services Docker, domaines de cluster Kubernetes ou simplement localhost sous Linux).

=== "Linux"

    Ajoutez les variables dans `/etc/bunkerweb/variables.env`. Ce fichier est chargé par les deux services, mais seul le Scheduler les utilisera :

    ```conf
    HTTP_PROXY=http://proxy.example.local:3128
    HTTPS_PROXY=http://proxy.example.local:3128
    NO_PROXY=localhost,127.0.0.1
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    ```

    Redémarrez les services pour recharger l'environnement :

    ```shell
    sudo systemctl restart bunkerweb && \
    sudo systemctl restart bunkerweb-scheduler
    ```

=== "All-in-one"

    Fournissez les variables lors de la création du conteneur (et montez le bundle CA si nécessaire). L'image All-in-one inclut le Scheduler, ce qui couvre les tâches sortantes :

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -v /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro \
        -e HTTP_PROXY="http://proxy.example.local:3128" \
        -e HTTPS_PROXY="http://proxy.example.local:3128" \
        -e NO_PROXY="localhost,127.0.0.1" \
        -e REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt" \
        -e SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.9
    ```

    Si le conteneur existe déjà, recréez-le pour appliquer le nouvel environnement.

=== "Docker"

    Ajoutez les variables au conteneur scheduler :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.9
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

=== "Docker autoconf"

    Appliquez les variables au conteneur scheduler :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.9
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

=== "Kubernetes"

    Ajoutez les variables au pod Scheduler via `extraEnvs`. Si vous avez besoin d'une AC personnalisée, montez-la via `extraVolumes`/`extraVolumeMounts` et pointez les variables vers le chemin monté :

    ```yaml
    scheduler:
      extraEnvs:
        - name: HTTP_PROXY
          value: "http://proxy.example.local:3128"
        - name: HTTPS_PROXY
          value: "http://proxy.example.local:3128"
        - name: NO_PROXY
          value: "localhost,127.0.0.1,.svc,.cluster.local"
        - name: REQUESTS_CA_BUNDLE
          value: "/etc/ssl/certs/ca-certificates.crt"
        - name: SSL_CERT_FILE
          value: "/etc/ssl/certs/ca-certificates.crt"
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Ajoutez les variables au service scheduler :

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.9
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

## Surveillance et rapports

### Monitoring <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

Le plugin de surveillance vous permet de collecter et de récupérer des métriques sur BunkerWeb. En l'activant, votre ou vos instances commenceront à collecter diverses données liées aux attaques, aux requêtes et aux performances. Vous pouvez ensuite les récupérer en appelant régulièrement le point de terminaison de l' `/monitoring` API ou en utilisant d'autres plugins comme celui de l'exportateur Prometheus.

**Liste des fonctionnalités**

- Permettre la collecte de diverses métriques BunkerWeb
- Récupérer des métriques à partir de l'API
- Utilisation en combinaison avec d'autres plugins (par exemple Prometheus exporter)
- Dédiée à la page d'interface utilisateur pour surveiller vos instances

**Liste des paramètres**

| Réglage                        | Défaut | Contexte | Multiple | Description                                                        |
| ------------------------------ | ------ | -------- | -------- | ------------------------------------------------------------------ |
| `USE_MONITORING`               | `yes`  | global   | Non      | Activez la surveillance de BunkerWeb.                              |
| `MONITORING_METRICS_DICT_SIZE` | `10M`  | global   | Non      | Taille du dictionnaire pour stocker les métriques de surveillance. |

### Prometheus exporter <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

Le plugin d'exportation Prometheus ajoute un [exportateur Prometheus](https://prometheus.io/docs/instrumenting/exporters/) sur votre ou vos instances BunkerWeb. Lorsqu'elle est activée, vous pouvez configurer votre ou vos instances Prometheus pour récupérer un point de terminaison spécifique sur Bunkerweb et collecter des métriques internes.

Nous fournissons également un [tableau de bord Grafana](https://grafana.com/grafana/dashboards/20755-bunkerweb/) que vous pouvez importer dans votre propre instance et connecter à votre propre source de données Prometheus.

**Veuillez noter que l'utilisation du plugin d'exportation Prometheus nécessite d'activer le plugin de surveillance (`USE_MONITORING=yes`)**

**Liste des fonctionnalités**

- L'exportateur Prometheus fournit des métriques internes à BunkerWeb
- Port dédié et configurable, IP et URL d'écoute
- Liste blanche IP/réseau pour une sécurité maximale

**Liste des paramètres**

| Réglage                        | Ddéfaut                                               | Contexte | Multiple | Description                                                                                              |
| ------------------------------ | ----------------------------------------------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global   | Non      | Activez l'exportation Prometheus.                                                                        |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global   | Non      | IP d'écoute de l'exportateur Prometheus.                                                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global   | Non      | Port d'écoute de l'exportateur Prometheus.                                                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global   | Non      | URL HTTP de l'exportateur Prometheus.                                                                    |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global   | Non      | Liste des adresses IP/réseaux autorisés à contacter le point de terminaison de l'exportateur Prometheus. |

### Reporting <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

!!! warning "Plugin de surveillance nécessaire"
    Ce plug-in nécessite l'installation et l'activation du plug-in Monitoring Pro avec le `USE_MONITORING` paramètre défini sur `yes`.

Le plugin Reporting fournit une solution complète pour la communication régulière de données importantes de BunkerWeb, y compris les statistiques mondiales, les attaques, les bannissements, les demandes, les raisons et les informations AS. Il offre un large éventail de fonctionnalités, notamment la création automatique de rapports, des options de personnalisation et une intégration transparente avec le plugin monitoring pro. Avec le plugin Reporting, vous pouvez facilement générer et gérer des rapports pour surveiller les performances et la sécurité de votre application.

**Liste des fonctionnalités**

- Rapports réguliers sur les données importantes de BunkerWeb, y compris les statistiques mondiales, les attaques, les bannissements, les demandes, les raisons et les informations sur les SA.
- Intégration avec le plug-in Monitoring Pro pour une intégration transparente et des capacités de reporting améliorées.
- Prise en charge des webhooks (classique, Discord et Slack) pour les notifications en temps réel.
- Prise en charge de SMTP pour les notifications par e-mail.
- Options de configuration pour plus de personnalisation et de flexibilité.

**Liste des paramètres**

| Réglage                        | Par défaut         | Contexte | Description                                                                                |
| ------------------------------ | ------------------ | -------- | ------------------------------------------------------------------------------------------ |
| `USE_REPORTING_SMTP`           | `no`               | global   | Activer l'envoi du rapport par e-mail (HTML).                                              |
| `USE_REPORTING_WEBHOOK`        | `no`               | global   | Activer l'envoi du rapport via webhook (Markdown).                                         |
| `REPORTING_SCHEDULE`           | `weekly`           | global   | Cadence du rapport : `daily`, `weekly` ou `monthly`.                                       |
| `REPORTING_WEBHOOK_URLS`       |                    | global   | URLs de webhook séparées par des espaces ; Discord et Slack sont détectés automatiquement. |
| `REPORTING_SMTP_EMAILS`        |                    | global   | Destinataires e-mail séparés par des espaces.                                              |
| `REPORTING_SMTP_HOST`          |                    | global   | Nom d'hôte ou IP du serveur SMTP.                                                          |
| `REPORTING_SMTP_PORT`          | `465`              | global   | Port SMTP. Utilisez `465` pour SSL, `587` pour TLS.                                        |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global   | Adresse de l'expéditeur (désactivez la 2FA si nécessaire).                                 |
| `REPORTING_SMTP_FROM_USER`     |                    | global   | Nom d'utilisateur SMTP (utilise l'adresse d'envoi si seul le mot de passe est fourni).     |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global   | Mot de passe SMTP.                                                                         |
| `REPORTING_SMTP_SSL`           | `SSL`              | global   | Sécurité de connexion : `no`, `SSL` ou `TLS`.                                              |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global   | Objet des envois e-mail.                                                                   |

!!! info "Information et comportement"
    - `REPORTING_SMTP_EMAILS` est requis quand l'envoi SMTP est activé ; `REPORTING_WEBHOOK_URLS` est requis quand les webhooks sont activés.
    - Si les webhooks et SMTP échouent tous, une nouvelle tentative est effectuée lors de la prochaine exécution planifiée.
    - Les modèles HTML et Markdown se trouvent dans `reporting/files/` ; personnalisez-les prudemment pour conserver les variables.

## Sauvegarde et restauration

### Backup S3 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge STREAM :white_check_mark:

L'outil Backup S3 automatise de manière transparente la protection des données, à l'instar du plug-in de sauvegarde communautaire. Cependant, il se distingue par le stockage sécurisé des sauvegardes directement dans un compartiment S3.

En activant cette fonctionnalité, vous protégez de manière proactive **l'intégrité de vos données**. Le stockage à **distance** des sauvegardes protège les informations cruciales contre les menaces telles que ** les pannes matérielles**, **les cyberattaques** ou **les catastrophes naturelles**. Cela garantit à la fois **la sécurité** et **la disponibilité**, ce qui permet une récupération rapide en cas ** d'événements inattendus**, préservant la **continuité opérationnelle** et garantissant **la tranquillité d'esprit**.

??? warning "Informations pour les utilisateurs de Red Hat Enterprise Linux (RHEL) 8.9"
    Si vous utilisez **RHEL 8.9** et que vous prévoyez d'utiliser une **base de données externe**, vous devez installer le `mysql-community-client` package pour vous assurer que la `mysqldump` commande est disponible. Vous pouvez installer le package en exécutant les commandes suivantes :

    === "MySQL/MariaDB"

        1. **Installez le paquet de configuration du dépôt MySQL**

          ```bash
          sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
          ```

        2. **Activez le dépôt MySQL**

          ```bash
          sudo dnf config-manager --enable mysql80-community
          ```

        3. **Installez le client MySQL**

          ```bash
          sudo dnf install mysql-community-client
          ```

    === "PostgreSQL"

        1. **Installez le paquet de configuration du dépôt PostgreSQL**

          ```bash
          dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
          ```

        2. **Installez le client PostgreSQL**

          ```bash
          dnf install postgresql<version>
          ```

**Liste des fonctionnalités**

- Sauvegarde automatique des données dans un compartiment S3
- Options de planification flexibles : quotidienne, hebdomadaire ou mensuelle
- Gestion de la rotation pour contrôler le nombre de sauvegardes à conserver
- Niveau de compression personnalisable pour les fichiers de sauvegarde

**Liste des paramètres**

| Réglage                       | Faire défaut | Contexte | Description                                           |
| ----------------------------- | ------------ | -------- | ----------------------------------------------------- |
| `USE_BACKUP_S3`               | `no`         | global   | Activer ou désactiver la fonction de sauvegarde S3    |
| `BACKUP_S3_SCHEDULE`          | `daily`      | global   | La fréquence de la sauvegarde                         |
| `BACKUP_S3_ROTATION`          | `7`          | global   | Le nombre de sauvegardes à conserver                  |
| `BACKUP_S3_ENDPOINT`          |              | global   | Le point de terminaison S3                            |
| `BACKUP_S3_BUCKET`            |              | global   | Le godet S3                                           |
| `BACKUP_S3_DIR`               |              | global   | L'annuaire S3                                         |
| `BACKUP_S3_REGION`            |              | global   | La région S3                                          |
| `BACKUP_S3_ACCESS_KEY_ID`     |              | global   | L'ID de la clé d'accès S3                             |
| `BACKUP_S3_ACCESS_KEY_SECRET` |              | global   | Le secret de la clé d'accès S3                        |
| `BACKUP_S3_COMP_LEVEL`        | `6`          | global   | Le niveau de compression du fichier zip de sauvegarde |

#### Sauvegarde manuelle

Pour lancer manuellement une sauvegarde, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

Cette commande crée une sauvegarde de votre base de données et la stocke dans le compartiment S3 spécifié dans le `BACKUP_S3_BUCKET` paramètre.

Vous pouvez également spécifier un compartiment S3 personnalisé pour la sauvegarde en fournissant la variable d' `BACKUP_S3_BUCKET` environnement lors de l'exécution de la commande :

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "Spécifications pour MariaDB/MySQL"

    Si vous utilisez MariaDB/MySQL, vous pouvez rencontrer l'erreur suivante lors de la sauvegarde de votre base de données :

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Pour résoudre ce problème, vous pouvez exécuter la commande suivante pour changer le plugin d'authentification en `mysql_native_password` :

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Si vous utilisez l'intégration Docker, vous pouvez ajouter la commande suivante au fichier `docker-compose.yml` pour changer automatiquement le plugin d'authentification :

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

#### Restauration manuelle

Pour lancer manuellement une restauration, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

Cette commande crée une sauvegarde temporaire de votre base de données dans le compartiment S3 spécifié dans le `BACKUP_S3_BUCKET` paramètre et restaure votre base de données à la dernière sauvegarde disponible dans le compartiment.

Vous pouvez également spécifier un fichier de sauvegarde personnalisé pour la restauration en fournissant le chemin d'accès à celui-ci en tant qu'argument lors de l'exécution de la commande :

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "En cas de panne"

    Don't worry if the restore fails, you can always restore your database to the previous state by executing the command again as a backup is created before the restore:

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

## Migration <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge STREAM :white_check_mark:

Le plug-in de migration **révolutionne les transferts de** configuration BunkerWeb entre les instances grâce à son **interface Web conviviale**, simplifiant ainsi l'ensemble du parcours de migration. Que vous mettiez à niveau des systèmes, que vous fassiez évoluer une infrastructure ou que vous transformiez d'environnement, cet outil vous permet de transférer sans effort les **paramètres, les préférences et les données** avec une facilité et une confiance inégalées. Dites adieu aux processus manuels fastidieux et bonjour à une expérience de **migration transparente et sans tracas**.

**Liste des fonctionnalités**

- **Migration sans effort :** Transférez facilement les configurations BunkerWeb entre les instances sans les complexités des procédures manuelles.

- **Interface Web intuitive :** Naviguez sans effort dans le processus de migration grâce à une interface Web conviviale conçue pour un fonctionnement intuitif.

- **Compatibilité entre bases de données :** profitez d'une migration transparente sur diverses plates-formes de bases de données, notamment SQLite, MySQL, MariaDB et PostgreSQL, garantissant la compatibilité avec votre environnement de base de données préféré.

### Créer un fichier de migration

Pour créer manuellement un fichier de migration, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin migration create /path/to/migration/file
    ```

=== "Docker"

    1. Créez un fichier de migration :

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /path/to/migration/file
        ```

    2. Copiez le fichier de migration sur votre ordinateur local :

        ```bash
        docker cp <scheduler_container>:/path/to/migration/file /path/to/migration/file
        ```

Cette commande créera une sauvegarde de votre base de données et la stockera dans le répertoire de sauvegarde spécifié dans la commande.

!!! note "Spécifications pour MariaDB/MySQL"

    Si vous utilisez MariaDB/MySQL, vous pouvez rencontrer l'erreur suivante lors de la sauvegarde de votre base de données :

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Pour résoudre ce problème, vous pouvez exécuter la commande suivante pour changer le plugin d'authentification en `mysql_native_password` :

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Si vous utilisez l'intégration Docker, vous pouvez ajouter la commande suivante au fichier `docker-compose.yml` pour changer automatiquement le plugin d'authentification :

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

### Initialiser une migration

Pour initialiser manuellement une migration, exécutez la commande suivante :

=== "Linux"

    ```bash
    bwcli plugin migration migrate /path/to/migration/file
    ```

=== "Docker"

    1. Copiez le fichier de migration dans le conteneur :

        ```bash
        docker cp /path/to/migration/file <scheduler_container>:/path/to/migration/file
        ```

    2. Initialisez la migration :

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /path/to/migration/file
        ```

=== "Tout-en-un"

    1. Copiez le fichier de migration dans le conteneur :

        ```bash
        docker cp /path/to/migration/file bunkerweb-aio:/path/to/migration/file
        ```

    2. Initialisez la migration :

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /path/to/migration/file
        ```

Cette commande migre de manière transparente vos données BunkerWeb pour qu'elles correspondent précisément à la configuration décrite dans le fichier de migration.

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

Le  plug-in **anti-DDoS** offre une protection avancée contre les attaques par déni de service distribué (DDoS) en surveillant, analysant et filtrant le trafic suspect en temps réel.

En utilisant un mécanisme de **fenêtre glissante**, le plugin maintient un dictionnaire en mémoire des horodatages des requêtes pour détecter les pics de trafic anormaux à partir d'adresses IP individuelles. En fonction du mode de sécurité configuré, il peut soit bloquer les connexions incriminées, soit consigner l'activité suspecte pour un examen plus approfondi.

### Fonctionnalités

- **Analyse du trafic en temps réel :** surveille en permanence les demandes entrantes pour détecter les attaques DDoS potentielles.
- **Mécanisme de fenêtre glissante :** suit l'activité récente des demandes dans une fenêtre de temps configurable.
- **Seuils configurables :** vous permet de définir le nombre maximum de requêtes suspectes par IP.
- **Logique de blocage avancée :** évalue à la fois le nombre de requêtes par IP et le nombre d'adresses IP distinctes dépassant le seuil.
- **Modes de sécurité flexibles :** choisissez entre le blocage immédiat de la connexion ou le mode de détection uniquement (journalisation).
- **Magasin de données en mémoire optimisé :** Garantit des recherches à grande vitesse et un suivi efficace des métriques.
- **Entretien ménager automatique :** efface périodiquement les données obsolètes pour maintenir des performances optimales.

### Configuration

Personnalisez le comportement du plug-in à l'aide des paramètres suivants :

| Réglage                      | Faire défaut  | Contexte | Multiple | Description                                                                                                 |
| ---------------------------- | ------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`          | global   | Non      | Activez ou désactivez la protection anti-DDoS. Réglez sur `"yes"` pour activer le plugin.                   |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`         | global   | Non      | Taille de la banque de données en mémoire pour le suivi des métriques DDoS (par exemple, `10M`, `500k`).    |
| `ANTIDDOS_THRESHOLD`         | `100`         | global   | Non      | Nombre maximum de requêtes suspectes autorisées par IP dans la fenêtre de temps définie.                    |
| `ANTIDDOS_WINDOW_TIME`       | `10`          | global   | Non      | Fenêtre de temps en secondes pendant laquelle les demandes suspectes sont comptabilisées.                   |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444` | global   | Non      | Codes d'état HTTP considérés comme suspects et utilisés pour déclencher des actions anti-DDoS.              |
| `ANTIDDOS_DISTINCT_IP`       | `5`           | global   | Non      | Nombre minimum d'adresses IP distinctes qui doivent dépasser le seuil avant d'appliquer le mode de blocage. |

### Bonnes pratiques

- **Réglage du seuil :** ajustez `ANTIDDOS_THRESHOLD` et `ANTIDDOS_WINDOW_TIME` en fonction de vos modèles de trafic typiques.
- **Révision du code d'état :** mettez régulièrement à jour `ANTIDDOS_STATUS_CODES` pour capturer les comportements suspects nouveaux ou en évolution.
- **Surveillance :** analysez régulièrement les journaux et les métriques pour affiner les paramètres et améliorer la protection globale.

## Gestionnaire d'utilisateurs <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="Gestionnaire d'utilisateurs" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Le plug-in de gestion des utilisateurs offre une interface robuste pour l'administration des comptes d'utilisateurs au sein de votre système.

Avec ce plugin, les administrateurs peuvent sans effort créer, mettre à jour et désactiver des comptes utilisateurs, gérer les rôles des utilisateurs, basculer l'authentification à deux facteurs (2FA) et afficher des informations détaillées sur les utilisateurs telles que les horodatages de la dernière connexion et les statuts des comptes (actif ou inactif). Conçu dans un souci de sécurité et de facilité d'utilisation, ce plug-in simplifie les tâches de gestion des utilisateurs tout en garantissant la conformité et l'auditabilité.

### Fonctionnalités

- **Opérations de compte d'utilisateur :** importez au format CSV/XSLX, créez, modifiez et supprimez des comptes d'utilisateur en toute simplicité.
- **Contrôle d'accès basé sur les rôles :** Attribuez et modifiez les rôles d'utilisateur pour gérer les autorisations et les niveaux d'accès.
- **Gestion 2FA :** désactivez l'authentification à deux facteurs en fonction des décisions administratives.
- **Informations complètes sur les utilisateurs :** surveillez les données clés des utilisateurs, notamment les heures de dernière connexion, les dates de création de compte et le statut actif/inactif.
- **Journalisation des audits :** conservez une piste d'audit pour toutes les actions de gestion des utilisateurs afin d'améliorer la sécurité et la conformité.

<figure markdown>
  ![Vue d'ensemble](assets/img/user-manager.png){ align=center }
  <figcaption>Page Gestionnaire d'utilisateurs</figcaption>
</figure>

<figure markdown>
  ![Créer un formulaire utilisateur](assets/img/user-manager-create.png){ align=center }
  <figcaption>Gestionnaire d'utilisateurs - Créer un formulaire d'utilisateur</figcaption>
</figure>

<figure markdown>
  ![Page d'activités](assets/img/user-manager-activities.png){ align=center }
  <figcaption>Gestionnaire d'utilisateurs - Page Activités</figcaption>
</figure>

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/45vX0WJqjxo" title="Easy Resolve" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Le plugin Easy Resolve vous permet de remédier rapidement aux faux positifs et aux problèmes récurrents directement depuis la page Rapports. Il transforme les actions guidées "Résoudre" en mises à jour de configuration sûres et étendues—sans édition manuelle.

### Fonctionnalités

- Actions en un clic depuis les Rapports et les détails des rapports.
- Suggestions contextuelles pour ModSecurity, blacklist, DNSBL, limitation de débit, méthodes HTTP autorisées et pays en liste blanche/noire.
- Génère des exclusions ModSecurity sûres ou met à jour les listes d'ignorance.
- Applique les changements au niveau du service ou global avec vérifications des permissions.
- Ouverture automatique optionnelle de la page de configuration liée après application.

<figure markdown>
  ![Vue d'ensemble](assets/img/easy-resolve.png){ align=center }
  <figcaption>Page Rapports - avec Easy Resolve</figcaption>
</figure>

## Load Balancer <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/cOVp0rAt5nw?si=iVhDio8o8S4F_uag" title="Load Balancer" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Le plugin Load Balancer transforme BunkerWeb en un directeur de trafic avec garde-fous. Déclarez des pools upstream une fois, pointez votre proxy inverse vers eux, et laissez le équilibrage conscient de la santé garder les utilisateurs sur des backends réactifs. Le mode sticky cookie émet automatiquement un cookie `BWLBID` pour que les sessions restent ancrées où vous le souhaitez.

### Fonctionnalités

- Blocs par upstream : nommez les pools et réutilisez-les sur les hôtes proxy inverse.
- Équilibrage flexible : round-robin par défaut, ou sticky via IP ou cookie signé.
- Cibles intelligentes : résolution DNS optionnelle pour les backends hostname plus réglage keepalive.
- Santé intégrée : sondes HTTP/HTTPS avec chemins personnalisés, intervalles, codes de statut et vérifications SSL.
- Continuité de session : cookie `BWLBID` automatique lorsque le mode sticky-cookie est activé.

### Configuration

**Définition upstream**

| Paramètre                                 | Défaut        | Contexte | Multiple | Description                                                                       |
| ----------------------------------------- | ------------- | -------- | -------- | --------------------------------------------------------------------------------- |
| `LOADBALANCER_UPSTREAM_NAME`              |               | global   | oui      | Identifiant upstream (référencé par `REVERSE_PROXY_HOST`).                        |
| `LOADBALANCER_UPSTREAM_SERVERS`           |               | global   | oui      | Liste séparée par espaces d'adresses backend (ex. `10.0.0.1:8080 10.0.0.2:8080`). |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin` | global   | oui      | Stratégie d'équilibrage (`round-robin` ou `sticky`).                              |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`          | global   | oui      | Méthode sticky (`ip` ou `cookie`). Mode cookie émet `BWLBID`.                     |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`          | global   | oui      | Résoudre les hostnames upstream via DNS.                                          |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |               | global   | oui      | Connexions keepalive par worker.                                                  |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`         | global   | oui      | Timeout inactif pour les connexions keepalive.                                    |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`          | global   | oui      | Durée de vie maximale pour les connexions keepalive.                              |

**Vérifications de santé**

| Paramètre                                 | Défaut    | Contexte | Multiple | Description                                                            |
| ----------------------------------------- | --------- | -------- | -------- | ---------------------------------------------------------------------- |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`     | global   | non      | Taille du dictionnaire partagé pour l'état des vérifications de santé. |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status` | global   | oui      | Chemin à sonder sur chaque backend.                                    |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`    | global   | oui      | Intervalle entre vérifications (ms).                                   |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`    | global   | oui      | Timeout par vérification (ms).                                         |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`       | global   | oui      | Échecs consécutifs avant de marquer comme down.                        |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`       | global   | oui      | Succès consécutifs avant de marquer comme up.                          |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`     | global   | oui      | Liste séparée par espaces de codes de statut HTTP valides.             |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`      | global   | oui      | Maximum de sondes concurrentes.                                        |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`    | global   | oui      | Protocole pour les vérifications de santé (`http` ou `https`).         |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`     | global   | oui      | Vérifier les certificats TLS lors des vérifications HTTPS.             |
| `LOADBALANCER_HEALTHCHECK_HOST`           |           | global   | oui      | Remplacer l'en-tête Host pendant les vérifications (utile pour SNI).   |

### Démarrage rapide

1. Définissez votre pool : définissez `LOADBALANCER_UPSTREAM_NAME=my-app` et listez les cibles dans `LOADBALANCER_UPSTREAM_SERVERS` (ex. `10.0.0.1:8080 10.0.0.2:8080`).
2. Dirigez le trafic : définissez `REVERSE_PROXY_HOST=http://my-app` pour que le proxy inverse utilise l'upstream nommé.
3. Choisissez un mode : gardez round-robin par défaut ou définissez `LOADBALANCER_UPSTREAM_MODE=sticky` avec `LOADBALANCER_UPSTREAM_STICKY_METHOD=cookie` ou `ip`.
4. Ajoutez de la santé : gardez `/status` ou ajustez les URLs, intervalles et statuts valides pour refléter le comportement de votre app.
5. Réglez les connexions : configurez les valeurs keepalive pour réutiliser les connexions backend et réduire la surcharge de handshake.

### Conseils d'utilisation

- Faites correspondre `REVERSE_PROXY_HOST` à `LOADBALANCER_UPSTREAM_NAME` lors de l'utilisation de cookies sticky pour que les clients s'épinglent au bon pool.
- Gardez les intervalles et timeouts des vérifications de santé équilibrés pour éviter les oscillations sur les liens lents.
- Activez `LOADBALANCER_UPSTREAM_RESOLVE` lorsque vous pointez vers des hostnames qui peuvent changer via DNS.
- Réglez les valeurs keepalive pour refléter la capacité backend et les objectifs de réutilisation des connexions.

## Custom Pages <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Le plugin Custom Pages vous permet de remplacer les pages intégrées de BunkerWeb (pages d'erreur, page du serveur par défaut et pages de défi antibot) par vos propres modèles HTML ou Lua personnalisés. Cela vous permet de maintenir une image de marque cohérente sur toutes les pages destinées aux utilisateurs servies par BunkerWeb.

### Fonctionnalités

- **Pages d'erreur personnalisées par service** et **pages de défi antibot** (captcha, vérification JavaScript, reCAPTCHA, hCaptcha, Turnstile, mCaptcha).
- **Page du serveur par défaut personnalisée globale** pour le vhost de repli/par défaut.
- **Analyse HTML et vérifications d'équilibre des balises de modèle Lua** avant qu'un modèle soit accepté.
- **Mise en cache automatique** vers `/var/cache/bunkerweb/custom_pages` avec détection des modifications pour déclencher les rechargements.
- **Configuration par site ou globale** via les paramètres/UI ou les variables d'environnement.

### Comment ça fonctionne

1. Au démarrage (ou lorsque les paramètres changent), le job `custom-pages.py` lit les chemins de modèles configurés.
2. Chaque fichier doit exister et être lisible par le scheduler ; le job valide la structure HTML et l'équilibre des balises de modèle Lua (`{% %}`, `{{ }}`, `{* *}`).
3. Les fichiers acceptés sont mis en cache sous `/var/cache/bunkerweb/custom_pages/<type>.html` ; les paramètres manquants/vides suppriment le fichier mis en cache.
4. NGINX est dirigé vers le répertoire de cache via `$template_root` lorsqu'au moins une page mise en cache existe, de sorte que vos modèles sont servis à la place des pages par défaut.

### Paramètres de configuration

| Paramètre                        | Défaut | Contexte  | Description                                                                  |
| -------------------------------- | ------ | --------- | ---------------------------------------------------------------------------- |
| `CUSTOM_ERROR_PAGE`              |        | multisite | Chemin absolu vers le modèle de page d'erreur personnalisé.                  |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |        | global    | Chemin absolu vers le modèle de page du serveur par défaut personnalisé.     |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |        | multisite | Chemin absolu vers la page de défi CAPTCHA antibot personnalisée.            |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |        | multisite | Chemin absolu vers la page de vérification JavaScript antibot personnalisée. |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |        | multisite | Chemin absolu vers la page reCAPTCHA antibot personnalisée.                  |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |        | multisite | Chemin absolu vers la page hCaptcha antibot personnalisée.                   |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |        | multisite | Chemin absolu vers la page Turnstile antibot personnalisée.                  |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |        | multisite | Chemin absolu vers la page mCaptcha antibot personnalisée.                   |

### Référence des variables de modèle

Les modèles BunkerWeb utilisent le moteur [lua-resty-template](https://github.com/bungle/lua-resty-template). Les variables suivantes sont disponibles selon le type de page :

#### Variables de page d'erreur

Ces variables sont disponibles dans les modèles de page d'erreur personnalisés (`CUSTOM_ERROR_PAGE`) :

| Variable         | Type   | Description                                                      |
| ---------------- | ------ | ---------------------------------------------------------------- |
| `title`          | string | Titre complet de la page (ex. `403 - Forbidden`)                 |
| `error_title`    | string | Texte du titre d'erreur (ex. `Forbidden`)                        |
| `error_code`     | string | Code de statut HTTP (ex. `403`, `404`, `500`)                    |
| `error_text`     | string | Message d'erreur descriptif                                      |
| `error_type`     | string | Catégorie d'erreur : `client` (4xx) ou `server` (5xx)            |
| `error_solution` | string | Texte de solution suggérée                                       |
| `nonce_script`   | string | Valeur nonce pour les balises `<script>` inline (conformité CSP) |
| `nonce_style`    | string | Valeur nonce pour les balises `<style>` inline (conformité CSP)  |
| `request_id`     | string | Identifiant de requête unique pour le débogage                   |
| `client_ip`      | string | Adresse IP du client                                             |
| `request_time`   | string | Horodatage de la requête (format : `YYYY-MM-DD HH:MM:SS UTC`)    |

#### Variables de page du serveur par défaut

Ces variables sont disponibles dans les modèles de page du serveur par défaut personnalisés (`CUSTOM_DEFAULT_SERVER_PAGE`) :

| Variable      | Type   | Description                                                     |
| ------------- | ------ | --------------------------------------------------------------- |
| `nonce_style` | string | Valeur nonce pour les balises `<style>` inline (conformité CSP) |

#### Variables de page de défi antibot

Ces variables sont disponibles dans les modèles de page de défi antibot :

**Variables communes (toutes les pages antibot) :**

| Variable       | Type   | Description                                                      |
| -------------- | ------ | ---------------------------------------------------------------- |
| `antibot_uri`  | string | URI d'action de formulaire pour soumettre le défi                |
| `nonce_script` | string | Valeur nonce pour les balises `<script>` inline (conformité CSP) |
| `nonce_style`  | string | Valeur nonce pour les balises `<style>` inline (conformité CSP)  |

**Défi JavaScript (`CUSTOM_ANTIBOT_JAVASCRIPT_PAGE`) :**

| Variable | Type   | Description                                         |
| -------- | ------ | --------------------------------------------------- |
| `random` | string | Chaîne aléatoire utilisée pour la preuve de travail |

**Captcha (`CUSTOM_ANTIBOT_CAPTCHA_PAGE`) :**

| Variable  | Type   | Description                                   |
| --------- | ------ | --------------------------------------------- |
| `captcha` | string | Image captcha encodée en Base64 (format JPEG) |

**reCAPTCHA (`CUSTOM_ANTIBOT_RECAPTCHA_PAGE`) :**

| Variable            | Type    | Description                                              |
| ------------------- | ------- | -------------------------------------------------------- |
| `recaptcha_sitekey` | string  | Votre clé de site reCAPTCHA                              |
| `recaptcha_classic` | boolean | `true` si utilisant reCAPTCHA classique, `false` pour v3 |

**hCaptcha (`CUSTOM_ANTIBOT_HCAPTCHA_PAGE`) :**

| Variable           | Type   | Description                |
| ------------------ | ------ | -------------------------- |
| `hcaptcha_sitekey` | string | Votre clé de site hCaptcha |

**Turnstile (`CUSTOM_ANTIBOT_TURNSTILE_PAGE`) :**

| Variable            | Type   | Description                            |
| ------------------- | ------ | -------------------------------------- |
| `turnstile_sitekey` | string | Votre clé de site Cloudflare Turnstile |

**mCaptcha (`CUSTOM_ANTIBOT_MCAPTCHA_PAGE`) :**

| Variable           | Type   | Description                |
| ------------------ | ------ | -------------------------- |
| `mcaptcha_sitekey` | string | Votre clé de site mCaptcha |
| `mcaptcha_url`     | string | Votre URL mCaptcha         |

### Syntaxe de modèle

Les modèles utilisent la syntaxe de modèle Lua avec les délimiteurs suivants :

- `{{ variable }}` – Afficher une variable (échappée HTML)
- `{* variable *}` – Afficher une variable (brut, non échappé)
- `{% lua_code %}` – Exécuter du code Lua (conditions, boucles, etc.)
- `{-raw-}` ... `{-raw-}` – Bloc brut (pas de traitement)

**Important** : Utilisez toujours les attributs nonce pour les scripts et styles inline pour respecter la Content Security Policy (CSP) :

```html
<style nonce="{*nonce_style*}">
  /* Votre CSS ici */
</style>
<script nonce="{*nonce_script*}">
  // Votre JavaScript ici
</script>
```

### Exemples

=== "Page d'erreur personnalisée"

    Créez un modèle de page d'erreur personnalisé dans `/etc/bunkerweb/templates/error.html` :

    ```html
    {-raw-}<!doctype html>
    <html lang="fr">
      <head>
        <meta charset="utf-8" />
        <title>{{ title }}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f5f5f5;
            color: #333;
          }
          .container {
            text-align: center;
            padding: 2rem;
          }
          .error-code {
            font-size: 6rem;
            font-weight: bold;
            color: {% if error_type == "server" %}#dc3545{% else %}#ffc107{% end %};
            margin: 0;
          }
          .error-title {
            font-size: 1.5rem;
            margin: 1rem 0;
          }
          .error-text {
            color: #666;
            margin-bottom: 1rem;
          }
          .request-info {
            font-size: 0.8rem;
            color: #999;
            margin-top: 2rem;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <p class="error-code">{{ error_code }}</p>
          <h1 class="error-title">{{ error_title }}</h1>
          <p class="error-text">{{ error_text }}</p>
          <p class="error-text">{{ error_solution }}</p>
          <div class="request-info">
            {% if request_id %}
            <p>ID de requête : <code>{{ request_id }}</code></p>
            {% end %}
            {% if request_time %}
            <p>Heure : {{ request_time }}</p>
            {% end %}
          </div>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Page captcha personnalisée"

    Créez une page de défi captcha personnalisée dans `/etc/bunkerweb/templates/captcha.html` :

    ```html
    {-raw-}<!doctype html>
    <html lang="fr">
      <head>
        <meta charset="utf-8" />
        <title>Vérification de sécurité</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          }
          .card {
            background: white;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 400px;
          }
          h1 {
            color: #333;
            margin-bottom: 1rem;
          }
          .captcha-img {
            margin: 1rem 0;
            border-radius: 0.5rem;
          }
          input[type="text"] {
            width: 100%;
            padding: 0.75rem;
            font-size: 1.2rem;
            border: 2px solid #ddd;
            border-radius: 0.5rem;
            text-align: center;
            box-sizing: border-box;
          }
          button {
            margin-top: 1rem;
            padding: 0.75rem 2rem;
            font-size: 1rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
          }
          button:hover {
            background: #5a6fd6;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="card">
          <h1>🔒 Vérification de sécurité</h1>
          <p>Veuillez entrer le texte que vous voyez ci-dessous pour continuer.</p>
          {-raw-}
          <form method="POST" action="{*antibot_uri*}">
            <img class="captcha-img" src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
            {-raw-}
            <input type="text" name="captcha" placeholder="Entrez le code" required autocomplete="off" />
            <button type="submit">Vérifier</button>
          </form>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Page du serveur par défaut personnalisée"

    Créez une page du serveur par défaut personnalisée dans `/etc/bunkerweb/templates/default.html` :

    ```html
    {-raw-}<!doctype html>
    <html lang="fr">
      <head>
        <meta charset="utf-8" />
        <title>Bienvenue</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #1a1a2e;
            color: #eee;
          }
          .container {
            text-align: center;
          }
          h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
          }
          p {
            color: #888;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <h1>🛡️ Protégé par BunkerWeb</h1>
          <p>Ce serveur est sécurisé et prêt.</p>
        </div>
      </body>
    </html>
    {-raw-}
    ```

### Exemples de déploiement

=== "Linux"

    1. Créez vos fichiers de modèle dans un répertoire de votre choix (ex. `/opt/bunkerweb/templates/`) :

        ```bash
        sudo mkdir -p /opt/bunkerweb/templates
        sudo nano /opt/bunkerweb/templates/error.html
        # Collez votre modèle de page d'erreur personnalisé
        ```

    2. Configurez BunkerWeb en éditant `/etc/bunkerweb/variables.env` :

        ```conf
        # Page d'erreur personnalisée pour tous les services (ou utilisez par service avec préfixe)
        CUSTOM_ERROR_PAGE=/opt/bunkerweb/templates/error.html

        # Page du serveur par défaut personnalisée (global uniquement)
        CUSTOM_DEFAULT_SERVER_PAGE=/opt/bunkerweb/templates/default.html

        # Page captcha personnalisée (par service ou globale)
        CUSTOM_ANTIBOT_CAPTCHA_PAGE=/opt/bunkerweb/templates/captcha.html
        ```

    3. Rechargez BunkerWeb :

        ```bash
        sudo systemctl reload bunkerweb
        ```

=== "Docker"

    Le **scheduler** est responsable de la lecture, de la validation et de la mise en cache de vos modèles personnalisés. Seul le scheduler a besoin d'accéder aux fichiers de modèle—BunkerWeb reçoit automatiquement la configuration validée.

    1. Créez vos fichiers de modèle dans un répertoire local (ex. `./templates/`) et définissez les bonnes permissions :

        ```bash
        mkdir templates && \
        chown root:101 templates && \
        chmod 770 templates
        ```

        !!! info "Pourquoi UID/GID 101 ?"
            Le conteneur scheduler s'exécute en tant qu'**utilisateur non privilégié avec UID 101 et GID 101**. Le répertoire doit être lisible par cet utilisateur pour que le scheduler puisse accéder à vos modèles.

        Si le dossier existe déjà :

        ```bash
        chown -R root:101 templates && \
        chmod -R 770 templates
        ```

        Lors de l'utilisation de [Docker en mode rootless](https://docs.docker.com/engine/security/rootless) ou [Podman](https://podman.io/), les UID/GID des conteneurs sont remappés. Vérifiez vos plages subuid/subgid :

        ```bash
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        Par exemple, si la plage commence à **100000**, le GID effectif devient **100100** (100000 + 100) :

        ```bash
        mkdir templates && \
        sudo chgrp 100100 templates && \
        chmod 770 templates
        ```

    2. Montez le répertoire de modèles vers le **scheduler** et configurez les paramètres sur le scheduler (le scheduler agit comme manager et distribue la configuration aux workers BunkerWeb). Vous pouvez monter les modèles vers n'importe quel chemin dans le conteneur :

        ```yaml
        services:
          bunkerweb:
            image: bunkerity/bunkerweb:1.6.9
            # ... autres paramètres (pas de variables d'environnement nécessaires ici pour les pages personnalisées)

          bw-scheduler:
            image: bunkerity/bunkerweb-scheduler:1.6.9
            volumes:
              - ./templates:/custom_templates:ro
            environment:
              - CUSTOM_ERROR_PAGE=/custom_templates/error.html
              - CUSTOM_DEFAULT_SERVER_PAGE=/custom_templates/default.html
              - CUSTOM_ANTIBOT_CAPTCHA_PAGE=/custom_templates/captcha.html
              # ... autres paramètres
        ```

    !!! warning "Accès au scheduler requis"
        Si le scheduler ne peut pas lire les fichiers de modèle (à cause d'un montage manquant ou de permissions incorrectes), les modèles seront silencieusement ignorés et les pages par défaut seront utilisées à la place. Vérifiez les logs du scheduler pour les erreurs de validation.

=== "Kubernetes"

    Le **scheduler** est responsable de la lecture, de la validation et de la mise en cache de vos modèles personnalisés. Vous devez monter les modèles vers le pod du scheduler.

    1. Créez une ConfigMap avec vos modèles :

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: bunkerweb-custom-templates
        data:
          error.html: |
            {-raw-}<!doctype html>
            <html lang="fr">
              <head>
                <meta charset="utf-8" />
                <title>{{ title }}</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                  .error-code { font-size: 4rem; color: #dc3545; }
                </style>
                {-raw-}
              </head>
              <body>
                <p class="error-code">{{ error_code }}</p>
                <h1>{{ error_title }}</h1>
                <p>{{ error_text }}</p>
              </body>
            </html>
            {-raw-}
          captcha.html: |
            {-raw-}<!doctype html>
            <html lang="fr">
              <head>
                <meta charset="utf-8" />
                <title>Vérification de sécurité</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                </style>
                {-raw-}
              </head>
              <body>
                <h1>Veuillez vérifier que vous êtes humain</h1>
                {-raw-}
                <form method="POST" action="{*antibot_uri*}">
                  <img src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
                  {-raw-}
                  <input type="text" name="captcha" placeholder="Entrez le code" required />
                  <button type="submit">Vérifier</button>
                </form>
              </body>
            </html>
            {-raw-}
        ```

    2. Montez la ConfigMap de modèles vers le pod du **scheduler** et configurez les paramètres comme variables d'environnement :

        ```yaml
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: bunkerweb-scheduler
        spec:
          template:
            spec:
              containers:
                - name: bunkerweb-scheduler
                  image: bunkerity/bunkerweb-scheduler:1.6.9
                  env:
                    - name: CUSTOM_ERROR_PAGE
                      value: "/custom_templates/error.html"
                    - name: CUSTOM_ANTIBOT_CAPTCHA_PAGE
                      value: "/custom_templates/captcha.html"
                    # ... autres paramètres
                  volumeMounts:
                    - name: custom-templates
                      mountPath: /custom_templates
                      readOnly: true
                  # ... autres paramètres du conteneur
              volumes:
                - name: custom-templates
                  configMap:
                    name: bunkerweb-custom-templates
              # ... autres paramètres du pod
        ```

    !!! tip "Utilisation du contrôleur Ingress BunkerWeb"
        Si vous utilisez le contrôleur Ingress BunkerWeb, le scheduler est intégré au contrôleur. Montez la ConfigMap vers le pod du contrôleur à la place.

### Notes et dépannage

- **Les chemins doivent être absolus** et se terminer par un nom de fichier ; les valeurs vides désactivent la page personnalisée correspondante et suppriment son cache.
- **Si la validation échoue** (HTML incorrect ou balises Lua déséquilibrées), le modèle est ignoré et la page par défaut reste active. Vérifiez les logs du scheduler pour les détails.
- **Les fichiers mis en cache** se trouvent dans `/var/cache/bunkerweb/custom_pages` ; la mise à jour du fichier source suffit—le job détecte le nouveau hash et recharge NGINX automatiquement.
- **Conformité CSP** : Utilisez toujours les variables `nonce_script` et `nonce_style` pour les scripts et styles inline afin d'assurer une bonne gestion de la Content Security Policy.
- **Test des modèles** : Vous pouvez tester vos modèles localement en les rendant avec un moteur de modèle Lua avant de les déployer sur BunkerWeb.

## OpenID Connect <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
  <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/0e4lcXTIIfs" title="OpenID Connect" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Le plugin **OpenID Connect** (PRO) ajoute le Single Sign-On (SSO) devant votre application en utilisant le flux OAuth 2.0 / OIDC **Authorization Code**.

Il s'exécute dans BunkerWeb (NGINX/Lua) et impose l'authentification pendant la **phase access**, ce qui bloque les requêtes non authentifiées *avant* qu'elles n'atteignent votre upstream.

### Comment fonctionne le flux de requête

Lorsqu'un navigateur demande une URL protégée :

1. S'il n'y a pas de session valide, BunkerWeb redirige l'utilisateur vers le fournisseur d'identité (IdP).
2. L'IdP authentifie l'utilisateur et redirige vers BunkerWeb sur `OPENIDC_REDIRECT_URI` (par défaut : `/callback`) avec un code d'autorisation.
3. BunkerWeb échange le code contre des jetons sur l'endpoint token de l'IdP.
4. Les jetons sont validés (issuer, audience, expiration, `iat` avec tolérance, signature via JWKS).
5. Une session est créée et le navigateur est redirigé vers l'URL initiale.

```mermaid
sequenceDiagram
  participant B as Navigateur
  participant BW as BunkerWeb (OpenIDC)
  participant IdP as Fournisseur d'identité
  participant Up as Upstream

  B->>BW: GET /protected
  alt Non authentifié
  BW-->>B: 302 Redirection vers l'endpoint authorize de l'IdP
  B->>IdP: Requête d'autorisation (nonce/PKCE optionnel)
  IdP-->>B: 302 Redirection vers /callback?code=...
  B->>BW: GET /callback?code=...
  BW->>IdP: Requête token (échange du code)
  IdP-->>BW: ID token + access token (+ refresh token)
  BW-->>B: 302 Redirection vers l'URL d'origine
  end
  B->>BW: GET /protected (authentifié)
  BW->>Up: Transmettre la requête (+ header d'identité optionnel)
  Up-->>BW: Réponse
  BW-->>B: Réponse
```

!!! warning "L'URL de callback doit correspondre à la configuration du client IdP"
    Enregistrez l'URL de callback complète côté IdP (schéma + hôte + chemin). Par exemple avec les valeurs par défaut : `https://app.example.com/callback`.

### Paramètres (expliqués)

!!! info "Paramètres requis"
    Au minimum, `OPENIDC_DISCOVERY` et `OPENIDC_CLIENT_ID` doivent être définis pour que le plugin fonctionne.

#### Activation

- `USE_OPENIDC` (défaut : `no`) : activer ou désactiver l'authentification OpenID Connect pour le site.

#### Fournisseur d'identité (IdP) + enregistrement du client

- `OPENIDC_DISCOVERY` : URL de discovery (ex. `https://idp.example.com/.well-known/openid-configuration`).
- `OPENIDC_CLIENT_ID` : identifiant du client OAuth 2.0 enregistré auprès de l'IdP.
- `OPENIDC_CLIENT_SECRET` : secret du client OAuth 2.0 (utilisé par `basic`, `post` et `secret_jwt`).

#### Callback / redirection

- `OPENIDC_REDIRECT_URI` (défaut : `/callback`) : chemin de callback utilisé par l'IdP après authentification (doit être enregistré côté IdP).

#### Scopes et paramètres d'autorisation

- `OPENIDC_SCOPE` (défaut : `openid email profile`) : liste d'espaces des scopes à demander.
- `OPENIDC_AUTHORIZATION_PARAMS` : paramètres d'autorisation supplémentaires sous forme `key=value` séparés par des virgules.

#### Renforcement de sécurité

- `OPENIDC_USE_NONCE` (défaut : `yes`) : ajouter un nonce aux requêtes d'autorisation.
- `OPENIDC_USE_PKCE` (défaut : `no`) : activer PKCE pour le flux Authorization Code.
- `OPENIDC_IAT_SLACK` (défaut : `120`) : tolérance de dérive d'horloge (secondes) pour la validation des jetons.
- `OPENIDC_ACCEPT_UNSUPPORTED_ALG` (défaut : `no`) : accepter des jetons signés avec des algorithmes non supportés (non recommandé).
- `OPENIDC_FORCE_REAUTHORIZE` (défaut : `no`) : forcer la ré-autorisation à chaque requête (debug uniquement).

#### Cycle de vie session/jetons

- `OPENIDC_REFRESH_SESSION_INTERVAL` : intervalle (secondes) pour ré-authentifier/rafraîchir silencieusement la session (vide = désactivé).
- `OPENIDC_ACCESS_TOKEN_EXPIRES_IN` (défaut : `3600`) : durée par défaut du jeton d'accès si l'IdP ne la fournit pas.
- `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY` (défaut : `yes`) : renouveler automatiquement le jeton d'accès via le refresh token.

#### Paramètres d'authentification sur l'endpoint token

- `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD` (défaut : `basic`) : `basic`, `post`, `secret_jwt`, `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY` : requis avec `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID` : `kid` optionnel pour `private_key_jwt`.
- `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN` : durée de vie (secondes) de l'assertion JWT.

#### Comportement de logout

- `OPENIDC_LOGOUT_PATH` (défaut : `/logout`) : chemin de logout local géré par BunkerWeb.
- `OPENIDC_REVOKE_TOKENS_ON_LOGOUT` (défaut : `no`) : révoquer les jetons côté IdP lors du logout.
- `OPENIDC_REDIRECT_AFTER_LOGOUT_URI` : redirection après logout local (vide = comportement par défaut de l'IdP).
- `OPENIDC_POST_LOGOUT_REDIRECT_URI` : redirection après fin du logout IdP (si supporté).

#### Connectivité et TLS vers l'IdP

- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` (défaut : `10000` ms chacun) : timeouts pour les appels HTTP vers l'IdP.
- `OPENIDC_SSL_VERIFY` (défaut : `yes`) : vérifier les certificats TLS de l'IdP.
- `OPENIDC_KEEPALIVE` (défaut : `yes`) : keepalive pour les connexions IdP.
- `OPENIDC_HTTP_PROXY` / `OPENIDC_HTTPS_PROXY` : proxys pour les appels IdP.

#### Transmission de l'identité à l'upstream

- `OPENIDC_USER_HEADER` (défaut : `X-User`) : header transmis à l'upstream (vide = désactivé).
- `OPENIDC_USER_HEADER_CLAIM` (défaut : `sub`) : claim à extraire pour la valeur du header.
- `OPENIDC_DISPLAY_CLAIM` (défaut : `preferred_username`) : claim utilisé pour l'affichage dans les logs/métriques.

#### Cache

- `OPENIDC_DISCOVERY_DICT_SIZE` (défaut : `1m`) : taille du shared dict pour le cache discovery.
- `OPENIDC_JWKS_DICT_SIZE` (défaut : `1m`) : taille du shared dict pour le cache JWKS.

!!! tip "Stockage de session Redis"
    Lorsque `USE_REDIS=yes` est configuré globalement dans BunkerWeb, le plugin OpenIDC stocke les sessions dans Redis au lieu des cookies (avec fallback automatique vers les cookies si Redis devient indisponible). C'est le mode recommandé pour les déploiements multi-instance / HA.

### Cache discovery + JWKS

Le plugin utilise `OPENIDC_DISCOVERY` (l'URL `.well-known/openid-configuration` de l'IdP) pour découvrir les endpoints, puis récupère et met en cache les clés JWKS pour valider les signatures.

Les données discovery/JWKS sont mises en cache dans des shared dictionaries NGINX. Si vous avez beaucoup de tenants/IdP ou de gros ensembles de clés, augmentez :

- `OPENIDC_DISCOVERY_DICT_SIZE` (global)
- `OPENIDC_JWKS_DICT_SIZE` (global)

### Sessions (cookies vs Redis)

Par défaut, les sessions sont stockées dans des cookies sécurisés gérés par la bibliothèque OpenID Connect.

Si `USE_REDIS=yes` est activé globalement et que Redis est configuré, le plugin bascule automatiquement vers des **sessions Redis** (avec fallback automatique vers les cookies si Redis est temporairement indisponible). Recommandé en load-balancing / HA et évite les limites de taille des cookies lorsque les jetons sont volumineux.

### Transmission de l'identité utilisateur à l'upstream

Si `OPENIDC_USER_HEADER` est défini (défaut : `X-User`), le plugin injecte un header extrait d'un claim (défaut : `OPENIDC_USER_HEADER_CLAIM=sub`).

Comportement de sécurité important :

- Le plugin **supprime tout header entrant** portant le même nom que `OPENIDC_USER_HEADER` pour éviter le spoofing côté client.
- Si le claim configuré est absent, le header n'est pas défini.
- Définissez `OPENIDC_USER_HEADER` à une valeur vide pour désactiver la transmission de l'identité.

!!! tip "Choisir un claim"
    Privilégiez des identifiants stables présents dans les jetons (ex. `sub`, `email`, `preferred_username`). Les claims sont lus d'abord depuis l'ID token, puis depuis userinfo si présent.

### Logout

Les requêtes de logout sont gérées sur `OPENIDC_LOGOUT_PATH` (défaut : `/logout`).

- Pour révoquer les jetons côté IdP lors du logout, définissez `OPENIDC_REVOKE_TOKENS_ON_LOGOUT=yes`.
- Utilisez `OPENIDC_REDIRECT_AFTER_LOGOUT_URI` et `OPENIDC_POST_LOGOUT_REDIRECT_URI` pour contrôler les redirections après logout.

### Authentification à l'endpoint token

La plupart des IdP fonctionnent avec la valeur par défaut `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD=basic` (client secret via HTTP Basic). Sont aussi supportés :

- `post`
- `secret_jwt`
- `private_key_jwt` (requiert `OPENIDC_CLIENT_RSA_PRIVATE_KEY`, optionnel `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`)

### Exemples de configuration minimale

Paramètres minimum requis par service protégé :

- `USE_OPENIDC=yes`
- `OPENIDC_DISCOVERY=...`
- `OPENIDC_CLIENT_ID=...`
- `OPENIDC_CLIENT_SECRET=...` (ou configuration de clé JWT pour `private_key_jwt`)

Options fréquentes de durcissement / tuning :

- `OPENIDC_USE_NONCE=yes` (défaut)
- `OPENIDC_USE_PKCE=yes`
- `OPENIDC_IAT_SLACK=...` en cas de dérive d'horloge
- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` adapté à la latence de l'IdP
- `OPENIDC_SSL_VERIFY=yes` (défaut)

### Dépannage

- **403 avec "Authentication failed"** : le plus souvent une URL discovery incorrecte, un mismatch d'URL de callback côté IdP, ou un IdP injoignable.
- **Dérive d'horloge / "token not yet valid"** : activez NTP ; ajustez `OPENIDC_IAT_SLACK` si nécessaire.
- **Header utilisateur absent** : vérifiez que le claim de `OPENIDC_USER_HEADER_CLAIM` existe dans l'ID token/userinfo.
- **Déploiements multi-instance** : activez `USE_REDIS=yes` et configurez `REDIS_HOST` (ou Sentinel) pour partager les sessions.

## OpenAPI Validator <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/3oZOO1XdSlc" title="OpenAPI Validator" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Le plugin **OpenAPI Validator** applique votre contrat d'API en validant les requêtes entrantes par rapport à une spécification OpenAPI / Swagger. Il s'assure que le chemin demandé existe, que la méthode HTTP est autorisée et valide éventuellement les paramètres de requête, d'en-tête, de cookie et de chemin par rapport à leurs définitions de schéma.

### Fonctionnement

1. Un job planifié (`openapi-download.py`) récupère le document OpenAPI à partir d'une URL ou d'un fichier et le met en cache sur le disque (toutes les heures par défaut).
2. Au moment de l'initialisation de NGINX, le plugin compile les routes à partir de la spécification mise en cache et les stocke dans un espace de stockage interne partagé.
3. Pendant le traitement de la requête, le plugin fait correspondre la requête aux routes compilées et applique la validation.

### Fonctionnalités

- Validation du chemin et de la méthode avec une réponse `405` lorsque la méthode n'est pas autorisée.
- Validation optionnelle des paramètres pour les requêtes, les en-têtes, les cookies et les paramètres de chemin.
- Surcharge du chemin de base via `OPENAPI_BASE_PATH` ou déduction automatique à partir de la spécification.
- Autoriser ou refuser les requêtes vers des chemins non listés dans la spécification.
- Liste d'ignorés configurable pour les points de terminaison tels que la documentation ou les fichiers de spécification.
- La spécification mise en cache est actualisée toutes les heures sans bloquer les requêtes.

### Configuration

| Paramètre                    | Défaut                               | Contexte  | Multiple | Description                                                                                          |
| ---------------------------- | ------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `USE_OPENAPI_VALIDATOR`      | `no`                                 | multisite | non      | Activer la validation des routes OpenAPI pour ce site.                                               |
| `OPENAPI_SPEC`               |                                      | multisite | non      | Chemin absolu ou URL HTTP(S) vers le document OpenAPI au format JSON/YAML.                           |
| `OPENAPI_BASE_PATH`          |                                      | multisite | non      | Préfixe de chemin de base optionnel à ajouter à chaque chemin de la spécification.                   |
| `OPENAPI_ALLOW_UNSPECIFIED`  | `no`                                 | multisite | non      | Autoriser les requêtes vers des chemins non listés dans la spécification.                            |
| `OPENAPI_ALLOW_INSECURE_URL` | `no`                                 | multisite | non      | Autoriser la récupération de la spécification OpenAPI via HTTP simple (non recommandé).              |
| `OPENAPI_IGNORE_URLS`        | `^/docs$ ^/redoc$ ^/openapi\\.json$` | multisite | non      | Liste d'expressions régulières d'URL séparées par des espaces pour contourner la validation OpenAPI. |
| `OPENAPI_MAX_SPEC_SIZE`      | `2M`                                 | global    | non      | Taille maximale autorisée du document OpenAPI (accepte les suffixes k/M/G).                          |
| `OPENAPI_VALIDATE_PARAMS`    | `yes`                                | multisite | non      | Valider les paramètres de requête, d'en-tête, de cookie et de chemin par rapport à la spécification. |

### Notes de comportement

- `OPENAPI_SPEC` peut être un fichier local ou une URL HTTPS. Les URL HTTP sont bloquées sauf si `OPENAPI_ALLOW_INSECURE_URL=yes`.
- Si `OPENAPI_BASE_PATH` est vide, le plugin déduit le chemin de base à partir de `servers[*].url` (OpenAPI 3) ou `basePath` (Swagger 2) lorsqu'il est présent.
- Les requêtes `HEAD` sont acceptées lorsque `GET` est défini pour le même chemin, et la correspondance de chemin tolère un slash final.
- Lorsqu'un chemin est absent de la spécification et que `OPENAPI_ALLOW_UNSPECIFIED=no`, la requête est refusée avec le statut de refus configuré.
- Les échecs de validation de paramètres sont refusés et seule la première erreur est enregistrée pour garder les logs concis.

### Démarrage rapide

Définissez les valeurs minimales par service protégé :

- `USE_OPENAPI_VALIDATOR=yes`
- `OPENAPI_SPEC=/path/to/openapi.yaml` (ou `https://...`)

Autorisez éventuellement les chemins inconnus pendant le déploiement :

- `OPENAPI_ALLOW_UNSPECIFIED=yes`

## Cache <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Prise en charge de STREAM :x:

Le plugin Cache PRO active la mise en cache des réponses au niveau du reverse proxy à l'aide des directives NGINX `proxy_cache*`. Il est utile pour absorber les lectures répétées sur du contenu cacheable, soulager les upstreams lors des pics de charge et servir du contenu périmé pendant de courtes indisponibilités du backend.

**Fonctionnement**

1. Chaque valeur globale `CACHE_PATH*` crée une directive `proxy_cache_path` dans le contexte HTTP.
2. Un service n'utilise le cache que lorsque `CACHE_ZONE` correspond à l'une des zones déclarées dans `CACHE_PATH*`.
3. Les paramètres au niveau du service contrôlent ensuite la clé de cache, les conditions de bypass/no-cache, le verrouillage, l'utilisation de contenu périmé et les règles de validité.
4. Si `CACHE_HEADER` est défini, BunkerWeb ajoute un en-tête de réponse exposant `$upstream_cache_status` comme `HIT`, `MISS`, `BYPASS`, `EXPIRED` ou `STALE`.

**Liste des fonctionnalités**

- Mise en cache des réponses du reverse proxy avec chemins et zones configurables.
- Activation du cache par service via `CACHE_ZONE`.
- En-tête facultatif exposant l'état du cache avec `$upstream_cache_status`.
- Contrôles fins pour le bypass, le no-cache, la clé, les méthodes, le verrouillage, le stale et la revalidation.
- Plusieurs règles de validité via des paramètres `CACHE_VALID*`.

**Liste des paramètres**

| Réglage                     | Défaut                            | Contexte  | Multiple | Description                                                                |
| --------------------------- | --------------------------------- | --------- | -------- | -------------------------------------------------------------------------- |
| `CACHE_PATH`                |                                   | global    | oui      | Chemin et paramètres d'un cache.                                           |
| `CACHE_ZONE`                |                                   | multisite | non      | Nom de la zone de cache à utiliser (définie dans un réglage `CACHE_PATH`). |
| `CACHE_HEADER`              | `X-Cache`                         | multisite | non      | Ajoute un en-tête exposant l'état du cache.                                |
| `CACHE_BACKGROUND_UPDATE`   | `no`                              | multisite | non      | Active ou désactive la mise à jour du cache en arrière-plan.               |
| `CACHE_BYPASS`              |                                   | multisite | non      | Liste de variables déterminant si le cache doit être contourné.            |
| `CACHE_NO_CACHE`            | `$http_pragma$http_authorization` | multisite | non      | Désactive le stockage en cache si des variables sont définies.             |
| `CACHE_KEY`                 | `$scheme$proxy_host$request_uri`  | multisite | non      | Clé utilisée pour identifier les éléments mis en cache.                    |
| `CACHE_CONVERT_HEAD_TO_GET` | `yes`                             | multisite | non      | Convertit les requêtes HEAD en GET lors de la mise en cache.               |
| `CACHE_LOCK`                | `no`                              | multisite | non      | Verrouille les requêtes concurrentes lors du remplissage du cache.         |
| `CACHE_LOCK_AGE`            | `5s`                              | multisite | non      | Envoie la requête à l'upstream si le cache est verrouillé depuis ce délai. |
| `CACHE_LOCK_TIMEOUT`        | `5s`                              | multisite | non      | Envoie la requête à l'upstream si le verrou persiste pendant ce délai.     |
| `CACHE_METHODS`             | `GET HEAD`                        | multisite | non      | Met en cache uniquement les réponses pour ces méthodes HTTP.               |
| `CACHE_MIN_USES`            | `1`                               | multisite | non      | Nombre de requêtes avant de stocker la réponse en cache.                   |
| `CACHE_REVALIDATE`          | `no`                              | multisite | non      | Revalide les éléments expirés via des requêtes conditionnelles.            |
| `CACHE_USE_STALE`           | `off`                             | multisite | non      | Définit dans quels cas servir un contenu périmé.                           |
| `CACHE_VALID`               | `10m`                             | multisite | oui      | Définit la durée de cache avec code(s) HTTP optionnel(s).                  |

**Exemple d'utilisation**

1. Définissez un chemin global et une zone de cache :

   ```yaml
   CACHE_PATH: "/var/cache/bunkerweb/proxy levels=1:2 keys_zone=htmlcache:10m max_size=1g inactive=60m use_temp_path=off"
   ```

2. Activez le reverse proxy et attachez la zone à un service :

   ```yaml
   www.example.com_USE_REVERSE_PROXY: "yes"
   www.example.com_REVERSE_PROXY_HOST: "http://app:8080"
   www.example.com_CACHE_ZONE: "htmlcache"
   www.example.com_CACHE_HEADER: "X-Cache"
   www.example.com_CACHE_VALID: "200 301 302 10m"
   www.example.com_CACHE_VALID_1: "404 1m"
   ```

3. Ajoutez des contrôles optionnels si nécessaire :

   ```yaml
   www.example.com_CACHE_BYPASS: "$cookie_nocache $arg_nocache"
   www.example.com_CACHE_NO_CACHE: "$http_pragma $http_authorization"
   www.example.com_CACHE_LOCK: "yes"
   www.example.com_CACHE_BACKGROUND_UPDATE: "yes"
   www.example.com_CACHE_USE_STALE: "error timeout updating http_500 http_502 http_503 http_504"
   ```

!!! info "Comportement important"
    - Ce plugin s'applique uniquement au trafic reverse proxy. Il ne met pas en cache le contenu servi directement depuis des fichiers statiques locaux ni les services stream/TCP.
    - `CACHE_ZONE` doit correspondre à une zone définie dans une valeur `CACHE_PATH*` via `keys_zone=<nom>:<taille>`.
    - Si `CACHE_ZONE` est vide pour un service, les directives de cache ne sont pas appliquées à ce service.
    - Utilisez des suffixes numériques pour les valeurs répétées, par exemple `CACHE_PATH_1`, `CACHE_PATH_2`, `CACHE_VALID_1` et `CACHE_VALID_2`.
    - Gardez le trafic authentifié ou spécifique à un utilisateur hors cache, sauf si votre `CACHE_KEY` varie explicitement selon cet état.
    - `CACHE_LOCK=yes` et `CACHE_BACKGROUND_UPDATE=yes` permettent de réduire les rafales de requêtes vers l'origine.
