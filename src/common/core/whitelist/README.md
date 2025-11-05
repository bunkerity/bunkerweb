The Whitelist plugin lets you define a list of trusted IP addresses that bypass other security filters.
For blocking unwanted clients instead, refer to the [Blacklist plugin](#blacklist).

The Whitelist plugin provides a comprehensive approach to explicitly allow access to your website based on various client attributes. This feature provides a security mechanism: visitors matching specific criteria are granted immediate access, while all others must pass regular security checks.

**How it works:**

1. You define criteria for visitors who should be "whitelisted" (*IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns*).
2. When a visitor attempts to access your site, BunkerWeb checks whether they match any of these whitelist criteria.
3. If a visitor matches any whitelist rule (and doesn't match any ignore rule), they are granted access to your site and **bypass all other security checks**.
4. If a visitor doesn't match any whitelist criteria, they proceed through all normal security checks as usual.
5. Whitelists can be automatically updated from external sources on a regular schedule.

### How to Use

Follow these steps to configure and use the Whitelist feature:

1. **Enable the feature:** The Whitelist feature is disabled by default. Set the `USE_WHITELIST` setting to `yes` to enable it.
2. **Configure allow rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be whitelisted.
3. **Set up ignore rules:** Specify any exceptions that should bypass the whitelist checks.
4. **Add external sources:** Configure URLs for automatically downloading and updating whitelist data.
5. **Monitor access:** Check the [web UI](web-ui.md) to see which visitors are being allowed or denied.

!!! info "stream mode"
    When using stream mode, only IP, rDNS, and ASN checks are performed.

### Configuration Settings

**General**

| Setting         | Default | Context   | Multiple | Description                                                         |
| --------------- | ------- | --------- | -------- | ------------------------------------------------------------------- |
| `USE_WHITELIST` | `no`    | multisite | no       | **Enable Whitelist:** Set to `yes` to enable the whitelist feature. |

=== "IP Address"
    **What this does:** Whitelists visitors based on their IP address or network. These visitors will bypass all security checks.

    | Setting                    | Default | Context   | Multiple | Description                                                                                                |
    | -------------------------- | ------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |         | multisite | no       | **IP Whitelist:** List of IP addresses or networks (CIDR notation) to allow, separated by spaces.          |
    | `WHITELIST_IGNORE_IP`      |         | multisite | no       | **IP Ignore List:** List of IP addresses or networks that should bypass IP whitelist checks.               |
    | `WHITELIST_IP_URLS`        |         | multisite | no       | **IP Whitelist URLs:** List of URLs containing IP addresses or networks to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_IP_URLS` |         | multisite | no       | **IP Ignore List URLs:** List of URLs containing IP addresses or networks to ignore.                       |

=== "Reverse DNS"
    **What this does:** Whitelists visitors based on their domain name (in reverse). This is useful for allowing access to visitors from specific organizations or networks by their domain.

    | Setting                      | Default | Context   | Multiple | Description                                                                                              |
    | ---------------------------- | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_RDNS`             |         | multisite | no       | **rDNS Whitelist:** List of reverse DNS suffixes to allow, separated by spaces.                          |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`   | multisite | no       | **rDNS Global Only:** Only perform rDNS whitelist checks on global IP addresses when set to `yes`.       |
    | `WHITELIST_IGNORE_RDNS`      |         | multisite | no       | **rDNS Ignore List:** List of reverse DNS suffixes that should bypass rDNS whitelist checks.             |
    | `WHITELIST_RDNS_URLS`        |         | multisite | no       | **rDNS Whitelist URLs:** List of URLs containing reverse DNS suffixes to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_RDNS_URLS` |         | multisite | no       | **rDNS Ignore List URLs:** List of URLs containing reverse DNS suffixes to ignore.                       |

=== "ASN"
    **What this does:** Whitelists visitors from specific network providers using Autonomous System Numbers. ASNs identify which provider or organization an IP belongs to.

    | Setting                     | Default | Context   | Multiple | Description                                                                             |
    | --------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------- |
    | `WHITELIST_ASN`             |         | multisite | no       | **ASN Whitelist:** List of Autonomous System Numbers to allow, separated by spaces.     |
    | `WHITELIST_IGNORE_ASN`      |         | multisite | no       | **ASN Ignore List:** List of ASNs that should bypass ASN whitelist checks.              |
    | `WHITELIST_ASN_URLS`        |         | multisite | no       | **ASN Whitelist URLs:** List of URLs containing ASNs to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_ASN_URLS` |         | multisite | no       | **ASN Ignore List URLs:** List of URLs containing ASNs to ignore.                       |

=== "User Agent"
    **What this does:** Whitelists visitors based on what browser or tool they claim to be using. This is effective for allowing access to specific known tools or services.

    | Setting                            | Default | Context   | Multiple | Description                                                                                             |
    | ---------------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |         | multisite | no       | **User-Agent Whitelist:** List of User-Agent patterns (PCRE regex) to allow, separated by spaces.       |
    | `WHITELIST_IGNORE_USER_AGENT`      |         | multisite | no       | **User-Agent Ignore List:** List of User-Agent patterns that should bypass User-Agent whitelist checks. |
    | `WHITELIST_USER_AGENT_URLS`        |         | multisite | no       | **User-Agent Whitelist URLs:** List of URLs containing User-Agent patterns to whitelist.                |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |         | multisite | no       | **User-Agent Ignore List URLs:** List of URLs containing User-Agent patterns to ignore.                 |

=== "URI"
    **What this does:** Whitelists requests to specific URLs on your site. This is helpful for allowing access to specific endpoints regardless of other factors.

    | Setting                     | Default | Context   | Multiple | Description                                                                                     |
    | --------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------- |
    | `WHITELIST_URI`             |         | multisite | no       | **URI Whitelist:** List of URI patterns (PCRE regex) to allow, separated by spaces.             |
    | `WHITELIST_IGNORE_URI`      |         | multisite | no       | **URI Ignore List:** List of URI patterns that should bypass URI whitelist checks.              |
    | `WHITELIST_URI_URLS`        |         | multisite | no       | **URI Whitelist URLs:** List of URLs containing URI patterns to whitelist, separated by spaces. |
    | `WHITELIST_IGNORE_URI_URLS` |         | multisite | no       | **URI Ignore List URLs:** List of URLs containing URI patterns to ignore.                       |

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Whitelists from URLs are automatically downloaded and updated hourly to ensure your protection remains current with the latest trusted sources.

!!! warning "Security Bypass"
    Whitelisted visitors will completely **bypass all other security checks** in BunkerWeb, including WAF rules, rate limiting, bad bot detection, and any other security mechanisms. Only use the whitelist for trusted sources you're absolutely confident in.


### Example Configurations

=== "Basic Organization Access"

    A simple configuration that whitelists company office IPs:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "Advanced Configuration"

    A more comprehensive configuration with multiple whitelist criteria:

    ```yaml
    USE_WHITELIST: "yes"

    # Company and trusted partner assets
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # Company and partner ASNs
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # External trusted sources
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Using Local Files"

    Configuration using local files for whitelists:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///path/to/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///path/to/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///path/to/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///path/to/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///path/to/uri-whitelist.txt"
    ```

=== "API Access Pattern"

    A configuration focused on allowing access to only specific API endpoints:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # Internal network for all endpoints
    ```

=== "Well-Known Crawlers"

    A configuration that whitelists common search engine and social media crawlers:

    ```yaml
    USE_WHITELIST: "yes"

    # Verification with reverse DNS for added security
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # Only check global IPs
    ```

    This configuration allows legitimate crawlers to index your site without being subject to rate limiting or other security measures that might block them. The rDNS checks help verify that crawlers are actually coming from their claimed companies.

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
# /etc/bunkerweb/lists/ip-whitelist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-whitelist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
