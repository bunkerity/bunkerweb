Le plugin Divers (Miscellaneous) fournit des **paramètres de base essentiels** qui aident à maintenir la sécurité et la fonctionnalité de votre site web. Ce composant central offre des contrôles complets pour :

- **Le comportement du serveur** - Configurez la manière dont votre serveur répond à diverses requêtes
- **Les paramètres HTTP** - Gérez les méthodes, la taille des requêtes et les options de protocole
- **La gestion des fichiers** - Contrôlez le service des fichiers statiques et optimisez leur livraison
- **Le support des protocoles** - Activez les protocoles HTTP modernes pour de meilleures performances
- **Les configurations système** - Étendez les fonctionnalités et améliorez la sécurité

Que vous ayez besoin de restreindre les méthodes HTTP, de gérer la taille des requêtes, d'optimiser la mise en cache des fichiers ou de contrôler la manière dont votre serveur répond à diverses requêtes, ce plugin vous donne les outils pour **affiner le comportement de votre service web** tout en optimisant à la fois la performance et la sécurité.

### Fonctionnalités clés

| Catégorie de fonctionnalité           | Description                                                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Contrôle des méthodes HTTP**        | Définissez quelles méthodes HTTP sont acceptables pour votre application                                     |
| **Protection du serveur par défaut**  | Empêchez l'accès non autorisé par des noms d'hôte incorrects et forcez le SNI pour les connexions sécurisées |
| **Gestion de la taille des requêtes** | Définissez des limites pour le corps des requêtes client et les téléversements de fichiers                   |
| **Service de fichiers statiques**     | Configurez et optimisez la livraison de contenu statique depuis des dossiers racine personnalisés            |
| **Mise en cache des fichiers**        | Améliorez les performances grâce à des mécanismes avancés de mise en cache des descripteurs de fichiers      |
| **Support des protocoles**            | Configurez les options des protocoles HTTP modernes (HTTP2/HTTP3) et les paramètres de port Alt-Svc          |
| **Rapport anonyme**                   | Rapport de statistiques d'utilisation optionnel pour aider à améliorer BunkerWeb                             |
| **Support des plugins externes**      | Étendez les fonctionnalités en intégrant des plugins externes via des URL                                    |
| **Contrôle du statut HTTP**           | Configurez la réponse de votre serveur lors du refus de requêtes (y compris la fermeture de connexion)       |

### Guide de configuration

