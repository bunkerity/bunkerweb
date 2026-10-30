#ifndef LIBINJECTION_XSS
#define LIBINJECTION_XSS

#ifdef __cplusplus
extern "C" {
#endif

/**
 * HEY THIS ISN'T DONE
 */

/* pull in size_t */

#include "libinjection.h"
#include "libinjection_html5.h"
#include <string.h>

injection_result_t libinjection_is_xss(const char *s, size_t len, int flags);

#ifdef __cplusplus
}
#endif
#endif
