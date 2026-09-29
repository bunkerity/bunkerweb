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

!!! warning "Let's Encrypt has no OCSP responders"
    Let's Encrypt certificates do **not** advertise usable OCSP responders, so OCSP stapling cannot work with `LETS_ENCRYPT_SERVER=letsencrypt`. For OCSP-capable ACME certificates, set `LETS_ENCRYPT_SERVER=zerossl` (and ZeroSSL credentials as needed). Custom certificates from a CA that publishes OCSP in AIA also work when stapling is enabled.

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
| `SSL_USE_OCSP_STAPLING`       | `no`              | multisite | no       | **Use OCSP stapling:** When set to `yes`, staple a cached OCSP response during the TLS handshake for certificates that advertise an OCSP responder. Applies to HTTP and stream TLS (custom certs, ZeroSSL ACME, etc.). Let's Encrypt leaves have no OCSP responders — use `LETS_ENCRYPT_SERVER=zerossl` for ACME + OCSP. When `no`, Must-Staple is not enforced: certificates are served unstapled and `OCSP_STAPLE_MODE` is ignored. |
| `OCSP_STAPLE_MODE`            | `normal`          | multisite | no       | **OCSP staple mode:** Must-Staple fuse for HTTP and stream. `normal` refuses the handshake when Must-Staple is unmet and may drop the canary allow-pin (`refuse_cause` DROP_ALLOW); `staple_only` still probes before `set_cert` (skips unprobed Must-Staple leaves when another leaf can install) but if nothing remains, installs the site leaf **unstapled** and does not abort or revoke the pin; `open` disables Must-Staple enforcement (recovery) and also installs unstapled without revoking the pin. Only applies when `SSL_USE_OCSP_STAPLING=yes`; with `no` the effective mode is `open`. |

Handshake and the OCSP refresh job share a fixed **clock-skew budget** of 300 seconds (`OCSP_CLOCK_SKEW_SECONDS`). Death time is `nextUpdate` / `max_age_unix` **minus** that skew: staples stop being served before the CA's advertised expiry so a lagging worker clock cannot present a response the CA already considers dead.

### OCSP `staple_decision` runbook

Every staple outcome logs a closed **`staple_decision=CODE`**. That code **is** the section key below—grep the log token, open this section, follow the steps. Unknown detail strings normalize to `unmet` with `detail=` preserved. The closed set and aliases live in one place (`bunkerweb.ocsp`); HTTP and stream both format through it.

