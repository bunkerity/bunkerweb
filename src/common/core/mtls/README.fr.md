Le plugin Mutual TLS (mTLS) protège vos applications sensibles en exigeant que les clients présentent des certificats délivrés par des autorités que vous maîtrisez. Une fois activé, BunkerWeb authentifie les appelants avant que leurs requêtes n’atteignent vos services, ce qui sécurise vos outils internes et intégrations partenaires.

BunkerWeb évalue chaque poignée de main TLS en fonction du bundle d’AC et de la politique que vous définissez. Les clients qui ne répondent pas aux règles sont bloqués, tandis que les connexions conformes peuvent transmettre les détails du certificat aux applications amont pour une autorisation affinée.

**Fonctionnement :**

1. Le plugin surveille les échanges HTTPS du site sélectionné.
2. Pendant l’échange TLS, BunkerWeb inspecte le certificat client et vérifie sa chaîne par rapport à votre magasin de confiance.
3. Le mode de vérification détermine si les clients non authentifiés sont rejetés, laissés passer ou autorisés pour des diagnostics. Voir « Ce que protège chaque mode » ci-dessous.
4. (Optionnel) BunkerWeb expose le résultat via les en-têtes `X-SSL-Client-*` afin que vos applications puissent appliquer leur propre logique d’accès.

!!! success "Avantages clés"

      1. **Contrôle renforcé :** limitez l’accès aux machines et utilisateurs authentifiés.
      2. **Politiques souples :** combinez modes stricts et optionnels pour accompagner vos workflows.
      3. **Visibilité applicative :** transférez empreintes et identités de certificats pour l’audit.
      4. **Défense en profondeur :** associez mTLS aux autres plugins BunkerWeb pour multiplier les protections.

### Mise en œuvre

Suivez ces étapes pour déployer le mutual TLS sereinement :

1. **Activer la fonctionnalité :** positionnez `USE_MTLS` à `yes` sur les sites qui nécessitent l’authentification par certificat.
2. **Fournir le bundle d’AC :** renseignez `MTLS_CA_CERTIFICATE` avec le chemin d’un fichier PEM lisible par le Scheduler, ou fournissez le bundle directement sous forme de données base64/PEM via `MTLS_CA_CERTIFICATE_DATA`. Le Scheduler valide, met en cache et distribue le bundle à chaque instance, sans montage nécessaire par instance.
3. **Choisir le mode de vérification :** sélectionnez `on` pour rendre les certificats obligatoires, `optional` pour laisser passer les clients sans certificat (et n’en exiger un que sur les chemins listés dans `MTLS_URL`) ou `optional_no_ca` pour un diagnostic temporaire.
4. **Ajuster la profondeur de chaîne :** adaptez `MTLS_VERIFY_DEPTH` si votre organisation utilise plusieurs intermédiaires.
5. **Transmettre le résultat (optionnel) :** laissez `MTLS_FORWARD_CLIENT_HEADERS` à `yes` si vos services amont doivent inspecter le certificat présenté.
6. **Maintenir la révocation :** si vous publiez une CRL, renseignez `MTLS_CRL` (ou `MTLS_CRL_DATA`) pour que BunkerWeb refuse les certificats révoqués.
7. **Choisir ce que devient le HTTP en clair :** `MTLS_HTTP_POLICY` (`redirect` par défaut) décide du sort des requêtes HTTP en clair que mTLS aurait dû protéger.
8. **Décider si les échecs de certificat comptent pour les bannissements (optionnel) :** `MTLS_COUNT_BAD_BEHAVIOR` (`no` par défaut) permet à Bad Behavior de les compter.

Le Scheduler valide l’intégralité du nouveau bundle d’AC ainsi que chaque CRL avant de remplacer un fichier du cache. Une CRL est refusée si elle ne peut pas être analysée, ou si son émetteur figure dans le bundle et que la signature ne se vérifie pas ; une CRL signée par une AC absente du bundle est publiée avec un avertissement, car NGINX reconstruit la chaîne à partir des intermédiaires présentés par le client. Des données illisibles, invalides ou incompatibles conservent la paire AC/CRL précédente et déclenchent une erreur dans les logs. Renouvelez l’AC et sa CRL ensemble et corrigez rapidement les sources invalides, notamment avant l’expiration d’une CRL. Vider à la fois `MTLS_CRL` et `MTLS_CRL_DATA` supprime volontairement le contrôle de révocation. Supprimer la configuration de l’AC, désactiver mTLS ou supprimer le service retire les fichiers correspondants du cache ; tant que `USE_MTLS` reste à `yes` avec un mode autre que `optional_no_ca`, `ssl_verify_client` s’applique alors contre une AC de remplacement intégrée : chaque client reçoit un 400 en mode `on`, et chaque client présentant un certificat reçoit un 400 en mode `optional`, jusqu’à ce qu’une AC soit de nouveau configurée. Toute suppression effective demande un rechargement.

