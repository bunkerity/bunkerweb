# Guide de démarrage rapide

!!! info "Prérequis"

    Nous supposons que vous connaissez déjà les [concepts de base](concepts.md) et que vous avez suivi les [instructions d'intégration](integrations.md) pour votre environnement.

    Ce guide de démarrage rapide suppose que BunkerWeb est accessible depuis Internet et que vous avez configuré au moins deux domaines : un pour l'interface Web et un pour votre service web.

    **Exigences système**

    Les spécifications minimales recommandées pour BunkerWeb sont une machine avec 2 (v)CPU et 8 Go de RAM. Notez que cela suffit généralement pour des environnements de test ou des déploiements avec très peu de services.

    Pour des environnements de production avec de nombreux services à protéger, nous recommandons au moins 4 (v)CPU et 16 Go de RAM. Ajustez les ressources en fonction de votre cas d'utilisation, du trafic réseau et des éventuelles attaques DDoS que vous pourriez subir.

    Il est fortement recommandé d'activer le chargement global des règles CRS (en définissant le paramètre `USE_MODSECURITY_GLOBAL_CRS` sur `yes`) si vous êtes dans des environnements à RAM limitée ou en production avec de nombreux services. Plus de détails sont disponibles dans la section [utilisations avancées](advanced.md#running-many-services-in-production) de la documentation.

Ce guide de démarrage rapide vous aidera à installer rapidement BunkerWeb et à sécuriser un service Web à l'aide de l'interface utilisateur Web.

Protéger les applications web existantes déjà accessibles avec le protocole HTTP(S) est l'objectif principal de BunkerWeb : il agira comme un [proxy inverse classique](https://en.wikipedia.org/wiki/Reverse_proxy) avec des fonctionnalités de sécurité supplémentaires.

Consultez le [dossier examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) du dépôt pour obtenir des exemples concrets.

## Configuration de base

=== "Tout-en-un"

    Pour déployer le conteneur tout-en-un, exécutez la commande suivante :

    ```shell
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Par défaut, le conteneur expose :

    * 8080/tcp pour HTTP
    * 8443/tcp pour HTTPS
    * 8443/udp pour QUIC
    * 7000/tcp pour l'accès à l'interface utilisateur web sans BunkerWeb en façade (non recommandé en production)

    L'image tout-en-un inclut plusieurs services intégrés, contrôlables via des variables d'environnement. Pour plus d'informations, consultez la section [Image tout-en-un (AIO)](integrations.md#all-in-one-aio-image) de la page des intégrations.

=== "Linux"

    Utilisez le script d'installation Easy Install pour configurer BunkerWeb sur les distributions Linux prises en charge. Il installe et configure automatiquement NGINX, ajoute le dépôt BunkerWeb et met en place les services requis.

    ```bash
    # Download the script and its checksum
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc3/install-bunkerweb.sh
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8-rc3/install-bunkerweb.sh.sha256

    # Verify the checksum
    sha256sum -c install-bunkerweb.sh.sha256

    # If the check is successful, run the script
    chmod +x install-bunkerweb.sh
    sudo ./install-bunkerweb.sh
    ```

    !!! danger "Avis de sécurité"
        Vérifiez toujours l'intégrité du script avec la somme de contrôle fournie avant de l'exécuter.

    #### Points forts d'Easy Install

    - Détecte votre distribution Linux et l'architecture CPU en amont et avertit si vous sortez de la matrice supportée avant toute modification.
    - Le flux interactif vous laisse choisir le profil d'installation (full stack, manager, worker, etc.) ; le mode manager expose toujours l'API sur `0.0.0.0`, désactive l'assistant et demande l'IP à autoriser (passez-la avec `--manager-ip` en mode non interactif), tandis que le mode worker exige les IP du manager pour sa liste blanche.
    - Les installations Manager peuvent toujours décider si le service Web UI doit démarrer, même si l'assistant reste désactivé.
    - Le récapitulatif indique si le service FastAPI sera lancé, ce qui vous permet de l'activer ou de le désactiver volontairement via `--api` / `--no-api`.
    - Les options CrowdSec ne sont disponibles que pour les installations full stack ; les modes manager/worker les ignorent automatiquement pour se concentrer sur le pilotage distant.

    Pour des méthodes d'installation avancées (gestionnaire de paquets, types d'installation, options non interactives, intégration CrowdSec, etc.), consultez l'[intégration Linux](integrations.md#linux).

=== "Docker"

    Voici le fichier docker-compose complet que vous pouvez utiliser ; veuillez noter que nous connecterons ultérieurement le service web au réseau `bw-services` :

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for both services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      # Optionnel : définir un jeton API et le refléter dans les deux conteneurs
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          <<: *bw-env # We use the anchor to avoid repeating the same settings for all services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

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

      redis: # Redis service for the persistence of reports/bans/stats
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

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    Voici le fichier docker-compose complet que vous pouvez utiliser ; veuillez noter que nous connecterons ultérieurement le service web au réseau `bw-services` :

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        labels:
          - "bunkerweb.INSTANCE=yes" # We set the instance label to allow the autoconf to detect the instance
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.8-rc3
        depends_on:
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *bw-ui-env
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

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

      redis: # Redis service for the persistence of reports/bans/stats
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

    volumes:
      bw-data:
      bw-storage:
      redis-data:

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

    La méthode recommandée pour installer Kubernetes est d'utiliser le chart Helm disponible à l'adresse `https://repo.bunkerweb.io/charts` :

    ```shell
    helm repo add bunkerweb https://repo.bunkerweb.io/charts
    ```

    Vous pouvez ensuite utiliser le chart Helm `bunkerweb` depuis ce dépôt :

    ```shell
    helm install mybw bunkerweb/bunkerweb --namespace bunkerweb --create-namespace
    ```

    Une fois installé, vous pouvez obtenir l'adresse IP du `LoadBalancer` pour configurer vos domaines :

    ```shell
    kubectl -n bunkerweb get svc mybw-external -o=jsonpath='{.status.loadBalancer.ingress[0].ip}'
    ```

=== "Swarm"

    !!! warning "Dépréciée"
        L'intégration Swarm est dépréciée et sera supprimée dans une prochaine version. Veuillez envisager d'utiliser plutôt l'[intégration Kubernetes](integrations.md#kubernetes).

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Voici le fichier stack docker-compose complet que vous pouvez utiliser ; veuillez noter que nous connecterons ultérieurement le service web au réseau `bw-services` :

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
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
            protocol: udp # For QUIC / HTTP3 support
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
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
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.8-rc3
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *bw-ui-env
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

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

      bw-redis:
        image: redis:8-alpine
        networks:
          - bw-universe

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

## Terminer l'assistant de configuration {#complete-the-setup-wizard}

!!! tip "Accès à l'assistant de configuration"

    You can access the setup wizard by browsing the `https://your-fqdn-or-ip-addresss/setup` URI of your server.

### Créer un compte administrateur

Vous devriez voir une page de configuration comme celle-ci :
<figure markdown>
  ![Page d'accueil de l'assistant d'installation](assets/img/ui-wizard-step1.png){ align=center }
  <figcaption>Page d'accueil de l'assistant de configuration</figcaption>
</figure>

Une fois que vous êtes sur la page de configuration, vous pouvez entrer le nom d'utilisateur, l'**adresse e-mail et le mot de passe de l'administrateur** et cliquer sur le bouton "Suivant".

### Configurer le proxy inverse, HTTPS et d'autres paramètres avancés

=== "Configuration de base"

    La prochaine étape vous demandera de saisir le **nom du serveur** (domaine/FQDN) que l'interface web utilisera.

    Vous pouvez également choisir d'activer [Let's Encrypt](features.md#lets-encrypt).

    <figure markdown>
      ![Assistant d'installation étape 2](assets/img/ui-wizard-step2.png){ align=center }
      <figcaption>Assistant d'installation étape 2</figcaption>
    </figure>

=== "Configuration avancée"

    L'étape suivante vous demandera de saisir le **nom du serveur** (domaine/FQDN) que l'interface web utilisera.

    Vous pouvez également choisir d'activer [Let's Encrypt](features.md#lets-encrypt).

    Si vous développez la section `Paramètres avancés`, vous pouvez aussi configurer les options suivantes :

    * **Proxy inverse** : ajustez les paramètres du proxy inverse pour l'interface d'administration (par exemple, si vous souhaitez utiliser un chemin personnalisé).
    * [**IP réelle**](features.md#real-ip) : configurez les paramètres d'IP réelle pour identifier correctement l'adresse IP du client (par exemple, si vous êtes derrière un équilibreur de charge ou un CDN).
    * [**Certificat personnalisé**](features.md#custom-ssl-certificate) : téléversez un certificat TLS personnalisé si vous ne souhaitez pas utiliser Let's Encrypt.

    <figure markdown>
      ![Assistant d'installation étape 2](assets/img/ui-wizard-step2-advanced.png){ align=center }
      <figcaption>Assistant d'installation étape 2 (avancé)</figcaption>
    </figure>

### Activation PRO

Si vous avez une licence PRO, vous pouvez l'activer en saisissant votre clé de licence dans la `Upgrade to PRO` section. Cela activera les fonctionnalités PRO de BunkerWeb.

<figure markdown>
  ![Assistant d'installation PRO step](assets/img/ui-wizard-step3.png){ align=center }
  <figcaption>Étape de l'assistant d'installation PRO</figcaption>
</figure>

### Vue d'ensemble de vos paramètres

La dernière étape vous donnera un aperçu des paramètres que vous avez saisis. Vous pouvez cliquer sur le bouton "Configurer" pour terminer la configuration.

<figure markdown>
  ![Étape finale de l'assistant d'installation](assets/img/ui-wizard-step4.png){ align=center }
  <figcaption>Étape finale de l'assistant d'installation</figcaption>
</figure>


## Accès à l'interface web

Vous pouvez maintenant accéder à l'interface Web en accédant au domaine que vous avez configuré à l'étape précédente et à l'URI si vous l'avez modifié (par défaut ). `https://your-domain/`

<figure markdown>
  ![Page de connexion à l'interface Web](assets/img/ui-login.png){ align=center }
  <figcaption>Page de connexion de l'interface web</figcaption>
</figure>

Vous pouvez maintenant vous connecter avec le compte administrateur que vous avez créé lors de l'assistant d'installation.

<figure markdown>
  ![Interface web home](assets/img/ui-home.png){ align=center }
  <figcaption>Accueil de l'interface Web</figcaption>
</figure>

## Création d'un nouveau service

=== "Interface utilisateur Web"

    Vous pouvez créer un nouveau service en vous rendant dans la section `Services` de l'interface web et en cliquant sur le bouton `➕ Créer un nouveau Service`.

    Plusieurs façons existent pour créer un service via l'interface web :

    * Le **mode facile** vous guidera tout au long du processus de création d'un nouveau service.
    * Le **mode avancé** vous permettra de configurer le service avec davantage d'options.
    * Le **mode Brut** vous permettra de saisir directement la configuration, comme si vous éditiez le fichier `variables.env`.

    !!! tip "Service brouillon"

        Vous pouvez créer un service brouillon pour enregistrer vos progrès et y revenir plus tard. Il suffit de cliquer sur le bouton `🌐 En Ligne` pour basculer le service en mode brouillon.

    === "Mode facile"

        Dans ce mode, vous pouvez choisir parmi les modèles disponibles et remplir les champs obligatoires.

        <figure markdown>
          ![Interface web — création de service (mode facile)](assets/img/ui-create-service-easy.png){ align=center }
          <figcaption>Interface web — création de service (mode facile)</figcaption>
        </figure>

        * Une fois que vous avez sélectionné le modèle, vous pouvez remplir les champs obligatoires et suivre les instructions pour créer le service.
        * Une fois que vous avez terminé de configurer le service, vous pouvez cliquer sur le `💾 Enregistrer` bouton pour enregistrer la configuration.

    === "Mode avancé"

        Dans ce mode, vous pouvez configurer le service avec davantage d'options tout en visualisant tous les paramètres disponibles de l'ensemble des plugins.

        <figure markdown>
          ![Interface web — création de service (mode avancé)](assets/img/ui-create-service-advanced.png){ align=center }
          <figcaption>Interface web — création de service (mode avancé)</figcaption>
        </figure>

        * Pour naviguer entre les différents plugins, vous pouvez utiliser le menu de navigation sur le côté gauche de la page.
        * Chaque paramètre comporte une petite information qui vous aidera à comprendre ce qu'il fait.
        * Une fois que vous avez terminé de configurer le service, vous pouvez cliquer sur le `💾 Enregistrer` bouton pour enregistrer la configuration.

    === "Mode brut"

        Dans ce mode, vous pouvez saisir la configuration directement, comme si vous éditiez le fichier `variables.env`.

        <figure markdown>
          ![Interface web — création de service (mode brut)](assets/img/ui-create-service-raw.png){ align=center }
          <figcaption>Interface web — création de service (mode brut)</figcaption>
        </figure>

        * Une fois que vous avez terminé de configurer le service, vous pouvez cliquer sur le bouton `💾 Enregistrer` pour enregistrer la configuration.

    🚀 Une fois que vous avez enregistré la configuration, vous devriez voir votre nouveau service dans la liste des services.

    <figure markdown>
      ![Page de services d'interface Web](assets/img/ui-services.png){ align=center }
      <figcaption>Page des services d'interface Web</figcaption>
    </figure>

    Si vous souhaitez modifier le service, vous pouvez cliquer sur le nom du service ou sur le bouton `📝 Modifier`.

=== "Tout-en-un"

    Lors de l'utilisation de l'image Tout-en-un, les nouveaux services sont configurés en ajoutant des variables d'environnement à la commande docker run du conteneur bunkerweb-aio. Si le conteneur est déjà en cours d'exécution, vous devez l'arrêter et le supprimer, puis le relancer avec les variables d'environnement mises à jour.

    Supposons que vous souhaitiez protéger une application myapp (exécutée dans un autre conteneur et accessible depuis BunkerWeb à l'adresse http://myapp:8080) et la rendre disponible sur www.example.com. Vous devez ajouter ou modifier les variables d'environnement suivantes dans votre commande docker run :

    ```shell
    # First, stop and remove the existing container if it's running:
    # docker stop bunkerweb-aio
    # docker rm bunkerweb-aio

    # Then, re-run the bunkerweb-aio container with additional/updated environment variables:
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      # --- Add/modify these environment variables for your new service ---
      -e MULTISITE=yes \
      -e SERVER_NAME="www.example.com" \
      -e "www.example.com_USE_REVERSE_PROXY=yes" \
      -e "www.example.com_REVERSE_PROXY_HOST=http://myapp:8080" \
      -e "www.example.com_REVERSE_PROXY_URL=/" \
      # --- Include any other existing environment variables for UI, Redis, CrowdSec, etc. ---
      bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Votre conteneur d'application (`myapp`) et le conteneur `bunkerweb-aio` doivent être sur le même réseau Docker pour que BunkerWeb puisse y accéder en utilisant le nom d'hôte `myapp`.

    Exemple de configuration réseau :
    ```shell
    # 1. Create a custom Docker network (if you haven't already):
    docker network create my-app-network

    # 2. Run your application container on this network:
    docker run -d --name myapp --network my-app-network your-app-image

    # 3. Add --network my-app-network to the bunkerweb-aio docker run command:
    docker run -d \
      --name bunkerweb-aio \
      --network my-app-network \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
    #   ... (all other relevant environment variables as shown in the main example above) ...
      bunkerity/bunkerweb-all-in-one:1.6.8-rc3
    ```

    Assurez-vous de remplacer `myapp` par le nom réel ou l'adresse IP de votre conteneur d'application et `http://myapp:8080` par son adresse et son port corrects.

=== "Fichier Linux variables.env"

    Nous supposons que vous avez suivi la [Configuration de base](#__tabbed_1_2) et que l'intégration Linux est en cours d'exécution sur votre machine.

    Vous pouvez créer un nouveau service en modifiant le fichier `variables.env` situé dans le répertoire `/etc/bunkerweb/`.

    ```shell
    nano /etc/bunkerweb/variables.env
    ```

    Vous pouvez ensuite ajouter la configuration suivante :

    ```shell
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/
    www.example.com_REVERSE_PROXY_HOST=http://myapp:8080
    ```

    Vous pouvez ensuite recharger le service `bunkerweb-scheduler` pour appliquer les modifications.

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

=== "Docker"

    Nous supposons que vous avez suivi la [Configuration de base](#__tabbed_1_3) et que l'intégration Docker fonctionne sur votre machine.

    Vous devez disposer d'un réseau nommé `bw-services` afin de pouvoir connecter votre application existante et configurer BunkerWeb :

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    Ensuite, vous pouvez ajouter manuellement le service dans le fichier docker compose que vous avez créé à l'étape précédente :

    ```yaml
    ...

    services:
      ...
      bw-scheduler:
        ...
        environment:
          ...
          SERVER_NAME: "www.example.com" # When using the Docker integration, you can set the configuration directly in the scheduler, make sure to set the correct domain name
          MULTISITE: "yes" # Enable multisite mode so you can add multiple services
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/"
          www.example.com_REVERSE_PROXY_HOST: "http://myapp:8080"
          ...
    ```

    Vous pouvez ensuite redémarrer le service `bw-scheduler` pour appliquer les modifications.

    ```shell
    docker compose down bw-scheduler && docker compose up -d bw-scheduler
    ```

=== "Étiquettes Docker autoconf"

    Nous supposons que vous avez suivi la [Configuration de base](#__tabbed_1_4) et que l'intégration Docker autoconf est en cours d'exécution sur votre machine.

    Vous devez disposer d'un réseau nommé `bw-services` afin de pouvoir connecter votre application existante et configurer BunkerWeb à l'aide d'étiquettes :

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services
    	  labels:
    	    - "bunkerweb.SERVER_NAME=www.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    Cela créera automatiquement un nouveau service en utilisant les étiquettes fournies comme configuration.

=== "Annotations Kubernetes"

    Nous supposons que vous avez suivi la [Configuration de base](#__tabbed_1_5) et que la stack Kubernetes est en cours d'exécution sur votre cluster.

    Supposons que vous disposiez d'un Deployment typique avec un Service pour accéder à l'application web depuis l'intérieur du cluster :

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app
      labels:
    	app: app
    spec:
      replicas: 1
      selector:
    	matchLabels:
    	  app: app
      template:
    	metadata:
    	  labels:
    		app: app
    	spec:
    	  containers:
    	  - name: app
    		image: bunkerity/bunkerweb-hello:v1.0
    		ports:
    		- containerPort: 8080
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app
    spec:
      selector:
    	app: app
      ports:
    	- protocol: TCP
    	  port: 80
    	  targetPort: 8080
    ```

    Voici la définition Ingress correspondante pour servir et protéger l'application web :

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/DUMMY_SETTING: "value"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app
                  port:
                    number: 80
    ```

=== "Étiquettes Swarm"

    !!! warning "Dépréciée"
        L'intégration Swarm est dépréciée et sera supprimée dans une prochaine version. Veuillez envisager d'utiliser plutôt l'[intégration Kubernetes](integrations.md#kubernetes).

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

      Nous supposons que vous avez suivi la [Configuration de base](#__tabbed_1_5) et que la stack Swarm est en cours d'exécution sur votre cluster et connectée à un réseau nommé `bw-services` afin de pouvoir connecter votre application existante et configurer BunkerWeb à l'aide d'étiquettes :

    ```yaml
    services:
      myapp:
        image: bunkerity/bunkerweb-hello:v1.0
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## Aller plus loin

Félicitations! Vous venez d'installer BunkerWeb et de sécuriser votre premier service web. Veuillez noter que BunkerWeb offre beaucoup plus, tant en termes de sécurité que d'intégrations avec d'autres systèmes et solutions. Voici une liste de ressources et d'actions qui peuvent vous aider à continuer d'approfondir vos connaissances sur la solution :

- Rejoignez la communauté Bunker : [Discord](https://discord.com/invite/fTf46FmtyD), [LinkedIn](https://www.linkedin.com/company/bunkerity/), [GitHub](https://github.com/bunkerity), [X (anciennement Twitter)](https://x.com/bunkerity)
- Consultez le [blog officiel](https://www.bunkerweb.io/blog?utm_campaign=self&utm_source=doc)
- Explorez  des [cas d'utilisation avancés](advanced.md) dans la documentation
- [Contactez-nous](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc) pour discuter des besoins de votre organisation
