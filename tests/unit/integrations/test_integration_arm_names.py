"""An arm is spelled two ways on purpose, and every boundary has to convert.

Specs, the ``--integration`` CLI choices and the pydantic ``integrations`` literals use the human
spelling (``All-in-one``). ``tests/utils/integrations.yml`` keys, the first field of a matrix entry,
the ``/tmp/tests/<arm>_tests.json`` file names and the GitHub Actions outputs built from them use the
identifier spelling (``All_in_one``) — a hyphen cannot appear in a GitHub expression property
(``outputs.All-in-one_tests`` does not parse) nor in a Python attribute.

Three boundaries convert between them: ``tests/generate.py`` before its integrations.yml lookup,
``.github/workflows/integration-tests.yml`` when it publishes the matrix entry's arm, and
``tests/parse.py`` when it resolves the arm a spec named. The third one was missing. The effect was
not an error: ``check_integration(["All-in-one"], ...)`` simply missed the ``All_in_one`` key, and
the three specs that name the arm explicitly — ``upgrade``, ``badbehavior`` and ``limit`` — were
dropped from the emitted matrix behind one warning line. The All-in-one arm of those three has never
run in CI. A manual ``test.sh All-in-one core ...`` still worked, which is why it stayed invisible.

Each test below guards a way that can come back silently rather than loudly.
"""

from pathlib import Path
from re import DOTALL, MULTILINE, search

import pytest
from yaml import safe_load

ROOT = Path(__file__).resolve().parents[3]
PARSE = ROOT / "tests" / "parse.py"
GENERATE = ROOT / "tests" / "generate.py"
INTEGRATIONS = ROOT / "tests" / "utils" / "integrations.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "integration-tests.yml"
SPEC_DIRS = ("core", "ui", "api")

# The specs that name the All-in-one arm explicitly instead of reaching it through
# `integrations: "all"`. They are the ones the missing conversion dropped, so they are the
# regression pin: if this set stops resolving, the arm has gone silent again.
NAMES_THE_ARM_EXPLICITLY = {"badbehavior", "limit", "upgrade"}


def _integration_key():
    """`integration_key` out of parse.py, without importing it.

    parse.py pulls in `utils.logger`, which pulls in the docker SDK; the unit venv has neither.
    """
    source = PARSE.read_text()
    block = search(r"^def integration_key\(.*?\n\n", source, DOTALL | MULTILINE)
    assert block, "parse.py no longer defines integration_key"
    namespace: dict = {}
    exec(block.group(0), namespace)  # noqa: S102 - our own source, read from disk
    return namespace["integration_key"]


integration_key = _integration_key()


def _arms(spec: dict) -> list:
    """The arms a spec names, ignoring the `all` expansion — that one walks the yml keys itself."""
    declared = spec.get("integrations", [])
    if isinstance(declared, str):
        declared = [declared]
    # An entry may carry an architecture and a distribution: `Linux;amd64;ubuntu/noble`.
    return [entry.split(";")[0] for entry in declared if entry != "all"]


def _specs():
    for directory in SPEC_DIRS:
        for path in sorted((ROOT / "tests" / directory).glob("*.yml")):
            data = safe_load(path.read_text())
            if data:
                yield path, data


@pytest.mark.parametrize("environment", ("staging", "dev"))
def test_every_arm_a_spec_names_resolves_to_an_integrations_key(environment):
    """A spec that names an arm nothing can resolve is dropped with a warning, not an error.

    This is the data half: the spelling in a spec, put through the conversion, has to land on a
    real key. Adding an arm to integrations.yml under a name no spec can reach fails here rather
    than in a CI board that is missing rows nobody counted.
    """
    keys = set(safe_load(INTEGRATIONS.read_text())[environment])

    unresolved = {}
    for path, spec in _specs():
        for arm in _arms(spec):
            if integration_key(arm) not in keys:
                unresolved.setdefault(path.relative_to(ROOT).as_posix(), []).append(arm)

    assert not unresolved, f"arms named by a spec but absent from integrations.yml[{environment}]: {unresolved}"


def test_parse_converts_the_arm_name_before_it_looks_it_up():
    """The code half: parse.py must normalise `parts[0]` BEFORE `check_integration` sees it.

    Order is the whole defect. `check_integration` does a plain `data.get(entry[0])`, so a lookup
    that runs on the spec's spelling misses the key and the spec is skipped.
    """
    source = PARSE.read_text()

    conversion = source.find("parts[0] = integration_key(parts[0])")
    assert conversion != -1, "parse.py no longer converts the arm name a spec declared"

    lookup = source.find("if not check_integration(parts, integrations):")
    assert lookup != -1, "parse.py no longer guards the lookup with check_integration"

    assert conversion < lookup, "parse.py converts the arm name after the lookup that needs it"


def test_the_arm_name_reaches_the_matrix_entry_in_its_identifier_spelling():
    """The emitted entry has to start with the integrations.yml key, or no JSON file collects it.

    parse.py writes one `/tmp/tests/<key>_tests.json` per integrations.yml key and fills each by
    `test.startswith(f"{key};")`. An entry emitted as `All-in-one;...` matches no key and is
    written nowhere — the spec is lost after the lookup succeeded, which is worse than before.
    """
    source = PARSE.read_text()
    assert 'integration = ";".join(parts)' in source, "parse.py emits the arm name as the spec spelled it, not as the integrations.yml key"


@pytest.mark.parametrize("name", sorted(NAMES_THE_ARM_EXPLICITLY))
def test_the_specs_that_name_the_all_in_one_arm_still_resolve(name):
    """The regression pin: these three are the specs the missing conversion dropped."""
    spec = safe_load((ROOT / "tests" / "core" / f"{name}.yml").read_text())
    arms = _arms(spec)

    assert "All-in-one" in arms, f"core/{name}.yml no longer names the All-in-one arm; drop it from NAMES_THE_ARM_EXPLICITLY"

    for environment in ("staging", "dev"):
        keys = safe_load(INTEGRATIONS.read_text())[environment]
        assert integration_key("All-in-one") in keys, f"All-in-one does not resolve in integrations.yml[{environment}]"


def test_all_three_boundaries_agree_on_the_conversion():
    """One conversion, three places. If one drifts the arm goes quiet somewhere else instead.

    generate.py converts before its own integrations.yml lookup; integration-tests.yml converts
    back when it publishes the arm for the rest of the workflow to compare against `All-in-one`.
    Neither can be replaced by the other — they sit on opposite sides of the matrix entry.
    """
    assert integration_key("All-in-one") == "All_in_one"

    assert (
        'ARGS.integration.replace("-", "_") not in integrations' in GENERATE.read_text()
    ), "generate.py no longer converts the arm name before its integrations.yml lookup"

    assert (
        'echo "integration=${INTEGRATION//_/-}"' in WORKFLOW.read_text()
    ), "integration-tests.yml no longer converts the matrix arm back to the spelling every later step compares against"
