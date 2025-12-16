Le plugin SSL fournit un chiffrement SSL/TLS robuste pour vos sites protégés par BunkerWeb. Il permet des connexions HTTPS sécurisées en configurant protocoles, suites cryptographiques et paramètres associés.

Comment ça marche :

1. Lors d’une connexion HTTPS, BunkerWeb gère la négociation SSL/TLS selon vos réglages.
2. Le plugin impose des protocoles modernes et des suites fortes, et désactive les options vulnérables.
3. Des paramètres de session optimisés améliorent les performances sans sacrifier la sécurité.
4. La présentation des certificats suit les bonnes pratiques pour compatibilité et sécurité.

### Comment l’utiliser

1. Protocoles : choisissez les versions via `SSL_PROTOCOLS`.
2. Suites : sélectionnez un niveau via `SSL_CIPHERS_LEVEL` ou des suites personnalisées via `SSL_CIPHERS_CUSTOM`.
3. Redirections : configurez la redirection HTTP→HTTPS avec `AUTO_REDIRECT_HTTP_TO_HTTPS` et/ou `REDIRECT_HTTP_TO_HTTPS`.

### Paramètres

| Paramètre                     | Défaut            | Contexte  | Multiple | Description                                                                                    |
| ----------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | non      | Rediriger tout HTTP vers HTTPS.                                                                |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | non      | Redirection auto si HTTPS détecté.                                                             |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | non      | Protocoles SSL/TLS supportés (séparés par des espaces).                                        |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | non      | Niveau de sécurité des suites (`modern`, `intermediate`, `old`).                               |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | non      | Suites personnalisées (liste séparée par `:`) qui remplacent le niveau.                        |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | multisite | non      | Taille du cache de session SSL (ex. `10m`, `512k`). Définir à `off` ou `none` pour désactiver. |

!!! tip "Test SSL Labs"
    Testez votre configuration via [Qualys SSL Labs](https://www.ssllabs.com/ssltest/). Une configuration BunkerWeb bien réglée atteint généralement A+.

!!! warning "Protocoles anciens"
    SSLv3, TLSv1.0 et TLSv1.1 sont désactivés par défaut (vulnérabilités connues). Activez‑les uniquement si nécessaire pour clients hérités.

### Exemples

=== "Sécurité moderne (défaut)"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Sécurité maximale"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Compatibilité héritée"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Suites personnalisées"

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```
