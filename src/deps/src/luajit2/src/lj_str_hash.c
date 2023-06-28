/*
 * This file defines string hash function using CRC32. It takes advantage of
 * Intel hardware support (crc32 instruction, SSE 4.2) to speedup the CRC32
 * computation. The hash functions try to compute CRC32 of length and up
 * to 128 bytes of given string.
 */

#include "lj_arch.h"

#if LJ_HAS_OPTIMISED_HASH == 1 || defined(SMOKETEST)
#include <stdint.h>
#include <sys/types.h>
#include <time.h>
#include <smmintrin.h>

#if defined(_MSC_VER)
#include <process.h>
/* Silence deprecated name warning */
#define getpid _getpid
#else
#include <unistd.h>
#endif

#include "lj_def.h"
#include "lj_str.h"
#include "lj_jit.h"


#if defined(_MSC_VER)
/*
 *  MSVC doesn't seem to restrict intrinsics used based on /arch: value set
 *  while clang-cl will error on it.
 */
#if defined(__clang__) && !defined(__SSE4_2__)
#error "This file must be built with /arch:AVX1 or higher"
#endif
#else
#if !defined(__SSE4_2__)
#error "This file must be built with -msse4.2"
#endif
#endif

#define lj_crc32_u32 _mm_crc32_u32
#define lj_crc32_u64 _mm_crc32_u64

#undef LJ_AINLINE
#define LJ_AINLINE

#if defined(__MINGW32__) || defined(_MSC_VER)
#define random()  ((long) rand())
#define srandom(seed)  srand(seed)
#endif

static const uint64_t* cast_uint64p(const char* str)
{
  return (const uint64_t*)(void*)str;
}

static const uint32_t* cast_uint32p(const char* str)
{
  return (const uint32_t*)(void*)str;
}

/* hash string with len in [1, 4) */
static LJ_AINLINE uint32_t hash_sparse_1_4(uint64_t seed, const char* str,
					   uint32_t len)
{
#if 0
  /* TODO: The if-1 part (i.e the original algorithm) is working better when
   * the load-factor is high, as revealed by conflict benchmark (via
   * 'make benchmark' command); need to understand why it's so.
   */
  uint32_t v = str[0];
  v = (v << 8) | str[len >> 1];
  v = (v << 8) | str[len - 1];
  v = (v << 8) | len;
  return lj_crc32_u32(0, v);
#else
  uint32_t a, b, h = len ^ seed;

  a = *(const uint8_t *)str;
  h ^= *(const uint8_t *)(str+len-1);
  b = *(const uint8_t *)(str+(len>>1));
  h ^= b; h -= lj_rol(b, 14);

  a ^= h; a -= lj_rol(h, 11);
  b ^= a; b -= lj_rol(a, 25);
  h ^= b; h -= lj_rol(b, 16);

  return h;
#endif
}

/* hash string with len in [4, 16) */
static LJ_AINLINE uint32_t hash_sparse_4_16(uint64_t seed, const char* str,
					    uint32_t len)
{
  uint64_t v1, v2, h;

  if (len >= 8) {
    v1 = *cast_uint64p(str);
    v2 = *cast_uint64p(str + len - 8);
  } else {
    v1 = *cast_uint32p(str);
    v2 = *cast_uint32p(str + len - 4);
  }

  h = lj_crc32_u32(0, len ^ seed);
  h = lj_crc32_u64(h, v1);
  h = lj_crc32_u64(h, v2);
  return h;
}

/* hash string with length in [16, 128) */
static uint32_t hash_16_128(uint64_t seed, const char* str,
				   uint32_t len)
{
  uint64_t h1, h2;
  uint32_t i;

  h1 = lj_crc32_u32(0, len ^ seed);
  h2 = 0;

  for (i = 0; i < len - 16; i += 16) {
    h1 += lj_crc32_u64(h1, *cast_uint64p(str + i));
    h2 += lj_crc32_u64(h2, *cast_uint64p(str + i + 8));
  };

  h1 = lj_crc32_u64(h1, *cast_uint64p(str + len - 16));
  h2 = lj_crc32_u64(h2, *cast_uint64p(str + len - 8));

  return lj_crc32_u32(h1, h2);
}

/* **************************************************************************
 *
 *  Following is code about hashing string with length >= 128
 *
 * **************************************************************************
 */
static uint32_t random_pos[32][2];
static const int8_t log2_tab[128] = { -1,0,1,1,2,2,2,2,3,3,3,3,3,3,3,3,4,4,
  4,4,4,4,4,4,4,4,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,
  5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,6,6,6,6,6,6,6,6,6,6,6,6,
  6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,
  6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6 };

/* return floor(log2(n)) */
static LJ_AINLINE uint32_t log2_floor(uint32_t n)
{
  if (n <= 127) {
    return log2_tab[n];
  }

  if ((n >> 8) <= 127) {
    return log2_tab[n >> 8] + 8;
  }

  if ((n >> 16) <= 127) {
    return log2_tab[n >> 16] + 16;
  }

  if ((n >> 24) <= 127) {
    return log2_tab[n >> 24] + 24;
  }

  return 31;
}

