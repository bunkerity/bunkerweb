Le plugin gRPC permet à BunkerWeb de proxyfier des services gRPC via HTTP/2 avec `grpc_pass`. Il est conçu pour des environnements multisites où chaque hôte virtuel peut exposer un ou plusieurs backends gRPC sur des chemins spécifiques.

!!! example "Fonctionnalité expérimentale"
    Cette fonctionnalité n'est pas prête pour la production. N'hésitez pas à la tester et à nous signaler tout bug via les [issues](https://github.com/bunkerity/bunkerweb/issues) du dépôt GitHub.

**Fonctionnement :**

1. Un client envoie une requête HTTP/2 à BunkerWeb.
2. Le plugin gRPC fait correspondre une `location` configurée (`GRPC_URL`) et transmet la requête à l'upstream configuré (`GRPC_HOST`) avec `grpc_pass`.
3. BunkerWeb ajoute des en-têtes de transfert et applique les paramètres de timeout/réessai upstream.
4. Le serveur gRPC upstream répond et BunkerWeb relaie la réponse vers le client.

### Utilisation

1. **Activer la fonctionnalité :** Définissez `USE_GRPC` sur `yes`.
2. **Configurer le(s) upstream(s) :** Définissez au minimum `GRPC_HOST` (et éventuellement `GRPC_HOST_2`, `GRPC_HOST_3`, ...).
3. **Associer les chemins :** Définissez `GRPC_URL` pour chaque upstream (avec les suffixes correspondants en cas d'entrées multiples).
4. **Ajuster le comportement :** Configurez si besoin les timeouts, les retries, les en-têtes et les options TLS SNI.

### Paramètres de configuration

| Paramètre                               | Défaut | Contexte  | Multiple | Description                                                                                                                                                    |
| --------------------------------------- | ------ | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`   | multisite | non      | **Activer gRPC :** Mettez `yes` pour activer le proxy gRPC.                                                                                                    |
| `GRPC_HOST`                             |        | multisite | oui      | **Upstream gRPC :** Valeur utilisée par `grpc_pass` (ex. `grpc://service:50051` ou `grpcs://...`).                                                             |
| `GRPC_URL`                              | `/`    | multisite | oui      | **URL de location :** Chemin proxyfié vers l'upstream gRPC.                                                                                                    |
| `GRPC_CUSTOM_HOST`                      |        | multisite | non      | **En-tête Host personnalisé :** Remplace l'en-tête `Host` envoyé à l'upstream.                                                                                 |
| `GRPC_HEADERS`                          |        | multisite | oui      | **En-têtes upstream supplémentaires :** Liste séparée par des `;` pour `grpc_set_header`.                                                                      |
| `GRPC_HIDE_HEADERS`                     |        | multisite | oui      | **En-têtes de réponse masqués :** Liste séparée par des espaces pour `grpc_hide_header`.                                                                       |
| `GRPC_HEADERS_CLIENT`                   |        | multisite | oui      | **En-têtes de réponse client :** Liste séparée par des `;` de valeurs `add_header` envoyées au client.                                                         |
| `GRPC_PASS_HEADERS`                     |        | multisite | oui      | **En-têtes de réponse transmis :** Liste séparée par des espaces pour `grpc_pass_header`, afin de transmettre les en-têtes masqués par défaut.                 |
| `GRPC_IGNORE_HEADERS`                   |        | multisite | oui      | **En-têtes de réponse ignorés :** Liste séparée par des espaces pour `grpc_ignore_headers`, afin que NGINX ne les traite pas.                                  |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`   | multisite | non      | **Underscores dans les en-têtes :** Active/désactive `underscores_in_headers`.                                                                                 |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`  | multisite | non      | **Intercepter les erreurs :** Active/désactive `grpc_intercept_errors`.                                                                                        |
| `GRPC_BUFFER_SIZE`                      |        | multisite | oui      | **Taille de buffer :** Valeur de `grpc_buffer_size` (buffer de lecture de la réponse upstream).                                                                |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`  | multisite | oui      | **Timeout de connexion :** Délai pour établir la connexion vers l'upstream.                                                                                    |
| `GRPC_READ_TIMEOUT`                     | `60s`  | multisite | oui      | **Timeout de lecture :** Délai de lecture depuis l'upstream.                                                                                                   |
| `GRPC_SEND_TIMEOUT`                     | `60s`  | multisite | oui      | **Timeout d'envoi :** Délai d'envoi vers l'upstream.                                                                                                           |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`  | multisite | oui      | **Keepalive socket :** Active/désactive keepalive sur les sockets upstream.                                                                                    |
| `GRPC_SSL_SNI`                          | `no`   | multisite | non      | **SSL SNI :** Active/désactive SNI pour les upstreams TLS.                                                                                                     |
| `GRPC_SSL_SNI_NAME`                     |        | multisite | non      | **Nom SSL SNI :** Nom SNI envoyé quand `GRPC_SSL_SNI=yes`.                                                                                                     |
| `GRPC_SSL_VERIFY`                       | `no`   | multisite | non      | **Vérification SSL :** Active/désactive la vérification du certificat de l'upstream gRPC.                                                                      |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file` | multisite | non      | **Priorité du certificat de confiance :** Source du bundle CA, `file` ou `data`.                                                                               |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |        | multisite | non      | **Chemin du certificat de confiance :** Chemin d'un bundle CA PEM lisible par le scheduler (priorité `file`).                                                  |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |        | multisite | non      | **Données du certificat de confiance :** Bundle CA en base64 ou PEM en clair (priorité `data`).                                                                |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`    | multisite | non      | **Profondeur de vérification SSL :** Profondeur de vérification dans la chaîne de certificats upstream.                                                        |
| `GRPC_SSL_CERT_PRIORITY`                | `file` | multisite | non      | **Priorité du certificat client :** Source du certificat et de la clé client, `file` ou `data`.                                                                |
| `GRPC_SSL_CERT`                         |        | multisite | non      | **Chemin du certificat client :** Certificat client PEM présenté à l'upstream pour le TLS mutuel (priorité `file`).                                            |
| `GRPC_SSL_CERT_DATA`                    |        | multisite | non      | **Données du certificat client :** Certificat client en base64 ou PEM en clair (priorité `data`).                                                              |
| `GRPC_SSL_KEY`                          |        | multisite | non      | **Chemin de la clé client :** Clé privée PEM correspondant au certificat client (priorité `file`). Elle ne doit pas être chiffrée.                             |
| `GRPC_SSL_KEY_DATA`                     |        | multisite | non      | **Données de la clé client :** Clé privée client en base64 ou PEM en clair (priorité `data`).                                                                  |
| `GRPC_SSL_CRL`                          |        | multisite | non      | **Chemin de la CRL :** Liste de révocation PEM appliquée lors de la vérification de l'upstream. Prioritaire sur les données de CRL.                            |
| `GRPC_SSL_CRL_DATA`                     |        | multisite | non      | **Données de la CRL :** Liste de révocation en base64 ou PEM en clair. Utilisées seulement si le chemin de la CRL est vide.                                    |
| `GRPC_SSL_PROTOCOLS`                    |        | multisite | non      | **Protocoles SSL upstream :** Versions TLS proposées à l'upstream. Vide conserve la valeur par défaut de NGINX.                                                |
| `GRPC_SSL_CIPHERS`                      |        | multisite | non      | **Ciphers SSL upstream :** Suite de chiffrement proposée à l'upstream. Vide conserve la valeur par défaut de NGINX.                                            |
| `GRPC_NEXT_UPSTREAM`                    |        | multisite | oui      | **Conditions de next upstream :** Valeur de `grpc_next_upstream`.                                                                                              |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |        | multisite | oui      | **Timeout de next upstream :** Valeur de `grpc_next_upstream_timeout`.                                                                                         |
| `GRPC_NEXT_UPSTREAM_TRIES`              |        | multisite | oui      | **Essais de next upstream :** Valeur de `grpc_next_upstream_tries`.                                                                                            |
| `GRPC_AUTH_REQUEST`                     |        | multisite | oui      | **Auth request :** Valeur de `auth_request`, pour authentifier via un fournisseur externe.                                                                     |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |        | multisite | oui      | **URL de connexion auth request :** Cible de redirection quand la requête d'authentification renvoie 401.                                                      |
| `GRPC_AUTH_REQUEST_SET`                 |        | multisite | oui      | **Auth request set :** Liste séparée par des `;` de valeurs `auth_request_set`.                                                                                |
| `GRPC_INCLUDES`                         |        | multisite | oui      | **Includes additionnels :** Fichiers `include` séparés par des espaces dans le bloc gRPC `location`.                                                           |
| `GRPC_MAX_CLIENT_SIZE`                  |        | multisite | oui      | **Taille maximale du corps :** Valeur de `client_max_body_size` pour cette location (`0` pour illimité). À défaut, le `MAX_CLIENT_SIZE` du service s'applique. |

!!! tip "TLS mutuel vers l'upstream"
    Le certificat client et sa clé doivent tous deux être fournis, et la clé ne doit pas être chiffrée. Le scheduler valide la paire, la met en cache et la distribue aux instances ; si elle n'est pas valide, les directives de certificat ne sont simplement pas générées. Une CRL n'est appliquée que si la vérification de l'upstream est active.

!!! warning "ModSecurity sur les locations gRPC"
    ModSecurity est actuellement désactivé automatiquement dans les blocs gRPC `location` générés par ce plugin, car ModSecurity ne prend pas en charge de manière fiable les schémas de trafic gRPC.

!!! tip "Vérifier le certificat de l'upstream"
    `GRPC_SSL_VERIFY` ne prend effet qu'une fois un bundle CA disponible. Fournissez-le via `GRPC_SSL_TRUSTED_CERTIFICATE` (un chemin lisible par le scheduler) ou `GRPC_SSL_TRUSTED_CERTIFICATE_DATA` (base64 ou PEM en clair), et choisissez la source avec `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY`. Le scheduler valide le bundle, le met en cache et le distribue aux instances. Sans bundle exploitable, la vérification reste désactivée.

!!! warning "Flux longue durée et timeouts du cœur"
    Les RPC longue durée ou en streaming peuvent nécessiter des timeouts NGINX génériques plus élevés que les valeurs globales par défaut. Les réglages les plus courants sont `CLIENT_BODY_TIMEOUT` et `CLIENT_HEADER_TIMEOUT` dans les paramètres du plugin General.

!!! tip "Plusieurs backends gRPC"
    Utilisez des paramètres suffixés pour plusieurs routes :
    - `GRPC_HOST`, `GRPC_URL`
    - `GRPC_HOST_2`, `GRPC_URL_2`
    - `GRPC_HOST_3`, `GRPC_URL_3`

### Exemples de configuration

=== "Proxy gRPC de base"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_CONNECT_TIMEOUT: "10s"
    GRPC_READ_TIMEOUT: "300s"
    GRPC_SEND_TIMEOUT: "300s"
    ```

=== "Upstream TLS (grpcs + SNI)"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    ```

=== "Plusieurs chemins / backends"

    ```yaml
    USE_GRPC: "yes"

    GRPC_HOST: "grpc://user-service:50051"
    GRPC_URL: "/users.UserService/"

    GRPC_HOST_2: "grpc://billing-service:50052"
    GRPC_URL_2: "/billing.BillingService/"

    GRPC_HOST_3: "grpc://inventory-service:50053"
    GRPC_URL_3: "/inventory.InventoryService/"
    ```

=== "En-têtes et politique de retry"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_HEADERS: "x-request-source bunkerweb;x-env production"
    GRPC_NEXT_UPSTREAM: "error timeout unavailable"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```

=== "Upstream TLS vérifié"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    GRPC_SSL_VERIFY: "yes"
    GRPC_SSL_TRUSTED_CERTIFICATE: "/etc/ssl/certs/ca-certificates.crt"
    GRPC_SSL_VERIFY_DEPTH: "2"
    ```

=== "Authentification externe"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_AUTH_REQUEST: "/auth"
    GRPC_AUTH_REQUEST_SIGNIN_URL: "https://sso.example.com/login"
    GRPC_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_email $upstream_http_x_email"
    GRPC_HEADERS: "x-forwarded-user $auth_user"
    ```
