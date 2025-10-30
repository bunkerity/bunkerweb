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
