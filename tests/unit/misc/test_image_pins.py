"""Every base image in every Dockerfile is pinned by digest, and one image never has two digests.

Three properties, each of which has failed in this repository or was one edit away from it:

1. **Pinned at all.** An unpinned `FROM image:tag` resolves to whatever the registry serves at build
   time, so a reproducible-build claim and a supply-chain review both stop being true silently.
2. **Well formed.** `@sha256:` plus exactly 64 lowercase hex. A truncated or upper-cased digest fails
   at `docker build` time, which is a slow way to find a typo.
3. **Consistent.** The same `image:tag` carries the same digest everywhere. This is the one that
   catches a *half-applied* bump -- most of these Dockerfiles are multi-stage and name the same base
   twice, so bumping the builder and forgetting the runtime stage produces an image whose two halves
   came from different upstreams. Nothing else in the repository notices.

Deliberately NOT asserted: that a digest is the newest one upstream, or that it resolves at all.
That needs a registry pull; these tests are static and offline by design, and the freshness question
belongs to whoever runs the bump.
"""

import re
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

# `FROM <ref> [AS <stage>]`. The ref may be a registry image or an earlier stage in the same file.
FROM = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
DIGEST = re.compile(r"^[0-9a-f]{64}$")

SKIP_PARTS = {".git", "deps", ".cache", "node_modules", ".venv-unit"}


def _dockerfiles():
    return sorted(p for p in ROOT.rglob("Dockerfile*") if p.is_file() and not SKIP_PARTS & set(p.relative_to(ROOT).parts))


def _base_images(path: Path):
    """(line number, ref) for every FROM that names a registry image rather than a local stage."""
    stages, found = set(), []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = FROM.match(line.strip())
        if not match:
            continue
        ref, alias = match.group(1), match.group(2)
        if alias:
            stages.add(alias)
        # `FROM builder` refers to a stage declared above; it has no digest and must not have one.
        if ref not in stages:
            found.append((number, ref))
    return found


DOCKERFILES = _dockerfiles()


def test_the_repository_still_has_dockerfiles_to_check():
    """Guards the glob: a rename that empties it would make every test below vacuously green."""
    assert len(DOCKERFILES) >= 20, f"only found {len(DOCKERFILES)} Dockerfiles, the glob is probably wrong"


@pytest.mark.parametrize("path", DOCKERFILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_base_image_is_pinned_by_digest(path):
    for number, ref in _base_images(path):
        assert "@sha256:" in ref, f"{path.relative_to(ROOT)}:{number} pins no digest: FROM {ref}"


@pytest.mark.parametrize("path", DOCKERFILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_digest_is_well_formed(path):
    for number, ref in _base_images(path):
        if "@sha256:" not in ref:
            continue  # reported by the test above; do not fail twice for one defect
        digest = ref.split("@sha256:", 1)[1]
        assert DIGEST.match(digest), f"{path.relative_to(ROOT)}:{number} has a malformed digest: {digest!r}"


def test_one_image_never_carries_two_digests():
    """A multi-stage file bumped in one stage only is the failure this catches."""
    seen = defaultdict(lambda: defaultdict(list))
    for path in DOCKERFILES:
        for number, ref in _base_images(path):
            if "@sha256:" not in ref:
                continue
            image, digest = ref.split("@sha256:", 1)
            seen[image][digest].append(f"{path.relative_to(ROOT)}:{number}")

    split = {image: digests for image, digests in seen.items() if len(digests) > 1}
    detail = "\n".join(
        f"  {image}\n" + "\n".join(f"     {digest[:12]}  {sorted(locations)}" for digest, locations in digests.items()) for image, digests in split.items()
    )
    assert not split, f"the same image is pinned to different digests, so a bump landed only half-way:\n{detail}"
