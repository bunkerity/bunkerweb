# API

## Rôle de l’API

L’API BunkerWeb est le plan de contrôle pour gérer instances, services, bans, plugins, jobs et configurations personnalisées. Elle tourne en FastAPI derrière Gunicorn et doit rester sur un réseau de confiance. Docs interactives : `/docs` (ou `<API_ROOT_PATH>/docs`) ; schéma OpenAPI : `/openapi.json`.

!!! warning "Gardez-la privée"
    Ne l’exposez pas directement à Internet. Gardez-la en réseau interne, restreignez les IP sources et imposez l’authentification.

!!! info "En bref"
    - Endpoints de santé : `GET /ping` et `GET /health`
    - Chemin racine : définissez `API_ROOT_PATH` en reverse proxy sur un sous-chemin pour que docs et OpenAPI fonctionnent
    - Auth obligatoire : tokens Biscuit, Basic admin ou Bearer de secours
    - Liste blanche IP par défaut sur les plages RFC1918 (`API_WHITELIST_IPS`) ; ne désactivez que si l’upstream contrôle l’accès
    - Rate limiting activé par défaut ; `/auth` a toujours son propre plafond

## Checklist sécurité

- Réseau : gardez le trafic interne ; liez sur loopback ou interface interne et restreignez les IP sources avec `API_WHITELIST_IPS` (activé par défaut).
- Auth présente : définissez `API_USERNAME`/`API_PASSWORD` (admin) et, si besoin, `API_ACL_BOOTSTRAP_FILE` pour d’autres utilisateurs/ACL ; conservez un `API_TOKEN` uniquement pour le break-glass.
- Masquage de chemin : en reverse proxy, choisissez un `API_ROOT_PATH` peu devinable et reflétez-le côté proxy.
- Rate limiting : laissez activé sauf si une autre couche impose des limites équivalentes ; `/auth` est toujours limité.
- TLS : terminez au proxy ou activez `API_SSL_ENABLED=yes` avec chemins de cert/clé.

## Exécution

Choisissez la saveur adaptée à votre environnement.

