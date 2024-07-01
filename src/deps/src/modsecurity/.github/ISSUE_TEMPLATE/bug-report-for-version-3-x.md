---
name: Bug report for version 3.x
about: Create a report to help us improve. If you don't know a specific detail or
  piece of information leave it blank, if necessary we will help you to figure out.
title: ''
labels: ''
assignees: ''

---

**Describe the bug**

A clear and concise description of what the bug is.

**Logs and dumps**

Output of:
 1. DebugLogs (level 9)
 2. AuditLogs
 3. Error logs
 4. If there is a crash, the core dump file.

_Notice:_ Be careful to not leak any confidential information.

**To Reproduce**

Steps to reproduce the behavior:

A **curl** command line that mimics the original request and reproduces the problem. Or a ModSecurity v3 test case.

[e.g: curl "modsec-full/ca/..\\..\\..\\..\\..\\..\\/\\etc/\\passwd" or [issue-394.json](https://github.com/SpiderLabs/ModSecurity/blob/v3/master/test/test-cases/regression/issue-394.json)]


**Expected behavior**

A clear and concise description of what you expected to happen.

**Server (please complete the following information):**
 - ModSecurity version (and connector): [e.g. ModSecurity v3.0.8 with nginx-connector v1.0.3]
 - WebServer: [e.g. nginx-1.18.0]
 - OS (and distro): [e.g. Linux, archlinux]


**Rule Set (please complete the following information):**
 - Running any public or commercial rule set? [e.g. SpiderLabs commercial rules]
 - What is the version number? [e.g. 2018-08-11]

**Additional context**

Add any other context about the problem here.
