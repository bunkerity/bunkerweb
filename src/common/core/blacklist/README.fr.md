Le plugin Blacklist protège votre site en bloquant l’accès selon divers attributs client. Cette fonctionnalité défend contre les entités malveillantes connues, les scanners et les visiteurs suspects en refusant l’accès en fonction des adresses IP, des réseaux, des entrées DNS inversées (rDNS), des ASN, des user-agents et de motifs d’URI spécifiques.

**Comment ça marche :**

1. Le plugin vérifie les requêtes entrantes par rapport à plusieurs critères de liste noire (adresses IP, réseaux, rDNS, ASN, User-Agent ou motifs d’URI).
2. Les listes noires peuvent être spécifiées directement dans votre configuration ou chargées depuis des URL externes.
3. Si un visiteur correspond à une règle de la liste noire (et ne correspond à aucune règle d’ignorance), l’accès est refusé.
4. Les listes noires sont mises à jour automatiquement à intervalles réguliers à partir des URL configurées.
5. Vous pouvez personnaliser précisément quels critères sont vérifiés et ignorés en fonction de vos besoins de sécurité spécifiques.

### Comment l’utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Blacklist :

1.  **Activer la fonctionnalité :** La fonctionnalité Blacklist est activée par défaut. Si nécessaire, vous pouvez la contrôler avec le paramètre `USE_BLACKLIST`.
2.  **Configurer les règles de blocage :** Définissez quelles IP, quels réseaux, quels motifs rDNS, quels ASN, quels User-Agents ou quelles URI doivent être bloqués.
3.  **Mettre en place des règles d’ignorance :** Spécifiez les exceptions qui doivent contourner les vérifications de la liste noire.
4.  **Ajouter des sources externes :** Configurez des URL pour télécharger et mettre à jour automatiquement les données de la liste noire.
5.  **Surveiller l’efficacité :** Consultez l'[interface web](web-ui.md) pour voir les statistiques sur les requêtes bloquées.

!!! info "Mode stream"
    En mode stream, seules les vérifications par IP, rDNS et ASN seront effectuées.

### Paramètres de configuration

**Général**

| Paramètre                   | Défaut                                                  | Contexte  | Multiple | Description                                                                                                                                  |
| --------------------------- | ------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | non      | **Activer la Blacklist :** Mettre à `yes` pour activer la fonctionnalité de liste noire.                                                     |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | non      | **Listes noires communautaires :** Sélectionnez des listes noires pré-configurées et maintenues par la communauté à inclure dans le blocage. |

=== "Listes noires communautaires"
    **Ce que ça fait :** Vous permet d’ajouter rapidement des listes noires bien entretenues et sourcées par la communauté sans avoir à configurer manuellement les URL.

    Le paramètre `BLACKLIST_COMMUNITY_LISTS` vous permet de choisir parmi des sources de listes noires sélectionnées. Les options disponibles incluent :

    | ID                                        | Description                                                                                                                                                                                                             | Source                                                                                                                                |
    | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
    | `ip:danmeuk-tor-exit`                     | Adresses IP des nœuds de sortie Tor (dan.me.uk)                                                                                                                                                                         | `https://www.dan.me.uk/torlist/?exit`                                                                                                 |
    | `ua:mitchellkrogza-bad-user-agents`       | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, avec anti-DDOS, Wordpress Theme Detector Blocking et Fail2Ban Jail for Repeat Offenders | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list`        |
    | `ip:laurent-minne-data-shield-aggressive` | Data-Shield IPv4 Blocklist - Laurent M. - Pour Web Apps, WordPress, VPS (Apache/Nginx)                                                                                                                                  | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt`          |
    | `ip:laurent-minne-data-shield-critical`   | Data-Shield IPv4 Blocklist - Laurent M. - Pour DMZs, SaaS, API & Actifs Critiques                                                                                                                                       | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_critical_data-shield_ipv4_blocklist.txt` |

    **Configuration :** Spécifiez plusieurs listes séparées par des espaces. Par exemple :
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Listes communautaires vs configuration manuelle"
        Les listes noires communautaires offrent un moyen pratique de démarrer avec des sources de listes noires éprouvées. Vous pouvez les utiliser en parallèle de configurations manuelles d’URL pour une flexibilité maximale.

    !!! note "Remerciements"
        Merci à Laurent Minne d'avoir contribué aux [listes de blocage Data-Shield](https://duggytuxy.github.io/#) !

=== "Adresse IP"
    **Ce que ça fait :** Bloque les visiteurs en fonction de leur adresse IP ou de leur réseau.

    | Paramètre                  | Défaut                                | Contexte  | Multiple | Description                                                                                                                     |
    | -------------------------- | ------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_IP`             |                                       | multisite | non      | **Liste noire d’IP :** Liste d’adresses IP ou de réseaux (notation CIDR) à bloquer, séparés par des espaces.                    |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | non      | **Liste d’ignorance d’IP :** Liste d’adresses IP ou de réseaux qui doivent contourner les vérifications de la liste noire d’IP. |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | non      | **URL de listes noires d’IP :** Liste d’URL contenant des adresses IP ou des réseaux à bloquer, séparés par des espaces.        |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | non      | **URL de listes d’ignorance d’IP :** Liste d’URL contenant des adresses IP ou des réseaux à ignorer.                            |

    Le paramètre par défaut `BLACKLIST_IP_URLS` inclut une URL qui fournit une **liste des nœuds de sortie Tor connus**. C’est une source courante de trafic malveillant et un bon point de départ pour de nombreux sites.