| `staple_decision` | Meaning | What to do |
| ----------------- | ------- | ---------- |
| `ok` | Staple set (or canary paged) | Healthy. Full multi-staple (every non-NULL stack entry has a body) also logs `ok` with `multi_entries` / `stapled_entries`. |
| `ok_partial` | Multi-staple attached with one or more NULL stack slots | Legal omission: that `CertificateEntry` has no `status_request`. Not a Must-Staple abort, and **not** a validate-budget miss (budget aborts never reach attach). Check `null_slots=` / `detail=null_slot_omission`; refresh the intermediate SPKI shard if you expected status on that cert. |
| `stapling_off` | Optional stapling disabled / unavailable | Expected when `SSL_USE_OCSP_STAPLING=no` or `ngx.ocsp` missing. Not a Must-Staple abort. |
| `skip_slot` | Dual-cert sibling deliberately not stapled | One OCSP slot per handshake; ECDSA preferred. Put Must-Staple on ECDSA only. |
| `cluster_floor` | Local CA `this_update_unix` behind colony floor | Wait for this node’s job to catch the floor. Floor is max-only on signed thisUpdate (not wall clock). Missing local timing is no opinion. Restore will not raise the floor above a fenced still-GOOD trio (avoids healthy files + closed Must-Staple). |
| `not_paged` | Shard on disk but canary never stamped `paged=true` | Missing `paged` is also not_paged. After **2** verified UNKNOWN answers the job soft-recalls (`paged=false`, bumps `soft_recall_gen`) while keeping DER until the **3rd** tombstones; a later verified GOOD must canary-page again. Soft-recall drops the allow-pin and rewrites `ocsp-ligand/{fp}` (before and after the unpage write). Generation identity is `der_sha256` **plus** `soft_recall_gen`. `not_paged` is KEEP_ALLOW (never revokes via DROP_ALLOW). Inspect `ocsp-refresh` canary / non-GOOD streak logs. |
| `aia_uri_mismatch` / `aia_uri_unpinned` / `aia_uri_missing_on_leaf` / `aia_uri_leaf_unavailable` | Staple not pinned to leaf AIA OCSP URI | HTTP and stream share `bunkerweb.ocsp.aia_uri_pin_ok`. Must-Staple requires a live leaf PEM to re-check AIA membership (`aia_uri_leaf_unavailable` when fingerprint-only). Re-run refresh; ensure the plugin returns leaf PEM (`status[3]`) for Must-Staple; check leaf AIA vs `ocsp.json` `aia_ocsp_uri`. |
| `ssl_use_ocsp_stapling_no` | Must-Staple leaf but stapling setting off | Not expected: with `SSL_USE_OCSP_STAPLING=no` Must-Staple is not enforced (effective `OCSP_STAPLE_MODE=open`) and the leaf is served unstapled. If seen, the setting flipped mid-handshake; set `SSL_USE_OCSP_STAPLING=yes` to staple. |
| `ngx_ocsp_unavailable` | `ngx.ocsp` / `set_ocsp_status_resp` missing | OpenResty build / load issue—fix ngx_http_lua / stream OCSP module. |
| `response_not_found` | No usable L1/disk GOOD staple | Check job fetch, shard path under `/var/cache/bunkerweb/ssl/`, serial blacklist. |
| `response_stale` | Past nextUpdate / max-age / skew death, or no death clock in meta | Wait for refresh or force `ocsp-refresh`. Handshake requires `expires_unix` and/or `max_age_unix`/`published_unix` in `ocsp.json` — L1 cached expiry may only shorten that clock, never substitute for missing meta. Missing both refuses the staple (fail-closed). |
| `serial_blacklisted` | Serial tombstoned after non-GOOD | Investigate CA revocation/UNKNOWN; clear only after a verified GOOD republish. Same serial clears on a strictly newer `thisUpdate`. A ban without `this_update_unix` is invalid and clears on any dated GOOD for that serial. DB restore keeps the ban when the restored body still matches; clears it when the restored GOOD supersedes (newer thisUpdate, different serial, or `serial_unknown` + serial). Restore sweeps preserve `serial-blacklist.json` / `nongood.json` (disk-local); coherence resets `nongood.json` on every GOOD trio restore. |
| `tombstoned` | Shard marked `tombstoned` in `ocsp.json` (revoked/unknown streak) | Job removed the GOOD staple; wait for a newer verified GOOD page. Mid-write: meta is the refuse signal before `.ocsp_epoch` / DER unlink finish. HTTP and stream both sample this flag (early refuse + L1 disk match). First verified non-GOOD below the tombstone threshold halves leftover GOOD `expires_unix` on disk **and** upserts that meta to the DB; restore prefers the shorter death clock for the same `der_sha256` (`ttl_halved_after_nongood`) so a longer stale row cannot undo the recall. |
| `shared_ligand` | Must-Staple body not bound to outside-shard `ocsp-ligand/{fp}` `der_sha256` (falls back to in-shard meta only while unpaged) | Epoch drift, torn promote, or missing ligand after canary—bump/`ocsp-refresh` so ligand matches body. Paged shards fail closed on ligand ENOENT. HTTP and stream both use `bunkerweb.ocsp.ligand_verdict` (single read + hardened merge). Logs may show `staple_decision=shared_ligand` while raw `refuse_cause=` / `detail=` is `ligand_missing`, `der_sha256_mismatch`, etc. — bus DROP/KEEP keys the **raw** string (`ligand_missing` and bare alias `shared_ligand` are KEEP_ALLOW so publish/upgrade ENOENT or aliased logging does not wipe the shared pin; sha/fingerprint mismatches DROP). HTTP and stream L1 disk coherence share `l1_body_matches_disk` (publish-gap keep only while outside ligand is `paged=true` **and** `ligand_effective_sha` names the cached binding — not after a full shard retract with a leftover ligand). |
| `certid_mismatch` | DER CertID ≠ leaf/issuer or meta pin | Refuse wrong leaf / ambiguous multi-match; re-fetch for this SPKI. Job accepts multi-`SingleResponse` bodies when exactly one entry matches leaf+issuer. Disk TTL skip also requires the cached response serial to match the current leaf (same-key renew / shared-key sites). |
| `set_staple_failed` / `set_staple_exception` | `set_ocsp_status_resp` failed | OpenResty/OpenSSL staple API error; check worker error log around the call. |
| `fingerprint_unavailable` | No SPKI / hint for the leaf | Ensure plugin returns PEM (`status[3]`) or fingerprint (`status[5]`). |
| `wrong_key_type_staple` | Staple body is wrong key type for chosen leaf | Dual-cert pin; do not borrow RSA↔ECDSA shards. |
| `probe_failed` | Must-Staple probe before `set_cert` failed | Same as unmet for that leaf—fix shard/canary before loading the cert. Soft fuse logs `action=continue_install` and loads the site leaf without a staple (avoids falling back to the static `ssl_certificate` after `clear_certs`). |
| `thisUpdate_future` / `thisUpdate_stale` / `lifetime_invalid` / `lifetime_too_long` / `thisUpdate_unreadable` | Intrinsic signed-window policy | CA window rejected; check `thisUpdate`/`nextUpdate`; do not force-page. |
| `canary_refused` | Scheduler canary refused page | Live shard unchanged; see `detail=` (`canary_openssl_verify`, …) and fix before page. |
| `peer_refuse` / `allow_pin_missing` / `allow_pin_mismatch` / `allow_pin_expired` / `allow_pin_claim_inflight` / `gen_type_drift` | Cross-zone allow-pin gate (HTTP↔stream) | Shared `ocsp-allow/{fp}` — **missing pin refuses Must-Staple** (inverted refuse bus). Only the scheduler canary (and the per-run restamp of live paged shards) writes the pin (`der_sha256` + `soft_recall_gen`, death at `expires_unix − skew`); write is compare-and-stamp (lagging canary must not clobber a newer `soft_recall_gen`). Handshake DROP_ALLOW causes compare-and-delete: unlink only when the pin still holds the refused generation; handshake never DROPs `soft_recall_gen=0` upgrade-grace pins (job `drop_allow_pin` / soft-recall cleanup still may). Mid-revoke claim litter: matching orphan claim is restored; otherwise `allow_pin_claim_inflight` (KEEP). Pin-state symptoms (`allow_pin_*`, `ligand_missing`, `gen_type_drift`) and clock-driven timing (`thisUpdate_*`, `lifetime_*`) are KEEP_ALLOW — a lagging or skewed worker must not erase a pin every zone shares. `soft_recall_gen` missing → `0` (upgrade grace); present but non-integer → `gen_type_drift` (local refuse). Soft fuse does not revoke. Soft-recall / tombstone / restore drop the pin; re-canary or restamp rewrites it. Logs keep runbook `staple_decision=`; bus policy keys raw `refuse_cause` before alias collapse. Legacy `ocsp-refuse/{fp}` is job-side cleanup only (handshake is read-only except compare-and-delete). |
| `peer_refuse_bus` | Allow-pin drop failed or kept (generation moved / gen-0 grace / EACCES) | See `action=` (`allow_kept_gen_moved`, `allow_kept_gen0_grace`, `allow_drop_eacces`, …). Dir is provisioned off-handshake (warmer/job). |
| `await_sni` | Stream staple deferred: no SNI-bound leaf yet | Optional: skip staple (`skip_slot` / `detail=await_sni`). Must-Staple: `OCSP_STAPLE_MODE=normal` aborts; `staple_only`/`open` soft-continue unstapled (global mode when SNI is empty). |
| `intermediate_must_staple_libssl` | Intermediate has Must-Staple but **this** worker’s libssl lacks `SSL_set0_tlsext_status_ocsp_resp_ex` (no multi-staple) | Capability gap — not a missing shard. Upgrade libssl (upstream OpenSSL ≥ 3.6 or a build that exports the symbol), remove Must-Staple from the intermediate, or use `OCSP_STAPLE_MODE=staple_only`/`open` as a temporary fuse. **KEEP_ALLOW** (aligned with colony — a single 3.5 worker must not DROP the fleet pin during mixed rollouts). Softened by `OCSP_STAPLE_MODE`. |
| `intermediate_must_staple_colony` | Intermediate has Must-Staple but the **colony min** is leaf-only (a live peer cannot multi-staple, e.g. OpenSSL 3.5 during rollout) | Fleet policy, not a local symbol miss. Every worker — including 3.6 — acts leaf-only until that peer’s vote expires (~120s after it leaves). KEEP_ALLOW (must not stick past the mixed window). Softened by `OCSP_STAPLE_MODE`. |
| `multi_staple_attach_failed` | Colony was multi-ready but OPENSSL_sk / `d2i` / `SSL_set0` / missing SSL pointer failed **and** the chain has intermediate Must-Staple | Do not treat as leaf `ok`. Attach clears the connection staple and refuses. Without intermediate Must-Staple, leaf-only fallback remains legal. KEEP_ALLOW. |
| `issuer_unresolved_must_staple` | Issuer DN in the bag did not resolve (or several PEMs share that DN with different SPKIs and no single paged staple) **and** Must-Staple intermediates were omitted from the presented chain | Those PEMs are not sent to the client. Attach and issuer-path health refuse leaf-only so a short chain is not treated as “no intermediate Must-Staple”. KEEP_ALLOW. |
| `fingerprint_chain_unavailable` | Must-Staple fingerprint-only path with no PEM chain (intermediate Must-Staple unprovable) | Pass fullchain PEM into `staple`/`probe`; status[5]-only Must-Staple is refused. Non-Must-Staple may still leaf-staple. KEEP_ALLOW. |
| `validate_budget` | Soft ~700ms `ngx.ocsp.validate` budget expired during **leaf** issuer tries | Handshake never reached multi-staple attach — intermediates were not considered. Not `ok_partial` (that requires a successful attach with NULL slots). Canary-paged leaves with a live allow-pin skip validate entirely. Budget miss **demotes local L1** to unverified (body kept for reuse) but **KEEP_ALLOW** (fleet pin stays) and stamps local `ocsp_ffi_needed` with `der_sha256|soft_recall_gen` so the **next** handshake on this worker **forces one FFI validate** (canary-skip cannot re-attach an unfinished body; soft-recall / re-page clears the latch by generation mismatch). Verified-L1 attach also consults the latch. No poison. Must-Staple softens via `OCSP_STAPLE_MODE`. |
| `issuer_unavailable` | OCSP body present but no accepted issuer PEM/SPKI for `ngx.ocsp.validate` | Distinct from `response_not_found` (missing DER). Check `issuer.pem` / chain bag; re-encodings of the same SPKI are deduped. KEEP_ALLOW. |
| `unmet` | Must-Staple required and no more specific code | Catch-all—check `detail=` / prior lines; use `OCSP_STAPLE_MODE=staple_only`/`open` only as a temporary fuse. |

