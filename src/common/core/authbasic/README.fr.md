Le plugin Auth Basic fournit une authentification HTTP Basic pour protéger votre site ou certaines ressources. Les utilisateurs doivent saisir un identifiant et un mot de passe avant d’accéder au contenu protégé. Simple à mettre en place et largement supporté par les navigateurs.

Comment ça marche :

1. Sur une zone protégée, le serveur envoie un défi d’authentification.
2. Le navigateur affiche une boîte de connexion.
3. L’utilisateur saisit ses identifiants, envoyés au serveur.
4. Valides ? Accès accordé. Invalides ? Réponse 401 Unauthorized.

### Comment l’utiliser

1. Activer : `USE_AUTH_BASIC: yes`.
2. Portée : `AUTH_BASIC_LOCATION` = `sitewide` (tout le site) ou un chemin (ex. `/admin`).
3. Identifiants : configurez `AUTH_BASIC_USER` et `AUTH_BASIC_PASSWORD` (plusieurs paires possibles).
4. Message : optionnel, ajustez `AUTH_BASIC_TEXT`.

### Paramètres

| Paramètre             | Défaut            | Contexte  | Multiple | Description                                                |
| --------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | non      | Activer l’authentification Basic.                          |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | non      | Portée : `sitewide` ou un chemin (ex. `/admin`).           |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | oui      | Nom d’utilisateur. Plusieurs paires peuvent être définies. |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | oui      | Mot de passe correspondant à chaque utilisateur.           |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | non      | Message affiché dans l’invite d’authentification.          |

!!! warning "Sécurité"
    Les identifiants sont encodés Base64, pas chiffrés. Utilisez toujours HTTPS avec l’authentification Basic.

!!! tip "Plusieurs comptes"
    Définissez des paires `AUTH_BASIC_USER[_n]`/`AUTH_BASIC_PASSWORD[_n]` pour gérer plusieurs utilisateurs.

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
