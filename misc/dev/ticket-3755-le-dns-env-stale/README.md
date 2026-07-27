# Ticket #3755: DNS-01 credentials invisible to `certbot-new` until AIO restart

Reproduction rig for <https://github.com/bunkerity/bunkerweb/issues/3755>.

A service created in the Web UI with an RFC2136 DNS-01 challenge saves its
`LETS_ENCRYPT_DNS_CREDENTIAL_ITEM*` values correctly, but `certbot-new` reports
`DNS challenge selected but no DNS credentials are configured, skipping generation.`
until the container is restarted.

## Root cause

`JobScheduler` rebound `os.environ` to a new dict on every reload. Jobs run in-process, and
`letsencrypt_utils.py` captures `environ` at import (`from os import environ`). Job helper
modules stay in `sys.modules` across reloads, so that captured reference froze on the
snapshot taken at container start, and `extract_provider()` iterated it. `certbot-new.py`
itself uses `getenv`, which is late-bound: that is why it found the new service but not its
credentials.

## What the rig contains

| Service | Role |
|---|---|
| `bunkerweb-all-in-one` | Built from `src/all-in-one/Dockerfile`; matches the reporter's integration, and puts the scheduler and the UI in one container so they share `/var/log/bunkerweb` |
| `bind9` (`10.30.55.53`) | Authoritative for `bwtest.lan`, accepts TSIG-signed RFC2136 dynamic updates |
| `pebble` (`10.30.55.14`) | Local ACME CA; `-dnsserver 10.30.55.53:53` makes its DNS-01 validation query our bind9 |
| `bw-db` | MariaDB |
| `app` | Upstream for the reverse proxy |

`setup.sh` generates a local CA plus a Pebble server certificate, and regenerates two patched
job files under `generated/`. BunkerWeb hardcodes the Let's Encrypt directory URLs with no
setting to override them, so pointing at a local ACME server means patching both
`letsencrypt_utils.py` (the directory constant, used for account bookkeeping) and
`certbot-new.py` (`certbot certonly` is invoked with no `--server` at all, so the constant
alone never reaches certbot). Each copy is regenerated from the repo on every run and the
script refuses to continue if it differs from its source by anything but the intended lines,
so the rig always exercises current code.

Only `app1.bwtest.lan` exists at container start, and it does not use Let's Encrypt. Every
DNS-01 service is created afterwards through the Web UI. That ordering is the whole point:
the bug only shows for configuration that arrives after the process started.

## Run

```bash
./setup.sh
docker compose build
docker compose up -d

# Services are created after the container is up, which is the whole point:
./create-service.py app2 dns           # RFC2136 DNS-01 with full credentials
./create-service.py app3 dns           # again later, to cover repeated reloads
./create-service.py app4 dns-nocreds   # misconfigured, for the UI-signal check
./create-service.py app2 delete
```

To reproduce the bug instead of the fix, add the overlay that restores the pre-fix
`JobScheduler`:

```bash
docker compose -f docker-compose.yml -f docker-compose.baseline.yml up -d
```

Web UI: <http://localhost:7355>, `admin` / `P@ssw0rd`. HTTPS is on `8443`, HTTP on `8355`, so reach a
service with `curl --resolve app2.bwtest.lan:8443:127.0.0.1 -k https://app2.bwtest.lan:8443/`.

### Credential items to enter (matching the reporter's)

Create service `app2.bwtest.lan` in Advanced mode with `AUTO_LETS_ENCRYPT=yes`,
`LETS_ENCRYPT_CHALLENGE=dns`, `LETS_ENCRYPT_DNS_PROVIDER=rfc2136`,
`LETS_ENCRYPT_DNS_PROPAGATION=10`, and:

```
LETS_ENCRYPT_DNS_CREDENTIAL_ITEM=server 10.30.55.53
LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_1=port 53
LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2=name bunkerweb-certbot.
LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_3=secret QrmNE3WJEYEMVtupVSWlznHxxTyIdR2I4LRiVPGWwpM=
LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_4=algorithm HMAC-SHA256
LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_5=sign_query false
LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64*=no
```

`server`, `port`, `name`, `secret`, `algorithm` and `sign_query` are accepted aliases of the
`dns_rfc2136_*` fields (`letsencrypt_providers.py`), so these are the reporter's exact values.

## Checks

All six were run and passed on 2026-07-27.

1. **Baseline reproduces the report** (with `docker-compose.baseline.yml`). After creating
   `app2` post-start:
   `[Service: app2.bwtest.lan] DNS challenge selected but no DNS credentials are configured, skipping generation.`
2. **Restart workaround** (still pre-fix). `docker compose restart bunkerweb-all-in-one`, no
   config change, and the same service issues a certificate. Together with check 1 this pins
   the cause on the environment snapshot, nothing else.
3. **Fixed: no restart needed.** `Certificate(s) for app2.bwtest.lan generated successfully.`
   in the container that was already running when the service was created. `docker compose
   logs bind9 | grep "updating zone"` shows the TSIG-signed add and delete of the
   `_acme-challenge` TXT, and `openssl s_client -connect 127.0.0.1:8443 -servername
   app2.bwtest.lan` reports `issuer=CN = Pebble Intermediate CA`.
4. **Multi-reload.** `app3` created after `app2` had already succeeded also issues with no
   restart, so `os.environ` identity holds past the first reload, not only once.
5. **Prune.** After deleting `app2`, the next `certbot-new` run processes only `app3` and
   `app4`. The old rebind dropped stale `{service}_*` keys for free; the fix does it
   explicitly.
6. **UI signal.** `app4` (DNS-01, no credentials) gives `bw_jobs_runs.success = 0` for
   `certbot-new`, a red cross on `/jobs`, while the healthy runs stay green. `/logs` lists
   `letsencrypt_certbot-new.log` and renders both the warning and
   `Skipped certificate generation for 1 service(s) with an invalid Let's Encrypt configuration: app4.bwtest.lan`.

## Teardown

```bash
docker compose down -v
```
