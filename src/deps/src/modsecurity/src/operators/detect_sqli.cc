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

#include "src/operators/detect_sqli.h"

#include <string>
#include <list>
#include <array>

#include "src/operators/operator.h"
#include "src/operators/libinjection_utils.h"
#include "src/operators/libinjection_adapter.h"
#include "src/utils/string.h"
#include "libinjection/src/libinjection_error.h"

namespace modsecurity::operators {

bool DetectSQLi::evaluate(Transaction *t, RuleWithActions *rule,
    const std::string& input, RuleMessage &ruleMessage) {
#ifndef NO_LOGS
    const std::string loggable_input =
        utils::string::limitTo(80, utils::string::toHexIfNeeded(input));
#endif

    std::array<char, 8> fingerprint{};

    const injection_result_t sqli_result =
        runLibinjectionSQLi(input.c_str(), input.length(), fingerprint.data());

    if (t == nullptr) {
        return isMaliciousLibinjectionResult(sqli_result);
    }

    switch (sqli_result) {
        case LIBINJECTION_RESULT_TRUE:
            t->m_matched.emplace_back(fingerprint.data());

#ifndef NO_LOGS
            ms_dbg_a(t, 4,
                std::string("detected SQLi using libinjection with fingerprint '")
                + fingerprint.data() + "' at: '" + loggable_input + "'");
#endif

            if (rule != nullptr && rule->hasCaptureAction()) {
                t->m_collections.m_tx_collection->storeOrUpdateFirst(
                    "0", std::string(fingerprint.data()));

                ms_dbg_a(t, 7,
                    std::string("Added DetectSQLi match TX.0: ")
                    + fingerprint.data());
            }
            break;

        case LIBINJECTION_RESULT_ERROR:
#ifndef NO_LOGS
            ms_dbg_a(t, 4,
                std::string("libinjection parser error during SQLi analysis (")
                + libinjectionResultToString(sqli_result)
                + "); treating as match (fail-safe). Input: '"
                + loggable_input + "'");
#endif

            if (rule != nullptr && rule->hasCaptureAction()) {
                t->m_collections.m_tx_collection->storeOrUpdateFirst(
                    "0", input);

                ms_dbg_a(t, 7,
                    std::string("Added DetectSQLi error input TX.0: ")
                    + input);
            }

            // Keep m_matched untouched for parser-error paths to avoid
            // introducing synthetic fingerprints for non-TRUE results.
            break;

        case LIBINJECTION_RESULT_FALSE:
#ifndef NO_LOGS
            ms_dbg_a(t, 9,
                std::string("libinjection was not able to find any SQLi in: ")
                + loggable_input);
#endif
            break;
    }

    return isMaliciousLibinjectionResult(sqli_result);
}

}  // namespace modsecurity::operators
