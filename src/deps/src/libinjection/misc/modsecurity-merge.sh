#!/bin/bash

#
# Sync ModSecurity / libinjection
#

# explode on error
set -e

#
# CLONE LIBINJECTION
#
if [ ! -d libinjection ]; then
    git clone https://github.com/client9/libinjection.git
else
    (cd libinjection; git pull)
fi

pwd

#
# CLONE MODSECURITY
#
if [ ! -d ModSecurity ]; then
    git clone https://github.com/client9/ModSecurity.git
else
    ( cd ModSecurity; git pull )
fi
pwd

#
# Use right branch
#
(cd ModSecurity; git checkout remotes/trunk )

pwd

#
# COPY IN NEW LIBINJECTION
#
cp libinjection/COPYING.txt ModSecurity/apache2/
cp libinjection/c/libinjection.h ModSecurity/apache2/libinjection
cp libinjection/c/libinjection_sqli.c ModSecurity/apache2/libinjection
cp libinjection/c/libinjection_sqli.h ModSecurity/apache2/libinjection
cp libinjection/c/libinjection_sqli_data.h ModSecurity/apache2/libinjection


#
# REGENERATE / BUILD
#
cd ModSecurity
./autogen.sh
./configure
make
make distclean

#
# ADD NEW BITS
#
git add apache2/libinjection/COPYING.txt
git add apache2/libinjection/libinjection.h
git add apache2/libinjection/libinjection_sqli.h
git add apache2/libinjection/libinjection_sqli.c
git add apache2/libinjection/libinjection_sqli_data.h

# this file seems to get modified, reset just to be safe
git checkout standalone/Makefile.in

git commit -m 'libinjection sync'

#
# PUSH TO SPECIAL BRANCH
#
echo "pushing to remotes/trunk"
git push origin remotes/trunk

#
# PROFIT
#
