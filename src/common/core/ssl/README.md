The SSL plugin provides robust SSL/TLS encryption capabilities for your BunkerWeb-protected websites. This core component enables secure HTTPS connections by configuring and optimizing cryptographic protocols, ciphers, and related security settings to protect data in transit between clients and your web services.

**How it works:**

1. When a client initiates an HTTPS connection to your website, BunkerWeb handles the SSL/TLS handshake using your configured settings.
2. The plugin enforces modern encryption protocols and strong cipher suites while disabling known vulnerable options.
3. Optimized SSL session parameters improve connection performance without sacrificing security.
4. Certificate presentation is configured according to best practices to ensure compatibility and security.

!!! success "Security Benefits"
    - **Data Protection:** Encrypts data in transit, preventing eavesdropping and man-in-the-middle attacks
    - **Authentication:** Verifies the identity of your server to clients
    - **Integrity:** Ensures data hasn't been tampered with during transmission
    - **Modern Standards:** Configured for compliance with industry best practices and security standards

### How to Use

Follow these steps to configure and use the SSL feature:

1. **Configure protocols:** Choose which SSL/TLS protocol versions to support using the `SSL_PROTOCOLS` setting.
2. **Select cipher suites:** Specify the encryption strength using the `SSL_CIPHERS_LEVEL` setting or provide custom ciphers with `SSL_CIPHERS_CUSTOM`.
3. **Configure HTTP to HTTPS redirection:** Set up automatic redirection using the `AUTO_REDIRECT_HTTP_TO_HTTPS` or `REDIRECT_HTTP_TO_HTTPS` settings.
4. **Enable OCSP stapling:** Set `SSL_USE_OCSP_STAPLING` to `yes` to staple a cached OCSP response for certificates that advertise an OCSP responder.
5. **Must-Staple fuse (optional):** Leave `OCSP_STAPLE_MODE` at `normal` unless you need an on-call escape hatch. Both HTTP and stream read the same value.

### Configuration Settings

| Setting                       | Default           | Context   | Multiple | Description                                                                                                         |
| ----------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `REDIRECT_HTTP_TO_HTTPS`      | `no`              | multisite | no       | **Redirect HTTP to HTTPS:** When set to `yes`, all HTTP requests are redirected to HTTPS.                           |
| `AUTO_REDIRECT_HTTP_TO_HTTPS` | `yes`             | multisite | no       | **Auto Redirect HTTP to HTTPS:** When set to `yes`, automatically redirects HTTP to HTTPS if HTTPS is detected.     |
| `SSL_PROTOCOLS`               | `TLSv1.2 TLSv1.3` | multisite | no       | **SSL Protocols:** Space-separated list of SSL/TLS protocols to support.                                            |
| `SSL_CIPHERS_LEVEL`           | `modern`          | multisite | no       | **SSL Ciphers Level:** Preset security level for cipher suites (`modern`, `intermediate`, or `old`).                |
| `SSL_CIPHERS_CUSTOM`          |                   | multisite | no       | **Custom SSL Ciphers:** Colon-separated list of cipher suites to use for SSL/TLS connections (overrides level).     |
| `SSL_ECDH_CURVE`              | `auto`            | multisite | no       | **SSL ECDH Curves:** Colon-separated list of ECDH curves (TLS groups) or `auto` for smart selection (prefers PQC on OpenSSL 3.5+). |
| `SSL_SESSION_CACHE_SIZE`      | `10m`             | multisite | no       | **SSL Session Cache Size:** Size of the SSL session cache (e.g., `10m`, `512k`). Set to `off` or `none` to disable. |
| `SSL_USE_OCSP_STAPLING`       | `no`              | multisite | no       | **Use OCSP stapling:** When set to `yes`, staple a cached OCSP response during the TLS handshake for certificates that advertise an OCSP responder. Applies to HTTP and stream TLS, including Let's Encrypt, custom, and self-signed certificates. |
| `OCSP_STAPLE_MODE`            | `normal`          | multisite | no       | **OCSP staple mode:** Must-Staple fuse for HTTP and stream. `normal` refuses the handshake when Must-Staple is unmet and records the generation on the peer-refuse bus; `staple_only` still probes before `set_cert` (skips unprobed Must-Staple leaves when another leaf can install) but if nothing remains, installs the site leaf **unstapled** and does not abort or write the bus; `open` disables Must-Staple enforcement (recovery) and also installs unstapled without writing the bus. |

