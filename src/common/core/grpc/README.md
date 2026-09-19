The gRPC plugin lets BunkerWeb proxy gRPC services through HTTP/2 using `grpc_pass`. It is designed for multisite setups where each virtual host can expose one or more gRPC backends under specific paths.

!!! example "Experimental feature"
    This feature is not production-ready. Feel free to test it and report us any bug using [issues](https://github.com/bunkerity/bunkerweb/issues) in the GitHub repository.

**How it works:**

1. A client sends an HTTP/2 request to BunkerWeb.
2. The gRPC plugin matches a configured `location` (`GRPC_URL`) and forwards the request to the configured upstream (`GRPC_HOST`) with `grpc_pass`.
3. BunkerWeb adds forwarding headers and applies timeout / upstream retry settings.
4. The upstream gRPC server replies and BunkerWeb relays the response back to the client.

### How to Use

1. **Enable the feature:** Set `USE_GRPC` to `yes`.
2. **Configure upstream(s):** Set at least `GRPC_HOST` (and optionally `GRPC_HOST_2`, `GRPC_HOST_3`, ...).
3. **Map path(s):** Set `GRPC_URL` for each upstream (and matching suffixed values for multiple entries).
4. **Tune behavior:** Configure timeouts, retries, headers, and TLS SNI options if needed.

### Configuration Settings

| Setting                                 | Default | Context   | Multiple | Description                                                                                                                               |
| --------------------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`    | multisite | no       | **Enable gRPC:** Set to `yes` to enable gRPC proxying.                                                                                    |
| `GRPC_HOST`                             |         | multisite | yes      | **gRPC Upstream:** Value used by `grpc_pass` (for example `grpc://service:50051` or `grpcs://...`).                                       |
| `GRPC_URL`                              | `/`     | multisite | yes      | **Location URL:** Path that will be proxied to the gRPC upstream.                                                                         |
| `GRPC_CUSTOM_HOST`                      |         | multisite | no       | **Custom Host Header:** Overrides `Host` header sent upstream.                                                                            |
| `GRPC_HEADERS`                          |         | multisite | yes      | **Extra Upstream Headers:** Semicolon-separated list of `grpc_set_header` values.                                                         |
| `GRPC_HIDE_HEADERS`                     |         | multisite | yes      | **Hidden Response Headers:** Space-separated list of `grpc_hide_header` values.                                                           |
| `GRPC_HEADERS_CLIENT`                   |         | multisite | yes      | **Client Response Headers:** Semicolon-separated list of `add_header` values sent to the client.                                          |
| `GRPC_PASS_HEADERS`                     |         | multisite | yes      | **Passed Response Headers:** Space-separated list of `grpc_pass_header` values, to forward headers NGINX hides by default.                |
| `GRPC_IGNORE_HEADERS`                   |         | multisite | yes      | **Ignored Response Headers:** Space-separated list of `grpc_ignore_headers` values, to stop NGINX processing them.                        |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`    | multisite | no       | **Allow Underscores in Headers:** Enables/disables `underscores_in_headers`.                                                              |
| `GRPC_INTERCEPT_ERRORS`                 | `yes`   | multisite | no       | **Intercept Errors:** Enables/disables `grpc_intercept_errors`.                                                                           |
| `GRPC_BUFFER_SIZE`                      |         | multisite | yes      | **Buffer Size:** Value for `grpc_buffer_size` (buffer used to read the upstream response).                                                |
| `GRPC_CONNECT_TIMEOUT`                  | `60s`   | multisite | yes      | **Connect Timeout:** Timeout for establishing connection to upstream.                                                                     |
| `GRPC_READ_TIMEOUT`                     | `60s`   | multisite | yes      | **Read Timeout:** Timeout for reading from upstream.                                                                                      |
| `GRPC_SEND_TIMEOUT`                     | `60s`   | multisite | yes      | **Send Timeout:** Timeout for sending to upstream.                                                                                        |
| `GRPC_SOCKET_KEEPALIVE`                 | `off`   | multisite | yes      | **Socket Keepalive:** Enables/disables upstream socket keepalive.                                                                         |
| `GRPC_SSL_SNI`                          | `no`    | multisite | no       | **SSL SNI:** Enables/disables SNI for TLS upstreams.                                                                                      |
| `GRPC_SSL_SNI_NAME`                     |         | multisite | no       | **SSL SNI Name:** SNI name to send when `GRPC_SSL_SNI=yes`.                                                                               |
| `GRPC_SSL_VERIFY`                       | `no`    | multisite | no       | **SSL Verify:** Enables/disables verification of the gRPC upstream certificate.                                                           |
| `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file`  | multisite | no       | **Trusted Certificate Priority:** Source of the CA bundle, `file` or `data`.                                                              |
| `GRPC_SSL_TRUSTED_CERTIFICATE`          |         | multisite | no       | **Trusted Certificate Path:** Path to a PEM CA bundle readable by the scheduler (priority `file`).                                        |
| `GRPC_SSL_TRUSTED_CERTIFICATE_DATA`     |         | multisite | no       | **Trusted Certificate Data:** CA bundle as base64 or plaintext PEM (priority `data`).                                                     |
| `GRPC_SSL_VERIFY_DEPTH`                 | `1`     | multisite | no       | **SSL Verify Depth:** Verification depth in the upstream certificate chain.                                                               |
| `GRPC_SSL_CERT_PRIORITY`                | `file`  | multisite | no       | **Client Certificate Priority:** Source of the client certificate and key, `file` or `data`.                                              |
| `GRPC_SSL_CERT`                         |         | multisite | no       | **Client Certificate Path:** PEM client certificate presented to the upstream for mutual TLS (priority `file`).                           |
| `GRPC_SSL_CERT_DATA`                    |         | multisite | no       | **Client Certificate Data:** Client certificate as base64 or plaintext PEM (priority `data`).                                             |
| `GRPC_SSL_KEY`                          |         | multisite | no       | **Client Key Path:** PEM private key matching the client certificate (priority `file`). It must not be encrypted.                         |
| `GRPC_SSL_KEY_DATA`                     |         | multisite | no       | **Client Key Data:** Client private key as base64 or plaintext PEM (priority `data`).                                                     |
| `GRPC_SSL_CRL`                          |         | multisite | no       | **CRL Path:** PEM revocation list applied when verifying the upstream. Takes precedence over the CRL data setting.                        |
| `GRPC_SSL_CRL_DATA`                     |         | multisite | no       | **CRL Data:** Revocation list as base64 or plaintext PEM. Used only when the CRL path is empty.                                           |
| `GRPC_SSL_PROTOCOLS`                    |         | multisite | no       | **Upstream SSL Protocols:** TLS versions offered to the upstream. Empty keeps the NGINX default.                                          |
| `GRPC_SSL_CIPHERS`                      |         | multisite | no       | **Upstream SSL Ciphers:** Cipher suite string offered to the upstream. Empty keeps the NGINX default.                                     |
| `GRPC_NEXT_UPSTREAM`                    |         | multisite | yes      | **Next Upstream Conditions:** Value for `grpc_next_upstream`.                                                                             |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |         | multisite | yes      | **Next Upstream Timeout:** Value for `grpc_next_upstream_timeout`.                                                                        |
| `GRPC_NEXT_UPSTREAM_TRIES`              |         | multisite | yes      | **Next Upstream Tries:** Value for `grpc_next_upstream_tries`.                                                                            |
| `GRPC_AUTH_REQUEST`                     |         | multisite | yes      | **Auth Request:** Value for `auth_request`, to authenticate through an external provider.                                                 |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |         | multisite | yes      | **Auth Request Signin URL:** Redirect target when the auth request returns 401.                                                           |
| `GRPC_AUTH_REQUEST_SET`                 |         | multisite | yes      | **Auth Request Set:** Semicolon-separated list of `auth_request_set` values.                                                              |
| `GRPC_INCLUDES`                         |         | multisite | yes      | **Additional Includes:** Space-separated include files added inside the gRPC `location` block.                                            |
| `GRPC_MAX_CLIENT_SIZE`                  |         | multisite | yes      | **Maximum Body Size:** Value for `client_max_body_size` in this location (`0` for infinite). Falls back to the service `MAX_CLIENT_SIZE`. |

!!! tip "Upstream Mutual TLS"
    A client certificate and its key must both be supplied, and the key must not be encrypted. The scheduler validates the pair, caches it and distributes it to the instances; if it does not validate, the certificate directives are simply not generated. A CRL is only applied while upstream verification is on.

!!! warning "ModSecurity on gRPC Locations"
    ModSecurity is currently disabled automatically inside gRPC `location` blocks generated by this plugin because ModSecurity does not reliably support gRPC traffic patterns.

!!! tip "Verifying the Upstream Certificate"
    `GRPC_SSL_VERIFY` only takes effect once a CA bundle is available. Provide it with `GRPC_SSL_TRUSTED_CERTIFICATE` (a path the scheduler can read) or `GRPC_SSL_TRUSTED_CERTIFICATE_DATA` (base64 or plaintext PEM), and select the source with `GRPC_SSL_TRUSTED_CERTIFICATE_PRIORITY`. The scheduler validates the bundle, caches it and distributes it to the instances. Without a usable bundle, verification stays off.

!!! warning "Long-Lived Streams and Core Timeouts"
    Long-lived or streaming RPCs may require higher generic NGINX timeouts than the global defaults. Commonly tuned settings are `CLIENT_BODY_TIMEOUT` and `CLIENT_HEADER_TIMEOUT` in the General plugin settings.

!!! tip "Multiple gRPC Backends"
    Use suffixed settings for multiple routes:
    - `GRPC_HOST`, `GRPC_URL`
    - `GRPC_HOST_2`, `GRPC_URL_2`
    - `GRPC_HOST_3`, `GRPC_URL_3`

### Example Configurations

=== "Basic gRPC Proxy"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_CONNECT_TIMEOUT: "10s"
    GRPC_READ_TIMEOUT: "300s"
    GRPC_SEND_TIMEOUT: "300s"
    ```

=== "TLS Upstream (grpcs + SNI)"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    ```

=== "Multiple Paths / Backends"

    ```yaml
    USE_GRPC: "yes"

    GRPC_HOST: "grpc://user-service:50051"
    GRPC_URL: "/users.UserService/"

    GRPC_HOST_2: "grpc://billing-service:50052"
    GRPC_URL_2: "/billing.BillingService/"

    GRPC_HOST_3: "grpc://inventory-service:50053"
    GRPC_URL_3: "/inventory.InventoryService/"
    ```

=== "Headers and Retry Policy"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_HEADERS: "x-request-source bunkerweb;x-env production"
    GRPC_NEXT_UPSTREAM: "error timeout unavailable"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```

=== "Verified TLS Upstream"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpcs://internal-grpc.example.net:443"
    GRPC_URL: "/"
    GRPC_SSL_SNI: "yes"
    GRPC_SSL_SNI_NAME: "internal-grpc.example.net"
    GRPC_SSL_VERIFY: "yes"
    GRPC_SSL_TRUSTED_CERTIFICATE: "/etc/ssl/certs/ca-certificates.crt"
    GRPC_SSL_VERIFY_DEPTH: "2"
    ```

=== "External Authentication"

    ```yaml
    USE_GRPC: "yes"
    GRPC_HOST: "grpc://grpcbin:9000"
    GRPC_URL: "/"
    GRPC_AUTH_REQUEST: "/auth"
    GRPC_AUTH_REQUEST_SIGNIN_URL: "https://sso.example.com/login"
    GRPC_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_email $upstream_http_x_email"
    GRPC_HEADERS: "x-forwarded-user $auth_user"
    ```
