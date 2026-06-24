# Trivy ignore policy (Rego). Referenced by container-build.yml via `ignore-policy`.
#
# Suppresses vulnerabilities for Python packages, which are tracked and patched
# separately through the pip ecosystem (requirements files + dependabot) rather
# than at the container-image layer. Matches every PyPI package by PURL, so it is
# version-agnostic and independent of how the package was installed.
package trivy

default ignore = false

ignore {
	startswith(input.PkgIdentifier.PURL, "pkg:pypi/")
}
