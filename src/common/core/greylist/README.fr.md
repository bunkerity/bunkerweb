Le plugin Greylist adopte une approche flexible : il autorise l’accès aux visiteurs correspondant à des critères donnés tout en maintenant les contrôles de sécurité. Contrairement aux listes noire/blanche, il crée un juste milieu.

Comment ça marche :

1. Vous définissez des critères (IP, réseaux, rDNS, ASN, User‑Agent, motifs d’URI).
2. Un visiteur qui correspond est autorisé, mais reste soumis aux autres contrôles.
3. S’il ne correspond à aucun critère greylist, l’accès est refusé.
4. Des sources externes peuvent alimenter automatiquement la liste.

### Comment l’utiliser

1. Activer : `USE_GREYLIST: yes`.
2. Règles : définissez IP/réseaux, rDNS, ASN, User‑Agent ou URIs.
3. Sources externes : optionnel, configurez des URLs pour mises à jour.
4. Suivi : consultez la [web UI](web-ui.md).

!!! tip "Comportement d’accès" - Visiteurs greylist : accès autorisé mais contrôles appliqués. - Autres visiteurs : accès refusé.

!!! info "Mode stream"
    En mode stream, seuls IP, rDNS et ASN sont pris en compte.

### Paramètres

Général

| Paramètre      | Défaut | Contexte  | Multiple | Description          |
| -------------- | ------ | --------- | -------- | -------------------- |
| `USE_GREYLIST` | `no`   | multisite | non      | Activer la greylist. |

=== "Adresse IP"

    | Paramètre          | Défaut | Contexte  | Multiple | Description                                                    |
    | ------------------ | ------ | --------- | -------- | -------------------------------------------------------------- |
    | `GREYLIST_IP`      |        | multisite | non      | Liste d’IP/réseaux (CIDR) à greylist, séparés par des espaces. |
    | `GREYLIST_IP_URLS` |        | multisite | non      | URLs contenant des IP/réseaux à greylist.                      |

=== "Reverse DNS"

    | Paramètre              | Défaut | Contexte  | Multiple | Description                                  |
    | ---------------------- | ------ | --------- | -------- | -------------------------------------------- |
    | `GREYLIST_RDNS`        |        | multisite | non      | Suffixes de DNS inversés à greylist.         |
    | `GREYLIST_RDNS_GLOBAL` | `yes`  | multisite | non      | Vérifier seulement les IP globales si `yes`. |
    | `GREYLIST_RDNS_URLS`   |        | multisite | non      | URLs contenant des suffixes rDNS à greylist. |

=== "ASN"

    | Paramètre           | Défaut | Contexte  | Multiple | Description                                        |
    | ------------------- | ------ | --------- | -------- | -------------------------------------------------- |
    | `GREYLIST_ASN`      |        | multisite | non      | Numéros d’AS à greylist (séparés par des espaces). |
    | `GREYLIST_ASN_URLS` |        | multisite | non      | URLs contenant des AS à greylist.                  |

=== "User‑Agent"

    | Paramètre                  | Défaut | Contexte  | Multiple | Description                                        |
    | -------------------------- | ------ | --------- | -------- | -------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |        | multisite | non      | Motifs (regex PCRE) d’User‑Agent à greylist.       |
    | `GREYLIST_USER_AGENT_URLS` |        | multisite | non      | URLs contenant des motifs d’User‑Agent à greylist. |

=== "URI"

    | Paramètre           | Défaut | Contexte  | Multiple | Description                                 |
    | ------------------- | ------ | --------- | -------- | ------------------------------------------- |
    | `GREYLIST_URI`      |        | multisite | non      | Motifs d’URI (regex PCRE) à greylist.       |
    | `GREYLIST_URI_URLS` |        | multisite | non      | URLs contenant des motifs d’URI à greylist. |

!!! info "Format d’URL"
    Les paramètres `*_URLS` supportent HTTP/HTTPS et `file:///`. Auth basique possible avec `http://user:pass@url`.

!!! tip "Mises à jour"
    Les listes récupérées par URL sont mises à jour automatiquement toutes les heures.

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
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
