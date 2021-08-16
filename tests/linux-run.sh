#!/bin/bash

function cleanup() {
	docker kill "$1"
}

image="$1"
name="$2"
do_cleanup="yes"
if [ "$3" == "no" ] ; then
	do_cleanup="no"
fi

echo "[*] Run $image"
id="$(docker run --rm -d -p 80:80 -p 443:443 --privileged=true --name "$name" "$image" /sbin/init)"
if [ $? -ne 0 ] ; then
	echo "[!] docker run failed"
	cleanup "$name"
	exit 1
fi

echo "[*] Copy install.sh"
docker cp helpers/install.sh "$name:/tmp"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$name"
	exit 2
fi

echo "[*] Copy bunkerized-nginx"
docker cp . "$name:/tmp/bunkerized-nginx-test"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$name"
	exit 3
fi

echo "[*] Exec install.sh"
docker exec "$name" /bin/bash -c 'chmod +x /tmp/install.sh && /tmp/install.sh'
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	cleanup "$name"
	exit 4
fi

echo "[*] Exec nginx -V"
docker exec "$name" nginx -V
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	cleanup "$name"
	exit 5
fi

echo "[*] Copy variables.env"
docker cp "tests/variables.env" "$name:/opt/bunkerized-nginx"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$name"
	exit 6
fi

echo "[*] Copy index.html"
docker cp "tests/index.html" "$name:/opt/bunkerized-nginx/www"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	cleanup "$name"
	exit 7
fi

echo "[*] Exec bunkerized-nginx"
docker exec "$name" bunkerized-nginx
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	cleanup "$name"
	exit 8
fi

echo "[*] Exec curl"
res="$(curl -s -H "User-Agent: LegitOne" http://localhost/)"
if [ $? -ne 0 ] || [ "$res" != "ok" ] ; then
	echo "[!] curl failed"
	cleanup "$name"
	exit 9
fi

if [ "$do_cleanup" == "yes" ] ; then
	cleanup "$name"
fi
