/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#ifndef SRC_OPERATORS_LIBINJECTION_ADAPTER_H_
#define SRC_OPERATORS_LIBINJECTION_ADAPTER_H_

#include <cstddef>

#include "libinjection/src/libinjection_error.h"  // matches detect_xss.cc, detect_sqli.cc, and libinjection_utils.h

namespace modsecurity::operators {

using DetectSQLiFn = injection_result_t (*)(const char *, size_t, char *);
using DetectXSSFn = injection_result_t (*)(const char *, size_t);

injection_result_t runLibinjectionSQLi(const char *input, size_t len,
    char *fingerprint);
injection_result_t runLibinjectionXSS(const char *input, size_t len);

void setLibinjectionSQLiOverrideForTesting(DetectSQLiFn fn);
void setLibinjectionXSSOverrideForTesting(DetectXSSFn fn);
void clearLibinjectionOverridesForTesting();

}  // namespace modsecurity::operators

#endif  // SRC_OPERATORS_LIBINJECTION_ADAPTER_H_
