#!/bin/bash
# Remember to run this script in a docker container with 3.9 python version

echo "Updating python dependencies"

echo "Creating virtual environment"

python3 -m venv tmp_venv && source tmp_venv/bin/activate
pip install pip --upgrade > /dev/null && pip install pip-compile-multi pip-upgrader > /dev/null

echo "Updating requirements.in files"

files=("../docs/requirements.txt" "./requirements.in" "../ui/requirements.in" "../tests/requirements.txt")

for file in "${files[@]}"
do
    echo "Updating $file"
    cd $(dirname $file)

    if [[ $file == *.in ]]; then
        mv $(basename $file) $(basename ${file/%.in}.txt)
    fi

    echo "all" | pip-upgrade

    if [[ $file == *.in ]]; then
        mv $(basename ${file/%.in}.txt) $(basename $file)
        echo "Generating hashes for $file ..."
        pip-compile --generate-hashes --allow-unsafe --resolver=backtracking
    else
        echo "No need to generate hashes for $file"
    fi

    cd -
done

echo "Finished updating requirements.txt files, cleaning up ..."

deactivate
rm -rf tmp_venv
