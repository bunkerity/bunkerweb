Le plugin General fournit le cadre de configuration de base de BunkerWeb, vous permettant de définir les paramètres essentiels qui régissent la protection et la distribution de vos services web. Ce plugin fondamental gère des aspects clés tels que les modes de sécurité, les valeurs par défaut du serveur, le comportement de journalisation et les paramètres opérationnels critiques pour l’ensemble de l’écosystème BunkerWeb.

Comment ça marche :

1. Au démarrage de BunkerWeb, le plugin General charge et applique vos paramètres de configuration principaux.
2. Les modes de sécurité sont définis globalement ou par site, déterminant le niveau de protection appliqué.
3. Les paramètres par défaut du serveur établissent des valeurs de repli pour toute configuration multisite non spécifiée.
4. Les paramètres de journalisation contrôlent les informations enregistrées et leur format.
5. Ces paramètres constituent la base sur laquelle s’appuient tous les autres plugins et fonctionnalités de BunkerWeb.

### Mode multisite {#multisite-mode}

Lorsque `MULTISITE` vaut `yes`, BunkerWeb peut héberger et protéger plusieurs sites web, chacun avec sa propre configuration. Ce mode est utile notamment pour :

- Héberger plusieurs domaines aux configurations distinctes
- Exécuter plusieurs applications avec des exigences de sécurité différentes
- Appliquer des politiques de sécurité adaptées à différents services

En mode multisite, chaque site est identifié par un `SERVER_NAME` unique. Pour appliquer des paramètres spécifiques à un site, préfixez le nom du paramètre par le `SERVER_NAME` principal. Par exemple :

- `www.example.com_USE_ANTIBOT=captcha` active le CAPTCHA pour `www.example.com`.
- `myapp.example.com_USE_GZIP=yes` active la compression GZIP pour `myapp.example.com`.

Cette approche garantit que les paramètres sont appliqués au bon site dans un environnement multisite.

### Paramètres multiples {#multiple-settings}

Certains paramètres de BunkerWeb supportent plusieurs configurations pour une même fonctionnalité. Pour définir plusieurs groupes de paramètres, ajoutez un suffixe numérique au nom du paramètre. Par exemple :

- `REVERSE_PROXY_URL_1=/subdir` et `REVERSE_PROXY_HOST_1=http://myhost1` définissent le premier reverse proxy.
- `REVERSE_PROXY_URL_2=/anotherdir` et `REVERSE_PROXY_HOST_2=http://myhost2` définissent le second reverse proxy.

Ce modèle permet de gérer plusieurs configurations pour des fonctionnalités comme les reverse proxies, les ports, ou d’autres paramètres nécessitant des valeurs distinctes selon les cas d’usage.

### Ordre d'exécution des plugins {#plugin-order}

Vous pouvez définir l’ordre d’exécution via des listes séparées par des espaces :

- Phases globales : `PLUGINS_ORDER_INIT`, `PLUGINS_ORDER_INIT_WORKER`, `PLUGINS_ORDER_TIMER`.
- Phases par site : `PLUGINS_ORDER_SET`, `PLUGINS_ORDER_ACCESS`, `PLUGINS_ORDER_SSL_CERTIFICATE`, `PLUGINS_ORDER_HEADER`, `PLUGINS_ORDER_LOG`, `PLUGINS_ORDER_PREREAD`, `PLUGINS_ORDER_LOG_STREAM`, `PLUGINS_ORDER_LOG_DEFAULT`.
- Sémantique : les plugins listés s’exécutent en premier pour la phase ; les autres s’exécutent ensuite dans leur séquence normale. Séparez les IDs uniquement par des espaces.

### Modes de sécurité {#security-modes}

Le paramètre `SECURITY_MODE` détermine la façon dont BunkerWeb gère les menaces détectées. Ce mécanisme flexible vous permet de choisir entre la surveillance et le blocage actif des activités suspectes, selon vos besoins :

- `detect` : Enregistre les menaces potentielles sans les bloquer. Utile pour analyser les faux positifs sans perturber les utilisateurs légitimes.
- `block` (par défaut) : Bloque activement les menaces détectées tout en journalisant les incidents pour protéger votre application.

