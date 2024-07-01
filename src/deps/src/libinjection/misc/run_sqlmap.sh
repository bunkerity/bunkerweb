#!/bin/bash

# Starts a bogus webserver that logs all input
# Then runs sqlmap
#

./nullserver.py --logging=none &

if [ ! -d "sqlmap" ]; then
    git clone https://github.com/sqlmapproject/sqlmap.git
else
    (cd sqlmap; git pull)
fi

SQLMAP=./sqlmap/sqlmap.py
URL=http://127.0.0.1:8888

HPP=
${SQLMAP} ${HPP} -v 0 --titles -p id --level=5 --risk=3 --url=${URL}/null?id=1
${SQLMAP} ${HPP} -v 0 --titles -p id --level=5 --risk=3 --url=${URL}/null?id=1234.5
${SQLMAP} ${HPP} -v 0 --titles -p id --level=5 --risk=3 --url=${URL}/null?id=foo

HPP=--hpp
${SQLMAP} ${HPP} -v 0 --titles -p id --level=5 --risk=3 --url=${URL}/null?id=1
${SQLMAP} ${HPP} -v 0 --titles -p id --level=5 --risk=3 --url=${URL}/null?id=1234.5
${SQLMAP} ${HPP} -v 0 --titles -p id --level=5 --risk=3 --url=${URL}/null?id=foo

curl -o /dev/null ${URL}/shutdown

