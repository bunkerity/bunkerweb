The Mutual TLS (mTLS) plugin protects sensitive applications by requiring visiting clients to present certificates issued by authorities you trust. With it enabled, BunkerWeb authenticates callers before their requests reach your services, keeping internal tools and partner integrations locked down.

BunkerWeb evaluates each handshake against the CA bundle and policy you configure. Clients that fail the verification rules are stopped, while compliant connections can optionally pass certificate details to upstream applications for deeper authorization decisions.

**How it works:**

1. The plugin watches HTTPS handshakes on the selected site.
2. During the TLS exchange, BunkerWeb inspects the client certificate and verifies its chain against your configured trust store.
3. The verification mode decides whether unauthenticated clients are rejected, let through, or accepted for diagnostics. See "What each mode protects" below.
4. (Optional) BunkerWeb exposes the verification outcome through `X-SSL-Client-*` headers so your application layer can apply finer-grained logic.

!!! success "Key benefits"

      1. **Strong perimeter control:** Allow only authenticated machines and users onto sensitive routes.
      2. **Flexible trust policies:** Combine strict and optional verification modes to match onboarding workflows.
      3. **Visibility for apps:** Forward certificate fingerprints and identities to downstream services for auditing.
      4. **Layered security:** Pair mTLS with other BunkerWeb plugins (rate limiting, IP filtering) for defense in depth.

### How to Use

Follow these steps to deploy mutual TLS with confidence:

1. **Enable the feature:** Set `USE_MTLS` to `yes` on the sites that require certificate authentication.
2. **Provide the CA bundle:** Point `MTLS_CA_CERTIFICATE` at a PEM file readable by the Scheduler, or supply the bundle inline as base64/PEM data with `MTLS_CA_CERTIFICATE_DATA`. The Scheduler validates, caches, and distributes the bundle to every instance, so no per-instance mounting is needed.
3. **Select the verification mode:** Pick `on` for mandatory certificates, `optional` to let clients without a certificate through (and require one only on the paths listed in `MTLS_URL`), or `optional_no_ca` for temporary diagnostics.
4. **Tune chain depth:** Adjust `MTLS_VERIFY_DEPTH` if your organization issues intermediate certificates beyond the default depth.
5. **Forward results (optional):** Keep `MTLS_FORWARD_CLIENT_HEADERS` at `yes` when upstream services should inspect the presented certificate.
6. **Maintain revocation data:** If you publish a CRL, set `MTLS_CRL` (or `MTLS_CRL_DATA`) so BunkerWeb can deny revoked certificates.
7. **Choose what plain HTTP does:** `MTLS_HTTP_POLICY` (`redirect` by default) decides what happens to plain HTTP requests that mTLS should have protected.
8. **Decide whether certificate failures count toward bans (optional):** `MTLS_COUNT_BAD_BEHAVIOR` (`no` by default) lets Bad Behavior count them.

The Scheduler validates the whole candidate CA bundle and every CRL before replacing either cached file. A CRL is refused when it cannot be parsed, or when its issuer is part of the bundle and the signature does not verify against it; a CRL signed by a CA that is absent from the bundle is published with a warning, because NGINX builds the chain from the intermediates the client presents. An unreadable, malformed or mismatched replacement keeps the previous CA/CRL pair and logs an error. Rotate the CA and its CRL together, and correct invalid sources promptly, especially before a CRL expires. Clearing both `MTLS_CRL` and `MTLS_CRL_DATA` deliberately removes revocation checking. Removing the CA configuration, disabling mTLS, or deleting the service removes its cached material; while `USE_MTLS` stays `yes` with any mode other than `optional_no_ca`, `ssl_verify_client` then applies against a built-in placeholder CA, so every client gets a 400 with `on` and every client presenting a certificate gets a 400 with `optional`, until a CA is configured again. Effective removals request a reload.

