"""Run the existing integration suite with candidate images and final package bytes."""

from json import loads
from os import environ
from pathlib import Path
from re import fullmatch
from shlex import split
from shutil import copy2, copytree
from subprocess import run
from sys import argv, executable, stderr
from tempfile import TemporaryDirectory

from release_artifacts import command, load_manifest, require, verify_package


def cleanup(kind, suites, distro=None):
    """Remove only this integration's named container or generated manifests."""
    commands = []
    if kind == "linux":
        containers = command(["docker", "ps", "--all", "--quiet", "--filter", f"name=^/linux-{distro}$"]).decode().split()
        if containers:
            commands.append(["docker", "rm", "--force", *containers])
    else:
        filename = {"docker": "docker-compose.yml", "autoconf": "autoconf.yml", "kubernetes": "kubernetes.yml"}[kind]
        manifests = []
        for suite in suites:
            if kind in suite["kinds"]:
                require(fullmatch(r"[a-zA-Z0-9_-]+", suite["name"]), "unsafe integration name")
                manifests.append(Path("/tmp/tests") / suite["name"] / filename)
        if kind == "autoconf":
            manifests.append(Path("/tmp/autoconf/docker-compose.yml"))
        elif kind == "kubernetes":
            manifests.append(Path("/tmp/kubernetes/bunkerweb.yml"))
        for manifest in manifests:
            if manifest.is_file():
                if kind == "kubernetes":
                    commands.append(["kubectl", "delete", "--ignore-not-found", "--timeout=60s", "-f", str(manifest)])
                else:
                    commands.append(["docker", "compose", "--file", str(manifest), "down", "--volumes", "--remove-orphans"])
    failed = []
    for args in commands:
        try:
            result = run(args, timeout=90, check=False)
            if result.returncode:
                failed.append(args)
        except Exception:
            failed.append(args)
    require(not failed, f"integration cleanup failed for {failed}")
    if kind == "kubernetes" and Path("/tmp/kubernetes").is_dir():
        Path("/tmp/kubernetes/bunkerweb.yml").unlink(missing_ok=True)
        Path("/tmp/kubernetes").rmdir()


def run_suite(kind, suites, distro=None, platform=None):
    args = [executable, "tests/main.py", kind]
    if distro:
        args.append(distro)
    try:
        run(args, env=environ | ({"DOCKER_DEFAULT_PLATFORM": platform} if platform else {}), check=True)
    except BaseException:
        # tests/main.py exits before end() when init() fails; its child process
        # may also call os._exit(). Cleanup belongs around that process, but a
        # cleanup failure must not hide the suite failure that caused it.
        try:
            cleanup(kind, suites, distro)
        except BaseException as cleanup_error:
            print(f"integration cleanup failed after the suite failed: {cleanup_error}", file=stderr, flush=True)
        raise
    cleanup(kind, suites, distro)


def select_packages(packages, platform=""):
    """Keep one platform's packages when the caller splits the Linux tests by platform."""
    if not platform:
        return list(packages)
    selected = [package for package in packages if package["platform"] == platform]
    require(selected, f"no candidate package for platform {platform}")
    return selected


def main():
    test_type = argv[1]
    manifest = load_manifest("release-manifest.json", environ["MANIFEST_SHA256"])
    for assignment in split(environ["TEST_DOMAINS"]):
        name, separator, value = assignment.partition("=")
        require(separator and fullmatch(r"TEST_DOMAIN[0-9]+(?:_[0-9]+)?", name) and value, "invalid test domain assignment")
        environ[name] = value
    kind = "kubernetes" if test_type == "k8s" else test_type
    require(kind in ("docker", "autoconf", "kubernetes", "linux"), "unknown integration type")
    suites = [loads(file.read_text()) for file in Path("examples").glob("*/tests.json")]
    require(any(kind in suite["kinds"] and suite["tests"] for suite in suites), "empty integration suite")
    if kind != "linux":
        run_suite(kind, suites)
        return
    # Each harness adds distribution dependencies around an already-built package.
    # It never recompiles BunkerWeb; the bytes copied into /opt are checked again.
    for package in select_packages(manifest["packages"], environ.get("RELEASE_TEST_PLATFORM", "")):
        distro, platform = package["distro"], package["platform"]
        file = verify_package(package, Path("candidate-packages") / package["artifact"])
        image = f"local/{distro}:latest"
        with TemporaryDirectory(prefix="release-package-") as temporary:
            context = Path(temporary)
            copytree("src/linux", context / "src/linux")
            target = context / f"package-{distro}"
            target.mkdir()
            copy2(file, target / file.name)
            run(["docker", "build", "--platform", platform, "--file", f"tests/linux/Dockerfile-{distro}", "--tag", image, str(context)], check=True)
        copied = command(["docker", "run", "--rm", "--platform", platform, "--entrypoint", "sha256sum", image, f"/opt/{file.name}"]).decode().split()[0]
        require(copied == package["sha256"], "test harness contains a different package")
        print(f"Testing {package['artifact']} ({package['sha256']})", flush=True)
        try:
            run_suite("linux", suites, distro, platform)
        finally:
            run(["docker", "image", "rm", image], check=False)


if __name__ == "__main__":
    main()
