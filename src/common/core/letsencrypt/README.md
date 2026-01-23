The Let's Encrypt plugin simplifies SSL/TLS certificate management by automating the creation, renewal, and configuration of free certificates from Let's Encrypt. This feature enables secure HTTPS connections for your websites without the complexity of manual certificate management, reducing both cost and administrative overhead.

**How it works:**

1. When enabled, BunkerWeb automatically detects the domains configured for your website.
2. BunkerWeb requests free SSL/TLS certificates from Let's Encrypt's certificate authority.
3. Domain ownership is verified through either HTTP challenges (proving you control the website) or DNS challenges (proving you control your domain's DNS).
4. Certificates are automatically installed and configured for your domains.
5. BunkerWeb handles certificate renewals in the background before expiration, ensuring continuous HTTPS availability.
6. The entire process is fully automated, requiring minimal intervention after the initial setup.

!!! info "Prerequisites"
    To use this feature, ensure that proper DNS **A records** are configured for each domain, pointing to the public IP(s) where BunkerWeb is accessible. Without correct DNS configuration, the domain verification process will fail.

### How to Use

Follow these steps to configure and use the Let's Encrypt feature:

1. **Enable the feature:** Set the `AUTO_LETS_ENCRYPT` setting to `yes` to enable automatic certificate issuance and renewal.
2. **Provide contact email (recommended):** Enter your email address using the `EMAIL_LETS_ENCRYPT` setting so Let's Encrypt can warn you before certificates expire. If you leave it blank, BunkerWeb registers without an address (Certbot's `--register-unsafely-without-email`), but you won't receive renewal reminders or recovery emails.
3. **Choose challenge type:** Select either `http` or `dns` verification with the `LETS_ENCRYPT_CHALLENGE` setting.
4. **Configure DNS provider:** If using DNS challenges, specify your DNS provider and credentials.
5. **Select certificate profile:** Choose your preferred certificate profile using the `LETS_ENCRYPT_PROFILE` setting (classic, tlsserver, or shortlived).
6. **Let BunkerWeb handle the rest:** Once configured, certificates are automatically issued, installed, and renewed as needed.

!!! tip "Certificate Profiles"
    Let's Encrypt provides different certificate profiles for different use cases:

    - **classic**: General-purpose certificates with 90-day validity (default)
    - **tlsserver**: Optimized for TLS server authentication with 90-day validity and smaller payload
    - **shortlived**: Enhanced security with 7-day validity for automated environments
    - **custom**: If your ACME server supports a different profile, set it using `LETS_ENCRYPT_CUSTOM_PROFILE`.

!!! info "Profile Availability"
    Note that the `tlsserver` and `shortlived` profiles may not be available in all environments or with all ACME clients at this time. The `classic` profile has the widest compatibility and is recommended for most users. If a selected profile is not available, the system will automatically fall back to the `classic` profile.

### Configuration Settings