Le job `client-cert` s’exécute toutes les heures : un bundle d’AC ou un fichier de CRL que vous remplacez sur le disque est donc pris en compte dans l’heure. Il journalise une erreur pour une CRL expirée (tous les clients de l’AC qui l’a signée sont refusés tant qu’aucune CRL à jour n’est publiée) et pour un certificat d’AC expiré. Il journalise un avertissement pour une CRL qui expire dans les 7 jours, pour un certificat d’AC qui expire dans les 30 jours, pour un certificat du bundle qui n’est pas une AC et, dès qu’au moins une CRL est configurée, pour chaque AC du bundle sans CRL. L’avertissement de CRL manquante nomme chaque AC sans CRL : toute AC qui émet un certificat de la chaîne, l’AC racine comprise, doit avoir sa CRL dans l’ensemble, sinon les clients dont la chaîne contient un certificat qu’elle a émis sont refusés. Dans chacun de ces cas, le job publie quand même le matériel : NGINX refuse de toute façon les clients concernés, et conserver un matériel plus ancien ne ferait pas mieux.

### Ce que protège chaque mode

« Atteint votre backend » signifie que la requête est transmise au service une fois que les autres plugins BunkerWeb l’ont eux aussi acceptée.

- **`on` :** chaque requête HTTPS exige un certificat qui se valide par rapport au bundle d’AC. Une requête sans certificat, ou avec un certificat invalide, reçoit un `400` de NGINX et n’atteint jamais votre backend. Le HTTP en clair suit `MTLS_HTTP_POLICY`, sur tous les chemins.
- **`optional` sans `MTLS_URL` :** n’impose rien par lui-même. Un client sans certificat atteint votre backend, en HTTPS comme en HTTP en clair. Un client qui présente un certificat invalide reste refusé (`400`) en HTTPS. Utilisez-le lorsque votre application lit les en-têtes `X-SSL-Client-*` transmis et décide elle-même.
- **`optional` avec `MTLS_URL` :** seuls les chemins qui correspondent à une règle exigent un certificat valide. En HTTPS, un client sans certificat reçoit un `403` sur ces chemins. En HTTP en clair, ces chemins suivent `MTLS_HTTP_POLICY`. Tout autre chemin atteint votre backend avec ou sans certificat, en HTTPS comme en HTTP. Un client qui présente un certificat invalide est refusé (`400`) sur tous les chemins.
- **`optional_no_ca` :** pour le diagnostic, pas pour la protection. NGINX demande un certificat et tolère les erreurs de chaîne de confiance (certificat auto-signé, émetteur inconnu, chaîne non approuvée) : un client qu’aucune AC ne garantit termine donc quand même la négociation TLS. Toute autre erreur de vérification refuse toujours le client avec un `400` en HTTPS, par exemple un certificat expiré ou révoqué. Sans `MTLS_URL`, il n’impose rien. Avec `MTLS_URL`, les chemins correspondants exigent toujours un certificat qui se valide par rapport à un bundle d’AC ; sans bundle d’AC configuré, rien ne peut être validé et ces chemins refusent donc tous les clients.

Avec `SECURITY_MODE=detect`, les refus et redirections que BunkerWeb émet lui-même (règle par chemin, politique du HTTP en clair, règle `MTLS_URL` invalide) sont seulement journalisés et non appliqués, et la requête passe au plugin suivant. Le contrôle au niveau du handshake de `on` et `optional` est effectué par NGINX et n’est pas affecté par le mode de sécurité.

### Requêtes HTTP en clair

