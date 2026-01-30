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
    - Dépendances : partage la base BunkerWeb et dialogue avec l’API pour recharger, bannir ou interroger les instances

## Checklist sécurité

- Placez l’UI derrière BunkerWeb sur un réseau interne ; choisissez un `REVERSE_PROXY_URL` difficile à deviner et limitez les IP sources.
- Définissez des `ADMIN_USERNAME` / `ADMIN_PASSWORD` solides ; activez `OVERRIDE_ADMIN_CREDS=yes` uniquement si vous voulez vraiment les réinitialiser.
- Fournissez `TOTP_ENCRYPTION_KEYS` et activez le TOTP pour les comptes admin ; gardez les codes de récupération en sécurité.
- Utilisez le TLS (terminé sur BunkerWeb ou via `UI_SSL_ENABLED=yes` avec chemins cert/clé) ; définissez `UI_FORWARDED_ALLOW_IPS` sur vos proxies de confiance.
- Persistez les secrets : montez `/var/lib/bunkerweb` pour conserver `FLASK_SECRET`, les clés Biscuit et le matériel TOTP après redémarrage.
- Gardez `CHECK_PRIVATE_IP=yes` (par défaut) pour lier les sessions à l’IP ; laissez `ALWAYS_REMEMBER=no` sauf besoin explicite de cookies longue durée.
- Assurez-vous que `/var/log/bunkerweb` est lisible par l’UID/GID 101 (ou l’UID mappé en rootless) pour que l’UI puisse lire les journaux.

## Mise en route

L’UI attend que le scheduler/l’API BunkerWeb/le redis/la base soient accessibles.

