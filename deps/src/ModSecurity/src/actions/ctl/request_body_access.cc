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

#include "src/actions/ctl/request_body_access.h"

#include <iostream>
#include <string>

#include "modsecurity/rules_properties.h"
#include "modsecurity/transaction.h"

namespace modsecurity {
namespace actions {
namespace ctl {


bool RequestBodyAccess::init(std::string *error) {
    std::string what(m_parser_payload, 18, m_parser_payload.size() - 18);

    if (what == "true") {
        m_request_body_access = true;
    } else if (what == "false") {
        m_request_body_access = false;
    } else {
        error->assign("Internal error. Expected: true or false, got: " \
            + m_parser_payload);
        return false;
    }

    return true;
}

bool RequestBodyAccess::evaluate(Rule *rule, Transaction *transaction) {
    if (m_request_body_access) {
        transaction->m_requestBodyAccess = RulesProperties::TrueConfigBoolean;
    } else {
        transaction->m_requestBodyAccess = RulesProperties::FalseConfigBoolean;
    }

    return true;
}


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity
