# Changelog

## v1.3.2 -

- Use API instead of a shared folder for Swarm and Kubernetes integrations
- Beta integration of distributed bad IPs database through a remote API
- Improvement of the request limiting feature : hour/day rate and multiple URL support
- Various bug fixes related to antibot feature
- Init support of Arch Linux
- Fix Moodle example
- Fix ROOT_FOLDER bug in serve-files.conf when using the UI

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