The `client-cert` job runs every hour, so a CA bundle or CRL file you replace on disk is picked up within the hour. It logs an error for an expired CRL (every client of the CA that signed it is refused until a fresh CRL is published) and for an expired CA certificate. It logs a warning for a CRL that expires within 7 days, for a CA certificate that expires within 30 days, for a certificate of the bundle that is not a CA, and, once at least one CRL is configured, for each CA of the bundle that has no CRL. The warning for a missing CRL names each CA without a CRL: every CA that issues a certificate of the chain, the root included, must have its CRL in the set, or clients whose chain includes a certificate it issued are refused. The job still publishes the material in each case: NGINX refuses the affected clients either way, and keeping older material would be no better.

### What each mode protects

"Reaches your backend" means the request is forwarded to the service once the other BunkerWeb plugins have accepted it too.

- **`on`:** every HTTPS request needs a certificate that validates against the CA bundle. A request with no certificate or an invalid one gets a `400` from NGINX and never reaches your backend. Plain HTTP follows `MTLS_HTTP_POLICY`, on every path.
- **`optional` without `MTLS_URL`:** enforces nothing by itself. A client without a certificate reaches your backend, on HTTPS and on plain HTTP. A client that presents an invalid certificate is still refused (`400`) on HTTPS. Use it when your application reads the forwarded `X-SSL-Client-*` headers and decides for itself.
- **`optional` with `MTLS_URL`:** only the paths that match a rule need a valid certificate. On HTTPS a client without one gets a `403` on those paths. On plain HTTP those paths follow `MTLS_HTTP_POLICY`. Every other path reaches your backend with or without a certificate, on HTTPS and on HTTP. A client that presents an invalid certificate is refused (`400`) on every path.
- **`optional_no_ca`:** for diagnostics, not protection. NGINX asks for a certificate and tolerates the trust-chain errors (self-signed certificate, unknown issuer, untrusted chain), so a client that no CA vouches for still completes the handshake. Any other verification error still refuses the client with a `400` on HTTPS, for example an expired or revoked certificate. Without `MTLS_URL` it enforces nothing. With `MTLS_URL`, the matching paths still need a certificate that validates against a CA bundle, and with no CA bundle configured nothing can validate, so those paths deny every client.

In `SECURITY_MODE=detect`, the denials and redirects that BunkerWeb itself issues (per-path rule, plain HTTP policy, invalid `MTLS_URL` rule) are logged and not enforced, and the request goes on to the next plugin. The handshake-level check of `on` and `optional` is done by NGINX and is not affected by the security mode.

### Plain HTTP requests

A client certificate travels only inside TLS, so the handshake check cannot protect plain HTTP. For a service with `USE_MTLS` set to `yes`, `MTLS_HTTP_POLICY` decides what happens to a plain HTTP request that mTLS should have protected: every path when `MTLS_VERIFY_CLIENT` is `on`, the `MTLS_URL` paths otherwise. Under `optional` or `optional_no_ca` without `MTLS_URL`, mTLS protects nothing on HTTPS, so nothing on HTTP either.

- `redirect` (default): the client gets a `301` to the same URL over HTTPS. A request without a usable `Host` header is denied instead. It keeps the port of the `Host` header, as the SSL plugin's redirect does: where the HTTP and HTTPS ports differ and are not the standard 80/443 pair, the client is sent over HTTPS to the HTTP port number, so use `MTLS_HTTP_POLICY=deny` there, or redirect in front of BunkerWeb.
- `deny`: the request is refused with the deny status (`DENY_HTTP_STATUS`, `403` by default).
- `allow`: plain HTTP is served as before when `MTLS_VERIFY_CLIENT` is `on`. The `MTLS_URL` paths stay denied.

An HTTPS redirect already issued by the SSL plugin (`REDIRECT_HTTP_TO_HTTPS`, or `AUTO_REDIRECT_HTTP_TO_HTTPS` when it detects HTTPS) comes first, so the policy only sees the plain HTTP requests that redirect lets through. ACME HTTP-01 challenges stay reachable: a plain HTTP `GET` or `HEAD` on `/.well-known/acme-challenge/<token>` is not touched when a solver owns it, which means the local Let's Encrypt solver with the token present, or `LETS_ENCRYPT_PASSTHROUGH` or `ACME_PASSTHROUGH` set to `yes`. Any other path under `/.well-known/acme-challenge/` follows the policy. Set `LISTEN_HTTP` to `no` on the service to close the plain HTTP port entirely.

