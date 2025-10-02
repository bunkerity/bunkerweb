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
