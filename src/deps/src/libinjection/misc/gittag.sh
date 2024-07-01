#!/bin/bash
set -e

# automated basic git tagging
# 1) edit the version number in
#   c/libinjection_sqli.c
#   pyton/setup.py
# 2) git add and commit
# 3) run this
# 4) done!
#

# get tag number
TAG=`grep 'LIBINJECTION_VERSION' ../c/libinjection_sqli.c | awk -F '"' '{print $2}' | tr -d '[[:space:]]'`

TAG="v${TAG}"

echo "TAG = ${TAG}"
echo "Tagging locally"
git tag -a "${TAG}" -m ${TAG}
echo "Sharing..."
git push origin "${TAG}"

git tag
echo "DONE"