=== "Reverse DNS"
    **Ce que ça fait :** Bloque les visiteurs en fonction de leur nom de domaine inversé. C’est utile pour bloquer les scanners et les crawlers connus en se basant sur les domaines de leur organisation.

    | Paramètre                    | Défaut                  | Contexte  | Multiple | Description                                                                                                                    |
    | ---------------------------- | ----------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | non      | **Liste noire rDNS :** Liste de suffixes de DNS inversé à bloquer, séparés par des espaces.                                    |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | non      | **rDNS global uniquement :** N’effectue des vérifications rDNS que sur les adresses IP globales si mis à `yes`.                |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | non      | **Liste d’ignorance rDNS :** Liste de suffixes de DNS inversé qui doivent contourner les vérifications de la liste noire rDNS. |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | non      | **URL de listes noires rDNS :** Liste d’URL contenant des suffixes de DNS inversé à bloquer.                                   |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | non      | **URL de listes d’ignorance rDNS :** Liste d’URL contenant des suffixes de DNS inversé à ignorer.                              |

    Le paramètre par défaut `BLACKLIST_RDNS` inclut des domaines de scanners courants comme **Shodan** et **Censys**. Ils sont souvent utilisés par des chercheurs en sécurité et des scanners pour identifier des sites vulnérables.

=== "ASN"
    **Ce que ça fait :** Bloque les visiteurs provenant de fournisseurs de réseaux spécifiques. Les ASN sont comme des codes postaux pour Internet—ils identifient à quel fournisseur ou organisation une IP appartient.

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                                 |
    | --------------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |        | multisite | non      | **Liste noire d’ASN :** Liste de numéros de systèmes autonomes à bloquer, séparés par des espaces.          |
    | `BLACKLIST_IGNORE_ASN`      |        | multisite | non      | **Liste d’ignorance d’ASN :** Liste d’ASN qui doivent contourner les vérifications de la liste noire d’ASN. |
    | `BLACKLIST_ASN_URLS`        |        | multisite | non      | **URL de listes noires d’ASN :** Liste d’URL contenant des ASN à bloquer.                                   |
    | `BLACKLIST_IGNORE_ASN_URLS` |        | multisite | non      | **URL de listes d’ignorance d’ASN :** Liste d’URL contenant des ASN à ignorer.                              |

=== "User-Agent"
    **Ce que ça fait :** Bloque les visiteurs en fonction du navigateur ou de l’outil qu’ils prétendent utiliser. C’est efficace contre les bots qui s’identifient honnêtement (comme "ScannerBot" ou "WebHarvestTool").

    | Paramètre                          | Défaut                                                                                                                         | Contexte  | Multiple | Description                                                                                                                                   |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | non      | **Liste noire de User-Agent :** Liste de motifs de User-Agent (regex PCRE) à bloquer, séparés par des espaces.                                |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | non      | **Liste d’ignorance de User-Agent :** Liste de motifs de User-Agent qui doivent contourner les vérifications de la liste noire de User-Agent. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | non      | **URL de listes noires de User-Agent :** Liste d’URL contenant des motifs de User-Agent à bloquer.                                            |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | non      | **URL de listes d’ignorance de User-Agent :** Liste d’URL contenant des motifs de User-Agent à ignorer.                                       |

    Le paramètre par défaut `BLACKLIST_USER_AGENT_URLS` inclut une URL qui fournit une **liste de user agents malveillants connus**. Ils sont souvent utilisés par des bots et des scanners malveillants pour identifier des sites vulnérables.

