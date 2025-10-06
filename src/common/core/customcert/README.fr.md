Le plugin Certificat SSL personnalisé permet d’utiliser vos propres certificats SSL/TLS avec BunkerWeb, au lieu de ceux générés automatiquement. Utile si vous possédez déjà des certificats d’une AC de confiance, avez des besoins spécifiques ou centralisez la gestion des certificats.

Comment ça marche :

1. Vous fournissez le certificat et la clé privée (chemins de fichiers ou données en base64/PEM).
2. BunkerWeb valide le format et l’utilisabilité des fichiers.
3. Lors d’une connexion sécurisée, BunkerWeb sert votre certificat personnalisé.
4. La validité est surveillée et des alertes sont émises avant expiration.
5. Vous gardez le contrôle total sur le cycle de vie des certificats.

!!! info "Surveillance automatique"
    Avec `USE_CUSTOM_SSL: yes`, BunkerWeb surveille le certificat `CUSTOM_SSL_CERT`, détecte les changements et recharge NGINX si nécessaire.

### Comment l’utiliser

1. Activer : `USE_CUSTOM_SSL: yes`.
2. Méthode : fichiers vs données, priorité via `CUSTOM_SSL_CERT_PRIORITY`.
3. Fichiers : fournissez les chemins du certificat et de la clé privée.
4. Données : fournissez les chaînes base64 ou PEM en clair.

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
