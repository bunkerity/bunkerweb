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

!!! tip "Reusable pools of gRPC backends"
    A `GRPC_HOST` points at a single backend. To balance across several backends, or to share the same backends between services, declare a **gRPC upstream pool** on the **Upstreams** page (or through the `/upstreams` API) and attach it to a service at a path — BunkerWeb then writes `grpc://<pool>` into the matching `GRPC_HOST` for you. Note that gRPC and reverse-proxy locations share one path namespace on a service: the same path cannot be claimed twice, whichever plugin serves it. See the *Reusable Upstreams* section of the Reverse Proxy documentation.

!!! tip "Mutual TLS with the gRPC backend"
    gRPC has its own upstream identity, independent of the reverse proxy. For TLS upstreams, use `grpcs://` and configure `GRPC_SSL_SNI` and `GRPC_SSL_SNI_NAME` as needed. To verify the upstream certificate, set `GRPC_SSL_VERIFY=yes` and supply a PEM CA bundle using `GRPC_SSL_TRUSTED_CERTIFICATE` or `_DATA`, selecting the source with `_PRIORITY` (`file` or `data`). `GRPC_SSL_VERIFY_DEPTH` defaults to `1`. No CA bundle is selected automatically: without a cached CA, the generated configuration disables verification and includes a comment explaining how to configure it. A CRL is optional (`GRPC_SSL_CRL` or `_DATA`) and is applied only when verification and a cached CA are present. `GRPC_SSL_PROTOCOLS` and `GRPC_SSL_CIPHERS` leave NGINX defaults unchanged when empty.

    For mutual TLS, set `GRPC_SSL_CLIENT_CERT` and `GRPC_SSL_CLIENT_KEY`, or their `_DATA` variants; `GRPC_SSL_CLIENT_CERT_PRIORITY` selects file paths or data for the pair. Both halves must be valid and match — BunkerWeb checks that the upstream client certificate matches its key; temporary file-read failures keep cached TLS material and report a job failure, while cleared settings or invalid material remove the affected cache. This identity belongs to gRPC; reverse proxy and stream use `REVERSE_PROXY_SSL_CLIENT_*` independently. The shared `trusted-cert` job caches the gRPC CA, CRL, and client pair in the reverseproxy cache directory and triggers configuration regeneration when material changes. There is no separate gRPC certificate job. TLS settings apply to the whole service, including attached upstream pools; they are not per-location settings. See *Mutual TLS with the upstream* in the Reverse Proxy documentation.

### Configuration Settings

