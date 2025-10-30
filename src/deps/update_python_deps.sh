#!/bin/bash
# filepath: /home/bunkerity/dev/bunkerweb-dev/src/deps/update_python_deps.sh
set -euo pipefail  # Exit on error, undefined vars, and pipe failures

# Remember to run this script in a docker container with 3.9 python version

echo "Updating python dependencies"

# Validate we're in the correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Check if required files exist
if [[ ! -f "requirements-deps.txt" ]]; then
    echo "Error: requirements-deps.txt not found in $SCRIPT_DIR"
    exit 1
fi

echo "Creating virtual environment"

# Clean up any existing venv
if [[ -d "tmp_venv" ]]; then
    echo "Removing existing virtual environment"
    rm -rf tmp_venv
fi

python3 -m venv tmp_venv

# shellcheck disable=SC1091
source tmp_venv/bin/activate || {
    echo "Error: Failed to activate virtual environment"
    rm -rf tmp_venv
    exit 1
}

# Upgrade pip first for security
pip install --upgrade "pip<25.3" setuptools wheel

pip install --force-reinstall --no-cache-dir --require-hashes -r requirements-deps.txt || {
    echo "Error: Failed to install dependencies"
    deactivate
    rm -rf tmp_venv
    exit 1
}

function update_python_deps() {
    local file=$1
    local original_dir
    original_dir="$(pwd)"

    # Validate file exists and is readable
    if [[ ! -f "$file" ]]; then
        echo "Warning: File $file does not exist, skipping"
        return 1
    fi

    # Ensure file is within the project directory (prevent directory traversal)
    local real_file
    real_file="$(realpath "$file")"
    local project_root
    project_root="$(realpath "$SCRIPT_DIR/..")"

    if [[ ! "$real_file" == "$project_root"* ]]; then
        echo "Error: File $file is outside project directory, skipping for security"
        return 1
    fi

    echo "Updating $file"
    local file_dir
    file_dir="$(dirname "$file")"

    cd "$file_dir" || {
        echo "Error: Cannot change to directory $file_dir"
        return 1
    }

    local basename_file
    basename_file="$(basename "$file")"

    if [[ $file == *.in ]]; then
        cp "$basename_file" "${basename_file/%.in}.txt" || {
            echo "Error: Failed to copy $basename_file"
            cd "$original_dir" || exit 1
            return 1
        }
    fi

    local txt_file="${basename_file/%.in}.txt"

    echo "all" | pip-upgrade "$txt_file" || {
        echo "Warning: pip-upgrade failed for $txt_file"
        # Restore original if it was a .in file
        if [[ $file == *.in ]] && [[ -f "$basename_file" ]]; then
            rm -f "$txt_file"
        fi
        cd "$original_dir" || exit 1
        return 1
    }

    if [[ $file == *.in ]]; then
        # Remove the temporary .txt file
        rm -f "$txt_file"

        echo "Generating hashes for $file ..."

        # Determine if we need backtracking resolver (only for deps folder)
        local pip_compile_args=(
            --allow-unsafe
            --resolver=backtracking
            --generate-hashes
            --no-emit-index-url
            --no-emit-trusted-host
        )

        pip-compile "${pip_compile_args[@]}" "$basename_file" || {
            echo "Error: pip-compile failed for $basename_file"
            cd "$original_dir" || exit 1
            return 1
        }

        # Verify output file was created and has content
        local output_file="${basename_file/%.in}.txt"
        if [[ ! -s "$output_file" ]]; then
            echo "Error: Generated requirements file is empty or missing"
            cd "$original_dir" || exit 1
            return 1
        fi

        # Verify hashes were actually generated
        if ! grep -q "sha256:" "$output_file"; then
            echo "Warning: No SHA256 hashes found in $output_file"
        fi
    else
        echo "No need to generate hashes for $file"
    fi

    echo " "

    cd "$original_dir" || exit 1
}

# Trap to ensure cleanup on exit
trap 'deactivate 2>/dev/null || true; rm -rf "$SCRIPT_DIR/tmp_venv"' EXIT INT TERM

update_python_deps requirements-deps.in || {
    echo "Error: Failed to update requirements-deps.in"
    exit 1
}

pip install --no-cache-dir --require-hashes -r requirements-deps.txt || {
    echo "Error: Failed to reinstall dependencies after update"
    exit 1
}

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

echo "Finished updating python requirements files"

# Cleanup happens via trap
deactivate