Un certificat client ne circule qu’à l’intérieur de TLS : le contrôle du handshake ne peut donc pas protéger le HTTP en clair. Pour un service avec `USE_MTLS` à `yes`, `MTLS_HTTP_POLICY` décide du sort d’une requête HTTP en clair que mTLS aurait dû protéger : tous les chemins lorsque `MTLS_VERIFY_CLIENT` vaut `on`, les chemins de `MTLS_URL` sinon. Avec `optional` ou `optional_no_ca` sans `MTLS_URL`, mTLS ne protège rien en HTTPS, donc rien non plus en HTTP.

- `redirect` (par défaut) : le client reçoit un `301` vers la même URL en HTTPS. Une requête sans en-tête `Host` exploitable est refusée à la place. Elle conserve le port de l’en-tête `Host`, comme la redirection du plugin SSL : lorsque les ports HTTP et HTTPS diffèrent et ne forment pas la paire standard 80/443, le client est redirigé en HTTPS vers le numéro du port HTTP. Utilisez alors `MTLS_HTTP_POLICY=deny`, ou redirigez en amont de BunkerWeb.
- `deny` : la requête est refusée avec le statut de refus (`DENY_HTTP_STATUS`, `403` par défaut).
- `allow` : le HTTP en clair est servi comme avant lorsque `MTLS_VERIFY_CLIENT` vaut `on`. Les chemins de `MTLS_URL` restent refusés.

Une redirection vers HTTPS déjà émise par le plugin SSL (`REDIRECT_HTTP_TO_HTTPS`, ou `AUTO_REDIRECT_HTTP_TO_HTTPS` lorsqu’il détecte HTTPS) passe en premier : la politique ne voit donc que les requêtes HTTP en clair que cette redirection laisse passer. Les défis ACME HTTP-01 restent accessibles : un `GET` ou `HEAD` HTTP en clair sur `/.well-known/acme-challenge/<token>` n’est pas touché lorsqu’un solveur en est propriétaire, c’est-à-dire le solveur local Let’s Encrypt avec le jeton présent, ou `LETS_ENCRYPT_PASSTHROUGH` ou `ACME_PASSTHROUGH` à `yes`. Tout autre chemin sous `/.well-known/acme-challenge/` suit la politique. Réglez `LISTEN_HTTP` sur `no` pour le service afin de fermer complètement le port HTTP en clair.

### Paramètres de configuration

