# Fonctionnalités

Cette section contient la liste complète des paramètres pris en charge par BunkerWeb. Si vous n’êtes pas encore familier avec BunkerWeb, commencez par lire la section [concepts](concepts.md) de la documentation. Suivez ensuite les instructions de votre [intégration](integrations.md) pour appliquer les paramètres.

## Paramètres globaux


Prise en charge STREAM :warning:

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

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :x:

Provides enhanced protection against DDoS attacks by analyzing and filtering suspicious traffic.

| Paramètre                    | Valeur par défaut | Contexte | Multiple | Description                                                             |
| ---------------------------- | ----------------- | -------- | -------- | ----------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`              | global   | non      | Enable or disable anti DDoS protection to mitigate high traffic spikes. |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`             | global   | non      | Size of in-memory storage for DDoS metrics (e.g., 10M, 500k).           |
| `ANTIDDOS_THRESHOLD`         | `100`             | global   | non      | Maximum suspicious requests allowed from a single IP before blocking.   |
| `ANTIDDOS_WINDOW_TIME`       | `10`              | global   | non      | Time window (seconds) to detect abnormal request patterns.              |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444`     | global   | non      | HTTP status codes treated as suspicious for DDoS analysis.              |
| `ANTIDDOS_DISTINCT_IP`       | `5`               | global   | non      | Minimum distinct IP count before enabling anti DDoS measures.           |

## Antibot

Prise en charge STREAM :x:

Les attaquants utilisent souvent des outils automatisés (bots) pour tenter d’exploiter votre site. Pour s’en protéger, BunkerWeb inclut une fonctionnalité « Antibot » qui demande aux utilisateurs de prouver qu’ils sont humains. Si un utilisateur réussit le défi, il obtient l’accès à votre site. Cette fonctionnalité est désactivée par défaut.

Comment ça marche :

1. Lorsqu’un utilisateur visite votre site, BunkerWeb vérifie s’il a déjà réussi un défi antibot.
2. Sinon, l’utilisateur est redirigé vers une page de défi.
3. L’utilisateur doit compléter le défi (ex. résoudre un CAPTCHA, exécuter du JavaScript).
4. Si le défi est réussi, l’utilisateur est redirigé vers la page initialement demandée et peut naviguer normalement.

### Comment l’utiliser

Suivez ces étapes pour activer et configurer Antibot :

1. Choisir un type de défi : décidez du mécanisme à utiliser (ex. [captcha](#__tabbed_3_3), [hcaptcha](#__tabbed_3_5), [javascript](#__tabbed_3_2)).
2. Activer la fonctionnalité : définissez le paramètre `USE_ANTIBOT` sur le type choisi dans votre configuration BunkerWeb.
3. Configurer les paramètres : ajustez les autres paramètres `ANTIBOT_*` si nécessaire. Pour reCAPTCHA, hCaptcha, Turnstile et mCaptcha, créez un compte auprès du service choisi et obtenez des clés API.
4. Important : assurez‑vous que `ANTIBOT_URI` est une URL unique de votre site et qu’elle n’est pas utilisée ailleurs.

!!! important "À propos du paramètre `ANTIBOT_URI`"
    Assurez‑vous que `ANTIBOT_URI` est une URL unique de votre site et qu’elle n’est pas utilisée ailleurs.

!!! warning "Sessions en environnement cluster"
    La fonction antibot utilise des cookies pour suivre si un utilisateur a complété le défi. Si vous exécutez BunkerWeb en cluster (plusieurs instances), vous devez configurer correctement la gestion des sessions : définissez `SESSIONS_SECRET` et `SESSIONS_NAME` avec les mêmes valeurs sur toutes les instances BunkerWeb. Sinon, les utilisateurs pourront être invités à répéter le défi. Plus d’informations sur la configuration des sessions [ici](#sessions).

### Paramètres communs

Les paramètres suivants sont partagés par tous les mécanismes de défi :

| Paramètre              | Valeur par défaut | Contexte  | Multiple | Description                                                                                                                                                 |
| ---------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge`      | multisite | non      | URL du défi : l’URL vers laquelle les utilisateurs sont redirigés pour compléter le défi. Veillez à ce que cette URL ne soit pas utilisée pour autre chose. |
| `ANTIBOT_TIME_RESOLVE` | `60`              | multisite | non      | Délai du défi : temps maximum (en secondes) pour compléter le défi. Au‑delà, un nouveau défi est généré.                                                    |
| `ANTIBOT_TIME_VALID`   | `86400`           | multisite | non      | Validité du défi : durée (en secondes) pendant laquelle un défi réussi reste valide. Passé ce délai, un nouveau défi sera requis.                           |

### Exclure du trafic des défis

BunkerWeb permet d’indiquer certains utilisateurs, IP ou requêtes qui doivent contourner totalement le défi antibot. Utile pour des services de confiance, réseaux internes ou des pages à laisser toujours accessibles :

| Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                                      |
| --------------------------- | ------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |        | multisite | non      | URL exclues : liste d’expressions régulières d’URI séparées par des espaces qui doivent contourner le défi.      |
| `ANTIBOT_IGNORE_IP`         |        | multisite | non      | IP exclues : liste d’adresses IP ou de plages CIDR séparées par des espaces qui doivent contourner le défi.      |
| `ANTIBOT_IGNORE_RDNS`       |        | multisite | non      | rDNS exclu : liste de suffixes de DNS inversés séparés par des espaces qui doivent contourner le défi.           |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`  | multisite | non      | IP publiques uniquement : si `yes`, ne faire des vérifications rDNS que sur des IP publiques.                    |
| `ANTIBOT_IGNORE_ASN`        |        | multisite | non      | ASN exclus : liste de numéros d’ASN séparés par des espaces qui doivent contourner le défi.                      |
| `ANTIBOT_IGNORE_USER_AGENT` |        | multisite | non      | User‑Agents exclus : liste de motifs regex d’User‑Agent séparés par des espaces qui doivent contourner le défi.  |
| `ANTIBOT_IGNORE_COUNTRY`    |        | multisite | non      | Pays exclus : liste de codes pays ISO 3166-1 alpha-2 séparés par des espaces qui doivent contourner le défi.     |
| `ANTIBOT_ONLY_COUNTRY`      |        | multisite | non      | Pays ciblés : liste de codes pays ISO 3166-1 alpha-2 qui doivent résoudre le défi. Les autres pays sont ignorés. |

!!! note "Comportement des paramètres basés sur le pays"
      - Lorsque `ANTIBOT_IGNORE_COUNTRY` et `ANTIBOT_ONLY_COUNTRY` sont définis, la liste d’exclusion est prioritaire : un pays présent dans les deux listes contourne le défi.
      - Les adresses IP privées ou inconnues contournent le défi lorsque `ANTIBOT_ONLY_COUNTRY` est défini, car aucun code pays ne peut être déterminé.

Exemples :

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  Exclut toutes les URI commençant par `/api/`, `/webhook/` ou `/assets/`.

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  Exclut le réseau interne `192.168.1.0/24` et l’IP spécifique `10.0.0.1`.

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  Exclut les requêtes provenant d’hôtes dont le DNS inversé se termine par `googlebot.com` ou `bingbot.com`.

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  Exclut les requêtes des ASN 15169 (Google) et 8075 (Microsoft).

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  Exclut les requêtes dont le User-Agent correspond au motif regex spécifié.

- `ANTIBOT_IGNORE_COUNTRY: "US CA"`
  Contourne le défi antibot pour les visiteurs situés aux États-Unis ou au Canada.

- `ANTIBOT_ONLY_COUNTRY: "CN RU"`
  Ne défie que les visiteurs provenant de Chine ou de Russie. Les requêtes d’autres pays (ou d’adresses IP privées) contournent le défi.

### Mécanismes de défi

=== "Cookie"

    Le défi Cookie est un mécanisme léger qui repose sur l’installation d’un cookie dans le navigateur de l’utilisateur. Lorsqu’un utilisateur accède au site, le serveur envoie un cookie au client. Lors des requêtes suivantes, le serveur vérifie la présence de ce cookie pour confirmer que l’utilisateur est légitime. Cette méthode est simple et efficace pour une protection de base contre les bots sans nécessiter d’interaction supplémentaire de l’utilisateur.

    **Comment ça marche :**

    1. Le serveur génère un cookie unique et l’envoie au client.
    2. Le client doit renvoyer le cookie dans les requêtes suivantes.
    3. Si le cookie est manquant ou invalide, l’utilisateur est redirigé vers la page de défi.

    **Paramètres :**

    | Paramètre     | Défaut | Contexte  | Multiple | Description                                                       |
    | ------------- | ------ | --------- | -------- | ----------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | non      | Activer Antibot : définir sur `cookie` pour activer ce mécanisme. |

=== "JavaScript"

    Le défi JavaScript demande au client de résoudre une tâche de calcul en utilisant JavaScript. Ce mécanisme garantit que le client a activé JavaScript et peut exécuter le code requis, ce qui est généralement hors de portée de la plupart des bots.

    **Comment ça marche :**

    1. Le serveur envoie un script JavaScript au client.
    2. Le script effectue une tâche de calcul (par exemple, un hachage) et soumet le résultat au serveur.
    3. Le serveur vérifie le résultat pour confirmer la légitimité du client.

    **Fonctionnalités clés :**

    - Le défi génère dynamiquement une tâche unique pour chaque client.
    - La tâche de calcul implique un hachage avec des conditions spécifiques (par exemple, trouver un hachage avec un certain préfixe).

    **Paramètres :**

    | Paramètre     | Défaut | Contexte  | Multiple | Description                                                           |
    | ------------- | ------ | --------- | -------- | --------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`   | multisite | non      | Activer Antibot : définir sur `javascript` pour activer ce mécanisme. |

