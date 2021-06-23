#!/bin/bash

function cleanup() {
	docker kill "$1"
}

image="$1"

echo "[*] Run $image"
id="$(docker run --rm -d -it -p 80:80 "$image")"
if [ $? -ne 0 ] ; then
	echo "[!] docker run failed"
	cleanup "$id"
	exit 1
fi

echo "[*] Copy dependencies.sh"
docker cp helpers/dependencies.sh "$id:/tmp"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$id"
	exit 2
fi

echo "[*] Exec dependencies.sh"
docker exec "$id" /bin/bash -c 'chmod +x /tmp/dependencies.sh && /tmp/dependencies.sh'
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	cleanup "$id"
	exit 3
fi

echo "[*] Copy install.sh"
docker cp helpers/install.sh "$id:/tmp"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$id"
	exit 4
fi

echo "[*] Exec install.sh"
docker exec "$id" /bin/bash -c 'chmod +x /tmp/install.sh && /tmp/install.sh'
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	cleanup "$id"
	exit 5
fi

echo "[*] Exec nginx -V"
docker exec "$id" nginx -V
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	cleanup "$id"
	exit 6
fi

echo "[*] Copy variables.env"
docker cp "tests/variables.env" "$id:/opt/bunkerized-nginx"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$id"
	exit 7
fi

echo "[*] Copy index.html"
docker cp "tests/index.html" "$id:/opt/bunkerized-nginx/www"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$id"
	exit 8
fi

echo "[*] Exec bunkerized-nginx"
docker exec "$id" bunkerized-nginx
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	cleanup "$id"
	exit 9
fi

echo "[*] Exec curl"
res="$(curl -s -H "User-Agent: LegitOne" http://localhost/)"
if [ $? -ne 0 ] || [ "$res" != "ok" ] ; then
	echo "[!] curl failed"
	cleanup "$id"
	exit 10
fi

cleanup "$id"
