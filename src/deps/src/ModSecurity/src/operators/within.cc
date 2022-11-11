/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/operators/within.h"

#include <string>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {


bool Within::evaluate(Transaction *transaction, Rule *rule,
    const std::string &str, std::shared_ptr<RuleMessage> ruleMessage) {
    bool res = false;
    size_t pos = 0;
    std::string paramTarget(m_string->evaluate(transaction));

    if (str.empty()) {
        return true;
    }

    pos = paramTarget.find(str);
    res = pos != std::string::npos;
    if (res) {
        logOffset(ruleMessage, pos, str.size());
    }

    return res;
}


}  // namespace operators
}  // namespace modsecurity
