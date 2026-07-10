Le plugin Greylist fournit une approche de sécurité flexible qui autorise l'accès des visiteurs tout en conservant les fonctionnalités de sécurité essentielles.

Contrairement aux approches classiques de [blacklist](#blacklist)/[whitelist](#whitelist), qui bloquent ou autorisent complètement l'accès, la greylist crée un compromis en accordant l'accès à certains visiteurs tout en continuant à les soumettre aux contrôles de sécurité.

**Comment ça marche :**

1. Vous définissez les critères des visiteurs à placer en greylist (*adresses IP, réseaux, rDNS, ASN, User-Agent ou motifs d'URI*).
2. Lorsqu'un visiteur correspond à l'un de ces critères, l'accès à votre site lui est accordé, mais les autres fonctionnalités de sécurité restent actives.
3. Si un visiteur ne correspond à aucun critère de greylist, son accès est refusé.
4. Les données de greylist peuvent être automatiquement mises à jour depuis des sources externes selon une planification régulière.

### Comment l'utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Greylist :

1. **Activer la fonctionnalité :** La fonctionnalité Greylist est désactivée par défaut. Mettez le paramètre `USE_GREYLIST` à `yes` pour l'activer.
2. **Configurer les règles de greylist :** Définissez les IP, réseaux, motifs rDNS, ASN, User-Agents ou URI à placer en greylist.
3. **Ajouter des sources externes :** Configurez éventuellement des URL pour télécharger et mettre à jour automatiquement les données de greylist.
4. **Surveiller l'accès :** Consultez l'[interface web](web-ui.md) pour voir quels visiteurs sont autorisés ou refusés.

!!! tip "Comportement du contrôle d'accès"
    Lorsque la fonctionnalité greylist est activée avec le paramètre `USE_GREYLIST` défini à `yes` :

    1. **Visiteurs en greylist :** Ils sont autorisés à accéder au site, mais restent soumis à tous les contrôles de sécurité.
    2. **Visiteurs hors greylist :** Leur accès est entièrement refusé.

!!! info "mode stream"
    En mode stream, seuls les contrôles IP, rDNS et ASN sont effectués.

### Paramètres de configuration

**Général**

| Paramètre      | Défaut | Contexte  | Multiple | Description                                                   |
| -------------- | ------ | --------- | -------- | ------------------------------------------------------------- |
| `USE_GREYLIST` | `no`   | multisite | non      | **Activer Greylist :** Mettre à `yes` pour activer la greylist. |

=== "Adresse IP"
    **Ce que cela fait :** Place les visiteurs en greylist selon leur adresse IP ou leur réseau. Ces visiteurs obtiennent l'accès, mais restent soumis aux contrôles de sécurité.

    | Paramètre          | Défaut | Contexte  | Multiple | Description                                                                                      |
    | ------------------ | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------ |
    | `GREYLIST_IP`      |        | multisite | non      | **Greylist IP :** Liste d'adresses IP ou de réseaux (notation CIDR) à placer en greylist, séparés par des espaces. |
    | `GREYLIST_IP_URLS` |        | multisite | non      | **URL de greylist IP :** Liste d'URL contenant des adresses IP ou des réseaux à placer en greylist, séparées par des espaces. |

=== "DNS inverse"
    **Ce que cela fait :** Place les visiteurs en greylist selon leur nom de domaine inversé. Utile pour autoriser conditionnellement l'accès aux visiteurs de certaines organisations ou de certains réseaux.

    | Paramètre              | Défaut | Contexte  | Multiple | Description                                                                                      |
    | ---------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------ |
    | `GREYLIST_RDNS`        |        | multisite | non      | **Greylist rDNS :** Liste de suffixes DNS inversés à placer en greylist, séparés par des espaces. |
    | `GREYLIST_RDNS_GLOBAL` | `yes`  | multisite | non      | **rDNS global seulement :** Effectue les contrôles de greylist rDNS uniquement sur les adresses IP globales lorsque défini à `yes`. |
    | `GREYLIST_RDNS_URLS`   |        | multisite | non      | **URL de greylist rDNS :** Liste d'URL contenant des suffixes DNS inversés à placer en greylist, séparées par des espaces. |

    !!! info "DNS inverse confirmé par résolution directe (FCrDNS)"
        Les suffixes `GREYLIST_RDNS` sont confirmés par résolution directe : le nom d'hôte PTR correspondant est résolu à nouveau vers une IP et l'accès accordé par la greylist ne s'applique que lorsque cette IP correspond à l'IP du client. Un enregistrement PTR qui ne peut pas être confirmé par résolution directe est considéré comme une possible usurpation et l'accès n'est pas accordé. Cela empêche un attaquant qui contrôle son propre enregistrement PTR de le définir sur un suffixe en greylist afin d'obtenir l'accès.

=== "ASN"
    **Ce que cela fait :** Place les visiteurs de fournisseurs réseau précis en greylist à l'aide des numéros de système autonome. Les ASN identifient le fournisseur ou l'organisation auquel appartient une IP.

    | Paramètre           | Défaut | Contexte  | Multiple | Description                                                                               |
    | ------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |        | multisite | non      | **Greylist ASN :** Liste de numéros de système autonome à placer en greylist, séparés par des espaces. |
    | `GREYLIST_ASN_URLS` |        | multisite | non      | **URL de greylist ASN :** Liste d'URL contenant des ASN à placer en greylist, séparées par des espaces. |

=== "User Agent"
    **Ce que cela fait :** Place les visiteurs en greylist selon le navigateur ou l'outil qu'ils déclarent utiliser. Cela permet un accès contrôlé pour des outils précis tout en conservant les contrôles de sécurité.

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                                                                       |
    | -------------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |        | multisite | non      | **Greylist User-Agent :** Liste de motifs User-Agent (regex PCRE) à placer en greylist, séparés par des espaces. |
    | `GREYLIST_USER_AGENT_URLS` |        | multisite | non      | **URL de greylist User-Agent :** Liste d'URL contenant des motifs User-Agent à placer en greylist. |

=== "URI"
    **Ce que cela fait :** Place en greylist les requêtes vers des URL précises de votre site. Cela permet un accès conditionnel à certains endpoints tout en conservant les contrôles de sécurité.

    | Paramètre           | Défaut | Contexte  | Multiple | Description                                                                           |
    | ------------------- | ------ | --------- | -------- | ------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |        | multisite | non      | **Greylist URI :** Liste de motifs d'URI (regex PCRE) à placer en greylist, séparés par des espaces. |
    | `GREYLIST_URI_URLS` |        | multisite | non      | **URL de greylist URI :** Liste d'URL contenant des motifs d'URI à placer en greylist, séparées par des espaces. |

!!! info "Prise en charge du format d'URL"
    Tous les paramètres `*_URLS` prennent en charge les URL HTTP/HTTPS ainsi que les chemins de fichiers locaux avec le préfixe `file:///`. L'authentification basique est prise en charge avec le format `http://user:pass@url`.

!!! tip "Mises à jour régulières"
    Les greylists provenant d'URL sont automatiquement téléchargées et mises à jour toutes les heures afin que votre protection reste à jour avec les dernières sources de confiance.


### Exemples de configuration

=== "Configuration de base"

    Configuration simple qui applique la greylist au réseau interne et au robot d'exploration d'une entreprise :

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "Configuration avancée"

    Configuration plus complète avec plusieurs critères de greylist :

    ```yaml
    USE_GREYLIST: "yes"

    # Ressources de l'entreprise et robots approuvés
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # ASN de l'entreprise et du partenaire
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # Sources externes de confiance
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Utilisation de fichiers locaux"

    Configuration utilisant des fichiers locaux pour les greylists :

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///path/to/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///path/to/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///path/to/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///path/to/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///path/to/uri-greylist.txt"
    ```

=== "Accès API sélectif"

    Configuration autorisant l'accès à des endpoints d'API précis :

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # Réseau partenaire externe
    ```

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
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