| Setting                                     | Default   | Context   | Multiple | Description                                                                                                                                                                                                                                                                    |
| ------------------------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AUTO_LETS_ENCRYPT`                         | `no`      | multisite | no       | **Enable Let's Encrypt:** Set to `yes` to enable automatic certificate issuance and renewal.                                                                                                                                                                                   |
| `LETS_ENCRYPT_PASSTHROUGH`                  | `no`      | multisite | no       | **Pass Through Let's Encrypt:** Set to `yes` to pass through Let's Encrypt requests to the web server. This is useful when BunkerWeb is behind another reverse proxy handling SSL.                                                                                             |
| `EMAIL_LETS_ENCRYPT`                        | `-`       | multisite | no       | **Contact Email:** Email address used for Let's Encrypt expiry reminders. Leave blank only if you accept that no alerts or recovery emails will be sent (Certbot registers with `--register-unsafely-without-email`).                                                          |
| `LETS_ENCRYPT_CHALLENGE`                    | `http`    | multisite | no       | **Challenge Type:** Method used to verify domain ownership. Options: `http` or `dns`.                                                                                                                                                                                          |
| `LETS_ENCRYPT_DNS_PROVIDER`                 |           | multisite | no       | **DNS Provider:** When using DNS challenges, the DNS provider to use (e.g., cloudflare, route53, digitalocean).                                                                                                                                                                |
| `LETS_ENCRYPT_DNS_PROPAGATION`              | `default` | multisite | no       | **DNS Propagation:** The time to wait for DNS propagation in seconds. If no value is provided, the provider's default propagation time is used.                                                                                                                                |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM`          |           | multisite | yes      | **Credential Item:** Configuration items for DNS provider authentication (e.g., `cloudflare_api_token 123456`). Values can be raw text, base64 encoded, or a JSON object.                                                                                                      |
| `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` | `yes`     | multisite | no       | **Decode Base64 DNS credentials:** Automatically decode base64-encoded DNS provider credentials when set to `yes`. Values matching base64 format are decoded before use (except for the `rfc2136` provider). Set to `no` if your credentials are intentionally base64 strings. |
| `USE_LETS_ENCRYPT_WILDCARD`                 | `no`      | multisite | no       | **Wildcard Certificates:** When set to `yes`, creates wildcard certificates for all domains. Only available with DNS challenges.                                                                                                                                               |
| `USE_LETS_ENCRYPT_STAGING`                  | `no`      | multisite | no       | **Use Staging:** When set to `yes`, uses Let's Encrypt's staging environment for testing. Staging has higher rate limits but produces certificates that are not trusted by browsers.                                                                                           |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`              | `no`      | global    | no       | **Clear Old Certificates:** When set to `yes`, removes old certificates that are no longer needed during renewal.                                                                                                                                                              |
| `LETS_ENCRYPT_CONCURRENT_REQUESTS`          | `no`      | global    | no       | **Concurrent Requests:** When set to `yes`, certbot-new issues certificate requests concurrently. Use with caution to avoid rate limits.                                                                                                                                       |
| `LETS_ENCRYPT_PROFILE`                      | `classic` | multisite | no       | **Certificate Profile:** Select the certificate profile to use. Options: `classic` (general-purpose), `tlsserver` (optimized for TLS servers), or `shortlived` (7-day certificates).                                                                                           |
| `LETS_ENCRYPT_CUSTOM_PROFILE`               |           | multisite | no       | **Custom Certificate Profile:** Enter a custom certificate profile if your ACME server supports non-standard profiles. This overrides `LETS_ENCRYPT_PROFILE` if set.                                                                                                           |
| `LETS_ENCRYPT_MAX_RETRIES`                  | `3`       | multisite | no       | **Maximum Retries:** Number of times to retry certificate generation on failure. Set to `0` to disable retries. Useful for handling temporary network issues or API rate limits.                                                                                               |

!!! info "Information and behavior"
    - The `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting is a multiple setting and can be used to set multiple items for the DNS provider. The items will be saved as a cache file, and Certbot will read the credentials from it.
    - If no `LETS_ENCRYPT_DNS_PROPAGATION` setting is provided, the provider's default propagation time is used.
    - Full Let's Encrypt automation using the `http` challenge works in stream mode as long as you open the `80/tcp` port from the outside. Use the `LISTEN_STREAM_PORT_SSL` setting to choose your listening SSL/TLS port.
    - If `LETS_ENCRYPT_PASSTHROUGH` is set to `yes`, BunkerWeb will not handle the ACME challenge requests itself but will pass them to the backend web server. This is useful in scenarios where BunkerWeb is acting as a reverse proxy in front of another server that is configured to handle Let's Encrypt challenges

!!! tip "HTTP vs. DNS Challenges"
    **HTTP Challenges** are easier to set up and work well for most websites:

    - Requires your website to be publicly accessible on port 80
    - Automatically configured by BunkerWeb
    - Cannot be used for wildcard certificates

    **DNS Challenges** offer more flexibility and are required for wildcard certificates:

    - Works even when your website is not publicly accessible
    - Requires DNS provider API credentials
    - Required for wildcard certificates (e.g., *.example.com)
    - Useful when port 80 is blocked or unavailable

!!! warning "Wildcard certificates"
    Wildcard certificates are only available with DNS challenges. If you want to use them, you must set the `USE_LETS_ENCRYPT_WILDCARD` setting to `yes` and properly configure your DNS provider credentials.

!!! warning "Rate Limits"
    Let's Encrypt imposes rate limits on certificate issuance. When testing configurations, use the staging environment by setting `USE_LETS_ENCRYPT_STAGING` to `yes` to avoid hitting production rate limits. Staging certificates are not trusted by browsers but are useful for validating your setup.


### Supported DNS Providers

The Let's Encrypt plugin supports a wide range of DNS providers for DNS challenges. Each provider requires specific credentials that must be provided using the `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting.

