#ifndef _TEST_UTIL_HPP_
#define _TEST_UTIL_HPP_

#include <sys/time.h> // gettimeofday()
#include <string>
#include <vector>

struct TestErrMsg
{
  const char* fileName;
  unsigned lineNo;
  std::string errMsg;

  TestErrMsg(const char* FN, unsigned LN, const char* Err):
             fileName(FN), lineNo(LN), errMsg(Err) {}
};

class TestErrMsgMgr
{
public:
  static std::vector<TestErrMsg> getError();
  static void
  addError(const char* fileName, unsigned lineNo, const char* Err) {
    _errMsg.push_back(TestErrMsg(fileName, lineNo, Err));
  }

  static bool noError() {
    return _errMsg.empty();
  }

private:
  static std::vector<TestErrMsg> _errMsg;
};

#define ASSERT(c, e) \
  if (!(c)) { TestErrMsgMgr::addError(__FILE__, __LINE__, (e)); }

class TestClock
{
public:
  void start() { gettimeofday(&_start, 0); }
  void stop() { gettimeofday(&_end, 0); }
  double getElapseInSecond() {
    return (_end.tv_sec - _start.tv_sec)
            + ((long)_end.tv_usec - (long)_start.tv_usec) / 1000000.0;
  }

private:
  struct timeval _start, _end;
};

// write to /dev/null, the only purpose is to make the data fed to the
// function alive.
extern void test_printf(const char* format, ...)
  __attribute__ ((format (printf, 1, 2)));

#endif //_TEST_UTIL_HPP_
