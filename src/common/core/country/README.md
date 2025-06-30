# Country Plugin

The Country plugin enables geo-blocking functionality for your website, allowing you to restrict access based on the geographic location of your visitors. This feature helps you comply with regional regulations, prevent fraudulent activities often associated with high-risk regions, and implement content restrictions based on geographic boundaries.

**How it works:**

1. When a visitor accesses your website, BunkerWeb determines their country based on their IP address.
2. Your configuration specifies either a whitelist (allowed countries) or a blacklist (blocked countries).
3. If you've set up a whitelist, only visitors from countries on that list will be granted access.
4. If you've set up a blacklist, visitors from countries on that list will be denied access.
5. The result is cached to improve performance for repeat visitors from the same IP address.

### How to Use

Follow these steps to configure and use the Country feature:

1. **Define your strategy:** Decide whether you want to use a whitelist approach (allow only specific countries) or a blacklist approach (block specific countries).
2. **Configure country codes:** Add the ISO 3166-1 alpha-2 country codes (two-letter codes like US, GB, FR) to either the `WHITELIST_COUNTRY` or `BLACKLIST_COUNTRY` setting.
3. **Apply settings:** Once configured, the country-based restrictions will apply to all visitors to your site.
4. **Monitor effectiveness:** Check the [web UI](web-ui.md) to see statistics on blocked requests by country.

### Configuration Settings

| Setting             | Default | Context   | Multiple | Description                                                                                                                     |
| ------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |         | multisite | no       | **Country Whitelist:** List of country codes (ISO 3166-1 alpha-2 format) separated by spaces. Only these countries are allowed. |
| `BLACKLIST_COUNTRY` |         | multisite | no       | **Country Blacklist:** List of country codes (ISO 3166-1 alpha-2 format) separated by spaces. These countries are blocked.      |

!!! tip "Whitelist vs. Blacklist"
    Choose the approach that best fits your needs:

    - Use the whitelist when you want to restrict access to a small number of countries.
    - Use the blacklist when you want to block access from specific problematic regions while allowing everyone else.

!!! warning "Precedence Rule"
    If both whitelist and blacklist are configured, the whitelist takes precedence. This means the system first checks if a country is whitelisted; if not, access is denied regardless of the blacklist configuration.

!!! info "Country Detection"
    BunkerWeb uses the [lite db-ip mmdb database](https://db-ip.com/db/download/ip-to-country-lite) to determine the country of origin based on IP addresses.

### Example Configurations

=== "Whitelist Only"

    Allow access only from the United States, Canada, and the United Kingdom:

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Blacklist Only"

    Block access from specific countries while allowing all others:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "EU Access Only"

    Allow access only from European Union member states:

    ```yaml
    WHITELIST_COUNTRY: "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE"
    ```

=== "High-Risk Countries Blocked"

    Block access from countries often associated with certain cyber threats:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```