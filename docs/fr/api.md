# API

## Aperçu

L'API de BunkerWeb est le plan de contrôle utilisé pour gérer les instances BunkerWeb de manière programmatique : lister et gérer les instances, les recharger/arrêter, gérer les bannissements, les plugins, les tâches, les configurations, et plus encore. Elle expose une application FastAPI documentée avec une authentification forte, une gestion des autorisations et une limitation de débit.

Ouvrez la documentation interactive sur `/docs` (ou `<root_path>/docs` si vous avez défini `API_ROOT_PATH`). Le schéma OpenAPI est disponible sur `/openapi.json`.

!!! warning "Sécurité"
    L'API est un plan de contrôle privilégié. Ne l'exposez pas sur l'Internet public sans protections supplémentaires.

    Au minimum, restreignez les adresses IP sources (`API_WHITELIST_IPS`), activez l'authentification (`API_TOKEN` ou des utilisateurs API + Biscuit), et envisagez de la placer derrière BunkerWeb avec une URL difficile à deviner et des contrôles d'accès supplémentaires.

## Prérequis

Le service API nécessite un accès à la base de données de BunkerWeb (`DATABASE_URI`). Il est généralement déployé aux côtés du Planificateur (Scheduler) et, optionnellement, de l'Interface Web (Web UI). La configuration recommandée est d'exécuter BunkerWeb en tant que reverse proxy en amont et d'isoler l'API sur un réseau interne.

Consultez l'assistant et les conseils d'architecture dans le [guide de démarrage rapide](quickstart-guide.md).

## Points clés

-   Gestion des instances : diffuse les actions opérationnelles aux instances découvertes.
-   Authentification forte : Basic pour les administrateurs, jeton Bearer pour un accès admin complet, ou jeton Biscuit pour des permissions granulaires.
-   Liste blanche d'IP et limitation de débit flexible par route.
-   Signaux standards de santé/disponibilité (`health`/`readiness`) et vérifications de sécurité au démarrage.

## Modèles de configuration Docker Compose

=== "Docker"

    Exposer l'API en reverse proxy sous `/api` avec BunkerWeb.

    ```yaml
    x-bw-env: &bw-env
      # Liste blanche commune pour le plan de contrôle des instances (BunkerWeb/Scheduler)
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          <<: *bw-env
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb"  # Doit correspondre au nom de service de l'instance
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
          DISABLE_DEFAULT_SERVER: "yes"
          # Reverse proxy pour l'API sur /api
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/api"
          www.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.5
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Utilisez un mot de passe robuste
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"                      # Liste blanche de l'API
          API_TOKEN: "secret"                                                 # Jeton optionnel pour accès admin complet
          API_ROOT_PATH: "/api"                                               # Doit correspondre au chemin du reverse proxy
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Évite les problèmes avec les requêtes volumineuses
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"  # Utilisez un mot de passe robuste
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
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

=== "Docker Autoconf"

    Identique à ci-dessus, mais en utilisant le service Autoconf pour découvrir et configurer automatiquement les services. L'API est exposée sous `/api` grâce aux labels sur le conteneur de l'API.

    ```yaml
    x-api-env: &api-env
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Utilisez un mot de passe robuste

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5
        environment:
          <<: *api-env
          BUNKERWEB_INSTANCES: ""    # Découvert par Autoconf
          SERVER_NAME: ""            # Rempli via les labels
          MULTISITE: "yes"           # Obligatoire avec Autoconf
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *api-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.5
        environment:
          <<: *api-env
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"
          API_TOKEN: "secret"
          API_ROOT_PATH: "/api"
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/api"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-api:8888"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
        networks:
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
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
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

!!! warning "Chemin du reverse proxy"
    Gardez le chemin de l'API difficile à deviner et combinez-le avec la liste blanche et l'authentification de l'API.

    Si vous exposez déjà une autre application sur le même nom de serveur avec un modèle (par ex. `USE_TEMPLATE`), préférez un nom d'hôte distinct pour l'API afin d'éviter les conflits.