| Paramètre                      | Valeur par défaut | Contexte  | Multiple | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------ | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                     | `no`              | multisite | non      | **Activer le mutual TLS :** active l’authentification par certificat client pour le site courant.                                                                                                                                                                                                                                                                                                                                                                                                 |
| `MTLS_CA_CERTIFICATE_PRIORITY` | `file`            | multisite | non      | **Priorité du bundle d’AC client :** source du bundle d’AC client : `file` (chemin) ou `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                                                                                       |
| `MTLS_CA_CERTIFICATE`          |                   | multisite | non      | **Chemin du bundle d’AC client :** chemin vers le bundle d’AC clients (PEM), lisible par le Scheduler. Requis lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`.                                                                                                                                                                                                                                                                                                                               |
| `MTLS_CA_CERTIFICATE_DATA`     |                   | multisite | non      | **Données du bundle d’AC client :** bundle d’AC client fourni directement en base64 ou PEM (p. ex. via l’interface web).                                                                                                                                                                                                                                                                                                                                                                          |
| `MTLS_VERIFY_CLIENT`           | `on`              | multisite | non      | **Mode de vérification :** `on` exige un certificat valide sur chaque requête HTTPS. `optional` demande un certificat, refuse un certificat invalide et n’impose rien de plus tant que `MTLS_URL` n’est pas défini. `optional_no_ca` demande un certificat sans le valider par rapport à une AC (diagnostic uniquement). Voir « Ce que protège chaque mode ».                                                                                                                                     |
| `MTLS_URL`                     |                   | multisite | oui      | **URL mTLS :** expression régulière sur l’URI normalisée de la requête qui exige un certificat client valide uniquement sur les chemins correspondants, en HTTPS comme en HTTP en clair. Nécessite `MTLS_VERIFY_CLIENT` réglé sur `optional`. Sensible à la casse, ancrez-la sur un répertoire. Laissez vide pour n’avoir aucune règle par chemin : avec `optional` ou `optional_no_ca`, rien n’est imposé, et exiger un certificat sur tout le site demande `MTLS_VERIFY_CLIENT` réglé sur `on`. |
| `MTLS_HTTP_POLICY`             | `redirect`        | multisite | non      | **Politique HTTP :** que faire d’une requête HTTP en clair que mTLS aurait dû protéger : la rediriger vers HTTPS (`redirect`), la refuser (`deny`) ou l’autoriser (`allow`, mode pour tout le site uniquement, les chemins de `MTLS_URL` restent refusés).                                                                                                                                                                                                                                        |
| `MTLS_COUNT_BAD_BEHAVIOR`      | `no`              | multisite | non      | **Compter les échecs mTLS dans Bad Behavior :** laisse Bad Behavior compter le `400` que NGINX renvoie pour un certificat client absent ou invalide, ainsi que les refus émis par mTLS lui-même. Avec `no`, un client sans certificat valide n’est pas banni pour cela seul.                                                                                                                                                                                                                      |
| `MTLS_VERIFY_DEPTH`            | `2`               | multisite | non      | **Profondeur de vérification :** profondeur maximale de chaîne acceptée pour les certificats clients.                                                                                                                                                                                                                                                                                                                                                                                             |
| `MTLS_FORWARD_CLIENT_HEADERS`  | `yes`             | multisite | non      | **Transmettre les en-têtes client :** propage les résultats de vérification (`X-SSL-Client-*` avec statut, DN, émetteur, numéro de série, empreinte, validité). Les en-têtes `X-SSL-*` envoyés par le client sont toujours supprimés en entrée, ces valeurs ne peuvent donc pas être falsifiées.                                                                                                                                                                                                  |
| `MTLS_CRL_PRIORITY`            | `file`            | multisite | non      | **Priorité de la CRL client :** source de la CRL : `file` (chemin) ou `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                                                                                                        |
| `MTLS_CRL`                     |                   | multisite | non      | **Chemin de la CRL client :** chemin optionnel vers une liste de révocation de certificats encodée en PEM, lisible par le Scheduler. Appliqué uniquement si le bundle d’AC est chargé avec succès. NGINX exige une CRL de chaque AC qui émet un certificat de la chaîne, l’AC racine comprise. Une CRL expirée fait refuser les clients de son AC.                                                                                                                                                |
| `MTLS_CRL_DATA`                |                   | multisite | non      | **Données de la CRL client :** liste de révocation fournie directement en base64 ou PEM.                                                                                                                                                                                                                                                                                                                                                                                                          |

!!! info "Une nouvelle CRL ou un changement de CA client supprime les sessions TLS en cache"
    Un changement de CRL ou du bundle de CA client supprime une fois toutes les sessions TLS en cache de l’instance, car le cache de sessions porte le nom d’un hash des bundles de CA et des CRL publiés. Un certificat révoqué ne peut pas reprendre une session antérieure, et les autres clients effectuent un handshake complet.

!!! tip "Écrivez les règles `MTLS_URL` avec soin"
    - La correspondance est sensible à la casse : `^/admin` ne correspond pas à `/Admin`. Commencez le motif par `(?i)` pour ignorer la casse.
    - La regex s’applique à l’URI telle que NGINX la normalise (décodée, segments de points résolus, barres obliques répétées fusionnées), sans la chaîne de requête ; `/a/../admin` et `//admin` sont donc déjà couverts.
    - Ancrez sur un répertoire, pas sur un nom de fichier. Écrivez `^/admin(/|$)` plutôt que `^/admin$`, qui ne correspond pas à `/admin/`. Une règle ancrée sur un nom de fichier comme `^/admin/index\.html$` ne couvre pas non plus `/admin/` : NGINX le sert depuis ce fichier par une redirection interne.
    - Les paramètres de chemin comme `/admin;x=1` et toute autre normalisation que votre backend applique en plus de celle de NGINX (par exemple `..;/` ou les barres obliques inverses) sont à couvrir vous-même dans la regex. BunkerWeb compare l’URI que voit NGINX.
    - Une regex invalide échoue en mode fermé : toute requête qu’aucune règle précédente n’a retenue est refusée (`403`) tant que vous ne la corrigez pas. BunkerWeb journalise une erreur qui nomme le service et le motif au démarrage et après chaque rechargement.

!!! tip "Configurez une fois, distribué partout"
    Les bundles d’AC et les listes de révocation n’ont pas besoin d’être montés dans les conteneurs BunkerWeb. Fournissez-les uniquement au Scheduler, sous forme de chemin de fichier ou de données en ligne ; le Scheduler les valide, les met en cache et les distribue à chaque instance. Les mises à jour sont prises en compte et redistribuées automatiquement lors de la prochaine exécution du job.

