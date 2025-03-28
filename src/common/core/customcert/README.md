The Custom SSL certificate plugin allows you to use your own SSL/TLS certificates with BunkerWeb instead of the automatically generated ones. This feature is particularly useful if you have existing certificates from a trusted Certificate Authority (CA), need to use certificates with specific configurations, or want to maintain consistent certificate management across your infrastructure.

**How it works:**

1. You provide BunkerWeb with your certificate and private key files, either by specifying file paths or by providing the data in base64-encoded format.
2. BunkerWeb validates your certificate and key to ensure they are properly formatted and usable.
3. When a secure connection is established, BunkerWeb serves your custom certificate instead of the auto-generated one.
4. BunkerWeb automatically monitors your certificate's validity and displays warnings if it is approaching expiration.
5. You have full control over certificate management, allowing you to use certificates from any issuer you prefer.

!!! info "Automatic Certificate Monitoring"
    When you enable custom SSL/TLS by setting `USE_CUSTOM_SSL` to `yes`, BunkerWeb automatically monitors the custom certificate specified in `CUSTOM_SSL_CERT`. It checks for changes daily and reloads NGINX if any modifications are detected, ensuring the latest certificate is always in use.

### How to Use

Follow these steps to configure and use the Custom SSL certificate feature:

1. **Enable the feature:** Set the `USE_CUSTOM_SSL` setting to `yes` to enable custom certificate support.
2. **Choose a method:** Decide whether to provide certificates via file paths or as base64-encoded data, and set the priority using `CUSTOM_SSL_CERT_PRIORITY`.
3. **Provide certificate files:** If using file paths, specify the locations of your certificate and private key files.
4. **Or provide certificate data:** If using base64 data, provide your certificate and key as base64-encoded strings.
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
| `CUSTOM_SSL_CERT_DATA`     |         | multisite | no       | **Certificate Data:** Your certificate encoded in base64 format.                                                              |
| `CUSTOM_SSL_KEY_DATA`      |         | multisite | no       | **Private Key Data:** Your private key encoded in base64 format.                                                              |

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
