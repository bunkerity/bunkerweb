#!/bin/bash -v

new_v=$1
if [[ -z $1 ]]; then
    echo "Usage: $0 version"
    exit 1
fi

if [[ $(uname) == "Darwin" ]]; then
    SED=gsed
else
    SED=sed
fi

git reset
old_rockspec=$(ls *.rockspec -r1|grep -v dev|grep -v "$new_v"|head -n1)
old_v=$(echo $old_rockspec | cut -d '-' -f4)
if [[ -z "$old_v" ]]; then
    echo "Unknown old version"
    exit 1
fi

echo "Creating new release $new_v from $old_v"
git branch -D release/${new_v}
git checkout -b release/${new_v}

# rockspec
new_rockspec="${old_rockspec/$old_v/$new_v}"
cp "$old_rockspec" "$new_rockspec"
git rm "$old_rockspec"
$SED -i "s/$old_v/$new_v/g" "$new_rockspec"
git add "$new_rockspec"

# file
$SED -i "s/_VERSION = '$old_v'/_VERSION = '$new_v'/g" lib/resty/*.lua
git add -u

# changelog
git commit -m "release: $new_v"
git tag "$new_v"
git-chglog --output CHANGELOG.md
git add -u
git tag -d "$new_v"
git commit -m "release: $new_v" --amend

