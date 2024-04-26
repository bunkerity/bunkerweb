from .helpers import *

class TestFilterRuleId:
    def test_filter_rule_id_exact_match(self):
        arguments = [
            "--filter-rule-id", "12",
            "--append-tag", "foo"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_filter_rule_id_prefix_match(self):
        arguments = [
            "--filter-rule-id", "^12",
            "--append-tag", "foo"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:122"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:122,tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_filter_rule_id_suffix_match(self):
        arguments = [
            "--filter-rule-id", ".*22$",
            "--append-tag", "foo"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:122"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:122,tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_filter_rule_id_no_match(self):
        arguments = [
            "--filter-rule-id", "11",
            "--append-tag", "foo"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = rule_string

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

class TestLineNumbers:
    def test_line_numbers_identical(self):
        arguments = [
            "--append-tag", "foo"
        ]
        rule_string = """

SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"

SecRule ARGS "@rx bar" "id:13"
"""
        expected = """

SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,tag:'foo'"

SecRule ARGS "@rx bar" "id:13,tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_line_numbers_shifted_down(self):
        arguments = [
            "--append-tag", "foo"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12"

SecRule ARGS "@rx bar" \\
    "id:13"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    tag:'foo'"

SecRule ARGS "@rx bar" \\
    "id:13,\\
    tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_line_numbers_shifted_up(self):
        arguments = [
            "--remove-tag", "foo"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    tag:foo"

SecRule ARGS "@rx bar" \\
    "id:13,\\
    tag:foo"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12"

SecRule ARGS "@rx bar" \\
    "id:13"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

class TestTargetFile:
    def test_target_file(self, tmp_path):
        import os
        from rule_ctl import write_output

        file_path = str(tmp_path / 'foo.conf')
        arguments = [
            "--append-tag", "foo",
            "--target-file", file_path
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12"
"""

        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        write_output(context)

        assert os.path.exists(file_path)
        with open(file_path, 'r') as h:
            assert expected.rstrip() == h.read()

    def test_target_file_uses_config_as_default(self, tmp_path):
        import os
        from rule_ctl import write_output

        file_path = str(tmp_path / 'foo.conf')
        arguments = [
            "--append-tag", "foo",
            "--config", file_path
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12"
"""

        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        write_output(context)

        assert os.path.exists(file_path)
        with open(file_path, 'r') as h:
            assert expected.rstrip() == h.read()
