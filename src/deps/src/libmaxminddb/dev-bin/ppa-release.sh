#!/bin/bash

set -e
set -x
set -u

DISTS=( questing noble jammy )

changelog_header=$(head -n 3 Changes.md)
if [[ ! $changelog_header =~ ^##\ ([0-9]+\.[0-9]+\.[0-9]+)\ -\ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
    echo "Could not find version in Changes.md!"
    exit 1
fi
VERSION="${BASH_REMATCH[1]}"

git push

RESULTS=/tmp/build-libmaxminddb-results/
SRCDIR="$RESULTS/libmaxminddb"

mkdir -p "$SRCDIR"

# gbp does weird things without a pristine checkout
git clone git@github.com:maxmind/libmaxminddb.git -b ubuntu-ppa $SRCDIR

pushd "$SRCDIR"
git merge "$VERSION"

for dist in "${DISTS[@]}"; do
    dch -v "$VERSION-0+maxmind1~$dist" -D "$dist" -u low "New upstream release."
    gbp buildpackage -S --git-ignore-new

    git clean -xfd
    git reset HEAD --hard
done

read -e -p "Release to PPA? (y/n)" SHOULD_RELEASE

if [ "$SHOULD_RELEASE" != "y" ]; then
    echo "Aborting"
    exit 1
fi

# Upload to launchpad
dput ppa:maxmind/ppa ../*source.changes

# Make the changelog up to date in git

dch -v "$VERSION-0+maxmind1" -D "${DISTS[0]}" -u low "New upstream release."

git add debian/changelog
git commit -m "Update debian/changelog for $VERSION"
git push

popd

git pull