### All-In-One

Si vous utilisez l'image All-In-One, l'API peut être activée en définissant `SERVICE_API=yes`:

```bash
docker run -d \
  --name bunkerweb-aio \
  -e SERVICE_API=yes \
  -e API_WHITELIST_IPS="127.0.0.0/8" \
  -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5
```

## Authentification

Méthodes supportées pour authentifier les requêtes :

-   **Basic admin** : Lorsque les identifiants appartiennent à un utilisateur admin de l'API, les points d'accès protégés acceptent `Authorization: Basic <base64(username:password)>`.
-   **Bearer admin (jeton global)** : Si `API_TOKEN` est configuré, `Authorization: Bearer <API_TOKEN>` accorde un accès complet.
-   **Jeton Biscuit (recommandé)** : Obtenez un jeton depuis `POST /auth` en utilisant des identifiants Basic ou un corps de requête JSON/formulaire contenant `username` et `password`. Utilisez le jeton retourné comme `Authorization: Bearer <token>` pour les appels suivants.

Exemple : obtenir un jeton Biscuit, lister les instances, puis les recharger toutes.

```bash
# 1) Obtenir un jeton Biscuit avec des identifiants admin
TOKEN=$(curl -s -X POST -u admin:changeme http://api.example.com/auth | jq -r .token)

# 2) Lister les instances
curl -H "Authorization: Bearer $TOKEN" http://api.example.com/instances

# 3) Recharger la configuration sur toutes les instances (sans test)
curl -X POST -H "Authorization: Bearer $TOKEN" \
     "http://api.example.com/instances/reload?test=no"
```

### Jetons Biscuit : fonctionnement et vérifications

Les jetons intègrent des "faits" (facts) comme `user(<username>)`, `client_ip(<ip>)`, `domain(<host>)`, et un rôle général `role("api_user", ["read", "write"])` dérivé des permissions de la base de données. Les administrateurs incluent `admin(true)` tandis que les non-administrateurs ont des faits granulaires comme `api_perm(<resource_type>, <resource_id|*>, <permission>)`.

L'autorisation fait correspondre la route/méthode aux permissions requises ; `admin(true)` est toujours accepté. En l'absence de faits granulaires, le système se base sur le rôle général : `GET`/`HEAD`/`OPTIONS` nécessitent `read` ; les verbes d'écriture nécessitent `write`.

Les clés sont stockées dans `/var/lib/bunkerweb/.api_biscuit_private_key` et `/var/lib/bunkerweb/.api_biscuit_public_key`. Vous pouvez aussi fournir `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` via des variables d'environnement ; si ni les fichiers ni les variables ne sont définis, l'API génère et sauvegarde une paire de clés au démarrage.

## Permissions (ACL)

Cette API supporte deux niveaux d'autorisation :

-   **Rôle général** : Les jetons contiennent `role("api_user", ["read"[, "write"]])` pour les points d'accès sans correspondance granulaire. `read` correspond à GET/HEAD/OPTIONS ; `write` correspond à POST/PUT/PATCH/DELETE.
-   **ACL granulaire** : Les jetons intègrent `api_perm(<resource_type>, <resource_id|*>, <permission>)` et les routes déclarent ce qu'elles exigent. `admin(true)` contourne toutes les vérifications.

Types de ressources supportés : `instances`, `global_config`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.

Noms des permissions par type de ressource :

-   instances: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
-   global\_config: `global_config_read`, `global_config_update`
-   services: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
-   configs: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
-   plugins: `plugin_read`, `plugin_create`, `plugin_delete`
-   cache: `cache_read`, `cache_delete`
-   bans: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
-   jobs: `job_read`, `job_run`

**ID de ressource** : Pour les vérifications granulaires, le deuxième segment de l'URL est traité comme `resource_id` lorsque c'est pertinent. Exemples : `/services/{service}` -> `{service}` ; `/configs/{service}/...` -> `{service}`. Utilisez `"*"` (ou omettez) pour accorder la permission globalement pour un type de ressource.

