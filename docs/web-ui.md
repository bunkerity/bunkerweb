# Web UI

## Role of the Web UI

The Web UI is the visual control plane for BunkerWeb. It drives services, global settings, bans, plugins, jobs, cache, logs, and upgrades without touching the CLI. It is a Flask app served by Gunicorn and normally sits behind a BunkerWeb reverse proxy.

!!! warning "Keep it behind BunkerWeb"
    The UI can change configuration, run jobs, and deploy custom snippets. Keep it on a trusted network, route it through BunkerWeb, and gate it with strong credentials and 2FA.

!!! info "Quick facts"
    - Default listener: `0.0.0.0:7000` in containers, `127.0.0.1:7000` in packages (change with `UI_LISTEN_ADDR`/`UI_LISTEN_PORT`)
    - Reverse-proxy aware: honors `X-Forwarded-*` via `UI_FORWARDED_ALLOW_IPS`; set `PROXY_NUMBERS` when multiple proxies add headers
    - Auth: local admin account (password policy enforced), optional roles, TOTP 2FA backed by `TOTP_ENCRYPTION_KEYS`
    - Sessions: signed with `FLASK_SECRET`, default lifetime 12h, pinned to IP and User-Agent; `ALWAYS_REMEMBER` controls persistent cookies
    - Logs: `/var/log/bunkerweb/ui.log` (+ access log when captured), UID/GID 101 inside the container
    - Health: optional `GET /healthcheck` when `ENABLE_HEALTHCHECK=yes`
    - Dependencies: shares the BunkerWeb database and talks to the API to reload, ban, or query instances

## Security checklist

- Run the UI behind BunkerWeb on an internal network; pick a hard-to-guess `REVERSE_PROXY_URL` and restrict source IPs.
- Set strong `ADMIN_USERNAME` / `ADMIN_PASSWORD`; enable `OVERRIDE_ADMIN_CREDS=yes` only when you intentionally want to reset credentials.
- Provide `TOTP_ENCRYPTION_KEYS` and enable TOTP on admin accounts; keep recovery codes safe.
- Use TLS (terminate at BunkerWeb or set `UI_SSL_ENABLED=yes` with cert/key paths); set `UI_FORWARDED_ALLOW_IPS` to trusted proxies.
- Persist secrets: mount `/var/lib/bunkerweb` so `FLASK_SECRET`, Biscuit keys, and TOTP material survive restarts.
- Keep `CHECK_PRIVATE_IP=yes` (default) to bind sessions to the client IP and `ALWAYS_REMEMBER=no` unless you explicitly want long-lived cookies.
- Ensure `/var/log/bunkerweb` is writable by UID/GID 101 (or the mapped ID when running rootless) so the UI can read logs.

## Run it

The UI expects the scheduler/(BunkerWeb) API/redis/database stack to be reachable.

