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
