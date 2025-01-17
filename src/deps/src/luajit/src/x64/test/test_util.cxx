#include <stdarg.h>
#include <stdio.h>
#include "test_util.hpp"

using namespace std;

std::vector<TestErrMsg> TestErrMsgMgr::_errMsg;

void
test_printf(const char* format, ...)
{
  va_list args;
  va_start (args, format);

  FILE* devNull = fopen("/dev/null", "w");
  if (devNull != 0) {
    (void)vfprintf (devNull, format, args);
  }
  fclose(devNull);
  va_end (args);
}
