#!/bin/bash

echo "ℹ️ Cloning BunkerWeb Plugins ..."

git clone https://github.com/bunkerity/bunkerweb-plugins.git

echo "ℹ️ Checking out to dev branch ..."

cd bunkerweb-plugins

echo "ℹ️ Extracting ClamAV plugin ..."

cp -r clamav /plugins/

cd ..

echo "ℹ️ Extracting settings.json file, db and core directory ..."

cp bunkerweb/settings.json /bunkerweb/
cp -r bunkerweb/core /bunkerweb/
cp -r bunkerweb/db /bunkerweb/

chown -R root:101 /plugins /bunkerweb
chmod -R 777 /plugins /bunkerweb
