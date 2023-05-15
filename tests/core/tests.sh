#!/bin/bash

echo "🚀 Starting core tests ..."

# Prepare environment
# TODO: uncomment this in production
# find . -type f -name 'docker-compose.*' -exec sed -i "s@bunkerity/bunkerweb:.*@bunkerweb-tests@" {} \;
# find . -type f -name 'docker-compose.*' -exec sed -i "s@bunkerity/bunkerweb-scheduler:.*@scheduler-tests@" {} \;

for dir in $(ls -d */)
do
  if [ -f "$dir/test.sh" ] ; then
    echo "Testing ${dir%?} ..."
    cd $dir
    ./test.sh

    if [ $? -ne 0 ] ; then
      echo "❌ Core test ${dir%?} failed"
      exit 1
    fi

    cd ..

    echo " "
  else
    echo "⚠️ No tests in ${dir%?}, skipping."
  fi
done

echo "🚀 Core tests are done ! ✅"