<figure markdown>
  ![Overview](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

Le plugin CrowdSec intègre BunkerWeb avec le moteur de sécurité CrowdSec, fournissant une couche de protection supplémentaire contre diverses cybermenaces. Ce plugin agit comme un bouncer [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs), refusant les requêtes en fonction des décisions de l'API CrowdSec.

CrowdSec est un moteur de sécurité moderne et open-source qui détecte et bloque les adresses IP malveillantes en se basant sur l'analyse comportementale et l'intelligence collective de sa communauté. Vous pouvez également configurer des [scénarios](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) pour bannir automatiquement les adresses IP en fonction de comportements suspects, bénéficiant ainsi d'une liste noire participative.

**Comment ça marche :**

1. Le moteur CrowdSec analyse les journaux et détecte les activités suspectes sur votre infrastructure.
2. Lorsqu'une activité malveillante est détectée, CrowdSec crée une décision pour bloquer l'adresse IP incriminée.
3. BunkerWeb, agissant comme un bouncer, interroge l'API locale de CrowdSec pour obtenir des décisions concernant les requêtes entrantes.
4. Si l'adresse IP d'un client fait l'objet d'une décision de blocage active, BunkerWeb refuse l'accès aux services protégés.
5. En option, le composant de sécurité applicative (Application Security Component) peut effectuer une inspection approfondie des requêtes pour une sécurité renforcée.

!!! success "Bénéfices clés"

      1. **Sécurité communautaire :** Bénéficiez des renseignements sur les menaces partagés par la communauté des utilisateurs de CrowdSec.
      2. **Analyse comportementale :** Détectez les attaques sophistiquées basées sur des modèles de comportement, et non uniquement sur des signatures.
      3. **Intégration légère :** Impact minimal sur les performances de votre instance BunkerWeb.
      4. **Protection multi-niveaux :** Combinez la défense périmétrique (blocage d'IP) avec la sécurité applicative pour une protection en profondeur.

### Prérequis

- Une API locale CrowdSec accessible par BunkerWeb (généralement l’agent exécuté sur la même machine ou dans le même réseau Docker).
- L’accès aux journaux d’accès de BunkerWeb (`/var/log/bunkerweb/access.log` par défaut) pour que l’agent CrowdSec puisse analyser les requêtes.
- L’accès à `cscli` sur l’hôte CrowdSec afin d’enregistrer la clé du bouncer BunkerWeb.

!!! warning "Démarrage explicite en tout-en-un"
    L’agent CrowdSec intégré démarre uniquement si le conteneur tout-en-un reçoit la variable d’environnement sans préfixe `USE_CROWDSEC=yes` et une `CROWDSEC_API` locale (`http://127.0.0.1:8000` par défaut). Activer CrowdSec uniquement pour un service ne démarre pas l’agent intégré. Avec une API locale externe, démarrez et configurez l’agent séparément.

### Parcours d’intégration

1. Préparer l’agent CrowdSec pour ingérer les journaux BunkerWeb.
2. Configurer BunkerWeb pour interroger l’API locale CrowdSec.
3. Valider le lien via l’API `/crowdsec/ping` ou la carte CrowdSec dans l’interface d’administration.

    Ce contrôle effectue une requête de lecture authentifiée auprès de chaque API locale configurée. Il échoue si une API est inaccessible, refuse la clé, renvoie une réponse invalide ou si le bouncer d’un service n’a pas pu être chargé. Pour les services utilisant uniquement AppSec, il confirme le chargement de la configuration ; il ne teste ni la connexion ni l’inspection AppSec.

Les sections suivantes détaillent chacune de ces étapes.

### Investigation et suppression des décisions

Ouvrez **Pages supplémentaires → CrowdSec** dans l’interface Web pour consulter chaque connexion configurée, le service concerné, la connectivité à l’API locale et la synchronisation des décisions. La carte d’état du plugin CrowdSec et les actions **Examiner l’IP** des pages Rapports et Bannissements ouvrent cette même page. Les liens d’investigation préremplissent l’adresse. Sélectionnez la connexion lorsque plusieurs services ou instances utilisent CrowdSec.

Une investigation regroupe les décisions CrowdSec actuelles, les alertes CrowdSec disponibles, les rapports BunkerWeb conservés et les bannissements locaux de BunkerWeb. Les décisions actuelles et les éléments capturés dans les rapports sont présentés séparément. Les nouveaux rapports CrowdSec conservent les identifiants de décision, origines, scénarios, cibles, mesures de remédiation et dates d’expiration disponibles, même après l’expiration ou la suppression des décisions. Les rejets AppSec et les blocages dus à une politique de gestion des échecs AppSec ont des sources distinctes. L’historique suit les paramètres existants de conservation des rapports ; les anciens rapports et les métadonnées facultatives évincées du cache peuvent ne contenir aucun détail supplémentaire. La consultation des alertes expose des métadonnées d’événement limitées, sans corps de requête brut, cookies ni en-têtes d’authentification.

Les rapports locaux et les bannissements propres à un service sont limités au périmètre de la connexion sélectionnée ; les bannissements globaux de BunkerWeb sont également inclus. Si ce périmètre ne peut plus être établi à partir de la configuration chargée par l’instance, l’investigation s’arrête pour éviter de renvoyer les données d’autres services. Les rapports conservés restent accessibles lorsque l’API locale est indisponible et que la configuration de la connexion est toujours chargée.

La section **Listes d’autorisation CrowdSec** affiche les listes natives du moteur, leurs entrées, commentaires, dates d’expiration et leur mode de gestion, local ou via la Console CrowdSec. Les investigations IP vérifient l’état actuel des listes d’autorisation du moteur et affichent le motif de correspondance. Leur lecture et leur vérification nécessitent les identifiants de gestion décrits ci-dessous. Une vérification indisponible est distinguée d’une IP absente des listes. Ces exceptions s’appliquent à l’ensemble du moteur CrowdSec ; elles ne suppriment pas les bannissements locaux de BunkerWeb. CrowdSec 1.8.0 expose les opérations de lecture et de vérification via la LAPI, tandis que les modifications natives nécessitent `cscli` sur son hôte ou un accès de gestion distinct à la Console.

Le paramètre existant `CROWDSEC_API_KEY` est une **clé de bouncer** : il permet de lire les décisions, mais pas de les supprimer ni de consulter les alertes. Pour activer ces opérations, enregistrez une machine dédiée sur le moteur CrowdSec concerné et configurez ces deux paramètres multisites facultatifs :

- `CROWDSEC_MANAGEMENT_LOGIN` : l’identifiant de la machine dédiée.
- `CROWDSEC_MANAGEMENT_PASSWORD` : le mot de passe de cette machine.

Enregistrez la machine en suivant la [procédure d’authentification à l’API locale](https://doc.crowdsec.net/docs/local_api/authentication/) de CrowdSec. Conservez les identifiants de manière confidentielle. Si l’un des deux paramètres reste vide, la gestion demeure indisponible. La même configuration s’applique aux moteurs intégrés et externes : les requêtes passent par l’instance BunkerWeb sélectionnée, ce qui permet à une API locale intégrée de continuer à écouter sur localhost. Les requêtes HTTPS de gestion vérifient le certificat du serveur avec la configuration de confiance TLS de BunkerWeb, indépendamment du paramètre de vérification AppSec.

L’action **Supprimer la décision CrowdSec** est distincte du débannissement BunkerWeb. Dans l’interface Web, elle nécessite un administrateur disposant d’un accès en écriture, des identifiants de gestion configurés, une base de données de l’interface accessible en écriture et la confirmation de la décision sélectionnée. Supprimer une décision portant sur une plage affecte toute cette plage. Sur un moteur partagé, la suppression affecte aussi les autres bouncers qui consomment cette décision. L’identifiant, la portée, la cible et la mesure de remédiation sélectionnés sont vérifiés de nouveau avant la suppression ; les autres décisions et les bannissements locaux sont conservés.

Une réponse réussie confirme la suppression dans l’API locale et affiche les décisions correspondantes restantes. Les bouncers prennent en compte le changement lors de leur actualisation du flux ou à l’expiration de leur cache en mode live ; l’interface indique que la propagation est en attente, sans affirmer que tous les clients sont déjà autorisés. Une autre décision, un bannissement local, une nouvelle détection ou une règle AppSec peut encore bloquer une requête. Le résultat de chaque suppression est journalisé avec l’acteur authentifié, la connexion et la décision sélectionnées.

L’API publique expose les mêmes opérations :

- `GET /crowdsec` : connexions, état de synchronisation et erreurs par instance.
- `GET /crowdsec/{connection_id}/decisions` : filtrage par `ip`, `origin` ou `scenario` ; pagination avec `offset` et `limit` (200 au maximum).
- `GET /crowdsec/{connection_id}/ips/{ip}` : investigation comprenant jusqu’à 200 décisions, 50 alertes et 50 rapports, avec les totaux ou limites et des sections explicitement signalées comme indisponibles.
- `GET /crowdsec/{connection_id}/alerts/{alert_id}` : détails d’alerte filtrés pour exclure les données sensibles.
- `GET /crowdsec/{connection_id}/allowlists` : listes d’autorisation natives, avec pagination par `offset` et `limit` ; jusqu’à 200 entrées par liste, avec affichage du nombre total d’entrées.
- `GET /crowdsec/{connection_id}/allowlists/check?ip={ip}` : présence actuelle dans une liste d’autorisation native et motif de correspondance.
- `DELETE /crowdsec/{connection_id}/decisions/{decision_id}` : inclure les valeurs sélectionnées de `scope`, `value` et `decision_type` dans le corps JSON.

Utilisez l’identifiant de connexion renvoyé sans le modifier. Il inclut l’identité de l’instance, afin de distinguer les URL localhost identiques sur des instances différentes. Les administrateurs de l’API peuvent utiliser ces opérations. Les utilisateurs délégués de l’API doivent disposer de la permission indépendante `crowdsec_read` ou `crowdsec_delete` sous la ressource existante `bans`, pour un identifiant de connexion renvoyé ou `*`. Une permission ordinaire `ban_delete` n’autorise pas la suppression CrowdSec. Aucune migration de base de données n’est nécessaire.

Le moteur d’exécution conserve les décisions individuelles par cible : en supprimer une ne peut donc pas effacer un autre bannissement sur la même IP ou plage. Les métadonnées facultatives des rapports utilisent un cache distinct de 5 Mio et ne peuvent pas évincer les entrées servant au blocage. Les actualisations du flux utilisent un verrou de processus non bloquant dans `/var/run/bunkerweb`, conservé jusqu’à la publication de la mise à jour et libéré automatiquement si le worker s’arrête.

### Étape&nbsp;1 – Préparer CrowdSec à ingérer les journaux BunkerWeb

=== "Docker"
    **Fichier d'acquisition**

    Vous devrez exécuter une instance de CrowdSec et la configurer pour analyser les journaux de BunkerWeb. Utilisez la valeur dédiée `bunkerweb` pour le paramètre `type` dans votre fichier d'acquisition (en supposant que les journaux de BunkerWeb sont stockés tels quels sans données supplémentaires) :

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    Si la collection n'apparaît pas dans le conteneur CrowdSec, exécutez `docker exec -it <crowdsec-container> cscli hub update`, puis redémarrez ce conteneur (`docker restart <crowdsec-container>`) afin que les nouveaux artefacts soient disponibles. Remplacez `<crowdsec-container>` par le nom de votre conteneur CrowdSec.

    **Composant de sécurité applicative (*optionnel*)**

    CrowdSec fournit également un [Composant de sécurité applicative](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) qui peut être utilisé pour protéger votre application contre les attaques. Si vous souhaitez l'utiliser, vous devez créer un autre fichier d'acquisition pour le composant AppSec :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    Pour les intégrations basées sur des conteneurs, nous recommandons de rediriger les journaux du conteneur BunkerWeb vers un service syslog afin que CrowdSec puisse y accéder facilement. Voici un exemple de configuration pour syslog-ng qui stockera les journaux bruts provenant de BunkerWeb dans un fichier local `/var/log/bunkerweb.log` :

    ```syslog
    @version: 4.10

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    Voici le modèle docker-compose que vous pouvez utiliser (n'oubliez pas de mettre à jour la clé du bouncer) :

    ```yaml
    x-bw-env: &bw-env
      # Nous utilisons une ancre pour éviter de répéter les mêmes paramètres pour les deux services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Assurez-vous de définir la bonne plage IP pour que le planificateur puisse envoyer la configuration à l'instance

    services:
      bunkerweb:
        # C'est le nom qui sera utilisé pour identifier l'instance dans le planificateur
        image: bunkerity/bunkerweb:1.6.15-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Pour le support QUIC / HTTP3
        environment:
          <<: *bw-env # Nous utilisons l'ancre pour éviter de répéter les mêmes paramètres pour tous les services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog # Envoyer les journaux à syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # L'adresse IP du service syslog

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.15-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Assurez-vous de définir le nom correct de l'instance
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # N'oubliez pas de définir un mot de passe plus fort pour la base de données
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # C'est l'adresse de l'API du conteneur CrowdSec dans le même réseau
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # Commentez si vous ne voulez pas utiliser le composant AppSec
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # N'oubliez pas de définir une clé plus forte pour le bouncer
        volumes:
          - bw-storage:/data # Ceci est utilisé pour persister le cache et d'autres données comme les sauvegardes
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Nous définissons la taille maximale des paquets autorisés pour éviter les problèmes avec les grosses requêtes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # N'oubliez pas de définir un mot de passe plus fort pour la base de données
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      crowdsec:
        image: crowdsecurity/crowdsec:v1.8.0 # Utilisez la dernière version mais épinglez toujours la version pour une meilleure stabilité/sécurité
        volumes:
          - cs-data:/var/lib/crowdsec/data # Pour persister les données de CrowdSec
          - bw-logs:/var/log:ro # Les journaux de BunkerWeb à analyser par CrowdSec
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # Le fichier d'acquisition pour les journaux de BunkerWeb
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Commentez si vous ne voulez pas utiliser le composant AppSec
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # N'oubliez pas de définir une clé plus forte pour le bouncer
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # Si vous ne voulez pas utiliser le composant AppSec, utilisez plutôt cette ligne
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # Lier aux ports bas
          - NET_BROADCAST  # Envoyer des diffusions
          - NET_RAW  # Utiliser des sockets brutes
          - DAC_READ_SEARCH  # Lire les fichiers en contournant les autorisations
          - DAC_OVERRIDE  # Outrepasser les autorisations de fichiers
          - CHOWN  # Changer le propriétaire
          - SYSLOG  # Écrire dans les journaux système
        volumes:
          - bw-logs:/var/log/bunkerweb # C'est le volume utilisé pour stocker les journaux
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # C'est le fichier de configuration de syslog-ng
        networks:
            bw-universe:
              ipv4_address: 10.20.30.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Assurez-vous de définir la bonne plage IP pour que le planificateur puisse envoyer la configuration à l'instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Linux"

    Vous devez installer CrowdSec et le configurer pour analyser les journaux de BunkerWeb. Suivez la [documentation officielle](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    Pour permettre à CrowdSec d'analyser les journaux de BunkerWeb, ajoutez les lignes suivantes à votre fichier d'acquisition situé à `/etc/crowdsec/acquis.yaml` :

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    Mettez à jour le hub CrowdSec et installez la collection BunkerWeb :

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    Maintenant, ajoutez votre bouncer personnalisé à l'API CrowdSec en utilisant l'outil `cscli` :

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "Clé API"
        Conservez la clé générée par la commande `cscli` ; vous en aurez besoin plus tard.

    Ensuite, redémarrez le service CrowdSec :

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Composant de sécurité applicative (*optionnel*)**

    Si vous souhaitez utiliser le composant AppSec, vous devez créer un autre fichier d'acquisition pour celui-ci, situé à `/etc/crowdsec/acquis.d/appsec.yaml` :

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    Vous devrez également installer les collections du composant AppSec :

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Enfin, redémarrez le service CrowdSec :

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Paramètres**

    Configurez le plugin en ajoutant les paramètres suivants à votre fichier de configuration BunkerWeb :

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<La clé fournie par cscli>
    # Commentez si vous ne voulez pas utiliser le composant AppSec
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    Enfin, rechargez le service BunkerWeb :

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "All-in-one"

    L'image Docker BunkerWeb All-In-One (AIO) est livrée avec CrowdSec entièrement intégré. Vous n'avez pas besoin de configurer une instance CrowdSec séparée ou de configurer manuellement les fichiers d'acquisition pour les journaux de BunkerWeb lorsque vous utilisez l'agent CrowdSec interne.

    Référez-vous à la [documentation d'intégration de l'image All-In-One (AIO)](integrations.md#crowdsec-integration).

### Étape&nbsp;2 – Configurer les paramètres de BunkerWeb

Appliquez les variables d’environnement suivantes (ou leurs équivalents via le scheduler) pour permettre à votre instance BunkerWeb de communiquer avec l’API locale CrowdSec. Au minimum, `USE_CROWDSEC`, `CROWDSEC_API` et `CROWDSEC_API_KEY` avec une clé valide générée via `cscli bouncers add` sont nécessaires.

| Paramètre                   | Valeur par défaut      | Contexte  | Multiple | Description                                                                                                                                    |
| --------------------------- | ---------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Activer CrowdSec :** Mettre à `yes` pour activer le bouncer CrowdSec.                                                                        |
| `CROWDSEC_API`              | `http://crowdsec:8080` | multisite    | no       | **URL de l'API CrowdSec :** L'adresse du service de l'API locale de CrowdSec.                                                                  |
| `CROWDSEC_API_KEY`          |                        | multisite    | no       | **Clé API CrowdSec :** La clé API pour s'authentifier auprès de l'API CrowdSec, obtenue avec `cscli bouncers add`.                             |
| `CROWDSEC_MODE`             | `live`                 | multisite    | no       | **Mode de fonctionnement :** Soit `live` (interroge l'API pour chaque requête) ou `stream` (met en cache périodiquement toutes les décisions). |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | multisite    | no       | **Trafic interne :** Mettre à `yes` pour vérifier le trafic interne par rapport aux décisions de CrowdSec.                                     |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | multisite    | no       | **Délai d'attente de la requête :** Délai d'attente en millisecondes pour les requêtes HTTP vers l'API locale de CrowdSec en mode live.        |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | multisite    | no       | **Emplacements exclus :** Liste d'emplacements (URI) séparés par des virgules à exclure des vérifications de CrowdSec.                         |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | multisite    | no       | **Expiration du cache :** Le temps d'expiration du cache en secondes pour les décisions IP en mode live.                                       |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | multisite    | no       | **Fréquence de mise à jour :** À quelle fréquence (en secondes) récupérer les décisions nouvelles/expirées de l'API CrowdSec en mode stream.   |

#### Paramètres du composant de sécurité applicative

| Paramètre                         | Valeur par défaut | Contexte | Multiple | Description                                                                                                                      |
| --------------------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |                   | multisite   | no       | **URL AppSec :** L'URL du composant de sécurité applicative de CrowdSec. Laisser vide pour désactiver AppSec.                    |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough`     | multisite   | no       | **Action en cas d'échec :** Action à entreprendre lorsque AppSec renvoie une erreur. Peut être `passthrough` ou `deny`.          |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`             | multisite   | no       | **Délai de connexion :** Le délai d'attente en millisecondes pour se connecter au composant AppSec.                              |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`             | multisite   | no       | **Délai d'envoi :** Le délai d'attente en millisecondes pour envoyer des données au composant AppSec.                            |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`             | multisite   | no       | **Délai de traitement :** Le délai d'attente en millisecondes pour traiter la requête dans le composant AppSec.                  |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`              | multisite   | no       | **Toujours envoyer :** Mettre à `yes` pour toujours envoyer les requêtes à AppSec, même s'il y a une décision au niveau de l'IP. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`              | multisite   | no       | **Vérification SSL :** Mettre à `yes` pour vérifier le certificat SSL du composant AppSec.                                       |

!!! info "À propos des modes de fonctionnement"
    - Le **mode Live** interroge l'API CrowdSec pour chaque requête entrante, offrant une protection en temps réel au prix d'une latence plus élevée.
    - Le **mode Stream** télécharge périodiquement toutes les décisions de l'API CrowdSec et les met en cache localement, réduisant la latence avec un léger retard dans l'application des nouvelles décisions.

#### Points de terminaison par service

Comme les points de terminaison sont `multisite`, les services d'une même instance peuvent utiliser des composants CrowdSec différents, ou seulement certains d'entre eux. Les deux fonctionnalités sont indépendantes :

- Les **recherches de décisions** sont actives lorsque `CROWDSEC_API` est défini. Définissez-le sur une chaîne vide pour qu'un service ignore entièrement la Local API.
- L'**inspection AppSec** est active lorsque `CROWDSEC_APPSEC_URL` est défini. Définissez-le sur une chaîne vide pour qu'un service ignore l'inspection approfondie des requêtes.

Un service avec `USE_CROWDSEC` à `yes` et les deux URL vides ne vérifie rien, et l'instance consigne qu'aucun point de terminaison n'est défini.

!!! warning "Un cache de décisions par instance"
    Les décisions mises en cache résident dans une seule zone de mémoire partagée pour toute l'instance, indexée par la Local API dont elles proviennent. Les services pointant vers la même `CROWDSEC_API` réutilisent les décisions mises en cache les uns des autres, ce qui garde la recherche peu coûteuse. Les services pointant vers des Local API différentes ne voient jamais les décisions les unes des autres. Le dimensionnement de cette zone est à l'échelle de l'instance, donc une flotte avec de nombreuses Local API distinctes et de longues listes de décisions partage un même budget.

!!! info "Clé de bouncer par Local API"
    `CROWDSEC_API_KEY` est résolu par service comme tout autre paramètre. Lorsque des services ciblent des Local API différentes, attribuez à chacun la clé enregistrée avec `cscli bouncers add` sur son propre hôte CrowdSec, sinon les recherches sont rejetées comme non authentifiées.

### Exemples de configurations

=== "Configuration de base"

    C'est une configuration simple pour lorsque CrowdSec s'exécute sur le même hôte :

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "live"
    ```

=== "Configuration avancée avec AppSec"

    Une configuration plus complète incluant le composant de sécurité applicative :

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # Configuration AppSec
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

=== "Configuration par service"

    AppSec sur chaque service public, recherches de décisions sur un sous-ensemble, et un service entièrement exclu. Les valeurs sans préfixe constituent la base commune à toute la flotte, et chaque service ne surcharge que ce qui diffère :

    ```yaml
    MULTISITE: "yes"
    SERVER_NAME: "app1.example.com app2.example.com intranet.example.com"

    # Base commune pour chaque service
    USE_CROWDSEC: "yes"
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_API: "" # Pas de recherche de décisions sauf si un service en fait la demande
    CROWDSEC_API_KEY: ""

    # app1 ajoute la recherche de décisions de la Local API en plus d'AppSec
    app1.example.com_CROWDSEC_API: "http://crowdsec:8080"
    app1.example.com_CROWDSEC_API_KEY: "your-api-key-here"

    # app2 conserve uniquement AppSec, héritant de la base CROWDSEC_API vide

    # intranet n'est pas vérifié du tout
    intranet.example.com_USE_CROWDSEC: "no"
    ```

    Un service peut aussi pointer vers un hôte CrowdSec entièrement différent, avec sa propre clé de bouncer :

    ```yaml
    app2.example.com_CROWDSEC_API: "http://crowdsec-dmz:8080"
    app2.example.com_CROWDSEC_API_KEY: "dmz-bouncer-key"
    app2.example.com_CROWDSEC_APPSEC_URL: "http://crowdsec-dmz:7422"
    ```

### Étape&nbsp;3 – Valider l’intégration

- Dans les journaux du planificateur, recherchez les entrées `CrowdSec configuration successfully generated` et `CrowdSec bouncer denied request` afin de vérifier que le plugin est actif.
- Côté CrowdSec, surveillez `cscli metrics show` ou la console CrowdSec pour vous assurer que les décisions BunkerWeb apparaissent comme prévu.
- Dans l’interface BunkerWeb, ouvrez la page du plugin CrowdSec pour voir l’état de l’intégration.
