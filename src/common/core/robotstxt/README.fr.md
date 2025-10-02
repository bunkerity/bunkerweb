Le plugin Robots.txt gère le fichier [robots.txt](https://www.robotstxt.org/) de votre site, indiquant aux robots les zones autorisées/interdites.

Comment ça marche :

Activé, BunkerWeb génère dynamiquement `/robots.txt` à la racine. Les règles sont agrégées dans l’ordre :

1. DarkVisitors (si `ROBOTSTXT_DARKVISITORS_TOKEN`) : bloque des bots/IA connus selon `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` et `ROBOTSTXT_DARKVISITORS_DISALLOW`.
2. Listes communautaires (`ROBOTSTXT_COMMUNITY_LISTS`).
3. URLs personnalisées (`ROBOTSTXT_URLS`).
4. Règles manuelles (`ROBOTSTXT_RULE[_N]`).

Ensuite, les règles à ignorer (`ROBOTSTXT_IGNORE_RULE[_N]`, PCRE) sont filtrées. S’il ne reste rien, un `User-agent: *` + `Disallow: /` par défaut est appliqué. Des sitemaps (`ROBOTSTXT_SITEMAP[_N]`) peuvent être ajoutés.

### DarkVisitors

[DarkVisitors](https://darkvisitors.com/) fournit un `robots.txt` dynamique pour bloquer des bots/IA. Inscrivez‑vous et obtenez un bearer token.

### Comment l’utiliser

1. Activer : `USE_ROBOTSTXT: yes`.
2. Règles : via DarkVisitors, listes communautaires, URLs ou variables `ROBOTSTXT_RULE`.
3. Filtrer (optionnel) : `ROBOTSTXT_IGNORE_RULE_N`.
4. Sitemaps (optionnel) : `ROBOTSTXT_SITEMAP_N`.
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
