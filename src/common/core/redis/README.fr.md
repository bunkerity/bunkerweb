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

!!! warning "Sécurité" - Mots de passe forts pour Redis et Sentinel - Envisagez SSL/TLS - Ne pas exposer Redis sur Internet - Restreignez l’accès au port Redis (pare‑feu, segmentation)

### Exemples

=== "Configuration basique"

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Configuration sécurisée"

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Redis Sentinel"

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Tuning avancé"

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
