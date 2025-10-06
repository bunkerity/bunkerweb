Le plugin BunkerNet permet le partage collectif de renseignements sur les menaces entre instances BunkerWeb, créant un réseau de protection contre les acteurs malveillants. En y participant, votre instance bénéficie d’une base mondiale de menaces et y contribue de façon anonyme.

Comment ça marche :

1. Votre instance s’enregistre automatiquement auprès de l’API BunkerNet et reçoit un identifiant unique.
2. À chaque IP/comportement malveillant bloqué, l’information est signalée anonymement à BunkerNet.
3. BunkerNet agrège l’intelligence de toutes les instances et diffuse une base consolidée.
4. Votre instance télécharge régulièrement la base à jour.
5. Cette intelligence collective permet de bloquer proactivement des IP déjà malveillantes ailleurs.

### Comment l’utiliser

1. Activation : `USE_BUNKERNET` (activé par défaut).
2. Enregistrement initial : effectué automatiquement au premier démarrage.
3. Mises à jour : téléchargement automatique et régulier de la base.
4. Signalement : contribution automatique lors de blocages d’IP.
5. Suivi : statistiques visibles dans la [web UI](web-ui.md).

### Paramètres

| Paramètre          | Défaut                     | Contexte  | Multiple | Description                         |
| ------------------ | -------------------------- | --------- | -------- | ----------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | non      | Activer la participation BunkerNet. |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | non      | URL de l’API BunkerNet.             |

!!! info "Confidentialité"
    Seules les données nécessaires à l’identification de la menace sont partagées (IP, raison du blocage, contexte minimal).

### Intégration CrowdSec Console

Grâce au partenariat avec [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc), vous pouvez inscrire vos instances BunkerWeb dans votre [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) et visualiser les attaques bloquées.

Étapes principales :

1. Créez un compte CrowdSec Console et récupérez la clé d’enrôlement.
2. Récupérez votre BunkerNet ID (BunkerNet activé).
3. Commandez le service gratuit « BunkerNet / CrowdSec » sur le Panel et fournissez l’ID et la clé.
4. Acceptez le nouvel engine dans la Console.

### Exemples

=== "Configuration par défaut (recommandée)"

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Désactivation"

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Serveur personnalisé"

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```
