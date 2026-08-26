Le plugin Metrics fournit des capacités complètes de surveillance et de collecte de données pour votre instance BunkerWeb. Cette fonctionnalité vous permet de suivre divers indicateurs de performance, événements de sécurité et statistiques système, afin d'obtenir des informations précieuses sur le comportement et l'état de santé de vos sites et services protégés.

**Comment ça marche :**

1. BunkerWeb collecte des métriques clés pendant le traitement des requêtes et des réponses.
2. Ces métriques incluent des compteurs de requêtes bloquées, des mesures de performance et diverses statistiques liées à la sécurité.
3. Les données sont stockées efficacement en mémoire, avec des limites configurables pour éviter une consommation excessive de ressources.
4. Pour les déploiements multi-instances, Redis peut être utilisé pour centraliser et agréger les données de métriques.
5. Les métriques collectées sont accessibles via l'API ou visualisables dans l'[interface web](web-ui.md).
6. Ces informations vous aident à identifier les menaces de sécurité, à résoudre les problèmes et à optimiser votre configuration.

### Implémentation technique

Le plugin Metrics fonctionne en :

- utilisant des dictionnaires partagés dans NGINX, où `metrics_datastore` est utilisé pour HTTP et `metrics_datastore_stream` pour le trafic TCP/UDP ;
- s'appuyant sur un cache LRU pour un stockage efficace en mémoire ;
- synchronisant périodiquement les données entre les workers à l'aide de timers ;
- stockant des informations détaillées sur les requêtes bloquées, notamment l'adresse IP du client, le pays, l'horodatage, les détails de la requête et le motif du blocage ;
- prenant en charge des métriques spécifiques aux plugins via une interface commune de collecte de métriques ;
- fournissant des points d'accès API pour interroger les métriques collectées.

### Utilisation

Suivez ces étapes pour configurer et utiliser la fonctionnalité Metrics :

1. **Activez la fonctionnalité :** la collecte de métriques est activée par défaut. Vous pouvez la contrôler avec le paramètre `USE_METRICS`.
2. **Configurez l'allocation mémoire :** définissez la quantité de mémoire allouée au stockage des métriques avec le paramètre `METRICS_MEMORY_SIZE`.
3. **Définissez les limites de stockage :** indiquez combien de requêtes bloquées stocker par worker et dans Redis avec les paramètres correspondants.
4. **Accédez aux données :** consultez les métriques collectées via l'[interface web](web-ui.md) ou les points d'accès API.
5. **Analysez les informations :** utilisez les données recueillies pour identifier des tendances, détecter des problèmes de sécurité et optimiser votre configuration.

### Métriques collectées

Le plugin Metrics collecte les informations suivantes :

1. **Requêtes bloquées** : pour chaque requête bloquée, les données suivantes sont stockées :
    - identifiant de requête et horodatage ;
    - adresse IP du client et pays (si disponible) ;
    - méthode HTTP et URL ;
    - code d'état HTTP ;
    - agent utilisateur ;
    - motif du blocage et mode de sécurité ;
    - nom du serveur ;
    - données supplémentaires liées au motif du blocage.

2. **Compteurs de plugins** : divers compteurs spécifiques aux plugins qui suivent des activités et événements.

### Accès API

Les données de métriques sont accessibles via les points d'accès API internes de BunkerWeb :

- **Point d'accès** : `/metrics/{filter}`
- **Méthode** : GET
- **Description** : récupère les données de métriques selon le filtre spécifié
- **Format de réponse** : objet JSON contenant les métriques demandées

Par exemple, `/metrics/requests` renvoie des informations sur les requêtes bloquées.