=== "Docker"

    Compose minimal avec l’API derrière BunkerWeb. Ajustez versions et mots de passe avant usage.

    ```yaml
    x-bw-env: &bw-env
      # On utilise une ancre pour éviter de répéter les mêmes réglages
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Renseignez la plage IP correcte pour que le scheduler envoie la config à l’instance (API interne BunkerWeb)
      # Optionnel : définir un token API et le refléter dans les deux conteneurs (API interne BunkerWeb)
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Mettez un mot de passe DB plus solide

    services:
      bunkerweb:
        # Nom utilisé par le scheduler pour identifier l’instance
        image: bunkerity/bunkerweb:1.6.7~rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Pour QUIC / HTTP3
        environment:
          <<: *bw-env # Réutilisation de l’ancre pour éviter les duplications
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7~rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Assurez-vous de mettre le bon nom d’instance
          SERVER_NAME: "api.example.com"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
          DISABLE_DEFAULT_SERVER: "yes"
          AUTO_LETS_ENCRYPT: "yes"
          api.example.com_USE_TEMPLATE: "api"
          api.example.com_USE_REVERSE_PROXY: "yes"
          api.example.com_REVERSE_PROXY_URL: "/"
          api.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data # Persiste le cache et les sauvegardes
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.7~rc1
        environment:
          <<: *bw-env
          API_USERNAME: "admin"
          API_PASSWORD: "Str0ng&P@ss!"
          # API_TOKEN: "admin-override-token" # optionnel
          FORWARDED_ALLOW_IPS: "*" # Attention : à n’utiliser que si le reverse proxy est l’unique accès
          API_ROOT_PATH: "/"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Max allowed packet plus élevé pour éviter les problèmes de grosses requêtes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Mettez un mot de passe DB plus solide
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis pour persister reports/bans/stats
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
            - subnet: 10.20.30.0/24 # Renseignez la plage IP correcte pour que le scheduler envoie la config à l’instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "All-in-One"

    ```bash
    docker run -d \
      --name bunkerweb-aio \
      -e SERVICE_API=yes \
      -e API_WHITELIST_IPS="127.0.0.0/8" \
      -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.6.7~rc1
    ```

=== "Linux"

    Les paquets DEB/RPM livrent `bunkerweb-api.service`, géré via `/usr/share/bunkerweb/scripts/bunkerweb-api.sh`.

    - Activer/démarrer : `sudo systemctl enable --now bunkerweb-api.service`
    - Recharger : `sudo systemctl reload bunkerweb-api.service`
    - Logs : journal plus `/var/log/bunkerweb/api.log`
    - Écoute par défaut : `127.0.0.1:8888` avec `API_WHITELIST_IPS=127.0.0.1`
    - Fichiers de config : `/etc/bunkerweb/api.env` (créé au premier démarrage avec des defaults commentés) et `/etc/bunkerweb/api.yml`
    - Sources d’environnement : `api.env`, `variables.env`, `/run/secrets/<VAR>`, puis exportées dans le processus Gunicorn

    Modifiez `/etc/bunkerweb/api.env` pour définir `API_USERNAME`/`API_PASSWORD`, la liste blanche, TLS, les limites ou `API_ROOT_PATH`, puis `systemctl reload bunkerweb-api`.

## Authentification et autorisation

- `/auth` émet des Biscuit. Les identifiants peuvent venir de Basic auth, champs de formulaire, corps JSON ou d’un header Bearer égal à `API_TOKEN` (override admin).
- Les admins peuvent aussi appeler les routes protégées en Basic HTTP direct (sans Biscuit).
- Si le Bearer correspond à `API_TOKEN`, l’accès est total/admin. Sinon, la garde Biscuit applique les ACL.
- Le payload Biscuit inclut utilisateur, heure, IP cliente, host, version, un rôle large `role("api_user", ["read", "write"])` et soit `admin(true)`, soit des permissions fines `api_perm(resource_type, resource_id|*, permission)`.
- TTL : `API_BISCUIT_TTL_SECONDS` (0/off désactive l’expiration). Les clés sont sous `/var/lib/bunkerweb/.api_biscuit_private_key` et `.api_biscuit_public_key`, sauf si fournies via `BISCUIT_PRIVATE_KEY`/`BISCUIT_PUBLIC_KEY`.
- Les endpoints d’auth ne sont exposés que lorsqu’au moins un utilisateur API existe en base.

!!! tip "Démarrage auth"
    1. Définissez `API_USERNAME` et `API_PASSWORD` (et `OVERRIDE_API_CREDS=yes` si vous devez réamorcer).
    2. Appelez `POST /auth` en Basic ; lisez `.token` dans la réponse.
    3. Utilisez `Authorization: Bearer <token>` pour les appels suivants.

## Permissions et ACL

- Rôle grossier : GET/HEAD/OPTIONS requièrent `read` ; les verbes d’écriture requièrent `write`.
- L’ACL fine s’applique quand les routes déclarent des permissions ; `admin(true)` contourne les vérifications.
- Types de ressources : `instances`, `global_settings`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.
- Noms de permissions :
  - `instances_*` : `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
  - `global_settings_*` : `global_settings_read`, `global_settings_update`
  - `services` : `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
  - `configs` : `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
  - `plugins` : `plugin_read`, `plugin_create`, `plugin_delete`
  - `cache` : `cache_read`, `cache_delete`
  - `bans` : `ban_read`, `ban_update`, `ban_delete`, `ban_created`
  - `jobs` : `job_read`, `job_run`
- `resource_id` est généralement le deuxième composant de chemin (ex. `/services/{id}`) ; "*" donne un accès global.
- Bootstrap des utilisateurs non admin et des permissions via `API_ACL_BOOTSTRAP_FILE` ou un `/var/lib/bunkerweb/api_acl_bootstrap.json` monté. Mots de passe en clair ou en hash bcrypt.

