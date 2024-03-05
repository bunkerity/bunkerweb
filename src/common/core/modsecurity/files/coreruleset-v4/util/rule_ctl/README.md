draft

# OWASP CRS Rule Control Script
This script aims to help when a bulk change on configuration files is needed. rule_ctl.py can, for example, change the value of an action on all rules, or can add/remove/rename a tag on each rule in a file, or can add/remove a transformation function only in rules that match range 942100-942190, etc...

## Example Usage

There're only two mandatory parameters: `--config` and `--filter-rule-id`.

**--config** set the target config file<br>
**--filter-rule-id** a regex that matches only rule ids to change

For example, if you want to add a new tag on each rule in file `REQUEST-933-APPLICATION-ATTACK-PHP.conf` you can do:

```sh
python3 util/rule_ctl/rule_ctl.py \
    --config rules/REQUEST-933-APPLICATION-ATTACK-PHP.conf \
    --filter-rule-id ^933.+ \
    --append-tag foo
    --dryrun
```

`--dryrun` sends to stdout the result of changes and prevent writing changes on file. It's a good idea to always check all commands with dryrun before overwrite the target configuration file.

You can even alphabetically sort tag list while adding new tags:
```sh
python3 util/rule_ctl/rule_ctl.py \
    --config rules/REQUEST-933-APPLICATION-ATTACK-PHP.conf \
    --filter-rule-id ^933.+ \
    --append-tag foo
    --sort-tag
    --dryrun
```

## Variables
- `--append-variable`: Append a variable on the variable list of selected rules
- `--remove-variable`: Remove exact matching variable from selected rules
- `--replace-variable`: Replace variable on selected rules

### Examples
Replace the variable name `ARGS` with `ARGS_GET`
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^.\* \
    --replace-variable ARGS,ARGS_GET \
    --dryrun
```

Replace the variable `ARGS` with `!ARGS_GET:'lisa'`
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^.\* \
    --replace-variable ARGS,\!ARGS_GET:\'lisa\' \
    --dryrun
```

## Tags
- `--append-tag`: Append a new tag to the tag list on selected rules
- `--remove-tag`: Remove tag from tag list on selected rules
- `--rename-tag`: Rename tag on selected rules
- `--sort-tags`: Alphabetically sort tag list on selected rules

### Examples
Append a new tag `foo` and sort tag list
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^.\* \
    --append-tag foo \
    --sort-tags \
    --dryrun
```

Remove a tag `foo`
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^.\* \
    --remove-tag foo \
    --dryrun
```

Rename a tag `foo`
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^.\* \
    --rename-tag foo,bar \
    --dryrun
```

## Transformation Functions
- `--append-tfunc`: Append a new transformation function on selected rules
- `--remove-tfunc`: Remove a transformation function on selected rules

### Examples
Append `t:lowercase` to all selected rules (you don't need the `t:` prefix)
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^.\* \
    --append-tfunc lowercase \
    --dryrun
```

## Actions
- `--replace-action`: Replace action on selected rules
- `--remove-action`: remove action from selected rules

### Examples
Replace action `severity:CRITICAL` with `severity:INFO` and set a new message on rule id 125
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^125 \
    --replace-action severity:CRITICAL,severity:INFO \
    --uncond-replace-action 'msg:this is a new message for rule 125' \
    --dryrun
```

## CTL
- `--append-ctl`: Append a new ctl action on selected rules

### Examples
Remove rule id 1337 on rule 125 by adding ctl:ruleRemoveById=1337. Do it on main rule (skipping chained rules if present)
```sh
python3 rule_ctl.py --config ../../rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf \
    --filter-rule-id ^125 \
    --append-ctl ruleRemoveById=1337 \
    --skip-chain \
    --dryrun
```

## Others
- `--target-file`: Set the target file where changes will be saved (default: use file set by `--config`)
- `--skip-chain`: Skip chained rules
- `--dryrun`: Do not write any changes, just output the results
- `--debug`: Show debug messages
- `--silent`: Used with `--dryrun` and `--debug` doesn't write and shows only debug messages
- `--json`: Used with `--dryrun` return the msc_pyparser JSON output instead of ModSecurity file
