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
| `ok` | Staple set (or canary paged) | Healthy. Full multi-staple (every non-NULL stack entry has a body) also logs `ok` with `multi_entries` / `stapled_entries`. |
| `ok_partial` | Multi-staple attached with one or more NULL stack slots | Legal omission: that `CertificateEntry` has no `status_request`. Not a Must-Staple abort, and **not** a validate-budget miss (budget aborts never reach attach). Check `null_slots=` / `detail=null_slot_omission`; refresh the intermediate SPKI shard if you expected status on that cert. |
| `stapling_off` | Optional stapling disabled / unavailable | Expected when `SSL_USE_OCSP_STAPLING=no` or `ngx.ocsp` missing. Not a Must-Staple abort. |
| `skip_slot` | Dual-cert sibling deliberately not stapled | One OCSP slot per handshake; ECDSA preferred. Put Must-Staple on ECDSA only. |
| `cluster_floor` | Local CA `this_update_unix` behind colony floor (legacy floors: `published_unix`) | Wait for this node’s job to catch the floor. Floor is max-only on signed thisUpdate (not wall clock). Missing local timing is no opinion. Restore will not raise the floor above a fenced still-GOOD trio (avoids healthy files + closed Must-Staple). |
| `not_paged` | Shard on disk but canary never stamped `paged=true` | Missing `paged` is also not_paged. After **2** verified UNKNOWN answers the job soft-recalls (`paged=false`) while keeping DER until the **3rd** tombstones; a later verified GOOD must canary-page again. Soft-recall clears peer-refuse (before and after the unpage write). Handshakes **ignore and drop** any leftover bus marker for that same `der_sha256` while unpaged — sticky poison must not pin recovery of the kept body forever. `not_paged` is never written to the bus. Inspect `ocsp-refresh` canary / non-GOOD streak logs. |
| `aia_uri_mismatch` / `aia_uri_unpinned` / `aia_uri_missing_on_leaf` / `aia_uri_leaf_unavailable` | Staple not pinned to leaf AIA OCSP URI | HTTP and stream share `bunkerweb.ocsp.aia_uri_pin_ok`. Must-Staple requires a live leaf PEM to re-check AIA membership (`aia_uri_leaf_unavailable` when fingerprint-only). Re-run refresh; ensure the plugin returns leaf PEM (`status[3]`) for Must-Staple; check leaf AIA vs `ocsp.json` `aia_ocsp_uri`. |
| `ssl_use_ocsp_stapling_no` | Must-Staple leaf but stapling setting off | Set `SSL_USE_OCSP_STAPLING=yes` or remove Must-Staple from the cert. |
| `ngx_ocsp_unavailable` | `ngx.ocsp` / `set_ocsp_status_resp` missing | OpenResty build / load issue—fix ngx_http_lua / stream OCSP module. |
| `response_not_found` | No usable L1/disk GOOD staple | Check job fetch, shard path under `/var/cache/bunkerweb/ssl/`, serial blacklist. |
| `response_stale` | Past nextUpdate / max-age / skew death, or no death clock in meta | Wait for refresh or force `ocsp-refresh`. Handshake requires `expires_unix` and/or `max_age_unix`/`published_unix` in `ocsp.json` — L1 cached expiry may only shorten that clock, never substitute for missing meta. Missing both refuses the staple (fail-closed). |
| `serial_blacklisted` | Serial tombstoned after non-GOOD | Investigate CA revocation/UNKNOWN; clear only after a verified GOOD republish. Same serial clears on a strictly newer `thisUpdate`, or on any dated GOOD when the ban has no `this_update_unix` (legacy null stamps). DB restore keeps the ban when the restored body still matches; clears it when the restored GOOD supersedes (newer/`undated-ban` rule, different serial, or `serial_unknown` + serial). Restore sweeps preserve `serial-blacklist.json` / `nongood.json` (disk-local); coherence resets `nongood.json` on every GOOD trio restore. |
| `tombstoned` | Shard marked `tombstoned` in `ocsp.json` (revoked/unknown streak) | Job removed the GOOD staple; wait for a newer verified GOOD page. Mid-write: meta is the refuse signal before `.ocsp_epoch` / DER unlink finish. HTTP and stream both sample this flag (early refuse + L1 disk match). First verified non-GOOD below the tombstone threshold halves leftover GOOD `expires_unix` on disk **and** upserts that meta to the DB; restore prefers the shorter death clock for the same `der_sha256` (`ttl_halved_after_nongood`) so a longer stale row cannot undo the recall. |
| `shared_ligand` | Must-Staple L1 not bound to `ocsp.json` `der_sha256` | Epoch drift or partial publish—bump/`ocsp-refresh` so disk meta matches body. |
| `certid_mismatch` | DER CertID ≠ leaf/issuer or meta pin | Refuse wrong leaf / ambiguous multi-match; re-fetch for this SPKI. Job accepts multi-`SingleResponse` bodies when exactly one entry matches leaf+issuer. Disk TTL skip also requires the cached response serial to match the current leaf (same-key renew / shared-key sites). |
| `set_staple_failed` / `set_staple_exception` | `set_ocsp_status_resp` failed | OpenResty/OpenSSL staple API error; check worker error log around the call. |
| `fingerprint_unavailable` | No SPKI / hint for the leaf | Ensure plugin returns PEM (`status[3]`) or fingerprint (`status[5]`). |
| `wrong_key_type_staple` | Staple body is wrong key type for chosen leaf | Dual-cert pin; do not borrow RSA↔ECDSA shards. |
| `probe_failed` | Must-Staple probe before `set_cert` failed | Same as unmet for that leaf—fix shard/canary before loading the cert. Soft fuse logs `action=continue_install` and loads the site leaf without a staple (avoids falling back to the static `ssl_certificate` after `clear_certs`). |
| `thisUpdate_future` / `thisUpdate_stale` / `lifetime_invalid` / `lifetime_too_long` / `thisUpdate_unreadable` | Intrinsic signed-window policy | CA window rejected; check `thisUpdate`/`nextUpdate`; do not force-page. |
| `canary_refused` | Scheduler canary refused page | Live shard unchanged; see `detail=` (`canary_openssl_verify`, …) and fix before page. |
| `peer_refuse` | Sibling subsystem (HTTP↔stream) refused this generation | Shared `ocsp-refuse/{fp}` bus. Inspect `refused_by` / prior `staple_decision`. Sticky codes (`certid_mismatch`, `aia_*`, `tombstoned`, `serial_blacklisted`, `cluster_floor`, `shared_ligand`, `canary_refused`, intrinsic timing, `intermediate_must_staple_libssl`) stay until a new generation is canary-paged — **except** while the shard is soft-recalled/`paged≠true`, when matching markers for the kept `der_sha256` are dropped so re-canary of the same body can succeed. Transient codes (`not_paged`, `set_staple_failed`, `response_not_found`, `validate_budget`, …) age out after 300s — and `not_paged` / `validate_budget` / unpaged shards / paged `set_staple_*` are not written to the bus at all. Soft fuse (`OCSP_STAPLE_MODE=staple_only`/`open`) continues with the site leaf installed unstapled and does **not** write the bus. Soft-recall clears any prior refuse marker for that SPKI. |
| `peer_refuse_bus` | Local refuse could not be written to the shared bus | Disk/`ocsp-refuse` write failed or generation id missing (`detail=`). Dir is provisioned off-handshake (warmer/job); sibling may still staple until fixed. |
| `await_sni` | Stream staple deferred: no SNI-bound leaf yet | Optional: skip staple (`skip_slot` / `detail=await_sni`). Must-Staple: `OCSP_STAPLE_MODE=normal` aborts; `staple_only`/`open` soft-continue unstapled (global mode when SNI is empty). |
| `intermediate_must_staple_libssl` | Intermediate has Must-Staple but **this** worker’s libssl lacks `SSL_set0_tlsext_status_ocsp_resp_ex` (no multi-staple) | Capability gap — not a missing shard. Upgrade libssl (upstream OpenSSL ≥ 3.6 or a build that exports the symbol), remove Must-Staple from the intermediate, or use `OCSP_STAPLE_MODE=staple_only`/`open` as a temporary fuse. Sticky on the peer-refuse bus until a new generation is canary-paged (or soft fuse). |
| `intermediate_must_staple_colony` | Intermediate has Must-Staple but the **colony min** is leaf-only (a live peer cannot multi-staple, e.g. OpenSSL 3.5 during rollout) | Fleet policy, not a local symbol miss. Every worker — including 3.6 — acts leaf-only until that peer’s vote expires (~120s after it leaves). Not written to the peer-refuse bus (must not stick past the mixed window). Softened by `OCSP_STAPLE_MODE`. |
| `validate_budget` | Soft ~700ms `ngx.ocsp.validate` budget expired during **leaf** issuer tries | Handshake never reached multi-staple attach — intermediates were not considered. Not `ok_partial` (that requires a successful attach with NULL slots). Canary-paged leaves skip validate entirely. No poison / no peer-refuse bus. Next handshake may succeed; reduce issuer fan-out or rely on canary page. Must-Staple softens via `OCSP_STAPLE_MODE`. |
| `unmet` | Must-Staple required and no more specific code | Catch-all—check `detail=` / prior lines; use `OCSP_STAPLE_MODE=staple_only`/`open` only as a temporary fuse. |