Passer en mode `detect` aide à identifier et corriger les faux positifs sans impacter les clients légitimes. Une fois ces problèmes résolus, repassez en mode `block` pour une protection complète.

### Paramètres de configuration

=== "Paramètres principaux"

    | Paramètre             | Valeur par défaut | Contexte  | Multiple | Description                                                                                              |
    | --------------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `SERVER_NAME`         | `www.example.com` | multisite | Non      | **Domaine principal :** Nom de domaine principal pour ce site. Requis en mode multisite.                 |
    | `BUNKERWEB_INSTANCES` | `127.0.0.1`       | global    | Non      | **Instances BunkerWeb :** Liste des instances BunkerWeb séparées par des espaces.                        |
    | `MULTISITE`           | `no`              | global    | Non      | **Sites multiples :** Définir à `yes` pour héberger plusieurs sites avec des configurations différentes. |
    | `SECURITY_MODE`       | `block`           | multisite | Non      | **Niveau de sécurité :** `detect` ou `block` pour contrôler l’application de la sécurité.                |
    | `SERVER_TYPE`         | `http`            | multisite | Non      | **Type de serveur :** Définit si le serveur est de type `http` ou `stream`.                              |

=== "Paramètres API"

    | Paramètre          | Valeur par défaut | Contexte | Multiple | Description                                                                                                     |
    | ------------------ | ----------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------- |
    | `USE_API`          | `yes`             | global   | Non      | **Activer l’API :** Active l’API pour piloter BunkerWeb.                                                        |
    | `API_HTTP_PORT`    | `5000`            | global   | Non      | **Port de l’API :** Numéro de port d’écoute de l’API.                                                           |
    | `API_HTTPS_PORT`   | `5443`            | global   | Non      | **Port HTTPS de l’API :** Numéro de port d’écoute (TLS) de l’API.                                               |
    | `API_LISTEN_HTTP`  | `yes`             | global   | Non      | **Écoute HTTP de l’API :** Active l’écoute HTTP pour l’API.                                                     |
    | `API_LISTEN_HTTPS` | `no`              | global   | Non      | **Écoute HTTPS de l’API :** Active l’écoute HTTPS (TLS) pour l’API.                                             |
    | `API_LISTEN_IP`    | `0.0.0.0`         | global   | Non      | **IP d’écoute de l’API :** Adresse IP d’écoute de l’API.                                                        |
    | `API_SERVER_NAME`  | `bwapi`           | global   | Non      | **Nom de serveur de l’API :** Nom de serveur (vhost) pour l’API.                                                |
    | `API_WHITELIST_IP` | `127.0.0.0/8`     | global   | Non      | **Liste blanche API :** Liste IP/réseaux autorisés à contacter l’API.                                           |
    | `API_TOKEN`        |                   | global   | Non      | **Jeton d’accès API (optionnel) :** Si défini, chaque requête API doit inclure `Authorization: Bearer <token>`. |

    Remarque : pour des raisons d’amorçage, si vous activez `API_TOKEN`, vous devez le définir dans l’environnement à la fois de l’instance BunkerWeb et du Scheduler. Le Scheduler ajoute automatiquement l’en-tête `Authorization` quand `API_TOKEN` est présent dans son environnement. S’il n’est pas défini, aucun en-tête n’est envoyé et BunkerWeb n’applique pas l’authentification par jeton. Vous pouvez exposer l’API en HTTPS en définissant `API_LISTEN_HTTPS=yes` (port : `API_HTTPS_PORT`, `5443` par défaut).

    Exemple de test avec curl (remplacez le jeton et l’hôte) :

    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://<bunkerweb-host>:5000/ping

    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         --insecure \
         https://<bunkerweb-host>:5443/ping
    ```

=== "Paramètres réseau et ports"

    | Paramètre       | Valeur par défaut | Contexte | Multiple | Description                                              |
    | --------------- | ----------------- | -------- | -------- | -------------------------------------------------------- |
    | `HTTP_PORT`     | `8080`            | global   | Oui      | **Port HTTP :** Numéro de port pour le trafic HTTP.      |
    | `HTTPS_PORT`    | `8443`            | global   | Oui      | **Port HTTPS :** Numéro de port pour le trafic HTTPS.    |
    | `USE_IPV6`      | `no`              | global   | Non      | **Support IPv6 :** Active la connectivité IPv6.          |
    | `DNS_RESOLVERS` | `127.0.0.11`      | global   | Non      | **Résolveurs DNS :** Adresses des résolveurs à utiliser. |

=== "Paramètres serveur Stream"

    | Paramètre                | Valeur par défaut | Contexte  | Multiple | Description                                                     |
    | ------------------------ | ----------------- | --------- | -------- | --------------------------------------------------------------- |
    | `LISTEN_STREAM`          | `yes`             | multisite | Non      | **Écoute stream :** Active l’écoute non-ssl (pass-through).     |
    | `LISTEN_STREAM_PORT`     | `1337`            | multisite | Oui      | **Port stream :** Port d’écoute pour le non-ssl (pass-through). |
    | `LISTEN_STREAM_PORT_SSL` | `4242`            | multisite | Oui      | **Port stream SSL :** Port d’écoute pour le SSL (pass-through). |
    | `USE_TCP`                | `yes`             | multisite | Non      | **Écoute TCP :** Active l’écoute TCP (stream).                  |
    | `USE_UDP`                | `no`              | multisite | Non      | **Écoute UDP :** Active l’écoute UDP (stream).                  |

=== "Paramètres des workers"

    | Paramètre              | Valeur par défaut | Contexte | Multiple | Description                                                                             |
    | ---------------------- | ----------------- | -------- | -------- | --------------------------------------------------------------------------------------- |
    | `WORKER_PROCESSES`     | `auto`            | global   | Non      | **Processus workers :** Nombre de processus workers. `auto` utilise le nombre de cœurs. |
    | `WORKER_CONNECTIONS`   | `1024`            | global   | Non      | **Connexions par worker :** Nombre maximal de connexions par worker.                    |
    | `WORKER_RLIMIT_NOFILE` | `2048`            | global   | Non      | **Limite descripteurs :** Nombre maximal de fichiers ouverts par worker.                |

=== "Paramètres mémoire"

    | Paramètre                      | Valeur par défaut | Contexte | Multiple | Description                                                                           |
    | ------------------------------ | ----------------- | -------- | -------- | ------------------------------------------------------------------------------------- |
    | `WORKERLOCK_MEMORY_SIZE`       | `48k`             | global   | Non      | **Mémoire workerlock :** Taille de lua_shared_dict pour l’initialisation des workers. |
    | `DATASTORE_MEMORY_SIZE`        | `64m`             | global   | Non      | **Mémoire datastore :** Taille du datastore interne.                                  |
    | `CACHESTORE_MEMORY_SIZE`       | `64m`             | global   | Non      | **Mémoire cachestore :** Taille du cache interne.                                     |
    | `CACHESTORE_IPC_MEMORY_SIZE`   | `16m`             | global   | Non      | **Mémoire cachestore IPC :** Taille du cache interne (IPC).                           |
    | `CACHESTORE_MISS_MEMORY_SIZE`  | `16m`             | global   | Non      | **Mémoire cachestore miss :** Taille du cache interne (miss).                         |
    | `CACHESTORE_LOCKS_MEMORY_SIZE` | `16m`             | global   | Non      | **Mémoire cachestore locks :** Taille du cache interne (locks).                       |

=== "Paramètres de journalisation"

    | Paramètre          | Valeur par défaut                                                                                                                          | Contexte | Multiple | Description                                                                                                                                                    |
    | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `LOG_FORMAT`       | `$host $remote_addr - $request_id $remote_user [$time_local] \"$request\" $status $body_bytes_sent \"$http_referer\" \"$http_user_agent\"` | global   | Non      | **Format des logs :** Format utilisé pour les logs d’accès.                                                                                                    |
    | `ACCESS_LOG`       | `/var/log/bunkerweb/access.log`                                                                                                            | global   | Oui      | **Chemin du log d'accès :** Fichier, `syslog:server=hôte[:port][,param=valeur]` ou tampon partagé `memory:nom:taille` ; mettez `off` pour désactiver les logs. |
    | `ERROR_LOG`        | `/var/log/bunkerweb/error.log`                                                                                                             | global   | Oui      | **Chemin du log d'erreur :** Fichier, `stderr`, `syslog:server=hôte[:port][,param=valeur]` ou `memory:taille`.                                                 |
    | `LOG_LEVEL`        | `notice`                                                                                                                                   | global   | Oui      | **Niveau de logs :** Verbosité des logs d’erreur. Options : `debug`, `info`, `notice`, `warn`, `error`, `crit`, `alert`, `emerg`.                              |
    | `TIMERS_LOG_LEVEL` | `debug`                                                                                                                                    | global   | Non      | **Niveau des timers :** Niveau de log pour les timers. Options : `debug`, `info`, `notice`, `warn`, `err`, `crit`, `alert`, `emerg`.                           |

    !!! tip "Bonnes pratiques de journalisation"
        - En production, utilisez les niveaux `notice`, `warn` ou `error` pour limiter le volume de logs.
        - Pour le dépannage, passez temporairement le niveau à `debug` pour obtenir plus de détails.

