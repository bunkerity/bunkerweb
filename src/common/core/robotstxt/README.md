The Robots.txt plugin manages the [robots.txt](httpshttps://www.robotstxt.org/) file for your website. This file tells web crawlers and robots which parts of your site they can or cannot access.

**How it works:**

1.  When enabled, BunkerWeb creates a `/robots.txt` file at the root of your website.
2.  The file contains rules and optional sitemap URLs, configured via environment variables.
3.  Web crawlers and automated tools can easily find this file at the standard location.
4.  The content is configured using simple settings that allow you to specify rules and sitemaps.
5.  BunkerWeb automatically formats the file according to the robots.txt standard.

### Dynamic Rule Sets

In addition to manually specifying rules, the Robots.txt plugin can download and aggregate rules from external sources. This allows you to use community-maintained lists or your own custom rule sets hosted at a URL.

-   **Community Lists:** You can select from a list of pre-defined, community-maintained `robots.txt` rule sets.
-   **Custom URLs:** You can provide one or more URLs to fetch additional `robots.txt` rules from.
-   **Ignore Rules:** You can specify regex patterns to filter out unwanted rules from all sources, which is useful for resolving conflicts or customizing lists.

### How to Use

1.  **Enable the feature:** Set the `USE_ROBOTSTXT` setting to `yes` to enable the robots.txt file.
2.  **Configure rules:**
    -   Use `ROBOTSTXT_RULE` to specify rules manually.
    -   Use `ROBOTSTXT_COMMUNITY_LISTS` to include community-maintained lists.
    -   Use `ROBOTSTXT_URLS` to fetch rules from your own URLs.
3.  **Filter rules (optional):** Use `ROBOTSTXT_IGNORE_RULES` to exclude specific rules.
4.  **Add sitemaps (optional):** Specify one or more sitemap URLs using the `ROBOTSTXT_SITEMAP` setting.
5.  **Let BunkerWeb handle the rest:** Once configured, BunkerWeb will automatically create and serve the robots.txt file at the standard location.

### Configuration Settings

| Setting                     | Default | Context   | Multiple | Description                                                                                                                                            |
| --------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_ROBOTSTXT`             | `no`    | multisite | No       | Enables or disables the `robots.txt` feature.                                                                                                          |
| `ROBOTSTXT_COMMUNITY_LISTS` |         | multisite | Yes      | A space-separated list of community-maintained rule sets to include.                                                                                   |
| `ROBOTSTXT_URLS`            |         | multisite | Yes      | A space-separated list of URLs to fetch `robots.txt` rules from.                                                                                       |
| `ROBOTSTXT_RULE`            |         | multisite | Yes      | A single rule for `robots.txt`. Use `ROBOTSTXT_RULE_N` for multiple rules. If no rules are provided from any source, defaults to denying all crawlers. |
| `ROBOTSTXT_IGNORE_RULES`    |         | multisite | Yes      | A single PCRE regex pattern to ignore rules. Any matching rules from any source will be ignored.                                                       |
| `ROBOTSTXT_SITEMAP`         |         | multisite | Yes      | A single sitemap URL. sitemaps.                                                                                                                        |

### Example Configurations

**Basic Configuration**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
```

**With Sitemap**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Using Community Lists**

This example uses two community lists to block AI crawlers and other disallowed bots.

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt robots-disallowed"
```

**Using a Custom URL**

This example fetches additional rules from a custom URL.

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
```

**Ignoring Specific Rules**

This example uses a community list but filters out a specific rule for `Googlebot-Image`.

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_IGNORE_RULES: "User-agent: Googlebot-Image"
ROBOTSTXT_IGNORE_RULES_1: "^Disallow: /wp-admin"
```

**Advanced Configuration (Combined)**

This example combines all features to create a comprehensive `robots.txt` file.

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULES: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

---

For more information, see the [robots.txt documentation](https://www.robotstxt.org/robotstxt.html).
