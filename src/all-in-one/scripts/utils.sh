#!/bin/bash

# Set NTASK to number of processors
set_ntask() {
    NTASK="$(nproc)"
    export NTASK
}

# Clone a git repo at a specific commit
git_clone_commit() {
    local DIR="$1"
    local URL="$2"
    local COMMIT="$3"
    mkdir "$DIR"
    cd "$DIR" || exit
    git init
    git remote add origin "$URL"
    git fetch origin "$COMMIT"
    git checkout FETCH_HEAD
}