| Setting                                 | Default | Context   | Multiple | Description                                                                                                                                |
| ---------------------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_GRPC`                              | `no`    | multisite | no       | **Enable gRPC:** Set to `yes` to enable gRPC proxying.                                                                                    |
| `GRPC_HOST`                             |         | multisite | yes      | **gRPC Upstream:** Value used by `grpc_pass` (for example `grpc://service:50051` or `grpcs://...`).                                       |
| `GRPC_URL`                              | `/`     | multisite | yes      | **Location URL:** Path that will be proxied to the gRPC upstream. A value starting with `^` or ending with `$` is treated as a regex location. Optionally prefix with `~`, `~*`, `=` or `^~` followed by one space to set the nginx location modifier explicitly; no spaces, `;`, `{` or `}` are allowed elsewhere in the value. |
| `GRPC_CUSTOM_HOST`                      |         | multisite | no       | **Custom Host Header:** Overrides `Host` header sent upstream.                                                                            |
| `GRPC_HEADERS`                          |         | multisite | yes      | **Upstream Headers:** Semicolon-separated `grpc_set_header` values; matching generated headers are replaced case-insensitively.           |
| `GRPC_HIDE_HEADERS`                     |         | multisite | yes      | **Hidden Response Headers:** Space-separated list of `grpc_hide_header` values.                                                           |
| `GRPC_HEADERS_CLIENT`                   |         | multisite | yes      | **Client Response Headers:** Semicolon-separated list of `add_header` values sent to the client.                                          |
| `GRPC_PASS_HEADERS`                     |         | multisite | yes      | **Passed Response Headers:** Space-separated list of `grpc_pass_header` values, to forward headers NGINX hides by default.                |
| `GRPC_IGNORE_HEADERS`                   |         | multisite | yes      | **Ignored Response Headers:** Space-separated list of `grpc_ignore_headers` values, to stop NGINX processing them.                        |
| `GRPC_UNDERSCORES_IN_HEADERS`           | `no`    | multisite | no       | **Allow Underscores in Headers:** Enables/disables `underscores_in_headers`. Shared server-wide with the reverse proxy and misc plugins: any service enabling it for one location enables it for the whole service. |
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
| `GRPC_SSL_CLIENT_CERT_PRIORITY`         | `file`  | multisite | no       | **Client Certificate Priority:** Source of the client certificate and key, `file` or `data`.                                              |
| `GRPC_SSL_CLIENT_CERT`                  |         | multisite | no       | **Client Certificate Path:** PEM client certificate presented to the upstream for mutual TLS (priority `file`).                           |
| `GRPC_SSL_CLIENT_CERT_DATA`             |         | multisite | no       | **Client Certificate Data:** Client certificate as base64 or plaintext PEM (priority `data`).                                             |
| `GRPC_SSL_CLIENT_KEY`                   |         | multisite | no       | **Client Key Path:** PEM private key matching the client certificate (priority `file`). It must not be encrypted.                         |
| `GRPC_SSL_CLIENT_KEY_DATA`              |         | multisite | no       | **Client Key Data:** Client private key as base64 or plaintext PEM (priority `data`).                                                     |
| `GRPC_SSL_CRL`                          |         | multisite | no       | **CRL Path:** PEM revocation list applied when verifying the upstream; only applied when `GRPC_SSL_VERIFY=yes`. Takes precedence over the CRL data setting; a set but missing path is an error and the data setting is not used as a fallback. |
| `GRPC_SSL_CRL_DATA`                     |         | multisite | no       | **CRL Data:** Revocation list as base64 or plaintext PEM. Used only when the CRL path is empty.                                           |
| `GRPC_SSL_PROTOCOLS`                    |         | multisite | no       | **Upstream SSL Protocols:** TLS versions offered to the upstream. Empty keeps the NGINX default.                                          |
| `GRPC_SSL_CIPHERS`                      |         | multisite | no       | **Upstream SSL Ciphers:** Cipher suite string offered to the upstream. Empty keeps the NGINX default.                                     |
| `GRPC_NEXT_UPSTREAM`                    |         | multisite | yes      | **Next Upstream Conditions:** Value for `grpc_next_upstream`.                                                                             |
| `GRPC_NEXT_UPSTREAM_TIMEOUT`            |         | multisite | yes      | **Next Upstream Timeout:** Value for `grpc_next_upstream_timeout`.                                                                        |
| `GRPC_NEXT_UPSTREAM_TRIES`              |         | multisite | yes      | **Next Upstream Tries:** Value for `grpc_next_upstream_tries`.                                                                            |
| `GRPC_AUTH_REQUEST`                     |         | multisite | yes      | **Auth Request:** Value for `auth_request`, to authenticate through an external provider.                                                 |
| `GRPC_AUTH_REQUEST_SIGNIN_URL`          |         | multisite | yes      | **Auth Request Signin URL:** Redirect target when the auth request returns 401. Fragments (`#`) are supported.                            |
| `GRPC_AUTH_REQUEST_SET`                 |         | multisite | yes      | **Auth Request Set:** Semicolon-separated list of `auth_request_set` values.                                                              |
| `GRPC_INCLUDES`                         |         | multisite | yes      | **Additional Includes:** Space-separated include files added inside the gRPC `location` block.                                            |
| `GRPC_MAX_CLIENT_SIZE`                  |         | multisite | yes      | **Maximum Body Size:** Value for `client_max_body_size` in this location (`0` for infinite). Falls back to the service `MAX_CLIENT_SIZE`. |

`GRPC_HOST`, `GRPC_URL`, `GRPC_HEADERS`, `GRPC_HIDE_HEADERS`, `GRPC_HEADERS_CLIENT`, `GRPC_PASS_HEADERS`, `GRPC_IGNORE_HEADERS`, `GRPC_BUFFER_SIZE`, `GRPC_CONNECT_TIMEOUT`, `GRPC_READ_TIMEOUT`, `GRPC_SEND_TIMEOUT`, `GRPC_SOCKET_KEEPALIVE`, `GRPC_NEXT_UPSTREAM{,_TIMEOUT,_TRIES}`, `GRPC_AUTH_REQUEST{,_SIGNIN_URL,_SET}`, `GRPC_INCLUDES` and `GRPC_MAX_CLIENT_SIZE` support numeric suffixes for multiple upstreams/locations (`GRPC_HOST_2`, `GRPC_URL_2`, ...). `GRPC_HEADERS_CLIENT` uses NGINX `add_header` semantics (append `always` where required). Auth signin URLs retain fragment support (`#`). ModSecurity remains disabled in gRPC locations.

!!! warning "ModSecurity on gRPC Locations"
    ModSecurity is currently disabled automatically inside gRPC `location` blocks generated by this plugin because ModSecurity does not reliably support gRPC traffic patterns.

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
    GRPC_NEXT_UPSTREAM: "error timeout http_502"
    GRPC_NEXT_UPSTREAM_TIMEOUT: "15s"
    GRPC_NEXT_UPSTREAM_TRIES: "3"
    ```
