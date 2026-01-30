Le plugin Reverse Proxy offre des capacités de proxy transparentes pour BunkerWeb, vous permettant de router les requêtes vers des serveurs et services backend. Cette fonctionnalité permet à BunkerWeb d'agir comme une façade sécurisée pour vos applications tout en offrant des avantages supplémentaires tels que la terminaison SSL et le filtrage de sécurité.

**Comment ça marche :**

1.  Lorsqu'un client envoie une requête à BunkerWeb, le plugin Reverse Proxy la transmet à votre serveur backend configuré.
2.  BunkerWeb ajoute des en-têtes de sécurité, applique des règles WAF et effectue d'autres contrôles de sécurité avant de transmettre les requêtes à votre application.
3.  Le serveur backend traite la requête et renvoie une réponse à BunkerWeb.
4.  BunkerWeb applique des mesures de sécurité supplémentaires à la réponse avant de la renvoyer au client.
5.  Le plugin prend en charge le proxying de flux HTTP et TCP/UDP, permettant un large éventail d'applications, y compris les WebSockets et d'autres protocoles non-HTTP.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Reverse Proxy :

1.  **Activer la fonctionnalité :** Mettez le paramètre `USE_REVERSE_PROXY` à `yes` pour activer la fonctionnalité de reverse proxy.
2.  **Configurer vos serveurs backend :** Spécifiez les serveurs en amont à l'aide du paramètre `REVERSE_PROXY_HOST`.
3.  **Ajuster les paramètres du proxy :** Affinez le comportement avec des paramètres optionnels pour les délais d'attente, les tailles de tampon, et d'autres paramètres.
4.  **Configurer les options spécifiques au protocole :** Pour les WebSockets ou des exigences HTTP spéciales, ajustez les paramètres correspondants.
5.  **Mettre en place la mise en cache (optionnel) :** Activez et configurez la mise en cache du proxy pour améliorer les performances pour le contenu fréquemment accédé.

### Guide de configuration

=== "Configuration de base"

    **Paramètres principaux**

    Les paramètres de configuration essentiels activent et contrôlent la fonctionnalité de base du reverse proxy.

    !!! success "Bénéfices du Reverse Proxy"
        - **Amélioration de la sécurité :** Tout le trafic passe par les couches de sécurité de BunkerWeb avant d'atteindre vos applications
        - **Terminaison SSL :** Gérez les certificats SSL/TLS de manière centralisée tandis que les services backend peuvent utiliser des connexions non chiffrées
        - **Gestion des protocoles :** Prise en charge de HTTP, HTTPS, WebSockets, et d'autres protocoles
        - **Interception des erreurs :** Personnalisez les pages d'erreur pour une expérience utilisateur cohérente

    | Paramètre                        | Défaut | Contexte  | Multiple | Description                                                                                                      |
    | -------------------------------- | ------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`              | `no`   | multisite | no       | **Activer le Reverse Proxy :** Mettre à `yes` pour activer la fonctionnalité de reverse proxy.                   |
    | `REVERSE_PROXY_HOST`             |        | multisite | yes      | **Hôte Backend :** URL complète de la ressource proxifiée (proxy_pass).                                          |
    | `REVERSE_PROXY_URL`              | `/`    | multisite | yes      | **URL d'emplacement :** Chemin qui sera proxifié vers le serveur backend.                                        |
    | `REVERSE_PROXY_BUFFERING`        | `yes`  | multisite | yes      | **Mise en tampon de la réponse :** Active ou désactive la mise en tampon des réponses de la ressource proxifiée. |
    | `REVERSE_PROXY_REQUEST_BUFFERING`| `yes`  | multisite | yes      | **Mise en tampon des requêtes :** Active ou désactive la mise en tampon des requêtes vers la ressource proxifiée. |
    | `REVERSE_PROXY_KEEPALIVE`        | `no`   | multisite | yes      | **Keep-Alive :** Active ou désactive les connexions keepalive avec la ressource proxifiée.                       |
    | `REVERSE_PROXY_CUSTOM_HOST`      |        | multisite | no       | **Hôte personnalisé :** Remplace l'en-tête Host envoyé au serveur en amont.                                      |
    | `REVERSE_PROXY_INTERCEPT_ERRORS` | `yes`  | multisite | no       | **Intercepter les erreurs :** Intercepte et réécrit les réponses d'erreur du backend.                            |

    !!! tip "Bonnes pratiques"
        - Spécifiez toujours l'URL complète dans `REVERSE_PROXY_HOST`, y compris le protocole (http:// ou https://)
        - Utilisez `REVERSE_PROXY_INTERCEPT_ERRORS` pour fournir des pages d'erreur cohérentes sur tous vos services
        - Lors de la configuration de plusieurs backends, utilisez le format de suffixe numéroté (par exemple, `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

    !!! warning "Comportement de la mise en tampon des requêtes"
        La désactivation de `REVERSE_PROXY_REQUEST_BUFFERING` n'a d'effet que lorsque ModSecurity est désactivé, car la mise en tampon des requêtes est autrement imposée.

