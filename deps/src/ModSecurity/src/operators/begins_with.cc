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

#include "src/operators/begins_with.h"

#include <string>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {


bool BeginsWith::evaluate(Transaction *transaction, Rule *rule,
    const std::string &str, std::shared_ptr<RuleMessage> ruleMessage) {
    std::string p(m_string->evaluate(transaction));

    if (str.size() < p.size()) {
        return false;
    } else if (!str.compare(0, p.size(), p)) {
        logOffset(ruleMessage, 0, p.size());
        return true;
    }

    return false;
}


}  // namespace operators
}  // namespace modsecurity
