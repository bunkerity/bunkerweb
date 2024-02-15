---
name: 'False positive'
about: Report a false positive (blocking of benign traffic)
title: ''
labels: ':heavy_plus_sign: False Positive'
assignees: ''
---

<!--
Please do not open issues for help and support running ModSecurity or the
OWASP Core Rule Set. Instead, use one of the following channels to reach
our project:

* https://security.stackexchange.com/questions/tagged/owasp-crs
* https://twitter.com/coreruleset
* https://groups.google.com/a/owasp.org/g/modsecurity-core-rule-set-project
* https://owasp.org/slack/invite (-> Channel #coreruleset)
-->

### Description

<!--
We want to be able to understand and to reproduce your problem. Please describe
it here in detail.

It is safest if you assume we know nothing about your service or software.
-->

### How to reproduce the misbehavior (-> curl call)

<!--
It is easiest for us, if you submit a curl request that triggers your problem.
If you can not do this, then please skip this section but be sure to fill out
the next one in detail.

Please test your curl call against the CRS Sandbox before submitting.
https://coreruleset.org/docs/development/sandbox/
-->

### Logs

<!--
Feel free to skip this section if you provided a curl call above.

Ideally, you provide a full audit log of the request, relevant infos out of
the error log or at least a screenshot where we can see the payload so we
can reproduce the behavior.

Usually, you find the logs at a location like /var/log/modsec_audit.log.
When using a CDN or cloud server, the naming of the logs and their location
depends on the provider. Please refer to their documentation.

If you cannot submit neither curl call nor log files nor a payload to reproduce
the behavior, there is litterally nothing we can do for you. Please help us to
get access to the information we need to help you.
-->

### Your Environment

<!-- Please provide all relevant information about your environment. -->

* CRS version (e.g., v3.3.4):
* Paranoia level setting (e.g. PL1) :
* ModSecurity version (e.g., 2.9.6):
* Web Server and version or cloud provider / CDN (e.g., Apache httpd 2.4.54):
* Operating System and version:

### Confirmation

[ ] I have removed any personal data (email addresses, IP addresses,
    passwords, domain names) from any logs posted.
