The DNSBL (Domain Name System Blacklist) plugin provides protection against known malicious IP addresses by checking client IP addresses against external DNSBL servers. This feature helps guard your website against spam, botnets, and various types of cyber threats by leveraging community-maintained lists of problematic IP addresses.

**How it works:**

1. When a client connects to your website, BunkerWeb queries the DNSBL servers you have chosen using the DNS protocol.
2. The check is performed by sending a reverse DNS query to each DNSBL server with the client's IP address.
3. If any DNSBL server confirms that the client's IP address is listed as malicious, BunkerWeb will automatically ban the client, preventing potential threats from reaching your application.
4. Results are cached to improve performance for repeat visitors from the same IP address.
5. Lookups are performed efficiently using asynchronous queries to minimize impact on page load times.

### How to Use

Follow these steps to configure and use the DNSBL feature:

1. **Enable the feature:** The DNSBL feature is disabled by default. Set the `USE_DNSBL` setting to `yes` to enable it.
2. **Configure DNSBL servers:** Add the domain names of the DNSBL services you want to use to the `DNSBL_LIST` setting.
3. **Apply settings:** Once configured, BunkerWeb will automatically check incoming connections against the specified DNSBL servers.
4. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on requests blocked by DNSBL checks.

### Configuration Settings

| Setting      | Default                                             | Context   | Multiple | Description                                                                     |
| ------------ | --------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | no       | **Enable DNSBL:** Set to `yes` to enable DNSBL checks for incoming connections. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | no       | **DNSBL Servers:** List of DNSBL server domains to check, separated by spaces.  |

!!! tip "Choosing DNSBL Servers"
    Choose reputable DNSBL providers to minimize false positives. The default list includes well-established services that are suitable for most websites:

    - **bl.blocklist.de:** Lists IPs that have been detected attacking other servers.
    - **sbl.spamhaus.org:** Focuses on spam sources and other malicious activities.
    - **xbl.spamhaus.org:** Targets infected systems, such as compromised machines or open proxies.

!!! info "How DNSBL Works"
    DNSBL servers work by responding to specially formatted DNS queries. When BunkerWeb checks an IP address, it reverses the IP and appends the DNSBL domain name. If the resulting DNS query returns a "success" response, the IP is considered blacklisted.

!!! warning "Performance Considerations"
    While BunkerWeb optimizes DNSBL lookups for performance, adding a large number of DNSBL servers could potentially impact response times. Start with a few reputable DNSBL servers and monitor performance before adding more.

### Example Configurations

=== "Basic Configuration"

    A simple configuration using the default DNSBL servers:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Minimal Configuration"

    A minimal configuration focusing on the most reliable DNSBL services:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    This configuration uses only:

    - **zen.spamhaus.org**: Spamhaus' combined list is often considered sufficient as a standalone solution due to its wide coverage and reputation for accuracy. It combines the SBL, XBL, and PBL lists in a single query, making it efficient and comprehensive.
