#include <stdlib.h>

#include "../libinjection.h"
#include "../libinjection_sqli.h"
#include "../libinjection_xss.h"

int LLVMFuzzerTestOneInput(const u_int8_t *data, size_t size);

int LLVMFuzzerTestOneInput( // cppcheck-suppress unusedFunction
    const u_int8_t *data,
    size_t size) { // cppcheck-suppress unmatchedSuppression
    char fingerprint[8];

    libinjection_sqli((const char *)data, size, fingerprint);

    libinjection_xss((const char *)data, size);

    return 0;
}
