Le plugin Mutual TLS (mTLS) protège vos applications sensibles en exigeant que les clients présentent des certificats délivrés par des autorités que vous maîtrisez. Une fois activé, BunkerWeb authentifie les appelants avant que leurs requêtes n’atteignent vos services, ce qui sécurise vos outils internes et intégrations partenaires.

BunkerWeb évalue chaque poignée de main TLS en fonction du bundle d’AC et de la politique que vous définissez. Les clients qui ne répondent pas aux règles sont bloqués, tandis que les connexions conformes peuvent transmettre les détails du certificat aux applications amont pour une autorisation affinée.

**Fonctionnement :**

1. Le plugin surveille les échanges HTTPS du site sélectionné.
2. Pendant l’échange TLS, BunkerWeb inspecte le certificat client et vérifie sa chaîne par rapport à votre magasin de confiance.
3. Le mode de vérification détermine si les clients non authentifiés sont rejetés, acceptés avec tolérance ou autorisés pour des diagnostics.
4. (Optionnel) BunkerWeb expose le résultat via les en-têtes `X-SSL-Client-*` afin que vos applications puissent appliquer leur propre logique d’accès.

!!! success "Avantages clés"

      1. **Contrôle renforcé :** limitez l’accès aux machines et utilisateurs authentifiés.
      2. **Politiques souples :** combinez modes stricts et optionnels pour accompagner vos workflows.
      3. **Visibilité applicative :** transférez empreintes et identités de certificats pour l’audit.
      4. **Défense en profondeur :** associez mTLS aux autres plugins BunkerWeb pour multiplier les protections.

### Mise en œuvre

Suivez ces étapes pour déployer le mutual TLS sereinement :

1. **Activer la fonctionnalité :** positionnez `USE_MTLS` à `yes` sur les sites qui nécessitent l’authentification par certificat.
2. **Fournir le bundle d’AC :** stockez vos autorités de confiance dans un fichier PEM et renseignez `MTLS_CA_CERTIFICATE` avec son chemin absolu.
3. **Choisir le mode de vérification :** sélectionnez `on` pour rendre les certificats obligatoires, `optional` pour offrir un repli ou `optional_no_ca` pour un diagnostic temporaire.
4. **Ajuster la profondeur de chaîne :** adaptez `MTLS_VERIFY_DEPTH` si votre organisation utilise plusieurs intermédiaires.
5. **Transmettre le résultat (optionnel) :** laissez `MTLS_FORWARD_CLIENT_HEADERS` à `yes` si vos services amont doivent inspecter le certificat présenté.
6. **Maintenir la révocation :** si vous publiez une CRL, renseignez `MTLS_CRL` pour que BunkerWeb refuse les certificats révoqués.

### Paramètres de configuration

| Paramètre                     | Valeur par défaut | Contexte | Multiple | Description                                                                                                                                             |
| ----------------------------- | ----------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                    | `no`              | multisite | non      | **Activer le mutual TLS :** active l’authentification par certificat client pour le site courant.                                                       |
| `MTLS_CA_CERTIFICATE`         |                   | multisite | non      | **Bundle d’AC client :** chemin absolu vers le bundle d’AC clients (PEM). Requis lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`; doit être lisible. |
| `MTLS_VERIFY_CLIENT`          | `on`              | multisite | non      | **Mode de vérification :** choisissez si les certificats sont requis (`on`), optionnels (`optional`) ou acceptés sans validation d’AC (`optional_no_ca`). |
| `MTLS_URL`                    |                   | multisite | oui      | **URL mTLS :** expression régulière comparée à l’URI de la requête pour exiger un certificat client valide uniquement sur les chemins correspondants (HTTP uniquement). Nécessite `MTLS_VERIFY_CLIENT` réglé sur `optional` ou `optional_no_ca`. Laissez vide pour appliquer le mTLS à tout le site. |
| `MTLS_VERIFY_DEPTH`           | `2`               | multisite | non      | **Profondeur de vérification :** profondeur maximale de chaîne acceptée pour les certificats clients.                                                   |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`             | multisite | non      | **Transmettre les en-têtes client :** propage les résultats de vérification (`X-SSL-Client-*` avec statut, DN, émetteur, numéro de série, empreinte, validité). Les en-têtes `X-SSL-*` envoyés par le client sont toujours supprimés en entrée, ces valeurs ne peuvent donc pas être falsifiées. |
| `MTLS_CRL`                    |                   | multisite | non      | **Chemin de la CRL client :** chemin optionnel vers une liste de révocation de certificats encodée en PEM. Appliqué dès que la vérification des certificats clients est active ; jamais ignoré silencieusement. |

!!! tip "Maintenez les certificats à jour"
    Stockez bundles d’AC et listes de révocation dans un volume monté accessible par l’**instance BunkerWeb** : NGINX ouvre lui-même `MTLS_CA_CERTIFICATE` et `MTLS_CRL`, et aucun job ne les distribue. Dans un déploiement séparé, les monter uniquement là où tourne le Scheduler ne suffit donc pas.