??? example "Bootstrap ACL minimal"
    ```json
    {
      "users": {
        "ci": {
          "admin": false,
          "password": "Str0ng&P@ss!",
          "permissions": {
            "services": { "*": { "service_read": true } },
            "configs": { "*": { "config_read": true, "config_update": true } }
          }
        }
      }
    }
    ```

## Limitation de débit

Activée par défaut avec deux chaînes : `API_RATE_LIMIT` (global, défaut `100r/m`) et `API_RATE_LIMIT_AUTH` (défaut `10r/m` ou `off`). Formats acceptés : notation style NGINX (`3r/s`, `40r/m`, `200r/h`) ou formes verbeuses (`100/minute`, `200 per 30 minutes`). Configurez via :

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (string CSV/JSON/YAML ou chemin de fichier)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Stockage en mémoire ou Redis/Valkey avec `USE_REDIS=yes` plus réglages `REDIS_*` (Sentinel supporté).

Stratégies (propulsées par `limits`) :

- `fixed-window` (défaut) : le bucket se réinitialise à chaque borne d’intervalle ; le plus léger et suffisant pour des plafonds grossiers.
- `moving-window` : vraie fenêtre glissante avec horodatages précis ; plus douce mais plus coûteuse en opérations de stockage.
- `sliding-window-counter` : hybride qui lisse avec des comptes pondérés de la fenêtre précédente ; plus léger que moving et plus doux que fixed.

