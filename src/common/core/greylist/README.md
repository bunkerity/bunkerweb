The Greylist plugin provides a flexible security approach that allows access to visitors while still maintaining security features.

Unlike traditional blacklist/whitelist approaches that completely block or allow access, greylisting creates a middle ground where certain visitors get access while still being subject to security checks.

**Here's how the Greylist feature works:**

1. You define criteria for visitors who should be "greylisted" (*IP addresses, networks, rDNS, ASN, User-Agent, or URI patterns*).
2. When a visitor matches any of these criteria, they are allowed access to your site while the other security features remain active.
3. If a visitor doesn't match any greylist criteria, their access is denied.

### How to Use

Follow these steps to configure and use the Greylist feature:

1. **Enable the feature:** The Greylist feature is disabled by default. Set the `USE_GREYLIST` setting to `yes` to enable it.
2. **Configure greylist rules:** Define which IPs, networks, rDNS patterns, ASNs, User-Agents, or URIs should be greylisted.
3. **Add external sources:** Optionally configure URLs for automatically downloading and updating greylist data.
4. **Let BunkerWeb handle the rest:** Once configured, visitors matching your greylist criteria will be given improved access while maintaining essential security protections.

### Configuration Settings

**General**

| Setting        | Default | Context   | Multiple | Description                                                          |
| -------------- | ------- | --------- | -------- | -------------------------------------------------------------------- |
| `USE_GREYLIST` | `no`    | multisite | no       | **Enable Greylist:** Set to `yes` to enable the greylisting feature. |

=== "IP Address"
    **What this does:** Greylists visitors based on their IP address or network.

    | Setting            | Default | Context   | Multiple | Description                                                                                              |
    | ------------------ | ------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |         | multisite | no       | **IP Greylist:** List of IP addresses or networks (CIDR notation) to greylist, separated by spaces.      |
    | `GREYLIST_IP_URLS` |         | multisite | no       | **IP Greylist URLs:** List of URLs containing IP addresses or networks to greylist, separated by spaces. |

=== "Reverse DNS"
    **What this does:** Greylists visitors based on their domain name (in reverse).

    | Setting                | Default | Context   | Multiple | Description                                                                                            |
    | ---------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------ |
    | `GREYLIST_RDNS`        |         | multisite | no       | **rDNS Greylist:** List of reverse DNS suffixes to greylist, separated by spaces.                      |
    | `GREYLIST_RDNS_GLOBAL` | `yes`   | multisite | no       | **rDNS Global Only:** Only perform rDNS greylist checks on global IP addresses when set to `yes`.      |
    | `GREYLIST_RDNS_URLS`   |         | multisite | no       | **rDNS Greylist URLs:** List of URLs containing reverse DNS suffixes to greylist, separated by spaces. |

=== "ASN"
    **What this does:** Greylists visitors from specific network providers using Autonomous System Numbers.

    | Setting             | Default | Context   | Multiple | Description                                                                           |
    | ------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |         | multisite | no       | **ASN Greylist:** List of Autonomous System Numbers to greylist, separated by spaces. |
    | `GREYLIST_ASN_URLS` |         | multisite | no       | **ASN Greylist URLs:** List of URLs containing ASNs to greylist, separated by spaces. |

=== "User Agent"
    **What this does:** Greylists visitors based on what browser or tool they claim to be using.

    | Setting                    | Default | Context   | Multiple | Description                                                                                         |
    | -------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |         | multisite | no       | **User-Agent Greylist:** List of User-Agent patterns (PCRE regex) to greylist, separated by spaces. |
    | `GREYLIST_USER_AGENT_URLS` |         | multisite | no       | **User-Agent Greylist URLs:** List of URLs containing User-Agent patterns to greylist.              |

=== "URI"
    **What this does:** Greylists requests to specific URLs on your site.

    | Setting             | Default | Context   | Multiple | Description                                                                                   |
    | ------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |         | multisite | no       | **URI Greylist:** List of URI patterns (PCRE regex) to greylist, separated by spaces.         |
    | `GREYLIST_URI_URLS` |         | multisite | no       | **URI Greylist URLs:** List of URLs containing URI patterns to greylist, separated by spaces. |

!!! info "URL Format Support"
    All `*_URLS` settings support HTTP/HTTPS URLs as well as local file paths using the `file:///` prefix. Basic authentication is supported using the `http://user:pass@url` format.

!!! tip "Regular Updates"
    Greylists from URLs are automatically downloaded and updated hourly to ensure your protection remains current with the latest trusted sources.

### Example Configurations

=== "Basic Configuration"

    A simple configuration that greylists a company's internal network and crawler:

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
