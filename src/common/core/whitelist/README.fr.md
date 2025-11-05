Le plugin Whitelist vous permet de définir des clients de confiance qui contournent les autres filtres de sécurité. Les visiteurs correspondant aux règles sont immédiatement autorisés et passent avant les autres contrôles. Pour bloquer des clients indésirables, voir [Blacklist](#blacklist).

Comment ça marche :

1. Vous définissez des critères (IP/réseaux, rDNS, ASN, User‑Agent, URI).
2. Si un visiteur correspond à une règle (et pas à une règle d’ignore), il est autorisé et bypass tous les contrôles.
3. Sinon, il suit le parcours de sécurité standard.
4. Les listes peuvent être mises à jour automatiquement depuis des sources externes.

!!! info "Mode stream"
    En stream, uniquement IP, rDNS et ASN sont évalués.

### Paramètres

Général

| Paramètre       | Défaut | Contexte  | Multiple | Description           |
| --------------- | ------ | --------- | -------- | --------------------- |
| `USE_WHITELIST` | `no`   | multisite | non      | Activer la whitelist. |

=== "Adresse IP"

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                          |
    | -------------------------- | ------ | --------- | -------- | ---------------------------------------------------- |
    | `WHITELIST_IP`             |        | multisite | non      | IP/réseaux (CIDR) autorisés.                         |
    | `WHITELIST_IGNORE_IP`      |        | multisite | non      | IP/réseaux ignorés (bypassent les vérifications IP). |
    | `WHITELIST_IP_URLS`        |        | multisite | non      | URLs contenant IP/réseaux à autoriser.               |
    | `WHITELIST_IGNORE_IP_URLS` |        | multisite | non      | URLs contenant IP/réseaux à ignorer.                 |

=== "Reverse DNS"

    | Paramètre                    | Défaut | Contexte  | Multiple | Description                                  |
    | ---------------------------- | ------ | --------- | -------- | -------------------------------------------- |
    | `WHITELIST_RDNS`             |        | multisite | non      | Suffixes rDNS autorisés.                     |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`  | multisite | non      | Vérifier seulement les IP globales si `yes`. |
    | `WHITELIST_IGNORE_RDNS`      |        | multisite | non      | Suffixes rDNS ignorés.                       |
    | `WHITELIST_RDNS_URLS`        |        | multisite | non      | URLs contenant des suffixes rDNS autorisés.  |
    | `WHITELIST_IGNORE_RDNS_URLS` |        | multisite | non      | URLs contenant des suffixes rDNS à ignorer.  |

=== "ASN"

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                          |
    | --------------------------- | ------ | --------- | -------- | ------------------------------------ |
    | `WHITELIST_ASN`             |        | multisite | non      | Numéros d’AS autorisés.              |
    | `WHITELIST_IGNORE_ASN`      |        | multisite | non      | AS ignorés (bypassent la vérif ASN). |
    | `WHITELIST_ASN_URLS`        |        | multisite | non      | URLs de listes d’AS autorisés.       |
    | `WHITELIST_IGNORE_ASN_URLS` |        | multisite | non      | URLs de listes d’AS à ignorer.       |

=== "User‑Agent"

    | Paramètre                          | Défaut | Contexte  | Multiple | Description                                  |
    | ---------------------------------- | ------ | --------- | -------- | -------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |        | multisite | non      | Motifs (regex PCRE) de User‑Agent autorisés. |
    | `WHITELIST_IGNORE_USER_AGENT`      |        | multisite | non      | Motifs ignorés.                              |
    | `WHITELIST_USER_AGENT_URLS`        |        | multisite | non      | URLs de motifs User‑Agent autorisés.         |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |        | multisite | non      | URLs de motifs User‑Agent à ignorer.         |

=== "URI"

    | Paramètre                   | Défaut | Contexte  | Multiple | Description                          |
    | --------------------------- | ------ | --------- | -------- | ------------------------------------ |
    | `WHITELIST_URI`             |        | multisite | non      | Motifs d’URI (regex PCRE) autorisés. |
    | `WHITELIST_IGNORE_URI`      |        | multisite | non      | Motifs d’URI ignorés.                |
    | `WHITELIST_URI_URLS`        |        | multisite | non      | URLs de motifs d’URI autorisés.      |
    | `WHITELIST_IGNORE_URI_URLS` |        | multisite | non      | URLs de motifs d’URI à ignorer.      |

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
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