=== "Paramètres d’intégration"

    | Paramètre         | Valeur par défaut | Contexte  | Multiple | Description                                                                                                     |
    | ----------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
    | `AUTOCONF_MODE`   | `no`              | global    | Non      | **Mode Autoconf :** Active l’intégration Docker Autoconf.                                                       |
    | `SWARM_MODE`      | `no`              | global    | Non      | **Mode Swarm :** Active l’intégration Docker Swarm.                                                             |
    | `KUBERNETES_MODE` | `no`              | global    | Non      | **Mode Kubernetes :** Active l’intégration Kubernetes.                                                          |
    | `KEEP_CONFIG_ON_RESTART` | `no` | global | Non | **Garder la configuration au redémarrage :** Conserver la configuration au redémarrage. Mettre à 'yes' pour éviter la réinitialisation de la config au redémarrage. |
    | `USE_TEMPLATE`    |                   | multisite | Non      | **Utiliser un template :** Modèle de configuration qui surcharge les valeurs par défaut de certains paramètres. |

=== "Paramètres Nginx"

    | Paramètre                       | Valeur par défaut | Contexte | Multiple | Description                                                                  |
    | ------------------------------- | ----------------- | -------- | -------- | ---------------------------------------------------------------------------- |
    | `NGINX_PREFIX`                  | `/etc/nginx/`     | global   | Non      | **Préfixe Nginx :** Répertoire où NGINX va chercher les configurations.      |
    | `SERVER_NAMES_HASH_BUCKET_SIZE` |                   | global   | Non      | **Taille du hash :** Valeur pour la directive server_names_hash_bucket_size. |