#define POW2_MASK(n) ((1L << (n)) - 1)

/* This function is to populate `random_pos` such that random_pos[i][*]
 * contains random value in the range of [2**i, 2**(i+1)).
 */
static void str_hash_init_random(void)
{
  int i, seed, rml;

  /* Calculate the ceil(log2(RAND_MAX)) */
  rml = log2_floor(RAND_MAX);
  if (RAND_MAX & (RAND_MAX - 1)) {
    rml += 1;
  }

  /* Init seed */
  seed = lj_crc32_u32(0, getpid());
  seed = lj_crc32_u32(seed, time(NULL));
  srandom(seed);

  /* Now start to populate the random_pos[][]. */
  for (i = 0; i < 3; i++) {
    /* No need to provide random value for chunk smaller than 8 bytes */
    random_pos[i][0] = random_pos[i][1] = 0;
  }

  for (; i < rml; i++) {
    random_pos[i][0] = random() & POW2_MASK(i+1);
    random_pos[i][1] = random() & POW2_MASK(i+1);
  }

  for (; i < 31; i++) {
    int j;
    for (j = 0; j < 2; j++) {
      uint32_t v, scale;
      scale = random_pos[i - rml][0];
      if (scale == 0) {
        scale = 1;
      }
      v = (random() * scale) & POW2_MASK(i+1);
      random_pos[i][j] = v;
    }
  }
}
#undef POW2_MASK

/* Return a pre-computed random number in the range of [1**chunk_sz_order,
 * 1**(chunk_sz_order+1)). It is "unsafe" in the sense that the return value
 * may be greater than chunk-size; it is up to the caller to make sure
 * "chunk-base + return-value-of-this-func" has valid virtual address.
 */
static LJ_AINLINE uint32_t get_random_pos_unsafe(uint32_t chunk_sz_order,
                                                 uint32_t idx)
{
  uint32_t pos = random_pos[chunk_sz_order][idx & 1];
  return pos;
}

static LJ_NOINLINE uint32_t hash_128_above(uint64_t seed, const char* str,
					   uint32_t len)
{
  uint32_t chunk_num, chunk_sz, chunk_sz_log2, i, pos1, pos2;
  uint64_t h1, h2, v;
  const char* chunk_ptr;

  chunk_num = 16;
  chunk_sz = len / chunk_num;
  chunk_sz_log2 = log2_floor(chunk_sz);

  pos1 = get_random_pos_unsafe(chunk_sz_log2, 0);
  pos2 = get_random_pos_unsafe(chunk_sz_log2, 1);

  h1 = lj_crc32_u32(0, len ^ seed);
  h2 = 0;

  /* loop over 14 chunks, 2 chunks at a time */
  for (i = 0, chunk_ptr = str; i < (chunk_num / 2 - 1);
       chunk_ptr += chunk_sz, i++) {

    v = *cast_uint64p(chunk_ptr + pos1);
    h1 = lj_crc32_u64(h1, v);

    v = *cast_uint64p(chunk_ptr + chunk_sz + pos2);
    h2 = lj_crc32_u64(h2, v);
  }

  /* the last two chunks */
  v = *cast_uint64p(chunk_ptr + pos1);
  h1 = lj_crc32_u64(h1, v);

  v = *cast_uint64p(chunk_ptr + chunk_sz - 8 - pos2);
  h2 = lj_crc32_u64(h2, v);

  /* process the trailing part */
  h1 = lj_crc32_u64(h1, *cast_uint64p(str));
  h2 = lj_crc32_u64(h2, *cast_uint64p(str + len - 8));

  h1 = lj_crc32_u32(h1, h2);
  return h1;
}

/* NOTE: the "len" should not be zero */
static StrHash hash_sparse_sse42(uint64_t seed, const char* str, MSize len)
{
  if (len < 4 || len >= 128)
    return hash_sparse_1_4(seed, str, len);

  if (len >= 16) /* [16, 128) */
    return hash_16_128(seed, str, len);

  /* [4, 16) */
  return hash_sparse_4_16(seed, str, len);
}

#if LUAJIT_SECURITY_STRHASH
static StrHash hash_dense_sse42(uint64_t seed, uint32_t h, const char* str,
				MSize len)
{
  uint32_t b = lj_bswap(lj_rol(h ^ (uint32_t)(seed >> 32), 4));

  if (len <= 16)
    return b;

  if (len < 128) /* [16, 128), try with a different seed. */
    return hash_16_128(b, str, len);

  /* Otherwise, do the slow crc32 randomization for long strings. */
  return hash_128_above(b, str, len);
}
#endif

void str_hash_init_sse42(void)
{
  hash_sparse = hash_sparse_sse42;
#if LUAJIT_SECURITY_STRHASH
  hash_dense = hash_dense_sse42;
#endif
  str_hash_init_random();
}
#endif