Handshake and the OCSP refresh job share a fixed **clock-skew budget** of 300 seconds (`OCSP_CLOCK_SKEW_SECONDS`). Death time is `nextUpdate` / `max_age_unix` **minus** that skew: staples stop being served before the CA's advertised expiry so a lagging worker clock cannot present a response the CA already considers dead.

### OCSP `staple_decision` runbook

Every staple outcome logs a closed **`staple_decision=CODE`**. That code **is** the section key below—grep the log token, open this section, follow the steps. Unknown detail strings normalize to `unmet` with `detail=` preserved. The closed set and aliases live in one place (`bunkerweb.ocsp`); HTTP and stream both format through it.

| `staple_decision` | Meaning | What to do |
| ----------------- | ------- | ---------- |
| `ok` | Staple set (or canary paged) | Healthy. |
| `stapling_off` | Optional stapling disabled / unavailable | Expected when `SSL_USE_OCSP_STAPLING=no` or `ngx.ocsp` missing. Not a Must-Staple abort. |
| `skip_slot` | Dual-cert sibling deliberately not stapled | One OCSP slot per handshake; ECDSA preferred. Put Must-Staple on ECDSA only. |
| `cluster_floor` | Local `published_unix` behind colony floor | Wait for this node’s job to catch the floor. Restore will not raise the floor above a fenced still-GOOD trio (avoids healthy files + closed Must-Staple). |
| `not_paged` | Shard on disk but canary never stamped `paged=true` | Missing `paged` is also not_paged. After **2** verified UNKNOWN answers the job soft-recalls (`paged=false`) while keeping DER until the **3rd** tombstones; a later verified GOOD must canary-page again. Inspect `ocsp-refresh` canary / non-GOOD streak logs. |
| `aia_uri_mismatch` / `aia_uri_unpinned` / `aia_uri_missing_on_leaf` / `aia_uri_leaf_unavailable` | Staple not pinned to leaf AIA OCSP URI | HTTP and stream share `bunkerweb.ocsp.aia_uri_pin_ok`. Must-Staple requires a live leaf PEM to re-check AIA membership (`aia_uri_leaf_unavailable` when fingerprint-only). Re-run refresh; ensure the plugin returns leaf PEM (`status[3]`) for Must-Staple; check leaf AIA vs `ocsp.json` `aia_ocsp_uri`. |
| `ssl_use_ocsp_stapling_no` | Must-Staple leaf but stapling setting off | Set `SSL_USE_OCSP_STAPLING=yes` or remove Must-Staple from the cert. |
| `ngx_ocsp_unavailable` | `ngx.ocsp` / `set_ocsp_status_resp` missing | OpenResty build / load issue—fix ngx_http_lua / stream OCSP module. |
| `response_not_found` | No usable L1/disk GOOD staple | Check job fetch, shard path under `/var/cache/bunkerweb/ssl/`, serial blacklist. |
| `response_stale` | Past nextUpdate / max-age / skew death, or no death clock in meta | Wait for refresh or force `ocsp-refresh`. Handshake requires `expires_unix` and/or `max_age_unix`/`published_unix` in `ocsp.json` — L1 cached expiry may only shorten that clock, never substitute for missing meta. Missing both refuses the staple (fail-closed). |
| `serial_blacklisted` | Serial tombstoned after non-GOOD | Investigate CA revocation/UNKNOWN; clear only after a verified GOOD republish. DB restore keeps the ban when the restored body still matches; clears it when the restored GOOD supersedes (newer `thisUpdate`, different serial, or `serial_unknown` + serial). Restore sweeps preserve `serial-blacklist.json` / `nongood.json` (disk-local); coherence resets `nongood.json` on every GOOD trio restore. |
| `tombstoned` | Shard marked `tombstoned` in `ocsp.json` (revoked/unknown streak) | Job removed the GOOD staple; wait for a newer verified GOOD page. Mid-write: meta is the refuse signal before `.ocsp_epoch` / DER unlink finish. HTTP and stream both sample this flag (early refuse + L1 disk match). First verified non-GOOD below the tombstone threshold halves leftover GOOD `expires_unix` on disk **and** upserts that meta to the DB; restore prefers the shorter death clock for the same `der_sha256` (`ttl_halved_after_nongood`) so a longer stale row cannot undo the recall. |
| `shared_ligand` | Must-Staple L1 not bound to `ocsp.json` `der_sha256` | Epoch drift or partial publish—bump/`ocsp-refresh` so disk meta matches body. |
| `certid_mismatch` | DER CertID ≠ leaf/issuer or meta pin | Refuse multi-response / wrong leaf; re-fetch for this SPKI. |
| `set_staple_failed` / `set_staple_exception` | `set_ocsp_status_resp` failed | OpenResty/OpenSSL staple API error; check worker error log around the call. |
| `fingerprint_unavailable` | No SPKI / hint for the leaf | Ensure plugin returns PEM (`status[3]`) or fingerprint (`status[5]`). |
| `wrong_key_type_staple` | Staple body is wrong key type for chosen leaf | Dual-cert pin; do not borrow RSA↔ECDSA shards. |
| `probe_failed` | Must-Staple probe before `set_cert` failed | Same as unmet for that leaf—fix shard/canary before loading the cert. Soft fuse logs `action=continue_install` and loads the site leaf without a staple (avoids falling back to the static `ssl_certificate` after `clear_certs`). |
| `thisUpdate_future` / `thisUpdate_stale` / `lifetime_too_long` / `thisUpdate_unreadable` | Intrinsic signed-window policy | CA window rejected; check `thisUpdate`/`nextUpdate`; do not force-page. |
| `canary_refused` | Scheduler canary refused page | Live shard unchanged; see `detail=` (`canary_openssl_verify`, …) and fix before page. |
| `peer_refuse` | Sibling subsystem (HTTP↔stream) refused this generation | Shared `ocsp-refuse/{fp}` bus. Inspect `refused_by` / prior `staple_decision`. Sticky codes (`certid_mismatch`, `aia_*`, `tombstoned`, `serial_blacklisted`, `cluster_floor`, `shared_ligand`, `canary_refused`, `not_paged`, intrinsic timing) stay until a new generation is canary-paged. Transient codes (`set_staple_failed`, `response_not_found`, …) age out after 300s. Soft fuse (`OCSP_STAPLE_MODE=staple_only`/`open`) continues with the site leaf installed unstapled and does **not** write the bus. When `paged=true`, a handshake `set_staple_failed` / `set_staple_exception` (CLI canary vs OpenResty attach mismatch) also skips the bus so the sibling subsystem is not poisoned. |
| `peer_refuse_bus` | Local refuse could not be written to the shared bus | Disk/`ocsp-refuse` write failed or generation id missing (`detail=`). Dir is provisioned off-handshake (warmer/job); sibling may still staple until fixed. |
| `await_sni` | Stream staple deferred: no SNI-bound leaf yet | Optional: skip staple (`skip_slot` / `detail=await_sni`). Must-Staple: `OCSP_STAPLE_MODE=normal` aborts; `staple_only`/`open` soft-continue unstapled (global mode when SNI is empty). |
| `unmet` | Must-Staple required and no more specific code | Catch-all—check `detail=` / prior lines; use `OCSP_STAPLE_MODE=staple_only`/`open` only as a temporary fuse. |

