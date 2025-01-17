#include <sys/time.h> // for gettimeofday()
extern "C" {
#define LUAJIT_SECURITY_STRHASH 1
#include "../../lj_str.h"
str_sparse_hashfn hash_sparse;
str_dense_hashfn hash_dense;
#include "../../lj_str_hash.c"
}
#include <string>
#include <vector>
#include <utility>
#include <algorithm>
#include "test_util.hpp"
#include <stdio.h>
#include <math.h>

using namespace std;

#define lj_rol(x, n) (((x)<<(n)) | ((x)>>(-(int)(n)&(8*sizeof(x)-1))))
#define lj_ror(x, n) (((x)<<(-(int)(n)&(8*sizeof(x)-1))) | ((x)>>(n)))

const char* separator = "-------------------------------------------";

static uint32_t LJ_AINLINE
original_hash_sparse(uint64_t seed, const char *str, size_t len)
{
  uint32_t a, b, h = len ^ seed;
  if (len >= 4) {
    a = lj_getu32(str); h ^= lj_getu32(str+len-4);
    b = lj_getu32(str+(len>>1)-2);
    h ^= b; h -= lj_rol(b, 14);
    b += lj_getu32(str+(len>>2)-1);
    a ^= h; a -= lj_rol(h, 11);
    b ^= a; b -= lj_rol(a, 25);
    h ^= b; h -= lj_rol(b, 16);
  } else {
    a = *(const uint8_t *)str;
    h ^= *(const uint8_t *)(str+len-1);
    b = *(const uint8_t *)(str+(len>>1));
    h ^= b; h -= lj_rol(b, 14);
  }

  a ^= h; a -= lj_rol(h, 11);
  b ^= a; b -= lj_rol(a, 25);
  h ^= b; h -= lj_rol(b, 16);

  return h;
}

static uint32_t original_hash_dense(uint64_t seed, uint32_t h,
				    const char *str, size_t len)
{
  uint32_t b = lj_bswap(lj_rol(h ^ (uint32_t)(seed >> 32), 4));
  if (len > 12) {
    uint32_t a = (uint32_t)seed;
    const char *pe = str+len-12, *p = pe, *q = str;
    do {
      a += lj_getu32(p);
      b += lj_getu32(p+4);
      h += lj_getu32(p+8);
      p = q; q += 12;
      h ^= b; h -= lj_rol(b, 14);
      a ^= h; a -= lj_rol(h, 11);
      b ^= a; b -= lj_rol(a, 25);
    } while (p < pe);
    h ^= b; h -= lj_rol(b, 16);
    a ^= h; a -= lj_rol(h, 4);
    b ^= a; b -= lj_rol(a, 14);
  }
  return b;
}


template<class T> double
BenchmarkHashTmpl(T func, uint64_t seed, char* buf, size_t len)
{
  TestClock timer;
  uint32_t h = 0;

  timer.start();
  for(int i = 1; i < 1000000 * 100; i++) {
    // So the buf is not loop invariant, hence the F(...)
    buf[i % 4096] = i;
    h += func(seed, buf, len) ^ i;
  }
  timer.stop();

  // make h alive
  test_printf("%x", h);
  return timer.getElapseInSecond();
}

struct TestFuncWasSparse
{
  uint32_t operator()(uint64_t seed, const char* buf, uint32_t len) {
    return original_hash_sparse(seed, buf, len);
  }
};

struct TestFuncIsSparse
{
  uint32_t operator()(uint64_t seed, const char* buf, uint32_t len) {
    return hash_sparse_sse42(seed, buf, len);
  }
};

struct TestFuncWasDense
{
  uint32_t operator()(uint64_t seed, const char* buf, uint32_t len) {
    return original_hash_dense(seed, 42, buf, len);
  }
};

struct TestFuncIsDense
{
  uint32_t operator()(uint64_t seed, const char* buf, uint32_t len) {
    return hash_dense_sse42(seed, 42, buf, len);
  }
};

static void
benchmarkIndividual(uint64_t seed, char* buf)
{
  fprintf(stdout,"\n\nCompare performance of particular len (in second)\n");
  fprintf(stdout, "%-12s%-8s%-8s%s%-8s%-8s%s\n", "len",
	  "was (s)", "is (s)", "diff (s)",
	  "was (d)", "is (d)", "diff (d)");
  fprintf(stdout, "-------------------------------------------\n");

  uint32_t lens[] = {3, 4, 7, 10, 15, 16, 20, 32, 36, 63, 80, 100,
                     120, 127, 280, 290, 400};
  for (unsigned i = 0; i < sizeof(lens)/sizeof(lens[0]); i++) {
    uint32_t len = lens[i];
    double e1 = BenchmarkHashTmpl(TestFuncWasSparse(), seed, buf, len);
    double e2 = BenchmarkHashTmpl(TestFuncIsSparse(), seed, buf, len);
    double e3 = BenchmarkHashTmpl(TestFuncWasDense(), seed, buf, len);
    double e4 = BenchmarkHashTmpl(TestFuncIsDense(), seed, buf, len);
    fprintf(stdout, "len = %4d: %-7.3lf %-7.3lf %-7.2f%% %-7.3lf %-7.3lf %.2f%%\n",
	    len, e1, e2, 100*(e1-e2)/e1, e3, e4, 100*(e3-e4)/e3);
  }
}

