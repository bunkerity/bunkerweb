# Change version in CRS

This page describes how can you change the version strings in CRS rules.

## Goals

The problem is change the version string in CRS rules isn't trivial. Version string used for mark all rule by the `ver` action, mark the whole file in a comment, or mark the rule set with `SecComponentSignature`. Few examples:

* in a rule: `SecRule ARGS "foo" "id:1,phase:1,ver:'OWASP_CRS/3.3.0',pass"`
* comment: `# OWASP ModSecurity Core Rule Set ver.3.3.0`
* config directive: `SecComponentSignature "OWASP_CRS/3.3.0"`

There are many other pattern which look-a-like version string, but that isn't it.

The main task is replace only the real version strings by the new one.

The Python script below helps to do that on the whole rule set or any unique file.

## Prerequisites

* Python3 interpreter
* [msc_pyparser](https://github.com/digitalwave/msc_pyparser)
* CRS rule set

You can install the `msc_pyparser` through PIP - that's the recommended method, see the [instructions](https://github.com/digitalwave/msc_pyparser#installing-using-pip3).

If you already have this package, don't forget to update it before you start the work:

```bash
python3 -m pip install --upgrade msc_pyparser
```

## Usage

The script expects three mandatory and one optional arguments:

* input file or directory
* output **directory**
* version string for `ver` actions and `SecComponentSignature` - these are always the same
* and optionally, the version string for comments

Please note that the input can be a single file (eg. 'coreruleset/rules/REQUEST-901-INITIALIZATION.conf' or a directory with meta name, eg 'coreruleset/rules/*.conf'. Also note that the output argument is always a **directory** where the script puts the transformed file or files.

### Run the script

Consider you want to change only the `ver` and `SecComponentSignature` values by a new one, eg: `OWASP_CRS/3.4.0-dev`. The current value is `OWASP_CRS/3.3.0`. The next command will solve this:

```bash
mkdir /path/to/coreruleset/rules_new
$ ./change-version.py "/path/to/coreruleset/rules/*.conf" /path/to/coreruleset/rules_new "OWASP_CRS/3.4.0-dev"
Working with file: /path/to/coreruleset/rules/REQUEST-903.9005-CPANEL-EXCLUSION-RULES.conf
Working with file: /path/to/coreruleset/rules/REQUEST-903.9008-PHPMYADMIN-EXCLUSION-RULES.conf
...
Working with file: /path/to/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf
Working with file: /path/to/coreruleset/rules/REQUEST-912-DOS-PROTECTION.conf
```

The new files will placed under the `/path/to/coreruleset/rules_new`, now make a diff:

```bash
$ for f in `ls -1 /path/to/coreruleset/rules/*.conf`; do b=`basename ${f}`; diff ${f} /path/to/coreruleset/rules_new/${b}; done
28c28
< SecComponentSignature "OWASP_CRS/3.3.0"
---
> SecComponentSignature "OWASP_CRS/3.4.0-dev"
61c61
<     ver:'OWASP_CRS/3.3.0',\
---
>     ver:'OWASP_CRS/3.4.0-dev',\
79c79
<     ver:'OWASP_CRS/3.3.0',\
---
>     ver:'OWASP_CRS/3.4.0-dev',\
...
```

As you can see, the comments have been left untouched.

In the next example, we can replace them too:

```bash
$ ./change-version.py "/path/to/coreruleset/rules/*.conf" /path/to/coreruleset/rules_new "OWASP_CRS/3.4.0-dev" "3.4.0-dev"
Working with file: /path/to/coreruleset/rules/REQUEST-903.9005-CPANEL-EXCLUSION-RULES.conf
Working with file: /path/to/coreruleset/rules/REQUEST-903.9008-PHPMYADMIN-EXCLUSION-RULES.conf
...
Working with file: /path/to/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf
Working with file: /path/to/coreruleset/rules/REQUEST-912-DOS-PROTECTION.conf
```

Run the diff again:

```bash
$ for f in `ls -1 /path/to/coreruleset/rules/*.conf`; do b=`basename ${f}`; diff ${f} /path/to/coreruleset/rules_new/${b}; done
2c2
< # OWASP ModSecurity Core Rule Set ver.3.3.0
---
> # OWASP ModSecurity Core Rule Set ver.3.4.0-dev
28c28
< SecComponentSignature "OWASP_CRS/3.3.0"
---
> SecComponentSignature "OWASP_CRS/3.4.0-dev"
61c61
<     ver:'OWASP_CRS/3.3.0',\
---
>     ver:'OWASP_CRS/3.4.0-dev',\
79c79
<     ver:'OWASP_CRS/3.3.0',\
---
>     ver:'OWASP_CRS/3.4.0-dev',\
...
```

As you can see, the version string at the end of comment line has changed in line 2.