Handshake L1 (`TLS:SSL:ocsp:*` in `internalstore` / `internalstore_stream`) is **preloaded off the TLS critical path**: every worker arms an OCSP L1 warmer timer; a short shared-dict lease picks one scanner so disk is not walked N times. If the holder dies, another worker takes the lease (well under the 300s L1 shm TTL) and re-warms. A cold miss can still read `ocsp.der` during `ssl_certificate`, but steady-state and post-publish handshakes should hit DRAM first.

When the scheduler canary has stamped `paged=true` for the exact DER (`der_sha256` ligand), the handshake **trusts that canary** and skips `ngx.ocsp.validate_ocsp_response` (openssl CLI and OpenResty FFI can disagree). CertID / leaf binding and `set_ocsp_status_resp` still run.

!!! warning "Dual-certificate (RSA + ECDSA) Must-Staple limits"
    NGINX / `ngx.ocsp` can attach **one** OCSP staple per handshake. When a service installs both an RSA and an ECDSA leaf (typical dual-cert / hybrid deployment), BunkerWeb picks **one** leaf for that slot:

    - **HTTP and stream:** read ClientHello `signature_algorithms` when available and staple the matching leaf (`ec` or `rsa`); otherwise prefer ECDSA (typical OpenSSL dual-cert choice). Stream also defers stapling until SNI has bound the handshake leaf (`staple_decision=await_sni` / `skip_slot detail=await_sni`).

    Consequences:

    - Only the preferred leaf is stapled. Clients that negotiate the other leaf receive **no** staple for that handshake.
    - If the **non-preferred** certificate has the Must-Staple TLS feature, clients that select that leaf will see Must-Staple as unmet. With `OCSP_STAPLE_MODE=normal`, that can abort the handshake for those clients even when the preferred staple is healthy.
    - If only the **ECDSA** leaf is Must-Staple (recommended for dual-cert), modern clients that prefer ECDSA stay fail-closed correctly; RSA-only clients are outside that pin unless stream ClientHello selected RSA.
    - Logs may show `staple_decision=skip_slot` (`detail=single_slot_ecdsa_prefer`, `single_slot_rsa_prefer`, `wrong_key_type_hint`, or `await_sni`) when a sibling key type is deliberately not stapled or SNI is not yet bound.

    Practical guidance: for dual-cert sites that need Must-Staple, put Must-Staple on the ECDSA leaf (or use a single leaf). Do not expect both key types to be Must-Staple-satisfied on the same connection. Use `OCSP_STAPLE_MODE=staple_only` or `open` only as a temporary recovery fuse if a dual-cert Must-Staple mismatch is paging you — the fuse presents the site leaf unstapled (after `clear_certs`) rather than falling back to the static `ssl_certificate`.

