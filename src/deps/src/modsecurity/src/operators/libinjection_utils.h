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

#ifndef SRC_OPERATORS_LIBINJECTION_UTILS_H_
#define SRC_OPERATORS_LIBINJECTION_UTILS_H_

#include "libinjection/src/libinjection_error.h"

namespace modsecurity::operators {

/*
 * libinjection parser errors are handled in fail-safe mode as suspicious
 * results, so callers can block on both confirmed detections and parser
 * failures.
 */
static inline bool isMaliciousLibinjectionResult(injection_result_t result) {
    return result == LIBINJECTION_RESULT_TRUE
        || result == LIBINJECTION_RESULT_ERROR;
}

static inline const char *libinjectionResultToString(injection_result_t result) {
    switch (result) {
        case LIBINJECTION_RESULT_TRUE:
            return "attack-detected";
        case LIBINJECTION_RESULT_FALSE:
            return "no-attack";
        case LIBINJECTION_RESULT_ERROR:
            return "parser-error";
    }

    return "unexpected-result";
}

}  // namespace modsecurity::operators

#endif  // SRC_OPERATORS_LIBINJECTION_UTILS_H_
