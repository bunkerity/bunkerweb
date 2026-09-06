"""Bind release builds, integration tests and promotion to one immutable manifest."""

from argparse import ArgumentParser
from hashlib import sha256
from json import dumps, loads
from os import environ
from pathlib import Path
from re import fullmatch
from subprocess import run

IMAGES = ("bunkerweb", "scheduler", "autoconf", "ui", "api", "all-in-one")
PLATFORMS = ("linux/amd64", "linux/386", "linux/arm64", "linux/arm/v7")
PACKAGE_PLATFORMS = ("linux/amd64", "linux/arm64")
DISTROS = {
    "ubuntu": "deb",
    "ubuntu-noble": "deb",
    "ubuntu-jammy": "deb",
    "debian-bookworm": "deb",
    "debian-trixie": "deb",
    "fedora-43": "rpm",
    "fedora-44": "rpm",
    "rhel-8": "rpm",
    "rhel-9": "rpm",
    "rhel-10": "rpm",
}
REQUIRED_JOBS = {"prepare", "plumber", "codeql", "candidates", "staging-tests", "staging-tests-arm64", "smoke-images"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(args):
    return run(args, check=True, capture_output=True).stdout


def identity():
    source_sha = command(["git", "rev-parse", "HEAD"]).decode().strip()
    require(source_sha == environ["GITHUB_SHA"], "checkout differs from triggering SHA")
    return {
        "source_sha": source_sha,
        "version": Path("src/VERSION").read_text().strip(),
        "run_id": environ["GITHUB_RUN_ID"],
        "run_attempt": environ["GITHUB_RUN_ATTEMPT"],
    }


def package_arch(platform, kind):
    arch = platform.removeprefix("linux/")
    return {"amd64": "x86_64", "arm64": "aarch64"}[arch] if kind == "rpm" else arch


def package_name(version, kind, arch):
    return f"bunkerweb-{version}-1.{arch}.rpm" if kind == "rpm" else f"bunkerweb_{version}-1_{arch}.deb"


def digest(value):
    require(isinstance(value, str) and fullmatch(r"sha256:[0-9a-f]{64}", value), "invalid SHA-256 digest")
    return value


def platform_digests(index):
    platforms = {}
    require(isinstance(index.get("manifests"), list), "candidate must include an image index and attestations")
    for item in index["manifests"]:
        platform = item["platform"]
        if platform == {"os": "unknown", "architecture": "unknown"}:
            require(item.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest", "unknown image platform")
            digest(item["digest"])
            continue
        name = "/".join(platform[key] for key in ("os", "architecture", "variant") if platform.get(key))
        # OCI permits the default arm64 variant to be explicit.
        if name == "linux/arm64/v8":
            name = "linux/arm64"
        require(name in PLATFORMS and name not in platforms, f"unexpected or duplicate image platform {name}")
        platforms[name] = digest(item["digest"])
    return platforms


def inspect_index(ref):
    return loads(command(["docker", "buildx", "imagetools", "inspect", "--raw", ref]))


def validate(manifest, expected):
    require(manifest.get("schema") == 1, "unsupported release manifest schema")
    for field in ("source_sha", "version", "run_id", "run_attempt"):
        require(manifest.get(field) == expected[field], f"manifest {field} mismatch")
    require(fullmatch(r"[0-9a-f]{40}", manifest["source_sha"]), "invalid source SHA")
    require(fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[~-](?:rc|beta)[0-9]+)?", manifest["version"]), "invalid release version")
    require(set(manifest["images"]) == set(IMAGES), "incomplete image inventory")
    for name, image in manifest["images"].items():
        prefix = f"ghcr.io/bunkerity/{name}-tests@"
        require(image["ref"].startswith(prefix), f"non-candidate image reference {name}")
        digest(image["ref"].removeprefix(prefix))
        require(set(image["platforms"]) == set(PLATFORMS), f"incomplete platforms for {name}")
        for value in image["platforms"].values():
            digest(value)
    found = set()
    for package in manifest["packages"]:
        distro, platform = package["distro"], package["platform"]
        require(distro in DISTROS and platform in PACKAGE_PLATFORMS, "unknown package variant")
        require((distro, platform) not in found, "duplicate package variant")
        found.add((distro, platform))
        kind = DISTROS[distro]
        arch = package_arch(platform, kind)
        require(package["artifact"] == f"package-{distro}-{arch}", "package artifact mismatch")
        require(package["filename"] == package_name(manifest["version"], kind, arch), "package name/version/architecture mismatch")
        digest("sha256:" + package["sha256"])
    require(found == {(distro, platform) for distro in DISTROS for platform in PACKAGE_PLATFORMS}, "incomplete package inventory")


def verify_package(package, directory):
    file = Path(directory) / package["filename"]
    require({entry.name for entry in Path(directory).iterdir() if entry.suffix in (".deb", ".rpm")} == {file.name}, "unexpected package files")
    require(file.is_file() and not file.is_symlink(), f"missing package {file}")
    require(sha256(file.read_bytes()).hexdigest() == package["sha256"], f"package checksum mismatch: {file}")
    return file


def require_success(needs, required=REQUIRED_JOBS):
    require(required <= needs.keys(), "missing mandatory release test jobs")
    for name in required:
        require(needs[name].get("result") == "success", f"mandatory job did not succeed: {name}")


def write_json(file, value):
    Path(file).write_text(dumps(value, indent=2, sort_keys=True) + "\n")


def record_image(args):
    digest(args.digest)
    require(args.image in IMAGES and args.platform in PLATFORMS, "unknown candidate image/platform")
    ref = f"ghcr.io/bunkerity/{args.image}-tests@{args.digest}"
    platforms = platform_digests(inspect_index(ref))
    require(set(platforms) == {args.platform}, "built image platform differs from matrix")
    write_json(args.output, identity() | {"kind": "image", "image": args.image, "ref": ref, "platforms": platforms})


def record_package(args):
    require(args.distro in DISTROS and args.platform in PACKAGE_PLATFORMS, "unknown package variant")
    source = identity()
    kind = DISTROS[args.distro]
    arch = package_arch(args.platform, kind)
    filename = package_name(source["version"], kind, arch)
    files = list(Path(args.directory).glob(f"*.{kind}"))
    require(len(files) == 1 and files[0].name == filename, "expected one correctly named candidate package")
    write_json(
        args.output,
        source
        | {
            "kind": "package",
            "distro": args.distro,
            "platform": args.platform,
            "artifact": f"package-{args.distro}-{arch}",
            "filename": filename,
            "sha256": sha256(files[0].read_bytes()).hexdigest(),
        },
    )


def assemble(args):
    source = identity()
    receipts = [loads(file.read_text()) for file in Path(args.directory).glob("*.json")]
    require(len(receipts) == len(IMAGES) * len(PLATFORMS) + len(DISTROS) * len(PACKAGE_PLATFORMS), "missing or extra build receipts")
    for receipt in receipts:
        require(all(receipt.get(key) == value for key, value in source.items()), "build receipt identity mismatch; rerun all jobs")
    manifest = source | {"schema": 1, "images": {}, "packages": []}
    for image in IMAGES:
        rows = [row for row in receipts if row["kind"] == "image" and row["image"] == image]
        require(len(rows) == len(PLATFORMS), f"missing image build receipts for {image}")
        expected = {}
        for row in rows:
            require(len(row["platforms"]) == 1 and not expected.keys() & row["platforms"].keys(), "duplicate image build receipt")
            expected.update(row["platforms"])
        tag = f"ghcr.io/bunkerity/{image}-tests:candidate-{source['run_id']}-{source['run_attempt']}"
        command(["docker", "buildx", "imagetools", "create", "--tag", tag, *[row["ref"] for row in rows]])
        # Ask the registry for the descriptor digest; hashing --raw output is unsafe because CLI output may add a newline.
        index_digest = command(["docker", "buildx", "imagetools", "inspect", "--format", "{{json .Manifest.Digest}}", tag]).decode().strip('"\n')
        ref = f"ghcr.io/bunkerity/{image}-tests@{digest(index_digest)}"
        actual = platform_digests(inspect_index(ref))
        require(actual == expected, "assembled candidate differs from built platform digests")
        manifest["images"][image] = {"ref": ref, "platforms": actual}
    manifest["packages"] = [{key: row[key] for key in ("distro", "platform", "artifact", "filename", "sha256")} for row in receipts if row["kind"] == "package"]
    validate(manifest, source)
    write_json(args.output, manifest)


def load_manifest(file, expected_hash):
    data = Path(file).read_bytes()
    require(fullmatch(r"[0-9a-f]{64}", expected_hash or ""), "missing manifest SHA-256")
    require(sha256(data).hexdigest() == expected_hash, "release manifest checksum mismatch")
    manifest = loads(data)
    expected = identity()
    # A failed test/publisher may be retried against an earlier build attempt in
    # this run. Mixing new build receipts remains forbidden by assemble().
    attempt = manifest.get("run_attempt", "")
    require(isinstance(attempt, str) and attempt.isdigit() and 0 < int(attempt) <= int(expected["run_attempt"]), "invalid build attempt")
    expected["run_attempt"] = attempt
    validate(manifest, expected)
    return manifest


def prepare_tests(manifest, test_type, packages):
    require(test_type in ("docker", "autoconf", "k8s", "linux"), "unknown integration type")
    kind = "kubernetes" if test_type == "k8s" else test_type
    suites = [loads(file.read_text()) for file in Path("examples").glob("*/tests.json")]
    require(any(kind in suite["kinds"] and suite["tests"] for suite in suites), "empty integration suite")
    with open(environ["GITHUB_ENV"], "a") as env:
        for name in ("bunkerweb", "scheduler", "autoconf"):
            ref = manifest["images"][name]["ref"]
            env.write(f"{name.upper()}_IMAGE={ref}\n")
            if test_type in ("docker", "autoconf"):
                command(["docker", "pull", "--platform", "linux/amd64", ref])
                command(["docker", "tag", ref, f"local/{name}-tests:latest"])
    if test_type == "linux":
        for package in manifest["packages"]:
            verify_package(package, Path(packages) / package["artifact"])


def promote(manifest, image, tags):
    source = manifest["images"][image]["ref"]
    for tag in tags.replace("~", "-").split(","):
        require(fullmatch(r"[a-z0-9./_-]+:[a-zA-Z0-9_.-]+", tag), "invalid publication tag")
        command(["skopeo", "copy", "--all", "--preserve-digests", "--retry-times", "3", f"docker://{source}", f"docker://{tag}"])
        actual = command(["skopeo", "inspect", "--format", "{{.Digest}}", f"docker://{tag}"]).decode().strip()
        require(actual == source.split("@")[1], f"published digest mismatch: {tag}")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("record-image", "record-package", "assemble", "verify", "prepare-tests", "promote", "gate"))
    parser.add_argument("--manifest", default="release-manifest.json")
    parser.add_argument("--manifest-sha256", default=environ.get("MANIFEST_SHA256", ""))
    parser.add_argument("--directory", default=".")
    parser.add_argument("--output", default="release-manifest.json")
    parser.add_argument("--image", choices=IMAGES)
    parser.add_argument("--platform", choices=PLATFORMS)
    parser.add_argument("--digest")
    parser.add_argument("--distro", choices=DISTROS)
    parser.add_argument("--type")
    parser.add_argument("--tags")
    parser.add_argument("--artifact")
    args = parser.parse_args()
    if args.operation == "record-image":
        record_image(args)
    elif args.operation == "record-package":
        record_package(args)
    elif args.operation == "assemble":
        assemble(args)
    else:
        if args.operation == "gate":
            require_success(loads(environ["NEEDS_JSON"]))
        manifest = load_manifest(args.manifest, args.manifest_sha256)
        if args.operation == "prepare-tests":
            prepare_tests(manifest, args.type, args.directory)
        elif args.operation == "promote":
            promote(manifest, args.image, args.tags)
        elif args.artifact:
            packages = [package for package in manifest["packages"] if package["artifact"] == args.artifact]
            require(len(packages) == 1, "package absent from candidate manifest")
            verify_package(packages[0], args.directory)
        elif args.operation == "verify" and args.directory != ".":
            for package in manifest["packages"]:
                verify_package(package, Path(args.directory) / package["artifact"])


if __name__ == "__main__":
    main()
