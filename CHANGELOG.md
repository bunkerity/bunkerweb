# Changelog

## v1.6.0-rc2 - ????/??/??

- [BUGFIX] Whitelisting a client no longer bypasses https redirect settings as the `ssl` plugin is now executed before the `whitelist` plugin
- [UI] Fixed condition when validating the setup wizard form when a custom certificate is used
- [FEATURE] Add extra validation of certificates in `customcert` plugin
- [FEATURE] Introduce new `SSL` plugin to manage SSL/TLS settings without tweaking the `misc` plugin
- [FEATURE] Add `stream` support in `Kubernetes` integration
- [FEATURE] Add support for Zstandard (Zstd) compression algorithm through the new `zstd` plugin
- [DOCS] Added Swarm deprecated notice in the documentation
- [DEPS] Updated libmaxminddb version to v1.12.2
- [DEPS] Added zstd version v1.5.6
- [DEPS] Added zstd-nginx-module version v0.1.1+

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
