from rule_ctl import Context

def create_context(arguments, rules_string):
    context = Context()
    patched_arguments = arguments
    if "--config" not in arguments:
        patched_arguments = arguments + ["--config", "dummy"]
    context.parse_arguments(args=patched_arguments)

    for rule in context.parse_rules(rules_string):
        rule.modify(context)
    return context


def get_output(context):
    return "\n".join(context.generate_output()) + "\n"
