<figure markdown>
  ![Overview](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

The CrowdSec plugin integrates BunkerWeb with the CrowdSec security engine, providing an additional layer of protection against various cyber threats. This plugin acts as a [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) bouncer, denying requests based on decisions from the CrowdSec API.

CrowdSec is a modern, open-source security engine that detects and blocks malicious IP addresses based on behavioral analysis and collective intelligence from its community. You can also configure [scenarios](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) to automatically ban IP addresses based on suspicious behavior, benefiting from a crowdsourced blacklist.

**How it works:**

1. The CrowdSec engine analyzes logs and detects suspicious activities on your infrastructure.
2. When malicious activity is detected, CrowdSec creates a decision to block the offending IP address.
3. BunkerWeb, acting as a bouncer, queries the CrowdSec Local API for decisions about incoming requests.
4. If a client's IP address has an active block decision, BunkerWeb denies access to the protected services.
5. Optionally, the Application Security Component can perform deep request inspection for enhanced security.

!!! success "Key benefits"

      1. **Community-Powered Security:** Benefit from threat intelligence shared across the CrowdSec user community.
      2. **Behavioral Analysis:** Detect sophisticated attacks based on behavior patterns, not just signatures.
      3. **Lightweight Integration:** Minimal performance impact on your BunkerWeb instance.
      4. **Multi-Level Protection:** Combine perimeter defense (IP blocking) with application security for in-depth protection.

### Prerequisites

- A CrowdSec Local API that BunkerWeb can reach (typically the agent running on the same host or inside the same Docker network).
- Access to BunkerWeb access logs (`/var/log/bunkerweb/access.log` by default) so the CrowdSec agent can analyse requests.
- `cscli` access on the CrowdSec host to register the BunkerWeb bouncer key.

### Integration workflow

1. Prepare the CrowdSec agent so it ingests BunkerWeb logs.
2. Configure BunkerWeb to query the CrowdSec Local API.
3. Validate the link with the `/crowdsec/ping` API or the admin UI CrowdSec card.

The detailed instructions below follow this sequence.

### Step&nbsp;1 – Prepare CrowdSec to ingest BunkerWeb logs

Follow one of the environment-specific guides below so the CrowdSec agent ingests BunkerWeb access, error, and ModSecurity audit logs. This is what drives the remediation decisions that the plugin will later enforce.

=== "Docker"
    **Acquisition file**

    You will need to run a CrowdSec instance and configure it to parse BunkerWeb logs. Use the dedicated `bunkerweb` value for the `type` parameter in your acquisition file (assuming that BunkerWeb logs are stored as is without additional data):

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    If the collection is not visible from inside the CrowdSec container, execute `docker exec -it <crowdsec-container> cscli hub update` and then restart that container (`docker restart <crowdsec-container>`) so the new assets become available. Replace `<crowdsec-container>` with the name of your CrowdSec container.

    **Application Security Component (*optional*)**

    CrowdSec also provides an [Application Security Component](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) that can be used to protect your application from attacks. If you want to use it, you must create another acquisition file for the AppSec Component:

    ```yaml
    appsec_configs:
      - crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    `appsec_configs` (plural) is a list and appends, so extra AppSec configurations extend `appsec-default` instead of replacing it. The singular `appsec_config` takes a single name and cannot be combined with the plural key — use the plural form if you plan to enable [bot detection](#bot-detection-crowdsec-18).

    **Syslog**

    For container-based integrations, we recommend redirecting the logs of the BunkerWeb container to a syslog service so CrowdSec can access them easily. Here is an example configuration for syslog-ng that will store raw logs coming from BunkerWeb to a local `/var/log/bunkerweb.log` file:

    ```syslog
    @version: 4.10

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    Here is the docker-compose boilerplate that you can use (don’t forget to update the bouncer key):

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for both services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.7.0-beta
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          <<: *bw-env # We use the anchor to avoid repeating the same settings for all services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog # Send logs to syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # The IP address of the syslog service

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # This is the address of the CrowdSec container API in the same network
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # Comment if you don't want to use the AppSec Component
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # Remember to set a stronger key for the bouncer
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      crowdsec:
        image: crowdsecurity/crowdsec:v1.7.8 # Use the latest version but always pin the version for a better stability/security
        volumes:
          - cs-data:/var/lib/crowdsec/data # To persist the CrowdSec data
          - bw-logs:/var/log:ro # The logs of BunkerWeb for CrowdSec to parse
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # The acquisition file for BunkerWeb logs
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Comment if you don't want to use the AppSec Component
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # Remember to set a stronger key for the bouncer
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # If you don't want to use the AppSec Component use this line instead
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # Bind to low ports
          - NET_BROADCAST  # Send broadcasts
          - NET_RAW  # Use raw sockets
          - DAC_READ_SEARCH  # Read files bypassing permissions
          - DAC_OVERRIDE  # Override file permissions
          - CHOWN  # Change ownership
          - SYSLOG  # Write to system logs
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # This is the syslog-ng configuration file
        networks:
            bw-universe:
              ipv4_address: 10.20.30.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Linux"

    You need to install CrowdSec and configure it to parse BunkerWeb logs. Follow the [official documentation](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    To enable CrowdSec to parse BunkerWeb logs, add the following lines to your acquisition file located at `/etc/crowdsec/acquis.yaml`:

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    Update the CrowdSec hub and install the BunkerWeb collection:

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    Now, add your custom bouncer to the CrowdSec API using the `cscli` tool:

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "API key"
        Keep the key generated by the `cscli` command; you will need it later.

    Then restart the CrowdSec service:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Application Security Component (*optional*)**

    If you want to use the AppSec Component, you must create another acquisition file for it located at `/etc/crowdsec/acquis.d/appsec.yaml`:

    ```yaml
    appsec_configs:
      - crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    You will also need to install the AppSec Component's collections:

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Finally, restart the CrowdSec service:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Settings**

    Configure the plugin by adding the following settings to your BunkerWeb configuration file:

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<The key provided by cscli>
    # Comment if you don't want to use the AppSec Component
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    Finally, reload the BunkerWeb service:

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "All-in-one"

    The BunkerWeb All-In-One (AIO) Docker image comes with CrowdSec fully integrated. You don't need to set up a separate CrowdSec instance or manually configure acquisition files for BunkerWeb logs when using the internal CrowdSec agent.

    Refer to the [All-In-One (AIO) Image integration documentation](integrations.md#crowdsec-integration).

### Step&nbsp;2 – Configure BunkerWeb settings

Apply the following environment variables (or values via the scheduler UI/API) so the BunkerWeb instance can talk to the CrowdSec Local API. At a minimum you must set `USE_CROWDSEC`, `CROWDSEC_API`, and a valid `CROWDSEC_API_KEY` that you created with `cscli bouncers add`.

Every setting is `multisite`, so a value set without a prefix applies to all services and a value prefixed with a server name overrides it for that service only.

| Setting                     | Default                | Context   | Multiple | Description                                                                                                     |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Enable CrowdSec:** Set to `yes` to enable the CrowdSec bouncer.                                               |
| `CROWDSEC_API`              | `http://crowdsec:8080` | multisite | no       | **CrowdSec API URL:** The address of the CrowdSec Local API service. Leave empty to disable decision lookups.   |
| `CROWDSEC_API_KEY`          |                        | multisite | no       | **CrowdSec API Key:** The API key for authenticating with the CrowdSec API, obtained using `cscli bouncers add`. |
| `CROWDSEC_MODE`             | `live`                 | multisite | no       | **Operation Mode:** Either `live` (query API for each request) or `stream` (periodically cache all decisions).   |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | multisite | no       | **Internal Traffic:** Set to `yes` to check internal traffic against CrowdSec decisions.                         |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | multisite | no       | **Request Timeout:** Timeout in milliseconds for HTTP requests to the CrowdSec Local API in live mode.           |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | multisite | no       | **Excluded Locations:** Comma-separated list of locations (URIs) to exclude from CrowdSec checks.                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | multisite | no       | **Cache Expiration:** The cache expiration time in seconds for IP decisions in live mode.                        |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | multisite | no       | **Update Frequency:** How often (in seconds) to pull new/expired decisions from the CrowdSec API in stream mode. |

!!! info "How `CROWDSEC_EXCLUDE_LOCATION` matches"
    Each comma-separated entry excludes the URI itself **and everything below it**: `/health` skips `/health` and `/health/live`, but not `/healthcheck` — a separator is always required before the rest of the path. Exclusion is total: an excluded request reaches neither the Local API nor the AppSec Component, so do not exclude a path you still want inspected. In particular, never exclude `/crowdsec-internal`: [bot detection](#bot-detection-crowdsec-18) serves its challenge assets from there and excluding it silently disables the challenge.

#### Application Security Component Settings

| Setting                           | Default       | Context   | Multiple | Description                                                                                           |
| --------------------------------- | ------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |               | multisite | no       | **AppSec URL:** The URL of the CrowdSec Application Security Component. Leave empty to disable AppSec. |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | multisite | no       | **Failure Action:** Action to take when AppSec returns an error. Can be `passthrough` or `deny`.       |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | multisite | no       | **Connect Timeout:** The timeout in milliseconds for connecting to the AppSec Component.               |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | multisite | no       | **Send Timeout:** The timeout in milliseconds for sending data to the AppSec Component.                |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | multisite | no       | **Process Timeout:** The timeout in milliseconds for processing the request in the AppSec Component.   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | multisite | no       | **Always Send:** Set to `yes` to always send requests to AppSec, even if there's an IP-level decision. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | multisite | no       | **SSL Verify:** Set to `yes` to verify the AppSec Component's SSL certificate.                         |

!!! info "About Operation Modes"
    - **Live mode** queries the CrowdSec API for each incoming request, providing real-time protection at the cost of higher latency.
    - **Stream mode** periodically downloads all decisions from the CrowdSec API and caches them locally, reducing latency with a slight delay in applying new decisions.

#### Per-service endpoints

Because the endpoints are `multisite`, services on the same instance can use different CrowdSec components, or only some of them. The two features are independent:

- **Decision lookups** are active when `CROWDSEC_API` is set. Set it to an empty string for a service to skip the Local API entirely.
- **AppSec inspection** is active when `CROWDSEC_APPSEC_URL` is set. Set it to an empty string for a service to skip deep request inspection.

A service with `USE_CROWDSEC` set to `yes` and both URLs empty checks nothing, and the instance logs that neither endpoint is defined.

!!! warning "One decision cache per instance"
    Cached decisions live in a single shared memory zone for the whole instance, keyed by the Local API they came from. Services pointing at the same `CROWDSEC_API` reuse each other's cached decisions, which is what keeps the lookup cheap. Services pointing at different Local APIs never see each other's decisions. Sizing that zone is instance-wide, so a fleet with many distinct Local APIs and large decision lists shares one budget.

!!! info "Bouncer key per Local API"
    `CROWDSEC_API_KEY` is resolved per service like every other setting. When services target different Local APIs, give each one the key registered with `cscli bouncers add` on its own CrowdSec host, otherwise the lookups are rejected as unauthenticated.

### Bot detection (CrowdSec 1.8+)

CrowdSec 1.8 adds bot detection to the AppSec Component. Instead of banning a suspicious client outright, the AppSec Component can answer with a **challenge**: a self-contained page that fingerprints the browser and makes it solve a proof of work, then scores the result on the CrowdSec side. BunkerWeb serves that page exactly as CrowdSec produced it — same status, same headers, same cookie, on the original URI — and never forwards the request to your application. A client that fails is still denied by BunkerWeb's own ban page, so nothing about the blocking experience changes.

Bot detection is **not enabled by default**: the bouncer relays a challenge as soon as the engine issues one, but the engine only issues one once you install the collection and load its configuration.

**Enabling it on a standalone CrowdSec engine**

```shell
cscli collections install crowdsecurity/appsec-bot-challenge
```

Then add the configurations it installed to the AppSec acquisition file, next to `appsec-default`:

```yaml
appsec_configs:
  - crowdsecurity/appsec-default
  - crowdsecurity/appsec-bot-*
labels:
  type: appsec
listen_addr: 0.0.0.0:7422
source: appsec
```

Restart CrowdSec, then confirm the rejections with `cscli alerts list --kind bot-detection`.

Three ready-made bundles set the rejection threshold: `crowdsecurity/appsec-bot-challenge` rejects at a score of 75, `crowdsecurity/appsec-bot-challenge-strict` at 45, and `crowdsecurity/appsec-bot-challenge-permissive` at 100. Install the one you want — they are alternatives, not layers.

**Enabling it on the All-In-One image**

Set `CROWDSEC_EXTRA_COLLECTIONS` on the container and restart it; the entrypoint installs the collection and adds its configurations to the AppSec acquisition file for you:

```shell
docker run -d --name bunkerweb-aio \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_APPSEC_URL=http://127.0.0.1:7422 \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/appsec-bot-challenge" \
  bunkerity/bunkerweb-all-in-one:1.7.0-beta
```

!!! warning "Challenged clients need JavaScript and cookies"
    The challenge page runs a script and stores its result in a cookie. Any legitimate client that has neither — API consumers, monitoring probes, feed readers, most command-line tools — cannot solve it and will keep being challenged. Exclude or allowlist them **on the CrowdSec side** (the bundle ships exclusions for search engines, monitoring, feeds, static files and API paths), not with `CROWDSEC_EXCLUDE_LOCATION`, which switches off every CrowdSec check for that path rather than just the challenge.

!!! warning "The CrowdSec host needs an executable-memory mapping"
    The challenge is obfuscated server-side by a WebAssembly runtime that CrowdSec only runs in compiler mode — there is no interpreter fallback. The **host running CrowdSec** therefore needs SSE4.1 on amd64 (arm64 has no such requirement) and a kernel that allows a writable mapping to be turned executable. A host hardened with W^X, or a restrictive seccomp or SELinux policy, makes CrowdSec log `failed to create wasm runtime in compiler mode` or `the kernel likely denied an executable memory mapping` at startup and bot detection stays off. This is a requirement of the engine's host, not of your visitors' browsers.

!!! tip "Keep the challenge page's Content-Security-Policy"
    CrowdSec always attaches a Content-Security-Policy to the challenge page, and the page needs it to run. BunkerWeb keeps it because `Content-Security-Policy` is in the default `KEEP_UPSTREAM_HEADERS`. Two settings bypass that list and would break the challenge: a `CUSTOM_HEADER` that sets `Content-Security-Policy` yourself, and listing it in `REMOVE_HEADERS`. If you use either, the instance logs a warning at startup naming the setting.

**Reading CrowdSec's verdict in the Reports page**

Every CrowdSec remediation is recorded as a report, and the report now names the verdict instead of only saying `crowdsec`. The **Reports** page reads it as a sentence — *CrowdSec AppSec: bot-detection challenge*, *CrowdSec LAPI: request blocked (scenario: crowdsecurity/http-probing)* — and the report details keep the raw fields underneath: `source` (`appsec` or `lapi`), `action` (`ban`, `captcha` or `challenge`), `http_status` (the status the remediation *declared*, which is not always the one served — a LAPI ban carries none, and an AppSec ban declares 403 while BunkerWeb answers with `DENY_HTTP_STATUS`), plus `scenario`, `origin` and `duration` when the decision came from the Local API.

A served challenge answers with a 200 rather than a block code, and the report filter keeps 4xx, `detect` and stream rows — so on its status alone the challenge would be dropped. The filter now keeps a CrowdSec remediation on its **reason** instead, whatever status it ended on, so the challenge is shown. Under `SECURITY_MODE=detect` nothing is served and the verdict names the remediation that *would* have been applied, which is otherwise invisible — the bouncer's own alert lines only fire on the paths that render a response.

!!! info "The scenario is only there on a fresh decision"
    A Local API decision carries its scenario only on a live query. Once the remediation is cached the cache stores the remediation and nothing else, so the following requests from the same client report the action without a scenario. AppSec verdicts never carry one: they do not come from a decision at all.

### Captcha remediation (rendered by BunkerWeb's antibot)

A CrowdSec `captcha` decision means *prove you are human*, not *go away*. BunkerWeb answers it with its **own antibot challenge** rather than with CrowdSec's captcha page: one look and feel for every challenge your site serves, no second set of captcha keys to manage, and the providers CrowdSec does not offer — `javascript`, `cookie`, `mcaptcha`, `capjs` — become available for a CrowdSec decision too.

| Setting                     | Default   | Context   | Multiple | Description                                                                                                                        |
| --------------------------- | --------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_CAPTCHA_PROVIDER` | `captcha` | multisite | no       | **Captcha challenge:** Which antibot challenge to show when CrowdSec asks for a captcha. Set to `no` to ignore captcha decisions.   |

It takes the same values as `USE_ANTIBOT`: `cookie`, `javascript`, `captcha`, `recaptcha`, `hcaptcha`, `turnstile`, `mcaptcha`, `capjs`. The third-party ones read their keys from the antibot's own `ANTIBOT_*` settings, so there is nothing to configure twice.

!!! warning "The antibot must be enabled on the service"
    The challenge page only exists on a service whose `USE_ANTIBOT` is set to something other than `no` (or that has a workflow challenge rule). On a service without it, a `captcha` decision is **banned** instead of challenged and the instance logs one line naming both settings. `USE_ANTIBOT: "cookie"` is the cheapest way to switch it on: an ordinary visitor is let through in one round trip, while a client CrowdSec flagged is shown the `CROWDSEC_CAPTCHA_PROVIDER` challenge instead.

!!! warning "This changes behaviour on upgrade"
    Until now BunkerWeb bounced on `ban` decisions only, so a `captcha` decision from your Local API was never fetched and had no effect at all. It is now fetched, cached and honoured, and renders the challenge described above. To keep the previous behaviour, set `CROWDSEC_CAPTCHA_PROVIDER: "no"`: captcha decisions are then ignored exactly as before. Note that the widened filter is `BOUNCING_ON_TYPE=all` and not a `ban`+`captcha` pair — the bouncer accepts only one value — so a decision of any **other** type your CrowdSec profiles emit is now honoured as well and, being unknown to the bouncer, applied as a ban. And the opt-out only restores the previous behaviour **fully when every service sharing the same CrowdSec Local API sets it**: the decision cache is partitioned per Local API, not per service (`cache_partition.lua`), so a sibling service left on the default caches the captcha decision and the opting-out service reads it back and bans on it.

!!! tip "`cookie` proves nothing here"
    The `cookie` provider resolves itself without asking the visitor anything. It is a fine cheap value for `USE_ANTIBOT`, but as a `CROWDSEC_CAPTCHA_PROVIDER` it costs two redirects and grants a session-long pass on a decision that means *prove you are human*. Prefer `captcha`, `javascript` or `capjs`.

!!! info "CrowdSec never learns that the captcha was solved"
    The challenge is solved against BunkerWeb, not against the engine, so `cscli metrics` counts no captcha, `CAPTCHA_EXPIRATION` does not apply, and another bouncer on the same Local API still challenges the same client. What holds the answer is the visitor's BunkerWeb session: once solved, that browser is not challenged again for the lifetime of its session — including if a **new** captcha decision lands for the same address in the meantime. Any client without that session (another browser, another device, a cleared cookie jar) is challenged normally.

### Handing the verdict to a security workflow

A CrowdSec verdict can be answered by your own **security workflows** instead of by CrowdSec's own remediation: a rule holding a *CrowdSec verdict* condition can challenge, redirect or block a flagged request on your terms.

| Setting                       | Default | Context   | Multiple | Description                                                                                                                    |
| ----------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `CROWDSEC_DEFER_TO_WORKFLOWS` | `no`    | multisite | no       | **Let security workflows decide:** hand the verdict to the workflows attached to this service instead of applying it here.      |

The condition reads two facts: the verdict **source** (`appsec` or `lapi`) and the **remediation** CrowdSec asked for (`ban` or `captcha`; a `challenge` is served by CrowdSec itself before the workflows run, so it is not offered). A request CrowdSec did not judge leaves the condition undecided, which never matches; a request CrowdSec judged and had nothing against makes it false.

!!! warning "Nothing is opened by default"
    With `no` — the default — CrowdSec applies its verdict itself, exactly as before. With `yes`, the verdict is applied unchanged whenever no workflow rule matched, and the instance logs one line naming both settings when the service has no workflow attached at all.

!!! info "Three answers still come from BunkerWeb while the verdict waits"
    The CORS preflight (`204`), `/robots.txt` and `/security.txt` are generated by BunkerWeb before the workflows run, so a flagged client can still receive those three. None of them reaches your application, and every request that would is checked by the workflow ladder first.

### Example Configurations

=== "Basic Configuration"

    This is a simple configuration for when CrowdSec runs on the same host:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "live"
    ```

=== "Advanced Configuration with AppSec"

    A more comprehensive configuration including the Application Security Component:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "your-api-key-here"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # AppSec Configuration
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

=== "Per-service Configuration"

    AppSec on every public service, decision lookups on a subset, and one service left out entirely. The unprefixed values are the fleet-wide baseline and each service overrides only what differs:

    ```yaml
    MULTISITE: "yes"
    SERVER_NAME: "app1.example.com app2.example.com intranet.example.com"

    # Baseline for every service
    USE_CROWDSEC: "yes"
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_API: "" # No decision lookup unless a service asks for it
    CROWDSEC_API_KEY: ""

    # app1 adds the Local API decision lookup on top of AppSec
    app1.example.com_CROWDSEC_API: "http://crowdsec:8080"
    app1.example.com_CROWDSEC_API_KEY: "your-api-key-here"

    # app2 keeps AppSec only, inheriting the empty CROWDSEC_API baseline

    # intranet is not checked at all
    intranet.example.com_USE_CROWDSEC: "no"
    ```

    A service can also point at a different CrowdSec host altogether, with its own bouncer key:

    ```yaml
    app2.example.com_CROWDSEC_API: "http://crowdsec-dmz:8080"
    app2.example.com_CROWDSEC_API_KEY: "dmz-bouncer-key"
    app2.example.com_CROWDSEC_APPSEC_URL: "http://crowdsec-dmz:7422"
    ```

### Step&nbsp;3 – Validate the integration

- In the scheduler logs, look for `CrowdSec configuration successfully generated` and `CrowdSec bouncer denied request` entries to verify that the plugin is active.
- In the BunkerWeb instance logs, the init phase reports how many bouncers were built and how many services they cover. Services sharing an identical configuration share one bouncer, so the two counts differ when a fleet uses several distinct endpoints.
- On the CrowdSec side, monitor `cscli metrics show` or the CrowdSec Console to ensure BunkerWeb decisions appear as expected.
- In the BunkerWeb UI, open the CrowdSec plugin page to see the status of the integration.
