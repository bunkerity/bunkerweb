# Interface Web

## Rôle de l’Interface Web

L’interface Web est le plan de contrôle visuel de BunkerWeb. Elle gère services, paramètres globaux, bannissements, plugins, tâches, cache, journaux et mises à niveau sans passer par la CLI. Elle s’appuie sur Flask + Gunicorn et se place généralement derrière un reverse proxy BunkerWeb.

!!! warning "Gardez-la derrière BunkerWeb"
    L’UI peut modifier la configuration, lancer des tâches et déployer des snippets personnalisés. Placez-la sur un réseau de confiance, faites-la transiter par BunkerWeb et protégez-la par des identifiants forts et du 2FA.

!!! info "En bref"
    - Écoute par défaut : `0.0.0.0:7000` en conteneur, `127.0.0.1:7000` en paquet (changez via `UI_LISTEN_ADDR`/`UI_LISTEN_PORT`)
    - Reverse proxy : respecte `X-Forwarded-*` via `UI_FORWARDED_ALLOW_IPS` ; réglez `PROXY_NUMBERS` si plusieurs proxies empilent les en-têtes
    - Auth : compte admin local (politique de mot de passe imposée), rôles optionnels, 2FA TOTP chiffré par `TOTP_ENCRYPTION_KEYS`
    - Sessions : signées par `FLASK_SECRET`, durée 12 h par défaut, liées à l’IP et au User-Agent ; `ALWAYS_REMEMBER` contrôle les cookies persistants
    - Journaux : `/var/log/bunkerweb/ui.log` (+ access log si capturé), UID/GID 101 dans le conteneur
    - Santé : `GET /healthcheck` optionnel avec `ENABLE_HEALTHCHECK=yes`
    - Dépendances : l’UI lit et écrit la configuration via l’API ; le Scheduler, le Worker, le broker de jobs et la base doivent être disponibles

## Checklist sécurité

- Placez l’UI derrière BunkerWeb sur un réseau interne ; choisissez un `REVERSE_PROXY_URL` difficile à deviner et limitez les IP sources.
- Définissez des `ADMIN_USERNAME` / `ADMIN_PASSWORD` solides ; activez `OVERRIDE_ADMIN_CREDS=yes` uniquement si vous voulez vraiment les réinitialiser.
- Fournissez `TOTP_ENCRYPTION_KEYS` et activez le TOTP pour les comptes admin ; gardez les codes de récupération en sécurité.
- Privilégiez les passkeys : définissez `UI_WEBAUTHN_RP_ID` (ou une unique entrée `UI_ALLOWED_HOSTS`) et enregistrez-en au moins deux par compte. Elles résistent à l'hameçonnage en refusant de signer pour une origine incorrecte ; un second appareil évite le blocage en cas de perte.

- Utilisez le TLS (terminé sur BunkerWeb ou via `UI_SSL_ENABLED=yes` avec chemins cert/clé) ; définissez `UI_FORWARDED_ALLOW_IPS` sur vos proxies de confiance.
- Persistez les secrets : montez `/var/lib/bunkerweb` pour conserver `FLASK_SECRET`, les clés Biscuit et le matériel TOTP après redémarrage.
- Gardez `CHECK_PRIVATE_IP=yes` (par défaut) pour lier les sessions à l’IP ; laissez `ALWAYS_REMEMBER=no` sauf besoin explicite de cookies longue durée.
- Assurez-vous que `/var/log/bunkerweb` est lisible par l’UID/GID 101 (ou l’UID mappé en rootless) pour que l’UI puisse lire les journaux.

## Mise en route

L’UI accède à BunkerWeb via l’API. Exécutez-la avec le Scheduler, le Worker, le broker dédié et la base de données des stacks de référence.

