#/bin/bash

if [ $# -ne 1 ] ; then
    echo "Missing version argument"
    exit 1
fi



OLD_VERSION="$(cat src/VERSION | tr -d '\n' | sed 's/\./\\./g' | sed 's/\-/\\-/g')"
NEW_VERSION="$(echo -n "$1" | sed 's/\./\\./g' | sed 's/\-/\\-/g')"

# VERSION
echo -en "$NEW_VERSION" | sed 's/\\//g' > src/VERSION
# integrations
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" misc/integrations/*.yml
# examples
for example in examples/* ; do
    sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" ${example}/*.yml
done
# docs
sed -i "s@${OLD_VERSION}@${NEW_VERSION}@g" docs/*.md