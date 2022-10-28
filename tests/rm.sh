#!/bin/bash

# drop and export secrets
echo "${CICD_SECRETS}" > /opt/.env
chmod +x /opt/.env
. /opt/.env

# go to terraform env
cd "/tmp/$1"
if [ $? -ne 0 ] ; then
	echo "terraform env is absent"
	exit 1
fi

# terraform destroy
terraform destroy

# done
exit $?