**Configuration des utilisateurs et des ACL :**

-   **Utilisateur admin** : Définissez `API_USERNAME` et `API_PASSWORD` pour créer le premier administrateur au démarrage. Pour renouveler les identifiants plus tard, définissez `OVERRIDE_API_CREDS=yes` (ou assurez-vous que l'admin a été créé avec la méthode `manual`). Il n'y a qu'un seul admin ; les tentatives supplémentaires de création basculent vers la création d'un utilisateur non-admin.
-   **Utilisateurs non-admin et permissions** : Fournissez `API_ACL_BOOTSTRAP_FILE` pointant vers un fichier JSON, ou montez-le sur `/var/lib/bunkerweb/api_acl_bootstrap.json`. L'API le lit au démarrage pour créer/mettre à jour les utilisateurs et les permissions.
-   **Fichier cache ACL** : Un résumé en lecture seule est écrit dans `/var/lib/bunkerweb/api_acl.json` au démarrage pour introspection ; l'autorisation évalue les permissions stockées en base de données et intégrées dans le jeton Biscuit.

Exemples de JSON de bootstrap (les deux formats sont supportés) :

```json
{
  "users": {
    "ci": {
      "admin": false,
      "password": "M0tDeP@sseF0rt!",
      "permissions": {
        "services": {
          "*": { "service_read": true },
          "app-frontend": { "service_update": true, "service_delete": false }
        },
        "configs": {
          "app-frontend": { "config_read": true, "config_update": true }
        }
      }
    },
    "ops": {
      "admin": false,
      "password_hash": "$2b$13$...hash-bcrypt...",
      "permissions": {
        "instances": { "*": { "instances_execute": true } },
        "jobs": { "*": { "job_run": true } }
      }
    }
  }
}
```

Ou en format liste :

```json
{
  "users": [
    {
      "username": "ci",
      "password": "M0tDeP@sseF0rt!",
      "permissions": [
        { "resource_type": "services", "resource_id": "*", "permission": "service_read" },
        { "resource_type": "services", "resource_id": "app-frontend", "permission": "service_update" }
      ]
    }
  ]
}
```

Notes :
- Les mots de passe peuvent être en clair (`password`) ou bcrypt (`password_hash` / `password_bcrypt`). Les mots de passe en clair trop faibles sont rejetés en dehors des builds de débogage ; si manquant, un mot de passe aléatoire est généré et un avertissement est journalisé.
- `resource_id: "*"` (ou null/vide) accorde la permission globalement pour ce type de ressource.
- Les mots de passe des utilisateurs existants peuvent être mis à jour et des permissions supplémentaires peuvent être appliquées via le bootstrap.

## Référence des fonctionnalités

L'API est organisée par routeurs thématiques. Utilisez les sections ci-dessous comme un aperçu des capacités ; le schéma interactif sur `/docs` documente en détail les modèles de requête/réponse.

### Cœur et authentification

-   `GET /ping`, `GET /health` : sondes de vivacité légères pour le service API lui-même.
-   `POST /auth` : échangez des identifiants Basic (ou le jeton admin global) contre un jeton Biscuit. Accepte JSON, formulaire, ou les en-têtes `Authorization`. Les admins peuvent aussi continuer à utiliser l'authentification HTTP Basic sur les routes protégées.

### Plan de contrôle des instances

-   `GET /instances` : liste les instances enregistrées, avec horodatages, méthode d'enregistrement et métadonnées.
-   `POST /instances` : enregistre une nouvelle instance gérée par l'API (nom d'hôte, port optionnel, nom de serveur, nom descriptif, méthode).
-   `GET /instances/{hostname}`, `PATCH /instances/{hostname}`, `DELETE /instances/{hostname}` : inspecte, met à jour les champs modifiables, ou supprime les instances gérées par l'API.
-   `DELETE /instances` : suppression en masse ; ignore les instances non gérées par l'API et les signale dans `skipped`.
-   `GET /instances/ping` et `GET /instances/{hostname}/ping` : vérifications de santé sur toutes les instances ou une seule.
-   `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload` : déclenche le rechargement de la configuration (le mode test effectue une validation à blanc).
-   `POST /instances/stop`, `POST /instances/{hostname}/stop` : relaie les commandes d'arrêt aux instances.

