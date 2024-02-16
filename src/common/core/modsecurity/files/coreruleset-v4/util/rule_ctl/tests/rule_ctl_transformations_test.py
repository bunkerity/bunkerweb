from .helpers import *

class TestAppendTfunc:
    def test_append_tfunc_with_no_transformations(self):
        arguments = [
            "--append-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12,t:lower"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_tfunc_with_existing_transformations(self):
        arguments = [
            "--append-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    t:lower"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_append_tfunc_with_duplicate_transformation(self):
        arguments = [
            "--append-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:lower,\\
    t:urlDecode"
"""
        expected = rule_string

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_tfunc_in_correct_order(self):
        arguments = [
            "--append-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    capture,\\
    log:'log',\\
    logdata:'data'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    deny,\\
    capture,\\
    t:lower,\\
    log:'log',\\
    logdata:'data'"
"""

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_tfunc_with_chain(self):
        arguments = [
            "--append-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    t:lower,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl,\\
        t:lower"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_append_tfunc_skip_chain(self):
        arguments = [
            "--append-tfunc", "lower",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    t:lower,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

class TestRemoveTfunc:
    def test_remove_tfunc_with_no_transformations(self):
        arguments = [
            "--remove-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar "@rx foo" "id:12"
"""
        expected = rule_string

        context = create_context(arguments, rule_string)
        assert expected == get_output(context)


    def test_remove_tfunc_with_existing_transformations(self):
        arguments = [
            "--remove-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    t:lower"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_remove_tfunc_with_multiple_args(self):
        arguments = [
            "--remove-tfunc", "lower",
            "--remove-tfunc", "decodeUrl"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    t:lower"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_remove_tfunc_with_chain(self):
        arguments = [
            "--remove-tfunc", "lower",
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    t:lower,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl,\\
        t:lower"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_remove_tfunc_skip_chain(self):
        arguments = [
            "--remove-tfunc", "lower",
            "--skip-chain"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    t:lower,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl,\\
        t:lower"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:decodeUrl,\\
    chain"

    SecRule ARGS|ARGS:foo|!ARGS:bar \\
        "@rx foo" \\
        "t:decodeUrl,\\
        t:lower"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)

    def test_remove_tfunc_retains_correct_line_numbers(self):
        arguments = [
            "--remove-tfunc", "lowercase"
        ]
        rule_string = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:none,t:lowercase,\\
    msg:'PHP Injection Attack: PHP Script File Upload Found'"
"""
        expected = """
SecRule ARGS|ARGS:foo|!ARGS:bar \\
    "@rx foo" \\
    "id:12,\\
    t:none,\\
    msg:'PHP Injection Attack: PHP Script File Upload Found'"
"""
        context = create_context(arguments, rule_string)
        assert expected == get_output(context)
