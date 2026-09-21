# Trivy ignore policy (Rego). Referenced by container-build.yml via `ignore-policy`.
#
# Suppresses whole ecosystems that are patched outside the container-image layer:
#
#   pkg:pypi/*    Python packages, tracked through the pip ecosystem (requirements
#                 files + dependabot).
#   pkg:golang/*  Go stdlib and modules. These come from the CrowdSec binaries built
#                 into the all-in-one image, and are addressed by bumping the pins in
#                 src/all-in-one/deps/crowdsec.json and src/all-in-one/deps/go.json —
#                 never by patching CrowdSec's dependency tree at build time. Those
#                 files are hand-maintained; dependabot does not cover them.
#
# Both rules match by PURL prefix, so they are version-agnostic and independent of how
# the package was installed.
package trivy

default ignore = false

ignore {
	startswith(input.PkgIdentifier.PURL, "pkg:pypi/")
}

ignore {
	startswith(input.PkgIdentifier.PURL, "pkg:golang/")
}
