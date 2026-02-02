#!/bin/bash
# Remember to run this script in a docker container with 3.9 python version

echo "Updating python dependencies"

echo "Creating virtual environment"

# shellcheck disable=SC1091
python3 -m venv tmp_venv && source tmp_venv/bin/activate

# Upgrade pip first for security
pip install --upgrade "pip<25.3" setuptools wheel

pip install --force-reinstall --no-cache-dir --require-hashes -r requirements-deps.txt

function update_python_deps() {
    file=$1

    echo "Updating $file"
    cd "$(dirname "$file")" || return

    if [[ $file == *.in ]]; then
        mv "$(basename "$file")" "$(basename "${file/%.in}.txt")"
    fi

    echo "all" | pip-upgrade "$(basename "${file/%.in}.txt")"

    if [[ $file == *.in ]]; then
        mv "$(basename "${file/%.in}.txt")" "$(basename "$file")"
        echo "Generating hashes for $file ..."
        pip-compile --generate-hashes --allow-unsafe --resolver=backtracking --strip-extras "$(basename "$file")"
    else
        echo "No need to generate hashes for $file"
    fi

    echo " "

    cd - || return
}

update_python_deps requirements-deps.in

# pip install --no-cache-dir --require-hashes -r requirements-deps.txt

pip install "pip<25.3"

echo "Updating python requirements files"

# Use array for explicit file list
files=(
    "requirements.in"
    "../api/requirements.in"
    "../autoconf/requirements.in"
    "../scheduler/requirements.in"
    "../ui/requirements.in"
)

# Safely find additional requirements files
# Use find with explicit constraints instead of globstar
while IFS= read -r -d '' file; do
    # Skip ansible-related files
    if [[ "$file" != *"ansible"* ]]; then
        files+=("$file")
    fi
done < <(find ../common ../docs ../misc -type f -name 'requirements*.in' -print0 2>/dev/null)

# Process each file
for file in "${files[@]}"; do
    update_python_deps "$file" || echo "Warning: Failed to update $file, continuing..."
done

echo "Finished updating python requirements files, cleaning up ..."

deactivate
rm -rf tmp_venv
