# Changelog

## v1.5.2 - 

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