### Exemples de configuration

=== "Configuration de base (production)"

    Configuration standard pour un site de production avec une sécurité stricte :

    ```yaml
    SECURITY_MODE: "block"
    SERVER_NAME: "example.com"
    LOG_LEVEL: "notice"
    ```

=== "Mode développement"

    Configuration pour un environnement de développement avec journalisation détaillée :

    ```yaml
    SECURITY_MODE: "detect"
    SERVER_NAME: "dev.example.com"
    LOG_LEVEL: "debug"
    ```

=== "Configuration multisite"

    Configuration pour héberger plusieurs sites :

    ```yaml
    MULTISITE: "yes"

    # Premier site
    site1.example.com_SERVER_NAME: "site1.example.com"
    site1.example.com_SECURITY_MODE: "block"

    # Second site
    site2.example.com_SERVER_NAME: "site2.example.com"
    site2.example.com_SECURITY_MODE: "detect"
    ```

=== "Configuration serveur Stream"

    Configuration pour un serveur TCP/UDP :

    ```yaml
    SERVER_TYPE: "stream"
    SERVER_NAME: "stream.example.com"
    LISTEN_STREAM: "yes"
    LISTEN_STREAM_PORT: "1337"
    USE_TCP: "yes"
    USE_UDP: "no"
    ```
