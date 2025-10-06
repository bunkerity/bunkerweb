Le plugin PHP fournit l’intégration PHP‑FPM avec BunkerWeb pour exécuter du PHP dynamiquement. Il prend en charge des instances locales (même machine) et distantes, offrant de la flexibilité dans l’architecture.

Comment ça marche :

1. À la demande d’un fichier PHP, BunkerWeb route la requête vers l’instance PHP‑FPM configurée.
2. En local, la communication se fait via un socket Unix.
3. À distance, la communication utilise FastCGI vers l’hôte et le port indiqués.
4. PHP‑FPM exécute le script et renvoie la réponse à BunkerWeb qui la livre au client.
5. La réécriture d’URL est automatiquement configurée pour les frameworks/applications qui utilisent des « pretty URLs ».

### Comment l’utiliser

1. Choisissez local vs distant.
2. Connexion : chemin du socket (local) ou hôte+port (distant).
3. Racine de documents : pointez vers le dossier contenant vos fichiers PHP.

### Paramètres

| Paramètre         | Défaut | Contexte  | Multiple | Description                                                                    |
| ----------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------ |
| `REMOTE_PHP`      |        | multisite | non      | Hôte PHP‑FPM distant. Laissez vide pour utiliser le local.                     |
| `REMOTE_PHP_PATH` |        | multisite | non      | Chemin racine des fichiers côté PHP‑FPM distant.                               |
| `REMOTE_PHP_PORT` | `9000` | multisite | non      | Port PHP‑FPM distant.                                                          |
| `LOCAL_PHP`       |        | multisite | non      | Chemin du socket PHP‑FPM local. Laissez vide pour utiliser un PHP‑FPM distant. |
| `LOCAL_PHP_PATH`  |        | multisite | non      | Chemin racine des fichiers côté PHP‑FPM local.                                 |

!!! tip "Local vs distant"
    Local : meilleures perfs (socket). Distant : flexibilité et scalabilité.

!!! warning "Chemins"
    `REMOTE_PHP_PATH`/`LOCAL_PHP_PATH` doivent correspondre au chemin réel des fichiers sous peine d’erreurs « File not found ».

!!! info "Réécriture d’URL"
    Le plugin configure automatiquement la réécriture pour diriger les requêtes vers `index.php` si le fichier demandé n’existe pas.

### Exemples

=== "PHP‑FPM local"

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html"
    ```

=== "PHP‑FPM distant"

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9000"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "Port personnalisé"

    ```yaml
    REMOTE_PHP: "php-server.example.com"
    REMOTE_PHP_PORT: "9001"
    REMOTE_PHP_PATH: "/var/www/html"
    ```

=== "WordPress"

    ```yaml
    LOCAL_PHP: "/var/run/php/php8.1-fpm.sock"
    LOCAL_PHP_PATH: "/var/www/html/wordpress"
    ```