### Configuration Settings

| Setting                        | Default    | Context   | Multiple | Description                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------ | ---------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                     | `no`       | multisite | no       | **Use mutual TLS:** Enable client certificate authentication for the current site.                                                                                                                                                                                                                                                                                                                                         |
| `MTLS_CA_CERTIFICATE_PRIORITY` | `file`     | multisite | no       | **Client CA bundle priority:** Source of the client CA bundle: `file` (path) or `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                       |
| `MTLS_CA_CERTIFICATE`          |            | multisite | no       | **Client CA bundle path:** Path to the trusted client CA bundle (PEM), readable by the Scheduler. Required when `MTLS_VERIFY_CLIENT` is `on` or `optional`.                                                                                                                                                                                                                                                                |
| `MTLS_CA_CERTIFICATE_DATA`     |            | multisite | no       | **Client CA bundle data:** Trusted client CA bundle supplied directly as base64 or plaintext PEM (e.g. through the web UI).                                                                                                                                                                                                                                                                                                |
| `MTLS_VERIFY_CLIENT`           | `on`       | multisite | no       | **Verify client mode:** `on` requires a valid certificate on every HTTPS request. `optional` asks for a certificate, refuses an invalid one and enforces nothing more unless `MTLS_URL` is set. `optional_no_ca` asks for a certificate without validating it against a CA (diagnostics only). See "What each mode protects".                                                                                              |
| `MTLS_URL`                     |            | multisite | yes      | **mTLS URL:** Regex on the normalized request URI that requires a valid client certificate only on matching paths, on HTTPS and on plain HTTP. Requires `MTLS_VERIFY_CLIENT` set to `optional`. Case-sensitive, anchor it on a directory. Leave empty for no per-path rule: with `optional` or `optional_no_ca` nothing is enforced, and requiring a certificate on the whole site needs `MTLS_VERIFY_CLIENT` set to `on`. |
| `MTLS_HTTP_POLICY`             | `redirect` | multisite | no       | **HTTP policy:** What to do with a plain HTTP request that mTLS should have protected: `redirect` it to HTTPS, `deny` it, or `allow` it (server-wide mode only, the `MTLS_URL` paths stay denied).                                                                                                                                                                                                                         |
| `MTLS_COUNT_BAD_BEHAVIOR`      | `no`       | multisite | no       | **Count mTLS failures in Bad Behavior:** Let Bad Behavior count the `400` that NGINX answers for a missing or invalid client certificate, and the denials mTLS issues itself. When `no`, a client without a valid certificate is not banned for that alone.                                                                                                                                                                |
| `MTLS_VERIFY_DEPTH`            | `2`        | multisite | no       | **Verify depth:** Maximum certificate chain depth accepted for client certificates.                                                                                                                                                                                                                                                                                                                                        |
| `MTLS_FORWARD_CLIENT_HEADERS`  | `yes`      | multisite | no       | **Forward client headers:** Propagate verification results (`X-SSL-Client-*` headers with status, DN, issuer, serial, fingerprint, validity window). Client-supplied `X-SSL-*` headers are always stripped on ingress, so these values cannot be spoofed.                                                                                                                                                                  |
| `MTLS_CRL_PRIORITY`            | `file`     | multisite | no       | **Client CRL priority:** Source of the CRL: `file` (path) or `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                                          |
| `MTLS_CRL`                     |            | multisite | no       | **Client CRL path:** Optional path to a PEM-encoded certificate revocation list, readable by the Scheduler. Applied only when the CA bundle is successfully loaded. NGINX needs a CRL from every CA that issues a certificate of the chain, the root included. An expired CRL refuses the clients of its CA.                                                                                                               |
| `MTLS_CRL_DATA`                |            | multisite | no       | **Client CRL data:** Certificate revocation list supplied directly as base64 or plaintext PEM.                                                                                                                                                                                                                                                                                                                             |

