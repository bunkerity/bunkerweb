Le plugin GZIP compresse les réponses HTTP avec l’algorithme gzip pour réduire la bande passante et accélérer le chargement des pages.

### Fonctionnement

1. BunkerWeb détecte si le client supporte gzip.
2. Si oui, la réponse est compressée au niveau configuré.
3. Les en‑têtes indiquent l’usage de gzip.
4. Le navigateur décompresse avant l’affichage.

### Comment l’utiliser

1. Activer : `USE_GZIP: yes` (désactivé par défaut).
2. Types MIME : définir `GZIP_TYPES`.
3. Taille minimale : `GZIP_MIN_LENGTH` pour éviter les très petits fichiers.
4. Niveau de compression : `GZIP_COMP_LEVEL` (1–9).
5. Contenu proxifié : ajuster `GZIP_PROXIED`.

### Paramètres

| Paramètre         | Défaut                                                                                                                                                                                                                                                                                                                                                                                                                           | Contexte  | Multiple | Description                                                                             |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | --------------------------------------------------------------------------------------- |
| `USE_GZIP`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | non      | Activer la compression gzip.                                                            |
| `GZIP_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | non      | Types MIME compressés.                                                                  |
| `GZIP_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | non      | Taille minimale (octets) pour appliquer la compression.                                 |
| `GZIP_COMP_LEVEL` | `5`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | non      | Niveau 1–9 : plus haut = meilleure compression mais plus de CPU.                        |
| `GZIP_PROXIED`    | `no-cache no-store private expired auth`                                                                                                                                                                                                                                                                                                                                                                                         | multisite | non      | Précise quels contenus proxifiés doivent être compressés selon les en‑têtes de réponse. |

!!! tip "Niveau de compression"
`5` est un bon compromis. Statique/CPU dispo : 7–9. Dynamique/CPU limité : 1–3.

### Exemples

=== "Basique"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json application/xml text/css text/html text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "5"
    ```

=== "Compression maximale"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    GZIP_MIN_LENGTH: "500"
    GZIP_COMP_LEVEL: "9"
    GZIP_PROXIED: "any"
    ```

=== "Performance équilibrée"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "3"
    GZIP_PROXIED: "no-cache no-store private expired"
    ```

=== "Contenu proxifié"

    ```yaml
    USE_GZIP: "yes"
    GZIP_TYPES: "application/javascript application/json text/css text/html text/javascript"
    GZIP_MIN_LENGTH: "1000"
    GZIP_COMP_LEVEL: "4"
    GZIP_PROXIED: "any"
    ```