template<class T> double
BenchmarkChangeLenTmpl(T func, uint64_t seed, char* buf, uint32_t* len_vect,
		       uint32_t len_num)
{
  TestClock timer;
  uint32_t h = 0;

  timer.start();
  for(int i = 1; i < 1000000 * 100; i++) {
    for (int j = 0; j < (int)len_num; j++) {
      // So the buf is not loop invariant, hence the F(...)
      buf[(i + j) % 4096] = i;
      h += func(seed, buf, len_vect[j]) ^ j;
    }
  }
  timer.stop();

  // make h alive
  test_printf("%x", h);
  return timer.getElapseInSecond();
}

// It is to measure the performance when length is changing.
// The purpose is to see how balanced branches impact the performance.
//
static void
benchmarkToggleLens(uint64_t seed, char* buf)
{
  double e1, e2, e3, e4;
  fprintf(stdout,"\nChanging length (in second):");
  fprintf(stdout, "\n%-24s%-8s%-8s%s%-8s%-8s%s\n%s\n", "len",
	  "was (s)", "is (s)", "diff (s)",
	  "was (d)", "is (d)", "diff (d)",
          separator);

  uint32_t lens1[] = {4, 9};
  e1 = BenchmarkChangeLenTmpl(TestFuncWasSparse(), seed, buf, lens1, 2);
  e2 = BenchmarkChangeLenTmpl(TestFuncIsSparse(), seed, buf, lens1, 2);
  e3 = BenchmarkChangeLenTmpl(TestFuncWasDense(), seed, buf, lens1, 2);
  e4 = BenchmarkChangeLenTmpl(TestFuncIsDense(), seed, buf, lens1, 2);
  fprintf(stdout, "%-20s%-7.3lf %-7.3lf %-7.2f%% %-7.3lf %-7.3lf %.2f%%\n", "4,9",
	  e1, e2, 100*(e1-e2)/e1, e3, e4, 100*(e3-e4)/e3);

  uint32_t lens2[] = {1, 4, 9};
  e1 = BenchmarkChangeLenTmpl(TestFuncWasSparse(), seed, buf, lens2, 3);
  e2 = BenchmarkChangeLenTmpl(TestFuncIsSparse(), seed, buf, lens2, 3);
  e3 = BenchmarkChangeLenTmpl(TestFuncWasDense(), seed, buf, lens2, 3);
  e4 = BenchmarkChangeLenTmpl(TestFuncIsDense(), seed, buf, lens2, 3);
  fprintf(stdout, "%-20s%-7.3lf %-7.3lf %-7.2f%% %-7.3lf %-7.3lf %.2f%%\n", "1,4,9",
	  e1, e2, 100*(e1-e2)/e1, e3, e4, 100*(e3-e4)/e3);

  uint32_t lens3[] = {1, 33, 4, 9};
  e1 = BenchmarkChangeLenTmpl(TestFuncWasSparse(), seed, buf, lens3, 4);
  e2 = BenchmarkChangeLenTmpl(TestFuncIsSparse(), seed, buf, lens3, 4);
  e3 = BenchmarkChangeLenTmpl(TestFuncWasDense(), seed, buf, lens3, 4);
  e4 = BenchmarkChangeLenTmpl(TestFuncIsDense(), seed, buf, lens3, 4);
  fprintf(stdout, "%-20s%-7.3lf %-7.3lf %-7.2f%% %-7.3lf %-7.3lf %.2f%%\n",
	  "1,33,4,9", e1, e2, 100*(e1-e2)/e1, e3, e4, 100*(e3-e4)/e3);

  uint32_t lens4[] = {16, 33, 64, 89};
  e1 = BenchmarkChangeLenTmpl(TestFuncWasSparse(), seed, buf, lens4, 4);
  e2 = BenchmarkChangeLenTmpl(TestFuncIsSparse(), seed, buf, lens4, 4);
  e3 = BenchmarkChangeLenTmpl(TestFuncWasDense(), seed, buf, lens4, 4);
  e4 = BenchmarkChangeLenTmpl(TestFuncIsDense(), seed, buf, lens4, 4);
  fprintf(stdout, "%-20s%-7.3lf %-7.3lf %-7.2f%% %-7.3lf %-7.3lf %.2f%%\n",
	  "16,33,64,89", e1, e2, 100*(e1-e2)/e1, e3, e4, 100*(e3-e4)/e3);
}

static void
genRandomString(uint32_t min, uint32_t max,
                uint32_t num, vector<string>& result)
{
  double scale = (max - min) / (RAND_MAX + 1.0);
  result.clear();
  result.reserve(num);
  for (uint32_t i = 0; i < num; i++) {
    uint32_t len = (rand() * scale) + min;

    char* buf = new char[len];
    for (uint32_t l = 0; l < len; l++) {
      buf[l] = rand() % 255;
    }
    result.push_back(string(buf, len));
    delete[] buf;
  }
}

