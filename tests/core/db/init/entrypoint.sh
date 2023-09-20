#!/bin/bash

echo "ℹ️ Cloning BunkerWeb Plugins ..."

git clone https://github.com/bunkerity/bunkerweb-plugins.git

echo "ℹ️ Extracting ClamAV plugin ..."

cp -r bunkerweb-plugins/clamav /plugins/

echo "ℹ️ Extracting settings.json file, db and core directory ..."

cp bunkerweb/settings.json /bunkerweb/
cp -r bunkerweb/core /bunkerweb/
cp -r bunkerweb/db /bunkerweb/

chown -R root:101 /plugins /bunkerweb
chmod -R 777 /plugins /bunkerweb
