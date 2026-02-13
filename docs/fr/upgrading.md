# Mise à niveau

## Mise à niveau à partir de la version 1.6.X

### Procédure

#### Docker

1. **Sauvegardez la base de données** :

    - Avant de procéder à la mise à niveau de la base de données, assurez-vous d'effectuer une sauvegarde complète de l'état actuel de la base de données.
    - Utilisez les outils appropriés pour sauvegarder l'intégralité de la base de données, y compris les données, les schémas et les configurations.

    ```bash
    docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
    ```

    ```bash
    docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
    ```

2. **Mettre à niveau BunkerWeb** :
    - Mettez à niveau BunkerWeb vers la dernière version.
        1. **Mettre à jour le fichier Docker Compose **: Mettez à jour le fichier Docker Compose pour utiliser la nouvelle version de l'image BunkerWeb.
            ```yaml
            services:
                bunkerweb:
                    image: bunkerity/bunkerweb:1.6.8
                    ...
                bw-scheduler:
                    image: bunkerity/bunkerweb-scheduler:1.6.8
                    ...
                bw-autoconf:
                    image: bunkerity/bunkerweb-autoconf:1.6.8
                    ...
                bw-ui:
                    image: bunkerity/bunkerweb-ui:1.6.8
                    ...
            ```

        2. **Redémarrer les conteneurs **: redémarrez les conteneurs pour appliquer les modifications.
            ```bash
            docker compose down
            docker compose up -d
            ```

3. **Vérifier les journaux **: vérifiez les journaux du service de planification pour vous assurer que la migration a réussi.

    ```bash
    docker compose logs <scheduler_container>
    ```

4. **Vérifier la base de données **: vérifiez que la mise à niveau de la base de données a réussi en vérifiant les données et les configurations dans le nouveau conteneur de base de données.

#### Linux

