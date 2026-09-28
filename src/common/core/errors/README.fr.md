Le plugin Errors fournit une gestion personnalisable des erreurs HTTP, afin de définir l’apparence des réponses d’erreur pour vos utilisateurs. Vous pouvez ainsi afficher des pages d’erreur claires et cohérentes avec votre identité, plutôt que les pages techniques par défaut du serveur.

Comment ça marche :

1. Quand une erreur HTTP survient (ex. 400, 404, 500), BunkerWeb intercepte la réponse.
2. À la place de la page par défaut, BunkerWeb affiche une page personnalisée et soignée.
3. Les pages d’erreur sont configurables : vous pouvez fournir un fichier HTML par code d’erreur. Les fichiers doivent être placés dans le répertoire défini par `ROOT_FOLDER` (voir le plugin Misc).
   - Par défaut, `ROOT_FOLDER` vaut `/var/www/html/{server_name}`.
   - En mode multisite, chaque site a son propre `ROOT_FOLDER` ; placez les pages d’erreur dans le dossier correspondant à chaque site.
4. Les pages par défaut expliquent clairement le problème et suggèrent des actions possibles.

### Comment l’utiliser

1. Définir les pages personnalisées : utilisez `ERRORS` pour associer des codes HTTP à des fichiers HTML (dans `ROOT_FOLDER`).
2. Configurer vos pages : utilisez celles de BunkerWeb par défaut ou vos propres fichiers (placés dans le `ROOT_FOLDER` approprié).
3. Définir les codes interceptés : avec `INTERCEPTED_ERROR_CODES`, choisissez les codes toujours gérés par BunkerWeb.
4. Laissez BunkerWeb faire le reste : la gestion d’erreurs sera appliquée automatiquement.

### Paramètres

| Paramètre                 | Défaut                                            | Contexte  | Multiple | Description                                                                                                  |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `ERRORS`                  |                                                   | multisite | non      | Pages d’erreur personnalisées : paires `CODE=/chemin/page.html`.                                             |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | non      | Codes interceptés : liste de codes gérés avec la page par défaut si aucune page personnalisée n’est définie. |

!!! tip "Conception des pages"
    Les pages d’erreur BunkerWeb par défaut sont informatives, conviviales et professionnelles. Elles incluent :

    - Des descriptions d’erreur claires
    - Des informations sur les causes possibles
    - Des actions suggérées pour résoudre le problème
    - Des repères visuels indiquant si le problème vient du client ou du serveur

!!! info "Types d’erreurs"
    Les codes d’erreur sont classés par type :

    - **Erreurs 4xx (côté client) :** requêtes invalides, ressource inexistante, authentification manquante…
    - **Erreurs 5xx (côté serveur) :** impossibilité de traiter une requête valide (erreur interne, indisponibilité temporaire…).

### Exemples

=== "Gestion par défaut"

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Pages personnalisées"

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Gestion sélective"

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```
