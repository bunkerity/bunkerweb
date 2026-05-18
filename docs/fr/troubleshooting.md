# Dépannage

!!! info "BunkerWeb Panel"
    Si vous n'êtes pas en mesure de résoudre votre problème, vous pouvez [nous contacter directement via notre panel](https://panel.bunkerweb.io/?language=french&utm_campaign=self&utm_source=doc). Celle-ci centralise toutes les demandes liées à la solution BunkerWeb.

## Journaux

Lors du dépannage, les journaux sont vos meilleurs amis. Nous faisons de notre mieux pour fournir des journaux conviviaux pour vous aider à comprendre ce qui se passe.

Veuillez noter que vous pouvez définir `LOG_LEVEL` le sur `info` (par défaut : `notice`) pour augmenter la verbosité de BunkerWeb.

Voici comment vous pouvez accéder aux logs, en fonction de votre intégration :

=== "Docker"

    !!! tip "Lister les conteneurs"
        Pour lister les conteneurs en cours d'exécution, vous pouvez utiliser la commande suivante :
        ```shell
        docker ps
        ```

    Vous pouvez utiliser la commande `docker logs` (remplacez `bunkerweb` par le nom de votre conteneur) :
    ```shell
    docker logs bunkerweb
    ```

    Voici l'équivalent docker-compose (remplacez `bunkerweb` par le nom du service déclaré dans le fichier docker-compose.yml) :
    ```shell
    docker-compose logs bunkerweb
    ```

=== "Docker autoconf"

    !!! tip "Lister les conteneurs"
        Pour lister les conteneurs en cours d'exécution, vous pouvez utiliser la commande suivante :
        ```shell
        docker ps
        ```

    Vous pouvez utiliser la commande `docker logs` (remplacez `bunkerweb` et `bw-autoconf` par le nom de vos conteneurs) :
    ```shell
    docker logs bunkerweb
    docker logs bw-autoconf
    ```

    Voici l'équivalent docker-compose (remplacez `bunkerweb` et `bw-autoconf` par le nom des services déclarés dans le fichier docker-compose.yml) :
    ```shell
    docker-compose logs bunkerweb
    docker-compose logs bw-autoconf
    ```