=== "Captcha"

    Le défi Captcha est un mécanisme maison qui génère des défis basés sur des images, entièrement hébergés dans votre environnement BunkerWeb. Il teste la capacité des utilisateurs à reconnaître et interpréter des caractères aléatoires, garantissant que les bots automatisés sont bloqués efficacement sans dépendre de services externes.

    **Comment ça marche :**

    1. Le serveur génère une image CAPTCHA contenant des caractères aléatoires.
    2. L’utilisateur doit saisir les caractères affichés dans l’image dans un champ de texte.
    3. Le serveur valide la saisie de l’utilisateur par rapport au CAPTCHA généré.

    **Fonctionnalités clés :**

    - Entièrement auto-hébergé, éliminant le besoin d’API tierces.
    - Les défis générés dynamiquement assurent l’unicité pour chaque session utilisateur.
    - Utilise un jeu de caractères personnalisable pour la génération du CAPTCHA.

    **Caractères pris en charge :**

    Le système CAPTCHA prend en charge les types de caractères suivants :

    - **Lettres :** Toutes les lettres minuscules (a-z) et majuscules (A-Z)
    - **Chiffres :** 2, 3, 4, 5, 6, 7, 8, 9 (exclut 0 et 1 pour éviter toute confusion)
    - **Caractères spéciaux :** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    Pour obtenir la liste complète des caractères pris en charge, consultez la [table des caractères de la police](https://www.dafont.com/moms-typewriter.charmap?back=theme) utilisée pour le CAPTCHA.

    **Paramètres :**

    | Paramètre                  | Défaut                                                 | Contexte  | Multiple | Description                                                                                                                                                                                                                                               |
    | -------------------------- | ------------------------------------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                                                   | multisite | non      | **Activer Antibot :** définir sur `captcha` pour activer ce mécanisme.                                                                                                                                                                                    |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | multisite | non      | **Alphabet du Captcha :** une chaîne de caractères à utiliser pour générer le CAPTCHA. Caractères pris en charge : toutes les lettres (a-z, A-Z), les chiffres 2-9 (exclut 0 et 1), et les caractères spéciaux : ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

=== "reCAPTCHA"

    reCAPTCHA de Google propose une validation des utilisateurs qui s’exécute en arrière‑plan (v3) pour attribuer un score basé sur le comportement. Un score inférieur au seuil configuré déclenchera une vérification supplémentaire ou bloquera la requête. Pour les défis visibles (v2), les utilisateurs doivent interagir avec le widget reCAPTCHA avant de continuer.

    Il existe désormais deux manières d’intégrer reCAPTCHA :
    - La version classique (clés site/secret, point de terminaison de vérification v2/v3)
    - La nouvelle version utilisant Google Cloud (ID de projet + clé API). La version classique reste disponible et peut être activée avec `ANTIBOT_RECAPTCHA_CLASSIC`.

    Pour la version classique, obtenez vos clés de site et secrète depuis la [console d’administration de Google reCAPTCHA](https://www.google.com/recaptcha/admin).
    Pour la nouvelle version, créez une clé reCAPTCHA dans votre projet Google Cloud et utilisez l’ID du projet ainsi qu’une clé API (voir la [console reCAPTCHA de Google Cloud](https://console.cloud.google.com/security/recaptcha)). Une clé de site est toujours requise.

    **Paramètres :**

    | Paramètre                      | Défaut | Contexte  | Multiple | Description                                                                                                         |
    | ------------------------------ | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`                  | `no`   | multisite | non      | Activer Antibot : définir sur `recaptcha` pour activer ce mécanisme.                                                |
    | `ANTIBOT_RECAPTCHA_CLASSIC`    | `yes`  | multisite | non      | Utiliser reCAPTCHA classique. Mettre à `no` pour utiliser la nouvelle version basée sur Google Cloud.               |
    | `ANTIBOT_RECAPTCHA_SITEKEY`    |        | multisite | non      | Clé de site reCAPTCHA. Requise pour les deux versions.                                                              |
    | `ANTIBOT_RECAPTCHA_SECRET`     |        | multisite | non      | Clé secrète reCAPTCHA. Requise pour la version classique uniquement.                                                |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID` |        | multisite | non      | ID de projet Google Cloud. Requis pour la nouvelle version uniquement.                                              |
    | `ANTIBOT_RECAPTCHA_API_KEY`    |        | multisite | non      | Clé API Google Cloud utilisée pour appeler l’API reCAPTCHA Enterprise. Requise pour la nouvelle version uniquement. |
    | `ANTIBOT_RECAPTCHA_JA3`        |        | multisite | non      | Empreinte TLS JA3 optionnelle à inclure dans les évaluations Enterprise.                                            |
    | `ANTIBOT_RECAPTCHA_JA4`        |        | multisite | non      | Empreinte TLS JA4 optionnelle à inclure dans les évaluations Enterprise.                                            |
    | `ANTIBOT_RECAPTCHA_SCORE`      | `0.7`  | multisite | non      | Score minimum requis pour passer (s’applique à la v3 classique et à la nouvelle version).                           |

=== "hCaptcha"

    Lorsqu’il est activé, hCaptcha offre une alternative efficace à reCAPTCHA en vérifiant les interactions des utilisateurs sans reposer sur un mécanisme de score. Il met les utilisateurs au défi avec un test simple et interactif pour confirmer leur légitimité.

    Pour intégrer hCaptcha avec BunkerWeb, vous devez obtenir les informations d’identification nécessaires depuis le tableau de bord hCaptcha sur [hCaptcha](https://www.hcaptcha.com). Ces informations incluent une clé de site et une clé secrète.

    **Paramètres :**

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                                         |
    | -------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`   | multisite | non      | Activer Antibot : définir sur `hcaptcha` pour activer ce mécanisme. |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |        | multisite | non      | Clé site hCaptcha.                                                  |
    | `ANTIBOT_HCAPTCHA_SECRET`  |        | multisite | non      | Clé secrète hCaptcha.                                               |

=== "Turnstile"

    Turnstile est un mécanisme de défi moderne et respectueux de la vie privée qui s’appuie sur la technologie de Cloudflare pour détecter et bloquer le trafic automatisé. Il valide les interactions des utilisateurs de manière transparente et en arrière-plan, réduisant les frictions pour les utilisateurs légitimes tout en décourageant efficacement les bots.

    Pour intégrer Turnstile avec BunkerWeb, assurez-vous d’obtenir les informations d’identification nécessaires depuis [Cloudflare Turnstile](https://www.cloudflare.com/turnstile).

    **Paramètres :**

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                          |
    | --------------------------- | ------ | --------- | -------- | -------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`   | multisite | non      | Activer Antibot : définir sur `turnstile` pour activer ce mécanisme. |
    | `ANTIBOT_TURNSTILE_SITEKEY` |        | multisite | non      | Clé site Turnstile (Cloudflare).                                     |
    | `ANTIBOT_TURNSTILE_SECRET`  |        | multisite | non      | Clé secrète Turnstile (Cloudflare).                                  |

=== "mCaptcha"

    mCaptcha est un mécanisme de défi CAPTCHA alternatif qui vérifie la légitimité des utilisateurs en présentant un test interactif similaire à d’autres solutions antibot. Lorsqu’il est activé, il met les utilisateurs au défi avec un CAPTCHA fourni par mCaptcha, s’assurant que seuls les utilisateurs authentiques contournent les contrôles de sécurité automatisés.

    mCaptcha est conçu dans le respect de la vie privée. Il est entièrement conforme au RGPD, garantissant que toutes les données des utilisateurs impliquées dans le processus de défi respectent des normes strictes de protection des données. De plus, mCaptcha offre la flexibilité d’être auto-hébergé, permettant aux organisations de garder un contrôle total sur leurs données et leur infrastructure. Cette capacité d’auto-hébergement améliore non seulement la confidentialité, mais optimise également les performances et la personnalisation pour répondre aux besoins spécifiques de déploiement.

    Pour intégrer mCaptcha avec BunkerWeb, vous devez obtenir les informations d’identification nécessaires depuis la plateforme [mCaptcha](https://mcaptcha.org/) ou votre propre fournisseur. Ces informations incluent une clé de site et une clé secrète pour la vérification.

    **Paramètres :**

    | Paramètre                  | Défaut                      | Contexte  | Multiple | Description                                                         |
    | -------------------------- | --------------------------- | --------- | -------- | ------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | non      | Activer Antibot : définir sur `mcaptcha` pour activer ce mécanisme. |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | non      | Clé site mCaptcha.                                                  |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | non      | Clé secrète mCaptcha.                                               |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | non      | Domaine à utiliser pour mCaptcha.                                   |

    Reportez‑vous aux Paramètres communs pour les options supplémentaires.

### Exemples de configuration

=== "Défi Cookie"

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Défi JavaScript"

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Défi Captcha"

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    Remarque : l’exemple ci‑dessus utilise les chiffres 2‑9 et toutes les lettres, fréquemment utilisés pour les CAPTCHA. Vous pouvez personnaliser l’alphabet pour inclure des caractères spéciaux si nécessaire.

=== "Défi reCAPTCHA Classique"

    Exemple de configuration pour le reCAPTCHA classique (clés site/secret) :

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "yes"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Défi reCAPTCHA (nouveau)"

    Exemple de configuration pour le nouveau reCAPTCHA basé sur Google Cloud (ID de projet + clé API) :

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # Empreintes optionnelles pour améliorer les évaluations Enterprise
    # ANTIBOT_RECAPTCHA_JA3: "<empreinte-ja3>"
    # ANTIBOT_RECAPTCHA_JA4: "<empreinte-ja4>"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Défi hCaptcha"

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Défi Turnstile"

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Défi mCaptcha"

    ```yaml
    USE_ANTIBOT: "mcaptcha"
    ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

## Auth basic

Prise en charge STREAM :x:

Le plugin Auth Basic fournit une authentification HTTP Basic pour protéger votre site ou certaines ressources. Les utilisateurs doivent saisir un identifiant et un mot de passe avant d’accéder au contenu protégé. Simple à mettre en place et largement supporté par les navigateurs.

Comment ça marche :

1. Sur une zone protégée, le serveur envoie un défi d’authentification.
2. Le navigateur affiche une boîte de connexion.
3. L’utilisateur saisit ses identifiants, envoyés au serveur.
4. Valides ? Accès accordé. Invalides ? Réponse 401 Unauthorized.

### Comment l’utiliser

1. Activer : `USE_AUTH_BASIC: yes`.
2. Portée : `AUTH_BASIC_LOCATION` = `sitewide` (tout le site) ou un chemin (ex. `/admin`).
3. Identifiants : configurez `AUTH_BASIC_USER` et `AUTH_BASIC_PASSWORD` (plusieurs paires possibles).
4. Message : optionnel, ajustez `AUTH_BASIC_TEXT`.

### Paramètres

| Paramètre             | Défaut            | Contexte  | Multiple | Description                                                                                                                              |
| --------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | non      | Activer l’authentification Basic.                                                                                                        |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | non      | Portée : `sitewide` ou un chemin (ex. `/admin`). Vous pouvez également utiliser des modificateurs de style Nginx (`=`, `~`, `~*`, `^~`). |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | oui      | Nom d’utilisateur. Plusieurs paires peuvent être définies.                                                                               |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | oui      | Mot de passe. Les mots de passe sont hachés avec scrypt pour une sécurité maximale.                                                      |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | non      | Message affiché dans l'invite d'authentification.                                                                                        |

!!! warning "Sécurité"
    Les identifiants sont encodés Base64, pas chiffrés. Utilisez toujours HTTPS avec l’authentification Basic.

!!! tip "Plusieurs comptes"
    Définissez des paires `AUTH_BASIC_USER[_n]`/`AUTH_BASIC_PASSWORD[_n]` pour gérer plusieurs utilisateurs.

### Exemples

=== "Tout le site"

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Zone spécifique"

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Utilisateurs multiples"

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # Premier utilisateur
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Deuxième utilisateur
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Troisième utilisateur
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```

## Backup

Prise en charge STREAM :white_check_mark:

Le plugin Backup fournit des sauvegardes automatisées pour protéger vos données BunkerWeb. Il crée des sauvegardes régulières selon une planification définie, stockées dans un emplacement dédié, avec rotation automatique et commandes CLI pour gérer manuellement.

Comment ça marche :

1. La base est sauvegardée automatiquement selon la fréquence (quotidienne, hebdomadaire, mensuelle).
2. Les sauvegardes sont stockées dans un répertoire dédié.
3. Les anciennes sauvegardes sont supprimées selon la politique de rétention.
4. Vous pouvez créer, lister et restaurer manuellement des sauvegardes.
5. Avant toute restauration, un snapshot de l’état courant est créé automatiquement.

### Comment l’utiliser

1. Activation : `USE_BACKUP` (activé par défaut).
2. Planification : `BACKUP_SCHEDULE`.
3. Rétention : `BACKUP_ROTATION`.
4. Emplacement : `BACKUP_DIRECTORY`.
5. CLI : utilisez `bwcli plugin backup`.

### Paramètres

| Paramètre          | Défaut                       | Contexte | Multiple | Description                                                                   |
| ------------------ | ---------------------------- | -------- | -------- | ----------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | non      | Activer les sauvegardes automatiques.                                         |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | non      | Fréquence : `daily`, `weekly`, `monthly`.                                     |
| `BACKUP_ROTATION`  | `7`                          | global   | non      | Rétention : nombre de fichiers à conserver. Au‑delà, suppression automatique. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | non      | Répertoire de stockage des sauvegardes.                                       |

### Interface en ligne de commande

```bash
bwcli plugin backup list        # Lister
bwcli plugin backup save        # Sauvegarde manuelle
bwcli plugin backup save --directory /chemin/perso   # Emplacement personnalisé
bwcli plugin backup restore     # Restaurer la plus récente
bwcli plugin backup restore /chemin/backup-sqlite-YYYY-MM-DD_HH-MM-SS.zip   # Restaurer via fichier
```

!!! tip "Sécurité"
    Avant toute restauration, un backup de l’état courant est créé automatiquement dans un emplacement temporaire.

!!! warning "Compatibilité bases"
    Supporte SQLite, MySQL/MariaDB, PostgreSQL. Oracle non pris en charge pour sauvegarde/restauration.

### Exemples

=== "Quotidien, rétention 7 jours" (défaut)

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Hebdomadaire, rétention étendue"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Mensuel, emplacement personnalisé"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```

## Backup S3 <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :white_check_mark:

Automatically backup your data to an S3 bucket

| Paramètre                     | Valeur par défaut | Contexte | Multiple | Description                                  |
| ----------------------------- | ----------------- | -------- | -------- | -------------------------------------------- |
| `USE_BACKUP_S3`               | `no`              | global   | non      | Enable or disable the S3 backup feature      |
| `BACKUP_S3_SCHEDULE`          | `daily`           | global   | non      | The frequency of the backup                  |
| `BACKUP_S3_ROTATION`          | `7`               | global   | non      | The number of backups to keep                |
| `BACKUP_S3_ENDPOINT`          |                   | global   | non      | The S3 endpoint                              |
| `BACKUP_S3_BUCKET`            |                   | global   | non      | The S3 bucket                                |
| `BACKUP_S3_DIR`               |                   | global   | non      | The S3 directory                             |
| `BACKUP_S3_REGION`            |                   | global   | non      | The S3 region                                |
| `BACKUP_S3_ACCESS_KEY_ID`     |                   | global   | non      | The S3 access key ID                         |
| `BACKUP_S3_ACCESS_KEY_SECRET` |                   | global   | non      | The S3 access key secret                     |
| `BACKUP_S3_COMP_LEVEL`        | `6`               | global   | non      | The compression level of the backup zip file |

## Bad behavior

Prise en charge STREAM :white_check_mark:

Le plugin Bad Behavior protège votre site en détectant et bannissant automatiquement les IP qui génèrent trop d’erreurs (codes HTTP « mauvais ») sur une période donnée. Utile contre la force brute, les scrapers, scanners et activités malveillantes.

Les attaquants déclenchent fréquemment des codes « suspects » lors de sondes ou d’exploitation — bien plus qu’un utilisateur normal sur une même période. En détectant ce comportement, BunkerWeb bannit l’IP fautive.

Comment ça marche :

1. Le plugin surveille les réponses HTTP.
2. À chaque code « mauvais » (400, 401, 403, 404, …), le compteur de l’IP augmente.
3. Au‑delà du seuil et dans la fenêtre configurée, l’IP est bannie.
4. Le bannissement peut être au niveau service (site) ou global (tous les sites).
5. Les bans expirent après la durée configurée (ou sont permanents avec `0`).

### Comment l’utiliser

1. Activation : `USE_BAD_BEHAVIOR` (activé par défaut).
2. Codes à compter : `BAD_BEHAVIOR_STATUS_CODES`.
3. Seuil : `BAD_BEHAVIOR_THRESHOLD`.
4. Fenêtre et durée de ban : `BAD_BEHAVIOR_COUNT_TIME`, `BAD_BEHAVIOR_BAN_TIME`.
5. Portée : `BAD_BEHAVIOR_BAN_SCOPE` (`service` ou `global`). Quand le trafic arrive sur le serveur par défaut (nom de serveur `_`), les bans sont toujours appliqués globalement pour bloquer l’IP partout.

!!! tip "Mode stream"
    En mode stream, seul `444` est considéré comme « mauvais ».

### Paramètres

| Paramètre                   | Défaut                        | Contexte  | Multiple | Description                                                                                                                     |
| --------------------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | non      | Activer la détection et le bannissement.                                                                                        |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | non      | Codes HTTP considérés « mauvais ».                                                                                              |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | non      | Seuil de réponses « mauvaises » avant bannissement.                                                                             |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | non      | Fenêtre de comptage (secondes).                                                                                                 |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | non      | Durée du ban en secondes (`0` = permanent).                                                                                     |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | non      | Portée du ban : site courant (`service`) ou global (`global`). Sur le serveur par défaut (`_`), les bans sont toujours globaux. |

!!! warning "Faux positifs"
    Un seuil/fenêtre trop bas peut bannir des utilisateurs légitimes. Démarrez conservateur et ajustez.

### Exemples

=== "Défaut"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Strict"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"
    BAD_BEHAVIOR_BAN_SCOPE: "global"
    ```

=== "Tolérant"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Ban permanent"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"
    BAD_BEHAVIOR_BAN_SCOPE: "global"
    ```

## Blacklist

Prise en charge STREAM :warning:

Le plugin Blacklist protège votre site en bloquant l’accès selon divers attributs client. Cette fonctionnalité défend contre les entités malveillantes connues, les scanners et les visiteurs suspects en refusant l’accès en fonction des adresses IP, des réseaux, des entrées DNS inversées (rDNS), des ASN, des user-agents et de motifs d’URI spécifiques.

**Comment ça marche :**

1. Le plugin vérifie les requêtes entrantes par rapport à plusieurs critères de liste noire (adresses IP, réseaux, rDNS, ASN, User-Agent ou motifs d’URI).
2. Les listes noires peuvent être spécifiées directement dans votre configuration ou chargées depuis des URL externes.
3. Si un visiteur correspond à une règle de la liste noire (et ne correspond à aucune règle d’ignorance), l’accès est refusé.
4. Les listes noires sont mises à jour automatiquement à intervalles réguliers à partir des URL configurées.
5. Vous pouvez personnaliser précisément quels critères sont vérifiés et ignorés en fonction de vos besoins de sécurité spécifiques.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Blacklist :

1.  **Activer la fonctionnalité :** La fonctionnalité Blacklist est activée par défaut. Si nécessaire, vous pouvez la contrôler avec le paramètre `USE_BLACKLIST`.
2.  **Configurer les règles de blocage :** Définissez quelles IP, quels réseaux, quels motifs rDNS, quels ASN, quels User-Agents ou quelles URI doivent être bloqués.
3.  **Mettre en place des règles d’ignorance :** Spécifiez les exceptions qui doivent contourner les vérifications de la liste noire.
4.  **Ajouter des sources externes :** Configurez des URL pour télécharger et mettre à jour automatiquement les données de la liste noire.
5.  **Surveiller l’efficacité :** Consultez l'[interface web](web-ui.md) pour voir les statistiques sur les requêtes bloquées.

!!! info "Mode stream"
    En mode stream, seules les vérifications par IP, rDNS et ASN seront effectuées.

### Paramètres de configuration

**Général**

| Paramètre                   | Défaut                                                  | Contexte  | Multiple | Description                                                                                                                                  |
| --------------------------- | ------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | non      | **Activer la Blacklist :** Mettre à `yes` pour activer la fonctionnalité de liste noire.                                                     |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | non      | **Listes noires communautaires :** Sélectionnez des listes noires pré-configurées et maintenues par la communauté à inclure dans le blocage. |

=== "Listes noires communautaires"
    **Ce que ça fait :** Vous permet d’ajouter rapidement des listes noires bien entretenues et sourcées par la communauté sans avoir à configurer manuellement les URL.

    Le paramètre `BLACKLIST_COMMUNITY_LISTS` vous permet de choisir parmi des sources de listes noires sélectionnées. Les options disponibles incluent :

    | ID                                        | Description                                                                                                                                                                                                             | Source                                                                                                                         |
    | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
    | `ip:laurent-minne-data-shield-aggressive` | Data-Shield IPv4 Blocklist. DST = Europa                                                                                                                                                                                | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt`   |
    | `ip:danmeuk-tor-exit`                     | Adresses IP des nœuds de sortie Tor (dan.me.uk)                                                                                                                                                                         | `https://www.dan.me.uk/torlist/?exit`                                                                                          |
    | `ua:mitchellkrogza-bad-user-agents`       | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, avec anti-DDOS, Wordpress Theme Detector Blocking et Fail2Ban Jail for Repeat Offenders | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` |

    **Configuration :** Spécifiez plusieurs listes séparées par des espaces. Par exemple :
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Listes communautaires vs configuration manuelle"
        Les listes noires communautaires offrent un moyen pratique de démarrer avec des sources de listes noires éprouvées. Vous pouvez les utiliser en parallèle de configurations manuelles d’URL pour une flexibilité maximale.

=== "Adresse IP"
    **Ce que ça fait :** Bloque les visiteurs en fonction de leur adresse IP ou de leur réseau.

    | Paramètre                  | Défaut                                | Contexte  | Multiple | Description                                                                                                                     |
    | -------------------------- | ------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_IP`             |                                       | multisite | non      | **Liste noire d’IP :** Liste d’adresses IP ou de réseaux (notation CIDR) à bloquer, séparés par des espaces.                    |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | non      | **Liste d’ignorance d’IP :** Liste d’adresses IP ou de réseaux qui doivent contourner les vérifications de la liste noire d’IP. |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | non      | **URL de listes noires d’IP :** Liste d’URL contenant des adresses IP ou des réseaux à bloquer, séparés par des espaces.        |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | non      | **URL de listes d’ignorance d’IP :** Liste d’URL contenant des adresses IP ou des réseaux à ignorer.                            |

    Le paramètre par défaut `BLACKLIST_IP_URLS` inclut une URL qui fournit une **liste des nœuds de sortie Tor connus**. C’est une source courante de trafic malveillant et un bon point de départ pour de nombreux sites.

=== "Reverse DNS"
    **Ce que ça fait :** Bloque les visiteurs en fonction de leur nom de domaine inversé. C’est utile pour bloquer les scanners et les crawlers connus en se basant sur les domaines de leur organisation.

    | Paramètre                    | Défaut                  | Contexte  | Multiple | Description                                                                                                                    |
    | ---------------------------- | ----------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | non      | **Liste noire rDNS :** Liste de suffixes de DNS inversé à bloquer, séparés par des espaces.                                    |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | non      | **rDNS global uniquement :** N’effectue des vérifications rDNS que sur les adresses IP globales si mis à `yes`.                |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | non      | **Liste d’ignorance rDNS :** Liste de suffixes de DNS inversé qui doivent contourner les vérifications de la liste noire rDNS. |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | non      | **URL de listes noires rDNS :** Liste d’URL contenant des suffixes de DNS inversé à bloquer.                                   |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | non      | **URL de listes d’ignorance rDNS :** Liste d’URL contenant des suffixes de DNS inversé à ignorer.                              |

    Le paramètre par défaut `BLACKLIST_RDNS` inclut des domaines de scanners courants comme **Shodan** et **Censys**. Ils sont souvent utilisés par des chercheurs en sécurité et des scanners pour identifier des sites vulnérables.

=== "ASN"
    **Ce que ça fait :** Bloque les visiteurs provenant de fournisseurs de réseaux spécifiques. Les ASN sont comme des codes postaux pour Internet—ils identifient à quel fournisseur ou organisation une IP appartient.

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                                 |
    | --------------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |        | multisite | non      | **Liste noire d’ASN :** Liste de numéros de systèmes autonomes à bloquer, séparés par des espaces.          |
    | `BLACKLIST_IGNORE_ASN`      |        | multisite | non      | **Liste d’ignorance d’ASN :** Liste d’ASN qui doivent contourner les vérifications de la liste noire d’ASN. |
    | `BLACKLIST_ASN_URLS`        |        | multisite | non      | **URL de listes noires d’ASN :** Liste d’URL contenant des ASN à bloquer.                                   |
    | `BLACKLIST_IGNORE_ASN_URLS` |        | multisite | non      | **URL de listes d’ignorance d’ASN :** Liste d’URL contenant des ASN à ignorer.                              |

=== "User-Agent"
    **Ce que ça fait :** Bloque les visiteurs en fonction du navigateur ou de l’outil qu’ils prétendent utiliser. C’est efficace contre les bots qui s’identifient honnêtement (comme "ScannerBot" ou "WebHarvestTool").

    | Paramètre                          | Défaut                                                                                                                         | Contexte  | Multiple | Description                                                                                                                                   |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | non      | **Liste noire de User-Agent :** Liste de motifs de User-Agent (regex PCRE) à bloquer, séparés par des espaces.                                |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | non      | **Liste d’ignorance de User-Agent :** Liste de motifs de User-Agent qui doivent contourner les vérifications de la liste noire de User-Agent. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | non      | **URL de listes noires de User-Agent :** Liste d’URL contenant des motifs de User-Agent à bloquer.                                            |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | non      | **URL de listes d’ignorance de User-Agent :** Liste d’URL contenant des motifs de User-Agent à ignorer.                                       |

    Le paramètre par défaut `BLACKLIST_USER_AGENT_URLS` inclut une URL qui fournit une **liste de user agents malveillants connus**. Ils sont souvent utilisés par des bots et des scanners malveillants pour identifier des sites vulnérables.

=== "URI"
    **Ce que ça fait :** Bloque les requêtes vers des URL spécifiques de votre site. C’est utile pour bloquer les tentatives d’accès aux pages d’administration, aux formulaires de connexion ou à d’autres zones sensibles qui pourraient être ciblées.

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                                           |
    | --------------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |        | multisite | non      | **Liste noire d’URI :** Liste de motifs d’URI (regex PCRE) à bloquer, séparés par des espaces.                        |
    | `BLACKLIST_IGNORE_URI`      |        | multisite | non      | **Liste d’ignorance d’URI :** Liste de motifs d’URI qui doivent contourner les vérifications de la liste noire d’URI. |
    | `BLACKLIST_URI_URLS`        |        | multisite | non      | **URL de listes noires d’URI :** Liste d’URL contenant des motifs d’URI à bloquer.                                    |
    | `BLACKLIST_IGNORE_URI_URLS` |        | multisite | non      | **URL de listes d’ignorance d’URI :** Liste d’URL contenant des motifs d’URI à ignorer.                               |

!!! info "Support des formats d’URL"
    Tous les paramètres `*_URLS` supportent les URL HTTP/HTTPS ainsi que les chemins de fichiers locaux en utilisant le préfixe `file:///`. L’authentification basique est supportée en utilisant le format `http://user:pass@url`.

!!! tip "Mises à jour régulières"
    Les listes noires provenant d’URL sont automatiquement téléchargées et mises à jour toutes les heures pour garantir que votre protection reste à jour contre les dernières menaces.

### Exemples de configuration

=== "Protection de base par IP et User-Agent"

    Une configuration simple qui bloque les nœuds de sortie Tor connus et les user agents malveillants courants en utilisant les listes noires communautaires :

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternativement, vous pouvez utiliser une configuration manuelle par URL :

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Protection avancée avec des règles personnalisées"

    Une configuration plus complète avec des entrées de liste noire personnalisées et des exceptions :

    ```yaml
    USE_BLACKLIST: "yes"

    # Entrées de liste noire personnalisées
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # ASN d'AWS et d'Amazon
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Règles d'ignorance personnalisées
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # Sources de listes noires externes
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Utilisation de fichiers locaux"

    Configuration utilisant des fichiers locaux pour les listes noires :

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///chemin/vers/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///chemin/vers/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///chemin/vers/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///chemin/vers/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///chemin/vers/uri-blacklist.txt"
    ```

### Travailler avec des fichiers de listes locaux

Les paramètres `*_URLS` fournis par les plugins Whitelist, Greylist et Blacklist utilisent le même téléchargeur. Lorsque vous référencez une URL `file:///` :

- Le chemin est résolu dans le conteneur du **scheduler** (dans un déploiement Docker il s’agit généralement de `bunkerweb-scheduler`). Montez-y vos fichiers et vérifiez que l’utilisateur scheduler possède un accès en lecture.
- Chaque fichier est un texte encodé en UTF-8 avec une entrée par ligne. Les lignes vides sont ignorées et les commentaires doivent commencer par `#` ou `;`. Les commentaires `//` ne sont pas pris en charge.
- Valeur attendue selon le type de liste :
  - **Listes IP** acceptent des adresses IPv4/IPv6 ou des réseaux CIDR (par exemple `192.0.2.10` ou `2001:db8::/48`).
  - **Listes rDNS** attendent un suffixe sans espaces (par exemple `.search.msn.com`). Les valeurs sont automatiquement converties en minuscules.
  - **Listes ASN** peuvent contenir uniquement le numéro (`32934`) ou le numéro préfixé par `AS` (`AS15169`).
  - **Listes User-Agent** sont traitées comme des motifs PCRE et la ligne complète est conservée (espaces compris). Placez vos commentaires sur une ligne séparée pour éviter qu’ils ne soient interprétés comme motif.
  - **Listes URI** doivent commencer par `/` et peuvent utiliser des jetons PCRE tels que `^` ou `$`.

Exemples de fichiers conformes :

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Brotli

Prise en charge STREAM :x:

Le plugin Brotli active la compression des réponses HTTP avec l’algorithme Brotli. Il réduit l’usage de bande passante et accélère le chargement en compressant le contenu avant l’envoi au navigateur.

Par rapport à gzip, Brotli atteint généralement de meilleurs taux de compression, pour des fichiers plus petits et une livraison plus rapide.

Comment ça marche :

1. À la requête d’un client, BunkerWeb vérifie si le navigateur supporte Brotli.
2. Si oui, la réponse est compressée au niveau configuré (`BROTLI_COMP_LEVEL`).
3. Les en‑têtes appropriés indiquent la compression Brotli.
4. Le navigateur décompresse avant affichage.
5. Bande passante et temps de chargement diminuent.

### Comment l’utiliser

1. Activer : `USE_BROTLI: yes` (désactivé par défaut).
2. Types MIME : définir les contenus à compresser via `BROTLI_TYPES`.
3. Taille minimale : `BROTLI_MIN_LENGTH` pour éviter de compresser les petites réponses.
4. Niveau de compression : `BROTLI_COMP_LEVEL` pour l’équilibre vitesse/ratio.

### Paramètres

| Paramètre           | Défaut                                                                                                                                                                                                                                                                                                                                                                                                                           | Contexte  | Multiple | Description                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ----------------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | non      | Activer la compression Brotli.                                    |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | non      | Types MIME compressés.                                            |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | non      | Taille minimale (octets) pour appliquer la compression.           |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | non      | Niveau 0–11 : plus haut = meilleure compression mais plus de CPU. |

!!! tip "Niveau de compression"
    `6` offre un bon compromis. Pour du statique et CPU disponible : 9–11. Pour du dynamique ou CPU contraint : 4–5.

### Exemples

=== "Basique"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "Compression maximale"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "Performance équilibrée"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```

## BunkerNet

Prise en charge STREAM :white_check_mark:

Le plugin BunkerNet permet le partage collectif de renseignements sur les menaces entre instances BunkerWeb, créant un réseau de protection contre les acteurs malveillants. En y participant, votre instance bénéficie d’une base mondiale de menaces et y contribue de façon anonyme.

Comment ça marche :

1. Votre instance s’enregistre automatiquement auprès de l’API BunkerNet et reçoit un identifiant unique.
2. À chaque IP/comportement malveillant bloqué, l’information est signalée anonymement à BunkerNet.
3. BunkerNet agrège l’intelligence de toutes les instances et diffuse une base consolidée.
4. Votre instance télécharge régulièrement la base à jour.
5. Cette intelligence collective permet de bloquer proactivement des IP déjà malveillantes ailleurs.

### Comment l’utiliser

1. Activation : `USE_BUNKERNET` (activé par défaut).
2. Enregistrement initial : effectué automatiquement au premier démarrage.
3. Mises à jour : téléchargement automatique et régulier de la base.
4. Signalement : contribution automatique lors de blocages d’IP.
5. Suivi : statistiques visibles dans la [web UI](web-ui.md).

### Paramètres

| Paramètre          | Défaut                     | Contexte  | Multiple | Description                         |
| ------------------ | -------------------------- | --------- | -------- | ----------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | non      | Activer la participation BunkerNet. |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | non      | URL de l’API BunkerNet.             |

!!! info "Confidentialité"
    Seules les données nécessaires à l’identification de la menace sont partagées (IP, raison du blocage, contexte minimal).

### Intégration CrowdSec Console

Grâce au partenariat avec [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc), vous pouvez inscrire vos instances BunkerWeb dans votre [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) et visualiser les attaques bloquées.

Étapes principales :

1. Créez un compte CrowdSec Console et récupérez la clé d’enrôlement.
2. Récupérez votre BunkerNet ID (BunkerNet activé).
3. Commandez le service gratuit « BunkerNet / CrowdSec » sur le Panel et fournissez l’ID et la clé.
4. Acceptez le nouvel engine dans la Console.

### Exemples

=== "Configuration par défaut (recommandée)"

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Désactivation"

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Serveur personnalisé"

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

## CORS

Prise en charge STREAM :x:

Le plugin CORS active le partage de ressources entre origines (Cross‑Origin Resource Sharing) de manière contrôlée. Il permet de partager vos ressources avec des domaines tiers de confiance en définissant précisément origines, méthodes et en‑têtes autorisés.

Comment ça marche :

1. Pour une requête cross‑origin, le navigateur envoie d’abord une requête « preflight » `OPTIONS`.
2. BunkerWeb vérifie si l’origine est autorisée.
3. Si oui, il renvoie les en‑têtes CORS appropriés décrivant ce qui est permis.
4. Sinon, la requête est refusée ou servie sans en‑têtes CORS selon la configuration.
5. Des politiques supplémentaires (COEP/COOP/CORP) peuvent renforcer la sécurité.

### Comment l’utiliser

1. Activer : `USE_CORS: yes` (désactivé par défaut).
2. Origines : `CORS_ALLOW_ORIGIN` (regex PCRE, `*` tous, `self` même origine).
3. Méthodes : `CORS_ALLOW_METHODS`.
4. En‑têtes : `CORS_ALLOW_HEADERS`.
5. Identifiants : `CORS_ALLOW_CREDENTIALS` pour autoriser cookies/auth.

### Paramètres

| Paramètre                      | Défaut                                                                               | Contexte  | Multiple | Description                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------ | --------- | -------- | ----------------------------------------------------------------------------- |
| `USE_CORS`                     | `no`                                                                                 | multisite | non      | Activer CORS.                                                                 |
| `CORS_ALLOW_ORIGIN`            | `self`                                                                               | multisite | non      | Origines autorisées (regex PCRE). `*` = toute origine, `self` = même origine. |
| `CORS_ALLOW_METHODS`           | `GET, POST, OPTIONS`                                                                 | multisite | non      | Méthodes autorisées.                                                          |
| `CORS_ALLOW_HEADERS`           | `DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range` | multisite | non      | En‑têtes autorisés côté requête.                                              |
| `CORS_ALLOW_CREDENTIALS`       | `no`                                                                                 | multisite | non      | Autoriser les identifiants (cookies, auth HTTP).                              |
| `CORS_EXPOSE_HEADERS`          | `Content-Length,Content-Range`                                                       | multisite | non      | En‑têtes exposés côté réponse.                                                |
| `CROSS_ORIGIN_OPENER_POLICY`   | `same-origin`                                                                        | multisite | non      | Politique COOP.                                                               |
| `CROSS_ORIGIN_EMBEDDER_POLICY` | `require-corp`                                                                       | multisite | non      | Politique COEP.                                                               |
| `CROSS_ORIGIN_RESOURCE_POLICY` | `same-site`                                                                          | multisite | non      | Politique CORP.                                                               |
| `CORS_MAX_AGE`                 | `86400`                                                                              | multisite | non      | Durée de cache du preflight (secondes).                                       |
| `CORS_DENY_REQUEST`            | `yes`                                                                                | multisite | non      | Refuser les origines non autorisées avec un code d’erreur.                    |

!!! tip "Optimiser le preflight"
    Augmenter `CORS_MAX_AGE` réduit la fréquence des preflights (par défaut 24h).

!!! warning "Sécurité"
    Soyez prudent avec `CORS_ALLOW_ORIGIN: *` et/ou `CORS_ALLOW_CREDENTIALS: yes`. Préférez lister explicitement les origines de confiance.

### Exemples

=== "Configuration basique"

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "self"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_DENY_REQUEST: "yes"
    ```

=== "API publique"

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "*"
    CORS_ALLOW_METHODS: "GET, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, X-API-Key"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "3600"
    CORS_DENY_REQUEST: "no"
    ```

=== "Plusieurs domaines de confiance"

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(app|api|dashboard)\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, DELETE, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Requested-With"
    CORS_ALLOW_CREDENTIALS: "yes"
    CORS_EXPOSE_HEADERS: "Content-Length, Content-Range, X-RateLimit-Remaining"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Wildcard sous‑domaine"

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://.*\\.example\\.com$"
    CORS_ALLOW_METHODS: "GET, POST, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

=== "Multiples motifs de domaine"

    ```yaml
    USE_CORS: "yes"
    CORS_ALLOW_ORIGIN: "^https://(.*\\.example\\.com|.*\\.trusted-partner\\.org|api\\.third-party\\.net)$"
    CORS_ALLOW_METHODS: "GET, POST, PUT, OPTIONS"
    CORS_ALLOW_HEADERS: "Content-Type, Authorization, X-Custom-Header"
    CORS_ALLOW_CREDENTIALS: "no"
    CORS_MAX_AGE: "86400"
    CORS_DENY_REQUEST: "yes"
    ```

## Cache <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :x:

Provides caching functionality at the reverse proxy level.

| Paramètre                   | Valeur par défaut                 | Contexte  | Multiple | Description                                                                    |
| --------------------------- | --------------------------------- | --------- | -------- | ------------------------------------------------------------------------------ |
| `CACHE_PATH`                |                                   | global    | oui      | Path and parameters for a cache.                                               |
| `CACHE_ZONE`                |                                   | multisite | non      | Name of cache zone to use (specified in a CACHE_PATH setting).                 |
| `CACHE_HEADER`              | `X-Cache`                         | multisite | non      | Add header about cache status.                                                 |
| `CACHE_BACKGROUND_UPDATE`   | `no`                              | multisite | non      | Enable or disable background update of the cache.                              |
| `CACHE_BYPASS`              |                                   | multisite | non      | List of variables to determine if the cache should be bypassed or not.         |
| `CACHE_NO_CACHE`            | `$http_pragma$http_authorization` | multisite | non      | Disable caching if variables are set.                                          |
| `CACHE_KEY`                 | `$scheme$proxy_host$request_uri`  | multisite | non      | Key used to identify cached elements.                                          |
| `CACHE_CONVERT_HEAD_TO_GET` | `yes`                             | multisite | non      | Convert HEAD requests to GET when caching.                                     |
| `CACHE_LOCK`                | `no`                              | multisite | non      | Lock concurrent requests when populating the cache.                            |
| `CACHE_LOCK_AGE`            | `5s`                              | multisite | non      | Pass request to upstream if cache is locked for that time (possible cache).    |
| `CACHE_LOCK_TIMEOUT`        | `5s`                              | multisite | non      | Pass request to upstream if cache is locked for that time (no cache).          |
| `CACHE_METHODS`             | `GET HEAD`                        | multisite | non      | Only cache response if corresponding method is present.                        |
| `CACHE_MIN_USES`            | `1`                               | multisite | non      | Number of requests before we put the corresponding response in cache.          |
| `CACHE_REVALIDATE`          | `no`                              | multisite | non      | Revalidate expired items using conditional requests to upstream.               |
| `CACHE_USE_STALE`           | `off`                             | multisite | non      | Determines the use of staled cache response (proxy_cache_use_stale directive). |
| `CACHE_VALID`               | `10m`                             | multisite | oui      | Defines default caching with optional status code.                             |

## Client cache

Prise en charge STREAM :x:

Le plugin Client Cache optimise les performances en contrôlant la mise en cache des contenus statiques par les navigateurs. Il réduit la bande passante, la charge serveur et accélère les temps de chargement en instruisant les navigateurs à conserver localement images, CSS, JS, etc., plutôt que de les retélécharger à chaque visite.

Comment ça marche :

1. Une fois activé, BunkerWeb ajoute des en‑têtes Cache-Control aux réponses des fichiers statiques.
2. Ces en‑têtes indiquent aux navigateurs pendant combien de temps conserver localement le contenu.
3. Pour les extensions spécifiées (images, CSS, JS…), BunkerWeb applique la politique de cache configurée.
4. Les ETags (optionnels) fournissent un mécanisme de validation supplémentaire.
5. Lors des visites suivantes, le navigateur réutilise les fichiers en cache, accélérant le chargement.

### Comment l’utiliser

1. Activer : mettez `USE_CLIENT_CACHE` à `yes` (désactivé par défaut).
2. Extensions : définissez `CLIENT_CACHE_EXTENSIONS` pour les types de fichiers à mettre en cache.
3. Directives Cache-Control : personnalisez `CLIENT_CACHE_CONTROL`.
4. ETag : activez ou non via `CLIENT_CACHE_ETAG`.

### Paramètres

| Paramètre                 | Défaut                     | Contexte  | Multiple | Description                                                  |
| ------------------------- | -------------------------- | --------- | -------- | ------------------------------------------------------------ | --- |
| `USE_CLIENT_CACHE`        | `no`                       | multisite | non      | Activer la mise en cache côté client des fichiers statiques. |
| `CLIENT_CACHE_EXTENSIONS` | `jpg                       | jpeg      | png      | bmp                                                          | ico | svg | tif | css | js | otf | ttf | eot | woff | woff2` | global | non | Extensions mises en cache (séparées par ` | `). |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000` | multisite | non      | Valeur de l’en‑tête HTTP Cache-Control.                      |
| `CLIENT_CACHE_ETAG`       | `yes`                      | multisite | non      | Envoi d’un ETag pour les ressources statiques.               |

!!! tip "Optimiser le cache"
    Contenu fréquemment mis à jour : durée plus courte. Contenu versionné ou peu changeant : durée plus longue. La valeur par défaut (180 jours) convient souvent.

### Exemples

=== "Basique"

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Agressif"

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Mixte"

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"
    CLIENT_CACHE_ETAG: "yes"
    ```

## Country

Prise en charge STREAM :white_check_mark:

Le plugin Country active le géo‑blocage et permet de restreindre l’accès selon la localisation géographique des visiteurs. Utile pour la conformité régionale, limiter la fraude associée à des zones à risque et appliquer des restrictions de contenu selon les frontières.

Comment ça marche :

1. À chaque visite, BunkerWeb détermine le pays d’origine via l’adresse IP.
2. Votre configuration définit une liste blanche (autorisés) ou noire (bloqués).
3. En liste blanche : seuls les pays listés sont autorisés.
4. En liste noire : les pays listés sont refusés.
5. Le résultat est mis en cache pour les visites répétées.

### Comment l’utiliser

1. Stratégie : choisir liste blanche (peu de pays autorisés) ou liste noire (bloquer certains pays).
2. Codes pays : ajoutez des codes ISO 3166‑1 alpha‑2 (US, GB, FR) à `WHITELIST_COUNTRY` ou `BLACKLIST_COUNTRY`.
3. Application : une fois configuré, la restriction s’applique à tous les visiteurs.
4. Suivi : consultez la [web UI](web-ui.md) pour les statistiques par pays.

### Paramètres

| Paramètre           | Défaut | Contexte  | Multiple | Description                                                                                           |
| ------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |        | multisite | non      | Liste blanche : codes pays ISO 3166‑1 alpha‑2 séparés par des espaces. Seuls ces pays sont autorisés. |
| `BLACKLIST_COUNTRY` |        | multisite | non      | Liste noire : codes pays ISO 3166‑1 alpha‑2 séparés par des espaces. Ces pays sont bloqués.           |

!!! tip "Liste blanche vs noire"
    Liste blanche : accès restreint à quelques pays. Liste noire : bloquer des régions problématiques et autoriser le reste.

!!! warning "Priorité"
    Si une liste blanche et une liste noire sont définies, la liste blanche a priorité : si le pays n’y figure pas, l’accès est refusé.

!!! info "Détection du pays"
    BunkerWeb utilise la base mmdb [db‑ip lite](https://db-ip.com/db/download/ip-to-country-lite).

### Exemples

=== "Liste blanche uniquement"

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Liste noire uniquement"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "UE uniquement"

    ```yaml
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "Blocage pays à risque"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```

## CrowdSec

Prise en charge STREAM :x:

<figure markdown>
  ![Overview](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

Le plugin CrowdSec intègre BunkerWeb avec le moteur de sécurité CrowdSec, fournissant une couche de protection supplémentaire contre diverses cybermenaces. Ce plugin agit comme un bouncer [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs), refusant les requêtes en fonction des décisions de l'API CrowdSec.

CrowdSec est un moteur de sécurité moderne et open-source qui détecte et bloque les adresses IP malveillantes en se basant sur l'analyse comportementale et l'intelligence collective de sa communauté. Vous pouvez également configurer des [scénarios](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) pour bannir automatiquement les adresses IP en fonction de comportements suspects, bénéficiant ainsi d'une liste noire participative.

**Comment ça marche :**

1. Le moteur CrowdSec analyse les journaux et détecte les activités suspectes sur votre infrastructure.
2. Lorsqu'une activité malveillante est détectée, CrowdSec crée une décision pour bloquer l'adresse IP incriminée.
3. BunkerWeb, agissant comme un bouncer, interroge l'API locale de CrowdSec pour obtenir des décisions concernant les requêtes entrantes.
4. Si l'adresse IP d'un client fait l'objet d'une décision de blocage active, BunkerWeb refuse l'accès aux services protégés.
5. En option, le composant de sécurité applicative (Application Security Component) peut effectuer une inspection approfondie des requêtes pour une sécurité renforcée.

!!! success "Bénéfices clés"

      1. **Sécurité communautaire :** Bénéficiez des renseignements sur les menaces partagés par la communauté des utilisateurs de CrowdSec.
      2. **Analyse comportementale :** Détectez les attaques sophistiquées basées sur des modèles de comportement, et non uniquement sur des signatures.
      3. **Intégration légère :** Impact minimal sur les performances de votre instance BunkerWeb.
      4. **Protection multi-niveaux :** Combinez la défense périmétrique (blocage d'IP) avec la sécurité applicative pour une protection en profondeur.

### Prérequis

- Une API locale CrowdSec accessible par BunkerWeb (généralement l’agent exécuté sur la même machine ou dans le même réseau Docker).
- L’accès aux journaux d’accès de BunkerWeb (`/var/log/bunkerweb/access.log` par défaut) pour que l’agent CrowdSec puisse analyser les requêtes.
- L’accès à `cscli` sur l’hôte CrowdSec afin d’enregistrer la clé du bouncer BunkerWeb.

### Parcours d’intégration

1. Préparer l’agent CrowdSec pour ingérer les journaux BunkerWeb.
2. Configurer BunkerWeb pour interroger l’API locale CrowdSec.
3. Valider le lien via l’API `/crowdsec/ping` ou la carte CrowdSec dans l’interface d’administration.

Les sections suivantes détaillent chacune de ces étapes.

### Étape&nbsp;1 – Préparer CrowdSec à ingérer les journaux BunkerWeb

=== "Docker"
    **Fichier d'acquisition**

    Vous devrez exécuter une instance de CrowdSec et la configurer pour analyser les journaux de BunkerWeb. Utilisez la valeur dédiée `bunkerweb` pour le paramètre `type` dans votre fichier d'acquisition (en supposant que les journaux de BunkerWeb sont stockés tels quels sans données supplémentaires) :

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    Si la collection n'apparaît pas dans le conteneur CrowdSec, exécutez `docker exec -it <crowdsec-container> cscli hub update`, puis redémarrez ce conteneur (`docker restart <crowdsec-container>`) afin que les nouveaux artefacts soient disponibles. Remplacez `<crowdsec-container>` par le nom de votre conteneur CrowdSec.

    **Composant de sécurité applicative (*optionnel*)**

    CrowdSec fournit également un [Composant de sécurité applicative](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) qui peut être utilisé pour protéger votre application contre les attaques. Si vous souhaitez l'utiliser, vous devez créer un autre fichier d'acquisition pour le composant AppSec :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    Pour les intégrations basées sur des conteneurs, nous recommandons de rediriger les journaux du conteneur BunkerWeb vers un service syslog afin que CrowdSec puisse y accéder facilement. Voici un exemple de configuration pour syslog-ng qui stockera les journaux bruts provenant de BunkerWeb dans un fichier local `/var/log/bunkerweb.log` :

    ```syslog
    @version: 4.10

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    Voici le modèle docker-compose que vous pouvez utiliser (n'oubliez pas de mettre à jour la clé du bouncer) :

    ```yaml
    x-bw-env: &bw-env
      # Nous utilisons une ancre pour éviter de répéter les mêmes paramètres pour les deux services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Assurez-vous de définir la bonne plage IP pour que le planificateur puisse envoyer la configuration à l'instance

    services:
      bunkerweb:
        # C'est le nom qui sera utilisé pour identifier l'instance dans le planificateur
        image: bunkerity/bunkerweb:1.6.7~rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Pour le support QUIC / HTTP3
        environment:
          <<: *bw-env # Nous utilisons l'ancre pour éviter de répéter les mêmes paramètres pour tous les services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog # Envoyer les journaux à syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # L'adresse IP du service syslog

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7~rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Assurez-vous de définir le nom correct de l'instance
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # N'oubliez pas de définir un mot de passe plus fort pour la base de données
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # C'est l'adresse de l'API du conteneur CrowdSec dans le même réseau
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # Commentez si vous ne voulez pas utiliser le composant AppSec
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # N'oubliez pas de définir une clé plus forte pour le bouncer
        volumes:
          - bw-storage:/data # Ceci est utilisé pour persister le cache et d'autres données comme les sauvegardes
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Nous définissons la taille maximale des paquets autorisés pour éviter les problèmes avec les grosses requêtes
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

      crowdsec:
        image: crowdsecurity/crowdsec:v1.7.3 # Utilisez la dernière version mais épinglez toujours la version pour une meilleure stabilité/sécurité
        volumes:
          - cs-data:/var/lib/crowdsec/data # Pour persister les données de CrowdSec
          - bw-logs:/var/log:ro # Les journaux de BunkerWeb à analyser par CrowdSec
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # Le fichier d'acquisition pour les journaux de BunkerWeb
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Commentez si vous ne voulez pas utiliser le composant AppSec
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # N'oubliez pas de définir une clé plus forte pour le bouncer
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # Si vous ne voulez pas utiliser le composant AppSec, utilisez plutôt cette ligne
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # Lier aux ports bas
          - NET_BROADCAST  # Envoyer des diffusions
          - NET_RAW  # Utiliser des sockets brutes
          - DAC_READ_SEARCH  # Lire les fichiers en contournant les autorisations
          - DAC_OVERRIDE  # Outrepasser les autorisations de fichiers
          - CHOWN  # Changer le propriétaire
          - SYSLOG  # Écrire dans les journaux système
        volumes:
          - bw-logs:/var/log/bunkerweb # C'est le volume utilisé pour stocker les journaux
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # C'est le fichier de configuration de syslog-ng
        networks:
            bw-universe:
              ipv4_address: 10.20.30.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Assurez-vous de définir la bonne plage IP pour que le planificateur puisse envoyer la configuration à l'instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Linux"

    Vous devez installer CrowdSec et le configurer pour analyser les journaux de BunkerWeb. Suivez la [documentation officielle](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    Pour permettre à CrowdSec d'analyser les journaux de BunkerWeb, ajoutez les lignes suivantes à votre fichier d'acquisition situé à `/etc/crowdsec/acquis.yaml` :

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    Mettez à jour le hub CrowdSec et installez la collection BunkerWeb :

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    Maintenant, ajoutez votre bouncer personnalisé à l'API CrowdSec en utilisant l'outil `cscli` :

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "Clé API"
        Conservez la clé générée par la commande `cscli` ; vous en aurez besoin plus tard.

    Ensuite, redémarrez le service CrowdSec :

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Composant de sécurité applicative (*optionnel*)**

    Si vous souhaitez utiliser le composant AppSec, vous devez créer un autre fichier d'acquisition pour celui-ci, situé à `/etc/crowdsec/acquis.d/appsec.yaml` :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    Vous devrez également installer les collections du composant AppSec :

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Enfin, redémarrez le service CrowdSec :

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Paramètres**

    Configurez le plugin en ajoutant les paramètres suivants à votre fichier de configuration BunkerWeb :

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<La clé fournie par cscli>
    # Commentez si vous ne voulez pas utiliser le composant AppSec
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    Enfin, rechargez le service BunkerWeb :

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "All-in-one"

    L'image Docker BunkerWeb All-In-One (AIO) est livrée avec CrowdSec entièrement intégré. Vous n'avez pas besoin de configurer une instance CrowdSec séparée ou de configurer manuellement les fichiers d'acquisition pour les journaux de BunkerWeb lorsque vous utilisez l'agent CrowdSec interne.

    Référez-vous à la [documentation d'intégration de l'image All-In-One (AIO)](integrations.md#crowdsec-integration).

### Étape&nbsp;2 – Configurer les paramètres de BunkerWeb

Appliquez les variables d’environnement suivantes (ou leurs équivalents via le scheduler) pour permettre à votre instance BunkerWeb de communiquer avec l’API locale CrowdSec. Au minimum, `USE_CROWDSEC`, `CROWDSEC_API` et une clé valide générée avec `cscli bouncers add` sont nécessaires.

| Paramètre                   | Valeur par défaut      | Contexte  | Multiple | Description                                                                                                                                    |
| --------------------------- | ---------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Activer CrowdSec :** Mettre à `yes` pour activer le bouncer CrowdSec.                                                                        |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | no       | **URL de l'API CrowdSec :** L'adresse du service de l'API locale de CrowdSec.                                                                  |
| `CROWDSEC_API_KEY`          |                        | global    | no       | **Clé API CrowdSec :** La clé API pour s'authentifier auprès de l'API CrowdSec, obtenue avec `cscli bouncers add`.                             |
| `CROWDSEC_MODE`             | `live`                 | global    | no       | **Mode de fonctionnement :** Soit `live` (interroge l'API pour chaque requête) ou `stream` (met en cache périodiquement toutes les décisions). |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | no       | **Trafic interne :** Mettre à `yes` pour vérifier le trafic interne par rapport aux décisions de CrowdSec.                                     |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | no       | **Délai d'attente de la requête :** Délai d'attente en millisecondes pour les requêtes HTTP vers l'API locale de CrowdSec en mode live.        |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | no       | **Emplacements exclus :** Liste d'emplacements (URI) séparés par des virgules à exclure des vérifications de CrowdSec.                         |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | no       | **Expiration du cache :** Le temps d'expiration du cache en secondes pour les décisions IP en mode live.                                       |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | no       | **Fréquence de mise à jour :** À quelle fréquence (en secondes) récupérer les décisions nouvelles/expirées de l'API CrowdSec en mode stream.   |

#### Paramètres du composant de sécurité applicative

| Paramètre                         | Valeur par défaut | Contexte | Multiple | Description                                                                                                                      |
| --------------------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |                   | global   | no       | **URL AppSec :** L'URL du composant de sécurité applicative de CrowdSec. Laisser vide pour désactiver AppSec.                    |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough`     | global   | no       | **Action en cas d'échec :** Action à entreprendre lorsque AppSec renvoie une erreur. Peut être `passthrough` ou `deny`.          |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`             | global   | no       | **Délai de connexion :** Le délai d'attente en millisecondes pour se connecter au composant AppSec.                              |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`             | global   | no       | **Délai d'envoi :** Le délai d'attente en millisecondes pour envoyer des données au composant AppSec.                            |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`             | global   | no       | **Délai de traitement :** Le délai d'attente en millisecondes pour traiter la requête dans le composant AppSec.                  |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`              | global   | no       | **Toujours envoyer :** Mettre à `yes` pour toujours envoyer les requêtes à AppSec, même s'il y a une décision au niveau de l'IP. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`              | global   | no       | **Vérification SSL :** Mettre à `yes` pour vérifier le certificat SSL du composant AppSec.                                       |

!!! info "À propos des modes de fonctionnement" - Le **mode Live** interroge l'API CrowdSec pour chaque requête entrante, offrant une protection en temps réel au prix d'une latence plus élevée. - Le **mode Stream** télécharge périodiquement toutes les décisions de l'API CrowdSec et les met en cache localement, réduisant la latence avec un léger retard dans l'application des nouvelles décisions.

### Exemples de configurations

=== "Configuration de base"

    C'est une configuration simple pour lorsque CrowdSec s'exécute sur le même hôte :

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "live"
    ```

=== "Configuration avancée avec AppSec"

    Une configuration plus complète incluant le composant de sécurité applicative :

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # Configuration AppSec
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

### Étape&nbsp;3 – Valider l’intégration

- Dans les journaux du planificateur, recherchez les entrées `CrowdSec configuration successfully generated` et `CrowdSec bouncer denied request` afin de vérifier que le plugin est actif.
- Côté CrowdSec, surveillez `cscli metrics show` ou la console CrowdSec pour vous assurer que les décisions BunkerWeb apparaissent comme prévu.
- Dans l’interface BunkerWeb, ouvrez la page du plugin CrowdSec pour voir l’état de l’intégration.

## Custom Pages <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :x:

Tweak BunkerWeb error/antibot/default pages with custom HTML.

| Paramètre                        | Valeur par défaut | Contexte  | Multiple | Description                                                                                                        |
| -------------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| `CUSTOM_ERROR_PAGE`              |                   | multisite | non      | Full path of the custom error page (must be readable by the scheduler) (Can be a lua template).                    |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |                   | global    | non      | Full path of the custom default server page (must be readable by the scheduler) (Can be a lua template).           |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |                   | multisite | non      | Full path of the custom antibot captcha page (must be readable by the scheduler) (Can be a lua template).          |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |                   | multisite | non      | Full path of the custom antibot javascript check page (must be readable by the scheduler) (Can be a lua template). |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |                   | multisite | non      | Full path of the custom antibot recaptcha page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |                   | multisite | non      | Full path of the custom antibot hcaptcha page (must be readable by the scheduler) (Can be a lua template).         |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |                   | multisite | non      | Full path of the custom antibot turnstile page (must be readable by the scheduler) (Can be a lua template).        |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |                   | multisite | non      | Full path of the custom antibot mcaptcha page (must be readable by the scheduler) (Can be a lua template).         |

## Custom SSL certificate

Prise en charge STREAM :white_check_mark:

Le plugin Certificat SSL personnalisé permet d’utiliser vos propres certificats SSL/TLS avec BunkerWeb, au lieu de ceux générés automatiquement. Utile si vous possédez déjà des certificats d’une AC de confiance, avez des besoins spécifiques ou centralisez la gestion des certificats.

Comment ça marche :

1. Vous fournissez le certificat et la clé privée (chemins de fichiers ou données en base64/PEM).
2. BunkerWeb valide le format et l’utilisabilité des fichiers.
3. Lors d’une connexion sécurisée, BunkerWeb sert votre certificat personnalisé.
4. La validité est surveillée et des alertes sont émises avant expiration.
5. Vous gardez le contrôle total sur le cycle de vie des certificats.

!!! info "Surveillance automatique"
    Avec `USE_CUSTOM_SSL: yes`, BunkerWeb surveille le certificat `CUSTOM_SSL_CERT`, détecte les changements et recharge NGINX si nécessaire.

### Comment l’utiliser

1. Activer : `USE_CUSTOM_SSL: yes`.
2. Méthode : fichiers vs données, priorité via `CUSTOM_SSL_CERT_PRIORITY`.
3. Fichiers : fournissez les chemins du certificat et de la clé privée.
4. Données : fournissez les chaînes base64 ou PEM en clair.

!!! tip "Mode stream"
    En mode stream, configurez `LISTEN_STREAM_PORT_SSL` pour le port SSL/TLS.

### Paramètres

| Paramètre                  | Défaut | Contexte  | Multiple | Description                                                   |
| -------------------------- | ------ | --------- | -------- | ------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`   | multisite | non      | Activer l’usage d’un certificat personnalisé.                 |
| `CUSTOM_SSL_CERT_PRIORITY` | `file` | multisite | non      | Priorité des sources : `file` (fichiers) ou `data` (données). |
| `CUSTOM_SSL_CERT`          |        | multisite | non      | Chemin complet vers le certificat (ou bundle).                |
| `CUSTOM_SSL_KEY`           |        | multisite | non      | Chemin complet vers la clé privée.                            |
| `CUSTOM_SSL_CERT_DATA`     |        | multisite | non      | Données du certificat (base64 ou PEM en clair).               |
| `CUSTOM_SSL_KEY_DATA`      |        | multisite | non      | Données de la clé privée (base64 ou PEM en clair).            |

!!! warning "Sécurité"
    Protégez la clé privée (droits adaptés, lisible par le scheduler BunkerWeb uniquement).

!!! tip "Format"
    Les certificats doivent être au format PEM. Convertissez si nécessaire.

!!! info "Chaînes de certification"
    Si une chaîne intermédiaire est nécessaire, fournissez le bundle complet dans l’ordre (certificat puis intermédiaires).

### Exemples

=== "Fichiers"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "Données base64"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```

=== "PEM en clair"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
    -----BEGIN CERTIFICATE-----
    MIIDdzCCAl+gAwIBAgIUJH...certificate content...AAAA
    -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
    -----BEGIN PRIVATE KEY-----
    MIIEvQIBADAN...key content...AAAA
    -----END PRIVATE KEY-----
    ```

=== "Fallback"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```

## DNSBL

Prise en charge STREAM :white_check_mark:

Le plugin DNSBL (Domain Name System Blacklist) protège contre les IP malveillantes connues en vérifiant l’adresse IP du client auprès de serveurs DNSBL externes. Cette fonctionnalité aide à se prémunir du spam, des botnets et de diverses menaces en s’appuyant on des listes communautaires d’IP problématiques.

**Comment ça marche :**

1.  Lorsqu’un client se connecte à votre site, BunkerWeb interroge les serveurs DNSBL que vous avez choisis via le protocole DNS.
2.  La vérification s’effectue en envoyant une requête DNS inversée à chaque serveur DNSBL avec l’IP du client.
3.  Si un serveur DNSBL confirme que l’IP du client est listée comme malveillante, BunkerWeb bannit automatiquement ce client, empêchant les menaces potentielles d’atteindre votre application.
4.  Les résultats sont mis en cache pour améliorer les performances pour les visites répétées depuis la même IP.
5.  Les recherches sont asynchrones pour minimiser l’impact sur le temps de chargement.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité DNSBL :

1.  **Activer la fonction :** La fonction DNSBL est désactivée par défaut. Passez `USE_DNSBL` à `yes` pour l'activer.
2.  **Configurer les serveurs DNSBL :** Ajoutez les noms de domaine des services DNSBL que vous souhaitez utiliser dans le paramètre `DNSBL_LIST`.
3.  **Appliquer les paramètres :** Une fois configuré, BunkerWeb vérifiera automatiquement les connexions entrantes auprès des serveurs DNSBL spécifiés.
4.  **Surveiller l'efficacité :** Consultez la [web UI](web-ui.md) pour voir les statistiques des requêtes bloquées par les vérifications DNSBL.

### Paramètres de configuration

**Général**

| Paramètre    | Défaut                                              | Contexte  | Multiple | Description                                                                                        |
| ------------ | --------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | non      | Activer DNSBL : mettre à `yes` pour activer les vérifications DNSBL pour les connexions entrantes. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | non      | Serveurs DNSBL : liste des domaines de serveurs DNSBL à vérifier, séparés par des espaces.         |

**Listes d’exception**

| Paramètre              | Défaut | Contexte  | Multiple | Description                                                                                         |
| ---------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``     | multisite | oui      | IP/CIDR séparés par des espaces pour lesquels ignorer les vérifications DNSBL (liste blanche).      |
| `DNSBL_IGNORE_IP_URLS` | ``     | multisite | oui      | URL séparées par des espaces fournissant des IP/CIDR à ignorer. Supporte `http(s)://` et `file://`. |

!!! tip "Choisir des serveurs DNSBL"
    Choisissez des fournisseurs DNSBL réputés pour minimiser les faux positifs. La liste par défaut inclut des services bien établis qui conviennent à la plupart des sites web :

    - **bl.blocklist.de :** Liste les IP qui ont été détectées en train d'attaquer d'autres serveurs.
    - **sbl.spamhaus.org :** Se concentre sur les sources de spam et autres activités malveillantes.
    - **xbl.spamhaus.org :** Cible les systèmes infectés, tels que les machines compromises ou les proxys ouverts.

!!! info "Principe de fonctionnement de DNSBL"
    Les serveurs DNSBL fonctionnent en répondant à des requêtes DNS spécialement formatées. Lorsque BunkerWeb vérifie une adresse IP, il inverse l'IP et y ajoute le nom de domaine du DNSBL. Si la requête DNS résultante renvoie une réponse de « succès », l'IP est considérée comme étant sur la liste noire.

!!! warning "Considérations sur la performance"
    Bien que BunkerWeb optimise les recherches DNSBL pour la performance, l'ajout d'un grand nombre de serveurs DNSBL pourrait potentiellement impacter les temps de réponse. Commencez avec quelques serveurs DNSBL réputés et surveillez la performance avant d'en ajouter d'autres.

### Exemples de configuration

=== "Configuration de base"

    Une configuration simple utilisant les serveurs DNSBL par défaut :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Configuration minimale"

    Une configuration minimale se concentrant sur les services DNSBL les plus fiables :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    Cette configuration utilise uniquement :

    - **zen.spamhaus.org** : La liste combinée de Spamhaus est souvent considérée comme suffisante en tant que solution autonome en raison de sa large couverture et de sa réputation de précision. Elle combine les listes SBL, XBL et PBL en une seule requête, la rendant efficace et complète.

=== "Exclure des IP de confiance"

    Vous pouvez exclure certains clients des vérifications DNSBL via des valeurs statiques et/ou des fichiers distants :

    - `DNSBL_IGNORE_IP` : Ajoutez des IP et des plages CIDR séparées par des espaces. Exemple : `192.0.2.10 203.0.113.0/24 2001:db8::/32`.
    - `DNSBL_IGNORE_IP_URLS` : Fournissez des URL dont le contenu liste une IP/CIDR par ligne. Les commentaires commençant par `#` ou `;` sont ignorés. Les entrées en double sont dédupliquées.

    Quand une IP cliente correspond à la liste d’exclusion, BunkerWeb saute les requêtes DNSBL et met en cache le résultat « ok » pour accélérer les requêtes suivantes.

=== "Utiliser des URL distantes"

    La tâche `dnsbl-download` télécharge et met en cache les IP à ignorer toutes les heures :

    - Protocoles : `https://`, `http://` et chemins locaux `file://`.
    - Un cache par URL avec une somme de contrôle empêche les téléchargements redondants (délai de grâce d'1 heure).
    - Fichier fusionné par service : `/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`.
    - Chargé au démarrage et fusionné avec `DNSBL_IGNORE_IP`.

    Exemple combinant des sources statiques et des URL :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://exemple.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "Utiliser des fichiers locaux"

    Chargez des IP à ignorer depuis des fichiers locaux en utilisant des URL `file://` :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```

## Database

Prise en charge STREAM :white_check_mark:

Le plugin Base de données fournit une intégration robuste pour BunkerWeb en permettant le stockage centralisé et la gestion des données de configuration, des journaux et d’autres informations essentielles.

Ce composant cœur prend en charge plusieurs moteurs : SQLite, PostgreSQL, MySQL/MariaDB et Oracle, afin de choisir la solution la mieux adaptée à votre environnement et à vos besoins.

Comment ça marche :

1. BunkerWeb se connecte à la base configurée via une URI au format SQLAlchemy.
2. Les données de configuration critiques, les informations d’exécution et les journaux des jobs sont stockés de manière sécurisée en base.
3. Des tâches de maintenance automatiques optimisent la base en gérant la croissance et en purgeant les enregistrements excédentaires.
4. Pour la haute disponibilité, vous pouvez configurer une URI en lecture seule servant de bascule et/ou pour délester les lectures.
5. Les opérations base de données sont journalisées selon le niveau de log spécifié, offrant la visibilité adaptée.

### Comment l’utiliser

Étapes pour configurer la base de données :

1. Choisir un moteur : SQLite (par défaut), PostgreSQL, MySQL/MariaDB ou Oracle.
2. Configurer l’URI : renseignez `DATABASE_URI` (format SQLAlchemy) pour la base principale.
3. Optionnel : `DATABASE_URI_READONLY` pour les opérations en lecture seule ou en secours.

### Paramètres

| Paramètre                       | Défaut                                    | Contexte | Multiple | Description                                                                    |
| ------------------------------- | ----------------------------------------- | -------- | -------- | ------------------------------------------------------------------------------ |
| `DATABASE_URI`                  | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global   | non      | URI principale de connexion (format SQLAlchemy).                               |
| `DATABASE_URI_READONLY`         |                                           | global   | non      | URI optionnelle en lecture seule (offload/HA).                                 |
| `DATABASE_LOG_LEVEL`            | `warning`                                 | global   | non      | Niveau de verbosité des logs DB : `debug`, `info`, `warn`, `warning`, `error`. |
| `DATABASE_MAX_JOBS_RUNS`        | `10000`                                   | global   | non      | Nombre max d’entrées de runs de jobs conservées avant purge automatique.       |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                                      | global   | non      | Durée max de conservation des sessions UI (en jours) avant purge automatique.  |

!!! tip "Choix du moteur" - SQLite (défaut) : simple et fichier unique, idéal mono‑nœud/tests. - PostgreSQL : recommandé en production multi‑instances (robustesse, concurrence). - MySQL/MariaDB : alternative solide aux capacités proches de PostgreSQL. - Oracle : adapté aux environnements d’entreprise standardisés sur Oracle.

!!! info "Format SQLAlchemy" - SQLite : `sqlite:////chemin/vers/database.sqlite3` - PostgreSQL : `postgresql://user:password@hôte:port/base` - MySQL/MariaDB : `mysql://user:password@hôte:port/base` ou `mariadb://user:password@hôte:port/base` - Oracle : `oracle://user:password@hôte:port/base`

!!! warning "Maintenance"
    Des tâches quotidiennes assurent la maintenance automatique :

- **Purge des runs de jobs excédentaires** : supprime l’historique au-delà de `DATABASE_MAX_JOBS_RUNS`.
- **Purge des sessions UI expirées** : enlève les sessions plus anciennes que `DATABASE_MAX_SESSION_AGE_DAYS`.

Ces jobs évitent la croissance illimitée tout en conservant un historique d’exploitation pertinent.

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :x:

Provides a simpler way to fix false positives in reports.

## Errors

Prise en charge STREAM :x:

Le plugin Errors fournit une gestion personnalisable des erreurs HTTP, afin de définir l’apparence des réponses d’erreur pour vos utilisateurs. Vous pouvez ainsi afficher des pages d’erreur claires et cohérentes avec votre identité, plutôt que les pages techniques par défaut du serveur.

Comment ça marche :

1. Quand une erreur HTTP survient (ex. 400, 404, 500), BunkerWeb intercepte la réponse.
2. À la place de la page par défaut, BunkerWeb affiche une page personnalisée et soignée.
3. Les pages d’erreur sont configurables : vous pouvez fournir un fichier HTML par code d’erreur. Les fichiers doivent être placés dans le répertoire défini par `ROOT_FOLDER` (voir le plugin Misc).
   - Par défaut, `ROOT_FOLDER` vaut `/var/www/html/{server_name}`.
   - En mode multisite, chaque site a son propre `ROOT_FOLDER` ; placez les pages d’erreur dans le dossier correspondant à chaque site.
4. Les pages par défaut expliquent clairement le problème et suggèrent des actions possibles.

### Comment l’utiliser

1. Définir les pages personnalisées : utilisez `ERRORS` pour associer des codes HTTP à des fichiers HTML (dans `ROOT_FOLDER`).
2. Configurer vos pages : utilisez celles de BunkerWeb par défaut ou vos propres fichiers.
3. Définir les codes interceptés : avec `INTERCEPTED_ERROR_CODES`, choisissez les codes toujours gérés par BunkerWeb.
4. Laissez BunkerWeb faire le reste : la gestion d’erreurs sera appliquée automatiquement.

### Paramètres

| Paramètre                 | Défaut                                            | Contexte  | Multiple | Description                                                                                                  |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `ERRORS`                  |                                                   | multisite | non      | Pages d’erreur personnalisées : paires `CODE=/chemin/page.html`.                                             |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | non      | Codes interceptés : liste de codes gérés avec la page par défaut si aucune page personnalisée n’est définie. |

!!! tip "Conception des pages"
    Les pages par défaut sont claires et pédagogiques : description de l’erreur, causes possibles, actions suggérées et repères visuels.

!!! info "Types d’erreurs" - 4xx (côté client) : requêtes invalides, ressource inexistante, authentification manquante… - 5xx (côté serveur) : impossibilité de traiter une requête valide (erreur interne, indisponibilité temporaire…).

### Exemples

=== "Gestion par défaut"

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Pages personnalisées"

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Gestion sélective"

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```

## Greylist

Prise en charge STREAM :warning:

Le plugin Greylist adopte une approche flexible : il autorise l’accès aux visiteurs correspondant à des critères donnés tout en maintenant les contrôles de sécurité. Contrairement aux listes noire/blanche, il crée un juste milieu.

Comment ça marche :

1. Vous définissez des critères (IP, réseaux, rDNS, ASN, User‑Agent, motifs d’URI).
2. Un visiteur qui correspond est autorisé, mais reste soumis aux autres contrôles.
3. S’il ne correspond à aucun critère greylist, l’accès est refusé.
4. Des sources externes peuvent alimenter automatiquement la liste.

### Comment l’utiliser

1. Activer : `USE_GREYLIST: yes`.
2. Règles : définissez IP/réseaux, rDNS, ASN, User‑Agent ou URIs.
3. Sources externes : optionnel, configurez des URLs pour mises à jour.
4. Suivi : consultez la [web UI](web-ui.md).

!!! tip "Comportement d’accès" - Visiteurs greylist : accès autorisé mais contrôles appliqués. - Autres visiteurs : accès refusé.

!!! info "Mode stream"
    En mode stream, seuls IP, rDNS et ASN sont pris en compte.

### Paramètres

Général

| Paramètre      | Défaut | Contexte  | Multiple | Description          |
| -------------- | ------ | --------- | -------- | -------------------- |
| `USE_GREYLIST` | `no`   | multisite | non      | Activer la greylist. |

=== "Adresse IP"

    | Paramètre          | Défaut | Contexte  | Multiple | Description                                                    |
    | ------------------ | ------ | --------- | -------- | -------------------------------------------------------------- |
    | `GREYLIST_IP`      |        | multisite | non      | Liste d’IP/réseaux (CIDR) à greylist, séparés par des espaces. |
    | `GREYLIST_IP_URLS` |        | multisite | non      | URLs contenant des IP/réseaux à greylist.                      |

=== "Reverse DNS"

    | Paramètre              | Défaut | Contexte  | Multiple | Description                                  |
    | ---------------------- | ------ | --------- | -------- | -------------------------------------------- |
    | `GREYLIST_RDNS`        |        | multisite | non      | Suffixes de DNS inversés à greylist.         |
    | `GREYLIST_RDNS_GLOBAL` | `yes`  | multisite | non      | Vérifier seulement les IP globales si `yes`. |
    | `GREYLIST_RDNS_URLS`   |        | multisite | non      | URLs contenant des suffixes rDNS à greylist. |

=== "ASN"

    | Paramètre           | Défaut | Contexte  | Multiple | Description                                        |
    | ------------------- | ------ | --------- | -------- | -------------------------------------------------- |
    | `GREYLIST_ASN`      |        | multisite | non      | Numéros d’AS à greylist (séparés par des espaces). |
    | `GREYLIST_ASN_URLS` |        | multisite | non      | URLs contenant des AS à greylist.                  |

=== "User‑Agent"

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                        |
    | -------------------------- | ------ | --------- | -------- | -------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |        | multisite | non      | Motifs (regex PCRE) d’User‑Agent à greylist.       |
    | `GREYLIST_USER_AGENT_URLS` |        | multisite | non      | URLs contenant des motifs d’User‑Agent à greylist. |

=== "URI"

    | Paramètre           | Défaut | Contexte  | Multiple | Description                                 |
    | ------------------- | ------ | --------- | -------- | ------------------------------------------- |
    | `GREYLIST_URI`      |        | multisite | non      | Motifs d’URI (regex PCRE) à greylist.       |
    | `GREYLIST_URI_URLS` |        | multisite | non      | URLs contenant des motifs d’URI à greylist. |

!!! info "Format d’URL"
    Les paramètres `*_URLS` supportent HTTP/HTTPS et `file:///`. Auth basique possible avec `http://user:pass@url`.

!!! tip "Mises à jour"
    Les listes récupérées par URL sont mises à jour automatiquement toutes les heures.

### Travailler avec des fichiers de listes locaux

Les paramètres `*_URLS` fournis par les plugins Whitelist, Greylist et Blacklist utilisent le même téléchargeur. Lorsque vous référencez une URL `file:///` :

- Le chemin est résolu dans le conteneur du **scheduler** (dans un déploiement Docker il s’agit généralement de `bunkerweb-scheduler`). Montez-y vos fichiers et vérifiez que l’utilisateur scheduler possède un accès en lecture.
- Chaque fichier est un texte encodé en UTF-8 avec une entrée par ligne. Les lignes vides sont ignorées et les commentaires doivent commencer par `#` ou `;`. Les commentaires `//` ne sont pas pris en charge.
- Valeur attendue selon le type de liste :
  - **Listes IP** acceptent des adresses IPv4/IPv6 ou des réseaux CIDR (par exemple `192.0.2.10` ou `2001:db8::/48`).
  - **Listes rDNS** attendent un suffixe sans espaces (par exemple `.search.msn.com`). Les valeurs sont automatiquement converties en minuscules.
  - **Listes ASN** peuvent contenir uniquement le numéro (`32934`) ou le numéro préfixé par `AS` (`AS15169`).
  - **Listes User-Agent** sont traitées comme des motifs PCRE et la ligne complète est conservée (espaces compris). Placez vos commentaires sur une ligne séparée pour éviter qu’ils ne soient interprétés comme motif.
  - **Listes URI** doivent commencer par `/` et peuvent utiliser des jetons PCRE tels que `^` ou `$`.

Exemples de fichiers conformes :

```text
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```

## Gzip

Prise en charge STREAM :x:

Le plugin GZIP compresse les réponses HTTP avec l’algorithme gzip pour réduire la bande passante et accélérer le chargement des pages.

### Fonctionnement

1. BunkerWeb détecte si le client supporte gzip.
2. Si oui, la réponse est compressée au niveau configuré.
3. Les en‑têtes indiquent l’usage de gzip.
4. Le navigateur décompresse avant l’affichage.

### Comment l’utiliser

1. Activer : `USE_GZIP: yes` (désactivé par défaut).
2. Types MIME : définir `GZIP_TYPES`.
3. Taille minimale : `GZIP_MIN_LENGTH` pour éviter les très petits fichiers.
4. Niveau de compression : `GZIP_COMP_LEVEL` (1–9).
5. Contenu proxifié : ajuster `GZIP_PROXIED`.

### Paramètres

| Paramètre         | Défaut                                                                                                                                                                                                                                                                                                                                                                                                                           | Contexte  | Multiple | Description                                                                             |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | non      | Activer la compression gzip.                                                            |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | non      | Types MIME compressés.                                                                  |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | non      | Taille minimale (octets) pour appliquer la compression.                                 |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | non      | Niveau 1–9 : plus haut = meilleure compression mais plus de CPU.                        |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | non      | Précise quels contenus proxifiés doivent être compressés selon les en‑têtes de réponse. |

!!! tip "Niveau de compression"
    `5` est un bon compromis. Statique/CPU dispo : 7–9. Dynamique/CPU limité : 1–3.

### Exemples

=== "Basique"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Compression maximale"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Performance équilibrée"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Contenu proxifié"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```

## HTML injection

Prise en charge STREAM :x:

Le plugin d’injection HTML permet d’ajouter du code HTML personnalisé dans les pages de votre site juste avant `</body>` ou `</head>`. Idéal pour intégrer des scripts d’analytics, pixels de tracking, JS/CSS personnalisés ou des intégrations tierces sans modifier le code source de votre application.

Comment ça marche :

1. À la livraison d’une page, BunkerWeb inspecte la réponse HTML.
2. Si l’injection « body » est configurée, il insère votre HTML juste avant `</body>`.
3. Si l’injection « head » est configurée, il insère votre HTML juste avant `</head>`.
4. L’insertion s’applique automatiquement à toutes les pages HTML servies.

### Comment l’utiliser

1. Préparez votre HTML personnalisé.
2. Choisissez l’emplacement : `<head>`, `<body>`, ou les deux.
3. Renseignez `INJECT_HEAD` et/ou `INJECT_BODY` avec votre code.

### Paramètres

| Paramètre     | Défaut | Contexte  | Multiple | Description                        |
| ------------- | ------ | --------- | -------- | ---------------------------------- |
| `INJECT_HEAD` |        | multisite | non      | Code HTML injecté avant `</head>`. |
| `INJECT_BODY` |        | multisite | non      | Code HTML injecté avant `</body>`. |

!!! tip "Bonnes pratiques" - Placez de préférence les scripts JS en fin de body pour éviter de bloquer le rendu. - Mettez le CSS et le JS critique dans le head pour éviter le flash de contenu non stylé. - Attention au contenu injecté qui pourrait casser le site.

### Exemples

=== "Google Analytics"

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: '<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag(''js'', new Date());gtag(''config'', ''G-XXXXXXXXXX'');</script>'
    ```

=== "Styles personnalisés"

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Intégrations multiples"

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: '<script src="https://cdn.example.com/js/widget.js"></script><script>initializeWidget(''your-api-key'');</script>'
    ```

=== "Bandeau cookies"

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: '<div id="cookie-banner" class="cookie-banner">This website uses cookies to ensure you get the best experience. <button onclick="acceptCookies()">Accept</button></div><script>function acceptCookies() { document.getElementById(''cookie-banner'').style.display = ''none''; localStorage.setItem(''cookies-accepted'', ''true''); } if(localStorage.getItem(''cookies-accepted'') === ''true'') { document.getElementById(''cookie-banner'').style.display = ''none''; }</script>'
    ```

## Headers

Prise en charge STREAM :x:

Les en-têtes HTTP jouent un rôle crucial dans la sécurité. Le plugin Headers offre une gestion robuste des en-têtes HTTP standards et personnalisés, améliorant ainsi la sécurité et les fonctionnalités. Il applique dynamiquement des mesures de sécurité, telles que [HSTS](https://developer.mozilla.org/fr/docs/Web/HTTP/Headers/Strict-Transport-Security), [CSP](https://developer.mozilla.org/fr/docs/Web/HTTP/Headers/Content-Security-Policy) (y compris un mode de rapport seul), et l'injection d'en-têtes personnalisés, tout en empêchant les fuites d'informations.

**Comment ça marche**

1. Lorsqu'un client demande du contenu depuis votre site web, BunkerWeb traite les en-têtes de la réponse.
2. Les en-têtes de sécurité sont appliqués conformément à votre configuration.
3. Des en-têtes personnalisés peuvent être ajoutés pour fournir des informations ou des fonctionnalités supplémentaires aux clients.
4. Les en-têtes indésirables qui pourraient révéler des informations sur le serveur sont automatiquement supprimés.
5. Les cookies sont modifiés pour inclure les attributs de sécurité appropriés en fonction de vos paramètres.
6. Les en-têtes des serveurs en amont peuvent être préservés de manière sélective lorsque cela est nécessaire.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Headers :

1.  **Configurer les en-têtes de sécurité :** Définissez des valeurs pour les en-têtes courants.
2.  **Ajouter des en-têtes personnalisés :** Définissez les en-têtes personnalisés à l'aide du paramètre `CUSTOM_HEADER`.
3.  **Supprimer les en-têtes indésirables :** Utilisez `REMOVE_HEADERS` pour vous assurer que les en-têtes qui pourraient exposer des détails sur le serveur sont supprimés.
4.  **Définir la sécurité des cookies :** Activez une sécurité robuste des cookies en configurant `COOKIE_FLAGS` et en réglant `COOKIE_AUTO_SECURE_FLAG` sur `yes` pour que l'attribut Secure soit automatiquement ajouté sur les connexions HTTPS.
5.  **Préserver les en-têtes en amont :** Spécifiez les en-têtes en amont à conserver en utilisant `KEEP_UPSTREAM_HEADERS`.
6.  **Tirer parti de l'application conditionnelle des en-têtes :** Si vous souhaitez tester des politiques sans interruption, activez le mode [CSP Report-Only](https://developer.mozilla.org/fr/docs/Web/HTTP/Headers/Content-Security-Policy-Report-Only) via `CONTENT_SECURITY_POLICY_REPORT_ONLY`.

### Guide de configuration

=== "En-têtes de sécurité"

    **Aperçu**

    Les en-têtes de sécurité renforcent la communication sécurisée, restreignent le chargement des ressources et préviennent les attaques comme le clickjacking et l'injection. Des en-têtes correctement configurés créent une couche de défense robuste pour votre site web.

    !!! success "Avantages des en-têtes de sécurité"
        - **HSTS :** Assure que toutes les connexions sont chiffrées, protégeant contre les attaques de rétrogradation de protocole.
        - **CSP :** Empêche l'exécution de scripts malveillants, réduisant le risque d'attaques XSS.
        - **X-Frame-Options :** Bloque les tentatives de clickjacking en contrôlant l'intégration des iframes.
        - **Referrer Policy :** Limite les fuites d'informations sensibles via les en-têtes referrer.

    | Paramètre                             | Défaut                                                                                              | Contexte  | Multiple | Description                                                                                                                                               |
    | ------------------------------------- | --------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `STRICT_TRANSPORT_SECURITY`           | `max-age=63072000; includeSubDomains; preload`                                                      | multisite | non      | **HSTS :** Force les connexions HTTPS sécurisées, réduisant les risques d'attaques de type "man-in-the-middle".                                           |
    | `CONTENT_SECURITY_POLICY`             | `object-src 'none'; form-action 'self'; frame-ancestors 'self';`                                    | multisite | non      | **CSP :** Restreint le chargement des ressources aux sources de confiance, atténuant les attaques de type cross-site scripting et d'injection de données. |
    | `CONTENT_SECURITY_POLICY_REPORT_ONLY` | `no`                                                                                                | multisite | non      | **Mode rapport CSP :** Signale les violations sans bloquer le contenu, aidant à tester les politiques de sécurité tout en capturant les journaux.         |
    | `X_FRAME_OPTIONS`                     | `SAMEORIGIN`                                                                                        | multisite | non      | **X-Frame-Options :** Empêche le clickjacking en contrôlant si votre site peut être intégré dans une frame.                                               |
    | `X_CONTENT_TYPE_OPTIONS`              | `nosniff`                                                                                           | multisite | non      | **X-Content-Type-Options :** Empêche les navigateurs de "MIME-sniffer", protégeant contre les attaques de type "drive-by download".                       |
    | `X_DNS_PREFETCH_CONTROL`              | `off`                                                                                               | multisite | non      | **X-DNS-Prefetch-Control :** Régule le préchargement DNS pour réduire les requêtes réseau involontaires et améliorer la confidentialité.                  |
    | `REFERRER_POLICY`                     | `strict-origin-when-cross-origin`                                                                   | multisite | non      | **Politique de Referrer :** Contrôle la quantité d'informations de référent envoyées, protégeant la vie privée de l'utilisateur.                          |
    | `PERMISSIONS_POLICY`                  | `accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), ...` | multisite | non      | **Politique de permissions :** Restreint l'accès aux fonctionnalités du navigateur, réduisant les vecteurs d'attaque potentiels.                          |
    | `KEEP_UPSTREAM_HEADERS`               | `Content-Security-Policy Permissions-Policy X-Frame-Options`                                        | multisite | non      | **Conserver les en-têtes :** Préserve les en-têtes en amont sélectionnés, facilitant l'intégration héritée tout en maintenant la sécurité.                |

    !!! tip "Bonnes pratiques"
        - Révisez et mettez à jour régulièrement vos en-têtes de sécurité pour vous conformer aux normes de sécurité en constante évolution.
        - Utilisez des outils comme [Mozilla Observatory](https://observatory.mozilla.org/) pour valider la configuration de vos en-têtes.
        - Testez la CSP en mode `Report-Only` avant de l'appliquer pour éviter de casser des fonctionnalités.

=== "Paramètres des cookies"

    **Aperçu**

    Des paramètres de cookies appropriés garantissent la sécurité des sessions utilisateur en empêchant le détournement, la fixation et le cross-site scripting. Les cookies sécurisés maintiennent l'intégrité de la session sur HTTPS et améliorent la protection globale des données des utilisateurs.

    !!! success "Avantages des cookies sécurisés"
        - **Attribut HttpOnly :** Empêche les scripts côté client d'accéder aux cookies, atténuant les risques XSS.
        - **Attribut SameSite :** Réduit les attaques CSRF en restreignant l'utilisation des cookies inter-origines.
        - **Attribut Secure :** Assure que les cookies ne sont transmis que sur des connexions HTTPS chiffrées.

    | Paramètre                 | Défaut                    | Contexte  | Multiple | Description                                                                                                                                                                                   |
    | ------------------------- | ------------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `COOKIE_FLAGS`            | `* HttpOnly SameSite=Lax` | multisite | oui      | **Attributs de cookie :** Ajoute automatiquement des attributs de sécurité tels que HttpOnly et SameSite, protégeant les cookies de l'accès par des scripts côté client et des attaques CSRF. |
    | `COOKIE_AUTO_SECURE_FLAG` | `yes`                     | multisite | non      | **Attribut Secure automatique :** Assure que les cookies ne sont envoyés que sur des connexions HTTPS sécurisées en ajoutant automatiquement l'attribut Secure.                               |

    !!! tip "Bonnes pratiques"
        - Utilisez `SameSite=Strict` pour les cookies sensibles afin d'empêcher l'accès inter-origines.
        - Auditez régulièrement vos paramètres de cookies pour assurer la conformité avec les réglementations de sécurité et de confidentialité.
        - Évitez de définir des cookies sans l'attribut Secure dans les environnements de production.

=== "En-têtes personnalisés"

    **Aperçu**

    Les en-têtes personnalisés vous permettent d'ajouter des en-têtes HTTP spécifiques pour répondre aux exigences de l'application ou de performance. Ils offrent de la flexibilité mais doivent être configurés avec soin pour éviter d'exposer des détails sensibles du serveur.

    !!! success "Avantages des en-têtes personnalisés"
        - Améliorez la sécurité en supprimant les en-têtes inutiles qui pourraient divulguer des détails sur le serveur.
        - Ajoutez des en-têtes spécifiques à l'application pour améliorer la fonctionnalité ou le débogage.

    | Paramètre        | Défaut                                                                               | Contexte  | Multiple | Description                                                                                                                                                                             |
    | ---------------- | ------------------------------------------------------------------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `CUSTOM_HEADER`  |                                                                                      | multisite | oui      | **En-tête personnalisé :** Permet d'ajouter des en-têtes définis par l'utilisateur au format NomEnTete: ValeurEnTete pour des améliorations de sécurité ou de performance spécialisées. |
    | `REMOVE_HEADERS` | `Server Expect-CT X-Powered-By X-AspNet-Version X-AspNetMvc-Version Public-Key-Pins` | multisite | non      | **Supprimer les en-têtes :** Spécifie les en-têtes à supprimer, réduisant ainsi le risque d'exposer des détails internes du serveur et des vulnérabilités connues.                      |

    !!! warning "Considérations de sécurité"
        - Évitez d'exposer des informations sensibles via des en-têtes personnalisés.
        - Révisez et mettez à jour régulièrement les en-têtes personnalisés pour les aligner sur les exigences de votre application.

    !!! tip "Bonnes pratiques"
        - Utilisez `REMOVE_HEADERS` pour supprimer les en-têtes comme `Server` et `X-Powered-By` afin de réduire les risques de prise d'empreintes.
        - Testez les en-têtes personnalisés dans un environnement de pré-production avant de les déployer en production.

### Exemples de configuration

=== "En-têtes de sécurité de base"

    Une configuration standard avec les en-têtes de sécurité essentiels :

    ```yaml
    STRICT_TRANSPORT_SECURITY: "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'self'"
    X_FRAME_OPTIONS: "SAMEORIGIN"
    X_CONTENT_TYPE_OPTIONS: "nosniff"
    REFERRER_POLICY: "strict-origin-when-cross-origin"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version"
    ```

=== "Sécurité des cookies renforcée"

    Configuration avec des paramètres de sécurité des cookies robustes :

    ```yaml
    COOKIE_FLAGS: "* HttpOnly SameSite=Strict"
    COOKIE_FLAGS_2: "session_cookie Secure HttpOnly SameSite=Strict"
    COOKIE_FLAGS_3: "auth_cookie Secure HttpOnly SameSite=Strict Max-Age=3600"
    COOKIE_AUTO_SECURE_FLAG: "yes"
    ```

=== "En-têtes personnalisés pour API"

    Configuration pour un service API avec des en-têtes personnalisés :

    ```yaml
    CUSTOM_HEADER: "API-Version: 1.2.3"
    CUSTOM_HEADER_2: "Access-Control-Max-Age: 86400"
    CONTENT_SECURITY_POLICY: "default-src 'none'; frame-ancestors 'none'"
    REMOVE_HEADERS: "Server X-Powered-By X-AspNet-Version X-Runtime"
    ```

=== "Content Security Policy - Mode rapport"

    Configuration pour tester la CSP sans casser les fonctionnalités :

    ```yaml
    CONTENT_SECURITY_POLICY: "default-src 'self'; script-src 'self' https://trusted-cdn.example.com; img-src 'self' data: https://*.example.com; style-src 'self' 'unsafe-inline' https://trusted-cdn.example.com; connect-src 'self' https://api.example.com; object-src 'none'; frame-ancestors 'self'; form-action 'self'; base-uri 'self'; report-uri https://example.com/csp-reports"
    CONTENT_SECURITY_POLICY_REPORT_ONLY: "yes"
    ```

## Let's Encrypt

Prise en charge STREAM :white_check_mark:

Le plugin Let’s Encrypt simplifie la gestion des certificats SSL/TLS en automatisant la création, le renouvellement et la configuration de certificats gratuits de Let's Encrypt. Cette fonctionnalité active les connexions HTTPS sécurisées pour vos sites web sans la complexité de la gestion manuelle des certificats, réduisant ainsi les coûts et la charge administrative.

**Comment ça marche :**

1.  Une fois activé, BunkerWeb détecte automatiquement les domaines configurés pour votre site.
2.  BunkerWeb demande des certificats SSL/TLS gratuits à l'autorité de certification de Let's Encrypt.
3.  La propriété du domaine est vérifiée par des défis HTTP (prouvant que vous contrôlez le site) ou des défis DNS (prouvant que vous contrôlez le DNS de votre domaine).
4.  Les certificats sont automatiquement installés et configurés pour vos domaines.
5.  BunkerWeb gère les renouvellements de certificats en arrière-plan avant leur expiration, assurant une disponibilité HTTPS continue.
6.  L'ensemble du processus est entièrement automatisé, ne nécessitant qu'une intervention minimale après la configuration initiale.

!!! info "Prérequis"
    Pour utiliser cette fonctionnalité, assurez-vous que des enregistrements DNS **A** corrects sont configurés pour chaque domaine, pointant vers la ou les IP publiques où BunkerWeb est accessible. Sans une configuration DNS correcte, le processus de vérification de domaine échouera.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Let's Encrypt :

1.  **Activer la fonctionnalité :** Mettez le paramètre `AUTO_LETS_ENCRYPT` à `yes` pour activer l'émission et le renouvellement automatiques des certificats.
2.  **Fournir un e-mail de contact (recommandé) :** Saisissez votre adresse e-mail dans le paramètre `EMAIL_LETS_ENCRYPT` pour que Let's Encrypt puisse vous prévenir avant l'expiration d'un certificat. Si vous laissez ce champ vide, BunkerWeb s'enregistrera sans adresse (option Certbot `--register-unsafely-without-email`) et vous ne recevrez aucun rappel ni e-mail de récupération.
3.  **Choisir le type de défi :** Sélectionnez la vérification `http` ou `dns` avec le paramètre `LETS_ENCRYPT_CHALLENGE`.
4.  **Configurer le fournisseur DNS :** Si vous utilisez les défis DNS, spécifiez votre fournisseur DNS et vos identifiants.
5.  **Sélectionner un profil de certificat :** Choisissez votre profil de certificat préféré avec le paramètre `LETS_ENCRYPT_PROFILE` (classic, tlsserver ou shortlived).
6.  **Laissez BunkerWeb s'occuper du reste :** Une fois configuré, les certificats sont automatiquement émis, installés et renouvelés selon les besoins.

!!! tip "Profils de certificat"
    Let's Encrypt propose différents profils de certificat pour différents cas d'usage : - **classic** : Certificats à usage général avec une validité de 90 jours (par défaut) - **tlsserver** : Optimisé pour l'authentification de serveur TLS avec une validité de 90 jours et une charge utile plus petite - **shortlived** : Sécurité renforcée avec une validité de 7 jours pour les environnements automatisés - **custom** : Si votre serveur ACME prend en charge un profil différent, définissez-le avec `LETS_ENCRYPT_CUSTOM_PROFILE`.

!!! info "Disponibilité des profils"
    Notez que les profils `tlsserver` et `shortlived` peuvent ne pas être disponibles dans tous les environnements ou avec tous les clients ACME pour le moment. Le profil `classic` a la compatibilité la plus large et est recommandé pour la plupart des utilisateurs. Si un profil sélectionné n'est pas disponible, le système basculera automatiquement sur le profil `classic`.

### Paramètres de configuration

| Paramètre                                   | Défaut    | Contexte  | Multiple | Description                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------- | --------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | no       | **Activer Let's Encrypt :** Mettre à `yes` pour activer l'émission et le renouvellement automatiques des certificats.                                                                                                                                                                                                        |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | no       | **Passer à travers Let's Encrypt :** Mettre à `yes` pour passer les requêtes Let's Encrypt au serveur web. Utile si BunkerWeb est derrière un autre reverse proxy gérant le SSL.                                                                                                                                             |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | no       | **E-mail de contact :** Adresse e-mail utilisée pour les rappels Let's Encrypt. Ne laissez ce champ vide que si vous acceptez de ne recevoir aucun avertissement ni e-mail de récupération (Certbot s'enregistre avec `--register-unsafely-without-email`).                                                                  |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | no       | **Type de défi :** Méthode utilisée pour vérifier la propriété du domaine. Options : `http` ou `dns`.                                                                                                                                                                                                                        |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | no       | **Fournisseur DNS :** Pour les défis DNS, le fournisseur à utiliser (ex. : cloudflare, route53, digitalocean).                                                                                                                                                                                                               |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | no       | **Propagation DNS :** Le temps d'attente en secondes pour la propagation DNS. Si aucune valeur n'est fournie, le temps par défaut du fournisseur est utilisé.                                                                                                                                                                |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | yes      | **Élément d'identification :** Éléments de configuration pour l'authentification du fournisseur DNS (ex. : `cloudflare_api_token 123456`). Les valeurs peuvent être du texte brut, encodées en base64 ou un objet JSON.                                                                                                      |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | no       | **Décoder les identifiants DNS Base64 :** Décoder automatiquement les identifiants du fournisseur DNS encodés en base64 lorsqu'il est défini sur `yes`. Les valeurs au format base64 sont décodées avant utilisation (sauf pour le fournisseur `rfc2136`). Désactivez si vos identifiants sont intentionnellement en base64. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | no       | **Certificats Wildcard :** Si mis à `yes`, crée des certificats wildcard pour tous les domaines. Uniquement disponible avec les défis DNS.                                                                                                                                                                                   |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | no       | **Utiliser Staging :** Si mis à `yes`, utilise l'environnement de staging de Let's Encrypt pour les tests. Les limites de débit y sont plus élevées mais les certificats ne sont pas fiables.                                                                                                                                |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | no       | **Effacer les anciens certificats :** Si mis à `yes`, supprime les anciens certificats inutiles lors du renouvellement.                                                                                                                                                                                                      |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | no       | **Profil de certificat :** Sélectionnez le profil à utiliser. Options : `classic` (général), `tlsserver` (optimisé TLS), ou `shortlived` (7 jours).                                                                                                                                                                          |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | no       | **Profil de certificat personnalisé :** Saisissez un profil personnalisé si votre serveur ACME le supporte. Remplace `LETS_ENCRYPT_PROFILE` s'il est défini.                                                                                                                                                                 |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | no       | **Tentatives maximales :** Nombre de tentatives de génération de certificat en cas d'échec. `0` pour désactiver. Utile pour les problèmes réseau temporaires.                                                                                                                                                                |

!!! info "Information et comportement"
    - Le paramètre `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` est un paramètre multiple et peut être utilisé pour définir plusieurs éléments pour le fournisseur DNS. Les éléments seront enregistrés dans un fichier de cache, et Certbot lira les informations d'identification à partir de celui-ci.
    - Si aucun paramètre `LETS_ENCRYPT_DNS_PROPAGATION` n'est fourni, le temps de propagation par défaut du fournisseur est utilisé.
    - L'automatisation complète de Let's Encrypt avec le défi `http` fonctionne en mode stream tant que vous ouvrez le port `80/tcp` depuis l'extérieur. Utilisez le paramètre `LISTEN_STREAM_PORT_SSL` pour choisir votre port d'écoute SSL/TLS.
    - Si `LETS_ENCRYPT_PASSTHROUGH` est mis à `yes`, BunkerWeb ne gérera pas les requêtes de défi ACME lui-même mais les transmettra au serveur web backend. Ceci est utile dans les scénarios où BunkerWeb agit comme un reverse proxy devant un autre serveur configuré pour gérer les défis Let's Encrypt.

!!! tip "Défis HTTP vs. DNS"
    **Les défis HTTP** sont plus simples à configurer et fonctionnent bien pour la plupart des sites web :

    - Nécessite que votre site soit publiquement accessible sur le port 80
    - Configuré automatiquement par BunkerWeb
    - Ne peut pas être utilisé pour les certificats wildcard

    **Les défis DNS** offrent plus de flexibilité et sont requis pour les certificats wildcard :

    - Fonctionne même si votre site n'est pas publiquement accessible
    - Nécessite les identifiants de l'API de votre fournisseur DNS
    - Requis pour les certificats wildcard (ex. : *.example.com)
    - Utile lorsque le port 80 est bloqué ou indisponible

!!! warning "Certificats wildcard"
    Les certificats wildcard ne sont disponibles qu'avec les défis DNS. Si vous souhaitez les utiliser, vous devez mettre le paramètre `USE_LETS_ENCRYPT_WILDCARD` à `yes` et configurer correctement les identifiants de votre fournisseur DNS.

!!! warning "Limites de débit"
    Let's Encrypt impose des limites de débit sur l'émission de certificats. Lors du test de configurations, utilisez l'environnement de staging en mettant `USE_LETS_ENCRYPT_STAGING` à `yes` pour éviter d'atteindre les limites de production. Les certificats de staging ne sont pas reconnus par les navigateurs mais sont utiles pour valider votre configuration.

### Fournisseurs DNS supportés

Le plugin Let's Encrypt prend en charge un large éventail de fournisseurs DNS pour les défis DNS. Chaque fournisseur nécessite des informations d'identification spécifiques qui doivent être fournies via le paramètre `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`.

| Fournisseur       | Description      | Paramètres obligatoires                                                                                      | Paramètres optionnels                                                                                                                                                                                                                                                    | Documentation                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | soit `api_token`<br>soit `email` et `api_key`                                                                |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (défaut : `service_account`)<br>`auth_uri` (défaut : `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (défaut : `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (défaut : `https://www.googleapis.com/oauth2/v1/certs`) | [Documentation](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (défaut : `https://api.hosting.ionos.com`)                                                                                                                                                                                                                    | [Documentation](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (défaut : `ovh-eu`)                                                                                                                                                                                                                                           | [Documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (défaut : `53`)<br>`algorithm` (défaut : `HMAC-SHA512`)<br>`sign_query` (défaut : `false`)                                                                                                                                                                        | [Documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |

### Exemples de configuration

=== "Défi HTTP de base"

    Configuration simple utilisant les défis HTTP pour un seul domaine :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "DNS Cloudflare avec Wildcard"

    Configuration pour les certificats wildcard utilisant le DNS de Cloudflare :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token VOTRE_JETON_API"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "Configuration AWS Route53"

    Configuration utilisant Amazon Route53 pour les défis DNS :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id VOTRE_CLE_ACCES"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key VOTRE_CLE_SECRETE"
    ```

=== "Test avec l'environnement de Staging et tentatives"

    Configuration pour tester la configuration avec l'environnement de staging et des paramètres de tentatives améliorés :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean avec temps de propagation personnalisé"

    Configuration utilisant le DNS de DigitalOcean avec un temps d'attente de propagation plus long :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token VOTRE_JETON_API"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    Configuration utilisant Google Cloud DNS avec les informations d'identification d'un compte de service :

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id votre-id-projet"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id votre-id-cle-privee"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key votre-cle-privee"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email votre-email-compte-service"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id votre-id-client"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url votre-url-cert"
    ```

## Limit

Prise en charge STREAM :warning:

Le plugin Limit permet d’appliquer des politiques de limitation pour garantir un usage équitable et protéger vos ressources contre les abus, les attaques par déni de service (DoS) et la surconsommation. Ces politiques incluent :

- **Le nombre de connexions simultanées par adresse IP** (support STREAM :white_check_mark:)
- **Le nombre de requêtes par adresse IP et par URL sur une période donnée** (support STREAM :x:)

### Fonctionnement

1.  **Limitation de débit :** Suit le nombre de requêtes de chaque adresse IP cliente vers des URL spécifiques. Si un client dépasse la limite de débit configurée, les requêtes suivantes sont temporairement refusées.
2.  **Limitation de connexions :** Surveille et restreint le nombre de connexions simultanées de chaque adresse IP cliente. Différentes limites de connexion peuvent être appliquées en fonction du protocole utilisé (HTTP/1, HTTP/2, HTTP/3 ou stream).
3.  Dans les deux cas, les clients qui dépassent les limites définies reçoivent un code de statut HTTP **« 429 - Too Many Requests »**, ce qui aide à prévenir la surcharge du serveur.

### Utilisation

1.  **Activer la limitation de débit de requêtes :** Utilisez `USE_LIMIT_REQ` pour activer la limitation de débit de requêtes et définissez des motifs d'URL avec leurs limites correspondantes.
2.  **Activer la limitation de connexions :** Utilisez `USE_LIMIT_CONN` pour activer la limitation de connexions et définissez le nombre maximum de connexions simultanées pour différents protocoles.
3.  **Appliquer un contrôle granulaire :** Créez plusieurs règles de limitation de débit pour différentes URL afin de fournir des niveaux de protection variés sur votre site.
4.  **Suivre l'efficacité :** Utilisez l'[interface web](web-ui.md) pour consulter les statistiques sur les requêtes et les connexions limitées.

### Paramètres

=== "Limitation de requêtes"

    | Paramètre        | Défaut | Contexte  | Multiple | Description                                                                                                                                                                  |
    | ---------------- | ------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_REQ`  | `yes`  | multisite | non      | **Activer la limitation de requêtes :** Mettre à `yes` pour activer la fonctionnalité de limitation de débit par requêtes.                                                   |
    | `LIMIT_REQ_URL`  | `/`    | multisite | oui      | **Motif d’URL :** Motif d’URL (regex PCRE) auquel la limite de débit sera appliquée ; utilisez `/` pour l'appliquer à toutes les requêtes.                                   |
    | `LIMIT_REQ_RATE` | `2r/s` | multisite | oui      | **Limite de débit :** Taux de requêtes maximal au format `Nr/t`, où N est le nombre de requêtes et t est l'unité de temps : s (seconde), m (minute), h (heure), ou d (jour). |

!!! tip "Format de la limitation de débit"
    Le format de la limite de débit est spécifié comme `Nr/t` où :

    - `N` est le nombre de requêtes autorisées
    - `r` est la lettre littérale 'r' (pour 'requêtes')
    - `/` est une barre oblique littérale
    - `t` est l'unité de temps : `s` (seconde), `m` (minute), `h` (heure), ou `d` (jour)

    Par exemple, `5r/m` signifie que 5 requêtes par minute sont autorisées pour chaque adresse IP.

=== "Limitation de connexions"

    | Paramètre               | Défaut | Contexte  | Multiple | Description                                                                                                    |
    | ----------------------- | ------ | --------- | -------- | -------------------------------------------------------------------------------------------------------------- |
    | `USE_LIMIT_CONN`        | `yes`  | multisite | non      | **Activer la limitation de connexions :** Mettre à `yes` pour activer la limitation de connexions simultanées. |
    | `LIMIT_CONN_MAX_HTTP1`  | `10`   | multisite | non      | **Connexions HTTP/1.X :** Nombre maximal de connexions HTTP/1.X simultanées par adresse IP.                    |
    | `LIMIT_CONN_MAX_HTTP2`  | `100`  | multisite | non      | **Flux HTTP/2 :** Nombre maximal de flux HTTP/2 simultanés par adresse IP.                                     |
    | `LIMIT_CONN_MAX_HTTP3`  | `100`  | multisite | non      | **Flux HTTP/3 :** Nombre maximal de flux HTTP/3 simultanés par adresse IP.                                     |
    | `LIMIT_CONN_MAX_STREAM` | `10`   | multisite | non      | **Connexions Stream :** Nombre maximal de connexions stream simultanées par adresse IP.                        |

!!! info "Limitation de connexions vs de requêtes" - La **limitation de connexions** restreint le nombre de connexions simultanées qu'une seule adresse IP peut maintenir. - La **limitation de débit de requêtes** restreint le nombre de requêtes qu'une adresse IP peut effectuer dans une période de temps définie.

    L'utilisation des deux méthodes offre une protection complète contre divers types d'abus.

!!! warning "Réglages adaptés"
    Des limites trop strictes peuvent impacter des clients légitimes, notamment pour HTTP/2 et HTTP/3 où les navigateurs utilisent souvent plusieurs flux. Les valeurs par défaut sont équilibrées pour la plupart des cas d'utilisation, mais envisagez de les ajuster en fonction des besoins de votre application et du comportement des utilisateurs.

### Exemples de configuration

=== "Protection de base"

    Une configuration simple utilisant les paramètres par défaut pour protéger l'ensemble de votre site :

    ```yaml
    USE_LIMIT_REQ: "yes"
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "2r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Protection d'endpoints spécifiques"

    Configuration avec différentes limites de débit pour divers endpoints :

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Règle par défaut pour toutes les requêtes
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "10r/s"

    # Limite plus stricte pour la page de connexion
    LIMIT_REQ_URL_2: "^/login"
    LIMIT_REQ_RATE_2: "1r/s"

    # Limite plus stricte pour l'API
    LIMIT_REQ_URL_3: "^/api/"
    LIMIT_REQ_RATE_3: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "10"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "10"
    ```

=== "Configuration pour site à fort trafic"

    Configuration optimisée pour les sites à fort trafic avec des limites plus permissives :

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Limite générale
    LIMIT_REQ_URL: "/"
    LIMIT_REQ_RATE: "30r/s"

    # Protection de la zone d'administration
    LIMIT_REQ_URL_2: "^/admin/"
    LIMIT_REQ_RATE_2: "5r/s"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "50"
    LIMIT_CONN_MAX_HTTP2: "200"
    LIMIT_CONN_MAX_HTTP3: "200"
    LIMIT_CONN_MAX_STREAM: "30"
    ```

=== "Configuration pour serveur d'API"

    Configuration optimisée pour un serveur d'API avec des limites de débit exprimées en requêtes par minute :

    ```yaml
    USE_LIMIT_REQ: "yes"

    # Endpoints de l'API publique
    LIMIT_REQ_URL: "^/api/public/"
    LIMIT_REQ_RATE: "120r/m"

    # Endpoints de l'API privée
    LIMIT_REQ_URL_2: "^/api/private/"
    LIMIT_REQ_RATE_2: "300r/m"

    # Endpoint d'authentification
    LIMIT_REQ_URL_3: "^/api/auth"
    LIMIT_REQ_RATE_3: "10r/m"

    USE_LIMIT_CONN: "yes"
    LIMIT_CONN_MAX_HTTP1: "20"
    LIMIT_CONN_MAX_HTTP2: "100"
    LIMIT_CONN_MAX_HTTP3: "100"
    LIMIT_CONN_MAX_STREAM: "20"
    ```

## Load Balancer <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/cOVp0rAt5nw' title='Équilibreur de charge' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

Prise en charge STREAM :x:

Provides load balancing feature to group of upstreams with optional healthchecks.

| Paramètre                                 | Valeur par défaut | Contexte | Multiple | Description                                                        |
| ----------------------------------------- | ----------------- | -------- | -------- | ------------------------------------------------------------------ |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`             | global   | non      | Shared dict size (datastore for all healthchecks).                 |
| `LOADBALANCER_UPSTREAM_NAME`              |                   | global   | oui      | Name of the upstream (used in REVERSE_PROXY_HOST).                 |
| `LOADBALANCER_UPSTREAM_SERVERS`           |                   | global   | oui      | List of servers/IPs in the server group.                           |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin`     | global   | oui      | Load balancing mode (round-robin or sticky).                       |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`              | global   | oui      | Sticky session method (ip or cookie).                              |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`              | global   | oui      | Dynamically resolve upstream hostnames.                            |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |                   | global   | oui      | Number of keepalive connections to cache per worker.               |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`             | global   | oui      | Keepalive timeout for upstream connections.                        |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`              | global   | oui      | Keepalive time for upstream connections.                           |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status`         | global   | oui      | The healthcheck URL.                                               |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`            | global   | oui      | Healthcheck interval in milliseconds.                              |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`            | global   | oui      | Healthcheck timeout in milliseconds.                               |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`               | global   | oui      | Number of failed healthchecks before marking the server as down.   |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`               | global   | oui      | Number of successful healthchecks before marking the server as up. |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`             | global   | oui      | HTTP status considered valid in healthchecks.                      |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`              | global   | oui      | Maximum number of concurrent healthchecks.                         |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`            | global   | oui      | Type of healthcheck (http or https).                               |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`             | global   | oui      | Verify SSL certificate in healthchecks.                            |
| `LOADBALANCER_HEALTHCHECK_HOST`           |                   | global   | oui      | Host header for healthchecks (useful for HTTPS).                   |

## Metrics

Prise en charge STREAM :warning:

Le plugin Metrics offre une collecte/visualisation des indicateurs de votre instance BunkerWeb : performances, événements de sécurité, statistiques système…

Comment ça marche :

1. BunkerWeb collecte des métriques lors du traitement des requêtes/réponses.
2. Compteurs de requêtes bloquées, mesures de perfs et stats sécurité sont enregistrés.
3. Stockage en mémoire avec limites configurables pour contenir l’usage de ressources.
4. En multi‑instances, Redis permet d’agréger/centraliser les données.
5. Accès via API ou [web UI](web-ui.md).

### Paramètres

| Paramètre                            | Défaut   | Contexte  | Multiple | Description                                                        |
| ------------------------------------ | -------- | --------- | -------- | ------------------------------------------------------------------ |
| `USE_METRICS`                        | `yes`    | multisite | non      | Activer la collecte et l’accès aux métriques.                      |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | non      | Taille du stockage interne (ex. `16m`, `32m`).                     |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`   | global    | non      | Max de requêtes bloquées conservées par worker.                    |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000` | global    | non      | Max de requêtes bloquées conservées dans Redis.                    |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | non      | Sauvegarder compteurs/tableaux dans Redis pour agrégation cluster. |

!!! tip "Dimensionnement mémoire"
    Ajustez `METRICS_MEMORY_SIZE` selon le trafic et le nombre d’instances.

!!! info "Intégration Redis"
    Avec [Redis](#redis), les requêtes bloquées sont synchronisées pour une vue centralisée multi‑nœuds.

!!! warning "Performance"
    Des valeurs trop élevées augmentent l’usage mémoire. Surveillez et ajustez.

### Exemples

=== "Configuration par défaut"

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Ressources limitées"

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "Fort trafic"

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Désactivation"

    ```yaml
    USE_METRICS: "no"
    ```

## Migration <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :white_check_mark:

Migration of BunkerWeb configuration between instances made easy via the web UI

## Miscellaneous

Prise en charge STREAM :warning:

Le plugin Divers (Miscellaneous) fournit des **paramètres de base essentiels** qui aident à maintenir la sécurité et la fonctionnalité de votre site web. Ce composant central offre des contrôles complets pour :

- **Le comportement du serveur** - Configurez la manière dont votre serveur répond à diverses requêtes
- **Les paramètres HTTP** - Gérez les méthodes, la taille des requêtes et les options de protocole
- **La gestion des fichiers** - Contrôlez le service des fichiers statiques et optimisez leur livraison
- **Le support des protocoles** - Activez les protocoles HTTP modernes pour de meilleures performances
- **Les configurations système** - Étendez les fonctionnalités et améliorez la sécurité

Que vous ayez besoin de restreindre les méthodes HTTP, de gérer la taille des requêtes, d'optimiser la mise en cache des fichiers ou de contrôler la manière dont votre serveur répond à diverses requêtes, ce plugin vous donne les outils pour **affiner le comportement de votre service web** tout en optimisant à la fois la performance et la sécurité.

### Fonctionnalités clés

| Catégorie de fonctionnalité           | Description                                                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Contrôle des méthodes HTTP**        | Définissez quelles méthodes HTTP sont acceptables pour votre application                                     |
| **Protection du serveur par défaut**  | Empêchez l'accès non autorisé par des noms d'hôte incorrects et forcez le SNI pour les connexions sécurisées |
| **Gestion de la taille des requêtes** | Définissez des limites pour le corps des requêtes client et les téléversements de fichiers                   |
| **Service de fichiers statiques**     | Configurez et optimisez la livraison de contenu statique depuis des dossiers racine personnalisés            |
| **Mise en cache des fichiers**        | Améliorez les performances grâce à des mécanismes avancés de mise en cache des descripteurs de fichiers      |
| **Support des protocoles**            | Configurez les options des protocoles HTTP modernes (HTTP2/HTTP3) et les paramètres de port Alt-Svc          |
| **Rapport anonyme**                   | Rapport de statistiques d'utilisation optionnel pour aider à améliorer BunkerWeb                             |
| **Support des plugins externes**      | Étendez les fonctionnalités en intégrant des plugins externes via des URL                                    |
| **Contrôle du statut HTTP**           | Configurez la réponse de votre serveur lors du refus de requêtes (y compris la fermeture de connexion)       |

### Guide de configuration

=== "Sécurité du serveur par défaut"

    **Contrôles du serveur par défaut**

    En HTTP, l'en-tête `Host` spécifie le serveur cible, mais il peut être manquant ou inconnu, souvent à cause de bots recherchant des vulnérabilités.

    Pour bloquer de telles requêtes :

    - Mettez `DISABLE_DEFAULT_SERVER` à `yes` pour refuser silencieusement ces requêtes en utilisant le [code de statut `444` de NGINX](https://http.dev/444).
    - Pour une sécurité plus stricte, activez `DISABLE_DEFAULT_SERVER_STRICT_SNI` pour rejeter les connexions SSL/TLS sans SNI valide.

    !!! success "Avantages en matière de sécurité"
        - Bloque la manipulation de l'en-tête Host et le scan des hôtes virtuels
        - Atténue les risques de contrebande de requêtes HTTP (HTTP request smuggling)
        - Supprime le serveur par défaut comme vecteur d'attaque

    | Paramètre                           | Défaut | Contexte | Multiple | Description                                                                                                                       |
    | ----------------------------------- | ------ | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
    | `DISABLE_DEFAULT_SERVER`            | `no`   | global   | no       | **Serveur par défaut :** Mettre à `yes` pour désactiver le serveur par défaut lorsqu'aucun nom d'hôte ne correspond à la requête. |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`   | global   | no       | **SNI Strict :** Si mis à `yes`, requiert le SNI pour les connexions HTTPS et rejette les connexions sans SNI valide.             |

    !!! warning "Application du SNI"
        Activer la validation stricte du SNI offre une sécurité renforcée mais peut causer des problèmes si BunkerWeb est derrière un proxy inverse qui transmet les requêtes HTTPS sans préserver les informations SNI. Testez minutieusement avant d'activer en production.

=== "Statut HTTP en cas de refus"

    **Contrôle du statut HTTP**

    La première étape dans la gestion de l'accès refusé à un client est de définir l'action appropriée. Cela peut être configuré avec le paramètre `DENY_HTTP_STATUS`. Lorsque BunkerWeb refuse une requête, vous pouvez contrôler sa réponse. Par défaut, il renvoie un statut `403 Forbidden`, affichant une page web ou un contenu personnalisé.

    Alternativement, le régler sur `444` ferme immédiatement la connexion sans envoyer de réponse. Ce [code de statut non standard](https://http.dev/444), spécifique à NGINX, est utile pour ignorer silencieusement les requêtes indésirables.

    | Paramètre          | Défaut | Contexte | Multiple | Description                                                                                                                          |
    | ------------------ | ------ | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
    | `DENY_HTTP_STATUS` | `403`  | global   | no       | **Statut HTTP de refus :** Code de statut HTTP à envoyer quand une requête est refusée (403 ou 444). Le code 444 ferme la connexion. |

    !!! warning "Considérations sur le code de statut 444"
        Comme les clients ne reçoivent aucun retour, le dépannage peut être plus difficile. Régler sur `444` est recommandé uniquement si vous avez minutieusement traité les faux positifs, êtes expérimenté avec BunkerWeb et exigez un niveau de sécurité plus élevé.

    !!! info "Mode stream"
        En **mode stream**, ce paramètre est toujours appliqué comme `444`, ce qui signifie que la connexion sera fermée, quelle que soit la valeur configurée.

=== "Méthodes HTTP"

    **Contrôle des méthodes HTTP**

    Restreindre les méthodes HTTP à celles requises par votre application est une mesure de sécurité fondamentale qui respecte le principe du moindre privilège. En définissant explicitement les méthodes acceptables, vous minimisez le risque d'exploitation via des méthodes inutilisées ou dangereuses.

    Cette fonctionnalité est configurée avec `ALLOWED_METHODS`, où les méthodes sont listées et séparées par un `|` (défaut : `GET|POST|HEAD`). Si un client tente une méthode non listée, le serveur répondra avec un statut **405 - Method Not Allowed**.

    Pour la plupart des sites web, le défaut `GET|POST|HEAD` est suffisant. Si votre application utilise des API RESTful, vous devrez peut-être inclure `PUT` et `DELETE`.

    !!! success "Avantages en matière de sécurité"
        - Empêche l'exploitation de méthodes HTTP inutilisées ou inutiles
        - Réduit la surface d'attaque en désactivant les méthodes potentiellement dangereuses
        - Bloque les techniques d'énumération de méthodes HTTP utilisées par les attaquants

    | Paramètre         | Défaut | Contexte | Multiple | Description |
    | ----------------- | ------ | -------- | -------- | ----------- |
    | `ALLOWED_METHODS` | `GET   | POST     | HEAD`    | multisite   | no | **Méthodes HTTP :** Liste des méthodes HTTP autorisées, séparées par des barres verticales (` | `). |

    !!! abstract "CORS et requêtes pre-flight"
        Si votre application prend en charge le [Cross-Origin Resource Sharing (CORS)](#cors), vous devriez inclure la méthode `OPTIONS` dans `ALLOWED_METHODS` pour gérer les requêtes pre-flight. Cela garantit le bon fonctionnement pour les navigateurs effectuant des requêtes inter-origines.

    !!! danger "Considérations de sécurité"
        - **Évitez d'activer `TRACE` ou `CONNECT` :** Ces méthodes sont rarement nécessaires et peuvent introduire des risques de sécurité importants, comme le Cross-Site Tracing (XST) ou les attaques par tunnelisation.
        - **Révisez régulièrement les méthodes autorisées :** Auditez périodiquement `ALLOWED_METHODS` pour vous assurer qu'il correspond aux besoins actuels de votre application.
        - **Testez minutieusement avant le déploiement :** Les changements de restrictions de méthodes HTTP peuvent impacter la fonctionnalité de l'application. Validez votre configuration dans un environnement de pré-production.

=== "Limites de taille des requêtes"

    **Limites de taille des requêtes**

    La taille maximale du corps d'une requête peut être contrôlée avec `MAX_CLIENT_SIZE` (défaut : `10m`). Les valeurs acceptées suivent la syntaxe décrite [ici](https://nginx.org/en/docs/syntax.html).

    !!! success "Avantages en matière de sécurité"
        - Protège contre les attaques par déni de service causées par des charges utiles excessives
        - Atténue les vulnérabilités de débordement de tampon (buffer overflow)
        - Empêche les attaques par téléversement de fichiers
        - Réduit le risque d'épuisement des ressources du serveur

    | Paramètre         | Défaut | Contexte  | Multiple | Description                                                                                                               |
    | ----------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`  | multisite | no       | **Taille maximale des requêtes :** La taille maximale autorisée pour le corps des requêtes client (ex. : téléversements). |

    !!! tip "Bonnes pratiques de configuration de la taille des requêtes"
        Si vous devez autoriser un corps de requête de taille illimitée, vous pouvez mettre la valeur `MAX_CLIENT_SIZE` à `0`. Cependant, ce n'est **pas recommandé** en raison des risques potentiels de sécurité et de performance.

        **Bonnes pratiques :**

        - Configurez toujours `MAX_CLIENT_SIZE` à la plus petite valeur répondant aux besoins légitimes de votre application.
        - Révisez et ajustez régulièrement ce paramètre pour l'aligner sur les besoins évolutifs de votre application.
        - Évitez de mettre `0` sauf en cas de nécessité absolue, car cela peut exposer votre serveur à des attaques par déni de service et à l'épuisement des ressources.

        En gérant soigneusement ce paramètre, vous pouvez garantir une sécurité et des performances optimales pour votre application.

=== "Support des protocoles"

    **Paramètres des protocoles HTTP**

    Les protocoles HTTP modernes comme HTTP/2 et HTTP/3 améliorent la performance et la sécurité. BunkerWeb permet une configuration facile de ces protocoles.

    !!! success "Avantages en matière de sécurité et de performance"
        - **Avantages de sécurité :** Les protocoles modernes comme HTTP/2 et HTTP/3 imposent TLS/HTTPS par défaut, réduisent la sensibilité à certaines attaques et améliorent la confidentialité grâce aux en-têtes chiffrés (HTTP/3).
        - **Avantages de performance :** Des fonctionnalités comme le multiplexage, la compression des en-têtes, le server push et le transfert de données binaires améliorent la vitesse et l'efficacité.

    | Paramètre            | Défaut | Contexte  | Multiple | Description                                                                   |
    | -------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`  | multisite | no       | **Écoute HTTP :** Répondre aux requêtes HTTP (non sécurisées) si mis à `yes`. |
    | `HTTP2`              | `yes`  | multisite | no       | **HTTP2 :** Supporte le protocole HTTP2 lorsque HTTPS est activé.             |
    | `HTTP3`              | `yes`  | multisite | no       | **HTTP3 :** Supporte le protocole HTTP3 lorsque HTTPS est activé.             |
    | `HTTP3_ALT_SVC_PORT` | `443`  | multisite | no       | **Port Alt-Svc HTTP3 :** Port à utiliser dans l'en-tête Alt-Svc pour HTTP3.   |

    !!! example "À propos de HTTP/3"
        HTTP/3, la dernière version du protocole Hypertext Transfer, utilise QUIC sur UDP au lieu de TCP, résolvant des problèmes comme le blocage en tête de ligne pour des connexions plus rapides et plus fiables.

        NGINX a introduit un support expérimental pour HTTP/3 et QUIC à partir de la version 1.25.0. Cependant, cette fonctionnalité est encore expérimentale, et la prudence est de mise pour une utilisation en production. Pour plus de détails, consultez la [documentation officielle de NGINX](https://nginx.org/en/docs/quic.html).

        Des tests approfondis sont recommandés avant d'activer HTTP/3 en production.

=== "Service de fichiers statiques"

    **Configuration du service de fichiers**

    BunkerWeb peut servir des fichiers statiques directement ou agir comme un proxy inverse vers un serveur d'application. Par défaut, les fichiers sont servis depuis `/var/www/html/{server_name}`.

    | Paramètre     | Défaut                        | Contexte  | Multiple | Description                                                                                                                      |
    | ------------- | ----------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
    | `SERVE_FILES` | `yes`                         | multisite | no       | **Servir des fichiers :** Si `yes`, BunkerWeb servira les fichiers statiques depuis le dossier racine configuré.                 |
    | `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | no       | **Dossier racine :** Le répertoire depuis lequel servir les fichiers statiques. Vide signifie utiliser l'emplacement par défaut. |

    !!! tip "Bonnes pratiques pour le service de fichiers statiques"
        - **Service direct :** Activez le service de fichiers (`SERVE_FILES=yes`) lorsque BunkerWeb est responsable de servir directement les fichiers statiques.
        - **Proxy inverse :** Si BunkerWeb agit comme un proxy inverse, **désactivez le service de fichiers** (`SERVE_FILES=no`) pour réduire la surface d'attaque et éviter d'exposer des répertoires inutiles.
        - **Permissions :** Assurez-vous que les permissions de fichiers et les configurations de chemin sont correctes pour empêcher tout accès non autorisé.
        - **Sécurité :** Évitez d'exposer des répertoires ou des fichiers sensibles par des mauvaises configurations.

        En gérant soigneusement le service de fichiers statiques, vous pouvez optimiser les performances tout en maintenant un environnement sécurisé.

=== "Paramètres système"

    **Gestion des plugins et du système**

    Ces paramètres gèrent l'interaction de BunkerWeb avec des systèmes externes et contribuent à l'amélioration du produit via des statistiques d'utilisation anonymes optionnelles.

    **Rapport anonyme**

    Le rapport anonyme fournit à l'équipe de BunkerWeb des informations sur la manière dont le logiciel est utilisé. Cela aide à identifier les domaines d'amélioration et à prioriser le développement de fonctionnalités. Les rapports sont strictement statistiques et n'incluent aucune information sensible ou personnellement identifiable. Ils couvrent :

    - Les fonctionnalités activées
    - Les schémas de configuration généraux

    Vous pouvez désactiver cette fonctionnalité si vous le souhaitez en mettant `SEND_ANONYMOUS_REPORT` à `no`.

    **Plugins externes**

    Les plugins externes vous permettent d'étendre les fonctionnalités de BunkerWeb en intégrant des modules tiers. Cela permet une personnalisation supplémentaire et des cas d'utilisation avancés.

    !!! danger "Sécurité des plugins externes"
        **Les plugins externes peuvent introduire des risques de sécurité s'ils ne sont pas correctement vérifiés.** Suivez ces bonnes pratiques pour minimiser les menaces potentielles :

        - N'utilisez que des plugins provenant de sources fiables.
        - Vérifiez l'intégrité des plugins à l'aide de sommes de contrôle (checksums) lorsqu'elles sont disponibles.
        - Révisez et mettez à jour régulièrement les plugins pour garantir la sécurité et la compatibilité.

        Pour plus de détails, consultez la [documentation des Plugins](plugins.md).

    | Paramètre               | Défaut | Contexte | Multiple | Description                                                                                       |
    | ----------------------- | ------ | -------- | -------- | ------------------------------------------------------------------------------------------------- |
    | `SEND_ANONYMOUS_REPORT` | `yes`  | global   | no       | **Rapports anonymes :** Envoyer des rapports d'utilisation anonymes aux mainteneurs de BunkerWeb. |
    | `EXTERNAL_PLUGIN_URLS`  |        | global   | no       | **Plugins externes :** URL pour télécharger des plugins externes (séparées par des espaces).      |

=== "Mise en cache des fichiers"

    **Optimisation du cache de fichiers**

    Le cache de fichiers ouverts améliore les performances en stockant les descripteurs de fichiers et les métadonnées en mémoire, réduisant ainsi le besoin d'opérations répétées sur le système de fichiers.

    !!! success "Avantages de la mise en cache de fichiers"
        - **Performance :** Réduit les E/S du système de fichiers, diminue la latence et abaisse l'utilisation du CPU pour les opérations sur les fichiers.
        - **Sécurité :** Atténue les attaques par synchronisation (timing attacks) en mettant en cache les réponses d'erreur et réduit l'impact des attaques DoS ciblant le système de fichiers.

    | Paramètre                  | Défaut                  | Contexte  | Multiple | Description                                                                                                                            |
    | -------------------------- | ----------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no       | **Activer le cache :** Activer la mise en cache des descripteurs de fichiers et des métadonnées pour améliorer les performances.       |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no       | **Configuration du cache :** Configurez le cache de fichiers ouverts (ex. : nombre max d'entrées et délai d'inactivité).               |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no       | **Mettre en cache les erreurs :** Met en cache les erreurs de recherche de descripteurs de fichiers ainsi que les recherches réussies. |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no       | **Utilisations minimales :** Nombre minimum d'accès pendant la période d'inactivité pour qu'un fichier reste en cache.                 |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no       | **Validité du cache :** Temps après lequel les éléments mis en cache sont revalidés.                                                   |

    **Guide de configuration**

    Pour activer et configurer la mise en cache des fichiers :
    1. Mettez `USE_OPEN_FILE_CACHE` à `yes`.
    2. Ajustez les paramètres `OPEN_FILE_CACHE` pour définir le nombre maximum d'entrées et leur délai d'inactivité.
    3. Utilisez `OPEN_FILE_CACHE_ERRORS` pour mettre en cache les recherches réussies et échouées.
    4. Réglez `OPEN_FILE_CACHE_MIN_USES` pour spécifier le nombre d'accès requis pour qu'un fichier reste en cache.
    5. Définissez la période de validité du cache avec `OPEN_FILE_CACHE_VALID`.

    !!! tip "Bonnes pratiques"
        - Activez la mise en cache pour les sites web avec de nombreux fichiers statiques pour améliorer les performances.
        - Révisez et affinez régulièrement les paramètres de cache pour équilibrer performance et utilisation des ressources.
        - Dans les environnements dynamiques où les fichiers changent fréquemment, envisagez de réduire la période de validité du cache ou de désactiver la fonctionnalité pour garantir la fraîcheur du contenu.

### Exemples de configuration

=== "Sécurité du serveur par défaut"

    Exemple pour désactiver le serveur par défaut et forcer le SNI strict :

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "Statut HTTP en cas de refus"

    Exemple pour ignorer silencieusement les requêtes indésirables :

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "Méthodes HTTP"

    Exemple pour restreindre les méthodes HTTP à celles requises par une API RESTful :

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "Limites de taille des requêtes"

    Exemple pour limiter la taille maximale du corps d'une requête :

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "Support des protocoles"

    Exemple pour activer HTTP/2 et HTTP/3 avec un port Alt-Svc personnalisé :

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "Service de fichiers statiques"

    Exemple pour servir des fichiers statiques depuis un dossier racine personnalisé :

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "Mise en cache des fichiers"

    Exemple pour activer et optimiser la mise en cache des fichiers :

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"

## ModSecurity

Prise en charge STREAM :x:

Le plugin ModSecurity intègre le puissant pare-feu applicatif web (WAF) [ModSecurity](https://modsecurity.org) dans BunkerWeb. Cette intégration offre une protection robuste contre un large éventail d'attaques web en s'appuyant sur le [Jeu de Règles de Base OWASP (CRS)](https://coreruleset.org) pour détecter et bloquer des menaces telles que l'injection SQL, le cross-site scripting (XSS), l'inclusion de fichiers locaux, et bien plus encore.

**Comment ça marche :**

1.  Lorsqu'une requête est reçue, ModSecurity l'évalue par rapport au jeu de règles actif.
2.  Le Jeu de Règles de Base OWASP inspecte les en-têtes, les cookies, les paramètres d'URL et le contenu du corps de la requête.
3.  Chaque violation détectée contribue à un score d'anomalie global.
4.  Si ce score dépasse le seuil configuré, la requête est bloquée.
5.  Des journaux détaillés sont créés pour aider à diagnostiquer quelles règles ont été déclenchées et pourquoi.

!!! success "Bénéfices clés"

      1. **Protection standard de l'industrie :** Utilise le pare-feu open-source ModSecurity largement répandu.
      2. **Jeu de Règles de Base OWASP :** Emploie des règles maintenues par la communauté couvrant le Top Dix de l'OWASP et plus encore.
      3. **Niveaux de sécurité configurables :** Ajustez les niveaux de paranoïa pour équilibrer la sécurité avec les faux positifs potentiels.
      4. **Journalisation détaillée :** Fournit des journaux d'audit complets pour l'analyse des attaques.
      5. **Support des plugins :** Étendez la protection avec des plugins CRS optionnels adaptés à vos applications.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser ModSecurity :

1.  **Activer la fonctionnalité :** ModSecurity est activé par défaut. Cela peut être contrôlé via le paramètre `USE_MODSECURITY`.
2.  **Sélectionner une version du CRS :** Choisissez une version du Jeu de Règles de Base OWASP (v3, v4, ou nightly).
3.  **Ajouter des plugins :** Activez optionnellement des plugins CRS pour améliorer la couverture des règles.
4.  **Surveiller et ajuster :** Utilisez les journaux et l'[interface web](web-ui.md) pour identifier les faux positifs et ajuster les paramètres.

### Paramètres de configuration

| Paramètre                             | Défaut         | Contexte  | Multiple | Description                                                                                                                                                                                |
| ------------------------------------- | -------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_MODSECURITY`                     | `yes`          | multisite | no       | **Activer ModSecurity :** Active la protection du pare-feu applicatif web ModSecurity.                                                                                                     |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | no       | **Utiliser le Core Rule Set :** Active le Jeu de Règles de Base OWASP pour ModSecurity.                                                                                                    |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | no       | **Version du CRS :** La version du Jeu de Règles de Base OWASP à utiliser. Options : `3`, `4`, ou `nightly`.                                                                               |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | no       | **Moteur de règles :** Contrôle si les règles sont appliquées. Options : `On`, `DetectionOnly`, ou `Off`.                                                                                  |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | no       | **Moteur d'audit :** Contrôle le fonctionnement de la journalisation d'audit. Options : `On`, `Off`, ou `RelevantOnly`.                                                                    |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | no       | **Parties du journal d'audit :** Quelles parties des requêtes/réponses inclure dans les journaux d'audit.                                                                                  |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | no       | **Limite du corps de requête (sans fichiers) :** Taille maximale pour les corps de requête sans téléversement de fichiers. Accepte les octets bruts ou un suffixe lisible (`k`, `m`, `g`). |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | no       | **Activer les plugins CRS :** Active des jeux de règles de plugins supplémentaires pour le Core Rule Set.                                                                                  |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | no       | **Liste des plugins CRS :** Liste de plugins séparés par des espaces à télécharger et installer (`nom-plugin[/tag]` ou URL).                                                               |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | no       | **CRS Global :** Si activé, applique les règles CRS globalement au niveau HTTP plutôt que par serveur.                                                                                     |

!!! warning "ModSecurity et le Jeu de Règles de Base OWASP"
    **Nous recommandons vivement de garder ModSecurity et le Jeu de Règles de Base OWASP (CRS) activés** pour fournir une protection robuste contre les vulnérabilités web courantes. Bien que des faux positifs occasionnels puissent se produire, ils peuvent être résolus avec un peu d'effort en affinant les règles ou en utilisant des exclusions prédéfinies.

    L'équipe du CRS maintient activement une liste d'exclusions pour des applications populaires telles que WordPress, Nextcloud, Drupal et Cpanel, facilitant ainsi l'intégration sans impacter la fonctionnalité. Les avantages en matière de sécurité l'emportent de loin sur l'effort de configuration minimal requis pour traiter les faux positifs.

### Versions du CRS disponibles

Sélectionnez une version du CRS pour répondre au mieux à vos besoins de sécurité :

- **`3`** : Stable [v3.3.7](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.7).
- **`4`** : Stable [v4.21.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.21.0) (**par défaut**).
- **`nightly`** : [Version de nuit](https://github.com/coreruleset/coreruleset/releases/tag/nightly) offrant les dernières mises à jour de règles.

!!! example "Version de nuit (Nightly Build)"
    La **version de nuit** contient les règles les plus à jour, offrant les dernières protections contre les menaces émergentes. Cependant, comme elle est mise à jour quotidiennement et peut inclure des changements expérimentaux ou non testés, il est recommandé d'utiliser d'abord la version de nuit dans un **environnement de pré-production** avant de la déployer en production.

!!! tip "Niveaux de paranoïa"
    Le Jeu de Règles de Base OWASP utilise des "niveaux de paranoïa" (PL) pour contrôler la rigueur des règles :

    - **PL1 (défaut) :** Protection de base avec un minimum de faux positifs
    - **PL2 :** Sécurité renforcée avec une correspondance de motifs plus stricte
    - **PL3 :** Sécurité améliorée avec une validation plus stricte
    - **PL4 :** Sécurité maximale avec des règles très strictes (peut causer de nombreux faux positifs)

    Vous pouvez définir le niveau de paranoïa en ajoutant un fichier de configuration personnalisé dans `/etc/bunkerweb/configs/modsec-crs/`.

### Configurations personnalisées {#custom-configurations}

L'ajustement de ModSecurity et du Jeu de Règles de Base OWASP (CRS) peut être réalisé grâce à des configurations personnalisées. Celles-ci vous permettent de personnaliser le comportement à des étapes spécifiques du traitement des règles de sécurité :

- **`modsec-crs`** : Appliqué **avant** le chargement du Jeu de Règles de Base OWASP.
- **`modsec`** : Appliqué **après** le chargement du Jeu de Règles de Base OWASP. Également utilisé si le CRS n'est pas chargé du tout.
- **`crs-plugins-before`** : Appliqué **avant** le chargement des plugins CRS.
- **`crs-plugins-after`** : Appliqué **après** le chargement des plugins CRS.

Cette structure offre une grande flexibilité, vous permettant d'affiner les paramètres de ModSecurity et du CRS pour répondre aux besoins spécifiques de votre application tout en maintenant un flux de configuration clair.

#### Ajout d'exclusions CRS avec `modsec-crs`

Vous pouvez utiliser une configuration personnalisée de type `modsec-crs` pour ajouter des exclusions pour des cas d'usage spécifiques, comme l'activation d'exclusions prédéfinies pour WordPress :

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

Dans cet exemple :

- L'action est exécutée en **Phase 1** (tôt dans le cycle de vie de la requête).
- Elle active les exclusions spécifiques à WordPress du CRS en définissant la variable `tx.crs_exclusions_wordpress`.

#### Mise à jour des règles CRS avec `modsec`

Pour affiner les règles CRS chargées, vous pouvez utiliser une configuration personnalisée de type `modsec`. Par exemple, vous pouvez supprimer des règles ou des balises spécifiques pour certains chemins de requête :

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

Dans cet exemple :

- **Règle 1** : Supprime les règles avec les balises `attack-xss` et `attack-rce` pour les requêtes vers `/wp-admin/admin-ajax.php`.
- **Règle 2** : Supprime les règles avec la balise `attack-xss` pour les requêtes vers `/wp-admin/options.php`.
- **Règle 3** : Supprime une règle spécifique (ID `930120`) pour les requêtes correspondant à `/wp-json/yoast`.

!!! info "Ordre d'exécution"
    L'ordre d'exécution pour ModSecurity dans BunkerWeb est le suivant, assurant une progression claire et logique de l'application des règles :

    1.  **Configuration OWASP CRS** : Configuration de base pour le Jeu de Règles de Base OWASP.
    2.  **Configuration des plugins personnalisés (`crs-plugins-before`)** : Paramètres spécifiques aux plugins, appliqués avant toute règle CRS.
    3.  **Règles des plugins personnalisés (avant les règles CRS) (`crs-plugins-before`)** : Règles personnalisées pour les plugins exécutées avant les règles CRS.
    4.  **Configuration des plugins téléchargés** : Configuration pour les plugins téléchargés en externe.
    5.  **Règles des plugins téléchargés (avant les règles CRS)** : Règles pour les plugins téléchargés exécutées avant les règles CRS.
    6.  **Règles CRS personnalisées (`modsec-crs`)** : Règles définies par l'utilisateur appliquées avant le chargement des règles CRS.
    7.  **Règles OWASP CRS** : Le jeu de règles de sécurité de base fourni par l'OWASP.
    8.  **Règles des plugins personnalisés (après les règles CRS) (`crs-plugins-after`)** : Règles de plugins personnalisés exécutées après les règles CRS.
    9.  **Règles des plugins téléchargés (après les règles CRS)** : Règles pour les plugins téléchargés exécutées après les règles CRS.
    10. **Règles personnalisées (`modsec`)** : Règles définies par l'utilisateur appliquées après toutes les règles CRS et de plugins.

    **Notes clés** :
    - Les personnalisations **pré-CRS** (`crs-plugins-before`, `modsec-crs`) vous permettent de définir des exceptions ou des règles préparatoires avant le chargement des règles CRS de base.
    - Les personnalisations **post-CRS** (`crs-plugins-after`, `modsec`) sont idéales pour outrepasser ou étendre des règles après l'application des règles CRS et de plugins.
    - Cette structure offre une flexibilité maximale, permettant un contrôle précis de l'exécution et de la personnalisation des règles tout en maintenant une base de sécurité solide.

### Plugins OWASP CRS

Le Jeu de Règles de Base OWASP prend également en charge une gamme de **plugins** conçus pour étendre ses fonctionnalités et améliorer la compatibilité avec des applications ou des environnements spécifiques. Ces plugins peuvent aider à affiner le CRS pour une utilisation avec des plateformes populaires telles que WordPress, Nextcloud et Drupal, ou même des configurations personnalisées. Pour plus d'informations et une liste des plugins disponibles, consultez le [registre des plugins OWASP CRS](https://github.com/coreruleset/plugin-registry).

!!! tip "Téléchargement de plugins"
    Le paramètre `MODSECURITY_CRS_PLUGINS` vous permet de télécharger et d'installer des plugins pour étendre les fonctionnalités du Jeu de Règles de Base OWASP (CRS). Ce paramètre accepte une liste de noms de plugins avec des balises ou des URL optionnelles, facilitant l'intégration de fonctionnalités de sécurité supplémentaires adaptées à vos besoins spécifiques.

    Voici une liste non exhaustive des valeurs acceptées pour le paramètre `MODSECURITY_CRS_PLUGINS` :

    *   `fake-bot` - Télécharge la dernière version du plugin.
    *   `wordpress-rule-exclusions/v1.0.0` - Télécharge la version 1.0.0 du plugin.
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Télécharge le plugin directement depuis l'URL.

!!! warning "Faux positifs"
    Des paramètres de sécurité plus élevés peuvent bloquer le trafic légitime. Commencez avec les paramètres par défaut et surveillez les journaux avant d'augmenter les niveaux de sécurité. Soyez prêt à ajouter des règles d'exclusion pour les besoins spécifiques de votre application.

### Exemples de configuration

=== "Configuration de base"

    Une configuration standard avec ModSecurity et CRS v4 activés :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Mode détection uniquement"

    Configuration pour surveiller les menaces potentielles sans bloquer :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Configuration avancée avec plugins"

    Configuration avec CRS v4 et des plugins activés pour une protection supplémentaire :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Configuration héritée"

    Configuration utilisant CRS v3 pour la compatibilité avec des installations plus anciennes :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "ModSecurity Global"

    Configuration appliquant ModSecurity globalement à toutes les connexions HTTP :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Version de nuit avec plugins personnalisés"

    Configuration utilisant la version de nuit du CRS avec des plugins personnalisés :

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "Valeurs de taille lisibles"
    Pour les paramètres de taille comme `MODSECURITY_REQ_BODY_NO_FILES_LIMIT`, les suffixes `k`, `m`, et `g` (insensibles à la casse) sont pris en charge et représentent les kibioctets, mébioctets et gibioctets (multiples de 1024). Exemples : `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.

## Monitoring <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :x:

BunkerWeb monitoring pro system. This plugin is a prerequisite for some other plugins.

| Paramètre                      | Valeur par défaut | Contexte | Multiple | Description                                                                 |
| ------------------------------ | ----------------- | -------- | -------- | --------------------------------------------------------------------------- |
| `USE_MONITORING`               | `yes`             | global   | non      | Enable monitoring of BunkerWeb.                                             |
| `MONITORING_METRICS_DICT_SIZE` | `10M`             | global   | non      | Size of the dict to store monitoring metrics.                               |
| `MONITORING_IGNORE_URLS`       |                   | global   | non      | List of URLs to ignore when monitoring separated with spaces (e.g. /health) |

## Mutual TLS

Prise en charge STREAM :white_check_mark:

Le plugin Mutual TLS (mTLS) protège vos applications sensibles en exigeant que les clients présentent des certificats délivrés par des autorités que vous maîtrisez. Une fois activé, BunkerWeb authentifie les appelants avant que leurs requêtes n’atteignent vos services, ce qui sécurise vos outils internes et intégrations partenaires.

BunkerWeb évalue chaque poignée de main TLS en fonction du bundle d’AC et de la politique que vous définissez. Les clients qui ne répondent pas aux règles sont bloqués, tandis que les connexions conformes peuvent transmettre les détails du certificat aux applications amont pour une autorisation affinée.

**Fonctionnement :**

1. Le plugin surveille les échanges HTTPS du site sélectionné.
2. Pendant l’échange TLS, BunkerWeb inspecte le certificat client et vérifie sa chaîne par rapport à votre magasin de confiance.
3. Le mode de vérification détermine si les clients non authentifiés sont rejetés, acceptés avec tolérance ou autorisés pour des diagnostics.
4. (Optionnel) BunkerWeb expose le résultat via les en-têtes `X-SSL-Client-*` afin que vos applications puissent appliquer leur propre logique d’accès.

!!! success "Avantages clés"

      1. **Contrôle renforcé :** limitez l’accès aux machines et utilisateurs authentifiés.
      2. **Politiques souples :** combinez modes stricts et optionnels pour accompagner vos workflows.
      3. **Visibilité applicative :** transférez empreintes et identités de certificats pour l’audit.
      4. **Défense en profondeur :** associez mTLS aux autres plugins BunkerWeb pour multiplier les protections.

### Mise en œuvre

Suivez ces étapes pour déployer le mutual TLS sereinement :

1. **Activer la fonctionnalité :** positionnez `USE_MTLS` à `yes` sur les sites qui nécessitent l’authentification par certificat.
2. **Fournir le bundle d’AC :** stockez vos autorités de confiance dans un fichier PEM et renseignez `MTLS_CA_CERTIFICATE` avec son chemin absolu.
3. **Choisir le mode de vérification :** sélectionnez `on` pour rendre les certificats obligatoires, `optional` pour offrir un repli ou `optional_no_ca` pour un diagnostic temporaire.
4. **Ajuster la profondeur de chaîne :** adaptez `MTLS_VERIFY_DEPTH` si votre organisation utilise plusieurs intermédiaires.
5. **Transmettre le résultat (optionnel) :** laissez `MTLS_FORWARD_CLIENT_HEADERS` à `yes` si vos services amont doivent inspecter le certificat présenté.
6. **Maintenir la révocation :** si vous publiez une CRL, renseignez `MTLS_CRL` pour que BunkerWeb refuse les certificats révoqués.

### Paramètres de configuration

| Paramètre                     | Valeur par défaut | Contexte  | Multiple | Description                                                                                                                                                              |
| ----------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_MTLS`                    | `no`              | multisite | non      | **Activer le mutual TLS :** active l’authentification par certificat client pour le site courant.                                                                        |
| `MTLS_CA_CERTIFICATE`         |                   | multisite | non      | **Bundle d’AC client :** chemin absolu vers le bundle d’AC clients (PEM). Requis lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`; doit être lisible.                |
| `MTLS_VERIFY_CLIENT`          | `on`              | multisite | non      | **Mode de vérification :** choisissez si les certificats sont requis (`on`), optionnels (`optional`) ou acceptés sans validation d’AC (`optional_no_ca`).                |
| `MTLS_VERIFY_DEPTH`           | `2`               | multisite | non      | **Profondeur de vérification :** profondeur maximale de chaîne acceptée pour les certificats clients.                                                                    |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`             | multisite | non      | **Transmettre les en-têtes client :** propage les résultats de vérification (`X-SSL-Client-*` avec statut, DN, émetteur, numéro de série, empreinte, validité).          |
| `MTLS_CRL`                    |                   | multisite | non      | **Chemin de la CRL client :** chemin optionnel vers une liste de révocation de certificats encodée en PEM. Appliqué uniquement si le bundle d’AC est chargé avec succès. |

!!! tip "Maintenez les certificats à jour"
    Stockez bundles d’AC et listes de révocation dans un volume monté accessible par le Scheduler pour que chaque redémarrage récupère les ancrages de confiance récents.

!!! warning "Bundle d’AC obligatoire en mode strict"
    Lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`, le fichier d’AC doit être présent à l’exécution. S’il manque, BunkerWeb ignore les directives mTLS pour éviter un démarrage sur un chemin invalide. Réservez `optional_no_ca` au diagnostic, car ce mode affaiblit l’authentification.

!!! info "Certificat approuvé vs. vérification"
    BunkerWeb réutilise le même bundle d’AC pour vérifier les clients et bâtir la chaîne de confiance, garantissant une cohérence OCSP/CRL et durant le handshake.

### Exemples de configuration

=== "Contrôle d’accès strict"

    Exigez des certificats clients valides émis par votre AC privée et transmettez les informations de vérification au backend :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Authentification client optionnelle"

    Autorisez les utilisateurs anonymes mais transmettez les détails du certificat lorsqu’un client en présente un :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnostic sans AC"

    Autorisez les connexions à aboutir même si un certificat ne peut pas être rattaché à un bundle d’AC de confiance. Utile uniquement pour le dépannage :

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

## PHP

Prise en charge STREAM :x:

Le plugin PHP fournit l’intégration PHP‑FPM avec BunkerWeb pour exécuter du PHP dynamiquement. Il prend en charge des instances locales (même machine) et distantes, offrant de la flexibilité dans l’architecture.

Comment ça marche :

1. À la demande d’un fichier PHP, BunkerWeb route la requête vers l’instance PHP‑FPM configurée.
2. En local, la communication se fait via un socket Unix.
3. À distance, la communication utilise FastCGI vers l’hôte et le port indiqués.
4. PHP‑FPM exécute le script et renvoie la réponse à BunkerWeb qui la livre au client.
5. La réécriture d’URL est automatiquement configurée pour les frameworks/applications qui utilisent des « pretty URLs ».

### Comment l’utiliser

1. Choisissez local vs distant.
2. Connexion : chemin du socket (local) ou hôte+port (distant).
3. Racine de documents : pointez vers le dossier contenant vos fichiers PHP.

### Paramètres

| Paramètre         | Défaut | Contexte  | Multiple | Description                                                                    |
| ----------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------ |
| `REMOTE_PHP`      |        | multisite | non      | Hôte PHP‑FPM distant. Laissez vide pour utiliser le local.                     |
| `REMOTE_PHP_PATH` |        | multisite | non      | Chemin racine des fichiers côté PHP‑FPM distant.                               |
| `REMOTE_PHP_PORT` | `9000` | multisite | non      | Port PHP‑FPM distant.                                                          |
| `LOCAL_PHP`       |        | multisite | non      | Chemin du socket PHP‑FPM local. Laissez vide pour utiliser un PHP‑FPM distant. |
| `LOCAL_PHP_PATH`  |        | multisite | non      | Chemin racine des fichiers côté PHP‑FPM local.                                 |

!!! tip "Local vs distant"
    Local : meilleures perfs (socket). Distant : flexibilité et scalabilité.

!!! warning "Chemins"
    `REMOTE_PHP_PATH`/`LOCAL_PHP_PATH` doivent correspondre au chemin réel des fichiers sous peine d’erreurs « File not found ».

!!! info "Réécriture d’URL"
    Le plugin configure automatiquement la réécriture pour diriger les requêtes vers `index.php` si le fichier demandé n’existe pas.

### Exemples

=== "PHP‑FPM local"

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "PHP‑FPM distant"

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Port personnalisé"

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress"

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```

## Pro

Prise en charge STREAM :x:

Le plugin Pro regroupe des fonctionnalités avancées pour les déploiements entreprise de BunkerWeb. Il déverrouille des capacités supplémentaires, des plugins premium et des extensions qui complètent la plateforme BunkerWeb, pour plus de sécurité, de performance et d’options de gestion.

Comment ça marche :

1. Avec une clé de licence Pro valide, BunkerWeb contacte l’API Pro pour valider votre abonnement.
2. Une fois authentifié, le plugin télécharge et installe automatiquement les plugins et extensions exclusifs Pro.
3. Le statut Pro est vérifié périodiquement afin d’assurer l’accès continu aux fonctionnalités premium.
4. Les plugins premium s’intègrent de façon transparente à votre configuration existante.
5. Les fonctionnalités Pro complètent le cœur open‑source, elles ne le remplacent pas.

!!! success "Bénéfices clés"

      1. Extensions premium : accès à des plugins et fonctions exclusives.
      2. Performances accrues : configurations optimisées et mécanismes avancés de cache.
      3. Support entreprise : assistance prioritaire et canaux dédiés.
      4. Intégration fluide : cohabite avec l’édition communautaire sans conflits.
      5. Mises à jour automatiques : plugins premium téléchargés et tenus à jour automatiquement.

### Comment l’utiliser

1. Obtenir une licence : achetez une licence Pro depuis le [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc).
2. Configurer la licence : définissez `PRO_LICENSE_KEY` avec votre clé.
3. Laissez BunkerWeb faire le reste : les plugins Pro sont téléchargés et activés automatiquement.
4. Surveiller le statut Pro : vérifiez les indicateurs de santé dans l’interface [web UI](web-ui.md).

### Paramètres

| Paramètre         | Défaut | Contexte | Multiple | Description                                      |
| ----------------- | ------ | -------- | -------- | ------------------------------------------------ |
| `PRO_LICENSE_KEY` |        | global   | non      | Clé de licence BunkerWeb Pro (authentification). |

!!! tip "Gestion de licence"
    La licence est liée à votre environnement de déploiement. Pour un transfert ou une question d’abonnement, contactez le support via le [BunkerWeb Panel](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Fonctionnalités Pro"
    Le périmètre des fonctionnalités peut évoluer. Le plugin Pro gère automatiquement l’installation et la configuration des capacités disponibles.

!!! warning "Accès réseau"
    Le plugin Pro requiert un accès Internet sortant pour contacter l’API BunkerWeb (vérification de licence) et télécharger les plugins premium. Autorisez les connexions HTTPS vers `api.bunkerweb.io:443`.

### FAQ

Q : Que se passe‑t‑il si ma licence Pro expire ?

R : L’accès aux fonctionnalités premium est désactivé, mais votre installation continue de fonctionner avec l’édition communautaire. Pour réactiver les fonctionnalités Pro, renouvelez la licence.

Q : Les fonctionnalités Pro peuvent‑elles perturber ma configuration existante ?

R : Non. Elles sont conçues pour s’intégrer sans modifier votre configuration actuelle.

Q : Puis‑je essayer Pro avant achat ?

R : Oui. Deux offres existent :

- BunkerWeb PRO Standard : accès complet, sans support technique.
- BunkerWeb PRO Enterprise : accès complet, avec support dédié.

Un essai gratuit d’1 mois est disponible avec le code `freetrial`. Rendez‑vous sur le [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) pour l’activer.

## Prometheus exporter <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :x:

Prometheus exporter for BunkerWeb internal metrics.

| Paramètre                      | Valeur par défaut                                     | Contexte | Multiple | Description                                                              |
| ------------------------------ | ----------------------------------------------------- | -------- | -------- | ------------------------------------------------------------------------ |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global   | non      | Enable the Prometheus export.                                            |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global   | non      | Listening IP of the Prometheus exporter.                                 |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global   | non      | Listening port of the Prometheus exporter.                               |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global   | non      | HTTP URL of the Prometheus exporter.                                     |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global   | non      | List of IP/networks allowed to contact the Prometheus exporter endpoint. |

## Real IP

Prise en charge STREAM :warning:

Le plugin Real IP garantit que BunkerWeb identifie correctement l’adresse IP du client même derrière des proxys. Indispensable pour appliquer les règles de sécurité, la limitation de débit et des logs fiables : sinon toutes les requêtes sembleraient venir de l’IP du proxy.

Comment ça marche :

1. Activé, BunkerWeb inspecte les en‑têtes (ex. [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)) contenant l’IP d’origine.
2. Il vérifie que l’IP source figure dans `REAL_IP_FROM` (liste de proxys de confiance) pour n’accepter que les proxys légitimes.
3. L’IP client est extraite de l’en‑tête `REAL_IP_HEADER` et utilisée pour l’évaluation sécurité et la journalisation.
4. En chaînes d’IPs, une recherche récursive peut déterminer l’IP d’origine via `REAL_IP_RECURSIVE`.
5. Le support du [PROXY protocol](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) peut être activé pour recevoir l’IP client directement depuis des proxys compatibles (ex. [HAProxy](https://www.haproxy.org/)).
6. Les listes d’IP de proxys de confiance peuvent être téléchargées automatiquement via des URLs.

### Comment l’utiliser

1. Activer : `USE_REAL_IP: yes`.
2. Proxys de confiance : renseignez IP/plages dans `REAL_IP_FROM`.
3. En‑tête : indiquez lequel porte l’IP réelle via `REAL_IP_HEADER`.
4. Récursif : activez `REAL_IP_RECURSIVE` si nécessaire.
5. Sources URL : utilisez `REAL_IP_FROM_URLS` pour télécharger des listes.
6. PROXY protocol : activez `USE_PROXY_PROTOCOL` si l’amont le supporte.

!!! danger "Avertissement PROXY protocol"
    Activer `USE_PROXY_PROTOCOL` sans un amont correctement configuré pour l’émettre cassera votre application. Assurez‑vous de l’avoir configuré avant activation.

### Paramètres

| Paramètre            | Défaut                                    | Contexte  | Multiple | Description                                                                      |
| -------------------- | ----------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | non      | Activer la récupération de l’IP réelle depuis les en‑têtes ou le PROXY protocol. |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | non      | Proxys de confiance : liste d’IP/réseaux séparés par des espaces.                |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | non      | En‑tête porteur de l’IP réelle ou valeur spéciale `proxy_protocol`.              |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | non      | Recherche récursive dans un en‑tête contenant plusieurs IPs.                     |
| `REAL_IP_FROM_URLS`  |                                           | multisite | non      | URLs fournissant des IPs/réseaux de proxys de confiance (supporte `file://`).    |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | non      | Activer le support PROXY protocol pour la communication directe proxy→BunkerWeb. |

!!! tip "Fournisseurs cloud"
    Ajoutez les IP de vos load balancers (AWS/GCP/Azure…) à `REAL_IP_FROM` pour une identification correcte.

!!! danger "Considérations sécurité"
    N’ajoutez que des sources de confiance, sinon risque d’usurpation d’IP via en‑têtes manipulés.

!!! info "Multiples adresses"
    Avec `REAL_IP_RECURSIVE`, si l’en‑tête contient plusieurs IPs, la première non listée comme proxy de confiance est retenue comme IP client.

### Exemples

=== "Basique (derrière reverse proxy)"

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    ```

## Redirect

Prise en charge STREAM :x:

Le plugin Redirect fournit des redirections HTTP simples et efficaces. Il permet de rediriger des visiteurs d’une URL à une autre, pour un domaine entier, des chemins précis, avec ou sans conservation du chemin d’origine.

Comment ça marche :

1. À l’accès d’un visiteur, BunkerWeb vérifie si une redirection est définie.
2. Si activée, il redirige vers l’URL de destination.
3. Vous pouvez préserver le chemin d’origine (`REDIRECT_TO_REQUEST_URI: yes`).
4. Le code HTTP peut être `301` (permanent) ou `302` (temporaire).
5. Idéal pour migrations, canonicals, URLs obsolètes.

### Comment l’utiliser

1. Source : `REDIRECT_FROM` (ex. `/`, `/old-page`).
2. Destination : `REDIRECT_TO`.
3. Type : `REDIRECT_TO_REQUEST_URI` pour conserver le chemin.
4. Code : `REDIRECT_TO_STATUS_CODE` (`301` ou `302`).

### Paramètres

| Paramètre                 | Défaut | Contexte  | Multiple | Description                                                         |
| ------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`    | multisite | oui      | Chemin source à rediriger.                                          |
| `REDIRECT_TO`             |        | multisite | oui      | URL de destination. Laisser vide pour désactiver.                   |
| `REDIRECT_TO_REQUEST_URI` | `no`   | multisite | oui      | Conserver le chemin d'origine en l'ajoutant à l'URL de destination. |
| `REDIRECT_TO_STATUS_CODE` | `301`  | multisite | oui      | Code HTTP : `301`, `302`, `303`, `307` ou `308`.                    |

!!! tip "Choisir le bon code"
    - **`301` (Moved Permanently) :** Redirection permanente, mise en cache par les navigateurs. Peut changer POST en GET. Idéal pour migrations de domaine.
    - **`302` (Found) :** Redirection temporaire. Peut changer POST en GET.
    - **`303` (See Other) :** Redirige toujours en GET. Utile après soumission de formulaire.
    - **`307` (Temporary Redirect) :** Redirection temporaire qui préserve la méthode HTTP. Idéal pour les APIs.
    - **`308` (Permanent Redirect) :** Redirection permanente qui préserve la méthode HTTP. Pour migrations d'API permanentes.

!!! info "Conservation du chemin"
    Avec `REDIRECT_TO_REQUEST_URI: yes`, `/blog/post-1` vers `https://new.com` devient `https://new.com/blog/post-1`.

### Exemples

=== "Multiples chemins"

    ```yaml
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Domaine entier"

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Conserver le chemin"

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Temporaire"

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Sous‑domaine → chemin"

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Migration API"

    ```yaml
    REDIRECT_FROM: "/api/v1/"
    REDIRECT_TO: "https://api.example.com/v2/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "308"
    ```

=== "Après soumission de formulaire"

    ```yaml
    REDIRECT_TO: "https://example.com/merci"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "303"
    ```

## Redis

Prise en charge STREAM :white_check_mark:

Le plugin Redis intègre [Redis](https://redis.io/) ou [Valkey](https://valkey.io/) à BunkerWeb pour la mise en cache et l’accès rapide aux données. Essentiel en haute disponibilité pour partager sessions, métriques et autres informations entre plusieurs nœuds.

Comment ça marche :

1. Activé, BunkerWeb se connecte au serveur Redis/Valkey configuré.
2. Les données critiques (sessions, métriques, sécurité) y sont stockées.
3. Plusieurs instances partagent ces données pour un clustering fluide.
4. Prend en charge déploiements standalone, auth par mot de passe, SSL/TLS et Redis Sentinel.
5. Reconnexion automatique et timeouts configurables pour la robustesse.

### Comment l’utiliser

1. Activer : `USE_REDIS: yes`.
2. Connexion : hôte/IP et port.
3. Sécurité : identifiants si requis.
4. Avancé : base, SSL et timeouts.
5. Haute dispo : configurez Sentinel si utilisé.

### Paramètres

| Paramètre                 | Défaut     | Contexte | Multiple | Description                                                    |
| ------------------------- | ---------- | -------- | -------- | -------------------------------------------------------------- |
| `USE_REDIS`               | `no`       | global   | non      | Activer l’intégration Redis/Valkey (mode cluster).             |
| `REDIS_HOST`              |            | global   | non      | Hôte/IP du serveur Redis/Valkey.                               |
| `REDIS_PORT`              | `6379`     | global   | non      | Port Redis/Valkey.                                             |
| `REDIS_DATABASE`          | `0`        | global   | non      | Numéro de base (0–15).                                         |
| `REDIS_SSL`               | `no`       | global   | non      | Activer SSL/TLS.                                               |
| `REDIS_SSL_VERIFY`        | `yes`      | global   | non      | Vérifier le certificat SSL du serveur.                         |
| `REDIS_TIMEOUT`           | `5`        | global   | non      | Timeout (secondes).                                            |
| `REDIS_USERNAME`          |            | global   | non      | Nom d’utilisateur (Redis ≥ 6.0).                               |
| `REDIS_PASSWORD`          |            | global   | non      | Mot de passe.                                                  |
| `REDIS_SENTINEL_HOSTS`    |            | global   | non      | Hôtes Sentinel (séparés par espaces, `hôte:port`).             |
| `REDIS_SENTINEL_USERNAME` |            | global   | non      | Utilisateur Sentinel.                                          |
| `REDIS_SENTINEL_PASSWORD` |            | global   | non      | Mot de passe Sentinel.                                         |
| `REDIS_SENTINEL_MASTER`   | `mymaster` | global   | non      | Nom du master Sentinel.                                        |
| `REDIS_KEEPALIVE_IDLE`    | `300`      | global   | non      | Intervalle keepalive TCP (secondes) pour connexions inactives. |
| `REDIS_KEEPALIVE_POOL`    | `3`        | global   | non      | Nb max de connexions conservées dans le pool.                  |

!!! tip "Haute disponibilité"
    Configurez Redis Sentinel pour un failover automatique en production.

!!! warning "Sécurité"
    - Mots de passe forts pour Redis et Sentinel
    - Envisagez SSL/TLS
    - Ne pas exposer Redis sur Internet
    - Restreignez l’accès au port Redis (pare‑feu, segmentation)

!!! info "Prérequis pour le clustering"
    Lors du déploiement de BunkerWeb en cluster :

    - Toutes les instances BunkerWeb doivent se connecter au même serveur Redis/Valkey ou cluster Sentinel
    - Configurez le même numéro de base de données sur toutes les instances
    - Assurez-vous de la connectivité réseau entre toutes les instances BunkerWeb et les serveurs Redis/Valkey

### Exemples

=== "Configuration basique"

    Une configuration simple pour se connecter à un serveur Redis ou Valkey sur la machine locale :

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Configuration sécurisée"

    Configuration avec authentification par mot de passe et SSL activé :

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Redis Sentinel"

    Configuration pour la haute disponibilité utilisant Redis Sentinel :

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Tuning avancé"

    Configuration avec des paramètres de connexion avancés pour l'optimisation des performances :

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3"
    REDIS_KEEPALIVE_IDLE: "60"
    REDIS_KEEPALIVE_POOL: "5"
    ```

### Bonnes pratiques Redis

Lorsque vous utilisez Redis ou Valkey avec BunkerWeb, prenez en compte ces bonnes pratiques pour garantir des performances, une sécurité et une fiabilité optimales :

#### Gestion de la mémoire
- **Surveillez l'utilisation de la mémoire :** Configurez Redis avec des paramètres `maxmemory` appropriés pour éviter les erreurs de mémoire insuffisante
- **Définissez une politique d'éviction :** Utilisez une `maxmemory-policy` (par exemple, `volatile-lru` ou `allkeys-lru`) adaptée à votre cas d'utilisation
- **Évitez les clés volumineuses :** Assurez-vous que les clés Redis individuelles restent d'une taille raisonnable pour éviter la dégradation des performances

#### Persistance des données
- **Activez les instantanés RDB :** Configurez des instantanés périodiques pour la persistance des données sans impact significatif sur les performances
- **Envisagez AOF :** Pour les données critiques, activez la persistance AOF (Append-Only File) avec une politique fsync appropriée
- **Stratégie de sauvegarde :** Mettez en œuvre des sauvegardes régulières de Redis dans le cadre de votre plan de reprise après sinistre

#### Optimisation des performances
- **Pooling de connexions :** BunkerWeb l'implémente déjà, mais assurez-vous que les autres applications suivent cette pratique
- **Pipelining :** Lorsque c'est possible, utilisez le pipelining pour les opérations en masse afin de réduire la surcharge réseau
- **Évitez les opérations coûteuses :** Soyez prudent avec les commandes comme KEYS dans les environnements de production
- **Testez votre charge de travail :** Utilisez redis-benchmark pour tester vos modèles de charge de travail spécifiques

### Ressources supplémentaires

- [Documentation Redis](https://redis.io/documentation)
- [Guide de sécurité Redis](https://redis.io/topics/security)
- [Haute disponibilité Redis](https://redis.io/topics/sentinel)
- [Persistance Redis](https://redis.io/topics/persistence)

## Reporting <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


Prise en charge STREAM :x:

Regular reporting of important data from BunkerWeb (global, attacks, bans, requests, reasons, AS...). Monitoring pro plugin needed to work.

| Paramètre                      | Valeur par défaut  | Contexte | Multiple | Description                                                                                                                        |
| ------------------------------ | ------------------ | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global   | non      | Enable sending the report via email.                                                                                               |
| `USE_REPORTING_WEBHOOK`        | `no`               | global   | non      | Enable sending the report via webhook.                                                                                             |
| `REPORTING_SCHEDULE`           | `weekly`           | global   | non      | The frequency at which reports are sent.                                                                                           |
| `REPORTING_WEBHOOK_URLS`       |                    | global   | non      | List of webhook URLs to receive the report in Markdown (separated by spaces).                                                      |
| `REPORTING_SMTP_EMAILS`        |                    | global   | non      | List of email addresses to receive the report in HTML format (separated by spaces).                                                |
| `REPORTING_SMTP_HOST`          |                    | global   | non      | The host server used for SMTP sending.                                                                                             |
| `REPORTING_SMTP_PORT`          | `465`              | global   | non      | The port used for SMTP. Please note that there are different standards depending on the type of connection (SSL = 465, TLS = 587). |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global   | non      | The email address used as the sender. Note that 2FA must be disabled for this email address.                                       |
| `REPORTING_SMTP_FROM_USER`     |                    | global   | non      | The user authentication value for sending via the from email address.                                                              |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global   | non      | The password authentication value for sending via the from email address.                                                          |
| `REPORTING_SMTP_SSL`           | `SSL`              | global   | non      | Determine whether or not to use a secure connection for SMTP.                                                                      |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global   | non      | The subject line of the email.                                                                                                     |

## Reverse proxy

Prise en charge STREAM :warning:

Le plugin Reverse Proxy offre des capacités de proxy transparentes pour BunkerWeb, vous permettant de router les requêtes vers des serveurs et services backend. Cette fonctionnalité permet à BunkerWeb d'agir comme une façade sécurisée pour vos applications tout en offrant des avantages supplémentaires tels que la terminaison SSL et le filtrage de sécurité.

**Comment ça marche :**

1.  Lorsqu'un client envoie une requête à BunkerWeb, le plugin Reverse Proxy la transmet à votre serveur backend configuré.
2.  BunkerWeb ajoute des en-têtes de sécurité, applique des règles WAF et effectue d'autres contrôles de sécurité avant de transmettre les requêtes à votre application.
3.  Le serveur backend traite la requête et renvoie une réponse à BunkerWeb.
4.  BunkerWeb applique des mesures de sécurité supplémentaires à la réponse avant de la renvoyer au client.
5.  Le plugin prend en charge le proxying de flux HTTP et TCP/UDP, permettant un large éventail d'applications, y compris les WebSockets et d'autres protocoles non-HTTP.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Reverse Proxy :

1.  **Activer la fonctionnalité :** Mettez le paramètre `USE_REVERSE_PROXY` à `yes` pour activer la fonctionnalité de reverse proxy.
2.  **Configurer vos serveurs backend :** Spécifiez les serveurs en amont à l'aide du paramètre `REVERSE_PROXY_HOST`.
3.  **Ajuster les paramètres du proxy :** Affinez le comportement avec des paramètres optionnels pour les délais d'attente, les tailles de tampon, et d'autres paramètres.
4.  **Configurer les options spécifiques au protocole :** Pour les WebSockets ou des exigences HTTP spéciales, ajustez les paramètres correspondants.
5.  **Mettre en place la mise en cache (optionnel) :** Activez et configurez la mise en cache du proxy pour améliorer les performances pour le contenu fréquemment accédé.

### Guide de configuration

=== "Configuration de base"

    **Paramètres principaux**

    Les paramètres de configuration essentiels activent et contrôlent la fonctionnalité de base du reverse proxy.

    !!! success "Bénéfices du Reverse Proxy"
        - **Amélioration de la sécurité :** Tout le trafic passe par les couches de sécurité de BunkerWeb avant d'atteindre vos applications
        - **Terminaison SSL :** Gérez les certificats SSL/TLS de manière centralisée tandis que les services backend peuvent utiliser des connexions non chiffrées
        - **Gestion des protocoles :** Prise en charge de HTTP, HTTPS, WebSockets, et d'autres protocoles
        - **Interception des erreurs :** Personnalisez les pages d'erreur pour une expérience utilisateur cohérente

    | Paramètre                        | Défaut | Contexte  | Multiple | Description                                                                                                      |
    | -------------------------------- | ------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`              | `no`   | multisite | no       | **Activer le Reverse Proxy :** Mettre à `yes` pour activer la fonctionnalité de reverse proxy.                   |
    | `REVERSE_PROXY_HOST`             |        | multisite | yes      | **Hôte Backend :** URL complète de la ressource proxifiée (proxy_pass).                                          |
    | `REVERSE_PROXY_URL`              | `/`    | multisite | yes      | **URL d'emplacement :** Chemin qui sera proxifié vers le serveur backend.                                        |
    | `REVERSE_PROXY_BUFFERING`        | `yes`  | multisite | yes      | **Mise en tampon de la réponse :** Active ou désactive la mise en tampon des réponses de la ressource proxifiée. |
    | `REVERSE_PROXY_KEEPALIVE`        | `no`   | multisite | yes      | **Keep-Alive :** Active ou désactive les connexions keepalive avec la ressource proxifiée.                       |
    | `REVERSE_PROXY_CUSTOM_HOST`      |        | multisite | no       | **Hôte personnalisé :** Remplace l'en-tête Host envoyé au serveur en amont.                                      |
    | `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`  | multisite | no       | **Intercepter les erreurs :** Intercepte et réécrit les réponses d'erreur du backend.                            |

    !!! tip "Bonnes pratiques"
        - Spécifiez toujours l'URL complète dans `REVERSE_PROXY_HOST`, y compris le protocole (http:// ou https://)
        - Utilisez `REVERSE_PROXY_INTERCEPT_ERRORS` pour fournir des pages d'erreur cohérentes sur tous vos services
        - Lors de la configuration de plusieurs backends, utilisez le format de suffixe numéroté (par exemple, `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

=== "Paramètres de connexion"

    **Configuration des connexions et des délais d'attente**

    Ces paramètres contrôlent le comportement des connexions, la mise en tampon et les valeurs de délai d'attente pour les connexions proxifiées.

    !!! success "Bénéfices"
        - **Performance optimisée :** Ajustez les tailles de tampon et les paramètres de connexion en fonction des besoins de votre application
        - **Gestion des ressources :** Contrôlez l'utilisation de la mémoire grâce à des configurations de tampon appropriées
        - **Fiabilité :** Configurez des délais d'attente appropriés pour gérer les connexions lentes ou les problèmes de backend

    | Paramètre                       | Défaut | Contexte  | Multiple | Description                                                                                                        |
    | ------------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
    | `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`  | multisite | yes      | **Délai de connexion :** Temps maximum pour établir une connexion avec le serveur backend.                         |
    | `REVERSE_PROXY_READ_TIMEOUT`    | `60s`  | multisite | yes      | **Délai de lecture :** Temps maximum entre les transmissions de deux paquets successifs depuis le serveur backend. |
    | `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`  | multisite | yes      | **Délai d'envoi :** Temps maximum entre les transmissions de deux paquets successifs vers le serveur backend.      |
    | `PROXY_BUFFERS`                 |        | multisite | no       | **Tampons :** Nombre et taille des tampons pour lire la réponse du serveur backend.                                |
    | `PROXY_BUFFER_SIZE`             |        | multisite | no       | **Taille du tampon :** Taille du tampon pour lire la première partie de la réponse du serveur backend.             |
    | `PROXY_BUSY_BUFFERS_SIZE`       |        | multisite | no       | **Taille des tampons occupés :** Taille des tampons qui peuvent être occupés à envoyer une réponse au client.      |

    !!! warning "Considérations sur les délais d'attente"
        - Des délais trop courts peuvent interrompre des connexions légitimes mais lentes
        - Des délais trop longs peuvent laisser des connexions ouvertes inutilement, épuisant potentiellement les ressources
        - Pour les applications WebSocket, augmentez considérablement les délais de lecture et d'envoi (300s ou plus recommandé)

=== "Configuration SSL/TLS"

    **Paramètres SSL/TLS pour les connexions Backend**

    Ces paramètres contrôlent la manière dont BunkerWeb établit des connexions sécurisées avec les serveurs backend.

    !!! success "Bénéfices"
        - **Chiffrement de bout en bout :** Maintenez des connexions chiffrées du client au backend
        - **Validation des certificats :** Contrôlez la validation des certificats des serveurs backend
        - **Support SNI :** Spécifiez l'indication du nom du serveur (SNI) pour les backends hébergeant plusieurs sites

    | Paramètre                    | Défaut | Contexte  | Multiple | Description                                                                                    |
    | ---------------------------- | ------ | --------- | -------- | ---------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_SSL_SNI`      | `no`   | multisite | no       | **SSL SNI :** Active ou désactive l'envoi du SNI (Server Name Indication) à l'amont.           |
    | `REVERSE_PROXY_SSL_SNI_NAME` |        | multisite | no       | **Nom SSL SNI :** Définit le nom d'hôte SNI à envoyer à l'amont lorsque le SSL SNI est activé. |

    !!! info "Explication du SNI"
        L'Indication du Nom du Serveur (SNI) est une extension TLS qui permet à un client de spécifier le nom d'hôte auquel il tente de se connecter pendant la négociation. Cela permet aux serveurs de présenter plusieurs certificats sur la même adresse IP et le même port, permettant ainsi de servir plusieurs sites web sécurisés (HTTPS) à partir d'une seule adresse IP sans que tous ces sites n'utilisent le même certificat.

=== "Support des protocoles"

    **Configuration spécifique aux protocoles**

    Configurez la gestion de protocoles spéciaux, notamment pour les WebSockets et autres protocoles non-HTTP.

    !!! success "Bénéfices"
        - **Flexibilité des protocoles :** Le support des WebSockets permet des applications en temps réel
        - **Applications web modernes :** Activez des fonctionnalités interactives nécessitant une communication bidirectionnelle

    | Paramètre          | Défaut | Contexte  | Multiple | Description                                                             |
    | ------------------ | ------ | --------- | -------- | ----------------------------------------------------------------------- |
    | `REVERSE_PROXY_WS` | `no`   | multisite | yes      | **Support WebSocket :** Active le protocole WebSocket sur la ressource. |

    !!! tip "Configuration WebSocket"
        - Lors de l'activation des WebSockets avec `REVERSE_PROXY_WS: "yes"`, envisagez d'augmenter les valeurs des délais d'attente
        - Les connexions WebSocket restent ouvertes plus longtemps que les connexions HTTP typiques
        - Pour les applications WebSocket, une configuration recommandée est :
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Gestion des en-têtes"

    **Configuration des en-têtes HTTP**

    Contrôlez quels en-têtes sont envoyés aux serveurs backend et aux clients, vous permettant d'ajouter, de modifier ou de préserver des en-têtes HTTP.

    !!! success "Bénéfices"
        - **Contrôle de l'information :** Gérez précisément les informations partagées entre les clients et les backends
        - **Amélioration de la sécurité :** Ajoutez des en-têtes liés à la sécurité ou supprimez ceux qui pourraient divulguer des informations sensibles
        - **Support d'intégration :** Fournissez les en-têtes nécessaires à l'authentification et au bon fonctionnement du backend

    | Paramètre                              | Défaut    | Contexte  | Multiple | Description                                                                                       |
    | -------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_HEADERS`                |           | multisite | yes      | **En-têtes personnalisés :** En-têtes HTTP à envoyer au backend, séparés par des points-virgules. |
    | `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade` | multisite | yes      | **Cacher les en-têtes :** En-têtes HTTP à cacher aux clients lorsqu'ils sont reçus du backend.    |
    | `REVERSE_PROXY_HEADERS_CLIENT`         |           | multisite | yes      | **En-têtes client :** En-têtes HTTP à envoyer au client, séparés par des points-virgules.         |
    | `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`      | multisite | no       | **Underscores dans les en-têtes :** Active ou désactive la directive `underscores_in_headers`.    |

    !!! warning "Considérations de sécurité"
        Lors de l'utilisation de la fonctionnalité de reverse proxy, soyez prudent quant aux en-têtes que vous transmettez à vos applications backend. Certains en-têtes peuvent exposer des informations sensibles sur votre infrastructure ou contourner les contrôles de sécurité.

    !!! example "Exemples de format d'en-tête"
        En-têtes personnalisés vers les serveurs backend :
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        En-têtes personnalisés vers les clients :
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Authentification"

    **Configuration de l'authentification externe**

    Intégrez avec des systèmes d'authentification externes pour centraliser la logique d'autorisation à travers vos applications.

    !!! success "Bénéfices"
        - **Authentification centralisée :** Mettez en œuvre un point d'authentification unique pour plusieurs applications
        - **Sécurité cohérente :** Appliquez des politiques d'authentification uniformes sur différents services
        - **Contrôle amélioré :** Transmettez les détails d'authentification aux applications backend via des en-têtes ou des variables

    | Paramètre                               | Défaut | Contexte  | Multiple | Description                                                                                               |
    | --------------------------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_AUTH_REQUEST`            |        | multisite | yes      | **Requête d'authentification :** Active l'authentification via un fournisseur externe.                    |
    | `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |        | multisite | yes      | **URL de connexion :** Redirige les clients vers l'URL de connexion en cas d'échec de l'authentification. |
    | `REVERSE_PROXY_AUTH_REQUEST_SET`        |        | multisite | yes      | **Variables d'authentification :** Variables à définir à partir du fournisseur d'authentification.        |

    !!! tip "Intégration de l'authentification"
        - La fonctionnalité de requête d'authentification permet la mise en œuvre de microservices d'authentification centralisés
        - Votre service d'authentification doit renvoyer un code de statut 200 pour une authentification réussie ou 401/403 en cas d'échec
        - Utilisez la directive auth_request_set pour extraire et transmettre des informations du service d'authentification

=== "Configuration avancée"

    **Options de configuration supplémentaires**

    Ces paramètres offrent une personnalisation plus poussée du comportement du reverse proxy pour des scénarios spécialisés.

    !!! success "Bénéfices"
        - **Personnalisation :** Incluez des extraits de configuration supplémentaires pour des exigences complexes
        - **Optimisation des performances :** Affinez la gestion des requêtes pour des cas d'usage spécifiques
        - **Flexibilité :** Adaptez-vous aux exigences uniques de l'application avec des configurations spécialisées

    | Paramètre                         | Défaut | Contexte  | Multiple | Description                                                                                           |
    | --------------------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |        | multisite | yes      | **Configurations supplémentaires :** Incluez des configurations additionnelles dans le bloc location. |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`  | multisite | yes      | **Passer le corps de la requête :** Active ou désactive la transmission du corps de la requête.       |

    !!! warning "Considérations de sécurité"
        Soyez prudent lorsque vous incluez des extraits de configuration personnalisés car ils peuvent outrepasser les paramètres de sécurité de BunkerWeb ou introduire des vulnérabilités s'ils ne sont pas correctement configurés.

=== "Configuration du cache"

    **Paramètres de mise en cache des réponses**

    Améliorez les performances en mettant en cache les réponses des serveurs backend, réduisant ainsi la charge et améliorant les temps de réponse.

    !!! success "Bénéfices"
        - **Performance :** Réduisez la charge sur les serveurs backend en servant du contenu mis en cache
        - **Latence réduite :** Temps de réponse plus rapides pour le contenu fréquemment demandé
        - **Économies de bande passante :** Minimisez le trafic réseau interne en mettant en cache les réponses
        - **Personnalisation :** Configurez exactement quoi, quand et comment le contenu est mis en cache

    | Paramètre                    | Défaut                             | Contexte  | Multiple | Description                                                                                                      |
    | ---------------------------- | ---------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `USE_PROXY_CACHE`            | `no`                               | multisite | no       | **Activer le cache :** Mettre à `yes` pour activer la mise en cache des réponses du backend.                     |
    | `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | no       | **Niveaux de chemin du cache :** Comment structurer la hiérarchie du répertoire de cache.                        |
    | `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | no       | **Taille de la zone de cache :** Taille de la zone de mémoire partagée utilisée pour les métadonnées du cache.   |
    | `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | no       | **Paramètres du chemin de cache :** Paramètres supplémentaires pour le chemin de cache.                          |
    | `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | no       | **Méthodes de cache :** Méthodes HTTP qui peuvent être mises en cache.                                           |
    | `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | no       | **Utilisations min. pour cache :** Nombre minimum de requêtes avant qu'une réponse ne soit mise en cache.        |
    | `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | no       | **Clé de cache :** La clé utilisée pour identifier de manière unique une réponse mise en cache.                  |
    | `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | no       | **Validité du cache :** Durée de mise en cache pour des codes de réponse spécifiques.                            |
    | `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | no       | **Pas de cache :** Conditions pour ne pas mettre en cache les réponses même si elles sont normalement cachables. |
    | `PROXY_CACHE_BYPASS`         | `0`                                | multisite | no       | **Contournement du cache :** Conditions sous lesquelles contourner le cache.                                     |

    !!! tip "Bonnes pratiques de mise en cache"
        - Ne mettez en cache que le contenu qui ne change pas fréquemment ou qui n'est pas personnalisé
        - Utilisez des durées de cache appropriées en fonction du type de contenu (les ressources statiques peuvent être mises en cache plus longtemps)
        - Configurez `PROXY_NO_CACHE` pour éviter de mettre en cache du contenu sensible ou personnalisé
        - Surveillez les taux de réussite du cache et ajustez les paramètres en conséquence

!!! danger "Utilisateurs de Docker Compose - Variables NGINX"
    Lorsque vous utilisez Docker Compose avec des variables NGINX dans vos configurations, vous devez échapper le signe dollar (`$`) en utilisant des doubles signes dollar (`$$`). Cela s'applique à tous les paramètres contenant des variables NGINX comme `$remote_addr`, `$proxy_add_x_forwarded_for`, etc.

    Sans cet échappement, Docker Compose essaiera de substituer ces variables par des variables d'environnement, qui n'existent généralement pas, ce qui entraînera des valeurs vides dans votre configuration NGINX.

### Exemples de configuration

=== "Proxy HTTP de base"

    Une configuration simple pour proxifier les requêtes HTTP vers un serveur d'application backend :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "Application WebSocket"

    Configuration optimisée pour une application WebSocket avec des délais d'attente plus longs :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Emplacements multiples"

    Configuration pour router différents chemins vers différents services backend :

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # Backend API
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Backend Admin
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Application Frontend
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Configuration du cache"

    Configuration avec mise en cache du proxy activée pour de meilleures performances :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Gestion avancée des en-têtes"

    Configuration avec manipulation personnalisée des en-têtes :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # En-têtes personnalisés vers le backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # En-têtes personnalisés vers le client
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Intégration de l'authentification"

    Configuration avec authentification externe :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Configuration de l'authentification
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Backend du service d'authentification
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```

## Reverse scan

Prise en charge STREAM :white_check_mark:

Le plugin Reverse Scan protège contre les tentatives de contournement via proxy en scannant certains ports côté client pour détecter des proxys/serveurs ouverts. Il aide à identifier et bloquer les clients qui tentent de masquer leur identité ou leur origine.

Comment ça marche :

1. À la connexion d’un client, BunkerWeb tente de scanner des ports spécifiques sur l’IP du client.
2. Les ports de proxy courants (80, 443, 8080, etc.) sont vérifiés.
3. Si des ports ouverts sont détectés (signe d’un proxy), la connexion est refusée.
4. Cela ajoute une couche contre bots/outils automatisés et utilisateurs malveillants.

### Comment l’utiliser

1. Activer : `USE_REVERSE_SCAN: yes`.
2. Ports : personnalisez `REVERSE_SCAN_PORTS`.
3. Timeout : ajustez `REVERSE_SCAN_TIMEOUT` pour l’équilibre sécurité/performance.
4. Suivi : consultez les logs et la [web UI](web-ui.md).

### Paramètres

| Paramètre              | Défaut                     | Contexte  | Multiple | Description                                 |
| ---------------------- | -------------------------- | --------- | -------- | ------------------------------------------- |
| `USE_REVERSE_SCAN`     | `no`                       | multisite | non      | Activer l’analyse des ports côté client.    |
| `REVERSE_SCAN_PORTS`   | `22 80 443 3128 8000 8080` | multisite | non      | Ports à vérifier (séparés par des espaces). |
| `REVERSE_SCAN_TIMEOUT` | `500`                      | multisite | non      | Délai max par port en millisecondes.        |

!!! warning "Performance"
    Scanner de nombreux ports ajoute de la latence. Limitez la liste et adaptez le timeout.

!!! info "Ports de proxy courants"
    La configuration par défaut inclut 80, 443, 8080, 3128 et SSH (22). Adaptez selon votre modèle de menace.

### Exemples

=== "Basique"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "500"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Approfondi"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1000"
    REVERSE_SCAN_PORTS: "22 80 443 3128 8080 8000 8888 1080 3333 8081"
    ```

=== "Optimisé performance"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "250"
    REVERSE_SCAN_PORTS: "80 443 8080"
    ```

=== "Haute sécurité"

    ```yaml
    USE_REVERSE_SCAN: "yes"
    REVERSE_SCAN_TIMEOUT: "1500"
    REVERSE_SCAN_PORTS: "22 25 80 443 1080 3128 3333 4444 5555 6588 6666 7777 8000 8080 8081 8800 8888 9999"
    ```

## Robots.txt

Prise en charge STREAM :white_check_mark:

Le plugin Robots.txt gère le fichier [robots.txt](https://www.robotstxt.org/) de votre site, indiquant aux robots les zones autorisées/interdites.

Comment ça marche :

Activé, BunkerWeb génère dynamiquement `/robots.txt` à la racine. Les règles sont agrégées dans l’ordre :

1. DarkVisitors (si `ROBOTSTXT_DARKVISITORS_TOKEN`) : bloque des bots/IA connus selon `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` et `ROBOTSTXT_DARKVISITORS_DISALLOW`.
2. Listes communautaires (`ROBOTSTXT_COMMUNITY_LISTS`).
3. URLs personnalisées (`ROBOTSTXT_URLS`).
4. Règles manuelles (`ROBOTSTXT_RULE[_N]`).

Ensuite, les règles à ignorer (`ROBOTSTXT_IGNORE_RULE[_N]`, PCRE) sont filtrées. S’il ne reste rien, un `User-agent: *` + `Disallow: /` par défaut est appliqué. Des sitemaps (`ROBOTSTXT_SITEMAP[_N]`) peuvent être ajoutés.

### DarkVisitors

[DarkVisitors](https://darkvisitors.com/) fournit un `robots.txt` dynamique pour bloquer des bots/IA. Inscrivez‑vous et obtenez un bearer token.

### Comment l’utiliser

1. Activer : `USE_ROBOTSTXT: yes`.
2. Règles : via DarkVisitors, listes communautaires, URLs ou variables `ROBOTSTXT_RULE`.
3. Filtrer (optionnel) : `ROBOTSTXT_IGNORE_RULE_N`.
4. Sitemaps (optionnel) : `ROBOTSTXT_SITEMAP_N`.
5. Accès : `http(s)://votre-domaine/robots.txt`.

### Paramètres

| Paramètre                            | Défaut | Contexte  | Multiple | Description                                                          |
| ------------------------------------ | ------ | --------- | -------- | -------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`   | multisite | non      | Active/désactive la fonctionnalité.                                  |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |        | multisite | non      | Jeton Bearer pour l’API DarkVisitors.                                |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |        | multisite | non      | Types d’agents (séparés par virgules) à inclure depuis DarkVisitors. |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`    | multisite | non      | Valeur du champ Disallow envoyée à l’API DarkVisitors.               |
| `ROBOTSTXT_COMMUNITY_LISTS`          |        | multisite | non      | IDs de listes communautaires (séparés par espaces).                  |
| `ROBOTSTXT_URLS`                     |        | multisite | non      | URLs supplémentaires (supporte `file://` et auth basique).           |
| `ROBOTSTXT_RULE`                     |        | multisite | oui      | Règle individuelle `robots.txt`.                                     |
| `ROBOTSTXT_HEADER`                   |        | multisite | oui      | En‑tête (peut être encodé Base64).                                   |
| `ROBOTSTXT_FOOTER`                   |        | multisite | oui      | Pied de page (peut être encodé Base64).                              |
| `ROBOTSTXT_IGNORE_RULE`              |        | multisite | oui      | Motif PCRE d’ignorance de règles.                                    |
| `ROBOTSTXT_SITEMAP`                  |        | multisite | oui      | URL de sitemap.                                                      |

### Exemples

Basique (manuel)

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

Sources dynamiques (DarkVisitors + liste)

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

Combiné

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

En‑tête/Pied de page

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# This is a custom header"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# This is a custom footer"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

Pour en savoir plus : [documentation robots.txt](https://www.robotstxt.org/robotstxt.html).

## SSL

Prise en charge STREAM :white_check_mark:

Le plugin SSL fournit un chiffrement SSL/TLS robuste pour vos sites protégés par BunkerWeb. Il permet des connexions HTTPS sécurisées en configurant protocoles, suites cryptographiques et paramètres associés.

Comment ça marche :

1. Lors d’une connexion HTTPS, BunkerWeb gère la négociation SSL/TLS selon vos réglages.
2. Le plugin impose des protocoles modernes et des suites fortes, et désactive les options vulnérables.
3. Des paramètres de session optimisés améliorent les performances sans sacrifier la sécurité.
4. La présentation des certificats suit les bonnes pratiques pour compatibilité et sécurité.

### Comment l’utiliser

1. Protocoles : choisissez les versions via `SSL_PROTOCOLS`.
2. Suites : sélectionnez un niveau via `SSL_CIPHERS_LEVEL` ou des suites personnalisées via `SSL_CIPHERS_CUSTOM`.
3. Redirections : configurez la redirection HTTP→HTTPS avec `AUTO_REDIRECT_HTTP_TO_HTTPS` et/ou `REDIRECT_HTTP_TO_HTTPS`.

### Paramètres

| Paramètre                     | Défaut            | Contexte  | Multiple | Description                                                                                    |
| ----------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | non      | Rediriger tout HTTP vers HTTPS.                                                                |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | non      | Redirection auto si HTTPS détecté.                                                             |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | non      | Protocoles SSL/TLS supportés (séparés par des espaces).                                        |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | non      | Niveau de sécurité des suites (`modern`, `intermediate`, `old`).                               |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | non      | Suites personnalisées (liste séparée par `:`) qui remplacent le niveau.                        |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | multisite | non      | Taille du cache de session SSL (ex. `10m`, `512k`). Définir à `off` ou `none` pour désactiver. |

!!! tip "Test SSL Labs"
    Testez votre configuration via [Qualys SSL Labs](https://www.ssllabs.com/ssltest/). Une configuration BunkerWeb bien réglée atteint généralement A+.

!!! warning "Protocoles anciens"
    SSLv3, TLSv1.0 et TLSv1.1 sont désactivés par défaut (vulnérabilités connues). Activez‑les uniquement si nécessaire pour clients hérités.

### Exemples

=== "Sécurité moderne (défaut)"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Sécurité maximale"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Compatibilité héritée"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Suites personnalisées"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

## Security.txt

Prise en charge STREAM :white_check_mark:

Le plugin Security.txt met en œuvre le standard [Security.txt](https://securitytxt.org/) ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) sur votre site. Il facilite l’accès aux politiques de sécurité et fournit un moyen standardisé de signaler des vulnérabilités.

Comment ça marche :

1. Une fois activé, BunkerWeb expose `/.well-known/security.txt` à la racine du site.
2. Le fichier contient vos politiques, contacts et informations pertinentes.
3. Les chercheurs en sécurité et outils automatisés le trouvent à l’emplacement standard.
4. Le contenu est défini via des paramètres simples (contacts, clés de chiffrement, politiques, remerciements…).
5. BunkerWeb formate automatiquement selon la RFC 9116.

### Comment l’utiliser

1. Activer : `USE_SECURITYTXT: yes`.
2. Contacts : précisez au moins un moyen de contact via `SECURITYTXT_CONTACT`.
3. Informations additionnelles : configurez expiration, chiffrement, remerciements, URL de politique…

### Paramètres

| Paramètre                      | Défaut                      | Contexte  | Multiple | Description                                                 |
| ------------------------------ | --------------------------- | --------- | -------- | ----------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | non      | Activer le fichier security.txt.                            |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | non      | URI d’accès au fichier.                                     |
| `SECURITYTXT_CONTACT`          |                             | multisite | oui      | Moyens de contact (ex. `mailto:security@example.com`).      |
| `SECURITYTXT_EXPIRES`          |                             | multisite | non      | Date d’expiration (format ISO 8601).                        |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | oui      | URL de clés de chiffrement pour échanges sécurisés.         |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | oui      | URL de remerciements pour les chercheurs.                   |
| `SECURITYTXT_POLICY`           |                             | multisite | oui      | URL de la politique de sécurité (procédure de signalement). |
| `SECURITYTXT_HIRING`           |                             | multisite | oui      | URL d’offres d’emploi sécurité.                             |
| `SECURITYTXT_CANONICAL`        |                             | multisite | oui      | URL canonique du fichier security.txt.                      |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | non      | Langue préférée (code ISO 639‑1).                           |
| `SECURITYTXT_CSAF`             |                             | multisite | oui      | Lien vers le provider-metadata.json du fournisseur CSAF.    |

!!! warning "Expiration requise"
    Le champ `Expires` est obligatoire. Si absent, BunkerWeb définit par défaut une expiration à un an.

!!! info "Contacts essentiels"
    Fournissez au moins un moyen de contact : email, formulaire, téléphone, etc.

!!! warning "HTTPS obligatoire"
    Toutes les URLs (sauf `mailto:` et `tel:`) DOIVENT utiliser HTTPS. BunkerWeb convertit les URL non‑HTTPS pour la conformité.

### Exemples

=== "Basique"

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Complet"

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Contacts multiples"

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```

## Self-signed certificate

Prise en charge STREAM :white_check_mark:

Le plugin Certificat auto‑signé génère et gère automatiquement des certificats SSL/TLS directement dans BunkerWeb, pour activer HTTPS sans autorité de certification externe. Idéal en développement, réseaux internes ou déploiements rapides d’HTTPS.

Comment ça marche :

1. Une fois activé, BunkerWeb génère un certificat auto‑signé pour vos domaines configurés.
2. Le certificat inclut tous les noms de serveurs définis, assurant une validation correcte.
3. Les certificats sont stockés de façon sécurisée et chiffrent tout le trafic HTTPS.
4. Le renouvellement est automatique avant expiration.

!!! warning "Avertissements navigateurs"
    Les navigateurs afficheront des alertes de sécurité car un certificat auto‑signé n’est pas émis par une AC de confiance. En production, préférez [Let’s Encrypt](#lets-encrypt).

### Comment l’utiliser

1. Activer : `GENERATE_SELF_SIGNED_SSL: yes`.
2. Algorithme : choisissez via `SELF_SIGNED_SSL_ALGORITHM`.
3. Validité : durée en jours via `SELF_SIGNED_SSL_EXPIRY`.
4. Sujet : champ subject via `SELF_SIGNED_SSL_SUBJ`.

!!! tip "Mode stream"
    En mode stream, configurez `LISTEN_STREAM_PORT_SSL` pour définir le port d’écoute SSL/TLS.

### Paramètres

| Paramètre                   | Défaut                 | Contexte  | Multiple | Description                                                           |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | non      | Activer la génération automatique de certificats auto‑signés.         |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | non      | Algorithme : `ec-prime256v1`, `ec-secp384r1`, `rsa-2048`, `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | non      | Validité (jours).                                                     |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | non      | Sujet du certificat (identifiant le domaine).                         |

### Exemples

=== "Basique"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Certificats courte durée"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Test en RSA"

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```

## Sessions

Prise en charge STREAM :white_check_mark:

Le plugin Sessions fournit une gestion robuste des sessions HTTP dans BunkerWeb pour suivre de manière sécurisée l’état utilisateur entre requêtes. Indispensable pour la persistance d’authentification et des fonctionnalités comme la [protection antibot](#antibot).

Comment ça marche :

1. À la première interaction, BunkerWeb crée un identifiant de session unique.
2. Il est stocké de manière sécurisée dans un cookie navigateur.
3. Aux requêtes suivantes, l’identifiant permet d’accéder aux données de session.
4. Le stockage peut être local ou dans [Redis](#redis) en environnement distribué.
5. Les sessions sont gérées automatiquement avec des timeouts configurables.
6. Un secret cryptographique signe les cookies de session.

### Comment l’utiliser

1. Secret : définissez un `SESSIONS_SECRET` fort et unique.
2. Nom : personnalisez `SESSIONS_NAME` si souhaité.
3. Délais : ajustez `SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`.
4. Cluster : activez `USE_REDIS: yes` et configurez Redis pour partager les sessions entre nœuds.

### Paramètres

| Paramètre                   | Défaut   | Contexte | Multiple | Description                                              |
| --------------------------- | -------- | -------- | -------- | -------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global   | non      | Clé de signature des cookies (forte, aléatoire, unique). |
| `SESSIONS_NAME`             | `random` | global   | non      | Nom du cookie de session.                                |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global   | non      | Inactivité max (secondes) avant invalidation.            |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global   | non      | Durée max (secondes) avant renouvellement obligatoire.   |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global   | non      | Durée max (secondes) avant destruction, activité ou non. |
| `SESSIONS_CHECK_IP`         | `yes`    | global   | non      | Détruire la session si l’IP change.                      |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global   | non      | Détruire la session si l’User‑Agent change.              |

!!! warning "Sécurité" - `SESSIONS_SECRET` doit être fort (≥32 caractères), confidentiel et identique sur toutes les instances. - Utilisez des variables d’environnement/secrets pour éviter le clair.

!!! tip "Clusters" - `USE_REDIS: yes` et même `SESSIONS_SECRET`/`SESSIONS_NAME` sur tous les nœuds.

### Exemples

=== "Basique (instance unique)"

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "myappsession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Sécurité renforcée"

    ```yaml
    SESSIONS_SECRET: "your-very-strong-random-secret-key-here"
    SESSIONS_NAME: "securesession"
    SESSIONS_IDLING_TIMEOUT: "900"
    SESSIONS_ROLLING_TIMEOUT: "1800"
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Cluster + Redis"

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "clustersession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Configurez la connexion Redis
    ```

=== "Sessions longue durée"

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "persistentsession"
    SESSIONS_IDLING_TIMEOUT: "86400"
    SESSIONS_ROLLING_TIMEOUT: "172800"
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"
    ```

## UI

Prise en charge STREAM :x:

Integrate easily the BunkerWeb UI.

| Paramètre | Valeur par défaut | Contexte  | Multiple | Description                                  |
| --------- | ----------------- | --------- | -------- | -------------------------------------------- |
| `USE_UI`  | `no`              | multisite | non      | Use UI                                       |
| `UI_HOST` |                   | global    | non      | Address of the web UI used for initial setup |

## User Manager <img src='../../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style='transform : translateY(3px);'> (PRO)


<p align='center'><iframe style='display: block;' width='560' height='315' data-src='https://www.youtube-nocookie.com/embed/EIohiUf9Fg4' title='Gestionnaire d'utilisateurs' frameborder='0' allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture' allowfullscreen></iframe></p>

Prise en charge STREAM :x:

Add the possibility to manage users on the web interface

| Paramètre           | Valeur par défaut | Contexte | Multiple | Description                                     |
| ------------------- | ----------------- | -------- | -------- | ----------------------------------------------- |
| `USERS_REQUIRE_2FA` | `no`              | global   | non      | Require two-factor authentication for all users |

## Whitelist

Prise en charge STREAM :warning:

Le plugin Whitelist vous permet de définir des clients de confiance qui contournent les autres filtres de sécurité. Les visiteurs correspondant aux règles sont immédiatement autorisés et passent avant les autres contrôles. Pour bloquer des clients indésirables, voir [Blacklist](#blacklist).

Comment ça marche :

1. Vous définissez des critères (IP/réseaux, rDNS, ASN, User‑Agent, URI).
2. Si un visiteur correspond à une règle (et pas à une règle d’ignore), il est autorisé et bypass tous les contrôles.
3. Sinon, il suit le parcours de sécurité standard.
4. Les listes peuvent être mises à jour automatiquement depuis des sources externes.

!!! info "Mode stream"
    En stream, uniquement IP, rDNS et ASN sont évalués.

### Paramètres

Général

| Paramètre       | Défaut | Contexte  | Multiple | Description           |
| --------------- | ------ | --------- | -------- | --------------------- |
| `USE_WHITELIST` | `no`   | multisite | non      | Activer la whitelist. |

=== "Adresse IP"

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                          |
    | -------------------------- | ------ | --------- | -------- | ---------------------------------------------------- |
    | `WHITELIST_IP`             |        | multisite | non      | IP/réseaux (CIDR) autorisés.                         |
    | `WHITELIST_IGNORE_IP`      |        | multisite | non      | IP/réseaux ignorés (bypassent les vérifications IP). |
    | `WHITELIST_IP_URLS`        |        | multisite | non      | URLs contenant IP/réseaux à autoriser.               |
    | `WHITELIST_IGNORE_IP_URLS` |        | multisite | non      | URLs contenant IP/réseaux à ignorer.                 |

=== "Reverse DNS"

    | Paramètre                    | Défaut | Contexte  | Multiple | Description                                  |
    | ---------------------------- | ------ | --------- | -------- | -------------------------------------------- |
    | `WHITELIST_RDNS`             |        | multisite | non      | Suffixes rDNS autorisés.                     |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`  | multisite | non      | Vérifier seulement les IP globales si `yes`. |
    | `WHITELIST_IGNORE_RDNS`      |        | multisite | non      | Suffixes rDNS ignorés.                       |
    | `WHITELIST_RDNS_URLS`        |        | multisite | non      | URLs contenant des suffixes rDNS autorisés.  |
    | `WHITELIST_IGNORE_RDNS_URLS` |        | multisite | non      | URLs contenant des suffixes rDNS à ignorer.  |

=== "ASN"

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                          |
    | --------------------------- | ------ | --------- | -------- | ------------------------------------ |
    | `WHITELIST_ASN`             |        | multisite | non      | Numéros d’AS autorisés.              |
    | `WHITELIST_IGNORE_ASN`      |        | multisite | non      | AS ignorés (bypassent la vérif ASN). |
    | `WHITELIST_ASN_URLS`        |        | multisite | non      | URLs de listes d’AS autorisés.       |
    | `WHITELIST_IGNORE_ASN_URLS` |        | multisite | non      | URLs de listes d’AS à ignorer.       |

=== "User‑Agent"

    | Paramètre                          | Défaut | Contexte  | Multiple | Description                                  |
    | ---------------------------------- | ------ | --------- | -------- | -------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |        | multisite | non      | Motifs (regex PCRE) de User‑Agent autorisés. |
    | `WHITELIST_IGNORE_USER_AGENT`      |        | multisite | non      | Motifs ignorés.                              |
    | `WHITELIST_USER_AGENT_URLS`        |        | multisite | non      | URLs de motifs User‑Agent autorisés.         |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |        | multisite | non      | URLs de motifs User‑Agent à ignorer.         |

=== "URI"

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                          |
    | --------------------------- | ------ | --------- | -------- | ------------------------------------ |
    | `WHITELIST_URI`             |        | multisite | non      | Motifs d’URI (regex PCRE) autorisés. |
    | `WHITELIST_IGNORE_URI`      |        | multisite | non      | Motifs d’URI ignorés.                |
    | `WHITELIST_URI_URLS`        |        | multisite | non      | URLs de motifs d’URI autorisés.      |
    | `WHITELIST_IGNORE_URI_URLS` |        | multisite | non      | URLs de motifs d’URI à ignorer.      |

### Travailler avec des fichiers de listes locaux

Les paramètres `*_URLS` fournis par les plugins Whitelist, Greylist et Blacklist utilisent le même téléchargeur. Lorsque vous référencez une URL `file:///` :

- Le chemin est résolu dans le conteneur du **scheduler** (dans un déploiement Docker il s’agit généralement de `bunkerweb-scheduler`). Montez-y vos fichiers et vérifiez que l’utilisateur scheduler possède un accès en lecture.
- Chaque fichier est un texte encodé en UTF-8 avec une entrée par ligne. Les lignes vides sont ignorées et les commentaires doivent commencer par `#` ou `;`. Les commentaires `//` ne sont pas pris en charge.
- Valeur attendue selon le type de liste :
  - **Listes IP** acceptent des adresses IPv4/IPv6 ou des réseaux CIDR (par exemple `192.0.2.10` ou `2001:db8::/48`).
  - **Listes rDNS** attendent un suffixe sans espaces (par exemple `.search.msn.com`). Les valeurs sont automatiquement converties en minuscules.
  - **Listes ASN** peuvent contenir uniquement le numéro (`32934`) ou le numéro préfixé par `AS` (`AS15169`).
  - **Listes User-Agent** sont traitées comme des motifs PCRE et la ligne complète est conservée (espaces compris). Placez vos commentaires sur une ligne séparée pour éviter qu’ils ne soient interprétés comme motif.
  - **Listes URI** doivent commencer par `/` et peuvent utiliser des jetons PCRE tels que `^` ou `$`.

Exemples de fichiers conformes :

```text
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
