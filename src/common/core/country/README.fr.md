Le plugin Country active le géo‑blocage et permet de restreindre l’accès selon la localisation géographique des visiteurs. Utile pour la conformité régionale, limiter la fraude associée à des zones à risque et appliquer des restrictions de contenu selon les frontières.

Comment ça marche :

1. À chaque visite, BunkerWeb détermine le pays d’origine via l’adresse IP.
2. Votre configuration définit une liste blanche (autorisés) ou noire (bloqués).
3. En liste blanche : seuls les pays listés sont autorisés.
4. En liste noire : les pays listés sont refusés.
5. Le résultat est mis en cache pour les visites répétées.

### Comment l’utiliser

1. Stratégie : choisir liste blanche (peu de pays autorisés) ou liste noire (bloquer certains pays).
2. Codes pays : ajoutez des codes ISO 3166‑1 alpha‑2 (US, GB, FR) à `WHITELIST_COUNTRY` ou `BLACKLIST_COUNTRY`.
3. Application : une fois configuré, la restriction s’applique à tous les visiteurs.
4. Suivi : consultez la [web UI](web-ui.md) pour les statistiques par pays.

### Paramètres

| Paramètre           | Défaut | Contexte  | Multiple | Description                                                                                           |
| ------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |        | multisite | non      | Liste blanche : codes pays ISO 3166‑1 alpha‑2 séparés par des espaces. Seuls ces pays sont autorisés. |
| `BLACKLIST_COUNTRY` |        | multisite | non      | Liste noire : codes pays ISO 3166‑1 alpha‑2 séparés par des espaces. Ces pays sont bloqués.           |

!!! tip "Liste blanche vs noire"
Liste blanche : accès restreint à quelques pays. Liste noire : bloquer des régions problématiques et autoriser le reste.

!!! warning "Priorité"
Si une liste blanche et une liste noire sont définies, la liste blanche a priorité : si le pays n’y figure pas, l’accès est refusé.

!!! info "Détection du pays"
BunkerWeb utilise la base mmdb [db‑ip lite](https://db-ip.com/db/download/ip-to-country-lite).

### Exemples

=== "Liste blanche uniquement"

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Liste noire uniquement"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "UE uniquement"

    ```yaml
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "Blocage pays à risque"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```
