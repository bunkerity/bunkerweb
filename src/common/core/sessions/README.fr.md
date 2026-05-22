Le plugin Sessions fournit une gestion robuste des sessions HTTP dans BunkerWeb pour suivre de manière sécurisée et fiable les sessions utilisateur entre les requêtes. Cette fonctionnalité centrale est essentielle pour maintenir l’état utilisateur, la persistance d’authentification et les autres fonctions qui nécessitent une continuité d’identité, comme la protection [antibot](#antibot) et les systèmes d’authentification utilisateur.

**Comment ça marche :**

1. Lorsqu’un utilisateur interagit pour la première fois avec votre site, BunkerWeb crée un identifiant de session unique.
2. Cet identifiant est stocké de manière sécurisée dans un cookie du navigateur de l’utilisateur.
3. Lors des requêtes suivantes, BunkerWeb récupère l’identifiant de session depuis le cookie et l’utilise pour accéder aux données de session de l’utilisateur.
4. Les données de session peuvent être stockées localement ou dans [Redis](#redis) pour les environnements distribués comportant plusieurs instances BunkerWeb.
5. Les sessions sont gérées automatiquement avec des délais configurables, ce qui garantit la sécurité tout en conservant une bonne ergonomie.
6. La sécurité cryptographique des sessions est assurée par une clé secrète utilisée pour signer les cookies de session.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Sessions :

1. **Configurer la sécurité des sessions :** définissez un `SESSIONS_SECRET` fort et unique pour empêcher la falsification des cookies de session. (La valeur par défaut est "random", ce qui amène BunkerWeb à générer une clé secrète aléatoire.)
2. **Choisir un nom de session :** personnalisez éventuellement `SESSIONS_NAME` pour définir le nom du cookie de session dans le navigateur. (La valeur par défaut est "random", ce qui amène BunkerWeb à générer un nom aléatoire.)
3. **Définir les délais d’expiration :** configurez la durée de validité des sessions avec les paramètres (`SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`).
4. **Partager le cookie entre sous-domaines (optionnel, par serveur) :** par défaut, le cookie de session est limité à l’hôte. Si un serveur donné héberge plusieurs sous-domaines d’un même domaine enregistrable (par exemple `a.example.com` et `b.example.com`) et que vous voulez partager l’état antibot/défi, définissez `SESSIONS_DOMAIN` sur le domaine parent (`example.com`) **sur ce serveur uniquement**. `SESSIONS_DOMAIN` est un paramètre multisite : configurez-le par serveur afin que des tenants non liés sur une même instance BunkerWeb ne reçoivent jamais un attribut `Domain` partagé entre tenants.
5. **Configurer l’intégration Redis :** pour les environnements distribués, définissez `USE_REDIS` sur "yes" et configurez votre [connexion Redis](#redis) afin de partager les données de session entre plusieurs nœuds BunkerWeb.
6. **Laisser BunkerWeb gérer le reste :** une fois configurée, la gestion des sessions est assurée automatiquement pour votre site.

### Paramètres de configuration

| Paramètre                   | Défaut   | Contexte  | Multiple | Description                                                                                                                                                                                                                                  |
| --------------------------- | -------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random` | global    | non      | **Secret de session :** clé cryptographique utilisée pour signer les cookies de session. Elle doit être une chaîne forte, aléatoire et propre à votre site.                                                                                |
| `SESSIONS_NAME`             | `random` | global    | non      | **Nom du cookie :** nom du cookie qui stockera l’identifiant de session.                                                                                                                                                                      |
| `SESSIONS_DOMAIN`           |          | multisite | non      | **Domaine du cookie :** attribut `Domain` optionnel appliqué au cookie de session (par exemple `example.com`). Laissez vide pour conserver un cookie limité à l’hôte. Définissez-le par serveur pour partager l’état de session entre sous-domaines frères d’un même domaine enregistrable. |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`   | global    | non      | **Délai d’inactivité :** durée maximale (en secondes) d’inactivité avant invalidation de la session.                                                                                                                                         |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`   | global    | non      | **Délai glissant :** durée maximale (en secondes) avant qu’une session doive être renouvelée.                                                                                                                                                |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`  | global    | non      | **Délai absolu :** durée maximale (en secondes) avant qu’une session soit détruite quelle que soit l’activité.                                                                                                                               |
| `SESSIONS_CHECK_IP`         | `yes`    | global    | non      | **Vérification IP :** lorsqu’il vaut `yes`, détruit la session si l’adresse IP du client change.                                                                                                                                             |
| `SESSIONS_CHECK_USER_AGENT` | `yes`    | global    | non      | **Vérification User-Agent :** lorsqu’il vaut `yes`, détruit la session si le User-Agent du client change.                                                                                                                                    |

!!! warning "Considérations de sécurité"
    Le paramètre `SESSIONS_SECRET` est critique pour la sécurité. En production :

    1. Utilisez une valeur forte et aléatoire (au moins 32 caractères)
    2. Gardez cette valeur confidentielle
    3. Utilisez exactement la même valeur sur toutes les instances BunkerWeb d’un cluster
    4. Envisagez des variables d’environnement ou un gestionnaire de secrets pour éviter de stocker cette valeur en clair

!!! tip "Environnements en cluster"
    Si vous exécutez plusieurs instances BunkerWeb derrière un répartiteur de charge :

    1. Définissez `USE_REDIS` sur `yes` et configurez votre connexion Redis
    2. Assurez-vous que toutes les instances utilisent exactement le même `SESSIONS_SECRET` et `SESSIONS_NAME`
    3. Cela garantit que les utilisateurs conservent leur session quelle que soit l’instance BunkerWeb qui traite leurs requêtes

### Exemples de configuration

=== "Configuration de base"

    Une configuration simple pour une instance BunkerWeb unique :

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "myappsession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Sécurité renforcée"

    Configuration avec des réglages de sécurité renforcés :

    ```yaml
    SESSIONS_SECRET: "your-very-strong-random-secret-key-here"
    SESSIONS_NAME: "securesession"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 minutes
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 minutes
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 heures
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Environnement en cluster avec Redis"

    Configuration pour plusieurs instances BunkerWeb partageant les données de session :

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "clustersession"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Assurez-vous que la connexion Redis est correctement configurée
    ```

=== "Sessions longue durée"

    Configuration pour les applications nécessitant une persistance de session étendue :

    ```yaml
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "persistentsession"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 jour
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 jours
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 jours
    ```

=== "Sessions inter-sous-domaines (tenant unique)"

    Partagez le cookie de session entre tous les sous-domaines de `example.com` afin que l’état antibot/défi ne doive être résolu qu’une seule fois pour tout le site :

    ```yaml
    SERVER_NAME: "app.example.com api.example.com shop.example.com"
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "crossdomainsession"
    # SESSIONS_DOMAIN est un paramètre multisite : préfixez-le avec le nom du serveur pour qu’il ne s’applique qu’aux hôtes correspondants
    app.example.com_SESSIONS_DOMAIN: "example.com"
    api.example.com_SESSIONS_DOMAIN: "example.com"
    shop.example.com_SESSIONS_DOMAIN: "example.com"
    USE_ANTIBOT: "turnstile"
    ```

=== "Sessions inter-sous-domaines (tenants mixtes)"

    Lorsque la même instance BunkerWeb héberge plusieurs domaines enregistrables non liés, limitez `SESSIONS_DOMAIN` aux seuls serveurs qui doivent partager le cookie. Les serveurs non configurés conservent le cookie limité à l’hôte par défaut, de sorte que les tenants restent isolés :

    ```yaml
    SERVER_NAME: "app.example.com api.example.com billing.acme.org www.unrelated.io"
    SESSIONS_SECRET: "your-strong-random-secret-key-here"
    SESSIONS_NAME: "tenantsession"
    # Partagez le cookie uniquement entre les sous-domaines example.com
    app.example.com_SESSIONS_DOMAIN: "example.com"
    api.example.com_SESSIONS_DOMAIN: "example.com"
    # billing.acme.org et www.unrelated.io restent volontairement limités à l’hôte
    USE_ANTIBOT: "turnstile"
    ```

    !!! note
        `SESSIONS_DOMAIN` doit toujours être un domaine parent du serveur auquel il s’applique. Par exemple, `example.com` est valide à la fois pour `example.com` et pour n’importe quel hôte `*.example.com`, et un point initial (`.example.com`) reste toléré pour compatibilité historique. Le définir sur un domaine enregistrable non lié fera rejeter le cookie par les navigateurs.
