# Upgrading

!!! warning "Recreating the Web UI container without a persistent `/data` loses 2FA"
    `docker compose down` followed by `up` replaces the `bw-ui` container's filesystem, and the keys that decrypt every stored TOTP secret live there. Without a volume mounted on `/data`, the admin enrollment is dropped and every user has to enroll again. Check that your `bw-ui` service has one **before** upgrading — see [2FA is gone after recreating the container](web-ui.md).

## Upgrade from 1.6.X

### Breaking changes

!!! warning "`REDIS_SSL_VERIFY` now defaults to `yes`"

    The Redis/Valkey client used to accept **any** certificate when `REDIS_SSL` was enabled: the
    documented default for `REDIS_SSL_VERIFY` was `yes`, but the shipped default was `no`, so TLS
    was negotiated without ever verifying the server. The code now matches the documentation.

    This only affects you if **all** of the following are true: `REDIS_SSL: "yes"`, the Redis or
    Valkey server presents a self-signed or otherwise untrusted certificate, and you never set
    `REDIS_SSL_VERIFY` explicitly. In that case the connection now fails after the upgrade.

    Either trust the server's CA, or restore the previous behaviour explicitly:

    ```yaml
    REDIS_SSL_VERIFY: "no"
    ```

!!! warning "The job broker is now a separate instance from the WAF datastore"

    BunkerWeb uses Redis/Valkey for two unrelated jobs, and they need contradictory settings:

    | Role | Setting | Why |
    |------|---------|-----|
    | **Job broker** (`CELERY_BROKER_URL`) | `maxmemory-policy noeviction` | It holds the correctness leases that stop two workers pushing configs at once. They are keys *with* a TTL, so any `volatile-*` policy is free to drop them mid-flight. |
    | **WAF datastore** (`USE_REDIS` / `REDIS_*`) | `maxmemory-policy volatile-lru` *(recommended)* | Cap it and let it evict: transient counters are cheaper to lose than writes are to refuse. Nothing forces this — an uncapped Redis never evicts and is fine — but it is the shape a datastore is usually given, and it is the one the broker must not have. |

    `maxmemory-policy` is a per-server setting, never per-database, so one instance cannot do
    both — pointing the two roles at different database numbers on the same server does not
    separate them. The multi-container stacks run a dedicated `bw-jobs-broker`; the AIO image
    supervises a separate loopback broker on port `6380`, and the Linux installer can provision
    a `bunkerweb-broker` service starting at port `6380`.

    **If you upgrade with the installer, this is handled for you.** It provisions the broker,
    writes `CELERY_BROKER_URL` into `/etc/bunkerweb/variables.env`, and leaves an untouched
    distro Redis alone (with no `maxmemory` set, nothing ever evicts, so it was never broken).

    **If you upgrade with plain `apt`/`dnf` and you set a Redis password by hand**, you are
    affected and background jobs are already failing — silently. The worker and the API default
    to an unauthenticated `redis://127.0.0.1:6379/0`, so a password-protected server answers
    `NOAUTH`: `POST /jobs/dispatch` returns 502 and the worker stays `active` while consuming
    nothing. There is no certificate renewal, no blocklist refresh and no backup in that state.
    Check for it with:

    ```bash
    journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'
    ```

    The same diagnostic, for containers as well, is in
    [Background jobs never run](troubleshooting.md#background-jobs).

    **Check that this is a dedicated, non-evicting job broker before fixing authentication.**
    If port `6379` serves an evicting WAF datastore, provision a separate broker with the
    [Linux installer](integrations.md#easy-installation-script) or configure one yourself with
    `maxmemory-policy noeviction`. Use that broker's actual address and port. The `6379` example
    below applies only to a dedicated distro Redis configured for jobs; adding a password to an
    evicting datastore does not make it a safe broker.

    Then give the broker its own credentials in `/etc/bunkerweb/variables.env` — one
    write covers both components, because the worker and the API both read that file before
    their own:

    ```bash
    CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0
    ```

    ```bash
    systemctl restart bunkerweb-worker bunkerweb-api
    ```

    TLS is supported with the `rediss://` scheme. **Set `ssl_cert_reqs` explicitly** — a bare
    `rediss://` URL negotiates TLS without verifying the server's certificate:

    ```bash
    CELERY_BROKER_URL=rediss://:<password>@broker.example.com:6379/0?ssl_cert_reqs=required
    ```

!!! warning "The Celery worker was not enabled on some installs"

    `bunkerweb-worker` executes every job the scheduler dispatches. On installs where the
    installer deferred service startup — `--redis`, an external database, CrowdSec, custom DNS
    resolvers, and every `--manager` install — it was never enabled, so the stack came up
    healthy and ran no background jobs at all. The installer now enables it alongside the
    scheduler on those paths. Verify after upgrading:

    ```bash
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    ```

    If it is missing or idle, see
    [Background jobs never run](troubleshooting.md#background-jobs).

!!! warning "The Docker, autoconf and Kubernetes stacks need three new components"

    A 1.6 stack carries `bunkerweb` and `bw-scheduler`. 1.7 also needs an **API**, a **Worker** and
    a **job broker**: `bw-api`, `bw-worker` and `bw-jobs-broker` in the Compose stacks,
    `bunkerweb-api`, `bunkerweb-worker` and `bunkerweb-jobs-broker` in the Kubernetes ones. The
    Worker executes every job the Scheduler used to run in-process, and the broker carries the
    dispatch between them. Every BunkerWeb component is given `API_URL`, `API_TOKEN` and
    `CELERY_BROKER_URL`, and the `bunkerweb` instance gains a `bw-instance-data` volume on `/data`.

    Bumping the image tags alone leaves a stack that reports healthy and runs **no background job at
    all** — no certificate renewal, no blocklist refresh, no backup
    ([how to spot it](troubleshooting.md#background-jobs)). Redeploy from the 1.7 reference
    stack for your integration rather than editing the old one:
    [Docker](integrations.md#docker), [Docker autoconf](integrations.md#docker-autoconf),
    [Kubernetes](integrations.md#kubernetes) or [Swarm](integrations.md#swarm). Every stack is kept
    in the repository under
    [`misc/integrations`](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/misc/integrations),
    one file per database engine.

    **The All-In-One image is not affected**: it supervises the API and the Worker inside the single
    container and brokers their jobs through a dedicated embedded Redis, so replacing the container —
    keeping `/data` — is the whole upgrade, with nothing to add to it.

!!! danger "A location value carrying whitespace, `;`, `{` or `}` is now refused — and falls back to `/`"

    `REVERSE_PROXY_URL`, `GRPC_URL` and `REDIRECT_FROM` accepted any value in 1.6. They now reject
    the characters that would let a value break out of the `location` block it is rendered into. One
    leading `~ `, `~* `, `^~ ` or `= ` is still accepted — that is the NGINX location modifier — but
    that one space is the only whitespace allowed anywhere in the value, trailing included, and
    `;`, `{` and `}` never are.

    A refused value does not fail the render. BunkerWeb logs a warning
    (`Ignoring variable REVERSE_PROXY_URL_1 : ...`) and the setting keeps its default, which is `/`
    for all three — so the rule moves to the site root instead of the path you configured. The
    common case is a regex location using a quantifier, `^/v[0-9]{1,3}/`.

    Find yours before upgrading, in whichever files you set them — Compose files, `variables.env`,
    container labels, Kubernetes annotations:

    ```bash
    grep -rInE '(REVERSE_PROXY_URL|GRPC_URL|REDIRECT_FROM)[A-Z_0-9]*[:=].*[;{}]' .
    ```

    That finds the `;`, `{` and `}` values, which is where a 1.6 configuration realistically trips.
    A value carrying a space is refused as well, unless that space is the one separating a leading
    `~`, `~*`, `^~` or `=` from the path — read those few by eye.

    The grep is file-scoped on purpose, and that leaves a blind spot worth knowing about. A value
    set through the web UI or the API lives in the database, and a stored value is re-validated
    neither when the configuration is rendered nor when an unrelated setting is saved — so it keeps
    working across the upgrade and **nothing will tell you**. Three things behave differently once
    you do touch that service:

    - **A JSON settings payload is validated whole.** `POST`/`PATCH /services` and
      `PATCH /global_settings` check **every** key you send, changed or not — so a
      read-modify-write that merely resubmits the stored value is refused with `400` naming the
      key. Keys are unprefixed on those routes: `REVERSE_PROXY_URL_1`, not
      `www.example.com_REVERSE_PROXY_URL_1`. (On `MULTISITE=no` these three settings are global,
      so `PATCH /global_settings` is the one that bites.)
    - **Everything that saves the whole configuration compares against what is stored in the
      database and skips unchanged keys** — the web UI's service and global-settings pages,
      autoconf, the scheduler's environment reconcile, `PUT /global_settings/config`. A stored
      value you leave alone is never looked at, on the UI page included: opening the service
      page and saving it will **not** surface the problem. (A value that comes from a *label*
      or from `variables.env` is a different case: autoconf and the Configurator re-read their
      own source in full every run, so an illegal one there is dropped with a log line and the
      setting falls back to its default — which is why the grep above matters.)
    - **When the UI does look at it** — because you edited that field — it does not refuse the
      save. It reverts that one field to its stored value, flashes `Variable <key> is not
      valid.`, saves the rest, and now reports the save itself with a matching orange flash naming
      how many values were refused, instead of an unconditional success flash.

    None of this finds a stored value for you. Audit `REVERSE_PROXY_URL`, `GRPC_URL` and
    `REDIRECT_FROM` on your UI-managed services by eye.

!!! warning "`GET /bans` answers from the database now"

    Bans are stored in the database in 1.7 and survive a restart, so `GET /bans` on the control
    plane returns that durable list. What it returned before — what each instance is enforcing
    in its own shared memory right now — moved verbatim to `GET /bans/instances`. Nothing errors
    if you leave a 1.6 automation pointed at `GET /bans`; its answer just means something else.
    Repoint it deliberately.

!!! info "`HTTP_PORT` and `HTTPS_PORT` are per-service settings now"

    They moved from the `global` context to `multisite`, so `www.example.com_HTTPS_PORT=9443` is
    accepted where 1.6 refused it with "context of ... isn't multisite". An existing configuration
    renders unchanged: a global value still means "the default of every service". What is new is
    that a service may declare its own list — and that list **replaces** the global one for that
    service rather than adding to it.

!!! warning "Swarm: `NAMESPACES` now filters custom configs too"

    Before 1.7, `NAMESPACES` filtered the Swarm controller's event path and its service discovery
    but **not** its config discovery: a global `docker config` object was collected by every
    autoconf on the daemon, whatever namespace it belonged to. 1.7 applies the filter to configs as
    well, which is what the Docker integration has always done. If you set `NAMESPACES` and your
    config objects carry no `bunkerweb.NAMESPACE` label, those configs **stop being applied after
    the upgrade, with no error** — a custom snippet that carried an allow/deny block simply
    disappears from the generated configuration.

    Label every config object you expect to be applied. Swarm configs are immutable — `docker
    config` has no `update` verb — so each one must be recreated under a new name and re-pointed
    with `docker service update --config-rm/--config-add`. Find the objects this affects before you
    upgrade with:

    ```bash
    docker config ls -q | xargs -r docker config inspect --format '{{.Spec.Name}} {{.Spec.Labels}}'
    ```

!!! info "Docker Swarm is supported again in 1.7"

    The Swarm integration was marked deprecated in 1.6 and is supported again in 1.7. The stack
    published for 1.6 does **not** boot on 1.7: it carries no `bw-api` and no `bw-worker`, so
    `bw-autoconf` waits forever for an API that is never started and no background job ever runs.
    Redeploy from the [1.7 reference stack](integrations.md#swarm) rather than editing the old one,
    and note the three new requirements it carries: a `bw-state=true` node label for the services
    that own volumes, `mode: global` on the `bunkerweb` service, and `mode: host` port publishing.

### Switching an older AIO job broker {#aio-broker-upgrade}

This applies to an **existing 1.7 AIO deployment**, not to a 1.6 installation, which had no Celery job queue. Earlier 1.7 images inferred the broker from `REDIS_*`. The default is now `redis://127.0.0.1:6380/0`, backed by a separate Redis with `noeviction` and AOF persistence in `/data/broker`. The WAF datastore keeps its own settings and files.

If you already set `CELERY_BROKER_URL` explicitly, that value is preserved. If you relied on `REDIS_HOST`, `REDIS_PASSWORD` or the Redis TLS settings to choose the broker, those now affect only the WAF datastore. To retain an external job broker, set its complete `CELERY_BROKER_URL` explicitly, including credentials and TLS verification parameters. An empty value is rejected when the Worker is enabled.

Before switching the broker of a running 1.7 deployment:

1. Stop direct API writers, including automation and other operators. Use the existing [backup quiescence procedure](#rolling-back-to-1614) to hold scheduler dispatch, autoconf and UI writes and wait for queued jobs, in-flight work and pending reload acknowledgements to drain. Only take the hold; do not run the downgrade steps. The target is a label for the hold, not a migration request.
2. Run that quiescence command against the **old** broker and API. On older AIO images a new shell does not inherit the URL exported by the entrypoint: provide the actual old `CELERY_BROKER_URL` and API credentials to that shell. If the hold is not observed by the API, or the drain times out, stop and resolve it before switching.
3. Keep the hold active until the old container is stopped. Recreate the container with the same `/data` volume and the new default, or your explicit external broker URL. No queue keys are copied between brokers and the old WAF Redis data is not deleted.
4. Check container health and verify that a dispatched job completes on the Jobs page before resuming API automation. A stale hold on an old external broker can be released through the existing quiescence command, or left to expire.

The new broker starts before the Worker and stops after it. Its AOF survives a container restart when `/data` is retained; persistence does not move jobs left on an old broker.

### After the upgrade

None of the following blocks the upgrade or needs action to complete it, but each one changes what
you see once 1.7 is running.

!!! info "A reserved `default-server` service appears in multisite installs"

    With `MULTISITE=yes`, the block that answers requests matching no configured service — an
    unknown hostname, a raw IP address, a `Host` nobody serves — is now a permanent reserved service
    row. It shows up in the web UI's service list and in `GET /services` flagged `reserved: true`,
    it cannot be deleted, renamed or drafted, and it is never counted against the PRO service quota.
    Configuring it is the point: it now has a certificate, TLS settings, response headers and error
    pages of its own. See [the API reference](api.md#api-surface-capability-map) and
    [the web UI page](web-ui.md#the-default-server-entry).

    With `MULTISITE=no` nothing is seeded, the row does not exist, and the default server renders
    exactly as it did in 1.6.

!!! info "Instance enrollment is available, and optional"

    An instance can now mint its own control-plane credential by redeeming a single-use,
    time-limited code, instead of sharing the global `API_TOKEN`. Nothing changes until you enrol
    one: an instance that is not enrolled keeps using `API_TOKEN` exactly as it did in 1.6. Once
    enrolled it answers only to its own credential and never falls back — and an in-place downgrade
    destroys stored credentials. Return the instance to the shared `API_TOKEN` before rolling
    back, or re-register it afterward. See
    [Instance enrollment](web-ui.md#instance-enrollment), and
    [An enrolled instance refuses to start](troubleshooting.md#lost-instance-credential) for the one
    way it bites: an enrolled instance whose credential file has been lost while the rest of its
    state survived refuses to boot until you re-enrol it.

!!! info "`REDIS_KEEPALIVE_POOL` now defaults to 64 (was 10)"

    `REDIS_KEEPALIVE_POOL` is per NGINX worker, so steady-state connections are roughly
    `WORKER_PROCESSES x REDIS_KEEPALIVE_POOL x instances`; it also caps the API rate limiter's own
    Redis pool. An explicit value you already set is unaffected — check that your Redis/Valkey
    `maxclients` sits above that count before upgrading a large fleet.

!!! info "New in 1.7 and worth a look once you are running"

    - **Composite AND rules** on the three access lists: `BLACKLIST_RULE_1`, `GREYLIST_RULE_1`,
      `WHITELIST_RULE_1` and their siblings match only when every term matches
      (`country:FR AND NOT ua:GoodBot`).
    - **A dedicated GeoIP plugin.** Nothing to configure: the country and ASN databases still come
      from the free DB-IP Lite editions. A MaxMind subscription (`MAXMIND_LICENSE_KEY`,
      `MAXMIND_ACCOUNT_ID`), a city database (`GEOIP_CITY`) and your own `.mmdb` files are the
      new options. See [GeoIP](features.md#geoip).
    - **`BACKUP_ROTATION_STRATEGY`**, which decides *which* backups a rotation keeps rather than how
      many. It defaults to `hanoi`, which buys older restore points by thinning the recent window;
      set it to `fifo` to keep the 1.6 selection. `BACKUP_ROTATION` is unchanged.
    - **Several templates per service**: `USE_TEMPLATE` is an ordered, space-separated list, applied
      in order, a later template overriding an earlier one.
    - **A server-translated web UI** with a language selector. See
      [Translations](web-ui.md#translations-i18n).

### Rolling back to 1.6.14

A rollback is not the reverse of an upgrade. Two paths exist, and BunkerWeb tells you which one applies to your installation rather than letting you guess.

**Restore from backup** works everywhere and is the supported path. It replays a backup taken *before* the upgrade over an emptied database, so everything written since the upgrade is lost. See [Rollback](#rollback) below for the manual procedure per database engine.

**In-place downgrade** is offered only for version/engine pairs that have been measured lossless, and only back to the immediately preceding release. For 1.7.0 that means 1.6.14, on **SQLite and PostgreSQL only**. On MariaDB and MySQL the 1.7 migration cannot be replayed backwards — it aborts partway and leaves a schema that is neither version — so those installations must restore from a backup.

Three commands, in this order:

```bash
# 1. Can this installation go back? Read-only: it creates no database and writes nothing.
bwcli plugin backup preflight 1.6.14

# 2. Hold the writers still. Stays in the foreground until you press Ctrl-C.
bwcli plugin backup quiesce 1.6.14

# 3. In a second shell, while step 2 is still holding:
bwcli plugin backup downgrade 1.6.14            # reports; changes nothing
bwcli plugin backup downgrade 1.6.14 --execute  # asks for confirmation, then migrates
```

Step 3 refuses unless the hold from step 2 is in place for that same version, the preflight it re-runs itself comes back clean, and the compatibility manifest marks the pair as tested. It then takes its own backup immediately before migrating and restores it if anything goes wrong.

Before starting, stop or firewall anything that writes to the API directly. The hold makes the API *report* the fleet read-only, which is what the scheduler, autoconf and the UI act on; it does not block a write made straight to the API by a token holder.

!!! danger "What an in-place downgrade destroys"
    Every centrally stored certificate, every attachable resource (redirects, upstream pools, workflows, resource groups), all request metrics and the threat map, every registered passkey, and every stored instance credential — enrolled instances must be re-registered against the global `API_TOKEN` afterwards. Per-user UI preferences survive but lose their meaning: 1.6.14 reads them all as per-table column layouts. Bans are the one soft loss: the `sync-bans` job relearns them from the instances, losing only their remaining durations.

    The preflight counts what your installation actually holds and refuses an in-place downgrade while anything irreplaceable is still there, so the answer you get is about your data rather than about the release in the abstract.

**Outside the database.** Job caches and PRO plugins are rebuilt on the next run. Custom configs, `www` content, Let's Encrypt state and backup archives are unchanged between the two versions. External plugins that need a 1.7 API are unusable on 1.6.14 and must be removed or downgraded too.

### Procedure

=== "Docker"

    === "Easy upgrade using the install script"

        The same script used for fresh Docker installs also upgrades a stack it
        generated. Run it from the directory holding your `docker-compose.yml`
        and `.env` (or point it there with `--compose-dir`):

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

        # Download the script and its checksum
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # Verify the checksum
        sha256sum -c install-bunkerweb.sh.sha256

        # If the check is successful, run the script
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh --docker --compose-dir /path/to/your/stack
        ```

        !!! danger "Security Notice"
            **Always verify the integrity of the installation script before running it.**

            Download the checksum file and use a tool like `sha256sum` to confirm the script has not been altered or tampered with.

            If the checksum verification fails, **do not execute the script**—it may be unsafe.

        !!! warning "Only for stacks created by this script"
            The upgrade path recognises a stack by the `generated by install-bunkerweb.sh`
            header in its `.env` file. A hand-written `docker-compose.yml`, an
            All-In-One container, or a Swarm/Kubernetes deployment is not upgraded
            by the script — use the **Manual** tab for those.

        * **How it works**:

            1. Detection
                * Reads the install type (full, manager, worker, scheduler, ui, api) back from `.env`, so you never have to restate your topology.
                * Recovers the secrets, host ports, worker list and Compose project name from `.env`, so an upgrade cannot rotate the database password, invalidate stored 2FA secrets, or move your published ports.
                * Reads the version actually running from the container rather than trusting the image tag, so a floating tag (`latest`, `testing`) and an interrupted previous upgrade are both detected correctly.
            2. Upgrade decision
                * Same version already running: prints the stack status and exits.
                * Older target version: **refuses**. The installer has no downgrade automation of its own, and starting the scheduler against an older package with an already-migrated database fails and restarts in a loop. See [Rolling back to 1.6.14](#rolling-back-to-1614) to bring the database back first, then re-run the installer at the older version.
                * Otherwise: asks for confirmation (or proceeds directly with `-y`).
            3. Pre-upgrade backup
                * Runs `bwcli plugin backup save` inside the scheduler container and copies the archive to the host.
                * Destination: `--backup-dir`, or a generated path like `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
                * Aborts the upgrade if the backup fails, unless you pass `--no-auto-backup`.
                * Skipped for `worker`, `ui` and `api` stacks, which own no database.
            4. File updates
                * `.env` is rewritten with the new image tag; any entry you added by hand is carried over.
                * `docker-compose.yml` is regenerated only when it still matches what the script produced, so local edits survive. Pass `--overwrite-compose` to regenerate it anyway. A `.bak.<timestamp>` copy is kept either way.
            5. Apply and verify
                * `docker compose pull`, then `docker compose up -d` — only the containers whose image changed are recreated, so downtime is shorter than a full `down`/`up` cycle.
                * If the pull fails nothing is recreated, the previous tag is restored in `.env`, and the running stack is left untouched.
                * Afterwards the script re-reads the version from the container and checks that the scheduler did not enter a restart loop, which is how a failed database migration shows up.

        * **Useful flags**:

            | Flag                    | Effect                                                                |
            | ----------------------- | --------------------------------------------------------------------- |
            | `--compose-dir PATH`    | Directory holding the stack (default: current directory)              |
            | `-v, --version VERSION` | Target version; the image tag is derived from it                      |
            | `--image-tag TAG`       | Target image tag directly, instead of deriving it                     |
            | `--backup-dir PATH`     | Where to store the pre-upgrade backup                                 |
            | `--no-auto-backup`      | Skip the automatic backup (manual backup becomes your responsibility) |
            | `--overwrite-compose`   | Regenerate `docker-compose.yml` even if it was edited locally         |
            | `--force-type-change`   | Allow the stack to change topology (destructive)                      |
            | `--no-pull`             | Do not pull images before recreating the stack                        |
            | `-y, --yes`             | Unattended run; piped invocations without it exit with an error       |

    === "Manual"

        1. **Backup the database**:

            - Before proceeding with the database upgrade, ensure that you perform a complete backup of the current state of the database.
            - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        2. **Upgrade BunkerWeb**:
            - Upgrade BunkerWeb to the latest version.
                1. **Update the Docker Compose file**: a tag bump is not enough coming from 1.6. The
                   stack also needs the `bw-api`, `bw-worker` and `bw-jobs-broker` services, the
                   `API_URL`, `API_TOKEN` and `CELERY_BROKER_URL` variables on every component, and
                   a `bw-instance-data` volume on the `bunkerweb` service — see
                   [The Docker, autoconf and Kubernetes stacks need three new components](#breaking-changes)
                   above. Rebuild your `docker-compose.yml` from the 1.7 reference stack for your
                   integration ([Docker](integrations.md#docker),
                   [Docker autoconf](integrations.md#docker-autoconf)), carrying over your own
                   settings, volumes and published ports rather than editing the 1.6 file service by
                   service.

                2. **Restart the containers**: Restart the containers to apply the changes.
                    ```bash
                    docker compose down
                    docker compose up -d
                    ```

        3. **Check the logs**: Check the logs of the scheduler service to ensure that the migration was successful.

            ```bash
            docker compose logs <scheduler_container>
            ```

        4. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database container.

=== "All-In-One (AIO)"

    The [All-In-One image](integrations.md#all-in-one-aio-image) bundles BunkerWeb, the Scheduler, the Web UI and (optionally) the API, Redis and CrowdSec in a **single container** named `bunkerweb-aio` by default. All persistent state — the SQLite database, cache, custom configs, plugins, backups, and the Redis/CrowdSec data — lives in the `/data` volume, so upgrading is a matter of replacing the container while keeping that volume.

    1. **Prerequisites**:

        - Note the image tag you are currently running and the name of the `/data` volume (or bind mount) so you reuse the exact same one after the upgrade.

        !!! warning "Preserve the `/data` volume"
            **Never remove the `/data` volume during an upgrade.** It holds the database, the embedded Redis and CrowdSec state, your custom configs and your backups. Replacing the container is safe; deleting the volume is not.

        !!! tip "External database backends"
            If you run the AIO with an external database (`DATABASE_URI` pointing at MySQL/MariaDB/PostgreSQL), the SQLite file under `/data` is not used — make sure you back up that external database with your usual tooling as well.

    2. **Backup the database**:

        - Before proceeding with the database upgrade, ensure that you perform a complete backup of the current state of the database. The Scheduler runs inside the `bunkerweb-aio` container, so the backup command is executed there directly.

        ```bash
        docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory bunkerweb-aio bwcli plugin backup save
        ```

        ```bash
        docker cp bunkerweb-aio:/path/to/backup/directory /path/to/backup/directory
        ```

    3. **Upgrade BunkerWeb**:

        === "docker run"

            3. **Stop and remove the current container** (the `/data` volume is kept):
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4. **Pull the new image**:
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

            5. **Re-create the container** with the same options, reusing the same `/data` volume, ports and environment variables as before:
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

        === "Docker Compose"

            6. **Update the Docker Compose file**: Update the Docker Compose file to use the new version of the All-In-One image.
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:1.7.0-beta
                        ...
                ```

            7. **Restart the container**: Restart the container to apply the changes. The `/data` volume is reattached automatically.
                ```bash
                docker compose down
                docker compose up -d
                ```

    4. **Check the logs**: Check the container logs to ensure that the migration performed by the embedded Scheduler was successful.

        ```bash
        docker logs bunkerweb-aio
        ```

    5. **Verify the upgrade**:
        - Confirm the container is running and healthy:
            ```bash
            docker ps --filter name=bunkerweb-aio
            ```
            The `STATUS` column should report `(healthy)` once the start-up checks pass.
        - Confirm the running version:
            ```bash
            docker exec bunkerweb-aio cat /usr/share/bunkerweb/VERSION
            ```
            The version can also be checked from the Web UI under *Support*.
        - Verify that your services, settings and custom configurations are intact in the Web UI, and that your sites are still served over HTTP/HTTPS.

=== "Linux"

    === "Easy upgrade using the install script"

        * **Quick start**:

            To get started, download the installation script and its checksum, then verify the script's integrity before running it.

            ```bash
            LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

            # Download the script and its checksum
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

            # Verify the checksum
            sha256sum -c install-bunkerweb.sh.sha256

            # If the check is successful, run the script
            chmod +x install-bunkerweb.sh
            sudo ./install-bunkerweb.sh
            ```

            !!! danger "Security Notice"
                **Always verify the integrity of the installation script before running it.**

                Download the checksum file and use a tool like `sha256sum` to confirm the script has not been altered or tampered with.

                If the checksum verification fails, **do not execute the script**—it may be unsafe.

        !!! tip "Interactive upgrade UI"
            The upgrade flow uses the same TUI as fresh installs: arrow-key inline prompts via [gum](https://github.com/charmbracelet/gum), with `whiptail` boxed-dialog and plain-text fallbacks if gum cannot be obtained. The `gum` binary is fetched from the official [GitHub release](https://github.com/charmbracelet/gum/releases) (SHA256-pinned, cosign-verified when cosign is installed) and runs from a tempdir that is removed on exit — no system package is installed and no apt/dnf source is added. Pass `--no-tui` (or set `BW_INSTALL_TUI=no`) to skip every TUI tier, or `--tui` to require a working TUI. For fully unattended upgrades pass `-y` / `--yes` with the relevant flags — piped invocations (`curl … | bash`) exit with a clear error instead of silently accepting every default. **Air-gapped upgrades**: combine `--no-tui --yes` so no network call is made for the TUI layer.

        * **How it works**:

            The same multi‑purpose install script used for fresh installs can also perform an in‑place upgrade. When it detects an existing installation and a different target version, it switches to upgrade mode and applies the following workflow:

            1. Detection & validation
                * Detects OS / version and confirms support matrix.
                * Reads currently installed BunkerWeb version from `/usr/share/bunkerweb/VERSION`.
            2. Upgrade scenario decision
                * If the requested version equals the installed one it aborts (unless you explicitly re-run for status).
                * If versions differ it flags an upgrade.
            3. (Optional) Automatic pre‑upgrade backup
                * If `bwcli` and the scheduler are available and auto‑backup is enabled, it creates a backup via the built‑in backup plugin.
                * Destination: either the directory you supplied with `--backup-dir` or a generated path like `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
                * You can disable this with `--no-auto-backup` (manual backup then becomes your responsibility).
            4. Service quiescing
                * Stops `bunkerweb`, `bunkerweb-ui`, and `bunkerweb-scheduler` to ensure a consistent upgrade (matches the manual procedure recommendations).
            5. Package locks removal
                * Temporarily removes `apt-mark hold` / `dnf versionlock` on `bunkerweb` and `nginx` so the targeted version can be installed.
            6. Upgrade execution
                * Installs only the new BunkerWeb package version (NGINX is not reinstalled in upgrade mode unless missing—this avoids touching a correctly pinned NGINX).
                * Re‑applies holds/versionlocks to freeze the upgraded versions.
            7. Finalization & status
                * Displays systemd status for core services and next steps.
                * Leaves your configuration and database intact—only the application code and managed files are updated.

            Key behaviors / notes:

            * The script does NOT modify your `/etc/bunkerweb/variables.env` or database content.
            * If automatic backup failed (or was disabled) you can still do a manual restore using the Rollback section below.
            * Upgrade mode intentionally avoids reinstalling or downgrading NGINX outside the supported pinned version already present.
            * Logs for troubleshooting remain in `/var/log/bunkerweb/`.

        * **Mode-aware behavior**:

            - The installer reuses the same installation-type logic during upgrades: manager mode keeps the setup wizard disabled, binds the internal API listener to `0.0.0.0`, and requires a whitelist IP (pass `--manager-ip` for unattended runs), while worker mode still enforces the manager IP list.
            - Manager upgrades can opt to start or skip the Web UI service, and the summary explicitly reports the API service state so you can decide whether to enable it via `--api` / `--no-api`.
            - CrowdSec is prompted interactively for Full Stack upgrades. The CLI flags remain valid for Full Stack and Manager upgrades, and the script continues to reject CrowdSec for Worker, Scheduler-only, UI-only, and API-only modes.

            Rollback summary:

            * Use the generated backup directory (or your manual backup) + the steps in the Rollback section to restore DB, then reinstall the previous image / package version and re‑lock packages.

        *  **Command-Line Options**:

            You can drive unattended upgrades with the same flags used for installation. The most relevant for upgrades:

            | Option                  | Purpose                                                                                           |
            | ----------------------- | ------------------------------------------------------------------------------------------------- |
            | `-v, --version <X.Y.Z>` | Target BunkerWeb version to upgrade to.                                                           |
            | `-y, --yes`             | Non‑interactive (assumes upgrade confirmation and enables auto backup unless `--no-auto-backup`). |
            | `--tui`                 | Force a TUI (downloaded gum or existing whiptail). Aborts if no TUI tier can render.              |
            | `--no-tui`              | Skip every TUI tier and use plain text prompts. Equivalent to `BW_INSTALL_TUI=no`.                |
            | `--backup-dir <PATH>`   | Destination for the automatic pre‑upgrade backup. Created if missing.                             |
            | `--no-auto-backup`      | Skip automatic backup (NOT recommended). You must have a manual backup.                           |
            | `-q, --quiet`           | Suppress output (combine with logging / monitoring).                                              |
            | `-f, --force`           | Proceed on an otherwise unsupported OS version.                                                   |
            | `--dry-run`             | Show detected environment, intended actions, then exit without changing anything.                 |

            Examples:

            ```bash
            # Upgrade to 1.7.0~beta interactively (will prompt for backup)
            sudo ./install-bunkerweb.sh --version 1.7.0~beta

            # Non-interactive upgrade with automatic backup to custom directory
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --backup-dir /var/backups/bw-2025-01 -y

            # Silent unattended upgrade (logs suppressed) – relies on default auto-backup
            sudo ./install-bunkerweb.sh -v 1.7.0~beta -y -q

            # Perform a dry run (plan) without applying changes
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --dry-run

            # Upgrade skipping automatic backup (NOT recommended)
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --no-auto-backup -y
            ```

            !!! warning "Skipping backups"
                Using `--no-auto-backup` without having a verified manual backup may result in irreversible data loss if the upgrade encounters issues. Always keep at least one recent, tested backup.

    === "Manual"

        1. **Backup the database**:

            - Before proceeding with the database upgrade, ensure that you perform a complete backup of the current state of the database.
            - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

            ??? warning "Information for Red Hat Enterprise Linux (RHEL) 8.10 users"
                If you are using **RHEL 8.10** and plan on using an **external database**, you will need to install the `mysql-community-client` package to ensure the `mysqldump` command is available. You can install the package by executing the following commands:

                === "MySQL/MariaDB"

                    1. **Install the MySQL repository configuration package**

                        ```bash
                        sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                        ```

                    2. **Enable the MySQL repository**

                        ```bash
                        sudo dnf config-manager --enable mysql80-community
                        ```

                    3. **Install the MySQL client**

                        ```bash
                        sudo dnf install mysql-community-client
                        ```

                === "PostgreSQL"

                    4. **Install the PostgreSQL repository configuration package**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5. **Install the PostgreSQL client**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

        1. **Upgrade BunkerWeb**:
            - Upgrade BunkerWeb to the latest version.

                1. **Stop the services**:
                    ```bash
                    sudo systemctl stop bunkerweb
                    sudo systemctl stop bunkerweb-ui
                    sudo systemctl stop bunkerweb-scheduler
                    sudo systemctl stop bunkerweb-api
                    sudo systemctl stop bunkerweb-worker
                    ```

                2. **Update BunkerWeb**:

                    === "Debian/Ubuntu"

                        First, if you have previously held the BunkerWeb package, unhold it :

                        You can print a list of packages on hold with `apt-mark showhold`

                        ```shell
                        sudo apt-mark unhold bunkerweb nginx
                        ```

                        Then, you can update the BunkerWeb package :

                        ```shell
                        sudo apt update && \
                        sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
                        ```

                        To prevent the BunkerWeb package from upgrading when executing `apt upgrade`, you can use the following command :

                        ```shell
                        sudo apt-mark hold bunkerweb nginx
                        ```

                        More details in the [integration Linux page](integrations.md#__tabbed_1_1).

                    === "Fedora/RedHat"

                        First, if you have previously held the BunkerWeb package, unhold it :

                        You can print a list of packages on hold with `dnf versionlock list`

                        ```shell
                        sudo dnf versionlock delete package bunkerweb && \
                        sudo dnf versionlock delete package nginx
                        ```

                        Then, you can update the BunkerWeb package :

                        ```shell
                        sudo dnf makecache && \
                        sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
                        ```

                        To prevent the BunkerWeb package from upgrading when executing `dnf upgrade`, you can use the following command :

                        ```shell
                        sudo dnf versionlock add bunkerweb && \
                        sudo dnf versionlock add nginx
                        ```

                        More details in the [integration Linux page](integrations.md#__tabbed_1_3).

                3. **Start the services**:
                        ```bash
                        sudo systemctl start bunkerweb
                        sudo systemctl start bunkerweb-api
                        sudo systemctl start bunkerweb-worker
                        sudo systemctl start bunkerweb-scheduler
                        sudo systemctl start bunkerweb-ui
                        ```
                        Or reboot the system:
                        ```bash
                        sudo reboot
                        ```


        3. **Check the logs**: Check the logs of the scheduler service to ensure that the migration was successful.

            ```bash
            journalctl -u bunkerweb --no-pager
            ```

        4. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database container.

### Rollback

!!! failure "In case of issues"

    If you encounter any issues during the upgrade, you can rollback to the previous version of the database by restoring the backup taken in [step 1](#__tabbed_1_1).

    Get support and more information :

    - [Order professional support](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Create an issue on GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Join the BunkerWeb Discord server](https://discord.bunkerity.com)

=== "Docker"

    1. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restore the backup**.

        === "SQLite"

            1. **Remove the existing database file.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restore the backup.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Fix permissions.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restore the backup.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

    3. **Downgrade BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Start the containers**.

        ```bash
        docker compose up -d
        ```

=== "All-In-One (AIO)"

    The Scheduler runs inside the `bunkerweb-aio` container, so the restore commands are executed there directly. The `/data` volume (database, configs, plugins, backups) is preserved throughout — only the container image is rolled back.

    !!! tip "External database backends"
        If you run the AIO with an external database (`DATABASE_URI` pointing at MySQL/MariaDB/PostgreSQL), the SQLite file under `/data` is not used. Restore that external database with your usual tooling — or the MySQL/MariaDB/PostgreSQL commands shown in the **Docker** tab, targeting your database host — and skip the SQLite steps below.

    1. **Extract the backup if zipped**.

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restore the backup** (embedded SQLite):

        1. **Remove the existing database file.**

            ```bash
            docker exec -u 0 -i bunkerweb-aio rm -f /var/lib/bunkerweb/db.sqlite3
            ```

        2. **Restore the backup.**

            ```bash
            docker exec -i bunkerweb-aio sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            ```

        3. **Fix permissions.**

            ```bash
            docker exec -u 0 -i bunkerweb-aio chown root:nginx /var/lib/bunkerweb/db.sqlite3
            docker exec -u 0 -i bunkerweb-aio chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

    3. **Roll back the image**, reusing the same `/data` volume:

        === "docker run"

            3. **Stop and remove the current container** (the `/data` volume is kept):
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4. **Pull the previous image**:
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:<old_version>
                ```

            5. **Re-create the container** with the same options, ports and the same `/data` volume as before:
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:<old_version>
                ```

        === "Docker Compose"

            6. **Update the Docker Compose file** to use the previous All-In-One image:
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:<old_version>
                        ...
                ```

            7. **Restart the container**. The `/data` volume is reattached automatically:
                ```bash
                docker compose down
                docker compose up -d
                ```

=== "Linux"

    4. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Stop the services**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
        ```

    6. **Restore the backup**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Start the services**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
        ```

    8. **Downgrade BunkerWeb**.
        - Downgrade BunkerWeb to the previous version by following the same steps as when upgrading BunkerWeb in the [integration Linux page](integrations.md#linux)

## Upgrade from 1.5.X

### What changed?

#### Scheduler

Unlike the 1.5.X releases, the Scheduler service **no longer uses the *docker socket proxy* to fetch BunkerWeb's instances**. Instead, it uses the new `BUNKERWEB_INSTANCES` environment variable.

!!! info "About the `BUNKERWEB_INSTANCES` environment variable"

    This new variable is a list of BunkerWeb instances separated by spaces in this format: `http://bunkerweb:5000 bunkerweb1:5000 bunkerweb2:5000 ...`. The scheduler will then use this list to fetch the instances' configuration and to send the configuration to them.

    * The `http://` prefix is optional.
    * The port is optional and defaults to the value of the `API_HTTP_PORT` environment variable.
    * The default value of the `BUNKERWEB_INSTANCES` environment variable is `127.0.0.1`.

In other words, the new system is fully agnostic and generic: the scheduler is in charge of managing a list of BunkerWeb instances and doesn't need to care about the environment.

!!! tip "Autoconf/Kubernetes/Swarm integrations"

    If you are using the `Autoconf`, `Kubernetes`, or `Swarm` integrations, you can set the `BUNKERWEB_INSTANCES` environment variable to an empty string (so that it doesn't try to send the configuration to the default one which is `127.0.0.1`).

    **The instances will be automatically fetched by the controller**. You can also add custom instances to the list that may not be picked up by the controller.

Since the `1.6`, the Scheduler also have a new [built-in healthcheck system](concepts.md), that will check the health of the instances. If an instance becomes unhealthy, the scheduler will stop sending the configuration to it. If the instance becomes healthy again, the scheduler will start sending the configuration to it again.

#### BunkerWeb container

Another important change is that the **settings** that were previously declared on the BunkerWeb container **are now declared on the scheduler**. This means that you'll have to move your settings from the BunkerWeb container to the Scheduler container.

While the settings are now declared on the Scheduler container, **you'll still need to declare API-related mandatory settings on the BunkerWeb container** like the `API_WHITELIST_IP` setting which is used to whitelist the Scheduler's IP address, so that it can send the configuration to the instance. If you use `API_TOKEN`, you must also set it on the BunkerWeb container (and mirror it on the Scheduler) to allow authenticated API calls.

!!! warning "BunkerWeb's container settings"

    Every API related setting that you declare on the BunkerWeb container **have to be mirrored on the Scheduler container** so that it keeps working, as the configuration will be overwritten by the Scheduler's generated configuration.

#### Default values and new settings

We tried our best not to change default value but we have added many other settings. It's highly recommended to read the [security tuning](advanced.md#security-tuning) and [settings](features.md) sections of the documentation.

#### Templates

We added a new feature called **templates**. Templates provide a structured and standardized approach to defining settings and custom configurations, check the [concepts/templates](concepts.md#templates) section for more information.

#### Autoconf namespaces

We added a **namespace** feature to the autoconf integrations. Namespaces allow you to group your instances and apply settings only to them. Check the following sections according to your Integration for more information:

- [Autoconf/namespaces](integrations.md#namespaces)
- [Kubernetes/namespaces](integrations.md#namespaces_1)
- [Swarm/namespaces](integrations.md#namespaces_2)

### Procedure

1. **Backup the database**:
      - Before proceeding with the database upgrade, ensure that you perform a complete backup of the current state of the database.
      - Use appropriate tools to backup the entire database, including data, schemas, and configurations.

    === "1\.5\.7 and later"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        === "Linux"

            ??? warning "Information for Red Hat Enterprise Linux (RHEL) 8.10 users"
                If you are using **RHEL 8.10** and plan on using an **external database**, you will need to install the `mysql-community-client` package to ensure the `mysqldump` command is available. You can install the package by executing the following commands:

                === "MySQL/MariaDB"

                    1. **Install the MySQL repository configuration package**

                        ```bash
                        sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                        ```

                    2. **Enable the MySQL repository**

                        ```bash
                        sudo dnf config-manager --enable mysql80-community
                        ```

                    3. **Install the MySQL client**

                        ```bash
                        sudo dnf install mysql-community-client
                        ```

                === "PostgreSQL"

                    4. **Install the PostgreSQL repository configuration package**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5. **Install the PostgreSQL client**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

    === "1\.5\.6 and earlier"

        === "SQLite"

            === "Docker"

                We first need to install the `sqlite` package in the container.

                ```bash
                docker exec -u 0 -it <scheduler_container> apk add sqlite
                ```

                Then, backup the database.

                ```bash
                docker exec -it <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

        === "MariaDB"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "MySQL"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it -e PGPASSWORD=<database_password> <database_container> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                PGPASSWORD=<database_password> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

2. **Upgrade BunkerWeb**:
      - Upgrade BunkerWeb to the latest version.

        === "Docker"

            1. **Update the Docker Compose file**: Update the Docker Compose file to use the new version of the BunkerWeb image.
                ```yaml
                services:
                    bunkerweb:
                        image: bunkerity/bunkerweb:1.7.0-beta
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.7.0-beta
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.7.0-beta
                        ...
                ```

            2. **Restart the containers**: Restart the containers to apply the changes.
                ```bash
                docker compose down
                docker compose up -d
                ```

        === "Linux"

            3. **Stop the services**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                sudo systemctl stop bunkerweb-api
                sudo systemctl stop bunkerweb-worker
                ```

            4. **Update BunkerWeb**:

                === "Debian/Ubuntu"

                    First, if you have previously held the BunkerWeb package, unhold it :

                    You can print a list of packages on hold with `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Then, you can update the BunkerWeb package :

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
                    ```

                    To prevent the BunkerWeb package from upgrading when executing `apt upgrade`, you can use the following command :

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    More details in the [integration Linux page](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    First, if you have previously held the BunkerWeb package, unhold it :

                    You can print a list of packages on hold with `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Then, you can update the BunkerWeb package :

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
                    ```

                    To prevent the BunkerWeb package from upgrading when executing `dnf upgrade`, you can use the following command :

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    More details in the [integration Linux page](integrations.md#__tabbed_1_3).

            5. **Start the services**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-api
                    sudo systemctl start bunkerweb-worker
                    sudo systemctl start bunkerweb-scheduler
                    sudo systemctl start bunkerweb-ui
                    ```
                    Or reboot the system:
                    ```bash
                    sudo reboot
                    ```


3. **Check the logs**: Check the logs of the scheduler service to ensure that the migration was successful.

    === "Docker"

        ```bash
        docker compose logs <scheduler_container>
        ```

    === "Linux"

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

4. **Verify the database**: Verify that the database upgrade was successful by checking the data and configurations in the new database container.

### Rollback

!!! failure "In case of issues"

    If you encounter any issues during the upgrade, you can rollback to the previous version of the database by restoring the backup taken in [step 1](#__tabbed_1_1).

    Get support and more information :

    - [Order professional support](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Create an issue on GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Join the BunkerWeb Discord server](https://discord.bunkerity.com)

=== "Docker"

    1. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restore the backup**.

        === "SQLite"

            1. **Remove the existing database file.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restore the backup.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Fix permissions.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restore the backup.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Stop the stack.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Stop the stack.**

                ```bash
                docker compose down
                ```

    3. **Downgrade BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Start the containers**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extract the backup if zipped**.

        Extract the backup zip file first:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Stop the services**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
        ```

    6. **Restore the backup**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Remove the existing database.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Recreate the database.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restore the backup.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Start the services**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
        ```

    8. **Downgrade BunkerWeb**.
        - Downgrade BunkerWeb to the previous version by following the same steps as when upgrading BunkerWeb in the [integration Linux page](integrations.md#linux)
