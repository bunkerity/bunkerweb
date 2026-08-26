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

### Upstreams réutilisables

Les paramètres ci-dessous font pointer un `location` vers un seul backend. Lorsque plusieurs backends servent la même application, ou que plusieurs services partagent les mêmes backends, vous pouvez à la place déclarer un **pool nommé et réutilisable** — un upstream — depuis la page **Upstreams** de l'interface web ou via les endpoints d'API `/upstreams`, et l'attacher à autant de services que vous le souhaitez. Modifier le pool met à jour tous les services auxquels il est attaché.

- Un pool porte un nom, un **protocole**, une méthode de répartition de charge (`round_robin`, `least_conn` ou `ip_hash`), un nombre de connexions `keepalive` facultatif, et un ou plusieurs serveurs.
- Chaque serveur porte son adresse (`hôte` ou `hôte:port`, sans schéma), un `weight`, et les paramètres de contrôle de santé passif `max_fails` et `fail_timeout` ; il peut aussi être marqué `backup` (utilisé uniquement lorsque les autres échouent) ou `down` (temporairement retiré).
- Le **protocole** décide quel consommateur utilise le pool et comment il est attaché :
    - `http` — le reverse proxy (`proxy_pass`). Attaché à un **service et un chemin**, de sorte qu'un même service peut relayer `/` vers un pool et `/api` vers un autre.
    - `grpc` — le plugin gRPC (`grpc_pass`), attaché de la même façon. Les pools HTTP et gRPC partagent un seul espace de noms de chemins, puisque tous deux rendent un `location` dans le même serveur.
    - `stream` — un service TCP/UDP. Il n'y a pas de chemin : le pool prend en charge tout le service et remplace le backend unique implicite que la configuration stream construit à partir de `REVERSE_PROXY_HOST`. Un service ne peut en porter qu'un seul, et `keepalive` ne s'applique pas.
- Le commutateur `backend_ssl` sélectionne TLS vers les serveurs : `https://` au lieu de `http://`, `grpcs://` au lieu de `grpc://`.
- Le protocole doit correspondre au service : un pool HTTP ou gRPC va sur un service dont le `SERVER_TYPE` est `http`, un pool stream sur un service dont le `SERVER_TYPE` est `stream`. L'interface web ne propose que les services compatibles ; l'API refuse les autres avec une explication.
- Les paramètres `REVERSE_PROXY_HOST` et `GRPC_HOST` en ligne continuent de fonctionner exactement comme avant. Les pools attachés sont rendus **après** eux, en prenant les suffixes libres suivants, de sorte que les configurations existantes ne changent pas et qu'aucune migration n'est nécessaire. Un service auquel un pool est attaché voit `USE_REVERSE_PROXY` (ou `USE_GRPC`) activé automatiquement.
- **Un chemin, un propriétaire.** Le reverse proxy, gRPC et les **redirections** rendent tous un `location` dans le même serveur, et NGINX refuse deux blocs `location` portant la même URI. Un chemin est donc pris pour les trois à la fois — qu'il soit revendiqué par un pool attaché, une redirection attachée ou un paramètre en ligne — et la modification en conflit est refusée avec un message nommant ce qui le détient déjà.
- Un pool attaché à rien ne rend rien, et la suppression d'un pool est refusée tant qu'il est encore attaché à un service ; détachez-le d'abord. Changer le protocole d'un pool attaché est refusé pour la même raison.
- Les noms de pool n'acceptent que des lettres, des chiffres, des tirets et des tirets bas. Les points sont refusés volontairement : NGINX résout un nom contre les upstreams déclarés avant le résolveur DNS, donc un pool nommé comme un hôte réel capterait le trafic qui lui est destiné.

### TLS mutuel avec l'upstream

Les paramètres `REVERSE_PROXY_SSL_VERIFY` ci-dessous vérifient le certificat *du backend*. Pour présenter aussi un certificat **au** backend — TLS mutuel — configurez la paire client :

