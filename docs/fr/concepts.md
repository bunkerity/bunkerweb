# Concepts

## Architecture

<figure markdown>
  ![Vue d'ensemble](assets/img/concepts.svg){ align=center, width="600" }
</figure>

Au sein de votre infrastructure, BunkerWeb agit comme un proxy inverse devant vos services web. L'architecture typique consiste à accéder à BunkerWeb à partir d'Internet, qui transmet ensuite les demandes au service d'application approprié sur un réseau sécurisé.

L'utilisation de BunkerWeb de cette manière (architecture classique de proxy inverse) avec le déchargement TLS et les politiques de sécurité centralisées améliore les performances en réduisant la surcharge de chiffrement sur les serveurs backend tout en garantissant un contrôle d'accès cohérent, l'atténuation des menaces et l'application de la conformité dans tous les services.

## Intégrations

Le premier concept est l'intégration de BunkerWeb dans l'environnement cible. Nous préférons utiliser le mot "intégration" au lieu de "installation" car l'un des objectifs de BunkerWeb est de s'intégrer de manière transparente dans les environnements existants.

Les intégrations suivantes sont officiellement prises en charge:

- [Docker](integrations.md#docker)
- [Linux](integrations.md#linux)
- [Docker autoconf](integrations.md#docker-autoconf)
- [Kubernetes](integrations.md#kubernetes)
- [Swarm](integrations.md#swarm)

Si vous pensez qu'une nouvelle intégration doit être prise en charge, n'hésitez pas à ouvrir un [nouveau ticket](https://github.com/bunkerity/bunkerweb/issues) sur le dépôt GitHub.

!!! info "Aller plus loin"

    Les détails techniques de toutes les intégrations de BunkerWeb sont disponibles dans la [section Intégrations](integrations.md) de la documentation.

## Paramètres

!!! tip "Paramètres BunkerWeb PRO"
    Certains plugins sont réservés à la **version PRO**. Vous souhaitez tester rapidement BunkerWeb PRO pendant un mois ? Utilisez le code `freetrial` lors de votre commande sur le [panneau BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=french&utm_campaign=self&utm_source=doc) ou en cliquant [ici](https://panel.bunkerweb.io/cart.php?language=french&a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) pour appliquer directement le code promo (sera effectif à la caisse).

Une fois BunkerWeb intégré à votre environnement, vous devrez le configurer pour servir et protéger vos applications Web.

La configuration de BunkerWeb se fait à l'aide de ce que nous appelons des "paramètres" ou des "variables". Chaque paramètre est identifié par un nom tel que `AUTO_LETS_ENCRYPT` ou `USE_ANTIBOT`. Vous pouvez attribuer des valeurs à ces paramètres pour configurer BunkerWeb.

Voici un exemple factice de configuration BunkerWeb:

```conf
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
USE_ANTIBOT=captcha
REFERRER_POLICY=no-referrer
USE_MODSECURITY=no
USE_GZIP=yes
USE_BROTLI=no
```

Veuillez noter que si vous utilisez l'interface utilisateur Web, les noms des paramètres sont également affichés en plus d'une étiquette "conviviale":

<figure markdown>
  ![Vue d'ensemble](assets/img/settings-ui1.png){ align=center, width="800" }
  <figcaption>Nom des paramètres dans l'interface utilisateur web</figcaption>
</figure>

Vous pouvez également utiliser la barre de recherche et spécifier directement un nom de paramètre:

<figure markdown>
  ![Vue d'ensemble](assets/img/settings-ui2.png){ align=center, width="600" }
  <figcaption>Recherche de paramètres dans l'interface utilisateur Web</figcaption>
</figure>

!!! info "Aller plus loin"

    La liste complète des paramètres disponibles, avec leurs descriptions et valeurs possibles, est disponible dans la section [Fonctionnalités](features.md) de la documentation.

## Mode multisite {#multisite-mode}

Comprendre le mode multisite est essentiel lors de l'utilisation de BunkerWeb. Comme notre objectif principal est la protection des applications web, notre solution est intimement liée au concept d'« hôtes virtuels » ou « vhosts » (plus d'informations [ici](https://en.wikipedia.org/wiki/Virtual_hosting)). Ces hôtes virtuels permettent de diffuser plusieurs applications Web à partir d'une seule instance ou d'un seul cluster.

Par défaut, le mode multisite est désactivé sur BunkerWeb. Cela signifie qu'une seule application web sera servie et que tous les paramètres lui seront appliqués. Cette configuration est idéale lorsque vous avez une seule application à protéger, car vous n'avez pas besoin de vous soucier des configurations multisites.

Cependant, lorsque le mode multisite est activé, BunkerWeb devient capable de servir et de protéger plusieurs applications Web. Chaque application Web est identifiée par un nom de serveur unique et possède son propre ensemble de paramètres. Ce mode s'avère avantageux lorsque vous avez plusieurs applications à sécuriser et que vous préférez utiliser une seule instance (ou un cluster) de BunkerWeb.

L'activation du mode multisite est contrôlée par le `MULTISITE` paramètre, qui peut être défini pour `yes` l'activer ou `no` pour le garder désactivé (valeur par défaut).

Chaque paramètre de BunkerWeb a un contexte spécifique qui détermine où il peut être appliqué. Si le contexte est défini sur « global », le paramètre ne peut pas être appliqué par serveur ou site, mais à l'ensemble de la configuration. D'autre part, si le contexte est « multisite », le paramètre peut être appliqué globalement et par serveur. Pour définir un paramètre multisite pour un serveur spécifique, il suffit d'ajouter le nom du serveur en tant que préfixe au nom du paramètre. Par exemple, `app1.example.com_AUTO_LETS_ENCRYPT` ou `app2.example.com_USE_ANTIBOT` sont des exemples de définition de noms avec des préfixes de nom de serveur. Lorsqu'un paramètre multisite est défini globalement sans préfixe de serveur, tous les serveurs héritent de ce paramètre. Toutefois, des serveurs individuels peuvent toujours remplacer le paramètre si le même paramètre est défini avec un préfixe de nom de serveur.

Comprendre les subtilités du mode multisite et de ses paramètres associés vous permet d'adapter le comportement de BunkerWeb à vos besoins spécifiques, garantissant ainsi une protection optimale de vos applications Web.

Voici un exemple factice de configuration BunkerWeb multisite:

```conf
MULTISITE=yes
SERVER_NAME=app1.example.com app2.example.com app3.example.com
AUTO_LETS_ENCRYPT=yes
USE_GZIP=yes
USE_BROTLI=yes
app1.example.com_USE_ANTIBOT=javascript
app1.example.com_USE_MODSECURITY=no
app2.example.com_USE_ANTIBOT=cookie
app2.example.com_WHITELIST_COUNTRY=FR
app3.example.com_USE_BAD_BEHAVIOR=no
```

Veuillez noter que le mode multisite est implicite lors de l'utilisation de l'interface utilisateur Web. Vous avez la possibilité d'appliquer des configurations directement à vos services ou de définir des paramètres globaux qui seront appliqués à tous vos services (vous pouvez toujours appliquer des exceptions directement à des services spécifiques):

<figure markdown>
  ![Vue d'ensemble](assets/img/ui-multisite.png){ align=center, width="600" }
  <figcaption>Appliquer un paramètre à tous les services à partir de l'interface utilisateur web</figcaption>
</figure>

!!! info "Aller plus loin"

    Vous trouverez des exemples concrets du mode multisite dans la section [Utilisations avancées](advanced.md) de la documentation et dans le répertoire [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/examples) du dépôt.

## Configurations personnalisées {#custom-configurations}

Pour relever des défis uniques et répondre à des cas d'utilisation spécifiques, BunkerWeb offre la flexibilité de configurations personnalisées. Bien que les paramètres fournis et les [plug-ins externes](plugins.md) couvrent un large éventail de scénarios, il peut y avoir des situations qui nécessitent une personnalisation supplémentaire.

BunkerWeb est construit sur le célèbre serveur Web NGINX, qui fournit un système de configuration puissant. Cela signifie que vous pouvez tirer parti des capacités de configuration de NGINX pour répondre à vos besoins spécifiques. Des configurations NGINX personnalisées peuvent être incluses dans divers [contextes](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts) tels que HTTP ou serveur, ce qui vous permet d'affiner le comportement de BunkerWeb en fonction de vos besoins. Que vous ayez besoin de personnaliser les paramètres globaux ou d'appliquer des configurations à des blocs de serveur spécifiques, BunkerWeb vous permet d'optimiser son comportement pour s'aligner parfaitement sur votre cas d'utilisation.

Un autre composant intégral de BunkerWeb est le pare-feu d'application Web ModSecurity. Avec les configurations personnalisées, vous avez la possibilité de traiter les faux positifs ou d'ajouter des règles personnalisées pour améliorer encore la protection fournie par ModSecurity. Ces configurations personnalisées vous permettent d'affiner le comportement du pare-feu et de vous assurer qu'il s'aligne sur les exigences spécifiques de vos applications Web.

En tirant parti de configurations personnalisées, vous débloquez un monde de possibilités pour adapter le comportement et les mesures de sécurité de BunkerWeb précisément à vos besoins. Qu'il s'agisse d'ajuster les configurations NGINX ou d'affiner ModSecurity, BunkerWeb offre la flexibilité nécessaire pour relever efficacement vos défis uniques.

La gestion des configurations personnalisées à partir de l'interface utilisateur web se fait via le ** menu Configs**:

<figure markdown>
  ![Vue d'ensemble](assets/img/configs-ui.png){ align=center, width="800" }
  <figcaption>Gérer les configurations personnalisées à partir de l'interface utilisateur web</figcaption>
</figure>

!!! info "Aller plus loin"

    Vous trouverez des exemples concrets de configurations personnalisées dans la section [Utilisations avancées](advanced.md#custom-configurations) de la documentation et dans le répertoire [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/examples) du dépôt.

## Base de données

BunkerWeb stocke en toute sécurité sa configuration actuelle dans une base de données backend, qui contient des données essentielles pour un fonctionnement sans faille. Les informations suivantes sont stockées dans la base de données:

- **Paramètres pour tous les services** : La base de données contient les paramètres définis pour tous les services fournis par BunkerWeb. Cela garantit que vos configurations et préférences sont préservées et facilement accessibles.

- **Configurations personnalisées**: toutes les configurations personnalisées que vous créez sont également stockées dans la base de données principale. Cela inclut des paramètres personnalisés et des modifications adaptées à vos besoins spécifiques.

- **Instances BunkerWeb**: Les informations sur les instances BunkerWeb, y compris leur configuration et les détails pertinents, sont stockées dans la base de données. Cela permet de gérer et de surveiller facilement plusieurs instances, le cas échéant.

- **Métadonnées sur l'exécution des tâches**: La base de données stocke les métadonnées liées à l'exécution de diverses tâches au sein de BunkerWeb. Cela inclut des informations sur les tâches planifiées, les processus de maintenance et d'autres activités automatisées.

- **Fichiers mis en cache**: BunkerWeb utilise des mécanismes de mise en cache pour améliorer les performances. La base de données contient les fichiers mis en cache, ce qui garantit une récupération et une distribution efficaces des ressources fréquemment utilisées.

Chaque fois que vous modifiez un paramètre ou ajoutez une nouvelle configuration, BunkerWeb stocke automatiquement les modifications dans la base de données, garantissant ainsi la persistance et la cohérence des données. BunkerWeb prend en charge plusieurs options de base de données backend, notamment SQLite, MariaDB, MySQL et PostgreSQL.

!!! tip
    Si vous utilisez l'interface Web pour l'administration quotidienne, nous recommandons de migrer vers un moteur de base de données externe (PostgreSQL ou MySQL/MariaDB) plutôt que de rester sur SQLite. Les moteurs externes gèrent mieux les requêtes simultanées et la croissance à long terme, en particulier dans les environnements multi-utilisateurs.

La configuration de la base de données est simple à l'aide du `DATABASE_URI` paramètre, qui suit les formats spécifiés pour chaque base de données prise en charge:

!!!avertissement
    Lors de l'utilisation de l'intégration Docker, vous devez définir la `DATABASE_URI` variable d'environnement dans tous les conteneurs BunkerWeb (à l'exception du conteneur BunkerWeb lui-même), afin de vous assurer que tous les composants peuvent accéder correctement à la base de données. Ceci est crucial pour maintenir l'intégrité et la fonctionnalité du système.

    In all cases, ensure that `DATABASE_URI` is set before starting BunkerWeb, as it is required for proper operation.

- **SQLite**: `sqlite:///var/lib/bunkerweb/db.sqlite3`
- **MariaDB**: `mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **MySQL**: `mysql+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **PostgreSQL :** `postgresql://bunkerweb:changeme@bw-db:5432/db`

En spécifiant l'URI de base de données appropriée dans la configuration, vous pouvez intégrer de manière transparente BunkerWeb à votre backend de base de données préféré, garantissant ainsi un stockage efficace et fiable de vos données de configuration.

### Matrice de compatibilité des bases de données

| Integration       | PostgreSQL                                   | MariaDB                   | MySQL                     | SQLite           |
| :---------------- | :------------------------------------------- | :------------------------ | :------------------------ | :--------------- |
| **Docker**        | ✅ `v18` et antérieures (all-in-one : ✅ `v17`) | ✅ `v11` et antérieures    | ✅ `v9` et antérieures     | ✅ Pris en charge |
| **Kubernetes**    | ✅ `v18` et antérieures                        | ✅ `v11` et antérieures    | ✅ `v9` et antérieures     | ✅ Pris en charge |
| **Autoconf**      | ✅ `v18` et antérieures                        | ✅ `v11` et antérieures    | ✅ `v9` et antérieures     | ✅ Pris en charge |
| **Paquets Linux** | Voir les notes ci-dessous                      | Voir les notes ci-dessous | Voir les notes ci-dessous | ✅ Pris en charge |

!!! info "Remarques"
    - **PostgreSQL** : les paquets basés sur Alpine incluent désormais le client `v18`, donc `v18` et les versions antérieures sont pris en charge par défaut ; l'image all-in-one embarque toujours le client `v17`, donc `v18` n'y est pas pris en charge.
    - **Linux** : La prise en charge dépend des paquets de votre distribution. Si nécessaire, vous pouvez installer les clients de base de données manuellement à partir des dépôts des fournisseurs (cela est généralement nécessaire pour RHEL).
    - **SQLite** : Est livré avec les paquets et est prêt à l'emploi.

Ressources externes utiles pour installer les clients de bases de données :

- [Guide de téléchargement et de dépôt PostgreSQL](https://www.postgresql.org/download/)
- [Outil de configuration du dépôt MariaDB](https://mariadb.org/download/?t=repo-config)
- [Guide de configuration du dépôt MySQL](https://dev.mysql.com/doc/mysql-yum-repo-quick-guide/en/)
- [Page de téléchargement de SQLite](https://www.sqlite.org/download.html)

<figure markdown>
  ![Vue d'ensemble](assets/img/bunkerweb_db.svg){ align=center, width="800" }
  <figcaption>Schéma de base de données</figcaption>
</figure>

## Programmateur {#scheduler}

Pour une coordination et une automatisation sans faille, BunkerWeb utilise un service spécialisé connu sous le nom de planificateur. Le planificateur joue un rôle essentiel dans le bon fonctionnement en effectuant les tâches suivantes:

- **Stockage des paramètres et des configurations personnalisées**: le planificateur est responsable du stockage de tous les paramètres et configurations personnalisées dans la base de données principale. Cela centralise les données de configuration, ce qui les rend facilement accessibles et gérables.

- **Exécution de diverses tâches (travaux)**: le planificateur gère l'exécution de diverses tâches, appelées travaux. Ces tâches englobent une gamme d'activités, telles que la maintenance périodique, les mises à jour programmées ou toute autre tâche automatisée requise par BunkerWeb.

- **Génération de la configuration BunkerWeb**: Le planificateur génère une configuration qui est facilement comprise par BunkerWeb. Cette configuration est dérivée des paramètres stockés et des configurations personnalisées, ce qui garantit que l'ensemble du système fonctionne de manière cohérente.

- **Agir en tant qu'intermédiaire pour d'autres services**: Le planificateur agit en tant qu'intermédiaire, facilitant la communication et la coordination entre les différents composants de BunkerWeb. Il s'interface avec des services tels que l'interface utilisateur web ou l'autoconf, assurant un flux continu d'informations et d'échange de données.

En substance, le planificateur sert de cerveau à BunkerWeb, orchestrant diverses opérations et assurant le bon fonctionnement du système.

Selon l'approche d'intégration, l'environnement d'exécution du planificateur peut différer. Dans les intégrations basées sur des conteneurs, le planificateur est exécuté dans son conteneur dédié, ce qui offre isolation et flexibilité. D'autre part, pour les intégrations basées sur Linux, le planificateur est autonome au sein du service bunkerweb, ce qui simplifie le processus de déploiement et de gestion.

En utilisant le planificateur, BunkerWeb rationalise l'automatisation et la coordination des tâches essentielles, permettant un fonctionnement efficace et fiable de l'ensemble du système.

Si vous utilisez l'interface utilisateur Web, vous pouvez gérer les tâches du planificateur en cliquant sur **Tâches** dans le menu:

<figure markdown>
  ![Vue d'ensemble](assets/img/jobs-ui.png){ align=center, width="800" }
  <figcaption>Gérer les tâches à partir de l'interface utilisateur web</figcaption>
</figure>

**Vérification de l'état des instances**

Depuis la version 1.6.0, le planificateur dispose d'un système de vérification de l'état intégré qui surveille l'état des instances. Si une instance devient défectueuse, le planificateur cessera de lui envoyer la configuration. Si l'instance redevient saine, le planificateur reprend l'envoi de la configuration.

L'intervalle de vérification de l'état est défini par la `HEALTHCHECK_INTERVAL` variable d'environnement, avec une valeur par défaut de `30`, ce qui signifie que le planificateur vérifiera l'état des instances toutes les 30 secondes.

## Modèles {#templates}

BunkerWeb exploite la puissance des modèles pour simplifier le processus de configuration et améliorer la flexibilité. Les modèles offrent une approche structurée et standardisée de la définition des paramètres et des configurations personnalisées, garantissant ainsi la cohérence et la facilité d'utilisation.

- **Modèles prédéfinis**: la version communautaire propose trois modèles prédéfinis qui encapsulent les configurations et paramètres personnalisés courants. Ces modèles servent de point de départ pour la configuration de BunkerWeb, permettant une configuration et un déploiement rapides. Les modèles prédéfinis sont les suivants:
    - **low**: modèle de base qui fournit des paramètres essentiels pour la protection des applications Web.
    - **medium**: un modèle équilibré qui offre un mélange de fonctionnalités de sécurité et d'optimisations de performances.
    - **élevé**: modèle avancé qui met l'accent sur des mesures de sécurité robustes et une protection complète.

- **Modèles personnalisés**: En plus des modèles prédéfinis, BunkerWeb permet aux utilisateurs de créer des modèles personnalisés adaptés à leurs besoins spécifiques. Les modèles personnalisés permettent d'affiner les paramètres et les configurations personnalisées, garantissant que BunkerWeb s'aligne parfaitement sur les besoins de l'utilisateur.

Avec l'interface utilisateur Web, les modèles sont disponibles en **mode facile** lorsque vous ajoutez ou modifiez un service:

<figure markdown>
  ![Vue d'ensemble](assets/img/templates-ui.png){ align=center, width="800" }
  <figcaption>Utilisation des modèles à partir de l'interface utilisateur web</figcaption>
</figure>

**Création de modèles personnalisés**

La création d'un modèle personnalisé est un processus simple qui implique la définition des paramètres, des configurations personnalisées et des étapes souhaités dans un format structuré.

- **Structure du modèle**: un modèle personnalisé se compose d'un nom, d'une série de paramètres, de configurations personnalisées et d'étapes facultatives. La structure du modèle est définie dans un fichier JSON qui respecte le format spécifié. Les principaux composants d'un modèle personnalisé sont les suivants:
  - **Paramètres**: Un paramètre est défini avec un nom et la valeur correspondante. Cette valeur remplacera la valeur par défaut du paramètre. **Seuls les paramètres multisites sont pris en charge.**
  - **Configurations**: une configuration personnalisée est un chemin d'accès à un fichier de configuration NGINX qui sera inclus en tant que configuration personnalisée. Pour savoir où placer le fichier de configuration personnalisé, référez-vous à l'exemple de l'arborescence d'un plugin ci-dessous. **Seuls les types de configuration multisite sont pris en charge.**
  - **Étapes**: une étape contient un titre, un sous-titre, des paramètres et des configurations personnalisées. Chaque étape représente une étape de configuration que l'utilisateur peut suivre pour configurer BunkerWeb selon le modèle personnalisé dans l'interface utilisateur Web.

!!! info "Spécifications des étapes"

    Si des étapes sont déclarées, **il n'est pas obligatoire d'inclure tous les paramètres et configurations personnalisées dans les sections `settings` et `configs`**. Gardez à l'esprit que les paramètres ou configurations personnalisées déclarés dans une étape pourront être modifiés par l'utilisateur dans l'interface utilisateur Web.

- **Fichier modèle**: le modèle personnalisé est défini dans un fichier JSON dans un `templates` dossier à l'intérieur du répertoire du plugin qui adhère à la structure spécifiée. Le fichier modèle contient un nom, les paramètres, les configurations personnalisées et les étapes requises pour configurer BunkerWeb selon les préférences de l'utilisateur.

- **Sélection d'un modèle**: une fois le modèle personnalisé défini, les utilisateurs peuvent le sélectionner pendant le processus de configuration en mode facile d'un service dans l'interface utilisateur Web. Un modèle peut également être sélectionné avec le `USE_TEMPLATE` paramètre dans la configuration. Le nom du fichier modèle (sans l' `.json` extension) doit être spécifié comme valeur du `USE_TEMPLATE` paramètre.

Exemple de fichier modèle personnalisé:
```json
{
    "name": "template name",
	// optional
    "settings": {
        "SETTING_1": "value",
        "SETTING_2": "value"
    },
	// optional
    "configs": [
        "modsec/false_positives.conf",
        "modsec/non_editable.conf",
		"modsec-crs/custom_rules.conf"
    ],
	// optional
    "steps": [
        {
            "title": "Title 1",
            "subtitle": "subtitle 1",
            "settings": [
                "SETTING_1"
            ],
            "configs": [
                "modsec-crs/custom_rules.conf"
            ]
        },
        {
            "title": "Title 2",
            "subtitle": "subtitle 2",
            "settings": [
                "SETTING_2"
            ],
            "configs": [
                "modsec/false_positives.conf"
            ]
        }
    ]
}
```

Exemple d'arborescence d'un plugin incluant des modèles personnalisés:
```tree
.
├── plugin.json
└── templates
    ├── my_other_template.json
    ├── my_template
    │   └── configs
    │       ├── modsec
    │       │   ├── false_positives.conf
    │       │   └── non_editable.conf
    │       └── modsec-crs
    │           └── custom_rules.conf
    └── my_template.json
```
