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
2. **Fournir le bundle d’AC :** renseignez `MTLS_CA_CERTIFICATE` avec le chemin d’un fichier PEM lisible par le Scheduler, ou fournissez le bundle directement sous forme de données base64/PEM via `MTLS_CA_CERTIFICATE_DATA`. Le Scheduler valide, met en cache et distribue le bundle à chaque instance, sans montage nécessaire par instance.
3. **Choisir le mode de vérification :** sélectionnez `on` pour rendre les certificats obligatoires, `optional` pour offrir un repli ou `optional_no_ca` pour un diagnostic temporaire.
4. **Ajuster la profondeur de chaîne :** adaptez `MTLS_VERIFY_DEPTH` si votre organisation utilise plusieurs intermédiaires.
5. **Transmettre le résultat (optionnel) :** laissez `MTLS_FORWARD_CLIENT_HEADERS` à `yes` si vos services amont doivent inspecter le certificat présenté.
6. **Maintenir la révocation :** si vous publiez une CRL, renseignez `MTLS_CRL` (ou `MTLS_CRL_DATA`) pour que BunkerWeb refuse les certificats révoqués.

### Paramètres de configuration

| Paramètre                        | Valeur par défaut | Contexte  | Multiple | Description                                                                                                                                             |
| ----------------------------------- | ------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                         | `no`               | multisite | non      | **Activer le mutual TLS :** active l’authentification par certificat client pour le site courant.                                                       |
| `MTLS_CA_CERTIFICATE_PRIORITY`     | `file`             | multisite | non      | **Priorité du bundle d’AC client :** source du bundle d’AC client : `file` (chemin) ou `data` (base64/PEM).                                             |
| `MTLS_CA_CERTIFICATE`              |                    | multisite | non      | **Chemin du bundle d’AC client :** chemin vers le bundle d’AC clients (PEM), lisible par le Scheduler. Requis lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`. |
| `MTLS_CA_CERTIFICATE_DATA`         |                    | multisite | non      | **Données du bundle d’AC client :** bundle d’AC client fourni directement en base64 ou PEM (p. ex. via l’interface web).                                    |
| `MTLS_VERIFY_CLIENT`               | `on`               | multisite | non      | **Mode de vérification :** choisissez si les certificats sont requis (`on`), optionnels (`optional`) ou acceptés sans validation d’AC (`optional_no_ca`). |
| `MTLS_URL`                         |                    | multisite | oui      | **URL mTLS :** expression régulière comparée à l’URI de la requête pour exiger un certificat client valide uniquement sur les chemins correspondants (HTTP uniquement). Nécessite `MTLS_VERIFY_CLIENT` réglé sur `optional` ou `optional_no_ca`. Laissez vide pour appliquer le mTLS à tout le site. |
| `MTLS_VERIFY_DEPTH`                | `2`                | multisite | non      | **Profondeur de vérification :** profondeur maximale de chaîne acceptée pour les certificats clients.                                                   |
| `MTLS_FORWARD_CLIENT_HEADERS`      | `yes`              | multisite | non      | **Transmettre les en-têtes client :** propage les résultats de vérification (`X-SSL-Client-*` avec statut, DN, émetteur, numéro de série, empreinte, validité). |
| `MTLS_CRL_PRIORITY`                | `file`             | multisite | non      | **Priorité de la CRL client :** source de la CRL : `file` (chemin) ou `data` (base64/PEM).                                                                |
| `MTLS_CRL`                         |                    | multisite | non      | **Chemin de la CRL client :** chemin optionnel vers une liste de révocation de certificats encodée en PEM, lisible par le Scheduler. Appliqué uniquement si le bundle d’AC est chargé avec succès. NGINX exige que le fichier de CRL contienne une CRL pour chaque AC de la chaîne de vérification. |
| `MTLS_CRL_DATA`                    |                    | multisite | non      | **Données de la CRL client :** liste de révocation fournie directement en base64 ou PEM.                                                                |

!!! tip "Configurez une fois, distribué partout"
    Les bundles d’AC et les listes de révocation n’ont pas besoin d’être montés dans les conteneurs BunkerWeb. Fournissez-les uniquement au Scheduler, sous forme de chemin de fichier ou de données en ligne ; le Scheduler les valide, les met en cache et les distribue à chaque instance. Les mises à jour sont prises en compte et redistribuées automatiquement lors de la prochaine exécution du job.

!!! warning "Bundle d’AC obligatoire en mode strict"
    Lorsque `MTLS_VERIFY_CLIENT` vaut `on` ou `optional`, le Scheduler doit pouvoir valider et mettre en cache un bundle d’AC client. En l’absence de bundle valide, BunkerWeb ignore les directives mTLS sur chaque instance afin que le service ne tourne pas avec une référence de certificat invalide ou manquante. Réservez `optional_no_ca` au diagnostic, car ce mode affaiblit l’authentification. Après un redémarrage du Scheduler avec un `/var/cache/bunkerweb` non persistant, le mTLS reste désactivé jusqu’à ce que la première exécution du job se termine et redistribue le bundle d’AC ; utilisez donc un volume de cache persistant lorsqu’une politique d’application stricte est requise.

!!! info "Certificat approuvé vs. vérification"
    BunkerWeb réutilise le même bundle d’AC pour vérifier les clients et bâtir la chaîne de confiance, garantissant une cohérence OCSP/CRL et durant le handshake.

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