// Return the standard deviation of given array of number
static double
standarDeviation(const vector<uint32_t>& v)
{
  uint64_t total = 0;
  for (vector<uint32_t>::const_iterator i = v.begin(), e = v.end();
      i != e; ++i) {
    total += *i;
  }

  double avg = total / (double)v.size();
  double sd = 0;

  for (vector<uint32_t>::const_iterator i = v.begin(), e = v.end();
       i != e; ++i) {
    double t = avg - *i;
    sd = sd + t*t;
  }

  return sqrt(sd/v.size());
}

static vector<double>
benchmarkConflictHelper(uint64_t seed, uint32_t bucketNum,
			const vector<string>& strs)
{
  if (bucketNum & (bucketNum - 1)) {
    bucketNum = (1L << (log2_floor(bucketNum) + 1));
  }
  uint32_t mask = bucketNum - 1;

  vector<uint32_t> conflictWasSparse(bucketNum);
  vector<uint32_t> conflictIsSparse(bucketNum);
  vector<uint32_t> conflictWasDense(bucketNum);
  vector<uint32_t> conflictIsDense(bucketNum);

  conflictWasSparse.resize(bucketNum);
  conflictIsSparse.resize(bucketNum);
  conflictWasDense.resize(bucketNum);
  conflictIsDense.resize(bucketNum);

  for (vector<string>::const_iterator i = strs.begin(), e = strs.end();
       i != e; ++i) {
    uint32_t h1 = original_hash_sparse(seed, i->c_str(), i->size());
    uint32_t h2 = hash_sparse_sse42(seed, i->c_str(), i->size());
    uint32_t h3 = original_hash_dense(seed, h1, i->c_str(), i->size());
    uint32_t h4 = hash_dense_sse42(seed, h2, i->c_str(), i->size());

    conflictWasSparse[h1 & mask]++;
    conflictIsSparse[h2 & mask]++;
    conflictWasDense[h3 & mask]++;
    conflictIsDense[h4 & mask]++;
  }

#if 0
  std::sort(conflictWas.begin(), conflictWas.end(), std::greater<int>());
  std::sort(conflictIs.begin(), conflictIs.end(), std::greater<int>());

  fprintf(stderr, "%d %d %d %d vs %d %d %d %d\n",
          conflictWas[0], conflictWas[1], conflictWas[2], conflictWas[3],
          conflictIs[0], conflictIs[1], conflictIs[2], conflictIs[3]);
#endif
  vector<double> ret(4);
  ret[0] = standarDeviation(conflictWasSparse);
  ret[1] = standarDeviation(conflictIsSparse);
  ret[2] = standarDeviation(conflictWasDense);
  ret[3] = standarDeviation(conflictIsDense);

  return ret;
}

static void
benchmarkConflict(uint64_t seed)
{
  float loadFactor[] = { 0.5f, 1.0f, 2.0f, 4.0f, 8.0f };
  int bucketNum[] = { 512, 1024, 2048, 4096, 8192, 16384};
  int lenRange[][2] = { {1,3}, {4, 15}, {16, 127}, {128, 1024}, {1, 1024}};

  fprintf(stdout,
          "\nBechmarking conflict (stand deviation of conflict)\n%s\n",
          separator);

  for (uint32_t k = 0; k < sizeof(lenRange)/sizeof(lenRange[0]); k++) {
    fprintf(stdout, "\nlen range from %d - %d\n", lenRange[k][0],
            lenRange[k][1]);
    fprintf(stdout, "%-10s %-12s %-10s %-10s diff (s) %-10s %-10s diff (d)\n%s\n",
	    "bucket", "load-factor", "was (s)", "is (s)", "was (d)", "is (d)",
	    separator);
    for (uint32_t i = 0; i < sizeof(bucketNum)/sizeof(bucketNum[0]); ++i) {
      for (uint32_t j = 0;
           j < sizeof(loadFactor)/sizeof(loadFactor[0]);
           ++j) {
        int strNum = bucketNum[i] * loadFactor[j];
        vector<string> strs(strNum);
        genRandomString(lenRange[k][0], lenRange[k][1], strNum, strs);

        vector<double> p;
        p = benchmarkConflictHelper(seed, bucketNum[i], strs);
        fprintf(stdout, "%-10d %-12.2f %-10.2f %-10.2f %-10.2f %-10.2f %-10.2f %.2f\n",
                bucketNum[i], loadFactor[j],
		p[0], p[1], p[0] - p[1],
		p[2], p[3], p[2] - p[3]);
      }
    }
  }
}

static void
benchmarkHashFunc()
{
  srand(time(0));

  uint64_t seed = (uint32_t) rand();
  char buf[4096];
  char c = getpid() % 'a';
  for (int i = 0; i < (int)sizeof(buf); i++) {
    buf[i] = (c + i) % 255;
  }

  benchmarkConflict(seed);
  benchmarkIndividual(seed, buf);
  benchmarkToggleLens(seed, buf);
}

int
main(int argc, char** argv)
{
  fprintf(stdout, "========================\nMicro benchmark...\n");
  benchmarkHashFunc();
  return 0;
}
