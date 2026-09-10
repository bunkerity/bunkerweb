# Troubleshooting

!!! info "BunkerWeb Panel"
    If you are unable to resolve your issue, you can [contact us directly via our panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc). This centralizes all requests related to the BunkerWeb solution.

## Logs

When troubleshooting, logs are your best friends. We try our best to provide user-friendly logs to help you understand what's happening.

Please note that you can set the `LOG_LEVEL` to `info` (default: `notice`) to increase BunkerWeb’s verbosity.

Here is how you can access the logs, depending on your integration :

=== "Docker"

    !!! tip "List containers"
        To list the running containers, you can use the following command :
        ```shell
        docker ps
        ```

    You can use the `docker logs` command (replace `bunkerweb` with the name of your container) :
    ```shell
    docker logs bunkerweb
    ```

    Here is the docker-compose equivalent (replace `bunkerweb` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs bunkerweb
    ```

=== "Docker autoconf"

    !!! tip "List containers"
        To list the running containers, you can use the following command :
        ```shell
        docker ps
        ```

    You can use the `docker logs` command (replace `bunkerweb` and `bw-autoconf` with the name of your containers) :
    ```shell
    docker logs bunkerweb
    docker logs bw-autoconf
    ```

    Here is the docker-compose equivalent (replace `bunkerweb` and `bw-autoconf` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs bunkerweb
    docker-compose logs bw-autoconf
    ```

=== "All-in-one"

    !!! tip "Container name"
        The default container name for the All-in-one image is `bunkerweb-aio`. If you've used a different name, please adjust the command accordingly.

    You can use the `docker logs` command:
    ```shell
    docker logs bunkerweb-aio
    ```

=== "Swarm"

    !!! tip "List services"
        To list the services, you can use the following command :
        ```shell
        docker service ls
        ```

    You can use the `docker service logs` command (replace `bunkerweb` and `bw-autoconf` with the name of your services) :
    ```shell
    docker service logs bunkerweb
    docker service logs bw-autoconf
    ```

=== "Kubernetes"

    !!! tip "List pods"
        To list the pods, you can use the following command :
        ```shell
        kubectl get pods
        ```

    You can use the `kubectl logs` command (replace `bunkerweb` and `bunkerweb-controler` with the name of your pods) :
    ```shell
    kubectl logs bunkerweb
    kubectl logs bunkerweb-controler
    ```

=== "Linux"

    For errors related to BunkerWeb services (e.g., not starting), you can use `journalctl` :
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Common logs are located inside the `/var/log/bunkerweb` directory :
    ```shell
    cat /var/log/bunkerweb/error.log
    cat /var/log/bunkerweb/access.log
    ```

## Permissions

Don't forget that BunkerWeb runs as an unprivileged user for obvious security reasons. Double-check the permissions of files and folders used by BunkerWeb, especially if you use custom configurations (more info [here](advanced.md#custom-configurations)). You will need to set at least **_RW_** rights on files and **_RWX_** on folders.

## IP unban

You can manually unban an IP, which is useful when performing tests so that you can contact the internal API of BunkerWeb (replace `1.2.3.4` with the IP address to unban) :

=== "Docker / Docker Autoconf"

    You can use the `docker exec` command (replace `bw-scheduler` with the name of your container) :
    ```shell
    docker exec bw-scheduler bwcli unban 1.2.3.4
    ```

    Here is the docker-compose equivalent (replace `bw-scheduler` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose exec bw-scheduler bwcli unban 1.2.3.4
    ```

=== "All-in-one"

    !!! tip "Container name"
        The default container name for the All-in-one image is `bunkerweb-aio`. If you've used a different name, please adjust the command accordingly.

    You can use the `docker exec` command:
    ```shell
    docker exec bunkerweb-aio bwcli unban 1.2.3.4
    ```

=== "Swarm"

    You can use the `docker exec` command (replace `bw-scheduler` with the name of your service) :
    ```shell
    docker exec $(docker ps -q -f name=bw-scheduler) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    You can use the `kubectl exec` command (replace `bunkerweb-scheduler` with the name of your pod) :
    ```shell
    kubectl exec bunkerweb-scheduler bwcli unban 1.2.3.4
    ```

=== "Linux"

    You can use the `bwcli` command (as root) :
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

## False positives

### Detect only mode

For debugging/test purposes, you can set BunkerWeb in [detect only mode](features.md#security-modes) so it won't block request and will act as a classical reverse proxy.

### ModSecurity

The default BunkerWeb configuration of ModSecurity is to load the Core Rule Set in anomaly scoring mode with a paranoia level (PL) of 1 :

- Each matched rule will increase an anomaly score (so many rules can match a single request)
- PL1 includes rules with fewer chances of false positives (but less security than PL4)
- the default threshold for anomaly score is 5 for requests and 4 for responses

Let's take the following logs as an example of ModSecurity detection using default configuration (formatted for better readability) :

```log
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `lfi-os-files.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf"]
	[line "78"]
	[id "930120"]
	[rev ""]
	[msg "OS File Access Attempt"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-lfi"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/255/153/126"]
	[tag "PCI/6.5.4"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:utf8toUnicode,t:urlDecodeUni,t:normalizePathWin,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `unix-shell.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf"]
	[line "480"]
	[id "932160"]
	[rev ""]
	[msg "Remote Command Execution: Unix Shell Code Found"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-shell"]
	[tag "platform-unix"]
	[tag "attack-rce"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/152/248/88"]
	[tag "PCI/6.5.2"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:urlDecodeUni,t:cmdLine,t:normalizePath,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [error] 85#85: *11 [client 172.17.0.1] ModSecurity: Access denied with code 403 (phase 2). Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `10' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-949-BLOCKING-EVALUATION.conf"]
	[line "80"]
	[id "949110"]
	[rev ""]
	[msg "Inbound Anomaly Score Exceeded (Total Score: 10)"]
	[data ""]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-generic"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref ""],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
```

As we can see, there are 3 different logs :

1. Rule **930120** matched
2. Rule **932160** matched
3. Access denied (rule **949110**)

One important thing to understand is that rule **949110** is not a "real" one : it's the one that will deny the request because the anomaly threshold is reached (which is **10** in this example). You should never remove the **949110** rule !

If it's a false-positive, you should then focus on both **930120** and **932160** rules. ModSecurity and/or CRS tuning is out of the scope of this documentation but don't forget that you can apply custom configurations before and after the CRS is loaded (more info [here](advanced.md#custom-configurations)).

### Bad Behavior

A common false-positive case is when the client is banned because of the "bad behavior" feature which means that too many suspicious HTTP status codes were generated within a time period (more info [here](features.md#bad-behavior)). You should start by reviewing the settings and then edit them according to your web application(s) like removing a suspicious HTTP code, decreasing the count time, increasing the threshold, ...

### Whitelisting

If you have bots (or admins) that need to access your website, the recommended way to avoid any false positive is to whitelist them using the [whitelisting feature](features.md#whitelist). We don't recommend using the `WHITELIST_URI*` or `WHITELIST_USER_AGENT*` settings unless they are set to secret and unpredictable values. Common use cases are :

- Healthcheck / status bot
- Callback like IPN or webhook
- Social media crawler

## Common errors

### Upstream sent too big header

If you see the following error `upstream sent too big header while reading response header from upstream` in the logs, you will need to tweak the various proxy buffers size using the following settings :

- `PROXY_BUFFERS`
- `PROXY_BUFFER_SIZE`
- `PROXY_BUSY_BUFFERS_SIZE`

### Could not build server_names_hash

If you see the following error `could not build server_names_hash, you should increase server_names_hash_bucket_size` in the logs, you will need to tweak the `SERVER_NAMES_HASH_BUCKET_SIZE` setting.

## Background jobs never run {#background-jobs}

Since 1.7 the Scheduler does not execute jobs itself. It dispatches them through the **API** (`POST /jobs/dispatch`) onto a **job broker**, and a **Worker** picks them up and runs them (see [Scheduler](concepts.md#scheduler)). The Worker and the broker are new in 1.7; the API is not, but it is on this path now. When any of the three is missing or unreachable the failure is silent: nothing crashes, the Scheduler keeps generating configuration, the instances stay healthy — and no certificate is renewed, no blocklist is refreshed and no backup is taken.

The symptom to look for is a **last run** that stops advancing on the **Jobs** page of the web UI, or on the API:

```bash
# container stacks: the API service name; on Linux: http://127.0.0.1:8888
curl -H "Authorization: Bearer $API_TOKEN" http://bw-api:8888/jobs
```

### The Worker is not running

The most common cause on an installation upgraded from 1.6 is that the Worker was never added: bumping the image tags of a 1.6 stack leaves it without `bw-api`, `bw-worker` and `bw-jobs-broker` entirely. See [the upgrade notes](upgrading.md#breaking-changes) and redeploy from the reference stack for your integration.

=== "Docker"

    ```shell
    docker compose ps bw-api bw-worker bw-jobs-broker
    docker compose logs bw-worker
    ```

    No such service means the stack predates 1.7 — add the three services, `API_URL`, `API_TOKEN` and `CELERY_BROKER_URL`, then recreate.

=== "Linux"

    ```shell
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    journalctl -u bunkerweb-worker --no-pager -n 100
    ```

    `bunkerweb-worker` is a new unit in 1.7 and the package installs it on every host, so the answer is `enabled`/`disabled`, never "not found".

    **Check it on the host that runs `bunkerweb-scheduler`.** There, `enabled`+`active` is what you want; `systemctl enable --now bunkerweb-worker` fixes it and pulls the broker unit in on its own. If it is active but idle, the broker is the next thing to look at.

    **On a BunkerWeb-instance-only node** — a `--worker` install, in the installer's sense of "runs the instance, not the control plane" — `disabled` is correct and deliberate: that host owns no jobs. Do not enable it there.

    !!! info "Upgrades from before 1.7.0 may have left it enabled on an instance-only node"
        The package decides what a host runs from `WORKER_MODE`/`MANAGER_MODE`/`SERVICE_*` in its own environment, and no upgrade sets them — not a plain `apt install bunkerweb=...`, and not `install-bunkerweb.sh` either, whose upgrade path exits before it would export them. Since 1.7.0 the package recovers the topology on its own instead: it reads the install type recorded at the last declared install, and on a host that predates that marker it falls back to "does this host run `bunkerweb-scheduler`?". Neither a broker nor `bunkerweb-worker` is enabled on a node that answers no. Earlier upgrades did take such a host for a standalone one and **enabled and started** `bunkerweb-worker` plus the first Redis unit they found — on a node like this the distro `redis-server` (or `valkey`/`redis`), since an instance-only install provisions no `bunkerweb-broker`. If your node went through one of those, clean it up once with the commands below.

        It is harmless as far as jobs go: that host is dispatched none (its worker falls back to `redis://127.0.0.1:6379/0`, which no control plane dispatches to). That fallback is what makes it harmless, with one exception: if this node's `CELERY_BROKER_URL` was made to point at a **routable** broker — copied in from a `--broker-url` install, or set by hand — the leftover worker really does consume jobs. A copied installer-provisioned URL is not that: the dedicated broker binds `127.0.0.1` and its URL says a `127.0.0.1` address, so on this node it resolves to this node's own loopback and the worker just retry-loops on a refused connection. If you want it gone: `systemctl disable --now bunkerweb-worker`. Once is enough on 1.7.0 and later — the next upgrade sees a host with no scheduler and leaves it alone.

        **Leave the Redis unit alone unless you know it is not your WAF datastore.** `USE_REDIS` and `REDIS_HOST` are *fleet* settings and live on the control plane — web UI → **Global settings** → Redis, or the scheduler host's `/etc/bunkerweb/variables.env`. They are not in this node's own `/etc/bunkerweb/variables.env`, which ignores those keys, so grepping *that* file proves nothing. The rendered configuration the control plane pushed does carry them, so on a node that has received at least one push you can also answer it locally:

        ```bash
        grep -E '^(USE_REDIS|REDIS_HOST)=' /etc/nginx/variables.env
        ```

        Before that first push the node is running off its own boot defaults, and only the control plane knows. Look them up there, and if `REDIS_HOST` is an address of **this** host — a LAN address, not necessarily `127.0.0.1`; a datastore shared across instances is reached by a routable one — then this server holds your shared bans and rate-limit counters, and disabling it drops them and un-shares them. Only once you have checked: `systemctl disable --now redis-server` (or `valkey`, or `redis`).

        One consequence to expect on a host that carries such a leftover worker: it points at `127.0.0.1:6379`, so if your local datastore is password-protected it logs `NOAUTH` forever. That is this node's idle worker talking to the datastore, not a broken job pipeline — the section below diagnoses the **scheduler** host.

### The broker refuses the connection (`NOAUTH`)

If the broker is password-protected but `CELERY_BROKER_URL` carries no credentials, the broker answers `NOAUTH Authentication required`. The Worker stays `active` while consuming nothing, and `POST /jobs/dispatch` on the API answers `502`.

```bash
journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'   # Linux
docker compose logs bw-worker | grep -i 'NOAUTH\|AuthenticationError'    # Docker
```

First verify that the endpoint is a dedicated job broker configured with `maxmemory-policy noeviction`. If port `6379` serves an evicting WAF datastore, provision a separate broker through the [Linux installer](integrations.md#easy-installation-script) or configure one yourself, then use its actual address and port. Fixing `NOAUTH` alone does not protect jobs and leases from eviction.

Then give the broker its own credentials. On Linux one write to `/etc/bunkerweb/variables.env` covers both components, because the Worker and the API read that file before their own environment; in a container stack, set it on both services:

```bash
CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0     # Linux, a dedicated noeviction distro Redis
CELERY_BROKER_URL=redis://:<password>@bw-jobs-broker:6379/0 # a container stack
```

Check `/etc/bunkerweb/broker.conf` before you touch anything. If that file exists, the installer provisioned a dedicated `bunkerweb-broker` and `CELERY_BROKER_URL` already points at it **with its password** — edit the line that is there rather than adding one, and read the port off it: `6380` is only the default, and the installer walks up from it when it is taken. If the file does not exist, `CELERY_BROKER_URL` is whatever you set — or unset, in which case on Linux the Worker and the API both fall back to `redis://127.0.0.1:6379/0` — and the fix above is the one you want. The installer provisions the dedicated broker narrowly — a fresh install, or an upgrade of a host whose Redis carries a `requirepass` or an evicting `maxmemory` — so an upgraded host with a plain distro Redis, or one installed with `--no-broker` or `--broker-url`, has no `broker.conf`.

Then restart both: `systemctl restart bunkerweb-worker bunkerweb-api`, or recreate `bw-worker` and `bw-api`.

!!! warning "The broker is not the WAF data store"
    The job broker must run `maxmemory-policy noeviction`: it holds the leases that stop two workers pushing configurations at once, and those are keys *with* a TTL, so any `volatile-*` policy is free to drop them mid-flight. A data store, by contrast, is normally capped and left free to evict — transient counters are cheaper to lose than writes are to refuse. `maxmemory-policy` is per-server and never per-database, so pointing the two roles at different database numbers of the same server does **not** separate them. Full explanation in [the upgrade notes](upgrading.md#breaking-changes).

## An enrolled instance refuses to start {#lost-instance-credential}

An instance that redeemed an enrollment code stores the credential it was given in `/var/lib/bunkerweb/instance-credential.json`, and from then on it accepts **only** that credential — it never falls back to the shared `API_TOKEN`. If the file disappears while the marker recording the enrollment survives, the instance refuses to start rather than come up deaf to the control plane, and says so:

```
This instance was enrolled but its credential is gone (/var/lib/bunkerweb/instance-credential.json
is missing or contains no usable credential) [...] Refusing to start.
```

The trigger is narrow on purpose: the marker is still there and a usable credential is not — the file was deleted, truncated, restored without it, or left with no credential inside it. A file that exists but cannot be *read* (root-owned after an upgrade, say) leaves the question open, so the instance boots — and then refuses every push until the permissions are fixed. Restore its permissions instead of re-enrolling it.

Two neighbouring cases boot normally and fail at the control plane instead, where every push to the instance is refused: a container recreated with **no** `/data` volume at all (marker and credential go together, and it comes back as a fresh, unenrolled instance), and a restore from a snapshot taken *before* the enrollment (neither file is in it). The instance logs only a per-call `can't validate API token from IP …` warning, which never says the enrollment is what went missing — the diagnosis is on the control-plane side.

Two ways out of the boot refusal:

- **Keep it enrolled**: issue a new enrollment code for it — the key button on the **Instances** page of the web UI, or `POST /instances/{hostname}/enroll` on the API — and pass it as `INSTANCE_ENROLLMENT_CODE` on the next start.
- **Put it back on the shared token** — two sides, and both are needed. On the instance, delete `/var/lib/bunkerweb/instance-enrolled` **and** `instance-credential.json`: a leftover empty or truncated credential file makes the instance refuse every token, the shared one included. That lets it boot on `API_TOKEN`, and on its own changes nothing else — the control plane still holds the minted credential for that row and keeps dialing with it, so every push is still refused. Clear it on the row too:

    ```bash
    curl -X PATCH -H "Authorization: Bearer $API_TOKEN" -H 'Content-Type: application/json' \
      -d '{"credential": ""}' http://bw-api:8888/instances/<hostname>
    ```

    An empty `credential` clears the stored one whatever the instance's method is, and the control plane goes back to dialing it with the shared `API_TOKEN`. This is an API-only route — the **Instances** page offers rotate and revoke, not clear.

    **It does not lift a revocation.** If you revoked the instance first — the reflex, and a button on that same page — clearing the credential is a no-op: the row stays revoked and every push stays refused. Two things lift it: a new enrollment code, or, on an instance that declares its own token (`BUNKERWEB_INSTANCE_API_TOKEN[_n]`, the grouped `BUNKERWEB_INSTANCE_HOST_n` form — the flat `BUNKERWEB_INSTANCES` list carries no token), the next scheduler configuration save, which re-sources the credential from the environment and lifts the revocation with it. That declared token has to **differ from the global `API_TOKEN`**: declaring the shared one again is not a declaration at all as far as this goes, and nothing happens — no lift, no log line. The scheduler logs that it did. On any other row, re-enrolling is not the preferred recovery, it is the only one. If you would rather not call the API: a **UI- or API-registered** instance can be deleted on the **Instances** page (or `DELETE /instances/{hostname}`) and added again; an instance **declared through the environment** (`BUNKERWEB_INSTANCES`) can be taken out of the declared list, given one scheduler configuration save — which deletes the row, and with it any TLS pinning or name set from the UI — then declared again. Both throw away more than the `PATCH` does.

    An instance **discovered** by autoconf, Kubernetes or Swarm is never in this situation at all: the control plane refuses to mint a credential for a row sourced from an orchestrator, so it never holds an enrollment.

    **Re-enrolling is the supported recovery; prefer it.**

!!! tip "Give the instance a persistent `/data`"
    The reference stacks mount a `bw-instance-data` volume on the `bunkerweb` service for exactly this reason. Without it, every `docker compose down` followed by `up` throws the credential away and the instance comes back unenrolled — silently, because it boots fine; the refusal shows up at the control plane, as pushes that never land. See [Instance enrollment](web-ui.md#instance-enrollment).

## Timezone

When using container-based integrations, the timezone of the container may not match that of the host machine. To resolve that, you can set the `TZ` environment variable to the timezone of your choice on your containers (e.g. `TZ=Europe/Paris`). You will find the list of timezone identifiers [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List).

## Clear old instances from database {#clear-old-instances-db}

BunkerWeb stores known instances in the `bw_instances` table (primary key: `hostname`).
If you frequently redeploy, old rows may remain (for example, instances that haven’t checked in for a long time) and you may want to purge them.

!!! warning "Backup first"
    Before editing the database manually, create a backup (snapshot the SQLite volume or use your DB engine backup tools).

!!! warning "Stop writers"
    To avoid races while deleting, stop (or scale down) components that can update instances
    (typically the scheduler / autoconf depending on your deployment), run the cleanup, then start them again.

### Table and columns (reference)

The instance model is defined as:

- Table: `bw_instances`
- Primary key: `hostname`
- “Last seen” timestamp: `last_seen`
- Also contains:
  `name`, `port`, `listen_https`, `https_port`,
  `server_name`, `type`, `status`, `method`,
  `creation_date`

### 1 - Connect to the database

Use the existing [Access database](#access-database) section to connect
(SQLite / MariaDB / PostgreSQL).

### 2 - Dry-run: list stale instances

Pick a retention window (example: 90 days) and review what would be deleted.

=== "SQLite"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days')
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "MariaDB / MySQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY)
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "PostgreSQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days'
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

### 3 - Delete stale instances

Once verified, delete the rows.

=== "SQLite"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days');

    COMMIT;
    ```

=== "MariaDB / MySQL"

    ```sql
    START TRANSACTION;

    DELETE FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY);

    COMMIT;
    ```

=== "PostgreSQL"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days';

    COMMIT;
    ```

!!! tip "Delete by hostname"
    To delete a specific instance, use its hostname (the primary key).

    ```sql
    DELETE FROM bw_instances WHERE hostname = '<hostname>';
    ```

### 4 - Mark instances as changed (optional)

BunkerWeb tracks instance changes in the `bw_metadata` table
(`instances_changed`, `last_instances_change`).

If the UI does not refresh as expected after manual cleanup,
you can force a “change marker” update:

=== "SQLite / PostgreSQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = CURRENT_TIMESTAMP
    WHERE id = 1;
    ```

=== "MariaDB / MySQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = NOW()
    WHERE id = 1;
    ```

### 5 - Reclaim space (optional)

=== "SQLite"

    ```sql
    VACUUM;
    ```

=== "PostgreSQL"

    ```sql
    VACUUM (ANALYZE);
    ```

=== "MariaDB / MySQL"

    ```sql
    OPTIMIZE TABLE bw_instances;
    ```

## Web UI {#web-ui}

In case you forgot your UI credentials or are experiencing 2FA issues, you can connect to the database to regain access.

### Access database

=== "SQLite"

    === "Linux"

        Install SQLite (Debian/Ubuntu):

        ```shell
        sudo apt install sqlite3
        ```

        Install SQLite (Fedora/RedHat):

        ```shell
        sudo dnf install sqlite
        ```

    === "Docker"

        Get a shell into your scheduler container :

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory)
            - the `-it` options are to run the command interactively (mandatory)
            - `<bunkerweb_scheduler_container>` : the name or ID of your scheduler container

        ```shell
        docker exec -u 0 -it <bunkerweb_scheduler_container> bash
        ```

        Install SQLite :

        ```bash
        apk add sqlite
        ```

    === "All-in-one"

        Get a shell into your All-in-one container:

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory).
            - the `-it` options are to run the command interactively (mandatory).
            - `bunkerweb-aio` is the default container name; adjust if you used a custom name.

        ```shell
        docker exec -u 0 -it bunkerweb-aio bash
        ```

    Access your database :

    !!! note "Database path"
        We assume that you are using the default database path. If you are using a custom path, you will need to adapt the command.
        For All-in-one, we assume the database is `db.sqlite3` located in the persistent `/data/lib` volume (`/data/lib/db.sqlite3`).

    ```bash
    sqlite3 /var/lib/bunkerweb/db.sqlite3
    ```

    You should see something like this :

    ```text
    SQLite version <VER> <DATE>
    Enter ".help" for usage hints.
    sqlite>
    ```

=== "MariaDB / MySQL"

    !!! note "MariaDB / MySQL only"
        The following steps are only valid for MariaDB / MySQL databases. If you are using another database, please refer to the documentation of your database.

    !!! note "Credentials and database name"
        You will need to use the same credentials and database named used in the `DATABASE_URI` setting.

    === "Linux"

        Access your local database :

        ```bash
        mysql -u <user> -p <database>
        ```

        Then enter the database user’s password and you should be able to access your database.

    === "Docker"

        Access your database container :

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory)
            - the `-it` options are to run the command interactively (mandatory)
            - `<bunkerweb_db_container>` : the name or ID of your database container
            - `<user>` : the database user
            - `<database>` : the database name

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> mysql -u <user> -p <database>
        ```

        Then enter the database user’s password and you should be able to access your database.

    === "All-in-one"

        The All-in-One image does not include a MariaDB/MySQL server. If you have configured the AIO to use an external MariaDB/MySQL database (by setting the `DATABASE_URI` environment variable), you should connect to that database directly using standard MySQL client tools.

        The connection method would be similar to the "Linux" tab (if connecting from the host where AIO runs or another machine) or by running a MySQL client in a separate Docker container if preferred, targeting your external database's host and credentials.

=== "PostgreSQL"

    !!! note "PostgreSQL only"
        The following steps are only valid for PostgreSQL databases. If you are using another database, please refer to the documentation of your database.

    !!! note "Credentials, host and database name"
        You will need to use the same credentials (user/password), host and database name used in the `DATABASE_URI` setting.

    === "Linux"

        Access your local database:

        ```bash
        psql -U <user> -d <database>
        ```

        If your database is on another host, include the hostname/IP and port:

        ```bash
        psql -h <host> -p 5432 -U <user> -d <database>
        ```

        Then enter the database user’s password and you should be able to access your database.

    === "Docker"

        Access your database container:

        !!! note "Docker arguments"
            - the `-u 0` option is to run the command as root (mandatory)
            - the `-it` options are to run the command interactively (mandatory)
            - `<bunkerweb_db_container>` : the name or ID of your database container
            - `<user>` : the database user
            - `<database>` : the database name

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> psql -U <user> -d <database>
        ```

        If the database is hosted elsewhere, add the `-h <host>` and `-p 5432` options accordingly.

    === "All-in-one"

        The All-in-One image does not include a PostgreSQL server. If you have configured the AIO to use an external PostgreSQL database (by setting the `DATABASE_URI` environment variable), you should connect to that database directly using standard PostgreSQL client tools.

        The connection method would be similar to the "Linux" tab (if connecting from the host where AIO runs or another machine) or by running a PostgreSQL client in a separate Docker container if preferred, targeting your external database's host and credentials.

### Troubleshooting actions

!!! info "Tables schema"
    The schema of the `bw_ui_users` table is the following:

    | Field         | Type                                                | Null | Key | Default | Extra |
    | ------------- | --------------------------------------------------- | ---- | --- | ------- | ----- |
    | username      | varchar(256)                                        | NO   | PRI | NULL    |       |
    | email         | varchar(256)                                        | YES  | UNI | NULL    |       |
    | password      | varchar(60)                                         | NO   |     | NULL    |       |
    | method        | enum('ui','scheduler','autoconf','manual','wizard') | NO   |     | NULL    |       |
    | admin         | tinyint(1)                                          | NO   |     | NULL    |       |
    | theme         | enum('light','dark')                                | NO   |     | NULL    |       |
    | language      | varchar(2)                                          | NO   |     | NULL    |       |
    | totp_secret   | varchar(256)                                        | YES  |     | NULL    |       |
    | creation_date | datetime                                            | NO   |     | NULL    |       |
    | update_date   | datetime                                            | NO   |     | NULL    |       |

=== "Retrieve username"

    Execute the following command to extract data from the `bw_ui_users` table :

    ```sql
    SELECT * FROM bw_ui_users;
    ```

    You should see something like this :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

=== "Update admin user password"

    You first need to hash the new password using the bcrypt algorithm.

    Install the Python bcrypt library :

    ```shell
    pip install bcrypt
    ```

    Generate your hash (replace `mypassword` with your own password) :

    ```shell
    python3 -c 'from bcrypt import hashpw, gensalt ; print(hashpw(b"""mypassword""", gensalt(rounds=10)).decode("utf-8"))'
    ```

    You can update your username / password executing this command :

    ```sql
    UPDATE bw_ui_users SET password = '<password_hash>' WHERE admin = 1;
    ```

    If you check again your `bw_ui_users` table following this command :

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    You should see something like this :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

    You should now be able to use the new credentials to log into the web UI.

=== "Disable 2FA authentication for admin user"

    You can deactivate 2FA by executing this command :

    ```sql
    UPDATE bw_ui_users SET totp_secret = NULL WHERE admin = 1;
    ```

    If you check again your `bw_ui_users` table by following this command :

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    You should see something like this :

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | -------- | ----- | -------- | ------ | ----- | ----- | ----------- | ------------- | ----------- |
    | ***      | ***   | ***      | manual | 1     | light | NULL        | ***           | ***         |

    You should now be able to log into the web UI only using your username and password without 2FA.

=== "Refresh 2FA recovery codes"

    The recovery codes can be refreshed in your **profile page** of the web UI under the `Security` tab.

=== "Export configuration and anonymized logs"

    Use the **Support page** in the Web UI to quickly gather configuration and logs for troubleshooting.

    - Open the Web UI and go to the Support page.
    - Choose the scope: export the global settings or select a specific Service.
    - Click to download the configuration archive for the chosen scope.
    - Optionally download logs: the exported logs are automatically anonymized (all IP addresses and domains are masked).

### Upload plugin

It may not be possible to upload a plugin from the UI in certain situations:

- Missing package to manage compressed files on your integration, in which case you will need to add the necessary packages
- Safari browser : the 'safe mode' may prevent you from being able to add a plugin. You will need to make the necessary changes on your machine