=== "Mise à niveau facile à l'aide du script d'installation"

    * **Démarrage rapide** :

        Pour commencer, téléchargez le script d'installation et sa somme de contrôle, puis vérifiez l'intégrité du script avant de l'exécuter.

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

        # Download the script and its checksum
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # Verify the checksum
        sha256sum -c install-bunkerweb.sh.sha256

        # If the check is successful, run the script
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "Avis de sécurité"
            **Vérifiez toujours l'intégrité du script d'installation avant de l'exécuter.**

            Téléchargez le fichier de somme de contrôle et utilisez un outil comme `sha256sum` pour confirmer que le script n'a pas été modifié ou altéré.

            Si la vérification de la somme échoue, **n'exécutez pas le script** — il pourrait être dangereux.

      * **Comment ça marche** :

        Le même script d'installation polyvalent utilisé pour les nouvelles installations peut également effectuer une mise à niveau sur place. Lorsqu'il détecte une installation existante et une version cible différente, il passe en mode mise à niveau et applique le flux de travail suivant :

        1. Détection et validation
            * Détecte le système d'exploitation / la version et confirme la matrice de support.
            * Lit la version BunkerWeb actuellement installée à partir de `/usr/share/bunkerweb/VERSION`.
        2. Décision du scénario de mise à niveau
            * Si la version demandée est égale à celle installée, elle abandonne (sauf si vous la réexécutez explicitement pour l'état).
            * Si les versions diffèrent, il signale une mise à niveau.
        3. (Facultatif) Sauvegarde automatique de pré-mise à niveau
            * Si `bwcli` le planificateur est disponible et que la sauvegarde automatique est activée, il crée une sauvegarde via le plugin de sauvegarde intégré.
            * Destination : soit le répertoire que vous avez fourni, `--backup-dir` soit un chemin généré tel que `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
            * Vous pouvez désactiver cela avec `--no-auto-backup` (la sauvegarde manuelle devient alors de votre responsabilité).
        4. Repos du service
            * Arrête `bunkerweb`, `bunkerweb-ui`et `bunkerweb-scheduler` pour assurer une mise à niveau cohérente (correspond aux recommandations de la procédure manuelle).
        5. Suppression des verrous de colis
            * Supprime temporairement `apt-mark hold` / `dnf versionlock` active `bunkerweb` et `nginx` permet ainsi d'installer la version ciblée.
        6. Exécution de la mise à niveau
            * Installe uniquement la nouvelle version du package BunkerWeb (NGINX n'est pas réinstallé en mode de mise à niveau à moins qu'il ne soit manquant - cela évite de toucher à un NGINX correctement épinglé).
            * Réapplique les blocages/verrous de version pour geler les versions mises à niveau.
        7. Finalisation et état d'avancement
            * Affiche l'état de systemd pour les services principaux et les étapes suivantes.
            * Laisse votre configuration et votre base de données intactes : seuls le code de l'application et les fichiers gérés sont mis à jour.

        Comportements clés / notes :

        * Le script ne modifie PAS le `/etc/bunkerweb/variables.env` contenu de votre base de données.
        * Si la sauvegarde automatique a échoué (ou a été désactivée), vous pouvez toujours effectuer une restauration manuelle à l'aide de la section Restauration ci-dessous.
        * Le mode de mise à niveau évite intentionnellement de réinstaller ou de rétrograder NGINX en dehors de la version épinglée prise en charge déjà présente.
        * Les journaux de dépannage restent dans `/var/log/bunkerweb/`.

    * **Comportement selon le mode** :

        - Le programme d'installation réutilise la même logique de sélection de mode pendant une mise à jour : le mode manager garde l'assistant désactivé, attache l'API à `0.0.0.0` et exige une IP à placer sur liste blanche (à fournir avec `--manager-ip` pour les exécutions non interactives), tandis que le mode worker impose toujours la liste d'IP du manager.
        - Les mises à jour Manager peuvent décider de démarrer ou non le service Web UI, et le récapitulatif mentionne explicitement l'état du service API afin de pouvoir le contrôler via `--api` / `--no-api`.
        - Les options CrowdSec restent réservées aux mises à jour full stack et le script continue de valider le système d'exploitation et l'architecture CPU avant de toucher aux paquets, les combinaisons non prises en charge nécessitant toujours `--force`.

        Résumé du retour en arrière :

        * Utilisez le répertoire de sauvegarde généré (ou votre sauvegarde manuelle) + les étapes de la section Rollback pour restaurer la base de données, puis réinstallez la version précédente de l'image/du paquet et verrouillez à nouveau les paquets.

    *  **Options de ligne de commande** :

        Vous pouvez effectuer des mises à niveau sans assistance avec les mêmes indicateurs que ceux utilisés pour l'installation. Les plus pertinents pour les mises à niveau :

        | Option                  | But                                                                                                                           |
        | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
        | `-v, --version <X.Y.Z>` | Ciblez la version de BunkerWeb à mettre à niveau.                                                                             |
        | `-y, --yes`             | Non interactif (suppose la confirmation de la mise à niveau et active la sauvegarde automatique, sauf si `--no-auto-backup`). |
        | `--backup-dir <PATH>`   | Destination de la sauvegarde automatique de pré-mise à niveau. Créé s'il est manquant.                                        |
        | `--no-auto-backup`      | Ignorez la sauvegarde automatique (NON recommandé). Vous devez disposer d'une sauvegarde manuelle.                            |
        | `-q, --quiet`           | Suppression de la sortie (combinée avec l'enregistrement/la surveillance).                                                    |
        | `-f, --force`           | Procédez sur une version du système d'exploitation non prise en charge.                                                       |
        | `--dry-run`             | Affichez l'environnement détecté, les actions prévues, puis quittez sans rien modifier.                                       |

        Exemples:

        ```bash
        # Upgrade to 1.6.8 interactively (will prompt for backup)
        sudo ./install-bunkerweb.sh --version 1.6.8

        # Non-interactive upgrade with automatic backup to custom directory
        sudo ./install-bunkerweb.sh -v 1.6.8 --backup-dir /var/backups/bw-2025-01 -y

        # Silent unattended upgrade (logs suppressed) – relies on default auto-backup
        sudo ./install-bunkerweb.sh -v 1.6.8 -y -q

        # Perform a dry run (plan) without applying changes
        sudo ./install-bunkerweb.sh -v 1.6.8 --dry-run

        # Upgrade skipping automatic backup (NOT recommended)
        sudo ./install-bunkerweb.sh -v 1.6.8 --no-auto-backup -y
        ```

        !!! warning "Sauter les sauvegardes"
            L'utilisation `--no-auto-backup` sans sauvegarde manuelle vérifiée peut entraîner une perte de données irréversible si la mise à niveau rencontre des problèmes. Conservez toujours au moins une sauvegarde récente et testée.

=== "Manuel"

    1. **Sauvegardez la base de données** :

        - Avant de procéder à la mise à niveau de la base de données, assurez-vous d'effectuer une sauvegarde complète de l'état actuel de la base de données.
        - Utilisez les outils appropriés pour sauvegarder l'intégralité de la base de données, y compris les données, les schémas et les configurations.

        ??? warning "Informations pour les utilisateurs de Red Hat Enterprise Linux (RHEL) 8.10"
            Si vous utilisez **RHEL 8.10** et prévoyez d'utiliser une **base de données externe**, vous devrez installer le paquet `mysql-community-client` pour vous assurer que la commande `mysqldump` est disponible. Vous pouvez installer le paquet en exécutant les commandes suivantes :

            === "MySQL/MariaDB"

                1. **Installez le paquet de configuration du dépôt MySQL**

                    ```bash
                    sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                    ```

                2. **Activez le dépôt MySQL**

                    ```bash
                    sudo dnf config-manager --enable mysql80-community
                    ```

                3. **Installez le client MySQL**

                    ```bash
                    sudo dnf install mysql-community-client
                    ```

            === "PostgreSQL"

                1. **Installer le paquet de configuration du dépôt PostgreSQL**

                    ```bash
                    dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                    ```

                2. **Installer le client PostgreSQL**

                    ```bash
                    dnf install postgresql<version>
                    ```

        ```bash
        BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
        ```

    2. **Mettre à niveau BunkerWeb** :
        - Mettez à niveau BunkerWeb vers la dernière version.

            1. **Arrêtez les services** :
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            2. **Mettre à jour BunkerWeb** :

                === "Debian/Ubuntu"

                    Tout d'abord, si vous avez précédemment marqué le paquet BunkerWeb comme mis en attente, annulez cette mise en attente :

                    Vous pouvez afficher la liste des paquets en attente avec `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Ensuite, vous pouvez mettre à jour le paquet BunkerWeb :

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.8
                    ```

                    Pour empêcher le paquet BunkerWeb d'être mis à niveau lors de l'exécution de `apt upgrade`, vous pouvez utiliser la commande suivante :

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    Plus de détails dans la page [intégration Linux](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    Tout d'abord, si vous avez précédemment marqué le paquet BunkerWeb comme mis en attente, annulez cette mise en attente :

                    Vous pouvez afficher la liste des paquets en attente avec `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Ensuite, vous pouvez mettre à jour le paquet BunkerWeb :

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.8
                    ```

                    Pour empêcher le paquet BunkerWeb d'être mis à niveau lors de l'exécution de `dnf upgrade`, vous pouvez utiliser la commande suivante :

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    Plus de détails dans la page [intégration Linux](integrations.md#__tabbed_1_3).

            3. **Démarrez les services** :
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-ui
                    sudo systemctl start bunkerweb-scheduler
                    ```
                    Ou redémarrez le système :
                    ```bash
                    sudo reboot
                    ```


    3. **Vérifier les journaux **: vérifiez les journaux du service de planification pour vous assurer que la migration a réussi.

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

    4. **Vérifier la base de données **: vérifiez que la mise à niveau de la base de données a réussi en vérifiant les données et les configurations dans le nouveau conteneur de base de données.

### Rollback

!!! failure "En cas de problèmes"

    Si vous rencontrez des problèmes lors de la mise à niveau, vous pouvez revenir à la version précédente de la base de données en restaurant la sauvegarde effectuée à l’étape [1](#__tabbed_1_1).

    Obtenez de l’aide et plus d’informations :

    - [Commander une assistance professionnelle](https://panel.bunkerweb.io/?language=french&utm_source=doc&utm_campaign=self)
    - [Créer un problème sur GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Rejoignez le serveur Discord de BunkerWeb](https://discord.bunkerity.com)

=== "Docker"

    1. **Extrayez la sauvegarde si elle est compressée**.

        Extrayez d'abord le fichier de sauvegarde compressé :

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restaurez la sauvegarde**.

        === "SQLite"

            1. **Supprimez le fichier de base de données existant.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restaurez la sauvegarde.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Corrigez les permissions.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Arrêtez la pile.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restaurez la sauvegarde.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Arrêtez la pile.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Supprimez la base de données existante.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Recréez la base de données.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restaurez la sauvegarde.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Arrêtez la pile.**

                ```bash
                docker compose down
                ```

    3. **Rétrograder BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Démarrez les conteneurs**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extrayez la sauvegarde si elle est compressée**.

        Extrayez d'abord le fichier zip de sauvegarde :

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Arrêtez les services**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Restaurez la sauvegarde**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Supprimez la base de données existante.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Recréez la base de données.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restaurez la sauvegarde.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Démarrez les services**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Rétrograder BunkerWeb**.
        - Rétrogradez BunkerWeb vers la version précédente en suivant les mêmes étapes que lors de la mise à niveau de BunkerWeb dans la [page d'intégration Linux](integrations.md#linux)

## Mise à niveau à partir de la version 1.5.X

### Qu'est-ce qui a changé ?

#### Programmateur

Contrairement aux versions 1.5.X, le service Scheduler n' **utilise plus le *proxy de la socket docker* pour récupérer les instances de BunkerWeb**. Au lieu de cela, il utilise la nouvelle `BUNKERWEB_INSTANCES` variable d'environnement.

!!! info "À propos de la `BUNKERWEB_INSTANCES` variable d'environnement"

    Cette nouvelle variable est une liste d'instances BunkerWeb séparées par des espaces, au format suivant : `http://bunkerweb:5000 bunkerweb1:5000 bunkerweb2:5000 ...`. Le planificateur utilisera ensuite cette liste pour récupérer et envoyer la configuration aux instances.

    * Le `http://` préfixe est facultatif.
    * Le port est facultatif et utilise par défaut la valeur de la variable d' `API_HTTP_PORT` environnement.
    * La valeur par défaut de la `BUNKERWEB_INSTANCES` variable d'environnement est `127.0.0.1`.

En d'autres termes, le nouveau système est totalement agnostique et générique : le planificateur est en charge de la gestion d'une liste d'instances BunkerWeb et n'a pas besoin de se soucier de l'environnement.

!!! tip "Intégrations Autoconf/Kubernetes/Swarm"

    Si vous utilisez les intégrations `Autoconf`, `Kubernetes` ou `Swarm`, vous pouvez définir la variable d'environnement `BUNKERWEB_INSTANCES` sur une chaîne vide (afin qu'elle n'essaie pas d'envoyer la configuration à la valeur par défaut `127.0.0.1`).

    **Les instances seront récupérées automatiquement par le contrôleur**. Vous pouvez également ajouter des instances personnalisées à la liste qui pourraient ne pas être détectées par le contrôleur.

Depuis le `1.6`, le planificateur dispose également d'un nouveau [système de vérification de l'état intégré](concepts.md), qui vérifiera l'état des instances. Si une instance devient défectueuse, le planificateur cessera de lui envoyer la configuration. Si l'instance redevient saine, le planificateur recommence à lui envoyer la configuration.

#### Conteneur BunkerWeb

Un autre changement important est que les **paramètres** qui étaient précédemment déclarés sur le conteneur BunkerWeb **sont désormais déclarés sur le planificateur**. Cela signifie que vous devrez déplacer vos paramètres du conteneur BunkerWeb vers le conteneur Scheduler.

Bien que les paramètres soient maintenant déclarés sur le conteneur du planificateur, **vous devrez toujours déclarer les paramètres obligatoires liés à l'API sur le conteneur BunkerWeb**, comme le paramètre `API_WHITELIST_IP` utilisé pour mettre en liste blanche l'adresse IP du planificateur, afin qu'il puisse envoyer la configuration à l'instance. Si vous utilisez `API_TOKEN`, vous devez également le définir sur le conteneur BunkerWeb (et le refléter sur le Scheduler) pour autoriser les appels API authentifiés.

!!! warning "Paramètres du conteneur de BunkerWeb"

    Tous les paramètres liés à l'API que vous déclarez sur le conteneur BunkerWeb doivent également être répliqués sur le conteneur du planificateur afin qu'ils continuent de fonctionner, car la configuration sera écrasée par celle générée par le planificateur.

#### Valeurs par défaut et nouveaux paramètres

Nous avons fait de notre mieux pour ne pas changer la valeur par défaut, mais nous avons ajouté de nombreux autres paramètres. Il est fortement recommandé de lire les sections sur le [réglage de la sécurité ](advanced.md#security-tuning) et  les [paramètres](features.md) de la documentation.

#### Modèles

Nous avons ajouté une nouvelle fonctionnalité appelée **modèles**. Les modèles fournissent une approche structurée et standardisée de la définition des paramètres et des configurations personnalisées, consultez la [ section concepts/modèles](concepts.md#templates) pour plus d'informations.

#### Espaces de noms Autoconf

Nous avons ajouté une fonctionnalité d**'espace de noms** aux intégrations autoconf. Les espaces de noms vous permettent de regrouper vos instances et d'appliquer des paramètres uniquement à celles-ci. Pour plus d'informations, consultez les sections suivantes en fonction de votre intégration :

- [Autoconf/espaces de noms](integrations.md#namespaces)
- [Kubernetes/espaces de noms](integrations.md#namespaces_1)
- [Swarm/espaces de noms](integrations.md#namespaces_2)

### Procédure

1. **Sauvegardez la base de données** :
      - Avant de procéder à la mise à niveau de la base de données, assurez-vous d'effectuer une sauvegarde complète de l'état actuel de la base de données.
      - Utilisez les outils appropriés pour sauvegarder l'intégralité de la base de données, y compris les données, les schémas et les configurations.

    === "1\.5\.7 et après"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        === "Linux"

            ??? warning "Informations pour les utilisateurs de Red Hat Enterprise Linux (RHEL) 8.10"
                Si vous utilisez **RHEL 8.10** et prévoyez d'utiliser une **base de données externe**, vous devrez installer le paquet `mysql-community-client` afin que la commande `mysqldump` soit disponible. Vous pouvez installer le paquet en exécutant les commandes suivantes :

                === "MySQL/MariaDB"

                    1. **Installez le paquet de configuration du dépôt MySQL**

                        ```bash
                        sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                        ```

                    2. **Activez le dépôt MySQL**

                        ```bash
                        sudo dnf config-manager --enable mysql80-community
                        ```

                    3. **Installez le client MySQL**

                        ```bash
                        sudo dnf install mysql-community-client
                        ```

                === "PostgreSQL"

                    1. **Installez le paquet de configuration du dépôt PostgreSQL**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    2. **Installez le client PostgreSQL**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

    === "1\.5\.6 et avant"

        === "SQLite"

            === "Docker"

                Nous devons d'abord installer le paquet `sqlite` dans le conteneur.

                ```bash
                docker exec -u 0 -it <scheduler_container> apk add sqlite
                ```

                Ensuite, sauvegardez la base de données.

                ```bash
                docker exec -it <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

        === "MariaDB"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "MySQL"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it -e PGPASSWORD=<database_password> <database_container> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                PGPASSWORD=<database_password> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

2. **Mettre à niveau BunkerWeb** :
      - Mettez à niveau BunkerWeb vers la dernière version.

        === "Docker"

            1. **Mettre à jour le fichier Docker Compose** : Mettez à jour le fichier Docker Compose pour utiliser la nouvelle version de l'image BunkerWeb.
                ```yaml
                services:
                    bunkerweb:
                        image: bunkerity/bunkerweb:1.6.8
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.6.8
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.6.8
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.6.8
                        ...
                ```

            2. **Redémarrer les conteneurs** : Redémarrez les conteneurs pour appliquer les modifications.
                ```bash
                docker compose down
                docker compose up -d
                ```

        === "Linux"

            3. **Arrêtez les services**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                ```

            4. **Mettre à jour BunkerWeb** :

                === "Debian/Ubuntu"

                    Tout d'abord, si vous avez précédemment marqué le paquet BunkerWeb comme mis en attente, annulez cette mise en attente :

                    Vous pouvez afficher la liste des paquets en attente avec `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Ensuite, vous pouvez mettre à jour le paquet BunkerWeb :

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.6.8
                    ```

                    Pour empêcher le paquet BunkerWeb d'être mis à niveau lors de l'exécution de `apt upgrade`, vous pouvez utiliser la commande suivante :

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    Plus de détails dans la page [intégration Linux](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    Tout d'abord, si vous avez précédemment verrouillé (mis en attente) le paquet BunkerWeb, annulez ce verrouillage :

                    Vous pouvez afficher la liste des paquets verrouillés avec `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Ensuite, vous pouvez mettre à jour le paquet BunkerWeb :

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.6.8
                    ```

                    Pour empêcher le paquet BunkerWeb d'être mis à niveau lors de l'exécution de `dnf upgrade`, vous pouvez utiliser la commande suivante :

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    Plus de détails dans la page [intégration Linux](integrations.md#__tabbed_1_3).

            5. **Démarrer les services** :
                ```bash
                sudo systemctl start bunkerweb
                sudo systemctl start bunkerweb-ui
                sudo systemctl start bunkerweb-scheduler
                ```
                Ou redémarrez le système :
                ```bash
                sudo reboot
                ```


3. **Vérifier les journaux **: vérifiez les journaux du service de planification pour vous assurer que la migration a réussi.

    === "Docker"

        ```bash
        docker compose logs <scheduler_container>
        ```

    === "Linux"

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

4. **Vérifier la base de données **: vérifiez que la mise à niveau de la base de données a réussi en vérifiant les données et les configurations dans le nouveau conteneur de base de données.

### Rollback

!!! failure "En cas de problèmes"

    Si vous rencontrez des problèmes lors de la mise à niveau, vous pouvez revenir à la version précédente de la base de données en restaurant la sauvegarde effectuée à l'étape [1](#__tabbed_1_1).

    Obtenez de l'aide et plus d'informations :

    - [Commander une assistance professionnelle](https://panel.bunkerweb.io/?language=french&utm_source=doc&utm_campaign=self)
    - [Créer un problème sur GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Rejoignez le serveur Discord de BunkerWeb](https://discord.bunkerity.com)

=== "Docker"

    1. **Extrayez la sauvegarde si elle est compressée**.

        Extrayez d'abord le fichier zip de sauvegarde :

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restaurez la sauvegarde**.

        === "SQLite"

            1. **Supprimez le fichier de base de données existant.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restaurez la sauvegarde.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Corrigez les permissions.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Arrêtez la pile.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            5. **Restaurez la sauvegarde.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            6. **Arrêtez la pile.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            7. **Supprimez la base de données existante.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            8. **Recréez la base de données.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            9. **Restaurez la sauvegarde.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            10. **Arrêtez la pile.**

                ```bash
                docker compose down
                ```

    3. **Rétrograder BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Démarrez les conteneurs**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extrayez la sauvegarde si elle est compressée**.

        Extrayez d'abord le fichier zip de sauvegarde :

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Arrêtez les services**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    6. **Restaurez la sauvegarde**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Supprimez la base de données existante.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Recréez la base de données.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restaurez la sauvegarde.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Démarrez les services**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-ui bunkerweb-scheduler
        ```

    8. **Rétrograder BunkerWeb**.
        - Rétrogradez BunkerWeb vers la version précédente en suivant les mêmes étapes que lors de la mise à niveau de BunkerWeb dans la [page d'intégration Linux](integrations.md#linux)
