# Find the rules without test cases

This page describes how can you find the rules without any test cases

## Goal

The main goal is that we must have at least one regression test for all relevant REQUEST- * rules. (In this context, the PL control rules are not relevant, because they do not need to have tests.)

You need to pass the CORERULESET_ROOT as argument, eg:
```
util/find-rules-without-test/find-rules-without-test.py /path/to/coreruleset
```

Optionally you can pass the argument `--output=github` or `--output=native`. The last one is the default.

The script collects all available test files, based on the name of the test files. It will look up under CORERULESET_ROOT/tests/regression/tests/*.

Then it starts to read all rule files with name "REQUEST-\*", which means this won't handle the RESPONSE-* rules.

The script parses the rules, uses `msc_pyparser`, reads the rule's id, and tries to find the test case.

The sctipt ignores the check in case of PL control rules (rules with id under 9XX100), and some hardcoded rules:
 * REQUEST-900-
 * REQUEST-901-
 * REQUEST-905-
 * REQUEST-910-
 * REQUEST-912.
 * REQUEST-949-


## Prerequisites

* Python3 interpreter
* Py-YAML
* msc_pyparser
* CRS rule set