### Configuration globale

-   `GET /global_config` : récupère les paramètres non-défaut (utilisez `full=true` pour la configuration complète, `methods=true` pour inclure la provenance).
-   `PATCH /global_config` : crée ou met à jour les paramètres globaux gérés par l'API (`method="api"`) ; les erreurs de validation signalent les clés inconnues ou en lecture seule.

### Cycle de vie des services

-   `GET /services` : énumère les services avec leurs métadonnées, y compris le statut de brouillon et les horodatages.
-   `GET /services/{service}` : récupère les surcharges non-défaut (`full=false`) ou la configuration complète (`full=true`) pour un service.
-   `POST /services` : crée des services, optionnellement en tant que brouillon, et initialise des variables préfixées (`{service}_{KEY}`). Met à jour la liste `SERVER_NAME` de manière atomique.
-   `PATCH /services/{service}` : renomme les services, bascule le statut brouillon/en ligne, et met à jour les variables préfixées. Ignore les modifications directes de `SERVER_NAME` dans `variables` par sécurité.
-   `DELETE /services/{service}` : supprime un service et ses clés de configuration dérivées.
-   `POST /services/{service}/convert?convert_to=online|draft` : bascule rapidement entre les états brouillon/en ligne sans modifier d'autres variables.

### Extraits de configuration personnalisés

-   `GET /configs` : liste les fragments de configuration personnalisés (hooks HTTP/server/stream/ModSecurity/CRS) pour un service (`service=global` par défaut). `with_data=true` intègre le contenu UTF-8 s'il est affichable.
-   `POST /configs` et `POST /configs/upload` : crée de nouveaux extraits depuis des données JSON ou des fichiers téléversés. Types acceptés : `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, et les hooks de plugins CRS. Les noms doivent correspondre à `^[\w_-]{1,64}$`.
-   `GET /configs/{service}/{type}/{name}` : récupère un extrait avec son contenu optionnel (`with_data=true`).
-   `PATCH /configs/{service}/{type}/{name}` et `PATCH .../upload` : met à jour ou déplace les extraits gérés par l'API ; les entrées gérées par modèle ou fichier restent en lecture seule.
-   `DELETE /configs` et `DELETE /configs/{service}/{type}/{name}` : supprime les extraits gérés par l'API tout en préservant ceux gérés par modèle, retournant une liste `skipped` pour les entrées ignorées.

### Orchestration des bannissements

-   `GET /bans` : agrège les bannissements actifs signalés par toutes les instances.
-   `POST /bans` ou `POST /bans/ban` : applique un ou plusieurs bannissements. Les données peuvent être des objets JSON, des tableaux, ou du JSON sous forme de chaîne. `service` est optionnel ; si omis, le bannissement est global.
-   `POST /bans/unban` ou `DELETE /bans` : supprime des bannissements globalement ou par service en utilisant les mêmes formats de données flexibles.

### Gestion des plugins

-   `GET /plugins?type=all|external|ui|pro` : liste les plugins avec leurs métadonnées ; `with_data=true` inclut les octets du paquet si disponibles.
-   `POST /plugins/upload` : installe des plugins UI depuis des archives `.zip`, `.tar.gz`, ou `.tar.xz`. Les archives peuvent contenir plusieurs plugins si chacun a un `plugin.json`.
-   `DELETE /plugins/{id}` : supprime un plugin UI par son ID (`^[\w.-]{4,64}$`).

### Cache et exécution des tâches

-   `GET /cache` : liste les artefacts en cache produits par les tâches du planificateur, filtrés par service, ID de plugin, ou nom de tâche. `with_data=true` inclut le contenu des fichiers s'il est affichable.
-   `GET /cache/{service}/{plugin}/{job}/{file}` : récupère un fichier de cache spécifique (`download=true` le télécharge en pièce jointe).
-   `DELETE /cache` ou `DELETE /cache/{service}/{plugin}/{job}/{file}` : supprime des fichiers de cache et notifie le planificateur des plugins affectés.
-   `GET /jobs` : inspecte les tâches connues, les métadonnées de leur planification, et les résumés du cache.
-   `POST /jobs/run` : demande l'exécution d'une tâche en marquant le ou les plugins associés comme modifiés.

### Notes opérationnelles

-   Les points d'accès en écriture persistent dans la base de données partagée ; les instances récupèrent les changements via la synchronisation du planificateur ou après un `/instances/reload`.
-   Les erreurs sont normalisées en `{ "status": "error", "message": "..." }` avec des codes de statut HTTP appropriés (422 validation, 404 non trouvé, 403 ACL, 5xx erreurs en amont).

## Limitation de débit

La limitation de débit par client est gérée par SlowAPI. Activez/désactivez et configurez les limites via des variables d'environnement ou `/etc/bunkerweb/api.yml`.

-   `API_RATE_LIMIT_ENABLED` (défaut : `yes`)
-   Limite par défaut : `API_RATE_LIMIT_TIMES` par `API_RATE_LIMIT_SECONDS` (ex. `100` par `60`)
-   `API_RATE_LIMIT_RULES` : JSON/CSV en ligne, ou un chemin vers un fichier YAML/JSON avec des règles par route
-   Stockage : en mémoire ou Redis/Valkey lorsque `USE_REDIS=yes` et les variables `REDIS_*` sont fournies (Sentinel supporté)
-   En-têtes : `API_RATE_LIMIT_HEADERS_ENABLED` (défaut : `yes`)

Exemple de YAML (monté dans `/etc/bunkerweb/api.yml`) :

```yaml
API_RATE_LIMIT_ENABLED: yes
API_RATE_LIMIT_DEFAULTS: ["200/minute"]
API_RATE_LIMIT_RULES:
  - path: "/auth"
    methods: "POST"
    times: 10
    seconds: 60
  - path: "/instances*"
    methods: "GET|POST"
    times: 100
    seconds: 60
