# Find the longest data in CRS test cases

This page describes how can you find the longest data string in CRS test cases.

## Goals

Some rules check the `FILES_COMBINED_SIZE` against the `TX:COMBINED_FILE_SIZES` variable. To check these work as well, we need to set the `tx.combined_file_sizes` variable and send a payload which is greater than this value - see [this](https://github.com/coreruleset/coreruleset/blob/v3.4/dev/tests/regression/README.md#requirements):

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
  setvar:tx.combined_file_sizes=MAX_LEN"
```

In `modsecurity-crs-docker` [here](https://github.com/coreruleset/modsecurity-crs-docker/blob/master/src/opt/modsecurity/activate-rules.sh#L79-L82) is how the setting works.

To configure the Github action, you need to set up this in CORERULESET/test/docker-compose.yaml:

```
   ...
   COMBINED_FILE_SIZES=MAX_LEN
   ...
```

## Usage

To find the possible value of MAX_LEN, run this script with one mandatory, and one optional argument. The mandatory argument is the path of the CRS directory (the root). The optional argument is the `-i` or `--ignoretests`, where you can pass the test id what you want to skip - eg. you want to use the test to exceed the maximum length.

```
./find_max_datalen.py ../.. -i 920410-1
```

In this case, you pass the CRS root as parent dir, and skip the test id 920410-1, which wants to exceed the maximum length.

## Prerequisites

* Python3 interpreter
* Py-YAML
* CRS rule set
