The Robots.txt plugin manages the [robots.txt](https://www.robotstxt.org/) file for your website. This file tells web crawlers and robots which parts of your site they can or cannot access.

**How it works:**

1. When enabled, BunkerWeb creates a `/robots.txt` file at the root of your website.
2. The file contains rules and optional sitemap URLs, configured via environment variables.
3. Web crawlers and automated tools can easily find this file at the standard location.
4. The content is configured using simple settings that allow you to specify rules and sitemaps.
5. BunkerWeb automatically formats the file according to the robots.txt standard.

### How to Use

1. **Enable the feature:** Set the `USE_ROBOTSTXT` setting to `yes` to enable the robots.txt file.
2. **Configure rules:** Specify one or more rules using the `ROBOTSTXT_RULE` setting (e.g., `User-agent: *`, `Disallow: /private`).
3. **Add sitemaps (optional):** Specify one or more sitemap URLs using the `ROBOTSTXT_SITEMAP` setting.
4. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb will automatically create and serve the robots.txt file at the standard location.

### Configuration Settings

| Setting             | Default | Context   | Multiple | Description                                                                                                                        |
| ------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_ROBOTSTXT`     | `no`    | multisite | no       | **Enable robots.txt:** Set to `yes` to enable the robots.txt file.                                                                 |
| `ROBOTSTXT_RULE`    |         | multisite | yes      | **Rule:** Each line in robots.txt (e.g., user-agent, disallow). (If empty, the default rule is `User-agent: *` and `Disallow: /`). |
| `ROBOTSTXT_SITEMAP` |         | multisite | yes      | **Sitemap:** Sitemap URL(s) to include.                                                                                            |

### Example Configurations

**Basic Configuration**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_2: "Disallow: /private"
```

**With Sitemap**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_2: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Multiple Sitemaps**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_2: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
ROBOTSTXT_SITEMAP_2: "https://example.com/sitemap-news.xml"
```

---

For more information, see the [robots.txt documentation](https://www.robotstxt.org/robotstxt.html).