=== "Sécurité du serveur par défaut"

    **Contrôles du serveur par défaut**

    En HTTP, l'en-tête `Host` spécifie le serveur cible, mais il peut être manquant ou inconnu, souvent à cause de bots recherchant des vulnérabilités.

    Pour bloquer de telles requêtes :

    - Mettez `DISABLE_DEFAULT_SERVER` à `yes` pour refuser silencieusement ces requêtes en utilisant le [code de statut `444` de NGINX](https://http.dev/444).
    - Pour une sécurité plus stricte, activez `DISABLE_DEFAULT_SERVER_STRICT_SNI` pour rejeter les connexions SSL/TLS sans SNI valide.

    !!! success "Avantages en matière de sécurité"
        - Bloque la manipulation de l'en-tête Host et le scan des hôtes virtuels
        - Atténue les risques de contrebande de requêtes HTTP (HTTP request smuggling)
        - Supprime le serveur par défaut comme vecteur d'attaque

    | Paramètre                           | Défaut | Contexte | Multiple | Description                                                                                                                       |
    | ----------------------------------- | ------ | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
    | `DISABLE_DEFAULT_SERVER`            | `no`   | global   | no       | **Serveur par défaut :** Mettre à `yes` pour désactiver le serveur par défaut lorsqu'aucun nom d'hôte ne correspond à la requête. |
    | `DISABLE_DEFAULT_SERVER_STRICT_SNI` | `no`   | global   | no       | **SNI Strict :** Si mis à `yes`, requiert le SNI pour les connexions HTTPS et rejette les connexions sans SNI valide.             |

    !!! warning "Application du SNI"
        Activer la validation stricte du SNI offre une sécurité renforcée mais peut causer des problèmes si BunkerWeb est derrière un proxy inverse qui transmet les requêtes HTTPS sans préserver les informations SNI. Testez minutieusement avant d'activer en production. `DISABLE_DEFAULT_SERVER_STRICT_SNI` n'a de serveur par défaut sur lequel s'appliquer que lorsque `MULTISITE=yes` (ou `DISABLE_DEFAULT_SERVER=yes` en mode mono-site) — en mono-site pur, il est silencieusement sans effet, puisque le bloc de votre propre service est déjà celui par défaut de NGINX.

=== "Configuration du serveur par défaut"

    **Le serveur par défaut est un service que vous pouvez modifier**

    Le bloc qui répond aux requêtes ne correspondant à aucun service configuré — un nom d'hôte inconnu, une adresse IP brute, un `Host` que personne ne sert — est exposé comme un **service réservé nommé `default-server`**. Il apparaît épinglé en haut de la liste des services dans l'interface web et `GET /services` le renvoie marqué `reserved: true`.

    !!! warning "Multisite uniquement"
        C'est une **fonctionnalité multisite** : tout ce qui figure sur cette page s'applique lorsque `MULTISITE` vaut `yes`. Les réglages par service ne sont matérialisés et résolubles à l'exécution qu'en mode multisite, donc avec `MULTISITE=no` le service réservé est inerte et invisible — la ligne réservée n'apparaît pas dans `GET /services`, n'est pas affichée dans l'interface web, n'apparaît jamais dans `SERVER_NAME` — un service à vous qui porterait ce même nom est un cas différent, voir la note de mise à niveau à la fin de ce paragraphe — et les trois exécuteurs de phase décrits plus bas ne sont pas rendus. Le serveur par défaut se comporte exactement comme avant la 1.7, et la surcharge globale de certificat `DEFAULT_SERVER_SSL_*` est stockée mais servie uniquement là où existe un bloc de serveur par défaut : avec `MULTISITE=no`, cela signifie `DISABLE_DEFAULT_SERVER=yes`, sinon le bloc de votre unique service est celui par défaut de NGINX et répond aux requêtes non appariées avec son propre certificat (le job journalise un avertissement à ce sujet). Sur un déploiement mono-site existant, la ligne n'est pas créée du tout ; sur une nouvelle installation, elle peut être créée avant que `MULTISITE` n'ait été écrit pour la première fois, auquel cas elle reste simplement en base sans rien faire. Mettez `MULTISITE=yes` et le service réservé sera là à la prochaine sauvegarde de configuration, sans redémarrage. Si un de vos services s'appelle déjà `default-server`, il n'est **pas** adopté : une erreur le nommant est journalisée, et — contrairement au service réservé — il peut toujours être renommé et supprimé pour le sortir du chemin. Avec `MULTISITE=no`, il continue aussi d'être servi exactement comme n'importe lequel de vos services : le nom reste dans `SERVER_NAME` et son bloc `server{}` est rendu, avec un avertissement à chaque génération vous demandant de le renommer avant d'activer `MULTISITE`.

    C'est une véritable ligne de service, donc son certificat, ses réglages TLS, ses en-têtes de réponse, ses pages d'erreur et sa whitelist sont stockés et modifiés exactement comme ceux de n'importe quel autre service. Il est aussi permanent : il ne peut être créé, renommé, converti en brouillon ni supprimé, il n'est jamais compté dans le quota de services PRO, et un déploiement autoconf qui retire son dernier ingress ne le supprime pas.

    Seuls les réglages qui ont un sens sans nom d'hôte sont proposés sur sa page : les fournisseurs de certificat, le TLS, `errors`, `headers`, `whitelist` et les réglages divers. Le reverse proxy, gRPC, les redirections, les sessions, l'antibot, le mTLS, le CORS et l'authentification HTTP basique ne le sont pas — il n'y a pas de `Host` vers lequel router ni d'identité de service à laquelle se lier, donc ces réglages seraient stockés sans jamais s'appliquer.

    Ces réglages s'exécutent réellement : le serveur par défaut exécute les phases `set`, `access` et `header` de ce sous-ensemble sélectionné, ce qu'il ne faisait jamais auparavant. Pour qu'une mise à niveau de déploiement ne change pas ce que répond son bloc fourre-tout, le service réservé est **pré-rempli** à sa création avec `AUTO_REDIRECT_HTTP_TO_HTTPS=no`, `REDIRECT_HTTP_TO_HTTPS=no` et `USE_WHITELIST=no` — visibles sur sa page, et modifiables par vous. Seulement à la création : une ligne existante n'est jamais réécrite. Sur une installation **neuve**, la ligne peut être créée avant que la table des réglages ne soit peuplée, auquel cas elle ne porte aucune valeur pré-remplie et le fourre-tout suit vos réglages globaux ; lors des mises à niveau, où un comportement doit être préservé, le pré-remplissage a toujours lieu.

    Un comportement est volontairement nouveau : `ALLOWED_METHODS` s'applique désormais ici aussi, donc une requête vers un nom d'hôte que vous ne servez pas avec une méthode hors de `GET|POST|HEAD|QUERY` reçoit `405` au lieu de la page par défaut. Les bans sont appliqués sur le serveur par défaut et les en-têtes de réponse y sont émis, ce qui est précisément le but de le rendre configurable.

    !!! info "Où vit le certificat"
        Le certificat que présente le serveur par défaut est défini par les quatre réglages **globaux** `DEFAULT_SERVER_SSL_*` du plugin [Certificat SSL personnalisé](#custom-ssl-certificate), pas par un réglage par service. La page du serveur par défaut renvoie directement vers eux.

    **Fourre-tout stream (TCP)**

    En `stream`, il n'y a pas de SNI en TCP brut et aucun du tout en UDP, donc NGINX sélectionne un bloc uniquement par `address:port` : un serveur par défaut sur un port qu'un service écoute l'emporterait là et répondrait au trafic de ce service. Le serveur par défaut de stream est donc opt-in et possède ses propres ports.

    | Paramètre                        | Défaut | Contexte  | Multiple | Description                                                                                                                                                             |
    | ------------------------------ | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `DEFAULT_SERVER_STREAM_PORTS`  |         | multisite | oui      | **Ports Stream du Serveur par défaut :** Ports sur lesquels le serveur par défaut accepte les connexions stream (TCP) ne correspondant à aucun service configuré. Vide le désactive, ce qui est la valeur par défaut. |
    | `DEFAULT_SERVER_STREAM_PORTS_SSL` |      | multisite | oui      | **Ports Stream du Serveur par défaut (TLS) :** Lesquels de ces ports sont servis en TLS. Doit être un sous-ensemble de `DEFAULT_SERVER_STREAM_PORTS` ; vide signifie TCP simple uniquement.               |

    Définissez-le sur le service réservé, par exemple `default-server_DEFAULT_SERVER_STREAM_PORTS=9000` (et `_1`, `_2`, … pour d'autres ports). C'est un réglage multisite comme un autre, donc le définir **globalement** atteint aussi le serveur par défaut et y ouvre l'écoute — si ce n'est pas ce que vous voulez, limitez-le à `default-server`.

    Trois types de port sont **refusés** lorsque vous les enregistrez sur le service réservé — sa page dans l'interface web, ou `PATCH /services/default-server` — chacun nommant ce qui l'occupe déjà : un port qu'un service stream écoute (sans SNI le serveur par défaut répondrait au trafic de ce service), un port utilisé par un écouteur HTTP ou HTTPS n'importe où dans le déploiement, et un port que BunkerWeb réserve pour lui-même (le serveur de healthcheck, l'API interne, et sur l'image all-in-one son service d'interface web et d'API). Le second n'est pas une préférence : `http{}` et `stream{}` ouvrent leurs propres sockets, donc le même port dans les deux fait échouer le démarrage de NGINX — et `8080`, le `HTTP_PORT` par défaut, est exactement ce cas.

    Écrit **globalement** à la place, la même valeur est acceptée — la page des réglages globaux n'est pas le chemin de sauvegarde du service réservé — et résolue au moment de la génération : le port fautif est retiré du bloc du serveur par défaut et la raison est journalisée. La même chose arrive à un port qu'un service stream réclame *après* que vous l'avez enregistré. Dans les deux cas, le vrai service conserve toujours son port.

    Un port également listé dans `DEFAULT_SERVER_STREAM_PORTS_SSL` est servi avec `ssl` et présente le certificat `DEFAULT_SERVER_SSL_*`. Cette liste est l'interrupteur TLS des ports ci-dessus, pas un second jeu d'écouteurs : un port qui y figure mais que `DEFAULT_SERVER_STREAM_PORTS` ne contient pas est refusé à l'enregistrement, et abandonné avec une ligne de log s'il a atteint la base d'une autre façon. Chaque connexion est répondue puis fermée ; le serveur par défaut de stream ne fait jamais proxy.

=== "Statut HTTP en cas de refus"

    **Contrôle du statut HTTP**

    La première étape dans la gestion de l'accès refusé à un client est de définir l'action appropriée. Cela peut être configuré avec le paramètre `DENY_HTTP_STATUS`. Lorsque BunkerWeb refuse une requête, vous pouvez contrôler sa réponse. Par défaut, il renvoie un statut `403 Forbidden`, affichant une page web ou un contenu personnalisé.

    Alternativement, le régler sur `444` ferme immédiatement la connexion sans envoyer de réponse. Ce [code de statut non standard](https://http.dev/444), spécifique à NGINX, est utile pour ignorer silencieusement les requêtes indésirables.

    | Paramètre          | Défaut | Contexte | Multiple | Description                                                                                                                          |
    | ------------------ | ------ | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
    | `DENY_HTTP_STATUS` | `403`  | global   | no       | **Statut HTTP de refus :** Code de statut HTTP à envoyer quand une requête est refusée (403 ou 444). Le code 444 ferme la connexion. |

    !!! warning "Considérations sur le code de statut 444"
        Comme les clients ne reçoivent aucun retour, le dépannage peut être plus difficile. Régler sur `444` est recommandé uniquement si vous avez minutieusement traité les faux positifs, êtes expérimenté avec BunkerWeb et exigez un niveau de sécurité plus élevé.

    !!! info "Mode stream"
        En **mode stream**, ce paramètre est toujours appliqué comme `444`, ce qui signifie que la connexion sera fermée, quelle que soit la valeur configurée.

=== "Méthodes HTTP"

    **Contrôle des méthodes HTTP**

    Restreindre les méthodes HTTP à celles requises par votre application est une mesure de sécurité fondamentale qui respecte le principe du moindre privilège. En définissant explicitement les méthodes acceptables, vous minimisez le risque d'exploitation via des méthodes inutilisées ou dangereuses.

    Cette fonctionnalité est configurée avec `ALLOWED_METHODS`, où les méthodes sont listées et séparées par un `|` (défaut : `GET|POST|HEAD|QUERY`). Si un client tente une méthode non listée, le serveur répondra avec un statut **405 - Method Not Allowed**.

    Pour la plupart des sites web, le défaut `GET|POST|HEAD|QUERY` est suffisant. Si votre application utilise des API RESTful, vous devrez peut-être inclure `PUT` et `DELETE`. Les méthodes personnalisées en majuscules peuvent également contenir des underscores et des tirets pour la compatibilité avec des protocoles non standards (ex. `CCM_POST`, `M-SEARCH`).

    !!! success "Avantages en matière de sécurité"
        - Empêche l'exploitation de méthodes HTTP inutilisées ou inutiles
        - Réduit la surface d'attaque en désactivant les méthodes potentiellement dangereuses
        - Bloque les techniques d'énumération de méthodes HTTP utilisées par les attaquants

    | Paramètre         | Défaut            | Contexte  | Multiple | Description                                                                                   |
    | ----------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------- |
    | `ALLOWED_METHODS` | `GET\|POST\|HEAD\|QUERY` | multisite | no       | **Méthodes HTTP :** Liste des méthodes HTTP autorisées, séparées par des barres verticales (` | `). Les méthodes personnalisées en majuscules peuvent contenir des underscores et des tirets. |

    !!! abstract "CORS et requêtes pre-flight"
        Si votre application prend en charge le [Cross-Origin Resource Sharing (CORS)](#cors), vous devriez inclure la méthode `OPTIONS` dans `ALLOWED_METHODS` pour gérer les requêtes pre-flight. Cela garantit le bon fonctionnement pour les navigateurs effectuant des requêtes inter-origines.

    !!! danger "Considérations de sécurité"
        - **Évitez d'activer `TRACE` ou `CONNECT` :** Ces méthodes sont rarement nécessaires et peuvent introduire des risques de sécurité importants, comme le Cross-Site Tracing (XST) ou les attaques par tunnelisation.
        - **Révisez régulièrement les méthodes autorisées :** Auditez périodiquement `ALLOWED_METHODS` pour vous assurer qu'il correspond aux besoins actuels de votre application.
        - **Testez minutieusement avant le déploiement :** Les changements de restrictions de méthodes HTTP peuvent impacter la fonctionnalité de l'application. Validez votre configuration dans un environnement de pré-production.

=== "Limites de taille des requêtes"

    **Limites de taille des requêtes**

    La taille maximale du corps d'une requête peut être contrôlée avec `MAX_CLIENT_SIZE` (défaut : `10m`). Les valeurs acceptées suivent la syntaxe décrite [ici](https://nginx.org/en/docs/syntax.html).

    !!! success "Avantages en matière de sécurité"
        - Protège contre les attaques par déni de service causées par des charges utiles excessives
        - Atténue les vulnérabilités de débordement de tampon (buffer overflow)
        - Empêche les attaques par téléversement de fichiers
        - Réduit le risque d'épuisement des ressources du serveur

    | Paramètre         | Défaut | Contexte  | Multiple | Description                                                                                                                                       |
    | ----------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `MAX_CLIENT_SIZE` | `10m`  | multisite | no       | **Taille maximale des requêtes :** La taille maximale autorisée pour le corps des requêtes client (ex. : téléversements).                         |
    | `MAX_HEADERS`     | `100`  | global    | no       | **En-têtes maximum :** Nombre maximum de lignes d'en-tête par requête. Les requêtes dépassant cette limite sont rejetées avec `400 Bad Request`.  |

    !!! tip "Bonnes pratiques de configuration de la taille des requêtes"
        Si vous devez autoriser un corps de requête de taille illimitée, vous pouvez mettre la valeur `MAX_CLIENT_SIZE` à `0`. Cependant, ce n'est **pas recommandé** en raison des risques potentiels de sécurité et de performance.

        **Bonnes pratiques :**

        - Configurez toujours `MAX_CLIENT_SIZE` à la plus petite valeur répondant aux besoins légitimes de votre application.
        - Révisez et ajustez régulièrement ce paramètre pour l'aligner sur les besoins évolutifs de votre application.
        - Évitez de mettre `0` sauf en cas de nécessité absolue, car cela peut exposer votre serveur à des attaques par déni de service et à l'épuisement des ressources.

        En gérant soigneusement ce paramètre, vous pouvez garantir une sécurité et des performances optimales pour votre application.

=== "Support des protocoles"

    **Paramètres des protocoles HTTP**

    Les protocoles HTTP modernes comme HTTP/2 et HTTP/3 améliorent la performance et la sécurité. BunkerWeb permet une configuration facile de ces protocoles.

    !!! success "Avantages en matière de sécurité et de performance"
        - **Avantages de sécurité :** Les protocoles modernes comme HTTP/2 et HTTP/3 imposent TLS/HTTPS par défaut, réduisent la sensibilité à certaines attaques et améliorent la confidentialité grâce aux en-têtes chiffrés (HTTP/3).
        - **Avantages de performance :** Des fonctionnalités comme le multiplexage, la compression des en-têtes, le server push et le transfert de données binaires améliorent la vitesse et l'efficacité.

    | Paramètre            | Défaut | Contexte  | Multiple | Description                                                                   |
    | -------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------- |
    | `LISTEN_HTTP`        | `yes`  | multisite | no       | **Écoute HTTP :** Répondre aux requêtes HTTP (non sécurisées) si mis à `yes`. Peut également être désactivé en laissant `HTTP_PORT` vide. |
    | `HTTP2`              | `yes`  | multisite | no       | **HTTP2 :** Supporte le protocole HTTP2 lorsque HTTPS est activé.             |
    | `HTTP3`              | `yes`  | multisite | no       | **HTTP3 :** Supporte le protocole HTTP3 lorsque HTTPS est activé.             |
    | `HTTP3_ALT_SVC_PORT` | `443`  | multisite | no       | **Port Alt-Svc HTTP3 :** Port à utiliser dans l'en-tête Alt-Svc pour HTTP3.   |

    !!! example "À propos de HTTP/3"
        HTTP/3, la dernière version du protocole Hypertext Transfer, utilise QUIC sur UDP au lieu de TCP, résolvant des problèmes comme le blocage en tête de ligne pour des connexions plus rapides et plus fiables.

        NGINX a introduit un support expérimental pour HTTP/3 et QUIC à partir de la version 1.25.0. Cependant, cette fonctionnalité est encore expérimentale, et la prudence est de mise pour une utilisation en production. Pour plus de détails, consultez la [documentation officielle de NGINX](https://nginx.org/en/docs/quic.html).

        Des tests approfondis sont recommandés avant d'activer HTTP/3 en production.

        HTTP/3 est silencieusement désactivé lorsque `USE_PROXY_PROTOCOL` vaut `yes`. NGINX ne peut pas lire l'en-tête PROXY protocol sur un écouteur QUIC : aucun écouteur `quic` ni en-tête `Alt-Svc` n'est généré, bien que `HTTP3` indique toujours `yes`, et `LIMIT_CONN_MAX_HTTP3` reste sans effet. Terminez le PROXY protocol en amont, ou limitez-vous à HTTP/1.1 et HTTP/2.

=== "Service de fichiers statiques"

    **Configuration du service de fichiers**

    BunkerWeb peut servir des fichiers statiques directement ou agir comme un proxy inverse vers un serveur d'application. Par défaut, les fichiers sont servis depuis `/var/www/html/{server_name}`.

    | Paramètre     | Défaut                        | Contexte  | Multiple | Description                                                                                                                      |
    | ------------- | ----------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
    | `SERVE_FILES` | `yes`                         | multisite | no       | **Servir des fichiers :** Si `yes`, BunkerWeb servira les fichiers statiques depuis le dossier racine configuré.                 |
    | `ROOT_FOLDER` | `/var/www/html/{server_name}` | multisite | no       | **Dossier racine :** Le répertoire depuis lequel servir les fichiers statiques. Vide signifie utiliser l'emplacement par défaut. |

    !!! tip "Bonnes pratiques pour le service de fichiers statiques"
        - **Service direct :** Activez le service de fichiers (`SERVE_FILES=yes`) lorsque BunkerWeb est responsable de servir directement les fichiers statiques.
        - **Proxy inverse :** Si BunkerWeb agit comme un proxy inverse, **désactivez le service de fichiers** (`SERVE_FILES=no`) pour réduire la surface d'attaque et éviter d'exposer des répertoires inutiles.
        - **Permissions :** Assurez-vous que les permissions de fichiers et les configurations de chemin sont correctes pour empêcher tout accès non autorisé.
        - **Sécurité :** Évitez d'exposer des répertoires ou des fichiers sensibles par des mauvaises configurations.

        En gérant soigneusement le service de fichiers statiques, vous pouvez optimiser les performances tout en maintenant un environnement sécurisé.

=== "Paramètres système"

    **Gestion des plugins et du système**

    Ces paramètres gèrent l'interaction de BunkerWeb avec des systèmes externes et contribuent à l'amélioration du produit via des statistiques d'utilisation anonymes optionnelles.

    **Rapport anonyme**

    Le rapport anonyme fournit à l'équipe de BunkerWeb des informations sur la manière dont le logiciel est utilisé. Cela aide à identifier les domaines d'amélioration et à prioriser le développement de fonctionnalités. Les rapports sont strictement statistiques et n'incluent aucune information sensible ou personnellement identifiable. Ils couvrent :

    - Les fonctionnalités activées
    - Les schémas de configuration généraux

    Vous pouvez désactiver cette fonctionnalité si vous le souhaitez en mettant `SEND_ANONYMOUS_REPORT` à `no`.

    **Plugins externes**

    Les plugins externes vous permettent d'étendre les fonctionnalités de BunkerWeb en intégrant des modules tiers. Cela permet une personnalisation supplémentaire et des cas d'utilisation avancés.

    !!! danger "Sécurité des plugins externes"
        **Les plugins externes peuvent introduire des risques de sécurité s'ils ne sont pas correctement vérifiés.** Suivez ces bonnes pratiques pour minimiser les menaces potentielles :

        - N'utilisez que des plugins provenant de sources fiables.
        - Vérifiez l'intégrité des plugins à l'aide de sommes de contrôle (checksums) lorsqu'elles sont disponibles.
        - Révisez et mettez à jour régulièrement les plugins pour garantir la sécurité et la compatibilité.

        Pour plus de détails, consultez la [documentation des Plugins](plugins.md).

    | Paramètre               | Défaut | Contexte | Multiple | Description                                                                                       |
    | ----------------------- | ------ | -------- | -------- | ------------------------------------------------------------------------------------------------- |
    | `SEND_ANONYMOUS_REPORT` | `yes`  | global   | no       | **Rapports anonymes :** Envoyer des rapports d'utilisation anonymes aux mainteneurs de BunkerWeb. |
    | `EXTERNAL_PLUGIN_URLS`  |        | global   | no       | **Plugins externes :** URL pour télécharger des plugins externes (séparées par des espaces).      |

=== "Mise en cache des fichiers"

    **Optimisation du cache de fichiers**

    Le cache de fichiers ouverts améliore les performances en stockant les descripteurs de fichiers et les métadonnées en mémoire, réduisant ainsi le besoin d'opérations répétées sur le système de fichiers.

    !!! success "Avantages de la mise en cache de fichiers"
        - **Performance :** Réduit les E/S du système de fichiers, diminue la latence et abaisse l'utilisation du CPU pour les opérations sur les fichiers.
        - **Sécurité :** Atténue les attaques par synchronisation (timing attacks) en mettant en cache les réponses d'erreur et réduit l'impact des attaques DoS ciblant le système de fichiers.

    | Paramètre                  | Défaut                  | Contexte  | Multiple | Description                                                                                                                            |
    | -------------------------- | ----------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
    | `USE_OPEN_FILE_CACHE`      | `no`                    | multisite | no       | **Activer le cache :** Activer la mise en cache des descripteurs de fichiers et des métadonnées pour améliorer les performances.       |
    | `OPEN_FILE_CACHE`          | `max=1000 inactive=20s` | multisite | no       | **Configuration du cache :** Configurez le cache de fichiers ouverts (ex. : nombre max d'entrées et délai d'inactivité).               |
    | `OPEN_FILE_CACHE_ERRORS`   | `yes`                   | multisite | no       | **Mettre en cache les erreurs :** Met en cache les erreurs de recherche de descripteurs de fichiers ainsi que les recherches réussies. |
    | `OPEN_FILE_CACHE_MIN_USES` | `2`                     | multisite | no       | **Utilisations minimales :** Nombre minimum d'accès pendant la période d'inactivité pour qu'un fichier reste en cache.                 |
    | `OPEN_FILE_CACHE_VALID`    | `30s`                   | multisite | no       | **Validité du cache :** Temps après lequel les éléments mis en cache sont revalidés.                                                   |

    **Guide de configuration**

    Pour activer et configurer la mise en cache des fichiers :
    1. Mettez `USE_OPEN_FILE_CACHE` à `yes`.
    2. Ajustez les paramètres `OPEN_FILE_CACHE` pour définir le nombre maximum d'entrées et leur délai d'inactivité.
    3. Utilisez `OPEN_FILE_CACHE_ERRORS` pour mettre en cache les recherches réussies et échouées.
    4. Réglez `OPEN_FILE_CACHE_MIN_USES` pour spécifier le nombre d'accès requis pour qu'un fichier reste en cache.
    5. Définissez la période de validité du cache avec `OPEN_FILE_CACHE_VALID`.

    !!! tip "Bonnes pratiques"
        - Activez la mise en cache pour les sites web avec de nombreux fichiers statiques pour améliorer les performances.
        - Révisez et affinez régulièrement les paramètres de cache pour équilibrer performance et utilisation des ressources.
        - Dans les environnements dynamiques où les fichiers changent fréquemment, envisagez de réduire la période de validité du cache ou de désactiver la fonctionnalité pour garantir la fraîcheur du contenu.

### Exemples de configuration

=== "Sécurité du serveur par défaut"

    Exemple pour désactiver le serveur par défaut et forcer le SNI strict :

    ```yaml
    DISABLE_DEFAULT_SERVER: "yes"
    DISABLE_DEFAULT_SERVER_STRICT_SNI: "yes"
    ```

=== "Statut HTTP en cas de refus"

    Exemple pour ignorer silencieusement les requêtes indésirables :

    ```yaml
    DENY_HTTP_STATUS: "444"
    ```

=== "Méthodes HTTP"

    Exemple pour restreindre les méthodes HTTP à celles requises par une API RESTful :

    ```yaml
    ALLOWED_METHODS: "GET|POST|PUT|DELETE"
    ```

=== "Limites de taille des requêtes"

    Exemple pour limiter la taille maximale du corps d'une requête :

    ```yaml
    MAX_CLIENT_SIZE: "5m"
    ```

=== "Support des protocoles"

    Exemple pour activer HTTP/2 et HTTP/3 avec un port Alt-Svc personnalisé :

    ```yaml
    HTTP2: "yes"
    HTTP3: "yes"
    HTTP3_ALT_SVC_PORT: "443"
    ```

=== "Service de fichiers statiques"

    Exemple pour servir des fichiers statiques depuis un dossier racine personnalisé :

    ```yaml
    SERVE_FILES: "yes"
    ROOT_FOLDER: "/var/www/custom-folder"
    ```

=== "Mise en cache des fichiers"

    Exemple pour activer et optimiser la mise en cache des fichiers :

    ```yaml
    USE_OPEN_FILE_CACHE: "yes"
    OPEN_FILE_CACHE: "max=2000 inactive=30s"
    OPEN_FILE_CACHE_ERRORS: "yes"
    OPEN_FILE_CACHE_MIN_USES: "3"
    OPEN_FILE_CACHE_VALID: "60s"
    ```