=== "URI"
    **Ce que ça fait :** Bloque les requêtes vers des URL spécifiques de votre site. C’est utile pour bloquer les tentatives d’accès aux pages d’administration, aux formulaires de connexion ou à d’autres zones sensibles qui pourraient être ciblées.

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                                                                                                           |
    | --------------------------- | ------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |        | multisite | non      | **Liste noire d’URI :** Liste de motifs d’URI (regex PCRE) à bloquer, séparés par des espaces.                        |
    | `BLACKLIST_IGNORE_URI`      |        | multisite | non      | **Liste d’ignorance d’URI :** Liste de motifs d’URI qui doivent contourner les vérifications de la liste noire d’URI. |
    | `BLACKLIST_URI_URLS`        |        | multisite | non      | **URL de listes noires d’URI :** Liste d’URL contenant des motifs d’URI à bloquer.                                    |
    | `BLACKLIST_IGNORE_URI_URLS` |        | multisite | non      | **URL de listes d’ignorance d’URI :** Liste d’URL contenant des motifs d’URI à ignorer.                               |

!!! info "Support des formats d’URL"
    Tous les paramètres `*_URLS` supportent les URL HTTP/HTTPS ainsi que les chemins de fichiers locaux en utilisant le préfixe `file:///`. L’authentification basique est supportée en utilisant le format `http://user:pass@url`.

!!! tip "Mises à jour régulières"
    Les listes noires provenant d’URL sont automatiquement téléchargées et mises à jour toutes les heures pour garantir que votre protection reste à jour contre les dernières menaces.

### Exemples de configuration

=== "Protection de base par IP et User-Agent"

    Une configuration simple qui bloque les nœuds de sortie Tor connus et les user agents malveillants courants en utilisant les listes noires communautaires :

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternativement, vous pouvez utiliser une configuration manuelle par URL :

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Protection avancée avec des règles personnalisées"

    Une configuration plus complète avec des entrées de liste noire personnalisées et des exceptions :

    ```yaml
    USE_BLACKLIST: "yes"

    # Entrées de liste noire personnalisées
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # ASN d'AWS et d'Amazon
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Règles d'ignorance personnalisées
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # Sources de listes noires externes
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Utilisation de fichiers locaux"

    Configuration utilisant des fichiers locaux pour les listes noires :

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///chemin/vers/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///chemin/vers/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///chemin/vers/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///chemin/vers/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///chemin/vers/uri-blacklist.txt"
    ```

### Travailler avec des fichiers de listes locaux

Les paramètres `*_URLS` fournis par les plugins Whitelist, Greylist et Blacklist utilisent le même téléchargeur. Lorsque vous référencez une URL `file:///` :

- Le chemin est résolu dans le conteneur du **scheduler** (dans un déploiement Docker il s’agit généralement de `bunkerweb-scheduler`). Montez-y vos fichiers et vérifiez que l’utilisateur scheduler possède un accès en lecture.
- Chaque fichier est un texte encodé en UTF-8 avec une entrée par ligne. Les lignes vides sont ignorées et les commentaires doivent commencer par `#` ou `;`. Les commentaires `//` ne sont pas pris en charge.
- Valeur attendue selon le type de liste :
  - **Listes IP** acceptent des adresses IPv4/IPv6 ou des réseaux CIDR (par exemple `192.0.2.10` ou `2001:db8::/48`).
  - **Listes rDNS** attendent un suffixe sans espaces (par exemple `.search.msn.com`). Les valeurs sont automatiquement converties en minuscules.
  - **Listes ASN** peuvent contenir uniquement le numéro (`32934`) ou le numéro préfixé par `AS` (`AS15169`).
  - **Listes User-Agent** sont traitées comme des motifs PCRE et la ligne complète est conservée (espaces compris). Placez vos commentaires sur une ligne séparée pour éviter qu’ils ne soient interprétés comme motif.
  - **Listes URI** doivent commencer par `/` et peuvent utiliser des jetons PCRE tels que `^` ou `$`.

Exemples de fichiers conformes :

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
