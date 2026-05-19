dnl Check for LMDB Libraries
dnl LMDB is disabled by default; only enabled when --with-lmdb is given.
dnl Sets:
dnl  LMDB_CFLAGS
dnl  LMDB_LDADD
dnl  LMDB_LDFLAGS
dnl  LMDB_VERSION
dnl  LMDB_DISPLAY
dnl  LMDB_FOUND

AC_DEFUN([PROG_LMDB], [

# LMDB is opt-in: auto-detect finds it but we only activate when
# --with-lmdb or --with-lmdb=PATH is given explicitly.
MSC_CHECK_LIB([LMDB], [lmdb], [lmdb.h], [lmdb], [-DWITH_LMDB])

# If LMDB was found by auto-detection (no explicit --with-lmdb) treat it
# as disabled since LMDB is opt-in.
_msc_lmdb_with_val="$with_lmdb"
if test "x${_msc_lmdb_with_val}" = "x" && test "x${LMDB_FOUND}" = "x1"; then
    LMDB_FOUND=2
    LMDB_CFLAGS=""
    LMDB_LDADD=""
    LMDB_LDFLAGS=""
    LMDB_DISPLAY=""
    AC_MSG_NOTICE([LMDB is disabled by default. Use --with-lmdb to enable.])
fi

]) # AC_DEFUN [PROG_LMDB]
