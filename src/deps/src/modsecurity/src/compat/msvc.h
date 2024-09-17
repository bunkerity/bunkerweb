#ifndef __COMPAT_MSVC
#define __COMPAT_MSVC

#include <time.h>

#if !defined(S_ISREG) && defined(S_IFMT) && defined(S_IFREG)
#define S_ISREG(m) (((m) & S_IFMT) == S_IFREG)
#endif

#define strcasecmp   _stricmp
#define strncasecmp  _strnicmp
#define strtok_r     strtok_s
#define popen        _popen
#define pclose       _pclose

inline tm* localtime_r(const time_t* tin, tm* tout) {
  if (!localtime_s(tout, tin)) return tout;

  return nullptr;
}

#endif
