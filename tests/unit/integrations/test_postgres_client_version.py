"""Every 64-bit image must carry a PostgreSQL client at least as new as the newest server we ship.

``pg_dump`` refuses any server newer than itself, so an unpinned client is a silent backup outage:
Debian's ``postgresql-client`` meta-package follows whatever the base image's distro ships (17 on
Debian 13) while the shipped manifests pin ``postgres:18-alpine``, and ``bwcli plugin backup save``
then aborts with "server version mismatch" before writing a byte. Restores keep working -- ``psql``
has no version gate -- which is exactly what let the mismatch go unnoticed.

The fix cannot be unconditional. PGDG publishes ``amd64 arm64 loong64 ppc64el`` and nothing else --
``binary-i386`` and ``binary-armhf`` are 404 -- while ``.github/workflows/push-docker.yml`` builds
``linux/amd64,linux/386,linux/arm64,linux/arm/v7`` for exactly these five images. Installing
``postgresql-client-18`` unconditionally therefore fails the 32-bit legs of every release push with
``E: Unable to locate package postgresql-client-18`` (apt exit 100). Each install site is gated on
``dpkg --print-architecture``: 64-bit gets the PGDG client, 32-bit keeps the distribution's one and
its pre-existing 17-server ceiling.

These are drift guards, not behaviour tests. They fail if someone drops either arm of that gate,
reintroduces a bare meta-package on the install line, or swaps the checked-in signing key.
"""

import re
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

# The one place the expected major lives. Bumping PostgreSQL means editing this and the six sites.
EXPECTED_MAJOR = 18
CLIENT_PACKAGE = f"postgresql-client-{EXPECTED_MAJOR}"

# The two arms of the architecture gate, verbatim. Both must be present at every install site: the
# first is the fix, the second is what keeps linux/386 and linux/arm/v7 buildable.
PGDG_ARM = f'amd64|arm64) echo "deb [signed-by=/etc/apt/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt ${{VERSION_CODENAME}}-pgdg main" > /etc/apt/sources.list.d/pgdg.list; PGCLIENT={CLIENT_PACKAGE} ;;'
FALLBACK_ARM = "*) PGCLIENT=postgresql-client ;;"
INSTALL_REF = '"$PGCLIENT"'

# Every Debian-based image that installs a PostgreSQL client. src/scheduler/Dockerfile carries two
# (the `bwcli` stage and the Scheduler runtime), so it is asserted per-occurrence, not per-file.
DOCKERFILES = {
    "src/scheduler/Dockerfile": 2,
    "src/worker/Dockerfile": 1,
    "src/ui/Dockerfile": 1,
    "src/api/Dockerfile": 1,
    "src/all-in-one/Dockerfile": 1,
}

# Recorded exemptions, so a file that installs a PostgreSQL client and is NOT in DOCKERFILES is a
# deliberate decision rather than an oversight nobody wrote down.
EXEMPT_DOCKERFILES = {
    # Alpine base, and alembic-only: `grep -rn "pg_dump\|psql" misc/migration/` is empty, so its
    # client is never on a dump path. Alpine has no PGDG equivalent to gate on either.
    "misc/migration/Dockerfile": "alpine, alembic-only, never on a dump path",
}

# The .deb recipes. RPM targets are deliberately absent: Fedora already ships an 18 client under the
# plain `postgresql` name, and the RHEL recipes declare no PostgreSQL dependency at all.
DEB_FPM_RECIPES = [
    "src/linux/fpm-ubuntu-jammy",
    "src/linux/fpm-ubuntu-noble",
    "src/linux/fpm-ubuntu",
    "src/linux/fpm-debian-bookworm",
    "src/linux/fpm-debian-trixie",
]

KEYRING = ROOT / "src" / "deps" / "pgdg-archive-keyring.asc"
# sha256 of the checked-in armored bytes, i.e. https://www.postgresql.org/media/keys/ACCC4CF8.asc.
# Dearmored, the same key is 8ca1b2fb3a2533cc44b87ee146a03858f6e8ea31c1f165dfd38dc270c04ada0f and
# carries fingerprint B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8 ("PostgreSQL Debian Repository").
# A PGDG key rotation must surface here as a red test, not as a silently different trust anchor.
KEYRING_SHA256 = "0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76"