Handshake L1 (`TLS:SSL:ocsp:*` in `internalstore` / `internalstore_stream`) is **preloaded off the TLS critical path**: every worker arms an OCSP L1 warmer timer (started flag only after the first `timer.at` succeeds so handshake re-arm can recover a failed schedule); a short shared-dict lease picks one scanner so disk is not walked N times. The holder heartbeats the lease mid-scan (and before enumeration), writes a resume cursor (`epoch|fp`) on mid-walk lease loss so the next holder continues MS-first mid-list, and only stamps the last-warm epoch after a **complete** pass (Must-Staple pcall failures also block completeness). `last_full` uses walk-start time so long scans do not stretch the 60s rescan. Bus dirs are re-provisioned on each lease claim. The warmer skips (and NOTICE-logs) generations blocked by allow-pin refuse or `serial-blacklist.json`. A cold miss can still read `ocsp.der` during `ssl_certificate`, but steady-state and post-publish handshakes should hit DRAM first.

!!! tip "HTTP handshake helpers (reviewer map)"
    These live in `ssl-certificate-by-lua.conf` (and `_M.current_ocsp_epoch` in `bunkerweb.ocsp`):

    | Helper / flag | Role |
    | ------------- | ---- |
    | `leaf_requires_must_staple(pem, fp)` | Tri-state Must-Staple (`true` / `false` / `nil`). Never invents `false` when resty and `ocsp.json` are both unavailable. |
    | `leaf_fail_closed_must_staple` | `~= false` — scopes module-miss / issuer_path demotion so non-MS leaves stay viable. |
    | `resolve_leaf(pem, hint)` | Picks end-entity SPKI (hint if non-issuer, else non-issuer block, else first). PATH B binds MS + allow-pin from this **before** peer / stapling-off / `ngx.ocsp`. |
    | `refuse_must_staple` | Logs runbook code; **`probe_only` never writes the allow-pin bus**; soft fuse never writes; normal may DROP_ALLOW. |
    | `ocsp_current_epoch` / `_M.current_ocsp_epoch` | One tokenizer for `.ocsp_epoch` (first-line `^%S+`) so HTTP and stream L1 cannot desync. |
    | `ocsp_l1_put(..., packed_epoch)` | Optional epoch from the L1 get that already matched disk; `probe_only` callers skip put. |
    | `certs_cleared` / `leaf_installed` / `leaf_must_staple` | Outside the top-level pcall so a throw after `clear_certs` / half-install aborts instead of falling through to nginx's static cert. `cleared_no_leaf` aborts when Must-Staple is required **or unknown** (`~= false`). |
    | `wipe_ssl_ctx` | Clears a half-installed leaf (`set_priv_key` / OCSP throw) and re-marks `certs_cleared`. |
    | PATH A open clear | Fingerprint path clears Must-Staple under `open` **before** peer refuse (aligned with PATH B). |

