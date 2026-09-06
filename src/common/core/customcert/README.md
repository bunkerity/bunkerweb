The Custom SSL certificate plugin allows you to use your own SSL/TLS certificates with BunkerWeb instead of the automatically generated ones. This feature is particularly useful if you have existing certificates from a trusted Certificate Authority (CA), need to use certificates with specific configurations, or want to maintain consistent certificate management across your infrastructure.

**How it works:**

1. You provide BunkerWeb with your certificate and private key files, either by specifying file paths or by providing the data in base64-encoded or plaintext PEM format.
2. BunkerWeb validates your certificate and key to ensure they are properly formatted and usable.
3. When a secure connection is established, BunkerWeb serves your custom certificate instead of the auto-generated one.
4. BunkerWeb automatically monitors your certificate's validity and displays warnings if it is approaching expiration.
5. You have full control over certificate management, allowing you to use certificates from any issuer you prefer.

!!! info "Automatic Certificate Monitoring"
    When you enable custom SSL/TLS by setting `USE_CUSTOM_SSL` to `yes`, BunkerWeb automatically monitors the custom certificate specified in `CUSTOM_SSL_CERT`. It checks for changes daily and reloads NGINX if any modifications are detected, ensuring the latest certificate is always in use.

### How to Use

Follow these steps to configure and use the Custom SSL certificate feature:

1. **Enable the feature:** Set the `USE_CUSTOM_SSL` setting to `yes` to enable custom certificate support.
2. **Choose a method:** Decide whether to provide certificates via file paths or as base64-encoded/plaintext data, and set the priority using `CUSTOM_SSL_CERT_PRIORITY`.
3. **Provide certificate files:** If using file paths, specify the locations of your certificate and private key files.
4. **Or provide certificate data:** If using data, provide your certificate and key as either base64-encoded strings or plaintext PEM format.
5. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb automatically uses your custom certificates for all HTTPS connections.

!!! tip "Stream Mode Configuration"
    For stream mode, you must configure the `LISTEN_STREAM_PORT_SSL` setting to specify the SSL/TLS listening port. This step is essential for proper operation in stream mode.

### Configuration Settings

| Setting                    | Default | Context   | Multiple | Description                                                                                                                   |
| -------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`    | multisite | no       | **Enable Custom SSL:** Set to `yes` to use your own certificate instead of the auto-generated one.                            |
| `CUSTOM_SSL_CERT_PRIORITY` | `file`  | multisite | no       | **Certificate Priority:** Choose whether to prioritize the certificate from file path or from base64 data (`file` or `data`). |
| `CUSTOM_SSL_CERT`          |         | multisite | no       | **Certificate Path:** Full path to your SSL certificate or certificate bundle file.                                           |
| `CUSTOM_SSL_KEY`           |         | multisite | no       | **Private Key Path:** Full path to your SSL private key file.                                                                 |
| `CUSTOM_SSL_CERT_DATA`     |         | multisite | no       | **Certificate Data:** Your certificate encoded in base64 format or as plaintext PEM.                                          |
| `CUSTOM_SSL_KEY_DATA`      |         | multisite | no       | **Private Key Data:** Your private key encoded in base64 format or as plaintext PEM.                                          |

### Default server certificate

The **default server** is the block that answers requests matching no configured service: an unknown SNI, a connection to a raw IP address, a `Host` nobody serves. It is not a service and has no settings of its own, so until now the only certificate it could present was the internal self-signed one BunkerWeb generates at startup — which is why a browser reaching an unknown hostname on your instance sees a name-mismatch warning.

These four global settings replace it. Leave them empty to keep the internal certificate.

| Setting                        | Default | Context | Multiple | Description                                                                                                                       |
| ------------------------------ | ------- | ------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `DEFAULT_SERVER_SSL_CERT`      |         | global  | no       | **Default Server Certificate Path:** Full path to the certificate or bundle served for requests matching no configured service.  |
| `DEFAULT_SERVER_SSL_KEY`       |         | global  | no       | **Default Server Key Path:** Full path to the matching private key.                                                              |
| `DEFAULT_SERVER_SSL_CERT_DATA` |         | global  | no       | **Default Server Certificate Data:** The same certificate as base64 or plaintext PEM. Used only when the path setting is empty.  |
| `DEFAULT_SERVER_SSL_KEY_DATA`  |         | global  | no       | **Default Server Key Data:** The same private key as base64 or plaintext PEM. Used only when the path setting is empty.          |

The override is consulted **last**, and only inside the default server: a service that resolves its own certificate — through the certificate inventory, `USE_CUSTOM_SSL`, Let's Encrypt or the self-signed provider — always keeps it.

!!! warning "A certificate covering one of your services is refused"
    The default server answers *any* hostname. If its certificate also covered `www.example.com`, a client could open a connection with an unknown SNI, be handed that certificate, and then reuse the same connection for `Host: www.example.com` — a certificate that service never authorized, now usable for it (HTTP/2 connection coalescing). The `custom-cert` job therefore refuses a certificate whose SANs or Common Name cover any hostname of any configured service, wildcards included, and logs the hostname it refused it for. Use a certificate that covers no configured service hostname, or attach it to the service with `USE_CUSTOM_SSL` instead.

!!! info "A refusal never withdraws what is already served"
    Invalid material, a mismatched pair and a covered hostname all fail the job loudly and leave the previously served certificate in place, rather than dropping the default server to nothing. Expiry only warns, for the same reason. Clearing both settings removes the override and brings the internal certificate back.

!!! tip "Inert when strict SNI is on"
    With `DISABLE_DEFAULT_SERVER_STRICT_SNI` set to `yes`, an unknown SNI is closed during the TLS handshake, before any certificate is chosen — so the override is never reached. Keep it off if you want unknown hostnames to be answered with your own certificate.

!!! warning "Security Considerations"
    When using custom certificates, ensure your private key is properly secured and has appropriate permissions. The files must be readable by the BunkerWeb scheduler.

!!! tip "Certificate Format"
    BunkerWeb expects certificates in PEM format. If your certificate is in a different format, you may need to convert it first.

!!! info "Certificate Chains"
    If your certificate includes a chain (intermediates), you should provide the full certificate chain in the correct order, with your certificate first, followed by any intermediate certificates.


### Example Configurations

=== "Using File Paths"

    A configuration using certificate and key files on disk:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    ```

=== "Using Base64 Data"

    A configuration using base64-encoded certificate and key data:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```

=== "Using Plaintext PEM Data"

    A configuration using plaintext certificate and key data in PEM format:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
      -----BEGIN CERTIFICATE-----
      MIIDdzCCAl+gAwIBAgIUJH...certificate content...AAAA
      -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
      -----BEGIN PRIVATE KEY-----
      MIIEvQIBADAN...key content...AAAA
      -----END PRIVATE KEY-----
    ```

=== "Fallback Configuration"

    A configuration that prioritizes files but falls back to base64 data if files are unavailable:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/path/to/your/certificate.pem"
    CUSTOM_SSL_KEY: "/path/to/your/private-key.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...base64 encoded certificate...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...base64 encoded key...Cg=="
    ```
