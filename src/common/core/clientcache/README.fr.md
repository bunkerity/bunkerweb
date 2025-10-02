Le plugin Client Cache optimise les performances en contrôlant la mise en cache des contenus statiques par les navigateurs. Il réduit la bande passante, la charge serveur et accélère les temps de chargement en instruisant les navigateurs à conserver localement images, CSS, JS, etc., plutôt que de les retélécharger à chaque visite.

Comment ça marche :

1. Une fois activé, BunkerWeb ajoute des en‑têtes Cache-Control aux réponses des fichiers statiques.
2. Ces en‑têtes indiquent aux navigateurs pendant combien de temps conserver localement le contenu.
3. Pour les extensions spécifiées (images, CSS, JS…), BunkerWeb applique la politique de cache configurée.
4. Les ETags (optionnels) fournissent un mécanisme de validation supplémentaire.
5. Lors des visites suivantes, le navigateur réutilise les fichiers en cache, accélérant le chargement.

### Comment l’utiliser

1. Activer : mettez `USE_CLIENT_CACHE` à `yes` (désactivé par défaut).
2. Extensions : définissez `CLIENT_CACHE_EXTENSIONS` pour les types de fichiers à mettre en cache.
3. Directives Cache-Control : personnalisez `CLIENT_CACHE_CONTROL`.
4. ETag : activez ou non via `CLIENT_CACHE_ETAG`.

### Paramètres

| Paramètre                 | Défaut                                                                    | Contexte  | Multiple | Description                                                  |
| ------------------------- | ------------------------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------ | --- |
| `USE_CLIENT_CACHE`        | `no`                                                                      | multisite | non      | Activer la mise en cache côté client des fichiers statiques. |
| `CLIENT_CACHE_EXTENSIONS` | `jpg\|jpeg\|png\|bmp\|ico\|svg\|tif\|css\|js\|otf\|ttf\|eot\|woff\|woff2` | global    | non      | Extensions mises en cache (séparées par `                    | `). |
| `CLIENT_CACHE_CONTROL`    | `public, max-age=15552000`                                                | multisite | non      | Valeur de l’en‑tête HTTP Cache-Control.                      |
| `CLIENT_CACHE_ETAG`       | `yes`                                                                     | multisite | non      | Envoi d’un ETag pour les ressources statiques.               |

!!! tip "Optimiser le cache"
Contenu fréquemment mis à jour : durée plus courte. Contenu versionné ou peu changeant : durée plus longue. La valeur par défaut (180 jours) convient souvent.

### Exemples

=== "Basique"

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|gif|css|js|svg|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=86400"
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Agressif"

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2|pdf|xml|txt"
    CLIENT_CACHE_CONTROL: "public, max-age=31536000, immutable"
    CLIENT_CACHE_ETAG: "yes"
    ```

=== "Mixte"

    ```yaml
    USE_CLIENT_CACHE: "yes"
    CLIENT_CACHE_EXTENSIONS: "jpg|jpeg|png|bmp|ico|svg|tif|gif|css|js|otf|ttf|eot|woff|woff2"
    CLIENT_CACHE_CONTROL: "public, max-age=604800"
    CLIENT_CACHE_ETAG: "yes"
    ```