- `REVERSE_PROXY_SSL_CLIENT_CERT` / `REVERSE_PROXY_SSL_CLIENT_KEY` pour des chemins de fichiers lisibles par le scheduler, ou `REVERSE_PROXY_SSL_CLIENT_CERT_DATA` / `REVERSE_PROXY_SSL_CLIENT_KEY_DATA` pour du PEM en base64 ou en clair, sélectionnés par `REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY` (`file` ou `data`).
- La paire est validée avec OpenSSL, mise en cache et distribuée à chaque instance par le même job que celui qui gère l'autorité de certification de confiance, et y est écrite avec des permissions restreintes au propriétaire et au groupe.
- **Les deux moitiés sont obligatoires.** Un certificat sans sa clé (ou l'inverse) est refusé plutôt qu'appliqué à moitié, car NGINX a besoin des deux directives ou d'aucune.
- L'identité est **par service, et partagée avec gRPC et stream** : un service s'authentifie auprès de ses backends avec un seul certificat, quel que soit le plugin qui relaie le trafic. Dans le contexte stream, c'est aussi ce qui active TLS vers le backend (`proxy_ssl on`), de sorte qu'un service sans paire client conserve son comportement en clair actuel.
- Effacer les paramètres supprime les fichiers à l'exécution suivante, ce qui désactive le TLS mutuel.

C'est indépendant du plugin `mtls`, qui authentifie *les clients qui se connectent à BunkerWeb* — la direction opposée.

!!! warning "Un backend non résoluble fait échouer le rechargement"
    NGINX résout les adresses des serveurs upstream au chargement de sa configuration. Si un serveur d'un pool attaché ne peut pas être résolu, toute la configuration est refusée et BunkerWeb conserve la dernière valide. Utilisez une adresse qui se résout au moment du rechargement, ou marquez le serveur comme `down` tant qu'il est indisponible.

### Guide de configuration

=== "Configuration de base"

    **Paramètres principaux**

    Les paramètres de configuration essentiels activent et contrôlent la fonctionnalité de base du reverse proxy.

    !!! success "Bénéfices du Reverse Proxy"
        - **Amélioration de la sécurité :** Tout le trafic passe par les couches de sécurité de BunkerWeb avant d'atteindre vos applications
        - **Terminaison SSL :** Gérez les certificats SSL/TLS de manière centralisée tandis que les services backend peuvent utiliser des connexions non chiffrées
        - **Gestion des protocoles :** Prise en charge de HTTP, HTTPS, WebSockets, et d'autres protocoles
        - **Interception des erreurs :** Personnalisez les pages d'erreur pour une expérience utilisateur cohérente

    | Paramètre                         | Défaut | Contexte  | Multiple | Description                                                                                                                                                                                                                                       |
    | --------------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_REVERSE_PROXY`               | `no`   | multisite | no       | **Activer le Reverse Proxy :** Mettre à `yes` pour activer la fonctionnalité de reverse proxy.                                                                                                                                                    |
    | `REVERSE_PROXY_HOST`              |        | multisite | yes      | **Hôte Backend :** URL complète de la ressource proxifiée (proxy_pass).                                                                                                                                                                           |
    | `REVERSE_PROXY_URL`               | `/`    | multisite | yes      | **URL d'emplacement :** Chemin qui sera proxifié vers le serveur backend. Une valeur commençant par `^` ou se terminant par `$` est traitée comme un emplacement défini par une expression régulière.                                             |
    | `REVERSE_PROXY_BUFFERING`         | `yes`  | multisite | yes      | **Mise en tampon de la réponse :** Active ou désactive la mise en tampon des réponses de la ressource proxifiée.                                                                                                                                  |
    | `REVERSE_PROXY_REQUEST_BUFFERING` | `yes`  | multisite | yes      | **Mise en tampon des requêtes :** Active ou désactive la mise en tampon des requêtes vers la ressource proxifiée.                                                                                                                                 |
    | `REVERSE_PROXY_KEEPALIVE`         | `no`   | multisite | yes      | **Keep-Alive :** Active ou désactive les connexions keepalive avec la ressource proxifiée.                                                                                                                                                        |
    | `REVERSE_PROXY_HTTP_VERSION`      | `1.1`  | multisite | yes      | **Version HTTP :** Version du protocole HTTP utilisée pour communiquer avec l'amont (`1.0`, `1.1` ou `2`). Définissez à `2` pour activer le multiplexage HTTP/2 sur le lien amont. Les emplacements WebSocket sont fixés à 1.1 quoi qu'il arrive. |
    | `REVERSE_PROXY_CUSTOM_HOST`       |        | multisite | no       | **Hôte personnalisé :** Remplace l'en-tête Host envoyé au serveur en amont.                                                                                                                                                                       |
    | `REVERSE_PROXY_INTERCEPT_ERRORS`  | `yes`  | multisite | no       | **Intercepter les erreurs :** Intercepte et réécrit les réponses d'erreur du backend.                                                                                                                                                             |

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
    | `REVERSE_PROXY_STREAM_HALF_CLOSE` | `no` | multisite | oui | **Fermeture à moitié (stream) :** à `yes`, garde la connexion vers le backend ouverte après que le client a fermé son sens d'écriture. Nécessaire pour les protocoles TCP où le client ferme à moitié puis attend la réponse ; nginx ferme les deux sens par défaut. Services stream (TCP/UDP) uniquement. |
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
    | `REVERSE_PROXY_SSL_VERIFY`                       | `no`   | multisite | no       | **SSL Verify :** Active ou désactive la vérification du certificat SSL du serveur amont.                |
    | `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file` | multisite | no       | **Priorité du certificat de confiance :** Source de l'AC de confiance : `file` (chemin) ou `data` (base64/PEM). |
    | `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE`          |        | multisite | no       | **Chemin du certificat de confiance SSL :** Chemin vers un bundle d'AC au format PEM (lisible par le planificateur) utilisé pour vérifier l'amont. |
    | `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA`     |        | multisite | no       | **Données du certificat de confiance SSL :** AC de confiance fournie directement en base64 ou PEM (p. ex. via l'interface web). |
    | `REVERSE_PROXY_SSL_VERIFY_DEPTH`                 | `1`    | multisite | no       | **Profondeur de vérification SSL :** Profondeur de vérification dans la chaîne de certificats de l'amont. |
    | `REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY` | `file` | multisite | non | **Priorité du certificat client :** Source du certificat et de la clé présentés à l'upstream : `file` (chemin) ou `data` (base64/PEM). |
    | `REVERSE_PROXY_SSL_CLIENT_CERT` | | multisite | non | **Chemin du certificat client :** Chemin vers le certificat client PEM que BunkerWeb présente à l'upstream, lisible par le scheduler. Nécessite la clé correspondante. |
    | `REVERSE_PROXY_SSL_CLIENT_CERT_DATA` | | multisite | non | **Données du certificat client :** Certificat client fourni directement en base64 ou en PEM (par ex. via l'interface web). |
    | `REVERSE_PROXY_SSL_CLIENT_KEY` | | multisite | non | **Chemin de la clé client :** Chemin vers la clé privée PEM correspondant au certificat client, lisible par le scheduler. |
    | `REVERSE_PROXY_SSL_CLIENT_KEY_DATA` | | multisite | non | **Données de la clé client :** Clé privée client fournie directement en base64 ou en PEM. Préférez un chemin de fichier quand c'est possible : une clé définie ici est stockée comme valeur de paramètre. |

    !!! info "Vérification du certificat"
        Lorsque `REVERSE_PROXY_SSL_VERIFY` est défini sur `yes`, NGINX valide à la fois la chaîne de certificats de l'amont et son nom :

        - **AC de confiance :** fournissez-la soit comme chemin de fichier (`REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE`, lisible par le planificateur), soit comme données base64/PEM (`REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA`), selon `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY`. Le planificateur la valide, la met en cache et la distribue à chaque instance, vous ne la configurez donc qu'une fois, sans montage par instance.
        - **Obligatoire :** un certificat de confiance est requis ; NGINX n'a pas de magasin système implicite pour la vérification de l'amont. Pour vérifier un amont public, pointez le chemin vers le bundle d'AC du système (p. ex. `/etc/ssl/certs/ca-certificates.crt`).
        - **Nom :** vérifié par défaut par rapport à l'hôte issu de `REVERSE_PROXY_HOST`. Si le CN/SAN du certificat du backend diffère, définissez `REVERSE_PROXY_SSL_SNI` sur `yes` et `REVERSE_PROXY_SSL_SNI_NAME` sur le nom attendu.
        - **Sécurité intégrée :** si aucun certificat de confiance valide n'est disponible, la vérification est désactivée pour ce serveur au lieu de rompre chaque connexion amont.

        Ces paramètres s'appliquent par service : toutes les entrées amont (`REVERSE_PROXY_HOST`, `REVERSE_PROXY_HOST_1`, ...) partagent la même configuration de vérification.

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

    | Paramètre                         | Défaut | Contexte  | Multiple | Description                                                                                                                                                                                                                |
    | --------------------------------- | ------ | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `REVERSE_PROXY_INCLUDES`          |        | multisite | yes      | **Configurations supplémentaires :** Incluez des configurations additionnelles dans le bloc location.                                                                                                                      |
    | `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`  | multisite | yes      | **Passer le corps de la requête :** Active ou désactive la transmission du corps de la requête.                                                                                                                            |
    | `REVERSE_PROXY_MODSECURITY`       | `yes`  | multisite | yes      | **ModSecurity (par location) :** Mettez à `no` pour émettre `modsecurity off;` dans cette location ; contourne le WAF sur les points de terminaison de gros téléversements afin d'éviter un OOM (voir la note ci-dessous). |
    | `REVERSE_PROXY_SEND_PROXY_PROTOCOL` | `auto` | multisite | non | **Envoyer le protocole PROXY :** Envoie l'en-tête du protocole PROXY à l'upstream stream. `auto` suit le paramètre global `USE_PROXY_PROTOCOL`, ce que BunkerWeb faisait avant l'existence de ce paramètre ; `yes` et `no` décident indépendamment du listener entrant. Services stream (TCP/UDP) uniquement. |

    !!! warning "Considérations de sécurité"
        Soyez prudent lorsque vous incluez des extraits de configuration personnalisés car ils peuvent outrepasser les paramètres de sécurité de BunkerWeb ou introduire des vulnérabilités s'ils ne sont pas correctement configurés.

    !!! warning "Recommandation de sécurité pour les gros téléversements"
        ModSecurity met en mémoire tampon le corps complet de la requête et ne peut pas le plafonner pour les téléversements de plusieurs Go, ce qui peut provoquer un OOM du worker. Si, **et seulement si**, une URL de reverse proxy est utilisée *exclusivement* pour les téléversements de fichiers (par exemple un point de terminaison `/upload` dédié), définissez `REVERSE_PROXY_MODSECURITY_N: "no"` sur cette URL. Ne le désactivez pas sur des URL à usage mixte : vous perdriez la couverture WAF sur tout ce qui est servi par cette location.

        Pour conserver une protection des téléversements après le contournement de ModSecurity, associez cela à un plugin d'analyse de fichiers comme [ClamAV](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav) ou [VirusTotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) ; ils inspectent le fichier téléversé lui-même plutôt que le corps brut de la requête.

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
