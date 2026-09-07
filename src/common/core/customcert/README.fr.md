Le plugin Certificat SSL personnalisé permet d’utiliser vos propres certificats SSL/TLS avec BunkerWeb, au lieu de ceux générés automatiquement. Utile si vous possédez déjà des certificats d’une AC de confiance, avez des besoins spécifiques ou centralisez la gestion des certificats.

Comment ça marche :

1. Vous fournissez le certificat et la clé privée (chemins de fichiers ou données en base64/PEM).
2. BunkerWeb valide le format et l’utilisabilité des fichiers.
3. Lors d’une connexion sécurisée, BunkerWeb sert votre certificat personnalisé.
4. La validité est surveillée et des alertes sont émises avant expiration.
5. Vous gardez le contrôle total sur le cycle de vie des certificats.

!!! info "Surveillance automatique"
    Avec le paramètre `USE_CUSTOM_SSL` défini à `yes`, BunkerWeb surveille le certificat `CUSTOM_SSL_CERT`, détecte les changements et recharge NGINX si nécessaire.

### Comment l’utiliser

1. Activer : mettez le paramètre `USE_CUSTOM_SSL` à `yes`.
2. Méthode : fichiers vs données, priorité via `CUSTOM_SSL_CERT_PRIORITY`.
3. Fichiers : fournissez les chemins du certificat et de la clé privée.
4. Données : fournissez les chaînes base64 ou PEM en clair.
5. Laisser BunkerWeb faire le reste : une fois configuré, vos certificats personnalisés sont utilisés automatiquement pour les connexions HTTPS.

!!! tip "Mode stream"
    En mode stream, configurez `LISTEN_STREAM_PORT_SSL` pour le port SSL/TLS.

### Paramètres

| Paramètre                  | Défaut | Contexte  | Multiple | Description                                                   |
| -------------------------- | ------ | --------- | -------- | ------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`   | multisite | non      | Activer l’usage d’un certificat personnalisé.                 |
| `CUSTOM_SSL_CERT_PRIORITY` | `file` | multisite | non      | Priorité des sources : `file` (fichiers) ou `data` (données). |
| `CUSTOM_SSL_CERT`          |        | multisite | non      | Chemin complet vers le certificat (ou bundle).                |
| `CUSTOM_SSL_KEY`           |        | multisite | non      | Chemin complet vers la clé privée.                            |
| `CUSTOM_SSL_CERT_DATA`     |        | multisite | non      | Données du certificat (base64 ou PEM en clair).               |
| `CUSTOM_SSL_KEY_DATA`      |        | multisite | non      | Données de la clé privée (base64 ou PEM en clair).            |

### Certificat du serveur par défaut

Le **serveur par défaut** est le bloc qui répond aux requêtes ne correspondant à aucun service configuré : un SNI inconnu, une connexion à une adresse IP brute, un `Host` que personne ne sert. Le seul certificat qu'il pouvait présenter était l'auto-signé interne généré par BunkerWeb au démarrage — c'est pourquoi un navigateur atteignant un nom d'hôte inconnu sur votre instance voit un avertissement de non-correspondance de nom.

Ces quatre réglages globaux le remplacent. Laissez-les vides pour conserver le certificat interne. Ses autres réglages — TLS, en-têtes, pages d'erreur — se modifient sur le service réservé `default-server`, voir [Configuration du serveur par défaut](#miscellaneous).

| Paramètre                      | Défaut | Contexte | Multiple | Description                                                                                                                          |
| :------------------------------ | :----- | :------- | :------- | :-------------------------------------------------------------------------------------------------------------------------------------- |
| `DEFAULT_SERVER_SSL_CERT`      |        | global   | non      | Chemin complet vers le certificat (ou bundle) servi pour les requêtes ne correspondant à aucun service configuré. Servi uniquement là où existe un bloc de serveur par défaut : mode multisite (`MULTISITE=yes`), ou `DISABLE_DEFAULT_SERVER=yes` en mono-site. |
| `DEFAULT_SERVER_SSL_KEY`       |        | global   | non      | Chemin complet vers la clé privée correspondante.                                                                                    |
| `DEFAULT_SERVER_SSL_CERT_DATA` |        | global   | non      | Le même certificat en base64 ou PEM en clair. Utilisé uniquement quand le réglage de chemin est vide. Servi uniquement là où existe un bloc de serveur par défaut : mode multisite (`MULTISITE=yes`), ou `DISABLE_DEFAULT_SERVER=yes` en mono-site. |
| `DEFAULT_SERVER_SSL_KEY_DATA`  |        | global   | non      | La même clé privée en base64 ou PEM en clair. Utilisée uniquement quand le réglage de chemin est vide.                              |

La surcharge est consultée **en dernier**, et uniquement à l'intérieur du serveur par défaut : un service qui résout son propre certificat — via l'inventaire des certificats, `USE_CUSTOM_SSL`, Let's Encrypt ou le fournisseur auto-signé — le conserve toujours.

!!! warning "Un certificat couvrant l'un de vos services est refusé"
    Le serveur par défaut répond à *n'importe quel* nom d'hôte. Si son certificat couvrait aussi `www.example.com`, un client pourrait ouvrir une connexion avec un SNI inconnu, recevoir ce certificat, puis réutiliser la même connexion pour `Host: www.example.com` — un certificat que ce service n'a jamais autorisé, désormais utilisable pour lui (coalescence de connexions HTTP/2). Le job `custom-cert` refuse donc un certificat dont les SAN ou le Common Name couvrent un nom d'hôte d'un service configuré, jokers inclus, et journalise le nom d'hôte pour lequel il l'a refusé. Utilisez un certificat ne couvrant aucun nom d'hôte de service configuré, ou attachez-le au service via `USE_CUSTOM_SSL` à la place.

!!! info "Un refus ne retire jamais ce qui est déjà servi"
    Un matériel invalide, une paire non concordante et un nom d'hôte couvert font tous échouer le job bruyamment et laissent en place le certificat précédemment servi, plutôt que de laisser le serveur par défaut sans rien. L'expiration ne fait qu'avertir, pour la même raison. Vider les deux réglages retire la surcharge et restaure le certificat interne.

!!! tip "Sans effet quand le SNI strict est actif"
    Avec `DISABLE_DEFAULT_SERVER_STRICT_SNI` à `yes`, un SNI inconnu est fermé pendant la négociation TLS, avant même le choix d'un certificat — la surcharge n'est donc jamais atteinte. Laissez-le désactivé si vous voulez que les noms d'hôte inconnus reçoivent votre propre certificat.

!!! warning "Sécurité"
    Protégez la clé privée (droits adaptés, lisible par le scheduler BunkerWeb uniquement).

!!! tip "Format"
    Les certificats doivent être au format PEM. Convertissez si nécessaire.

!!! info "Chaînes de certification"
    Si une chaîne intermédiaire est nécessaire, fournissez le bundle complet dans l’ordre (certificat puis intermédiaires).

### Exemples

=== "Fichiers"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "Données base64"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```

=== "PEM en clair"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
    -----BEGIN CERTIFICATE-----
    MIIDdzCCAl+gAwIBAgIUJH...certificate content...AAAA
    -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
    -----BEGIN PRIVATE KEY-----
    MIIEvQIBADAN...key content...AAAA
    -----END PRIVATE KEY-----
    ```

=== "Fallback"

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR..."
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV..."
    ```
