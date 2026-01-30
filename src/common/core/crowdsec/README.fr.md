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

### Parcours d’intégration

1. Préparer l’agent CrowdSec pour ingérer les journaux BunkerWeb.
2. Configurer BunkerWeb pour interroger l’API locale CrowdSec.
3. Valider le lien via l’API `/crowdsec/ping` ou la carte CrowdSec dans l’interface d’administration.

Les sections suivantes détaillent chacune de ces étapes.

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
        image: bunkerity/bunkerweb:1.6.8-rc3
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
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
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
        image: crowdsecurity/crowdsec:v1.7.4 # Utilisez la dernière version mais épinglez toujours la version pour une meilleure stabilité/sécurité
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

Appliquez les variables d’environnement suivantes (ou leurs équivalents via le scheduler) pour permettre à votre instance BunkerWeb de communiquer avec l’API locale CrowdSec. Au minimum, `USE_CROWDSEC`, `CROWDSEC_API` et une clé valide générée avec `cscli bouncers add` sont nécessaires.

| Paramètre                   | Valeur par défaut      | Contexte  | Multiple | Description                                                                                                                                    |
| --------------------------- | ---------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Activer CrowdSec :** Mettre à `yes` pour activer le bouncer CrowdSec.                                                                        |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | no       | **URL de l'API CrowdSec :** L'adresse du service de l'API locale de CrowdSec.                                                                  |
| `CROWDSEC_API_KEY`          |                        | global    | no       | **Clé API CrowdSec :** La clé API pour s'authentifier auprès de l'API CrowdSec, obtenue avec `cscli bouncers add`.                             |
| `CROWDSEC_MODE`             | `live`                 | global    | no       | **Mode de fonctionnement :** Soit `live` (interroge l'API pour chaque requête) ou `stream` (met en cache périodiquement toutes les décisions). |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | no       | **Trafic interne :** Mettre à `yes` pour vérifier le trafic interne par rapport aux décisions de CrowdSec.                                     |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | no       | **Délai d'attente de la requête :** Délai d'attente en millisecondes pour les requêtes HTTP vers l'API locale de CrowdSec en mode live.        |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | no       | **Emplacements exclus :** Liste d'emplacements (URI) séparés par des virgules à exclure des vérifications de CrowdSec.                         |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | no       | **Expiration du cache :** Le temps d'expiration du cache en secondes pour les décisions IP en mode live.                                       |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | no       | **Fréquence de mise à jour :** À quelle fréquence (en secondes) récupérer les décisions nouvelles/expirées de l'API CrowdSec en mode stream.   |

#### Paramètres du composant de sécurité applicative

| Paramètre                         | Valeur par défaut | Contexte | Multiple | Description                                                                                                                      |
| --------------------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |                   | global   | no       | **URL AppSec :** L'URL du composant de sécurité applicative de CrowdSec. Laisser vide pour désactiver AppSec.                    |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough`     | global   | no       | **Action en cas d'échec :** Action à entreprendre lorsque AppSec renvoie une erreur. Peut être `passthrough` ou `deny`.          |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`             | global   | no       | **Délai de connexion :** Le délai d'attente en millisecondes pour se connecter au composant AppSec.                              |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`             | global   | no       | **Délai d'envoi :** Le délai d'attente en millisecondes pour envoyer des données au composant AppSec.                            |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`             | global   | no       | **Délai de traitement :** Le délai d'attente en millisecondes pour traiter la requête dans le composant AppSec.                  |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`              | global   | no       | **Toujours envoyer :** Mettre à `yes` pour toujours envoyer les requêtes à AppSec, même s'il y a une décision au niveau de l'IP. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`              | global   | no       | **Vérification SSL :** Mettre à `yes` pour vérifier le certificat SSL du composant AppSec.                                       |

!!! info "À propos des modes de fonctionnement" - Le **mode Live** interroge l'API CrowdSec pour chaque requête entrante, offrant une protection en temps réel au prix d'une latence plus élevée. - Le **mode Stream** télécharge périodiquement toutes les décisions de l'API CrowdSec et les met en cache localement, réduisant la latence avec un léger retard dans l'application des nouvelles décisions.

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

### Étape&nbsp;3 – Valider l’intégration

- Dans les journaux du planificateur, recherchez les entrées `CrowdSec configuration successfully generated` et `CrowdSec bouncer denied request` afin de vérifier que le plugin est actif.
- Côté CrowdSec, surveillez `cscli metrics show` ou la console CrowdSec pour vous assurer que les décisions BunkerWeb apparaissent comme prévu.
- Dans l’interface BunkerWeb, ouvrez la page du plugin CrowdSec pour voir l’état de l’intégration.