Plus de détails et compromis : [https://limits.readthedocs.io/en/stable/strategies.html](https://limits.readthedocs.io/en/stable/strategies.html)

??? example "CSV en ligne"
    ```
    API_RATE_LIMIT_RULES='POST /auth 10r/m, GET /instances* 200r/m, POST|PATCH /services* 40r/m'
    ```

??? example "Fichier YAML"
    ```yaml
    API_RATE_LIMIT: 200r/m
    API_RATE_LIMIT_AUTH: 15r/m
    API_RATE_LIMIT_RULES:
      - path: "/auth"
        methods: "POST"
        rate: "10r/m"
      - path: "/instances*"
        methods: "GET|POST"
        rate: "100r/m"
    ```

## Sources de configuration et priorité

1. Variables d’environnement (y compris `environment:` Docker/Compose)
2. Secrets dans `/run/secrets/<VAR>` (Docker)
3. YAML sous `/etc/bunkerweb/api.yml`
4. Fichier env sous `/etc/bunkerweb/api.env`
5. Valeurs par défaut intégrées

### Runtime et fuseau horaire

| Setting | Description                                                                                                      | Valeurs acceptées                                     | Défaut                                          |
| ------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------- |
| `TZ`    | Fuseau horaire pour les logs API et les claims basés sur le temps (ex. TTL Biscuit et horodatages de logs)       | Nom de la base TZ (ex. `UTC`, `Europe/Paris`)         | unset (défaut conteneur, généralement UTC)      |

Désactivez docs ou schéma en mettant leurs URLs à `off|disabled|none|false|0`. Activez `API_SSL_ENABLED=yes` avec `API_SSL_CERTFILE` et `API_SSL_KEYFILE` pour terminer TLS dans l’API. En reverse proxy, fixez `API_FORWARDED_ALLOW_IPS` aux IPs du proxy pour que Gunicorn fasse confiance aux `X-Forwarded-*`.

### Référence de configuration (power users)

#### Surface & docs

| Setting                                            | Description                                                                                  | Valeurs acceptées           | Défaut                             |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------- | ---------------------------------- |
| `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL` | Chemins Swagger, ReDoc et schéma OpenAPI ; mettre `off/disabled/none/false/0` pour désactiver | Chemin ou `off`             | `/docs`, `/redoc`, `/openapi.json` |
| `API_ROOT_PATH`                                    | Préfixe de montage en reverse proxy                                                          | Chemin (ex. `/api`)         | vide                               |
| `API_FORWARDED_ALLOW_IPS`                          | IPs proxy de confiance pour `X-Forwarded-*`                                                  | IPs/CIDR séparées par virgule | `127.0.0.1` (défaut paquet)        |

#### Auth, ACL, Biscuit

| Setting                                     | Description                                  | Valeurs acceptées                                                  | Défaut                  |
| ------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------ | ----------------------- |
| `API_USERNAME`, `API_PASSWORD`              | Utilisateur admin initial                    | Chaînes ; mot de passe fort requis hors debug                      | unset                   |
| `OVERRIDE_API_CREDS`                        | Réappliquer les creds admin au démarrage     | `yes/no/on/off/true/false/0/1`                                      | `no`                    |
| `API_TOKEN`                                 | Bearer d’override admin                      | Chaîne opaque                                                     | unset                   |
| `API_ACL_BOOTSTRAP_FILE`                    | Chemin JSON pour utilisateurs/permissions    | Chemin ou `/var/lib/bunkerweb/api_acl_bootstrap.json` monté         | unset                   |
| `BISCUIT_PRIVATE_KEY`, `BISCUIT_PUBLIC_KEY` | Clés Biscuit (hex) si pas de fichiers        | Chaînes hex                                                       | auto-générées/persistées |
| `API_BISCUIT_TTL_SECONDS`                   | Durée de vie du token ; `0/off` désactive    | Secondes entières ou `off/disabled`                                | `3600`                  |
| `CHECK_PRIVATE_IP`                          | Lier le Biscuit à l’IP cliente (hors privées) | `yes/no/on/off/true/false/0/1`                                     | `yes`                   |

#### Liste blanche

| Setting                 | Description                               | Valeurs acceptées                | Défaut                 |
| ----------------------- | ----------------------------------------- | -------------------------------- | ---------------------- |
| `API_WHITELIST_ENABLED` | Activer/désactiver le middleware d’IP     | `yes/no/on/off/true/false/0/1`   | `yes`                  |
| `API_WHITELIST_IPS`     | IPs/CIDR séparées par espace/virgule      | IPs/CIDR                         | Plages RFC1918 en code |

#### Limitation

| Setting                          | Description                                   | Valeurs acceptées                                           | Défaut        |
| -------------------------------- | --------------------------------------------- | ----------------------------------------------------------- | ------------- |
| `API_RATE_LIMIT`                 | Limite globale (chaîne style NGINX)           | `3r/s`, `100/minute`, `500 per 30 minutes`                  | `100r/m`      |
| `API_RATE_LIMIT_AUTH`            | Limite de `/auth` (ou `off`)                  | idem ou `off/disabled/none/false/0`                         | `10r/m`       |
| `API_RATE_LIMIT_ENABLED`         | Activer le limiteur                           | `yes/no/on/off/true/false/0/1`                              | `yes`         |
| `API_RATE_LIMIT_HEADERS_ENABLED` | Injecter les headers de limite                | idem                                                        | `yes`         |
| `API_RATE_LIMIT_RULES`           | Règles par chemin (CSV/JSON/YAML ou fichier)  | Chaîne ou chemin                                            | unset         |
| `API_RATE_LIMIT_STRATEGY`        | Algorithme                                    | `fixed-window`, `moving-window`, `sliding-window-counter`   | `fixed-window`|
| `API_RATE_LIMIT_KEY`             | Sélectionneur de clé                          | `ip`, `header:<Name>`                                       | `ip`          |
| `API_RATE_LIMIT_EXEMPT_IPS`      | Exempter ces IPs/CIDR des limites             | Séparées par espace/virgule                                 | unset         |
| `API_RATE_LIMIT_STORAGE_OPTIONS` | JSON fusionné dans la config de stockage      | Chaîne JSON                                                 | unset         |

#### Redis/Valkey (pour les limites)

| Setting                                              | Description               | Valeurs acceptées                | Défaut             |
| ---------------------------------------------------- | ------------------------ | -------------------------------- | ------------------ |
| `USE_REDIS`                                          | Activer le backend Redis | `yes/no/on/off/true/false/0/1`   | `no`               |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`         | Détails de connexion     | Host, int, int                   | unset, `6379`, `0` |
| `REDIS_USERNAME`, `REDIS_PASSWORD`                   | Auth                     | Chaînes                          | unset              |
| `REDIS_SSL`, `REDIS_SSL_VERIFY`                      | TLS et vérification      | `yes/no/on/off/true/false/0/1`   | `no`, `yes`        |
| `REDIS_TIMEOUT`                                      | Timeout (ms)             | Entier                           | `1000`             |
| `REDIS_KEEPALIVE_POOL`                               | Keepalive du pool        | Entier                           | `10`               |
| `REDIS_SENTINEL_HOSTS`                               | Hôtes Sentinel           | `host:port` séparés par espace   | unset              |
| `REDIS_SENTINEL_MASTER`                              | Nom du master Sentinel   | Chaîne                           | unset              |
| `REDIS_SENTINEL_USERNAME`, `REDIS_SENTINEL_PASSWORD` | Auth Sentinel            | Chaînes                          | unset              |

!!! info "Redis fourni par la BD"
    Si la configuration BunkerWeb en base contient Redis/Valkey, l’API la réutilise automatiquement pour le rate limiting même sans `USE_REDIS` dans l’environnement. Surcharger via variables d’environnement si nécessaire.

#### Listener & TLS

| Setting                               | Description                      | Valeurs acceptées                | Défaut                               |
| ------------------------------------- | -------------------------------- | -------------------------------- | ------------------------------------ |
| `API_LISTEN_ADDR`, `API_LISTEN_PORT`  | Adresse/port de bind pour Gunicorn | IP ou hostname, int             | `127.0.0.1`, `8888` (script paquet)  |
| `API_SSL_ENABLED`                     | Activer TLS dans l’API           | `yes/no/on/off/true/false/0/1`   | `no`                                 |
| `API_SSL_CERTFILE`, `API_SSL_KEYFILE` | Certificat et clé PEM            | Chemins de fichier               | unset                                |
| `API_SSL_CA_CERTS`                    | CA/chaîne optionnelle            | Chemin de fichier                | unset                                |

#### Logging & runtime (défauts paquet)

| Setting                         | Description                                                                       | Valeurs acceptées                                 | Défaut                                                             |
| ------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------ |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Niveau de base / override                                                          | `debug`, `info`, `warning`, `error`, `critical`   | `info`                                                             |
| `LOG_TYPES`                     | Destinations                                                                      | `stderr`/`file`/`syslog` séparés par espaces       | `stderr`                                                           |
| `LOG_FILE_PATH`                 | Chemin du log (utilisé si `LOG_TYPES` contient `file` ou `CAPTURE_OUTPUT=yes`)     | Chemin de fichier                                 | `/var/log/bunkerweb/api.log` si file/capture, sinon unset          |
| `LOG_SYSLOG_ADDRESS`            | Cible syslog (`udp://host:514`, `tcp://host:514`, socket)                         | Host:port, host préfixé protocole ou socket       | unset                                                              |
| `LOG_SYSLOG_TAG`                | Tag syslog                                                                        | Chaîne                                           | `bw-api`                                                           |
| `MAX_WORKERS`, `MAX_THREADS`    | Workers/threads Gunicorn                                                          | Entier ou unset pour auto                        | unset                                                              |
| `CAPTURE_OUTPUT`                | Rediriger stdout/stderr Gunicorn vers les handlers configurés                     | `yes` ou `no`                                    | `no`                                                               |

## Surface API (carte des capacités)

- **Core**
  - `GET /ping`, `GET /health` : vérifications de vivacité de l’API.
- **Auth**
  - `POST /auth` : émettre des Biscuit ; accepte Basic, formulaire, JSON ou Bearer override si `API_TOKEN` correspond.
- **Instances**
  - `GET /instances` : lister les instances avec metadata de création/dernière vue.
  - `POST /instances` : enregistrer une instance (hostname/port/server_name/method).
  - `GET/PATCH/DELETE /instances/{hostname}` : inspecter, mettre à jour les champs mutables ou supprimer les instances gérées par l’API.
  - `DELETE /instances` : suppression en masse des instances gérées par l’API ; celles hors API sont ignorées.
  - Santé/actions : `GET /instances/ping`, `GET /instances/{hostname}/ping`, `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`, `POST /instances/stop`, `POST /instances/{hostname}/stop`.
- **Global settings**
  - `GET /global_settings` : par défaut uniquement les non-defaults ; ajoutez `full=true` pour tous les réglages, `methods=true` pour la provenance.
  - `PATCH /global_settings` : upsert des globals détenus par l’API ; les clés read-only sont rejetées.
- **Services**
  - `GET /services` : lister les services (brouillons inclus par défaut).
  - `GET /services/{service}` : récupérer les non-defaults ou la config complète (`full=true`) ; `methods=true` inclut la provenance.
  - `POST /services` : créer un service (draft ou online), définir des variables et mettre à jour `SERVER_NAME` de façon atomique.
  - `PATCH /services/{service}` : renommer, mettre à jour les variables, basculer le draft.
  - `DELETE /services/{service}` : supprimer le service et les clés dérivées de config.
  - `POST /services/{service}/convert?convert_to=online|draft` : bascule rapide draft/online.
- **Custom configs**
  - `GET /configs` : lister les snippets (service par défaut `global`) ; `with_data=true` intègre le contenu imprimable.
  - `POST /configs`, `POST /configs/upload` : créer des snippets via JSON ou upload de fichier.
  - `GET /configs/{service}/{type}/{name}` : récupérer un snippet ; `with_data=true` pour le contenu.
  - `PATCH /configs/{service}/{type}/{name}`, `PATCH .../upload` : mettre à jour ou déplacer les snippets gérés par l’API.
  - `DELETE /configs` ou `DELETE /configs/{service}/{type}/{name}` : supprimer les snippets gérés par l’API ; ceux gérés par template sont ignorés.
  - Types supportés : `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, hooks CRS/plugin.
- **Bans**
  - `GET /bans` : agréger les bans actifs depuis les instances.
  - `POST /bans` ou `/bans/ban` : appliquer un ou plusieurs bans ; le payload peut être objet, tableau ou JSON sérialisé.
  - `POST /bans/unban` ou `DELETE /bans` : lever les bans globalement ou par service.
- **Plugins (UI)**
  - `GET /plugins` : lister les plugins ; `with_data=true` inclut les bytes packagés quand dispo.
  - `POST /plugins/upload` : installer des plugins UI depuis `.zip`, `.tar.gz`, `.tar.xz`.
  - `DELETE /plugins/{id}` : supprimer un plugin par ID.
- **Cache (artefacts de jobs)**
  - `GET /cache` : lister les fichiers de cache avec filtres (`service`, `plugin`, `job_name`) ; `with_data=true` intègre le contenu imprimable.
  - `GET /cache/{service}/{plugin}/{job}/{file}` : récupérer/télécharger un fichier de cache spécifique (`download=true`).
  - `DELETE /cache` ou `DELETE /cache/{service}/{plugin}/{job}/{file}` : supprimer des fichiers de cache et notifier le scheduler.
- **Jobs**
  - `GET /jobs` : lister jobs, plannings et résumés de cache.
  - `POST /jobs/run` : marquer des plugins comme modifiés pour déclencher les jobs associés.

## Comportement opérationnel

- Réponses d’erreur normalisées en `{"status": "error", "message": "..."}` avec les codes HTTP adéquats.
- Les écritures sont persistées en base partagée ; les instances consomment les changements via sync scheduler ou après un reload.
- `API_ROOT_PATH` doit correspondre au chemin reverse proxy pour que `/docs` et les liens fonctionnent.
- Le démarrage échoue s’il n’existe aucun chemin d’auth (pas de clés Biscuit, pas d’admin, pas de `API_TOKEN`) ; les erreurs sont loggées dans `/var/tmp/bunkerweb/api.error`.