=== "Quickstart (wizard)"

    Use the published images and the [quickstart guide](quickstart-guide.md#__tabbed_1_3) layout to bring the stack up, then finish the setup via the wizard in your browser.

=== "Advanced (preseeded env)"

    Skip the wizard by seeding credentials and network settings up front; example Compose with a syslog sidecar:

    ```yaml
    x-service-env: &service-env
      # We anchor the environment variables to avoid duplication
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database
      LOG_TYPES: "stderr syslog" # Service logs from supporting components
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          # Optional API token when securing API access
          API_TOKEN: "" # Make sure that it matches the one set in the scheduler
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *service-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          API_WHITELIST_IP: "127.0.0.0/24 10.20.30.0/24"
          # Optional API token when securing API access
          API_TOKEN: "" # Make sure that it matches the one set in the bunkerweb service
          ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
          ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"
          DISABLE_DEFAULT_SERVER: "yes"
          www.example.com_USE_TEMPLATE: "ui"
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/changeme" # Change it to a hard-to-guess URI
          www.example.com_REVERSE_PROXY_HOST: "http://bw-ui:7000"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8-rc3
        environment:
          <<: *service-env
          ADMIN_USERNAME: "admin"
          ADMIN_PASSWORD: "Str0ng&P@ss!" # Remember to set a stronger password for the admin user
          TOTP_ENCRYPTION_KEYS: "set-me"  # Remember to set a stronger secret key (see below)
          UI_FORWARDED_ALLOW_IPS: "10.20.30.0/24"
        volumes:
          - bw-logs:/var/log/bunkerweb # This is the volume used to store the logs
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

      bw-syslog:
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
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"


    Add `bunkerweb-autoconf` and apply labels on the UI container instead of explicit `BUNKERWEB_INSTANCES`. The scheduler still reverse-proxies the UI through the `ui` template and a secret `REVERSE_PROXY_URL`.

=== "Linux"

    The package ships a `bunkerweb-ui` systemd service. It is activated automatically when using the easy-install flow (the wizard also auto-starts by default). To adjust or reconfigure, edit `/etc/bunkerweb/ui.env`, then:

    ```bash
    sudo systemctl enable --now bunkerweb-ui
    sudo systemctl restart bunkerweb-ui  # after changes
    ```

    Reverse-proxy it from BunkerWeb (`ui` template, `REVERSE_PROXY_URL=/changeme`, upstream `http://127.0.0.1:7000`). Mount `/var/lib/bunkerweb` and `/var/log/bunkerweb` so secrets and logs persist.

### Linux vs Docker specifics

- Bind defaults: Docker images listen on `0.0.0.0:7000`; Linux packages bind to `127.0.0.1:7000`. Override with `UI_LISTEN_ADDR` / `UI_LISTEN_PORT`.
- Proxy headers: `UI_FORWARDED_ALLOW_IPS` defaults to `*`; on Linux installations set it to your reverse proxy IPs for tighter defaults.
- Secrets and state: `/var/lib/bunkerweb` stores `FLASK_SECRET`, Biscuit keys, and TOTP material. Mount it in Docker; on Linux it is created and managed by the package scripts.
- Logs: `/var/log/bunkerweb` must be readable by UID/GID 101 (or the mapped UID in rootless Docker). Packages create the path; containers need a volume with correct ownership.
- Wizard behavior: easy-install on Linux starts the UI and wizard automatically; Docker users reach the wizard via the reverse-proxied URL unless they preseed env vars.

## Authentication and sessions

- Admin account: create via setup wizard or `ADMIN_USERNAME` / `ADMIN_PASSWORD`. Passwords must include lowercase, uppercase, digit, and special chars. `OVERRIDE_ADMIN_CREDS=yes` forces reseeding even if an account exists.
- Roles: `admin`, `writer`, and `reader` are created automatically; accounts live in the database.
- Secrets: `FLASK_SECRET` is stored at `/var/lib/bunkerweb/.flask_secret`; Biscuit keys live next to it and can be provided via `BISCUIT_PUBLIC_KEY` / `BISCUIT_PRIVATE_KEY`.


    ```bash
    python3 -c "from passlib import totp; print(totp.generate_secret())"
    ```

    Recovery codes are shown once in the UI; losing the encryption keys wipes stored TOTP secrets.
- Sessions: default lifetime is 12h (`SESSION_LIFETIME_HOURS`). Sessions are pinned to IP and User-Agent; `CHECK_PRIVATE_IP=no` relaxes the IP check for private ranges only. `ALWAYS_REMEMBER=yes` always sets persistent cookies.
- Remember to set `PROXY_NUMBERS` if multiple proxies append `X-Forwarded-*` headers.

## Configuration sources and precedence

1. Environment variables (including Docker/Compose `environment:`)
2. Secrets in `/run/secrets/<VAR>` (Docker)
3. Env file at `/etc/bunkerweb/ui.env` (Linux packages)
4. Built-in defaults

## Configuration reference

### Runtime & time zone

| Setting | Description                                 | Accepted values                                | Default                                |
| ------- | ------------------------------------------- | ---------------------------------------------- | -------------------------------------- |
| `TZ`    | Time zone for UI logs and scheduled actions | TZ database name (e.g., `UTC`, `Europe/Paris`) | unset (container default, usually UTC) |

### Listener & TLS

| Setting                             | Description                                | Accepted values                 | Default                                    |
| ----------------------------------- | ------------------------------------------ | ------------------------------- | ------------------------------------------ |
| `UI_LISTEN_ADDR`                    | Bind address for the UI                    | IP or hostname                  | `0.0.0.0` (Docker) / `127.0.0.1` (package) |
| `UI_LISTEN_PORT`                    | Bind port for the UI                       | Integer                         | `7000`                                     |
| `LISTEN_ADDR`, `LISTEN_PORT`        | Fallbacks when UI-specific vars are unset  | IP/hostname, integer            | `0.0.0.0`, `7000`                          |
| `UI_SSL_ENABLED`                    | Enable TLS in the UI container             | `yes` or `no`                   | `no`                                       |
| `UI_SSL_CERTFILE`, `UI_SSL_KEYFILE` | PEM cert and key paths when TLS is enabled | File paths                      | unset                                      |
| `UI_SSL_CA_CERTS`                   | Optional CA/chain                          | File path                       | unset                                      |
| `UI_FORWARDED_ALLOW_IPS`            | Trusted proxy IPs for `X-Forwarded-*`      | Comma/space-separated IPs/CIDRs | `*`                                        |

### Auth, sessions, and cookies

| Setting                                     | Description                                                              | Accepted values          | Default                   |
| ------------------------------------------- | ------------------------------------------------------------------------ | ------------------------ | ------------------------- |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`          | Seed admin account (password policy enforced)                            | Strings                  | unset                     |
| `OVERRIDE_ADMIN_CREDS`                      | Force updating admin credentials from env                                | `yes` or `no`            | `no`                      |
| `FLASK_SECRET`                              | Session signing secret (persisted to `/var/lib/bunkerweb/.flask_secret`) | Hex/base64/opaque string | auto-generated            |
| `TOTP_ENCRYPTION_KEYS` (`TOTP_SECRETS`)     | Encryption keys for TOTP secrets (space-separated or JSON map)           | Strings / JSON           | auto-generated if missing |
| `BISCUIT_PUBLIC_KEY`, `BISCUIT_PRIVATE_KEY` | Optional Biscuit keys (hex) used to mint UI tokens                       | Hex strings              | auto-generated & stored   |
| `SESSION_LIFETIME_HOURS`                    | Session lifetime                                                         | Number (hours)           | `12`                      |
| `ALWAYS_REMEMBER`                           | Always enable "remember me" cookies                                      | `yes` or `no`            | `no`                      |
| `CHECK_PRIVATE_IP`                          | Enforce IP pinning (skips change inside private ranges when `no`)        | `yes` or `no`            | `yes`                     |
| `PROXY_NUMBERS`                             | Number of proxy hops to trust for `X-Forwarded-*`                        | Integer                  | `1`                       |

### Logging

| Setting                         | Description                                                   | Accepted values                                 | Default                                       |
| ------------------------------- | ------------------------------------------------------------- | ----------------------------------------------- | --------------------------------------------- |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Base log level / override                                     | `debug`, `info`, `warning`, `error`, `critical` | `info`                                        |
| `LOG_TYPES`                     | Destinations                                                  | Space-separated `stderr`/`file`/`syslog`        | `stderr`                                      |
| `LOG_FILE_PATH`                 | Path for file logging (`file` or `CAPTURE_OUTPUT=yes`)        | File path                                       | `/var/log/bunkerweb/ui.log` when file/capture |
| `CAPTURE_OUTPUT`                | Send Gunicorn stdout/stderr to log handlers                   | `yes` or `no`                                   | `no`                                          |
| `LOG_SYSLOG_ADDRESS`            | Syslog target (`udp://host:514`, `tcp://host:514`, or socket) | Host:port / URL / socket path                   | unset                                         |
| `LOG_SYSLOG_TAG`                | Syslog ident/tag                                              | String                                          | `bw-ui`                                       |

### Misc runtime

| Setting                         | Description                                        | Accepted values | Default                              |
| ------------------------------- | -------------------------------------------------- | --------------- | ------------------------------------ |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn workers/threads                           | Integer         | `cpu_count()-1` (min 1), `workers*2` |
| `ENABLE_HEALTHCHECK`            | Expose `GET /healthcheck`                          | `yes` or `no`   | `no`                                 |
| `FORWARDED_ALLOW_IPS`           | Deprecated alias for proxy allowlist               | IPs/CIDRs       | `*`                                  |
| `DISABLE_CONFIGURATION_TESTING` | Skip test reloads when pushing config to instances | `yes` or `no`   | `no`                                 |
| `IGNORE_REGEX_CHECK`            | Skip regex validation on settings                  | `yes` or `no`   | `no`                                 |

## Log access

The UI reads NGINX/service logs from `/var/log/bunkerweb`. Feed that directory from a syslog daemon or volume:

- Container UID/GID is 101. On the host, set permissions so files are readable: `chown root:101 bw-logs && chmod 770 bw-logs` (adjust for rootless mappings).
- Send BunkerWeb access/error logs via `ACCESS_LOG` / `ERROR_LOG` to the syslog sidecar; send component logs with `LOG_TYPES=syslog`.


```conf
@version: 4.10

# Source configuration to receive logs from Docker containers
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Template to format log messages
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Destination configuration to write logs to dynamically named files
destination d_dyna_file {
  file(
    "/var/log/bunkerweb/${PROGRAM}.log"
    template(t_imp)
    owner("101")
    group("101")
    dir_owner("root")
    dir_group("101")
    perm(0440)
    dir_perm(0770)
    create_dirs(yes)
    logrotate(
      enable(yes),
      size(100MB),
      rotations(7)
    )
  );
};

# Log path to direct logs to dynamically named files
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Capabilities

- Dashboard for requests, bans, cache, and jobs; restart/reload instances.
- Create/update/delete services and global settings with validation against plugin schemas.
- Upload and manage custom configs (NGINX/ModSecurity) and plugins (external or PRO).
- View logs, search reports, and inspect cached artefacts.
- Manage UI users, roles, sessions, and TOTP with recovery codes.
- Upgrade to BunkerWeb PRO and inspect license status from the dedicated page.

## Upgrade to PRO {#upgrade-to-pro}

!!! tip "BunkerWeb PRO free trial"
    Use the code `freetrial` on the [BunkerWeb panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) for a one-month trial.


<figure markdown>
<figure markdown>
  ![PRO upgrade](assets/img/ui-pro.png){ align=center, width="700" }
</figure>

## Translations (i18n)

The Web UI is available in multiple languages thanks to community contributions. Translation strings are stored as per-locale JSON files (for example `en.json`, `fr.json`, …). Each locale has a clear provenance indicating whether it was translated manually or generated using AI, as well as its review status.

### Available languages and contributors

| Language              | Locale | Created by                    | Reviewed by              |
| --------------------- | ------ | ----------------------------- | ------------------------ |
| Arabic                | `ar`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Bengali               | `bn`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Breton                | `br`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| German                | `de`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| English               | `en`   | Manual (@TheophileDiot)       | Manual (@TheophileDiot)  |
| Spanish               | `es`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| French                | `fr`   | Manual (@TheophileDiot)       | Manual (@TheophileDiot)  |
| Hindi                 | `hi`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Italian               | `it`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Korean                | `ko`   | Manual (@rayshoo)             | Manual (@rayshoo)        |
| Polish                | `pl`   | Manual (@tomkolp) via Weblate | Manual (@tomkolp)        |
| Portuguese            | `pt`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Russian               | `ru`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Turkish               | `tr`   | Manual (@wiseweb-works)       | Manual (@wiseweb-works)  |
| Chinese (Traditional) | `tw`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Urdu                  | `ur`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |
| Chinese (Simplified)  | `zh`   | AI (Google:Gemini-2.5-pro)    | AI (Google:Gemini-3-pro) |

> 💡 Some translations may be partial. Manual review is encouraged, especially for critical UI elements.

### How to contribute

Translation contributions follow the standard BunkerWeb contribution workflow:

1. **Create or update the locale file**
   - Copy `src/ui/app/static/locales/en.json` and rename it to your locale code (for example `de.json`).
   - Translate **values only**; keys must remain unchanged.

2. **Register the language**
   - Add or update the language entry in `src/ui/app/lang_config.py` (locale code, display name, flag, English name).
     This file is the single source of truth for supported languages.

3. **Update documentation and provenance**
   - `src/ui/app/static/locales/README.md` → add the new language to the provenance table (created by / reviewed by).
   - `README.md` → ensure the project-level documentation reflects the new supported language.
   - `docs/web-ui.md` → update the Web UI documentation (this Translations section).
   - `docs/*/web-ui.md` → update the corresponding translated Web UI documentation with the same Translations section.

4. **Open a pull request**
   - Clearly state whether the translation was done manually or with an AI tool.
   - For non-trivial additions (new language or major updates), consider opening an issue first to discuss the change.

By contributing translations, you help make BunkerWeb accessible to a broader, international audience.
