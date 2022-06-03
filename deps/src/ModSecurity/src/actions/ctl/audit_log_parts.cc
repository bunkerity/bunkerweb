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

#include "src/actions/ctl/audit_log_parts.h"

#include <iostream>
#include <string>
#include <utility>

#include "modsecurity/transaction.h"

namespace modsecurity {
namespace actions {
namespace ctl {


bool AuditLogParts::init(std::string *error) {
    std::string what(m_parser_payload, 14, 1);
    mParts = std::string(m_parser_payload, 15, m_parser_payload.length()-15);
    if (what == "+") {
        mPartsAction = 0;
    } else {
        mPartsAction = 1;
    }

    return true;
}

bool AuditLogParts::evaluate(Rule *rule, Transaction *transaction) {
    transaction->m_auditLogModifier.push_back(
        std::make_pair(mPartsAction, mParts));
    return true;
}


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity
