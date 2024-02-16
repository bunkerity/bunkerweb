#! /usr/bin/env python

import sys, re, json, uuid

try:
    import argparse, msc_pyparser
except:
    print(f"Error: missing modules.\nYou can install all dependences with: pip3 install -r requirements.txt")
    sys.exit(1)

ACTION_ORDER = {
    key: index for index, key in enumerate(
        [
            "id",
            "phase",
            "allow",
            "block",
            "deny",
            "drop",
            "pass",
            "proxy",
            "redirect",
            "status",
            "capture",
            "t",
            "log",
            "nolog",
            "auditlog",
            "noauditlog",
            "msg",
            "logdata",
            "tag",
            "sanitiseArg",
            "sanitiseRequestHeader",
            "sanitiseMatched",
            "sanitiseMatchedBytes",
            "ctl",
            "ver",
            "severity",
            "multiMatch",
            "initcol",
            "setenv",
            "setvar",
            "expirevar",
            "chain",
            "skip",
            "skipAfter"
        ]
    )
}

class Context(object):
    def __init__(self):
        self.args = ()
        self.line_number_change = 0
        self.next_index_to_parse = 0
        self.parser = None
        self._rules = []
        self._rules_map = {}

    def parse_rules(self, data):
        mparser = msc_pyparser.MSCParser()
        mparser.parser.parse(data, debug = False)

        for line in mparser.configlines:
            type = line["type"]
            if type == "SecAction":
                rule = SecAction(line, self)
            elif type == "Comment":
                rule = Comment(line, self)
            elif type == "SecRule":
                rule = SecRule(line, self)
            else:
                rule = Directive(line, self)

            self._rules.append(rule)
            if isinstance(rule, SecAction):
                if rule.is_chained():
                    self._rules_map[rule.id]['chained'].append(rule)
                else:
                    self._rules_map[rule.id] = {
                        'rule': rule,
                        'chained': []
                    }
            yield rule

    def get_chain_starter_rule(self, rule):
        try:
            self._rules_map[rule.id]['rule']
        except KeyError:
            # Chained rules don't have ID during initialization.
            # In this case, however, the last parsed rule now has one
            return self._rules_map[self._rules[-1].id]['rule']

    def dprint(self, rule_id, action, message, indent):
        if not indent:
            indent=0

        prefix = "[*]"
        if indent > 0:
            prefix = "`"

        if not rule_id:
            rule_id = "chained"

        print(f'{" "*int(indent)}{prefix} \033[92m{rule_id}/{action}\033[0m: {message}')

    def generate_output(self):
        mwriter = msc_pyparser.MSCWriter(self.generate_lines())
        mwriter.generate()
        return mwriter.output

    def generate_lines(self):
        generated_lines = []
        line_number_change = 0
        for rule in self._rules:
            lines, line_number_change = rule.generate_lines(line_number_change)
            generated_lines.append(lines)
        return generated_lines

    def parse_arguments(self, args=None):
        args_parser = self._create_args_parser()
        self.args = args_parser.parse_args(args)

    def _create_args_parser(self):
        parser = argparse.ArgumentParser(description="OWASP CRS Configuration Control")
        parser.add_argument("--config", dest="config", help="OWASP ModSecurity CRS config file path", required=True)
        parser.add_argument("--filter-rule-id", dest="filter_rule_id", help="Filter on ruleid (regex)", required=False)
        parser.add_argument("--append-variable", dest="append_variable", help="Append var on SecRule (string)", action='append', required=False)
        parser.add_argument("--remove-variable", dest="remove_variable", help="Remove var from SecRule (string)", action='append', required=False)
        parser.add_argument("--replace-variable", dest="replace_variable", help="Replace var in SecRule (old,new) (string)", action='append', required=False)
        parser.add_argument("--append-tag", dest="append_tag", help="Append tag on SecRule (string)", required=False)
        parser.add_argument("--remove-tag", dest="remove_tag", help="Remove tag from SecRule (string)", required=False)
        parser.add_argument("--rename-tag", dest="rename_tag", help="Rename tag on SecRule (old,new) (string)", required=False)
        parser.add_argument("--sort-tags", dest="sort_tags", help="Sort tag list in SecRule", action="store_true", required=False)
        parser.add_argument("--append-tfunc", dest="append_tfunc", help="Append transformation func on SecRule (example: urlDecodeUni) (string)", action='append', required=False)
        parser.add_argument("--remove-tfunc", dest="remove_tfunc", help="Remove transformation func from SecRule (example: urlDecodeUni) (string)", action='append', required=False)
        parser.add_argument("--append-action", dest="append_action", help="Append action on Secrule (example: 'severity:CRITICAL) (string)", required=False)
        parser.add_argument("--replace-action", dest="replace_action", help="Replace action (example: 'severity:CRITICAL,severity:INFO') (string)", required=False)
        parser.add_argument("--remove-action", dest="remove_action", help="Remove action from SecRule (string)", required=False)
        parser.add_argument("--append-ctl", dest="append_ctl", help="Append ctl action on SecRule (example: 'ruleRemoveTargetById=1234;ARGS:passwd') (string)", required=False)
        parser.add_argument("--target-file", dest="target_file", help="Save changes in another file (string)", required=False)
        parser.add_argument("--skip-chain", dest="skip_chain", help="Skip chained rules", action="store_true", required=False)
        parser.add_argument("--dryrun", dest="dryrun", help="Show changes without write", action="store_true", required=False)
        parser.add_argument("--silent", dest="silent", help="Do not output content file on dryrun", action="store_true", required=False)
        parser.add_argument("--debug", dest="debug", help="Show debug messages", action="store_true", required=False)
        parser.add_argument("--json", dest="output_json", help="Get all output in JSON format", action="store_true", required=False)
        return parser

class RuleFileItem(object):
    def __init__(self, data, context):
        self._data = data
        self._line_numbers = {"rule_line": data["lineno"]}

    def modify(self, context):
        pass

    def generate_lines(self, line_number_change):
        new_line_number_change = self._update_line_numbers(line_number_change)
        return (self._data, new_line_number_change)

    def _update_line_numbers(self, line_number_change):
        self._data["lineno"] = self._line_numbers["rule_line"] + line_number_change

        return line_number_change

class SecAction(RuleFileItem):
    TAG_RENAME_REGEX = re.compile('^([^,]+),(.+)$')
    ACTION_REPLACE_REGEX = re.compile('^([^,]+),(.+)$')
    ACTION_REPLACE_VALUES_REGEX = re.compile('^([^:]+)(?::(.+))?$')
    CTL_APPEND_REGEX = re.compile('^([^=]+)=([^;]+)(;[^:]+:.+|)$')
    CTL_APPEND_PARAMS_REGEX = re.compile('^;([^:]+):(.+)$')
    id = None
    _id_matcher = None

    def __init__(self, data, context):
        super().__init__(data, context)

        for action in self.get_actions():
            action["id"] = uuid.uuid4()
            if action["act_name"] == "id":
                self.id = int(action["act_arg"])
                break

        if "oplineno" in self._data:
            self._line_numbers["opline"] = self._data["oplineno"]
        for action in self.get_actions():
            self._line_numbers[("action", uuid)] = action["lineno"]

    def _parse_var(self, variable):
        negated = False
        counter = False
        newvar = variable
        newvarpart = ""
        quote_type = "no_quote"
        m = re.match('^([!&]?)([^:]+)(?::(.+))?$', variable)
        if m:
            counter = m.group(1) == '&'
            negated = m.group(1) == '!'
            newvar = m.group(2)
            varpart = m.group(3)
            if varpart is not None:
                if varpart[0] == '"' and varpart[-1] == '"':
                    quote_type = 'quoted'
                    varpart = varpart[1:-1]
                elif varpart[0] == "'" and varpart[-1] == "'":
                    quote_type = 'quotes'
                    varpart = varpart[1:-1]
                newvarpart = varpart
        return {
            "variable": newvar,
            "variable_part": newvarpart,
            "quote_type": quote_type,
            "negated": negated,
            "counter": counter
        }

    def _is_equal_variable(self, variable1, variable2):
        compare_fields = ("variable", "variable_part", "negated", "counter")
        return all(variable1[field] == variable2[field] for field in compare_fields)

    def _has_variable(self, variable):
        for var in self.get_variables():
            if self._is_equal_variable(variable, var):
                return True
        return False



    def _update_line_numbers(self, line_number_change):
        #TODO: doesn't yet work when order changes, e.g. variables and tags may not have been grouped together
        super()._update_line_numbers(line_number_change)

        first_line_number = last_line_number = self._data["lineno"]

        if "oplineno" in self._data:
            last_line_number = self._line_numbers["opline"] + line_number_change
            self._data["oplineno"] = last_line_number


        for action in self.get_actions():
            try:
                last_line_number = self._line_numbers[("action", action["id"])] + line_number_change
                action["lineno"] = last_line_number
            except KeyError:
                # keep everything on one line if it already was
                if any(lineno > self._line_numbers['rule_line'] for lineno in self._line_numbers.values()):
                    last_line_number += 1
                action["lineno"] = last_line_number

        original_first_line_number = min(self._line_numbers.values())
        original_last_line_number = max(self._line_numbers.values())
        original_length = original_last_line_number - original_first_line_number
        new_length = last_line_number - first_line_number
        start_change = first_line_number - original_first_line_number
        length_change = new_length - original_length
        total_change = length_change + start_change
        return total_change

    def modify(self, context):
        if context.args.filter_rule_id and not self.matches_id(context.args.filter_rule_id):
            return

        self.append_tag(context)
        self.remove_tag(context)
        self.rename_tag(context)
        self.append_tfunc(context)
        self.remove_tfunc(context)
        self.append_action(context)
        self.replace_action(context)
        self.remove_action(context)
        self.append_variables(context)
        self.remove_variables(context)
        self.replace_variables(context)
        self.append_ctl(context)
        self.sort_tags(context)

    def get_actions(self):
        try:
            return self._data["actions"]
        except KeyError:
            return []

    def set_actions(self, actions):
        self._data["actions"] = actions

    def get_variables(self):
        try:
            return self._data["variables"]
        except KeyError:
            return []

    def set_variables(self, variables):
        self._data["variables"] = variables

    def get_tags(self):
        return [action for action in self.get_actions() if action["act_name"] == "tag"]

    def get_ctls(self):
        return [action for action in self.get_actions() if action["act_name"] == "ctl"]

    def matches_id(self, id_pattern):
        if self._id_matcher is None:
            self._id_matcher = re.compile(id_pattern)
        return self._id_matcher.match(str(self.id)) != None

    def append_tag(self, context):
        if context.args.append_tag is None:
            return

        #TODO: support appending multiple tags
        tags = self.get_tags()
        if context.args.append_tag in [tag["act_arg"] for tag in tags]:
            return

        actions = self.get_actions()
        new_act_list = []
        last_tag_line = 0
        tag_order = ACTION_ORDER["tag"]
        new_tag = {
            'id': uuid.uuid4(),
            'act_name': 'tag',
            'lineno': 0,
            'act_quote': 'quotes',
            'act_arg': context.args.append_tag,
            'act_arg_val': '',
            'act_arg_val_param': '',
            'act_arg_val_param_val': ''
        }

        done = False
        last_action_index = len(actions) - 1
        for index, action in enumerate(actions):
            action_name = action["act_name"]
            action_order = ACTION_ORDER[action_name]
            if action_order <= tag_order:
                last_tag_line = action["lineno"]
                new_act_list.append(action)
            if not done and (action_order > tag_order or index == last_action_index):
                done = True
                new_act_list.append(new_tag)
                if context.args.debug:
                    context.dprint(self.id, "append-tag", f"append tag {context.args.append_tag} on line {last_tag_line}", 0)
            if action_order > tag_order:
                new_act_list.append(action)
        self.set_actions(new_act_list)

    def remove_tag(self, context):
        if context.args.remove_tag is None:
            return

        #TODO: support removing multiple tags
        actions = self.get_actions()
        new_act_list = []
        for action in actions:
            if action["act_name"] == "tag":
                if action["act_arg"] != context.args.remove_tag:
                    new_act_list.append(action)
                else:
                    if context.args.debug:
                        context.dprint(self.id, "remove-tag", f"remove tag {context.args.remove_tag} on line {action['lineno']}", 0)
            else:
                new_act_list.append(action)

        self.set_actions(new_act_list)

    def rename_tag(self, context):
        if context.args.rename_tag is None:
            return

        match = self.TAG_RENAME_REGEX.match(context.args.rename_tag)
        if match is None:
            return

        old_tag = match.group(1)
        new_tag = match.group(2)
        new_act_list = []
        for act in self.get_actions():
            if act["act_name"] == "id":
                current_rule_id = act["act_arg"]
            if act["act_name"] == "tag":
                if act["act_arg"] == old_tag:
                    act["act_arg"] = new_tag
                    if context.args.debug:
                        context.dprint(current_rule_id, "rename-tag", f"rename tag {old_tag} to {new_tag} on line {act['lineno']}", 0)
                new_act_list.append(act)
            else:
                new_act_list.append(act)
        self.set_actions(new_act_list)

    def append_action(self, context):
        if context.args.append_action is None:
            return

        match = self.ACTION_REPLACE_VALUES_REGEX.match(context.args.append_action)
        if match is None:
            return

        new_action_name = match.group(1)
        new_action_value = match.group(2) or ""

        #TODO: support appending multiple actions
        actions = self.get_actions()
        if (
            new_action_name in [action["act_name"] for action in actions] and
            new_action_value in [action["act_arg"] for action in actions]
        ):
            return

        new_act_list = []
        last_action_line = 0
        new_action_order = ACTION_ORDER[new_action_name]
        has_quotes = len(new_action_value) > 0 and new_action_value[0] in '"\'' and new_action_value[-1] in '"\''
        if has_quotes:
            new_action_value = new_action_value[1:-1]
        new_action = {
            'id': uuid.uuid4(),
            'act_name': new_action_name,
            'lineno': 0,
            'act_quote': 'quotes' if has_quotes else 'no_quote',
            'act_arg': new_action_value,
            'act_arg_val': '',
            'act_arg_val_param': '',
            'act_arg_val_param_val': ''
        }

        done = False
        last_action_index = len(actions) - 1
        for index, action in enumerate(actions):
            action_name = action["act_name"]
            action_order = ACTION_ORDER[action_name]
            if action_order <= new_action_order:
                last_action_line = action["lineno"]
                new_act_list.append(action)
            if not done and (action_order > new_action_order or index == last_action_index):
                done = True
                new_act_list.append(new_action)
                if context.args.debug:
                    context.dprint(self.id, "append-action", f"append action {context.args.append_action} on line {last_action_line}", 0)
            if action_order > new_action_order:
                new_act_list.append(action)

        if len(new_act_list) == 0:
            new_act_list.append(new_action)

        self.set_actions(new_act_list)



    def replace_action(self, context):
        if context.args.replace_action is None:
            return

        match = self.ACTION_REPLACE_REGEX.match(context.args.replace_action)
        if match is None:
            return

        from_string = match.group(1)
        to_string = match.group(2)
        from_match = self.ACTION_REPLACE_VALUES_REGEX.match(from_string)
        to_match = self.ACTION_REPLACE_VALUES_REGEX.match(to_string)
        if from_match is None or to_match is None:
            return

        from_actname = from_match.group(1)
        from_actvalue = from_match.group(2) or ""
        to_actname = to_match.group(1)
        to_actvalue = to_match.group(2) or ""
        has_quotes = len(to_actvalue) > 0 and to_actvalue[0] in '"\'' and to_actvalue[-1] in '"\''
        if has_quotes:
            to_actvalue = to_actvalue[1:-1]

        for act in self.get_actions():
            if act["act_name"] == from_actname:
                # match all actions of the specified name if `from_actvalue` is empty
                if len(from_actvalue) == 0 or act["act_arg"] == from_actvalue:
                    act["act_name"] = to_actname
                    act["act_arg"] = to_actvalue
                    act["act_quote"] = "quotes" if has_quotes else "no_quote"

    def remove_action(self, context):
        if context.args.remove_action is None:
            return

        actions = self.get_actions()
        new_act_list = []
        for action in actions:
            if action["act_name"] != context.args.remove_action:
                new_act_list.append(action)

        self.set_actions(new_act_list)

    def append_tfunc(self, context):
        if context.args.append_tfunc is None:
            return

        transform_order = ACTION_ORDER["t"]
        actions = self.get_actions()
        last_action_index = len(actions) - 1
        transformation_names = [action["act_arg"] for action in actions if action["act_name"] == "t"]

        for tfunc in context.args.append_tfunc:
            if tfunc in transformation_names:
                continue

            new_act_list = []
            done = False
            last_lineno = 0
            for index, act in enumerate(actions):
                action_name = act["act_name"]
                action_order = ACTION_ORDER[action_name]
                if action_order <= transform_order:
                    last_lineno = act["lineno"]
                    new_act_list.append(act)
                if not done and (action_order > transform_order or index == last_action_index):
                    done = True
                    new_act_list.append({
                        'id': uuid.uuid4(),
                        'act_name': 't',
                        'lineno': last_lineno,
                        'act_quote': 'no_quote',
                        'act_arg': tfunc,
                        'act_arg_val': '',
                        'act_arg_val_param': '',
                        'act_arg_val_param_val': ''
                    })
                    if context.args.debug:
                        context.dprint(self.id, "append-tfunc", f"append transformation {context.args.append_tfunc} on line {last_lineno}", 0)
                if action_order > transform_order:
                    new_act_list.append(act)
            actions = new_act_list

        self.set_actions(actions)


    def remove_tfunc(self, context):
        if context.args.remove_tfunc is None:
            return

        actions = self.get_actions()
        for tfunc in context.args.remove_tfunc:
            new_act_list = []
            for act in actions:
                if act["act_name"] == "t":
                    if act["act_arg"] != tfunc:
                        new_act_list.append(act)
                else:
                    new_act_list.append(act)
            actions = new_act_list

        self.set_actions(actions)


    def append_variables(self, context):
        if context.args.append_variable is None:
            return

        variables = self.get_variables()
        for nv in context.args.append_variable:
            newvar = self._parse_var(nv)
            if self._has_variable(newvar):
                continue

            new_var_list = []
            for v in variables:
                new_var_list.append(v)
            new_var_list.append({
                "variable": newvar["variable"],
                "variable_part": newvar["variable_part"],
                "quote_type": "no_quote",
                "negated": newvar["negated"],
                "counter": newvar["counter"]
            })
            if context.args.debug:
                context.dprint(self.id, "append-variable", f"Append variable {newvar}:{newvar['variable_part']}", 0)
            variables = new_var_list

        self.set_variables(variables)


    def remove_variables(self, context):
        if context.args.remove_variable is None:
            return

        variables = self.get_variables()
        for nv in context.args.remove_variable:
            var = self._parse_var(nv)
            if not self._has_variable(var):
                continue

            new_var_list = []
            for v in variables:
                if not self._is_equal_variable(var, v):
                    new_var_list.append(v)
                else:
                    if context.args.debug:
                        varpart = var["variable_part"]
                        negated = var["negated"]
                        counter = var["counter"]
                        context.dprint(self.id, "remove-variable", f"Removed variable {var}:{varpart} negated:{negated} counter:{counter}", 0)
            variables = new_var_list
        self.set_variables(variables)


    def replace_variables(self, context):
        if context.args.replace_variable is None:
            return

        variables = self.get_variables()
        for nv_tosplit in context.args.replace_variable:
            oldvar, newvar = nv_tosplit.split(",")
            ov = self._parse_var(oldvar)
            nv = self._parse_var(newvar)

            new_variable = nv["variable"]
            newvarpart = nv["variable_part"]
            newnegated = nv["negated"]
            newcounter = nv["counter"]
            newquotetype = nv["quote_type"]
            old_variable = ov["variable"]
            oldvarpart = ov["variable_part"]
            oldnegated = ov["negated"]
            oldcounter = ov["counter"]
            oldquotetype = ov["quote_type"]
            new_var_list = []
            for v in variables:
                if (v["variable"] == old_variable and v["variable_part"] == oldvarpart
                        and v["negated"] == oldnegated and v["counter"] == oldcounter and v["quote_type"] == oldquotetype):
                    new_var_list.append({
                        "variable": new_variable,
                        "variable_part": newvarpart,
                        "quote_type": newquotetype,
                        "negated": newnegated,
                        "counter": newcounter
                    })
                    if context.args.debug:
                        context.dprint(self.id, "replace-variable", f"Replaced variable {oldvar}:{oldvarpart} negated:{oldnegated} counter:{oldcounter} quote_type:{oldquotetype} with {newvar}:{newvarpart} negated:{newnegated} counter:{newcounter} quote_type:{newquotetype}", 0)
                else:
                    new_var_list.append(v)
            variables = new_var_list

        self.set_variables(variables)

    def append_ctl(self, context):
        # TODO: support appending multiple ctl
        if context.args.append_ctl is None:
            return

        match = self.CTL_APPEND_REGEX.match(context.args.append_ctl)
        if match is None:
            return

        arg = match.group(1)
        if arg.startswith('ctl:'):
            arg = arg[4:]
        val = match.group(2)

        params = self.CTL_APPEND_PARAMS_REGEX.match(match.group(3))
        param = params.group(1) if params is not None else ""
        paramval = params.group(2) if params is not None else ""

        ctls = self.get_ctls()
        if (
            arg in [ctl["act_arg"] for ctl in ctls] and
            val in [ctl["act_arg_val"] for ctl in ctls] and
            param in [ctl["act_arg_val_param"] for ctl in ctls] and
            paramval in [ctl["act_arg_val_param_val"] for ctl in ctls]
        ):
            return

        actions = self.get_actions()
        new_act_list = []
        last_ctl_line = 0
        ctl_order = ACTION_ORDER["ctl"]
        new_ctl = {
            "id": uuid.uuid4(),
            "act_name": "ctl",
            "lineno": last_ctl_line,
            "act_quote": "no_quote",
            "act_arg": arg,
            "act_arg_val": val,
            "act_arg_val_param": param,
            "act_arg_val_param_val": paramval
        }

        done = False
        last_action_index = len(actions) - 1
        for index, action in enumerate(actions):
            action_name = action["act_name"]
            action_order = ACTION_ORDER[action_name]
            if action_order <= ctl_order:
                last_ctl_line = action["lineno"]
                new_act_list.append(action)
            if not done and (action_order > ctl_order or index == last_action_index):
                done = True
                new_act_list.append(new_ctl)
                if context.args.debug:
                    context.dprint(self.id, "append-ctl", f"append ctl {context.args.append_ctl} on line {last_ctl_line}", 0)
            if action_order > ctl_order:
                new_act_list.append(action)

        if len(new_act_list) == 0:
            new_act_list.append(new_ctl)

        self.set_actions(new_act_list)


    def sort_tags(self, context):
        #TODO: tags don't need to be grouped together; need to look through all actions
        if not context.args.sort_tags:
            return

        new_act_list = []
        post_tag_actions = []
        tags = []
        last_lineno = None
        found_tag = False
        for act in self.get_actions():
            if act["act_name"] == "tag":
                tags.append(act)
                found_tag = True
                if last_lineno is None:
                    first_lineno = act["lineno"]
            elif not found_tag:
                new_act_list.append(act)
            elif found_tag:
                post_tag_actions.append(act)

        def get_sort_key(tag):
            return tag["act_arg"].lower()

        sorted_tags = sorted(tags, key=get_sort_key)
        for tag in sorted_tags:
            new_act_list.append(tag)
            tag["lineno"] = first_lineno
            first_lineno += 1

        for act in post_tag_actions:
            new_act_list.append(act)

        self.set_actions(new_act_list)

class Comment(RuleFileItem):
    pass

class Directive(RuleFileItem):
    pass

class SecRule(SecAction):
    _is_chained = False

    def __init__(self, data, context):
        super().__init__(data, context)

        # for chained rules (they have no ID)
        if self.id is None:
            self.id = context.get_chain_starter_rule(self).id
            self._is_chained = True

    def has_chained_rules(self):
        return self._data["chained"]

    def is_chained(self):
        return self._is_chained

    def modify(self, context):
        if context.args.skip_chain and self.is_chained():
            return

        super().modify(context)


def write_output(context):
    if context.args.dryrun and context.args.output_json:
        print(json.dumps(context.generate_lines(), indent=4))
        return

    if context.args.dryrun:
        if not context.args.silent:
            print("\n".join(context.generate_output()))
        return

    path = context.args.target_file if context.args.target_file else context.args.config
    with open(path, 'w') as handle:
        handle.write("\n".join(context.generate_output()))


def run():
    context = Context()
    context.parse_arguments()

    with open(context.args.config) as file:
        data = file.read()

    for rule in context.parse_rules(data):
        rule.modify(context)

    write_output(context)

if __name__ == '__main__':
    run()
