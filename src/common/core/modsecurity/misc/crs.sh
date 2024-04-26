#!/bin/bash

function git_secure_clone() {
	repo="$1"
	commit="$2"
	folder="$3"

	if [ -z "$folder" ] || [ "$folder" == "" ] ; then
		folder="$(echo "$repo" | rev | cut -d '/' -f 1 | rev | sed -E "s@\.git@@")"
	fi

	if [ ! -d "files/${folder}" ] ; then
		output="$(git clone "$repo" "files/${folder}" 2>&1)"
		# shellcheck disable=SC2181
		if [ $? -ne 0 ] ; then
			echo "❌ Error cloning $1"
			echo "$output"
			exit 1
		fi
		old_dir="$(pwd)"
		cd "files/${folder}" || return 1
		output="$(git checkout "${commit}^{commit}" 2>&1)"
		# shellcheck disable=SC2181
		if [ $? -ne 0 ] ; then
			echo "❌ Commit hash $commit is absent from repository $repo"
			echo "$output"
			exit 1
		fi
		cd "$old_dir" || return 1
		output="$(rm -rf "files/${folder}/.git")"
		# shellcheck disable=SC2181
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
		cd "$CHANGE_DIR" || return 1
	fi
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
	return 0
}

rm -rf files/*

jq -c .git_repository[] misc/versions.json | while read -r repo
do
  id="$(echo "$repo" | jq -r .id)"
  name="$(echo "$repo" | jq -r .name)"
  url="$(echo "$repo" | jq -r .url)"
  commit="$(echo "$repo" | jq -r .commit)"
  post_install="$(echo "$repo" | jq -r .post_install)"

  echo "ℹ️ Clone ${name} from $url at commit/version $commit"

	git_secure_clone "$url" "$commit" "$id"

  if [ "$post_install" != "null" ]; then
    echo "ℹ️ Running post install script for ${name}"
    bash -c "$post_install"
  fi
done
