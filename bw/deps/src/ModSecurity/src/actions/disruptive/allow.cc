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

#include "src/actions/disruptive/allow.h"

#include <iostream>
#include <string>

#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "modsecurity/rules.h"
#include "src/utils/string.h"
#include "modsecurity/modsecurity.h"


namespace modsecurity {
namespace actions {
namespace disruptive {


bool Allow::init(std::string *error) {
    std::string a = utils::string::tolower(m_parser_payload);

    if (a == "phase") {
        m_allowType = PhaseAllowType;
    } else if (a == "request") {
        m_allowType = RequestAllowType;
    } else if (a == "") {
        m_allowType = FromNowOnAllowType;
    } else {
        error->assign("Allow: if specified, the parameter " \
            "most be: phase, request");
        return false;
    }

    return true;
}


bool Allow::evaluate(Rule *rule, Transaction *transaction) {
    ms_dbg_a(transaction, 4, "Dropping the evaluation of upcoming rules " \
        "in favor of an `allow' action of type: " \
        + allowTypeToName(m_allowType));

    transaction->m_allowType = m_allowType;

    return true;
}


}  // namespace disruptive
}  // namespace actions
}  // namespace modsecurity
