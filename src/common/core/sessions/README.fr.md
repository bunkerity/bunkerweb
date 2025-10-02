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
