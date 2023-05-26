from .helpers import *

class TestAppendControl:
    def test_append_ctl_with_no_ctls(self):
        arguments = [
            "--append-ctl", "ruleRemoveTargetById=1234;ARGS:passwd",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,ctl:ruleRemoveTargetById=1234;ARGS:passwd"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_ctl_with_existing_ctls(self):
        arguments = [
            "--append-ctl", "ruleRemoveTargetById=1234;ARGS:passwd",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    ctl:ruleRemoveTargetById=1234;ARGS:username"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    ctl:ruleRemoveTargetById=1234;ARGS:username,\\
    ctl:ruleRemoveTargetById=1234;ARGS:passwd"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_ctl_with_duplicate_ctl(self):
        arguments = [
            "--append-ctl", "ruleRemoveTargetById=1234;ARGS:passwd",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    ctl:ruleRemoveTargetById=1234;ARGS:passwd,\\
    log:'abc'"
"""

        context = create_context(arguments, rule_string)
        assert rule_string == get_output(context)

    def test_append_ctl_in_correct_order(self):
        arguments = [
            "--append-ctl", "ruleRemoveTargetById=1234;ARGS:passwd",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    sanitiseMatchedBytes,\\
    ver:3"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    sanitiseMatchedBytes,\\
    ctl:ruleRemoveTargetById=1234;ARGS:passwd,\\
    ver:3"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_ctl_ignores_ctl_prefix(self):
        arguments = [
            "--append-ctl", "ctl:ruleRemoveTargetById=1234;ARGS:passwd",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,ctl:ruleRemoveTargetById=1234;ARGS:passwd"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_ctl_with_chain(self):
        arguments = [
            "--append-ctl", "ctl:ruleRemoveTargetById=1234;ARGS:passwd",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx bar"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,ctl:ruleRemoveTargetById=1234;ARGS:passwd,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx bar" "ctl:ruleRemoveTargetById=1234;ARGS:passwd"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_ctl_skip_chain(self):
        arguments = [
            "--append-ctl", "ctl:ruleRemoveTargetById=1234;ARGS:passwd",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx bar"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,ctl:ruleRemoveTargetById=1234;ARGS:passwd,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx bar"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)
