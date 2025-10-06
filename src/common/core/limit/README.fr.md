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
