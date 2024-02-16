owasp-crs-regressions
=====================

Introduction
============
Welcome to the OWASP CRS regression testing suite. This suite is meant to test specific rules in OWASP CRS version 3. The suite is designed to use pre-configured IDs that are specific to this version of CRS. The tests themselves can be run without CRS and one would expect the same elements to be blocked, however one must override the default Output parameter in the tests.

Installation
============
The OWASP CRS project was part of the effort to develop the Web Application Firewall Testing Framework (FTW), a framework for Testing WAFs. We recommend using `go-ftw`: a modern, fast, and efficient way to test the WAF. By utilizing it, you can test your WAF effortlessly in two steps: define a test case in YAML and run it with go-ftw.

```yaml
# example of test case: /tests/regression/tests/REQUEST-911-METHOD-ENFORCEMENT
# format can be found at: https://github.com/coreruleset/ftw/blob/master/docs/YAMLFormat.md
---
meta:
  author: "csanders-git"
  enabled: true
  name: "911100.yaml"
  description: "Description"
tests:
  - test_title: 911100-1
    stages:
      - stage:
          input:
            dest_addr: "127.0.0.1"
            port: 80
            headers:
              User-Agent: "OWASP CRS test agent"
              Host: "localhost"
              Accept: text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5
          output:
            no_log_contains: "id \"911100\""
```

For go-ftw, please check out from [go-ftw releases page](https://github.com/coreruleset/go-ftw/releases).

Requirements
============
There are three requirements for running the OWASP CRS regressions:

1. Create `.ftw.yaml` for your environment. (see Section [Yaml Config File](https://github.com/coreruleset/go-ftw#yaml-config-file) in go-ftw for more details)
2. Specify your error.log location from ModSecurity in `.ftw.yaml`.
3. Make sure ModSecurity is in `DetectionOnly` mode.

The following rule is provided to properly configure your engine for testing. Add it to crs-setup.conf:
```
SecAction "id:900005,\
  phase:1,\
  nolog,\
  pass,\
  ctl:ruleEngine=DetectionOnly,\
  ctl:ruleRemoveById=910000,\
  setvar:tx.blocking_paranoia_level=4,\
  setvar:tx.crs_validate_utf8_encoding=1,\
  setvar:tx.arg_name_length=100,\
  setvar:tx.arg_length=400,\
  setvar:tx.max_file_size=64100,\
  setvar:tx.combined_file_sizes=65535"
```

Running The Tests
=================

On Windows this will look like:
-------------------------------
Single Rule File:
```py.test.exe -v CRS_Tests.py --rule=tests/test.yaml```
The Whole Suite:
```py.test.exe -v CRS_Tests.py --ruledir_recurse=tests/```

On Linux this will look like:
-----------------------------
Single Rule File:
```py.test -v CRS_Tests.py --rule=tests/test.yaml```
The Whole Suite:
```py.test -v CRS_Tests.py --ruledir_recurse=tests/```

Contributions
=============

We'd like to thank Fastly for their help and support in developing these tests.
