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

!!! tip "Pools réutilisables de backends gRPC"
    Un `GRPC_HOST` pointe vers un seul backend. Pour répartir la charge entre plusieurs backends, ou partager les mêmes backends entre plusieurs services, déclarez un **pool d'upstreams gRPC** sur la page **Upstreams** (ou via l'API `/upstreams`) et attachez-le à un service sur un chemin — BunkerWeb écrit alors `grpc://<pool>` dans le `GRPC_HOST` correspondant à votre place. Notez que les `location` gRPC et reverse proxy partagent un seul espace de noms de chemins sur un service : un même chemin ne peut pas être revendiqué deux fois, quel que soit le plugin qui le sert. Voir la section *Upstreams réutilisables* de la documentation du Reverse Proxy.

!!! tip "TLS mutuel avec le backend gRPC"
    gRPC possède sa propre identité amont, indépendante du reverse proxy. Pour les upstreams TLS, utilisez `grpcs://` et configurez `GRPC_SSL_SNI` et `GRPC_SSL_SNI_NAME` si nécessaire. Pour vérifier le certificat de l'amont, mettez `GRPC_SSL_VERIFY=yes` et fournissez un lot de CA au format PEM via `GRPC_SSL_TRUSTED_CERTIFICATE` ou `_DATA`, en choisissant la source avec `_PRIORITY` (`file` ou `data`). `GRPC_SSL_VERIFY_DEPTH` vaut `1` par défaut. Aucun lot de CA n'est sélectionné automatiquement : sans CA en cache, la configuration générée désactive la vérification et inclut un commentaire expliquant comment la configurer. Une CRL est optionnelle (`GRPC_SSL_CRL` ou `_DATA`) et n'est appliquée que lorsque la vérification et une CA en cache sont présentes. `GRPC_SSL_PROTOCOLS` et `GRPC_SSL_CIPHERS` laissent les valeurs par défaut de NGINX inchangées lorsqu'ils sont vides.

    Pour le TLS mutuel, définissez `GRPC_SSL_CLIENT_CERT` et `GRPC_SSL_CLIENT_KEY`, ou leurs variantes `_DATA` ; `GRPC_SSL_CLIENT_CERT_PRIORITY` choisit des chemins de fichiers ou des données pour la paire. Les deux moitiés doivent être valides et correspondre — BunkerWeb vérifie que le certificat client de l'amont correspond à sa clé ; les échecs de lecture de fichier temporaires conservent le matériel TLS en cache et signalent un échec du job, tandis que des paramètres effacés ou un matériel invalide suppriment le cache concerné. Cette identité appartient à gRPC ; le reverse proxy et le stream utilisent `REVERSE_PROXY_SSL_CLIENT_*` de façon indépendante. Le job partagé `trusted-cert` met en cache la CA gRPC, la CRL et la paire client dans le répertoire de cache reverseproxy, et déclenche une régénération de la configuration lorsque le matériel change. Il n'existe pas de job de certificat gRPC séparé. Les paramètres TLS s'appliquent à l'ensemble du service, y compris les pools amont attachés ; ce ne sont pas des paramètres par location. Voir *TLS mutuel avec l'amont* dans la documentation du Reverse Proxy.

### Paramètres de configuration