=== "Démarrage rapide (assistant)"

    Utilisez les images publiées et la structure du [guide de démarrage rapide](quickstart-guide.md#__tabbed_1_3), puis terminez l'assistant dans votre navigateur.

=== "Avancé (variables pré-semées)"

    Contournez l’assistant en renseignant identifiants et réseau dès le départ ; exemple Compose avec sidecar syslog :

    ```yaml
    x-service-env: &service-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      API_URL: "http://bw-api:8888"
      API_TOKEN: "changeme" # Replace this shared token before deploying
      CELERY_BROKER_URL: "redis://bw-jobs-broker:6379/0"
      LOG_TYPES: "stderr syslog" # Service logs from supporting components
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.7.0-beta
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *service-env
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-instance-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-api:
        image: bunkerity/bunkerweb-api:1.7.0-beta
        restart: "unless-stopped"
        environment:
          <<: *service-env
          API_USERNAME: "changeme"
          API_PASSWORD: "Ch@ngeme1234"
        networks:
          - bw-universe
          - bw-db

      bw-worker:
        image: bunkerity/bunkerweb-worker:1.7.0-beta
        restart: "unless-stopped"
        depends_on:
          - bw-api
          - bw-jobs-broker
        volumes:
          # Its own volume: DATABASE_URI points at a real server here, so this /data holds
          # nothing but a scratch tree the worker rebuilds from the database -- no reason to
          # share the scheduler's. The SQLite stack (docker.yml) does share it, because there
          # the database IS a file under /data.
          - bw-worker-storage:/data
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb"
        networks:
          - bw-universe
          - bw-db

      bw-jobs-broker:
        image: valkey/valkey:8-alpine
        # noeviction on purpose: a broker that evicts under memory pressure drops queued
        # jobs on the floor, and nothing upstream would notice.
        # appendonly on purpose: a broker restart must not vaporise queued jobs.
        # AOF, not RDB ("--save" stays empty) — a 60s RDB loss window on a job queue
        # means silently dropped work, which is what the at-least-once acks exist to stop.
        command:
          [
            "valkey-server",
            "--save",
            "",
            "--appendonly",
            "yes",
            "--maxmemory",
            "256mb",
            "--maxmemory-policy",
            "noeviction",
          ]
        volumes:
          - bw-jobs-broker-data:/data
        healthcheck:
          test: ["CMD", "valkey-cli", "ping"]
          interval: 5s
          timeout: 3s
          retries: 10
          start_period: 5s
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
          ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"
          DISABLE_DEFAULT_SERVER: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Change it to a hard-to-guess URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.7.0-beta
        environment:
          <<: *service-env
          ADMIN_USERNAME: "admin"
          ADMIN_PASSWORD: "Str0ng&P@ss!" # Remember to set a stronger password for the admin user
          # TOTP_ENCRYPTION_KEYS: "changeme" # Optional: generated in the bw-ui-data volume when unset; a key must be 43 characters
          UI_FORWARDED_ALLOW_IPS: "10.20.30.0/24"
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - bw-ui-data:/data # This is used to persist the UI secrets (Flask secret, TOTP encryption keys, Biscuit keys)
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

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-instance-data:
      bw-worker-storage:
      bw-jobs-broker-data:
      bw-data:
      bw-storage:
      bw-logs:
      bw-ui-data:

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

    Ajoutez `bunkerweb-autoconf` et appliquez des labels sur le conteneur UI au lieu d’un `BUNKERWEB_INSTANCES` explicite. Le scheduler reverse-proxie toujours l’UI via le template `ui` et un `REVERSE_PROXY_URL` secret.

=== "Linux"

    Le paquet installe un service systemd `bunkerweb-ui`. Il est activé automatiquement via l’easy-install (l’assistant démarre aussi par défaut). Pour ajuster ou reconfigurer, éditez `/etc/bunkerweb/ui.env`, puis :

    ```bash
    sudo systemctl enable --now bunkerweb-ui
    sudo systemctl restart bunkerweb-ui  # après modifications
    ```

    Placez-le derrière BunkerWeb (template `ui`, `REVERSE_PROXY_URL=/changeme`, upstream `http://127.0.0.1:7000`). Montez `/var/lib/bunkerweb` et `/var/log/bunkerweb` pour persister secrets et journaux.

### Spécificités Linux vs Docker

- Liens par défaut : images Docker sur `0.0.0.0:7000` ; paquets Linux sur `127.0.0.1:7000`. Changez via `UI_LISTEN_ADDR` / `UI_LISTEN_PORT`.
- En-têtes proxy : `UI_FORWARDED_ALLOW_IPS` vaut `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` par défaut ; `UI_PROXY_ALLOW_IPS` reprend par défaut la valeur de `FORWARDED_ALLOW_IPS`. En Linux, réglez-les sur vos IP de proxy pour un durcissement immédiat.
- Secrets et état : `/var/lib/bunkerweb` contient `FLASK_SECRET`, clés Biscuit et données TOTP. Montez-le en Docker ; sur Linux, il est géré par les scripts du paquet.
- Journaux : `/var/log/bunkerweb` doit être lisible par l’UID/GID 101 (ou l’UID mappé en rootless). Les paquets créent le chemin ; les conteneurs requièrent un volume avec les bons droits.
- Comportement de l’assistant : l’easy-install Linux démarre automatiquement l’UI et l’assistant ; en Docker, on accède à l’assistant via l’URL reverse-proxifiée sauf si vous pré-semez les variables d’environnement.

## Authentification et sessions

- Compte admin : créé via l’assistant ou via `ADMIN_USERNAME` / `ADMIN_PASSWORD`. Mot de passe requis : minuscule, majuscule, chiffre, caractère spécial. `OVERRIDE_ADMIN_CREDS=yes` force le réensemencement même si un compte existe.
- Limite de longueur du mot de passe : bcrypt n'utilise que les **72 premiers octets** d'un secret ; les mots de passe sont donc limités à 72 octets partout où ils sont définis (assistant de configuration, page de profil, `ADMIN_PASSWORD` / `API_PASSWORD`). Une valeur plus longue est rejetée avec une erreur ou un journal explicite au lieu d'être tronquée silencieusement. Notez que les caractères non ASCII (accents, emoji) consomment plusieurs octets chacun ; une phrase secrète de "72 caractères" composée de tels caractères peut donc dépasser la limite. Les valeurs bcrypt pré-hachées sont exemptées (le hash encode déjà cette limite).
- Rôles : `admin`, `writer` et `reader` sont créés automatiquement ; les comptes sont stockés en base.
- Secrets : `FLASK_SECRET` est enregistré dans `/var/lib/bunkerweb/.flask_secret` ; les clés Biscuit sont à côté et peuvent être fournies via `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY`.
- 2FA : activez le TOTP avec `TOTP_ENCRYPTION_KEYS` (séparées par des espaces ou map JSON). Générer une clé :

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Les codes de récupération sont affichés une seule fois dans l’UI ; perdre les clés de chiffrement supprime les secrets TOTP stockés.
- **Passkeys (WebAuthn / FIDO2)** : lorsque `UI_WEBAUTHN_RP_ID` est résolu, l'onglet **Sécurité** du profil affiche une carte **Passkeys**. Une passkey permet de se connecter sans nom d'utilisateur ni mot de passe, avec vérification locale par l'authentificateur et sans TOTP supplémentaire. Vous pouvez en enregistrer plusieurs, chacune nommée avec sa date de création et de dernière utilisation. Une ancienne clé FIDO2 non découvrable ne peut pas ouvrir seule une session, mais remplace le TOTP après le mot de passe.

    La passkey est un mode de connexion alternatif : son enregistrement n'ajoute pas d'étape après le mot de passe. Sans codes de récupération, exiger systématiquement un appareil perdu bloquerait le compte. Mot de passe et TOTP continuent de fonctionner ; utilisez TOTP et ses codes pour imposer un second facteur.

- Sessions : durée d’inactivité par défaut 12 h (`SESSION_LIFETIME_HOURS`), rafraîchie à chaque requête. Un plafond absolu est imposé par `SESSION_ABSOLUTE_HOURS` (par défaut `168` = 7 jours) — au-delà, les utilisateurs sont déconnectés quelle que soit leur activité. Rotation optionnelle de l’identifiant de session (`SESSION_ROLLING_HOURS`, par défaut `0` = désactivée) régénère le SID à cet intervalle. Sessions liées à l’IP et au User-Agent ; `CHECK_PRIVATE_IP=no` relâche le contrôle d’IP pour les plages privées uniquement. `ALWAYS_REMEMBER=yes` force les cookies persistants.
- Pensez à régler `PROXY_NUMBERS` si plusieurs proxies ajoutent des `X-Forwarded-*`.

!!! tip "Mot de passe administrateur pré-haché"
    `ADMIN_PASSWORD` accepte un **hash bcrypt** (`$2a$`/`$2b$`/`$2y$`) et le stocke tel quel : le texte en clair ne reste pas dans vos fichiers d’environnement ni secrets. La politique de robustesse est ignorée (vous êtes responsable du mot de passe source), mais un facteur de coût inférieur à `10` est **rejeté** ; `10`–`11` émet un avertissement (`12`+ recommandé). Uniquement en création par environnement et `OVERRIDE_ADMIN_CREDS` ; l’assistant et le profil exigent toujours du texte en clair.

    Générer un hash :

    ```bash
    python3 -c "import bcrypt; print(bcrypt.hashpw(b'Str0ng&P@ss!', bcrypt.gensalt(rounds=13)).decode())"
    ```

!!! warning "Un hash incorrect vous verrouille"
    N’utilisez un hash que si vous connaissez son texte en clair. Un hash valide mais incorrect à la première création est irréversible et un redémarrage ne le corrige pas. Récupérez avec un `ADMIN_PASSWORD` différent et `OVERRIDE_ADMIN_CREDS=yes`.

!!! warning "La 2FA disparaît après une recréation du conteneur"
    Les secrets TOTP sont stockés chiffrés en base, mais les clés qui les déchiffrent vivent **sur disque**, pas en base. À chaque démarrage l'interface prend la première source disponible : `/var/lib/bunkerweb/.totp_encryption_keys.json`, puis l'ancien `.totp_secrets.json`, puis `TOTP_ENCRYPTION_KEYS` (alias `TOTP_SECRETS`). Si aucune n'est exploitable, elle génère un nouveau jeu aléatoire, les secrets stockés ne peuvent plus être déchiffrés, l'enrôlement de l'administrateur est supprimé de la base et chaque utilisateur doit se réenrôler.

    Redémarrer un conteneur est sans effet. Ce qui perd les clés, c'est de perdre le système de fichiers du conteneur : `docker compose down` puis `up`, une recréation après un changement d'image ou d'environnement, `docker rm`, ou un nouveau pod. Monter un volume persistant sur `/data` dans le conteneur `bw-ui` suffit, et tous les exemples de cette page le font — `/var/lib/bunkerweb` est un lien symbolique vers `/data/lib` dans l'image — ce qui rend `TOTP_ENCRYPTION_KEYS` facultative.

    Ne définissez la variable vous-même que si ce volume ne peut pas être persisté, ou pour maîtriser la rotation. Dans ce cas, attention à la longueur : un espace réservé comme `changeme` n'est **pas** une clé valide — une clé fait 43 caractères, telle que produite par `generate_secret()` de `passlib`. Une valeur invalide est rejetée et remplacée par une clé aléatoire et, contrairement à une variable non définie, elle empêche aussi la réinitialisation de l'enrôlement administrateur : la 2FA reste donc inutilisable jusqu'à suppression manuelle. La rotation est possible via une map JSON : gardez les anciennes clés à côté de la nouvelle et les enrôlements existants restent valides.

## Sources de configuration et priorité

1. Variables d’environnement (y compris `environment:` Docker/Compose)
2. Secrets dans `/run/secrets/<VAR>` (Docker)
3. Fichier env `/etc/bunkerweb/ui.env` (paquets Linux)
4. Valeurs par défaut intégrées

## Référence de configuration

### Runtime et fuseau

| Paramètre | Description                                       | Valeurs acceptées                  | Défaut                                |
| --------- | ------------------------------------------------- | ---------------------------------- | ------------------------------------- |
| `TZ`      | Fuseau pour les journaux UI et actions planifiées | Nom TZ (ex. `UTC`, `Europe/Paris`) | non défini (UTC conteneur en général) |

### Écoute et TLS

| Paramètre                           | Description                                  | Valeurs acceptées                    | Défaut                                                |
| ----------------------------------- | -------------------------------------------- | ------------------------------------ | ----------------------------------------------------- |
| `UI_LISTEN_ADDR`                    | Adresse d’écoute de l’UI                     | IP ou hostname                       | `0.0.0.0` (Docker) / `127.0.0.1` (paquet)             |
| `UI_LISTEN_PORT`                    | Port d’écoute de l’UI                        | Entier                               | `7000`                                                |
| `LISTEN_ADDR`, `LISTEN_PORT`        | Substituts si les variables UI manquent      | IP/hostname, entier                  | `0.0.0.0`, `7000`                                     |
| `UI_SSL_ENABLED`                    | Activer le TLS dans le conteneur UI          | `yes` ou `no`                        | `no`                                                  |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | Chemins cert/clé PEM si TLS activé           | Chemins de fichier                   | non définis                                           |
| `UI_SSL_CA_CERTS`                   | CA/chaîne optionnelle                        | Chemin de fichier                    | non défini                                            |
| `UI_FORWARDED_ALLOW_IPS`            | Proxies de confiance pour `X-Forwarded-*`    | IP/CIDR séparés par espaces/virgules | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `UI_PROXY_ALLOW_IPS`                | Proxies de confiance pour le protocole PROXY | IP/CIDR séparés par espaces/virgules | `FORWARDED_ALLOW_IPS`                                 |

### Auth, sessions et cookies

| Paramètre                                   | Description                                                                                                              | Valeurs acceptées         | Défaut                    |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------- | ------------------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | Initialiser le compte admin (politique de mot de passe ; `ADMIN_PASSWORD` accepte aussi un hash bcrypt, stocké tel quel) | Chaînes / hash bcrypt     | non définis               |
| `OVERRIDE_ADMIN_CREDS`                      | Forcer la mise à jour des identifiants admin depuis l’env                                                                | `yes` ou `no`             | `no`                      |
| `FLASK_SECRET`                              | Secret de signature de session (persisté dans `/var/lib/bunkerweb/.flask_secret`)                                        | Chaîne hex/base64/opacité | généré automatiquement    |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | Clés de chiffrement TOTP (espaces ou map JSON)                                                                           | Chaînes / JSON            | générées si absent        |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Clés Biscuit (hex) pour générer des tokens UI                                                                            | Chaînes hex               | auto-générées et stockées |
| `SESSION_LIFETIME_HOURS`                    | Durée d’inactivité de session (TTL glissante, rafraîchie à chaque requête)                                               | Nombre (heures)           | `12`                      |
| `SESSION_ABSOLUTE_HOURS`                    | Plafond absolu de session indépendant de l’activité                                                                      | Nombre (heures)           | `168`                     |
| `SESSION_ROLLING_HOURS`                     | Intervalle de rotation du SID (`0` désactive la rotation)                                                                | Nombre (heures)           | `0`                       |
| `ALWAYS_REMEMBER`                           | Toujours activer le cookie “remember me”                                                                                 | `yes` ou `no`             | `no`                      |
| `CHECK_PRIVATE_IP`                          | Lier la session à l’IP (relâchement sur plages privées si `no`)                                                          | `yes` ou `no`             | `yes`                     |
| `PROXY_NUMBERS`                             | Nombre de sauts proxy à faire confiance pour `X-Forwarded-*`                                                             | Entier                    | `1`                       |
| `UI_WEBAUTHN_RP_ID` | Identifiant WebAuthn de partie de confiance : domaine nu, sans protocole ni port. À défaut, unique entrée non générique de `UI_ALLOWED_HOSTS` | Nom de domaine | déduit, sinon désactivé |
| `UI_WEBAUTHN_ORIGINS` | Origines exactes autorisées lors de l'authentification | URL séparées par espaces ou virgules | `https://<RP ID>` |

!!! warning "Le RP ID définit le périmètre de confiance"
    Les identifiants WebAuthn sont liés cryptographiquement au RP ID. Il n'est jamais déduit de l'en-tête `Host`, contrôlable par le client. La résolution suit cet ordre :

    1. `UI_WEBAUTHN_RP_ID` explicite ;
    2. l'unique entrée non générique de `UI_ALLOWED_HOSTS`, sans son éventuel `:port` ;
    3. sinon, les passkeys restent désactivées et la raison est journalisée au démarrage.

    **Changer le domaine de l'UI invalide toutes les passkeys enregistrées.** Les utilisateurs doivent en créer sur le nouveau domaine : le RP ID inscrit par l'authentificateur ne se migre pas. Conservez TOTP ou un mot de passe avant tout changement de domaine. Un contexte sécurisé HTTPS est requis, sauf pour `localhost` (donc `http://localhost:7000` fonctionne en développement).

### Gestionnaire de certificats

| Paramètre | Description | Valeurs acceptées | Défaut |
| --------- | ----------- | ----------------- | ------ |
| `CERTIFICATE_ENCRYPTION_KEYS` | Trousseau AES-256-GCM pour les clés privées stockées | Objet JSON d'identifiants de clés vers des clés de 32 octets en base64 | non défini |
| `CERTIFICATE_ENCRYPTION_ACTIVE_KEY` | Identifiant de clé utilisé pour les nouvelles clés privées importées ou générées | Clé présente dans le trousseau | non défini |

Ces deux variables sont requises pour créer/importer des certificats et renouveler les certificats auto-signés. Conservez les anciennes clés tant que des certificats les utilisent et fournissez le même trousseau à tous les processus API/Worker concernés. Les endpoints de téléchargement ne donnent jamais les clés privées.

`/certificates` gère l'inventaire partagé (liste, métadonnées, affectations, suppression des certificats non gérés, téléchargements publics). Les plugins gèrent le cycle de vie : `/selfsigned/certificates` crée et renouvelle, `/customcert/certificates/upload` importe le PEM, `/letsencrypt/certificates` planifie ACME et inspecte les orphelins en lecture seule. L'UI passe toujours par l'API.

### Journalisation

| Paramètre                       | Description                                                   | Valeurs acceptées                               | Défaut                                         |
| ------------------------------- | ------------------------------------------------------------- | ----------------------------------------------- | ---------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Niveau de log de base / override                              | `debug`, `info`, `warning`, `error`, `critical` | `info`                                         |
| `LOG_TYPES`                     | Destinations                                                  | `stderr`/`file`/`syslog` séparés par espaces    | `stderr`                                       |
| `LOG_FILE_PATH`                 | Chemin pour les logs fichier (`file` ou `CAPTURE_OUTPUT=yes`) | Chemin de fichier                               | `/var/log/bunkerweb/ui.log` si fichier/capture |
| `CAPTURE_OUTPUT`                | Envoyer stdout/stderr Gunicorn vers les handlers              | `yes` ou `no`                                   | `no`                                           |
| `LOG_SYSLOG_ADDRESS`            | Cible syslog (`udp://host:514`, `tcp://host:514`, socket)     | Host:port / URL / socket                        | non défini                                     |
| `LOG_SYSLOG_TAG`                | Tag/ident syslog                                              | Chaîne                                          | `bw-ui`                                        |

### Divers runtime

| Paramètre                       | Description                                                          | Valeurs acceptées                           | Défaut                                                |
| ------------------------------- | -------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------- |
| `MAX_WORKERS`, `MAX_THREADS`    | Workers/threads Gunicorn                                             | Entier                                      | `cpu_count()-1` (min 1), `workers*2`                  |
| `MAX_REQUESTS`                  | Requêtes avant recyclage du worker Gunicorn (évite la fuite mémoire) | Entier                                      | `1000`                                                |
| `ENABLE_HEALTHCHECK`            | Exposer `GET /healthcheck`                                           | `yes` ou `no`                               | `no`                                                  |
| `FORWARDED_ALLOW_IPS`           | Alias pour la liste des proxies                                      | IP/CIDR                                     | `127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` |
| `PROXY_ALLOW_IPS`               | Alias pour la liste PROXY                                            | IP/CIDR                                     | `FORWARDED_ALLOW_IPS`                                 |
| `DISABLE_CONFIGURATION_TESTING` | Sauter les reloads de test lors des push config                      | `yes` ou `no`                               | `no`                                                  |
| `IGNORE_REGEX_CHECK`            | Ignorer la validation regex des paramètres                           | `yes` ou `no`                               | `no`                                                  |
| `MAX_CONTENT_LENGTH`            | Taille maximale d'upload (Flask `MAX_CONTENT_LENGTH`)                | Taille avec unité (`50M`, `1G`, `52428800`) | `50MB`                                                |

## Accès aux journaux

L’UI lit les journaux NGINX/services depuis `/var/log/bunkerweb`. Alimentez ce répertoire via un démon syslog ou un volume :

- L’UID/GID du conteneur est 101. Sur l’hôte, rendez les fichiers lisibles : `chown root:101 bw-logs && chmod 770 bw-logs` (adaptez en rootless).
- Envoyez les access/error logs BunkerWeb via `ACCESS_LOG` / `ERROR_LOG` vers le sidecar syslog ; envoyez les logs des composants avec `LOG_TYPES=syslog`.

Exemple `syslog-ng.conf` pour écrire des journaux par programme :

```conf
@version: 4.10

# Source configuration to receive logs from Docker containers
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Template to format log messages
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Destination configuration to write logs to dynamically named files
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

# Log path to direct logs to dynamically named files
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Capacités

- Tableau de bord pour requêtes, bannissements, cache et tâches ; redémarrage/rechargement d’instances.
- Création/mise à jour/suppression de services et paramètres globaux avec validation sur les schémas de plugins.
- Téléversement et gestion de configs personnalisées (NGINX/ModSecurity) et de plugins (externes ou PRO).
- Consultation des journaux, recherche de rapports, inspection des artefacts de cache.
- Gestion des utilisateurs UI, rôles, sessions et TOTP avec codes de récupération, ainsi que des passkeys (WebAuthn / FIDO2) pour la connexion sans mot de passe.
- Mise à niveau vers BunkerWeb PRO et visualisation du statut de licence via la page dédiée.

### Le serveur par défaut {#the-default-server-entry}

Avec `MULTISITE=yes`, la liste des services affiche une entrée épinglée **Serveur par défaut**, accompagnée d'une explication. Cette entrée n'existe pas en mode mono-site (`MULTISITE=no`). Ce service réservé `default-server` répond aux requêtes ne correspondant à aucun service configuré : nom d'hôte inconnu, IP directe ou en-tête `Host` non desservi.

Ouvrez-le pour configurer son certificat, TLS, ses en-têtes de réponse, pages d'erreur et liste blanche. Reverse proxy, gRPC, redirections, sessions, antibot, mTLS, CORS et authentification HTTP Basic n'y sont pas proposés : il n'a ni nom d'hôte à router ni identité de service associée. Il ne peut pas être supprimé, cloné ou converti et ne compte jamais dans le quota PRO.

### Mode du service {#service-mode}

Un service est soit `standard`, soit `redirect_only`. Un service redirect-only ne fait rien d'autre que rediriger — il ne porte ni reverse proxy, ni service de fichiers, ni configuration NGINX personnalisée, ni modèle, ni upstream ou workflow attaché — et il ne comptera plus dans le quota PRO une fois la facturation redirect-only activée. Partout ailleurs, c'est un service ordinaire : il garde sa propre page, ses métriques et sa place dans la liste des services.

La déclaration est explicite. Elle n'est jamais déduite des paramètres de redirection, et se fait depuis la carte **Mode du service** sur la page de paramètres du service, pas depuis le formulaire de paramètres. Si le service porte encore quelque chose qu'un service redirect-only ne peut pas avoir — ou s'il lui manque quelque chose qu'il doit avoir, comme une cible `REDIRECT_TO`, ou `SERVE_FILES` explicitement à `no` puisqu'il vaut `yes` par défaut —, la carte liste chaque raison et l'action reste désactivée tant qu'elles ne sont pas levées. La carte n'apparaît pas sur un service en brouillon — un brouillon ne compte jamais, dans un sens ou l'autre — même si la conversion via l'API fonctionne toujours pour lui.

La liste des services signale chaque service qui serait éligible, pour trouver l'économie sans ouvrir chaque page.

### Enrôlement des instances {#instance-enrollment}

Une instance affichée sur la page **Instances** peut recevoir son propre identifiant de plan de contrôle au lieu de partager l'`API_TOKEN` global. Le bouton clé de la ligne (ou le menu d'historique) émet un code d'enrôlement à usage unique, affiché une seule fois, que l'instance échange au démarrage via `INSTANCE_ENROLLMENT_CODE` ; elle ne répond ensuite plus qu'à l'identifiant émis pour elle par le plan de contrôle. Le mécanisme complet, y compris les points d'API et la distinction `manual` / `autoconf`, se trouve dans la [référence API](api.md#enrollment-an-alternative-to-setting-credential-by-hand).

L'enrôlement fonctionne pour une ligne créée depuis l'UI ou l'API, et pour une ligne déclarée via l'environnement (`BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*`) — la forme par défaut d'un déploiement Docker ou Linux. Il ne fonctionne **pas** pour une ligne découverte par autoconf : cette ligne est réobtenue depuis un orchestrateur actif à chaque réconciliation, ce qui replacerait le token de l'environnement au-dessus d'un identifiant émis ; les boutons d'enrôlement, de rotation et de révocation y sont donc désactivés.

Une instance qui déclare son propre `BUNKERWEB_INSTANCE_API_TOKEN_<n>` affiche la même puce **Enrôlée** qu'une instance enrôlée via un code, car la page lit « possède un identifiant par instance » et un token déclaré est stocké comme tel. Les boutons n'y sont pas dangereux, mais quasiment sans effet : le prochain enregistrement de la configuration du scheduler réobtient le token déclaré, ce qui écrase un identifiant émis et lève une révocation dans tous les cas. Choisissez l'un ou l'autre pour une instance donnée — l'enrôler, ou lui déclarer un token, pas les deux.

!!! warning "Donnez à l'instance un volume persistant"
    L'identifiant vit sous `/var/lib/bunkerweb`, que l'image Docker lie symboliquement à `/data`. Un conteneur recréé **sans** volume pour `/data` perd l'identifiant et le marqueur qui détecterait sinon la perte : il revient comme une instance neuve, non enrôlée, alors que le plan de contrôle la croit toujours enrôlée, et chaque envoi de configuration vers elle est refusé sans rien expliquer. Avec un volume monté, l'instance détecte elle-même la perte et **refuse de démarrer**, en nommant la cause et le correctif. Les paquets Linux persistent déjà `/var/lib/bunkerweb`, ce n'est donc une mise en garde que pour les conteneurs — voir les fichiers compose du [guide de démarrage rapide](quickstart-guide.md) et sous `misc/integrations/`, qui en montent tous un.

!!! note "Une ligne `manual` ne peut toujours pas être supprimée d'ici"
    Enrôler, faire pivoter ou révoquer une ligne déclarée dans l'environnement fonctionne depuis cette page, mais pas la supprimer — le prochain enregistrement de la configuration la recrée à partir de `BUNKERWEB_INSTANCES` / `BUNKERWEB_INSTANCE_*`. Retirez plutôt le nom d'hôte de l'environnement, ce qui supprime aussi son enrôlement.

### Groupes de ressources {#resource-groups}

Ouvrez **Configurer → Groupes de ressources** pour gérer des listes réutilisables d'IP/CIDR, pays, ASN, suffixes DNS inversés, motifs de User-Agent ou d'URI. Chaque entrée possède un type et un commentaire facultatif. Vous pouvez cloner un groupe, l'exporter en JSON et inspecter ses références.

Utilisez son `@alias` dans les paramètres compatibles, par exemple `@office 203.0.113.5`. Whitelist, Blacklist, Greylist, Real IP, DNSBL et Antibot acceptent ces références. BunkerWeb conserve le jeton en base et développe les entrées du type attendu pendant la génération : modifier le groupe met à jour ses consommateurs au prochain envoi. Les workflows sélectionnent les groupes dans l'éditeur et conservent un identifiant stable.

L'alias comporte de 1 à 64 lettres, chiffres, tirets bas ou tirets. `@EU`, `@G7` et `@SCHENGEN` sont réservés. Une référence est refusée si le groupe est absent ou n'a aucune entrée du type requis. Un groupe utilisé par un paramètre ou workflow ne peut pas être supprimé.

### Upstreams

Ouvrez **Configurer → Upstreams** pour gérer des pools de backends HTTP, gRPC ou stream partagés entre plusieurs services. Chaque pool possède un nom, un protocole (`http`, `grpc`, `stream`), une méthode (`round_robin`, `least_conn`, `ip_hash`), jusqu'à 64 serveurs (poids, nombre maximal d'échecs, délai d'échec, rôle principal/secours/indisponible), un nombre facultatif de connexions keepalive et l'option `backend_ssl`. L'attachement enregistre le chemin reverse proxy (`/` par défaut). Un pool peut être attaché à 100 services au maximum.

La page utilise `GET /upstreams`, `POST /upstreams`, `PATCH /upstreams/{id}`, `DELETE /upstreams/{id}` et `POST/DELETE /upstreams/{id}/attachments[/{service}]` pour lister, créer, modifier, supprimer, attacher ou détacher les pools.

### Modèles {#templates}

Ouvrez **Configurer → Modèles** pour consulter et gérer des modèles de service réutilisables : paramètres, étapes ordonnées et configurations personnalisées adoptés avec `USE_TEMPLATE`. La galerie indique le nombre de services utilisateurs, brouillons compris, et les fonctionnalités déduites. L'éditeur utilise le catalogue multisite des services et permet de partir de zéro ou de cloner un modèle.

Le **Catalogue de modèles** communautaire propose des modèles préparés. Leur installation exige `admin`, pas seulement `write` : ils peuvent contenir des configurations personnalisées NGINX enregistrées sans validation du contenu. Les paramètres de chaque modèle installé ou enregistré sont toutefois vérifiés avec le catalogue courant ; un paramètre inconnu entraîne un refus.

Depuis 1.7, `USE_TEMPLATE` accepte plusieurs modèles par service, appliqués dans l'ordre, le dernier l'emportant en cas de conflit.

### Gestion du cache Web {#web-cache-management}

La page **Cache Web** gère le cache de réponses NGINX de Reverse Proxy : état de remontée de chaque instance, nombre d'entrées et taille sur disque, services dont `USE_PROXY_CACHE` est effectivement activé, compteurs `HIT`, `MISS`, `BYPASS` et `STALE` lorsque Metrics les fournit.

Vous pouvez purger une URL HTTP(S) absolue ou le cache complet. La purge d'URL reconstruit exactement `PROXY_CACHE_KEY` : fournissez le modèle personnalisé du service s'il diffère de la valeur par défaut. L'API accepte au maximum 100 URL par requête.

!!! warning "Une purge complète concerne tous les services mis en cache"
    `scope: "all"` vide la zone partagée `proxycache` sur toutes les instances joignables, sans cibler un service ni recharger NGINX. Une instance injoignable est ignorée, sans mise en file différée : vérifiez les résultats par instance avant de considérer la purge de flotte comme complète.

### Tableau de bord des rapports {#reports-dashboard}

La page **Rapports** couvre les requêtes HTTP et sessions STREAM bloquées. **Vue d'ensemble** représente l'activité, **Motifs d'attaque** regroupe les règles ModSecurity et familles d'attaques, **Principaux contrevenants** classe IP, pays et ASN. Le **Journal d'événements** propose recherche côté serveur, filtres, colonnes triables, détails d'incident et export CSV ou Excel. Les administrateurs peuvent bannir un contrevenant, les lignes sélectionnées ou toutes les IP du résultat filtré. Le journal inclut les requêtes HTTP bloquées, les détections avec `SECURITY_MODE=detect` et les sessions STREAM bloquées. Il conserve aussi trois actions de sécurité dont le code n'est pas un refus : les défis de détection de bots CrowdSec 1.8 servis en 200 par BunkerWeb, les redirections `workflows` en 3xx et les défis antibot.

Antibot défie chaque visiteur non identifié, pas seulement les attaquants. Un service très fréquenté ajoute donc un rapport par défi. Le tampon `METRICS_MAX_BLOCKED_REQUESTS` (par worker, `1k` par défaut ; `METRICS_MAX_BLOCKED_REQUESTS_REDIS` avec Redis) évince les entrées les plus anciennes quand il est plein : des défis peuvent remplacer de véritables blocages. Augmentez d'abord ce tampon, puis dimensionnez `METRICS_RETENTION_DAYS` et `METRICS_RETENTION_MAX_ROWS`. Les vues **Vue d'ensemble**, **Principaux contrevenants** et carte des menaces comptent seulement blocages et détections, jamais les défis servis.

La colonne **Raison** affiche une phrase quand le plugin fournit son verdict : défi de détection CrowdSec AppSec, blocage CrowdSec LAPI avec scénario, défi Antibot captcha ou redirection d'un workflow de sécurité. Les champs bruts restent dans les détails. Le tri et le filtre continuent d'utiliser la valeur sous-jacente pour préserver les filtres enregistrés.

`METRICS_PERSIST_TO_DB=yes` est la valeur par défaut et fournit un historique durable centralisé, borné par `METRICS_RETENTION_DAYS` et `METRICS_RETENTION_MAX_ROWS`. Sans persistance, les rapports restent en mémoire ou dans Redis et peuvent expirer plus vite. Si l'API Metrics est indisponible, le journal revient à la lecture des instances/Redis ; les onglets analytiques affichent un état vide jusqu'au retour des métriques.

### Threatmap

La page **Threatmap** affiche les rapports persistés sur une carte mondiale adaptée à un écran mural : arcs du pays d'origine des requêtes bloquées vers un centre symbolique, volume de blocages par pays, principaux contrevenants et événements récents. Ce centre illustre l'origine, pas un impact géolocalisé : aucune coordonnée n'est collectée et un nom de service n'a pas de position.

Elle exige `METRICS_PERSIST_TO_DB=yes` et explique quand la persistance est désactivée. Le mode plein écran masque l'interface de l'application. Les données proviennent de `GET /threatmap/data`, avec environ une à deux minutes de retard liées au job de collecte des rapports.

### Durées {#timings}

La page **Durées** présente `METRICS_COLLECT_TIMINGS` : temps consommé par plugin et phase sur la flotte, trié par coût total. Le pourcentage est rapporté à la durée totale de requête enregistrée systématiquement par la phase `request` de Metrics. Les phases qui ne s'exécutent pas une fois par requête (`init`, `init_worker(s)`, `timer`, API interne) n'ont pas de pourcentage. En l'absence de données, la page distingue une collecte désactivée (`METRICS_COLLECT_TIMINGS`) d'une API injoignable.

### Exécutions de jobs différées

La page **Jobs** peut afficher un troisième résultat d'exécution en plus des puces habituelles vert Succès et rouge Échec : **Différé — en attente qu'une instance démarre**, dans la couleur d'avertissement, avec une icône d'horloge. Cela apparaît quand un job — le cas courant est `push-configs` constatant qu'aucune instance enregistrée n'est joignable — s'arrête délibérément sans rien appliquer, plutôt que d'échouer : rien n'a été envoyé, mais rien n'est cassé non plus, et le changement en attente est retenté automatiquement dès qu'une instance répond à nouveau. Survolez la puce pour connaître la raison précise ; le libellé court est aussi ce sur quoi le filtre de statut de la page se base.

Le premier différé suivant une exécution réussie déclenche aussi une bannière d'avertissement masquable en haut de chaque page, distincte de la bannière existante (et plus grave) « push échoué », afin qu'une flotte simplement en attente qu'une instance redémarre ne paraisse pas cassée.

## Parcours guidé

Une nouvelle installation ouvre un tiroir **Premiers pas** depuis l'icône fusée dans la barre supérieure. Il liste ce qu'il reste à faire, coche chaque élément de lui-même, et disparaît une fois tout terminé — ou dès que vous le fermez.

Rien n'est enregistré sur ce que vous avez *vu* : chaque élément est recalculé à partir de la configuration en cours à chaque ouverture du tiroir. Enregistrez un service depuis l'API, ou depuis un label Docker, et l'élément correspondant est déjà coché la prochaine fois que vous regardez. À l'inverse, supprimer votre dernier service fait réapparaître son élément.

Ce qui vous est montré dépend de votre rôle :

| Rôle | Ce que propose le parcours |
| --- | --- |
| Admin | Installation, premier service, HTTPS, première requête bloquée, MFA, plus les éléments optionnels workflow et PRO |
| Writer | Le même, sans l'élément PRO réservé aux admins |
| Reader | Une orientation plutôt que des tâches : où se trouvent le dashboard, les reports, les bans et les logs, et comment les lire |

Les Reader reçoivent une brève indication sur chacune de ces quatre pages lors de leur première visite ; l'accepter avec **Compris** coche l'élément correspondant. Tout élément pointant vers un endroit de l'interface porte aussi un bouton **Montre-moi** qui le met en évidence dans la navigation.

Les éléments optionnels — un workflow de sécurité, PRO — ne retiennent jamais le compteur : une installation Community atteint « tout est fait » sans eux.

!!! info "Fermé par accident ?"
    **Profil → Parcours guidé → Redémarrer le parcours** ramène le tiroir. Sur une base de données en lecture seule, le bouton est désactivé, puisque rien ne pourrait être enregistré.

## Nouveautés après une mise à niveau

Après une mise à niveau, la première page ouverte affiche un récapitulatif de ce qui a changé entre la version précédemment utilisée et celle en cours d'exécution. Il est construit à partir du `CHANGELOG.md` livré dans l'image — rien n'est récupéré depuis internet, donc une installation en air-gap affiche le même récapitulatif qu'une installation connectée.

Le récapitulatif est propre à chaque utilisateur et à chaque version : le fermer marque cette version comme vue uniquement pour votre compte. Tout reste disponible sur **/whats-new**, accessible en cliquant sur le numéro de version en bas de la barre latérale — fermer le récapitulatif ne fait rien perdre.

Deux comportements à connaître :

- **Un compte qui n'a jamais vu de récapitulatif est marqué à jour silencieusement.** Activer cette fonctionnalité n'accueille pas les utilisateurs existants avec tout l'historique ; vous commencez à voir des récapitulatifs à partir de votre prochaine mise à niveau.
- **Les rétrogradations n'affichent rien.** Exécuter une build plus ancienne que celle enregistrée n'affiche aucun récapitulatif, plutôt que d'annoncer des versions que le binaire en cours d'exécution ne contient pas.

Sur une base de données en lecture seule, rien ne peut être enregistré, donc le récapitulatif réapparaît à la prochaine connexion.

## Mise à niveau vers PRO {#upgrade-to-pro}

!!! tip "Essai gratuit BunkerWeb PRO"
    Essayez gratuitement BunkerWeb PRO pendant 30 jours depuis le [Panel BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=french&utm_campaign=self&utm_source=doc).

Collez votre clé PRO dans la page **PRO** de l’UI (ou pré-renseignez `PRO_LICENSE_KEY` pour l’assistant). Les mises à niveau sont téléchargées en arrière-plan par le scheduler ; vérifiez l’UI pour l’expiration et les limites de services une fois appliquées.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>Informations de licence PRO</figcaption>
</figure>

## Traductions (i18n)

L’interface Web est disponible en plusieurs langues grâce aux contributions de la communauté. Les traductions sont stockées dans des fichiers JSON par langue (par exemple `en.json`, `fr.json`, …). Pour chaque langue, l’origine de la traduction est clairement documentée (manuelle ou générée par IA), ainsi que son statut de relecture.

### Langues disponibles et contributeurs

| Langue                 | Locale | Créée par                     | Relue par                |
| ---------------------- | ------ | ----------------------------- | ------------------------ |
| Arabe                  | `ar`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Bengali                | `bn`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Breton                 | `br`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Allemand               | `de`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Anglais                | `en`   | Manuel (@TheophileDiot)       | Manuel (@TheophileDiot)  |
| Espagnol               | `es`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Français               | `fr`   | Manuel (@TheophileDiot)       | Manuel (@TheophileDiot)  |
| Hindi                  | `hi`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Italien                | `it`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Coréen                 | `ko`   | Manuel (@rayshoo)             | Manuel (@rayshoo)        |
| Polonais               | `pl`   | Manuel (@tomkolp) via Weblate | Manuel (@tomkolp)        |
| Portugais              | `pt`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Russe                  | `ru`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Turc                   | `tr`   | Manuel (@wiseweb-works)       | Manuel (@wiseweb-works)  |
| Chinois (Traditionnel) | `tw`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Ourdou                 | `ur`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |
| Chinois (Simplifié)    | `zh`   | IA (Google:Gemini-2.5-pro)    | IA (Google:Gemini-3-pro) |

> 💡 Certaines traductions peuvent être partielles. Une relecture manuelle est fortement recommandée, en particulier pour les éléments critiques de l’interface.

### Comment contribuer

Les contributions aux traductions suivent le workflow de contribution standard de BunkerWeb :

1. **Créer ou mettre à jour le fichier de traduction**
   - Copier `src/ui/app/static/locales/en.json` et le renommer avec le code de la langue cible (par exemple `de.json`).
   - Traduire **uniquement les valeurs** ; les clés ne doivent pas être modifiées.

2. **Enregistrer la langue**
   - Ajouter ou mettre à jour l’entrée correspondante dans `src/ui/app/lang_config.py` (code de langue, nom affiché, drapeau, nom anglais).
     Ce fichier constitue la source de vérité pour les langues supportées.

3. **Mettre à jour la documentation et la provenance**
   - `src/ui/app/static/locales/README.md` → ajouter la nouvelle langue dans la table de provenance (créée par / relue par).
   - `README.md` → mettre à jour la documentation générale du projet pour refléter la nouvelle langue supportée.
   - `docs/web-ui.md` → mettre à jour la documentation de l’interface Web (cette section Traductions).
   - `docs/*/web-ui.md` → mettre à jour les versions traduites de la documentation de l’interface Web avec la même section Traductions.

4. **Ouvrir une pull request**
   - Indiquer clairement si la traduction a été réalisée manuellement ou à l’aide d’un outil d’IA.
   - Pour les changements non triviaux (nouvelle langue ou mises à jour importantes), il est recommandé d’ouvrir au préalable une issue afin d’en discuter.

En contribuant aux traductions, vous aidez à rendre BunkerWeb accessible à un public international plus large.
