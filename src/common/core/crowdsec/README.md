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
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

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
        image: bunkerity/bunkerweb:1.6.7-rc1
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
        image: bunkerity/bunkerweb-scheduler:1.6.7-rc1
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
        image: crowdsecurity/crowdsec:v1.7.3 # Use the latest version but always pin the version for a better stability/security
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
    appsec_config: crowdsecurity/appsec-default
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

| Setting                     | Default                | Context   | Multiple | Description                                                                                                      |
| --------------------------- | ---------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Enable CrowdSec:** Set to `yes` to enable the CrowdSec bouncer.                                                |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | no       | **CrowdSec API URL:** The address of the CrowdSec Local API service.                                             |
| `CROWDSEC_API_KEY`          |                        | global    | no       | **CrowdSec API Key:** The API key for authenticating with the CrowdSec API, obtained using `cscli bouncers add`. |
| `CROWDSEC_MODE`             | `live`                 | global    | no       | **Operation Mode:** Either `live` (query API for each request) or `stream` (periodically cache all decisions).   |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | no       | **Internal Traffic:** Set to `yes` to check internal traffic against CrowdSec decisions.                         |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | no       | **Request Timeout:** Timeout in milliseconds for HTTP requests to the CrowdSec Local API in live mode.           |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | no       | **Excluded Locations:** Comma-separated list of locations (URIs) to exclude from CrowdSec checks.                |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | no       | **Cache Expiration:** The cache expiration time in seconds for IP decisions in live mode.                        |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | no       | **Update Frequency:** How often (in seconds) to pull new/expired decisions from the CrowdSec API in stream mode. |

#### Application Security Component Settings

| Setting                           | Default       | Context | Multiple | Description                                                                                            |
| --------------------------------- | ------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `CROWDSEC_APPSEC_URL`             |               | global  | no       | **AppSec URL:** The URL of the CrowdSec Application Security Component. Leave empty to disable AppSec. |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough` | global  | no       | **Failure Action:** Action to take when AppSec returns an error. Can be `passthrough` or `deny`.       |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`         | global  | no       | **Connect Timeout:** The timeout in milliseconds for connecting to the AppSec Component.               |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`         | global  | no       | **Send Timeout:** The timeout in milliseconds for sending data to the AppSec Component.                |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`         | global  | no       | **Process Timeout:** The timeout in milliseconds for processing the request in the AppSec Component.   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`          | global  | no       | **Always Send:** Set to `yes` to always send requests to AppSec, even if there's an IP-level decision. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`          | global  | no       | **SSL Verify:** Set to `yes` to verify the AppSec Component's SSL certificate.                         |

!!! info "About Operation Modes"
    - **Live mode** queries the CrowdSec API for each incoming request, providing real-time protection at the cost of higher latency.
    - **Stream mode** periodically downloads all decisions from the CrowdSec API and caches them locally, reducing latency with a slight delay in applying new decisions.

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

### Step&nbsp;3 – Validate the integration

- In the scheduler logs, look for `CrowdSec configuration successfully generated` and `CrowdSec bouncer denied request` entries to verify that the plugin is active.
- On the CrowdSec side, monitor `cscli metrics show` or the CrowdSec Console to ensure BunkerWeb decisions appear as expected.
- In the BunkerWeb UI, open the CrowdSec plugin page to see the status of the integration.
