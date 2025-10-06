Le plugin Certificat auto‑signé génère et gère automatiquement des certificats SSL/TLS directement dans BunkerWeb, pour activer HTTPS sans autorité de certification externe. Idéal en développement, réseaux internes ou déploiements rapides d’HTTPS.

Comment ça marche :

1. Une fois activé, BunkerWeb génère un certificat auto‑signé pour vos domaines configurés.
2. Le certificat inclut tous les noms de serveurs définis, assurant une validation correcte.
3. Les certificats sont stockés de façon sécurisée et chiffrent tout le trafic HTTPS.
4. Le renouvellement est automatique avant expiration.

!!! warning "Avertissements navigateurs"
    Les navigateurs afficheront des alertes de sécurité car un certificat auto‑signé n’est pas émis par une AC de confiance. En production, préférez [Let’s Encrypt](#lets-encrypt).

### Comment l’utiliser

1. Activer : `GENERATE_SELF_SIGNED_SSL: yes`.
2. Algorithme : choisissez via `SELF_SIGNED_SSL_ALGORITHM`.
3. Validité : durée en jours via `SELF_SIGNED_SSL_EXPIRY`.
4. Sujet : champ subject via `SELF_SIGNED_SSL_SUBJ`.

!!! tip "Mode stream"
    En mode stream, configurez `LISTEN_STREAM_PORT_SSL` pour définir le port d’écoute SSL/TLS.

### Paramètres

| Paramètre                   | Défaut                 | Contexte  | Multiple | Description                                                           |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | non      | Activer la génération automatique de certificats auto‑signés.         |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | non      | Algorithme : `ec-prime256v1`, `ec-secp384r1`, `rsa-2048`, `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | non      | Validité (jours).                                                     |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | non      | Sujet du certificat (identifiant le domaine).                         |

### Exemples

=== "Basique"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Certificats courte durée"

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Test en RSA"

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```