!!! tip "Stream `bunkerweb.ocsp` helpers (reviewer map)"
    | Helper | Role |
    | ------ | ---- |
    | `has_must_staple(pem)` | Tri-state TLS Feature parse (`true`/`false`/`nil`). Never collapses resty throw to `false`. |
    | `resolve_leaf_must_staple(pem, fp)` | TLS Feature → `ocsp.json` → unknown. Handshake uses `~= false` (fail closed). |
    | `cert_must_staple_bool(pem, fail_closed_unknown)` | Boolean for intermediate/bag filtering; unknown without meta → true when fail-closed. |
    | `attach_ocsp_staple` | Multi-staple attach. Stack/`set0`/missing SSL-pointer failure **refuses** when intermediate Must-Staple is present (`multi_staple_attach_failed`); leaf-only fallback only when no intermediate MS. `issuer_unresolved_must_staple` refuses when the presented chain omitted Must-Staple bag PEMs. After building the EX stack, asserts `OPENSSL_sk_num == #ders` or refuses. Intermediate Must-Staple detection uses one oracle (`cert_must_staple_bool`). Empty status cb is installed **once per SSL_CTX** (OpenSSL will not emit pre-set staples without a cb that returns OK; rebinding every handshake races the shared ctx). |
    | `clear_connection_staple` / `on_ssl_context_swap` | Clears SSL_ctrl 71 always; clears SSL_ctrl 143 when this connection noted multi (`bw_ocsp_multi_entries`) or local probe proved ctrl 143. Ctx notes wiped **only after** clear succeeds — failed EX clear keeps `had_multi` for retry. |
    | `colony_multi_staple_min` | Live MIN of worker votes. Handshake **does not** `os.remove` stale files (publish prunes votes **and** orphan `*.tmp.*`). A live vote that is neither `0` nor `1` is leaf-only. In-progress `*.tmp.*` names are skipped on read (publish renames into place). |
    | `multi_staple_worker_id` | Vote filename is `sha256(HOSTNAME)[1..16]-pid-wid` (crc32 fallback). Full hostname is hashed so a 64-char prefix cannot merge two pods. |
    | `pick_issuer_candidate` | Same subject DN, several PEMs: unique SPKI only. Distinct SPKIs under one DN → nil (no staplable-only tiebreak — paged DER is not issuer-path proof). |
    | `issuer_linked_chain_blocks` / `presentable_chain_blocks` | Issuer-linked presentation. `linked==0` stays leaf-only (no off-path non-MS bag PEMs). Omitting Must-Staple bag PEMs sets `unresolved_must_staple`. Depth-8 walk that still has a resolvable issuer stamps unresolved (no silent truncate). Depleted PEM export stamps `ngx.ctx.bw_ocsp_chain_unresolved_by_fp[leaf_spki]`. |
    | `load_paged_intermediate_staple` | Tenant `intermediate_control_fp` gates negatives. When `leaf_pem` is provided but control_fp cannot be derived, refuse the shared CA body (fail closed). |
    | `issuer_path_null_slots` | Ranks siblings by NULL-slot count. `unresolved_must_staple>0` (even on `#blocks<2`) and colony/libssl leaf-only **with** intermediate Must-Staple score sentinel `64`. Without intermediate Must-Staple, leaf-only still scores 0. |
    | `openssl_multi_staple_ready` / `refresh_multi_staple_vote` / `publish_multi_staple_attach` | Force-publishes on local XOR colony mismatch. Rate-limited path heartbeats vote mtime. Vote open/rename failure → not multi-ready (fail closed). Warmer clears latched `false` probe **and** `_ssl_ffi=false`. |
    | `certid_matches_handshake_leaf` | Serial plus issuer DN. Several DN matches must share one SPKI (`issuer_ambiguous` → certid mismatch). Not a full issuerKeyHash parse. `try_staple` returns `certid_mismatch` (DROP_ALLOW when Must-Staple and resp bytes are passed); optional stapling skips without abort. |
    | `staple_one_leaf` | Shared ligand is checked **before** `try_staple` attach so soft fuse cannot leave a mismatched DER on the SSL object. DROP causes pass the body into `must_staple_refuse`. |
    | `peer_refuse_blocks` | Unpaged / soft-recall revokes this generation and returns `not_paged` (callers that skip `shard_not_paged` still refuse). Missing pin tries orphan-claim reclaim; leftover claim → `allow_pin_claim_inflight`. KEEP_ALLOW. |
    | `warm_l1_from_disk` | Warms paged shards; Must-Staple first via ligand-merged meta (still-paged only; sort meta reused for warm). Mid-scan lease heartbeat; resume cursor `epoch|fp` on lease loss. Incomplete / MS pcall-fail → `complete=false`. Lease claim uses `dict.add`; renew verifies token post-set. Refuse/blacklist skips NOTICE-logged. |
    | `warm_cache(..., packed_epoch)` | Same packed-epoch rule as HTTP `ocsp_l1_put` — do not stamp "now" over a body that already matched disk. |
    | `staple_from_fingerprint(..., chain_blocks)` | Optional chain. Must-Staple without chain → `fingerprint_chain_unavailable`. `probe_only` runs the same `issuer_path_intermediate_ready` gate as PEM when blocks are present. |
    | `set_certs_from_pem` | Dual-cert install. Ranks healthy leaves by fewest `issuer_path_null_slots` then ClientHello order; seals returned blocks (`ocsp_path_sealed`) so `staple`/`probe` skip re-presentable; clears connection staple before `set_cert`; on `set_priv_key` fail runs `clear_certs` so a torn CertificateEntry cannot linger; soft-fuse (`open`/`staple_only`) installs the ranked survivor (not always `candidates[1]`). Rank probes set `bw_ocsp_skip_l1_drop` so sibling demotion cannot clear L1 for another leaf. Rearms L1 warmer. |
    | `record_peer_refuse` | Hard-gates `should_skip_peer_bus` first. Body-poison DROPs require resp bytes (probe `resp=nil` cannot CAS-delete via meta alone). Handshake DROP skips `soft_recall_gen=0` upgrade-grace pins. Bare `shared_ligand` alias and `intermediate_must_staple_libssl` are KEEP. Policy tables live in `ocsp_common`. |
    | `soften_must_staple` | Fuse: abort → `false, "must_staple", "abort"`; soft continue → `false, nil, "continue"`. Always logs raw `refuse_cause=` before alias collapse. Branch on the second return, not bare falsiness. Callers unpack `staple_from_fingerprint` into locals before soften (do not nest as a non-final arg). |

