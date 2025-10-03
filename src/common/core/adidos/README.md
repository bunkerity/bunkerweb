# ADIDOS (Adaptive DDoS Protection System)

ADIDOS is an intelligent load-based antibot control system that automatically monitors remote server CPU load and dynamically enables or disables antibot protection based on configurable thresholds. This helps protect your infrastructure during high-load periods while maintaining user experience during normal operations.

**How it works:**

1. ADIDOS continuously monitors the CPU load of a remote server via SSH connection.
2. When CPU load exceeds the high threshold, antibot protection is automatically enabled.
3. When CPU load drops below the low threshold and cooldown period has passed, antibot protection is automatically disabled.
4. Optional webhook notifications keep you informed of protection status changes.
5. The system uses configurable cooldown periods to prevent rapid toggling of protection.

### How to Use

Follow these steps to enable and configure the ADIDOS feature:

1. **Set up SSH access:** Configure SSH key-based authentication to your monitored server.
2. **Mount SSH keys:** Ensure SSH private key is accessible in the bw-scheduler container.
3. **Enable the feature:** Set the `USE_ADIDOS` setting to `yes` in your BunkerWeb configuration.
4. **Configure monitoring:** Set the target host, thresholds, and other ADIDOS settings.
5. **Optional:** Configure webhook notifications for real-time alerts.

!!! important "SSH Requirements"
    The bw-scheduler container already includes SSH client pre-installed. You only need to:
    - Mount or manually place an SSH private key in the container at the path specified in `ADIDOS_SSH_KEY` (default: `/usr/share/bunkerweb/scheduler/.ssh/id_rsa`)
    - Ensure the key has passwordless access to the monitored server
    - The SSH client is already available in the container via the src/scheduler/Dockerfile installation (at line  44 add `RUN apk add .... ssh`) or by installing it manually (docker exec bw-scheduler bash -c "apk add --no-cache openssh && which ssh")
    - The SSH client version must be at least 7.0 (docker exec bw-scheduler bash -c "ssh -V")

