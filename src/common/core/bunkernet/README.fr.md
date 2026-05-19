Le plugin BunkerNet permet le partage collectif de renseignements sur les menaces entre instances BunkerWeb, créant un puissant réseau de protection contre les acteurs malveillants. En participant à BunkerNet, votre instance bénéficie d'une base mondiale de menaces connues et y contribue, ce qui renforce la sécurité de toute la communauté BunkerWeb.

**Comment ça marche :**

1. Votre instance BunkerWeb s'enregistre automatiquement auprès de l'API BunkerNet afin de recevoir un identifiant unique.
2. Lorsque votre instance détecte et bloque une adresse IP ou un comportement malveillant, elle signale anonymement la menace à BunkerNet.
3. BunkerNet agrège les renseignements sur les menaces provenant de toutes les instances participantes et distribue la base consolidée.
4. Votre instance télécharge régulièrement une base mise à jour des menaces connues depuis BunkerNet.
5. Cette intelligence collective permet à votre instance de bloquer proactivement des adresses IP ayant eu un comportement malveillant sur d'autres instances BunkerWeb.

!!! success "Avantages clés"
    1. **Défense collective :** Exploitez les détections de sécurité de milliers d'autres instances BunkerWeb dans le monde.
    2. **Protection proactive :** Bloquez les acteurs malveillants avant qu'ils ne ciblent votre site, d'après leur comportement ailleurs.
    3. **Contribution communautaire :** Aidez à protéger les autres utilisateurs BunkerWeb en partageant des données anonymisées sur les attaquants.
    4. **Zéro configuration :** Fonctionne immédiatement avec des valeurs par défaut adaptées et très peu de configuration.
    5. **Respect de la vie privée :** Ne partage que les informations de menace nécessaires, sans compromettre votre confidentialité ni celle de vos utilisateurs.

### Comment l'utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité BunkerNet :

1. **Activer la fonctionnalité :** La fonctionnalité BunkerNet est activée par défaut. Si nécessaire, vous pouvez la contrôler avec le paramètre `USE_BUNKERNET`.
2. **Enregistrement initial :** Au premier démarrage, votre instance s'enregistre automatiquement auprès de l'API BunkerNet et reçoit un identifiant unique.
3. **Mises à jour automatiques :** Votre instance télécharge automatiquement la dernière base de menaces selon une planification régulière.
4. **Signalement automatique :** Lorsque votre instance bloque une adresse IP malveillante, elle contribue automatiquement ces données à la communauté.
5. **Surveiller la protection :** Consultez l'[interface web](web-ui.md) pour voir les statistiques des menaces bloquées grâce aux renseignements BunkerNet.

### Paramètres de configuration

| Paramètre          | Défaut                     | Contexte  | Multiple | Description                                                                                  |
| ------------------ | -------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | non      | **Activer BunkerNet :** Mettre à `yes` pour activer le partage de renseignements BunkerNet.  |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | non      | **Serveur BunkerNet :** Adresse du serveur API BunkerNet pour partager les renseignements sur les menaces. |

!!! tip "Protection réseau"
    Lorsque BunkerNet détecte qu'une adresse IP a été impliquée dans une activité malveillante sur plusieurs instances BunkerWeb, il ajoute cette IP à une blacklist collective. Cela fournit une couche de défense proactive, protégeant votre site contre les menaces avant qu'elles ne vous ciblent directement.

!!! info "Signalement anonyme"
    Lors du signalement d'informations de menace à BunkerNet, votre instance ne partage que les données nécessaires pour identifier la menace : l'adresse IP, la raison du blocage et un minimum de contexte. Aucune information personnelle sur vos utilisateurs ni aucun détail sensible sur votre site n'est partagé.

### Exemples de configuration

=== "Configuration par défaut (recommandée)"

    La configuration par défaut active BunkerNet avec le serveur API officiel de BunkerWeb :

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Configuration désactivée"

    Si vous préférez ne pas participer au réseau de renseignements BunkerNet :

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Configuration avec serveur personnalisé"

    Pour les organisations exploitant leur propre serveur BunkerNet (peu courant) :

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

### Intégration CrowdSec Console

Si vous ne connaissez pas encore l'intégration CrowdSec Console, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) utilise le renseignement participatif pour combattre les cybermenaces. Imaginez un "Waze de la cybersécurité" : lorsqu'un serveur est attaqué, d'autres systèmes dans le monde sont alertés et protégés contre les mêmes attaquants. Vous pouvez en savoir plus [ici](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

Grâce à notre partenariat avec CrowdSec, vous pouvez enrôler vos instances BunkerWeb dans votre [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration). Les attaques bloquées par BunkerWeb seront visibles dans votre CrowdSec Console aux côtés des attaques bloquées par les CrowdSec Security Engines, ce qui vous donne une vue unifiée des menaces.

Important : CrowdSec n'a pas besoin d'être installé pour cette intégration, même si nous recommandons fortement de l'essayer avec le [plugin CrowdSec pour BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) afin de renforcer davantage la sécurité de vos services web. Vous pouvez également enrôler vos CrowdSec Security Engines dans le même compte Console pour encore plus de synergie.

**Étape n°1 : Créer votre compte CrowdSec Console**

Rendez-vous sur la [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) et inscrivez-vous si vous n'avez pas encore de compte. Une fois terminé, notez la clé d'enrôlement disponible dans "Security Engines" après avoir cliqué sur "Add Security Engine" :

<figure markdown>
  ![Overview](assets/img/crowdity1.png){ align=center }
  <figcaption>Obtenir votre clé d'enrôlement CrowdSec Console</figcaption>
</figure>

**Étape n°2 : Obtenir votre identifiant BunkerNet**

L'activation de la fonctionnalité BunkerNet (activée par défaut) est obligatoire si vous souhaitez enrôler vos instances BunkerWeb dans votre CrowdSec Console. Activez-la en définissant `USE_BUNKERNET` à `yes`.

Pour Docker, obtenez votre identifiant BunkerNet avec :

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

Pour Linux, utilisez :

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**Étape n°3 : Enrôler votre instance avec le Panel**

Une fois votre identifiant BunkerNet et votre clé d'enrôlement CrowdSec Console obtenus, [commandez le produit gratuit "BunkerNet / CrowdSec" sur le Panel](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc). Vous pourrez être invité à créer un compte si ce n'est pas déjà fait.

Vous pouvez maintenant sélectionner le service "BunkerNet / CrowdSec" et remplir le formulaire en collant votre identifiant BunkerNet et votre clé d'enrôlement CrowdSec Console :

<figure markdown>
  ![Overview](assets/img/crowdity2.png){ align=center }
  <figcaption>Enrôler votre instance BunkerWeb dans la CrowdSec Console</figcaption>
</figure>

**Étape n°4 : Accepter le nouveau security engine dans la Console**

Retournez ensuite dans votre CrowdSec Console et acceptez le nouveau Security Engine :

<figure markdown>
  ![Overview](assets/img/crowdity3.png){ align=center }
  <figcaption>Accepter l'enrôlement dans la CrowdSec Console</figcaption>
</figure>

**Félicitations, votre instance BunkerWeb est maintenant enrôlée dans votre CrowdSec Console !**

Astuce : Lorsque vous consultez vos alertes, cliquez sur l'option "columns" et cochez la case "context" pour accéder aux données spécifiques à BunkerWeb.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>Données BunkerWeb affichées dans la colonne context</figcaption>
</figure>
