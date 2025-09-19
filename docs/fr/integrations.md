# Intégrations

## BunkerWeb Cloud

<figure markdown>
  ![Vue d'ensemble](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

BunkerWeb Cloud sera le moyen le plus simple de commencer avec BunkerWeb. Il vous offre un service BunkerWeb entièrement géré sans tracas. Considérez-le comme un BunkerWeb-as-a-Service !

Essayez notre [offre BunkerWeb Cloud](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc) et accédez à :

- Une instance BunkerWeb entièrement gérée et hébergée dans notre cloud
- Toutes les fonctionnalités de BunkerWeb, y compris les fonctionnalités PRO
- Une plateforme de surveillance avec tableaux de bord et alertes
- Support technique pour vous aider dans la configuration

Si vous êtes intéressé par l'offre BunkerWeb Cloud, n'hésitez pas à [nous contacter](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc) afin que nous puissions discuter de vos besoins.

## Image tout-en-un (AIO)

<figure markdown>
  ![Architecture AIO Graph Placeholder](assets/img/aio-graph-placeholder.png){ align=center, width="600" }
  <figcaption>Architecture tout-en-un (AIO) BunkerWeb</figcaption>
</figure>

### Déploiement

Pour déployer le conteneur tout-en-un, il vous suffit d'exécuter la commande suivante :

```shell
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5-rc4
```

Par défaut, le conteneur expose :

- 8080/tcp pour HTTP
- 8443/tcp pour HTTPS
- 8443/udp pour QUIC
- 7000/tcp pour l'accès à l'interface utilisateur web sans BunkerWeb en façade (non recommandé pour la production)

L'image tout-en-un est livrée avec plusieurs services intégrés, qui peuvent être contrôlés à l'aide de variables d'environnement :

- `SERVICE_UI=yes` (par défaut) - Active le service d'interface utilisateur Web
- `SERVICE_SCHEDULER=yes` (par défaut) - Active le service Scheduler
- `AUTOCONF_MODE=no` (par défaut) - Active le service autoconf
- `USE_REDIS=yes` (par défaut) : active l' [ instance](#redis-integration) Redis intégrée
- `USE_CROWDSEC=no` (par défaut) - [ L'intégration CrowdSec](#crowdsec-integration) est désactivée par défaut

### Accès à l'assistant d'installation

Par défaut, l'assistant d'installation est lancé automatiquement lorsque vous exécutez le conteneur AIO pour la première fois. Pour y accéder, procédez comme suit :

1. **Démarrez le conteneur AIO** comme [ci-dessus](#deployment), en vous assurant ( `SERVICE_UI=yes` par défaut).
2. **Accédez à l'interface utilisateur** via votre point de terminaison BunkerWeb principal, par exemple `https://your-domain`.

> Suivez les étapes suivantes du guide de [démarrage rapide](quickstart-guide.md#complete-the-setup-wizard) pour configurer l'interface utilisateur Web.

### Intégration Redis

L'image **BunkerWeb All-In-One** inclut Redis prêt à l'emploi pour la [persistance des bannissements et des rapports](advanced.md#persistence-of-bans-and-reports). Pour gérer Redis :

- Pour désactiver Redis, définissez `USE_REDIS=no` ou pointez `REDIS_HOST` vers un hôte externe.
- Les journaux Redis apparaissent `[REDIS]` avec le préfixe dans les journaux Docker et `/var/log/bunkerweb/redis.log`.

### Intégration CrowdSec

L'image Docker tout-en-un** de BunkerWeb ** est livrée avec CrowdSec entièrement intégré, sans conteneurs supplémentaires ni configuration manuelle requise. Suivez les étapes ci-dessous pour activer, configurer et étendre CrowdSec dans votre déploiement.

Par défaut, CrowdSec est **désactivé**. Pour l'activer, il suffit d'ajouter la `USE_CROWDSEC` variable d'environnement :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5-rc4
```

* Lorsque `USE_CROWDSEC=yes`, le point d'entrée :

    1. **Inscrivez-vous** et **démarrez** l'agent CrowdSec local (via `cscli`).
    2. **Installez ou mettez à niveau** les collections et les analyseurs par défaut.
    3. **Configurez** le `crowdsec-bunkerweb-bouncer/v1.6` videur.

---

#### Collections et analyseurs par défaut

Au premier démarrage (ou après la mise à niveau), les ressources suivantes sont automatiquement installées et maintenues à jour :

| Type           | Nom                                     | But                                                                                                                                                                                                                                                                                                 |
| -------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Collection** | `crowdsecurity/nginx`                   | Protégez les serveurs Nginx contre un large éventail d'attaques basées sur HTTP, de la force brute aux tentatives d'injection.                                                                                                                                                                      |
| **Collection** | `crowdsecurity/appsec-virtual-patching` | Fournit un ensemble de règles de type WAF mis à jour dynamiquement ciblant les CVE connues, automatiquement corrigé quotidiennement pour protéger les applications Web contre les vulnérabilités nouvellement découvertes.                                                                          |
| **Collection** | `crowdsecurity/appsec-generic-rules`    | Compléments `crowdsecurity/appsec-virtual-patching` avec des heuristiques pour les modèles d'attaque génériques de la couche application, tels que l'énumération, la traversée de chemin et les sondes automatisées, comblant les lacunes là où il n'existe pas encore de règles spécifiques à CVE. |
| **Analyseur**  | `crowdsecurity/geoip-enrich`            | Enrichit les événements avec le contexte GeoIP                                                                                                                                                                                                                                                      |

<details>
<summary><strong>Comment ça marche en interne</strong></summary>

Le script entrypoint appelle :

```bash
cscli install collection crowdsecurity/nginx
cscli install collection crowdsecurity/appsec-virtual-patching
cscli install collection crowdsecurity/appsec-generic-rules
cscli install parser     crowdsecurity/geoip-enrich
```

</details>

---

#### Ajouter des collections supplémentaires

Vous avez besoin d'une couverture supplémentaire ? Définissez `CROWDSEC_EXTRA_COLLECTIONS` à l'aide d'une liste de collections Hubb séparées par des espaces :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/apache2 crowdsecurity/mysql" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5-rc4
```

!!! info "Comment ça marche en interne"
    Le script parcourt chaque nom et installe ou met à jour si nécessaire — aucune intervention manuelle n'est requise.

---

#### Désactiver des analyseurs spécifiques

Si vous souhaitez conserver la configuration par défaut tout en désactivant explicitement un ou plusieurs analyseurs, fournissez une liste séparée par des espaces via `CROWDSEC_DISABLED_PARSERS` :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_DISABLED_PARSERS="crowdsecurity/geoip-enrich foo/bar-parser" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5-rc4
```

Notes :
- La liste est appliquée après l'installation/mise à jour des éléments requis ; seuls les analyseurs indiqués sont supprimés.
- Utilisez les slugs du hub tels qu'affichés par `cscli parsers list` (ex. : `crowdsecurity/geoip-enrich`).

---

#### Basculement AppSec

Les  fonctionnalités [CrowdSec AppSec](https://docs.crowdsec.net/docs/appsec/intro/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs), optimisées par les  collections `appsec-virtual-patching` et `appsec-generic-rules` , sont **activées par défaut**.

Pour **désactiver** toutes les fonctionnalités AppSec (WAF/virtual-patching), définissez :

```bash
-e CROWDSEC_APPSEC_URL=""
```

Cela désactive effectivement le point de terminaison AppSec, de sorte qu'aucune règle n'est appliquée.

---

#### API CrowdSec externe

Si vous exploitez une instance CrowdSec distante, pointez le conteneur vers votre API :

```bash
docker run -d \
  --name bunkerweb-aio \
  -v bw-storage:/data \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_API="https://crowdsec.example.com:8000" \
  -p 80:8080/tcp \
  -p 443:8443/tcp \
  -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5-rc4
```

* **L'enregistrement local** est ignoré lorsque n' `CROWDSEC_API` est pas `127.0.0.1` ou `localhost`.
* **AppSec** est désactivé par défaut lors de l'utilisation d'une API externe. Pour l'activer, définissez-le `CROWDSEC_APPSEC_URL` sur le point de terminaison de votre choix.
* L'inscription du videur se produit toujours sur l'API distante.
* Pour réutiliser une clé de videur existante, fournissez-la `CROWDSEC_API_KEY` avec votre jeton pré-généré.

---

!!! tip "Plus d'options"
    Pour une couverture complète de toutes les options CrowdSec (scénarios personnalisés, journaux, dépannage, etc.), consultez la [documentation du plugin BunkerWeb CrowdSec](features.md#crowdsec) ou visitez le [site officiel de CrowdSec](https://www.crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs).

## Docker

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-docker.svg){ align=center, width="600" }
  <figcaption>Intégration Docker</figcaption>
</figure>

L'utilisation de BunkerWeb en tant que [ conteneur Docker](https://www.docker.com/) offre une approche pratique et simple pour tester et utiliser la solution, en particulier si vous êtes déjà familiarisé avec la technologie Docker.

Pour faciliter votre déploiement Docker, nous fournissons des images prédéfinies facilement disponibles sur [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb), prenant en charge plusieurs architectures. Ces images prédéfinies sont optimisées et préparées pour être utilisées sur les architectures suivantes :

- x64 (64 bits)
- x86
- armv8 (ARM 64 bits)
- armv7 (ARM 32 bits)

En accédant à ces images prédéfinies à partir de Docker Hub, vous pouvez rapidement extraire et exécuter BunkerWeb dans votre environnement Docker, éliminant ainsi le besoin de processus de configuration ou d'installation étendus. Cette approche simplifiée vous permet de vous concentrer sur l'exploitation des capacités de BunkerWeb sans complexités inutiles.

Que vous effectuiez des tests, développiez des applications ou déployiez BunkerWeb en production, l'option de conteneurisation Docker offre flexibilité et facilité d'utilisation. L'adoption de cette méthode vous permet de tirer pleinement parti des fonctionnalités de BunkerWeb tout en tirant parti des avantages de la technologie Docker.

```shell
docker pull bunkerity/bunkerweb:1.6.5-rc4
```

Les images Docker sont également disponibles sur [les packages GitHub](https://github.com/orgs/bunkerity/packages?repo_name=bunkerweb) et peuvent être téléchargées à l'aide de l'adresse du `ghcr.io` dépôt :

```shell
docker pull ghcr.io/bunkerity/bunkerweb:1.6.5-rc4
```

Les concepts clés de l'intégration Docker sont les suivants :

- **Variables d'environnement**: Configurez facilement BunkerWeb à l'aide de variables d'environnement. Ces variables vous permettent de personnaliser divers aspects du comportement de BunkerWeb, tels que les paramètres réseau, les options de sécurité et d'autres paramètres.
- **Conteneur du Scheduler** : gérez la configuration et exécutez les tâches à l'aide d'un conteneur dédié appelé [Scheduler](concepts.md#scheduler).
- **Réseaux**: Les réseaux Docker jouent un rôle essentiel dans l'intégration de BunkerWeb. Ces réseaux ont deux objectifs principaux : exposer les ports aux clients et se connecter aux services Web en amont. En exposant les ports, BunkerWeb peut accepter les demandes entrantes des clients, leur permettant d'accéder aux services Web protégés. De plus, en se connectant aux services Web en amont, BunkerWeb peut acheminer et gérer efficacement le trafic, offrant ainsi une sécurité et des performances améliorées.

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez SQLite comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, d'autres backends de base de données sont également pris en charge. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc4/misc/integrations) du dépôt.

### Variables d'environnement

Les paramètres sont transmis au Scheduler à l'aide de variables d'environnement Docker :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
    environment:
      - MY_SETTING=value
      - ANOTHER_SETTING=another value
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
...
```

!!! info "Liste complète"
    Pour obtenir la liste complète des variables d'environnement, consultez la [section des paramètres](features.md) de la documentation.

### Utilisation des secrets Docker

Au lieu de transmettre des paramètres sensibles via des variables d'environnement, vous pouvez les stocker en tant que secrets Docker. Pour chaque paramètre que vous souhaitez sécuriser, créez un secret Docker dont le nom correspond à la clé de paramètre (en majuscules). Les scripts d'entrée de BunkerWeb chargent automatiquement les secrets `/run/secrets` et les exportent en tant que variables d'environnement.

Exemple:
```bash
# Create a Docker secret for ADMIN_PASSWORD
echo "S3cr3tP@ssw0rd" | docker secret create ADMIN_PASSWORD -
```

Montez les secrets lors du déploiement :
```yaml
services:
  bw-ui:
    secrets:
      - ADMIN_PASSWORD
...
secrets:
  ADMIN_PASSWORD:
    external: true
```

Cela garantit que les paramètres sensibles sont tenus à l'écart de l'environnement et des journaux.

### Programmateur

Le [Scheduler](concepts.md#scheduler) s'exécute dans son propre conteneur, qui est également disponible sur Docker Hub :

```shell
docker pull bunkerity/bunkerweb-scheduler:1.6.5-rc4
```

!!! info "Paramètres BunkerWeb"

    Since version `1.6.0`, the Scheduler container is where you define the settings for BunkerWeb. The Scheduler then pushes the configuration to the BunkerWeb container.

    ⚠ **Important**: Tous les paramètres liés à l'API (comme `API_HTTP_PORT`, `API_LISTEN_IP`, `API_SERVER_NAME`, `API_WHITELIST_IP`, et `API_TOKEN` si vous l'utilisez) **doivent également être définis dans le conteneur BunkerWeb**. Les paramètres doivent être répliqués dans les deux conteneurs, sinon le conteneur BunkerWeb n'acceptera pas les requêtes API du Scheduler.

    ```yaml
    x-bw-api-env: &bw-api-env
      # We use an anchor to avoid repeating the same settings for both containers
      API_HTTP_PORT: "5000" # Default value
      API_LISTEN_IP: "0.0.0.0" # Default value
      API_SERVER_NAME: "bwapi" # Default value
      API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24" # Set this according to your network settings
      # Jeton optionnel ; si défini, le Scheduler enverra Authorization: Bearer <token>
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc4
        environment:
          # This will set the API settings for the BunkerWeb container
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
        environment:
          # This will set the API settings for the Scheduler container
          <<: *bw-api-env
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like backups
        restart: "unless-stopped"
        networks:
          - bw-universe
    ...
    ```

Un volume est nécessaire pour stocker la base de données SQLite et les sauvegardes utilisées par le Scheduler :

```yaml
...
services:
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
    volumes:
      - bw-storage:/data
...
volumes:
  bw-storage:
```

!!! warning "Utilisation d'un dossier local pour les données persistantes"
    Le Scheduler s'exécute en tant qu' **utilisateur non privilégié avec UID 101 et GID 101** à l'intérieur du conteneur. Cela renforce la sécurité : en cas d'exploitation d'une vulnérabilité, l'attaquant ne disposera pas des privilèges de root complet (UID/GID 0).

    However, if you use a **local folder for persistent data**, you must **set the correct permissions** so the unprivileged user can write data to it. For example:

    ```shell
    mkdir bw-data && \
    chown root:101 bw-data && \
    chmod 770 bw-data
    ```

    Alternatively, if the folder already exists:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    If you are using [Docker in rootless mode](https://docs.docker.com/engine/security/rootless) or [Podman](https://podman.io/), UIDs and GIDs in the container will be mapped to different ones on the host. You will first need to check your initial subuid and subgid:

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    For example, if you have a value of **100000**, the mapped UID/GID will be **100100** (100000 + 100):

    ```shell
    mkdir bw-data && \
    sudo chgrp 100100 bw-data && \
    chmod 770 bw-data
    ```

    Or if the folder already exists:

    ```shell
    sudo chgrp -R 100100 bw-data && \
    sudo chmod -R 770 bw-data
    ```

### Réseau

Par défaut, le conteneur BunkerWeb écoute (à l'intérieur du conteneur) les **fichiers 8080/tcp** pour **HTTP,** **8443/tcp** pour **HTTPS** et **8443/udp** pour **QUIC**.

!! avertissement "Ports privilégiés en mode rootless ou lors de l'utilisation de Podman"
    Si vous utilisez [Docker en mode rootless](https://docs.docker.com/engine/security/rootless) et que vous souhaitez rediriger les ports privilégiés (< 1024) tels que 80 et 443 vers BunkerWeb, veuillez vous référer aux prérequis [ici](https://docs.docker.com/engine/security/rootless/#exposing-privileged-ports).

    If you are using [Podman](https://podman.io/), you can lower the minimum number for unprivileged ports:
    ```shell
    sudo sysctl net.ipv4.ip_unprivileged_port_start=1
    ```

La pile BunkerWeb typique lors de l'utilisation de l'intégration Docker contient les conteneurs suivants :

- BunkerWeb (en anglais)
- Programmateur
- Vos services

À des fins de défense en profondeur, nous vous recommandons vivement de créer au moins trois réseaux Docker différents :

- `bw-services`: pour BunkerWeb et vos services web
- `bw-universe`: pour BunkerWeb et le Scheduler
- `bw-db`: pour la base de données (si vous en utilisez une)

Pour sécuriser la communication entre le Scheduler et l'API BunkerWeb, **autorisez les appels d'API**. Utilisez le paramètre `API_WHITELIST_IP` pour spécifier les adresses IP et sous-réseaux autorisés. Pour un niveau de protection supérieur, définissez `API_TOKEN` dans les deux conteneurs ; le Scheduler inclura automatiquement l'en-tête `Authorization: Bearer <token>`.

**Il est fortement recommandé d'utiliser un sous-réseau statique pour le `bw-universe` réseau** afin d'améliorer la sécurité. En mettant en œuvre ces mesures, vous pouvez vous assurer que seules les sources autorisées peuvent accéder à l'API BunkerWeb, réduisant ainsi le risque d'accès non autorisé ou d'activités malveillantes :

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  API_TOKEN: "" # Jeton API optionnel
  # Jeton API optionnel pour l'accès authentifié à l'API
  API_TOKEN: ""

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.5-rc4
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-services
      - bw-universe
...
  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
...
volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # Static subnet so only authorized sources can access the BunkerWeb API
  bw-services:
    name: bw-services
```

### Fichier de composition complet

```yaml
x-bw-api-env: &bw-api-env
  # We use an anchor to avoid repeating the same settings for both containers
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.5-rc4
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    environment:
      <<: *bw-api-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
    depends_on:
      - bunkerweb
    environment:
      <<: *bw-api-env
      BUNKERWEB_INSTANCES: "bunkerweb" # This setting is mandatory to specify the BunkerWeb instance
      SERVER_NAME: "www.example.com"
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe

volumes:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24 # Static subnet so only authorized sources can access the BunkerWeb API
  bw-services:
    name: bw-services
```

### Construire à partir de la source

Sinon, si vous préférez une approche plus pratique, vous avez la possibilité de créer l'image Docker directement à partir de la [source](https://github.com/bunkerity/bunkerweb). La création de l'image à partir de la source vous offre un meilleur contrôle et une meilleure personnalisation du processus de déploiement. Cependant, veuillez noter que cette méthode peut prendre un certain temps, en fonction de votre configuration matérielle (vous pouvez prendre un café ☕ si nécessaire).

```shell
git clone https://github.com/bunkerity/bunkerweb.git && \
cd bunkerweb && \
docker build -t bw -f src/bw/Dockerfile . && \
docker build -t bw-scheduler -f src/scheduler/Dockerfile . && \
docker build -t bw-autoconf -f src/autoconf/Dockerfile . && \
docker build -t bw-ui -f src/ui/Dockerfile .
```

## Linux

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-linux.svg){ align=center, width="600" }
  <figcaption>Intégration Linux</figcaption>
</figure>

Les distributions Linux prises en charge par BunkerWeb (architectures amd64/x86_64 et arm64/aarch64) comprennent :

- Debian 12 "Rat de bibliothèque"
- Debian 13 "Trixie"
- Ubuntu 22.04 "Jammy"
- Ubuntu 24.04 "Noble"
- Fedora 41 et 42
- Red Hat Enterprise Linux (RHEL) 8, 9 et 10

### Script d'installation facile

Pour une expérience d'installation simplifiée, BunkerWeb fournit un script d'installation facile qui gère automatiquement l'ensemble du processus d'installation, y compris l'installation de NGINX, la configuration du référentiel et la configuration du service.

#### Démarrage rapide

Pour commencer, téléchargez le script d'installation et sa somme de contrôle, puis vérifiez l'intégrité du script avant de l'exécuter.

```bash
# Download the script and its checksum
wget https://github.com/bunkerity/bunkerweb/releases/download/v1.6.5-rc4/install-bunkerweb.sh
wget https://github.com/bunkerity/bunkerweb/releases/download/v1.6.5-rc4/install-bunkerweb.sh.sha256

# Verify the checksum
sha256sum -c install-bunkerweb.sh.sha256

# If the check is successful, run the script
chmod +x install-bunkerweb.sh
sudo ./install-bunkerweb.sh
```

!!! danger "Avis de sécurité"
    **Vérifiez toujours l'intégrité du script d'installation avant de l'exécuter.**

    Téléchargez le fichier de somme de contrôle et utilisez un outil comme `sha256sum` pour confirmer que le script n'a pas été modifié ou altéré.

    Si la vérification de la somme de contrôle échoue, **n'exécutez pas le script** — il pourrait être dangereux.

#### Comment ça marche

Le script d'installation facile est un outil puissant conçu pour rationaliser l'installation de BunkerWeb sur un nouveau système Linux. Il automatise les étapes clés suivantes :

1.  **Analyse du système**: détecte votre système d'exploitation et le compare à la liste des distributions prises en charge.
2.  **Personnalisation de l'installation**: en mode interactif, il vous invite à choisir un type d'installation (Tout en un, Manager, Worker, etc.) et à décider d'activer ou non l'assistant de configuration Web.
3.  **Intégrations facultatives**: propose d'installer et de configurer automatiquement le [moteur de sécurité CrowdSec](#crowdsec-integration-with-the-script).
4.  **Gestion des **dépendances : Installe la version correcte de NGINX requise par BunkerWeb à partir de sources officielles et verrouille la version pour éviter les mises à niveau involontaires.
5.  **Installation de BunkerWeb**: Ajoute le référentiel de paquets BunkerWeb, installe les paquets nécessaires et verrouille la version.
6.  **Configuration du service** : Configure et active les `systemd` services correspondant au type d'installation que vous avez choisi.
7.  **Conseils post-installation**: Fournit des étapes suivantes claires pour vous aider à démarrer avec votre nouvelle instance BunkerWeb.

#### Interactive Installation

Lorsqu'il est exécuté sans aucune option, le script passe en mode interactif qui vous guide tout au long du processus d'installation. Il vous sera demandé de faire les choix suivants :

1.  **Type d'installation**: sélectionnez les composants que vous souhaitez installer.
    *   **Full Stack (par défaut)**: une installation tout-en-un comprenant BunkerWeb, le Scheduler et l'interface utilisateur Web.
    *   **Manager**: Installe le Scheduler et l'interface utilisateur Web, destinés à gérer un ou plusieurs travailleurs BunkerWeb distants.
    *   **Worker**: Installe uniquement l'instance BunkerWeb, qui peut être gérée par un gestionnaire distant.
    *   **Planificateur uniquement** : installe uniquement le composant Planificateur.
    *   **Interface utilisateur Web uniquement** : installe uniquement le composant Interface utilisateur Web.
2.  **Assistant d'installation**: choisissez d'activer ou non l'assistant de configuration Web. Ceci est fortement recommandé pour les nouveaux utilisateurs.
3.  **Intégration CrowdSec**: choisissez d'installer le moteur de sécurité CrowdSec pour une protection avancée et en temps réel contre les menaces.
4.  **CrowdSec AppSec**: si vous choisissez d'installer CrowdSec, vous pouvez également activer le composant Application Security (AppSec), qui ajoute des fonctionnalités WAF.
5.  **Service API** : choisissez d'activer le service API BunkerWeb optionnel. Il est désactivé par défaut sur les installations Linux.

!!! info "Installations du gestionnaire et du Scheduler"
    Si vous choisissez le type d'installation **Manager** ou **Scheduler Only**, vous serez également invité à fournir les adresses IP ou les noms d'hôte de vos instances de travail BunkerWeb.

#### Options de ligne de commande

Pour les configurations non interactives ou automatisées, le script peut être contrôlé à l'aide d'indicateurs de ligne de commande :

**Options générales :**

| Option                  | Description                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------------------- |
| `-v, --version VERSION` | Spécifie la version de BunkerWeb à installer (par exemple, `1.6.5-rc4`).                                     |
| `-w, --enable-wizard`   | Active l'assistant de configuration.                                                                     |
| `-n, --no-wizard`       | Désactive l'assistant d'installation.                                                                    |
| `--api`, `--enable-api` | Active le service API (FastAPI) systemd (désactivé par défaut).                                         |
| `--no-api`              | Désactive explicitement le service API.                                                                  |
| `-y, --yes`             | S'exécute en mode non interactif en utilisant les réponses par défaut pour toutes les invites.           |
| `-f, --force`           | Force l'installation à se poursuivre même sur une version du système d'exploitation non prise en charge. |
| `-q, --quiet`           | Installation silencieuse (suppression de la sortie).                                                     |
| `-h, --help`            | Affiche le message d'aide avec toutes les options disponibles.                                           |
| `--dry-run`             | Montrez ce qui serait installé sans le faire.                                                            |

**Types d'installation :**

| Option             | Description                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| `--full`           | Installation complète de la pile (BunkerWeb, Scheduler, UI). Il s'agit de l'option par défaut. |
| `--manager`        | Installe le Scheduler et l'interface utilisateur pour gérer les travailleurs à distance.       |
| `--worker`         | Installe uniquement l'instance BunkerWeb.                                                      |
| `--scheduler-only` | Installe uniquement le composant Scheduler.                                                    |
| `--ui-only`        | Installe uniquement le composant Interface utilisateur Web.                                    |

**Intégrations de sécurité :**

| Option              | Description                                                                   |
| ------------------- | ----------------------------------------------------------------------------- |
| `--crowdsec`        | Installez et configurez le moteur de sécurité CrowdSec.                       |
| `--no-crowdsec`     | Ignorez l'installation de CrowdSec.                                           |
| `--crowdsec-appsec` | Installez CrowdSec avec le composant AppSec (inclut les fonctionnalités WAF). |

**Options avancées :**

| Option                  | Description                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------------------------ |
| `--instances "IP1 IP2"` | Liste séparée par des espaces des instances BunkerWeb (requise pour les modes gestionnaire/Scheduler). |

**Exemple d'utilisation :**

```bash
# Run in interactive mode (recommended for most users)
sudo ./install-bunkerweb.sh

# Non-interactive installation with defaults (full stack, wizard enabled)
sudo ./install-bunkerweb.sh --yes

# Install a Worker node without the setup wizard
sudo ./install-bunkerweb.sh --worker --no-wizard

# Install a specific version
sudo ./install-bunkerweb.sh --version 1.6.5-rc4

# Manager setup with remote worker instances (instances required)
sudo ./install-bunkerweb.sh --manager --instances "192.168.1.10 192.168.1.11"

# Full installation with CrowdSec and AppSec
sudo ./install-bunkerweb.sh --crowdsec-appsec

# Silent non-interactive installation
sudo ./install-bunkerweb.sh --quiet --yes

# Preview installation without executing
sudo ./install-bunkerweb.sh --dry-run

# Error: CrowdSec cannot be used with worker installations
# sudo ./install-bunkerweb.sh --worker --crowdsec  # This will fail

# Error: Instances required for manager in non-interactive mode
# sudo ./install-bunkerweb.sh --manager --yes  # This will fail without --instances
```

!!! warning "Remarques importantes sur la compatibilité des options"

    **CrowdSec Limitations:**
    - Les options CrowdSec (`--crowdsec`, `--crowdsec-appsec`) ne sont compatibles qu'avec `--full` (par défaut) et `--manager` les types d'installation
    - Ils ne peuvent pas être utilisés avec `--worker`des installations , `--scheduler-only`, ou `--ui-only`

    **Exigences relatives aux instances :**
    - L `--instances` 'option n'est valable qu'avec `--manager` les types d `--scheduler-only` 'installation et
    - Lors de l'utilisation `--manager` ou `--scheduler-only` avec `--yes` (mode non interactif), l' `--instances` option est obligatoire
    - Format: `--instances "192.168.1.10 192.168.1.11 192.168.1.12"`

    **Interactif vs non interactif :**
    - Le mode interactif (par défaut) vous demandera les valeurs requises manquantes
    - Le mode non interactif (`--yes`) nécessite que toutes les options nécessaires soient fournies via la ligne de commande

#### Intégration de CrowdSec avec le script

Si vous choisissez d'installer CrowdSec lors de la configuration interactive, le script automatise entièrement son intégration avec BunkerWeb :

- Il ajoute le dépôt officiel CrowdSec et installe l'agent.
- Il crée un nouveau fichier d'acquisition pour que CrowdSec analyse les journaux de BunkerWeb (`access.log`, `error.log`, et `modsec_audit.log`).
- Il installe les collections essentielles (`crowdsecurity/nginx`) et les analyseurs syntaxiques (`crowdsecurity/geoip-enrich`).
- Il enregistre un videur pour BunkerWeb et configure automatiquement la clé API dans `/etc/bunkerweb/variables.env`.
- Si vous sélectionnez également le **composant AppSec**, il installe les `appsec-virtual-patching` collections  et `appsec-generic-rules` configure  le point de terminaison AppSec pour BunkerWeb.

Cela permet une intégration transparente et prête à l'emploi pour une prévention puissante des intrusions.

#### Considérations RHEL

!!! warning "Prise en charge des bases de données externes sur les systèmes basés sur RHEL"
    Si vous envisagez d'utiliser une base de données externe (recommandée pour la production), installez le paquet client approprié:

    ```bash
    # Pour MariaDB
    sudo dnf install mariadb

    # Pour MySQL
    sudo dnf install mysql

    # Pour PostgreSQL
    sudo dnf install postgresql
    ```

    Ceci est nécessaire pour que le Scheduler de BunkerWeb puisse se connecter à votre base de données externe.

#### Après l'installation

En fonction de vos choix lors de l'installation :

**Avec l'assistant d'installation activé :**

1. Accédez à l'assistant de configuration à l'adresse suivante : `https://your-server-ip/setup`
2. Suivez la configuration guidée pour configurer votre premier service protégé
3. Configurer les certificats SSL/TLS et d'autres paramètres de sécurité

**Sans assistant d'installation :**

1. Modifier `/etc/bunkerweb/variables.env` pour configurer BunkerWeb manuellement
2. Ajouter les paramètres de votre serveur et les services protégés
3. Redémarrez le Scheduler : `sudo systemctl restart bunkerweb-scheduler`

### Installation à l'aide du gestionnaire de paquets

Veuillez vous assurer que **NGINX 1.28.0 est installé avant d'installer BunkerWeb**. Pour toutes les distributions, à l'exception de Fedora, il est obligatoire d'utiliser des paquets préconstruits à partir du [dépôt officiel NGINX](https://nginx.org/en/linux_packages.html). La compilation de NGINX à partir des sources ou l'utilisation de paquets provenant de différents dépôts ne fonctionnera pas avec les paquets officiels préconstruits de BunkerWeb. Cependant, vous avez la possibilité de construire BunkerWeb à partir des sources.

=== "Debian Bookworm/Trixie"

    La première étape consiste à ajouter le dépôt officiel NGINX :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Vous devriez maintenant pouvoir installer NGINX 1.28.0 :

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Version testing/dev"
        Si vous utilisez la version `testing` ou `dev`, vous devrez ajouter la directive `force-bad-version` à votre fichier `/etc/dpkg/dpkg.cfg` avant d'installer BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Et enfin, installez BunkerWeb 1.6.5-rc4 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.5-rc4
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `apt upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Ubuntu"

    La première étape consiste à ajouter le dépôt officiel NGINX :

    ```shell
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    ```

    Vous devriez maintenant pouvoir installer NGINX 1.28.0 :

    ```shell
    sudo apt update && \
    sudo apt install -y --allow-downgrades nginx=1.28.0-1~$(lsb_release -cs)
    ```

    !!! warning "Version testing/dev"
        Si vous utilisez la version `testing` ou `dev`, vous devrez ajouter la directive `force-bad-version` à votre fichier `/etc/dpkg/dpkg.cfg` avant d'installer BunkerWeb.

        ```shell
        echo "force-bad-version" | sudo tee -a /etc/dpkg/dpkg.cfg
        ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Et enfin, installez BunkerWeb 1.6.5-rc4 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo -E apt install -y --allow-downgrades bunkerweb=1.6.5-rc4
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `apt upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo apt-mark hold nginx bunkerweb
    ```

=== "Fedora"

    !!! info "Fedora Update Testing"
        Si vous ne trouvez pas la version de NGINX répertoriée dans le dépôt stable, vous pouvez activer le dépôt `updates-testing` :

        ```shell
        sudo dnf config-manager setopt updates-testing.enabled=1
        ```

    Fedora fournit déjà NGINX 1.28.0, que nous prenons en charge :

    ```shell
    sudo dnf install -y --allowerasing nginx-1.28.0
    ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Et enfin, installez BunkerWeb 1.6.5-rc4 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf makecache && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.5-rc4
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `dnf upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

=== "RedHat"

    La première étape consiste à ajouter le dépôt officiel NGINX. Créez le fichier suivant dans /etc/yum.repos.d/nginx.repo :

    ```conf
    [nginx-stable]
    name=nginx stable repo
    baseurl=http://nginx.org/packages/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=1
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true

    [nginx-mainline]
    name=nginx mainline repo
    baseurl=http://nginx.org/packages/mainline/centos/$releasever/$basearch/
    gpgcheck=1
    enabled=0
    gpgkey=https://nginx.org/keys/nginx_signing.key
    module_hotfixes=true
    ```

    Vous devriez maintenant pouvoir installer NGINX 1.28.0 :

    ```shell
    sudo dnf install --allowerasing nginx-1.28.0
    ```

    !!! example "Désactiver l'assistant d'installation"
        Si vous ne souhaitez pas utiliser l'assistant de configuration de l'interface Web lors de l'installation de BunkerWeb, exportez la variable suivante :

        ```shell
        export UI_WIZARD=no
        ```

    Enfin, installez BunkerWeb 1.6.5-rc4 :

    ```shell
    curl -s https://repo.bunkerweb.io/install/script.rpm.sh | sudo bash && \
    sudo dnf check-update && \
    sudo -E dnf install -y --allowerasing bunkerweb-1.6.5-rc4
    ```

    Pour empêcher la mise à jour des paquets NGINX et/ou BunkerWeb lors de l'exécution de `dnf upgrade`, vous pouvez utiliser la commande suivante :

    ```shell
    sudo dnf versionlock add nginx && \
    sudo dnf versionlock add bunkerweb
    ```

### Configuration et service

La configuration manuelle de BunkerWeb se fait en éditant le `/etc/bunkerweb/variables.env` fichier :

```conf
MY_SETTING_1=value1
MY_SETTING_2=value2
...
```

Une fois installé, BunkerWeb est livré avec trois services `bunkerweb`, `bunkerweb-scheduler` et `bunkerweb-ui` que vous pouvez gérer à l'aide `systemctl`de .

Si vous modifiez manuellement la configuration de BunkerWeb à l'aide `/etc/bunkerweb/variables.env` d'un redémarrage du `bunkerweb-scheduler` service, il suffira de générer et de recharger la configuration sans aucun temps d'arrêt. Mais selon le cas (par exemple, en changeant de port d'écoute), vous devrez peut-être redémarrer le `bunkerweb` service.

### Haute disponibilité

Le Scheduler peut être détaché de l'instance BunkerWeb pour fournir une haute disponibilité. Dans ce cas, le Scheduler sera installé sur un serveur séparé et pourra gérer plusieurs instances BunkerWeb.

#### Manager

Pour installer uniquement le Scheduler sur un serveur, vous pouvez exporter les variables suivantes avant d'exécuter l'installation de BunkerWeb :

```shell
export MANAGER_MODE=yes
export UI_WIZARD=no
```

Vous pouvez également exporter les variables suivantes pour activer uniquement le Scheduler :

```shell
export SERVICE_SCHEDULER=yes
export SERVICE_BUNKERWEB=no
export SERVICE_UI=no
```

#### Worker

Sur un autre serveur, pour installer uniquement BunkerWeb, vous pouvez exporter les variables suivantes avant d'exécuter l'installation de BunkerWeb :

```shell
export WORKER_MODE=yes
```

Alternativement, vous pouvez également exporter les variables suivantes pour activer uniquement BunkerWeb :

```shell
export SERVICE_BUNKERWEB=yes
export SERVICE_SCHEDULER=no
export SERVICE_UI=no
```

#### Interface utilisateur Web

L'interface utilisateur Web peut être installée sur un serveur séparé pour fournir une interface dédiée à la gestion des instances BunkerWeb. Pour installer uniquement l'interface utilisateur Web, vous pouvez exporter les variables suivantes avant d'exécuter l'installation de BunkerWeb :

```shell
export SERVICE_BUNKERWEB=no
export SERVICE_SCHEDULER=no
export SERVICE_UI=yes
```

## Docker autoconf

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-autoconf.svg){ align=center, width="600" }
  <figcaption>Intégration de Docker autoconf</figcaption>
</figure>

!!! info "Intégration Docker"
    L'intégration de Docker autoconf est une "évolution" de celle de Docker. Veuillez d'abord lire la section sur l' [intégration Docker](#docker) si nécessaire.

Une autre approche est disponible pour résoudre l'inconvénient de recréer le conteneur chaque fois qu'il y a une mise à jour. En utilisant une autre image appelée **autoconf**, vous pouvez automatiser la reconfiguration en temps réel de BunkerWeb sans avoir besoin de recréer des conteneurs.

Pour tirer parti de cette fonctionnalité, au lieu de définir des variables d'environnement pour le conteneur BunkerWeb, vous pouvez ajouter des **étiquettes** à vos conteneurs d'application Web. L'image **autoconf** écoutera alors les événements Docker et gérera de manière transparente les mises à jour de configuration pour BunkerWeb.

Ce processus «* automagique *» simplifie la gestion des configurations BunkerWeb. En ajoutant des étiquettes à vos conteneurs d'applications web, vous pouvez déléguer les tâches de reconfiguration à **autoconf** sans l'intervention manuelle de la recréation de conteneurs. Cela simplifie le processus de mise à jour et améliore la commodité.

En adoptant cette approche, vous pouvez profiter d'une reconfiguration en temps réel de BunkerWeb sans avoir à vous soucier de la recréation de conteneurs, ce qui le rend plus efficace et plus convivial.

!!! info "Mode multisite"
    L'intégration de Docker autoconf implique l'utilisation du **mode multisite**. Pour plus d'informations, reportez-vous à la [section multisite](concepts.md#multisite-mode) de la documentation.

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez MariaDB comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, nous comprenons que vous préférerez peut-être utiliser d'autres backends pour votre intégration Docker. Si c'est le cas, soyez assuré que d'autres backends de base de données sont toujours possibles. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc4/misc/integrations) du dépôt.

Pour activer les mises à jour automatiques de la configuration, incluez un conteneur supplémentaire appelé `bw-autoconf` dans la pile. Ce conteneur héberge le service autoconf, qui gère les modifications de configuration dynamiques pour BunkerWeb.

Pour prendre en charge cette fonctionnalité, utilisez un "vrai" backend de base de données dédié (par exemple, MariaDB, MySQL ou PostgreSQL) pour le stockage de configuration synchronisé. En intégrant `bw-autoconf` un backend de base de données approprié, vous établissez l'infrastructure pour une gestion automatisée de la configuration sans faille dans BunkerWeb.

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both containers
  AUTOCONF_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.5-rc4
    ports:
      - "80:8080/tcp"
      - "443:8443/tcp"
      - "443:8443/udp" # QUIC
    labels:
      - "bunkerweb.INSTANCE=yes" # Mandatory label for the autoconf service to identify the BunkerWeb instance
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.5-rc4
    depends_on:
      - bunkerweb
      - bw-docker
    environment:
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-docker
      - bw-db

  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      CONTAINERS: "1"
      LOG_LEVEL: "warning"
    restart: "unless-stopped"
    networks:
      - bw-docker

  bw-db:
    image: mariadb:11
    # We set the max allowed packet size to avoid issues with large queries
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db

volumes:
  bw-data:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    ipam:
      driver: default
      config:
        - subnet: 10.20.30.0/24
  bw-services:
    name: bw-services
  bw-docker:
    name: bw-docker
  bw-db:
    name: bw-db
```

!!! info "Base de données dans le `bw-db` réseau"
    Le conteneur de base de données n'est intentionnellement pas inclus dans le `bw-universe` réseau. Il est utilisé par les `bw-autoconf` `bw-scheduler` conteneurs et plutôt que directement par BunkerWeb. Par conséquent, le conteneur de base de données fait partie du `bw-db` réseau, ce qui renforce la sécurité en rendant l'accès externe à la base de données plus difficile. **Ce choix de conception délibéré permet de protéger la base de données et de renforcer la perspective de sécurité globale du système**.

!!! warning "Utilisation de Docker en mode rootless"
    Si vous utilisez [Docker en mode rootless](https://docs.docker.com/engine/security/rootless), vous devrez remplacer le support du socket docker par la valeur suivante : `$XDG_RUNTIME_DIR/docker.sock:/var/run/docker.sock:ro`.

### Les services d'Autoconf

Une fois la pile configurée, vous pourrez créer le conteneur de l'application web et ajouter les paramètres sous forme d'étiquettes à l'aide du préfixe "bunkerweb." afin de configurer automatiquement BunkerWeb :

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### Espaces de noms

À partir de la version `1.6.0`, les piles Autoconf de BunkerWeb supportent désormais les espaces de noms. Cette fonctionnalité vous permet de gérer plusieurs «* clusters *» d'instances et de services BunkerWeb sur le même hôte Docker. Pour tirer parti des espaces de noms, il vous suffit de définir l' `NAMESPACE` étiquette sur vos services. Voici un exemple :

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    labels:
      - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the service
      - "bunkerweb.MY_SETTING_1=value1"
      - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Comportement de l'espace de nommage"

    By default all Autoconf stacks listen to all namespaces. If you want to restrict a stack to specific namespaces, you can set the `NAMESPACES` environment variable in the `bw-autoconf` service:

    ```yaml
    ...
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc4
        labels:
          - "bunkerweb.INSTANCE=yes"
          - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the BunkerWeb instance so the autoconf service can detect it
      ...
      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc4
        environment:
          ...
          NAMESPACES: "my-namespace my-other-namespace" # Only listen to these namespaces
    ...
    ```

    Keep in mind that the `NAMESPACES` environment variable is a space-separated list of namespaces.

!!! warning "Spécifications de l'espace de nommage"

    There can only be **one database** and **one Scheduler** per namespace. If you try to create multiple databases or Schedulers in the same namespace, the configurations will end up conflicting with each other.

    The Scheduler doesn't need the `NAMESPACE` label to work properly. It will only need the `DATABASE_URI` setting properly configured so that it can access the same database as the autoconf service.

## Kubernetes

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-kubernetes.svg){ align=center, width="600" }
  <figcaption>Intégration Kubernetes</figcaption>
</figure>

Pour automatiser la configuration des instances BunkerWeb dans un environnement Kubernetes, le service autoconf sert de [contrôleur d'entrée](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/). Il configure les instances BunkerWeb en fonction des [ressources d'entrée](https://kubernetes.io/docs/concepts/services-networking/ingress/) et surveille également d'autres objets Kubernetes, tels que [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/), pour des configurations personnalisées.

Pour une configuration optimale, il est recommandé de définir BunkerWeb en tant que **[DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)**, ce qui garantit qu'un pod est créé sur tous les nœuds, tandis que l'**autoconf et le scheduler** sont définis comme  un **seul déploiement[ répliqué](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)**.

Compte tenu de la présence de plusieurs instances BunkerWeb, il est nécessaire d'établir un magasin de données partagé implémenté en tant que [ service Redis](https://redis.io/) ou [Valkey](https://valkey.io/). Ce service sera utilisé par les instances pour mettre en cache et partager des données entre elles. Vous trouverez de plus amples informations sur les paramètres Redis/Valkey [ici](features.md#redis).

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez MariaDB comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, nous comprenons que vous préférerez peut-être utiliser d'autres backends pour votre intégration Docker. Si c'est le cas, soyez assuré que d'autres backends de base de données sont toujours possibles. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc4/misc/integrations) du dépôt.

      La configuration des backends de base de données en cluster est hors du périmètre de cette documentation.

Assurez-vous que les services autoconf ont accès à l'API Kubernetes. Il est recommandé d'utiliser l' [autorisation RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) à cette fin.

!!! warning "Autorité de certification personnalisée pour l'API Kubernetes"
    Si vous utilisez une autorité de certification personnalisée pour votre API Kubernetes, vous pouvez monter un fichier de bundle contenant vos certificats intermédiaires et racines sur le contrôleur d'entrée et définir la `KUBERNETES_SSL_CA_CERT` valeur de l'environnement sur le chemin d'accès du bundle à l'intérieur du conteneur. Sinon, même si cela n'est pas recommandé, vous pouvez désactiver la vérification du certificat en définissant la `KUBERNETES_SSL_VERIFY` variable d'environnement du contrôleur d'entrée sur `no` (la valeur par défaut `yes`est ).

De plus, **il est crucial de définir la `KUBERNETES_MODE` variable d'environnement lors `yes` de  l'utilisation de l'intégration Kubernetes**. Cette variable est obligatoire pour un bon fonctionnement.

### Méthodes d'installation

#### Utilisation du graphique de barre (recommandé)

La méthode recommandée pour installer Kubernetes est d'utiliser le graphique Helm disponible à l'adresse `https://repo.bunkerweb.io/charts`:

```shell
helm repo add bunkerweb https://repo.bunkerweb.io/charts
```

Vous pouvez ensuite utiliser le tableau de bord de bunkerweb à partir de ce dépôt :

```shell
helm install -f myvalues.yaml mybunkerweb bunkerweb/bunkerweb
```

La liste complète des valeurs est répertoriée dans le [fichier charts/bunkerweb/values.yaml](https://github.com/bunkerity/bunkerweb-helm/blob/main/charts/bunkerweb/values.yaml) du [dépôt bunkerity/bunkerweb-helm](https://github.com/bunkerity/bunkerweb-helm).

#### Fichiers YAML complets

Au lieu d'utiliser le graphique helm, vous pouvez également utiliser les modèles YAML dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc4/misc/integrations) du référentiel GitHub. Veuillez noter que nous vous recommandons vivement d'utiliser le tableau de barre à la place.

### Ressources d'entrée

Une fois que la pile Kubernetes de BunkerWeb est correctement configurée et opérationnelle (reportez-vous aux journaux autoconf pour plus d'informations), vous pouvez procéder au déploiement d'applications Web au sein du cluster et déclarer votre ressource d'entrée.

Il est important de noter que les paramètres BunkerWeb doivent être spécifiés en tant qu'annotations pour la ressource Ingress. Pour la partie domaine, veuillez utiliser la valeur spéciale **`bunkerweb.io`**. En incluant les annotations appropriées, vous pouvez configurer BunkerWeb en conséquence pour la ressource Ingress.

!!! info "Prise en charge TLS"
    Le contrôleur d'entrée BunkerWeb prend entièrement en charge les certificats HTTPS personnalisés à l'aide de la spécification tls, comme indiqué dans l'exemple. La configuration de solutions telles que `cert-manager` la génération automatique de secrets tls n'entre pas dans le cadre de cette documentation.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # Will be applied to all host in this ingress
    bunkerweb.io/MY_SETTING: "value"
    # Will only be applied to the www.example.com host
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  # TLS is optional, you can also use builtin Let's Encrypt for example
  # tls:
  #   - hosts:
  #       - www.example.com
  #     secretName: secret-example-tls
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
...
```

### Espaces de noms

À partir de la version `1.6.0`, les piles autoconf de BunkerWeb prennent désormais en charge les espaces de noms. Cette fonctionnalité vous permet de gérer plusieurs clusters d'instances et de services BunkerWeb sur le même cluster Kubernetes. Pour tirer parti des espaces de noms, il suffit de définir le `namespace` champ de métadonnées sur vos instances et services BunkerWeb. Voici un exemple :

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: bunkerweb
  namespace: my-namespace # Set the namespace for the BunkerWeb instance
...
```

!!! info "Comportement de l'espace de nommage"

    Par défaut, toutes les piles Autoconf écoutent tous les namespaces. Si vous souhaitez restreindre une pile à des namespaces spécifiques, vous pouvez définir la variable d'environnement `NAMESPACES` dans le déploiement `bunkerweb-controller` :

    ```yaml
    ...
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-controller
      namespace: my-namespace # Set the namespace for the Controller
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-controller
      template:
        metadata:
          labels:
            app: bunkerweb-controller
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-controller
              image: bunkerity/bunkerweb-autoconf:1.6.5-rc4
              imagePullPolicy: Always
              env:
                - name: NAMESPACES
                  value: "my-namespace my-other-namespace" # Only listen to these namespaces
                ...
    ...
    ```

    Gardez à l'esprit que la variable d'environnement `NAMESPACES` est une liste de namespaces séparés par des espaces.

!!! warning "Spécifications de l'espace de nommage"

    Il ne peut y avoir qu'une **seule base de données** et qu'un **seul Scheduler** par namespace. Si plusieurs bases de données ou plusieurs Schedulers sont créés dans le même namespace, les configurations entreront en conflit.

    Le Scheduler n'a pas besoin de l'annotation `NAMESPACE` pour fonctionner correctement. Il suffit que le paramètre `DATABASE_URI` soit correctement configuré afin qu'il puisse accéder à la même base de données que le service autoconf.

### Classe d'entrée

Lorsqu'il est installé en utilisant les méthodes officielles de la documentation, BunkerWeb est livré avec la définition suivante `IngressClass` :

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: bunkerweb
spec:
  controller: bunkerweb.io/ingress-controller
```

Afin de limiter les `Ingress` ressources surveillées par le contrôleur d'entrée, vous pouvez définir la `KUBERNETES_INGRESS_CLASS` variable d'environnement avec la valeur `bunkerweb`. Ensuite, vous pouvez utiliser la `ingressClassName` directive dans vos `Ingress` définitions :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    bunkerweb.io/MY_SETTING: "value"
    bunkerweb.io/www.example.com_MY_SETTING: "value"
spec:
  ingressClassName: bunkerweb
  rules:
    - host: www.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: svc-my-app
                port:
                  number: 8000
```

### Nom de domaine personnalisé

Si vous utilisez un nom de domaine personnalisé différent de celui par défaut pour votre cluster Kubernetes `kubernetes.local` , vous pouvez définir la valeur à l'aide de la `KUBERNETES_DOMAIN_NAME` variable d'environnement sur le conteneur du Scheduler.

### Utilisation avec le contrôleur d'entrée existant

!!! info "Conserver à la fois le contrôleur d'entrée existant et BunkerWeb"

    Il s'agit d'un cas d'utilisation où vous souhaitez conserver un contrôleur d'entrée existant, tel que nginx. Le flux de trafic typique sera : équilibreur de charge => contrôleur d'entrée => BunkerWeb => application.

#### Installation du contrôleur d'entrée nginx

Installez le dépôt helm nginx d'entrée :

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

Installez le contrôleur d'entrée nginx avec les valeurs par défaut (il se peut qu'il ne fonctionne pas sur votre propre cluster prêt à l'emploi, veuillez consulter la [documentation](https://kubernetes.github.io/ingress-nginx/)) :

```bash
helm install --namespace nginx --create-namespace nginx ingress-nginx/ingress-nginx
```

Extraire l'adresse IP de LB :

```bash
kubectl get svc nginx-ingress-nginx-controller -n nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Configurez les entrées DNS sur l'adresse IP de LB (par exemple, `bunkerweb` le sous-domaine pour l'interface utilisateur BW et `myapp` pour l'application) :

```bash
$ nslookup bunkerweb.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   bunkerweb.example.com
Address: 1.2.3.4
$ nslookup myapp.example.com
Server:         172.26.112.1
Address:        172.26.112.1#53

Non-authoritative answer:
Name:   myapp.example.com
Address: 1.2.3.4
```

**Installation de BunkerWeb**

Installez le dépôt helm de BunkerWeb :

```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
```

Créer un `values.yaml` fichier :

```yaml
# Here we will setup the values needed to setup BunkerWeb behind an existing ingress controller
# Traffic flow with BW: LB => existing Ingress Controller => BunkerWeb => Service
# Traffic flow without BW: LB => existing Ingress Controller => Service

# Global settings
settings:
  misc:
    # Replace with your DNS resolver
    # to get it: kubectl exec in a random pod then cat /etc/resolv.conf
    # if you have an IP as nameserver then do a reverse DNS lookup: nslookup <IP>
    # most of the time it's coredns.kube-system.svc.cluster.local or kube-dns.kube-system.svc.cluster.local
    dnsResolvers: "kube-dns.kube-system.svc.cluster.local"
  kubernetes:
    # We only consider Ingress resources with ingressClass bunkerweb to avoid conflicts with existing ingress controller
    ingressClass: "bunkerweb"
    # Optional: you can choose namespace(s) where BunkerWeb will listen for Ingress/ConfigMap changes
    # Default (blank value) is all namespaces
    namespaces: ""

# Override the bunkerweb-external service type to ClusterIP
# Since we don't need to expose it to the outside world
# We will use the existing ingress controller to route traffic to BunkerWeb
service:
  type: ClusterIP

# BunkerWeb settings
bunkerweb:
  tag: 1.6.5-rc4

# Scheduler settings
scheduler:
  tag: 1.6.5-rc4
  extraEnvs:
    # Enable real IP module to get real IP of clients
    - name: USE_REAL_IP
      value: "yes"

# Controller settings
controller:
  tag: 1.6.5-rc4

# UI settings
ui:
  tag: 1.6.5-rc4
```

Installez BunkerWeb avec des valeurs personnalisées :

```bash
helm install --namespace bunkerweb --create-namespace -f values.yaml bunkerweb bunkerweb/bunkerweb
```

Vérifiez les journaux et attendez que tout soit prêt.

**Installation de l'interface utilisateur Web**

Configurez l'entrée suivante (en supposant que le contrôleur nginx est installé) :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ui-bunkerweb
  # Replace with your namespace of BW if needed
  namespace: bunkerweb
  annotations:
    # HTTPS is mandatory for web UI even if traffic is internal
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    # We must set SNI so BW can serve the right vhost
    # Replace with your domain
    nginx.ingress.kubernetes.io/proxy-ssl-name: "bunkerweb.example.com"
    nginx.ingress.kubernetes.io/proxy-ssl-server-name: "on"
spec:
  # Only served by nginx controller and not BW
  ingressClassName: nginx
  # Uncomment and edit if you want to use your own certificate
  # tls:
  # - hosts:
  #   - bunkerweb.example.com
  #   secretName: tls-secret
  rules:
  # Replace with your domain
  - host: bunkerweb.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Created by Helm chart
            name: bunkerweb-external
            port:
              # Using HTTPS port is mandatory for UI
              number: 443
```

Et vous pouvez maintenant passer à l'assistant de configuration en accédant à `https://bunkerweb.example.com/setup`.

**Protection de l'application existante**

**Tout d'abord, vous devrez vous rendre dans Global Config, sélectionner le plugin SSL, puis désactiver la redirection automatique HTTP vers HTTPS. Veuillez noter que vous n'avez besoin de le faire qu'une seule fois.**

Supposons que vous ayez une application dans l'espace de `myapp` noms qui est accessible à l'aide du `myapp-service` service sur le port `5000`.

Vous devrez ajouter un nouveau service sur l'interface utilisateur web et renseigner les informations requises :

- Nom du serveur : le domaine public de votre application (par ex. `myapp.example.com`)
- SSL/TLS : votre contrôleur d'entrée s'occupe de cette partie, donc ne l'activez pas sur BunkerWeb car le trafic est interne au sein du cluster
- Hôte proxy inverse : l'URL complète de votre application au sein du cluster (par exemple) `http://myapp-service.myapp.svc.cluster.local:5000`

Une fois le nouveau service ajouté, vous pouvez maintenant déclarer une ressource Ingress pour ce service et l'acheminer vers le service BunkerWeb sur le port HTTP :

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  # Replace with your namespace of BW if needed
  namespace: bunkerweb
spec:
  # Only served by nginx controller and not BW
  ingressClassName: nginx
  # Uncomment and edit if you want to use your own certificate
  # tls:
  # - hosts:
  #   - myapp.example.com
  #   secretName: tls-secret
  rules:
  # Replace with your domain
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            # Created by Helm chart
            name: bunkerweb-external
            port:
              number: 80
```

Vous pouvez visiter `http(s)://myapp.example.com`, qui est maintenant protégé par BunkerWeb ️

## Swarm

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-swarm.svg){ align=center, width="600" }
  <figcaption>Intégration de Docker Swarm</figcaption>
</figure>

!!! warning "Obsolète"
    L'intégration de Swarm est obsolète et sera supprimée dans une version ultérieure. Veuillez envisager d'utiliser l' [intégration Kubernetes](#kubernetes) à la place.

!!! tip "Support PRO"
    **Si vous avez besoin d'aide sur l'intégration Swarm**, veuillez nous contacter au [contact@bunkerity.com](mailto:contact@bunkerity.com) ou via le formulaire de [contact](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc).

!!! info "Docker autoconf"
    L'intégration de Swarm est similaire à celle de Docker autoconf (mais avec des services au lieu de conteneurs). Veuillez d'abord lire la section sur l ['intégration de Docker autoconf](#docker-autoconf) si nécessaire.

Pour permettre la configuration automatique des instances BunkerWeb, le ** service autoconf** nécessite l'accès à l'API Docker. Ce service est à l'écoute des événements Docker Swarm, tels que la création ou la suppression de services, et configure de manière transparente les **instances BunkerWeb** en temps réel sans aucun temps d'arrêt. Il surveille également d'autres objets Swarm, tels que [les configurations](https://docs.docker.com/engine/swarm/configs/), pour les configurations personnalisées.

Semblable à l'[intégration Docker autoconf](#docker-autoconf), la configuration des services Web est définie à l'aide d'étiquettes qui commencent par le ** préfixe **bunkerweb.

Pour une configuration optimale, il est recommandé de planifier le **service BunkerWeb** en tant que ***service global*** sur tous les nœuds, tandis que les **services autoconf, scheduler et proxy Docker API** doivent être planifiés en tant que ***services répliqués uniques***. Veuillez noter que le service proxy de l'API Docker doit être planifié sur un nœud de gestionnaire, sauf si vous le configurez pour utiliser une API distante (ce qui n'est pas couvert dans la documentation).

Étant donné que plusieurs instances de BunkerWeb sont en cours d'exécution, un magasin de données partagé implémenté en tant que [ service Redis](https://redis.io/) ou [Valkey](https://valkey.io/) doit être créé. Ces instances utiliseront le service Redis/Valkey pour mettre en cache et partager des données. Vous trouverez plus de détails sur les paramètres Redis/Valkey [ici](features.md#redis).

En ce qui concerne le volume de la base de données, la documentation ne spécifie pas d'approche spécifique. Le choix d'un dossier partagé ou d'un pilote spécifique pour le volume de base de données dépend de votre cas d'utilisation unique et est laissé à la disposition du lecteur.

!!! info "Backend de base de données"
    Veuillez noter que nos instructions supposent que vous utilisez MariaDB comme backend de base de données par défaut, tel que configuré par le `DATABASE_URI` paramètre. Cependant, nous comprenons que vous préférerez peut-être utiliser d'autres backends pour votre intégration Docker. Si c'est le cas, soyez assuré que d'autres backends de base de données sont toujours possibles. Pour plus d'informations, consultez les fichiers docker-compose dans le [dossier misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc4/misc/integrations) du dépôt.

      La configuration des backends de base de données en cluster est hors du périmètre de cette documentation.

Voici le passe-partout de la pile que vous pouvez déployer à l'aide de `docker stack deploy`:

```yaml
x-bw-env: &bw-env
  # We use an anchor to avoid repeating the same settings for both services
  SWARM_MODE: "yes"
  API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.5-rc4
    ports:
      - published: 80
        target: 8080
        mode: host
        protocol: tcp
      - published: 443
        target: 8443
        mode: host
        protocol: tcp
      - published: 443
        target: 8443
        mode: host
        protocol: udp # QUIC
    environment:
      <<: *bw-env
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-services
    deploy:
      mode: global
      placement:
        constraints:
          - "node.role == worker"
      labels:
        - "bunkerweb.INSTANCE=yes" # Mandatory label for the autoconf service to identify the BunkerWeb instance

  bw-scheduler:
    image: bunkerity/bunkerweb-scheduler:1.6.5-rc4
    environment:
      <<: *bw-env
      BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
      SERVER_NAME: "" # The server name will be filled with services labels
      MULTISITE: "yes" # Mandatory setting for autoconf
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      USE_REDIS: "yes"
      REDIS_HOST: "bw-redis"
    volumes:
      - bw-storage:/data # This is used to persist the cache and other data like backups
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-autoconf:
    image: bunkerity/bunkerweb-autoconf:1.6.5-rc4
    environment:
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      DOCKER_HOST: "tcp://bw-docker:2375" # The Docker socket
    restart: "unless-stopped"
    networks:
      - bw-universe
      - bw-docker
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-docker:
    image: tecnativa/docker-socket-proxy:nightly
    environment:
      CONFIGS: "1"
      CONTAINERS: "1"
      SERVICES: "1"
      SWARM: "1"
      TASKS: "1"
      LOG_LEVEL: "warning"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: "unless-stopped"
    networks:
      - bw-docker
    deploy:
      placement:
        constraints:
          - "node.role == manager"

  bw-db:
    image: mariadb:11
    # We set the max allowed packet size to avoid issues with large queries
    command: --max-allowed-packet=67108864
    environment:
      MYSQL_RANDOM_ROOT_PASSWORD: "yes"
      MYSQL_DATABASE: "db"
      MYSQL_USER: "bunkerweb"
      MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
    volumes:
      - bw-data:/var/lib/mysql
    restart: "unless-stopped"
    networks:
      - bw-db
    deploy:
      placement:
        constraints:
          - "node.role == worker"

  bw-redis:
    image: redis:7-alpine
    restart: "unless-stopped"
    networks:
      - bw-universe
    deploy:
      placement:
        constraints:
          - "node.role == worker"

volumes:
  bw-data:
  bw-storage:

networks:
  bw-universe:
    name: bw-universe
    driver: overlay
    attachable: true
    ipam:
      config:
        - subnet: 10.20.30.0/24
  bw-services:
    name: bw-services
    driver: overlay
    attachable: true
  bw-docker:
    name: bw-docker
    driver: overlay
    attachable: true
  bw-db:
    name: bw-db
    driver: overlay
    attachable: true
```

!!! info "Réglage obligatoire de l'swarm"
    Veuillez noter que la `SWARM_MODE: "yes"` variable d'environnement est obligatoire lors de l'utilisation de l'intégration Swarm.

### Services Swarm

Une fois que la pile BunkerWeb Swarm est configurée et en cours d'exécution (voir les journaux autoconf et scheduler pour plus d'informations), vous pourrez déployer des applications Web dans le cluster et utiliser des étiquettes pour configurer dynamiquement BunkerWeb :

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

### Espaces de noms

À partir de la version `1.6.0`, les piles Autoconf de BunkerWeb supportent désormais les espaces de noms. Cette fonctionnalité vous permet de gérer plusieurs «* clusters *» d'instances et de services BunkerWeb sur le même hôte Docker. Pour tirer parti des espaces de noms, il vous suffit de définir l' `NAMESPACE` étiquette sur vos services. Voici un exemple :

```yaml
services:
  myapp:
    image: mywebapp:4.2
    networks:
      - bw-services
    deploy:
      placement:
        constraints:
          - "node.role==worker"
      labels:
        - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the service
        - "bunkerweb.MY_SETTING_1=value1"
        - "bunkerweb.MY_SETTING_2=value2"

networks:
  bw-services:
    external: true
    name: bw-services
```

!!! info "Comportement de l'espace de nommage"

    Par défaut, toutes les piles Autoconf écoutent tous les espaces de noms. Si vous souhaitez restreindre une pile à des espaces de noms spécifiques, vous pouvez définir la variable d'environnement `NAMESPACES` dans le service `bw-autoconf` :

    ```yaml
    ...
    services:
      bunkerweb:
      image: bunkerity/bunkerweb:1.6.5-rc4
      ...
      deploy:
        mode: global
        placement:
        constraints:
          - "node.role == worker"
        labels:
        - "bunkerweb.INSTANCE=yes"
        - "bunkerweb.NAMESPACE=my-namespace" # Set the namespace for the BunkerWeb instance
      ...
      bw-autoconf:
      image: bunkerity/bunkerweb-autoconf:1.6.5-rc4
      environment:
        NAMESPACES: "my-namespace my-other-namespace" # Only listen to these namespaces
        ...
      deploy:
        placement:
        constraints:
          - "node.role == worker"
    ...
    ```

    Gardez à l'esprit que la variable d'environnement `NAMESPACES` est une liste d'espaces de noms séparés par des espaces.

!!! warning "Spécifications de l'espace de nommage"

    Il ne peut y avoir **qu'une seule base de données** et **un seul Scheduler** par espace de noms. Si vous tentez de créer plusieurs bases de données ou plusieurs Schedulers dans le même espace de noms, les configurations entreront en conflit.

    Le Scheduler n'a pas besoin de l'étiquette `NAMESPACE` pour fonctionner correctement. Il a seulement besoin que le paramètre `DATABASE_URI` soit correctement configuré afin qu'il puisse accéder à la même base de données que le service autoconf.

## Microsoft Azure

<figure markdown>
  ![Vue d'ensemble](assets/img/integration-azure.webp){ align=center, width="600" }
  <figcaption>Intégration Azure</figcaption>
</figure>

!!! info "Taille de machine virtuelle recommandée"
    Soyez vigilant lorsque vous choisissez la référence SKU de la machine virtuelle. Vous devez sélectionner une référence SKU compatible avec la machine virtuelle Gen2 et nous vous recommandons de commencer par la série B2s ou Ds2 pour une utilisation optimale.

Vous pouvez facilement déployer BunkerWeb sur votre abonnement Azure de plusieurs manières :

- Azure CLI dans Cloud Shell
- Modèle Azure ARM
- Portail Azure via la Place de marché

=== "Cloud Shell"

    Créez un groupe de ressources. Remplacez la valeur `RG_NAME`

    ```bash
    az group create --name "RG_NAME" --location "LOCATION"
    ```

    Créez une machine virtuelle avec la taille (SKU) `Standard_B2s` dans la même région que le groupe de ressources. Remplacez les valeurs `RG_NAME`, `VM_NAME`, `VNET_NAME`, `SUBNET_NAME`

    ```bash

    az vm create --resource-group "RG_NAME" --name "VM_NAME" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --vnet-name "VNET_NAME" --size Standard_B2s --subnet "SUBNET_NAME"
    ```

    Commande complète. Remplacez les valeurs `RG_NAME`, `VM_NAME`, `LOCATION`, `HOSTNAME`, `USERNAME`, `PUBLIC_IP`, `VNET_NAME`, `SUBNET_NAME`, `NSG_NAME`

    ```bash
    az vm create --resource-group "RG_NAME" --name "VM_NAME" --location "LOCATION" --image bunkerity:bunkerweb:bunkerweb:latest --accept-term --generate-ssh-keys --computer-name "HOSTNAME" --admin-username "USERNAME" --public-ip-address "PUBLIC_IP" --public-ip-address-allocation Static --size Standard_B2s --public-ip-sku Standard --os-disk-delete-option Delete --nic-delete-option Delete --vnet-name "VNET_NAME" --subnet "SUBNET_NAME" --nsg "NSG_NAME"
    ```

=== "Modèle ARM"

    !!! info "Exigences en matière d'autorisations"
        Pour déployer un modèle ARM, vous devez disposer d'un accès en écriture sur les ressources que vous déployez ainsi que de l'accès à toutes les opérations sur le type de ressource Microsoft.Resources/deployments.
        Pour déployer une machine virtuelle, vous avez besoin des autorisations Microsoft.Compute/virtualMachines/write et Microsoft.Resources/deployments/*. L'opération what-if requiert les mêmes autorisations.

    Déployer le modèle ARM :

    [![Déployer sur Azure](assets/img/integration-azure-deploy.svg)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fbunkerity%2Fbunkerweb%2Fmaster%2Fmisc%2Fintegrations%2Fazure-arm-template.json){:target="_blank"}

=== "Marketplace"

    Connectez-vous au [portail Azure](https://portal.azure.com){:target="_blank"}.

    Obtenez BunkerWeb depuis le menu [Créer une ressource](https://portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/bunkerity.bunkerweb){:target="_blank"}.

    Vous pouvez également passer par [le Marketplace](https://azuremarketplace.microsoft.com/fr-fr/marketplace/apps/bunkerity.bunkerweb?tab=Overview){:target="_blank"}.

Vous pouvez accéder à l'assistant d'installation en parcourant l' `https://your-ip-address/setup` URI de votre machine virtuelle.