=== "Démarrage rapide (assistant)"

    Utilisez les images publiées et le layout du [guide de démarrage rapide](quickstart-guide.md#__tabbed_1_3) pour monter la stack, puis terminez la configuration dans le navigateur.

    ```bash
    docker compose -f https://raw.githubusercontent.com/bunkerity/bunkerweb/v1.6.8~rc3-rc1/misc/integrations/docker-compose.yml up -d
    ```

    Ouvrez le nom d’hôte du scheduler (par ex. `https://www.example.com/changeme`) et lancez l’assistant `/setup` pour configurer l’UI, le scheduler et l’instance.

=== "Avancé (variables pré-semées)"

    Contournez l’assistant en renseignant identifiants et réseau dès le départ ; exemple Compose avec sidecar syslog :

    ```yaml
    x-service-env: &service-env
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"
        environment:
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks: [bw-universe, bw-services]

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb"
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
          ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"
          DISABLE_DEFAULT_SERVER: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme"
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data
        restart: "unless-stopped"
        networks: [bw-universe, bw-db]

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *service-env
          ADMIN_USERNAME: "admin"
          ADMIN_PASSWORD: "Str0ng&P@ss!"
          TOTP_ENCRYPTION_KEYS: "set-me"
          UI_FORWARDED_ALLOW_IPS: "10.20.30.0/24"
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks: [bw-universe, bw-db]

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
        restart: "unless-stopped"
        networks: [bw-db]

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        volumes:
          - bw-logs:/var/log/bunkerweb
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf
        restart: "unless-stopped"
        networks: [bw-universe]

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      bw-lib:

    networks:
      bw-universe:
        ipam:
          config: [{ subnet: 10.20.30.0/24 }]
      bw-services:
      bw-db:
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
- En-têtes proxy : `UI_FORWARDED_ALLOW_IPS` vaut `*` par défaut ; en Linux, réglez-le sur vos IP de proxy pour un durcissement immédiat.
- Secrets et état : `/var/lib/bunkerweb` contient `FLASK_SECRET`, clés Biscuit et données TOTP. Montez-le en Docker ; sur Linux, il est géré par les scripts du paquet.
- Journaux : `/var/log/bunkerweb` doit être lisible par l’UID/GID 101 (ou l’UID mappé en rootless). Les paquets créent le chemin ; les conteneurs requièrent un volume avec les bons droits.
- Comportement de l’assistant : l’easy-install Linux démarre automatiquement l’UI et l’assistant ; en Docker, on accède à l’assistant via l’URL reverse-proxifiée sauf si vous pré-semez les variables d’environnement.

## Authentification et sessions

- Compte admin : créé via l’assistant ou via `ADMIN_USERNAME` / `ADMIN_PASSWORD`. Mot de passe requis : minuscule, majuscule, chiffre, caractère spécial. `OVERRIDE_ADMIN_CREDS=yes` force le réensemencement même si un compte existe.
- Rôles : `admin`, `writer` et `reader` sont créés automatiquement ; les comptes sont stockés en base.
- Secrets : `FLASK_SECRET` est enregistré dans `/var/lib/bunkerweb/.flask_secret` ; les clés Biscuit sont à côté et peuvent être fournies via `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY`.
- 2FA : activez le TOTP avec `TOTP_ENCRYPTION_KEYS` (séparées par des espaces ou map JSON). Générer une clé :

    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Les codes de récupération sont affichés une seule fois dans l’UI ; perdre les clés de chiffrement supprime les secrets TOTP stockés.
- Sessions : durée par défaut 12 h (`SESSION_LIFETIME_HOURS`). Sessions liées à l’IP et au User-Agent ; `CHECK_PRIVATE_IP=no` relâche le contrôle d’IP pour les plages privées uniquement. `ALWAYS_REMEMBER=yes` force les cookies persistants.
- Pensez à régler `PROXY_NUMBERS` si plusieurs proxies ajoutent des `X-Forwarded-*`.

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

| Paramètre                           | Description                               | Valeurs acceptées                    | Défaut                                    |
| ----------------------------------- | ----------------------------------------- | ------------------------------------ | ----------------------------------------- |
| `UI_LISTEN_ADDR`                    | Adresse d’écoute de l’UI                  | IP ou hostname                       | `0.0.0.0` (Docker) / `127.0.0.1` (paquet) |
| `UI_LISTEN_PORT`                    | Port d’écoute de l’UI                     | Entier                               | `7000`                                    |
| `LISTEN_ADDR`, `LISTEN_PORT`        | Substituts si les variables UI manquent   | IP/hostname, entier                  | `0.0.0.0`, `7000`                         |
| `UI_SSL_ENABLED`                    | Activer le TLS dans le conteneur UI       | `yes` ou `no`                        | `no`                                      |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | Chemins cert/clé PEM si TLS activé        | Chemins de fichier                   | non définis                               |
| `UI_SSL_CA_CERTS`                   | CA/chaîne optionnelle                     | Chemin de fichier                    | non défini                                |
| `UI_FORWARDED_ALLOW_IPS`            | Proxies de confiance pour `X-Forwarded-*` | IP/CIDR séparés par espaces/virgules | `*`                                       |

### Auth, sessions et cookies

| Paramètre                                   | Description                                                                       | Valeurs acceptées         | Défaut                    |
| ------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------- | ------------------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | Initialiser le compte admin (politique de mot de passe)                           | Chaînes                   | non définis               |
| `OVERRIDE_ADMIN_CREDS`                      | Forcer la mise à jour des identifiants admin depuis l’env                         | `yes` ou `no`             | `no`                      |
| `FLASK_SECRET`                              | Secret de signature de session (persisté dans `/var/lib/bunkerweb/.flask_secret`) | Chaîne hex/base64/opacité | généré automatiquement    |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | Clés de chiffrement TOTP (espaces ou map JSON)                                    | Chaînes / JSON            | générées si absent        |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Clés Biscuit (hex) pour générer des tokens UI                                     | Chaînes hex               | auto-générées et stockées |
| `SESSION_LIFETIME_HOURS`                    | Durée de session                                                                  | Nombre (heures)           | `12`                      |
| `ALWAYS_REMEMBER`                           | Toujours activer le cookie “remember me”                                          | `yes` ou `no`             | `no`                      |
| `CHECK_PRIVATE_IP`                          | Lier la session à l’IP (relâchement sur plages privées si `no`)                   | `yes` ou `no`             | `yes`                     |
| `PROXY_NUMBERS`                             | Nombre de sauts proxy à faire confiance pour `X-Forwarded-*`                      | Entier                    | `1`                       |

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

| Paramètre                       | Description                                     | Valeurs acceptées | Défaut                               |
| ------------------------------- | ----------------------------------------------- | ----------------- | ------------------------------------ |
| `MAX_WORKERS`, `MAX_THREADS`    | Workers/threads Gunicorn                        | Entier            | `cpu_count()-1` (min 1), `workers*2` |
| `ENABLE_HEALTHCHECK`            | Exposer `GET /healthcheck`                      | `yes` ou `no`     | `no`                                 |
| `FORWARDED_ALLOW_IPS`           | Alias déprécié pour la liste des proxies        | IP/CIDR           | `*`                                  |
| `DISABLE_CONFIGURATION_TESTING` | Sauter les reloads de test lors des push config | `yes` ou `no`     | `no`                                 |
| `IGNORE_REGEX_CHECK`            | Ignorer la validation regex des paramètres      | `yes` ou `no`     | `no`                                 |

## Accès aux journaux

L’UI lit les journaux NGINX/services depuis `/var/log/bunkerweb`. Alimentez ce répertoire via un démon syslog ou un volume :

- L’UID/GID du conteneur est 101. Sur l’hôte, rendez les fichiers lisibles : `chown root:101 bw-logs && chmod 770 bw-logs` (adaptez en rootless).
- Envoyez les access/error logs BunkerWeb via `ACCESS_LOG` / `ERROR_LOG` vers le sidecar syslog ; envoyez les logs des composants avec `LOG_TYPES=syslog`.

Exemple `syslog-ng.conf` pour écrire des journaux par programme :

```conf
@version: 4.10
source s_net { udp(ip("0.0.0.0")); };
template t_imp { template("$MSG\n"); template_escape(no); };
destination d_dyna_file {
  file("/var/log/bunkerweb/${PROGRAM}.log"
       template(t_imp) owner("101") group("101")
       dir_owner("root") dir_group("101")
       perm(0440) dir_perm(0770) create_dirs(yes));
};
log { source(s_net); destination(d_dyna_file); };
```

## Capacités

- Tableau de bord pour requêtes, bannissements, cache et tâches ; redémarrage/rechargement d’instances.
- Création/mise à jour/suppression de services et paramètres globaux avec validation sur les schémas de plugins.
- Téléversement et gestion de configs personnalisées (NGINX/ModSecurity) et de plugins (externes ou PRO).
- Consultation des journaux, recherche de rapports, inspection des artefacts de cache.
- Gestion des utilisateurs UI, rôles, sessions et TOTP avec codes de récupération.
- Mise à niveau vers BunkerWeb PRO et visualisation du statut de licence via la page dédiée.

## Mise à niveau vers PRO {#upgrade-to-pro}

!!! tip "Essai gratuit BunkerWeb PRO"
    Utilisez le code `freetrial` sur le [Panel BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=french&utm_campaign=self&utm_source=doc) pour un mois d’essai.

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
