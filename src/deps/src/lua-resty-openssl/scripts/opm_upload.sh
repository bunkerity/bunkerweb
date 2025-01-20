#!/bin/bash -x
cd $(dirname $(readlink -e $0))/../

start=$(grep -n "## resty.openssl" README.md | head -n1 | cut -d: -f1)
end=$(grep -n "Copyright and License" README.md | tail -n1 | cut -d: -f1)
start=$(( start + 1 ))
end=$(( end - 1 ))


cat README.md | sed "${start},${end}d" | \
    sed -E "s/([+*])(.+)#/\1\2https:\/\/github.com\/fffonion\/lua-resty-openssl#/g" | \
    sed "s/## resty.openssl/Due to the size limit of OPM, the full documentation can be viewed at [Github](https:\/\/github.com\/fffonion\/lua-resty-openssl\/blob\/master\/README.md)\n\n/" \
    > README.opm.md

mv README.opm.md README.md

opm upload

git checkout README.md