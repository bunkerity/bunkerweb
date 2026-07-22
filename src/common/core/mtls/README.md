The Mutual TLS (mTLS) plugin protects sensitive applications by requiring visiting clients to present certificates issued by authorities you trust. With it enabled, BunkerWeb authenticates callers before their requests reach your services, keeping internal tools and partner integrations locked down.

BunkerWeb evaluates each handshake against the CA bundle and policy you configure. Clients that fail the verification rules are stopped, while compliant connections can optionally pass certificate details to upstream applications for deeper authorization decisions.

**How it works:**

1. The plugin watches HTTPS handshakes on the selected site.
2. During the TLS exchange, BunkerWeb inspects the client certificate and verifies its chain against your configured trust store.
3. The verification mode decides whether unauthenticated clients are rejected, allowed with warnings, or accepted for diagnostics.
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
3. **Select the verification mode:** Pick `on` for mandatory certificates, `optional` to allow fallbacks, or `optional_no_ca` for temporary diagnostics.
4. **Tune chain depth:** Adjust `MTLS_VERIFY_DEPTH` if your organization issues intermediate certificates beyond the default depth.
5. **Forward results (optional):** Keep `MTLS_FORWARD_CLIENT_HEADERS` at `yes` when upstream services should inspect the presented certificate.
6. **Maintain revocation data:** If you publish a CRL, set `MTLS_CRL` (or `MTLS_CRL_DATA`) so BunkerWeb can deny revoked certificates.

### Configuration Settings

| Setting                        | Default | Context   | Multiple | Description                                                                                                                                            |
| ------------------------------ | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_MTLS`                     | `no`    | multisite | no       | **Use mutual TLS:** Enable client certificate authentication for the current site.                                                                     |
| `MTLS_CA_CERTIFICATE_PRIORITY` | `file`  | multisite | no       | **Client CA bundle priority:** Source of the client CA bundle: `file` (path) or `data` (base64/PEM).                                                   |
| `MTLS_CA_CERTIFICATE`          |         | multisite | no       | **Client CA bundle path:** Path to the trusted client CA bundle (PEM), readable by the Scheduler. Required when `MTLS_VERIFY_CLIENT` is `on` or `optional`. |
| `MTLS_CA_CERTIFICATE_DATA`     |         | multisite | no       | **Client CA bundle data:** Trusted client CA bundle supplied directly as base64 or plaintext PEM (e.g. through the web UI).                             |
| `MTLS_VERIFY_CLIENT`           | `on`    | multisite | no       | **Verify client mode:** Choose whether certificates are required (`on`), optional (`optional`), or accepted without CA validation (`optional_no_ca`).  |
| `MTLS_URL`                     |         | multisite | yes      | **mTLS URL:** Regex matched against the request URI to enforce a valid client certificate only on matching paths (HTTP only). Requires `MTLS_VERIFY_CLIENT` set to `optional` or `optional_no_ca`. Leave empty to enforce mTLS on the whole site. |
| `MTLS_VERIFY_DEPTH`            | `2`     | multisite | no       | **Verify depth:** Maximum certificate chain depth accepted for client certificates.                                                                    |
| `MTLS_FORWARD_CLIENT_HEADERS`  | `yes`   | multisite | no       | **Forward client headers:** Propagate verification results (`X-SSL-Client-*` headers with status, DN, issuer, serial, fingerprint, validity window).   |
| `MTLS_CRL_PRIORITY`            | `file`  | multisite | no       | **Client CRL priority:** Source of the CRL: `file` (path) or `data` (base64/PEM).                                                                      |
| `MTLS_CRL`                     |         | multisite | no       | **Client CRL path:** Optional path to a PEM-encoded certificate revocation list, readable by the Scheduler. Applied only when the CA bundle is successfully loaded. nginx requires the CRL file to contain a CRL for every CA in the verification chain. |
| `MTLS_CRL_DATA`                |         | multisite | no       | **Client CRL data:** Certificate revocation list supplied directly as base64 or plaintext PEM.                                                          |

!!! tip "Configure once, distributed everywhere"
    CA bundles and revocation lists do not need to be mounted into the BunkerWeb containers. Supply them to the Scheduler only, as a file path or inline data; the Scheduler validates them, caches them, and distributes them to every instance. Updates are picked up and redistributed automatically on the next job run.

!!! warning "Provide the CA bundle for strict modes"
    When `MTLS_VERIFY_CLIENT` is `on` or `optional`, the Scheduler must be able to validate and cache a client CA bundle. If none is available, BunkerWeb skips the mTLS directives on every instance so the service does not run with an invalid or missing certificate reference. Use `optional_no_ca` only for diagnostics because it weakens client authentication. After a Scheduler restart with a non-persistent `/var/cache/bunkerweb`, mTLS stays disabled until the first job run completes and redistributes the CA bundle, so use a persistent cache volume where a strict enforcement posture is required.

!!! info "Trusted certificate vs. verification"
    BunkerWeb reuses the same CA bundle for client verification and for building trust chains, keeping revocation checks and handshake validation consistent.

!!! warning "Per-path mTLS requires optional mode"
    NGINX's `ssl_verify_client` directive is server-scope only — it cannot be set per `location`. To require a certificate on some paths only, set `MTLS_VERIFY_CLIENT` to `optional` so the handshake completes for every path, then list the protected paths in `MTLS_URL_n`. BunkerWeb enforces the certificate per-request in Lua on the matching URLs. Use `optional` for real enforcement: `optional_no_ca` skips CA chain validation, so a matching URL would accept any presented certificate and provides no meaningful protection. If you leave `MTLS_VERIFY_CLIENT` at `on` while setting `MTLS_URL_n`, NGINX rejects certificate-less clients during the handshake before BunkerWeb can apply the per-path logic, so enforcement stays site-wide (BunkerWeb logs a warning at startup in this case). If an `MTLS_URL_n` value is not a valid regex, BunkerWeb fails closed — requests are denied (`403`) and the offending pattern is logged — rather than silently letting the path through; fix the pattern to restore service.

!!! info "Browser certificate prompts with optional mode"
    The TLS handshake happens before NGINX knows which URL was requested, so under `optional` NGINX still sends a `CertificateRequest` on every connection. Enforcement becomes per-path, but the handshake-level invitation does not — browsers may still prompt for a certificate on unprotected paths (behaviour varies per browser). On those paths BunkerWeb allows the request whether or not a certificate is presented.

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

    Allow anonymous users but forward certificate details when a client presents one:

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
    MTLS_URL_1: "^/login"
    MTLS_URL_2: "^/admin"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Request          | Certificate         | Result                                  |
    | ---------------- | ------------------- | --------------------------------------- |
    | `GET /`          | none                | Allowed (path not under mTLS)           |
    | `GET /login`     | none                | Denied (`403`)                          |
    | `GET /login`     | valid               | Allowed, `X-SSL-Client-*` forwarded     |
    | `GET /login`     | invalid / expired   | Denied (`403`)                          |