=== "Paramètres de connexion"

    **Configuration des connexions et des délais d'attente**

    Ces paramètres contrôlent le comportement des connexions, la mise en tampon et les valeurs de délai d'attente pour les connexions proxifiées.

    !!! success "Bénéfices"
        - **Performance optimisée :** Ajustez les tailles de tampon et les paramètres de connexion en fonction des besoins de votre application
        - **Gestion des ressources :** Contrôlez l'utilisation de la mémoire grâce à des configurations de tampon appropriées
        - **Fiabilité :** Configurez des délais d'attente appropriés pour gérer les connexions lentes ou les problèmes de backend

    | Paramètre                       | Défaut | Contexte  | Multiple | Description                                                                                                        |
    | ------------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
    | `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`  | multisite | yes      | **Délai de connexion :** Temps maximum pour établir une connexion avec le serveur backend.                         |
    | `REVERSE_PROXY_READ_TIMEOUT`    | `60s`  | multisite | yes      | **Délai de lecture :** Temps maximum entre les transmissions de deux paquets successifs depuis le serveur backend. |
    | `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`  | multisite | yes      | **Délai d'envoi :** Temps maximum entre les transmissions de deux paquets successifs vers le serveur backend.      |
    | `PROXY_BUFFERS`                 |        | multisite | no       | **Tampons :** Nombre et taille des tampons pour lire la réponse du serveur backend.                                |
    | `PROXY_BUFFER_SIZE`             |        | multisite | no       | **Taille du tampon :** Taille du tampon pour lire la première partie de la réponse du serveur backend.             |
    | `PROXY_BUSY_BUFFERS_SIZE`       |        | multisite | no       | **Taille des tampons occupés :** Taille des tampons qui peuvent être occupés à envoyer une réponse au client.      |

    !!! warning "Considérations sur les délais d'attente"
        - Des délais trop courts peuvent interrompre des connexions légitimes mais lentes
        - Des délais trop longs peuvent laisser des connexions ouvertes inutilement, épuisant potentiellement les ressources
        - Pour les applications WebSocket, augmentez considérablement les délais de lecture et d'envoi (300s ou plus recommandé)

