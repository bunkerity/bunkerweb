The Robots.txt plugin manages the [robots.txt](https://www.robotstxt.org/) file for your website. This file tells web crawlers and robots which parts of your site they can or cannot access.

**How it works:**

When enabled, BunkerWeb dynamically generates the `/robots.txt` file at the root of your website. The rules within this file are aggregated from multiple sources in the following order:

1.  **DarkVisitors API:** If `ROBOTSTXT_DARKVISITORS_TOKEN` is provided, rules are fetched from the [DarkVisitors](https://darkvisitors.com/) API, allowing dynamic blocking of malicious bots and AI crawlers based on configured agent types and disallowed user agents.
2.  **Community Lists:** Rules from pre-defined, community-maintained `robots.txt` lists (specified by `ROBOTSTXT_COMMUNITY_LISTS`) are included.
3.  **Custom URLs:** Rules are fetched from user-provided URLs (specified by `ROBOTSTXT_URLS`).
4.  **Manual Rules:** Rules defined directly via `ROBOTSTXT_RULE` environment variables are added.

All rules from these sources are combined. After aggregation, `ROBOTSTXT_IGNORE_RULE` are applied to filter out any unwanted rules using PCRE regex patterns. Finally, if no rules remain after this entire process, a default `User-agent: *` and `Disallow: /` rule is automatically applied to ensure a basic level of protection. Optional sitemap URLs (specified by `ROBOTSTXT_SITEMAP`) are also included in the final `robots.txt` output.

### Dynamic Bot Circumvention with DarkVisitors API

[DarkVisitors](https://darkvisitors.com/) is a service that provides a dynamic `robots.txt` file to help block known malicious bots and AI crawlers. By integrating with DarkVisitors, BunkerWeb can automatically fetch and serve an up-to-date `robots.txt` that helps protect your site from unwanted automated traffic.

To enable this, you need to sign up at [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) and obtain a bearer token.

### How to Use

1.  **Enable the feature:** Set the `USE_ROBOTSTXT` setting to `yes`.
2.  **Configure rules:** Choose one or more methods to define your `robots.txt` rules:
    -   **DarkVisitors API:** Provide `ROBOTSTXT_DARKVISITORS_TOKEN` and optionally `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` and `ROBOTSTXT_DARKVISITORS_DISALLOW`.
    -   **Community Lists:** Specify `ROBOTSTXT_COMMUNITY_LISTS` (space-separated IDs).
    -   **Custom URLs:** Provide `ROBOTSTXT_URLS` (space-separated URLs).
    -   **Manual Rules:** Use `ROBOTSTXT_RULE` for individual rules (multiple rules can be specified with `ROBOTSTXT_RULE_N`).
3.  **Filter rules (optional):** Use `ROBOTSTXT_IGNORE_RULE_N` to exclude specific rules by regex pattern.
4.  **Add sitemaps (optional):** Use `ROBOTSTXT_SITEMAP_N` for sitemap URLs.
5.  **Obtain the generated robots.txt file:** Once BunkerWeb is running with the above settings, you can access the dynamically generated `robots.txt` file by making an HTTP GET request to `http(s)://your-domain.com/robots.txt`.

### Configuration Settings

| Setting                              | Default | Context   | Multiple | Description                                                                                                                           |
| ------------------------------------ | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`    | multisite | No       | Enables or disables the `robots.txt` feature.                                                                                         |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |         | multisite | No       | Bearer token for the DarkVisitors API.                                                                                                |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |         | multisite | No       | Comma-separated list of agent types (e.g., `AI Data Scraper`) to include from DarkVisitors.                                           |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`     | multisite | No       | A string specifying which URLs are disallowed. This value will be sent as the disallow field when contacting the DarkVisitors API.    |
| `ROBOTSTXT_COMMUNITY_LISTS`          |         | multisite | No       | Space-separated list of community-maintained rule set IDs to include.                                                                 |
| `ROBOTSTXT_URLS`                     |         | multisite | No       | Space-separated list of URLs to fetch additional `robots.txt` rules from. Supports `file://` and basic auth (`http://user:pass@url`). |
| `ROBOTSTXT_RULE`                     |         | multisite | Yes      | A single rule for `robots.txt`.                                                                                                       |
| `ROBOTSTXT_HEADER`                   |         | multisite | Yes      | Header for `robots.txt` file (before rules). Can be Base64 encoded.                                                                   |
| `ROBOTSTXT_FOOTER`                   |         | multisite | Yes      | Footer for `robots.txt` file (after rules). Can be Base64 encoded.                                                                    |
| `ROBOTSTXT_IGNORE_RULE`              |         | multisite | Yes      | A single PCRE regex pattern to ignore rules.                                                                                          |
| `ROBOTSTXT_SITEMAP`                  |         | multisite | Yes      | A single sitemap URL.                                                                                                                 |

### Example Configurations

**Basic Manual Rules**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Using Dynamic Sources (DarkVisitors & Community List)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "your-darkvisitors-token-here"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

**Combined Configuration**

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

**With Header and Footer**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# This is a custom header"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# This is a custom footer"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

---

For more information, see the [robots.txt documentation](https://www.robotstxt.org/robotstxt.html).
