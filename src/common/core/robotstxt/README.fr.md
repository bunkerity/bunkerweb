Le plugin Robots.txt gère le fichier [robots.txt](https://www.robotstxt.org/) de votre site, indiquant aux robots les zones autorisées/interdites.

Comment ça marche :

Activé, BunkerWeb génère dynamiquement `/robots.txt` à la racine. Les règles sont agrégées dans l’ordre :

1. [DarkVisitors](https://darkvisitors.com/) (si `ROBOTSTXT_DARKVISITORS_TOKEN`) : bloque des bots/IA connus selon les types d’agents et chemins interdits configurés.
2. Listes communautaires (`ROBOTSTXT_COMMUNITY_LISTS`).
3. URLs personnalisées (`ROBOTSTXT_URLS`).
4. Règles manuelles définies via les variables `ROBOTSTXT_RULE`.

Ensuite, les règles à ignorer (`ROBOTSTXT_IGNORE_RULE[_N]`, PCRE) sont filtrées. S’il ne reste rien, un `User-agent: *` + `Disallow: /` par défaut est appliqué. Des sitemaps (`ROBOTSTXT_SITEMAP[_N]`) peuvent être ajoutés.

### Contournement dynamique des bots avec l’API DarkVisitors

[DarkVisitors](https://darkvisitors.com/) fournit un `robots.txt` dynamique pour bloquer des bots/IA. Inscrivez‑vous sur [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) et obtenez un bearer token.

### Comment l’utiliser

1. Activer : mettez le paramètre `USE_ROBOTSTXT` à `yes`.
2. Règles : choisissez une ou plusieurs méthodes pour définir vos règles `robots.txt` :
    - **API DarkVisitors :** fournissez `ROBOTSTXT_DARKVISITORS_TOKEN` et, si nécessaire, `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` et `ROBOTSTXT_DARKVISITORS_DISALLOW`.
    - **Listes communautaires :** indiquez `ROBOTSTXT_COMMUNITY_LISTS` (IDs séparés par des espaces).
    - **URLs personnalisées :** fournissez `ROBOTSTXT_URLS` (URLs séparées par des espaces).
    - **Règles manuelles :** utilisez `ROBOTSTXT_RULE` pour une règle individuelle (plusieurs règles peuvent être précisées avec `ROBOTSTXT_RULE_N`).
3. Filtrer (optionnel) : utilisez `ROBOTSTXT_IGNORE_RULE` (ou `ROBOTSTXT_IGNORE_RULE_N`) pour ignorer des règles selon un motif PCRE.
4. Sitemaps (optionnel) : utilisez `ROBOTSTXT_SITEMAP` (ou `ROBOTSTXT_SITEMAP_N`) pour ajouter des URLs de sitemap.
5. Accès : `http(s)://votre-domaine/robots.txt`.

### Paramètres

| Paramètre                            | Défaut | Contexte  | Multiple | Description                                                          |
| ------------------------------------ | ------ | --------- | -------- | -------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`   | multisite | non      | Active/désactive la fonctionnalité.                                  |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |        | multisite | non      | Jeton Bearer pour l’API DarkVisitors.                                |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |        | multisite | non      | Types d’agents (séparés par virgules) à inclure depuis DarkVisitors. |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`    | multisite | non      | Valeur du champ Disallow envoyée à l’API DarkVisitors.               |
| `ROBOTSTXT_COMMUNITY_LISTS`          |        | multisite | non      | IDs de listes communautaires (séparés par espaces).                  |
| `ROBOTSTXT_URLS`                     |        | multisite | non      | URLs supplémentaires (supporte `file://` et auth basique).           |
| `ROBOTSTXT_RULE`                     |        | multisite | oui      | Règle individuelle `robots.txt`.                                     |
| `ROBOTSTXT_HEADER`                   |        | multisite | oui      | En‑tête (peut être encodé Base64).                                   |
| `ROBOTSTXT_FOOTER`                   |        | multisite | oui      | Pied de page (peut être encodé Base64).                              |
| `ROBOTSTXT_IGNORE_RULE`              |        | multisite | oui      | Motif PCRE d’ignorance de règles.                                    |
| `ROBOTSTXT_SITEMAP`                  |        | multisite | oui      | URL de sitemap.                                                      |

### Exemples

Basique (manuel)

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

Sources dynamiques (DarkVisitors + liste)

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

Combiné

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

En‑tête/Pied de page

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# This is a custom header"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# This is a custom footer"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

Pour en savoir plus : [documentation robots.txt](https://www.robotstxt.org/robotstxt.html).