!!! warning "Docker Configuration Required"
    When using Docker, you **must** mount the SSH directory to the bw-scheduler container. See the [Docker Configuration](#docker-configuration) section below for the complete setup.

### Configuration Settings

The following settings control ADIDOS behavior:

| Setting                    | Default                                              | Context | Multiple | Description                                                                                    |
| -------------------------- | ---------------------------------------------------- | ------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_ADIDOS`               | `no`                                                 | global  | no       | **Enable ADIDOS:** Set to `yes` to enable load-based antibot control.                         |
| `ADIDOS_HOST`              | `85.198.111.8`                                       | global  | no       | **Monitor Host:** Remote server hostname or IP address to monitor for CPU load.               |
| `ADIDOS_SSH_KEY`           | `/usr/share/bunkerweb/scheduler/.ssh/id_rsa`         | global  | no       | **SSH Private Key:** Path to SSH private key file for remote server access.                   |
| `ADIDOS_THRESHOLD_HIGH`    | `80`                                                 | global  | no       | **High Load Threshold:** CPU load percentage to trigger antibot activation.                   |
| `ADIDOS_THRESHOLD_LOW`     | `50`                                                 | global  | no       | **Low Load Threshold:** CPU load percentage to trigger antibot deactivation.                  |
| `ADIDOS_COOLDOWN_MINUTES`  | `5`                                                  | global  | no       | **Cooldown Period:** Minutes to wait before disabling antibot after load drops.               |
| `ADIDOS_CAPTCHA_TYPE`      | `no`                                                 | global  | no       | **Captcha Type:** Type of antibot challenge to activate (cookie, javascript, captcha, etc.).  |
| `ADIDOS_SERVICES`          |                                                      | global  | no       | **Services:** Space-separated list of services to apply antibot protection to.                |
| `ADIDOS_USE_WEBHOOK`       | `no`                                                 | global  | no       | **Enable Webhooks:** Set to `yes` to enable webhook notifications.                            |
| `ADIDOS_WEB_HOOK_URL`      |                                                      | global  | no       | **Webhook URL:** HTTP endpoint to send notifications to.                                      |
| `ADIDOS_WEB_HOOK_BODY`     | `{\"chat\": \"<TG_CHAT_ID>\", \"text\": \"{{MESSAGE}}\"}` | global  | no       | **Webhook Body:** Template for webhook payload. Use `{{MESSAGE}}` placeholder for content.    |
| `ADIDOS_LOG`               | `no`                                                 | global  | no       | **Enable Logging:** Set to `yes` to enable detailed ADIDOS logging.                           |

### Supported Antibot Types

ADIDOS can activate any of the following antibot challenge types:

- **no** - No antibot protection
- **cookie** - Simple cookie-based challenge
- **javascript** - JavaScript computational challenge
- **captcha** - Image-based CAPTCHA challenge
- **recaptcha** - Google reCAPTCHA integration
- **hcaptcha** - hCaptcha integration
- **turnstile** - Cloudflare Turnstile integration
- **mcaptcha** - mCaptcha integration

For external services (reCAPTCHA, hCaptcha, Turnstile, mCaptcha), you must configure the appropriate API keys in the antibot plugin settings.

### Webhook Notifications

ADIDOS can send webhook notifications when antibot protection is enabled or disabled. This is useful for monitoring and alerting purposes.

**Webhook Message Format:**
- **Activation:** `🛡️ ADIDOS: antibot enabled, current load {load}%`
- **Deactivation:** `✅ ADIDOS: antibot disabled after {duration} activity, current load {load}%`

**Webhook Configuration Examples:**

=== \"Telegram Bot\"

    ```yaml
    ADIDOS_USE_WEBHOOK: \"yes\"
    ADIDOS_WEB_HOOK_URL: \"https://api.telegram.org/bot<BOT_TOKEN>/sendMessage\"
    ADIDOS_WEB_HOOK_BODY: '{\"chat_id\": \"<CHAT_ID>\", \"text\": \"{{MESSAGE}}\"}'
    ```

=== \"Discord Webhook\"

    ```yaml
    ADIDOS_USE_WEBHOOK: \"yes\"
    ADIDOS_WEB_HOOK_URL: \"https://discord.com/api/webhooks/<WEBHOOK_ID>/<WEBHOOK_TOKEN>\"
    ADIDOS_WEB_HOOK_BODY: '{\"content\": \"{{MESSAGE}}\"}'
    ```

=== \"Slack Webhook\"

    ```yaml
    ADIDOS_USE_WEBHOOK: \"yes\"
    ADIDOS_WEB_HOOK_URL: \"https://hooks.slack.com/services/<WEBHOOK_PATH>\"
    ADIDOS_WEB_HOOK_BODY: '{\"text\": \"{{MESSAGE}}\"}'
    ```

### Docker Configuration

When using ADIDOS with Docker, you must mount the SSH directory to the bw-scheduler container. The SSH client is already pre-installed in the container. Here's the complete configuration:

```yaml
bw-scheduler:
  image: bunkerity/bunkerweb-scheduler:1.6.3
  user: $(id -u):$(id -g)
  env_file:
    - .env
  environment:
    <<: *bw-env
    BUNKERWEB_INSTANCES: \"${BUNKERWEB_INSTANCES}\"
    MULTISITE: \"${MULTISITE}\"
    DATABASE_URI: \"${DATABASE_URI}\"
    SERVE_FILES: \"${SERVE_FILES}\"
    DISABLE_DEFAULT_SERVER: \"${DISABLE_DEFAULT_SERVER}\"
    USE_CLIENT_CACHE: \"${USE_CLIENT_CACHE}\"
    USE_GZIP: \"${USE_GZIP}\"
    AUTO_LETS_ENCRYPT: \"${AUTO_LETS_ENCRYPT}\"
    EMAIL_LETS_ENCRYPT: \"${EMAIL_LETS_ENCRYPT}\"
    ${SERVER_NAME}_USE_TEMPLATE: \"ui\"
    ${SERVER_NAME}_USE_REVERSE_PROXY: \"yes\"
    ${SERVER_NAME}_REVERSE_PROXY_URL: \"${REVERSE_PROXY_URL}\" # Change it to a hard to guess URI
    ${SERVER_NAME}_REVERSE_PROXY_HOST: \"${REVERSE_PROXY_HOST}\"
  volumes:
    - ./data/bw-storage:/data # This is used to persist the cache and other data like the backups
    - ~/.ssh:/usr/share/bunkerweb/scheduler/.ssh # SSH keys for ADIDOS monitoring
  restart: \"unless-stopped\"
  networks:
    - bw-universe
    - bw-db
  depends_on:
    bw-db:
      condition: service_healthy
      restart: true
    bw-redis:
      condition: service_healthy
      restart: true
  logging:
    driver: syslog
    options:
      tag: \"bw-scheduler\" # This will be the tag used by syslog-ng to create the log file
      syslog-address: \"udp://${SYSLOG_NG_IP}:514\" # This is the syslog-ng container address
```

!!! important \"SSH Client Pre-installed\"
    The bw-scheduler container comes with SSH client pre-installed via the Dockerfile. You don't need to modify the Dockerfile or install SSH manually. The installation is handled by this line in the Dockerfile:
    ```dockerfile
    RUN apk add --no-cache bash unzip libgcc libstdc++ libpq openssl libmagic mariadb-connector-c mariadb-client postgresql-client sqlite tzdata sed grep ssh curl
    ```

!!! important \"SSH Key Requirements\"
    - The SSH private key must be readable by the user running the bw-scheduler container
    - The key must have passwordless access to the monitored server
    - Ensure the `~/.ssh/known_hosts` file contains the monitored server's host key, or ADIDOS will use `StrictHostKeyChecking=no`

### Example Configurations

=== \"Basic Configuration\"

    ```yaml
    USE_ADIDOS: \"yes\"
    ADIDOS_HOST: \"192.168.1.100\"
    ADIDOS_SSH_KEY: \"/usr/share/bunkerweb/scheduler/.ssh/id_rsa\"
    ADIDOS_THRESHOLD_HIGH: \"80\"
    ADIDOS_THRESHOLD_LOW: \"50\"
    ADIDOS_COOLDOWN_MINUTES: \"5\"
    ADIDOS_CAPTCHA_TYPE: \"captcha\"
    ADIDOS_SERVICES: \"example.com www.example.com\"
    ```

=== \"With Webhook Notifications\"

    ```yaml
    USE_ADIDOS: \"yes\"
    ADIDOS_HOST: \"192.168.1.100\"
    ADIDOS_SSH_KEY: \"/usr/share/bunkerweb/scheduler/.ssh/id_rsa\"
    ADIDOS_THRESHOLD_HIGH: \"75\"
    ADIDOS_THRESHOLD_LOW: \"40\"
    ADIDOS_COOLDOWN_MINUTES: \"10\"
    ADIDOS_CAPTCHA_TYPE: \"javascript\"
    ADIDOS_SERVICES: \"api.example.com\"
    ADIDOS_USE_WEBHOOK: \"yes\"
    ADIDOS_WEB_HOOK_URL: \"https://api.telegram.org/bot<TOKEN>/sendMessage\"
    ADIDOS_WEB_HOOK_BODY: '{\"chat_id\": \"<CHAT_ID>\", \"text\": \"{{MESSAGE}}\"}'
    ADIDOS_LOG: \"yes\"
    ```

=== \"High-Security Configuration\"

    ```yaml
    USE_ADIDOS: \"yes\"
    ADIDOS_HOST: \"production-server.example.com\"
    ADIDOS_SSH_KEY: \"/usr/share/bunkerweb/scheduler/.ssh/production_key\"
    ADIDOS_THRESHOLD_HIGH: \"70\"
    ADIDOS_THRESHOLD_LOW: \"30\"
    ADIDOS_COOLDOWN_MINUTES: \"15\"
    ADIDOS_CAPTCHA_TYPE: \"recaptcha\"
    ADIDOS_SERVICES: \"app.example.com api.example.com\"
    ADIDOS_USE_WEBHOOK: \"yes\"
    ADIDOS_WEB_HOOK_URL: \"https://monitoring.example.com/webhook\"
    ADIDOS_WEB_HOOK_BODY: '{\"alert\": \"ADIDOS\", \"message\": \"{{MESSAGE}}\", \"timestamp\": \"{{TIMESTAMP}}\"}'
    ADIDOS_LOG: \"yes\"
    ```

### Monitoring and Troubleshooting

**Common Issues:**

1. **SSH Connection Failed:**
   - Verify SSH key permissions (should be 600)
   - Check if the monitored server is accessible
   - Ensure SSH key is properly mounted in the container
   - SSH client is pre-installed, no additional installation needed

2. **Load Detection Issues:**
   - Verify the monitored server has `top` command available
   - Check if the SSH user has sufficient permissions
   - Enable logging with `ADIDOS_LOG: \"yes\"` for detailed diagnostics

3. **Webhook Delivery Failed:**
   - Verify webhook URL is accessible from the container
   - Check webhook body format matches the target service requirements
   - Review container logs for webhook error messages

**Monitoring Commands:**

```bash
# Check ADIDOS logs
docker logs bw-scheduler | grep ADIDOS

# Test SSH connection manually
docker exec bw-scheduler ssh -i /usr/share/bunkerweb/scheduler/.ssh/id_rsa user@target-host \"top -bn1 | grep 'Cpu(s)'\"

# Check current antibot state
docker exec bw-scheduler cat /data/cache/adidos-monitor/antibot_state

# Verify SSH client is available
docker exec bw-scheduler which ssh
```

### Security Considerations

- **SSH Key Security:** Use dedicated SSH keys with minimal privileges for monitoring
- **Network Access:** Ensure the monitored server is only accessible from trusted networks
- **Webhook Security:** Use HTTPS endpoints and consider authentication for webhook URLs
- **Threshold Tuning:** Set appropriate thresholds to avoid false positives during normal load spikes
- **Cooldown Periods:** Configure adequate cooldown periods to prevent rapid protection toggling
- **Container Security:** The SSH client is securely installed in the container during build time

### Technical Notes

**SSH Installation in Container:**
The bw-scheduler container includes SSH client pre-installed through the Dockerfile. The relevant installation line is:
```dockerfile
RUN apk add --no-cache bash unzip libgcc libstdc++ libpq openssl libmagic mariadb-connector-c mariadb-client postgresql-client sqlite tzdata sed grep ssh curl
```

This means you don't need to:
- Modify the Dockerfile
- Install SSH manually
- Build custom images

You only need to provide the SSH keys and proper configuration.