#!/bin/sh

# build-packages.sh [ REF ]

# Build packages. Use current checked out version, or a specific tag/commit.

# Files requiring a version bump
VERSION_FILES="lua-cjson-2.1devel-1.rockspec lua-cjson.spec lua_cjson.c manual.adoc runtests.sh tests/test.lua"

[ "$1" ] && BRANCH="$1" || BRANCH="`git describe --match '[1-3].[0-9]*'`"
VERSION="`git describe --match '[1-3].[0-9]*' $BRANCH`"
VERSION="${VERSION//-/.}"

PREFIX="lua-cjson-$VERSION"

set -x
set -e

DESTDIR="`pwd`/packages"
mkdir -p "$DESTDIR"
BUILDROOT="`mktemp -d`"
trap "rm -rf '$BUILDROOT'" 0

git archive --prefix="$PREFIX/" "$BRANCH" | tar xf - -C "$BUILDROOT"
cd "$BUILDROOT"

cd "$PREFIX"
rename 2.1devel "$VERSION" $VERSION_FILES
perl -pi -e "s/\\b2.1devel\\b/$VERSION/g" ${VERSION_FILES/2.1devel/$VERSION};
cd ..

make -C "$PREFIX" doc
tar cf - "$PREFIX" | gzip -9 > "$DESTDIR/$PREFIX.tar.gz"
zip -9rq "$DESTDIR/$PREFIX.zip" "$PREFIX"

# vi:ai et sw=4 ts=4:
