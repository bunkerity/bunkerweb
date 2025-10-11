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