@pytest.mark.parametrize("relpath,occurrences", sorted(DOCKERFILES.items()))
def test_every_install_site_carries_both_arms_of_the_architecture_gate(relpath, occurrences):
    text = (ROOT / relpath).read_text(encoding="utf-8")
    assert text.count(PGDG_ARM) == occurrences, f"{relpath} must gate the PGDG client on amd64|arm64 {occurrences}x"
    assert text.count(FALLBACK_ARM) == occurrences, f"{relpath} lost the 32-bit fallback arm; linux/386 and linux/arm/v7 stop building"
    assert text.count(INSTALL_REF) == occurrences, f"{relpath} must install {INSTALL_REF}, not a hardcoded package name"


@pytest.mark.parametrize("relpath,occurrences", sorted(DOCKERFILES.items()))
def test_no_postgresql_client_is_installed_outside_the_gate(relpath, occurrences):
    """The gate is only worth anything if nothing bypasses it.

    Both arms name a package, so a plain regex would match them; strip the two arms verbatim first
    and require that no ``postgresql-client`` mention survives anywhere else -- that is exactly the
    revert-to-the-meta-package regression, and also catches a second install line added later.
    """
    text = (ROOT / relpath).read_text(encoding="utf-8")
    residue = text.replace(PGDG_ARM, "").replace(FALLBACK_ARM, "")
    leftovers = re.findall(r"postgresql-client[-\w]*", residue)
    assert not leftovers, f"{relpath} installs a PostgreSQL client outside the architecture gate: {leftovers}"


@pytest.mark.parametrize("relpath,occurrences", sorted(DOCKERFILES.items()))
def test_image_wires_the_checked_in_pgdg_key(relpath, occurrences):
    text = (ROOT / relpath).read_text(encoding="utf-8")
    assert text.count("COPY --chmod=644 src/deps/pgdg-archive-keyring.asc /etc/apt/keyrings/pgdg.asc") == occurrences
    # signed-by scopes the key to this one repository; ${VERSION_CODENAME} follows a base-image bump
    # instead of silently pointing at a stale suite. Both live inside PGDG_ARM, asserted above.
    assert text.count("[signed-by=/etc/apt/keyrings/pgdg.asc]") == occurrences
    assert text.count("${VERSION_CODENAME}-pgdg main") == occurrences
    # No key is fetched over the network, and no gnupg is added to a runtime image to dearmor one.
    assert "apt-key" not in text
    assert "postgresql.org/media/keys" not in text


def test_the_pgdg_key_is_checked_in_and_is_the_postgresql_repository_key():
    assert KEYRING.is_file(), "src/deps/pgdg-archive-keyring.asc is missing; the image builds cannot add the repository"
    digest = sha256(KEYRING.read_bytes()).hexdigest()
    assert digest == KEYRING_SHA256, f"the PGDG signing key changed ({digest}); re-verify the fingerprint before updating this hash"


def test_every_dockerfile_installing_a_postgresql_client_is_accounted_for():
    """A sixth image that quietly installs a client must not slip past the guard above."""
    known = set(DOCKERFILES) | set(EXEMPT_DOCKERFILES)
    found = set()
    for path in ROOT.glob("**/Dockerfile*"):
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        if "postgresql-client" in path.read_text(encoding="utf-8", errors="ignore"):
            found.add(path.relative_to(ROOT).as_posix())
    assert found <= known, f"Dockerfile(s) install a PostgreSQL client but are neither guarded nor exempt: {sorted(found - known)}"
    # Non-vacuity: a glob that silently stopped matching would make the assertion above trivially
    # true, so require that every guarded file was actually discovered by the sweep.
    assert set(DOCKERFILES) <= found, f"the sweep no longer finds the guarded Dockerfiles: {sorted(set(DOCKERFILES) - found)}"


@pytest.mark.parametrize("relpath", DEB_FPM_RECIPES)
def test_deb_package_prefers_the_pinned_client_but_still_installs_without_pgdg(relpath):
    text = (ROOT / relpath).read_text(encoding="utf-8")
    # The alternative form is the whole point: apt takes postgresql-client-18 when the PGDG
    # repository is configured and falls back to the distribution's client when it is not, so the
    # package stays installable on a host that never touches PostgreSQL (SQLite is the default).
    assert f"--depends '{CLIENT_PACKAGE} | postgresql-client'" in text, f"{relpath} lost the alternative dependency"
