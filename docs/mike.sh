#!/bin/bash

if [ "$1" != "dev" ] && [ "$1" != "latest" ] ; then
	echo "missing dev/latest argument"
	exit 1
fi

if [ "$1" == "dev" ] ; then
	mike deploy --push --update-aliases dev
else
	mike deploy --push --update-aliases "$(cat src/VERSION | sed -E 's/([0-9]+)\.([0-9]+)\.([0-9]+)/\1\.\2/')" latest
	mike set-default --push latest
fi