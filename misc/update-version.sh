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
# db
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" src/common/db/Database.py
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" src/common/db/model.py
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
# easy-install script
sed -i "s@DEFAULT_BUNKERWEB_VERSION=.*@DEFAULT_BUNKERWEB_VERSION=\"$NEW_VERSION_UNESCAPED\"@g" misc/install-bunkerweb.sh