!!! warning "A revoked certificate keeps working until its TLS session ends"
    Publishing a CRL does not end the TLS sessions that a revoked client saved before. NGINX lets that client resume such a session without checking the certificate again, until the session expires (`ssl_session_timeout`, one day by default) or NGINX is restarted. A reload does not clear it. Plan for that delay when you revoke a certificate, and restart NGINX if the revocation cannot wait. Only new sessions are checked against the CRL.

!!! tip "Write `MTLS_URL` rules with care"
    - The match is case-sensitive: `^/admin` does not match `/Admin`. Start the pattern with `(?i)` to ignore case.
    - The regex runs on the URI as NGINX normalizes it (decoded, dot segments resolved, repeated slashes merged), without the query string, so `/a/../admin` and `//admin` are already covered.
    - Anchor on a directory, not on a file name. Write `^/admin(/|$)` rather than `^/admin$`, which does not match `/admin/`. A rule anchored on a file name such as `^/admin/index\.html$` does not cover `/admin/` either: NGINX serves it from that file through an internal redirect.
    - Path parameters such as `/admin;x=1`, and any other normalization your backend applies on top of NGINX's (for example `..;/` or backslashes), are yours to cover in the regex. BunkerWeb matches the URI NGINX sees.
    - An invalid regex fails closed: every request that no earlier rule matched is denied (`403`) until you fix it. BunkerWeb logs an error that names the service and the pattern at startup and after each reload.

!!! tip "Configure once, distributed everywhere"
    CA bundles and revocation lists do not need to be mounted into the BunkerWeb containers. Supply them to the Scheduler only, as a file path or inline data; the Scheduler validates them, caches them, and distributes them to every instance. Updates are picked up and redistributed automatically on the next job run.

!!! warning "Provide the CA bundle for strict modes"
    When `MTLS_VERIFY_CLIENT` is `on` or `optional`, the Scheduler must be able to validate and cache a client CA bundle. Until it has validated and distributed one, every instance falls back to a placeholder CA that no client can chain to. With `on` that means every client is rejected, where the service previously ran with client verification switched off entirely. With `optional` a client that presents no certificate is still allowed through, which is what that mode means; enforcement for those requests comes from `MTLS_URL` when it is set, and nothing enforces them when it is left empty. A client that does present a certificate is rejected, because nothing can be validated against the placeholder. Use `optional_no_ca` only for diagnostics because it weakens client authentication. After a Scheduler restart with a non-persistent `/var/cache/bunkerweb`, that state lasts until the first job run completes and redistributes the CA bundle, so use a persistent cache volume where a strict enforcement posture is required.

!!! warning "mTLS runs before the whitelist"
    mTLS is evaluated right after the SSL plugin and before the whitelist. A client that matches `WHITELIST_IP`, `WHITELIST_URI`, `WHITELIST_USER_AGENT` (or a default `WHITELIST_RDNS` or `WHITELIST_ASN` entry) still needs a certificate where mTLS requires one. Before 1.6.19 the whitelist skipped the `MTLS_URL` check. To restore that precedence, set `PLUGINS_ORDER_ACCESS` to `ssl whitelist mtls`. If you set `PLUGINS_ORDER_ACCESS` yourself, globally or per service, your value is kept: when it does not name `mtls`, mTLS still runs after the whitelist there. Put `mtls` right after `ssl` in that value.

!!! info "Bad Behavior does not count certificate failures by default"
    With `MTLS_COUNT_BAD_BEHAVIOR` at `no`, the `400` that NGINX answers when the client certificate is missing or invalid, and the denials mTLS issues itself (per-path rule, plain HTTP policy, invalid `MTLS_URL` regex), are not counted by the Bad Behavior plugin, so a client without a valid certificate is not banned for that alone. Any other `400` on the same service still counts. Set it to `yes` to count them again. The answer to a missing or invalid certificate is now BunkerWeb's `400` error page when the Errors plugin handles `400` (the default, unless `ERRORS` sets a custom page for `400`); otherwise it stays NGINX's stock page.

!!! info "Stream services"
    On a stream service only the handshake-level check applies, so only `MTLS_VERIFY_CLIENT` set to `on` enforces anything. A client without a certificate is let through by `optional` and `optional_no_ca`, and `MTLS_URL` and `MTLS_HTTP_POLICY` are HTTP only.

