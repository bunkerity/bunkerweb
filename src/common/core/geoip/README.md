The GeoIP plugin owns the MaxMind-format databases (`.mmdb`) that BunkerWeb uses to resolve the **country**, **ASN** and optionally the **city** of every client IP. Those lookups feed the [Country](#country) plugin, blacklist and greylist ASN rules, the reports shown in the [web UI](web-ui.md), and the `$bw_country`, `$bw_asn_number`, `$bw_asn_org` and `$bw_city` log variables.

Out of the box no configuration is needed: the country and ASN databases come from the free [DB-IP Lite](https://db-ip.com/db/lite.php) editions, refreshed daily. You only need this plugin's settings when you want a **different provider** — a MaxMind subscription, or a database you supply yourself.

**How it works:**

1. Three daily jobs refresh the country, ASN and city databases.
2. Each job picks its source with a simple priority: your own file wins, then MaxMind, then DB-IP.
3. The downloaded file is unpacked, opened and checked to be the kind of database that was asked for.
4. If it differs from the cached copy, it is stored and shipped to every BunkerWeb instance, which reloads to pick it up.
5. A lookup that fails never blocks a request: the country becomes `unknown` and traffic is served normally.

### Source priority

There is no "source" setting to pick. The priority is simply which settings you filled in:

| Priority | Used when                                             | Source                                                     |
| -------- | ----------------------------------------------------- | ---------------------------------------------------------- |
| 1        | `GEOIP_<KIND>_MMDB` is set                            | Your own file or URL                                        |
| 2        | `MAXMIND_LICENSE_KEY` is set                          | MaxMind (GeoLite2 free, or your GeoIP2 subscription)        |
| 3        | Nothing is set                                        | DB-IP Lite (the default)                                    |

Setting `MAXMIND_LICENSE_KEY` switches **all three** databases to MaxMind. Mixing providers per database is not supported; use `GEOIP_<KIND>_MMDB` if you need one specific database to come from somewhere else.

### Configuration Settings

| Setting                 | Default | Context | Multiple | Description                                                                                                                            |
| ----------------------- | ------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `MAXMIND_LICENSE_KEY`   |         | global  | no       | **MaxMind license key:** When set, the country, ASN and city databases are downloaded from MaxMind instead of DB-IP.                    |
| `MAXMIND_ACCOUNT_ID`    |         | global  | no       | **MaxMind account ID:** Optional but recommended: without it the deprecated key-only endpoint is used, which carries the key in the URL. |
| `GEOIP_CITY`            | `no`    | global  | no       | **City database:** Download the city database. Far bigger than the others (125 MB unpacked) and not bundled in the images.              |
| `GEOIP_COUNTRY_MMDB`    |         | global  | no       | **Custom country database:** Absolute path readable by the worker, or `http(s)` URL. Takes priority over MaxMind and DB-IP.             |
| `GEOIP_ASN_MMDB`        |         | global  | no       | **Custom ASN database:** Absolute path readable by the worker, or `http(s)` URL. Takes priority over MaxMind and DB-IP.                 |
| `GEOIP_CITY_MMDB`       |         | global  | no       | **Custom city database:** Absolute path readable by the worker, or `http(s)` URL. Takes priority over MaxMind and DB-IP.                |

!!! warning "The city database is big"
    DB-IP City Lite is a **59 MB download that unpacks to 125 MB**, against 7.8 MB for country and 9.2 MB for ASN. Unlike those two it is **not bundled in the images**: nothing is available until the first successful download, and a failed download simply leaves `$bw_city` empty.

    Because job caches are stored in the database and shipped to every instance, enabling it has real consequences:

    - On MariaDB and MySQL, raise `max_allowed_packet` above 125 MB or the job will fail (the default is 64 MB). The job says so explicitly in its logs when this happens.
    - The worker holds the database in memory while storing it, so raise `WORKER_MAX_MEMORY_KB` and the worker's container memory limit accordingly.
    - Every configuration change re-ships the cache to each instance, so plan for the bandwidth and the disk.

    MaxMind's `GeoLite2-City` is noticeably smaller if you have a license key.

!!! info "Getting a MaxMind license key"
    Create a free account on [maxmind.com](https://www.maxmind.com/en/geolite2/signup), then generate a license key **and** note your account ID. Both are shown in the account portal. GeoLite2 is updated twice a week, against once a month for DB-IP Lite.

    A newly created key can take a moment to become active; until it does, downloads fail with `401`.

!!! warning "Provide the account ID, not just the key"
    The account ID is optional only for backwards compatibility, and going without it is worse for two reasons:

    - MaxMind's key-only endpoint is **deprecated** and can be withdrawn.
    - It carries your license key **in the URL query string**, where it lands in the access logs of any forward proxy on the path. With an account ID the credentials travel in an `Authorization` header instead.

    BunkerWeb strips the key from its own logs either way, including from download error messages, but it cannot strip it from third-party logs.

!!! info "Using your own database"
    Any MaxMind-format `.mmdb` works, including the commercial GeoIP2 editions and internal databases, as long as it uses the standard field names (`country.iso_code`, `autonomous_system_number`, `autonomous_system_organization`, `city.names.en`).

    A local path must be readable by the **worker**, not by the BunkerWeb instances: the worker reads it once and distributes it. Plain `.mmdb`, `.mmdb.gz` and `.tar.gz` files are all accepted.

    The file is opened and its type checked **before** it is stored or sent anywhere, so pointing a setting at the wrong kind of database — or at something that is not a database at all — fails loudly instead of silently returning nothing.

    Prefer `https` for a URL. Geolocation drives allow and block decisions, so a database swapped in transit can make traffic appear to come from a country you allow.

### Example Configurations

=== "Default (DB-IP)"

    Nothing to configure. Country and ASN are refreshed daily from DB-IP Lite:

    ```yaml
    # no settings needed
    ```

=== "MaxMind GeoLite2"

    Switch every database to MaxMind:

    ```yaml
    MAXMIND_ACCOUNT_ID: "123456"
    MAXMIND_LICENSE_KEY: "your-license-key"
    ```

=== "Add City Data"

    Enable the city database on top of the default sources:

    ```yaml
    GEOIP_CITY: "yes"
    ```

=== "Own Database"

    Use a commercial database mounted into the worker, keeping DB-IP for the rest:

    ```yaml
    GEOIP_COUNTRY_MMDB: "/data/geoip/GeoIP2-Country.mmdb"
    ```

=== "Internal Mirror"

    Fetch every database from an internal HTTP mirror:

    ```yaml
    GEOIP_COUNTRY_MMDB: "https://mirror.example.com/geoip/country.mmdb"
    GEOIP_ASN_MMDB: "https://mirror.example.com/geoip/asn.mmdb"
    GEOIP_CITY: "yes"
    GEOIP_CITY_MMDB: "https://mirror.example.com/geoip/city.mmdb.gz"
    ```

### Licensing

- **DB-IP Lite** databases are published under the [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) license and require attribution to DB-IP.com.
- **GeoLite2** databases are covered by MaxMind's end user license agreement, which you accept when you create your key. BunkerWeb never redistributes them: they are downloaded with your own credentials, which is why no MaxMind database ships inside the images.