!!! info "Configuration de l'accès API"
    Pour accéder aux métriques via l'API, vous devez vous assurer que :

    1. la fonctionnalité API est activée avec `USE_API: "yes"` (activée par défaut) ;
    2. votre IP cliente est incluse dans le paramètre `API_WHITELIST_IP` (par défaut `127.0.0.0/8`) ;
    3. vous accédez à l'API sur le port configuré (par défaut `5000` via le paramètre `API_HTTP_PORT`) ;
    4. vous utilisez la bonne valeur `API_SERVER_NAME` dans l'en-tête Host (par défaut `bwapi`) ;
    5. si `API_TOKEN` est configuré, vous incluez `Authorization: Bearer <token>` dans les en-têtes de la requête.

    Requêtes typiques :

    Sans jeton (lorsque `API_TOKEN` n'est pas défini) :
    ```bash
    curl -H "Host: bwapi" \
         http://votre-instance-bunkerweb:5000/metrics/requests
    ```

    Avec jeton (lorsque `API_TOKEN` est défini) :
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://votre-instance-bunkerweb:5000/metrics/requests
    ```

    Si vous avez personnalisé `API_SERVER_NAME` avec une valeur différente de `bwapi`, utilisez cette valeur dans l'en-tête Host.

    Pour les environnements de production sécurisés, limitez l'accès à l'API à des IP de confiance et activez `API_TOKEN`.

### Paramètres de configuration

| Paramètre                            | Défaut   | Contexte  | Multiple | Description                                                                                                                                |
| ------------------------------------ | -------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_METRICS`                        | `yes`    | multisite | non      | **Activer les métriques :** mettez `yes` pour activer la collecte et la récupération des métriques.                                         |
| `METRICS_MEMORY_SIZE`                | `16m`    | global    | non      | **Taille mémoire :** taille du stockage interne des métriques (par exemple `8192`, `16m`, `32m`).                                          |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1k`     | global    | non      | **Maximum de requêtes bloquées :** nombre maximal de requêtes bloquées à stocker par worker. Accepte la notation abrégée `k`/`m`.          |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `10k`    | global    | non      | **Maximum Redis de requêtes bloquées :** nombre maximal de requêtes bloquées à stocker dans Redis. Accepte la notation abrégée `k`/`m`.    |
| `METRICS_REDIS_TTL` | `2592000` | global | non | **TTL Redis des métriques :** Secondes avant expiration des clés de métriques dans Redis (`0` = permanent) ; rafraîchi à chaque synchronisation pour que les données actives n'expirent jamais, ce qui laisse les données abandonnées devenir évincibles sous `volatile-lru` afin que Redis se remette d'un `maxmemory`. Accepte les raccourcis `k`/`m`. |
| `MAX_LRU_HISTORY`                    | `1k`     | global    | non      | **Historique LRU maximal :** nombre d'emplacements LRU par worker et limite du tableau d'historique des événements par clé (traces de blocage, traces d'authentification, etc.). Accepte la notation abrégée `k`/`m`. |
| `METRICS_SAVE_TO_REDIS`              | `yes`    | global    | non      | **Enregistrer les métriques dans Redis :** mettez `yes` pour stocker les métriques (compteurs et tableaux) dans Redis pour l'agrégation. |
| `METRICS_COLLECT_TIMINGS` | `yes` | global | non | **Collecter les temps des plugins :** Mesure le temps passé par chaque plugin dans chaque phase de requête, sous forme d'agrégat count/sum/max par (plugin, phase). Cela force un rafraîchissement du temps NGINX autour de chaque appel de plugin — environ une microseconde par requête sur une chaîne complète ; mettez `no` pour supprimer ce coût. La durée totale de la requête est toujours collectée. |
| `METRICS_MEMORY_MAX_RETRIES` | `5` | global | non | **Nombre max de tentatives mémoire :** Nombre maximal de tentatives pour les opérations en mémoire. |
| `METRICS_PERSIST_TO_DB` | `yes` | global | non | **Persister les rapports :** Persiste les rapports de requêtes bloquées en base de données — durables et interrogeables — en interrogeant périodiquement les instances. Désactivé, les rapports ne vivent que dans les stockages en mémoire et Redis. |
| `METRICS_RETENTION_DAYS` | `90` | global | non | **Rétention des rapports (jours) :** Âge maximal des rapports de requêtes bloquées persistés avant que le job de rétention ne les supprime. |
| `METRICS_RETENTION_MAX_ROWS` | `1000000` | global | non | **Rétention des rapports (lignes) :** Nombre maximal de rapports persistés à conserver ; le job de rétention supprime les lignes les plus anciennes au-delà. |
| `METRICS_BASELINE_SAMPLE_RATE` | `1` | global | non | **Taux d'échantillonnage de la baseline :** Pourcentage de requêtes *non bloquées* enregistrées comme baseline de trafic, afin que la détection d'anomalies apprenne à quoi ressemble la normale (`0` la désactive, `1` échantillonne une requête sur cent). L'échantillonnage est déterministe sur l'identifiant de requête, et l'IP du client n'est jamais stockée. |
| `METRICS_MAX_BASELINE_REQUESTS` | `1k` | global | non | **Nombre max d'enregistrements de baseline :** Nombre maximal d'enregistrements de baseline conservés par worker avant que les plus anciens ne soient supprimés. Ce tampon partage `METRICS_MEMORY_SIZE` avec les rapports, mais il est abandonné plutôt que de les évincer lorsque la place manque. Baissez plutôt le taux d'échantillonnage. |
| `METRICS_BASELINE_RETENTION_DAYS` | `14` | global | non | **Rétention de la baseline (jours) :** Âge maximal des enregistrements de baseline avant que le job de rétention ne les supprime. Volontairement plus courte que celle des rapports : une baseline grossit bien plus vite, et un modèle s'entraîne sur le comportement normal récent. |
| `METRICS_BASELINE_RETENTION_MAX_ROWS` | `2000000` | global | non | **Rétention de la baseline (lignes) :** Nombre maximal d'enregistrements de baseline à conserver. Distinct du plafond des rapports, car les deux tables grossissent à des rythmes très différents. |

!!! tip "Dimensionner l'allocation mémoire"
    Le paramètre `METRICS_MEMORY_SIZE` doit être ajusté selon votre volume de trafic et le nombre d'instances. Les valeurs brutes en octets et les suffixes `k`/`m` sont pris en charge. Pour les sites à fort trafic, envisagez d'augmenter cette valeur afin de garantir la capture de toutes les métriques sans perte de données.

!!! info "Intégration Redis"
    Lorsque BunkerWeb est configuré pour utiliser [Redis](#redis), le plugin Metrics synchronise automatiquement les données de requêtes bloquées avec le serveur Redis. Cela fournit une vue centralisée des événements de sécurité sur plusieurs instances de BunkerWeb.

!!! warning "Considérations de performance"
    Définir des valeurs très élevées pour `METRICS_MAX_BLOCKED_REQUESTS` ou `METRICS_MAX_BLOCKED_REQUESTS_REDIS` peut augmenter l'utilisation de la mémoire. Surveillez les ressources système et ajustez ces valeurs selon vos besoins réels et les ressources disponibles.

!!! note "Stockage spécifique aux workers"
    Chaque worker NGINX maintient ses propres métriques en mémoire. Lors de l'accès aux métriques via l'API, les données de tous les workers sont automatiquement agrégées pour fournir une vue complète.

### Exemples de configuration

=== "Configuration de base"

    Configuration par défaut adaptée à la plupart des déploiements :

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1k"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10k"
    MAX_LRU_HISTORY: "1k"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Environnement à faibles ressources"

    Configuration optimisée pour les environnements disposant de ressources limitées :

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    MAX_LRU_HISTORY: "500"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "Environnement à fort trafic"

    Configuration pour des sites à fort trafic qui doivent suivre davantage d'événements de sécurité :

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    MAX_LRU_HISTORY: "5k"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Métriques désactivées"

    Configuration avec la collecte de métriques désactivée :

    ```yaml
    USE_METRICS: "no"
    ```
