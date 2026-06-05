Le plugin Auth Basic fournit une authentification HTTP Basic pour protéger votre site ou certaines ressources. Les utilisateurs doivent saisir un identifiant et un mot de passe avant d’accéder au contenu protégé. Simple à mettre en place et largement supporté par les navigateurs.

Comment ça marche :

1. Sur une zone protégée, le serveur envoie un défi d’authentification.
2. Le navigateur affiche une boîte de connexion.
3. L’utilisateur saisit ses identifiants, envoyés au serveur.
4. Si les identifiants sont valides, l’accès au contenu demandé est accordé.
5. Si les identifiants sont invalides, une erreur 401 Unauthorized est renvoyée.

### Comment l’utiliser

1. Activer : mettez le paramètre `USE_AUTH_BASIC` à `yes`.
2. Portée : configurez le paramètre `AUTH_BASIC_LOCATION` avec `sitewide` (tout le site) ou un chemin (ex. `/admin`).
3. Identifiants : configurez les paramètres `AUTH_BASIC_USER` et `AUTH_BASIC_PASSWORD` (plusieurs paires possibles).
4. Message : optionnel, ajustez `AUTH_BASIC_TEXT`.

### Paramètres

| Paramètre             | Défaut            | Contexte  | Multiple | Description                                                                                                                              |
| --------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | non      | Activer l’authentification Basic.                                                                                                        |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | non      | Portée : `sitewide` ou un chemin (ex. `/admin`). Vous pouvez également utiliser des modificateurs de style Nginx (`=`, `~`, `~*`, `^~`). |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | oui      | Nom d’utilisateur. Plusieurs paires peuvent être définies.                                                                               |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | oui      | Mot de passe. Les mots de passe sont hachés avec scrypt pour une sécurité maximale.                                                      |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | non      | Message affiché dans l'invite d'authentification.                                                                                        |

!!! warning "Sécurité"
    Les identifiants sont encodés Base64, pas chiffrés. Utilisez toujours HTTPS avec l’authentification Basic.

!!! tip "Plusieurs comptes"
    Vous pouvez configurer plusieurs paires identifiant/mot de passe pour l'accès. Chaque paramètre `AUTH_BASIC_USER` doit avoir un paramètre `AUTH_BASIC_PASSWORD` correspondant.

### Exemples

=== "Tout le site"

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Zone spécifique"

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Utilisateurs multiples"

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # Premier utilisateur
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Deuxième utilisateur
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Troisième utilisateur
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```
