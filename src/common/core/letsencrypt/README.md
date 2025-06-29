# Let's Encrypt Plugin

The Let's Encrypt plugin simplifies SSL/TLS certificate management by automating the creation, renewal, and configuration of free certificates from multiple certificate authorities. This feature enables secure HTTPS connections for your websites without the complexity of manual certificate management, reducing both cost and administrative overhead.

**How it works:**

1. When enabled, BunkerWeb automatically detects the domains configured for your website.
2. BunkerWeb requests free SSL/TLS certificates from supported certificate authorities (Let's Encrypt, ZeroSSL).
3. Domain ownership is verified through either HTTP challenges (proving you control the website) or DNS challenges (proving you control your domain's DNS).
4. Certificates are automatically installed and configured for your domains.
5. BunkerWeb handles certificate renewals in the background before expiration, ensuring continuous HTTPS availability.
6. The entire process is fully automated with intelligent retry mechanisms, requiring minimal intervention after the initial setup.

!!! info "Prerequisites"
    To use this feature, ensure that proper DNS **A records** are configured for each domain, pointing to the public IP(s) where BunkerWeb is accessible. Without correct DNS configuration, the domain verification process will fail.

## How to Use

Follow these steps to configure and use the Let's Encrypt feature:

1. **Enable the feature:** Set the `AUTO_LETS_ENCRYPT` setting to `yes` to enable automatic certificate issuance and renewal.
2. **Choose certificate authority:** Select your preferred CA using `ACME_SSL_CA_PROVIDER` (letsencrypt or zerossl).
3. **Provide contact email:** Enter your email address using the `EMAIL_LETS_ENCRYPT` setting to receive important notifications about your certificates.
4. **Choose challenge type:** Select either `http` or `dns` verification with the `LETS_ENCRYPT_CHALLENGE` setting.
5. **Configure DNS provider:** If using DNS challenges, specify your DNS provider and credentials.
6. **Select certificate profile:** Choose your preferred certificate profile using the `LETS_ENCRYPT_PROFILE` setting (classic, tlsserver, or shortlived).
7. **Configure API keys:** For ZeroSSL, provide your API key using `ACME_ZEROSSL_API_KEY`.
8. **Let BunkerWeb handle the rest:** Once configured, certificates are automatically issued, installed, and renewed as needed with intelligent retry mechanisms.

!!! tip "Certificate Authorities"
    The plugin supports multiple certificate authorities:
    - **Let's Encrypt**: Free, widely trusted, 90-day certificates
    - **ZeroSSL**: Free alternative with competitive rate limits, supports EAB (External Account Binding)

    ZeroSSL requires an API key for automated EAB credential generation. Without an API key, you can manually provide EAB credentials using `ACME_ZEROSSL_EAB_KID` and `ACME_ZEROSSL_EAB_HMAC_KEY`.

!!! tip "Certificate Profiles"
    Let's Encrypt and ZeroSSL provide different certificate profiles for different use cases:
    - **classic**: General-purpose certificates with 90-day validity (default, widest compatibility)
    - **tlsserver**: Optimized for TLS server authentication with 90-day validity and smaller payload
    - **shortlived**: Enhanced security with 7-day validity for automated environments
    - **custom**: If your ACME server supports a different profile, set it using `LETS_ENCRYPT_CUSTOM_PROFILE`.

!!! info "Profile Availability"
    Note that the `tlsserver` and `shortlived` profiles may not be available in all environments or with all ACME clients at this time. The `classic` profile has the widest compatibility and is recommended for most users. If a selected profile is not available, the system will automatically fall back to the `classic` profile.

## Advanced Security Features

The plugin includes several advanced security and validation features:

- **Public Suffix List (PSL) Validation**: Automatically prevents certificate requests for domains on the PSL (controlled by `LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES`)
- **CAA Record Validation**: Checks DNS CAA records to ensure the selected certificate authority is authorized for your domains
- **IP Address Validation**: For HTTP challenges, validates that domain DNS records point to your server's public IP addresses
- **Retry Mechanisms**: Intelligent retry with exponential backoff for failed certificate generation attempts
- **Certificate Key Types**: Supports both RSA and ECDSA keys with provider-specific optimizations

## Configuration Settings

| Setting                            | Default                  | Context   | Multiple | Description                                                                                                                                                                          |
| ---------------------------------- | ------------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AUTO_LETS_ENCRYPT`                | `no`                     | multisite | no       | **Enable Let's Encrypt:** Set to `yes` to enable automatic certificate issuance and renewal.                                                                                         |
| `ACME_SSL_CA_PROVIDER`             | `letsencrypt`            | multisite | no       | **Certificate Authority:** Select certificate authority (`letsencrypt` or `zerossl`).                                                                                                |
| `ACME_ZEROSSL_API_KEY`             |                          | multisite | no       | **ZeroSSL API Key:** Required for automated ZeroSSL certificate generation and EAB credential setup.                                                                                |
| `ACME_ZEROSSL_EAB_KID`             |                          | multisite | no       | **ZeroSSL EAB Key ID:** Manual EAB key identifier (alternative to API key). Used with `ACME_ZEROSSL_EAB_HMAC_KEY`.                                                                |
| `ACME_ZEROSSL_EAB_HMAC_KEY`        |                          | multisite | no       | **ZeroSSL EAB HMAC Key:** Manual EAB HMAC key (alternative to API key). Used with `ACME_ZEROSSL_EAB_KID`.                                                                         |
| `LETS_ENCRYPT_PASSTHROUGH`         | `no`                     | multisite | no       | **Pass Through Let's Encrypt:** Set to `yes` to pass through Let's Encrypt requests to the web server. This is useful when BunkerWeb is behind another reverse proxy handling SSL.   |
| `EMAIL_LETS_ENCRYPT`               | `contact@{FIRST_SERVER}` | multisite | no       | **Contact Email:** Email address that is used for certificate notifications and is included in certificates.                                                                         |
| `LETS_ENCRYPT_CHALLENGE`           | `http`                   | multisite | no       | **Challenge Type:** Method used to verify domain ownership. Options: `http` or `dns`.                                                                                                |
| `LETS_ENCRYPT_DNS_PROVIDER`        |                          | multisite | no       | **DNS Provider:** When using DNS challenges, the DNS provider to use (e.g., cloudflare, route53, digitalocean).                                                                      |
| `LETS_ENCRYPT_DNS_PROPAGATION`     | `default`                | multisite | no       | **DNS Propagation:** The time to wait for DNS propagation in seconds. If no value is provided, the provider's default propagation time is used.                                      |
| `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` |                          | multisite | yes      | **Credential Item:** Configuration items for DNS provider authentication (e.g., `cloudflare_api_token 123456`). Values can be raw text, base64 encoded, or a JSON object.            |
| `USE_LETS_ENCRYPT_WILDCARD`        | `no`                     | multisite | no       | **Wildcard Certificates:** When set to `yes`, creates wildcard certificates for all domains. Only available with DNS challenges.                                                     |
| `USE_LETS_ENCRYPT_STAGING`         | `no`                     | multisite | no       | **Use Staging:** When set to `yes`, uses staging environment for testing. Staging has higher rate limits but produces certificates that are not trusted by browsers.               |
| `LETS_ENCRYPT_CLEAR_OLD_CERTS`     | `no`                     | global    | no       | **Clear Old Certificates:** When set to `yes`, removes old certificates that are no longer needed during renewal.                                                                    |
| `LETS_ENCRYPT_PROFILE`             | `classic`                | multisite | no       | **Certificate Profile:** Select the certificate profile to use. Options: `classic` (general-purpose), `tlsserver` (optimized for TLS servers), or `shortlived` (7-day certificates). |
| `LETS_ENCRYPT_CUSTOM_PROFILE`      |                          | multisite | no       | **Custom Certificate Profile:** Enter a custom certificate profile if your ACME server supports non-standard profiles. This overrides `LETS_ENCRYPT_PROFILE` if set.                 |
| `LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES` | `yes`                | multisite | no       | **Disable Public Suffixes:** When set to `yes`, prevents certificate requests for domains matching the Public Suffix List (recommended for security).                               |
| `LETS_ENCRYPT_MAX_RETRIES`         | `0`                      | multisite | no       | **Maximum Retries:** Number of times to retry certificate generation on failure. Set to `0` to disable retries. Uses exponential backoff (30s, 60s, 120s, etc. up to 300s max).    |
| `ACME_SKIP_CAA_CHECK`              | `no`                     | global    | no       | **Skip CAA Validation:** Set to `yes` to skip DNS CAA record validation. Use with caution as CAA records provide important security controls.                                       |
| `ACME_HTTP_STRICT_IP_CHECK`        | `no`                     | global    | no       | **Strict IP Check:** When set to `yes`, rejects HTTP challenge certificates if domain IP doesn't match server IP. Useful for preventing misconfigurations.                          |

!!! info "Information and behavior"
    - The `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting is a multiple setting and can be used to set multiple items for the DNS provider. The items will be saved as a cache file, and Certbot will read the credentials from it.
    - If no `LETS_ENCRYPT_DNS_PROPAGATION` setting is provided, the provider's default propagation time is used.
    - Full Let's Encrypt automation using the `http` challenge works in stream mode as long as you open the `80/tcp` port from the outside. Use the `LISTEN_STREAM_PORT_SSL` setting to choose your listening SSL/TLS port.
    - If `LETS_ENCRYPT_PASSTHROUGH` is set to `yes`, BunkerWeb will not handle the ACME challenge requests itself but will pass them to the backend web server. This is useful in scenarios where BunkerWeb is acting as a reverse proxy in front of another server that is configured to handle Let's Encrypt challenges.
    - The plugin automatically validates external IP addresses for HTTP challenges and can optionally enforce strict IP matching.
    - CAA record validation ensures only authorized certificate authorities can issue certificates for your domains.
    - Public Suffix List validation prevents certificate requests for domains like `.com` or `.co.uk` that could never be validated.

!!! tip "HTTP vs. DNS Challenges"
    **HTTP Challenges** are easier to set up and work well for most websites:

    - Requires your website to be publicly accessible on port 80
    - Automatically configured by BunkerWeb
    - Cannot be used for wildcard certificates
    - Includes IP address validation for additional security

    **DNS Challenges** offer more flexibility and are required for wildcard certificates:

    - Works even when your website is not publicly accessible
    - Requires DNS provider API credentials
    - Required for wildcard certificates (e.g., *.example.com)
    - Useful when port 80 is blocked or unavailable
    - Supports advanced wildcard domain grouping

!!! warning "Wildcard certificates"
    Wildcard certificates are only available with DNS challenges. If you want to use them, you must set the `USE_LETS_ENCRYPT_WILDCARD` setting to `yes` and properly configure your DNS provider credentials.

!!! warning "Rate Limits"
    Certificate authorities impose rate limits on certificate issuance. When testing configurations, use the staging environment by setting `USE_LETS_ENCRYPT_STAGING` to `yes` to avoid hitting production rate limits. Staging certificates are not trusted by browsers but are useful for validating your setup.

## Supported DNS Providers

The Let's Encrypt plugin supports a wide range of DNS providers for DNS challenges. Each provider requires specific credentials that must be provided using the `LETS_ENCRYPT_DNS_CREDENTIAL_ITEM` setting.

| Provider       | Description     | Mandatory Settings                                                                                           | Optional Settings                                                                                                                                                                                                                                                        | Documentation                                                                         |
| -------------- | --------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `cloudflare`   | Cloudflare      | either `api_token` or `email` and `api_key`                                                               |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/)             |
| `desec`        | deSEC           | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/desec-io/certbot-dns-desec/blob/main/README.md)    |
| `digitalocean` | DigitalOcean    | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/)           |
| `dnsimple`     | DNSimple        | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/)               |
| `dnsmadeeasy`  | DNS Made Easy   | `api_key` `secret_key`                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/)            |
| `gehirn`       | Gehirn DNS      | `api_token` `api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/)                 |
| `google`       | Google Cloud    | `project_id` `private_key_id` `private_key` `client_email` `client_id` `client_x509_cert_url` | `type` (default: `service_account`) `auth_uri` (default: `https://accounts.google.com/o/oauth2/auth`) `token_uri` (default: `https://accounts.google.com/o/oauth2/token`) `auth_provider_x509_cert_url` (default: `https://www.googleapis.com/oauth2/v1/certs`) | [Documentation](https://certbot-dns-google.readthedocs.io/en/stable/)                 |
| `infomaniak`   | Infomaniak      | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/infomaniak/certbot-dns-infomaniak)                 |
| `ionos`        | IONOS           | `prefix` `secret`                                                                                         | `endpoint` (default: `https://api.hosting.ionos.com`)                                                                                                                                                                                                                    | [Documentation](https://github.com/helgeerbe/certbot-dns-ionos/blob/master/README.md) |
| `linode`       | Linode          | `key`                                                                                                        |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-linode.readthedocs.io/en/stable/)                 |
| `luadns`       | LuaDNS          | `email` `token`                                                                                           |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/)                 |
| `njalla`       | Njalla          | `token`                                                                                                      |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/chaptergy/certbot-dns-njalla)                      |
| `nsone`        | NS1             | `api_key`                                                                                                    |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/)                  |
| `ovh`          | OVH             | `application_key` `application_secret` `consumer_key`                                                  | `endpoint` (default: `ovh-eu`)                                                                                                                                                                                                                                           | [Documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/)                    |
| `rfc2136`      | RFC 2136        | `server` `name` `secret`                                                                               | `port` (default: `53`) `algorithm` (default: `HMAC-SHA512`) `sign_query` (default: `false`)                                                                                                                                                                        | [Documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/)                |
| `route53`      | Amazon Route 53 | `access_key_id` `secret_access_key`                                                                       |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-route53.readthedocs.io/en/stable/)                |
| `sakuracloud`  | Sakura Cloud    | `api_token` `api_secret`                                                                                  |                                                                                                                                                                                                                                                                          | [Documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/)            |
| `scaleway`     | Scaleway        | `application_token`                                                                                          |                                                                                                                                                                                                                                                                          | [Documentation](https://github.com/vanonox/certbot-dns-scaleway/blob/main/README.rst) |

## Certificate Key Types and Optimization

The plugin automatically selects optimal certificate key types based on the certificate authority and DNS provider:

- **ECDSA Keys**: Used by default for most providers
  - Let's Encrypt: P-256 curve (secp256r1) for optimal performance
  - ZeroSSL: P-384 curve (secp384r1) for enhanced security
- **RSA Keys**: Used for specific providers that require them
  - Infomaniak and IONOS: RSA-4096 for compatibility

## Example Configurations

=== "Basic HTTP Challenge with Let's Encrypt"

    Simple configuration using HTTP challenges for a single domain:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ACME_SSL_CA_PROVIDER: "letsencrypt"
    ```

=== "ZeroSSL with API Key"

    Configuration using ZeroSSL with automated EAB setup:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ACME_SSL_CA_PROVIDER: "zerossl"
    ACME_ZEROSSL_API_KEY: "your-zerossl-api-key"
    ```

=== "ZeroSSL with Manual EAB Credentials"

    Configuration using ZeroSSL with manually provided EAB credentials:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ACME_SSL_CA_PROVIDER: "zerossl"
    ACME_ZEROSSL_EAB_KID: "your-eab-kid"
    ACME_ZEROSSL_EAB_HMAC_KEY: "your-eab-hmac-key"
    ```

=== "Cloudflare DNS with Wildcard"

    Configuration for wildcard certificates using Cloudflare DNS:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "dns"
    LETS_ENCRYPT_DNS_PROVIDER: "cloudflare"
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "dns_cloudflare_api_token YOUR_API_TOKEN"
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

=== "Production with Enhanced Security"

    Configuration with all security features enabled and retry mechanisms:

    ```yaml
    AUTO_LETS_ENCRYPT: "yes"
    EMAIL_LETS_ENCRYPT: "admin@example.com"
    LETS_ENCRYPT_CHALLENGE: "http"
    ACME_SSL_CA_PROVIDER: "letsencrypt"
    LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES: "yes"
    ACME_HTTP_STRICT_IP_CHECK: "yes"
    LETS_ENCRYPT_MAX_RETRIES: "3"
    LETS_ENCRYPT_PROFILE: "tlsserver"
    ```

=== "Testing with Staging Environment"

    Configuration for testing setup with the staging environment:

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
    LETS_ENCRYPT_DNS_CREDENTIAL_ITEM: "dns_digitalocean_token YOUR_API_TOKEN"
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

## Troubleshooting

**Common Issues and Solutions:**

1. **Certificate generation fails with rate limits**
   - Use staging environment: `USE_LETS_ENCRYPT_STAGING: "yes"`
   - Enable retries: `LETS_ENCRYPT_MAX_RETRIES: "3"`

2. **HTTP challenge fails**
   - Verify domain DNS points to your server IP
   - Enable strict IP checking: `ACME_HTTP_STRICT_IP_CHECK: "yes"`
   - Check firewall allows port 80 access

3. **DNS challenge fails**
   - Verify DNS provider credentials are correct
   - Increase propagation time: `LETS_ENCRYPT_DNS_PROPAGATION: "300"`
   - Check DNS provider API rate limits

4. **CAA validation errors**
   - Update CAA records to authorize your chosen certificate authority
   - Temporarily skip CAA checking: `ACME_SKIP_CAA_CHECK: "yes"`

5. **ZeroSSL EAB issues**
   - Ensure API key is valid and has correct permissions
   - Try manual EAB credentials if API setup fails
   - Check ZeroSSL account has ACME access enabled

**Debug Information:**

Enable debug logging by setting `LOG_LEVEL: "DEBUG"` to get detailed information about:

- Certificate generation process
- DNS validation steps
- HTTP challenge deployment
- CAA record checking
- IP address validation
- Retry attempts and backoff timing
