The Bad Behavior plugin protects your website by automatically detecting and banning IP addresses that generate too many errors or "bad" HTTP status codes within a specified period of time. This helps defend against brute force attacks, web scrapers, vulnerability scanners, and other malicious activities that might generate numerous error responses.

Attackers often generate "suspicious" HTTP status codes when probing for or exploiting vulnerabilities—codes that a typical user is unlikely to trigger within a given time frame. By detecting this behavior, BunkerWeb can automatically ban the offending IP address, forcing the attacker to use a new IP address to continue their attempts.

**How it works:**

1. The plugin monitors HTTP responses from your site.
2. When a visitor receives a "bad" HTTP status code (like 400, 401, 403, 404, etc.), the counter for that IP address is incremented.
3. If an IP address exceeds the configured threshold of bad status codes within the specified time period, the IP is automatically banned.
4. Banned IPs can be blocked either at the service level (just for the specific site) or globally (across all sites), depending on your configuration.
5. Bans automatically expire after the configured ban duration, or remain permanent if configured with `0`.

!!! success "Key benefits"

      1. **Automatic Protection:** Detects and blocks potentially malicious clients without requiring manual intervention.
      2. **Customizable Rules:** Fine-tune what constitutes "bad behavior" based on your specific needs.
      3. **Resource Conservation:** Prevents malicious actors from consuming server resources with repeated invalid requests.
      4. **Flexible Scope:** Choose whether bans should apply just to the current service or globally across all services.
      5. **Ban Duration Control:** Set temporary bans that automatically expire after the configured duration, or permanent bans that remain until manually removed.

### How to Use

Follow these steps to configure and use the Bad Behavior feature:

1. **Enable the feature:** The Bad Behavior feature is enabled by default. If needed, you can control this with the `USE_BAD_BEHAVIOR` setting.
2. **Configure status codes:** Define which HTTP status codes should be considered "bad" using the `BAD_BEHAVIOR_STATUS_CODES` setting.
3. **Set threshold values:** Determine how many "bad" responses should trigger a ban using the `BAD_BEHAVIOR_THRESHOLD` setting.
4. **Configure time periods:** Specify the duration for counting bad responses and the ban duration using the `BAD_BEHAVIOR_COUNT_TIME` and `BAD_BEHAVIOR_BAN_TIME` settings.
5. **Choose ban scope:** Decide whether the bans should apply only to the current service or globally across all services using the `BAD_BEHAVIOR_BAN_SCOPE` setting.

!!! tip "Stream Mode"
    In **stream mode**, only the `444` status code is considered "bad" and will trigger this behavior.

### Configuration Settings

| Setting                     | Default                       | Context   | Multiple | Description                                                                                                                                                                           |
| --------------------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | no       | **Enable Bad Behavior:** Set to `yes` to enable the bad behavior detection and banning feature.                                                                                       |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | no       | **Bad Status Codes:** List of HTTP status codes that will be counted as "bad" behavior when returned to a client.                                                                     |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | no       | **Threshold:** The number of "bad" status codes an IP can generate within the counting period before being banned.                                                                    |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | no       | **Count Period:** The time window (in seconds) during which bad status codes are counted toward the threshold.                                                                        |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | no       | **Ban Duration:** How long (in seconds) an IP will remain banned after exceeding the threshold. Default is 24 hours (86400 seconds). Set to `0` for permanent bans that never expire. |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | no       | **Ban Scope:** Determines whether bans apply only to the current service (`service`) or to all services (`global`).                                                                   |

!!! warning "False Positives"
    Be careful when setting the threshold and count time. Setting these values too low may inadvertently ban legitimate users who encounter errors while browsing your site.

!!! tip "Tuning Your Configuration"
    Start with conservative settings (higher threshold, shorter ban time) and adjust based on your specific needs and traffic patterns. Monitor your logs to ensure that legitimate users are not mistakenly banned.

### Example Configurations

=== "Default Configuration"

    The default configuration provides a balanced approach suitable for most websites:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Strict Configuration"

    For high-security applications where you want to be more aggressive in banning potential threats:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"  # 7 days
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Ban across all services
    ```

=== "Lenient Configuration"

    For sites with high legitimate traffic where you want to avoid false positives:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"  # Only count unauthorized, forbidden, and rate limited
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"  # 1 hour
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Permanent Ban Configuration"

    For scenarios where you want detected attackers permanently banned until manually unbanned:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"  # Permanent ban (never expires)
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Ban across all services
    ```
