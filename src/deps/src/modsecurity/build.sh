#!/bin/sh

rm -rf autom4te.cache
rm -f aclocal.m4

cd src
rm -f headers.mk
echo "noinst_HEADERS = \\" > headers.mk
ls -1 \
    actions/*.h \
    actions/ctl/*.h \
    actions/data/*.h \
    actions/disruptive/*.h \
    actions/transformations/*.h \
    debug_log/*.h \
    audit_log/writer/*.h \
    collection/backend/*.h \
    operators/*.h \
    parser/*.h \
    request_body_processor/*.h \
    utils/*.h \
    variables/*.h \
    engine/*.h \
    *.h | tr "\012" " " >> headers.mk
cd ../

case `uname` in Darwin*) glibtoolize --force --copy ;;
  *) libtoolize --force --copy ;; esac
autoreconf --install
autoheader
automake --add-missing --foreign --copy --force-missing
autoconf --force
rm -rf autom4te.cache