=== "Configuration SSL/TLS"

    **Paramètres SSL/TLS pour les connexions Backend**

    Ces paramètres contrôlent la manière dont BunkerWeb établit des connexions sécurisées avec les serveurs backend.

    !!! success "Bénéfices"
        - **Chiffrement de bout en bout :** Maintenez des connexions chiffrées du client au backend
        - **Validation des certificats :** Contrôlez la validation des certificats des serveurs backend
        - **Support SNI :** Spécifiez l'indication du nom du serveur (SNI) pour les backends hébergeant plusieurs sites

    | Paramètre                    | Défaut | Contexte  | Multiple | Description                                                                                    |
    | ---------------------------- | ------ | --------- | -------- | ---------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_SSL_SNI`      | `no`   | multisite | no       | **SSL SNI :** Active ou désactive l'envoi du SNI (Server Name Indication) à l'amont.           |
    | `REVERSE_PROXY_SSL_SNI_NAME` |        | multisite | no       | **Nom SSL SNI :** Définit le nom d'hôte SNI à envoyer à l'amont lorsque le SSL SNI est activé. |

    !!! info "Explication du SNI"
        L'Indication du Nom du Serveur (SNI) est une extension TLS qui permet à un client de spécifier le nom d'hôte auquel il tente de se connecter pendant la négociation. Cela permet aux serveurs de présenter plusieurs certificats sur la même adresse IP et le même port, permettant ainsi de servir plusieurs sites web sécurisés (HTTPS) à partir d'une seule adresse IP sans que tous ces sites n'utilisent le même certificat.

=== "Support des protocoles"

    **Configuration spécifique aux protocoles**

    Configurez la gestion de protocoles spéciaux, notamment pour les WebSockets et autres protocoles non-HTTP.

    !!! success "Bénéfices"
        - **Flexibilité des protocoles :** Le support des WebSockets permet des applications en temps réel
        - **Applications web modernes :** Activez des fonctionnalités interactives nécessitant une communication bidirectionnelle

    | Paramètre          | Défaut | Contexte  | Multiple | Description                                                             |
    | ------------------ | ------ | --------- | -------- | ----------------------------------------------------------------------- |
    | `REVERSE_PROXY_WS` | `no`   | multisite | yes      | **Support WebSocket :** Active le protocole WebSocket sur la ressource. |

    !!! tip "Configuration WebSocket"
        - Lors de l'activation des WebSockets avec `REVERSE_PROXY_WS: "yes"`, envisagez d'augmenter les valeurs des délais d'attente
        - Les connexions WebSocket restent ouvertes plus longtemps que les connexions HTTP typiques
        - Pour les applications WebSocket, une configuration recommandée est :
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Gestion des en-têtes"

    **Configuration des en-têtes HTTP**

    Contrôlez quels en-têtes sont envoyés aux serveurs backend et aux clients, vous permettant d'ajouter, de modifier ou de préserver des en-têtes HTTP.

    !!! success "Bénéfices"
        - **Contrôle de l'information :** Gérez précisément les informations partagées entre les clients et les backends
        - **Amélioration de la sécurité :** Ajoutez des en-têtes liés à la sécurité ou supprimez ceux qui pourraient divulguer des informations sensibles
        - **Support d'intégration :** Fournissez les en-têtes nécessaires à l'authentification et au bon fonctionnement du backend

    | Paramètre                              | Défaut    | Contexte  | Multiple | Description                                                                                       |
    | -------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_HEADERS`                |           | multisite | yes      | **En-têtes personnalisés :** En-têtes HTTP à envoyer au backend, séparés par des points-virgules. |
    | `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade` | multisite | yes      | **Cacher les en-têtes :** En-têtes HTTP à cacher aux clients lorsqu'ils sont reçus du backend.    |
    | `REVERSE_PROXY_HEADERS_CLIENT`         |           | multisite | yes      | **En-têtes client :** En-têtes HTTP à envoyer au client, séparés par des points-virgules.         |
    | `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`      | multisite | no       | **Underscores dans les en-têtes :** Active ou désactive la directive `underscores_in_headers`.    |

    !!! warning "Considérations de sécurité"
        Lors de l'utilisation de la fonctionnalité de reverse proxy, soyez prudent quant aux en-têtes que vous transmettez à vos applications backend. Certains en-têtes peuvent exposer des informations sensibles sur votre infrastructure ou contourner les contrôles de sécurité.

    !!! example "Exemples de format d'en-tête"
        En-têtes personnalisés vers les serveurs backend :
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        En-têtes personnalisés vers les clients :
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Authentification"

    **Configuration de l'authentification externe**

    Intégrez avec des systèmes d'authentification externes pour centraliser la logique d'autorisation à travers vos applications.

    !!! success "Bénéfices"
        - **Authentification centralisée :** Mettez en œuvre un point d'authentification unique pour plusieurs applications
        - **Sécurité cohérente :** Appliquez des politiques d'authentification uniformes sur différents services
        - **Contrôle amélioré :** Transmettez les détails d'authentification aux applications backend via des en-têtes ou des variables

    | Paramètre                               | Défaut | Contexte  | Multiple | Description                                                                                               |
    | --------------------------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_AUTH_REQUEST`            |        | multisite | yes      | **Requête d'authentification :** Active l'authentification via un fournisseur externe.                    |
    | `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |        | multisite | yes      | **URL de connexion :** Redirige les clients vers l'URL de connexion en cas d'échec de l'authentification. |
    | `REVERSE_PROXY_AUTH_REQUEST_SET`        |        | multisite | yes      | **Variables d'authentification :** Variables à définir à partir du fournisseur d'authentification.        |

    !!! tip "Intégration de l'authentification"
        - La fonctionnalité de requête d'authentification permet la mise en œuvre de microservices d'authentification centralisés
        - Votre service d'authentification doit renvoyer un code de statut 200 pour une authentification réussie ou 401/403 en cas d'échec
        - Utilisez la directive auth_request_set pour extraire et transmettre des informations du service d'authentification