When the scheduler canary has stamped `paged=true` for the exact DER (`ocsp-ligand/{fp}` + in-shard `der_sha256`) **and** `ocsp-allow/{fp}` still names that `(der_sha256, soft_recall_gen)`, the handshake **trusts that canary** and skips `ngx.ocsp.validate_ocsp_response` (openssl CLI and OpenResty FFI can disagree). Ligand+paged alone is not enough — soft-fuse / pin revoke must re-open FFI validate. CertID / leaf binding and `set_ocsp_status_resp` still run. DB restore always stamps `paged=false` (a peer's canary is not local proof) and runs restore coherence (epoch bump + allow/ligand clear) so this node must re-page before canary trust resumes. Shard publish prefers Linux `renameat2(RENAME_EXCHANGE)` so the live SPKI directory never disappears mid-swap. When exchange is unavailable, files are promoted into the existing live directory with `ocsp.json` last; the **ligand lives outside the shard** so a torn trio cannot half-expose `der_sha256`. `.ocsp_epoch` advances only after the new live tree is visible. Each `ocsp-refresh` run also **restamps** ligand + allow for every other live paged shard that still passes local predicates (hash, freshness, CertStatus, intrinsic policy, serial ban) without a network fetch — that closes the upgrade window where allow-pin polarity fails closed while the TTL-skip path never republishes. When validate does run, HTTP and stream share a soft ~700ms total budget and at most 4 issuer candidates — that budget covers **leaf** issuer tries only; intermediates are loaded later from canary-paged shards (or NULL slots → `ok_partial`). Issuer candidates are deduped by **SPKI** (not PEM bytes). Budget abort logs `staple_decision=validate_budget` (`detail=leaf_issuers_only`), demotes local L1 verified→unverified (KEEP pin), stamps local `TLS:SSL:ocsp_ffi_needed:{fp}` as `der_sha256|soft_recall_gen` so the next handshake forces one FFI validate (verified-L1 shortcut included; latch dies on soft-recall gen flip), and never attaches a partial stack under another name. Empty issuer queues log `issuer_unavailable` (not `response_not_found`).

!!! note "Allow-pin + outside ligand (cross-zone bus)"
    HTTP and stream use separate `lua_shared_dict`s, so disk is the coherence bus:

    - **`ocsp-ligand/{fp}`** — `der_sha256` + `soft_recall_gen` + `paged` outside the SPKI dir. Both zones call `bunkerweb.ocsp.ligand_verdict` (one read, hardened merge). Paged shards fail closed on ligand ENOENT.
    - **`ocsp-allow/{fp}`** — missing pin refuses Must-Staple. Only canary/restamp writes (**compare-and-stamp**: refuse overwrite when on-disk `soft_recall_gen` is strictly newer). Handshake **compare-and-deletes** on DROP_ALLOW causes only when the pin still holds the refused generation — a lagging worker must not erase a newer pin; handshake never DROPs gen-0 upgrade-grace pins. Mid-revoke claim litter is reclaimed or refused as `allow_pin_claim_inflight` (KEEP). Pin-state and clock-driven causes are KEEP_ALLOW (local refuse, shared pin stays).
    - **DROP/KEEP policy** — `DROP_ALLOW_ON_REFUSE` / `KEEP_ALLOW_ON_REFUSE` / `META_ONLY_DROP_ALLOW` live in `ocsp_common.lua` (single source); `ocsp_pin.lua` applies prefix rules (`canary_*`, `shared_ligand_*`). Bus keys **raw** `refuse_cause=` — `format_staple_decision` always emits that field (even when `staple_decision=` collapses to a runbook alias).
    - **L1 coherence** — HTTP and stream share `bunkerweb.ocsp.l1_body_matches_disk` (ligand-gated publish-gap keep; paged+ENOENT / corrupt meta drop L1). L1 is **bw3** (`epoch|binding|soft_recall_gen|expires|DER`); legacy bw2 still unpacks but **cannot** be treated as crypto-verified (no gen). Soft-recall gen bumps therefore depotentiate verified trust without waiting for `.ocsp_epoch`. Publish-gap keep requires ligand `paged=true` **and** an explicit `soft_recall_gen` key (omitted gen ≠ upgrade-grace `0`).
    - **Generation** — `der_sha256` + `soft_recall_gen`. Soft-recall bumps the counter so the kept DER can be re-paged without a leftover pin re-matching. `generation_tuple` returns `(sha, nil)` on gen type drift (pin → `gen_type_drift` KEEP; never CAS on body alone).

!!! note "Intentionally not flipped (ADHD traps)"
    Do **not** "fix" these without a separate design pass: always/never validate on handshake (canary skip is the CLI↔FFI truce — skip still requires live allow-pin); split `ffi_paged` / force FFI always when `paged=true`; salt or mutate `der_sha256` while keeping the body; directory rename without `RENAME_EXCHANGE` (ENOENT window — use in-place promote + outside ligand); floor that never closes Must-Staple or quorum floor; serial ban cleared on soft-recall; HMAC on `paged` / signed colony votes; kill the intermediate plasmid / attach intermediates while colony is leaf-only; soft fuse as permanent per-scheme plane; forbid re-page of the same DER bytes (`soft_recall_gen` exists so the kept body can return); status-cb abort after staple queued; latch `.ocsp_epoch` for a whole handshake (must re-read mid-flight bumps); map unknown `OCSP_STAPLE_MODE` to soft-open; per-fingerprint epoch instead of global `.ocsp_epoch`; treat colony vote `nil` (no live markers) as hard-block multi (strands first worker if publish fails); delete crc32 worker-id fallback without guaranteeing digest; refuse every NULL slot whenever any intermediate is Must-Staple (legal non-MS omissions must remain); split http/stream colony vote dirs (changes fleet MIN semantics); always SSL_ctrl 143-clear on every swap regardless of prior multi note; re-probe ctrl 143 on every handshake (flaky probe flip under Must-Staple); AKI-only issuer walk (drop DN — breaks legacy intermediates without AKI); disk `.issuer_ambiguous.d` markers; warmer `mark_verified=true` without leaf PEM; treat soft-recall as Must-Staple warm priority (unpaged must drop); merge HTTP+stream warmer leases into one dict key; delete the `find` warmer fallback (no-lfs builds); crypto-validate every shard inside the warmer timer; refresh multi-staple votes only on the lease holder (leaf-only peers must still publish `0`); block warmer `complete` on intentional MS refuse/blacklist skips.

!!! warning "Dual-certificate (RSA + ECDSA): one leaf per handshake"
    NGINX / OpenSSL present **one** end-entity certificate per handshake. BunkerWeb installs **only the leaf this ClientHello will use**, then staples that leaf’s OCSP response (RFC 9846 §4.5.1.1: `status_request` on the matching `CertificateEntry`).

    Selection walks ClientHello `signature_algorithms` in preference order and builds the list of leaves this client can verify (curve-aware: `ecdsa_secp256r1_sha256` does not select a P-384 leaf). Must-Staple / staple-health probe runs in that order and **demotes a leaf whose issuer-linked path will fail intermediate Must-Staple** (`issuer_path_intermediate_ready`) — not leaf-shard readiness alone. Among remaining leaf-GOOD candidates, prefer the sibling whose path is **most completely stapled** (fewest intermediate NULL slots via `issuer_path_null_slots`) so ClientHello order does not stick on `ok_partial` when another leaf can fully multi-staple (`detail=path_completeness`). If the preferred leaf’s shard is poisoned/`not_paged`/refused, or its path cannot satisfy intermediate Must-Staple (`intermediate_must_staple_libssl` / `_colony` / missing body), the next ClientHello-compatible leaf is tried (`OCSP_STAPLE_HEALTH_FALLBACK`). **`probe_only` never writes the peer-refuse / allow-pin bus** — a demoted sibling must not DROP_ALLOW the leaf that may still install. Module miss / `issuer_path` pcall throw fail-closes only for Must-Staple or unknown leaves (`leaf_requires_must_staple`); non-MS leaves stay viable unstapled (`OCSP_MODULE_DEGRADED`). Legal `ok_partial` NULL slots (no intermediate Must-Staple) do not demote when they are the only healthy option. A leaf the client did not advertise (e.g. ECDSA when the ClientHello is RSA-only) is never installed — that would break `CertificateVerify`. If nothing matches, prefer ECDSA, else the only leaf.

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
