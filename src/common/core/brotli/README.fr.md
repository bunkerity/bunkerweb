Le plugin Brotli active la compression des réponses HTTP avec l’algorithme Brotli. Il réduit l’usage de bande passante et accélère le chargement en compressant le contenu avant l’envoi au navigateur.

Par rapport à gzip, Brotli atteint généralement de meilleurs taux de compression, pour des fichiers plus petits et une livraison plus rapide.

Comment ça marche :

1. À la requête d’un client, BunkerWeb vérifie si le navigateur supporte Brotli.
2. Si oui, la réponse est compressée au niveau configuré (`BROTLI_COMP_LEVEL`).
3. Les en‑têtes appropriés indiquent la compression Brotli.
4. Le navigateur décompresse avant affichage.
5. Bande passante et temps de chargement diminuent.

### Comment l’utiliser

1. Activer : `USE_BROTLI: yes` (désactivé par défaut).
2. Types MIME : définir les contenus à compresser via `BROTLI_TYPES`.
3. Taille minimale : `BROTLI_MIN_LENGTH` pour éviter de compresser les petites réponses.
4. Niveau de compression : `BROTLI_COMP_LEVEL` pour l’équilibre vitesse/ratio.

### Paramètres

| Paramètre           | Défaut                                                                                                                                                                                                                                                                                                                                                                                                                           | Contexte  | Multiple | Description                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ----------------------------------------------------------------- |
| `USE_BROTLI`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | non      | Activer la compression Brotli.                                    |
| `BROTLI_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | non      | Types MIME compressés.                                            |
| `BROTLI_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | non      | Taille minimale (octets) pour appliquer la compression.           |
| `BROTLI_COMP_LEVEL` | `6`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | non      | Niveau 0–11 : plus haut = meilleure compression mais plus de CPU. |

!!! tip "Niveau de compression"
    `6` offre un bon compromis. Pour du statique et CPU disponible : 9–11. Pour du dynamique ou CPU contraint : 4–5.

### Exemples

=== "Basique"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json application/xml application/xhtml+xml text/css text/html text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "6"
    ```

=== "Compression maximale"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml"
    BROTLI_MIN_LENGTH: "500"
    BROTLI_COMP_LEVEL: "11"
    ```

=== "Performance équilibrée"

    ```yaml
    USE_BROTLI: "yes"
    BROTLI_TYPES: "application/javascript application/json text/css text/html text/javascript text/plain"
    BROTLI_MIN_LENGTH: "1000"
    BROTLI_COMP_LEVEL: "4"
    ```
