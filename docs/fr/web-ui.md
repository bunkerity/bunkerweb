# Interface utilisateur Web

## Aperçu

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Le "Web UI" est une application Web qui vous aide à gérer votre instance BunkerWeb à l'aide d'une interface conviviale au lieu de vous fier uniquement à la ligne de commande.

Voici une liste des fonctionnalités offertes par l'interface utilisateur web :

- Obtenez une vue complète des attaques bloquées
- Démarrez, arrêtez, redémarrez et rechargez votre instance BunkerWeb
- Ajouter, modifier et supprimer des paramètres pour vos applications web
- Ajoutez, modifiez et supprimez des configurations personnalisées pour NGINX et ModSecurity
- Installer et désinstaller des plug-ins externes
- Explorer les fichiers mis en cache
- Surveillez l'exécution des tâches et redémarrez-les si nécessaire
- Afficher les journaux et rechercher des modèles

## Conditions préalables

Étant donné que l'interface utilisateur Web est une application Web, l'architecture recommandée consiste à exécuter BunkerWeb devant elle en tant que proxy inverse. La procédure d'installation recommandée consiste à utiliser l'assistant de configuration, qui vous guidera étape par étape, comme décrit dans le guide de [démarrage rapide](quickstart-guide.md).

!!! warning "Considérations de sécurité"

    La sécurité de l'interface utilisateur Web est extrêmement importante. Si une personne non autorisée obtient l'accès à l'application, elle pourra non seulement modifier vos configurations, mais aussi potentiellement exécuter du code dans le contexte de BunkerWeb (par exemple via une configuration personnalisée contenant du code Lua). Nous vous recommandons vivement de respecter au minimum les bonnes pratiques de sécurité suivantes :

    * Choisissez un mot de passe fort pour la connexion (**au moins 8 caractères, dont 1 lettre minuscule, 1 lettre majuscule, 1 chiffre et 1 caractère spécial**)
    * Placez l'interface utilisateur web sous une URI « difficile à deviner »
    * Activer l'authentification à deux facteurs (2FA)
    * N'exposez pas l'interface utilisateur Web sur Internet sans restrictions supplémentaires
    * Appliquez les bonnes pratiques répertoriées dans la [section Utilisations avancées](advanced.md#security-tuning) de la documentation en fonction de votre cas d'utilisation

## Mise à niveau vers PRO

!!! tip "BunkerWeb PRO essai gratuit"
    Vous souhaitez tester rapidement BunkerWeb PRO pendant un mois ? Utilisez le code `freetrial` lors de votre commande sur le [Panel BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=french&utm_campaign=self&utm_source=doc) ou en cliquant [ici](https://panel.bunkerweb.io/cart.php?language=french&a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) pour appliquer directement le code promo (sera effectif à la caisse).

Une fois que vous avez votre clé de licence PRO à partir du [Panel BunkerWeb](https://panel.bunkerweb.io/?language=french&utm_campaign=self&utm_source=doc), vous pouvez la coller dans la page PRO de l'interface utilisateur Web.

<figure markdown>
  ![PRO upgrade](assets/img/pro-ui-upgrade.png){ align=center, width="700" }
  <figcaption>Mise à niveau vers PRO à partir de l'interface utilisateur Web</figcaption>
</figure>

!!! warning "Temps de mise à niveau"
    La version PRO est téléchargée en arrière-plan par le planificateur, la mise à niveau peut prendre un certain temps.

Lorsque votre instance BunkerWeb aura été mise à niveau vers la version PRO, vous verrez la date d'expiration de votre licence et le nombre maximum de services que vous pouvez protéger.

<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
  <figcaption>Informations sur la licence PRO</figcaption>
</figure>

## Accès aux journaux

À partir de la version `1.6`, la méthode d'accès aux journaux a changé. Cette mise à jour affecte spécifiquement les intégrations basées sur des conteneurs : l'interface utilisateur web lit désormais les fichiers journaux du `/var/log/bunkerweb` répertoire.

Pour que les journaux restent accessibles à partir de l'interface utilisateur Web, nous vous recommandons d'utiliser un serveur syslog, tel que `syslog-ng`, pour lire les journaux et créer les fichiers correspondants dans le `/var/log/bunkerweb` répertoire.

!!! warning "Utilisation du dossier local pour les journaux"
    Pour des raisons de sécurité, l'interface utilisateur web s'exécute en tant que **utilisateur non privilégié avec UID 101 et GID 101** à l'intérieur du conteneur : en cas d'exploitation d'une vulnérabilité, l'attaquant ne disposera pas des privilèges root complets (UID/GID 0).

    Cependant, il y a un inconvénient : si vous utilisez un **dossier local pour les journaux**, vous devez **définir les permissions correctes** afin que l'utilisateur non privilégié puisse lire les fichiers journaux. Par exemple :

    ```shell
    mkdir bw-logs && \
    chown root:101 bw-logs && \
    chmod 770 bw-logs
    ```

    Alternativement, si le dossier existe déjà :

    ```shell
    chown -R root:101 bw-logs && \
    chmod -R 770 bw-logs
    ```

    Si vous utilisez [Docker en mode rootless](https://docs.docker.com/engine/security/rootless) ou [podman](https://podman.io/), les UID et GID dans le conteneur seront mappés sur d'autres valeurs sur l'hôte. Vous devrez d'abord vérifier vos subuid et subgid initiaux :

    ```shell
    grep ^$(whoami): /etc/subuid && \
    grep ^$(whoami): /etc/subgid
    ```

    Par exemple, si vous avez une valeur de **100000**, l'UID/GID mappé sera **100100** (100000 + 100) :

    ```shell
    mkdir bw-logs && \
    sudo chgrp 100100 bw-logs && \
    chmod 770 bw-logs
    ```

    Ou si le dossier existe déjà :

    ```shell
    sudo chgrp -R 100100 bw-logs && \
    sudo chmod -R 770 bw-logs
    ```

### Composez des passe-partout

=== "Docker"

    Pour transférer correctement les journaux vers le répertoire `/var/log/bunkerweb` dans l'intégration Docker, vous devrez rediriger les journaux vers un fichier en utilisant `syslog-ng`. Voici un exemple de comment procéder :

    ```yaml
    x-bw-env: &bw-env
      # We anchor the environment variables to avoid duplication
  API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
  # Jeton API optionnel pour sécuriser l'accès à l'API
  API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Change it to a hard-to-guess URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.5-rc3
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the admin user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

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

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Make sure to set the correct IP address

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"

    Pour transférer correctement les journaux vers le répertoire `/var/log/bunkerweb` dans l'intégration Docker, vous devrez rediriger les journaux vers un fichier en utilisant `syslog-ng`. Voici un exemple de comment procéder :

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog
          options:
            tag: "bunkerweb" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: "" # We don't need to specify the BunkerWeb instance here as they are automatically detected by the autoconf service
          SERVER_NAME: "" # The server name will be filled with services labels
          MULTISITE: "yes" # Mandatory setting for autoconf / ui
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-scheduler" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc3
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375" # This is the Docker socket address
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db
        logging:
          driver: syslog
          options:
            tag: "bw-autoconf" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.5-rc3
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the admin user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        volumes:
          - bw-logs:/var/log/bunkerweb
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme" # Change it to a hard-to-guess URI
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        logging:
          driver: syslog
          options:
            tag: "bw-ui" # This will be the tag used by syslog-ng to create the log file
            syslog-address: "udp://10.20.30.254:514" # This is the syslog-ng container address

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

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: "unless-stopped"
        networks:
          - bw-docker

      bw-syslog:
        image: balabit/syslog-ng:4.9.0
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
          bw-universe:
            ipv4_address: 10.20.30.254 # Make sure to set the correct IP address

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

### Configuration de syslog-ng

Voici un exemple de `syslog-ng.conf` fichier que vous pouvez utiliser pour transférer les journaux vers un fichier :

```conf
@version: 4.8

# Source configuration to receive logs from Docker containers
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Template to format log messages
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Destination configuration to write logs to dynamically named files
destination d_dyna_file {
  file(
    "/var/log/bunkerweb/${PROGRAM}.log"
    template(t_imp)
    owner("101")
    group("101")
    dir_owner("root")
    dir_group("101")
    perm(0440)
    dir_perm(0770)
    create_dirs(yes)
  );
};

# Log path to direct logs to dynamically named files
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Gestion de compte

Vous pouvez accéder à la page de gestion du compte en cliquant sur l'image de profil dans le coin supérieur droit :

<figure markdown>
  ![Vue d'ensemble](assets/img/manage-account.png){ align=center, width="400" }
  <figcaption>Accès à la page du compte depuis le coin supérieur droit</figcaption>
</figure>

### Nom d'utilisateur / Mot de passe

!!! warning "Mot de passe/nom d'utilisateur perdu"

    Si vous avez oublié vos identifiants de l'interface utilisateur, vous pouvez les réinitialiser depuis la ligne de commande en suivant [les étapes décrites dans la section de dépannage](troubleshooting.md#web-ui).

Vous pouvez mettre à jour votre nom d'utilisateur ou votre mot de passe en remplissant les formulaires dédiés dans l'onglet **Sécurité**. Pour des raisons de sécurité, vous devez entrer votre mot de passe actuel même si vous êtes connecté.

Veuillez noter que lorsque votre nom d'utilisateur ou votre mot de passe est mis à jour, vous serez déconnecté de l'interface utilisateur Web pour vous connecter à nouveau.

<figure markdown>
  ![Vue d'ensemble](assets/img/profile-username-password.png){ align=center }
  <figcaption>Formulaire de nom d'utilisateur / Mot de passe</figcaption>
</figure>

### Authentification à deux facteurs

!!! tip "Clés de cryptage obligatoires"

    Lorsque vous activez la 2FA, vous devez fournir au moins une clé de chiffrement. Cette clé sera utilisée pour chiffrer vos secrets TOTP.

    La méthode recommandée pour générer une clé valide est d'utiliser le package `passlib` :

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Placez la clé générée dans la variable d'environnement `TOTP_ENCRYPTION_KEYS` de l'interface Web. Vous pouvez également définir plusieurs clés séparées par des espaces ou sous forme de dictionnaire (pour la rétrocompatibilité).

!!! warning "Clé secrète perdue"

    En cas de perte de votre clé secrète, deux options sont disponibles :

    - Vous pouvez récupérer votre compte à l'aide de l'un des codes de récupération fournis lorsque vous avez activé 2FA (un code de récupération ne peut être utilisé qu'une seule fois).
    - Vous pouvez désactiver 2FA à partir de l'interface de ligne de commande en suivant [les étapes décrites dans la section de dépannage](troubleshooting.md#web-ui).

Vous pouvez renforcer la sécurité de votre connexion en ajoutant ** l'authentification à deux facteurs (2FA)** à votre compte. Ce faisant, un code supplémentaire sera nécessaire en plus de votre mot de passe.

L'interface utilisateur web utilise [ le mot de passe à usage unique basé sur le temps (TOTP)](https://en.wikipedia.org/wiki/Time-based_one-time_password) comme implémentation 2FA : à l'aide d'une **clé secrète**, l'algorithme générera **des mots de passe à usage unique valables uniquement pour une courte période de temps**.

Tout client TOTP tel que Google Authenticator, Authy, FreeOTP, ... Peut être utilisé pour stocker la clé secrète et générer les codes. Veuillez noter qu'une fois TOTP activé, **vous ne pourrez plus le récupérer à partir de l'interface utilisateur Web**.

Les étapes suivantes sont nécessaires pour activer la fonctionnalité TOTP à partir de l'interface utilisateur Web :

- Copiez la clé secrète ou utilisez le code QR sur votre application d'authentification
- Entrez le code TOTP actuel dans la saisie 2FA
- Entrez votre mot de passe actuel

!!! info "Actualisation de la clé secrète"
    Une nouvelle clé secrète est **générée chaque fois que** vous visitez la page ou soumettez le formulaire. En cas de problème (par exemple, un code TOTP expiré), vous devrez copier la nouvelle clé secrète dans votre application d'authentification jusqu'à ce que 2FA soit activé avec succès.

!!! tip "Codes de récupération"

    Lorsque vous activez la 2FA, vous recevrez **5 codes de récupération**. Ces codes peuvent être utilisés pour récupérer votre compte si vous perdez votre clé secrète TOTP. Chaque code ne peut être utilisé qu'une seule fois. **Ces codes ne seront affichés qu'une seule fois, assurez‑vous donc de les conserver dans un endroit sûr.**

    Si vous perdez vos codes de récupération, **vous pouvez les régénérer via la section TOTP de la page de gestion du compte**. Veuillez noter que les anciens codes de récupération seront invalidés.

Vous pouvez activer ou désactiver l'authentification à deux facteurs et actualiser les codes de récupération dans l'onglet **Sécurité** :

<figure markdown>
  ![Vue d'ensemble](assets/img/profile-totp.png){ align=center }
  <figcaption>Formulaires TOTP d'activation/désactivation/actualisation des codes de récupération</figcaption>
</figure>

Une fois la combinaison connexion/mot de passe réussie vous sera demandé de saisir votre code TOTP :

<figure markdown>
  ![Vue d'ensemble](assets/img/profile-2fa.png){ align=center, width="400" }
  <figcaption>2FA sur la page de connexion</figcaption>
</figure>

### Sessions en cours

Dans l' onglet **Session**, vous pourrez lister et révoquer les sessions en cours :

<figure markdown>
  ![Vue d'ensemble](assets/img/sessions.png){ align=center }
  <figcaption>Gérer les sessions</figcaption>
</figure>

## Advanced installation

L'interface utilisateur web peut être déployée et configurée sans passer par l'assistant d'installation : la configuration se fait par le biais de variables d'environnement, qui peuvent être ajoutées directement aux conteneurs ou dans le `/etc/bunkerweb/ui.env` fichier dans le cas d'une intégration Linux.

!!! tip "Variables d'environnement spécifiques à l'interface utilisateur Web"

    L'interface utilisateur Web utilise les variables d'environnement suivantes :

    - `OVERRIDE_ADMIN_CREDS`: définissez-le sur `yes` pour activer le remplacement même si les informations d'identification de l'administrateur sont déjà définies (la valeur par défaut est `no`).
    - `ADMIN_USERNAME`: nom d'utilisateur pour accéder à l'interface web.
    - `ADMIN_PASSWORD`: mot de passe pour accéder à l'interface web.
    - `FLASK_SECRET`: une clé secrète utilisée pour chiffrer le cookie de session (si elle n'est pas définie, une clé aléatoire sera générée).
    - `TOTP_ENCRYPTION_KEYS` (ou `TOTP_SECRETS`) : une liste de clés de chiffrement TOTP séparées par des espaces ou un dictionnaire (par exemple : `{"1": "mysecretkey"}` ou `mysecretkey` ou `mysecretkey mysecretkey1`). **Nous vous recommandons vivement de définir cette variable si vous souhaitez utiliser 2FA, car elle sera utilisée pour chiffrer les clés secrètes TOTP** (si elle n'est pas définie, un nombre aléatoire de clés secrètes sera généré). Pour plus d'informations, consultez la [documentation de passlib](https://passlib.readthedocs.io/en/stable/narr/totp-tutorial.html#application-secrets) .
    - `UI_LISTEN_ADDR` (recommandé) : l'adresse à laquelle l'interface utilisateur web écoutera (par défaut `0.0.0.0` dans les **images Docker** et `127.0.0.1` sur **les installations Linux**). Revient à `LISTEN_ADDR` si non défini.
    - `UI_LISTEN_PORT` (recommandé) : le port sur lequel l'interface utilisateur web écoutera (par défaut `7000`). Revient à `LISTEN_PORT` si non défini.
    - `MAX_WORKERS`: le nombre de workers utilisés par l'interface utilisateur web (la valeur par défaut est le nombre de CPU).
    - `MAX_THREADS`: le nombre de threads utilisés par l'interface utilisateur web (* 2 par défaut `MAX_WORKERS` ).
    - `FORWARDED_ALLOW_IPS`: une liste d'adresses IP ou de réseaux autorisés à être utilisés dans l' `X-Forwarded-For` en-tête (par défaut `*` dans les **images Docker** et `127.0.0.1` sur **les installations Linux**).
    - `CHECK_PRIVATE_IP`: définissez-le sur `yes` pour ne pas déconnecter les utilisateurs dont l'adresse IP a été modifiée au cours d'une session s'ils se trouvent dans un réseau privé (par défaut ). `yes` (Les adresses IP non privées sont toujours vérifiées).
    - `ENABLE_HEALTHCHECK`: définissez-le sur `yes` pour activer le point de `/healthcheck` terminaison qui renvoie une réponse JSON simple avec des informations d'état (la valeur par défaut est `no`).

    L'interface utilisateur Web utilisera ces variables pour vous authentifier et gérer la fonctionnalité 2FA.

!!! example "Génération de secrets recommandés"

    Pour générer un **ADMIN_PASSWORD** valide, nous vous recommandons d'**utiliser un gestionnaire de mots de passe** ou un **générateur de mots de passe**.

    Vous pouvez générer un **FLASK_SECRET** valide en utilisant la commande suivante :

    ```shell
    python3 -c "import secrets; print(secrets.token_hex(64))"
    ```

    Vous pouvez générer des **TOTP_ENCRYPTION_KEYS** valides, séparées par des espaces, en utilisant la commande suivante (le paquet `passlib` est requis) :

    ```shell
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

=== "Linux"

    L'installation de l'interface utilisateur Web via l'[intégration Linux](integrations.md#linux) est assez simple puisqu'elle est installée avec BunkerWeb.

    L'interface utilisateur est fournie en tant que service systemd nommé `bunkerweb-ui`. Veuillez vous assurer qu'il est activé :

    ```shell
    sudo systemctl enable bunkerweb-ui && \
    sudo systemctl status bunkerweb-ui
    ```

    Un fichier d'environnement dédié situé dans `/etc/bunkerweb/ui.env` est utilisé pour configurer l'interface utilisateur :

    ```conf
    ADMIN_USERNAME=changeme
    ADMIN_PASSWORD=changeme
    TOTP_ENCRYPTION_KEYS=mysecret
    ```

    Remplacez les valeurs `changeme` par vos propres valeurs.

    Pensez à définir une clé secrète plus robuste pour `TOTP_ENCRYPTION_KEYS`.

    Chaque fois que vous modifiez le fichier `/etc/bunkerweb/ui.env`, vous devez redémarrer le service :

    ```shell
    systemctl restart bunkerweb-ui
    ```

    L'accès à l'interface utilisateur via BunkerWeb se fait via une configuration classique de [proxy inverse](quickstart-guide.md). Notez que l'interface écoute sur le port `7000` et uniquement sur l'interface de loopback.

    Voici le modèle `/etc/bunkerweb/variables.env` que vous pouvez utiliser :

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_TEMPLATE=ui
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/changeme
    www.example.com_REVERSE_PROXY_HOST=http://127.0.0.1:7000
    ```

    Don't forget to reload the `bunkerweb` service:

    ```shell
    systemctl reload bunkerweb
    ```

=== "Docker"

    L'interface Web peut être déployée en utilisant un conteneur dédié disponible sur [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) :

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Sinon, vous pouvez aussi le construire vous‑même :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    L'accès à l'interface Web via BunkerWeb se fait par une configuration classique de [proxy inverse](quickstart-guide.md). Nous vous recommandons de connecter BunkerWeb et l'interface Web via un réseau dédié (par exemple `bw-universe`, également utilisé par le planificateur) afin qu'ils ne soient pas sur le même réseau que vos services Web, pour des raisons de sécurité évidentes. Notez que le conteneur de l'interface écoute sur le port `7000`.

    !!! info "Backend de base de données"

        Si vous souhaitez utiliser un backend de base de données autre que MariaDB, consultez les fichiers docker-compose dans le dossier [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc3/misc/integrations) du dépôt.

    Voici le modèle docker-compose que vous pouvez utiliser (n'oubliez pas de modifier les valeurs `changeme`) :

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # We mirror the API_WHITELIST_IP from the bunkerweb service
          API_TOKEN: "" # Miroir du API_TOKEN si vous l'utilisez
          SERVE_FILES: "no"
          DISABLE_DEFAULT_SERVER: "yes"
          USE_CLIENT_CACHE: "yes"
          USE_GZIP: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Remember to set a stronger URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000" # The web UI container is listening on the 7000 port by default
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.5-rc3
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        networks:
          - bw-universe
          - bw-db

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
      bw-db:
        name: bw-db
    ```

=== "Docker autoconf"

    L'interface Web peut être déployée en utilisant un conteneur dédié disponible sur [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui):

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativement, vous pouvez aussi le construire vous‑même :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    !!! tip "Variables d'environnement"

        Veuillez lire la section [Prérequis](#prerequisites) pour consulter toutes les variables d'environnement que vous pouvez définir pour personnaliser l'interface Web.

    L'accès à l'interface Web via BunkerWeb se fait par une configuration classique de [proxy inverse](quickstart-guide.md). Nous vous recommandons de connecter BunkerWeb et l'interface Web via un réseau dédié (comme `bw-universe` utilisé également par le planificateur et l'autoconf) afin qu'ils ne se trouvent pas sur le même réseau que vos services Web, pour des raisons de sécurité évidentes. Veuillez noter que le conteneur de l'interface Web écoute sur le port `7000`.

    !!! info "Backend de base de données"

        Si vous souhaitez utiliser un backend de base de données autre que MariaDB, consultez les fichiers docker-compose dans le dossier [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc3/misc/integrations) du dépôt.

    Voici le modèle docker-compose que vous pouvez utiliser (n'oubliez pas de modifier les valeurs `changeme`) :

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        labels:
          - "bunkerweb.INSTANCE=yes" # We set the instance label to allow the autoconf to detect the instance
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc3
        depends_on:
          - bw-docker
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
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
        networks:
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.5-rc3
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_TEMPLATE=ui"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/changeme"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"
        networks:
          - bw-universe
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

=== "Kubernetes"

    L'interface Web peut être déployée à l'aide d'un conteneur dédié disponible sur [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) et vous pouvez la déployer comme un Deployment Kubernetes standard (voir la documentation sur les Deployments).

    L'accès à l'interface Web via BunkerWeb se fait par une configuration classique de [proxy inverse](quickstart-guide.md). La segmentation réseau entre l'interface Web et les services web n'est pas couverte par cette documentation. Veuillez noter que le conteneur de l'interface Web écoute sur le port `7000`.

    !!! info "Backend de base de données"

        Si vous souhaitez utiliser un backend de base de données autre que MariaDB, consultez les fichiers YAML dans le dossier [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc3/misc/integrations) du dépôt.

    Voici la partie correspondante de votre fichier values.yaml que vous pouvez utiliser :

    ```yaml
    settings:
      # Use an existing secret named bunkerweb and containing the following values:
      # - admin-username
      # - admin-password
      # - flask-secret
      # - totp-secrets
      existingSecret: "secret-bunkerweb"
    ui:
      wizard: false
      ingress:
        enabled: true
        serverName: "www.example.com"
        serverPath: "/admin"
      overrideAdminCreds: "yes"
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    L'interface Web peut être déployée en utilisant un conteneur dédié disponible sur [Docker Hub](https://hub.docker.com/r/bunkerity/bunkerweb-ui) :

    ```shell
    docker pull bunkerity/bunkerweb-ui
    ```

    Alternativement, vous pouvez aussi la construire vous‑même :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb.git && \
    cd bunkerweb && \
    docker build -t my-bunkerweb-ui -f src/ui/Dockerfile .
    ```

    L'accès à l'interface Web via BunkerWeb se fait par une configuration classique de [proxy inverse](quickstart-guide.md). Nous vous recommandons de connecter BunkerWeb et l'interface Web via un réseau dédié (par exemple `bw-universe`, également utilisé par le planificateur et l'autoconf) afin qu'ils ne soient pas sur le même réseau que vos services Web, pour des raisons de sécurité évidentes. Notez que le conteneur de l'interface Web écoute sur le port `7000`.

    !!! info "Backend de base de données"

        Si vous souhaitez utiliser un backend de base de données autre que MariaDB, veuillez consulter les fichiers de stack dans le dossier [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc3/misc/integrations) du dépôt.

    Voici le modèle de stack que vous pouvez utiliser (n'oubliez pas de modifier les valeurs `changeme`) :

    ```yaml
    x-ui-env: &ui-env
      # We anchor the environment variables to avoid duplication
      SWARM_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc3
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
            protocol: udp # For QUIC / HTTP3 support
        environment:
          SWARM_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        networks:
          - bw-universe
          - bw-services
        deploy:
          mode: global
          placement:
            constraints:
              - "node.role == worker"
          labels:
            - "bunkerweb.INSTANCE=yes"

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
        environment:
          <<: *ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "bw-redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc3
        environment:
          <<: *ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONFIGS: "1"
          CONTAINERS: "1"
          SERVICES: "1"
          SWARM: "1"
          TASKS: "1"
          LOG_LEVEL: "warning"
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
        networks:
          - bw-db

      bw-redis:
        image: redis:7-alpine
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.5-rc3
        environment:
          <<: *ui-env
          ADMIN_USERNAME: "changeme"
          ADMIN_PASSWORD: "changeme" # Remember to set a stronger password for the changeme user
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        networks:
          - bw-universe
          - bw-db
        deploy:
          labels:
            - "bunkerweb.SERVER_NAME=www.example.com"
            - "bunkerweb.USE_TEMPLATE=ui"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_URL=/changeme"
            - "bunkerweb.REVERSE_PROXY_HOST=http://bw-ui:7000"

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

## Prise en charge linguistique et localisation

L'interface utilisateur de BunkerWeb prend en charge plusieurs langues. Les traductions sont gérées dans l' `src/ui/app/static/locales` annuaire. Les langues suivantes sont actuellement disponibles :

- Français (en)
- Français (fr)
- Arabe (ar)
- Bengali (bn)
- Français (en)
- Hindi (hi)
- Portugais (pt)
- Russe (ru)
- L'ourdou (votre)
- Chinois (zh)
- Allemand (de)
- Italien (it)

Consultez [locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.5-rc3/src/ui/app/static/locales/README.md) pour plus de détails sur la provenance des traductions et l'état de la révision.

### Traduction contributive

Nous accueillons les contributions pour améliorer ou ajouter de nouveaux fichiers de locale !

**Comment contribuer à une traduction :**

1. Modifiez le `src/ui/app/lang_config.py` fichier pour ajouter votre langue (code, nom, drapeau, english_name).
2. Copiez `en.json` en tant que modèle dans `src/ui/app/static/locales/`, renommez-le avec votre code de langue (par exemple, `de.json` pour l'allemand).
3. Traduisez les valeurs de votre nouveau fichier.
4. Mettez à jour le tableau pour `locales/README.md` ajouter votre langue et indiquez qui l'a créé/révisé.
5. Envoyez une demande de tirage.

Pour les mises à jour, modifiez le fichier concerné et mettez à jour la table de provenance si nécessaire.

Voir [le locales/README.md](https://github.com/bunkerity/bunkerweb/raw/v1.6.5-rc3/src/ui/app/static/locales/README.md) pour les directives complètes.
