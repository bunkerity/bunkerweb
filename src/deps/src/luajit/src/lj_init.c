#include <stdint.h>
#include "lj_arch.h"
#include "lj_jit.h"
#include "lj_vm.h"
#include "lj_str.h"

#if LJ_TARGET_ARM && LJ_TARGET_LINUX
#include <sys/utsname.h>
#endif

#ifdef _MSC_VER
/*
** Append a function pointer to the static constructor table executed by
** the C runtime.
** Based on https://stackoverflow.com/questions/1113409/attribute-constructor-equivalent-in-vc
** see also https://docs.microsoft.com/en-us/cpp/c-runtime-library/crt-initialization.
*/
#pragma section(".CRT$XCU",read)
#define LJ_INITIALIZER2_(f,p) \
        static void f(void); \
        __declspec(allocate(".CRT$XCU")) void (*f##_)(void) = f; \
        __pragma(comment(linker,"/include:" p #f "_")) \
        static void f(void)
#ifdef _WIN64
#define LJ_INITIALIZER(f) LJ_INITIALIZER2_(f,"")
#else
#define LJ_INITIALIZER(f) LJ_INITIALIZER2_(f,"_")
#endif

#else
#define LJ_INITIALIZER(f) static void __attribute__((constructor)) f(void)
#endif


#ifdef LJ_HAS_OPTIMISED_HASH
static void str_hash_init(uint32_t flags)
{
  if (flags & JIT_F_SSE4_2)
    str_hash_init_sse42 ();
}

/* CPU detection for interpreter features such as string hash function
   selection.  We choose to cherry-pick from lj_cpudetect and not have a single
   initializer to make sure that merges with LuaJIT/LuaJIT remain
   convenient. */
LJ_INITIALIZER(lj_init_cpuflags)
{
  uint32_t flags = 0;
#if LJ_TARGET_X86ORX64

  uint32_t vendor[4];
  uint32_t features[4];
  if (lj_vm_cpuid(0, vendor) && lj_vm_cpuid(1, features)) {
    flags |= ((features[2] >> 0)&1) * JIT_F_SSE3;
    flags |= ((features[2] >> 19)&1) * JIT_F_SSE4_1;
    flags |= ((features[2] >> 20)&1) * JIT_F_SSE4_2;
    if (vendor[0] >= 7) {
      uint32_t xfeatures[4];
      lj_vm_cpuid(7, xfeatures);
      flags |= ((xfeatures[1] >> 8)&1) * JIT_F_BMI2;
    }
  }

#endif

  /* The reason why we initialized early: select our string hash functions.  */
  str_hash_init (flags);
}
#endif
