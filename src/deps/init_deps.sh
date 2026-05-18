#!/bin/bash

function do_and_check_cmd() {
	output=$("$@" 2>&1)
	ret="$?"
	if [ $ret -ne 0 ] ; then
		echo "❌ Error from command : $*"
		echo "$output"
		exit $ret
	fi
	return 0
}

jq -c .download[] src/deps/deps.json | while read -r download
do
  url="$(echo "$download" | jq -r .url)"
  id="$(echo "$url" | sed 's/.*\/\([^\/]*\)\.tar\.gz/\1/')"
  name="$(echo "$download" | jq -r .name)"
  sha512="$(echo "$download" | jq -r .sha512)"
  post_install="$(echo "$repo" | jq -r .post_install)"

  echo "ℹ️ Downloading ${name} from $url"

  if [ ! -d "src/deps/src/$id" ] ; then
    do_and_check_cmd wget -q -O "src/deps/src/$id.tar.gz" "$url"
    check="$(sha512sum "src/deps/src/$id.tar.gz" | cut -d ' ' -f 1)"
		if [ "$check" != "$sha512" ] ; then
			echo "❌️ Wrong hash from file $url (expected $sha512 got $check)"
			exit 1
		fi
    if [ -f "src/deps/src/$id.tar.gz" ] ; then
      do_and_check_cmd tar -xvzf src/deps/src/"$id".tar.gz -C src/deps/src
      do_and_check_cmd rm -f src/deps/src/"$id".tar.gz
    fi
  else
		echo "⚠️ Skipping download of $url because target directory is already present"
	fi

  if [ "$post_install" != "null" ]; then
    echo "ℹ️ Running post install script for ${name}"
    bash -c "$post_install"
  fi
done

jq -c .git_repository[] src/deps/deps.json | while read -r repo
do
  id="$(echo "$repo" | jq -r .id)"
  name="$(echo "$repo" | jq -r .name)"
  url="$(echo "$repo" | jq -r .url)"
  commit="$(echo "$repo" | jq -r .commit)"
  submodules="$(echo "$repo" | jq -r '.submodules // false')"
  post_install="$(echo "$repo" | jq -r .post_install)"

  echo "ℹ️ Clone ${name} from $url at commit/version $commit"

  if [ -d "src/deps/src/$id" ] ; then
    rm -rf "src/deps/src/$id"
  fi

  do_and_check_cmd mkdir -p "src/deps/src/$id"
  do_and_check_cmd git -C "src/deps/src/$id" init
  do_and_check_cmd git -C "src/deps/src/$id" remote add origin "$url"
  do_and_check_cmd git -C "src/deps/src/$id" fetch origin "$commit"
  do_and_check_cmd git -C "src/deps/src/$id" checkout FETCH_HEAD

  if [ "$submodules" = "true" ] && [ -f "src/deps/src/$id/.gitmodules" ] ; then
    echo "ℹ️ Fetching submodules for ${name}"
    do_and_check_cmd git -C "src/deps/src/$id" submodule update --init --recursive
  fi

  if [ -d "src/deps/src/$id/.git" ] ; then
    do_and_check_cmd rm -rf "src/deps/src/$id/.git"
    do_and_check_cmd rm -rf "src/deps/src/$id/.github"
  fi
  # Submodules leave dangling `.git` pointer files (gitdir -> parent
  # .git/modules/...) and nested .gitmodules that break IDE source control
  # once the parent .git is gone. Only scrub these for submodule-enabled
  # deps so we don't preempt post_install scripts that expect to remove
  # `.gitmodules` themselves (e.g. modsecurity, ngx_brotli).
  if [ "$submodules" = "true" ] ; then
    do_and_check_cmd find "src/deps/src/$id" -depth \
      \( -name ".git" -o -name ".github" -o -name ".gitmodules" \) \
      -exec rm -rf {} +
  fi

  if [ "$post_install" != "null" ]; then
    echo "ℹ️ Running post install script for ${name}"
    bash -c "$post_install"
  fi
done
