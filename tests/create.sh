#!/bin/bash

# drop and export secrets
echo "${CICD_SECRETS}" > /opt/.env
chmod +x /opt/.env
# shellcheck disable=SC1091
. /opt/.env

# create terraform env
mkdir "/tmp/$1"
cp ./tests/terraform/providers.tf "/tmp/$1"
cp -r ./tests/terraform/templates "/tmp/$1"
cp "./tests/terraform/${1}.tf" "/tmp/$1"
old_dir="$(pwd)"
cd "/tmp/$1" || exit 1

# terraform init
terraform init
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
	echo "terraform init failed"
	exit 1
fi

# terraform apply
terraform apply -auto-approve -input=false
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
	echo "terraform apply failed"
	terraform destroy -auto-approve
	exit 2
fi

# run ansible playbook
if [ -f "/tmp/${1}_inventory" ] ; then
	cd "${old_dir}/tests/ansible" || exit 1
	export ANSIBLE_HOST_KEY_CHECKING=False
	ansible-playbook -i "/tmp/${1}_inventory" "${1}_playbook"
	# shellcheck disable=SC2181
	if [ $? -ne 0 ] ; then
		echo "ansible-playbook failed"
		cd "/tmp/$1" || exit 1
		terraform destroy -auto-approve
		exit 3
	fi
fi

# done
exit 0
