The Self-signed Certificate plugin automatically generates and manages SSL/TLS certificates directly within BunkerWeb, enabling secure HTTPS connections without requiring an external certificate authority. This feature is particularly useful in development environments, internal networks, or whenever you need to quickly deploy HTTPS without configuring external certificates.

**How it works:**

1. When enabled, BunkerWeb automatically generates a self-signed SSL/TLS certificate for your configured domains.
2. The certificate includes all server names defined in your configuration, ensuring proper SSL validation for each domain.
3. Certificates are stored securely and used to encrypt all HTTPS traffic to your websites.
4. The certificate is automatically renewed before expiration, ensuring continuous HTTPS availability.

!!! warning "Browser Security Warnings"
    Browsers will display security warnings when users visit sites using self-signed certificates, as these certificates aren't validated by a trusted certificate authority. For production environments, consider using [Let's Encrypt](#lets-encrypt) instead.

### How to Use

Follow these steps to configure and use the Self-signed Certificate feature:

1. **Enable the feature:** Set the `GENERATE_SELF_SIGNED_SSL` setting to `yes` to enable self-signed certificate generation.
2. **Choose cryptographic algorithm:** Select your preferred algorithm using the `SELF_SIGNED_SSL_ALGORITHM` setting.
3. **Configure validity period:** Optionally set how long the certificate should be valid using the `SELF_SIGNED_SSL_EXPIRY` setting.
4. **Set certificate subject:** Configure the certificate subject using the `SELF_SIGNED_SSL_SUBJ` setting.
5. **Let BunkerWeb handle the rest:** Once configured, certificates are automatically generated and applied to your domains.

!!! tip "Stream Mode Configuration"
    For stream mode, configure the `LISTEN_STREAM_PORT_SSL` setting to specify the SSL/TLS listening port. This step is essential for proper operation in stream mode.

### Configuration Settings

| Setting                     | Default                | Context   | Multiple | Description                                                                                                                       |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `GENERATE_SELF_SIGNED_SSL`  | `no`                   | multisite | no       | **Enable Self-signed:** Set to `yes` to enable automatic self-signed certificate generation.                                      |
| `SELF_SIGNED_SSL_ALGORITHM` | `ec-prime256v1`        | multisite | no       | **Certificate Algorithm:** Algorithm used for certificate generation: `ec-prime256v1`, `ec-secp384r1`, `rsa-2048`, or `rsa-4096`. |
| `SELF_SIGNED_SSL_EXPIRY`    | `365`                  | multisite | no       | **Certificate Validity:** Number of days the self-signed certificate should be valid (default: 1 year).                           |
| `SELF_SIGNED_SSL_SUBJ`      | `/CN=www.example.com/` | multisite | no       | **Certificate Subject:** Subject field for the certificate that identifies the domain.                                            |

!!! tip "Development Environments"
    Self-signed certificates are ideal for development and testing environments where you need HTTPS but do not require certificates trusted by public browsers.

!!! info "Certificate Information"
    The generated self-signed certificates use the specified algorithm (defaulting to Elliptic Curve cryptography with the prime256v1 curve) and include the configured subject, ensuring proper functionality for your domains.

### Example Configurations

=== "Basic Configuration"

    A simple configuration using self-signed certificates with default settings:

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=mysite.local/"
    ```

=== "Short-lived Certificates"

    Configuration with certificates that expire more frequently (useful for regularly testing certificate renewal processes):

    ```yaml
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "ec-prime256v1"
    SELF_SIGNED_SSL_EXPIRY: "90"
    SELF_SIGNED_SSL_SUBJ: "/CN=dev.example.com/"
    ```

=== "Testing with RSA Certificates"

    Configuration for a testing environment where a domain uses self-signed RSA certificates:

    ```yaml
    SERVER_NAME: "test.example.com"
    GENERATE_SELF_SIGNED_SSL: "yes"
    SELF_SIGNED_SSL_ALGORITHM: "rsa-4096"
    SELF_SIGNED_SSL_EXPIRY: "365"
    SELF_SIGNED_SSL_SUBJ: "/CN=test.example.com/"
    ```
