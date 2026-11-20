Le plugin Zstandard compresse les réponses HTTP avec l’algorithme Zstandard (zstd). Il réduit la consommation de bande passante pour les clients qui annoncent `Accept-Encoding: zstd`.

### Utilisation

1. Activer : définissez `USE_ZSTD` sur `yes` (désactivé par défaut).
2. Types MIME et taille minimale : choisissez les contenus à compresser avec `ZSTD_TYPES` et la taille minimale d’une réponse avec `ZSTD_MIN_LENGTH`.
3. Niveau de compression : réglez `ZSTD_COMP_LEVEL` entre `1` (le plus rapide) et `19` (compression maximale prise en charge). La valeur par défaut est `3`.

Les clients compatibles zstd reçoivent `Content-Encoding: zstd` et `Vary: Accept-Encoding`. Les clients sans prise en charge de zstd, y compris ceux qui envoient `zstd;q=0`, peuvent recevoir du Brotli ou du gzip lorsque ces plugins sont activés ; sinon, ils reçoivent des réponses non compressées.

Avec `USE_ZSTD=yes`, les réponses éligibles peuvent contenir `Vary: Accept-Encoding` même si la représentation choisie est non compressée, en gzip ou en Brotli. Les caches doivent respecter cet en-tête pour séparer les représentations.

Lorsque plusieurs plugins de compression sont activés, la préférence du serveur va à zstd, puis à Brotli, puis à gzip. Chaque codage respecte son propre `q=0` ; les poids positifs ne sont pas comparés entre les plugins de compression.

### Paramètres

| Paramètre         | Défaut                                                                                                                                                                                                                                                                                                                                                                                                                           | Contexte  | Multiple | Description                                                                                                |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------- |
| `USE_ZSTD`        | `no`                                                                                                                                                                                                                                                                                                                                                                                                                             | multisite | non      | Activer la compression Zstandard des réponses.                                                             |
| `ZSTD_TYPES`      | `application/atom+xml application/javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-opentype application/x-font-truetype application/x-font-ttf application/x-javascript application/xhtml+xml application/xml font/eot font/opentype font/otf font/truetype image/svg+xml image/vnd.microsoft.icon image/x-icon image/x-win-bitmap text/css text/javascript text/plain text/xml` | multisite | non      | Types MIME à compresser, en plus de `text/html` qui est toujours inclus.                                   |
| `ZSTD_MIN_LENGTH` | `1000`                                                                                                                                                                                                                                                                                                                                                                                                                           | multisite | non      | Taille minimale de la réponse en octets. Les réponses de longueur inconnue peuvent aussi être compressées. |
| `ZSTD_COMP_LEVEL` | `3`                                                                                                                                                                                                                                                                                                                                                                                                                              | multisite | non      | Niveau de compression de `1` à `19`. Plus le niveau est élevé, plus le CPU et la mémoire sont sollicités.  |

!!! tip "Niveau de compression"
    Commencez au niveau `3`. Les niveaux plus élevés augmentent la consommation de CPU et de mémoire par requête ; gardez de la marge pour les requêtes concurrentes. Les niveaux sont limités à `19` pour respecter la limite de fenêtre zstd de 8 Mo pour HTTP.

!!! warning "Réponses sensibles"
    La compression peut révéler des secrets par les différences de taille des réponses lorsqu’une réponse contient à la fois des secrets et des données contrôlées par un attaquant. Désactivez la compression pour les services sensibles ou traitez ce risque dans l’application. `text/html` est toujours éligible lorsque zstd est activé, même s’il est absent de `ZSTD_TYPES`.

!!! info "Compression en amont"
    Les réponses déjà compressées par l’upstream ne sont pas recompressées. Le plugin inject a besoin d’une réponse non compressée de l’upstream pour modifier le HTML ; configurez l’upstream en conséquence si vous utilisez les deux fonctions.

### Exemple de configuration

Activer zstd avec Brotli et gzip en repli :

```yaml
USE_ZSTD: "yes"
ZSTD_MIN_LENGTH: "1000"
ZSTD_COMP_LEVEL: "3"
USE_BROTLI: "yes"
USE_GZIP: "yes"
```
