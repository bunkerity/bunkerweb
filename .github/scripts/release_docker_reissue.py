"""Verify and promote the two corrected RC1 container indexes."""

from argparse import ArgumentParser
from hashlib import sha256
from json import loads
from os import environ
from pathlib import Path
from re import fullmatch
from subprocess import run
from tempfile import TemporaryDirectory
from time import sleep

import release_artifacts as release
import release_smoke

VERSION = "1.6.19~rc1"
PUBLIC_TAG = "v1.6.19-rc1"
DOCKER_TAG = "1.6.19-rc1"
AUTH_TAG = "docker-reissue/1.6.19-rc1-nginx-1.30.8"
WORKFLOW = ".github/workflows/docker-reissue-rc1.yml"
SIGNER = "4821439D531B030E5DCCF1F77C44E4D7742628F8"
OLD_SOURCE = "c80b2e71cec7df3af1db0b1abfab79dfa11a4acf"
OLD_TAG_OBJECT = "4a14d4d3266a4d58f4ae93546fbe22e1bfef34c1"
OLD_RELEASE_ID = 456697465
OLD_MANIFEST = "c6e8da69a7e3635fd5ed010488dc185af6461cd51bca79eaf7a1fd9053e4d74a"
OLD_BUNDLE = "dae207b180a0de2bb63a1eea08280051c8941c94cf559ddc7fea187654f68582"
OLD_DIGESTS = {
    "bunkerweb": "sha256:b5fbe570b1967147f507357e66b124fb0c769ad1e45d031598b646518c6ffe5f",
    "all-in-one": "sha256:09c768039e4d1a789ae53c4f4702172263a31fa526bfc8a2bacd27b9aa2aab0b",
}
CORRECTED_FILES = {
    "CHANGELOG.md": "df920c8ffaa6851582289d8746a8e65b70ce1eb1",
    "src/bw/Dockerfile": "cf21e03dcc44efc6d53a9f68dd2c89543a782deb",
    "src/all-in-one/Dockerfile": "c31c451ae7ac5690c2e5b23760885b74fb3015e9",
    "src/deps/install.sh": "4f0a68c98f3844402a44fbeb734cbe9c3d74be72",
}
MANIFEST_FILE = "docker-reissue-manifest.json"
ORIGINAL = {"source_sha": OLD_SOURCE, "tag_object": OLD_TAG_OBJECT, "release_id": OLD_RELEASE_ID, "manifest_sha256": OLD_MANIFEST}


def api(endpoint):
    return loads(release.command(["gh", "api", "--method", "GET", f"repos/{release.REPOSITORY}/{endpoint}"]))


def check_signed_tag(tag, source_sha):
    ref = api(f"git/ref/tags/{tag}")
    release.require(ref["ref"] == f"refs/tags/{tag}" and ref["object"]["type"] == "tag", f"expected annotated tag {tag}")
    object_sha = ref["object"]["sha"]
    signed = api(f"git/tags/{object_sha}")
    release.require(
        signed["sha"] == object_sha and signed["tag"] == tag and signed["object"]["type"] == "commit" and signed["object"]["sha"] == source_sha,
        f"tag {tag} does not sign the required source",
    )
    release.require(signed["verification"]["verified"] is True, f"GitHub cannot verify {tag}")
    return object_sha, signed["verification"]


def verify_fingerprint(verification):
    with TemporaryDirectory(prefix="docker-reissue-gpg-") as temporary:
        directory = Path(temporary)
        gpg = ["gpg", "--batch", "--no-options", "--homedir", temporary]
        key = release.command(["curl", "-fsSL", "--retry", "3", "--max-time", "30", "https://github.com/TheophileDiot.gpg"])
        (directory / "key").write_bytes(key)
        release.command([*gpg, "--import", str(directory / "key")])
        (directory / "payload").write_bytes(verification["payload"].encode())
        (directory / "signature").write_bytes(verification["signature"].encode())
        status = release.command([*gpg, "--status-fd", "1", "--verify", str(directory / "signature"), str(directory / "payload")]).decode()
        signatures = [line.split()[2] for line in status.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
        release.require(signatures == [SIGNER], "authorization tag does not have the pinned release-owner fingerprint")


def check_authorization():
    source = release.identity()
    auth_ref = f"refs/tags/{AUTH_TAG}"
    release.require(
        environ["GITHUB_REPOSITORY"] == release.REPOSITORY and environ["GITHUB_EVENT_NAME"] == "push" and environ["GITHUB_REF"] == auth_ref,
        "unexpected authorization event",
    )
    release.require(environ["GITHUB_WORKFLOW_REF"] == f"{release.REPOSITORY}/{WORKFLOW}@{auth_ref}", "unexpected workflow identity")
    release.require(source["version"] == VERSION and source["source_sha"] != OLD_SOURCE, "incorrect corrected RC1 source")
    _, verification = check_signed_tag(AUTH_TAG, source["source_sha"])
    verify_fingerprint(verification)
    public_tag, _ = check_signed_tag(PUBLIC_TAG, OLD_SOURCE)
    release.require(public_tag == OLD_TAG_OBJECT, "the original annotated tag object changed")
    original = api(f"releases/{OLD_RELEASE_ID}")
    release.require(original["tag_name"] == PUBLIC_TAG and original["draft"] is False and original["prerelease"] is True, "original RC1 release changed")
    assets = {asset["name"]: asset.get("digest") for asset in original["assets"]}
    release.require(assets.get("release-manifest.json") == f"sha256:{OLD_MANIFEST}", "original RC1 manifest changed")
    release.require(assets.get(f"bunkerweb-{DOCKER_TAG}.intoto.jsonl") == f"sha256:{OLD_BUNDLE}", "original RC1 provenance bundle changed")
    compared = api(f"compare/{OLD_SOURCE}...{source['source_sha']}")
    expected_paths = set(CORRECTED_FILES) | {WORKFLOW, ".github/scripts/release_docker_reissue.py"}
    release.require(compared["merge_base_commit"]["sha"] == OLD_SOURCE, "corrected commit must descend from the public RC1 commit")
    release.require({file["filename"] for file in compared["files"]} == expected_paths, "unexpected files in the corrected RC1 tree")
    for path, blob in CORRECTED_FILES.items():
        actual = release.command(["git", "hash-object", "--", path]).decode().strip()
        release.require(actual == blob, f"{path} differs from the reviewed correction")


def check_environment():
    environment = api("environments/release")
    owners = {"TheophileDiot", "fl0ppy-d1sk"}
    release.require(
        environment["name"] == "release"
        and any(
            rule["type"] == "required_reviewers"
            and rule["reviewers"]
            and all(reviewer["type"] == "User" and reviewer["reviewer"]["login"] in owners for reviewer in rule["reviewers"])
            for rule in environment["protection_rules"]
        ),
        "release environment lacks the required owner review",
    )


def candidate_digest(image, ref):
    prefix = f"ghcr.io/bunkerity/{image}-tests@"
    release.require(ref.startswith(prefix), f"unexpected candidate repository for {image}")
    return release.digest(ref.removeprefix(prefix))


def image_receipts(receipts, identity):
    grouped = {image: {} for image in OLD_DIGESTS}
    release.require(len(receipts) == len(grouped) * len(release.PLATFORMS), "expected eight scanned image receipts")
    for receipt in receipts:
        release.require(all(receipt[key] == value for key, value in identity.items()), "foreign receipt source, run, or attempt")
        image = receipt["image"]
        release.require(receipt["kind"] == "image" and image in grouped, "unexpected receipt image")
        candidate_digest(image, receipt["ref"])
        release.require(len(receipt["platforms"]) == 1, "receipt must cover one platform")
        platform, digest = next(iter(receipt["platforms"].items()))
        release.require(platform in release.PLATFORMS and platform not in grouped[image], f"unexpected or duplicate receipt for {image} on {platform}")
        grouped[image][platform] = (receipt["ref"], release.digest(digest))
    return grouped


def registry_digest(tag):
    result = release.registry(["docker", "buildx", "imagetools", "inspect", "--format", "{{json .Manifest.Digest}}", tag])
    return release.digest(loads(result))


def assemble(directory):
    identity = release.identity()
    receipts = [loads(file.read_text()) for file in Path(directory).glob("*.json")]
    grouped = image_receipts(receipts, identity)
    manifest = identity | {"schema": 1, "authorization_ref": f"refs/tags/{AUTH_TAG}", "original": ORIGINAL, "images": {}}
    for image, platforms in grouped.items():
        repository = f"ghcr.io/bunkerity/{image}-tests"
        tag = f"{repository}:docker-reissue-{identity['run_id']}-{identity['run_attempt']}"
        refs = [platforms[platform][0] for platform in release.PLATFORMS]
        release.registry(["docker", "buildx", "imagetools", "create", "--tag", tag, *refs])
        ref = f"{repository}@{registry_digest(tag)}"
        index = release.inspect_index(ref)
        expected = {platform: platforms[platform][1] for platform in release.PLATFORMS}
        release.require(release.platform_digests(index) == expected, f"assembled {image} differs from the scanned platform digests")
        attestations = {
            item.get("annotations", {}).get("vnd.docker.reference.digest")
            for item in index["manifests"]
            if item.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest"
        }
        release.require(attestations == set(expected.values()), f"incomplete BuildKit attestations for {image}")
        manifest["images"][image] = {"ref": ref, "platforms": expected, "previous": OLD_DIGESTS[image]}
    release.write_json(MANIFEST_FILE, manifest)
    print(f"sha256={sha256(Path(MANIFEST_FILE).read_bytes()).hexdigest()}")


def load_manifest():
    data = Path(MANIFEST_FILE).read_bytes()
    release.require(sha256(data).hexdigest() == environ["MANIFEST_SHA256"], "unexpected manifest checksum")
    manifest = loads(data)
    identity = release.identity()
    attempt = manifest["run_attempt"]
    release.require(fullmatch(r"[1-9][0-9]*", attempt) and int(attempt) <= int(identity["run_attempt"]), "unexpected build attempt")
    release.require(all(manifest[key] == value for key, value in (identity | {"run_attempt": attempt}).items()), "manifest source or run differs")
    release.require(
        set(manifest) == set(identity) | {"schema", "authorization_ref", "original", "images"}
        and manifest["schema"] == 1
        and manifest["authorization_ref"] == f"refs/tags/{AUTH_TAG}"
        and manifest["original"] == ORIGINAL
        and set(manifest["images"]) == set(OLD_DIGESTS),
        "unexpected Docker rebuild manifest",
    )
    for image, entry in manifest["images"].items():
        release.require(
            entry["previous"] == OLD_DIGESTS[image]
            and candidate_digest(image, entry["ref"]) != OLD_DIGESTS[image]
            and set(entry["platforms"]) == set(release.PLATFORMS),
            f"unexpected candidate inventory for {image}",
        )
        for digest in entry["platforms"].values():
            release.digest(digest)
    return manifest


def smoke(manifest):
    config = release_smoke.compose_config()
    services = config["services"]
    config["services"] = {name: services[name] for name in ("bunkerweb", "all-in-one", "scheduler")}
    for image, entry in manifest["images"].items():
        services[image].update(image=entry["ref"], platform="linux/amd64")
    scheduler_digest = "sha256:c3ed2471ee0e77d106fece4737b52ac860c2655213ffdd93a92ff909331997af"
    services["scheduler"].update(image=f"ghcr.io/bunkerity/bunkerweb-scheduler@{scheduler_digest}", platform="linux/amd64")
    services["scheduler"]["environment"].update(AUTOCONF_MODE="no", BUNKERWEB_INSTANCES="bunkerweb", SERVER_NAME="smoke.example.com")
    with TemporaryDirectory(prefix="docker-reissue-smoke-") as temporary:
        file = Path(temporary) / "compose.json"
        release.write_json(file, config)
        compose = ["docker", "compose", "--project-name", "docker-reissue-smoke", "--file", str(file)]
        try:
            release.command([*compose, "pull"])
            release_smoke.start_services(compose)
            for image in OLD_DIGESTS:
                result = release.command([*compose, "exec", "-T", image, "sh", "-c", "nginx -v 2>&1"]).decode().strip()
                release.require(result == "nginx version: nginx/1.30.8", f"wrong NGINX in {image}: {result}")
                release.command([*compose, "exec", "-T", image, "nginx", "-t"])
            for image in OLD_DIGESTS:
                health = [*compose, "exec", "-T", image, "/usr/share/bunkerweb/helpers/healthcheck.sh", "ok"]
                for _ in range(30):
                    if run(health, check=False).returncode == 0:
                        break
                    sleep(2)
                else:
                    raise ValueError(f"{image} never reached configured health")
        finally:
            run([*compose, "logs", "--no-color"], check=False)
            release.command([*compose, "down", "--volumes", "--remove-orphans"])


def destinations(manifest):
    for image, entry in manifest["images"].items():
        digest = candidate_digest(image, entry["ref"])
        for prefix in release.REGISTRIES.values():
            name = f"{prefix}/{release.PUBLISHED[image]}"
            yield image, name, digest


def image_attestations(manifest, references):
    policy = [
        "--repo",
        release.REPOSITORY,
        "--signer-workflow",
        f"{release.REPOSITORY}/{WORKFLOW}",
        "--source-ref",
        manifest["authorization_ref"],
        "--source-digest",
        manifest["source_sha"],
        "--predicate-type",
        release.PROVENANCE_PREDICATE,
    ]
    pending = references
    for attempt in range(release.REGISTRY_ATTEMPTS):
        pending = [ref for ref in pending if not release.attested(ref, policy)]
        if not pending:
            return
        if attempt + 1 < release.REGISTRY_ATTEMPTS:
            sleep(release.REGISTRY_DELAY)
    raise ValueError("missing or foreign reissue attestation: " + ", ".join(pending))


def promote(manifest):
    targets = [(image, f"{name}:{DOCKER_TAG}", digest) for image, name, digest in destinations(manifest)]
    for image, tag, digest in targets:
        found = registry_digest(tag)
        release.require(found in (OLD_DIGESTS[image], digest), f"unexpected digest {found} at {tag}")
    # Another registry may fail after a successful write. Reuse this same manifest on retry.
    for image, tag, digest in targets:
        found = registry_digest(tag)
        release.require(found in (OLD_DIGESTS[image], digest), f"unexpected digest {found} at {tag}")
        if found != digest:
            release.promote(manifest, image, tag)


def verify_publication(manifest):
    targets = list(destinations(manifest))
    for _, name, digest in targets:
        tag = f"{name}:{DOCKER_TAG}"
        release.require(registry_digest(tag) == digest, f"published tag differs from the approved manifest: {tag}")
    image_attestations(manifest, [f"oci://{name}@{digest}" for _, name, digest in targets])


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("authorize", "assemble", "smoke", "approve", "subjects", "promote", "verify"))
    parser.add_argument("--directory", default="receipts")
    args = parser.parse_args()
    if args.operation == "authorize":
        check_authorization()
        check_environment()
        return
    if args.operation == "assemble":
        assemble(args.directory)
        return
    manifest = load_manifest()
    if args.operation == "smoke":
        smoke(manifest)
    elif args.operation == "approve":
        check_authorization()
        check_environment()
        print(f"sha256={environ['MANIFEST_SHA256']}")
    elif args.operation == "subjects":
        for image, entry in manifest["images"].items():
            print(f"{image}={candidate_digest(image, entry['ref'])}")
    elif args.operation == "promote":
        check_authorization()
        check_environment()
        image_attestations(manifest, [MANIFEST_FILE, *[f"oci://{entry['ref']}" for entry in manifest["images"].values()]])
        promote(manifest)
    else:
        check_authorization()
        verify_publication(manifest)


if __name__ == "__main__":
    main()
