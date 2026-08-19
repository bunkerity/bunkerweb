"""Requirements files that get installed into one target must agree on every shared pin.

The images do not install one requirements file each. `src/ui/Dockerfile` copies four of them
into `/tmp/req/` and hands the lot to a single `pip install --require-hashes --target deps/python`:

    pip install ... $(for file in $(ls /tmp/req/requirements*.txt); do echo "-r ${file}"; done)

So a package pinned by two of those files at two versions is not a warning, it is
`ResolutionImpossible` and the image does not build. Adding Flask-Babel to the UI did exactly
that: Babel pulls `pytz`, `pip-compile` resolved `2026.3.post1`, and `src/common/gen` had been
pinning `2026.3` — a build failure produced by a change that touched neither file's own pins.

Nothing in the per-file compile step can see this, because each file is compiled alone.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s\\;]+)", re.MULTILINE)

# Every `COPY <path> /tmp/req/...` in an image whose build installs that directory in one go.
IMAGES = {
    "src/ui/Dockerfile": ("src/ui", "src/common/gen", "src/common/db"),
    "src/api/Dockerfile": ("src/api", "src/common/gen", "src/common/db"),
    "src/scheduler/Dockerfile": ("src/scheduler", "src/common/gen", "src/common/db"),
}


def _pins(directory):
    path = REPO / directory / "requirements.txt"
    if not path.is_file():
        pytest.skip(f"{directory} has no requirements.txt")
    return {name.lower(): version for name, version in PIN.findall(path.read_text(encoding="utf-8"))}


@pytest.mark.parametrize("dockerfile,directories", sorted(IMAGES.items()))
def test_co_installed_requirements_agree_on_every_shared_package(dockerfile, directories):
    if not (REPO / dockerfile).is_file():
        pytest.skip(f"{dockerfile} not present")

    seen = {}
    conflicts = []
    for directory in directories:
        for name, version in _pins(directory).items():
            if name in seen and seen[name][1] != version:
                conflicts.append(f"{name}: {seen[name][0]} pins {seen[name][1]}, {directory} pins {version}")
            seen.setdefault(name, (directory, version))

    assert not conflicts, f"{dockerfile} installs these together:\n  " + "\n  ".join(conflicts)


def test_the_dockerfile_still_installs_them_as_one_set():
    """If this ever becomes one `pip install` per file, the test above is measuring nothing."""
    dockerfile = (REPO / "src" / "ui" / "Dockerfile").read_text(encoding="utf-8")

    assert 'for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs' in dockerfile


def test_the_ui_pins_the_shared_package_that_caused_this():
    """`pytz` reaches the UI only through Babel, so nothing in `requirements.in` would mention it
    and the next `pip-compile` would happily float it again."""
    source = (REPO / "src" / "ui" / "requirements.in").read_text(encoding="utf-8")

    assert "pytz==" in source
    assert _pins("src/ui")["pytz"] == _pins("src/common/gen")["pytz"]
