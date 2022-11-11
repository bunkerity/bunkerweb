dnl based on
dnl http://www.php.net/manual/en/internals2.buildsys.configunix.php


PHP_ARG_ENABLE(libinjection, for libinjection support,
[  --enable-libinjection            Include libinjection])

dnl Check whether the extension is enabled at all
if test "$PHP_LIBINJECTION" != "no"; then
  dnl Finally, tell the build system about the extension and what files are needed
  PHP_NEW_EXTENSION(libinjection, libinjection_sqli.c libinjection_wrap.c, $ext_shared)
  PHP_SUBST(LIBINJECTION_SHARED_LIBADD)
fi
