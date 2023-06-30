#!/bin/bash

set -eu -o pipefail

changelog=$(cat Changes.md)

regex='## ([0-9]+\.[0-9]+\.[0-9]+) - ([0-9]{4}-[0-9]{2}-[0-9]{2})

((.|
)*)
'

if [[ ! $changelog =~ $regex ]]; then
      echo "Could not find date line in change log!"
      exit 1
fi

version="${BASH_REMATCH[1]}"
date="${BASH_REMATCH[2]}"
notes="$(echo "${BASH_REMATCH[3]}" | sed -n -e '/^## [0-9]\+\.[0-9]\+\.[0-9]\+/,$!p')"

dist="libmaxminddb-$version.tar.gz"

if [[ "$date" !=  $(date +"%Y-%m-%d") ]]; then
    echo "$date is not today!"
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo ". is not clean." >&2
    exit 1
fi

old_version=$(perl -MFile::Slurp=read_file <<EOF
use v5.16;
my \$conf = read_file(q{configure.ac});
\$conf =~ /AC_INIT.+\[(\d+\.\d+\.\d+)\]/;
say \$1;
EOF
)

perl -MFile::Slurp=edit_file -e \
    "edit_file { s/\Q$old_version/$version/g } \$_ for qw( configure.ac include/maxminddb.h CMakeLists.txt )"

if [ -n "$(git status --porcelain)" ]; then
    git diff

    read -e -p "Commit changes? " should_commit

    if [ "$should_commit" != "y" ]; then
        echo "Aborting"
        exit 1
    fi

    git add configure.ac include/maxminddb.h CMakeLists.txt
    git commit -m "Bumped version to $version"
fi

./bootstrap
./configure
make
make check
make clean
make safedist

if [ ! -d .gh-pages ]; then
    echo "Checking out gh-pages in .gh-pages"
    git clone -b gh-pages git@github.com:maxmind/libmaxminddb.git .gh-pages
    pushd .gh-pages
else
    echo "Updating .gh-pages"
    pushd .gh-pages
    git pull
fi

if [ -n "$(git status --porcelain)" ]; then
    echo ".gh-pages is not clean" >&2
    exit 1
fi

index=index.md
cat <<EOF > $index
---
layout: default
title: libmaxminddb - a library for working with MaxMind DB files
version: $version
---
EOF

cat ../doc/libmaxminddb.md >> $index

mmdblookup=mmdblookup.md
cat <<EOF > $mmdblookup
---
layout: default
title: mmdblookup - a utility to look up an IP address in a MaxMind DB file
version: $version
---
EOF

cat ../doc/mmdblookup.md >> $mmdblookup

git commit -m "Updated for $version" -a

read -p "Push to origin? (y/n) " should_push

if [ "$should_push" != "y" ]; then
    echo "Aborting"
    exit 1
fi

git push

popd

git push

gh release create --target "$(git branch --show-current)" -t "$version" -n "$notes" "$version" "$dist"
