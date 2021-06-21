#!/bin/sh

# load some functions
. /opt/bunkerized-nginx/entrypoint/utils.sh

if [ "$MULTISITE" != "yes" ] && [ "$AUTO_LETS_ENCRYPT" = "yes" ] ; then
	first_server_name=$(echo "$SERVER_NAME" | cut -d " " -f 1)
	domains_lets_encrypt=$(echo "$SERVER_NAME" | sed "s/ /,/g")
	EMAIL_LETS_ENCRYPT="${EMAIL_LETS_ENCRYPT-contact@$first_server_name}"
	if [ ! -f /etc/letsencrypt/live/${first_server_name}/fullchain.pem ] ; then
		echo "[*] Performing Let's Encrypt challenge for $domains_lets_encrypt ..."
		/opt/bunkerized-nginx/scripts/certbot-new.sh "$domains_lets_encrypt" "$EMAIL_LETS_ENCRYPT"
	fi
elif [ "$MULTISITE" = "yes" ] ; then
	servers=$(find /etc/nginx -name "site.env" | cut -d '/' -f 4)
	for server in $servers ; do
		lets_encrypt=$(grep "^AUTO_LETS_ENCRYPT=yes$" /etc/nginx/${server}/site.env)
		if [ "$lets_encrypt" != "" ] && [ ! -f /etc/letsencrypt/live/${server}/fullchain.pem ] ; then
			server_name=$(grep "^SERVER_NAME=.*$" /etc/nginx/${server}/site.env | sed "s/SERVER_NAME=//" | sed "s/ /,/g")
			echo "[*] Performing Let's Encrypt challenge for $server_name ..."
			EMAIL_LETS_ENCRYPT=$(grep "^EMAIL_LETS_ENCRYPT=.*$" /etc/nginx/${server}/site.env | sed "s/EMAIL_LETS_ENCRYPT=//")
			if [ "$EMAIL_LETS_ENCRYPT" = "" ] ; then
				EMAIL_LETS_ENCRYPT="contact@${server}"
			fi
			/opt/bunkerized-nginx/scripts/certbot-new.sh "$domains" "EMAIL_LETS_ENCRYPT"
		fi
	done
fi