```

## Configuration

Vous pouvez configurer l'API via des variables d'environnement, des secrets Docker, et les fichiers optionnels `/etc/bunkerweb/api.yml` ou `/etc/bunkerweb/api.env`. Paramètres clés :

-   Docs & schéma : `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`.
-   Authentification de base : `API_TOKEN` (jeton Bearer admin), `API_USERNAME`/`API_PASSWORD` (créer/mettre à jour l'admin), `OVERRIDE_API_CREDS`.
-   ACL et utilisateurs : `API_ACL_BOOTSTRAP_FILE` (chemin JSON).
-   Politique Biscuit : `API_BISCUIT_TTL_SECONDS` (0/désactivé désactive la durée de vie), `CHECK_PRIVATE_IP` (lie le jeton à l'IP du client sauf si privée).
-   Liste blanche IP : `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`.
-   Limitation de débit (cœur) : `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_TIMES`, `API_RATE_LIMIT_SECONDS`, `API_RATE_LIMIT_HEADERS_ENABLED`.
-   Limitation de débit (avancé) : `API_RATE_LIMIT_AUTH_TIMES`, `API_RATE_LIMIT_AUTH_SECONDS`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_DEFAULTS`, `API_RATE_LIMIT_APPLICATION_LIMITS`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_STORAGE_OPTIONS`.
-   Stockage de la limitation de débit : en mémoire ou Redis/Valkey lorsque `USE_REDIS=yes` et les paramètres Redis comme `REDIS_HOST`, `REDIS_PORT`, etc., sont définis. Voir la table des paramètres Redis dans `docs/features.md`.
-   Réseau/TLS : `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`.

### Comment la configuration est chargée

Priorité du plus élevé au plus bas :

1.  Variables d'environnement (ex. `environment:` du conteneur ou variables shell exportées)
2.  Fichiers secrets sous `/run/secrets` (secrets Docker/K8s ; les noms de fichiers correspondent aux noms de variables)
3.  Fichier YAML à l'adresse `/etc/bunkerweb/api.yml`
4.  Fichier d'environnement à l'adresse `/etc/bunkerweb/api.env` (lignes `clé=valeur`)
5.  Valeurs par défaut intégrées

Notes :
- Le YAML supporte l'inclusion de fichiers secrets avec `<file:chemin/relatif>`; le chemin est résolu par rapport à `/run/secrets`.
- Mettez les URL de la documentation à `off`/`disabled`/`none` pour désactiver les points d'accès (ex. `API_DOCS_URL=off`).
- Si `API_SSL_ENABLED=yes`, vous devez aussi définir `API_SSL_CERTFILE` et `API_SSL_KEYFILE`.
- Si Redis est activé (`USE_REDIS=yes`), fournissez les détails de connexion ; voir la section Redis dans `docs/features.md`.

### Authentification et utilisateurs

-   **Bootstrap admin** : définissez `API_USERNAME` et `API_PASSWORD` pour créer le premier admin. Pour réappliquer plus tard, définissez `OVERRIDE_API_CREDS=yes`.
-   **Non-admins et permissions** : fournissez `API_ACL_BOOTSTRAP_FILE` avec un chemin JSON (ou montez-le sur `/var/lib/bunkerweb/api_acl_bootstrap.json`). Le fichier peut lister des utilisateurs et des permissions granulaires.
-   **Clés Biscuit** : définissez `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` ou montez des fichiers sur `/var/lib/bunkerweb/.api_biscuit_public_key` et `/var/lib/bunkerweb/.api_biscuit_private_key`. Si rien n'est fourni, l'API génère et sauvegarde une paire de clés au démarrage.

### TLS et réseau

-   Adresse/port d'écoute : `API_LISTEN_ADDR` (défaut `0.0.0.0`), `API_LISTEN_PORT` (défaut `8888`).
-   Reverse proxies : définissez `API_FORWARDED_ALLOW_IPS` avec les IPs des proxys pour que Gunicorn fasse confiance aux en-têtes `X-Forwarded-*`.
-   Terminaison TLS dans l'API : `API_SSL_ENABLED=yes` plus `API_SSL_CERTFILE` et `API_SSL_KEYFILE` ; optionnellement `API_SSL_CA_CERTS`.

### Limitation de débit : configurations rapides

-   Désactiver globalement : `API_RATE_LIMIT_ENABLED=no`
-   Définir une limite globale simple : `API_RATE_LIMIT_TIMES=100`, `API_RATE_LIMIT_SECONDS=60`
-   Règles par route : définissez `API_RATE_LIMIT_RULES` sur un chemin de fichier JSON/YAML ou du YAML en ligne dans `/etc/bunkerweb/api.yml`.

!!! warning "Sécurité au démarrage"
    L'API se termine si aucun chemin d'authentification n'est configuré (pas de clés Biscuit, pas d'utilisateur admin, et pas de `API_TOKEN`). Assurez-vous qu'au moins une méthode est définie avant de démarrer.

!!! info "Chemin racine et proxys"
    Si vous déployez l'API derrière BunkerWeb sur une sous-URL, définissez `API_ROOT_PATH` sur ce chemin pour que `/docs` et les routes relatives fonctionnent correctement.

## Opérations

-   Santé : `GET /health` renvoie `{"status":"ok"}` lorsque le service est démarré.
-   Service Linux : une unité `systemd` nommée `bunkerweb-api.service` est fournie. Personnalisez via `/etc/bunkerweb/api.env` et gérez avec `systemctl`.
-   Sécurité au démarrage : l'API échoue rapidement si aucun chemin d'authentification n'est disponible (pas de clés Biscuit, pas d'utilisateur admin, pas de `API_TOKEN`). Les erreurs sont écrites dans `/var/tmp/bunkerweb/api.error`.