=== "Configuration avancée"

    **Options de configuration supplémentaires**

    Ces paramètres offrent une personnalisation plus poussée du comportement du reverse proxy pour des scénarios spécialisés.

    !!! success "Bénéfices"
        - **Personnalisation :** Incluez des extraits de configuration supplémentaires pour des exigences complexes
        - **Optimisation des performances :** Affinez la gestion des requêtes pour des cas d'usage spécifiques
        - **Flexibilité :** Adaptez-vous aux exigences uniques de l'application avec des configurations spécialisées

    | Paramètre                         | Défaut | Contexte  | Multiple | Description                                                                                           |
    | --------------------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |        | multisite | yes      | **Configurations supplémentaires :** Incluez des configurations additionnelles dans le bloc location. |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`  | multisite | yes      | **Passer le corps de la requête :** Active ou désactive la transmission du corps de la requête.       |

    !!! warning "Considérations de sécurité"
        Soyez prudent lorsque vous incluez des extraits de configuration personnalisés car ils peuvent outrepasser les paramètres de sécurité de BunkerWeb ou introduire des vulnérabilités s'ils ne sont pas correctement configurés.

=== "Configuration du cache"

    **Paramètres de mise en cache des réponses**

    Améliorez les performances en mettant en cache les réponses des serveurs backend, réduisant ainsi la charge et améliorant les temps de réponse.

    !!! success "Bénéfices"
        - **Performance :** Réduisez la charge sur les serveurs backend en servant du contenu mis en cache
        - **Latence réduite :** Temps de réponse plus rapides pour le contenu fréquemment demandé
        - **Économies de bande passante :** Minimisez le trafic réseau interne en mettant en cache les réponses
        - **Personnalisation :** Configurez exactement quoi, quand et comment le contenu est mis en cache

    | Paramètre                    | Défaut                             | Contexte  | Multiple | Description                                                                                                      |
    | ---------------------------- | ---------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
    | `USE_PROXY_CACHE`            | `no`                               | multisite | no       | **Activer le cache :** Mettre à `yes` pour activer la mise en cache des réponses du backend.                     |
    | `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | no       | **Niveaux de chemin du cache :** Comment structurer la hiérarchie du répertoire de cache.                        |
    | `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | no       | **Taille de la zone de cache :** Taille de la zone de mémoire partagée utilisée pour les métadonnées du cache.   |
    | `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | no       | **Paramètres du chemin de cache :** Paramètres supplémentaires pour le chemin de cache.                          |
    | `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | no       | **Méthodes de cache :** Méthodes HTTP qui peuvent être mises en cache.                                           |
    | `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | no       | **Utilisations min. pour cache :** Nombre minimum de requêtes avant qu'une réponse ne soit mise en cache.        |
    | `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | no       | **Clé de cache :** La clé utilisée pour identifier de manière unique une réponse mise en cache.                  |
    | `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | no       | **Validité du cache :** Durée de mise en cache pour des codes de réponse spécifiques.                            |
    | `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | no       | **Pas de cache :** Conditions pour ne pas mettre en cache les réponses même si elles sont normalement cachables. |
    | `PROXY_CACHE_BYPASS`         | `0`                                | multisite | no       | **Contournement du cache :** Conditions sous lesquelles contourner le cache.                                     |

    !!! tip "Bonnes pratiques de mise en cache"
        - Ne mettez en cache que le contenu qui ne change pas fréquemment ou qui n'est pas personnalisé
        - Utilisez des durées de cache appropriées en fonction du type de contenu (les ressources statiques peuvent être mises en cache plus longtemps)
        - Configurez `PROXY_NO_CACHE` pour éviter de mettre en cache du contenu sensible ou personnalisé
        - Surveillez les taux de réussite du cache et ajustez les paramètres en conséquence

!!! danger "Utilisateurs de Docker Compose - Variables NGINX"
    Lorsque vous utilisez Docker Compose avec des variables NGINX dans vos configurations, vous devez échapper le signe dollar (`$`) en utilisant des doubles signes dollar (`$$`). Cela s'applique à tous les paramètres contenant des variables NGINX comme `$remote_addr`, `$proxy_add_x_forwarded_for`, etc.

    Sans cet échappement, Docker Compose essaiera de substituer ces variables par des variables d'environnement, qui n'existent généralement pas, ce qui entraînera des valeurs vides dans votre configuration NGINX.

### Exemples de configuration

=== "Proxy HTTP de base"

    Une configuration simple pour proxifier les requêtes HTTP vers un serveur d'application backend :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "Application WebSocket"

    Configuration optimisée pour une application WebSocket avec des délais d'attente plus longs :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Emplacements multiples"

    Configuration pour router différents chemins vers différents services backend :

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # Backend API
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Backend Admin
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Application Frontend
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Configuration du cache"

    Configuration avec mise en cache du proxy activée pour de meilleures performances :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Gestion avancée des en-têtes"

    Configuration avec manipulation personnalisée des en-têtes :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # En-têtes personnalisés vers le backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # En-têtes personnalisés vers le client
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Intégration de l'authentification"

    Configuration avec authentification externe :

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Configuration de l'authentification
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Backend du service d'authentification
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```