!!! info "`X-SSL-Client-*` headers reach reverse proxy and gRPC upstreams only"
    BunkerWeb forwards the verification results to services configured with the reverse proxy or gRPC plugins. PHP/FastCGI and custom locations do not receive them: pass the `$ssl_client_*` NGINX variables yourself in your configuration.

!!! info "Trusted certificate vs. verification"
    BunkerWeb reuses the same CA bundle for client verification and for building trust chains, keeping revocation checks and handshake validation consistent.

!!! info "Inbound `X-SSL-*` headers are always stripped"
    BunkerWeb removes every client-supplied `X-SSL-*` request header before the request reaches your application, on every site, whether or not mTLS is enabled, and on HTTP/1.1, HTTP/2 and HTTP/3 alike. Only the values BunkerWeb derives from the verified TLS handshake are forwarded, and only when `MTLS_FORWARD_CLIENT_HEADERS` is `yes`, so a client cannot spoof `X-SSL-Client-Verify: SUCCESS`.

    If BunkerWeb sits behind another proxy that terminates mTLS and injects these headers itself, capture the value before the strip and re-publish it. Add a custom `server-http` configuration:

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    then forward it with `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"`. `REVERSE_PROXY_HEADERS` alone does not work: `$http_x_ssl_client_verify` is already empty by the time `proxy_set_header` evaluates it, whereas `set` runs in the server-rewrite phase, before the strip.

!!! warning "Per-path mTLS requires optional mode"
    NGINX's `ssl_verify_client` directive is server-scope only: it cannot be set per `location`. To require a certificate on some paths only, set `MTLS_VERIFY_CLIENT` to `optional` so the handshake completes for every path, then list the protected paths in `MTLS_URL_n`. BunkerWeb enforces the certificate per-request in Lua on the matching URLs. Use `optional` for real enforcement: `optional_no_ca` skips the CA check at the handshake, and the per-path check still needs a certificate that validates against a CA bundle, so with no CA bundle configured the matching paths deny every client. If you leave `MTLS_VERIFY_CLIENT` at `on` while setting `MTLS_URL_n`, NGINX rejects certificate-less clients during the handshake before BunkerWeb can apply the per-path logic, so enforcement stays site-wide (BunkerWeb logs a warning at startup in this case).

!!! info "Browser certificate prompts with optional mode"
    The TLS handshake happens before NGINX knows which URL was requested, so under `optional` NGINX still sends a `CertificateRequest` on every connection. Enforcement becomes per-path, but the handshake-level invitation does not: browsers may still prompt for a certificate on unprotected paths (behaviour varies per browser). On those paths BunkerWeb allows the request whether or not a certificate is presented.

### Example Configurations

=== "Strict access control"

    Require valid client certificates issued by your private CA and forward verification information to the backend:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Optional client authentication"

    Allow anonymous users but forward certificate details when a client presents one. This enforces nothing by itself: your application decides from the forwarded headers:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnostics without a CA"

    Allow connections to complete even if a certificate cannot be chained to a trusted CA bundle. Useful only for troubleshooting:

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

=== "Per-path mTLS (e.g. only `/login`)"

    Require client certificates on selected paths while keeping the rest of the site open. Verification runs in `optional` mode so the handshake completes for unauthenticated paths; BunkerWeb then enforces the certificate per-request on URLs matching `MTLS_URL_n` (a regex per slot):

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_URL_1: "^/login(/|$)"
    MTLS_URL_2: "^/admin(/|$)"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Request             | Certificate       | Result                                                 |
    | ------------------- | ----------------- | ------------------------------------------------------ |
    | `GET /`             | none              | Allowed (path not under mTLS)                          |
    | `GET /login`        | none              | Denied (`403`)                                         |
    | `GET /login`        | valid             | Allowed, `X-SSL-Client-*` forwarded                    |
    | any path            | invalid / expired | Refused (`400`) by NGINX                               |
    | `GET /login` (HTTP) | none              | Redirected to HTTPS (`MTLS_HTTP_POLICY` is `redirect`) |