!!! warning "Bundle d’AC obligatoire en mode strict"
    Lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`, le bundle d’AC est obligatoire. Si `MTLS_CA_CERTIFICATE` est vide, BunkerWeb refuse le handshake TLS pour ce site (`ssl_reject_handshake`) au lieu de le servir sans vérifier les certificats clients ; le HTTP en clair continue de répondre, le renouvellement ACME `http-01` n’est donc pas affecté. Si le chemin est renseigné mais que le fichier est absent ou illisible sur l’instance, NGINX refuse de charger la configuration : lors d’un rechargement la précédente reste active, à froid l’instance ne démarre pas. Il en va de même pour `MTLS_CRL` : une liste de révocation configurée est appliquée, jamais ignorée silencieusement. Réservez `optional_no_ca` au diagnostic, car ce mode affaiblit l’authentification. Un handshake refusé **est** bien journalisé, sous la forme `handshake rejected`, dans le log d’erreurs NGINX de l’instance BunkerWeb (`ERROR_LOG`, `/var/log/bunkerweb/error.log` par défaut) — pas dans celui du Scheduler. Il est écrit au niveau `info` alors que `LOG_LEVEL` vaut `notice` par défaut : passez `LOG_LEVEL=info` pour le voir.

!!! info "Certificat approuvé vs. vérification"
    `ssl_client_certificate` et `ssl_trusted_certificate` sont tous deux des magasins de confiance pour la vérification des certificats clients ; la seule différence est que le premier annonce ses AC au client dans le CertificateRequest et le second non. BunkerWeb pointait les deux sur le même fichier : le second n’apportait donc rien et a été supprimé. C’est aussi le magasin utilisé pour vérifier les réponses OCSP lorsque `ssl_stapling` est activé — ce que BunkerWeb n’active jamais : dirigé vers le bundle d’AC *clients*, il restait inerte, mais c’était un piège et il a disparu.

!!! info "Les en-têtes `X-SSL-*` entrants sont toujours supprimés"
    BunkerWeb supprime tout en-tête de requête `X-SSL-*` envoyé par le client avant que la requête n’atteigne votre application : sur chaque site, que mTLS soit activé ou non, et aussi bien en HTTP/1.1, HTTP/2 qu’en HTTP/3. Seules les valeurs que BunkerWeb dérive du handshake TLS vérifié sont transmises, et uniquement lorsque `MTLS_FORWARD_CLIENT_HEADERS` vaut `yes` ; un client ne peut donc pas falsifier `X-SSL-Client-Verify: SUCCESS`. Votre application doit tout de même vérifier que `X-SSL-Client-Verify` vaut `SUCCESS` : avec `MTLS_VERIFY_CLIENT=optional`, une requête anonyme est transmise elle aussi, avec `X-SSL-Client-Verify: NONE` et un `X-SSL-Client-DN` vide ; traiter le DN comme une preuve d’authentification reviendrait à l’accepter.

    Si BunkerWeb est placé derrière un autre proxy qui termine le mTLS et injecte lui-même ces en-têtes, capturez la valeur avant la suppression puis republiez-la. Ajoutez une configuration personnalisée `server-http` :

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    puis transmettez-la avec `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"`. `REVERSE_PROXY_HEADERS` seul ne suffit pas : `$http_x_ssl_client_verify` est déjà vide au moment où `proxy_set_header` l’évalue, alors que `set` s’exécute en phase server-rewrite, avant la suppression.

!!! warning "Le mTLS par chemin nécessite le mode optionnel"
    La directive `ssl_verify_client` de NGINX n’est valable qu’au niveau `server` — elle ne peut pas être placée dans un bloc `location`. Pour exiger un certificat sur certains chemins seulement, réglez `MTLS_VERIFY_CLIENT` sur `optional` afin que le handshake aboutisse pour tous les chemins, puis listez les chemins protégés dans `MTLS_URL_n`. BunkerWeb applique alors l’exigence de certificat par requête, en Lua, sur les URL correspondantes. Utilisez `optional` pour une vraie protection : `optional_no_ca` ignore la validation de la chaîne d’AC, donc une URL correspondante accepterait n’importe quel certificat présenté et n’offre aucune protection réelle. Si vous laissez `MTLS_VERIFY_CLIENT` à `on` tout en renseignant `MTLS_URL_n`, NGINX rejette les clients sans certificat dès le handshake, avant que la logique par chemin ne s’applique : l’exigence reste alors valable pour tout le site (BunkerWeb émet alors un avertissement au démarrage). Si une valeur `MTLS_URL_n` n’est pas une regex valide, BunkerWeb échoue en mode fermé — les requêtes sont refusées (`403`) et le motif fautif est journalisé — plutôt que de laisser passer le chemin silencieusement ; corrigez le motif pour rétablir le service.

!!! info "Invites de certificat des navigateurs en mode optionnel"
    Le handshake TLS a lieu avant que NGINX ne connaisse l’URL demandée : en mode `optional`, NGINX envoie donc toujours un `CertificateRequest` à chaque connexion. L’exigence devient bien par chemin, mais pas l’invitation au niveau du handshake — les navigateurs peuvent encore proposer un certificat sur les chemins non protégés (comportement variable selon le navigateur). Sur ces chemins, BunkerWeb autorise la requête, qu’un certificat soit présenté ou non.

### Exemples de configuration

=== "Contrôle d’accès strict"

    Exigez des certificats clients valides émis par votre AC privée et transmettez les informations de vérification au backend :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Authentification client optionnelle"

    Autorisez les utilisateurs anonymes mais transmettez les détails du certificat lorsqu’un client en présente un :

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnostic sans AC"

    Autorisez les connexions à aboutir même si un certificat ne peut pas être rattaché à un bundle d’AC de confiance. Utile uniquement pour le dépannage :

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
    MTLS_URL_1: "^/login"
    MTLS_URL_2: "^/admin"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Requête          | Certificat          | Résultat                                |
    | ---------------- | ------------------- | --------------------------------------- |
    | `GET /`          | aucun               | Autorisé (chemin hors mTLS)             |
    | `GET /login`     | aucun               | Refusé (`403`)                          |
    | `GET /login`     | valide              | Autorisé, `X-SSL-Client-*` transmis     |
    | `GET /login`     | invalide / expiré   | Refusé (`403`)                          |
