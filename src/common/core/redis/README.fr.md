Le plugin Redis intègre [Redis](https://redis.io/) ou [Valkey](https://valkey.io/) à BunkerWeb pour la mise en cache et l’accès rapide aux données. Essentiel en haute disponibilité pour partager sessions, métriques et autres informations entre plusieurs nœuds.

Comment ça marche :

1. Activé, BunkerWeb se connecte au serveur Redis/Valkey configuré.
2. Les données critiques (sessions, métriques, sécurité) y sont stockées.
3. Plusieurs instances partagent ces données pour un clustering fluide.
4. Prend en charge déploiements standalone, auth par mot de passe, SSL/TLS et Redis Sentinel.
5. Reconnexion automatique et timeouts configurables pour la robustesse.

### Comment l’utiliser

1. Activer : mettez le paramètre `USE_REDIS` à `yes`.
2. Connexion : hôte/IP et port.
3. Sécurité : identifiants si requis.
4. Avancé : base, SSL et timeouts.
5. Haute dispo : configurez Sentinel si utilisé.

### Paramètres

| Paramètre                 | Défaut     | Contexte | Multiple | Description                                                    |
| ------------------------- | ---------- | -------- | -------- | -------------------------------------------------------------- |
| `USE_REDIS`               | `no`       | global   | non      | Activer l’intégration Redis/Valkey (mode cluster).             |
| `REDIS_HOST`              |            | global   | non      | Hôte/IP du serveur Redis/Valkey. Inutile lorsque `REDIS_SENTINEL_HOSTS` est défini (le master est résolu via les Sentinels). |
| `REDIS_PORT`              | `6379`     | global   | non      | Port Redis/Valkey.                                             |
| `REDIS_DATABASE`          | `0`        | global   | non      | Numéro de base (0–15).                                         |
| `REDIS_SSL`               | `no`       | global   | non      | Activer SSL/TLS.                                               |
| `REDIS_SSL_VERIFY`        | `no`       | global   | non      | Vérifier le certificat SSL du serveur.                         |
| `REDIS_TIMEOUT`           | `1s`       | global   | non      | Timeout (ms) pour connexion/lecture/écriture. Accepte un suffixe de durée (ms, s, m, h, d, w, M, y) ; un nombre sans suffixe est en millisecondes. |
| `REDIS_USERNAME`          |            | global   | non      | Nom d’utilisateur (Redis ≥ 6.0).                               |
| `REDIS_PASSWORD`          |            | global   | non      | Mot de passe.                                                  |
| `REDIS_CLUSTER_NODES`     |            | global   | non      | Nœuds de départ d’un cluster Redis, `hôte[:port]` séparés par espaces, `[ipv6]:port` pour IPv6. Active le mode cluster. |
| `REDIS_SENTINEL_HOSTS`    |            | global   | non      | Hôtes Sentinel (séparés par espaces, `hôte:port`).             |
| `REDIS_SENTINEL_USERNAME` |            | global   | non      | Utilisateur Sentinel.                                          |
| `REDIS_SENTINEL_PASSWORD` |            | global   | non      | Mot de passe Sentinel.                                         |
| `REDIS_SENTINEL_MASTER`   |            | global   | non      | Nom du master Sentinel.                                        |
| `REDIS_KEEPALIVE_IDLE`    | `30s`      | global   | non      | Temps d’inactivité max (ms) avant fermeture d’une connexion du pool. Accepte un suffixe de durée (ms, s, m, h, d, w, M, y) ; un nombre sans suffixe est en millisecondes. |
| `REDIS_KEEPALIVE_POOL`    | `64`       | global   | non      | Nb max de connexions conservées dans le pool, par worker NGINX. |

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

### Cluster Redis

Définissez `REDIS_CLUSTER_NODES` avec au moins un nœud joignable ; BunkerWeb découvre le reste du cluster à partir de là. Fonctionne avec Redis 6.2+, Valkey, et les services de cluster managés comme ElastiCache ou MemoryDB via leur endpoint de configuration. Les nœuds de départ acceptent `hôte`, `hôte:port` ou `[ipv6]:port`, mais le cluster doit lui-même annoncer des adresses IPv4 ou des noms d’hôte (`cluster-announce-hostname` avec `cluster-preferred-endpoint-type hostname`) ; les clusters qui annoncent de l’IPv6 ne sont pas pris en charge.

Le mode cluster utilise la base 0. Définir `REDIS_CLUSTER_NODES` en même temps que `REDIS_SENTINEL_HOSTS`, ou avec `REDIS_DATABASE` différent de 0, est une erreur de configuration : BunkerWeb consigne une erreur nommant les deux paramètres et n’utilise pas Redis du tout (retour aux compteurs locaux et aux sessions en cookie) tant que l’un des deux n’est pas retiré.

Basculer un déploiement existant en mode cluster repart d’un espace de clés vide : bannissements actifs et permanents, sessions et rapports ne sont pas repris. Réappliquez les bannissements permanents après le basculement.

Les bannissements et compteurs de mauvais comportement sont répartis entre les primaires par IP client. Les rapports de requêtes bloquées partagent un seul hash slot, donc un seul primaire les stocke tous.

Avec la valeur par défaut `cluster-require-full-coverage yes`, la perte d’un primaire sans réplica arrête tout le cluster ; BunkerWeb revient alors aux compteurs locaux et aux sessions en cookie jusqu’au rétablissement. `cluster-require-full-coverage no` limite l’impact aux clés du shard perdu.

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
    # REDIS_HOST est inutile : le master est résolu via les Sentinels
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
    REDIS_TIMEOUT: "3000"
    REDIS_KEEPALIVE_IDLE: "60000"
    REDIS_KEEPALIVE_POOL: "5"
    ```

!!! info "Redis sur Kubernetes (configuration pilotée par le scheduler)"
    Sur Kubernetes, c’est le **scheduler** qui lit les paramètres et pousse la configuration générée
    vers les instances BunkerWeb — les instances ne lisent pas ces paramètres Redis depuis leur propre
    environnement de pod. Avec le chart Helm officiel, configurez Redis sous `settings.redis`, y
    compris Sentinel via `settings.redis.redisSentinelHosts` et `settings.redis.redisSentinelMaster`
    (chart ≥ v1.0.21). Pour tout paramètre sans clé dédiée dans le chart, utilisez
    `scheduler.extraEnvs`. Les définir uniquement sur `bunkerweb.extraEnvs` n’a **aucun effet**.

### Bonnes pratiques Redis

Lorsque vous utilisez Redis ou Valkey avec BunkerWeb, prenez en compte ces bonnes pratiques pour garantir des performances, une sécurité et une fiabilité optimales :

#### Gestion de la mémoire
- **Surveillez l'utilisation de la mémoire :** Configurez Redis avec des paramètres `maxmemory` appropriés pour éviter les erreurs de mémoire insuffisante
- **Définissez une politique d'éviction :** Utilisez une `maxmemory-policy` (par exemple, `volatile-lru` pour un usage général ou `allkeys-lru` pour les charges de travail à forte composante cache) adaptée à votre cas d'utilisation
- **Valeurs par défaut de l'all-in-one :** L'image Docker AIO livre Redis avec `maxmemory=256mb` et `maxmemory-policy=volatile-lru` ; remplacez ces valeurs via les variables d'environnement `REDIS_MAXMEMORY` et `REDIS_MAXMEMORY_POLICY`. Avec `volatile-lru`, les compteurs transitoires (rate-limit, bad-behavior) sont évincés avant les clés dont la TTL est importante pour les sessions et les bannissements temporaires, et les clés sans expiration (bannissements permanents) restent intactes. La même politique est recommandée pour les serveurs Redis ou Valkey externes utilisés par BunkerWeb.
- **Gardez les rapports de sécurité hors du pool d'éviction :** avec la valeur par défaut de `METRICS_REDIS_TTL`, les rapports de requêtes bloquées portent une expiration, et c'est cette expiration qui les rend éligibles à l'éviction sous `volatile-lru`. La liste est une clé unique qui contient toute la fenêtre conservée : une éviction emporte donc l'ensemble, et non les rapports les plus anciens. Définissez `METRICS_REDIS_TTL=0` sur chaque instance partageant le serveur, sinon une instance restée sur la valeur par défaut réarme l'expiration en quelques secondes. Cela ne change rien sous `allkeys-lru`, où aucune clé n'est immunisée, et cela ne réduit pas la pression mémoire, cela la reporte sur les clés qui expirent encore, dont les bannissements temporaires, les sessions et les verdicts en cache. Dimensionnez `maxmemory` pour les rapports conservés plutôt que de compter sur l'éviction : `METRICS_MAX_BLOCKED_REQUESTS_REDIS` fixe ce plafond.
- **Évitez les clés volumineuses :** Assurez-vous que les clés Redis individuelles restent d'une taille raisonnable pour éviter la dégradation des performances

#### Persistance des données
- **Activez les instantanés RDB :** Configurez des instantanés périodiques pour la persistance des données sans impact significatif sur les performances
- **Envisagez AOF :** Pour les données critiques, activez la persistance AOF (Append-Only File) avec une politique fsync appropriée
- **Stratégie de sauvegarde :** Mettez en œuvre des sauvegardes régulières de Redis dans le cadre de votre plan de reprise après sinistre

#### Optimisation des performances
- **Pooling de connexions :** BunkerWeb l'implémente déjà, mais assurez-vous que les autres applications suivent cette pratique. `REDIS_KEEPALIVE_POOL` s'applique par worker NGINX : en régime établi, le nombre de connexions vaut environ `WORKER_PROCESSES x REDIS_KEEPALIVE_POOL x instances`. Dimensionnez la limite `maxclients` de Redis/Valkey au-dessus, car une connexion refusée empêche, pour cette requête, la vérification des bannissements conservés uniquement dans Redis
- **Pipelining :** Lorsque c'est possible, utilisez le pipelining pour les opérations en masse afin de réduire la surcharge réseau
- **Évitez les opérations coûteuses :** Soyez prudent avec les commandes comme KEYS dans les environnements de production
- **Testez votre charge de travail :** Utilisez redis-benchmark pour tester vos modèles de charge de travail spécifiques

### Ressources supplémentaires

- [Documentation Redis](https://redis.io/documentation)
- [Guide de sécurité Redis](https://redis.io/topics/security)
- [Haute disponibilité Redis](https://redis.io/topics/sentinel)
- [Persistance Redis](https://redis.io/topics/persistence)
