#!/bin/bash

function git_secure_clone() {
	repo="$1"
	commit="$2"
	folder="$(echo "$repo" | sed -E "s@https://github.com/.*/(.*)\.git@\1@")"
	if [ ! -d "files/${folder}" ] ; then
		output="$(git clone "$repo" "files/${folder}" 2>&1)"
		if [ $? -ne 0 ] ; then
			echo "❌ Error cloning $1"
			echo "$output"
			exit 1
		fi
		old_dir="$(pwd)"
		cd "files/${folder}"
		output="$(git checkout "${commit}^{commit}" 2>&1)"
		if [ $? -ne 0 ] ; then
			echo "❌ Commit hash $commit is absent from repository $repo"
			echo "$output"
			exit 1
		fi
		cd "$old_dir"
		output="$(rm -rf "files/${folder}/.git")"
		if [ $? -ne 0 ] ; then
			echo "❌ Can't delete .git from repository $repo"
			echo "$output"
			exit 1
		fi
	else
		echo "⚠️ Skipping clone of $repo because target directory is already present"
	fi
}

function do_and_check_cmd() {
	if [ "$CHANGE_DIR" != "" ] ; then
		cd "$CHANGE_DIR"
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
	#echo $output
	return 0
}

# CRS v3.3.5
echo "ℹ️ Download CRS"
git_secure_clone "https://github.com/coreruleset/coreruleset.git" "0bd51ff806c68e2a54c4d60ca13f731c5355696d"
do_and_check_cmd cp -r files/coreruleset/crs-setup.conf.example files/crs-setup.conf
