The Blacklist plugin provides robust protection for your website by blocking access based on various client attributes. This feature defends against known malicious entities, scanners, and suspicious visitors by denying access based on IP addresses, networks, reverse DNS entries, ASNs, user agents, and specific URI patterns.

**How it works:**

1. The plugin checks incoming requests against multiple blacklist criteria (IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns).
2. Blacklists can be specified directly in your configuration or loaded from external URLs.
3. If a visitor matches any blacklist rule (and does not match any ignore rule), access is denied.
4. Blacklists are automatically updated on a regular schedule from configured URLs.
5. You can customize exactly which criteria are checked and ignored based on your specific security needs.

### How to Use

Follow these steps to configure and use the Blacklist feature:

1. **Enable the feature:** The Blacklist feature is enabled by default. If needed, you can control this with the `USE_BLACKLIST` setting.
2. **Configure block rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be blocked.
3. **Set up ignore rules:** Specify any exceptions that should bypass the blacklist checks.
4. **Add external sources:** Configure URLs for automatically downloading and updating blacklist data.
5. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on blocked requests.

!!! info "stream mode"
    When using stream mode, only IP, rDNS, and ASN checks will be performed.

### Configuration Settings

**General**

| Setting                     | Default                                                 | Context   | Multiple | Description                                                                                             |
| --------------------------- | ------------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | no       | **Enable Blacklist:** Set to `yes` to enable the blacklist feature.                                     |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | no       | **Community Blacklists:** Select pre-configured community-maintained blacklists to include in blocking. |

