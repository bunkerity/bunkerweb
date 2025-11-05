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
2. **Provide the CA bundle:** Store the trusted issuers in a PEM file and point `MTLS_CA_CERTIFICATE` to its absolute path.
3. **Select the verification mode:** Pick `on` for mandatory certificates, `optional` to allow fallbacks, or `optional_no_ca` for temporary diagnostics.
4. **Tune chain depth:** Adjust `MTLS_VERIFY_DEPTH` if your organization issues intermediate certificates beyond the default depth.
5. **Forward results (optional):** Keep `MTLS_FORWARD_CLIENT_HEADERS` at `yes` when upstream services should inspect the presented certificate.
6. **Maintain revocation data:** If you publish a CRL, set `MTLS_CRL` so BunkerWeb can deny revoked certificates.

### Configuration Settings

| Setting                       | Default | Context   | Multiple | Description                                                                                                                                            |
| ----------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_MTLS`                    | `no`    | multisite | no       | **Use mutual TLS:** Enable client certificate authentication for the current site.                                                                     |
| `MTLS_CA_CERTIFICATE`         |         | multisite | no       | **Client CA bundle:** Absolute path to the trusted client CA bundle (PEM). Required when `MTLS_VERIFY_CLIENT` is `on` or `optional`; must be readable. |
| `MTLS_VERIFY_CLIENT`          | `on`    | multisite | no       | **Verify client mode:** Choose whether certificates are required (`on`), optional (`optional`), or accepted without CA validation (`optional_no_ca`).  |
| `MTLS_VERIFY_DEPTH`           | `2`     | multisite | no       | **Verify depth:** Maximum certificate chain depth accepted for client certificates.                                                                    |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`   | multisite | no       | **Forward client headers:** Propagate verification results (`X-SSL-Client-*` headers with status, DN, issuer, serial, fingerprint, validity window).   |
| `MTLS_CRL`                    |         | multisite | no       | **Client CRL path:** Optional path to a PEM-encoded certificate revocation list. Applied only when the CA bundle is successfully loaded.               |

!!! tip "Keep certificates up to date"
    Store CA bundles and revocation lists in a mounted volume that the Scheduler can read so that restarts pick up the latest trust anchors.

!!! warning "Provide the CA bundle for strict modes"
    When `MTLS_VERIFY_CLIENT` is `on` or `optional`, the CA file must exist at runtime. If it is missing, BunkerWeb skips the mTLS directives so the service does not boot with an invalid path. Use `optional_no_ca` only for diagnostics because it weakens client authentication.

!!! info "Trusted certificate vs. verification"
    BunkerWeb reuses the same CA bundle for client verification and for building trust chains, keeping revocation checks and handshake validation consistent.

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
