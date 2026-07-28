Le plugin GeoIP gère les bases de données au format MaxMind (`.mmdb`) que BunkerWeb utilise pour déterminer le **pays**, l'**ASN** et, éventuellement, la **ville** de chaque adresse IP cliente. Ces recherches alimentent le plugin [Country](#country), les règles ASN des listes noire et grise, les rapports affichés dans l'[interface web](web-ui.md), ainsi que les variables de journalisation `$bw_country`, `$bw_asn_number`, `$bw_asn_org` et `$bw_city`.

Prêt à l'emploi, il ne nécessite aucune configuration : les bases de données de pays et d'ASN proviennent des éditions gratuites [DB-IP Lite](https://db-ip.com/db/lite.php), actualisées quotidiennement. Vous n'avez besoin des paramètres de ce plugin que si vous souhaitez utiliser un **autre fournisseur** — un abonnement MaxMind ou une base de données que vous fournissez vous-même.

**Fonctionnement :**

1. Trois tâches quotidiennes actualisent les bases de données de pays, d'ASN et de villes.
2. Chaque tâche choisit sa source selon une priorité simple : votre propre fichier, puis MaxMind, puis DB-IP.
3. Le fichier téléchargé est décompressé, ouvert et vérifié pour s'assurer qu'il correspond au type de base demandé.
4. S'il diffère de la copie en cache, il est stocké et envoyé à chaque instance BunkerWeb, qui se recharge pour l'utiliser.
5. L'échec d'une recherche ne bloque jamais une requête : le pays devient `unknown` et le trafic est servi normalement.

### Priorité des sources

Il n'existe aucun paramètre « source » à sélectionner. La priorité dépend simplement des paramètres que vous avez renseignés :

| Priorité | Condition d'utilisation                      | Source                                                     |
| -------- | -------------------------------------------- | ---------------------------------------------------------- |
| 1        | `GEOIP_<KIND>_MMDB` est défini              | Votre propre fichier ou URL                                |
| 2        | `MAXMIND_LICENSE_KEY` est défini             | MaxMind (GeoLite2 gratuit ou votre abonnement GeoIP2)      |
| 3        | Aucun paramètre n'est défini                 | DB-IP Lite (par défaut)                                    |

Définir `MAXMIND_LICENSE_KEY` fait basculer les **trois** bases de données vers MaxMind. Il n'est pas possible de mélanger les fournisseurs par base de données ; utilisez `GEOIP_<KIND>_MMDB` si vous souhaitez qu'une base précise provienne d'une autre source.

### Paramètres de configuration

| Paramètre                | Défaut | Contexte | Multiple | Description                                                                                                                                                                     |
| ------------------------ | ------ | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MAXMIND_LICENSE_KEY`    |        | global   | non      | **Clé de licence MaxMind :** lorsqu'elle est définie, les bases de pays, d'ASN et de villes sont téléchargées depuis MaxMind au lieu de DB-IP.                                    |
| `MAXMIND_ACCOUNT_ID`     |        | global   | non      | **ID de compte MaxMind :** facultatif mais recommandé ; sans lui, l'ancien point d'accès utilisant uniquement la clé est employé et place celle-ci dans l'URL.                   |
| `GEOIP_CITY`             | `no`   | global   | non      | **Base de données de villes :** télécharge la base de villes. Beaucoup plus volumineuse que les autres (125 MB décompressée), elle n'est pas incluse dans les images.             |
| `GEOIP_COUNTRY_MMDB`     |        | global   | non      | **Base de pays personnalisée :** chemin absolu lisible par le worker ou URL `http(s)`. Prioritaire sur MaxMind et DB-IP.                                                          |
| `GEOIP_ASN_MMDB`         |        | global   | non      | **Base ASN personnalisée :** chemin absolu lisible par le worker ou URL `http(s)`. Prioritaire sur MaxMind et DB-IP.                                                              |
| `GEOIP_CITY_MMDB`        |        | global   | non      | **Base de villes personnalisée :** chemin absolu lisible par le worker ou URL `http(s)`. Prioritaire sur MaxMind et DB-IP.                                                       |

!!! warning "La base de données de villes est volumineuse"
    DB-IP City Lite représente un **téléchargement de 59 MB qui atteint 125 MB après décompression**, contre 7.8 MB pour la base de pays et 9.2 MB pour celle des ASN. Contrairement à ces deux dernières, elle n'est **pas incluse dans les images** : aucune donnée n'est disponible avant le premier téléchargement réussi, et un échec laisse simplement `$bw_city` vide.

    Comme les caches des tâches sont stockés dans la base de données et envoyés à chaque instance, leur activation a de réelles conséquences :

    - Sur MariaDB et MySQL, augmentez `max_allowed_packet` au-dessus de 125 MB, sinon la tâche échouera (la valeur par défaut est 64 MB). La tâche l'indique explicitement dans ses journaux lorsque cela se produit.
    - Le worker conserve la base en mémoire pendant son stockage ; augmentez donc `WORKER_MAX_MEMORY_KB` et la limite mémoire du conteneur du worker en conséquence.
    - Chaque changement de configuration renvoie le cache à chaque instance ; prévoyez donc la bande passante et l'espace disque nécessaires.

    `GeoLite2-City` de MaxMind est sensiblement plus petite si vous disposez d'une clé de licence.

!!! info "Obtenir une clé de licence MaxMind"
    Créez un compte gratuit sur [maxmind.com](https://www.maxmind.com/en/geolite2/signup), puis générez une clé de licence **et** notez votre ID de compte. Les deux sont affichés dans le portail du compte. GeoLite2 est mise à jour deux fois par semaine, contre une fois par mois pour DB-IP Lite.

    Une clé nouvellement créée peut prendre un moment avant de devenir active ; entre-temps, les téléchargements échouent avec `401`.

!!! warning "Fournissez l'ID de compte, pas seulement la clé"
    L'ID de compte n'est facultatif que pour assurer la rétrocompatibilité. S'en passer est déconseillé pour deux raisons :

    - Le point d'accès de MaxMind utilisant uniquement la clé est **obsolète** et peut être supprimé.
    - Il place votre clé de licence **dans la chaîne de requête de l'URL**, où elle apparaît dans les journaux d'accès de tout proxy de transfert présent sur le chemin. Avec un ID de compte, les identifiants sont transmis dans un en-tête `Authorization`.

    BunkerWeb retire la clé de ses propres journaux dans les deux cas, y compris des messages d'erreur de téléchargement, mais ne peut pas la retirer des journaux de tiers.

!!! info "Utiliser votre propre base de données"
    Toute base `.mmdb` au format MaxMind fonctionne, y compris les éditions commerciales GeoIP2 et les bases internes, à condition d'utiliser les noms de champs standard (`country.iso_code`, `autonomous_system_number`, `autonomous_system_organization`, `city.names.en`).

    Un chemin local doit être lisible par le **worker**, et non par les instances BunkerWeb : le worker le lit une fois puis le distribue. Les fichiers `.mmdb`, `.mmdb.gz` et `.tar.gz` sont tous acceptés.

    Le fichier est ouvert et son type vérifié **avant** d'être stocké ou envoyé. Ainsi, faire pointer un paramètre vers le mauvais type de base — ou vers un fichier qui n'est pas une base — provoque une erreur explicite au lieu de ne rien renvoyer silencieusement.

    Préférez `https` pour une URL. La géolocalisation intervient dans les décisions d'autorisation et de blocage ; une base remplacée pendant le transfert peut faire apparaître le trafic comme provenant d'un pays que vous autorisez.

### Exemples de configuration

=== "Par défaut (DB-IP)"

    Rien à configurer. Les bases de pays et d'ASN sont actualisées quotidiennement depuis DB-IP Lite :

    ```yaml
    # no settings needed
    ```

=== "MaxMind GeoLite2"

    Faites basculer toutes les bases de données vers MaxMind :

    ```yaml
    MAXMIND_ACCOUNT_ID: "123456"
    MAXMIND_LICENSE_KEY: "your-license-key"
    ```

=== "Ajouter les données de ville"

    Activez la base de villes en plus des sources par défaut :

    ```yaml
    GEOIP_CITY: "yes"
    ```

=== "Base de données personnelle"

    Utilisez une base commerciale montée dans le worker, tout en conservant DB-IP pour le reste :

    ```yaml
    GEOIP_COUNTRY_MMDB: "/data/geoip/GeoIP2-Country.mmdb"
    ```

=== "Miroir interne"

    Récupérez toutes les bases depuis un miroir HTTP interne :

    ```yaml
    GEOIP_COUNTRY_MMDB: "https://mirror.example.com/geoip/country.mmdb"
    GEOIP_ASN_MMDB: "https://mirror.example.com/geoip/asn.mmdb"
    GEOIP_CITY: "yes"
    GEOIP_CITY_MMDB: "https://mirror.example.com/geoip/city.mmdb.gz"
    ```

### Licences

- Les bases de données **DB-IP Lite** sont publiées sous licence [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) et nécessitent une attribution à DB-IP.com.
- Les bases de données **GeoLite2** sont soumises au contrat de licence utilisateur final de MaxMind, que vous acceptez lors de la création de votre clé. BunkerWeb ne les redistribue jamais : elles sont téléchargées avec vos propres identifiants, raison pour laquelle aucune base MaxMind n'est incluse dans les images.