!!! warning "Bundle d’AC obligatoire en mode strict"
    Lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`, le Scheduler doit pouvoir valider et mettre en cache un bundle d’AC client. Tant qu’aucun bundle n’a été validé et distribué, chaque instance bascule sur une AC de remplacement à laquelle aucun client ne peut se rattacher. Avec `on`, tout client est donc rejeté, là où le service tournait auparavant sans aucune vérification client. Avec `optional`, un client qui ne présente pas de certificat passe quand même, puisque c’est le sens de ce mode ; l’application pour ces requêtes vient de `MTLS_URL` lorsqu’il est défini, et rien ne les contrôle lorsqu’il est laissé vide. Un client qui présente un certificat est rejeté, car rien ne permet de le valider. Réservez `optional_no_ca` au diagnostic, car ce mode affaiblit l’authentification. Après un redémarrage du Scheduler avec un `/var/cache/bunkerweb` non persistant, cet état persiste jusqu’à ce que la première exécution du job se termine et redistribue le bundle d’AC ; utilisez donc un volume de cache persistant lorsqu’une politique d’application stricte est requise.

!!! warning "mTLS s’exécute avant la liste blanche"
    mTLS est évalué juste après le plugin SSL et avant la liste blanche. Un client qui correspond à `WHITELIST_IP`, `WHITELIST_URI`, `WHITELIST_USER_AGENT` (ou à une entrée par défaut de `WHITELIST_RDNS` ou `WHITELIST_ASN`) a toujours besoin d’un certificat là où mTLS en exige un. Avant la 1.6.19, la liste blanche contournait le contrôle de `MTLS_URL`. Pour rétablir cette précédence, réglez `PLUGINS_ORDER_ACCESS` sur `ssl whitelist mtls`. Si vous définissez vous-même `PLUGINS_ORDER_ACCESS`, globalement ou par service, votre valeur est conservée : si elle ne nomme pas `mtls`, mTLS s’exécute toujours après la liste blanche dans ce cas. Placez `mtls` juste après `ssl` dans cette valeur.

!!! info "Bad Behavior ne compte pas les échecs de certificat par défaut"
    Avec `MTLS_COUNT_BAD_BEHAVIOR` à `no`, le plugin Bad Behavior ne compte ni le `400` que NGINX renvoie lorsque le certificat client est absent ou invalide, ni les refus émis par mTLS lui-même (règle par chemin, politique du HTTP en clair, regex `MTLS_URL` invalide) : un client sans certificat valide n’est donc pas banni pour cela seul. Tout autre `400` sur le même service compte toujours. Réglez-le sur `yes` pour les compter de nouveau. La réponse à un certificat absent ou invalide est désormais la page d’erreur `400` de BunkerWeb lorsque le plugin Errors gère le `400` (cas par défaut, sauf si `ERRORS` définit une page personnalisée pour `400`) ; sinon elle reste la page standard de NGINX.

!!! info "Services stream"
    Sur un service stream, seul le contrôle au niveau du handshake s’applique : seul `MTLS_VERIFY_CLIENT` réglé sur `on` impose donc quelque chose. `optional` et `optional_no_ca` laissent passer un client sans certificat, et `MTLS_URL` et `MTLS_HTTP_POLICY` ne concernent que HTTP.

!!! info "Les en-têtes `X-SSL-Client-*` n’atteignent que les upstreams reverse proxy et gRPC"
    BunkerWeb transmet les résultats de vérification aux services configurés avec les plugins reverse proxy ou gRPC. PHP/FastCGI et les locations personnalisées ne les reçoivent pas : transmettez vous-même les variables NGINX `$ssl_client_*` dans votre configuration.

!!! info "Certificat approuvé vs. vérification"
    BunkerWeb réutilise le même bundle d’AC pour vérifier les clients et bâtir la chaîne de confiance, garantissant une cohérence OCSP/CRL et durant le handshake.

!!! info "Les en-têtes `X-SSL-*` entrants sont toujours supprimés"
    BunkerWeb supprime tout en-tête de requête `X-SSL-*` envoyé par le client avant que la requête n’atteigne votre application : sur chaque site, que mTLS soit activé ou non, et aussi bien en HTTP/1.1, HTTP/2 qu’en HTTP/3. Seules les valeurs que BunkerWeb dérive du handshake TLS vérifié sont transmises, et uniquement lorsque `MTLS_FORWARD_CLIENT_HEADERS` vaut `yes` ; un client ne peut donc pas falsifier `X-SSL-Client-Verify: SUCCESS`.

    Si BunkerWeb est placé derrière un autre proxy qui termine le mTLS et injecte lui-même ces en-têtes, capturez la valeur avant la suppression puis republiez-la. Ajoutez une configuration personnalisée `server-http` :

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    puis transmettez-la avec `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"`. `REVERSE_PROXY_HEADERS` seul ne suffit pas : `$http_x_ssl_client_verify` est déjà vide au moment où `proxy_set_header` l’évalue, alors que `set` s’exécute en phase server-rewrite, avant la suppression.

