The Greylist plugin provides a flexible security approach that allows visitors access while still maintaining essential security features.

Unlike traditional [blacklist](#blacklist)/[whitelist](#whitelist) approaches—that completely block or allow access—greylisting creates a middle ground by granting access to certain visitors while still subjecting them to security checks.

**How it works:**

1. You define criteria for visitors to be greylisted (*IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns*).
2. When a visitor matches any of these criteria, they are granted access to your site while the other security features remain active.
3. If a visitor does not match any greylist criteria, their access is denied.
4. Greylist data can be automatically updated from external sources on a regular schedule.

### How to Use

Follow these steps to configure and use the Greylist feature:

1. **Enable the feature:** The Greylist feature is disabled by default. Set the `USE_GREYLIST` setting to `yes` to enable it.
2. **Configure greylist rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be greylisted.
3. **Add external sources:** Optionally, configure URLs for automatically downloading and updating greylist data.
4. **Monitor access:** Check the [web UI](web-ui.md) to see which visitors are being allowed or denied.

!!! tip "Access Control Behavior"
    When the greylist feature is enabled with the `USE_GREYLIST` setting set to `yes`:

    1. **Greylisted visitors:** Are allowed access but are still subject to all security checks.
    2. **Non-greylisted visitors:** Are completely denied access.

!!! info "stream mode"
    When using stream mode, only IP, rDNS, and ASN checks are performed.

### Configuration Settings

**General**

| Setting        | Default | Context   | Multiple | Description                                              |
| -------------- | ------- | --------- | -------- | -------------------------------------------------------- |
| `USE_GREYLIST` | `no`    | multisite | no       | **Enable Greylist:** Set to `yes` to enable greylisting. |

=== "IP Address"
    **What this does:** Greylist visitors based on their IP address or network. These visitors gain access but remain subject to security checks.

    | Setting            | Default | Context   | Multiple | Description                                                                                              |
    | ------------------ | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |         | multisite | no       | **IP Greylist:** List of IP addresses or networks (in CIDR notation) to greylist, separated by spaces.   |
    | `GREYLIST_IP_URLS` |         | multisite | no       | **IP Greylist URLs:** List of URLs containing IP addresses or networks to greylist, separated by spaces. |

=== "Reverse DNS"
    **What this does:** Greylist visitors based on their domain name (in reverse). Useful for allowing conditional access to visitors from specific organizations or networks.

    | Setting                | Default | Context   | Multiple | Description                                                                                            |
    | ---------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `GREYLIST_RDNS`        |         | multisite | no       | **rDNS Greylist:** List of reverse DNS suffixes to greylist, separated by spaces.                      |
    | `GREYLIST_RDNS_GLOBAL` | `yes`   | multisite | no       | **rDNS Global Only:** Only perform rDNS greylist checks on global IP addresses when set to `yes`.      |
    | `GREYLIST_RDNS_URLS`   |         | multisite | no       | **rDNS Greylist URLs:** List of URLs containing reverse DNS suffixes to greylist, separated by spaces. |

    !!! info "Forward-confirmed reverse DNS (FCrDNS)"
        `GREYLIST_RDNS` suffixes are forward-confirmed: the matching PTR hostname is resolved back to an IP and the greylist grant only applies when it matches the client IP. A PTR that cannot be forward-confirmed is treated as a possible spoof and access is not granted. This prevents an attacker who controls their own PTR record from setting it to a greylisted suffix to gain access.

=== "ASN"
    **What this does:** Greylist visitors from specific network providers using Autonomous System Numbers. ASNs identify which provider or organization an IP belongs to.

    | Setting             | Default | Context   | Multiple | Description                                                                           |
    | ------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |         | multisite | no       | **ASN Greylist:** List of Autonomous System Numbers to greylist, separated by spaces. |
    | `GREYLIST_ASN_URLS` |         | multisite | no       | **ASN Greylist URLs:** List of URLs containing ASNs to greylist, separated by spaces. |

=== "User Agent"
    **What this does:** Greylist visitors based on the browser or tool they claim to be using. This allows controlled access for specific tools while maintaining security checks.

    | Setting                    | Default | Context   | Multiple | Description                                                                                         |
    | -------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |         | multisite | no       | **User-Agent Greylist:** List of User-Agent patterns (PCRE regex) to greylist, separated by spaces. |
    | `GREYLIST_USER_AGENT_URLS` |         | multisite | no       | **User-Agent Greylist URLs:** List of URLs containing User-Agent patterns to greylist.              |

=== "URI"
    **What this does:** Greylist requests to specific URLs on your site. This allows conditional access to certain endpoints while maintaining security checks.

    | Setting             | Default | Context   | Multiple | Description                                                                                   |
    | ------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |         | multisite | no       | **URI Greylist:** List of URI patterns (PCRE regex) to greylist, separated by spaces.         |
    | `GREYLIST_URI_URLS` |         | multisite | no       | **URI Greylist URLs:** List of URLs containing URI patterns to greylist, separated by spaces. |

=== "Composite rules (AND)"
    **What this does:** require several criteria *at once*. Each flat list above is an OR — any single one matching is enough to greylist a visitor. A rule is an AND: it greylists only a visitor that matches every one of its terms.

    | Setting | Default | Context | Multiple | Description |
    | ------- | ------- | ------- | -------- | ----------- |
    | `GREYLIST_RULE` |  | multisite | yes | **Greylist rule:** Terms joined with ` AND `; every one must match. |

    A rule is a list of terms separated by the literal ` AND ` — uppercase, one space on each
    side. Every term must match for the rule to match:

    ```
    <rule> := <term> ( " AND " <term> )*
    <term> := [ "NOT " ] <kind> ":" <value>
    <kind> := ip | country | asn | rdns | ua | uri
    ```

    `user_agent` is accepted as an alias of `ua`. A `<value>` may be a resource-group token such
    as `@office`, resolved against that term's kind. Rules are declared with the usual
    numeric-suffix form: `GREYLIST_RULE_1`, `GREYLIST_RULE_2`, and so on.

    ```yaml
    USE_GREYLIST: "yes"
    # a partner's crawler, but only when it comes from the partner's own network
    GREYLIST_RULE_1: "ip:203.0.113.0/24 AND ua:^PartnerCrawler"
    # everything from one ASN, except its scanners
    GREYLIST_RULE_2: "asn:12345 AND NOT ua:(?:nmap|masscan)"
    # a country plus a path, using a resource group for the country list
    GREYLIST_RULE_3: "country:@internal-markets AND uri:^/api/v1/"
    ```

    !!! warning "OR between rules, AND inside one"
        This is the distinction readers get wrong. **Rules are OR'd** — with each other and with
        the flat lists above: a visitor matching `GREYLIST_IP`, or any single rule, is greylisted.
        **Terms inside one rule are AND'd**: the rule above greylists nobody unless every one of its
        terms matches. Two criteria written as two rules is an OR; the same two written as two
        terms of one rule is an AND.

    !!! info "Limits"
        * A term whose subject the request cannot supply is **unknown**, and a rule holding an
          unknown term never matches — `NOT` does not rescue it. `ua:` and `uri:` are always
          unknown in stream mode, and a `ua:` term is unknown on a request that sends no
          `User-Agent` header. A failed lookup (no GeoIP database, a resolver error) is unknown
          too; a private client IP is **not** — it definitely has no ASN and its country is
          `local`, so `NOT asn:…` legitimately matches it.
        * A rule containing a `ua:` or `uri:` term therefore cannot match in a stream service.
          It is not refused — the same service configuration may serve HTTP too — but a warning
          naming the rule is logged when the configuration loads, so it is never *silently* dead.
        * A rule made only of `NOT` terms is valid but matches almost every request. Same
          warning channel.
        * There is no escaping syntax. Because ` AND ` is the separator, a `ua:` or `uri:` regex
          may not contain " and " in any casing; such a rule is refused when it is saved.
        * An `rdns:` term is forward-confirmed, exactly like the flat `GREYLIST_RDNS` pass: the
          matching PTR hostname is resolved back and the term is only true when it resolves to
          the client IP.

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Greylists from URLs are automatically downloaded and updated hourly to ensure that your protection remains current with the latest trusted sources.


### Example Configurations

=== "Basic Configuration"

    A simple configuration that applies greylisting to a company's internal network and crawler:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "Advanced Configuration"

    A more comprehensive configuration with multiple greylist criteria:

    ```yaml
    USE_GREYLIST: "yes"

    # Company assets and approved crawlers
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # Company and partner ASNs
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # External trusted sources
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Using Local Files"

    Configuration using local files for greylists:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///path/to/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///path/to/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///path/to/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///path/to/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///path/to/uri-greylist.txt"
    ```

=== "Selective API Access"

    A configuration allowing access to specific API endpoints:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # External partner network
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
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
