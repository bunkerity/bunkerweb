# Troubleshooting

## Logs

When troubleshooting, the logs are your best friends. We try our best to provide user-friendly logs to help you understand what happened.

If you are using container based integrations, you can get the logs using your manager/orchestrator (e.g., docker logs, docker service logs, kubectl logs, ...). For Linux integration, everything is stored inside the `/var/log` folder.

You can edit the `LOG_LEVEL` environment variable to increase or decrease the verbosity of logs with the following values : `debug`, `info`, `notice`, `warn`, `error`, `crit`, `alert` or `emerg` (with `debug` being the most verbose level).

## Permissions

Don't forget that bunkerized-nginx runs as an unprivileged user with UID/GID 101 when using container based integrations or simply the `nginx` user on Linux. Double check the permissions of files and folders for each special folders (see the [volumes list](https://bunkerized-nginx.readthedocs.io/en/latest/special_folders.html)).

## ModSecurity

The OWASP Core Rule Set can sometimes leads to false positives. Here is what you can do :
- Check if your application has exclusions rules (e.g : wordpress, nextcloud, drupal, ...)
- Edit the matched rules to exclude some parameters, URIs, ...
- Remove the matched rules if editing it is too much a hassle

Some additional resources : 
- [Wordpress example](https://github.com/bunkerity/bunkerized-nginx/tree/master/examples/wordpress)
- [Handling false positive](https://www.netnea.com/cms/apache-tutorial-8_handling-false-positives-modsecurity-core-rule-set/)
- [Adding exceptions and tuning](https://coreruleset.org/docs/exceptions.html)

## Bad behavior

The [bad behavior](https://bunkerized-nginx.readthedocs.io/en/latest/security_tuning.html#bad-behaviors-detection) feature comes with a set of status codes considered as "suspicious". You may need to tweak the corresponding list to avoid false positives within your application.

## Whitelisting

It's a common case that a bot gets flagged as suspicious and can't access your website. Instead of disabling the corresponding security feature(s) we recommend a whitelisting approach. Here is a list of environment variables you can use :

- `WHITELIST_IP_LIST`
- `WHITELIST_REVERSE_LIST`
- `WHITELIST_URI`
- `WHITELIST_USER_AGENT`

More information [here](https://bunkerized-nginx.readthedocs.io/en/latest/environment_variables.html#custom-whitelisting).

