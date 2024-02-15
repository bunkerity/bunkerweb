from .helpers import *

class TestAppendTag:
    def test_append_tag_with_no_tags(self):
        arguments = [
            "--append-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,tag:'foo'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_tag_with_existing_tags(self):
        arguments = [
            "--append-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    tag:'abc'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    tag:'abc',\\
    tag:'foo'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_tag_with_duplicate_tag(self):
        arguments = [
            "--append-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    tag:'foo',\\
    tag:'abc'"
"""

        context = create_context(arguments, rule_string)
        assert rule_string == get_output(context)

    def test_append_tag_in_correct_order(self):
        arguments = [
            "--append-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    log:'log',\\
    logdata:'data',\\
    sanitiseArg:arg"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    log:'log',\\
    logdata:'data',\\
    tag:'foo',\\
    sanitiseArg:arg"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_tag_with_chain(self):
        arguments = [
            "--append-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    log:'log',\\
    logdata:'data',\\
    sanitiseArg:arg,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "deny"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    log:'log',\\
    logdata:'data',\\
    tag:'foo',\\
    sanitiseArg:arg,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "deny,\\
        tag:'foo'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_tag_skip_chain(self):
        arguments = [
            "--append-tag", "foo",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    log:'log',\\
    logdata:'data',\\
    sanitiseArg:arg,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "deny"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    log:'log',\\
    logdata:'data',\\
    tag:'foo',\\
    sanitiseArg:arg,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx bar" \\
        "deny"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

class TestRemoveTag:
    def test_remove_tag_with_no_tags(self):
        arguments = [
            "--remove-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = rule_string
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_remove_tag_with_existing_tags(self):
        arguments = [
            "--remove-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,tag:foo"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_remove_tag_with_chain(self):
        arguments = [
            "--remove-tag", "foo",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,tag:foo,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "tag:foo"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_remove_tag_skip_chain(self):
        arguments = [
            "--remove-tag", "foo",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,tag:foo,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "tag:foo"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,chain"
    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "tag:foo"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

class TestRenameTag:
    def test_rename_tag_with_no_tags(self):
        arguments = [
            "--rename-tag", "foo,bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = rule_string
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_rename_tag_with_existing_tags(self):
        arguments = [
            "--rename-tag", "foo,bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'foo',\\
    tag:'alpha'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'bar',\\
    tag:'alpha'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_rename_tag_with_chain(self):
        arguments = [
            "--rename-tag", "foo,bar",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'foo',\\
    tag:'alpha',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'foo'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'bar',\\
    tag:'alpha',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'bar'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_rename_tag_skip_chain(self):
        arguments = [
            "--rename-tag", "foo,bar",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'foo',\\
    tag:'alpha',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'foo'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'bar',\\
    tag:'alpha',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'foo'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

class TestSortTags:
    def test_sort_tags(self):
        arguments = [
            "--sort-tags"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'foo',\\
    tag:'alpha'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'alpha',\\
    tag:'foo',\\
    tag:'omega'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_sort_tags_with_chain(self):
        arguments = [
            "--sort-tags"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'foo',\\
    tag:'alpha',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'omega',\\
        tag:'foo',\\
        tag:'alpha'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'alpha',\\
    tag:'foo',\\
    tag:'omega',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'alpha',\\
        tag:'foo',\\
        tag:'omega'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_sort_tags_skip_chain(self):
        arguments = [
            "--sort-tags",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'omega',\\
    tag:'foo',\\
    tag:'alpha',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'omega',\\
        tag:'foo',\\
        tag:'alpha'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
    "id:12,\\
    tag:'alpha',\\
    tag:'foo',\\
    tag:'omega',\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" \\
        "tag:'omega',\\
        tag:'foo',\\
        tag:'alpha'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)
