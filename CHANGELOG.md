# Changelog

## v1.6.8~rc3 - 2026/01/30

- [FEATURE] Add new `REVERSE_PROXY_REQUEST_BUFFERING` setting to the `Reverse Proxy` plugin to control request body buffering behavior when proxying requests (default: `on`)
- [BUGFIX] Initialize is_whitelisted variable to 'no' in configuration files to avoid spam uninitialized messages in logs
- [BUGFIX] Reorganize insertion logic to prevent foreign key errors and improve order of operations in database when creating/updating plugins
- [AUTOCONF] Add experimental Gateway API controller support (Gateway/HTTPRoute) and documentation
- [UI] Change redirect status code from 302 to 303 in the web UI to follow best practices for redirection after form submissions
- [UI] Fix bug where updating a ban to a custom duration accidentally created a permanent ban
- [UI] Enhance map legend and color ramp for blocked requests visualization
- [UI] Enhance dark mode styles for news card elements
- [MISC] Update Laurent Minne's blacklist's label and add the new one from [DuggyTuxy Data-Shield IPv4 Blocklist](https://duggytuxy.github.io/)
- [MISC] Add publiccode metadata file for open source compliance

## v1.6.8~rc2 - 2026/01/23

- [FEATURE] Enhance `Let's Encrypt` plugin to support concurrent certificate generation for multiple services via the new `LETS_ENCRYPT_CONCURRENT_REQUESTS` setting (default: `no`), improving efficiency and reducing wait times during bulk operations
- [FEATURE] Add `GoDaddy` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add `TransIP` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add `Domeneshop` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add new `KEEP_CONFIG_ON_RESTART` global setting to control whether a temporary configuration should be generated on each restart or preserve the existing one (default: `no`)
- [BUGFIX] Fix robots.txt and list-based plugins (greylist/whitelist/blacklist/dnsbl) appending duplicate entries on subsequent requests by creating deep copies of internalstore data instead of using shared references
- [LINUX] Enhance Easy Install script to detect if the epel-release should be installed or not for RHEL-family distros
- [UI] Add security mode in services table
- [UI] Implement services import functionality with drag-and-drop support
- [UI] Ensure UI service URL is properly formatted in setup loading route
- [UI] Enhance Redis report querying with filter parsing and chunked retrieval
- [UI] Update ace editor to version 1.43.5
- [DEPS] Updated lua-cjson version to v2.1.0.16
- [CONTRIBUTION] Thank you [rayshoo](https://github.com/rayshoo) for your contribution regarding the `Korean` translation of the web UI.

## v1.6.8~rc1 - 2026/01/19

- [FEATURE] Refactor Templator engine to use Jinja2 for improved templating capabilities and maintainability
- [BUGFIX] Fix Redis database selection in web UI and bwcli by renaming `REDIS_DB` to `REDIS_DATABASE` when fetching the settings
- [BUGFIX] Fix timezone discrepancies when checking for daily PRO plugin updates by normalizing dates to UTC
- [BUGFIX] Fix plugin deletion logic to correctly identify manually installed plugins so they are only removed when explicitly uninstalled
- [LINUX] Check the installation type in the easy-install script to avoid issues when upgrading from an older version and the installation type is not `all-in-one` or `manager`
- [LINUX] Enhance Easy Install script by adding an option to install a Redis server for data persistence and caching
- [UI] Enhance page titles to dynamically reflect current context and navigation state for improved user experience
- [DEPS] Update coreruleset-v3 version to v3.3.8
- [DEPS] Update coreruleset-v4 version to v4.22.0
- [DEPS] Updated luajit2 version to v2.1-20260114
- [DEPS] Update lua-resty-openssl version to v1.7.1

## v1.6.7 - 2026/01/09

- [BUGFIX] Fix wrong modsecurity reason data under heavy load
- [FEATURE] Enhance SSL/TLS negotiation by implementing dynamic ECDH curve resolution, enabling more flexible and secure key exchange configurations in preparation for post-quantum cryptography (X25519MLKEM768) with OpenSSL 3.5+
- [UI] Restrict flash messages containing sensitive information to authenticated users only
- [UI] Enhance breadcrumb navigation and filtering on custom configuration pages for improved user experience
- [LINUX] Drop support of Fedora 41
- [DOCS] Add Easy Resolve PRO plugin video tutorial link to the documentation
- [DEPS] Updated Modsecurity nginx connector version to 1.0.4
- [DEPS] Updated NGINX version to v1.28.1 for all integrations

## v1.6.7~rc2 - 2026/01/07

- [BUGFIX] Fix wrong certificate name checks in Let's Encrypt
- [BUGFIX] Fix issues with Let's Encrypt's HTTP challenge on Linux HA integrations
- [FEATURE] Implement automatic LRU cache eviction in the metrics module to prevent memory exhaustion by purging least-recently-used elements when capacity is reached
- [FEATURE] Optimize Redis connection handling by reusing pooled connections in Lua timers for improved performance and reduced overhead
- [LINUX] Updated NGINX version to v1.28.1 for Fedora 42 and 43 integration
- [ALL-IN-ONE] Update CrowdSec version to 1.7.4
- [DEPS] Updated luajit2 version to v2.1-20251229

## v1.6.7~rc1 - 2025/12/17

- [FEATURE] Refactor logging setup across multiple modules to be able to send logs to a syslog server and have multiple handlers at the same time
- [FEATURE] Allow configuration of whether Base64 decoding should be applied to DNS credentials via the new `LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64` setting in the `Let's Encrypt` plugin (default is `yes`)
- [FEATURE] Add new `ACCESS_LOG` and `ERROR_LOG` settings to configure access and error log destinations for BunkerWeb's instance
- [FEATURE] Refactor `Auth Basic` plugin so Lua now hashes credentials with salted scrypt (CSPRNG-only) and verifies them in constant time.
- [FEATURE] Updated `Bad Behavior` plugin to automatically apply bans made by the default server globally across all services, enhancing security by ensuring that IPs exhibiting bad behavior are consistently blocked.
- [FEATURE] Add the possibility to have **draft** custom configurations that are not applied to the service until they are explicitly published. Draft custom configurations are indicated in the web UI and can be toggled between draft and online status.
- [FEATURE] Add new `SSL_SESSION_CACHE_SIZE` setting to the SSL plugin to allow configuration of the size of the SSL session cache (e.g., `10m`, `512k`). Setting it to `off` or `none` disables session caching (default is `10m`).
- [FEATURE] Enhance the Antibot plugin to better handle redirection back to the original request path after a successful challenge by checking the `Referer` header, ensuring users are redirected to meaningful content rather than static files or other unintended destinations
- [FEATURE] Add the possibility to tweak custom configurations created from the web UI or API manually
- [FEATURE] Allow customizing plugin execution order via new `PLUGINS_ORDER_*` settings (space-separated plugin IDs; multisite-aware per phase)
- [BUGFIX] Fix issues with the Ingress controller regarding reverse proxy settings when using multiple paths per rule and a template by adjusting the indexing logic to be configurable via the new `KUBERNETES_REVERSE_PROXY_SUFFIX_START` setting (default is `1` to keep backward compatibility)
- [BUGFIX] Escape percentage signs in `DATABASE_URI` for Alembic when using the SQLAlchemy URL configuration to prevent formatting errors during migrations
- [BUGFIX] Fix issues with `Autoconf` controllers persisting old instances after they have been deleted from the orchestrator.
- [UI] Enhance service configuration handling during edits and renames to ensure consistency and prevent data loss
- [UI] Enhance session management with Redis support and configurable session lifetime
- [UI] Renamed "Global Configuration" to "Global Settings" in the web UI for clarity
- [UI] Address CSRF token issues in the web UI when not connecting through BunkerWeb
- [UI] Add the possibility to provide a certificate and a key so that the web UI can be served over HTTPS (without requiring a reverse proxy)
- [UI] Fix occasional flash of the light mode on the loading page when using dark mode
- [API] Refactor rate limiting to be more user-friendly and configurable via settings
- [LINUX] Support Fedora 43
- [LINUX] Update version retrieval for RPM packaging to ensure correct sorting for release candidates
- [DOCS] Add documentation about the new logging settings and how to configure them
- [DOCS] Update database compatibility matrix
- [DOCS] Refactor API documentation to include new API features and improve clarity
- [DOCS] Add documentation about the new "Custom Pages" PRO plugin
- [DOCS] Refactor web UI documentation to improve clarity
- [DEPS] Update lua-resty-session version to v4.1.5
- [DEPS] Update coreruleset-v4 version to v4.21.0
- [DEPS] Updated zlib version to v1.3.1.2

## v1.6.6 - 2025/11/24

- [FEATURE] Implement IP whitelisting checks in badbehavior module to avoid banning whitelisted IPs
- [FEATURE] Enhance default server configuration: when IP is whitelisted, serve the "nothing to see here" page even if the default server is deactivated.
- [BUGFIX] Fix default rate limit for POST /auth endpoint with API service
- [BUGFIX] Fix instant ban when using bad behavior with redis if the ban time is set to 0 (permanent ban)
- [BUGFIX] Fix "no memory" errors on metrics
- [LINUX] Enhance Easy Install script with manager and worker mode configurations
- [UI] Enhance bad behavior logging and UI actions with additional fields and filtering capabilities
- [UI] Optimize the reports page export functionality for large datasets by implementing server-side processing to handle data exports in manageable chunks, reducing memory usage and improving performance.
- [CONTRIBUTION] Thank you @Marvo2011 for your contribution to the `Let's Encrypt` plugin by helping the implementation of the new `Powerdns` DNS provider

## v1.6.6-rc3 - 2025/11/18

- [BUGFIX] Fix `Let's Encrypt` wildcard certificate serving when using `wildcard` mode in multisite setups and the root domain is a part of the `SERVER_NAME` setting of the service.
- [BUGFIX] Fix duplicated id error with ModSecurity rules when two services have the `USE_UI` setting enabled and the `USE_MODSECURITY_GLOBAL_CRS` setting enabled as well.
- [BUGFIX] Ensure the `Limit` plugin ignores global rules when `USE_LIMIT_REQ` is disabled globally so service-specific configs do not get throttled unintentionally.
- [BUGFIX] Ensure HTTP/3 works with the HTTP3 plugin by adding conditional reuseport to QUIC listen directives on the default HTTPS server.
- [FEATURE] Start monitoring `405` and `400` http status codes in the requests to be able to see them in the reports page.
- [FEATURE] Refactored `Auth Basic` authentication implementation to enhance security and maintainability by switching password hashing to bcrypt.
- [UI] Update DataTable initialization to automatically enable state saving for improved user experience.
- [LINUX] Support RHEL 9.7 instead of 9.6
- [LINUX] Support RHEL 10.1 instead of 10.0
- [DOCS] Add live status updates link to README and documentation in multiple languages.
- [DOCS] Fix PDF generation to generate it in english.
- [DOCS] Add documentation about how to setup BunkerWeb as a sidecar in Kubernetes.

## v1.6.6-rc2 - 2025/11/05

- [BUGFIX] Update logrotate config to use the right chown when creating the folders/files.
- [FEATURE] Refactor `Let's Encrypt` mail handling: validate the configured email and warn if missing/invalid. Use normal registration when valid; otherwise add **--register-unsafely-without-email** to Certbot and log that choice.
- [FEATURE] Add `DuckDNS` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add `AUTH_BASIC_ROUNDS` setting to the `authbasic` plugin to configure password hashing strength (default: 656000, range: 1000-999999999).
- [FEATURE] Add new `API` template to easily protect the API service using BunkerWeb.
- [FEATURE] Add new `ANTIBOT_IGNORE_COUNTRY` and `ANTIBOT_ONLY_COUNTRY` to the `Antibot` plugin for country-based challenge prompting/bypassing.
- [FEATURE] Add new `mtls` plugin for mutual TLS client certificate authentication, allowing services to require and verify client certificates against trusted CA bundles with configurable verification modes, chain depth control, and optional header forwarding for downstream authorization.
- [AUTOCONF] Implement event debouncing in Docker, Ingress, and Swarm controllers for improved configuration management
- [UI] Fix confirmation message not showing the right value when removing cache files on the file cache page.
- [UI] Fix filtering on the `Let's Encrypt` custom page
- [UI] Update CSS to fix truncated text in specific lang on the menu
- [MISC] Update regex for `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` setting to support human readable values.
- [MISC] Update default value for Permissions-Policy header to include additional features (`private-state-token-issuance` and `private-state-token-redemption`).
- [DEPS] Update coreruleset-v4 version to v4.20.0
- [DEPS] Updated luajit2 version to v2.1-20251030
- [DEPS] Updated lua-resty-core version to v0.1.32
- [DEPS] Updated lua-nginx-module version to v0.10.29
- [DEPS] Updated stream-lua-nginx-module version to v0.0.17
- [DEPS] Update lua-resty-openssl version to v1.7.0

## v1.6.6-rc1 - 2025/10/31

- [BUGFIX] Update BunkerWeb integration to use dedicated CrowdSec collection so that CrowdSec now works with the log format used by BunkerWeb.
- [FEATURE] Enhance plugin update process with per-plugin commit option and improved error handling
- [FEATURE] Add retry operation in case of memory failure for metrics linked to the `METRICS_MEMORY_MAX_RETRIES`.
- [FEATURE] Refactor wildcard certificate handling in certbot and letsencrypt plugin to improve reliability, performance and user experience
- [FEATURE] Allow edition of API settings in the web UI and of UI settings from the API
- [UI] Add [DB-IP](https://db-ip.com/) attribution in the web UI reports page footer
- [UI] Add `RAW` mode when editing/creating templates
- [UI] Enhanced the raw configuration editor with disabled settings highlighting and improved UI elements.
- [UI] Implemented **Ctrl+S** / **Command+S** shortcuts for saving RAW global config / services / custom configurations.
- [UI] Refactor threading to use a shared ThreadPoolExecutor for configuration tasks across routes, preventing gradual RAM growth over time
- [UI] Fix UX issue when a flash message was too big we couldn't remove it.
- [ALL-IN-ONE] Add Redis data directory creation in entrypoint script to fix redis not being able to start
- [ALL-IN-ONE] Update CrowdSec version to 1.7.3
- [API] fix API authorization to correctly handle root path prefixes in Biscuit guards
- [AUTOCONF] Allow ConfigMap of type "settings" to be applied to services easier.
- [AUTOCONF] Add the possibility to ignore services with a specific annotations when using the Kubernetes integration
- [DOCS] Add documentation for persistent data storage in the all-in-one image
- [DOCS] Add database compatibility matrix.
- [DEPS] Updated lua-cjson version to v2.1.0.15
- [DEPS] Update Mbed TLS version to v3.6.5

## v1.6.5 - 2025/10/03

- [BUGFIX] Fix wildcard certification handling when not using the MULTISITE mode in `Let's Encrypt` plugin
- [BUGFIX] Fix suffix handling in `Database` module when dealing with template settings to ensure proper management of settings without suffixes
- [FEATURE] Add the possibility use HTTPS with BunkerWeb's internal API
- [FEATURE] Add reason data for bad behavior bans/reports
- [FEATURE] Add session retention configuration via the `DATABASE_MAX_SESSION_AGE_DAYS` setting in the `Database` plugin and automatic cleanup job to purge old UI user sessions from the database
- [API] Introduce a dedicated control‑plane service exposing a REST API to programmatically manage BunkerWeb: list/register instances, trigger reload/stop, and manage bans, plugins, jobs, and configurations.
- [UI] Tweak the bad behavior details to look nice in the report page
- [UI] Prevent renaming of template-based custom configs in update and edit functions for consistency
- [UI] Fix template config not being editable in service easy mode
- [UI] Introduce a `Templates` management page to create, edit, clone and delete service templates.
- [UI] Add new `Template` column in the services page to display the template a service is based on (if any) and allow filtering by template.
- [MISC] Update default value for Permissions-Policy header to include additional features and remove the deprecated ones
- [DOCS] Add multi-language support to the documentation, including French, German, Spanish and Chinese (Mandarin) translations.
- [DOCS] Add documentation about the possibility to extend bwcli via plugins commands
- [DOCS] Add Docker logging best practices to advanced documentation
- [DEPS] Updated luajit2 version to v2.1-20250826
- [DEPS] Update coreruleset-v4 version to v4.19.0
- [CONTRIBUTION] Thank you [Arakmar](https://github.com/Arakmar) for your contribution regarding the `Let's Encrypt` plugin.
- [CONTRIBUTION] Thank you [tomkolp](https://github.com/tomkolp) for your contribution regarding the `Polish` translation of the web UI.

## v1.6.5-rc3 - 2025/09/16

- [BUGFIX] Fix lua session handling when using redis
- [BUGFIX] Fix ctx error at startup with `DNSBL` plugin
- [FEATURE] Introduce optional API token authentication to bolster security for BunkerWeb API calls, allowing users to enable token-based access control for enhanced protection against unauthorized requests
- [FEATURE] Add the possibility to ignore IPs in `DNSBL` plugin
- [LINUX] Improve nginx stop and reload handling in BunkerWeb service to use the pid file instead of the `pgrep` command
- [UI] Fix incorrect key used when viewing service details
- [UI] Fix 403 when changing IP address
- [UI] Add the possibility to quickly ban IP addresses from the reports page
- [UI] Fix date sorting in bans and reports pages
- [UI] Add ipaddr.js library for robust IP address validation
- [MISC] Update new `reloading` health status for BunkerWeb when NGINX is reloading and handle it in it's healthcheck file
- [MISC] Automatically minify UI CSS files in Images/Packages build process
- [MISC] Add LRU eviction fallback to avoid no memory errors
- [DEPS] Update lua-resty-openssl version to v1.6.4

## v1.6.5-rc2 - 2025/09/11

- [BUGFIX] Enhance database backup and restore functionality with improved compatibility and options
- [FEATURE] Add support for new reCAPTCHA version in `Antibot` plugin
- [ALL-IN-ONE] Update CrowdSec version to 1.7.0
- [ALL-IN-ONE] Add support for disabling specific CrowdSec parsers
- [UI] Fix occasional rate limiting when using the web UI by increasing the base limit in its template
- [UI] Fix status code filtering in reports page
- [UI] Fix IPs charts in home page to accurately reflect data
- [MISC] Automatically minify loading, errors and antibot HTML files in Images/Packages build process
- [DEPS] Update lua-resty-session version to v4.1.4
- [DEPS] Update lua-resty-openssl version to v1.6.3
- [DEPS] Update coreruleset-v4 version to v4.18.0
- [SECURITY] Enforce restrictive umask across scripts and configurations for improved security

## v1.6.5-rc1 - 2025/08/30

- [FEATURE] Enhance update-check job to utilize cached GitHub release data and improve error handling
- [BUGFIX] Update default algorithm for Let's Encrypt's `RFC2136` DNS provider from HMAC-SHA512 to HMAC-MD5
- [BUGFIX] Fix issue with loading environment variables in the `robotstxt` plugin
- [LINUX] Add upgrade capability to the easy-install script for seamless in-place updates
- [LINUX] Fix logrotation of certbot logs, they know gets automatically deleted after 7 days
- [UI] Always display all multiple settings to avoid confusion
- [UI] Update step navigation buttons to use visually-hidden class for better accessibility
- [UI] Fixed an issue where certain settings were reset when editing a service based on a template
- [UI] Fixed an issue where non-template custom configurations were removed when editing a service using a template
- [UI] Add Free Trial promotion card to pro.html for non-pro users
- [UI] Add Force update button on PRO page to force the download of PRO plugins without checking for updates.

## v1.6.4 - 2025/08/18

- [SECURITY] Fix open-redirection vulnerability in the Web UI regarding the `next` parameter in the loading process ([CVE-2025-8066](https://github.com/bunkerity/bunkerweb/security/advisories/GHSA-xxx9-3fh5-g585)).
- [FEATURE] Enhance `ModSecurity` plugin to support human-readable size values for request body limits (requests without files)
- [BUGFIX] Fix limit zones for HTTP/3 connections in `limitconn.conf` to ensure proper connection limiting for HTTP/3 requests.
- [LINUX] Support RHEL 10.0
- [LINUX] Support Debian 13 (Trixie)

## v1.6.3 - 2025/08/05

- [BUGFIX] Fix connection error shenanigans regarding the `Let's Encrypt` plugin when generating wildcard domains by adding the `--expand` flag to the certbot command.
- [BUGFIX] Fix errors with `PostgreSQL` database, ensuring that suffixes are stored as integers for consistency.
- [FEATURE] Enhance `Redirect` plugin to support multiple source/destination paths
- [FEATURE] Enhance `Antibot` CAPTCHA functionality with customizable character set via the `ANTIBOT_CAPTCHA_ALPHABET` setting, allowing users to define a custom alphabet for CAPTCHA generation.
- [UI] Always display the selected service and selected type when editing/creating a custom configuration
- [UI] Add global configuration fetching functionality to easy mode
- [UI] Fix metrics retrieval in the web UI to ensure that metrics are correctly displayed and updated
- [UI] Fix 500 error with TMP-UI fallback
- [LINUX] Add installation type to the post-install script to allow users to choose among `all-in-one` (Full installation), `manager` (Scheduler and UI), `worker` (BunkerWeb only), `scheduler` (Scheduler only), and `ui` (UI only) installation types.
- [ALL-IN-ONE] In entrypoint script, create redis directory if it does not exist to avoid issues with Redis not starting properly.
- [DEPS] Update coreruleset-v4 version to v4.17.1
- [CONTRIBUTION] Thank you [Arakmar](https://github.com/Arakmar) for your contribution regarding the web UI's `reports` page.

## v1.6.3-rc3 - 2025/07/30

- [BUGFIX] Fix HTTP/3 not working on default server as the `reuseport` directive was missing in the `default-server-http.conf` file.
- [UI] Fix missing settings when cloning a service in the web UI
- [FEATURE] Add the possibility to add headers and a footers to the `robots.txt` file using the `ROBOTSTXT_HEADER` and `ROBOTSTXT_FOOTER` settings. (Can be Base64 encoded)
- [FEATURE] Add `domainoffensive.de` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add `Dynu` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add a reason when a request is rate-limited in the `Rate Limiting` plugin, allowing users to understand why their request was blocked.
- [UI] De-duplicate metrics about requests on the home page to avoid counting the same request multiple times
- [UI] Enhance plugin filtering to avoid two plugins being displayed at the same time when filtering by name
- [UI] Enhance keywords search in the settings UI to make it more intuitive and user-friendly
- [DEPS] Update lua-resty-session version to v4.1.3
- [DEPS] Update lua-resty-redis version to v0.33
- [CONTRIBUTION] Thank you [Michal-Koeckeis-Fresel](https://github.com/Michal-Koeckeis-Fresel) for your contribution to the `Let's Encrypt` plugin.
- [CONTRIBUTION] Thank you [killmasta93](https://github.com/killmasta93) for your contribution regarding the integrations examples.

## v1.6.3-rc2 - 2025/07/29

- [BUGFIX] Fix errors with the `Custom SSL certificate` job when a lot of environment variables are set in the scheduler.
- [BUGFIX] Fix shenanigans regarding external/PRO plugins in Linux integration.
- [FEATURE] Update Laurent Minne's blacklist URL to the new one: <https://github.com/duggytuxy/Data-Shield_IPv4_Blocklist>
- [UI] Add PRO activation step in the setup wizard to allow users to activate the PRO version during the initial setup.
- [UI] Simplify configuration step in setup wizard by adding a new `Advanced settings` section to allow users to configure advanced settings like `SERVER_NAME`, and the `Let's Encrypt` plugin.
- [UI] Add a new alias to the `TOTP_SECRETS` environment variable: `TOTP_ENCRYPTION_KEYS` to make more sense in the context of the TOTP feature.
- [UI] Add a force recheck PRO plugins button in the web UI to allow users to force a recheck of the PRO plugins status.
- [LINUX] Add CrowdSec automatic installation/configuration in the easy-install script for Linux distributions.
- [ALL-IN-ONE] Update CrowdSec to version v1.6.11.

## v1.6.3-rc1 - 2025/07/19

- [BUGFIX] Update scheduler environment variables handling to avoid issues when there are too many environment variables set.
- [BUGFIX] Fix `Let's Encrypt` credential files being removed upon reload of the scheduler creating issues with the certificate renewal.
- [BUGFIX] Change `BAD_BEHAVIOR_BAN_SCOPE` setting context from `multisite` to `global`.
- [BUGFIX] Update template data handling to use template_data instead of template when updating external plugins.
- [BUGFIX] Fix unban functionality to correctly handle global bans in the web UI.
- [FEATURE] Add `BunnyNet` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add new `robotstxt` plugin to manage the robots.txt file from settings and serve it
- [UI] Fix shenanigans when fetching the latest version in the web UI.
- [UI] Fix the fact that the "global" choice wasn't categorized as is in the web UI when editing a custom configuration.
- [UI] Fix multivalue toggle button functionality and transition effects
- [UI] Enhance ModSecurity Reporting: Add Anomaly Score Handling
- [UI] Improve multiple setting handling in plugin settings template for better UI interaction (always show the first group, hide others by default)
- [DOCS] Update error handling documentation to clarify custom error page placement and ROOT_FOLDER settings.
- [MISC] Enhance plugin command execution with error handling and available commands listing
- [MISC] Streamline ban management by utilizing utility functions for adding and removing bans
- [MISC] Reorder session data retrieval in antibot access method for improved clarity and flow
- [LINUX] Drop support of Fedora 40
- [DEPS] Updated NGINX version to 1.28.0 for Fedora integration now that it is available in the repositories.

## v1.6.2 - 2025/07/08

- [SECURITY] Introduce ModSecurity exclusion rules targeting the password input upon login, preventing false-positive blocks on valid complex passwords while preserving strict overall request inspection.
- [SECURITY] Add new ModSecurity exclusion rule to prevent false positives on the `/instances/new` endpoint, specifically for the `hostname` argument, ensuring that legitimate requests are not blocked while maintaining security.
- [FEATURE] Refactor download scripts to canonicalize and deduplicate URLs before fetching and implement smarter cache management for improved efficiency
- [FEATURE] Implement Redis-backed metrics storage and optimize retrieval workflows for faster, more reliable performance
- [FEATURE] Add support for custom Let's Encrypt profiles and log profile changes during renewal
- [ALL-IN-ONE] Update CrowdSec to version v1.6.9
- [UI] Add "Go Back" button functionality in unauthorized page
- [UI] Improve dynamic translation handling and update chart rendering on theme and language changes
- [UI] Add an optional /healthcheck endpoint to the web UI for health monitoring, which can be enabled via the `ENABLE_HEALTHCHECK` setting (default is `no`)
- [UI] Enhance log file handling and display Let's Encrypt logs
- [DOCS] Add documentation about [Valkey](https://valkey.io/) support alongside [Redis](https://redis.io/) for data persistence and caching in BunkerWeb
- [MISC] Enhance logging to differentiate between allowed and denied access based on whitelist status
- [DEPS] Update coreruleset-v4 version to v4.16.0
- [DEPS] Update Mbed TLS version to v3.6.4
- [DEPS] Update Ace editor version to 1.43.1
- [DEPS] Update i18next version to v25.3.0
- [DEPS] Update i18next browser languageDetector extension version to v8.2.0
- [DEPS] Update DOMPurify version to 3.2.6
- [DEPS] Update ApexCharts.js version to v4.7.0

## v1.6.2-rc7 - 2025/06/25

- [BUGFIX] Add a conditional `proxy_hide_header` rule for the `Upgrade` header to preserve WebSocket connections in the `Reverse Proxy` plugin, preventing issues with WebSocket connections when the `REVERSE_PROXY_HIDE_HEADERS` setting is used.
- [BUGFIX] Correct the Logs page copy-to-clipboard button so it reliably copies selected log entries.
- [BUGFIX] Fix issues with database backup when using MySQL and MariaDB if the database's size is larger than 1GB, ensuring that the backup process can handle larger databases without errors.
- [FEATURE] Introduce a new `number` setting type with built-in numeric validation and enhanced rendering in the web UI.
- [FEATURE] Introduce a new `multivalue` setting type with customizable separator and validation, enhancing user experience for multi-value inputs in the web UI.
- [MISC] Switch the `Bad Behavior` plugin to use the new numeric `BAD_BEHAVIOR_BAN_TIME` setting by updating the permanent ban value from `-1` to `0`.
- [CONTRIBUTION] Thank you @Michal-Koeckeis-Fresel for the optimizations regarding the web UI fonts and geoip data loading, which significantly improves the performance of the web UI and the new dhparam file to respect the latest security standards.

## v1.6.2-rc6 - 2025/06/20

- [BUGFIX] Ensure template defaults settings are correctly retrieved by jobs and templates.
- [BUGFIX] No longer completely delete all PRO plugins data upon PRO deactivation, allowing for easier reactivation without losing data.
- [BUGFIX] Enhance cache robustness by using dict.get() for lookups to avoid KeyError exceptions during cache operations.
- [SECURITY] Make sure the files/dirs in /usr/share/bunkerweb have the appropriate permissions to prevent unauthorized access to sensitive files on Linux integration

## v1.6.2-rc5 - 2025/06/17

- [BUGFIX] Ensure jobs correctly retrieve multisite settings when a service uses its default value while the global setting is overridden, preventing configuration mismatches.
- [FEATURE] Add new `LETS_ENCRYPT_PASSTHROUGH` setting to the `Let's Encrypt` plugin to allow passing through the Let's Encrypt challenge requests to the upstream server (default is `no`)
- [UI] Fix i18n shenanigans in services page and in dataTables
- [UI] Fix plugins delete button not working
- [LINUX] Make sure that the NGINX service is disabled every time in the post-install script to avoid issues with the NGINX service being started when it shouldn't be
- [SECURITY] Refactor permissions in BunkerWeb files to ensure that only the necessary files are readable/writable/executable by the user running the service, enhancing security and preventing unauthorized access to sensitive files.

## v1.6.2-rc4 - 2025/06/12

- [FEATURE] Introduce `multiselect` setting type, enabling users to choose multiple options from a configurable list
- [FEATURE] Add new `BLACKLIST_COMMUNITY_LISTS` setting to the `blacklist` plugin, allowing users to choose which community blocklists to use for blacklisting
- [FEATURE] Add new `REVERSE_PROXY_HIDE_HEADERS` setting to the `Reverse Proxy` plugin, allowing users to specify a list of HTTP headers to hide from clients when received from the proxied resource (values for proxy_hide_header directive).
- [MISC] Greatly improve scheduler's performance by optimizing the way it handles environment variables and settings, reducing the number of database queries and improving overall efficiency
- [MISC] Optimize variable loading during the init phase to improve startup performance
- [DEPS] Update coreruleset-v4 version to v4.15.0
- [DEPS] Update lua-resty-session version to 4.1.2
- [DEPS] Update LuaJIT version to v2.1-20250529
- [CONTRIBUTION] Thank you @Ablablab for your contribution to the `Headers` plugin
- [CONTRIBUTION] Thank you @sachin-vcs for your contribution to the `Let's Encrypt` plugin by helping the implementation of the new `Njalla` DNS provider

## v1.6.2-rc3 - 2025/06/06

- [BUGFIX] Refactor CLI command handling to support additional arguments
- [DOCS] Update the documentation about the `all-in-one` image to include the new features and improvements, also move it to its own section
- [FEATURE] Add request ID to error pages, logs and display it in UI reports for easier tracking of issues
- [FEATURE] Add support for Docker secrets in all services
- [FEATURE] Add more data to ModSecurity reports
- [FEATURE] Add new `LETS_ENCRYPT_MAX_RETRIES` setting to the `Let's Encrypt` plugin to configure how many times certificate generation should be retried with Let's Encrypt (default is 0, meaning no retries)
- [ALL-IN-ONE] Fully integrate CrowdSec in the all-in-one image
- [ALL-IN-ONE] Fully integrate Redis in the all-in-one image (activated by default)
- [UI] Add clear notifications feature to both UI and backend for improved notification management
- [UI] Improve plugin navigation by displaying plugins as a vertical list on the left side of the card, replacing the dropdown combobox
- [UI] Display a small "enabled/disabled" icon next to each plugin name in the plugin sidebar and menu to indicate whether the plugin is active (e.g., show if Reverse Proxy is enabled)
- [UI] Update QR code generation to use PilImage and output JPEG format for improved compatibility
- [UI] Add a modal to update ban durations, with support for localization
- [UI] Add system memory usage monitoring to the home page dashboard for real-time insights
- [UI] Add a more robust system when showing reports and bans data to avoid potential XSS vulnerabilities
- [UI] Refactor the data display on the report page for a more user-friendly experience
- [UI] Add quick actions for bans back
- [UI] Enhance reset button visibility and tooltip handling across various settings templates
- [UI] Add the possibility to delete cache files
- [MISC] Refactor template rendering for improved performance and efficiency
- [LINUX] Provide an interactive installer script for BunkerWeb that guides users through setup options
- [DEPS] Updated NGINX version to 1.28.0 (except for Fedora as it is not yet available)
- [CONTRIBUTION] Thank you @lenglet-k for your contribution to the Ingress controller
- [CONTRIBUTION] Thank you @kovacs-andras for your contribution to the PRO urls in the documentation
- [CONTRIBUTION] Thank you @mevenG for your contribution to the README file

## v1.6.2-rc2 - 2025/05/19

- [BUGFIX] Fix draft services deletion when editing the global config in the web UI
- [BUGFIX] Enhance the `Let's Encrypt` plugin's Cloudflare Provider with default values and validation for credentials to avoid having to set all of them all the time (`api_token` or `email` and `api_key`)
- [BUGFIX] Remove settings form input sanitization as it was creating issues when saving settings in the web UI
- [BUGFIX] Exclude the RFC2136 DNS provider from the base64 encoding validation for credential items in the `letsencrypt` plugin to prevent issues with the `secret` field being detected as base64 encoded
- [BUGFIX] Avoid redirecting clients when they match an ignore list item in `antibot` plugin
- [BUGFIX] Avoid always trying to regenerate a Let's Encrypt certificate that was using the staging production over and over at every restart
- [FEATURE] Add the possibility to choose a profile when generating certificates with Let's Encrypt using the `LETS_ENCRYPT_PROFILE` setting (`classic` (default), `tlsserver` for server-only validation, and `shortlived` for reduced 7-day validity) to provide flexibility in certificate configuration based on security requirements
- [FEATURE] Add the possibility to declare custom certificates and keys data as plaintext as well as base64-encoded data in the `customcert` plugin using the `CUSTOM_SSL_CERT_DATA` and `CUSTOM_SSL_KEY_DATA` settings
- [FEATURE] Add `IONOS` as a DNS provider in the `letsencrypt` plugin
- [FEATURE] Add `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` setting to control if underscores in headers should be allowed or not in the `Reverse Proxy` plugin (default is `no`)
- [FEATURE] Add `LETS_ENCRYPT_CUSTOM_PROFILE` setting to allow setting a custom profile for the `Let's Encrypt` plugin
- [FEATURE] Add `LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES` setting to allow disabling the public suffixes check in the `Let's Encrypt` plugin (default is `yes`)
- [FEATURE] Add permanent ban feature to `badbehavior` plugin, web UI and bwcli
- [UI] Fix shenanigans when editing a service in easy mode
- [UI] Fix false positive with the newer CRS version (v4.13.0) on the web UI when fetching fonts
- [UI] Add reset functionality to settings with UI updates for input, checkbox, and select elements
- [UI] Fix LEDNS credential handling in setup wizard and reset button visibility in settings templates
- [UI] Update time formatting in requests chart to use 12-hour format in home page
- [UI] Introduce multi‑language support in the web UI: `ar`, `bn`, `en`, `es`, `fr`, `hi`, `pt`, `ru`, `ur`, `zh`, `de`, `it` — covering the world’s top 10 and Europe’s top 5 languages.
- [UI] Refactor TOTP Pretty key generation to avoid separating the parts with a `-` character (this was causing issues with some QR code readers)
- [UI] Add the possibility to manually delete Let's Encrypt certificates in the web UI
- [UI] Refactor bans management to process the data on the serverSide like done with the reports
- [UI] Update apexcharts.js to version 4.6.0
- [UI] Update ace editor to version 1.40.1
- [UI] Update DOMPurify to version 3.2.5
- [MISC] Add algorithm normalization for self-signed certificate generation to avoid regenerating the certificate if the algorithm is already the right one but the setting is not set to the same value
- [MISC] Refactor the way we fetch the entire config from the database to avoid issues with default values and multiple settings in the lua code
- [MISC] Add new container security using docker scout in CI/CD pipeline
- [MISC] Add warning for RHEL users regarding external database client installation and remove dependency on `mysql` and `postgresql` packages in the RHEL fpm file (it was causing issues when `mariadb` was installed)
- [AUTOCONF] (Re) Remove possible infinite loop in Kubernetes integration
- [UI] Integrate Biscuit authentication and key management
- [DEPS] Update coreruleset-v4 version to v4.14.0
- [DEPS] Update lua-resty-openssl version to v1.6.1
- [DEPS] Update lua-resty-session version to v4.1.1
- [LINUX] Support Fedora 42
- [CONTRIBUTION] Thank you @nimro27 for your contribution to the Ingress controller (#2141 and #2143)
- [CONTRIBUTION] Thank you @TomVivant for your contribution to the `letsencrypt` plugin (#2149)
- [CONTRIBUTION] Thank you @wiseweb-works for your contribution to the `web UI` by adding the Turkish language (#2204)
- [CONTRIBUTION] Thank you @HongyiHank for your contribution to the `web UI` by adding the Traditional Chinese language and double checking the Simplified Chinese language (#2226)

## v1.6.2-rc1 - 2025/03/29

- [BUGFIX] Fix database migration issues when upgrading from older versions to v1.6.1-rc1 with a PostgreSQL database
- [BUGFIX] Fix shenanigans with templates in the web UI when editing/creating a service using the easy mode
- [BUGFIX] Improve database table existence checks and error handling in scripts to avoid errors when the LANG is not en_US.UTF-8
- [BUGFIX] Fix `Country` plugin regex to avoid false positives and deduplicate entries in the lua code
- [BUGFIX] Fix `Let's Encrypt` clear old certificates logic to avoid deleting the wrong certificates
- [DOCS] Enhance documentation about `all-in-one` image
- [DOCS] Refactor the settings documentation to make it more consistent and easier to read, it is now renamed to `Features`
- [FEATURE] Enhance `SSL` plugin configuration with customizable cipher levels `modern`, `intermediate`, and `old` for better control over SSL/TLS settings and the ability to set a custom cipher list
- [FEATURE] Add the possibility to ignore `URI`, `IP`, `reverse DNS`, `ASN`, and `User-Agent` in the `Antibot` plugin
- [FEATURE] Add the possibility to configure the algorithm used when generating the `self-signed` certificate in the `Self-signed certificate` plugin (default is `ec-prime256v1`)
- [FEATURE] Add `Infomaniak` as a DNS provider in the `letsencrypt` plugin
- [MISC] Add the possibility to use the less secure `dns_cloudflare_email` and `dns_cloudflare_api_key` credentials in the `letsencrypt` plugin for Cloudflare DNS provider
- [MISC] Update regex in the `Self-signed certificate` plugin for subject validation so we don't have to always start with `/CN=`
- [MISC] Update regex in the `Security.txt` plugin to support both HTTP and HTTPS URLs and add an helper function to convert HTTP URLs to HTTPS
- [MISC] Update regex in the `SSL` plugin to support older HTTPS protocols
- [MISC] Make the default certificate more secure by using the `secp384r1` curve and the `sha384` hash algorithm instead of the `secp256r1` curve and the `sha256` hash algorithm
- [AUTOCONF] Remove possible infinite loop in Kubernetes integration
- [UI] The temporary web UI will now accept X-Forwarded-For headers to allow the use of a reverse proxy in front of it
- [UI] Persist DataTable page length in localStorage for consistent user experience.
- [UI] Fix 2FA setup page QR code not being scannable when using the dark mode
- [UI] Update latest stable release only if available to avoid unnecessary updates prompting
- [UI] Fix correct key retrieval for `Redis` metrics
- [UI] Enhance report data formatting and error handling in reports module
- [UI] Templates are now listed in an appropriate order in the web UI when creating a new service in easy mode (`low` -> `medium` -> `high` -> `custom`)
- [UI] Refactor easy mode to improve the user experience and make it more intuitive
- [ALL-IN-ONE] Enhance supervisord configuration to ensure proper startup and shutdown of all services in the all-in-one image
- [ALL-IN-ONE] Improve logging mechanism in the all-in-one image to ensure that logs are properly captured and displayed
- [LINUX] Fix NGINX service not being disabled correctly in the post-install script
- [DEPS] Add lua-upstream-nginx-module
- [DEPS] Update lua-resty-redis version to v0.32
- [DEPS] Update ngx_devel_kit version to v0.3.4
- [DEPS] Update mbedtls version to v3.6.3

## v1.6.1 - 2025/03/15

- [BUGFIX] Enhance Alembic configuration to support database URIs args
- [BUGFIX] Made `SERVER_NAME` setting's regex more permissive (removed the duplication check)
- [BUGFIX] Add selective table support in `Backup` plugin to avoid issues when restoring the database
- [DOCS] Document how to use BunkerWeb with and existing Ingress controller in Kubernetes
- [DOCS] Add documentation about new `all-in-one` image for BunkerWeb in the Docker section of the Integrations page
- [DOCS] Edit documentation about thew `User Manager` PRO plugin
- [FEATURE] Add a new `all-in-one` image for BunkerWeb that includes all the services in one image (BunkerWeb, Scheduler, Autoconf, and UI)
- [FEATURE] Add `CrowdSec` as a core plugin
- [MISC] Improve update check output formatting for better readability
- [MISC] Enhance `Let's Encrypt` DNS credential handling to support base64-encoded values, while also refining credential item processing to handle escape sequences and improve data integrity.
- [UI] Enhance ban handling with improved validation and informative responses for ban scope and service
- [UI] Improve plugin page template handling logic
- [UI] Add a failover message reporting
- [UI] Prevent interference with newsletter form checkbox click handler

## v1.6.1-rc3 - 2025/03/05

- [BUGFIX] Fix issue where Redis Server returns a `NOPERM` error, ensuring proper handling and preventing 500 errors in the web UI
- [FEATURE] Enhance ban management with service-specific options and UI improvements
- [FEATURE] Add `BAD_BEHAVIOR_BAN_SCOPE` setting to control the scope of the ban when using the `Bad Behavior` plugin (default is `service`) - before the bans were global
- [FEATURE] Add verbose logging option for certbot commands based on log level (when set to `DEBUG`)
- [FEATURE] Enhance `bwcli` rendering and added support for new service-specific ban options
- [AUTOCONF] Add missing `redis` dependency
- [MISC] improve Redis data handling and error logging in CLI and routes
- [DEPS] Updated coreruleset-v4 version to v4.12.0

## v1.6.1-rc2 - 2025/02/27

- [BUGFIX] Fix shenanigans with settings' plugin_id when updating the config
- [BUGFIX] Fix rare error where "python3" is not found in docker images
- [BUGFIX] Fix jobs runs excess cleanup method in Database
- [FEATURE] Add `PROXY_BUFFER_SIZE` and `PROXY_BUFFERS` settings to control the proxy buffer size and the number of buffers in `multisite` mode
- [UI] Introduced a visual label in the UI to clearly mark service settings that were cloned from the original.
- [UI] Added support for custom plugins: developers can now create hooks and blueprints to override existing functionalities, not just a plugin page.
- [DEPS] Updated ModSecurity version to v3.0.14

## v1.6.1-rc1 - 2025/02/20

- [BUGFIX] Fix ModSecurity false positive on the web UI when the `UI_HOST` setting contains an IP address
- [BUGFIX] Fix ModSecurity false positive when the web UI `SERVER_NAME` is set to an IP address
- [BUGFIX] Fix PRO activation not working in the web UI
- [BUGFIX] Fix log extraction was not working in the web UI when specific conditions were met (invalid UTF-8 characters)
- [BUGFIX] Fix database migration logic to handle `dev` and `testing` versions
- [BUGFIX] Fix web UI waiting for temporary web UI to stop indefinitely in some cases
- [FEATURE] Add `deSEC` DNS provider support in `letsencrypt` plugin
- [UI] Enhance UX here and there
- [UI] Add an instance hostname validation in the `instances` page when adding a new instance
- [UI] It is now possible to edit services created with the `autoconf` method
- [UI] It is now possible to change the theme even if the database is in read-only mode
- [UI] Added an auto-hide functionality to informative messages in the UI
- [MISC] Update regex for `SERVER_NAME` to improve accuracy and avoid issues
- [MISC] Revamped DNS credential validation to minimize configuration errors and enhance overall reliability.

## v1.6.0 - 2025/02/13

- [BUGFIX] Fix CRS plugins not being included correctly in ModSecurity configuration
- [FEATURE] Add mCaptcha antibot mode
- [FEATURE] Add `USE_MODSECURITY_GLOBAL_CRS` setting to ModSecurity plugin to allow using the global CRS instead of the service CRS, which is useful to accelerate the configuration generation when you have a lot of services
- [AUTOCONF] Increase retry limit and improve stability of Kubernetes watch stream
- [UI] Add caching for GitHub buttons to improve performance
- [UI] Fix shenanigans with multiples
- [DEPS] Updated NGINX version to 1.26.3
- [DEPS] Updated lua-resty-openssl version to 1.5.2

## v1.6.0-rc4 - 2025/01/29

- [BUGFIX] Fix shenanigans with the configuration being wiped after a restart
- [BUGFIX] Fix shenanigans with cache files being deleted for no reason
- [BUGFIX] Refactor condition checks in Database class to avoid default value check when a multiple has a suffix so that it still saves important values
- [DOCKER] Update Dockerfiles to change user home directories and set shell to nologin for autoconf, scheduler, and ui users
- [DEPS] Updated coreruleset-v4 version to v4.11.0

## v1.6.0-rc3 - 2025/01/26

- [FEATURE] Update BunkerNet's logic to send reports in bulk instead of one by one
- [AUTOCONF] Add the possibility to add/override settings via ConfigMap in Kubernetes using the `bunkerweb.io/CONFIG_TYPE=settings` annotation
- [UI] Add support page for easy logs and configuration sharing while anonymizing sensitive data
- [LINUX] Support Fedora 41

## v1.6.0-rc2 - 2025/01/21

- [BUGFIX] Whitelisting a client no longer bypasses https redirect settings as the `ssl` plugin is now executed before the `whitelist` plugin
- [UI] Fixed condition when validating the setup wizard form when a custom certificate is used
- [FEATURE] Add extra validation of certificates in `customcert` plugin
- [FEATURE] Introduce new `SSL` plugin to manage SSL/TLS settings without tweaking the `misc` plugin
- [FEATURE] Add `stream` support in `Kubernetes` integration
- [FEATURE] Renamed the `MODSECURITY_CRS_PLUGIN_URLS` setting to `MODSECURITY_CRS_PLUGINS` to make it more consistent as the setting now accepts plugin names directly as well as URLs and automatically downloads them
[FEATURE] Add `plugin_list` command to `bwcli` for listing available plugins and their commands
- [DOCS] Added Swarm deprecated notice in the documentation
- [DEPS] Added Brotli v1.1.0 dependency for ngx_brotli
- [DEPS] Updated headers-more-nginx-module version to v0.37
- [DEPS] Updated libinjection to latest commit on main branch
- [DEPS] Updated libmaxminddb version to v1.12.2
- [DEPS] Updated luajit2 version to v2.1-20250117
- [DEPS] Updated lua-nginx-module version to v0.10.28
- [DEPS] Updated lua-resty-core version to v0.1.31
- [DEPS] Updated lua-resty-dns version to v0.23
- [DEPS] Updated lua-resty-redis version to v0.31
- [DEPS] Updated ngx_brotli to latest commit on master branch
- [DEPS] Updated stream-lua-nginx-module version to v0.0.16

## v1.6.0-rc1 - 2025/01/10

- [BUGFIX] Increase string length for service_id and id columns in database models to avoid issues with long service names
- [BUGFIX] Fix shenanigans with setup wizard when a reverse proxy was already configured
- [LINUX] Support Fedora 40 back and temporarily put aside Fedora 41 (there are issues when building the images)
- [UI] Add `CHECK_PRIVATE_IP` configuration to manage session IP address changes for private networks
- [UI] Implement `ALWAYS_REMEMBER` functionality for session persistence in login
- [UI] Add temporary UI service to show errors that occurred if any while web UI was starting up
- [FEATURE] Update regex for cookie flags validation to allow additional attributes
- [FEATURE] Add health check endpoint and integrate it into the scheduler for instance status monitoring
- [FEATURE] Add country tracking to bans data
- [FEATURE] Refactored the way the database migrations are handled to make it more reliable and faster using alembic
- [FEATURE] Add configurable limit for SecRequestBodyNoFilesLimit in ModSecurity via the `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` setting
- [FEATURE] Add multi-user support in `Auth basic` plugin
- [FEATURE] Add support for TCP toggle listening in server-stream configuration (now UDP doesn't replace TCP when activated)
- [FEATURE] Made `LISTEN_STREAM_PORT` and `LISTEN_STREAM_PORT_SSL` settings multiples to allow listening on multiple ports
- [DEPRECATION] Remove `X-XSS-Protection` header from the `header` plugin as it is deprecated
- [DEPS] Updated coreruleset-v4 version to v4.10.0
- [DEPS] Updated libmaxminddb version to v1.12.1

## v1.6.0-beta - 2024/12/10

- [FEATURE] Add support for the Coreruleset plugins via the USE_MODSECURITY_CRS_PLUGINS and the MODSECURITY_CRS_PLUGIN_URLS settings (it automatically downloads and installs the plugins like with BunkerWeb's external plugins). plugins can also be added manually via custom configuration files
- [FEATURE] Add X_DNS_PREFETCH_CONTROL setting to control the DNS prefetching behavior via the X-DNS-Prefetch-Control header (default is off)
- [FEATURE] Add new `securitytxt` plugin to manage the security.txt file from settings and serve it
- [FEATURE] Add new `REVERSE_PROXY_PASS_REQUEST_BODY` setting to control if the request body should be passed to the upstream server (default is yes)
- [FEATURE] Jobs now have an history which the size can be controlled via the `DATABASE_MAX_JOBS_RUNS` setting (default is 10000) and it will be possible to see it in the web UI in a future release
- [FEATURE] Add support for HTTP/3 connections limiting via the `HTTP3_CONNECTIONS_LIMIT` setting (default is 100) in the `limit` plugin
- [FEATURE] Add new templating feature to allow to quickly override the default values of settings and custom configurations. You can also precise steps to follow in the UI to help the user configure services.
- [FEATURE] Optimized the way the scheduler sends the configuration to the instances to make it faster and more reliable using a ThreadPoolExecutor
- [FEATURE] Add the possibility to set a custom timezone for every service via the `TZ` environment variable (will apply to the logs and all date fields stored in the database). If not set, it will use the local timezone of the server.
- [FEATURE] Add the possibility to run plugins job in async mode to avoid running them in order in the scheduler by setting the `async` key to `true` in the plugin job configuration (default is `false`)
- [FEATURE] Add Let's Encrypt DNS challenges support !
- [FEATURE] Add new `REMOTE_PHP_PORT` setting to control the port used by the remote PHP feature (default is 9000)
- [SCHEDULER] Refactor the scheduler to use the `BUNKERWEB_INSTANCES` (previously known as `OVERRIDE_INSTANCES`) environment variable instead of an integration specific system
- [AUTOCONF] Add new `NAMESPACES` environment variable to allow setting the namespaces to watch for the autoconf feature which makes it possible to use multiple autoconf instances in the same cluster while keeping the configuration separated
- [AUTOCONF] Add new `USE_KUBERNETES_FQDN` environment variable to allow using the full qualified domain name of the services in Kubernetes instead of the ip address for the hostname of instances (default is yes)
- [LINUX] Support Fedora 41 and drop support of Fedora 40
- [UI] Start refactoring the UI to make it more modular and easier to maintain
- [UI] Add a `remember me` feature to the login page so that the user can stay logged in for a longer period of time (expires after 31 days)
- [UI] Add new `TOTP_SECRETS` setting to encrypt the TOTP secrets in the database (if not set, we generate a random amount of secrets via passlib.totp) - ⚠ We highly recommend setting this setting to a custom value to prevent the secrets from being erased when the volumes are deleted
- [UI] Start adding roles and permissions to the UI to allow different users to have different permissions in a multi-user environment for the near future
- [UI] Made 2FA feature more user-friendly and added recovery codes in case of lost access to the 2FA device
- [UI] Refactored the way we handle logs in the UI to make it so that it no longer relies on Integration specific logics and instead always reads the files present in the `/var/log/bunkerweb` folder
- [DOCS] Updated docs for all new features and changes
- [MISC] Review security headers in the `headers` plugin to improve security
- [MISC] Updated context of `realip`'s `USE_PROXY_PROTOCOL` setting to `global` as it was always applied globally even if set only on a service
- [DEPS] Updated lua-resty-core version to v0.1.30
- [DEPS] Updated lua-resty-lrucache version to v0.15
- [DEPS] Updated LuaJIT version to v2.1-20241113
- [DEPS] Updated Mbed TLS version to v3.6.2
- [DEPS] Updated coreruleset-v4 version to v4.9.0

## v1.5.12 - 2024/11/27

- [SECURITY] Fix CVE-2024-53254
- [UI] Fix issues in several pages because of a wrong key being used to fetch the data

## v1.5.11 - 2024/11/08

- [BUGFIX] Fix INTERCEPTED_ERROR_CODES to allow empty value
- [UI] Fix missing settings when a service is published online
- [UI] Fix instances always down in instances page
- [AUTOCONF] Fix BW env vars not retrieved
- [AUTOCONF] Fix deadlock on k8s events when there is no ingress
- [LINUX] Increase default worker dict size to avoid crash on RPI
- [MISC] Add WORKERLOCK_MEMORY_SIZE setting for worker dict size
- [MISC] Add API_TIMEOUT and API_READ_TIMEOUT settings to control API timeouts
- [DEPS] Updated coreruleset-v4 version to v4.8.0
- [DEPS] Updated coreruleset-v3 version to v3.3.7

## v1.5.10 - 2024/08/17

- [UI] Fix setup wizard bug related to certificate
- [UI] Fix bug when adding more than 3 reverse proxies URLs
- [UI] Fix wrong type for REVERSE_PROXY_SSL_SNI_NAME setting
- [BUGFIX] Add HTTP3 specific modsec rule in web UI to avoid false positives
- [BUGFIX] Fix missing scheduler logs in Linux integration
- [BUGFIX] Add missing REPORT HTTP method to ALLOWED_METHODS setting
- [DEPS] Updated NGINX version to v1.26.2
- [DEPS] Updated LuaJIT version to v2.1-20240815
- [DEPS] Updated libmaxminddb version to v1.11.0
- [DEPS] Updated lua-cjson to latest commit for the version v2.1.0.14
- [DEPS] Updated lua-nginx-module version to v0.10.27
- [DEPS] Updated lua-resty-core version to v0.1.29
- [DEPS] Updated lua-resty-lrucache version to v0.14
- [DEPS] Updated lua-resty-openssl version to v1.5.1
- [DEPS] Updated lua-resty-signal version to v0.04
- [DEPS] Updated lua-resty-string version to v0.16
- [DEPS] Updated stream-lua-nginx-module version to v0.0.15
- [DEPS] Updated coreruleset-v4 version to v4.6.0
- [DEPS] Updated coreruleset-v3 version to v3.3.6
- [DEPS] Updated ModSecurity version to v3.0.13
- [DEPS] Start managing Mbed TLS as a dependency for ModSecurity (v3.6.1)

## v1.5.9 - 2024/07/22

- [BUGFIX] Fix compatibility issues with mysql 8.4+ version and the `backup` plugin by adding the `mariadb-connector-c` dependency to the scheduler Dockerfile (on alpine)
- [BUGFIX] Fix potential issues with multiple settings in helpers.load_variables when multiple settings have the same suffix (the issue is only present in future external plugins)
- [BUGFIX] Fix issues with kubernetes integration when were setting a global multisite setting it was not applied to the services
- [FEATURE] Add REVERSE_PROXY_SSL_SNI and REVERSE_PROXY_SSL_SNI_NAME to support SNI-based upstreams
- [UI] Update web UI setup wizard to handle when a reverse proxy already exists but no admin user is configured
- [UI] Fix issues with multiple settings on the global_config not being able to be deleted in specific cases
- [AUTOCONF] Fix issues with globally set settings overridden by default values not being saved correctly in database
- [LINUX] Update Linux repository to repo.bunkerweb.io
- [SECURITY] Update security headers in default pages and error pages for improved security
- [DEPS] Updated LuaJIT version to v2.1-20240626
- [DEPS] Updated coreruleset-v4 version to v4.5.0

## v1.5.8 - 2024/06/19

- [LINUX] Support Fedora 40 and drop support of Fedora 39
- [BUGFIX] Fix potential errors when upgrading from a previous version
- [BUGFIX] Fix rare bug on the web UI when editing the SERVER_NAME setting of a service
- [BUGFIX] Fix potential race conditions between the autoconf and the scheduler waiting for each other indefinitely
- [BUGFIX] Fix Let's Encrypt certificate renewal when a certificate date changes by forcing the renewal
- [BUGFIX] Fix issues with k8s integration and the save_config.py script
- [FEATURE] Add nightly build of the OWASP coreruleset that are automatically downloaded and updated
- [FEATURE] Enhance security on error pages, default server page and loading page by adding a custom `Content-Security-Policy` header with nonces and removing the `Server` header
- [FEATURE] Add new DATABASE_URI_READONLY setting to allow setting up a fallback read-only database URI in case the main database URI is not available
- [FEATURE] Add automatic fallback to either read-only on the primary database or to the read-only database URI when the main database URI is not available and automatically switch back to the main database URI when it becomes available again
- [FEATURE] Add experimental support of HTTP/3 (QUIC)
- [FEATURE] Optimize the way the scheduler handles jobs and the way the jobs are executed
- [FEATURE] Optimize the way the cache files are being refreshed from the database
- [FEATURE] Add failover logic in case the NGINX configuration is not valid to fallback to the previous configuration and log the error to prevent the service from being stopped
- [UI] Force HTTPS on setup wizard
- [UI] Fallback to self-signed certificate when UI is installed with setup wizard and let's encrypt is not used
- [UI] Force HTTPS even if UI is installed in advanced mode
- [UI] Add OVERRIDE_ADMIN_CREDS environment variable to allow overriding the default admin credentials even if an admin user already exists
- [UI] Optimize the way the UI handles the requests and the responses
- [AUTOCONF] Refactor Autoconf config parsing and saving logic so that it doesn't override the scheduler or UI config every time
- [MISC] Update logger format and datefmt for better readability
- [DEPS] Updated NGINX version to v1.26.1
- [DEPS] Updated stream-lua-nginx-module version to the latest commit to incorporate the latest changes and fixes for NGINX v1.26
- [DEPS] Updated coreruleset-v4 version to v4.3.0
- [DEPS] Updated lua-resty-openssl version to v1.4.0

## v1.5.7 - 2024/05/14

- [LINUX] Support Ubuntu 24.04 (Noble)
- [LINUX] Support RHEL 9.4 instead of 9.3
- [LINUX] Support hot reload with systemctl reload
- [BUGFIX] Fix rare error when the cache is not properly initialized and jobs are executed
- [BUGFIX] Fix bug when downloading new mmdb files
- [BUGFIX] Remove potential false positives with ModSecurity on the jobs page of the web UI
- [BUGFIX] Fix bwcli not working with Redis sentinel
- [BUGFIX] Fix potential issues when removing the bunkerweb Linux package
- [BUGFIX] Fix bug when antibot is enabled and User-Agent or IP address has changed
- [FEATURE] Add backup plugin to backup and restore easily the database
- [FEATURE] Add LETS_ENCRYPT_CLEAR_OLD_CERTS setting to control if old certificates should be removed when generating Let's Encrypt certificates (default is no)
- [FEATURE] Add DISABLE_DEFAULT_SERVER_STRICT_SNI setting to allow/block requests when SNI is unknown or unset (default is no)
- [UI] General : fix tooltip crop because of overflow
- [UI] General : fix select setting crop because of overflow and check if select is out of viewport to determine visible position
- [UI] General : show logs on UI when pre rendering issue
- [UI] General : Improve UI performance by using multiple workers for the web server and reducing the number of times we prompt a loading page
- [UI] General : handle word breaks on dynamic text content
- [UI] General : fix overflow issue with tables on Safari
- [UI] General : fix static resources issue with firefox leading to loop requests
- [UI] Global config : fix script error while fragment relate to a missing plugin
- [UI] Global config / services page : filtering settings now open plugin select to highlight remaining plugin
- [UI] Global config / services page : add combobox on plugin select open to search a plugin quick
- [UI] Global config / services page : add order for settings to always respect the order defined in the plugin
- [UI] Services page : show any invalid setting value on setting modal and disabled save if case
- [UI] Reporting page : fix missing data and add new ones
- [UI] Account page : keep license key form even if pro register to easy update
- [UI] Wizard : Add the possibility to still configure reverse proxy even if an admin user already exists
- [AUTOCONF] Speedup autoconf process when we have multiple events in short period of time
- [DOCUMENTATION] Add upgrade procedure for 1.5.7+
- [DOCUMENTATION] Rename Migrating section to Upgrading
- [MISC] Drop support of ansible and vagrant integrations
- [MISC] Support custom bwcli commands using plugins
- [MISC] Add Docker labels in autoconf, bw, scheduler, and ui Dockerfiles
- [DEPS] Update Python base Docker image to version 3.12.3-alpine3.19
- [DEPS] Updated LuaJIT version to v2.1-20240314
- [DEPS] Updated lua-resty-openssl version to 1.3.1
- [DEPS] Updated coreruleset-v4 version to v4.2.0

## v1.5.6 - 2024/03/25

- [LINUX] Support RHEL 9.3
- [BUGFIX] Fix issues with the antibot feature ([#866](https://github.com/bunkerity/bunkerweb/issues/866), [#870](https://github.com/bunkerity/bunkerweb/issues/870))
- [BUGFIX] Fix Bad behavior whitelist check in access phase
- [BUGFIX] Fix ModSecurity FP on antibot page
- [BUGFIX] Fix Whitelist core plugin missing a check for empty server_name in multisite mode
- [BUGFIX] Fix Templator missing some common configs
- [BUGFIX] Database update with external plugins reupload
- [BUGFIX] UI delete or edit multiple setting
- [LINUX] Add logrotate support for the logs
- [UI] New : add bans management page in the web UI
- [UI] New : add blocked requests page in the web UI
- [UI] New : some core plugins pages in the web UI
- [UI] General : enhance the Content-Security-Policy header in the web UI
- [UI] General : dark mode enhancement
- [UI] General : add visual feedback when filtering is matching nothing
- [UI] General : blog news working and add dynamic banner news
- [UI] Global config page : Add multisite edit, add context filter
- [UI] Global config / Service page : remove tabs for select and enhance filtering (plugin name, multiple settings and context now includes)
- [UI] Service page : add the possibility to clone a service in the web UI
- [UI] Service page : add the possibility to set a service as draft in the web UI
- [UI] Service page : add services filter when at least 4 services
- [UI] Configs page : add path filtering related to config presence, remove service when config is root only
- [UI] Pro license : add home card, show pro plugins on menu and plugins page, resume in account page, alert in case issue with license usage
- [UI] Log page : enhance UX
- [FEATURE] Add setting REDIS_SSL_VERIFY to activate/disable the SSL certificate verification when using Redis
- [FEATURE] Add Redis Sentinel fallback to master automatically if no slaves are available
- [FEATURE] Add Redis Sentinel support for bwcli
- [FEATURE] Add new Metrics core plugin that will allow metrics collection and retrieval of internal metrics
- [FEATURE] Add setting DATABASE_LOG_LEVEL to control SQLAlchemy loggers separately from the main one
- [FEATURE] Add whitelist check for the default-server as well
- [FEATURE] Add the possibility to choose between the coreruleset v3 and v4 that will be used by ModSecurity (default is v3)
- [FEATURE] Add the TIMERS_LOG_LEVEL setting to control the log level of the lua timers
- [FEATURE] Add pro version management to core plugins, the scheduler and the web UI
- [FEATURE] Add REVERSE_PROXY_CUSTOM_HOST setting to set a custom Host header when using reverse proxy
- [MISC] Add a better custom certificate cache handling
- [MISC] Updated Linux base images in Dockerfiles
- [MISC] Add recommended dialects to databases string
- [MISC] Refine the data sent in the anonymous reporting feature and move the setting and the job to the "jobs" plugin
- [MISC] BunkerWeb will now load the default loading page even on 404 errors when generating the configuration
- [MISC] Update database schema to support the new pro version and optimize it
- [MISC] Refactor SSL/TLS logics to make it more consistent
- [MISC] Use ECDSA key instead of RSA for selfsigned/default/fallback certificates
- [MISC] Refactor certbot-new job to optimize the certbot requests
- [MISC] Refactor jobs utils to make it more consistent
- [MISC] Review jobs and utils to make it more consistent and better in general
- [MISC] Change BunkerWeb base Docker image to nginx:1.24.0-alpine-slim
- [DOCUMENTATION] Update web UI's setup wizard instructions in the documentation
- [DOCUMENTATION] Update plugins documentation to reflect the new plugin system
- [DOCUMENTATION] Update ModSecurity documentation to reflect the new changes in the Security Tuning section
- [DOCUMENTATION] Add pro version documentation
- [DEPS] Updated stream-lua-nginx-module to v0.0.14
- [DEPS] Updated lua-nginx-module version to v0.10.26
- [DEPS] Updated libmaxminddb version to v1.9.1
- [DEPS] Updated lua-resty-core to v0.1.28
- [DEPS] Updated zlib version to v1.3.1
- [DEPS] Updated ModSecurity version to v3.0.12
- [DEPS] Updated coreruleset version to v3.3.5
- [DEPS] Added coreruleset version v4.1.0
- [DEPS] Updated lua-resty-mlcache version to v2.7.0
- [DEPS] Updated lua-resty-openssl version to v1.2.1
- [DEPS] Updated lua-resty-http version to v0.17.2

## v1.5.5 - 2024/01/12

- [BUGFIX] Fix issues with the database when upgrading from one version to a newer one
- [BUGFIX] Fix ModSecurity-nginx to make it work with brotli
- [BUGFIX] Remove certbot renew delay causing errors on k8s
- [BUGFIX] Fix missing custom modsec files when BW instances change
- [BUGFIX] Fix inconsistency on config changes when using Redis
- [BUGFIX] Fix web UI not working when using / URL
- [FEATURE] Add Anonymous reporting feature
- [FEATURE] Add support for fallback Referrer-Policies
- [FEATURE] Add 2FA support to web UI
- [FEATURE] Add username and password management to web UI
- [FEATURE] Add setting REVERSE_PROXY_INCLUDES to manually add "include" directives in the reverse proxies
- [FEATURE] Add support for Redis Sentinel
- [FEATURE] Add support for tls in Ingress definition
- [MISC] Fallback to default HTTPS certificate to prevent errors
- [MISC] Various internal improvements in LUA code
- [MISC] Check nginx configuration before reload
- [MISC] Updated Python Docker image to 3.12.1-alpine3.18 in Dockerfiles
- [DEPS] Updated ModSecurity to v3.0.11

## v1.5.4 - 2023/12/04

- [UI] Add an optional setup wizard for the web UI
- [BUGFIX] Fix issues with the Linux integration and external databases
- [BUGFIX] Fix scheduler trying to connect to Docker socket in k8s and swarm
- [LINUX] Support Debian 12, Fedora 39 and RHEL 8.9
- [DOCKER] Handle start and stop event of BunkerWeb with the scheduler
- [MISC] Refactor database session handling to make it more stable with SQLite
- [MISC] Add conditional block for open file cache in nginx config
- [MISC] Updated core dependencies
- [MISC] Updated python dependencies
- [MISC] Updated Python Docker image to 3.12.0-alpine3.18 in Dockerfiles

## v1.5.3 - 2023/10/31

- [BUGFIX] Fix BunkerWeb not loading his own settings after a docker restart
- [BUGFIX] Fix Custom configs not following the service name after an update on the UI
- [BUGFIX] Fix UI clearing configs folder at startup
- [BUGFIX] Fix Database not clearing old services when not using multisite
- [BUGFIX] Fix UI using the wrong database when generating the new config when using an external database
- [BUGFIX] Small fixes on linux paths creating unnecessary folders
- [BUGFIX] Fix ACME renewal fails on redirection enabled Service
- [BUGFIX] Fix errors when using a server name with multiple values in web UI
- [BUGFIX] Fix error when deleting a service that have custom configs on web UI
- [BUGFIX] Fix rare bug where database is locked
- [MISC] Updated core dependencies
- [MISC] Updated self-signed job to regenerate the cert if the subject or the expiration date has changed
- [MISC] Jobs that download files from urls will now remove old cached files if urls are empty
- [MISC] Replaced gevent with gthread in UI for security reasons
- [MISC] Add HTML sanitization when injecting code in pages in the UI
- [MISC] Optimize the way the UI handles services creation and edition
- [MISC] Optimize certbot renew script to renew all domains in one command
- [MISC] Use capability instead of sudo in Linux
- [SECURITY] Init work on OpenSSF best practices

## v1.5.2 - 2023/09/10

- [BUGFIX] Fix UI fetching only default values from the database (fixes no trash button too)
- [BUGFIX] Fix infinite loop when using autoconf
- [BUGFIX] Fix BunkerWeb fails to start after reboot on Fedora and Rhel
- [BUGFIX] Fix logs page not working in UI on Linux integrations
- [BUGFIX] Fix settings regex that had issues in general and with the UI
- [BUGFIX] Fix scheduler error with external plugins when reloading
- [BUGFIX] Fix permissions with folders in linux integrations
- [MISC] Push Docker images to GitHub packages (ghcr.io repository)
- [MISC] Improved CI/CD
- [MISC] Updated python dependencies
- [MISC] Updated Python Docker image to 3.11.5-alpine in Dockerfiles
- [MISC] Add support for ModSecurity JSON LogFormat
- [MISC] Updated OWASP coreruleset to 3.3.5

## v1.5.1 - 2023/08/08

- [BUGFIX] New version checker in logs displays "404 not found"
- [BUGFIX] New version checker in UI
- [BUGFIX] Only get the right keys from plugin.json files when importing plugins
- [BUGFIX] Remove external resources for Google fonts in UI
- [BUGFIX] Support multiple plugin uploads in one zip when using the UI
- [BUGFIX] Variable being ignored instead of saved in the database when value is empty
- [BUGFIX] ALLOWED_METHODS regex working with LOCK/UNLOCK methods
- [BUGFIX] Custom certificate bug after the refactoring
- [BUGFIX] Wrong variables in header phase (fix CORS feature too)
- [BUGFIX] UI not working in Ubuntu (python zope module)
- [BUGFIX] Patch ModSecurity to run it after LUA code (should fix whitelist problems)
- [BUGFIX] Custom configurations from env were not being deleted properly
- [BUGFIX] Missing concepts image not displayed in the documentation
- [BUGFIX] Scheduler not picking up new instances IPs in autoconf modes
- [BUGFIX] Autoconf deadlock in k8s
- [BUGFIX] Missing HTTP and HTTPS ports for temp nginx
- [BUGFIX] Infinite loop when sessions is not valid
- [BUGFIX] Missing valid LE certificates in edge cases
- [BUGFIX] Wrong service namespace in k8s
- [BUGFIX] DNS_RESOLVERS regex not accepting hostnames
- [PERFORMANCE] Reduce CPU and RAM usage of scheduler
- [PERFORMANCE] Cache ngx.ctx instead of loading it each time
- [PERFORMANCE] Use per-worker LRU cache for common RO LUA values
- [FEATURE] Add Turnstile antibot mode
- [FEATURE] Add more CORS headers
- [FEATURE] Add KEEP_UPSTREAM_HEADERS to preserve headers when using reverse proxy
- [FEATURE] Add the possibility to download the different lists and plugins from a local file (like the blacklist)
- [FEATURE] External plugins can now be downloaded from a tar.gz and tar.xz file as well as zip
- [FEATURE] Add X-Forwarded-Prefix header when using reverse proxy
- [FEATURE] Add REDIRECT_TO_STATUS_CODE to choose status code 301 or 302 when redirecting
- [DOCUMENTATION] Add timezone information
- [DOCUMENTATION] Add timezone informat
- [MISC] Add LOG_LEVEL=warning for docker socket proxy in docs, examples and boilerplates
- [MISC] Temp remove VMWare provider for Vagrant integration
- [MISC] Remove X-Script-Name header and ABSOLUTE_URI variable when using UI
- [MISC] Move logs to /var/log/bunkerweb folder
- [MISC] Reduce "Got an error reading communication packets" warnings in mariadb/mysql

## v1.5.0 - 2023/05/23

- Refactoring of almost all the components of the project
- Dedicated scheduler service to manage jobs and configuration
- Store configuration in a database backend
- Improved web UI and make it working with all integrations
- Improved internal LUA code
- Improved internal cache of BW
- Add Redis support when using clustered integrations
- Add RHEL integration
- Add Vagrant integration
- Init support of generic TCP/UDP (stream)
- Init support of IPv6
- Improved CI/CD : UI tests, core tests and release automation
- Reduce Docker images size
- Fix and improved core plugins : antibot, cors, dnsbl, ...
- Use PCRE regex instead of LUA patterns
- Connectivity tests at startup/reload with logging

## v1.5.0-beta - 2023/05/02

- Refactoring of almost all the components of the project
- Dedicated scheduler service to manage jobs and configuration
- Store configuration in a database backend
- Improved web UI and make it working with all integrations
- Improved internal LUA code
- Improved internal cache of BW
- Add Redis support when using clustered integrations
- Add RHEL integration
- Add Vagrant integration
- Init support of generic TCP/UDP (stream)
- Init support of IPv6
- Improved CI/CD : UI tests, core tests and release automation
- Reduce Docker images size
- Fix and improved core plugins : antibot, cors, dnsbl, ...
- Use PCRE regex instead of LUA patterns
- Connectivity tests at startup/reload with logging

## v1.4.8 - 2023/04/05

- Fix UI bug related to multiple settings
- Increase check reload interval in UI to avoid rate limit
- Fix Let's Encrypt error when using auth basic
- Fix wrong setting name in realip job (again)
- Fix blog posts retrieval in the UI
- Fix missing logs for UI
- Fix error log if BunkerNet ip list is empty
- Updated python dependencies
- Gunicorn will now show the logs in the console for the UI
- BunkerNet job will now create the ip list file at the beginning of the job to avoid errors

## v1.4.7 - 2023/02/27

- Fix DISABLE_DEFAULT_SERVER=yes not working with HTTPS (again)
- Fix wrong setting name in realip job
- Fix whitelisting not working with modsecurity

## v1.4.6 - 2023/02/14

- Fix error in the UI when a service have multiple domains
- Fix bwcli bans command
- Fix documentation about Linux Fedora install
- Fix DISABLE_DEFAULT_SERVER=yes not working with HTTPS
- Add INTERCEPTED_ERROR_CODES setting

## v1.4.5 - 2022/11/26

- Fix bwcli syntax error
- Fix UI not working using Linux integration
- Fix missing openssl dep in autoconf
- Fix typo in selfsigned job

## v1.4.4 - 2022/11/10

- Fix k8s controller not watching the events when there is an exception
- Fix python dependencies bug in CentOS and Fedora
- Fix incorrect log when reloading nginx using Linux integration
- Fix UI dev mode, production mode is now the default
- Fix wrong exposed port in the UI container
- Fix endless loading in the UI
- Fix \*_CUSTOM_CONF_\* dissapear when jobs are executed
- Fix various typos in documentation
- Fix warning about StartLimitIntervalSec directive when using Linux
- Fix incorrect log when issuing certbot renew
- Fix certbot renew error when using Linux or Docker integration
- Add greylist core feature
- Add BLACKLIST_IGNORE_\* settings
- Add automatic change of SecRequestBodyLimit modsec directive based on MAX_CLIENT_SIZE setting
- Add MODSECURITY_SEC_RULE_ENGINE and MODSECURITY_SEC_AUDIT_LOG_PARTS settings
- Add manual ban and get bans to the API/CLI
- Add Brawdunoir community example
- Improve core plugins order and add documentation about it
- Improve overall documentation
- Improve CI/CD

## v1.4.3 - 2022/08/26

- Fix various documentation errors/typos and add various enhancements
- Fix ui.env not read when using Linux integration
- Fix wrong variables.env path when using Linux integration
- Fix missing default server when TEMP_NGINX=yes
- Fix check if BunkerNet is activated on default server
- Fix request crash when mmdb lookup fails
- Fix bad behavior trigger when request is whitelisted
- Fix bad behavior not triggered when request is on default server
- Fix BW overriding config when config is already present
- Add Ansible integration in beta
- Add \*_CUSTOM_CONF_\* setting to automatically add custom config files from setting value
- Add DENY_HTTP_STATUS setting to choose standard 403 error page (default) or 444 to close connection when access is denied
- Add CORS (Cross-Origin Resource Sharing) core plugin
- Add documentation about Docker in rootless mode and podman
- Improve automatic tests setup
- Migrate CI/CD infrastructure to another provider

## v1.4.2 - 2022/06/28

- Fix "too old resource version" exceptions when using k8s integration
- Fix missing bwcli command with Linux integration
- Fix various bugs with jobs scheduler when using autoconf/swarm/k8s
- Fix bwcli unban command when using Linux integration
- Fix permissions check when filename has a space
- Fix static config (SERVER_NAME not empty) support when using autoconf/swarm/k8s
- Fix config files overwrite when using Docker autoconf
- Add EXTERNAL_PLUGIN_URLS setting to automatically download and install external plugins
- Add log_default() plugin hook
- Add various certbot-dns examples
- Add mattermost example
- Add radarr example
- Add Discord and Slack to list of official plugins
- Force NGINX version dependencies in Linux packages DEB/RPM

## v1.4.1 - 2022/06/16

- Fix sending local IPs to BunkerNet when DISABLE_DEFAULT_SERVER=yes
- Fix certbot bug when AUTOCONF_MODE=yes
- Fix certbot bug when MULTISITE=no
- Add reverse proxy timeouts settings
- Add auth_request settings
- Add authentik and authelia examples
- Prebuilt Docker images for arm64 and armv7
- Improve documentation for Linux integration
- Various fixes in the documentation

## v1.4.0 - 2022/06/06

- Project renamed to BunkerWeb
- Internal architecture fully revised with a modular approach
- Improved CI/CD with automatic tests for multiple integrations
- Plugin improvement
- Volume improvement for container-based integrations
- Web UI improvement with various new features
- Web tool to generate settings from a user-friendly UI
- Linux packages
- Various bug fixes

## v1.3.2 - 2021/10/24

- Use API instead of a shared folder for Swarm and Kubernetes integrations
- Beta integration of distributed bad IPs database through a remote API
- Improvement of the request limiting feature : hour/day rate and multiple URL support
- Various bug fixes related to antibot feature
- Init support of Arch Linux
- Fix Moodle example
- Fix ROOT_FOLDER bug in serve-files.conf when using the UI
- Update default values for PERMISSIONS_POLICY and FEATURE_POLICY
- Disable COUNTRY ban if IP is local

## v1.3.1 - 2021/09/02

- Use ModSecurity v3.0.4 instead of v3.0.5 to fix memory leak
- Fix ignored variables to control jobs
- Fix bug when LISTEN_HTTP=no and MULTISITE=yes
- Add CUSTOM_HEADER variable
- Add REVERSE_PROXY_BUFFERING variable
- Add REVERSE_PROXY_KEEPALIVE variable
- Fix documentation for modsec and modsec-crs special folders

## v1.3.0 - 2021/08/23

- Kubernetes integration in beta
- Linux integration in beta
- autoconf refactoring
- jobs refactoring
- UI refactoring
- UI security : login/password authentication and CRSF protection
- various dependencies updates
- move CrowdSec as an external plugin
- Authelia support
- improve various regexes
- add INJECT_BODY variable
- add WORKER_PROCESSES variable
- add USE_LETS_ENCRYPT_STAGING variable
- add LOCAL_PHP and LOCAL_PHP_PATH variables
- add REDIRECT_TO variable

## v1.2.8 - 2021/07/22

- Fix broken links in README
- Fix regex for EMAIL_LETS_ENCRYPT
- Fix regex for REMOTE_PHP and REMOTE_PHP_PATH
- Fix regex for SELF_SIGNED_*
- Fix various bugs related to web UI
- Fix bug in autoconf (missing instances parameter to reload function)
- Remove old .env files when generating a new configuration

## v1.2.7 - 2021/06/14

- Add custom robots.txt and sitemap to RTD
- Fix missing GeoIP DB bug when using BLACKLIST/WHITELIST_COUNTRY
- Add underscore "_" to allowed chars for CUSTOM_HTTPS_CERT/KEY
- Fix bug when using automatic self-signed certificate
- Build and push images from GitHub actions instead of Docker Hub autobuild
- Display the reason when generator is ignoring a variable
- Various bug fixes related to certbot and jobs
- Split jobs into pre and post jobs
- Add HEALTHCHECK to image
- Fix race condition when using autoconf without Swarm by checking healthy state
- Bump modsecurity-nginx to v1.0.2
- Community chat with bridged platforms

## v1.2.6 - 2021/06/06

- Move from "ghetto-style" shell scripts to generic jinja2 templating
- Init work on a basic plugins system
- Move ClamAV to external plugin
- Reduce image size by removing unnecessary dependencies
- Fix CrowdSec example
- Change some global variables to multisite
- Add LOG_LEVEL environment variable
- Read-only container support
- Improved antibot javascript with a basic proof of work
- Update nginx to 1.20.1
- Support of docker-socket-proxy with web UI
- Add certbot-cloudflare example
- Disable DNSBL checks when IP is local

## v1.2.5 - 2021/05/14

- Performance improvement : move some nginx security checks to LUA and external blacklist parsing enhancement
- Init work on official documentation on readthedocs
- Fix default value for CONTENT_SECURITY_POLICY to allow file downloads
- Add ROOT_SITE_SUBFOLDER environment variable

## TODO - retrospective changelog
