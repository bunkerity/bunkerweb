# CRS KNOWN BUGS

## Report Bugs/Issues to GitHub Issues Tracker or the mailinglist

* https://github.com/coreruleset/coreruleset/issues
or the CRS Google Group at
* https://groups.google.com/a/owasp.org/forum/#!forum/modsecurity-core-rule-set-project

* There are still false positives for standard web applications in
  the default install (paranoia level 1). Please report these when
  you encounter them.
  False Positives from paranoia level 2 rules are less interesting,
  as we expect users to write exclusion rules for their alerts in
  the higher paranoia levels.
* Permanent blocking of clients is based on a previous user agent / IP
  combination. Changing the user agent will thus allow to bypass
  this new filter. The plan is to allow for a purely IP based
  filter in the future.
* Apache 2.4 prior to 2.4.11 is affected by a bug in parsing multi-line
  configuration directives, which causes Apache to fail during startup
  with an error such as:
    Error parsing actions: Unknown action: \\
    Action 'configtest' failed.
  This bug is known to plague RHEL/Centos 7 below v7.4 or
  httpd v2.4.6 release 67 and Ubuntu 14.04 LTS users.
  https://bz.apache.org/bugzilla/show_bug.cgi?id=55910
  We advise to upgrade your Apache version. If upgrading is not possible,
  we have provided a script in the util/join-multiline-rules directory
  which converts the rules into a format that works around the bug.
  You have to re-run this script whenever you modify or update
  the CRS rules.
* Debian up to and including Jessie lacks YAJL/JSON support in ModSecurity,
  which causes the following error in the Apache ErrorLog or SecAuditLog:
    'ModSecurity: JSON support was not enabled.'
  JSON support was enabled in Debian's package version 2.8.0-4 (Nov 2014).
  You can either use backports.debian.org to install the latest ModSecurity
  release or disable rule id 200001.
* As of CRS version 3.0.1, support has been added for the application/soap+xml MIME
  type by default, as specified in RFC 3902. OF IMPORTANCE, application/soap+xml is
  indicative that XML will be provided. In accordance with this, ModSecurity's XML
  Request Body Processor should also be configured to support this MIME type. Within
  the ModSecurity project, [commit 5e4e2af](https://github.com/SpiderLabs/ModSecurity/commit/5e4e2af7a6f07854fee6ed36ef4a381d4e03960e)
  has been merged to support this endeavour. However, if you are running a modified or
  preexisting version of the modsecurity.conf provided by this repository, you may
  wish to upgrade rule '200000' accordingly. The rule now appears as follows:
  ```
  SecRule REQUEST_HEADERS:Content-Type "(?:application(?:/soap\+|/)|text/)xml" \
       "id:'200000',phase:1,t:none,t:lowercase,pass,nolog,ctl:requestBodyProcessor=XML"
  ```
