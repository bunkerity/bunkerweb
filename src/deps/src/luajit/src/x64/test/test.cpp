#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <map>
#define LUAJIT_SECURITY_STRHASH 1
#include "test_util.hpp"
#include "../../lj_str.h"
str_sparse_hashfn hash_sparse;
str_dense_hashfn hash_dense;
#include "../../lj_str_hash.c"

using namespace std;


static bool
smoke_test()
{
  fprintf(stdout, "running smoke tests...\n");
	char buf[1024];
  char c = getpid() % 'a';
  srand(time(0));

  for (int i = 0; i < (int)sizeof(buf); i++) {
    buf[i] = (c + i) % 255;
  }

  uint32_t lens[] = {3, 4, 5, 7, 8, 16, 17, 24, 25, 32, 33, 127, 128,
                     255, 256, 257};
  for (unsigned i = 0; i < sizeof(lens)/sizeof(lens[0]); i++) {
    string s(buf, lens[i]);
    uint32_t h = hash_sparse_sse42(rand(), s.c_str(), lens[i]);
    test_printf("%d", h);
    test_printf("%d", hash_dense_sse42(rand(), h, s.c_str(), lens[i]));
  }

  return true;
}

static bool
verify_log2()
{
  fprintf(stdout, "verify log2...\n");
  bool err = false;
  std::map<uint32_t, uint32_t> lm;
  lm[0] =(uint32_t)-1;
  lm[1] = 0;
  lm[2] = 1;
  for (int i = 2; i < 31; i++) {
    lm[(1<<i) - 2] = i - 1;
    lm[(1<<i) - 1] = i - 1;
    lm[1<<i] = i;
    lm[(1<<i) + 1] = i;
  }
  lm[(uint32_t)-1] = 31;

  for (map<uint32_t, uint32_t>::iterator iter = lm.begin(), iter_e = lm.end();
       iter != iter_e; ++iter) {
    uint32_t v = (*iter).first;
    uint32_t log2_expect = (*iter).second;
    uint32_t log2_get = log2_floor(v);
    if (log2_expect != log2_get) {
      err = true;
      fprintf(stderr, "log2(%u) expect %u, get %u\n", v, log2_expect, log2_get);
      exit(1);
    }
  }
  return !err;
}

int
main(int argc, char** argv)
{
  fprintf(stdout, "=======================\nRun unit testing...\n");

  ASSERT(smoke_test(), "smoke_test test failed");
  ASSERT(verify_log2(), "log2 failed");

  fprintf(stdout, TestErrMsgMgr::noError() ? "succ\n\n" : "fail\n\n");

  return TestErrMsgMgr::noError() ? 0 : -1;
}