Handshake L1 (`TLS:SSL:ocsp:*` in `internalstore` / `internalstore_stream`) is **preloaded off the TLS critical path**: every worker arms an OCSP L1 warmer timer; a short shared-dict lease picks one scanner so disk is not walked N times. If the holder dies, another worker takes the lease (well under the 300s L1 shm TTL) and re-warms. The warmer skips (and drops) generations blocked by the peer-refuse bus or `serial-blacklist.json`, same as the handshake refuse gates. A cold miss can still read `ocsp.der` during `ssl_certificate`, but steady-state and post-publish handshakes should hit DRAM first.

When the scheduler canary has stamped `paged=true` for the exact DER (`der_sha256` ligand), the handshake **trusts that canary** and skips `ngx.ocsp.validate_ocsp_response` (openssl CLI and OpenResty FFI can disagree). CertID / leaf binding and `set_ocsp_status_resp` still run. DB restore always stamps `paged=false` (a peer's canary is not local proof) and runs restore coherence (epoch bump + refuse clear) so this node must re-page before canary trust resumes. Shard publish prefers Linux `renameat2(RENAME_EXCHANGE)` so the live SPKI directory never disappears mid-swap; other platforms fall back to move-aside + rename (brief ENOENT possible). When validate does run, HTTP and stream share a soft ~700ms total budget and at most 4 issuer candidates — that budget covers **leaf** issuer tries only; intermediates are loaded later from canary-paged shards (or NULL slots → `ok_partial`). Budget abort logs `staple_decision=validate_budget` (`detail=leaf_issuers_only`) and never attaches a partial stack under another name.

!!! warning "Dual-certificate (RSA + ECDSA): one leaf per handshake"
    NGINX / OpenSSL present **one** end-entity certificate per handshake. BunkerWeb installs **only the leaf this ClientHello will use**, then staples that leaf’s OCSP response (RFC 9846 §4.5.1.1: `status_request` on the matching `CertificateEntry`).

    Selection walks ClientHello `signature_algorithms` in preference order and builds the list of leaves this client can verify (curve-aware: `ecdsa_secp256r1_sha256` does not select a P-384 leaf). Must-Staple / staple-health probe runs in that order and **demotes a leaf whose issuer-linked path will fail intermediate Must-Staple** (`issuer_path_intermediate_ready`) — not leaf-shard readiness alone. If the preferred leaf’s shard is poisoned/`not_paged`/refused, or its path cannot satisfy intermediate Must-Staple (`intermediate_must_staple_libssl` / `_colony` / missing body), the next ClientHello-compatible leaf is tried (`OCSP_STAPLE_HEALTH_FALLBACK`). Skip-leaf path demotion does not write the peer-refuse bus (a sibling may still install). Legal `ok_partial` NULL slots (no intermediate Must-Staple) do not demote. A leaf the client did not advertise (e.g. ECDSA when the ClientHello is RSA-only) is never installed — that would break `CertificateVerify`. If nothing matches, prefer ECDSA, else the only leaf.

    Consequences:

    - The sibling key type is **not** offered on that connection once a leaf is chosen (logged as `staple_decision=skip_slot`).
    - A ClientHello that lists both RSA and ECDSA schemes cannot be forced into a Must-Staple outage solely by poisoning the first-preference shard while the other remains staplable.
    - Must-Staple is evaluated for the presented leaf, and for any intermediate that itself carries Must-Staple (multi-staple API present: missing body fails closed; API absent: `intermediate_must_staple_libssl`).
    - Stream still defers stapling until SNI has bound the handshake leaf (`await_sni` / `skip_slot detail=await_sni`).

    Use `OCSP_STAPLE_MODE=staple_only` or `open` only as a temporary recovery fuse if a Must-Staple probe fails — the fuse presents the chosen site leaf unstapled (after `clear_certs`) rather than falling back to the static `ssl_certificate`.

!!! tip "Intermediate OCSP (TLS 1.3 multi-staple)"
    When linked libssl exports **`SSL_set0_tlsext_status_ocsp_resp_ex`** (upstream OpenSSL **3.6+**; detected by symbol probe, not `version_num`), BunkerWeb attaches a `status_request` on each non-root `CertificateEntry`:

    - Workers each vote under `/var/cache/bunkerweb/ssl/.multi_staple_attach.d/<host-pid-wid>`; the aggregate `/var/cache/bunkerweb/ssl/.multi_staple_attach` is the **minimum across live workers** (`1` only when every live vote is `1`). Any leaf-only (e.g. OpenSSL 3.5) worker forces the fleet leaf-only until its marker expires (~120s without refresh) — **handshake attach and health** honor that min (not only `ocsp-refresh`), so a 3.6 worker does not multi-staple while a 3.5 peer is still live. Intermediate Must-Staple during that window logs `intermediate_must_staple_colony` (not sticky). Leaf-only libssl does not burn OCSP GETs/canaries for bodies it cannot put on the wire. Targets are the **issuer-linked path** from each leaf (plus any extra Must-Staple members still in the PEM), not every AIA-bearing block in a fat/dual-cert bundle.
    - At handshake, HTTP and stream **present** that same issuer-linked chain for the ClientHello-selected leaf (`set_cert` + OCSP attach). Off-path bag PEMs (cross-signs, unused extras) are dropped so their Must-Staple cannot fail-close a healthy leaf path — including after dual-cert health steers onto a sibling (`OCSP_STAPLE_HEALTH_FALLBACK`). If the leaf issuer DN cannot be resolved in the bag, presentation keeps only **non-Must-Staple** intermediates as chain hints (never restores full-bag concat of Must-Staple extras).
    - GOOD intermediate bodies are keyed by the intermediate SPKI (shared across tenants) — one successful fetch **donates** that plasmid for the rest of the job run (`ocsp_intermediate_plasmid_reuse`). Later leaves, and even the first leaf under `force_fetch` when the shared body is still above soft-refresh thresholds, clear only their tenant control key and **do not** re-hit the OCSP responder or swap the live shard directory under concurrent handshakes. Sticky refuse, serial-blacklist, nongood/tombstone, and cluster floor for intermediates use a **tenant control key** `sha256(leaf_spki || ':' || inter_spki)` so one site’s failure cannot brick every chain on that CA. Handshake loads the shared body but gates negatives on the control key.
    - The staple stack is leaf DER then each **presented** intermediate (NULL slot if that intermediate has no GOOD paged body). Missing intermediate status is legal; the audit line is `staple_decision=ok_partial` with `null_slots=` (not a hollow `ok`). An intermediate with Must-Staple and no usable staple fails closed.
    - When the symbol is **missing** on this worker (e.g. Alpine OpenSSL **3.5.x**), or the colony min is leaf-only because a peer still lacks it, only the leaf staple can be sent and intermediate refresh is skipped. If any **presented** intermediate itself carries Must-Staple, the handshake refuses with `staple_decision=intermediate_must_staple_libssl` (local) or `intermediate_must_staple_colony` (fleet) — softened by `OCSP_STAPLE_MODE` — the server never logs `OCSP_STAPLED` / `ok` for a leaf-only attach that TLS 1.3 clients enforcing intermediate Must-Staple would still reject.

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
