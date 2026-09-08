Le plugin Whitelist vous permet de définir une liste d'adresses IP de confiance qui contournent les autres filtres de sécurité.
Pour bloquer plutôt des clients indésirables, consultez le [plugin Blacklist](#blacklist).

Le plugin Whitelist fournit une approche complète pour autoriser explicitement l'accès à votre site web selon différents attributs client. Cette fonctionnalité agit comme un mécanisme de sécurité : les visiteurs correspondant à des critères précis obtiennent un accès immédiat, tandis que tous les autres doivent passer les contrôles de sécurité habituels.

**Comment ça marche :**

1. Vous définissez les critères des visiteurs à placer en "whitelist" (*adresses IP, réseaux, rDNS, ASN, User-Agent ou motifs d'URI*).
2. Lorsqu'un visiteur tente d'accéder à votre site, BunkerWeb vérifie s'il correspond à l'un de ces critères de whitelist.
3. Si un visiteur correspond à une règle de whitelist (et ne correspond à aucune règle d'ignore), l'accès à votre site lui est accordé et il **contourne tous les autres contrôles de sécurité**.
4. Si un visiteur ne correspond à aucun critère de whitelist, il passe normalement par tous les contrôles de sécurité habituels.
5. Les whitelists peuvent être automatiquement mises à jour depuis des sources externes selon une planification régulière.

### Comment l'utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Whitelist :

1. **Activer la fonctionnalité :** La fonctionnalité Whitelist est désactivée par défaut. Mettez le paramètre `USE_WHITELIST` à `yes` pour l'activer.
2. **Configurer les règles d'autorisation :** Définissez les IP, réseaux, motifs rDNS, ASN, User-Agents ou URI à placer en whitelist.
3. **Définir les règles d'ignore :** Indiquez les exceptions qui doivent contourner les contrôles de whitelist.
4. **Ajouter des sources externes :** Configurez des URL pour télécharger et mettre à jour automatiquement les données de whitelist.
5. **Surveiller l'accès :** Consultez l'[interface web](web-ui.md) pour voir quels visiteurs sont autorisés ou refusés.

!!! info "mode stream"
    En mode stream, seuls les contrôles IP, rDNS et ASN sont effectués.

### Paramètres de configuration

**Général**

| Paramètre       | Défaut | Contexte  | Multiple | Description                                                           |
| --------------- | ------ | --------- | -------- | --------------------------------------------------------------------- |
| `USE_WHITELIST` | `no`   | multisite | non      | **Activer Whitelist :** Mettre à `yes` pour activer la fonctionnalité whitelist. |

=== "Adresse IP"
    **Ce que cela fait :** Place les visiteurs en whitelist selon leur adresse IP ou leur réseau. Ces visiteurs contourneront tous les contrôles de sécurité.

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                                                                                   |
    | -------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |        | multisite | non      | **Whitelist IP :** Liste d'adresses IP ou de réseaux (notation CIDR) à autoriser, séparés par des espaces.    |
    | `WHITELIST_IGNORE_IP`      |        | multisite | non      | **Liste d'ignore IP :** Liste d'adresses IP ou de réseaux qui doivent contourner les contrôles de whitelist IP. |
    | `WHITELIST_IP_URLS`        |        | multisite | non      | **URL de whitelist IP :** Liste d'URL contenant des adresses IP ou réseaux à placer en whitelist, séparées par des espaces. |
    | `WHITELIST_IGNORE_IP_URLS` |        | multisite | non      | **URL de liste d'ignore IP :** Liste d'URL contenant des adresses IP ou réseaux à ignorer.                    |

=== "DNS inverse"
    **Ce que cela fait :** Place les visiteurs en whitelist selon leur nom de domaine inversé. C'est utile pour autoriser l'accès à des visiteurs de certaines organisations ou de certains réseaux via leur domaine.

    | Paramètre                    | Défaut | Contexte  | Multiple | Description                                                                                                  |
    | ---------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------ |
    | `WHITELIST_RDNS`             |        | multisite | non      | **Whitelist rDNS :** Liste de suffixes DNS inversés à autoriser, séparés par des espaces.                    |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`  | multisite | non      | **rDNS global seulement :** Effectue les contrôles de whitelist rDNS uniquement sur les adresses IP globales lorsque défini à `yes`. |
    | `WHITELIST_IGNORE_RDNS`      |        | multisite | non      | **Liste d'ignore rDNS :** Liste de suffixes DNS inversés qui doivent contourner les contrôles de whitelist rDNS. |
    | `WHITELIST_RDNS_URLS`        |        | multisite | non      | **URL de whitelist rDNS :** Liste d'URL contenant des suffixes DNS inversés à placer en whitelist, séparées par des espaces. |
    | `WHITELIST_IGNORE_RDNS_URLS` |        | multisite | non      | **URL de liste d'ignore rDNS :** Liste d'URL contenant des suffixes DNS inversés à ignorer.                  |

=== "ASN"
    **Ce que cela fait :** Place les visiteurs de fournisseurs réseau précis en whitelist à l'aide des numéros de système autonome. Les ASN identifient le fournisseur ou l'organisation auquel appartient une IP.

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                  |
    | --------------------------- | ------ | --------- | -------- | -------------------------------------------------------------------------------------------- |
    | `WHITELIST_ASN`             |        | multisite | non      | **Whitelist ASN :** Liste de numéros de système autonome à autoriser, séparés par des espaces. |
    | `WHITELIST_IGNORE_ASN`      |        | multisite | non      | **Liste d'ignore ASN :** Liste d'ASN qui doivent contourner les contrôles de whitelist ASN.   |
    | `WHITELIST_ASN_URLS`        |        | multisite | non      | **URL de whitelist ASN :** Liste d'URL contenant des ASN à placer en whitelist, séparées par des espaces. |
    | `WHITELIST_IGNORE_ASN_URLS` |        | multisite | non      | **URL de liste d'ignore ASN :** Liste d'URL contenant des ASN à ignorer.                     |

=== "User Agent"
    **Ce que cela fait :** Place les visiteurs en whitelist selon le navigateur ou l'outil qu'ils déclarent utiliser. C'est efficace pour autoriser l'accès à des outils ou services connus précis.

    | Paramètre                          | Défaut | Contexte  | Multiple | Description                                                                                              |
    | ---------------------------------- | ------ | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |        | multisite | non      | **Whitelist User-Agent :** Liste de motifs User-Agent (regex PCRE) à autoriser, séparés par des espaces. |
    | `WHITELIST_IGNORE_USER_AGENT`      |        | multisite | non      | **Liste d'ignore User-Agent :** Liste de motifs User-Agent qui doivent contourner les contrôles de whitelist User-Agent. |
    | `WHITELIST_USER_AGENT_URLS`        |        | multisite | non      | **URL de whitelist User-Agent :** Liste d'URL contenant des motifs User-Agent à placer en whitelist.      |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |        | multisite | non      | **URL de liste d'ignore User-Agent :** Liste d'URL contenant des motifs User-Agent à ignorer.             |

=== "URI"
    **Ce que cela fait :** Place en whitelist les requêtes vers des URL précises de votre site. C'est utile pour autoriser l'accès à certains endpoints indépendamment des autres facteurs.

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                   |
    | --------------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------- |
    | `WHITELIST_URI`             |        | multisite | non      | **Whitelist URI :** Liste de motifs d'URI (regex PCRE) à autoriser, séparés par des espaces.  |
    | `WHITELIST_IGNORE_URI`      |        | multisite | non      | **Liste d'ignore URI :** Liste de motifs d'URI qui doivent contourner les contrôles de whitelist URI. |
    | `WHITELIST_URI_URLS`        |        | multisite | non      | **URL de whitelist URI :** Liste d'URL contenant des motifs d'URI à placer en whitelist, séparées par des espaces. |
    | `WHITELIST_IGNORE_URI_URLS` |        | multisite | non      | **URL de liste d'ignore URI :** Liste d'URL contenant des motifs d'URI à ignorer.              |

=== "Règles composites (AND)"
    **Fonctionnement :** exiger plusieurs critères *simultanément*. Les listes simples ci-dessus fonctionnent en OU : une seule correspondance suffit pour que le visiteur soit placé en liste blanche. Une règle fonctionne en ET : tous ses termes doivent correspondre. Cela permet de cibler précisément un comportement.

    | Paramètre | Défaut | Contexte | Multiple | Description |
    | --------- | ------ | -------- | -------- | ----------- |
    | `WHITELIST_RULE` | | multisite | yes | **Règle de liste blanche :** termes reliés par ` AND ` ; tous doivent correspondre. |

    Les termes sont séparés par le texte littéral ` AND `, en majuscules, avec exactement une espace de chaque côté :

    ```
    <rule> := <term> ( " AND " <term> )*
    <term> := [ "NOT " ] <kind> ":" <value>
    <kind> := ip | country | asn | rdns | ua | uri
    ```

    `user_agent` est un alias de `ua`. Une `<value>` peut être un jeton de groupe de ressources comme `@office`, résolu selon le type du terme. Les règles utilisent les suffixes numériques habituels : `WHITELIST_RULE_1`, `WHITELIST_RULE_2`, etc.

    ```yaml
    USE_WHITELIST: "yes"
    # the monitoring probe, but only from the monitoring network
    WHITELIST_RULE_1: "ip:10.20.0.0/16 AND ua:^HealthCheck/"
    # the office network, except the guest VLAN's ASN
    WHITELIST_RULE_2: "ip:@office AND NOT asn:64500"
    ```

    !!! warning "OU entre les règles, ET au sein d'une règle"
        **Les règles sont reliées par OU**, entre elles et avec les listes simples : un visiteur correspondant à `WHITELIST_IP` ou à une seule règle est placé en liste blanche. **Les termes d'une règle sont reliés par ET** : tous doivent correspondre. Deux critères écrits dans deux règles forment un OU ; les mêmes critères écrits dans une seule règle forment un ET.

    !!! info "Limites"
        - Un terme dont la requête ne fournit pas le sujet est **inconnu** : une règle contenant ce terme ne correspond jamais, même avec `NOT`. `ua:` et `uri:` sont toujours inconnus en mode stream ; `ua:` l'est aussi sans en-tête `User-Agent`. Une recherche échouée (base GeoIP absente, erreur de résolution) produit également un résultat inconnu. Une IP privée, en revanche, n'a explicitement aucun ASN et son pays est `local` : `NOT asn:…` peut donc lui correspondre.
        - Une règle contenant `ua:` ou `uri:` ne peut pas correspondre à un service stream. Elle n'est pas refusée, car la même configuration peut aussi servir du HTTP, mais un avertissement nommant la règle apparaît au chargement.
        - Une règle composée uniquement de termes `NOT` est valide, mais correspond à presque toutes les requêtes ; elle produit le même type d'avertissement.
        - Il n'existe pas de syntaxe d'échappement. Une regex `ua:` ou `uri:` ne peut pas contenir « and » entouré d'espaces, quelle que soit la casse : la règle serait refusée à l'enregistrement.
        - Un terme `rdns:` fait l'objet d'une confirmation directe, comme `WHITELIST_RDNS` : le nom PTR correspondant est résolu et le terme n'est vrai que si cette résolution renvoie l'IP du client.

    !!! warning "Une règle saute les vérifications suivantes sans désactiver ModSecurity"
        Une règle de liste blanche saute les vérifications BunkerWeb **suivantes**, comme une liste simple. Elle ne désactive **pas** ModSecurity.

        ModSecurity consulte la variable `is_whitelisted` dans sa règle de phase 1 `ctl:ruleEngine=Off`. Cette variable est écrite pendant la phase `set`, avant ModSecurity, uniquement à partir du **cache** de liste blanche du visiteur. Cette phase n'évalue rien elle-même, car elle ne peut pas suspendre son exécution alors qu'un terme `rdns:` exige une résolution. Une correspondance de liste simple remplit ce cache et atteint donc ModSecurity dès la deuxième requête. Le verdict d'une règle n'est jamais mis en cache (seul le résultat de chaque terme l'est, dans son propre espace de noms) : une requête autorisée **uniquement** par une règle traverse intégralement ModSecurity et OWASP CRS à chaque fois.

        Une règle précise maintient ainsi le WAF pour le trafic autorisé. Utilisez une liste simple si vous avez besoin du comportement des listes simples.

!!! info "Prise en charge du format d'URL"
    Tous les paramètres `*_URLS` prennent en charge les URL HTTP/HTTPS ainsi que les chemins de fichiers locaux avec le préfixe `file:///`. L'authentification basique est prise en charge avec le format `http://user:pass@url`.

!!! tip "Mises à jour régulières"
    Les whitelists provenant d'URL sont automatiquement téléchargées et mises à jour toutes les heures afin que votre protection reste à jour avec les dernières sources de confiance.

!!! warning "Contournement de sécurité"
    Les visiteurs en whitelist **contourneront complètement tous les autres contrôles de sécurité** de BunkerWeb, y compris les règles WAF, la limitation de débit, la détection des mauvais bots et tout autre mécanisme de sécurité. Utilisez la whitelist uniquement pour des sources de confiance dont vous êtes absolument certain.


### Exemples de configuration

=== "Accès d'organisation de base"

    Configuration simple qui place en whitelist les IP des bureaux de l'entreprise :

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "Configuration avancée"

    Configuration plus complète avec plusieurs critères de whitelist :

    ```yaml
    USE_WHITELIST: "yes"

    # Ressources de l'entreprise et des partenaires de confiance
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # ASN de l'entreprise et du partenaire
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # Sources externes de confiance
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Utilisation de fichiers locaux"

    Configuration utilisant des fichiers locaux pour les whitelists :

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///path/to/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///path/to/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///path/to/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///path/to/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///path/to/uri-whitelist.txt"
    ```

=== "Motif d'accès API"

    Configuration centrée sur l'autorisation d'accès à certains endpoints d'API uniquement :

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # Réseau interne pour tous les endpoints
    ```

=== "Robots d'exploration connus"

    Configuration qui place en whitelist les robots d'exploration courants des moteurs de recherche et réseaux sociaux :

    ```yaml
    USE_WHITELIST: "yes"

    # Vérification par DNS inverse pour plus de sécurité
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # Vérifier uniquement les IP globales
    ```

    Cette configuration permet aux robots d'exploration légitimes d'indexer votre site sans être soumis à la limitation de débit ou à d'autres mesures de sécurité susceptibles de les bloquer. Les contrôles rDNS aident à vérifier que les robots proviennent bien des entreprises qu'ils déclarent.

### Travailler avec des fichiers de listes locaux

Les paramètres `*_URLS` fournis par les plugins Whitelist, Greylist et Blacklist utilisent le même téléchargeur. Lorsque vous référencez une URL `file:///` :

- Le chemin est résolu dans le conteneur du **scheduler** (dans un déploiement Docker il s'agit généralement de `bunkerweb-scheduler`). Montez-y vos fichiers et vérifiez que l'utilisateur scheduler possède un accès en lecture.
- Chaque fichier est un texte encodé en UTF-8 avec une entrée par ligne. Les lignes vides sont ignorées et les commentaires doivent commencer par `#` ou `;`. Les commentaires `//` ne sont pas pris en charge.
- Valeur attendue selon le type de liste :
  - **Listes IP** acceptent des adresses IPv4/IPv6 ou des réseaux CIDR (par exemple `192.0.2.10` ou `2001:db8::/48`).
  - **Listes rDNS** attendent un suffixe sans espaces (par exemple `.search.msn.com`). Les valeurs sont automatiquement converties en minuscules.
  - **Listes ASN** peuvent contenir uniquement le numéro (`32934`) ou le numéro préfixé par `AS` (`AS15169`).
  - **Listes User-Agent** sont traitées comme des motifs PCRE et la ligne complète est conservée (espaces compris). Placez vos commentaires sur une ligne séparée pour éviter qu'ils ne soient interprétés comme motif.
  - **Listes URI** doivent commencer par `/` et peuvent utiliser des jetons PCRE tels que `^` ou `$`.

Exemples de fichiers conformes :

```text
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
