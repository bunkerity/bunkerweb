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

#include "src/operators/detect_xss.h"

#include <string>

#include "src/operators/operator.h"
#include "src/operators/libinjection_utils.h"
#include "src/operators/libinjection_adapter.h"
#include "src/utils/string.h"
#include "libinjection/src/libinjection_error.h"

namespace modsecurity::operators {

bool DetectXSS::evaluate(Transaction *t, RuleWithActions *rule,
    const std::string& input, RuleMessage &ruleMessage) {
#ifndef NO_LOGS
    const std::string loggable_input =
        utils::string::limitTo(80, utils::string::toHexIfNeeded(input));
#endif

    const injection_result_t xss_result =
        runLibinjectionXSS(input.c_str(), input.length());

    if (t == nullptr) {
        return isMaliciousLibinjectionResult(xss_result);
    }

    switch (xss_result) {
        case LIBINJECTION_RESULT_TRUE:
            ms_dbg_a(t, 5, std::string("detected XSS using libinjection."));
            if (rule != nullptr && rule->hasCaptureAction()) {
                t->m_collections.m_tx_collection->storeOrUpdateFirst("0", input);
                ms_dbg_a(t, 7, std::string("Added DetectXSS match TX.0: ") + input);
            }
            break;

        case LIBINJECTION_RESULT_ERROR:
#ifndef NO_LOGS
            ms_dbg_a(t, 4,
                std::string("libinjection parser error during XSS analysis (")
                + libinjectionResultToString(xss_result)
                + "); treating as match (fail-safe). Input: "
                + loggable_input);
#endif
            if (rule != nullptr && rule->hasCaptureAction()) {
                t->m_collections.m_tx_collection->storeOrUpdateFirst("0", input);
                ms_dbg_a(t, 7, std::string("Added DetectXSS error input TX.0: ") + input);
            }
            break;

        case LIBINJECTION_RESULT_FALSE:
#ifndef NO_LOGS
            ms_dbg_a(t, 9,
                std::string("libinjection was not able to find any XSS in: ")
                + loggable_input);
#endif
            break;
    }

    return isMaliciousLibinjectionResult(xss_result);
}

}  // namespace modsecurity::operators