| Provider          | Description      | Mandatory Settings                                                                                           | Optional Settings                                                                                                                                                                                                                                                        | Documentation                                                                                         |
| ----------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `bunny`           | bunny.net        | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/mwt/certbot-dns-bunny/blob/main/README.rst)                        |
| `cloudflare`      | Cloudflare       | either `api_token`<br>or `email` and `api_key`                                                               |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)                             |
| `desec`           | deSEC            | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)                    |
| `digitalocean`    | DigitalOcean     | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)                           |
| `domainoffensive` | Domain-Offensive | `api_token`                                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/domainoffensive/certbot-dns-domainoffensive/blob/master/README.md) |
| `domeneshop`      | Domeneshop       | `token`<br>`secret`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/domeneshop/certbot-dns-domeneshop/blob/master/README.rst)          |
| `dnsimple`        | DNSimple         | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)                               |
| `dnsmadeeasy`     | DNS Made Easy    | `api_key`<br>`secret_key`                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)                            |
| `duckdns`         | DuckDNS          | `duckdns_token`                                                                                              |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infinityofspace/certbot_dns_duckdns/blob/main/Readme.md)           |
| `dynu`            | Dynu             | `auth_token`                                                                                                 |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/bikram990/certbot-dns-dynu/blob/main/README.md)                    |
| `gehirn`          | Gehirn DNS       | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                                 |
| `godaddy`         | GoDaddy          | `key`<br>`secret`                                                                                            | `ttl` (default: `600`)                                                                                                                                                                                                                                                   | [Documentation](https://github.com/miigotu/certbot-dns-godaddy/blob/main/README.md)                   |
| `google`          | Google Cloud     | `project_id`<br>`private_key_id`<br>`private_key`<br>`client_email`<br>`client_id`<br>`client_x509_cert_url` | `type` (default: `service_account`)<br>`auth_uri` (default: `https://accounts.google.com/o/oauth2/auth`)<br>`token_uri` (default: `https://accounts.google.com/o/oauth2/token`)<br>`auth_provider_x509_cert_url` (default: `https://www.googleapis.com/oauth2/v1/certs`) | [Documentation](https://certbot-dns-google.readthedocs.io/en/stable/)                                 |
| `infomaniak`      | Infomaniak       | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infomaniak/certbot-dns-infomaniak/blob/main/README.rst)            |
| `ionos`           | IONOS            | `prefix`<br>`secret`                                                                                         | `endpoint` (default: `https://api.hosting.ionos.com`)                                                                                                                                                                                                                    | [Documentation](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md)                 |
| `linode`          | Linode           | `key`                                                                                                        |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                                 |
| `luadns`          | LuaDNS           | `email`<br>`token`                                                                                           |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                                 |
| `njalla`          | Njalla           | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/chaptergy/certbot-dns-njalla/blob/main/README.md)                  |
| `nsone`           | NS1              | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                                  |
| `ovh`             | OVH              | `application_key`<br>`application_secret`<br>`consumer_key`                                                  | `endpoint` (default: `ovh-eu`)                                                                                                                                                                                                                                           | [Documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                                    |
| `pdns`            | PowerDNS         | `endpoint`<br>`api_key`<br>`server_id` (default: `localhost`)<br>`disable_notify` (default: `false`)         |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/kaechele/certbot-dns-pdns/blob/main/README.md)                     |
| `rfc2136`         | RFC 2136         | `server`<br>`name`<br>`secret`                                                                               | `port` (default: `53`)<br>`algorithm` (default: `HMAC-SHA512`)<br>`sign_query` (default: `false`)                                                                                                                                                                        | [Documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                                |
| `route53`         | Amazon Route 53  | `access_key_id`<br>`secret_access_key`                                                                       |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                                |
| `sakuracloud`     | Sakura Cloud     | `api_token`<br>`api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)                            |
| `scaleway`        | Scaleway         | `application_token`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst)                 |
| `transip`         | TransIP          | `key_file`<br>`username`                                                                                     |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-transip.readthedocs.io/en/stable/)                                |

### Example Configurations

=== "Basic HTTP Challenge"

    Simple configuration using HTTP challenges for a single domain:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ```

=== "Cloudflare DNS with Wildcard"

    Configuration for wildcard certificates using Cloudflare DNS:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "api_token YOUR_API_TOKEN"
    USE_LETS_ENCRYPT_WILDCARD: "yes"
    ```

=== "AWS Route53 Configuration"

    Configuration using Amazon Route53 for DNS challenges:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "route53"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "aws_access_key_id YOUR_ACCESS_KEY"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "aws_secret_access_key YOUR_SECRET_KEY"
    ```

=== "Testing with Staging Environment and Retries"

    Configuration for testing setup with the staging environment and enhanced retry settings:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    USE_LETS_ENCRYPT_STAGING: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "5"
    ```

=== "DigitalOcean with Custom Propagation Time"

    Configuration using DigitalOcean DNS with a longer propagation wait time:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "digitalocean"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "token YOUR_API_TOKEN"
    LETS_ENCRYPT_DNS_PROPAGATION: "120"
    ```

=== "Google Cloud DNS"

    Configuration using Google Cloud DNS with service account credentials:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "google"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "project_id your-project-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2: "private_key_id your-private-key-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3: "private_key your-private-key"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4: "client_email your-service-account-email"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5: "client_id your-client-id"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_6: "client_x509_cert_url your-cert-url"
    ```
