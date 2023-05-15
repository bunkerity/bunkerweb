#!/bin/bash

echo "ℹ️ Cloning BunkerWeb Plugins ..."

git clone https://github.com/bunkerity/bunkerweb-plugins.git

echo "ℹ️ Checking out to dev branch ..."

cd bunkerweb-plugins
git checkout dev # TODO: remove this when the next release of bw-plugins is out

echo "ℹ️ Extracting ClamAV plugin ..."

cp -r clamav /plugins/

chown -R root:101 /plugins
chmod -R 777 /plugins