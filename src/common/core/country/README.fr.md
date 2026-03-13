Le plugin Country active le géo‑blocage et permet de restreindre l’accès selon la localisation géographique des visiteurs. Utile pour la conformité régionale, limiter la fraude associée à des zones à risque et appliquer des restrictions de contenu selon les frontières.

Comment ça marche :

1. À chaque visite, BunkerWeb détermine le pays d’origine via l’adresse IP.
2. Votre configuration définit une liste blanche (autorisés) ou noire (bloqués).
3. En liste blanche : seuls les pays listés sont autorisés.
4. En liste noire : les pays listés sont refusés.
5. Le résultat est mis en cache pour les visites répétées.

### Comment l’utiliser

1. Stratégie : choisir liste blanche (peu de pays autorisés) ou liste noire (bloquer certains pays).
2. Codes ou groupes : ajoutez des codes ISO 3166‑1 alpha‑2 (US, GB, FR) et/ou des tokens de groupe pris en charge (comme `@EU`, `@SCHENGEN`) à `WHITELIST_COUNTRY` ou `BLACKLIST_COUNTRY`.
3. Application : une fois configuré, la restriction s’applique à tous les visiteurs.
4. Suivi : consultez la [web UI](web-ui.md) pour les statistiques par pays.

### Paramètres

| Paramètre           | Défaut | Contexte  | Multiple | Description                                                                                           |
| ------------------- | ------ | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |        | multisite | non      | Liste blanche : codes pays et/ou tokens de groupe, séparés par des espaces. Seuls ces pays sont autorisés. |
| `BLACKLIST_COUNTRY` |        | multisite | non      | Liste noire : codes pays et/ou tokens de groupe, séparés par des espaces. Ces pays sont bloqués.           |

### Groupes de pays pris en charge

Vous pouvez utiliser des tokens de groupe préfixés par `@`. Ils sont étendus côté serveur en pays membres :

- `@EU` : États membres de l’Union européenne.
- `@SCHENGEN` : pays de l’espace Schengen.
- `@EEA` : Espace économique européen (`@EU` + Islande, Liechtenstein, Norvège).
- `@BENELUX` : Belgique, Pays-Bas, Luxembourg.
- `@DACH` : zone germanophone de référence (Allemagne, Autriche, Suisse).
- `@NORDICS` : pays nordiques (Danemark, Finlande, Islande, Norvège, Suède).
- `@USMCA` : zone de l’accord USMCA (États-Unis, Canada, Mexique).
- `@FIVE_EYES` : pays de l’alliance de renseignement Five Eyes.
- `@ASEAN` : États membres de l’ASEAN en Asie du Sud-Est.
- `@GCC` : États membres du Conseil de coopération du Golfe.
- `@G7` : pays du Groupe des Sept.
- `@LATAM` : ensemble Amérique latine utilisé par ce plugin.

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
    WHITELIST_COUNTRY: "@EU"
    ```

=== "Groupe + pays explicites"

    ```yaml
    WHITELIST_COUNTRY: "@SCHENGEN GB"
    ```

=== "Blocage pays à risque"

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```
