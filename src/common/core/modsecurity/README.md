The ModSecurity plugin integrates the powerful [ModSecurity](https://modsecurity.org) Web Application Firewall (WAF) into BunkerWeb. This integration delivers robust protection against a wide range of web attacks by leveraging the [OWASP Core Rule Set (CRS)](https://coreruleset.org) to detect and block threats such as SQL injection, cross-site scripting (XSS), local file inclusion, and more.

**How it works:**

1. When a request is received, ModSecurity evaluates it against the active rule set.
2. The OWASP Core Rule Set inspects headers, cookies, URL parameters, and body content.
3. Each detected violation contributes to an overall anomaly score.
4. If this score exceeds the configured threshold, the request is blocked.
5. Detailed logs are created to help diagnose which rules were triggered and why.

!!! success "Key benefits"

      1. **Industry Standard Protection:** Utilizes the widely used open-source ModSecurity firewall.
      2. **OWASP Core Rule Set:** Employs community-maintained rules covering the OWASP Top Ten and more.
      3. **Configurable Security Levels:** Adjust paranoia levels to balance security with potential false positives.
      4. **Detailed Logging:** Provides thorough audit logs for attack analysis.
      5. **Plugin Support:** Extend protection with optional CRS plugins tailored to your applications.

### How to Use

Follow these steps to configure and use ModSecurity:

1. **Enable the feature:** ModSecurity is enabled by default. This can be controlled using the `USE_MODSECURITY` setting.
2. **Select a CRS version:** Choose a version of the OWASP Core Rule Set (v3, v4, or nightly).
3. **Add plugins:** Optionally activate CRS plugins to enhance rule coverage.
4. **Monitor and tune:** Use logs and the [web UI](web-ui.md) to identify false positives and adjust settings.

### Configuration Settings

| Setting                               | Default        | Context   | Multiple | Description                                                                                                                                                                               |
| ------------------------------------- | -------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`          | multisite | no       | **Enable ModSecurity:** Turn on ModSecurity Web Application Firewall protection.                                                                                                          |
| `USE_MODSECURITY_CRS`                 | `yes`          | multisite | no       | **Use Core Rule Set:** Enable the OWASP Core Rule Set for ModSecurity.                                                                                                                    |
| `MODSECURITY_CRS_VERSION`             | `4`            | multisite | no       | **CRS Version:** The version of the OWASP Core Rule Set to use. Options: `3`, `4`, or `nightly`.                                                                                          |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`           | multisite | no       | **Rule Engine:** Control whether rules are enforced. Options: `On`, `DetectionOnly`, or `Off`.                                                                                            |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly` | multisite | no       | **Audit Engine:** Control how audit logging works. Options: `On`, `Off`, or `RelevantOnly`.                                                                                               |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`    | multisite | no       | **Audit Log Parts:** Which parts of requests/responses to include in audit logs.                                                                                                          |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`       | multisite | no       | **Request Body Limit (No Files):** Maximum size for request bodies without file uploads. Accepts plain bytes or human‑readable suffix (`k`, `m`, `g`), e.g. `131072`, `256k`, `1m`, `2g`. |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`          | multisite | no       | **Enable CRS Plugins:** Enable additional plugin rule sets for the Core Rule Set.                                                                                                         |
| `MODSECURITY_CRS_PLUGINS`             |                | multisite | no       | **CRS Plugins List:** Space-separated list of plugins to download and install (`plugin-name[/tag]` or URL).                                                                               |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`           | global    | no       | **Global CRS:** When enabled, applies CRS rules globally at the HTTP level rather than per server.                                                                                        |

!!! warning "ModSecurity and the OWASP Core Rule Set"
    **We strongly recommend keeping both ModSecurity and the OWASP Core Rule Set (CRS) enabled** to provide robust protection against common web vulnerabilities. While occasional false positives may occur, they can be resolved with some effort by fine-tuning rules or using predefined exclusions.

    The CRS team actively maintains a list of exclusions for popular applications such as WordPress, Nextcloud, Drupal, and Cpanel, making it easier to integrate without impacting functionality. The security benefits far outweigh the minimal configuration effort required to address false positives.

### Available CRS Versions

Select a CRS version to best match your security needs:

- **`3`**: Stable [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8).
- **`4`**: Stable [v4.23.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.23.0) (**default**).
- **`nightly`**: [Nightly build](https://github.com/coreruleset/coreruleset/releases/tag/nightly) offering the latest rule updates.

!!! example "Nightly Build"
    The **nightly build** contains the most up-to-date rules, offering the latest protections against emerging threats. However, since it is updated daily and may include experimental or untested changes, it is recommended to first use the nightly build in a **staging environment** before deploying it in production.

!!! tip "Paranoia Levels"
    The OWASP Core Rule Set uses "paranoia levels" (PL) to control rule strictness:

    - **PL1 (default):** Basic protection with minimal false positives
    - **PL2:** Tighter security with more strict pattern matching
    - **PL3:** Enhanced security with stricter validation
    - **PL4:** Maximum security with very strict rules (may cause many false positives)

    You can set the paranoia level by adding a custom configuration file in `/etc/bunkerweb/configs/modsec-crs/`.

### Custom Configurations {#custom-configurations}

Tuning ModSecurity and the OWASP Core Rule Set (CRS) can be achieved through custom configurations. These configurations allow you to customize behavior at specific stages of the security rules processing:

- **`modsec-crs`**: Applied **before** the OWASP Core Rule Set is loaded.
- **`modsec`**: Applied **after** the OWASP Core Rule Set is loaded. This is also used if the CRS is not loaded at all.
- **`crs-plugins-before`**: Applied **before** the CRS plugins are loaded.
- **`crs-plugins-after`**: Applied **after** the CRS plugins are loaded.

This structure provides flexibility, allowing you to fine-tune ModSecurity and CRS settings to suit your application's specific needs while maintaining a clear configuration flow.

#### Adding CRS Exclusions with `modsec-crs`

You can use a custom configuration of type `modsec-crs` to add exclusions for specific use cases, such as enabling predefined exclusions for WordPress:

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

In this example:

- The action is executed in **Phase 1** (early in the request lifecycle).
- It enables WordPress-specific CRS exclusions by setting the variable `tx.crs_exclusions_wordpress`.

#### Updating CRS Rules with `modsec`

To fine-tune the loaded CRS rules, you can use a custom configuration of type `modsec`. For example, you can remove specific rules or tags for certain request paths:

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

In this example:

- **Rule 1**: Removes rules tagged as `attack-xss` and `attack-rce` for requests to `/wp-admin/admin-ajax.php`.
- **Rule 2**: Removes rules tagged as `attack-xss` for requests to `/wp-admin/options.php`.
- **Rule 3**: Removes a specific rule (ID `930120`) for requests matching `/wp-json/yoast`.

!!! info "Order of execution"
    The execution order for ModSecurity in BunkerWeb is as follows, ensuring a clear and logical progression of rule application:

    1. **OWASP CRS Configuration**: Base configuration for the OWASP Core Rule Set.
    2. **Custom Plugins Configuration (`crs-plugins-before`)**: Settings specific to plugins, applied before any CRS rules.
    3. **Custom Plugin Rules (Before CRS Rules) (`crs-plugins-before`)**: Custom rules for plugins executed prior to CRS rules.
    4. **Downloaded Plugins Configuration**: Configuration for externally downloaded plugins.
    5. **Downloaded Plugin Rules (Before CRS Rules)**: Rules for downloaded plugins executed before CRS rules.
    6. **Custom CRS Rules (`modsec-crs`)**: User-defined rules applied before loading the CRS rules.
    7. **OWASP CRS Rules**: The core set of security rules provided by OWASP.
    8. **Custom Plugin Rules (After CRS Rules) (`crs-plugins-after`)**: Custom plugin rules executed after CRS rules.
    9. **Downloaded Plugin Rules (After CRS Rules)**: Rules for downloaded plugins executed after CRS rules.
    10. **Custom Rules (`modsec`)**: User-defined rules applied after all CRS and plugin rules.

    **Key Notes**:

    - **Pre-CRS customizations** (`crs-plugins-before`, `modsec-crs`) allow you to define exceptions or preparatory rules before the core CRS rules are loaded.
    - **Post-CRS customizations** (`crs-plugins-after`, `modsec`) are ideal for overriding or extending rules after CRS and plugin rules have been applied.
    - This structure provides maximum flexibility, enabling precise control over rule execution and customization while maintaining a strong security baseline.

### OWASP CRS Plugins

The OWASP Core Rule Set also supports a range of **plugins** designed to extend its functionality and improve compatibility with specific applications or environments. These plugins can help fine-tune the CRS for use with popular platforms such as WordPress, Nextcloud, and Drupal, or even custom setups. For more information and a list of available plugins, refer to the [OWASP CRS plugin registry](https://github.com/coreruleset/plugin-registry).

!!! tip "Plugin download"
    The `MODSECURITY_CRS_PLUGINS` setting allows you to download and install plugins to extend the functionality of the OWASP Core Rule Set (CRS). This setting accepts a list of plugin names with optional tags or URLs, making it easy to integrate additional security features tailored to your specific needs.

    Here's a non-exhaustive list of accepted values for the `MODSECURITY_CRS_PLUGINS` setting:

    * `fake-bot` - Download the latest release of the plugin.
    * `wordpress-rule-exclusions/v1.0.0` - Download the version 1.0.0 of the plugin.
    * `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Download the plugin directly from the URL.

!!! warning "False Positives"
    Higher security settings may block legitimate traffic. Start with the default settings and monitor logs before increasing security levels. Be prepared to add exclusion rules for your specific application needs.

### Example Configurations

=== "Basic Configuration"

    A standard configuration with ModSecurity and CRS v4 enabled:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Detection-Only Mode"

    Configuration for monitoring potential threats without blocking:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Advanced Configuration with Plugins"

    Configuration with CRS v4 and plugins enabled for additional protection:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Legacy Configuration"

    Configuration using CRS v3 for compatibility with older setups:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Global ModSecurity"

    Configuration applying ModSecurity globally across all HTTP connections:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Nightly Build with Custom Plugins"

    Configuration using the nightly build of CRS with custom plugins:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "Human-readable size values"
    For size settings like `MODSECURITY_REQ_BODY_NO_FILES_LIMIT`, the suffixes `k`, `m`, and `g` (case-insensitive) are supported and represent kibibytes, mebibytes, and gibibytes (multiples of 1024). Examples: `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.