!!! tip "SSL Labs Testing"
    After configuring your SSL settings, use the [Qualys SSL Labs Server Test](https://www.ssllabs.com/ssltest/) to verify your configuration and check for potential security issues. A proper BunkerWeb SSL configuration should achieve an A+ rating.

!!! warning "Protocol Selection"
    Support for older protocols like SSLv3, TLSv1.0, and TLSv1.1 is intentionally disabled by default due to known vulnerabilities. Only enable these protocols if you absolutely need to support legacy clients and understand the security implications of doing so.

### Example Configurations

=== "Modern Security (Default)"

    The default configuration that provides strong security while maintaining compatibility with modern browsers:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Maximum Security"

    Configuration focused on maximum security, potentially with reduced compatibility for older clients:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.3"
    SSL_CIPHERS_LEVEL: "modern"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    REDIRECT_HTTP_TO_HTTPS: "yes"
    ```

=== "Legacy Compatibility"

    Configuration with broader compatibility for older clients (use only if necessary):

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_LEVEL: "old"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "no"
    ```

=== "Custom Ciphers"

    Configuration using custom cipher specification:

    ```yaml
    LISTEN_HTTPS: "yes"
    SSL_PROTOCOLS: "TLSv1.2 TLSv1.3"
    SSL_CIPHERS_CUSTOM: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
    AUTO_REDIRECT_HTTP_TO_HTTPS: "yes"
    ```
