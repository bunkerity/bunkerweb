"""Create a release draft once; only resume its failed publisher with identical inputs."""

from hashlib import sha256
from itertools import chain
from json import dumps, loads
from os import environ
from pathlib import Path
from subprocess import run
from time import sleep
from urllib.parse import urlencode

from release_artifacts import command, load_manifest, require

MARKER = "<!-- bunkerweb-release-claim: "
PUBLISH_JOB_NAME = "Publish GitHub release"
CLAIM_LOOKUPS = 6
CLAIM_DELAY = 5


def api(endpoint, payload=None, paginated=False):
    args = ["gh", "api", endpoint]
    if paginated:
        args.extend(("--paginate", "--slurp"))
    if payload is not None:
        args.extend(("--method", "POST", "--input", "-"))
        return loads(run(args, input=dumps(payload).encode(), capture_output=True, check=True).stdout)
    return loads(command(args))


def matching_releases(repo, tag):
    pages = api(f"repos/{repo}/releases?per_page=100", paginated=True)
    require(isinstance(pages, list) and all(isinstance(page, list) for page in pages), "invalid releases response")
    return [release for page in pages for release in page if release["tag_name"] == tag]


def require_unique_claim(repo, tag, release_id):
    """The releases list trails a create by a few seconds, and a draft missing from it is not a rival claim."""
    for lookup in range(CLAIM_LOOKUPS):
        ids = [row["id"] for row in matching_releases(repo, tag)]
        if ids == [release_id]:
            return
        # Anything else already claiming the tag is a real conflict: our own create never reads back as another id.
        require(not ids, "release claim is not unique; refusing publication")
        if lookup + 1 < CLAIM_LOOKUPS:
            sleep(CLAIM_DELAY)
    require(False, "created draft never appeared in the releases list")


def body_with_claim(body, binding):
    return f"{body.rstrip()}\n\n{MARKER}{dumps(binding, sort_keys=True)} -->"


def verify_asset(repo, asset, checksum):
    actual = asset.get("digest")
    if actual is None:
        data = command(["gh", "api", f"repos/{repo}/releases/assets/{asset['id']}", "--header", "Accept: application/octet-stream"])
        actual = "sha256:" + sha256(data).hexdigest()
    require(actual == "sha256:" + checksum, f"existing release asset differs: {asset['name']}")


def publish(manifest, manifest_hash, body, files, prerelease):
    repo = environ["GITHUB_REPOSITORY"]
    tag = "v" + manifest["version"].replace("~", "-")
    files = {file.name: file for file in files}
    binding = {key: manifest[key] for key in ("source_sha", "run_id", "run_attempt")}
    binding.update(manifest_sha256=manifest_hash, assets={name: sha256(file.read_bytes()).hexdigest() for name, file in files.items()})
    current_attempt = int(environ["GITHUB_RUN_ATTEMPT"])
    existing = matching_releases(repo, tag)
    require(len(existing) <= 1, "multiple releases already claim this tag")
    if existing:
        release = existing[0]
        require(release.get("draft") is True, "refusing to update a published release")
        notes = release.get("body") or ""
        require(notes.count(MARKER) == 1 and notes.endswith(" -->"), "existing draft has no unique candidate claim")
        original = loads(notes.rsplit(MARKER, 1)[1][:-4])
        publisher_attempt = original.get("publisher_attempt")
        require(isinstance(publisher_attempt, int) and 0 < publisher_attempt < current_attempt, "only a failed earlier publisher attempt can be resumed")
        binding["publisher_attempt"] = publisher_attempt
        require(original == binding and notes == body_with_claim(body, binding), "existing draft belongs to different release inputs")
        require(release.get("prerelease") is prerelease and release.get("name") == tag, "existing draft metadata differs")
        pages = api(f"repos/{repo}/actions/runs/{manifest['run_id']}/attempts/{publisher_attempt}/jobs?per_page=100", paginated=True)
        jobs = [job for page in pages for job in page["jobs"] if job["name"].split(" / ")[-1] == PUBLISH_JOB_NAME]
        require(len(jobs) == 1 and jobs[0]["conclusion"] in ("failure", "cancelled"), "original publisher was not a failed job")
    else:
        # This marker is created atomically with the draft, before any asset or
        # image/package publication. No PATCH or create-conflict fallback exists.
        binding["publisher_attempt"] = current_attempt
    tag_ref = api(f"repos/{repo}/git/ref/tags/{tag}")
    require(tag_ref["object"]["type"] == "tag", "release tag is not annotated")
    signed = api(f"repos/{repo}/git/tags/{tag_ref['object']['sha']}")
    require(
        signed["verification"]["verified"] and signed["object"]["type"] == "commit" and signed["object"]["sha"] == manifest["source_sha"],
        "signed tag target differs",
    )
    if not existing:
        payload = {
            "tag_name": tag,
            "name": tag,
            "draft": True,
            "prerelease": prerelease,
            "discussion_category_name": "Announcements",
            "body": body_with_claim(body, binding),
        }
        release = api(f"repos/{repo}/releases", payload=payload)
        require(release.get("draft") is True and release.get("body") == payload["body"], "created draft does not match its candidate claim")
        require_unique_claim(repo, tag, release["id"])
    release_id = release["id"]
    pages = api(f"repos/{repo}/releases/{release_id}/assets?per_page=100", paginated=True)
    assets = list(chain.from_iterable(pages))
    require(len({asset["name"] for asset in assets}) == len(assets), "duplicate release assets")
    require({asset["name"] for asset in assets} <= files.keys(), "unexpected assets in release draft")
    uploaded = {asset["name"]: asset for asset in assets}
    for name, file in files.items():
        if name in uploaded:
            verify_asset(repo, uploaded[name], binding["assets"][name])
            continue
        endpoint = f"https://uploads.github.com/repos/{repo}/releases/{release_id}/assets?{urlencode({'name': name})}"
        asset = loads(command(["gh", "api", "--method", "POST", endpoint, "--input", str(file), "--header", "Content-Type: application/octet-stream"]))
        verify_asset(repo, asset, binding["assets"][name])


if __name__ == "__main__":
    manifest_hash = environ["MANIFEST_SHA256"]
    manifest = load_manifest("release-manifest.json", manifest_hash)
    files = [
        Path(f"BunkerWeb_documentation_v{manifest['version']}.pdf"),
        Path("misc/install-bunkerweb.sh"),
        Path("misc/install-bunkerweb.sh.sha256"),
        Path("release-manifest.json"),
        Path("release-manifest.json.sha256"),
    ]
    require(environ["PRERELEASE"] in ("true", "false"), "invalid prerelease flag")
    publish(manifest, manifest_hash, environ["RELEASE_BODY"], files, environ["PRERELEASE"] == "true")
