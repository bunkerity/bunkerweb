Le plugin DNSBL (Domain Name System Blacklist) protège contre les IP malveillantes connues en vérifiant l’adresse IP du client auprès de serveurs DNSBL externes. Cette fonctionnalité aide à se prémunir du spam, des botnets et de diverses menaces en s’appuyant on des listes communautaires d’IP problématiques.

**Comment ça marche :**

1.  Lorsqu’un client se connecte à votre site, BunkerWeb interroge les serveurs DNSBL que vous avez choisis via le protocole DNS.
2.  La vérification s’effectue en envoyant une requête DNS inversée à chaque serveur DNSBL avec l’IP du client.
3.  Si un serveur DNSBL confirme que l’IP du client est listée comme malveillante, BunkerWeb bannit automatiquement ce client, empêchant les menaces potentielles d’atteindre votre application.
4.  Les résultats sont mis en cache pour améliorer les performances pour les visites répétées depuis la même IP.
5.  Les recherches sont asynchrones pour minimiser l’impact sur le temps de chargement.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité DNSBL :

1.  **Activer la fonction :** La fonction DNSBL est désactivée par défaut. Passez `USE_DNSBL` à `yes` pour l'activer.
2.  **Configurer les serveurs DNSBL :** Ajoutez les noms de domaine des services DNSBL que vous souhaitez utiliser dans le paramètre `DNSBL_LIST`.
3.  **Appliquer les paramètres :** Une fois configuré, BunkerWeb vérifiera automatiquement les connexions entrantes auprès des serveurs DNSBL spécifiés.
4.  **Surveiller l'efficacité :** Consultez la [web UI](web-ui.md) pour voir les statistiques des requêtes bloquées par les vérifications DNSBL.

### Paramètres de configuration

**Général**

| Paramètre    | Défaut                                              | Contexte  | Multiple | Description                                                                                        |
| ------------ | --------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | non      | Activer DNSBL : mettre à `yes` pour activer les vérifications DNSBL pour les connexions entrantes. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | non      | Serveurs DNSBL : liste des domaines de serveurs DNSBL à vérifier, séparés par des espaces.         |

**Listes d’exception**

| Paramètre              | Défaut | Contexte  | Multiple | Description                                                                                         |
| ---------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``     | multisite | oui      | IP/CIDR séparés par des espaces pour lesquels ignorer les vérifications DNSBL (liste blanche).      |
| `DNSBL_IGNORE_IP_URLS` | ``     | multisite | oui      | URL séparées par des espaces fournissant des IP/CIDR à ignorer. Supporte `http(s)://` et `file://`. |

!!! tip "Choisir des serveurs DNSBL"
    Choisissez des fournisseurs DNSBL réputés pour minimiser les faux positifs. La liste par défaut inclut des services bien établis qui conviennent à la plupart des sites web :

    - **bl.blocklist.de :** Liste les IP qui ont été détectées en train d'attaquer d'autres serveurs.
    - **sbl.spamhaus.org :** Se concentre sur les sources de spam et autres activités malveillantes.
    - **xbl.spamhaus.org :** Cible les systèmes infectés, tels que les machines compromises ou les proxys ouverts.

!!! info "Principe de fonctionnement de DNSBL"
    Les serveurs DNSBL fonctionnent en répondant à des requêtes DNS spécialement formatées. Lorsque BunkerWeb vérifie une adresse IP, il inverse l'IP et y ajoute le nom de domaine du DNSBL. Si la requête DNS résultante renvoie une réponse de « succès », l'IP est considérée comme étant sur la liste noire.

!!! warning "Considérations sur la performance"
    Bien que BunkerWeb optimise les recherches DNSBL pour la performance, l'ajout d'un grand nombre de serveurs DNSBL pourrait potentiellement impacter les temps de réponse. Commencez avec quelques serveurs DNSBL réputés et surveillez la performance avant d'en ajouter d'autres.

### Exemples de configuration

=== "Configuration de base"

    Une configuration simple utilisant les serveurs DNSBL par défaut :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Configuration minimale"

    Une configuration minimale se concentrant sur les services DNSBL les plus fiables :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    Cette configuration utilise uniquement :

    - **zen.spamhaus.org** : La liste combinée de Spamhaus est souvent considérée comme suffisante en tant que solution autonome en raison de sa large couverture et de sa réputation de précision. Elle combine les listes SBL, XBL et PBL en une seule requête, la rendant efficace et complète.

=== "Exclure des IP de confiance"

    Vous pouvez exclure certains clients des vérifications DNSBL via des valeurs statiques et/ou des fichiers distants :

    - `DNSBL_IGNORE_IP` : Ajoutez des IP et des plages CIDR séparées par des espaces. Exemple : `192.0.2.10 203.0.113.0/24 2001:db8::/32`.
    - `DNSBL_IGNORE_IP_URLS` : Fournissez des URL dont le contenu liste une IP/CIDR par ligne. Les commentaires commençant par `#` ou `;` sont ignorés. Les entrées en double sont dédupliquées.

    Quand une IP cliente correspond à la liste d’exclusion, BunkerWeb saute les requêtes DNSBL et met en cache le résultat « ok » pour accélérer les requêtes suivantes.

=== "Utiliser des URL distantes"

    La tâche `dnsbl-download` télécharge et met en cache les IP à ignorer toutes les heures :

    - Protocoles : `https://`, `http://` et chemins locaux `file://`.
    - Un cache par URL avec une somme de contrôle empêche les téléchargements redondants (délai de grâce d'1 heure).
    - Fichier fusionné par service : `/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`.
    - Chargé au démarrage et fusionné avec `DNSBL_IGNORE_IP`.

    Exemple combinant des sources statiques et des URL :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://exemple.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "Utiliser des fichiers locaux"

    Chargez des IP à ignorer depuis des fichiers locaux en utilisant des URL `file://` :

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```
