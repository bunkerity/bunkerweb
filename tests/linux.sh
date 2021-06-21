#!/bin/sh

image="$1"

echo "[*] Run $image"
id="$(docker run -d -it "$image")"
if [ $? -ne 0 ] ; then
	echo "[!] docker run failed"
	exit 1
fi

echo "[*] Copy dependencies.sh"
docker cp helpers/dependencies.sh "$id:/tmp"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	exit 2
fi

echo "[*] Exec dependencies.sh"
docker exec "$id" /bin/bash -c 'chmod +x /tmp/dependencies.sh && /tmp/dependencies.sh'
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	exit 3
fi

echo "[*] Copy install.sh"
docker cp helpers/install.sh "$id:/tmp"
if [ $? -ne 0 ] ; then
	echo "[!] docker cp failed"
	exit 4
fi

echo "[*] Exec install.sh"
docker exec "$id" /bin/bash -c 'chmod +x /tmp/install.sh && /tmp/install.sh'
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	exit 4
fi

echo "[*] Exec nginx -V"
docker exec "$id" nginx -V
if [ $? -ne 0 ] ; then
	echo "[!] docker exec failed"
	exit 5
fi
