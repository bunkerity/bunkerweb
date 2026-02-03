# Plug-ins

BunkerWeb est livré avec un système de plugins permettant d'ajouter facilement de nouvelles fonctionnalités. Une fois qu'un plugin est installé, vous pouvez le gérer à l'aide de paramètres supplémentaires définis par le plugin.

## Plugins officiels

Voici la liste des plugins "officiels" que nous maintenons (voir le dépôt [bunkerweb-plugins](https://github.com/bunkerity/bunkerweb-plugins) pour plus d'informations) :

|       Nom       | Version | Description                                                                                                                                             |                                                Lien                                                 |
| :-------------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------: |
|   **ClamAV**    |   1.9   | Analyse automatiquement les fichiers téléchargés avec le moteur antivirus ClamAV et rejette la demande lorsqu'un fichier est détecté comme malveillant. |     [bunkerweb-plugins/clamav](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav)     |
|   **Coraza**    |   1.9   | Inspectez les requêtes à l'aide du WAF Coraza (alternative à ModSecurity).                                                                              |     [bunkerweb-plugins/coraza](https://github.com/bunkerity/bunkerweb-plugins/tree/main/coraza)     |
|  **Discorde**   |   1.9   | Envoyez des notifications de sécurité à un canal Discord à l'aide d'un Webhook.                                                                         |    [bunkerweb-plugins/discord](https://github.com/bunkerity/bunkerweb-plugins/tree/main/discord)    |
|    **Lâche**    |   1.9   | Envoyez des notifications de sécurité à un canal Slack à l'aide d'un Webhook.                                                                           |      [bunkerweb-plugins/slack](https://github.com/bunkerity/bunkerweb-plugins/tree/main/slack)      |
| **VirusTotal**  |   1.9   | Analyse automatiquement les fichiers téléchargés à l'aide de l'API VirusTotal et rejette la demande lorsqu'un fichier est détecté comme malveillant.    | [bunkerweb-plugins/virustotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal) |
| **Crochet Web** |   1.9   | Envoyez des notifications de sécurité à un point de terminaison HTTP personnalisé à l'aide d'un Webhook.                                                |    [bunkerweb-plugins/webhook](https://github.com/bunkerity/bunkerweb-plugins/tree/main/webhook)    |

## Comment utiliser un plugin

### Automatique

Si vous souhaitez installer rapidement des plugins externes, vous pouvez utiliser ce `EXTERNAL_PLUGIN_URLS` paramètre. Il prend une liste d'URL séparées par des espaces, chacune pointant vers une archive compressée (format zip) contenant un ou plusieurs plugins.

Vous pouvez utiliser la valeur suivante si vous souhaitez installer automatiquement les plugins officiels : `EXTERNAL_PLUGIN_URLS=https://github.com/bunkerity/bunkerweb-plugins/archive/refs/tags/v1.9.zip`

### Manuelle

La première étape consiste à installer le plugin en plaçant ses fichiers dans le dossier de données correspondant `plugins` . La procédure dépend de votre intégration :

=== "Docker"

    Lors de l'utilisation de l'[intégration Docker](integrations.md#docker), les plugins doivent être placés dans le volume monté sur `/data/plugins` dans le conteneur du planificateur.

    La première chose à faire est de créer le dossier des plugins :

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Ensuite, vous pouvez déposer les plugins de votre choix dans ce dossier :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    ??? warning "Utilisation d'un dossier local pour les données persistantes"
        Le planificateur s'exécute en tant qu'utilisateur non privilégié avec UID 101 et GID 101 à l'intérieur du conteneur. La raison en est la sécurité : en cas d'exploitation d'une vulnérabilité, l'attaquant n'aura pas de privilèges root complets (UID/GID 0).
        Mais il y a un inconvénient : si vous utilisez un **dossier local pour les données persistantes**, vous devrez **définir les permissions correctes** afin que l'utilisateur non privilégié puisse écrire des données dedans. Quelque chose comme ça devrait faire l'affaire :

        ```shell
        mkdir bw-data && \
        chown root:101 bw-data && \
        chmod 770 bw-data
        ```

        Alternativement, si le dossier existe déjà :

        ```shell
        chown -R root:101 bw-data && \
        chmod -R 770 bw-data
        ```

        Si vous utilisez [Docker en mode rootless](https://docs.docker.com/engine/security/rootless) ou [podman](https://podman.io/), les UID et GID dans le conteneur seront mappés à des valeurs différentes sur l'hôte. Vous devrez d'abord vérifier vos subuid et subgid initiaux :

        ```shell
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        Par exemple, si vous avez une valeur de **100000**, l'UID/GID mappé sera **100100** (100000 + 100) :

        ```shell
        mkdir bw-data && \
        sudo chgrp 100100 bw-data && \
        chmod 770 bw-data
        ```

        Ou si le dossier existe déjà :

        ```shell
        sudo chgrp -R 100100 bw-data && \
        chmod -R 770 bw-data
        ```

    Ensuite, vous pouvez monter le volume lors du démarrage de votre stack Docker :

    ```yaml
    services:
    ...
      bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
      volumes:
        - ./bw-data:/data
    ...
    ```

=== "Docker autoconf"

    Lors de l'utilisation de l'[intégration Docker autoconf](integrations.md#docker-autoconf), les plugins doivent être placés dans le volume monté sur `/data/plugins` dans le conteneur du planificateur.


    La première chose à faire est de créer le dossier des plugins :

    ```shell
    mkdir -p ./bw-data/plugins
    ```

    Ensuite, vous pouvez déposer les plugins de votre choix dans ce dossier :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* ./bw-data/plugins
    ```

    Étant donné que le planificateur s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les permissions :

    ```shell
    chown -R 101:101 ./bw-data
    ```

    Ensuite, vous pouvez monter le volume lors du démarrage de votre stack Docker :

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        volumes:
          - ./bw-data:/data
    ...
    ```

=== "Swarm"

    !!! warning "Obsolète"
        L'intégration Swarm est obsolète et sera supprimée dans une future version. Veuillez envisager d'utiliser l'[intégration Kubernetes](integrations.md#kubernetes) à la place.

        **Plus d'informations sont disponibles dans la [documentation de l'intégration Swarm](integrations.md#swarm).**

    Lors de l'utilisation de l'[intégration Swarm](integrations.md#swarm), les plugins doivent être placés dans le volume monté sur `/data/plugins` dans le conteneur du planificateur.

    !!! info "Volume Swarm"
      La configuration d'un volume Swarm qui persistera lorsque le service du planificateur s'exécute sur différents nœuds n'est pas couverte dans cette documentation. Nous supposons que vous avez un dossier partagé monté sur `/shared` sur tous les nœuds.

    La première chose à faire est de créer le dossier des plugins :

    ```shell
    mkdir -p /shared/bw-plugins
    ```

    Ensuite, vous pouvez déposer les plugins de votre choix dans ce dossier :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /shared/bw-plugins
    ```

    Étant donné que le planificateur s'exécute en tant qu'utilisateur non privilégié avec UID et GID 101, vous devrez modifier les permissions :

    ```shell
    chown -R 101:101 /shared/bw-plugins
    ```

    Ensuite, vous pouvez monter le volume lors du démarrage de votre stack Swarm :

    ```yaml
    services:
    ...
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        volumes:
          - /shared/bw-plugins:/data/plugins
    ...
    ```

=== "Kubernetes"

    Lors de l'utilisation de l'[intégration Kubernetes](integrations.md#kubernetes), les plugins doivent être placés dans le volume monté sur `/data/plugins` dans le conteneur du planificateur.

    La première chose à faire est de déclarer un [PersistentVolumeClaim](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) qui contiendra nos données de plugins :

    ```yaml
    apiVersion: v1
    kind: PersistentVolumeClaim
    metadata:
      name: pvc-bunkerweb-plugins
    spec:
      accessModes:
        - ReadWriteOnce
      resources:
        requests:
          storage: 5Gi
    ```

    Vous pouvez maintenant ajouter le montage de volume et un conteneur d'initialisation pour provisionner automatiquement le volume :

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: bunkerweb-scheduler
    spec:
      replicas: 1
      strategy:
        type: Recreate
      selector:
        matchLabels:
          app: bunkerweb-scheduler
      template:
        metadata:
          labels:
            app: bunkerweb-scheduler
        spec:
          serviceAccountName: sa-bunkerweb
          containers:
            - name: bunkerweb-scheduler
              image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
              imagePullPolicy: Always
              env:
                - name: KUBERNETES_MODE
                  value: "yes"
                - name: "DATABASE_URI"
                  value: "mariadb+pymysql://bunkerweb:changeme@svc-bunkerweb-db:3306/db"
              volumeMounts:
                - mountPath: "/data/plugins"
                  name: vol-plugins
          initContainers:
            - name: bunkerweb-scheduler-init
              image: alpine/git
              command: ["/bin/sh", "-c"]
              args: ["git clone https://github.com/bunkerity/bunkerweb-plugins /data/plugins && chown -R 101:101 /data/plugins"]
              volumeMounts:
                - mountPath: "/data/plugins"
                  name: vol-plugins
          volumes:
            - name: vol-plugins
              persistentVolumeClaim:
                claimName: pvc-bunkerweb-plugins
    ```

=== "Linux"

    Lors de l'utilisation de l'[intégration Linux](integrations.md#linux), les plugins doivent être écrits dans le dossier `/etc/bunkerweb/plugins` :

    ```shell
    git clone https://github.com/bunkerity/bunkerweb-plugins && \
    cp -rp ./bunkerweb-plugins/* /etc/bunkerweb/plugins && \
    chown -R nginx:nginx /etc/bunkerweb/plugins
    ```

## Écrire un plugin

### Structure

!!! tip "Plugins existants"

    Si la documentation n'est pas suffisante, vous pouvez consulter le code source existant des [plugins officiels](https://github.com/bunkerity/bunkerweb-plugins) et des [plugins core](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/src/common/core) (déjà inclus dans BunkerWeb mais ce sont des plugins, techniquement parlant).

À quoi ressemble la structure d'un plugin :
```
plugin /
    confs / conf_type / conf_name.conf
    ui / actions.py
         hooks.py
         template.html
         blueprints / <blueprint_file(s)>
              templates / <blueprint_template(s)>
    jobs / my-job.py
    templates / my-template.json
          my-template / configs / conf_type / conf_name.conf
    plugin.lua
    plugin.json
```

- **conf_name.conf** : Ajout de [configurations NGINX personnalisées](advanced.md#custom-configurations) (en tant que modèles Jinja2).

- **actions.py** : Script à exécuter sur le serveur Flask. Ce script s'exécute dans un contexte Flask, ce qui vous donne accès à des bibliothèques et des utilitaires tels que `jinja2` et `requests`.

- **hooks.py** : Fichier Python personnalisé qui contient les hooks de flask et qui sera exécuté lors du chargement du plugin.

- **template.html** : Page de plugin personnalisée accessible via l'interface utilisateur.

- **Dossier Blueprints (dans l'interface utilisateur) **:
  Ce dossier est utilisé pour remplacer les blueprints Flask existants ou en créer de nouveaux. À l'intérieur, vous pouvez inclure des fichiers de blueprint et un **** sous-dossier de modèles facultatif pour les modèles spécifiques aux blueprints.

- **jobs py file** : Fichiers Python personnalisés exécutés en tant que jobs par le planificateur.

- **my-template.json** : Ajoutez [des modèles personnalisés](concepts.md#templates) pour remplacer les valeurs par défaut des paramètres et appliquer facilement des configurations personnalisées.

- **plugin.lua** : Code exécuté sur NGINX à l'aide du [module NGINX LUA](https://github.com/openresty/lua-nginx-module).

- **plugin.json** : Métadonnées, paramètres et définitions de tâches pour votre plugin.

### Commencer

La première étape consiste à créer un dossier qui contiendra le plugin :

```shell
mkdir myplugin && \
cd myplugin
```

### Métadonnées

Un fichier nommé **plugin.json** et écrit à la racine du dossier du plugin doit contenir des métadonnées sur le plugin. En voici un exemple :

```json
{
  "id": "myplugin",
  "name": "My Plugin",
  "description": "Just an example plugin.",
  "version": "1.0",
  "stream": "partial",
  "settings": {
    "DUMMY_SETTING": {
      "context": "multisite",
      "default": "1234",
      "help": "Here is the help of the setting.",
      "id": "dummy-id",
      "label": "Dummy setting",
      "regex": "^.*$",
      "type": "text"
    }
  },
  "jobs": [
    {
      "name": "my-job",
      "file": "my-job.py",
      "every": "hour"
    }
  ]
}
```

Voici le détail des champs :

|     Champ     | Obligatoire | Type  | Description                                                                                                                           |
| :-----------: | :---------: | :---: | :------------------------------------------------------------------------------------------------------------------------------------ |
|     `id`      |     oui     | corde | ID interne du plugin : doit être unique parmi les autres plugins (y compris les "core") et ne contenir que des caractères minuscules. |
|    `name`     |     oui     | corde | Nom de votre plugin.                                                                                                                  |
| `description` |     oui     | corde | Description de votre plugin.                                                                                                          |
|   `version`   |     oui     | corde | Version de votre plugin.                                                                                                              |
|   `stream`    |     oui     | corde | Informations sur la prise en charge des flux : `no`, `yes` ou `partial`.                                                              |
|  `settings`   |     oui     | Dict  | Liste des paramètres de votre plugin.                                                                                                 |
|    `jobs`     |     Non     | liste | Liste des jobs de votre plugin.                                                                                                       |
|    `bwcli`    |     Non     |  dict  | Associer les noms de commandes CLI aux fichiers stockés dans le répertoire 'bwcli' du plugin pour exposer les plugins CLI. |

Chaque paramètre comporte les champs suivants (la clé est l'ID des paramètres utilisés dans une configuration) :

|   Champ    | Obligatoire | Type  | Description                                                                       |
| :--------: | :---------: | :---: | :-------------------------------------------------------------------------------- |
| `context`  |     oui     | corde | Contexte du cadre : `multisite` ou `global`.                                      |
| `default`  |     oui     | corde | Valeur par défaut du paramètre.                                                   |
|   `help`   |     oui     | corde | Texte d'aide sur le plugin (affiché dans l'interface utilisateur Web).            |
|    `id`    |     oui     | corde | ID interne utilisé par l'interface utilisateur web pour les éléments HTML.        |
|  `label`   |     oui     | corde | Étiquette affichée par l'interface utilisateur Web.                               |
|  `regex`   |     oui     | corde | L'expression régulière utilisée pour valider la valeur fournie par l'utilisateur. |
|   `type`   |     oui     | corde | Le type du champ : `text`, `check`, `select` ou `password`.                       |
| `multiple` |     Non     | corde | ID unique pour regrouper plusieurs paramètres avec des chiffres comme suffixe.    |
|  `select`  |     Non     | liste | Liste des valeurs de chaîne possibles lorsque est `type` . `select`               |

Chaque emploi comporte les champs suivants :

|  Champ  | Obligatoire | Type  | Description                                                                                                                                                  |
| :-----: | :---------: | :---: | :----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`  |     oui     | corde | Nom de l'emploi.                                                                                                                                             |
| `file`  |     oui     | corde | Nom du fichier à l'intérieur du dossier jobs.                                                                                                                |
| `every` |     oui     | corde | Fréquence de planification des tâches : `minute`, `hour`, `day` `week` , ou `once` (pas de fréquence, une seule fois avant de (ré)générer la configuration). |

### Commandes CLI

Les plugins peuvent étendre l'outil 'bwcli' avec des commandes personnalisées qui s'exécutent sous 'bwcli plugin <plugin_id> ...':

1. Ajoutez un répertoire 'bwcli' dans votre plugin et déposez-y un fichier par commande (par exemple 'bwcli/list.py'). La CLI ajoute le chemin du plugin à 'sys.path' avant d'exécuter le fichier.
2. Déclarez les commandes dans la section optionnelle 'bwcli' de 'plugin.json', en associant chaque nom de commande à son nom de fichier exécutable.

```json
{
  "bwcli": {
    "list": "list.py",
    "save": "save.py"
  }
}
```

Le planificateur expose automatiquement les commandes déclarées une fois le plugin installé. Les plugins principaux, tels que 'backup' dans 'src/common/core/backup', suivent le même modèle.

### Configurations

Vous pouvez ajouter des configurations NGINX personnalisées en ajoutant un dossier nommé **confs** avec un contenu similaire aux [configurations personnalisées](advanced.md#custom-configurations). Chaque sous-dossier à l'intérieur des **confs** contiendra  des modèles [jinja2](https://jinja.palletsprojects.com) qui seront générés et chargés dans le contexte correspondant (`http` `server-http` `default-server-http` `stream` `server-stream`, , `modsec` `modsec-crs`, `crs-plugins-before` et `crs-plugins-after`).

Voici un exemple de fichier de modèle de configuration à l'intérieur du dossier **confs/server-http** nommé **example.conf** :

```nginx
location /setting {
  default_type 'text/plain';
    content_by_lua_block {
        ngx.say('{{ DUMMY_SETTING }}')
    }
}
```

`{{ DUMMY_SETTING }}` sera remplacée par la valeur de la `DUMMY_SETTING` choisie par l'utilisateur du plugin.

### Modèles

Pour  plus d'informations[, consultez la documentation des ](concepts.md#templates)modèles.

### LUA

#### Scénario principal

Sous le capot, BunkerWeb utilise le [module LUA de NGINX](https://github.com/openresty/lua-nginx-module) pour exécuter du code dans NGINX. Les plugins qui ont besoin d'exécuter du code doivent fournir un fichier lua dans le répertoire racine du dossier du plugin en utilisant la `id` valeur de **plugin.json** comme nom. Voici un exemple nommé **myplugin.lua** :

```lua
local class     = require "middleclass"
local plugin    = require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"


local myplugin = class("myplugin", plugin)


function myplugin:initialize(ctx)
    plugin.initialize(self, "myplugin", ctx)
    self.dummy = "dummy"
end

function myplugin:init()
    self.logger:log(ngx.NOTICE, "init called")
    return self:ret(true, "success")
end

function myplugin:set()
    self.logger:log(ngx.NOTICE, "set called")
    return self:ret(true, "success")
end

function myplugin:access()
    self.logger:log(ngx.NOTICE, "access called")
    return self:ret(true, "success")
end

function myplugin:log()
    self.logger:log(ngx.NOTICE, "log called")
    return self:ret(true, "success")
end

function myplugin:log_default()
    self.logger:log(ngx.NOTICE, "log_default called")
    return self:ret(true, "success")
end

function myplugin:preread()
    self.logger:log(ngx.NOTICE, "preread called")
    return self:ret(true, "success")
end

function myplugin:log_stream()
    self.logger:log(ngx.NOTICE, "log_stream called")
    return self:ret(true, "success")
end

return myplugin
```

Les fonctions déclarées sont automatiquement appelées dans des contextes spécifiques. Voici le détail de chaque fonction :

|   Fonction    |                                           Contexte                                            | Description                                                                                                                                                                                                 | Valeur de retour                                                                                                                                                                                                                                                                                                                                                                                |
| :-----------: | :-------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    `init`     |           [init_by_lua](https://github.com/openresty/lua-nginx-module#init_by_lua)            | Appelé lorsque NGINX vient de démarrer ou a reçu un ordre de rechargement. Le cas d'utilisation typique consiste à préparer toutes les données qui seront utilisées par votre plugin.                       | `ret`, `msg`<ul><li>`ret` (booléen) : true s'il n'y a pas d'erreur ou sinon false</li><li>`msg` (chaîne) : message de réussite ou d'erreur</li></ul>                                                                                                                                                                                                                                            |
|     `set`     |            [set_by_lua](https://github.com/openresty/lua-nginx-module#set_by_lua)             | Appelé avant chaque requête reçue par le serveur. Le cas d'utilisation typique est celui de l'informatique avant la phase d'accès.                                                                          | `ret`, `msg`<ul><li>`ret` (booléen) : true s'il n'y a pas d'erreur ou sinon false</li><li>`msg` (chaîne) : message de réussite ou d'erreur</li></ul>                                                                                                                                                                                                                                            |
|   `access`    |         [access_by_lua](https://github.com/openresty/lua-nginx-module#access_by_lua)          | Appelé à chaque requête reçue par le serveur. Le cas d'utilisation typique consiste à effectuer les vérifications de sécurité ici et à refuser la demande si nécessaire.                                    | `ret`, `msg`,`status`,`redirect`<ul><li>`ret` (booléen) : true si pas d'erreur ou sinon false</li><li>`msg` (chaîne) : message de réussite ou d'erreur</li><li>`status` (nombre) : interrompt le processus en cours et renvoie [l'état HTTP](https://github.com/openresty/lua-nginx-module#http-status-constants)</li><li>`redirect` (URL) : si défini, redirigera vers l'URL</li></ul>  donnée |
|     `log`     |            [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)             | Appelé lorsqu'une requête est terminée (et avant qu'elle ne soit consignée dans les journaux d'accès). Le cas d'utilisation typique est de créer des statistiques ou de calculer des compteurs par exemple. | `ret`, `msg`<ul><li>`ret` (booléen) : true s'il n'y a pas d'erreur ou sinon false</li><li>`msg` (chaîne) : message de réussite ou d'erreur</li></ul>                                                                                                                                                                                                                                            |
| `log_default` |            [log_by_lua](https://github.com/openresty/lua-nginx-module#log_by_lua)             | Identique mais `log` uniquement appelé sur le serveur par défaut.                                                                                                                                           | `ret`, `msg`<ul><li>`ret` (booléen) : true s'il n'y a pas d'erreur ou sinon false</li><li>`msg` (chaîne) : message de réussite ou d'erreur</li></ul>                                                                                                                                                                                                                                            |
|   `preread`   | [](https://github.com/openresty/stream-lua-nginx-module#preread_by_lua_block)  preread_by_lua | Similaire à la `access` fonction mais pour le mode flux.                                                                                                                                                    | `ret`, `msg`,`status`<ul><li>`ret` (booléen) : true s'il n'y a pas d'erreur ou sinon false</li><li>`msg` (chaîne) : message de réussite ou d'erreur</li><li>`status` (nombre) : interrompre le processus en cours et [renvoyer l'état](https://github.com/openresty/lua-nginx-module#http-status-constants)</li></ul>                                                                           |
| `log_stream`  |      [log_by_lua](https://github.com/openresty/stream-lua-nginx-module#log_by_lua_block)      | Similaire à la `log` fonction mais pour le mode flux.                                                                                                                                                       | `ret`, `msg`<ul><li>`ret` (booléen) : true s'il n'y a pas d'erreur ou sinon false</li><li>`msg` (chaîne) : message de réussite ou d'erreur</li></ul>                                                                                                                                                                                                                                            |

#### Bibliothèques

Toutes les directives du [module LUA NGINX](https://github.com/openresty/lua-nginx-module) sont disponibles et  le [module LUA de flux NGINX](https://github.com/openresty/stream-lua-nginx-module). En plus de cela, vous pouvez utiliser les bibliothèques LUA incluses dans BunkerWeb : voir [ce script](https://github.com/bunkerity/bunkerweb/blobsrc/deps/clone.sh) pour la liste complète.

Si vous avez besoin de bibliothèques supplémentaires, vous pouvez les mettre dans le dossier racine du plugin et y accéder en les préfixant avec votre ID de plugin. Voici un exemple de fichier nommé **mylibrary.lua** :

```lua
local _M = {}

_M.dummy = function ()
	return "dummy"
end

return _M
```

Et voici comment vous pouvez l'utiliser à partir du fichier **myplugin.lua** :

```lua
local mylibrary = require "myplugin.mylibrary"

...

mylibrary.dummy()

...
```

#### Aides

Certains modules d'aide fournissent des aides utiles courantes :

- `self.variables` : permet d'accéder et de stocker les attributs des plugins
- `self.logger` : journaux d'impression
- `bunkerweb.utils` : diverses fonctions utiles
- `bunkerweb.datastore` : accéder aux données globales partagées sur une instance (magasin de clés/valeurs)
- `bunkerweb.clusterstore` : accéder à un magasin de données Redis partagé entre les instances de BunkerWeb (magasin clé/valeur)

Pour accéder aux fonctions, il faut d'abord **demander** les modules :

```lua
local utils       = require "bunkerweb.utils"
local datastore   = require "bunkerweb.datastore"
local clustestore = require "bunkerweb.clustertore"
```

Récupérer une valeur de réglage :

```lua
local myvar = self.variables["DUMMY_SETTING"]
if not myvar then
    self.logger:log(ngx.ERR, "can't retrieve setting DUMMY_SETTING")
else
    self.logger:log(ngx.NOTICE, "DUMMY_SETTING = " .. value)
end
```

Stockez quelque chose dans le cache local :

```lua
local ok, err = self.datastore:set("plugin_myplugin_something", "somevalue")
if not ok then
    self.logger:log(ngx.ERR, "can't save plugin_myplugin_something into datastore : " .. err)
else
    self.logger:log(ngx.NOTICE, "successfully saved plugin_myplugin_something into datastore")
end
```

Vérifiez si une adresse IP est globale :

```lua
local ret, err = utils.ip_is_global(ngx.ctx.bw.remote_addr)
if ret == nil then
    self.logger:log(ngx.ERR, "error while checking if IP " .. ngx.ctx.bw.remote_addr .. " is global or not : " .. err)
elseif not ret then
    self.logger:log(ngx.NOTICE, "IP " .. ngx.ctx.bw.remote_addr .. " is not global")
else
    self.logger:log(ngx.NOTICE, "IP " .. ngx.ctx.bw.remote_addr .. " is global")
end
```

!!! tip "Plus d'exemples"

    Si vous souhaitez voir la liste complète des fonctions disponibles, vous pouvez consulter les fichiers présents dans le [répertoire lua](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/src/bw/lua/bunkerweb) du dépôt.

### Emplois

BunkerWeb utilise un planificateur de tâches interne pour des tâches périodiques telles que le renouvellement des certificats avec certbot, le téléchargement de listes noires, le téléchargement de fichiers MMDB, ... Vous pouvez ajouter des tâches de votre choix en les plaçant dans un sous-dossier nommé **tâches** et en les répertoriant dans le  fichier de métadonnées **plugin.json**. N'oubliez pas d'ajouter les permissions d'exécution pour tout le monde afin d'éviter tout problème lorsqu'un utilisateur clone et installe votre plugin.

### Page du plugin

Tout ce qui concerne l'interface utilisateur web se trouve dans le sous-dossier **ui** comme nous l'avons vu dans la [section précédente sur la structure.](#structure).

#### Conditions préalables

Lorsque vous souhaitez créer une page de plugin, vous avez besoin de deux fichiers :

- **template.html** qui seront accessibles avec un **GET /plugins/<*plugin_id*>**.

- **actions.py** où vous pouvez ajouter des scripts et de la logique avec un **POST /plugins/<*plugin_id*>**. Notez que ce fichier **a besoin d'une fonction portant le même nom que le plugin** pour fonctionner. Ce fichier est nécessaire même si la fonction est vide.

#### Exemple de base

!!! info "Modèle Jinja 2"
    Le  fichier **template.html** est un modèle Jinja2, veuillez vous référer à la [documentation Jinja2](https://jinja.palletsprojects.com) si nécessaire.

Nous pouvons mettre de côté le ** fichier actions.py** et commencer à **utiliser uniquement le modèle dans une situation GET**. Le modèle peut accéder au contexte de l'application et aux libs, ce qui vous permet d'utiliser les utilitaires Jinja, request ou flask.

Par exemple, vous pouvez obtenir les arguments de requête dans votre modèle comme ceci :

```html
<p>request args : {{ request.args.get() }}.</p>
```

#### Actions.py

!!! warning "Jeton CSRF"

    Please note that every form submission is protected via a CSRF token, you will need to include the following snippet into your forms :
    ```html
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
    ```

Vous pouvez alimenter votre page de plugin avec des scripts supplémentaires avec le ** fichier actions.py** lors de l  'envoi d'un **POST /plugins/<*plugin_id*>**.

Vous avez deux fonctions par défaut dans **actions.py** :

**pre_render fonction**

Cela vous permet de récupérer les données lorsque vous **OBTENEZ** le modèle, et d'utiliser les données avec la variable pre_render disponible dans Jinja pour afficher le contenu de manière plus dynamique.

```python
def pre_render(**kwargs)
  return <pre_render_data>
```

BunkerWeb vous enverra ce type de réponse :


```python
return jsonify({"status": "ok|ko", "code" : XXX, "data": <pre_render_data>}), 200
```

**Fonction <*plugin_id*>**

Cela vous permet de récupérer des données lorsque vous effectuez un **POST** à partir du point de terminaison du modèle, qui doit être utilisé dans AJAX.

```python
def myplugin(**kwargs)
  return <plugin_id_data>
```

BunkerWeb vous enverra ce type de réponse :

```python
return jsonify({"message": "ok", "data": <plugin_id_data>}), 200
```

**Ce à quoi vous pouvez accéder à partir de action.py**

Voici les arguments qui sont passés et auxquels on accède sur action.py fonctions :

```python
function(app=app, args=request.args.to_dict() or request.json or None)
```

!!! info "Bibliothèques Python Disponibles"

    L'interface utilisateur Web de BunkerWeb inclut un ensemble de bibliothèques Python préinstallées que vous pouvez utiliser dans le fichier `actions.py` de votre plugin ou d'autres scripts liés à l'interface utilisateur. Elles sont disponibles prêtes à l'emploi sans nécessiter d'installations supplémentaires.

    Voici la liste complète des bibliothèques incluses :

    - **bcrypt** - Bibliothèque de hachage de mots de passe
    - **biscuit-python** - Jetons d'authentification Biscuit
    - **certbot** - Client ACME pour Let's Encrypt
    - **Flask** - Framework web
    - **Flask-Login** - Gestion des sessions utilisateur
    - **Flask-Session[cachelib]** - Stockage des sessions côté serveur
    - **Flask-WTF** - Gestion des formulaires et protection CSRF
    - **gunicorn[gthread]** - Serveur HTTP WSGI
    - **pillow** - Traitement d'images
    - **psutil** - Utilitaires système et processus
    - **python_dateutil** - Utilitaires de date et heure
    - **qrcode** - Génération de codes QR
    - **regex** - Expressions régulières avancées
    - **urllib3** - Client HTTP
    - **user_agents** - Analyse des agents utilisateur

    !!! tip "Utilisation des Bibliothèques dans Votre Plugin"
        Pour importer et utiliser ces bibliothèques dans votre fichier `actions.py`, utilisez simplement l'instruction `import` standard de Python. Par exemple :

        ```python
        from flask import request
        import bcrypt
        ```

    ??? warning "Bibliothèques Externes"
        Si vous avez besoin de bibliothèques non listées ci-dessus, installez-les dans le dossier `ui` de votre plugin et importez-les en utilisant la directive `import` classique. Assurez-vous de la compatibilité avec l'environnement existant pour éviter les conflits.

**Quelques exemples**

- Récupérer les données soumises par le formulaire

```python
from flask import request

def myplugin(**kwargs) :
	my_form_value = request.form["my_form_input"]
  return my_form_value
```

- Accéder à la configuration de l'application

**action.py**
```python
from flask import request

def pre_render(**kwargs) :
	config = kwargs['app'].config["CONFIG"].get_config(methods=False)
  return config
```

**modèle**
```html
<!-- metadata + config -->
<div>{{ pre_render }}</div>
```

### Hooks.py

Cette documentation décrit les hooks de cycle de vie utilisés pour gérer les différentes étapes d'une demande au sein de l'application. Chaque crochet est associé à une phase spécifique.

=== "before_request"
    Ces hooks sont exécutés **avant** le traitement d'une requête entrante. Ils sont généralement utilisés pour des tâches de prétraitement telles que l'authentification, la validation ou la journalisation.

    Si le hook retourne un objet de réponse, Flask ignorera le traitement de la requête et retournera la réponse directement. Cela peut être utile pour court-circuiter le pipeline de traitement des requêtes.

    **Exemple :**

    ```python
    from flask import request, Response

    def before_request():
        print("Before-request: Validating request...", flush=True)
        # Perform authentication, validation, or logging here
        if not is_valid_request(request): # We are in the app context
            return Response("Invalid request!", status=400)

    def is_valid_request(request):
        # Dummy validation logic
        return "user" in request
    ```
=== "after_request"
    Ces hooks qui s'exécutent **après** le traitement de la requête. Ils sont idéaux pour les tâches de post-traitement telles que le nettoyage, la journalisation supplémentaire ou la modification de la réponse avant qu'elle ne soit renvoyée.

    Ils reçoivent l'objet de réponse en tant qu'argument et peuvent le modifier avant de le retourner. Le premier crochet after_request qui retourne une réponse sera utilisé comme réponse finale.

    **Exemple :**

    ```python
    from flask import request

    def after_request(response):
        print("After-request: Logging response...", flush=True)
        # Perform logging, cleanup, or response modifications here
        log_response(response)
        return response

    def log_response(response):
        # Dummy logging logic
        print("Response logged:", response, flush=True)
    ```
=== "teardown_request"
    Ces hooks sont invoqués lorsque le contexte de la requête est en cours de destruction. Ces hooks sont utilisés pour libérer des ressources ou gérer les erreurs qui se sont produites au cours du cycle de vie de la demande.

    **Exemple:**

    ```python
    def teardown_request(error=None):
        print("Teardown-request: Cleaning up resources...", flush=True)
        # Perform cleanup, release resources, or handle errors here
        if error:
            handle_error(error)
        cleanup_resources()

    def handle_error(error):
        # Dummy error handling logic
        print("Error encountered:", error, flush=True)

    def cleanup_resources():
        # Dummy resource cleanup logic
        print("Resources have been cleaned up.", flush=True)
    ```
=== "context_processor"
    Ces points d'entrée sont utilisés pour injecter du contexte supplémentaire dans des modèles ou des vues. Ils enrichissent le contexte d'exécution en transmettant des données courantes (telles que des informations sur l'utilisateur ou des paramètres de configuration) aux modèles.

    Si un processeur de contexte retourne un dictionnaire, les clés et les valeurs seront ajoutées au contexte pour tous les modèles. Cela permet de partager des données entre plusieurs vues ou modèles.

    **Exemple :**

    ```python
    def context_processor() -> dict:
        print("Context-processor: Injecting context data...", flush=True)
        # Return a dictionary containing context data for templates/views
        return {
            "current_user": "John Doe",
            "app_version": "1.0.0",
            "feature_flags": {"new_ui": True}
        }
    ```

Cette conception de crochet de cycle de vie offre une approche modulaire et systématique de la gestion de divers aspects du cycle de vie d'une demande :

- **Modularité :** Chaque crochet est responsable d'une phase distincte, ce qui permet de séparer les préoccupations.
- **Maintenabilité :** les développeurs peuvent facilement ajouter, modifier ou supprimer des implémentations de hooks sans affecter les autres parties du cycle de vie de la requête.
- **Extensibilité :** le cadre est flexible, ce qui permet d'ajouter des crochets ou d'apporter des améliorations à mesure que les exigences de l'application évoluent.

En définissant clairement les responsabilités de chaque hook et leurs préfixes de journalisation associés, le système garantit que chaque étape du traitement des requêtes est transparente et gérable.

### Plans

Dans Flask, **les blueprints** servent de moyen modulaire pour organiser les composants associés, tels que les vues, les modèles et les fichiers statiques, au sein de votre application. Ils vous permettent de regrouper logiquement les fonctionnalités et peuvent être utilisés pour créer de nouvelles sections de votre application ou remplacer celles existantes.

#### Création d'un Blueprint

Pour définir un blueprint, vous devez créer une instance de la `Blueprint` classe, en spécifiant son nom et son chemin d'importation. Vous définissez ensuite les itinéraires et les vues associés à ce blueprint.

**Exemple : Définition d'un nouveau blueprint**

```python
from os.path import dirname
from flask import Blueprint, render_template

# Define the blueprint
my_blueprint = Blueprint('my_blueprint', __name__, template_folder=dirname(__file__) + '/templates') # The template_folder is set to avoid conflicts with the original blueprint

# Define a route within the blueprint
@my_blueprint.route('/my_blueprint')
def my_blueprint_page():
    return render_template('my_blueprint.html')
```


Dans cet exemple, un blueprint nommé `my_blueprint` est créé et un itinéraire `/my_blueprint` est défini à l'intérieur de celui-ci.

#### Remplacement d'un blueprint existant

Les Blueprints peuvent également remplacer les Blueprints existants pour modifier ou étendre les fonctionnalités. Pour ce faire, assurez-vous que le nouveau blueprint porte le même nom que celui que vous remplacez et enregistrez-le après l'original.

**Exemple : Remplacement d'un blueprint existant**

```python
from os.path import dirname
from flask import Flask, Blueprint

# Original blueprint
instances = Blueprint('instances', __name__, template_folder=dirname(__file__) + '/templates') # The template_folder is set to avoid conflicts with the original blueprint

@instances.route('/instances')
def override_instances():
    return "My new instances page"
```

Dans ce scénario, l'accès à l'URL `/instances` affiche "Ma nouvelle page d'instances", car le `instances` blueprint, enregistré en dernier, remplace le blueprint d'origine `instances` .

!!! warning "À propos de la dérogation"
    Soyez prudent lorsque vous remplacez des blueprints existants, car cela peut avoir un impact sur le comportement de l'application. Assurez-vous que les modifications sont conformes aux exigences de l'application et n'introduisent pas d'effets secondaires inattendus.

    Toutes les routes existantes seront supprimées du blueprint original, vous devrez donc les réimplémenter si nécessaire.

#### Conventions de nommage

!!! danger "Important"
    Assurez-vous que le nom du blueprint correspond au nom de la variable de blueprint, sinon il ne sera pas considéré comme un blueprint valide et ne sera pas enregistré.

Pour plus de cohérence et de clarté, il est conseillé de suivre les conventions de nommage suivantes :

- **Noms de blueprint**: utilisez des noms courts et tout en minuscules. Des traits de soulignement peuvent être utilisés pour la lisibilité, par exemple, `user_auth`.

- **Noms de fichiers**: faites correspondre le nom de fichier au nom du blueprint, en vous assurant qu'il est entièrement en minuscules avec des traits de soulignement si nécessaire, par exemple, `user_auth.py`.

Cette pratique s'aligne sur les conventions de nommage des modules de Python et permet de maintenir une structure de projet claire.

**Exemple : Blueprint et nommage de fichier**

```
plugin /
    ui / blueprints / user_auth.py
                      templates / user_auth.html
```

Dans cette structure, `user_auth.py` contient le `user_auth` blueprint et `user_auth.html` est le modèle associé, en respectant les conventions de nommage recommandées.