| Setting                                 | Défaut  | Contexte  | Multiple | Description                                                                                                                                |
| ---------------------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`    | multisite | non      | **Activer gRPC :** Mettez `yes` pour activer le proxy gRPC.                                                                               |
| `GRPC_HOST`                             |         | multisite | oui      | **Upstream gRPC :** Valeur utilisée par `grpc_pass` (ex. `grpc://service:50051` ou `grpcs://...`).                                        |
| `GRPC_URL`                              | `/`     | multisite | oui      | **URL de location :** Chemin proxyfié vers l'upstream gRPC. Une valeur commençant par `^` ou se terminant par `$` est traitée comme un emplacement défini par une expression régulière. Vous pouvez éventuellement préfixer avec `~`, `~*`, `=` ou `^~` suivi d'une espace pour définir explicitement le modificateur d'emplacement nginx ; aucune espace, `;`, `{` ou `}` n'est autorisé ailleurs dans la valeur. |
| `GRPC_CUSTOM_HOST`                      |         | multisite | non      | **En-tête Host personnalisé :** Remplace l'en-tête `Host` envoyé à l'upstream.                                                            |
| `GRPC_HEADERS`                          |         | multisite | oui      | **En-têtes amont :** Liste séparée par des `;` de valeurs `grpc_set_header` ; les en-têtes générés correspondants sont remplacés sans distinction de casse. |
| `GRPC_HIDE_HEADERS`                     |         | multisite | oui      | **En-têtes de réponse masqués :** Liste séparée par des espaces pour `grpc_hide_header`.                                                  |
| `GRPC_HEADERS_CLIENT`                   |         | multisite | oui      | **En-têtes de réponse client :** Liste séparée par des `;` de valeurs `add_header` envoyées au client.                                    |
| `GRPC_PASS_HEADERS`                     |         | multisite | oui      | **En-têtes de réponse transmis :** Liste séparée par des espaces de valeurs `grpc_pass_header`, pour transmettre des en-têtes masqués par défaut. |
| `GRPC_IGNORE_HEADERS`                   |         | multisite | oui      | **En-têtes de réponse ignorés :** Liste séparée par des espaces de valeurs `grpc_ignore_headers`, pour empêcher NGINX de les traiter.      |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`    | multisite | non      | **Underscores dans les en-têtes :** Active/désactive `underscores_in_headers`. Partagée à l'échelle du serveur avec les plugins reverse proxy et misc : si un service l'active pour une location, elle s'applique à tout le service. |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`   | multisite | non      | **Intercepter les erreurs :** Active/désactive `grpc_intercept_errors`.                                                                   |
| `GRPC_BUFFER_SIZE`                      |         | multisite | oui      | **Taille du buffer :** Valeur pour `grpc_buffer_size` (buffer utilisé pour lire la réponse de l'amont).                                   |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`   | multisite | oui      | **Timeout de connexion :** Délai pour établir la connexion vers l'upstream.                                                               |
| `GRPC_READ_TIMEOUT`                     | `60s`   | multisite | oui      | **Timeout de lecture :** Délai de lecture depuis l'upstream.                                                                              |
| `GRPC_SEND_TIMEOUT`                     | `60s`   | multisite | oui      | **Timeout d'envoi :** Délai d'envoi vers l'upstream.                                                                                      |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`   | multisite | oui      | **Keepalive socket :** Active/désactive keepalive sur les sockets upstream.                                                               |
| `GRPC_SSL_SNI`                          | `no`    | multisite | non      | **SSL SNI :** Active/désactive SNI pour les upstreams TLS.                                                                                |
| `GRPC_SSL_SNI_NAME`                     |         | multisite | non      | **Nom SSL SNI :** Nom SNI envoyé quand `GRPC_SSL_SNI=yes`.                                                                                |
| `GRPC_SSL_VERIFY`                       | `no`    | multisite | non      | **Vérification SSL :** Active/désactive la vérification du certificat de l'amont gRPC.                                                    |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file`  | multisite | non      | **Priorité du certificat de confiance :** Source du lot de CA, `file` ou `data`.                                                          |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |         | multisite | non      | **Chemin du certificat de confiance :** Chemin vers un lot de CA PEM lisible par le scheduler (priorité `file`).                          |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |         | multisite | non      | **Données du certificat de confiance :** Lot de CA en base64 ou PEM en clair (priorité `data`).                                           |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`     | multisite | non      | **Profondeur de vérification SSL :** Profondeur de vérification dans la chaîne de certificats de l'amont.                                 |
| `GRPC_SSL_CLIENT_CERT_PRIORITY`         | `file`  | multisite | non      | **Priorité du certificat client :** Source du certificat et de la clé client, `file` ou `data`.                                           |
| `GRPC_SSL_CLIENT_CERT`                  |         | multisite | non      | **Chemin du certificat client :** Certificat client PEM présenté à l'amont pour le TLS mutuel (priorité `file`).                          |
| `GRPC_SSL_CLIENT_CERT_DATA`             |         | multisite | non      | **Données du certificat client :** Certificat client en base64 ou PEM en clair (priorité `data`).                                         |
| `GRPC_SSL_CLIENT_KEY`                   |         | multisite | non      | **Chemin de la clé client :** Clé privée PEM correspondant au certificat client (priorité `file`). Elle ne doit pas être chiffrée.        |
| `GRPC_SSL_CLIENT_KEY_DATA`              |         | multisite | non      | **Données de la clé client :** Clé privée client en base64 ou PEM en clair (priorité `data`).                                             |
| `GRPC_SSL_CRL`                          |         | multisite | non      | **Chemin de la CRL :** Liste de révocation PEM appliquée lors de la vérification de l'amont ; appliquée uniquement lorsque `GRPC_SSL_VERIFY=yes`. Prioritaire sur le paramètre de données de la CRL ; un chemin défini mais manquant est une erreur et le paramètre de données n'est pas utilisé comme repli. |
| `GRPC_SSL_CRL_DATA`                     |         | multisite | non      | **Données de la CRL :** Liste de révocation en base64 ou PEM en clair. Utilisée uniquement lorsque le chemin de la CRL est vide.           |
| `GRPC_SSL_PROTOCOLS`                    |         | multisite | non      | **Protocoles SSL de l'amont :** Versions TLS proposées à l'amont. Vide conserve la valeur par défaut de NGINX.                            |
| `GRPC_SSL_CIPHERS`                      |         | multisite | non      | **Suites de chiffrement SSL de l'amont :** Chaîne de suites de chiffrement proposée à l'amont. Vide conserve la valeur par défaut de NGINX. |
| `GRPC_NEXT_UPSTREAM`                    |         | multisite | oui      | **Conditions de next upstream :** Valeur de `grpc_next_upstream`.                                                                         |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |         | multisite | oui      | **Timeout de next upstream :** Valeur de `grpc_next_upstream_timeout`.                                                                    |
| `GRPC_NEXT_UPSTREAM_TRIES`              |         | multisite | oui      | **Essais de next upstream :** Valeur de `grpc_next_upstream_tries`.                                                                       |
| `GRPC_AUTH_REQUEST`                     |         | multisite | oui      | **Auth Request :** Valeur pour `auth_request`, pour s'authentifier via un fournisseur externe.                                            |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |         | multisite | oui      | **URL de connexion Auth Request :** Cible de redirection lorsque l'auth request renvoie 401. Les fragments (`#`) sont pris en charge.      |
| `GRPC_AUTH_REQUEST_SET`                 |         | multisite | oui      | **Auth Request Set :** Liste séparée par des `;` de valeurs `auth_request_set`.                                                           |
| `GRPC_INCLUDES`                         |         | multisite | oui      | **Includes additionnels :** Fichiers `include` séparés par des espaces dans le bloc gRPC `location`.                                      |
| `GRPC_MAX_CLIENT_SIZE`                  |         | multisite | oui      | **Taille maximale du corps :** Valeur pour `client_max_body_size` dans cette location (`0` pour illimité). Retombe sur `MAX_CLIENT_SIZE` du service. |

`GRPC_HOST`, `GRPC_URL`, `GRPC_HEADERS`, `GRPC_HIDE_HEADERS`, `GRPC_HEADERS_CLIENT`, `GRPC_PASS_HEADERS`, `GRPC_IGNORE_HEADERS`, `GRPC_BUFFER_SIZE`, `GRPC_CONNECT_TIMEOUT`, `GRPC_READ_TIMEOUT`, `GRPC_SEND_TIMEOUT`, `GRPC_SOCKET_KEEPALIVE`, `GRPC_NEXT_UPSTREAM{,_TIMEOUT,_TRIES}`, `GRPC_AUTH_REQUEST{,_SIGNIN_URL,_SET}`, `GRPC_INCLUDES` et `GRPC_MAX_CLIENT_SIZE` prennent en charge les suffixes numériques pour plusieurs upstreams/locations (`GRPC_HOST_2`, `GRPC_URL_2`, ...). `GRPC_HEADERS_CLIENT` suit la sémantique `add_header` de NGINX (ajoutez `always` si nécessaire). Les URL de connexion conservent la prise en charge des fragments (`#`). ModSecurity reste désactivé dans les locations gRPC.

!!! warning "ModSecurity sur les locations gRPC"
    ModSecurity est actuellement désactivé automatiquement dans les blocs gRPC `location` générés par ce plugin, car ModSecurity ne prend pas en charge de manière fiable les schémas de trafic gRPC.

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
    GRPC_NEXT_UPSTREAM: "error timeout http_502"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```
