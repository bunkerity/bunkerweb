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

#include "src/operators/rx_global.h"

#include <string>
#include <list>
#include <memory>

#include "src/operators/operator.h"
#include "modsecurity/rule.h"
#include "modsecurity/rule_message.h"

namespace modsecurity {
namespace operators {


bool RxGlobal::init(const std::string &arg, std::string *error) {
    if (m_string->m_containsMacro == false) {
        m_re = new Regex(m_param);
    }

    return true;
}


bool RxGlobal::evaluate(Transaction *transaction, RuleWithActions *rule,
    const std::string& input, RuleMessage &ruleMessage) {
    Regex *re;

    if (m_param.empty() && !m_string->m_containsMacro) {
        return true;
    }

    if (m_string->m_containsMacro) {
        std::string eparam(m_string->evaluate(transaction));
        re = new Regex(eparam);
    } else {
        re = m_re;
    }

    Utils::RegexResult regex_result;
    std::vector<Utils::SMatchCapture> captures;
    if (transaction && transaction->m_rules->m_pcreMatchLimit.m_set) {
        unsigned long match_limit = transaction->m_rules->m_pcreMatchLimit.m_value;
        regex_result = re->searchGlobal(input, captures, match_limit);
    } else {
        regex_result = re->searchGlobal(input, captures);
    }

    // FIXME: DRY regex error reporting. This logic is currently duplicated in other operators.
    if (regex_result != Utils::RegexResult::Ok) {
        if (transaction) {
            transaction->m_variableMscPcreError.set("1", transaction->m_variableOffset);

            std::string regex_error_str = "OTHER";
            if (regex_result == Utils::RegexResult::ErrorMatchLimit) {
                regex_error_str = "MATCH_LIMIT";
                transaction->m_variableMscPcreLimitsExceeded.set("1", transaction->m_variableOffset);
                transaction->m_collections.m_tx_collection->storeOrUpdateFirst("MSC_PCRE_LIMITS_EXCEEDED", "1");
                ms_dbg_a(transaction, 7, "Set TX.MSC_PCRE_LIMITS_EXCEEDED to 1");
            }

            ms_dbg_a(transaction, 1, "rxGlobal: regex error '" + regex_error_str + "' for pattern '" + re->pattern + "'");
        }

        return false;
    }


    if (rule && rule->hasCaptureAction() && transaction) {
        for (const Utils::SMatchCapture& capture : captures) {
            const std::string capture_substring(input.substr(capture.m_offset,capture.m_length));
            transaction->m_collections.m_tx_collection->storeOrUpdateFirst(
                std::to_string(capture.m_group), capture_substring);
            ms_dbg_a(transaction, 7, "Added regex subexpression TX." +
                std::to_string(capture.m_group) + ": " + capture_substring);
            transaction->m_matched.push_back(capture_substring);
        }
    }

    for (const auto & capture : captures) {
        logOffset(ruleMessage, capture.m_offset, capture.m_length);
    }

    if (m_string->m_containsMacro) {
        delete re;
    }

    if (captures.size() > 0) {
        return true;
    }

    return false;
}


}  // namespace operators
}  // namespace modsecurity
