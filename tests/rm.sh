#!/bin/bash

# drop and export secrets
echo "${CICD_SECRETS}" > /opt/.env
chmod +x /opt/.env
# shellcheck disable=SC1091
. /opt/.env

# go to terraform env
cd "/tmp/$1" || exit 1
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
	echo "terraform env is absent"
	exit 1
fi

# terraform destroy
terraform destroy -auto-approve

# done
exit $?
