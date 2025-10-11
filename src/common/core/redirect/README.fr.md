Le plugin Redirect fournit des redirections HTTP simples et efficaces. Il permet de rediriger des visiteurs d’une URL à une autre, pour un domaine entier, des chemins précis, avec ou sans conservation du chemin d’origine.

Comment ça marche :

1. À l’accès d’un visiteur, BunkerWeb vérifie si une redirection est définie.
2. Si activée, il redirige vers l’URL de destination.
3. Vous pouvez préserver le chemin d’origine (`REDIRECT_TO_REQUEST_URI: yes`).
4. Le code HTTP peut être `301` (permanent) ou `302` (temporaire).
5. Idéal pour migrations, canonicals, URLs obsolètes.

### Comment l’utiliser

1. Source : `REDIRECT_FROM` (ex. `/`, `/old-page`).
2. Destination : `REDIRECT_TO`.
3. Type : `REDIRECT_TO_REQUEST_URI` pour conserver le chemin.
4. Code : `REDIRECT_TO_STATUS_CODE` (`301` ou `302`).

### Paramètres

| Paramètre                 | Défaut | Contexte  | Multiple | Description                                                         |
| ------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------- |
| `REDIRECT_FROM`           | `/`    | multisite | oui      | Chemin source à rediriger.                                          |
| `REDIRECT_TO`             |        | multisite | oui      | URL de destination. Laisser vide pour désactiver.                   |
| `REDIRECT_TO_REQUEST_URI` | `no`   | multisite | oui      | Conserver le chemin d’origine en l’ajoutant à l’URL de destination. |
| `REDIRECT_TO_STATUS_CODE` | `301`  | multisite | oui      | Code de statut HTTP : `301` (permanent) ou `302` (temporaire).      |

!!! tip "Choisir le bon code"
    `301` pour une redirection permanente (migrations, canonicals). `302` pour temporaire.

!!! info "Conservation du chemin"
    Avec `REDIRECT_TO_REQUEST_URI: yes`, `/blog/post-1` vers `https://new.com` devient `https://new.com/blog/post-1`.

### Exemples

=== "Multiples chemins"

    ```yaml
    REDIRECT_FROM: "/blog/"
    REDIRECT_TO: "https://blog.example.com/"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"

    REDIRECT_FROM_2: "/shop/"
    REDIRECT_TO_2: "https://shop.example.com/"
    REDIRECT_TO_REQUEST_URI_2: "no"
    REDIRECT_TO_STATUS_CODE_2: "301"

    REDIRECT_FROM_3: "/"
    REDIRECT_TO_3: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI_3: "no"
    REDIRECT_TO_STATUS_CODE_3: "301"
    ```

=== "Domaine entier"

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Conserver le chemin"

    ```yaml
    REDIRECT_TO: "https://new-domain.com"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```

=== "Temporaire"

    ```yaml
    REDIRECT_TO: "https://maintenance.example.com"
    REDIRECT_TO_REQUEST_URI: "no"
    REDIRECT_TO_STATUS_CODE: "302"
    ```

=== "Sous‑domaine → chemin"

    ```yaml
    REDIRECT_TO: "https://example.com/support"
    REDIRECT_TO_REQUEST_URI: "yes"
    REDIRECT_TO_STATUS_CODE: "301"
    ```
