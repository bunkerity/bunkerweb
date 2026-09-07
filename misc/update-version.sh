#!/bin/bash

if [ $# -ne 1 ] ; then
    echo "Missing version argument"
    exit 1
fi

OLD_VERSION="$(tr -d '\n' < src/VERSION | sed 's/\./\\./g' | sed 's/\-/\\-/g' | sed 's/~/\\~/g')"
NEW_VERSION="$(echo -n "$1" | sed 's/\./\\./g' | sed 's/\-/\\-/g' | sed 's/~/\\~/g')"

# Docker tag versions: replace ~ with - for valid Docker/GHCR tag names
OLD_DOCKER_VERSION="${OLD_VERSION//\\~/-}"
NEW_DOCKER_VERSION="${NEW_VERSION//\\~/-}"

# Unescaped versions for direct substitution
NEW_VERSION_UNESCAPED="${NEW_VERSION//\\/}"

# VERSION
echo -en "$NEW_VERSION_UNESCAPED" | tee src/VERSION
# integrations (uses Docker image tags only)
sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" misc/integrations/*.yml
# examples (uses Docker image tags only)
shopt -s globstar
for example in examples/* ; do
    if [ -d "$example" ] ; then
        # shellcheck disable=SC2086
        sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" ${example}/*.yml
    fi
done
shopt -u globstar
# docs - Docker image tags only (bunkerity/image:version pattern)
sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" docs/*.md
sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" docs/*/*.md
# docs - GitHub repository links (tree/blob/releases/raw URLs must use - instead of ~)
sed -i "s@github.com/bunkerity/bunkerweb/tree/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/tree/v${NEW_DOCKER_VERSION}@g" docs/*.md
sed -i "s@github.com/bunkerity/bunkerweb/tree/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/tree/v${NEW_DOCKER_VERSION}@g" docs/*/*.md
sed -i "s@github.com/bunkerity/bunkerweb/blob/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/blob/v${NEW_DOCKER_VERSION}@g" docs/*.md
sed -i "s@github.com/bunkerity/bunkerweb/blob/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/blob/v${NEW_DOCKER_VERSION}@g" docs/*/*.md
sed -i "s@github.com/bunkerity/bunkerweb/releases/download/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/releases/download/v${NEW_DOCKER_VERSION}@g" docs/*.md
sed -i "s@github.com/bunkerity/bunkerweb/releases/download/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/releases/download/v${NEW_DOCKER_VERSION}@g" docs/*/*.md
sed -i "s@github.com/bunkerity/bunkerweb/raw/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/raw/v${NEW_DOCKER_VERSION}@g" docs/*.md
sed -i "s@github.com/bunkerity/bunkerweb/raw/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/raw/v${NEW_DOCKER_VERSION}@g" docs/*/*.md
# docs - other version references keep ~
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" docs/*.md
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" docs/*/*.md
# README - Docker image tags only
sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" README.md
sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" src/common/core/*/README*.md
# README - GitHub repository links (tree/blob/releases/raw URLs must use - instead of ~)
sed -i "s@github.com/bunkerity/bunkerweb/tree/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/tree/v${NEW_DOCKER_VERSION}@g" README.md
sed -i "s@github.com/bunkerity/bunkerweb/tree/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/tree/v${NEW_DOCKER_VERSION}@g" src/common/core/*/README*.md
sed -i "s@github.com/bunkerity/bunkerweb/blob/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/blob/v${NEW_DOCKER_VERSION}@g" README.md
sed -i "s@github.com/bunkerity/bunkerweb/blob/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/blob/v${NEW_DOCKER_VERSION}@g" src/common/core/*/README*.md
sed -i "s@github.com/bunkerity/bunkerweb/releases/download/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/releases/download/v${NEW_DOCKER_VERSION}@g" README.md
sed -i "s@github.com/bunkerity/bunkerweb/releases/download/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/releases/download/v${NEW_DOCKER_VERSION}@g" src/common/core/*/README*.md
sed -i "s@github.com/bunkerity/bunkerweb/raw/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/raw/v${NEW_DOCKER_VERSION}@g" README.md
sed -i "s@github.com/bunkerity/bunkerweb/raw/v${OLD_DOCKER_VERSION}@github.com/bunkerity/bunkerweb/raw/v${NEW_DOCKER_VERSION}@g" src/common/core/*/README*.md
# README - other version references keep ~
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" README.md
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" src/common/core/*/README*.md
# tests (uses Docker image tags only)
sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" tests/ui/docker-compose.yml
shopt -s globstar
for test in tests/core/* ; do
    if [ -d "$test" ] ; then
        sed -i "s@bunkerity/\([^:]*\):${OLD_DOCKER_VERSION}@bunkerity/\1:${NEW_DOCKER_VERSION}@g" "$test/docker-compose.yml"
    fi
done
shopt -u globstar
# linux
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" src/linux/scripts/beforeInstall.sh
# db (the default version moved from Database.py to the metadata mixin when Database.py was split into db_methods/)
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" src/common/db/db_methods/metadata.py
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" src/common/db/model.py
# controlled downgrade: the manifest is keyed on src/VERSION and the CLI matches `from` verbatim,
# so a stamped build that leaves it behind ships a manifest it can never match itself -- "No
# manifest entry for 1.7-dev -> 1.6.14 on sqlite", every pair unclassified, the in-place path
# silently gone. Same for the upgrade spec's version pin, which asserts against the artifact built
# from this stamp. Note what does NOT catch a regression here: tests/unit/backup/
# test_downgrade_manifest.py compares the manifest to src/VERSION on the checked-in tree, where
# both read the same thing whether or not this line exists. The net is the integration spec
# tests/core/backup.yml::downgrade_finds_the_shipped_manifest, which runs inside a stamped image.
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" src/common/core/backup/downgrade-manifest.json
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" tests/core/upgrade.yml
# github
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" .github/ISSUE_TEMPLATE/bug_report.yml
# pyproject
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" pyproject.toml
# Dockerfiles (keep original version with ~ for LABEL)
sed -i "s@LABEL version.*@LABEL version=\"$NEW_VERSION_UNESCAPED\"@g" src/all-in-one/Dockerfile
sed -i "s@LABEL version.*@LABEL version=\"$NEW_VERSION_UNESCAPED\"@g" src/api/Dockerfile
sed -i "s@LABEL version.*@LABEL version=\"$NEW_VERSION_UNESCAPED\"@g" src/bw/Dockerfile
sed -i "s@LABEL version.*@LABEL version=\"$NEW_VERSION_UNESCAPED\"@g" src/scheduler/Dockerfile
sed -i "s@LABEL version.*@LABEL version=\"$NEW_VERSION_UNESCAPED\"@g" src/ui/Dockerfile
sed -i "s@LABEL version.*@LABEL version=\"$NEW_VERSION_UNESCAPED\"@g" src/autoconf/Dockerfile
sed -i "s@LABEL version.*@LABEL version=\"$NEW_VERSION_UNESCAPED\"@g" src/worker/Dockerfile
# easy-install script
sed -i "s@DEFAULT_BUNKERWEB_VERSION=.*@DEFAULT_BUNKERWEB_VERSION=\"$NEW_VERSION_UNESCAPED\"@g" misc/install-bunkerweb.sh
# publiccode.yml
sed -i "s@softwareVersion: .*@softwareVersion: $NEW_VERSION_UNESCAPED@g" publiccode.yml
sed -i "s@releaseDate: .*@releaseDate: $(date +%Y-%m-%d)@g" publiccode.yml
sed -i "s@logo: .*@logo: https://github.com/bunkerity/bunkerweb/raw/v$NEW_DOCKER_VERSION/misc/logo.png@g" publiccode.yml