=== "Community Blacklists"
    **What this does:** Enables you to quickly add well-maintained, community-sourced blacklists without having to manually configure URLs.

    The `BLACKLIST_COMMUNITY_LISTS` setting allows you to select from curated blacklist sources. Available options include:

    | ID                                        | Description                                                                                                                                                                                                              | Source                                                                                                                                |
    | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
    | `ip:danmeuk-tor-exit`                     | Tor Exit Nodes IPs (dan.me.uk)                                                                                                                                                                                           | `https://www.dan.me.uk/torlist/?exit`                                                                                                 |
    | `ua:mitchellkrogza-bad-user-agents`       | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, with anti-DDOS, Wordpress Theme Detector Blocking and Fail2Ban Jail for Repeat Offenders | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list`        |
    | `ip:laurent-minne-data-shield-aggressive` | Data-Shield IPv4 Blocklist - Laurent M. - For Web Apps, WordPress, VPS (Apache/Nginx)                                                                                                                                    | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt`          |
    | `ip:laurent-minne-data-shield-critical`   | Data-Shield IPv4 Blocklist - Laurent M. - For DMZs, SaaS, API & Critical Assets                                                                                                                                          | `https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_critical_data-shield_ipv4_blocklist.txt` |

    **Configuration:** Specify multiple lists separated by spaces. For example:
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Community vs Manual Configuration"
        Community blacklists provide a convenient way to get started with proven blacklist sources. You can use them alongside manual URL configurations for maximum flexibility.

    !!! note "Acknowledgements"
        Thank you Laurent Minne for contributing the [Data-Shield blocklists](https://duggytuxy.github.io/#)!

=== "IP Address"
    **What this does:** Blocks visitors based on their IP address or network.

    | Setting                    | Default                               | Context   | Multiple | Description                                                                                            |
    | -------------------------- | ------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_IP`             |                                       | multisite | no       | **IP Blacklist:** List of IP addresses or networks (CIDR notation) to block, separated by spaces.      |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | no       | **IP Ignore List:** List of IP addresses or networks that should bypass IP blacklist checks.           |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | no       | **IP Blacklist URLs:** List of URLs containing IP addresses or networks to block, separated by spaces. |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | no       | **IP Ignore List URLs:** List of URLs containing IP addresses or networks to ignore.                   |

    The default `BLACKLIST_IP_URLS` setting includes a URL that provides a **list of known Tor exit nodes**. This is a common source of malicious traffic and is a good starting point for many sites.

=== "Reverse DNS"
    **What this does:** Blocks visitors based on their reverse domain name. This is useful for blocking known scanners and crawlers based on their organization domains.

    | Setting                      | Default                 | Context   | Multiple | Description                                                                                          |
    | ---------------------------- | ----------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | no       | **rDNS Blacklist:** List of reverse DNS suffixes to block, separated by spaces.                      |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | no       | **rDNS Global Only:** Only perform rDNS checks on global IP addresses when set to `yes`.             |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | no       | **rDNS Ignore List:** List of reverse DNS suffixes that should bypass rDNS blacklist checks.         |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | no       | **rDNS Blacklist URLs:** List of URLs containing reverse DNS suffixes to block, separated by spaces. |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | no       | **rDNS Ignore List URLs:** List of URLs containing reverse DNS suffixes to ignore.                   |

    The default `BLACKLIST_RDNS` setting includes common scanner domains like **Shodan** and **Censys**. These are often used by security researchers and scanners to identify vulnerable sites.

=== "ASN"
    **What this does:** Blocks visitors from specific network providers. ASNs are like ZIP codes for the Internet—they identify which provider or organization an IP belongs to.

    | Setting                     | Default | Context   | Multiple | Description                                                                         |
    | --------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |         | multisite | no       | **ASN Blacklist:** List of Autonomous System Numbers to block, separated by spaces. |
    | `BLACKLIST_IGNORE_ASN`      |         | multisite | no       | **ASN Ignore List:** List of ASNs that should bypass ASN blacklist checks.          |
    | `BLACKLIST_ASN_URLS`        |         | multisite | no       | **ASN Blacklist URLs:** List of URLs containing ASNs to block, separated by spaces. |
    | `BLACKLIST_IGNORE_ASN_URLS` |         | multisite | no       | **ASN Ignore List URLs:** List of URLs containing ASNs to ignore.                   |

=== "User Agent"
    **What this does:** Blocks visitors based on the browser or tool they claim to be using. This is effective against bots that honestly identify themselves (such as "ScannerBot" or "WebHarvestTool").

    | Setting                            | Default                                                                                                                        | Context   | Multiple | Description                                                                                             |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | no       | **User-Agent Blacklist:** List of User-Agent patterns (PCRE regex) to block, separated by spaces.       |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | no       | **User-Agent Ignore List:** List of User-Agent patterns that should bypass User-Agent blacklist checks. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | no       | **User-Agent Blacklist URLs:** List of URLs containing User-Agent patterns to block.                    |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | no       | **User-Agent Ignore List URLs:** List of URLs containing User-Agent patterns to ignore.                 |

    The default `BLACKLIST_USER_AGENT_URLS` setting includes a URL that provides a **list of known bad user agents**. These are often used by malicious bots and scanners to identify vulnerable sites.

=== "URI"
    **What this does:** Blocks requests to specific URLs on your site. This is helpful for blocking attempts to access admin pages, login forms, or other sensitive areas that might be targeted.

    | Setting                     | Default | Context   | Multiple | Description                                                                                 |
    | --------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |         | multisite | no       | **URI Blacklist:** List of URI patterns (PCRE regex) to block, separated by spaces.         |
    | `BLACKLIST_IGNORE_URI`      |         | multisite | no       | **URI Ignore List:** List of URI patterns that should bypass URI blacklist checks.          |
    | `BLACKLIST_URI_URLS`        |         | multisite | no       | **URI Blacklist URLs:** List of URLs containing URI patterns to block, separated by spaces. |
    | `BLACKLIST_IGNORE_URI_URLS` |         | multisite | no       | **URI Ignore List URLs:** List of URLs containing URI patterns to ignore.                   |

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Blacklists from URLs are automatically downloaded and updated hourly to ensure your protection remains current against the latest threats.

### Example Configurations

=== "Basic IP and User-Agent Protection"

    A simple configuration that blocks known Tor exit nodes and common bad user agents using community blacklists:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternatively, you can use manual URL configuration:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Advanced Protection with Custom Rules"

    A more comprehensive configuration with custom blacklist entries and exceptions:

    ```yaml
    USE_BLACKLIST: "yes"

    # Custom blacklist entries
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # AWS and Amazon ASNs
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Custom ignore rules
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # External blacklist sources
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Using Local Files"

    Configuration using local files for blacklists:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///path/to/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///path/to/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///path/to/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///path/to/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///path/to/uri-blacklist.txt"
    ```

### Working with local list files

The `*_URLS` settings provided by the whitelist, greylist, and blacklist plugins all use the same downloader. When you reference a `file:///` URL:

- The path is resolved inside the **scheduler** container (for Docker deployments this is typically `bunkerweb-scheduler`). Mount the files there and ensure they are readable by the scheduler user.
- Each file is plain text encoded in UTF-8 with one entry per line. Empty lines are ignored and comment lines must begin with `#` or `;`. `//` comments are not supported.
- Expected value per list type:
  - **IP lists** accept IPv4/IPv6 addresses or CIDR networks (for example `192.0.2.10` or `2001:db8::/48`).
  - **rDNS lists** expect a suffix without spaces (for example `.search.msn.com`). Values are normalised to lowercase automatically.
  - **ASN lists** may contain just the number (`32934`) or the number prefixed with `AS` (`AS15169`).
  - **User-Agent lists** are treated as PCRE patterns and the whole line is preserved (including spaces). Keep comments on their own line so they are not interpreted as part of the pattern.
  - **URI lists** must start with `/` and may use PCRE tokens such as `^` or `$`.

Example files that match the expected format:

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