!!! warning "Le mTLS par chemin nécessite le mode optionnel"
    La directive `ssl_verify_client` de NGINX n’est valable qu’au niveau `server` : elle ne peut pas être placée dans un bloc `location`. Pour exiger un certificat sur certains chemins seulement, réglez `MTLS_VERIFY_CLIENT` sur `optional` afin que le handshake aboutisse pour tous les chemins, puis listez les chemins protégés dans `MTLS_URL_n`. BunkerWeb applique alors l’exigence de certificat par requête, en Lua, sur les URL correspondantes. Utilisez `optional` pour une vraie protection : `optional_no_ca` ignore la validation de l’AC au handshake, et le contrôle par chemin exige toujours un certificat qui se valide par rapport à un bundle d’AC ; sans bundle d’AC configuré, les chemins correspondants refusent tous les clients. Si vous laissez `MTLS_VERIFY_CLIENT` à `on` tout en renseignant `MTLS_URL_n`, NGINX rejette les clients sans certificat dès le handshake, avant que la logique par chemin ne s’applique : l’exigence reste alors valable pour tout le site (BunkerWeb émet alors un avertissement au démarrage).

!!! info "Invites de certificat des navigateurs en mode optionnel"
    Le handshake TLS a lieu avant que NGINX ne connaisse l’URL demandée : en mode `optional`, NGINX envoie donc toujours un `CertificateRequest` à chaque connexion. L’exigence devient bien par chemin, mais pas l’invitation au niveau du handshake : les navigateurs peuvent encore proposer un certificat sur les chemins non protégés (comportement variable selon le navigateur). Sur ces chemins, BunkerWeb autorise la requête, qu’un certificat soit présenté ou non.

### Exemples de configuration

=== "Contrôle d’accès strict"

    Exigez des certificats clients valides émis par votre AC privée et transmettez les informations de vérification au backend :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Authentification client optionnelle"

    Autorisez les utilisateurs anonymes mais transmettez les détails du certificat lorsqu’un client en présente un. Cela n’impose rien par soi-même : votre application décide à partir des en-têtes transmis :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnostic sans AC"

    Autorisez les connexions à aboutir même si un certificat ne peut pas être rattaché à un bundle d’AC de confiance. Utile uniquement pour le dépannage :

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

=== "mTLS par chemin (par ex. `/login` uniquement)"

    Exigez des certificats clients sur certains chemins seulement, tout en laissant le reste du site ouvert. La vérification s’exécute en mode `optional` pour que le handshake aboutisse sur les chemins non authentifiés ; BunkerWeb applique ensuite l’exigence de certificat par requête sur les URL correspondant à `MTLS_URL_n` (une regex par emplacement) :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_URL_1: "^/login(/|$)"
    MTLS_URL_2: "^/admin(/|$)"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Requête               | Certificat        | Résultat                                                 |
    | --------------------- | ----------------- | -------------------------------------------------------- |
    | `GET /`               | aucun             | Autorisé (chemin hors mTLS)                              |
    | `GET /login`          | aucun             | Refusé (`403`)                                           |
    | `GET /login`          | valide            | Autorisé, `X-SSL-Client-*` transmis                      |
    | n’importe quel chemin | invalide / expiré | Refusé par NGINX (`400`)                                 |
    | `GET /login` (HTTP)   | aucun             | Redirigé vers HTTPS (`MTLS_HTTP_POLICY` vaut `redirect`) |
