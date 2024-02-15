from .helpers import *

class TestAppendAction:
    def test_append_action_with_no_actions(self):
        arguments = [
            "--append-action", "msg:foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,msg:foo"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_action_with_existing_actions(self):
        arguments = [
            "--append-action", "msg:foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    log:'abc'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    log:'abc',\\
    msg:foo"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_action_with_duplicate_action(self):
        arguments = [
            "--append-action", "msg:foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:'foo',\\
    log:'abc'"
"""

        context = create_context(arguments, rule_string)
        assert rule_string == get_output(context)

    def test_append_action_in_correct_order(self):
        arguments = [
            "--append-action", "msg:foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    noauditlog,\\
    logdata:'data'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    noauditlog,\\
    msg:foo,\\
    logdata:'data'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_action_with_chain(self):
        arguments = [
            "--append-action", "msg:foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    noauditlog,\\
    logdata:'data',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    noauditlog,\\
    msg:foo,\\
    logdata:'data',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "msg:foo"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_action_skip_chain(self):
        arguments = [
            "--append-action", "msg:foo",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    noauditlog,\\
    logdata:'data',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    noauditlog,\\
    msg:foo,\\
    logdata:'data',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

class TestReplaceAction:
    def test_replace_action_with_no_actions(self):
        arguments = [
            "--replace-action", "msg:foo,msg:bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = rule_string

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_replace_action_with_existing_actions(self):
        arguments = [
            "--replace-action", "msg:foo,msg:bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:bar,\\
    log:'abc'"
"""
        expected = rule_string

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_replace_action_with_duplicate_action(self):
        arguments = [
            "--replace-action", "msg:foo,msg:bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:'foo',\\
    msg:'abc'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:bar,\\
    msg:'abc'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_replace_action_with_different_name(self):
        arguments = [
            "--replace-action", "msg:foo,deny",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:'foo',\\
    msg:'abc'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    msg:'abc'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

        arguments = [
            "--replace-action", "deny,msg:foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    msg:'abc'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:foo,\\
    msg:'abc'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_replace_action_without_values(self):
        arguments = [
            "--replace-action", "pass,deny",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    pass,\\
    msg:'abc'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    msg:'abc'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_replace_action_with_for_any_value(self):
        arguments = [
            "--replace-action", "msg,msg:bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    msg:something,\\
    msg:'or',\\
    msg:other"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    msg:bar,\\
    msg:bar,\\
    msg:bar"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_replace_action_with_quotes(self):
        arguments = [
            "--replace-action", "msg,msg:'bar'",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    msg:something,\\
    msg:'or',\\
    msg:other"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    msg:'bar',\\
    msg:'bar',\\
    msg:'bar'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_replace_action_with_chain(self):
        arguments = [
            "--replace-action", "msg:foo,msg:bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:'foo',\\
    msg:'abc',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "msg:'foo'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:bar,\\
    msg:'abc',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "msg:bar"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_replace_action_skip_chain(self):
        arguments = [
            "--replace-action", "msg:foo,msg:bar",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:'foo',\\
    msg:'abc',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "msg:'foo'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    msg:bar,\\
    msg:'abc',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "msg:'foo'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)