=== "Tout-en-un"

    !!! tip "Nom du conteneur"
        Le nom de conteneur par défaut pour l'image All-in-one est `bunkerweb-aio`. Si vous avez utilisé un nom différent, ajustez la commande en conséquence.

    Vous pouvez utiliser la commande `docker logs` :
    ```shell
    docker logs bunkerweb-aio
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    !!! tip "Lister les services"
        Pour lister les services, vous pouvez utiliser la commande suivante :
        ```shell
        docker service ls
        ```

    Vous pouvez utiliser la commande `docker service logs` (remplacez `bunkerweb` et `bw-autoconf` par le nom de vos services) :
    ```shell
    docker service logs bunkerweb
    docker service logs bw-autoconf
    ```

=== "Kubernetes"

    !!! tip "Lister les pods"
        Pour lister les pods, vous pouvez utiliser la commande suivante :
        ```shell
        kubectl get pods
        ```

    Vous pouvez utiliser la commande `kubectl logs` (remplacez `bunkerweb` et `bunkerweb-controler` par le nom de vos pods) :
        ```shell
        kubectl logs bunkerweb
        kubectl logs bunkerweb-controler
        ```

=== "Linux"

    Pour les erreurs liées aux services BunkerWeb (par exemple, ne démarre pas), vous pouvez utiliser `journalctl` :
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Les journaux courants sont situés dans le répertoire `/var/log/bunkerweb` :
    ```shell
    cat /var/log/bunkerweb/error.log
    cat /var/log/bunkerweb/access.log
    ```

## Autorisations

N'oubliez pas que BunkerWeb fonctionne en tant qu'utilisateur non privilégié pour des raisons de sécurité évidentes. Vérifiez les autorisations des fichiers et dossiers utilisés par BunkerWeb, surtout si vous utilisez des configurations personnalisées (plus d'informations [ici](advanced.md#custom-configurations)). Vous devrez définir au moins les droits **_RW_** sur les fichiers et **_RWX_** sur les dossiers.

## Débannissement d'IP

Vous pouvez débannir manuellement une IP, ce qui est utile lors de la réalisation de tests afin de pouvoir contacter l'API interne de BunkerWeb (remplacez `1.2.3.4` par l'adresse IP à débannir) :

=== "Docker / Docker Autoconf"

    Vous pouvez utiliser la commande `docker exec` (remplacez `bw-scheduler` par le nom de votre conteneur) :
    ```shell
    docker exec bw-scheduler bwcli unban 1.2.3.4
    ```

    Voici l'équivalent docker-compose (remplacez `bw-scheduler` par le nom des services déclarés dans le fichier docker-compose.yml) :
    ```shell
    docker-compose exec bw-scheduler bwcli unban 1.2.3.4
    ```

=== "Tout-en-un"

    !!! tip "Nom du conteneur"
        Le nom de conteneur par défaut pour l'image Tout-en-un est `bunkerweb-aio`. Si vous avez utilisé un nom différent, ajustez la commande en conséquence.

    Vous pouvez utiliser la commande `docker exec` :
    ```shell
    docker exec bunkerweb-aio bwcli unban 1.2.3.4
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Vous pouvez utiliser la commande `docker exec` (remplacez `bw-scheduler` par le nom de votre service) :
    ```shell
    docker exec $(docker ps -q -f name=bw-scheduler) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    Vous pouvez utiliser la commande `kubectl exec` (remplacez `bunkerweb-scheduler` par le nom de votre pod) :
    ```shell
    kubectl exec bunkerweb-scheduler bwcli unban 1.2.3.4
    ```

=== "Linux"

    Vous pouvez utiliser la commande `bwcli` (en tant que root) :
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

## Faux positifs

### Mode de détection uniquement

À des fins de débogage/test, vous pouvez définir BunkerWeb en [mode de détection uniquement](features.md#security-modes) afin qu'il ne bloque pas la demande et agisse comme un proxy inverse classique.

### ModSecurity

La configuration par défaut de BunkerWeb de ModSecurity est de charger le Core Rule Set en mode scoring d'anomalie avec un niveau de paranoïa (PL) de 1 :

- Chaque règle correspondante augmentera un score d'anomalie (de sorte que de nombreuses règles peuvent correspondre à une seule requête)
- PL1 comprend des règles avec moins de risques de faux positifs (mais moins de sécurité que PL4)
- Le seuil par défaut pour le score d'anomalie est de 5 pour les requêtes et de 4 pour les réponses

Prenons les logs suivants comme exemple de détection ModSecurity à l'aide de la configuration par défaut (formatée pour une meilleure lisibilité) :

```log
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `lfi-os-files.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf"]
	[line "78"]
	[id "930120"]
	[rev ""]
	[msg "OS File Access Attempt"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-lfi"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/255/153/126"]
	[tag "PCI/6.5.4"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:utf8toUnicode,t:urlDecodeUni,t:normalizePathWin,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `unix-shell.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf"]
	[line "480"]
	[id "932160"]
	[rev ""]
	[msg "Remote Command Execution: Unix Shell Code Found"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-shell"]
	[tag "platform-unix"]
	[tag "attack-rce"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/152/248/88"]
	[tag "PCI/6.5.2"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:urlDecodeUni,t:cmdLine,t:normalizePath,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [error] 85#85: *11 [client 172.17.0.1] ModSecurity: Access denied with code 403 (phase 2). Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `10' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-949-BLOCKING-EVALUATION.conf"]
	[line "80"]
	[id "949110"]
	[rev ""]
	[msg "Inbound Anomaly Score Exceeded (Total Score: 10)"]
	[data ""]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-generic"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref ""],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
```

Comme nous pouvons le voir, il existe 3 journaux différents :

1. Règle **930120** appariée
2. Règle **932160** appariée
3. Accès refusé (règle **949110**)

Une chose importante à comprendre est que la règle **949110** n'est pas une "vraie" règle : c'est celle qui refusera la requête car le seuil d'anomalie est atteint (qui est de **10** dans cet exemple). Vous ne devriez jamais supprimer la règle **949110** !

S'il s'agit d'un faux positif, vous devez alors vous concentrer sur les règles **930120** et **932160**. Le réglage de ModSecurity et/ou du CRS n'entre pas dans le cadre de cette documentation, mais n'oubliez pas que vous pouvez appliquer des configurations personnalisées avant et après le chargement du SCR (plus d'informations [ici](advanced.md#custom-configurations)).

### Mauvais comportement

Un cas courant de faux positifs est lorsque le client est banni en raison de la fonction "mauvais comportement", ce qui signifie que trop de codes d'état HTTP suspects ont été générés au cours d'une période donnée (plus d'informations [ici](features.md#bad-behavior)). Vous devez commencer par examiner les paramètres, puis les modifier en fonction de votre ou vos applications web, comme la suppression d'un code HTTP suspect, la diminution du temps de comptage, l'augmentation du seuil, ...

### Liste blanche

Si vous avez des bots (ou des administrateurs) qui ont besoin d'accéder à votre site Web, la méthode recommandée pour éviter tout faux positif est de les mettre sur liste blanche à l'aide de la [fonction de liste blanche](features.md#whitelist). Nous vous déconseillons d'utiliser les `WHITELIST_URI*` paramètres  ou `WHITELIST_USER_AGENT*` à moins qu'ils ne soient définis sur des valeurs secrètes et imprévisibles. Les cas d'utilisation courants sont :

- Vérification de l'état / bot d'état
- Callback comme IPN ou webhook
- Robot d'exploration des médias sociaux

## Erreurs courantes

### En-tête trop gros envoyé en amont

Si vous voyez l'erreur suivante `upstream sent too big header while reading response header from upstream` dans les journaux, vous devrez ajuster la taille des différents tampons proxy à l'aide des paramètres suivants :

- `PROXY_BUFFERS`
- `PROXY_BUFFER_SIZE`
- `PROXY_BUSY_BUFFERS_SIZE`

### Impossible de construire server_names_hash

Si vous voyez l'erreur suivante `could not build server_names_hash, you should increase server_names_hash_bucket_size` dans les journaux, vous devrez modifier le `SERVER_NAMES_HASH_BUCKET_SIZE` paramètre.

## Fuseau horaire

Lors de l'utilisation d'intégrations basées sur des conteneurs, le fuseau horaire du conteneur peut ne pas correspondre à celui de la machine hôte. Pour résoudre ce problème, vous pouvez définir la `TZ` variable d'environnement sur le fuseau horaire de votre choix sur vos conteneurs (par exemple, `TZ=Europe/Paris`). Vous trouverez la liste des identifiants de fuseau horaire [ici](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List).

## Nettoyer les anciennes instances dans la base de données {#clear-old-instances-db}

BunkerWeb stocke les instances connues dans la table `bw_instances` (clé primaire : `hostname`).
Si vous redéployez fréquemment, d’anciennes lignes peuvent rester (par exemple, des instances qui ne se sont pas signalées depuis longtemps) et vous pouvez vouloir les purger.

!!! warning "Sauvegarde d’abord"
    Avant de modifier la base manuellement, faites une sauvegarde (snapshot du volume SQLite ou outils de sauvegarde de votre moteur de BD).

!!! warning "Arrêter les composants qui écrivent"
    Pour éviter les courses lors de la suppression, arrêtez (ou réduisez) les composants pouvant mettre à jour les instances
    (généralement le scheduler / autoconf selon votre déploiement), exécutez le nettoyage, puis redémarrez-les.

### Table et colonnes (référence)

Le modèle d’instance est défini comme suit :

- Table : `bw_instances`
- Clé primaire : `hostname`
- Horodatage « last seen » : `last_seen`
- Contient aussi :
  `name`, `port`, `listen_https`, `https_port`,
  `server_name`, `type`, `status`, `method`,
  `creation_date`

### 1 - Se connecter à la base de données

Utilisez la section existante [Accès à la base de données](#access-database) pour vous connecter
(SQLite / MariaDB / PostgreSQL).

### 2 - Dry-run : lister les instances obsolètes

Choisissez une fenêtre de rétention (ex. : 90 jours) et vérifiez ce qui serait supprimé.

=== "SQLite"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days')
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "MariaDB / MySQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY)
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "PostgreSQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days'
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

### 3 - Supprimer les instances obsolètes

Une fois vérifié, supprimez les lignes.

=== "SQLite"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days');

    COMMIT;
    ```

=== "MariaDB / MySQL"

    ```sql
    START TRANSACTION;

    DELETE FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY);

    COMMIT;
    ```

=== "PostgreSQL"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days';

    COMMIT;
    ```

!!! tip "Supprimer par hostname"
    Pour supprimer une instance spécifique, utilisez son hostname (la clé primaire).

    ```sql
    DELETE FROM bw_instances WHERE hostname = '<hostname>';
    ```

### 4 - Marquer les instances comme modifiées (optionnel)

BunkerWeb suit les changements d’instances dans la table `bw_metadata`
(`instances_changed`, `last_instances_change`).

Si l’UI ne se rafraîchit pas comme prévu après un nettoyage manuel,
vous pouvez forcer la mise à jour du « marqueur de changement » :

=== "SQLite / PostgreSQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = CURRENT_TIMESTAMP
    WHERE id = 1;
    ```

=== "MariaDB / MySQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = NOW()
    WHERE id = 1;
    ```

### 5 - Récupérer de l’espace (optionnel)

=== "SQLite"

    ```sql
    VACUUM;
    ```

=== "PostgreSQL"

    ```sql
    VACUUM (ANALYZE);
    ```

=== "MariaDB / MySQL"

    ```sql
    OPTIMIZE TABLE bw_instances;
    ```

## Interface utilisateur Web {#web-ui}

Si vous avez oublié vos informations d'identification de l'interface utilisateur ou si vous rencontrez des problèmes de 2FA, vous pouvez vous connecter à la base de données pour retrouver l'accès.

### Accéder à la base de données

=== "SQLite"

    === "Linux"

        Installer SQLite (Debian/Ubuntu) :

        ```shell
        sudo apt install sqlite3
        ```

        Installer SQLite (Fedora/RedHat) :

        ```shell
        sudo dnf install sqlite
        ```

    === "Docker"

        Obtenir un shell dans votre conteneur scheduler :

        !!! note "Arguments Docker"
            - l'option `-u 0` permet d'exécuter la commande en tant que root (obligatoire)
            - les options `-it` permettent d'exécuter la commande de manière interactive (obligatoire)
            - `<bunkerweb_scheduler_container>` : le nom ou l'ID de votre conteneur scheduler

        ```shell
        docker exec -u 0 -it <bunkerweb_scheduler_container> bash
        ```

        Installer SQLite :

        ```bash
        apk add sqlite
        ```

    === "Tout-en-un"

        Obtenir un shell dans votre conteneur Tout-en-un :

        !!! note "Arguments Docker"
            - l'option `-u 0` permet d'exécuter la commande en tant que root (obligatoire).
            - les options `-it` permettent d'exécuter la commande de manière interactive (obligatoire).
            - `bunkerweb-aio` est le nom de conteneur par défaut ; ajustez si vous avez utilisé un nom personnalisé.

        ```shell
        docker exec -u 0 -it bunkerweb-aio bash
        ```

    Accéder à votre base de données :

    !!! note "Chemin de la base de données"
        Nous supposons que vous utilisez le chemin de base de données par défaut. Si vous utilisez un chemin personnalisé, vous devrez adapter la commande.
        Pour Tout-en-un, nous supposons que la base de données est `db.sqlite3` située dans le volume persistant `/data` (`/data/db.sqlite3`).

    ```bash
    sqlite3 /var/lib/bunkerweb/db.sqlite3
    ```

    Vous devriez voir quelque chose comme ceci :

    ```text
    SQLite version <VER> <DATE>
    Enter ".help" for usage hints.
    sqlite>
    ```

=== "MariaDB / MySQL"

    !!! note "MariaDB / MySQL uniquement"
        Les étapes suivantes sont uniquement valides pour les bases de données MariaDB / MySQL. Si vous utilisez une autre base de données, veuillez vous référer à la documentation de votre base de données.

    !!! note "Identifiants et nom de la base de données"
        Vous devrez utiliser les mêmes identifiants et nom de base de données utilisés dans le paramètre `DATABASE_URI`.

    === "Linux"

        Accédez à votre base de données locale :

        ```bash
        mysql -u <user> -p <database>
        ```

        Ensuite, entrez le mot de passe de l'utilisateur de la base de données et vous devriez pouvoir accéder à votre base de données.

    === "Docker"

        Accédez à votre conteneur de base de données :

        !!! note "Arguments Docker"
            - l'option `-u 0` permet d'exécuter la commande en tant que root (obligatoire)
            - les options `-it` permettent d'exécuter la commande de manière interactive (obligatoire)
            - `<bunkerweb_db_container>` : le nom ou l'ID de votre conteneur de base de données
            - `<user>` : l'utilisateur de la base de données
            - `<database>` : le nom de la base de données

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> mysql -u <user> -p <database>
        ```

        Ensuite, entrez le mot de passe de l'utilisateur de la base de données et vous devriez pouvoir accéder à votre base de données.

    === "All-in-one"

        L'image Tout-en-un n'inclut pas de serveur MariaDB/MySQL. Si vous avez configuré l'AIO pour utiliser une base de données MariaDB/MySQL externe (en définissant la variable d'environnement `DATABASE_URI`), vous devez vous connecter à cette base de données directement à l'aide des outils clients MySQL standard.

        La méthode de connexion serait similaire à l'onglet "Linux" (si vous vous connectez depuis l'hôte où AIO fonctionne ou une autre machine) ou en exécutant un client MySQL dans un conteneur Docker séparé si préféré, en ciblant l'hôte et les identifiants de votre base de données externe.

=== "PostgreSQL"

    !!! note "PostgreSQL uniquement"
        Les étapes suivantes sont uniquement valides pour les bases de données PostgreSQL. Si vous utilisez une autre base de données, veuillez vous référer à la documentation de votre base de données.

    !!! note "Identifiants, hôte et nom de base de données"
        Vous devrez utiliser les mêmes identifiants (utilisateur/mot de passe), l’hôte et le nom de base de données utilisés dans le paramètre `DATABASE_URI`.

    === "Linux"

        Accédez à votre base de données locale :

        ```bash
        psql -U <user> -d <database>
        ```

        Si votre base de données se trouve sur un autre hôte, ajoutez le nom d’hôte/l’IP et le port :

        ```bash
        psql -h <host> -p 5432 -U <user> -d <database>
        ```

        Ensuite, entrez le mot de passe de l’utilisateur de la base de données pour y accéder.

    === "Docker"

        Accédez à votre conteneur de base de données :

        !!! note "Arguments Docker"
            - l'option `-u 0` permet d'exécuter la commande en tant que root (obligatoire)
            - les options `-it` permettent d'exécuter la commande de manière interactive (obligatoire)
            - `<bunkerweb_db_container>` : le nom ou l'ID de votre conteneur de base de données
            - `<user>` : l'utilisateur de la base de données
            - `<database>` : le nom de la base de données

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> psql -U <user> -d <database>
        ```

        Si la base de données est hébergée ailleurs, ajoutez les options `-h <host>` et `-p 5432` selon le cas.

    === "All-in-one"

        L'image Tout-en-un n'inclut pas de serveur PostgreSQL. Si vous avez configuré l'AIO pour utiliser une base de données PostgreSQL externe (en définissant la variable d'environnement `DATABASE_URI`), vous devez vous connecter à cette base de données directement à l'aide des outils clients PostgreSQL standard.

        La méthode de connexion serait similaire à l'onglet "Linux" (si vous vous connectez depuis l'hôte où AIO fonctionne ou une autre machine) ou en exécutant un client PostgreSQL dans un conteneur Docker séparé si préféré, en ciblant l'hôte et les identifiants de votre base de données externe.

### Actions de dépannage

!!! info "Schéma des tables"
    Le schéma de la `bw_ui_users` table est le suivant :

    | Field         | Type                                                | Null | Key | Default | Extra |
    | ------------- | --------------------------------------------------- | ---- | --- | ------- | ----- |
    | username      | varchar(256)                                        | NO   | PRI | NULL    |       |
    | email         | varchar(256)                                        | YES  | UNI | NULL    |       |
    | password      | varchar(60)                                         | NO   |     | NULL    |       |
    | method        | enum('ui','scheduler','autoconf','manual','wizard') | NO   |     | NULL    |       |
    | admin         | tinyint(1)                                          | NO   |     | NULL    |       |
    | theme         | enum('light','dark')                                | NO   |     | NULL    |       |
    | language      | varchar(2)                                          | NO   |     | NULL    |       |
    | totp_secret   | varchar(256)                                        | YES  |     | NULL    |       |
    | creation_date | datetime                                            | NO   |     | NULL    |       |
    | update_date   | datetime                                            | NO   |     | NULL    |       |

=== "Récupérer le nom d'utilisateur"

    Exécutez la commande suivante pour extraire les données de la table `bw_ui_users` :

    ```sql
    SELECT * FROM bw_ui_users;
    ```

    Vous devriez voir quelque chose comme ceci :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

=== "Mettre à jour le mot de passe de l'utilisateur administrateur"

    Vous devez d'abord hacher le nouveau mot de passe en utilisant l'algorithme bcrypt.

    Installez la bibliothèque Python bcrypt :

    ```shell
    pip install bcrypt
    ```

    Générez votre hachage (remplacez `mypassword` par votre propre mot de passe) :

    ```shell
    python3 -c 'from bcrypt import hashpw, gensalt ; print(hashpw(b"""mypassword""", gensalt(rounds=10)).decode("utf-8"))'
    ```

    Vous pouvez mettre à jour votre nom d'utilisateur / mot de passe en exécutant cette commande :

    ```sql
    UPDATE bw_ui_users SET password = '<password_hash>' WHERE admin = 1;
    ```

    Si vous vérifiez à nouveau votre table `bw_ui_users` en suivant cette commande :

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    Vous devriez voir quelque chose comme ceci :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

    Vous devriez maintenant pouvoir utiliser les nouvelles informations d'identification pour vous connecter à l'interface utilisateur Web.

=== "Désactiver l'authentification 2FA pour l'utilisateur administrateur"

    Vous pouvez désactiver l'authentification 2FA en exécutant cette commande :

    ```sql
    UPDATE bw_ui_users SET totp_secret = NULL WHERE admin = 1;
    ```

    Si vous vérifiez à nouveau votre table `bw_ui_users` en suivant cette commande :

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    Vous devriez voir quelque chose comme ceci :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | NULL        | ***           | ***         |

    Vous devriez maintenant pouvoir vous connecter à l'interface utilisateur Web en utilisant uniquement votre nom d'utilisateur et votre mot de passe sans 2FA.

=== "Actualiser les codes de récupération 2FA"

    Les codes de récupération peuvent être actualisés dans votre **page de profil** de l'interface utilisateur Web sous l'onglet `Sécurité`.

=== "Exporter la configuration et les journaux anonymisés"

    Utilisez la **page Support** de l’interface Web pour rassembler rapidement la configuration et les journaux pour le dépannage.

    - Ouvrez l’interface Web et allez à la page Support.
    - Choisissez la portée : exporter les paramètres globaux ou sélectionner un Service spécifique.
    - Cliquez pour télécharger l’archive de configuration pour la portée choisie.
    - Vous pouvez également télécharger les journaux : les journaux exportés sont automatiquement anonymisés (toutes les adresses IP et les domaines sont masqués).

### Téléversement de plugin

Il peut ne pas être possible de télécharger un plugin à partir de l'interface utilisateur dans certaines situations :

- Package manquant pour gérer les fichiers compressés sur votre intégration, auquel cas vous devrez ajouter les packages nécessaires
- Navigateur Safari : le 'mode sans échec' peut vous empêcher d'ajouter un plugin. Vous devrez apporter les modifications nécessaires sur votre machine
